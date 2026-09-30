import io
import json
import os
import shutil
import tempfile
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from webui.backend.config import PREVIEWS_DIR, UPLOADS_DIR, VIRALS_DIR, ensure_directories
from webui.backend.core.security import (
    sanitize_filename,
    sanitize_project_name,
    validate_safe_path,
)
from webui.backend.main import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_dirs(tmp_path, monkeypatch):
    """Ensure clean test environment directories."""
    ensure_directories()
    yield


# ==============================================================================
# Security & Path Traversal Unit Tests
# ==============================================================================


def test_sanitize_filename_traversal():
    assert sanitize_filename("../../etc/passwd") == "passwd"
    assert sanitize_filename("..\\..\\windows\\system32.dll") == "system32.dll"
    assert sanitize_filename("normal_video.mp4") == "normal_video.mp4"

    with pytest.raises(Exception):
        sanitize_filename("..\0test.mp4")

    with pytest.raises(Exception):
        sanitize_filename("")


def test_sanitize_project_name():
    assert sanitize_project_name("My Project 2026") == "My_Project_2026"
    assert sanitize_project_name("../../dangerous") == "dangerous"

    with pytest.raises(Exception):
        sanitize_project_name("..")

    with pytest.raises(Exception):
        sanitize_project_name("")


def test_validate_safe_path_rejection():
    # Outside allowed directories
    with pytest.raises(Exception) as exc_info:
        validate_safe_path("/etc/passwd")
    assert exc_info.value.status_code == 403

    with pytest.raises(Exception) as exc_info:
        validate_safe_path("../../var/log/syslog")
    assert exc_info.value.status_code == 403


# ==============================================================================
# Upload API Tests
# ==============================================================================


def test_upload_single_file_success(tmp_path):
    dummy_video_bytes = b"FAKE_MP4_HEADER_CONTENT_BYTES"
    files = {"file": ("test_upload.mp4", dummy_video_bytes, "video/mp4")}
    data = {"project_name": "test_upload_proj"}

    response = client.post("/api/v1/upload", files=files, data=data)
    assert response.status_code == 201
    res_data = response.json()
    assert res_data["filename"] == "test_upload.mp4"
    assert res_data["completed"] is True
    assert res_data["size"] == len(dummy_video_bytes)
    assert Path(res_data["filepath"]).exists()

    # Clean up
    proj_dir = VIRALS_DIR / "test_upload_proj"
    shutil.rmtree(proj_dir, ignore_errors=True)


def test_upload_disallowed_extension():
    files = {"file": ("script.sh", b"#!/bin/bash\necho bad", "text/plain")}
    response = client.post("/api/v1/upload", files=files)
    assert response.status_code == 400
    assert "Unsupported file format" in response.json()["detail"]


@pytest.mark.parametrize("img_ext", [".png", ".jpg", ".jpeg", ".webp", ".svg"])
def test_upload_image_formats_success(img_ext):
    dummy_bytes = b"FAKE_IMAGE_DATA_BYTES"
    filename = f"watermark_logo{img_ext}"
    files = {"file": (filename, dummy_bytes, "image/png")}
    response = client.post("/api/v1/upload", files=files)
    assert response.status_code == 201
    res_data = response.json()
    assert res_data["filename"] == filename
    assert res_data["completed"] is True
    assert res_data["size"] == len(dummy_bytes)
    target = Path(res_data["filepath"])
    assert target.exists()
    target.unlink(missing_ok=True)


def test_upload_image_with_project():
    dummy_bytes = b"FAKE_IMAGE_BYTES"
    filename = "logo.png"
    files = {"file": (filename, dummy_bytes, "image/png")}
    data = {"project_name": "watermark_proj"}
    response = client.post("/api/v1/upload", files=files, data=data)
    assert response.status_code == 201
    res_data = response.json()
    assert res_data["filename"] == filename
    assert res_data["project_name"] == "watermark_proj"
    target = Path(res_data["filepath"])
    assert target.exists()
    shutil.rmtree(VIRALS_DIR / "watermark_proj", ignore_errors=True)


@pytest.mark.parametrize("bad_name", ["malicious.exe", "script.sh", "payload.bin", "archive.zip"])
def test_upload_disallowed_arbitrary_binaries(bad_name):
    files = {"file": (bad_name, b"BINARY_DATA", "application/octet-stream")}
    response = client.post("/api/v1/upload", files=files)
    assert response.status_code == 400
    assert "Unsupported file format" in response.json()["detail"]


