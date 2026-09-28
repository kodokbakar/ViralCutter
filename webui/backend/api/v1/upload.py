import asyncio
import os
import shutil
from pathlib import Path
from typing import Optional
from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status

from webui.backend.config import ALLOWED_VIDEO_EXTENSIONS, UPLOADS_DIR, VIRALS_DIR
from webui.backend.core.security import sanitize_filename, sanitize_project_name
from webui.backend.schemas.upload import UploadResponse

router = APIRouter()


def _write_file_sync(source_file, target_path: Path):
    with open(target_path, "wb") as buffer:
        shutil.copyfileobj(source_file, buffer)


def _assemble_chunks_sync(staging_dir: Path, target_path: Path, total_chunks: int):
    with open(target_path, "wb") as outfile:
        for idx in range(total_chunks):
            chunk_file = staging_dir / f"chunk_{idx:05d}"
            if not chunk_file.exists():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Missing chunk {idx} in staging upload",
                )
            with open(chunk_file, "rb") as infile:
                shutil.copyfileobj(infile, outfile)
    shutil.rmtree(staging_dir, ignore_errors=True)


@router.post("", response_model=UploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_file(
    file: UploadFile = File(...),
    project_name: Optional[str] = Form(None),
    chunk_index: Optional[int] = Form(None),
    total_chunks: Optional[int] = Form(None),
    upload_id: Optional[str] = Form(None),
):
    """
    Upload video file using standard multipart or chunked upload.
    Validates video extensions and stores file securely under UPLOADS_DIR or project dir.
    """
    orig_name = file.filename or "uploaded_video.mp4"
    safe_name = sanitize_filename(orig_name)
    ext = Path(safe_name).suffix.lower()

    if ext not in ALLOWED_VIDEO_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported video format: '{ext}'. Allowed formats: {sorted(list(ALLOWED_VIDEO_EXTENSIONS))}",
        )

    if project_name:
        safe_proj = sanitize_project_name(project_name)
        dest_dir = VIRALS_DIR / safe_proj
    else:
        dest_dir = UPLOADS_DIR

    await asyncio.to_thread(dest_dir.mkdir, parents=True, exist_ok=True)

    # Chunked upload flow
    if chunk_index is not None and total_chunks is not None and upload_id:
        if chunk_index < 0 or total_chunks <= 0 or chunk_index >= total_chunks:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid chunk index {chunk_index} for total_chunks {total_chunks}",
            )

        safe_uid = sanitize_filename(upload_id)
        staging_dir = dest_dir / f".staging_{safe_uid}"
        await asyncio.to_thread(staging_dir.mkdir, parents=True, exist_ok=True)

        chunk_path = staging_dir / f"chunk_{chunk_index:05d}"
        await asyncio.to_thread(_write_file_sync, file.file, chunk_path)

        existing_chunks = len(list(staging_dir.glob("chunk_*")))
        if existing_chunks >= total_chunks:
            target_path = dest_dir / safe_name
            await asyncio.to_thread(_assemble_chunks_sync, staging_dir, target_path, total_chunks)
            size = target_path.stat().st_size
            return UploadResponse(
                filename=safe_name,
                filepath=str(target_path.resolve()),
                size=size,
                project_name=project_name,
                chunk_index=chunk_index,
                completed=True,
            )

        return UploadResponse(
            filename=safe_name,
            filepath="",
            size=0,
            project_name=project_name,
            chunk_index=chunk_index,
            completed=False,
        )

    # Standard single multipart upload
    target_path = dest_dir / safe_name
    await asyncio.to_thread(_write_file_sync, file.file, target_path)
    size = target_path.stat().st_size

    return UploadResponse(
        filename=safe_name,
        filepath=str(target_path.resolve()),
        size=size,
        project_name=project_name,
        completed=True,
    )
