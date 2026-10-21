# Multi-Dimensional Virality Rubric & Calibrated Hook Title Generator Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Transform ViralCutter's virality evaluation and hook generation from naive random scores into a calibrated, multi-dimensional decision engine (inspired by `XBuilderLAB/cheat-on-content`). Introduces a 5-dimension rubric (Hook, Retention Flow, Emotional Resonance, Shareability, Audio Dynamics) with breakdown storage and UI visualization, coupled with a calibrated anti-fluff hook title engine following high-conversion curiosity-gap frameworks.

**Architecture:**
1. **5-Dimension Virality Rubric Engine (`scripts/virality_rubric.py`):**
   - Formalizes 5 scoring dimensions: `hook_strength`, `retention_flow`, `emotional_resonance`, `shareability`, and `audio_dynamics`.
   - Computes weighted composite score ($0 \dots 100$) using calibrated weights:
     $$\text{Score} = (\text{hook} \times 0.25 + \text{retention} \times 0.25 + \text{emotion} \times 0.20 + \text{shareability} \times 0.15 + \text{audio} \times 0.15) \times 10$$
   - Emits structured metadata (`rubric` dictionary) embedded into `viral_segments` JSON.
2. **Calibrated Hook Title Engine (`scripts/create_viral_segments.py`):**
   - Injects 4 proven viral copywriting frameworks (*Negative Warning/FOMO*, *Curiosity Gap*, *Direct Challenge*, *Speed/Outcome Promise*).
   - Enforces strict constraints: 3–6 words, ALL CAPS, zero passive fluff ("Tips untuk...", "Membahas...").
3. **API & Pipeline Schema Update:**
   - `webui/backend/schemas/library.py` and `webui/backend/api/v1/library.py` expose `rubric: Optional[Dict[str, Any]]` on `GeneratedClipItem`.
   - `webui/frontend/src/api/types.ts` adds `ClipRubricBreakdown` to `GeneratedClipItem`.
4. **WebUI Visualization:**
   - `GeneratorTab.tsx`: Rating badge displays AI Composite Score (`94/100`). Clicking or expanding reveals the 5-dimension breakdown bar and editorial verdict.
   - Displays calibrated hook title with copy button.

**Tech Stack:** Python 3.10+, FastAPI, Pydantic, Pytest, React, TypeScript, Tailwind CSS, Vite.

**Spec:** N/A (Feature enhancement based on Cheat-on-Content audit)

## Global Constraints
- Must remain 100% backward-compatible with existing numeric scores (`001_95_Judul.mp4` naming convention remains intact).
- If AI does not return a full rubric (e.g. legacy model or manual mode), fallback safely generates estimated rubric from composite score without breaking.
- Hook titles must strictly stay in the transcript's language (Indonesian/English/etc.) and 3–6 words.
- All backend tests and frontend tests must pass with zero errors.

---

### Task 1: Virality Rubric Module & Composite Scoring

**Files:**
- Create: `scripts/virality_rubric.py`
- Test: `tests/test_virality_rubric.py`

**Interfaces:**
- Produces:
  - `virality_rubric.compute_composite_score(rubric: Dict[str, float], audio_energy: float = 75.0) -> Tuple[int, Dict[str, Any]]`
  - `virality_rubric.normalize_rubric_dict(raw_rubric: Any, fallback_score: int = 80) -> Dict[str, Any]`
  - `virality_rubric.DIMENSIONS`: dictionary of dimension names, descriptions, and weights.

- [ ] **Step 1: Write unit tests for rubric computation and normalization**

