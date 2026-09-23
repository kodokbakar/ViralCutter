import json
import pytest
from scripts.smart_clipping import (
    parse_narrative_topics,
    build_narrative_prompt,
)

SAMPLE_LLM_RESPONSE_WITH_SCORE = """
{
  "topics": [
    {
      "title": "Kunci Sukses Usaha",
      "rationale": "Hook sangat kuat dan langsung ke inti.",
      "target_duration": 40.0,
      "score": 94,
      "segments": {
        "hook": {"start_time": 2.0, "end_time": 5.0, "text": "Pernahkah kamu rugi?"},
        "core": {"start_time": 10.0, "end_time": 25.0, "text": "Kuncinya ada di manajemen arus kas."},
        "payoff": {"start_time": 30.0, "end_time": 40.0, "text": "Terapkan ini sekarang juga."}
      }
    }
  ]
}
"""

def test_parse_narrative_topics_extracts_score():
    topics = parse_narrative_topics(SAMPLE_LLM_RESPONSE_WITH_SCORE)
    assert len(topics) == 1
    assert topics[0]["score"] == 94
    assert topics[0]["title"] == "Kunci Sukses Usaha"

def test_build_narrative_prompt_includes_score():
    prompt = build_narrative_prompt("sample transcript", target_min=20, target_max=60, num_topics=2)
    assert '"score"' in prompt or '"virality_score"' in prompt
