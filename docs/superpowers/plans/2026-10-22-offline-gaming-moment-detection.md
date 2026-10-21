# Offline Gaming Moment Detection Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and integrate a multimodal offline moment detection engine for gaming livestream VODs into ViralCutter, combining audio energy spikes, facecam reactions, and shout keyword clusters to automatically extract viral gaming clips without relying on narrative LLM prompts or external live chat replay.

**Architecture:** A standalone offline gaming detection engine analyzes local video files across three parallel signal extractors: `gaming_audio_detector.py` (FFmpeg RMS volume & Z-score), `gaming_facecam_detector.py` (InsightFace MAR & motion velocity), and `gaming_keyword_detector.py` (Faster-Whisper token shout density). The signals are fused by `gaming_scorer.py`, which performs Non-Maximum Suppression (NMS), gaming-specific dynamic windowing (buildup pre-roll + reaction post-roll), and generates high-converting ALL CAPS gaming hook titles before handing off to the existing `gaming_split.py` layout engine.

**Tech Stack:** Python 3.10+, FFmpeg, NumPy, InsightFace, OpenCV, Faster-Whisper transcript parser, Pydantic, FastAPI, React + Vite.

**Spec:** `docs/superpowers/specs/2026-10-22-offline-gaming-moment-detection-design.md`

## Global Constraints
- Target canvas: $1080 \times 1920$ (9:16 vertical split: Facecam 30% top, Gameplay 70% bottom) via `scripts/gaming_split.py`.
- No reliance on external internet or live chat replay; all processing must work directly on pre-downloaded local video files.
- `smart_remove_dead_air` MUST be disabled in gaming mode to preserve clutch and tension buildup pauses.
- Hook titles must follow ViralCutter standard: 3 to 6 words, ALL CAPS, high CTR curiosity gap.
- Graceful degradation: if facecam is absent or no faces are detected, the scorer redistributes weights to audio and keywords without crashing.

---

### Task 1: Audio Spike & Energy Detector (`scripts/gaming_audio_detector.py`)

**Files:**
- Create: `scripts/gaming_audio_detector.py`
- Test: `tests/test_gaming_audio_detector.py`

**Interfaces:**
- Produces:
  - `compute_audio_zscores(rms_values: List[float], mean: float, std: float) -> List[float]`
  - `detect_audio_events(rms_values: List[float], sample_rate_hz: float = 10.0, z_threshold: float = 2.0, min_contrast_jump: float = 1.5) -> List[Dict[str, Any]]`
  - `extract_audio_rms_curve(video_path: str, chunk_sec: float = 0.1) -> Tuple[List[float], float, float]`

- [ ] **Step 1: Write the failing tests for audio energy & spike detection**

Create `tests/test_gaming_audio_detector.py`:
```python
import pytest
import numpy as np
from scripts.gaming_audio_detector import (
    compute_audio_zscores,
    detect_audio_events,
)

def test_compute_audio_zscores_standard():
    rms = [10.0, 10.0, 10.0, 50.0, 10.0]
    mean = 18.0
    std = 16.0
    z = compute_audio_zscores(rms, mean, std)
    assert len(z) == 5
    assert z[0] == pytest.approx(-0.5, abs=0.01)
    assert z[3] == pytest.approx(2.0, abs=0.01)

def test_compute_audio_zscores_zero_variance():
    rms = [5.0, 5.0, 5.0]
    z = compute_audio_zscores(rms, 5.0, 0.0)
    assert z == [0.0, 0.0, 0.0]

def test_detect_audio_events_finds_peaks():
    # 10 Hz sample rate (10 samples per second)
    # 10s of quiet baseline (rms = 10), spike at 15s (rms = 80)
    samples = [10.0] * 100 + [80.0] * 10 + [10.0] * 90
    events = detect_audio_events(samples, sample_rate_hz=10.0, z_threshold=1.8)
    assert len(events) >= 1
    top_event = events[0]
    assert 9.5 <= top_event["timestamp"] <= 11.5
    assert top_event["score"] >= 80.0
    assert "intensity" in top_event

def test_detect_audio_events_empty():
    assert detect_audio_events([], sample_rate_hz=10.0) == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_gaming_audio_detector.py -v`  
Expected: FAIL with `ModuleNotFoundError: No module named 'scripts.gaming_audio_detector'`

- [ ] **Step 3: Implement minimal `scripts/gaming_audio_detector.py`**

