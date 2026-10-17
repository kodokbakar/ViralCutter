import math
import os
import random
import struct
import wave
from typing import Dict, List, Optional

DEFAULT_SFX_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "assets",
    "sfx"
)

TEMPLATE_SFX_MAP: Dict[str, str] = {
    "stat_counter": "paper_slide.wav",
    "vox_stat_counter": "paper_slide.wav",
    "quote_card": "marker_sweep.wav",
    "vox_quote_card": "marker_sweep.wav",
    "point_highlight": "tape_snap.wav",
    "vox_point_list": "tape_snap.wav",
    "vox_versus_split": "soft_thud.wav",
    "vox_headline_punch": "soft_thud.wav",
    "vox_explainer_def": "page_flip.wav",
    "vox_bar_chart": "page_flip.wav",
}


def get_sfx_name_for_template(template_id: str) -> str:
    return TEMPLATE_SFX_MAP.get(str(template_id).strip(), "paper_slide.wav")


def get_sfx_path_for_template(template_id: str, sfx_dir: Optional[str] = None) -> str:
    target_dir = sfx_dir or DEFAULT_SFX_DIR
    filename = get_sfx_name_for_template(template_id)
    path = os.path.join(target_dir, filename)
    if not os.path.exists(path):
        ensure_sfx_assets(target_dir)
    return path


