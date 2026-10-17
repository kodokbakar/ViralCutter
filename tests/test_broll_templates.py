import pytest
from scripts import broll_engine


def test_list_templates_returns_full_catalog():
    templates = broll_engine.list_templates()
    ids = [t["id"] for t in templates]
    # Check that all 7 distinct Vox templates are present
    assert "stat_counter" in ids
    assert "quote_card" in ids
    assert "point_highlight" in ids
    assert "vox_versus_split" in ids
    assert "vox_headline_punch" in ids
    assert "vox_explainer_def" in ids
    assert "vox_bar_chart" in ids
    assert len(templates) >= 7


def test_render_stat_counter_html():
    data = {
        "target_number": "87",
        "prefix": "+",
        "suffix": "%",
        "label": "Tingkat Retensi",
        "accent_color": "#FF5A36",
    }
    html = broll_engine.render_html_content("stat_counter", data)
    assert "87" in html
    assert "Tingkat Retensi" in html
    assert "window.renderSeek" in html
    assert "METRIC // EVIDENCE" in html

    # Alias check
    html_alias = broll_engine.render_html_content("vox_stat_counter", data)
    assert "87" in html_alias


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
    assert "PULL-QUOTE // STATEMENT" in html


def test_render_point_highlight_html():
    data = {
        "headline": "3 KUNCI VIRAL",
        "points": ["Hook 3 detik", "Pacing dinamis", "Punchline jelas"],
    }
    html = broll_engine.render_html_content("point_highlight", data)
    assert "3 KUNCI VIRAL" in html
    assert "Hook 3 detik" in html
    assert "window.renderSeek" in html
    assert "01" in html


def test_render_vox_versus_split_html():
    data = {
        "tag_a": "CARA LAMA",
        "title_a": "MANUAL EDIT",
        "desc_a": "4 jam per video",
        "tag_b": "CARA BARU",
        "title_b": "VIRALCUTTER AI",
        "desc_b": "2 menit otomatis",
    }
    html = broll_engine.render_html_content("vox_versus_split", data)
    assert "MANUAL EDIT" in html
    assert "VIRALCUTTER AI" in html
    assert "VS" in html
    assert "window.renderSeek" in html


def test_render_vox_headline_punch_html():
    data = {
        "tag": "BREAKING",
        "line_1": "JANGAN PERNAH",
        "line_2": "BUANG HOOK",
        "line_3": "PERTAMA ANDA",
        "subtext": "Penonton scroll dalam 2 detik",
    }
    html = broll_engine.render_html_content("vox_headline_punch", data)
    assert "BREAKING" in html
    assert "BUANG HOOK" in html
    assert "window.renderSeek" in html


def test_render_vox_explainer_def_html():
    data = {
        "term": "PARADIGM SHIFT",
        "phonetic": "/ˈper.ə.daɪm/",
        "pos": "noun",
        "definition": "Perubahan mendasar dalam pendekatan",
        "context_note": "Penting untuk retensi",
    }
    html = broll_engine.render_html_content("vox_explainer_def", data)
    assert "PARADIGM SHIFT" in html
    assert "Perubahan mendasar" in html
    assert "window.renderSeek" in html


def test_render_vox_bar_chart_html():
    data = {
        "chart_title": "RETENSI PENONTON",
        "source": "DATA 2026",
        "bars": [
            {"label": "Standard", "value": "20%", "height": 25, "accent": False},
            {"label": "ViralCutter", "value": "85%", "height": 90, "accent": True},
        ],
    }
    html = broll_engine.render_html_content("vox_bar_chart", data)
    assert "RETENSI PENONTON" in html
    assert "ViralCutter" in html
    assert "85%" in html
    assert "window.renderSeek" in html
