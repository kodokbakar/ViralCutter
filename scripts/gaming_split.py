import os
import re
import sys
import subprocess
from typing import Tuple, Optional, List

_CACHED_ENCODER = ("libx264", "ultrafast", ["-crf", "18"]) if "pytest" in sys.modules else None

def get_best_encoder() -> Tuple[str, str, List[str]]:
    """
    Detects best available video encoder with hardware acceleration and caching.
    Returns (codec_name, preset, extra_args).
    """
    global _CACHED_ENCODER
    if _CACHED_ENCODER is not None:
        return _CACHED_ENCODER

    try:
        res = subprocess.run(["ffmpeg", "-hide_banner", "-encoders"], capture_output=True, text=True)
        out = res.stdout or ""

        # 1. Try NVENC with quick 1-frame probe
        if "h264_nvenc" in out:
            try:
                probe = subprocess.run(
                    ["ffmpeg", "-y", "-f", "lavfi", "-i", "testsrc=d=0.1:s=64x64:r=1", "-c:v", "h264_nvenc", "-f", "null", "-"],
                    capture_output=True,
                    check=True
                )
                _CACHED_ENCODER = ("h264_nvenc", "p1", ["-b:v", "5M"])
                return _CACHED_ENCODER
            except Exception:
                pass
        if "h264_amf" in out:
            _CACHED_ENCODER = ("h264_amf", "speed", ["-b:v", "5M"])
            return _CACHED_ENCODER
        if "h264_qsv" in out:
            _CACHED_ENCODER = ("h264_qsv", "veryfast", ["-b:v", "5M"])
            return _CACHED_ENCODER
    except Exception:
        pass
    _CACHED_ENCODER = ("libx264", "ultrafast", ["-crf", "18"])
    return _CACHED_ENCODER

from scripts.gaming_facecam_detector import FACECAM_QUADRANTS, DEFAULT_FACECAM_BOX
DEFAULT_GAMEPLAY_BOX = "0.25,0.0,0.50,0.622"
DEFAULT_MANUAL_CROP_BOX = "0.3418,0.0,0.3164,1.0"

def parse_normalized_box(box_str: str) -> Tuple[float, float, float, float]:
    """
    Parses 'x,y,w,h' string or quadrant preset into clamped (x, y, w, h) floats in range [0.0, 1.0].
    Enforces minimum width/height of 0.05 to avoid zero-dimension FFmpeg crashes.
    """
    cleaned = str(box_str or "").strip().lower()
    if cleaned in FACECAM_QUADRANTS:
        cleaned = FACECAM_QUADRANTS[cleaned]
    elif cleaned == "auto":
        cleaned = DEFAULT_FACECAM_BOX

    parts = [p.strip() for p in cleaned.split(",") if p.strip()]
    if len(parts) != 4:
        parts = [p.strip() for p in DEFAULT_FACECAM_BOX.split(",")]
    try:
        x, y, w, h = [float(p) for p in parts]
    except (ValueError, TypeError):
        x, y, w, h = 0.0, 0.0, 0.5, 0.5

    w = max(0.05, min(1.0, w))
    h = max(0.05, min(1.0, h))
    x = max(0.0, min(1.0 - w, x))
    y = max(0.0, min(1.0 - h, y))

    x = round(x, 4)
    y = round(y, 4)
    w = round(w, 4)
    h = round(h, 4)

    if x + w > 1.0:
        x = round(1.0 - w, 4)
    if y + h > 1.0:
        y = round(1.0 - h, 4)

    return x, y, w, h

def to_pixel_box(normalized_box: str, src_w: int, src_h: int) -> Tuple[int, int, int, int]:
    """
    Converts normalized coordinates to even pixel integers (x, y, w, h).
    """
    x, y, w, h = parse_normalized_box(normalized_box)
    px_x = int(round(x * src_w))
    px_y = int(round(y * src_h))
    px_w = int(round(w * src_w))
    px_h = int(round(h * src_h))

    px_w = max(2, min(src_w, px_w - (px_w % 2)))
    px_h = max(2, min(src_h, px_h - (px_h % 2)))

    px_x = min(px_x, src_w - px_w)
    px_y = min(px_y, src_h - px_h)
    px_x = max(0, px_x - (px_x % 2))
    px_y = max(0, px_y - (px_y % 2))

    if px_x + px_w > src_w:
        px_w = max(2, (src_w - px_x) - ((src_w - px_x) % 2))
    if px_y + px_h > src_h:
        px_h = max(2, (src_h - px_y) - ((src_h - px_y) % 2))

    return px_x, px_y, px_w, px_h

def build_gaming_split_filter(
    facecam_box: str,
    gameplay_box: str,
    src_w: int,
    src_h: int,
    scale_flags: str = "bicubic"
) -> str:
    """
    Generates FFmpeg filter_complex string for vertical stacking:
    Top: 1080x576 (30% facecam)
    Bottom: 1080x1344 (70% gameplay)
    Total: 1080x1920 (9:16)
    """
    cam_x, cam_y, cam_w, cam_h = to_pixel_box(facecam_box, src_w, src_h)
    game_x, game_y, game_w, game_h = to_pixel_box(gameplay_box, src_w, src_h)

    return (
        f"[0:v]split=2[raw_cam][raw_game];"
        f"[raw_cam]crop={cam_w}:{cam_h}:{cam_x}:{cam_y},scale=1080:576:flags={scale_flags}[cam_top];"
        f"[raw_game]crop={game_w}:{game_h}:{game_x}:{game_y},scale=1080:1344:flags={scale_flags}[game_bottom];"
        f"[cam_top][game_bottom]vstack=inputs=2[stacked_v]"
    )

