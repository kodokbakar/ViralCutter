import asyncio
import json
import os
import re
from pathlib import Path
from typing import List, Optional
from fastapi import APIRouter, HTTPException, status

import sys
import types

if "gradio" not in sys.modules:
    try:
        import gradio  # noqa: F401
    except ImportError:
        dummy_gr = types.ModuleType("gradio")
        setattr(dummy_gr, "skip", lambda: None)
        setattr(dummy_gr, "update", lambda **kw: None)
        sys.modules["gradio"] = dummy_gr

from webui.backend.config import VIRALS_DIR
from webui.backend.core.security import sanitize_project_name, validate_safe_path
from webui.backend.schemas.subtitles import (
    SubtitleConvertRequest,
    SubtitleConvertResponse,
    SubtitleItem,
    SubtitleParseRequest,
    SubtitleParseResponse,
    SubtitlePresetsResponse,
    SubtitleSaveRequest,
    SubtitleSaveResponse,
    SubtitleStylePreviewRequest,
    SubtitleStylePreviewResponse,
)
try:
    from webui.subtitle_handler import SUBTITLE_PRESETS, generate_preview_html
except Exception:
    from webui.backend.core.subtitle_presets import SUBTITLE_PRESETS, generate_preview_html

router = APIRouter()


def _timestamp_to_seconds(ts_str: str) -> float:
    """Parse timestamp string (HH:MM:SS,mmm or HH:MM:SS.mmm or MM:SS.mmm) into seconds."""
    ts = ts_str.strip().replace(",", ".")
    parts = ts.split(":")
    if len(parts) == 3:
        h, m, s = parts
        return int(h) * 3600 + int(m) * 60 + float(s)
    elif len(parts) == 2:
        m, s = parts
        return int(m) * 60 + float(s)
    return float(ts or 0.0)


def _seconds_to_srt_timestamp(seconds: float) -> str:
    seconds = max(0.0, float(seconds))
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int(round((seconds - int(seconds)) * 1000))
    if ms >= 1000:
        s += 1
        ms = 0
    if s >= 60:
        m += 1
        s = 0
    if m >= 60:
        h += 1
        m = 0
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def _seconds_to_vtt_timestamp(seconds: float) -> str:
    seconds = max(0.0, float(seconds))
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int(round((seconds - int(seconds)) * 1000))
    if ms >= 1000:
        s += 1
        ms = 0
    if s >= 60:
        m += 1
        s = 0
    if m >= 60:
        h += 1
        m = 0
    return f"{h:02d}:{m:02d}:{s:02d}.{ms:03d}"


def _seconds_to_ass_timestamp(seconds: float) -> str:
    seconds = max(0.0, float(seconds))
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    cs = int(round((seconds - int(seconds)) * 100))
    if cs >= 100:
        s += 1
        cs = 0
    if s >= 60:
        m += 1
        s = 0
    if m >= 60:
        h += 1
        m = 0
    return f"{h:d}:{m:02d}:{s:02d}.{cs:02d}"


def parse_srt_string(content: str) -> List[SubtitleItem]:
    text = content.strip().lstrip("\ufeff").replace("\r\n", "\n")
    if not text:
        return []

    entries = []
    blocks = re.split(r"\n\s*\n", text)
    counter = 1

    for block in blocks:
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        if not lines:
            continue

        # Find timestamp line containing '-->'
        arrow_idx = -1
        for idx, line in enumerate(lines):
            if "-->" in line:
                arrow_idx = idx
                break

        if arrow_idx == -1:
            continue

        time_line = lines[arrow_idx]
        start_str, end_str = time_line.split("-->", 1)
        # Strip any formatting settings after timestamp
        end_str = end_str.strip().split()[0]

        start_sec = _timestamp_to_seconds(start_str)
        end_sec = _timestamp_to_seconds(end_str)

        cue_text = "\n".join(lines[arrow_idx + 1:])
        entries.append(SubtitleItem(index=counter, start=start_sec, end=end_sec, text=cue_text))
        counter += 1

    return entries


