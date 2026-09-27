from fastapi import APIRouter, HTTPException, status
from fastapi.responses import StreamingResponse

from webui.backend.core.job_manager import JobConflictError, job_manager
from webui.backend.schemas.jobs import (
    ActiveJobResponse,
    JobResponse,
    JobRunRequest,
    JobStatusResponse,
)

router = APIRouter()


@router.post("/run", response_model=JobResponse, status_code=status.HTTP_200_OK)
async def run_job(request: JobRunRequest):
    """Trigger video processing job with single-job lock."""
    try:
        job = job_manager.start_job(request)
        return JobResponse(status="started", job_id=job.job_id)
    except JobConflictError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e) or "A job is currently in progress",
        )


@router.get("/active", response_model=ActiveJobResponse)
async def get_active_job():
    """Get currently active job status if running."""
    active_job = job_manager.get_active_job()
    if active_job:
        return ActiveJobResponse(active=True, job=active_job.to_status_response())
    return ActiveJobResponse(active=False, job=None)


@router.get("/{job_id}/stream")
async def stream_job_logs(job_id: str):
    """Server-Sent Events (SSE) stream for logs and progress events."""
    job = job_manager.get_job(job_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job {job_id} not found",
        )

    return StreamingResponse(
        job.event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/{job_id}/cancel")
async def cancel_job(job_id: str):
    """Cancel a running job."""
    job = job_manager.get_job(job_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job {job_id} not found",
        )

    job_manager.cancel_job(job_id)
    return {"status": "cancelled", "job_id": job_id}


@router.get("/{job_id}", response_model=JobStatusResponse)
async def get_job_status(job_id: str):
    """Get metadata and status of a specific job."""
    job = job_manager.get_job(job_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job {job_id} not found",
        )
    return job.to_status_response()
