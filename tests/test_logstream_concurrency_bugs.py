import asyncio
import os
import signal
import sys
import time
import pytest

from webui.backend.core.job_manager import Job, job_manager
from webui.backend.schemas.jobs import JobRunRequest


@pytest.mark.anyio
async def test_cancellation_race_drops_terminal_sse_event():
    """
    Bug: Cancellation race condition in event_generator.
    When job._initiate_cancel() marks status as 'cancelled', event_generator sees
    is_done=True and cursor >= len(self.events), causing it to break immediately.
    _finalize_cancel() emits the terminal 'error' event only afterwards, so the
    SSE client terminates abruptly without ever receiving the terminal event.
    """
    req = JobRunRequest(url="https://youtube.com/watch?v=mock")
    job = Job(job_id="test_cancel_race", request=req)
    job.status = "running"
    job.emit("log", {"level": "INFO", "timestamp": "12:00:00", "message": "job started"})

    gen = job.event_generator()
    first = await anext(gen)
    assert first.startswith(": stream-open")
    log = await anext(gen)
    assert "job started" in log

    # Cancellation initiated while client is listening
    job._initiate_cancel()

    # Client continues reading from SSE generator
    received = []
    try:
        while True:
            chunk = await anext(gen)
            received.append(chunk)
    except StopAsyncIteration:
        pass

    # Process cleanup finalizes cancellation
    job._finalize_cancel()

    has_terminal = any("event: error" in c or "event: complete" in c for c in received)
    assert has_terminal, (
        f"event_generator closed before receiving terminal event! Received: {received}"
    )


def test_windows_cancellation_attribute_error(monkeypatch):
    """
    Bug: On Windows, os.killpg and os.getpgid do not exist.
    Job._terminate_proc_group only catches (ProcessLookupError, PermissionError),
    so calling it on Windows raises AttributeError instead of falling back to proc.terminate()/kill().
    """
    req = JobRunRequest(url="https://youtube.com/watch?v=mock")
    job = Job(job_id="test_win_cancel", request=req)

    class DummyProc:
        pid = 12345
        terminated = False
        killed = False

        def poll(self):
            return None

        def terminate(self):
            self.terminated = True

        def kill(self):
            self.killed = True

    dummy = DummyProc()
    job.process = dummy

    # Simulate Windows environment
    monkeypatch.delattr(os, "killpg", raising=False)
    monkeypatch.delattr(os, "getpgid", raising=False)

    job._terminate_proc_group(dummy, signal.SIGTERM)
    assert dummy.terminated is True


def test_subprocess_non_utf8_output_drops_subsequent_logs():
    """
    Bug: Subprocess stdout reader uses text=True without errors='replace'.
    Any invalid UTF-8 byte sequence raises UnicodeDecodeError, aborting the read
    loop, closing proc.stdout, and dropping all subsequent logs.
    """
    script = (
        "import sys, time\n"
        "sys.stdout.buffer.write(b'start_marker\\n')\n"
        "sys.stdout.buffer.flush()\n"
        "time.sleep(0.05)\n"
        "sys.stdout.buffer.write(b'invalid_byte:\\xff\\xfe_end\\n')\n"
        "sys.stdout.buffer.flush()\n"
        "time.sleep(0.05)\n"
        "sys.stdout.buffer.write(b'subsequent_valid_marker\\n')\n"
        "sys.stdout.buffer.flush()\n"
    )
    req = JobRunRequest(custom_cmd=[sys.executable, "-c", script])
    job = Job("test_utf8_recovery", req)

    job_manager._run_job_process(job)

    # Collect messages from stdout (exclude initial command echo)
    messages = [
        e["data"].get("message", "")
        for e in job.events
        if e["event"] == "log" and not e["data"].get("message", "").startswith("Starting job")
    ]
    assert any(m == "subsequent_valid_marker" for m in messages), (
        f"Subsequent logs dropped after decoding error. Messages: {messages}"
    )


def test_job_completion_clears_active_job():
    """
    Bug: JobManager.active_job is never reset to None when a job completes or is cancelled,
    preventing garbage collection of the Job instance and all its buffered events.
    """
    req = JobRunRequest(custom_cmd=[sys.executable, "-c", "import time; time.sleep(0.05)"])
    job = job_manager.start_job(req)

    for _ in range(50):
        if job.status == "completed":
            break
        time.sleep(0.05)

    assert job.status == "completed"
    assert job_manager.active_job is None, (
        f"active_job was not cleared after job completion: {job_manager.active_job}"
    )


