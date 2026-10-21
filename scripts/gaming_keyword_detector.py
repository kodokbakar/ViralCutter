import re
from typing import List, Dict, Any, Optional

GAMING_KEYWORDS_ID = [
    "anjir", "gila", "mati", "woi", "bisa gitu", "hoki", "rata",
    "mampus", "waduh", "lah", "kebantai", "panik", "anjay", "kocak"
]

GAMING_KEYWORDS_EN = [
    "no way", "let's go", "holy shit", "what the fuck", "clutch", "ace",
    "headshot", "hacker", "omg", "gg", "ez", "pog", "insane", "wtf"
]

ALL_KEYWORDS = sorted(GAMING_KEYWORDS_ID + GAMING_KEYWORDS_EN, key=len, reverse=True)
KEYWORD_PATTERNS = [(kw, re.compile(r"\b" + re.escape(kw) + r"\b", re.IGNORECASE)) for kw in ALL_KEYWORDS]
MULTI_WORD_KEYWORDS = {kw for kw in ALL_KEYWORDS if " " in kw}


def _safe_float(val: Any, default: float = 0.0) -> float:
    try:
        if val is None:
            return default
        return float(val)
    except (ValueError, TypeError):
        return default


def match_gaming_keywords(text: str) -> List[str]:
    """Finds all gaming shout keywords occurring in text."""
    if not text or not isinstance(text, str):
        return []
    matched = []
    for kw, pattern in KEYWORD_PATTERNS:
        if pattern.search(text):
            matched.append(kw)
    return matched


def scan_shout_keywords(words: List[Dict[str, Any]], window_sec: float = 8.0) -> List[Dict[str, Any]]:
    """
    Scans word-level transcript for clusters of shout keywords within window_sec.
    Returns list of event dicts with timestamp, count, matched_words, and score.
    """
    if not words or not isinstance(words, list):
        return []

    # Map each word / consecutive word n-gram to matched keywords
    keyword_hits = []
    n = len(words)
    k = 0

    while k < n:
        w = words[k]
        if not isinstance(w, dict):
            k += 1
            continue

        start = _safe_float(w.get("start"), 0.0)
        word_text = str(w.get("word") or "").strip()

        matched = []
        matched_span = 1

        # Check multi-word phrase sequences across consecutive words (3-word then 2-word)
        for span in (3, 2):
            if k + span <= n:
                cand = words[k:k+span]
                if all(isinstance(c, dict) for c in cand):
                    close = True
                    for idx in range(span - 1):
                        e_prev = _safe_float(cand[idx].get("end"), _safe_float(cand[idx].get("start"), 0.0))
                        s_next = _safe_float(cand[idx+1].get("start"), 0.0)
                        if s_next - e_prev > 1.5:
                            close = False
                            break
                    if close:
                        combined = " ".join(str(c.get("word") or "").strip() for c in cand)
                        clean_combined = re.sub(r"[^\w\s']", "", combined).strip().lower()
                        if clean_combined in MULTI_WORD_KEYWORDS:
                            matched = [clean_combined]
                            matched_span = span
                            break

        if not matched:
            matched = match_gaming_keywords(word_text)
            matched_span = 1

        if matched:
            keyword_hits.append({
                "start": start,
                "keywords": matched
            })
            k += matched_span
        else:
            k += 1

    if not keyword_hits:
        return []

    # Sort hits chronologically
    keyword_hits.sort(key=lambda x: x["start"])

    clusters = []
    total_hits = len(keyword_hits)
    i = 0

    while i < total_hits:
        t_start = keyword_hits[i]["start"]
        t_end = t_start + window_sec
        sub = [h for h in keyword_hits if t_start <= h["start"] <= t_end]

        all_words = []
        for s in sub:
            all_words.extend(s["keywords"])

        count = len(all_words)
        # Score scaled to 100. 1 keyword = 35, 2 keywords = 65, >= 3 keywords = 90-100
        score = min(100.0, 35.0 + (count - 1) * 30.0) if count > 0 else 0.0

        center_time = sum(h["start"] for h in sub) / len(sub) if sub else t_start

        clusters.append({
            "timestamp": round(center_time, 2),
            "count": count,
            "matched_words": sorted(list(set(all_words))),
            "score": round(score, 1)
        })

        # Advance past window
        i += len(sub)

    clusters.sort(key=lambda x: x["score"], reverse=True)
    return clusters


def get_keyword_score_at_time(events: List[Dict[str, Any]], timestamp: float, max_distance: float = 4.0) -> float:
    """Returns interpolated keyword score around a given timestamp."""
    if not events or not isinstance(events, list):
        return 0.0

    best_score = 0.0
    for ev in events:
        if not isinstance(ev, dict):
            continue
        ev_ts = _safe_float(ev.get("timestamp"), 0.0)
        ev_score = _safe_float(ev.get("score"), 0.0)
        dist = abs(ev_ts - timestamp)

        if dist <= max_distance:
            decay = 1.0 if max_distance <= 0 else max(0.0, 1.0 - (dist / max_distance))
            eff_score = ev_score * decay
            if eff_score > best_score:
                best_score = eff_score

    return round(best_score, 1)
