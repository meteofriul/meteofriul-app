import tempfile
import unittest
from pathlib import Path

from app.contracts.live import WebcamRecord
from app.services.webcam_health import check_webcam_health


JPEG_SAMPLE = b"\xff\xd8\xff\xe0" + b"image-data"
HTML_SAMPLE = b"<!doctype html><html><body>webcam</body></html>"
SPA_SHELL_SAMPLE = (
    b'<!doctype html><html><head><title>Reti monitoraggio rischi</title></head>'
    b'<body><div id="app"></div><script type="module" src="/assets/app.js"></script>'
    b"</body></html>"
)


class StubResponse:
    def __init__(
        self,
        *,
        url,
        body,
        status_code=200,
        content_type="application/octet-stream",
    ):
        self.url = url
        self.body = body
        self.status_code = status_code
        self.headers = {"Content-Type": content_type}
        self.closed = False

    def iter_content(self, chunk_size):
        for index in range(0, len(self.body), chunk_size):
            yield self.body[index : index + chunk_size]

    def close(self):
        self.closed = True


class StubSession:
    def __init__(self, responses):
        self.responses = responses
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        response = self.responses[url]
        if isinstance(response, Exception):
            raise response
        return response


def webcam(**overrides):
    values = {
        "id": "barcis-lago",
        "name": "Barcis - Lago",
        "group": "mountain",
        "municipality": "Barcis",
        "fallbackImageUrl": "/municipalities/photos/barcis.webp",
        "sourcePage": "https://camera.example.test/webcam/barcis",
    }
    values.update(overrides)
    return WebcamRecord(**values)


