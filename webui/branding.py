import base64
import html
import io
from pathlib import Path

from PIL import Image, ImageOps


CANVAS_WIDTH = 270
CANVAS_HEIGHT = 480

SOURCE_WIDTH = 1080
SOURCE_HEIGHT = 1920

MAX_PREVIEW_IMAGE_SIZE = 768


def _clamp(
    value,
    minimum,
    maximum,
):
    try:
        numeric = float(value)
    except (
        TypeError,
        ValueError,
    ):
        numeric = minimum

    return max(
        minimum,
        min(maximum, numeric),
    )


def _resolve_file_path(value):
    if value is None:
        return None

    if isinstance(value, dict):
        value = (
            value.get("path")
            or value.get("name")
        )

    elif hasattr(value, "name"):
        value = value.name

    value = str(value or "").strip()

    return value or None


def _load_preview_image(
    image_value,
):
    image_path = _resolve_file_path(
        image_value
    )

    if not image_path:
        return (
            None,
            None,
            "Upload an image to preview it.",
        )

    path = (
        Path(image_path)
        .expanduser()
    )

    if not path.is_file():
        return (
            None,
            None,
            (
                "The uploaded image is no "
                "longer available."
            ),
        )

    try:
        with Image.open(path) as opened:
            image = (
                ImageOps.exif_transpose(
                    opened
                )
                .convert("RGBA")
            )

            alpha_bounds = (
                image
                .getchannel("A")
                .getbbox()
            )

            if alpha_bounds is None:
                return (
                    None,
                    None,
                    (
                        "The uploaded image is "
                        "fully transparent."
                    ),
                )

            # Match backend normalization by
            # ignoring transparent padding.
            image = image.crop(
                alpha_bounds
            )

            (
                original_width,
                original_height,
            ) = image.size

            preview_image = image.copy()

            preview_image.thumbnail(
                (
                    MAX_PREVIEW_IMAGE_SIZE,
                    MAX_PREVIEW_IMAGE_SIZE,
                ),
                Image.Resampling.LANCZOS,
            )

            buffer = io.BytesIO()

            preview_image.save(
                buffer,
                format="PNG",
                optimize=True,
            )

            encoded = base64.b64encode(
                buffer.getvalue()
            ).decode("ascii")

            return (
                (
                    "data:image/png;base64,"
                    f"{encoded}"
                ),
                (
                    original_width
                    / original_height
                ),
                None,
            )

    except (
        OSError,
        ValueError,
    ) as error:
        return (
            None,
            None,
            (
                "Cannot preview image: "
                f"{error}"
            ),
        )


def _position_box(
    position,
    box_width,
    box_height,
    h_margin,
    v_margin,
    custom_x,
    custom_y,
):
    scale_x = (
        CANVAS_WIDTH
        / SOURCE_WIDTH
    )
    scale_y = (
        CANVAS_HEIGHT
        / SOURCE_HEIGHT
    )

    h_margin = max(
        0.0,
        float(h_margin or 0),
    ) * scale_x

    v_margin = max(
        0.0,
        float(v_margin or 0),
    ) * scale_y

    custom_x = max(
        0.0,
        float(custom_x or 0),
    ) * scale_x

    custom_y = max(
        0.0,
        float(custom_y or 0),
    ) * scale_y

    positions = {
        "top_left": (
            h_margin,
            v_margin,
        ),
        "top_center": (
            (
                CANVAS_WIDTH
                - box_width
            )
            / 2,
            v_margin,
        ),
        "top_right": (
            CANVAS_WIDTH
            - box_width
            - h_margin,
            v_margin,
        ),
        "center": (
            (
                CANVAS_WIDTH
                - box_width
            )
            / 2,
            (
                CANVAS_HEIGHT
                - box_height
            )
            / 2,
        ),
        "bottom_left": (
            h_margin,
            CANVAS_HEIGHT
            - box_height
            - v_margin,
        ),
        "bottom_center": (
            (
                CANVAS_WIDTH
                - box_width
            )
            / 2,
            CANVAS_HEIGHT
            - box_height
            - v_margin,
        ),
        "bottom_right": (
            CANVAS_WIDTH
            - box_width
            - h_margin,
            CANVAS_HEIGHT
            - box_height
            - v_margin,
        ),
        "custom": (
            custom_x,
            custom_y,
        ),
    }

    (
        left,
        top,
    ) = positions.get(
        position,
        positions["top_right"],
    )

    return (
        _clamp(
            left,
            0,
            max(
                0,
                CANVAS_WIDTH
                - box_width,
            ),
        ),
        _clamp(
            top,
            0,
            max(
                0,
                CANVAS_HEIGHT
                - box_height,
            ),
        ),
    )


