import os
import subprocess
import tempfile
import pytest
from scripts import watermark, burn_subtitles


def test_build_filter_no_premature_truncation():
    """Verify build_filter does not contain shortest=1 or setpts=N/(30*TB) which causes freeze at 75s on 90s clips."""
    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as temp_vid:
        temp_vid_path = temp_vid.name

    try:
        # Generate dummy 10s video for probing
        cmd = [
            "ffmpeg", "-y", "-loglevel", "error",
            "-f", "lavfi", "-i", "testsrc=duration=10:size=640x360:rate=30",
            "-c:v", "libx264", "-t", "10",
            temp_vid_path
        ]
        subprocess.run(cmd, check=True)

        config = watermark.build_config(
            mode="text",
            text="ViralCutter",
            position="top_right",
            scale_percent=15.0,
            opacity=0.85,
        )

        filter_complex, summary = watermark.build_filter(config, temp_vid_path)

        # Invariants: No shortest=1, no setpts=N/(30*TB), no trim on watermark stream
        assert "shortest=1" not in filter_complex, "overlay must not contain shortest=1 as it kills the main video early"
        assert "setpts=N/(30*TB)" not in filter_complex, "setpts must not compress the watermark frames"
        assert "trim=duration=" not in filter_complex, "trim must not prematurely cut the looped watermark"
        assert "eof_action=pass" in filter_complex, "overlay must use eof_action=pass"
    finally:
        if os.path.exists(temp_vid_path):
            os.remove(temp_vid_path)


def test_90s_video_burn_does_not_freeze_at_75s():
    """
    Simulates user bug scenario:
    Video of 90s (1m 30s) with 90s audio.
    Ensure video stream duration remains 90s and does not freeze at 75s (1m 15s).
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        video_input = os.path.join(tmpdir, "input_90s.mp4")
        watermark_png = os.path.join(tmpdir, "watermark.png")
        sub_ass = os.path.join(tmpdir, "sub.ass")
        output_mp4 = os.path.join(tmpdir, "output_burned.mp4")

        # 1. Create a 90s video with 90s audio
        cmd_gen = [
            "ffmpeg", "-y", "-loglevel", "error",
            "-f", "lavfi", "-i", "testsrc=duration=90:size=320x180:rate=25",
            "-f", "lavfi", "-i", "sine=duration=90",
            "-c:v", "libx264", "-preset", "ultrafast",
            "-c:a", "aac",
            "-t", "90",
            video_input
        ]
        subprocess.run(cmd_gen, check=True)

        # 2. Create watermark image
        cmd_img = [
            "ffmpeg", "-y", "-loglevel", "error",
            "-f", "lavfi", "-i", "color=c=red:size=50x50",
            "-frames:v", "1",
            watermark_png
        ]
        subprocess.run(cmd_img, check=True)

        # 3. Create dummy ASS subtitle
        with open(sub_ass, "w", encoding="utf-8") as f:
            f.write("""[Script Info]
ScriptType: v4.00+
PlayResX: 320
PlayResY: 180

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Arial,16,&H00FFFFFF,&H000000FF,&H00000000,&H80000000,1,0,0,0,100,100,0,0,1,1,0,2,10,10,20,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
Dialogue: 0,0:01:20.00,0:01:28.00,Default,,0,0,0,,Subtitle at 80-88s
""")

        wm_config = watermark.build_config(
            mode="image",
            image_path=watermark_png,
            position="top_right",
            scale_percent=15.0,
            opacity=0.85,
        )

        burn_subtitles.burn_video_file(
            video_path=video_input,
            subtitle_path=sub_ass,
            output_path=output_mp4,
            watermark_config=wm_config,
            watermark_asset=watermark_png
        )

        assert os.path.exists(output_mp4)

        # Check video stream duration specifically
        res_v = subprocess.run(
            [
                "ffprobe", "-v", "error",
                "-select_streams", "v:0",
                "-show_entries", "stream=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                output_mp4
            ],
            capture_output=True, text=True, check=True
        )
        video_dur = float(res_v.stdout.strip())

        # Check audio stream duration
        res_a = subprocess.run(
            [
                "ffprobe", "-v", "error",
                "-select_streams", "a:0",
                "-show_entries", "stream=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                output_mp4
            ],
            capture_output=True, text=True, check=True
        )
        audio_dur = float(res_a.stdout.strip())

        # Prior bug caused video_dur to be ~75.0s (1m 15s) while audio_dur was 90.0s.
        # Now both must be ~90.0s (tolerance within 0.5s).
        assert video_dur >= 89.0, f"Video froze prematurely! Duration was {video_dur:.2f}s instead of ~90s"
        assert abs(video_dur - audio_dur) <= 0.5, f"Video ({video_dur:.2f}s) and Audio ({audio_dur:.2f}s) desync!"
