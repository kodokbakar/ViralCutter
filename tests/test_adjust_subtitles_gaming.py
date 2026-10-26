import json
import pytest
from scripts.adjust_subtitles import generate_ass_from_file


def test_adjust_subtitles_gaming_split_mid_seam_position(tmp_path):
    input_json = tmp_path / "output000_processed.json"
    output_ass = tmp_path / "output000.ass"

    raw_data = {
        "segments": [
            {
                "start": 0.0,
                "end": 3.0,
                "text": "Clutch moment here",
                "words": [
                    {"word": "Clutch", "start": 0.0, "end": 1.0},
                    {"word": "moment", "start": 1.0, "end": 2.0},
                    {"word": "here", "start": 2.0, "end": 3.0},
                ],
            }
        ]
    }
    input_json.write_text(json.dumps(raw_data), encoding="utf-8")

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
        vertical_position=210,
        alignment=2,
        font="Arial",
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
        face_modes={},
        layout_mode="9:16_gaming_split",
    )

    assert output_ass.exists()
    content = output_ass.read_text(encoding="utf-8")
    style_lines = [l for l in content.splitlines() if l.startswith("Style: Default")]
    assert len(style_lines) == 1
    # Style: Default,Fontname,Fontsize,...,Alignment,MarginL,MarginR,MarginV,Encoding
    parts = style_lines[0].split(",")
    # Alignment is 2nd from last, MarginV is 1st before Encoding
    alignment_field = parts[-5]
    margin_v_field = parts[-2]
    assert alignment_field == "2"
    assert margin_v_field == "400"


def test_adjust_subtitles_face_modes_gaming_split(tmp_path):
    input_json = tmp_path / "output001_processed.json"
    output_ass = tmp_path / "output001.ass"

    raw_data = {
        "segments": [
            {
                "start": 0.0,
                "end": 2.0,
                "text": "Nice play",
                "words": [
                    {"word": "Nice", "start": 0.0, "end": 1.0},
                    {"word": "play", "start": 1.0, "end": 2.0},
                ],
            }
        ]
    }
    input_json.write_text(json.dumps(raw_data), encoding="utf-8")

    generate_ass_from_file(
        input_path=str(input_json),
        output_path=str(output_ass),
        project_folder=str(tmp_path),
        base_color="&H00FFFFFF",
        base_size=24,
        highlight_size=28,
        highlight_color="&H0000FF00",
        words_per_block=2,
        gap_limit=0.2,
        mode="highlight",
        vertical_position=210,
        alignment=2,
        font="Arial",
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
        face_modes={"output001": "gaming_split"},
    )

    assert output_ass.exists()
    content = output_ass.read_text(encoding="utf-8")
    style_lines = [l for l in content.splitlines() if l.startswith("Style: Default")]
    parts = style_lines[0].split(",")
    alignment_field = parts[-5]
    margin_v_field = parts[-2]
    assert alignment_field == "2"
    assert margin_v_field == "400"


def test_adjust_subtitles_non_gaming_retains_default(tmp_path):
    input_json = tmp_path / "output002_processed.json"
    output_ass = tmp_path / "output002.ass"

    raw_data = {
        "segments": [
            {
                "start": 0.0,
                "end": 2.0,
                "text": "Podcast dialogue",
                "words": [
                    {"word": "Podcast", "start": 0.0, "end": 1.0},
                    {"word": "dialogue", "start": 1.0, "end": 2.0},
                ],
            }
        ]
    }
    input_json.write_text(json.dumps(raw_data), encoding="utf-8")

    generate_ass_from_file(
        input_path=str(input_json),
        output_path=str(output_ass),
        project_folder=str(tmp_path),
        base_color="&H00FFFFFF",
        base_size=24,
        highlight_size=28,
        highlight_color="&H0000FF00",
        words_per_block=2,
        gap_limit=0.2,
        mode="highlight",
        vertical_position=180,
        alignment=2,
        font="Arial",
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
        face_modes={},
    )

    assert output_ass.exists()
    content = output_ass.read_text(encoding="utf-8")
    style_lines = [l for l in content.splitlines() if l.startswith("Style: Default")]
    parts = style_lines[0].split(",")
    margin_v_field = parts[-2]
    assert margin_v_field == "180"


def test_adjust_subtitles_face_mode_2_static_override(tmp_path):
    # Mode 2 without timeline forces center alignment 5, vertical position 0
    input_json = tmp_path / "output003_processed.json"
    output_ass = tmp_path / "output003.ass"

    raw_data = {
        "segments": [
            {
                "start": 0.0,
                "end": 2.0,
                "text": "Two speakers",
                "words": [{"word": "Two", "start": 0.0, "end": 1.0}, {"word": "speakers", "start": 1.0, "end": 2.0}],
            }
        ]
    }
    input_json.write_text(json.dumps(raw_data), encoding="utf-8")

    generate_ass_from_file(
        input_path=str(input_json),
        output_path=str(output_ass),
        project_folder=str(tmp_path),
        base_color="&H00FFFFFF",
        base_size=24,
        highlight_size=28,
        highlight_color="&H0000FF00",
        words_per_block=2,
        gap_limit=0.2,
        mode="highlight",
        vertical_position=210,
        alignment=2,
        font="Arial",
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
        face_modes={"output003": "2"},
    )

    assert output_ass.exists()
    content = output_ass.read_text(encoding="utf-8")
    style_lines = [l for l in content.splitlines() if l.startswith("Style: Default")]
    parts = style_lines[0].split(",")
    alignment_field = parts[-5]
    margin_v_field = parts[-2]
    # Verifies the line 230 fix: current_alignment (5) and current_vertical_position (0) are written
    assert alignment_field == "5"
    assert margin_v_field == "0"


def test_adjust_subtitles_podcast_various_alignments_no_regression(tmp_path):
    # Verifies standard podcast modes (1 face, none, custom alignments) do NOT regress to mid-seam
    for idx, (face_mode_val, req_align, req_margin) in enumerate([
        ("1", 2, 210),
        ("none", 2, 210),
        (None, 8, 160),
        ("auto", 2, 190),
    ]):
        in_json = tmp_path / f"podcast_{idx}.json"
        out_ass = tmp_path / f"podcast_{idx}.ass"
        in_json.write_text(json.dumps({
            "segments": [{
                "start": 0.0,
                "end": 1.0,
                "text": "Podcast speaker",
                "words": [{"word": "Podcast", "start": 0.0, "end": 0.5}, {"word": "speaker", "start": 0.5, "end": 1.0}],
            }]
        }), encoding="utf-8")

        f_modes = {f"output{idx:03d}": face_mode_val} if face_mode_val else {}
        generate_ass_from_file(
            input_path=str(in_json),
            output_path=str(out_ass),
            project_folder=str(tmp_path),
            base_color="&H00FFFFFF",
            base_size=24,
            highlight_size=28,
            highlight_color="&H0000FF00",
            words_per_block=2,
            gap_limit=0.2,
            mode="highlight",
            vertical_position=req_margin,
            alignment=req_align,
            font="Arial",
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
            face_modes=f_modes,
            layout_mode="",
        )

        assert out_ass.exists()
        content = out_ass.read_text(encoding="utf-8")
        style_line = next(l for l in content.splitlines() if l.startswith("Style: Default"))
        parts = style_line.split(",")
        assert parts[-5] == str(req_align)
        assert parts[-2] == str(req_margin)
