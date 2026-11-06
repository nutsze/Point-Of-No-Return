"""Кнопки, архивная заглушка и полоса прокрутки."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import pygame

from .canvas import Canvas
from .theme import FAINT, LINE, MUTED, WHITE


@dataclass
class Button:
    rect: pygame.Rect
    label: str
    action: Callable[[], None]
    style: str = "ghost"
    enabled: bool = True
    font_size: int = 24
    align: str = "left"

    def draw(self, canvas: Canvas, mouse, selected=False) -> None:
        active = self.enabled and (self.rect.collidepoint(mouse) or selected)
        color = WHITE if active else (MUTED if self.enabled else FAINT)
        x, y = self.rect.topleft
        if self.style == "choice":
            canvas.text(self.label.upper(), (x, y + 19), self.font_size, color,
                        max_width=self.rect.width, bold=True, align="center", line_gap=2, max_lines=2)
            canvas.line((x + 40, self.rect.bottom - 10), (self.rect.right - 40, self.rect.bottom - 10),
                        WHITE if active else LINE, 2 if active else 1, 210 if active else 65)
            return
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


def draw_scrollbar(canvas: Canvas, x: int, y: int, height: int, offset: int, content_height: int) -> None:
    rect = (x, y, 6, height)
    if content_height <= height:
        return
    canvas.overlay(90, rect, color=MUTED)
    thumb_height = max(45, round(height * height / content_height))
    max_offset = max(1, content_height - height)
    thumb_y = y + round((height - thumb_height) * min(offset, max_offset) / max_offset)
    canvas.overlay(190, (x, thumb_y, 6, thumb_height), color=WHITE)
