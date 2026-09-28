from typing import Any, Dict
from pydantic import BaseModel, Field


class SystemStatusResponse(BaseModel):
    status: str = Field(default="ok", description="Overall system health status")
    gpu: Dict[str, Any] = Field(default_factory=dict, description="GPU and CUDA availability metrics")
    disk: Dict[str, Any] = Field(default_factory=dict, description="Disk capacity and usage stats")
    ffmpeg: Dict[str, Any] = Field(default_factory=dict, description="FFmpeg and FFprobe binary status")
    python: Dict[str, Any] = Field(default_factory=dict, description="Python runtime environment details")
    tools: Dict[str, bool] = Field(default_factory=dict, description="AI models and runtime tool availability")


class SystemHealthResponse(BaseModel):
    status: str = Field(default="ok", description="Liveness status")
    timestamp: float = Field(..., description="Server epoch timestamp")
