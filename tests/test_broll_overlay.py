import os
import subprocess
import tempfile
import pytest
from scripts import burn_subtitles, broll_renderer


def test_burn_video_file_with_broll_overlay():
    with tempfile.TemporaryDirectory() as tmpdir:
        video_in = os.path.join(tmpdir, "test_input.mp4")
        sub_ass = os.path.join(tmpdir, "test_sub.ass")
        output_mp4 = os.path.join(tmpdir, "test_out.mp4")
        broll_webm = os.path.join(tmpdir, "broll.webm")

        # Create 5s synthetic video
        subprocess.run([
            "ffmpeg", "-y", "-loglevel", "error",
            "-f", "lavfi", "-i", "testsrc=duration=5:size=320x180:rate=30",
            "-f", "lavfi", "-i", "sine=duration=5",
            "-c:v", "libx264", "-c:a", "aac",
            video_in
        ], check=True)

        # Create 2s WebM broll
        broll_renderer.render_broll_clip(
            "stat_counter",
            {"target_number": "50", "suffix": "%", "label": "Uji B-Roll"},
            duration=2.0,
            output_path=broll_webm,
            fps=30
        )

        with open(sub_ass, "w") as f:
            f.write("[Script Info]\nScriptType: v4.00+\n[Events]\nFormat: Layer, Start, End, Style, Text\nDialogue: 0,0:00:01.00,0:00:03.00,Default,Test\n")

        broll_items = [
            {
                "start_offset": 1.0,
                "duration": 2.0,
                "video_path": broll_webm
            }
        ]

        burn_subtitles.burn_video_file(
            video_path=video_in,
            subtitle_path=sub_ass,
            output_path=output_mp4,
            broll_items=broll_items
        )

        assert os.path.exists(output_mp4)
        assert os.path.getsize(output_mp4) > 1000

        # Verify video duration matches 5s
        res = subprocess.run([
            "ffprobe", "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "stream=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
        output_mp4
        ], capture_output=True, text=True, check=True)
        dur = float(res.stdout.strip())
        assert abs(dur - 5.0) < 0.2

        # Verify audio stream is preserved and not muted or truncated
        res_a = subprocess.run([
            "ffprobe", "-v", "error",
            "-select_streams", "a:0",
            "-show_entries", "stream=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            output_mp4
        ], capture_output=True, text=True, check=True)
        dur_a = float(res_a.stdout.strip())
        assert abs(dur_a - 5.0) < 0.2
def test_burn_video_file_with_broll_and_watermark():
    with tempfile.TemporaryDirectory() as tmpdir:
        video_in = os.path.join(tmpdir, "test_input.mp4")
        sub_ass = os.path.join(tmpdir, "test_sub.ass")
        output_mp4 = os.path.join(tmpdir, "test_out.mp4")
        broll_webm = os.path.join(tmpdir, "broll.webm")
        wm_img = os.path.join(tmpdir, "watermark.png")

        subprocess.run([
            "ffmpeg", "-y", "-loglevel", "error",
            "-f", "lavfi", "-i", "testsrc=duration=4:size=320x180:rate=30",
            "-f", "lavfi", "-i", "sine=duration=4",
            "-c:v", "libx264", "-c:a", "aac",
            video_in
        ], check=True)

        subprocess.run([
            "ffmpeg", "-y", "-loglevel", "error",
            "-f", "lavfi", "-i", "color=white:s=20x20:d=1",
            "-vframes", "1", wm_img
        ], check=True)

        broll_renderer.render_broll_clip(
            "stat_counter",
            {"target_number": "99", "suffix": "+", "label": "Retention"},
            duration=1.5,
            output_path=broll_webm,
            fps=30
        )

        with open(sub_ass, "w") as f:
            f.write("[Script Info]\nScriptType: v4.00+\n[Events]\nFormat: Layer, Start, End, Style, Text\nDialogue: 0,0:00:00.50,0:00:02.50,Default,Test Sub\n")

        from scripts import watermark
        wm_cfg = watermark.build_config(mode="image", image_path=wm_img)

        broll_items = [
            {
                "start_offset": 0.5,
                "duration": 1.5,
                "video_path": broll_webm
            }
        ]

        burn_subtitles.burn_video_file(
            video_path=video_in,
            subtitle_path=sub_ass,
            output_path=output_mp4,
            watermark_config=wm_cfg,
            watermark_asset=wm_img,
            broll_items=broll_items
        )

        assert os.path.exists(output_mp4)
        assert os.path.getsize(output_mp4) > 1000

        res = subprocess.run([
            "ffprobe", "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "stream=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            output_mp4
        ], capture_output=True, text=True, check=True)
        dur = float(res.stdout.strip())
        assert abs(dur - 4.0) < 0.2

        # Verify audio stream is preserved
        res_a = subprocess.run([
            "ffprobe", "-v", "error",
            "-select_streams", "a:0",
            "-show_entries", "stream=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            output_mp4
        ], capture_output=True, text=True, check=True)
        dur_a = float(res_a.stdout.strip())
        assert abs(dur_a - 4.0) < 0.2

