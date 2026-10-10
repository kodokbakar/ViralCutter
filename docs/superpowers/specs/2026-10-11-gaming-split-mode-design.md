# Design Specification: 9:16 Gaming Split Framing (Facecam + Gameplay)

**Date:** 2026-10-11  
**Status:** Validated / Ready for Implementation Planning  
**Branch:** `feat/gaming-split`  
**Topic:** Interactive Dual Bounding-Box Selector (Facecam & Gameplay) for 16:9 to 9:16 Vertical Stacking Conversion  

---

## 1. Executive Summary & Goals

Gamers and streamers regularly record horizontal 16:9 gameplay footage containing a facecam overlay in one corner and gameplay across the rest of the screen. Converting this footage into viral 9:16 vertical shorts (TikTok, Reels, YouTube Shorts) usually requires tedious manual cropping in editing suites.

This feature introduces **9:16 Gaming Split**:
1. An interactive, low-latency visual canvas editor in the React WebUI (`GamingCropEditor.tsx`) allowing users to drag and resize two distinct bounding boxes on the 16:9 source frame:
   - **Box 1 (Facecam):** Frames the streamer's camera (aspect ratio locked to $1.875$).
   - **Box 2 (Gameplay):** Frames the active gameplay action (aspect ratio locked to $0.803$).
2. A real-time 9:16 stacked live preview ($30\%$ Facecam top / $70\%$ Gameplay bottom) rendered in-browser using HTML5 Canvas.
3. A high-performance FFmpeg `filter_complex` execution pipeline on the backend that crops, scales, and stacks both streams vertically into a native $1080 \times 1920$ canvas without quality distortion or audio desync.
4. Seamless integration with ViralCutter's existing subtitle burning, watermarking, and AI smart-clipping pipelines.

---

## 2. Visual Layout & Mathematical Specifications

### 2.1 Canvas Geometry
The final composition targets a standard Full HD vertical canvas of **$1080 \times 1920$** ($9:16$):

```
+--------------------------------------------------------+  y = 0
|                                                        |
|                   FACECAM (Top 30%)                    |
|             Resolution: 1080 x 576 px                  |
|             Aspect Ratio: 15:8 (1.875)                 |
|                                                        |
+--------------------------------------------------------+  y = 576 px
|                                                        |
|                                                        |
|                                                        |
|                   GAMEPLAY (Bottom 70%)                |
|             Resolution: 1080 x 1344 px                 |
|             Aspect Ratio: 45:56 (~0.803)               |
|                                                        |
|                                                        |
|     [Subtitles Rendered in Gameplay Region as usual]   |
|                                                        |
+--------------------------------------------------------+  y = 1920 px
x = 0                                                 x = 1080 px
```

### 2.2 Aspect Ratio Locking
To prevent video distortion (squishing or stretching):
- **Facecam Box:** Locked to aspect ratio $\text{AR}_{\text{cam}} = \frac{1080}{576} = 1.875$. When resizing, height changes proportionally: $\Delta h = \frac{\Delta w}{1.875}$.
- **Gameplay Box:** Locked to aspect ratio $\text{AR}_{\text{game}} = \frac{1080}{1344} \approx 0.80357$. When resizing, height changes proportionally: $\Delta h = \frac{\Delta w}{0.80357}$.

---

## 3. Data Contract & Coordinate Representation

To support source footage in any resolution ($720\text{p}$, $1080\text{p}$, $1440\text{p}$, $4\text{K}$), coordinates are normalized between $0.0$ and $1.0$:

### 3.1 Bounding Box Schema
```typescript
export interface NormalizedRect {
  x: number;      // 0.0 <= x <= 1.0 (left position normalized to video width)
  y: number;      // 0.0 <= y <= 1.0 (top position normalized to video height)
  width: number;  // 0.0 < width <= 1.0
  height: number; // 0.0 < height <= 1.0
}

export interface GamingSplitLayoutConfig {
  facecam: NormalizedRect;
  gameplay: NormalizedRect;
}
```

### 3.2 Default Layout Initializer
For standard $16:9$ input video:
- **Facecam (Default Top-Right Corner):**
  `{ x: 0.68, y: 0.05, width: 0.28, height: 0.1493 }`
- **Gameplay (Default Center Screen):**
  `{ x: 0.25, y: 0.0, width: 0.50, height: 0.622 }`

### 3.3 Backend API & CLI Arguments
1. **CLI in `main_improved.py`:**
   - `--orientation`: Add choice `9:16_gaming_split`.
   - `--gaming-facecam`: String formatted as `"x,y,w,h"` (e.g. `"0.68,0.05,0.28,0.149"`).
   - `--gaming-gameplay`: String formatted as `"x,y,w,h"` (e.g. `"0.25,0.0,0.50,0.622"`).
2. **FastAPI Job Schema (`webui/backend/schemas/jobs.py`):**
   - Add fields to `JobRunRequest`:
     ```python
     orientation: str = Field(default="9:16", description="Video orientation: 9:16, 16:9, 1:1, 9:16_gaming_split")
     gaming_facecam_crop: Optional[str] = Field(default=None, description="Normalized crop x,y,w,h for facecam")
     gaming_gameplay_crop: Optional[str] = Field(default=None, description="Normalized crop x,y,w,h for gameplay")
     ```

---

## 4. Frontend Architecture: Interactive Canvas Editor

### 4.1 Component Design (`webui/frontend/src/components/GamingCropEditor.tsx`)
Rendered directly inside `GeneratorTab.tsx` when `orientation === '9:16_gaming_split'` is selected:

1. **Source View Canvas (16:9):**
   - Renders current video frame (from `/api/v1/preview/frame` or client upload).
   - Draws Facecam Box (Blue theme, `#3b82f6`) with label `Facecam (30%)`.
   - Draws Gameplay Box (Emerald theme, `#10b981`) with label `Gameplay (70%)`.
   - Supports:
     - Drag to move anywhere inside video boundaries.
     - 4 corner resize handles with enforced aspect ratio locks.
     - Out-of-bounds containment clamping ($0 \le x$, $x + w \le 1.0$, $0 \le y$, $y + h \le 1.0$).
2. **Live 9:16 Split Preview Canvas:**
   - Positioned alongside the source editor.
   - Slices pixel data from the source frame canvas according to both bounding boxes in real-time.
   - Draws Top 30% from Facecam box, scaled to fit $1080 \times 576$.
   - Draws Bottom 70% from Gameplay box, scaled to fit $1080 \times 1344$.
   - Live updates with zero server roundtrips while dragging.
3. **Quick Presets Toolbar:**
   - Presets buttons:
     - `Top-Left Cam` (`x: 0.04, y: 0.05`)
     - `Top-Right Cam` (`x: 0.68, y: 0.05`)
     - `Bottom-Left Cam` (`x: 0.04, y: 0.70`)
     - `Bottom-Right Cam` (`x: 0.68, y: 0.70`)
     - `Center Action` (centers gameplay box horizontally)

---

## 5. Backend Rendering Engine: FFmpeg Pipeline

### 5.1 Coordinate Conversion
Given source video dimensions $W_{\text{src}} \times H_{\text{src}}$:
```python
def to_pixel_box(normalized_box: str, src_w: int, src_h: int) -> tuple[int, int, int, int]:
    x, y, w, h = [float(v.strip()) for v in normalized_box.split(",")]
    px_x = int(round(x * src_w))
    px_y = int(round(y * src_h))
    px_w = int(round(w * src_w))
    px_h = int(round(h * src_h))
    # Ensure even dimensions for H.264/yuv420p compatibility
    px_x = px_x - (px_x % 2)
    px_y = px_y - (px_y % 2)
    px_w = max(2, px_w - (px_w % 2))
    px_h = max(2, px_h - (px_h % 2))
    return px_x, px_y, px_w, px_h
```

### 5.2 FFmpeg Filter Complex Construction
Constructed in a dedicated helper `scripts/gaming_split.py` and called from `scripts/edit_video.py`:

```bash
ffmpeg -y -i "{input_clip}" -filter_complex "\
  [0:v]split=2[raw_cam][raw_game];\
  [raw_cam]crop={w1}:{h1}:{x1}:{y1},scale=1080:576:flags=lanczos[cam_top];\
  [raw_game]crop={w2}:{h2}:{x2}:{y2},scale=1080:1344:flags=lanczos[game_bottom];\
  [cam_top][game_bottom]vstack=inputs=2[v_out]\
" -map "[v_out]" -map 0:a? -c:v libx264 -preset fast -crf 18 -c:a copy "{output_clip}"
```

### 5.3 Pipeline Handshake
1. **Video Cutting:** `cut_segments.py` cuts raw clips to `cuts/` normally.
2. **Framing & Stacking:** `edit_video.py` inspects orientation. If `9:16_gaming_split`, it skips MediaPipe/InsightFace face tracking and executes `render_gaming_split()` on each clip into `final/`.
3. **Subtitles & Watermarks:** `burn_subtitles.py` burns subtitles onto the resulting $1080 \times 1920$ video. Subtitles placed at default vertical margins naturally sit in the lower gameplay region without occluding the facecam.

---

## 6. Error Handling & Edge Cases

| Scenario | Behavior / Mitigation |
| :--- | :--- |
| **Bounding box exceeds video edge** | Clamped to `[0.0, 1.0]` bounds so $x + w \le 1.0$ and $y + h \le 1.0$. |
| **Box resized too small** | Minimum width/height enforced ($w \ge 0.08, h \ge 0.08$). |
| **Missing crop arguments** | Fallback to default presets (Top-Right Cam + Center Gameplay). |
| **Non-16:9 source video** | FFmpeg filter normalizes aspect ratios cleanly using Lanczos scaler. |
| **Odd pixel dimensions** | Forced even integers (`px - px % 2`) to prevent FFmpeg chroma errors. |
| **Audio codec compatibility** | `-c:a copy` preserves audio bitstream directly; falls back to `-c:a aac` if container transcoding fails. |

---

## 7. Verification & Testing Plan

1. **Backend Unit Tests (`tests/test_gaming_split.py`):**
   - Coordinate parsing and normalization roundtrip.
   - Even-pixel rounding math for uneven source resolutions.
   - Filter complex string generation and validation.
   - CLI argument parsing for `--orientation 9:16_gaming_split` and crop flags.
2. **Frontend Unit Tests (`webui/frontend/src/test/gaming_editor.test.tsx`):**
   - Mounting and rendering of `GamingCropEditor` when orientation is `9:16_gaming_split`.
   - Dragging calculations and boundary clamping.
   - Aspect ratio lock verification on resize.
3. **End-to-End Smoke Test (`tests/test_gaming_split_e2e.py`):**
   - Generate synthetic $16:9$ test video ($1280 \times 720$) using `testsrc`.
   - Execute gaming split filter complex.
   - Probe final video using `ffprobe`: assert duration matches input and dimensions are exactly $1080 \times 1920$.
