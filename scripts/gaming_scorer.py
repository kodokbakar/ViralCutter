import os
import re
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
    speech_events: Optional[List[Dict[str, Any]]] = None,
    isolated_audio_penalty: float = 0.6,
    convergence_boost: float = 1.15,
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

    # Candidate anchors from the UNION of audio, keyword, and face events
    candidate_ts_list = []
    for ev in audio_events:
        if isinstance(ev, dict):
            ts = _safe_float(ev.get("timestamp"), None)
            if ts is not None and ts >= 0.0 and not isinstance(ev.get("timestamp"), bool):
                candidate_ts_list.append((ts, 0, _safe_float(ev.get("score"), 0.0)))
    for ev in keyword_events:
        if isinstance(ev, dict):
            ts = _safe_float(ev.get("timestamp"), None)
            if ts is not None and ts >= 0.0 and not isinstance(ev.get("timestamp"), bool):
                candidate_ts_list.append((ts, 1, _safe_float(ev.get("score"), 0.0)))
    for ev in face_events:
        if isinstance(ev, dict):
            ts = _safe_float(ev.get("timestamp"), None)
            if ts is not None and ts >= 0.0 and not isinstance(ev.get("timestamp"), bool):
                candidate_ts_list.append((ts, 2, _safe_float(ev.get("score"), 0.0)))

    if not candidate_ts_list:
        return []

    # Cluster timestamps within tol_sec, prioritizing audio, then keyword, then face, sorted by score descending
    candidate_ts_list.sort(key=lambda item: (item[1], -item[2], item[0]))
    anchor_timestamps = []
    for ts, prio, sc in candidate_ts_list:
        if any(abs(ts - a) <= tol_sec for a in anchor_timestamps):
            continue
        anchor_timestamps.append(ts)

    candidates = []
    for ts in anchor_timestamps:
        a_score = 0.0
        for a in audio_events:
            if isinstance(a, dict):
                a_ts = _safe_float(a.get("timestamp"), None)
                if a_ts is not None and abs(a_ts - ts) <= tol_sec:
                    a_score = max(a_score, _safe_float(a.get("score"), 0.0))

        kw_score = gaming_keyword_detector.get_keyword_score_at_time(keyword_events, ts, max_distance=tol_sec)

        f_score = 0.0
        for f in face_events:
            if isinstance(f, dict):
                f_ts = _safe_float(f.get("timestamp"), None)
                if f_ts is not None and abs(f_ts - ts) <= tol_sec:
                    f_score = max(f_score, _safe_float(f.get("score"), 0.0))

        composite = (a_score * w_audio) + (f_score * w_face) + (kw_score * w_kw)

        # Modality presence
        has_audio = a_score > 0.0
        has_kw = kw_score > 0.0
        has_face = f_score > 0.0

        # Speech presence check
        has_speech = False
        if speech_events is not None:
            try:
                for sp in speech_events:
                    if isinstance(sp, dict):
                        s_st = _safe_float(sp.get("start"), None)
                        s_en = _safe_float(sp.get("end"), None)
                        if s_st is not None and s_en is not None:
                            if s_st - tol_sec <= ts <= s_en + tol_sec:
                                has_speech = True
                                break
                        s_ts = _safe_float(sp.get("timestamp"), None)
                        if s_ts is not None and abs(s_ts - ts) <= tol_sec:
                            has_speech = True
                            break
                    else:
                        s_ts = _safe_float(sp, None)
                        if s_ts is not None and abs(s_ts - ts) <= tol_sec:
                            has_speech = True
                            break
            except Exception:
                has_speech = False

        # Isolated audio junk penalty (loud audio spike with no face reaction, keywords, or speech)
        is_isolated = False
        if has_audio and not has_kw and not has_face and not has_speech:
            composite = composite * max(0.0, _safe_float(isolated_audio_penalty, 0.6))
            is_isolated = True

        # Multi-signal convergence boost (2+ modalities co-occur)
        modalities_count = sum(1 for m in (has_audio, has_kw, has_face) if m)
        is_converged = False
        if modalities_count >= 2:
            boost = max(1.0, _safe_float(convergence_boost, 1.15))
            composite = min(100.0, composite * boost)
            is_converged = True

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
            "keywords": sorted(list(set(matched_kws))),
            "converged": is_converged,
            "isolated_audio": is_isolated,
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
    language: str = "id",
    transcript_words: Optional[Any] = None,
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

    valid_words = []
    if transcript_words is not None:
        try:
            for w in transcript_words:
                if isinstance(w, dict):
                    ws = _safe_float(w.get("start"), None)
                    we = _safe_float(w.get("end"), None)
                    if ws is not None and we is not None and ws <= we:
                        valid_words.append({"word": str(w.get("word", "")), "start": ws, "end": we})
        except Exception:
            valid_words = []
    valid_words.sort(key=lambda x: x["start"])

    segments = []
    for p in peaks:
        if not isinstance(p, dict):
            continue
        ts = _safe_float(p.get("timestamp"), None)
        if ts is None or ts < 0.0:
            continue

        score = _safe_float(p.get("score"), 0.0)
        audio_score = _safe_float(p.get("audio_score", score), score)

        total_roll = pre + post
        ratio_pre = (pre / total_roll) if total_roll > 0 else 0.6
        if total_roll > max_dur:
            eff_pre = max_dur * ratio_pre
            eff_post = max_dur * (1.0 - ratio_pre)
        else:
            eff_pre = pre
            eff_post = post

        ideal_start = max(0.0, round(ts - eff_pre, 2))
        ideal_end = min(vid_dur, round(ts + eff_post, 2))

        if valid_words:
            # Adaptive speech-boundary snapping:
            # Start: look back [ts - 22.0, ts - 6.0] for natural speech pause
            search_start_min = max(0.0, ts - 22.0)
            search_start_max = max(0.0, ts - 6.0)
            start_candidates = []
            for k, w in enumerate(valid_words):
                w_start = w["start"]
                if search_start_min <= w_start <= search_start_max:
                    if k == 0 or (w_start - valid_words[k - 1]["end"]) >= 0.4:
                        start_candidates.append(w_start)

            start = min(start_candidates, key=lambda c: abs(c - ideal_start)) if start_candidates else ideal_start

            # End: look forward [ts + 6.0, ts + 18.0] for post-reaction phrase conclusion
            search_end_min = min(vid_dur, ts + 6.0)
            search_end_max = min(vid_dur, ts + 18.0)
            end_candidates = []
            for k, w in enumerate(valid_words):
                w_end = w["end"]
                if search_end_min <= w_end <= search_end_max:
                    if k == len(valid_words) - 1 or (valid_words[k + 1]["start"] - w_end) >= 0.4:
                        end_candidates.append(w_end)

            end = min(end_candidates, key=lambda c: abs(c - ideal_end)) if end_candidates else ideal_end
        else:
            start = ideal_start
            end = ideal_end

        start = max(0.0, round(start, 2))
        end = min(vid_dur, round(end, 2))
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
            ideal_pre = max_dur * ratio_pre
            ideal_post = max_dur - ideal_pre
            start = max(0.0, round(ts - ideal_pre, 2))
            end = min(vid_dur, round(ts + ideal_post, 2))
            if round(end - start, 2) < max_dur:
                if start == 0.0:
                    end = min(vid_dur, round(start + max_dur, 2))
                elif end == vid_dur:
                    start = max(0.0, round(end - max_dur, 2))
            dur = round(end - start, 2)

        # Invariant: ts must always be inside [start, end]
        if start > ts:
            start = max(0.0, ts)
        if end < ts:
            end = min(vid_dur, ts)
        dur = round(end - start, 2)

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
            "title": hook,
            "hook_title": hook,
            "keywords": kws,
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


