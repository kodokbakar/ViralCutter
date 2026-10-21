import pytest
from scripts import virality_rubric

def test_compute_composite_score_standard():
    raw_dimensions = {
        "hook_strength": 9.0,
        "retention_flow": 8.5,
        "emotional_resonance": 8.0,
        "shareability": 9.0,
    }
    # audio_energy is on 0-100 scale, converted to 0-10 (e.g. 80.0 -> 8.0)
    score, rubric = virality_rubric.compute_composite_score(raw_dimensions, audio_energy=80.0)
    
    # 9.0*0.25 (2.25) + 8.5*0.25 (2.125) + 8.0*0.20 (1.6) + 9.0*0.15 (1.35) + 8.0*0.15 (1.2) = 8.525 * 10 = 85
    assert score == 85
    assert rubric["hook_strength"] == 9.0
    assert rubric["retention_flow"] == 8.5
    assert rubric["emotional_resonance"] == 8.0
    assert rubric["shareability"] == 9.0
    assert rubric["audio_dynamics"] == 8.0
    assert rubric["composite_score"] == 85
    assert "verdict" in rubric

def test_normalize_rubric_fallback():
    # When AI provides raw numeric score without rubric
    rubric = virality_rubric.normalize_rubric_dict(None, fallback_score=92)
    assert rubric["composite_score"] == 92
    assert rubric["hook_strength"] == 9.2
    assert rubric["retention_flow"] == 9.2

def test_clamping_bounds():
    # Out of range dimensions must be clamped between 1.0 and 10.0
    raw = {
        "hook_strength": 15.0,
        "retention_flow": -2.0,
        "emotional_resonance": 10.0,
        "shareability": 5.0,
    }
    score, rubric = virality_rubric.compute_composite_score(raw, audio_energy=120.0)
    assert rubric["hook_strength"] == 10.0
    assert rubric["retention_flow"] == 1.0
    assert rubric["audio_dynamics"] == 10.0
    assert 1 <= score <= 100

def test_normalize_rubric_existing():
    raw = {
        "hook_strength": 8.5,
        "retention_flow": 8.0,
        "emotional_resonance": 7.5,
        "shareability": 7.0,
        "audio_dynamics": 7.5,
        "composite_score": 80,
        "verdict": "Custom existing verdict",
    }
    rubric = virality_rubric.normalize_rubric_dict(raw, fallback_score=50)
    assert rubric["composite_score"] == 80
    assert rubric["hook_strength"] == 8.5
    assert rubric["verdict"] == "Custom existing verdict"

def test_compute_composite_score_custom_verdict_and_aliases():
    raw = {
        "hook": 9.5,
        "retention": 9.0,
        "emotion": 8.5,
        "share": 8.0,
    }
    score, rubric = virality_rubric.compute_composite_score(raw, audio_energy=85.0, user_verdict="Manual Override")
    assert rubric["verdict"] == "Manual Override"
    assert rubric["hook_strength"] == 9.5
    assert rubric["retention_flow"] == 9.0
    assert rubric["emotional_resonance"] == 8.5
    assert rubric["shareability"] == 8.0

def test_weights_and_dimensions_contract():
    assert sum(virality_rubric.WEIGHTS.values()) == pytest.approx(1.0)
    assert set(virality_rubric.WEIGHTS.keys()) == set(virality_rubric.DIMENSIONS.keys())

def test_process_segments_attaches_rubric_and_composite():
    from scripts.create_viral_segments import process_segments
    transcript = [{"start": 0.0, "end": 10.0, "text": "hello viral world"}]
    raw_segments = [
        {
            "title": "Test Viral Clip",
            "start_time_ref": "(0s)",
            "start_text": "hello viral",
            "end_text": "viral world",
            "hook_title": "JANGAN LAKUKAN INI!",
            "rubric": {
                "hook_strength": 9.0,
                "retention_flow": 9.0,
                "emotional_resonance": 8.0,
                "shareability": 8.5
            }
        }
    ]
    res = process_segments(raw_segments, transcript, min_duration=3, max_duration=15)
    seg = res["segments"][0]
    assert "rubric" in seg
    assert seg["score"] >= 80
    assert seg["rubric"]["hook_strength"] == 9.0
    assert seg["rubric"]["audio_dynamics"] > 0
def test_smart_clipping_pipeline_attaches_rubric_and_composite(tmp_path):
    from unittest.mock import patch
    from scripts.smart_clipping import run_smart_clipping_pipeline

    llm_payload = """```json
    {
      "topics": [
        {
          "title": "Smart Clip Rubric Test",
          "hook_title": "INI RAHASIA BESAR",
          "rationale": "High curiosity viral hook",
          "target_duration": 10.0,
          "score": 90,
          "rubric": {
            "hook_strength": 9.0,
            "retention_flow": 8.5,
            "emotional_resonance": 8.0,
            "shareability": 9.0
          },
          "segments": {
            "hook": {"start_time": 1.0, "end_time": 4.0, "text": "start hook"},
            "core": {"start_time": 4.0, "end_time": 8.0, "text": "core body"},
            "payoff": {"start_time": 8.0, "end_time": 11.0, "text": "final payoff"}
          }
        }
      ]
    }
    ```"""

    dummy_video = str(tmp_path / "input.mp4")
    with open(dummy_video, "w") as f:
        f.write("dummy")

    with patch("scripts.create_viral_segments.load_transcript", return_value=[{"start": 0.0, "end": 12.0, "text": "start hook core body final payoff"}]), \
         patch("scripts.create_viral_segments.preprocess_transcript_for_ai", return_value="start hook core body final payoff"), \
         patch("scripts.smart_clipping.query_ai_backend", return_value=llm_payload), \
         patch("scripts.smart_clipping.compute_audio_energy_score", return_value=80.0), \
         patch("scripts.smart_clipping.splice_topic_segments", return_value=str(tmp_path / "out.mp4")):

        res = run_smart_clipping_pipeline(
            project_folder=str(tmp_path),
            ai_backend="gemini",
            min_duration=5,
            max_duration=15,
        )

        assert "segments" in res
        assert len(res["segments"]) == 1
        seg = res["segments"][0]
        assert seg["score"] == 85
        assert seg["rubric"]["hook_strength"] == 9.0
        assert seg["rubric"]["retention_flow"] == 8.5
        assert seg["rubric"]["audio_dynamics"] == 8.0
        assert seg["rubric"]["composite_score"] == 85
        assert seg["hook_title"] == "INI RAHASIA BESAR"
