import os
import json
import time
from unittest.mock import patch, MagicMock, Mock
import pytest

from scripts.create_viral_segments import (
    preprocess_transcript_for_ai,
    call_gemini,
    call_custom_api,
    verify_ai_connection,
    get_http_session,
    get_gemini_client,
    _reset_gemini_clients,
    process_segments,
    create,
)
from scripts.smart_clipping import (
    build_narrative_prompt,
    query_ai_backend,
    run_smart_clipping_pipeline,
)


# =====================================================================
# Strategy 6: Client & Session Connection Pooling
# =====================================================================

def test_http_session_pooling_singleton():
    _reset_gemini_clients()
    session1 = get_http_session()
    session2 = get_http_session()
    assert session1 is session2
    assert "http://" in session1.adapters
    assert "https://" in session1.adapters
    _reset_gemini_clients()


def test_gemini_client_pooling_and_mock_bypass():
    _reset_gemini_clients()
    with patch("scripts.create_viral_segments.HAS_GEMINI", True), \
         patch("scripts.create_viral_segments.genai") as mock_genai:
        # Real-like client class (not a Mock subclass)
        class DummyClient:
            def __init__(self, **kwargs):
                self.kwargs = kwargs

        mock_genai.Client = DummyClient
        c1 = get_gemini_client("key-a", timeout=10.0)
        c2 = get_gemini_client("key-a", timeout=10.0)
        c3 = get_gemini_client("key-b", timeout=10.0)
        assert c1 is c2
        assert c1 is not c3
        _reset_gemini_clients()

        # When genai.Client is a Mock instance, bypass cache
        mock_client_cls = MagicMock()
        mock_genai.Client = mock_client_cls
        m1 = get_gemini_client("key-mock")
        m2 = get_gemini_client("key-mock")
        assert mock_client_cls.call_count == 2
        _reset_gemini_clients()


# =====================================================================
# Strategy 4: Timestamp Tag Thinning & Alignment Resolution
# =====================================================================

def test_preprocess_transcript_tag_thinning():
    # 10 segments, 3 seconds each -> 30 seconds total
    transcript = [{"start": i * 3.0, "end": (i + 1) * 3.0, "text": f"word{i}"} for i in range(10)]
    
    # Default 12.0s interval
    thinned = preprocess_transcript_for_ai(transcript)
    tags = [part for part in thinned.split() if part.startswith("(") and part.endswith(")")]
    # Starts at (0s), next at end >= 12s -> (12s), next at end >= 24s -> (24s)
    assert len(tags) <= 4

    # Explicit 4.0s interval (legacy baseline)
    dense = preprocess_transcript_for_ai(transcript, tag_interval=4.0)
    dense_tags = [part for part in dense.split() if part.startswith("(") and part.endswith(")")]
    assert len(dense_tags) > len(tags)


def test_process_segments_widened_lookup_accuracy():
    # Transcript segments spanning 60 seconds with thinned tags (e.g. at 0s, 15s, 30s)
    transcript_segments = [
        {"start": float(i), "end": float(i + 1), "text": f"token_{i:03d}"}
        for i in range(60)
    ]
    raw_segments = [
        {
            "start_time_ref": "(12s)",
            "start_text": "token_020",  # 8s away from ref tag 12s
            "end_text": "token_045",
            "title": "Uji Akurasi Waktu",
            "score": 90,
        }
    ]
    processed = process_segments(raw_segments, transcript_segments, min_duration=10, max_duration=60)
    assert "segments" in processed
    assert len(processed["segments"]) >= 1
    seg = processed["segments"][0]
    assert seg["start_time"] == 20.0
    assert seg["end_time"] == 46.0


# =====================================================================
# Strategy 2: Output JSON Schema Pruning & Local Rubric Hydration
# =====================================================================

def test_schema_pruning_in_prompts():
    prompt = build_narrative_prompt("sample transcript", target_min=15, target_max=60, num_topics=2)
    # The prompt should not contain the verbose rubric schema keys in the example output
    assert '"hook_strength"' not in prompt
    assert '"retention_flow"' not in prompt
    assert '"shareability"' not in prompt
    # But it must retain core fields
    assert '"score"' in prompt
    assert '"title"' in prompt
    assert '"segments"' in prompt


