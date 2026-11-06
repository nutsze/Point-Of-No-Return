"""Собирает файлы GitHub Release из уже проверенного Windows EXE."""
from __future__ import annotations

import hashlib
import shutil
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "release"
VERSION = "v0.1"
STEM = f"PointOfNoReturn2030-{VERSION}"
EXCLUDED = {".git", "build", "dist", "release", "__pycache__", ".pytest_cache"}


def verify_archive(path: Path) -> None:
    with zipfile.ZipFile(path) as archive:
        if archive.testzip() is not None:
            raise RuntimeError(f"Повреждён архив: {path.name}")


def main() -> None:
    source_exe = ROOT / "dist" / "PointOfNoReturn2030.exe"
    if not source_exe.is_file():
        raise FileNotFoundError("Сначала соберите dist/PointOfNoReturn2030.exe")
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir()
    exe = OUT / f"{STEM}.exe"
    shutil.copy2(source_exe, exe)
    with zipfile.ZipFile(OUT / f"{STEM}-Windows.zip", "w", zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        archive.write(exe, exe.name)
    with zipfile.ZipFile(OUT / f"{STEM}-Source.zip", "w", zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for path in sorted(ROOT.rglob("*")):
            relative = path.relative_to(ROOT)
            if not path.is_file() or any(part in EXCLUDED for part in relative.parts) or path.suffix == ".pyc":
                continue
            archive.write(path, Path("point_of_no_return") / relative)
    with zipfile.ZipFile(OUT / f"{STEM}-Figma.zip", "w", zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        layouts = sorted((ROOT / "design" / "figma").glob("*.svg"))
        if len(layouts) != 4:
            raise RuntimeError("Для релиза необходимы четыре SVG-макета")
        for path in layouts:
            archive.write(path, path.name)
        archive.write(ROOT / "assets" / "credits.json", "assets/credits.json")
    for path in sorted(OUT.iterdir()):
        if path.suffix == ".zip":
            verify_archive(path)
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        print(f"{path.name}\t{path.stat().st_size}\t{digest}")


if __name__ == "__main__":
    main()
