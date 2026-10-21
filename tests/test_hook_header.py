import json
import os
import pytest
import argparse
from pathlib import Path

from scripts.create_viral_segments import (
    process_segments,
    build_hook_title_prompt,
    extract_hook_title_from_response,
)
from scripts.cut_json import cut_json_transcript
from scripts.adjust_subtitles import generate_ass_from_file, format_hook_title, HOOK_HEADER_STYLES
from webui.backend.schemas.jobs import JobRunRequest


def test_hook_title_in_process_segments():
    """Verify that process_segments extracts and normalizes hook_title, falling back to title."""
    transcript_segments = [
        {"start": 0.0, "end": 2.0, "text": "Halo semuanya selamat datang"},
        {"start": 2.0, "end": 5.0, "text": "hari ini kita belajar ai"},
        {"start": 5.0, "end": 10.0, "text": "sampai jumpa di video berikutnya"},
    ]
    raw_segments = [
        {
            "title": "Belajar AI Seru",
            "hook_title": "Rahasia Cuan Dari AI?!",
            "start_time_ref": "(0s)",
            "start_text": "Halo semuanya",
            "end_text": "belajar ai",
            "score": 90,
        },
        {
            "title": "Segmen Tanpa Hook Title",
            "start_time_ref": "(0s)",
            "start_text": "Halo semuanya",
            "end_text": "video berikutnya",
            "score": 80,
        },
    ]

    result = process_segments(raw_segments, transcript_segments, min_duration=3, max_duration=10)
    segs = result.get("segments", [])
    assert len(segs) >= 1

    # First segment should preserve custom hook_title in uppercase
    first = segs[0]
    assert first["hook_title"] == "RAHASIA CUAN DARI AI?!"

    # Second segment should fallback to title in uppercase
    if len(segs) > 1:
        second = segs[1]
        assert second["hook_title"] == "SEGMEN TANPA HOOK TITLE"


def test_format_hook_title_wrapping():
    """Verify word-wrapping helper for long hook titles."""
    short_title = "RAHASIA CUAN AI"
    assert format_hook_title(short_title) == short_title

    long_title = "JANGAN PERNAH LAKUKAN KESALAHAN FATAL INI SAAT MEMULAI BISNIS ONLINE"
    wrapped = format_hook_title(long_title, max_line_chars=24)
    assert "\\N" in wrapped
    parts = wrapped.split("\\N")
    assert len(parts) == 2
    assert "JANGAN" in parts[0]
    assert "ONLINE" in parts[1]


def test_cut_json_transcript_preserves_hook_title(tmp_path):
    """Verify that cut_json_transcript saves hook_title and title to output JSON."""
    input_json = tmp_path / "input.json"
    output_json = tmp_path / "output.json"

    data = {
        "segments": [
            {"start": 0.0, "end": 4.0, "text": "Hello world", "words": []},
            {"start": 4.0, "end": 8.0, "text": "Goodbye world", "words": []},
        ]
    }
    input_json.write_text(json.dumps(data), encoding="utf-8")

    cut_json_transcript(
        input_json_path=str(input_json),
        output_json_path=str(output_json),
        start_time=0.0,
        end_time=5.0,
        hook_title="STOP SCROLL SEKARANG!",
        title="Sample Title",
    )

    assert output_json.exists()
    saved = json.loads(output_json.read_text(encoding="utf-8"))
    assert saved.get("hook_title") == "STOP SCROLL SEKARANG!"
    assert saved.get("title") == "Sample Title"


