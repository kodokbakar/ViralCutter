import os
import subprocess


# Safe-area margins (px) to avoid platform UI overlays covering the watermark.
SAFE_AREA_TIKTOK_BOTTOM = 150
SAFE_AREA_IG_BOTTOM = 120
SAFE_AREA_SHORTS_BOTTOM = 120
SAFE_AREA_TIKTOK_LEFT = 90
SAFE_AREA_TIKTOK_RIGHT = 90


def get_watermark_filter(logo_path, position, scale, opacity, h_margin, v_margin, custom_x, custom_y):
    """
    Build FFmpeg overlay filter string for watermark.
    
    Position presets: top-left, top-right, bottom-left, bottom-right, center
    Returns: vf filter string for overlay
    """
    # Escape path for FFmpeg filter
    logo_escaped = logo_path.replace('\\', '/').replace(':', '\\:')
    
    # Scale filter for logo
    scale_filter = f"scale=iw*{scale}:ih*{scale}"
    
    # Opacity filter (using format=rgba and colorchannelmixer)
    opacity_filter = f"format=rgba,colorchannelmixer=aa={opacity}"
    
    # Combine logo processing filters
    logo_filters = f"[1:v]{scale_filter},{opacity_filter}[logo];"
    
    # Calculate overlay position
    if position == "top-left":
        overlay_pos = f"{h_margin}:{v_margin}"
    elif position == "top-right":
        overlay_pos = f"main_w-overlay_w-{h_margin}:{v_margin}"
    elif position == "bottom-left":
        overlay_pos = f"{h_margin}:main_h-overlay_h-{v_margin}"
    elif position == "bottom-right":
        overlay_pos = f"main_w-overlay_w-{h_margin}:main_h-overlay_h-{v_margin}"
    elif position == "center":
        overlay_pos = "(main_w-overlay_w)/2:(main_h-overlay_h)/2"
    elif position == "custom":
        overlay_pos = f"{custom_x}:{custom_y}"
    else:
        overlay_pos = f"{h_margin}:{v_margin}"
    
    # Full filter string
    filter_str = f"{logo_filters}[0:v][logo]overlay={overlay_pos}"
    
    return filter_str


def apply_watermark(video_path, logo_path, output_path, position="bottom-right", 
                    scale=0.15, opacity=0.8, h_margin=20, v_margin=20,
                    custom_x=100, custom_y=100):
    """
    Apply image watermark to a video file.
    
    Args:
        video_path: Input video file
        logo_path: Watermark logo image (PNG with transparency recommended)
        output_path: Output video file
        position: Preset position (top-left, top-right, bottom-left, bottom-right, center, custom)
        scale: Logo scale factor (0.0-1.0)
        opacity: Logo opacity (0.0-1.0)
        h_margin: Horizontal margin in pixels
        v_margin: Vertical margin in pixels
        custom_x: Custom X position (only used when position="custom")
        custom_y: Custom Y position (only used when position="custom")
    
    Returns:
        tuple: (success: bool, message: str)
    """
    if not os.path.exists(video_path):
        return False, f"Video not found: {video_path}"
    if not os.path.exists(logo_path):
        return False, f"Logo not found: {logo_path}"
    if not (0.0 <= scale <= 1.0):
        return False, f"scale must be 0.0-1.0, got {scale}"
    if not (0.0 <= opacity <= 1.0):
        return False, f"opacity must be 0.0-1.0, got {opacity}"
    if not isinstance(h_margin, (int, float)) or h_margin < 0:
        return False, f"h_margin must be non-negative, got {h_margin}"
    if not isinstance(v_margin, (int, float)) or v_margin < 0:
        return False, f"v_margin must be non-negative, got {v_margin}"
    
    filter_str = get_watermark_filter(logo_path, position, scale, opacity, h_margin, v_margin, custom_x, custom_y)
    
    def run_ffmpeg(encoder, preset):
        cmd = [
            "ffmpeg", "-y", "-loglevel", "error", "-hide_banner",
            "-i", video_path,
            "-i", logo_path,
            "-filter_complex", filter_str,
            "-c:v", encoder,
            "-preset", preset,
            "-b:v", "5M",
            "-pix_fmt", "yuv420p",
            "-c:a", "copy",
            output_path
        ]
        subprocess.run(cmd, check=True, capture_output=True)
    
    # Try NVENC first, fallback to CPU
    try:
        run_ffmpeg("h264_nvenc", "p1")
        return True, "NVENC Success"
    except subprocess.CalledProcessError:
        try:
            run_ffmpeg("libx264", "ultrafast")
            return True, "CPU Success"
        except subprocess.CalledProcessError as e:
            err_msg = f"Failed to apply watermark: {e}"
            if e.stderr:
                err_msg += f" | FFmpeg: {e.stderr.decode('utf-8')}"
            return False, err_msg
    except Exception as e:
        return False, str(e)


