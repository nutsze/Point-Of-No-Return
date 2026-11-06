"""Пути к ресурсам и локальным сохранениям."""
from __future__ import annotations

import os
import sys
from pathlib import Path


def resource_root() -> Path:
    bundle = getattr(sys, "_MEIPASS", None)
    return Path(bundle) if bundle else Path(__file__).resolve().parents[1]


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
