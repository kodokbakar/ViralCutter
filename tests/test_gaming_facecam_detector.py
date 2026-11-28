import os
import tempfile
import pytest
from scripts.gaming_facecam_detector import (
    compute_mouth_aspect_ratio,
    score_facecam_reaction,
    detect_facecam_reactions,
    auto_detect_facecam_quadrant,
    auto_detect_facecam_box,
    is_remote_or_fuse_path,
    extract_facecam_scratch_video,
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

    # When facecam is not specified and auto-detection finds nothing, returns [] immediately
    events_none = detect_facecam_reactions(
        str(dummy_video),
        facecam_box_str=None,
        candidate_timestamps=[10.0, 25.5]
    )
    assert events_none == []

    # When facecam box is explicitly provided but CV cannot open/read frames, returns neutral fallback with score 0.0
    events = detect_facecam_reactions(
        str(dummy_video),
        facecam_box_str="0.68,0.05,0.28,0.22",
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
        facecam_box_str="0.68,0.05,0.28,0.22",
        candidate_timestamps=np.array([10.0, 20.0, 30.0])
    )
    assert len(events_np) == 3
    assert [e["timestamp"] for e in events_np] == [10.0, 20.0, 30.0]

    # candidate_timestamps as tuple
    events_tuple = detect_facecam_reactions(
        str(dummy_video),
        facecam_box_str="0.68,0.05,0.28,0.22",
        candidate_timestamps=(15.0, 5.0)
    )
    assert len(events_tuple) == 2
    assert [e["timestamp"] for e in events_tuple] == [5.0, 15.0]


def test_detect_facecam_reactions_deduplicates_and_sorts(tmp_path):
    dummy_video = tmp_path / "test.mp4"
    dummy_video.write_bytes(b"dummy video data")

    events = detect_facecam_reactions(
        str(dummy_video),
        facecam_box_str="0.68,0.05,0.28,0.22",
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
    assert quadrant is None
    assert box is None


def test_auto_detect_facecam_box_nonexistent():
    box = auto_detect_facecam_box("/nonexistent/video.mp4")
    assert box is None


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


def test_auto_detect_facecam_quadrant_synthetic_bottom_right(tmp_path):
    import sys
    import numpy as np
    from unittest.mock import patch, MagicMock

    dummy_video = tmp_path / "stream_br.mp4"
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

    # Face located in bottom-right: cx = 850/1000 = 0.85, cy = 850/1000 = 0.85 (>=0.5, >=0.5)
    mock_cascade = MagicMock()
    mock_cascade.detectMultiScale.return_value = [[800, 800, 100, 100]]
    mock_cv2.CascadeClassifier.return_value = mock_cascade
    mock_cv2.data.haarcascades = "/dummy/cascades"

    with patch.dict(sys.modules, {"cv2": mock_cv2}), \
         patch("os.path.exists", return_value=True):
        quadrant, box = auto_detect_facecam_quadrant(str(dummy_video))

    assert quadrant == "bottom-right"
    assert box == FACECAM_QUADRANTS["bottom-right"]


def test_auto_detect_facecam_quadrant_no_faces_fallback(tmp_path):
    import sys
    import numpy as np
    from unittest.mock import patch, MagicMock

    dummy_video = tmp_path / "stream_none.mp4"
    dummy_video.write_text("fake video")

    mock_cv2 = MagicMock()
    mock_cap = MagicMock()
    mock_cap.isOpened.return_value = True
    mock_cap.get.side_effect = lambda prop: {
        mock_cv2.CAP_PROP_FRAME_WIDTH: 1000,
        mock_cv2.CAP_PROP_FRAME_HEIGHT: 1000,
        mock_cv2.CAP_PROP_FRAME_COUNT: 100,
    }.get(prop, 0)

    mock_cap.read.return_value = (True, np.zeros((1000, 1000, 3), dtype=np.uint8))
    mock_cv2.VideoCapture.return_value = mock_cap

    # No faces detected by cascade
    mock_cascade = MagicMock()
    mock_cascade.detectMultiScale.return_value = []
    mock_cv2.CascadeClassifier.return_value = mock_cascade
    mock_cv2.data.haarcascades = "/dummy/cascades"

    with patch.dict(sys.modules, {"cv2": mock_cv2}), \
         patch("os.path.exists", return_value=True):
        quadrant, box = auto_detect_facecam_quadrant(str(dummy_video))

    assert quadrant is None
    assert box is None


def test_detect_facecam_reactions_disabled_early_exit(tmp_path):
    import sys
    from unittest.mock import patch, MagicMock

    dummy_video = tmp_path / "stream_disabled.mp4"
    dummy_video.write_bytes(b"dummy video")

    mock_cv2 = MagicMock()
    with patch.dict(sys.modules, {"cv2": mock_cv2}), \
         patch("scripts.gaming_facecam_detector.auto_detect_facecam_box") as mock_auto:
        for disabled_val in ["none", "None", "off", "OFF", "no", "false", "False"]:
            res = detect_facecam_reactions(
                str(dummy_video),
                facecam_box_str=disabled_val,
                candidate_timestamps=[10.0, 20.0]
            )
            assert res == []

    # Neither cv2.VideoCapture nor auto_detect_facecam_box was invoked
    assert not mock_cv2.VideoCapture.called
    assert not mock_auto.called


def test_detect_facecam_reactions_zero_votes_early_exit(tmp_path):
    import sys
    from unittest.mock import patch, MagicMock

    dummy_video = tmp_path / "stream_zero_votes.mp4"
    dummy_video.write_bytes(b"dummy video")

    mock_cv2 = MagicMock()
    with patch.dict(sys.modules, {"cv2": mock_cv2}), \
         patch("scripts.gaming_facecam_detector.auto_detect_facecam_box", return_value=None):
        res = detect_facecam_reactions(
            str(dummy_video),
            facecam_box_str="auto",
            candidate_timestamps=[15.0, 30.0]
        )
        assert res == []

    # Reaction frame capture was never opened
    assert not mock_cv2.VideoCapture.called


def test_auto_detect_facecam_quadrant_min_votes(tmp_path):
    import sys
    import numpy as np
    from unittest.mock import patch, MagicMock

    dummy_video = tmp_path / "stream_min_votes.mp4"
    dummy_video.write_text("fake video")

    mock_cv2 = MagicMock()
    mock_cap = MagicMock()
    mock_cap.isOpened.return_value = True
    mock_cap.get.side_effect = lambda prop: {
        mock_cv2.CAP_PROP_FRAME_WIDTH: 1000,
        mock_cv2.CAP_PROP_FRAME_HEIGHT: 1000,
        mock_cv2.CAP_PROP_FRAME_COUNT: 100,
    }.get(prop, 0)

    mock_cap.read.return_value = (True, np.zeros((1000, 1000, 3), dtype=np.uint8))
    mock_cv2.VideoCapture.return_value = mock_cap

    # Exactly 1 detection in top-left
    mock_cascade = MagicMock()
    mock_cascade.detectMultiScale.side_effect = [
        [[50, 50, 100, 100]],  # 1st sample frame: face detected
        [], [], [], [],         # subsequent samples: no face
    ]
    mock_cv2.CascadeClassifier.return_value = mock_cascade
    mock_cv2.data.haarcascades = "/dummy/cascades"

    with patch.dict(sys.modules, {"cv2": mock_cv2}), \
         patch("os.path.exists", return_value=True):
        # min_votes=1 -> winner is top-left
        q1, b1 = auto_detect_facecam_quadrant(str(dummy_video), min_votes=1)
        assert q1 == "top-left"
        assert b1 == FACECAM_QUADRANTS["top-left"]

        # Reset side_effect for second run
        mock_cascade.detectMultiScale.side_effect = [
            [[50, 50, 100, 100]],
            [], [], [], [],
        ]
        # min_votes=2 -> 1 vote is not enough, returns (None, None)
        q2, b2 = auto_detect_facecam_quadrant(str(dummy_video), min_votes=2)
        assert q2 is None
        assert b2 is None


def test_detect_facecam_reactions_edge_cases(tmp_path):
    dummy_video = tmp_path / "edge_case.mp4"
    dummy_video.write_bytes(b"dummy video")

    # None video path
    assert detect_facecam_reactions(None) == []
    assert detect_facecam_reactions("") == []
    assert detect_facecam_reactions(12345) == []

    # Empty candidate timestamps or malformed candidates
    assert detect_facecam_reactions(str(dummy_video), candidate_timestamps=[]) == []
    assert detect_facecam_reactions(str(dummy_video), candidate_timestamps=None) == []
    assert detect_facecam_reactions(str(dummy_video), candidate_timestamps=[-5.0, "invalid", None, float("nan")]) == []

    # Whitespace variations in disabled facecam_box_str
    for disabled_val in [" none ", " OFF \n", "\tno\t", "False", " FALSE "]:
        assert detect_facecam_reactions(
            str(dummy_video),
            facecam_box_str=disabled_val,
            candidate_timestamps=[10.0, 20.0]
        ) == []

    # Malformed facecam crop string fallback (when box is not disabled)
    # OpenCV won't open dummy video bytes, so it falls back to neutral reactions
    events = detect_facecam_reactions(
        str(dummy_video),
        facecam_box_str="malformed,box,not,floats",
        candidate_timestamps=[5.0]
    )
    assert len(events) == 1
    assert events[0]["score"] == 0.0
    assert events[0]["timestamp"] == 5.0


def test_is_remote_or_fuse_path():
    assert is_remote_or_fuse_path("/content/drive/MyDrive/game.mp4") is True
    assert is_remote_or_fuse_path("/content/drive") is True
    assert is_remote_or_fuse_path("/mnt/drive/test.mp4") is True
    assert is_remote_or_fuse_path(r"\content\drive\video.mp4") is True
    assert is_remote_or_fuse_path(r"/content\drive/sub/video.mp4") is True
    assert is_remote_or_fuse_path("/mnt/drive\\video.mp4") is True
    assert is_remote_or_fuse_path("/tmp/local.mp4") is False
    assert is_remote_or_fuse_path("relative/path/test.mp4") is False
    assert is_remote_or_fuse_path("") is False
    assert is_remote_or_fuse_path(None) is False
    assert is_remote_or_fuse_path(12345) is False


def test_extract_facecam_scratch_disk_space_fallback():
    import collections
    from unittest.mock import patch

    Usage = collections.namedtuple("Usage", ["total", "used", "free"])
    with patch("shutil.disk_usage", return_value=Usage(100 * 1024 * 1024, 95 * 1024 * 1024, 5 * 1024 * 1024)):
        result = extract_facecam_scratch_video("any_video.mp4", "0.68,0.05,0.28,0.22")
        assert result is None


def test_extract_facecam_scratch_ffmpeg_failure_fallback():
    import collections
    import subprocess
    from unittest.mock import patch

    Usage = collections.namedtuple("Usage", ["total", "used", "free"])
    created_files = []
    real_named_temp = tempfile.NamedTemporaryFile

    def tracking_temp_file(*args, **kwargs):
        f = real_named_temp(*args, **kwargs)
        created_files.append(f.name)
        return f

    with patch("shutil.disk_usage", return_value=Usage(1000 * 1024 * 1024, 100 * 1024 * 1024, 900 * 1024 * 1024)), \
         patch("tempfile.NamedTemporaryFile", side_effect=tracking_temp_file), \
         patch("subprocess.run", side_effect=subprocess.CalledProcessError(1, "ffmpeg")):
        result = extract_facecam_scratch_video("any_video.mp4", "0.68,0.05,0.28,0.22")
        assert result is None

    assert len(created_files) == 1
    assert not os.path.exists(created_files[0])


def test_detect_facecam_reactions_fuse_scratch_lifecycle(tmp_path):
    import sys
    import numpy as np
    from unittest.mock import patch, MagicMock

    fuse_video = "/content/drive/MyDrive/gaming.mp4"
    dummy_scratch = tmp_path / "facecam_scratch_123.mp4"
    dummy_scratch.write_bytes(b"scratch data")

    mock_cv2 = MagicMock()
    mock_cap = MagicMock()
    mock_cap.isOpened.return_value = True
    mock_cap.get.side_effect = lambda prop: {
        mock_cv2.CAP_PROP_FRAME_WIDTH: 640,
        mock_cv2.CAP_PROP_FRAME_HEIGHT: 360,
        mock_cv2.CAP_PROP_FPS: 30.0,
        mock_cv2.CAP_PROP_FRAME_COUNT: 100,
    }.get(prop, 0)
    mock_cap.read.return_value = (True, np.zeros((360, 640, 3), dtype=np.uint8))
    mock_cv2.VideoCapture.return_value = mock_cap

    with patch.dict(sys.modules, {"cv2": mock_cv2}), \
         patch("os.path.exists", side_effect=lambda p: True if p in (fuse_video, str(dummy_scratch)) else os.path.exists(p)), \
         patch("scripts.gaming_facecam_detector.extract_facecam_scratch_video", return_value=str(dummy_scratch)) as mock_extract:

        reactions = detect_facecam_reactions(
            fuse_video,
            facecam_box_str="0.68,0.05,0.28,0.22",
            candidate_timestamps=[5.0, 10.0]
        )

        mock_extract.assert_called_once_with(
            fuse_video,
            "0.68,0.05,0.28,0.22",
            max_timestamp=10.0
        )
        mock_cv2.VideoCapture.assert_called_once_with(str(dummy_scratch))
        # The scratch file must be removed in finally:
        assert not dummy_scratch.exists()
        assert mock_cap.release.called
        assert len(reactions) == 2


def test_detect_facecam_reactions_fuse_cleanup_on_error(tmp_path):
    import sys
    from unittest.mock import patch, MagicMock

    fuse_video = "/content/drive/MyDrive/gaming.mp4"
    dummy_scratch = tmp_path / "facecam_scratch_err.mp4"
    dummy_scratch.write_bytes(b"scratch data")

    mock_cv2 = MagicMock()
    mock_cv2.VideoCapture.side_effect = RuntimeError("OpenCV decoder error")

    with patch.dict(sys.modules, {"cv2": mock_cv2}), \
         patch("os.path.exists", side_effect=lambda p: True if p in (fuse_video, str(dummy_scratch)) else os.path.exists(p)), \
         patch("scripts.gaming_facecam_detector.extract_facecam_scratch_video", return_value=str(dummy_scratch)):

        res = detect_facecam_reactions(
            fuse_video,
            facecam_box_str="0.68,0.05,0.28,0.22",
            candidate_timestamps=[5.0]
        )
        assert len(res) == 1
        assert res[0]["score"] == 0.0

    assert not dummy_scratch.exists()


def test_detect_facecam_reactions_local_path_bypasses_scratch(tmp_path):
    import sys
    from unittest.mock import patch, MagicMock

    local_video = tmp_path / "local_stream.mp4"
    local_video.write_bytes(b"fake data")

    mock_cv2 = MagicMock()
    mock_cap = MagicMock()
    mock_cap.isOpened.return_value = False
    mock_cv2.VideoCapture.return_value = mock_cap

    with patch.dict(sys.modules, {"cv2": mock_cv2}), \
         patch("scripts.gaming_facecam_detector.extract_facecam_scratch_video") as mock_extract:

        detect_facecam_reactions(
            str(local_video),
            facecam_box_str="0.68,0.05,0.28,0.22",
            candidate_timestamps=[5.0]
        )

        assert not mock_extract.called
        mock_cv2.VideoCapture.assert_called_once_with(str(local_video))
