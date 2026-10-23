import subprocess
import pytest
from unittest.mock import patch, MagicMock
from scripts import gaming_split

def test_get_best_encoder_nvenc_success():
    with patch("scripts.gaming_split._CACHED_ENCODER", None), \
         patch("subprocess.run") as mock_run:
        mock_encoders = MagicMock(stdout=" V....D h264_nvenc NVIDIA NVENC H.264 encoder\n")
        mock_probe = MagicMock(returncode=0)
        mock_run.side_effect = [mock_encoders, mock_probe]

        codec, preset, extra_args = gaming_split.get_best_encoder()
        assert codec == "h264_nvenc"
        assert "-b:v" in extra_args

def test_get_best_encoder_fallback_on_probe_failure():
    with patch("scripts.gaming_split._CACHED_ENCODER", None), \
         patch("subprocess.run") as mock_run:
        mock_encoders = MagicMock(stdout=" V....D h264_nvenc NVIDIA NVENC H.264 encoder\n")
        mock_run.side_effect = [mock_encoders, subprocess.CalledProcessError(255, ["ffmpeg"])]

        codec, preset, extra_args = gaming_split.get_best_encoder()
        assert codec == "libx264"
        assert preset == "ultrafast"

def test_build_manual_crop_filter_defaults_to_bicubic():
    filt = gaming_split.build_manual_crop_filter(
        crop_box=gaming_split.DEFAULT_MANUAL_CROP_BOX,
        src_w=1920,
        src_h=1080
    )
    assert "flags=bicubic" in filt
    assert "flags=lanczos" not in filt

def test_render_manual_crop_clip_recovers_from_hardware_encoder_failure(tmp_path):
    in_video = tmp_path / "in.mp4"
    in_video.write_text("fake video")
    out_video = tmp_path / "out.mp4"

    commands_executed = []
    def fake_subprocess_run(cmd, *args, **kwargs):
        commands_executed.append(list(cmd))
        if "-c:v" in cmd:
            idx = cmd.index("-c:v")
            if cmd[idx + 1] == "h264_nvenc":
                raise subprocess.CalledProcessError(255, cmd, stderr="NVENC failed")
        return MagicMock(returncode=0)

    with patch("scripts.gaming_split._CACHED_ENCODER", ("h264_nvenc", "p1", ["-b:v", "5M"])), \
         patch("scripts.gaming_split.probe_video_dimensions", return_value=(1920, 1080)), \
         patch("subprocess.run", side_effect=fake_subprocess_run):

        res = gaming_split.render_manual_crop_clip(str(in_video), str(out_video))
        assert res == str(out_video)
        assert gaming_split._CACHED_ENCODER[0] == "libx264"
        # Confirm retry with libx264 occurred
        assert any("-c:v" in c and c[c.index("-c:v") + 1] == "libx264" for c in commands_executed)
