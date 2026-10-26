import os
import sys
import json
import subprocess
import pytest
from scripts import gaming_scorer
import main_improved
from webui.backend.schemas.jobs import JobRunRequest


def test_gaming_pipeline_e2e_mock(tmp_path, monkeypatch):
    """
    Full pipeline mock execution with synthetic audio RMS, facecam reaction,
    and realistic synthetic transcript. Validates segment count, duration,
    non-negative timestamps, composite score, and 5-dimension rubric.
    """
    def mock_extract(video_path, chunk_sec=0.1):
        # 120s video at 10Hz = 1200 samples.
        # Quiet baseline (10.0), spike at 30-31s (88.0), spike at 80-81s (92.0).
        rms = [10.0] * 300 + [88.0] * 10 + [10.0] * 490 + [92.0] * 10 + [10.0] * 390
        return rms, 15.0, 15.0

    def mock_facecam(video_path, facecam_box_str, candidate_timestamps):
        return [
            {"timestamp": 30.5, "score": 85.0, "reaction": "mouth_open"},
            {"timestamp": 80.5, "score": 75.0, "reaction": "surprise"},
        ]

    monkeypatch.setattr(
        gaming_scorer.gaming_audio_detector,
        "extract_audio_rms_curve",
        mock_extract,
    )
    monkeypatch.setattr(
        gaming_scorer.gaming_facecam_detector,
        "detect_facecam_reactions",
        mock_facecam,
    )

    project_dir = tmp_path / "proj_gaming_e2e"
    project_dir.mkdir()
    dummy_video = project_dir / "input.mp4"
    dummy_video.write_bytes(b"dummy video content")

    transcript_words = [
        {"word": "halo", "start": 1.0, "end": 2.0},
        {"word": "guys", "start": 2.2, "end": 2.8},
        {"word": "kita", "start": 3.0, "end": 3.5},
        {"word": "santai", "start": 4.0, "end": 5.0},
        {"word": "musuh", "start": 28.5, "end": 29.2},
        {"word": "anjir", "start": 30.0, "end": 30.6},
        {"word": "clutch", "start": 30.8, "end": 31.5},
        {"word": "gg", "start": 32.0, "end": 32.5},
        {"word": "tenang", "start": 50.0, "end": 51.0},
        {"word": "lagi", "start": 78.5, "end": 79.2},
        {"word": "headshot", "start": 80.0, "end": 80.7},
        {"word": "kill", "start": 81.0, "end": 81.6},
    ]

    min_dur = 20.0
    max_dur = 45.0
    video_dur = 120.0

    result = gaming_scorer.run_gaming_clipping_pipeline(
        video_path=str(dummy_video),
        project_folder=str(project_dir),
        transcript_words=transcript_words,
        video_duration=video_dur,
        num_segments=2,
        min_duration=min_dur,
        max_duration=max_dur,
        facecam_crop="0.68,0.05,0.28,0.1493",
        language="id",
    )

    assert "segments" in result
    segments = result["segments"]
    assert 1 <= len(segments) <= 2

    # Validate each segment's structure, boundaries, and 5-dimension rubric
    for seg in segments:
        assert "start_time" in seg
        assert "end_time" in seg
        assert "duration" in seg
        assert "score" in seg
        assert "hook_title" in seg
        assert "virality_explanation" in seg
        assert "rubric" in seg

        # Non-negative timestamps within video duration
        assert 0.0 <= seg["start_time"] < seg["end_time"] <= video_dur
        # Duration within [min_duration, max_duration]
        assert min_dur <= seg["duration"] <= max_dur
        assert round(seg["end_time"] - seg["start_time"], 2) == seg["duration"]

        # Composite score
        assert 0 <= seg["score"] <= 100

        # Hook title
        assert len(seg["hook_title"].strip()) > 0

        # 5-dimension rubric breakdown
        rubric = seg["rubric"]
        dimensions = [
            "hook_strength",
            "retention_flow",
            "emotional_resonance",
            "shareability",
            "audio_dynamics",
        ]
        for dim in dimensions:
            assert dim in rubric, f"Missing rubric dimension: {dim}"
            assert isinstance(rubric[dim], (int, float))
            assert 0.0 <= rubric[dim] <= 10.0
        assert "verdict" in rubric
        assert isinstance(rubric["verdict"], str)
        assert len(rubric["verdict"]) > 0

    # Output file verification
    saved_json = project_dir / "viral_segments.json"
    assert saved_json.exists()
    file_data = json.loads(saved_json.read_text(encoding="utf-8"))
    assert "segments" in file_data
    assert len(file_data["segments"]) == len(segments)
    for orig, loaded in zip(segments, file_data["segments"]):
        assert orig["start_time"] == loaded["start_time"]
        assert orig["end_time"] == loaded["end_time"]
        assert orig["score"] == loaded["score"]
        assert orig["hook_title"] == loaded["hook_title"]
        assert orig["rubric"] == loaded["rubric"]


