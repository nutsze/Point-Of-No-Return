"""Переходы по сюжетному графу, последствия и концовки."""
from __future__ import annotations

import copy
from datetime import datetime, timezone
from typing import Any

from .constants import INITIAL_STATE
from .content import ENDINGS


def new_state() -> dict[str, Any]:
    state = copy.deepcopy(INITIAL_STATE)
    state["started_at"] = datetime.now(timezone.utc).isoformat()
    return state


def clamp(value: int) -> int:
    return max(0, min(100, int(value)))


def apply_choice(state, event, choice_index: int) -> None:
    if state["completed"]:
        raise ValueError("Кампания уже завершена")
    if event["id"] != state["event_id"] or state["pending_event"]:
        raise ValueError("Эпизод не соответствует сохранённому состоянию")
    if not 0 <= choice_index < len(event["choices"]):
        raise IndexError("Некорректный вариант решения")
    choice = event["choices"][choice_index]
    for key, delta in choice["effects"].items():
        if key in state["metrics"]:
            state["metrics"][key] = clamp(state["metrics"][key] + delta)
    for key, delta in choice.get("regions", {}).items():
        if key in state["regions"]:
            state["regions"][key] = clamp(state["regions"][key] + delta)
    state["route"] = choice.get("route", state["route"])
    for name in choice.get("credits", []):
        if name not in state["credits"]:
            state["credits"].append(name)
    state["alternative_history"] = True
    state["pending_event"] = choice["next"]
    state["history"].append({
        "event_id": event["id"],
        "event_date": event["date"],
        "event_title": event["title"],
        "choice_index": choice_index,
        "choice": choice["text"],
        "result": choice["result"],
        "route": state["route"],
        "next": choice["next"],
        "ending": choice.get("ending"),
        "fallback": choice.get("fallback"),
        "metrics_after": dict(state["metrics"]),
    })
    state["ending_id"] = crisis_ending(state)
    if state["ending_id"]:
        state["completed"] = True


def advance(state, events=None) -> None:
    if state["completed"]:
        return
    target = state["pending_event"]
    if not target:
        raise ValueError("Сначала необходимо принять решение")
    if target == "END":
        state["completed"] = True
        state["ending_id"] = final_ending(state)
    else:
        state["event_id"] = target
        state["chapter"] += 1
    state["pending_event"] = None


def crisis_ending(state) -> str | None:
    metrics = state["metrics"]
    if metrics["trust"] <= 0:
        return "no_trust"
    if metrics["resources"] <= 0:
        return "no_resources"
    if metrics["pressure"] >= 100:
        return "shutdown"
    return None


def final_ending(state) -> str:
    crisis = crisis_ending(state)
    if crisis:
        return crisis
    if not state["history"]:
        return "long_road"
    metrics = state["metrics"]
    if metrics["trust"] < 25:
        return "split"
    if metrics["resources"] < 10:
        return "exhaustion"
    last = state["history"][-1]
    developed = sum(value >= 28 for value in state["regions"].values())
    successful = (
        metrics["support"] >= 35 and metrics["trust"] >= 25
        and metrics["resources"] >= 10 and metrics["pressure"] < 100
        and developed >= 2
    )
    return last["ending"] if successful else last.get("fallback", "long_road")


def ending_for(state) -> dict[str, Any]:
    return ENDINGS[state.get("ending_id") or final_ending(state)]