def test_process_segments_hydrates_omitted_rubric():
    transcript_segments = [
        {"start": float(i), "end": float(i + 1), "text": f"kata {i}"}
        for i in range(30)
    ]
    raw_segments = [
        {
            "start_time_ref": "(0s)",
            "start_text": "kata 2",
            "end_text": "kata 15",
            "title": "Judul Viral",
            "score": 92,
            # Notice: NO "rubric" provided in LLM response!
        }
    ]
    processed = process_segments(raw_segments, transcript_segments, min_duration=5, max_duration=30)
    assert "segments" in processed
    assert len(processed["segments"]) == 1
    seg = processed["segments"][0]
    assert "rubric" in seg
    rubric = seg["rubric"]
    assert "hook_strength" in rubric
    assert "retention_flow" in rubric
    assert "verdict" in rubric


# =====================================================================
# Strategy 3: Exponential Jitter Backoff & Retry-After Handling
# =====================================================================

def test_call_gemini_exponential_jitter_and_retry_after():
    sleep_calls = []

    class MockErrorWithHeaders(Exception):
        def __init__(self, msg, retry_after=None):
            super().__init__(msg)
            self.status_code = 429
            if retry_after is not None:
                self.headers = {"Retry-After": str(retry_after)}

    with patch("scripts.create_viral_segments.HAS_GEMINI", True), \
         patch("scripts.create_viral_segments.genai") as mock_genai, \
         patch("scripts.create_viral_segments.time.sleep", side_effect=lambda s: sleep_calls.append(s)):

        mock_client = MagicMock()
        mock_genai.Client.return_value = mock_client
        mock_client.__enter__.return_value = mock_client

        # Fail with retry-after=3.5 on attempt 1, succeed on attempt 2
        mock_resp = MagicMock()
        mock_resp.text = '{"segments": []}'
        mock_client.models.generate_content.side_effect = [
            MockErrorWithHeaders("Resource exhausted 429", retry_after=3.5),
            mock_resp,
        ]

        res = call_gemini("prompt", api_key="dummy_key", max_retries=2)
        assert res == '{"segments": []}'
        assert len(sleep_calls) == 1
        # Should respect Retry-After (3.5 + jitter)
        assert 3.5 <= sleep_calls[0] <= 4.2


def test_call_custom_api_retries_and_exponential_backoff():
    sleep_calls = []
    mock_resp_503 = MagicMock()
    mock_resp_503.status_code = 503
    mock_resp_503.text = "Service Unavailable"
    mock_resp_503.headers = {"Retry-After": "2.0"}

    mock_resp_200 = MagicMock()
    mock_resp_200.status_code = 200
    mock_resp_200.json.return_value = {
        "choices": [{"message": {"content": "custom result"}}]
    }

    with patch("requests.post", side_effect=[mock_resp_503, mock_resp_200]) as mock_post, \
         patch("scripts.create_viral_segments.time.sleep", side_effect=lambda s: sleep_calls.append(s)):

        res = call_custom_api(
            prompt="hi",
            base_url="http://localhost:11434/v1",
            max_retries=3,
        )
        assert res == "custom result"
        assert len(sleep_calls) == 1
        assert 2.0 <= sleep_calls[0] <= 3.0
        assert mock_post.call_count == 2


# =====================================================================
# Strategy 5: Native Structured JSON Mode & 400 Fallback
# =====================================================================

def test_call_custom_api_structured_json_mode_and_400_fallback():
    mock_resp_400 = MagicMock()
    mock_resp_400.status_code = 400
    mock_resp_400.text = "Invalid request: unrecognized field 'response_format'"

    mock_resp_200 = MagicMock()
    mock_resp_200.status_code = 200
    mock_resp_200.json.return_value = {
        "choices": [{"message": {"content": '{"ok": true}'}}]
    }

    with patch("requests.post", side_effect=[mock_resp_400, mock_resp_200]) as mock_post:
        res = call_custom_api(
            prompt="give json",
            base_url="http://localhost:11434/v1",
            response_mime_type="application/json",
            max_retries=1,
        )
        assert res == '{"ok": true}'
        assert mock_post.call_count == 2
        first_payload = mock_post.call_args_list[0][1]["json"]
        assert first_payload.get("response_format") == {"type": "json_object"}
        second_payload = mock_post.call_args_list[1][1]["json"]
        assert "response_format" not in second_payload


# =====================================================================
# Strategy 1: Concurrent Chunk Execution & Determinism
# =====================================================================

