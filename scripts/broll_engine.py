import html
import json
import os
import re
from typing import Any, Dict, List, Tuple

TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), "broll_templates")

# Map of supported template IDs to their underlying HTML files
TEMPLATE_FILE_MAP: Dict[str, str] = {
    "stat_counter": "stat_counter.html",
    "vox_stat_counter": "stat_counter.html",
    "quote_card": "quote_card.html",
    "vox_quote_card": "quote_card.html",
    "point_highlight": "point_highlight.html",
    "vox_point_list": "point_highlight.html",
    "vox_versus_split": "vox_versus_split.html",
    "vox_headline_punch": "vox_headline_punch.html",
    "vox_explainer_def": "vox_explainer_def.html",
    "vox_bar_chart": "vox_bar_chart.html",
}

VALID_TEMPLATE_IDS = set(TEMPLATE_FILE_MAP.keys())
def normalize_broll_items(
    raw_broll: Any,
    max_items: int = 3,
    min_gap: float = 3.0,
    min_duration: float = 2.0,
    max_duration: float = 5.0,
) -> List[Dict[str, Any]]:
    """
    Validates, clamps, sorts, deduplicates, and spaces out B-Roll items for a clip.
    Guarantees no visual overlap and caps to max_items (default: 3).
    """
    if not isinstance(raw_broll, list):
        return []

    valid_items = []
    for item in raw_broll:
        if not isinstance(item, dict):
            continue
        tpl_id = str(item.get("template_id", "")).strip()
        if tpl_id not in VALID_TEMPLATE_IDS:
            continue
        try:
            start_offset = float(item.get("start_offset", -1.0))
            duration = float(item.get("duration", 3.5))
        except (ValueError, TypeError):
            continue
        if start_offset < 0.0 or duration <= 0.0:
            continue

        clamped_duration = max(min_duration, min(max_duration, duration))
        b_data = item.get("data")
        if not isinstance(b_data, dict):
            b_data = {}

        entry = {
            "start_offset": round(start_offset, 3),
            "duration": round(clamped_duration, 3),
            "template_id": tpl_id,
            "data": b_data,
        }
        for k in ("audio_snapped", "matched_word", "matched_time", "video_path", "anchor_phrase"):
            if k in item:
                entry[k] = item[k]
        valid_items.append(entry)

    # Sort chronologically by start_offset
    valid_items.sort(key=lambda x: x["start_offset"])

    # Enforce minimum gap between consecutive brolls and limit to max_items
    spaced_items = []
    last_end = -1.0
    for item in valid_items:
        if len(spaced_items) >= max_items:
            break
        if last_end < 0 or (item["start_offset"] >= last_end + min_gap):
            spaced_items.append(item)
            last_end = item["start_offset"] + item["duration"]

    return spaced_items

