import asyncio
import json
import math
import mimetypes
import os
import shutil
from pathlib import Path
from typing import Generator, Optional
from fastapi import APIRouter, HTTPException, Query, Request, status
from fastapi.responses import FileResponse, Response, StreamingResponse

from webui.backend.config import PREVIEWS_DIR
from webui.backend.core.security import validate_safe_path
from webui.backend.schemas.preview import (
    ThumbnailRequest,
    ThumbnailResponse,
    VideoMetadataResponse,
)
from webui.video_preview import extract_preview_frame

router = APIRouter()

CHUNK_SIZE = 1024 * 1024  # 1MB chunks


def _read_byte_range(file_path: Path, start: int, length: int) -> Generator[bytes, None, None]:
    with open(file_path, "rb") as f:
        f.seek(start)
        remaining = length
        while remaining > 0:
            bytes_to_read = min(CHUNK_SIZE, remaining)
            data = f.read(bytes_to_read)
            if not data:
                break
            remaining -= len(data)
            yield data


@router.get("/stream")
async def stream_video(request: Request, path: str = Query(..., description="Path to video file")):
    """
    Stream video file supporting HTTP 206 Partial Content range requests.
    Enables smooth video scrubbing and seeking in HTML5 video players.
    """
    safe_path = validate_safe_path(path, must_exist=True)

    if not safe_path.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Video file not found: {safe_path.name}",
        )

    file_size = safe_path.stat().st_size
    mime_type, _ = mimetypes.guess_type(str(safe_path))
    content_type = mime_type or "video/mp4"

    range_header = request.headers.get("Range")

    # If no Range header, serve full file
    if not range_header:
        return StreamingResponse(
            _read_byte_range(safe_path, 0, file_size),
            status_code=status.HTTP_200_OK,
            media_type=content_type,
            headers={
                "Accept-Ranges": "bytes",
                "Content-Length": str(file_size),
            },
        )

    # Parse Range: bytes=start-end
    if not range_header.startswith("bytes="):
        raise HTTPException(
            status_code=status.HTTP_416_RANGE_NOT_SATISFIABLE,
            detail="Invalid range header format",
            headers={"Content-Range": f"bytes */{file_size}"},
        )

    range_spec = range_header.replace("bytes=", "").strip()
    try:
        parts = range_spec.split("-", 1)
        start_str = parts[0].strip()
        end_str = parts[1].strip() if len(parts) > 1 else ""

        if not start_str and end_str:
            # Suffix range: bytes=-500
            suffix_len = int(end_str)
            start = max(0, file_size - suffix_len)
            end = file_size - 1
        elif start_str and not end_str:
            # Prefix range: bytes=100-
            start = int(start_str)
            end = file_size - 1
        elif start_str and end_str:
            # Full range: bytes=100-200
            start = int(start_str)
            end = int(end_str)
        else:
            raise ValueError("Empty range")

        if start < 0 or start >= file_size or end < start:
            raise ValueError("Out of bounds")

        # Clamp end to file size
        end = min(end, file_size - 1)
        length = end - start + 1
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_416_RANGE_NOT_SATISFIABLE,
            detail="Range not satisfiable",
            headers={"Content-Range": f"bytes */{file_size}"},
        )

    headers = {
        "Content-Range": f"bytes {start}-{end}/{file_size}",
        "Accept-Ranges": "bytes",
        "Content-Length": str(length),
        "Content-Type": content_type,
    }

    return StreamingResponse(
        _read_byte_range(safe_path, start, length),
        status_code=status.HTTP_206_PARTIAL_CONTENT,
        media_type=content_type,
        headers=headers,
    )


@router.get("/metadata", response_model=VideoMetadataResponse)
async def get_video_metadata(path: str = Query(..., description="Path to video file")):
    """
    Extract video resolution, duration, fps, codec, and bitrate via ffprobe.
    """
    safe_path = validate_safe_path(path, must_exist=True)

    ffprobe_bin = shutil.which("ffprobe")
    if not ffprobe_bin:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="ffprobe utility not installed or available on PATH",
        )

    cmd = [
        ffprobe_bin,
        "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "stream=width,height,duration,r_frame_rate,codec_name:format=duration,size,bit_rate",
        "-of", "json",
        str(safe_path),
    ]

    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=15.0)
    except asyncio.TimeoutError:
        try:
            proc.kill()
            await proc.wait()
        except Exception:
            pass
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="Subprocess execution timed out during metadata extraction",
        )

    if proc.returncode != 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to inspect video metadata: {stderr.decode('utf-8', errors='ignore')}",
        )

    try:
        data = json.loads(stdout.decode("utf-8"))
        stream = (data.get("streams") or [{}])[0]
        fmt = data.get("format") or {}

        width = int(stream.get("width") or 0)
        height = int(stream.get("height") or 0)
        codec = stream.get("codec_name")

        # Parse duration
        duration_val = stream.get("duration") or fmt.get("duration") or 0.0
        duration = float(duration_val)

        # Parse fps from r_frame_rate e.g. "30/1" or "24000/1001"
        fps_str = stream.get("r_frame_rate", "0/0")
        fps = 0.0
        if "/" in fps_str:
            num, den = fps_str.split("/", 1)
            if float(den) > 0:
                fps = round(float(num) / float(den), 2)
        else:
            fps = float(fps_str or 0.0)

        # Bitrate
        bitrate_val = fmt.get("bit_rate") or stream.get("bit_rate")
        bitrate = int(bitrate_val) if bitrate_val else None

        # Aspect ratio string
        aspect_ratio = None
        if width > 0 and height > 0:
            gcd = math.gcd(width, height)
            aspect_ratio = f"{width // gcd}:{height // gcd}"

        return VideoMetadataResponse(
            width=width,
            height=height,
            duration=duration,
            fps=fps,
            bitrate=bitrate,
            codec=codec,
            aspect_ratio=aspect_ratio,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error parsing ffprobe output: {e}",
        )


@router.post("/thumbnail", response_model=ThumbnailResponse)
async def generate_thumbnail(request: ThumbnailRequest):
    """
    Generate representative thumbnail frame for video and cache under PREVIEWS_DIR.
    """
    safe_path = validate_safe_path(request.path, must_exist=True)

    await asyncio.to_thread(PREVIEWS_DIR.mkdir, parents=True, exist_ok=True)
    thumb_name = f"thumb_{safe_path.stem}_{int(request.timestamp * 1000)}.jpg"
    thumb_path = PREVIEWS_DIR / thumb_name

    # Extract frame
    extracted = await asyncio.to_thread(
        extract_preview_frame,
        video_path=str(safe_path),
        output_path=str(thumb_path),
        timestamp=request.timestamp,
        width=request.width,
        height=request.height,
    )

    if not extracted or not thumb_path.exists():
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to extract thumbnail frame from video",
        )

    return ThumbnailResponse(
        thumbnail_path=str(thumb_path.resolve()),
        filename=thumb_name,
    )


@router.get("/thumbnail")
async def get_thumbnail_file(path: str = Query(..., description="Path to thumbnail image")):
    """
    Retrieve thumbnail image file directly.
    """
    safe_thumb = validate_safe_path(path, allowed_roots=[PREVIEWS_DIR], must_exist=True)
    return FileResponse(safe_thumb, media_type="image/jpeg")
