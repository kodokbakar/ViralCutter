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


def test_cut_json_transcript_boundary_crossing_segments(tmp_path):
    """
    Edge case: When segments or words cross slice boundaries (start before slice or end after slice),
    they must be clamped to slice boundaries, out-of-slice words must be dropped, and text updated.
    """
    input_json = tmp_path / "input.json"
    output_json = tmp_path / "output.json"

    transcript_data = {
        "segments": [
            {
                "start": 8.0,
                "end": 15.0,
                "text": "dropped_pre clamped_start inside_first",
                "words": [
                    {"word": "dropped_pre", "start": 8.0, "end": 9.5},
                    {"word": "clamped_start", "start": 9.5, "end": 11.5},
                    {"word": "inside_first", "start": 12.0, "end": 14.0},
                ],
            },
            {
                "start": 18.0,
                "end": 24.0,
                "text": "inside_second clamped_end dropped_post",
                "words": [
                    {"word": "inside_second", "start": 18.0, "end": 19.5},
                    {"word": "clamped_end", "start": 19.5, "end": 21.0},
                    {"word": "dropped_post", "start": 21.5, "end": 23.5},
                ],
            },
            {
                "start": 22.0,
                "end": 28.0,
                "text": "completely_in_gap",
                "words": [
                    {"word": "completely_in_gap", "start": 23.0, "end": 27.0},
                ],
            },
            {
                "start": 29.0,
                "end": 42.0,
                "text": "dropped_before inside_third dropped_after",
                "words": [
                    {"word": "dropped_before", "start": 29.0, "end": 29.8},
                    {"word": "inside_third", "start": 31.0, "end": 39.0},
                    {"word": "dropped_after", "start": 40.5, "end": 41.5},
                ],
            },
        ]
    }
    input_json.write_text(json.dumps(transcript_data), encoding="utf-8")

    # Slice 1: [10.0, 20.0] (dur 10s), Slice 2: [30.0, 40.0] (dur 10s)
    slices = [(10.0, 20.0), (30.0, 40.0)]

    cut_json_transcript(
        str(input_json),
        str(output_json),
        start_time=10.0,
        end_time=40.0,
        segments_to_splice=slices,
    )

    result = json.loads(output_json.read_text(encoding="utf-8"))
    segments = result["segments"]

    # Segment 3 (gap) must be completely omitted
    texts = [s["text"] for s in segments]
    assert "completely_in_gap" not in texts

    # Check words across all segments
    all_words = {w["word"]: w for s in segments for w in s.get("words", [])}

    # Dropped words must be absent
    assert "dropped_pre" not in all_words
    assert "dropped_post" not in all_words
    assert "dropped_before" not in all_words
    assert "dropped_after" not in all_words

    # Words crossing boundary must be clamped
    assert all_words["clamped_start"]["start"] == pytest.approx(0.0, abs=0.01)
    assert all_words["clamped_start"]["end"] == pytest.approx(1.5, abs=0.01)

    assert all_words["clamped_end"]["start"] == pytest.approx(9.5, abs=0.01)
    assert all_words["clamped_end"]["end"] == pytest.approx(10.0, abs=0.01)

    assert all_words["inside_third"]["start"] == pytest.approx(11.0, abs=0.01)
    assert all_words["inside_third"]["end"] == pytest.approx(19.0, abs=0.01)

    # Segment timestamps check
    assert segments[0]["start"] == pytest.approx(0.0, abs=0.01)
    assert segments[0]["end"] == pytest.approx(5.0, abs=0.01)
    assert segments[0]["text"] == "clamped_start inside_first"

    assert segments[1]["start"] == pytest.approx(8.0, abs=0.01)
    assert segments[1]["end"] == pytest.approx(10.0, abs=0.01)
    assert segments[1]["text"] == "inside_second clamped_end"

    assert segments[2]["start"] == pytest.approx(10.0, abs=0.01)
    assert segments[2]["end"] == pytest.approx(20.0, abs=0.01)
    assert segments[2]["text"] == "inside_third"