def extract_keywords_from_broll(item: Dict[str, Any]) -> Tuple[List[str], List[str]]:
    """
    Extracts (primary_keywords, secondary_keywords) from a B-roll item.
    Primary keywords (numbers, anchor phrases, main terms) take precedence
    over generic secondary label words.
    """
    if not isinstance(item, dict):
        return [], []

    primary: List[str] = []
    secondary: List[str] = []

    # 1. Explicit anchor_phrase if provided by LLM
    anchor = item.get("anchor_phrase") or item.get("trigger_phrase")
    if anchor and isinstance(anchor, str):
        primary.append(anchor.strip().lower())

    data = item.get("data")
    if not isinstance(data, dict):
        return primary, secondary

    tpl_id = str(item.get("template_id", "")).strip()

    # 2. Template-specific keyword extraction
    if tpl_id in ("stat_counter", "vox_stat_counter"):
        target_num = str(data.get("target_number", "")).strip()
        if target_num:
            # Strip percent / currency symbols for pure number matching
            num_clean = re.sub(r"[^\w\s]", "", target_num).strip().lower()
            if num_clean:
                primary.append(num_clean)
        label = str(data.get("label", "")).strip()
        if label:
            words = [w.strip().lower() for w in label.split() if len(w.strip()) >= 4]
            secondary.extend(words)

    elif tpl_id in ("quote_card", "vox_quote_card"):
        quote = str(data.get("quote", "")).strip()
        if quote:
            words = [w.strip().lower() for w in quote.split() if len(w.strip()) >= 4]
            if words:
                primary.extend(words[:3])
                secondary.extend(words[3:8])
        author = str(data.get("author", "")).strip()
        if author:
            secondary.extend([w.strip().lower() for w in author.split() if len(w.strip()) >= 3])

    elif tpl_id in ("point_highlight", "vox_point_list"):
        headline = str(data.get("headline", "")).strip()
        if headline:
            words = [w.strip().lower() for w in headline.split() if len(w.strip()) >= 4]
            primary.extend(words)
        points = data.get("points")
        if isinstance(points, list) and points:
            first_pt = str(points[0]).strip()
            secondary.extend([w.strip().lower() for w in first_pt.split() if len(w.strip()) >= 4])

    elif tpl_id == "vox_versus_split":
        for field in ("title_a", "title_b"):
            val = str(data.get(field, "")).strip()
            if val:
                primary.extend([w.strip().lower() for w in val.split() if len(w.strip()) >= 3])
        for field in ("tag_a", "tag_b"):
            val = str(data.get(field, "")).strip()
            if val:
                secondary.extend([w.strip().lower() for w in val.split() if len(w.strip()) >= 3])

    elif tpl_id == "vox_headline_punch":
        for field in ("line_1", "line_2", "line_3"):
            val = str(data.get(field, "")).strip()
            if val:
                primary.extend([w.strip().lower() for w in val.split() if len(w.strip()) >= 4])
        tag = str(data.get("tag", "")).strip()
        if tag:
            secondary.extend([w.strip().lower() for w in tag.split() if len(w.strip()) >= 4])

    elif tpl_id == "vox_explainer_def":
        term = str(data.get("term", "")).strip()
        if term:
            term_clean = re.sub(r"[^\w\s]", "", term).strip().lower()
            primary.append(term_clean)
            primary.extend([w.strip().lower() for w in term.split() if len(w.strip()) >= 3])

    elif tpl_id == "vox_bar_chart":
        title = str(data.get("chart_title", "")).strip()
        if title:
            primary.extend([w.strip().lower() for w in title.split() if len(w.strip()) >= 4])

    def _clean_list(raw_list: List[str]) -> List[str]:
        seen = set()
        res = []
        for k in raw_list:
            clean_k = "".join(c for c in k if c.isalnum() or c.isspace()).strip()
            if clean_k and clean_k not in seen:
                seen.add(clean_k)
                res.append(clean_k)
        return res

    return _clean_list(primary), _clean_list(secondary)


def _extract_words_helper(data: Any) -> List[Dict[str, Any]]:
    words: List[Dict[str, Any]] = []
    segments: List[Any] = []
    if isinstance(data, dict):
        segments = data.get("segments", [])
    elif isinstance(data, list):
        segments = data

    for seg in segments:
        if not isinstance(seg, dict):
            continue
        seg_words = seg.get("words")
        if seg_words and isinstance(seg_words, list):
            for w in seg_words:
                if not isinstance(w, dict):
                    continue
                w_text = str(w.get("word") or "").strip()
                s = w.get("start")
                e = w.get("end")
                if w_text and s is not None and e is not None:
                    clean = "".join(c for c in w_text.lower() if c.isalnum())
                    words.append({
                        "word": w_text,
                        "clean_word": clean,
                        "start": float(s),
                        "end": float(e),
                    })
        else:
            text = str(seg.get("text") or "").strip()
            s = seg.get("start")
            e = seg.get("end")
            if text and s is not None and e is not None:
                tokens = text.split()
                if tokens:
                    dur = max(0.1, float(e) - float(s))
                    step = dur / len(tokens)
                    for i, t in enumerate(tokens):
                        clean = "".join(c for c in t.lower() if c.isalnum())
                        words.append({
                            "word": t,
                            "clean_word": clean,
                            "start": round(float(s) + i * step, 3),
                            "end": round(float(s) + (i + 1) * step, 3),
                        })
    return words


