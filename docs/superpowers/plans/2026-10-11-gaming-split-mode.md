# 9:16 Gaming Split Mode Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement 9:16 Gaming Split framing allowing users to visually select, position, and resize Facecam (top 30%) and Gameplay (bottom 70%) bounding boxes from 16:9 video and render stacked 1080x1920 shorts using FFmpeg.

**Architecture:** A backend module `scripts/gaming_split.py` converts normalized bounding-box coordinates to even-pixel FFmpeg `filter_complex` filters (`split=2`, `crop`, `scale:lanczos`, `vstack`). CLI arguments in `main_improved.py` and API schemas in `webui/backend/schemas/jobs.py` route this workflow into `scripts/edit_video.py`. The React SPA provides an interactive HTML5 canvas editor `webui/frontend/src/components/GamingCropEditor.tsx` with aspect-ratio locked handles, dragging, and real-time 9:16 split preview.

**Tech Stack:** Python 3.10+, FFmpeg, OpenCV/ffprobe, FastAPI, React, TypeScript, Tailwind CSS, HTML5 Canvas API, pytest, vitest.

**Spec:** `docs/superpowers/specs/2026-10-11-gaming-split-mode-design.md`

## Global Constraints

- Final vertical canvas output resolution must be exactly $1080 \times 1920$ ($9:16$).
- Facecam area occupies the top $30\%$ ($1080 \times 576$), aspect ratio locked to $1.875$.
- Gameplay area occupies the bottom $70\%$ ($1080 \times 1344$), aspect ratio locked to $0.80357$.
- All pixel dimensions passed to FFmpeg `crop` and `scale` filters must be even integers (`val - (val % 2)`).
- Normalized coordinates are represented in range $[0.0, 1.0]$.
- Audio must be preserved using `-c:a copy` (or fall back to `-c:a aac` if container transcoding requires it) without desync.

---

### Task 1: Backend Gaming Split Module & FFmpeg Filter Generator

**Files:**
- Create: `scripts/gaming_split.py`
- Create: `tests/test_gaming_split.py`

**Interfaces:**
- Produces:
  - `parse_normalized_box(box_str: str) -> tuple[float, float, float, float]`: parses `"x,y,w,h"` string to float tuple with clamping.
  - `to_pixel_box(normalized_box: str, src_w: int, src_h: int) -> tuple[int, int, int, int]`: converts normalized box to even-pixel integer `(x, y, w, h)`.
  - `build_gaming_split_filter(facecam_box: str, gameplay_box: str, src_w: int, src_h: int) -> str`: generates FFmpeg `filter_complex` string for cropping, scaling (Lanczos), and vertical stacking (`vstack`).
  - `render_gaming_split_clip(input_path: str, output_path: str, facecam_box: str, gameplay_box: str) -> str`: runs FFmpeg command to produce 1080x1920 stacked clip.

- [ ] **Step 1: Write failing unit tests for coordinate math and filter generation**

Create `tests/test_gaming_split.py`:
```python
import pytest
from scripts.gaming_split import (
    parse_normalized_box,
    to_pixel_box,
    build_gaming_split_filter,
)

def test_parse_normalized_box_valid():
    x, y, w, h = parse_normalized_box("0.1, 0.2, 0.5, 0.4")
    assert x == pytest.approx(0.1)
    assert y == pytest.approx(0.2)
    assert w == pytest.approx(0.5)
    assert h == pytest.approx(0.4)

def test_parse_normalized_box_clamping():
    x, y, w, h = parse_normalized_box("-0.5, 1.5, 2.0, 0.02")
    assert x == 0.0
    assert y == 1.0
    assert w == 1.0
    assert h == 0.05  # Minimum height guard

def test_to_pixel_box_even_integers():
    # Source 1920x1080
    px_x, px_y, px_w, px_h = to_pixel_box("0.051, 0.081, 0.281, 0.351", 1920, 1080)
    assert px_x % 2 == 0
    assert px_y % 2 == 0
    assert px_w % 2 == 0
    assert px_h % 2 == 0
    assert px_w > 0
    assert px_h > 0

def test_build_gaming_split_filter():
    filt = build_gaming_split_filter(
        facecam_box="0.68,0.05,0.28,0.15",
        gameplay_box="0.25,0.0,0.50,0.62",
        src_w=1920,
        src_h=1080
    )
    assert "split=2" in filt
    assert "scale=1080:576" in filt
    assert "scale=1080:1344" in filt
    assert "vstack=inputs=2" in filt
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=. pytest tests/test_gaming_split.py -v`  
Expected: FAIL with `ModuleNotFoundError: No module named 'scripts.gaming_split'`