def refine_gaming_candidates_with_llm(
    candidates: List[Dict[str, Any]],
    transcript_words: Optional[Any] = None,
    video_path: Optional[str] = None,
    ai_backend: str = "offline",
    api_key: Optional[str] = None,
    ai_model_name: Optional[str] = None,
    base_url: Optional[str] = None,
    language: str = "id",
) -> List[Dict[str, Any]]:
    """
    Refines candidate gaming clips using LLM if an AI backend is configured.
    Generates context-specific viral hooks and refines scores for clutch/outplay/fail moments.
    Gracefully falls back to original candidates untouched if offline, timeout, or error.
    """
    if not candidates:
        return []

    backend = (ai_backend or "").strip().lower()
    if not backend or backend in ("offline", "none"):
        return candidates

    try:
        from scripts import smart_clipping
    except ImportError:
        return candidates

    words = []
    if transcript_words is not None:
        try:
            for w in transcript_words:
                if isinstance(w, dict) and "word" in w and "start" in w and "end" in w:
                    words.append(w)
        except Exception:
            words = []

    clip_contexts = []
    for idx, c in enumerate(candidates):
        c_start = _safe_float(c.get("start_time"), 0.0)
        c_end = _safe_float(c.get("end_time"), 0.0)
        clip_dialogue = " ".join(
            str(w.get("word", ""))
            for w in words
            if _safe_float(w.get("start"), 0.0) >= c_start and _safe_float(w.get("end"), 0.0) <= c_end
        ).strip()
        clip_contexts.append({
            "index": idx,
            "start_time": c_start,
            "end_time": c_end,
            "score": c.get("score", 75),
            "dialogue": clip_dialogue if clip_dialogue else "(no spoken dialogue)",
            "keywords": c.get("keywords", []),
        })

    lang_desc = "Indonesian" if str(language).lower() in ("id", "indonesian") else "English"
    prompt = (
        f"You are an expert esports and gaming video editor for TikTok and YouTube Shorts.\n"
        f"Evaluate these {len(clip_contexts)} gaming stream candidate clips ({lang_desc} commentary).\n"
        f"Analyze streamer dialogue and gameplay context (clutch, outplay, funny fail, rage, jumpscare).\n"
        f"For each clip, return JSON object with:\n"
        f"- 'index': candidate index integer\n"
        f"- 'hook_title': high-CTR 3-6 word ALL CAPS headline in {lang_desc}\n"
        f"- 'score': refined virality score integer (0-100)\n"
        f"- 'virality_explanation': concise 1-sentence explanation of what made this moment viral\n\n"
        f"Candidates:\n{json.dumps(clip_contexts, indent=2, ensure_ascii=False)}\n\n"
        f"Return ONLY valid JSON array."
    )

    try:
        resp = smart_clipping.query_ai_backend(
            prompt=prompt,
            ai_backend=backend,
            api_key=api_key,
            ai_model_name=ai_model_name,
            base_url=base_url,
        )
        if not resp or not resp.strip():
            return candidates

        clean_resp = resp.strip()
        if "```" in clean_resp:
            clean_resp = re.sub(r"^```[a-zA-Z]*\n", "", clean_resp)
            clean_resp = re.sub(r"\n```$", "", clean_resp).strip()

        data = json.loads(clean_resp)
        if not isinstance(data, list):
            return candidates

        refined = [dict(c) for c in candidates]
        for item in data:
            if not isinstance(item, dict):
                continue
            idx = item.get("index")
            if idx is None or not isinstance(idx, int) or idx < 0 or idx >= len(refined):
                continue
            hook = str(item.get("hook_title") or "").strip().upper()
            if hook:
                refined[idx]["title"] = hook
                refined[idx]["hook_title"] = hook
            new_score = _safe_float(item.get("score"), None)
            if new_score is not None and 0.0 <= new_score <= 100.0:
                refined[idx]["score"] = int(round(new_score))
                if "rubric" in refined[idx] and isinstance(refined[idx]["rubric"], dict):
                    refined[idx]["rubric"]["hook_strength"] = round(new_score / 10.0, 1)
            expl = str(item.get("virality_explanation") or "").strip()
            if expl:
                refined[idx]["virality_explanation"] = expl
                if "rubric" in refined[idx] and isinstance(refined[idx]["rubric"], dict):
                    refined[idx]["rubric"]["verdict"] = expl

        return refined
    except Exception as e:
        print(f"[GAMING-SCORER] LLM refinement fallback to offline: {e}")
        return candidates


