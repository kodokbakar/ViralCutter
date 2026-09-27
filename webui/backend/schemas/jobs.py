import json
import tempfile
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class JobRunRequest(BaseModel):
    # Input source options
    input_source: str = Field(default="youtube", description="Input type: youtube, upload, gdrive, existing")
    url: Optional[str] = Field(default=None, description="YouTube URL")
    gdrive_url: Optional[str] = Field(default=None, description="Google Drive URL")
    gdrive_file_id: Optional[str] = Field(default=None, description="Google Drive file ID")
    gdrive_file_name: Optional[str] = Field(default=None, description="Google Drive file name")
    project_name: Optional[str] = Field(default=None, description="Project name for existing project")
    project_path: Optional[str] = Field(default=None, description="Direct project directory path")
    video_path: Optional[str] = Field(default=None, description="Local or uploaded video path")
    video_quality: str = Field(default="best", description="Download video quality")
    skip_youtube_subs: bool = Field(default=False, description="Skip fetching YouTube subtitles")
    translate_target: Optional[str] = Field(default=None, description="Target subtitle translation language")

    # Segmentation & Duration
    segments: int = Field(default=3, description="Number of viral segments")
    viral: bool = Field(default=True, description="Enable viral scoring mode")
    themes: Optional[str] = Field(default=None, description="Comma-separated themes if not viral")
    burn_only: bool = Field(default=False, description="Skip processing and burn subtitles only")
    min_duration: int = Field(default=15, description="Min duration in seconds")
    max_duration: int = Field(default=90, description="Max duration in seconds")
    pre_roll: float = Field(default=1.25, description="Pre-roll seconds")
    post_roll: float = Field(default=0.75, description="Post-roll seconds")
    workflow: str = Field(default="1", description="1=Full, 2=Cut Only, 3=Subtitles Only")

    # Whisper & Audio
    model: str = Field(default="large-v3-turbo", description="Whisper model")
    language: str = Field(default="auto", description="Whisper language code")
    prompt_file: Optional[str] = Field(default=None, description="Path to AI prompt file")
    prompt_template: Optional[str] = Field(default=None, description="Raw text of prompt template override")
    whisper_preset: str = Field(default="custom", description="Preset: fast, balanced, accurate, custom")
    whisper_batch_size: Optional[int] = Field(default=None, description="Whisper batch size override")
    whisper_chunk_size: Optional[int] = Field(default=None, description="Whisper chunk size override")

    # AI backend
    ai_backend: str = Field(default="gemini", description="AI backend: gemini, g4f, local, custom, manual")
    ai_base_url: Optional[str] = Field(default=None, description="Custom AI base URL")
    api_key: Optional[str] = Field(default=None, description="AI API key")
    chunk_size: Optional[int] = Field(default=None, description="Chunk size for LLM input")
    ai_model_name: Optional[str] = Field(default=None, description="Model name override")

    # Smart clipping
    smart_clipping: bool = Field(default=False, description="Enable smart clipping")
    smart_clipping_mode: str = Field(default="splice", description="splice or continuous")
    smart_snap_margin: float = Field(default=0.05, description="Snap margin in seconds")
    smart_remove_dead_air: bool = Field(default=False, description="Jump-cut silence")
    smart_silence_threshold: float = Field(default=0.6, description="Silence threshold in seconds")

    # Face detection & framing
    face_model: str = Field(default="insightface", description="insightface or mediapipe")
    face_mode: str = Field(default="auto", description="auto, 1, 2, none")
    no_face_mode: str = Field(default="padding", description="padding or zoom")
    face_detect_interval: str = Field(default="0.17,1.0", description="Detection interval")
    face_filter_threshold: float = Field(default=0.35, description="Filter threshold")
    face_two_threshold: float = Field(default=0.60, description="Two face threshold")
    face_confidence_threshold: float = Field(default=0.30, description="Confidence threshold")
    face_dead_zone: str = Field(default="40", description="Camera dead zone")
    focus_active_speaker: bool = Field(default=False, description="Focus active speaker")
    active_speaker_mar: float = Field(default=0.03, description="Mouth aspect ratio threshold")
    active_speaker_score_diff: float = Field(default=1.5, description="Score difference")
    include_motion: bool = Field(default=False, description="Include body motion")
    active_speaker_motion_threshold: float = Field(default=3.0, description="Motion threshold")
    active_speaker_motion_sensitivity: float = Field(default=0.05, description="Motion sensitivity")
    active_speaker_decay: float = Field(default=2.0, description="Activity decay rate")

    # Subtitles
    use_custom_subs: bool = Field(default=False, description="Use custom subtitle styling")
    subtitle_config: Optional[Dict[str, Any]] = Field(default=None, description="Subtitle config dictionary")

    # Watermark
    watermark_mode: str = Field(default="disabled", description="disabled, image, text")
    watermark_image: Optional[str] = Field(default=None, description="Watermark image path")
    watermark_text: Optional[str] = Field(default="", description="Watermark text")
    watermark_text_color: Optional[str] = Field(default="#FFFFFF", description="Text color")
    watermark_background_color: Optional[str] = Field(default="#000000", description="Background color")
    watermark_background_opacity: Optional[float] = Field(default=0.35, description="Background opacity")
    watermark_font_size: Optional[int] = Field(default=48, description="Font size")
    watermark_position: Optional[str] = Field(default="top_right", description="Position")
    watermark_scale: Optional[float] = Field(default=12.0, description="Scale percentage")
    watermark_opacity: Optional[float] = Field(default=0.85, description="Opacity 0.0 to 1.0")
    watermark_h_margin: Optional[int] = Field(default=40, description="H margin")
    watermark_v_margin: Optional[int] = Field(default=40, description="V margin")
    watermark_custom_x: Optional[int] = Field(default=40, description="Custom X")
    watermark_custom_y: Optional[int] = Field(default=40, description="Custom Y")
    watermark_start: Optional[float] = Field(default=0.0, description="Start time")
    watermark_end: Optional[float] = Field(default=0.0, description="End time")
    watermark_fade_in: Optional[float] = Field(default=0.5, description="Fade in duration")
    watermark_fade_out: Optional[float] = Field(default=0.5, description="Fade out duration")

    # General / test overrides
    skip_prompts: bool = Field(default=True, description="Always run non-interactively")
    custom_cmd: Optional[List[str]] = Field(default=None, description="Custom command override for testing")

    def to_cli_args(self, python_exec: str, script_path: str) -> List[str]:
        """Convert request to command-line argument list."""
        if self.custom_cmd:
            return self.custom_cmd

        cmd = [python_exec, script_path]

        # Input source
        if self.project_path:
            cmd.extend(["--project-path", str(self.project_path)])
            cmd.append("--skip-youtube-subs")
        elif self.gdrive_file_id:
            cmd.extend(["--gdrive-file-id", str(self.gdrive_file_id)])
            if self.gdrive_file_name:
                cmd.extend(["--gdrive-file-name", str(self.gdrive_file_name)])
            cmd.append("--skip-youtube-subs")
        elif self.gdrive_url:
            cmd.extend(["--gdrive-url", str(self.gdrive_url)])
            cmd.append("--skip-youtube-subs")
        elif self.url:
            cmd.extend(["--url", str(self.url)])
            if self.video_quality:
                cmd.extend(["--video-quality", str(self.video_quality)])
            if self.skip_youtube_subs:
                cmd.append("--skip-youtube-subs")

        if self.translate_target and self.translate_target != "None":
            cmd.extend(["--translate-target", str(self.translate_target)])

        # Segments & Duration
        cmd.extend(["--segments", str(int(self.segments))])
        if self.viral:
            cmd.append("--viral")
        if self.themes:
            cmd.extend(["--themes", str(self.themes)])
        if self.burn_only:
            cmd.append("--burn-only")
        cmd.extend(["--min-duration", str(int(self.min_duration))])
        cmd.extend(["--max-duration", str(int(self.max_duration))])
        cmd.extend(["--pre-roll", str(float(self.pre_roll))])
        cmd.extend(["--post-roll", str(float(self.post_roll))])

        # Workflow
        cmd.extend(["--workflow", str(self.workflow)])

        # Whisper
        cmd.extend(["--model", str(self.model)])
        cmd.extend(["--language", str(self.language)])
        cmd.extend(["--whisper-preset", str(self.whisper_preset)])
        if self.whisper_batch_size:
            cmd.extend(["--whisper-batch-size", str(int(self.whisper_batch_size))])
        if self.whisper_chunk_size:
            cmd.extend(["--whisper-chunk-size", str(int(self.whisper_chunk_size))])

        # AI
        if self.prompt_file:
            cmd.extend(["--prompt-file", str(self.prompt_file)])
        elif self.prompt_template:
            tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8")
            tmp.write(self.prompt_template)
            tmp.close()
            cmd.extend(["--prompt-file", tmp.name])

        cmd.extend(["--ai-backend", str(self.ai_backend)])
        if self.api_key:
            cmd.extend(["--api-key", str(self.api_key)])
        if self.ai_base_url and str(self.ai_base_url).strip():
            cmd.extend(["--ai-base-url", str(self.ai_base_url).strip()])
        if self.ai_model_name:
            cmd.extend(["--ai-model-name", str(self.ai_model_name)])
        if self.chunk_size:
            cmd.extend(["--chunk-size", str(int(self.chunk_size))])

        # Smart clipping
        if self.smart_clipping:
            cmd.append("--smart-clipping")
            cmd.extend(["--smart-clipping-mode", str(self.smart_clipping_mode)])
            cmd.extend(["--smart-snap-margin", str(float(self.smart_snap_margin))])
            if self.smart_remove_dead_air:
                cmd.append("--smart-remove-dead-air")
                cmd.extend(["--smart-silence-threshold", str(float(self.smart_silence_threshold))])

        # Face tracking
        cmd.extend(["--face-model", str(self.face_model)])
        cmd.extend(["--face-mode", str(self.face_mode)])
        cmd.extend(["--no-face-mode", str(self.no_face_mode)])
        if self.face_detect_interval:
            cmd.extend(["--face-detect-interval", str(self.face_detect_interval)])
        if self.face_filter_threshold is not None:
            cmd.extend(["--face-filter-threshold", str(float(self.face_filter_threshold))])
        if self.face_two_threshold is not None:
            cmd.extend(["--face-two-threshold", str(float(self.face_two_threshold))])
        if self.face_confidence_threshold is not None:
            cmd.extend(["--face-confidence-threshold", str(float(self.face_confidence_threshold))])
        if self.face_dead_zone is not None:
            cmd.extend(["--face-dead-zone", str(self.face_dead_zone)])

        if self.focus_active_speaker:
            cmd.append("--focus-active-speaker")
            cmd.extend(["--active-speaker-mar", str(float(self.active_speaker_mar))])
            cmd.extend(["--active-speaker-score-diff", str(float(self.active_speaker_score_diff))])
            if self.include_motion:
                cmd.append("--include-motion")
            cmd.extend(["--active-speaker-motion-threshold", str(float(self.active_speaker_motion_threshold))])
            cmd.extend(["--active-speaker-motion-sensitivity", str(float(self.active_speaker_motion_sensitivity))])
            cmd.extend(["--active-speaker-decay", str(float(self.active_speaker_decay))])

        # Subtitle config
        if self.subtitle_config:
            tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8")
            json.dump(self.subtitle_config, tmp)
            tmp.close()
            cmd.extend(["--subtitle-config", tmp.name])

        # Watermark
        cmd.extend(["--watermark-mode", str(self.watermark_mode)])
        if self.watermark_mode == "image" and self.watermark_image:
            cmd.extend(["--watermark-image", str(self.watermark_image)])
        elif self.watermark_mode == "text" and self.watermark_text:
            cmd.extend([
                "--watermark-text", str(self.watermark_text),
                "--watermark-text-color", str(self.watermark_text_color or "#FFFFFF"),
                "--watermark-background-color", str(self.watermark_background_color or "#000000"),
                "--watermark-background-opacity", str(float(self.watermark_background_opacity or 0.35)),
                "--watermark-font-size", str(int(self.watermark_font_size or 48)),
            ])

        if self.watermark_mode != "disabled":
            cmd.extend([
                "--watermark-position", str(self.watermark_position or "top_right"),
                "--watermark-scale", str(float(self.watermark_scale or 12.0)),
                "--watermark-opacity", str(float(self.watermark_opacity or 0.85)),
                "--watermark-h-margin", str(int(self.watermark_h_margin or 40)),
                "--watermark-v-margin", str(int(self.watermark_v_margin or 40)),
                "--watermark-custom-x", str(int(self.watermark_custom_x or 40)),
                "--watermark-custom-y", str(int(self.watermark_custom_y or 40)),
                "--watermark-start", str(float(self.watermark_start or 0.0)),
                "--watermark-end", str(float(self.watermark_end or 0.0)),
                "--watermark-fade-in", str(float(self.watermark_fade_in or 0.5)),
                "--watermark-fade-out", str(float(self.watermark_fade_out or 0.5)),
            ])

        if self.skip_prompts:
            cmd.append("--skip-prompts")

        return cmd


class JobResponse(BaseModel):
    status: str
    job_id: str
    message: Optional[str] = None


class JobStatusResponse(BaseModel):
    job_id: str
    status: str
    stage: Optional[str] = None
    percent: int = 0
    elapsed: Optional[str] = None
    output_dir: Optional[str] = None
    error: Optional[str] = None
    started_at: Optional[str] = None


class ActiveJobResponse(BaseModel):
    active: bool
    job: Optional[JobStatusResponse] = None
