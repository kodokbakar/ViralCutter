import base64
import re
from functools import lru_cache
from pathlib import Path

from PIL import ImageFont


ROOT_DIR = (
    Path(__file__)
    .resolve()
    .parent
    .parent
)

FONTS_DIR = (
    ROOT_DIR
    / "assets"
    / "fonts"
)

DEFAULT_FONT_ID = "montserrat_extrabold"
PREVIEW_CSS_FAMILY = "ViralCutterSubtitlePreview"


FONT_CATALOG = {
    "montserrat_extrabold": {
        "label": "Montserrat ExtraBold",
        "filename": "Montserrat-ExtraBold.ttf",
        "fallback_family": "Montserrat",
        "weight": 800,
    },
    "poppins_extrabold": {
        "label": "Poppins ExtraBold",
        "filename": "Poppins-ExtraBold.ttf",
        "fallback_family": "Poppins",
        "weight": 800,
    },
    "roboto_bold": {
        "label": "Roboto Bold",
        "filename": "Roboto-Bold.ttf",
        "fallback_family": "Roboto",
        "weight": 700,
    },
    "barlow_semibold": {
        "label": "Barlow SemiBold",
        "filename": "Barlow-SemiBold.ttf",
        "fallback_family": "Barlow",
        "weight": 600,
    },
    "anton_regular": {
        "label": "Anton Regular",
        "filename": "Anton-Regular.ttf",
        "fallback_family": "Anton",
        "weight": 400,
    },
}


LEGACY_FONT_ALIASES = {
    "montserrat": "montserrat_extrabold",
    "montserrat_regular": "montserrat_extrabold",
    "montserrat_extrabold": "montserrat_extrabold",
    "arial": "montserrat_extrabold",
    "arial_bold": "montserrat_extrabold",

    "poppins": "poppins_extrabold",
    "poppins_extrabold": "poppins_extrabold",

    "roboto": "roboto_bold",
    "roboto_bold": "roboto_bold",

    "barlow": "barlow_semibold",
    "barlow_semibold": "barlow_semibold",
    "consolas": "barlow_semibold",

    "anton": "anton_regular",
    "anton_regular": "anton_regular",
    "impact": "anton_regular",
}


def _normalize_key(value):
    return re.sub(
        r"[^a-z0-9]+",
        "_",
        str(value or "").casefold(),
    ).strip("_")


@lru_cache(maxsize=None)
def _runtime_entry(font_id):
    if font_id not in FONT_CATALOG:
        raise KeyError(
            f"Unknown subtitle font ID: {font_id}"
        )

    catalog_entry = FONT_CATALOG[font_id]

    font_path = (
        FONTS_DIR
        / catalog_entry["filename"]
    ).resolve()

    family = catalog_entry[
        "fallback_family"
    ]
    style = ""

    if font_path.is_file():
        try:
            font = ImageFont.truetype(
                str(font_path),
                24,
            )
            detected_name = font.getname()

            if detected_name:
                family = (
                    detected_name[0]
                    or family
                )

                if len(detected_name) > 1:
                    style = (
                        detected_name[1]
                        or ""
                    )

        except Exception as error:
            print(
                "Warning: failed to inspect "
                f"font metadata for "
                f"{font_path.name}: {error}",
                flush=True,
            )

    return {
        "id": font_id,
        "label": catalog_entry["label"],
        "filename": catalog_entry[
            "filename"
        ],
        "family": family,
        "style": style,
        "weight": catalog_entry["weight"],
        "path": str(font_path),
        "exists": font_path.is_file(),
    }


def available_font_entries():
    return [
        _runtime_entry(font_id)
        for font_id in FONT_CATALOG
        if _runtime_entry(
            font_id
        )["exists"]
    ]


def missing_font_entries():
    return [
        _runtime_entry(font_id)
        for font_id in FONT_CATALOG
        if not _runtime_entry(
            font_id
        )["exists"]
    ]


def validate_font_assets():
    entries = available_font_entries()

    if not entries:
        expected = ", ".join(
            entry["filename"]
            for entry in FONT_CATALOG.values()
        )

        raise FileNotFoundError(
            "No bundled subtitle fonts found in "
            f"{FONTS_DIR}. Expected one or more "
            f"of: {expected}"
        )

    return entries


def get_fonts_dir():
    validate_font_assets()
    return str(FONTS_DIR.resolve())


def get_font_choices():
    return [
        (
            entry["label"],
            entry["id"],
        )
        for entry in validate_font_assets()
    ]


def resolve_font(
    value=None,
    *,
    allow_fallback=True,
):
    requested_value = (
        value
        or DEFAULT_FONT_ID
    )
    requested_key = _normalize_key(
        requested_value
    )

    selected_id = (
        LEGACY_FONT_ALIASES.get(
            requested_key
        )
    )

    if selected_id is None:
        for font_id in FONT_CATALOG:
            entry = _runtime_entry(font_id)

            possible_names = {
                _normalize_key(font_id),
                _normalize_key(
                    entry["label"]
                ),
                _normalize_key(
                    entry["filename"]
                ),
                _normalize_key(
                    Path(
                        entry["filename"]
                    ).stem
                ),
                _normalize_key(
                    entry["family"]
                ),
            }

            if requested_key in possible_names:
                selected_id = font_id
                break

    if selected_id is None:
        selected_id = DEFAULT_FONT_ID

    selected_entry = _runtime_entry(
        selected_id
    )

    if selected_entry["exists"]:
        return {
            **selected_entry,
            "fallback_used": False,
            "requested_value": str(
                requested_value
            ),
        }

    if not allow_fallback:
        raise FileNotFoundError(
            "Selected subtitle font is missing: "
            f"{selected_entry['path']}"
        )

    available = validate_font_assets()

    default_entry = _runtime_entry(
        DEFAULT_FONT_ID
    )

    if default_entry["exists"]:
        fallback_entry = default_entry
    else:
        fallback_entry = available[0]

    print(
        "Subtitle font fallback: "
        f"requested={requested_value!r}, "
        f"using={fallback_entry['label']!r}, "
        f"path={fallback_entry['path']}",
        flush=True,
    )

    return {
        **fallback_entry,
        "fallback_used": True,
        "requested_value": str(
            requested_value
        ),
    }


@lru_cache(maxsize=None)
def _encoded_font_file(font_path):
    path = Path(font_path)

    if not path.is_file():
        raise FileNotFoundError(
            f"Subtitle font not found: {path}"
        )

    return base64.b64encode(
        path.read_bytes()
    ).decode("ascii")


def build_preview_font_css(
    font_value,
    css_family=PREVIEW_CSS_FAMILY,
):
    entry = resolve_font(font_value)

    encoded = _encoded_font_file(
        entry["path"]
    )

    css = f"""
    @font-face {{
        font-family: '{css_family}';
        src: url(
            'data:font/ttf;base64,{encoded}'
        ) format('truetype');
        font-style: normal;
        font-weight: {entry["weight"]};
        font-display: swap;
    }}
    """

    return entry, css