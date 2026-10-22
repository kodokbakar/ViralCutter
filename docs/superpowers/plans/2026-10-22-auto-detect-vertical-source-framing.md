# Auto-Detect Vertical Source Video Framing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Automatically detect if the input video is already vertical ($W < H$, e.g. 1080x1920) in gaming mode, bypassing the 9:16 Gaming Split layout and preserving the source framing as-is without re-cropping or distortion.

**Architecture:** A dimension probe (`is_vertical_video`) checks input video aspect ratio. When $W < H$, the backend bypasses `gaming_split.render_gaming_split_clip` and directly invokes `preserve_segments.preserve_original_scale`, while the WebUI (`GeneratorTab.tsx`) inspects video metadata, displays a "Vertical Source Detected — Framing Preserved" banner, and suppresses the dual bounding-box editor.

**Tech Stack:** Python 3.10+, FFmpeg / FFprobe, Pydantic, FastAPI, React + Vite.

**Spec / Requirements:**
- If input video $W < H$, `main_improved.py` in `--pipeline-mode gaming` must NOT apply `gaming_split.py` (which crops 16:9 into facecam and gameplay boxes).
- It must preserve the exact 9:16 vertical resolution and framing of the source video using `preserve_segments.preserve_original_scale`.
- Subtitle burning and title hook overlays must continue to render correctly on top of the preserved 9:16 vertical video.
- WebUI must auto-detect when a selected video has $W < H$ and adapt the UI gracefully without requiring manual user workarounds.

## Global Constraints
- Target output canvas for vertical videos: preserves exact input dimensions (e.g. $1080 \times 1920$).
- No reliance on external internet; all dimension inspection is performed locally via `ffprobe`.
- Subtitle burning in Workflow 1 must remain centered in the lower third without colliding with facecam areas.
- Zero distortion, stretching, or squishing on vertical video inputs.

---

### Task 1: Dimension Probe Helper & Backend Auto-Bypass (`scripts/gaming_split.py`, `main_improved.py`)

**Files:**
- Modify: `scripts/gaming_split.py`
- Modify: `main_improved.py`
- Test: `tests/test_gaming_vertical_source.py`

**Interfaces:**
- Produces:
  - `is_vertical_video(video_path: str) -> bool`: returns `True` if video width < height, `False` otherwise.
  - In `main_improved.py`: before Step 5 (Edit Video), checks if source video is vertical. If vertical, logs message and falls back to `preserve_segments.preserve_original_scale`.

- [ ] **Step 1: Write the failing tests for vertical video detection and bypass**

Create `tests/test_gaming_vertical_source.py`:
```python
import pytest
from unittest.mock import patch
from scripts.gaming_split import is_vertical_video

def test_is_vertical_video_true():
    with patch("scripts.gaming_split.probe_video_dimensions", return_value=(1080, 1920)):
        assert is_vertical_video("vertical.mp4") is True

def test_is_vertical_video_false_for_horizontal():
    with patch("scripts.gaming_split.probe_video_dimensions", return_value=(1920, 1080)):
        assert is_vertical_video("horizontal.mp4") is False

def test_is_vertical_video_false_for_square():
    with patch("scripts.gaming_split.probe_video_dimensions", return_value=(1080, 1080)):
        assert is_vertical_video("square.mp4") is False

def test_is_vertical_video_missing_file():
    assert is_vertical_video("non_existent_file.mp4") is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_gaming_vertical_source.py -v`  
Expected: FAIL with `ImportError: cannot import name 'is_vertical_video'`

- [ ] **Step 3: Implement `is_vertical_video` and backend bypass**

In `scripts/gaming_split.py`:
```python
def is_vertical_video(video_path: str) -> bool:
    """Returns True if the video exists and has width < height (portrait/vertical)."""
    if not video_path or not os.path.exists(video_path):
        return False
    w, h = probe_video_dimensions(video_path)
    return w > 0 and h > 0 and w < h
```

In `main_improved.py`:
Before Step 5 (Edit Video / Preserve Original Framing):
```python
        # Check if source video is already vertical (e.g. 9:16)
        from scripts.gaming_split import is_vertical_video
        is_already_vertical = is_vertical_video(input_video)

        if is_already_vertical and args.pipeline_mode == "gaming":
            print(i18n("Source video is already vertical (portrait). Preserving original framing without gaming split..."))
            args.orientation = "16:9"  # Signals preserve_original_scale
            face_mode = "none"
```
And in Step 5:
```python
        if workflow_choice != "3":
            if is_already_vertical or face_mode == "none":
                print(i18n("Preserving original source framing..."), flush=True)
                preserve_segments.preserve_original_scale(project_folder=project_folder)
            elif args.orientation == "9:16_gaming_split":
                ...
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_gaming_vertical_source.py -v`  
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add scripts/gaming_split.py main_improved.py tests/test_gaming_vertical_source.py
git commit -m "feat(gaming): add is_vertical_video probe and auto-bypass gaming split for portrait sources"
```

---

### Task 2: Backend Job Schema & CLI Auto-Routing Safety (`webui/backend/schemas/jobs.py`)

**Files:**
- Modify: `webui/backend/schemas/jobs.py`
- Test: `tests/test_gaming_vertical_cli.py`

**Interfaces:**
- Updates `JobRunRequest.to_cli_args()`:
  - If `is_vertical_video(self.video_path)` is True, does NOT force `--orientation 9:16_gaming_split`.
  - Instead passes `--orientation 16:9` and `--face-mode none` to preserve original vertical framing.

- [ ] **Step 1: Write the failing tests for schema auto-routing of vertical sources**

Create `tests/test_gaming_vertical_cli.py`:
```python
from unittest.mock import patch
from webui.backend.schemas.jobs import JobRunRequest

