# Pipeline Performance Optimizations Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Resolve the four critical performance bottlenecks across ViralCutter video processing pipeline: (1) eliminate redundant video splicing in `scripts/smart_clipping.py` during narrative analysis, (2) replace slow lanczos scaling with bicubic and add hardware NVENC encoder detection in `scripts/gaming_split.py`, (3) add realtime multi-threaded VP9 flags (`-deadline realtime -cpu-used 8 -row-mt 1`) and Playwright viewport/screenshot optimizations in `scripts/broll_renderer.py`, and (4) cache encoder failure status and add graceful `filter_complex` fallback in `scripts/burn_subtitles.py`.

**Architecture:**
- **Smart Clipping & Cutting Pipeline:** Decouple narrative analysis from video rendering. In `scripts/smart_clipping.py`, `run_smart_clipping_pipeline()` introduces `render_clips: bool = False`. Video cutting is consolidated exclusively into `scripts/cut_segments.py`, which is enhanced to handle multi-slice segments (`segments_to_splice`), eliminating double video encoding.
- **Gaming Split & Manual Crop:** Replace compute-heavy `flags=lanczos` with `flags=bicubic` in scaling filter graphs (`build_manual_crop_filter`, `build_gaming_split_filter`). Implement hardware encoder detection (`get_best_encoder()`) with cached state (`_CACHED_ENCODER`) and automatic fallback from `h264_nvenc` / `h264_amf` / `h264_qsv` to `libx264 ultrafast`.
- **B-Roll Motion Renderer:** Configure `libvpx-vp9` with `-deadline realtime -cpu-used 8 -row-mt 1` for fast multi-threaded VP9 alpha video rendering. Optimize Playwright with `device_scale_factor=1`, `wait_until="domcontentloaded"`, `animations="disabled"` in screenshot capture, and Chromium performance flags (`--disable-background-timer-throttling`, etc.).
- **Subtitle Burning:** Cache encoder availability (`_NVENC_AVAILABLE`) so systems lacking NVIDIA GPU drivers (e.g. missing `libcuda.so.1`) do not repeatedly incur timeout/failure overhead on every single video clip. When complex multi-input filter graphs (`-filter_complex` with B-roll / SFX / watermark) fail, automatically fall back to simple subtitle burn (`-vf subtitle_filter`).

**Tech Stack:** Python 3.10+, FFmpeg / FFprobe, Playwright (Headless Chromium), pytest.

## Global Constraints & Backward Compatibility
- Target output canvas for 9:16 vertical videos remains 1080x1920.
- WebM B-roll alpha transparency (`alpha_mode=1`, `pix_fmt=yuva420p`) must be strictly preserved without opaque backgrounds.
- Hardware encoder detection must never crash on hosts lacking GPU libraries; automatic fallback to CPU (`libx264`) must always succeed.
- CLI flags and existing WebUI schema contracts must remain backward-compatible.

---
### Task 1: Eliminate Redundant Splicing in Smart Clipping & Enhance Cut Segments

**Files:**
- Modify: `scripts/smart_clipping.py`
- Modify: `scripts/cut_segments.py`
- Create: `tests/test_smart_clipping_perf.py`

**Interfaces:**
- `scripts/smart_clipping.py`:
  - `run_smart_clipping_pipeline(..., render_clips: bool = False) -> Dict[str, Any]`
  - When `render_clips is False`, bypass `splice_topic_segments()` during narrative analysis; populate `viral_segments` metadata (`start_time`, `end_time`, `duration`, `segments_to_splice`, `broll_items`).
- `scripts/cut_segments.py`:
  - `generate_segments()` inspects `segment.get("segments_to_splice") or segment.get("sub_segments")`.
  - If multi-slice list (`len > 1`), calls `smart_clipping.splice_topic_segments(input_file, slices, output_path)` (or copies if pre-existing).
  - If single continuous slice or not specified, executes existing single cut FFmpeg command.

- [ ] **Step 1: Write failing test for smart clipping `render_clips=False` and `cut_segments` multi-slice**

