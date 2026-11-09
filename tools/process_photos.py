"""Turn fetched Commons thumbnails into in-game photos and credits.json.

Reads assets/photos/candidates.json and assets/photos/raw/<key>.jpg (written by
tools/fetch_photos.py), writes assets/photos/<key>.jpg as a grayscale,
contrast-adjusted copy (max 1920 px wide) and merges attribution into
assets/photos/credits.json. The engine darkens photos itself at runtime.

Keys listed in REJECT are skipped (wrong subject picked by the search);
re-run fetch_photos.py with an override to replace them.

    pip install pillow
    python3 tools/process_photos.py
"""
import json
import os

from PIL import Image, ImageOps

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PHOTOS = os.path.join(ROOT, "assets", "photos")
RAW = os.path.join(PHOTOS, "raw")

NOTE = ("Grayscale, contrast-adjusted and resized derivative; darkened at runtime "
        "for use as a background. Content and identity unaltered.")

REJECT: set[str] = set()


def process(src: str, dst: str, max_w: int = 1920) -> None:
    im = Image.open(src).convert("RGB")
    if im.width > max_w:
        im = im.resize((max_w, round(im.height * max_w / im.width)), Image.LANCZOS)
    g = ImageOps.autocontrast(ImageOps.grayscale(im), cutoff=1)
    Image.merge("RGB", (g, g, g)).save(dst, quality=86, optimize=True)


def main() -> None:
    with open(os.path.join(PHOTOS, "candidates.json"), encoding="utf-8") as f:
        candidates = json.load(f)
    credits_path = os.path.join(PHOTOS, "credits.json")
    credits = {}
    if os.path.exists(credits_path):
        with open(credits_path, encoding="utf-8") as f:
            credits = json.load(f)
    for key, c in candidates.items():
        src = os.path.join(RAW, key + ".jpg")
        if key in REJECT or not os.path.exists(src):
            continue
        process(src, os.path.join(PHOTOS, key + ".jpg"))
        credits[key] = {
            "title": c["title"].removeprefix("File:"),
            "source_url": c["page_url"],
            "license": c["license"],
            "artist": c["artist"],
            "date": c.get("date", ""),
            "note": NOTE,
        }
        print("ok", key, "|", c["license"], "|", c["artist"][:50])
    with open(credits_path, "w", encoding="utf-8") as f:
        json.dump(dict(sorted(credits.items())), f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
