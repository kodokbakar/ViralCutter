import subprocess
import sys
import pytest
from webui.backend.schemas.jobs import JobRunRequest

def test_gaming_split_cli_flags_present():
    result = subprocess.run(
        [sys.executable, "main_improved.py", "--help"],
        capture_output=True,
        text=True,
        check=True
    )
    assert "--gaming-split" in result.stdout or "9:16_gaming_split" in result.stdout
    assert "--gaming-facecam" in result.stdout
    assert "--gaming-gameplay" in result.stdout

def test_job_run_request_gaming_split_mapping():
    req = JobRunRequest(
        video_path="/tmp/video.mp4",
        orientation="9:16_gaming_split",
        gaming_facecam_crop="0.1,0.2,0.3,0.4",
        gaming_gameplay_crop="0.2,0.3,0.4,0.5"
    )
    args = req.to_cli_args(python_exec="python", script_path="main_improved.py")
    assert "--orientation" in args
    assert "9:16_gaming_split" in args
    assert "--gaming-facecam" in args
    assert "0.1,0.2,0.3,0.4" in args
    assert "--gaming-gameplay" in args
    assert "0.2,0.3,0.4,0.5" in args

def test_job_run_request_defaults():
    req = JobRunRequest(
        video_path="/tmp/video.mp4"
    )
    args = req.to_cli_args(python_exec="python", script_path="main_improved.py")
    assert "--orientation" in args
    assert "9:16" in args
    assert "--gaming-facecam" not in args
    assert "--gaming-gameplay" not in args
