import os
import math
import json
import random
from typing import List, Dict, Any, Optional
from scripts import gaming_audio_detector
from scripts import gaming_keyword_detector
from scripts import gaming_facecam_detector


GAMING_HOOKS_ID = [
    "DETIK-DETIK CLUTCH PANIK?!",
    "MOMEN TERGILA BIKIN SYOK!",
    "REAKSI REFLEKS DEWA BANGET?!",
    "MOMEN HOKI SEUMUR HIDUP!",
    "DETIK DETIK JUMPSCARE FATAL?!",
    "GAK BISA BERKATA-KATA LAGI!",
    "EPIC CLUTCH GILA BANGET!"
]

GAMING_HOOKS_EN = [
    "INSANE CLUTCH MOMENT EVER?!",
    "HE COULD NOT BELIEVE THIS!",
    "PEAK GAMER RAGE REACTION?!",
    "LUCKIEST SHOT IN GAMING!",
    "NO WAY THIS JUST HAPPENED!",
    "PURE UNFILTERED CHAOS HERE!"
]


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


def generate_gaming_hook_title(keywords: Optional[Any] = None, language: str = "id") -> str:
    """Generates a high-CTR ALL CAPS 3-6 word gaming hook headline."""
    lang_str = str(language).lower() if language else "id"
    catalog = GAMING_HOOKS_ID if lang_str in ["id", "indonesian"] else GAMING_HOOKS_EN

    if keywords is not None:
        try:
            kw_list = list(keywords)
        except TypeError:
            kw_list = []
        clean_kws = [str(k).upper() for k in kw_list if k]
        matching = [t for t in catalog if any(k in t for k in clean_kws)]
        if matching:
            return random.choice(matching)

    return random.choice(catalog)

def fuse_gaming_scores(
    audio_events: Optional[List[Dict[str, Any]]],
    keyword_events: Optional[List[Dict[str, Any]]],
    face_events: Optional[List[Dict[str, Any]]] = None,
    tolerance_sec: float = 3.0,
) -> List[Dict[str, Any]]:
    """Combines audio, facecam, and keyword events into a unified score curve."""
    try:
        audio_events = list(audio_events) if audio_events is not None else []
    except TypeError:
        audio_events = []
    try:
        keyword_events = list(keyword_events) if keyword_events is not None else []
    except TypeError:
        keyword_events = []
    try:
        face_events = list(face_events) if face_events is not None else []
    except TypeError:
        face_events = []

    tol_sec = max(0.0, _safe_float(tolerance_sec, 3.0))

    has_face = False
    for f in face_events:
        if isinstance(f, dict) and _safe_float(f.get("score"), 0.0) > 0.0:
            has_face = True
            break

    w_audio = 0.50 if has_face else 0.70
    w_face = 0.30 if has_face else 0.00
    w_kw = 0.20 if has_face else 0.30

    # Primary anchors: audio events; fallback: keyword events if audio events empty
    primary_events = audio_events if audio_events else keyword_events
    if not primary_events:
        return []

    candidates = []
    for anchor in primary_events:
        if not isinstance(anchor, dict):
            continue
        ts = _safe_float(anchor.get("timestamp"), None)
        if ts is None or ts < 0.0:
            continue

        a_score = _safe_float(anchor.get("score"), 0.0) if primary_events is audio_events else 0.0
        kw_score = gaming_keyword_detector.get_keyword_score_at_time(keyword_events, ts, max_distance=tol_sec)

        f_score = 0.0
        for f in face_events:
            if isinstance(f, dict):
                f_ts = _safe_float(f.get("timestamp"), None)
                if f_ts is not None and abs(f_ts - ts) <= tol_sec:
                    f_score = max(f_score, _safe_float(f.get("score"), 0.0))

        composite = (a_score * w_audio) + (f_score * w_face) + (kw_score * w_kw)

        matched_kws = []
        for k in keyword_events:
            if isinstance(k, dict):
                k_ts = _safe_float(k.get("timestamp"), None)
                if k_ts is not None and abs(k_ts - ts) <= tol_sec:
                    words = k.get("matched_words", [])
                    if isinstance(words, (list, tuple, set)):
                        matched_kws.extend(words)

        candidates.append({
            "timestamp": round(ts, 2),
            "score": round(composite, 1),
            "audio_score": a_score,
            "face_score": f_score,
            "keyword_score": kw_score,
            "keywords": sorted(list(set(matched_kws)))
        })

    candidates.sort(key=lambda x: x["score"], reverse=True)
    return candidates


def apply_non_maximum_suppression(
    candidates: Optional[List[Dict[str, Any]]],
    radius_sec: float = 45.0
) -> List[Dict[str, Any]]:
    """Suppresses neighboring candidate peaks within radius_sec of a higher-scoring peak."""
    try:
        candidates = list(candidates) if candidates is not None else []
    except TypeError:
        return []
    valid_cands = []
    for c in candidates:
        if isinstance(c, dict):
            ts = _safe_float(c.get("timestamp"), None)
            if ts is not None and ts >= 0.0:
                valid_cands.append(c)

    rad = _safe_float(radius_sec, 45.0)
    if rad <= 0.0:
        return valid_cands

    # Sort descending by score, deterministic tie-break by timestamp ascending
    sorted_cands = sorted(
        valid_cands,
        key=lambda x: (_safe_float(x.get("score"), 0.0), -_safe_float(x.get("timestamp"), 0.0)),
        reverse=True
    )

    selected = []
    for cand in sorted_cands:
        ts = _safe_float(cand.get("timestamp"), 0.0)
        collision = any(abs(ts - _safe_float(s.get("timestamp"), 0.0)) < rad for s in selected)
        if not collision:
            selected.append(cand)
    return selected


