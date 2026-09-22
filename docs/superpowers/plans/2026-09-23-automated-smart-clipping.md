# Automated Smart-Clipping Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the Automated Smart-Clipping core module that processes long videos into concise short clips with word-level timestamp snapping, 3-part narrative extraction (Hook, Core, Payoff) via LLM, and FFmpeg splicing, while placing the experimental feature under the pre-roll/post-roll area in WebUI and completely removing the legacy "compile into single video" feature.

**Architecture:** A dedicated module `scripts/smart_clipping.py` will handle word-level timestamp extraction, word-boundary snapping, LLM prompt generation/parsing for narrative topics (Hook, Core, Payoff), and FFmpeg slicing/splicing. CLI arguments in `main_improved.py` and UI components in `webui/app.py` directly wire this pipeline while stripping out legacy compilation logic.

**Tech Stack:** Python 3.10+, FFmpeg, WhisperX (or existing `input.json` / Whisper transcripts), Google GenAI / G4F / local LLM backends, Gradio (WebUI), pytest.

**Spec:** `docs/superpowers/specs/2026-09-23-automated-smart-clipping-design.md`

## Global Constraints

- Never cut audio mid-syllable: word snapping must snap `start` backwards to word start minus safety margin ($0.05$s) and `end` forwards to word end plus safety margin ($0.08$s).
- Narrative structure must contain Hook, Pembahasan Inti (Core), and Payoff.
- Experimental UI must be placed in `webui/app.py` directly beneath `pre_roll_input` and `post_roll_input`.
- Legacy compilation feature (`--compile`, `compile_mode_input`, etc.) must be completely removed without breaking unrelated workflows.

---

### Task 1: Word-Level Boundary Snapping Engine in `scripts/smart_clipping.py`

**Files:**
- Create: `scripts/smart_clipping.py`
- Create: `tests/test_smart_clipping_snapping.py`

**Interfaces:**
- Produces:
  - `extract_words_from_transcript(transcript_data: dict | list) -> list[dict]`: returns flattened list of words with `{"word": str, "start": float, "end": float, "score": float}`.
  - `snap_time_to_word_boundary(timestamp: float, words: list[dict], is_start: bool, window: float = 3.0, margin: float = 0.05) -> float`: snaps timestamp to nearest word boundary.
  - `snap_segment_boundaries(start_time: float, end_time: float, words: list[dict], margin: float = 0.05) -> tuple[float, float]`: snaps both ends and guarantees valid duration.

- [ ] **Step 1: Write the failing test**

Create `tests/test_smart_clipping_snapping.py`:
```python
import pytest
from scripts.smart_clipping import (
    extract_words_from_transcript,
    snap_time_to_word_boundary,
    snap_segment_boundaries,
)

SAMPLE_TRANSCRIPT = {
    "segments": [
        {
            "start": 1.0,
            "end": 3.0,
            "text": "Halo semuanya selamat datang",
            "words": [
                {"word": "Halo", "start": 1.05, "end": 1.40, "score": 0.9},
                {"word": "semuanya", "start": 1.45, "end": 2.10, "score": 0.95},
                {"word": "selamat", "start": 2.15, "end": 2.50, "score": 0.92},
                {"word": "datang", "start": 2.55, "end": 2.95, "score": 0.96},
            ],
        },
        {
            "start": 4.0,
            "end": 6.5,
            "text": "hari ini kita bahas topik seru",
            "words": [
                {"word": "hari", "start": 4.10, "end": 4.35, "score": 0.88},
                {"word": "ini", "start": 4.38, "end": 4.55, "score": 0.91},
                {"word": "kita", "start": 4.60, "end": 4.85, "score": 0.90},
                {"word": "bahas", "start": 4.90, "end": 5.25, "score": 0.94},
                {"word": "topik", "start": 5.30, "end": 5.70, "score": 0.93},
                {"word": "seru", "start": 5.75, "end": 6.20, "score": 0.95},
            ],
        }
    ]
}

def test_extract_words_from_transcript():
    words = extract_words_from_transcript(SAMPLE_TRANSCRIPT)
    assert len(words) == 10
    assert words[0]["word"] == "Halo"
    assert words[0]["start"] == 1.05
    assert words[-1]["word"] == "seru"
    assert words[-1]["end"] == 6.20

def test_snap_time_to_word_boundary_start():
    words = extract_words_from_transcript(SAMPLE_TRANSCRIPT)
    # Target 1.2s falls near "Halo" (1.05-1.40), start should snap to word start (1.05) minus margin (0.05) = 1.00
    snapped = snap_time_to_word_boundary(1.20, words, is_start=True, margin=0.05)
    assert snapped == pytest.approx(1.00, abs=0.01)

def test_snap_time_to_word_boundary_end():
    words = extract_words_from_transcript(SAMPLE_TRANSCRIPT)
    # Target 2.8s falls near "datang" (2.55-2.95), end should snap to word end (2.95) plus margin (0.05) = 3.00
    snapped = snap_time_to_word_boundary(2.80, words, is_start=False, margin=0.05)
    assert snapped == pytest.approx(3.00, abs=0.01)

def test_snap_segment_boundaries():
    words = extract_words_from_transcript(SAMPLE_TRANSCRIPT)
    start, end = snap_segment_boundaries(1.20, 2.80, words, margin=0.05)
    assert start == pytest.approx(1.00, abs=0.01)
    assert end == pytest.approx(3.00, abs=0.01)
    assert end > start
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_smart_clipping_snapping.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'scripts.smart_clipping'`

