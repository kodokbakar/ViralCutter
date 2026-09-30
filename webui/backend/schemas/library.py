from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ProjectSummary(BaseModel):
    name: str = Field(..., description="Project directory name")
    path: str = Field(..., description="Absolute path to project directory")
    created_at: float = Field(..., description="Creation epoch timestamp")
    modified_at: float = Field(..., description="Modification epoch timestamp")
    video_count: int = Field(default=0, description="Total mp4 videos found in project")
    segment_count: int = Field(default=0, description="Number of viral segments discovered")


class ProjectDetail(BaseModel):
    name: str = Field(..., description="Project directory name")
    path: str = Field(..., description="Absolute path to project directory")
    created_at: float = Field(..., description="Creation epoch timestamp")
    modified_at: float = Field(..., description="Modification epoch timestamp")
    segments: List[Dict[str, Any]] = Field(default_factory=list, description="Parsed viral segments data")
    files: List[str] = Field(default_factory=list, description="List of relative video file paths")


class ProjectRenameRequest(BaseModel):
    new_name: str = Field(..., min_length=1, max_length=100, description="New project name")


class AssetItem(BaseModel):
    name: str = Field(..., description="Asset file name")
    path: str = Field(..., description="Absolute file path")
    size: int = Field(..., description="File size in bytes")
    modified_at: float = Field(..., description="Last modified epoch timestamp")
    asset_type: str = Field(..., description="Asset category: video, subtitle, audio, other")


class ExportResponse(BaseModel):
    zip_path: str = Field(..., description="Path to generated project export zip")
    filename: str = Field(..., description="Filename of zip export")
    size_bytes: int = Field(..., description="Size of exported zip in bytes")


class GeneratedClipItem(BaseModel):
    name: str = Field(..., description="Clip file name")
    path: str = Field(..., description="Absolute file path")
    size: int = Field(..., description="File size in bytes")
    folder_type: str = Field(..., description="Folder source: burned_sub or final")
    score: Optional[float] = Field(default=None, description="AI Virality Score (0-100)")
    hook_title: Optional[str] = Field(default=None, description="AI Hook title or headline")
    duration: Optional[float] = Field(default=None, description="Clip duration in seconds")
