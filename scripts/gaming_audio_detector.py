import os
import math
import json
import subprocess
from typing import List, Dict, Tuple, Any, Optional

try:
    import numpy as np
    _HAS_NUMPY = True
except ImportError:
    _HAS_NUMPY = False


def compute_audio_zscores(rms_values: List[float], mean: float, std: float) -> List[float]:
    """Computes Z-scores for each RMS audio value against stream baseline."""
    if not rms_values:
        return []
    if std <= 1e-6:
        return [0.0] * len(rms_values)
    if _HAS_NUMPY:
        try:
            rms_arr = np.asarray(rms_values, dtype=np.float32)
            return ((rms_arr - mean) / std).tolist()
        except Exception:
            pass
    return [(v - mean) / std for v in rms_values]


def detect_audio_events(
    rms_values: List[float],
    sample_rate_hz: float = 10.0,
    z_threshold: float = 2.0,
    min_contrast_jump: Optional[float] = None,
) -> List[Dict[str, Any]]:
    """
    Detects spike audio events where volume exceeds z_threshold above baseline.
    sample_rate_hz defaults to 10 (100ms per sample).
    """
    if not rms_values:
        return []

    n = len(rms_values)
    mean = sum(rms_values) / n
    variance = sum((x - mean) ** 2 for x in rms_values) / n
    std = math.sqrt(variance)

    z_scores = compute_audio_zscores(rms_values, mean, std)
    events = []

    # Window step (0.1s per frame)
    step_sec = 1.0 / sample_rate_hz if sample_rate_hz > 0 else 0.1

    i = 0
    while i < n:
        z = z_scores[i]
        if z >= z_threshold:
            # Enforce minimum 1-step cluster span to prevent infinite loops on low/zero rate
            cluster_span = max(1, int(2.0 * max(0.1, sample_rate_hz)))
            cluster_end = min(n, i + cluster_span)
            best_idx = i
            best_z = z
            for j in range(i, cluster_end):
                if z_scores[j] > best_z:
                    best_z = z_scores[j]
                    best_idx = j

            # Check quiet-to-burst contrast (preceding 3 seconds)
            contrast_span = max(1, int(3.0 * max(0.1, sample_rate_hz)))
            contrast_start = max(0, best_idx - contrast_span)
            pre_mean = sum(rms_values[contrast_start:best_idx]) / max(1, best_idx - contrast_start) if best_idx > contrast_start else mean
            jump_ratio = rms_values[best_idx] / max(1e-3, pre_mean)

            # Do not drop peaks if Z >= z_threshold; treat contrast jump as score multiplier/bonus
            # unless min_contrast_jump is strictly specified and not matched.
            if min_contrast_jump is not None and jump_ratio < min_contrast_jump:
                i = max(i + 1, cluster_end)
                continue

            score = min(100.0, max(0.0, (best_z / 4.0) * 80.0 + min(20.0, jump_ratio * 4.0)))
            events.append({
                "timestamp": round(best_idx * step_sec, 2),
                "z_score": round(best_z, 2),
                "intensity": round(rms_values[best_idx], 2),
                "contrast_jump": round(jump_ratio, 2),
                "score": round(score, 1),
            })
            # Skip past cluster; ensure i always advances by at least 1
            i = max(i + 1, cluster_end)
        else:
            i += 1
    events.sort(key=lambda x: x["score"], reverse=True)
    return events


def _design_fir_bandpass(
    low_cut: float = 200,
    high_cut: float = 3500,
    sample_rate: int = 16000,
    num_taps: int = 101,
) -> Any:
    """
    Designs a linear-phase windowed-sinc FIR bandpass filter using Hamming window.
    num_taps must be an odd integer (default 101).
    """
    if not _HAS_NUMPY:
        return None
    if num_taps % 2 == 0:
        num_taps += 1

    sr = float(sample_rate)
    f1 = max(1e-5, min(0.499, float(low_cut) / sr))
    f2 = max(1e-5, min(0.499, float(high_cut) / sr))
    if f1 >= f2:
        f1, f2 = 0.01, 0.49

    c = (num_taps - 1) / 2.0
    n = np.arange(num_taps) - c
    # Ideal sinc bandpass: np.sinc(x) = sin(pi*x)/(pi*x)
    h = 2 * f2 * np.sinc(2 * f2 * n) - 2 * f1 * np.sinc(2 * f1 * n)
    h *= np.hamming(num_taps)
    # Normalize gain to 1.0 at center passband frequency
    f0 = (f1 + f2) / 2.0
    gain = np.abs(np.sum(h * np.cos(2 * np.pi * f0 * n)))
    if gain > 1e-6:
        h /= gain
    return h.astype(np.float32)


