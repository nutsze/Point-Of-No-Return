"""Synthesise the original Ten Winters soundtrack with numpy.

Everything here is generated from scratch (sine/additive synthesis, filtered
noise); no recordings or third-party samples are used. Writes OGG files to
assets/audio/ via ffmpeg, falling back to WAV when ffmpeg is missing.

    python3 tools/make_audio.py
"""
from __future__ import annotations

import os
import shutil
import subprocess
import wave

import numpy as np

SR = 32000
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "assets", "audio")
rng = np.random.default_rng(2030)


def note(name: str) -> float:
    names = {"C": -9, "C#": -8, "Db": -8, "D": -7, "D#": -6, "Eb": -6, "E": -5, "F": -4,
             "F#": -3, "Gb": -3, "G": -2, "G#": -1, "Ab": -1, "A": 0, "A#": 1, "Bb": 1, "B": 2}
    pitch, octave = name[:-1], int(name[-1])
    return 440.0 * 2 ** ((names[pitch] + 12 * (octave - 4)) / 12)


def t_axis(sec: float) -> np.ndarray:
    return np.arange(int(sec * SR)) / SR


def fast_lowpass(x: np.ndarray, cutoff: float) -> np.ndarray:
    """FFT brick-ish low-pass with a smooth roll-off, for long buffers."""
    spec = np.fft.rfft(x)
    freqs = np.fft.rfftfreq(len(x), 1 / SR)
    spec *= 1 / (1 + (freqs / cutoff) ** 4)
    return np.fft.irfft(spec, len(x))


def env(n: int, attack: float, release: float) -> np.ndarray:
    e = np.ones(n)
    a, r = int(attack * SR), int(release * SR)
    if a:
        e[:a] = np.linspace(0, 1, a)
    if r:
        e[-r:] *= np.linspace(1, 0, r)
    return e


def pad(freqs: list[float], sec: float, bright: float = 0.35) -> np.ndarray:
    """Warm additive pad: a few harmonics per note, slow chorus detune."""
    t = t_axis(sec)
    out = np.zeros_like(t)
    for f in freqs:
        for k, amp in enumerate([1.0, bright, bright * 0.5, bright * 0.25], start=1):
            for det in (-0.0007, 0.0007):  # ~1 cent of chorus, slow gentle beating
                out += amp * np.sin(2 * np.pi * f * k * (1 + det) * t + rng.uniform(0, 6.28))
    return out / (len(freqs) * 6)


def bell(f: float, sec: float, decay: float = 2.5) -> np.ndarray:
    t = t_axis(sec)
    partials = [(1, 1.0), (2.76, 0.5), (5.4, 0.25), (8.9, 0.12)]
    out = sum(a * np.sin(2 * np.pi * f * r * t) * np.exp(-t * decay * r ** 0.5) for r, a in partials)
    return out * 0.5


def thump(sec: float = 0.6) -> np.ndarray:
    t = t_axis(sec)
    f = 55 * np.exp(-t * 6) + 38
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 7)


def place(buf: np.ndarray, clip: np.ndarray, at: float, gain: float = 1.0) -> None:
    i = int(at * SR)
    j = min(len(buf), i + len(clip))
    buf[i:j] += clip[: j - i] * gain


def loopify(x: np.ndarray, fade: float = 3.0) -> np.ndarray:
    """Crossfade the tail into the head so the file loops seamlessly."""
    n = int(fade * SR)
    head, tail = x[:n].copy(), x[-n:]
    ramp = np.linspace(0, 1, n)
    x = x[:-n].copy()
    x[:n] = head * ramp + tail * (1 - ramp)
    return x


def normalise(x: np.ndarray, peak: float = 0.8) -> np.ndarray:
    return x / (np.max(np.abs(x)) + 1e-9) * peak


def wind(sec: float, cutoff: float = 500) -> np.ndarray:
    t = t_axis(sec)
    noise = fast_lowpass(rng.standard_normal(len(t)), cutoff)
    gust = 0.55 + 0.45 * np.sin(2 * np.pi * t / 9.0) * np.sin(2 * np.pi * t / 23.0)
    return noise * gust


# ---------------------------------------------------------------- tracks --

def ambient() -> np.ndarray:
    """Cold, uneasy winter drone for ordinary scenes (D minor)."""
    sec = 50.0
    buf = pad([note("D2"), note("A2"), note("F3")], sec, bright=0.25) * 0.9
    buf += normalise(wind(sec), 0.25)
    for at, n in [(4, "A4"), (16, "F4"), (29, "D5"), (41, "E4")]:
        place(buf, bell(note(n), 6.0, decay=1.4), at, 0.18)
    buf *= 0.85 + 0.15 * np.sin(2 * np.pi * t_axis(sec) / 12.5)
    return normalise(loopify(buf), 0.55)


