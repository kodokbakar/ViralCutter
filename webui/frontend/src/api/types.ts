/**
 * TypeScript API contracts for ViralCutter FastAPI backend.
 * Synchronized with webui/backend/schemas/.
 */

// Job schemas
export type JobInputSource = 'youtube' | 'upload' | 'gdrive' | 'existing';
export type JobStatus = 'queued' | 'running' | 'completed' | 'failed' | 'cancelled';

export interface JobRunRequest {
  input_source?: JobInputSource;
  url?: string;
  gdrive_url?: string;
  gdrive_file_id?: string;
  gdrive_file_name?: string;
  project_name?: string;
  project_path?: string;
  video_path?: string;
  video_quality?: string;
  skip_youtube_subs?: boolean;
  translate_target?: string;

  // Segmentation & Duration
  segments?: number;
  viral?: boolean;
  themes?: string;
  burn_only?: boolean;
  min_duration?: number;
  max_duration?: number;
  pre_roll?: number;
  post_roll?: number;
  workflow?: string;

  // Whisper & Audio
  model?: string;
  language?: string;
  prompt_file?: string;
  prompt_template?: string;
  whisper_preset?: string;
  whisper_batch_size?: number;
  whisper_chunk_size?: number;

  // AI backend
  ai_backend?: 'gemini' | 'g4f' | 'local' | 'custom' | 'manual' | string;
  ai_base_url?: string;
  api_key?: string;
  chunk_size?: number;
  ai_model_name?: string;

  // Smart clipping
  smart_clipping?: boolean;
  smart_clipping_mode?: 'splice' | 'continuous';
  smart_snap_margin?: number;
  smart_remove_dead_air?: boolean;
  smart_silence_threshold?: number;

  // Face detection & framing
  face_model?: 'insightface' | 'mediapipe' | string;
  face_mode?: 'auto' | '1' | '2' | 'none' | string;
  no_face_mode?: 'padding' | 'zoom' | string;
  face_detect_interval?: string;
  face_filter_threshold?: number;
  face_two_threshold?: number;
  face_confidence_threshold?: number;
  face_dead_zone?: string;
  focus_active_speaker?: boolean;

  // Subtitles
  use_custom_subs?: boolean;
  subtitle_config?: Record<string, unknown>;

  // Watermark
  watermark_mode?: 'disabled' | 'image' | 'text';
  watermark_image?: string;
  watermark_text?: string;
  watermark_text_color?: string;
  watermark_background_color?: string;
  watermark_background_opacity?: number;
  watermark_font_size?: number;
  watermark_position?: string;
  watermark_scale?: number;
  watermark_opacity?: number;
  watermark_h_margin?: number;
  watermark_v_margin?: number;

  // Overrides
  skip_prompts?: boolean;
  custom_cmd?: string[];
}

export interface JobResponse {
  job_id: string;
  status: JobStatus;
  command: string[];
  started_at: number;
  ended_at: number | null;
  return_code: number | null;
  error: string | null;
  log_tail: string[];
}

export interface ActiveJobResponse {
  has_active_job: boolean;
  job: JobResponse | null;
}

export interface JobStatusResponse {
  job_id: string;
  status: JobStatus;
  started_at: number;
  ended_at: number | null;
  return_code: number | null;
  error: string | null;
  log_tail: string[];
}

// Upload schemas
export interface UploadResponse {
  filename: string;
  filepath: string;
  size: number;
  project_name?: string | null;
  chunk_index?: number | null;
  completed: boolean;
}

// Preview schemas
export interface VideoMetadata {
  width: number;
  height: number;
  duration: number;
  fps: number;
  bitrate?: number | null;
  codec?: string | null;
  aspect_ratio?: string | null;
}

export interface ThumbnailRequest {
  path: string;
  timestamp?: number;
  width?: number;
  height?: number;
}

export interface ThumbnailResponse {
  thumbnail_path: string;
  filename: string;
}

