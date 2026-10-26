from pathlib import Path
import os
import json
import math
import pytest
from unittest.mock import patch, MagicMock

from scripts.gaming_scorer import (
    fuse_gaming_scores,
    apply_non_maximum_suppression,
    generate_gaming_windows,
    generate_gaming_hook_title,
    run_gaming_clipping_pipeline,
    refine_gaming_candidates_with_llm,
)


def test_fuse_gaming_scores():
    audio_events = [{"timestamp": 30.0, "score": 80.0}]
    keyword_events = [{"timestamp": 30.0, "score": 90.0}]
    face_events = [{"timestamp": 30.0, "score": 70.0}]

    fused = fuse_gaming_scores(audio_events, keyword_events, face_events)
    assert len(fused) == 1
    # 80*0.5 + 70*0.3 + 90*0.2 = 79.0; with convergence boost (+15%): 79.0 * 1.15 = 90.9
    assert fused[0]["score"] == pytest.approx(90.9, abs=1.0)
    assert fused[0]["converged"] is True
    assert fused[0]["timestamp"] == 30.0


def test_fuse_gaming_scores_without_face():
    # When facecam is missing or score is 0: audio=0.70, kw=0.30
    audio_events = [{"timestamp": 25.0, "score": 80.0}]
    keyword_events = [{"timestamp": 25.0, "score": 60.0}]
    face_events = [{"timestamp": 25.0, "score": 0.0}]

    fused = fuse_gaming_scores(audio_events, keyword_events, face_events)
    assert len(fused) == 1
    # 80*0.7 + 60*0.3 = 74.0; with convergence boost (+15%): 74.0 * 1.15 = 85.1
    assert fused[0]["score"] == pytest.approx(85.1, abs=1.0)
    assert fused[0]["converged"] is True
    assert fused[0]["timestamp"] == 25.0

def test_fuse_gaming_scores_with_numpy_or_tuples():
    import numpy as np
    audio_events = [{"timestamp": 30.0, "score": 80.0}]
    keyword_events = tuple([{"timestamp": 30.0, "score": 90.0}])
    face_events = np.array([{"timestamp": 30.0, "score": 70.0}], dtype=object)

    fused = fuse_gaming_scores(audio_events, keyword_events, face_events)
    assert len(fused) == 1
    assert fused[0]["score"] == pytest.approx(90.9, abs=1.0)
    assert fused[0]["converged"] is True


def test_fuse_gaming_scores_edge_cases():
    # Empty inputs
    assert fuse_gaming_scores([], []) == []
    assert fuse_gaming_scores(None, None) == []

    # Corrupted / boolean / NaN / Inf inputs
    audio_events = [
        {"timestamp": True, "score": 80.0},  # True shouldn't be 1.0 timestamp
        {"timestamp": float("nan"), "score": 50.0},
        {"timestamp": 40.0, "score": float("inf")},
        "not_a_dict",
    ]
    fused = fuse_gaming_scores(audio_events, [])
    # Only valid timestamp is 40.0, score inf clamped or defaulted safely
    assert len(fused) <= 2


def test_fuse_gaming_scores_keyword_fallback_when_audio_empty():
    keyword_events = [{"timestamp": 45.0, "score": 85.0, "matched_words": ["clutch"]}]
    fused = fuse_gaming_scores([], keyword_events)
    assert len(fused) == 1
    assert fused[0]["timestamp"] == 45.0
    assert fused[0]["keywords"] == ["clutch"]


def test_apply_non_maximum_suppression():
    candidates = [
        {"timestamp": 100.0, "score": 95.0},
        {"timestamp": 110.0, "score": 85.0},  # Within 45s of 100.0, lower score -> suppress
        {"timestamp": 200.0, "score": 90.0},  # Independent
    ]
    kept = apply_non_maximum_suppression(candidates, radius_sec=45.0)
    assert len(kept) == 2
    assert kept[0]["timestamp"] == 100.0
    assert kept[1]["timestamp"] == 200.0


def test_apply_non_maximum_suppression_unsorted():
    # Unsorted input: higher score candidate appears later, NMS should still retain highest score
    candidates = [
        {"timestamp": 110.0, "score": 70.0},
        {"timestamp": 100.0, "score": 95.0},
    ]
    kept = apply_non_maximum_suppression(candidates, radius_sec=45.0)
    assert len(kept) == 1
    assert kept[0]["timestamp"] == 100.0
    assert kept[0]["score"] == 95.0


