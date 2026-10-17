import pytest
from scripts import broll_engine


def test_list_templates_returns_catalog():
    templates = broll_engine.list_templates()
    ids = [t["id"] for t in templates]
    assert "stat_counter" in ids
    assert "quote_card" in ids
    assert "point_highlight" in ids


def test_render_stat_counter_html():
    data = {
        "target_number": "87",
        "prefix": "+",
        "suffix": "%",
        "label": "Tingkat Retensi",
        "accent_color": "#FF3B30",
    }
    html = broll_engine.render_html_content("stat_counter", data)
    assert "87" in html
    assert "Tingkat Retensi" in html
    assert "window.renderSeek" in html
    assert "background: transparent" in html or "background:transparent" in html


def test_render_quote_card_html():
    data = {
        "quote": "Konten hebat butuh hook cepat",
        "author": "Budi Santoso",
        "title": "Kreator Konten",
    }
    html = broll_engine.render_html_content("quote_card", data)
    assert "Konten hebat butuh hook cepat" in html
    assert "Budi Santoso" in html
    assert "window.renderSeek" in html


def test_render_point_highlight_html():
    data = {
        "headline": "3 Kunci Viral",
        "points": ["Hook 3 detik", "Pacing dinamis", "Punchline jelas"],
    }
    html = broll_engine.render_html_content("point_highlight", data)
    assert "3 Kunci Viral" in html
    assert "Hook 3 detik" in html
    assert "window.renderSeek" in html
