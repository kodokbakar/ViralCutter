import os
import pytest
from unittest.mock import patch
from scripts.smart_clipping import (
    build_ffmpeg_cut_command,
    splice_topic_segments,
    extract_audio_for_transcription,
)

def test_build_ffmpeg_cut_command():
    cmd = build_ffmpeg_cut_command("input.mp4", 10.5, 25.0, "sub_1.mp4")
    assert cmd[0] == "ffmpeg"
    assert "-ss" in cmd
    assert "10.500" in cmd
    assert "-to" in cmd
    assert "25.000" in cmd
    assert "sub_1.mp4" in cmd

@patch("subprocess.run")
def test_splice_topic_segments_multi(mock_run, tmp_path):
    video = str(tmp_path / "input.mp4")
    out = str(tmp_path / "output.mp4")
    segments = [(1.0, 5.0), (12.0, 20.0), (30.0, 40.0)]

    splice_topic_segments(video, segments, out, temp_dir=str(tmp_path))
    # mock_run should be called 3 times for cuts, 1 time for concat = 4 times
    assert mock_run.call_count == 4

@patch("subprocess.run")
def test_splice_topic_segments_single(mock_run, tmp_path):
    video = str(tmp_path / "input.mp4")
    out = str(tmp_path / "output.mp4")
    segments = [(1.0, 5.0)]

    splice_topic_segments(video, segments, out, temp_dir=str(tmp_path))
    assert mock_run.call_count == 1

@patch("subprocess.run")
def test_extract_audio_for_transcription(mock_run, tmp_path):
    video = str(tmp_path / "input.mp4")
    out_wav = str(tmp_path / "audio.wav")

    extract_audio_for_transcription(video, out_wav)
    assert mock_run.call_count == 1
    call_args = mock_run.call_args[0][0]
    assert call_args[0] == "ffmpeg"
    assert "-ar" in call_args
    assert "16000" in call_args