def test_apply_non_maximum_suppression_edge_cases():
    assert apply_non_maximum_suppression([]) == []
    assert apply_non_maximum_suppression(None) == []

    # Non-positive radius
    candidates = [
        {"timestamp": 10.0, "score": 90.0},
        {"timestamp": 12.0, "score": 80.0},
    ]
    kept = apply_non_maximum_suppression(candidates, radius_sec=0.0)
    assert len(kept) == 2

def test_apply_non_maximum_suppression_numpy_array():
    import numpy as np
    candidates = np.array([
        {"timestamp": 100.0, "score": 95.0},
        {"timestamp": 110.0, "score": 85.0},
    ], dtype=object)
    kept = apply_non_maximum_suppression(candidates, radius_sec=45.0)
    assert len(kept) == 1
    assert kept[0]["timestamp"] == 100.0

def test_generate_gaming_windows_numpy_array():
    import numpy as np
    peaks = np.array([{"timestamp": 50.0, "score": 88.0, "keywords": ["clutch"]}], dtype=object)
    windows = generate_gaming_windows(peaks, video_duration=120.0)
    assert len(windows) == 1
    assert windows[0]["score"] == 88


def test_generate_gaming_windows():
    # Peak at 50s. Pre-roll 18s -> start 32s. Post-roll 10s -> end 60s. Duration 28s.
    peaks = [{"timestamp": 50.0, "score": 88.0, "keywords": ["clutch"]}]
    windows = generate_gaming_windows(
        peaks,
        video_duration=120.0,
        min_duration=20.0,
        max_duration=60.0
    )
    assert len(windows) == 1
    w = windows[0]
    assert 30.0 <= w["start_time"] <= 35.0
    assert 58.0 <= w["end_time"] <= 62.0
    assert w["duration"] >= 20.0
    assert "hook_title" in w
    assert len(w["hook_title"].split()) >= 3
    assert "rubric" in w
    assert w["rubric"]["hook_strength"] <= 10.0


def test_generate_gaming_windows_boundary_clamping():
    # Peak at 5s, video duration 100s. Window must not start before 0.0 and duration >= 20.0
    peaks = [{"timestamp": 5.0, "score": 80.0}]
    windows = generate_gaming_windows(
        peaks,
        video_duration=100.0,
        min_duration=20.0,
        max_duration=60.0
    )
    assert len(windows) == 1
    assert windows[0]["start_time"] == 0.0
    assert windows[0]["duration"] >= 20.0
    assert windows[0]["end_time"] <= 100.0

    # Peak near end: 98s on a 100s video
    peaks_end = [{"timestamp": 98.0, "score": 85.0}]
    windows_end = generate_gaming_windows(
        peaks_end,
        video_duration=100.0,
        min_duration=20.0,
        max_duration=60.0
    )
    assert len(windows_end) == 1
    assert windows_end[0]["end_time"] == 100.0
    assert windows_end[0]["duration"] >= 20.0
    assert windows_end[0]["start_time"] <= 80.0


def test_generate_gaming_windows_short_video():
    # Video shorter than min_duration: clamped to video_duration
    peaks = [{"timestamp": 8.0, "score": 75.0}]
    windows = generate_gaming_windows(
        peaks,
        video_duration=15.0,
        min_duration=20.0,
        max_duration=60.0
    )
    assert len(windows) == 1
    assert windows[0]["start_time"] == 0.0
    assert windows[0]["end_time"] == 15.0
    assert windows[0]["duration"] == 15.0


def test_generate_gaming_hook_title():
    title_id = generate_gaming_hook_title(keywords=["anjir", "gila"], language="id")
    assert title_id == title_id.upper()
    assert 3 <= len(title_id.split()) <= 6

    title_en = generate_gaming_hook_title(keywords=["clutch"], language="en")
    assert title_en == title_en.upper()
    assert 3 <= len(title_en.split()) <= 6

    # Default / fallback language
    title_default = generate_gaming_hook_title(keywords=None, language="unknown")
    assert title_default == title_default.upper()
    assert 3 <= len(title_default.split()) <= 6

def test_generate_gaming_hook_title_numpy_array():
    import numpy as np
    kws = np.array(["clutch", "epic"])
    title = generate_gaming_hook_title(keywords=kws, language="en")
    assert title == title.upper()
    assert 3 <= len(title.split()) <= 6


def test_generate_gaming_windows_tuple_and_set_keywords():
    peaks = [
        {"timestamp": 40.0, "score": 80.0, "keywords": ("clutch", "gila")},
        {"timestamp": 80.0, "score": 85.0, "keywords": {"clutch", "epic"}},
    ]
    windows = generate_gaming_windows(peaks, video_duration=120.0)
    assert len(windows) == 2
    assert "hook_title" in windows[0]
    assert "hook_title" in windows[1]