def _image_mark_html(
    image_value,
    position,
    scale_percent,
    opacity,
    h_margin,
    v_margin,
    custom_x,
    custom_y,
):
    (
        data_url,
        aspect_ratio,
        error,
    ) = _load_preview_image(
        image_value
    )

    if error:
        return f"""
        <div style="
            position:absolute;
            left:18px;
            right:18px;
            top:210px;
            padding:10px;
            border:1px dashed
                rgba(255,170,90,.9);
            border-radius:7px;
            background:rgba(0,0,0,.55);
            color:#ffd39a;
            font:600 11px/1.35 sans-serif;
            text-align:center;
        ">
            {html.escape(error)}
        </div>
        """

    max_width = (
        CANVAS_WIDTH
        * scale_percent
        / 100.0
    )
    max_height = (
        CANVAS_HEIGHT
        * 0.90
    )

    box_width = max_width
    box_height = (
        box_width
        / aspect_ratio
    )

    if box_height > max_height:
        box_height = max_height
        box_width = (
            box_height
            * aspect_ratio
        )

    box_width = max(
        1,
        box_width,
    )
    box_height = max(
        1,
        box_height,
    )

    (
        left,
        top,
    ) = _position_box(
        position,
        box_width,
        box_height,
        h_margin,
        v_margin,
        custom_x,
        custom_y,
    )

    return f"""
    <img
        src="{data_url}"
        alt="Watermark preview"
        style="
            position:absolute;
            left:{left:.1f}px;
            top:{top:.1f}px;
            width:{box_width:.1f}px;
            height:{box_height:.1f}px;
            object-fit:contain;
            opacity:{opacity:.3f};
            pointer-events:none;
            filter:drop-shadow(
                0 1px 2px
                rgba(0,0,0,.35)
            );
        "
    />
    """


def _text_mark_html(
    text,
    position,
    scale_percent,
    opacity,
    h_margin,
    v_margin,
    custom_x,
    custom_y,
):
    label = html.escape(
        str(
            text
            or "WATERMARK"
        )
    )

    box_width = _clamp(
        max(
            (
                CANVAS_WIDTH
                * scale_percent
                / 100.0
            ),
            min(
                170,
                16 + len(label) * 7,
            ),
        ),
        45,
        170,
    )
    box_height = 28

    (
        left,
        top,
    ) = _position_box(
        position,
        box_width,
        box_height,
        h_margin,
        v_margin,
        custom_x,
        custom_y,
    )

    return f"""
    <div style="
        position:absolute;
        left:{left:.1f}px;
        top:{top:.1f}px;
        width:{box_width:.1f}px;
        min-height:{box_height:.1f}px;
        display:flex;
        align-items:center;
        justify-content:center;
        padding:4px 7px;
        box-sizing:border-box;
        border-radius:5px;
        background:rgba(0,0,0,.45);
        color:white;
        font:700 11px/1.1 sans-serif;
        opacity:{opacity:.3f};
        overflow:hidden;
        text-align:center;
        word-break:break-word;
    ">
        {label}
    </div>
    """


def watermark_safe_area_preview(
    mode,
    image_path,
    text,
    position,
    scale_percent,
    opacity_percent,
    h_margin,
    v_margin,
    custom_x,
    custom_y,
):
    mode = str(
        mode
        or "disabled"
    ).lower()

    position = str(
        position
        or "top_right"
    )

    scale_percent = _clamp(
        scale_percent or 12,
        1,
        100,
    )

    opacity = (
        _clamp(
            opacity_percent or 85,
            0,
            100,
        )
        / 100.0
    )

    if mode == "image":
        mark_html = (
            _image_mark_html(
                image_path,
                position,
                scale_percent,
                opacity,
                h_margin,
                v_margin,
                custom_x,
                custom_y,
            )
        )

    elif mode == "text":
        mark_html = (
            _text_mark_html(
                text,
                position,
                scale_percent,
                opacity,
                h_margin,
                v_margin,
                custom_x,
                custom_y,
            )
        )

    else:
        mark_html = ""

    return f"""
    <div style="
        display:flex;
        gap:18px;
        align-items:flex-start;
        flex-wrap:wrap;
    ">
      <div style="
          position:relative;
          width:{CANVAS_WIDTH}px;
          height:{CANVAS_HEIGHT}px;
          border-radius:14px;
          overflow:hidden;
          border:1px solid #444;
          background:linear-gradient(
              160deg,
              #252525,
              #0b0b0b
          );
          box-shadow:
              0 12px 30px
              rgba(0,0,0,.3);
      ">
        <div style="
            position:absolute;
            inset:42px 34px 92px 28px;
            border:1px dashed
                rgba(80,220,150,.9);
            background:
                rgba(80,220,150,.06);
            border-radius:8px;
        "></div>

        <div style="
            position:absolute;
            right:0;
            top:72px;
            width:44px;
            height:285px;
            background:
                rgba(255,90,90,.13);
        "></div>

        <div style="
            position:absolute;
            left:0;
            right:0;
            bottom:0;
            height:88px;
            background:
                rgba(255,190,70,.12);
        "></div>

        <div style="
            position:absolute;
            left:10px;
            top:10px;
            color:#ddd;
            font:600 11px sans-serif;
        ">
            9:16 safe-area preview
        </div>

        <div style="
            position:absolute;
            left:34px;
            top:48px;
            color:rgba(80,220,150,.95);
            font:600 10px sans-serif;
        ">
            recommended safe area
        </div>

        <div style="
            position:absolute;
            right:4px;
            top:180px;
            writing-mode:vertical-rl;
            color:rgba(255,130,130,.9);
            font:600 9px sans-serif;
        ">
            platform buttons
        </div>

        <div style="
            position:absolute;
            left:74px;
            bottom:34px;
            color:rgba(255,205,110,.9);
            font:600 9px sans-serif;
        ">
            captions / navigation
        </div>

        {mark_html}
      </div>

      <div style="
          max-width:310px;
          color:#aaa;
          font:13px/1.45 sans-serif;
          padding-top:8px;
      ">
        The preview uses the uploaded image,
        its real aspect ratio, selected opacity,
        scale, position, and margins. Transparent
        padding is ignored so the preview matches
        the normalized asset used during final
        rendering.
      </div>
    </div>
    """