import asyncio
import hashlib
import json
import math
import mimetypes
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any, Generator, Optional
from fastapi import APIRouter, HTTPException, Query, Request, status
from fastapi.responses import FileResponse, Response, StreamingResponse

from scripts import subtitle_fonts
from scripts.burn_subtitles import _escape_filter_path
from webui.backend.config import PREVIEWS_DIR
from webui.backend.core.security import validate_safe_path
from webui.backend.schemas.preview import (
    SubtitleVideoPreviewRequest,
    SubtitleVideoPreviewResponse,
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


def _to_ass_color(col: Any, default: str = "&H00FFFFFF&", alpha: str = "00") -> str:
    if not col:
        return default
    col = str(col).strip()
    if col.startswith("&H") and col.endswith("&"):
        return col
    if col.startswith("#"):
        col = col[1:]
    if len(col) == 6:
        r, g, b = col[0:2], col[2:4], col[4:6]
        return f"&H{alpha}{b}{g}{r}&"
    return default


def _generate_subtitle_preview_video_sync(
    video_path: Optional[str],
    subtitle_config: Optional[dict],
    sample_text: str,
    timestamp: float,
    duration: float,
) -> Path:
    PREVIEWS_DIR.mkdir(parents=True, exist_ok=True)
    cfg = subtitle_config or {}

    config_hash = hashlib.md5(
        f"{video_path}_{json.dumps(cfg, sort_keys=True)}_{sample_text}_{timestamp}_{duration}".encode()
    ).hexdigest()[:12]
    out_video = PREVIEWS_DIR / f"sub_preview_{config_hash}.mp4"
    if out_video.exists() and out_video.stat().st_size > 1000:
        return out_video

    ass_path = PREVIEWS_DIR / f"sub_preview_{config_hash}.ass"

    font_name = cfg.get("font") or cfg.get("font_name") or "Montserrat-ExtraBold"
    try:
        font_entry = subtitle_fonts.resolve_font(font_name)
        ass_font_name = font_entry.get("ass_name") or font_entry.get("label") or font_entry.get("family") or font_name
    except Exception:
        ass_font_name = font_name

    base_size = int(cfg.get("fontSize") or cfg.get("base_size") or cfg.get("size") or 32)
    base_color = _to_ass_color(cfg.get("color") or cfg.get("base_color"), "&H00FFFFFF&")
    outline_color = _to_ass_color(cfg.get("outlineColor") or cfg.get("outline_color"), "&H00000000&")
    shadow_color = _to_ass_color(cfg.get("shadowColor") or cfg.get("shadow_color"), "&H00000000&")
    outline_thickness = float(cfg.get("outlineThickness") or cfg.get("outline_thickness") or 2.0)
    shadow_size = float(cfg.get("shadowSize") or cfg.get("shadow_size") or 1.0)
    border_style = int(cfg.get("border_style") or 1)
    alignment = int(cfg.get("alignment") or 2)
    vertical_position = int(cfg.get("vertical_position") or 210)
    bold = 1 if cfg.get("bold", True) else 0
    italic = 1 if cfg.get("italic", False) else 0

    dur_int = max(1, int(duration))
    dur_cs = int((duration % 1) * 100)
    time_str = f"0:00:{dur_int:02d}.{dur_cs:02d}"

    ass_content = f"""[Script Info]
Title: Subtitle Preview
ScriptType: v4.00+
PlayResX: 540
PlayResY: 960

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{ass_font_name},{base_size},{base_color},&H00000000&,{outline_color},{shadow_color},{bold},{italic},0,0,100,100,0,0,{border_style},{outline_thickness},{shadow_size},{alignment},-2,-2,{vertical_position},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
Dialogue: 0,0:00:00.00,{time_str},Default,,0,0,0,,{sample_text}
"""
    ass_path.write_text(ass_content, encoding="utf-8")

    escaped_ass = _escape_filter_path(str(ass_path))
    escaped_fonts_dir = _escape_filter_path(subtitle_fonts.get_fonts_dir())
    sub_filter = f"subtitles='{escaped_ass}':fontsdir='{escaped_fonts_dir}'"

    valid_video = bool(video_path and os.path.exists(video_path))

    if valid_video:
        filter_str = f"scale=540:960:force_original_aspect_ratio=decrease,pad=540:960:(ow-iw)/2:(oh-ih)/2:black,{sub_filter}"
        cmd = [
            "ffmpeg", "-y",
            "-ss", f"{float(timestamp):.3f}",
            "-t", f"{float(duration):.3f}",
            "-i", str(video_path),
            "-vf", filter_str,
            "-c:v", "libx264",
            "-preset", "ultrafast",
            "-crf", "23",
            "-c:a", "aac",
            "-b:a", "96k",
            str(out_video),
        ]
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if res.returncode != 0 or not out_video.exists() or out_video.stat().st_size <= 500:
            cmd[3] = "0.0"
            subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    else:
        cmd = [
            "ffmpeg", "-y",
            "-f", "lavfi",
            "-i", f"color=c=black:s=540x960:r=25:d={duration}",
            "-vf", sub_filter,
            "-c:v", "libx264",
            "-preset", "ultrafast",
            "-crf", "23",
            str(out_video),
        ]
        subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)

    if not out_video.exists() or out_video.stat().st_size <= 500:
        raise RuntimeError("Failed to generate subtitle preview video")

    return out_video


@router.post("/subtitle-video", response_model=SubtitleVideoPreviewResponse)
async def generate_subtitle_video_preview(req: SubtitleVideoPreviewRequest):
    """
    Generate a 3-second 9:16 video clip with burned sample subtitles.
    """
    resolved_video_path = None
    if req.video_path:
        try:
            safe_p = validate_safe_path(req.video_path, must_exist=True)
            if safe_p.is_file():
                resolved_video_path = str(safe_p.resolve())
        except Exception:
            resolved_video_path = None

    try:
        out_video = await asyncio.to_thread(
            _generate_subtitle_preview_video_sync,
            video_path=resolved_video_path,
            subtitle_config=req.subtitle_config,
            sample_text=req.sample_text,
            timestamp=req.timestamp,
            duration=req.duration,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate subtitle video preview: {e}",
        )

    return SubtitleVideoPreviewResponse(
        preview_url=f"/api/v1/preview/stream?path={out_video.resolve()}",
        file_path=str(out_video.resolve()),
    )
