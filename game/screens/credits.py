"""Динамические финальные титры по маршруту игрока."""
from __future__ import annotations

from functools import partial

from engine import ending_for
from ui import FAINT, LINE, MUTED, TEXT, WHITE


class RollCreditsScreen:
    def roll_limit(self) -> int:
        return max(900, len(self.state.get("credits", [])) * 78 + 760)

    def screen_roll(self) -> None:
        ending = ending_for(self.state)
        self.background("kremlin_spasskaya", 125, blurred=True)
        self.canvas.overlay(45)
        self.snow(45)
        self.canvas.text(ending["headline"], (48, 62), 66, WHITE, bold=True, max_width=1500, align="center")
        self.canvas.text(ending["outcome"], (48, 153), 27, TEXT, max_width=1500, align="center")
        self.canvas.text("АЛЬТЕРНАТИВНАЯ ИСТОРИЯ", (48, 215), 14, MUTED, bold=True, max_width=1500, align="center")

        self.canvas.text("ЗА ВАС БОРОЛИСЬ:", (610, 324), 25, WHITE, bold=True)
        self.canvas.line((610, 370), (1500, 370), LINE, 1, 120)
        names = self.state.get("credits", [])
        for index, name in enumerate(names):
            y = 855 - self.roll_offset + index * 78
            if 390 < y < 820:
                self.canvas.text(name, (620, y), 34, WHITE, max_width=870)
        closing_y = 855 - self.roll_offset + len(names) * 78 + 90
        if 390 < closing_y < 780:
            self.canvas.text(ending["closing"], (620, closing_y), 25, TEXT, max_width=850, line_gap=8)

        self.canvas.rect((60, 350, 480, 410), (10, 10, 10), alpha=205)
        self.canvas.text("20 АВГУСТА 2030", (88, 380), 16, MUTED, bold=True)
        fields = [
            ("Государство", ending["government"]),
            ("Столица", "Москва"),
            ("Руководитель", ending["leader"]),
            ("Идеология", ending["ideology"]),
        ]
        for index, (label, value) in enumerate(fields):
            y = 426 + index * 78
            self.canvas.text(label.upper(), (88, y), 13, MUTED, bold=True)
            self.canvas.text(value, (88, y + 23), 23, WHITE, max_width=420, max_lines=2)
        self.add_button((60, 798, 300, 52), "К ФИНАЛУ", partial(self.go, "ending"), font_size=20)
        self.add_button((1210, 798, 330, 52), "ГЛАВНОЕ МЕНЮ", partial(self.go, "menu"), "primary", font_size=20, align="right")
        self.canvas.text("SPACE — ПРОПУСТИТЬ", (620, 860), 12, FAINT, max_width=500)
        self.caption("kremlin_spasskaya")
