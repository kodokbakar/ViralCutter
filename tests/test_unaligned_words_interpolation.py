import json
import pytest
from pathlib import Path
from scripts.adjust_subtitles import generate_ass_from_file

def test_generate_ass_preserves_numbers_with_none_timestamps(tmp_path: Path):
    input_json = tmp_path / "subs_with_numbers.json"
    output_ass = tmp_path / "output.ass"

    # Transcript where Wav2Vec2 couldn't align the digits "500" and "2024"
    data = {
        "segments": [
            {
                "start": 1.0,
                "end": 5.0,
                "text": "Pada tahun 2024 ada 500 orang hadir.",
                "words": [
                    {"word": "Pada", "start": 1.0, "end": 1.3},
                    {"word": "tahun", "start": 1.3, "end": 1.7},
                    # "2024" unaligned by Wav2Vec2 (start/end None or missing)
                    {"word": "2024", "start": None, "end": None},
                    {"word": "ada", "start": 2.5, "end": 2.8},
                    # "500" unaligned by Wav2Vec2
                    {"word": "500"},
                    {"word": "orang", "start": 3.6, "end": 4.0},
                    {"word": "hadir.", "start": 4.1, "end": 4.6}
                ]
            }
        ]
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
        words_per_block=4,
        gap_limit=0.2,
        mode="highlight",
        vertical_position=150,
        alignment=2,
        font="Montserrat ExtraBold",
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

    assert output_ass.exists()
    content = output_ass.read_text(encoding="utf-8")
    dialogue_lines = [l for l in content.splitlines() if l.startswith("Dialogue:")]
    assert len(dialogue_lines) > 0
    full_sub_text = " ".join(dialogue_lines)

    # Numbers MUST be present in the subtitles!
    assert "2024" in full_sub_text, f"Number 2024 was dropped! Output: {full_sub_text}"
    assert "500" in full_sub_text, f"Number 500 was dropped! Output: {full_sub_text}"
