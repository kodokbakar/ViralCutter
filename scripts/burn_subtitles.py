import functools
import re
import json
import os
import shlex
import subprocess

# Explicitly flush all standard output prints immediately
print = functools.partial(print, flush=True)

from scripts import (
    subtitle_fonts,
    watermark,
)


def _escape_filter_path(path):
    return (
        os.path.abspath(path)
        .replace("\\", "/")
        .replace(":", "\\:")
        .replace("'", "\\'")
    )

def _build_subtitle_filter(
    subtitle_path,
):
    subtitle_file = _escape_filter_path(
        subtitle_path
    )
    fonts_directory = _escape_filter_path(
        subtitle_fonts.get_fonts_dir()
    )

    return (
        "subtitles="
        f"'{subtitle_file}':"
        "fontsdir="
        f"'{fonts_directory}'"
    )

def _probe_duration(path):
    # Prefer video stream duration to catch truncated/frozen video streams
    try:
        result_stream = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-select_streams",
                "v:0",
                "-show_entries",
                "stream=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                path,
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        val = result_stream.stdout.strip()
        if val and val != "N/A":
            return float(val)
    except Exception:
        pass

    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            (
                "default="
                "noprint_wrappers=1:"
                "nokey=1"
            ),
            path,
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    return float(
        result.stdout.strip()
    )


def _validate_render(
    input_path,
    output_path,
):
    if not os.path.isfile(output_path):
        raise RuntimeError(
            "Rendered output was not created: "
            f"{output_path}"
        )

    output_size = os.path.getsize(
        output_path
    )

    if output_size <= 0:
        raise RuntimeError(
            "Rendered output is empty: "
            f"{output_path}"
        )

    input_duration = _probe_duration(
        input_path
    )
    output_duration = _probe_duration(
        output_path
    )

    tolerance = max(
        0.75,
        input_duration * 0.01,
    )

    if (
        abs(
            input_duration
            - output_duration
        )
        > tolerance
    ):
        raise RuntimeError(
            "Rendered output duration mismatch: "
            f"input={input_duration:.3f}s, "
            f"output={output_duration:.3f}s, "
            f"file={output_path}"
        )

    return {
        "size": output_size,
        "duration": output_duration,
    }