def test_job_run_request_keeps_framing_for_vertical_source(tmp_path):
    dummy_video = tmp_path / "vertical.mp4"
    dummy_video.write_bytes(b"dummy")

    with patch("scripts.gaming_split.is_vertical_video", return_value=True):
        req = JobRunRequest(
            video_path=str(dummy_video),
            pipeline_mode="gaming",
            orientation="9:16"
        )
        cmd = req.to_cli_args("python", "main_improved.py")
        
        # When source is vertical, it should NOT route to 9:16_gaming_split
        assert "9:16_gaming_split" not in cmd
        assert "--face-mode" in cmd
        assert "none" in cmd
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_gaming_vertical_cli.py -v`  
Expected: FAIL with `AssertionError: assert '9:16_gaming_split' not in cmd`

- [ ] **Step 3: Update `webui/backend/schemas/jobs.py`**

In `webui/backend/schemas/jobs.py`:
```python
        # Auto-route orientation for gaming mode:
        # If source video is already vertical (W < H), preserve framing with face_mode none.
        # Otherwise for horizontal video, route default 9:16 to 9:16_gaming_split.
        from scripts.gaming_split import is_vertical_video
        source_is_vertical = bool(self.video_path and is_vertical_video(self.video_path))

        if self.orientation:
            orient = self.orientation
            if self.pipeline_mode == "gaming":
                if source_is_vertical:
                    orient = "16:9"  # preserve original framing
                    args.extend(["--face-mode", "none"])
                elif orient == "9:16":
                    orient = "9:16_gaming_split"
            cmd.extend(["--orientation", str(orient)])
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_gaming_vertical_cli.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add webui/backend/schemas/jobs.py tests/test_gaming_vertical_cli.py
git commit -m "feat(jobs): auto-route vertical video inputs to preserved framing in JobRunRequest"
```

---

### Task 3: Frontend WebUI Vertical Video Detection & Badge (`GeneratorTab.tsx`)

**Files:**
- Modify: `webui/frontend/src/components/GeneratorTab.tsx`
- Test: `webui/frontend/src/test/tabs.test.tsx`

**Interfaces:**
- Inspects `metadata.width` and `metadata.height`:
  - When `metadata.width < metadata.height`:
    - Shows info banner: "Vertical 9:16 Video Detected — Source framing will be preserved automatically."
    - Hides `GamingCropEditor` (dual-cropping is unnecessary for vertical video).
    - Sets framing mode to preserved framing.

- [ ] **Step 1: Write the failing tests for vertical video detection in WebUI**

Edit `webui/frontend/src/test/tabs.test.tsx`:
```tsx
it('detects vertical video metadata and displays preservation indicator', async () => {
  // Test that when metadata has width < height, indicator is displayed
  // and dual crop editor is hidden
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pnpm test tabs.test.tsx`  
Expected: FAIL

- [ ] **Step 3: Implement vertical video detection state in `GeneratorTab.tsx`**

In `webui/frontend/src/components/GeneratorTab.tsx`:
```tsx
const isVerticalSource = metadata ? metadata.width < metadata.height : false;
```
Render banner when `isVerticalSource && pipelineMode === 'gaming'`:
```tsx
{isVerticalSource && pipelineMode === 'gaming' && (
  <div className="p-3 bg-blue-950/40 border border-blue-800/60 rounded-lg text-xs text-blue-200 flex items-center gap-2">
    <span>📱</span>
    <span><strong>Vertical Video Detected ({metadata?.width}x{metadata?.height}):</strong> Source framing will be preserved automatically without cropping.</span>
  </div>
)}
```
And condition `GamingCropEditor`:
```tsx
{orientation === '9:16_gaming_split' && !isVerticalSource && (
  <GamingCropEditor ... />
)}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pnpm test tabs.test.tsx`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add webui/frontend/src/components/GeneratorTab.tsx webui/frontend/src/test/tabs.test.tsx
git commit -m "feat(ui): display vertical source detected notice and hide dual crop editor"
```

---

### Task 4: End-to-End Integration Test for Vertical Video (`tests/test_gaming_vertical_e2e.py`)

**Files:**
- Create: `tests/test_gaming_vertical_e2e.py`

**Interfaces:**
- End-to-end test verifying:
  - Input: synthetic vertical video ($1080 \times 1920$).
  - Pipeline mode: `gaming`.
  - Workflow: 1 (Full) and 2 (Cut Only).
  - Asserts output video exists, has dimensions $1080 \times 1920$, framing is preserved without split artifacts, and subtitle burning succeeds.

- [ ] **Step 1: Write the end-to-end vertical video test**

Create `tests/test_gaming_vertical_e2e.py`:
```python
import os
import json
import subprocess
import pytest
from scripts.gaming_split import is_vertical_video, probe_video_dimensions

def test_vertical_video_pipeline_e2e_preserves_dimensions(tmp_path):
    # Generates a synthetic 5-second 1080x1920 vertical video via ffmpeg testsrc
    video_path = tmp_path / "vertical_test.mp4"
    subprocess.run([
        "ffmpeg", "-y", "-f", "lavfi",
        "-i", "testsrc=size=1080x1920:rate=30",
        "-f", "lavfi", "-i", "sine=frequency=1000:sample_rate=16000",
        "-t", "5",
        "-c:v", "libx264", "-c:a", "aac",
        str(video_path)
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)

    assert is_vertical_video(str(video_path)) is True
    w, h = probe_video_dimensions(str(video_path))
    assert w == 1080
    assert h == 1920
```

- [ ] **Step 2: Run test to verify it passes**

Run: `pytest tests/test_gaming_vertical_e2e.py -v`  
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add tests/test_gaming_vertical_e2e.py
git commit -m "test(gaming): add e2e integration test verifying vertical video dimensions preservation"
```
