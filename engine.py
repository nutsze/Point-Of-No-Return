"""Игровая логика «2030: Точка невозврата». Не зависит от графической библиотеки."""
from __future__ import annotations

import copy
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

APP_NAME = "2030: Точка невозврата"
SAVE_VERSION = 1

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

INITIAL_STATE: dict[str, Any] = {
    "version": SAVE_VERSION,
    "event_index": 0,
    "metrics": {"support": 18, "resources": 38, "trust": 52, "pressure": 22},
    "regions": {
        "moscow": 24,
        "spb": 22,
        "volga": 12,
        "nizhny": 14,
        "ural": 13,
        "siberia": 14,
        "south": 8,
        "far_east": 10,
    },
    "alternative_history": False,
    "history": [],
    "completed": False,
    "ending_id": None,
    "started_at": None,
}


def resource_root() -> Path:
    """Каталог ресурсов: исходный проект или распакованные данные PyInstaller."""
    bundle = getattr(sys, "_MEIPASS", None)
    return Path(bundle) if bundle else Path(__file__).resolve().parent


def save_directory() -> Path:
    if os.name == "nt" and os.environ.get("APPDATA"):
        base = Path(os.environ["APPDATA"])
    else:
        base = Path.home() / ".point_of_no_return"
    path = base / "PointOfNoReturn"
    path.mkdir(parents=True, exist_ok=True)
    return path


def save_path() -> Path:
    return save_directory() / "autosave.json"


def load_events() -> list[dict[str, Any]]:
    path = resource_root() / "data" / "events.json"
    with path.open("r", encoding="utf-8") as handle:
        events = json.load(handle)
    validate_events(events)
    return events


def validate_events(events: list[dict[str, Any]]) -> None:
    required = {"id", "date", "title", "description", "photo", "forces", "documentary", "choices"}
    ids: set[str] = set()
    for event in events:
        missing = required - event.keys()
        if missing:
            raise ValueError(f"Событие не содержит поля: {sorted(missing)}")
        if event["id"] in ids:
            raise ValueError(f"Повторяющийся id события: {event['id']}")
        ids.add(event["id"])
        if event["documentary"] and (not event.get("source_name") or not event.get("source_url")):
            raise ValueError(f"У документального события {event['id']} нет источника")
        if not event["documentary"] and not event["description"].startswith("АЛЬТЕРНАТИВНАЯ ИСТОРИЯ"):
            raise ValueError(f"Альтернативное событие {event['id']} не промаркировано")
        if len(event["choices"]) != 3:
            raise ValueError(f"В событии {event['id']} должно быть три решения")


def new_state() -> dict[str, Any]:
    state = copy.deepcopy(INITIAL_STATE)
    state["started_at"] = datetime.now(timezone.utc).isoformat()
    return state


def clamp(value: int) -> int:
    return max(0, min(100, int(value)))


def apply_choice(state: dict[str, Any], event: dict[str, Any], choice_index: int) -> dict[str, int]:
    """Применяет решение, но не переводит игру к следующему событию."""
    if state["completed"]:
        raise ValueError("Кампания уже завершена")
    if not 0 <= choice_index < len(event["choices"]):
        raise IndexError("Некорректный вариант решения")
    choice = event["choices"][choice_index]
    before = dict(state["metrics"])
    for key, delta in choice["effects"].items():
        if key in state["metrics"]:
            state["metrics"][key] = clamp(state["metrics"][key] + delta)
    for key, delta in choice.get("regions", {}).items():
        if key in state["regions"]:
            state["regions"][key] = clamp(state["regions"][key] + delta)
    state["alternative_history"] = True
    state["history"].append({
        "event_id": event["id"],
        "event_date": event["date"],
        "event_title": event["title"],
        "choice_index": choice_index,
        "choice": choice["text"],
        "result": choice["result"],
        "metrics_after": dict(state["metrics"]),
    })
    state["ending_id"] = crisis_ending(state)
    if state["ending_id"]:
        state["completed"] = True
    return {key: state["metrics"][key] - before[key] for key in before}


def advance(state: dict[str, Any], events: list[dict[str, Any]]) -> None:
    if state["completed"]:
        return
    state["event_index"] += 1
    if state["event_index"] >= len(events):
        state["event_index"] = len(events) - 1
        state["completed"] = True
        state["ending_id"] = final_ending(state)


def crisis_ending(state: dict[str, Any]) -> str | None:
    metrics = state["metrics"]
    if metrics["pressure"] >= 100:
        return "shutdown"
    if metrics["trust"] <= 0:
        return "no_trust"
    if metrics["resources"] <= 0:
        return "no_resources"
    return None


