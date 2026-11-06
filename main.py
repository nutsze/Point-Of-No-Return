from __future__ import annotations

import os
import sys
import traceback
import webbrowser
from functools import partial

import pygame

from engine import (
    APP_NAME, ENDINGS, METRIC_NAMES, REGION_NAMES, advance, apply_choice,
    final_ending, has_save, load_events, load_game, new_state, save_game,
)
from media import MediaLibrary
from ui import (
    AMBER, AMBER_LIGHT, BG, BG_SOFT, FAINT, GREEN, LINE, MUTED, PANEL,
    RED, TEAL, TEXT, Button, FontBook, darken, draw_archive_tag,
    draw_brand, draw_empty_archive, draw_photo_caption, draw_scrollbar, draw_stat,
    draw_text, panel, scanlines, vertical_gradient,
)

WIDTH, HEIGHT = 1280, 720
FPS = 30


class Game:
    def __init__(self) -> None:
        pygame.init()
        pygame.display.set_caption(APP_NAME)
        self.window = pygame.display.set_mode((WIDTH, HEIGHT), pygame.RESIZABLE)
        self.canvas = pygame.Surface((WIDTH, HEIGHT)).convert()
        self.clock = pygame.time.Clock()
        self.fonts = FontBook()
        self.media = MediaLibrary()
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
        self.last_deltas: dict[str, int] = {}
        self.viewport = pygame.Rect(0, 0, WIDTH, HEIGHT)

    def go(self, screen: str, **params) -> None:
        self.screen = screen
        self.params = params
        self.buttons = []
        self.focus_index = 0
        self.scroll = 0
        self.max_scroll = 0
        self.notice = ""

    def start_new(self) -> None:
        self.state = new_state()
        self.go("briefing")

    def continue_game(self) -> None:
        loaded = load_game()
        if loaded is None:
            self.notice = "Сохранение не найдено или повреждено."
            return
        self.state = loaded
        self.go("ending" if self.state.get("completed") else "event")

    def current_event(self) -> dict:
        return self.events[self.state["event_index"]]

    def choose(self, choice_index: int) -> None:
        event = self.current_event()
        self.last_deltas = apply_choice(self.state, event, choice_index)
        save_game(self.state)
        self.go("result", event_id=event["id"], choice_index=choice_index)

    def next_chapter(self) -> None:
        if self.state["completed"]:
            self.go("ending")
            return
        advance(self.state, self.events)
        save_game(self.state)
        self.go("ending" if self.state["completed"] else "event")

    def manual_save(self) -> None:
        save_game(self.state)
        self.notice = "Игра сохранена локально."

    def open_url(self, url: str) -> None:
        if url.startswith("https://"):
            webbrowser.open(url, new=2)

    def toggle_fullscreen(self) -> None:
        self.fullscreen = not self.fullscreen
        if self.fullscreen:
            self.window = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
        else:
            self.window = pygame.display.set_mode((WIDTH, HEIGHT), pygame.RESIZABLE)

    def logical_mouse(self, position: tuple[int, int]) -> tuple[int, int]:
        if not self.viewport.width or not self.viewport.height:
            return position
        x = (position[0] - self.viewport.x) * WIDTH / self.viewport.width
        y = (position[1] - self.viewport.y) * HEIGHT / self.viewport.height
        return round(x), round(y)

    def present(self) -> None:
        window_size = self.window.get_size()
        scale = min(window_size[0] / WIDTH, window_size[1] / HEIGHT)
        size = (max(1, round(WIDTH * scale)), max(1, round(HEIGHT * scale)))
        self.viewport = pygame.Rect(0, 0, *size)
        self.viewport.center = (window_size[0] // 2, window_size[1] // 2)
        self.window.fill((0, 0, 0))
        scaled = pygame.transform.smoothscale(self.canvas, size)
        self.window.blit(scaled, self.viewport)
        pygame.display.flip()

    def handle_key(self, event: pygame.event.Event) -> None:
        if event.key == pygame.K_F11:
            self.toggle_fullscreen()
            return
        if event.key == pygame.K_ESCAPE:
            self.handle_escape()
            return
        if event.key == pygame.K_s and event.mod & pygame.KMOD_CTRL:
            if self.screen not in {"menu", "credits", "media", "media_detail", "timeline", "timeline_detail", "people", "help"}:
                self.manual_save()
            return
        if self.screen == "event" and event.key in {pygame.K_1, pygame.K_2, pygame.K_3}:
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
            self.scroll = max(0, self.scroll - 430)
        elif event.key == pygame.K_PAGEDOWN:
            self.scroll = min(self.max_scroll, self.scroll + 430)

    def handle_escape(self) -> None:
        if self.screen in {"event", "result"}:
            self.return_screen = self.screen
            self.return_params = dict(self.params)
            self.go("pause")
        elif self.screen == "pause":
            self.go(self.return_screen, **self.return_params)
        elif self.screen == "map":
            self.go("event")
        elif self.screen == "timeline_detail":
            self.go("timeline", return_to=self.params.get("origin", "menu"))
        elif self.screen == "media_detail":
            self.go(self.params.get("return_to", "media"))
        elif self.screen != "menu":
            self.go(self.params.get("return_to", "menu"))

    def run(self) -> None:
        while self.running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                elif event.type == pygame.KEYDOWN:
                    self.handle_key(event)
                elif event.type == pygame.MOUSEWHEEL:
                    self.scroll = max(0, min(self.max_scroll, self.scroll - event.y * 55))
                elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    mouse = self.logical_mouse(event.pos)
                    for index, button in enumerate(self.buttons):
                        if button.enabled and button.rect.collidepoint(mouse):
                            self.focus_index = index
                            button.action()
                            break
            self.buttons = []
            screen_method = getattr(self, f"screen_{self.screen}", self.screen_menu)
            screen_method()
            mouse = self.logical_mouse(pygame.mouse.get_pos())
            for index, button in enumerate(self.buttons):
                clip = None
                if self.screen == "timeline" and button.label == "Карточка":
                    clip = pygame.Rect(32, 148, 1216, 500)
                elif self.screen == "credits" and button.label in {"Страница оригинала", "Текст лицензии"}:
                    clip = pygame.Rect(30, 143, 1220, 518)
                self.canvas.set_clip(clip)
                button.draw(self.canvas, self.fonts, mouse, selected=index == self.focus_index)
            self.canvas.set_clip(None)
            if self.notice:
                rect = pygame.Rect(350, 656, 580, 40)
                panel(self.canvas, rect, color=(30, 61, 55), alpha=245, radius=5, border=TEAL)
                draw_text(self.canvas, self.notice, (rect.x + 12, rect.y + 10), self.fonts.get(13), TEXT, max_width=rect.width - 24, align="center")
            self.present()
            self.clock.tick(FPS)
        pygame.quit()

    def add_button(self, rect, label, action, style="normal", enabled=True, font_size=17, hint="") -> None:
        self.buttons.append(Button(pygame.Rect(rect), label, action, style, enabled, hint, font_size))

    def background(self, photo_id: str | None = None, dark: int = 130) -> None:
        if photo_id and self.media.get(photo_id):
            image = self.media.surface(photo_id, (WIDTH, HEIGHT), "cover")
            self.canvas.blit(image, (0, 0))
            darken(self.canvas, dark)
            vertical_gradient(self.canvas, self.canvas.get_rect(), 10, 210)
            scanlines(self.canvas)
        else:
            self.canvas.fill(BG)
            for y in range(0, HEIGHT, 4):
                pygame.draw.line(self.canvas, (12, 20, 28), (0, y), (WIDTH, y))
            if photo_id:
                draw_empty_archive(self.canvas, self.fonts, pygame.Rect(300, 170, 680, 380))

    def screen_menu(self) -> None:
        self.background("kremlin_spasskaya", 95)
        draw_brand(self.canvas, self.fonts, "документальный политический симулятор")
        draw_archive_tag(self.canvas, self.fonts, "РЕЛИЗ 1.0 / ЛОКАЛЬНАЯ МЕДИАТЕКА", (38, 82))
        draw_text(self.canvas, "2030", (40, 142), self.fonts.get(86, bold=True), AMBER_LIGHT, max_width=570)
        draw_text(self.canvas, "ТОЧКА\nНЕВОЗВРАТА", (42, 237), self.fonts.get(47, bold=True), TEXT, max_width=610, line_gap=0)
        draw_text(self.canvas, "Политическая визуальная новелла о десяти годах, в которых каждое решение оставляет след.", (44, 365), self.fonts.get(18), (203, 208, 208), max_width=560, line_gap=7)
        pygame.draw.line(self.canvas, AMBER, (44, 445), (510, 445), 2)
        draw_text(self.canvas, "Реальные события. Вымышленный Гражданский совет.\nАльтернативная история — только после вашего первого решения.", (44, 462), self.fonts.get(13), MUTED, max_width=570, line_gap=6)
        x, y, w, h, gap = 790, 116, 430, 55, 12
        self.add_button((x, y, w, h), "Новая кампания", self.start_new, "primary")
        self.add_button((x, y + (h + gap), w, h), "Продолжить", self.continue_game, enabled=has_save())
        entries = [
            ("Хронология 2020–2030", "timeline"),
            ("Историческая медиатека", "media"),
            ("Политические деятели", "people"),
            ("Авторы и источники", "credits"),
            ("Правила и управление", "help"),
        ]
        for i, (label, target) in enumerate(entries):
            self.add_button((x, y + (h + gap) * (i + 2), w, h), label, partial(self.go, target), "ghost")
        self.add_button((x, y + (h + gap) * 7, w, 45), "Выход", self.quit, "danger")
        draw_photo_caption(self.canvas, self.fonts, self.media.caption("kremlin_spasskaya"), HEIGHT - 8)

    def quit(self) -> None:
        self.running = False

    def screen_briefing(self) -> None:
        self.background("navalny_2020", 175)
        draw_brand(self.canvas, self.fonts, "учредительное совещание / август 2020")
        panel(self.canvas, pygame.Rect(48, 82, 1184, 566), alpha=244)
        draw_archive_tag(self.canvas, self.fonts, "ВАША РОЛЬ — ВЫМЫШЛЕННАЯ", (76, 106))
        draw_text(self.canvas, "Гражданский совет", (76, 151), self.fonts.get(38, bold=True), TEXT, max_width=700)
        draw_text(self.canvas, "Вы — координатор независимой общественной инициативы. Реальные политики и события образуют документальный фон, но вашего совета и принимаемых вами решений в действительности не было.", (78, 208), self.fonts.get(17), MUTED, max_width=690, line_gap=7)
        draw_text(self.canvas, "Цель", (78, 316), self.fonts.get(14, bold=True), AMBER)
        draw_text(self.canvas, "К 2030 году построить устойчивую общенациональную коалицию, сохранив людей, ресурсы и внутреннее доверие.", (78, 345), self.fonts.get(19, bold=True), TEXT, max_width=690)
        draw_text(self.canvas, "Документальные карточки содержат дату, описание, участников и источник. После первого решения вся ветка развития событий получает постоянную пометку «АЛЬТЕРНАТИВНАЯ ИСТОРИЯ».", (78, 418), self.fonts.get(15), MUTED, max_width=690)
        metrics = [
            ("ПОДДЕРЖКА", "Общественный охват и электоральный потенциал", AMBER),
            ("РЕСУРСЫ", "Финансы, кадры и организационный резерв", TEAL),
            ("ДОВЕРИЕ", "Способность союзников работать вместе", GREEN),
            ("ДАВЛЕНИЕ", "Политические и правовые ограничения", RED),
        ]
        for i, (name, description, color) in enumerate(metrics):
            y = 150 + i * 102
            pygame.draw.rect(self.canvas, color, (824, y, 5, 76))
            draw_text(self.canvas, name, (848, y), self.fonts.get(14, bold=True), color, max_width=320)
            draw_text(self.canvas, description, (848, y + 28), self.fonts.get(14), MUTED, max_width=310)
        self.add_button((806, 561, 386, 56), "Начать кампанию", partial(self.go, "event"), "primary")
        self.add_button((76, 574, 180, 42), "В меню", partial(self.go, "menu"), "ghost")

    def screen_event(self) -> None:
        event = self.current_event()
        photo_id = event["photo"]
        self.background(photo_id, 155)
        index = self.state["event_index"]
        draw_brand(self.canvas, self.fonts, f"глава {index + 1} из {len(self.events)} / {event['date']}")
        if self.state["alternative_history"]:
            draw_archive_tag(self.canvas, self.fonts, "АЛЬТЕРНАТИВНАЯ ИСТОРИЯ — СОБЫТИЯ РАЗВИВАЮТСЯ ИНАЧЕ", (30, 65), True)
        else:
            draw_archive_tag(self.canvas, self.fonts, "ДОКУМЕНТАЛЬНЫЙ КОНТЕКСТ", (30, 65))
        left = pygame.Rect(28, 105, 720, 535)
        right = pygame.Rect(770, 105, 482, 535)
        panel(self.canvas, left, alpha=232)
        panel(self.canvas, right, alpha=239)
        draw_text(self.canvas, event["date"].upper(), (52, 130), self.fonts.get(13, bold=True, mono=True), AMBER, max_width=670)
        y = draw_text(self.canvas, event["title"], (52, 161), self.fonts.get(31, bold=True), TEXT, max_width=665, line_gap=2)
        y += 12
        y = draw_text(self.canvas, event["description"], (52, y), self.fonts.get(16), (202, 207, 207), max_width=665, line_gap=6)
        y += 14
        draw_text(self.canvas, "ПОЛИТИЧЕСКИЕ СИЛЫ", (52, y), self.fonts.get(11, bold=True), MUTED, max_width=650)
        draw_text(self.canvas, " · ".join(event["forces"]), (52, y + 24), self.fonts.get(13), MUTED, max_width=665, line_gap=4)
        if event["documentary"]:
            self.add_button((52, 573, 214, 42), "Открыть источник", partial(self.open_url, event["source_url"]), "ghost", font_size=14)
            draw_text(self.canvas, event["source_name"], (52, 531), self.fonts.get(11), FAINT, max_width=665)
        else:
            draw_text(self.canvas, "Вымышленное событие ветки игрока. Документальный источник не применяется.", (52, 541), self.fonts.get(12), RED, max_width=660)
        self.add_button((282, 573, 132, 42), "Карта", partial(self.go, "map"), "ghost", font_size=14)
        self.add_button((428, 573, 132, 42), "Хроника", partial(self.go, "timeline", return_to="event"), "ghost", font_size=14)
        self.add_button((574, 573, 142, 42), "Пауза", self.pause, "ghost", font_size=14)
        draw_text(self.canvas, "ВАШЕ РЕШЕНИЕ", (794, 130), self.fonts.get(13, bold=True), AMBER, max_width=430)
        draw_text(self.canvas, "Последствия показаны до выбора. Решение нельзя отменить.", (794, 157), self.fonts.get(12), MUTED, max_width=430)
        for i, choice in enumerate(event["choices"]):
            y_choice = 204 + i * 136
            label = f"{i + 1}. {choice['text']}\n{choice['detail']}"
            self.add_button((792, y_choice, 438, 119), label, partial(self.choose, i), "normal", font_size=14)
        draw_photo_caption(self.canvas, self.fonts, self.media.caption(photo_id), HEIGHT - 4)

    def pause(self) -> None:
        self.return_screen = self.screen
        self.return_params = dict(self.params)
        self.go("pause")

    def screen_pause(self) -> None:
        self.background("kremlin_spasskaya", 190)
        draw_brand(self.canvas, self.fonts, "пауза")
        panel(self.canvas, pygame.Rect(390, 102, 500, 514), alpha=246)
        draw_text(self.canvas, "ПАУЗА", (424, 137), self.fonts.get(38, bold=True), TEXT, max_width=432, align="center")
        draw_text(self.canvas, "Прогресс автоматически сохраняется после каждого решения.", (434, 196), self.fonts.get(14), MUTED, max_width=412, align="center")
        self.add_button((434, 252, 412, 54), "Продолжить", partial(self.go, self.return_screen, **self.return_params), "primary")
        self.add_button((434, 320, 412, 52), "Сохранить сейчас", self.manual_save)
        self.add_button((434, 386, 412, 52), "Правила и управление", partial(self.go, "help", return_to="pause"), "ghost")
        self.add_button((434, 452, 412, 52), "Главное меню", partial(self.go, "menu"), "ghost")
        self.add_button((434, 518, 412, 52), "Выход из игры", self.quit, "danger")

    def screen_result(self) -> None:
        event = self.events[self.state["event_index"]]
        choice = event["choices"][self.params.get("choice_index", 0)]
        self.background(event["photo"], 185)
        draw_brand(self.canvas, self.fonts, "результат решения")
        draw_archive_tag(self.canvas, self.fonts, "АЛЬТЕРНАТИВНАЯ ИСТОРИЯ — СОБЫТИЯ РАЗВИВАЮТСЯ ИНАЧЕ", (30, 66), True)
        panel(self.canvas, pygame.Rect(40, 112, 752, 496), alpha=240)
        draw_text(self.canvas, choice["text"], (68, 140), self.fonts.get(28, bold=True), TEXT, max_width=695)
        draw_text(self.canvas, choice["result"], (68, 213), self.fonts.get(18), (209, 213, 211), max_width=690, line_gap=8)
        pygame.draw.line(self.canvas, LINE, (68, 333), (754, 333), 1)
        draw_text(self.canvas, "СОСТОЯНИЕ ГРАЖДАНСКОГО СОВЕТА", (68, 356), self.fonts.get(12, bold=True), AMBER)
        changed_regions = [(REGION_NAMES.get(key, key), value) for key, value in choice.get("regions", {}).items() if value]
        region_text = " · ".join(f"{name} {'+' if value > 0 else ''}{value}" for name, value in changed_regions) or "Региональные показатели не изменились"
        draw_text(self.canvas, region_text, (68, 388), self.fonts.get(15), MUTED, max_width=690)
        draw_text(self.canvas, "Все показатели являются игровой абстракцией, а не оценкой реальных рейтингов.", (68, 462), self.fonts.get(12), FAINT, max_width=690)
        self.add_button((68, 526, 684, 54), "Следующая глава" if not self.state["completed"] else "Увидеть итог кампании", self.next_chapter, "primary")
        panel(self.canvas, pygame.Rect(818, 112, 422, 496), alpha=242)
        draw_text(self.canvas, "ИЗМЕНЕНИЯ", (844, 140), self.fonts.get(13, bold=True), AMBER)
        colors = {"support": AMBER, "resources": TEAL, "trust": GREEN, "pressure": RED}
        for i, (key, label) in enumerate(METRIC_NAMES.items()):
            draw_stat(self.canvas, self.fonts, label, self.state["metrics"][key], pygame.Rect(846, 183 + i * 91, 366, 76), colors[key], self.last_deltas.get(key))
        draw_photo_caption(self.canvas, self.fonts, self.media.caption(event["photo"]), HEIGHT - 4)

    def screen_ending(self) -> None:
        ending_id = self.state.get("ending_id") or final_ending(self.state)
        ending = ENDINGS[ending_id]
        self.background("kremlin_spasskaya", 178)
        draw_brand(self.canvas, self.fonts, "20 августа 2030 / итог")
        draw_archive_tag(self.canvas, self.fonts, "АЛЬТЕРНАТИВНАЯ ИСТОРИЯ / ФИНАЛ НЕ ЯВЛЯЕТСЯ ПРОГНОЗОМ", (32, 68), True)
        panel(self.canvas, pygame.Rect(48, 115, 780, 505), alpha=240)
        draw_text(self.canvas, ending["subtitle"].upper(), (78, 145), self.fonts.get(13, bold=True), AMBER, max_width=720)
        draw_text(self.canvas, ending["title"], (78, 181), self.fonts.get(42, bold=True), TEXT, max_width=720)
        draw_text(self.canvas, ending["text"], (78, 254), self.fonts.get(18), (211, 214, 210), max_width=710, line_gap=8)
        developed = sum(value >= 30 for value in self.state["regions"].values())
        draw_text(self.canvas, f"Принято решений: {len(self.state['history'])}  /  Регионов с поддержкой 30+: {developed}  /  Завершение: 2030", (78, 413), self.fonts.get(13, bold=True, mono=True), MUTED, max_width=710)
        self.add_button((78, 489, 340, 56), "Новая кампания", self.start_new, "primary")
        self.add_button((438, 489, 340, 56), "Главное меню", partial(self.go, "menu"), "ghost")
        self.add_button((78, 558, 340, 38), "Итоговая хроника", partial(self.go, "timeline", return_to="ending"), "ghost", font_size=13)
        panel(self.canvas, pygame.Rect(852, 115, 380, 505), alpha=242)
        draw_text(self.canvas, "ИТОГОВЫЕ ПОКАЗАТЕЛИ", (878, 145), self.fonts.get(12, bold=True), AMBER, max_width=325)
        colors = {"support": AMBER, "resources": TEAL, "trust": GREEN, "pressure": RED}
        for i, (key, label) in enumerate(METRIC_NAMES.items()):
            draw_stat(self.canvas, self.fonts, label, self.state["metrics"][key], pygame.Rect(880, 190 + i * 91, 324, 76), colors[key])
        draw_text(self.canvas, "Этот финал описывает только вымышленную ветку вашей кампании.", (880, 554), self.fonts.get(12), FAINT, max_width=320)
        draw_photo_caption(self.canvas, self.fonts, self.media.caption("kremlin_spasskaya"), HEIGHT - 4)

    def screen_timeline(self) -> None:
        self.canvas.fill(BG)
        draw_brand(self.canvas, self.fonts, "хронология / документ и альтернатива")
        draw_text(self.canvas, "Хронология 2020–2030", (34, 70), self.fonts.get(28, bold=True), TEXT, max_width=800)
        draw_text(self.canvas, "Документальные события отделены от вымышленных глав и решений игрока.", (36, 111), self.fonts.get(13), MUTED, max_width=900)
        viewport = pygame.Rect(32, 148, 1216, 500)
        card_height, gap = 116, 10
        content_height = len(self.events) * (card_height + gap)
        self.max_scroll = max(0, content_height - viewport.height)
        self.scroll = min(self.scroll, self.max_scroll)
        self.canvas.set_clip(viewport)
        for i, event in enumerate(self.events):
            y = viewport.y + i * (card_height + gap) - self.scroll
            rect = pygame.Rect(viewport.x, y, 1160, card_height)
            if rect.bottom < viewport.y or rect.top > viewport.bottom:
                continue
            panel(self.canvas, rect, color=PANEL, alpha=245, radius=5)
            accent = AMBER if event["documentary"] else RED
            pygame.draw.rect(self.canvas, accent, (rect.x, rect.y, 4, rect.height))
            draw_text(self.canvas, event["date"].upper(), (rect.x + 20, rect.y + 16), self.fonts.get(11, bold=True, mono=True), accent, max_width=188)
            draw_text(self.canvas, "ДОКУМЕНТ" if event["documentary"] else "АЛЬТЕРНАТИВА", (rect.x + 20, rect.y + 48), self.fonts.get(10, bold=True), MUTED, max_width=180)
            draw_text(self.canvas, event["title"], (rect.x + 224, rect.y + 13), self.fonts.get(19, bold=True), TEXT, max_width=660)
            description = event["description"].replace("АЛЬТЕРНАТИВНАЯ ИСТОРИЯ. ", "")
            draw_text(self.canvas, description, (rect.x + 224, rect.y + 48), self.fonts.get(12), MUTED, max_width=690, line_gap=3, max_lines=3)
            self.add_button((rect.right - 142, rect.y + 34, 118, 46), "Карточка", partial(self.go, "timeline_detail", event_index=i, return_to="timeline", origin=self.params.get("return_to", "menu")), "ghost", font_size=13)
        self.canvas.set_clip(None)
        draw_scrollbar(self.canvas, pygame.Rect(1206, viewport.y, 7, viewport.height), self.scroll, content_height)
        self.add_button((1040, 76, 196, 44), "Назад", partial(self.go, self.params.get("return_to", "menu")), "ghost")
        draw_text(self.canvas, "Колесо мыши / Page Up / Page Down", (36, 668), self.fonts.get(11), FAINT, max_width=600)

    def screen_timeline_detail(self) -> None:
        event = self.events[self.params.get("event_index", 0)]
        self.background(event["photo"], 145)
        draw_brand(self.canvas, self.fonts, "архивная карточка события")
        draw_archive_tag(self.canvas, self.fonts, "ДОКУМЕНТАЛЬНОЕ СОБЫТИЕ" if event["documentary"] else "АЛЬТЕРНАТИВНАЯ ИСТОРИЯ", (30, 67), not event["documentary"])
        panel(self.canvas, pygame.Rect(38, 111, 1204, 520), alpha=237)
        draw_text(self.canvas, event["date"].upper(), (68, 141), self.fonts.get(13, bold=True, mono=True), AMBER, max_width=1100)
        draw_text(self.canvas, event["title"], (68, 176), self.fonts.get(34, bold=True), TEXT, max_width=1100)
        draw_text(self.canvas, event["description"], (68, 251), self.fonts.get(17), (210, 214, 211), max_width=1100, line_gap=7)
        draw_text(self.canvas, "ЗАДЕЙСТВОВАННЫЕ СИЛЫ", (68, 382), self.fonts.get(11, bold=True), MUTED)
        draw_text(self.canvas, " · ".join(event["forces"]), (68, 411), self.fonts.get(14), MUTED, max_width=1100)
        if event["documentary"]:
            draw_text(self.canvas, event["source_name"], (68, 488), self.fonts.get(12), FAINT, max_width=800)
            self.add_button((68, 539, 250, 50), "Открыть источник", partial(self.open_url, event["source_url"]), "primary")
        else:
            draw_text(self.canvas, "Вымышленная глава. Не используется как утверждение о реальном будущем.", (68, 495), self.fonts.get(13), RED, max_width=800)
        self.add_button((956, 539, 236, 50), "К хронологии", partial(self.go, "timeline", return_to=self.params.get("origin", "menu")), "ghost")
        draw_photo_caption(self.canvas, self.fonts, self.media.caption(event["photo"]), HEIGHT - 4)

    def screen_media(self) -> None:
        self.canvas.fill(BG)
        draw_brand(self.canvas, self.fonts, "историческая медиатека / 9 локальных файлов")
        draw_text(self.canvas, "Историческая медиатека", (32, 68), self.fonts.get(27, bold=True), TEXT, max_width=780)
        draw_text(self.canvas, "Только документальные фотографии с проверенными метаданными. Сеть при запуске не используется.", (34, 108), self.fonts.get(12), MUTED, max_width=960)
        self.add_button((1040, 74, 196, 42), "В меню", partial(self.go, self.params.get("return_to", "menu")), "ghost")
        records = self.media.records
        cell_w, cell_h = 392, 174
        for i, record in enumerate(records):
            col, row = i % 3, i // 3
            x, y = 32 + col * 408, 145 + row * 181
            rect = pygame.Rect(x, y, cell_w, cell_h)
            panel(self.canvas, rect, alpha=245, radius=5)
            thumb = self.media.thumbnail(record["id"], (cell_w - 12, 96))
            self.canvas.blit(thumb, (x + 6, y + 6))
            draw_text(self.canvas, record["title"], (x + 10, y + 109), self.fonts.get(11, bold=True), TEXT, max_width=276, line_gap=1, max_lines=3)
            self.add_button((x + 294, y + 123, 86, 36), "Фото", partial(self.go, "media_detail", photo_id=record["id"], return_to="media"), "ghost", font_size=12)

    def screen_media_detail(self) -> None:
        record = self.media.get(self.params.get("photo_id", ""))
        if not record:
            self.go("media")
            return
        self.canvas.fill(BG)
        draw_brand(self.canvas, self.fonts, "карточка фотографии / подтверждённые метаданные")
        image_rect = pygame.Rect(26, 78, 758, 548)
        image = self.media.surface(record["id"], image_rect.size, "contain")
        self.canvas.blit(image, image_rect)
        pygame.draw.rect(self.canvas, LINE, image_rect, width=1)
        panel(self.canvas, pygame.Rect(806, 78, 448, 548), alpha=246)
        draw_text(self.canvas, record["title"], (830, 96), self.fonts.get(19, bold=True), TEXT, max_width=400, line_gap=2, max_lines=3)
        y = 174
        fields = [
            ("АВТОР", record["author"]),
            ("ДАТА", record.get("date", "Не указана")),
            ("ЛИЦЕНЗИЯ", record["license"]),
            ("ОРИГИНАЛ", record["original_filename"]),
        ]
        for label, value in fields:
            draw_text(self.canvas, label, (830, y), self.fonts.get(9, bold=True), AMBER, max_width=390)
            draw_text(self.canvas, value, (830, y + 16), self.fonts.get(11), MUTED, max_width=396, line_gap=1, max_lines=2)
            y += 54
        draw_text(self.canvas, "ИЗМЕНЕНИЯ", (830, y), self.fonts.get(9, bold=True), AMBER)
        draw_text(self.canvas, record["modification_description"], (830, y + 16), self.fonts.get(10), MUTED, max_width=396, line_gap=1, max_lines=6)
        self.add_button((830, 512, 188, 42), "Оригинал", partial(self.open_url, record["source_url"]), "primary", font_size=13)
        self.add_button((1032, 512, 196, 42), "Лицензия", partial(self.open_url, record["license_url"]), "ghost", font_size=13)
        self.add_button((830, 566, 398, 40), "Назад в медиатеку", partial(self.go, "media"), "ghost", font_size=13)
        draw_photo_caption(self.canvas, self.fonts, self.media.caption(record["id"]), HEIGHT - 4)

    def screen_credits(self) -> None:
        self.canvas.fill(BG)
        draw_brand(self.canvas, self.fonts, "авторы и источники / лицензионный учёт")
        draw_text(self.canvas, "Авторы и источники", (32, 68), self.fonts.get(28, bold=True), TEXT, max_width=800)
        draw_text(self.canvas, "Каждая фотография хранится локально и связана с записью в assets/credits.json.", (34, 109), self.fonts.get(12), MUTED, max_width=900)
        self.add_button((1040, 74, 196, 42), "В меню", partial(self.go, "menu"), "ghost")
        viewport = pygame.Rect(30, 143, 1220, 518)
        card_height, gap = 205, 12
        content_height = len(self.media.records) * (card_height + gap)
        self.max_scroll = max(0, content_height - viewport.height)
        self.scroll = min(self.scroll, self.max_scroll)
        self.canvas.set_clip(viewport)
        for i, record in enumerate(self.media.records):
            y = viewport.y + i * (card_height + gap) - self.scroll
            rect = pygame.Rect(34, y, 1160, card_height)
            if rect.bottom < viewport.y or rect.top > viewport.bottom:
                continue
            panel(self.canvas, rect, alpha=246, radius=5)
            thumb = self.media.thumbnail(record["id"], (170, 172))
            self.canvas.blit(thumb, (rect.x + 10, rect.y + 10))
            draw_text(self.canvas, record["title"], (rect.x + 198, rect.y + 13), self.fonts.get(16, bold=True), TEXT, max_width=680)
            draw_text(self.canvas, f"Фото: {record['author']} / Wikimedia Commons / {record['license']}", (rect.x + 198, rect.y + 49), self.fonts.get(12), AMBER_LIGHT, max_width=900)
            draw_text(self.canvas, record["usage_terms"], (rect.x + 198, rect.y + 78), self.fonts.get(11), MUTED, max_width=920, line_gap=2, max_lines=3)
            draw_text(self.canvas, "Изменения: " + record["modification_description"], (rect.x + 198, rect.y + 127), self.fonts.get(10), FAINT, max_width=920, line_gap=1, max_lines=3)
            self.add_button((rect.right - 230, rect.y + 18, 208, 38), "Страница оригинала", partial(self.open_url, record["source_url"]), "ghost", font_size=12)
            self.add_button((rect.right - 230, rect.y + 66, 208, 38), "Текст лицензии", partial(self.open_url, record["license_url"]), "ghost", font_size=12)
        self.canvas.set_clip(None)
        draw_scrollbar(self.canvas, pygame.Rect(1208, viewport.y, 7, viewport.height), self.scroll, content_height)
        draw_text(self.canvas, "Изображения информационных агентств, стоков и материалы с неизвестной лицензией в релиз не включены.", (34, 675), self.fonts.get(11), FAINT, max_width=1100)

    def screen_people(self) -> None:
        self.canvas.fill(BG)
        draw_brand(self.canvas, self.fonts, "карточки политических деятелей")
        draw_text(self.canvas, "Политические деятели", (30, 70), self.fonts.get(28, bold=True), TEXT, max_width=800)
        draw_text(self.canvas, "Фотографии датированы; более ранние портреты не выдаются за снимки событий 2020–2024 годов.", (32, 111), self.fonts.get(12), MUTED, max_width=980)
        self.add_button((1040, 74, 196, 42), "В меню", partial(self.go, "menu"), "ghost")
        people = [
            ("navalny_2020", "Алексей\nНавальный", "1976–2024. Оппозиционный политик, антикоррупционный активист, основатель ФБК.", "29.02.2020"),
            ("yulia_navalnaya_2024", "Юлия\nНавальная", "Общественный и политический деятель. Публичные выступления и международная работа.", "19.02.2024"),
            ("kara_murza_2005", "Владимир\nКара-Мурза", "Политик, журналист и правозащитник. Освобождён в ходе обмена 1 августа 2024 года.", "Сентябрь 2005"),
            ("yashin_2005", "Илья\nЯшин", "Политик и муниципальный деятель. Освобождён в ходе обмена 1 августа 2024 года.", "08.07.2005"),
            ("yavlinsky_2018", "Григорий\nЯвлинский", "Политик и экономист, один из основателей партии «Яблоко».", "19.03.2018"),
        ]
        for i, (photo_id, name, bio, photo_date) in enumerate(people):
            x, y, w = 26 + i * 250, 148, 234
            rect = pygame.Rect(x, y, w, 500)
            panel(self.canvas, rect, alpha=246, radius=5)
            image = self.media.surface(photo_id, (w - 12, 268), "cover")
            self.canvas.blit(image, (x + 6, y + 6))
            draw_text(self.canvas, name, (x + 14, y + 287), self.fonts.get(20, bold=True), TEXT, max_width=w - 28, line_gap=0)
            draw_text(self.canvas, bio, (x + 14, y + 350), self.fonts.get(11), MUTED, max_width=w - 28, line_gap=3, max_lines=5)
            draw_text(self.canvas, "ДАТА ФОТО: " + photo_date, (x + 14, y + 447), self.fonts.get(9, bold=True, mono=True), AMBER, max_width=w - 28)
            record = self.media.get(photo_id)
            draw_text(self.canvas, record["author"], (x + 14, y + 471), self.fonts.get(8), FAINT, max_width=w - 28, line_gap=1, max_lines=2)

    def screen_map(self) -> None:
        self.canvas.fill(BG_SOFT)
        draw_brand(self.canvas, self.fonts, "региональная карта / игровая модель")
        draw_text(self.canvas, "Региональная сеть", (30, 69), self.fonts.get(27, bold=True), TEXT, max_width=700)
        draw_text(self.canvas, "Схематичная карта, не географическая проекция. Значения не являются реальными рейтингами.", (32, 108), self.fonts.get(11), MUTED, max_width=820)
        self.add_button((1040, 74, 196, 42), "К событию", partial(self.go, "event"), "ghost")
        map_rect = pygame.Rect(24, 143, 842, 516)
        panel(self.canvas, map_rect, color=(15, 28, 38), alpha=250)
        outline = [(75, 320), (140, 215), (250, 165), (355, 190), (465, 155), (580, 195), (705, 174), (820, 240), (792, 342), (730, 390), (660, 460), (535, 485), (430, 540), (320, 505), (240, 450), (140, 420)]
        shifted = [(map_rect.x + x * 0.92, map_rect.y + (y - 140) * 1.02) for x, y in outline]
        pygame.draw.polygon(self.canvas, (29, 53, 65), shifted)
        pygame.draw.polygon(self.canvas, (62, 87, 97), shifted, width=2)
        nodes = {
            "spb": (238, 118), "moscow": (285, 265), "nizhny": (365, 245),
            "volga": (405, 310), "ural": (500, 260), "siberia": (610, 260),
            "south": (285, 390), "far_east": (730, 235),
        }
        for key, (nx, ny) in nodes.items():
            value = self.state["regions"][key]
            x = map_rect.x + round(nx * 0.92)
            y = map_rect.y + round(ny * 1.02)
            radius = 10 + value // 8
            color = AMBER if value >= 30 else (TEAL if value >= 18 else (83, 109, 123))
            pygame.draw.circle(self.canvas, (8, 15, 21), (x, y), radius + 4)
            pygame.draw.circle(self.canvas, color, (x, y), radius)
            pygame.draw.circle(self.canvas, TEXT, (x, y), radius, width=1)
            label = f"{REGION_NAMES[key]}  {value}"
            label_x = max(map_rect.x + 8, min(x - 55, map_rect.right - 170))
            draw_text(self.canvas, label, (label_x, y + radius + 6), self.fonts.get(10, bold=True), TEXT, max_width=165, align="center")
        draw_text(self.canvas, "Радиус и цвет отражают только накопленные эффекты ваших решений.", (map_rect.x + 20, map_rect.bottom - 35), self.fonts.get(10), FAINT, max_width=780)
        stats_rect = pygame.Rect(890, 143, 366, 516)
        panel(self.canvas, stats_rect, alpha=245)
        draw_text(self.canvas, "ПОДДЕРЖКА ПО РЕГИОНАМ", (914, 166), self.fonts.get(11, bold=True), AMBER, max_width=320)
        for i, (key, name) in enumerate(REGION_NAMES.items()):
            draw_stat(self.canvas, self.fonts, name, self.state["regions"][key], pygame.Rect(914, 200 + i * 53, 318, 48), AMBER if self.state["regions"][key] >= 30 else TEAL)
        draw_text(self.canvas, "Цель наиболее успешной ветки: не менее четырёх регионов со значением 30+.", (914, 610), self.fonts.get(10), FAINT, max_width=315)

    def screen_help(self) -> None:
        self.canvas.fill(BG)
        draw_brand(self.canvas, self.fonts, "правила и управление")
        draw_text(self.canvas, "Как играть", (38, 78), self.fonts.get(30, bold=True), TEXT, max_width=700)
        panel(self.canvas, pygame.Rect(38, 132, 576, 472), alpha=245)
        draw_text(self.canvas, "ИГРОВОЙ ЦИКЛ", (64, 158), self.fonts.get(12, bold=True), AMBER)
        rules = [
            "1. Прочитайте документальную карточку: дата, событие, участники и источник.",
            "2. Выберите одно из трёх решений. Его эффекты применяются сразу и сохраняются.",
            "3. Следите за четырьмя показателями и поддержкой в восьми регионах.",
            "4. После девяти документальных глав наступают три полностью вымышленные главы до 2030 года.",
            "5. Финал зависит от всей кампании. Давление 100 или нулевые ресурсы/доверие завершают её досрочно.",
        ]
        y = 194
        for rule in rules:
            y = draw_text(self.canvas, rule, (64, y), self.fonts.get(14), MUTED, max_width=520, line_gap=5) + 13
        panel(self.canvas, pygame.Rect(636, 132, 606, 472), alpha=245)
        draw_text(self.canvas, "УПРАВЛЕНИЕ", (662, 158), self.fonts.get(12, bold=True), AMBER)
        controls = [
            ("Мышь", "Выбор и прокрутка"),
            ("↑ / ↓ / Tab", "Переход между кнопками"),
            ("Enter / Space", "Подтвердить"),
            ("1 / 2 / 3", "Выбрать решение в главе"),
            ("Esc", "Пауза или возврат"),
            ("F11", "Полноэкранный режим"),
            ("Ctrl + S", "Сохранить вручную"),
            ("Page Up / Down", "Листать длинные списки"),
        ]
        for i, (key, action) in enumerate(controls):
            y = 198 + i * 38
            draw_text(self.canvas, key, (662, y), self.fonts.get(13, bold=True, mono=True), TEXT, max_width=180)
            draw_text(self.canvas, action, (858, y), self.fonts.get(13), MUTED, max_width=350)
        draw_text(self.canvas, "Сохранение Windows: %APPDATA% / PointOfNoReturn / autosave.json", (662, 520), self.fonts.get(10), FAINT, max_width=540)
        self.add_button((894, 630, 348, 48), "Назад", partial(self.go, self.params.get("return_to", "menu")), "primary")
        draw_text(self.canvas, "Игра не является прогнозом, учебным пособием по насильственным действиям или заявлением от имени изображённых лиц.", (40, 649), self.fonts.get(10), FAINT, max_width=800)


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