def burn_video_file(
    video_path,
    subtitle_path,
    output_path,
    *,
    watermark_config=None,
    watermark_asset=None,
    broll_items=None,
    **kwargs,
):
    """
    Render one final clip.

        source video
        -> transparent WebM broll
        -> watermark
        -> ASS subtitles
        -> encoded MP4
    """
    subtitle_filter = (
        _build_subtitle_filter(
            subtitle_path
        )
    )

    watermark_enabled = bool(
        watermark_config
        and watermark_config.get(
            "mode"
        )
        in {
            "image",
            "text",
        }
    )
    valid_broll = []
    if broll_items:
        for item in broll_items:
            if isinstance(item, dict):
                v_path = item.get("video_path")
                if v_path and os.path.exists(v_path):
                    valid_broll.append(item)


    def run_ffmpeg(
        encoder,
        preset,
    ):
        command = [
            "ffmpeg",
            "-y",
            "-loglevel",
            "error",
            "-hide_banner",
            "-i",
            video_path,
        ]
        if watermark_enabled:
            command.extend(
                [
                    "-i",
                    watermark_asset,
                ]
            )
            broll_start_idx = 2
        else:
            broll_start_idx = 1

        for b_item in valid_broll:
            command.extend(["-i", b_item["video_path"]])

        if valid_broll or watermark_enabled:
            filter_parts = []
            current_stream = "0:v"

            for b_idx, b_item in enumerate(valid_broll):
                broll_in_idx = broll_start_idx + b_idx
                start = max(0.0, float(b_item.get("start_offset", b_item.get("start_time", 0.0))))
                dur = b_item.get("duration")
                if dur is not None and float(dur) > 0:
                    duration = float(dur)
                else:
                    try:
                        duration = _probe_duration(b_item["video_path"])
                    except Exception:
                        duration = 3.0
                end = start + duration

                broll_in_label = f"broll_in_{b_idx}"
                next_stream = f"broll_out_{b_idx}"

                filter_parts.append(
                    f"[{broll_in_idx}:v]setpts=PTS-STARTPTS+{start:.6f}/TB[{broll_in_label}]"
                )
                filter_parts.append(
                    f"[{current_stream}][{broll_in_label}]overlay=x=0:y=0:enable='between(t,{start:.6f},{end:.6f})':eof_action=pass[{next_stream}]"
                )
                current_stream = next_stream

            if watermark_enabled:
                (
                    wm_filter,
                    filter_summary,
                ) = watermark.build_filter(
                    watermark_config,
                    video_path,
                )
                if current_stream != "0:v":
                    wm_filter = wm_filter.replace("[0:v][watermark]", f"[{current_stream}][watermark]")
                filter_parts.append(wm_filter)
                current_stream = "watermarked"

                print(
                    "Watermark render settings: "
                    f"asset={watermark_asset} "
                    f"video="
                    f"{filter_summary['video_width']}x"
                    f"{filter_summary['video_height']} "
                    f"target_max="
                    f"{filter_summary['target_width']}x"
                    f"{filter_summary['target_height']}px "
                    f"position="
                    f"{filter_summary['position']} "
                    f"opacity="
                    f"{filter_summary['opacity']:.2f} "
                    f"range="
                    f"{filter_summary['start']:.2f}-"
                    f"{filter_summary['end']:.2f}s",
                    flush=True,
                )

                print(
                    "Watermark filter: "
                    f"{wm_filter}",
                    flush=True,
                )

            filter_parts.append(
                f"[{current_stream}]{subtitle_filter}[video_out]"
            )
            filter_complex = ";".join(filter_parts)

            command.extend(
                [
                    "-filter_complex",
                    filter_complex,
                    "-map",
                    "[video_out]",
                    "-map",
                    "0:a?",
                ]
            )
        else:
            command.extend(
                [
                    "-vf",
                    subtitle_filter,
                ]
            )

        command.extend(
            [
                "-c:v",
                encoder,
                "-preset",
                preset,
            ]
        )

        if encoder == "h264_nvenc":
            command.extend(
                [
                    "-b:v",
                    "5M",
                ]
            )
        else:
            command.extend(
                [
                    "-crf",
                    "20",
                ]
            )

        command.extend(
            [
                "-pix_fmt",
                "yuv420p",
                "-c:a",
                "copy",
                "-movflags",
                "+faststart",
                output_path,
            ]
        )

        print(
            "FFmpeg command: "
            + shlex.join(command),
            flush=True,
        )

        subprocess.run(
            command,
            check=True,
            text=True,
        )

        return _validate_render(
            video_path,
            output_path,
        )

    try:
        validation = run_ffmpeg(
            "h264_nvenc",
            "p1",
        )

        return (
            True,
            "NVENC Success",
            validation,
        )

    except Exception as nvenc_error:
        if isinstance(
            nvenc_error,
            subprocess.CalledProcessError,
        ):
            nvenc_detail = (
                nvenc_error.stderr
                or ""
            ).strip()
        else:
            nvenc_detail = str(
                nvenc_error
            ).strip()

        print(
            "NVENC render failed. "
            "Falling back to libx264."
            + (
                f" Details: {nvenc_detail}"
                if nvenc_detail
                else ""
            ),
            flush=True,
        )

    try:
        validation = run_ffmpeg(
            "libx264",
            "ultrafast",
        )

        return (
            True,
            "CPU Success",
            validation,
        )

    except Exception as cpu_error:
        if isinstance(
            cpu_error,
            subprocess.CalledProcessError,
        ):
            cpu_detail = (
                cpu_error.stderr
                or ""
            ).strip()
        else:
            cpu_detail = str(
                cpu_error
            ).strip()

        message = (
            "Failed to render final video "
            f"{os.path.basename(video_path)}"
        )

        if cpu_detail:
            message += (
                f" | FFmpeg: {cpu_detail}"
            )

        print(
            message,
            flush=True,
        )

        return (
            False,
            message,
            None,
        )


