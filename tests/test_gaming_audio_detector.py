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
