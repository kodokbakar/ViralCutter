import os
import json
import subprocess
from typing import List, Dict, Tuple, Optional, Any

def extract_words_from_transcript(transcript_data: Any) -> List[Dict[str, Any]]:
    """
    Extracts flat word list with start, end, word from transcript data dict or list.
    """
    words = []
    if isinstance(transcript_data, dict):
        segments = transcript_data.get("segments", [])
    elif isinstance(transcript_data, list):
        segments = transcript_data
    else:
        return words

    for seg in segments:
        seg_words = seg.get("words")
        if seg_words and isinstance(seg_words, list):
            for w in seg_words:
                text = str(w.get("word") or "").strip()
                start = w.get("start")
                end = w.get("end")
                if text and start is not None and end is not None:
                    words.append({
                        "word": text,
                        "start": float(start),
                        "end": float(end),
                        "score": float(w.get("score", 1.0) or 1.0)
                    })
        else:
            # Fallback if words not present in segment
            text = str(seg.get("text") or "").strip()
            start = seg.get("start")
            end = seg.get("end")
            if text and start is not None and end is not None:
                words.append({
                    "word": text,
                    "start": float(start),
                    "end": float(end),
                    "score": 1.0
                })
    return words

def snap_time_to_word_boundary(
    timestamp: float,
    words: List[Dict[str, Any]],
    is_start: bool,
    window: float = 3.0,
    margin: float = 0.05
) -> float:
    """
    Snaps timestamp to the nearest word boundary within a search window.
    For start: snaps to word start minus safety margin.
    For end: snaps to word end plus safety margin.
    """
    if not words:
        return max(0.0, float(timestamp))

    target = float(timestamp)
    candidates = []
    for w in words:
        ref_time = w["start"] if is_start else w["end"]
        diff = abs(ref_time - target)
        if diff <= window:
            candidates.append((diff, ref_time))

    if not candidates:
        return max(0.0, target)

    candidates.sort(key=lambda x: x[0])
    best_time = candidates[0][1]

    if is_start:
        return max(0.0, round(best_time - margin, 3))
    else:
        return max(0.0, round(best_time + margin, 3))

def snap_segment_boundaries(
    start_time: float,
    end_time: float,
    words: List[Dict[str, Any]],
    margin: float = 0.05,
    min_duration: float = 1.0
) -> Tuple[float, float]:
    """
    Snaps both start and end times to word boundaries while preserving minimum duration.
    """
    snapped_start = snap_time_to_word_boundary(start_time, words, is_start=True, margin=margin)
    snapped_end = snap_time_to_word_boundary(end_time, words, is_start=False, margin=margin)

    if snapped_end <= snapped_start + min_duration:
        snapped_end = max(snapped_start + min_duration, end_time)

    return snapped_start, snapped_end

def build_narrative_prompt(
    transcript_text: str,
    target_min: float = 20.0,
    target_max: float = 90.0,
    num_topics: int = 3
) -> str:
    return f"""You are an elite short-form video editor specializing in narrative retention.
Analyze the following transcript with timestamps and extract {num_topics} standalone, high-impact topics.

Each topic MUST have a strict 3-part storytelling structure:
1. Hook (Pemantik): The opening question, bold statement, or intriguing premise that stops the scroll (approx 3-10s).
2. Core (Pembahasan Inti): The essential explanation, story body, or argument.
3. Payoff (Klimaks / Penutup): The key conclusion, unexpected twist, practical takeaway, or satisfying punchline.

Target duration for the total spliced topic is between {int(target_min)}s and {int(target_max)}s.
The sub-segments may be continuous or skip boring filler/tangents.

TRANSCRIPT:
{transcript_text}

OUTPUT FORMAT: Return VALID JSON ONLY matching this structure:
{{
  "topics": [
    {{
      "title": "Short punchy title",
      "rationale": "Why this story holds retention",
      "target_duration": 45.0,
      "segments": {{
        "hook": {{
          "start_time": 0.0,
          "end_time": 5.0,
          "text": "Exact text of the hook"
        }},
        "core": {{
          "start_time": 12.0,
          "end_time": 35.0,
          "text": "Exact text of the core"
        }},
        "payoff": {{
          "start_time": 50.0,
          "end_time": 60.0,
          "text": "Exact text of the payoff"
        }}
      }}
    }}
  ]
}}
"""

