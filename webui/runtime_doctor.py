import importlib
import os
import platform
import shutil
import subprocess
import sys
import time


def _ok(label, value):
    return f"✅ {label}: {value}"


def _warn(label, value):
    return f"⚠️ {label}: {value}"


def _fail(label, value):
    return f"❌ {label}: {value}"


def _run_command(cmd, timeout=20):
    try:
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=timeout,
            check=False,
        )
        return result.returncode, result.stdout.strip(), result.stderr.strip()
    except subprocess.TimeoutExpired:
        return 124, "", f"Timed out after {timeout}s"
    except Exception as e:
        return 1, "", str(e)


def _first_line(text):
    return str(text or "").splitlines()[0] if text else ""


def _import_module(name):
    started = time.time()

    try:
        module = importlib.import_module(name)
        elapsed = time.time() - started
        version = getattr(module, "__version__", "unknown")
        return True, f"{version} imported in {elapsed:.2f}s", None
    except Exception as e:
        elapsed = time.time() - started
        return False, f"failed after {elapsed:.2f}s", str(e)


def _check_python():
    lines = [
        _ok("Python executable", sys.executable),
        _ok("Python version", sys.version.replace("\n", " ")),
        _ok("Platform", platform.platform()),
        _ok("Working directory", os.getcwd()),
    ]

    return lines


def _check_torch():
    ok, message, error = _import_module("torch")
    if not ok:
        return [_fail("torch import", f"{message}: {error}")], False

    import torch

    lines = [_ok("torch import", message)]
    lines.append(_ok("torch version", getattr(torch, "__version__", "unknown")))
    lines.append(_ok("torch CUDA version", getattr(torch.version, "cuda", None)))

    cuda_available = torch.cuda.is_available()
    lines.append((_ok if cuda_available else _fail)("torch.cuda.is_available()", cuda_available))

    if cuda_available:
        try:
            gpu_name = torch.cuda.get_device_name(0)
            allocated = torch.cuda.memory_allocated() / 1024**3
            reserved = torch.cuda.memory_reserved() / 1024**3

            lines.append(_ok("GPU device", gpu_name))
            lines.append(_ok("torch GPU memory", f"allocated={allocated:.2f}GB reserved={reserved:.2f}GB"))
        except Exception as e:
            lines.append(_warn("torch GPU detail", e))

    return lines, cuda_available


def _check_nvidia_smi():
    if not shutil.which("nvidia-smi"):
        return [_fail("nvidia-smi", "not found in PATH")], False

    code, stdout, stderr = _run_command(
        [
            "nvidia-smi",
            "--query-gpu=name,memory.used,memory.total,utilization.gpu,driver_version",
            "--format=csv,noheader,nounits",
        ],
        timeout=20,
    )

    if code != 0:
        return [_fail("nvidia-smi", stderr or stdout or f"exit code {code}")], False

    lines = [_ok("nvidia-smi", stdout)]
    return lines, True


def _check_module_imports():
    checks = [
        ("whisperx", "whisperx import"),
        ("ctranslate2", "ctranslate2 import"),
        ("faster_whisper", "faster_whisper import"),
    ]

    lines = []
    passed = True

    for module_name, label in checks:
        ok, message, error = _import_module(module_name)
        if ok:
            lines.append(_ok(label, message))
        else:
            lines.append(_fail(label, f"{message}: {error}"))
            passed = False

    try:
        import ctranslate2

        if hasattr(ctranslate2, "get_supported_compute_types"):
            try:
                cuda_types = ctranslate2.get_supported_compute_types("cuda")
                lines.append(_ok("CTranslate2 CUDA compute types", ", ".join(cuda_types) or "none"))
                if "float16" not in cuda_types:
                    lines.append(_warn("CTranslate2 float16", "float16 not listed for CUDA"))
            except Exception as e:
                lines.append(_warn("CTranslate2 CUDA compute types", e))

            try:
                cpu_types = ctranslate2.get_supported_compute_types("cpu")
                lines.append(_ok("CTranslate2 CPU compute types", ", ".join(cpu_types) or "none"))
            except Exception as e:
                lines.append(_warn("CTranslate2 CPU compute types", e))
    except Exception:
        pass

    return lines, passed


