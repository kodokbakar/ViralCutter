from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class SubtitleItem(BaseModel):
    index: int = Field(default=1, description="1-indexed sequence number")
    start: float = Field(..., ge=0.0, description="Start timestamp in seconds")
    end: float = Field(..., ge=0.0, description="End timestamp in seconds")
    text: str = Field(..., description="Subtitle text content")


class SubtitleParseRequest(BaseModel):
    content: Optional[str] = Field(default=None, description="Raw subtitle content string (SRT, VTT, or Whisper JSON)")
    file_path: Optional[str] = Field(default=None, description="Path to subtitle file on disk")
    format: Optional[str] = Field(default=None, description="Optional explicit format override: srt, vtt, json")


class SubtitleParseResponse(BaseModel):
    format: str = Field(..., description="Detected format: srt, vtt, json")
    entries: List[SubtitleItem] = Field(default_factory=list, description="Parsed subtitle entries")
    count: int = Field(..., description="Total number of entries parsed")


class SubtitleConvertRequest(BaseModel):
    content: Optional[str] = Field(default=None, description="Raw subtitle content string")
    file_path: Optional[str] = Field(default=None, description="Path to subtitle file on disk")
    source_format: Optional[str] = Field(default=None, description="Optional source format hint")
    target_format: str = Field(default="vtt", description="Target format: srt, vtt, ass")


class SubtitleConvertResponse(BaseModel):
    content: str = Field(..., description="Converted subtitle string")
    target_format: str = Field(..., description="Format converted to")
    count: int = Field(..., description="Number of cues in converted subtitle")


class SubtitleSaveRequest(BaseModel):
    project_name: Optional[str] = Field(default=None, description="Project directory name to save into")
    file_path: Optional[str] = Field(default=None, description="Direct file path override")
    entries: List[SubtitleItem] = Field(..., description="Subtitle entries to persist")
    format: str = Field(default="srt", description="Target file format: srt, vtt, ass")
    filename: Optional[str] = Field(default=None, description="Filename override e.g. custom.srt")


class SubtitleSaveResponse(BaseModel):
    status: str = Field(default="saved", description="Operation status")
    file_path: str = Field(..., description="Path where subtitle file was written")
    count: int = Field(..., description="Number of entries saved")


class SubtitleStylePreviewRequest(BaseModel):
    font: str = Field(default="Montserrat-ExtraBold", description="Font name/id")
    size: int = Field(default=32, description="Base font size")
    color: str = Field(default="#FFFFFF", description="Base text hex color")
    highlight_color: str = Field(default="#FFD700", description="Active word highlight color")
    outline_color: str = Field(default="#000000", description="Outline hex color")
    outline_thickness: int = Field(default=3, description="Outline thickness in pixels")
    shadow_color: str = Field(default="#000000", description="Shadow hex color")
    shadow_size: int = Field(default=2, description="Shadow offset/blur size")
    bold: bool = Field(default=True, description="Bold text")
    italic: bool = Field(default=False, description="Italic text")
    uppercase: bool = Field(default=True, description="Force uppercase text")
    highlight_size: int = Field(default=38, description="Highlighted word font size")
    words_per_block: int = Field(default=3, description="Words shown per subtitle block")
    gap_limit: float = Field(default=0.25, description="Max silence gap before breaking block")
    mode: str = Field(default="highlight", description="Subtitle animation mode: highlight, word_by_word, no_highlight")
    underline: bool = Field(default=False, description="Underline text")
    strikeout: bool = Field(default=False, description="Strikeout text")
    border_style: int = Field(default=1, description="Border style: 1=Outline+drop shadow, 3=Opaque box")
    vertical_position: int = Field(default=180, description="Vertical position from bottom in pixels")
    alignment: int = Field(default=2, description="ASS alignment code (2=bottom center)")
    remove_punctuation: bool = Field(default=True, description="Strip punctuation marks")


class SubtitleStylePreviewResponse(BaseModel):
    html: str = Field(..., description="Rendered HTML preview fragment")


class SubtitlePresetsResponse(BaseModel):
    presets: Dict[str, Any] = Field(..., description="Predefined subtitle styling presets")
