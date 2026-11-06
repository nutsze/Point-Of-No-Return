"""Меню, эпизоды, решения и итог кампании."""
from __future__ import annotations

from functools import partial

from engine import CHAPTER_COUNT, ending_for, has_save
from ui import FAINT, MUTED, RED, TEXT, WHITE
from ..constants import ALT_WARNING


class StoryScreens:
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
            ("ДЕЯТЕЛИ", partial(self.go, "people"), True),
            ("АВТОРЫ И ИСТОЧНИКИ", partial(self.go, "credits"), True),
            ("НАСТРОЙКИ", partial(self.go, "settings"), True),
        ]
        for index, (label, action, enabled) in enumerate(entries):
            self.add_button((82, 500 + index * 47, 450, 41), label, action, "menu", enabled, 23)
        self.add_button((1320, 822, 230, 44), "ВЫХОД", self.quit, font_size=19, align="right")
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
            "Каждое решение открывает один из трёх вариантов следующей главы. Можно строить правовую коалицию, "
            "региональную сеть или независимую медиаплатформу — и менять стратегию по ходу кампании.\n\n"
            "Последствия проявляются в новых сценах, союзниках, титрах и финальном политическом устройстве."
        )
        self.canvas.text(body, (74, 278), 25, TEXT, max_width=780, line_gap=8)
        self.canvas.text("После первого решения вся ветка получает постоянную пометку «АЛЬТЕРНАТИВНАЯ ИСТОРИЯ».", (74, 666), 18, MUTED, max_width=750)
        self.add_button((76, 760, 380, 58), "НАЧАТЬ ИСТОРИЮ", partial(self.go, "event", phase="narration"), "primary", font_size=26)
        self.add_button((500, 768, 220, 42), "В МЕНЮ", partial(self.go, "menu"), font_size=18)
        self.caption("navalny_2020")

    def screen_event(self) -> None:
        event = self.current_event()
        phase = self.params.get("phase", "narration")
        self.background(event["photo"], 15 if phase == "narration" else 75)
        self.snow(90)
        self.header(f"Глава {self.state['chapter'] + 1} из {CHAPTER_COUNT} / {event['date']}")
        self.alternative_tag()
        if phase == "choice":
            self.canvas.overlay(70)
            self.canvas.text(event["title"].upper(), (160, 132), 35, WHITE, max_width=1280, bold=True, align="center")
            self.canvas.text("КАЖДЫЙ ВАРИАНТ ОТКРЫВАЕТ ДРУГУЮ ВЕТВЬ", (500, 207), 16, MUTED, max_width=600, align="center")
            for index, choice in enumerate(event["choices"]):
                self.add_button((245, 280 + index * 153, 1110, 122), choice["text"], partial(self.choose, index), "choice", font_size=33, align="center")
            self.canvas.text("1 / 2 / 3 — ВЫБРАТЬ    ESC — ПАУЗА", (500, 800), 16, MUTED, max_width=600, align="center")
        else:
            self.canvas.gradient((0, 330, 1600, 570), 0, 250)
            title_end = self.canvas.text(event["title"].upper(), (64, 477), 44, WHITE, max_width=1450, bold=True, line_gap=2)
            label = "ДОКУМЕНТАЛЬНЫЙ ФОН / АЛЬТЕРНАТИВНАЯ РЕАКЦИЯ" if event["documentary"] else "ВЫМЫШЛЕННАЯ ГЛАВА"
            self.canvas.text(label, (68, title_end + 8), 14, MUTED, bold=True)
            body_end = self.canvas.text(event["description"], (68, title_end + 43), 22, TEXT, max_width=1450, line_gap=4, max_lines=4)
            forces_y = min(746, body_end + 10)
            self.canvas.text("Участники: " + " · ".join(event["forces"]), (68, forces_y), 14, MUTED, max_width=1130, max_lines=2)
            if event["documentary"]:
                self.canvas.text(event["source_name"], (68, 803), 13, FAINT, max_width=1060)
            self.add_button((1240, 801, 290, 52), "ДАЛЕЕ", partial(self.go, "event", phase="choice"), "primary", font_size=24, align="right")
        self.caption(event["photo"])

    def screen_result(self) -> None:
        event = self.current_event()
        choice = event["choices"][self.params.get("choice_index", 0)]
        self.background(event["photo"], 45)
        self.snow(75)
        self.header("Последствие и новый маршрут")
        self.canvas.text(ALT_WARNING, (50, 88), 15, RED, bold=True, max_width=1450)
        self.canvas.gradient((0, 330, 1600, 570), 0, 250)
        title_end = self.canvas.text(choice["text"].upper(), (66, 485), 40, WHITE, max_width=1450, bold=True)
        self.canvas.text(choice["result"], (70, title_end + 28), 25, TEXT, max_width=1400, line_gap=7, max_lines=4)
        label = "УВИДЕТЬ ФИНАЛ" if self.state["completed"] else ("СЛЕДУЮЩАЯ ГЛАВА" if choice["next"] == "END" else "ВОЙТИ В НОВУЮ ВЕТВЬ")
        self.add_button((1080, 790, 450, 58), label, self.next_chapter, "primary", font_size=25, align="right")
        self.caption(event["photo"])

    def screen_ending(self) -> None:
        ending = ending_for(self.state)
        self.background("kremlin_spasskaya", 65)
        self.snow(80)
        self.header("20 августа 2030 / финал")
        self.canvas.text(ALT_WARNING + " / НЕ ПРОГНОЗ", (50, 88), 15, RED, bold=True, max_width=1450)
        self.canvas.gradient((0, 250, 1600, 650), 0, 250)
        self.canvas.text(ending["subtitle"].upper(), (68, 374), 17, MUTED, bold=True)
        self.canvas.text(ending["title"], (64, 418), 64, WHITE, max_width=1450, bold=True)
        self.canvas.text(ending["text"], (70, 532), 25, TEXT, max_width=1370, line_gap=7, max_lines=4)
        self.add_button((72, 780, 300, 56), "ТИТРЫ", partial(self.go, "roll"), "primary", font_size=24)
        self.add_button((410, 780, 300, 56), "НОВАЯ ИСТОРИЯ", self.start_new, font_size=22)
        self.add_button((748, 780, 300, 56), "ГЛАВНОЕ МЕНЮ", partial(self.go, "menu"), font_size=22)
        self.add_button((1190, 780, 340, 56), "ХРОНОЛОГИЯ", partial(self.go, "timeline", return_to="ending"), font_size=22, align="right")
        self.caption("kremlin_spasskaya")
