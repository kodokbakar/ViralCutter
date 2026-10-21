# AI Output Token Expansion & Timestamp Parsing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Resolve segment under-generation (where 12 requested segments drop to 8 or 9 on >1-hour videos) by expanding AI output token limits (`max_tokens`) to 16,384 for models like DeepSeek v4.1, and implementing a robust multi-format timestamp parser supporting `HH:MM:SS`, `MM:SS`, and `(XXs)` formats to prevent incorrect fallbacks to 0s and duplicate dropping.

**Architecture:** 
1. Expand `call_custom_api` default output tokens from 4,096 to 16,384, preventing mid-JSON truncation when generating 12+ segments with B-roll metadata, and enhance `<think>` tag stripping for reasoning models.
2. Replace naive regex digit parsing (`re.search(r'\d+', ...)`) in `scripts/create_viral_segments.py` with `parse_time_ref()`, supporting full `HH:MM:SS`, `MM:SS`, and decimal second tags so hours-long timestamps (e.g. `01:15:30` = 4530s) don't parse as 1s and trigger overlap deduplication drops.
3. Broaden the transcript search window in `process_segments()` to ensure accurate text matching in long videos.

**Tech Stack:** Python 3.10+, FastAPI, Pytest, Regex.

**Spec:** N/A (Bounded architectural bugfix)

## Global Constraints
- Must maintain 100% backward compatibility with existing Whisper `(XXs)` timestamp tags.
- Must support DeepSeek v4.1, OpenAI, Gemini, and local LLM endpoints.
- Output token increase must not break Ollama or local APIs that have configurable token caps.
- Full pytest test suite must pass with zero regressions.

---

### Task 1: Output Token Expansion & `<think>` Tag Sanitization for DeepSeek v4.1

**Files:**
- Modify: `scripts/create_viral_segments.py:115-135,510-530,1135-1150`
- Modify: `scripts/smart_clipping.py:310-325`
- Modify: `prompt.txt:30-40`
- Modify: `webui/backend/api/v1/system.py:50-65`
- Modify: `webui/app.py:425-440`
- Modify: `tests/test_custom_api.py:85-115`

**Interfaces:**
- Produces:
  - `call_custom_api(prompt, base_url, api_key="", model_name="gpt-4o-mini", timeout=360, max_tokens=16384)`
  - Enhanced `clean_json_response(response_text)` stripping `<think>...</think>` and unclosed `<think>...` blocks.

- [ ] **Step 1: Write test for expanded max_tokens and unclosed `<think>` stripping**

In `tests/test_custom_api.py`, update `test_call_custom_api_max_tokens_default` and add unclosed think test:

```python
def test_call_custom_api_max_tokens_default():
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "choices": [
            {"message": {"content": '{"segments": []}'}}
        ]
    }

    with patch("requests.post", return_value=mock_resp) as mock_post:
        result = call_custom_api(
            prompt="Hello",
            base_url="http://localhost:11434/v1",
            api_key="sk-test",
            model_name="deepseek-v4.1",
        )
        assert result == '{"segments": []}'
        payload = mock_post.call_args[1].get("json", {})
        # Verify expanded token limit
        assert payload.get("max_tokens") == 16384

def test_clean_json_response_strips_unclosed_think_tags():
    from scripts.create_viral_segments import clean_json_response
    raw = "<think>\nThinking about viral segments...\n" + '{"segments": [{"title": "Seg 1"}]}'
    cleaned = clean_json_response(raw)
    assert len(cleaned.get("segments", [])) == 1
    assert cleaned["segments"][0]["title"] == "Seg 1"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=. pytest tests/test_custom_api.py -k "test_call_custom_api_max_tokens_default or test_clean_json_response_strips_unclosed_think_tags" -v`
Expected: FAIL with `assert 4096 == 16384`.

- [ ] **Step 3: Update `call_custom_api`, `clean_json_response`, and prompt instructions**