def tension() -> np.ndarray:
    """Heartbeat and a dissonant cluster, for arrests, war, searches."""
    sec = 32.0
    t = t_axis(sec)
    buf = pad([note("D2"), note("Eb3"), note("A2")], sec, bright=0.45) * 0.8
    trem = 0.6 + 0.4 * np.sin(2 * np.pi * 5.5 * t)
    buf += pad([note("D4"), note("Eb4")], sec, bright=0.2) * trem * 0.35
    beat = 60 / 64
    k = 0.0
    while k < sec - 1:
        place(buf, thump(), k, 0.9)
        place(buf, thump(), k + 0.28, 0.55)
        k += beat
    buf += normalise(wind(sec, 300), 0.15)
    return normalise(loopify(buf, 2.0), 0.6)


def grief() -> np.ndarray:
    """Slow, sparse minor piece for losses and the bitter endings."""
    sec = 48.0
    buf = pad([note("A2"), note("E3")], sec, bright=0.2) * 0.6
    melody = ["E5", "C5", "B4", "A4", "C5", "B4", "G4", "A4", "E4", "A4", "B4", "C5"]
    for i, n in enumerate(melody):
        place(buf, bell(note(n), 5.0, decay=0.9), 2.0 + i * 3.6, 0.3)
        place(buf, bell(note(n) / 2, 5.0, decay=1.2), 2.0 + i * 3.6, 0.12)
    buf += normalise(wind(sec, 250), 0.12)
    return normalise(loopify(buf), 0.55)


def victory() -> np.ndarray:
    """Hymn-like theme for the winning credits: dark start, opening into D major."""
    chords = [
        (["D3", "F3", "A3", "D4"], 6.0),   # Dm: still winter
        (["Bb2", "F3", "Bb3", "D4"], 6.0),
        (["G2", "D3", "G3", "Bb3"], 6.0),
        (["A2", "E3", "A3", "C#4"], 6.0),  # A major: the turn
        (["D3", "F#3", "A3", "D4"], 6.0),  # D major: spring
        (["B2", "F#3", "B3", "D4"], 6.0),
        (["G2", "D3", "G3", "B3"], 6.0),
        (["A2", "E3", "A3", "C#4"], 6.0),
        (["D3", "F#3", "A3", "D4", "F#4"], 10.0),
    ]
    total = sum(d for _, d in chords) + 2
    buf = np.zeros(int(total * SR))
    at = 0.0
    for i, (names, dur) in enumerate(chords):
        p = pad([note(n) for n in names], dur + 1.5, bright=0.3 + 0.05 * i)
        p *= env(len(p), 1.2, 1.5)
        place(buf, p, at, 0.6 + 0.06 * i)
        place(buf, thump(1.2) * 0.5, at, 0.5 if i >= 3 else 0.25)
        at += dur
    tune = [("A4", 0), ("D5", 1.5), ("C5", 3), ("A4", 4.5),
            ("Bb4", 6), ("A4", 7.5), ("F4", 9), ("D4", 10.5),
            ("G4", 12), ("A4", 13.5), ("Bb4", 15), ("D5", 16.5),
            ("C#5", 18), ("E5", 19.5), ("A5", 21),
            ("F#5", 24), ("E5", 25.5), ("D5", 27), ("A4", 28.5),
            ("B4", 30), ("D5", 31.5), ("F#5", 33),
            ("G5", 36), ("F#5", 37.5), ("E5", 39), ("D5", 40.5),
            ("E5", 42), ("F#5", 43.5), ("A5", 45), ("D6", 48)]
    for n, when in tune:
        place(buf, bell(note(n), 4.0, decay=1.1), when, 0.22)
    buf += normalise(wind(total, 300), 0.06) * np.linspace(1, 0, len(buf))
    buf *= env(len(buf), 2.0, 4.0)
    return normalise(buf, 0.75)


def click() -> np.ndarray:
    t = t_axis(0.08)
    return normalise(np.sin(2 * np.pi * 1800 * t) * np.exp(-t * 70) + 0.3 * rng.standard_normal(len(t)) * np.exp(-t * 120), 0.35)


# ----------------------------------------------------------------- output --

def write(name: str, data: np.ndarray) -> str:
    os.makedirs(OUT, exist_ok=True)
    wav_path = os.path.join(OUT, name + ".wav")
    pcm = (np.clip(data, -1, 1) * 32767).astype(np.int16)
    with wave.open(wav_path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())
    if name != "click" and shutil.which("ffmpeg"):
        ogg_path = os.path.join(OUT, name + ".ogg")
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", wav_path,
                        "-c:a", "libvorbis", "-q:a", "4", ogg_path], check=True)
        os.remove(wav_path)
        return ogg_path
    return wav_path


if __name__ == "__main__":
    for name, fn in [("ambient", ambient), ("tension", tension), ("grief", grief),
                     ("victory", victory), ("click", click)]:
        path = write(name, fn())
        print(name, "->", os.path.relpath(path, ROOT), os.path.getsize(path), "bytes")
