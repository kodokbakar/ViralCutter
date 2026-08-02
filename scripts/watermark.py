import json
import os
import subprocess
from pathlib import Path

from PIL import Image, ImageOps


IMAGE_EXTENSIONS = {
    ".png",
    ".jpg",
    ".jpeg",
    ".webp",
    ".bmp",
}

POSITION_EXPRESSIONS = {
    "top_left": (
        "max(0,min(W-w,{h_margin}))",
        "max(0,min(H-h,{v_margin}))",
    ),
    "top_center": (
        "(W-w)/2",
        "max(0,min(H-h,{v_margin}))",
    ),
    "top_right": (
        "max(0,W-w-{h_margin})",
        "max(0,min(H-h,{v_margin}))",
    ),
    "center": (
        "(W-w)/2",
        "(H-h)/2",
    ),
    "bottom_left": (
        "max(0,min(W-w,{h_margin}))",
        "max(0,H-h-{v_margin})",
    ),
    "bottom_center": (
        "(W-w)/2",
        "max(0,H-h-{v_margin})",
    ),
    "bottom_right": (
        "max(0,W-w-{h_margin})",
        "max(0,H-h-{v_margin})",
    ),
    "custom": (
        "max(0,min(W-w,{custom_x}))",
        "max(0,min(H-h,{custom_y}))",
    ),
}


def clamp(value, minimum, maximum):
    return max(
        minimum,
        min(maximum, value),
    )


def normalize_hex_color(
    value,
    default,
):
    value = str(value or "").strip()

    if value.startswith("#"):
        value = value[1:]

    if len(value) == 3:
        value = "".join(
            character * 2
            for character in value
        )

    valid = (
        len(value) == 6
        and all(
            character
            in "0123456789abcdefABCDEF"
            for character in value
        )
    )

    if not valid:
        return default

    return f"#{value.upper()}"


def build_config(
    *,
    mode="disabled",
    image_path=None,
    text="",
    text_color="#FFFFFF",
    background_color="#000000",
    background_opacity=0.35,
    font_size=48,
    position="top_right",
    scale_percent=12.0,
    opacity=0.85,
    h_margin=40,
    v_margin=40,
    custom_x=40,
    custom_y=40,
    start_time=0.0,
    end_time=0.0,
    fade_in=0.5,
    fade_out=0.5,
):
    mode = str(
        mode or "disabled"
    ).lower()

    if mode not in {
        "disabled",
        "image",
        "text",
    }:
        raise ValueError(
            f"Unsupported watermark mode: {mode}"
        )

    if position not in POSITION_EXPRESSIONS:
        raise ValueError(
            f"Unsupported watermark position: "
            f"{position}"
        )

    start_time = max(
        0.0,
        float(start_time or 0.0),
    )
    end_time = max(
        0.0,
        float(end_time or 0.0),
    )

    if (
        end_time > 0
        and end_time <= start_time
    ):
        raise ValueError(
            "Watermark end time must be greater "
            "than start time, or 0 for video end."
        )

    text = str(text or "").strip()

    if mode == "text" and not text:
        raise ValueError(
            "Text watermark cannot be empty."
        )

    return {
        "mode": mode,
        "image_path": (
            str(image_path)
            if image_path
            else None
        ),
        "text": text,
        "text_color": normalize_hex_color(
            text_color,
            "#FFFFFF",
        ),
        "background_color": (
            normalize_hex_color(
                background_color,
                "#000000",
            )
        ),
        "background_opacity": clamp(
            float(
                background_opacity
                or 0.0
            ),
            0.0,
            1.0,
        ),
        "font_size": max(
            8,
            int(font_size or 48),
        ),
        "position": position,
        "scale_percent": clamp(
            float(
                scale_percent
                or 12.0
            ),
            1.0,
            100.0,
        ),
        "opacity": clamp(
            float(
                opacity
                or 0.85
            ),
            0.0,
            1.0,
        ),
        "h_margin": max(
            0,
            int(h_margin or 0),
        ),
        "v_margin": max(
            0,
            int(v_margin or 0),
        ),
        "custom_x": max(
            0,
            int(custom_x or 0),
        ),
        "custom_y": max(
            0,
            int(custom_y or 0),
        ),
        "start_time": start_time,
        "end_time": end_time,
        "fade_in": max(
            0.0,
            float(fade_in or 0.0),
        ),
        "fade_out": max(
            0.0,
            float(fade_out or 0.0),
        ),
    }


