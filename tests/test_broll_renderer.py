import os
import subprocess
import tempfile
import pytest
from scripts import broll_renderer


def test_render_broll_clip_generates_valid_alpha_webm():
    with tempfile.TemporaryDirectory() as tmpdir:
        output_webm = os.path.join(tmpdir, "test_stat.webm")
        data = {
            "target_number": "99",
            "prefix": "",
            "suffix": "%",
            "label": "Test Retensi",
            "accent_color": "#10B981",
        }
        res_path = broll_renderer.render_broll_clip(
            template_id="stat_counter",
            data=data,
            duration=1.0,
            output_path=output_webm,
            fps=30,
        )
        assert os.path.exists(res_path)
        assert os.path.getsize(res_path) > 1000

        # Check format and alpha channel via ffprobe
        # libvpx-vp9 decoder must be specified so ffprobe parses WebM BlockAdditional alpha as yuva420p
        probe = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-c:v",
                "libvpx-vp9",
                "-select_streams",
                "v:0",
                "-show_entries",
                "stream=codec_name,pix_fmt,duration",
                "-of",
                "default=noprint_wrappers=1",
                output_webm,
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        stdout = probe.stdout
        assert "codec_name=vp9" in stdout
        assert "pix_fmt=yuva420p" in stdout

        # Also verify WebM container alpha_mode metadata tag is set
        tag_probe = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-select_streams",
                "v:0",
                "-show_entries",
                "stream_tags=alpha_mode",
                "-of",
                "default=noprint_wrappers=1",
                output_webm,
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        assert "alpha_mode=1" in tag_probe.stdout
