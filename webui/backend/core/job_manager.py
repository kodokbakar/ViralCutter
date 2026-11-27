import asyncio
from collections import deque
import datetime
import json
import os
import signal
import subprocess
import threading
import time
from typing import Any, Dict, List, Optional, Tuple

from webui.backend.config import (
    MAIN_SCRIPT_PATH,
    PYTHON_EXECUTABLE,
    VIRALS_DIR,
)
from webui.backend.schemas.jobs import JobRunRequest, JobStatusResponse

STAGE_RULES = [
    ("starting download", "Download"),
    ("downloading video", "Download"),
    ("download finished", "Download"),
    ("transcribing with model", "Transcription"),
    ("iniciando transcrição", "Transcription"),
    ("starting full whisperx transcription", "Transcription"),
    ("starting model.transcribe", "Transcription"),
    ("model.transcribe() completed", "Transcription"),
    ("creating viral segments", "AI segment selection"),
    ("enviando chunk", "AI segment selection"),
    ("processing chunk", "AI segment selection"),
    ("gaming moment detection", "AI segment selection"),
    ("offline multimodal gaming moment detection", "AI segment selection"),
    ("matching", "Segment alignment"),
    ("segments aligned", "Segment alignment"),
    ("segment timings snapped", "Timing refinement"),
    ("cutting segments", "Video cutting"),
    ("generated segment", "Video cutting"),
    ("face mode none selected", "Face processing"),
    ("editing video with", "Face processing"),
    ("applying watermark", "Branding"),
    ("processing subtitles", "Subtitle processing"),
    ("adjusting subtitles", "Subtitle processing"),
    ("burning subtitles", "Subtitle processing"),
    ("compiling segments", "Subtitle processing"),
    ("compilation saved", "Subtitle processing"),
    ("process completed", "Completed"),
]

PIPELINE_STAGES = [
    ("Download", 1),
    ("Transcription", 2),
    ("AI segment selection", 3),
    ("Segment alignment", 4),
    ("Timing refinement", 5),
    ("Video cutting", 6),
    ("Face processing", 7),
    ("Branding", 8),
    ("Subtitle processing", 9),
    ("Completed", 9),
]
TOTAL_PIPELINE_STAGES = 9
STAGE_TO_INDEX = {stage: index for stage, index in PIPELINE_STAGES}


def format_duration(seconds: float) -> str:
    secs = int(max(0, seconds))
    h, rem = divmod(secs, 3600)
    m, s = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def stage_for_line(line: str) -> Optional[str]:
    lowered = line.lower()
    for needle, stage in STAGE_RULES:
        if needle in lowered:
            return stage
    return None


def extract_project_folder_from_line(line: str) -> Optional[str]:
    if "Project Folder:" not in line:
        return None
    parts = line.split("Project Folder:", 1)
    if len(parts) < 2:
        return None
    path = parts[1].strip()
    return path or None


class JobConflictError(Exception):
    """Raised when attempting to start a job while another job is active."""
    pass


def _iter_proc_lines(stream):
    """
    Universal non-blocking chunk/line reader that yields on either \r or \n.
    Prevents in-place carriage-return progress bars (tqdm/whisperx/ffmpeg)
    from blocking readline().
    """
    fd = None
    if hasattr(stream, "fileno"):
        try:
            raw_fd = stream.fileno()
            if isinstance(raw_fd, int) and raw_fd >= 0:
                fd = raw_fd
        except Exception:
            fd = None

    buffer = b""
    while True:
        chunk = None
        if fd is not None:
            try:
                chunk = os.read(fd, 1024)
            except Exception:
                fd = None
        if chunk is None:
            try:
                chunk = stream.read(1024)
            except Exception:
                break

        if not chunk:
            break

        if isinstance(chunk, str):
            chunk = chunk.encode("utf-8", errors="replace")

        buffer += chunk
        while b"\r" in buffer or b"\n" in buffer:
            r_idx = buffer.find(b"\r")
            n_idx = buffer.find(b"\n")
            if r_idx != -1 and (n_idx == -1 or r_idx < n_idx):
                line = buffer[:r_idx].decode("utf-8", errors="replace")
                if n_idx == r_idx + 1:
                    buffer = buffer[r_idx + 2 :]
                else:
                    buffer = buffer[r_idx + 1 :]
            else:
                line = buffer[:n_idx].decode("utf-8", errors="replace")
                buffer = buffer[n_idx + 1 :]
            clean = line.rstrip("\r\n")
            if clean:
                yield clean
    rest = buffer.decode("utf-8", errors="replace").rstrip("\r\n")
    if rest:
        yield rest


