"""Загрузка и проверка сюжетного графа и концовок."""
from __future__ import annotations

import json
from functools import lru_cache
from typing import Any

from .constants import CHAPTER_COUNT, START_EVENT
from .paths import resource_root

EVENT_FIELDS = {
    "id", "chapter", "date", "title", "description", "photo", "forces",
    "documentary", "choices", "route",
}
CHOICE_FIELDS = {"text", "result", "effects", "next"}


def _read(path):
    return json.loads(path.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def load_events() -> list[dict[str, Any]]:
    folder = resource_root() / "data" / "chapters"
    events = []
    for path in sorted(folder.glob("*.json")):
        payload = _read(path)
        events.extend(payload["events"])
    validate_events(events)
    return events


@lru_cache(maxsize=1)
def load_endings() -> dict[str, dict[str, Any]]:
    return _read(resource_root() / "data" / "endings.json")


ENDINGS = load_endings()


def event_by_id(events: list[dict[str, Any]], event_id: str) -> dict[str, Any]:
    for event in events:
        if event["id"] == event_id:
            return event
    raise KeyError(f"Неизвестный эпизод: {event_id}")


def validate_events(events: list[dict[str, Any]]) -> None:
    by_id = {}
    chapters = {index: [] for index in range(CHAPTER_COUNT)}
    for event in events:
        missing = EVENT_FIELDS - event.keys()
        if missing:
            raise ValueError(f"В эпизоде отсутствуют поля: {sorted(missing)}")
        event_id = event["id"]
        if event_id in by_id:
            raise ValueError(f"Повторяющийся id эпизода: {event_id}")
        by_id[event_id] = event
        chapter = event["chapter"]
        if chapter not in chapters:
            raise ValueError(f"Некорректный этап: {event_id}")
        chapters[chapter].append(event)
        if event["documentary"] and not (event.get("source_name") and event.get("source_url")):
            raise ValueError(f"У документального эпизода {event_id} нет источника")
        if not event["documentary"] and not event["description"].startswith("АЛЬТЕРНАТИВНАЯ ИСТОРИЯ"):
            raise ValueError(f"Альтернативный эпизод {event_id} не промаркирован")
        if len(event["choices"]) != 3:
            raise ValueError(f"В эпизоде {event_id} должно быть три решения")
        for choice in event["choices"]:
            if CHOICE_FIELDS - choice.keys():
                raise ValueError(f"Неполное решение в {event_id}")
            if chapter == CHAPTER_COUNT - 1 and choice["next"] != "END":
                raise ValueError(f"Финальное решение не завершает кампанию: {event_id}")
            if chapter < CHAPTER_COUNT - 1 and choice["next"] == "END":
                raise ValueError(f"Преждевременный выход: {event_id}")
    if set(by_id) != set(event["id"] for event in events):
        raise ValueError("Ошибка индексации сценария")
    if len(chapters[0]) != 1 or chapters[0][0]["id"] != START_EVENT:
        raise ValueError("Некорректный стартовый эпизод")
    for chapter in range(1, CHAPTER_COUNT):
        if len(chapters[chapter]) != 3:
            raise ValueError(f"Этап {chapter + 1} должен содержать три ветви")
    for event in events:
        for choice in event["choices"]:
            target = choice["next"]
            if target == "END":
                if not choice.get("ending") or choice["ending"] not in ENDINGS:
                    raise ValueError(f"Не указана концовка в {event['id']}")
                if choice.get("fallback") not in ENDINGS:
                    raise ValueError(f"Не указан запасной финал в {event['id']}")
            else:
                target_event = by_id.get(target)
                if not target_event or target_event["chapter"] != event["chapter"] + 1:
                    raise ValueError(f"Некорректный переход {event['id']} -> {target}")
    _validate_reachability(chapters[0][0], by_id)


def _validate_reachability(start, by_id) -> None:
    reached = {start["id"]}
    frontier = [start]
    while frontier:
        event = frontier.pop()
        for choice in event["choices"]:
            target = choice["next"]
            if target != "END" and target not in reached:
                reached.add(target)
                frontier.append(by_id[target])
    if len(reached) != len(by_id):
        raise ValueError("Не все сюжетные ветви достижимы")
