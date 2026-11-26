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

def get_max_render_workers(default_cap: int = 3) -> int:
    """
    Computes maximum worker threads for layout rendering and subtitle burning.
    Uses VIRALCUTTER_MAX_RENDER_WORKERS environment variable if set (clamped to >= 1).
    Otherwise computes min(default_cap, max(1, (os.cpu_count() or 2) // 2)).
    """
    env_workers = os.getenv("VIRALCUTTER_MAX_RENDER_WORKERS")
    if env_workers is not None:
        try:
            return max(1, int(str(env_workers).strip()))
        except (ValueError, TypeError):
            pass
    cpu_workers = max(1, (os.cpu_count() or 2) // 2)
    return max(1, min(default_cap, cpu_workers))

from scripts.gaming_facecam_detector import FACECAM_QUADRANTS, DEFAULT_FACECAM_BOX
DEFAULT_GAMEPLAY_BOX = "0.25,0.0,0.50,0.622"
DEFAULT_MANUAL_CROP_BOX = "0.3418,0.0,0.3164,1.0"
DEFAULT_KILLFEED_BOX = "0.70,0.05,0.25,0.12"
VALID_GAMING_LAYOUTS = ("split_30_70", "split_40_60", "floating_pip", "blurred_bg")

class RenderResult(str):
    subtitles_burned: bool

    def __new__(cls, value: str, subtitles_burned: bool = False):
        obj = super().__new__(cls, value)
        obj.subtitles_burned = subtitles_burned
        return obj

def escape_filter_path(path: str) -> str:
    """Escapes file path for FFmpeg filter arguments (subtitles filter)."""
    p = os.path.abspath(str(path)).replace("\\", "/")
    for ch in (':', "'", '[', ']'):
        p = p.replace(ch, f"\\{ch}")
    return p

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
    scale_flags: str = "bicubic",
    layout: str = "split_30_70",
    killfeed_box: Optional[str] = None,
    subtitle_ass_path: Optional[str] = None,
) -> str:
    """
    Generates FFmpeg filter_complex string for gaming layouts:
    - split_30_70: 1080x576 facecam top (30%), 1080x1344 gameplay bottom (70%)
    - split_40_60: 1080x768 facecam top (40%), 1080x1152 gameplay bottom (60%)
    - floating_pip: 1080x1920 gameplay background with floating facecam PiP overlay
    - blurred_bg: blurred gameplay background with facecam top and gameplay center
    Optional killfeed_box overlay positioned at top-right (x=W-w-20:y=20) with white border.
    Total: 1080x1920 (9:16), terminating strictly on pad [stacked_v] (or [v_out] if subtitles).
    """
    # Backward compatibility: swap if layout passed positionally into scale_flags
    if scale_flags in VALID_GAMING_LAYOUTS and layout == "split_30_70":
        layout = scale_flags
        scale_flags = "bicubic"
    if layout not in VALID_GAMING_LAYOUTS:
        layout = "split_30_70"

    cam_x, cam_y, cam_w, cam_h = to_pixel_box(facecam_box, src_w, src_h)
    game_x, game_y, game_w, game_h = to_pixel_box(gameplay_box, src_w, src_h)

    has_kf = bool(killfeed_box and str(killfeed_box).strip() and str(killfeed_box).strip().lower() != "none")
    base_pad = "[base_v]" if has_kf else "[stacked_v]"

    if layout == "split_40_60":
        split_n = 3 if has_kf else 2
        splits = f"[0:v]split={split_n}[raw_cam][raw_game]" + ("[raw_kf];" if has_kf else ";")
        filt = (
            f"{splits}"
            f"[raw_cam]crop={cam_w}:{cam_h}:{cam_x}:{cam_y},scale=1080:768:flags={scale_flags}[cam_top];"
            f"[raw_game]crop={game_w}:{game_h}:{game_x}:{game_y},scale=1080:1152:flags={scale_flags}[game_bottom];"
            f"[cam_top][game_bottom]vstack=inputs=2{base_pad}"
        )
    elif layout == "floating_pip":
        split_n = 3 if has_kf else 2
        splits = f"[0:v]split={split_n}[raw_cam][raw_game]" + ("[raw_kf];" if has_kf else ";")
        filt = (
            f"{splits}"
            f"[raw_game]crop={game_w}:{game_h}:{game_x}:{game_y},scale=1080:1920:flags={scale_flags}[game_bg];"
            f"[raw_cam]crop={cam_w}:{cam_h}:{cam_x}:{cam_y},scale=360:270:flags={scale_flags}[cam_pip];"
            f"[game_bg][cam_pip]overlay=x=40:y=60{base_pad}"
        )
    elif layout == "blurred_bg":
        split_n = 4 if has_kf else 3
        splits = f"[0:v]split={split_n}[raw_bg][raw_cam][raw_game]" + ("[raw_kf];" if has_kf else ";")
        filt = (
            f"{splits}"
            f"[raw_bg]crop={game_w}:{game_h}:{game_x}:{game_y},scale=1080:1920:flags={scale_flags},boxblur=20:5[bg_blur];"
            f"[raw_cam]crop={cam_w}:{cam_h}:{cam_x}:{cam_y},scale=1080:576:flags={scale_flags}[cam_top];"
            f"[raw_game]crop={game_w}:{game_h}:{game_x}:{game_y},scale=1080:608:flags={scale_flags}[game_mid];"
            f"[bg_blur][cam_top]overlay=x=0:y=0[bg_cam];"
            f"[bg_cam][game_mid]overlay=x=0:y=620{base_pad}"
        )
    else:  # split_30_70 (default)
        split_n = 3 if has_kf else 2
        splits = f"[0:v]split={split_n}[raw_cam][raw_game]" + ("[raw_kf];" if has_kf else ";")
        filt = (
            f"{splits}"
            f"[raw_cam]crop={cam_w}:{cam_h}:{cam_x}:{cam_y},scale=1080:576:flags={scale_flags}[cam_top];"
            f"[raw_game]crop={game_w}:{game_h}:{game_x}:{game_y},scale=1080:1344:flags={scale_flags}[game_bottom];"
            f"[cam_top][game_bottom]vstack=inputs=2{base_pad}"
        )

    if has_kf:
        kf_x, kf_y, kf_w, kf_h = to_pixel_box(str(killfeed_box), src_w, src_h)
        filt += (
            f";[raw_kf]crop={kf_w}:{kf_h}:{kf_x}:{kf_y},drawbox=t=2:c=white@0.6[kf_boxed];"
            f"[base_v][kf_boxed]overlay=x=W-w-20:y=20[stacked_v]"
        )

    if subtitle_ass_path:
        escaped_ass = escape_filter_path(subtitle_ass_path)
        from scripts import subtitle_fonts
        escaped_fonts = escape_filter_path(subtitle_fonts.get_fonts_dir())
        filt += f";[stacked_v]subtitles=filename='{escaped_ass}':fontsdir='{escaped_fonts}'[v_out]"

    return filt

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
    gameplay_box: str = DEFAULT_GAMEPLAY_BOX,
    layout: str = "split_30_70",
    killfeed_box: Optional[str] = None,
    subtitle_ass_path: Optional[str] = None,
) -> RenderResult:
    """
    Renders input video into 1080x1920 gaming format via FFmpeg.
    Supports single-pass subtitle burning if subtitle_ass_path is provided.
    Falls back gracefully to rendering without subtitles if single-pass fails.
    """
    if not os.path.exists(input_path):
        raise FileNotFoundError(f"Input video not found: {input_path}")

    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    src_w, src_h = probe_video_dimensions(input_path)

    codec, preset, extra_args = get_best_encoder()

    def _execute_ffmpeg(filter_str: str, map_pad: str):
        nonlocal codec, preset, extra_args
        def _build_cmd(c, p, extra, a_codec):
            return [
                "ffmpeg", "-y",
                "-i", input_path,
                "-filter_complex", filter_str,
                "-map", map_pad,
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
                    return
                except subprocess.CalledProcessError:
                    pass
            cmd_aac = _build_cmd(codec, preset, extra_args, "aac")
            subprocess.run(cmd_aac, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)

    if subtitle_ass_path and os.path.exists(subtitle_ass_path):
        try:
            filt_sub = build_gaming_split_filter(
                facecam_box=facecam_box,
                gameplay_box=gameplay_box,
                src_w=src_w,
                src_h=src_h,
                layout=layout,
                killfeed_box=killfeed_box,
                subtitle_ass_path=subtitle_ass_path,
            )
            _execute_ffmpeg(filt_sub, "[v_out]")
            return RenderResult(output_path, subtitles_burned=True)
        except Exception:
            pass

    filt_no_sub = build_gaming_split_filter(
        facecam_box=facecam_box,
        gameplay_box=gameplay_box,
        src_w=src_w,
        src_h=src_h,
        layout=layout,
        killfeed_box=killfeed_box,
        subtitle_ass_path=None,
    )
    _execute_ffmpeg(filt_no_sub, "[stacked_v]")
    return RenderResult(output_path, subtitles_burned=False)

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


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Render gaming split video clip")
    parser.add_argument("-i", "--input", required=True, help="Input video file path")
    parser.add_argument("-o", "--output", required=True, help="Output video file path")
    parser.add_argument("--facecam", default=DEFAULT_FACECAM_BOX, help="Facecam crop box (x,y,w,h)")
    parser.add_argument("--gameplay", default=DEFAULT_GAMEPLAY_BOX, help="Gameplay crop box (x,y,w,h)")
    parser.add_argument("--layout", default="split_30_70", choices=VALID_GAMING_LAYOUTS, help="Gaming layout preset")
    parser.add_argument("--killfeed", default=None, help="Killfeed crop box (x,y,w,h)")
    args = parser.parse_args()

    render_gaming_split_clip(
        input_path=args.input,
        output_path=args.output,
        facecam_box=args.facecam,
        gameplay_box=args.gameplay,
        layout=args.layout,
        killfeed_box=args.killfeed
    )


