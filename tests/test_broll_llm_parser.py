import pytest
from scripts import smart_clipping
from scripts.create_viral_segments import process_segments


def test_parse_llm_topics_with_broll():
    sample_llm = """
    {
      "topics": [
        {
          "title": "Rahasia Cuan 100M",
          "rationale": "High retention statistic",
          "score": 92,
          "segments": {
            "hook": {"start_time": 2.0, "end_time": 6.0, "text": "Kalian tahu tidak?"},
            "core": {"start_time": 8.0, "end_time": 25.0, "text": "Bisnis ini melonjak 85% dalam 1 bulan."},
            "payoff": {"start_time": 30.0, "end_time": 40.0, "text": "Itulah kuncinya."}
          },
          "broll_items": [
            {
              "start_offset": 8.5,
              "duration": 3.5,
              "template_id": "stat_counter",
              "data": {
                "target_number": "85",
                "suffix": "%",
                "label": "Lonjakan Bisnis 1 Bulan"
              }
            }
          ]
        }
      ]
    }
    """
    topics = smart_clipping.parse_llm_topics(sample_llm)
    assert len(topics) == 1
    topic = topics[0]
    assert "broll_items" in topic
    assert len(topic["broll_items"]) == 1
    assert topic["broll_items"][0]["template_id"] == "stat_counter"
    assert topic["broll_items"][0]["start_offset"] == 8.5
    assert topic["broll_items"][0]["duration"] == 3.5
    assert topic["broll_items"][0]["data"]["target_number"] == "85"


def test_parse_llm_topics_invalid_template_filtered():
    sample_llm = """
    {
      "topics": [
        {
          "title": "Topic with Invalid Template",
          "segments": {
            "hook": {"start_time": 1.0, "end_time": 4.0, "text": "Hook text"}
          },
          "broll_items": [
            {
              "start_offset": 2.0,
              "duration": 3.0,
              "template_id": "invalid_template",
              "data": {"foo": "bar"}
            },
            {
              "start_offset": 3.0,
              "duration": 4.0,
              "template_id": "quote_card",
              "data": {"quote": "Valid quote"}
            }
          ]
        }
      ]
    }
    """
    topics = smart_clipping.parse_llm_topics(sample_llm)
    assert len(topics) == 1
    broll = topics[0].get("broll_items", [])
    assert len(broll) == 1
    assert broll[0]["template_id"] == "quote_card"


def test_parse_llm_topics_without_broll():
    sample_llm = """
    {
      "topics": [
        {
          "title": "No Broll Topic",
          "segments": {
            "hook": {"start_time": 1.0, "end_time": 4.0, "text": "Hook text"}
          }
        }
      ]
    }
    """
    topics = smart_clipping.parse_llm_topics(sample_llm)
    assert len(topics) == 1
    assert topics[0].get("broll_items") == []


def test_process_segments_broll_validation():
    transcript_segments = [
        {"start": 0.0, "end": 5.0, "text": "intro text here"},
        {"start": 5.0, "end": 15.0, "text": "middle content discussing stats"},
        {"start": 15.0, "end": 20.0, "text": "outro text here"},
    ]
    raw_segments = [
        {
            "title": "Segment with Valid and Invalid B-roll",
            "start_time_ref": "(0s)",
            "start_text": "intro text",
            "end_text": "middle content",
            "score": 90,
            "broll_items": [
                {
                    "template_id": "stat_counter",
                    "start_offset": 1.0,
                    "duration": 3.0,
                    "data": {"target_number": "100"},
                },
                {
                    "template_id": "unknown_fx",
                    "start_offset": 1.0,
                    "duration": 3.0,
                    "data": {},
                },
                {
                    "template_id": "quote_card",
                    "start_offset": -0.5,
                    "duration": 2.0,
                    "data": {"quote": "hello"},
                },
                {
                    "template_id": "point_highlight",
                    "start_offset": 2.0,
                    "duration": 0.0,
                    "data": {"points": ["a"]},
                },
                {
                    "template_id": "point_highlight",
                    "start_offset": 2.0,
                    "duration": 2.0,
                    "data": "not-a-dict",
                },
                "not-a-dict-item",
            ],
        }
    ]

    result = process_segments(raw_segments, transcript_segments, min_duration=5, max_duration=20)
    segs = result.get("segments", [])
    assert len(segs) == 1
    brolls = segs[0].get("broll_items", [])
    assert len(brolls) == 1
    assert brolls[0]["template_id"] == "stat_counter"
    assert brolls[0]["duration"] == 3.0


def test_map_words_to_spliced_timeline():
    segments_to_splice = [(10.0, 20.0), (30.0, 40.0)]
    words = [
        {"word": "A", "start": 12.0, "end": 12.5},
        {"word": "B", "start": 25.0, "end": 26.0},  # Outside slices (dead air / skipped)
        {"word": "C", "start": 32.0, "end": 33.0},
    ]
    spliced = smart_clipping.map_words_to_spliced_timeline(segments_to_splice, words)
    assert len(spliced) == 2
    assert spliced[0]["word"] == "A"
    assert spliced[0]["start"] == 2.0  # 12.0 - 10.0
    assert spliced[1]["word"] == "C"
    assert spliced[1]["start"] == 12.0  # 10s (slice 1) + (32.0 - 30.0)