- [ ] **Step 3: Write minimal implementation in `scripts/smart_clipping.py`**

Create `scripts/smart_clipping.py` with snapping logic:
```python
import os
import json
import subprocess
from typing import List, Dict, Tuple, Optional, Any

def extract_words_from_transcript(transcript_data: Any) -> List[Dict[str, Any]]:
    """
    Extracts flat word list with start, end, word from transcript data dict or list.
    """
    words = []
    if isinstance(transcript_data, dict):
        segments = transcript_data.get("segments", [])
    elif isinstance(transcript_data, list):
        segments = transcript_data
    else:
        return words

    for seg in segments:
        seg_words = seg.get("words")
        if seg_words and isinstance(seg_words, list):
            for w in seg_words:
                text = str(w.get("word") or "").strip()
                start = w.get("start")
                end = w.get("end")
                if text and start is not None and end is not None:
                    words.append({
                        "word": text,
                        "start": float(start),
                        "end": float(end),
                        "score": float(w.get("score", 1.0) or 1.0)
                    })
        else:
            # Fallback if words not present in segment
            text = str(seg.get("text") or "").strip()
            start = seg.get("start")
            end = seg.get("end")
            if text and start is not None and end is not None:
                words.append({
                    "word": text,
                    "start": float(start),
                    "end": float(end),
                    "score": 1.0
                })
    return words

def snap_time_to_word_boundary(
    timestamp: float,
    words: List[Dict[str, Any]],
    is_start: bool,
    window: float = 3.0,
    margin: float = 0.05
) -> float:
    """
    Snaps timestamp to the nearest word boundary within a search window.
    For start: snaps to word start minus safety margin.
    For end: snaps to word end plus safety margin.
    """
    if not words:
        return max(0.0, timestamp)

    target = float(timestamp)
    candidates = []
    for w in words:
        ref_time = w["start"] if is_start else w["end"]
        diff = abs(ref_time - target)
        if diff <= window:
            candidates.append((diff, ref_time))

    if not candidates:
        return max(0.0, target)

    candidates.sort(key=lambda x: x[0])
    best_time = candidates[0][1]

    if is_start:
        return max(0.0, round(best_time - margin, 3))
    else:
        return max(0.0, round(best_time + margin, 3))

def snap_segment_boundaries(
    start_time: float,
    end_time: float,
    words: List[Dict[str, Any]],
    margin: float = 0.05,
    min_duration: float = 1.0
) -> Tuple[float, float]:
    """
    Snaps both start and end times to word boundaries while preserving minimum duration.
    """
    snapped_start = snap_time_to_word_boundary(start_time, words, is_start=True, margin=margin)
    snapped_end = snap_time_to_word_boundary(end_time, words, is_start=False, margin=margin)

    if snapped_end <= snapped_start + min_duration:
        snapped_end = max(snapped_start + min_duration, end_time)

    return snapped_start, snapped_end
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_smart_clipping_snapping.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/smart_clipping.py tests/test_smart_clipping_snapping.py
git commit -m "feat(smart-clipping): add word-level timestamp snapping engine"
```