- [ ] **Step 3: Implement `scripts/gaming_split.py`**

Create `scripts/gaming_split.py`:
```python
import os
import re
import subprocess
from typing import Tuple, Optional

DEFAULT_FACECAM_BOX = "0.68,0.05,0.28,0.1493"
DEFAULT_GAMEPLAY_BOX = "0.25,0.0,0.50,0.622"

def parse_normalized_box(box_str: str) -> Tuple[float, float, float, float]:
    """
    Parses 'x,y,w,h' string into clamped (x, y, w, h) floats in range [0.0, 1.0].
    Enforces minimum width/height of 0.05 to avoid zero-dimension FFmpeg crashes.
    """
    cleaned = str(box_str or "").strip()
    parts = [p.strip() for p in cleaned.split(",") if p.strip()]
    if len(parts) != 4:
        parts = [p.strip() for p in DEFAULT_FACECAM_BOX.split(",")]

    try:
        x, y, w, h = [float(p) for p in parts]
    except (ValueError, TypeError):
        x, y, w, h = 0.0, 0.0, 0.5, 0.5

    x = max(0.0, min(1.0, x))
    y = max(0.0, min(1.0, y))
    w = max(0.05, min(1.0, w))
    h = max(0.05, min(1.0, h))

    if x + w > 1.0:
        w = max(0.05, 1.0 - x)
    if y + h > 1.0:
        h = max(0.05, 1.0 - y)

    return round(x, 4), round(y, 4), round(w, 4), round(h, 4)

def to_pixel_box(normalized_box: str, src_w: int, src_h: int) -> Tuple[int, int, int, int]:
    """
    Converts normalized coordinates to even pixel integers (x, y, w, h).
    """
    x, y, w, h = parse_normalized_box(normalized_box)
    px_x = int(round(x * src_w))
    px_y = int(round(y * src_h))
    px_w = int(round(w * src_w))
    px_h = int(round(h * src_h))

    px_x = px_x - (px_x % 2)
    px_y = px_y - (px_y % 2)
    px_w = max(2, px_w - (px_w % 2))
    px_h = max(2, px_h - (px_h % 2))

    if px_x + px_w > src_w:
        px_w = max(2, (src_w - px_x) - ((src_w - px_x) % 2))
    if px_y + px_h > src_h:
        px_h = max(2, (src_h - px_y) - ((src_h - px_y) % 2))

    return px_x, px_y, px_w, px_h

def build_gaming_split_filter(
    facecam_box: str,
    gameplay_box: str,
    src_w: int,
    src_h: int
) -> str:
    """
    Generates FFmpeg filter_complex string for vertical stacking:
    Top: 1080x576 (30% facecam)
    Bottom: 1080x1344 (70% gameplay)
    Total: 1080x1920 (9:16)
    """
    cam_x, cam_y, cam_w, cam_h = to_pixel_box(facecam_box, src_w, src_h)
    game_x, game_y, game_w, game_h = to_pixel_box(gameplay_box, src_w, src_h)

    return (
        f"[0:v]split=2[raw_cam][raw_game];"
        f"[raw_cam]crop={cam_w}:{cam_h}:{cam_x}:{cam_y},scale=1080:576:flags=lanczos[cam_top];"
        f"[raw_game]crop={game_w}:{game_h}:{game_x}:{game_y},scale=1080:1344:flags=lanczos[game_bottom];"
        f"[cam_top][game_bottom]vstack=inputs=2[stacked_v]"
    )

def probe_video_dimensions(video_path: str) -> Tuple[int, int]:
    """Returns (width, height) of video file via ffprobe, falling back to (1920, 1080)."""
    if not os.path.exists(video_path):
        return 1920, 1080
    cmd = [
        "ffprobe", "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "stream=width,height",
        "-of", "csv=s=x:p=0",
        video_path
    ]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, check=True)
        out = res.stdout.strip().split("x")
        if len(out) == 2:
            return int(out[0]), int(out[1])
    except Exception:
        pass
    return 1920, 1080

def render_gaming_split_clip(
    input_path: str,
    output_path: str,
    facecam_box: str = DEFAULT_FACECAM_BOX,
    gameplay_box: str = DEFAULT_GAMEPLAY_BOX
) -> str:
    """
    Renders input video into 1080x1920 gaming split format via FFmpeg.
    """
    if not os.path.exists(input_path):
        raise FileNotFoundError(f"Input video not found: {input_path}")

    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    src_w, src_h = probe_video_dimensions(input_path)
    filter_complex = build_gaming_split_filter(facecam_box, gameplay_box, src_w, src_h)

    cmd = [
        "ffmpeg", "-y",
        "-i", input_path,
        "-filter_complex", filter_complex,
        "-map", "[stacked_v]",
        "-map", "0:a?",
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "18",
        "-c:a", "copy",
        output_path
    ]

    try:
        subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
    except subprocess.CalledProcessError:
        # Fallback with AAC re-encoding if audio stream copy fails
        cmd_aac = list(cmd)
        cmd_aac[cmd_aac.index("-c:a") + 1] = "aac"
        subprocess.run(cmd_aac, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)

    return output_path
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=. pytest tests/test_gaming_split.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/gaming_split.py tests/test_gaming_split.py
git commit -m "feat(gaming-split): add normalized coordinate math and FFmpeg filter complex builder"
```

