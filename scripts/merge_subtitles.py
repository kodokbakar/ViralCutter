import json
import os
import re
import shutil
from dataclasses import dataclass


@dataclass
class SubtitleEntry:
    index: int
    start: float
    end: float
    text: str


def timestamp_to_seconds(value):
    value = value.strip().replace(",", ".")
    hours, minutes, seconds = value.split(":")
    return int(hours) * 3600 + int(minutes) * 60 + float(seconds)


def seconds_to_timestamp(value):
    value = max(0.0, float(value))
    hours = int(value // 3600)
    minutes = int((value % 3600) // 60)
    seconds = int(value % 60)
    millis = int(round((value - int(value)) * 1000))

    if millis == 1000:
        seconds += 1
        millis = 0
    if seconds == 60:
        minutes += 1
        seconds = 0
    if minutes == 60:
        hours += 1
        minutes = 0

    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{millis:03d}"


def parse_timestamp(line):
    start, end = line.split("-->", 1)
    return timestamp_to_seconds(start), timestamp_to_seconds(end)


def parse_srt(filepath):
    with open(filepath, "r", encoding="utf-8-sig") as f:
        content = f.read().strip()

    if not content:
        return []

    entries = []
    blocks = re.split(r"\n\s*\n", content.replace("\r\n", "\n"))

    for block in blocks:
        lines = [line.rstrip() for line in block.splitlines() if line.strip()]
        if len(lines) < 3 or "-->" not in lines[1]:
            continue

        start, end = parse_timestamp(lines[1])
        entries.append(SubtitleEntry(int(lines[0]), start, end, "\n".join(lines[2:])))

    return entries


def parse_whisper_json(filepath):
    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)

    entries = []
    counter = 1

    for segment in data.get("segments", []):
        words = segment.get("words") or []
        if words:
            for word in words:
                text = (word.get("word") or "").strip()
                start = word.get("start")
                end = word.get("end")
                if text and start is not None and end is not None:
                    entries.append(SubtitleEntry(counter, float(start), float(end), text))
                    counter += 1
        else:
            text = (segment.get("text") or "").strip()
            start = segment.get("start")
            end = segment.get("end")
            if text and start is not None and end is not None:
                entries.append(SubtitleEntry(counter, float(start), float(end), text))
                counter += 1

    return entries


def write_srt(entries, output_path):
    with open(output_path, "w", encoding="utf-8") as f:
        for entry in entries:
            f.write(f"{entry.index}\n")
            f.write(f"{seconds_to_timestamp(entry.start)} --> {seconds_to_timestamp(entry.end)}\n")
            f.write(f"{entry.text}\n\n")


def merge_srt_files(srt_files, segment_durations, output_path):
    all_entries = []
    time_offset = 0.0
    counter = 1

    for srt_path, duration in zip(srt_files, segment_durations):
        for entry in parse_srt(srt_path):
            all_entries.append(
                SubtitleEntry(counter, entry.start + time_offset, entry.end + time_offset, entry.text)
            )
            counter += 1
        time_offset += float(duration)

    write_srt(all_entries, output_path)
    return output_path


def merge_subtitle_entries(subtitle_files, segment_durations, output_path):
    all_entries = []
    time_offset = 0.0
    counter = 1

    for subtitle_path, duration in zip(subtitle_files, segment_durations):
        entries = parse_srt(subtitle_path) if subtitle_path.endswith(".srt") else parse_whisper_json(subtitle_path)

        for entry in entries:
            all_entries.append(
                SubtitleEntry(counter, entry.start + time_offset, entry.end + time_offset, entry.text)
            )
            counter += 1

        time_offset += float(duration)

    if not all_entries:
        raise FileNotFoundError("No subtitle entries found to merge.")

    write_srt(all_entries, output_path)
    return output_path


def subtitle_candidates_for_video(video_path, project_root):
    base = os.path.splitext(os.path.basename(video_path))[0]
    base = re.sub(r"_subtitled$", "", base)

    return [
        os.path.join(project_root, "subs", f"{base}.srt"),
        os.path.join(project_root, "subs", f"{base}_processed.srt"),
        os.path.join(project_root, "subs", f"{base}.json"),
        os.path.join(project_root, "subs", f"{base}_processed.json"),
    ]


def find_matching_subtitle(video_path, project_root):
    for path in subtitle_candidates_for_video(video_path, project_root):
        if os.path.exists(path):
            return path
    return None


def merge_project_subtitles(video_paths, segment_durations, project_root, output_path):
    subtitle_files = []
    for video_path in video_paths:
        subtitle_path = find_matching_subtitle(video_path, project_root)
        if not subtitle_path:
            raise FileNotFoundError(f"No subtitle file found for: {os.path.basename(video_path)}")
        subtitle_files.append(subtitle_path)

    merged_path = merge_subtitle_entries(subtitle_files, segment_durations, output_path)

    output_dir = os.path.join(project_root, "output")
    os.makedirs(output_dir, exist_ok=True)
    mirrored_path = os.path.join(output_dir, os.path.basename(output_path))
    if os.path.abspath(merged_path) != os.path.abspath(mirrored_path):
        shutil.copy2(merged_path, mirrored_path)

    return merged_path