---

### Task 2: LLM Narrative Context Analyzer (Hook, Core, Payoff) in `scripts/smart_clipping.py`

**Files:**
- Modify: `scripts/smart_clipping.py`
- Create: `tests/test_smart_clipping_llm.py`

**Interfaces:**
- Produces:
  - `build_narrative_prompt(transcript_text: str, target_min: float, target_max: float, num_topics: int = 3) -> str`: creates formatted prompt enforcing Hook, Core, Payoff structure.
  - `parse_narrative_topics(llm_response: str) -> List[Dict[str, Any]]`: parses JSON response and extracts topics with normalized hook, core, and payoff sub-segments.
  - `snap_narrative_topic_segments(topic: Dict[str, Any], words: List[Dict[str, Any]], margin: float = 0.05) -> Dict[str, Any]`: applies word boundary snapping to all sub-segments in a topic.

- [ ] **Step 1: Write the failing test**

Create `tests/test_smart_clipping_llm.py`:
```python
import pytest
from scripts.smart_clipping import (
    build_narrative_prompt,
    parse_narrative_topics,
    snap_narrative_topic_segments,
)

SAMPLE_LLM_RESPONSE = """
```json
{
  "topics": [
    {
      "title": "Rahasia Sukses Produktif",
      "rationale": "Hook kuat tentang bangun pagi dilanjutkan tips praktis dan kesimpulan mengejutkan.",
      "target_duration": 45.0,
      "segments": {
        "hook": {
          "start_time": 1.2,
          "end_time": 4.5,
          "text": "Kenapa kamu selalu bangun kesiangan?"
        },
        "core": {
          "start_time": 10.0,
          "end_time": 30.0,
          "text": "Trik utama adalah meletakkan alarm di luar kamar..."
        },
        "payoff": {
          "start_time": 50.0,
          "end_time": 60.0,
          "text": "Hasilnya, energimu meningkat 2 kali lipat."
        }
      }
    }
  ]
}
```
"""

SAMPLE_WORDS = [
    {"word": "Kenapa", "start": 1.15, "end": 1.45, "score": 0.95},
    {"word": "kesiangan", "start": 4.10, "end": 4.60, "score": 0.92},
    {"word": "Trik", "start": 9.95, "end": 10.20, "score": 0.91},
    {"word": "kamar", "start": 29.80, "end": 30.15, "score": 0.93},
    {"word": "Hasilnya", "start": 49.90, "end": 50.30, "score": 0.94},
    {"word": "lipat", "start": 59.85, "end": 60.25, "score": 0.96},
]

def test_build_narrative_prompt():
    prompt = build_narrative_prompt("transcript sample", target_min=15, target_max=60, num_topics=2)
    assert "Hook" in prompt
    assert "Pembahasan Inti" in prompt or "core" in prompt.lower()
    assert "Payoff" in prompt
    assert "transcript sample" in prompt

def test_parse_narrative_topics():
    topics = parse_narrative_topics(SAMPLE_LLM_RESPONSE)
    assert len(topics) == 1
    t = topics[0]
    assert t["title"] == "Rahasia Sukses Produktif"
    assert "hook" in t["segments"]
    assert "core" in t["segments"]
    assert "payoff" in t["segments"]
    assert t["segments"]["hook"]["start_time"] == 1.2
    assert t["segments"]["payoff"]["end_time"] == 60.0

def test_snap_narrative_topic_segments():
    topics = parse_narrative_topics(SAMPLE_LLM_RESPONSE)
    snapped_topic = snap_narrative_topic_segments(topics[0], SAMPLE_WORDS, margin=0.05)
    hook = snapped_topic["segments"]["hook"]
    core = snapped_topic["segments"]["core"]
    payoff = snapped_topic["segments"]["payoff"]

    # Hook: start near 1.15 -> snapped 1.10; end near 4.60 -> snapped 4.65
    assert hook["snapped_start"] == pytest.approx(1.10, abs=0.02)
    assert hook["snapped_end"] == pytest.approx(4.65, abs=0.02)

    # Core: start near 9.95 -> snapped 9.90; end near 30.15 -> snapped 30.20
    assert core["snapped_start"] == pytest.approx(9.90, abs=0.02)
    assert core["snapped_end"] == pytest.approx(30.20, abs=0.02)

    # Payoff: start near 49.90 -> snapped 49.85; end near 60.25 -> snapped 60.30
    assert payoff["snapped_start"] == pytest.approx(49.85, abs=0.02)
    assert payoff["snapped_end"] == pytest.approx(60.30, abs=0.02)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_smart_clipping_llm.py -v`
