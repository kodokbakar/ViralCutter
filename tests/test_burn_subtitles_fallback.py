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

def test_nvenc_success_cached(tmp_path):
    video_path = str(tmp_path / "in.mp4")
    (tmp_path / "in.mp4").write_bytes(b"fake video")
    sub_path = str(tmp_path / "in.ass")
    (tmp_path / "in.ass").write_text("[Script Info]\n")
    out_1 = str(tmp_path / "out1.mp4")
    out_2 = str(tmp_path / "out2.mp4")

    burn_subtitles._NVENC_AVAILABLE = None

    calls = []
    def fake_subprocess_run(cmd, *args, **kwargs):
        encoder = cmd[cmd.index("-c:v") + 1]
        calls.append(encoder)
        return subprocess.CompletedProcess(cmd, 0)

    with patch("subprocess.run", side_effect=fake_subprocess_run), \
         patch("scripts.burn_subtitles._validate_render", return_value=True):

        ok1, msg1, val1 = burn_subtitles.burn_video_file(video_path, sub_path, out_1)
        assert ok1 is True
        assert burn_subtitles._NVENC_AVAILABLE is True
        assert calls.count("h264_nvenc") == 1

        ok2, msg2, val2 = burn_subtitles.burn_video_file(video_path, sub_path, out_2)
        assert ok2 is True
        assert calls.count("h264_nvenc") == 2
        assert calls.count("libx264") == 0

def test_filter_complex_failure_watermark_fallback(tmp_path):
    video_path = str(tmp_path / "in.mp4")
    (tmp_path / "in.mp4").write_bytes(b"fake video")
    sub_path = str(tmp_path / "in.ass")
    (tmp_path / "in.ass").write_text("[Script Info]\n")
    watermark_path = str(tmp_path / "wm.png")
    (tmp_path / "wm.png").write_bytes(b"dummy png")
    out_path = str(tmp_path / "out.mp4")

    burn_subtitles._NVENC_AVAILABLE = False

    commands_executed = []
    def fake_subprocess_run(cmd, *args, **kwargs):
        commands_executed.append(list(cmd))
        if "-filter_complex" in cmd:
            raise subprocess.CalledProcessError(1, cmd, stderr="Watermark overlay error")
        return subprocess.CompletedProcess(cmd, 0)

    with patch("subprocess.run", side_effect=fake_subprocess_run), \
         patch("scripts.burn_subtitles._validate_render", return_value=True):

        ok, msg, val = burn_subtitles.burn_video_file(
            video_path=video_path,
            subtitle_path=sub_path,
            output_path=out_path,
            watermark_asset=watermark_path,
            watermark_config={"mode": "image"}
        )

        assert ok is True
        assert msg == "CPU Fallback Success (Simple Subs)"
        vf_commands = [c for c in commands_executed if "-vf" in c]
        assert len(vf_commands) == 1

def test_filter_complex_and_cpu_fallback_both_fail(tmp_path):
    video_path = str(tmp_path / "in.mp4")
    (tmp_path / "in.mp4").write_bytes(b"fake video")
    sub_path = str(tmp_path / "in.ass")
    (tmp_path / "in.ass").write_text("[Script Info]\n")
    broll_webm = str(tmp_path / "broll.webm")
    (tmp_path / "broll.webm").write_bytes(b"dummy webm")
    out_path = str(tmp_path / "out.mp4")

    burn_subtitles._NVENC_AVAILABLE = False

    def fake_subprocess_run(cmd, *args, **kwargs):
        raise subprocess.CalledProcessError(1, cmd, stderr="Fatal render error")

    with patch("subprocess.run", side_effect=fake_subprocess_run):
        ok, msg, val = burn_subtitles.burn_video_file(
            video_path=video_path,
            subtitle_path=sub_path,
            output_path=out_path,
            broll_items=[{"video_path": broll_webm}]
        )

        assert ok is False
        assert "Fatal render error" in msg
        assert val is None

def test_complex_filter_non_nvenc_error_preserves_nvenc_availability(tmp_path):
    video_path = str(tmp_path / "in.mp4")
    (tmp_path / "in.mp4").write_bytes(b"fake video")
    sub_path = str(tmp_path / "in.ass")
    (tmp_path / "in.ass").write_text("[Script Info]\n")
    broll_webm = str(tmp_path / "broll.webm")
    (tmp_path / "broll.webm").write_bytes(b"dummy webm")
    out_1 = str(tmp_path / "out1.mp4")
    out_2 = str(tmp_path / "out2.mp4")

    burn_subtitles._NVENC_AVAILABLE = None

    calls = []
    def fake_subprocess_run(cmd, *args, **kwargs):
        idx = len(cmd) - 1 - cmd[::-1].index("-c:v")
        encoder = cmd[idx + 1]
        calls.append(encoder)
        # Fail only when complex filter is involved (e.g. corrupt b-roll overlay)
        if "-filter_complex" in cmd:
            raise subprocess.CalledProcessError(1, cmd, stderr="Error configuring filtergraph: corrupt b-roll")
        return subprocess.CompletedProcess(cmd, 0)

    with patch("subprocess.run", side_effect=fake_subprocess_run), \
         patch("scripts.burn_subtitles._validate_render", return_value=True):

        # Clip 1 with b-roll fails on complex filter under NVENC & CPU, succeeds on simple CPU subs
        ok1, msg1, val1 = burn_subtitles.burn_video_file(
            video_path=video_path,
            subtitle_path=sub_path,
            output_path=out_1,
            broll_items=[{"video_path": broll_webm}]
        )
        assert ok1 is True
        # NVENC availability should NOT be marked False because error was not NVENC/CUDA related
        assert burn_subtitles._NVENC_AVAILABLE is not False

        # Clip 2 without b-roll should still attempt NVENC
        ok2, msg2, val2 = burn_subtitles.burn_video_file(
            video_path=video_path,
            subtitle_path=sub_path,
            output_path=out_2
        )
        assert ok2 is True
        assert burn_subtitles._NVENC_AVAILABLE is True
        # Both clips attempted NVENC
        assert calls.count("h264_nvenc") == 2

def test_complex_filter_nvenc_error_disables_nvenc_availability(tmp_path):
    video_path = str(tmp_path / "in.mp4")
    (tmp_path / "in.mp4").write_bytes(b"fake video")
    sub_path = str(tmp_path / "in.ass")
    (tmp_path / "in.ass").write_text("[Script Info]\n")
    broll_webm = str(tmp_path / "broll.webm")
    (tmp_path / "broll.webm").write_bytes(b"dummy webm")
    out_1 = str(tmp_path / "out1.mp4")

    burn_subtitles._NVENC_AVAILABLE = None

    def fake_subprocess_run(cmd, *args, **kwargs):
        idx = len(cmd) - 1 - cmd[::-1].index("-c:v")
        encoder = cmd[idx + 1]
        if encoder == "h264_nvenc":
            raise subprocess.CalledProcessError(1, cmd, stderr="NVENC encoder error: device out of memory")
        return subprocess.CompletedProcess(cmd, 0)

    with patch("subprocess.run", side_effect=fake_subprocess_run), \
         patch("scripts.burn_subtitles._validate_render", return_value=True):

        ok1, msg1, val1 = burn_subtitles.burn_video_file(
            video_path=video_path,
            subtitle_path=sub_path,
            output_path=out_1,
            broll_items=[{"video_path": broll_webm}]
        )
        assert ok1 is True
        assert burn_subtitles._NVENC_AVAILABLE is False
