from __future__ import annotations

import os
import random
import sys
import traceback
import webbrowser
from functools import partial

import pygame

from audio import AudioManager
from engine import (
    APP_NAME, ENDINGS, advance, apply_choice, final_ending, has_save,
    load_events, load_game, new_state, save_game,
)
from media import MediaLibrary
from ui import (
    BASE_H, BASE_W, BLACK, FAINT, LINE, MUTED, RED, TEXT, WHITE,
    Button, Canvas, draw_empty_archive, draw_scrollbar,
)

FPS = 30
ALT_WARNING = "АЛЬТЕРНАТИВНАЯ ИСТОРИЯ — СОБЫТИЯ РАЗВИВАЮТСЯ ИНАЧЕ, ЧЕМ В ДЕЙСТВИТЕЛЬНОСТИ"


class Game:
    def __init__(self) -> None:
        pygame.mixer.pre_init(48000, -16, 2, 512)
        pygame.init()
        pygame.display.set_caption(APP_NAME)
        initial_size = (
            int(os.environ.get("POR_WIDTH", "1280")),
            int(os.environ.get("POR_HEIGHT", "720")),
        )
        self.window = pygame.display.set_mode(initial_size, pygame.RESIZABLE)
        self.canvas = Canvas(self.window)
        self.media = MediaLibrary()
        self.audio = AudioManager()
        self.audio.start_music()
        self.events = load_events()
        self.state = new_state()
        self.running = True
        self.fullscreen = False
        self.screen = "menu"
        self.params: dict = {}
        self.buttons: list[Button] = []
        self.focus_index = 0
        self.scroll = 0
        self.max_scroll = 0
        self.return_screen = "menu"
        self.return_params: dict = {}
        self.notice = ""
        self.last_hover = -1
        rng = random.Random(2030)
        self.particles = [
            [rng.uniform(0, BASE_W), rng.uniform(0, BASE_H), rng.uniform(12, 48), rng.uniform(-9, 9), rng.uniform(0.7, 2.2)]
            for _ in range(74)
        ]
        self.capture_path = os.environ.get("POR_CAPTURE")
        self.capture_frame = int(os.environ.get("POR_CAPTURE_FRAME", "4"))
        self.frame = 0

    def go(self, screen: str, **params) -> None:
        self.audio.stop_voice()
        self.screen = screen
        self.params = params
        self.buttons = []
        self.focus_index = 0
        self.scroll = 0
        self.max_scroll = 0
        self.notice = ""
        self.last_hover = -1
        self._screen_voice()

    def _screen_voice(self) -> None:
        if self.screen == "event" and self.params.get("phase", "narration") == "narration":
            self.audio.narrate(f"event_{self.current_event()['id']}.ogg")
        elif self.screen == "result":
            event = self.events[self.state["event_index"]]
            self.audio.narrate(f"result_{event['id']}_{self.params.get('choice_index', 0)}.ogg")
        elif self.screen == "ending":
            ending_id = self.state.get("ending_id") or final_ending(self.state)
            self.audio.narrate(f"ending_{ending_id}.ogg")

    def start_new(self) -> None:
        self.state = new_state()
        self.go("briefing")

    def continue_game(self) -> None:
        loaded = load_game()
        if loaded is None:
            self.notice = "Сохранение не найдено или повреждено."
            return
        self.state = loaded
        self.go("ending" if self.state.get("completed") else "event", phase="narration")

    def current_event(self) -> dict:
        return self.events[self.state["event_index"]]

    def choose(self, choice_index: int) -> None:
        event = self.current_event()
        apply_choice(self.state, event, choice_index)
        save_game(self.state)
        self.audio.play_sfx("choice")
        self.go("result", choice_index=choice_index)

    def next_chapter(self) -> None:
        if self.state["completed"]:
            self.go("ending")
            return
        advance(self.state, self.events)
        save_game(self.state)
        self.audio.play_sfx("page")
        self.go("ending" if self.state["completed"] else "event", phase="narration")

    def manual_save(self) -> None:
        save_game(self.state)
        self.notice = "Игра сохранена локально."

    def open_url(self, url: str) -> None:
        if url.startswith("https://"):
            webbrowser.open(url, new=2)

    def toggle_fullscreen(self) -> None:
        self.fullscreen = not self.fullscreen
        if self.fullscreen:
            info = pygame.display.Info()
            self.window = pygame.display.set_mode((info.current_w, info.current_h), pygame.FULLSCREEN)
        else:
            self.window = pygame.display.set_mode((1280, 720), pygame.RESIZABLE)
        self.canvas.update(self.window)

    def pause(self) -> None:
        self.return_screen = self.screen
        self.return_params = dict(self.params)
        self.go("pause")

    def quit(self) -> None:
        self.running = False

    def add_button(self, rect, label, action, style="ghost", enabled=True, font_size=24, align="left") -> None:
        self.buttons.append(Button(pygame.Rect(rect), label, action, style, enabled, font_size, align))

    def handle_key(self, event: pygame.event.Event) -> None:
        if event.key == pygame.K_F11:
            self.toggle_fullscreen()
            return
        if event.key == pygame.K_ESCAPE:
            self.handle_escape()
            return
        if event.key == pygame.K_m:
            self.audio.toggle_mute()
            return
        if event.key == pygame.K_v:
            self.audio.toggle_voice()
            return
        if event.key == pygame.K_s and event.mod & pygame.KMOD_CTRL:
            if self.screen not in {"menu", "credits", "media", "media_detail", "timeline", "timeline_detail", "people", "help", "settings"}:
                self.manual_save()
            return
        if self.screen == "event" and self.params.get("phase") == "choice" and event.key in {pygame.K_1, pygame.K_2, pygame.K_3}:
            self.choose(event.key - pygame.K_1)
            return
        enabled = [i for i, button in enumerate(self.buttons) if button.enabled]
        if not enabled:
            return
        if event.key in {pygame.K_DOWN, pygame.K_TAB, pygame.K_RIGHT}:
            current = enabled.index(self.focus_index) if self.focus_index in enabled else -1
            self.focus_index = enabled[(current + 1) % len(enabled)]
        elif event.key in {pygame.K_UP, pygame.K_LEFT}:
            current = enabled.index(self.focus_index) if self.focus_index in enabled else 0
            self.focus_index = enabled[(current - 1) % len(enabled)]
        elif event.key in {pygame.K_RETURN, pygame.K_SPACE}:
            if 0 <= self.focus_index < len(self.buttons):
                button = self.buttons[self.focus_index]
                if button.enabled:
                    button.action()
        elif event.key == pygame.K_PAGEUP:
            self.scroll = max(0, self.scroll - 500)
        elif event.key == pygame.K_PAGEDOWN:
            self.scroll = min(self.max_scroll, self.scroll + 500)

    def handle_escape(self) -> None:
        if self.screen in {"event", "result"}:
            self.pause()
        elif self.screen == "pause":
            self.go(self.return_screen, **self.return_params)
        elif self.screen == "timeline_detail":
            self.go("timeline", return_to=self.params.get("origin", "menu"))
        elif self.screen == "media_detail":
            self.go("media")
        elif self.screen != "menu":
            self.go(self.params.get("return_to", "menu"))

    def update_particles(self, dt: float) -> None:
        for particle in self.particles:
            particle[1] += particle[2] * dt
            particle[0] += particle[3] * dt
            if particle[1] > BASE_H + 8:
                particle[1] = -8
            if particle[0] < -8:
                particle[0] = BASE_W + 8
            elif particle[0] > BASE_W + 8:
                particle[0] = -8

    def run(self) -> None:
        while self.running:
            dt = min(0.1, self.clock.tick(FPS) / 1000) if hasattr(self, "clock") else 1 / FPS
            if not hasattr(self, "clock"):
                self.clock = pygame.time.Clock()
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                elif event.type == pygame.VIDEORESIZE and not self.fullscreen:
                    self.window = pygame.display.set_mode((max(800, event.w), max(450, event.h)), pygame.RESIZABLE)
                    self.canvas.update(self.window)
                elif event.type == pygame.KEYDOWN:
                    self.handle_key(event)
                elif event.type == pygame.MOUSEWHEEL:
                    self.scroll = max(0, min(self.max_scroll, self.scroll - event.y * 65))
                elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    mouse = self.canvas.logical_pos(event.pos)
                    for index, button in enumerate(self.buttons):
                        if button.enabled and button.rect.collidepoint(mouse):
                            self.focus_index = index
                            button.action()
                            break
            self.update_particles(dt)
            self.buttons = []
            screen_method = getattr(self, f"screen_{self.screen}", self.screen_menu)
            screen_method()
            mouse = self.canvas.logical_pos(pygame.mouse.get_pos())
            hover = -1
            for index, button in enumerate(self.buttons):
                if button.enabled and button.rect.collidepoint(mouse):
                    hover = index
                clip = None
                if self.screen == "timeline" and button.label == "Читать":
                    clip = (35, 140, 1530, 650)
                elif self.screen == "credits" and button.label in {"Оригинал", "Лицензия"}:
                    clip = (35, 135, 1530, 670)
                self.canvas.clip(clip)
                button.draw(self.canvas, mouse, selected=index == self.focus_index)
            self.canvas.clip()
            if hover >= 0 and hover != self.last_hover:
                self.audio.play_sfx("hover")
            self.last_hover = hover
            if self.notice:
                self.canvas.overlay(225, (490, 810, 620, 48))
                self.canvas.text(self.notice, (500, 822), 18, WHITE, max_width=600, align="center")
            self.audio.update()
            pygame.display.flip()
            self.frame += 1
            if self.capture_path and self.frame >= self.capture_frame:
                pygame.image.save(self.window, self.capture_path)
                self.running = False
        self.audio.stop_voice()
        pygame.quit()

    @property
    def clock(self) -> pygame.time.Clock:
        if not hasattr(self, "_clock"):
            self._clock = pygame.time.Clock()
        return self._clock

    def background(self, photo_id: str | None = None, dark: int = 25) -> None:
        if photo_id and self.media.get(photo_id):
            image = self.media.scene_surface(photo_id, self.window.get_size(), "cover")
            self.window.blit(image, (0, 0))
            if dark:
                self.canvas.overlay(dark, (0, 0, BASE_W, BASE_H))
        else:
            self.canvas.fill(BLACK)
            if photo_id:
                draw_empty_archive(self.canvas)

    def snow(self, alpha: int = 95) -> None:
        for x, y, _, _, radius in self.particles:
            self.canvas.circle((x, y), radius, WHITE, alpha)

    def header(self, section: str = "") -> None:
        self.canvas.text("2030 / ТОЧКА НЕВОЗВРАТА", (48, 31), 19, WHITE, bold=True)
        if section:
            self.canvas.text(section.upper(), (950, 33), 16, MUTED, max_width=600, align="right")
        self.canvas.line((48, 72), (1552, 72), LINE, 1, 80)

    def alternative_tag(self) -> None:
        if self.state["alternative_history"]:
            self.canvas.text(ALT_WARNING, (50, 88), 15, RED, bold=True, max_width=1450)

    def caption(self, photo_id: str) -> None:
        self.canvas.text(self.media.caption(photo_id), (48, 875), 11, MUTED, max_width=1500)

    def screen_menu(self) -> None:
        self.background("kremlin_spasskaya", 20)
        self.canvas.gradient((0, 0, 960, 900), 215, 30)
        self.snow(80)
        self.canvas.text("2030", (70, 126), 132, WHITE, bold=True)
        self.canvas.text("ТОЧКА\nНЕВОЗВРАТА", (76, 267), 62, WHITE, max_width=700, bold=True, line_gap=0)
        self.canvas.text("Документальная политическая визуальная новелла", (80, 432), 23, MUTED, max_width=600)
        self.canvas.line((80, 482), (490, 482), WHITE, 1, 100)
        entries = [
            ("НОВАЯ ИСТОРИЯ", self.start_new, True),
            ("ПРОДОЛЖИТЬ", self.continue_game, has_save()),
            ("ХРОНОЛОГИЯ", partial(self.go, "timeline"), True),
            ("МЕДИАТЕКА", partial(self.go, "media"), True),
            ("АВТОРЫ И ИСТОЧНИКИ", partial(self.go, "credits"), True),
            ("НАСТРОЙКИ", partial(self.go, "settings"), True),
        ]
        for index, (label, action, enabled) in enumerate(entries):
            self.add_button((82, 518 + index * 51, 450, 45), label, action, "menu", enabled, 25)
        self.add_button((1320, 822, 230, 44), "ВЫХОД", self.quit, "ghost", font_size=19, align="right")
        self.caption("kremlin_spasskaya")

    def screen_briefing(self) -> None:
        self.background("navalny_2020", 65)
        self.canvas.gradient((0, 0, 1120, 900), 235, 45)
        self.snow(65)
        self.header("Август 2020 / учредительное совещание")
        self.canvas.text("ГРАЖДАНСКИЙ СОВЕТ", (70, 150), 50, WHITE, max_width=850, bold=True)
        self.canvas.text("ВАША РОЛЬ — ВЫМЫШЛЕННАЯ", (74, 225), 16, MUTED, bold=True)
        body = (
            "Вы — координатор независимой общественной инициативы. Реальные политики и события "
            "образуют документальный фон, но вашего совета и принимаемых вами решений в действительности не было.\n\n"
            "К 2030 году нужно построить устойчивую общенациональную коалицию, сохранив людей и внутреннее доверие. "
            "Последствия решений не показываются числами: они проявляются в дальнейшей истории и её финале."
        )
        self.canvas.text(body, (74, 278), 26, TEXT, max_width=760, line_gap=9)
        self.canvas.text("После первого решения вся ветка получает постоянную пометку «АЛЬТЕРНАТИВНАЯ ИСТОРИЯ».", (74, 610), 19, MUTED, max_width=750)
        self.add_button((76, 735, 380, 58), "НАЧАТЬ ИСТОРИЮ", partial(self.go, "event", phase="narration"), "primary", font_size=26)
        self.add_button((76, 812, 220, 42), "В МЕНЮ", partial(self.go, "menu"), font_size=18)
        self.caption("navalny_2020")

    def screen_event(self) -> None:
        event = self.current_event()
        phase = self.params.get("phase", "narration")
        self.background(event["photo"], 15 if phase == "narration" else 75)
        self.snow(90)
        self.header(f"Глава {self.state['event_index'] + 1} из {len(self.events)} / {event['date']}")
        self.alternative_tag()
        if phase == "choice":
            self.canvas.overlay(70)
            self.canvas.text(event["title"].upper(), (160, 132), 35, WHITE, max_width=1280, bold=True, align="center")
            self.canvas.text("ВЫБЕРИТЕ ДАЛЬНЕЙШИЙ ХОД", (500, 207), 16, MUTED, max_width=600, align="center")
            for index, choice in enumerate(event["choices"]):
                self.add_button((245, 280 + index * 153, 1110, 122), choice["text"], partial(self.choose, index), "choice", font_size=33, align="center")
            self.canvas.text("1 / 2 / 3 — ВЫБРАТЬ    ESC — ПАУЗА", (500, 800), 16, MUTED, max_width=600, align="center")
        else:
            self.canvas.gradient((0, 330, 1600, 570), 0, 250)
            title_end = self.canvas.text(event["title"].upper(), (64, 477), 44, WHITE, max_width=1450, bold=True, line_gap=2)
            label = "ДОКУМЕНТАЛЬНОЕ СОБЫТИЕ" if event["documentary"] else "ВЫМЫШЛЕННАЯ ГЛАВА"
            self.canvas.text(label, (68, title_end + 8), 14, MUTED, bold=True)
            body_end = self.canvas.text(event["description"], (68, title_end + 43), 23, TEXT, max_width=1450, line_gap=5, max_lines=4)
            forces_y = min(746, body_end + 10)
            self.canvas.text("Участники: " + " · ".join(event["forces"]), (68, forces_y), 15, MUTED, max_width=1130, max_lines=2)
            if event["documentary"]:
                self.canvas.text(event["source_name"], (68, 803), 13, FAINT, max_width=1060)
            self.add_button((1240, 801, 290, 52), "ДАЛЕЕ", partial(self.go, "event", phase="choice"), "primary", font_size=24, align="right")
        self.caption(event["photo"])

    def screen_result(self) -> None:
        event = self.events[self.state["event_index"]]
        choice = event["choices"][self.params.get("choice_index", 0)]
        self.background(event["photo"], 45)
        self.snow(75)
        self.header("Последствие решения")
        self.canvas.text(ALT_WARNING, (50, 88), 15, RED, bold=True, max_width=1450)
        self.canvas.gradient((0, 330, 1600, 570), 0, 250)
        title_end = self.canvas.text(choice["text"].upper(), (66, 495), 42, WHITE, max_width=1450, bold=True)
        self.canvas.text(choice["result"], (70, title_end + 34), 27, TEXT, max_width=1400, line_gap=8, max_lines=4)
        self.add_button((1080, 790, 450, 58), "СЛЕДУЮЩАЯ ГЛАВА" if not self.state["completed"] else "УВИДЕТЬ ФИНАЛ", self.next_chapter, "primary", font_size=25, align="right")
        self.caption(event["photo"])

    def screen_ending(self) -> None:
        ending_id = self.state.get("ending_id") or final_ending(self.state)
        ending = ENDINGS[ending_id]
        self.background("kremlin_spasskaya", 65)
        self.snow(80)
        self.header("20 августа 2030 / финал")
        self.canvas.text(ALT_WARNING + " / НЕ ПРОГНОЗ", (50, 88), 15, RED, bold=True, max_width=1450)
        self.canvas.gradient((0, 250, 1600, 650), 0, 250)
        self.canvas.text(ending["subtitle"].upper(), (68, 394), 17, MUTED, bold=True)
        self.canvas.text(ending["title"], (64, 438), 64, WHITE, max_width=1450, bold=True)
        self.canvas.text(ending["text"], (70, 552), 26, TEXT, max_width=1370, line_gap=8, max_lines=4)
        self.add_button((72, 780, 360, 56), "НОВАЯ ИСТОРИЯ", self.start_new, "primary", font_size=24)
        self.add_button((474, 780, 300, 56), "ГЛАВНОЕ МЕНЮ", partial(self.go, "menu"), font_size=22)
        self.add_button((1190, 780, 340, 56), "ХРОНОЛОГИЯ", partial(self.go, "timeline", return_to="ending"), font_size=22, align="right")
        self.caption("kremlin_spasskaya")

    def screen_pause(self) -> None:
        self.background("kremlin_spasskaya", 175)
        self.header("Пауза")
        self.canvas.text("ПАУЗА", (550, 170), 58, WHITE, max_width=500, bold=True, align="center")
        entries = [
            ("ПРОДОЛЖИТЬ", partial(self.go, self.return_screen, **self.return_params)),
            ("СОХРАНИТЬ", self.manual_save),
            ("НАСТРОЙКИ", partial(self.go, "settings", return_to="pause")),
            ("ПРАВИЛА И УПРАВЛЕНИЕ", partial(self.go, "help", return_to="pause")),
            ("ГЛАВНОЕ МЕНЮ", partial(self.go, "menu")),
        ]
        for index, (label, action) in enumerate(entries):
            self.add_button((510, 286 + index * 83, 580, 62), label, action, "primary" if index == 0 else "ghost", font_size=27, align="center")
        self.add_button((620, 748, 360, 50), "ВЫХОД ИЗ ИГРЫ", self.quit, font_size=19, align="center")

    def screen_timeline(self) -> None:
        self.background("kremlin_spasskaya", 205)
        self.header("Хронология / документ и альтернатива")
        self.canvas.text("ХРОНОЛОГИЯ 2020–2030", (48, 94), 35, WHITE, bold=True)
        self.add_button((1370, 91, 180, 42), "НАЗАД", partial(self.go, self.params.get("return_to", "menu")), font_size=18, align="right")
        viewport = (35, 140, 1530, 650)
        row_height, gap = 94, 12
        content_height = len(self.events) * (row_height + gap)
        self.max_scroll = max(0, content_height - viewport[3])
        self.scroll = min(self.scroll, self.max_scroll)
        self.canvas.clip(viewport)
        for index, event in enumerate(self.events):
            y = viewport[1] + index * (row_height + gap) - self.scroll
            if y + row_height < viewport[1] or y > viewport[1] + viewport[3]:
                continue
            accent = WHITE if event["documentary"] else RED
            self.canvas.line((52, y + row_height), (1510, y + row_height), LINE, 1, 70)
            self.canvas.text(event["date"].upper(), (56, y + 12), 15, accent, bold=True)
            self.canvas.text("ДОКУМЕНТ" if event["documentary"] else "АЛЬТЕРНАТИВА", (56, y + 48), 12, MUTED)
            self.canvas.text(event["title"], (340, y + 13), 27, TEXT, max_width=970, bold=True)
            self.canvas.text(" · ".join(event["forces"]), (340, y + 55), 14, MUTED, max_width=980, max_lines=1)
            self.add_button((1350, y + 20, 160, 50), "Читать", partial(self.go, "timeline_detail", event_index=index, origin=self.params.get("return_to", "menu")), font_size=19, align="right")
        self.canvas.clip()
        draw_scrollbar(self.canvas, (1540, viewport[1], 4, viewport[3]), self.scroll, content_height)
        self.canvas.text("Колесо мыши / Page Up / Page Down", (48, 824), 14, FAINT)

    def screen_timeline_detail(self) -> None:
        event = self.events[self.params.get("event_index", 0)]
        self.background(event["photo"], 55)
        self.snow(65)
        self.header("Архивная карточка")
        self.canvas.text("ДОКУМЕНТАЛЬНОЕ СОБЫТИЕ" if event["documentary"] else ALT_WARNING, (50, 88), 15, RED if not event["documentary"] else MUTED, bold=True, max_width=1450)
        self.canvas.gradient((0, 290, 1600, 610), 0, 250)
        self.canvas.text(event["date"].upper(), (66, 402), 16, MUTED, bold=True)
        title_end = self.canvas.text(event["title"].upper(), (64, 444), 45, WHITE, max_width=1450, bold=True)
        body_end = self.canvas.text(event["description"], (68, title_end + 27), 24, TEXT, max_width=1440, line_gap=6, max_lines=4)
        self.canvas.text("Участники: " + " · ".join(event["forces"]), (68, min(734, body_end + 12)), 15, MUTED, max_width=1100, max_lines=2)
        if event["documentary"]:
            self.add_button((68, 801, 280, 50), "ОТКРЫТЬ ИСТОЧНИК", partial(self.open_url, event["source_url"]), "primary", font_size=20)
        self.add_button((1260, 801, 270, 50), "К ХРОНОЛОГИИ", partial(self.go, "timeline", return_to=self.params.get("origin", "menu")), font_size=20, align="right")
        self.caption(event["photo"])

    def screen_media(self) -> None:
        self.background("kremlin_spasskaya", 215)
        self.header("Историческая медиатека / 9 локальных файлов")
        self.canvas.text("МЕДИАТЕКА", (48, 94), 35, WHITE, bold=True)
        self.add_button((1120, 91, 210, 42), "ДЕЯТЕЛИ", partial(self.go, "people"), font_size=18, align="right")
        self.add_button((1370, 91, 180, 42), "В МЕНЮ", partial(self.go, "menu"), font_size=18, align="right")
        for index, record in enumerate(self.media.records):
            col, row = index % 3, index // 3
            x, y = 42 + col * 520, 145 + row * 238
            image = self.media.thumbnail(record["id"], self.canvas.rect((x, y, 480, 158)).size)
            self.window.blit(image, self.canvas.point((x, y)))
            self.canvas.text(record["title"], (x + 4, y + 169), 16, TEXT, max_width=360, max_lines=2, line_gap=1)
            self.add_button((x + 374, y + 177, 106, 40), "ФОТО", partial(self.go, "media_detail", photo_id=record["id"]), font_size=16, align="right")

    def screen_media_detail(self) -> None:
        record = self.media.get(self.params.get("photo_id", ""))
        if not record:
            self.go("media")
            return
        self.background("kremlin_spasskaya", 225)
        self.header("Карточка фотографии")
        area = self.canvas.rect((40, 105, 930, 700))
        image = self.media.surface(record["id"], area.size, "contain")
        self.window.blit(image, area)
        self.canvas.text(record["title"], (1010, 112), 26, WHITE, max_width=540, bold=True, line_gap=3, max_lines=3)
        y = 224
        for label, value in [
            ("АВТОР", record["author"]),
            ("ДАТА", record.get("date", "Не указана")),
            ("ЛИЦЕНЗИЯ", record["license"]),
            ("ОРИГИНАЛ", record["original_filename"]),
        ]:
            self.canvas.text(label, (1010, y), 13, MUTED, bold=True)
            end = self.canvas.text(value, (1010, y + 24), 18, TEXT, max_width=530, line_gap=2, max_lines=3)
            y = max(y + 83, end + 17)
        self.canvas.text("ИЗМЕНЕНИЯ", (1010, y), 13, MUTED, bold=True)
        self.canvas.text(record["modification_description"], (1010, y + 24), 15, MUTED, max_width=530, line_gap=2, max_lines=8)
        self.add_button((1010, 728, 245, 48), "ОРИГИНАЛ", partial(self.open_url, record["source_url"]), "primary", font_size=19)
        self.add_button((1300, 728, 240, 48), "ЛИЦЕНЗИЯ", partial(self.open_url, record["license_url"]), font_size=19, align="right")
        self.add_button((1300, 800, 240, 44), "НАЗАД", partial(self.go, "media"), font_size=18, align="right")
        self.caption(record["id"])

    def screen_credits(self) -> None:
        self.background("kremlin_spasskaya", 220)
        self.header("Авторы и источники / лицензионный учёт")
        self.canvas.text("АВТОРЫ И ИСТОЧНИКИ", (48, 91), 35, WHITE, bold=True)
        self.add_button((1370, 91, 180, 42), "В МЕНЮ", partial(self.go, "menu"), font_size=18, align="right")
        viewport = (35, 135, 1530, 670)
        row_height, gap = 205, 18
        content_height = len(self.media.records) * (row_height + gap)
        self.max_scroll = max(0, content_height - viewport[3])
        self.scroll = min(self.scroll, self.max_scroll)
        self.canvas.clip(viewport)
        for index, record in enumerate(self.media.records):
            y = viewport[1] + index * (row_height + gap) - self.scroll
            if y + row_height < viewport[1] or y > viewport[1] + viewport[3]:
                continue
            image = self.media.thumbnail(record["id"], self.canvas.rect((52, y, 205, 174)).size)
            self.window.blit(image, self.canvas.point((52, y)))
            self.canvas.text(record["title"], (290, y + 2), 24, WHITE, max_width=870, bold=True, max_lines=2)
            self.canvas.text(f"Фото: {record['author']} / Wikimedia Commons / {record['license']}", (290, y + 58), 17, TEXT, max_width=1180)
            self.canvas.text(record["usage_terms"], (290, y + 91), 15, MUTED, max_width=1190, max_lines=2)
            self.canvas.text("Изменения: " + record["modification_description"], (290, y + 137), 13, FAINT, max_width=1190, max_lines=3)
            self.add_button((1290, y + 4, 230, 42), "Оригинал", partial(self.open_url, record["source_url"]), font_size=17, align="right")
            self.add_button((1290, y + 52, 230, 42), "Лицензия", partial(self.open_url, record["license_url"]), font_size=17, align="right")
            self.canvas.line((290, y + 197), (1518, y + 197), LINE, 1, 60)
        self.canvas.clip()
        draw_scrollbar(self.canvas, (1540, viewport[1], 4, viewport[3]), self.scroll, content_height)
        self.canvas.text("Фотографии агентств, стоков и материалы с неизвестной лицензией не включены.", (48, 835), 14, FAINT, max_width=1100)

    def screen_people(self) -> None:
        self.background("kremlin_spasskaya", 215)
        self.header("Карточки политических деятелей")
        self.canvas.text("ПОЛИТИЧЕСКИЕ ДЕЯТЕЛИ", (48, 94), 35, WHITE, bold=True)
        self.add_button((1370, 91, 180, 42), "В МЕНЮ", partial(self.go, "menu"), font_size=18, align="right")
        people = [
            ("navalny_2020", "Алексей\nНавальный", "1976–2024. Оппозиционный политик, антикоррупционный активист, основатель ФБК.", "29.02.2020"),
            ("yulia_navalnaya_2024", "Юлия\nНавальная", "Общественный и политический деятель. Публичные выступления и международная работа.", "19.02.2024"),
            ("kara_murza_2005", "Владимир\nКара-Мурза", "Политик, журналист и правозащитник. Освобождён в ходе обмена 1 августа 2024 года.", "Сентябрь 2005"),
            ("yashin_2005", "Илья\nЯшин", "Политик и муниципальный деятель. Освобождён в ходе обмена 1 августа 2024 года.", "08.07.2005"),
            ("yavlinsky_2018", "Григорий\nЯвлинский", "Политик и экономист, один из основателей партии «Яблоко».", "19.03.2018"),
        ]
        for index, (photo_id, name, bio, photo_date) in enumerate(people):
            x, y, width = 34 + index * 312, 155, 286
            image = self.media.surface(photo_id, self.canvas.rect((x, y, width, 370)).size, "cover")
            self.window.blit(image, self.canvas.point((x, y)))
            self.canvas.text(name, (x + 8, y + 390), 29, WHITE, max_width=width - 16, bold=True, line_gap=0)
            self.canvas.text(bio, (x + 8, y + 474), 16, MUTED, max_width=width - 16, line_gap=4, max_lines=6)
            self.canvas.text("ДАТА ФОТО: " + photo_date, (x + 8, y + 635), 12, TEXT, bold=True)
            self.canvas.text(self.media.get(photo_id)["author"], (x + 8, y + 668), 11, FAINT, max_width=width - 16, max_lines=2)

    def screen_settings(self) -> None:
        self.background("kremlin_spasskaya", 205)
        self.header("Настройки / локальное аудио и дисплей")
        self.canvas.text("НАСТРОЙКИ", (60, 118), 45, WHITE, bold=True)
        rows = [("МУЗЫКА", "music"), ("ГОЛОС", "voice"), ("СИГНАЛЫ ИНТЕРФЕЙСА", "sfx")]
        for index, (label, name) in enumerate(rows):
            y = 230 + index * 104
            value = getattr(self.audio, f"{name}_volume")
            self.canvas.text(label, (86, y), 24, TEXT, bold=True)
            self.canvas.text(f"{round(value * 100)}%", (650, y), 25, WHITE, max_width=100, align="right")
            self.add_button((790, y - 8, 80, 54), "-", partial(self.audio.adjust, name, -0.05), font_size=30, align="center")
            self.add_button((900, y - 8, 80, 54), "+", partial(self.audio.adjust, name, 0.05), font_size=28, align="center")
        self.canvas.line((84, 552), (980, 552), LINE, 1, 80)
        self.add_button((86, 590, 560, 54), f"ГОЛОСОВОЕ ОЗВУЧИВАНИЕ: {'ВКЛ' if self.audio.voice_enabled else 'ВЫКЛ'}", self.audio.toggle_voice, font_size=22)
        self.add_button((86, 658, 560, 54), f"ЗВУК: {'ВЫКЛ' if self.audio.muted else 'ВКЛ'}", self.audio.toggle_mute, font_size=22)
        width, height = self.window.get_size()
        self.canvas.text("РАЗРЕШЕНИЕ", (1080, 232), 17, MUTED, bold=True)
        self.canvas.text(f"{width} × {height}", (1080, 270), 35, WHITE, bold=True)
        self.canvas.text("Интерфейс и текст рендерятся в фактическом разрешении окна. Поддерживаются 2K и 4K без растягивания готового кадра.", (1080, 337), 20, MUTED, max_width=410, line_gap=6)
        self.add_button((1080, 485, 420, 56), "ОКОННЫЙ РЕЖИМ" if self.fullscreen else "ПОЛНЫЙ ЭКРАН", self.toggle_fullscreen, font_size=23)
        self.canvas.text("M — выключить звук\nV — включить или выключить голос\nF11 — полный экран", (1080, 584), 19, MUTED, max_width=410, line_gap=10)
        self.add_button((1080, 776, 420, 52), "НАЗАД", partial(self.go, self.params.get("return_to", "menu")), "primary", font_size=23, align="right")

    def screen_help(self) -> None:
        self.background("kremlin_spasskaya", 215)
        self.header("Правила и управление")
        self.canvas.text("КАК ИГРАТЬ", (58, 110), 42, WHITE, bold=True)
        rules = (
            "1. Читайте документальную карточку и продолжайте сцену кнопкой «Далее».\n\n"
            "2. Выберите один из трёх вариантов. Числовые эффекты скрыты: последствия раскрываются через повествование.\n\n"
            "3. После девяти документальных глав следуют три вымышленные главы до 2030 года.\n\n"
            "4. Прогресс автоматически сохраняется после каждого решения. Финал зависит от всей кампании."
        )
        self.canvas.text(rules, (62, 199), 24, TEXT, max_width=760, line_gap=8)
        controls = [
            ("Мышь", "Выбор и прокрутка"),
            ("↑ / ↓ / Tab", "Переход между вариантами"),
            ("Enter / Space", "Подтвердить"),
            ("1 / 2 / 3", "Выбрать решение"),
            ("Esc", "Пауза или возврат"),
            ("F11", "Полноэкранный режим"),
            ("M / V", "Звук / голос"),
            ("Ctrl + S", "Сохранить вручную"),
        ]
        for index, (key, action) in enumerate(controls):
            y = 206 + index * 60
            self.canvas.text(key, (930, y), 20, WHITE, bold=True, mono=True, max_width=200)
            self.canvas.text(action, (1150, y), 20, MUTED, max_width=360)
        self.add_button((1160, 776, 370, 54), "НАЗАД", partial(self.go, self.params.get("return_to", "menu")), "primary", font_size=23, align="right")
        self.canvas.text("Сохранение: %APPDATA% / PointOfNoReturn / autosave.json", (62, 827), 13, FAINT, max_width=800)


def main() -> None:
    if os.environ.get("POR_SOFTWARE_RENDER"):
        os.environ.setdefault("SDL_RENDER_DRIVER", "software")
    try:
        Game().run()
    except Exception:
        pygame.quit()
        if getattr(sys, "frozen", False):
            from engine import save_directory
            (save_directory() / "crash.log").write_text(traceback.format_exc(), encoding="utf-8")
        raise


if __name__ == "__main__":
    main()
