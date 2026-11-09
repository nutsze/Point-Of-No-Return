"""Slow, polite Wikimedia Commons photo fetcher for Ten Winters.

For each subject: one REST search on Commons, one batched imageinfo call for
license/author metadata, then a 960px thumbnail download. Only freely licensed
files (CC BY, CC BY-SA, CC0, public domain) are kept. Every API call is spaced
out and honours Retry-After, because the Wikimedia APIs rate-limit hard.

Output: assets/photos/raw/<key>.jpg plus assets/photos/candidates.json.
tools/process_photos.py then builds the in-game derivatives and credits.json.

    pip install pillow
    python3 tools/fetch_photos.py
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

UA = "TenWintersGame/0.1 (educational visual-novel project; non-commercial)"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW_DIR = os.path.join(ROOT, "assets", "photos", "raw")
CANDIDATES = os.path.join(ROOT, "assets", "photos", "candidates.json")
API_GAP = 25  # seconds between API calls
OK_LICENSES = ("CC BY", "CC-BY", "CC0", "Public domain", "PD", "CC BY-SA", "CC-BY-SA")

# key -> Commons search query
SUBJECTS = {
    "kremlin": "Moscow Kremlin wall Red Square",
    "kremlin_night": "Moscow Kremlin night",
    "navalny": "Alexey Navalny",
    "navalny_rally": "Navalny rally Moscow",
    "navalnaya": "Yulia Navalnaya",
    "kara_murza": "Vladimir Kara-Murza",
    "yashin": "Ilya Yashin",
    "yavlinsky": "Grigory Yavlinsky",
    "shlosberg": "Lev Shlosberg",
    "nemtsov": "Boris Nemtsov",
    "nemtsov_bridge": "Nemtsov bridge memorial flowers",
    "protest_2021": "Navalny protest Moscow 23 January 2021",
    "antiwar_2022": "anti-war protest Russia 2022",
    "mobilization_2022": "Verkhny Lars border queue September 2022",
    "nadezhdin_queue": "Boris Nadezhdin signatures 2024",
    "navalny_memorial": "Navalny memorial flowers February 2024",
    "navalny_funeral": "Navalny funeral Borisovskoye cemetery",
    "politkovskaya": "Anna Politkovskaya",
    "estemirova": "Natalia Estemirova",
}

# key -> exact Commons file, used instead of the search when the search picks
# the wrong image (a panorama, a group shot, a different subject)
OVERRIDES = {
    "kremlin": "File:Kremlin wall - Red Square.jpg",
    "kara_murza": "File:Vladimir V. Kara-Murza (2017).jpg",
    "navalny_portrait": "File:Alexey Navalny.jpg",
    "nemtsov": "File:Boris Nemtsov 2014.jpg",
    "politkovskaya": "File:Anna Politkovskaja im Gespräch mit Christhard Läpple.jpg",
    "estemirova": "File:Natalia Estemirova.jpg",
}


def get(url: str, as_json: bool = True, tries: int = 6):
    delay = API_GAP
    for attempt in range(tries):
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                data = r.read()
            return json.loads(data) if as_json else data
        except urllib.error.HTTPError as e:
            if e.code != 429:
                raise
            wait = int(e.headers.get("Retry-After") or delay)
            print(f"    429, waiting {wait}s", flush=True)
            time.sleep(wait)
            delay = min(delay * 2, 300)
    raise RuntimeError("gave up after repeated 429s: " + url)


def strip_html(s: str) -> str:
    return re.sub(r"\s+", " ", re.sub("<[^>]+>", "", s or "")).strip()


def search(query: str) -> list[str]:
    url = ("https://commons.wikimedia.org/w/rest.php/v1/search/page?"
           + urllib.parse.urlencode({"q": "filetype:bitmap " + query, "limit": 12}))
    pages = get(url)["pages"]
    return [p["key"] for p in pages if p["key"].startswith("File:")]


def metadata(titles: list[str]) -> list[dict]:
    url = ("https://commons.wikimedia.org/w/api.php?" + urllib.parse.urlencode({
        "action": "query", "titles": "|".join(titles), "prop": "imageinfo",
        "iiprop": "url|extmetadata|size", "iiurlwidth": 960, "format": "json",
    }))
    out = []
    for p in get(url).get("query", {}).get("pages", {}).values():
        info = (p.get("imageinfo") or [None])[0]
        if not info:
            continue
        m = info.get("extmetadata", {})
        out.append({
            "title": p["title"],
            "thumb": info.get("thumburl"),
            "page_url": info.get("descriptionurl"),
            "width": info.get("width"), "height": info.get("height"),
            "license": strip_html(m.get("LicenseShortName", {}).get("value", "")),
            "artist": strip_html(m.get("Artist", {}).get("value", "")),
            "date": strip_html(m.get("DateTimeOriginal", {}).get("value", ""))[:10],
            "description": strip_html(m.get("ImageDescription", {}).get("value", ""))[:200],
        })
    return out


def acceptable(c: dict, min_width: int = 800) -> bool:
    lic = c["license"]
    if not lic or not any(lic.startswith(ok) for ok in OK_LICENSES):
        return False
    if "NC" in lic or "ND" in lic:
        return False
    w, h = c["width"] or 0, c["height"] or 1
    return bool(c["thumb"]) and w >= min_width and w / h <= 2.5  # no panoramas


def main(keys: list[str]) -> None:
    os.makedirs(RAW_DIR, exist_ok=True)
    found = {}
    if os.path.exists(CANDIDATES):
        with open(CANDIDATES, encoding="utf-8") as f:
            found = json.load(f)
    forced = set(keys)
    for key in keys or list(SUBJECTS) + [k for k in OVERRIDES if k not in SUBJECTS]:
        have = key in found and os.path.exists(os.path.join(RAW_DIR, key + ".jpg"))
        override = OVERRIDES.get(key)
        if have and key not in forced and not (override and found[key]["title"] != override):
            print(f"{key}: already have it")
            continue
        try:
            if override:
                print(f"{key}: fetching {override}", flush=True)
                cands = [c for c in metadata([override]) if acceptable(c, min_width=300)]
            else:
                print(f"{key}: searching '{SUBJECTS[key]}'", flush=True)
                titles = search(SUBJECTS[key])
                time.sleep(API_GAP)
                cands = [c for c in metadata(titles[:10]) if acceptable(c)] if titles else []
            time.sleep(API_GAP)
        except Exception as e:  # keep going with the other subjects
            print(f"  failed: {e}", flush=True)
            continue
        if not cands:
            print("  no freely licensed match", flush=True)
            continue
        # prefer landscape images for full-screen backgrounds
        cands.sort(key=lambda c: (c["width"] < c["height"], -c["width"]))
        best = cands[0]
        try:
            data = get(best["thumb"], as_json=False)
        except Exception as e:
            print(f"  download failed: {e}", flush=True)
            continue
        with open(os.path.join(RAW_DIR, key + ".jpg"), "wb") as f:
            f.write(data)
        best["alternatives"] = [c["title"] for c in cands[1:5]]
        found[key] = best
        with open(CANDIDATES, "w", encoding="utf-8") as f:
            json.dump(found, f, ensure_ascii=False, indent=2)
        print(f"  saved {best['title']} | {best['license']} | {best['artist'][:60]}", flush=True)
        time.sleep(5)
    print("done:", len(found), "photos")


if __name__ == "__main__":
    main(sys.argv[1:])
