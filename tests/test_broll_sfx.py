import os
import wave
import pytest
from scripts import broll_sfx


def test_generate_all_sfx_creates_files(tmp_path):
    sfx_dir = str(tmp_path / "sfx")
    generated = broll_sfx.generate_all_sfx(output_dir=sfx_dir)

    expected_files = [
        "paper_slide.wav",
        "marker_sweep.wav",
        "soft_thud.wav",
        "tape_snap.wav",
        "page_flip.wav",
    ]

    for fname in expected_files:
        assert fname in generated
        fpath = generated[fname]
        assert os.path.exists(fpath)
        assert os.path.getsize(fpath) > 1000

        # Verify valid WAV format: 44.1kHz, 16-bit
        with wave.open(fpath, "rb") as wf:
            assert wf.getnchannels() == 1
            assert wf.getsampwidth() == 2
            assert wf.getframerate() == 44100
            frames = wf.getnframes()
            dur = frames / wf.getframerate()
            assert 0.15 <= dur <= 0.80  # Short, snappy punchy SFX


def test_get_sfx_for_template():
    # Template to SFX mapping check
    assert broll_sfx.get_sfx_name_for_template("stat_counter") == "paper_slide.wav"
    assert broll_sfx.get_sfx_name_for_template("vox_stat_counter") == "paper_slide.wav"
    assert broll_sfx.get_sfx_name_for_template("quote_card") == "marker_sweep.wav"
    assert broll_sfx.get_sfx_name_for_template("vox_quote_card") == "marker_sweep.wav"
    assert broll_sfx.get_sfx_name_for_template("point_highlight") == "tape_snap.wav"
    assert broll_sfx.get_sfx_name_for_template("vox_versus_split") == "soft_thud.wav"
    assert broll_sfx.get_sfx_name_for_template("vox_headline_punch") == "soft_thud.wav"
    assert broll_sfx.get_sfx_name_for_template("vox_explainer_def") == "page_flip.wav"
    assert broll_sfx.get_sfx_name_for_template("vox_bar_chart") == "page_flip.wav"