def _save_wave_16bit_mono(filepath: str, samples: List[float], sample_rate: int = 44100):
    os.makedirs(os.path.dirname(os.path.abspath(filepath)), exist_ok=True)
    with wave.open(filepath, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        # Clamp samples between -1.0 and 1.0, convert to signed 16-bit int
        packed = bytearray()
        for s in samples:
            clamped = max(-1.0, min(1.0, s))
            int_val = int(clamped * 32767.0)
            packed.extend(struct.pack("<h", int_val))
        wf.writeframes(packed)


def synthesize_paper_slide(sample_rate: int = 44100) -> List[float]:
    """Tactile paper slide / swoosh sound with bandpass-filtered noise."""
    duration = 0.35
    num_samples = int(duration * sample_rate)
    samples = []
    
    # Simple recursive IIR bandpass filter state
    b0, b1 = 0.0, 0.0
    for i in range(num_samples):
        t = i / sample_rate
        # Envelope: quick rise (50ms) and exponential decay
        if t < 0.05:
            env = t / 0.05
        else:
            env = math.exp(-7.5 * (t - 0.05))

        # Sweep center frequency from 800Hz to 1800Hz
        cf = 800.0 + 1000.0 * (t / duration)
        raw_noise = (random.random() * 2.0 - 1.0)
        
        # High-pass / band emphasis
        b0 = 0.85 * b0 + 0.15 * raw_noise
        b1 = 0.70 * b1 + 0.30 * b0
        
        carrier = math.sin(2.0 * math.pi * cf * t)
        val = (b0 * 0.7 + b1 * 0.3) * (0.6 + 0.4 * carrier) * env
        samples.append(val * 0.85)

    return samples


def synthesize_marker_sweep(sample_rate: int = 44100) -> List[float]:
    """Realistic chisel-tip marker squeak / friction sweep."""
    duration = 0.38
    num_samples = int(duration * sample_rate)
    samples = []

    phase = 0.0
    for i in range(num_samples):
        t = i / sample_rate
        # Envelope: trapezoid with gentle tail
        if t < 0.04:
            env = t / 0.04
        elif t < 0.30:
            env = 1.0
        else:
            env = max(0.0, 1.0 - (t - 0.30) / 0.08)

        # Chirp frequency sweeping down slightly with friction wobble (micro-flutter)
        flutter = math.sin(2.0 * math.pi * 32.0 * t) * 70.0
        freq = 2200.0 - (t / duration) * 500.0 + flutter
        phase += 2.0 * math.pi * freq / sample_rate

        sine_part = math.sin(phase)
        # Add paper texture friction
        friction_noise = (random.random() * 2.0 - 1.0) * 0.25

        val = (sine_part * 0.75 + friction_noise) * env
        samples.append(val * 0.75)

    return samples


def synthesize_soft_thud(sample_rate: int = 44100) -> List[float]:
    """Subtle punchy card impact / thud."""
    duration = 0.26
    num_samples = int(duration * sample_rate)
    samples = []

    phase = 0.0
    for i in range(num_samples):
        t = i / sample_rate
        # Fast exponential decay envelope
        env = math.exp(-12.0 * t)
        # Pitch drop from 95Hz to 38Hz
        freq = 38.0 + 57.0 * math.exp(-16.0 * t)
        phase += 2.0 * math.pi * freq / sample_rate

        bass = math.sin(phase)
        # Transient click at t < 0.012s
        click = (random.random() * 2.0 - 1.0) * math.exp(-250.0 * t) if t < 0.02 else 0.0

        val = (bass * 0.85 + click * 0.45) * env
        samples.append(val * 0.95)

    return samples


def synthesize_tape_snap(sample_rate: int = 44100) -> List[float]:
    """Snappy tape / sticker paper slap."""
    duration = 0.18
    num_samples = int(duration * sample_rate)
    samples = []

    b = 0.0
    for i in range(num_samples):
        t = i / sample_rate
        env = math.exp(-22.0 * t)
        raw_noise = (random.random() * 2.0 - 1.0)
        # High pass click
        b = 0.92 * b + 0.08 * raw_noise
        hp_click = raw_noise - b
        
        # Resonant pop around 1100Hz
        pop = math.sin(2.0 * math.pi * 1100.0 * t) * math.exp(-35.0 * t)
        val = (hp_click * 0.7 + pop * 0.3) * env
        samples.append(val * 0.85)

    return samples


def synthesize_page_flip(sample_rate: int = 44100) -> List[float]:
    """Quick flutter of two consecutive paper leaves turning."""
    duration = 0.32
    num_samples = int(duration * sample_rate)
    samples = []

    b = 0.0
    for i in range(num_samples):
        t = i / sample_rate
        # Double flutter envelope (t=0.02s and t=0.12s)
        env1 = math.exp(-24.0 * abs(t - 0.05)) if t < 0.14 else 0.0
        env2 = math.exp(-18.0 * abs(t - 0.16)) if t >= 0.10 else 0.0
        env = min(1.0, env1 + env2)

        raw_noise = (random.random() * 2.0 - 1.0)
        b = 0.80 * b + 0.20 * raw_noise
        tone = math.sin(2.0 * math.pi * (1400.0 - 600.0 * t) * t) * 0.25
        val = (b * 0.75 + tone) * env
        samples.append(val * 0.85)

    return samples


def generate_all_sfx(output_dir: Optional[str] = None) -> Dict[str, str]:
    target_dir = output_dir or DEFAULT_SFX_DIR
    os.makedirs(target_dir, exist_ok=True)

    generators = {
        "paper_slide.wav": synthesize_paper_slide,
        "marker_sweep.wav": synthesize_marker_sweep,
        "soft_thud.wav": synthesize_soft_thud,
        "tape_snap.wav": synthesize_tape_snap,
        "page_flip.wav": synthesize_page_flip,
    }

    out_paths = {}
    for filename, fn in generators.items():
        fpath = os.path.join(target_dir, filename)
        samples = fn(sample_rate=44100)
        _save_wave_16bit_mono(fpath, samples, sample_rate=44100)
        out_paths[filename] = fpath

    return out_paths


def ensure_sfx_assets(target_dir: Optional[str] = None):
    """Ensures SFX files exist in target directory; generates them if missing."""
    target = target_dir or DEFAULT_SFX_DIR
    expected = [
        "paper_slide.wav",
        "marker_sweep.wav",
        "soft_thud.wav",
        "tape_snap.wav",
        "page_flip.wav",
    ]
    missing = any(not os.path.exists(os.path.join(target, f)) for f in expected)
    if missing:
        generate_all_sfx(target)