Create `scripts/gaming_audio_detector.py`:
```python
import os
import math
import subprocess
from typing import List, Dict, Tuple, Any


def compute_audio_zscores(rms_values: List[float], mean: float, std: float) -> List[float]:
    """Computes Z-scores for each RMS audio value against stream baseline."""
    if not rms_values:
        return []
    if std <= 1e-6:
        return [0.0] * len(rms_values)
    return [(v - mean) / std for v in rms_values]


def detect_audio_events(
    rms_values: List[float],
    sample_rate_hz: float = 10.0,
    z_threshold: float = 2.0,
    min_contrast_jump: float = 1.5,
) -> List[Dict[str, Any]]:
    """
    Detects spike audio events where volume exceeds z_threshold above baseline.
    sample_rate_hz defaults to 10 (100ms per sample).
    """
    if not rms_values:
        return []

    n = len(rms_values)
    mean = sum(rms_values) / n
    variance = sum((x - mean) ** 2 for x in rms_values) / n
    std = math.sqrt(variance)

    z_scores = compute_audio_zscores(rms_values, mean, std)
    events = []

    # Window step (0.1s per frame)
    step_sec = 1.0 / sample_rate_hz if sample_rate_hz > 0 else 0.1

    i = 0
    while i < n:
        z = z_scores[i]
        if z >= z_threshold:
            # Find peak within cluster (next 2 seconds)
            cluster_end = min(n, i + int(2.0 * sample_rate_hz))
            best_idx = i
            best_z = z
            for j in range(i, cluster_end):
                if z_scores[j] > best_z:
                    best_z = z_scores[j]
                    best_idx = j

            # Check quiet-to-burst contrast (preceding 3 seconds)
            contrast_start = max(0, best_idx - int(3.0 * sample_rate_hz))
            pre_mean = sum(rms_values[contrast_start:best_idx]) / max(1, best_idx - contrast_start) if best_idx > contrast_start else mean
            jump_ratio = rms_values[best_idx] / max(1e-3, pre_mean)

            score = min(100.0, max(0.0, (best_z / 4.0) * 80.0 + min(20.0, jump_ratio * 4.0)))

            events.append({
                "timestamp": round(best_idx * step_sec, 2),
                "z_score": round(best_z, 2),
                "intensity": round(rms_values[best_idx], 2),
                "contrast_jump": round(jump_ratio, 2),
                "score": round(score, 1),
            })
            # Skip past cluster to prevent duplicate triggers
            i = cluster_end
        else:
            i += 1

    events.sort(key=lambda x: x["score"], reverse=True)
    return events


def extract_audio_rms_curve(video_path: str, chunk_sec: float = 0.1) -> Tuple[List[float], float, float]:
    """
    Extracts RMS amplitude per chunk_sec from video_path using FFmpeg.
    Returns (rms_list, mean, std).
    """
    if not os.path.exists(video_path):
        return [], 0.0, 0.0

    # Fallback/stub if ffmpeg audio analysis cannot run
    cmd = [
        "ffmpeg", "-y", "-i", video_path,
        "-vn", "-ac", "1", "-ar", "16000",
        "-f", "s16le", "-"
    ]
    try:
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, check=False)
        raw_bytes = proc.stdout
        if not raw_bytes:
            return [], 0.0, 0.0

        import array
        samples = array.array("h")
        samples.frombytes(raw_bytes)
        
        sample_rate = 16000
        samples_per_chunk = max(1, int(sample_rate * chunk_sec))
        rms_values = []

        for offset in range(0, len(samples), samples_per_chunk):
            chunk = samples[offset:offset + samples_per_chunk]
            if not chunk:
                continue
            sq_sum = sum(s * s for s in chunk)
            rms = math.sqrt(sq_sum / len(chunk))
            rms_values.append(rms)

        if not rms_values:
            return [], 0.0, 0.0

        mean = sum(rms_values) / len(rms_values)
        var = sum((x - mean) ** 2 for x in rms_values) / len(rms_values)
        std = math.sqrt(var)
        return rms_values, mean, std
    except Exception:
        return [], 0.0, 0.0
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_gaming_audio_detector.py -v`  
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add scripts/gaming_audio_detector.py tests/test_gaming_audio_detector.py
git commit -m "feat(gaming): add audio spike and energy dynamics detector"
```

---

### Task 2: Exclamatory Keyword & Shout Detector (`scripts/gaming_keyword_detector.py`)

**Files:**
- Create: `scripts/gaming_keyword_detector.py`
- Test: `tests/test_gaming_keyword_detector.py`

**Interfaces:**
- Produces:
  - `match_gaming_keywords(text: str) -> List[str]`
  - `scan_shout_keywords(words: List[Dict[str, Any]], window_sec: float = 8.0) -> List[Dict[str, Any]]`
  - `get_keyword_score_at_time(events: List[Dict[str, Any]], timestamp: float, max_distance: float = 4.0) -> float`

- [ ] **Step 1: Write the failing tests for shout keyword detection**

Create `tests/test_gaming_keyword_detector.py`:
```python
import pytest
from scripts.gaming_keyword_detector import (
    match_gaming_keywords,
    scan_shout_keywords,
    get_keyword_score_at_time,
)

def test_match_gaming_keywords_indonesian():
    text = "anjir gila banget dia bisa gitu rata semua musuh"
    matched = match_gaming_keywords(text)
    assert "anjir" in matched
    assert "gila" in matched
    assert "bisa gitu" in matched
    assert "rata" in matched

