import json
import os
import re
import subprocess


SENTENCE_ENDINGS = (".", "!", "?", "…", "。", "！", "？")


def to_seconds(value, default=0.0):
    if isinstance(value, (int, float)):
        return float(value) / 1000.0 if value > 10000 else float(value)

    try:
        return float(value)
    except (TypeError, ValueError):
        pass

    try:
        parts = str(value).split(":")
        if len(parts) == 3:
            hours, minutes, seconds = parts
            return int(hours) * 3600 + int(minutes) * 60 + float(seconds)
    except Exception:
        pass

    return default

def clamp(value, minimum, maximum=None):
    value = max(float(minimum), float(value))
    if maximum is not None:
        value = min(float(maximum), value)
    return value


def get_project_video_duration(project_folder):
    candidates = [
        os.path.join(project_folder, "input.mp4"),
        os.path.join(project_folder, "input_video.mp4"),
    ]

    input_video = next((path for path in candidates if os.path.exists(path)), None)
    if not input_video:
        return None

    try:
        result = subprocess.run(
            [
                "ffprobe",
                "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                input_video,
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
        )

        if result.returncode != 0:
            return None

        return float(result.stdout.strip())
    except Exception:
        return None


def apply_roll_padding(start, end, pre_roll, post_roll, video_duration=None):
    padded_start = clamp(start - float(pre_roll), 0.0, video_duration)
    padded_end = end + float(post_roll)

    if video_duration is not None:
        padded_end = min(video_duration, padded_end)

    if padded_end <= padded_start:
        padded_end = end

    return padded_start, padded_end

def clean_word(value):
    return str(value or "").strip()


def sentence_done(text):
    text = clean_word(text)
    return text.endswith(SENTENCE_ENDINGS)


def load_transcript_segments(project_folder):
    input_json = os.path.join(project_folder, "input.json")
    if not os.path.exists(input_json):
        return []

    with open(input_json, "r", encoding="utf-8") as f:
        data = json.load(f)

    return data.get("segments", [])


def build_word_sentences(transcript_segments):
    sentences = []
    current_words = []
    current_start = None
    current_end = None

    for segment in transcript_segments:
        words = segment.get("words") or []

        for word in words:
            text = clean_word(word.get("word"))
            start = word.get("start")
            end = word.get("end")

            if not text or start is None or end is None:
                continue

            start = to_seconds(start)
            end = to_seconds(end)

            if current_start is None:
                current_start = start

            current_end = end
            current_words.append(text)

            if sentence_done(text):
                sentences.append({
                    "start": current_start,
                    "end": current_end,
                    "text": " ".join(current_words).strip(),
                })
                current_words = []
                current_start = None
                current_end = None

    if current_words and current_start is not None and current_end is not None:
        sentences.append({
            "start": current_start,
            "end": current_end,
            "text": " ".join(current_words).strip(),
        })

    return sentences


def build_segment_sentences(transcript_segments):
    sentences = []

    for segment in transcript_segments:
        start = segment.get("start")
        end = segment.get("end")
        text = clean_word(segment.get("text"))

        if start is None or end is None or not text:
            continue

        sentences.append({
            "start": to_seconds(start),
            "end": to_seconds(end),
            "text": text,
        })

    return sentences


def build_sentences(project_folder):
    transcript_segments = load_transcript_segments(project_folder)

    word_sentences = build_word_sentences(transcript_segments)
    if word_sentences:
        return word_sentences

    return build_segment_sentences(transcript_segments)


def nearest_sentence_start(sentences, current_start, snap_window):
    candidates = [
        sentence["start"]
        for sentence in sentences
        if abs(sentence["start"] - current_start) <= snap_window
    ]

    if not candidates:
        return current_start

    return min(candidates, key=lambda value: abs(value - current_start))


def nearest_sentence_end(sentences, current_end, snap_window):
    candidates = [
        sentence["end"]
        for sentence in sentences
        if abs(sentence["end"] - current_end) <= snap_window
    ]

    if not candidates:
        return current_end

    return min(candidates, key=lambda value: abs(value - current_end))


def clamp_duration(start, end, original_start, original_end, min_duration, max_duration, video_duration=None):
    start = clamp(start, 0.0, video_duration)
    end = clamp(end, start, video_duration)

    duration = end - start

    if duration < min_duration:
        end = start + min_duration
        if video_duration is not None and end > video_duration:
            end = video_duration
            start = max(0.0, end - min_duration)

    duration = end - start

    if duration > max_duration:
        # Keep the extra context at the beginning, but cap the end.
        end = start + max_duration

        if video_duration is not None:
            end = min(video_duration, end)

        # If capping created invalid timing, fall back to original segment.
        if end <= start:
            start = original_start
            end = original_end

    return start, end


def refine_to_sentence_boundaries(
    viral_segments,
    project_folder,
    min_duration,
    max_duration,
    snap_window=4.0,
    pre_roll=1.25,
    post_roll=0.75,
):
    if not viral_segments or not isinstance(viral_segments.get("segments"), list):
        return viral_segments

    sentences = build_sentences(project_folder)
    if not sentences:
        print("[WARN] Sentence boundary snap skipped: no transcript sentences found. Applying pre/post-roll only.")

    video_duration = get_project_video_duration(project_folder)
    refined = []

    for segment in viral_segments["segments"]:
        start = to_seconds(segment.get("start_time"))
        end = to_seconds(
            segment.get("end_time"),
            start + to_seconds(segment.get("duration"), min_duration),
        )

        if end <= start:
            end = start + to_seconds(segment.get("duration"), min_duration)

        padded_start, padded_end = apply_roll_padding(
            start,
            end,
            pre_roll=pre_roll,
            post_roll=post_roll,
            video_duration=video_duration,
        )

        if sentences:
            snapped_start = nearest_sentence_start(sentences, padded_start, snap_window)
            snapped_end = nearest_sentence_end(sentences, padded_end, snap_window)
        else:
            snapped_start = padded_start
            snapped_end = padded_end

        snapped_start, snapped_end = clamp_duration(
            snapped_start,
            snapped_end,
            start,
            end,
            float(min_duration),
            float(max_duration),
            video_duration=video_duration,
        )

        updated = dict(segment)
        updated["original_start_time"] = round(start, 3)
        updated["original_end_time"] = round(end, 3)
        updated["pre_roll"] = float(pre_roll)
        updated["post_roll"] = float(post_roll)
        updated["padded_start_time"] = round(padded_start, 3)
        updated["padded_end_time"] = round(padded_end, 3)
        updated["start_time"] = round(snapped_start, 3)
        updated["end_time"] = round(snapped_end, 3)
        updated["duration"] = round(snapped_end - snapped_start, 3)
        updated["roll_padded"] = (
            abs(updated["padded_start_time"] - start) > 0.001
            or abs(updated["padded_end_time"] - end) > 0.001
        )
        updated["sentence_snapped"] = (
            abs(updated["start_time"] - updated["padded_start_time"]) > 0.001
            or abs(updated["end_time"] - updated["padded_end_time"]) > 0.001
        )

        refined.append(updated)

        if updated["roll_padded"] or updated["sentence_snapped"]:
            print(
                "[refine] {}: {:.3f}-{:.3f} -> {:.3f}-{:.3f}".format(
                    updated.get("title", "Segment"),
                    start,
                    end,
                    updated["start_time"],
                    updated["end_time"],
                )
            )

    viral_segments = dict(viral_segments)
    viral_segments["segments"] = refined
    return viral_segments