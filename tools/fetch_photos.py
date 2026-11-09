"""Download chosen Commons files, build a monochrome/dimmed derivative for
in-game background use, and write full attribution metadata."""
import json
import os
import urllib.request

from PIL import Image, ImageEnhance, ImageOps, ImageDraw

UA = "PointOfNoReturnGame/0.1 (educational visual-novel project; non-commercial)"
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(REPO_ROOT, "assets", "photos")
os.makedirs(OUT_DIR, exist_ok=True)

# key -> (title, source page url, thumb/original url, license, artist, date)
CHOSEN = {
    "kremlin": dict(
        title="Kremlin wall - Red Square.jpg",
        page_url="https://commons.wikimedia.org/wiki/File:Kremlin_wall_-_Red_Square.jpg",
        url="https://upload.wikimedia.org/wikipedia/commons/e/ec/Kremlin_wall_-_Red_Square.jpg",
        license="CC BY 4.0", artist="A.Savin", date="",
    ),
    "navalny": dict(
        title="Alexey Navalny.jpg",
        page_url="https://commons.wikimedia.org/wiki/File:Alexey_Navalny.jpg",
        url="https://upload.wikimedia.org/wikipedia/commons/b/b1/Alexey_Navalny.jpg",
        license="CC BY-SA 4.0", artist="Evgeny Feldman / Novaya Gazeta", date="2017",
    ),
    "kara_murza": dict(
        title="Vladimir V. Kara-Murza (2017).jpg",
        page_url="https://commons.wikimedia.org/wiki/File:Vladimir_V._Kara-Murza_(2017).jpg",
        url="https://upload.wikimedia.org/wikipedia/commons/a/ac/Vladimir_V._Kara-Murza_%282017%29.jpg",
        license="CC BY-SA 4.0", artist="Michael Jarmoluk / U.S. Institute of Peace", date="2017",
    ),
    "yashin": dict(
        title="Ilya Yashin in 2019 (cropped).png",
        page_url="https://commons.wikimedia.org/wiki/File:Ilya_Yashin_in_2019_(cropped).png",
        url="https://upload.wikimedia.org/wikipedia/commons/3/39/Ilya_Yashin_in_2019_%28cropped%29.png",
        license="CC BY-SA 4.0", artist="Evgeny Feldman", date="2019",
    ),
    "nemtsov": dict(
        title="Boris Nemtsov 2014.jpg",
        page_url="https://commons.wikimedia.org/wiki/File:Boris_Nemtsov_2014.jpg",
        url="https://upload.wikimedia.org/wikipedia/commons/7/75/Boris_Nemtsov_2014.jpg",
        license="CC BY-SA 3.0", artist="Michael Jarmoluk", date="2014",
    ),
    "politkovskaya": dict(
        title="Anna Stepanowna Politkowskaja, Tschetschenien 2003.jpg",
        page_url="https://commons.wikimedia.org/wiki/File:Anna_Stepanowna_Politkowskaja,_Tschetschenien_2003.jpg",
        url="https://upload.wikimedia.org/wikipedia/commons/3/34/Anna_Stepanowna_Politkowskaja%2C_Tschetschenien_2003.jpg",
        license="Public domain", artist="unknown", date="2003",
    ),
    "estemirova": dict(
        title="Natalia Estemirova.jpg",
        page_url="https://commons.wikimedia.org/wiki/File:Natalia_Estemirova.jpg",
        url="https://upload.wikimedia.org/wikipedia/commons/3/30/Natalia_Estemirova.jpg",
        license="CC BY-SA 4.0", artist="unknown / Memorial", date="",
    ),
}


def download(url, dest):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r, open(dest, "wb") as f:
        f.write(r.read())


def process(src_path, dest_path, target_w=1600):
    im = Image.open(src_path).convert("RGB")
    w, h = im.size
    scale = target_w / w
    im = im.resize((target_w, int(h * scale)), Image.LANCZOS)
    # square-ish crop centered, 16:10-ish for background use
    tw, th = target_w, int(target_w * 0.68)
    if im.height > th:
        top = (im.height - th) // 2
        im = im.crop((0, top, tw, top + th))
    gray = ImageOps.grayscale(im)
    gray = ImageOps.autocontrast(gray, cutoff=1)
    rgb = Image.merge("RGB", (gray, gray, gray))
    rgb = ImageEnhance.Contrast(rgb).enhance(1.05)
    rgb = ImageEnhance.Brightness(rgb).enhance(0.8)  # dim, for text overlay legibility
    # vignette (dark ellipse overlay, strongest at the edges, clear in the centre)
    vign = Image.new("L", rgb.size, 0)
    d = ImageDraw.Draw(vign)
    d.ellipse([-rgb.width * 0.15, -rgb.height * 0.25, rgb.width * 1.15, rgb.height * 1.25], fill=110)
    rgb = Image.composite(rgb, Image.new("RGB", rgb.size, (8, 8, 9)), vign)
    rgb.save(dest_path, quality=87)


if __name__ == "__main__":
    import json as _json
    import tempfile

    tmp_dir = tempfile.mkdtemp(prefix="point_of_no_return_photos_")
    credits_path = os.path.join(OUT_DIR, "credits.json")
    credits = {}
    if os.path.exists(credits_path):
        with open(credits_path, encoding="utf-8") as f:
            credits = _json.load(f)  # keep entries already fetched (e.g. from pasted images)
    for key, meta in CHOSEN.items():
        if key in credits and os.path.exists(os.path.join(OUT_DIR, key + ".jpg")):
            print("skipping", key, "(already present)")
            continue
        raw_path = os.path.join(tmp_dir, key + ".jpg")
        out_path = os.path.join(OUT_DIR, key + ".jpg")
        print("downloading", key, "...")
        download(meta["url"], raw_path)
        process(raw_path, out_path)
        credits[key] = {
            "title": meta["title"], "source_url": meta["page_url"],
            "license": meta["license"], "artist": meta["artist"], "date": meta["date"],
            "note": "Monochrome, dimmed, cropped derivative for in-game background use. "
                    "Identity and content unaltered.",
        }
        print("  ->", out_path, os.path.getsize(out_path), "bytes")
    with open(os.path.join(OUT_DIR, "credits.json"), "w", encoding="utf-8") as f:
        json.dump(credits, f, ensure_ascii=False, indent=2)
    print("done")
