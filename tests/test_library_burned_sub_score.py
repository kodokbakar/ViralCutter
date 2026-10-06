import json
import pytest
from pathlib import Path
from webui.backend.api.v1.library import _get_project_clips_sync

def test_get_project_clips_sync_resolves_score_robustly(tmp_path: Path):
    proj_dir = tmp_path / "test_proj"
    proj_dir.mkdir()

    # Create burned_sub/ with standard burned video files
    burned_dir = proj_dir / "burned_sub"
    burned_dir.mkdir()
    (burned_dir / "000_Viral_Hook_processed_subtitled.mp4").write_bytes(b"video content")
    (burned_dir / "001_Second_Topic_processed_subtitled.mp4").write_bytes(b"video content")

    # Create viral_segments.txt with scores
    segments_data = {
        "segments": [
            {
                "title": "Viral Hook Title",
                "score": 94,
                "duration": 32.5,
                "start_time": 10.0,
                "end_time": 42.5
            },
            {
                "title": "Second Topic Title",
                "score": "88",
                "duration": 40.0,
                "start_time": 50.0,
                "end_time": 90.0
            }
        ]
    }
    (proj_dir / "viral_segments.txt").write_text(json.dumps(segments_data), encoding="utf-8")

    clips = _get_project_clips_sync(proj_dir)
    assert len(clips) == 2
    assert clips[0].score == 94.0
    assert clips[0].hook_title == "Viral Hook Title"
    assert clips[1].score == 88.0
    assert clips[1].hook_title == "Second Topic Title"
