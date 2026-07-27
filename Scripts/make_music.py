"""Generates CH_Editor/music.wav: an original 64-bar Heavy Darksynth Action Loop.

Designed specifically for Cargo Hunters: Save Editor (Hackerman Edition).
Pure aggressive, dark, driving industrial darksynth action - NO high melodic gedudel!

Features:
- 64 Bars total (~1.8 minutes / 108 seconds) for an epic, long, non-repetitive loop.
- Heavy 16th-note Darksynth Octave Bass with filter drive.
- Rhythmic Heavy Power Stabs (Root + 5th) on accent steps & syncopations.
- Dark Cyber Arpeggiator providing constant 16th tension & filter sweeps.
- Heavy Industrial Drums (Sub Kick, Snappy Snare, Gated Hats, Fill Rolls).

Output matches app requirements: 16-bit PCM, mono, 22050 Hz, 100% seamlessly loopable.

    py Scripts/make_music.py
"""
from __future__ import annotations

import math
import random
import struct
import wave
from pathlib import Path

SAMPLE_RATE = 22050
BPM = 140
BEATS_PER_BAR = 4
STEPS_PER_BAR = 16                      # 16th notes
OUT = Path(__file__).resolve().parents[1] / "CH_Editor" / "music.wav"

SECONDS_PER_STEP = (60.0 / BPM) / 4.0
SAMPLES_PER_STEP = int(SAMPLE_RATE * SECONDS_PER_STEP)

_NOTE_INDEX = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}


def freq(note: str | None) -> float:
    """'A4' -> 440.0. Accepts sharps as 'G#5'. None is a rest."""
    if not note:
        return 0.0
    name, rest = note[0].upper(), note[1:]
    semitone = _NOTE_INDEX[name]
    if rest.startswith("#"):
        semitone += 1
        rest = rest[1:]
    midi = (int(rest) + 1) * 12 + semitone
    return 440.0 * (2.0 ** ((midi - 69) / 12.0))


# --- Composition: 64-Bar Heavy Darksynth Action Loop ----------------------------------

# Bass Patterns
BASS_PATTERN_A = ["D1", "D2", "D1", "D2", "D1", "D2", "F1", "D2", "D1", "D2", "D1", "D2", "G1", "D2", "G#1", "D2"]
BASS_PATTERN_B = ["A#0", "A#1", "A#0", "A#1", "A#0", "A#1", "D1", "A#1", "A#0", "A#1", "A#0", "A#1", "C1", "D1", "E1", "F1"]
BASS_PATTERN_C = ["C1", "C2", "C1", "C2", "C1", "C2", "E1", "C2", "C1", "C2", "C1", "C2", "D1", "E1", "F1", "G1"]
BASS_PATTERN_D = ["F1", "F2", "F1", "F2", "F1", "F2", "A1", "F2", "F1", "F2", "F1", "F2", "G1", "G1", "A1", "A1"]

BASS_BARS = [
    # Bars 1-8: Intro Build
    BASS_PATTERN_A, BASS_PATTERN_A, BASS_PATTERN_B, BASS_PATTERN_C,
    BASS_PATTERN_A, BASS_PATTERN_A, BASS_PATTERN_D, BASS_PATTERN_C,
    # Bars 9-24: Section A (Full Drive)
    BASS_PATTERN_A, BASS_PATTERN_A, BASS_PATTERN_B, BASS_PATTERN_C,
    BASS_PATTERN_A, BASS_PATTERN_A, BASS_PATTERN_D, BASS_PATTERN_C,
    BASS_PATTERN_A, BASS_PATTERN_A, BASS_PATTERN_B, BASS_PATTERN_C,
    BASS_PATTERN_A, BASS_PATTERN_A, BASS_PATTERN_D, BASS_PATTERN_C,
    # Bars 25-40: Section B (Tension Modulation)
    BASS_PATTERN_B, BASS_PATTERN_B, BASS_PATTERN_C, BASS_PATTERN_C,
    BASS_PATTERN_A, BASS_PATTERN_A, BASS_PATTERN_D, BASS_PATTERN_C,
    BASS_PATTERN_B, BASS_PATTERN_B, BASS_PATTERN_C, BASS_PATTERN_C,
    BASS_PATTERN_A, BASS_PATTERN_A, BASS_PATTERN_D, BASS_PATTERN_C,
    # Bars 41-56: Breakdown & Heavy Pulse
    BASS_PATTERN_A, BASS_PATTERN_A, BASS_PATTERN_B, BASS_PATTERN_C,
    BASS_PATTERN_A, BASS_PATTERN_A, BASS_PATTERN_D, BASS_PATTERN_C,
    BASS_PATTERN_A, BASS_PATTERN_A, BASS_PATTERN_B, BASS_PATTERN_C,
    BASS_PATTERN_A, BASS_PATTERN_A, BASS_PATTERN_D, BASS_PATTERN_C,
    # Bars 57-64: Climax Drop
    BASS_PATTERN_A, BASS_PATTERN_A, BASS_PATTERN_B, BASS_PATTERN_C,
    BASS_PATTERN_A, BASS_PATTERN_A, BASS_PATTERN_D, BASS_PATTERN_C,
]
BASS_STEPS = [step for bar in BASS_BARS for step in bar]

