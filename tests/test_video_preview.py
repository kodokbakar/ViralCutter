import os
import subprocess
import pytest
from webui.video_preview import (
    extract_preview_frame,
    extract_preview_snippet,
    get_frame_as_data_uri,
    get_fallback_preview_frame,
)

def create_dummy_video(path: str, duration: int = 6):
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi",
        "-i", f"testsrc=duration={duration}:size=320x240:rate=25",
        "-f", "lavfi",
        "-i", f"sine=frequency=1000:duration={duration}",
        "-c:v", "libx264",
        "-preset", "ultrafast",
        "-c:a", "aac",
        path
    ]
    subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

def test_extract_preview_frame(tmp_path):
    video_path = str(tmp_path / "dummy.mp4")
    create_dummy_video(video_path, duration=5)

    out_jpg = str(tmp_path / "frame.jpg")
    res = extract_preview_frame(video_path, out_jpg, timestamp=1.5, width=270, height=480)
    assert res == out_jpg
    assert os.path.exists(out_jpg)
    assert os.path.getsize(out_jpg) > 500

    data_uri = get_frame_as_data_uri(out_jpg)
    assert data_uri.startswith("data:image/jpeg;base64,")

def test_extract_preview_snippet(tmp_path):
    video_path = str(tmp_path / "dummy.mp4")
    create_dummy_video(video_path, duration=5)

    out_snippet = str(tmp_path / "snippet.mp4")
    res = extract_preview_snippet(video_path, out_snippet, timestamp=1.0, duration=2.0, width=270, height=480)
    assert res == out_snippet
    assert os.path.exists(out_snippet)
    assert os.path.getsize(out_snippet) > 1000

def test_fallback_preview_frame():
    fallback_uri = get_fallback_preview_frame()
    assert fallback_uri.startswith("data:image/")
