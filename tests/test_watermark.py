import sys
import os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from scripts.watermark import (
    get_watermark_filter,
    apply_watermark,
    check_safe_area,
    SAFE_AREA_TIKTOK_BOTTOM,
    SAFE_AREA_IG_BOTTOM,
    SAFE_AREA_SHORTS_BOTTOM,
    SAFE_AREA_TIKTOK_LEFT,
    SAFE_AREA_TIKTOK_RIGHT,
)


class TestGetWatermarkFilter:
    def test_watermark_filter_generation(self):
        f = get_watermark_filter(
            "/tmp/logo.png", "bottom-right", 0.15, 0.8, 20, 20, 0, 0
        )
        assert "overlay=" in f
        assert "scale=" in f
        assert "colorchannelmixer=" in f

    def test_watermark_position_presets(self):
        positions = {
            "top-left": "20:20",
            "top-right": "main_w-overlay_w-20:20",
            "bottom-left": "20:main_h-overlay_h-20",
            "bottom-right": "main_w-overlay_w-20:main_h-overlay_h-20",
            "center": "(main_w-overlay_w)/2:(main_h-overlay_h)/2",
            "custom": "100:200",
        }
        for pos, expected_overlay in positions.items():
            cx, cy = (100, 200) if pos == "custom" else (0, 0)
            f = get_watermark_filter(
                "/tmp/logo.png", pos, 0.15, 0.8, 20, 20, cx, cy
            )
            assert f"overlay={expected_overlay}" in f, (
                f"Position '{pos}' expected overlay={expected_overlay} in: {f}"
            )


class TestApplyWatermarkValidation:
    def test_watermark_missing_video(self, tmp_path):
        logo = tmp_path / "logo.png"
        logo.write_bytes(b"\x89PNG")
        ok, msg = apply_watermark(
            str(tmp_path / "nope.mp4"), str(logo), str(tmp_path / "out.mp4")
        )
        assert not ok
        assert "not found" in msg.lower() or "Video" in msg

    def test_watermark_missing_logo(self, tmp_path):
        video = tmp_path / "video.mp4"
        video.write_bytes(b"\x00\x00")
        ok, msg = apply_watermark(
            str(video), str(tmp_path / "nope.png"), str(tmp_path / "out.mp4")
        )
        assert not ok
        assert "not found" in msg.lower() or "Logo" in msg

    def test_watermark_invalid_scale(self, tmp_path):
        video = tmp_path / "video.mp4"
        video.write_bytes(b"\x00\x00")
        logo = tmp_path / "logo.png"
        logo.write_bytes(b"\x89PNG")
        for bad_scale in (-0.1, 1.1, 2.0):
            ok, msg = apply_watermark(
                str(video), str(logo), str(tmp_path / "out.mp4"),
                scale=bad_scale,
            )
            assert not ok, f"scale={bad_scale} should fail"
            assert "scale" in msg.lower()


class TestCheckSafeArea:
    def test_safe_position_returns_no_warnings(self):
        w = check_safe_area("top-left", 0.15, 100, 100, video_height=1920)
        assert w == []

    def test_bottom_right_overlaps_platforms(self):
        # v_margin=20 makes logo bottom deep in safe zones
        w = check_safe_area("bottom-right", 0.15, 20, 20, video_height=1920)
        assert len(w) >= 3  # tiktok, ig, shorts all overlap
        assert any("TikTok" in x for x in w)
        assert any("Instagram" in x for x in w)
        assert any("YouTube Shorts" in x for x in w)

    def test_bottom_left_overlaps_platforms(self):
        w = check_safe_area("bottom-left", 0.15, 20, 20, video_height=1920)
        assert len(w) >= 3

    def test_high_margin_avoids_overlap(self):
        # Place logo high enough to clear all safe zones
        w = check_safe_area("bottom-right", 0.1, 200, 200, video_height=1920)
        assert w == []

    def test_tiktok_left_margin_warning(self):
        w = check_safe_area("top-left", 0.15, 10, 20, video_height=1920)
        assert any("left safe-area" in x for x in w)

    def test_tiktok_right_margin_warning(self):
        w = check_safe_area("top-right", 0.15, 10, 20, video_height=1920)
        assert any("right safe-area" in x for x in w)

    def test_margin_at_boundary_no_warning(self):
        w_left = check_safe_area("top-left", 0.15, SAFE_AREA_TIKTOK_LEFT, 20)
        w_right = check_safe_area("top-right", 0.15, SAFE_AREA_TIKTOK_RIGHT, 20)
        assert w_left == []
        assert w_right == []

    def test_center_position_no_warnings(self):
        w = check_safe_area("center", 0.15, 20, 20)
        assert w == []
