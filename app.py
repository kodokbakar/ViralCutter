#!/usr/bin/env python3
"""ViralCutter Application Entrypoint.

CLI runner for ViralCutter FastAPI + React SPA, Cloudflare auto-tunneling,
Google Colab mode, and legacy Gradio fallback toggle.
"""

import sys
from webui.runner import main

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