def parse_vtt_string(content: str) -> List[SubtitleItem]:
    text = content.strip().lstrip("\ufeff").replace("\r\n", "\n")
    if not text:
        return []

    # Strip WEBVTT header and any header metadata
    if text.startswith("WEBVTT"):
        lines = text.split("\n")
        body_lines = []
        in_header = True
        for line in lines:
            if in_header:
                if not line.strip() or line.strip() == "WEBVTT":
                    in_header = False
                continue
            body_lines.append(line)
        text = "\n".join(body_lines)

    return parse_srt_string(text)


def parse_whisper_json_string(content: str) -> List[SubtitleItem]:
    data = json.loads(content)
    entries = []
    counter = 1

    for seg in data.get("segments", []):
        text = (seg.get("text") or "").strip()
        start = float(seg.get("start", 0.0))
        end = float(seg.get("end", 0.0))
        if text:
            entries.append(SubtitleItem(index=counter, start=start, end=end, text=text))
            counter += 1

    return entries


def render_srt(entries: List[SubtitleItem]) -> str:
    output = []
    for idx, item in enumerate(entries, 1):
        output.append(f"{idx}")
        output.append(f"{_seconds_to_srt_timestamp(item.start)} --> {_seconds_to_srt_timestamp(item.end)}")
        output.append(item.text)
        output.append("")
    return "\n".join(output)


def render_vtt(entries: List[SubtitleItem]) -> str:
    output = ["WEBVTT", ""]
    for idx, item in enumerate(entries, 1):
        output.append(f"{idx}")
        output.append(f"{_seconds_to_vtt_timestamp(item.start)} --> {_seconds_to_vtt_timestamp(item.end)}")
        output.append(item.text)
        output.append("")
    return "\n".join(output)


