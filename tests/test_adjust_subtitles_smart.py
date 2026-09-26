import json
import os
import pytest
from scripts.adjust_subtitles import generate_ass_from_file

def test_generate_ass_overlap_and_smart_splitting(tmp_path):
    input_json = tmp_path / "test_subs.json"
    output_ass = tmp_path / "output.ass"

    # Simulated transcript with an overlap and punctuation
    raw_data = {
        "segments": [
            {
                "start": 1.0,
                "end": 5.0,
                "text": "Halo semuanya! Hari ini kita mulai proyek baru.",
                "words": [
                    {"word": "Halo", "start": 1.0, "end": 1.4},
                    {"word": "semuanya!", "start": 1.45, "end": 2.0}, # End of clause
                    {"word": "Hari", "start": 2.4, "end": 2.7},       # Start of new clause after pause
                    {"word": "ini", "start": 2.65, "end": 3.0},       # Overlap with 'Hari' (2.65 < 2.7)
                    {"word": "kita", "start": 3.0, "end": 3.3},
                    {"word": "mulai", "start": 3.3, "end": 3.6},
                    {"word": "proyek", "start": 3.6, "end": 4.0},
                    {"word": "baru.", "start": 4.0, "end": 4.5}
                ]
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
        remove_punctuation=False
    )

    assert output_ass.exists()
    content = output_ass.read_text(encoding="utf-8")
    lines = [l for l in content.splitlines() if l.startswith("Dialogue:")]
    assert len(lines) > 0

    # Verify no line has negative or reversed start/end duration
    for line in lines:
        parts = line.split(",")
        start = parts[1]
        end = parts[2]
        # start and end in format H:MM:SS.cs
        assert start <= end
