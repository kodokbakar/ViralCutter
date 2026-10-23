import subprocess
import pytest
from unittest.mock import patch, MagicMock
from scripts import burn_subtitles

def test_nvenc_failure_cached_avoids_repeated_nvenc_calls(tmp_path):
    video_path = str(tmp_path / "in.mp4")
    (tmp_path / "in.mp4").write_bytes(b"fake video")
    sub_path = str(tmp_path / "in.ass")
    (tmp_path / "in.ass").write_text("[Script Info]\n")
    out_1 = str(tmp_path / "out1.mp4")
    out_2 = str(tmp_path / "out2.mp4")

    # Reset cache
    burn_subtitles._NVENC_AVAILABLE = None

    calls = []
    def fake_subprocess_run(cmd, *args, **kwargs):
        encoder = cmd[cmd.index("-c:v") + 1]
        calls.append(encoder)
        if encoder == "h264_nvenc":
            raise subprocess.CalledProcessError(255, cmd, stderr="Cannot load libcuda.so.1")
        (tmp_path / "temp_done").touch()
        return subprocess.CompletedProcess(cmd, 0)

    with patch("subprocess.run", side_effect=fake_subprocess_run), \
         patch("scripts.burn_subtitles._validate_render", return_value=True):

        # First clip: tries NVENC -> fails -> falls back to libx264
        ok1, msg1, val1 = burn_subtitles.burn_video_file(video_path, sub_path, out_1)
        assert ok1 is True
        assert burn_subtitles._NVENC_AVAILABLE is False
        assert calls.count("h264_nvenc") == 1
        assert calls.count("libx264") == 1

        # Second clip: NVENC should be SKIPPED directly
        ok2, msg2, val2 = burn_subtitles.burn_video_file(video_path, sub_path, out_2)
        assert ok2 is True
        # NVENC call count remains 1 (never re-tested)
        assert calls.count("h264_nvenc") == 1
        assert calls.count("libx264") == 2

def test_filter_complex_failure_falls_back_to_simple_subtitle_burn(tmp_path):
    video_path = str(tmp_path / "in.mp4")
    (tmp_path / "in.mp4").write_bytes(b"fake video")
    sub_path = str(tmp_path / "in.ass")
    (tmp_path / "in.ass").write_text("[Script Info]\n")
    out_path = str(tmp_path / "out.mp4")

    burn_subtitles._NVENC_AVAILABLE = False
    broll_webm = str(tmp_path / "broll.webm")
    (tmp_path / "broll.webm").write_bytes(b"dummy webm")

    commands_executed = []
    def fake_subprocess_run(cmd, *args, **kwargs):
        commands_executed.append(list(cmd))
        if "-filter_complex" in cmd:
            raise subprocess.CalledProcessError(1, cmd, stderr="Filter complex overlay error")
        return subprocess.CompletedProcess(cmd, 0)

    with patch("subprocess.run", side_effect=fake_subprocess_run), \
         patch("scripts.burn_subtitles._validate_render", return_value=True):

        ok, msg, val = burn_subtitles.burn_video_file(
            video_path=video_path,
            subtitle_path=sub_path,
            output_path=out_path,
            broll_items=[{"video_path": broll_webm}]
        )

        assert ok is True
        # Check that a retry occurred with simple -vf subtitle filter
        vf_commands = [c for c in commands_executed if "-vf" in c]
        assert len(vf_commands) >= 1