def test_generate_ass_with_hook_header(tmp_path):
    """Verify that generate_ass_from_file injects HookHeader style and Dialogue event at t=0.0s."""
    input_json = tmp_path / "000_sample_processed.json"
    output_ass = tmp_path / "000_sample_processed.ass"

    data = {
        "hook_title": "RAHASIA CUAN DARI AI?!",
        "segments": [
            {
                "start": 0.0,
                "end": 6.5,
                "text": "Ini adalah video pendek tentang kecerdasan buatan.",
                "words": [
                    {"word": "Ini", "start": 0.0, "end": 0.5},
                    {"word": "adalah", "start": 0.5, "end": 1.0},
                    {"word": "video", "start": 1.0, "end": 1.5},
                    {"word": "pendek", "start": 1.5, "end": 2.5},
                    {"word": "tentang", "start": 2.5, "end": 3.5},
                    {"word": "kecerdasan", "start": 3.5, "end": 5.0},
                    {"word": "buatan.", "start": 5.0, "end": 6.5},
                ],
            }
        ],
    }
    input_json.write_text(json.dumps(data), encoding="utf-8")

    generate_ass_from_file(
        input_path=str(input_json),
        output_path=str(output_ass),
        project_folder=str(tmp_path),
        base_color="&H00FFFFFF",
        base_size=24,
        highlight_size=28,
        highlight_color="&H0000FF00",
        words_per_block=3,
        gap_limit=0.2,
        mode="highlight",
        vertical_position=150,
        alignment=2,
        font="Montserrat-ExtraBold",
        outline_color="&H00000000",
        shadow_color="&H00000000",
        bold=True,
        italic=False,
        underline=False,
        strikeout=False,
        border_style=1,
        outline_thickness=2,
        shadow_size=1,
        uppercase=False,
        enable_hook_header=True,
        hook_header_style="yellow_box",
        hook_font_size=22,
        hook_margin_v=40,
    )

    assert output_ass.exists()
    content = output_ass.read_text(encoding="utf-8")

    # 1. Verify HookHeader Style definition
    assert "Style: HookHeader" in content
    # Alignment: 8, BorderStyle: 3, MarginV: 40
    assert ",3,4,0,8,15,15,40,1" in content
    # Yellow primary color
    assert HOOK_HEADER_STYLES["yellow_box"]["primary"] in content

    # 2. Verify Dialogue line for HookHeader
    dialogues = [line for line in content.splitlines() if line.startswith("Dialogue:")]
    assert len(dialogues) >= 2

    hook_line = dialogues[0]
    assert "HookHeader" in hook_line
    assert "0:00:00.00" in hook_line
    assert "RAHASIA CUAN DARI AI?!" in hook_line


def test_generate_ass_with_disabled_hook_header(tmp_path):
    """Verify that when enable_hook_header=False, no HookHeader style or dialogue is emitted."""
    input_json = tmp_path / "000_sample_processed.json"
    output_ass = tmp_path / "000_sample_processed.ass"

    data = {
        "hook_title": "RAHASIA CUAN DARI AI?!",
        "segments": [
            {
                "start": 0.0,
                "end": 4.0,
                "text": "Subtitle biasa saja",
                "words": [{"word": "Subtitle", "start": 0.0, "end": 2.0}],
            }
        ],
    }
    input_json.write_text(json.dumps(data), encoding="utf-8")

    generate_ass_from_file(
        input_path=str(input_json),
        output_path=str(output_ass),
        project_folder=str(tmp_path),
        base_color="&H00FFFFFF",
        base_size=24,
        highlight_size=28,
        highlight_color="&H0000FF00",
        words_per_block=3,
        gap_limit=0.2,
        mode="highlight",
        vertical_position=150,
        alignment=2,
        font="Montserrat-ExtraBold",
        outline_color="&H00000000",
        shadow_color="&H00000000",
        bold=True,
        italic=False,
        underline=False,
        strikeout=False,
        border_style=1,
        outline_thickness=2,
        shadow_size=1,
        uppercase=False,
        enable_hook_header=False,
    )

    assert output_ass.exists()
    content = output_ass.read_text(encoding="utf-8")
    assert "Style: HookHeader" not in content
    assert "HookHeader" not in content


def test_job_schema_hook_header_cli_args():
    """Verify JobRunRequest CLI argument generation for hook header."""
    # Enabled (default)
    req_default = JobRunRequest(url="https://youtube.com/watch?v=abc")
    cmd_default = req_default.to_cli_args("python3", "main_improved.py")
    assert "--enable-hook-header" in cmd_default
    assert "--hook-header-style" in cmd_default
    assert cmd_default[cmd_default.index("--hook-header-style") + 1] == "yellow_box"

    # White box style
    req_white = JobRunRequest(url="https://youtube.com/watch?v=abc", hook_header_style="white_box")
    cmd_white = req_white.to_cli_args("python3", "main_improved.py")
    assert "--enable-hook-header" in cmd_white
    assert cmd_white[cmd_white.index("--hook-header-style") + 1] == "white_box"

    # Disabled
    req_disabled = JobRunRequest(url="https://youtube.com/watch?v=abc", enable_hook_header=False)
    cmd_disabled = req_disabled.to_cli_args("python3", "main_improved.py")
    assert "--no-enable-hook-header" in cmd_disabled
    assert "--enable-hook-header" not in cmd_disabled