def snap_broll_items_to_transcript(
    broll_items: List[Dict[str, Any]],
    transcript_source: Any,
    lead_in: float = 0.25,
    search_window: float = 14.0,
) -> List[Dict[str, Any]]:
    """
    Aligns B-roll start_offset with actual spoken words from WhisperX transcript.
    Finds candidate words matching item keywords within search_window seconds
    of the estimated start_offset, adjusting start_offset to word_start - lead_in.
    """
    if not broll_items:
        return []

    words: List[Dict[str, Any]] = []
    if isinstance(transcript_source, str) and os.path.exists(transcript_source):
        try:
            with open(transcript_source, "r", encoding="utf-8") as f:
                data = json.load(f)
                words = _extract_words_helper(data)
        except Exception as e:
            print(f"[WARN] Failed to load transcript for B-roll snapping: {e}")
            words = []
    elif isinstance(transcript_source, (dict, list)):
        words = _extract_words_helper(transcript_source)

    if not words:
        return normalize_broll_items(broll_items)

    snapped_items = []
    for item in broll_items:
        if not isinstance(item, dict):
            continue
        item_copy = dict(item)
        est_offset = float(item_copy.get("start_offset", 0.0))
        primary_kw, secondary_kw = extract_keywords_from_broll(item_copy)

        def _find_best_match(kw_list: List[str]) -> Any:
            match = None
            lowest_dist = float("inf")
            for kw in kw_list:
                kw_tokens = kw.split()
                if len(kw_tokens) > 1:
                    kw_str = " ".join(kw_tokens)
                    for i in range(len(words) - len(kw_tokens) + 1):
                        window_tokens = [w["clean_word"] for w in words[i:i + len(kw_tokens)]]
                        window_str = " ".join(window_tokens)
                        if kw_str in window_str or window_str in kw_str:
                            w_start = words[i]["start"]
                            dist = abs(w_start - est_offset)
                            if dist <= search_window and dist < lowest_dist:
                                lowest_dist = dist
                                match = words[i]
                else:
                    for w in words:
                        cw = w["clean_word"]
                        if kw == cw or (len(kw) >= 3 and (kw in cw or cw in kw)):
                            dist = abs(w["start"] - est_offset)
                            if dist <= search_window and dist < lowest_dist:
                                lowest_dist = dist
                                match = w
            return match

        # Match against primary keywords first (e.g. number, main phrase, term)
        best_match = _find_best_match(primary_kw)
        if best_match is None and secondary_kw:
            best_match = _find_best_match(secondary_kw)
        if best_match is not None:
            snapped_start = max(0.0, round(best_match["start"] - lead_in, 3))
            print(
                f"[B-ROLL SNAP] Aligned '{item_copy.get('template_id')}' to spoken word '{best_match['word']}' at {best_match['start']:.2f}s "
                f"(offset shifted from {est_offset:.2f}s -> {snapped_start:.2f}s)"
            )
            item_copy["start_offset"] = snapped_start
            item_copy["audio_snapped"] = True
            item_copy["matched_word"] = best_match["word"]
            item_copy["matched_time"] = round(best_match["start"], 3)
            dur = float(item_copy.get("duration", 3.5))
            item_copy["duration"] = max(3.0, min(5.0, dur))

        snapped_items.append(item_copy)

    return normalize_broll_items(snapped_items)