@patch("scripts.gaming_facecam_detector.detect_facecam_reactions")
@patch("scripts.gaming_keyword_detector.scan_shout_keywords")
@patch("scripts.gaming_audio_detector.detect_audio_events")
@patch("scripts.gaming_audio_detector.extract_audio_rms_curve")
def test_run_gaming_clipping_pipeline(mock_rms, mock_audio_ev, mock_kw, mock_face, tmp_path):
    mock_rms.return_value = ([0.1] * 100, 0.1, 0.02)
    mock_audio_ev.return_value = [
        {"timestamp": 30.0, "score": 85.0},
        {"timestamp": 90.0, "score": 75.0},
    ]
    mock_kw.return_value = [
        {"timestamp": 30.0, "score": 90.0, "matched_words": ["gila"]}
    ]
    mock_face.return_value = [
        {"timestamp": 30.0, "score": 80.0, "mar": 0.15, "motion_velocity": 12.0}
    ]

    project_folder = str(tmp_path / "proj")
    dummy_video = str(tmp_path / "game.mp4")
    with open(dummy_video, "w") as f:
        f.write("dummy")

    result = run_gaming_clipping_pipeline(
        video_path=dummy_video,
        project_folder=project_folder,
        transcript_words=[{"word": "gila", "start": 29.5, "end": 30.2}],
        video_duration=120.0,
        num_segments=2,
        language="id"
    )

    assert "segments" in result
    assert len(result["segments"]) == 2
    # Verify viral_segments.json was written to project_folder
    out_file = os.path.join(project_folder, "viral_segments.json")
    assert os.path.exists(out_file)
    with open(out_file, "r", encoding="utf-8") as f:
        saved_data = json.load(f)
    assert "segments" in saved_data
    assert len(saved_data["segments"]) == 2
    assert saved_data["segments"][0]["score"] > 0
    assert "hook_title" in saved_data["segments"][0]


def test_run_gaming_clipping_pipeline_missing_video(tmp_path):
    project_folder = str(tmp_path / "proj_missing")
    result = run_gaming_clipping_pipeline(
        video_path="non_existent_video.mp4",
        project_folder=project_folder,
        transcript_words=[],
        video_duration=60.0
    )
    assert "segments" in result
    assert result["segments"] == []
    out_file = os.path.join(project_folder, "viral_segments.json")
    assert os.path.exists(out_file)


@patch("scripts.gaming_facecam_detector.detect_facecam_reactions")
@patch("scripts.gaming_keyword_detector.scan_shout_keywords")
@patch("scripts.gaming_audio_detector.detect_audio_events")
@patch("scripts.gaming_audio_detector.extract_audio_rms_curve")
def test_run_gaming_clipping_pipeline_numpy_transcript_words(mock_rms, mock_audio_ev, mock_kw, mock_face, tmp_path):
    import numpy as np
    mock_rms.return_value = ([0.1] * 50, 0.1, 0.02)
    mock_audio_ev.return_value = [{"timestamp": 25.0, "score": 80.0}]
    mock_kw.return_value = []
    mock_face.return_value = []

    words = np.array([{"word": "clutch", "start": 24.0, "end": 25.0}], dtype=object)
    dummy_vid = tmp_path / "vid.mp4"
    dummy_vid.write_text("test")

    result = run_gaming_clipping_pipeline(
        video_path=str(dummy_vid),
        project_folder=str(tmp_path),
        transcript_words=words,
        video_duration=60.0
    )
    assert len(result["segments"]) == 1


@patch("scripts.gaming_facecam_detector.detect_facecam_reactions")
@patch("scripts.gaming_keyword_detector.scan_shout_keywords")
@patch("scripts.gaming_audio_detector.detect_audio_events")
@patch("scripts.gaming_audio_detector.extract_audio_rms_curve")
def test_run_gaming_clipping_pipeline_num_segments_none(mock_rms, mock_audio_ev, mock_kw, mock_face, tmp_path):
    mock_rms.return_value = ([0.1] * 50, 0.1, 0.02)
    mock_audio_ev.return_value = [{"timestamp": 25.0, "score": 80.0}]
    mock_kw.return_value = []
    mock_face.return_value = []

    dummy_vid = tmp_path / "vid.mp4"
    dummy_vid.write_text("test")

    result = run_gaming_clipping_pipeline(
        video_path=str(dummy_vid),
        project_folder=str(tmp_path),
        transcript_words=[],
        video_duration=60.0,
        num_segments=None
    )
    assert len(result["segments"]) == 1


