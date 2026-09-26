import pytest
from scripts import subtitle_fonts
from scripts.adjust_subtitles import generate_ass_from_file

def test_resolve_font_ass_name():
    for font_id in ["montserrat_extrabold", "poppins_extrabold", "roboto_bold", "barlow_semibold", "anton_regular"]:
        entry = subtitle_fonts.resolve_font(font_id)
        assert "ass_name" in entry
        assert entry["ass_name"] in [
            "Montserrat ExtraBold",
            "Poppins ExtraBold",
            "Roboto Bold",
            "Barlow SemiBold",
            "Anton"
        ]

def test_generate_ass_writes_exact_ass_name(tmp_path):
    input_json = tmp_path / "subs.json"
    input_json.write_text('{"segments": [{"start": 0, "end": 1, "words": [{"word": "Hi", "start": 0, "end": 1}]}]}', encoding="utf-8")
    
    for font_id, expected_ass_name in [
        ("montserrat_extrabold", "Montserrat ExtraBold"),
        ("poppins_extrabold", "Poppins ExtraBold"),
        ("barlow_semibold", "Barlow SemiBold"),
        ("roboto_bold", "Roboto Bold"),
        ("anton_regular", "Anton")
    ]:
        out_ass = tmp_path / f"out_{font_id}.ass"
        generate_ass_from_file(
            input_path=str(input_json),
            output_path=str(out_ass),
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
            font=font_id,
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
            remove_punctuation=False
        )
        content = out_ass.read_text(encoding="utf-8")
        assert f"Style: Default,{expected_ass_name}," in content
