import contextlib
import hashlib
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlsplit

import yaml
from PIL import Image

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / "tools"))
import build_skill
import get_image


def jpeg_bytes():
    stream = io.BytesIO()
    Image.new("RGB", (1200, 1600), "#504030").save(stream, "JPEG")
    return stream.getvalue()


class ImageDistributionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.cache = self.root / "cache"
        (self.root / "corpus").mkdir()
        self.art = {
            "id": "sample", "title": "Sample", "artist": "Example", "date": 1800,
            "source": {"provider": "commons", "asset": "File:Exact Artwork.jpg", "rights": "public-domain"},
            "image": "images/sample.jpg", "image_sha256": None,
            "targets": [{"id": "figure", "kind": "figure", "subject_point": [0.5, 0.5],
                         "label_box": [0.05, 0.05, 0.3, 0.1]}],
            "uses": [{"structure": "example", "bindings": {"actor": "figure"}}],
        }
        self.resolved = {
            "asset": "File:Exact Artwork.jpg",
            "source_url": "https://commons.wikimedia.org/wiki/File:Exact_Artwork.jpg",
            "download_url": "https://upload.wikimedia.org/example.jpg",
        }
        self.data = jpeg_bytes()

    def download(self, refresh=False):
        with patch.object(get_image, "_resolve_commons", return_value=self.resolved), \
                patch.object(get_image, "_request", return_value=self.data):
            return get_image.get_image(self.art, self.root, self.cache, refresh=refresh)

    def build(self):
        (self.root / "structures.yaml").write_text(yaml.safe_dump([{"id": "example", "roles": ["actor"]}]))
        (self.root / "corpus/sample.yaml").write_text(yaml.safe_dump(self.art))
        shutil.copytree(PROJECT / "tools", self.root / "tools")
        with patch.object(build_skill, "REPO", self.root), contextlib.redirect_stdout(io.StringIO()):
            build_skill.main()
        return self.root / "skill"

    def test_lookup_uses_exact_recorded_filename_not_search(self):
        response = {"query": {"pages": [{"title": self.resolved["asset"], "imageinfo": [
            {"url": self.resolved["download_url"]}
        ]}]}}
        with patch.object(get_image, "_request", return_value=json.dumps(response).encode()) as request:
            get_image._resolve_commons(self.art["source"])
        query = parse_qs(urlsplit(request.call_args.args[0]).query)
        self.assertEqual((query["titles"], "generator" in query), (["File:Exact Artwork.jpg"], False))

    def test_cached_download_is_reused_offline_without_changing_bytes(self):
        self.download()
        with patch.object(get_image, "_request", side_effect=AssertionError("network not allowed")):
            result = get_image.get_image(self.art, self.root, self.cache)
        self.assertEqual((result["origin"], Path(result["path"]).read_bytes()), ("cache", self.data))

    def test_corrupted_cached_bytes_fail_instead_of_rendering(self):
        result = self.download()
        Path(result["path"]).write_bytes(b"corrupt")
        with self.assertRaisesRegex(get_image.ImageError, "cache missing or corrupt"):
            get_image.get_image(self.art, self.root, self.cache)

    def test_explicit_refresh_repairs_corrupt_cache(self):
        result = self.download()
        Path(result["path"]).write_bytes(b"corrupt")
        self.download(refresh=True)
        self.assertEqual(Path(result["path"]).read_bytes(), self.data)

    def test_missing_source_does_not_substitute_search_result(self):
        with (
            patch.object(get_image, "_request", return_value=b'{"query":{"pages":[{"missing":true}]}}'),
            self.assertRaisesRegex(get_image.ImageError, "file unavailable"),
        ):
            get_image.get_image(self.art, self.root, self.cache)

    def test_non_image_response_is_not_cached(self):
        self.data = b"<html>not an image</html>"
        with self.assertRaisesRegex(get_image.ImageError, "not a valid image"):
            self.download()
        self.assertEqual(list(self.cache.glob("*")), [])

    def test_unapproved_rights_declaration_is_rejected_before_download(self):
        self.art["source"]["rights"] = "fair-use"
        with (
            patch.object(get_image, "_request", side_effect=AssertionError("network not allowed")),
            self.assertRaisesRegex(get_image.ImageError, "public-domain or cc0"),
        ):
            get_image.get_image(self.art, self.root, self.cache)

    def test_optional_local_authoring_copy_works_offline(self):
        local = self.root / "corpus/images/sample.jpg"
        local.parent.mkdir()
        local.write_bytes(self.data)
        with patch.object(get_image, "_request", side_effect=AssertionError("network not allowed")):
            result = get_image.get_image(self.art, self.root, self.cache)
        self.assertEqual(result["path"], str(local))

    def test_authoring_copy_mismatch_is_rejected_when_hash_is_present(self):
        local = self.root / "corpus/images/sample.jpg"
        local.parent.mkdir()
        local.write_bytes(self.data)
        self.art["image_sha256"] = "0" * 64
        with self.assertRaisesRegex(get_image.ImageError, "authoring image checksum mismatch"):
            get_image.get_image(self.art, self.root, self.cache)

    def test_rate_limit_waits_before_retry(self):
        rate_limit = HTTPError("https://commons.wikimedia.org", 429, "slow down", {"Retry-After": "3"}, None)
        with patch.object(get_image, "urlopen", side_effect=[rate_limit, io.BytesIO(b"ok")]), \
                patch.object(get_image.time, "sleep") as sleep:
            result = get_image._request("https://commons.wikimedia.org")
        self.assertEqual((result, sleep.call_args.args), (b"ok", (3,)))

    def test_long_rate_limit_returns_actionable_error_without_early_retry(self):
        rate_limit = HTTPError("https://commons.wikimedia.org", 429, "slow down", {"Retry-After": "120"}, None)
        with (
            patch.object(get_image, "urlopen", side_effect=rate_limit),
            self.assertRaisesRegex(get_image.ImageError, "retry later"),
        ):
            get_image._request("https://commons.wikimedia.org")

    def test_artwork_id_cannot_escape_annotation_directory(self):
        with self.assertRaisesRegex(get_image.ImageError, "invalid artwork id"):
            get_image.load_artwork(self.root, "../outside")

    def test_build_without_images_emits_only_metadata_and_code(self):
        skill = self.build()
        self.assertEqual(sorted(p.relative_to(skill).as_posix() for p in skill.rglob("*") if p.is_file()), [
            "COVERAGE.md", "SKILL.md", "corpus/sample.yaml", "index.yaml",
            "tools/get_image.py", "tools/match.py", "tools/render.py",
        ])

    def test_build_excludes_existing_authoring_images_and_their_hashes(self):
        local = self.root / "corpus/images/sample.jpg"
        local.parent.mkdir()
        local.write_bytes(self.data)
        self.art["image_sha256"] = hashlib.sha256(self.data).hexdigest()
        skill = self.build()
        packaged = yaml.safe_load((skill / "corpus/sample.yaml").read_text())
        self.assertEqual((list(skill.rglob("*.jpg")), packaged.get("image_sha256")), ([], None))

    def test_image_free_package_renders_from_external_cache(self):
        self.download()
        skill = self.build()
        result = subprocess.run(
            [sys.executable, str(skill / "tools/render.py")],
            input=json.dumps({"artwork": "sample", "labels": {"figure": "me"}, "out": str(self.root / "render.jpg")}),
            text=True, capture_output=True, check=False,
            env={**os.environ, "ART_MEME_CACHE_DIR": str(self.cache)},
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        with Image.open(self.root / "render.jpg") as rendered:
            self.assertEqual(rendered.format, "JPEG")


if __name__ == "__main__":
    unittest.main()
