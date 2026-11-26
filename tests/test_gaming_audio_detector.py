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


def _create_test_wav(path, duration_sec=0.2, sample_rate=16000, value=1500):
    import wave
    n_samples = int(duration_sec * sample_rate)
    raw = array.array("h", [value] * n_samples).tobytes()
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(raw)


def test_extract_audio_rms_curve_audio_path_kwarg(tmp_path):
    video_file = tmp_path / "stream.mp4"
    video_file.write_text("fake video")
    audio_file = tmp_path / "audio_16k.wav"
    audio_file.write_text("fake audio")

    mock_proc = MagicMock()
    mock_proc.stdout = array.array("h", [1200] * 1600).tobytes()

    with patch("subprocess.run", return_value=mock_proc) as mock_run:
        rms, mean, std = extract_audio_rms_curve(
            str(video_file),
            audio_path=str(audio_file),
            vocal_bandpass=True,
        )
        assert len(rms) == 1
        assert rms[0] == pytest.approx(1200.0, abs=1.0)
        # Verify FFmpeg was passed the audio_file, NOT video_file
        cmd = mock_run.call_args[0][0]
        i_idx = cmd.index("-i")
        assert cmd[i_idx + 1] == str(audio_file)
        assert str(video_file) not in cmd


def test_extract_audio_rms_curve_audio_path_positional(tmp_path):
    video_file = tmp_path / "stream.mp4"
    video_file.write_text("fake video")
    audio_file = tmp_path / "audio_16k.wav"
    audio_file.write_text("fake audio")

    mock_proc = MagicMock()
    mock_proc.stdout = array.array("h", [800] * 1600).tobytes()

    with patch("subprocess.run", return_value=mock_proc) as mock_run:
        rms, mean, std = extract_audio_rms_curve(
            str(video_file),
            str(audio_file),
            vocal_bandpass=True,
        )
        assert len(rms) == 1
        assert rms[0] == pytest.approx(800.0, abs=1.0)
        cmd = mock_run.call_args[0][0]
        i_idx = cmd.index("-i")
        assert cmd[i_idx + 1] == str(audio_file)


def test_extract_audio_rms_curve_wav_input_direct(tmp_path):
    audio_file = tmp_path / "stream.wav"
    audio_file.write_text("fake wav")

    mock_proc = MagicMock()
    mock_proc.stdout = array.array("h", [2500] * 1600).tobytes()

    with patch("subprocess.run", return_value=mock_proc) as mock_run:
        rms, mean, std = extract_audio_rms_curve(str(audio_file), vocal_bandpass=True)
        assert len(rms) == 1
        assert rms[0] == pytest.approx(2500.0, abs=1.0)
        cmd = mock_run.call_args[0][0]
        i_idx = cmd.index("-i")
        assert cmd[i_idx + 1] == str(audio_file)


def test_extract_audio_rms_curve_direct_wav_fast_path(tmp_path):
    wav_path = tmp_path / "fast_audio.wav"
    _create_test_wav(wav_path, duration_sec=0.2, sample_rate=16000, value=2000)

    # When vocal_bandpass is False and input is valid 16kHz mono WAV,
    # it must read directly from wave file without calling subprocess.run
    with patch("subprocess.run", side_effect=AssertionError("subprocess.run should not be called")):
        rms, mean, std = extract_audio_rms_curve(str(wav_path), vocal_bandpass=False)
        assert len(rms) == 2  # 0.2s at 0.1s chunk = 2 chunks
        assert rms[0] == pytest.approx(2000.0, abs=1.0)
        assert rms[1] == pytest.approx(2000.0, abs=1.0)
        assert mean == pytest.approx(2000.0, abs=1.0)


