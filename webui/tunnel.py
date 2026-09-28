"""Cloudflared Tunnel Management Module.

Provides safe subprocess management, non-blocking URL extraction, binary provisioning,
and clean lifecycle termination (preventing zombie processes) for Cloudflare tunnels.
"""

import atexit
import os
import platform
import queue
import re
import shutil
import signal
import subprocess
import sys
import threading
import time
import urllib.request
from pathlib import Path
from typing import Optional, Tuple

CLOUDFLARE_URL_PATTERN = re.compile(r"https://[a-zA-Z0-9-]+\.trycloudflare\.com")
WORKING_DIR = Path(__file__).resolve().parent.parent


def extract_cloudflare_url(log_text: str) -> Optional[str]:
    """Extract a trycloudflare.com public URL from text output."""
    if not log_text:
        return None
    match = CLOUDFLARE_URL_PATTERN.search(str(log_text))
    return match.group(0) if match else None


def get_or_download_cloudflared() -> Optional[str]:
    """Locate existing cloudflared binary or download official release on Linux.

    Returns the path to an executable cloudflared binary, or None if unavailable.
    """
    # 1. Check system PATH
    which_path = shutil.which("cloudflared")
    if which_path:
        return which_path

    # 2. Check known safe paths
    candidates = [
        Path("/content/cloudflared"),
        WORKING_DIR / "cloudflared",
        Path("/tmp/cloudflared"),
    ]
    for c in candidates:
        if c.is_file() and os.access(c, os.X_OK):
            return str(c)

    # 3. Auto-download official release on Linux environments (e.g. Colab / containers)
    if sys.platform.startswith("linux"):
        machine = platform.machine().lower()
        arch = "arm64" if machine in ["aarch64", "arm64"] else "amd64"
        download_url = (
            f"https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-{arch}"
        )
        target_dir = Path("/content") if Path("/content").exists() else Path("/tmp")
        target_path = target_dir / "cloudflared"
        temp_target = target_dir / f"cloudflared.tmp.{os.getpid()}"

        try:
            print(f"[INFO] Downloading official cloudflared binary ({arch}) to {target_path}...")
            req = urllib.request.Request(
                download_url,
                headers={"User-Agent": "ViralCutter-AutoTunnel/1.0"},
            )
            with urllib.request.urlopen(req, timeout=30) as response, open(temp_target, "wb") as out_file:
                shutil.copyfileobj(response, out_file)

            os.chmod(temp_target, 0o755)
            os.replace(temp_target, target_path)
            print(f"[INFO] cloudflared successfully installed at {target_path}")
            return str(target_path)
        except Exception as e:
            if temp_target.exists():
                try:
                    temp_target.unlink()
                except OSError:
                    pass
            print(f"[WARN] Failed to download cloudflared: {e}")
            return None

    return None


class CloudflaredTunnel:
    """Manages the lifecycle of a cloudflared tunnel subprocess safely."""

    def __init__(
        self,
        port: int = 7860,
        host: str = "127.0.0.1",
        binary_path: Optional[str] = None,
    ):
        if not (1 <= int(port) <= 65535):
            raise ValueError(f"Invalid port: {port}")
        self.port = int(port)
        self.host = host
        self.binary_path = binary_path
        self.proc: Optional[subprocess.Popen] = None
        self.url: Optional[str] = None
        self._queue: queue.Queue = queue.Queue()
        self._reader_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._cleanup_registered = False

    def start(self, timeout: float = 25.0) -> Optional[str]:
        """Spawn the cloudflared process and extract the public tunnel URL.

        Non-blocking read with timeout to prevent hanging.
        """
        binary = self.binary_path or get_or_download_cloudflared()
        if not binary or not os.path.exists(binary):
            print("[WARN] cloudflared binary not found or could not be downloaded.")
            return None

        # Build command safely as a list without shell expansion
        cmd = [
            str(binary),
            "tunnel",
            "--url",
            f"http://{self.host}:{self.port}",
            "--metrics",
            "localhost:0",
        ]

        try:
            self.proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )
        except Exception as e:
            print(f"[WARN] Error launching cloudflared process: {e}")
            return None

        # Register cleanup with atexit
        if not self._cleanup_registered:
            atexit.register(self.stop)
            self._cleanup_registered = True

        # Non-blocking output reader
        def _enqueue_output(pipe, q, stop_evt):
            try:
                for line in iter(pipe.readline, ""):
                    if stop_evt.is_set():
                        break
                    if not line:
                        break
                    q.put(line)
            except Exception:
                pass
            finally:
                try:
                    pipe.close()
                except Exception:
                    pass

        self._stop_event.clear()
        self._reader_thread = threading.Thread(
            target=_enqueue_output,
            args=(self.proc.stdout, self._queue, self._stop_event),
            daemon=True,
        )
        self._reader_thread.start()

        # Poll output queue up to timeout
        start_time = time.time()
        while time.time() - start_time < timeout:
            if self.proc.poll() is not None:
                # Process terminated prematurely
                break
            try:
                line = self._queue.get(timeout=0.25)
                extracted = extract_cloudflare_url(line)
                if extracted:
                    self.url = extracted
                    return self.url
            except queue.Empty:
                continue

        if not self.url and self.proc and self.proc.poll() is None:
            print("[WARN] Cloudflare tunnel timed out waiting for public URL.")
            self.stop()

        return self.url

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()

    def stop(self):
        """Terminate process and child processes gracefully, reaping zombies."""
        self._stop_event.set()
        if self.proc is None:
            return

        proc = self.proc
        self.proc = None
        self.url = None

        if proc.poll() is None:
            # Terminate any child processes first using psutil if available
            try:
                import psutil
                parent = psutil.Process(proc.pid)
                children = parent.children(recursive=True)
                for child in children:
                    try:
                        child.terminate()
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        pass
            except Exception:
                pass

            # Graceful SIGTERM
            try:
                proc.terminate()
                proc.wait(timeout=2)
            except (subprocess.TimeoutExpired, Exception):
                # Force kill if still unresponsive
                try:
                    proc.kill()
                    proc.wait(timeout=2)
                except Exception:
                    pass

        # Ensure zombie process is reaped
        try:
            proc.poll()
        except Exception:
            pass


_active_tunnel: Optional[CloudflaredTunnel] = None


def start_cloudflare_tunnel(
    port: int = 7860,
    timeout: float = 25.0,
    host: str = "127.0.0.1",
) -> Tuple[Optional[subprocess.Popen], Optional[str]]:
    """Convenience helper matching legacy signature: returns (proc, url)."""
    global _active_tunnel
    if _active_tunnel is not None:
        _active_tunnel.stop()

    _active_tunnel = CloudflaredTunnel(port=port, host=host)
    url = _active_tunnel.start(timeout=timeout)
    return _active_tunnel.proc, url


def stop_cloudflare_tunnel():
    """Stop any currently active cloudflared tunnel."""
    global _active_tunnel
    if _active_tunnel is not None:
        _active_tunnel.stop()
        _active_tunnel = None


# Alias for naming consistency
CloudflareTunnel = CloudflaredTunnel

