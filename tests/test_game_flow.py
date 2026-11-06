import os
import tempfile
import unittest
from unittest.mock import patch

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

from engine import METRIC_NAMES
from game.app import Game
from game.constants import ALT_WARNING

OPEN_DOOR_PATH = (0,) * 8 + (2, 2, 0, 0)


class GameFlowTests(unittest.TestCase):
    def setUp(self):
        self.home = tempfile.TemporaryDirectory()
        self.environment = patch.dict(os.environ, {"HOME": self.home.name})
        self.environment.start()
        self.game = Game()

    def tearDown(self):
        self.game.audio.stop_voice()
        pygame.quit()
        self.environment.stop()
        self.home.cleanup()

    def play(self, path):
        game = self.game
        game.start_new()
        game.go("event", phase="narration")
        for choice_index in path:
            game.go("event", phase="choice")
            game.choose(choice_index)
            game.next_chapter()
            if game.state["completed"]:
                break

    def test_complete_branching_campaign_save_continue_and_credits(self):
        game = self.game
        self.play(OPEN_DOOR_PATH)
        self.assertTrue(game.state["completed"])
        self.assertEqual(game.state["ending_id"], "open_door")
        self.assertEqual(game.screen, "ending")
        self.assertEqual(len(game.state["history"]), 12)
        self.assertGreater(len(game.state["credits"]), 3)
        game.continue_game()
        self.assertEqual(game.screen, "ending")
        game.go("roll")
        game.update(1)
        self.assertGreater(game.roll_offset, 0)
        game.screen_roll()

    def test_continue_restores_pending_result(self):
        game = self.game
        game.start_new()
        game.go("event", phase="choice")
        game.choose(0)
        game.continue_game()
        self.assertEqual(game.screen, "result")
        self.assertEqual(game.params["choice_index"], 0)
        game.next_chapter()
        self.assertEqual(game.state["event_id"], "e01_legal")

    def test_choices_open_different_paths_and_allow_switching(self):
        game = self.game
        game.start_new()
        for choice, expected in [(0, "e01_legal")]:
            game.go("event", phase="choice")
            game.choose(choice)
            game.next_chapter()
            self.assertEqual(game.state["event_id"], expected)
        for choice, expected in [(1, "e02_grassroots"), (2, "e03_media")]:
            game.go("event", phase="choice")
            game.choose(choice)
            game.next_chapter()
            self.assertEqual(game.state["event_id"], expected)

    def test_pause_settings_and_choice_phase_are_restored(self):
        game = self.game
        game.go("event", phase="choice")
        game.pause()
        game.go("settings", return_to="pause")
        escape = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE, mod=0)
        game.handle_key(escape)
        self.assertEqual(game.screen, "pause")
        game.handle_key(escape)
        self.assertEqual(game.screen, "event")
        self.assertEqual(game.params["phase"], "choice")

    def test_audio_keyboard_toggles_and_manual_save(self):
        game = self.game
        voice = game.audio.voice_enabled
        muted = game.audio.muted
        game.handle_key(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_v, mod=0))
        game.handle_key(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_m, mod=0))
        self.assertEqual(game.audio.voice_enabled, not voice)
        self.assertEqual(game.audio.muted, not muted)
        game.go("event", phase="narration")
        game.handle_key(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_s, mod=pygame.KMOD_CTRL))
        self.assertIn("сохранена", game.notice.lower())

    def test_alternative_warning_and_no_visible_metric_effects(self):
        self.assertIn("СОБЫТИЯ РАЗВИВАЮТСЯ ИНАЧЕ, ЧЕМ В ДЕЙСТВИТЕЛЬНОСТИ", ALT_WARNING)
        game = self.game
        game.state["alternative_history"] = True
        game.go("event", phase="choice")
        game.screen_event()
        labels = " ".join(button.label for button in game.buttons)
        for metric_name in METRIC_NAMES.values():
            self.assertNotIn(metric_name, labels)
        self.assertNotRegex(labels, r"[+-]\d")

    def test_all_main_screens_render(self):
        game = self.game
        for screen in ("menu", "briefing", "timeline", "media", "credits", "people", "settings", "help", "pause"):
            with self.subTest(screen=screen):
                game.go(screen)
                game._draw_frame()
        game.go("event", phase="narration")
        game._draw_frame()
        game.go("event", phase="choice")
        game._draw_frame()
        game.choose(0)
        game._draw_frame()
        game.state["completed"] = True
        game.state["ending_id"] = "open_door"
        for screen in ("ending", "roll"):
            game.go(screen)
            game._draw_frame()


if __name__ == "__main__":
    unittest.main()