def test_main_improved_extract_cached_audio_lifecycle(tmp_path):
    import main_improved
    proj_dir = tmp_path / "proj"
    proj_dir.mkdir()
    video_file = proj_dir / "input.mp4"
    video_file.write_text("dummy video")

    target_wav = proj_dir / "audio_16k.wav"
    calls = []

    def mock_extract(v_path, out_wav):
        calls.append((v_path, out_wav))
        _create_test_wav(out_wav, duration_sec=0.3, sample_rate=16000, value=1500)
        return out_wav

    with patch("scripts.smart_clipping.extract_audio_for_transcription", side_effect=mock_extract):
        # First call: extracts audio once
        res1 = main_improved.extract_cached_audio(str(video_file), str(proj_dir))
        assert res1 == str(target_wav)
        assert len(calls) == 1
        assert target_wav.exists()

        # Second call: reuses cached WAV without running extraction again
        res2 = main_improved.extract_cached_audio(str(video_file), str(proj_dir))
        assert res2 == str(target_wav)
        assert len(calls) == 1  # No additional extraction call!


def test_main_improved_extract_cached_audio_fallback_on_error(tmp_path):
    import main_improved
    proj_dir = tmp_path / "proj_err"
    proj_dir.mkdir()
    video_file = proj_dir / "corrupt.mp4"
    video_file.write_text("corrupt data")

    with patch("scripts.smart_clipping.extract_audio_for_transcription", side_effect=subprocess.CalledProcessError(1, "ffmpeg")):
        # If extraction fails, must return None cleanly without crashing
        res = main_improved.extract_cached_audio(str(video_file), str(proj_dir))
        assert res is None


def test_audio_cache_reuse_across_whisper_and_gaming_pipeline(tmp_path):
    import main_improved
    from scripts import transcribe_video, gaming_scorer

    proj_dir = tmp_path / "unified_proj"
    proj_dir.mkdir()
    video_file = proj_dir / "input.mp4"
    video_file.write_text("video frames")

    cached_wav = proj_dir / "audio_16k.wav"
    _create_test_wav(cached_wav, duration_sec=1.0, sample_rate=16000, value=3000)

    # 1. Verify transcribe loads audio from cached_wav
    loaded_audio_paths = []
    fake_whisperx = MagicMock()
    fake_whisperx.load_audio.side_effect = lambda p: loaded_audio_paths.append(str(p)) or [0.1] * 16000
    fake_whisperx.load_model.return_value = MagicMock(transcribe=lambda *a, **k: {"segments": [], "language": "en"})
    fake_whisperx.load_align_model.return_value = (MagicMock(), {})
    fake_whisperx.align.return_value = {"segments": [], "word_segments": []}

    fake_utils = MagicMock()
    def fake_writer(*a, **k):
        (proj_dir / "input.srt").write_text("1\n00:00:00,000 --> 00:00:01,000\nhi")
        (proj_dir / "input.tsv").write_text("start\tend\ttext")
        (proj_dir / "input.json").write_text("{}")
    fake_utils.get_writer.return_value = fake_writer
    fake_whisperx.utils = fake_utils

    with patch.dict("sys.modules", {"whisperx": fake_whisperx, "whisperx.utils": fake_utils}):
        transcribe_video.transcribe(
            str(video_file),
            project_folder=str(proj_dir),
            audio_path=str(cached_wav),
        )
        assert str(cached_wav) in loaded_audio_paths
        assert str(video_file) not in loaded_audio_paths

    # 2. Verify gaming pipeline extracts audio RMS from cached_wav
    extracted_rms_sources = []
    def spy_rms(path, *args, **kwargs):
        extracted_rms_sources.append(str(kwargs.get("audio_path") or path))
        return [10.0] * 50, 10.0, 1.0

    with patch("scripts.gaming_audio_detector.extract_audio_rms_curve", side_effect=spy_rms):
        gaming_scorer.run_gaming_clipping_pipeline(
            video_path=str(video_file),
            project_folder=str(proj_dir),
            transcript_words=[],
            video_duration=10.0,
            num_segments=1,
            audio_path=str(cached_wav),
        )
        assert str(cached_wav) in extracted_rms_sources