def _visible_bounds(image):
    alpha = image.getchannel("A")
    bounds = alpha.getbbox()

    if bounds is None:
        raise ValueError(
            "Watermark image is fully transparent. "
            "Upload an image with visible pixels."
        )

    return bounds


def normalize_image_asset(
    source_path,
    destination_path,
):
    source = (
        Path(source_path)
        .expanduser()
        .resolve()
    )
    destination = (
        Path(destination_path)
        .expanduser()
        .resolve()
    )

    if not source.is_file():
        raise FileNotFoundError(
            f"Watermark image not found: {source}"
        )

    if (
        source.suffix.lower()
        not in IMAGE_EXTENSIONS
    ):
        raise ValueError(
            "Unsupported watermark image format. "
            "Use PNG, JPG, JPEG, WEBP, or BMP."
        )

    destination.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    try:
        with Image.open(source) as opened:
            oriented = (
                ImageOps.exif_transpose(
                    opened
                )
            )
            rgba = oriented.convert("RGBA")
            original_size = rgba.size

            bounds = _visible_bounds(rgba)
            cropped = rgba.crop(bounds)

            # Keep a very small transparent margin for
            # antialiased pixels while removing large
            # transparent borders from uploaded logos.
            padding = max(
                2,
                round(
                    max(cropped.size)
                    * 0.01
                ),
            )

            normalized = ImageOps.expand(
                cropped,
                border=padding,
                fill=(0, 0, 0, 0),
            )

            normalized.save(
                destination,
                format="PNG",
                optimize=True,
            )

    except (
        OSError,
        ValueError,
    ) as error:
        raise ValueError(
            "Invalid watermark image "
            f"'{source.name}': {error}"
        ) from error

    info = describe_asset(destination)

    info.update(
        {
            "source_path": str(source),
            "source_width": (
                original_size[0]
            ),
            "source_height": (
                original_size[1]
            ),
            "visible_bounds": list(
                bounds
            ),
        }
    )

    return str(destination), info


def persist_image_asset(
    image_path,
    project_folder,
):
    if not image_path:
        raise ValueError(
            "Image watermark mode requires "
            "an image file."
        )

    assets_folder = (
        Path(project_folder).resolve()
        / "assets"
    )
    destination = (
        assets_folder
        / "watermark.png"
    )

    (
        normalized_path,
        info,
    ) = normalize_image_asset(
        image_path,
        destination,
    )

    print(
        "Watermark image normalized: "
        f"source="
        f"{info['source_width']}x"
        f"{info['source_height']} "
        f"visible_bounds="
        f"{tuple(info['visible_bounds'])} "
        f"output="
        f"{info['width']}x"
        f"{info['height']} "
        f"path={normalized_path}",
        flush=True,
    )

    return normalized_path


def describe_asset(image_path):
    path = (
        Path(image_path)
        .expanduser()
        .resolve()
    )

    if not path.is_file():
        raise FileNotFoundError(
            f"Watermark asset not found: {path}"
        )

    with Image.open(path) as image:
        rgba = image.convert("RGBA")
        alpha = rgba.getchannel("A")
        alpha_bounds = alpha.getbbox()

        if alpha_bounds is None:
            raise ValueError(
                "Watermark asset is fully "
                f"transparent: {path}"
            )

        alpha_extrema = (
            alpha.getextrema()
        )

        return {
            "path": str(path),
            "width": int(rgba.width),
            "height": int(rgba.height),
            "alpha_min": int(
                alpha_extrema[0]
            ),
            "alpha_max": int(
                alpha_extrema[1]
            ),
            "visible_bounds": list(
                alpha_bounds
            ),
        }


