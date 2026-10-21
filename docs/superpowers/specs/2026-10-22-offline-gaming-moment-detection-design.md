# Design Specification: Offline Gaming Moment Detection Engine

**Date:** 2026-10-22  
**Status:** Validated / Ready for Implementation  
**Branch:** `kodokbakar/yellowtail`  
**Topic:** Multimodal Offline Moment Detection (Audio Spike, Facecam Reaction, Keyword Clustered Scoring) for Gaming Livestream VODs  

---

## 1. Executive Summary & Problem Statement

ViralCutter's core clipping engine (`create_viral_segments.py` / `prompt.txt`) was engineered specifically for podcasts and interview content:
- It requires **narrative completeness** (hook, middle story, punchline/conclusion).
- It rejects filler phrases and fragments without context.
- It attempts dead-air elimination (`smart_remove_dead_air`).
- It produces corporate/educational infographic B-roll (`vox_bar_chart`, `sleek_step_list`).

When applied to **gaming livestreams**, this approach completely breaks down:
1. Peak gaming moments (1v4 clutch, jumpscares, boss defeats, funny fails) are driven by **in-game action, screams, laughter, or intense silence**, not structured verbal exposition.
2. Streamers often shout fragmented slang or exclamations (*"ANJIR!", "LET'S GOOO!", "WHAT?!"*), which the narrative LLM ignores as low-value noise.
3. For pre-downloaded local video files, external live chat replay (Twitch/YouTube chat logs) is not available.

This specification defines the **Offline Gaming Moment Detection Engine**:
An offline, multimodal detection pipeline that identifies high-energy gaming highlights directly from local video files using three synergistic signals:
1. **Audio Spike & Quiet-to-Burst Energy Dynamics** (FFmpeg audio analysis)
2. **Facecam Reaction & Physical Motion Tracking** (InsightFace Mouth Aspect Ratio and displacement)
3. **Exclamatory Keyword & Shout Density** (Faster-Whisper transcript token scanning)
4. **Dynamic Gaming Windowing & Layout Automation** (Pre-action buildup + post-action reaction windowing with auto-routing to 9:16 gaming split)

---

## 2. Multimodal Signal Detection Architecture

```
                                  [Input Video File]
                                          │
            ┌─────────────────────────────┼─────────────────────────────┐
            │                             │                             │
    [Audio Stream]               [Facecam Crop Window]         [Whisper Transcript]
            │                             │                             │
    gaming_audio_detector        gaming_facecam_detector      gaming_keyword_detector
  (FFmpeg RMS & Z-Score)        (InsightFace MAR & Motion)    (Exclamation Regex Match)
            │                             │                             │
      Audio Curve                   Facecam Curve                 Keyword Curve
      S_audio(t)                     S_face(t)                      S_kw(t)
            │                             │                             │
            └─────────────────────────────┼─────────────────────────────┘
                                          │
                                 gaming_scorer.py
                         [Hybrid Signal Fusion & Normalization]
                                          │
                            [Local Peak Detection + NMS]
                                          │
                        [Dynamic Windowing: Buildup + Aftermath]
                                          │
                          Output: `viral_segments.json`
                                          │
                      ┌───────────────────┴───────────────────┐
                      ▼                                       ▼
        [Layout: 9:16 Gaming Split]               [Subtitles: High-Impact Gaming Style]
       (Facecam 30% / Game 70%)                    (No Dead-Air Cutting, Bold Contrast)
```

---

## 3. Detailed Component Specifications

### 3.1 Audio Spike & Energy Detector (`scripts/gaming_audio_detector.py`)
Audio volume and sudden loudness transitions are the single most reliable offline indicator of gaming climaxes (gunfire, boss screams, player yelling, laughing, jumpscares).

1. **Extraction:**
   - Extract audio track to 16kHz mono PCM (`.wav`) via FFmpeg.
   - Compute Root-Mean-Square (RMS) amplitude in rolling windows of $100\text{ ms}$ with $50\text{ ms}$ hop size.
2. **Baseline Normalization (Z-Score):**
   - Calculate stream-wide mean volume $\mu_{\text{audio}}$ and standard deviation $\sigma_{\text{audio}}$.
   - Instantaneous Z-score:
     $$Z_{\text{audio}}(t) = \frac{\text{RMS}(t) - \mu_{\text{audio}}}{\sigma_{\text{audio}}}$$
3. **Quiet-to-Burst Transition Contrast:**
   - Detect clutch/jumpscare patterns: sustained low volume ($Z < -0.2$ for $\ge 3.0\text{ s}$) followed by an explosive burst ($Z > +2.5$ in $< 0.5\text{ s}$).
   - Sudden transition gives up to $+25\%$ bonus to the audio score.
4. **Output:** Continuous normalized audio score $S_{\text{audio}}(t) \in [0.0, 100.0]$.

### 3.2 Facecam Reaction Detector (`scripts/gaming_facecam_detector.py`)
If a Facecam bounding box is specified (or configured via `GamingCropEditor.tsx`), the visual region is analyzed for emotional reaction.

1. **Facecam Sub-Region Sampling:**
   - Crop only the Facecam rectangle $[x, y, w, h]$ to minimize compute.
   - Sample at $5 \text{ FPS}$ (every 0.2s) across candidate event spans.
2. **Mouth Aspect Ratio (MAR) Analysis:**
   - Detect mouth landmarks using existing `insightface` landmarks.
   - Compute MAR:
     $$\text{MAR} = \frac{\|p_{14} - p_{18}\| + \|p_{15} - p_{17}\|}{2 \times \|p_{13} - p_{16}\|}$$
   - Wide open mouth ($\text{MAR} > 0.12$) indicates screaming, open-mouthed shock, or intense laughter.
