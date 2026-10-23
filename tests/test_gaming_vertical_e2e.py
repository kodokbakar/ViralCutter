import json
import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

import main_improved
from scripts import gaming_split
from scripts.gaming_split import is_vertical_video, probe_video_dimensions


def _create_synthetic_vertical_video(video_path: Path, duration: int = 5) -> None:
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-i",
            f"testsrc=size=1080x1920:rate=30",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=1000:sample_rate=16000",
            "-t",
            str(duration),
            "-preset",
            "ultrafast",
            "-c:v",
            "libx264",
            "-c:a",
            "aac",
            str(video_path),
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=True,
    )


def _setup_mock_environment(monkeypatch, project_dir: Path) -> MagicMock:
    """Sets up mock transcription, audio/face detector, and software encoder fallback."""
    orig_subprocess_run = subprocess.run

    def safe_subprocess_run(cmd, *args, **kwargs):
        # Force fallback to libx264 when encoders are checked so test runs on all environments
        if (
            isinstance(cmd, list)
            and len(cmd) >= 2
            and cmd[0] == "ffmpeg"
            and cmd[1] == "-encoders"
        ):
            res = orig_subprocess_run(cmd, *args, **kwargs)
            res.stdout = res.stdout.replace("h264_nvenc", "disabled_nvenc")
            return res
        return orig_subprocess_run(cmd, *args, **kwargs)

    monkeypatch.setattr(subprocess, "run", safe_subprocess_run)

    mock_render_split = MagicMock(wraps=gaming_split.render_gaming_split_clip)
    monkeypatch.setattr("scripts.gaming_split.render_gaming_split_clip", mock_render_split)

    monkeypatch.setattr(
        "scripts.transcribe_video.transcribe",
        lambda *args, **kwargs: ("dummy.srt", "dummy.tsv"),
    )
    monkeypatch.setattr(
        "scripts.transcribe_video.get_audio_duration",
        lambda *args, **kwargs: 5.0,
    )
    monkeypatch.setattr(
        "scripts.gaming_scorer.gaming_audio_detector.extract_audio_rms_curve",
        lambda *args, **kwargs: ([10.0] * 20 + [90.0] * 10 + [10.0] * 20, 15.0, 10.0),
    )
    monkeypatch.setattr(
        "scripts.gaming_scorer.gaming_facecam_detector.detect_facecam_reactions",
        lambda *args, **kwargs: [{"timestamp": 2.5, "score": 85.0, "reaction": "mouth_open"}],
    )

    transcript = {
        "segments": [
            {
                "start": 0.0,
                "end": 5.0,
                "words": [
                    {"word": "halo", "start": 0.5, "end": 1.0},
                    {"word": "clutch", "start": 1.5, "end": 2.5},
                    {"word": "gg", "start": 3.0, "end": 3.8},
                ],
            }
        ]
    }
    (project_dir / "input.json").write_text(json.dumps(transcript), encoding="utf-8")

    return mock_render_split


def test_vertical_video_pipeline_e2e_preserves_dimensions(tmp_path):
    """
    Step 1 specification test:
    Generates a synthetic 5-second 1080x1920 vertical video via ffmpeg testsrc
    and validates dimension probing and vertical classification.
    """
    video_path = tmp_path / "vertical_test.mp4"
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "testsrc=size=1080x1920:rate=30",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=1000:sample_rate=16000",
            "-t",
            "5",
            "-c:v",
            "libx264",
            "-c:a",
            "aac",
            str(video_path),
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=True,
    )

    assert is_vertical_video(str(video_path)) is True
    w, h = probe_video_dimensions(str(video_path))
    assert w == 1080
    assert h == 1920


def test_vertical_video_pipeline_e2e_workflow_2_cut_only(tmp_path, monkeypatch):
    """
    End-to-end integration test with Workflow 2 (Cut Only):
    Generates synthetic vertical video, executes main_improved with gaming pipeline,
    and verifies that the resulting cut segment retains exact 1080x1920 vertical dimensions.
    """
    project_dir = tmp_path / "proj_wf2"
    project_dir.mkdir()
    video_path = project_dir / "input.mp4"
    _create_synthetic_vertical_video(video_path, duration=5)

    _setup_mock_environment(monkeypatch, project_dir)

    test_argv = [
        "main_improved.py",
        "--project-path",
        str(project_dir),
        "--pipeline-mode",
        "gaming",
        "--workflow",
        "2",
        "--skip-prompts",
        "--segments",
        "1",
        "--min-duration",
        "2",
        "--max-duration",
        "5",
    ]
    monkeypatch.setattr(sys, "argv", test_argv)

    with pytest.raises(SystemExit) as exc_info:
        main_improved.main()
    assert exc_info.value.code == 0

    cuts_dir = project_dir / "cuts"
    assert cuts_dir.exists()
    cut_files = list(cuts_dir.glob("*.mp4"))
    assert len(cut_files) == 1

    cut_video = cut_files[0]
    assert is_vertical_video(str(cut_video)) is True
    w, h = probe_video_dimensions(str(cut_video))
    assert w == 1080
    assert h == 1920


def test_vertical_video_pipeline_e2e_workflow_1_full(tmp_path, monkeypatch, capsys):
    """
    End-to-end integration test with Workflow 1 (Full Pipeline):
    - Verifies vertical bypass log messages are emitted.
    - Verifies gaming_split.render_gaming_split_clip is NOT called.
    - Verifies preserved final video has dimensions 1080x1920.
    - Verifies burned subtitle video exists and has dimensions 1080x1920.
    - Verifies face_modes.json records 'none' for preserved framing.
    """
    project_dir = tmp_path / "proj_wf1"
    project_dir.mkdir()
    video_path = project_dir / "input.mp4"
    _create_synthetic_vertical_video(video_path, duration=5)

    mock_render_split = _setup_mock_environment(monkeypatch, project_dir)

    test_argv = [
        "main_improved.py",
        "--project-path",
        str(project_dir),
        "--pipeline-mode",
        "gaming",
        "--workflow",
        "1",
        "--skip-prompts",
        "--segments",
        "1",
        "--min-duration",
        "2",
        "--max-duration",
        "5",
        "--watermark-mode",
        "disabled",
    ]
    monkeypatch.setattr(sys, "argv", test_argv)

    main_improved.main()

    # Verify bypass logs
    captured = capsys.readouterr().out
    assert "Source video is already vertical (portrait). Preserving original framing without gaming split..." in captured
    assert "Preserving original source framing..." in captured

    # Verify gaming split was never called
    assert mock_render_split.call_count == 0

    # Verify final preserved video dimensions
    final_dir = project_dir / "final"
    assert final_dir.exists()
    final_files = list(final_dir.glob("*.mp4"))
    assert len(final_files) == 1
    final_video = final_files[0]
    assert is_vertical_video(str(final_video)) is True
    fw, fh = probe_video_dimensions(str(final_video))
    assert fw == 1080
    assert fh == 1920

    # Verify burned subtitle video exists and preserves 1080x1920 dimensions
    burned_dir = project_dir / "burned_sub"
    assert burned_dir.exists()
    burned_files = list(burned_dir.glob("*.mp4"))
    assert len(burned_files) == 1
    burned_video = burned_files[0]
    assert is_vertical_video(str(burned_video)) is True
    bw, bh = probe_video_dimensions(str(burned_video))
    assert bw == 1080
    assert bh == 1920

    # Verify face_modes record
    face_modes_file = project_dir / "face_modes.json"
    assert face_modes_file.exists()
    modes = json.loads(face_modes_file.read_text(encoding="utf-8"))
    assert any(mode == "none" for mode in modes.values())
