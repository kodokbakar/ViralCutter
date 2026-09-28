import asyncio
import importlib
import platform
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict
from fastapi import APIRouter

from webui.backend.config import VIRALS_DIR
from webui.backend.schemas.system import SystemHealthResponse, SystemStatusResponse

router = APIRouter()


def _get_gpu_status_sync() -> Dict[str, Any]:
    gpu_info: Dict[str, Any] = {
        "available": False,
        "count": 0,
        "device_name": None,
        "memory_allocated_gb": None,
        "memory_reserved_gb": None,
        "cuda_version": None,
        "nvidia_smi": False,
    }

    try:
        import torch

        cuda_avail = torch.cuda.is_available()
        gpu_info["available"] = cuda_avail
        gpu_info["cuda_version"] = getattr(torch.version, "cuda", None)

        if cuda_avail:
            gpu_info["count"] = torch.cuda.device_count()
            gpu_info["device_name"] = torch.cuda.get_device_name(0)
            gpu_info["memory_allocated_gb"] = round(torch.cuda.memory_allocated() / (1024**3), 2)
            gpu_info["memory_reserved_gb"] = round(torch.cuda.memory_reserved() / (1024**3), 2)
    except Exception:
        pass

    if shutil.which("nvidia-smi"):
        gpu_info["nvidia_smi"] = True

    return gpu_info


def _get_disk_status_sync() -> Dict[str, Any]:
    try:
        usage = shutil.disk_usage(VIRALS_DIR if VIRALS_DIR.exists() else Path.cwd())
        total_gb = round(usage.total / (1024**3), 2)
        used_gb = round(usage.used / (1024**3), 2)
        free_gb = round(usage.free / (1024**3), 2)
        percent_used = round((usage.used / usage.total) * 100, 1) if usage.total > 0 else 0.0
        return {
            "total_gb": total_gb,
            "used_gb": used_gb,
            "free_gb": free_gb,
            "percent_used": percent_used,
            "path": str(VIRALS_DIR.resolve()),
        }
    except Exception as e:
        return {"error": str(e)}


def _get_ffmpeg_status_sync() -> Dict[str, Any]:
    ffmpeg_path = shutil.which("ffmpeg")
    ffprobe_path = shutil.which("ffprobe")
    version = None

    if ffmpeg_path:
        try:
            res = subprocess.run(
                [ffmpeg_path, "-version"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=5,
                check=False,
            )
            first_line = (res.stdout or "").splitlines()[0] if res.stdout else ""
            version = first_line.strip()
        except Exception:
            version = "installed (version check error)"

    return {
        "installed": bool(ffmpeg_path),
        "path": ffmpeg_path,
        "version": version,
        "ffprobe_installed": bool(ffprobe_path),
        "ffprobe_path": ffprobe_path,
    }


def _check_tool_availability_sync() -> Dict[str, bool]:
    modules = ["torch", "whisperx", "faster_whisper", "ctranslate2", "insightface", "yt_dlp"]
    results = {}
    for mod in modules:
        try:
            importlib.import_module(mod)
            results[mod] = True
        except Exception:
            results[mod] = False

    results["ffmpeg"] = bool(shutil.which("ffmpeg"))
    results["ffprobe"] = bool(shutil.which("ffprobe"))
    return results


@router.get("/status", response_model=SystemStatusResponse)
async def get_system_status():
    """
    Retrieve comprehensive system diagnostics including GPU/CUDA status,
    disk space, FFmpeg availability, Python runtime, and AI tools.
    """
    def _gather_all():
        return SystemStatusResponse(
            status="ok",
            gpu=_get_gpu_status_sync(),
            disk=_get_disk_status_sync(),
            ffmpeg=_get_ffmpeg_status_sync(),
            python={
                "version": sys.version.replace("\n", " "),
                "executable": sys.executable,
                "platform": platform.platform(),
            },
            tools=_check_tool_availability_sync(),
        )

    return await asyncio.to_thread(_gather_all)


@router.get("/health", response_model=SystemHealthResponse)
async def get_health():
    """
    Lightweight health check endpoint.
    """
    return SystemHealthResponse(status="ok", timestamp=time.time())
