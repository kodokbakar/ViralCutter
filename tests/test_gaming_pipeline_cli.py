import subprocess
import sys
import pytest
from webui.backend.schemas.jobs import JobRunRequest

def test_main_improved_has_pipeline_mode_flag():
    result = subprocess.run(
        [sys.executable, "main_improved.py", "--help"],
        capture_output=True,
        text=True,
        check=True
    )
    assert "--pipeline-mode" in result.stdout
    assert "gaming" in result.stdout

def test_job_run_request_pipeline_mode_mapping():
    req = JobRunRequest(
        video_path="/tmp/game.mp4",
        pipeline_mode="gaming",
        orientation="9:16_gaming_split"
    )
    args = req.to_cli_args(python_exec="python", script_path="main_improved.py")
    assert "--pipeline-mode" in args
    idx = args.index("--pipeline-mode")
    assert args[idx + 1] == "gaming"

def test_main_improved_rejects_invalid_pipeline_mode():
    result = subprocess.run(
        [sys.executable, "main_improved.py", "--pipeline-mode", "invalid_mode"],
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert "invalid choice" in result.stderr

def test_job_run_request_auto_routes_default_orientation_for_gaming():
    req = JobRunRequest(
        video_path="/tmp/game.mp4",
        pipeline_mode="gaming",
        orientation="9:16"
    )
    args = req.to_cli_args(python_exec="python", script_path="main_improved.py")
    assert "--orientation" in args
    idx = args.index("--orientation")
    assert args[idx + 1] == "9:16_gaming_split"

def test_job_manager_stage_for_line_gaming_detection():
    from webui.backend.core.job_manager import stage_for_line
    line1 = "Running Offline Multimodal Gaming Moment Detection Pipeline..."
    line2 = "Running Gaming Moment Detection..."
    assert stage_for_line(line1) == "AI segment selection"
    assert stage_for_line(line2) == "AI segment selection"

def test_main_improved_accepts_offline_ai_backend():
    result = subprocess.run(
        [sys.executable, "main_improved.py", "--ai-backend", "offline", "--help"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "offline" in result.stdout


def test_main_improved_rejects_invalid_ai_backend():
    result = subprocess.run(
        [sys.executable, "main_improved.py", "--ai-backend", "invalid_backend", "--help"],
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert "invalid choice" in result.stderr
