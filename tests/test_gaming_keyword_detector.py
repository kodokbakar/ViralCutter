import pytest
from scripts.gaming_keyword_detector import (
    match_gaming_keywords,
    scan_shout_keywords,
    get_keyword_score_at_time,
)

def test_match_gaming_keywords_indonesian():
    text = "anjir gila banget dia bisa gitu rata semua musuh"
    matched = match_gaming_keywords(text)
    assert "anjir" in matched
    assert "gila" in matched
    assert "bisa gitu" in matched
    assert "rata" in matched

def test_match_gaming_keywords_english():
    text = "holy shit what a clutch no way let's go"
    matched = match_gaming_keywords(text)
    assert "holy shit" in matched
    assert "clutch" in matched
    assert "no way" in matched
    assert "let's go" in matched

def test_match_gaming_keywords_empty_or_non_string():
    assert match_gaming_keywords("") == []
    assert match_gaming_keywords(None) == []
    assert match_gaming_keywords(123) == []

def test_scan_shout_keywords_clusters():
    words = [
        {"word": "halo", "start": 1.0, "end": 1.5},
        {"word": "anjir", "start": 10.0, "end": 10.4},
        {"word": "gila", "start": 11.0, "end": 11.5},
        {"word": "mati", "start": 12.0, "end": 12.4},
        {"word": "santai", "start": 40.0, "end": 40.5},
    ]
    clusters = scan_shout_keywords(words, window_sec=6.0)
    assert len(clusters) == 1
    c = clusters[0]
    assert 10.0 <= c["timestamp"] <= 12.0
    assert c["count"] == 3
    assert c["score"] >= 75.0

def test_scan_shout_keywords_empty():
    assert scan_shout_keywords([]) == []
    assert scan_shout_keywords(None) == []

def test_scan_shout_keywords_multiword_split():
    words = [
        {"word": "no", "start": 5.0, "end": 5.2},
        {"word": "way", "start": 5.25, "end": 5.5},
        {"word": "clutch", "start": 6.0, "end": 6.5},
    ]
    clusters = scan_shout_keywords(words, window_sec=4.0)
    assert len(clusters) == 1
    assert "no way" in clusters[0]["matched_words"]
    assert "clutch" in clusters[0]["matched_words"]
    assert clusters[0]["count"] == 2

def test_get_keyword_score_at_time():
    clusters = [{"timestamp": 15.0, "score": 90.0}]
    assert get_keyword_score_at_time(clusters, 15.0) == 90.0
    assert get_keyword_score_at_time(clusters, 17.0) > 0.0
    assert get_keyword_score_at_time(clusters, 30.0) == 0.0

def test_get_keyword_score_at_time_empty_or_zero_dist():
    assert get_keyword_score_at_time([], 10.0) == 0.0
    clusters = [{"timestamp": 10.0, "score": 80.0}]
    assert get_keyword_score_at_time(clusters, 10.0, max_distance=0.0) == 80.0
    assert get_keyword_score_at_time(clusters, 11.0, max_distance=0.0) == 0.0