def test_main_cli_arg_enable_html_broll():
    import subprocess
    res = subprocess.run(["python3", "main_improved.py", "--help"], capture_output=True, text=True, check=True)
    assert "--enable-html-broll" in res.stdout


def test_burn_subtitles_snaps_broll_to_processed_subs():
    import json
    with tempfile.TemporaryDirectory() as tmpdir:
        final_dir = os.path.join(tmpdir, "final")
        subs_ass_dir = os.path.join(tmpdir, "subs_ass")
        subs_dir = os.path.join(tmpdir, "subs")
        os.makedirs(final_dir)
        os.makedirs(subs_ass_dir)
        os.makedirs(subs_dir)

        clip_name = "001_Test_Video"
        vid_in = os.path.join(final_dir, f"{clip_name}.mp4")
        sub_ass = os.path.join(subs_ass_dir, f"{clip_name}.ass")
        sub_json = os.path.join(subs_dir, f"{clip_name}_processed.json")

        # 1. Create 5s input video
        subprocess.run([
            "ffmpeg", "-y", "-loglevel", "error",
            "-f", "lavfi", "-i", "testsrc=duration=5:size=320x180:rate=30",
            "-f", "lavfi", "-i", "sine=duration=5",
            "-c:v", "libx264", "-c:a", "aac",
            vid_in
        ], check=True)

        # 2. Create ASS sub
        with open(sub_ass, "w") as f:
            f.write("[Script Info]\nScriptType: v4.00+\n[Events]\nFormat: Layer, Start, End, Style, Text\nDialogue: 0,0:00:01.00,0:00:03.00,Default,Test\n")

        # 3. Create processed transcript JSON where "85" is spoken at 2.5s
        with open(sub_json, "w", encoding="utf-8") as f:
            json.dump({
                "segments": [
                    {
                        "start": 0.0,
                        "end": 4.5,
                        "words": [
                            {"word": "halo", "start": 0.5, "end": 1.0},
                            {"word": "naik", "start": 1.8, "end": 2.2},
                            {"word": "85", "start": 2.5, "end": 3.0},
                            {"word": "persen", "start": 3.1, "end": 3.8},
                        ]
                    }
                ]
            }, f)

        # 4. viral_segments.txt with broll estimated at 1.0s (too early)
        vs_file = os.path.join(tmpdir, "viral_segments.txt")
        with open(vs_file, "w", encoding="utf-8") as f:
            json.dump({
                "segments": [
                    {
                        "title": "Test Video",
                        "broll_items": [
                            {
                                "template_id": "stat_counter",
                                "start_offset": 1.0,  # Estimated too early
                                "duration": 2.0,
                                "data": {"target_number": "85"}
                            }
                        ]
                    }
                ]
            }, f)

        # 5. Run burn
        out_folder = burn_subtitles.burn(project_folder=tmpdir, enable_html_broll=True)
        out_file = os.path.join(out_folder, f"{clip_name}.mp4")
        assert os.path.exists(out_file)
        assert os.path.getsize(out_file) > 1000
