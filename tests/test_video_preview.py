import os
import subprocess
import pytest
from webui.video_preview import (
    extract_preview_frame,
    extract_preview_snippet,
    get_frame_as_data_uri,
    get_fallback_preview_frame,
    extract_source_sample_frames,
    get_video_duration,
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

def test_extract_source_sample_frames(tmp_path):
    video_path = str(tmp_path / "gameplay.mp4")
    create_dummy_video(video_path, duration=20)

    out_dir = str(tmp_path / "samples")
    samples = extract_source_sample_frames(video_path, out_dir, count=3, width=640, height=360)
    assert len(samples) == 3
    for idx, item in enumerate(samples):
        assert item["index"] == idx
        assert item["timestamp"] > 0
        assert ":" in item["time_label"]
        assert os.path.exists(item["path"])
        assert item["data_uri"].startswith("data:image/jpeg;base64,")

def test_get_video_duration(tmp_path):
    video_path = str(tmp_path / "dummy.mp4")
    create_dummy_video(video_path, duration=8)
    dur = get_video_duration(video_path)
    assert 7.0 <= dur <= 9.0
