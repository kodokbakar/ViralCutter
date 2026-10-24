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


def test_get_best_encoder_nvenc_fails_checks_amf_and_qsv():
    with patch("scripts.gaming_split._CACHED_ENCODER", None), \
         patch("subprocess.run") as mock_run:
        mock_encoders = MagicMock(stdout=" V....D h264_nvenc NVIDIA NVENC H.264 encoder\n V....D h264_amf AMD AMF H.264 encoder\n")
        mock_nvenc_fail = subprocess.CalledProcessError(255, ["ffmpeg"])
        mock_run.side_effect = [mock_encoders, mock_nvenc_fail]

        codec, preset, extra_args = gaming_split.get_best_encoder()
        assert codec == "h264_amf"
        assert preset == "speed"

def test_get_best_encoder_nvenc_fails_checks_qsv_when_no_amf():
    with patch("scripts.gaming_split._CACHED_ENCODER", None), \
         patch("subprocess.run") as mock_run:
        mock_encoders = MagicMock(stdout=" V....D h264_nvenc NVIDIA NVENC H.264 encoder\n V....D h264_qsv Intel QuickSync H.264 encoder\n")
        mock_nvenc_fail = subprocess.CalledProcessError(255, ["ffmpeg"])
        mock_run.side_effect = [mock_encoders, mock_nvenc_fail]

        codec, preset, extra_args = gaming_split.get_best_encoder()
        assert codec == "h264_qsv"
        assert preset == "veryfast"
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

def test_get_best_encoder_caches_result():
    with patch("scripts.gaming_split._CACHED_ENCODER", None), \
         patch("subprocess.run") as mock_run:
        mock_encoders = MagicMock(stdout=" V....D h264_nvenc NVIDIA NVENC H.264 encoder\n")
        mock_probe = MagicMock(returncode=0)
        mock_run.side_effect = [mock_encoders, mock_probe]

        enc1 = gaming_split.get_best_encoder()
        enc2 = gaming_split.get_best_encoder()

        assert enc1 == enc2
        # Should only run subprocess twice (encoders + probe), not 4 times
        assert mock_run.call_count == 2

def test_get_best_encoder_amf_detection():
    with patch("scripts.gaming_split._CACHED_ENCODER", None), \
         patch("subprocess.run") as mock_run:
        mock_encoders = MagicMock(stdout=" V....D h264_amf AMD AMF H.264 encoder\n")
        mock_run.return_value = mock_encoders

        codec, preset, extra_args = gaming_split.get_best_encoder()
        assert codec == "h264_amf"
        assert preset == "speed"

def test_get_best_encoder_qsv_detection():
    with patch("scripts.gaming_split._CACHED_ENCODER", None), \
         patch("subprocess.run") as mock_run:
        mock_encoders = MagicMock(stdout=" V....D h264_qsv Intel QuickSync H.264 encoder\n")
        mock_run.return_value = mock_encoders

        codec, preset, extra_args = gaming_split.get_best_encoder()
        assert codec == "h264_qsv"
        assert preset == "veryfast"

def test_get_best_encoder_ffmpeg_not_found():
    with patch("scripts.gaming_split._CACHED_ENCODER", None), \
         patch("subprocess.run", side_effect=FileNotFoundError("ffmpeg not found")):

        codec, preset, extra_args = gaming_split.get_best_encoder()
        assert codec == "libx264"
        assert preset == "ultrafast"

def test_build_gaming_split_filter_defaults_to_bicubic():
    filt = gaming_split.build_gaming_split_filter(
        facecam_box=gaming_split.DEFAULT_FACECAM_BOX,
        gameplay_box=gaming_split.DEFAULT_GAMEPLAY_BOX,
        src_w=1920,
        src_h=1080
    )
    assert "flags=bicubic" in filt
    assert "flags=lanczos" not in filt

def test_build_gaming_split_filter_custom_scale_flags():
    filt = gaming_split.build_gaming_split_filter(
        facecam_box=gaming_split.DEFAULT_FACECAM_BOX,
        gameplay_box=gaming_split.DEFAULT_GAMEPLAY_BOX,
        src_w=1920,
        src_h=1080,
        scale_flags="bilinear"
    )
    assert "flags=bilinear" in filt
    assert "flags=bicubic" not in filt

def test_render_manual_crop_clip_audio_copy_fails_falls_back_to_aac(tmp_path):
    in_video = tmp_path / "in.mp4"
    in_video.write_text("fake video")
    out_video = tmp_path / "out.mp4"

    commands_executed = []
    def fake_subprocess_run(cmd, *args, **kwargs):
        commands_executed.append(list(cmd))
        # audio copy fails
        if "-c:a" in cmd and cmd[cmd.index("-c:a") + 1] == "copy":
            raise subprocess.CalledProcessError(1, cmd, stderr="Cannot copy audio")
        return MagicMock(returncode=0)

    with patch("scripts.gaming_split._CACHED_ENCODER", ("libx264", "ultrafast", ["-crf", "18"])), \
         patch("scripts.gaming_split.probe_video_dimensions", return_value=(1920, 1080)), \
         patch("subprocess.run", side_effect=fake_subprocess_run):

        res = gaming_split.render_manual_crop_clip(str(in_video), str(out_video))
        assert res == str(out_video)
        # Confirm fallback to aac occurred
        assert any("-c:a" in c and c[c.index("-c:a") + 1] == "aac" for c in commands_executed)