In `scripts/create_viral_segments.py`:
1. Change default parameter in `call_custom_api`:
   `def call_custom_api(prompt, base_url, api_key="", model_name="gpt-4o-mini", timeout=360, max_tokens=16384):`
2. Update `call_custom_api` calls in `create_viral_segments.py` and `scripts/smart_clipping.py:315` to forward `max_tokens=16384`.
3. In `clean_json_response`:
   ```python
   # Strip complete think blocks
   response_text = re.sub(r'<think>.*?</think>', '', response_text, flags=re.DOTALL)
   # Strip unclosed think block at start if present
   response_text = re.sub(r'^<think>.*?(?=\{)', '', response_text, flags=re.DOTALL)
   ```
4. In `prompt.txt`, `webui/backend/api/v1/system.py`, and `webui/app.py`:
   Add constraint instruction:
   `- Keep "reasoning" concise (1 to 2 sentences) to preserve token output capacity for all requested segments.`

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=. pytest tests/test_custom_api.py -v`
Expected: ALL PASS.

- [ ] **Step 5: Commit Task 1**

```bash
git add scripts/create_viral_segments.py scripts/smart_clipping.py prompt.txt webui/ tests/test_custom_api.py
git commit -m "fix(ai): expand custom API max_tokens to 16384 and clean unclosed think tags"
```

---

### Task 2: Multi-Format Timestamp Parser (`parse_time_ref`) and Extended Window Search

**Files:**
- Modify: `scripts/create_viral_segments.py:685-750`
- Create: `tests/test_timestamp_parser.py`

**Interfaces:**
- Produces: `parse_time_ref(ref_time_str: Any) -> float`
  - Correctly parses `01:15:30` -> `4530.0`
  - Correctly parses `15:30` -> `930.0`
  - Correctly parses `(4500s)` -> `4500.0`
  - Correctly parses `4500.5s` -> `4500.5`
  - Returns `float` seconds.

- [ ] **Step 1: Write failing unit test for `parse_time_ref`**

Create `tests/test_timestamp_parser.py`:

```python
import pytest
from scripts.create_viral_segments import parse_time_ref, process_segments

@pytest.mark.parametrize("time_str,expected", [
    ("(120s)", 120.0),
    ("120s", 120.0),
    ("120", 120.0),
    ("120.5s", 120.5),
    ("(4500s)", 4500.0),
    ("01:15:30", 4530.0),       # 1h 15m 30s
    ("1:15:30", 4530.0),
    ("01:15:30.500", 4530.5),
    ("15:30", 930.0),           # 15m 30s
    ("05:20", 320.0),
    ("00:45", 45.0),
    (3600, 3600.0),
    (1800.5, 1800.5),
    ("", 0.0),
    (None, 0.0),
])
def test_parse_time_ref_formats(time_str, expected):
    assert parse_time_ref(time_str) == expected