3. **Motion Displacement:**
   - Measure rapid face center-of-mass translation velocity:
     $$v(t) = \frac{\|\text{Center}_t - \text{Center}_{t-1}\|}{\Delta t}$$
   - Detects the streamer jumping out of the chair, slamming desk, or lurching toward the screen.
4. **Fallback Handling:**
   - If no facecam is provided or no face is detected in the stream, return $S_{\text{face}}(t) = 0.0$ and redistribute weights to audio and keywords without crashing.

### 3.3 Exclamatory Keyword & Shout Detector (`scripts/gaming_keyword_detector.py`)
Uses the Faster-Whisper word-level timestamp transcript to detect shout/hype vocabulary clusters.

1. **Dictionary of Exclamations:**
   - **Indonesian:** `"anjir"`, `"gila"`, `"mati"`, `"woi"`, `"bisa gitu"`, `"hoki"`, `"rata"`, `"mampus"`, `"waduh"`, `"lah"`, `"kebantai"`, `"panik"`, `"anjay"`.
   - **English:** `"no way"`, `"let's go"`, `"holy shit"`, `"what the fuck"`, `"clutch"`, `"ace"`, `"headshot"`, `"hacker"`, `"omg"`, `"gg"`, `"ez"`, `"pog"`, `"insane"`.
2. **Cluster Density Scoring:**
   - Count matched shout tokens in a sliding window of $8.0\text{ s}$.
   - Token density $\ge 3$ words yields a score approaching $100.0$.
3. **Output:** $S_{\text{kw}}(t) \in [0.0, 100.0]$.

### 3.4 Hybrid Gaming Scorer & Windowing (`scripts/gaming_scorer.py`)

1. **Composite Score:**
   $$\text{Score}(t) = w_{\text{audio}} S_{\text{audio}}(t) + w_{\text{face}} S_{\text{face}}(t) + w_{\text{kw}} S_{\text{kw}}(t)$$
   - Standard weights: $w_{\text{audio}} = 0.50$, $w_{\text{face}} = 0.30$, $w_{\text{kw}} = 0.20$.
   - When Facecam is inactive: $w_{\text{audio}} = 0.70$, $w_{\text{kw}} = 0.30$.
2. **Peak Finding & Non-Maximum Suppression (NMS):**
   - Find local maxima above threshold (default $\text{Score} \ge 60.0$).
   - Apply NMS with suppression radius $R_{\text{nms}} = 45.0\text{ s}$ to guarantee diverse, non-overlapping clips.
3. **Dynamic Gaming Windowing:**
   - Unlike podcasts that start cleanly at a sentence start, gaming highlights require **pre-action buildup**:
     $$T_{\text{start}} = \max(0.0, T_{\text{peak}} - 18.0\text{ s})$$
     $$T_{\text{end}} = \min(T_{\text{video}}, T_{\text{peak}} + 10.0\text{ s})$$
   - Total duration target: $\approx 25\text{ s} - 45\text{ s}$, clamped strictly between user `min_duration` and `max_duration`.
4. **Hook Headline Generation:**
   - Generates high-converting, curiosity-driven gaming headlines matching ViralCutter's 3-6 words ALL CAPS standard:
     - Indonesian: `"DETIK-DETIK CLUTCH PANIK?!"`, `"MOMEN TERGILA BIKIN SYOK!"`, `"REAKSI REFLEKS DEWA?!"`, `"MOMEN HOKI SEUMUR HIDUP!"`.
     - English: `"INSANE 1V4 CLUTCH MOMENT?!"`, `"HE COULD NOT BELIEVE THIS!"`, `"PEAK GAMER RAGE REACTION?!"`.

---

## 4. Pipeline Execution & Routing Rules

When `--pipeline-mode gaming` is selected:
1. **Bypass Narrative Prompting:** `create_viral_segments.py` is skipped. Segments are produced deterministically by `gaming_scorer.py`.
2. **Force Preserve Dead-Air:** `smart_remove_dead_air` is set to `False`. Pauses during high-stakes clutches are preserved.
3. **Layout Default:** Sets orientation to `9:16_gaming_split` using provided Facecam and Gameplay boxes (fallback to default boxes if unspecified).
4. **B-Roll Suppression:** Suppresses corporate chart templates (`vox_bar_chart`, `sleek_step_list`), keeping video clean for fast gameplay visual readability.

---

## 5. File Structure & Responsibilities

| File | Responsibility |
|---|---|
| `scripts/gaming_audio_detector.py` | Audio RMS, Z-score, and quiet-to-burst contrast detection via FFmpeg |
| `scripts/gaming_facecam_detector.py` | Facecam bounding-box crop, MAR calculation, and facial motion velocity |
| `scripts/gaming_keyword_detector.py` | Exclamatory word clustering from Whisper transcript |
| `scripts/gaming_scorer.py` | Multi-signal fusion, peak finding, dynamic windowing, and segment emission |
| `main_improved.py` | CLI flags `--pipeline-mode` and dispatch branch |
| `webui/backend/schemas/jobs.py` | Schema field `pipeline_mode: "podcast" \| "gaming"` and parameter validation |
| `webui/frontend/src/components/GeneratorTab.tsx` | Mode selection toggle and UI panel adaptation |
| `tests/test_gaming_audio_detector.py` | Unit tests for audio peak detection and Z-score calculations |
| `tests/test_gaming_facecam_detector.py` | Unit tests for MAR and facial displacement |
| `tests/test_gaming_keyword_detector.py` | Unit tests for shout word density |
| `tests/test_gaming_scorer.py` | Unit tests for composite scoring, NMS, and dynamic windowing |
| `tests/test_gaming_pipeline_e2e.py` | End-to-end integration test for gaming mode pipeline |
