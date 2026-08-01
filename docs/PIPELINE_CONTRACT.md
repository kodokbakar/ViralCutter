# ViralCutter Pipeline Contract

## CLI Arguments

| Argument | Type | Default | Source | Notes |
|----------|------|---------|--------|-------|
| `--url` | `str` | `None` | URL input field | YouTube video URL |
| `--gdrive-url` | `str` | `None` | Google Drive path | Google Drive video URL |
| `--gdrive-file-id` | `str` | `None` | Google Drive file ID | Google Drive file ID from Drive Explorer |
| `--gdrive-file-name` | `str` | `None` | Google Drive file name | Google Drive file name from Drive Explorer |
| `--segments` | `int` | Required | Segments slider | Number of segments to create |
| `--viral` | `bool` | `False` | Viral mode checkbox | Enable viral mode |
| `--themes` | `str` | `None` | Themes input | Comma-separated themes (non-viral mode) |
| `--burn-only` | `bool` | `False` | N/A | Skip processing, only burn subtitles |
| `--min-duration` | `int` | `15` | Min duration slider | Minimum segment duration (seconds) |
| `--max-duration` | `int` | `90` | Max duration slider | Maximum segment duration (seconds) |
| `--pre-roll` | `float` | `1.25` | Pre-roll slider | Seconds to add before each segment |
| `--post-roll` | `float` | `0.75` | Post-roll slider | Seconds to add after each segment |
| `--model` | `str` | `"large-v3-turbo"` | Model dropdown | Whisper model to use |
| `--language` | `str` | `"auto"` | Language input | WhisperX language code. `auto` for detection, or force codes (`en`, `id`, `pt`, `es`) |
| `--prompt-file` | `str` | `None` | Prompt template textarea | Path to AI prompt template file |
| `--whisper-preset` | `str` | `"custom"` | Preset dropdown | WhisperX preset: `fast`, `balanced`, `accurate`, `custom` |
| `--whisper-batch-size` | `int` | `None` | Batch size input | WhisperX batch size override |
| `--whisper-chunk-size` | `int` | `None` | Chunk size input | WhisperX chunk size override |
| `--ai-backend` | `str` | `None` | Backend dropdown | AI backend: `manual`, `gemini`, `g4f`, `local` |
| `--api-key` | `str` | `None` | API key input | Gemini API key (required if ai-backend is `gemini`) |
| `--chunk-size` | `str` | `None` | Chunk size input | Override AI chunk size |
| `--ai-model-name` | `str` | `None` | Model name input | Override AI model name |
| `--project-path` | `str` | `None` | Project selector | Path to existing project folder (overrides URL/Latest) |
| `--workflow` | `str` | `"1"` | Workflow dropdown | Workflow: `1`=Full, `2`=Cut Only, `3`=Subtitles Only |
| `--face-model` | `str` | `"insightface"` | Face model dropdown | Face detection model: `insightface`, `mediapipe` |
| `--face-mode` | `str` | `"auto"` | Face mode dropdown | Face tracking mode: `auto`, `1`, `2`, `none` |
| `--subtitle-config` | `str` | `None` | Subtitle config textarea | Path to subtitle configuration JSON file |
| `--no-face-mode` | `str` | `"padding"` | No-face mode dropdown | No-face handling: `padding` (black bars), `zoom` (center crop) |
| `--face-detect-interval` | `str` | `"0.17,1.0"` | Interval input | Face detection interval (seconds). Single value or `interval_1face,interval_2face` |
| `--face-filter-threshold` | `float` | `0.35` | Filter threshold slider | Relative area threshold to ignore background faces |
| `--face-two-threshold` | `float` | `0.60` | Two-threshold slider | Relative area threshold to trigger 2-face mode |
| `--face-confidence-threshold` | `float` | `0.30` | Confidence slider | Face detection confidence threshold (0.0-1.0) |
| `--face-dead-zone` | `str` | `"40"` | Dead zone input | Camera movement dead zone in pixels |
| `--focus-active-speaker` | `bool` | `False` | Focus checkbox | Enable active speaker focus (InsightFace only) |
| `--active-speaker-mar` | `float` | `0.03` | MAR slider | Mouth Aspect Ratio threshold (0.0-1.0) |
| `--active-speaker-score-diff` | `float` | `1.5` | Score diff slider | Score difference to focus on active speaker |
| `--include-motion` | `bool` | `False` | Include motion checkbox | Include motion in activity score |
| `--active-speaker-motion-threshold` | `float` | `3.0` | Motion threshold slider | Motion deadzone in pixels |
| `--active-speaker-motion-sensitivity` | `float` | `0.05` | Motion sensitivity slider | Motion sensitivity multiplier |
| `--active-speaker-decay` | `float` | `2.0` | Decay slider | Activity score decay rate |
| `--skip-prompts` | `bool` | `False` | N/A | Skip interactive prompts (always `True` in WebUI) |
| `--video-quality` | `str` | `"best"` | Quality dropdown | Video download quality: `best`, `1080p`, `720p`, `480p` |
| `--skip-youtube-subs` | `bool` | `False` | Use YouTube subs checkbox | Skip downloading YouTube subtitles |
| `--translate-target` | `str` | `None` | Translate target input | Target language code for subtitle translation (e.g., `pt`, `en`) |
| `--compile` | `bool` | `False` | Compile mode checkbox | Compile segments into single video |
| `--crossfade` | `float` | `0.0` | Crossfade slider | Crossfade duration between clips (seconds) |
| `--fade-to-black` | `bool` | `False` | Fade to black checkbox | Add fade transitions between clips |
| `--segment-order` | `str` | `None` | Segment order input | Comma-separated segment order for compilation (e.g., `3,1,2`) |
| `--watermark-logo` | `str` | `None` | Logo file picker | Path to watermark logo image (PNG recommended) |
| `--watermark-position` | `str` | `"bottom-right"` | Position dropdown | Watermark position: `top-left`, `top-right`, `bottom-left`, `bottom-right`, `center`, `custom` |
| `--watermark-scale` | `float` | `0.15` | Scale slider | Watermark scale factor (0.0-1.0) |
| `--watermark-opacity` | `float` | `0.8` | Opacity slider | Watermark opacity (0.0-1.0) |
| `--watermark-h-margin` | `int` | `20` | H-margin slider | Horizontal margin in pixels |
| `--watermark-v-margin` | `int` | `20` | V-margin slider | Vertical margin in pixels |
| `--watermark-custom-x` | `int` | `100` | Custom X input | Custom X position (for `custom` position) |
| `--watermark-custom-y` | `int` | `100` | Custom Y input | Custom Y position (for `custom` position) |

