import asyncio
import os
import sys
import time
import pytest
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient

from webui.backend.config import VIRALS_DIR, ensure_directories
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
        active.cancel_sync()
        time.sleep(0.1)
    job_manager.active_job = None
    job_manager.jobs.clear()
    yield
    active = job_manager.get_active_job()
    if active:
        active.cancel_sync()


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
    assert cmd[1] == "-u"
    assert cmd[2] == "main_improved.py"
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
    cancelled = job_manager.cancel_job_sync(job1.job_id)
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


@pytest.mark.anyio
async def test_job_event_generator_heartbeat_ping():
    req = JobRunRequest(url="https://youtube.com/watch?v=mock")
    job = Job(job_id="test_ping_job", request=req)

    gen = job.event_generator()
    ping_chunk = None
    start = time.time()
    while time.time() - start < 2.0:
        chunk = await anext(gen)
        if chunk == ": ping\n\n":
            ping_chunk = chunk
            break

    assert ping_chunk == ": ping\n\n"

    # Emit complete event and ensure it resumes and finishes cleanly
    job.emit("complete", {"status": "completed", "output_dir": "/tmp/out"})
    next_chunk = await anext(gen)
    assert "event: complete" in next_chunk


@pytest.mark.anyio
async def test_stream_job_logs_headers():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        req = JobRunRequest(url="https://youtube.com/watch?v=mock")
        job = Job(job_id="test_headers_job", request=req)
        with job_manager.lock:
            job_manager.jobs[job.job_id] = job
        job.emit("complete", {"status": "completed", "output_dir": "/tmp/out"})

        async with client.stream("GET", f"/api/v1/jobs/{job.job_id}/stream") as response:
            assert response.status_code == 200
            assert response.headers["Cache-Control"] == "no-cache, no-transform"
            assert response.headers["Connection"] == "keep-alive"
            assert response.headers["X-Accel-Buffering"] == "no"
            assert response.headers["Content-Type"] == "text/event-stream; charset=utf-8"


def test_cli_mapping_project_name_and_video_path():
    # 1. project_name only
    req1 = JobRunRequest(project_name="my_cool_project")
    cmd1 = req1.to_cli_args(python_exec="python3", script_path="main_improved.py")
    assert "--project-path" in cmd1
    assert cmd1[cmd1.index("--project-path") + 1] == str(VIRALS_DIR / "my_cool_project")
    assert "--skip-youtube-subs" in cmd1

    # 2. video_path only (file path)
    req2 = JobRunRequest(video_path="/tmp/awesome_video.mp4")
    cmd2 = req2.to_cli_args(python_exec="python3", script_path="main_improved.py")
    assert "--project-path" in cmd2
    assert cmd2[cmd2.index("--project-path") + 1] == str(VIRALS_DIR / "awesome_video")
    assert "--skip-youtube-subs" in cmd2

    # 3. video_path with input.mp4 leaf
    req3 = JobRunRequest(video_path="/tmp/existing_run/input.mp4")
    cmd3 = req3.to_cli_args(python_exec="python3", script_path="main_improved.py")
    assert "--project-path" in cmd3
    assert cmd3[cmd3.index("--project-path") + 1] == "/tmp/existing_run"
    assert "--skip-youtube-subs" in cmd3

    # 4. project_name + video_path
    req4 = JobRunRequest(project_name="target_folder", video_path="/tmp/source.mp4")
    cmd4 = req4.to_cli_args(python_exec="python3", script_path="main_improved.py")
    assert "--project-path" in cmd4
    assert cmd4[cmd4.index("--project-path") + 1] == str(VIRALS_DIR / "target_folder")
    assert "--skip-youtube-subs" in cmd4