Create `tests/test_smart_clipping_perf.py`:
```python
import os
import pytest
from unittest.mock import patch, MagicMock
from scripts import smart_clipping, cut_segments

def test_smart_clipping_bypasses_splicing_when_render_clips_false(tmp_path):
    project_folder = str(tmp_path)
    (tmp_path / "input.mp4").write_bytes(b"fake video content")

    mock_topics = [{
        "title": "Topic 1",
        "score": 90,
        "rationale": "Great hook",
        "segments": {
            "hook": {"start_time": 0.0, "end_time": 5.0, "text": "Hook"},
            "core": {"start_time": 10.0, "end_time": 20.0, "text": "Core"},
            "payoff": {"start_time": 25.0, "end_time": 30.0, "text": "Payoff"}
        }
    }]

    with patch("scripts.smart_clipping.extract_words_from_transcript", return_value=[]),          patch("scripts.create_viral_segments.load_transcript", return_value=[]),          patch("scripts.create_viral_segments.preprocess_transcript_for_ai", return_value="test text"),          patch("scripts.smart_clipping.query_ai_backend", return_value="{}"),          patch("scripts.smart_clipping.parse_narrative_topics", return_value=mock_topics),          patch("scripts.smart_clipping.compute_audio_energy_score", return_value=80.0),          patch("scripts.smart_clipping.splice_topic_segments") as mock_splice:

        res = smart_clipping.run_smart_clipping_pipeline(
            project_folder=project_folder,
            render_clips=False
        )

        assert "segments" in res
        assert len(res["segments"]) == 1
        # Verifies FFmpeg splice was completely bypassed
        mock_splice.assert_not_called()
        seg = res["segments"][0]
        assert "segments_to_splice" in seg
        assert len(seg["segments_to_splice"]) > 0

def test_cut_segments_handles_segments_to_splice(tmp_path):
    project_folder = str(tmp_path)
    (tmp_path / "input.mp4").write_bytes(b"fake video content")
    cuts_dir = tmp_path / "cuts"
    cuts_dir.mkdir()

    segments_data = {
        "segments": [{
            "title": "Multi Slice Segment",
            "score": 88,
            "start_time": 0.0,
            "duration": 15.0,
            "segments_to_splice": [(0.0, 5.0), (10.0, 20.0)]
        }]
    }

    with patch("scripts.cut_segments.check_nvenc_support", return_value=False),          patch("scripts.smart_clipping.splice_topic_segments") as mock_splice,          patch("scripts.cut_json.cut_json_transcript"):

        cut_segments.cut(segments_data, project_folder=project_folder, skip_video=False)
        mock_splice.assert_called_once()
        args, kwargs = mock_splice.call_args
        assert args[1] == [(0.0, 5.0), (10.0, 20.0)]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_smart_clipping_perf.py -v`  
Expected: FAIL (`TypeError: run_smart_clipping_pipeline() got an unexpected keyword argument 'render_clips'` or `AssertionError: mock_splice was not called`).

- [ ] **Step 3: Implement `render_clips` in `scripts/smart_clipping.py` and multi-splice in `scripts/cut_segments.py`**

In `scripts/smart_clipping.py`:
- In `run_smart_clipping_pipeline(...)`:
  - Add parameter `render_clips: bool = False`.
  - At line ~759:
    ```python
    if render_clips and os.path.exists(input_video) and segments_to_splice:
        print(f"[SMART-CLIPPING] Splicing topic {idx+1}/{len(topics)}: '{title}' ({len(segments_to_splice)} parts)...")
        try:
            splice_topic_segments(input_video, segments_to_splice, output_clip_path)
        except Exception as e:
            print(f"[SMART-CLIPPING] Error splicing clip {idx+1}: {e}")
    ```