@patch("scripts.gaming_facecam_detector.detect_facecam_reactions")
@patch("scripts.gaming_keyword_detector.scan_shout_keywords")
@patch("scripts.gaming_audio_detector.detect_audio_events")
@patch("scripts.gaming_audio_detector.extract_audio_rms_curve")
def test_run_gaming_clipping_pipeline_pathlib_path(mock_rms, mock_audio_ev, mock_kw, mock_face, tmp_path):
    mock_rms.return_value = ([0.1] * 50, 0.1, 0.02)
    mock_audio_ev.return_value = [{"timestamp": 25.0, "score": 80.0}]
    mock_kw.return_value = []
    mock_face.return_value = []

    proj_path = Path(tmp_path / "pathlib_proj")
    vid_path = Path(tmp_path / "pathlib_vid.mp4")
    vid_path.write_text("dummy")

    result = run_gaming_clipping_pipeline(
        video_path=vid_path,
        project_folder=proj_path,
        transcript_words=[],
        video_duration=60.0
    )
    assert len(result["segments"]) == 1
    assert (proj_path / "viral_segments.json").exists()

def test_generate_gaming_windows_anchoring_max_dur_less_than_pre_roll():
    # Peak at 40.0s, pre_roll 20.0s, max_dur 15.0s (< pre_roll)
    peaks = [{"timestamp": 40.0, "score": 90.0, "keywords": ["clutch"]}]
    windows = generate_gaming_windows(
        peaks,
        video_duration=100.0,
        min_duration=10.0,
        max_duration=15.0,
        pre_roll=20.0,
        post_roll=10.0
    )
    assert len(windows) == 1
    seg = windows[0]
    # Invariant: peak timestamp must always be included in [start, end]
    assert seg["start_time"] <= 40.0 <= seg["end_time"]
    assert seg["duration"] <= 15.0
    # Output segments must have "title" alongside "hook_title"
    assert "title" in seg
    assert "hook_title" in seg
    assert seg["title"] == seg["hook_title"]


def test_fuse_gaming_scores_preserves_standalone_keyword_peaks():
    audio_events = [{"timestamp": 20.0, "score": 80.0}]
    keyword_events = [{"timestamp": 85.0, "score": 95.0, "matched_words": ["epic"]}]
    face_events = []

    fused = fuse_gaming_scores(audio_events, keyword_events, face_events)
    assert len(fused) == 2
    timestamps = {c["timestamp"] for c in fused}
    assert 20.0 in timestamps
    assert 85.0 in timestamps

    kw_cand = next(c for c in fused if c["timestamp"] == 85.0)
    assert kw_cand["keyword_score"] == 95.0
    assert "epic" in kw_cand["keywords"]


def test_fuse_gaming_scores_isolated_audio_penalty():
    audio_events = [{"timestamp": 50.0, "score": 80.0}]
    # Isolated loud audio spike without keyword or face reaction
    fused = fuse_gaming_scores(audio_events, [], [], isolated_audio_penalty=0.5)
    assert len(fused) == 1
    # 80.0 * 0.70 = 56.0; penalized by 0.5 -> 28.0
    assert fused[0]["score"] == pytest.approx(28.0, abs=0.5)
    assert fused[0]["isolated_audio"] is True
    assert fused[0]["converged"] is False


def test_fuse_gaming_scores_speech_prevents_isolated_penalty():
    audio_events = [{"timestamp": 50.0, "score": 80.0}]
    # Audio spike without keyword, but speech occurs around 50.0s
    speech_words = [{"word": "halo", "start": 49.0, "end": 51.0}]
    fused = fuse_gaming_scores(audio_events, [], [], speech_events=speech_words, isolated_audio_penalty=0.5)
    assert len(fused) == 1
    # Should NOT be penalized as isolated audio junk
    assert fused[0]["score"] == pytest.approx(56.0, abs=0.5)
    assert fused[0]["isolated_audio"] is False


def test_fuse_gaming_scores_converged_event():
    audio_events = [{"timestamp": 35.0, "score": 80.0}]
    keyword_events = [{"timestamp": 35.0, "score": 60.0, "matched_words": ["gila"]}]
    face_events = [{"timestamp": 35.0, "score": 70.0}]
    fused = fuse_gaming_scores(audio_events, keyword_events, face_events, convergence_boost=1.15)
    assert len(fused) == 1
    assert fused[0]["converged"] is True
    assert fused[0]["isolated_audio"] is False
    # (80*0.5 + 70*0.3 + 60*0.2) = 40 + 21 + 12 = 73.0; 73.0 * 1.15 = 83.95 -> 84.0
    assert fused[0]["score"] == pytest.approx(84.0, abs=1.0)