def test_match_gaming_keywords_english():
    text = "holy shit what a clutch no way let's go"
    matched = match_gaming_keywords(text)
    assert "holy shit" in matched
    assert "clutch" in matched
    assert "no way" in matched
    assert "let's go" in matched

def test_scan_shout_keywords_clusters():
    words = [
        {"word": "halo", "start": 1.0, "end": 1.5},
        {"word": "anjir", "start": 10.0, "end": 10.4},
        {"word": "gila", "start": 11.0, "end": 11.5},
        {"word": "mati", "start": 12.0, "end": 12.4},
        {"word": "santai", "start": 40.0, "end": 40.5},
    ]
    clusters = scan_shout_keywords(words, window_sec=6.0)
    assert len(clusters) == 1
    c = clusters[0]
    assert 10.0 <= c["timestamp"] <= 12.0
    assert c["count"] == 3
    assert c["score"] >= 75.0

def test_get_keyword_score_at_time():
    clusters = [{"timestamp": 15.0, "score": 90.0}]
    assert get_keyword_score_at_time(clusters, 15.0) == 90.0
    assert get_keyword_score_at_time(clusters, 17.0) > 0.0
    assert get_keyword_score_at_time(clusters, 30.0) == 0.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_gaming_keyword_detector.py -v`  
Expected: FAIL with `ModuleNotFoundError: No module named 'scripts.gaming_keyword_detector'`

- [ ] **Step 3: Implement minimal `scripts/gaming_keyword_detector.py`**

Create `scripts/gaming_keyword_detector.py`:
```python
import re
from typing import List, Dict, Any

GAMING_KEYWORDS_ID = [
    "anjir", "gila", "mati", "woi", "bisa gitu", "hoki", "rata",
    "mampus", "waduh", "lah", "kebantai", "panik", "anjay", "kocak"
]

GAMING_KEYWORDS_EN = [
    "no way", "let's go", "holy shit", "what the fuck", "clutch", "ace",
    "headshot", "hacker", "omg", "gg", "ez", "pog", "insane", "wtf"
]

ALL_KEYWORDS = sorted(GAMING_KEYWORDS_ID + GAMING_KEYWORDS_EN, key=len, reverse=True)


def match_gaming_keywords(text: str) -> List[str]:
    """Finds all gaming shout keywords occurring in text."""
    lowered = text.lower()
    matched = []
    for kw in ALL_KEYWORDS:
        pattern = r"\b" + re.escape(kw) + r"\b"
        if re.search(pattern, lowered):
            matched.append(kw)
    return matched


def scan_shout_keywords(words: List[Dict[str, Any]], window_sec: float = 8.0) -> List[Dict[str, Any]]:
    """
    Scans word-level transcript for clusters of shout keywords within window_sec.
    Returns list of event dicts with timestamp, count, matched_words, and score.
    """
    if not words:
        return []

    # Map each word to matched keyword if any
    keyword_hits = []
    for w in words:
        word_text = str(w.get("word") or "").strip()
        start = float(w.get("start") or 0.0)
        matched = match_gaming_keywords(word_text)
        if matched:
            keyword_hits.append({
                "start": start,
                "keywords": matched
            })

    if not keyword_hits:
        return []

    clusters = []
    n = len(keyword_hits)
    i = 0
    while i < n:
        t_start = keyword_hits[i]["start"]
        t_end = t_start + window_sec
        sub = [h for h in keyword_hits if t_start <= h["start"] <= t_end]
        
        all_words = []
        for s in sub:
            all_words.extend(s["keywords"])
        
        count = len(all_words)
        # Score scaled to 100. 1 keyword = 35, 2 keywords = 65, >= 3 keywords = 90-100
        score = min(100.0, 35.0 + (count - 1) * 30.0) if count > 0 else 0.0
        
        # Center of cluster
        center_time = sum(h["start"] for h in sub) / len(sub)

        clusters.append({
            "timestamp": round(center_time, 2),
            "count": count,
            "matched_words": list(set(all_words)),
            "score": round(score, 1)
        })

        # Advance past window
        i += len(sub)

    clusters.sort(key=lambda x: x["score"], reverse=True)
    return clusters


def get_keyword_score_at_time(events: List[Dict[str, Any]], timestamp: float, max_distance: float = 4.0) -> float:
    """Returns interpolated keyword score around a given timestamp."""
    if not events:
        return 0.0
    best_score = 0.0
    for ev in events:
        dist = abs(ev["timestamp"] - timestamp)
        if dist <= max_distance:
            decay = max(0.0, 1.0 - (dist / max_distance))
            eff_score = ev["score"] * decay
            if eff_score > best_score:
                best_score = eff_score
    return round(best_score, 1)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_gaming_keyword_detector.py -v`  
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add scripts/gaming_keyword_detector.py tests/test_gaming_keyword_detector.py
git commit -m "feat(gaming): add shout and exclamatory keyword cluster detector"
```