def test_render_gaming_split_clip_uses_best_encoder(tmp_path):
    in_video = tmp_path / "in.mp4"
    in_video.write_text("fake video")
    out_video = tmp_path / "out.mp4"

    commands_executed = []
    def fake_subprocess_run(cmd, *args, **kwargs):
        commands_executed.append(list(cmd))
        return MagicMock(returncode=0)

    with patch("scripts.gaming_split._CACHED_ENCODER", ("h264_nvenc", "p1", ["-b:v", "5M"])), \
         patch("scripts.gaming_split.probe_video_dimensions", return_value=(1920, 1080)), \
         patch("subprocess.run", side_effect=fake_subprocess_run):

        res = gaming_split.render_gaming_split_clip(str(in_video), str(out_video))
        assert res == str(out_video)
        assert len(commands_executed) == 1
        cmd = commands_executed[0]
        assert "-c:v" in cmd
        assert cmd[cmd.index("-c:v") + 1] == "h264_nvenc"
        assert "-preset" in cmd
        assert cmd[cmd.index("-preset") + 1] == "p1"
        assert "-b:v" in cmd
        assert cmd[cmd.index("-b:v") + 1] == "5M"

def test_render_gaming_split_clip_recovers_from_hardware_encoder_failure(tmp_path):
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

        res = gaming_split.render_gaming_split_clip(str(in_video), str(out_video))
        assert res == str(out_video)
        assert gaming_split._CACHED_ENCODER[0] == "libx264"
        assert any("-c:v" in c and c[c.index("-c:v") + 1] == "libx264" for c in commands_executed)

def test_render_gaming_split_clip_audio_copy_fails_falls_back_to_aac(tmp_path):
    in_video = tmp_path / "in.mp4"
    in_video.write_text("fake video")
    out_video = tmp_path / "out.mp4"

    commands_executed = []
    def fake_subprocess_run(cmd, *args, **kwargs):
        commands_executed.append(list(cmd))
        if "-c:a" in cmd and cmd[cmd.index("-c:a") + 1] == "copy":
            raise subprocess.CalledProcessError(1, cmd, stderr="Cannot copy audio")
        return MagicMock(returncode=0)

    with patch("scripts.gaming_split._CACHED_ENCODER", ("libx264", "ultrafast", ["-crf", "18"])), \
         patch("scripts.gaming_split.probe_video_dimensions", return_value=(1920, 1080)), \
         patch("subprocess.run", side_effect=fake_subprocess_run):

        res = gaming_split.render_gaming_split_clip(str(in_video), str(out_video))
        assert res == str(out_video)
        assert any("-c:a" in c and c[c.index("-c:a") + 1] == "aac" for c in commands_executed)

def test_render_gaming_split_clip_hardware_failure_and_audio_copy_failure(tmp_path):
    in_video = tmp_path / "in.mp4"
    in_video.write_text("fake video")
    out_video = tmp_path / "out.mp4"

    commands_executed = []
    def fake_subprocess_run(cmd, *args, **kwargs):
        commands_executed.append(list(cmd))
        # Fail if using hardware encoder
        if "-c:v" in cmd and cmd[cmd.index("-c:v") + 1] == "h264_nvenc":
            raise subprocess.CalledProcessError(255, cmd, stderr="NVENC failed")
        # Fail if copying audio under CPU
        if "-c:a" in cmd and cmd[cmd.index("-c:a") + 1] == "copy":
            raise subprocess.CalledProcessError(1, cmd, stderr="Cannot copy audio")
        return MagicMock(returncode=0)

    with patch("scripts.gaming_split._CACHED_ENCODER", ("h264_nvenc", "p1", ["-b:v", "5M"])), \
         patch("scripts.gaming_split.probe_video_dimensions", return_value=(1920, 1080)), \
         patch("subprocess.run", side_effect=fake_subprocess_run):

        res = gaming_split.render_gaming_split_clip(str(in_video), str(out_video))
        assert res == str(out_video)
        assert len(commands_executed) == 3
        # Run 1: nvenc + copy
        assert commands_executed[0][commands_executed[0].index("-c:v") + 1] == "h264_nvenc"
        assert commands_executed[0][commands_executed[0].index("-c:a") + 1] == "copy"
        # Run 2: libx264 + copy
        assert commands_executed[1][commands_executed[1].index("-c:v") + 1] == "libx264"
        assert commands_executed[1][commands_executed[1].index("-c:a") + 1] == "copy"
        # Run 3: libx264 + aac
        assert commands_executed[2][commands_executed[2].index("-c:v") + 1] == "libx264"
        assert commands_executed[2][commands_executed[2].index("-c:a") + 1] == "aac"