def final_ending(state: dict[str, Any]) -> str:
    crisis = crisis_ending(state)
    if crisis:
        return crisis
    m = state["metrics"]
    developed_regions = sum(value >= 30 for value in state["regions"].values())
    if m["support"] >= 62 and m["trust"] >= 58 and m["resources"] >= 20 and m["pressure"] < 75 and developed_regions >= 4:
        return "open_door"
    if m["trust"] < 35:
        return "split"
    if m["resources"] < 10:
        return "exhaustion"
    if m["pressure"] >= 75 and m["trust"] >= 50 and m["resources"] >= 10:
        return "network_survives"
    if m["support"] >= 45 and m["trust"] >= 45 and m["resources"] >= 10:
        return "fragile_mandate"
    return "long_road"


ENDINGS: dict[str, dict[str, str]] = {
    "open_door": {
        "title": "ОТКРЫТАЯ ДВЕРЬ",
        "subtitle": "Общенациональный прорыв",
        "text": "Коалиция получает общенациональное представительство, а региональные сети — реальное влияние. Это не конец истории: теперь обещания придётся превращать в институты, сохраняя доверие избирателей и внутренний плюрализм.",
    },
    "fragile_mandate": {
        "title": "ХРУПКИЙ МАНДАТ",
        "subtitle": "Ограниченный, но реальный успех",
        "text": "Движение закрепляется в нескольких регионах и получает право участвовать в публичных решениях. Победа уязвима: ресурсов немного, союзники спорят, а давление сохраняется. Следующий этап потребует дисциплины и открытой отчётности.",
    },
    "network_survives": {
        "title": "СЕТЬ ВЫЖИВАЕТ",
        "subtitle": "Сопротивление изоляции",
        "text": "Публичная политика сильно ограничена, но распределённая сеть сохраняет юридическую помощь, архив и местные инициативы. Быстрого прорыва нет; главным результатом становится устойчивость гражданских связей.",
    },
    "split": {
        "title": "РАСКОЛ",
        "subtitle": "Коалиция теряет общий центр",
        "text": "Накопленные разногласия оказываются сильнее общей программы. Часть региональных групп продолжает работу самостоятельно, однако общенациональная кампания распадается. Доверие придётся восстанавливать с самого начала.",
    },
    "exhaustion": {
        "title": "ИСТОЩЕНИЕ",
        "subtitle": "Ресурсов больше нет",
        "text": "Программа оказывается шире финансовых и кадровых возможностей. Штабы сокращаются, а часть инициатив передаётся независимым сообществам. Стратегия масштабирования без устойчивой базы не выдерживает испытания временем.",
    },
    "long_road": {
        "title": "ДОЛГИЙ ПУТЬ",
        "subtitle": "Точка невозврата ещё впереди",
        "text": "Движение сохраняется, но не получает решающего преимущества. Его достижения неодинаковы по регионам, а поддержка остаётся фрагментированной. История продолжается — теперь уже без гарантированного финала.",
    },
    "shutdown": {
        "title": "ПРИНУДИТЕЛЬНАЯ ОСТАНОВКА",
        "subtitle": "Давление превысило возможности организации",
        "text": "Общий центр прекращает публичную работу. Отдельные инициативы продолжают существовать независимо, но кампания в прежнем виде завершена. Решения, повышавшие охват ценой риска, привели к критическому результату.",
    },
    "no_trust": {
        "title": "ПОТЕРЯ ДОВЕРИЯ",
        "subtitle": "Коалиция перестаёт существовать",
        "text": "Участники отзывают делегатов и прекращают совместную работу. Без доверия даже значительные ресурсы и публичная поддержка не позволяют сохранить общую стратегию.",
    },
    "no_resources": {
        "title": "РЕСУРСЫ ИСЧЕРПАНЫ",
        "subtitle": "Кампания не может продолжаться",
        "text": "Финансовые и кадровые резервы исчерпаны. Дальнейшие обязательства невозможно выполнить, поэтому совет объявляет о завершении кампании и передаче архива независимым группам.",
    },
}


def save_game(state: dict[str, Any]) -> Path:
    path = save_path()
    temporary = path.with_suffix(".tmp")
    payload = copy.deepcopy(state)
    payload["saved_at"] = datetime.now(timezone.utc).isoformat()
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)
    return path


def has_save() -> bool:
    return save_path().is_file()


def load_game() -> dict[str, Any] | None:
    path = save_path()
    if not path.is_file():
        return None
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
        if state.get("version") != SAVE_VERSION:
            return None
        if set(state["metrics"]) != set(METRIC_NAMES) or set(state["regions"]) != set(REGION_NAMES):
            return None
        if not isinstance(state["history"], list) or not isinstance(state["event_index"], int):
            return None
        if not 0 <= state["event_index"] < len(load_events()):
            return None
        values = list(state["metrics"].values()) + list(state["regions"].values())
        if any(not isinstance(value, int) or not 0 <= value <= 100 for value in values):
            return None
        if not isinstance(state["completed"], bool):
            return None
        return state
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError):
        return None
