import os
import math
import subprocess
from typing import List, Dict, Tuple, Any, Optional

try:
    import numpy as np
    _HAS_NUMPY = True
except ImportError:
    _HAS_NUMPY = False


def compute_audio_zscores(rms_values: List[float], mean: float, std: float) -> List[float]:
    """Computes Z-scores for each RMS audio value against stream baseline."""
    if not rms_values:
        return []
    if std <= 1e-6:
        return [0.0] * len(rms_values)
    if _HAS_NUMPY:
        try:
            rms_arr = np.asarray(rms_values, dtype=np.float32)
            return ((rms_arr - mean) / std).tolist()
        except Exception:
            pass
    return [(v - mean) / std for v in rms_values]


def detect_audio_events(
    rms_values: List[float],
    sample_rate_hz: float = 10.0,
    z_threshold: float = 2.0,
    min_contrast_jump: Optional[float] = None,
) -> List[Dict[str, Any]]:
    """
    Detects spike audio events where volume exceeds z_threshold above baseline.
    sample_rate_hz defaults to 10 (100ms per sample).
    """
    if not rms_values:
        return []

    n = len(rms_values)
    mean = sum(rms_values) / n
    variance = sum((x - mean) ** 2 for x in rms_values) / n
    std = math.sqrt(variance)

    z_scores = compute_audio_zscores(rms_values, mean, std)
    events = []

    # Window step (0.1s per frame)
    step_sec = 1.0 / sample_rate_hz if sample_rate_hz > 0 else 0.1

    i = 0
    while i < n:
        z = z_scores[i]
        if z >= z_threshold:
            # Enforce minimum 1-step cluster span to prevent infinite loops on low/zero rate
            cluster_span = max(1, int(2.0 * max(0.1, sample_rate_hz)))
            cluster_end = min(n, i + cluster_span)
            best_idx = i
            best_z = z
            for j in range(i, cluster_end):
                if z_scores[j] > best_z:
                    best_z = z_scores[j]
                    best_idx = j

            # Check quiet-to-burst contrast (preceding 3 seconds)
            contrast_span = max(1, int(3.0 * max(0.1, sample_rate_hz)))
            contrast_start = max(0, best_idx - contrast_span)
            pre_mean = sum(rms_values[contrast_start:best_idx]) / max(1, best_idx - contrast_start) if best_idx > contrast_start else mean
            jump_ratio = rms_values[best_idx] / max(1e-3, pre_mean)

            # Do not drop peaks if Z >= z_threshold; treat contrast jump as score multiplier/bonus
            # unless min_contrast_jump is strictly specified and not matched.
            if min_contrast_jump is not None and jump_ratio < min_contrast_jump:
                i = max(i + 1, cluster_end)
                continue

            score = min(100.0, max(0.0, (best_z / 4.0) * 80.0 + min(20.0, jump_ratio * 4.0)))
            events.append({
                "timestamp": round(best_idx * step_sec, 2),
                "z_score": round(best_z, 2),
                "intensity": round(rms_values[best_idx], 2),
                "contrast_jump": round(jump_ratio, 2),
                "score": round(score, 1),
            })
            # Skip past cluster; ensure i always advances by at least 1
            i = max(i + 1, cluster_end)
        else:
            i += 1
    events.sort(key=lambda x: x["score"], reverse=True)
    return events