def get_video_info(video_path):
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            (
                "stream=width,height:"
                "format=duration"
            ),
            "-of",
            "json",
            str(video_path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    payload = json.loads(result.stdout)
    streams = (
        payload.get("streams")
        or []
    )

    if not streams:
        raise ValueError(
            "No video stream found: "
            f"{video_path}"
        )

    width = int(
        streams[0]["width"]
    )
    height = int(
        streams[0]["height"]
    )
    duration = float(
        payload
        .get("format", {})
        .get("duration")
        or 0.0
    )

    if (
        width <= 0
        or height <= 0
        or duration <= 0
    ):
        raise ValueError(
            "Invalid video metadata: "
            f"{video_path}"
        )

    return width, height, duration


def resolve_font_file():
    candidates = [
        (
            "/usr/share/fonts/truetype/"
            "dejavu/DejaVuSans-Bold.ttf"
        ),
        (
            "/usr/share/fonts/truetype/"
            "liberation2/"
            "LiberationSans-Bold.ttf"
        ),
        "C:/Windows/Fonts/arialbd.ttf",
        "C:/Windows/Fonts/arial.ttf",
    ]

    for candidate in candidates:
        if os.path.isfile(candidate):
            return candidate

    try:
        result = subprocess.run(
            [
                "fc-match",
                "-f",
                "%{file}",
                "sans-serif:style=Bold",
            ],
            check=True,
            capture_output=True,
            text=True,
        )

        matched = (
            result.stdout.strip()
        )

        if (
            matched
            and os.path.isfile(matched)
        ):
            return matched

    except (
        FileNotFoundError,
        subprocess.CalledProcessError,
    ):
        pass

    return None


def hex_to_rgba(
    color,
    alpha=1.0,
):
    color = normalize_hex_color(
        color,
        "#FFFFFF",
    )[1:]

    return (
        int(color[0:2], 16),
        int(color[2:4], 16),
        int(color[4:6], 16),
        round(
            clamp(
                alpha,
                0.0,
                1.0,
            )
            * 255
        ),
    )


def create_text_asset(
    config,
    output_path,
):
    from PIL import (
        ImageDraw,
        ImageFont,
    )

    text = config["text"]
    font_file = resolve_font_file()

    if font_file:
        font = ImageFont.truetype(
            font_file,
            config["font_size"],
        )
    else:
        font = (
            ImageFont.load_default()
        )

    padding_x = max(
        12,
        config["font_size"] // 3,
    )
    padding_y = max(
        8,
        config["font_size"] // 5,
    )
    stroke_width = max(
        1,
        config["font_size"] // 24,
    )

    scratch = Image.new(
        "RGBA",
        (1, 1),
        (0, 0, 0, 0),
    )
    draw = ImageDraw.Draw(scratch)

    bounds = draw.textbbox(
        (0, 0),
        text,
        font=font,
        stroke_width=stroke_width,
    )

    width = max(
        1,
        (
            bounds[2]
            - bounds[0]
            + padding_x * 2
        ),
    )
    height = max(
        1,
        (
            bounds[3]
            - bounds[1]
            + padding_y * 2
        ),
    )

    image = Image.new(
        "RGBA",
        (width, height),
        hex_to_rgba(
            config[
                "background_color"
            ],
            config[
                "background_opacity"
            ],
        ),
    )

    draw = ImageDraw.Draw(image)

    draw.text(
        (
            padding_x - bounds[0],
            padding_y - bounds[1],
        ),
        text,
        font=font,
        fill=hex_to_rgba(
            config["text_color"],
            1.0,
        ),
        stroke_width=stroke_width,
        stroke_fill=(
            0,
            0,
            0,
            210,
        ),
    )

    image.save(
        output_path,
        format="PNG",
        optimize=True,
    )

    return str(output_path)


def prepare_asset(
    config,
    project_folder,
):
    mode = config["mode"]

    if mode == "disabled":
        return None

    if mode == "image":
        image_path = (
            Path(
                config.get("image_path")
                or ""
            )
            .expanduser()
            .resolve()
        )

        if not image_path.is_file():
            raise FileNotFoundError(
                "Watermark image not found: "
                f"{image_path}"
            )

        describe_asset(image_path)
        return str(image_path)

    runtime_folder = (
        Path(project_folder).resolve()
        / ".runtime"
    )
    runtime_folder.mkdir(
        parents=True,
        exist_ok=True,
    )

    output_path = (
        runtime_folder
        / "text_watermark.png"
    )

    return create_text_asset(
        config,
        output_path,
    )


def resolve_position(config):
    (
        x_expression,
        y_expression,
    ) = POSITION_EXPRESSIONS[
        config["position"]
    ]

    return (
        x_expression.format(**config),
        y_expression.format(**config),
    )


def build_filter(
    config,
    video_path,
):
    (
        width,
        height,
        duration,
    ) = get_video_info(video_path)

    start = min(
        config["start_time"],
        duration,
    )

    if config["end_time"] <= 0:
        end = duration
    else:
        end = min(
            config["end_time"],
            duration,
        )

    if end <= start:
        raise ValueError(
            "Watermark time range is empty "
            f"for {os.path.basename(video_path)}: "
            f"start={start:.3f}, "
            f"end={end:.3f}."
        )

    visible_duration = end - start

    fade_in = min(
        config["fade_in"],
        visible_duration / 2,
    )
    fade_out = min(
        config["fade_out"],
        visible_duration / 2,
    )

    target_width = max(
        1,
        round(
            width
            * config["scale_percent"]
            / 100.0
        ),
    )

    # Prevent unusually tall images from
    # overflowing the video frame.
    target_height = max(
        1,
        round(height * 0.90),
    )

    scale_filter = (
        f"scale=w={target_width}:"
        f"h={target_height}:"
        "force_original_aspect_ratio=decrease"
    )

    # Turn the normalized PNG into a finite
    # 30 FPS stream matching the source video.
    # This makes fade timing deterministic.
    watermark_filters = [
        "loop=loop=-1:size=1:start=0",
        (
            "trim=duration="
            f"{duration:.6f}"
        ),
        "setpts=N/(30*TB)",
        scale_filter,
        "format=rgba",
        (
            "colorchannelmixer="
            f"aa={config['opacity']:.6f}"
        ),
    ]

    if fade_in > 0:
        watermark_filters.append(
            "fade=t=in:"
            f"st={start:.6f}:"
            f"d={fade_in:.6f}:"
            "alpha=1"
        )

    if fade_out > 0:
        fade_out_start = max(
            start,
            end - fade_out,
        )

        watermark_filters.append(
            "fade=t=out:"
            f"st={fade_out_start:.6f}:"
            f"d={fade_out:.6f}:"
            "alpha=1"
        )

    (
        x_expression,
        y_expression,
    ) = resolve_position(config)

    enable_expression = (
        "between("
        f"t,{start:.6f},{end:.6f}"
        ")"
    )

    filter_complex = (
        f"[1:v]"
        f"{','.join(watermark_filters)}"
        "[watermark];"
        "[0:v][watermark]"
        "overlay="
        f"x='{x_expression}':"
        f"y='{y_expression}':"
        f"enable='{enable_expression}':"
        "eof_action=pass:"
        "shortest=1"
        "[watermarked]"
    )

    return filter_complex, {
        "video_width": width,
        "video_height": height,
        "video_duration": duration,
        "target_width": target_width,
        "target_height": target_height,
        "start": start,
        "end": end,
        "fade_in": fade_in,
        "fade_out": fade_out,
        "position": (
            config["position"]
        ),
        "opacity": config["opacity"],
    }