def test_build_and_extract_hook_title_prompt():
    """Verify hook title prompt generation and LLM response extraction."""
    transcript = "Hari ini kita akan membahas trik rahasia menghasilkan uang dari kecerdasan buatan."
    prompt = build_hook_title_prompt(transcript, language_instruction="Indonesian")
    assert "Stop-the-Scroll" in prompt
    assert "ALL CAPS" in prompt
    assert "Indonesian" in prompt
    assert transcript in prompt

    # Test JSON extraction
    sample_json = '{"hook_title": "RAHASIA CUAN DARI AI?!"}'
    assert extract_hook_title_from_response(sample_json) == "RAHASIA CUAN DARI AI?!"

    # Test regex extraction on wrapped response
    wrapped_json = 'Berikut hasilnya:\n```json\n{"hook_title": "JANGAN LAKUKAN HAL INI!"}\n```'
    assert extract_hook_title_from_response(wrapped_json) == "JANGAN LAKUKAN HAL INI!"

    # Test fallback
    empty_resp = ""
    assert extract_hook_title_from_response(empty_resp, fallback="DEFAULT HOOK") == "DEFAULT HOOK"


def test_build_hook_title_prompt_contains_calibrated_frameworks():
    prompt = build_hook_title_prompt("sample transcript", language_instruction="Indonesian")
    assert "CALIBRATED HOOK FRAMEWORKS" in prompt
    assert "Curiosity Gap" in prompt
    assert "Negative Warning" in prompt
    assert "strictly 3 to 6 words" in prompt


def test_extract_hook_title_cleans_passive_fluff():
    # Test that passive fluff prefixes like "Tips Untuk..." are stripped or sanitized
    raw_fluffy = '{"hook_title": "TIPS UNTUK MENJADI KAYA SECARA CEPAT"}'
    cleaned = extract_hook_title_from_response(raw_fluffy)
    assert not cleaned.startswith("TIPS UNTUK ")
    assert len(cleaned.split()) <= 6


def test_extract_hook_title_limits_to_six_words():
    raw_long = '{"hook_title": "SATU DUA TIGA EMPAT LIMA ENAM TUJUH DELAPAN"}'
    cleaned = extract_hook_title_from_response(raw_long)
    assert len(cleaned.split()) <= 6
    assert cleaned == "SATU DUA TIGA EMPAT LIMA ENAM"


@pytest.mark.parametrize("fluff_prefix", [
    "TIPS UNTUK ",
    "TIPS ",
    "CARA CEPAT UNTUK ",
    "MEMBAHAS TENTANG ",
    "APAKAH ANDA TAHU ",
    "BAGAIMANA CARA ",
    "INILAH CARA ",
])
def test_extract_hook_title_all_banned_prefixes(fluff_prefix):
    raw = f'{{"hook_title": "{fluff_prefix}RAHASIA SUKSES BISNIS DIGITAL"}}'
    cleaned = extract_hook_title_from_response(raw)
    assert not cleaned.startswith(fluff_prefix)
    assert "RAHASIA SUKSES BISNIS DIGITAL" in cleaned

def test_smart_clipping_prompt_contains_rubric_and_hook():
    from scripts.smart_clipping import build_narrative_prompt, parse_narrative_topics
    prompt = build_narrative_prompt("sample transcript", target_min=20.0, target_max=60.0)
    assert "hook_strength" in prompt
    assert "retention_flow" in prompt
    assert "emotional_resonance" in prompt
    assert "shareability" in prompt
    assert "verdict" in prompt
    assert "hook_title" in prompt

    sample_resp = json.dumps({
        "topics": [{
            "title": "Topik Viral",
            "hook_title": "JANGAN BIKIN INI",
            "rationale": "High interest",
            "target_duration": 40.0,
            "score": 92,
            "rubric": {
                "hook_strength": 9.5,
                "retention_flow": 9.0,
                "emotional_resonance": 8.5,
                "shareability": 9.0,
                "verdict": "Great hook"
            },
            "segments": {
                "hook": {"start_time": 0.0, "end_time": 4.0, "text": "Hook text"},
                "core": {"start_time": 5.0, "end_time": 25.0, "text": "Core text"},
                "payoff": {"start_time": 26.0, "end_time": 35.0, "text": "Payoff text"}
            }
        }]
    })
    topics = parse_narrative_topics(sample_resp)
    assert len(topics) == 1
    assert topics[0]["hook_title"] == "JANGAN BIKIN INI"
    assert topics[0]["rubric"]["hook_strength"] == 9.5