def test_sse_ping_cadence_relaxed_to_15s():
    """Verify default SSE ping cadence is relaxed from 0.5s to 15.0s."""
    import inspect
    sig = inspect.signature(Job.event_generator)
    assert sig.parameters["ping_interval"].default == 15.0



def test_terminate_proc_group_kills_nested_grandchildren():
    """
    Verify _terminate_proc_group recursively finds and terminates
    grandchild processes (e.g. spawned worker or GPU subprocesses).
    """
    import subprocess
    import psutil

    nested_script = (
        "import subprocess, sys, time; "
        "child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)']); "
        "time.sleep(60)"
    )
    proc = subprocess.Popen([sys.executable, '-c', nested_script], start_new_session=True)
    try:
        p_proc = psutil.Process(proc.pid)
        children = []
        for _ in range(30):
            children = p_proc.children(recursive=True)
            if children:
                break
            time.sleep(0.1)

        assert len(children) >= 1
        grandchild_pid = children[0].pid
        assert psutil.pid_exists(grandchild_pid)

        req = JobRunRequest(url='https://youtube.com/watch?v=mock')
        job = Job(job_id='test_nested_kill', request=req)
        job.process = proc

        job._terminate_proc_group(proc, signal.SIGKILL)
        proc.wait(timeout=5)

        time.sleep(0.2)
        assert not psutil.pid_exists(grandchild_pid)
    finally:
        try:
            if proc.poll() is None:
                proc.kill()
        except Exception:
            pass


@pytest.mark.anyio
async def test_concurrent_cancellation_calls_are_safe_and_idempotent():
    """
    Verify concurrent cancel() invocations on the same Job instance
    resolve safely, with exactly one returning True and no race-induced exceptions.
    """
    req = JobRunRequest(custom_cmd=[sys.executable, '-c', 'import time; time.sleep(10)'])
    job = job_manager.start_job(req)
    for _ in range(20):
        if job.status == 'running' and job.process is not None:
            break
        await asyncio.sleep(0.05)

    results = await asyncio.gather(
        job_manager.cancel_job(job.job_id),
        job_manager.cancel_job(job.job_id),
        job_manager.cancel_job(job.job_id),
    )
    assert results.count(True) == 1
    assert results.count(False) == 2
    assert job.status == 'cancelled'
    assert job_manager.active_job is None


def test_subprocess_pipe_handles_mixed_surrogates_and_cjk_binary_noise():
    """
    Verify stdout reader with errors='replace' handles arbitrary invalid byte sequences,
    multibyte CJK fragments, and surrogates without crashing or truncation.
    """
    script = (
        "import sys, time; "
        "sys.stdout.buffer.write('こんにちは世界\n'.encode('utf-8')); "
        "sys.stdout.buffer.flush(); "
        "time.sleep(0.02); "
        "sys.stdout.buffer.write(b'\xe3\x81\xff\xfe\xed\xa0\x80bad_bytes\n'); "
        "sys.stdout.buffer.flush(); "
        "time.sleep(0.02); "
        "sys.stdout.buffer.write('final_stream_success\n'.encode('utf-8')); "
        "sys.stdout.buffer.flush()"
    )
    req = JobRunRequest(custom_cmd=[sys.executable, '-c', script])
    job = Job('test_cjk_surrogates', req)
    job_manager._run_job_process(job)

    logs = [e['data'].get('message', '') for e in job.events if e.get('event') == 'log']
    assert any('こんにちは世界' in m for m in logs)
    assert any('final_stream_success' in m for m in logs)


def test_cancel_job_sync_when_process_already_exited():
    """
    Verify cancel_job_sync when process has already terminated
    returns False without exceptions and active_job is None.
    """
    req = JobRunRequest(custom_cmd=[sys.executable, '-c', 'import sys; sys.exit(0)'])
    job = job_manager.start_job(req)
    for _ in range(50):
        if job.status in ('completed', 'failed'):
            break
        time.sleep(0.05)

    assert job.status == 'completed'
    res = job_manager.cancel_job_sync(job.job_id)
    assert res is False
    assert job_manager.active_job is None