# Dark Arpeggiator Patterns
ARP_PATTERN_A = ["D3", "F3", "D3", "F3", "A3", "F3", "D3", "F3", "D3", "F3", "A3", "F3", "D3", "F3", "G#3", "G3"]
ARP_PATTERN_B = ["A#2", "D3", "A#2", "D3", "F3", "D3", "A#2", "D3", "A#2", "D3", "F3", "D3", "A#2", "C3", "D3", "E3"]
ARP_PATTERN_C = ["C3", "E3", "C3", "E3", "G3", "E3", "C3", "E3", "C3", "E3", "G3", "E3", "D3", "E3", "F3", "G3"]
ARP_PATTERN_D = ["F3", "A3", "F3", "A3", "C4", "A3", "F3", "A3", "F3", "A3", "C4", "A3", "G3", "G3", "A3", "A3"]

ARP_BARS = [
    # Bars 1-8
    ARP_PATTERN_A, ARP_PATTERN_A, ARP_PATTERN_B, ARP_PATTERN_C,
    ARP_PATTERN_A, ARP_PATTERN_A, ARP_PATTERN_D, ARP_PATTERN_C,
] * 8
ARP_STEPS = [step for bar in ARP_BARS for step in bar]

# Heavy Power Stabs (Root + 5th Power Chords - Pure Industrial Bite)
STAB_HIT_1 = [("D3", "A3"), None, None, ("D3", "A3"), None, None, ("F3", "C4"), None, ("D3", "A3"), None, None, ("G3", "D4"), None, ("G#3", "D#4"), None, None]
STAB_HIT_2 = [("D3", "A3"), None, None, ("D3", "A3"), None, None, ("F3", "C4"), None, ("D3", "A3"), None, None, ("F3", "C4"), None, ("E3", "B3"), None, None]
STAB_HIT_3 = [("A#2", "F3"), None, None, ("A#2", "F3"), None, None, ("D3", "A3"), None, ("A#2", "F3"), None, None, ("C3", "G3"), None, ("D3", "A3"), None, None]
STAB_HIT_4 = [("C3", "G3"), None, None, ("C3", "G3"), None, None, ("E3", "B3"), None, ("C3", "G3"), None, None, ("D3", "A3"), None, ("E3", "B3"), None, None]

STAB_DOUBLE_1 = [("D3", "A3"), ("D3", "A3"), None, ("D3", "A3"), None, ("F3", "C4"), None, ("D3", "A3"), ("D3", "A3"), None, ("D3", "A3"), None, ("G3", "D4"), None, ("G#3", "D#4"), None]
STAB_DOUBLE_2 = [("D3", "A3"), ("D3", "A3"), None, ("D3", "A3"), None, ("F3", "C4"), None, ("D3", "A3"), ("D3", "A3"), None, ("F3", "C4"), None, ("E3", "B3"), None, ("D3", "A3"), None]
STAB_DOUBLE_3 = [("A#2", "F3"), ("A#2", "F3"), None, ("A#2", "F3"), None, ("D3", "A3"), None, ("A#2", "F3"), ("A#2", "F3"), None, ("C3", "G3"), None, ("D3", "A3"), None, ("E3", "B3"), None]
STAB_DOUBLE_4 = [("C3", "G3"), ("C3", "G3"), None, ("C3", "G3"), None, ("E3", "B3"), None, ("C3", "G3"), ("C3", "G3"), None, ("D3", "A3"), None, ("E3", "B3"), None, ("F3", "C4"), None]

