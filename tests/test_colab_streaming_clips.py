import json
import os
import shutil
import tempfile
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from webui.backend.config import VIRALS_DIR
from webui.backend.core.job_manager import Job, job_manager
from webui.backend.main import app
from webui.backend.schemas.jobs import JobRunRequest

client = TestClient(app)


def test_sse_streaming_headers(monkeypatch):
    """Verify anti-buffering SSE headers: Content-Encoding, Cache-Control, X-Accel-Buffering."""
    # Create a dummy completed job
    req = JobRunRequest(project_name="test_sse_headers_proj")
    job = Job(job_id="job_test_sse_headers", request=req)
    job.status = "completed"
    job.emit("complete", {"status": "completed", "output_dir": str(VIRALS_DIR / "test_sse_headers_proj")})

    with job_manager.lock:
        job_manager.jobs[job.job_id] = job

    response = client.get(f"/api/v1/jobs/{job.job_id}/stream")
    assert response.status_code == 200
    headers = response.headers
    assert "no-cache" in headers.get("Cache-Control", "")
    assert "no-transform" in headers.get("Cache-Control", "")
    assert headers.get("X-Accel-Buffering") == "no"
    assert headers.get("Content-Encoding") == "identity"
    assert "text/event-stream" in headers.get("Content-Type", "")


def test_colab_gdrive_video_isolation(tmp_path, monkeypatch):
    """
    Ensure video from Google Drive mount (/content/drive/...) is copied to local
    VIRALS_DIR and --project-path is never assigned directly to Google Drive.
    """
    mock_virals = tmp_path / "VIRALS"
    mock_virals.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr("webui.backend.schemas.jobs.VIRALS_DIR", mock_virals)

    # Create a simulated Google Drive file
    gdrive_video = tmp_path / "mock_drive" / "my_video.mp4"
    gdrive_video.parent.mkdir(parents=True, exist_ok=True)
    gdrive_video.write_bytes(b"dummy video data")

    # Set video_path to simulated Google Drive path
    fake_gdrive_path = f"/content/drive/MyDrive/my_video.mp4"
    req = JobRunRequest(video_path=fake_gdrive_path)

    # Monkeypatch src file existence for the copy test
    def mock_ensure_input_video(self, project_dir: Path, source_path: str):
        target = project_dir / "input.mp4"
        project_dir.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b"dummy copied video data")

    monkeypatch.setattr(JobRunRequest, "_ensure_input_video", mock_ensure_input_video)

    cmd = req.to_cli_args(python_exec="python3", script_path="main_improved.py")
    assert "--project-path" in cmd
    proj_arg = cmd[cmd.index("--project-path") + 1]

    # Must be in VIRALS_DIR, never in /content/drive
    assert not proj_arg.startswith("/content/drive")
    assert proj_arg == str(mock_virals / "my_video")


def test_colab_gdrive_project_path_isolation(tmp_path, monkeypatch):
    """
    Ensure project_path set to Google Drive is redirected to local VIRALS_DIR.
    """
    mock_virals = tmp_path / "VIRALS"
    mock_virals.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr("webui.backend.schemas.jobs.VIRALS_DIR", mock_virals)

    req = JobRunRequest(project_path="/content/drive/MyDrive/MyProject")
    cmd = req.to_cli_args(python_exec="python3", script_path="main_improved.py")
    assert "--project-path" in cmd
    proj_arg = cmd[cmd.index("--project-path") + 1]

    assert not proj_arg.startswith("/content/drive")
    assert proj_arg == str(mock_virals / "MyProject")


