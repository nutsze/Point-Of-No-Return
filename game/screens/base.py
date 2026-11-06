"""Общие визуальные элементы экранов."""
from __future__ import annotations

from ui import BASE_H, BASE_W, BLACK, LINE, MUTED, RED, WHITE, draw_empty_archive
from ..constants import ALT_WARNING


class BaseScreens:
    def background(self, photo_id=None, dark=25, blurred=False) -> None:
        if photo_id and self.media.get(photo_id):
            if blurred:
                image = self.media.blurred_scene(photo_id, self.window.get_size())
            else:
                image = self.media.scene_surface(photo_id, self.window.get_size(), "cover")
            self.window.blit(image, (0, 0))
            if dark:
                self.canvas.overlay(dark, (0, 0, BASE_W, BASE_H))
        else:
            self.canvas.fill(BLACK)
            if photo_id:
                draw_empty_archive(self.canvas)

    def snow(self, alpha=95) -> None:
        for x, y, _, _, radius in self.particles:
            self.canvas.circle((x, y), radius, WHITE, alpha)

    def header(self, section="") -> None:
        self.canvas.text("2030 / ТОЧКА НЕВОЗВРАТА", (48, 31), 19, WHITE, bold=True)
        if section:
            self.canvas.text(section.upper(), (950, 33), 16, MUTED, max_width=600, align="right")
        self.canvas.line((48, 72), (1552, 72), LINE, 1, 80)

    def alternative_tag(self) -> None:
        if self.state["alternative_history"]:
            self.canvas.text(ALT_WARNING, (50, 88), 15, RED, bold=True, max_width=1450)

    def caption(self, photo_id) -> None:
        self.canvas.text(self.media.caption(photo_id), (48, 875), 11, MUTED, max_width=1500)