Expected: FAIL with `ImportError: cannot import name 'build_narrative_prompt'`

- [ ] **Step 3: Implement prompt building and topic parsing in `scripts/smart_clipping.py`**

Append to `scripts/smart_clipping.py`:
```python
import re

def build_narrative_prompt(
    transcript_text: str,
    target_min: float = 20.0,
    target_max: float = 90.0,
    num_topics: int = 3
) -> str:
    return f"""You are an elite short-form video editor specializing in narrative retention.
Analyze the following transcript with timestamps and extract {num_topics} standalone, high-impact topics.

Each topic MUST have a strict 3-part storytelling structure:
1. Hook (Pemantik): The opening question, bold statement, or intriguing premise that stops the scroll (approx 3-10s).
2. Core (Pembahasan Inti): The essential explanation, story body, or argument.
3. Payoff (Klimaks / Penutup): The key conclusion, unexpected twist, practical takeaway, or satisfying punchline.

Target duration for the total spliced topic is between {int(target_min)}s and {int(target_max)}s.
The sub-segments may be continuous or skip boring filler/tangents.

TRANSCRIPT:
{transcript_text}

OUTPUT FORMAT: Return VALID JSON ONLY matching this structure:
{{
  "topics": [
    {{
      "title": "Short punchy title",
      "rationale": "Why this story holds retention",
      "target_duration": 45.0,
      "segments": {{
        "hook": {{
          "start_time": 0.0,
          "end_time": 5.0,
          "text": "Exact text of the hook"
        }},
        "core": {{
          "start_time": 12.0,
          "end_time": 35.0,
          "text": "Exact text of the core"
        }},
        "payoff": {{
          "start_time": 50.0,
          "end_time": 60.0,
          "text": "Exact text of the payoff"
        }}
      }}
    }}
  ]
}}
"""

def parse_narrative_topics(llm_response: str) -> List[Dict[str, Any]]:
    """
    Parses LLM response into normalized list of topic dictionaries.
    """
    cleaned = re.sub(r'<think>.*?</think>', '', str(llm_response), flags=re.DOTALL)
    cleaned = re.sub(r'```(?:json)?', '', cleaned)
    cleaned = cleaned.strip()

    try:
        data = json.loads(cleaned)
    except Exception:
        # Fallback regex search for JSON object with "topics"
        match = re.search(r'\{.*"topics"\s*:\s*\[.*\]\s*\}', cleaned, re.DOTALL)
        if match:
            try:
                data = json.loads(match.group(0))
            except Exception:
                return []
        else:
            return []

    raw_topics = data.get("topics", [])
    valid_topics = []
    for t in raw_topics:
        if not isinstance(t, dict):
            continue
        segs = t.get("segments", {})
        if not isinstance(segs, dict):
            continue

        normalized_segs = {}
        for key in ["hook", "core", "payoff"]:
            part = segs.get(key, {})
            if isinstance(part, dict):
                normalized_segs[key] = {
                    "start_time": float(part.get("start_time", 0.0)),
                    "end_time": float(part.get("end_time", 0.0)),
                    "text": str(part.get("text", "")).strip()
                }

        if normalized_segs:
            valid_topics.append({
                "title": str(t.get("title", "Untitled Topic")),
                "rationale": str(t.get("rationale", "")),
                "target_duration": float(t.get("target_duration", 0.0)),
                "segments": normalized_segs
            })

    return valid_topics