def test_cut_json_transcript_without_word_level_timestamps(tmp_path):
    """
    Edge case: When segments have no word-level timestamps ('words' key missing),
    splicing must adjust segment start/end onto the spliced timeline and omit gap segments.
    """
    input_json = tmp_path / "input.json"
    output_json = tmp_path / "output.json"

    transcript_data = {
        "segments": [
            {"start": 8.0, "end": 14.0, "text": "Segment 1 across slice 1 start"},
            {"start": 15.0, "end": 18.0, "text": "Segment 2 fully inside slice 1"},
            {"start": 21.0, "end": 29.0, "text": "Segment 3 fully inside gap"},
            {"start": 32.0, "end": 38.0, "text": "Segment 4 fully inside slice 2"},
            {"start": 39.0, "end": 45.0, "text": "Segment 5 across slice 2 end"},
        ]
    }
    input_json.write_text(json.dumps(transcript_data), encoding="utf-8")

    # Slices: [10.0, 20.0] (dur 10s) and [30.0, 40.0] (dur 10s)
    slices = [(10.0, 20.0), (30.0, 40.0)]

    cut_json_transcript(
        str(input_json),
        str(output_json),
        start_time=10.0,
        end_time=40.0,
        segments_to_splice=slices,
    )

    result = json.loads(output_json.read_text(encoding="utf-8"))
    segments = result["segments"]

    assert len(segments) == 4
    assert segments[0]["text"] == "Segment 1 across slice 1 start"
    assert segments[0]["start"] == pytest.approx(0.0, abs=0.01)
    assert segments[0]["end"] == pytest.approx(4.0, abs=0.01)
    assert "words" not in segments[0]

    assert segments[1]["text"] == "Segment 2 fully inside slice 1"
    assert segments[1]["start"] == pytest.approx(5.0, abs=0.01)
    assert segments[1]["end"] == pytest.approx(8.0, abs=0.01)

    assert segments[2]["text"] == "Segment 4 fully inside slice 2"
    assert segments[2]["start"] == pytest.approx(12.0, abs=0.01)
    assert segments[2]["end"] == pytest.approx(18.0, abs=0.01)

    assert segments[3]["text"] == "Segment 5 across slice 2 end"
    assert segments[3]["start"] == pytest.approx(19.0, abs=0.01)
    assert segments[3]["end"] == pytest.approx(20.0, abs=0.01)


def test_cut_json_transcript_standard_non_spliced_regression(tmp_path):
    """
    Regression test: Standard non-spliced cutting (segments_to_splice=None) must preserve
    linear cutting behavior, correct offset adjustment, and metadata headers.
    """
    input_json = tmp_path / "input.json"
    output_json = tmp_path / "output.json"

    transcript_data = {
        "segments": [
            {
                "start": 5.0,
                "end": 15.0,
                "text": "before inside_one",
                "words": [
                    {"word": "before", "start": 5.0, "end": 9.0},
                    {"word": "inside_one", "start": 11.0, "end": 14.0},
                ],
            },
            {
                "start": 16.0,
                "end": 25.0,
                "text": "inside_two after",
                "words": [
                    {"word": "inside_two", "start": 17.0, "end": 19.0},
                    {"word": "after", "start": 21.0, "end": 24.0},
                ],
            },
        ]
    }
    input_json.write_text(json.dumps(transcript_data), encoding="utf-8")

    cut_json_transcript(
        str(input_json),
        str(output_json),
        start_time=10.0,
        end_time=20.0,
        hook_title="MY HOOK",
        title="My Clip Title",
        segments_to_splice=None,
    )

    result = json.loads(output_json.read_text(encoding="utf-8"))
    assert result.get("hook_title") == "MY HOOK"
    assert result.get("title") == "My Clip Title"

    words = [w["word"] for s in result["segments"] for w in s.get("words", [])]
    assert "before" not in words
    assert "after" not in words
    assert "inside_one" in words
    assert "inside_two" in words

    all_words = {w["word"]: w for s in result["segments"] for w in s.get("words", [])}
    assert all_words["inside_one"]["start"] == pytest.approx(1.0, abs=0.01)
    assert all_words["inside_two"]["start"] == pytest.approx(7.0, abs=0.01)


def test_cut_segments_standard_non_spliced_path(tmp_path):
    """
    Regression check: cut_segments.cut with non-spliced segment runs standard ffmpeg cut
    and produces correctly offset json subtitles.
    """
    project_folder = str(tmp_path)
    (tmp_path / "input.mp4").write_bytes(b"fake video")

    transcript_data = {
        "segments": [
            {
                "start": 5.0,
                "end": 15.0,
                "text": "hello world",
                "words": [
                    {"word": "hello", "start": 6.0, "end": 8.0},
                    {"word": "world", "start": 9.0, "end": 11.0},
                ],
            }
        ]
    }
    (tmp_path / "input.json").write_text(json.dumps(transcript_data), encoding="utf-8")

    segments_data = {
        "segments": [
            {
                "title": "Standard Clip",
                "score": 88,
                "start_time": 5.0,
                "duration": 10.0,
            }
        ]
    }

    with patch("scripts.cut_segments.check_nvenc_support", return_value=False), \
         patch("subprocess.run") as mock_run, \
         patch("scripts.smart_clipping.splice_topic_segments") as mock_splice:
        cut_segments.cut(segments_data, project_folder=project_folder, skip_video=False)

    assert mock_splice.call_count == 0
    assert mock_run.call_count >= 1
    ffmpeg_cmd = mock_run.call_args[0][0]
    assert ffmpeg_cmd[0] == "ffmpeg"
    assert "-ss" in ffmpeg_cmd
    assert "-c:v" in ffmpeg_cmd
    assert ffmpeg_cmd[ffmpeg_cmd.index("-c:v") + 1] == "libx264"

    subs_file = tmp_path / "subs" / "001_88_Standard_Clip_processed.json"
    assert subs_file.exists()
    result = json.loads(subs_file.read_text(encoding="utf-8"))
    assert len(result["segments"]) > 0
