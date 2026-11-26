# Design Specification: Flexible Gaming Layouts, Killfeed Overlay, Clutch Buildup, and Pop Subtitles (Issue #4)

**Date:** 2026-11-26  
**Status:** Approved / Implemented  
**Branch:** `feat/issue-4`  
**Topic:** Modular Production-Grade Gaming Pipeline: 4 Framing Layouts, Secondary Killfeed/HUD Overlay, Silence-Aware Clutch Windowing, and Layout-Aligned Pop Subtitles.

---

## 1. Executive Summary & Problem Statement

Viral horizontal gaming videos (stream highlights, esports matches, FPS clutches) vary significantly in visual hierarchy and streamer HUD design. A rigid 30/70 vertical split does not suit all games or creator preferences:
1. Some streams feature larger VTuber / webcam setups requiring 40/60 splits.
2. Fast-paced FPS games need immersive full-screen vertical action with a subtle floating picture-in-picture (PiP) facecam.
3. MOBA / RTS games or landscape gameplays benefit from centered content with aesthetic blurred backgrounds.
4. Crucial in-game narrative moments (aces, multikills, clutch defuses) depend heavily on the **killfeed** or status HUD located in extreme corners of the 16:9 feed.
5. High-intensity gaming moments are driven by audio dynamics: prolonged silent tension before an explosive play followed by shouting. Fixed clip windows cut off the tension, while uniform subtitles miss the emotional weight of shout peaks.

Issue #4 establishes a comprehensive, production-grade gaming layout engine across the backend and frontend.

---

## 2. Multi-Layout Architecture & Mathematical Specifications

All layouts render into a native Full HD vertical resolution of **$1080 \times 1920$** ($9:16$). The filtergraph terminates on output pad `[stacked_v]`.

### 2.1 Layout Specifications

| Layout Key | Description | Facecam Aspect Ratio & Box | Gameplay Aspect Ratio & Box | Geometry / Stacking |
| :--- | :--- | :--- | :--- | :--- |
| `split_30_70` | Default Top/Bottom Split | $1080 \times 576$ ($\text{AR} = 1.875$) | $1080 \times 1344$ ($\text{AR} \approx 0.8036$) | Vertical stack (`vstack=inputs=2`) |
| `split_40_60` | Emphasized Camera Split | $1080 \times 768$ ($\text{AR} = 1.40625$) | $1080 \times 1152$ ($\text{AR} = 0.9375$) | Vertical stack (`vstack=inputs=2`) |
| `floating_pip` | Fullscreen with PiP Cam | $360 \times 270$ ($\text{AR} = 1.3333$) | $1080 \times 1920$ ($\text{AR} = 0.5625$) | Overlay at $x=40, y=60$ on vertical base |
| `blurred_bg` | Center 16:9 with Blurred BG | $1080 \times 576$ ($\text{AR} = 1.875$) | $1080 \times 608$ ($\text{AR} \approx 1.7778$) | Blurred BG (`boxblur=20:5`), Cam at $y=0$, Game at $y=620$ |

### 2.2 Secondary Killfeed / HUD Overlay Box
- Parameter: `--gaming-killfeed "x,y,w,h"` (normalized coordinates $[0.0, 1.0]$).
- Fixed Aspect Ratio: $\text{AR}_{\text{killfeed}} = 2.0$.
- Visual Styling: Subdued border overlay (`drawbox=t=2:c=white@0.6`) positioned in the upper right quadrant ($x = W - w - 20, y = 20$).
- Output Pad Guarantee: Overlaid cleanly over base video, outputting to `[stacked_v]`.

---

## 3. Clutch Silence Buildup Windowing

Gaming clips frequently suffer when algorithms crop directly to high-energy audio spikes without the preceding tense silence.

### 3.1 Algorithm
- Audio RMS is calculated at 100ms intervals and transformed into standard score $Z = \frac{\text{RMS} - \mu}{\sigma}$.
- Silence threshold: $Z < -0.2$ sustained for $\ge 5.0$ seconds immediately prior to the climax.
- Window Expansion: `ideal_start` is expanded backward to capture up to 8.0 seconds of tension buildup while respecting `max_dur`.
- Boundary Snapping: The expanded boundary snaps cleanly to speech pauses ($>0.4$s) or transcript sentence breaks.

---

## 4. Layout-Aligned Dynamic Subtitles & Pop Tags

### 4.1 Vertical Position Overrides
Different layouts position visual focus and gameplay UI differently. In `scripts/adjust_subtitles.py`, ASS subtitle styles define `MarginV` adaptively:
- `split_30_70`: `MarginV = 400`
- `split_40_60`: `MarginV = 350`
- `floating_pip`: `MarginV = 120`
- `blurred_bg`: `MarginV = 180`

### 4.2 Pop Tag Animation
Active words occurring during scream/shout keywords or high RMS peaks ($Z \ge 2.0$) receive inline ASS transform animation tags:
```ass
{\fscx125\fscy125\t(0,100,\fscx100\fscy100)\c&H0000FFFF&}
```
This enlarges the word by 125% and transitions back to 100% within 100ms while highlighting it in neon yellow/gold.

---

## 5. WebUI & Frontend Integration

1. `webui/frontend/src/api/types.ts`:
   - Defined `GamingLayout = 'split_30_70' | 'split_40_60' | 'floating_pip' | 'blurred_bg'`.
   - Extended `JobRunRequest` with optional `gaming_layout` and `gaming_killfeed_crop`.
2. `webui/frontend/src/components/GamingCropEditor.tsx`:
   - Interactive layout selector buttons.
   - Dynamic aspect ratio constraints for facecam and gameplay boxes per layout.
   - Draggable & resizable amber killfeed overlay box with toggle control.
   - Real-time HTML5 canvas rendering of 16:9 bounding boxes and 9:16 layout previews.
3. `webui/frontend/src/components/GeneratorTab.tsx`:
   - LocalStorage persistence for selected layout via `usePersistedState`.
   - Conditional attachment of `gaming_layout` and `gaming_killfeed_crop` upon job submission.

---

## 6. Verification & Test Architecture

- `tests/test_gaming_split.py`: Unit tests validating FFmpeg filtergraph strings for all 4 layouts and killfeed overlays.
- `tests/test_gaming_split_cli.py`: CLI flag parsing and `JobRunRequest.to_cli_args()` mapping tests.
- `tests/test_gaming_scorer.py`: Audio RMS z-score calculation and silence buildup window expansion tests.
- `tests/test_adjust_subtitles_gaming.py`: Subtitle vertical margin layout overrides and pop tag injection tests.
- `webui/frontend/src/test/gaming_editor.test.tsx`: Component tests for layout switching, killfeed toggle, and job submission payload verification.