def snap_narrative_topic_segments(
    topic: Dict[str, Any],
    words: List[Dict[str, Any]],
    margin: float = 0.05
) -> Dict[str, Any]:
    """
    Snaps all sub-segments of a topic (hook, core, payoff) to word boundaries.
    """
    updated_topic = json.loads(json.dumps(topic))
    segs = updated_topic.get("segments", {})

    for key, seg in segs.items():
        s = seg.get("start_time", 0.0)
        e = seg.get("end_time", 0.0)
        snapped_s, snapped_e = snap_segment_boundaries(s, e, words, margin=margin)
        seg["snapped_start"] = snapped_s
        seg["snapped_end"] = snapped_e
        seg["duration"] = round(snapped_e - snapped_s, 3)

    return updated_topic
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_smart_clipping_llm.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/smart_clipping.py tests/test_smart_clipping_llm.py
git commit -m "feat(smart-clipping): add narrative prompt builder, parser, and topic snapping"
```

---

### Task 3: Audio Extraction & FFmpeg Splicing Engine in `scripts/smart_clipping.py`

**Files:**
- Modify: `scripts/smart_clipping.py`
- Create: `tests/test_smart_clipping_splicing.py`

**Interfaces:**
- Produces:
  - `extract_audio_for_transcription(video_path: str, output_wav: str) -> str`: runs FFmpeg to extract 16kHz mono wav.
  - `build_ffmpeg_cut_command(video_path: str, start: float, end: float, output_path: str) -> List[str]`: builds command for sample-accurate cutting.
  - `splice_topic_segments(video_path: str, segments: List[Tuple[float, float]], output_path: str, temp_dir: Optional[str] = None) -> str`: cuts sub-segments and concatenates them with FFmpeg concat demuxer into final video.

- [ ] **Step 1: Write the failing test**

Create `tests/test_smart_clipping_splicing.py`:
```python
import os
import pytest
from unittest.mock import patch
from scripts.smart_clipping import (
    build_ffmpeg_cut_command,
    splice_topic_segments,
)

def test_build_ffmpeg_cut_command():
    cmd = build_ffmpeg_cut_command("input.mp4", 10.5, 25.0, "sub_1.mp4")
    assert cmd[0] == "ffmpeg"
    assert "-ss" in cmd
    assert "10.500" in cmd
    assert "-to" in cmd
    assert "25.000" in cmd
    assert "sub_1.mp4" in cmd

@patch("subprocess.run")
def test_splice_topic_segments_multi(mock_run, tmp_path):
    video = str(tmp_path / "input.mp4")
    out = str(tmp_path / "output.mp4")
    segments = [(1.0, 5.0), (12.0, 20.0), (30.0, 40.0)]

    splice_topic_segments(video, segments, out, temp_dir=str(tmp_path))
    # mock_run should be called 3 times for cuts, 1 time for concat
    assert mock_run.call_count == 4
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_smart_clipping_splicing.py -v`
Expected: FAIL with `ImportError: cannot import name 'build_ffmpeg_cut_command'`

- [ ] **Step 3: Implement FFmpeg cutting & splicing in `scripts/smart_clipping.py`**

Append to `scripts/smart_clipping.py`:
```python
import shutil

def extract_audio_for_transcription(video_path: str, output_wav: str) -> str:
    """
    Extracts 16kHz 16-bit mono PCM audio from video for fast, accurate speech transcription.
    """
    if os.path.exists(output_wav) and os.path.getsize(output_wav) > 1000:
        return output_wav

    os.makedirs(os.path.dirname(os.path.abspath(output_wav)), exist_ok=True)
    cmd = [
        "ffmpeg", "-y",
        "-i", video_path,
        "-vn",
        "-acodec", "pcm_s16le",
        "-ar", "16000",
        "-ac", "1",
        output_wav
    ]
    subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return output_wav

def build_ffmpeg_cut_command(video_path: str, start: float, end: float, output_path: str) -> List[str]:
    """
    Builds FFmpeg command to cut a segment accurately with re-encoding to avoid keyframe offset.
    """
    return [
        "ffmpeg", "-y",
        "-ss", f"{float(start):.3f}",
        "-to", f"{float(end):.3f}",
        "-i", video_path,
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "18",
        "-c:a", "aac",
        "-b:a", "192k",
        "-avoid_negative_ts", "make_zero",
        output_path
    ]

