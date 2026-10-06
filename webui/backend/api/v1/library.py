import asyncio
import json
import os
import re
import shutil
from pathlib import Path
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import FileResponse

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
    GeneratedClipItem,
    ProjectDetail,
    ProjectRenameRequest,
    ProjectSummary,
)
from webui.project_export import build_project_zip

router = APIRouter()


def _is_protected_project_dir(target_dir: Path, name: str) -> bool:
    clean = name.strip().lower()
    if clean in {"uploads", ".", ".."}:
        return True
    try:
        resolved = target_dir.resolve()
        if resolved in {VIRALS_DIR.resolve(), UPLOADS_DIR.resolve()}:
            return True
    except Exception:
        pass
    return False


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

    if _is_protected_project_dir(proj_dir, safe_name) or not proj_dir.is_dir():
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


def _probe_duration_sync(file_path: Path) -> Optional[float]:
    try:
        ffprobe_bin = shutil.which("ffprobe")
        if not ffprobe_bin:
            return None
        import subprocess
        res = subprocess.run(
            [
                ffprobe_bin,
                "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                str(file_path),
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=3,
        )
        if res.returncode == 0 and res.stdout.strip():
            return round(float(res.stdout.strip()), 2)
    except Exception:
        pass
    return None


def _get_project_clips_sync(proj_dir: Path) -> List[GeneratedClipItem]:
    # 1. Primary: burned_sub/
    burned_dir = proj_dir / "burned_sub"
    burned_files = []
    if burned_dir.is_dir():
        burned_files = [
            p for p in burned_dir.iterdir()
            if p.is_file()
            and p.suffix.lower() in ALLOWED_VIDEO_EXTENSIONS
            and "input" not in p.name.lower()
        ]

    if not burned_files:
        return []

    folder_type = "burned_sub"
    selected_files = sorted(burned_files, key=lambda p: p.name)

    # 2. Read viral segments metadata
    segments_list = []
    for s_dir in [proj_dir, proj_dir / "smart_clips", proj_dir / "cuts", proj_dir / "final"]:
        for seg_candidate in ["viral_segments.json", "viral_segments.txt"]:
            seg_file = s_dir / seg_candidate
            if seg_file.is_file():
                try:
                    with open(seg_file, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    if isinstance(data, dict) and isinstance(data.get("segments"), list):
                        segments_list = data["segments"]
                        break
                    elif isinstance(data, list):
                        segments_list = data
                        break
                except Exception:
                    pass
        if segments_list:
            break

    clips: List[GeneratedClipItem] = []
    for i, clip_file in enumerate(selected_files):
        fname = clip_file.name
        stem = clip_file.stem
        clean_stem = re.sub(r'(_subtitled|_processed|_original_scale)+$', '', stem, flags=re.IGNORECASE)

        # Timeline lookup
        hook_from_timeline = None
        for tl_dir in [proj_dir / "final", proj_dir / "burned_sub", proj_dir]:
            for tl_name in [f"{clean_stem}_timeline.json", f"{stem}_timeline.json"]:
                tl_p = tl_dir / tl_name
                if tl_p.is_file():
                    try:
                        with open(tl_p, "r", encoding="utf-8") as tf:
                            tl_data = json.load(tf)
                        if isinstance(tl_data, list):
                            for item in tl_data:
                                if isinstance(item, dict) and item.get("hook_title"):
                                    hook_from_timeline = str(item["hook_title"]).strip()
                                    break
                        elif isinstance(tl_data, dict) and tl_data.get("hook_title"):
                            hook_from_timeline = str(tl_data["hook_title"]).strip()
                        if hook_from_timeline:
                            break
                    except Exception:
                        pass
            if hook_from_timeline:
                break

        # Match segment
        matched_seg = None
        for seg in segments_list:
            if isinstance(seg, dict):
                sf = seg.get("filename") or seg.get("filepath") or seg.get("smart_clip_path")
                if sf and (sf == fname or Path(sf).name == fname or Path(sf).stem == clean_stem or Path(sf).stem == stem):
                    matched_seg = seg
                    break

        if not matched_seg:
            for seg in segments_list:
                if isinstance(seg, dict):
                    t = str(seg.get("title") or seg.get("hook_title") or "").strip()
                    if t:
                        safe_t = re.sub(r'[^\w\s]', '', t).replace(' ', '_').lower()
                        if safe_t and (safe_t in stem.lower() or stem.lower() in safe_t):
                            matched_seg = seg
                            break

        if not matched_seg:
            idx_match = re.search(r'(?:output|segment|clip|_|^)(\d+)', stem, re.IGNORECASE)
            if not idx_match:
                idx_match = re.search(r'(\d+)', stem)
            if idx_match:
                idx_num = int(idx_match.group(1))
                if 0 <= idx_num < len(segments_list) and isinstance(segments_list[idx_num], dict):
                    matched_seg = segments_list[idx_num]
                elif 0 <= (idx_num - 1) < len(segments_list) and isinstance(segments_list[idx_num - 1], dict):
                    matched_seg = segments_list[idx_num - 1]

        if not matched_seg and i < len(segments_list) and isinstance(segments_list[i], dict):
            matched_seg = segments_list[i]

        score = None
        hook_title = hook_from_timeline
        duration = None

        if matched_seg:
            raw_score = (
                matched_seg.get("score")
                or matched_seg.get("virality_score")
                or matched_seg.get("rating")
                or matched_seg.get("ai_rating")
            )
            if raw_score is not None:
                try:
                    if isinstance(raw_score, str):
                        raw_clean = re.sub(r'[^\d.]', '', raw_score.split('/')[0])
                        score = float(raw_clean)
                    else:
                        score = float(raw_score)
                except (ValueError, TypeError):
                    score = None
            if not hook_title:
                cand_title = matched_seg.get("hook_title") or matched_seg.get("title")
                if cand_title:
                    hook_title = str(cand_title).strip()

            dur_cand = matched_seg.get("duration")
            if dur_cand is not None:
                try:
                    duration = float(dur_cand)
                except (ValueError, TypeError):
                    pass
            if duration is None:
                st = matched_seg.get("start_time") or matched_seg.get("start")
                et = matched_seg.get("end_time") or matched_seg.get("end")
                if st is not None and et is not None:
                    try:
                        duration = round(float(et) - float(st), 2)
                    except (ValueError, TypeError):
                        pass

        if duration is None:
            duration = _probe_duration_sync(clip_file)

        clips.append(
            GeneratedClipItem(
                name=fname,
                path=str(clip_file.resolve()),
                size=clip_file.stat().st_size,
                folder_type=folder_type,
                score=score,
                hook_title=hook_title,
                duration=duration,
            )
        )

    return clips


@router.get("/projects/{project_name}/clips", response_model=List[GeneratedClipItem])
async def get_project_clips(project_name: str):
    """
    List generated output video clips for a project, prioritized from burned_sub/
    with automatic fallback to final/. Intermediate cuts/ and input.mp4 are excluded.
    Extracts AI virality score and hook title metadata from viral_segments / timeline files.
    """
    safe_name = sanitize_project_name(project_name)
    proj_dir = VIRALS_DIR / safe_name

    if _is_protected_project_dir(proj_dir, safe_name) or not proj_dir.is_dir():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project '{safe_name}' not found",
        )

    return await asyncio.to_thread(_get_project_clips_sync, proj_dir)


@router.patch("/projects/{project_name}")
async def rename_project(project_name: str, body: ProjectRenameRequest):
    """
    Rename an existing project folder safely.
    """
    safe_old = sanitize_project_name(project_name)
    safe_new = sanitize_project_name(body.new_name)

    old_dir = VIRALS_DIR / safe_old
    new_dir = VIRALS_DIR / safe_new

    if _is_protected_project_dir(old_dir, safe_old):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot rename protected system directory '{safe_old}'",
        )

    if _is_protected_project_dir(new_dir, safe_new):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot rename project to protected system directory name '{safe_new}'",
        )

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

    if _is_protected_project_dir(target_dir, safe_name):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot delete protected system directory '{safe_name}'",
        )

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
async def list_assets(
    type: Optional[str] = Query(None, description="Filter by type: video, subtitle, audio"),
    project_name: Optional[str] = Query(None, description="Filter by project name"),
):
    """
    List individual media assets found in uploads and projects.
    """
    def _scan_assets_sync():
        assets = []
        if project_name:
            safe_proj = sanitize_project_name(project_name)
            proj_d = VIRALS_DIR / safe_proj
            scan_dirs = [proj_d] if proj_d.is_dir() else []
        else:
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
async def delete_asset(
    path: Optional[str] = Query(None, description="File path to media asset to delete"),
    file_path: Optional[str] = Query(None, description="File path to media asset to delete"),
):
    """
    Delete an individual asset file. Path must reside within VIRALS_DIR or UPLOADS_DIR.
    """
    target_str = file_path or path
    if not target_str:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing path or file_path query parameter",
        )

    safe_file = validate_safe_path(
        target_str,
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


@router.get("/export/download")
async def download_export(
    path: Optional[str] = Query(None, description="File path to project export ZIP"),
    file_path: Optional[str] = Query(None, description="File path to project export ZIP"),
):
    """
    Download a generated project ZIP export safely.
    Path must reside within VIRALS_DIR and have a .zip extension.
    """
    target_str = file_path or path
    if not target_str:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing path or file_path query parameter",
        )

    safe_file = validate_safe_path(
        target_str,
        allowed_roots=[VIRALS_DIR],
        must_exist=True,
    )

    if not safe_file.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Export file not found: {safe_file.name}",
        )

    if safe_file.suffix.lower() != ".zip":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Requested file is not a valid zip archive",
        )

    return FileResponse(
        path=safe_file,
        filename=safe_file.name,
        media_type="application/zip",
    )


@router.post("/projects/{project_name}/export", response_model=ExportResponse)
async def export_project(project_name: str):
    """
    Build a downloadable ZIP export containing cuts, subtitles, and configuration.
    """
    safe_name = sanitize_project_name(project_name)
    proj_dir = VIRALS_DIR / safe_name

    if _is_protected_project_dir(proj_dir, safe_name) or not proj_dir.is_dir():
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
