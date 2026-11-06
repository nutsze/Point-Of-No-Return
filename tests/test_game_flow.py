import os
import tempfile
import unittest
from unittest.mock import patch

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.pop("POR_CAPTURE", None)

import pygame

from engine import METRIC_NAMES
from main import ALT_WARNING, Game


class GameFlowTests(unittest.TestCase):
    def setUp(self):
        self.home = tempfile.TemporaryDirectory()
        self.environment = patch.dict(os.environ, {"HOME": self.home.name, "POR_WIDTH": "1280", "POR_HEIGHT": "720"})
        self.environment.start()
        self.game = Game()

    def tearDown(self):
        self.game.audio.stop_voice()
        pygame.quit()
        self.environment.stop()
        self.home.cleanup()

    def test_complete_campaign_save_and_continue(self):
        path = (0, 0, 1, 1, 1, 2, 2, 2, 1, 1, 2, 1)
        game = self.game
        game.start_new()
        self.assertEqual(game.screen, "briefing")
        game.go("event", phase="narration")
        for index, choice_index in enumerate(path):
            self.assertEqual(game.state["event_index"], index)
            self.assertFalse(game.state["completed"])
            game.screen_event()
            game.go("event", phase="choice")
            game.screen_event()
            labels = " ".join(button.label for button in game.buttons)
            for metric_name in METRIC_NAMES.values():
                self.assertNotIn(metric_name, labels)
            self.assertNotRegex(labels, r"[+-]\d")
            pygame_event = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_1 + choice_index, mod=0)
            game.handle_key(pygame_event)
            self.assertEqual(game.screen, "result")
            self.assertEqual(len(game.state["history"]), index + 1)
            game.next_chapter()
        self.assertTrue(game.state["completed"])
        self.assertEqual(game.state["ending_id"], "open_door")
        self.assertEqual(game.screen, "ending")
        game.continue_game()
        self.assertEqual(game.screen, "ending")
        self.assertEqual(len(game.state["history"]), 12)

    def test_pause_settings_and_choice_phase_are_restored(self):
        game = self.game
        game.state["event_index"] = 4
        game.go("event", phase="choice")
        game.pause()
        self.assertEqual(game.screen, "pause")
        game.go("settings", return_to="pause")
        game.handle_escape()
        self.assertEqual(game.screen, "pause")
        game.handle_escape()
        self.assertEqual(game.screen, "event")
        self.assertEqual(game.params["phase"], "choice")
        self.assertEqual(game.state["event_index"], 4)

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
        self.assertIn("сохранена", game.notice)

    def test_alternative_warning_is_explicit(self):
        self.assertIn("СОБЫТИЯ РАЗВИВАЮТСЯ ИНАЧЕ, ЧЕМ В ДЕЙСТВИТЕЛЬНОСТИ", ALT_WARNING)
        self.game.state["alternative_history"] = True
        self.game.go("event", phase="narration")
        self.game.screen_event()


if __name__ == "__main__":
    unittest.main()
