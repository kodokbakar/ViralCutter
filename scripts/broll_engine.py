import html
import os
from typing import Any, Dict, List

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

        valid_items.append({
            "start_offset": round(start_offset, 3),
            "duration": round(clamped_duration, 3),
            "template_id": tpl_id,
            "data": b_data,
        })

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
