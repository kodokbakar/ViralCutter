"""Tests for pure functions in scripts.compile_segments"""
import sys
import os
import pytest
from unittest.mock import MagicMock

# Mock the merge_subtitles module before importing compile_segments
# (compile_segments does `from scripts import merge_subtitles`)
mock_merge = MagicMock()
sys.modules["scripts.merge_subtitles"] = mock_merge
sys.modules["merge_subtitles"] = mock_merge

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from scripts.compile_segments import (
    extract_segment_number,
    segment_sort_key,
    parse_segment_order,
    reorder_paths,
    project_root_for,
)


class TestExtractSegmentNumber:
    def test_leading_number(self):
        assert extract_segment_number("001_title.mp4") == 1
        assert extract_segment_number("002_intro.mp4") == 2

    def test_segment_pattern(self):
        assert extract_segment_number("segment-3-foo.mp4") == 3

    def test_output_pattern(self):
        assert extract_segment_number("output005_final.mp4") == 5

    def test_final_output_pattern(self):
        assert extract_segment_number("final-output-7-bar.mp4") == 7

    def test_no_number_returns_none(self):
        assert extract_segment_number("video.mp4") is None

    def test_full_path(self):
        assert extract_segment_number("/some/dir/004_hello.mp4") == 4

    def test_underscore_separated(self):
        assert extract_segment_number("42_the_title.mp4") == 42


class TestSegmentSortKey:
    def test_numbered_sorts_first(self):
        keys = [segment_sort_key("003_b.mp4"), segment_sort_key("001_a.mp4")]
        assert keys[0] > keys[1]  # 3 > 1

    def test_unnumbered_sorts_last(self):
        keys = [
            segment_sort_key("001_a.mp4"),
            segment_sort_key("no_number.mp4"),
        ]
        assert keys[0] < keys[1]  # numbered < unnumbered (10**9)

    def test_same_number_sorts_by_name(self):
        key_a = segment_sort_key("001_aaa.mp4")
        key_b = segment_sort_key("001_zzz.mp4")
        assert key_a < key_b

    def test_correct_tuple_format(self):
        key = segment_sort_key("005_test.mp4")
        assert key == (5, "005_test.mp4")


class TestParseSegmentOrder:
    def test_none_returns_none(self):
        assert parse_segment_order(None, 3) is None

    def test_empty_string_returns_none(self):
        assert parse_segment_order("", 3) is None

    def test_valid_order(self):
        assert parse_segment_order("3,1,2", 3) == [3, 1, 2]

    def test_identity_order(self):
        assert parse_segment_order("1,2,3", 3) == [1, 2, 3]

    def test_invalid_non_numeric(self):
        with pytest.raises(ValueError, match="comma-separated numbers"):
            parse_segment_order("a,b,c", 3)

    def test_invalid_count_too_few(self):
        with pytest.raises(ValueError, match="Invalid segment order"):
            parse_segment_order("1,2", 3)

    def test_invalid_count_too_many(self):
        with pytest.raises(ValueError, match="Invalid segment order"):
            parse_segment_order("1,2,3,4", 3)

    def test_invalid_duplicates(self):
        with pytest.raises(ValueError, match="Invalid segment order"):
            parse_segment_order("1,1,2", 3)

    def test_invalid_missing_number(self):
        with pytest.raises(ValueError, match="Invalid segment order"):
            parse_segment_order("1,2,4", 3)


class TestReorderPaths:
    def test_basic_reorder(self):
        paths = [
            "/cuts/001_a.mp4",
            "/cuts/002_b.mp4",
            "/cuts/003_c.mp4",
        ]
        result = reorder_paths(paths, [3, 1, 2])
        assert result == [
            "/cuts/003_c.mp4",
            "/cuts/001_a.mp4",
            "/cuts/002_b.mp4",
        ]

    def test_identity_order(self):
        paths = [
            "/cuts/001_a.mp4",
            "/cuts/002_b.mp4",
        ]
        result = reorder_paths(paths, [1, 2])
        assert result == paths

    def test_fallback_index_based(self):
        """When no paths have extractable numbers, fall back to index-based."""
        paths = ["a.mp4", "b.mp4", "c.mp4"]
        result = reorder_paths(paths, [3, 1, 2])
        assert result == ["c.mp4", "a.mp4", "b.mp4"]


class TestProjectRootFor:
    def test_burned_sub(self, tmp_path):
        folder = tmp_path / "myproject" / "burned_sub"
        folder.mkdir(parents=True)
        result = project_root_for(str(folder))
        assert result == str(tmp_path / "myproject")

    def test_final(self, tmp_path):
        folder = tmp_path / "myproject" / "final"
        folder.mkdir(parents=True)
        result = project_root_for(str(folder))
        assert result == str(tmp_path / "myproject")

    def test_cuts(self, tmp_path):
        folder = tmp_path / "myproject" / "cuts"
        folder.mkdir(parents=True)
        result = project_root_for(str(folder))
        assert result == str(tmp_path / "myproject")

    def test_other_folder_returns_self(self, tmp_path):
        folder = tmp_path / "myproject" / "other"
        folder.mkdir(parents=True)
        result = project_root_for(str(folder))
        assert result == str(folder)
