import asyncio
import importlib
import platform
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict
from fastapi import APIRouter

from scripts.create_viral_segments import verify_ai_connection
from webui.backend.config import BASE_DIR, VIRALS_DIR
from webui.backend.schemas.system import (
    PromptTemplateResponse,
    SystemHealthResponse,
    SystemStatusResponse,
    TestAIRequest,
    TestAIResponse,
)

router = APIRouter()

DEFAULT_PROMPT_TEMPLATE = """You are a World-Class Viral Video Editor and Storyteller. You are an expert at finding "gold nuggets" in long transcripts that can stand alone as viral TikToks/Reels/Shorts.

Your goal is to extract segments that have **Perfect Narrative Completeness** (Start, Middle, End) while respecting time constraints.

### INPUT FORMAT EXPLAINED
The transcript below is a continuous text stream with embedded **Time Tags** like `(12s)`.
- Example: `"Hello world (0s). Today we are going to (3s) fly to the moon."`
- These tags represent the approximate timestamp of the *preceding* text.
- Use them to calculate duration. Duration = (End Tag - Start Tag).

### STRICT VIRAL RULES (The "ViralCutter Standard"):
1.  **NO "GARBAGE" STARTS:**
    -   NEVER start with filler words ("Um", "Uh", "So...", "And then").
    -   NEVER start with low-energy intros ("Hi guys, welcome back").
    -   **ALWAYS** start with a Hook: A strong statement, a question, or an action verb.
    -   *Bad Start:* "(10s) So, I was thinking..."
    -   *Good Start:* "(12s) I almost died yesterday."

2.  **THE "STANDALONE" TEST:**
    -   Can this segment be shown to a stranger without ANY context?
    -   If it contains "That's why *he* said that" (and "he" is unknown), it FAILS. Eliminate or expand context.

3.  **NARRATIVE ARC:**
    -   **Start:** Hook (0-3s).
    -   **Middle:** Value/Story (Retain attention).
    -   **End:** Punchline/Conclusion (Satisfying ending). NEVER cut mid-sentence.

4.  **DURATION MATH:**
    -   Use the `(XXs)` tags to estimate duration.
    -   CONSTRAINT: Segment MUST be between {min_duration}s and {max_duration}s.

5.  **AI HOOK TITLE (STOP-THE-SCROLL HEADER):**
    -   High-converting, curiosity-inducing hook headline in ALL CAPS (4-7 words, e.g. "RAHASIA CUAN DARI AI?!", "JANGAN LAKUKAN HAL INI!").
    -   Must induce FOMO, extreme curiosity, or urgent interest to stop viewers from scrolling.
    -   In the SAME LANGUAGE as the transcript.

### YOUR TASK:
Analyze the transcript below. Find {amount} potential viral segments.

TRANSCRIPT:
{transcript_chunk}

### OUTPUT FORMAT (JSON ONLY):
{json_template}

Return ONLY VALID JSON. No markdown, no commentary."""


def _read_prompt_template_sync() -> str:
    prompt_path = BASE_DIR / "prompt.txt"
    if prompt_path.is_file():
        try:
            return prompt_path.read_text(encoding="utf-8")
        except Exception:
            pass
    return DEFAULT_PROMPT_TEMPLATE


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


@router.post("/test-ai", response_model=TestAIResponse)
async def test_ai_connection(req: TestAIRequest):
    """
    Test connectivity to the specified AI backend provider.
    """
    start = time.perf_counter()
    success, message = await asyncio.to_thread(
        verify_ai_connection,
        backend=req.backend,
        base_url=req.base_url or "",
        api_key=req.api_key or "",
        model_name=req.model_name or "",
    )
    elapsed_ms = int((time.perf_counter() - start) * 1000)

    match = re.search(r"\((\d+)ms\)", message)
    latency_ms = int(match.group(1)) if match else elapsed_ms

    return TestAIResponse(
        success=success,
        message=message,
        latency_ms=latency_ms,
    )


@router.get("/prompt-template", response_model=PromptTemplateResponse)
async def get_prompt_template():
    """
    Get the default AI prompt template from prompt.txt with fallback.
    """
    template = await asyncio.to_thread(_read_prompt_template_sync)
    return PromptTemplateResponse(template=template)
