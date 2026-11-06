import json
import os
import unittest
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

from engine import load_events, resource_root
from media import MediaLibrary, REQUIRED_FIELDS


class MediaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.display.set_mode((32, 32))
        cls.media = MediaLibrary()

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def test_all_records_and_files(self):
        self.assertEqual(len(self.media.records), 9)
        self.assertFalse(self.media.errors)
        for record in self.media.records:
            self.assertFalse(REQUIRED_FIELDS - record.keys())
            self.assertTrue((resource_root() / record["filename"]).is_file())
            self.assertTrue((resource_root() / record["scene_filename"]).is_file())
            self.assertTrue(record["author"].strip())
            self.assertTrue(record["license"].strip())
            self.assertIn("Wikimedia Commons", self.media.caption(record["id"]))

    def test_event_photos_exist(self):
        for event in load_events():
            self.assertIsNotNone(self.media.get(event["photo"]), event["id"])

    def test_scaling_and_missing_photo_fallback(self):
        surface = self.media.surface("navalny_2020", (320, 200), "cover")
        self.assertEqual(surface.get_size(), (320, 200))
        scene = self.media.scene_surface("navalny_2020", (2560, 1440), "cover")
        self.assertEqual(scene.get_size(), (2560, 1440))
        missing = self.media.surface("not_in_library", (320, 200), "cover")
        self.assertEqual(missing.get_size(), (320, 200))
        self.assertIn("отсутствует", self.media.caption("not_in_library"))


if __name__ == "__main__":
    unittest.main()
