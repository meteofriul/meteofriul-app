import json
import tempfile
import unittest
from pathlib import Path

from app.services.webcams import WebcamManifestValidationError
from tools import check_webcams


JPEG_SAMPLE = b"\xff\xd8\xff\xe0" + b"image-data"
HTML_SAMPLE = b"<!doctype html><html><body>webcam player</body></html>"


class StubResponse:
    def __init__(self, url):
        self.url = url
        self.status_code = 200
        self.headers = {"Content-Type": "text/html"}

    def iter_content(self, chunk_size):
        yield HTML_SAMPLE

    def close(self):
        return None


class StubSession:
    def get(self, url, **kwargs):
        return StubResponse(url)


def candidate_manifest(*, publish=False, mode="shadow"):
    return {
        "version": 1,
        "mode": mode,
        "publish": publish,
        "candidates": [
            {
                "id": "maniago-centro",
                "name": "Maniago - Centro",
                "group": "plain",
                "municipality": "Maniago",
                "fallbackImageUrl": "/municipalities/photos/maniago.webp",
                "sourcePage": "https://camera.example.test/webcam/maniago",
            }
        ],
    }


class CheckWebcamsToolTests(unittest.TestCase):
    def test_candidate_check_stays_shadow_and_non_publishing(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = root / "candidates.json"
            manifest.write_text(json.dumps(candidate_manifest()), encoding="utf-8")
            photo = root / "public" / "municipalities" / "photos" / "maniago.webp"
            photo.parent.mkdir(parents=True)
            photo.write_bytes(JPEG_SAMPLE)

            report = check_webcams.run_health_check(
                manifest_path=manifest,
                shadow=True,
                asset_root=root / "public",
                session=StubSession(),
            )

        self.assertEqual(report["mode"], "shadow")
        self.assertFalse(report["publish"])
        self.assertEqual(report["status"], "ok")
        self.assertEqual(report["counts"]["total"], 1)

    def test_candidate_check_rejects_publish_true_before_network(self):
        with tempfile.TemporaryDirectory() as directory:
            manifest = Path(directory) / "candidates.json"
            manifest.write_text(
                json.dumps(candidate_manifest(publish=True)),
                encoding="utf-8",
            )

            with self.assertRaises(WebcamManifestValidationError) as error:
                check_webcams.run_health_check(
                    manifest_path=manifest,
                    shadow=True,
                    asset_root=Path(directory),
                    session=StubSession(),
                )

        self.assertIn(
            "shadow_publish_must_be_false",
            {issue.code for issue in error.exception.issues},
        )


if __name__ == "__main__":
    unittest.main()
