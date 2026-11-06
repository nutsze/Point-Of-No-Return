import copy
import os
import tempfile
import unittest
from unittest.mock import patch

from engine import (
    ENDINGS, METRIC_NAMES, REGION_NAMES, SAVE_VERSION, advance, apply_choice,
    event_by_id, final_ending, load_events, load_game, new_state, save_game,
)


ENDING_PATHS = {
    "open_door": (0,) * 8 + (2, 2, 0, 0),
    "civic_pact": (0,) * 9 + (2, 1, 0),
    "regional_federation": (0,) * 9 + (2, 1, 1),
    "public_archive": (0,) * 10 + (2, 2),
    "fragile_mandate": (0,) * 9 + (1, 2, 0),
    "network_survives": (0,) * 9 + (1, 1, 2),
    "split": (0,) * 3 + (2,) * 9,
    "exhaustion": (0,) * 10 + (1, 0),
    "long_road": (0, 0, 1, 2, 2, 0, 0, 1, 1, 1, 2, 1),
    "shutdown": (0, 0) + (2,) * 10,
    "no_trust": (2,) * 12,
    "no_resources": (0,) * 12,
}


class EngineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.events = load_events()
        cls.by_id = {event["id"]: event for event in cls.events}

    def play(self, path):
        state = new_state()
        for choice in path:
            apply_choice(state, self.by_id[state["event_id"]], choice)
            if state["completed"]:
                break
            advance(state, self.events)
        return state

    def test_graph_shape_and_distinct_transitions(self):
        self.assertEqual(len(self.events), 34)
        self.assertEqual(sum(len(event["choices"]) for event in self.events), 102)
        chapters = {chapter: 0 for chapter in range(12)}
        for event in self.events:
            chapters[event["chapter"]] += 1
            self.assertEqual(len(event["choices"]), 3)
            targets = {choice["next"] for choice in event["choices"]}
            if event["chapter"] < 11:
                self.assertEqual(len(targets), 3, event["id"])
            else:
                self.assertEqual(targets, {"END"})
            for choice in event["choices"]:
                self.assertFalse(set(choice["effects"]) - set(METRIC_NAMES))
                self.assertFalse(set(choice.get("regions", {})) - set(REGION_NAMES))
                if choice["next"] != "END":
                    self.assertEqual(self.by_id[choice["next"]]["chapter"], event["chapter"] + 1)
        self.assertEqual(chapters[0], 1)
        self.assertTrue(all(chapters[chapter] == 3 for chapter in range(1, 12)))

    def test_route_switch_changes_the_next_episode(self):
        state = new_state()
        apply_choice(state, self.by_id[state["event_id"]], 0)
        advance(state, self.events)
        self.assertEqual(state["event_id"], "e01_legal")
        apply_choice(state, self.by_id[state["event_id"]], 1)
        advance(state, self.events)
        self.assertEqual(state["event_id"], "e02_grassroots")
        apply_choice(state, self.by_id[state["event_id"]], 2)
        advance(state, self.events)
        self.assertEqual(state["event_id"], "e03_media")

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

    def test_save_round_trip_version_and_corrupt_save(self):
        with tempfile.TemporaryDirectory() as home, patch.dict(os.environ, {"HOME": home}):
            state = self.play((1, 2, 0))
            save_game(state)
            loaded = load_game()
            self.assertEqual(loaded["version"], SAVE_VERSION)
            self.assertEqual(loaded["history"], state["history"])
            self.assertEqual(loaded["event_id"], state["event_id"])
            path = save_game(state)
            payload = path.read_text(encoding="utf-8").replace(f'"version": {SAVE_VERSION}', '"version": 1', 1)
            path.write_text(payload, encoding="utf-8")
            self.assertIsNone(load_game())
            path.write_text("{broken", encoding="utf-8")
            self.assertIsNone(load_game())


if __name__ == "__main__":
    unittest.main()
