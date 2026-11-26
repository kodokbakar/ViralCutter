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


def test_extract_audio_rms_curve_vocal_bandpass(tmp_path):
    dummy = tmp_path / "stream.mp4"
    dummy.write_text("fake video")
    mock_proc = MagicMock()
    mock_proc.stdout = array.array("h", [500] * 1600).tobytes()

    with patch("subprocess.run", return_value=mock_proc) as mock_run:
        extract_audio_rms_curve(str(dummy), vocal_bandpass=True)
        called_cmd = mock_run.call_args[0][0]
        assert "-af" in called_cmd
        af_idx = called_cmd.index("-af")
        assert called_cmd[af_idx + 1] == "highpass=f=200,lowpass=f=3500"

    with patch("subprocess.run", return_value=mock_proc) as mock_run:
        extract_audio_rms_curve(str(dummy), vocal_bandpass=False)
        called_cmd = mock_run.call_args[0][0]
        assert "-af" not in called_cmd

    with patch("subprocess.run", return_value=mock_proc) as mock_run:
        extract_audio_rms_curve(str(dummy), vocal_bandpass=True, low_cut=300, high_cut=3000)
        called_cmd = mock_run.call_args[0][0]
        af_idx = called_cmd.index("-af")
        assert called_cmd[af_idx + 1] == "highpass=f=300,lowpass=f=3000"


def test_extract_audio_rms_curve_ffmpeg_errors(tmp_path):
    dummy = tmp_path / "stream.mp4"
    dummy.write_text("fake video")

    # Subprocess errors (non-zero exit code, exec failure, permission error, file not found)
    for error in [
        subprocess.CalledProcessError(1, ["ffmpeg"]),
        FileNotFoundError("ffmpeg not found"),
        PermissionError("permission denied"),
        OSError("exec failed"),
    ]:
        with patch("subprocess.run", side_effect=error):
            rms, mean, std = extract_audio_rms_curve(str(dummy), chunk_sec=0.1)
            assert rms == []
            assert mean == 0.0
            assert std == 0.0


def test_extract_audio_rms_curve_nonexistent_path():
    rms, mean, std = extract_audio_rms_curve("/nonexistent/video/file_12345.mp4")
    assert rms == []
    assert mean == 0.0
    assert std == 0.0


def test_extract_audio_rms_curve_odd_byte_length_and_empty(tmp_path):
    dummy = tmp_path / "stream.mp4"
    dummy.write_text("fake video")

    # Odd byte length (3201 bytes instead of 3200): must be trimmed cleanly without array error
    raw_samples = array.array("h", [2000] * 1600).tobytes() + b"\x01"
    assert len(raw_samples) % 2 != 0

    mock_proc = MagicMock()
    mock_proc.stdout = raw_samples
    with patch("subprocess.run", return_value=mock_proc):
        rms, mean, std = extract_audio_rms_curve(str(dummy), chunk_sec=0.1)
        assert len(rms) == 1
        assert rms[0] == pytest.approx(2000.0, abs=1.0)
        assert mean == pytest.approx(2000.0, abs=1.0)
        assert std == 0.0

    # Empty stdout bytes
    mock_proc.stdout = b""
    with patch("subprocess.run", return_value=mock_proc):
        rms, mean, std = extract_audio_rms_curve(str(dummy), chunk_sec=0.1)
        assert rms == []
        assert mean == 0.0
        assert std == 0.0

    # None stdout
    mock_proc.stdout = None
    with patch("subprocess.run", return_value=mock_proc):
        rms, mean, std = extract_audio_rms_curve(str(dummy), chunk_sec=0.1)
        assert rms == []
        assert mean == 0.0
        assert std == 0.0


def test_extract_audio_rms_curve_custom_bandpass_frequencies(tmp_path):
    dummy = tmp_path / "stream.mp4"
    dummy.write_text("fake video")
    mock_proc = MagicMock()
    mock_proc.stdout = array.array("h", [400] * 1600).tobytes()

    # Custom low_cut and high_cut
    with patch("subprocess.run", return_value=mock_proc) as mock_run:
        extract_audio_rms_curve(str(dummy), vocal_bandpass=True, low_cut=100, high_cut=5000)
        called_cmd = mock_run.call_args[0][0]
        assert "-af" in called_cmd
        af_idx = called_cmd.index("-af")
        assert called_cmd[af_idx + 1] == "highpass=f=100,lowpass=f=5000"


