"""Публичный интерфейс игрового движка."""
from .constants import (
    APP_NAME, CHAPTER_COUNT, INITIAL_STATE, METRIC_NAMES, REGION_NAMES,
    ROUTE_NAMES, SAVE_VERSION, START_EVENT,
)
from .content import ENDINGS, event_by_id, load_endings, load_events, validate_events
from .paths import resource_root, save_directory, save_path
from .saves import has_save, load_game, save_game
from .state import advance, apply_choice, clamp, crisis_ending, ending_for, final_ending, new_state

__all__ = [
    "APP_NAME", "CHAPTER_COUNT", "ENDINGS", "INITIAL_STATE", "METRIC_NAMES",
    "REGION_NAMES", "ROUTE_NAMES", "SAVE_VERSION", "START_EVENT", "advance",
    "apply_choice", "clamp", "crisis_ending", "ending_for", "event_by_id",
    "final_ending", "has_save", "load_endings", "load_events", "load_game",
    "new_state", "resource_root", "save_directory", "save_game", "save_path",
    "validate_events",
]
