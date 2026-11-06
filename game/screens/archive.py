"""Документальная хронология, медиатека, деятели и источники."""
from __future__ import annotations

from functools import partial

from ui import FAINT, LINE, MUTED, RED, TEXT, WHITE, draw_scrollbar


class ArchiveScreens:
    def screen_timeline(self) -> None:
        self.background("kremlin_spasskaya", 205)
        self.header("Документальная хронология / реальные события")
        self.canvas.text("ХРОНОЛОГИЯ", (60, 112), 42, WHITE, bold=True)
        self.canvas.text("Источники открываются в браузере по вашему действию. Сюжетные решения и альтернативные главы сюда не включены.", (64, 178), 19, MUTED, max_width=1250)
        visible = (229, 681)
        top = 225 - self.scroll
        documentary = {}
        for event in self.events:
            if event["documentary"]:
                documentary.setdefault(event["chapter"], event)
        events = list(documentary.values())
        for event in events:
            y = top + event["chapter"] * 190
            if y + 176 > visible[0] and y < visible[1]:
                self.canvas.text(event["date"], (64, y), 19, WHITE, bold=True, max_width=215)
                self.canvas.text(event["title"], (300, y), 27, WHITE, bold=True, max_width=560, max_lines=2)
                self.canvas.text(event["description"], (300, y + 65), 17, MUTED, max_width=1000, max_lines=3, line_gap=4)
                self.add_button((1325, y, 205, 45), "ИСТОЧНИК", partial(self.open_url, event["source_url"]), font_size=17, align="center")
                self.canvas.line((300, y + 162), (1530, y + 162), LINE, 1, 80)
        draw_scrollbar(self.canvas, 1544, visible[0], visible[1] - visible[0], self.scroll, len(events) * 190)
        self.add_button((60, 793, 310, 54), "НАЗАД", partial(self.go, self.params.get("return_to", "menu")), "primary", font_size=22)
        self.caption("kremlin_spasskaya")

    def screen_media(self) -> None:
        self.background(None)
        self.header("Локальная медиатека / проверенные материалы")
        self.canvas.text("МЕДИАТЕКА", (60, 104), 39, WHITE, bold=True)
        self.canvas.text("АРХИВНЫЕ ФОТОГРАФИИ", (610, 113), 24, MUTED, bold=True, max_width=870, align="right")
        self.canvas.text("Только заранее сохранённые файлы. Никаких случайных загрузок при запуске.", (64, 162), 18, MUTED, max_width=1300)
        for index, item in enumerate(self.media.all()):
            column, row = index % 3, index // 3
            x, y = 60 + column * 505, 220 + row * 312 - self.scroll
            if y + 288 < 205 or y > 805:
                continue
            thumb = self.media.scene_surface(item["id"], (480, 176))
            self.canvas.raw(thumb, (x, y), (480, 176))
            self.canvas.text(item["title"], (x, y + 184), 18, WHITE, bold=True, max_width=480, max_lines=2)
            self.canvas.text(self.media.caption(item["id"]), (x, y + 232), 12, MUTED, max_width=480, max_lines=2)
            if 205 <= y + 267 <= 790:
                self.add_button((x, y + 267, 480, 30), "ОТКРЫТЬ СТРАНИЦУ ИСТОЧНИКА", partial(self.open_url, item["source_url"]), font_size=13)
        rows = (len(self.media.all()) + 2) // 3
        draw_scrollbar(self.canvas, 1544, 210, 590, self.scroll, rows * 312)
        self.add_button((60, 823, 310, 46), "НАЗАД", partial(self.go, "menu"), "primary", font_size=20)

    def screen_credits(self) -> None:
        self.background("kremlin_spasskaya", 218)
        self.header("Авторы, источники и правовые сведения")
        self.canvas.text("АВТОРЫ И ИСТОЧНИКИ", (60, 105), 37, WHITE, bold=True)
        self.canvas.text("ОБ ИГРЕ", (64, 185), 20, WHITE, bold=True)
        about = (
            "Некоммерческая художественно-документальная игра. Python + pygame. События до августа 2024 года "
            "опираются на указанные источники; решения игрока и события после августа 2024 года — альтернативная история.\n"
            "Это не официальный продукт упомянутых людей и организаций и не предсказание будущего."
        )
        self.canvas.text(about, (64, 223), 17, MUTED, max_width=1420, line_gap=5)
        top = 368 - self.scroll
        for index, item in enumerate(self.media.all()):
            y = top + index * 82
            if 315 < y < 712:
                self.canvas.text(item["title"], (64, y), 18, WHITE, bold=True, max_width=520, max_lines=2)
                self.canvas.text(f"{item['author']} / {item['license']}", (610, y), 16, TEXT, max_width=550, max_lines=2)
                if item.get("modification_description"):
                    self.canvas.text(item["modification_description"], (610, y + 38), 12, FAINT, max_width=550, max_lines=1)
                self.add_button((1190, y, 340, 44), "СТРАНИЦА ФАЙЛА", partial(self.open_url, item["source_url"]), font_size=16, align="right")
        draw_scrollbar(self.canvas, 1544, 324, 390, self.scroll, len(self.media.all()) * 82)
        self.canvas.text("Аудио: локальные синтезированные дорожки; сведения — assets/audio/credits.json. Правовые сведения — assets/credits.json; лицензии шрифтов — assets/fonts/.", (64, 738), 13, MUTED, max_width=1460)
        self.add_button((60, 802, 310, 48), "НАЗАД", partial(self.go, "menu"), "primary", font_size=20)

    def screen_people(self) -> None:
        self.background(None)
        self.header("Реальные деятели / краткий справочник")
        self.canvas.text("ПОЛИТИЧЕСКИЕ ДЕЯТЕЛИ", (60, 108), 38, WHITE, bold=True)
        self.canvas.text("Справочные данные не являются высказываниями этих людей или их участием в игре.", (64, 168), 18, MUTED, max_width=1400)
        for index, person in enumerate(self.data["people"]):
            column, row = index % 3, index // 3
            x, y = 60 + column * 505, 224 + row * 322
            self.canvas.rect((x, y, 480, 294), (20, 20, 20), alpha=225)
            self.canvas.rect((x, y, 3, 294), RED, alpha=190)
            if self.media.get(person["photo"]):
                image = self.media.scene_surface(person["photo"], (105, 128))
                self.canvas.raw(image, (x + 22, y + 22), (105, 128))
            self.canvas.text(person["name"], (x + 148, y + 24), 25, WHITE, bold=True, max_width=310, max_lines=2)
            self.canvas.text(person["role"], (x + 148, y + 90), 15, MUTED, max_width=305, max_lines=3)
            self.canvas.text(person["text"], (x + 22, y + 174), 17, TEXT, max_width=436, max_lines=5, line_gap=5)
        self.add_button((1220, 820, 310, 48), "НАЗАД", partial(self.go, "menu"), "primary", font_size=20, align="right")
