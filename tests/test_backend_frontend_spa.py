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