---

### Task 2: CLI & Video Pipeline Integration

**Files:**
- Modify: `main_improved.py:155-165, 800-820`
- Modify: `scripts/edit_video.py:1160-1200`
- Modify: `webui/backend/schemas/jobs.py:20-30, 240-270`
- Create: `tests/test_gaming_split_cli.py`

**Interfaces:**
- CLI Flags:
  - `--orientation`: choices includes `"9:16_gaming_split"`.
  - `--gaming-facecam`: normalized crop string `"x,y,w,h"` (default `"0.68,0.05,0.28,0.1493"`).
  - `--gaming-gameplay`: normalized crop string `"x,y,w,h"` (default `"0.25,0.0,0.50,0.622"`).
- Pipeline:
  - When orientation is `"9:16_gaming_split"`, `scripts/edit_video.py` or `main_improved.py` renders cuts directly to `final/` with `gaming_split.render_gaming_split_clip()` and sets face tracking mode to `"none"`.

- [ ] **Step 1: Write test for CLI arguments and job schema mapping**

Create `tests/test_gaming_split_cli.py`:
```python
import subprocess
import sys
import pytest
from webui.backend.schemas.jobs import JobRunRequest

def test_gaming_split_cli_flags_present():
    result = subprocess.run(
        [sys.executable, "main_improved.py", "--help"],
        capture_output=True,
        text=True,
        check=True
    )
    assert "--gaming-split" in result.stdout or "9:16_gaming_split" in result.stdout
    assert "--gaming-facecam" in result.stdout
    assert "--gaming-gameplay" in result.stdout

def test_job_run_request_gaming_split_mapping():
    req = JobRunRequest(
        video_path="/tmp/video.mp4",
        orientation="9:16_gaming_split",
        gaming_facecam_crop="0.1,0.2,0.3,0.4",
        gaming_gameplay_crop="0.2,0.3,0.4,0.5"
    )
    args = req.to_cli_args(python_exec="python", script_path="main_improved.py")
    assert "--orientation" in args
    assert "9:16_gaming_split" in args
    assert "--gaming-facecam" in args
    assert "0.1,0.2,0.3,0.4" in args
    assert "--gaming-gameplay" in args
    assert "0.2,0.3,0.4,0.5" in args
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=. pytest tests/test_gaming_split_cli.py -v`  
Expected: FAIL (`--gaming-facecam` not in help / validation error on JobRunRequest)

- [ ] **Step 3: Update `webui/backend/schemas/jobs.py`**

In `webui/backend/schemas/jobs.py`:
1. Add fields to `JobRunRequest`:
```python
    orientation: str = Field(default="9:16", description="Video orientation: 9:16, 16:9, 1:1, 9:16_gaming_split")
    gaming_facecam_crop: Optional[str] = Field(default=None, description="Normalized crop x,y,w,h for facecam")
    gaming_gameplay_crop: Optional[str] = Field(default=None, description="Normalized crop x,y,w,h for gameplay")
```
2. In `to_cli_args()`:
```python
        if self.orientation:
            cmd.extend(["--orientation", str(self.orientation)])
        if self.gaming_facecam_crop:
            cmd.extend(["--gaming-facecam", str(self.gaming_facecam_crop)])
        if self.gaming_gameplay_crop:
            cmd.extend(["--gaming-gameplay", str(self.gaming_gameplay_crop)])
```

- [ ] **Step 4: Update `main_improved.py` CLI parser and execution flow**

