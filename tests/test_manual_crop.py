import pytest
from scripts.gaming_split import (
    DEFAULT_MANUAL_CROP_BOX,
    build_manual_crop_filter,
    render_manual_crop_clip,
)

def test_default_manual_crop_box_is_valid_9_16():
    parts = [float(p) for p in DEFAULT_MANUAL_CROP_BOX.split(",")]
    x, y, w, h = parts
    assert len(parts) == 4
    assert 0.0 <= x <= 1.0
    assert 0.0 <= y <= 1.0
    assert 0.0 < w <= 1.0
    assert 0.0 < h <= 1.0
    # In 16:9 frame (1920x1080), a 9:16 crop box of height 1.0 has width (9/16)/(16/9) = 81/256 ≈ 0.3164
    # Or normalized to canvas width & height: (w * 1920) / (h * 1080) == 9/16
    pixel_w = w * 1920
    pixel_h = h * 1080
    assert (pixel_w / pixel_h) == pytest.approx(9 / 16, abs=0.01)

def test_build_manual_crop_filter():
    filt = build_manual_crop_filter(
        crop_box=DEFAULT_MANUAL_CROP_BOX,
        src_w=1920,
        src_h=1080
    )
    assert "crop=" in filt
    assert "scale=1080:1920:flags=lanczos" in filt

def test_manual_crop_cli_flag_in_help():
    import subprocess
    import sys
    res = subprocess.run([sys.executable, "main_improved.py", "--help"], capture_output=True, text=True, check=True)
    assert "--manual-crop" in res.stdout

def test_job_run_request_manual_crop_mapping():
    from webui.backend.schemas.jobs import JobRunRequest
    req = JobRunRequest(
        video_path="/tmp/v.mp4",
        orientation="9:16",
        manual_crop="0.1,0.0,0.5625,1.0"
    )
    args = req.to_cli_args(python_exec="python", script_path="main_improved.py")
    assert "--manual-crop" in args
    assert "0.1,0.0,0.5625,1.0" in args

def test_render_manual_crop_clip_e2e(tmp_path):
    import subprocess
    from scripts.gaming_split import probe_video_dimensions

    in_vid = str(tmp_path / "in16x9.mp4")
    out_vid = str(tmp_path / "out9x16.mp4")

    # Create 2s 1280x720 video
    subprocess.run([
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", "testsrc=duration=2:size=1280x720:rate=25",
        "-f", "lavfi", "-i", "sine=frequency=1000:duration=2",
        "-c:v", "libx264", "-preset", "ultrafast", "-c:a", "aac",
        in_vid
    ], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    res = render_manual_crop_clip(in_vid, out_vid, "0.3418,0.0,0.3164,1.0")
    assert res == out_vid
    w, h = probe_video_dimensions(out_vid)
    assert w == 1080
    assert h == 1920
