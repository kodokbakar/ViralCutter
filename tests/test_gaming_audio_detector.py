import array
import subprocess
from unittest.mock import patch, MagicMock
import pytest
from scripts.gaming_audio_detector import (
    compute_audio_zscores,
    detect_audio_events,
    extract_audio_rms_curve,
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


def test_detect_audio_events_min_contrast_jump_filter():
    samples = [10.0] * 100 + [80.0] * 10 + [10.0] * 90
    # jump_ratio is 8.0; setting min_contrast_jump=10.0 should filter it out
    events = detect_audio_events(samples, sample_rate_hz=10.0, z_threshold=1.8, min_contrast_jump=10.0)
    assert events == []


def test_detect_audio_events_gradual_buildup_allowed():
    # Baseline 10.0, gradual rise from 10 to 70 over 30 samples (3s), peak at 80
    # Because of gradual buildup, jump_ratio from preceding 3s is ~1.2 (less than 1.5)
    ramp = [10.0 + i * 2.0 for i in range(30)]
    samples = [10.0] * 100 + ramp + [80.0] * 10 + [10.0] * 60
    # Default min_contrast_jump=None should keep the peak
    events = detect_audio_events(samples, sample_rate_hz=10.0, z_threshold=1.8)
    assert len(events) >= 1
    assert events[0]["z_score"] >= 1.8

    # If strictly specified min_contrast_jump=3.0, it is filtered out
    filtered = detect_audio_events(samples, sample_rate_hz=10.0, z_threshold=1.8, min_contrast_jump=3.0)
    assert filtered == []

def test_detect_audio_events_low_sample_rate_no_hang():
    samples = [10.0] * 20 + [50.0] * 5 + [10.0] * 20
    events = detect_audio_events(samples, sample_rate_hz=0.0, z_threshold=1.5)
    assert isinstance(events, list)


def test_extract_audio_rms_curve_nonexistent():
    rms, mean, std = extract_audio_rms_curve("/nonexistent/file/video.mp4")
    assert rms == []
    assert mean == 0.0
    assert std == 0.0


def test_extract_audio_rms_curve_mocked(tmp_path):
    dummy = tmp_path / "stream.mp4"
    dummy.write_text("fake video")

    # 1600 samples at 1000, 1600 samples at 3000 (0.1s chunks at 16kHz)
    raw_samples = array.array("h", [1000] * 1600 + [3000] * 1600).tobytes()
    mock_proc = MagicMock()
    mock_proc.stdout = raw_samples

    with patch("subprocess.run", return_value=mock_proc):
        rms, mean, std = extract_audio_rms_curve(str(dummy), chunk_sec=0.1)
        assert len(rms) == 2
        assert rms[0] == pytest.approx(1000.0, abs=1.0)
        assert rms[1] == pytest.approx(3000.0, abs=1.0)
        assert mean == pytest.approx(2000.0, abs=1.0)
        assert std == pytest.approx(1000.0, abs=1.0)


def test_extract_audio_rms_curve_timeout(tmp_path):
    dummy = tmp_path / "stream.mp4"
    dummy.write_text("fake video")

    with patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="ffmpeg", timeout=120)):
        rms, mean, std = extract_audio_rms_curve(str(dummy), chunk_sec=0.1)
        assert rms == []
        assert mean == 0.0
        assert std == 0.0