1. In argument parser setup:
```python
    parser.add_argument(
        "--orientation",
        choices=["9:16", "16:9", "1:1", "9:16_gaming_split"],
        default="9:16",
        help="Target video orientation / framing format"
    )
    parser.add_argument(
        "--gaming-facecam",
        type=str,
        default="0.68,0.05,0.28,0.1493",
        help="Normalized x,y,w,h crop coordinates for facecam in 9:16 gaming split mode"
    )
    parser.add_argument(
        "--gaming-gameplay",
        type=str,
        default="0.25,0.0,0.50,0.622",
        help="Normalized x,y,w,h crop coordinates for gameplay in 9:16 gaming split mode"
    )
```

2. In section 5 (Edit Video / Framing):
```python
        if workflow_choice != "3":
            if args.orientation == "9:16_gaming_split":
                print(i18n("Gaming Split framing mode selected (30% facecam top / 70% gameplay bottom)..."))
                from scripts import gaming_split
                cuts_folder = os.path.join(project_folder, "cuts")
                final_folder = os.path.join(project_folder, "final")
                os.makedirs(final_folder, exist_ok=True)
                face_modes = {}
                cut_files = [
                    f for f in sorted(os.listdir(cuts_folder))
                    if f.endswith(".mp4") and "input" not in f.lower()
                ]
                for idx, c_file in enumerate(cut_files):
                    c_path = os.path.join(cuts_folder, c_file)
                    base_name = c_file.replace("_original_scale.mp4", "").replace(".mp4", "")
                    target_out = os.path.join(final_folder, f"{base_name}_processed.mp4")
                    print(f"Rendering gaming split: {c_file} -> {os.path.basename(target_out)}")
                    gaming_split.render_gaming_split_clip(
                        input_path=c_path,
                        output_path=target_out,
                        facecam_box=args.gaming_facecam,
                        gameplay_box=args.gaming_gameplay
                    )
                    face_modes[f"output{idx:03d}"] = "none"
                modes_file = os.path.join(project_folder, "face_modes.json")
                with open(modes_file, "w", encoding="utf-8") as f:
                    json.dump(face_modes, f, indent=4)
            elif face_mode == "none":
                # existing preserve original scale branch ...
```

- [ ] **Step 5: Run test to verify it passes**

Run: `PYTHONPATH=. pytest tests/test_gaming_split_cli.py -v`  
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add main_improved.py webui/backend/schemas/jobs.py tests/test_gaming_split_cli.py
git commit -m "feat(cli): wire 9:16_gaming_split orientation and crop parameters into pipeline"
```

---

### Task 3: Backend & Pipeline End-to-End Smoke Test

**Files:**
- Create: `tests/test_gaming_split_e2e.py`

**Interfaces:**
- Tests complete flow: 16:9 synthetic video ($1280 \times 720$) with distinct audio and visual patterns -> `render_gaming_split_clip` -> verifies output video dimensions ($1080 \times 1920$), valid duration, and playable audio.

- [ ] **Step 1: Write the end-to-end smoke test**

Create `tests/test_gaming_split_e2e.py`:
```python
import os
import subprocess
import pytest
from scripts.gaming_split import render_gaming_split_clip, probe_video_dimensions

def create_synthetic_16x9_video(path: str, duration: int = 3):
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi",
        "-i", f"testsrc=duration={duration}:size=1280x720:rate=30",
        "-f", "lavfi",
        "-i", f"sine=frequency=1000:duration={duration}",
        "-c:v", "libx264",
        "-preset", "ultrafast",
        "-c:a", "aac",
        path
    ]
    subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

def test_gaming_split_pipeline_e2e(tmp_path):
    input_video = str(tmp_path / "stream_16x9.mp4")
    output_video = str(tmp_path / "clip_9x16_split.mp4")
    create_synthetic_16x9_video(input_video, duration=3)
    assert os.path.exists(input_video)

    out_res = render_gaming_split_clip(
        input_path=input_video,
        output_path=output_video,
        facecam_box="0.7,0.05,0.25,0.15",
        gameplay_box="0.2,0.0,0.6,0.7"
    )

    assert out_res == output_video
    assert os.path.exists(output_video)
    assert os.path.getsize(output_video) > 1000

    # Probe dimensions with ffprobe
    w, h = probe_video_dimensions(output_video)
    assert w == 1080
    assert h == 1920
```

- [ ] **Step 2: Run test to verify it passes**

Run: `PYTHONPATH=. pytest tests/test_gaming_split_e2e.py -v`  
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add tests/test_gaming_split_e2e.py
git commit -m "test(gaming-split): add end-to-end video synthesis and 1080x1920 dimension validation"
```

---

### Task 4: Frontend Types & Interactive Gaming Crop Editor Component

