import pytest
from scripts.smart_clipping import (
    build_narrative_prompt,
    parse_narrative_topics,
    snap_narrative_topic_segments,
)

SAMPLE_LLM_RESPONSE = """
```json
{
  "topics": [
    {
      "title": "Rahasia Sukses Produktif",
      "rationale": "Hook kuat tentang bangun pagi dilanjutkan tips praktis dan kesimpulan mengejutkan.",
      "target_duration": 45.0,
      "segments": {
        "hook": {
          "start_time": 1.2,
          "end_time": 4.5,
          "text": "Kenapa kamu selalu bangun kesiangan?"
        },
        "core": {
          "start_time": 10.0,
          "end_time": 30.0,
          "text": "Trik utama adalah meletakkan alarm di luar kamar..."
        },
        "payoff": {
          "start_time": 50.0,
          "end_time": 60.0,
          "text": "Hasilnya, energimu meningkat 2 kali lipat."
        }
      }
    }
  ]
}
```
"""

SAMPLE_WORDS = [
    {"word": "Kenapa", "start": 1.15, "end": 1.45, "score": 0.95},
    {"word": "kesiangan", "start": 4.10, "end": 4.60, "score": 0.92},
    {"word": "Trik", "start": 9.95, "end": 10.20, "score": 0.91},
    {"word": "kamar", "start": 29.80, "end": 30.15, "score": 0.93},
    {"word": "Hasilnya", "start": 49.90, "end": 50.30, "score": 0.94},
    {"word": "lipat", "start": 59.85, "end": 60.25, "score": 0.96},
]

def test_build_narrative_prompt():
    prompt = build_narrative_prompt("transcript sample", target_min=15, target_max=60, num_topics=2)
    assert "Hook" in prompt
    assert "Pembahasan Inti" in prompt or "core" in prompt.lower()
    assert "Payoff" in prompt
    assert "transcript sample" in prompt

def test_parse_narrative_topics():
    topics = parse_narrative_topics(SAMPLE_LLM_RESPONSE)
    assert len(topics) == 1
    t = topics[0]
    assert t["title"] == "Rahasia Sukses Produktif"
    assert "hook" in t["segments"]
    assert "core" in t["segments"]
    assert "payoff" in t["segments"]
    assert t["segments"]["hook"]["start_time"] == 1.2
    assert t["segments"]["payoff"]["end_time"] == 60.0

def test_snap_narrative_topic_segments():
    topics = parse_narrative_topics(SAMPLE_LLM_RESPONSE)
    snapped_topic = snap_narrative_topic_segments(topics[0], SAMPLE_WORDS, margin=0.05)
    hook = snapped_topic["segments"]["hook"]
    core = snapped_topic["segments"]["core"]
    payoff = snapped_topic["segments"]["payoff"]

    # Hook: start near 1.15 -> snapped 1.10; end near 4.60 -> snapped 4.65
    assert hook["snapped_start"] == pytest.approx(1.10, abs=0.02)
    assert hook["snapped_end"] == pytest.approx(4.65, abs=0.02)

    # Core: start near 9.95 -> snapped 9.90; end near 30.15 -> snapped 30.20
    assert core["snapped_start"] == pytest.approx(9.90, abs=0.02)
    assert core["snapped_end"] == pytest.approx(30.20, abs=0.02)

    # Payoff: start near 49.90 -> snapped 49.85; end near 60.25 -> snapped 60.30
    assert payoff["snapped_start"] == pytest.approx(49.85, abs=0.02)
    assert payoff["snapped_end"] == pytest.approx(60.30, abs=0.02)
