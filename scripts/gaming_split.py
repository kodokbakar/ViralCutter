import os
import re
import subprocess
from typing import Tuple, Optional

DEFAULT_FACECAM_BOX = "0.68,0.05,0.28,0.1493"
DEFAULT_GAMEPLAY_BOX = "0.25,0.0,0.50,0.622"

def parse_normalized_box(box_str: str) -> Tuple[float, float, float, float]:
    """
    Parses 'x,y,w,h' string into clamped (x, y, w, h) floats in range [0.0, 1.0].
    Enforces minimum width/height of 0.05 to avoid zero-dimension FFmpeg crashes.
    """
    cleaned = str(box_str or "").strip()
    parts = [p.strip() for p in cleaned.split(",") if p.strip()]
    if len(parts) != 4:
        parts = [p.strip() for p in DEFAULT_FACECAM_BOX.split(",")]

    try:
        x, y, w, h = [float(p) for p in parts]
    except (ValueError, TypeError):
        x, y, w, h = 0.0, 0.0, 0.5, 0.5

    x = max(0.0, min(1.0, x))
    y = max(0.0, min(1.0, y))
    w = max(0.05, min(1.0, w))
    h = max(0.05, min(1.0, h))

    if x + w > 1.0:
        w = max(0.05, 1.0 - x)
    if y + h > 1.0:
        h = max(0.05, 1.0 - y)

    return round(x, 4), round(y, 4), round(w, 4), round(h, 4)

def to_pixel_box(normalized_box: str, src_w: int, src_h: int) -> Tuple[int, int, int, int]:
    """
    Converts normalized coordinates to even pixel integers (x, y, w, h).
    """
    x, y, w, h = parse_normalized_box(normalized_box)
    px_x = int(round(x * src_w))
    px_y = int(round(y * src_h))
    px_w = int(round(w * src_w))
    px_h = int(round(h * src_h))

    px_x = px_x - (px_x % 2)
    px_y = px_y - (px_y % 2)
    px_w = max(2, px_w - (px_w % 2))
    px_h = max(2, px_h - (px_h % 2))

    if px_x + px_w > src_w:
        px_w = max(2, (src_w - px_x) - ((src_w - px_x) % 2))
    if px_y + px_h > src_h:
        px_h = max(2, (src_h - px_y) - ((src_h - px_y) % 2))

    return px_x, px_y, px_w, px_h

def build_gaming_split_filter(
    facecam_box: str,
    gameplay_box: str,
    src_w: int,
    src_h: int
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
        f"[raw_cam]crop={cam_w}:{cam_h}:{cam_x}:{cam_y},scale=1080:576:flags=lanczos[cam_top];"
        f"[raw_game]crop={game_w}:{game_h}:{game_x}:{game_y},scale=1080:1344:flags=lanczos[game_bottom];"
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

    cmd = [
        "ffmpeg", "-y",
        "-i", input_path,
        "-filter_complex", filter_complex,
        "-map", "[stacked_v]",
        "-map", "0:a?",
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "18",
        "-c:a", "copy",
        output_path
    ]

    try:
        subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
    except subprocess.CalledProcessError:
        # Fallback with AAC re-encoding if audio stream copy fails
        cmd_aac = list(cmd)
        cmd_aac[cmd_aac.index("-c:a") + 1] = "aac"
        subprocess.run(cmd_aac, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)

    return output_path
