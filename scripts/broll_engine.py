import html
import os
from typing import Any, Dict, List

TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), "broll_templates")

CATALOG: List[Dict[str, Any]] = [
    {
        "id": "stat_counter",
        "name": "Stat Counter",
        "description": "Animated numerical metric with label and customizable accent color",
        "default_duration": 3.5,
        "sample_data": {
            "target_number": "87",
            "prefix": "+",
            "suffix": "%",
            "label": "Tingkat Retensi 3 Detik Pertama",
            "accent_color": "#FF3B30",
        },
    },
    {
        "id": "quote_card",
        "name": "Quote Card",
        "description": "Highlight memorable punchline or statement with speaker attribution",
        "default_duration": 4.0,
        "sample_data": {
            "quote": "Bila pembukaan video tidak memikat dalam 2 detik, penonton pergi selamanya.",
            "author": "Dr. Sarah Adams",
            "title": "Media Psychologist",
        },
    },
    {
        "id": "point_highlight",
        "name": "Point Highlight",
        "description": "Staggered bullet points highlighting core arguments or steps",
        "default_duration": 4.5,
        "sample_data": {
            "headline": "3 Kunci Viral",
            "points": ["Hook 3 detik pertama", "Pacing tanpa dead-air", "Punchline memuaskan"],
        },
    },
]


def list_templates() -> List[Dict[str, Any]]:
    return list(CATALOG)


def get_template_path(template_id: str) -> str:
    path = os.path.join(TEMPLATES_DIR, f"{template_id}.html")
    if not os.path.exists(path):
        raise FileNotFoundError(f"B-roll template '{template_id}' not found at {path}")
    return path


def render_html_content(template_id: str, data: Dict[str, Any]) -> str:
    path = get_template_path(template_id)
    with open(path, "r", encoding="utf-8") as f:
        template_str = f.read()

    data = data or {}

    if template_id == "stat_counter":
        target_num = html.escape(str(data.get("target_number", "100")))
        prefix = html.escape(str(data.get("prefix", "")))
        suffix = html.escape(str(data.get("suffix", "%")))
        label = html.escape(str(data.get("label", "Key Statistic")))
        accent = html.escape(str(data.get("accent_color", "#FF3B30")))

        rendered = template_str.replace("{{TARGET_NUMBER}}", target_num)
        rendered = rendered.replace("{{PREFIX}}", prefix)
        rendered = rendered.replace("{{SUFFIX}}", suffix)
        rendered = rendered.replace("{{LABEL}}", label)
        rendered = rendered.replace("{{ACCENT_COLOR}}", accent)
        return rendered

    elif template_id == "quote_card":
        quote = html.escape(str(data.get("quote", "")))
        author = html.escape(str(data.get("author", "Speaker")))
        title = html.escape(str(data.get("title", "")))

        rendered = template_str.replace("{{QUOTE}}", quote)
        rendered = rendered.replace("{{AUTHOR}}", author)
        rendered = rendered.replace("{{TITLE}}", title)
        return rendered

    elif template_id == "point_highlight":
        headline = html.escape(str(data.get("headline", "Summary")))
        raw_points = data.get("points") or ["Key Point 1", "Key Point 2"]
        points_html_parts = []
        for idx, pt in enumerate(raw_points, start=1):
            esc_pt = html.escape(str(pt))
            points_html_parts.append(
                f'<div class="point-item"><div class="point-badge">{idx}</div><span>{esc_pt}</span></div>'
            )
        points_html = "\n".join(points_html_parts)

        rendered = template_str.replace("{{HEADLINE}}", headline)
        rendered = rendered.replace("{{POINTS_HTML}}", points_html)
        return rendered

    raise ValueError(f"Unsupported template_id: {template_id}")
