import asyncio
import json
import os
import shutil
from pathlib import Path
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query, status

from webui.backend.config import (
    ALLOWED_SUBTITLE_EXTENSIONS,
    ALLOWED_VIDEO_EXTENSIONS,
    UPLOADS_DIR,
    VIRALS_DIR,
)
from webui.backend.core.security import (
    sanitize_project_name,
    validate_safe_path,
)
from webui.backend.schemas.library import (
    AssetItem,
    ExportResponse,
    ProjectDetail,
    ProjectRenameRequest,
    ProjectSummary,
)
from webui.project_export import build_project_zip

router = APIRouter()


def _get_project_summary_sync(proj_dir: Path) -> ProjectSummary:
    stat = proj_dir.stat()
    created_at = stat.st_ctime
    modified_at = stat.st_mtime

    # Read segment count if viral_segments.txt exists
    segment_count = 0
    seg_file = proj_dir / "viral_segments.txt"
    if seg_file.exists():
        try:
            with open(seg_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                segment_count = len(data.get("segments", []))
        except Exception:
            pass

    # Count videos
    video_count = 0
    for root, _, files in os.walk(proj_dir):
        for f in files:
            if Path(f).suffix.lower() in ALLOWED_VIDEO_EXTENSIONS:
                video_count += 1

    return ProjectSummary(
        name=proj_dir.name,
        path=str(proj_dir.resolve()),
        created_at=created_at,
        modified_at=modified_at,
        video_count=video_count,
        segment_count=segment_count,
    )


@router.get("/projects", response_model=List[ProjectSummary])
async def list_projects():
    """
    List all recent projects with video counts and segment counts, newest first.
    """
    if not VIRALS_DIR.exists():
        return []

    def _scan_all():
        summaries = []
        for item in VIRALS_DIR.iterdir():
            if item.is_dir() and item != UPLOADS_DIR and not item.name.startswith("."):
                try:
                    summaries.append(_get_project_summary_sync(item))
                except Exception:
                    continue
        summaries.sort(key=lambda s: s.modified_at, reverse=True)
        return summaries

    return await asyncio.to_thread(_scan_all)


@router.get("/projects/{project_name}", response_model=ProjectDetail)
async def get_project_detail(project_name: str):
    """
    Retrieve project details, including discovered video files and parsed viral segments.
    """
    safe_name = sanitize_project_name(project_name)
    proj_dir = VIRALS_DIR / safe_name

    if not proj_dir.is_dir():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project '{safe_name}' not found",
        )

    def _get_detail_sync():
        stat = proj_dir.stat()
        segments = []
        seg_file = proj_dir / "viral_segments.txt"
        if seg_file.exists():
            try:
                with open(seg_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    segments = data.get("segments", [])
            except Exception:
                segments = []

        files = []
        for root, _, filenames in os.walk(proj_dir):
            for fname in sorted(filenames):
                if Path(fname).suffix.lower() in ALLOWED_VIDEO_EXTENSIONS:
                    full_p = Path(root) / fname
                    rel_p = full_p.relative_to(proj_dir)
                    files.append(str(rel_p))

        return ProjectDetail(
            name=safe_name,
            path=str(proj_dir.resolve()),
            created_at=stat.st_ctime,
            modified_at=stat.st_mtime,
            segments=segments,
            files=files,
        )

    return await asyncio.to_thread(_get_detail_sync)


@router.patch("/projects/{project_name}")
async def rename_project(project_name: str, body: ProjectRenameRequest):
    """
    Rename an existing project folder safely.
    """
    safe_old = sanitize_project_name(project_name)
    safe_new = sanitize_project_name(body.new_name)

    old_dir = VIRALS_DIR / safe_old
    new_dir = VIRALS_DIR / safe_new

    if not old_dir.is_dir():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project '{safe_old}' not found",
        )

    if new_dir.exists():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"A project named '{safe_new}' already exists",
        )

    await asyncio.to_thread(old_dir.rename, new_dir)
    return {
        "status": "renamed",
        "old_name": safe_old,
        "new_name": safe_new,
        "path": str(new_dir.resolve()),
    }


@router.delete("/projects/{project_name}")
async def delete_project(project_name: str):
    """
    Delete a project and all associated artifacts.
    """
    safe_name = sanitize_project_name(project_name)
    target_dir = VIRALS_DIR / safe_name

    if not target_dir.is_dir():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project '{safe_name}' not found",
        )

    await asyncio.to_thread(shutil.rmtree, target_dir)
    return {
        "status": "deleted",
        "project_name": safe_name,
    }


@router.get("/assets", response_model=List[AssetItem])
async def list_assets(type: Optional[str] = Query(None, description="Filter by type: video, subtitle, audio")):
    """
    List individual media assets found in uploads and projects.
    """
    def _scan_assets_sync():
        assets = []
        scan_dirs = [UPLOADS_DIR, VIRALS_DIR]
        for base_d in scan_dirs:
            if not base_d.exists():
                continue
            for root, _, files in os.walk(base_d):
                for f in files:
                    ext = Path(f).suffix.lower()
                    asset_type = "other"
                    if ext in ALLOWED_VIDEO_EXTENSIONS:
                        asset_type = "video"
                    elif ext in ALLOWED_SUBTITLE_EXTENSIONS:
                        asset_type = "subtitle"
                    elif ext in {".mp3", ".wav", ".aac", ".m4a", ".ogg"}:
                        asset_type = "audio"

                    if type and asset_type != type:
                        continue

                    f_path = Path(root) / f
                    try:
                        f_stat = f_path.stat()
                        assets.append(
                            AssetItem(
                                name=f,
                                path=str(f_path.resolve()),
                                size=f_stat.st_size,
                                modified_at=f_stat.st_mtime,
                                asset_type=asset_type,
                            )
                        )
                    except Exception:
                        continue
        assets.sort(key=lambda a: a.modified_at, reverse=True)
        return assets

    return await asyncio.to_thread(_scan_assets_sync)


@router.delete("/assets")
async def delete_asset(path: str = Query(..., description="File path to media asset to delete")):
    """
    Delete an individual asset file. Path must reside within VIRALS_DIR or UPLOADS_DIR.
    """
    safe_file = validate_safe_path(
        path,
        allowed_roots=[UPLOADS_DIR, VIRALS_DIR],
        must_exist=True,
    )

    if not safe_file.is_file():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Path is not a regular file: {safe_file.name}",
        )

    await asyncio.to_thread(safe_file.unlink)
    return {"status": "deleted", "path": str(safe_file)}


@router.post("/projects/{project_name}/export", response_model=ExportResponse)
async def export_project(project_name: str):
    """
    Build a downloadable ZIP export containing cuts, subtitles, and configuration.
    """
    safe_name = sanitize_project_name(project_name)
    proj_dir = VIRALS_DIR / safe_name

    if not proj_dir.is_dir():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project '{safe_name}' not found",
        )

    try:
        zip_path_str = await asyncio.to_thread(build_project_zip, str(proj_dir))
        zip_p = Path(zip_path_str)
        return ExportResponse(
            zip_path=str(zip_p.resolve()),
            filename=zip_p.name,
            size_bytes=zip_p.stat().st_size,
        )
    except FileNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create project export: {e}",
        )
