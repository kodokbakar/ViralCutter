from typing import Optional
from pydantic import BaseModel, Field


class UploadResponse(BaseModel):
    filename: str = Field(..., description="Uploaded file name")
    filepath: str = Field(..., description="Absolute path to saved file")
    size: int = Field(..., description="File size in bytes")
    project_name: Optional[str] = Field(default=None, description="Project folder name if associated")
    chunk_index: Optional[int] = Field(default=None, description="Index of uploaded chunk if chunked")
    completed: bool = Field(default=True, description="Whether entire upload has completed")
