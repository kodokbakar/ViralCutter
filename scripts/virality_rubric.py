from typing import Any, Dict, Optional, Tuple

WEIGHTS = {
    "hook_strength": 0.25,        # 0-3s stop-the-scroll impact
    "retention_flow": 0.25,       # Pacing & narrative momentum
    "emotional_resonance": 0.20,  # Relatability, surprise, or controversy
    "shareability": 0.15,         # Urge to forward to peers/groups
    "audio_dynamics": 0.15,       # Speech energy & rhythm
}

DIMENSIONS = {
    "hook_strength": "Stop-the-Scroll Impact (0-3s)",
    "retention_flow": "Narrative Flow & Momentum",
    "emotional_resonance": "Emotional Depth & Value",
    "shareability": "Virality & Share Probability",
    "audio_dynamics": "Audio Energy & Delivery Rhythm",
}


def _clamp(val: Any, default: float = 7.0, min_v: float = 1.0, max_v: float = 10.0) -> float:
    try:
        if val is None:
            return default
        f = float(val)
        return max(min_v, min(max_v, round(f, 1)))
    except (TypeError, ValueError):
        return default


def compute_verdict(composite: int, hook: float, retention: float) -> str:
    if composite >= 90:
        if hook >= 9.0:
            return "Elite Hook & Peak Retention: high viral breakout probability."
        return "Exceptional Value & Resonance: strong organic share potential."
    elif composite >= 80:
        if hook >= 8.5:
            return "Punchy Opening: holds initial scroll with solid momentum."
        return "Solid Narrative: consistent retention across the core idea."
    elif composite >= 70:
        return "Decent Content: good topic, moderate conversion velocity."
    return "Niche Appeal: lower virality threshold, recommended for loyal audience."


def compute_composite_score(
    raw_dimensions: Dict[str, Any],
    audio_energy: float = 75.0,
    user_verdict: Optional[str] = None
) -> Tuple[int, Dict[str, Any]]:
    """
    Computes calibrated composite virality score (0-100) from 5 dimensional ratings (1-10).
    """
    if not isinstance(raw_dimensions, dict):
        raw_dimensions = {}

    hook = _clamp(raw_dimensions.get("hook_strength") or raw_dimensions.get("hook"), 8.0)
    retention = _clamp(raw_dimensions.get("retention_flow") or raw_dimensions.get("retention"), 8.0)
    emotion = _clamp(raw_dimensions.get("emotional_resonance") or raw_dimensions.get("emotion"), 7.5)
    share = _clamp(raw_dimensions.get("shareability") or raw_dimensions.get("share"), 7.5)

    # Audio energy is 0-100 scale, normalize to 0-10
    audio_scaled = _clamp(audio_energy / 10.0, 7.5)

    composite_float = (
        hook * WEIGHTS["hook_strength"]
        + retention * WEIGHTS["retention_flow"]
        + emotion * WEIGHTS["emotional_resonance"]
        + share * WEIGHTS["shareability"]
        + audio_scaled * WEIGHTS["audio_dynamics"]
    ) * 10.0

    score = max(1, min(100, int(round(composite_float))))
    verdict = user_verdict or compute_verdict(score, hook, retention)

    rubric_dict = {
        "composite_score": score,
        "hook_strength": hook,
        "retention_flow": retention,
        "emotional_resonance": emotion,
        "shareability": share,
        "audio_dynamics": audio_scaled,
        "verdict": verdict,
    }

    return score, rubric_dict


def normalize_rubric_dict(raw_rubric: Any, fallback_score: int = 80) -> Dict[str, Any]:
    """
    Normalizes existing or legacy rubric dictionary, or creates plausible rubric
    from a single integer score.
    """
    if isinstance(raw_rubric, dict) and "hook_strength" in raw_rubric:
        hook = _clamp(raw_rubric.get("hook_strength"), 8.0)
        retention = _clamp(raw_rubric.get("retention_flow"), 8.0)
        emotion = _clamp(raw_rubric.get("emotional_resonance"), 7.5)
        share = _clamp(raw_rubric.get("shareability"), 7.5)
        audio = _clamp(raw_rubric.get("audio_dynamics"), 7.5)
        comp = int(raw_rubric.get("composite_score") or fallback_score)
        verdict = str(raw_rubric.get("verdict") or compute_verdict(comp, hook, retention))
        return {
            "composite_score": comp,
            "hook_strength": hook,
            "retention_flow": retention,
            "emotional_resonance": emotion,
            "shareability": share,
            "audio_dynamics": audio,
            "verdict": verdict,
        }

    # Generate synthetic proportional rubric from single score
    base_dim = max(1.0, min(10.0, round(float(fallback_score) / 10.0, 1)))
    return {
        "composite_score": int(fallback_score),
        "hook_strength": base_dim,
        "retention_flow": base_dim,
        "emotional_resonance": base_dim,
        "shareability": base_dim,
        "audio_dynamics": base_dim,
        "verdict": compute_verdict(int(fallback_score), base_dim, base_dim),
    }
