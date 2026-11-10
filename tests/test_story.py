import itertools
import unittest

from engine.state import State
from engine.story import CHAPTERS, CITIES, ENDINGS, NODES, PROFESSIONS, START_NODE, compute_ending, epilogue


def targets(choice, seeds):
    _label, nxt, _fx = choice
    return {nxt(s) for s in seeds} if callable(nxt) else {nxt}


def seed_states():
    """States covering every flag combination that data-dependent branches read."""
    out = []
    for saved, risk, voice, left, arrested, trust, org in itertools.product(
            (True, False), (0, 10), (0, 10), (False, True), (False, True),
            ("marina", "oleg"), (None, "fbk")):
        s = State()
        s.data.update(saved_dima=saved, risk=risk, voice=voice, left=left, arrested=arrested,
                      trust=trust, org=org)
        out.append(s)
    court = State()
    court.data.update(court_support=True)
    out.append(court)
    return out


class TestGraph(unittest.TestCase):
    def test_every_target_exists(self):
        seeds = seed_states()
        for nid, node in NODES.items():
            for choice in node["choices"]:
                for t in targets(choice, seeds):
                    self.assertTrue(t == "FINALE" or t in NODES, f"{nid} -> missing {t!r}")

    def test_every_node_reachable(self):
        seeds = seed_states()
        seen, stack = set(), [START_NODE]
        while stack:
            nid = stack.pop()
            if nid in seen or nid == "FINALE":
                continue
            seen.add(nid)
            for choice in NODES[nid]["choices"]:
                stack.extend(targets(choice, seeds))
        self.assertEqual(set(NODES) - seen, set())

    def test_twelve_chapters_all_used(self):
        self.assertEqual(sorted(CHAPTERS), list(range(1, 13)))
        self.assertEqual({n["chapter"] for n in NODES.values()}, set(range(1, 13)))

    def test_quotes_have_speaker_and_source(self):
        for nid, node in NODES.items():
            q = node.get("quote")
            if q:
                self.assertTrue(q["text"] and q["who"] and q["source"], nid)

    def test_placeholders_resolve(self):
        for gender, prof, city in itertools.product("mf", PROFESSIONS, CITIES):
            s = State(name="Тест", gender=gender, profession=prof, city=city)
            for nid, node in NODES.items():
                texts = [node["text"], node["place"]] + [c[0] for c in node["choices"]]
                if node.get("quote"):
                    texts.append(node["quote"]["text"])
                for t in texts:
                    out = s.format(t)
                    self.assertNotRegex(out, r"\{|\}|\[\[|\]\]", f"{nid}: {out[:80]}")


class TestProfessions(unittest.TestCase):
    def all_text(self, s):
        for node in NODES.values():
            yield node["text"]
            yield node["place"]
            for c in node["choices"]:
                yield c[0]
        for e in ENDINGS.values():
            yield e["note"]

    def test_students_study_rather_than_work(self):
        import re
        for gender in "mf":
            s = State(name="Тест", gender=gender, profession="student", city="Томск")
            for t in self.all_text(s):
                out = s.format(t)
                self.assertNotRegex(out, re.compile(r"уволь|по собственному|работает студент|рабочий чат|"
                                                    r"место работы|работа, кредит", re.I), out[:90])


class TestPlaythrough(unittest.TestCase):
    def play(self, pick):
        """Walk the graph choosing with pick(node_id, n_choices) until FINALE."""
        s = State(name="Аня", gender="f", profession="doctor", city="Томск")
        nid, steps = START_NODE, 0
        while nid != "FINALE":
            choices = NODES[nid]["choices"]
            _label, nxt, fx = choices[pick(nid, len(choices))]
            if fx:
                fx(s)
            nid = nxt(s) if callable(nxt) else nxt
            steps += 1
            self.assertLess(steps, 200)
        return compute_ending(s), s

    def test_bold_path_wins(self):
        ending, _ = self.play(lambda nid, n: 0)
        self.assertIn(ending, ("win", "win_prison", "win_return", "tragic"))

    def test_passive_path_is_quiet(self):
        ending, _ = self.play(lambda nid, n: n - 1)
        self.assertIn(ending, ("quiet", "emigration"))

    def test_many_random_paths_reach_an_ending(self):
        import random
        rnd = random.Random(7)
        seen = set()
        for _ in range(3000):
            ending, s = self.play(lambda nid, n: rnd.randrange(n))
            seen.add(ending)
            lines = epilogue(s)
            self.assertGreaterEqual(len(lines), 3)
            for line in lines + [s.format(ENDINGS[ending]["note"])]:
                self.assertNotRegex(line, r"\{|\}|\[\[|\]\]", line)
        self.assertEqual(seen, set(ENDINGS), f"unreached endings: {set(ENDINGS) - seen}")


class TestState(unittest.TestCase):
    def test_gendered_forms(self):
        m = State(name="Иван", gender="m", profession="teacher", city="Казань")
        f = State(name="Анна", gender="f", profession="teacher", city="Казань")
        t = "{name} [[пошёл|пошла]] в школу. Работает {prof_ins} в {city_pre}, родом из {city_gen}."
        self.assertEqual(m.format(t), "Иван пошёл в школу. Работает учителем в Казани, родом из Казани.")
        self.assertEqual(f.format(t), "Анна пошла в школу. Работает учительницей в Казани, родом из Казани.")

    def test_empty_masculine_suffix(self):
        self.assertEqual(State(gender="m").format("сказал[[|а]]"), "сказал")
        self.assertEqual(State(gender="f").format("сказал[[|а]]"), "сказала")

    def test_save_roundtrip(self):
        s = State(name="Аня", gender="f", profession="doctor", city="Томск")
        s.add("voice", 3)
        s.set("org", "yabloko")
        r = State.from_json(s.to_json())
        self.assertEqual((r.name, r.gender, r.data["voice"], r.data["org"]), ("Аня", "f", 3, "yabloko"))


if __name__ == "__main__":
    unittest.main()
