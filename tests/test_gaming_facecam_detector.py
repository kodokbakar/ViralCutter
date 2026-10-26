import pytest
from scripts.gaming_facecam_detector import (
    compute_mouth_aspect_ratio,
    score_facecam_reaction,
    detect_facecam_reactions,
    auto_detect_facecam_quadrant,
    auto_detect_facecam_box,
    FACECAM_QUADRANTS,
)


def test_compute_mouth_aspect_ratio_closed_mouth():
    # 4/5 landmarks standard or custom points
    # p0: left corner, p1: right corner, p2: top lip, p3: bottom lip
    landmarks = [(10.0, 50.0), (90.0, 50.0), (50.0, 48.0), (50.0, 52.0)]
    mar = compute_mouth_aspect_ratio(landmarks)
    assert mar < 0.08


def test_compute_mouth_aspect_ratio_open_mouth():
    landmarks = [(10.0, 50.0), (90.0, 50.0), (50.0, 30.0), (50.0, 70.0)]
    mar = compute_mouth_aspect_ratio(landmarks)
    assert mar > 0.25


def test_compute_mouth_aspect_ratio_edge_cases():
    # Empty or insufficient landmarks
    assert compute_mouth_aspect_ratio([]) == 0.0
    assert compute_mouth_aspect_ratio([(10.0, 20.0), (30.0, 40.0)]) == 0.0
    assert compute_mouth_aspect_ratio(None) == 0.0

    # Zero width / degenerate points
    degenerate = [(50.0, 50.0), (50.0, 50.0), (50.0, 40.0), (50.0, 60.0)]
    assert compute_mouth_aspect_ratio(degenerate) == 0.0

    # NaN / Inf coordinates
    nan_landmarks = [(float("nan"), 50.0), (90.0, 50.0), (50.0, 30.0), (50.0, 70.0)]
    assert compute_mouth_aspect_ratio(nan_landmarks) == 0.0

    # Invalid items
    invalid_landmarks = ["not", "valid", "tuples", "here"]
    assert compute_mouth_aspect_ratio(invalid_landmarks) == 0.0


def test_score_facecam_reaction():
    # Normal talking
    score_norm = score_facecam_reaction(mar=0.05, motion_velocity=2.0)
    assert score_norm < 50.0

    # Screaming / Laughing / Jumping
    score_hype = score_facecam_reaction(mar=0.18, motion_velocity=25.0)
    assert score_hype >= 80.0


def test_score_facecam_reaction_edge_cases():
    # Extreme values clamp to 100.0
    score_extreme = score_facecam_reaction(mar=1.0, motion_velocity=500.0)
    assert score_extreme == 100.0

    # Negative values clamp to 0.0
    score_neg = score_facecam_reaction(mar=-0.5, motion_velocity=-10.0)
    assert score_neg == 0.0

    # NaN / Inf handling
    score_nan = score_facecam_reaction(mar=float("nan"), motion_velocity=float("inf"))
    assert 0.0 <= score_nan <= 100.0

    # String parameter casting
    score_str = score_facecam_reaction(mar="0.18", motion_velocity="25.0")
    assert score_str >= 80.0

    # Low motion velocity (<= 3.0 gives 0 motion score)
    score_low_motion = score_facecam_reaction(mar=0.0, motion_velocity=2.5)
    assert score_low_motion == 0.0


def test_detect_facecam_reactions_empty_or_missing_file():
    events = detect_facecam_reactions("nonexistent_video.mp4")
    assert events == []
    assert detect_facecam_reactions("") == []
    assert detect_facecam_reactions(None) == []


def test_detect_facecam_reactions_empty_candidates(tmp_path):
    dummy_video = tmp_path / "test.mp4"
    dummy_video.write_bytes(b"dummy video data")

    assert detect_facecam_reactions(str(dummy_video), candidate_timestamps=[]) == []
    assert detect_facecam_reactions(str(dummy_video), candidate_timestamps=None) == []


def test_detect_facecam_reactions_fallback(tmp_path):
    dummy_video = tmp_path / "test.mp4"
    dummy_video.write_bytes(b"dummy video data")

    # When CV is unavailable or facecam is not specified, returns neutral fallback with score 0.0
    events = detect_facecam_reactions(
        str(dummy_video),
        facecam_box_str=None,
        candidate_timestamps=[10.0, 25.5]
    )
    assert len(events) == 2
    assert events[0]["timestamp"] == 10.0
    assert events[0]["score"] == 0.0
    assert events[1]["timestamp"] == 25.5
    assert events[1]["score"] == 0.0
    assert "mar" in events[0]
    assert "motion_velocity" in events[0]


def test_detect_facecam_reactions_sanitizes_timestamps(tmp_path):
    dummy_video = tmp_path / "test.mp4"
    dummy_video.write_bytes(b"dummy video data")

    # Mixed valid and invalid timestamps
    events = detect_facecam_reactions(
        str(dummy_video),
        facecam_box_str="0.68,0.05,0.28,0.1493",
        candidate_timestamps=[5.0, float("nan"), -10.0, 15.25]
    )
    assert len(events) == 2
    assert events[0]["timestamp"] == 5.0
    assert events[1]["timestamp"] == 15.25


def test_compute_mouth_aspect_ratio_numpy_ndarray():
    import numpy as np

    arr_closed = np.array([(10.0, 50.0), (90.0, 50.0), (50.0, 48.0), (50.0, 52.0)])
    assert compute_mouth_aspect_ratio(arr_closed) < 0.08

    arr_open = np.array([(10.0, 50.0), (90.0, 50.0), (50.0, 30.0), (50.0, 70.0)])
    assert compute_mouth_aspect_ratio(arr_open) > 0.25

    arr_empty = np.zeros((0, 2))
    assert compute_mouth_aspect_ratio(arr_empty) == 0.0