class Job:
    def __init__(self, job_id: str, request: JobRunRequest):
        self.job_id = job_id
        self.request = request
        self.status = "pending"
        self.current_stage = "Starting"
        self.percent = 0
        self.start_time = time.time()
        self.end_time: Optional[float] = None
        self.output_dir: Optional[str] = None
        self.error: Optional[str] = None
        self.process: Optional[subprocess.Popen] = None
        self.events: deque = deque(maxlen=10000)
        self.event_counter: int = 0
        self.lock = threading.RLock()

    def get_elapsed(self) -> str:
        ref_time = self.end_time if self.end_time else time.time()
        return format_duration(ref_time - self.start_time)

    def to_status_response(self) -> JobStatusResponse:
        return JobStatusResponse(
            job_id=self.job_id,
            status=self.status,
            stage=self.current_stage,
            percent=self.percent,
            elapsed=self.get_elapsed(),
            output_dir=self.output_dir,
            error=self.error,
            started_at=datetime.datetime.fromtimestamp(self.start_time).strftime("%Y-%m-%d %H:%M:%S"),
        )

    def emit(self, event_type: str, data: Dict[str, Any]):
        with self.lock:
            event = {"id": self.event_counter, "event": event_type, "data": data}
            self.event_counter += 1
            self.events.append(event)

    def _initiate_cancel(self) -> Tuple[bool, Optional[subprocess.Popen]]:
        with self.lock:
            if self.status in ("completed", "failed", "cancelled"):
                return False, None
            proc = self.process
            self.status = "cancelled"
            self.error = "Job was cancelled by user"
            self.end_time = time.time()
            now_str = datetime.datetime.now().strftime("%H:%M:%S")
            self.emit("log", {
                "level": "WARN",
                "timestamp": now_str,
                "message": f"Job {self.job_id} cancelled by user",
            })
            self.emit("error", {
                "status": "cancelled",
                "error": "Job was cancelled by user",
            })
            return True, proc

    def _terminate_proc_group(self, proc: subprocess.Popen, sig: int) -> None:
        try:
            import psutil
            parent = psutil.Process(proc.pid)
            children = parent.children(recursive=True)
            for child in children:
                try:
                    if sig == signal.SIGKILL:
                        child.kill()
                    else:
                        child.terminate()
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
        except Exception:
            pass

        try:
            if hasattr(os, "killpg") and hasattr(os, "getpgid"):
                os.killpg(os.getpgid(proc.pid), sig)
            else:
                if sig == signal.SIGKILL:
                    proc.kill()
                else:
                    proc.terminate()
        except (ProcessLookupError, PermissionError, AttributeError):
            try:
                if sig == signal.SIGKILL:
                    proc.kill()
                else:
                    proc.terminate()
            except Exception:
                pass

    def _finalize_cancel(self) -> None:
        self.request.cleanup_temp_files()

    async def cancel(self, timeout: float = 5.0) -> bool:
        cancelled, proc = self._initiate_cancel()
        if not cancelled:
            return False

        if proc and proc.poll() is None:
            self._terminate_proc_group(proc, signal.SIGTERM)

            start_wait = time.time()
            while time.time() - start_wait < timeout:
                if proc.poll() is not None:
                    break
                await asyncio.sleep(0.05)

            if proc.poll() is None:
                self._terminate_proc_group(proc, signal.SIGKILL)

        self._finalize_cancel()
        return True

    def cancel_sync(self, timeout: float = 5.0) -> bool:
        cancelled, proc = self._initiate_cancel()
        if not cancelled:
            return False

        if proc and proc.poll() is None:
            self._terminate_proc_group(proc, signal.SIGTERM)

            start_wait = time.time()
            while time.time() - start_wait < timeout:
                if proc.poll() is not None:
                    break
                time.sleep(0.05)

            if proc.poll() is None:
                self._terminate_proc_group(proc, signal.SIGKILL)

        self._finalize_cancel()
        return True

    async def event_generator(self, cursor: int = 0, ping_interval: float = 15.0):
        import asyncio
        current_cursor = cursor
        last_activity = time.time()
        # Flush initial HTTP headers and bypass proxy/Cloudflare edge buffers immediately
        yield f": stream-open {' ' * 8192}\n\n"
        while True:
            events_to_yield = []
            with self.lock:
                for ev in self.events:
                    ev_id = ev.get("id", 0)
                    if ev_id >= current_cursor:
                        events_to_yield.append(ev)
                if events_to_yield:
                    current_cursor = events_to_yield[-1]["id"] + 1
                is_done = self.status in ("completed", "failed", "cancelled")

            for ev in events_to_yield:
                ev_id = ev.get("id", 0)
                event_name = ev.get("event", "message")
                data_str = json.dumps(ev.get("data", {}))
                yield f"id: {ev_id}\nretry: 3000\nevent: {event_name}\ndata: {data_str}\n\n"
                last_activity = time.time()
                if event_name in ("complete", "error"):
                    return

            if is_done and (not self.events or current_cursor > self.events[-1].get("id", -1)):
                break

            now = time.time()
            if not events_to_yield and (now - last_activity) >= ping_interval:
                yield ": ping\n\n"
                last_activity = now

            if not events_to_yield:
                await asyncio.sleep(0.05)
            else:
                await asyncio.sleep(0)


