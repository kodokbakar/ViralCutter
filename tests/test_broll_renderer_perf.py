import subprocess
import pytest
from unittest.mock import patch, MagicMock
from scripts import broll_renderer

def test_render_broll_clip_uses_realtime_vp9_flags(tmp_path):
    output_webm = str(tmp_path / "out.webm")
    data = {"target_number": "42"}

    with patch("subprocess.Popen") as mock_popen, \
         patch("scripts.broll_renderer.sync_playwright") as mock_pw, \
         patch("os.path.exists", return_value=True), \
         patch("os.path.getsize", return_value=5000):

        mock_proc = MagicMock()
        mock_proc.poll.return_value = 0
        mock_proc.returncode = 0
        mock_proc.stdin = MagicMock()
        mock_popen.return_value = mock_proc

        broll_renderer.render_broll_clip("stat_counter", data, 1.0, output_webm, fps=12)

        cmd = mock_popen.call_args[0][0]
        assert "-deadline" in cmd
        assert cmd[cmd.index("-deadline") + 1] == "realtime"
        assert "-cpu-used" in cmd
        assert cmd[cmd.index("-cpu-used") + 1] == "8"
        assert "-row-mt" in cmd
        assert cmd[cmd.index("-row-mt") + 1] == "1"

def test_render_broll_clip_optimizes_playwright(tmp_path):
    output_webm = str(tmp_path / "out.webm")
    data = {"target_number": "42"}

    with patch("subprocess.Popen") as mock_popen, \
         patch("scripts.broll_renderer.sync_playwright") as mock_pw, \
         patch("os.path.exists", return_value=True), \
         patch("os.path.getsize", return_value=5000):

        mock_proc = MagicMock()
        mock_proc.poll.return_value = 0
        mock_proc.returncode = 0
        mock_proc.stdin = MagicMock()
        mock_popen.return_value = mock_proc

        mock_playwright = MagicMock()
        mock_browser = MagicMock()
        mock_context = MagicMock()
        mock_page = MagicMock()

        mock_pw.return_value.__enter__.return_value = mock_playwright
        mock_playwright.chromium.launch.return_value = mock_browser
        mock_browser.new_context.return_value = mock_context
        mock_context.new_page.return_value = mock_page

        broll_renderer.render_broll_clip("stat_counter", data, 1.0, output_webm, fps=12)

        launch_args = mock_playwright.chromium.launch.call_args[1].get("args", [])
        assert "--disable-background-timer-throttling" in launch_args
        assert "--disable-backgrounding-occluded-windows" in launch_args
        assert "--disable-renderer-backgrounding" in launch_args

        context_kwargs = mock_browser.new_context.call_args[1]
        assert context_kwargs.get("device_scale_factor") == 1

        goto_kwargs = mock_page.goto.call_args[1]
        assert goto_kwargs.get("wait_until") == "domcontentloaded"

        screenshot_kwargs = mock_page.screenshot.call_args[1]
        assert screenshot_kwargs.get("animations") == "disabled"
        assert screenshot_kwargs.get("omit_background") is True

def test_render_broll_clip_handles_single_frame_without_zerodivision(tmp_path):
    output_webm = str(tmp_path / "out.webm")
    data = {"target_number": "1"}

    with patch("subprocess.Popen") as mock_popen, \
         patch("scripts.broll_renderer.sync_playwright") as mock_pw, \
         patch("os.path.exists", return_value=True), \
         patch("os.path.getsize", return_value=1000):

        mock_proc = MagicMock()
        mock_proc.poll.return_value = 0
        mock_proc.returncode = 0
        mock_proc.stdin = MagicMock()
        mock_popen.return_value = mock_proc

        mock_playwright = MagicMock()
        mock_browser = MagicMock()
        mock_context = MagicMock()
        mock_page = MagicMock()

        mock_pw.return_value.__enter__.return_value = mock_playwright
        mock_playwright.chromium.launch.return_value = mock_browser
        mock_browser.new_context.return_value = mock_context
        mock_context.new_page.return_value = mock_page

        # 1.0s at 1 fps -> total_frames = max(1, round(1.0 * 1)) = 1
        broll_renderer.render_broll_clip("stat_counter", data, 1.0, output_webm, fps=1)

        assert mock_page.screenshot.call_count == 1

def test_render_broll_clip_raises_on_ffmpeg_failure(tmp_path):
    output_webm = str(tmp_path / "out.webm")
    data = {"target_number": "42"}

    with patch("subprocess.Popen") as mock_popen, \
         patch("scripts.broll_renderer.sync_playwright") as mock_pw:

        mock_proc = MagicMock()
        mock_proc.poll.return_value = 1
        mock_proc.returncode = 1
        mock_proc.stdin = MagicMock()
        mock_popen.return_value = mock_proc

        mock_playwright = MagicMock()
        mock_browser = MagicMock()
        mock_context = MagicMock()
        mock_page = MagicMock()

        mock_pw.return_value.__enter__.return_value = mock_playwright
        mock_playwright.chromium.launch.return_value = mock_browser
        mock_browser.new_context.return_value = mock_context
        mock_context.new_page.return_value = mock_page

        with pytest.raises(RuntimeError, match="FFmpeg exit code 1"):
            broll_renderer.render_broll_clip("stat_counter", data, 1.0, output_webm, fps=12)

def test_render_broll_clip_cleans_up_html_on_exception(tmp_path):
    output_webm = str(tmp_path / "out.webm")
    data = {"target_number": "42"}

    created_html_files = []
    original_named_temp = broll_renderer.tempfile.NamedTemporaryFile

    with patch("subprocess.Popen", side_effect=RuntimeError("Subprocess failed")), \
         patch("scripts.broll_renderer.tempfile.NamedTemporaryFile") as mock_temp:

        tf = original_named_temp("w", suffix=".html", delete=False, encoding="utf-8")
        html_path = tf.name
        mock_temp.return_value = tf

        with pytest.raises(RuntimeError, match="Subprocess failed"):
            broll_renderer.render_broll_clip("stat_counter", data, 1.0, output_webm, fps=12)

        import os
        assert not os.path.exists(html_path)