def parse_narrative_topics(llm_response: str) -> List[Dict[str, Any]]:
    """
    Parses LLM response into normalized list of topic dictionaries.
    """
    import re
    cleaned = re.sub(r'<think>.*?</think>', '', str(llm_response), flags=re.DOTALL)
    cleaned = re.sub(r'```(?:json)?', '', cleaned)
    cleaned = cleaned.strip()

    data = None
    try:
        data = json.loads(cleaned)
    except Exception:
        match = re.search(r'\{.*"topics"\s*:\s*\[.*\]\s*\}', cleaned, re.DOTALL)
        if match:
            try:
                data = json.loads(match.group(0))
            except Exception:
                return []
        else:
            return []

    raw_topics = data.get("topics", []) if isinstance(data, dict) else []
    valid_topics = []
    for t in raw_topics:
        if not isinstance(t, dict):
            continue
        segs = t.get("segments", {})
        if not isinstance(segs, dict):
            continue

        normalized_segs = {}
        for key in ["hook", "core", "payoff"]:
            part = segs.get(key, {})
            if isinstance(part, dict):
                normalized_segs[key] = {
                    "start_time": float(part.get("start_time", 0.0)),
                    "end_time": float(part.get("end_time", 0.0)),
                    "text": str(part.get("text", "")).strip()
                }

        if normalized_segs:
            valid_topics.append({
                "title": str(t.get("title", "Untitled Topic")),
                "rationale": str(t.get("rationale", "")),
                "target_duration": float(t.get("target_duration", 0.0)),
                "segments": normalized_segs
            })

    return valid_topics

def snap_narrative_topic_segments(
    topic: Dict[str, Any],
    words: List[Dict[str, Any]],
    margin: float = 0.05
) -> Dict[str, Any]:
    """
    Snaps all sub-segments of a topic (hook, core, payoff) to word boundaries.
    """
    updated_topic = json.loads(json.dumps(topic))
    segs = updated_topic.get("segments", {})

    for key, seg in segs.items():
        s = seg.get("start_time", 0.0)
        e = seg.get("end_time", 0.0)
        snapped_s, snapped_e = snap_segment_boundaries(s, e, words, margin=margin)
        seg["snapped_start"] = snapped_s
        seg["snapped_end"] = snapped_e
        seg["duration"] = round(snapped_e - snapped_s, 3)

    return updated_topic

def extract_audio_for_transcription(video_path: str, output_wav: str) -> str:
    """
    Extracts 16kHz 16-bit mono PCM audio from video for fast, accurate speech transcription.
    """
    if os.path.exists(output_wav) and os.path.getsize(output_wav) > 1000:
        return output_wav

    out_dir = os.path.dirname(os.path.abspath(output_wav))
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
    cmd = [
        "ffmpeg", "-y",
        "-i", video_path,
        "-vn",
        "-acodec", "pcm_s16le",
        "-ar", "16000",
        "-ac", "1",
        output_wav
    ]
    subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return output_wav

def build_ffmpeg_cut_command(video_path: str, start: float, end: float, output_path: str) -> List[str]:
    """
    Builds FFmpeg command to cut a segment accurately with re-encoding to avoid keyframe offset.
    """
    return [
        "ffmpeg", "-y",
        "-ss", f"{float(start):.3f}",
        "-to", f"{float(end):.3f}",
        "-i", video_path,
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "18",
        "-c:a", "aac",
        "-b:a", "192k",
        "-avoid_negative_ts", "make_zero",
        output_path
    ]

def splice_topic_segments(
    video_path: str,
    segments: List[Tuple[float, float]],
    output_path: str,
    temp_dir: Optional[str] = None
) -> str:
    """
    Extracts sub-segments and splices them into one video file.
    If single segment, cuts directly to output_path.
    If multiple segments, cuts each and concats losslessly via concat demuxer.
    """
    import shutil
    if not segments:
        raise ValueError("No segments provided for splicing.")

    out_dir = os.path.dirname(os.path.abspath(output_path))
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)

    valid_segs = [(s, e) for s, e in segments if e > s]
    if not valid_segs:
        raise ValueError("All segments have zero or invalid duration.")

    if len(valid_segs) == 1:
        s, e = valid_segs[0]
        cmd = build_ffmpeg_cut_command(video_path, s, e, output_path)
        subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return output_path

    cleanup_temp = False
    if not temp_dir:
        temp_dir = os.path.join(out_dir or ".", "temp_splice")
        cleanup_temp = True
    os.makedirs(temp_dir, exist_ok=True)

    sub_files = []
    try:
        for idx, (s, e) in enumerate(valid_segs):
            sub_path = os.path.join(temp_dir, f"subseg_{idx:03d}.mp4")
            cmd = build_ffmpeg_cut_command(video_path, s, e, sub_path)
            subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            sub_files.append(sub_path)

        concat_list_path = os.path.join(temp_dir, "concat_list.txt")
        with open(concat_list_path, "w", encoding="utf-8") as f:
            for p in sub_files:
                f.write(f"file '{os.path.abspath(p)}'\n")

        concat_cmd = [
            "ffmpeg", "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", concat_list_path,
            "-c", "copy",
            output_path
        ]
        subprocess.run(concat_cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    finally:
        if cleanup_temp and os.path.exists(temp_dir):
            shutil.rmtree(temp_dir, ignore_errors=True)

    return output_path
