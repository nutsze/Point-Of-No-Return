"""Локально создаёт оригинальный эмбиент, сигналы UI и синтетическую русскую речь.

Для повторной генерации требуются eSpeak NG и FFmpeg. Готовые OGG-файлы входят
в релиз, поэтому при запуске игры синтезатор и сеть не нужны.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import wave
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from engine import ENDINGS, load_events

OUT = ROOT / "assets" / "audio"
VOICE = OUT / "voice"
RATE = 32000


def save_wav(path: Path, samples: np.ndarray) -> None:
    samples = np.clip(samples, -0.98, 0.98)
    channels = 1 if samples.ndim == 1 else samples.shape[1]
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(channels)
        handle.setsampwidth(2)
        handle.setframerate(RATE)
        handle.writeframes((samples * 32767).astype("<i2").tobytes())


def encode(path: Path, samples: np.ndarray, quality: int = 4) -> None:
    temporary = path.with_suffix(".wav")
    save_wav(temporary, samples)
    subprocess.run([
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(temporary),
        "-c:a", "libvorbis", "-q:a", str(quality), str(path),
    ], check=True)
    temporary.unlink()


def ambient() -> np.ndarray:
    duration = 48
    count = RATE * duration
    t = np.arange(count, dtype=np.float64) / RATE
    left = np.zeros(count, dtype=np.float64)
    right = np.zeros(count, dtype=np.float64)
    for frequency, amplitude, pan in [(73.416, 0.10, -0.2), (110.0, 0.055, 0.25), (146.832, 0.035, 0.0), (174.614, 0.018, 0.35)]:
        drift = 0.16 * np.sin(2 * np.pi * 0.025 * t + frequency)
        tone = amplitude * (0.72 + 0.28 * np.sin(2 * np.pi * 0.041 * t + pan)) * np.sin(2 * np.pi * frequency * t + drift)
        left += tone * (0.8 - pan * 0.25)
        right += tone * (0.8 + pan * 0.25)
    rng = np.random.default_rng(2030)
    spectrum = np.fft.rfft(rng.normal(0, 1, count))
    frequencies = np.fft.rfftfreq(count, 1 / RATE)
    spectrum *= 1 / np.sqrt(np.maximum(frequencies, 18))
    spectrum[frequencies > 1700] = 0
    wind = np.fft.irfft(spectrum, count)
    wind /= max(1e-9, np.max(np.abs(wind)))
    gust = 0.035 + 0.025 * (0.5 + 0.5 * np.sin(2 * np.pi * 0.063 * t))
    left += wind * gust
    right += np.roll(wind, 701) * gust
    for start, frequency in [(4.0, 293.665), (13.5, 349.228), (25.0, 220.0), (37.0, 261.626)]:
        index = int(start * RATE)
        length = min(int(7 * RATE), count - index)
        local = np.arange(length) / RATE
        bell = (np.sin(2 * np.pi * frequency * local) + 0.35 * np.sin(2 * np.pi * frequency * 2.01 * local))
        bell *= 0.06 * np.exp(-local * 0.85) * (1 - np.exp(-local * 35))
        left[index:index + length] += bell * 0.8
        right[index:index + length] += bell * 0.55
    # Короткое перекрёстное затухание делает зацикливание незаметным.
    fade = int(2 * RATE)
    ramp = np.linspace(0, 1, fade)[:, None]
    stereo = np.column_stack((left, right))
    stereo[:fade] *= ramp
    stereo[-fade:] *= ramp[::-1]
    return stereo


def signal(kind: str) -> np.ndarray:
    if kind == "choice":
        duration, frequency = 0.32, 92
    elif kind == "page":
        duration, frequency = 0.20, 168
    else:
        duration, frequency = 0.075, 420
    t = np.arange(int(RATE * duration)) / RATE
    envelope = np.exp(-t * (18 if kind == "hover" else 10)) * (1 - np.exp(-t * 180))
    sound = np.sin(2 * np.pi * frequency * t) + 0.25 * np.sin(2 * np.pi * frequency * 1.5 * t)
    return sound * envelope * (0.18 if kind != "hover" else 0.08)


def narration(text: str, target: Path) -> None:
    temporary = target.with_suffix(".raw.wav")
    subprocess.run([
        "espeak-ng", "-v", "ru", "-s", "139", "-p", "28", "-a", "150",
        "-w", str(temporary), text,
    ], check=True)
    subprocess.run([
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(temporary),
        "-af", "highpass=f=85,lowpass=f=4300,equalizer=f=260:t=q:w=1.1:g=-3,aecho=0.8:0.35:28:0.09,loudnorm=I=-20:TP=-2:LRA=7,apad=pad_dur=0.18",
        "-c:a", "libvorbis", "-q:a", "4", str(target),
    ], check=True)
    temporary.unlink()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--force", action="store_true", help="пересоздать даже неизменённые дорожки")
    args = parser.parse_args()
    VOICE.mkdir(parents=True, exist_ok=True)
    manifest_path = OUT / "credits.json"
    try:
        previous = json.loads(manifest_path.read_text(encoding="utf-8")).get("text_hashes", {})
    except (OSError, ValueError, json.JSONDecodeError):
        previous = {}
    if args.force or not (OUT / "ambient.ogg").is_file():
        encode(OUT / "ambient.ogg", ambient(), 5)
    for name in ("choice", "page", "hover"):
        if args.force or not (OUT / f"{name}.ogg").is_file():
            encode(OUT / f"{name}.ogg", signal(name), 4)
    manifest = {
        "music": {"file": "ambient.ogg", "method": "Оригинальная программная синтезированная композиция: низкий дрон, ветер и редкие колокольные тона."},
        "voice": {"engine": "eSpeak NG 1.51", "language": "ru", "notice": "Синтетическое озвучивание, не запись живого актёра."},
        "files": [],
        "text_hashes": {},
    }

    def add_narration(text: str, target: Path) -> None:
        relative = target.relative_to(OUT).as_posix()
        digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
        if args.force or previous.get(relative) != digest or not target.is_file():
            narration(text, target)
        manifest["files"].append(relative)
        manifest["text_hashes"][relative] = digest
        if len(manifest["files"]) % 20 == 0:
            print(f"Озвучивание: {len(manifest['files'])}/148", flush=True)

    for event in load_events():
        add_narration(f"{event['title']}. {event['description']}", VOICE / f"event_{event['id']}.ogg")
        for index, choice in enumerate(event["choices"]):
            add_narration(choice["result"], VOICE / f"result_{event['id']}_{index}.ogg")
    for ending_id, ending in ENDINGS.items():
        add_narration(f"{ending['title']}. {ending['text']}", VOICE / f"ending_{ending_id}.ogg")
    expected = set(manifest["files"])
    for stale in VOICE.glob("*.ogg"):
        if stale.relative_to(OUT).as_posix() not in expected:
            stale.unlink()
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Аудио готово: {len(manifest['files'])} голосовых дорожек, эмбиент и 3 сигнала.")


if __name__ == "__main__":
    main()