def run_gaming_clipping_pipeline(
    video_path: Any,
    project_folder: Any,
    transcript_words: Optional[Any],
    video_duration: float,
    num_segments: Optional[int] = 5,
    min_duration: float = 20.0,
    max_duration: float = 60.0,
    facecam_crop: Optional[str] = None,
    language: str = "id",
    ai_backend: str = "offline",
    api_key: Optional[str] = None,
    ai_model_name: Optional[str] = None,
    base_url: Optional[str] = None,
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
    valid_events = [
        ev
        for ev in (audio_events + keyword_events)
        if isinstance(ev, dict) and "timestamp" in ev and not isinstance(ev.get("timestamp"), bool)
    ]
    valid_events.sort(key=lambda x: _safe_float(x.get("score"), 0.0), reverse=True)
    candidate_ts = [ev["timestamp"] for ev in valid_events[:15]]
    face_events = []
    if video_str and os.path.exists(video_str):
        face_events = gaming_facecam_detector.detect_facecam_reactions(
            video_path=video_str,
            facecam_box_str=facecam_crop,
            candidate_timestamps=candidate_ts
        )

    # 4. Fusion and NMS
    fused = fuse_gaming_scores(
        audio_events,
        keyword_events,
        face_events,
        speech_events=transcript_words,
        isolated_audio_penalty=0.6,
        convergence_boost=1.15,
    )
    num_limit = int(_safe_float(num_segments, 5.0) or 5)
    peaks = apply_non_maximum_suppression(fused, radius_sec=45.0)[:max(1, num_limit)]

    # 5. Window generation with adaptive speech boundary snapping
    segments = generate_gaming_windows(
        peaks,
        video_duration=video_duration,
        min_duration=min_duration,
        max_duration=max_duration,
        language=language,
        transcript_words=transcript_words,
    )

    # 6. Hybrid LLM candidate refinement (if configured)
    if ai_backend and str(ai_backend).lower() not in ("offline", "none"):
        segments = refine_gaming_candidates_with_llm(
            candidates=segments,
            transcript_words=transcript_words,
            video_path=video_str,
            ai_backend=ai_backend,
            api_key=api_key,
            ai_model_name=ai_model_name,
            base_url=base_url,
            language=language,
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
