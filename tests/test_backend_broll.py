import pytest
from fastapi.testclient import TestClient
from webui.backend.main import app
from webui.backend.schemas.jobs import JobRunRequest

client = TestClient(app)


def test_get_broll_templates():
    response = client.get("/api/v1/broll/templates")
    assert response.status_code == 200
    templates = response.json()
    assert len(templates) >= 3
    ids = [t["id"] for t in templates]
    assert "stat_counter" in ids


def test_preview_broll_template():
    payload = {
        "template_id": "stat_counter",
        "duration": 1.0,
        "data": {
            "target_number": "100",
            "suffix": "%",
            "label": "Test Label",
        },
    }
    response = client.post("/api/v1/broll/preview", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "preview_url" in data
    assert data["preview_url"].endswith(".webm")
    stream_resp = client.get(data["preview_url"])
    assert stream_resp.status_code == 200


def test_preview_unknown_template():
    payload = {
        "template_id": "non_existent_template",
        "duration": 1.0,
        "data": {},
    }
    response = client.post("/api/v1/broll/preview", json=payload)
    assert response.status_code == 404


def test_job_schema_enable_html_broll():
    req_default = JobRunRequest(url="https://youtube.com/watch?v=123")
    assert req_default.enable_html_broll is False
    args_default = req_default.to_cli_args("python3", "main_improved.py")
    assert "--enable-html-broll" not in args_default

    req_enabled = JobRunRequest(url="https://youtube.com/watch?v=123", enable_html_broll=True)
    assert req_enabled.enable_html_broll is True
    args_enabled = req_enabled.to_cli_args("python3", "main_improved.py")
    assert "--enable-html-broll" in args_enabled
