import os
import subprocess
import pytest
from scripts.gaming_split import render_gaming_split_clip, probe_video_dimensions

def create_synthetic_16x9_video(path: str, duration: int = 3):
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi",
        "-i", f"testsrc=duration={duration}:size=1280x720:rate=30",
        "-f", "lavfi",
        "-i", f"sine=frequency=1000:duration={duration}",
        "-c:v", "libx264",
        "-preset", "ultrafast",
        "-c:a", "aac",
        path
    ]
    subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

def test_gaming_split_pipeline_e2e(tmp_path):
    input_video = str(tmp_path / "stream_16x9.mp4")
    output_video = str(tmp_path / "clip_9x16_split.mp4")
    create_synthetic_16x9_video(input_video, duration=3)
    assert os.path.exists(input_video)

    out_res = render_gaming_split_clip(
        input_path=input_video,
        output_path=output_video,
        facecam_box="0.7,0.05,0.25,0.15",
        gameplay_box="0.2,0.0,0.6,0.7"
    )

    assert out_res == output_video
    assert os.path.exists(output_video)
    assert os.path.getsize(output_video) > 1000

    # Probe dimensions with ffprobe
    w, h = probe_video_dimensions(output_video)
    assert w == 1080
    assert h == 1920

    # Probe audio stream existence and duration
    probe_cmd = [
        "ffprobe", "-v", "error",
        "-select_streams", "a:0",
        "-show_entries", "stream=codec_name",
        "-of", "csv=p=0",
        output_video
    ]
    audio_check = subprocess.run(probe_cmd, capture_output=True, text=True, check=True)
    assert audio_check.stdout.strip() != ""
