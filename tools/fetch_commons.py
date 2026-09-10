# /// script
# requires-python = ">=3.11"
# dependencies = ["requests>=2"]
# ///
"""Resolve a Wikimedia Commons search to its best file match and download a
~1600px copy into corpus/images/. Prints provenance JSON for the corpus entry.

Usage: uv run tools/fetch_commons.py "<search terms>" <artwork-id>
"""
import json
import sys
from pathlib import Path

import requests

REPO = Path(__file__).resolve().parent.parent
UA = {"User-Agent": "art-meme-dev/0.1 (personal project; contact: local)"}
API = "https://commons.wikimedia.org/w/api.php"


def main():
    search, art_id = sys.argv[1], sys.argv[2]
    r = requests.get(API, params={
        "action": "query", "format": "json", "generator": "search",
        "gsrsearch": f"filetype:bitmap {search}", "gsrnamespace": 6,
        "gsrlimit": 8, "prop": "imageinfo",
        "iiprop": "url|size|mime", "iiurlwidth": 1600,
    }, headers=UA, timeout=60)
    r.raise_for_status()
    pages = list(r.json().get("query", {}).get("pages", {}).values())
    pages.sort(key=lambda p: p.get("index", 99))
    pick = None
    for p in pages:
        info = (p.get("imageinfo") or [{}])[0]
        if info.get("mime") in ("image/jpeg", "image/png") and \
                info.get("width", 0) >= 1000 and info.get("height", 0) >= 800:
            pick = (p, info)
            break
    if not pick:
        sys.exit(f"fetch_commons: no suitable match for {search!r}")
    page, info = pick
    url = info.get("thumburl") or info["url"]
    img = requests.get(url, headers=UA, timeout=120)
    img.raise_for_status()
    out = REPO / "corpus/images" / f"{art_id}.jpg"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(img.content)
    print(json.dumps({
        "id": art_id, "asset": page["title"],
        "full_size": [info.get("width"), info.get("height")],
        "saved": str(out), "bytes": len(img.content),
        "url": f'https://commons.wikimedia.org/wiki/{page["title"].replace(" ", "_")}',
    }))


if __name__ == "__main__":
    main()
