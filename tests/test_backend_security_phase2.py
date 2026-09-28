import asyncio
import os
import shutil
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from webui.backend.config import (
    BASE_DIR,
    PREVIEWS_DIR,
    UPLOADS_DIR,
    VIRALS_DIR,
    ensure_directories,
)
from webui.backend.core.security import (
    DEFAULT_ALLOWED_ROOTS,
    validate_safe_path,
)
from webui.backend.main import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_dirs():
    ensure_directories()
    yield


# ==============================================================================
# P0: Path Traversal & Arbitrary File Write in Subtitles Save
# ==============================================================================


def test_subtitles_save_rejects_path_traversal_filename():
    payload = {
        "project_name": "test_sec_proj",
        "filename": "../../vuln_subtitles_test.txt",
        "format": "srt",
        "entries": [{"index": 1, "start": 0.0, "end": 2.0, "text": "Exploit"}],
    }
    response = client.post("/api/v1/subtitles/save", json=payload)
    assert response.status_code == 400
    assert "traversal" in response.json()["detail"].lower()

    # Reject absolute path or path with separators
    payload["filename"] = "/tmp/vuln_subtitles_test.txt"
    response = client.post("/api/v1/subtitles/save", json=payload)
    assert response.status_code == 400

    payload["filename"] = "..\\windows_traversal.srt"
    response = client.post("/api/v1/subtitles/save", json=payload)
    assert response.status_code == 400


def test_subtitles_save_rejects_unauthorized_filepath():
    # Attempting to write into code directories or arbitrary host locations
    payload = {
        "file_path": str(BASE_DIR / "scripts" / "malicious.py"),
        "format": "srt",
        "entries": [{"index": 1, "start": 0.0, "end": 2.0, "text": "print('pwned')"}],
    }
    response = client.post("/api/v1/subtitles/save", json=payload)
    assert response.status_code == 403

    payload["file_path"] = "/etc/cron.d/malicious"
    response = client.post("/api/v1/subtitles/save", json=payload)
    assert response.status_code == 403


def test_subtitles_save_valid_filename():
    proj_name = "test_sec_valid_proj"
    payload = {
        "project_name": proj_name,
        "filename": "clean_subtitles.srt",
        "format": "srt",
        "entries": [{"index": 1, "start": 0.0, "end": 2.0, "text": "Valid Subtitle"}],
    }
    response = client.post("/api/v1/subtitles/save", json=payload)
    assert response.status_code == 200
    saved_path = Path(response.json()["file_path"])
    assert saved_path.exists()
    assert (VIRALS_DIR / proj_name / "subs").resolve() in saved_path.parents

    # Cleanup
    shutil.rmtree(VIRALS_DIR / proj_name, ignore_errors=True)


# ==============================================================================
# P0: Code Overwrite & RCE in DEFAULT_ALLOWED_ROOTS
# ==============================================================================


def test_security_roots_exclude_code_directories():
    scripts_dir = (BASE_DIR / "scripts").resolve()
    webui_dir = (BASE_DIR / "webui").resolve()

    resolved_roots = [r.resolve() for r in DEFAULT_ALLOWED_ROOTS]
    assert scripts_dir not in resolved_roots
    assert webui_dir not in resolved_roots

    # Access via validate_safe_path is rejected with 403
    with pytest.raises(Exception) as exc_info:
        validate_safe_path(str(scripts_dir / "gdrive_client.py"))
    assert exc_info.value.status_code == 403

    with pytest.raises(Exception) as exc_info:
        validate_safe_path(str(webui_dir / "backend" / "main.py"))
    assert exc_info.value.status_code == 403


def test_source_code_disclosure_via_preview_stream_prevented():
    source_file = BASE_DIR / "webui" / "backend" / "main.py"
    response = client.get(f"/api/v1/preview/stream?path={source_file}")
    assert response.status_code == 403


# ==============================================================================
# P1: Arbitrary Host File Exfiltration in GDrive Import
# ==============================================================================


def test_gdrive_import_rejects_arbitrary_system_paths():
    # Attempt to exfiltrate /etc/passwd or tmp files
    response = client.post("/api/v1/gdrive/import", json={"file_path": "/etc/passwd"})
    assert response.status_code == 403
    assert "outside allowed google drive mount" in response.json()["detail"].lower()

    response = client.post("/api/v1/gdrive/import", json={"file_path": "/tmp/host_secret.mp4"})
    assert response.status_code == 403

    # Traversal escaping drive root
    response = client.post(
        "/api/v1/gdrive/import",
        json={"file_path": "/content/drive/MyDrive/../../etc/shadow"},
    )
    assert response.status_code == 403


