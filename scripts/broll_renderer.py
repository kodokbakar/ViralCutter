import os
import subprocess
import tempfile
from typing import Any, Dict
from playwright.sync_api import sync_playwright
from scripts import broll_engine


def render_broll_clip(
    template_id: str,
    data: Dict[str, Any],
    duration: float,
    output_path: str,
    fps: int = 30,
) -> str:
    """
    Renders an HTML motion template to a transparent WebM video (VP9 / yuva420p)
    frame-by-frame via Playwright headless Chromium and FFmpeg stdin pipe (CPU-only).
    """
    duration = max(1.0, float(duration or 3.0))
    total_frames = max(1, int(round(duration * fps)))
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

    html_content = broll_engine.render_html_content(template_id, data)

    ffmpeg_cmd = [
        "ffmpeg",
        "-y",
        "-loglevel",
        "error",
        "-f",
        "image2pipe",
        "-vcodec",
        "png",
        "-r",
        str(fps),
        "-i",
        "-",
        "-c:v",
        "libvpx-vp9",
        "-pix_fmt",
        "yuva420p",
        "-b:v",
        "2M",
        "-auto-alt-ref",
        "0",
        output_path,
    ]

    with tempfile.NamedTemporaryFile("w", suffix=".html", delete=False, encoding="utf-8") as tf:
        tf.write(html_content)
        temp_html_path = tf.name

    proc = None
    try:
        proc = subprocess.Popen(ffmpeg_cmd, stdin=subprocess.PIPE)

        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=[
                    "--disable-gpu",
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-dev-shm-usage",
                ],
            )
            context = browser.new_context(viewport={"width": 1080, "height": 1920})
            page = context.new_page()
            page.goto(f"file://{os.path.abspath(temp_html_path)}")

            denominator = max(1, total_frames - 1)
            for frame_idx in range(total_frames):
                progress = frame_idx / denominator
                page.evaluate(f"window.renderSeek({progress})")
                frame_bytes = page.screenshot(type="png", omit_background=True)
                proc.stdin.write(frame_bytes)

            browser.close()

        if proc.stdin and not proc.stdin.closed:
            proc.stdin.close()
        proc.wait()
    finally:
        if proc and proc.poll() is None:
            proc.kill()
        if os.path.exists(temp_html_path):
            try:
                os.remove(temp_html_path)
            except Exception:
                pass

    if not os.path.exists(output_path) or os.path.getsize(output_path) == 0:
        raise RuntimeError(f"B-roll render failed: Output file missing or empty: {output_path}")

    return output_path
