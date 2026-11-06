"""Общие константы игрового состояния."""
from __future__ import annotations

from typing import Any

APP_NAME = "2030: Точка невозврата"
SAVE_VERSION = 2
START_EVENT = "e00"
CHAPTER_COUNT = 12

METRIC_NAMES = {
    "support": "Общественная поддержка",
    "resources": "Ресурсы",
    "trust": "Доверие в коалиции",
    "pressure": "Политическое давление",
}
REGION_NAMES = {
    "moscow": "Москва",
    "spb": "Санкт-Петербург",
    "volga": "Поволжье",
    "nizhny": "Нижний Новгород",
    "ural": "Урал",
    "siberia": "Сибирь",
    "south": "Юг",
    "far_east": "Дальний Восток",
}
ROUTE_NAMES = {
    "legal": "Правовая коалиция",
    "grassroots": "Региональная сеть",
    "media": "Независимая медиаплатформа",
}
INITIAL_STATE: dict[str, Any] = {
    "version": SAVE_VERSION,
    "event_id": START_EVENT,
    "chapter": 0,
    "pending_event": None,
    "metrics": {"support": 22, "resources": 45, "trust": 55, "pressure": 20},
    "regions": {
        "moscow": 24, "spb": 22, "volga": 12, "nizhny": 14,
        "ural": 13, "siberia": 14, "south": 8, "far_east": 10,
    },
    "route": "legal",
    "credits": ["Алексей Навальный †"],
    "alternative_history": False,
    "history": [],
    "completed": False,
    "ending_id": None,
    "started_at": None,
}
