import json
import os
import re


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


def clamp_duration(start, end, original_start, original_end, min_duration, max_duration):
    duration = end - start

    if duration < min_duration:
        end = start + min_duration

    duration = end - start

    if duration > max_duration:
        # Prefer keeping the cleaner sentence start, then cap the end.
        end = start + max_duration

        # If the original segment was already inside the max range, fall back to original timing.
        original_duration = original_end - original_start
        if min_duration <= original_duration <= max_duration:
            start = original_start
            end = original_end

    return start, end


def refine_to_sentence_boundaries(viral_segments, project_folder, min_duration, max_duration, snap_window=4.0):
    if not viral_segments or not isinstance(viral_segments.get("segments"), list):
        return viral_segments

    sentences = build_sentences(project_folder)
    if not sentences:
        print("[WARN] Sentence boundary snap skipped: no transcript sentences found.")
        return viral_segments

    refined = []

    for segment in viral_segments["segments"]:
        start = to_seconds(segment.get("start_time"))
        end = to_seconds(segment.get("end_time"), start + to_seconds(segment.get("duration")))

        if end <= start:
            end = start + to_seconds(segment.get("duration"), min_duration)

        snapped_start = nearest_sentence_start(sentences, start, snap_window)
        snapped_end = nearest_sentence_end(sentences, end, snap_window)

        snapped_start, snapped_end = clamp_duration(
            snapped_start,
            snapped_end,
            start,
            end,
            float(min_duration),
            float(max_duration),
        )

        updated = dict(segment)
        updated["original_start_time"] = start
        updated["original_end_time"] = end
        updated["start_time"] = round(snapped_start, 3)
        updated["end_time"] = round(snapped_end, 3)
        updated["duration"] = round(snapped_end - snapped_start, 3)
        updated["sentence_snapped"] = (
            abs(updated["start_time"] - start) > 0.001
            or abs(updated["end_time"] - end) > 0.001
        )

        refined.append(updated)

        if updated["sentence_snapped"]:
            print(
                "[snap] {}: {:.3f}-{:.3f} -> {:.3f}-{:.3f}".format(
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