def test_extract_audio_rms_curve_vectorized_matches_pure_python_fallback(tmp_path):
    import time
    dummy = tmp_path / "stream.mp4"
    dummy.write_text("fake video")

    # Generate 16000 samples (10 chunks of 1600 samples) with distinct amplitudes
    sample_list = []
    for chunk_idx in range(10):
        amp = (chunk_idx + 1) * 1500
        sample_list.extend([amp] * 1600)
    raw_samples = array.array("h", sample_list).tobytes()

    mock_proc = MagicMock()
    mock_proc.stdout = raw_samples

    with patch("subprocess.run", return_value=mock_proc):
        # 1. Vectorized NumPy execution
        with patch("scripts.gaming_audio_detector._HAS_NUMPY", True):
            rms_np, mean_np, std_np = extract_audio_rms_curve(str(dummy), chunk_sec=0.1)

        # 2. Pure Python fallback execution
        with patch("scripts.gaming_audio_detector._HAS_NUMPY", False):
            rms_py, mean_py, std_py = extract_audio_rms_curve(str(dummy), chunk_sec=0.1)

    assert len(rms_np) == 10
    assert len(rms_py) == 10
    for r_np, r_py in zip(rms_np, rms_py):
        assert r_np == pytest.approx(r_py, rel=1e-3, abs=0.1)
    assert mean_np == pytest.approx(mean_py, rel=1e-3, abs=0.1)
    assert std_np == pytest.approx(std_py, rel=1e-3, abs=0.1)


def test_extract_audio_rms_curve_numpy_error_fallback(tmp_path):
    dummy = tmp_path / "stream.mp4"
    dummy.write_text("fake video")

    raw_samples = array.array("h", [1200] * 1600 + [2400] * 1600).tobytes()
    mock_proc = MagicMock()
    mock_proc.stdout = raw_samples

    with patch("subprocess.run", return_value=mock_proc):
        with patch("numpy.frombuffer", side_effect=ValueError("simulated numpy buffer error")):
            rms, mean, std = extract_audio_rms_curve(str(dummy), chunk_sec=0.1)
            assert len(rms) == 2
            assert rms[0] == pytest.approx(1200.0, abs=1.0)
            assert rms[1] == pytest.approx(2400.0, abs=1.0)
            assert mean == pytest.approx(1800.0, abs=1.0)


def test_compute_audio_zscores_numpy_and_fallback_consistency():
    rms_vals = [10.0, 15.0, 20.0, 45.0, 10.0]
    mean = 20.0
    std = 13.0

    with patch("scripts.gaming_audio_detector._HAS_NUMPY", True):
        z_np = compute_audio_zscores(rms_vals, mean, std)

    with patch("scripts.gaming_audio_detector._HAS_NUMPY", False):
        z_py = compute_audio_zscores(rms_vals, mean, std)

    assert len(z_np) == len(z_py)
    for a, b in zip(z_np, z_py):
        assert a == pytest.approx(b, rel=1e-3, abs=1e-4)

    # Test error fallback in compute_audio_zscores
    with patch("numpy.asarray", side_effect=RuntimeError("simulated error")):
        z_err = compute_audio_zscores(rms_vals, mean, std)
        assert len(z_err) == len(rms_vals)
        for a, b in zip(z_err, z_py):
            assert a == pytest.approx(b, rel=1e-3, abs=1e-4)


def test_extract_audio_rms_curve_large_buffer_performance(tmp_path):
    dummy = tmp_path / "stream.mp4"
    dummy.write_text("fake video")

    # 160,000 samples (10 seconds, 100 chunks of 1600 samples)
    raw_samples = array.array("h", [1500] * 160000).tobytes()
    mock_proc = MagicMock()
    mock_proc.stdout = raw_samples

    with patch("subprocess.run", return_value=mock_proc):
        rms, mean, std = extract_audio_rms_curve(str(dummy), chunk_sec=0.1)

    assert len(rms) == 100
    assert rms[0] == pytest.approx(1500.0, abs=1.0)
    assert mean == pytest.approx(1500.0, abs=1.0)
    assert std == pytest.approx(0.0, abs=1.0)




def test_extract_audio_rms_curve_unaligned_bytes_and_empty_fallbacks(tmp_path):
    dummy = tmp_path / "stream.mp4"
    dummy.write_text("fake video")

    # 1. Single odd byte (1 byte -> trimmed to 0 bytes -> empty)
    mock_proc = MagicMock()
    mock_proc.stdout = b"\x7f"
    with patch("subprocess.run", return_value=mock_proc):
        with patch("scripts.gaming_audio_detector._HAS_NUMPY", True):
            assert extract_audio_rms_curve(str(dummy)) == ([], 0.0, 0.0)
        with patch("scripts.gaming_audio_detector._HAS_NUMPY", False):
            assert extract_audio_rms_curve(str(dummy)) == ([], 0.0, 0.0)

    # 2. 3 bytes (1 int16 sample + 1 unaligned byte) -> trimmed to 2 bytes (1 sample)
    # chunk_sec=0.1 means samples_per_chunk=1600. Since 1 sample < 1600, returns [rms], rms, 0.0
    mock_proc.stdout = array.array("h", [1234]).tobytes() + b"\xff"
    with patch("subprocess.run", return_value=mock_proc):
        with patch("scripts.gaming_audio_detector._HAS_NUMPY", True):
            rms_np, mean_np, std_np = extract_audio_rms_curve(str(dummy), chunk_sec=0.1)
        with patch("scripts.gaming_audio_detector._HAS_NUMPY", False):
            rms_py, mean_py, std_py = extract_audio_rms_curve(str(dummy), chunk_sec=0.1)

    assert rms_np == [pytest.approx(1234.0, abs=1.0)]
    assert rms_py == [pytest.approx(1234.0, abs=1.0)]
    assert mean_np == pytest.approx(mean_py, abs=1.0)
    assert std_np == pytest.approx(std_py, abs=1.0)


