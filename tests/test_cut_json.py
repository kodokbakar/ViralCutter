"""Tests for scripts.cut_json.process_segments"""
import sys
import os
import json
import pytest

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from scripts.cut_json import process_segments


class TestProcessSegments:
    """Tests for process_segments pure function."""

    def test_empty_input(self):
        result = process_segments({}, 0, 100)
        assert result == {"segments": []}

    def test_empty_segments(self):
        result = process_segments({"segments": []}, 0, 100)
        assert result == {"segments": []}

    def test_segment_fully_inside_range(self):
        data = {
            "segments": [
                {"start": 10, "end": 20, "text": "hello"},
            ]
        }
        # cut from 5 to 30: segment fully inside
        result = process_segments(data, 5, 30)
        assert len(result["segments"]) == 1
        seg = result["segments"][0]
        # timestamps adjusted to 0-based relative to start_time
        assert seg["start"] == 5   # 10 - 5
        assert seg["end"] == 15    # 20 - 5
        assert seg["text"] == "hello"

    def test_segment_fully_outside_range_before(self):
        data = {
            "segments": [
                {"start": 0, "end": 5, "text": "before"},
            ]
        }
        result = process_segments(data, 10, 20)
        assert len(result["segments"]) == 0

    def test_segment_fully_outside_range_after(self):
        data = {
            "segments": [
                {"start": 25, "end": 30, "text": "after"},
            ]
        }
        result = process_segments(data, 10, 20)
        assert len(result["segments"]) == 0

    def test_segment_overlapping_start(self):
        data = {
            "segments": [
                {"start": 0, "end": 15, "text": "overlap start"},
            ]
        }
        result = process_segments(data, 10, 30)
        seg = result["segments"][0]
        # clipped: max(0, 0-10)=0, min(30,15)-10=5
        assert seg["start"] == 0
        assert seg["end"] == 5

    def test_segment_overlapping_end(self):
        data = {
            "segments": [
                {"start": 15, "end": 35, "text": "overlap end"},
            ]
        }
        result = process_segments(data, 10, 25)
        seg = result["segments"][0]
        # clipped: max(0, 15-10)=5, min(25,35)-10=15
        assert seg["start"] == 5
        assert seg["end"] == 15

    def test_segment_covers_entire_range(self):
        data = {
            "segments": [
                {"start": 0, "end": 100, "text": "big"},
            ]
        }
        result = process_segments(data, 20, 40)
        seg = result["segments"][0]
        assert seg["start"] == 0
        assert seg["end"] == 20

    def test_words_filtered_by_range(self):
        data = {
            "segments": [
                {
                    "start": 5,
                    "end": 25,
                    "words": [
                        {"start": 0, "end": 5, "word": "before"},   # outside
                        {"start": 10, "end": 15, "word": "inside"},  # inside
                        {"start": 25, "end": 30, "word": "after"},   # outside (end == start_time -> not included)
                    ],
                },
            ]
        }
        result = process_segments(data, 10, 25)
        seg = result["segments"][0]
        assert len(seg["words"]) == 1
        assert seg["words"][0]["word"] == "inside"
        # word timestamp adjusted
        assert seg["words"][0]["start"] == 0   # 10 - 10
        assert seg["words"][0]["end"] == 5     # 15 - 10

    def test_words_partial_overlap(self):
        data = {
            "segments": [
                {
                    "start": 5,
                    "end": 25,
                    "words": [
                        {"start": 0, "end": 12, "word": "partial"},  # overlaps start
                    ],
                },
            ]
        }
        result = process_segments(data, 10, 30)
        seg = result["segments"][0]
        assert len(seg["words"]) == 1
        # clipped: max(0,0-10)=0, min(30,12)-10=2
        assert seg["words"][0]["start"] == 0
        assert seg["words"][0]["end"] == 2

    def test_segment_boundary_conditions(self):
        """Test exact boundary: seg_end <= start_time excluded, seg_start >= end_time excluded."""
        data = {
            "segments": [
                {"start": 10, "end": 20, "text": "exact start"},
                {"start": 20, "end": 30, "text": "exact boundary"},
            ]
        }
        # cut from 10 to 20
        result = process_segments(data, 10, 20)
        assert len(result["segments"]) == 1
        assert result["segments"][0]["text"] == "exact start"

    def test_multiple_segments_mixed(self):
        data = {
            "segments": [
                {"start": 0, "end": 5, "text": "out"},
                {"start": 5, "end": 15, "text": "in1"},
                {"start": 12, "end": 22, "text": "in2"},
                {"start": 25, "end": 30, "text": "out"},
            ]
        }
        result = process_segments(data, 5, 20)
        assert len(result["segments"]) == 2
        assert result["segments"][0]["text"] == "in1"
        assert result["segments"][1]["text"] == "in2"

    def test_preserves_extra_fields(self):
        data = {
            "segments": [
                {"start": 10, "end": 20, "text": "hi", "speaker": "A"},
            ]
        }
        result = process_segments(data, 5, 25)
        seg = result["segments"][0]
        assert seg["speaker"] == "A"
        assert seg["text"] == "hi"