def test_gaming_pipeline_e2e_json_schema_validation(tmp_path, monkeypatch):
    """
    Verifies viral_segments.json output file schema and valid JSON content.
    """
    def mock_extract(video_path, chunk_sec=0.1):
        rms = [10.0] * 100 + [85.0] * 10 + [10.0] * 90
        return rms, 15.0, 15.0

    monkeypatch.setattr(
        gaming_scorer.gaming_audio_detector,
        "extract_audio_rms_curve",
        mock_extract,
    )

    project_dir = tmp_path / "proj_schema"
    project_dir.mkdir()
    dummy_video = project_dir / "input.mp4"
    dummy_video.write_bytes(b"dummy")

    transcript_words = [
        {"word": "clutch", "start": 10.0, "end": 10.8},
        {"word": "gg", "start": 11.0, "end": 11.5},
    ]

    gaming_scorer.run_gaming_clipping_pipeline(
        video_path=str(dummy_video),
        project_folder=str(project_dir),
        transcript_words=transcript_words,
        video_duration=60.0,
        num_segments=1,
        min_duration=20.0,
        max_duration=40.0,
        language="en",
    )

    json_file = project_dir / "viral_segments.json"
    assert json_file.exists()
    content = json_file.read_text(encoding="utf-8")
    parsed = json.loads(content)

    assert isinstance(parsed, dict)
    assert "segments" in parsed
    assert isinstance(parsed["segments"], list)
    assert len(parsed["segments"]) == 1

    seg = parsed["segments"][0]
    expected_types = {
        "start_time": (int, float),
        "end_time": (int, float),
        "duration": (int, float),
        "score": (int, float),
        "hook_title": str,
        "virality_explanation": str,
        "rubric": dict,
    }
    for field, exp_type in expected_types.items():
        assert field in seg, f"Field '{field}' missing from segment JSON"
        assert isinstance(seg[field], exp_type)

    rubric = seg["rubric"]
    rubric_fields = ["hook_strength", "retention_flow", "emotional_resonance", "shareability", "audio_dynamics"]
    for rf in rubric_fields:
        assert rf in rubric
        assert isinstance(rubric[rf], (int, float))
    assert isinstance(rubric.get("verdict"), str)