def _check_ffmpeg(input_video_path=None):
    lines = []
    passed = True

    if not shutil.which("ffmpeg"):
        lines.append(_fail("ffmpeg", "not found in PATH"))
        passed = False
    else:
        code, stdout, stderr = _run_command(["ffmpeg", "-version"], timeout=20)
        if code == 0:
            lines.append(_ok("ffmpeg", _first_line(stdout)))
        else:
            lines.append(_fail("ffmpeg", stderr or stdout or f"exit code {code}"))
            passed = False

    if not shutil.which("ffprobe"):
        lines.append(_fail("ffprobe", "not found in PATH"))
        passed = False
    else:
        code, stdout, stderr = _run_command(["ffprobe", "-version"], timeout=20)
        if code == 0:
            lines.append(_ok("ffprobe", _first_line(stdout)))
        else:
            lines.append(_fail("ffprobe", stderr or stdout or f"exit code {code}"))
            passed = False

    input_video_path = str(input_video_path or "").strip()
    if input_video_path:
        if not os.path.exists(input_video_path):
            lines.append(_fail("input video", f"not found: {input_video_path}"))
            passed = False
        else:
            size_mb = os.path.getsize(input_video_path) / 1024**2
            lines.append(_ok("input video path", input_video_path))
            lines.append(_ok("input video size", f"{size_mb:.2f} MB"))

            code, stdout, stderr = _run_command(
                [
                    "ffprobe",
                    "-v", "error",
                    "-show_entries", "format=duration",
                    "-of", "default=noprint_wrappers=1:nokey=1",
                    input_video_path,
                ],
                timeout=30,
            )

            if code == 0 and stdout:
                try:
                    duration = float(stdout)
                    lines.append(_ok("input video duration", f"{duration:.2f}s / {duration / 60:.2f}m"))
                except ValueError:
                    lines.append(_warn("input video duration", stdout))
            else:
                lines.append(_fail("input video duration", stderr or stdout or f"exit code {code}"))
                passed = False
    else:
        lines.append(_warn("input video", "not provided; duration check skipped"))

    return lines, passed


def _verdict(cuda_ok, nvidia_ok, imports_ok, ffmpeg_ok):
    if cuda_ok and nvidia_ok and imports_ok and ffmpeg_ok:
        return [
            "",
            "VERDICT",
            "✅ Runtime looks ready for GPU WhisperX transcription.",
            "Tip: start with Whisper model 'small' and 1-3 segments for the first smoke test.",
        ]

    lines = ["", "VERDICT"]

    if not cuda_ok:
        lines.append("❌ CUDA is not available to torch. WhisperX will not use the GPU.")
    if not nvidia_ok:
        lines.append("❌ nvidia-smi failed. Colab may not be attached to a GPU runtime.")
    if not imports_ok:
        lines.append("❌ WhisperX / CTranslate2 / faster-whisper import failed. Fix notebook dependencies before running.")
    if not ffmpeg_ok:
        lines.append("❌ ffmpeg/ffprobe check failed. Video/audio loading may hang or fail.")

    lines.append("Recommended next step: fix failed checks before starting a long transcription job.")
    return lines


def run_runtime_doctor(input_video_path=None):
    started = time.time()
    lines = [
        "=" * 72,
        "ViralCutter Runtime Doctor",
        "=" * 72,
    ]

    lines.extend(_check_python())

    lines.append("")
    lines.append("GPU / CUDA")
    torch_lines, cuda_ok = _check_torch()
    lines.extend(torch_lines)

    nvidia_lines, nvidia_ok = _check_nvidia_smi()
    lines.extend(nvidia_lines)

    lines.append("")
    lines.append("WhisperX stack")
    import_lines, imports_ok = _check_module_imports()
    lines.extend(import_lines)

    lines.append("")
    lines.append("Video tools")
    ffmpeg_lines, ffmpeg_ok = _check_ffmpeg(input_video_path=input_video_path)
    lines.extend(ffmpeg_lines)

    lines.extend(_verdict(cuda_ok, nvidia_ok, imports_ok, ffmpeg_ok))

    elapsed = time.time() - started
    lines.append("")
    lines.append(f"Doctor completed in {elapsed:.2f}s.")

    return "\n".join(str(line) for line in lines)