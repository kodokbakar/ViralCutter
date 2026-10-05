import pytest
from unittest.mock import patch, MagicMock
from webui.app import extract_cloudflare_url, get_or_download_cloudflared, start_ngrok_tunnel

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

def test_start_ngrok_tunnel_no_token():
    with patch.dict("os.environ", {}, clear=True):
        tunnel, url = start_ngrok_tunnel(port=7860, token=None)
        assert tunnel is None
        assert url is None

def test_start_ngrok_tunnel_success():
    mock_tunnel = MagicMock()
    mock_tunnel.public_url = "https://abc.ngrok-free.app"
    mock_ngrok = MagicMock()
    mock_ngrok.connect.return_value = mock_tunnel
    mock_conf = MagicMock()
    mock_pyngrok = MagicMock()
    mock_pyngrok.ngrok = mock_ngrok
    mock_pyngrok.conf = mock_conf

    with patch.dict("sys.modules", {"pyngrok": mock_pyngrok, "pyngrok.ngrok": mock_ngrok, "pyngrok.conf": mock_conf}):
        tunnel, url = start_ngrok_tunnel(port=7860, token="test-token-123", region="ap")
        assert url == "https://abc.ngrok-free.app"
        mock_ngrok.set_auth_token.assert_called_with("test-token-123")
        mock_ngrok.connect.assert_called_with(7860)
