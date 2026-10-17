import base64
import os
import subprocess
from typing import Optional

FALLBACK_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="540" height="960" viewBox="0 0 540 960">
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="#18181b"/>
      <stop offset="100%" stop-color="#09090b"/>
    </linearGradient>
  </defs>
  <rect width="540" height="960" fill="url(#bg)"/>
  <rect x="20" y="20" width="500" height="920" fill="none" stroke="#27272a" stroke-width="2" stroke-dasharray="6,6"/>
</svg>"""

def get_fallback_preview_frame() -> str:
    """Returns a dark 9:16 background SVG as base64 data URI."""
    encoded = base64.b64encode(FALLBACK_SVG.encode("utf-8")).decode("ascii")
    return f"data:image/svg+xml;base64,{encoded}"

def get_frame_as_data_uri(image_path: str) -> str:
    """Encodes an image file as a base64 data URI for direct inline CSS rendering."""
    if not image_path or not os.path.exists(image_path):
        return get_fallback_preview_frame()

    ext = os.path.splitext(image_path)[1].lower().lstrip(".")
    mime = "image/jpeg" if ext in ["jpg", "jpeg"] else f"image/{ext}"
    try:
        with open(image_path, "rb") as f:
            data = base64.b64encode(f.read()).decode("ascii")
        return f"data:{mime};base64,{data}"
    except Exception:
        return get_fallback_preview_frame()

def extract_preview_frame(
    video_path: str,
    output_path: str,
    timestamp: float = 3.0,
    width: int = 540,
    height: int = 960,
    pad: bool = True
) -> Optional[str]:
    """
    Extracts a single representative frame from video scaled and padded to 9:16 aspect ratio.
    """
    if not video_path or not os.path.exists(video_path):
        return None

    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

    if pad:
        filter_str = f"scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:black"
    else:
        filter_str = f"scale={width}:{height}:force_original_aspect_ratio=decrease"
    cmd = [
        "ffmpeg", "-y",
        "-ss", f"{float(timestamp):.3f}",
        "-i", video_path,
        "-vframes", "1",
        "-vf", filter_str,
        "-q:v", "3",
        output_path
    ]
    try:
        subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        if os.path.exists(output_path) and os.path.getsize(output_path) > 100:
            return output_path
    except Exception:
        # Fallback to extracting frame at timestamp 0.5s if 3.0s is beyond duration
        try:
            cmd_fallback = [
                "ffmpeg", "-y",
                "-ss", "0.5",
                "-i", video_path,
                "-vframes", "1",
                "-vf", filter_str,
                "-q:v", "3",
                output_path
            ]
            subprocess.run(cmd_fallback, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
            if os.path.exists(output_path) and os.path.getsize(output_path) > 100:
                return output_path
        except Exception:
            pass

    return None

def extract_preview_snippet(
    video_path: str,
    output_path: str,
    timestamp: float = 3.0,
    duration: float = 3.0,
    width: int = 540,
    height: int = 960
) -> Optional[str]:
    """
    Extracts a short 3-second low-res 9:16 video clip for rapid animated subtitle burning preview.
    """
    if not video_path or not os.path.exists(video_path):
        return None

    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

    filter_str = f"scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:black"
    cmd = [
        "ffmpeg", "-y",
        "-ss", f"{float(timestamp):.3f}",
        "-t", f"{float(duration):.3f}",
        "-i", video_path,
        "-vf", filter_str,
        "-c:v", "libx264",
        "-preset", "ultrafast",
        "-crf", "26",
        "-c:a", "aac",
        "-b:a", "96k",
        output_path
    ]
    try:
        subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        if os.path.exists(output_path) and os.path.getsize(output_path) > 500:
            return output_path
    except Exception:
        # Fallback start at 0.0s
        try:
            cmd[3] = "0.0"
            subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
            if os.path.exists(output_path) and os.path.getsize(output_path) > 500:
                return output_path
        except Exception:
            pass

    return None

def get_video_duration(video_path: str) -> float:
    """Probes video duration via ffprobe, returning seconds (default 30.0)."""
    if not video_path or not os.path.exists(video_path):
        return 30.0
    cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        video_path
    ]
    try:
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
        val = float(res.stdout.strip())
        return max(1.0, val)
    except Exception:
        return 30.0


def extract_source_sample_frames(
    video_path: str,
    output_dir: str,
    count: int = 3,
    width: int = 1280,
    height: int = 720
) -> list[dict]:
    """
    Extracts N clean 16:9 unpadded representative sample frames from source video at distributed timestamps.
    Returns metadata list containing timestamps, time labels, paths, and data URIs.
    """
    if not video_path or not os.path.exists(video_path):
        return []

    os.makedirs(output_dir, exist_ok=True)
    duration = get_video_duration(video_path)
    base_stem = os.path.splitext(os.path.basename(video_path))[0]
    safe_stem = "".join(c for c in base_stem if c.isalnum() or c in "_-")[:30] or "source"

    # Calculate distributed timestamps across video duration
    timestamps = []
    if duration >= 15.0:
        # e.g. 15%, 50%, 85%
        ratios = [0.15, 0.50, 0.85]
        if count != 3:
            step = 0.8 / max(1, count - 1)
            ratios = [0.10 + i * step for i in range(count)]
        timestamps = [round(duration * r, 2) for r in ratios[:count]]
    else:
        step = duration / (count + 1)
        timestamps = [round(max(0.2, (i + 1) * step), 2) for i in range(count)]

    results = []
    for idx, ts in enumerate(timestamps):
        out_name = f"sample_{safe_stem}_{idx+1}_{int(ts * 1000)}.jpg"
        out_file = os.path.join(output_dir, out_name)
        extracted = extract_preview_frame(
            video_path=video_path,
            output_path=out_file,
            timestamp=ts,
            width=width,
            height=height,
            pad=False,
        )
        if extracted and os.path.exists(extracted):
            mins = int(ts // 60)
            secs = int(ts % 60)
            time_label = f"{mins:02d}:{secs:02d}"
            results.append({
                "index": idx,
                "timestamp": ts,
                "time_label": time_label,
                "path": str(out_file),
                "filename": out_name,
                "data_uri": get_frame_as_data_uri(out_file),
            })

    return results
