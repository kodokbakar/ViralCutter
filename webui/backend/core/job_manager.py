import datetime
import json
import os
import signal
import subprocess
import threading
import time
from typing import Any, Dict, List, Optional

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
        self.events: List[Dict[str, Any]] = []
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
        event = {"event": event_type, "data": data}
        with self.lock:
            self.events.append(event)

    def cancel(self) -> bool:
        with self.lock:
            if self.status in ("completed", "failed", "cancelled"):
                return False
            proc = self.process
            self.status = "cancelled"
            self.error = "Job was cancelled by user"
            self.end_time = time.time()

        if proc and proc.poll() is None:
            try:
                os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
            except (ProcessLookupError, PermissionError):
                try:
                    proc.terminate()
                except Exception:
                    pass

            start_wait = time.time()
            while time.time() - start_wait < 5.0:
                if proc.poll() is not None:
                    break
                time.sleep(0.1)

            if proc.poll() is None:
                try:
                    os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
                except (ProcessLookupError, PermissionError):
                    try:
                        proc.kill()
                    except Exception:
                        pass

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
        return True

    async def event_generator(self):
        import asyncio
        cursor = 0
        while True:
            events_to_yield = []
            with self.lock:
                while cursor < len(self.events):
                    events_to_yield.append(self.events[cursor])
                    cursor += 1
                is_done = self.status in ("completed", "failed", "cancelled")

            for ev in events_to_yield:
                event_name = ev.get("event", "message")
                data_str = json.dumps(ev.get("data", {}))
                yield f"event: {event_name}\ndata: {data_str}\n\n"
                if event_name in ("complete", "error"):
                    return

            if is_done and cursor >= len(self.events):
                break

            await asyncio.sleep(0.05)


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

    def cancel_job(self, job_id: str) -> bool:
        job = self.get_job(job_id)
        if not job:
            return False
        return job.cancel()

    def _run_job_process(self, job: Job):
        cmd = job.request.to_cli_args(
            python_exec=str(PYTHON_EXECUTABLE),
            script_path=str(MAIN_SCRIPT_PATH),
        )

        work_dir = str(MAIN_SCRIPT_PATH.parent)
        env = os.environ.copy()
        env["PYTHONUNBUFFERED"] = "1"
        if job.request.whisper_batch_size:
            env["VIRALCUTTER_WHISPER_BATCH_SIZE"] = str(int(job.request.whisper_batch_size))
        if job.request.whisper_chunk_size:
            env["VIRALCUTTER_WHISPER_CHUNK_SIZE"] = str(int(job.request.whisper_chunk_size))

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

        with job.lock:
            job.status = "running"

        try:
            proc = subprocess.Popen(
                cmd,
                cwd=work_dir,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                start_new_session=True,
                env=env,
            )
            job.process = proc
        except Exception as e:
            with job.lock:
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
            return

        seen_stages = set()
        detected_output_dir = None

        if proc.stdout is None:
            return

        try:
            for line in iter(proc.stdout.readline, ""):
                if not line and proc.poll() is not None:
                    break

                clean_line = line.rstrip("\r\n")
                if not clean_line:
                    continue

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
            if proc.stdout:
                try:
                    proc.stdout.close()
                except Exception:
                    pass
            ret_code = proc.wait()

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