def test_gaming_pipeline_e2e_boundary_durations(tmp_path, monkeypatch):
    """
    Validates boundary conditions:
    - Peak near start clamped at 0.0 with duration at least min_duration.
    - Peak near end clamped at video_duration.
    - Video shorter than min_duration clamped to total video duration.
    """
    def mock_extract(video_path, chunk_sec=0.1):
        # 10s video, peak at 5s
        rms = [10.0] * 40 + [90.0] * 10 + [10.0] * 50
        return rms, 15.0, 15.0

    monkeypatch.setattr(
        gaming_scorer.gaming_audio_detector,
        "extract_audio_rms_curve",
        mock_extract,
    )

    project_dir = tmp_path / "proj_boundary"
    project_dir.mkdir()
    dummy_video = project_dir / "input.mp4"
    dummy_video.write_bytes(b"dummy")

    result = gaming_scorer.run_gaming_clipping_pipeline(
        video_path=str(dummy_video),
        project_folder=str(project_dir),
        transcript_words=[{"word": "clutch", "start": 4.5, "end": 5.5}],
        video_duration=10.0,
        num_segments=1,
        min_duration=20.0,
        max_duration=60.0,
    )

    assert len(result["segments"]) == 1
    seg = result["segments"][0]
    assert seg["start_time"] >= 0.0
    assert seg["end_time"] <= 10.0
    assert seg["duration"] == 10.0


def test_gaming_pipeline_cli_argument_verification():
    """
    Verifies CLI argument handling:
    - --pipeline-mode flag presence and valid options.
    - Rejection of invalid pipeline modes.
    - JobRunRequest serialization with --pipeline-mode gaming and auto-routing.
    """
    # 1. --help output includes --pipeline-mode with gaming
    res = subprocess.run(
        [sys.executable, "main_improved.py", "--help"],
        capture_output=True,
        text=True,
        check=True,
    )
    assert "--pipeline-mode" in res.stdout
    assert "gaming" in res.stdout
    assert "--gaming-facecam" in res.stdout
    assert "--gaming-gameplay" in res.stdout

    # 2. Rejection of invalid choice
    bad_res = subprocess.run(
        [sys.executable, "main_improved.py", "--pipeline-mode", "invalid_pipeline_choice"],
        capture_output=True,
        text=True,
    )
    assert bad_res.returncode != 0
    assert "invalid choice" in bad_res.stderr

    # 3. JobRunRequest integration
    req = JobRunRequest(
        video_path="/tmp/gameplay.mp4",
        pipeline_mode="gaming",
        orientation="9:16",
    )
    cli_args = req.to_cli_args(python_exec="python", script_path="main_improved.py")
    assert "--pipeline-mode" in cli_args
    mode_idx = cli_args.index("--pipeline-mode")
    assert cli_args[mode_idx + 1] == "gaming"

    # Auto-routes 9:16 to 9:16_gaming_split
    assert "--orientation" in cli_args
    orient_idx = cli_args.index("--orientation")
    assert cli_args[orient_idx + 1] == "9:16_gaming_split"


