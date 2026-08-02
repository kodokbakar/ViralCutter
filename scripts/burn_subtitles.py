import os
import shlex
import subprocess

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
):
    """
    Render one final clip.

    Visual order:
        source video
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

            (
                filter_complex,
                filter_summary,
            ) = watermark.build_filter(
                watermark_config,
                video_path,
            )

            filter_complex += (
                ";[watermarked]"
                f"{subtitle_filter}"
                "[video_out]"
            )

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
                f"{filter_complex}",
                flush=True,
            )

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
            capture_output=True,
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
):
    project_folder_abs = (
        os.path.abspath(
            project_folder
        )
    )

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
        output_file = os.path.join(
            output_folder,
            (
                f"{video_name}"
                "_subtitled.mp4"
            ),
        )

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
            watermark_asset=(
                watermark_asset
            ),
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