def test_extract_audio_rms_curve_partial_and_odd_chunk_lengths(tmp_path):
    dummy = tmp_path / "stream.mp4"
    dummy.write_text("fake video")

    # 4000 samples (2.5 chunks of 1600 samples)
    # Chunk 1: 1600 samples of 1000
    # Chunk 2: 1600 samples of 2000
    # Trailing: 800 samples of 5000 (should be discarded identically by both)
    samples = [1000] * 1600 + [2000] * 1600 + [5000] * 800
    mock_proc = MagicMock()
    mock_proc.stdout = array.array("h", samples).tobytes()

    with patch("subprocess.run", return_value=mock_proc):
        with patch("scripts.gaming_audio_detector._HAS_NUMPY", True):
            rms_np, mean_np, std_np = extract_audio_rms_curve(str(dummy), chunk_sec=0.1)
        with patch("scripts.gaming_audio_detector._HAS_NUMPY", False):
            rms_py, mean_py, std_py = extract_audio_rms_curve(str(dummy), chunk_sec=0.1)

    assert len(rms_np) == 2
    assert len(rms_py) == 2
    assert rms_np[0] == pytest.approx(1000.0, abs=1.0)
    assert rms_np[1] == pytest.approx(2000.0, abs=1.0)
    assert rms_np == pytest.approx(rms_py, rel=1e-3, abs=0.1)
    assert mean_np == pytest.approx(mean_py, rel=1e-3, abs=0.1)
    assert std_np == pytest.approx(std_py, rel=1e-3, abs=0.1)

    # All-zero samples (silence)
    mock_proc.stdout = array.array("h", [0] * 3200).tobytes()
    with patch("subprocess.run", return_value=mock_proc):
        with patch("scripts.gaming_audio_detector._HAS_NUMPY", True):
            rms_np, mean_np, std_np = extract_audio_rms_curve(str(dummy), chunk_sec=0.1)
        with patch("scripts.gaming_audio_detector._HAS_NUMPY", False):
            rms_py, mean_py, std_py = extract_audio_rms_curve(str(dummy), chunk_sec=0.1)

    assert rms_np == [0.0, 0.0]
    assert rms_py == [0.0, 0.0]
    assert mean_np == 0.0
    assert std_np == 0.0


def test_extract_audio_rms_curve_tiny_or_zero_chunk_sec(tmp_path):
    dummy = tmp_path / "stream.mp4"
    dummy.write_text("fake video")

    # chunk_sec <= 0 clamped to max(1, ...)
    mock_proc = MagicMock()
    mock_proc.stdout = array.array("h", [1500, 2500]).tobytes()

    with patch("subprocess.run", return_value=mock_proc):
        with patch("scripts.gaming_audio_detector._HAS_NUMPY", True):
            rms_np, mean_np, std_np = extract_audio_rms_curve(str(dummy), chunk_sec=0.0)
        with patch("scripts.gaming_audio_detector._HAS_NUMPY", False):
            rms_py, mean_py, std_py = extract_audio_rms_curve(str(dummy), chunk_sec=0.0)

    assert len(rms_np) == 2
    assert len(rms_py) == 2
    assert rms_np[0] == pytest.approx(1500.0, abs=1.0)
    assert rms_np[1] == pytest.approx(2500.0, abs=1.0)
    assert rms_np == pytest.approx(rms_py, rel=1e-3, abs=0.1)


def test_compute_audio_zscores_edge_cases_and_nan_guards():
    # 1. Empty rms list
    assert compute_audio_zscores([], mean=10.0, std=5.0) == []

    # 2. Zero standard deviation guards
    assert compute_audio_zscores([10.0, 10.0, 10.0], mean=10.0, std=0.0) == [0.0, 0.0, 0.0]
    assert compute_audio_zscores([10.0, 10.0], mean=10.0, std=1e-7) == [0.0, 0.0]

    # 3. Single element list
    with patch("scripts.gaming_audio_detector._HAS_NUMPY", True):
        assert compute_audio_zscores([5.0], mean=5.0, std=0.0) == [0.0]
    with patch("scripts.gaming_audio_detector._HAS_NUMPY", False):
        assert compute_audio_zscores([5.0], mean=5.0, std=0.0) == [0.0]

    # 4. Consistency on negative and extreme values
    extreme_vals = [-1000.0, 0.0, 50000.0]
    mean = 16333.33
    std = 23814.09
    with patch("scripts.gaming_audio_detector._HAS_NUMPY", True):
        z_np = compute_audio_zscores(extreme_vals, mean, std)
    with patch("scripts.gaming_audio_detector._HAS_NUMPY", False):
        z_py = compute_audio_zscores(extreme_vals, mean, std)

    assert z_np == pytest.approx(z_py, rel=1e-3, abs=1e-4)