def test_gaming_pipeline_cli_e2e_dry_run(tmp_path, monkeypatch):
    """
    CLI end-to-end dry-run: executes main_improved.main() with --pipeline-mode gaming,
    mocking transcription and cutting, and verifies viral_segments.json generation.
    """
    project_dir = tmp_path / "proj_cli_e2e"
    project_dir.mkdir()

    video_file = project_dir / "input.mp4"
    video_file.write_bytes(b"dummy video")

    transcript_file = project_dir / "input.json"
    transcript_file.write_text(
        json.dumps({
            "segments": [
                {
                    "start": 0.0,
                    "end": 60.0,
                    "words": [
                        {"word": "santai", "start": 5.0, "end": 6.0},
                        {"word": "anjir", "start": 25.0, "end": 25.5},
                        {"word": "clutch", "start": 26.0, "end": 26.8},
                        {"word": "gg", "start": 27.0, "end": 27.5},
                    ],
                }
            ]
        }, ensure_ascii=False),
        encoding="utf-8",
    )

    test_argv = [
        "main_improved.py",
        "--project-path", str(project_dir),
        "--pipeline-mode", "gaming",
        "--workflow", "2",
        "--skip-prompts",
        "--segments", "1",
        "--min-duration", "20",
        "--max-duration", "60",
    ]

    monkeypatch.setattr(sys, "argv", test_argv)
    monkeypatch.setattr(
        "scripts.transcribe_video.transcribe",
        lambda *args, **kwargs: ("dummy.srt", "dummy.tsv"),
    )
    monkeypatch.setattr(
        "scripts.transcribe_video.get_audio_duration",
        lambda *args, **kwargs: 60.0,
    )
    monkeypatch.setattr(
        "scripts.cut_segments.cut",
        lambda *args, **kwargs: None,
    )

    def mock_rms(path, chunk_sec=0.1):
        rms = [10.0] * 250 + [90.0] * 20 + [10.0] * 330
        return rms, 15.0, 10.0

    def mock_face(video_path, facecam_box_str, candidate_timestamps):
        return [{"timestamp": 25.5, "score": 85.0, "reaction": "mouth_open"}]

    monkeypatch.setattr(
        gaming_scorer.gaming_audio_detector,
        "extract_audio_rms_curve",
        mock_rms,
    )
    monkeypatch.setattr(
        gaming_scorer.gaming_facecam_detector,
        "detect_facecam_reactions",
        mock_face,
    )

    with pytest.raises(SystemExit) as exc_info:
        main_improved.main()
    assert exc_info.value.code == 0

    saved_json = project_dir / "viral_segments.json"
    assert saved_json.exists()
    data = json.loads(saved_json.read_text(encoding="utf-8"))
    assert "segments" in data
    assert len(data["segments"]) == 1

    seg = data["segments"][0]
    assert 0.0 <= seg["start_time"] < seg["end_time"] <= 60.0
    assert 20.0 <= seg["duration"] <= 60.0
    assert seg["score"] > 0
    assert len(seg["hook_title"]) > 0
    assert "rubric" in seg
    assert seg["rubric"]["audio_dynamics"] > 0.0
    assert seg["rubric"]["hook_strength"] > 0.0


def test_main_improved_auto_language_resolution(tmp_path, monkeypatch):
    project_dir = tmp_path / "proj_auto_lang"
    project_dir.mkdir()

    video_file = project_dir / "input.mp4"
    video_file.write_bytes(b"dummy video")

    transcript_file = project_dir / "input.json"
    transcript_file.write_text(
        json.dumps({
            "language": "id",
            "segments": [
                {
                    "start": 0.0,
                    "end": 30.0,
                    "words": [{"word": "mantap", "start": 5.0, "end": 5.5}]
                }
            ]
        }),
        encoding="utf-8"
    )

    test_argv = [
        "main_improved.py",
        "--project-path", str(project_dir),
        "--pipeline-mode", "gaming",
        "--workflow", "2",
        "--skip-prompts",
        "--language", "auto",
    ]

    monkeypatch.setattr(sys, "argv", test_argv)
    monkeypatch.setattr("scripts.transcribe_video.transcribe", lambda *args, **kwargs: ("dummy.srt", "dummy.tsv"))
    monkeypatch.setattr("scripts.transcribe_video.get_audio_duration", lambda *args, **kwargs: 30.0)
    monkeypatch.setattr("scripts.cut_segments.cut", lambda *args, **kwargs: None)

    captured_pipeline_kwargs = {}
    def mock_pipeline(**kwargs):
        captured_pipeline_kwargs.update(kwargs)
        return {
            "segments": [
                {
                    "start_time": 0.0,
                    "end_time": 20.0,
                    "duration": 20.0,
                    "score": 85,
                    "title": "HOOK",
                    "hook_title": "HOOK",
                    "rubric": {"audio_dynamics": 8.0, "hook_strength": 8.0}
                }
            ]
        }
    monkeypatch.setattr(
        gaming_scorer,
        "run_gaming_clipping_pipeline",
        mock_pipeline
    )

    with pytest.raises(SystemExit) as exc_info:
        main_improved.main()
    assert exc_info.value.code == 0

    # Language resolved from transcript_data should be "id" instead of "auto"
    assert captured_pipeline_kwargs.get("language") == "id"


