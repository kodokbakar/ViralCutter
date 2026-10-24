import json
import os
from unittest.mock import patch
import pytest

from scripts.cut_json import cut_json_transcript
from scripts import cut_segments


def test_cut_json_transcript_with_segments_to_splice(tmp_path):
    """
    Regression test: When cutting a transcript for spliced clips, words in dropped gaps
    must be excluded, and words in subsequent slices must be remapped to the accumulated
    spliced timeline rather than cut linearly.
    """
    input_json = tmp_path / "input.json"
    output_json = tmp_path / "output.json"

    transcript_data = {
        "segments": [
            {
                "start": 10.0,
                "end": 40.0,
                "text": "word_one word_gap word_two",
                "words": [
                    {"word": "word_one", "start": 12.0, "end": 13.0},
                    {"word": "word_gap", "start": 25.0, "end": 26.0},
                    {"word": "word_two", "start": 32.0, "end": 33.0},
                ],
            }
        ]
    }
    input_json.write_text(json.dumps(transcript_data), encoding="utf-8")

    # Spliced slices: [10.0, 20.0] (duration 10s) and [30.0, 40.0] (duration 10s)
    # Total duration = 20s. Gap [20.0, 30.0] is dropped.
    slices = [(10.0, 20.0), (30.0, 40.0)]

    cut_json_transcript(
        str(input_json),
        str(output_json),
        start_time=10.0,
        end_time=40.0,
        segments_to_splice=slices,
    )

    assert output_json.exists()
    result = json.loads(output_json.read_text(encoding="utf-8"))

    # Flatten all words from all output segments
    all_words = []
    for seg in result.get("segments", []):
        all_words.extend(seg.get("words", []))

    word_map = {w["word"]: w for w in all_words}

    # 1. Word in dropped gap (25.0s) MUST be removed
    assert "word_gap" not in word_map, "Words in dropped gaps must be excluded from spliced subtitle JSON"

    # 2. Word in first slice (12.0s) must be mapped to 2.0s (12.0 - 10.0)
    assert "word_one" in word_map
    assert word_map["word_one"]["start"] == pytest.approx(2.0, abs=0.01)
    assert word_map["word_one"]["end"] == pytest.approx(3.0, abs=0.01)

    # 3. Word in second slice (32.0s) must be mapped to 12.0s (10.0 accumulated + (32.0 - 30.0))
    # In linear cutting, this would either be 22.0s or dropped
    assert "word_two" in word_map, "Word in second slice must not be dropped"
    assert word_map["word_two"]["start"] == pytest.approx(12.0, abs=0.01)
    assert word_map["word_two"]["end"] == pytest.approx(13.0, abs=0.01)


def test_cut_segments_spliced_subtitle_sync(tmp_path):
    """
    Regression test: cut_segments.cut() must forward segments_to_splice to cut_json_transcript
    so the resulting processed subtitle file aligns with the spliced video.
    """
    project_folder = str(tmp_path)
    (tmp_path / "input.mp4").write_bytes(b"fake video")

    transcript_data = {
        "segments": [
            {
                "start": 10.0,
                "end": 40.0,
                "text": "first gap second",
                "words": [
                    {"word": "first", "start": 12.0, "end": 13.0},
                    {"word": "gap", "start": 25.0, "end": 26.0},
                    {"word": "second", "start": 32.0, "end": 33.0},
                ],
            }
        ]
    }
    (tmp_path / "input.json").write_text(json.dumps(transcript_data), encoding="utf-8")

    segments_data = {
        "segments": [
            {
                "title": "Spliced Clip",
                "score": 95,
                "start_time": 10.0,
                "duration": 20.0,
                "segments_to_splice": [(10.0, 20.0), (30.0, 40.0)],
            }
        ]
    }

    with patch("scripts.cut_segments.check_nvenc_support", return_value=False), \
         patch("scripts.smart_clipping.splice_topic_segments"):
        cut_segments.cut(segments_data, project_folder=project_folder, skip_video=False)

    subs_file = tmp_path / "subs" / "001_95_Spliced_Clip_processed.json"
    assert subs_file.exists()
    result = json.loads(subs_file.read_text(encoding="utf-8"))

    all_words = []
    for seg in result.get("segments", []):
        all_words.extend(seg.get("words", []))

    word_map = {w["word"]: w for w in all_words}

    # Gap word must NOT be present
    assert "gap" not in word_map, "Gap word should be dropped in spliced subtitle JSON"
    # Second slice word must be mapped to 12.0s
    assert "second" in word_map, "Second slice word must be present in spliced subtitle JSON"
    assert word_map["second"]["start"] == pytest.approx(12.0, abs=0.01)