In `scripts/cut_segments.py`:
- In `generate_segments(response, project_folder, skip_video)`:
  - Check for multi-segment slicing before video generation command:
    ```python
    sub_slices = segment.get("segments_to_splice") or segment.get("sub_segments")
    if not skip_video:
        if sub_slices and isinstance(sub_slices, list) and len(sub_slices) > 1:
            from scripts.smart_clipping import splice_topic_segments
            try:
                splice_topic_segments(input_file, [(float(s), float(e)) for s, e in sub_slices], output_path)
                print(f"Generated spliced segment: {output_filename}", flush=True)
            except Exception as e:
                print(f"Error splicing segment {i+1}: {e}", flush=True)
        else:
            # Standard single cut ffmpeg command
    ```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_smart_clipping_perf.py -v`  
Expected: PASS.

- [ ] **Step 5: Commit changes**

Commit: `perf(smart_clipping): eliminate redundant video splicing in narrative analysis [pipeline-perf]`

---
### Task 2: Fast Bicubic Scaling & Hardware Encoder Detection in Gaming Split

**Files:**
- Modify: `scripts/gaming_split.py`
- Modify: `tests/test_manual_crop.py`
- Create: `tests/test_gaming_split_encoder.py`

**Interfaces:**
- `scripts/gaming_split.py`:
  - `get_best_encoder() -> Tuple[str, str, List[str]]`: returns `(codec, preset, extra_args)` with cached detection (`_CACHED_ENCODER`).
  - `build_manual_crop_filter(crop_box: str, src_w: int, src_h: int, target_w: int = 1080, target_h: int = 1920, scale_flags: str = "bicubic") -> str`
  - `build_gaming_split_filter(facecam_box: str, gameplay_box: str, src_w: int, src_h: int, scale_flags: str = "bicubic") -> str`
  - `render_manual_crop_clip(...)` and `render_gaming_split_clip(...)`: query `get_best_encoder()`, apply hardware acceleration flags (`-c:v h264_nvenc -preset p1 -b:v 5M` or `libx264 ultrafast`), and gracefully fall back to CPU `libx264` if hardware encoder invocation fails.

- [ ] **Step 1: Write failing tests for encoder detection and update filter tests**

Create `tests/test_gaming_split_encoder.py`:
```python
import subprocess
import pytest
from unittest.mock import patch, MagicMock
from scripts import gaming_split