def test_process_segments_long_video_timestamps():
    """Verify segments at 1h15m don't fall back to 0s and don't get dropped."""
    transcript_segments = [
        {"start": 0.0, "end": 10.0, "text": "intro at the very start"},
        # 1 hour 15 minutes = 4500s
        {"start": 4500.0, "end": 4515.0, "text": "segmen penting di menit tujuh puluh lima"},
        {"start": 4515.0, "end": 4570.0, "text": "penjelasan mendalam tentang topik"},
        # 1 hour 25 minutes = 5100s
        {"start": 5100.0, "end": 5115.0, "text": "segmen kedua di menit delapan puluh lima"},
        {"start": 5115.0, "end": 5165.0, "text": "penutup topik kedua"},
    ]

    raw_segments = [
        {
            "title": "Segment 1h 15m",
            "start_time_ref": "01:15:00",
            "start_text": "segmen penting di menit",
            "end_text": "penjelasan mendalam",
            "score": 95,
        },
        {
            "title": "Segment 1h 25m",
            "start_time_ref": "01:25:00",
            "start_text": "segmen kedua di menit",
            "end_text": "penutup topik kedua",
            "score": 90,
        },
    ]

    result = process_segments(raw_segments, transcript_segments, min_duration=15, max_duration=90)
    segs = result.get("segments", [])
    assert len(segs) == 2, f"Expected 2 segments, got {len(segs)} (one was falsely dropped as overlap!)"
    assert segs[0]["start_time"] >= 4490.0
    assert segs[1]["start_time"] >= 5090.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=. pytest tests/test_timestamp_parser.py -v`
Expected: FAIL (`ImportError: cannot import name 'parse_time_ref'`).

- [ ] **Step 3: Implement `parse_time_ref` and integrate into `process_segments`**

In `scripts/create_viral_segments.py`:
```python
def parse_time_ref(ref_time_str: Any) -> float:
    """
    Robustly parses time tags into float seconds.
    Supports:
      - '01:15:30' / '1:15:30.500' -> 4530.5s
      - '15:30' / '05:20' -> 930.0s / 320.0s
      - '(120s)' / '120s' / '120.5' -> 120.5s
      - numeric int / float
    """
    if ref_time_str is None:
        return 0.0
    if isinstance(ref_time_str, (int, float)):
        return max(0.0, float(ref_time_str))

    cleaned = str(ref_time_str).strip("()s \t\r\n")
    if not cleaned:
        return 0.0

    # 1. Check for HH:MM:SS or MM:SS
    if ":" in cleaned:
        parts = cleaned.split(":")
        try:
            if len(parts) == 3:
                h = float(parts[0])
                m = float(parts[1])
                s = float(parts[2])
                return max(0.0, round(h * 3600.0 + m * 60.0 + s, 3))
            elif len(parts) == 2:
                m = float(parts[0])
                s = float(parts[1])
                return max(0.0, round(m * 60.0 + s, 3))
        except (ValueError, TypeError):
            pass

    # 2. Check for numeric seconds with optional decimal
    match = re.search(r"(\d+(?:\.\d+)?)", cleaned)
    if match:
        try:
            return max(0.0, float(match.group(1)))
        except (ValueError, TypeError):
            pass

    return 0.0
```

In `process_segments()`:
Replace:
```python
            # 1. Parse Reference Time
            ref_time_str = seg.get('start_time_ref', '(0s)')
            ref_time_val = parse_time_ref(ref_time_str)
```
And broaden the search window around `start_idx`:
```python
            search_start = max(0, start_idx - 30)
            search_limit = min(len(transcript_segments), start_idx + 150)
            for i in range(search_start, search_limit):
```
And add global search fallback if start text was not matched in local window:
```python
            if final_start_time == -1 and start_text_target:
                for i, t_seg in enumerate(transcript_segments):
                    s_text = re.sub(r'[^\w\s]', '', t_seg.get('text', '').lower())
                    if start_text_target in s_text or s_text in start_text_target:
                        final_start_time = t_seg['start']
                        match_start_idx = i
                        break
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=. pytest tests/test_timestamp_parser.py -v`
Expected: ALL PASS.

- [ ] **Step 5: Commit Task 2**

```bash
git add scripts/create_viral_segments.py tests/test_timestamp_parser.py
git commit -m "fix(alignment): implement robust multi-format timestamp parser and global text fallback"
```

---

### Task 3: Full System Verification & Regression Run

**Files:**
- Test: `tests/`
- Test: `webui/frontend/src/test/`

- [ ] **Step 1: Run complete backend pytest suite**

Run: `PYTHONPATH=. pytest tests/ -v`
Expected: 225+ tests pass with zero failures.

- [ ] **Step 2: Run complete frontend vitest suite and build**

Run: `cd webui/frontend && npm test && npm run build`
Expected: 59 passed, build production clean.

- [ ] **Step 3: Commit and push to remote**

```bash
git push origin1 feat/html-motion-broll
```
Ensure working tree is clean.
