"""Tests for scripts.adjust_subtitles.format_time_ass"""
import sys
import os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from scripts.adjust_subtitles import format_time_ass


class TestFormatTimeAss:
    def test_zero(self):
        assert format_time_ass(0) == "0:00:00.00"

    def test_exactly_one_second(self):
        assert format_time_ass(1) == "0:00:01.00"

    def test_one_minute(self):
        assert format_time_ass(60) == "0:01:00.00"

    def test_one_hour(self):
        assert format_time_ass(3600) == "1:00:00.00"

    def test_complex_time(self):
        # 3661.5 = 1h 1min 1.5s
        assert format_time_ass(3661.5) == "1:01:01.50"

    def test_fractional_seconds(self):
        assert format_time_ass(0.5) == "0:00:00.50"

    def test_99_centiseconds(self):
        assert format_time_ass(0.99) == "0:00:00.99"

    def test_23_hours_59_minutes_59_seconds_99_cs(self):
        assert format_time_ass(86399.99) == "23:59:59.99"

    def test_large_value(self):
        # 100 hours + 1 second
        assert format_time_ass(360001) == "100:00:01.00"

    def test_half_centisecond_truncates(self):
        # 0.005 seconds = 0.5 centiseconds -> int(0.5) = 0
        assert format_time_ass(0.005) == "0:00:00.00"

    def test_format_always_has_colon_separated(self):
        result = format_time_ass(42.73)
        # Format: H:MM:SS.CC
        parts = result.split(":")
        assert len(parts) == 3
        assert "." in parts[2]
