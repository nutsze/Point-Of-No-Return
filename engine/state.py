"""Player state: identity + accumulated story flags, with save/load."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict


DEFAULT_DATA = {
    "voice": 0,
    "trust": None,
    "joined": False,
    "left": False,
    "betrayed": False,
}


@dataclass
class State:
    name: str = ""
    profession: str = ""
    city: str = ""
    node: str = "n1"
    data: Dict[str, Any] = field(default_factory=lambda: dict(DEFAULT_DATA))

    def add(self, key: str, amount: int) -> None:
        self.data[key] = self.data.get(key, 0) + amount

    def set(self, key: str, value: Any) -> None:
        self.data[key] = value

    def format(self, text: str) -> str:
        return (
            text.replace("{name}", self.name or "Ты")
            .replace("{city}", self.city or "твой город")
            .replace("{prof}", (self.profession or "человек").lower())
        )

    def to_json(self) -> dict:
        return {
            "name": self.name, "profession": self.profession, "city": self.city,
            "node": self.node, "data": self.data,
        }

    @classmethod
    def from_json(cls, raw: dict) -> "State":
        s = cls()
        s.name = raw.get("name", "")
        s.profession = raw.get("profession", "")
        s.city = raw.get("city", "")
        s.node = raw.get("node", "n1")
        s.data = {**DEFAULT_DATA, **raw.get("data", {})}
        return s


def save_path() -> Path:
    return Path.home() / ".point_of_no_return_save.json"


def save(state: State) -> None:
    try:
        save_path().write_text(json.dumps(state.to_json(), ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError:
        pass


def load() -> State | None:
    p = save_path()
    if not p.exists():
        return None
    try:
        return State.from_json(json.loads(p.read_text(encoding="utf-8")))
    except (OSError, json.JSONDecodeError):
        return None


def clear() -> None:
    try:
        save_path().unlink(missing_ok=True)
    except OSError:
        pass
