"""Атомарное локальное сохранение и проверка версии."""
from __future__ import annotations

import copy
import json
from datetime import datetime, timezone

from .constants import METRIC_NAMES, REGION_NAMES, SAVE_VERSION
from .content import ENDINGS, load_events
from .paths import save_path


def save_game(state) -> object:
    path = save_path()
    temporary = path.with_suffix(".tmp")
    payload = copy.deepcopy(state)
    payload["saved_at"] = datetime.now(timezone.utc).isoformat()
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)
    return path


def has_save() -> bool:
    return save_path().is_file()


def load_game():
    path = save_path()
    if not path.is_file():
        return None
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
        if state.get("version") != SAVE_VERSION:
            return None
        if set(state["metrics"]) != set(METRIC_NAMES) or set(state["regions"]) != set(REGION_NAMES):
            return None
        event_ids = {event["id"] for event in load_events()}
        if state["event_id"] not in event_ids or not isinstance(state["chapter"], int):
            return None
        if not 0 <= state["chapter"] < 12 or not isinstance(state["history"], list):
            return None
        values = list(state["metrics"].values()) + list(state["regions"].values())
        if any(not isinstance(value, int) or not 0 <= value <= 100 for value in values):
            return None
        if not isinstance(state["completed"], bool) or not isinstance(state["credits"], list):
            return None
        pending = state.get("pending_event")
        if pending is not None and pending != "END" and pending not in event_ids:
            return None
        if pending and not state["history"]:
            return None
        if state["completed"] and state.get("ending_id") not in ENDINGS:
            return None
        if any(not isinstance(name, str) for name in state["credits"]):
            return None
        return state
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError):
        return None