def test_create_viral_segments_concurrent_chunks_preserves_order(tmp_path):
    proj_dir = str(tmp_path)
    tsv_path = os.path.join(proj_dir, "input.tsv")
    with open(tsv_path, "w", encoding="utf-8") as f:
        # Create enough content so chunking with chunk_size_arg splits into 2+ chunks
        for i in range(20):
            f.write(f"{i * 3000}\t{(i + 1) * 3000}\tkalimat panjang sekali bagian nomor {i}\n")

    call_prompts = []

    def mock_call_custom_api(prompt, **kwargs):
        call_prompts.append(prompt)
        # Variable sleep to test that results are sorted by chunk index
        if "Part 1" in prompt:
            time.sleep(0.04)
            return json.dumps({
                "segments": [{
                    "start_time_ref": "(0s)",
                    "start_text": "kalimat panjang sekali bagian nomor 0",
                    "end_text": "kalimat panjang sekali bagian nomor 3",
                    "title": "Segment Chunk 1",
                    "score": 85,
                }]
            })
        else:
            return json.dumps({
                "segments": [{
                    "start_time_ref": "(30s)",
                    "start_text": "kalimat panjang sekali bagian nomor 10",
                    "end_text": "kalimat panjang sekali bagian nomor 14",
                    "title": "Segment Chunk 2",
                    "score": 95,
                }]
            })

    with patch("scripts.create_viral_segments.call_custom_api", side_effect=mock_call_custom_api):
        result = create(
            num_segments=2,
            viral_mode=True,
            themes="",
            tempo_minimo=3,
            tempo_maximo=30,
            ai_mode="custom",
            project_folder=proj_dir,
            chunk_size_arg=100,  # Forces multiple chunks
            base_url_arg="http://localhost:11434/v1",
        )

        segments = result.get("segments", [])
        assert len(segments) >= 1
        assert len(call_prompts) > 1
        # Segments sorted by score descending in process_segments
        assert segments[0]["title"] == "Segment Chunk 2"


def test_smart_clipping_concurrent_chunks_preserves_order(tmp_path):
    proj_dir = str(tmp_path)
    input_json = os.path.join(proj_dir, "input.json")
    with open(input_json, "w", encoding="utf-8") as f:
        json.dump({
            "segments": [
                {"start": 0.0, "end": 5.0, "text": "intro", "words": [{"word": "intro", "start": 0.0, "end": 5.0}]},
                {"start": 5.0, "end": 20.0, "text": "body", "words": [{"word": "body", "start": 5.0, "end": 20.0}]},
                {"start": 20.0, "end": 35.0, "text": "conclusion", "words": [{"word": "conclusion", "start": 20.0, "end": 35.0}]},
            ]
        }, f)

    chunks = ["chunk_one_text", "chunk_two_text"]

    def mock_query(prompt, **kwargs):
        if "chunk_one_text" in prompt:
            time.sleep(0.04)
            return json.dumps({
                "topics": [{
                    "title": "Topic from Chunk 1",
                    "score": 90,
                    "target_duration": 20.0,
                    "segments": {
                        "hook": {"start_time": 0.0, "end_time": 2.0, "text": "intro"},
                        "core": {"start_time": 5.0, "end_time": 10.0, "text": "body"},
                        "payoff": {"start_time": 20.0, "end_time": 25.0, "text": "conclusion"},
                    }
                }]
            })
        else:
            return json.dumps({
                "topics": [{
                    "title": "Topic from Chunk 2",
                    "score": 80,
                    "target_duration": 20.0,
                    "segments": {
                        "hook": {"start_time": 1.0, "end_time": 3.0, "text": "intro"},
                        "core": {"start_time": 6.0, "end_time": 12.0, "text": "body"},
                        "payoff": {"start_time": 22.0, "end_time": 28.0, "text": "conclusion"},
                    }
                }]
            })

    with patch("scripts.smart_clipping.chunk_transcript_text", return_value=chunks), \
         patch("scripts.smart_clipping.query_ai_backend", side_effect=mock_query), \
         patch("scripts.create_viral_segments.load_transcript", return_value=[]), \
         patch("scripts.create_viral_segments.preprocess_transcript_for_ai", return_value="dummy"):

        res = run_smart_clipping_pipeline(
            project_folder=proj_dir,
            min_duration=10.0,
            max_duration=30.0,
            ai_backend="custom",
            base_url="http://localhost:11434/v1",
            num_segments=2,
            render_clips=False,
        )

        segments = res.get("segments", [])
        assert len(segments) == 2
        titles = [s["title"] for s in segments]
        assert "Topic from Chunk 1" in titles
        assert "Topic from Chunk 2" in titles


