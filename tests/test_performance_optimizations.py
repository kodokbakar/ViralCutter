import os
import time
import pytest
from unittest.mock import patch
from webui import drive_browser
from webui import library

def test_drive_browser_cache_and_depth(tmp_path):
    # Mock DRIVE_ROOT to tmp_path
    with patch.object(drive_browser, "DRIVE_ROOT", str(tmp_path)), \
         patch.object(drive_browser, "is_colab_drive_available", return_value=True):
        
        # Create folder structure
        video1 = tmp_path / "video1.mp4"
        video1.write_bytes(b"0" * 1024)

        sub = tmp_path / "subdir"
        sub.mkdir()
        video2 = sub / "video2.mp4"
        video2.write_bytes(b"0" * 2048)

        deep = sub / "deep1" / "deep2" / "deep3"
        deep.mkdir(parents=True)
        video_deep = deep / "deep_video.mp4"
        video_deep.write_bytes(b"0" * 1024)

        # First call: lists videos up to max_depth=2
        res1 = drive_browser.list_drive_videos("", limit=50, max_depth=2, force_refresh=True)
        paths = [p for _, p in res1]
        assert str(video1) in paths
        assert str(video2) in paths
        assert str(video_deep) not in paths  # Excluded due to depth limit!

        # Second call: cached
        res2 = drive_browser.list_drive_videos("", limit=50, max_depth=2, force_refresh=False)
        assert res1 == res2

def test_library_get_existing_projects_caching(tmp_path):
    with patch.object(library, "VIRALS_DIR", str(tmp_path)):
        p1 = tmp_path / "proj1"
        p1.mkdir()
        
        # First call loads proj1
        projs1 = library.get_existing_projects(force_refresh=True)
        assert "proj1" in projs1

        # Create another folder without force refresh
        p2 = tmp_path / "proj2"
        p2.mkdir()
        
        # Should return cached projs1 within TTL
        projs2 = library.get_existing_projects(force_refresh=False)
        assert projs2 == projs1

        # With force refresh, it should pick up proj2
        projs3 = library.get_existing_projects(force_refresh=True)
        assert "proj2" in projs3