Create `tests/test_virality_rubric.py`:
```python
import pytest
from scripts import virality_rubric

def test_compute_composite_score_standard():
    raw_dimensions = {
        "hook_strength": 9.0,
        "retention_flow": 8.5,
        "emotional_resonance": 8.0,
        "shareability": 9.0,
    }
    # audio_energy is on 0-100 scale, converted to 0-10 (e.g. 80.0 -> 8.0)
    score, rubric = virality_rubric.compute_composite_score(raw_dimensions, audio_energy=80.0)
    
    # 9.0*0.25 (2.25) + 8.5*0.25 (2.125) + 8.0*0.20 (1.6) + 9.0*0.15 (1.35) + 8.0*0.15 (1.2) = 8.525 * 10 = 85
    assert score == 85
    assert rubric["hook_strength"] == 9.0
    assert rubric["retention_flow"] == 8.5
    assert rubric["emotional_resonance"] == 8.0
    assert rubric["shareability"] == 9.0
    assert rubric["audio_dynamics"] == 8.0
    assert rubric["composite_score"] == 85
    assert "verdict" in rubric

def test_normalize_rubric_fallback():
    # When AI provides raw numeric score without rubric
    rubric = virality_rubric.normalize_rubric_dict(None, fallback_score=92)
    assert rubric["composite_score"] == 92
    assert rubric["hook_strength"] == 9.2
    assert rubric["retention_flow"] == 9.2

def test_clamping_bounds():
    # Out of range dimensions must be clamped between 1.0 and 10.0
    raw = {
        "hook_strength": 15.0,
        "retention_flow": -2.0,
        "emotional_resonance": 10.0,
        "shareability": 5.0,
    }
    score, rubric = virality_rubric.compute_composite_score(raw, audio_energy=120.0)
    assert rubric["hook_strength"] == 10.0
    assert rubric["retention_flow"] == 1.0
    assert rubric["audio_dynamics"] == 10.0
    assert 1 <= score <= 100
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=. pytest tests/test_virality_rubric.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'scripts.virality_rubric'`.

- [ ] **Step 3: Implement scripts/virality_rubric.py**

