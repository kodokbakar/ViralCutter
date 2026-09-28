import asyncio
import os
import shutil
from pathlib import Path
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query, status

try:
    from scripts.gdrive_client import (
        CREDENTIALS_PATH,
        TOKEN_PATH,
        download_drive_video,
        format_size,
        is_colab_runtime,
        list_drive_videos as list_oauth_drive_videos,
    )
except ImportError:
    from webui.backend.config import BASE_DIR
    CREDENTIALS_PATH = str(BASE_DIR / "credentials.json")
    TOKEN_PATH = str(BASE_DIR / "token_drive.json")
    download_drive_video = None
    list_oauth_drive_videos = None

    def format_size(size):
        if not size:
            return "unknown size"
        size = int(size)
        for unit in ["B", "KB", "MB", "GB"]:
            if size < 1024:
                return f"{size:.1f} {unit}" if unit != "B" else f"{size} {unit}"
            size /= 1024
        return f"{size:.1f} TB"
from webui.backend.config import UPLOADS_DIR, VIRALS_DIR
from webui.backend.core.security import sanitize_filename, sanitize_project_name, validate_safe_path
from webui.backend.schemas.gdrive import (
    GDriveExportRequest,
    GDriveExportResponse,
    GDriveImportRequest,
    GDriveImportResponse,
    GDriveStatusResponse,
    GDriveVideoItem,
)
import webui.drive_browser as drive_browser
from webui.drive_browser import (
    DRIVE_ROOT,
    is_colab_drive_available,
    list_drive_videos as list_colab_drive_videos,
)
from webui.project_export import build_project_zip

router = APIRouter()


def _validate_drive_path(path_str: str) -> Path:
    if not path_str or "\0" in path_str:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid drive path: empty string or null byte",
        )
    target = Path(path_str).resolve()
    current_drive_root = Path(getattr(drive_browser, "DRIVE_ROOT", DRIVE_ROOT)).resolve()
    allowed_roots = [current_drive_root, Path("/content/drive").resolve()]
    if not any(target == r or r in target.parents for r in allowed_roots):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: path is outside allowed Google Drive mount boundary",
        )
    return target


@router.get("/status", response_model=GDriveStatusResponse)
async def get_gdrive_status():
    """
    Check availability and mode of Google Drive integration (Colab FUSE mount vs OAuth API).
    """
    if is_colab_drive_available():
        return GDriveStatusResponse(
            available=True,
            mode="colab_mount",
            message="Google Drive mounted via Colab (/content/drive/MyDrive)",
        )

    if os.path.exists(TOKEN_PATH) or os.path.exists(CREDENTIALS_PATH):
        return GDriveStatusResponse(
            available=True,
            mode="oauth",
            message="Google Drive API credentials configured",
        )

    return GDriveStatusResponse(
        available=False,
        mode="unconfigured",
        message="Google Drive is not mounted and no credentials.json / token_drive.json was found",
    )


@router.get("/videos", response_model=List[GDriveVideoItem])
async def list_videos(
    query: str = Query("", description="Optional search filter for video filename"),
    limit: int = Query(50, ge=1, le=200, description="Max videos to return"),
    force_refresh: bool = Query(False, description="Bypass cache and force rescanning"),
):
    """
    List video files available on Google Drive.
    """
    if is_colab_drive_available():
        def _get_colab_videos():
            try:
                pairs = list_colab_drive_videos(search_query=query, limit=limit, force_refresh=force_refresh)
                items = []
                for label, full_path in pairs:
                    fname = os.path.basename(full_path)
                    try:
                        sz = os.path.getsize(full_path)
                    except OSError:
                        sz = None
                    items.append(
                        GDriveVideoItem(
                            id=full_path,
                            name=fname,
                            size=sz,
                            size_formatted=format_size(sz) if sz else "unknown size",
                            path=full_path,
                        )
                    )
                return items
            except Exception as e:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to scan Colab Drive: {e}",
                )

        return await asyncio.to_thread(_get_colab_videos)

    if os.path.exists(TOKEN_PATH) or os.path.exists(CREDENTIALS_PATH):
        if list_oauth_drive_videos is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Google Drive client library (google-api-python-client) is not installed",
            )

        def _get_oauth_videos():
            try:
                files = list_oauth_drive_videos(search_query=query, page_size=limit)
                items = []
                for f in files:
                    sz = int(f.get("size")) if f.get("size") else None
                    items.append(
                        GDriveVideoItem(
                            id=f["id"],
                            name=f.get("name", "Untitled"),
                            size=sz,
                            size_formatted=format_size(sz),
                            modified_time=f.get("modifiedTime"),
                            path=None,
                        )
                    )
                return items
            except Exception as e:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to query Drive API: {e}",
                )

        return await asyncio.to_thread(_get_oauth_videos)

    # Not configured
    return []


@router.post("/import", response_model=GDriveImportResponse)
async def import_drive_video(request: GDriveImportRequest):
    """
    Import video from Google Drive into project directory or uploads folder.
    """
    if not request.file_id and not request.file_path:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Either file_id or file_path must be provided",
        )

    # Colab filesystem path import
    if request.file_path:
        src_path = _validate_drive_path(request.file_path)
        if not src_path.is_file():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"File not found on drive mount: {src_path.name}",
            )

        safe_name = sanitize_filename(src_path.name)
        if request.project_name:
            safe_proj = sanitize_project_name(request.project_name)
            target_dir = VIRALS_DIR / safe_proj
        else:
            target_dir = UPLOADS_DIR

        await asyncio.to_thread(target_dir.mkdir, parents=True, exist_ok=True)
        dest_path = target_dir / safe_name

        def _copy_sync():
            shutil.copy2(src_path, dest_path)

        await asyncio.to_thread(_copy_sync)
        return GDriveImportResponse(
            status="imported",
            video_path=str(dest_path.resolve()),
            project_folder=str(target_dir.resolve()),
        )

    # OAuth file download
    if request.file_id:
        if download_drive_video is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Google Drive client library (google-api-python-client) is not installed",
            )
        try:
            video_path, project_folder = await asyncio.to_thread(
                download_drive_video,
                file_id=request.file_id,
                base_root=str(VIRALS_DIR),
            )
            return GDriveImportResponse(
                status="imported",
                video_path=video_path,
                project_folder=project_folder,
            )
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Drive download failed: {e}",
            )


@router.post("/export", response_model=GDriveExportResponse)
async def export_to_drive(request: GDriveExportRequest):
    """
    Export project artifacts to Google Drive directory.
    """
    safe_proj = sanitize_project_name(request.project_name)
    proj_dir = VIRALS_DIR / safe_proj

    if not proj_dir.is_dir():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project '{safe_proj}' not found",
        )

    # Build zip export
    zip_path_str = await asyncio.to_thread(build_project_zip, str(proj_dir))
    zip_path = Path(zip_path_str)

    # If Colab drive available, copy to destination
    if is_colab_drive_available():
        dest_folder_str = request.destination_folder or "/content/drive/MyDrive/ViralCutter_Exports"
        dest_dir = _validate_drive_path(dest_folder_str)
        await asyncio.to_thread(dest_dir.mkdir, parents=True, exist_ok=True)
        dest_file = dest_dir / zip_path.name
        await asyncio.to_thread(shutil.copy2, zip_path, dest_file)
        return GDriveExportResponse(
            status="exported",
            destination=str(dest_file.resolve()),
        )

    # Otherwise return local export path
    return GDriveExportResponse(
        status="exported_local",
        destination=str(zip_path.resolve()),
    )