class JobManager:
    _instance: Optional["JobManager"] = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self):
        if getattr(self, "_initialized", False):
            return
        self.jobs: Dict[str, Job] = {}
        self.active_job: Optional[Job] = None
        self.lock = threading.RLock()
        self._initialized = True

    def is_running(self) -> bool:
        with self.lock:
            return self.active_job is not None and self.active_job.status in ("pending", "running")

    def get_active_job(self) -> Optional[Job]:
        with self.lock:
            if self.active_job and self.active_job.status in ("pending", "running"):
                return self.active_job
            return None

    def get_job(self, job_id: str) -> Optional[Job]:
        with self.lock:
            return self.jobs.get(job_id)

    def start_job(self, request: JobRunRequest) -> Job:
        with self.lock:
            if self.active_job is not None and self.active_job.status in ("pending", "running"):
                raise JobConflictError("A job is currently in progress")

            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            job_id = f"job_{timestamp}"
            job = Job(job_id=job_id, request=request)
            self.jobs[job_id] = job
            self.active_job = job

        threading.Thread(target=self._run_job_process, args=(job,), daemon=True).start()
        return job

    async def cancel_job(self, job_id: str, timeout: float = 5.0) -> bool:
        job = self.get_job(job_id)
        if not job:
            return False
        res = await job.cancel(timeout=timeout)
        with self.lock:
            if self.active_job is job:
                self.active_job = None
        return res

    def cancel_job_sync(self, job_id: str, timeout: float = 5.0) -> bool:
        job = self.get_job(job_id)
        if not job:
            return False
        res = job.cancel_sync(timeout=timeout)
        with self.lock:
            if self.active_job is job:
                self.active_job = None
        return res

    def _run_job_process(self, job: Job):
        try:
            self._execute_job_process(job)
        finally:
            with self.lock:
                if self.active_job is job:
                    self.active_job = None

    def _execute_job_process(self, job: Job):
        work_dir = str(MAIN_SCRIPT_PATH.parent)
        env = os.environ.copy()
        env["PYTHONUNBUFFERED"] = "1"
        env["PYTHONIOENCODING"] = "utf-8"
        if job.request.whisper_batch_size:
            env["VIRALCUTTER_WHISPER_BATCH_SIZE"] = str(int(job.request.whisper_batch_size))
        if job.request.whisper_chunk_size:
            env["VIRALCUTTER_WHISPER_CHUNK_SIZE"] = str(int(job.request.whisper_chunk_size))

        proc = None
        with job.lock:
            if job.status == "cancelled":
                job.request.cleanup_temp_files()
                return

            try:
                cmd = job.request.to_cli_args(
                    python_exec=str(PYTHON_EXECUTABLE),
                    script_path=str(MAIN_SCRIPT_PATH),
                )
            except Exception as e:
                job.status = "failed"
                job.error = str(e)
                job.end_time = time.time()
                job.emit("error", {
                    "status": "failed",
                    "error": str(e),
                })
                job.request.cleanup_temp_files()
                return

            if job.status == "cancelled":
                job.request.cleanup_temp_files()
                return

            job.status = "running"

            now_str = datetime.datetime.now().strftime("%H:%M:%S")
            job.emit("log", {
                "level": "INFO",
                "timestamp": now_str,
                "message": f"Starting job {job.job_id} with command: {' '.join(cmd)}",
            })
            job.emit("progress", {
                "stage": "STARTING",
                "percent": 0,
                "elapsed": "00:00:00",
            })

            try:
                proc = subprocess.Popen(
                    cmd,
                    cwd=work_dir,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    universal_newlines=True,
                    errors="replace",
                    bufsize=1,
                    start_new_session=True,
                    env=env,
                )
                job.process = proc
            except Exception as e:
                job.status = "failed"
                job.error = str(e)
                job.end_time = time.time()
                job.emit("log", {
                    "level": "ERROR",
                    "timestamp": datetime.datetime.now().strftime("%H:%M:%S"),
                    "message": f"Failed to start process: {e}",
                })
                job.emit("error", {
                    "status": "failed",
                    "error": str(e),
                })
                job.request.cleanup_temp_files()
                return

        seen_stages = set()
        detected_output_dir = None

        if proc.stdout is None:
            job.request.cleanup_temp_files()
            return

        try:
            for clean_line in _iter_proc_lines(proc.stdout):
                line_time = datetime.datetime.now().strftime("%H:%M:%S")

                proj_folder = extract_project_folder_from_line(clean_line)
                if proj_folder:
                    detected_output_dir = proj_folder
                    with job.lock:
                        job.output_dir = detected_output_dir

                stage = stage_for_line(clean_line)
                if stage and stage != job.current_stage:
                    with job.lock:
                        job.current_stage = stage
                        stage_idx = STAGE_TO_INDEX.get(stage, 0)
                        job.percent = int((stage_idx / TOTAL_PIPELINE_STAGES) * 100)

                    seen_stages.add(stage)
                    job.emit("progress", {
                        "stage": stage.upper(),
                        "percent": job.percent,
                        "elapsed": job.get_elapsed(),
                    })

                job.emit("log", {
                    "level": "INFO",
                    "timestamp": line_time,
                    "message": clean_line,
                })
        except Exception as e:
            job.emit("log", {
                "level": "ERROR",
                "timestamp": datetime.datetime.now().strftime("%H:%M:%S"),
                "message": f"Error reading output: {e}",
            })
        finally:
            if proc and proc.stdout:
                try:
                    proc.stdout.close()
                except Exception:
                    pass
            if proc:
                ret_code = proc.wait()
            else:
                ret_code = -1
            job.request.cleanup_temp_files()

        with job.lock:
            if job.status == "cancelled":
                return

            job.end_time = time.time()
            if ret_code == 0:
                job.status = "completed"
                job.percent = 100
                job.current_stage = "Completed"
                final_out = job.output_dir or str(VIRALS_DIR)
                job.emit("progress", {
                    "stage": "COMPLETED",
                    "percent": 100,
                    "elapsed": job.get_elapsed(),
                })
                job.emit("complete", {
                    "status": "completed",
                    "output_dir": final_out,
                })
            else:
                job.status = "failed"
                job.error = f"Process exited with non-zero exit code: {ret_code}"
                job.emit("error", {
                    "status": "failed",
                    "error": job.error,
                })


job_manager = JobManager()