def extract_audio_rms_curve(
    video_path: str,
    chunk_sec: Any = 0.1,
    vocal_bandpass: bool = True,
    low_cut: int = 200,
    high_cut: int = 3500,
    audio_path: Optional[str] = None,
    **kwargs,
) -> Tuple[List[float], float, float]:
    """
    Extracts RMS amplitude per chunk_sec from video_path or pre-extracted audio_path.
    If audio_path is provided or input is already a WAV file, processes audio directly without re-demuxing video.
    When vocal_bandpass is True, applies bandpass filter to focus on human voice frequencies.
    Returns (rms_list, mean, std).
    """
    # Positional backward compatibility: 2nd argument could be audio_path string
    if isinstance(chunk_sec, (str, os.PathLike)) and audio_path is None:
        audio_path = str(chunk_sec)
        chunk_sec = kwargs.get("chunk_sec", 0.1)

    target_audio = audio_path if (audio_path and os.path.exists(audio_path)) else video_path
    if not target_audio or not os.path.exists(target_audio):
        return [], 0.0, 0.0

    raw_bytes = None
    target_str = str(target_audio)

    # Fast path: read 16kHz mono PCM directly from WAV if no bandpass filtering required
    if target_str.lower().endswith(".wav") and not vocal_bandpass:
        try:
            import wave
            with wave.open(target_str, "rb") as wf:
                if wf.getnchannels() == 1 and wf.getsampwidth() == 2 and wf.getframerate() == 16000:
                    raw_bytes = wf.readframes(wf.getnframes())
        except Exception:
            raw_bytes = None

    if raw_bytes is None:
        cmd = [
            "ffmpeg", "-nostdin", "-y", "-i", target_str,
            "-vn", "-ac", "1", "-ar", "16000",
        ]
        if vocal_bandpass:
            cmd.extend(["-af", f"highpass=f={low_cut},lowpass=f={high_cut}"])
        cmd.extend(["-f", "s16le", "-"])
        try:
            proc = subprocess.run(
                cmd,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                timeout=120,
                check=False,
            )
            raw_bytes = proc.stdout
        except (subprocess.TimeoutExpired, subprocess.SubprocessError, Exception):
            return [], 0.0, 0.0

    if not raw_bytes:
        return [], 0.0, 0.0

    try:
        if len(raw_bytes) % 2 != 0:
            raw_bytes = raw_bytes[:len(raw_bytes) - (len(raw_bytes) % 2)]
        if not raw_bytes:
            return [], 0.0, 0.0

        sample_rate = 16000
        samples_per_chunk = max(1, int(sample_rate * float(chunk_sec)))

        if _HAS_NUMPY:
            try:
                arr = np.frombuffer(raw_bytes, dtype=np.int16).astype(np.float32)
                n_chunks = len(arr) // samples_per_chunk
                if n_chunks > 0:
                    chunks = arr[:n_chunks * samples_per_chunk].reshape(n_chunks, samples_per_chunk)
                    rms_arr = np.sqrt(np.mean(chunks ** 2, axis=1))
                    rms_values = rms_arr.tolist()
                    mean = float(np.mean(rms_arr))
                    std = float(np.std(rms_arr))
                    return rms_values, mean, std
                elif len(arr) > 0:
                    rms = float(np.sqrt(np.mean(arr ** 2)))
                    return [rms], rms, 0.0
                else:
                    return [], 0.0, 0.0
            except Exception:
                pass

        # Fallback to pure Python loop
        import array
        samples = array.array("h")
        samples.frombytes(raw_bytes)

        rms_values = []
        usable_samples = (len(samples) // samples_per_chunk) * samples_per_chunk
        samples_to_use = samples[:usable_samples] if usable_samples > 0 else samples

        for offset in range(0, len(samples_to_use), samples_per_chunk):
            chunk = samples_to_use[offset:offset + samples_per_chunk]
            if not chunk:
                continue
            sq_sum = sum(s * s for s in chunk)
            rms = math.sqrt(sq_sum / len(chunk))
            rms_values.append(rms)

        if not rms_values:
            return [], 0.0, 0.0

        mean = sum(rms_values) / len(rms_values)
        var = sum((x - mean) ** 2 for x in rms_values) / len(rms_values)
        std = math.sqrt(var)
        return rms_values, mean, std
    except (subprocess.TimeoutExpired, subprocess.SubprocessError, Exception):
        return [], 0.0, 0.0
