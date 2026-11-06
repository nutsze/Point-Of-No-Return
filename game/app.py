"""Цикл приложения и переходы между экранами."""
from __future__ import annotations

import argparse
import json
import os
import random
import webbrowser
from pathlib import Path

import pygame

from audio import AudioManager
from engine import (
    advance, apply_choice, event_by_id, load_events, load_game,
    new_state, resource_root, save_game,
)
from media import MediaLibrary
from ui import BASE_H, BASE_W, WHITE, Button, Canvas

from .constants import FPS
from .screens.archive import ArchiveScreens
from .screens.base import BaseScreens
from .screens.credits import RollCreditsScreen
from .screens.story import StoryScreens
from .screens.system import SystemScreens


class Game(BaseScreens, StoryScreens, ArchiveScreens, SystemScreens, RollCreditsScreen):
    def __init__(self, capture: str | None = None) -> None:
        os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
        pygame.mixer.pre_init(44100, -16, 2, 512)
        pygame.init()
        flags = 0 if capture else pygame.RESIZABLE
        self.windowed_size = (1280, 720)
        self.fullscreen = False
        self.window = pygame.display.set_mode(self.windowed_size, flags)
        pygame.display.set_caption("2030: Точка невозврата")
        self.canvas = Canvas(self.window)
        self.clock = pygame.time.Clock()
        self.media = MediaLibrary()
        self.audio = AudioManager()
        self.audio.start_music()
        self.events = load_events()
        self.data = {"people": json.loads((resource_root() / "data" / "people.json").read_text(encoding="utf-8"))}
        self.state = new_state()
        self.screen = "menu"
        self.params: dict = {}
        self.return_screen = "menu"
        self.return_params: dict = {}
        self.running = True
        self.focus = 0
        self.scroll = 0
        self.roll_offset = 0
        self.buttons: list[Button] = []
        self.notice = ""
        self.notice_until = 0
        self.capture = capture
        rng = random.Random(2030)
        self.particles = [
            [rng.uniform(0, BASE_W), rng.uniform(0, BASE_H), rng.uniform(8, 25), rng.uniform(-9, 9), rng.uniform(0.8, 2.2)]
            for _ in range(95)
        ]

    def current_event(self) -> dict:
        return event_by_id(self.events, self.state["event_id"])

    def go(self, screen: str, **params) -> None:
        self.screen = screen
        self.params = params
        self.focus = 0
        self.scroll = 0
        if screen == "roll":
            self.roll_offset = 0
        self.audio.stop_voice()
        self._screen_voice()

    def _screen_voice(self) -> None:
        if self.screen == "event" and self.params.get("phase") == "narration":
            self.audio.narrate(f"event_{self.state['event_id']}")
        elif self.screen == "result":
            self.audio.narrate(f"result_{self.state['event_id']}_{self.params.get('choice_index', 0)}")
        elif self.screen == "ending":
            self.audio.narrate(f"ending_{self.state['ending_id']}")

    def start_new(self) -> None:
        self.state = new_state()
        self.go("briefing")

    def continue_game(self) -> None:
        state = load_game()
        if state is None:
            self.flash("СОХРАНЕНИЕ НЕ НАЙДЕНО ИЛИ ПОВРЕЖДЕНО")
            return
        self.state = state
        if state["completed"]:
            self.go("ending")
        elif state.get("pending_event"):
            self.go("result", choice_index=state["history"][-1]["choice_index"])
        else:
            self.go("event", phase="narration")

    def choose(self, index: int) -> None:
        if self.screen != "event" or self.params.get("phase") != "choice":
            return
        apply_choice(self.state, self.current_event(), index)
        save_game(self.state)
        self.audio.play_sfx("choice")
        self.go("result", choice_index=index)

    def next_chapter(self) -> None:
        if not self.state["completed"]:
            advance(self.state, self.events)
        save_game(self.state)
        self.audio.play_sfx("page")
        self.go("ending" if self.state["completed"] else "event", phase="narration")

    def pause(self) -> None:
        self.return_screen = self.screen
        self.return_params = dict(self.params)
        self.go("pause")

    def manual_save(self) -> None:
        self.flash("ИГРА СОХРАНЕНА" if save_game(self.state) else "НЕ УДАЛОСЬ СОХРАНИТЬ ИГРУ")

    def flash(self, text: str) -> None:
        self.notice = text
        self.notice_until = pygame.time.get_ticks() + 2200

    def scroll_limit(self) -> int:
        if self.screen == "timeline":
            chapters = {event["chapter"] for event in self.events if event["documentary"]}
            return max(0, len(chapters) * 190 - 452)
        if self.screen == "media":
            rows = (len(self.media.all()) + 2) // 3
            return max(0, rows * 312 - 590)
        if self.screen == "credits":
            return max(0, len(self.media.all()) * 82 - 390)
        return 0

    def open_url(self, url: str) -> None:
        if url.startswith(("https://", "http://")):
            webbrowser.open(url)
        self.audio.play_sfx("page")

    def toggle_fullscreen(self) -> None:
        self.fullscreen = not self.fullscreen
        if self.fullscreen:
            self.windowed_size = self.window.get_size()
            self.window = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
        else:
            self.window = pygame.display.set_mode(self.windowed_size, pygame.RESIZABLE)
        self.canvas = Canvas(self.window)
        self.media.clear_cache()

    def add_button(self, rect, text, action, style="ghost", enabled=True, font_size=22, align="left") -> None:
        self.buttons.append(Button(pygame.Rect(rect), text, action, style, enabled, font_size, align))

    def quit(self) -> None:
        self.running = False

    def handle_key(self, event) -> None:
        key = event.key
        if key == pygame.K_F11:
            self.toggle_fullscreen()
            return
        if key == pygame.K_m:
            self.audio.toggle_mute()
            return
        if key == pygame.K_v:
            self.audio.toggle_voice()
            return
        if key == pygame.K_s and event.mod & pygame.KMOD_CTRL:
            self.manual_save()
            return
        if self.screen in {"timeline", "media", "credits"} and key in {pygame.K_PAGEUP, pygame.K_PAGEDOWN}:
            self.scroll = max(0, min(self.scroll_limit(), self.scroll + (-240 if key == pygame.K_PAGEUP else 240)))
            return
        if self.screen == "roll" and key in {pygame.K_SPACE, pygame.K_RETURN}:
            self.go("menu")
            return
        enabled = [button for button in self.buttons if button.enabled]
        if enabled and key in {pygame.K_UP, pygame.K_TAB, pygame.K_DOWN}:
            direction = -1 if key == pygame.K_UP else 1
            self.focus = (self.focus + direction) % len(enabled)
            return
        if enabled and key in {pygame.K_RETURN, pygame.K_SPACE}:
            enabled[self.focus % len(enabled)].action()
            return
        if self.screen == "event" and self.params.get("phase") == "choice" and key in {pygame.K_1, pygame.K_2, pygame.K_3}:
            self.choose(key - pygame.K_1)
            return
        if key != pygame.K_ESCAPE:
            return
        if self.screen in {"event", "result"}:
            self.pause()
        elif self.screen == "pause":
            self.go(self.return_screen, **self.return_params)
        elif self.screen in {"settings", "help", "timeline"}:
            self.go(self.params.get("return_to", "menu"))
        elif self.screen == "roll":
            self.go("ending")
        elif self.screen != "menu":
            self.go("menu")

    def update(self, dt: float) -> None:
        for particle in self.particles:
            particle[1] += particle[2] * dt
            particle[0] += particle[3] * dt
            if particle[1] > BASE_H + 5:
                particle[1] = -5
            if particle[0] < -5:
                particle[0] = BASE_W + 5
            elif particle[0] > BASE_W + 5:
                particle[0] = -5
        if self.screen == "roll":
            self.roll_offset = min(self.roll_limit(), self.roll_offset + 62 * dt)
        self.audio.update()

    def _handle_input(self) -> None:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.quit()
            elif event.type == pygame.KEYDOWN:
                self.handle_key(event)
            elif event.type == pygame.VIDEORESIZE and not self.fullscreen:
                size = (max(800, event.w), max(450, event.h))
                self.windowed_size = size
                self.window = pygame.display.set_mode(size, pygame.RESIZABLE)
                self.canvas = Canvas(self.window)
                self.media.clear_cache()
            elif event.type == pygame.MOUSEMOTION:
                for button in self.buttons:
                    button.hovered = button.enabled and button.rect.collidepoint(self.canvas.logical_point(event.pos))
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                point = self.canvas.logical_point(event.pos)
                for button in self.buttons:
                    if button.enabled and button.rect.collidepoint(point):
                        self.audio.play_sfx("page")
                        button.action()
                        break
            elif event.type == pygame.MOUSEWHEEL and self.screen in {"timeline", "media", "credits"}:
                self.scroll = max(0, min(self.scroll_limit(), self.scroll - event.y * 55))

    def _draw_frame(self) -> None:
        self.buttons = []
        getattr(self, f"screen_{self.screen}")()
        mouse = self.canvas.logical_point(pygame.mouse.get_pos())
        visible = [button for button in self.buttons if button.rect.bottom > 72 and button.rect.top < 860]
        for button in visible:
            button.draw(self.canvas, mouse)
        enabled = [button for button in visible if button.enabled]
        if enabled:
            button = enabled[self.focus % len(enabled)]
            self.canvas.rect(button.rect, None, 2, WHITE, 120)
        if self.notice and pygame.time.get_ticks() < self.notice_until:
            self.canvas.rect((420, 810, 760, 52), (10, 10, 10), alpha=245)
            self.canvas.text(self.notice, (440, 824), 18, WHITE, max_width=720, align="center")

    def run(self) -> None:
        while self.running:
            dt = min(0.1, self.clock.tick(FPS) / 1000)
            self._handle_input()
            self.update(dt)
            self._draw_frame()
            pygame.display.flip()
        self.audio.stop_voice()
        pygame.quit()

    def capture_frame(self, filename: str) -> None:
        self._draw_frame()
        path = Path(filename)
        path.parent.mkdir(parents=True, exist_ok=True)
        pygame.image.save(self.window, str(path))


def main() -> None:
    parser = argparse.ArgumentParser(description="2030: Точка невозврата")
    parser.add_argument("--capture", help="Сохранить один кадр в PNG для технической проверки")
    parser.add_argument("--screen", default="menu", help="Стартовый экран для --capture")
    parser.add_argument("--size", default="1280x720", help="Размер окна для --capture")
    args = parser.parse_args()
    if args.capture:
        os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    game = Game(args.capture)
    if args.capture:
        width, height = (int(value) for value in args.size.lower().split("x", 1))
        game.window = pygame.display.set_mode((width, height))
        game.canvas = Canvas(game.window)
        game.go(args.screen, phase="narration")
        game.capture_frame(args.capture)
        pygame.quit()
    else:
        game.run()


if __name__ == "__main__":
    main()