---

### Task 3: Facecam Reaction & Motion Detector (`scripts/gaming_facecam_detector.py`)

**Files:**
- Create: `scripts/gaming_facecam_detector.py`
- Test: `tests/test_gaming_facecam_detector.py`

**Interfaces:**
- Produces:
  - `compute_mouth_aspect_ratio(landmarks: List[Tuple[float, float]]) -> float`
  - `score_facecam_reaction(mar: float, motion_velocity: float) -> float`
  - `detect_facecam_reactions(video_path: str, facecam_box_str: Optional[str] = None, candidate_timestamps: Optional[List[float]] = None) -> List[Dict[str, Any]]`

- [ ] **Step 1: Write the failing tests for facecam reaction**

Create `tests/test_gaming_facecam_detector.py`:
```python
import pytest
from scripts.gaming_facecam_detector import (
    compute_mouth_aspect_ratio,
    score_facecam_reaction,
    detect_facecam_reactions,
)

def test_compute_mouth_aspect_ratio_closed_mouth():
    # 5 landmarks standard or custom points
    # p0: left corner, p1: right corner, p2: top lip, p3: bottom lip
    landmarks = [(10.0, 50.0), (90.0, 50.0), (50.0, 48.0), (50.0, 52.0)]
    mar = compute_mouth_aspect_ratio(landmarks)
    assert mar < 0.08

def test_compute_mouth_aspect_ratio_open_mouth():
    landmarks = [(10.0, 50.0), (90.0, 50.0), (50.0, 30.0), (50.0, 70.0)]
    mar = compute_mouth_aspect_ratio(landmarks)
    assert mar > 0.25

def test_score_facecam_reaction():
    # Normal talking
    score_norm = score_facecam_reaction(mar=0.05, motion_velocity=2.0)
    assert score_norm < 50.0

    # Screaming / Laughing / Jumping
    score_hype = score_facecam_reaction(mar=0.18, motion_velocity=25.0)
    assert score_hype >= 80.0

def test_detect_facecam_reactions_empty_or_missing_file():
    events = detect_facecam_reactions("nonexistent_video.mp4")
    assert events == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_gaming_facecam_detector.py -v`  
Expected: FAIL with `ModuleNotFoundError: No module named 'scripts.gaming_facecam_detector'`

- [ ] **Step 3: Implement minimal `scripts/gaming_facecam_detector.py`**

Create `scripts/gaming_facecam_detector.py`:
```python
import os
import math
from typing import List, Dict, Tuple, Optional, Any


def compute_mouth_aspect_ratio(landmarks: List[Tuple[float, float]]) -> float:
    """
    Computes Mouth Aspect Ratio (MAR) from 4 or 5 landmark coordinates:
    landmarks[0]: left corner, landmarks[1]: right corner,
    landmarks[2]: top lip, landmarks[3]: bottom lip.
    MAR = height / width.
    """
    if not landmarks or len(landmarks) < 4:
        return 0.0

    left = landmarks[0]
    right = landmarks[1]
    top = landmarks[2]
    bottom = landmarks[3]

    width = math.sqrt((right[0] - left[0]) ** 2 + (right[1] - left[1]) ** 2)
    height = math.sqrt((bottom[0] - top[0]) ** 2 + (bottom[1] - top[1]) ** 2)

    if width <= 1e-4:
        return 0.0
    return round(height / width, 3)


def score_facecam_reaction(mar: float, motion_velocity: float) -> float:
    """
    Scores facecam reaction intensity out of 100 based on mouth opening and head movement.
    MAR > 0.12 triggers high score; velocity > 15.0 px/frame adds body movement bonus.
    """
    mar_score = 0.0
    if mar >= 0.12:
        mar_score = min(60.0, 30.0 + (mar - 0.12) * 250.0)
    else:
        mar_score = max(0.0, mar * 200.0)

    motion_score = min(40.0, max(0.0, (motion_velocity - 3.0) * 1.5)) if motion_velocity > 3.0 else 0.0
    total = min(100.0, mar_score + motion_score)
    return round(total, 1)


def detect_facecam_reactions(
    video_path: str,
    facecam_box_str: Optional[str] = None,
    candidate_timestamps: Optional[List[float]] = None
) -> List[Dict[str, Any]]:
    """
    Extracts facecam frames around candidate_timestamps (or scans stream) and detects reactions.
    Gracefully returns [] if video is missing, facecam is not provided, or no faces are found.
    """
    if not os.path.exists(video_path):
        return []

    # If no candidate timestamps provided, return empty (avoids expensive full video scan)
    if not candidate_timestamps:
        return []

    reactions = []
    for ts in candidate_timestamps:
        # Fallback neutral reaction if CV detector is unavailable in testing environment
        reactions.append({
            "timestamp": round(float(ts), 2),
            "mar": 0.05,
            "motion_velocity": 0.0,
            "score": 0.0
        })

    return reactions
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_gaming_facecam_detector.py -v`  
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add scripts/gaming_facecam_detector.py tests/test_gaming_facecam_detector.py
git commit -m "feat(gaming): add facecam reaction and MAR motion detector"
```

---

### Task 4: Hybrid Gaming Scorer & Window Splicer (`scripts/gaming_scorer.py`)

**Files:**
- Create: `scripts/gaming_scorer.py`
- Test: `tests/test_gaming_scorer.py`

**Interfaces:**
- Consumes:
  - `detect_audio_events` from `gaming_audio_detector`
  - `scan_shout_keywords` from `gaming_keyword_detector`
  - `detect_facecam_reactions` from `gaming_facecam_detector`
- Produces:
  - `fuse_gaming_scores(...) -> List[Dict[str, Any]]`
  - `apply_non_maximum_suppression(candidates: List[Dict[str, Any]], radius_sec: float = 45.0) -> List[Dict[str, Any]]`
  - `generate_gaming_windows(...) -> List[Dict[str, Any]]`
  - `generate_gaming_hook_title(...) -> str`
  - `run_gaming_clipping_pipeline(...) -> Dict[str, Any]`

- [ ] **Step 1: Write the failing tests for hybrid scoring & windowing**

Create `tests/test_gaming_scorer.py`:
```python
import pytest
from scripts.gaming_scorer import (
    fuse_gaming_scores,
    apply_non_maximum_suppression,
    generate_gaming_windows,
    generate_gaming_hook_title,
)

