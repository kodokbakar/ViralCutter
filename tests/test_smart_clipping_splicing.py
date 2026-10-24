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

def test_build_ffmpeg_cut_command_hardware_encoder():
    """Verify build_ffmpeg_cut_command accepts hardware encoder options (h264_nvenc)."""
    cmd = build_ffmpeg_cut_command(
        "input.mp4", 10.5, 25.0, "sub_1.mp4",
        video_codec="h264_nvenc",
        preset="p1"
    )
    assert "-c:v" in cmd
    codec_idx = cmd.index("-c:v")
    assert cmd[codec_idx + 1] == "h264_nvenc"
    assert "-preset" in cmd
    preset_idx = cmd.index("-preset")
    assert cmd[preset_idx + 1] == "p1"
    assert "-b:v" in cmd

@patch("subprocess.run")
def test_splice_topic_segments_supports_video_codec(mock_run, tmp_path):
    """Verify splice_topic_segments passes video_codec down to subsegment cut commands."""
    video = str(tmp_path / "input.mp4")
    out = str(tmp_path / "output.mp4")
    segments = [(1.0, 5.0), (12.0, 20.0)]

    splice_topic_segments(video, segments, out, temp_dir=str(tmp_path), video_codec="h264_nvenc")
    cut_calls = mock_run.call_args_list[:-1]
    assert len(cut_calls) == 2
    for call in cut_calls:
        cmd = call[0][0]
        assert "-c:v" in cmd
        assert cmd[cmd.index("-c:v") + 1] == "h264_nvenc"


def test_build_ffmpeg_cut_command_custom_nvenc_preset():
    """Verify build_ffmpeg_cut_command uses custom preset with h264_nvenc."""
    cmd = build_ffmpeg_cut_command(
        "input.mp4", 5.0, 15.0, "sub.mp4",
        video_codec="h264_nvenc",
        preset="p4"
    )
    assert "-c:v" in cmd
    assert cmd[cmd.index("-c:v") + 1] == "h264_nvenc"
    assert "-preset" in cmd
    assert cmd[cmd.index("-preset") + 1] == "p4"
    assert "-b:v" in cmd
    assert cmd[cmd.index("-b:v") + 1] == "5M"


def test_build_ffmpeg_cut_command_fallback_codec_and_preset():
    """Verify build_ffmpeg_cut_command handles software fallback codec and preset."""
    cmd = build_ffmpeg_cut_command(
        "input.mp4", 0.0, 10.0, "out.mp4",
        video_codec="libx264",
        preset="veryfast"
    )
    assert "-c:v" in cmd
    assert cmd[cmd.index("-c:v") + 1] == "libx264"
    assert "-preset" in cmd
    assert cmd[cmd.index("-preset") + 1] == "veryfast"
    assert "-crf" in cmd
    assert cmd[cmd.index("-crf") + 1] == "18"


def test_build_ffmpeg_cut_command_default_fallback():
    """Verify build_ffmpeg_cut_command defaults to libx264 fast with crf 18 when unspecified."""
    cmd = build_ffmpeg_cut_command("input.mp4", 0.0, 10.0, "out.mp4")
    assert cmd[cmd.index("-c:v") + 1] == "libx264"
    assert cmd[cmd.index("-preset") + 1] == "fast"
    assert cmd[cmd.index("-crf") + 1] == "18"


@patch("subprocess.run")
def test_splice_topic_segments_forwards_custom_preset_and_codec(mock_run, tmp_path):
    """Verify splice_topic_segments passes custom preset and video_codec to subcuts."""
    video = str(tmp_path / "input.mp4")
    out = str(tmp_path / "output.mp4")
    segments = [(1.0, 5.0), (12.0, 20.0)]

    splice_topic_segments(
        video, segments, out,
        temp_dir=str(tmp_path),
        video_codec="h264_nvenc",
        preset="p5"
    )
    cut_calls = mock_run.call_args_list[:-1]
    assert len(cut_calls) == 2
    for call in cut_calls:
        cmd = call[0][0]
        assert "-c:v" in cmd
        assert cmd[cmd.index("-c:v") + 1] == "h264_nvenc"
        assert "-preset" in cmd
        assert cmd[cmd.index("-preset") + 1] == "p5"

    # Concat call should copy stream
    concat_call = mock_run.call_args_list[-1][0][0]
    assert "-c" in concat_call
    assert concat_call[concat_call.index("-c") + 1] == "copy"


@patch("subprocess.run")
def test_splice_topic_segments_single_segment_forwards_codec_and_preset(mock_run, tmp_path):
    """Verify single slice forwarding to build_ffmpeg_cut_command."""
    video = str(tmp_path / "input.mp4")
    out = str(tmp_path / "output.mp4")

    splice_topic_segments(
        video, [(2.0, 8.0)], out,
        temp_dir=str(tmp_path),
        video_codec="h264_nvenc",
        preset="p2"
    )
    assert mock_run.call_count == 1
    cmd = mock_run.call_args[0][0]
    assert cmd[cmd.index("-c:v") + 1] == "h264_nvenc"
    assert cmd[cmd.index("-preset") + 1] == "p2"


def test_cut_segments_hardware_encoder_nvenc_and_fallback(tmp_path):
    """Verify cut_segments.cut passes detected video_codec to splice_topic_segments."""
    from scripts import cut_segments
    project_folder = str(tmp_path)
    (tmp_path / "input.mp4").write_bytes(b"dummy")

    segments_data = {
        "segments": [
            {
                "title": "Clip",
                "score": 90,
                "start_time": 0.0,
                "duration": 10.0,
                "segments_to_splice": [(0.0, 5.0), (10.0, 15.0)],
            }
        ]
    }

    # Test NVENC supported
    with patch("scripts.cut_segments.check_nvenc_support", return_value=True), \
         patch("scripts.smart_clipping.splice_topic_segments") as mock_splice, \
         patch("scripts.cut_json.cut_json_transcript"):
        cut_segments.cut(segments_data, project_folder=project_folder, skip_video=False)
        assert mock_splice.call_count == 1
        assert mock_splice.call_args[1]["video_codec"] == "h264_nvenc"

    # Test NVENC fallback to libx264
    with patch("scripts.cut_segments.check_nvenc_support", return_value=False), \
         patch("scripts.smart_clipping.splice_topic_segments") as mock_splice, \
         patch("scripts.cut_json.cut_json_transcript"):
        cut_segments.cut(segments_data, project_folder=project_folder, skip_video=False)
        assert mock_splice.call_count == 1
        assert mock_splice.call_args[1]["video_codec"] == "libx264"


def test_check_nvenc_support():
    """Verify check_nvenc_support returns True on nvenc support and False otherwise."""
    import subprocess
    from scripts.cut_segments import check_nvenc_support

    class MockCompletedProcess:
        def __init__(self, stdout):
            self.stdout = stdout

    with patch("subprocess.run", return_value=MockCompletedProcess(" V..... h264_nvenc NVIDIA NVENC H.264 encoder")):
        assert check_nvenc_support() is True

    with patch("subprocess.run", return_value=MockCompletedProcess(" V..... libx264 libx264 H.264 / AVC")):
        assert check_nvenc_support() is False

    with patch("subprocess.run", side_effect=FileNotFoundError):
        assert check_nvenc_support() is False