def test_main_improved_api_key_resolution_gemini_cli(tmp_path, monkeypatch):
    project_dir = tmp_path / "proj_api_key_cli"
    project_dir.mkdir()

    video_file = project_dir / "input.mp4"
    video_file.write_bytes(b"dummy video")

    transcript_file = project_dir / "input.json"
    transcript_file.write_text(
        json.dumps({
            "language": "id",
            "segments": [
                {
                    "start": 0.0,
                    "end": 30.0,
                    "words": [{"word": "mantap", "start": 5.0, "end": 5.5}]
                }
            ]
        }),
        encoding="utf-8"
    )

    test_argv = [
        "main_improved.py",
        "--project-path", str(project_dir),
        "--pipeline-mode", "gaming",
        "--ai-backend", "gemini",
        "--api-key", "secret_gemini_key_123",
        "--workflow", "2",
        "--skip-prompts",
    ]

    monkeypatch.setattr(sys, "argv", test_argv)
    monkeypatch.setattr("scripts.transcribe_video.transcribe", lambda *args, **kwargs: ("dummy.srt", "dummy.tsv"))
    monkeypatch.setattr("scripts.transcribe_video.get_audio_duration", lambda *args, **kwargs: 30.0)
    monkeypatch.setattr("scripts.cut_segments.cut", lambda *args, **kwargs: None)

    captured_pipeline_kwargs = {}
    def mock_pipeline(**kwargs):
        captured_pipeline_kwargs.update(kwargs)
        return {
            "segments": [
                {
                    "start_time": 0.0,
                    "end_time": 20.0,
                    "duration": 20.0,
                    "score": 85,
                    "title": "HOOK",
                    "hook_title": "HOOK",
                    "rubric": {"audio_dynamics": 8.0, "hook_strength": 8.0}
                }
            ]
        }
    monkeypatch.setattr(gaming_scorer, "run_gaming_clipping_pipeline", mock_pipeline)

    with pytest.raises(SystemExit) as exc_info:
        main_improved.main()
    assert exc_info.value.code == 0

    assert captured_pipeline_kwargs.get("ai_backend") == "gemini"
    assert captured_pipeline_kwargs.get("api_key") == "secret_gemini_key_123"


def test_main_improved_api_key_resolution_from_config(tmp_path, monkeypatch):
    project_dir = tmp_path / "proj_api_key_cfg"
    project_dir.mkdir()

    video_file = project_dir / "input.mp4"
    video_file.write_bytes(b"dummy video")

    transcript_file = project_dir / "input.json"
    transcript_file.write_text(
        json.dumps({
            "language": "id",
            "segments": [
                {
                    "start": 0.0,
                    "end": 30.0,
                    "words": [{"word": "mantap", "start": 5.0, "end": 5.5}]
                }
            ]
        }),
        encoding="utf-8"
    )

    test_argv = [
        "main_improved.py",
        "--project-path", str(project_dir),
        "--pipeline-mode", "gaming",
        "--ai-backend", "gemini",
        "--workflow", "2",
        "--skip-prompts",
    ]

    monkeypatch.setattr(sys, "argv", test_argv)
    monkeypatch.setattr("scripts.transcribe_video.transcribe", lambda *args, **kwargs: ("dummy.srt", "dummy.tsv"))
    monkeypatch.setattr("scripts.transcribe_video.get_audio_duration", lambda *args, **kwargs: 30.0)
    monkeypatch.setattr("scripts.cut_segments.cut", lambda *args, **kwargs: None)

    config_content = json.dumps({"gemini": {"api_key": "config_gemini_key_789"}})
    cfg_file = tmp_path / "api_config.json"
    cfg_file.write_text(config_content, encoding="utf-8")
    real_exists = os.path.exists
    monkeypatch.setattr(os.path, "exists", lambda p: True if str(p).endswith("api_config.json") else real_exists(p))
    original_open = open
    def mock_open_config(file, *args, **kwargs):
        if str(file).endswith("api_config.json"):
            from io import StringIO
            return StringIO(config_content)
        return original_open(file, *args, **kwargs)
    monkeypatch.setattr("builtins.open", mock_open_config)

    captured_pipeline_kwargs = {}
    def mock_pipeline(**kwargs):
        captured_pipeline_kwargs.update(kwargs)
        return {
            "segments": [
                {
                    "start_time": 0.0,
                    "end_time": 20.0,
                    "duration": 20.0,
                    "score": 85,
                    "title": "HOOK",
                    "hook_title": "HOOK",
                    "rubric": {"audio_dynamics": 8.0, "hook_strength": 8.0}
                }
            ]
        }
    monkeypatch.setattr(gaming_scorer, "run_gaming_clipping_pipeline", mock_pipeline)

    with pytest.raises(SystemExit) as exc_info:
        main_improved.main()
    assert exc_info.value.code == 0

    assert captured_pipeline_kwargs.get("ai_backend") == "gemini"
    assert captured_pipeline_kwargs.get("api_key") == "config_gemini_key_789"


