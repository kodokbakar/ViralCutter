import html

CANVAS_WIDTH = 270
CANVAS_HEIGHT = 480

SOURCE_WIDTH = 1080
SOURCE_HEIGHT = 1920


def _clamp(
    value,
    minimum,
    maximum,
):
    return max(
        minimum,
        min(maximum, value),
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
        0,
        float(h_margin or 0),
    ) * scale_x

    v_margin = max(
        0,
        float(v_margin or 0),
    ) * scale_y

    custom_x = max(
        0,
        float(custom_x or 0),
    ) * scale_x

    custom_y = max(
        0,
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
            ) / 2,
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
            ) / 2,
            (
                CANVAS_HEIGHT
                - box_height
            ) / 2,
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
            ) / 2,
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

    left, top = positions.get(
        position,
        positions["top_right"],
    )

    return (
        _clamp(
            left,
            0,
            CANVAS_WIDTH - box_width,
        ),
        _clamp(
            top,
            0,
            CANVAS_HEIGHT - box_height,
        ),
    )


def watermark_safe_area_preview(
    mode,
    text,
    position,
    scale_percent,
    opacity_percent,
    h_margin,
    v_margin,
    custom_x,
    custom_y,
):
    mode = mode or "disabled"

    scale_percent = _clamp(
        float(scale_percent or 12),
        1,
        100,
    )

    opacity = (
        _clamp(
            float(opacity_percent or 85),
            0,
            100,
        )
        / 100
    )

    if mode == "disabled":
        mark_html = ""

    else:
        if mode == "image":
            label = "LOGO"
        else:
            label = html.escape(
                str(
                    text
                    or "WATERMARK"
                )
            )

        box_width = _clamp(
            (
                CANVAS_WIDTH
                * scale_percent
                / 100
            ),
            30,
            170,
        )

        if mode == "text":
            text_width = min(
                170,
                16 + len(label) * 7,
            )

            box_width = _clamp(
                max(
                    box_width,
                    text_width,
                ),
                45,
                170,
            )

        if mode == "text":
            box_height = 28
        else:
            box_height = max(
                24,
                box_width * 0.45,
            )

        left, top = _position_box(
            position,
            box_width,
            box_height,
            h_margin,
            v_margin,
            custom_x,
            custom_y,
        )

        mark_html = f"""
        <div style="
            position:absolute;
            left:{left:.1f}px;
            top:{top:.1f}px;
            width:{box_width:.1f}px;
            height:{box_height:.1f}px;
            display:flex;
            align-items:center;
            justify-content:center;
            padding:3px;
            box-sizing:border-box;
            border:1px solid rgba(255,255,255,.9);
            border-radius:5px;
            background:rgba(0,0,0,.45);
            color:white;
            font:700 11px/1.1 sans-serif;
            opacity:{opacity:.3f};
            overflow:hidden;
            text-align:center;
        ">
            {label}
        </div>
        """

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
        Keep important branding inside the green guide.
        The red and amber areas approximate controls,
        captions, profile information, and navigation
        used by TikTok, Instagram Reels, and YouTube Shorts.
      </div>
    </div>
    """