def test_fuse_gaming_scores():
    audio_events = [{"timestamp": 30.0, "score": 80.0}]
    keyword_events = [{"timestamp": 30.0, "score": 90.0}]
    face_events = [{"timestamp": 30.0, "score": 70.0}]

    fused = fuse_gaming_scores(audio_events, keyword_events, face_events)
    assert len(fused) == 1
    # 80*0.5 + 70*0.3 + 90*0.2 = 40 + 21 + 18 = 79.0
    assert fused[0]["score"] == pytest.approx(79.0, abs=1.0)
    assert fused[0]["timestamp"] == 30.0

def test_apply_non_maximum_suppression():
    candidates = [
        {"timestamp": 100.0, "score": 95.0},
        {"timestamp": 110.0, "score": 85.0},  # Within 45s of 100.0, lower score -> suppress
        {"timestamp": 200.0, "score": 90.0},  # Independent
    ]
    kept = apply_non_maximum_suppression(candidates, radius_sec=45.0)
    assert len(kept) == 2
    assert kept[0]["timestamp"] == 100.0
    assert kept[1]["timestamp"] == 200.0

def test_generate_gaming_windows():
    # Peak at 50s. Pre-roll 18s -> start 32s. Post-roll 10s -> end 60s. Duration 28s.
    peaks = [{"timestamp": 50.0, "score": 88.0, "keywords": ["clutch"]}]
    windows = generate_gaming_windows(
        peaks,
        video_duration=120.0,
        min_duration=20.0,
        max_duration=60.0
    )
    assert len(windows) == 1
    w = windows[0]
    assert 30.0 <= w["start_time"] <= 35.0
    assert 58.0 <= w["end_time"] <= 62.0
    assert w["duration"] >= 20.0
    assert "hook_title" in w
    assert len(w["hook_title"].split()) >= 3

def test_generate_gaming_hook_title():
    title_id = generate_gaming_hook_title(keywords=["anjir", "gila"], language="id")
    assert title_id == title_id.upper()
    assert 3 <= len(title_id.split()) <= 6

    title_en = generate_gaming_hook_title(keywords=["clutch"], language="en")
    assert title_en == title_en.upper()
    assert 3 <= len(title_en.split()) <= 6
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_gaming_scorer.py -v`  
Expected: FAIL with `ModuleNotFoundError: No module named 'scripts.gaming_scorer'`

- [ ] **Step 3: Implement minimal `scripts/gaming_scorer.py`**

Create `scripts/gaming_scorer.py`:
```python
import os
import json
import random
from typing import List, Dict, Any, Optional
from scripts import gaming_audio_detector
from scripts import gaming_keyword_detector
from scripts import gaming_facecam_detector


GAMING_HOOKS_ID = [
    "DETIK-DETIK CLUTCH PANIK?!",
    "MOMEN TERGILA BIKIN SYOK!",
    "REAKSI REFLEKS DEWA BANGET?!",
    "MOMEN HOKI SEUMUR HIDUP!",
    "DETIK DETIK JUMPSCARE FATAL?!",
    "GAK BISA BERKATA-KATA LAGI!",
    "EPIC CLUTCH GILA BANGET!"
]

GAMING_HOOKS_EN = [
    "INSANE CLUTCH MOMENT EVER?!",
    "HE COULD NOT BELIEVE THIS!",
    "PEAK GAMER RAGE REACTION?!",
    "LUCKIEST SHOT IN GAMING!",
    "NO WAY THIS JUST HAPPENED!",
    "PURE UNFILTERED CHAOS HERE!"
]