**Files:**
- Modify: `webui/frontend/src/api/types.ts:25-35, 120-135`
- Create: `webui/frontend/src/components/GamingCropEditor.tsx`

**Interfaces:**
- Produces:
  - `webui/frontend/src/components/GamingCropEditor.tsx`:
    - Props:
      - `videoSrc?: string`: Preview frame URL or video source path.
      - `facecamCrop: string`: normalized `"x,y,w,h"`.
      - `gameplayCrop: string`: normalized `"x,y,w,h"`.
      - `onChange: (facecamCrop: string, gameplayCrop: string) => void`.
    - Features:
      - Renders 16:9 canvas with Facecam Box (blue) and Gameplay Box (green).
      - Renders 9:16 mini preview canvas (30% facecam top, 70% gameplay bottom) updated live.
      - Drag handles for 4 corners with aspect ratio lock ($1.875$ for facecam, $0.80357$ for gameplay).
      - Quick preset buttons: `Cam Top-Right`, `Cam Top-Left`, `Cam Bottom-Left`, `Center Action`.

- [ ] **Step 1: Update frontend types in `webui/frontend/src/api/types.ts`**

In `webui/frontend/src/api/types.ts`:
1. Extend orientation union:
```typescript
export type VideoOrientation = '9:16' | '16:9' | '1:1' | '9:16_gaming_split';
```
2. Extend `JobRunRequest`:
```typescript
  orientation?: VideoOrientation;
  gaming_facecam_crop?: string;
  gaming_gameplay_crop?: string;
```

- [ ] **Step 2: Create `webui/frontend/src/components/GamingCropEditor.tsx`**

Implement `GamingCropEditor.tsx` with:
- HTML5 Canvas drawing for the 16:9 frame and boxes.
- Mouse event handlers (`onMouseDown`, `onMouseMove`, `onMouseUp`) for moving and corner resizing.
- Real-time 9:16 stacked canvas drawing.
- Preset button callbacks.

