"""Одноразовое восстановление проверенных бинарных ресурсов репозитория.

Игра сама сеть не использует. Этот скрипт нужен только после клонирования
репозитория или перед повторной сборкой, если локальные ресурсы отсутствуют.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import sys
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent
COMMONS = "https://commons.wikimedia.org/wiki/Special:Redirect/file/"
DEJAVU = "https://github.com/dejavu-fonts/dejavu-fonts/releases/download/version_2_37/dejavu-fonts-ttf-2.37.zip"
USER_AGENT = "PointOfNoReturn2030/1.0 (verified local game assets)"

# SHA-256 вычислен по пикселям RGBA уже проверенных оригиналов, а не по имени файла.
PHOTO_HASHES = {
    "navalny_2020": (1633, 1225, "2d8e75e144936fb8c3e47875cefd7a040d587e6d0b2419bb412d65cfbb3ec57a"),
    "yulia_navalnaya_2024": (2093, 2791, "6765be08f5a2b59a2f7531cca6e7e5082a5af89c260c589d439ec8d8cf09b9fa"),
    "kara_murza_2005": (1638, 2121, "75dd10a3025baf0b0c1e2769b9f71cf95cb4bbfa4e2ec4d79aa55d100d7048eb"),
    "yashin_2005": (1280, 960, "aa10ab9334d2ba68d3e42aa4dc0cc7bf5d529645cbaea3e7e22952c42763be5e"),
    "yavlinsky_2018": (1880, 1160, "4537960fddd067990c9610c16d455d6afaf442e3d760d3d97985444cb859bdef"),
    "kremlin_spasskaya": (3984, 2814, "6605bbbf463e7dae4e199dfd4e5fb7c0ffaf7247accf01b3cc87bd0913173f6b"),
    "state_duma_2009": (683, 1024, "5010552499cebeda801d4ab2f68b116bee24476467f41a8bb1310e07ed1ccce8"),
    "protest_spb_2021": (960, 540, "22d0e18cd4b93f057d947e29a25d36fdb73c55ffc4a80e9f72bd80fc4b8b94c8"),
    "protest_nizhny_2021": (1280, 960, "5504adaedb44331c78f93a66dcc4af31870674e4f46547a450b3595eb3b45c06"),
}
FONT_HASHES = {
    "DejaVuSans.ttf": "abdc775b21b1bc470d50c97e790d276f2054b7504e56e5bd3e64f48d68582322",
    "DejaVuSans-Bold.ttf": "0d977336a6d5fba34eab8e3199eb218327161b5143749f802982c2bc34df0c96",
    "DejaVuSansMono.ttf": "0f5db4f1749979d961019838b160bec74abdf7f9eca69553fe1aa856bbff49a4",
    "LICENSE-DejaVu.txt": "63d3ba759d12804c5b31a9d5940d855c1820d1f5999e6b0872eb1c7ff045fbc9",
}


def download(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=120) as response:
        return response.read()


def verify_photo(photo_id: str, image: Image.Image) -> None:
    width, height, expected = PHOTO_HASHES[photo_id]
    rgba = image.convert("RGBA")
    actual = hashlib.sha256(rgba.tobytes()).hexdigest()
    if rgba.size != (width, height) or actual != expected:
        raise ValueError(f"Контрольная сумма фотографии {photo_id} не совпала; файл не использован")


def restore_photos() -> None:
    records = json.loads((ROOT / "assets" / "credits.json").read_text(encoding="utf-8"))["images"]
    for record in records:
        original = ROOT / record["original_copy"]
        working = ROOT / record["filename"]
        original.parent.mkdir(parents=True, exist_ok=True)
        working.parent.mkdir(parents=True, exist_ok=True)
        if original.is_file():
            image = Image.open(original)
        else:
            url = COMMONS + urllib.parse.quote(record["original_filename"].replace(" ", "_"))
            print(f"Wikimedia Commons: {record['original_filename']}")
            image = Image.open(io.BytesIO(download(url)))
        verify_photo(record["id"], image)
        rgba = image.convert("RGBA")
        rgba.save(original, "PNG")
        output = rgba.convert("RGB")
        output.thumbnail((1600, 1200), Image.Resampling.LANCZOS)
        output.save(working, "JPEG", quality=90, optimize=True)


def restore_fonts() -> None:
    folder = ROOT / "assets" / "fonts"
    folder.mkdir(parents=True, exist_ok=True)
    if all((folder / name).is_file() for name in FONT_HASHES):
        return
    print("DejaVu Fonts 2.37")
    payload = download(DEJAVU)
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        for name, expected in FONT_HASHES.items():
            source = "LICENSE" if name == "LICENSE-DejaVu.txt" else f"ttf/{name}"
            data = archive.read(f"dejavu-fonts-ttf-2.37/{source}")
            if hashlib.sha256(data).hexdigest() != expected:
                raise ValueError(f"Контрольная сумма {name} не совпала")
            (folder / name).write_bytes(data)


def create_icon() -> None:
    path = ROOT / "assets" / "app.ico"
    if path.is_file():
        return
    image = Image.new("RGBA", (256, 256), (10, 16, 23, 255))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((8, 8, 247, 247), radius=35, fill=(19, 30, 42, 255), outline=(211, 166, 77, 255), width=5)
    draw.rectangle((29, 42, 35, 211), fill=(211, 166, 77, 255))
    draw.text((54, 52), "30", font=ImageFont.truetype(str(ROOT / "assets" / "fonts" / "DejaVuSans-Bold.ttf"), 100), fill=(239, 202, 127, 255))
    small = ImageFont.truetype(str(ROOT / "assets" / "fonts" / "DejaVuSans-Bold.ttf"), 20)
    draw.text((58, 166), "ТОЧКА", font=small, fill=(235, 232, 223, 255))
    draw.text((58, 192), "НЕВОЗВРАТА", font=small, fill=(155, 166, 176, 255))
    image.save(path, sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])


def required_paths() -> list[Path]:
    records = json.loads((ROOT / "assets" / "credits.json").read_text(encoding="utf-8"))["images"]
    paths = [ROOT / record["filename"] for record in records]
    paths += [ROOT / record["original_copy"] for record in records]
    paths += [ROOT / "assets" / "fonts" / name for name in FONT_HASHES]
    paths.append(ROOT / "assets" / "app.ico")
    return paths


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="только проверить наличие ресурсов")
    args = parser.parse_args()
    if not args.check:
        restore_photos()
        restore_fonts()
        create_icon()
    missing = [str(path.relative_to(ROOT)) for path in required_paths() if not path.is_file()]
    if missing:
        print("Отсутствуют ресурсы:\n" + "\n".join(missing), file=sys.stderr)
        return 1
    print("Все локальные фотографии, оригиналы, шрифты и значок на месте.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