def splice_topic_segments(
    video_path: str,
    segments: List[Tuple[float, float]],
    output_path: str,
    temp_dir: Optional[str] = None
) -> str:
    """
    Extracts sub-segments and splices them into one video file.
    If single segment, cuts directly to output_path.
    If multiple segments, cuts each and concats losslessly via concat demuxer.
    """
    if not segments:
        raise ValueError("No segments provided for splicing.")

    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

    # Filter out empty or inverted segments
    valid_segs = [(s, e) for s, e in segments if e > s]
    if not valid_segs:
        raise ValueError("All segments have zero or invalid duration.")

    # Single segment optimization
    if len(valid_segs) == 1:
        s, e = valid_segs[0]
        cmd = build_ffmpeg_cut_command(video_path, s, e, output_path)
        subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return output_path

    # Multi-segment splicing
    cleanup_temp = False
    if not temp_dir:
        temp_dir = os.path.join(os.path.dirname(output_path), "temp_splice")
        cleanup_temp = True
    os.makedirs(temp_dir, exist_ok=True)

    sub_files = []
    try:
        for idx, (s, e) in enumerate(valid_segs):
            sub_path = os.path.join(temp_dir, f"subseg_{idx:03d}.mp4")
            cmd = build_ffmpeg_cut_command(video_path, s, e, sub_path)
            subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            sub_files.append(sub_path)

        concat_list_path = os.path.join(temp_dir, "concat_list.txt")
        with open(concat_list_path, "w", encoding="utf-8") as f:
            for p in sub_files:
                f.write(f"file '{os.path.abspath(p)}'\n")

        concat_cmd = [
            "ffmpeg", "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", concat_list_path,
            "-c", "copy",
            output_path
        ]
        subprocess.run(concat_cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    finally:
        if cleanup_temp and os.path.exists(temp_dir):
            shutil.rmtree(temp_dir, ignore_errors=True)

    return output_path
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_smart_clipping_splicing.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/smart_clipping.py tests/test_smart_clipping_splicing.py
git commit -m "feat(smart-clipping): add audio extraction and FFmpeg splicing engine"
```

---

### Task 4: Removal of Legacy "Compile into Single Video" Feature

**Files:**
- Modify: `main_improved.py:25-35, 175-180, 925-950`
- Modify: `webui/app.py:480-500, 595-605, 910-920, 1355-1385, 1910-1920`
- Modify: `webui/project_export.py:18-24, 90-97`

**Interfaces:**
- Consumes: Existing files
- Produces: Clean cutover with all `--compile`, `--crossfade`, `--segment-order`, `--fade-to-black`, `compile_mode_input` removed.

- [ ] **Step 1: Write test to verify `--compile` is absent and `main_improved.py` runs without errors**

Create `tests/test_compile_removed.py`:
```python
import subprocess
import sys

def test_compile_args_removed():
    result = subprocess.run(
        [sys.executable, "main_improved.py", "--help"],
        capture_output=True,
        text=True
    )
    assert result.returncode == 0
    assert "--compile" not in result.stdout
    assert "--crossfade" not in result.stdout
    assert "--segment-order" not in result.stdout
    assert "--fade-to-black" not in result.stdout
```

- [ ] **Step 2: Run test to verify it currently fails (args still present)**

Run: `pytest tests/test_compile_removed.py -v`
Expected: FAIL (`--compile` is currently present in stdout)

- [ ] **Step 3: Remove compilation arguments and logic from `main_improved.py`**

1. Remove `compile_segments` import from line ~28.
2. Remove parser arguments `--compile`, `--crossfade`, `--fade-to-black`, `--segment-order` (lines ~176-179).
3. Remove compilation execution block (lines ~927-947):
   ```python
   # Delete block:
   # if args.compile:
   #     ...
   #     compile_segments.compile_segments(...)
   ```

- [ ] **Step 4: Remove compilation inputs and event listeners from `webui/app.py`**

1. Remove `compile_mode`, `crossfade_duration`, `segment_order` parameters from `run_viral_cutter` signature.
2. Remove command-building lines:
   ```python
   # if compile_mode:
   #     cmd.append("--compile")
   #     ...
   ```
3. Remove `Compile: ...` from logging.
4. Remove `compile_mode_input`, `crossfade_duration_input`, `segment_order_input` Gradio components and `.change(...)` handlers (lines ~1356-1381).
5. Remove them from `start_btn.click(run_viral_cutter, inputs=[...])`.

- [ ] **Step 5: Clean up `webui/project_export.py`**

Remove `"compilation.mp4"` and `"compilation.srt"` from `ROOT_EXTRA_PATTERNS`.

- [ ] **Step 6: Run test to verify removal passes**

Run: `pytest tests/test_compile_removed.py -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add main_improved.py webui/app.py webui/project_export.py tests/test_compile_removed.py
git commit -m "refactor: remove legacy compile into single video feature"
```

---

### Task 5: WebUI & CLI Integration for Automated Smart-Clipping

**Files:**
- Modify: `main_improved.py`
- Modify: `webui/app.py`
- Modify: `scripts/smart_clipping.py`

**Interfaces:**
- CLI parameters:
  - `--smart-clipping`: Flag to enable automated smart clipping.
  - `--smart-clipping-mode`: `splice` (Hook+Core+Payoff) or `continuous`.
  - `--smart-snap-margin`: Float (default `0.05`).
- WebUI components (placed directly under `pre_roll_input` and `post_roll_input`):
  - `smart_clipping_input`: Checkbox "Automated Smart-Clipping (Experimental)"
  - `smart_clipping_mode_input`: Dropdown with mode options
  - `smart_snap_margin_input`: Number for snapping margin

- [ ] **Step 1: Write integration test for smart-clipping CLI options**

Create `tests/test_smart_clipping_cli.py`:
```python
import subprocess
import sys

def test_smart_clipping_cli_flags():
    result = subprocess.run(
        [sys.executable, "main_improved.py", "--help"],
        capture_output=True,
        text=True
    )
    assert result.returncode == 0
    assert "--smart-clipping" in result.stdout
    assert "--smart-clipping-mode" in result.stdout
    assert "--smart-snap-margin" in result.stdout
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_smart_clipping_cli.py -v`
Expected: FAIL (flags not yet added)

- [ ] **Step 3: Add CLI arguments and execution hook in `main_improved.py`**

In `main_improved.py`:
1. Add CLI arguments:
   ```python
   parser.add_argument("--smart-clipping", action="store_true", help="Enable Automated Smart-Clipping")
   parser.add_argument("--smart-clipping-mode", choices=["splice", "continuous"], default="splice", help="Smart-clipping mode")
   parser.add_argument("--smart-snap-margin", type=float, default=0.05, help="Word snapping margin in seconds")
   ```
2. Import `smart_clipping` from `scripts`.
3. In main execution flow, when `args.smart_clipping` is enabled:
   - Extract/verify word transcript.
   - Run narrative topic extraction with Hook, Core, Payoff.
   - Apply snapping and splice each topic into `smart_clips/` folder using FFmpeg.
   - Update `viral_segments` so downstream processing (subtitles, face tracking) continues smoothly.

- [ ] **Step 4: Add WebUI controls in `webui/app.py` under pre-roll/post-roll**

Directly under `pre_roll_input` and `post_roll_input`:
```python
                    with gr.Group():
                        smart_clipping_input = gr.Checkbox(label=i18n("Automated Smart-Clipping (Experimental)"), value=False)
                        with gr.Row(visible=False) as smart_clipping_options:
                            smart_clipping_mode_input = gr.Dropdown(
                                choices=[
                                    (i18n("Multi-Segment Splice (Hook + Core + Payoff)"), "splice"),
                                    (i18n("Single Continuous Topic"), "continuous")
                                ],
                                value="splice",
                                label=i18n("Narrative Structure Mode")
                            )
                            smart_snap_margin_input = gr.Number(label=i18n("Word Snap Margin (s)"), value=0.05, precision=2)

                    smart_clipping_input.change(
                        lambda enabled: gr.update(visible=enabled),
                        inputs=smart_clipping_input,
                        outputs=smart_clipping_options
                    )
```
Pass `smart_clipping_input`, `smart_clipping_mode_input`, `smart_snap_margin_input` into `run_viral_cutter` and append `--smart-clipping`, `--smart-clipping-mode`, `--smart-snap-margin` to `cmd`.

- [ ] **Step 5: Run CLI test to verify it passes**

Run: `pytest tests/test_smart_clipping_cli.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add main_improved.py webui/app.py tests/test_smart_clipping_cli.py
git commit -m "feat: integrate automated smart-clipping into CLI and WebUI"
```

---

### Task 6: End-to-End Pipeline Smoke Test & Verification

**Files:**
- Create: `tests/test_smart_clipping_e2e.py`

**Interfaces:**
- Tests complete flow: synthetic test video + mock WhisperX word timestamps -> narrative topic extraction -> word boundary snapping -> FFmpeg sub-segment splicing -> verified final video.

- [ ] **Step 1: Write the end-to-end smoke test**

Create `tests/test_smart_clipping_e2e.py`:
```python
import os
import subprocess
import pytest
from scripts.smart_clipping import (
    snap_narrative_topic_segments,
    splice_topic_segments,
)

def create_synthetic_video(output_path: str, duration: int = 15):
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi",
        "-i", f"testsrc=duration={duration}:size=320x240:rate=30",
        "-f", "lavfi",
        "-i", f"sine=frequency=1000:duration={duration}",
        "-c:v", "libx264",
        "-c:a", "aac",
        output_path
    ]
    subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

