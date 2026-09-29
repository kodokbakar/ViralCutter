from typing import Optional
from pydantic import BaseModel, Field


class VideoMetadataResponse(BaseModel):
    width: int = Field(..., description="Video frame width in pixels")
    height: int = Field(..., description="Video frame height in pixels")
    duration: float = Field(..., description="Duration in seconds")
    fps: float = Field(..., description="Frames per second")
    bitrate: Optional[int] = Field(default=None, description="Video bitrate in bps")
    codec: Optional[str] = Field(default=None, description="Video codec name")
    aspect_ratio: Optional[str] = Field(default=None, description="Aspect ratio e.g. 9:16, 16:9")


class ThumbnailRequest(BaseModel):
    path: str = Field(..., description="Video file path")
    timestamp: float = Field(default=1.0, ge=0.0, description="Timestamp in seconds to extract thumbnail")
    width: int = Field(default=540, gt=0, description="Thumbnail width")
    height: int = Field(default=960, gt=0, description="Thumbnail height")


class ThumbnailResponse(BaseModel):
    thumbnail_path: str = Field(..., description="Path to generated thumbnail")
    filename: str = Field(..., description="Thumbnail filename")


class SubtitleVideoPreviewRequest(BaseModel):
    video_path: Optional[str] = Field(default=None, description="Video file path to burn preview on")
    subtitle_config: Optional[dict] = Field(default=None, description="Subtitle style configuration")
    sample_text: str = Field(
        default="The quick brown fox jumps over the lazy dog",
        description="Sample text for preview rendering",
    )
    timestamp: float = Field(default=3.0, ge=0.0, description="Start timestamp in seconds")
    duration: float = Field(default=3.0, gt=0.0, le=10.0, description="Clip duration in seconds")


class SubtitleVideoPreviewResponse(BaseModel):
    preview_url: str = Field(..., description="Streamable preview video URL")
    file_path: str = Field(..., description="Absolute local path to generated preview video")
