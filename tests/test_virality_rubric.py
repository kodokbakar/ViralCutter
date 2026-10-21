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
