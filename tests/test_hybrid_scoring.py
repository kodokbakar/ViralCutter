import pytest
from scripts.smart_clipping import (
    compute_hybrid_virality_score,
    parse_volumedetect_output,
)

def test_compute_hybrid_virality_score():
    # Normal case: text score 90, audio score 80
    # 0.7 * 90 + 0.3 * 80 = 63 + 24 = 87
    score = compute_hybrid_virality_score(text_score=90, audio_energy_score=80)
    assert score == 87

def test_compute_hybrid_virality_score_monotone_penalty():
    # Monotone case: text score 95, audio score 40
    # 0.7 * 95 + 0.3 * 40 = 66.5 + 12 = 78.5 -> 79
    score = compute_hybrid_virality_score(text_score=95, audio_energy_score=40)
    assert score in [78, 79]
    assert score < 95

def test_parse_volumedetect_output():
    sample_stderr = """
[Parsed_volumedetect_0 @ 0x55d7f1d2c0] n_samples: 192000
[Parsed_volumedetect_0 @ 0x55d7f1d2c0] mean_volume: -18.4 dB
[Parsed_volumedetect_0 @ 0x55d7f1d2c0] max_volume: -1.2 dB
[Parsed_volumedetect_0 @ 0x55d7f1d2c0] histogram_0db: 12
    """
    mean_vol, max_vol = parse_volumedetect_output(sample_stderr)
    assert mean_vol == pytest.approx(-18.4, abs=0.1)
    assert max_vol == pytest.approx(-1.2, abs=0.1)
