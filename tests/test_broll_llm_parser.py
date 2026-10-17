import pytest
from scripts import smart_clipping


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