def test_generate_gaming_windows_adaptive_speech_boundary():
    peaks = [{"timestamp": 40.0, "score": 90.0, "keywords": ["clutch"]}]
    # Words: speech before peak with a natural pause at 24.0s (gap between 23.5 and 24.5 is 1.0s)
    # Pre-roll 18.0s -> ideal start is 22.0s. Nearest pause is at word start 24.5s.
    # Speech after peak ends at 48.0s with post-reaction pause (gap > 0.4s). Post-roll 10s -> ideal end 50.0s.
    transcript_words = [
        {"word": "awal", "start": 15.0, "end": 18.0},
        {"word": "kalimat", "start": 18.2, "end": 23.5},
        # 1.0s pause from 23.5 to 24.5
        {"word": "ayo", "start": 24.5, "end": 26.0},
        {"word": "rush", "start": 26.2, "end": 28.0},
        {"word": "b", "start": 38.0, "end": 40.5},
        {"word": "nice", "start": 41.0, "end": 43.0},
        {"word": "clutch", "start": 43.5, "end": 48.0},
        # 2.0s pause from 48.0 to 50.0
        {"word": "lanjut", "start": 50.0, "end": 52.0},
    ]

    windows = generate_gaming_windows(
        peaks,
        video_duration=120.0,
        min_duration=20.0,
        max_duration=60.0,
        pre_roll=18.0,
        post_roll=10.0,
        transcript_words=transcript_words,
    )
    assert len(windows) == 1
    seg = windows[0]
    # Snapped start to natural speech pause at 24.5s
    assert seg["start_time"] == pytest.approx(24.5, abs=0.5)
    # Snapped end to reaction conclusion at 48.0s
    assert seg["end_time"] == pytest.approx(48.0, abs=0.5)
    assert seg["start_time"] <= 40.0 <= seg["end_time"]


def test_generate_gaming_windows_adaptive_fallback_empty_transcript():
    peaks = [{"timestamp": 40.0, "score": 90.0, "keywords": ["clutch"]}]
    windows = generate_gaming_windows(
        peaks,
        video_duration=100.0,
        min_duration=20.0,
        max_duration=60.0,
        pre_roll=18.0,
        post_roll=10.0,
        transcript_words=None,
    )
    assert len(windows) == 1
    seg = windows[0]
    assert seg["start_time"] == pytest.approx(22.0, abs=0.1)
    assert seg["end_time"] == pytest.approx(50.0, abs=0.1)


def test_refine_gaming_candidates_with_llm_offline():
    candidates = [{"start_time": 10.0, "end_time": 40.0, "score": 80, "title": "CATALOG TITLE"}]
    # Offline mode returns candidates untouched
    res = refine_gaming_candidates_with_llm(candidates, ai_backend="offline")
    assert res == candidates


def test_refine_gaming_candidates_with_llm_mocked():
    candidates = [
        {
            "start_time": 20.0,
            "end_time": 50.0,
            "score": 80,
            "title": "CATALOG TITLE",
            "rubric": {"hook_strength": 8.0, "verdict": "Old verdict"},
        }
    ]
    words = [{"word": "clutch", "start": 30.0, "end": 31.0}]

    mock_llm_json = json.dumps([
        {
            "index": 0,
            "hook_title": "DETIK DETIK CLUTCH DEWA!",
            "score": 95,
            "virality_explanation": "Incredible outplay 1v3 round with shout.",
        }
    ])

    with patch("scripts.smart_clipping.query_ai_backend", return_value=mock_llm_json):
        refined = refine_gaming_candidates_with_llm(
            candidates=candidates,
            transcript_words=words,
            ai_backend="gemini",
            api_key="fake-key",
            language="id",
        )
        assert len(refined) == 1
        assert refined[0]["title"] == "DETIK DETIK CLUTCH DEWA!"
        assert refined[0]["score"] == 95
        assert refined[0]["virality_explanation"] == "Incredible outplay 1v3 round with shout."
        assert refined[0]["rubric"]["hook_strength"] == 9.5


def test_refine_gaming_candidates_with_llm_error_fallback():
    candidates = [{"start_time": 10.0, "end_time": 40.0, "score": 80, "title": "ORIGINAL TITLE"}]
    with patch("scripts.smart_clipping.query_ai_backend", side_effect=RuntimeError("API Network Timeout")):
        res = refine_gaming_candidates_with_llm(candidates, ai_backend="gemini", api_key="fake-key")
        assert res[0]["title"] == "ORIGINAL TITLE"
        assert res[0]["score"] == 80
