"""Создаёт монохромные производные проверенных фотографий и SVG-макеты для Figma.

Новые изображения людей не генерируются: используются только локальные оригиналы
с подтверждёнными авторами и лицензиями из assets/credits.json.
"""
from __future__ import annotations

import base64
import html
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageOps

ROOT = Path(__file__).resolve().parents[1]
SIZE = (3840, 2160)
PORTRAITS = {
    "navalny_2020", "yulia_navalnaya_2024", "kara_murza_2005",
    "yashin_2005", "yavlinsky_2018",
}


def cover(image: Image.Image, size: tuple[int, int]) -> Image.Image:
    return ImageOps.fit(image, size, Image.Resampling.LANCZOS, centering=(0.5, 0.46))


def scene(record: dict) -> Image.Image:
    source = Image.open(ROOT / record["original_copy"]).convert("RGB")
    if record["id"] in PORTRAITS:
        # Полный портрет сохраняется поверх расфокусированного фона той же фотографии.
        background = cover(source, SIZE).filter(ImageFilter.GaussianBlur(24))
        foreground = source.copy()
        foreground.thumbnail((2200, 2100), Image.Resampling.LANCZOS)
        canvas = background
        x = round(SIZE[0] * 0.63 - foreground.width / 2)
        y = SIZE[1] - foreground.height
        mask = Image.new("L", foreground.size, 0)
        draw = ImageDraw.Draw(mask)
        feather = 70
        draw.rectangle((feather, feather, foreground.width - feather, foreground.height), fill=255)
        mask = mask.filter(ImageFilter.GaussianBlur(feather))
        canvas.paste(foreground, (x, y), mask)
    else:
        canvas = cover(source, SIZE)
    gray = ImageOps.grayscale(canvas)
    gray = ImageOps.autocontrast(gray, cutoff=1)
    gray = ImageEnhance.Contrast(gray).enhance(1.32)
    gray = ImageEnhance.Brightness(gray).enhance(0.78)
    gray = gray.filter(ImageFilter.UnsharpMask(radius=2, percent=115, threshold=4))
    gray = ImageOps.posterize(gray.convert("RGB"), 7).convert("L")
    image = ImageOps.colorize(gray, black=(4, 6, 8), white=(220, 220, 214)).convert("RGB")

    # Детерминированное зерно и мягкая виньетка не меняют содержание фотографии.
    rng = np.random.default_rng(2030 + sum(record["id"].encode()))
    small_noise = rng.normal(0, 5.0, (270, 480, 1)).astype(np.float32)
    noise = np.asarray(
        Image.fromarray(np.clip(small_noise[:, :, 0] + 128, 0, 255).astype(np.uint8)).resize(SIZE, Image.Resampling.BILINEAR),
        dtype=np.float32,
    )[:, :, None] - 128
    yy, xx = np.mgrid[0:SIZE[1], 0:SIZE[0]]
    dx = (xx - SIZE[0] / 2) / (SIZE[0] / 2)
    dy = (yy - SIZE[1] / 2) / (SIZE[1] / 2)
    vignette = np.clip(1.02 - 0.34 * (dx * dx + dy * dy), 0.52, 1.0)[:, :, None]
    pixels = np.asarray(image, dtype=np.float32) * vignette + noise
    return Image.fromarray(np.clip(pixels, 0, 255).astype(np.uint8), "RGB")


def svg_text(x: int, y: int, text: str, size: int, *, fill: str = "#eeeeea",
             weight: int = 400, anchor: str = "start", spacing: int = 0) -> str:
    return (
        f'<text x="{x}" y="{y}" fill="{fill}" font-family="Noto Sans Display, sans-serif" '
        f'font-size="{size}" font-weight="{weight}" text-anchor="{anchor}" '
        f'letter-spacing="{spacing}">{html.escape(text)}</text>'
    )