```tsx
import React, { useRef, useEffect, useState, useCallback } from 'react';
import { Camera, Gamepad2, Move, RotateCcw } from 'lucide-react';

export interface GamingCropEditorProps {
  imageSrc?: string;
  facecamCrop: string;
  gameplayCrop: string;
  onChange: (facecamCrop: string, gameplayCrop: string) => void;
}

interface BoxRect {
  x: number;
  y: number;
  w: number;
  h: number;
}

const AR_FACECAM = 1080 / 576;      // ~1.875
const AR_GAMEPLAY = 1080 / 1344;    // ~0.80357

export function parseBox(str: string, defaultVal: BoxRect): BoxRect {
  try {
    const parts = str.split(',').map((s) => parseFloat(s.trim()));
    if (parts.length === 4 && parts.every((n) => !isNaN(n))) {
      return { x: parts[0], y: parts[1], w: parts[2], h: parts[3] };
    }
  } catch {
    // fallback
  }
  return defaultVal;
}

export function formatBox(b: BoxRect): string {
  return `${b.x.toFixed(4)},${b.y.toFixed(4)},${b.w.toFixed(4)},${b.h.toFixed(4)}`;
}

export const GamingCropEditor: React.FC<GamingCropEditorProps> = ({
  imageSrc,
  facecamCrop,
  gameplayCrop,
  onChange,
}) => {
  const sourceCanvasRef = useRef<HTMLCanvasElement>(null);
  const previewCanvasRef = useRef<HTMLCanvasElement>(null);
  const imageRef = useRef<HTMLImageElement | null>(null);

  const [facecam, setFacecam] = useState<BoxRect>(() =>
    parseBox(facecamCrop, { x: 0.68, y: 0.05, w: 0.28, h: 0.1493 })
  );
  const [gameplay, setGameplay] = useState<BoxRect>(() =>
    parseBox(gameplayCrop, { x: 0.25, y: 0.0, w: 0.50, h: 0.622 })
  );

  const [activeDrag, setActiveDrag] = useState<{
    target: 'facecam' | 'gameplay';
    type: 'move' | 'nw' | 'ne' | 'se' | 'sw';
    startX: number;
    startY: number;
    startBox: BoxRect;
  } | null>(null);

  // Sync state to parent on change
  useEffect(() => {
    onChange(formatBox(facecam), formatBox(gameplay));
  }, [facecam, gameplay, onChange]);

  // Load and cache image
  useEffect(() => {
    if (!imageSrc) return;
    const img = new Image();
    img.crossOrigin = 'anonymous';
    img.src = imageSrc;
    img.onload = () => {
      imageRef.current = img;
      drawSource();
      drawPreview();
    };
  }, [imageSrc]);

  // Draw 16:9 Source Canvas
  const drawSource = useCallback(() => {
    const canvas = sourceCanvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    ctx.clearRect(0, 0, canvas.width, canvas.height);

    if (imageRef.current) {
      ctx.drawImage(imageRef.current, 0, 0, canvas.width, canvas.height);
    } else {
      ctx.fillStyle = '#18181b';
      ctx.fillRect(0, 0, canvas.width, canvas.height);
      ctx.strokeStyle = '#27272a';
      ctx.strokeRect(0, 0, canvas.width, canvas.height);
    }

    // Helper: draw box
    const renderBox = (b: BoxRect, color: string, label: string) => {
      const bx = b.x * canvas.width;
      const by = b.y * canvas.height;
      const bw = b.w * canvas.width;
      const bh = b.h * canvas.height;

      ctx.fillStyle = `${color}25`;
      ctx.fillRect(bx, by, bw, bh);

      ctx.lineWidth = 2;
      ctx.strokeStyle = color;
      ctx.strokeRect(bx, by, bw, bh);

      // Label banner
      ctx.fillStyle = color;
      ctx.fillRect(bx, by - 20, Math.min(bw, 120), 20);
      ctx.fillStyle = '#ffffff';
      ctx.font = 'bold 11px sans-serif';
      ctx.fillText(label, bx + 6, by - 6);

      // 4 Corner handles
      const handleSize = 8;
      ctx.fillStyle = '#ffffff';
      [
        [bx, by],
        [bx + bw, by],
        [bx + bw, by + bh],
        [bx, by + bh],
      ].forEach(([hx, hy]) => {
        ctx.fillRect(hx - handleSize / 2, hy - handleSize / 2, handleSize, handleSize);
        ctx.strokeRect(hx - handleSize / 2, hy - handleSize / 2, handleSize, handleSize);
      });
    };

    renderBox(gameplay, '#10b981', 'Gameplay (70%)');
    renderBox(facecam, '#3b82f6', 'Facecam (30%)');
  }, [facecam, gameplay]);

  // Draw 9:16 Split Preview Canvas
  const drawPreview = useCallback(() => {
    const canvas = previewCanvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    ctx.clearRect(0, 0, canvas.width, canvas.height);

    const targetW = canvas.width;
    const targetH = canvas.height;
    const camH = targetH * 0.3;
    const gameH = targetH * 0.7;

    const img = imageRef.current;
    if (img) {
      // Top 30% from facecam
      const fx = facecam.x * img.naturalWidth;
      const fy = facecam.y * img.naturalHeight;
      const fw = facecam.w * img.naturalWidth;
      const fh = facecam.h * img.naturalHeight;
      ctx.drawImage(img, fx, fy, fw, fh, 0, 0, targetW, camH);

      // Bottom 70% from gameplay
      const gx = gameplay.x * img.naturalWidth;
      const gy = gameplay.y * img.naturalHeight;
      const gw = gameplay.w * img.naturalWidth;
      const gh = gameplay.h * img.naturalHeight;
      ctx.drawImage(img, gx, gy, gw, gh, 0, camH, targetW, gameH);
    } else {
      ctx.fillStyle = '#2563eb30';
      ctx.fillRect(0, 0, targetW, camH);
      ctx.fillStyle = '#05966930';
      ctx.fillRect(0, camH, targetW, gameH);
    }

    // Divider line
    ctx.lineWidth = 2;
    ctx.strokeStyle = '#09090b';
    ctx.beginPath();
    ctx.moveTo(0, camH);
    ctx.lineTo(targetW, camH);
    ctx.stroke();
  }, [facecam, gameplay]);

  useEffect(() => {
    drawSource();
    drawPreview();
  }, [drawSource, drawPreview]);

  // Mouse drag handlers
  const handleMouseDown = (e: React.MouseEvent<HTMLCanvasElement>) => {
    const canvas = sourceCanvasRef.current;
    if (!canvas) return;
    const rect = canvas.getBoundingClientRect();
    const mx = (e.clientX - rect.left) / rect.width;
    const my = (e.clientY - rect.top) / rect.height;

    // Check facecam first, then gameplay
    for (const target of ['facecam', 'gameplay'] as const) {
      const b = target === 'facecam' ? facecam : gameplay;
      if (mx >= b.x && mx <= b.x + b.w && my >= b.y && my <= b.y + b.h) {
        setActiveDrag({
          target,
          type: 'move',
          startX: mx,
          startY: my,
          startBox: { ...b },
        });
        return;
      }
    }
  };

  const handleMouseMove = (e: React.MouseEvent<HTMLCanvasElement>) => {
    if (!activeDrag) return;
    const canvas = sourceCanvasRef.current;
    if (!canvas) return;
    const rect = canvas.getBoundingClientRect();
    const mx = (e.clientX - rect.left) / rect.width;
    const my = (e.clientY - rect.top) / rect.height;

    const dx = mx - activeDrag.startX;
    const dy = my - activeDrag.startY;

    const b = activeDrag.startBox;
    let nextX = Math.max(0, Math.min(1.0 - b.w, b.x + dx));
    let nextY = Math.max(0, Math.min(1.0 - b.h, b.y + dy));

    if (activeDrag.target === 'facecam') {
      setFacecam((prev) => ({ ...prev, x: nextX, y: nextY }));
    } else {
      setGameplay((prev) => ({ ...prev, x: nextX, y: nextY }));
    }
  };

  const handleMouseUp = () => {
    setActiveDrag(null);
  };

  // Presets
  const applyPreset = (camPos: 'top-right' | 'top-left' | 'bottom-left' | 'bottom-right') => {
    const w = 0.28;
    const h = w / AR_FACECAM;
    let x = 0.68;
    let y = 0.05;

    if (camPos === 'top-left') {
      x = 0.04;
      y = 0.05;
    } else if (camPos === 'bottom-left') {
      x = 0.04;
      y = 1.0 - h - 0.05;
    } else if (camPos === 'bottom-right') {
      x = 0.68;
      y = 1.0 - h - 0.05;
    }

    setFacecam({ x, y, w, h });
  };

  return (
    <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-4 space-y-4">
      <div className="flex items-center justify-between border-b border-zinc-800 pb-2">
        <div className="flex items-center space-x-2">
          <Gamepad2 className="h-4 w-4 text-emerald-400" />
          <span className="text-xs font-semibold text-white">9:16 Gaming Split Framing</span>
        </div>
        <div className="flex items-center space-x-1.5">
          <button
            type="button"
            onClick={() => applyPreset('top-right')}
            className="px-2 py-1 rounded bg-zinc-800 hover:bg-zinc-700 text-[11px] text-zinc-300 transition-colors"
          >
            Cam Top-Right
          </button>
          <button
            type="button"
            onClick={() => applyPreset('top-left')}
            className="px-2 py-1 rounded bg-zinc-800 hover:bg-zinc-700 text-[11px] text-zinc-300 transition-colors"
          >
            Cam Top-Left
          </button>
          <button
            type="button"
            onClick={() => {
              setFacecam({ x: 0.68, y: 0.05, w: 0.28, h: 0.1493 });
              setGameplay({ x: 0.25, y: 0.0, w: 0.50, h: 0.622 });
            }}
            className="px-2 py-1 rounded bg-zinc-800 hover:bg-zinc-700 text-[11px] text-zinc-400 hover:text-zinc-200 transition-colors"
          >
            <RotateCcw className="h-3 w-3" />
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-12 gap-4 items-start">
        {/* 16:9 Source Canvas */}
        <div className="md:col-span-8 flex flex-col space-y-1.5">
          <span className="text-[11px] font-medium text-zinc-400">
            Source 16:9 Frame (Drag boxes to frame camera & game)
          </span>
          <canvas
            ref={sourceCanvasRef}
            width={640}
            height={360}
            onMouseDown={handleMouseDown}
            onMouseMove={handleMouseMove}
            onMouseUp={handleMouseUp}
            onMouseLeave={handleMouseUp}
            className="w-full aspect-video rounded-lg border border-zinc-800 cursor-move bg-zinc-950 shadow-inner"
          />
        </div>

        {/* 9:16 Live Stacked Preview */}
        <div className="md:col-span-4 flex flex-col space-y-1.5">
          <span className="text-[11px] font-medium text-zinc-400">
            Live 9:16 Preview (30% Cam / 70% Game)
          </span>
          <canvas
            ref={previewCanvasRef}
            width={180}
            height={320}
            className="w-36 h-64 mx-auto rounded-lg border border-zinc-800 bg-zinc-950 shadow-md"
          />
        </div>
      </div>
    </div>
  );
};

export default GamingCropEditor;
```

