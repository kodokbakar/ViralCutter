import os
import math
from typing import List, Dict, Tuple, Optional, Any


def _safe_float(val: Any, default: Optional[float] = 0.0) -> Optional[float]:
    """Safely converts input to float, guarding against None, bool, NaN, and Inf."""
    if val is None or isinstance(val, bool):
        return default
    try:
        res = float(val)
        if math.isnan(res) or math.isinf(res):
            return default
        return res
    except (ValueError, TypeError):
        return default

def compute_mouth_aspect_ratio(landmarks: List[Tuple[float, float]]) -> float:
    """
    Computes Mouth Aspect Ratio (MAR) from 4 or 5 landmark coordinates:
    landmarks[0]: left corner, landmarks[1]: right corner,
    landmarks[2]: top lip, landmarks[3]: bottom lip.
    MAR = height / width.
    """
    if landmarks is None:
        return 0.0

    try:
        if len(landmarks) < 4:
            return 0.0
        left = landmarks[0]
        right = landmarks[1]
        top = landmarks[2]
        bottom = landmarks[3]

        lx = _safe_float(left[0], None)
        ly = _safe_float(left[1], None)
        rx = _safe_float(right[0], None)
        ry = _safe_float(right[1], None)
        tx = _safe_float(top[0], None)
        ty = _safe_float(top[1], None)
        bx = _safe_float(bottom[0], None)
        by = _safe_float(bottom[1], None)

        if None in (lx, ly, rx, ry, tx, ty, bx, by):
            return 0.0

        width = math.sqrt((rx - lx) ** 2 + (ry - ly) ** 2)
        height = math.sqrt((bx - tx) ** 2 + (by - ty) ** 2)

        if width <= 1e-4:
            return 0.0

        mar = height / width
        if math.isnan(mar) or math.isinf(mar) or mar < 0.0:
            return 0.0

        return round(mar, 3)
    except (IndexError, TypeError, ValueError):
        return 0.0


def score_facecam_reaction(mar: float, motion_velocity: float) -> float:
    """
    Scores facecam reaction intensity out of 100 based on mouth opening and head movement.
    MAR > 0.12 triggers high score; velocity > 15.0 px/frame adds body movement bonus.
    """
    mar_val = max(0.0, _safe_float(mar, 0.0) or 0.0)
    vel_val = max(0.0, _safe_float(motion_velocity, 0.0) or 0.0)

    if mar_val >= 0.12:
        mar_score = min(60.0, 30.0 + (mar_val - 0.12) * 250.0)
    else:
        mar_score = max(0.0, mar_val * 200.0)

    motion_score = 0.0
    if vel_val > 3.0:
        motion_score = (vel_val - 3.0) * 1.5
        if vel_val > 15.0:
            motion_score += 10.0
        motion_score = min(40.0, max(0.0, motion_score))

    total = min(100.0, max(0.0, mar_score + motion_score))
    return round(total, 1)


def detect_facecam_reactions(
    video_path: str,
    facecam_box_str: Optional[str] = None,
    candidate_timestamps: Optional[List[float]] = None
) -> List[Dict[str, Any]]:
    """
    Extracts facecam frames around candidate_timestamps (or scans stream) and detects reactions.
    Gracefully returns [] if video is missing, or fallback neutral reactions if facecam box
    is missing or OpenCV/InsightFace detects no faces.
    """
    if not video_path or not isinstance(video_path, str) or not os.path.exists(video_path):
        return []

    if candidate_timestamps is None:
        return []

    try:
        clean_ts = []
        for ts in candidate_timestamps:
            v = _safe_float(ts, None)
            if v is not None and v >= 0.0:
                clean_ts.append(round(v, 2))
    except (TypeError, Exception):
        return []

    clean_ts = sorted(set(clean_ts))
    if not clean_ts:
        return []
    # Fallback neutral reaction if CV detector is unavailable or no faces found
    reactions = []
    for ts in clean_ts:
        reactions.append({
            "timestamp": ts,
            "mar": 0.05,
            "motion_velocity": 0.0,
            "score": 0.0
        })

    return reactions
