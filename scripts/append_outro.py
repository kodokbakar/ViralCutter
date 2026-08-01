"""Outro append functionality."""
import os
import subprocess
import json
from pathlib import Path


def get_video_info(video_path):
    """Get video width, height, fps, duration using ffprobe."""
    cmd = [
        "ffprobe", "-v", "quiet", "-print_format", "json",
        "-show_streams", "-show_format", video_path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        return None
    data = json.loads(result.stdout)
    
    info = {"width": 1080, "height": 1920, "fps": 30, "duration": 0}
    for stream in data.get("streams", []):
        if stream.get("codec_type") == "video":
            info["width"] = int(stream.get("width", 1080))
            info["height"] = int(stream.get("height", 1920))
            fps_str = stream.get("r_frame_rate", "30/1")
            if "/" in fps_str:
                num, den = fps_str.split("/")
                info["fps"] = round(int(num) / int(den))
            else:
                info["fps"] = int(float(fps_str))
            break
    fmt = data.get("format", {})
    info["duration"] = float(fmt.get("duration", 0))
    return info


def normalize_media(input_path, output_path, target_width, target_height, target_fps=30, target_audio_codec="aac"):
    """Normalize media to target format using FFmpeg."""
    filter_str = f"scale={target_width}:{target_height}:force_original_aspect_ratio=decrease,pad={target_width}:{target_height}:(ow-iw)/2:(oh-ih)/2,setsar=1,fps={target_fps}"
    
    cmd = [
        "ffmpeg", "-y", "-loglevel", "error", "-hide_banner",
        "-i", input_path,
        "-vf", filter_str,
        "-c:v", "libx264", "-preset", "fast", "-crf", "23",
        "-c:a", target_audio_codec, "-ar", "44100", "-ac", "2",
        output_path
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.returncode == 0, result.stderr if result.returncode != 0 else ""


def append_image_outro(video_path, image_path, output_path, duration=5.0, transition="fade", transition_duration=1.0):
    """Append image outro to video."""
    if not os.path.exists(video_path):
        return False, f"Video not found: {video_path}"
    if not os.path.exists(image_path):
        return False, f"Image not found: {image_path}"
    
    # Get video info for normalization
    info = get_video_info(video_path)
    if not info:
        return False, "Could not read video info"
    
    # Create temporary normalized outro video from image
    temp_outro = output_path + ".tmp_outro.mp4"
    
    # Generate outro video from image
    filter_str = (
        f"loop=loop=-1:size=1:start=0,"
        f"scale={info['width']}:{info['height']}:force_original_aspect_ratio=decrease,"
        f"pad={info['width']}:{info['height']}:(ow-iw)/2:(oh-ih)/2,"
        f"setsar=1,fps={info['fps']},"
        f"trim=duration={duration}"
    )
    
    cmd = [
        "ffmpeg", "-y", "-loglevel", "error", "-hide_banner",
        "-loop", "1", "-i", image_path,
        "-f", "lavfi", "-i", f"anullsrc=r=44100:cl=stereo",
        "-vf", filter_str,
        "-c:v", "libx264", "-preset", "fast", "-crf", "23",
        "-c:a", "aac", "-shortest",
        temp_outro
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        return False, f"Failed to create outro video: {result.stderr}"
    
    # Concatenate with transition
    success, msg = _concatenate_with_transition(video_path, temp_outro, output_path, transition, transition_duration)
    
    # Cleanup temp
    if os.path.exists(temp_outro):
        os.remove(temp_outro)
    
    return success, msg


def append_video_outro(video_path, outro_path, output_path, transition="fade", transition_duration=1.0):
    """Append video outro to video."""
    if not os.path.exists(video_path):
        return False, f"Video not found: {video_path}"
    if not os.path.exists(outro_path):
        return False, f"Outro not found: {outro_path}"
    
    # Get video info for normalization
    info = get_video_info(video_path)
    if not info:
        return False, "Could not read video info"
    
    # Normalize outro to match main video
    temp_outro = output_path + ".tmp_outro.mp4"
    ok, err = normalize_media(outro_path, temp_outro, info["width"], info["height"], info["fps"])
    if not ok:
        return False, f"Failed to normalize outro: {err}"
    
    # Concatenate with transition
    success, msg = _concatenate_with_transition(video_path, temp_outro, output_path, transition, transition_duration)
    
    # Cleanup temp
    if os.path.exists(temp_outro):
        os.remove(temp_outro)
    
    return success, msg


def append_text_outro(video_path, text, output_path, duration=5.0, font="Montserrat-Regular", font_size=48, transition="fade", transition_duration=1.0):
    """Append text outro to video."""
    if not os.path.exists(video_path):
        return False, f"Video not found: {video_path}"
    
    # Get video info
    info = get_video_info(video_path)
    if not info:
        return False, "Could not read video info"
    
    # Create text outro video
    temp_outro = output_path + ".tmp_outro.mp4"
    
    filter_str = (
        f"color=c=black:s={info['width']}x{info['height']}:r={info['fps']}:d={duration},"
        f"drawtext=text='{text}':fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
        f":fontsize={font_size}:fontcolor=white:x=(w-text_w)/2:y=(h-text_h)/2"
    )
    
    cmd = [
        "ffmpeg", "-y", "-loglevel", "error", "-hide_banner",
        "-f", "lavfi", "-i", f"color=c=black:s={info['width']}x{info['height']}:r={info['fps']}:d={duration}",
        "-f", "lavfi", "-i", f"anullsrc=r=44100:cl=stereo",
        "-vf", f"drawtext=text='{text}':fontsize={font_size}:fontcolor=white:x=(w-text_w)/2:y=(h-text_h)/2",
        "-c:v", "libx264", "-preset", "fast", "-crf", "23",
        "-c:a", "aac", "-shortest",
        temp_outro
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        return False, f"Failed to create text outro: {result.stderr}"
    
    # Concatenate
    success, msg = _concatenate_with_transition(video_path, temp_outro, output_path, transition, transition_duration)
    
    # Cleanup
    if os.path.exists(temp_outro):
        os.remove(temp_outro)
    
    return success, msg


def _concatenate_with_transition(video1, video2, output, transition="none", transition_duration=1.0):
    """Concatenate two videos with optional transition."""
    if transition == "none":
        # Simple concat
        concat_file = output + ".concat.txt"
        with open(concat_file, 'w') as f:
            f.write(f"file '{video1}'\nfile '{video2}'\n")
        
        cmd = [
            "ffmpeg", "-y", "-loglevel", "error", "-hide_banner",
            "-f", "concat", "-safe", "0", "-i", concat_file,
            "-c", "copy", output
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        os.remove(concat_file)
        return result.returncode == 0, result.stderr if result.returncode != 0 else ""
    
    elif transition == "fade":
        # Crossfade transition
        info = get_video_info(video1)
        if not info:
            return False, "Could not read video info"
        
        dur1 = info["duration"]
        offset = max(0, dur1 - transition_duration)
        
        filter_str = (
            f"[0:v][1:v]xfade=transition=fade:duration={transition_duration}:offset={offset}[v];"
            f"[0:a][1:a]acrossfade=d={transition_duration}[a]"
        )
        
        cmd = [
            "ffmpeg", "-y", "-loglevel", "error", "-hide_banner",
            "-i", video1, "-i", video2,
            "-filter_complex", filter_str,
            "-map", "[v]", "-map", "[a]",
            "-c:v", "libx264", "-preset", "fast", "-crf", "23",
            "-c:a", "aac",
            output
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        return result.returncode == 0, result.stderr if result.returncode != 0 else ""
    
    elif transition == "crossfade":
        # Same as fade for now
        return _concatenate_with_transition(video1, video2, output, "fade", transition_duration)
    
    return False, f"Unknown transition: {transition}"


def apply_outro_to_clips(project_folder, outro_type="image", outro_source=None, outro_text="Thanks for watching!",
                         duration=5.0, transition="fade", transition_duration=1.0):
    """Apply outro to each individual clip in the project."""
    if not outro_source and outro_type != "text":
        return False, "No outro source provided"

    # Find clips in burned_sub or cuts
    burned_folder = os.path.join(project_folder, "burned_sub")
    cuts_folder = os.path.join(project_folder, "cuts")

    if os.path.exists(burned_folder) and any(f.endswith(".mp4") for f in os.listdir(burned_folder)):
        clips_folder = burned_folder
    elif os.path.exists(cuts_folder) and any(f.endswith(".mp4") for f in os.listdir(cuts_folder)):
        clips_folder = cuts_folder
    else:
        return False, "No clips found"

    output_folder = os.path.join(project_folder, "outro_clips")
    os.makedirs(output_folder, exist_ok=True)

    files = sorted([f for f in os.listdir(clips_folder) if f.endswith(".mp4")])
    results = []

    for f in files:
        input_path = os.path.join(clips_folder, f)
        output_path = os.path.join(output_folder, f"{os.path.splitext(f)[0]}_outro.mp4")

        if outro_type == "image":
            ok, msg = append_image_outro(input_path, outro_source, output_path, duration, transition, transition_duration)
        elif outro_type == "video":
            ok, msg = append_video_outro(input_path, outro_source, output_path, transition, transition_duration)
        elif outro_type == "text":
            ok, msg = append_text_outro(input_path, outro_text, output_path, duration, transition=transition, transition_duration=transition_duration)
        else:
            ok, msg = False, f"Unknown outro type: {outro_type}"

        results.append({"file": f, "success": ok, "message": msg})

    successes = sum(1 for r in results if r["success"])
    return successes == len(results), f"{successes}/{len(results)} clips processed"


def apply_outro_to_compilation(project_folder, outro_type="image", outro_source=None, outro_text="Thanks for watching!",
                                duration=5.0, transition="fade", transition_duration=1.0):
    """Apply outro only to the final compilation."""
    if not outro_source and outro_type != "text":
        return False, "No outro source provided"

    compilation_path = os.path.join(project_folder, "compiled", "compilation.mp4")
    if not os.path.exists(compilation_path):
        return False, f"Compilation not found: {compilation_path}"

    output_path = os.path.join(project_folder, "compiled", "compilation_outro.mp4")

    if outro_type == "image":
        return append_image_outro(compilation_path, outro_source, output_path, duration, transition, transition_duration)
    elif outro_type == "video":
        return append_video_outro(compilation_path, outro_source, output_path, transition, transition_duration)
    elif outro_type == "text":
        return append_text_outro(compilation_path, outro_text, output_path, duration, transition=transition, transition_duration=transition_duration)
    else:
        return False, f"Unknown outro type: {outro_type}"