## WebUI Parameter Mapping

The WebUI (`webui/app.py`) translates interface controls to CLI arguments:

| WebUI Control | CLI Argument | Transformation |
|---------------|--------------|----------------|
| Input Source: Existing Project | `--project-path` | Full path under VIRALS_DIR |
| Input Source: Upload Video | `--project-path` | Copies file to VIRALS_DIR/project_name |
| Input Source: YouTube URL | `--url` | Direct passthrough |
| Input Source: Google Drive | `--project-path` | Copies file to VIRALS_DIR/project_name |
| Video Quality | `--video-quality` | Direct passthrough |
| Use YouTube Subs | `--skip-youtube-subs` | Inverted (False → flag set) |
| Translate Target | `--translate-target` | Direct passthrough |
| Workflow | `--workflow` | Map: `Full`→`1`, `Cut Only`→`2`, `Subtitles Only`→`3` |
| Compile Mode | `--compile` | Flag only |
| Crossfade Duration | `--crossfade` | Only if compile enabled and > 0 |
| Segment Order | `--segment-order` | Only if compile enabled |
| Subtitle Config | `--subtitle-config` | Writes JSON to temp file, passes path |
| Watermark Enabled | `--watermark-logo` | Copies logo to temp, passes path |
| Skip Prompts | `--skip-prompts` | Always set in WebUI |

## Workflow Modes

