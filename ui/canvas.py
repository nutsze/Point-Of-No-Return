"""Нативно масштабируемый холст: никакого растягивания готового кадра."""
from __future__ import annotations

import pygame

from engine import resource_root
from .theme import BASE_H, BASE_W, BLACK, TEXT


class FontBook:
    def __init__(self) -> None:
        self.root = resource_root() / "assets" / "fonts"
        self.cache = {}

    def get(self, pixels: int, bold: bool = False, mono: bool = False):
        pixels = max(7, int(pixels))
        key = (pixels, bold, mono)
        if key not in self.cache:
            if mono:
                filename = "DejaVuSansMono.ttf"
            else:
                filename = "NotoSansDisplay-CondensedBold.ttf" if bold else "NotoSansDisplay-Condensed.ttf"
            self.cache[key] = pygame.font.Font(str(self.root / filename), pixels)
        return self.cache[key]


def wrap_text(text: str, font, max_width: int) -> list[str]:
    lines = []
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
    def __init__(self, surface: pygame.Surface) -> None:
        self.fonts = FontBook()
        self._gradient_cache = {}
        self.update(surface)

    def update(self, surface) -> None:
        self.surface = surface
        self.width, self.height = surface.get_size()
        self.scale = min(self.width / BASE_W, self.height / BASE_H)
        self.offset_x = round((self.width - BASE_W * self.scale) / 2)
        self.offset_y = round((self.height - BASE_H * self.scale) / 2)
        self._gradient_cache.clear()

    def value(self, value: float) -> int:
        return max(1, round(value * self.scale))

    def point(self, xy) -> tuple[int, int]:
        return self.offset_x + round(xy[0] * self.scale), self.offset_y + round(xy[1] * self.scale)

    def pixel_rect(self, rect) -> pygame.Rect:
        x, y, w, h = rect
        px, py = self.point((x, y))
        return pygame.Rect(px, py, self.value(w), self.value(h))

    def rect(self, rect, color=BLACK, width=0, border_color=TEXT, alpha=255) -> None:
        area = self.pixel_rect(rect)
        layer = pygame.Surface(area.size, pygame.SRCALPHA)
        if color is not None:
            layer.fill((*color, alpha))
        if width:
            pygame.draw.rect(layer, (*border_color, alpha), layer.get_rect(), self.value(width))
        self.surface.blit(layer, area)

    def logical_pos(self, position) -> tuple[int, int]:
        return (
            round((position[0] - self.offset_x) / self.scale),
            round((position[1] - self.offset_y) / self.scale),
        )

    def fill(self, color=BLACK) -> None:
        self.surface.fill(color)

    def logical_point(self, position) -> tuple[int, int]:
        return self.logical_pos(position)

    def raw(self, image, xy, size) -> None:
        area = self.pixel_rect((*xy, *size))
        scaled = pygame.transform.smoothscale(image, area.size)
        self.surface.blit(scaled, area)

    def overlay(self, alpha: int, rect=(0, 0, BASE_W, BASE_H), color=BLACK) -> None:
        area = self.pixel_rect(rect)
        layer = pygame.Surface(area.size, pygame.SRCALPHA)
        layer.fill((*color, alpha))
        self.surface.blit(layer, area)

    def gradient(self, rect, top_alpha: int = 0, bottom_alpha: int = 245) -> None:
        area = self.pixel_rect(rect)
        key = (area.width, area.height, top_alpha, bottom_alpha)
        if key not in self._gradient_cache:
            strip = pygame.Surface((1, 256), pygame.SRCALPHA)
            for y in range(256):
                alpha = round(top_alpha + (bottom_alpha - top_alpha) * y / 255)
                strip.set_at((0, y), (*BLACK, alpha))
            self._gradient_cache[key] = pygame.transform.smoothscale(strip, area.size)
        self.surface.blit(self._gradient_cache[key], area)

    def text(self, text: str, xy, size: int, color=TEXT, max_width=None,
             bold=False, mono=False, align="left", line_gap=5, max_lines=None) -> float:
        x, y = xy
        font = self.fonts.get(self.value(size), bold=bold, mono=mono)
        width = self.value(max_width or BASE_W - x)
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

    def line(self, start, end, color, width=1, alpha=None) -> None:
        if alpha is None:
            pygame.draw.line(self.surface, color, self.point(start), self.point(end), self.value(width))
            return
        a, b = self.point(start), self.point(end)
        layer = pygame.Surface((abs(a[0] - b[0]) + 2, abs(a[1] - b[1]) + 2), pygame.SRCALPHA)
        local_a = (a[0] - min(a[0], b[0]) + 1, a[1] - min(a[1], b[1]) + 1)
        local_b = (b[0] - min(a[0], b[0]) + 1, b[1] - min(a[1], b[1]) + 1)
        pygame.draw.line(layer, (*color, alpha), local_a, local_b, self.value(width))
        self.surface.blit(layer, (min(a[0], b[0]) - 1, min(a[1], b[1]) - 1))

    def circle(self, center, radius, color, alpha=180) -> None:
        point = self.point(center)
        size = self.value(radius * 2 + 2)
        layer = pygame.Surface((size, size), pygame.SRCALPHA)
        pygame.draw.circle(layer, (*color, alpha), (size // 2, size // 2), self.value(radius))
        self.surface.blit(layer, (point[0] - size // 2, point[1] - size // 2))

    def clip(self, rect=None) -> None:
        self.surface.set_clip(self.pixel_rect(rect) if rect else None)