CATALOG: List[Dict[str, Any]] = [
    {
        "id": "stat_counter",
        "name": "Vox Metric Punch",
        "description": "Bold kinetic number counter with kraft tape, ruler marks, and highlighter sweep",
        "default_duration": 3.5,
        "sample_data": {
            "target_number": "87",
            "prefix": "+",
            "suffix": "%",
            "label": "Lonjakan Retensi 3 Detik Pertama",
            "accent_color": "#FF5A36",
        },
    },
    {
        "id": "quote_card",
        "name": "Vox Editorial Pull-Quote",
        "description": "Angled newsprint paper cutout with animated highlighter marker and speaker stamp",
        "default_duration": 4.0,
        "sample_data": {
            "quote": "Bila pembukaan video tidak memikat dalam 2 detik, penonton pergi selamanya.",
            "author": "Dr. Sarah Adams",
            "title": "Media Psychologist",
        },
    },
    {
        "id": "point_highlight",
        "name": "Vox Collage Sticky Steps",
        "description": "Staggered numbered paper index cards with caution tape and stop-motion timing",
        "default_duration": 4.5,
        "sample_data": {
            "headline": "3 KUNCI VIRAL",
            "points": ["Hook 3 detik pertama", "Pacing tanpa dead-air", "Punchline memuaskan"],
        },
    },
    {
        "id": "vox_versus_split",
        "name": "Vox Versus / Split Screen",
        "description": "Full-screen dual-tone split comparison (Navy vs Coral) with rotating VS stamp",
        "default_duration": 4.0,
        "sample_data": {
            "tag_a": "CARA LAMA",
            "title_a": "MANUAL EDIT",
            "desc_a": "Butuh 4 jam per video pendek, rawan lelah dan tidak konsisten.",
            "tag_b": "CARA BARU",
            "title_b": "VIRALCUTTER AI",
            "desc_b": "Selesai dalam 2 menit otomatis dengan 3-part storytelling retention.",
        },
    },
    {
        "id": "vox_headline_punch",
        "name": "Vox Kinetic Typographic Hook",
        "description": "Full-screen 9:16 kinetic text slam with yellow highlighter block and breaking badge",
        "default_duration": 3.5,
        "sample_data": {
            "tag": "BREAKING INSIGHT",
            "line_1": "JANGAN PERNAH",
            "line_2": "BUANG 3 DETIK",
            "line_3": "PERTAMA ANDA",
            "subtext": "Algoritma TikTok dan Reels mengukur 70% retensi dari detik pembuka.",
        },
    },
    {
        "id": "vox_explainer_def",
        "name": "Vox Glossary / Blueprint Def",
        "description": "Technical dictionary breakdown with phonetic guide and highlighter sweep",
        "default_duration": 4.0,
        "sample_data": {
            "term": "HOOK RETENTION",
            "phonetic": "/hʊk rɪˈten.ʃən/",
            "pos": "noun",
            "definition": "Teknik psikologi visual untuk menghentikan jempol penonton dari scrolling.",
            "context_note": "Faktor nomor 1 penentu viralitas di YouTube Shorts dan Reels.",
        },
    },
    {
        "id": "vox_bar_chart",
        "name": "Vox Editorial Data Graph",
        "description": "Animated comparison bar graph with diagonal textures and counter ticker",
        "default_duration": 4.0,
        "sample_data": {
            "chart_title": "PERBANDINGAN RETENSI AUDIENS",
            "source": "DATA ANALYTICS 2026",
            "bars": [
                {"label": "Standard", "value": "24%", "height": 32, "accent": False},
                {"label": "Jump-Cut", "value": "58%", "height": 65, "accent": False},
                {"label": "ViralCutter", "value": "89%", "height": 95, "accent": True},
            ],
        },
    },
]


def list_templates() -> List[Dict[str, Any]]:
    return list(CATALOG)


def get_template_path(template_id: str) -> str:
    filename = TEMPLATE_FILE_MAP.get(template_id)
    if not filename:
        filename = f"{template_id}.html"
    path = os.path.join(TEMPLATES_DIR, filename)
    if not os.path.exists(path):
        raise FileNotFoundError(f"B-roll template '{template_id}' not found at {path}")
    return path


