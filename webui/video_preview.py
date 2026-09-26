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
    height: int = 960
) -> Optional[str]:
    """
    Extracts a single representative frame from video scaled and padded to 9:16 aspect ratio.
    """
    if not video_path or not os.path.exists(video_path):
        return None

    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

    filter_str = f"scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:black"
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