def test_upload_image_path_traversal_sanitized():
    files = {"file": ("../../evil_logo.png", b"IMAGE_BYTES", "image/png")}
    response = client.post("/api/v1/upload", files=files)
    assert response.status_code == 201
    res_data = response.json()
    assert res_data["filename"] == "evil_logo.png"
    assert ".." not in res_data["filename"]
    target = Path(res_data["filepath"])
    assert target.exists()
    target.unlink(missing_ok=True)


def test_upload_chunked():
    chunk1 = b"CHUNK_PART_ONE_"
    chunk2 = b"CHUNK_PART_TWO"
    uid = "test_chunk_upload_123"
    filename = "chunked_video.mp4"

    # Send chunk 0 of 2
    res0 = client.post(
        "/api/v1/upload",
        files={"file": (filename, chunk1, "video/mp4")},
        data={"chunk_index": "0", "total_chunks": "2", "upload_id": uid},
    )
    assert res0.status_code == 201
    assert res0.json()["completed"] is False

    # Send chunk 1 of 2
    res1 = client.post(
        "/api/v1/upload",
        files={"file": (filename, chunk2, "video/mp4")},
        data={"chunk_index": "1", "total_chunks": "2", "upload_id": uid},
    )
    assert res1.status_code == 201
    res1_data = res1.json()
    assert res1_data["completed"] is True
    assert res1_data["size"] == len(chunk1) + len(chunk2)

    final_file = Path(res1_data["filepath"])
    assert final_file.exists()
    assert final_file.read_bytes() == chunk1 + chunk2

    # Clean up
    final_file.unlink(missing_ok=True)


# ==============================================================================
# Preview API Tests
# ==============================================================================


def test_preview_streaming_full_and_range():
    # Create a dummy video file inside UPLOADS_DIR
    dummy_file = UPLOADS_DIR / "preview_stream_test.mp4"
    content = b"0123456789" * 100  # 1000 bytes
    dummy_file.write_bytes(content)

    try:
        # Full stream (no Range header)
        res_full = client.get(f"/api/v1/preview/stream?path={dummy_file}")
        assert res_full.status_code == 200
        assert res_full.content == content
        assert res_full.headers["Accept-Ranges"] == "bytes"

        # Range request: first 50 bytes (0-49)
        res_range = client.get(
            f"/api/v1/preview/stream?path={dummy_file}",
            headers={"Range": "bytes=0-49"},
        )
        assert res_range.status_code == 206
        assert len(res_range.content) == 50
        assert res_range.content == content[0:50]
        assert res_range.headers["Content-Range"] == "bytes 0-49/1000"
        assert res_range.headers["Content-Length"] == "50"

        # Range request: offset to end (900-)
        res_suffix = client.get(
            f"/api/v1/preview/stream?path={dummy_file}",
            headers={"Range": "bytes=900-"},
        )
        assert res_suffix.status_code == 206
        assert len(res_suffix.content) == 100
        assert res_suffix.content == content[900:1000]
        assert res_suffix.headers["Content-Range"] == "bytes 900-999/1000"

        # Invalid out-of-bounds range
        res_invalid = client.get(
            f"/api/v1/preview/stream?path={dummy_file}",
            headers={"Range": "bytes=2000-3000"},
        )
        assert res_invalid.status_code == 416

        # Path traversal security check
        res_forbidden = client.get("/api/v1/preview/stream?path=/etc/passwd")
        assert res_forbidden.status_code == 403
    finally:
        dummy_file.unlink(missing_ok=True)


def test_preview_metadata_path_traversal():
    res = client.get("/api/v1/preview/metadata?path=../../etc/shadow")
    assert res.status_code == 403


# ==============================================================================
# Library API Tests
# ==============================================================================