STAB_BARS = [
    # Bars 1-8: Intro (No stabs)
    *([[None] * 16] * 8),
    # Bars 9-24: Section A (Single Stabs)
    STAB_HIT_1, STAB_HIT_2, STAB_HIT_3, STAB_HIT_4,
    STAB_HIT_1, STAB_HIT_2, STAB_HIT_3, STAB_HIT_4,
    STAB_HIT_1, STAB_HIT_2, STAB_HIT_3, STAB_HIT_4,
    STAB_HIT_1, STAB_HIT_2, STAB_HIT_3, STAB_HIT_4,
    # Bars 25-40: Section B (Mixed Heavy Stabs)
    STAB_DOUBLE_1, STAB_HIT_2, STAB_DOUBLE_3, STAB_HIT_4,
    STAB_DOUBLE_1, STAB_HIT_2, STAB_DOUBLE_3, STAB_HIT_4,
    STAB_DOUBLE_1, STAB_HIT_2, STAB_DOUBLE_3, STAB_HIT_4,
    STAB_DOUBLE_1, STAB_HIT_2, STAB_DOUBLE_3, STAB_HIT_4,
    # Bars 41-56: Breakdown
    STAB_HIT_1, STAB_HIT_2, STAB_HIT_3, STAB_HIT_4,
    STAB_HIT_1, STAB_HIT_2, STAB_HIT_3, STAB_HIT_4,
    STAB_DOUBLE_1, STAB_DOUBLE_2, STAB_DOUBLE_3, STAB_DOUBLE_4,
    STAB_DOUBLE_1, STAB_DOUBLE_2, STAB_DOUBLE_3, STAB_DOUBLE_4,
    # Bars 57-64: Climax Drop
    STAB_DOUBLE_1, STAB_DOUBLE_2, STAB_DOUBLE_3, STAB_DOUBLE_4,
    STAB_DOUBLE_1, STAB_DOUBLE_2, STAB_DOUBLE_3, STAB_DOUBLE_4,
]
STAB_STEPS = [step for bar in STAB_BARS for step in bar]

TOTAL_STEPS = len(BASS_STEPS)
TOTAL_SAMPLES = TOTAL_STEPS * SAMPLES_PER_STEP


def env_exp(pos: int, length: int, attack: int, decay: float) -> float:
    if pos < attack:
        return pos / attack
    t = (pos - attack) / max(1, length - attack)
    return math.exp(-decay * t)


def lowpass_filter(signal: list[float], cutoff_ratio: float) -> list[float]:
    """Lowpass filter for analogue warmth and synth punch."""
    alpha = min(1.0, max(0.01, cutoff_ratio))
    out = [0.0] * len(signal)
    prev = 0.0
    for i, s in enumerate(signal):
        prev += alpha * (s - prev)
        out[i] = prev
    return out


def distort(signal: list[float], drive: float, level: float) -> list[float]:
    """Soft clipping distortion (tanh). Gives instruments raw industrial bite."""
    return [math.tanh(v * drive) * level for v in signal]


def render_synth_bass() -> list[float]:
    """Driving 16th-note octave saw/square bass."""
    out = [0.0] * TOTAL_SAMPLES
    attack = int(0.001 * SAMPLE_RATE)
    for i, note in enumerate(BASS_STEPS):
        if not note:
            continue
        base_f = freq(note)
        start = i * SAMPLES_PER_STEP
        length = int(SAMPLES_PER_STEP * 0.85)
        
        phase_saw = 0.0
        phase_sq = 0.0
        for n in range(length):
            if start + n >= TOTAL_SAMPLES:
                break
            phase_saw += base_f / SAMPLE_RATE
            saw = 2.0 * (phase_saw % 1.0) - 1.0
            
            phase_sq += (base_f * 0.5) / SAMPLE_RATE
            sq = 1.0 if (phase_sq % 1.0) < 0.5 else -1.0
            
            e = env_exp(n, length, attack, decay=3.2)
            out[start + n] += (saw * 0.65 + sq * 0.40) * e * 0.50

    return distort(lowpass_filter(out, cutoff_ratio=0.45), drive=2.2, level=0.75)


