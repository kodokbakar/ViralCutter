from unittest.mock import patch
from webui.backend.schemas.jobs import JobRunRequest


def test_job_run_request_keeps_framing_for_vertical_source(tmp_path):
    dummy_video = tmp_path / "vertical.mp4"
    dummy_video.write_bytes(b"dummy")

    with patch("scripts.gaming_split.is_vertical_video", return_value=True):
        req = JobRunRequest(
            video_path=str(dummy_video),
            pipeline_mode="gaming",
            orientation="9:16"
        )
        cmd = req.to_cli_args("python", "main_improved.py")

        # When source is vertical, it should NOT route to 9:16_gaming_split
        assert "9:16_gaming_split" not in cmd
        assert "--face-mode" in cmd
        assert "none" in cmd
        assert "--orientation" in cmd
        assert cmd[cmd.index("--orientation") + 1] == "16:9"
        assert cmd[cmd.index("--face-mode") + 1] == "none"


def test_job_run_request_horizontal_source_routes_to_gaming_split(tmp_path):
    dummy_video = tmp_path / "horizontal.mp4"
    dummy_video.write_bytes(b"dummy")

    with patch("scripts.gaming_split.is_vertical_video", return_value=False):
        req = JobRunRequest(
            video_path=str(dummy_video),
            pipeline_mode="gaming",
            orientation="9:16"
        )
        cmd = req.to_cli_args("python", "main_improved.py")

        assert "9:16_gaming_split" in cmd
        assert cmd[cmd.index("--orientation") + 1] == "9:16_gaming_split"
        assert cmd[cmd.index("--face-mode") + 1] == "auto"


def test_job_run_request_vertical_source_podcast_mode_keeps_9_16(tmp_path):
    dummy_video = tmp_path / "vertical.mp4"
    dummy_video.write_bytes(b"dummy")

    with patch("scripts.gaming_split.is_vertical_video", return_value=True):
        req = JobRunRequest(
            video_path=str(dummy_video),
            pipeline_mode="podcast",
            orientation="9:16"
        )
        cmd = req.to_cli_args("python", "main_improved.py")

        assert cmd[cmd.index("--orientation") + 1] == "9:16"
        assert cmd[cmd.index("--face-mode") + 1] == "auto"
