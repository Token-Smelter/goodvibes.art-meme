# /// script
# requires-python = ">=3.11"
# dependencies = ["pillow>=10", "pyyaml>=6"]
# ///
"""Resolve an exact Commons file and cache the image outside the skill package.

Usage: uv run tools/get_image.py <artwork-id> [--refresh]
Prints a local image path and provenance as JSON. No artwork search or cropping.
"""
import argparse
import hashlib
import io
import json
import os
import re
import tempfile
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode, urlsplit
from urllib.request import Request, urlopen

import yaml
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
API = "https://commons.wikimedia.org/w/api.php"
USER_AGENT = "ArtMeme/0.2 (public-domain art skill; Python urllib)"
MAX_DOWNLOAD_BYTES = 50 * 1024 * 1024
THUMB_WIDTH = 1600
FORMATS = {"JPEG": ".jpg", "PNG": ".png"}


class ImageError(ValueError):
    """An actionable image/source/cache error for the CLI and renderer."""


def load_artwork(root, artwork_id):
    if not isinstance(artwork_id, str) or not re.fullmatch(r"[a-z0-9][a-z0-9-]*", artwork_id):
        raise ImageError("invalid artwork id")
    try:
        return yaml.safe_load((root / "corpus" / f"{artwork_id}.yaml").read_text())
    except FileNotFoundError as exc:
        raise ImageError(f"unknown artwork {artwork_id!r}") from exc


def validate_source(source):
    if not isinstance(source, dict) or source.get("provider") != "commons":
        raise ImageError("image downloads currently require source.provider: commons")
    asset = source.get("asset")
    if not isinstance(asset, str) or not asset.startswith("File:") or not asset[5:].strip():
        raise ImageError("source.asset must name an exact Commons File:, not search terms")
    if source.get("rights") not in {"public-domain", "cc0"}:
        raise ImageError("source.rights must declare public-domain or cc0")


def _request(url):
    for attempt in range(3):
        try:
            with urlopen(Request(url, headers={"User-Agent": USER_AGENT}), timeout=45) as response:
                data = response.read(MAX_DOWNLOAD_BYTES + 1)
            if len(data) > MAX_DOWNLOAD_BYTES:
                raise ImageError("source response exceeds the 50 MiB download limit")
            return data
        except HTTPError as exc:
            if exc.code in {429, 503} and attempt < 2:
                retry_after = exc.headers.get("Retry-After", "")
                # Do not retry earlier than an unrecognized or long server delay.
                if retry_after and (not retry_after.isdigit() or int(retry_after) > 30):
                    raise ImageError(f"source rate limited; retry later (Retry-After: {retry_after})") from exc
                time.sleep(int(retry_after) if retry_after else 2 ** (attempt + 1))
                continue
            raise ImageError(f"source unavailable (HTTP {exc.code}); retry later: {url}") from exc
        except (URLError, TimeoutError) as exc:
            raise ImageError(f"cannot reach image source; connect and retry: {exc}") from exc


def _resolve_commons(source):
    url = API + "?" + urlencode({
        "action": "query", "format": "json", "formatversion": 2,
        "titles": source["asset"], "redirects": 1, "prop": "imageinfo",
        "iiprop": "url|size|mime", "iiurlwidth": THUMB_WIDTH,
    })
    try:
        result = json.loads(_request(url))
        pages = result.get("query", {}).get("pages", [])
        page = next((p for p in pages if p.get("imageinfo")), None)
        if not page:
            raise ImageError(f"Commons file unavailable: {source['asset']}; fix its recorded source, not a search substitute")
        info = page["imageinfo"][0]
        download_url = info.get("thumburl") or info["url"]
        parsed = urlsplit(download_url)
        if parsed.scheme != "https" or parsed.hostname != "upload.wikimedia.org":
            raise ImageError("Commons returned an unexpected image host")
        return {
            "asset": page["title"],
            "source_url": "https://commons.wikimedia.org/wiki/" + quote(page["title"].replace(" ", "_"), safe=":"),
            "download_url": download_url,
        }
    except (KeyError, TypeError, json.JSONDecodeError) as exc:
        raise ImageError("invalid image metadata returned by Commons") from exc


def _image_format(data):
    try:
        with Image.open(io.BytesIO(data)) as image:
            fmt = image.format
            image.verify()
    except (OSError, SyntaxError, Image.DecompressionBombError) as exc:
        raise ImageError("download is not a valid image") from exc
    if fmt not in FORMATS:
        raise ImageError("only JPEG and PNG sources are supported")
    return fmt


def _atomic_write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as tmp:
        temp_path = Path(tmp.name)
        try:
            tmp.write(data)
            tmp.close()
            temp_path.replace(path)
        finally:
            temp_path.unlink(missing_ok=True)


def get_image(art, root=ROOT, cache_dir=None, refresh=False):
    """Prefer an optional local authoring image; otherwise use a verified cache."""
    source = art.get("source")
    validate_source(source)
    local = (root / "corpus" / art["image"]).resolve()
    if not local.is_relative_to((root / "corpus").resolve()):
        raise ImageError("local image path must stay inside corpus/")
    if local.is_file() and not refresh:
        data = local.read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        if art.get("image_sha256") and art["image_sha256"] != digest:
            raise ImageError("local authoring image checksum mismatch")
        _image_format(data)
        return {"path": str(local), "sha256": digest, "origin": "local"}

    if cache_dir is None:
        base = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache"))
        cache_dir = Path(os.environ.get("ART_MEME_CACHE_DIR", base / "art-meme"))
    cache_dir = Path(cache_dir).expanduser()
    key = hashlib.sha256(json.dumps({
        "provider": source["provider"], "asset": source["asset"], "width": THUMB_WIDTH,
    }, sort_keys=True).encode()).hexdigest()
    record_path = cache_dir / f"{key}.json"
    if record_path.exists() and not refresh:
        try:
            record = json.loads(record_path.read_text())
            digest = record["sha256"]
            if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
                raise ValueError("bad digest")
            image_path = cache_dir / (digest + FORMATS[record["format"]])
            if hashlib.sha256(image_path.read_bytes()).hexdigest() != digest:
                raise ValueError("checksum mismatch")
            return {**record, "path": str(image_path.resolve()), "origin": "cache"}
        except (OSError, ValueError, KeyError, TypeError) as exc:
            raise ImageError("image cache missing or corrupt; run get_image.py <artwork-id> --refresh") from exc

    resolved = _resolve_commons(source)
    data = _request(resolved["download_url"])
    fmt = _image_format(data)
    digest = hashlib.sha256(data).hexdigest()
    image_path = cache_dir / (digest + FORMATS[fmt])
    record = {**resolved, "sha256": digest, "format": fmt,
              "declared_rights": source["rights"]}
    # Content-addressing keeps a concurrent refresh from invalidating an older record.
    _atomic_write(image_path, data)
    _atomic_write(record_path, (json.dumps(record, indent=2) + "\n").encode())
    return {**record, "path": str(image_path.resolve()), "origin": "download"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("artwork")
    parser.add_argument("--refresh", action="store_true", help="refetch the recorded source, bypassing local/cache copies")
    args = parser.parse_args()
    try:
        print(json.dumps(get_image(load_artwork(ROOT, args.artwork), refresh=args.refresh)))
    except (ImageError, OSError) as exc:
        raise SystemExit(f"get_image.py: {exc}") from exc


if __name__ == "__main__":
    main()