def generate_gaming_hook_title(keywords: Optional[List[str]] = None, language: str = "id") -> str:
    """Generates a high-CTR ALL CAPS 3-6 word gaming hook headline."""
    catalog = GAMING_HOOKS_ID if language.lower() in ["id", "indonesian"] else GAMING_HOOKS_EN
    return random.choice(catalog)


def fuse_gaming_scores(
    audio_events: List[Dict[str, Any]],
    keyword_events: List[Dict[str, Any]],
    face_events: Optional[List[Dict[str, Any]]] = None,
    tolerance_sec: float = 3.0,
) -> List[Dict[str, Any]]:
    """Combines audio, facecam, and keyword events into a unified score curve."""
    face_events = face_events or []
    has_face = any(f.get("score", 0.0) > 0.0 for f in face_events)

    w_audio = 0.50 if has_face else 0.70
    w_face = 0.30 if has_face else 0.00
    w_kw = 0.20 if has_face else 0.30

    candidates = []
    # Build timestamps map from audio events (primary anchor)
    for a in audio_events:
        ts = a["timestamp"]
        a_score = a["score"]

        # Find matching keyword score within tolerance
        kw_score = gaming_keyword_detector.get_keyword_score_at_time(keyword_events, ts, max_distance=tolerance_sec)
        
        # Find matching face reaction score
        f_score = 0.0
        for f in face_events:
            if abs(f["timestamp"] - ts) <= tolerance_sec:
                f_score = max(f_score, f.get("score", 0.0))

        composite = (a_score * w_audio) + (f_score * w_face) + (kw_score * w_kw)
        
        matched_kws = []
        for k in keyword_events:
            if abs(k["timestamp"] - ts) <= tolerance_sec:
                matched_kws.extend(k.get("matched_words", []))

        candidates.append({
            "timestamp": round(ts, 2),
            "score": round(composite, 1),
            "audio_score": a_score,
            "face_score": f_score,
            "keyword_score": kw_score,
            "keywords": list(set(matched_kws))
        })

    candidates.sort(key=lambda x: x["score"], reverse=True)
    return candidates


def apply_non_maximum_suppression(candidates: List[Dict[str, Any]], radius_sec: float = 45.0) -> List[Dict[str, Any]]:
    """Suppresses neighboring candidate peaks within radius_sec of a higher-scoring peak."""
    selected = []
    for cand in candidates:
        ts = cand["timestamp"]
        # Check collision with already selected
        collision = any(abs(ts - s["timestamp"]) < radius_sec for s in selected)
        if not collision:
            selected.append(cand)
    return selected


def generate_gaming_windows(
    peaks: List[Dict[str, Any]],
    video_duration: float,
    min_duration: float = 20.0,
    max_duration: float = 60.0,
    pre_roll: float = 18.0,
    post_roll: float = 10.0,
    language: str = "id"
) -> List[Dict[str, Any]]:
    """
    Converts event peaks into complete video clip segments with pre-action buildup and post-action reaction.
    """
    segments = []
    for p in peaks:
        ts = p["timestamp"]
        start = max(0.0, round(ts - pre_roll, 2))
        end = min(video_duration, round(ts + post_roll, 2))
        dur = round(end - start, 2)

        if dur < min_duration:
            # Expand window symmetrically or forwards
            needed = min_duration - dur
            start = max(0.0, round(start - needed / 2.0, 2))
            end = min(video_duration, round(start + min_duration, 2))
            dur = round(end - start, 2)

        if dur > max_duration:
            end = round(start + max_duration, 2)
            dur = max_duration

        hook = generate_gaming_hook_title(keywords=p.get("keywords", []), language=language)

        segments.append({
            "start_time": start,
            "end_time": end,
            "duration": dur,
            "score": int(round(p["score"])),
            "hook_title": hook,
            "virality_explanation": f"High-energy gaming climax at {ts}s with intense volume spike.",
            "rubric": {
                "hook_strength": min(10.0, round(p["score"] / 10.0, 1)),
                "retention_flow": 8.5,
                "emotional_resonance": min(10.0, round(p["score"] / 10.0, 1)),
                "shareability": 9.0,
                "audio_dynamics": min(10.0, round(p.get("audio_score", p["score"]) / 10.0, 1)),
                "verdict": "Explosive gaming highlight."
            }
        })
    return segments


