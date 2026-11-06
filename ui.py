"""Нативно масштабируемый монохромный UI визуальной новеллы."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import pygame

from engine import resource_root

BASE_W, BASE_H = 1600, 900
BLACK = (4, 5, 7)
PANEL = (12, 14, 17)
WHITE = (238, 238, 232)
TEXT = (218, 218, 212)
MUTED = (158, 158, 153)
FAINT = (105, 105, 102)
LINE = (105, 105, 101)
RED = (193, 102, 98)


class FontBook:
    def __init__(self) -> None:
        self.root = resource_root() / "assets" / "fonts"
        self.cache: dict[tuple[int, bool, bool], pygame.font.Font] = {}

    def get(self, pixels: int, bold: bool = False, mono: bool = False) -> pygame.font.Font:
        pixels = max(7, int(pixels))
        key = (pixels, bold, mono)
        if key not in self.cache:
            if mono:
                filename = "DejaVuSansMono.ttf"
            else:
                filename = "NotoSansDisplay-CondensedBold.ttf" if bold else "NotoSansDisplay-Condensed.ttf"
            self.cache[key] = pygame.font.Font(str(self.root / filename), pixels)
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


class Canvas:
    """Рисует в координатах 1600×900 на поверхности фактического разрешения."""

    def __init__(self, surface: pygame.Surface) -> None:
        self.fonts = FontBook()
        self._gradient_cache: dict[tuple[int, int, int, int], pygame.Surface] = {}
        self.update(surface)

    def update(self, surface: pygame.Surface) -> None:
        self.surface = surface
        self.width, self.height = surface.get_size()
        self.scale = min(self.width / BASE_W, self.height / BASE_H)
        self.offset_x = round((self.width - BASE_W * self.scale) / 2)
        self.offset_y = round((self.height - BASE_H * self.scale) / 2)
        self._gradient_cache.clear()

    def value(self, value: float) -> int:
        return max(1, round(value * self.scale))

    def point(self, xy: tuple[float, float]) -> tuple[int, int]:
        return self.offset_x + round(xy[0] * self.scale), self.offset_y + round(xy[1] * self.scale)

    def rect(self, rect) -> pygame.Rect:
        x, y, w, h = rect
        px, py = self.point((x, y))
        return pygame.Rect(px, py, self.value(w), self.value(h))

    def logical_pos(self, position: tuple[int, int]) -> tuple[int, int]:
        return (
            round((position[0] - self.offset_x) / self.scale),
            round((position[1] - self.offset_y) / self.scale),
        )

    def fill(self, color=BLACK) -> None:
        self.surface.fill(color)

    def overlay(self, alpha: int, rect=(0, 0, BASE_W, BASE_H), color=BLACK) -> None:
        area = self.rect(rect)
        layer = pygame.Surface(area.size, pygame.SRCALPHA)
        layer.fill((*color, alpha))
        self.surface.blit(layer, area)

    def gradient(self, rect, top_alpha: int = 0, bottom_alpha: int = 245) -> None:
        area = self.rect(rect)
        key = (area.width, area.height, top_alpha, bottom_alpha)
        if key not in self._gradient_cache:
            strip = pygame.Surface((1, 256), pygame.SRCALPHA)
            for y in range(256):
                alpha = round(top_alpha + (bottom_alpha - top_alpha) * y / 255)
                strip.set_at((0, y), (*BLACK, alpha))
            self._gradient_cache[key] = pygame.transform.smoothscale(strip, area.size)
        self.surface.blit(self._gradient_cache[key], area)

    def text(self, text: str, xy, size: int, color=TEXT, max_width: float | None = None,
             bold: bool = False, mono: bool = False, align: str = "left",
             line_gap: int = 5, max_lines: int | None = None) -> float:
        x, y = xy
        font = self.fonts.get(self.value(size), bold=bold, mono=mono)
        logical_width = max_width or BASE_W - x
        width = self.value(logical_width)
        lines = wrap_text(text, font, width)
        if max_lines is not None:
            lines = lines[:max_lines]
        line_height = font.get_linesize() + self.value(line_gap)
        px, py = self.point((x, y))
        for line in lines:
            rendered = font.render(line, True, color)
            target = rendered.get_rect()
            if align == "center":
                target.midtop = (px + width // 2, py)
            elif align == "right":
                target.topright = (px + width, py)
            else:
                target.topleft = (px, py)
            self.surface.blit(rendered, target)
            py += line_height
        return y + len(lines) * line_height / self.scale

    def line(self, start, end, color=LINE, width: int = 1, alpha: int | None = None) -> None:
        if alpha is None:
            pygame.draw.line(self.surface, color, self.point(start), self.point(end), self.value(width))
        else:
            a, b = self.point(start), self.point(end)
            layer = pygame.Surface((abs(a[0] - b[0]) + 2, abs(a[1] - b[1]) + 2), pygame.SRCALPHA)
            local_a = (a[0] - min(a[0], b[0]) + 1, a[1] - min(a[1], b[1]) + 1)
            local_b = (b[0] - min(a[0], b[0]) + 1, b[1] - min(a[1], b[1]) + 1)
            pygame.draw.line(layer, (*color, alpha), local_a, local_b, self.value(width))
            self.surface.blit(layer, (min(a[0], b[0]) - 1, min(a[1], b[1]) - 1))

    def circle(self, center, radius: float, color=WHITE, alpha: int = 180) -> None:
        point = self.point(center)
        size = self.value(radius * 2 + 2)
        layer = pygame.Surface((size, size), pygame.SRCALPHA)
        pygame.draw.circle(layer, (*color, alpha), (size // 2, size // 2), self.value(radius))
        self.surface.blit(layer, (point[0] - size // 2, point[1] - size // 2))

    def clip(self, rect=None) -> None:
        self.surface.set_clip(self.rect(rect) if rect else None)


@dataclass
class Button:
    rect: pygame.Rect
    label: str
    action: Callable[[], None]
    style: str = "ghost"
    enabled: bool = True
    font_size: int = 24
    align: str = "left"

    def draw(self, canvas: Canvas, mouse: tuple[int, int], selected: bool = False) -> None:
        active = self.enabled and (self.rect.collidepoint(mouse) or selected)
        color = WHITE if active else (MUTED if self.enabled else FAINT)
        x, y = self.rect.topleft
        if self.style == "choice":
            canvas.text(self.label.upper(), (x, y + 19), self.font_size, color,
                        max_width=self.rect.width, bold=True, align="center", line_gap=2, max_lines=2)
            canvas.line((x + 40, self.rect.bottom - 10), (self.rect.right - 40, self.rect.bottom - 10),
                        color=WHITE if active else LINE, width=2 if active else 1,
                        alpha=210 if active else 65)
        else:
            canvas.text(self.label, (x, y + 12), self.font_size, color,
                        max_width=self.rect.width, bold=active or self.style == "primary",
                        align=self.align, line_gap=2, max_lines=2)
            if active:
                if self.align == "center":
                    canvas.line((x + 40, self.rect.bottom - 5), (self.rect.right - 40, self.rect.bottom - 5), WHITE, 1, 180)
                else:
                    canvas.line((x - 12, y + 11), (x - 12, y + self.font_size + 19), WHITE, 3, 210)


def draw_empty_archive(canvas: Canvas, rect=(260, 180, 1080, 500)) -> None:
    canvas.overlay(245, rect, color=(18, 18, 18))
    canvas.text("АРХИВНАЯ КАРТОЧКА", (rect[0] + 40, rect[1] + 45), 20, MUTED, bold=True, mono=True)
    canvas.text("ИЗОБРАЖЕНИЕ НЕ НАЙДЕНО", (rect[0] + 40, rect[1] + 180), 38, WHITE,
                max_width=rect[2] - 80, bold=True, align="center")
    canvas.text("Фотография с подтверждёнными авторством и лицензией отсутствует. Генерация замены не производилась.",
                (rect[0] + 60, rect[1] + 280), 22, MUTED, max_width=rect[2] - 120, align="center")


def draw_scrollbar(canvas: Canvas, rect, offset: int, content_height: int) -> None:
    if content_height <= rect[3]:
        return
    canvas.overlay(90, rect, color=MUTED)
    thumb_height = max(45, round(rect[3] * rect[3] / content_height))
    max_offset = max(1, content_height - rect[3])
    y = rect[1] + round((rect[3] - thumb_height) * min(offset, max_offset) / max_offset)
    canvas.overlay(190, (rect[0], y, rect[2], thumb_height), color=WHITE)