def test_main_improved_facecam_auto_detection_propagation(tmp_path, monkeypatch):
    project_dir = tmp_path / "proj_facecam_auto"
    project_dir.mkdir()

    video_file = project_dir / "input.mp4"
    video_file.write_bytes(b"dummy video")

    transcript_file = project_dir / "input.json"
    transcript_file.write_text(
        json.dumps({
            "language": "id",
            "segments": [
                {
                    "start": 0.0,
                    "end": 30.0,
                    "words": [{"word": "mantap", "start": 5.0, "end": 5.5}]
                }
            ]
        }),
        encoding="utf-8"
    )

    test_argv = [
        "main_improved.py",
        "--project-path", str(project_dir),
        "--pipeline-mode", "gaming",
        "--gaming-facecam", "auto",
        "--workflow", "1",
        "--skip-prompts",
    ]

    monkeypatch.setattr(sys, "argv", test_argv)
    monkeypatch.setattr("scripts.transcribe_video.transcribe", lambda *args, **kwargs: ("dummy.srt", "dummy.tsv"))
    monkeypatch.setattr("scripts.transcribe_video.get_audio_duration", lambda *args, **kwargs: 30.0)

    cuts_dir = project_dir / "cuts"
    def mock_cut(*args, **kwargs):
        cuts_dir.mkdir(parents=True, exist_ok=True)
        (cuts_dir / "output000.mp4").write_bytes(b"dummy cut video")
    monkeypatch.setattr("scripts.cut_segments.cut", mock_cut)

    from scripts import gaming_facecam_detector, gaming_split
    detected_box = "0.04,0.05,0.28,0.22"
    monkeypatch.setattr(gaming_facecam_detector, "auto_detect_facecam_box", lambda *args, **kwargs: detected_box)
    monkeypatch.setattr(gaming_split, "is_vertical_video", lambda *args, **kwargs: False)

    captured_pipeline_kwargs = {}
    def mock_pipeline(**kwargs):
        captured_pipeline_kwargs.update(kwargs)
        return {
            "segments": [
                {
                    "start_time": 0.0,
                    "end_time": 20.0,
                    "duration": 20.0,
                    "score": 85,
                    "title": "HOOK",
                    "hook_title": "HOOK",
                    "rubric": {"audio_dynamics": 8.0, "hook_strength": 8.0}
                }
            ]
        }
    monkeypatch.setattr(gaming_scorer, "run_gaming_clipping_pipeline", mock_pipeline)

    captured_render_kwargs = {}
    def mock_render(**kwargs):
        captured_render_kwargs.update(kwargs)
        out_p = kwargs.get("output_path")
        if out_p:
            with open(out_p, "wb") as f:
                f.write(b"processed")
    monkeypatch.setattr(gaming_split, "render_gaming_split_clip", mock_render)

    monkeypatch.setattr("scripts.adjust_subtitles.adjust", lambda *args, **kwargs: None)
    monkeypatch.setattr("scripts.burn_subtitles.burn", lambda *args, **kwargs: None)

    main_improved.main()

    assert captured_pipeline_kwargs.get("facecam_crop") == detected_box
    assert captured_render_kwargs.get("facecam_box") == detected_box


