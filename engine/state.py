"""Player state: identity, accumulated story flags, save/load."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict

from .story import CITIES, PROFESSIONS, START_NODE

DEFAULT_DATA = {
    "voice": 0,        # how much the hero speaks and acts
    "risk": 0,         # how visible the hero is to the security services
    "org": None,       # fbk / yabloko / kprf / vesna / ovd / diaspora
    "member": False,   # holds a party card
    "trust": None,     # oleg / marina / none
    "left": False,     # emigrated
    "arrested": False,
    "betrayed": False,
    "saved_dima": None,
    "jobless": False,
    "detentions": 0,
}

_GENDER = re.compile(r"\[\[([^|\]]*)\|([^\]]*)\]\]")


@dataclass
class State:
    name: str = ""
    gender: str = "m"       # "m" or "f"
    profession: str = ""    # key of PROFESSIONS
    city: str = ""          # key of CITIES
    node: str = START_NODE
    data: Dict[str, Any] = field(default_factory=lambda: dict(DEFAULT_DATA))

    def add(self, key: str, amount: int) -> None:
        self.data[key] = (self.data.get(key) or 0) + amount

    def set(self, key: str, value: Any) -> None:
        self.data[key] = value

    # ---------------------------------------------------------- text --

    def prof(self, case: str = "nom") -> str:
        forms = PROFESSIONS.get(self.profession)
        if not forms:
            return "человек" if case == "nom" else "человеком"
        f = self.gender == "f"
        return forms[1 if f else 0] if case == "nom" else forms[3 if f else 2]

    def city_form(self, case: str = "nom") -> str:
        if self.city not in CITIES:
            return {"nom": "город", "gen": "города", "pre": "городе"}[case]
        gen, pre = CITIES[self.city]
        return {"nom": self.city, "gen": gen, "pre": pre}[case]

    def format(self, text: str) -> str:
        text = _GENDER.sub(lambda m: m.group(2 if self.gender == "f" else 1), text)
        return (text
                .replace("{name}", self.name or "Ты")
                .replace("{prof_ins}", self.prof("ins"))
                .replace("{prof}", self.prof("nom"))
                .replace("{city_gen}", self.city_form("gen"))
                .replace("{city_pre}", self.city_form("pre"))
                .replace("{city}", self.city_form("nom")))

    # ---------------------------------------------------------- save --

    def to_json(self) -> dict:
        return {"name": self.name, "gender": self.gender, "profession": self.profession,
                "city": self.city, "node": self.node, "data": self.data, "version": 3}

    @classmethod
    def from_json(cls, raw: dict) -> "State":
        if raw.get("version") != 3:
            raise ValueError("old save format")
        s = cls()
        for key in ("name", "gender", "profession", "city", "node"):
            setattr(s, key, raw.get(key, getattr(s, key)))
        s.data = {**DEFAULT_DATA, **raw.get("data", {})}
        return s


def save_path() -> Path:
    return Path.home() / ".ten_winters_save.json"


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
    except (OSError, ValueError, json.JSONDecodeError):
        return None


def clear() -> None:
    try:
        save_path().unlink(missing_ok=True)
    except OSError:
        pass
