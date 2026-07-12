import argparse
import os
import re
import shutil
import subprocess


VIDEO_EXTENSIONS = (".mp4", ".mkv", ".mov", ".avi")


def segment_sort_key(path):
    name = os.path.basename(path)
    match = re.search(r"(?:segment|output|final-output)?[-_]?(\d+)", name, re.IGNORECASE)
    return (int(match.group(1)) if match else 10**9, name.lower())


def find_segment_files(segments_folder):
    if not os.path.isdir(segments_folder):
        raise FileNotFoundError(f"Segments folder not found: {segments_folder}")

    files = [
        os.path.join(segments_folder, name)
        for name in os.listdir(segments_folder)
        if name.lower().endswith(VIDEO_EXTENSIONS)
        and "input" not in name.lower()
        and "compilation" not in name.lower()
        and "temp_video_no_audio" not in name.lower()
    ]

    files.sort(key=segment_sort_key)

    if not files:
        raise FileNotFoundError(f"No segment videos found in: {segments_folder}")

    return files


def project_root_for(segments_folder):
    folder = os.path.abspath(segments_folder)
    if os.path.basename(folder) in {"burned_sub", "final", "cuts"}:
        return os.path.dirname(folder)
    return folder


def ffprobe(path):
    cmd = [
        "ffprobe",
        "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "stream=codec_name,width,height,r_frame_rate",
        "-of", "default=noprint_wrappers=1:nokey=1",
        path,
    ]
    result = subprocess.run(cmd, check=True, capture_output=True, text=True)
    return tuple(line.strip() for line in result.stdout.splitlines() if line.strip())


def same_video_format(paths):
    if len(paths) < 2:
        return True

    first = ffprobe(paths[0])
    return all(ffprobe(path) == first for path in paths[1:])


def write_concat_list(paths, filelist_path):
    with open(filelist_path, "w", encoding="utf-8") as f:
        for path in paths:
            safe_path = os.path.abspath(path).replace("'", "'\\''")
            f.write(f"file '{safe_path}'\n")


def concat_copy(paths, output_path, work_dir):
    filelist_path = os.path.join(work_dir, "filelist.txt")
    write_concat_list(paths, filelist_path)

    cmd = [
        "ffmpeg",
        "-y",
        "-hide_banner",
        "-loglevel", "error",
        "-stats",
        "-f", "concat",
        "-safe", "0",
        "-i", filelist_path,
        "-c", "copy",
        output_path,
    ]
    subprocess.run(cmd, check=True)


def concat_reencode(paths, output_path, work_dir):
    normalized_dir = os.path.join(work_dir, "normalized")
    os.makedirs(normalized_dir, exist_ok=True)

    normalized = []
    for index, path in enumerate(paths):
        out = os.path.join(normalized_dir, f"{index:03d}.mp4")
        cmd = [
            "ffmpeg",
            "-y",
            "-hide_banner",
            "-loglevel", "error",
            "-stats",
            "-i", path,
            "-vf", "scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2,setsar=1,fps=30",
            "-c:v", "libx264",
            "-preset", "veryfast",
            "-crf", "20",
            "-pix_fmt", "yuv420p",
            "-c:a", "aac",
            "-b:a", "192k",
            "-ar", "48000",
            out,
        ]
        subprocess.run(cmd, check=True)
        normalized.append(out)

    concat_copy(normalized, output_path, work_dir)


def compile_with_crossfade(paths, output_path, duration):
    if len(paths) < 2:
        return paths[0]

    inputs = []
    for path in paths:
        inputs.extend(["-i", path])

    filters = []
    last_video = "[0:v]"
    last_audio = "[0:a]"
    offset = 0.0

    for index in range(1, len(paths)):
        clip_duration = get_duration(paths[index - 1])
        offset += max(clip_duration - duration, 0)

        video_out = f"[v{index}]"
        audio_out = f"[a{index}]"

        filters.append(
            f"{last_video}[{index}:v]xfade=transition=fade:duration={duration}:offset={offset}{video_out}"
        )
        filters.append(
            f"{last_audio}[{index}:a]acrossfade=d={duration}{audio_out}"
        )

        last_video = video_out
        last_audio = audio_out

    cmd = [
        "ffmpeg",
        "-y",
        "-hide_banner",
        "-loglevel", "error",
        "-stats",
        *inputs,
        "-filter_complex", ";".join(filters),
        "-map", last_video,
        "-map", last_audio,
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-crf", "20",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        "-b:a", "192k",
        output_path,
    ]
    subprocess.run(cmd, check=True)


def get_duration(path):
    cmd = [
        "ffprobe",
        "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        path,
    ]
    result = subprocess.run(cmd, check=True, capture_output=True, text=True)
    return float(result.stdout.strip())


def mirror_to_output_folder(compilation_path, project_root):
    output_dir = os.path.join(project_root, "output")
    os.makedirs(output_dir, exist_ok=True)

    mirrored_path = os.path.join(output_dir, os.path.basename(compilation_path))
    if os.path.abspath(compilation_path) != os.path.abspath(mirrored_path):
        shutil.copy2(compilation_path, mirrored_path)

    return mirrored_path


def compile_segments(
    segments_folder: str,
    output_path: str = None,
    crossfade_duration: float = 0.0,
    add_transitions: bool = False,
) -> str:
    """
    Compile processed segment videos into one MP4.

    Returns the main compilation path.
    """
    paths = find_segment_files(segments_folder)

    if len(paths) == 1:
        return paths[0]

    project_root = project_root_for(segments_folder)
    output_path = output_path or os.path.join(project_root, "compilation.mp4")
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

    work_dir = os.path.join(project_root, ".compile_tmp")
    os.makedirs(work_dir, exist_ok=True)

    try:
        if add_transitions and crossfade_duration > 0:
            compile_with_crossfade(paths, output_path, crossfade_duration)
        elif same_video_format(paths):
            concat_copy(paths, output_path, work_dir)
        else:
            print("Warning: segment formats differ. Re-encoding before concat.")
            concat_reencode(paths, output_path, work_dir)

        mirror_to_output_folder(output_path, project_root)
        print(f"Compilation generated: {output_path}")
        return output_path
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)


def main():
    parser = argparse.ArgumentParser(description="Compile ViralCutter segments into one video.")
    parser.add_argument("segments_folder", help="Folder containing processed segment videos.")
    parser.add_argument("--output", help="Output MP4 path.")
    parser.add_argument("--crossfade-duration", type=float, default=0.0)
    parser.add_argument("--transitions", action="store_true", help="Enable crossfade transitions.")
    args = parser.parse_args()

    compile_segments(
        args.segments_folder,
        output_path=args.output,
        crossfade_duration=args.crossfade_duration,
        add_transitions=args.transitions,
    )


if __name__ == "__main__":
    main()