def test_temp_files_lifecycle():
    req = JobRunRequest(
        prompt_template="Custom AI prompt instructions",
        subtitle_config={"font_size": 24, "primary_color": "&H00FFFFFF"},
    )
    cmd = req.to_cli_args(python_exec="python3", script_path="main_improved.py")
    prompt_file = cmd[cmd.index("--prompt-file") + 1]
    subtitle_file = cmd[cmd.index("--subtitle-config") + 1]

    # Verify temp files created and exist
    assert os.path.isfile(prompt_file)
    assert os.path.isfile(subtitle_file)

    with open(prompt_file, "r", encoding="utf-8") as f:
        assert f.read() == "Custom AI prompt instructions"

    # Cleanup temp files
    req.cleanup_temp_files()
    assert not os.path.exists(prompt_file)
    assert not os.path.exists(subtitle_file)


def test_early_cancel_before_spawn_cleans_state():
    req = JobRunRequest(
        custom_cmd=[sys.executable, "-c", "import time; time.sleep(10)"]
    )
    job = job_manager.start_job(req)
    # Immediately cancel before subprocess starts or right away
    cancelled = job_manager.cancel_job_sync(job.job_id)
    assert cancelled is True
    assert job.status == "cancelled"
    assert job_manager.is_running() is False
    assert job_manager.get_active_job() is None

    # Verify subsequent job can be started immediately without 409 conflict
    req2 = JobRunRequest(
        custom_cmd=[sys.executable, "-c", "import time; time.sleep(0.1)"]
    )
    job2 = job_manager.start_job(req2)
    assert job2 is not None
    assert job_manager.cancel_job_sync(job2.job_id) is True


def test_early_cancel_race_condition_never_spawns_process():
    req = JobRunRequest(
        custom_cmd=[sys.executable, "-c", "import time; time.sleep(10)"]
    )
    job = Job(job_id="test_early_race", request=req)
    # Cancel job before _run_job_process is called
    job.cancel_sync()
    assert job.status == "cancelled"

    # Run _run_job_process; should detect cancelled state and not spawn process
    job_manager._run_job_process(job)
    assert job.process is None
    assert job.status == "cancelled"


@pytest.mark.anyio
async def test_cancel_non_blocking_fastapi_event_loop():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Start a mock job that takes time
        res_run = await client.post(
            "/api/v1/jobs/run",
            json={"custom_cmd": [sys.executable, "-c", "import time; time.sleep(5)"]},
        )
        assert res_run.status_code == 200
        job_id = res_run.json()["job_id"]

        await asyncio.sleep(0.05)
        assert job_manager.is_running() is True

        # Launch cancel task and concurrently issue health requests
        cancel_task = asyncio.create_task(client.post(f"/api/v1/jobs/{job_id}/cancel"))

        # While cancel is executing, health endpoint must respond promptly (non-blocking event loop)
        health_start = time.perf_counter()
        res_health = await client.get("/api/v1/health")
        health_duration = time.perf_counter() - health_start

        assert res_health.status_code == 200
        assert res_health.json() == {"status": "ok"}
        assert health_duration < 0.5, f"Health endpoint blocked! Took {health_duration:.2f}s"

        res_cancel = await cancel_task
        assert res_cancel.status_code == 200
        assert res_cancel.json()["status"] == "cancelled"


def test_unbuffered_subprocess_execution(monkeypatch):
    import subprocess
    captured = {}
    original_popen = subprocess.Popen

    def mock_popen(*args, **kwargs):
        captured["args"] = args
        captured["kwargs"] = kwargs
        return original_popen(
            [sys.executable, "-c", "import sys; print('unbuffered_line')"],
            cwd=kwargs.get("cwd"),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            start_new_session=True,
        )

    monkeypatch.setattr(subprocess, "Popen", mock_popen)

    req = JobRunRequest(project_name="test_unbuffered")
    job = Job(job_id="test_unbuffered_job", request=req)
    job_manager._run_job_process(job)

    cmd = captured["args"][0]
    kwargs = captured["kwargs"]

    assert cmd[1] == "-u"
    assert kwargs.get("bufsize") == 1
    assert kwargs.get("text") is True
    assert kwargs.get("universal_newlines") is True
    assert kwargs["env"].get("PYTHONUNBUFFERED") == "1"
    assert kwargs["env"].get("PYTHONIOENCODING") == "utf-8"

    log_events = [ev for ev in job.events if ev["event"] == "log"]
    assert any("unbuffered_line" in ev["data"]["message"] for ev in log_events)



