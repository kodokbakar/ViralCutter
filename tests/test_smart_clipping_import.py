import sys
from unittest.mock import MagicMock
import pytest

import main_improved
from scripts import smart_clipping, gaming_scorer


def test_main_scope_does_not_shadow_smart_clipping():
    """
    Ensure smart_clipping is loaded from module scope and not shadowed as a local
    variable within main(), preventing UnboundLocalError across any execution branch.
    """
    assert "smart_clipping" not in main_improved.main.__code__.co_varnames
    assert "smart_clipping" in main_improved.__dict__
    assert main_improved.__dict__["smart_clipping"] is smart_clipping


def test_smart_clipping_podcast_pipeline_no_unbound_local(tmp_path, monkeypatch, capsys):
    """
    Regression test: verify running main() with --smart-clipping in podcast mode
    does not raise UnboundLocalError for smart_clipping due to local shadowing.
    """
    project_dir = tmp_path / "proj_smart_clipping_podcast"
    project_dir.mkdir()
    (project_dir / "input.mp4").write_bytes(b"dummy video")

    test_argv = [
        "main_improved.py",
        "--project-path", str(project_dir),
        "--pipeline-mode", "podcast",
        "--smart-clipping",
        "--skip-prompts",
        "--workflow", "2",
    ]
    monkeypatch.setattr(sys, "argv", test_argv)

    monkeypatch.setattr(
        "scripts.transcribe_video.transcribe",
        lambda *args, **kwargs: ("dummy.srt", "dummy.tsv"),
    )
    monkeypatch.setattr(
        "scripts.cut_segments.cut",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(
        "scripts.refine_segments.refine_to_sentence_boundaries",
        lambda segs, *args, **kwargs: segs,
    )

    mock_run_smart_clipping = MagicMock(
        return_value={"segments": [{"start": 0.0, "end": 10.0, "duration": 10.0}]}
    )
    monkeypatch.setattr(
        smart_clipping,
        "run_smart_clipping_pipeline",
        mock_run_smart_clipping,
    )

    with pytest.raises(SystemExit) as exc_info:
        main_improved.main()

    captured = capsys.readouterr()
    assert "UnboundLocalError" not in captured.err
    assert exc_info.value.code == 0
    assert mock_run_smart_clipping.called


def test_smart_clipping_default_mode_no_unbound_local(tmp_path, monkeypatch, capsys):
    """
    Verify running main() with --smart-clipping and default pipeline mode (omitted flag)
    correctly routes to smart_clipping pipeline without UnboundLocalError.
    """
    project_dir = tmp_path / "proj_smart_clipping_default"
    project_dir.mkdir()
    (project_dir / "input.mp4").write_bytes(b"dummy video")

    test_argv = [
        "main_improved.py",
        "--project-path", str(project_dir),
        "--smart-clipping",
        "--skip-prompts",
        "--workflow", "2",
    ]
    monkeypatch.setattr(sys, "argv", test_argv)

    monkeypatch.setattr(
        "scripts.transcribe_video.transcribe",
        lambda *args, **kwargs: ("dummy.srt", "dummy.tsv"),
    )
    monkeypatch.setattr(
        "scripts.cut_segments.cut",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(
        "scripts.refine_segments.refine_to_sentence_boundaries",
        lambda segs, *args, **kwargs: segs,
    )

    mock_run_smart_clipping = MagicMock(
        return_value={"segments": [{"start": 0.0, "end": 10.0, "duration": 10.0}]}
    )
    monkeypatch.setattr(
        smart_clipping,
        "run_smart_clipping_pipeline",
        mock_run_smart_clipping,
    )

    with pytest.raises(SystemExit) as exc_info:
        main_improved.main()

    captured = capsys.readouterr()
    assert "UnboundLocalError" not in captured.err
    assert exc_info.value.code == 0
    assert mock_run_smart_clipping.called


def test_smart_clipping_gaming_pipeline_access(tmp_path, monkeypatch, capsys):
    """
    Verify gaming pipeline mode correctly accesses smart_clipping module utilities
    (extract_words_from_transcript) and completes without UnboundLocalError, even
    if --smart-clipping is also passed.
    """
    project_dir = tmp_path / "proj_smart_clipping_gaming"
    project_dir.mkdir()
    (project_dir / "input.mp4").write_bytes(b"dummy video")

    test_argv = [
        "main_improved.py",
        "--project-path", str(project_dir),
        "--pipeline-mode", "gaming",
        "--smart-clipping",
        "--skip-prompts",
        "--workflow", "2",
    ]
    monkeypatch.setattr(sys, "argv", test_argv)

    monkeypatch.setattr(
        "scripts.transcribe_video.transcribe",
        lambda *args, **kwargs: ("dummy.srt", "dummy.tsv"),
    )
    monkeypatch.setattr(
        "scripts.transcribe_video.get_audio_duration",
        lambda *args, **kwargs: 20.0,
    )
    monkeypatch.setattr(
        "scripts.cut_segments.cut",
        lambda *args, **kwargs: None,
    )

    mock_extract_words = MagicMock(
        return_value=[{"word": "victory", "start": 1.0, "end": 2.0}]
    )
    monkeypatch.setattr(
        smart_clipping,
        "extract_words_from_transcript",
        mock_extract_words,
    )

    mock_gaming_pipeline = MagicMock(
        return_value={
            "segments": [
                {
                    "start_time": 0.0,
                    "end_time": 10.0,
                    "duration": 10.0,
                    "score": 90,
                    "title": "CLUTCH",
                    "hook_title": "CLUTCH",
                    "rubric": {"audio_dynamics": 9.0, "hook_strength": 9.0},
                }
            ]
        }
    )
    monkeypatch.setattr(
        gaming_scorer,
        "run_gaming_clipping_pipeline",
        mock_gaming_pipeline,
    )

    with pytest.raises(SystemExit) as exc_info:
        main_improved.main()

    captured = capsys.readouterr()
    assert "UnboundLocalError" not in captured.err
    assert exc_info.value.code == 0
    assert mock_extract_words.called
    assert mock_gaming_pipeline.called