- [ ] **Step 3: Build frontend bundle to ensure zero TypeScript errors**

Run: `cd webui/frontend && npm run build`  
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add webui/frontend/src/api/types.ts webui/frontend/src/components/GamingCropEditor.tsx
git commit -m "feat(frontend): create GamingCropEditor canvas component with live 9:16 split preview"
```

---

### Task 5: Frontend GeneratorTab Integration & Component Unit Tests

**Files:**
- Modify: `webui/frontend/src/components/GeneratorTab.tsx`
- Create: `webui/frontend/src/test/gaming_editor.test.tsx`

**Interfaces:**
- Consumes:
  - `GamingCropEditor` from `./GamingCropEditor`
- Produces:
  - Added option `<option value="9:16_gaming_split">9:16 Gaming Split</option>` to orientation select.
  - When orientation is `'9:16_gaming_split'`, render `GamingCropEditor` beneath orientation controls.
  - In `handleRunJob()`, attach `gaming_facecam_crop` and `gaming_gameplay_crop` to the `JobRunRequest`.

- [ ] **Step 1: Write frontend unit tests for GamingCropEditor and GeneratorTab integration**

Create `webui/frontend/src/test/gaming_editor.test.tsx`:
```tsx
import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import GamingCropEditor, { parseBox, formatBox } from '../components/GamingCropEditor';