def figma_layout(name: str, title: str, body: str, choices: list[str], mode: str,
                 photo_id: str = "yulia_navalnaya_2024") -> str:
    scene_path = ROOT / "assets" / "scenes" / f"{photo_id}.jpg"
    payload = base64.b64encode(scene_path.read_bytes()).decode("ascii")
    parts = [
        '<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="1600" height="900" viewBox="0 0 1600 900">',
        '<defs>',
        '<linearGradient id="bottom" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#050608" stop-opacity="0"/><stop offset="1" stop-color="#050608" stop-opacity="0.97"/></linearGradient>',
        '<linearGradient id="left" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#050608" stop-opacity="0.88"/><stop offset="1" stop-color="#050608" stop-opacity="0"/></linearGradient>',
        '</defs>',
        f'<image width="1600" height="900" xlink:href="data:image/jpeg;base64,{payload}"/>',
        '<rect x="0" y="480" width="1600" height="420" fill="url(#bottom)"/>',
        svg_text(56, 58, "2030 / ТОЧКА НЕВОЗВРАТА", 22, weight=700, spacing=3),
        svg_text(1544, 58, "16 ФЕВРАЛЯ 2024 / ГЛАВА 8 ИЗ 12", 17, fill="#b5b5af", anchor="end", spacing=2),
    ]
    if mode == "menu":
        parts += [
            '<rect width="900" height="900" fill="url(#left)"/>',
            svg_text(72, 250, "2030", 148, weight=700),
            svg_text(76, 334, "ТОЧКА НЕВОЗВРАТА", 58, weight=700, spacing=2),
            svg_text(80, 402, "Документальная политическая визуальная новелла", 24, fill="#b8b8b2"),
        ]
        for index, label in enumerate(["НОВАЯ ИСТОРИЯ", "ПРОДОЛЖИТЬ", "ХРОНОЛОГИЯ", "МЕДИАТЕКА", "НАСТРОЙКИ"]):
            y = 520 + index * 58
            parts += [svg_text(82, y, label, 27, fill="#eeeeea" if index == 0 else "#a9a9a4", weight=600, spacing=2)]
            if index == 0:
                parts.append('<line x1="80" y1="510" x2="360" y2="510" stroke="#eeeeea" stroke-width="2"/>')
    elif mode == "choice":
        parts.append('<rect width="1600" height="900" fill="#050608" opacity="0.38"/>')
        for index, choice in enumerate(choices):
            y = 355 + index * 102
            parts += [
                svg_text(800, y, choice.upper(), 34, weight=600, anchor="middle", spacing=1),
                f'<line x1="510" y1="{y + 25}" x2="1090" y2="{y + 25}" stroke="#deded8" stroke-opacity="{0.8 if index == 0 else 0.25}"/>',
            ]
        parts.append(svg_text(800, 740, "1 / 2 / 3 — ВЫБРАТЬ    ESC — ПАУЗА", 16, fill="#a4a49f", anchor="middle", spacing=2))
    else:
        parts += [
            svg_text(68, 574, title.upper(), 43, weight=700),
            svg_text(70, 614, "АРХИВ / ДОКУМЕНТАЛЬНОЕ СОБЫТИЕ", 15, fill="#a7a7a2", spacing=2),
        ]
        words = body.split()
        lines, current = [], ""
        for word in words:
            if len(current) + len(word) + 1 > 92:
                lines.append(current)
                current = word
            else:
                current = (current + " " + word).strip()
        lines.append(current)
        for index, line in enumerate(lines[:4]):
            parts.append(svg_text(70, 666 + index * 34, line, 23, fill="#d4d4cf"))
        action = "ДАЛЕЕ" if mode == "event" else "СЛЕДУЮЩАЯ ГЛАВА"
        parts += [
            svg_text(1530, 842, action, 22, weight=600, anchor="end", spacing=2),
            svg_text(70, 854, "Фото: Julien Nizet / Belgian Presidency of the Council of the EU / Wikimedia Commons / CC BY 2.0", 12, fill="#8d8d89"),
        ]
    parts.append('</svg>')
    target = ROOT / "design" / "figma" / f"{name}.svg"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("\n".join(parts), encoding="utf-8")


def main() -> None:
    credits_path = ROOT / "assets" / "credits.json"
    payload = json.loads(credits_path.read_text(encoding="utf-8"))
    output = ROOT / "assets" / "scenes"
    output.mkdir(parents=True, exist_ok=True)
    for record in payload["images"]:
        image = scene(record)
        target = output / f"{record['id']}.jpg"
        image.save(target, "JPEG", quality=90, optimize=True, progressive=True)
        record["scene_filename"] = f"assets/scenes/{record['id']}.jpg"
        addition = " Сценическая производная 3840×2160: монохромная обработка, повышение контраста, кадрирование или компоновка того же снимка, зерно и виньетка; содержание и личность не изменялись."
        if addition.strip() not in record["modification_description"]:
            record["modification_description"] += addition
        print(target.relative_to(ROOT))
    credits_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    description = "ФСИН сообщила о смерти Алексея Навального в исправительной колонии № 3 в Харпе. Его соратники возложили ответственность на российские власти."
    choices = ["Создать независимый исторический архив", "Провести съезд коалиции", "Сосредоточиться на региональной взаимопомощи"]
    figma_layout("01-main-menu", "", "", [], "menu", "kremlin_spasskaya")
    figma_layout("02-narration", "Сообщение о смерти Навального", description, [], "event")
    figma_layout("03-choice", "", "", choices, "choice")
    figma_layout("04-result", "Независимый исторический архив", "Документы, свидетельства и публикации сохраняются в распределённом архиве. Эта история больше не исчезнет бесследно.", [], "result")
    print("SVG-макеты для импорта в Figma: design/figma/")


if __name__ == "__main__":
    main()
