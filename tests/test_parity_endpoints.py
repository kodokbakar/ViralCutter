import json
import pytest
from fastapi.testclient import TestClient

from main_improved import get_subtitle_config
from scripts.adjust_subtitles import generate_ass_from_file
from webui.backend.main import app

client = TestClient(app)


def test_default_subtitle_config_parity():
    cfg = get_subtitle_config()
    assert cfg["border_style"] == 1
    # Check outline color has opaque alpha &H00...&
    assert cfg["outline_color"].startswith("&H00")


def test_adjust_subtitles_words_empty_fallback(tmp_path):
    input_json = tmp_path / "empty_words.json"
    output_ass = tmp_path / "output.ass"

    data = {
        "segments": [
            {
                "start": 0.5,
                "end": 3.5,
                "text": "Fallback segment text without words array",
                "words": []
            }
        ]
    }
    input_json.write_text(json.dumps(data), encoding="utf-8")

    generate_ass_from_file(
        input_path=str(input_json),
        output_path=str(output_ass),
        project_folder=str(tmp_path),
        base_color="&H00FFFFFF&",
        base_size=24,
        highlight_size=28,
        highlight_color="&H0000FF00&",
        words_per_block=3,
        gap_limit=0.2,
        mode="highlight",
        vertical_position=150,
        alignment=2,
        font="Montserrat-ExtraBold",
        outline_color="&H00000000&",
        shadow_color="&H00000000&",
        bold=True,
        italic=False,
        underline=False,
        strikeout=False,
        border_style=1,
        outline_thickness=2,
        shadow_size=1,
        uppercase=False,
        remove_punctuation=True,
    )

    assert output_ass.exists()
    content = output_ass.read_text(encoding="utf-8")
    lines = [l for l in content.splitlines() if l.startswith("Dialogue:")]
    assert len(lines) > 0
    # Dialogue text should contain words from segment['text']
    assert any("Fallback" in l for l in lines)


def test_system_test_ai_endpoint():
    # Test local backend which returns immediately
    resp = client.post(
        "/api/v1/system/test-ai",
        json={"backend": "local"}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert "ready" in data["message"].lower() or "connected" in data["message"].lower()
    assert isinstance(data["latency_ms"], int)

    # Test custom backend with invalid URL
    resp_bad = client.post(
        "/api/v1/system/test-ai",
        json={
            "backend": "custom",
            "base_url": "http://127.0.0.1:59999",
            "api_key": "dummy",
            "model_name": "test"
        }
    )
    assert resp_bad.status_code == 200
    data_bad = resp_bad.json()
    assert data_bad["success"] is False


def test_preview_subtitle_video_endpoint():
    resp = client.post(
        "/api/v1/preview/subtitle-video",
        json={
            "sample_text": "Parity test subtitle text",
            "timestamp": 0.0,
            "duration": 2.0,
            "subtitle_config": {
                "font": "Montserrat-ExtraBold",
                "fontSize": 36,
                "color": "#FFFFFF",
                "outlineColor": "#000000",
                "border_style": 1
            }
        }
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "preview_url" in data
    assert "file_path" in data
    assert data["file_path"].endswith(".mp4")

    # Stream the generated video
    stream_url = data["preview_url"]
    stream_resp = client.get(stream_url)
    assert stream_resp.status_code in [200, 206]
    assert stream_resp.headers["content-type"] == "video/mp4"