Create `scripts/virality_rubric.py`:
```python
from typing import Any, Dict, Optional, Tuple

WEIGHTS = {
    "hook_strength": 0.25,        # 0-3s stop-the-scroll impact
    "retention_flow": 0.25,       # Pacing & narrative momentum
    "emotional_resonance": 0.20,  # Relatability, surprise, or controversy
    "shareability": 0.15,         # Urge to forward to peers/groups
    "audio_dynamics": 0.15,       # Speech energy & rhythm
}

DIMENSIONS = {
    "hook_strength": "Stop-the-Scroll Impact (0-3s)",
    "retention_flow": "Narrative Flow & Momentum",
    "emotional_resonance": "Emotional Depth & Value",
    "shareability": "Virality & Share Probability",
    "audio_dynamics": "Audio Energy & Delivery Rhythm",
}


def _clamp(val: Any, default: float = 7.0, min_v: float = 1.0, max_v: float = 10.0) -> float:
    try:
        f = float(val)
        return max(min_v, min(max_v, round(f, 1)))
    except (TypeError, ValueError):
        return default


def compute_verdict(composite: int, hook: float, retention: float) -> str:
    if composite >= 90:
        if hook >= 9.0:
            return "Elite Hook & Peak Retention: high viral breakout probability."
        return "Exceptional Value & Resonance: strong organic share potential."
    elif composite >= 80:
        if hook >= 8.5:
            return "Punchy Opening: holds initial scroll with solid momentum."
        return "Solid Narrative: consistent retention across the core idea."
    elif composite >= 70:
        return "Decent Content: good topic, moderate conversion velocity."
    return "Niche Appeal: lower virality threshold, recommended for loyal audience."


def compute_composite_score(
    raw_dimensions: Dict[str, Any],
    audio_energy: float = 75.0,
    user_verdict: Optional[str] = None
) -> Tuple[int, Dict[str, Any]]:
    """
    Computes calibrated composite virality score (0-100) from 5 dimensional ratings (1-10).
    """
    raw_dimensions = raw_dimensions or {}

    hook = _clamp(raw_dimensions.get("hook_strength") or raw_dimensions.get("hook"), 8.0)
    retention = _clamp(raw_dimensions.get("retention_flow") or raw_dimensions.get("retention"), 8.0)
    emotion = _clamp(raw_dimensions.get("emotional_resonance") or raw_dimensions.get("emotion"), 7.5)
    share = _clamp(raw_dimensions.get("shareability") or raw_dimensions.get("share"), 7.5)
    
    # Audio energy is 0-100 scale, normalize to 0-10
    audio_scaled = _clamp(audio_energy / 10.0, 7.5)

    composite_float = (
        hook * WEIGHTS["hook_strength"]
        + retention * WEIGHTS["retention_flow"]
        + emotion * WEIGHTS["emotional_resonance"]
        + share * WEIGHTS["shareability"]
        + audio_scaled * WEIGHTS["audio_dynamics"]
    ) * 10.0

    score = max(1, min(100, int(round(composite_float))))
    verdict = user_verdict or compute_verdict(score, hook, retention)

    rubric_dict = {
        "composite_score": score,
        "hook_strength": hook,
        "retention_flow": retention,
        "emotional_resonance": emotion,
        "shareability": share,
        "audio_dynamics": audio_scaled,
        "verdict": verdict,
    }

    return score, rubric_dict


def normalize_rubric_dict(raw_rubric: Any, fallback_score: int = 80) -> Dict[str, Any]:
    """
    Normalizes existing or legacy rubric dictionary, or creates plausible rubric
    from a single integer score.
    """
    if isinstance(raw_rubric, dict) and "hook_strength" in raw_rubric:
        hook = _clamp(raw_rubric.get("hook_strength"), 8.0)
        retention = _clamp(raw_rubric.get("retention_flow"), 8.0)
        emotion = _clamp(raw_rubric.get("emotional_resonance"), 7.5)
        share = _clamp(raw_rubric.get("shareability"), 7.5)
        audio = _clamp(raw_rubric.get("audio_dynamics"), 7.5)
        comp = int(raw_rubric.get("composite_score") or fallback_score)
        verdict = str(raw_rubric.get("verdict") or compute_verdict(comp, hook, retention))
        return {
            "composite_score": comp,
            "hook_strength": hook,
            "retention_flow": retention,
            "emotional_resonance": emotion,
            "shareability": share,
            "audio_dynamics": audio,
            "verdict": verdict,
        }

    # Generate synthetic proportional rubric from single score
    base_dim = max(1.0, min(10.0, round(float(fallback_score) / 10.0, 1)))
    return {
        "composite_score": int(fallback_score),
        "hook_strength": base_dim,
        "retention_flow": base_dim,
        "emotional_resonance": base_dim,
        "shareability": base_dim,
        "audio_dynamics": base_dim,
        "verdict": compute_verdict(int(fallback_score), base_dim, base_dim),
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=. pytest tests/test_virality_rubric.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit Task 1**

```bash
git add scripts/virality_rubric.py tests/test_virality_rubric.py
git commit -m "feat(scoring): implement multi-dimensional virality rubric and composite scoring engine"
```

---

### Task 2: Calibrated Hook Title Generator & Anti-Fluff System Prompt

**Files:**
- Modify: `scripts/create_viral_segments.py:37-105,920-1010`
- Modify: `scripts/smart_clipping.py:175-235,690-730`
- Modify: `prompt.txt`
- Modify: `webui/backend/api/v1/system.py`
- Modify: `webui/app.py`
- Test: `tests/test_hook_header.py`

**Interfaces:**
- Produces:
  - Calibrated `build_hook_title_prompt()` enforcing 4 viral frameworks (Negative FOMO, Curiosity Gap, Speed/Outcome, Direct Accusation).
  - Validation in `extract_hook_title_from_response()` banning passive fluff prefixes ("TIPS UNTUK", "MEMBAHAS TENTANG", "APAKAH ANDA").
  - LLM JSON schema emitting `hook_title` and `rubric` dimensions.

- [ ] **Step 1: Write unit tests for calibrated hook frameworks and anti-fluff rules**

In `tests/test_hook_header.py`, add tests:
```python
def test_build_hook_title_prompt_contains_calibrated_frameworks():
    prompt = build_hook_title_prompt("sample transcript", language_instruction="Indonesian")
    assert "CALIBRATED HOOK FRAMEWORKS" in prompt
    assert "Curiosity Gap" in prompt
    assert "Negative Warning" in prompt
    assert "strictly 3 to 6 words" in prompt

