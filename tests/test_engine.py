import copy
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from engine import (
    ENDINGS, METRIC_NAMES, REGION_NAMES, advance, apply_choice, final_ending,
    load_events, load_game, new_state, save_game,
)


ENDING_PATHS = {
    "open_door": (0, 0, 1, 1, 1, 2, 2, 2, 1, 1, 2, 1),
    "fragile_mandate": (0, 0, 0, 0, 0, 0, 0, 1, 2, 0, 2, 2),
    "network_survives": (0, 0, 0, 1, 1, 0, 0, 0, 1, 0, 2, 0),
    "split": (0, 0, 0, 1, 2, 2, 2, 1, 1, 0, 2, 0),
    "exhaustion": (0, 0, 0, 0, 0, 0, 0, 0, 0, 2, 2, 0),
    "long_road": (0, 0, 0, 0, 0, 0, 0, 0, 0, 2, 2, 2),
    "shutdown": (0, 0, 2, 1, 1, 0, 0, 0, 0, 0, 0, 0),
    "no_trust": (1, 1, 2, 1, 2, 2, 2, 1, 1, 0, 2, 0),
    "no_resources": (0,) * 12,
}


class EngineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.events = load_events()

    def play(self, path):
        state = new_state()
        for index, choice in enumerate(path):
            apply_choice(state, self.events[index], choice)
            if state["completed"]:
                break
            advance(state, self.events)
        return state

    def test_content_shape(self):
        self.assertEqual(len(self.events), 12)
        self.assertEqual(sum(event["documentary"] for event in self.events), 9)
        for event in self.events:
            self.assertEqual(len(event["choices"]), 3)
            for choice in event["choices"]:
                labels = {"support": "Поддержка", "resources": "Ресурсы", "trust": "Доверие", "pressure": "Давление"}
                for key in choice["effects"]:
                    self.assertIn(key, METRIC_NAMES)
                    self.assertIn(labels[key], choice["detail"])
                for key in choice.get("regions", {}):
                    self.assertIn(key, REGION_NAMES)

    def test_every_ending_is_reachable(self):
        self.assertEqual(set(ENDING_PATHS), set(ENDINGS))
        for expected, path in ENDING_PATHS.items():
            with self.subTest(ending=expected):
                state = self.play(path)
                self.assertEqual(state["ending_id"] or final_ending(state), expected)

    def test_metrics_are_clamped(self):
        state = new_state()
        event = copy.deepcopy(self.events[0])
        event["choices"][0]["effects"] = {"support": 999, "resources": -999}
        apply_choice(state, event, 0)
        self.assertEqual(state["metrics"]["support"], 100)
        self.assertTrue(state["completed"])
        self.assertEqual(state["ending_id"], "no_resources")

    def test_save_round_trip_and_corrupt_save(self):
        with tempfile.TemporaryDirectory() as home, patch.dict(os.environ, {"HOME": home}):
            state = self.play((1, 2, 0))
            save_game(state)
            loaded = load_game()
            self.assertEqual(loaded["history"], state["history"])
            self.assertEqual(loaded["event_index"], state["event_index"])
            save_game(state).write_text("{broken", encoding="utf-8")
            self.assertIsNone(load_game())


if __name__ == "__main__":
    unittest.main()
