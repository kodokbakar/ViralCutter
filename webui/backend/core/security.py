import os
import re
from pathlib import Path
from typing import List, Optional
from fastapi import HTTPException, status

from webui.backend.config import BASE_DIR, PREVIEWS_DIR, UPLOADS_DIR, VIRALS_DIR

DEFAULT_ALLOWED_ROOTS = [
    VIRALS_DIR,
    UPLOADS_DIR,
    PREVIEWS_DIR,
    BASE_DIR / "models",
]


def sanitize_filename(filename: str) -> str:
    """Sanitize filename to prevent directory traversal and illegal characters."""
    if not filename or "\0" in filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid filename: null bytes or empty string",
        )
    norm = filename.replace("\\", "/")
    clean = os.path.basename(norm).strip()
    clean = re.sub(r'[\\/*?:"<>|]', "", clean)
    clean = clean.replace("..", "").strip()
    if not clean:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Filename is invalid after sanitization",
        )
    return clean


def sanitize_project_name(name: str) -> str:
    """Sanitize project folder name to prevent path traversal."""
    if not name or "\0" in name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid project name: null bytes or empty string",
        )
    norm = name.replace("\\", "/")
    clean = os.path.basename(norm).strip()
    clean = re.sub(r"[^a-zA-Z0-9_\-\.]", "_", clean)
    clean = clean.lstrip(".").strip("_")
    if not clean or clean in {".", ".."}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Project name is invalid",
        )
    return clean


def validate_safe_path(
    path_str: str,
    allowed_roots: Optional[List[Path]] = None,
    must_exist: bool = False,
) -> Path:
    """Validate that path resolves within allowed directory boundaries."""
    if not path_str or "\0" in path_str:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid path: null bytes or empty string",
        )

    if allowed_roots is None:
        allowed_roots = DEFAULT_ALLOWED_ROOTS

    resolved_roots = [r.resolve() for r in allowed_roots]

    p = Path(path_str)
    if not p.is_absolute():
        candidate = (VIRALS_DIR / p).resolve()
        if not candidate.exists() and (UPLOADS_DIR / p).resolve().exists():
            candidate = (UPLOADS_DIR / p).resolve()
        elif not candidate.exists() and (PREVIEWS_DIR / p).resolve().exists():
            candidate = (PREVIEWS_DIR / p).resolve()
        target = candidate
    else:
        target = p.resolve()

    is_safe = any(target == root or root in target.parents for root in resolved_roots)
    if not is_safe:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: path is outside allowed directories",
        )

    if must_exist and not target.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Path not found: {target.name}",
        )

    return target