def test_library_crud_lifecycle():
    proj_name = "test_lib_proj_alpha"
    proj_dir = VIRALS_DIR / proj_name
    proj_dir.mkdir(parents=True, exist_ok=True)

    # Create dummy viral_segments.txt
    seg_file = proj_dir / "viral_segments.txt"
    seg_file.write_text(
        json.dumps({
            "segments": [
                {"title": "Hook Segment", "start": "00:00:01", "end": "00:00:15"},
                {"title": "Climax Segment", "start": "00:00:20", "end": "00:00:45"},
            ]
        })
    )

    # Create dummy video file
    dummy_vid = proj_dir / "output000.mp4"
    dummy_vid.write_bytes(b"VIDEO_CONTENT")

    try:
        # 1. List projects
        res_list = client.get("/api/v1/library/projects")
        assert res_list.status_code == 200
        projects = res_list.json()
        match = next((p for p in projects if p["name"] == proj_name), None)
        assert match is not None
        assert match["segment_count"] == 2
        assert match["video_count"] >= 1

        # 2. Get project detail
        res_detail = client.get(f"/api/v1/library/projects/{proj_name}")
        assert res_detail.status_code == 200
        detail = res_detail.json()
        assert detail["name"] == proj_name
        assert len(detail["segments"]) == 2
        assert any("output000.mp4" in f for f in detail["files"])

        # 3. Rename project
        new_name = "test_lib_proj_beta"
        res_rename = client.patch(
            f"/api/v1/library/projects/{proj_name}",
            json={"new_name": new_name},
        )
        assert res_rename.status_code == 200
        assert res_rename.json()["new_name"] == new_name
        assert not proj_dir.exists()
        new_proj_dir = VIRALS_DIR / new_name
        assert new_proj_dir.exists()

        # 4. Export project
        res_export = client.post(f"/api/v1/library/projects/{new_name}/export")
        assert res_export.status_code == 200
        exp_data = res_export.json()
        assert Path(exp_data["zip_path"]).exists()

        # 5. Delete project
        res_del = client.delete(f"/api/v1/library/projects/{new_name}")
        assert res_del.status_code == 200
        assert not new_proj_dir.exists()
    finally:
        shutil.rmtree(proj_dir, ignore_errors=True)
        shutil.rmtree(VIRALS_DIR / "test_lib_proj_beta", ignore_errors=True)


def test_library_assets_list_and_delete():
    asset_file = UPLOADS_DIR / "test_asset_file.mp4"
    asset_file.write_bytes(b"ASSET_DATA")

    try:
        res = client.get("/api/v1/library/assets?type=video")
        assert res.status_code == 200
        assets = res.json()
        found = any(a["name"] == "test_asset_file.mp4" for a in assets)
        assert found

        # Delete asset
        del_res = client.delete(f"/api/v1/library/assets?path={asset_file}")
        assert del_res.status_code == 200
        assert not asset_file.exists()
    finally:
        asset_file.unlink(missing_ok=True)


# ==============================================================================
# Subtitle API & Conversion Tests
# ==============================================================================


SAMPLE_SRT = """1
00:00:01,000 --> 00:00:04,500
First subtitle line

2
00:00:05,000 --> 00:00:08,250
Second line with punctuation!
And multiple rows.
"""

SAMPLE_VTT = """WEBVTT

1
00:00:01.000 --> 00:00:04.500
First subtitle line

2
00:00:05.000 --> 00:00:08.250
Second line with punctuation!
And multiple rows.
"""


def test_subtitle_parse_srt():
    res = client.post("/api/v1/subtitles/parse", json={"content": SAMPLE_SRT, "format": "srt"})
    assert res.status_code == 200
    data = res.json()
    assert data["format"] == "srt"
    assert data["count"] == 2
    assert data["entries"][0]["start"] == 1.0
    assert data["entries"][0]["end"] == 4.5
    assert data["entries"][0]["text"] == "First subtitle line"


def test_subtitle_parse_vtt():
    res = client.post("/api/v1/subtitles/parse", json={"content": SAMPLE_VTT, "format": "vtt"})
    assert res.status_code == 200
    data = res.json()
    assert data["format"] == "vtt"
    assert data["count"] == 2
    assert data["entries"][0]["start"] == 1.0
    assert data["entries"][0]["end"] == 4.5