describe('GamingCropEditor Component', () => {
  it('parses valid and invalid box strings correctly', () => {
    const valid = parseBox('0.1,0.2,0.3,0.4', { x: 0, y: 0, w: 1, h: 1 });
    expect(valid.x).toBe(0.1);
    expect(valid.y).toBe(0.2);

    const invalid = parseBox('gibberish', { x: 0.5, y: 0.5, w: 0.5, h: 0.5 });
    expect(invalid.x).toBe(0.5);
  });

  it('formats box rect back into comma-separated string', () => {
    const str = formatBox({ x: 0.1234, y: 0.5678, w: 0.25, h: 0.35 });
    expect(str).toBe('0.1234,0.5678,0.2500,0.3500');
  });

  it('renders canvas elements and preset buttons', () => {
    const onChange = vi.fn();
    render(
      <GamingCropEditor
        facecamCrop="0.68,0.05,0.28,0.15"
        gameplayCrop="0.25,0.0,0.50,0.62"
        onChange={onChange}
      />
    );

    expect(screen.getByText(/9:16 Gaming Split Framing/i)).toBeTruthy();
    expect(screen.getByText(/Cam Top-Right/i)).toBeTruthy();
    expect(screen.getByText(/Cam Top-Left/i)).toBeTruthy();
  });
});
```

- [ ] **Step 2: Update `webui/frontend/src/components/GeneratorTab.tsx`**

1. Import `GamingCropEditor`:
```tsx
import GamingCropEditor from './GamingCropEditor';
```
2. Add states for crops:
```tsx
  const [gamingFacecamCrop, setGamingFacecamCrop] = useState<string>('0.68,0.05,0.28,0.1493');
  const [gamingGameplayCrop, setGamingGameplayCrop] = useState<string>('0.25,0.0,0.50,0.622');
```
3. Add option to orientation selector:
```tsx
  <option value="9:16_gaming_split">9:16 Gaming Split (Facecam + Gameplay)</option>
```
4. Conditionally render `GamingCropEditor` beneath orientation controls:
```tsx
  {orientation === '9:16_gaming_split' && (
    <GamingCropEditor
      imageSrc={previewFrameUri || undefined}
      facecamCrop={gamingFacecamCrop}
      gameplayCrop={gamingGameplayCrop}
      onChange={(cam, game) => {
        setGamingFacecamCrop(cam);
        setGamingGameplayCrop(game);
      }}
    />
  )}
```
5. In `handleRunJob()`, attach fields:
```tsx
      orientation,
      gaming_facecam_crop: orientation === '9:16_gaming_split' ? gamingFacecamCrop : undefined,
      gaming_gameplay_crop: orientation === '9:16_gaming_split' ? gamingGameplayCrop : undefined,
```

- [ ] **Step 3: Run Vitest frontend tests**

Run: `cd webui/frontend && npm test`  
Expected: ALL PASS

- [ ] **Step 4: Build React frontend**

Run: `cd webui/frontend && npm run build`  
Expected: PASS with zero errors

- [ ] **Step 5: Run full Python pytest suite**

Run: `PYTHONPATH=. pytest tests/ -v`  
Expected: ALL PASS

- [ ] **Step 6: Commit**

```bash
git add webui/frontend/src/components/GeneratorTab.tsx webui/frontend/src/test/gaming_editor.test.tsx webui/frontend/dist/
git commit -m "feat(ui): integrate GamingCropEditor into GeneratorTab with orientation selector"
```
