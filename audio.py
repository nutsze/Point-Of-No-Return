"""Локальное аудио игры: эмбиент, интерфейсные сигналы и синтетическая речь."""
from __future__ import annotations

import json
from pathlib import Path

import pygame

from engine import resource_root, save_directory


class AudioManager:
    def __init__(self) -> None:
        self.root = resource_root() / "assets" / "audio"
        self.settings_path = save_directory() / "settings.json"
        self.music_volume = 0.46
        self.sfx_volume = 0.62
        self.voice_volume = 0.78
        self.voice_enabled = True
        self.muted = False
        self.available = bool(pygame.mixer.get_init())
        self.music: pygame.mixer.Sound | None = None
        self.sounds: dict[str, pygame.mixer.Sound] = {}
        self.current_voice: pygame.mixer.Sound | None = None
        self._load_settings()
        if self.available:
            pygame.mixer.set_num_channels(10)
            self.music_channel = pygame.mixer.Channel(0)
            self.voice_channel = pygame.mixer.Channel(1)
            self.sfx_channel = pygame.mixer.Channel(2)
            self._load()

    def _load_settings(self) -> None:
        try:
            data = json.loads(self.settings_path.read_text(encoding="utf-8"))
            for key in ("music_volume", "sfx_volume", "voice_volume"):
                if key in data:
                    setattr(self, key, max(0.0, min(1.0, float(data[key]))))
            self.voice_enabled = bool(data.get("voice_enabled", self.voice_enabled))
            self.muted = bool(data.get("muted", self.muted))
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            pass

    def save_settings(self) -> None:
        data = {
            "music_volume": self.music_volume,
            "sfx_volume": self.sfx_volume,
            "voice_volume": self.voice_volume,
            "voice_enabled": self.voice_enabled,
            "muted": self.muted,
        }
        try:
            self.settings_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        except OSError:
            pass

    def _sound(self, relative: str) -> pygame.mixer.Sound | None:
        path = self.root / relative
        if not path.is_file():
            return None
        try:
            return pygame.mixer.Sound(str(path))
        except pygame.error:
            return None

    def _load(self) -> None:
        self.music = self._sound("ambient.ogg")
        for name in ("choice", "page", "hover"):
            sound = self._sound(f"{name}.ogg")
            if sound:
                self.sounds[name] = sound

    def start_music(self) -> None:
        if self.available and self.music and not self.music_channel.get_busy():
            self.music_channel.play(self.music, loops=-1, fade_ms=900)
        self.update()

    def update(self) -> None:
        if not self.available:
            return
        master = 0.0 if self.muted else 1.0
        duck = 0.32 if self.voice_channel.get_busy() else 1.0
        self.music_channel.set_volume(self.music_volume * master * duck)
        self.voice_channel.set_volume(self.voice_volume * master)
        self.sfx_channel.set_volume(self.sfx_volume * master)

    def play_sfx(self, name: str) -> None:
        if self.available and name in self.sounds:
            self.sfx_channel.play(self.sounds[name])

    def narrate(self, relative: str) -> None:
        if not self.available:
            return
        self.voice_channel.stop()
        self.current_voice = None
        if not self.voice_enabled:
            self.update()
            return
        sound = self._sound(f"voice/{relative}")
        if sound:
            self.current_voice = sound
            self.voice_channel.play(sound)
        self.update()

    def stop_voice(self) -> None:
        if self.available:
            self.voice_channel.stop()
        self.current_voice = None

    def toggle_mute(self) -> None:
        self.muted = not self.muted
        self.save_settings()
        self.update()

    def toggle_voice(self) -> None:
        self.voice_enabled = not self.voice_enabled
        if not self.voice_enabled:
            self.stop_voice()
        self.save_settings()
        self.update()

    def adjust(self, name: str, delta: float) -> None:
        attribute = f"{name}_volume"
        if attribute not in {"music_volume", "sfx_volume", "voice_volume"}:
            return
        setattr(self, attribute, round(max(0.0, min(1.0, getattr(self, attribute) + delta)), 2))
        self.save_settings()
        self.update()
        if name == "sfx":
            self.play_sfx("page")