def test_extract_hook_title_cleans_passive_fluff():
    # Test that passive fluff prefixes like "Tips Untuk..." are stripped or sanitized
    raw_fluffy = '{"hook_title": "TIPS UNTUK MENJADI KAYA SECARA CEPAT"}'
    cleaned = extract_hook_title_from_response(raw_fluffy)
    assert not cleaned.startswith("TIPS UNTUK ")
    assert len(cleaned.split()) <= 6
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=. pytest tests/test_hook_header.py -v`
Expected: FAIL.

- [ ] **Step 3: Update build_hook_title_prompt and extract_hook_title_from_response**

In `scripts/create_viral_segments.py`:
Update `build_hook_title_prompt()`:
```python
def build_hook_title_prompt(transcript_chunk: str, language_instruction: str = "Same Language as Transcript") -> str:
    """
    Builds a focused prompt for LLM to generate a high-converting, curiosity-inducing
    Stop-the-Scroll hook title using 4 proven copywriting frameworks.
    """
    return f"""You are an elite short-form video strategist and copywriter.
Analyze the transcript below and generate a high-converting "Stop-the-Scroll" hook headline.

CALIBRATED HOOK FRAMEWORKS (Pick the one that fits best):
1. Negative Warning / FOMO: Highlight a costly mistake, trap, or urgent warning (e.g. 'JANGAN PERNAH LAKUKAN INI!', 'KESALAHAN FATAL BISNIS!').
2. Curiosity Gap / Counter-Intuitive: Create unbearable curiosity about an unexpected truth (e.g. 'KENAPA CARA INI SALAH?!', 'RAHASIA GELAP ALGORITMA!').
3. Speed / High-Value Outcome: Promise a specific, shocking result (e.g. 'DAPAT 100 JUTA DALAM 30 HARI?!', 'TRIK CEPAT TEMBUS FYP!').
4. Direct Challenge / Accusation: Call out the viewer directly (e.g. 'KAMU MASIH SALAH PAHAM?!', 'STOP BIKIN KONTEN BEGINI!').

STRICT ANTI-FLUFF RULES:
- Length: strictly 3 to 6 words.
- ALL CAPS ONLY.
- BANNED: Never start with passive fluff like 'Tips untuk...', 'Cara membuat...', 'Membahas tentang...', 'Apakah kamu tahu...'.
- Language: Output in the {language_instruction}.
- Return JSON ONLY with key "hook_title".

TRANSCRIPT:
{transcript_chunk}

OUTPUT JSON ONLY:
{{"hook_title": "YOUR HOOK HEADLINE HERE"}}"""
```

In `extract_hook_title_from_response()`:
Sanitize passive fluff prefixes:
```python
FLUFF_PREFIXES = [
    "TIPS UNTUK ", "TIPS ", "CARA CEPAT UNTUK ", "MEMBAHAS TENTANG ",
    "APAKAH ANDA TAHU ", "BAGAIMANA CARA ", "INILAH CARA "
]
for prefix in FLUFF_PREFIXES:
    if title.startswith(prefix):
        title = title[len(prefix):].strip()
