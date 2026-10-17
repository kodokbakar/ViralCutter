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


def test_normalize_broll_items():
    raw = [
        {"template_id": "vox_versus_split", "start_offset": 5.0, "duration": 3.5, "data": {"title_a": "A"}},
        {"template_id": "invalid_tpl", "start_offset": 6.0, "duration": 2.0, "data": {}},
        {"template_id": "quote_card", "start_offset": 6.0, "duration": 3.0, "data": {"quote": "Overlap"}},  # Overlaps 5.0+3.5=8.5
        {"template_id": "stat_counter", "start_offset": 25.0, "duration": 4.0, "data": {"target_number": "90"}},
        {"template_id": "vox_headline_punch", "start_offset": 50.0, "duration": 3.0, "data": {"line_1": "Boom"}},
        {"template_id": "point_highlight", "start_offset": 70.0, "duration": 3.5, "data": {}},  # 4th item, should be dropped by max_items=3
    ]
    normalized = broll_engine.normalize_broll_items(raw, max_items=3, min_gap=3.0)
    assert len(normalized) == 3
    assert normalized[0]["template_id"] == "vox_versus_split"
    assert normalized[0]["start_offset"] == 5.0
    assert normalized[1]["template_id"] == "stat_counter"
    assert normalized[1]["start_offset"] == 25.0
    assert normalized[2]["template_id"] == "vox_headline_punch"
    assert normalized[2]["start_offset"] == 50.0


def test_extract_keywords_from_broll():
    item = {
        "template_id": "stat_counter",
        "data": {
            "target_number": "85%",
            "label": "Lonjakan Bisnis Cepat",
        },
    }
    primary, secondary = broll_engine.extract_keywords_from_broll(item)
    assert "85" in primary
    assert "lonjakan" in secondary
    assert "bisnis" in secondary


def test_snap_broll_items_to_transcript_aligns_timing():
    """
    Verify that an estimated B-roll at 46.0s snaps to 48.95s when the speaker
    actually says '85 persen' at 49.2s.
    """
    transcript_mock = {
        "segments": [
            {
                "start": 40.0,
                "end": 55.0,
                "words": [
                    {"word": "Saya", "start": 45.0, "end": 45.4},
                    {"word": "melihat", "start": 45.5, "end": 46.1},
                    {"word": "pertumbuhan", "start": 47.0, "end": 47.8},
                    {"word": "mencapai", "start": 48.2, "end": 48.9},
                    {"word": "85", "start": 49.2, "end": 49.6},
                    {"word": "persen", "start": 49.7, "end": 50.3},
                ],
            }
        ]
    }

    broll_items = [
        {
            "template_id": "stat_counter",
            "start_offset": 46.0,  # AI estimated too early
            "duration": 3.5,
            "data": {
                "target_number": "85",
                "label": "Pertumbuhan Bisnis",
            },
        }
    ]

    snapped = broll_engine.snap_broll_items_to_transcript(broll_items, transcript_mock, lead_in=0.25)
    assert len(snapped) == 1
    # 49.2s - 0.25s = 48.95s
    assert snapped[0]["start_offset"] == 48.95
    assert snapped[0]["audio_snapped"] is True
    assert snapped[0]["matched_word"] == "85"