def test_gdrive_import_allows_within_drive_boundary(tmp_path):
    mock_drive = tmp_path / "mock_drive"
    mock_drive.mkdir(parents=True)
    mock_video = mock_drive / "test_import_video.mp4"
    mock_video.write_bytes(b"MOCK_VIDEO_DATA")

    with patch("webui.drive_browser.DRIVE_ROOT", str(mock_drive)):
        response = client.post(
            "/api/v1/gdrive/import",
            json={"file_path": str(mock_video), "project_name": "test_gdrive_import_proj"},
        )
        assert response.status_code == 200
        res_data = response.json()
        assert res_data["status"] == "imported"
        imported_file = Path(res_data["video_path"])
        assert imported_file.exists()
        assert imported_file.read_bytes() == b"MOCK_VIDEO_DATA"

    # Cleanup
    shutil.rmtree(VIRALS_DIR / "test_gdrive_import_proj", ignore_errors=True)


# ==============================================================================
# P2: Deletion and Renaming of UPLOADS_DIR in Library API
# ==============================================================================


def test_library_uploads_dir_cannot_be_deleted():
    assert UPLOADS_DIR.exists()

    response = client.delete("/api/v1/library/projects/uploads")
    assert response.status_code == 400
    assert "protected" in response.json()["detail"].lower()
    assert UPLOADS_DIR.exists()


def test_library_uploads_dir_cannot_be_renamed():
    response = client.patch(
        "/api/v1/library/projects/uploads",
        json={"new_name": "renamed_uploads"},
    )
    assert response.status_code == 400
    assert "protected" in response.json()["detail"].lower()
    assert UPLOADS_DIR.exists()


def test_library_project_cannot_be_renamed_to_uploads():
    test_proj = VIRALS_DIR / "test_lib_proj"
    test_proj.mkdir(parents=True, exist_ok=True)

    response = client.patch(
        "/api/v1/library/projects/test_lib_proj",
        json={"new_name": "uploads"},
    )
    assert response.status_code == 400
    assert "protected" in response.json()["detail"].lower()

    # Cleanup
    shutil.rmtree(test_proj, ignore_errors=True)


def test_library_uploads_cannot_be_accessed_as_project():
    response = client.get("/api/v1/library/projects/uploads")
    assert response.status_code == 404


# ==============================================================================
# P2: Missing Subprocess Timeout in Preview Metadata
# ==============================================================================


def test_preview_metadata_subprocess_timeout(tmp_path):
    dummy_video = UPLOADS_DIR / "test_timeout_video.mp4"
    dummy_video.write_bytes(b"DUMMY_MP4_DATA")

    async def mock_timeout(coro, timeout=None):
        if asyncio.iscoroutine(coro):
            coro.close()
        raise asyncio.TimeoutError()

    with patch("asyncio.wait_for", side_effect=mock_timeout):
        response = client.get(f"/api/v1/preview/metadata?path={dummy_video}")
        assert response.status_code == 504
        assert "timed out" in response.json()["detail"].lower()

    # Cleanup
    if dummy_video.exists():
        dummy_video.unlink()


# ==============================================================================
# Phase 3 Security Remediation Tests
# ==============================================================================


def test_library_export_download_security():
    # 1. Missing query params
    res = client.get("/api/v1/library/export/download")
    assert res.status_code == 400

    # 2. Path traversal outside VIRALS_DIR
    res = client.get("/api/v1/library/export/download?file_path=/etc/passwd")
    assert res.status_code in (403, 404)

    # 3. Non-zip file inside VIRALS_DIR
    dummy_txt = VIRALS_DIR / "fake_export.txt"
    dummy_txt.write_text("not a zip")
    try:
        res = client.get(f"/api/v1/library/export/download?path={dummy_txt}")
        assert res.status_code == 400
        assert "valid zip" in res.json()["detail"].lower()
    finally:
        if dummy_txt.exists():
            dummy_txt.unlink()

    # 4. Valid zip inside VIRALS_DIR
    dummy_zip = VIRALS_DIR / "valid_export.zip"
    dummy_zip.write_bytes(b"PK\x05\x06" + b"\x00" * 18)  # Empty ZIP bytes
    try:
        res = client.get(f"/api/v1/library/export/download?file_path={dummy_zip}")
        assert res.status_code == 200
        assert res.headers["content-type"] == "application/zip"
    finally:
        if dummy_zip.exists():
            dummy_zip.unlink()


def test_library_assets_file_path_and_project_filter():
    proj_dir = VIRALS_DIR / "test_filter_proj"
    proj_dir.mkdir(parents=True, exist_ok=True)
    asset_file = proj_dir / "clip1.mp4"
    asset_file.write_bytes(b"CLIP_DATA")

    try:
        # Filter by project_name
        res = client.get("/api/v1/library/assets?project_name=test_filter_proj")
        assert res.status_code == 200
        assets = res.json()
        assert any(a["name"] == "clip1.mp4" for a in assets)

        # Delete by file_path
        del_res = client.delete(f"/api/v1/library/assets?file_path={asset_file}")
        assert del_res.status_code == 200
        assert not asset_file.exists()
    finally:
        shutil.rmtree(proj_dir, ignore_errors=True)
