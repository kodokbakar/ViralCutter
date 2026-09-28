import os
import sys
from pathlib import Path

# Base directories
BASE_DIR = Path(__file__).resolve().parent.parent.parent
WEBUI_DIR = BASE_DIR / "webui"
VIRALS_DIR = Path(os.environ.get("VIRALCUTTER_OUTPUT_DIR", BASE_DIR / "VIRALS"))
MODELS_DIR = BASE_DIR / "models"
PREVIEWS_DIR = WEBUI_DIR / "PREVIEW"
UPLOADS_DIR = VIRALS_DIR / "uploads"
MAIN_SCRIPT_PATH = BASE_DIR / "main_improved.py"
FRONTEND_DIST_DIR = WEBUI_DIR / "frontend" / "dist"

# Server configuration
HOST = os.environ.get("VIRALCUTTER_HOST", "0.0.0.0")
PORT = int(os.environ.get("VIRALCUTTER_PORT", 7860))
PYTHON_EXECUTABLE = sys.executable

# Supported file extensions
ALLOWED_VIDEO_EXTENSIONS = {".mp4", ".mov", ".mkv", ".avi", ".webm", ".m4v"}
ALLOWED_SUBTITLE_EXTENSIONS = {".srt", ".vtt", ".ass", ".json"}

def ensure_directories():
    """Ensure core output and cache directories exist."""
    VIRALS_DIR.mkdir(parents=True, exist_ok=True)
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    PREVIEWS_DIR.mkdir(parents=True, exist_ok=True)
    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
