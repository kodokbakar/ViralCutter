import pytest
from pathlib import Path
from webui.backend.api.v1.library import _get_project_clips_sync

def test_get_project_clips_sync_burned_sub_only(tmp_path: Path):
    proj_dir = tmp_path / "test_proj"
    proj_dir.mkdir()

    # Create final/ with a video
    final_dir = proj_dir / "final"
    final_dir.mkdir()
    (final_dir / "final_output.mp4").write_bytes(b"dummy")

    # Create cuts/ with a video
    cuts_dir = proj_dir / "cuts"
    cuts_dir.mkdir()
    (cuts_dir / "cut_output.mp4").write_bytes(b"dummy")

    # When burned_sub/ does NOT exist, it must return [] (no fallback to final/)
    clips_no_burned = _get_project_clips_sync(proj_dir)
    assert clips_no_burned == []

    # Now create burned_sub/ with videos
    burned_dir = proj_dir / "burned_sub"
    burned_dir.mkdir()
    (burned_dir / "burned_001.mp4").write_bytes(b"dummy")
    (burned_dir / "burned_002.mp4").write_bytes(b"dummy")

    clips_burned = _get_project_clips_sync(proj_dir)
    assert len(clips_burned) == 2
    names = [c.name for c in clips_burned]
    assert "burned_001.mp4" in names
    assert "burned_002.mp4" in names
    for c in clips_burned:
        assert c.folder_type == "burned_sub"
        assert "burned_sub" in c.path
