"""Одноразовое восстановление проверенных бинарных ресурсов репозитория.

Игра сама сеть не использует. Этот скрипт нужен только после клонирования
репозитория или перед повторной сборкой, если локальные ресурсы отсутствуют.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import shutil
import sys
import tarfile
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent
COMMONS = "https://commons.wikimedia.org/wiki/Special:Redirect/file/"
DEJAVU = "https://github.com/dejavu-fonts/dejavu-fonts/releases/download/version_2_37/dejavu-fonts-ttf-2.37.zip"
NOTO_DEB = "https://deb.debian.org/debian/pool/main/f/fonts-noto/fonts-noto-extra_20201225-1_all.deb"
NOTO_DEB_SHA256 = "a44b0c7b9e3c72caf4237ab46846652d6d6eea296abfe675f6f604b6562ffd40"
USER_AGENT = "PointOfNoReturn2030/2.0 (verified local game assets)"

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
NOTO_HASHES = {
    "NotoSansDisplay-Condensed.ttf": "ba9bfa8b3dba7b09c7faa5d94df31299df1c05c5119f66ad642ea1fc861cb562",
    "NotoSansDisplay-CondensedBold.ttf": "1f07421ff2325605e4b2e50fe0735bc74db03595a4bc3acafa2ee89e598510ab",
    "LICENSE-Noto.txt": "075f91382875da1c4b491f1facf2586f55448705133264d98ce15cab6211b125",
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


def deb_member(payload: bytes, member_name: str) -> bytes:
    """Читает элемент data.tar.* из стандартного Debian ar-архива без внешних утилит."""
    if not payload.startswith(b"!<arch>\n"):
        raise ValueError("Некорректный DEB-архив Noto")
    offset = 8
    while offset + 60 <= len(payload):
        header = payload[offset:offset + 60]
        offset += 60
        name = header[:16].decode("ascii").strip().rstrip("/")
        size = int(header[48:58].decode("ascii").strip())
        data = payload[offset:offset + size]
        offset += size + size % 2
        if name == member_name:
            return data
    raise ValueError(f"В DEB-архиве нет {member_name}")


def restore_noto_fonts() -> None:
    """Восстанавливает точные Noto 2.003 из подписанного выпуска Debian 20201225."""
    folder = ROOT / "assets" / "fonts"
    folder.mkdir(parents=True, exist_ok=True)
    if all((folder / name).is_file() for name in NOTO_HASHES):
        for name, expected in NOTO_HASHES.items():
            if hashlib.sha256((folder / name).read_bytes()).hexdigest() != expected:
                raise ValueError(f"Контрольная сумма {name} не совпала")
        return
    print("Noto Sans Display 2.003 / Debian fonts-noto-extra 20201225")
    payload = download(NOTO_DEB)
    if hashlib.sha256(payload).hexdigest() != NOTO_DEB_SHA256:
        raise ValueError("Контрольная сумма пакета Noto не совпала")
    data = deb_member(payload, "data.tar.xz")
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:xz") as archive:
        for name, expected in NOTO_HASHES.items():
            source = "usr/share/doc/fonts-noto-extra/copyright" if name.endswith(".txt") else f"usr/share/fonts/truetype/noto/{name}"
            extracted = archive.extractfile(source)
            if extracted is None:
                raise ValueError(f"В пакете Noto отсутствует {source}")
            content = extracted.read()
            if hashlib.sha256(content).hexdigest() != expected:
                raise ValueError(f"Контрольная сумма {name} не совпала")
            (folder / name).write_bytes(content)


def create_icon() -> None:
    path = ROOT / "assets" / "app.ico"
    image = Image.new("RGBA", (256, 256), (4, 5, 7, 255))
    draw = ImageDraw.Draw(image)
    draw.rectangle((9, 9, 246, 246), outline=(105, 105, 102, 255), width=2)
    draw.line((28, 25, 28, 231), fill=(238, 238, 232, 255), width=4)
    font = ImageFont.truetype(str(ROOT / "assets" / "fonts" / "NotoSansDisplay-CondensedBold.ttf"), 93)
    small = ImageFont.truetype(str(ROOT / "assets" / "fonts" / "NotoSansDisplay-CondensedBold.ttf"), 24)
    draw.text((45, 42), "2030", font=font, fill=(238, 238, 232, 255))
    draw.text((49, 157), "ТОЧКА", font=small, fill=(218, 218, 212, 255))
    draw.text((49, 188), "НЕВОЗВРАТА", font=small, fill=(158, 158, 153, 255))
    image.save(path, sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])


def scene_paths() -> list[Path]:
    records = json.loads((ROOT / "assets" / "credits.json").read_text(encoding="utf-8"))["images"]
    return [ROOT / "assets" / "scenes" / f"{record['id']}.jpg" for record in records]


def audio_paths() -> list[Path]:
    from engine import ENDINGS, load_events

    folder = ROOT / "assets" / "audio"
    paths = [folder / "credits.json"] + [folder / f"{name}.ogg" for name in ("ambient", "choice", "page", "hover")]
    for event in load_events():
        paths.append(folder / "voice" / f"event_{event['id']}.ogg")
        paths += [folder / "voice" / f"result_{event['id']}_{index}.ogg" for index in range(3)]
    paths += [folder / "voice" / f"ending_{ending_id}.ogg" for ending_id in ENDINGS]
    return paths


def restore_generated_assets() -> None:
    if any(not path.is_file() for path in scene_paths()):
        from tools.build_visual_assets import main as build_visuals
        print("Создание монохромных сцен и SVG-макетов…")
        build_visuals()
    if any(not path.is_file() for path in audio_paths()):
        missing_tools = [name for name in ("ffmpeg", "espeak-ng") if not shutil.which(name)]
        if missing_tools:
            raise RuntimeError("Для создания аудио установите: " + ", ".join(missing_tools))
        from tools.build_audio_assets import main as build_audio
        print("Создание локальной музыки, сигналов и русской озвучки…")
        build_audio()


def required_paths() -> list[Path]:
    records = json.loads((ROOT / "assets" / "credits.json").read_text(encoding="utf-8"))["images"]
    paths = [ROOT / record["filename"] for record in records]
    paths += [ROOT / record["original_copy"] for record in records]
    paths += [ROOT / "assets" / "fonts" / name for name in FONT_HASHES]
    paths += [ROOT / "assets" / "fonts" / name for name in NOTO_HASHES]
    paths.append(ROOT / "assets" / "app.ico")
    paths += scene_paths()
    paths += audio_paths()
    return paths


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="только проверить наличие ресурсов")
    args = parser.parse_args()
    if not args.check:
        restore_photos()
        restore_fonts()
        restore_noto_fonts()
        create_icon()
        restore_generated_assets()
    missing = [str(path.relative_to(ROOT)) for path in required_paths() if not path.is_file()]
    if missing:
        print("Отсутствуют ресурсы:\n" + "\n".join(missing), file=sys.stderr)
        return 1
    print("Все фотографии, сцены, шрифты, аудио и значок на месте.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
