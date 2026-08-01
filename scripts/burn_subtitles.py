import os
import subprocess

from scripts import watermark


def _escape_filter_path(path):
    return (
        os.path.abspath(path)
        .replace("\\", "/")
        .replace(":", "\\:")
        .replace("'", "\\'")
    )


def burn_video_file(
    video_path,
    subtitle_path,
    output_path,
    *,
    watermark_config=None,
    watermark_asset=None,
):
    """
    Burn ASS subtitles into one video.

    When watermarking is enabled, FFmpeg applies
    the watermark first and subtitles second.
    """
    subtitle_file_ffmpeg = (
        _escape_filter_path(subtitle_path)
    )

    watermark_enabled = bool(
        watermark_config
        and watermark_config.get("mode")
        in {"image", "text"}
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
                    "-loop",
                    "1",
                    "-framerate",
                    "30",
                    "-i",
                    watermark_asset,
                ]
            )

            filter_complex = (
                watermark.build_filter(
                    watermark_config,
                    video_path,
                )
            )

            filter_complex += (
                ";[watermarked]"
                f"subtitles='{subtitle_file_ffmpeg}'"
                "[video_out]"
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
                    (
                        "subtitles="
                        f"'{subtitle_file_ffmpeg}'"
                    ),
                ]
            )

        command.extend(
            [
                "-c:v",
                encoder,
                "-preset",
                preset,
                "-b:v",
                "5M",
                "-pix_fmt",
                "yuv420p",
                "-c:a",
                "copy",
            ]
        )

        if watermark_enabled:
            command.append("-shortest")

        command.append(output_path)

        subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True,
        )

    try:
        run_ffmpeg(
            "h264_nvenc",
            "p1",
        )

        return True, "NVENC Success"

    except subprocess.CalledProcessError as nvenc_error:
        print(
            f"NVENC failed ({nvenc_error}). "
            "Falling back to libx264..."
        )

        try:
            run_ffmpeg(
                "libx264",
                "ultrafast",
            )

            return True, "CPU Success"

        except subprocess.CalledProcessError as cpu_error:
            ffmpeg_log = (
                cpu_error.stderr
                or ""
            ).strip()

            message = (
                "Failed to render subtitles for "
                f"{os.path.basename(video_path)}: "
                f"{cpu_error}"
            )

            if ffmpeg_log:
                message += (
                    f" | FFmpeg: {ffmpeg_log}"
                )

            print(message)

            return False, message

    except Exception as error:
        return False, str(error)


def burn(
    project_folder="tmp",
    watermark_config=None,
):
    project_folder_abs = os.path.abspath(
        project_folder
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

    if not os.path.isdir(videos_folder):
        raise FileNotFoundError(
            "Final video folder not found: "
            f"{videos_folder}"
        )

    if not os.path.isdir(subs_folder):
        raise FileNotFoundError(
            "ASS subtitle folder not found: "
            f"{subs_folder}"
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
        config["mode"] != "disabled"
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
            processed_candidate = os.path.join(
                subs_folder,
                f"{video_name}_processed.ass",
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
                f"{subtitle_file}"
            )
            continue

        input_file = os.path.join(
            videos_folder,
            video_file,
        )
        output_file = os.path.join(
            output_folder,
            f"{video_name}_subtitled.mp4",
        )

        if watermark_enabled:
            print(
                "Applying watermark before "
                f"subtitles: {video_name}..."
            )
        else:
            print(
                f"Burning subtitles: "
                f"{video_name}..."
            )

        success, message = burn_video_file(
            input_file,
            subtitle_file,
            output_file,
            watermark_config=config,
            watermark_asset=watermark_asset,
        )

        if not success:
            raise RuntimeError(message)

        rendered_count += 1

        print(
            f"Done: {output_file}"
        )

    if rendered_count == 0:
        raise FileNotFoundError(
            "No videos were rendered because "
            "matching ASS subtitle files "
            "were not found."
        )

    return output_folder