"""Tests for webui.project_export"""
import sys
import os
import json
import zipfile
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from webui.project_export import (
    _safe_project_name,
    build_project_zip,
    EXPORT_FOLDERS,
    EXPORT_FILES,
    ROOT_EXTRA_PATTERNS,
)


class TestSafeProjectName:
    def test_normal_path(self):
        assert _safe_project_name("/home/user/my_project") == "my_project"

    def test_trailing_slash(self):
        assert _safe_project_name("/home/user/my_project/") == "my_project"

    def test_current_dir(self):
        # basename of abspath of "." will be the cwd name
        result = _safe_project_name(".")
        assert result  # non-empty

    def test_empty_basename_fallback(self):
        # Root path: basename of "/" is "", should return "project"
        assert _safe_project_name("/") == "project"

    def test_whitespace_stripped(self):
        assert _safe_project_name("/path/to/  myproject  ") == "myproject"


class TestBuildProjectZip:
    def test_no_project_raises(self):
        with pytest.raises(ValueError, match="No project selected"):
            build_project_zip("")

    def test_nonexistent_project_raises(self):
        with pytest.raises(FileNotFoundError, match="Project folder not found"):
            build_project_zip("/nonexistent/path/xyz")

    def test_empty_project_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError, match="No exportable files found"):
            build_project_zip(str(tmp_path))

    def test_creates_zip_with_files(self, tmp_path):
        # Create some expected files
        cuts_dir = tmp_path / "cuts"
        cuts_dir.mkdir()
        (cuts_dir / "video.mp4").write_bytes(b"fake")

        prompt = tmp_path / "prompt.txt"
        prompt.write_text("hello")

        result = build_project_zip(str(tmp_path))
        assert result.endswith(".zip")
        assert os.path.exists(result)

        with zipfile.ZipFile(result) as zf:
            names = zf.namelist()
            assert any("cuts/video.mp4" in n for n in names)
            assert any("prompt.txt" in n for n in names)

    def test_zip_removes_pycache(self, tmp_path):
        cuts_dir = tmp_path / "cuts" / "__pycache__"
        cuts_dir.mkdir(parents=True)
        (cuts_dir / "cached.pyc").write_bytes(b"cache")

        final_dir = tmp_path / "final"
        final_dir.mkdir()
        (final_dir / "output.mp4").write_bytes(b"real")

        result = build_project_zip(str(tmp_path))
        with zipfile.ZipFile(result) as zf:
            names = zf.namelist()
            assert not any("__pycache__" in n for n in names)
            assert any("final/output.mp4" in n for n in names)

    def test_zip_excludes_other_zips(self, tmp_path):
        final_dir = tmp_path / "final"
        final_dir.mkdir()
        (final_dir / "other_export.zip").write_bytes(b"zip")
        (final_dir / "real.mp4").write_bytes(b"real")

        result = build_project_zip(str(tmp_path))
        with zipfile.ZipFile(result) as zf:
            names = zf.namelist()
            assert not any(n.endswith("other_export.zip") for n in names)
            assert any("final/real.mp4" in n for n in names)

    def test_overwrites_existing_zip(self, tmp_path):
        final_dir = tmp_path / "final"
        final_dir.mkdir()
        (final_dir / "video.mp4").write_bytes(b"v1")

        # Create a stale zip
        stale_zip = tmp_path / f"{_safe_project_name(str(tmp_path))}_export.zip"
        stale_zip.write_bytes(b"stale")

        result = build_project_zip(str(tmp_path))
        with zipfile.ZipFile(result) as zf:
            # Should have fresh content, not stale
            assert any("final/video.mp4" in n for n in zf.namelist())
