import sys
from unittest.mock import MagicMock
import pytest

import main_improved
from scripts import smart_clipping


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
