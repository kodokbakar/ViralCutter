import os
import math
import subprocess
from typing import List, Dict, Tuple, Any, Optional


def compute_audio_zscores(rms_values: List[float], mean: float, std: float) -> List[float]:
    """Computes Z-scores for each RMS audio value against stream baseline."""
    if not rms_values:
        return []
    if std <= 1e-6:
        return [0.0] * len(rms_values)
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


def extract_audio_rms_curve(video_path: str, chunk_sec: float = 0.1) -> Tuple[List[float], float, float]:
    """
    Extracts RMS amplitude per chunk_sec from video_path using FFmpeg.
    Returns (rms_list, mean, std).
    """
    if not os.path.exists(video_path):
        return [], 0.0, 0.0

    cmd = [
        "ffmpeg", "-nostdin", "-y", "-i", video_path,
        "-vn", "-ac", "1", "-ar", "16000",
        "-f", "s16le", "-"
    ]
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
        if not raw_bytes:
            return [], 0.0, 0.0

        if len(raw_bytes) % 2 != 0:
            raw_bytes = raw_bytes[:len(raw_bytes) - (len(raw_bytes) % 2)]

        import array
        samples = array.array("h")
        samples.frombytes(raw_bytes)

        sample_rate = 16000
        samples_per_chunk = max(1, int(sample_rate * chunk_sec))
        rms_values = []

        for offset in range(0, len(samples), samples_per_chunk):
            chunk = samples[offset:offset + samples_per_chunk]
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