def probe_video_dimensions(video_path: str) -> Tuple[int, int]:
    """Returns (width, height) of video file via ffprobe, falling back to (1920, 1080)."""
    if not os.path.exists(video_path):
        return 1920, 1080
    cmd = [
        "ffprobe", "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "stream=width,height",
        "-of", "csv=s=x:p=0",
        video_path
    ]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, check=True)
        out = res.stdout.strip().split("x")
        if len(out) == 2:
            return int(out[0]), int(out[1])
    except Exception:
        pass
    return 1920, 1080

def is_vertical_video(video_path: str) -> bool:
    """Returns True if the video exists and has width < height (portrait/vertical)."""
    if not video_path or not isinstance(video_path, str):
        return False
    try:
        w, h = probe_video_dimensions(video_path)
        return bool(w > 0 and h > 0 and w < h)
    except Exception:
        return False

def render_gaming_split_clip(
    input_path: str,
    output_path: str,
    facecam_box: str = DEFAULT_FACECAM_BOX,
    gameplay_box: str = DEFAULT_GAMEPLAY_BOX
) -> str:
    """
    Renders input video into 1080x1920 gaming split format via FFmpeg.
    """
    if not os.path.exists(input_path):
        raise FileNotFoundError(f"Input video not found: {input_path}")

    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    src_w, src_h = probe_video_dimensions(input_path)
    filter_complex = build_gaming_split_filter(facecam_box, gameplay_box, src_w, src_h)

    codec, preset, extra_args = get_best_encoder()

    def _build_cmd(c, p, extra, a_codec):
        return [
            "ffmpeg", "-y",
            "-i", input_path,
            "-filter_complex", filter_complex,
            "-map", "[stacked_v]",
            "-map", "0:a?",
            "-c:v", c,
            "-preset", p,
            *extra,
            "-pix_fmt", "yuv420p",
            "-c:a", a_codec,
            output_path
        ]

    cmd = _build_cmd(codec, preset, extra_args, "copy")
    try:
        subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
    except subprocess.CalledProcessError:
        global _CACHED_ENCODER
        if codec != "libx264":
            _CACHED_ENCODER = ("libx264", "ultrafast", ["-crf", "18"])
            codec, preset, extra_args = _CACHED_ENCODER
            try:
                cmd_cpu = _build_cmd(codec, preset, extra_args, "copy")
                subprocess.run(cmd_cpu, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
                return output_path
            except subprocess.CalledProcessError:
                pass
        cmd_aac = _build_cmd(codec, preset, extra_args, "aac")
        subprocess.run(cmd_aac, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
    return output_path

def build_manual_crop_filter(
    crop_box: str,
    src_w: int,
    src_h: int,
    target_w: int = 1080,
    target_h: int = 1920,
    scale_flags: str = "bicubic"
) -> str:
    """
    Generates FFmpeg filter string to crop and scale source video to 9:16 (1080x1920).
    """
    px_x, px_y, px_w, px_h = to_pixel_box(crop_box or DEFAULT_MANUAL_CROP_BOX, src_w, src_h)
    return f"crop={px_w}:{px_h}:{px_x}:{px_y},scale={target_w}:{target_h}:flags={scale_flags}"

def render_manual_crop_clip(
    input_path: str,
    output_path: str,
    crop_box: str = DEFAULT_MANUAL_CROP_BOX
) -> str:
    """
    Renders input video directly into 1080x1920 9:16 using a manual bounding box.
    """
    if not os.path.exists(input_path):
        raise FileNotFoundError(f"Input video not found: {input_path}")

    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    src_w, src_h = probe_video_dimensions(input_path)
    vf = build_manual_crop_filter(crop_box, src_w, src_h)

    codec, preset, extra_args = get_best_encoder()

    def _build_cmd(c, p, extra, a_codec):
        return [
            "ffmpeg", "-y",
            "-i", input_path,
            "-vf", vf,
            "-c:v", c,
            "-preset", p,
            *extra,
            "-pix_fmt", "yuv420p",
            "-c:a", a_codec,
            output_path
        ]

    cmd = _build_cmd(codec, preset, extra_args, "copy")
    try:
        subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
    except subprocess.CalledProcessError:
        global _CACHED_ENCODER
        if codec != "libx264":
            _CACHED_ENCODER = ("libx264", "ultrafast", ["-crf", "18"])
            codec, preset, extra_args = _CACHED_ENCODER
            try:
                cmd_cpu = _build_cmd(codec, preset, extra_args, "copy")
                subprocess.run(cmd_cpu, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
                return output_path
            except subprocess.CalledProcessError:
                pass
        cmd_aac = _build_cmd(codec, preset, extra_args, "aac")
        subprocess.run(cmd_aac, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)

    return output_path

