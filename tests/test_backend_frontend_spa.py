import pytest
from fastapi.testclient import TestClient
from webui.backend.main import app
from webui.backend.config import FRONTEND_DIST_DIR

client = TestClient(app)


def test_frontend_dist_exists():
    assert FRONTEND_DIST_DIR.exists()
    assert (FRONTEND_DIST_DIR / "index.html").exists()


def test_root_html_for_browser():
    res = client.get("/", headers={"accept": "text/html,application/xhtml+xml"})
    assert res.status_code == 200
    assert "text/html" in res.headers.get("content-type", "")
    assert "<div id=\"root\"></div>" in res.text


def test_spa_client_routing():
    for route in ["/jobs", "/upload", "/subtitles", "/library", "/system"]:
        res = client.get(route, headers={"accept": "text/html"})
        assert res.status_code == 200
        assert "<div id=\"root\"></div>" in res.text


def test_api_routes_unaffected():
    res = client.get("/api/v1/health")
    assert res.status_code == 200
    assert res.json() == {"status": "ok"}


def test_spa_path_traversal_blocked():
    # Attempting to read host files through SPA fallback must be blocked
    res = client.get("/..%2f..%2fetc/passwd")
    assert res.status_code == 404
    assert "root:x:0:0" not in res.text

    res_dotdot = client.get("/../../etc/passwd")
    assert res_dotdot.status_code in (404, 200)
    assert "root:x:0:0" not in res_dotdot.text

    res_encoded = client.get("/%2e%2e/%2e%2e/etc/passwd")
    assert res_encoded.status_code in (404, 200)
    assert "root:x:0:0" not in res_encoded.text


def test_root_accept_negotiation():
    # Browser requesting HTML receives SPA index.html
    res_html = client.get("/", headers={"accept": "text/html,application/xhtml+xml"})
    assert res_html.status_code == 200
    assert "text/html" in res_html.headers.get("content-type", "")
    assert '<div id="root"></div>' in res_html.text

    # API client / curl requesting JSON receives API info
    res_json = client.get("/", headers={"accept": "application/json"})
    assert res_json.status_code == 200
    assert "application/json" in res_json.headers.get("content-type", "")
    assert res_json.json()["name"] == "ViralCutter API"

    # Default wildcard client receives JSON
    res_wildcard = client.get("/", headers={"accept": "*/*"})
    assert res_wildcard.status_code == 200
    assert res_wildcard.json()["name"] == "ViralCutter API"
