import pytest
from scripts.smart_clipping import remove_dead_air_from_segment

WORDS_WITH_PAUSE = [
    {"word": "Halo", "start": 1.0, "end": 1.5, "score": 0.95},
    {"word": "teman", "start": 1.6, "end": 2.0, "score": 0.92},
    # 1.5s silence gap between 2.0 and 3.5
    {"word": "hari", "start": 3.5, "end": 3.8, "score": 0.94},
    {"word": "ini", "start": 3.9, "end": 4.2, "score": 0.96},
]

def test_remove_dead_air_splits_on_long_silence():
    # Segment from 0.9 to 4.3 with a 1.5s pause between word 2 and word 3
    slices = remove_dead_air_from_segment(
        start_time=0.9,
        end_time=4.3,
        words=WORDS_WITH_PAUSE,
        silence_threshold=0.6,
        pad=0.08
    )
    # Should produce 2 active slices:
    # Slice 1: approx 0.9 to 2.08
    # Slice 2: approx 3.45 to 4.3
    assert len(slices) == 2
    s1, e1 = slices[0]
    s2, e2 = slices[1]
    assert s1 == pytest.approx(0.9, abs=0.05)
    assert e1 == pytest.approx(2.08, abs=0.05)
    assert s2 == pytest.approx(3.45, abs=0.05)
    assert e2 == pytest.approx(4.3, abs=0.05)
    # The gap between e1 and s2 (silence) was removed:
    assert s2 > e1

def test_remove_dead_air_keeps_normal_speech_continuous():
    normal_words = [
        {"word": "Halo", "start": 1.0, "end": 1.4, "score": 0.95},
        {"word": "semuanya", "start": 1.5, "end": 1.9, "score": 0.92},
        {"word": "selamat", "start": 2.0, "end": 2.4, "score": 0.90},
    ]
    slices = remove_dead_air_from_segment(
        start_time=0.9,
        end_time=2.5,
        words=normal_words,
        silence_threshold=0.6
    )
    assert len(slices) == 1
    assert slices[0][0] == pytest.approx(0.9, abs=0.05)
    assert slices[0][1] == pytest.approx(2.5, abs=0.05)

def test_remove_dead_air_empty_words_fallback():
    slices = remove_dead_air_from_segment(
        start_time=10.0,
        end_time=25.0,
        words=[],
        silence_threshold=0.6
    )
    assert len(slices) == 1
    assert slices[0] == (10.0, 25.0)