def test_project_clips_endpoint_burned_sub_priority(tmp_path, monkeypatch):
    """
    Test GET /api/v1/library/projects/{project_name}/clips:
    1. Returns burned_sub/ clips when available with score and hook title metadata.
    2. Excludes input.mp4 and cuts/.
    """
    mock_virals = tmp_path / "VIRALS"
    mock_virals.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr("webui.backend.api.v1.library.VIRALS_DIR", mock_virals)

    proj_dir = mock_virals / "TestProjectAlpha"
    proj_dir.mkdir(parents=True, exist_ok=True)

    # Create root input.mp4 and cuts/ (should be ignored)
    (proj_dir / "input.mp4").write_bytes(b"root video")
    cuts_dir = proj_dir / "cuts"
    cuts_dir.mkdir(parents=True, exist_ok=True)
    (cuts_dir / "segment_000.mp4").write_bytes(b"cut 0")

    # Create final/ clean videos
    final_dir = proj_dir / "final"
    final_dir.mkdir(parents=True, exist_ok=True)
    (final_dir / "000_ClipAlpha.mp4").write_bytes(b"final 0")
    (final_dir / "001_ClipBeta.mp4").write_bytes(b"final 1")

    # Create burned_sub/ final hardsub videos
    burned_dir = proj_dir / "burned_sub"
    burned_dir.mkdir(parents=True, exist_ok=True)
    clip1 = burned_dir / "000_ClipAlpha_subtitled.mp4"
    clip2 = burned_dir / "001_ClipBeta_subtitled.mp4"
    clip1.write_bytes(b"burned 0")
    clip2.write_bytes(b"burned 1")

    # Create viral_segments.json
    segments_data = {
        "segments": [
            {
                "order": 1,
                "score": 96,
                "hook_title": "SECRET HACK REVEALED",
                "title": "Segment 1",
                "start": 10.0,
                "end": 45.0,
                "duration": 35.0,
            },
            {
                "order": 2,
                "score": 88,
                "hook_title": "WHY THIS MATTERS",
                "title": "Segment 2",
                "start": 50.0,
                "end": 90.0,
                "duration": 40.0,
            },
        ]
    }
    (proj_dir / "viral_segments.json").write_text(json.dumps(segments_data), encoding="utf-8")

    # Create timeline file in final/
    timeline1 = [
        {"frame": 0, "mode": "1", "hook_title": "SECRET HACK REVEALED OVERRIDE"}
    ]
    (final_dir / "000_ClipAlpha_timeline.json").write_text(json.dumps(timeline1), encoding="utf-8")

    res = client.get("/api/v1/library/projects/TestProjectAlpha/clips")
    assert res.status_code == 200
    clips = res.json()

    assert len(clips) == 2
    # Verify burned_sub priority
    assert clips[0]["folder_type"] == "burned_sub"
    assert clips[0]["name"] == "000_ClipAlpha_subtitled.mp4"
    assert clips[0]["score"] == 96.0
    assert clips[0]["hook_title"] == "SECRET HACK REVEALED OVERRIDE"
    assert clips[0]["duration"] == 35.0

    assert clips[1]["folder_type"] == "burned_sub"
    assert clips[1]["name"] == "001_ClipBeta_subtitled.mp4"
    assert clips[1]["score"] == 88.0
    assert clips[1]["hook_title"] == "WHY THIS MATTERS"
    assert clips[1]["duration"] == 40.0

    # Ensure cuts and input.mp4 were not included
    for c in clips:
        assert "input.mp4" not in c["name"]
        assert "cuts" not in c["path"]


def test_project_clips_endpoint_burned_sub_only(tmp_path, monkeypatch):
    """
    Test that clips endpoint strictly requires burned_sub/ and does not fallback to final/.
    """
    mock_virals = tmp_path / "VIRALS"
    mock_virals.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr("webui.backend.api.v1.library.VIRALS_DIR", mock_virals)

    proj_dir = mock_virals / "TestProjectCutOnly"
    proj_dir.mkdir(parents=True, exist_ok=True)

    # final/ videos should not be included if burned_sub is empty
    final_dir = proj_dir / "final"
    final_dir.mkdir(parents=True, exist_ok=True)
    (final_dir / "000_CutOnly.mp4").write_bytes(b"cut only video")

    res = client.get("/api/v1/library/projects/TestProjectCutOnly/clips")
    assert res.status_code == 200
    assert res.json() == []

    # Now put clip inside burned_sub/
    burned_dir = proj_dir / "burned_sub"
    burned_dir.mkdir(parents=True, exist_ok=True)
    (burned_dir / "000_BurnedSub.mp4").write_bytes(b"burned subtitle video")

    segments_data = {
        "segments": [
            {
                "score": 91,
                "hook_title": "BURNED HOOK",
                "duration": 25.5,
            }
        ]
    }
    (proj_dir / "viral_segments.txt").write_text(json.dumps(segments_data), encoding="utf-8")

    res2 = client.get("/api/v1/library/projects/TestProjectCutOnly/clips")
    assert res2.status_code == 200
    clips = res2.json()
    assert len(clips) == 1
    assert clips[0]["folder_type"] == "burned_sub"
    assert clips[0]["name"] == "000_BurnedSub.mp4"
    assert clips[0]["score"] == 91.0
    assert clips[0]["hook_title"] == "BURNED HOOK"
    assert clips[0]["duration"] == 25.5

def test_project_clips_endpoint_404(tmp_path, monkeypatch):
    mock_virals = tmp_path / "VIRALS"
    mock_virals.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr("webui.backend.api.v1.library.VIRALS_DIR", mock_virals)

    res = client.get("/api/v1/library/projects/NonExistentProject/clips")
    assert res.status_code == 404
