"""Player state: identity, accumulated story flags, save/load."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict

from .story import CITIES, PROF_WORLD, PROFESSIONS, START_NODE

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
    "mom_argued": False,  # stood up to the mother about the news
    "ashamed": False,     # looked away when Marina was detained
    "talked": False,      # told the security services what they asked
    # remembered for the epilogue
    "filmed": False, "apologized": False, "observer": False, "refused_kprf": False,
    "letter": None, "letters": False, "promised_mom": False, "dima_abroad": False,
    "grief": None, "helped_flood": False, "price_tag": False, "marina_friend": False,
    "kept_sign": False, "collector": False, "flowers": False, "helped_teens": False,
    "campaigned": False, "role": None,
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

    def pick(self, value):
        """Resolve a profession-keyed dict or a callable into a concrete value."""
        if callable(value):
            return value(self)
        if isinstance(value, dict):
            return value.get(self.profession, value.get("default"))
        return value

    def format(self, text) -> str:
        text = self.pick(text) or ""
        text = _GENDER.sub(lambda m: m.group(2 if self.gender == "f" else 1), text)
        world = PROF_WORLD.get(self.profession, PROF_WORLD["engineer"])
        boss = world["boss"]
        return (text
                .replace("{mate}", world["mate"])
                .replace("{Boss}", boss[:1].upper() + boss[1:])
                .replace("{boss}", boss)
                .replace("{at_work}", world["at_work"])
                .replace("{to_work}", world["to_work"])
                .replace("{life}", world.get("life", "работает " + self.prof("ins")))
                .replace("{routine}", world.get("routine", "работа, кредит"))
                .replace("{work_chat}", world.get("work_chat", "рабочий чат"))
                .replace("{abroad_job}", world.get("abroad_job", "работа на удалёнке за полцены"))
                .replace("{workplace}", world.get("workplace", "место работы"))
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
