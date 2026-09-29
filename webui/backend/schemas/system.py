from typing import Any, Dict, Optional
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


class TestAIRequest(BaseModel):
    backend: str = Field(..., description="AI backend: gemini, g4f, local, custom")
    base_url: Optional[str] = Field(default="", description="Base API URL for custom backend")
    api_key: Optional[str] = Field(default="", description="API key")
    model_name: Optional[str] = Field(default="", description="Model name")


class TestAIResponse(BaseModel):
    success: bool = Field(..., description="Whether the connection test succeeded")
    message: str = Field(..., description="Status or error message")
    latency_ms: Optional[int] = Field(default=None, description="Response latency in milliseconds")