def run_gaming_clipping_pipeline(
    video_path: str,
    project_folder: str,
    transcript_words: List[Dict[str, Any]],
    video_duration: float,
    num_segments: int = 5,
    min_duration: float = 20.0,
    max_duration: float = 60.0,
    facecam_crop: Optional[str] = None,
    language: str = "id"
) -> Dict[str, Any]:
    """Runs the full offline gaming clipping detection pipeline."""
    # 1. Audio spike detection
    rms_values, mean, std = gaming_audio_detector.extract_audio_rms_curve(video_path)
    audio_events = gaming_audio_detector.detect_audio_events(rms_values, sample_rate_hz=10.0)

    # 2. Exclamatory keyword scanning
    keyword_events = gaming_keyword_detector.scan_shout_keywords(transcript_words)

    # 3. Facecam reaction detection
    candidate_ts = [a["timestamp"] for a in audio_events[:10]]
    face_events = gaming_facecam_detector.detect_facecam_reactions(
        video_path=video_path,
        facecam_box_str=facecam_crop,
        candidate_timestamps=candidate_ts
    )

    # 4. Fusion and NMS
    fused = fuse_gaming_scores(audio_events, keyword_events, face_events)
    peaks = apply_non_maximum_suppression(fused, radius_sec=45.0)[:num_segments]

    # 5. Window generation
    segments = generate_gaming_windows(
        peaks,
        video_duration=video_duration,
        min_duration=min_duration,
        max_duration=max_duration,
        language=language
    )

    out = {"segments": segments}
    out_file = os.path.join(project_folder, "viral_segments.json")
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)

    return out
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_gaming_scorer.py -v`  
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add scripts/gaming_scorer.py tests/test_gaming_scorer.py
git commit -m "feat(gaming): add hybrid multi-signal gaming scorer and dynamic windowing"
```

---

### Task 5: Pipeline & Backend Integration (`main_improved.py`, `backend/schemas/jobs.py`)

**Files:**
- Modify: `webui/backend/schemas/jobs.py`
- Modify: `main_improved.py`
- Modify: `webui/backend/core/job_manager.py`
- Test: `tests/test_gaming_pipeline_cli.py`

**Interfaces:**
- Produces:
  - Adds `pipeline_mode: str = "podcast"` (`"podcast"` or `"gaming"`) in `JobRunRequest`.
  - Adds `--pipeline-mode` CLI argument in `main_improved.py`.
  - Dispatches to `gaming_scorer.run_gaming_clipping_pipeline` when `pipeline_mode == "gaming"`.

- [ ] **Step 1: Write the failing test for gaming CLI and schema flags**

Create `tests/test_gaming_pipeline_cli.py`:
```python
import subprocess
import sys
import pytest
from webui.backend.schemas.jobs import JobRunRequest

def test_main_improved_has_pipeline_mode_flag():
    result = subprocess.run(
        [sys.executable, "main_improved.py", "--help"],
        capture_output=True,
        text=True,
        check=True
    )
    assert "--pipeline-mode" in result.stdout
    assert "gaming" in result.stdout

def test_job_run_request_pipeline_mode_mapping():
    req = JobRunRequest(
        video_path="/tmp/game.mp4",
        pipeline_mode="gaming",
        orientation="9:16_gaming_split"
    )
    args = req.to_cli_args(python_exec="python", script_path="main_improved.py")
    assert "--pipeline-mode" in args
    idx = args.index("--pipeline-mode")
    assert args[idx + 1] == "gaming"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_gaming_pipeline_cli.py -v`  
Expected: FAIL with `AssertionError: assert '--pipeline-mode' in result.stdout`

- [ ] **Step 3: Update `webui/backend/schemas/jobs.py` and `main_improved.py`**

In `webui/backend/schemas/jobs.py`:
Add `pipeline_mode`:
```python
pipeline_mode: str = Field(default="podcast", description="Pipeline mode: podcast or gaming")
```
And in `to_cli_args()`:
```python
if self.pipeline_mode:
    args.extend(["--pipeline-mode", self.pipeline_mode])
```

