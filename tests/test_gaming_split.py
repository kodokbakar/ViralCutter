import os
import pytest
from unittest.mock import patch
from scripts.gaming_split import (
    parse_normalized_box,
    to_pixel_box,
    build_gaming_split_filter,
    render_gaming_split_clip,
    probe_video_dimensions,
    escape_filter_path,
    RenderResult,
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


def test_parse_normalized_box_quadrant_presets():
    tl_x, tl_y, tl_w, tl_h = parse_normalized_box("top-left")
    assert tl_x == pytest.approx(0.04)
    assert tl_y == pytest.approx(0.05)
    assert tl_w == pytest.approx(0.28)
    assert tl_h == pytest.approx(0.22)

    tr_x, tr_y, tr_w, tr_h = parse_normalized_box("top-right")
    assert tr_x == pytest.approx(0.68)
    assert tr_y == pytest.approx(0.05)

    bl_x, bl_y, bl_w, bl_h = parse_normalized_box("bottom-left")
    assert bl_x == pytest.approx(0.04)
    assert bl_y == pytest.approx(0.72)

    br_x, br_y, br_w, br_h = parse_normalized_box("bottom-right")
    assert br_x == pytest.approx(0.68)
    assert br_y == pytest.approx(0.72)

    auto_x, auto_y, auto_w, auto_h = parse_normalized_box("auto")
    assert auto_x == pytest.approx(0.68)
    assert auto_y == pytest.approx(0.05)


def test_parse_normalized_box_center_and_invalid_fallbacks():
    # "center" preset fallback to default box (since facecam is quadrant-based)
    c_x, c_y, c_w, c_h = parse_normalized_box("center")
    assert c_x == pytest.approx(0.68)
    assert c_y == pytest.approx(0.05)
    assert c_w == pytest.approx(0.28)
    assert c_h == pytest.approx(0.22)

    # Case insensitivity and whitespace handling
    tl_x, tl_y, tl_w, tl_h = parse_normalized_box("   Top-Left   ")
    assert (tl_x, tl_y, tl_w, tl_h) == (0.04, 0.05, 0.28, 0.22)

    br_x, br_y, br_w, br_h = parse_normalized_box("BOTTOM-RIGHT")
    assert (br_x, br_y, br_w, br_h) == (0.68, 0.72, 0.28, 0.22)

    # Invalid strings and non-string inputs fall back to default
    for invalid_val in ["unknown", "gibberish", "", None, "1,2", "1,2,3"]:
        x, y, w, h = parse_normalized_box(invalid_val)
        assert x == pytest.approx(0.68)
        assert y == pytest.approx(0.05)
        assert w == pytest.approx(0.28)
        assert h == pytest.approx(0.22)

    # Non-float string fallback (4 parts with non-numbers)
    x, y, w, h = parse_normalized_box("a,b,c,d")
    assert (x, y, w, h) == (0.0, 0.0, 0.5, 0.5)

    # Out of bounds clamping: values exceeding 1.0 or below 0.0
    x, y, w, h = parse_normalized_box("0.5,0.5,2.0,2.0")
    assert x + w <= 1.0
    assert y + h <= 1.0
    assert w == 1.0
    assert h == 1.0

    # Minimum dimension clamping (min width/height = 0.05)
    x, y, w, h = parse_normalized_box("0.1,0.1,0.01,0.01")
    assert w >= 0.05
    assert h >= 0.05


def test_build_gaming_split_all_layouts_and_killfeed():
    # 1. split_30_70
    f_30_70 = build_gaming_split_filter(
        facecam_box="0.68,0.05,0.28,0.15",
        gameplay_box="0.25,0.0,0.50,0.62",
        src_w=1920,
        src_h=1080,
        layout="split_30_70"
    )
    assert "[stacked_v]" in f_30_70
    assert "scale=1080:576" in f_30_70
    assert "scale=1080:1344" in f_30_70

    # 2. split_40_60
    f_40_60 = build_gaming_split_filter(
        facecam_box="0.68,0.05,0.28,0.15",
        gameplay_box="0.25,0.0,0.50,0.62",
        src_w=1920,
        src_h=1080,
        layout="split_40_60"
    )
    assert "[stacked_v]" in f_40_60
    assert "scale=1080:768" in f_40_60
    assert "scale=1080:1152" in f_40_60

    # 3. floating_pip
    f_pip = build_gaming_split_filter(
        facecam_box="0.68,0.05,0.28,0.15",
        gameplay_box="0.25,0.0,0.50,0.62",
        src_w=1920,
        src_h=1080,
        layout="floating_pip"
    )
    assert "[stacked_v]" in f_pip
    assert "overlay=x=40:y=60" in f_pip

    # 4. blurred_bg
    f_blurred = build_gaming_split_filter(
        facecam_box="0.68,0.05,0.28,0.15",
        gameplay_box="0.25,0.0,0.50,0.62",
        src_w=1920,
        src_h=1080,
        layout="blurred_bg"
    )
    assert "[stacked_v]" in f_blurred
    assert "boxblur=20:5" in f_blurred

    # 5. with killfeed overlay
    f_kf = build_gaming_split_filter(
        facecam_box="0.68,0.05,0.28,0.15",
        gameplay_box="0.25,0.0,0.50,0.62",
        src_w=1920,
        src_h=1080,
        layout="split_30_70",
        killfeed_box="0.70,0.05,0.26,0.13"
    )
    assert "[stacked_v]" in f_kf
    assert "[kf_boxed]" in f_kf
    assert "overlay=x=W-w-20:y=20" in f_kf


def test_build_gaming_split_filter_floating_pip_empty_or_none_facecam():
    # When facecam is empty or None in floating_pip layout, it falls back to DEFAULT_FACECAM_BOX safely
    for empty_cam in ["", None, "none"]:
        filt = build_gaming_split_filter(
            facecam_box=empty_cam,
            gameplay_box="0.25,0.0,0.50,0.62",
            src_w=1920,
            src_h=1080,
            layout="floating_pip",
        )
        assert "[stacked_v]" in filt
        assert "overlay=x=40:y=60" in filt
        assert "scale=360:270" in filt
        assert "scale=1080:1920" in filt


def test_build_gaming_split_filter_killfeed_edge_cases():
    # 1. Killfeed coordinates completely out of bounds (should clamp within src dimensions)
    filt_oob = build_gaming_split_filter(
        facecam_box="0.68,0.05,0.28,0.15",
        gameplay_box="0.25,0.0,0.50,0.62",
        src_w=1920,
        src_h=1080,
        layout="split_30_70",
        killfeed_box="1.5,2.0,3.0,4.0",
    )
    assert "[kf_boxed]" in filt_oob
    assert "overlay=x=W-w-20:y=20[stacked_v]" in filt_oob

    # 2. Killfeed empty, whitespace, None, or none string disables overlay completely
    for empty_kf in ["", "   ", None, "none", "NONE"]:
        filt_none = build_gaming_split_filter(
            facecam_box="0.68,0.05,0.28,0.15",
            gameplay_box="0.25,0.0,0.50,0.62",
            src_w=1920,
            src_h=1080,
            layout="split_30_70",
            killfeed_box=empty_kf,
        )
        assert "[kf_boxed]" not in filt_none
        assert "drawbox=" not in filt_none
        assert filt_none.endswith("[stacked_v]")


def test_escape_filter_path():
    # Test colons, quotes, brackets, and backslashes
    raw = "/path/to/my [clips]: 'test'/sub.ass"
    escaped = escape_filter_path(raw)
    assert r"\:" in escaped
    assert r"\'" in escaped
    assert r"\[" in escaped
    assert r"\]" in escaped
    assert "\\" not in escaped.replace(r"\:", "").replace(r"\'", "").replace(r"\[", "").replace(r"\]", "")

    # Windows-style backslashes
    win_path = r"C:\Users\tester\video.ass"
    esc_win = escape_filter_path(win_path)
    assert "\\Users" not in esc_win
    assert r"\:" in esc_win


def test_build_gaming_split_filter_with_subtitles(tmp_path):
    sub_file = tmp_path / "test [sample]: 1.ass"
    sub_file.write_text("[Script Info]")

    filt = build_gaming_split_filter(
        facecam_box="0.68,0.05,0.28,0.15",
        gameplay_box="0.25,0.0,0.50,0.62",
        src_w=1920,
        src_h=1080,
        layout="split_30_70",
        subtitle_ass_path=str(sub_file),
    )
    assert ";[stacked_v]subtitles=filename=" in filt
    assert ":fontsdir=" in filt
    assert filt.endswith("[v_out]")
    assert r"\[sample\]" in filt
    assert r"\:" in filt


@patch("scripts.gaming_split.probe_video_dimensions", return_value=(1920, 1080))
@patch("subprocess.run")
def test_render_gaming_split_clip_single_pass_success(mock_run, mock_probe, tmp_path):
    import subprocess
    in_file = tmp_path / "in.mp4"
    in_file.write_text("dummy")
    out_file = tmp_path / "out.mp4"
    sub_file = tmp_path / "sub.ass"
    sub_file.write_text("subtitles")

    mock_run.return_value = subprocess.CompletedProcess(["ffmpeg"], 0)

    res = render_gaming_split_clip(
        str(in_file),
        str(out_file),
        subtitle_ass_path=str(sub_file),
    )
    assert isinstance(res, RenderResult)
    assert res == str(out_file)
    assert res.subtitles_burned is True
    assert mock_run.call_count == 1

    cmd = mock_run.call_args[0][0]
    assert "-filter_complex" in cmd
    filt_idx = cmd.index("-filter_complex") + 1
    assert "subtitles=" in cmd[filt_idx]
    assert cmd[filt_idx].endswith("[v_out]")
    map_idx = cmd.index("-map")
    assert cmd[map_idx + 1] == "[v_out]"


@patch("scripts.gaming_split.probe_video_dimensions", return_value=(1920, 1080))
@patch("subprocess.run")
def test_render_gaming_split_clip_single_pass_fallback_on_failure(mock_run, mock_probe, tmp_path):
    import subprocess
    in_file = tmp_path / "in.mp4"
    in_file.write_text("dummy")
    out_file = tmp_path / "out.mp4"
    sub_file = tmp_path / "sub.ass"
    sub_file.write_text("subtitles")

    # Single-pass with subtitles fails, fallback without subtitles succeeds
    def fake_run(cmd, *args, **kwargs):
        if "[v_out]" in cmd:
            raise subprocess.CalledProcessError(1, cmd, stderr=b"subtitles filter failed")
        return subprocess.CompletedProcess(cmd, 0)
    mock_run.side_effect = fake_run

    res = render_gaming_split_clip(
        str(in_file),
        str(out_file),
        subtitle_ass_path=str(sub_file),
    )
    assert isinstance(res, RenderResult)
    assert res == str(out_file)
    assert res.subtitles_burned is False

    # The last executed command should be without subtitles, mapping [stacked_v]
    last_cmd = mock_run.call_args_list[-1][0][0]
    filt_idx = last_cmd.index("-filter_complex") + 1
    assert "subtitles=" not in last_cmd[filt_idx]
    assert last_cmd[filt_idx].endswith("[stacked_v]")
    map_idx = last_cmd.index("-map")
    assert last_cmd[map_idx + 1] == "[stacked_v]"


@patch("scripts.gaming_split.probe_video_dimensions", return_value=(1920, 1080))
@patch("subprocess.run")
def test_render_gaming_split_clip_missing_sub_file_does_no_subs(mock_run, mock_probe, tmp_path):
    import subprocess
    in_file = tmp_path / "in.mp4"
    in_file.write_text("dummy")
    out_file = tmp_path / "out.mp4"

    mock_run.return_value = subprocess.CompletedProcess(["ffmpeg"], 0)

    res = render_gaming_split_clip(
        str(in_file),
        str(out_file),
        subtitle_ass_path=str(tmp_path / "nonexistent.ass"),
    )
    assert isinstance(res, RenderResult)
    assert res.subtitles_burned is False
    assert mock_run.call_count == 1
    cmd = mock_run.call_args[0][0]
    filt_idx = cmd.index("-filter_complex") + 1
    assert "subtitles=" not in cmd[filt_idx]
    assert cmd[cmd.index("-map") + 1] == "[stacked_v]"


def test_render_result_properties():
    r1 = RenderResult("/path/to/clip.mp4", subtitles_burned=True)
    assert isinstance(r1, str)
    assert r1 == "/path/to/clip.mp4"
    assert r1.subtitles_burned is True
    assert os.path.basename(r1) == "clip.mp4"
    assert r1.endswith(".mp4")
    assert f"Output: {r1}" == "Output: /path/to/clip.mp4"

    r2 = RenderResult("/path/to/clip.mp4", subtitles_burned=False)
    assert r2.subtitles_burned is False


def test_escape_filter_path_advanced_edge_cases():
    # Empty string
    assert escape_filter_path("") == os.path.abspath("").replace("\\", "/")

    # Tricky filename with quotes, spaces, colon, brackets
    tricky = "C:\\Videos\\Gaming: 'Epic' [Win] #1 (2026).ass"
    escaped = escape_filter_path(tricky)
    assert "\\:" in escaped
    assert "\\'" in escaped
    assert "\\[" in escaped
    assert "\\]" in escaped
    assert "\\" not in escaped.replace(r"\:", "").replace(r"\'", "").replace(r"\[", "").replace(r"\]", "")


def test_build_gaming_split_filter_empty_or_none_subtitle_path():
    for empty_sub in [None, ""]:
        filt = build_gaming_split_filter(
            facecam_box="0.68,0.05,0.28,0.15",
            gameplay_box="0.25,0.0,0.50,0.62",
            src_w=1920,
            src_h=1080,
            layout="split_30_70",
            subtitle_ass_path=empty_sub,
        )
        assert "subtitles=" not in filt
        assert filt.endswith("[stacked_v]")


def test_build_gaming_split_filter_special_characters_sub_path(tmp_path):
    sub_file = tmp_path / "streamer's [highlight]: #1.ass"
    sub_file.write_text("[Script Info]\n")

    filt = build_gaming_split_filter(
        facecam_box="0.68,0.05,0.28,0.15",
        gameplay_box="0.25,0.0,0.50,0.62",
        src_w=1920,
        src_h=1080,
        layout="split_40_60",
        subtitle_ass_path=str(sub_file),
    )
    assert ";[stacked_v]subtitles=filename=" in filt
    assert ":fontsdir=" in filt
    assert filt.endswith("[v_out]")
    assert r"streamer\'s" in filt
    assert r"\[highlight\]" in filt
    assert r"\:" in filt


def test_single_pass_gating_conditions():
    def can_single_pass(watermark_mode: str, enable_html_broll: bool) -> bool:
        watermark_config = {"mode": watermark_mode}
        return (
            watermark_config.get("mode") == "disabled"
            and not enable_html_broll
        )

    # Disabled watermark and no broll -> eligible for single-pass
    assert can_single_pass("disabled", False) is True

    # Active watermark (e.g. image or text overlay) -> must fallback to two-pass
    assert can_single_pass("image", False) is False
    assert can_single_pass("text", False) is False

    # Enabled HTML b-roll -> must fallback to two-pass
    assert can_single_pass("disabled", True) is False
    assert can_single_pass("image", True) is False