def test_generate_ass_hook_duration_custom(tmp_path):
    """Verify that hook header respects custom hook_duration parameter and JSON hook_duration."""
    input_json = tmp_path / "custom_dur.json"
    output_ass = tmp_path / "custom_dur.ass"

    data = {
        "hook_title": "HOOK 3 DETIK SAJA",
        "hook_duration": 3.0,
        "segments": [
            {
                "start": 0.0,
                "end": 10.0,
                "text": "Total klip sepuluh detik",
                "words": [{"word": "Total", "start": 0.0, "end": 1.0}],
            }
        ],
    }
    input_json.write_text(json.dumps(data), encoding="utf-8")

    generate_ass_from_file(
        input_path=str(input_json),
        output_path=str(output_ass),
        project_folder=str(tmp_path),
        base_color="&H00FFFFFF",
        base_size=24,
        highlight_size=28,
        highlight_color="&H0000FF00",
        words_per_block=3,
        gap_limit=0.2,
        mode="highlight",
        vertical_position=150,
        alignment=2,
        font="Roboto-Bold",
        outline_color="&H00000000",
        shadow_color="&H00000000",
        bold=True,
        italic=False,
        underline=False,
        strikeout=False,
        border_style=1,
        outline_thickness=2,
        shadow_size=1,
        uppercase=False,
        enable_hook_header=True,
        hook_duration=4.5,  # Explicit override
    )

    content = output_ass.read_text(encoding="utf-8")
    dialogues = [line for line in content.splitlines() if line.startswith("Dialogue:")]
    hook_line = dialogues[0]
    assert "HookHeader" in hook_line
    assert "0:00:00.00" in hook_line
    # 4.5s format is 0:00:04.50
    assert "0:00:04.50" in hook_line
    assert "HOOK 3 DETIK SAJA" in hook_line


def test_generate_ass_style_presets(tmp_path):
    """Verify ASS output for white_box and neon styling presets."""
    input_json = tmp_path / "styles.json"
    data = {
        "hook_title": "STYLE TEST",
        "segments": [{"start": 0.0, "end": 2.0, "text": "test", "words": []}],
    }
    input_json.write_text(json.dumps(data), encoding="utf-8")

    # 1. White box
    out_white = tmp_path / "white.ass"
    generate_ass_from_file(
        input_path=str(input_json),
        output_path=str(out_white),
        project_folder=str(tmp_path),
        base_color="&H00FFFFFF",
        base_size=24,
        highlight_size=28,
        highlight_color="&H0000FF00",
        words_per_block=3,
        gap_limit=0.2,
        mode="highlight",
        vertical_position=150,
        alignment=2,
        font="Roboto-Bold",
        outline_color="&H00000000",
        shadow_color="&H00000000",
        bold=True,
        italic=False,
        underline=False,
        strikeout=False,
        border_style=1,
        outline_thickness=2,
        shadow_size=1,
        uppercase=False,
        enable_hook_header=True,
        hook_header_style="white_box",
    )
    white_content = out_white.read_text(encoding="utf-8")
    assert f"Style: HookHeader,Roboto Bold,22,{HOOK_HEADER_STYLES['white_box']['primary']}" in white_content

    # 2. Neon box
    out_neon = tmp_path / "neon.ass"
    generate_ass_from_file(
        input_path=str(input_json),
        output_path=str(out_neon),
        project_folder=str(tmp_path),
        base_color="&H00FFFFFF",
        base_size=24,
        highlight_size=28,
        highlight_color="&H0000FF00",
        words_per_block=3,
        gap_limit=0.2,
        mode="highlight",
        vertical_position=150,
        alignment=2,
        font="Roboto-Bold",
        outline_color="&H00000000",
        shadow_color="&H00000000",
        bold=True,
        italic=False,
        underline=False,
        strikeout=False,
        border_style=1,
        outline_thickness=2,
        shadow_size=1,
        uppercase=False,
        enable_hook_header=True,
        hook_header_style="neon",
    )
    neon_content = out_neon.read_text(encoding="utf-8")
    assert f"Style: HookHeader,Roboto Bold,22,{HOOK_HEADER_STYLES['neon']['primary']}" in neon_content

