"""Небольшой UI-слой pygame для документального интерфейса."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import pygame

from engine import resource_root

BG = (10, 16, 23)
BG_SOFT = (15, 24, 34)
PANEL = (19, 30, 42)
PANEL_LIGHT = (27, 41, 55)
LINE = (49, 66, 81)
TEXT = (235, 232, 223)
MUTED = (155, 166, 176)
FAINT = (103, 117, 130)
AMBER = (211, 166, 77)
AMBER_LIGHT = (239, 202, 127)
RED = (184, 70, 70)
TEAL = (86, 154, 148)
GREEN = (101, 168, 118)
PAPER = (216, 208, 191)
INK = (30, 34, 37)
WHITE = (255, 255, 255)


class FontBook:
    def __init__(self) -> None:
        self.root = resource_root() / "assets" / "fonts"
        self.cache: dict[tuple[int, bool, bool], pygame.font.Font] = {}

    def get(self, size: int, bold: bool = False, mono: bool = False) -> pygame.font.Font:
        key = (size, bold, mono)
        if key not in self.cache:
            filename = "DejaVuSansMono.ttf" if mono else ("DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf")
            self.cache[key] = pygame.font.Font(str(self.root / filename), size)
        return self.cache[key]


def wrap_text(text: str, font: pygame.font.Font, max_width: int) -> list[str]:
    lines: list[str] = []
    for paragraph in str(text).splitlines() or [""]:
        if not paragraph:
            lines.append("")
            continue
        words = paragraph.split()
        current = words[0]
        for word in words[1:]:
            candidate = current + " " + word
            if font.size(candidate)[0] <= max_width:
                current = candidate
            else:
                lines.append(current)
                current = word
        lines.append(current)
    return lines


def draw_text(surface: pygame.Surface, text: str, xy: tuple[int, int], font: pygame.font.Font, color: tuple[int, int, int] = TEXT, max_width: int | None = None, line_gap: int = 5, align: str = "left", max_lines: int | None = None) -> int:
    x, y = xy
    width = max_width or surface.get_width() - x
    lines = wrap_text(text, font, width)
    if max_lines is not None:
        lines = lines[:max_lines]
    line_height = font.get_linesize() + line_gap
    for line in lines:
        rendered = font.render(line, True, color)
        rect = rendered.get_rect()
        if align == "center":
            rect.midtop = (x + width // 2, y)
        elif align == "right":
            rect.topright = (x + width, y)
        else:
            rect.topleft = (x, y)
        surface.blit(rendered, rect)
        y += line_height
    return y


def text_height(text: str, font: pygame.font.Font, max_width: int, line_gap: int = 5) -> int:
    return len(wrap_text(text, font, max_width)) * (font.get_linesize() + line_gap)


def panel(surface: pygame.Surface, rect: pygame.Rect, color=PANEL, alpha: int = 235, radius: int = 8, border=LINE) -> None:
    layer = pygame.Surface(rect.size, pygame.SRCALPHA)
    pygame.draw.rect(layer, (*color, alpha), layer.get_rect(), border_radius=radius)
    if border is not None:
        pygame.draw.rect(layer, (*border, min(255, alpha + 15)), layer.get_rect(), width=1, border_radius=radius)
    surface.blit(layer, rect.topleft)


def darken(surface: pygame.Surface, amount: int = 130, rect: pygame.Rect | None = None) -> None:
    area = rect or surface.get_rect()
    layer = pygame.Surface(area.size, pygame.SRCALPHA)
    layer.fill((3, 8, 13, amount))
    surface.blit(layer, area.topleft)


def vertical_gradient(surface: pygame.Surface, rect: pygame.Rect, top_alpha=20, bottom_alpha=235) -> None:
    layer = pygame.Surface(rect.size, pygame.SRCALPHA)
    for y in range(rect.height):
        ratio = y / max(1, rect.height - 1)
        alpha = round(top_alpha + (bottom_alpha - top_alpha) * ratio)
        pygame.draw.line(layer, (5, 11, 17, alpha), (0, y), (rect.width, y))
    surface.blit(layer, rect.topleft)


def scanlines(surface: pygame.Surface, alpha: int = 13) -> None:
    layer = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
    for y in range(0, surface.get_height(), 4):
        pygame.draw.line(layer, (0, 0, 0, alpha), (0, y), (surface.get_width(), y))
    surface.blit(layer, (0, 0))


@dataclass
class Button:
    rect: pygame.Rect
    label: str
    action: Callable[[], None]
    style: str = "normal"
    enabled: bool = True
    hint: str = ""
    font_size: int = 17

    def draw(self, surface: pygame.Surface, fonts: FontBook, mouse: tuple[int, int], selected: bool = False) -> None:
        hover = self.enabled and self.rect.collidepoint(mouse)
        active = hover or selected
        if not self.enabled:
            fill, border, text_color = (23, 29, 35), (43, 49, 54), FAINT
        elif self.style == "primary":
            fill = AMBER if active else (167, 127, 54)
            border = AMBER_LIGHT if active else AMBER
            text_color = (18, 22, 25)
        elif self.style == "danger":
            fill = (115, 45, 45) if active else (72, 35, 38)
            border = RED
            text_color = TEXT
        elif self.style == "ghost":
            fill = (20, 31, 42) if active else (12, 20, 28)
            border = LINE if not active else MUTED
            text_color = TEXT if active else MUTED
        else:
            fill = PANEL_LIGHT if active else PANEL
            border = AMBER if active else LINE
            text_color = TEXT
        pygame.draw.rect(surface, fill, self.rect, border_radius=6)
        pygame.draw.rect(surface, border, self.rect, width=1, border_radius=6)
        font = fonts.get(self.font_size, bold=self.style == "primary")
        lines = wrap_text(self.label, font, self.rect.width - 28)
        total = len(lines) * font.get_linesize() + (len(lines) - 1) * 2
        y = self.rect.centery - total // 2
        for line in lines[:5]:
            image = font.render(line, True, text_color)
            surface.blit(image, image.get_rect(midtop=(self.rect.centerx, y)))
            y += font.get_linesize() + 2


def draw_brand(surface: pygame.Surface, fonts: FontBook, section: str = "") -> None:
    pygame.draw.rect(surface, (8, 14, 20), (0, 0, surface.get_width(), 54))
    pygame.draw.line(surface, LINE, (0, 53), (surface.get_width(), 53))
    draw_text(surface, "2030 / ТОЧКА НЕВОЗВРАТА", (28, 16), fonts.get(15, bold=True), AMBER)
    if section:
        draw_text(surface, section.upper(), (surface.get_width() - 430, 17), fonts.get(13), MUTED, max_width=400, align="right")


def draw_archive_tag(surface: pygame.Surface, fonts: FontBook, text: str, xy=(28, 74), alternative=False) -> None:
    font = fonts.get(12, bold=True, mono=True)
    width = min(surface.get_width() - xy[0] * 2, font.size(text)[0] + 24)
    rect = pygame.Rect(xy[0], xy[1], width, 30)
    color = RED if alternative else AMBER
    pygame.draw.rect(surface, (12, 19, 26), rect, border_radius=3)
    pygame.draw.rect(surface, color, rect, width=1, border_radius=3)
    draw_text(surface, text, (rect.x + 12, rect.y + 7), font, color, max_width=rect.width - 24)


def draw_photo_caption(surface: pygame.Surface, fonts: FontBook, caption: str, bottom: int | None = None) -> None:
    bottom = bottom or surface.get_height() - 12
    font = fonts.get(11)
    lines = wrap_text(caption, font, surface.get_width() - 56)
    height = len(lines) * (font.get_linesize() + 2) + 16
    rect = pygame.Rect(20, bottom - height, surface.get_width() - 40, height)
    panel(surface, rect, color=(7, 12, 17), alpha=205, radius=3, border=None)
    draw_text(surface, caption, (rect.x + 10, rect.y + 7), font, (196, 199, 198), max_width=rect.width - 20, line_gap=2)


def draw_stat(surface: pygame.Surface, fonts: FontBook, label: str, value: int, rect: pygame.Rect, color=AMBER, delta: int | None = None) -> None:
    draw_text(surface, label.upper(), (rect.x, rect.y), fonts.get(11, bold=True), MUTED, max_width=rect.width - 44)
    draw_text(surface, str(value), (rect.right - 42, rect.y - 6), fonts.get(20, bold=True), TEXT, max_width=42, align="right")
    track = pygame.Rect(rect.x, rect.y + 29, rect.width, 5)
    pygame.draw.rect(surface, (44, 55, 65), track, border_radius=2)
    fill = track.copy()
    fill.width = round(track.width * max(0, min(100, value)) / 100)
    pygame.draw.rect(surface, color, fill, border_radius=2)
    if delta:
        delta_color = GREEN if delta > 0 else RED
        sign = "+" if delta > 0 else ""
        draw_text(surface, f"{sign}{delta}", (rect.right - 40, rect.y + 38), fonts.get(11, bold=True), delta_color, max_width=40, align="right")


def draw_empty_archive(surface: pygame.Surface, fonts: FontBook, rect: pygame.Rect, title="ИЗОБРАЖЕНИЕ НЕ НАЙДЕНО") -> None:
    pygame.draw.rect(surface, PAPER, rect)
    for y in range(rect.y + 20, rect.bottom - 20, 26):
        pygame.draw.line(surface, (190, 182, 165), (rect.x + 22, y), (rect.right - 22, y), 1)
    draw_text(surface, "АРХИВНАЯ КАРТОЧКА", (rect.x + 30, rect.y + 30), fonts.get(12, bold=True, mono=True), (111, 66, 53), max_width=rect.width - 60)
    draw_text(surface, title, (rect.x + 30, rect.y + rect.height // 2 - 30), fonts.get(25, bold=True), INK, max_width=rect.width - 60, align="center")
    draw_text(surface, "Фотография с подтверждёнными авторством и лицензией отсутствует. Генерация замены не производилась.", (rect.x + 40, rect.y + rect.height // 2 + 30), fonts.get(14), (70, 72, 72), max_width=rect.width - 80, align="center")


def draw_scrollbar(surface: pygame.Surface, rect: pygame.Rect, offset: int, content_height: int) -> None:
    if content_height <= rect.height:
        return
    pygame.draw.rect(surface, (32, 44, 55), rect, border_radius=3)
    thumb_height = max(35, round(rect.height * rect.height / content_height))
    max_offset = max(1, content_height - rect.height)
    y = rect.y + round((rect.height - thumb_height) * min(offset, max_offset) / max_offset)
    pygame.draw.rect(surface, MUTED, (rect.x, y, rect.width, thumb_height), border_radius=3)
