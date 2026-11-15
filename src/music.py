"""Copyright-free upbeat kids' backing track, synthesised from scratch (no downloads, no licences).

Marimba-style arpeggios + bouncy bass + soft kick/clap/hi-hat over a happy I-V-vi-IV progression.
Every seed gives a different key, tempo and pattern, so videos don't all sound the same.
"""
from __future__ import annotations

import random
import wave
from pathlib import Path

import numpy as np

SR = 44100
PROGRESSIONS = [[0, 7, 9, 5], [0, 5, 7, 5], [0, 9, 5, 7], [0, 4, 5, 7]]  # semitone offsets of chord roots
MAJOR = [0, 4, 7]
MINOR = [0, 3, 7]


def _note(freq: float, dur: float, kind: str) -> np.ndarray:
    t = np.arange(int(SR * dur)) / SR
    if kind == "marimba":
        wave_ = np.sin(2 * np.pi * freq * t) + 0.35 * np.sin(2 * np.pi * freq * 4 * t) * np.exp(-t * 30)
        env = np.exp(-t * 7)
    elif kind == "bass":
        wave_ = np.sin(2 * np.pi * freq * t) + 0.25 * np.sin(2 * np.pi * freq * 2 * t)
        env = np.minimum(1, t * 80) * np.exp(-t * 4)
    else:  # bell / sparkle
        wave_ = np.sin(2 * np.pi * freq * t) + 0.2 * np.sin(2 * np.pi * freq * 2.76 * t)
        env = np.exp(-t * 5)
    return (wave_ * env).astype(np.float32)


def _drum(kind: str, rnd: np.random.Generator) -> np.ndarray:
    t = np.arange(int(SR * 0.25)) / SR
    if kind == "kick":
        f = 110 * np.exp(-t * 18) + 45
        return (np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 14)).astype(np.float32)
    if kind == "clap":
        return (rnd.standard_normal(len(t)) * np.exp(-t * 28) * 0.6).astype(np.float32)
    return (rnd.standard_normal(len(t))[: int(SR * 0.04)] * np.exp(-t[: int(SR * 0.04)] * 90) * 0.25).astype(np.float32)


def _add(buf: np.ndarray, sig: np.ndarray, at: float, gain: float) -> None:
    i = int(at * SR)
    if i >= len(buf):
        return
    n = min(len(sig), len(buf) - i)
    buf[i:i + n] += sig[:n] * gain


def pick_bpm(seed: int, style: str = "happy") -> int:
    """Same seed + style -> same tempo (the video uses it to pulse on the beat)."""
    return random.Random(seed * 7 + (1 if style == "dance" else 0)).choice(
        [124, 126, 128] if style == "dance" else [100, 106, 112, 118])


def make_track(seconds: float, out: Path, seed: int = 0, style: str = "happy") -> Path:
    """style='happy' = bouncy nursery groove · style='dance' = four-on-the-floor kids party beat."""
    rnd = random.Random(seed)
    nrng = np.random.default_rng(seed)
    bpm = pick_bpm(seed, style)
    dance = style == "dance"
    beat = 60 / bpm
    key = rnd.choice([0, 2, 5, 7, 9])          # C, D, F, G, A major
    base = 261.63 * 2 ** (key / 12)            # tonic around middle C
    prog = rnd.choice(PROGRESSIONS)
    pattern = rnd.choice([[0, 1, 2, 1], [0, 2, 1, 2], [0, 1, 2, 3], [2, 1, 0, 1]])
    buf = np.zeros(int(SR * (seconds + 1)), dtype=np.float32)

    bar, t = 0, 0.0
    while t < seconds:
        root = prog[bar % 4]
        triad = MINOR if root == 9 else MAJOR
        chord = [base * 2 ** ((root + s) / 12) for s in triad] + [base * 2 ** ((root + 12) / 12)]
        for b in range(4):                                   # 4 beats per bar
            tb = t + b * beat
            if dance:   # party beat: kick on every beat, claps on 2 & 4, off-beat bass + hats, synth stabs
                _add(buf, _drum("kick", nrng), tb, 0.7)
                if b % 2 == 1:
                    _add(buf, _drum("clap", nrng), tb, 0.55)
                _add(buf, _drum("hat", nrng), tb + beat / 2, 0.7)
                _add(buf, _note(chord[0] / 2, beat * 0.45, "bass"), tb + beat / 2, 0.7)
                if b in (0, 2):
                    for nt in chord[:3]:
                        _add(buf, _note(nt, beat * 0.4, "marimba"), tb + beat * 0.75, 0.16)
                _add(buf, _note(chord[pattern[b % 4]] * 2, beat * 0.5, "bell"), tb, 0.12)
                continue
            _add(buf, _note(chord[0] / 2, beat * 0.9, "bass"), tb, 0.55)
            for e in range(2):                               # 8th-note marimba arpeggio
                _add(buf, _note(chord[pattern[(b * 2 + e) % 4]], beat, "marimba"), tb + e * beat / 2, 0.28)
            _add(buf, _drum("kick" if b % 2 == 0 else "clap", nrng), tb, 0.45)
            _add(buf, _drum("hat", nrng), tb + beat / 2, 0.5)
        if bar % 2 == 1:                                     # little sparkle every 2 bars
            _add(buf, _note(chord[2] * 2, beat * 2, "bell"), t + 3.5 * beat, 0.12)
        t += 4 * beat
        bar += 1

    buf = buf[: int(SR * seconds)]
    fade = int(SR * 1.5)
    buf[-fade:] *= np.linspace(1, 0, fade)
    buf[: int(SR * 0.3)] *= np.linspace(0, 1, int(SR * 0.3))
    peak = float(np.max(np.abs(buf))) or 1.0
    pcm = (buf / peak * 0.8 * 32767).astype(np.int16)
    with wave.open(str(out), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())
    return out
