import os
import subprocess
import pytest
from scripts.smart_clipping import (
    snap_narrative_topic_segments,
    splice_topic_segments,
)

def create_synthetic_video(output_path: str, duration: int = 15):
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi",
        "-i", f"testsrc=duration={duration}:size=320x240:rate=30",
        "-f", "lavfi",
        "-i", f"sine=frequency=1000:duration={duration}",
        "-c:v", "libx264",
        "-c:a", "aac",
        output_path
    ]
    subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

def test_smart_clipping_end_to_end(tmp_path):
    video_path = str(tmp_path / "test_long_video.mp4")
    create_synthetic_video(video_path, duration=15)
    assert os.path.exists(video_path)

    topic = {
        "title": "Synthetic Test Topic",
        "rationale": "Verify splicing",
        "target_duration": 8.0,
        "segments": {
            "hook": {"start_time": 1.0, "end_time": 3.0, "text": "Hook text"},
            "core": {"start_time": 5.0, "end_time": 8.0, "text": "Core text"},
            "payoff": {"start_time": 11.0, "end_time": 13.0, "text": "Payoff text"}
        }
    }

    words = [
        {"word": "Hook", "start": 0.95, "end": 1.5, "score": 0.9},
        {"word": "text", "start": 2.5, "end": 2.95, "score": 0.9},
        {"word": "Core", "start": 4.95, "end": 5.5, "score": 0.9},
        {"word": "text", "start": 7.5, "end": 7.95, "score": 0.9},
        {"word": "Payoff", "start": 10.95, "end": 11.5, "score": 0.9},
        {"word": "text", "start": 12.5, "end": 12.95, "score": 0.9},
    ]

    snapped = snap_narrative_topic_segments(topic, words, margin=0.05)
    hook = snapped["segments"]["hook"]
    core = snapped["segments"]["core"]
    payoff = snapped["segments"]["payoff"]

    segments_to_splice = [
        (hook["snapped_start"], hook["snapped_end"]),
        (core["snapped_start"], core["snapped_end"]),
        (payoff["snapped_start"], payoff["snapped_end"]),
    ]

    output_clip = str(tmp_path / "final_smart_clip.mp4")
    result_path = splice_topic_segments(video_path, segments_to_splice, output_clip)

    assert os.path.exists(result_path)
    assert os.path.getsize(result_path) > 1000

    # Probe duration of spliced output
    probe_cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        result_path
    ]
    res = subprocess.run(probe_cmd, capture_output=True, text=True, check=True)
    dur = float(res.stdout.strip())
    # Spliced segments: ~2.1s + ~3.1s + ~2.1s = ~7.3s
    assert 6.0 <= dur <= 9.0
