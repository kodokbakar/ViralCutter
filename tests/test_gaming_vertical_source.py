import json
import os
import sys
import pytest
from unittest.mock import patch, MagicMock

import main_improved
from scripts.gaming_split import is_vertical_video


def test_is_vertical_video_true():
    with patch("scripts.gaming_split.probe_video_dimensions", return_value=(1080, 1920)):
        assert is_vertical_video("vertical.mp4") is True


def test_is_vertical_video_false_for_horizontal():
    with patch("scripts.gaming_split.probe_video_dimensions", return_value=(1920, 1080)):
        assert is_vertical_video("horizontal.mp4") is False


def test_is_vertical_video_false_for_square():
    with patch("scripts.gaming_split.probe_video_dimensions", return_value=(1080, 1080)):
        assert is_vertical_video("square.mp4") is False


def test_is_vertical_video_missing_file():
    assert is_vertical_video("non_existent_file.mp4") is False


def test_is_vertical_video_invalid_inputs():
    assert is_vertical_video("") is False
    assert is_vertical_video(None) is False
    assert is_vertical_video(123) is False
    assert is_vertical_video(["path.mp4"]) is False


def test_is_vertical_video_zero_or_negative_dimensions():
    with patch("scripts.gaming_split.probe_video_dimensions", return_value=(0, 0)):
        assert is_vertical_video("video.mp4") is False
    with patch("scripts.gaming_split.probe_video_dimensions", return_value=(0, 1920)):
        assert is_vertical_video("video.mp4") is False
    with patch("scripts.gaming_split.probe_video_dimensions", return_value=(-1080, 1920)):
        assert is_vertical_video("video.mp4") is False
    with patch("scripts.gaming_split.probe_video_dimensions", return_value=(1080, -1920)):
        assert is_vertical_video("video.mp4") is False


def test_main_improved_vertical_source_gaming_bypass(tmp_path, monkeypatch, capsys):
    project_dir = tmp_path / "proj_vertical"
    project_dir.mkdir()
    input_file = project_dir / "input.mp4"
    input_file.write_bytes(b"dummy")

    cuts_dir = project_dir / "cuts"
    cuts_dir.mkdir()
    cut_file = cuts_dir / "000_original_scale.mp4"
    cut_file.write_bytes(b"cut content")

    viral_seg = {
        "segments": [
            {"start_time": 0.0, "end_time": 10.0, "duration": 10.0, "title": "Seg 1"}
        ]
    }

    test_args = [
        "main_improved.py",
        "--project-path", str(project_dir),
        "--pipeline-mode", "gaming",
        "--skip-prompts",
        "--workflow", "1",
    ]
    monkeypatch.setattr("sys.argv", test_args)

    # Patch is_vertical_video to return True
    monkeypatch.setattr("scripts.gaming_split.is_vertical_video", lambda p: True)

    mock_preserve = MagicMock()
    mock_render_split = MagicMock()
    monkeypatch.setattr("scripts.preserve_segments.preserve_original_scale", mock_preserve)
    monkeypatch.setattr("scripts.gaming_split.render_gaming_split_clip", mock_render_split)
    monkeypatch.setattr("scripts.cut_segments.cut", lambda *a, **kw: None)
    monkeypatch.setattr("scripts.transcribe_video.transcribe", lambda *a, **kw: ("d.srt", "d.tsv"))
    monkeypatch.setattr("scripts.gaming_scorer.run_gaming_clipping_pipeline", lambda **kw: viral_seg)
    monkeypatch.setattr("scripts.adjust_subtitles.adjust", lambda *a, **kw: None)
    monkeypatch.setattr("scripts.burn_subtitles.burn", lambda *a, **kw: None)

    main_improved.main()

    # Verify preserve_original_scale was called, gaming split was NOT called
    assert mock_preserve.called
    assert not mock_render_split.called

    captured = capsys.readouterr().out
    assert "Source video is already vertical (portrait). Preserving original framing without gaming split..." in captured
    assert "Preserving original source framing..." in captured


def test_main_improved_horizontal_source_gaming_split_runs(tmp_path, monkeypatch, capsys):
    project_dir = tmp_path / "proj_horizontal"
    project_dir.mkdir()
    input_file = project_dir / "input.mp4"
    input_file.write_bytes(b"dummy")

    cuts_dir = project_dir / "cuts"
    cuts_dir.mkdir()
    cut_file = cuts_dir / "000_original_scale.mp4"
    cut_file.write_bytes(b"cut content")

    viral_seg = {
        "segments": [
            {"start_time": 0.0, "end_time": 10.0, "duration": 10.0, "title": "Seg 1"}
        ]
    }

    test_args = [
        "main_improved.py",
        "--project-path", str(project_dir),
        "--pipeline-mode", "gaming",
        "--skip-prompts",
        "--workflow", "1",
    ]
    monkeypatch.setattr("sys.argv", test_args)

    # Patch is_vertical_video to return False
    monkeypatch.setattr("scripts.gaming_split.is_vertical_video", lambda p: False)

    mock_preserve = MagicMock()
    mock_render_split = MagicMock()
    monkeypatch.setattr("scripts.preserve_segments.preserve_original_scale", mock_preserve)
    monkeypatch.setattr("scripts.gaming_split.render_gaming_split_clip", mock_render_split)
    monkeypatch.setattr("scripts.cut_segments.cut", lambda *a, **kw: None)
    monkeypatch.setattr("scripts.transcribe_video.transcribe", lambda *a, **kw: ("d.srt", "d.tsv"))
    monkeypatch.setattr("scripts.gaming_scorer.run_gaming_clipping_pipeline", lambda **kw: viral_seg)
    monkeypatch.setattr("scripts.adjust_subtitles.adjust", lambda *a, **kw: None)
    monkeypatch.setattr("scripts.burn_subtitles.burn", lambda *a, **kw: None)

    main_improved.main()

    # Verify gaming split was called, preserve_original_scale was NOT called
    assert mock_render_split.called
    assert not mock_preserve.called

    captured = capsys.readouterr().out
    assert "Gaming Split framing mode selected" in captured