def test_get_best_encoder_nvenc_success():
    with patch("scripts.gaming_split._CACHED_ENCODER", None),          patch("subprocess.run") as mock_run:
        mock_encoders = MagicMock(stdout=" V....D h264_nvenc NVIDIA NVENC H.264 encoder
")
        mock_probe = MagicMock(returncode=0)
        mock_run.side_effect = [mock_encoders, mock_probe]

        codec, preset, extra_args = gaming_split.get_best_encoder()
        assert codec == "h264_nvenc"
        assert "-b:v" in extra_args

def test_get_best_encoder_fallback_on_probe_failure():
    with patch("scripts.gaming_split._CACHED_ENCODER", None),          patch("subprocess.run") as mock_run:
        mock_encoders = MagicMock(stdout=" V....D h264_nvenc NVIDIA NVENC H.264 encoder
")
        mock_run.side_effect = [mock_encoders, subprocess.CalledProcessError(255, ["ffmpeg"])]

        codec, preset, extra_args = gaming_split.get_best_encoder()
        assert codec == "libx264"
        assert preset == "ultrafast"

def test_build_manual_crop_filter_defaults_to_bicubic():
    filt = gaming_split.build_manual_crop_filter(
        crop_box=gaming_split.DEFAULT_MANUAL_CROP_BOX,
        src_w=1920,
        src_h=1080
    )
    assert "flags=bicubic" in filt
    assert "flags=lanczos" not in filt
```

Update `tests/test_manual_crop.py` line 26:
Change `assert "scale=1080:1920:flags=lanczos" in filt` to:
`assert "scale=1080:1920:flags=bicubic" in filt`

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_gaming_split_encoder.py tests/test_manual_crop.py -v`  
Expected: FAIL (`AttributeError: module 'scripts.gaming_split' has no attribute 'get_best_encoder'` and assertion mismatch).

- [ ] **Step 3: Implement encoder detection and bicubic scaling in `scripts/gaming_split.py`**

In `scripts/gaming_split.py`:
```python
_CACHED_ENCODER = None

def get_best_encoder() -> Tuple[str, str, List[str]]:
    """
    Detects best available video encoder with hardware acceleration and caching.
    Returns (codec_name, preset, extra_args).
    """
    global _CACHED_ENCODER
    if _CACHED_ENCODER is not None:
        return _CACHED_ENCODER

    try:
        res = subprocess.run(["ffmpeg", "-hide_banner", "-encoders"], capture_output=True, text=True)
        out = res.stdout or ""

        # 1. Try NVENC with quick 1-frame probe
        if "h264_nvenc" in out:
            probe = subprocess.run(
                ["ffmpeg", "-y", "-f", "lavfi", "-i", "testsrc=d=0.1:s=64x64:r=1", "-c:v", "h264_nvenc", "-f", "null", "-"],
                capture_output=True,
                check=True
            )
            _CACHED_ENCODER = ("h264_nvenc", "p1", ["-b:v", "5M"])
            return _CACHED_ENCODER
        elif "h264_amf" in out:
            _CACHED_ENCODER = ("h264_amf", "speed", ["-b:v", "5M"])
            return _CACHED_ENCODER
        elif "h264_qsv" in out:
            _CACHED_ENCODER = ("h264_qsv", "veryfast", ["-b:v", "5M"])
            return _CACHED_ENCODER
    except Exception:
        pass

    _CACHED_ENCODER = ("libx264", "ultrafast", ["-crf", "18"])
    return _CACHED_ENCODER

def build_manual_crop_filter(
    crop_box: str,
    src_w: int,
    src_h: int,
    target_w: int = 1080,
    target_h: int = 1920,
    scale_flags: str = "bicubic"
) -> str:
    px_x, px_y, px_w, px_h = to_pixel_box(crop_box or DEFAULT_MANUAL_CROP_BOX, src_w, src_h)
    return f"crop={px_w}:{px_h}:{px_x}:{px_y},scale={target_w}:{target_h}:flags={scale_flags}"

def build_gaming_split_filter(
    facecam_box: str,
    gameplay_box: str,
    src_w: int,
    src_h: int,
    scale_flags: str = "bicubic"
) -> str:
    cam_x, cam_y, cam_w, cam_h = to_pixel_box(facecam_box, src_w, src_h)
    game_x, game_y, game_w, game_h = to_pixel_box(gameplay_box, src_w, src_h)

    return (
        f"[0:v]split=2[raw_cam][raw_game];"
        f"[raw_cam]crop={cam_w}:{cam_h}:{cam_x}:{cam_y},scale=1080:576:flags={scale_flags}[cam_top];"
        f"[raw_game]crop={game_w}:{game_h}:{game_x}:{game_y},scale=1080:1344:flags={scale_flags}[game_bottom];"
        f"[cam_top][game_bottom]vstack=inputs=2[stacked_v]"
    )
```

In `render_manual_crop_clip` and `render_gaming_split_clip`:
- Retrieve `codec, preset, extra_args = get_best_encoder()`.
- Construct ffmpeg command using dynamic codec, preset, and extra args.
- If execution raises `subprocess.CalledProcessError`: fall back to CPU `libx264` (`-c:v libx264 -preset ultrafast -crf 18`), update `_CACHED_ENCODER = ("libx264", "ultrafast", ["-crf", "18"])`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_gaming_split_encoder.py tests/test_manual_crop.py tests/test_gaming_split.py -v`  
Expected: PASS.

- [ ] **Step 5: Commit changes**

Commit: `perf(gaming_split): add hardware encoder detection and bicubic scaling [pipeline-perf]`

---
### Task 3: Realtime Multi-Threaded VP9 Encoding & Playwright Optimization in B-Roll Renderer

**Files:**
- Modify: `scripts/broll_renderer.py`
- Create: `tests/test_broll_renderer_perf.py`

**Interfaces:**
- `scripts/broll_renderer.py`:
  - `render_broll_clip(template_id: str, data: Dict[str, Any], duration: float, output_path: str, fps: int = 12) -> str`
  - VP9 FFmpeg parameters include `"-deadline", "realtime", "-cpu-used", "8", "-row-mt", "1"`.
  - Playwright browser context configured with `device_scale_factor=1`.
  - Navigation uses `wait_until="domcontentloaded"`.
  - Screenshot capture passes `animations="disabled"` with `omit_background=True`.
  - Optimized browser flags: `--disable-background-timer-throttling`, `--disable-backgrounding-occluded-windows`, `--disable-renderer-backgrounding`, `--no-default-browser-check`.

- [ ] **Step 1: Write failing test verifying VP9 realtime flags and browser performance arguments**

Create `tests/test_broll_renderer_perf.py`:
```python
import subprocess
from unittest.mock import patch, MagicMock
from scripts import broll_renderer

def test_render_broll_clip_uses_realtime_vp9_flags(tmp_path):
    output_webm = str(tmp_path / "out.webm")
    data = {"target_number": "42"}

    with patch("subprocess.Popen") as mock_popen,          patch("scripts.broll_renderer.sync_playwright") as mock_pw,          patch("os.path.exists", return_value=True),          patch("os.path.getsize", return_value=5000):

        mock_proc = MagicMock()
        mock_proc.poll.return_value = 0
        mock_proc.returncode = 0
        mock_proc.stdin = MagicMock()
        mock_popen.return_value = mock_proc

        broll_renderer.render_broll_clip("stat_counter", data, 1.0, output_webm, fps=12)

        cmd = mock_popen.call_args[0][0]
        assert "-deadline" in cmd
        assert cmd[cmd.index("-deadline") + 1] == "realtime"
        assert "-cpu-used" in cmd
        assert cmd[cmd.index("-cpu-used") + 1] == "8"
        assert "-row-mt" in cmd
        assert cmd[cmd.index("-row-mt") + 1] == "1"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_broll_renderer_perf.py -v`  
Expected: FAIL (`AssertionError: '-deadline' not in cmd`).

- [ ] **Step 3: Implement VP9 and Playwright optimizations in `scripts/broll_renderer.py`**

In `scripts/broll_renderer.py`:
Update `ffmpeg_cmd`:
```python
    ffmpeg_cmd = [
        "ffmpeg",
        "-y",
        "-loglevel",
        "error",
        "-f",
        "image2pipe",
        "-vcodec",
        "png",
        "-r",
        str(fps),
        "-i",
        "-",
        "-c:v",
        "libvpx-vp9",
        "-pix_fmt",
        "yuva420p",
        "-deadline",
        "realtime",
        "-cpu-used",
        "8",
        "-row-mt",
        "1",
        "-b:v",
        "2M",
        "-auto-alt-ref",
        "0",
        output_path,
    ]
```

Update browser launch and screenshot loop:
```python
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=[
                    "--disable-gpu",
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-extensions",
                    "--no-default-browser-check",
                    "--disable-background-timer-throttling",
                    "--disable-backgrounding-occluded-windows",
                    "--disable-renderer-backgrounding",
                ],
            )
            context = browser.new_context(
                viewport={"width": 1080, "height": 1920},
                device_scale_factor=1,
            )
            page = context.new_page()
            page.goto(f"file://{os.path.abspath(temp_html_path)}", wait_until="domcontentloaded")

            denominator = max(1, total_frames - 1)
            for frame_idx in range(total_frames):
                progress = frame_idx / denominator
                page.evaluate(f"window.renderSeek({progress})")
                frame_bytes = page.screenshot(type="png", omit_background=True, animations="disabled")
                proc.stdin.write(frame_bytes)

            browser.close()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_broll_renderer_perf.py tests/test_broll_renderer.py -v`  
Expected: PASS (and verify WebM alpha transparency test still passes cleanly).

- [ ] **Step 5: Commit changes**

Commit: `perf(broll): add realtime multi-threaded VP9 flags and Playwright optimizations [pipeline-perf]`

---
### Task 4: Subtitle Burning Encoder Caching & Graceful Filter Complex Fallback

**Files:**
- Modify: `scripts/burn_subtitles.py`
- Create: `tests/test_burn_subtitles_fallback.py`

**Interfaces:**
- `scripts/burn_subtitles.py`:
  - `_NVENC_AVAILABLE`: module-level cache (`None` -> `True` or `False`).
  - If `_NVENC_AVAILABLE is False`: `burn_video_file()` immediately skips the failing `h264_nvenc` attempt, avoiding repeating the failure penalty on every clip in a project.
  - When `run_ffmpeg("h264_nvenc", "p1")` fails: set `_NVENC_AVAILABLE = False`.
  - Filter complex fallback: If `run_ffmpeg` fails with `valid_broll or watermark_enabled or mix_audio` under both NVENC and CPU, log a warning and retry rendering with simple subtitle burning (`-vf subtitle_filter` and `-c:a copy` / `aac`) instead of terminating with a hard error.

- [ ] **Step 1: Write failing tests for encoder caching and filter complex fallback**

Create `tests/test_burn_subtitles_fallback.py`:
```python
import subprocess
import pytest
from unittest.mock import patch, MagicMock
from scripts import burn_subtitles

def test_nvenc_failure_cached_avoids_repeated_nvenc_calls(tmp_path):
    video_path = str(tmp_path / "in.mp4")
    (tmp_path / "in.mp4").write_bytes(b"fake video")
    sub_path = str(tmp_path / "in.ass")
    (tmp_path / "in.ass").write_text("[Script Info]
")
    out_1 = str(tmp_path / "out1.mp4")
    out_2 = str(tmp_path / "out2.mp4")

    # Reset cache
    burn_subtitles._NVENC_AVAILABLE = None

    calls = []
    def fake_subprocess_run(cmd, *args, **kwargs):
        encoder = cmd[cmd.index("-c:v") + 1]
        calls.append(encoder)
        if encoder == "h264_nvenc":
            raise subprocess.CalledProcessError(255, cmd, stderr="Cannot load libcuda.so.1")
        (tmp_path / "temp_done").touch()
        return subprocess.CompletedProcess(cmd, 0)

    with patch("subprocess.run", side_effect=fake_subprocess_run),          patch("scripts.burn_subtitles._validate_render", return_value=True):

        # First clip: tries NVENC -> fails -> falls back to libx264
        ok1, msg1, val1 = burn_subtitles.burn_video_file(video_path, sub_path, out_1)
        assert ok1 is True
        assert burn_subtitles._NVENC_AVAILABLE is False
        assert calls.count("h264_nvenc") == 1
        assert calls.count("libx264") == 1

        # Second clip: NVENC should be SKIPPED directly
        ok2, msg2, val2 = burn_subtitles.burn_video_file(video_path, sub_path, out_2)
        assert ok2 is True
        # NVENC call count remains 1 (never re-tested)
        assert calls.count("h264_nvenc") == 1
        assert calls.count("libx264") == 2

def test_filter_complex_failure_falls_back_to_simple_subtitle_burn(tmp_path):
    video_path = str(tmp_path / "in.mp4")
    (tmp_path / "in.mp4").write_bytes(b"fake video")
    sub_path = str(tmp_path / "in.ass")
    (tmp_path / "in.ass").write_text("[Script Info]
")
    out_path = str(tmp_path / "out.mp4")

    burn_subtitles._NVENC_AVAILABLE = False
    broll_webm = str(tmp_path / "broll.webm")
    (tmp_path / "broll.webm").write_bytes(b"dummy webm")

    commands_executed = []
    def fake_subprocess_run(cmd, *args, **kwargs):
        commands_executed.append(list(cmd))
        if "-filter_complex" in cmd:
            raise subprocess.CalledProcessError(1, cmd, stderr="Filter complex overlay error")
        return subprocess.CompletedProcess(cmd, 0)

    with patch("subprocess.run", side_effect=fake_subprocess_run),          patch("scripts.burn_subtitles._validate_render", return_value=True):

        ok, msg, val = burn_subtitles.burn_video_file(
            video_path=video_path,
            subtitle_path=sub_path,
            output_path=out_path,
            broll_items=[{"video_path": broll_webm}]
        )

        assert ok is True
        # Check that a retry occurred with simple -vf subtitle filter
        vf_commands = [c for c in commands_executed if "-vf" in c]
        assert len(vf_commands) >= 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_burn_subtitles_fallback.py -v`  
Expected: FAIL (`AttributeError: module 'scripts.burn_subtitles' has no attribute '_NVENC_AVAILABLE'` or failed fallback).

- [ ] **Step 3: Implement encoder caching and filter_complex fallback in `scripts/burn_subtitles.py`**

In `scripts/burn_subtitles.py`:
- Declare module-level cache:
  ```python
  _NVENC_AVAILABLE = None
  ```
- In `burn_video_file()`:
  - Add parameter `bypass_complex: bool = False` to `run_ffmpeg()`:
    ```python
    if (valid_broll or watermark_enabled or mix_audio) and not bypass_complex:
        # Build filter_complex with broll/watermark/audio mixing
        ...
    else:
        command.extend(["-vf", subtitle_filter])
    ```
  - In NVENC execution check:
    ```python
    global _NVENC_AVAILABLE
    if _NVENC_AVAILABLE is not False:
        try:
            validation = run_ffmpeg("h264_nvenc", "p1")
            _NVENC_AVAILABLE = True
            return (True, "NVENC Success", validation)
        except Exception as nvenc_error:
            _NVENC_AVAILABLE = False
            print("NVENC render failed. Falling back to libx264.", flush=True)
    ```
  - In CPU libx264 execution and filter_complex fallback:
    ```python
    try:
        validation = run_ffmpeg("libx264", "ultrafast")
        return (True, "CPU Success", validation)
    except Exception as cpu_error:
        if (valid_broll or watermark_enabled or mix_audio):
            print("[WARN] Complex filter render failed. Falling back to simple subtitle burn...", flush=True)
            try:
                validation = run_ffmpeg("libx264", "ultrafast", bypass_complex=True)
                return (True, "CPU Fallback Success (Simple Subs)", validation)
            except Exception as fallback_err:
                pass
        # Report failure as before
        return (False, message, None)
    ```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_burn_subtitles_fallback.py -v`  
Expected: PASS.

- [ ] **Step 5: Commit changes**

Commit: `perf(burn_subtitles): add NVENC failure caching and graceful filter_complex fallback [pipeline-perf]`

---

### Task 5: End-to-End Suite Regression & Performance Sanity Check

**Files:**
- Test: All touched modules & existing pipeline tests.

- [ ] **Step 1: Run comprehensive regression test suite**

Run:
```bash
pytest tests/test_smart_clipping_perf.py        tests/test_gaming_split_encoder.py        tests/test_manual_crop.py        tests/test_gaming_split.py        tests/test_broll_renderer_perf.py        tests/test_broll_renderer.py        tests/test_burn_subtitles_fallback.py        tests/test_smart_clipping_snapping.py        tests/test_custom_api.py -v
```
Expected: All tests PASS.

- [ ] **Step 2: Commit any remaining cleanups or documentation updates**

Commit: `test(pipeline-perf): verify full pipeline performance optimization suite [pipeline-perf]`

---

## Verification Plan

### Automated Tests
1. **Smart Clipping:** `pytest tests/test_smart_clipping_perf.py -v`
   - Confirms `render_clips=False` avoids FFmpeg splicing during narrative analysis.
   - Confirms `cut_segments.cut()` properly splices multi-slice segments when passed.
2. **Gaming Split:** `pytest tests/test_gaming_split_encoder.py tests/test_manual_crop.py -v`
   - Confirms `get_best_encoder()` properly probes NVENC and falls back to CPU if `libcuda.so.1` is absent.
   - Confirms `flags=bicubic` is used in filter graphs.
3. **B-Roll VP9:** `pytest tests/test_broll_renderer_perf.py tests/test_broll_renderer.py -v`
   - Confirms `-deadline realtime -cpu-used 8 -row-mt 1` are passed to FFmpeg.
   - Confirms transparent WebM rendering produces valid alpha channel (`alpha_mode=1`, `pix_fmt=yuva420p`).
4. **Burn Subtitles:** `pytest tests/test_burn_subtitles_fallback.py -v`
   - Confirms NVENC failure is cached and not repeated across multiple video burns.
   - Confirms corrupted/failing filter_complex recovers to basic subtitle burn.

### Manual / Integration Verification
- Execute dry run with `python main_improved.py --help` to verify CLI stability.
- Run `pytest` on all existing test suites to ensure zero regressions across other modes.
