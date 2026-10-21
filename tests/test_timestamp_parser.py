import pytest
from scripts.create_viral_segments import parse_time_ref, process_segments

@pytest.mark.parametrize("time_str,expected", [
    ("(120s)", 120.0),
    ("120s", 120.0),
    ("120", 120.0),
    ("120.5s", 120.5),
    ("(4500s)", 4500.0),
    ("01:15:30", 4530.0),       # 1h 15m 30s
    ("1:15:30", 4530.0),
    ("01:15:30.500", 4530.5),
    ("15:30", 930.0),           # 15m 30s
    ("05:20", 320.0),
    ("00:45", 45.0),
    (3600, 3600.0),
    (1800.5, 1800.5),
    ("", 0.0),
    (None, 0.0),
])
def test_parse_time_ref_formats(time_str, expected):
    assert parse_time_ref(time_str) == expected


def test_process_segments_long_video_timestamps():
    """Verify segments at 1h15m don't fall back to 0s and don't get dropped."""
    transcript_segments = [
        {"start": 0.0, "end": 10.0, "text": "intro at the very start"},
        # 1 hour 15 minutes = 4500s
        {"start": 4500.0, "end": 4515.0, "text": "segmen penting di menit tujuh puluh lima"},
        {"start": 4515.0, "end": 4570.0, "text": "penjelasan mendalam tentang topik"},
        # 1 hour 25 minutes = 5100s
        {"start": 5100.0, "end": 5115.0, "text": "segmen kedua di menit delapan puluh lima"},
        {"start": 5115.0, "end": 5165.0, "text": "penutup topik kedua"},
    ]

    raw_segments = [
        {
            "title": "Segment 1h 15m",
            "start_time_ref": "01:15:00",
            "start_text": "segmen penting di menit",
            "end_text": "penjelasan mendalam",
            "score": 95,
        },
        {
            "title": "Segment 1h 25m",
            "start_time_ref": "01:25:00",
            "start_text": "segmen kedua di menit",
            "end_text": "penutup topik kedua",
            "score": 90,
        },
    ]

    result = process_segments(raw_segments, transcript_segments, min_duration=15, max_duration=90)
    segs = result.get("segments", [])
    assert len(segs) == 2, f"Expected 2 segments, got {len(segs)} (one was falsely dropped as overlap!)"
    assert segs[0]["start_time"] >= 4490.0
    assert segs[1]["start_time"] >= 5090.0
