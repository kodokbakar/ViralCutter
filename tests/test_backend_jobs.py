import sys
import time
import pytest
from fastapi.testclient import TestClient

from webui.backend.config import ensure_directories
from webui.backend.core.job_manager import (
    Job,
    JobConflictError,
    JobManager,
    extract_project_folder_from_line,
    format_duration,
    job_manager,
    stage_for_line,
)
from webui.backend.main import app
from webui.backend.schemas.jobs import JobRunRequest


@pytest.fixture(autouse=True)
def reset_job_manager():
    """Ensure JobManager is clean before each test."""
    ensure_directories()
    # Cancel any running job
    active = job_manager.get_active_job()
    if active:
        active.cancel()
        time.sleep(0.1)
    job_manager.active_job = None
    job_manager.jobs.clear()
    yield
    active = job_manager.get_active_job()
    if active:
        active.cancel()


def test_format_duration():
    assert format_duration(0) == "00:00:00"
    assert format_duration(65) == "00:01:05"
    assert format_duration(3665) == "01:01:05"


def test_stage_for_line():
    assert stage_for_line("Starting download from YouTube...") == "Download"
    assert stage_for_line("transcribing with model large-v3...") == "Transcription"
    assert stage_for_line("creating viral segments now") == "AI segment selection"
    assert stage_for_line("process completed successfully") == "Completed"
    assert stage_for_line("random unmapped line") is None


def test_extract_project_folder():
    assert extract_project_folder_from_line("Project Folder: /path/to/project_123") == "/path/to/project_123"
    assert extract_project_folder_from_line("No folder line here") is None


def test_job_run_request_cli_mapping():
    req = JobRunRequest(
        url="https://youtube.com/watch?v=123",
        segments=5,
        viral=True,
        min_duration=20,
        max_duration=60,
        model="tiny",
        language="en",
        smart_clipping=True,
        smart_clipping_mode="continuous",
        watermark_mode="text",
        watermark_text="ViralCutter",
    )
    cmd = req.to_cli_args(python_exec="python3", script_path="main_improved.py")

    assert cmd[0] == "python3"
    assert cmd[1] == "main_improved.py"
    assert "--url" in cmd
    assert cmd[cmd.index("--url") + 1] == "https://youtube.com/watch?v=123"
    assert "--segments" in cmd
    assert cmd[cmd.index("--segments") + 1] == "5"
    assert "--viral" in cmd
    assert "--min-duration" in cmd
    assert cmd[cmd.index("--min-duration") + 1] == "20"
    assert "--max-duration" in cmd
    assert cmd[cmd.index("--max-duration") + 1] == "60"
    assert "--smart-clipping" in cmd
    assert "--smart-clipping-mode" in cmd
    assert cmd[cmd.index("--smart-clipping-mode") + 1] == "continuous"
    assert "--watermark-mode" in cmd
    assert cmd[cmd.index("--watermark-mode") + 1] == "text"
    assert "--watermark-text" in cmd
    assert cmd[cmd.index("--watermark-text") + 1] == "ViralCutter"


def test_job_manager_single_lock():
    # Start long-running mock process
    req = JobRunRequest(
        custom_cmd=[sys.executable, "-c", "import time; time.sleep(2)"]
    )
    job1 = job_manager.start_job(req)
    assert job1 is not None
    time.sleep(0.1)
    assert job_manager.is_running() is True

    # Attempt to start second job while first is running
    with pytest.raises(JobConflictError):
        job_manager.start_job(req)

    # Cancel first job
    cancelled = job_manager.cancel_job(job1.job_id)
    assert cancelled is True
    assert job1.status == "cancelled"
    assert job_manager.is_running() is False


def test_fastapi_api_lifecycle():
    client = TestClient(app)

    # 1. Health check
    res_health = client.get("/api/v1/health")
    assert res_health.status_code == 200
    assert res_health.json() == {"status": "ok"}

    # 2. Check no active job initially
    res_active = client.get("/api/v1/jobs/active")
    assert res_active.status_code == 200
    assert res_active.json()["active"] is False

    # 3. Start a mock job that prints logs and finishes
    mock_script = (
        "import time\n"
        "print('Starting download of test video')\n"
        "time.sleep(0.2)\n"
        "print('transcribing with model test')\n"
        "time.sleep(0.2)\n"
        "print('Project Folder: /tmp/test_project')\n"
        "print('process completed')\n"
    )
    req_payload = {
        "custom_cmd": [sys.executable, "-c", mock_script]
    }
    res_run = client.post("/api/v1/jobs/run", json=req_payload)
    assert res_run.status_code == 200
    job_id = res_run.json()["job_id"]
    assert job_id.startswith("job_")

    # 4. Check conflict while running
    res_conflict = client.post("/api/v1/jobs/run", json=req_payload)
    if job_manager.is_running():
        assert res_conflict.status_code == 409
        assert "in progress" in res_conflict.json()["detail"]

    # 5. Check active endpoint
    time.sleep(0.1)
    res_active_running = client.get("/api/v1/jobs/active")
    assert res_active_running.status_code == 200

    # 6. Stream SSE events
    # Test streaming directly using generator or client
    job = job_manager.get_job(job_id)
    assert job is not None
    # Wait for mock job to complete
    for _ in range(100):
        if job.status in ("completed", "failed"):
            break
        time.sleep(0.05)

    # Now verify events were emitted
    event_types = [ev["event"] for ev in job.events]
    assert "log" in event_types
    assert "progress" in event_types
    assert job.status == "completed", f"Status: {job.status}, Error: {job.error}, Events: {job.events}"
    assert "complete" in event_types

    # 7. Check final status
    res_status = client.get(f"/api/v1/jobs/{job_id}")
    assert res_status.status_code == 200
    assert res_status.json()["status"] == "completed"
    assert res_status.json()["percent"] == 100


def test_fastapi_cancel_job():
    client = TestClient(app)

    mock_script = "import time; time.sleep(5)"
    res_run = client.post("/api/v1/jobs/run", json={"custom_cmd": [sys.executable, "-c", mock_script]})
    assert res_run.status_code == 200
    job_id = res_run.json()["job_id"]

    time.sleep(0.1)
    assert job_manager.is_running() is True

    # Cancel via API
    res_cancel = client.post(f"/api/v1/jobs/{job_id}/cancel")
    assert res_cancel.status_code == 200
    assert res_cancel.json()["status"] == "cancelled"

    time.sleep(0.1)
    assert job_manager.is_running() is False


@pytest.mark.anyio
async def test_job_event_generator_sse_stream():
    req = JobRunRequest(url="https://youtube.com/watch?v=mock")
    job = Job(job_id="test_sse_job", request=req)

    job.emit("progress", {"stage": "TRANSCRIPTION", "percent": 40, "elapsed": "00:01:23"})
    job.emit("log", {"level": "INFO", "timestamp": "14:20:10", "message": "Test log line"})
    job.emit("complete", {"status": "completed", "output_dir": "/tmp/out"})

    chunks = []
    async for chunk in job.event_generator():
        chunks.append(chunk)

    joined = "".join(chunks)
    assert "event: progress\ndata: {\"stage\": \"TRANSCRIPTION\", \"percent\": 40, \"elapsed\": \"00:01:23\"}\n\n" in joined
    assert "event: log\ndata: {\"level\": \"INFO\", \"timestamp\": \"14:20:10\", \"message\": \"Test log line\"}\n\n" in joined
    assert "event: complete\ndata: {\"status\": \"completed\", \"output_dir\": \"/tmp/out\"}\n\n" in joined

