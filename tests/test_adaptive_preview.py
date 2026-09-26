import os
import subprocess
import pytest
from webui import branding
from webui import subtitle_handler as subs

def create_sample_video(path: str, duration: int = 4):
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi",
        "-i", f"testsrc=duration={duration}:size=320x240:rate=25",
        "-f", "lavfi",
        "-i", f"sine=frequency=1000:duration={duration}",
        "-c:v", "libx264",
        "-preset", "ultrafast",
        "-c:a", "aac",
        path
    ]
    subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

def test_watermark_preview_with_background():
    sample_uri = "data:image/jpeg;base64,12345fake"
    html = branding.watermark_safe_area_preview(
        mode="text",
        image_path="",
        text="Sample Logo",
        position="top_right",
        scale_percent=15,
        opacity_percent=80,
        h_margin=10,
        v_margin=10,
        custom_x=0,
        custom_y=0,
        bg_data_uri=sample_uri
    )
    assert sample_uri in html
    assert "Sample Logo" in html

def test_subtitle_html_preview_with_background():
    sample_uri = "data:image/jpeg;base64,67890fake"
    html = subs.generate_preview_html(
        font="Montserrat-ExtraBold",
        size=24,
        color="#FFFFFF",
        highlight="#00FF00",
        outline="#000000",
        outline_thick=2,
        shadow="#000000",
        shadow_sz=1,
        bold=True,
        italic=False,
        upper=True,
        h_size=28,
        w_block=3,
        gap=0.2,
        mode="highlight",
        under=False,
        strike=False,
        border_s=1,
        vert_pos=150,
        align=2,
        remove_punc=True,
        bg_data_uri=sample_uri
    )
    assert sample_uri in html
    assert "Montserrat" in html

def test_subtitle_render_video_with_real_video(tmp_path):
    vid_path = str(tmp_path / "real_sample.mp4")
    create_sample_video(vid_path, duration=4)

    res = subs.render_preview_video(
        font="Montserrat-ExtraBold",
        size=24,
        color="#FFFFFF",
        highlight="#00FF00",
        outline="#000000",
        outline_thick=2,
        shadow="#000000",
        shadow_sz=1,
        bold=True,
        italic=False,
        upper=True,
        h_size=28,
        w_block=3,
        gap=0.2,
        mode="highlight",
        under=False,
        strike=False,
        border_s=1,
        vert_pos=150,
        align=2,
        remove_punc=True,
        video_path=vid_path
    )
    assert res is not None
    # res is a gradio update dict with 'value' pointing to mp4 path
    out_file = res["value"]
    assert os.path.exists(out_file)
    assert os.path.getsize(out_file) > 1000