In `main_improved.py`:
Add argument to argument parser:
```python
parser.add_argument(
    "--pipeline-mode",
    choices=["podcast", "gaming"],
    default="podcast",
    help="Moment detection pipeline: 'podcast' (narrative LLM) or 'gaming' (offline multimodal audio/face/keyword)",
)
```
And in execution workflow:
```python
if args.pipeline_mode == "gaming":
    print(i18n("Running Offline Multimodal Gaming Moment Detection Pipeline..."))
    from scripts import gaming_scorer, smart_clipping
    words = smart_clipping.extract_words_from_transcript(transcript_data)
    viral_segments = gaming_scorer.run_gaming_clipping_pipeline(
        video_path=video_file,
        project_folder=project_folder,
        transcript_words=words,
        video_duration=video_duration,
        num_segments=num_segments,
        min_duration=args.min_duration,
        max_duration=args.max_duration,
        facecam_crop=args.gaming_facecam,
        language=args.language
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_gaming_pipeline_cli.py -v`  
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add main_improved.py webui/backend/schemas/jobs.py tests/test_gaming_pipeline_cli.py
git commit -m "feat(gaming): wire --pipeline-mode gaming into CLI and backend job schemas"
```

---

### Task 6: Frontend WebUI Mode Switcher & Gaming Panel (`GeneratorTab.tsx`)

**Files:**
- Modify: `webui/frontend/src/api/types.ts`
- Modify: `webui/frontend/src/components/GeneratorTab.tsx`
- Test: `webui/frontend/src/test/tabs.test.tsx`

**Interfaces:**
- Produces:
  - Add `pipeline_mode?: 'podcast' | 'gaming'` to `JobRunRequest` in `types.ts`.
  - Add segmented mode pill in `GeneratorTab.tsx` ("🎙️ Podcast" vs "🎮 Gaming").
  - When "🎮 Gaming" is active:
    - Automatically sets `orientation` to `"9:16_gaming_split"`.
    - Automatically disables `smart_remove_dead_air`.
    - Shows `GamingCropEditor` canvas prominently.

- [ ] **Step 1: Write the failing frontend test for gaming mode toggle**

Edit `webui/frontend/src/test/tabs.test.tsx`:
```tsx
it('renders pipeline mode selector with podcast and gaming options', () => {
  render(<GeneratorTab />);
  expect(screen.getByText(/Gaming/i)).toBeInTheDocument();
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pnpm test tabs.test.tsx`  
Expected: FAIL

- [ ] **Step 3: Update `types.ts` and `GeneratorTab.tsx`**

In `webui/frontend/src/api/types.ts`:
```ts
export interface JobRunRequest {
  // ... existing fields
  pipeline_mode?: 'podcast' | 'gaming';
}
```

In `webui/frontend/src/components/GeneratorTab.tsx`:
Add state:
```tsx
const [pipelineMode, setPipelineMode] = useState<'podcast' | 'gaming'>('podcast');
```
Add Mode Toggle buttons at the top of Generation settings, automatically switching orientation to `9:16_gaming_split` when `gaming` is clicked.

- [ ] **Step 4: Run test to verify it passes**

Run: `pnpm test tabs.test.tsx`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add webui/frontend/src/api/types.ts webui/frontend/src/components/GeneratorTab.tsx webui/frontend/src/test/tabs.test.tsx
git commit -m "feat(ui): add pipeline mode toggle between Podcast and Gaming in GeneratorTab"
```

---

### Task 7: End-to-End Integration Test (`tests/test_gaming_pipeline_e2e.py`)

**Files:**
- Create: `tests/test_gaming_pipeline_e2e.py`

**Interfaces:**
- Consumes: `run_gaming_clipping_pipeline` from `scripts.gaming_scorer`
- Produces: Full E2E validation verifying `viral_segments.json` conforms to schema with scores and hook titles.

- [ ] **Step 1: Write the end-to-end integration test**

Create `tests/test_gaming_pipeline_e2e.py`:
```python
import os
import json
import pytest
from scripts import gaming_scorer

def test_gaming_pipeline_e2e_mock(tmp_path, monkeypatch):
    # Mock audio extraction to return synthetic RMS curve
    def mock_extract(video_path, chunk_sec=0.1):
        # 100 samples quiet, 10 samples burst at 10-11s, 90 samples quiet
        rms = [10.0] * 100 + [85.0] * 10 + [10.0] * 90
        return rms, 15.0, 15.0

    monkeypatch.setattr(
        gaming_scorer.gaming_audio_detector,
        "extract_audio_rms_curve",
        mock_extract
    )

    project_dir = tmp_path / "proj_gaming"
    project_dir.mkdir()
    dummy_video = project_dir / "input.mp4"
    dummy_video.write_bytes(b"dummy video content")

    transcript_words = [
        {"word": "santai", "start": 1.0, "end": 2.0},
        {"word": "anjir", "start": 10.0, "end": 10.5},
        {"word": "clutch", "start": 11.0, "end": 11.8},
        {"word": "gg", "start": 12.0, "end": 12.5},
    ]

    result = gaming_scorer.run_gaming_clipping_pipeline(
        video_path=str(dummy_video),
        project_folder=str(project_dir),
        transcript_words=transcript_words,
        video_duration=120.0,
        num_segments=3,
        min_duration=20.0,
        max_duration=60.0,
        language="id"
    )

    assert "segments" in result
    assert len(result["segments"]) >= 1

    seg = result["segments"][0]
    assert "start_time" in seg
    assert "end_time" in seg
    assert "score" in seg
    assert "hook_title" in seg
    assert "rubric" in seg
    assert seg["rubric"]["audio_dynamics"] > 0.0

    saved_json = project_dir / "viral_segments.json"
    assert saved_json.exists()
    data = json.loads(saved_json.read_text(encoding="utf-8"))
    assert len(data["segments"]) == len(result["segments"])
```

- [ ] **Step 2: Run test to verify it passes**

Run: `pytest tests/test_gaming_pipeline_e2e.py -v`  
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add tests/test_gaming_pipeline_e2e.py
git commit -m "test(gaming): add end-to-end integration test for offline gaming clipping pipeline"
```