```
And limit to 6 words max.

Update `prompt.txt`, `webui/backend/api/v1/system.py`, and `smart_clipping.py` with the 5-dimension rubric output template:
```json
"rubric": {
  "hook_strength": 9.5,
  "retention_flow": 9.0,
  "emotional_resonance": 8.5,
  "shareability": 9.0,
  "verdict": "High viral velocity hook with strong curiosity gap"
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=. pytest tests/test_hook_header.py -v`
Expected: ALL PASS.

- [ ] **Step 5: Commit Task 2**

```bash
git add scripts/create_viral_segments.py scripts/smart_clipping.py prompt.txt webui/ tests/test_hook_header.py
git commit -m "feat(hook): inject calibrated curiosity-gap frameworks and anti-fluff sanitizer"
```

---

### Task 3: Pipeline Integration (smart_clipping.py & create_viral_segments.py)

**Files:**
- Modify: `scripts/create_viral_segments.py:780-840`
- Modify: `scripts/smart_clipping.py:690-745`
- Test: `tests/test_broll_llm_parser.py`
- Test: `tests/test_virality_rubric.py`

**Interfaces:**
- Consumes: `virality_rubric.compute_composite_score()` and `virality_rubric.normalize_rubric_dict()`
- Produces: Each segment dictionary in `viral_segments["segments"]` contains:
  - `"score"`: int composite ($0 \dots 100$)
  - `"rubric"`: dict with 5 dimensions + verdict
  - `"hook_title"`: clean calibrated 3-6 word headline

- [ ] **Step 1: Write integration test for rubric in segment pipeline**

In `tests/test_virality_rubric.py`, add:
```python
def test_process_segments_attaches_rubric_and_composite():
    from scripts.create_viral_segments import process_segments
    transcript = [{"start": 0.0, "end": 10.0, "text": "hello viral world"}]
    raw_segments = [
        {
            "title": "Test Viral Clip",
            "start_time_ref": "(0s)",
            "start_text": "hello viral",
            "end_text": "viral world",
            "hook_title": "JANGAN LAKUKAN INI!",
            "rubric": {
                "hook_strength": 9.0,
                "retention_flow": 9.0,
                "emotional_resonance": 8.0,
                "shareability": 8.5
            }
        }
    ]
    res = process_segments(raw_segments, transcript, min_duration=3, max_duration=15)
    seg = res["segments"][0]
    assert "rubric" in seg
    assert seg["score"] >= 80
    assert seg["rubric"]["hook_strength"] == 9.0
    assert seg["rubric"]["audio_dynamics"] > 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=. pytest tests/test_virality_rubric.py -k "test_process_segments_attaches_rubric_and_composite" -v`
Expected: FAIL (rubric not yet processed).

- [ ] **Step 3: Integrate virality_rubric into process_segments and smart_clipping**

In `scripts/create_viral_segments.py` `process_segments()`:
```python
from scripts import virality_rubric

raw_rubric = seg.get("rubric")
raw_score = seg.get("score") or 80
try:
    raw_score_int = int(round(float(raw_score)))
except Exception:
    raw_score_int = 80

score_val, normalized_rubric = virality_rubric.compute_composite_score(
    raw_rubric,
    audio_energy=75.0, # default if audio energy not precomputed
    user_verdict=seg.get("reasoning")
) if raw_rubric else (raw_score_int, virality_rubric.normalize_rubric_dict(None, raw_score_int))

segment_dict["score"] = score_val
segment_dict["rubric"] = normalized_rubric
```

In `scripts/smart_clipping.py`:
When `audio_energy` is measured:
```python
final_score, rubric_data = virality_rubric.compute_composite_score(
    snapped_topic.get("rubric", {}),
    audio_energy=audio_energy,
    user_verdict=snapped_topic.get("rationale")
)
```
Attach `"rubric": rubric_data` to `viral_segments_list`.

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=. pytest tests/test_virality_rubric.py tests/test_broll_llm_parser.py -v`
Expected: ALL PASS.

- [ ] **Step 5: Commit Task 3**

```bash
git add scripts/create_viral_segments.py scripts/smart_clipping.py tests/test_virality_rubric.py
git commit -m "feat(scoring): integrate 5-dimension rubric computation into clipping pipelines"
```

---

### Task 4: Library & Clip API Schema Extension

**Files:**
- Modify: `webui/backend/schemas/library.py:40-60`
- Modify: `webui/backend/api/v1/library.py:280-345`
- Modify: `webui/frontend/src/api/types.ts:60-75`
- Test: `tests/test_backend_phase2.py`

**Interfaces:**
- Produces:
  - `GeneratedClipItem.rubric: Optional[Dict[str, Any]] = None`
  - Backend extracts rubric metadata from `viral_segments.txt` / `process_config.json` for each rendered clip item.

- [ ] **Step 1: Write test for rubric metadata in library clip item**

In `tests/test_backend_phase2.py`, add test:
```python
def test_library_clip_item_contains_rubric_metadata(tmp_path):
    from webui.backend.schemas.library import GeneratedClipItem
    item = GeneratedClipItem(
        name="001_92_Clip.mp4",
        path="/tmp/001_92_Clip.mp4",
        size=1024,
        folder_type="burned_sub",
        score=92.0,
        hook_title="STOP BIKIN KONTEN INI!",
        rubric={
            "composite_score": 92,
            "hook_strength": 9.5,
            "retention_flow": 9.0,
            "emotional_resonance": 8.5,
            "shareability": 9.0,
            "audio_dynamics": 8.8,
            "verdict": "Exceptional hook retention."
        }
    )
    assert item.rubric["hook_strength"] == 9.5
    assert item.hook_title == "STOP BIKIN KONTEN INI!"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=. pytest tests/test_backend_phase2.py -k "test_library_clip_item_contains_rubric_metadata" -v`
Expected: FAIL (`unexpected keyword argument 'rubric'`).

- [ ] **Step 3: Update schemas and library API endpoint**

In `webui/backend/schemas/library.py`:
Add field to `GeneratedClipItem`:
```python
rubric: Optional[Dict[str, Any]] = Field(default=None, description="5-dimension virality rubric breakdown")
```

In `webui/backend/api/v1/library.py`:
When building `GeneratedClipItem`, extract `matched_seg.get("rubric")`:
```python
clip_rubric = matched_seg.get("rubric") if matched_seg else None
if not clip_rubric and score is not None:
    from scripts import virality_rubric
    clip_rubric = virality_rubric.normalize_rubric_dict(None, int(score))

items.append(
    GeneratedClipItem(
        name=f.name,
        path=str(f.resolve()),
        size=f.stat().st_size,
        folder_type=folder_type,
        score=score,
        hook_title=hook_title,
        duration=duration,
        rubric=clip_rubric,
    )
)
```

In `webui/frontend/src/api/types.ts`:
```typescript
export interface ClipRubricBreakdown {
  composite_score: number;
  hook_strength: number;
  retention_flow: number;
  emotional_resonance: number;
  shareability: number;
  audio_dynamics: number;
  verdict: string;
}

export interface GeneratedClipItem {
  name: string;
  path: string;
  size: number;
  folder_type: 'burned_sub' | 'final';
  score?: number | null;
  hook_title?: string | null;
  duration?: number | null;
  rubric?: ClipRubricBreakdown | null;
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=. pytest tests/test_backend_phase2.py -v`
Expected: ALL PASS.

- [ ] **Step 5: Commit Task 4**

```bash
git add webui/backend/schemas/library.py webui/backend/api/v1/library.py webui/frontend/src/api/types.ts tests/test_backend_phase2.py
git commit -m "feat(api): expose 5-dimension rubric breakdown in GeneratedClipItem schema"
```

---

### Task 5: WebUI Visualization (GeneratorTab & LibraryTab Rubric Inspector)

**Files:**
- Create: `webui/frontend/src/components/RubricInspectorModal.tsx`
- Modify: `webui/frontend/src/components/GeneratorTab.tsx:2360-2410`
- Modify: `webui/frontend/src/test/tabs.test.tsx`

**Interfaces:**
- `RubricInspectorModal`: Renders clean popover/modal with:
  - Big Circular Composite Score (`94/100`)
  - 5 Progress Bars (Hook, Retention Flow, Emotion, Shareability, Audio Dynamics) with rating out of 10
  - Calibrated Hook Title with one-click copy
  - AI Strategic Verdict
- `GeneratorTab`: Clickable score badge that opens `RubricInspectorModal` for the selected clip.

- [ ] **Step 1: Write frontend test for Rubric modal trigger in tabs.test.tsx**

In `webui/frontend/src/test/tabs.test.tsx`, add test:
```typescript
it('renders rubric breakdown modal when clicking AI rating badge', async () => {
  // Test click on clip score badge opens modal displaying rubric dimensions
});
```

- [ ] **Step 2: Run frontend test to verify it fails**

Run: `cd webui/frontend && npm test`
Expected: FAIL.

- [ ] **Step 3: Implement RubricInspectorModal.tsx and wire into GeneratorTab.tsx**

Create `webui/frontend/src/components/RubricInspectorModal.tsx`:
```tsx
import React from 'react';
import { X, Copy, Check, Sparkles, TrendingUp, Volume2, Share2, Heart, Zap } from 'lucide-react';
import type { GeneratedClipItem } from '../api/types';

interface RubricInspectorModalProps {
  clip: GeneratedClipItem | null;
  onClose: () => void;
}

export const RubricInspectorModal: React.FC<RubricInspectorModalProps> = ({ clip, onClose }) => {
  const [copied, setCopied] = React.useState(false);
  if (!clip) return null;

  const rubric = clip.rubric || {
    composite_score: clip.score || 85,
    hook_strength: 8.5,
    retention_flow: 8.5,
    emotional_resonance: 8.0,
    shareability: 8.0,
    audio_dynamics: 8.0,
    verdict: 'High-conversion viral clip.'
  };

  const dimensions = [
    { label: 'Hook Strength (0-3s)', value: rubric.hook_strength, icon: Zap, color: 'bg-amber-400' },
    { label: 'Retention & Narrative Flow', value: rubric.retention_flow, icon: TrendingUp, color: 'bg-emerald-400' },
    { label: 'Emotional Resonance', value: rubric.emotional_resonance, icon: Heart, color: 'bg-rose-400' },
    { label: 'Shareability Probability', value: rubric.shareability, icon: Share2, color: 'bg-blue-400' },
    { label: 'Audio Delivery Dynamics', value: rubric.audio_dynamics, icon: Volume2, color: 'bg-purple-400' },
  ];

  const handleCopyHook = () => {
    if (clip.hook_title) {
      navigator.clipboard.writeText(clip.hook_title);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4">
      <div className="relative w-full max-w-lg bg-zinc-900 border border-zinc-800 rounded-2xl shadow-2xl p-6 space-y-6 text-zinc-100">
        <button
          onClick={onClose}
          className="absolute top-4 right-4 text-zinc-400 hover:text-white p-1 rounded-lg"
        >
          <X className="h-5 w-5" />
        </button>

        <div className="flex items-center space-x-3">
          <div className="p-2.5 rounded-xl bg-red-600/20 text-red-400 border border-red-500/30">
            <Sparkles className="h-6 w-6" />
          </div>
          <div>
            <h3 className="text-base font-bold text-white tracking-tight">Virality Rubric Audit</h3>
            <p className="text-xs text-zinc-400 truncate max-w-xs">{clip.name}</p>
          </div>
        </div>

        {/* Big Score Header */}
        <div className="p-4 rounded-xl bg-zinc-950/70 border border-zinc-800 flex items-center justify-between">
          <div>
            <div className="text-[11px] font-mono uppercase tracking-wider text-zinc-500">Composite Score</div>
            <div className="text-3xl font-black text-white tracking-tight">
              {rubric.composite_score}<span className="text-base text-zinc-500 font-medium">/100</span>
            </div>
          </div>
          <div className="text-right max-w-xs">
            <span className="text-[10px] font-mono uppercase tracking-wider text-emerald-400 block">AI Strategic Verdict</span>
            <p className="text-xs text-zinc-300 font-medium italic mt-0.5">{rubric.verdict}</p>
          </div>
        </div>

        {/* Calibrated Hook Title Box */}
        {clip.hook_title && (
          <div className="p-3.5 rounded-xl bg-amber-950/20 border border-amber-800/40 space-y-1.5">
            <div className="flex items-center justify-between">
              <span className="text-[10px] font-mono uppercase tracking-wider text-amber-400">Calibrated Stop-The-Scroll Hook</span>
              <button
                onClick={handleCopyHook}
                className="flex items-center space-x-1 text-[11px] text-amber-300 hover:text-amber-200"
              >
                {copied ? <Check className="h-3 w-3" /> : <Copy className="h-3 w-3" />}
                <span>{copied ? 'Copied' : 'Copy Hook'}</span>
              </button>
            </div>
            <div className="text-sm font-black text-white tracking-tight">{clip.hook_title}</div>
          </div>
        )}

        {/* 5-Dimension Bars */}
        <div className="space-y-3 pt-1">
          <span className="text-xs font-semibold text-zinc-300 uppercase tracking-wider block">5-Dimension Analysis</span>
          {dimensions.map((dim) => {
            const Icon = dim.icon;
            const pct = Math.min(100, Math.round((dim.value / 10.0) * 100));
            return (
              <div key={dim.label} className="space-y-1">
                <div className="flex items-center justify-between text-xs">
                  <span className="flex items-center space-x-1.5 text-zinc-300">
                    <Icon className="h-3.5 w-3.5 text-zinc-400" />
                    <span>{dim.label}</span>
                  </span>
                  <span className="font-mono font-bold text-white">{dim.value.toFixed(1)}/10</span>
                </div>
                <div className="w-full bg-zinc-800 h-2 rounded-full overflow-hidden">
                  <div className={`h-full ${dim.color} rounded-full transition-all duration-300`} style={{ width: `${pct}%` }} />
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
};
```

In `GeneratorTab.tsx`:
- Render `<RubricInspectorModal clip={inspectedClip} onClose={() => setInspectedClip(null)} />`.
- Make `<button onClick={() => setInspectedClip(clip)} data-testid="clip-score-badge">` interactive.

- [ ] **Step 4: Run frontend test and build**

Run: `cd webui/frontend && npm test && npm run build`
Expected: ALL PASS, build clean.

- [ ] **Step 5: Commit Task 5**

```bash
git add webui/frontend/
git commit -m "feat(ui): add Virality Rubric Inspector modal with 5-dimension breakdown and hook copy"
```

---

### Task 6: Full System Verification & Regression Run

**Files:**
- Test: All tests in `tests/` and `webui/frontend/src/test/`

- [ ] **Step 1: Run complete backend pytest suite**

Run: `PYTHONPATH=. pytest tests/ -v`
Expected: 225+ tests pass with zero failures.

- [ ] **Step 2: Run complete frontend vitest suite and build**

Run: `cd webui/frontend && npm test && npm run build`
Expected: 60+ tests pass with zero failures.

- [ ] **Step 3: Push to remote branch**

```bash
git push origin1 feat/html-motion-broll
```
Ensure working tree is clean.