# =====================================================================
# Additional Edge-Case Coverage: Fault Tolerance & Sequential Modes
# =====================================================================

def test_concurrent_chunk_partial_failure_resilience(tmp_path):
    """Verifies that if one chunk errors, healthy chunks still succeed."""
    proj_dir = str(tmp_path)
    tsv_path = os.path.join(proj_dir, "input.tsv")
    with open(tsv_path, "w", encoding="utf-8") as f:
        for i in range(20):
            f.write(f"{i * 3000}\t{(i + 1) * 3000}\tbukti chunk resilience kalimat {i}\n")

    def mock_call_with_one_failing_chunk(prompt, **kwargs):
        if "Part 1" in prompt:
            raise RuntimeError("Temporary upstream server error on chunk 1")
        return json.dumps({
            "segments": [{
                "start_time_ref": "(30s)",
                "start_text": "bukti chunk resilience kalimat 10",
                "end_text": "bukti chunk resilience kalimat 14",
                "title": "Healthy Chunk 2",
                "score": 90,
            }]
        })

    with patch("scripts.create_viral_segments.call_custom_api", side_effect=mock_call_with_one_failing_chunk):
        result = create(
            num_segments=2,
            viral_mode=True,
            themes="",
            tempo_minimo=3,
            tempo_maximo=30,
            ai_mode="custom",
            project_folder=proj_dir,
            chunk_size_arg=100,
            base_url_arg="http://localhost:11434/v1",
        )
        segments = result.get("segments", [])
        assert len(segments) >= 1
        assert segments[0]["title"] == "Healthy Chunk 2"


def test_retry_after_malformed_and_case_insensitive_handling():
    """Ensures non-numeric, negative, or lowercase retry-after headers fall back safely to backoff."""
    sleep_calls = []

    mock_resp_429 = MagicMock()
    mock_resp_429.status_code = 429
    mock_resp_429.text = "Too Many Requests"
    mock_resp_429.headers = {"retry-after": "not-a-number"}

    mock_resp_200 = MagicMock()
    mock_resp_200.status_code = 200
    mock_resp_200.json.return_value = {"choices": [{"message": {"content": "recovered"}}]}

    with patch("requests.post", side_effect=[mock_resp_429, mock_resp_200]), \
         patch("scripts.create_viral_segments.time.sleep", side_effect=lambda s: sleep_calls.append(s)):

        res = call_custom_api("hello", base_url="http://localhost:11434/v1", max_retries=2)
        assert res == "recovered"
        assert len(sleep_calls) == 1
        assert 1.0 <= sleep_calls[0] <= 6.0


def test_call_custom_api_non_response_format_400_not_retried():
    """HTTP 400 with unrelated error should immediately raise and not retry."""
    mock_resp_400 = MagicMock()
    mock_resp_400.status_code = 400
    mock_resp_400.text = "Bad Request: Prompt exceeds context length"

    with patch("requests.post", return_value=mock_resp_400) as mock_post:
        with pytest.raises(RuntimeError) as exc_info:
            call_custom_api("too long prompt", base_url="http://localhost:11434/v1", response_mime_type="application/json")
        assert "Bad Request" in str(exc_info.value)
        assert mock_post.call_count == 1


def test_manual_mode_sequential_safety(tmp_path):
    """Ensures manual mode processes chunks sequentially without threading."""
    proj_dir = str(tmp_path)
    tsv_path = os.path.join(proj_dir, "input.tsv")
    with open(tsv_path, "w", encoding="utf-8") as f:
        # Generate enough text (>15000 chars) to produce multiple chunks under manual mode chunk_size=15000
        for i in range(200):
            f.write(f"{i * 1000}\t{(i + 1) * 1000}\tmanual sequential line {i} with lots of long descriptive words to surpass fifteen thousand characters\n")

    thread_names = []

    def mock_input(prompt_msg=""):
        import threading
        thread_names.append(threading.current_thread().name)
        return "{}"

    with patch("builtins.input", side_effect=mock_input):
        result = create(
            num_segments=2,
            viral_mode=True,
            themes="",
            tempo_minimo=3,
            tempo_maximo=30,
            ai_mode="manual",
            project_folder=proj_dir,
        )
        assert len(thread_names) >= 2
        assert all("MainThread" in t for t in thread_names)
