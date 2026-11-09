import unittest

from engine.state import State
from engine.story import NODES, START_NODE, ENDINGS, compute_ending


class TestGraph(unittest.TestCase):
    def test_all_next_ids_exist_or_are_finale(self):
        for node_id, node in NODES.items():
            for label, tag, nxt, fx in node["choices"]:
                if callable(nxt):
                    continue  # data-dependent, checked separately
                self.assertTrue(
                    nxt == "FINALE" or nxt in NODES,
                    f"{node_id} points to missing node {nxt!r}",
                )

    def test_start_node_exists(self):
        self.assertIn(START_NODE, NODES)

    def test_every_node_reachable_from_start(self):
        # Explore with a couple of seed states so data-dependent branches
        # (callable `next`) can resolve to every target they support.
        seeds = [State(), State()]
        seeds[1].data["trust"] = "marina"
        seeds[1].data["left"] = False

        seen = set()
        stack = [START_NODE]
        while stack:
            nid = stack.pop()
            if nid in seen or nid == "FINALE":
                continue
            seen.add(nid)
            for label, tag, nxt, fx in NODES[nid]["choices"]:
                targets = {nxt(seed) for seed in seeds} if callable(nxt) else {nxt}
                for target in targets:
                    if target != "FINALE":
                        stack.append(target)
        self.assertEqual(seen, set(NODES.keys()))

    def test_every_node_has_at_least_one_choice(self):
        for node_id, node in NODES.items():
            self.assertTrue(len(node["choices"]) >= 1, node_id)


class TestEndings(unittest.TestCase):
    def _play(self, **flags):
        s = State(name="Тест", profession="Инженер(ка)", city="Томск")
        s.data.update(flags)
        return compute_ending(s)

    def test_win_by_default_high_voice(self):
        self.assertEqual(self._play(voice=5, joined=True, left=False, betrayed=False), "win")

    def test_emigration_when_left_and_not_joined(self):
        self.assertEqual(self._play(voice=3, joined=False, left=True, betrayed=False), "emigration")

    def test_tragic_when_betrayed_and_vocal(self):
        self.assertEqual(self._play(voice=5, joined=True, left=False, betrayed=True), "tragic")

    def test_quiet_when_low_voice_and_not_joined(self):
        self.assertEqual(self._play(voice=1, joined=False, left=False, betrayed=False), "quiet")

    def test_all_endings_defined(self):
        for key in ("win", "emigration", "tragic", "quiet"):
            self.assertIn(key, ENDINGS)


class TestState(unittest.TestCase):
    def test_format_substitutes_placeholders(self):
        s = State(name="Аня", profession="Врач", city="Казань")
        out = s.format("{name} работает {prof} в {city}")
        self.assertEqual(out, "Аня работает врач в Казань")

    def test_add_and_set(self):
        s = State()
        s.add("voice", 2)
        s.add("voice", 3)
        self.assertEqual(s.data["voice"], 5)
        s.set("joined", True)
        self.assertTrue(s.data["joined"])


if __name__ == "__main__":
    unittest.main()