def test_main_improved_api_key_resolution_ignores_placeholder(tmp_path, monkeypatch):
    project_dir = tmp_path / "proj_api_placeholder"
    project_dir.mkdir()
    video_file = project_dir / "input.mp4"
    video_file.write_bytes(b"dummy video")
    transcript_file = project_dir / "input.json"
    transcript_file.write_text(
        json.dumps({
            "language": "en",
            "segments": [{"start": 0.0, "end": 10.0, "words": []}]
        }),
        encoding="utf-8"
    )

    test_argv = [
        "main_improved.py",
        "--project-path", str(project_dir),
        "--pipeline-mode", "gaming",
        "--ai-backend", "gemini",
        "--workflow", "2",
        "--skip-prompts",
    ]
    monkeypatch.setattr(sys, "argv", test_argv)
    monkeypatch.setattr("scripts.transcribe_video.transcribe", lambda *args, **kwargs: ("dummy.srt", "dummy.tsv"))
    monkeypatch.setattr("scripts.transcribe_video.get_audio_duration", lambda *args, **kwargs: 10.0)
    monkeypatch.setattr("scripts.cut_segments.cut", lambda *args, **kwargs: None)

    config_content = json.dumps({"gemini": {"api_key": "SUA_KEY_AQUI"}})
    cfg_file = tmp_path / "api_config.json"
    cfg_file.write_text(config_content, encoding="utf-8")
    real_exists = os.path.exists
    monkeypatch.setattr(os.path, "exists", lambda p: True if str(p).endswith("api_config.json") else real_exists(p))
    original_open = open
    monkeypatch.setattr(
        "builtins.open",
        lambda file, *a, **kw: (
            from_io_string(config_content) if str(file).endswith("api_config.json")
            else original_open(file, *a, **kw)
        )
    )
    from io import StringIO
    def from_io_string(content):
        return StringIO(content)

    captured_pipeline_kwargs = {}
    def mock_pipeline(**kwargs):
        captured_pipeline_kwargs.update(kwargs)
        return {
            "segments": [
                {
                    "start_time": 0.0,
                    "end_time": 5.0,
                    "duration": 5.0,
                    "score": 85,
                    "title": "HOOK",
                    "hook_title": "HOOK",
                    "rubric": {"audio_dynamics": 8.0, "hook_strength": 8.0}
                }
            ]
        }
    monkeypatch.setattr(gaming_scorer, "run_gaming_clipping_pipeline", mock_pipeline)
    with pytest.raises(SystemExit) as exc_info:
        main_improved.main()
    assert exc_info.value.code == 0
    # Placeholder key must NOT be used
    assert captured_pipeline_kwargs.get("api_key") != "SUA_KEY_AQUI"
    assert captured_pipeline_kwargs.get("api_key") is None


