import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

from audio import AudioManager
from bootstrap_assets import audio_paths, scene_paths
from engine import resource_root
from ui import Canvas


class NativeCanvasTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.display.set_mode((32, 32))

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def test_text_is_rasterized_at_native_2k_and_4k_sizes(self):
        expected = {(1280, 720): 0.8, (2560, 1440): 1.6, (3840, 2160): 2.4}
        heights = []
        for size, scale in expected.items():
            with self.subTest(size=size):
                surface = pygame.Surface(size)
                canvas = Canvas(surface)
                self.assertAlmostEqual(canvas.scale, scale)
                self.assertEqual(canvas.value(40), round(40 * scale))
                canvas.text("ТОЧКА НЕВОЗВРАТА", (40, 40), 40)
                heights.append(canvas.fonts.get(canvas.value(40)).get_height())
        self.assertLess(heights[0], heights[1])
        self.assertLess(heights[1], heights[2])

    def test_ultrawide_letterboxing_and_mouse_mapping(self):
        canvas = Canvas(pygame.Surface((3440, 1440)))
        self.assertEqual((canvas.offset_x, canvas.offset_y), (440, 0))
        logical = (800, 450)
        self.assertEqual(canvas.logical_pos(canvas.point(logical)), logical)


class LocalAudioTests(unittest.TestCase):
    def setUp(self):
        pygame.mixer.pre_init(48000, -16, 2, 512)
        pygame.init()
        pygame.display.set_mode((32, 32))

    def tearDown(self):
        pygame.quit()

    def test_all_scenes_and_audio_are_local_and_nonempty(self):
        self.assertEqual(len(scene_paths()), 9)
        self.assertEqual(len(audio_paths()), 153)
        for path in scene_paths() + audio_paths():
            with self.subTest(path=path.name):
                self.assertTrue(path.is_file())
                self.assertGreater(path.stat().st_size, 0)
        self.assertTrue(all(path.is_relative_to(resource_root()) for path in scene_paths() + audio_paths()))

    def test_mixer_voice_ducking_and_persistent_settings(self):
        with tempfile.TemporaryDirectory() as home, patch.dict(os.environ, {"HOME": home}):
            audio = AudioManager()
            self.assertTrue(audio.available)
            self.assertIsNotNone(audio.music)
            self.assertEqual(set(audio.sounds), {"choice", "page", "hover"})
            audio.start_music()
            audio.narrate("event_e00.ogg")
            self.assertIsNotNone(audio.current_voice)
            self.assertTrue(audio.voice_channel.get_busy())
            audio.update()
            self.assertAlmostEqual(audio.music_channel.get_volume(), audio.music_volume * 0.32, delta=0.01)
            audio.toggle_voice()
            self.assertFalse(audio.voice_enabled)
            self.assertFalse(audio.voice_channel.get_busy())
            audio.adjust("music", -2)
            audio.adjust("sfx", 2)
            audio.toggle_mute()
            self.assertEqual(audio.music_volume, 0)
            self.assertEqual(audio.sfx_volume, 1)
            restored = AudioManager()
            self.assertFalse(restored.voice_enabled)
            self.assertTrue(restored.muted)
            self.assertEqual(restored.music_volume, 0)
            self.assertEqual(restored.sfx_volume, 1)
            restored.narrate("missing.ogg")


if __name__ == "__main__":
    unittest.main()
