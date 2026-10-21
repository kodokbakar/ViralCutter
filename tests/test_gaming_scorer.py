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
)


def test_fuse_gaming_scores():
    audio_events = [{"timestamp": 30.0, "score": 80.0}]
    keyword_events = [{"timestamp": 30.0, "score": 90.0}]
    face_events = [{"timestamp": 30.0, "score": 70.0}]

    fused = fuse_gaming_scores(audio_events, keyword_events, face_events)
    assert len(fused) == 1
    # 80*0.5 + 70*0.3 + 90*0.2 = 40 + 21 + 18 = 79.0
    assert fused[0]["score"] == pytest.approx(79.0, abs=1.0)
    assert fused[0]["timestamp"] == 30.0


def test_fuse_gaming_scores_without_face():
    # When facecam is missing or score is 0: audio=0.70, kw=0.30
    audio_events = [{"timestamp": 25.0, "score": 80.0}]
    keyword_events = [{"timestamp": 25.0, "score": 60.0}]
    face_events = [{"timestamp": 25.0, "score": 0.0}]

    fused = fuse_gaming_scores(audio_events, keyword_events, face_events)
    assert len(fused) == 1
    # 80*0.7 + 60*0.3 = 56 + 18 = 74.0
    assert fused[0]["score"] == pytest.approx(74.0, abs=1.0)
    assert fused[0]["timestamp"] == 25.0

def test_fuse_gaming_scores_with_numpy_or_tuples():
    import numpy as np
    audio_events = [{"timestamp": 30.0, "score": 80.0}]
    keyword_events = tuple([{"timestamp": 30.0, "score": 90.0}])
    face_events = np.array([{"timestamp": 30.0, "score": 70.0}], dtype=object)

    fused = fuse_gaming_scores(audio_events, keyword_events, face_events)
    assert len(fused) == 1
    assert fused[0]["score"] == pytest.approx(79.0, abs=1.0)



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