def test_subtitle_conversion_and_roundtrip_integrity():
    # 1. SRT -> VTT
    res_vtt = client.post(
        "/api/v1/subtitles/convert",
        json={"content": SAMPLE_SRT, "source_format": "srt", "target_format": "vtt"},
    )
    assert res_vtt.status_code == 200
    vtt_content = res_vtt.json()["content"]
    assert "WEBVTT" in vtt_content
    assert "00:00:01.000 --> 00:00:04.500" in vtt_content

    # 2. VTT -> SRT
    res_srt = client.post(
        "/api/v1/subtitles/convert",
        json={"content": vtt_content, "source_format": "vtt", "target_format": "srt"},
    )
    assert res_srt.status_code == 200
    srt_content = res_srt.json()["content"]
    assert "00:00:01,000 --> 00:00:04,500" in srt_content

    # 3. Roundtrip data verification: parse original and roundtrip
    p_orig = client.post("/api/v1/subtitles/parse", json={"content": SAMPLE_SRT}).json()
    p_roundtrip = client.post("/api/v1/subtitles/parse", json={"content": srt_content}).json()

    assert len(p_orig["entries"]) == len(p_roundtrip["entries"])
    for orig_item, round_item in zip(p_orig["entries"], p_roundtrip["entries"]):
        assert orig_item["start"] == pytest.approx(round_item["start"], abs=0.005)
        assert orig_item["end"] == pytest.approx(round_item["end"], abs=0.005)
        assert orig_item["text"].strip() == round_item["text"].strip()

    # 4. SRT -> ASS
    res_ass = client.post(
        "/api/v1/subtitles/convert",
        json={"content": SAMPLE_SRT, "source_format": "srt", "target_format": "ass"},
    )
    assert res_ass.status_code == 200
    ass_content = res_ass.json()["content"]
    assert "[Script Info]" in ass_content
    assert "[Events]" in ass_content
    assert "Dialogue:" in ass_content


def test_subtitle_presets_and_style_preview():
    # Presets endpoint
    res_presets = client.get("/api/v1/subtitles/presets")
    assert res_presets.status_code == 200
    presets = res_presets.json()["presets"]
    assert "MrBeast Clean Hook" in presets
    assert "Hormozi (Classic)" in presets

    # Style preview endpoint
    res_prev = client.post(
        "/api/v1/subtitles/preview-style",
        json={
            "font": "Montserrat-ExtraBold",
            "size": 32,
            "color": "#FFFFFF",
            "highlight_color": "#FFD700",
            "mode": "highlight",
        },
    )
    assert res_prev.status_code == 200
    assert "html" in res_prev.json()
    assert len(res_prev.json()["html"]) > 10


def test_subtitle_save():
    proj_name = "test_sub_save_proj"
    proj_dir = VIRALS_DIR / proj_name
    proj_dir.mkdir(parents=True, exist_ok=True)

    try:
        res = client.post(
            "/api/v1/subtitles/save",
            json={
                "project_name": proj_name,
                "format": "srt",
                "filename": "custom_subs.srt",
                "entries": [
                    {"index": 1, "start": 0.0, "end": 2.0, "text": "Hello world"}
                ],
            },
        )
        assert res.status_code == 200
        saved_file = Path(res.json()["file_path"])
        assert saved_file.exists()
        assert "Hello world" in saved_file.read_text(encoding="utf-8")
    finally:
        shutil.rmtree(proj_dir, ignore_errors=True)


# ==============================================================================
# Google Drive API Tests
# ==============================================================================


def test_gdrive_status_and_videos():
    res_status = client.get("/api/v1/gdrive/status")
    assert res_status.status_code == 200
    data = res_status.json()
    assert "available" in data
    assert "mode" in data

    res_videos = client.get("/api/v1/gdrive/videos?limit=10")
    assert res_videos.status_code == 200
    assert isinstance(res_videos.json(), list)


def test_gdrive_import_validation():
    # Empty request
    res = client.post("/api/v1/gdrive/import", json={})
    assert res.status_code == 400

    # Non-existent file path
    res_notfound = client.post(
        "/api/v1/gdrive/import",
        json={"file_path": "/content/drive/MyDrive/non_existent_123.mp4"},
    )
    assert res_notfound.status_code == 404


# ==============================================================================
# System API Tests
# ==============================================================================


def test_system_status():
    res = client.get("/api/v1/system/status")
    assert res.status_code == 200
    status_data = res.json()
    assert status_data["status"] == "ok"
    assert "gpu" in status_data
    assert "disk" in status_data
    assert "ffmpeg" in status_data
    assert "python" in status_data
    assert "tools" in status_data

    # Check disk fields
    disk = status_data["disk"]
    assert "total_gb" in disk
    assert "free_gb" in disk

    # Check ffmpeg structure
    assert "installed" in status_data["ffmpeg"]