def test_smart_clipping_end_to_end(tmp_path):
    video_path = str(tmp_path / "test_long_video.mp4")
    create_synthetic_video(video_path, duration=15)
    assert os.path.exists(video_path)

    topic = {
        "title": "Synthetic Test Topic",
        "rationale": "Verify splicing",
        "target_duration": 8.0,
        "segments": {
            "hook": {"start_time": 1.0, "end_time": 3.0, "text": "Hook text"},
            "core": {"start_time": 5.0, "end_time": 8.0, "text": "Core text"},
            "payoff": {"start_time": 11.0, "end_time": 13.0, "text": "Payoff text"}
        }
    }

    words = [
        {"word": "Hook", "start": 0.95, "end": 1.5, "score": 0.9},
        {"word": "text", "start": 2.5, "end": 2.95, "score": 0.9},
        {"word": "Core", "start": 4.95, "end": 5.5, "score": 0.9},
        {"word": "text", "start": 7.5, "end": 7.95, "score": 0.9},
        {"word": "Payoff", "start": 10.95, "end": 11.5, "score": 0.9},
        {"word": "text", "start": 12.5, "end": 12.95, "score": 0.9},
    ]

    snapped = snap_narrative_topic_segments(topic, words, margin=0.05)
    hook = snapped["segments"]["hook"]
    core = snapped["segments"]["core"]
    payoff = snapped["segments"]["payoff"]

    segments_to_splice = [
        (hook["snapped_start"], hook["snapped_end"]),
        (core["snapped_start"], core["snapped_end"]),
        (payoff["snapped_start"], payoff["snapped_end"]),
    ]

    output_clip = str(tmp_path / "final_smart_clip.mp4")
    result_path = splice_topic_segments(video_path, segments_to_splice, output_clip)

    assert os.path.exists(result_path)
    assert os.path.getsize(result_path) > 1000

    # Probe duration of spliced output
    probe_cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        result_path
    ]
    res = subprocess.run(probe_cmd, capture_output=True, text=True, check=True)
    dur = float(res.stdout.strip())
    # Spliced segments: ~2.1s + ~3.1s + ~2.1s = ~7.3s
    assert 6.0 <= dur <= 9.0
```

- [ ] **Step 2: Run all tests in the test suite**

Run: `pytest tests/ -v`
Expected: ALL PASS

- [ ] **Step 3: Commit**

```bash
git add tests/test_smart_clipping_e2e.py
git commit -m "test: add end-to-end smoke test for smart-clipping pipeline"
```