def watermark(project_folder="tmp", logo_path=None, position="bottom-right",
              scale=0.15, opacity=0.8, h_margin=20, v_margin=20,
              custom_x=100, custom_y=100):
    """
    Apply watermark to all videos in project's burned_sub or final folder.
    
    Args:
        project_folder: Project folder path
        logo_path: Path to watermark logo image
        position: Watermark position preset
        scale: Logo scale factor
        opacity: Logo opacity
        h_margin: Horizontal margin
        v_margin: Vertical margin
        custom_x: Custom X position
        custom_y: Custom Y position
    """
    if not logo_path or not os.path.exists(logo_path):
        print("Watermark skipped: No valid logo provided.")
        return
    
    if project_folder and not os.path.isabs(project_folder):
        project_folder = os.path.abspath(project_folder)
    
    # Check burned_sub first, then final
    burned_folder = os.path.join(project_folder, 'burned_sub')
    final_folder = os.path.join(project_folder, 'final')
    
    if os.path.exists(burned_folder) and any(f.endswith('.mp4') for f in os.listdir(burned_folder)):
        videos_folder = burned_folder
        output_folder = os.path.join(project_folder, 'watermarked')
    elif os.path.exists(final_folder) and any(f.endswith('.mp4') for f in os.listdir(final_folder)):
        videos_folder = final_folder
        output_folder = os.path.join(project_folder, 'watermarked')
    else:
        print("No videos found to watermark.")
        return
    
    os.makedirs(output_folder, exist_ok=True)
    
    files = [f for f in os.listdir(videos_folder) if f.endswith(('.mp4', '.mkv', '.avi'))]
    
    if not files:
        print("No video files found for watermarking.")
        return
    
    print(f"Applying watermark to {len(files)} video(s)...")
    
    for video_file in files:
        video_path = os.path.join(videos_folder, video_file)
        output_name = os.path.splitext(video_file)[0] + "_watermarked.mp4"
        output_path = os.path.join(output_folder, output_name)
        
        print(f"Watermarking: {video_file}...")
        success, msg = apply_watermark(
            video_path, logo_path, output_path,
            position=position, scale=scale, opacity=opacity,
            h_margin=h_margin, v_margin=v_margin,
            custom_x=custom_x, custom_y=custom_y
        )
        
        if success:
            print(f"Done: {output_name}")
        else:
            print(f"Failed: {msg}")


def check_safe_area(position, scale, h_margin, v_margin, video_height=1920):
    """Check if watermark position overlaps platform UI zones.

    Returns list of warning strings. Empty list means no overlap detected.
    """
    warnings = []
    # Estimate logo height from scale (assumes ~100px base logo at scale=1.0)
    logo_height = int(100 * scale)

    # Bottom positions: logo sits at (video_height - logo_height - v_margin)
    if position in ("bottom-left", "bottom-right"):
        logo_bottom_y = video_height - v_margin
        logo_top_y = logo_bottom_y - logo_height

        if logo_top_y > video_height - SAFE_AREA_TIKTOK_BOTTOM:
            warnings.append(
                f"TikTok safe-area overlap: watermark bottom {logo_bottom_y}px "
                f"> safe-zone {video_height - SAFE_AREA_TIKTOK_BOTTOM}px"
            )
        if logo_top_y > video_height - SAFE_AREA_IG_BOTTOM:
            warnings.append(
                f"Instagram safe-area overlap: watermark bottom {logo_bottom_y}px "
                f"> safe-zone {video_height - SAFE_AREA_IG_BOTTOM}px"
            )
        if logo_top_y > video_height - SAFE_AREA_SHORTS_BOTTOM:
            warnings.append(
                f"YouTube Shorts safe-area overlap: watermark bottom {logo_bottom_y}px "
                f"> safe-zone {video_height - SAFE_AREA_SHORTS_BOTTOM}px"
            )

    if position in ("top-left", "bottom-left"):
        if h_margin < SAFE_AREA_TIKTOK_LEFT:
            warnings.append(
                f"TikTok left safe-area: margin {h_margin}px < recommended {SAFE_AREA_TIKTOK_LEFT}px"
            )
    if position in ("top-right", "bottom-right"):
        if h_margin < SAFE_AREA_TIKTOK_RIGHT:
            warnings.append(
                f"TikTok right safe-area: margin {h_margin}px < recommended {SAFE_AREA_TIKTOK_RIGHT}px"
            )

    return warnings


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 3:
        print("Usage: python watermark.py <project_folder> <logo_path> [position] [scale] [opacity]")
        sys.exit(1)
    
    project = sys.argv[1]
    logo = sys.argv[2]
    pos = sys.argv[3] if len(sys.argv) > 3 else "bottom-right"
    sc = float(sys.argv[4]) if len(sys.argv) > 4 else 0.15
    op = float(sys.argv[5]) if len(sys.argv) > 5 else 0.8
    
    watermark(project, logo, position=pos, scale=sc, opacity=op)
