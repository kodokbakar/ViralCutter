import asyncio
import hashlib
import json
from pathlib import Path
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from scripts import broll_engine, broll_renderer
from webui.backend.config import PREVIEWS_DIR

router = APIRouter()


class BrollTemplateResponse(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    default_duration: Optional[float] = 3.5
    sample_data: Optional[Dict[str, Any]] = None


class BrollPreviewRequest(BaseModel):
    template_id: str
    duration: float = Field(default=3.0, gt=0.0, le=15.0, description="Duration in seconds (max 15.0)")
    data: Dict[str, Any] = Field(default_factory=dict)


class BrollPreviewResponse(BaseModel):
    preview_url: str
    file_path: Optional[str] = None


@router.get("/templates", response_model=List[BrollTemplateResponse])
async def get_templates():
    """List available HTML motion graphics templates."""
    try:
        return broll_engine.list_templates()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to load B-roll templates: {e}",
        )


@router.post("/preview", response_model=BrollPreviewResponse)
async def preview_template(req: BrollPreviewRequest):
    """Render a short WebM preview clip for an HTML motion template."""
    try:
        broll_engine.get_template_path(req.template_id)
    except FileNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )

    PREVIEWS_DIR.mkdir(parents=True, exist_ok=True)
    hash_key = hashlib.md5(
        f"{req.template_id}:{req.duration}:{json.dumps(req.data, sort_keys=True)}".encode()
    ).hexdigest()
    out_file = PREVIEWS_DIR / f"broll_preview_{req.template_id}_{hash_key[:12]}.webm"

    try:
        if not out_file.exists() or out_file.stat().st_size == 0:
            await asyncio.to_thread(
                broll_renderer.render_broll_clip,
                req.template_id,
                req.data,
                req.duration,
                str(out_file),
            )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to render B-roll preview: {e}",
        )

    resolved_path = str(out_file.resolve())
    return BrollPreviewResponse(
        preview_url=f"/api/v1/preview/stream?path={resolved_path}",
        file_path=resolved_path,
    )
