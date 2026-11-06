"""Пауза, настройки и справка."""
from __future__ import annotations

from functools import partial

from ui import LINE, MUTED, TEXT, WHITE


class SystemScreens:
    def screen_pause(self) -> None:
        self.background("kremlin_spasskaya", 175)
        self.header("Пауза")
        self.canvas.text("ПАУЗА", (550, 170), 58, WHITE, max_width=500, bold=True, align="center")
        entries = [
            ("ПРОДОЛЖИТЬ", partial(self.go, self.return_screen, **self.return_params)),
            ("СОХРАНИТЬ", self.manual_save),
            ("НАСТРОЙКИ", partial(self.go, "settings", return_to="pause")),
            ("ПРАВИЛА И УПРАВЛЕНИЕ", partial(self.go, "help", return_to="pause")),
            ("ГЛАВНОЕ МЕНЮ", partial(self.go, "menu")),
        ]
        for index, (label, action) in enumerate(entries):
            self.add_button((510, 286 + index * 83, 580, 62), label, action, "primary" if index == 0 else "ghost", font_size=27, align="center")
        self.add_button((620, 748, 360, 50), "ВЫХОД ИЗ ИГРЫ", self.quit, font_size=19, align="center")
        self.caption("kremlin_spasskaya")

    def screen_settings(self) -> None:
        self.background("kremlin_spasskaya", 205)
        self.header("Настройки / локальное аудио и дисплей")
        self.canvas.text("НАСТРОЙКИ", (60, 118), 45, WHITE, bold=True)
        rows = [("МУЗЫКА", "music"), ("ГОЛОС", "voice"), ("СИГНАЛЫ ИНТЕРФЕЙСА", "sfx")]
        for index, (label, name) in enumerate(rows):
            y = 230 + index * 104
            value = getattr(self.audio, f"{name}_volume")
            self.canvas.text(label, (86, y), 24, TEXT, bold=True)
            self.canvas.text(f"{round(value * 100)}%", (650, y), 25, WHITE, max_width=100, align="right")
            self.add_button((790, y - 8, 80, 54), "-", partial(self.audio.adjust, name, -0.05), font_size=30, align="center")
            self.add_button((900, y - 8, 80, 54), "+", partial(self.audio.adjust, name, 0.05), font_size=28, align="center")
        self.canvas.line((84, 552), (980, 552), LINE, 1, 80)
        self.add_button((86, 590, 560, 54), f"ГОЛОСОВОЕ ОЗВУЧИВАНИЕ: {'ВКЛ' if self.audio.voice_enabled else 'ВЫКЛ'}", self.audio.toggle_voice, font_size=22)
        self.add_button((86, 658, 560, 54), f"ЗВУК: {'ВЫКЛ' if self.audio.muted else 'ВКЛ'}", self.audio.toggle_mute, font_size=22)
        width, height = self.window.get_size()
        self.canvas.text("РАЗРЕШЕНИЕ", (1080, 232), 17, MUTED, bold=True)
        self.canvas.text(f"{width} × {height}", (1080, 270), 35, WHITE, bold=True)
        self.canvas.text("Интерфейс и текст рендерятся в фактическом разрешении окна. Поддерживаются 2K и 4K без растягивания готового кадра.", (1080, 337), 20, MUTED, max_width=410, line_gap=6)
        self.add_button((1080, 485, 420, 56), "ОКОННЫЙ РЕЖИМ" if self.fullscreen else "ПОЛНЫЙ ЭКРАН", self.toggle_fullscreen, font_size=23)
        self.canvas.text("M — выключить звук\nV — включить или выключить голос\nF11 — полный экран", (1080, 584), 19, MUTED, max_width=410, line_gap=10)
        self.add_button((1080, 776, 420, 52), "НАЗАД", partial(self.go, self.params.get("return_to", "menu")), "primary", font_size=23, align="right")
        self.caption("kremlin_spasskaya")

    def screen_help(self) -> None:
        self.background("kremlin_spasskaya", 215)
        self.header("Правила и управление")
        self.canvas.text("КАК ИГРАТЬ", (58, 110), 42, WHITE, bold=True)
        rules = (
            "1. Каждый вариант открывает конкретный следующий эпизод. Всего в кампании 34 сцены и 102 решения.\n\n"
            "2. Правовая, региональная и информационная ветви имеют разные сцены, союзников и последствия.\n\n"
            "3. Стратегию можно менять. Финал и титры учитывают весь пройденный маршрут.\n\n"
            "4. Прогресс автоматически сохраняется после каждого решения."
        )
        self.canvas.text(rules, (62, 199), 23, TEXT, max_width=780, line_gap=8)
        controls = [
            ("Мышь", "Выбор и прокрутка"), ("↑ / ↓ / Tab", "Переход между вариантами"),
            ("Enter / Space", "Подтвердить"), ("1 / 2 / 3", "Выбрать решение"),
            ("Esc", "Пауза или возврат"), ("F11", "Полноэкранный режим"),
            ("M / V", "Звук / голос"), ("Ctrl + S", "Сохранить вручную"),
        ]
        for index, (key, action) in enumerate(controls):
            y = 206 + index * 60
            self.canvas.text(key, (930, y), 20, WHITE, bold=True, mono=True, max_width=200)
            self.canvas.text(action, (1150, y), 20, MUTED, max_width=360)
        self.add_button((1160, 776, 370, 54), "НАЗАД", partial(self.go, self.params.get("return_to", "menu")), "primary", font_size=23, align="right")
        self.canvas.text("Сохранение: %APPDATA% / PointOfNoReturn / autosave.json", (62, 827), 13, MUTED, max_width=800)
        self.caption("kremlin_spasskaya")
