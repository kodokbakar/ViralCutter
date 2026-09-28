"""ViralCutter CLI Runner.

Provides CLI entrypoint for launching ViralCutter FastAPI + React SPA or legacy Gradio UI.
Handles Colab environment configuration, cloudflared auto-tunneling, and graceful process shutdown.
"""

import argparse
import atexit
import os
import signal
import sys
from pathlib import Path
from typing import List, Optional

# Ensure project root and webui dir are in sys.path when invoked directly as a script
project_root = Path(__file__).resolve().parent.parent
webui_dir = Path(__file__).resolve().parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))
if str(webui_dir) not in sys.path:
    sys.path.insert(0, str(webui_dir))

from webui.tunnel import CloudflaredTunnel


def build_cli_parser() -> argparse.ArgumentParser:
    """Build and return command-line argument parser for ViralCutter runner."""
    parser = argparse.ArgumentParser(description="ViralCutter WebUI Runner")
    parser.add_argument(
        "--colab",
        action="store_true",
        help="Run in Google Colab / headless mode (host 0.0.0.0, port 7860, default cloudflare tunnel)",
    )
    parser.add_argument(
        "--tunnel",
        choices=["cloudflare", "gradio", "both", "none"],
        default=None,
        help="Tunnel type for Colab/remote access (default: cloudflare in colab, none otherwise)",
    )
    parser.add_argument(
        "--legacy-gradio",
        action="store_true",
        help="Launch legacy Gradio interface as fallback if specified",
    )
    parser.add_argument(
        "--host",
        type=str,
        default=None,
        help="Host address to bind to (default: 0.0.0.0 in colab, otherwise VIRALCUTTER_HOST / 0.0.0.0)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=None,
        help="Port to bind to (default: 7860)",
    )
    parser.add_argument(
        "--reload",
        action="store_true",
        help="Enable uvicorn auto-reload (development only)",
    )
    return parser


# Alias for compatibility
create_parser = build_cli_parser


def ensure_frontend_built():
    """Ensure static SPA frontend dist exists; attempt auto-build with npm if available."""
    import shutil
    import subprocess
    from webui.backend.config import FRONTEND_DIST_DIR

    dist_index = FRONTEND_DIST_DIR / "index.html"
    if not dist_index.exists():
        npm_bin = shutil.which("npm")
        frontend_dir = Path(__file__).resolve().parent / "frontend"
        if npm_bin and (frontend_dir / "package.json").exists():
            print("[INFO] Frontend dist not found. Building SPA assets via npm...")
            try:
                subprocess.run([npm_bin, "run", "build"], cwd=str(frontend_dir), check=True)
                print("[INFO] Frontend SPA assets built successfully.")
            except Exception as e:
                print(f"[WARN] Failed to auto-build frontend SPA: {e}")
        else:
            print("[WARN] Frontend dist not built and npm not found. Run 'npm run build' inside webui/frontend.")


def launch_modern_webui(args, host: str = "0.0.0.0", port: int = 7860, tunnel_type: str = "none"):
    """Launch the modern FastAPI + React SPA WebUI with optional Cloudflare auto-tunneling."""
    import uvicorn
    from webui.backend.config import ensure_directories

    if tunnel_type == "gradio":
        print("[WARN] Gradio tunneling (--tunnel gradio) only applies to legacy Gradio interface (--legacy-gradio).")
        tunnel_type = "none"
    elif tunnel_type == "both":
        print("[WARN] Gradio tunneling only applies to legacy Gradio interface (--legacy-gradio); using Cloudflare tunnel only.")
        tunnel_type = "cloudflare"

    ensure_directories()
    ensure_frontend_built()

    tunnel: Optional[CloudflaredTunnel] = None
    use_cloudflare = tunnel_type in ["cloudflare", "both"]
    if use_cloudflare:
        print("Starting high-speed Cloudflare Tunnel for FastAPI + React SPA...")
        tunnel = CloudflaredTunnel(port=port, host="127.0.0.1")
        public_url = tunnel.start(timeout=25.0)
        if public_url:
            print("\n" + "=" * 76)
            print("🚀 HIGH-SPEED CLOUDFLARE TUNNEL ACTIVE (FastAPI + React SPA):")
            print(f"🔗 Public URL: {public_url}")
            print("=" * 76 + "\n")
        else:
            print("[WARN] Cloudflare tunnel could not be established; accessing locally/on network.")

    def cleanup():
        nonlocal tunnel
        if tunnel:
            tunnel.stop()
            tunnel = None

    atexit.register(cleanup)

    def _sig_handler(signum, frame):
        cleanup()
        sys.exit(0)

    try:
        signal.signal(signal.SIGINT, _sig_handler)
        signal.signal(signal.SIGTERM, _sig_handler)
    except (ValueError, AttributeError):
        pass

    print(f"Starting ViralCutter FastAPI + React SPA on http://{host}:{port}...")
    try:
        uvicorn.run(
            "webui.backend.main:app",
            host=host,
            port=port,
            reload=getattr(args, "reload", False),
        )
    finally:
        cleanup()


def main(argv: Optional[List[str]] = None) -> int:
    """Main CLI runner entrypoint."""
    parser = build_cli_parser()
    args = parser.parse_args(argv)

    if args.colab:
        host = args.host or "0.0.0.0"
        port = args.port or 7860
        tunnel_type = args.tunnel if args.tunnel is not None else "cloudflare"
        # Auto-detect Colab drive mount if VIRALCUTTER_OUTPUT_DIR not set
        colab_drive_virals = Path("/content/drive/MyDrive/ViralCutter/VIRALS")
        if colab_drive_virals.exists() and "VIRALCUTTER_OUTPUT_DIR" not in os.environ:
            os.environ["VIRALCUTTER_OUTPUT_DIR"] = str(colab_drive_virals)
    else:
        host = args.host or os.environ.get("VIRALCUTTER_HOST", "0.0.0.0")
        port = args.port or int(os.environ.get("VIRALCUTTER_PORT", 7860))
        tunnel_type = args.tunnel if args.tunnel is not None else "none"

    if not args.legacy_gradio:
        if tunnel_type == "gradio":
            print("[WARN] Gradio tunneling (--tunnel gradio) only applies to legacy Gradio interface (--legacy-gradio).")
            tunnel_type = "none"
        elif tunnel_type == "both":
            print("[WARN] Gradio tunneling only applies to legacy Gradio interface (--legacy-gradio); using Cloudflare tunnel only.")
            tunnel_type = "cloudflare"

    if args.legacy_gradio:
        if str(webui_dir) not in sys.path:
            sys.path.insert(0, str(webui_dir))
        from webui.app import launch_legacy_gradio
        launch_legacy_gradio(args, host=host, port=port, tunnel_type=tunnel_type)
    else:
        launch_modern_webui(args, host=host, port=port, tunnel_type=tunnel_type)

    return 0


if __name__ == "__main__":
    sys.exit(main())
