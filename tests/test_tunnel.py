import pytest
from unittest.mock import patch, MagicMock
from webui.app import extract_cloudflare_url, get_or_download_cloudflared

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