def render_arp() -> list[float]:
    """Constant 16th dark synth arp providing high tension."""
    out = [0.0] * TOTAL_SAMPLES
    attack = int(0.001 * SAMPLE_RATE)
    for i, note in enumerate(ARP_STEPS):
        if not note or (i // 16 < 2):  # Enters after bar 2
            continue
        base_f = freq(note)
        start = i * SAMPLES_PER_STEP
        length = int(SAMPLES_PER_STEP * 0.65)
        
        phase = 0.0
        for n in range(length):
            if start + n >= TOTAL_SAMPLES:
                break
            phase += base_f / SAMPLE_RATE
            pulse = 1.0 if (phase % 1.0) < 0.30 else -1.0
            e = env_exp(n, length, attack, decay=5.5)
            out[start + n] += pulse * e * 0.22

    return lowpass_filter(out, cutoff_ratio=0.55)


def render_power_stabs() -> list[float]:
    """Heavy industrial power stabs (Root + 5th). Pure punch, 0% gedudel."""
    out = [0.0] * TOTAL_SAMPLES
    attack = int(0.002 * SAMPLE_RATE)
    
    for i, pair in enumerate(STAB_STEPS):
        if not pair:
            continue
        n1, n2 = pair
        f1, f2 = freq(n1), freq(n2)
        start = i * SAMPLES_PER_STEP
        length = int(SAMPLES_PER_STEP * 1.8)
        
        phase1, phase2 = 0.0, 0.0
        for n in range(length):
            if start + n >= TOTAL_SAMPLES:
                break
            phase1 += f1 / SAMPLE_RATE
            phase2 += f2 / SAMPLE_RATE
            
            s1 = 1.0 if (phase1 % 1.0) < 0.5 else -1.0
            s2 = 2.0 * (phase2 % 1.0) - 1.0
            
            e = env_exp(n, length, attack, decay=4.0)
            out[start + n] += (s1 + s2) * 0.5 * e * 0.45

    return distort(out, drive=3.5, level=0.60)


def render_drums() -> list[float]:
    """Heavy Industrial Action Drums (Sub Kick, Heavy Snare, Gated Hats, Fills)."""
    rng = random.Random(20260727)
    out = [0.0] * TOTAL_SAMPLES

    def kick(start: int):
        length = int(0.14 * SAMPLE_RATE)
        phase = 0.0
        for n in range(length):
            if start + n >= TOTAL_SAMPLES:
                break
            t = n / length
            f = 150.0 * (2.718 ** (-4.5 * t)) + 36.0  # Swept sub thud
            phase += f / SAMPLE_RATE
            out[start + n] += math.sin(2 * math.pi * phase) * 0.95 * (1.0 - t) ** 1.6

    def snare(start: int, fill: bool = False):
        length = int((0.20 if fill else 0.16) * SAMPLE_RATE)
        phase = 0.0
        vol = 0.75 if fill else 0.65
        for n in range(length):
            if start + n >= TOTAL_SAMPLES:
                break
            t = n / length
            phase += 210.0 / SAMPLE_RATE
            body = math.sin(2 * math.pi * phase) * 0.40
            noise = rng.uniform(-1.0, 1.0) * 0.70
            out[start + n] += (noise + body) * (1.0 - t) ** 1.8 * vol

    def hat(start: int, open_hat: bool):
        length = int((0.05 if open_hat else 0.025) * SAMPLE_RATE)
        last = rng.uniform(-1.0, 1.0)
        vol = 0.22 if open_hat else 0.12
        for n in range(length):
            if start + n >= TOTAL_SAMPLES:
                break
            white = rng.uniform(-1.0, 1.0)
            value, last = white - last, white
            out[start + n] += value * vol * (1.0 - n / length) ** 2.0

    for step in range(TOTAL_STEPS):
        bar = step // 16
        in_bar = step % 16
        start = step * SAMPLES_PER_STEP

        # Hats on every 16th note (after bar 1)
        if bar >= 1:
            hat(start, open_hat=(in_bar % 4 == 2))

        # Drums enter after bar 1
        if bar >= 1:
            # Kick on 0, 4, 8, 12 + syncopated accents
            if in_bar in (0, 4, 8, 12):
                kick(start)
            elif in_bar in (10, 14) and bar % 2 == 1:
                kick(start)  # Syncopated double kick

            # Snare on 4 and 12 (plus drum fills at bar ends)
            if in_bar in (4, 12):
                snare(start)
            elif in_bar >= 12 and (bar + 1) % 4 == 0:
                # 16th snare roll fill at end of every 4 bars
                snare(start, fill=True)

    return out


def build() -> list[float]:
    bass = render_synth_bass()
    arp = render_arp()
    stabs = render_power_stabs()
    drums = render_drums()

    # Mix tracks together
    mix = [0.0] * TOTAL_SAMPLES
    for i in range(TOTAL_SAMPLES):
        mix[i] = bass[i] * 0.85 + arp[i] * 0.45 + stabs[i] * 0.70 + drums[i] * 0.70

    # Peak normalization
    peak = max(abs(v) for v in mix) or 1.0
    mix = [v / peak * 0.90 for v in mix]

    # Seamless loop crossfade (4ms at start & end)
    edge = int(0.004 * SAMPLE_RATE)
    for n in range(edge):
        ramp = n / edge
        mix[n] *= ramp
        mix[-1 - n] *= ramp

    return mix


def main() -> None:
    samples = build()
    frames = b"".join(struct.pack("<h", int(max(-1.0, min(1.0, v)) * 32767)) for v in samples)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(OUT), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SAMPLE_RATE)
        w.writeframes(frames)
    print(f"Successfully generated {OUT}")
    print(f"  {TOTAL_STEPS // STEPS_PER_BAR} bars at {BPM} BPM Heavy 64-Bar Darksynth Action Loop")
    print(f"  {TOTAL_SAMPLES / SAMPLE_RATE:.1f}s loop ({TOTAL_SAMPLES / SAMPLE_RATE / 60.0:.2f} min), {OUT.stat().st_size / 1024:.0f} KB, {SAMPLE_RATE} Hz 16-bit mono")


if __name__ == "__main__":
    main()
