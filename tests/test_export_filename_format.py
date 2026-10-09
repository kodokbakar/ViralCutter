import re
import pytest
from pathlib import Path
from webui.backend.api.v1.library import _get_project_clips_sync

def test_export_filename_format_pattern():
    # Format: nomor_ai score_judul.mp4 (e.g. 001_95_Viral_Hook_Title.mp4)
    pattern = r"^(\d{3})_(\d+)_([A-Za-z0-9_]+)\.mp4$"
    sample = "001_95_Rahasia_Sukses_Bisnis.mp4"
    match = re.match(pattern, sample)
    assert match is not None
    assert match.group(1) == "001"
    assert match.group(2) == "95"
    assert match.group(3) == "Rahasia_Sukses_Bisnis"

def test_get_project_clips_sync_extracts_score_from_filename(tmp_path: Path):
    proj_dir = tmp_path / "test_proj"
    proj_dir.mkdir()

    burned_dir = proj_dir / "burned_sub"
    burned_dir.mkdir()
    (burned_dir / "001_95_Rahasia_Sukses.mp4").write_bytes(b"dummy")
    (burned_dir / "002_88_Tips_Investasi.mp4").write_bytes(b"dummy")

    clips = _get_project_clips_sync(proj_dir)
    assert len(clips) == 2
    assert clips[0].name == "001_95_Rahasia_Sukses.mp4"
    assert clips[0].score == 95.0
    assert clips[0].hook_title == "Rahasia Sukses"

    assert clips[1].name == "002_88_Tips_Investasi.mp4"
    assert clips[1].score == 88.0
    assert clips[1].hook_title == "Tips Investasi"