class WebcamHealthTests(unittest.TestCase):
    def source_response(self, url="https://camera.example.test/webcam/barcis"):
        return StubResponse(url=url, body=HTML_SAMPLE, content_type="text/html")

    def test_external_only_record_checks_local_photo_and_source_page(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            photo = root / "municipalities" / "photos" / "barcis.webp"
            photo.parent.mkdir(parents=True)
            photo.write_bytes(JPEG_SAMPLE)
            source = self.source_response()
            session = StubSession({source.url: source})

            report = check_webcam_health(
                [webcam()],
                mode="shadow",
                asset_root=root,
                session=session,
            )

        self.assertEqual(report["status"], "ok")
        self.assertFalse(report["publish"])
        self.assertEqual(
            report["verification_scope"],
            "configured_assets_and_source_reachability",
        )
        self.assertEqual(
            report["not_verified"],
            ["stream_freshness", "viewpoint_identity", "embedding_permission"],
        )
        self.assertTrue(report["results"][0]["external_only"])
        self.assertEqual(report["results"][0]["stream_freshness"], "not_verified")
        self.assertEqual(
            [check["target"] for check in report["results"][0]["checks"]],
            ["fallbackImageUrl", "sourcePage"],
        )
        self.assertEqual([call[0] for call in session.calls], [source.url])

    def test_failed_feed_with_working_fallback_is_degraded(self):
        feed_url = "https://camera.example.test/live/barcis.jpg"
        fallback_url = "https://static.example.test/barcis.jpg"
        source_url = "https://camera.example.test/webcam/barcis"
        responses = {
            feed_url: StubResponse(
                url=feed_url,
                body=b"",
                status_code=503,
                content_type="text/html",
            ),
            fallback_url: StubResponse(
                url=fallback_url,
                body=JPEG_SAMPLE,
                content_type="image/jpeg",
            ),
            source_url: self.source_response(source_url),
        }

        report = check_webcam_health(
            [webcam(imageUrl=feed_url, fallbackImageUrl=fallback_url)],
            mode="active",
            asset_root=Path("unused"),
            session=StubSession(responses),
        )

        self.assertEqual(report["status"], "degraded")
        self.assertEqual(report["counts"]["degraded"], 1)

    def test_html_payload_disguised_as_image_is_failed(self):
        feed_url = "https://camera.example.test/live/barcis.jpg"
        source_url = "https://camera.example.test/webcam/barcis"
        report = check_webcam_health(
            [webcam(imageUrl=feed_url, fallbackImageUrl=None)],
            mode="active",
            asset_root=Path("unused"),
            session=StubSession(
                {
                    feed_url: StubResponse(
                        url=feed_url,
                        body=HTML_SAMPLE,
                        content_type="image/jpeg",
                    ),
                    source_url: self.source_response(source_url),
                }
            ),
        )

        self.assertEqual(report["status"], "failed")
        self.assertEqual(report["results"][0]["checks"][0]["status"], "not_an_image")

    def test_source_check_url_is_checked_together_with_source_page(self):
        feed_url = "https://camera.example.test/live/barcis.jpg"
        source_url = "https://camera.example.test/webcam/barcis"
        source_check_url = "https://camera.example.test/api/webcams/9"
        session = StubSession(
            {
                feed_url: StubResponse(
                    url=feed_url,
                    body=JPEG_SAMPLE,
                    content_type="image/jpeg",
                ),
                source_url: self.source_response(source_url),
                source_check_url: StubResponse(
                    url=source_check_url,
                    body=b'{"result":"OK","webcam":{"id":9,"name":"Monfalcone"}}',
                    content_type="application/json",
                ),
            }
        )
        report = check_webcam_health(
            [
                webcam(
                    imageUrl=feed_url,
                    fallbackImageUrl=None,
                    sourceCheckUrl=source_check_url,
                    sourceCheckExpectedId="9",
                )
            ],
            mode="active",
            asset_root=Path("unused"),
            session=session,
        )

        self.assertEqual(report["status"], "ok")
        self.assertEqual(
            [call[0] for call in session.calls],
            [feed_url, source_url, source_check_url],
        )

    def test_direct_image_source_page_is_a_valid_external_resource(self):
        fallback_url = "https://static.example.test/barcis.jpg"
        source_url = "https://camera.example.test/images/9/last"
        report = check_webcam_health(
            [webcam(fallbackImageUrl=fallback_url, sourcePage=source_url)],
            mode="active",
            asset_root=Path("unused"),
            session=StubSession(
                {
                    fallback_url: StubResponse(
                        url=fallback_url,
                        body=JPEG_SAMPLE,
                        content_type="image/jpeg",
                    ),
                    source_url: StubResponse(
                        url=source_url,
                        body=JPEG_SAMPLE,
                        content_type="image/jpeg",
                    )
                }
            ),
        )

        source_check = report["results"][0]["checks"][-1]
        self.assertEqual(report["status"], "ok")
        self.assertTrue(source_check["ok"])
        self.assertEqual(source_check["target"], "sourcePage")

    def test_source_page_redirect_to_generic_home_is_degraded(self):
        feed_url = "https://camera.example.test/live/barcis.jpg"
        source_url = "https://camera.example.test/webcam/barcis"
        report = check_webcam_health(
            [webcam(imageUrl=feed_url, fallbackImageUrl=None)],
            mode="active",
            asset_root=Path("unused"),
            session=StubSession(
                {
                    feed_url: StubResponse(
                        url=feed_url,
                        body=JPEG_SAMPLE,
                        content_type="image/jpeg",
                    ),
                    source_url: StubResponse(
                        url="https://camera.example.test/",
                        body=HTML_SAMPLE,
                        content_type="text/html",
                    ),
                }
            ),
        )

        source_check = report["results"][0]["checks"][-1]
        self.assertEqual(report["status"], "degraded")
        self.assertEqual(source_check["status"], "source_redirected_to_generic")

    def test_source_page_without_camera_signal_is_degraded(self):
        feed_url = "https://camera.example.test/live/barcis.jpg"
        source_url = "https://camera.example.test/webcam/barcis"
        report = check_webcam_health(
            [webcam(imageUrl=feed_url, fallbackImageUrl=None)],
            mode="active",
            asset_root=Path("unused"),
            session=StubSession(
                {
                    feed_url: StubResponse(
                        url=feed_url,
                        body=JPEG_SAMPLE,
                        content_type="image/jpeg",
                    ),
                    source_url: StubResponse(
                        url=source_url,
                        body=b"<!doctype html><html><body>meteo e vento</body></html>",
                        content_type="text/html",
                    ),
                }
            ),
        )

        source_check = report["results"][0]["checks"][-1]
        self.assertEqual(report["status"], "degraded")
        self.assertEqual(source_check["status"], "source_signal_missing")

    def test_valid_source_check_json_is_healthy(self):
        feed_url = "https://camera.example.test/live/barcis.jpg"
        source_url = "https://camera.example.test/webcam/barcis"
        source_check_url = "https://camera.example.test/api/webcams/9"
        report = check_webcam_health(
            [
                webcam(
                    imageUrl=feed_url,
                    fallbackImageUrl=None,
                    sourceCheckUrl=source_check_url,
                    sourceCheckExpectedId="9",
                )
            ],
            mode="active",
            asset_root=Path("unused"),
            session=StubSession(
                {
                    feed_url: StubResponse(
                        url=feed_url,
                        body=JPEG_SAMPLE,
                        content_type="image/jpeg",
                    ),
                    source_url: self.source_response(source_url),
                    source_check_url: StubResponse(
                        url=source_check_url,
                        body=b'{"result":"OK","webcam":{"id":9,"name":"Monfalcone"}}',
                        content_type="application/json; charset=utf-8",
                    ),
                }
            ),
        )

        source_check = report["results"][0]["checks"][-1]
        self.assertEqual(report["status"], "ok")
        self.assertTrue(source_check["ok"])
        self.assertEqual(source_check["target"], "sourceCheckUrl")
        self.assertEqual(source_check["status"], "ok")
        # Matching metadata does not establish that any current frame exists.
        self.assertEqual(report["results"][0]["stream_freshness"], "not_verified")

    def test_generic_or_failed_source_check_json_is_degraded(self):
        feed_url = "https://camera.example.test/live/barcis.jpg"
        source_url = "https://camera.example.test/webcam/barcis"
        source_check_url = "https://camera.example.test/api/webcams/9"
        cases = (
            (b'{"result":"OK","forecast":{}}', "source_api_invalid_webcam"),
            (
                b'{"result":"OK","webcam":{"id":[],"name":"Monfalcone"}}',
                "source_api_invalid_webcam",
            ),
            (
                b'{"result":"OK","webcam":{"id":9,"name":"  "}}',
                "source_api_invalid_webcam",
            ),
            (
                b'{"result":"ERROR","webcam":{"id":9,"name":"Monfalcone"}}',
                "source_api_result_not_ok",
            ),
        )
        for payload, expected_status in cases:
            with self.subTest(expected_status=expected_status):
                report = check_webcam_health(
                    [
                        webcam(
                            imageUrl=feed_url,
                            fallbackImageUrl=None,
                            sourceCheckUrl=source_check_url,
                            sourceCheckExpectedId="9",
                        )
                    ],
                    mode="shadow",
                    asset_root=Path("unused"),
                    session=StubSession(
                        {
                            feed_url: StubResponse(
                                url=feed_url,
                                body=JPEG_SAMPLE,
                                content_type="image/jpeg",
                            ),
                            source_url: self.source_response(source_url),
                            source_check_url: StubResponse(
                                url=source_check_url,
                                body=payload,
                                content_type="application/json",
                            ),
                        }
                    ),
                )

                source_check = report["results"][0]["checks"][-1]
                self.assertEqual(report["status"], "degraded")
                self.assertFalse(source_check["ok"])
                self.assertEqual(source_check["status"], expected_status)

    def test_working_api_does_not_hide_a_broken_source_page(self):
        feed_url = "https://camera.example.test/live/barcis.jpg"
        source_url = "https://camera.example.test/webcam/barcis"
        source_check_url = "https://camera.example.test/api/webcams/9"
        report = check_webcam_health(
            [
                webcam(
                    imageUrl=feed_url,
                    fallbackImageUrl=None,
                    sourceCheckUrl=source_check_url,
                    sourceCheckExpectedId="9",
                )
            ],
            mode="active",
            asset_root=Path("unused"),
            session=StubSession(
                {
                    feed_url: StubResponse(
                        url=feed_url,
                        body=JPEG_SAMPLE,
                        content_type="image/jpeg",
                    ),
                    source_url: StubResponse(
                        url=source_url,
                        body=b"missing",
                        status_code=404,
                        content_type="text/html",
                    ),
                    source_check_url: StubResponse(
                        url=source_check_url,
                        body=b'{"result":"OK","webcam":{"id":"9","name":"Monfalcone"}}',
                        content_type="application/json",
                    ),
                }
            ),
        )

        checks = report["results"][0]["checks"]
        self.assertEqual(report["status"], "degraded")
        self.assertFalse(checks[-2]["ok"])
        self.assertTrue(checks[-1]["ok"])

    def test_matching_api_identity_verifies_the_related_spa_source_page(self):
        fallback_url = "https://static.example.test/monfalcone.jpg"
        source_url = "https://camera.example.test/immagini/9/last"
        source_check_url = "https://camera.example.test/api/webcams/9"
        report = check_webcam_health(
            [
                webcam(
                    fallbackImageUrl=fallback_url,
                    sourcePage=source_url,
                    sourceCheckUrl=source_check_url,
                    sourceCheckExpectedId="9",
                )
            ],
            mode="active",
            asset_root=Path("unused"),
            session=StubSession(
                {
                    fallback_url: StubResponse(
                        url=fallback_url,
                        body=JPEG_SAMPLE,
                        content_type="image/jpeg",
                    ),
                    source_url: StubResponse(
                        url=source_url,
                        body=SPA_SHELL_SAMPLE,
                        content_type="text/html",
                    ),
                    source_check_url: StubResponse(
                        url=source_check_url,
                        body=b'{"result":"OK","webcam":{"id":9,"name":"Monfalcone"}}',
                        content_type="application/json",
                    ),
                }
            ),
        )

        source_page_check, source_api_check = report["results"][0]["checks"][-2:]
        self.assertEqual(report["status"], "ok")
        self.assertTrue(source_page_check["ok"])
        self.assertEqual(source_page_check["verification"], "source_api_identity")
        self.assertTrue(source_api_check["ok"])

    def test_spa_source_page_with_a_different_path_id_stays_degraded(self):
        fallback_url = "https://static.example.test/monfalcone.jpg"
        source_url = "https://camera.example.test/immagini/55/last"
        source_check_url = "https://camera.example.test/api/webcams/9"
        report = check_webcam_health(
            [
                webcam(
                    fallbackImageUrl=fallback_url,
                    sourcePage=source_url,
                    sourceCheckUrl=source_check_url,
                    sourceCheckExpectedId="9",
                )
            ],
            mode="active",
            asset_root=Path("unused"),
            session=StubSession(
                {
                    fallback_url: StubResponse(
                        url=fallback_url,
                        body=JPEG_SAMPLE,
                        content_type="image/jpeg",
                    ),
                    source_url: StubResponse(
                        url=source_url,
                        body=SPA_SHELL_SAMPLE,
                        content_type="text/html",
                    ),
                    source_check_url: StubResponse(
                        url=source_check_url,
                        body=b'{"result":"OK","webcam":{"id":9,"name":"Monfalcone"}}',
                        content_type="application/json",
                    ),
                }
            ),
        )

        source_page_check, source_api_check = report["results"][0]["checks"][-2:]
        self.assertEqual(report["status"], "degraded")
        self.assertFalse(source_page_check["ok"])
        self.assertEqual(source_page_check["status"], "source_signal_missing")
        self.assertTrue(source_api_check["ok"])

    def test_source_api_identity_mismatch_is_degraded(self):
        feed_url = "https://camera.example.test/live/barcis.jpg"
        source_url = "https://camera.example.test/webcam/barcis"
        source_check_url = "https://camera.example.test/api/webcams/9"
        report = check_webcam_health(
            [
                webcam(
                    imageUrl=feed_url,
                    fallbackImageUrl=None,
                    sourceCheckUrl=source_check_url,
                    sourceCheckExpectedId="9",
                )
            ],
            mode="active",
            asset_root=Path("unused"),
            session=StubSession(
                {
                    feed_url: StubResponse(
                        url=feed_url,
                        body=JPEG_SAMPLE,
                        content_type="image/jpeg",
                    ),
                    source_url: self.source_response(source_url),
                    source_check_url: StubResponse(
                        url=source_check_url,
                        body=b'{"result":"OK","webcam":{"id":55,"name":"Sacile"}}',
                        content_type="application/json",
                    ),
                }
            ),
        )

        source_check = report["results"][0]["checks"][-1]
        self.assertEqual(report["status"], "degraded")
        self.assertFalse(source_check["ok"])
        self.assertEqual(source_check["status"], "source_api_identity_mismatch")


if __name__ == "__main__":
    unittest.main()
