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
