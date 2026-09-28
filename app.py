#!/usr/bin/env python3
"""ViralCutter Application Entrypoint.

CLI runner for ViralCutter FastAPI + React SPA, Cloudflare auto-tunneling,
Google Colab mode, and legacy Gradio fallback toggle.
"""

import sys
from pathlib import Path

# Ensure project root and webui dir are in sys.path
_root = Path(__file__).resolve().parent
_webui = _root / "webui"
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))
if str(_webui) not in sys.path:
    sys.path.insert(0, str(_webui))

from webui.runner import main

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
