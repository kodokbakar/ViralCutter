from typing import Optional
from pydantic import BaseModel, Field


class GDriveStatusResponse(BaseModel):
    available: bool = Field(..., description="Whether Google Drive integration is available")
    mode: str = Field(..., description="Integration mode: colab_mount, oauth, or unconfigured")
    message: str = Field(..., description="Detailed status description or instruction")


class GDriveVideoItem(BaseModel):
    id: str = Field(..., description="Drive file ID or relative path identifier")
    name: str = Field(..., description="Display file name")
    size: Optional[int] = Field(default=None, description="Size in bytes if known")
    size_formatted: str = Field(default="unknown size", description="Human-readable file size")
    modified_time: Optional[str] = Field(default=None, description="Last modification timestamp")
    path: Optional[str] = Field(default=None, description="Direct filesystem path if Colab mounted")


class GDriveImportRequest(BaseModel):
    file_id: Optional[str] = Field(default=None, description="Google Drive file ID for OAuth mode")
    file_path: Optional[str] = Field(default=None, description="Filesystem path if mounted via Colab")
    project_name: Optional[str] = Field(default=None, description="Optional target project folder name")


class GDriveImportResponse(BaseModel):
    status: str = Field(default="imported", description="Import result status")
    video_path: str = Field(..., description="Local path to staged video")
    project_folder: str = Field(..., description="Target project folder path")


class GDriveExportRequest(BaseModel):
    project_name: str = Field(..., description="Project name to export to Drive")
    destination_folder: Optional[str] = Field(default=None, description="Drive destination folder path")


class GDriveExportResponse(BaseModel):
    status: str = Field(default="exported", description="Export status")
    destination: str = Field(..., description="Drive destination path where export was copied")