| Mode | Value | Description |
|------|-------|-------------|
| Full | `1` | Download → Transcribe → AI Segment → Cut → Face Detection → Subtitles → Export |
| Cut Only | `2` | Transcribe → AI Segment → Cut (skip face detection and subtitles) |
| Subtitles Only | `3` | Re-subtitle existing cut segments (requires `--project-path`) |

## Project Directory Schema

All project data lives under `VIRALS/<project_name>/`. The project name is either user-supplied or auto-derived from the video title.

```
VIRALS/<project_name>/
├── input.mp4                          # source video (download)
├── input.srt                          # WhisperX subtitles
├── input.tsv                          # WhisperX TSV transcript
├── input.json                         # WhisperX JSON transcript (word-level timestamps)
├── viral_segments.txt                 # AI-selected segment metadata (JSON)
├── response.json                      # raw AI response from segment creation
├── process_config.json                # pipeline run configuration
├── face_modes.json                    # face detection mode per segment
├── prompt.txt                         # AI prompt template (copied at run time)
├── webui_run.log                      # full WebUI execution log
├── compilation.mp4                    # final compiled output video
├── compilation.srt                    # merged subtitle for compilation
│
├── cuts/                              # raw cut segments from source
│   ├── 000_<title>.mp4
│   ├── 000_<title>_processed.json     # trimmed transcript per segment
│   └── ...
│
├── final/                             # face-detected / cropped segments
│   ├── 000_<title>.mp4
│   ├── 000_<title>_timeline.json      # face tracking timeline
│   ├── 000_<title>_coords.json        # face coordinates
│   ├── 000_<title>_processed.json     # segment transcript copy
│   └── ...
│
├── burned_sub/                        # subtitles burned into video
│   ├── 000_<title>_processed_subtitled.mp4
│   └── ...
│
├── subs/                              # subtitle files (SRT + JSON)
│   ├── 000_<title>.srt
│   ├── 000_<title>_processed.srt
│   ├── 000_<title>.json
│   ├── 000_<title>_processed.json
│   ├── 000_<title>_original.json      # backup before translation
│   ├── 000_<title>_<lang>.json        # translated subtitle
│   └── ...
│
├── subs_ass/                          # ASS subtitle files (for burn)
│   ├── 000_<title>.ass
│   └── ...
│
├── compiled/                          # export-ready compiled output
│
├── output/                            # mirrored compilation + merged SRT
│   ├── compilation.mp4
│   └── compilation.srt
│
├── .compile_tmp/                      # temp files during compilation (ephemeral)
│
├── .runtime/                          # project-scoped runtime files (G-009, planned)
│   ├── prompt.txt
│   ├── subtitle_config.json
│   ├── command.json
│   ├── process.pid
│   ├── current_stage.json
│   ├── stdout.log
│   └── stderr.log
│
└── watermarked/                       # optional watermarked output
```

### Root-level Files

| File | Writer | Reader | Purpose |
|------|--------|--------|---------|
| `input.mp4` | `download_video.py`, `gdrive_client.py` | `cut_segments.py`, `refine_segments.py`, `edit_video.py` | Source video downloaded or uploaded by user |
| `input.srt` | `download_video.py`, `transcribe_video.py` | `create_viral_segments.py` | WhisperX-generated SRT subtitles |
| `input.tsv` | `transcribe_video.py` | `create_viral_segments.py` | WhisperX TSV transcript (word-level) |
| `input.json` | `transcribe_video.py` | `cut_segments.py`, `refine_segments.py` | WhisperX JSON transcript (word-level timestamps) |
| `viral_segments.txt` | `create_viral_segments.py` | `compile_segments.py`, WebUI | AI-selected segment metadata with titles, hooks, reasoning, and ordering |
| `response.json` | `create_viral_segments.py` | (debugging) | Raw AI model response |
| `process_config.json` | `main_improved.py`, WebUI | WebUI | Pipeline run configuration (segment count, durations, etc.) |
| `face_modes.json` | `edit_video.py` | `adjust_subtitles.py`, `preserve_segments.py` | Face detection mode per segment (one/two face, insightface, etc.) |
| `prompt.txt` | User (WebUI) | `create_viral_segments.py` | AI prompt template with placeholders |
| `webui_run.log` | WebUI | User | Full execution log for the pipeline run |
| `compilation.mp4` | `compile_segments.py` | `export_xml_lib/exporter.py` | Final concatenated video |
| `compilation.srt` | `compile_segments.py` | (merging) | Merged subtitle aligned to compilation |