// Library schemas
export interface ProjectSummary {
  name: string;
  path: string;
  created_at: number;
  modified_at: number;
  video_count: number;
  segment_count: number;
}

export interface ProjectDetail {
  name: string;
  path: string;
  created_at: number;
  modified_at: number;
  segments: Record<string, unknown>[];
  files: string[];
}

export interface AssetItem {
  name: string;
  path: string;
  size: number;
  modified_at: number;
  asset_type: 'video' | 'subtitle' | 'audio' | 'other' | string;
}

export interface ExportResponse {
  zip_path: string;
  filename: string;
  size_bytes: number;
}

// Subtitle schemas
export interface SubtitleItem {
  index: number;
  start: number;
  end: number;
  text: string;
}

export interface SubtitleParseRequest {
  content?: string;
  file_path?: string;
  format?: 'srt' | 'vtt' | 'json' | string;
}

export interface SubtitleParseResponse {
  format: string;
  entries: SubtitleItem[];
  count: number;
}

export interface SubtitleConvertRequest {
  content?: string;
  file_path?: string;
  source_format?: string;
  target_format: 'srt' | 'vtt' | 'ass' | string;
}

export interface SubtitleConvertResponse {
  content: string;
  target_format: string;
  count: number;
}

export interface SubtitleSaveRequest {
  project_name?: string;
  file_path?: string;
  entries: SubtitleItem[];
  format?: 'srt' | 'vtt' | 'ass' | string;
  filename?: string;
}

export interface SubtitleSaveResponse {
  status: string;
  file_path: string;
  count: number;
}

export interface SubtitleStylePreviewRequest {
  font?: string;
  size?: number;
  color?: string;
  highlight_color?: string;
  outline_color?: string;
  outline_thickness?: number;
  shadow_color?: string;
  shadow_size?: number;
  bold?: boolean;
  italic?: boolean;
  uppercase?: boolean;
  highlight_size?: number;
  words_per_block?: number;
  gap_limit?: number;
  mode?: 'highlight' | 'word_by_word' | 'no_highlight' | string;
  underline?: boolean;
  strikeout?: boolean;
  border_style?: number;
  vertical_position?: number;
  alignment?: number;
  remove_punctuation?: boolean;
}

export interface SubtitleStylePreviewResponse {
  html: string;
}

export interface SubtitlePresetsResponse {
  presets: Record<string, Record<string, unknown>>;
}

// Google Drive schemas
export interface GDriveStatusResponse {
  available: boolean;
  mode: 'colab_mount' | 'oauth' | 'unconfigured' | string;
  message: string;
}

export interface GDriveVideoItem {
  id: string;
  name: string;
  size?: number | null;
  size_formatted: string;
  modified_time?: string | null;
  path?: string | null;
}

export interface GDriveImportRequest {
  file_id?: string;
  file_path?: string;
  project_name?: string;
}

export interface GDriveImportResponse {
  status: string;
  video_path: string;
  project_folder: string;
}

export interface GDriveExportRequest {
  project_name: string;
  destination_folder?: string;
}

export interface GDriveExportResponse {
  status: string;
  destination: string;
}

// System schemas
export interface SystemStatusResponse {
  status: string;
  gpu: {
    available?: boolean;
    name?: string;
    device_count?: number;
    cuda_version?: string;
    vram_total_mb?: number;
    vram_free_mb?: number;
    [key: string]: unknown;
  };
  disk: {
    total_gb?: number;
    used_gb?: number;
    free_gb?: number;
    percent_used?: number;
    [key: string]: unknown;
  };
  ffmpeg: {
    ffmpeg_available?: boolean;
    ffprobe_available?: boolean;
    version?: string;
    [key: string]: unknown;
  };
  python: {
    version?: string;
    executable?: string;
    [key: string]: unknown;
  };
  tools: Record<string, boolean>;
}

export interface SystemHealthResponse {
  status: string;
  timestamp: number;
}
