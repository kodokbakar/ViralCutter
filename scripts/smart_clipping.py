import os
import json
import subprocess
from typing import List, Dict, Tuple, Optional, Any

def extract_words_from_transcript(transcript_data: Any) -> List[Dict[str, Any]]:
    """
    Extracts flat word list with start, end, word from transcript data dict or list.
    """
    words = []
    if isinstance(transcript_data, dict):
        segments = transcript_data.get("segments", [])
    elif isinstance(transcript_data, list):
        segments = transcript_data
    else:
        return words

    for seg in segments:
        seg_words = seg.get("words")
        if seg_words and isinstance(seg_words, list):
            for w in seg_words:
                text = str(w.get("word") or "").strip()
                start = w.get("start")
                end = w.get("end")
                if text and start is not None and end is not None:
                    words.append({
                        "word": text,
                        "start": float(start),
                        "end": float(end),
                        "score": float(w.get("score", 1.0) or 1.0)
                    })
        else:
            # Fallback if words not present in segment
            text = str(seg.get("text") or "").strip()
            start = seg.get("start")
            end = seg.get("end")
            if text and start is not None and end is not None:
                words.append({
                    "word": text,
                    "start": float(start),
                    "end": float(end),
                    "score": 1.0
                })
    return words

def snap_time_to_word_boundary(
    timestamp: float,
    words: List[Dict[str, Any]],
    is_start: bool,
    window: float = 3.0,
    margin: float = 0.05
) -> float:
    """
    Snaps timestamp to the nearest word boundary within a search window.
    For start: snaps to word start minus safety margin.
    For end: snaps to word end plus safety margin.
    """
    if not words:
        return max(0.0, float(timestamp))

    target = float(timestamp)
    candidates = []
    for w in words:
        ref_time = w["start"] if is_start else w["end"]
        diff = abs(ref_time - target)
        if diff <= window:
            candidates.append((diff, ref_time))

    if not candidates:
        return max(0.0, target)

    candidates.sort(key=lambda x: x[0])
    best_time = candidates[0][1]

    if is_start:
        return max(0.0, round(best_time - margin, 3))
    else:
        return max(0.0, round(best_time + margin, 3))

def snap_segment_boundaries(
    start_time: float,
    end_time: float,
    words: List[Dict[str, Any]],
    margin: float = 0.05,
    min_duration: float = 1.0
) -> Tuple[float, float]:
    """
    Snaps both start and end times to word boundaries while preserving minimum duration.
    """
    snapped_start = snap_time_to_word_boundary(start_time, words, is_start=True, margin=margin)
    snapped_end = snap_time_to_word_boundary(end_time, words, is_start=False, margin=margin)

    if snapped_end <= snapped_start + min_duration:
        snapped_end = max(snapped_start + min_duration, end_time)

    return snapped_start, snapped_end
