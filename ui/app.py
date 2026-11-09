"""Pygame windowed front-end: resizable window, real fullscreen (F11) at the
desktop's native resolution (so it renders correctly at 2K/4K), reusing the
same story graph and save format as the terminal version.
"""
from __future__ import annotations

import json
import os
import sys

import pygame

from engine import state as state_mod
from engine.story import DEDICATION, ENDINGS, NODES, PEOPLE, START_NODE, compute_ending

PHOTOS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "photos")

BG = (15, 16, 18)
FG = (233, 230, 223)
MUTED = (143, 139, 130)
ACCENT = (178, 58, 47)
SURFACE = (26, 27, 31)
LINE = (46, 48, 54)

PROFESSIONS = ["Студент(ка)", "Врач", "Учитель(ница)", "IT-специалист(ка)",
               "Продавец(щица)", "Инженер(ка)"]
CITIES = ["Москва", "Санкт-Петербург", "Екатеринбург", "Новосибирск",
          "Томск", "Краснодар", "Казань", "Владивосток"]

DEFAULT_SIZE = (1280, 720)


def wrap_text(font: pygame.font.Font, text: str, max_width: int) -> list[str]:
    lines: list[str] = []
    for paragraph in text.split("\n\n"):
        words = paragraph.split()
        cur = ""
        for w in words:
            trial = (cur + " " + w).strip()
            if font.size(trial)[0] <= max_width or not cur:
                cur = trial
            else:
                lines.append(cur)
                cur = w
        lines.append(cur)
        lines.append("")  # blank line between paragraphs
    if lines and lines[-1] == "":
        lines.pop()
    return lines


class Rect:
    """A clickable zone tagged with an action."""
    def __init__(self, rect: pygame.Rect, action):
        self.rect = rect
        self.action = action


