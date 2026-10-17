import pytest
from unittest.mock import patch
from scripts.gaming_split import (
    parse_normalized_box,
    to_pixel_box,
    build_gaming_split_filter,
    render_gaming_split_clip,
    probe_video_dimensions,
)

def test_parse_normalized_box_valid():
    x, y, w, h = parse_normalized_box("0.1, 0.2, 0.5, 0.4")
    assert x == pytest.approx(0.1)
    assert y == pytest.approx(0.2)
    assert w == pytest.approx(0.5)
    assert h == pytest.approx(0.4)

def test_parse_normalized_box_clamping():
    x, y, w, h = parse_normalized_box("-0.5, 1.5, 2.0, 0.02")
    assert x == 0.0
    assert y == pytest.approx(0.95)
    assert w == 1.0
    assert h == 0.05  # Minimum height guard
    assert x + w <= 1.0
    assert y + h <= 1.0

def test_boundary_edge_case():
    x, y, w, h = parse_normalized_box("1.0, 1.0, 0.5, 0.5")
    assert x + w <= 1.0
    assert y + h <= 1.0
    assert x == pytest.approx(0.5)
    assert y == pytest.approx(0.5)

    px_x, px_y, px_w, px_h = to_pixel_box("1.0, 1.0, 0.5, 0.5", 1920, 1080)
    assert px_x + px_w <= 1920
    assert px_y + px_h <= 1080
def test_parse_normalized_box_invalid():
    # Empty or malformed falls back to defaults or safe fallbacks
    x, y, w, h = parse_normalized_box("")
    assert 0.0 <= x <= 1.0
    assert 0.0 <= y <= 1.0
    assert 0.05 <= w <= 1.0
    assert 0.05 <= h <= 1.0

def test_to_pixel_box_even_integers():
    # Source 1920x1080
    px_x, px_y, px_w, px_h = to_pixel_box("0.051, 0.081, 0.281, 0.351", 1920, 1080)
    assert px_x % 2 == 0
    assert px_y % 2 == 0
    assert px_w % 2 == 0
    assert px_h % 2 == 0
    assert px_w > 0
    assert px_h > 0
    assert px_x + px_w <= 1920
    assert px_y + px_h <= 1080

def test_build_gaming_split_filter():
    filt = build_gaming_split_filter(
        facecam_box="0.68,0.05,0.28,0.15",
        gameplay_box="0.25,0.0,0.50,0.62",
        src_w=1920,
        src_h=1080
    )
    assert "split=2" in filt
    assert "scale=1080:576" in filt
    assert "scale=1080:1344" in filt
    assert "vstack=inputs=2" in filt

def test_render_gaming_split_clip_missing_input(tmp_path):
    with pytest.raises(FileNotFoundError):
        render_gaming_split_clip(str(tmp_path / "non_existent_input.mp4"), str(tmp_path / "out.mp4"))

@patch("scripts.gaming_split.probe_video_dimensions", return_value=(1920, 1080))
@patch("subprocess.run")
def test_render_gaming_split_clip_ffmpeg_invocation(mock_run, mock_probe, tmp_path):
    in_file = tmp_path / "in.mp4"
    in_file.write_text("dummy")
    out_file = tmp_path / "out.mp4"
    out = render_gaming_split_clip(str(in_file), str(out_file))
    assert out == str(out_file)
    assert mock_run.call_count == 1
    cmd = mock_run.call_args[0][0]
    assert cmd[0] == "ffmpeg"
    assert "-filter_complex" in cmd
    assert "-c:a" in cmd
    assert "-pix_fmt" in cmd
    assert cmd[cmd.index("-pix_fmt") + 1] == "yuv420p"
@patch("scripts.gaming_split.probe_video_dimensions", return_value=(1920, 1080))
@patch("subprocess.run")
def test_render_gaming_split_clip_fallback_aac(mock_run, mock_probe, tmp_path):
    import subprocess
    in_file = tmp_path / "in.mp4"
    in_file.write_text("dummy")
    out_file = tmp_path / "out.mp4"
    mock_run.side_effect = [
        subprocess.CalledProcessError(1, ["ffmpeg"]),
        subprocess.CompletedProcess(["ffmpeg"], 0),
    ]
    out = render_gaming_split_clip(str(in_file), str(out_file))
    assert out == str(out_file)
    assert mock_run.call_count == 2
    second_cmd = mock_run.call_args_list[1][0][0]
    assert second_cmd[second_cmd.index("-c:a") + 1] == "aac"
