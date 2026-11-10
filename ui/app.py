"""Ten Winters — pygame front-end.

Everything is laid out relative to the real window height (design grid is
1080p), so the game renders natively at 720p, 1440p and 2160p. F11 toggles
true fullscreen at the desktop resolution; Esc opens the pause menu; M mutes.
"""
from __future__ import annotations

import json
import math
import os
import random
import sys

import pygame

from engine import state as state_mod
from engine.story import (CHAPTER_PHOTOS, CHAPTERS, CITIES, COUNTRY_CARD, DEDICATION, ENDINGS,
                          FALLBACK_PHOTOS, NODES, ORGS, PEOPLE, PROFESSIONS, START_NODE,
                          compute_ending, epilogue)


def resource_root() -> str:
    # PyInstaller unpacks bundled data into sys._MEIPASS
    return getattr(sys, "_MEIPASS", os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


ROOT = resource_root()
FONTS = os.path.join(ROOT, "assets", "fonts")
PHOTOS = os.path.join(ROOT, "assets", "photos")
AUDIO = os.path.join(ROOT, "assets", "audio")

# palette
INK = (10, 11, 13)
PAPER = (236, 231, 221)
MUTED = (150, 144, 134)
DIM = (96, 92, 86)
RED = (196, 48, 40)
RED_DARK = (120, 26, 22)
PANEL = (20, 21, 24)
WHITE = (250, 248, 244)
FLAG = [(255, 255, 255), (0, 57, 166), (213, 43, 30)]

TYPE_SPEED = 75          # characters per second
FADE_TIME = 0.35         # seconds
CHAPTER_CARD_TIME = 3.2  # seconds


# ============================================================== helpers ====

def wrap(font: pygame.font.Font, text: str, width: int) -> list[str]:
    lines: list[str] = []
    for para in text.split("\n"):
        if not para.strip():
            lines.append("")
            continue
        cur = ""
        for word in para.split(" "):
            trial = f"{cur} {word}" if cur else word
            if font.size(trial)[0] <= width or not cur:
                cur = trial
            else:
                lines.append(cur)
                cur = word
        lines.append(cur)
    return lines


def ease(t: float) -> float:
    t = max(0.0, min(1.0, t))
    return t * t * (3 - 2 * t)


class Button:
    def __init__(self, rect: pygame.Rect, action, label: str = "", key: str | None = None):
        self.rect, self.action, self.label, self.key = rect, action, label, key


# ============================================================== assets =====

class Fonts:
    FILES = {
        "display": "Oswald-Bold.ttf",
        "display_md": "Oswald-Medium.ttf",
        "serif": "PTSerif-Regular.ttf",
        "serif_b": "PTSerif-Bold.ttf",
        "serif_i": "PTSerif-Italic.ttf",
        "mono": "PTMono-Regular.ttf",
    }

    def __init__(self):
        self.cache: dict[tuple[str, int], pygame.font.Font] = {}

    def get(self, role: str, px: int) -> pygame.font.Font:
        px = max(8, int(px))
        key = (role, px)
        if key not in self.cache:
            path = os.path.join(FONTS, self.FILES[role])
            try:
                self.cache[key] = pygame.font.Font(path, px)
            except (OSError, FileNotFoundError):
                self.cache[key] = pygame.font.SysFont("dejavusans", px)
        return self.cache[key]


class Photos:
    def __init__(self):
        self.raw: dict[str, pygame.Surface | None] = {}
        self.scaled: dict[tuple, pygame.Surface] = {}
        self.credits: dict = {}
        try:
            with open(os.path.join(PHOTOS, "credits.json"), encoding="utf-8") as f:
                self.credits = json.load(f)
        except (OSError, json.JSONDecodeError):
            self.credits = {}

    def has(self, key: str | None) -> bool:
        return bool(key) and self._load(key) is not None

    def _load(self, key: str):
        if key not in self.raw:
            path = os.path.join(PHOTOS, key + ".jpg")
            try:
                self.raw[key] = pygame.image.load(path).convert() if os.path.exists(path) else None
            except pygame.error:
                self.raw[key] = None
        return self.raw[key]

    def cover(self, key: str, size: tuple[int, int], overscan: float = 1.06) -> pygame.Surface | None:
        img = self._load(key)
        if img is None:
            return None
        ck = (key, size, overscan)
        if ck not in self.scaled:
            w, h = size
            iw, ih = img.get_size()
            s = max(w / iw, h / ih) * overscan
            self.scaled[ck] = pygame.transform.smoothscale(img, (int(iw * s) + 1, int(ih * s) + 1))
        return self.scaled[ck]

    def caption(self, key: str) -> str | None:
        meta = self.credits.get(key)
        if not meta:
            return None
        where = "Wikimedia Commons" if "wikimedia.org" in meta.get("source_url", "") else None
        parts = [f"Фото: {meta['artist']}", where, meta["license"]]
        return " · ".join(p for p in parts if p)


class Audio:
    TRACKS = ("ambient", "tension", "grief", "victory")

    def __init__(self):
        self.ok = False
        self.muted = False
        self.current: str | None = None
        self.click_snd = None
        try:
            pygame.mixer.init(frequency=32000)
            self.ok = True
            path = os.path.join(AUDIO, "click.wav")
            if os.path.exists(path):
                self.click_snd = pygame.mixer.Sound(path)
                self.click_snd.set_volume(0.35)
        except pygame.error:
            self.ok = False

    def play(self, track: str | None, loop: bool = True):
        if not self.ok or not track or track == self.current:
            return
        path = os.path.join(AUDIO, track + ".ogg")
        if not os.path.exists(path):
            return
        self.current = track
        try:
            pygame.mixer.music.fadeout(800)
            pygame.mixer.music.load(path)
            pygame.mixer.music.set_volume(0 if self.muted else 0.7)
            pygame.mixer.music.play(-1 if loop else 0, fade_ms=1500)
        except pygame.error:
            pass

    def click(self):
        if self.ok and self.click_snd and not self.muted:
            self.click_snd.play()

    def toggle_mute(self):
        self.muted = not self.muted
        if self.ok:
            pygame.mixer.music.set_volume(0 if self.muted else 0.7)


# ============================================================ effects ======

class Atmosphere:
    """Film grain, vignette, bottom gradient and falling snow."""

    def __init__(self):
        self.size = (0, 0)
        self.vignette = None
        self.bottom = None
        self.grain = []
        rnd = random.Random(10)
        for _ in range(4):
            tile = pygame.Surface((256, 256), pygame.SRCALPHA)
            for _ in range(2600):
                v = rnd.randint(0, 255)
                tile.set_at((rnd.randrange(256), rnd.randrange(256)), (v, v, v, rnd.randint(10, 26)))
            self.grain.append(tile)
        self.flakes = [[random.random(), random.random(), random.uniform(0.3, 1.0)] for _ in range(140)]

    def resize(self, size):
        if size == self.size:
            return
        self.size = size
        w, h = size
        small = pygame.Surface((160, 90), pygame.SRCALPHA)
        for y in range(90):
            for x in range(160):
                dx, dy = (x - 80) / 80, (y - 45) / 45
                d = min(1.0, math.sqrt(dx * dx + dy * dy) / 1.25)
                small.set_at((x, y), (0, 0, 0, int(220 * d ** 2.2)))
        self.vignette = pygame.transform.smoothscale(small, size)
        grad = pygame.Surface((1, 256), pygame.SRCALPHA)
        for y in range(256):
            grad.set_at((0, y), (8, 8, 10, int(250 * ease(y / 255) ** 1.1)))
        self.bottom = pygame.transform.smoothscale(grad, (w, h))

    def snow(self, surf: pygame.Surface, dt: float, t: float, amount: float = 1.0):
        w, h = surf.get_size()
        n = int(len(self.flakes) * amount)
        for f in self.flakes[:n]:
            f[1] += dt * 0.035 * f[2]
            f[0] += dt * 0.01 * math.sin(t * 0.7 + f[2] * 10)
            if f[1] > 1.02:
                f[1], f[0] = -0.02, random.random()
            r = max(1, int(h / 900 * (1 + 1.6 * f[2])))
            a = int(70 + 110 * f[2])
            pygame.draw.circle(surf, (a, a, a + 6), (int(f[0] * w) % w, int(f[1] * h)), r)

    def overlay(self, surf: pygame.Surface, t: float, grain: bool = True):
        surf.blit(self.vignette, (0, 0))
        if grain:
            tile = self.grain[int(t * 18) % len(self.grain)]
            w, h = surf.get_size()
            ox, oy = int(t * 997) % 256, int(t * 613) % 256
            for x in range(-ox, w, 256):
                for y in range(-oy, h, 256):
                    surf.blit(tile, (x, y))


# =============================================================== app ========

class App:
    def __init__(self):
        pygame.init()
        pygame.display.set_caption("Ten Winters")
        pygame.key.set_repeat(400, 40)
        info = pygame.display.Info()
        start = (min(1600, int(info.current_w * 0.85)) or 1280, 0)
        start = (start[0], int(start[0] * 9 / 16))
        self.windowed_size = start
        self.fullscreen = False
        self.screen = pygame.display.set_mode(self.windowed_size, pygame.RESIZABLE)
        self.clock = pygame.time.Clock()
        self.fonts = Fonts()
        self.photos = Photos()
        self.audio = Audio()
        self.fx = Atmosphere()
        self.fx.resize(self.screen.get_size())

        self.veils: dict[tuple, pygame.Surface] = {}
        self.t = 0.0
        self.mode = "menu"
        self.paused = False
        self.saved = state_mod.load()
        self.state = state_mod.State()
        self.buttons: list[Button] = []
        self.focus = 0
        self.hover = -1

        # character creation
        self.name_buf = ""
        self.gender = "m"
        self.profession = ""
        self.city = ""

        # story playback
        self.node_t = 0.0
        self.reveal = 0.0
        self.text_cache_key = None
        self.lay: dict = {}
        self.page = 0
        self.chapter_shown = 0
        self.card_t = 0.0
        self.fade = 1.0
        self.pending = None

        # ending
        self.ending = None
        self.credits_t = 0.0
        self.scroll = 0.0
        self.running = True
        self.audio.play("ambient")

    def veil(self, color, alpha: int) -> pygame.Surface:
        key = (self.screen.get_size(), color, alpha)
        if key not in self.veils:
            if len(self.veils) > 40:
                self.veils.clear()
            surf = pygame.Surface(self.screen.get_size())
            surf.fill(color)
            surf.set_alpha(alpha)
            self.veils[key] = surf
        return self.veils[key]

    def scanlines(self) -> pygame.Surface:
        key = (self.screen.get_size(), "scan")
        if key not in self.veils:
            w, h = self.screen.get_size()
            surf = pygame.Surface((w, h), pygame.SRCALPHA)
            for y in range(0, h, max(3, self.px(4))):
                pygame.draw.line(surf, (0, 0, 0, 55), (0, y), (w, y))
            self.veils[key] = surf
        return self.veils[key]

    # ----------------------------------------------------------- sizing --

    @property
    def s(self) -> float:
        return self.screen.get_height() / 1080

    def px(self, v: float) -> int:
        return max(1, int(v * self.s))

    def margin(self) -> int:
        w = self.screen.get_width()
        return max(self.px(90), (w - self.px(1500)) // 2)

    def toggle_fullscreen(self):
        if self.fullscreen:
            self.screen = pygame.display.set_mode(self.windowed_size, pygame.RESIZABLE)
        else:
            self.windowed_size = self.screen.get_size()
            info = pygame.display.Info()
            self.screen = pygame.display.set_mode((info.current_w, info.current_h), pygame.FULLSCREEN)
        self.fullscreen = not self.fullscreen
        self.fx.resize(self.screen.get_size())
        self.text_cache_key = None

    # -------------------------------------------------------- main loop --

    def run(self):
        while self.running:
            dt = min(self.clock.tick(60) / 1000, 0.05)
            for event in pygame.event.get():
                self.handle(event)
            self.update(dt)
            self.draw(dt)
        pygame.quit()

    def update(self, dt: float):
        self.t += dt
        if self.paused:
            return
        if self.pending is not None:
            self.fade = min(1.0, self.fade + dt / FADE_TIME)
            if self.fade >= 1.0:
                action, self.pending = self.pending, None
                action()
        else:
            self.fade = max(0.0, self.fade - dt / FADE_TIME)
        if self.mode == "chapter":
            self.card_t += dt
            if self.card_t >= CHAPTER_CARD_TIME and self.pending is None:
                self.transition(lambda: self.set_mode("story"))
        elif self.mode == "story":
            self.node_t += dt
            self.reveal += dt * TYPE_SPEED
        elif self.mode in ("ending", "epilogue"):
            self.credits_t += dt

    def transition(self, action):
        if self.pending is None:
            self.pending = action

    def set_mode(self, mode: str):
        self.mode = mode
        self.focus = 0
        self.scroll = 0.0
        if mode == "story":
            self.node_t = 0.0
            self.reveal = 0.0
            self.page = 0
            self.text_cache_key = None
            node = NODES[self.state.node]
            self.audio.play(node.get("music", "ambient"))

    # ----------------------------------------------------------- input --

    def handle(self, event):
        if event.type == pygame.QUIT:
            self.running = False
            return
        if event.type == pygame.VIDEORESIZE and not self.fullscreen:
            self.windowed_size = (max(640, event.w), max(360, event.h))
            self.screen = pygame.display.set_mode(self.windowed_size, pygame.RESIZABLE)
            self.fx.resize(self.screen.get_size())
            self.text_cache_key = None
            return
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_F11:
                self.toggle_fullscreen()
                return
            if event.key == pygame.K_m and not (self.mode == "create"):
                self.audio.toggle_mute()
                return
            if event.key == pygame.K_ESCAPE:
                if self.mode in ("story", "chapter", "ending", "epilogue", "dossier"):
                    self.paused = not self.paused
                    self.focus = 0
                elif self.mode == "create":
                    self.mode = "menu"
                return
        if self.mode == "create" and not self.paused and self.handle_create_keys(event):
            return
        if event.type == pygame.MOUSEMOTION:
            self.hover = next((i for i, b in enumerate(self.buttons) if b.rect.collidepoint(event.pos)), -1)
            if self.hover >= 0:
                self.focus = self.hover
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.skip_if_animating():
                return
            for b in self.buttons:
                if b.rect.collidepoint(event.pos):
                    self.press(b)
                    return
        elif event.type == pygame.MOUSEWHEEL and self.mode in ("ending", "dossier"):
            self.scroll = max(0.0, self.scroll - event.y * self.px(60))
        elif event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_SPACE, pygame.K_RETURN, pygame.K_KP_ENTER):
                if self.skip_if_animating():
                    return
                if self.buttons and 0 <= self.focus < len(self.buttons):
                    self.press(self.buttons[self.focus])
            elif event.key in (pygame.K_DOWN, pygame.K_TAB, pygame.K_RIGHT):
                if self.buttons:
                    self.focus = (self.focus + 1) % len(self.buttons)
            elif event.key in (pygame.K_UP, pygame.K_LEFT):
                if self.buttons:
                    self.focus = (self.focus - 1) % len(self.buttons)
            elif pygame.K_1 <= event.key <= pygame.K_9 and self.mode == "story" and not self.paused:
                if self.skip_if_animating():
                    return
                idx = event.key - pygame.K_1
                choices = [b for b in self.buttons if b.key == "choice"]
                if idx < len(choices):
                    self.press(choices[idx])

    def skip_if_animating(self) -> bool:
        if self.paused or self.pending is not None:
            return False
        if self.mode == "chapter":
            self.transition(lambda: self.set_mode("story"))
            return True
        if self.mode == "story":
            if self.reveal < self.page_chars():
                self.reveal = 1e9
                return True
            if not self.on_last_page():
                self.page += 1
                self.reveal = 0.0
                return True
        if self.mode in ("ending", "epilogue") and self.credits_t < 30:
            self.credits_t = 999
            return True
        return False

    def press(self, b: Button):
        self.audio.click()
        b.action()

    def handle_create_keys(self, event) -> bool:
        if event.type == pygame.TEXTINPUT:
            if len(self.name_buf) < 24 and event.text.isprintable():
                self.name_buf += event.text
            return True
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_BACKSPACE:
                self.name_buf = self.name_buf[:-1]
                return True
            if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                self.start_story()
                return True
            if event.unicode and event.unicode.isprintable():
                return True  # the character arrives as TEXTINPUT
        return False

    # ----------------------------------------------------------- flow --

    def new_game(self):
        self.name_buf, self.gender, self.profession, self.city = "", "m", "", ""
        self.transition(lambda: setattr(self, "mode", "create"))

    def continue_game(self):
        if not self.saved:
            return
        self.state = self.saved
        self.chapter_shown = NODES[self.state.node]["chapter"]
        self.transition(lambda: self.set_mode("story"))

    def start_story(self):
        if not (self.name_buf.strip() and self.profession and self.city):
            return
        self.state = state_mod.State(name=self.name_buf.strip(), gender=self.gender,
                                     profession=self.profession, city=self.city, node=START_NODE)
        state_mod.save(self.state)
        self.chapter_shown = 0
        self.transition(self.enter_node)

    def enter_node(self):
        node = NODES[self.state.node]
        if node["chapter"] != self.chapter_shown:
            self.chapter_shown = node["chapter"]
            self.card_t = 0.0
            self.mode = "chapter"
            self.audio.play(node.get("music", "ambient"))
        else:
            self.set_mode("story")

    def choose(self, nxt, fx):
        def go():
            if fx:
                fx(self.state)
            target = nxt(self.state) if callable(nxt) else nxt
            if target == "FINALE":
                self.ending = compute_ending(self.state)
                self.credits_t = 0.0
                state_mod.clear()
                self.saved = None
                self.set_mode("ending")
                self.audio.play(ENDINGS[self.ending]["music"], loop=self.ending not in ("win", "win_prison", "win_return"))
            else:
                self.state.node = target
                state_mod.save(self.state)
                self.saved = self.state
                self.enter_node()
        self.transition(go)

    def to_menu(self):
        self.paused = False
        self.saved = state_mod.load()
        self.transition(lambda: (setattr(self, "mode", "menu"), self.audio.play("ambient")))

    # ============================================================ draw ====

    def draw(self, dt: float):
        self.buttons = []
        self.screen.fill(INK)
        {"menu": self.draw_menu, "create": self.draw_create, "chapter": self.draw_chapter,
         "story": self.draw_story, "ending": self.draw_ending, "epilogue": self.draw_epilogue,
         "dossier": self.draw_dossier}[self.mode](dt)
        if self.paused:
            self.buttons = []
            self.draw_pause()
        if self.fade > 0:
            self.screen.blit(self.veil(INK, int(255 * ease(self.fade)) // 8 * 8), (0, 0))
        if self.audio.muted:
            f = self.fonts.get("mono", self.px(18))
            surf = f.render("ЗВУК ВЫКЛ · M", True, DIM)
            self.screen.blit(surf, (self.px(24), self.px(20)))
        pygame.display.flip()

    # ------------------------------------------------------- primitives --

    def background(self, key: str | None, dt: float, darkness: int = 150, snow: float = 1.0,
                   caption: bool = True):
        w, h = self.screen.get_size()
        img = self.photos.cover(key, (w, h)) if self.photos.has(key) else None
        if img:
            iw, ih = img.get_size()
            drift = math.sin(self.t * 0.05)
            x = -(iw - w) / 2 + drift * (iw - w) / 2
            y = -(ih - h) / 2
            self.screen.blit(img, (int(x), int(y)))
            self.screen.blit(self.veil(INK, darkness), (0, 0))
        self.fx.snow(self.screen, dt, self.t, snow)
        self.fx.overlay(self.screen, self.t)
        if img and caption:
            cap = self.photos.caption(key)
            if cap:
                f = self.fonts.get("mono", self.px(15))
                surf = f.render(cap, True, DIM)
                self.screen.blit(surf, (w - surf.get_width() - self.px(24), h - surf.get_height() - self.px(16)))

    def text(self, role, size, s, color, pos, anchor="topleft", alpha=255):
        surf = self.fonts.get(role, self.px(size)).render(s, True, color)
        if alpha < 255:
            surf.set_alpha(alpha)
        r = surf.get_rect(**{anchor: pos})
        self.screen.blit(surf, r)
        return r

    def button(self, rect: pygame.Rect, label: str, action, primary=False, selected=False,
               role="display_md", size=26, key=None, enabled=True):
        idx = len(self.buttons)
        focused = idx == self.focus and enabled
        if enabled:
            self.buttons.append(Button(rect, action, label, key))
        if primary and enabled:
            bg = RED if not focused else (220, 62, 52)
            pygame.draw.rect(self.screen, bg, rect)
            color = WHITE
        else:
            bg = (34, 35, 39) if focused or selected else PANEL
            surf = pygame.Surface(rect.size, pygame.SRCALPHA)
            surf.fill((*bg, 225))
            self.screen.blit(surf, rect)
            if selected:
                pygame.draw.rect(self.screen, RED, rect, width=self.px(2))
            elif focused:
                pygame.draw.rect(self.screen, (70, 70, 74), rect, width=1)
            color = PAPER if enabled else DIM
        f = self.fonts.get(role, self.px(size))
        surf = f.render(label, True, color)
        self.screen.blit(surf, surf.get_rect(center=rect.center))

    # ------------------------------------------------------------- menu --

    def draw_menu(self, dt):
        w, h = self.screen.get_size()
        self.background("kremlin_night" if self.photos.has("kremlin_night") else "kremlin", dt, darkness=175, snow=1.4)
        m = self.margin()
        y = int(h * 0.26)
        self.text("mono", 22, "2020 — 2030", RED, (m, y))
        y += self.px(40)
        title = self.text("display", 150, "TEN WINTERS", WHITE, (m - self.px(6), y))
        y = title.bottom + self.px(4)
        self.text("serif_i", 34, "Десять зим. Обычный человек и десятилетие, которое изменило страну.",
                  MUTED, (m, y))
        y += self.px(110)
        bw, bh = self.px(380), self.px(64)
        if self.saved:
            self.button(pygame.Rect(m, y, bw, bh), "ПРОДОЛЖИТЬ", self.continue_game, primary=True)
            y += bh + self.px(14)
        self.button(pygame.Rect(m, y, bw, bh), "НОВАЯ ИГРА", self.new_game, primary=not self.saved)
        y += bh + self.px(14)
        self.button(pygame.Rect(m, y, bw, bh), "КТО ЭТИ ЛЮДИ", lambda: self.transition(lambda: self.set_mode("dossier")))
        y += bh + self.px(14)
        self.button(pygame.Rect(m, y, bw, bh), "ВЫХОД", lambda: setattr(self, "running", False))
        self.text("mono", 16, "F11 — полный экран   ·   M — звук   ·   Esc — пауза",
                  DIM, (m, h - self.px(50)))
        self.text("mono", 16, "Вымышленный герой. Реальная история. Реплики реальных людей — только подлинные.",
                  DIM, (w - m, h - self.px(50)), anchor="topright")

    # ----------------------------------------------------------- create --

    def draw_create(self, dt):
        w, h = self.screen.get_size()
        self.background(None, dt, snow=0.8)
        m = self.margin()
        y = self.px(90)
        self.text("mono", 20, "АВГУСТ 2020", RED, (m, y))
        y += self.px(36)
        self.text("display", 64, "КТО ТЫ, ПОКА ЕЩЁ НИЧЕГО НЕ СЛУЧИЛОСЬ?", WHITE, (m, y))
        y += self.px(120)

        # name
        self.text("mono", 18, "ИМЯ", MUTED, (m, y))
        y += self.px(32)
        field = pygame.Rect(m, y, self.px(560), self.px(66))
        pygame.draw.rect(self.screen, PANEL, field)
        pygame.draw.line(self.screen, RED, field.bottomleft, field.bottomright, self.px(3))
        caret = "|" if int(self.t * 2) % 2 == 0 else " "
        shown = self.name_buf + caret if self.name_buf else caret + " введи имя"
        self.text("serif", 34, shown, PAPER if self.name_buf else DIM, (field.x + self.px(18), field.centery), anchor="midleft")

        # gender
        gx = field.right + self.px(60)
        self.text("mono", 18, "ПОЛ", MUTED, (gx, y - self.px(32)))
        for i, (g, label) in enumerate((("m", "МУЖЧИНА"), ("f", "ЖЕНЩИНА"))):
            r = pygame.Rect(gx + i * self.px(210), y, self.px(196), self.px(66))
            self.button(r, label, (lambda g=g: setattr(self, "gender", g)), selected=self.gender == g, size=24)
        y += self.px(110)

        def chips(label, options, current, setter, y):
            self.text("mono", 18, label, MUTED, (m, y))
            y += self.px(32)
            x = m
            ch = self.px(54)
            for key, text in options:
                f = self.fonts.get("serif", self.px(26))
                cw = f.size(text)[0] + self.px(44)
                if x + cw > w - m:
                    x = m
                    y += ch + self.px(12)
                self.button(pygame.Rect(x, y, cw, ch), text, (lambda k=key: setter(k)),
                            selected=current == key, role="serif", size=26)
                x += cw + self.px(12)
            return y + ch + self.px(40)

        f = self.gender == "f"
        profs = [(k, v[1] if f else v[0]) for k, v in PROFESSIONS.items()]
        y = chips("ПРОФЕССИЯ", [(k, t.capitalize()) for k, t in profs], self.profession,
                  lambda k: setattr(self, "profession", k), y)
        y = chips("ГОРОД", [(c, c) for c in CITIES], self.city, lambda k: setattr(self, "city", k), y)

        ready = bool(self.name_buf.strip() and self.profession and self.city)
        r = pygame.Rect(m, max(y, h - self.px(150)), self.px(420), self.px(70))
        self.button(r, "НАЧАТЬ ИГРУ", self.start_story, primary=True, size=30, enabled=ready)
        self.text("mono", 16, "Esc — назад", DIM, (r.right + self.px(30), r.centery), anchor="midleft")

    # ----------------------------------------------------------- chapter --

    def draw_chapter(self, dt):
        w, h = self.screen.get_size()
        node = NODES[self.state.node]
        num = node["chapter"]
        title, when = CHAPTERS[num]
        self.background(self.scene_photo(node), dt, darkness=215, snow=1.2)
        a = ease(min(self.card_t / 0.8, 1.0, (CHAPTER_CARD_TIME - self.card_t) / 0.6 + 0.2))
        alpha = int(255 * a)
        cy = h // 2
        self.text("mono", 24, f"ГЛАВА {num} ИЗ 12", RED, (w // 2, cy - self.px(110)), anchor="center", alpha=alpha)
        self.text("display", 120, title.upper(), WHITE, (w // 2, cy), anchor="center", alpha=alpha)
        self.text("serif_i", 36, when, MUTED, (w // 2, cy + self.px(100)), anchor="center", alpha=alpha)

    # ------------------------------------------------------------- story --

    def scene_photo(self, node) -> str | None:
        """The node's own photo if present, else the chapter's, else any fallback."""
        wanted = self.state.pick(node.get("photo"))
        if isinstance(wanted, str):
            wanted = [wanted]
        for key in list(wanted or []) + CHAPTER_PHOTOS.get(node["chapter"], []) + FALLBACK_PHOTOS:
            if self.photos.has(key):
                return key
        return None

    def panel_rect(self) -> pygame.Rect:
        w, h = self.screen.get_size()
        m = self.margin()
        top = int(h * 0.585)
        return pygame.Rect(m, top, w - 2 * m, h - top - self.px(34))

    def layout(self):
        """Split the node's text into pages that fit the text panel."""
        node = NODES[self.state.node]
        key = (self.state.node, self.screen.get_size())
        if key == self.text_cache_key:
            return self.lay
        self.text_cache_key = key
        panel = self.panel_rect()
        pad = self.px(40)
        inner_w = panel.w - 2 * pad
        inner_h = panel.h - 2 * pad - self.px(10)
        bf = self.fonts.get("serif", self.px(31))
        lh = int(bf.get_linesize() * 1.25)
        per_page = max(2, inner_h // lh)
        lines = []
        for para in self.state.format(node["text"]).split("\n\n"):
            if lines:
                lines.append("")
            lines.extend(wrap(bf, para.replace("\n", " "), inner_w))
        pages = []
        while lines:
            chunk = lines[:per_page]
            while chunk and chunk[-1] == "":
                chunk.pop()
            pages.append({"kind": "body", "lines": chunk})
            lines = lines[per_page:]
            while lines and lines[0] == "":
                lines.pop(0)
        q = node.get("quote")
        if q:
            qf = self.fonts.get("serif_i", self.px(38))
            pages.append({"kind": "quote", "lines": wrap(qf, f"«{q['text']}»", inner_w - self.px(40)),
                          "who": q["who"], "src": q["source"]})
        cf = self.fonts.get("serif", self.px(27))
        cw = min(self.px(1150), panel.w)
        choices = []
        for label, nxt, fx in node["choices"]:
            cl = wrap(cf, self.state.format(label), cw - self.px(110))[:2]
            choices.append((cl, self.px(62 if len(cl) == 1 else 90), nxt, fx))
        self.lay = {"pages": pages, "lh": lh, "pad": pad, "choices": choices, "cw": cw}
        return self.lay

    def page_chars(self) -> int:
        page = self.layout()["pages"][self.page]
        return sum(len(l) for l in page["lines"])

    def total_chars(self) -> int:
        return self.page_chars()

    def on_last_page(self) -> bool:
        return self.page >= len(self.layout()["pages"]) - 1

    def draw_story(self, dt):
        w, h = self.screen.get_size()
        node = NODES[self.state.node]
        photo = self.scene_photo(node)
        self.background(photo, dt, darkness=105, snow=0.6, caption=False)
        self.screen.blit(self.fx.bottom, (0, 0))
        lay = self.layout()
        m = self.margin()

        # header over the photo
        y = self.px(54)
        chap = f"ГЛАВА {node['chapter']} · {CHAPTERS[node['chapter']][0].upper()}"
        self.text("mono", 19, chap, PAPER, (m, y))
        y += self.px(32)
        self.text("display", 46, self.state.format(node["date"]).upper(), WHITE, (m, y))
        self.text("serif_i", 26, self.state.format(node["place"]), PAPER, (m, y + self.px(62)))
        if node.get("pressure"):
            pulse = 0.5 + 0.5 * math.sin(self.t * 4)
            r = self.text("mono", 18, "ДАВЛЕНИЕ", RED, (w - m, self.px(58)), anchor="topright",
                          alpha=int(140 + 115 * pulse))
            pygame.draw.circle(self.screen, RED, (r.left - self.px(16), r.centery), self.px(6))

        # text panel
        panel = self.panel_rect()
        surf = pygame.Surface(panel.size, pygame.SRCALPHA)
        surf.fill((9, 10, 12, 228))
        self.screen.blit(surf, panel)
        pygame.draw.rect(self.screen, RED, (panel.x, panel.y, panel.w, self.px(3)))
        cap = self.photos.caption(photo) if photo else None
        if cap:
            self.text("mono", 14, cap, MUTED, (panel.right, h - self.px(8)), anchor="bottomright")
        page = lay["pages"][self.page]
        x = panel.x + lay["pad"]
        y = panel.y + lay["pad"]
        budget = self.reveal
        if page["kind"] == "body":
            bf = self.fonts.get("serif", self.px(31))
            for line in page["lines"]:
                shown = line[: max(0, int(budget))]
                budget -= len(line)
                if shown:
                    self.screen.blit(bf.render(shown, True, PAPER), (x, y))
                y += lay["lh"] if line else lay["lh"] // 2
        else:
            qf = self.fonts.get("serif_i", self.px(38))
            top = y
            for line in page["lines"]:
                shown = line[: max(0, int(budget))]
                budget -= len(line)
                if shown:
                    self.screen.blit(qf.render(shown, True, WHITE), (x + self.px(36), y))
                y += int(qf.get_linesize() * 1.15)
            pygame.draw.rect(self.screen, RED, (x, top + self.px(6), self.px(5), y - top - self.px(6)))
            if budget > 0:
                y += self.px(10)
                self.text("display_md", 24, "— " + page["who"].upper(), PAPER, (x + self.px(36), y))
                self.text("mono", 16, page["src"], MUTED, (x + self.px(36), y + self.px(36)))

        done = self.reveal >= self.page_chars()
        if not done:
            return
        if not self.on_last_page():
            if int(self.t * 2) % 2 == 0:
                bx, by = panel.right - self.px(40), panel.bottom - self.px(34)
                pygame.draw.polygon(self.screen, RED, [(bx - self.px(12), by - self.px(8)),
                                                       (bx + self.px(12), by - self.px(8)), (bx, by + self.px(6))])
            self.text("mono", 15, "клик / пробел — дальше", DIM,
                      (panel.right - self.px(70), panel.bottom - self.px(42)), anchor="topright")
            return

        # source, quietly, above the panel
        if node.get("source"):
            sf = self.fonts.get("mono", self.px(16))
            sy = panel.y - self.px(14)
            for line in reversed(wrap(sf, "ИСТОЧНИК: " + node["source"], panel.w)):
                r = self.text("mono", 16, line, PAPER, (panel.x, sy), anchor="bottomleft")
                sy = r.top - self.px(2)
            src_top = sy
        else:
            src_top = panel.y - self.px(14)

        # choices float above the panel, centred
        gap = self.px(12)
        total = sum(rh + gap for _, rh, _, _ in lay["choices"])
        by = src_top - self.px(18) - total
        cw = lay["cw"]
        cx = w // 2 - cw // 2
        cf = self.fonts.get("serif", self.px(27))
        appear = ease(min(1.0, (self.reveal - self.page_chars()) / TYPE_SPEED / 0.35 + 0.15))
        for i, (lines, rh, nxt, fx) in enumerate(lay["choices"]):
            rect = pygame.Rect(cx, by, cw, rh)
            focused = i == self.focus
            box = pygame.Surface(rect.size, pygame.SRCALPHA)
            box.fill((44, 22, 22, 240) if focused else (12, 13, 16, 230))
            box.set_alpha(int(255 * appear))
            self.screen.blit(box, rect)
            pygame.draw.rect(self.screen, RED if focused else (70, 70, 76), rect, width=self.px(2) if focused else 1)
            self.text("display", 28, str(i + 1), RED if focused else MUTED,
                      (rect.x + self.px(34), rect.centery), anchor="midleft")
            lh = cf.get_linesize()
            ty = rect.centery - lh * len(lines) // 2
            for line in lines:
                self.screen.blit(cf.render(line, True, WHITE), (rect.x + self.px(80), ty))
                ty += lh
            self.buttons.append(Button(rect, (lambda n=nxt, f=fx: self.choose(n, f)), lines[0], "choice"))
            by += rh + gap

    # ------------------------------------------------------------ ending --

    def draw_ending(self, dt):
        e = ENDINGS[self.ending]
        if e["credits"]:
            self.draw_victory(dt, e)
        else:
            self.draw_bitter(dt, e)

    def draw_bitter(self, dt, e):
        w, h = self.screen.get_size()
        self.background(e.get("photo"), dt, darkness=190, snow=1.5)
        a = int(255 * ease(self.credits_t / 2.0))
        cy = int(h * 0.30)
        self.text("display", 130, e["headline"], WHITE, (w // 2, cy), anchor="center", alpha=a)
        self.text("serif_i", 38, e["sub"], MUTED, (w // 2, cy + self.px(105)), anchor="center", alpha=a)
        col = min(self.px(1100), w - 2 * self.margin())
        f = self.fonts.get("serif", self.px(32))
        y = cy + self.px(190)
        b = int(255 * ease((self.credits_t - 1.5) / 2.0))
        for line in wrap(f, self.state.format(e["note"]), col):
            surf = f.render(line, True, PAPER)
            surf.set_alpha(b)
            self.screen.blit(surf, surf.get_rect(midtop=(w // 2, y)))
            y += int(f.get_linesize() * 1.25)
        if self.credits_t > 3.0:
            bw, bh = self.px(420), self.px(64)
            self.button(pygame.Rect(w // 2 - bw // 2, y + self.px(50), bw, bh), "ЧТО БЫЛО ДАЛЬШЕ",
                        self.open_epilogue, primary=True)

    def end_buttons(self, y):
        w = self.screen.get_width()
        bw, bh, gap = self.px(330), self.px(62), self.px(18)
        x = w // 2 - (bw * 3 + gap * 2) // 2
        self.button(pygame.Rect(x, y, bw, bh), "ЗАНОВО", self.new_game, primary=True)
        self.button(pygame.Rect(x + bw + gap, y, bw, bh), "КТО ЭТИ ЛЮДИ",
                    lambda: self.transition(lambda: self.set_mode("dossier")))
        self.button(pygame.Rect(x + 2 * (bw + gap), y, bw, bh), "В МЕНЮ", self.to_menu)

    def draw_victory(self, dt, e):
        """The credits: a country card on the left, names rolling up on the right."""
        w, h = self.screen.get_size()
        t = self.credits_t
        self.background(e.get("photo"), dt, darkness=165, snow=0.5)
        # scanlines, the old-broadcast look
        self.screen.blit(self.scanlines(), (0, 0))

        m = self.margin()
        a = int(255 * ease(t / 1.5))
        top = self.px(60)
        head = self.text("display", 120, e["headline"], WHITE, (w // 2, top), anchor="midtop", alpha=a)
        # tricolour rule under the headline
        rule_w = head.width
        for i, c in enumerate(FLAG):
            pygame.draw.rect(self.screen, c, (head.x + i * rule_w // 3, head.bottom + self.px(4),
                                              rule_w // 3 + 1, self.px(5)))
        sub = self.text("display_md", 40, e["sub"], PAPER, (w // 2, head.bottom + self.px(24)),
                        anchor="midtop", alpha=a)
        band_top = sub.bottom + self.px(30)
        pygame.draw.line(self.screen, (90, 90, 94), (m, band_top), (w - m, band_top), 1)
        self.text("display", 56, "ЗА ВАС БОРОЛИСЬ:", WHITE, (m, band_top + self.px(18)), alpha=a)
        list_top = band_top + self.px(110)

        # country card
        card = pygame.Rect(m, list_top, self.px(330), h - list_top - self.px(70))
        panel = pygame.Surface(card.size, pygame.SRCALPHA)
        panel.fill((14, 15, 18, 230))
        self.screen.blit(panel, card)
        pygame.draw.rect(self.screen, (70, 70, 74), card, 1)
        cy = card.y + self.px(18)
        cx = card.centerx
        self.text("display", 54, COUNTRY_CARD["year"], WHITE, (cx, cy), anchor="midtop")
        cy += self.px(76)
        self.text("serif_b", 22, COUNTRY_CARD["name"], PAPER, (cx, cy), anchor="midtop")
        cy += self.px(40)
        fw, fh = self.px(150), self.px(96)
        for i, c in enumerate(FLAG):
            pygame.draw.rect(self.screen, c, (cx - fw // 2, cy + i * fh // 3, fw, fh // 3 + 1))
        cy += fh + self.px(22)
        org_name = ORGS.get(self.state.data.get("org"))
        rows = [("Столица", COUNTRY_CARD["capital"]), ("Президент", COUNTRY_CARD["president"]),
                ("Строй", COUNTRY_CARD["ideology"]),
                ("С кем", org_name or "сам" + ("а" if self.state.gender == "f" else "") + " по себе")]
        for k, v in rows:
            self.text("mono", 16, k.upper(), MUTED, (cx, cy), anchor="midtop")
            cy += self.px(22)
            for line in wrap(self.fonts.get("serif_b", self.px(22)), v, card.w - self.px(30)):
                self.text("serif_b", 22, line, WHITE, (cx, cy), anchor="midtop")
                cy += self.px(28)
            cy += self.px(8)
        for line in wrap(self.fonts.get("serif", self.px(17)), COUNTRY_CARD["note"], card.w - self.px(30)):
            if cy > card.bottom - self.px(24):
                break
            self.text("serif", 17, line, MUTED, (cx, cy), anchor="midtop")
            cy += self.px(22)

        # rolling names
        area = pygame.Rect(card.right + self.px(60), list_top, w - m - card.right - self.px(60), card.h)
        clip = self.screen.get_clip()
        self.screen.set_clip(area)
        name_f = self.fonts.get("display_md", self.px(46))
        row = int(name_f.get_linesize() * 1.35)
        names = list(DEDICATION)
        you = f"{self.state.name} — {self.state.prof('nom')}, {self.state.city_form('nom')}"
        speed = self.px(42)
        offset = area.bottom - t * speed
        total = (len(names) + 3) * row
        end_offset = area.y + self.px(10) - total + area.h * 0.55
        offset = max(offset, end_offset)
        y = offset
        for n in names:
            if area.y - row < y < area.bottom:
                dead = n.endswith("†")
                self.text("display_md", 46, n, (215, 210, 200) if not dead else (170, 165, 158),
                          (area.x, int(y)))
            y += row
        y += row
        if y < area.bottom:
            self.text("mono", 20, "И ВЫ:", RED, (area.x, int(y)))
            self.text("display", 54, you, WHITE, (area.x, int(y + self.px(28))))
        self.screen.set_clip(clip)
        # fade the list edges
        for edge, flip in ((area.y, False), (area.bottom - self.px(60), True)):
            grad = pygame.Surface((area.w, self.px(60)), pygame.SRCALPHA)
            for i in range(grad.get_height()):
                k = i / grad.get_height()
                grad.fill((10, 11, 13, int(200 * (k if flip else 1 - k))), (0, i, area.w, 1))
            self.screen.blit(grad, (area.x, edge))

        finished = offset <= end_offset
        if finished or t > 40:
            note_f = self.fonts.get("serif_i", self.px(26))
            ny = area.bottom - self.px(260)
            panel = pygame.Surface((area.w, self.px(250)), pygame.SRCALPHA)
            panel.fill((10, 11, 13, 220))
            self.screen.blit(panel, (area.x, ny - self.px(16)))
            for line in wrap(note_f, self.state.format(e["note"]), area.w - self.px(20))[:4]:
                self.text("serif_i", 26, line, PAPER, (area.x + self.px(10), ny))
                ny += int(note_f.get_linesize() * 1.15)
            bw, bh = self.px(380), self.px(56)
            by = area.bottom - bh
            self.button(pygame.Rect(area.x + self.px(10), by, bw, bh), "ЧТО БЫЛО ДАЛЬШЕ",
                        self.open_epilogue, primary=True, size=22)
        else:
            self.text("mono", 16, "пробел — пропустить титры", DIM, (w - m, h - self.px(40)), anchor="topright")

        self.text("mono", 15, "Будущее после 2026 года в игре вымышлено. Люди в списке — реальные; "
                  "список — дань уважения и не означает их участия в игре.",
                  DIM, (m, h - self.px(40)))

    # ---------------------------------------------------------- epilogue --

    def open_epilogue(self):
        def go():
            self.mode = "epilogue"
            self.focus = 0
            self.credits_t = 0.0
            self.epilogue_lines = epilogue(self.state)
        self.transition(go)

    def draw_epilogue(self, dt):
        w, h = self.screen.get_size()
        e = ENDINGS[self.ending]
        self.background(e.get("photo"), dt, darkness=200, snow=1.0)
        m = self.margin()
        col = min(self.px(1200), w - 2 * m)
        x = w // 2 - col // 2
        y = self.px(90)
        self.text("mono", 20, e["headline"] + " · 2030", RED, (x, y))
        y += self.px(34)
        self.text("display", 76, "ЧТО БЫЛО ДАЛЬШЕ", WHITE, (x, y))
        y += self.px(130)
        f = self.fonts.get("serif", self.px(29))
        lh = int(f.get_linesize() * 1.2)
        lines = getattr(self, "epilogue_lines", [])
        for i, line in enumerate(lines):
            a = ease((self.credits_t - 0.6 - i * 0.9) / 0.8)
            if a <= 0:
                break
            pygame.draw.rect(self.screen, RED, (x, y + self.px(14), self.px(14), self.px(3)))
            for part in wrap(f, line, col - self.px(40)):
                surf = f.render(part, True, PAPER)
                surf.set_alpha(int(255 * a))
                self.screen.blit(surf, (x + self.px(36), y))
                y += lh
            y += self.px(16)
        if self.credits_t > 0.6 + len(lines) * 0.9:
            self.end_buttons(max(y + self.px(30), h - self.px(140)))

    # ----------------------------------------------------------- dossier --

    def draw_dossier(self, dt):
        w, h = self.screen.get_size()
        self.background(None, dt, snow=0.5)
        m = self.margin()
        y = self.px(70) - int(self.scroll)
        self.text("mono", 20, "ДОСЬЕ", RED, (m, y))
        y += self.px(34)
        self.text("display", 72, "КТО ЭТИ ЛЮДИ", WHITE, (m, y))
        y += self.px(120)
        thumb = self.px(170)
        col = w - 2 * m - thumb - self.px(40)
        for p in PEOPLE:
            img = self.photos.cover(p["photo"], (thumb, thumb), 1.0) if self.photos.has(p["photo"]) else None
            box = pygame.Rect(m, y, thumb, thumb)
            if img:
                iw, ih = img.get_size()
                self.screen.blit(img, box, pygame.Rect((iw - thumb) // 2, (ih - thumb) // 3, thumb, thumb))
            else:
                pygame.draw.rect(self.screen, PANEL, box)
                self.text("display", 64, p["name"][0], DIM, box.center, anchor="center")
            tx = m + thumb + self.px(40)
            self.text("display_md", 36, p["name"] + (" †" if p["died"] else ""), WHITE, (tx, y))
            self.text("mono", 18, p["years"], RED, (tx, y + self.px(50)))
            ty = y + self.px(86)
            for line in wrap(self.fonts.get("serif", self.px(24)), p["bio"], col):
                self.text("serif", 24, line, PAPER, (tx, ty))
                ty += self.px(32)
            cap = self.photos.caption(p["photo"])
            if cap:
                self.text("mono", 14, cap, DIM, (tx, ty + self.px(4)))
                ty += self.px(24)
            y = max(y + thumb, ty) + self.px(44)
        y += self.px(10)
        self.button(pygame.Rect(m, y, self.px(300), self.px(60)), "НАЗАД", self.to_menu, primary=True)
        content = y + self.px(60) + int(self.scroll) + self.px(60)
        self.scroll = min(self.scroll, max(0, content - h))

    # ------------------------------------------------------------- pause --

    def draw_pause(self):
        w, h = self.screen.get_size()
        self.screen.blit(self.veil((6, 6, 8), 215), (0, 0))
        self.text("display", 90, "ПАУЗА", WHITE, (w // 2, int(h * 0.3)), anchor="center")
        bw, bh = self.px(420), self.px(64)
        y = int(h * 0.42)
        x = w // 2 - bw // 2
        self.button(pygame.Rect(x, y, bw, bh), "ПРОДОЛЖИТЬ", lambda: setattr(self, "paused", False), primary=True)
        y += bh + self.px(14)
        self.button(pygame.Rect(x, y, bw, bh), "ЗВУК: " + ("ВЫКЛ" if self.audio.muted else "ВКЛ"),
                    self.audio.toggle_mute)
        y += bh + self.px(14)
        self.button(pygame.Rect(x, y, bw, bh), "ПОЛНЫЙ ЭКРАН (F11)", self.toggle_fullscreen)
        y += bh + self.px(14)
        self.button(pygame.Rect(x, y, bw, bh), "В ГЛАВНОЕ МЕНЮ", self.to_menu)
        y += bh + self.px(14)
        self.button(pygame.Rect(x, y, bw, bh), "ВЫЙТИ ИЗ ИГРЫ", lambda: setattr(self, "running", False))


def main():
    App().run()


if __name__ == "__main__":
    main()