def render_html_content(template_id: str, data: Dict[str, Any]) -> str:
    path = get_template_path(template_id)
    with open(path, "r", encoding="utf-8") as f:
        template_str = f.read()

    data = data or {}

    if template_id in ("stat_counter", "vox_stat_counter"):
        target_num = html.escape(str(data.get("target_number", "100")))
        prefix = html.escape(str(data.get("prefix", "")))
        suffix = html.escape(str(data.get("suffix", "%")))
        label = html.escape(str(data.get("label", "Key Statistic")))
        accent = html.escape(str(data.get("accent_color", "#FF5A36")))

        rendered = template_str.replace("{{TARGET_NUMBER}}", target_num)
        rendered = rendered.replace("{{PREFIX}}", prefix)
        rendered = rendered.replace("{{SUFFIX}}", suffix)
        rendered = rendered.replace("{{LABEL}}", label)
        rendered = rendered.replace("{{ACCENT_COLOR}}", accent)
        return rendered

    elif template_id in ("quote_card", "vox_quote_card"):
        quote = html.escape(str(data.get("quote", "")))
        author = html.escape(str(data.get("author", "Speaker")))
        title = html.escape(str(data.get("title", "")))

        rendered = template_str.replace("{{QUOTE}}", quote)
        rendered = rendered.replace("{{AUTHOR}}", author)
        rendered = rendered.replace("{{TITLE}}", title)
        return rendered

    elif template_id in ("point_highlight", "vox_point_list"):
        headline = html.escape(str(data.get("headline", "Summary")))
        raw_points = data.get("points") or ["Key Point 1", "Key Point 2"]
        if isinstance(raw_points, str):
            raw_points = [p.strip() for p in raw_points.split("\n") if p.strip()]

        points_html_parts = []
        for idx, pt in enumerate(raw_points, start=1):
            esc_pt = html.escape(str(pt))
            points_html_parts.append(
                f'<div class="point-card">'
                f'<div class="badge-number">{idx:02d}</div>'
                f'<div class="point-text">{esc_pt}</div>'
                f'</div>'
            )
        points_html = "\n".join(points_html_parts)

        rendered = template_str.replace("{{HEADLINE}}", headline)
        rendered = rendered.replace("{{POINTS_HTML}}", points_html)
        return rendered

    elif template_id == "vox_versus_split":
        tag_a = html.escape(str(data.get("tag_a", "BEFORE")))
        title_a = html.escape(str(data.get("title_a", "OLD WAY")))
        desc_a = html.escape(str(data.get("desc_a", "")))

        tag_b = html.escape(str(data.get("tag_b", "AFTER")))
        title_b = html.escape(str(data.get("title_b", "NEW WAY")))
        desc_b = html.escape(str(data.get("desc_b", "")))

        rendered = template_str.replace("{{TAG_A}}", tag_a)
        rendered = rendered.replace("{{TITLE_A}}", title_a)
        rendered = rendered.replace("{{DESC_A}}", desc_a)
        rendered = rendered.replace("{{TAG_B}}", tag_b)
        rendered = rendered.replace("{{TITLE_B}}", title_b)
        rendered = rendered.replace("{{DESC_B}}", desc_b)
        return rendered

    elif template_id == "vox_headline_punch":
        tag = html.escape(str(data.get("tag", "KEY TAKEAWAY")))
        line_1 = html.escape(str(data.get("line_1", "JANGAN PERNAH")))
        line_2 = html.escape(str(data.get("line_2", "LEWATKAN INI")))
        line_3 = html.escape(str(data.get("line_3", "UNTUK RETENSI")))
        subtext = html.escape(str(data.get("subtext", "")))

        rendered = template_str.replace("{{TAG}}", tag)
        rendered = rendered.replace("{{LINE_1}}", line_1)
        rendered = rendered.replace("{{LINE_2}}", line_2)
        rendered = rendered.replace("{{LINE_3}}", line_3)
        rendered = rendered.replace("{{SUBTEXT}}", subtext)
        return rendered

    elif template_id == "vox_explainer_def":
        term = html.escape(str(data.get("term", "KEY CONCEPT")))
        phonetic = html.escape(str(data.get("phonetic", "/kiː kɒn.sept/")))
        pos = html.escape(str(data.get("pos", "noun")))
        definition = html.escape(str(data.get("definition", "")))
        context_note = html.escape(str(data.get("context_note", "")))

        rendered = template_str.replace("{{TERM}}", term)
        rendered = rendered.replace("{{PHONETIC}}", phonetic)
        rendered = rendered.replace("{{POS}}", pos)
        rendered = rendered.replace("{{DEFINITION}}", definition)
        rendered = rendered.replace("{{CONTEXT_NOTE}}", context_note)
        return rendered

    elif template_id == "vox_bar_chart":
        chart_title = html.escape(str(data.get("chart_title", "DATA COMPARISON")))
        source = html.escape(str(data.get("source", "VERIFIED DATA")))
        bars = data.get("bars") or [
            {"label": "Item A", "value": "30%", "height": 30, "accent": False},
            {"label": "Item B", "value": "85%", "height": 85, "accent": True},
        ]

        bars_html_parts = []
        for b in bars:
            label = html.escape(str(b.get("label", "")))
            val = html.escape(str(b.get("value", "")))
            h = max(5, min(100, int(b.get("height", 50))))
            is_accent = bool(b.get("accent", False))
            accent_cls = "accent" if is_accent else ""

            bars_html_parts.append(
                f'<div class="bar-col {accent_cls}">'
                f'<div class="bar-value">{val}</div>'
                f'<div class="bar-pillar" data-target-height="{h}"></div>'
                f'<div class="bar-label">{label}</div>'
                f'</div>'
            )
        bars_html = "\n".join(bars_html_parts)

        rendered = template_str.replace("{{CHART_TITLE}}", chart_title)
        rendered = rendered.replace("{{SOURCE}}", source)
        rendered = rendered.replace("{{BARS_HTML}}", bars_html)
        return rendered

    raise ValueError(f"Unsupported template_id: {template_id}")