def burn(
    project_folder="tmp",
    watermark_config=None,
    broll_items=None,
    enable_html_broll=False,
    **kwargs,
):
    project_folder_abs = (
        os.path.abspath(
            project_folder
        )
    )
    segments_data = []
    if enable_html_broll and broll_items is None:
        vs_file = os.path.join(project_folder_abs, "viral_segments.txt")
        if not os.path.exists(vs_file):
            vs_file = os.path.join(project_folder_abs, "viral_segments.json")
        if os.path.exists(vs_file):
            try:
                with open(vs_file, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                    if isinstance(loaded, dict) and "segments" in loaded:
                        segments_data = loaded["segments"]
                    elif isinstance(loaded, list):
                        segments_data = loaded
            except Exception as e:
                print(f"Warning: could not load viral_segments for b-roll: {e}")


    subs_folder = os.path.join(
        project_folder_abs,
        "subs_ass",
    )
    videos_folder = os.path.join(
        project_folder_abs,
        "final",
    )
    output_folder = os.path.join(
        project_folder_abs,
        "burned_sub",
    )

    os.makedirs(
        output_folder,
        exist_ok=True,
    )

    if not os.path.isdir(
        videos_folder
    ):
        raise FileNotFoundError(
            "Final video folder not found: "
            f"{videos_folder}"
        )

    if not os.path.isdir(
        subs_folder
    ):
        raise FileNotFoundError(
            "ASS subtitle folder not found: "
            f"{subs_folder}"
        )

    bundled_fonts = (
        subtitle_fonts
        .validate_font_assets()
    )

    print(
        "Bundled subtitle fonts: "
        + ", ".join(
            (
                f"{entry['label']} "
                f"({entry['family']})"
            )
            for entry in bundled_fonts
        ),
        flush=True,
    )

    print(
        "Subtitle fonts directory: "
        f"{subtitle_fonts.get_fonts_dir()}",
        flush=True,
    )

    config = (
        watermark_config
        or watermark.build_config(
            mode="disabled"
        )
    )

    watermark_asset = (
        watermark.prepare_asset(
            config,
            project_folder_abs,
        )
    )

    watermark_enabled = (
        config["mode"]
        != "disabled"
    )

    if watermark_enabled:
        asset_info = (
            watermark.describe_asset(
                watermark_asset
            )
        )

        print(
            "Watermark asset ready: "
            f"path={asset_info['path']} "
            f"size="
            f"{asset_info['width']}x"
            f"{asset_info['height']} "
            f"alpha="
            f"{asset_info['alpha_min']}-"
            f"{asset_info['alpha_max']}",
            flush=True,
        )

    files = sorted(
        os.listdir(videos_folder)
    )

    video_files = [
        filename
        for filename in files
        if filename.lower().endswith(
            (
                ".mp4",
                ".mkv",
                ".avi",
                ".mov",
            )
        )
        and "temp_video_no_audio"
        not in filename
    ]

    if not video_files:
        raise FileNotFoundError(
            "No final videos found in: "
            f"{videos_folder}"
        )

    rendered_count = 0

    for video_file in video_files:
        video_name = os.path.splitext(
            video_file
        )[0]

        subtitle_file = os.path.join(
            subs_folder,
            f"{video_name}.ass",
        )

        if not os.path.exists(
            subtitle_file
        ):
            processed_candidate = (
                os.path.join(
                    subs_folder,
                    (
                        f"{video_name}"
                        "_processed.ass"
                    ),
                )
            )

            if os.path.exists(
                processed_candidate
            ):
                subtitle_file = (
                    processed_candidate
                )

        if not os.path.exists(
            subtitle_file
        ):
            print(
                "Subtitle not found for "
                f"{video_name}: "
                f"{subtitle_file}",
                flush=True,
            )
            continue

        input_file = os.path.join(
            videos_folder,
            video_file,
        )
        clean_clip_name = re.sub(r'(_processed|_original_scale)+$', '', video_name)
        output_file = os.path.join(
            output_folder,
            f"{clean_clip_name}.mp4",
        )
        clip_brolls = []
        if broll_items is not None:
            if isinstance(broll_items, dict):
                clip_brolls = (
                    broll_items.get(video_name)
                    or broll_items.get(clean_clip_name)
                    or broll_items.get(rendered_count)
                    or broll_items.get(str(rendered_count))
                    or []
                )
            elif isinstance(broll_items, list):
                if broll_items and isinstance(broll_items[0], list):
                    clip_brolls = broll_items[rendered_count] if rendered_count < len(broll_items) else []
                else:
                    clip_brolls = broll_items if (len(video_files) == 1 or rendered_count == 0) else []
        elif enable_html_broll and segments_data:
            seg = None
            if rendered_count < len(segments_data):
                seg = segments_data[rendered_count]
            if not seg:
                for s in segments_data:
                    title = s.get("title", "")
                    if title and (title in video_name or video_name in title):
                        seg = s
                        break
            clip_brolls = (seg.get("broll_items") if seg else []) or []

        rendered_clip_brolls = []
        if enable_html_broll and clip_brolls:
            cache_dir = os.path.join(project_folder_abs, "broll_cache")
            os.makedirs(cache_dir, exist_ok=True)
            from scripts import broll_renderer

            for b_idx, b_item in enumerate(clip_brolls):
                if not isinstance(b_item, dict):
                    continue
                item_copy = dict(b_item)
                v_path = item_copy.get("video_path")
                if not v_path or not os.path.exists(v_path):
                    tpl_id = item_copy.get("template_id")
                    if tpl_id:
                        out_webm = os.path.join(cache_dir, f"{clean_clip_name}_broll_{b_idx}.webm")
                        duration = float(item_copy.get("duration", 3.0))
                        data = item_copy.get("data", {})
                        print(f"Rendering B-roll clip {b_idx} ({tpl_id}) for {clean_clip_name}...")
                        broll_renderer.render_broll_clip(
                            template_id=tpl_id,
                            data=data,
                            duration=duration,
                            output_path=out_webm,
                        )
                        item_copy["video_path"] = out_webm
                if item_copy.get("video_path") and os.path.exists(item_copy["video_path"]):
                    rendered_clip_brolls.append(item_copy)
        elif clip_brolls:
            rendered_clip_brolls = [b for b in clip_brolls if isinstance(b, dict) and b.get("video_path") and os.path.exists(b["video_path"])]


        if watermark_enabled:
            action = (
                "Applying watermark "
                "before subtitles"
            )
        else:
            action = (
                "Burning subtitles"
            )

        print(
            f"{action}: {video_name}...",
            flush=True,
        )

        (
            success,
            message,
            validation,
        ) = burn_video_file(
            input_file,
            subtitle_file,
            output_file,
            watermark_config=config,
            watermark_asset=watermark_asset,
            broll_items=rendered_clip_brolls if rendered_clip_brolls else None,
        )

        if not success:
            raise RuntimeError(message)

        rendered_count += 1

        print(
            "Done: "
            f"{output_file} "
            f"({validation['size']} bytes, "
            f"{validation['duration']:.2f}s)",
            flush=True,
        )

    if rendered_count == 0:
        raise FileNotFoundError(
            "No videos were rendered because "
            "matching ASS subtitle files were "
            "not found."
        )

    return output_folder