def test_score_facecam_reaction_boolean_inputs():
    assert score_facecam_reaction(mar=True, motion_velocity=False) == 0.0
    assert score_facecam_reaction(mar=False, motion_velocity=True) == 0.0
    assert score_facecam_reaction(mar=True, motion_velocity=True) == 0.0


def test_detect_facecam_reactions_numpy_and_tuples(tmp_path):
    import numpy as np

    dummy_video = tmp_path / "test.mp4"
    dummy_video.write_bytes(b"dummy video data")

    # candidate_timestamps as numpy array
    events_np = detect_facecam_reactions(
        str(dummy_video),
        candidate_timestamps=np.array([10.0, 20.0, 30.0])
    )
    assert len(events_np) == 3
    assert [e["timestamp"] for e in events_np] == [10.0, 20.0, 30.0]

    # candidate_timestamps as tuple
    events_tuple = detect_facecam_reactions(
        str(dummy_video),
        candidate_timestamps=(15.0, 5.0)
    )
    assert len(events_tuple) == 2
    assert [e["timestamp"] for e in events_tuple] == [5.0, 15.0]


def test_detect_facecam_reactions_deduplicates_and_sorts(tmp_path):
    dummy_video = tmp_path / "test.mp4"
    dummy_video.write_bytes(b"dummy video data")

    events = detect_facecam_reactions(
        str(dummy_video),
        candidate_timestamps=[30.0, 10.0, 30.0, 20.0, 10.0]
    )
    assert len(events) == 3
    assert [e["timestamp"] for e in events] == [10.0, 20.0, 30.0]

def test_detect_facecam_reactions_frame_sampling_mocked(tmp_path):
    import sys
    import numpy as np
    from unittest.mock import MagicMock, patch

    dummy_video = tmp_path / "stream.mp4"
    dummy_video.write_bytes(b"dummy")

    # Create mock cv2 and capture
    mock_cv2 = MagicMock()
    mock_cap = MagicMock()
    mock_cap.isOpened.return_value = True
    mock_cap.get.side_effect = lambda prop: {
        mock_cv2.CAP_PROP_FPS: 30.0,
        mock_cv2.CAP_PROP_FRAME_WIDTH: 1280,
        mock_cv2.CAP_PROP_FRAME_HEIGHT: 720,
        mock_cv2.CAP_PROP_FRAME_COUNT: 600,
    }.get(prop, 0)

    # 720x1280 mock frame
    dummy_frame = np.zeros((720, 1280, 3), dtype=np.uint8)
    mock_cap.read.return_value = (True, dummy_frame)
    mock_cv2.VideoCapture.return_value = mock_cap

    # Mock face with landmarks
    mock_face = MagicMock()
    mock_face.bbox = [100.0, 100.0, 300.0, 300.0]
    # Open mouth landmarks: MAR ~ 0.5
    mock_face.landmarks = [(10.0, 50.0), (90.0, 50.0), (50.0, 30.0), (50.0, 70.0)]

    mock_insight_app = MagicMock()
    mock_insight_app.get.return_value = [mock_face]

    with patch.dict(sys.modules, {"cv2": mock_cv2}), \
         patch("scripts.face_detection_insightface.init_insightface", return_value=mock_insight_app):
        events = detect_facecam_reactions(
            str(dummy_video),
            facecam_box_str="0.68,0.05,0.28,0.30",
            candidate_timestamps=[10.0]
        )

    assert len(events) == 1
    ev = events[0]
    assert ev["timestamp"] == 10.0
    assert ev["mar"] > 0.2
    assert ev["score"] > 50.0
    assert mock_cap.release.called


def test_auto_detect_facecam_quadrant_nonexistent():
    quadrant, box = auto_detect_facecam_quadrant("/nonexistent/video.mp4")
    assert quadrant == "top-right"
    assert box == FACECAM_QUADRANTS["top-right"]


def test_auto_detect_facecam_box_nonexistent():
    box = auto_detect_facecam_box("/nonexistent/video.mp4")
    assert box == FACECAM_QUADRANTS["top-right"]


def test_auto_detect_facecam_quadrant_synthetic_top_left(tmp_path):
    import sys
    import numpy as np
    from unittest.mock import patch, MagicMock

    dummy_video = tmp_path / "stream_tl.mp4"
    dummy_video.write_text("fake video")

    mock_cv2 = MagicMock()
    mock_cap = MagicMock()
    mock_cap.isOpened.return_value = True
    mock_cap.get.side_effect = lambda prop: {
        mock_cv2.CAP_PROP_FRAME_WIDTH: 1000,
        mock_cv2.CAP_PROP_FRAME_HEIGHT: 1000,
        mock_cv2.CAP_PROP_FRAME_COUNT: 100,
    }.get(prop, 0)

    dummy_frame = np.zeros((1000, 1000, 3), dtype=np.uint8)
    mock_cap.read.return_value = (True, dummy_frame)
    mock_cv2.VideoCapture.return_value = mock_cap

    # Face located in top-left: cx = 100/1000 = 0.1, cy = 100/1000 = 0.1 (<0.5, <0.5)
    mock_cascade = MagicMock()
    mock_cascade.detectMultiScale.return_value = [[50, 50, 100, 100]]
    mock_cv2.CascadeClassifier.return_value = mock_cascade
    mock_cv2.data.haarcascades = "/dummy/cascades"

    with patch.dict(sys.modules, {"cv2": mock_cv2}), \
         patch("os.path.exists", return_value=True):
        quadrant, box = auto_detect_facecam_quadrant(str(dummy_video))

    assert quadrant == "top-left"
    assert box == FACECAM_QUADRANTS["top-left"]