def test_system_health():
    res = client.get("/api/v1/system/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ok"
    assert "timestamp" in data

    # Top-level legacy health check
    res_legacy = client.get("/api/v1/health")
    assert res_legacy.status_code == 200
    assert res_legacy.json() == {"status": "ok"}


def test_system_prompt_template():
    res = client.get("/api/v1/system/prompt-template")
    assert res.status_code == 200
    data = res.json()
    assert "template" in data
    assert "{transcript_chunk}" in data["template"]
    assert "{json_template}" in data["template"]


def test_system_prompt_template_fallback(monkeypatch):
    from pathlib import Path
    from webui.backend.api.v1 import system

    # Point BASE_DIR to non-existent folder
    monkeypatch.setattr(system, "BASE_DIR", Path("/non/existent/path"))
    res = client.get("/api/v1/system/prompt-template")
    assert res.status_code == 200
    data = res.json()
    assert "template" in data
    assert "{transcript_chunk}" in data["template"]
    assert "{json_template}" in data["template"]


def test_root_fallback():
    res = client.get("/")
    assert res.status_code == 200
    assert res.json()["name"] == "ViralCutter API"


def test_real_video_metadata_and_thumbnail(tmp_path):
    import subprocess
    vid_path = UPLOADS_DIR / "real_test_sample.mp4"

    # Generate 1-second 320x240 test video using ffmpeg
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", "color=c=blue:s=320x240:d=1.5",
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        str(vid_path),
    ]
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)

    try:
        # Test metadata
        res_meta = client.get(f"/api/v1/preview/metadata?path={vid_path}")
        assert res_meta.status_code == 200
        meta = res_meta.json()
        assert meta["width"] == 320
        assert meta["height"] == 240
        assert meta["duration"] >= 1.0
        assert meta["fps"] > 0
        assert meta["codec"] == "h264"
        assert meta["aspect_ratio"] == "4:3"

        # Test thumbnail generation
        res_thumb = client.post(
            "/api/v1/preview/thumbnail",
            json={"path": str(vid_path), "timestamp": 0.5, "width": 160, "height": 120},
        )
        assert res_thumb.status_code == 200
        thumb_data = res_thumb.json()
        thumb_file = Path(thumb_data["thumbnail_path"])
        assert thumb_file.exists()

        # Test thumbnail file retrieval
        res_thumb_get = client.get(f"/api/v1/preview/thumbnail?path={thumb_file}")
        assert res_thumb_get.status_code == 200
        assert res_thumb_get.headers["content-type"] == "image/jpeg"

        # Clean up thumb
        thumb_file.unlink(missing_ok=True)
    finally:
        vid_path.unlink(missing_ok=True)


def test_subtitle_whisper_json_parsing():
    sample_whisper = {
        "segments": [
            {
                "id": 0,
                "seek": 0,
                "start": 0.5,
                "end": 3.2,
                "text": "This is a transcribed sentence.",
            },
            {
                "id": 1,
                "seek": 320,
                "start": 3.5,
                "end": 6.8,
                "text": "Here is another viral sentence.",
            },
        ]
    }
    res = client.post(
        "/api/v1/subtitles/parse",
        json={"content": json.dumps(sample_whisper), "format": "json"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["format"] == "json"
    assert data["count"] == 2
    assert data["entries"][0]["start"] == 0.5
    assert data["entries"][0]["text"] == "This is a transcribed sentence."


def test_gdrive_export_local(tmp_path):
    proj_name = "test_gdrive_export_proj"
    proj_dir = VIRALS_DIR / proj_name
    proj_dir.mkdir(parents=True, exist_ok=True)
    (proj_dir / "viral_segments.txt").write_text(json.dumps({"segments": []}))
    (proj_dir / "output000.mp4").write_bytes(b"CONTENT")

    try:
        res = client.post("/api/v1/gdrive/export", json={"project_name": proj_name})
        assert res.status_code == 200
        exp = res.json()
        assert exp["status"] in {"exported", "exported_local"}
        assert Path(exp["destination"]).exists()
    finally:
        shutil.rmtree(proj_dir, ignore_errors=True)