class App:
    def __init__(self):
        pygame.init()
        pygame.display.set_caption("Точка невозврата")
        self.windowed_size = DEFAULT_SIZE
        self.fullscreen = False
        self.screen = pygame.display.set_mode(self.windowed_size, pygame.RESIZABLE)
        self.clock = pygame.time.Clock()
        self._load_fonts()

        self.state = state_mod.load() or state_mod.State()
        self.mode = "creation" if not (self.state.name and self.state.profession and self.state.city) else "story"
        if self.mode == "story" and self.state.node == "FINALE":
            self.mode = "ending"

        self.name_buf = self.state.name
        self.profession_sel = self.state.profession
        self.city_sel = self.state.city
        self.name_active = True

        self.clickables: list[Rect] = []
        self.scroll = 0
        self.content_height = 0

        self.photo_cache: dict[str, pygame.Surface | None] = {}
        self.photo_credits: dict = {}
        credits_path = os.path.join(PHOTOS_DIR, "credits.json")
        if os.path.exists(credits_path):
            try:
                with open(credits_path, encoding="utf-8") as f:
                    self.photo_credits = json.load(f)
            except (OSError, json.JSONDecodeError):
                self.photo_credits = {}

        self.running = True

    def _get_photo(self, key: str) -> pygame.Surface | None:
        if key not in self.photo_cache:
            path = os.path.join(PHOTOS_DIR, key + ".jpg")
            if os.path.exists(path):
                try:
                    self.photo_cache[key] = pygame.image.load(path).convert()
                except pygame.error:
                    self.photo_cache[key] = None
            else:
                self.photo_cache[key] = None
        return self.photo_cache[key]

    def _draw_photo_background(self, key: str):
        """Cover-fit the photo behind the current frame and caption its source."""
        img = self._get_photo(key)
        if img is None:
            return
        w, h = self.screen.get_size()
        iw, ih = img.get_size()
        scale = max(w / iw, h / ih)
        sw, sh = int(iw * scale), int(ih * scale)
        scaled = pygame.transform.smoothscale(img, (sw, sh))
        self.screen.blit(scaled, ((w - sw) // 2, (h - sh) // 2))

        meta = self.photo_credits.get(key)
        if meta:
            caption = f"Фото: {meta['artist']} / Wikimedia Commons / {meta['license']}"
            surf = self.f_small.render(caption, True, (210, 207, 200))
            shadow = self.f_small.render(caption, True, (0, 0, 0))
            x, y = w - surf.get_width() - int(14 * self.scale), h - surf.get_height() - int(10 * self.scale)
            self.screen.blit(shadow, (x + 1, y + 1))
            self.screen.blit(surf, (x, y))

    def _load_fonts(self):
        w, h = self.screen.get_size()
        scale = h / 720
        self.f_title = pygame.font.SysFont("dejavusans", int(34 * scale), bold=True)
        self.f_head = pygame.font.SysFont("dejavusans", int(22 * scale), bold=True)
        self.f_body = pygame.font.SysFont("dejavusans", int(18 * scale))
        self.f_small = pygame.font.SysFont("dejavusans", int(14 * scale))
        self.margin = int(60 * scale)
        self.scale = scale

    def toggle_fullscreen(self):
        if self.fullscreen:
            self.screen = pygame.display.set_mode(self.windowed_size, pygame.RESIZABLE)
            self.fullscreen = False
        else:
            self.windowed_size = self.screen.get_size()
            info = pygame.display.Info()
            self.screen = pygame.display.set_mode((info.current_w, info.current_h), pygame.FULLSCREEN)
            self.fullscreen = True
        self._load_fonts()

    def run(self):
        while self.running:
            for event in pygame.event.get():
                self._handle_event(event)
            self._draw()
            self.clock.tick(60)
        pygame.quit()

    # ---------------------------------------------------------- events ----

    def _handle_event(self, event):
        if event.type == pygame.QUIT:
            self.running = False
        elif event.type == pygame.VIDEORESIZE and not self.fullscreen:
            self.windowed_size = (event.w, event.h)
            self.screen = pygame.display.set_mode(self.windowed_size, pygame.RESIZABLE)
            self._load_fonts()
        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_F11:
                self.toggle_fullscreen()
            elif event.key == pygame.K_ESCAPE:
                if self.fullscreen:
                    self.toggle_fullscreen()
            elif self.mode == "creation" and self.name_active:
                if event.key == pygame.K_BACKSPACE:
                    self.name_buf = self.name_buf[:-1]
                elif event.key == pygame.K_RETURN:
                    self.name_active = False
            elif self.mode in ("story", "ending"):
                if pygame.K_1 <= event.key <= pygame.K_9:
                    self._pick_numbered(event.key - pygame.K_1)
        elif event.type == pygame.TEXTINPUT and self.mode == "creation" and self.name_active:
            if len(self.name_buf) < 40:
                self.name_buf += event.text
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            for c in self.clickables:
                if c.rect.collidepoint(event.pos):
                    c.action()
                    break
        elif event.type == pygame.MOUSEWHEEL and self.mode == "ending":
            max_scroll = max(0, getattr(self, "content_height", 0) - self.screen.get_height())
            self.scroll = min(max_scroll, max(0, self.scroll - event.y * 30))

    def _pick_numbered(self, index: int):
        for c in self.clickables:
            if getattr(c, "choice_index", None) == index:
                c.action()
                return

    # ----------------------------------------------------------- logic ----

    def _start_game(self):
        if not (self.name_buf.strip() and self.profession_sel and self.city_sel):
            return
        self.state.name = self.name_buf.strip()
        self.state.profession = self.profession_sel
        self.state.city = self.city_sel
        self.state.node = START_NODE
        self.mode = "story"
        state_mod.save(self.state)

    def _choose(self, nxt, fx):
        if fx:
            fx(self.state)
        target = nxt(self.state) if callable(nxt) else nxt
        if target == "FINALE":
            self.mode = "ending"
            state_mod.clear()
        else:
            self.state.node = target
            state_mod.save(self.state)

    def _restart(self):
        state_mod.clear()
        self.state = state_mod.State()
        self.name_buf = ""
        self.profession_sel = ""
        self.city_sel = ""
        self.name_active = True
        self.scroll = 0
        self.mode = "creation"

    # ------------------------------------------------------------ draw ----

    def _draw(self):
        self.screen.fill(BG)
        self.clickables = []
        if self.mode == "creation":
            self._draw_creation()
        elif self.mode == "story":
            self._draw_story()
        else:
            self._draw_ending()
        pygame.display.flip()

    def _button(self, rect: pygame.Rect, text: str, font, selected=False, index=None):
        pygame.draw.rect(self.screen, SURFACE, rect, border_radius=4)
        border = ACCENT if selected else LINE
        pygame.draw.rect(self.screen, border, rect, width=2, border_radius=4)
        surf = font.render(text, True, FG)
        self.screen.blit(surf, (rect.x + 14, rect.y + (rect.h - surf.get_height()) // 2))
        return rect

    def _draw_creation(self):
        w, h = self.screen.get_size()
        m = self.margin
        y = m
        self.screen.blit(self.f_title.render("ТОЧКА НЕВОЗВРАТА", True, ACCENT), (m, y))
        y += int(self.f_title.get_height() * 1.4)
        self.screen.blit(self.f_small.render(
            "2020-2030 · вымышленный герой на фоне реальной истории", True, MUTED), (m, y))
        y += int(self.f_small.get_height() * 2.2)

        self.screen.blit(self.f_head.render("Имя", True, MUTED), (m, y))
        y += int(self.f_head.get_height() * 1.3)
        name_rect = pygame.Rect(m, y, min(500, w - 2 * m), int(44 * self.scale))
        pygame.draw.rect(self.screen, SURFACE, name_rect, border_radius=4)
        pygame.draw.rect(self.screen, ACCENT if self.name_active else LINE, name_rect, width=2, border_radius=4)
        cursor = "│" if (pygame.time.get_ticks() // 500) % 2 == 0 and self.name_active else ""
        self.screen.blit(self.f_body.render(self.name_buf + cursor, True, FG),
                          (name_rect.x + 12, name_rect.y + 8))
        self.clickables.append(Rect(name_rect, lambda: setattr(self, "name_active", True)))
        y += name_rect.h + int(26 * self.scale)

        y = self._chip_row("Профессия", PROFESSIONS, self.profession_sel,
                            lambda v: setattr(self, "profession_sel", v), m, y, w)
        y = self._chip_row("Город", CITIES, self.city_sel,
                            lambda v: setattr(self, "city_sel", v), m, y, w)

        btn = pygame.Rect(m, y + int(10 * self.scale), int(220 * self.scale), int(48 * self.scale))
        ready = bool(self.name_buf.strip() and self.profession_sel and self.city_sel)
        pygame.draw.rect(self.screen, ACCENT if ready else LINE, btn, border_radius=4)
        label = self.f_body.render("Начать историю", True, (255, 242, 238) if ready else MUTED)
        self.screen.blit(label, (btn.x + (btn.w - label.get_width()) // 2,
                                  btn.y + (btn.h - label.get_height()) // 2))
        if ready:
            self.clickables.append(Rect(btn, self._start_game))

        hint = self.f_small.render("F11 — полноэкранный режим", True, MUTED)
        self.screen.blit(hint, (m, h - m // 2))

    def _chip_row(self, label, options, selected, setter, m, y, w):
        self.screen.blit(self.f_head.render(label, True, MUTED), (m, y))
        y += int(self.f_head.get_height() * 1.3)
        x = m
        row_h = int(40 * self.scale)
        for opt in options:
            width = self.f_body.size(opt)[0] + int(28 * self.scale)
            if x + width > w - m:
                x = m
                y += row_h + int(10 * self.scale)
            rect = pygame.Rect(x, y, width, row_h)
            self._button(rect, opt, self.f_body, selected=(selected == opt))
            self.clickables.append(Rect(rect, (lambda v=opt: setter(v))))
            x += width + int(10 * self.scale)
        return y + row_h + int(26 * self.scale)

    def _draw_story(self):
        w, h = self.screen.get_size()
        m = self.margin
        node = NODES[self.state.node]
        if node.get("photo"):
            self._draw_photo_background(node["photo"])
        y = m

        header = f"{node['date']}   ·   {self.state.format(node['place'])}"
        self.screen.blit(self.f_small.render(header, True, ACCENT), (m, y))
        y += int(self.f_small.get_height() * 2)
        pygame.draw.line(self.screen, LINE, (m, y), (w - m, y), 1)
        y += int(24 * self.scale)

        body = self.state.format(node["text"])
        for line in wrap_text(self.f_body, body, w - 2 * m):
            if line:
                self.screen.blit(self.f_body.render(line, True, FG), (m, y))
            y += int(self.f_body.get_height() * 1.4)

        if node.get("source"):
            y += int(10 * self.scale)
            for line in wrap_text(self.f_small, "Источник: " + node["source"], w - 2 * m):
                self.screen.blit(self.f_small.render(line, True, MUTED), (m, y))
                y += int(self.f_small.get_height() * 1.3)

        btn_y = h - m - len(node["choices"]) * (int(54 * self.scale))
        btn_y = max(btn_y, y + int(20 * self.scale))
        for i, (label, tag, nxt, fx) in enumerate(node["choices"]):
            text = f"{i + 1}.  {label}" + (f"   ({tag})" if tag else "")
            rect = pygame.Rect(m, btn_y, w - 2 * m, int(44 * self.scale))
            self._button(rect, text, self.f_body)
            cr = Rect(rect, (lambda n=nxt, f=fx: self._choose(n, f)))
            cr.choice_index = i
            self.clickables.append(cr)
            btn_y += int(54 * self.scale)

    def _draw_ending(self):
        w, h = self.screen.get_size()
        m = self.margin
        kind = compute_ending(self.state)
        ending = ENDINGS[kind]

        y = m - self.scroll
        title = self.f_title.render(ending["headline"], True, ACCENT)
        self.screen.blit(title, ((w - title.get_width()) // 2, y))
        y += int(title.get_height() * 1.3)
        sub = self.f_head.render(ending["sub"], True, MUTED)
        self.screen.blit(sub, ((w - sub.get_width()) // 2, y))
        y += int(sub.get_height() * 2)

        card = pygame.Rect(m, y, w - 2 * m, int(90 * self.scale))
        pygame.draw.rect(self.screen, SURFACE, card, border_radius=4)
        pygame.draw.rect(self.screen, LINE, card, width=1, border_radius=4)
        info = f"2030 · Российская Федерация · Президент: ?   —   {self.state.name}, {self.state.profession}, {self.state.city}"
        info_lines = wrap_text(self.f_small, info, card.w - int(28 * self.scale))
        for i, line in enumerate(info_lines):
            self.screen.blit(
                self.f_small.render(line, True, FG),
                (card.x + 14, card.y + 14 + i * int(self.f_small.get_height() * 1.4)),
            )
        y += card.h + int(24 * self.scale)

        note = self.state.format(ending["note"])
        for line in wrap_text(self.f_body, note, w - 2 * m):
            if line:
                self.screen.blit(self.f_body.render(line, True, FG), (m, y))
            y += int(self.f_body.get_height() * 1.4)
        y += int(20 * self.scale)

        if ending["show_dedication"]:
            pygame.draw.line(self.screen, LINE, (m, y), (w - m, y), 1)
            y += int(16 * self.scale)
            self.screen.blit(self.f_head.render("За вас боролись", True, ACCENT), (m, y))
            y += int(self.f_head.get_height() * 1.6)
            for line in DEDICATION:
                self.screen.blit(self.f_body.render(line, True, FG), (m, y))
                y += int(self.f_body.get_height() * 1.3)
            y += int(10 * self.scale)
            you = f"{self.state.name} — {self.state.profession}, {self.state.city}"
            self.screen.blit(self.f_body.render(you, True, ACCENT), (m, y))
            y += int(self.f_body.get_height() * 1.6)
            disc = ("Это вымышленная история и вымышленный персонаж. Люди выше — реальные "
                    "общественные деятели, журналисты и правозащитники; список — дань уважения, "
                    "а не часть сюжета, и не подразумевает их участия в этой истории.")
            for line in wrap_text(self.f_small, disc, w - 2 * m):
                self.screen.blit(self.f_small.render(line, True, MUTED), (m, y))
                y += int(self.f_small.get_height() * 1.3)

        y += int(20 * self.scale)
        btn = pygame.Rect(m, y, int(220 * self.scale), int(44 * self.scale))
        self._button(btn, "Начать заново", self.f_body)
        self.clickables.append(Rect(btn, self._restart))
        self.content_height = y + btn.h + m


def main():
    App().run()


if __name__ == "__main__":
    main()
