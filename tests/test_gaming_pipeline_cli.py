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