def test_main_improved_offline_backend_pipeline_execution(tmp_path, monkeypatch):
    project_dir = tmp_path / "proj_offline_backend"
    project_dir.mkdir()
    video_file = project_dir / "input.mp4"
    video_file.write_bytes(b"dummy video")
    transcript_file = project_dir / "input.json"
    transcript_file.write_text(
        json.dumps({
            "language": "id",
            "segments": [{"start": 0.0, "end": 10.0, "words": []}]
        }),
        encoding="utf-8"
    )

    test_argv = [
        "main_improved.py",
        "--project-path", str(project_dir),
        "--pipeline-mode", "gaming",
        "--ai-backend", "offline",
        "--workflow", "2",
        "--skip-prompts",
    ]
    monkeypatch.setattr(sys, "argv", test_argv)
    monkeypatch.setattr("scripts.transcribe_video.transcribe", lambda *args, **kwargs: ("dummy.srt", "dummy.tsv"))
    monkeypatch.setattr("scripts.transcribe_video.get_audio_duration", lambda *args, **kwargs: 10.0)
    monkeypatch.setattr("scripts.cut_segments.cut", lambda *args, **kwargs: None)

    captured_pipeline_kwargs = {}
    def mock_pipeline(**kwargs):
        captured_pipeline_kwargs.update(kwargs)
        return {
            "segments": [
                {
                    "start_time": 0.0,
                    "end_time": 5.0,
                    "duration": 5.0,
                    "score": 85,
                    "title": "HOOK",
                    "hook_title": "HOOK",
                    "rubric": {"audio_dynamics": 8.0, "hook_strength": 8.0}
                }
            ]
        }
    monkeypatch.setattr(gaming_scorer, "run_gaming_clipping_pipeline", mock_pipeline)

    with pytest.raises(SystemExit) as exc_info:
        main_improved.main()
    assert exc_info.value.code == 0
    assert captured_pipeline_kwargs.get("ai_backend") == "offline"


def test_main_improved_facecam_fallback_during_split_render(tmp_path, monkeypatch):
    project_dir = tmp_path / "proj_facecam_fallback"
    project_dir.mkdir()
    cuts_dir = project_dir / "cuts"
    cuts_dir.mkdir()
    cut_file = cuts_dir / "output000.mp4"
    cut_file.write_bytes(b"dummy cut")

    # Create existing viral_segments.json so scoring is bypassed
    segments_file = project_dir / "viral_segments.json"
    segments_file.write_text(
        json.dumps({
            "segments": [
                {
                    "start_time": 0.0,
                    "end_time": 10.0,
                    "duration": 10.0,
                    "score": 80,
                    "title": "HOOK",
                    "hook_title": "HOOK",
                    "rubric": {"audio_dynamics": 8.0}
                }
            ]
        }),
        encoding="utf-8"
    )

    test_argv = [
        "main_improved.py",
        "--project-path", str(project_dir),
        "--pipeline-mode", "gaming",
        "--workflow", "1",
        "--skip-prompts",
    ]
    monkeypatch.setattr(sys, "argv", test_argv)
    monkeypatch.setattr("scripts.transcribe_video.transcribe", lambda *args, **kwargs: ("dummy.srt", "dummy.tsv"))
    monkeypatch.setattr("scripts.transcribe_video.get_audio_duration", lambda *args, **kwargs: 10.0)
    monkeypatch.setattr("scripts.cut_segments.cut", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        gaming_scorer,
        "run_gaming_clipping_pipeline",
        lambda **kwargs: {
            "segments": [
                {
                    "start_time": 0.0,
                    "end_time": 10.0,
                    "duration": 10.0,
                    "score": 80,
                    "title": "HOOK",
                    "hook_title": "HOOK",
                    "rubric": {"audio_dynamics": 8.0, "hook_strength": 8.0}
                }
            ]
        }
    )

    from scripts import gaming_facecam_detector, gaming_split
    detected_box = "0.7,0.0,1.0,0.4"
    monkeypatch.setattr(gaming_facecam_detector, "auto_detect_facecam_box", lambda *args, **kwargs: detected_box)
    monkeypatch.setattr(gaming_split, "is_vertical_video", lambda *args, **kwargs: False)

    captured_render_kwargs = {}
    def mock_render(**kwargs):
        captured_render_kwargs.update(kwargs)
        out_p = kwargs.get("output_path")
        if out_p:
            with open(out_p, "wb") as f:
                f.write(b"processed")
    monkeypatch.setattr(gaming_split, "render_gaming_split_clip", mock_render)
    monkeypatch.setattr("scripts.adjust_subtitles.adjust", lambda *args, **kwargs: None)
    monkeypatch.setattr("scripts.burn_subtitles.burn", lambda *args, **kwargs: None)

    main_improved.main()

    assert captured_render_kwargs.get("facecam_box") == detected_box
