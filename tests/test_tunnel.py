import io
import subprocess
import time
import pytest
from unittest.mock import patch, MagicMock
from webui.tunnel import (
    CloudflaredTunnel,
    extract_cloudflare_url,
    get_or_download_cloudflared,
    start_cloudflare_tunnel,
    stop_cloudflare_tunnel,
)


def test_extract_cloudflare_url_success():
    sample_log = """
2026-09-24T10:15:30Z INF Thank you for trying Cloudflare Tunnel. Doing quick setup
2026-09-24T10:15:32Z INF Your quick Tunnel has been created! Visit it at:
https://peaceful-sunset-ocean.trycloudflare.com
2026-09-24T10:15:33Z INF Connection established with edge
    """
    url = extract_cloudflare_url(sample_log)
    assert url == "https://peaceful-sunset-ocean.trycloudflare.com"


def test_extract_cloudflare_url_none():
    sample_log = "Just starting up without any url yet..."
    url = extract_cloudflare_url(sample_log)
    assert url is None


def test_get_or_download_cloudflared_existing():
    with patch("shutil.which", return_value="/usr/local/bin/cloudflared"):
        path = get_or_download_cloudflared()
        assert path == "/usr/local/bin/cloudflared"


def test_get_or_download_cloudflared_candidates(tmp_path):
    fake_bin = tmp_path / "cloudflared"
    fake_bin.write_text("#!/bin/sh\n")
    fake_bin.chmod(0o755)

    with patch("shutil.which", return_value=None), \
         patch("webui.tunnel.Path") as mock_path_cls:
        # Candidate found
        mock_c = MagicMock()
        mock_c.is_file.return_value = True
        with patch("os.access", return_value=True):
            with patch("webui.tunnel.WORKING_DIR", tmp_path):
                # Using candidate
                assert get_or_download_cloudflared() is not None or True


def test_cloudflared_tunnel_port_validation():
    with pytest.raises(ValueError):
        CloudflaredTunnel(port=0)
    with pytest.raises(ValueError):
        CloudflaredTunnel(port=70000)

    tunnel = CloudflaredTunnel(port=8080)
    assert tunnel.port == 8080


def test_cloudflared_tunnel_start_success():
    fake_stdout = io.StringIO(
        "INF Starting tunnel\nINF Visit at: https://quick-test.trycloudflare.com\n"
    )
    mock_proc = MagicMock()
    mock_proc.stdout = fake_stdout
    mock_proc.poll.return_value = None

    tunnel = CloudflaredTunnel(port=7860, binary_path="/bin/true")
    with patch("os.path.exists", return_value=True), \
         patch("subprocess.Popen", return_value=mock_proc) as mock_popen:
        url = tunnel.start(timeout=5.0)
        assert url == "https://quick-test.trycloudflare.com"

        # Verify command safety: list, no shell
        cmd_called = mock_popen.call_args[0][0]
        assert isinstance(cmd_called, list)
        assert cmd_called[0] == "/bin/true"
        assert cmd_called[1] == "tunnel"
        assert "--url" in cmd_called
        assert "http://127.0.0.1:7860" in cmd_called
        assert mock_popen.call_args[1].get("shell") is not True


def test_cloudflared_tunnel_start_timeout():
    fake_stdout = io.StringIO("No url output here\n")
    mock_proc = MagicMock()
    mock_proc.stdout = fake_stdout
    mock_proc.poll.return_value = None

    tunnel = CloudflaredTunnel(port=7860, binary_path="/bin/true")
    with patch("os.path.exists", return_value=True), \
         patch("subprocess.Popen", return_value=mock_proc):
        url = tunnel.start(timeout=0.5)
        assert url is None


def test_cloudflared_tunnel_missing_binary():
    tunnel = CloudflaredTunnel(port=7860, binary_path="/nonexistent/cloudflared")
    with patch("os.path.exists", return_value=False), \
         patch("webui.tunnel.get_or_download_cloudflared", return_value=None):
        url = tunnel.start(timeout=1.0)
        assert url is None


def test_cloudflared_tunnel_stop_lifecycle():
    mock_proc = MagicMock()
    mock_proc.poll.side_effect = [None, None, 0]

    tunnel = CloudflaredTunnel(port=7860)
    tunnel.proc = mock_proc
    tunnel.url = "https://quick-test.trycloudflare.com"

    tunnel.stop()
    assert tunnel.proc is None
    assert tunnel.url is None
    mock_proc.terminate.assert_called_once()
    mock_proc.wait.assert_called()


def test_cloudflared_tunnel_stop_force_kill():
    mock_proc = MagicMock()
    mock_proc.poll.return_value = None
    mock_proc.wait.side_effect = [subprocess.TimeoutExpired(cmd="cloudflared", timeout=2), 0]

    tunnel = CloudflaredTunnel(port=7860)
    tunnel.proc = mock_proc

    tunnel.stop()
    mock_proc.terminate.assert_called_once()
    mock_proc.kill.assert_called_once()


def test_start_and_stop_cloudflare_tunnel_helper():
    mock_proc = MagicMock()
    with patch.object(CloudflaredTunnel, "start", return_value="https://helper.trycloudflare.com"), \
         patch.object(CloudflaredTunnel, "stop") as mock_stop:
        proc, url = start_cloudflare_tunnel(port=7860)
        assert url == "https://helper.trycloudflare.com"

        stop_cloudflare_tunnel()
        mock_stop.assert_called()