### Directories

**`cuts/`** - Raw segment videos cut from source. Created by `cut_segments.py`. Each segment is named `NNN_<title>.mp4` where NNN is the zero-padded index. Accompanying `_processed.json` files contain the trimmed transcript for each segment.

**`final/`** - Face-detected and cropped segments. Created by `edit_video.py` (or `preserve_segments.py` when face detection is skipped). Contains the same video files but reframed for 9:16 vertical output. Each segment also has `_timeline.json` (face tracking timeline) and `_coords.json` (face bounding boxes) sidecars.

**`burned_sub/`** - Videos with hardcoded subtitles. Created by `burn_subtitles.py`. Takes videos from `final/` and ASS files from `subs_ass/`, burns them together. Files are named `NNN_<title>_processed_subtitled.mp4`.

**`subs/`** - Subtitle files in SRT and JSON format. Written by `transcribe_video.py` (initial transcription), `cut_segments.py` (per-segment trimming), and `translate_json.py` (translation). The `_processed.json` variants contain adjusted timestamps. Translations create `_original.json` backups and `_lang.json` outputs.

**`subs_ass/`** - ASS subtitle files generated by `adjust_subtitles.py`. These are styled versions of the JSON subtitles, ready for burning into video. Each `_processed.json` from `subs/` becomes a `.ass` file here.

**`compiled/`** - Export-ready compiled output. Listed in `EXPORT_FOLDERS` by `project_export.py`.

**`output/`** - Mirrored copy of the final compilation and merged SRT. Created by `compile_segments.py` and `merge_subtitles.py` as a convenience location.

**`.compile_tmp/`** - Temporary working directory used by `compile_segments.py` during crossfade and re-encoding operations. Ephemeral; deleted after compilation completes.

**`.runtime/`** - Project-scoped runtime files (planned per G-009). Will isolate per-project state: prompt config, subtitle config, command queue, process PID, current stage, and logs. Replaces the current global shared state model.

**`watermarked/`** - Optional watermarked output. Created by `watermark.py` when watermarking is applied.

### Export Structure

`webui/project_export.py` packages projects into ZIP files. The export includes:

```python
EXPORT_FOLDERS = ["cuts", "final", "burned_sub", "compiled"]
EXPORT_FILES = ["viral_segments.txt", "prompt.txt", "webui_run.log", "process_config.json"]
ROOT_EXTRA_PATTERNS = ["compilation.mp4", "compilation.srt"]
```

The ZIP mirrors the project directory structure, preserving subdirectory paths.

### Pipeline Flow

The pipeline writes to directories in this order:

1. **Download** → `input.mp4`, `input.srt`
2. **Transcribe** → `input.srt`, `input.tsv`, `input.json`
3. **Create Viral Segments** → `viral_segments.txt`, `response.json`
4. **Cut Segments** → `cuts/`
5. **Edit / Preserve** → `final/`
6. **Adjust Subtitles** → `subs_ass/`
7. **Burn Subtitles** → `burned_sub/`
8. **Compile** → `compilation.mp4`, `compilation.srt`, `output/`
9. **Export** → `<project>_export.zip`

### Conventions

- Segment files use zero-padded indices: `000_`, `001_`, `002_`, etc.
- `project_root_for(segments_folder)` in `compile_segments.py` resolves `cuts/`, `final/`, or `burned_sub/` back to the project root.
- Face modes are stored in `face_modes.json` and read by multiple scripts to determine cropping behavior.
- Translation creates `_original.json` backups before modifying `_processed.json` files.
- The `webui_run.log` accumulates the full pipeline log and is saved when the project folder is known.

## Source Files

- CLI definitions: `main_improved.py` (lines 104-163)
- WebUI mapping: `webui/app.py` (lines 526-751)