def generate_gaming_windows(
    peaks: Optional[List[Dict[str, Any]]],
    video_duration: float,
    min_duration: float = 20.0,
    max_duration: float = 60.0,
    pre_roll: float = 18.0,
    post_roll: float = 10.0,
    language: str = "id"
) -> List[Dict[str, Any]]:
    """
    Converts event peaks into complete video clip segments with pre-action buildup and post-action reaction.
    """
    try:
        peaks = list(peaks) if peaks is not None else []
    except TypeError:
        return []
    vid_dur = _safe_float(video_duration, 0.0)
    if vid_dur <= 0.0:
        return []

    min_dur = max(1.0, _safe_float(min_duration, 20.0))
    max_dur = max(min_dur, _safe_float(max_duration, 60.0))
    target_min = min(min_dur, vid_dur)
    pre = max(0.0, _safe_float(pre_roll, 18.0))
    post = max(0.0, _safe_float(post_roll, 10.0))

    segments = []
    for p in peaks:
        if not isinstance(p, dict):
            continue
        ts = _safe_float(p.get("timestamp"), None)
        if ts is None or ts < 0.0:
            continue

        score = _safe_float(p.get("score"), 0.0)
        audio_score = _safe_float(p.get("audio_score", score), score)

        start = max(0.0, round(ts - pre, 2))
        end = min(vid_dur, round(ts + post, 2))
        dur = round(end - start, 2)

        if dur < target_min:
            needed = target_min - dur
            start = max(0.0, round(start - needed / 2.0, 2))
            end = min(vid_dur, round(start + target_min, 2))
            dur = round(end - start, 2)
            if dur < target_min:
                start = max(0.0, round(end - target_min, 2))
                dur = round(end - start, 2)

        if dur > max_dur:
            end = round(start + max_dur, 2)
            dur = max_dur

        kws = p.get("keywords")
        if kws is not None:
            try:
                kws = list(kws)
            except TypeError:
                kws = []
        else:
            kws = []
        hook = generate_gaming_hook_title(keywords=kws, language=language)

        segments.append({
            "start_time": start,
            "end_time": end,
            "duration": dur,
            "score": int(round(score)),
            "hook_title": hook,
            "virality_explanation": f"High-energy gaming climax at {round(ts, 1)}s with intense volume spike.",
            "rubric": {
                "hook_strength": min(10.0, max(0.0, round(score / 10.0, 1))),
                "retention_flow": 8.5,
                "emotional_resonance": min(10.0, max(0.0, round(score / 10.0, 1))),
                "shareability": 9.0,
                "audio_dynamics": min(10.0, max(0.0, round(audio_score / 10.0, 1))),
                "verdict": "Explosive gaming highlight."
            }
        })
    return segments


def run_gaming_clipping_pipeline(
    video_path: Any,
    project_folder: Any,
    transcript_words: Optional[Any],
    video_duration: float,
    num_segments: Optional[int] = 5,
    min_duration: float = 20.0,
    max_duration: float = 60.0,
    facecam_crop: Optional[str] = None,
    language: str = "id"
) -> Dict[str, Any]:
    """Runs the full offline gaming clipping detection pipeline."""
    video_str = str(video_path) if video_path else None
    proj_str = str(project_folder) if project_folder else None

    # 1. Audio spike detection
    audio_events = []
    if video_str and os.path.exists(video_str):
        rms_values, mean, std = gaming_audio_detector.extract_audio_rms_curve(video_str)
        audio_events = gaming_audio_detector.detect_audio_events(rms_values, sample_rate_hz=10.0)

    # 2. Exclamatory keyword scanning
    try:
        transcript_words = list(transcript_words) if transcript_words is not None else []
    except TypeError:
        transcript_words = []
    keyword_events = gaming_keyword_detector.scan_shout_keywords(transcript_words)

    # 3. Facecam reaction detection
    candidate_ts = [a["timestamp"] for a in audio_events[:10] if isinstance(a, dict) and "timestamp" in a]
    face_events = []
    if video_str and os.path.exists(video_str):
        face_events = gaming_facecam_detector.detect_facecam_reactions(
            video_path=video_str,
            facecam_box_str=facecam_crop,
            candidate_timestamps=candidate_ts
        )

    # 4. Fusion and NMS
    fused = fuse_gaming_scores(audio_events, keyword_events, face_events)
    num_limit = int(_safe_float(num_segments, 5.0) or 5)
    peaks = apply_non_maximum_suppression(fused, radius_sec=45.0)[:max(1, num_limit)]

    # 5. Window generation
    segments = generate_gaming_windows(
        peaks,
        video_duration=video_duration,
        min_duration=min_duration,
        max_duration=max_duration,
        language=language
    )

    out = {"segments": segments}
    if proj_str:
        try:
            os.makedirs(proj_str, exist_ok=True)
            out_file = os.path.join(proj_str, "viral_segments.json")
            with open(out_file, "w", encoding="utf-8") as f:
                json.dump(out, f, indent=2, ensure_ascii=False)
        except OSError:
            pass

    return out