def _apply_fir_bandpass(
    audio_arr: Any,
    low_cut: float = 200,
    high_cut: float = 3500,
    sample_rate: int = 16000,
    num_taps: int = 101,
) -> Any:
    """
    Applies FIR bandpass filter to 1D float NumPy array via convolution (same length).
    """
    if not _HAS_NUMPY or audio_arr is None or len(audio_arr) == 0:
        return audio_arr
    h = _design_fir_bandpass(low_cut=low_cut, high_cut=high_cut, sample_rate=sample_rate, num_taps=num_taps)
    if h is None:
        return audio_arr
    return np.convolve(audio_arr, h, mode="same")


def load_rms_cache(
    cache_path: str,
    target_audio: Optional[str] = None,
    chunk_sec: float = 0.1,
    vocal_bandpass: bool = True,
    low_cut: int = 200,
    high_cut: int = 3500,
) -> Optional[Tuple[List[float], float, float]]:
    """
    Loads cached RMS values if cache file exists, is valid JSON, and matches all audio and filter parameters.
    Returns (rms_values, mean, std) or None if invalid/stale/missing.
    """
    try:
        cache_file = os.path.join(cache_path, "rms_cache.json") if os.path.isdir(cache_path) else cache_path
        if not os.path.exists(cache_file):
            return None

        with open(cache_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        if not isinstance(data, dict):
            return None

        if "rms_values" not in data or "mean" not in data or "std" not in data:
            return None

        # Verify filter & chunk parameters
        if "chunk_sec" in data and abs(float(data["chunk_sec"]) - float(chunk_sec)) > 1e-4:
            return None
        if "vocal_bandpass" in data and bool(data["vocal_bandpass"]) != bool(vocal_bandpass):
            return None
        if "low_cut" in data and int(data["low_cut"]) != int(low_cut):
            return None
        if "high_cut" in data and int(data["high_cut"]) != int(high_cut):
            return None

        # Verify audio source mtime and size if audio file is available
        if target_audio and os.path.exists(target_audio):
            current_mtime = os.path.getmtime(target_audio)
            cached_mtime = data.get("audio_mtime")
            if cached_mtime is not None and abs(float(cached_mtime) - float(current_mtime)) > 1e-3:
                return None
            cached_size = data.get("audio_size")
            if cached_size is not None and int(cached_size) != os.path.getsize(target_audio):
                return None

        rms_values = [float(v) for v in data["rms_values"]]
        mean = float(data["mean"])
        std = float(data["std"])
        return rms_values, mean, std
    except Exception:
        return None


def save_rms_cache(
    cache_path: str,
    target_audio: Optional[str] = None,
    rms_values: Optional[List[float]] = None,
    mean: float = 0.0,
    std: float = 0.0,
    chunk_sec: float = 0.1,
    vocal_bandpass: bool = True,
    low_cut: int = 200,
    high_cut: int = 3500,
) -> bool:
    """
    Atomically writes calculated RMS curve and metadata to rms_cache.json.
    """
    tmp_file = None
    try:
        cache_file = os.path.join(cache_path, "rms_cache.json") if os.path.isdir(cache_path) else cache_path
        os.makedirs(os.path.dirname(os.path.abspath(cache_file)), exist_ok=True)

        mtime = 0.0
        size = 0
        if target_audio and os.path.exists(target_audio):
            mtime = os.path.getmtime(target_audio)
            size = os.path.getsize(target_audio)

        payload = {
            "version": 1,
            "audio_path": str(target_audio) if target_audio else "",
            "audio_mtime": mtime,
            "audio_size": size,
            "chunk_sec": float(chunk_sec),
            "vocal_bandpass": bool(vocal_bandpass),
            "low_cut": int(low_cut),
            "high_cut": int(high_cut),
            "rms_values": [float(v) for v in (rms_values or [])],
            "mean": float(mean),
            "std": float(std),
        }

        tmp_file = f"{cache_file}.tmp.{os.getpid()}"
        with open(tmp_file, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
        os.replace(tmp_file, cache_file)
        return True
    except Exception:
        if tmp_file and os.path.exists(tmp_file):
            try:
                os.remove(tmp_file)
            except OSError:
                pass
        return False


def extract_audio_rms_curve(
    video_path: str,
    chunk_sec: Any = 0.1,
    vocal_bandpass: bool = True,
    low_cut: int = 200,
    high_cut: int = 3500,
    audio_path: Optional[str] = None,
    project_folder: Optional[str] = None,
    use_cache: bool = True,
    **kwargs,
) -> Tuple[List[float], float, float]:
    """
    Extracts RMS amplitude per chunk_sec from video_path or pre-extracted audio_path.
    If audio_path is provided or input is already a WAV file, processes audio directly without re-demuxing video.
    When vocal_bandpass is True, applies bandpass filter to focus on human voice frequencies.
    If project_folder is provided and use_cache is True, caches and reuses results via rms_cache.json.
    Returns (rms_list, mean, std).
    """
    # Positional backward compatibility: 2nd argument could be audio_path string
    if isinstance(chunk_sec, (str, os.PathLike)) and audio_path is None:
        audio_path = str(chunk_sec)
        chunk_sec = kwargs.get("chunk_sec", 0.1)

    project_folder = project_folder or kwargs.get("project_folder") or kwargs.get("project_dir")
    if "use_cache" in kwargs:
        use_cache = bool(kwargs["use_cache"])

    target_audio = audio_path if (audio_path and os.path.exists(audio_path)) else video_path
    if not target_audio or not os.path.exists(target_audio):
        return [], 0.0, 0.0

    target_str = str(target_audio)

    # 1. Check cached RMS if project_folder and use_cache
    if project_folder and use_cache:
        cached = load_rms_cache(
            cache_path=project_folder,
            target_audio=target_str,
            chunk_sec=float(chunk_sec),
            vocal_bandpass=vocal_bandpass,
            low_cut=low_cut,
            high_cut=high_cut,
        )
        if cached is not None:
            return cached

    raw_bytes = None
    from_direct_wav = False

    # Fast path: read 16kHz mono PCM directly from WAV
    if target_str.lower().endswith(".wav"):
        try:
            import wave
            with wave.open(target_str, "rb") as wf:
                if wf.getnchannels() == 1 and wf.getsampwidth() == 2 and wf.getframerate() == 16000:
                    raw_bytes = wf.readframes(wf.getnframes())
                    from_direct_wav = True
        except Exception:
            raw_bytes = None
            from_direct_wav = False

    if raw_bytes is None:
        from_direct_wav = False
        cmd = [
            "ffmpeg", "-nostdin", "-y", "-i", target_str,
            "-vn", "-ac", "1", "-ar", "16000",
        ]
        if vocal_bandpass:
            cmd.extend(["-af", f"highpass=f={low_cut},lowpass=f={high_cut}"])
        cmd.extend(["-f", "s16le", "-"])
        try:
            proc = subprocess.run(
                cmd,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                timeout=120,
                check=False,
            )
            raw_bytes = proc.stdout
        except (subprocess.TimeoutExpired, subprocess.SubprocessError, Exception):
            return [], 0.0, 0.0

    if not raw_bytes:
        return [], 0.0, 0.0

    try:
        if len(raw_bytes) % 2 != 0:
            raw_bytes = raw_bytes[:len(raw_bytes) - (len(raw_bytes) % 2)]
        if not raw_bytes:
            return [], 0.0, 0.0

        sample_rate = 16000
        samples_per_chunk = max(1, int(sample_rate * float(chunk_sec)))

        rms_values = []
        mean = 0.0
        std = 0.0

        if _HAS_NUMPY:
            try:
                arr = np.frombuffer(raw_bytes, dtype=np.int16).astype(np.float32)
                if from_direct_wav and vocal_bandpass:
                    arr = _apply_fir_bandpass(
                        arr,
                        low_cut=low_cut,
                        high_cut=high_cut,
                        sample_rate=sample_rate,
                    )
                n_chunks = len(arr) // samples_per_chunk
                if n_chunks > 0:
                    chunks = arr[:n_chunks * samples_per_chunk].reshape(n_chunks, samples_per_chunk)
                    rms_arr = np.sqrt(np.mean(chunks ** 2, axis=1))
                    rms_values = rms_arr.tolist()
                    mean = float(np.mean(rms_arr))
                    std = float(np.std(rms_arr))
                elif len(arr) > 0:
                    rms = float(np.sqrt(np.mean(arr ** 2)))
                    rms_values = [rms]
                    mean = rms
                    std = 0.0
                else:
                    return [], 0.0, 0.0
            except Exception:
                rms_values = []

        if not rms_values:
            # Fallback to pure Python loop
            import array
            samples = array.array("h")
            samples.frombytes(raw_bytes)

            rms_values = []
            usable_samples = (len(samples) // samples_per_chunk) * samples_per_chunk
            samples_to_use = samples[:usable_samples] if usable_samples > 0 else samples

            for offset in range(0, len(samples_to_use), samples_per_chunk):
                chunk = samples_to_use[offset:offset + samples_per_chunk]
                if not chunk:
                    continue
                sq_sum = sum(s * s for s in chunk)
                rms = math.sqrt(sq_sum / len(chunk))
                rms_values.append(rms)

            if not rms_values:
                return [], 0.0, 0.0

            mean = sum(rms_values) / len(rms_values)
            var = sum((x - mean) ** 2 for x in rms_values) / len(rms_values)
            std = math.sqrt(var)

        # Cache calculated results if project_folder and use_cache
        if project_folder and use_cache and rms_values:
            save_rms_cache(
                cache_path=project_folder,
                target_audio=target_str,
                rms_values=rms_values,
                mean=mean,
                std=std,
                chunk_sec=float(chunk_sec),
                vocal_bandpass=vocal_bandpass,
                low_cut=low_cut,
                high_cut=high_cut,
            )

        return rms_values, mean, std
    except (subprocess.TimeoutExpired, subprocess.SubprocessError, Exception):
        return [], 0.0, 0.0
