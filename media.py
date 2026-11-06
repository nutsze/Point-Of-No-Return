"""Проверяемая локальная историческая медиатека."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from engine import resource_root

REQUIRED_FIELDS = {
    "id", "filename", "title", "author", "source_url", "license",
    "license_url", "modification_description",
}


class MediaLibrary:
    def __init__(self) -> None:
        self.root = resource_root()
        path = self.root / "assets" / "credits.json"
        with path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
        self.records: list[dict[str, Any]] = payload["images"]
        self.by_id: dict[str, dict[str, Any]] = {}
        self.errors: list[str] = []
        self._validate()
        self._surface_cache: dict[tuple[str, int, int, str], Any] = {}

    def _validate(self) -> None:
        for record in self.records:
            missing = REQUIRED_FIELDS - record.keys()
            if missing:
                raise ValueError(f"В credits.json отсутствуют поля: {sorted(missing)}")
            photo_id = record["id"]
            if photo_id in self.by_id:
                raise ValueError(f"Повторяющийся id фотографии: {photo_id}")
            if not record["author"].strip() or record["author"].lower() in {"unknown", "неизвестно"}:
                raise ValueError(f"Не подтверждён автор: {photo_id}")
            if not record["license"].strip() or record["license"].lower() in {"unknown", "неизвестно"}:
                raise ValueError(f"Не подтверждена лицензия: {photo_id}")
            if not record["source_url"].startswith("https://commons.wikimedia.org/"):
                raise ValueError(f"Источник не относится к Wikimedia Commons: {photo_id}")
            filename = Path(record["filename"])
            if filename.is_absolute() or ".." in filename.parts:
                raise ValueError(f"Небезопасный путь к фотографии: {photo_id}")
            if not (self.root / filename).is_file():
                self.errors.append(f"Файл отсутствует: {record['filename']}")
            self.by_id[photo_id] = record

    def get(self, photo_id: str) -> dict[str, Any] | None:
        return self.by_id.get(photo_id)

    def caption(self, photo_id: str) -> str:
        record = self.get(photo_id)
        if not record:
            return "Документальное изображение отсутствует в проверенной медиатеке"
        return f"Фото: {record['author']} / Wikimedia Commons / {record['license']}"

    def surface(self, photo_id: str, size: tuple[int, int], mode: str = "cover"):
        """Возвращает масштабированную копию; исходный файл никогда не изменяется."""
        import pygame

        width, height = max(1, int(size[0])), max(1, int(size[1]))
        key = (photo_id, width, height, mode)
        if key in self._surface_cache:
            return self._surface_cache[key]
        record = self.get(photo_id)
        target = pygame.Surface((width, height)).convert()
        target.fill((13, 19, 27))
        if not record:
            return target
        path = self.root / record["filename"]
        if not path.is_file():
            return target
        try:
            source = pygame.image.load(str(path)).convert()
        except (pygame.error, OSError):
            return target
        sw, sh = source.get_size()
        if mode == "contain":
            scale = min(width / sw, height / sh)
        else:
            scale = max(width / sw, height / sh)
        scaled_size = (max(1, round(sw * scale)), max(1, round(sh * scale)))
        scaled = pygame.transform.smoothscale(source, scaled_size)
        rect = scaled.get_rect(center=(width // 2, height // 2))
        target.blit(scaled, rect)
        self._surface_cache[key] = target
        if len(self._surface_cache) > 36:
            self._surface_cache.pop(next(iter(self._surface_cache)))
        return target

    def thumbnail(self, photo_id: str, size: tuple[int, int]):
        return self.surface(photo_id, size, "cover")