def render_ass(entries: List[SubtitleItem]) -> str:
    header = """[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Montserrat-ExtraBold,36,&H00FFFFFF,&H0000FFFF,&H00000000,&H00000000,-1,0,0,0,100,100,0,0,1,3,2,2,10,10,200,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    dialogues = []
    for item in entries:
        start_ts = _seconds_to_ass_timestamp(item.start)
        end_ts = _seconds_to_ass_timestamp(item.end)
        clean_text = item.text.replace("\n", "\\N")
        dialogues.append(f"Dialogue: 0,{start_ts},{end_ts},Default,,0,0,0,,{clean_text}")

    return header + "\n".join(dialogues) + "\n"


@router.post("/parse", response_model=SubtitleParseResponse)
async def parse_subtitles(request: SubtitleParseRequest):
    """
    Parse subtitles from raw string content or file path on disk.
    Auto-detects format (SRT, VTT, or JSON) if not explicitly provided.
    """
    raw_content = request.content

    if request.file_path:
        safe_path = validate_safe_path(request.file_path, must_exist=True)
        raw_content = await asyncio.to_thread(safe_path.read_text, encoding="utf-8-sig")

    if not raw_content:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Either content or file_path must be provided",
        )

    # Detect format
    detected_format = (request.format or "").lower()
    if not detected_format:
        stripped = raw_content.strip()
        if stripped.startswith("WEBVTT"):
            detected_format = "vtt"
        elif stripped.startswith("{") or stripped.startswith("["):
            detected_format = "json"
        else:
            detected_format = "srt"

    try:
        if detected_format == "vtt":
            entries = parse_vtt_string(raw_content)
        elif detected_format == "json":
            entries = parse_whisper_json_string(raw_content)
        else:
            entries = parse_srt_string(raw_content)
            detected_format = "srt"

        return SubtitleParseResponse(
            format=detected_format,
            entries=entries,
            count=len(entries),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to parse subtitle content: {e}",
        )


@router.post("/convert", response_model=SubtitleConvertResponse)
async def convert_subtitles(request: SubtitleConvertRequest):
    """
    Convert subtitles between SRT, VTT, and ASS without data corruption.
    """
    raw_content = request.content
    if request.file_path:
        safe_path = validate_safe_path(request.file_path, must_exist=True)
        raw_content = await asyncio.to_thread(safe_path.read_text, encoding="utf-8-sig")

    if not raw_content:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Either content or file_path must be provided",
        )

    target_fmt = request.target_format.lower()
    if target_fmt not in {"srt", "vtt", "ass"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported target format: '{target_fmt}'. Supported: srt, vtt, ass",
        )

    # Parse into entries
    source_fmt = (request.source_format or "").lower()
    if not source_fmt:
        if raw_content.strip().startswith("WEBVTT"):
            source_fmt = "vtt"
        elif raw_content.strip().startswith("{"):
            source_fmt = "json"
        else:
            source_fmt = "srt"

    if source_fmt == "vtt":
        entries = parse_vtt_string(raw_content)
    elif source_fmt == "json":
        entries = parse_whisper_json_string(raw_content)
    else:
        entries = parse_srt_string(raw_content)

    if target_fmt == "vtt":
        converted = render_vtt(entries)
    elif target_fmt == "ass":
        converted = render_ass(entries)
    else:
        converted = render_srt(entries)

    return SubtitleConvertResponse(
        content=converted,
        target_format=target_fmt,
        count=len(entries),
    )


@router.post("/save", response_model=SubtitleSaveResponse)
async def save_subtitles(request: SubtitleSaveRequest):
    """
    Persist subtitle entries to disk under project directory or specified file path.
    """
    fmt = request.format.lower()
    if fmt not in {"srt", "vtt", "ass"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported subtitle format: '{fmt}'",
        )

    if request.file_path:
        target_path = validate_safe_path(request.file_path)
    elif request.project_name:
        safe_proj = sanitize_project_name(request.project_name)
        proj_dir = VIRALS_DIR / safe_proj
        subs_dir = proj_dir / "subs"
        await asyncio.to_thread(subs_dir.mkdir, parents=True, exist_ok=True)
        fname = request.filename or f"subtitles.{fmt}"
        target_path = subs_dir / fname
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Either project_name or file_path must be specified",
        )

    if fmt == "vtt":
        content = render_vtt(request.entries)
    elif fmt == "ass":
        content = render_ass(request.entries)
    else:
        content = render_srt(request.entries)

    await asyncio.to_thread(target_path.write_text, content, encoding="utf-8")
    return SubtitleSaveResponse(
        status="saved",
        file_path=str(target_path.resolve()),
        count=len(request.entries),
    )


@router.get("/presets", response_model=SubtitlePresetsResponse)
async def get_subtitle_presets():
    """
    Retrieve all built-in subtitle animation and style presets.
    """
    return SubtitlePresetsResponse(presets=SUBTITLE_PRESETS)


@router.post("/preview-style", response_model=SubtitleStylePreviewResponse)
async def preview_subtitle_style(request: SubtitleStylePreviewRequest):
    """
    Generate rendered HTML preview of customized subtitle styling.
    """
    html = generate_preview_html(
        font=request.font,
        size=request.size,
        color=request.color,
        highlight=request.highlight_color,
        outline=request.outline_color,
        outline_thick=request.outline_thickness,
        shadow=request.shadow_color,
        shadow_sz=request.shadow_size,
        bold=request.bold,
        italic=request.italic,
        upper=request.uppercase,
        h_size=request.highlight_size,
        w_block=request.words_per_block,
        gap=request.gap_limit,
        mode=request.mode,
        under=request.underline,
        strike=request.strikeout,
        border_s=request.border_style,
        vert_pos=request.vertical_position,
        align=request.alignment,
        remove_punc=request.remove_punctuation,
    )
    return SubtitleStylePreviewResponse(html=html)
