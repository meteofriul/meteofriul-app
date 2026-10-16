import json
import tempfile
import unittest
from pathlib import Path

import requests

from app.services.webcams import (
    DEFAULT_MANIFEST_CACHE_SECONDS,
    WebcamManifestService,
    WebcamManifestValidationError,
    load_shadow_webcam_manifest,
    validate_webcam_manifest,
)


WORKSPACE_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_ROOT = WORKSPACE_ROOT / "contracts" / "runtime-api" / "v1" / "live"


def raw_manifest_from_fixture():
    fixture = json.loads((FIXTURE_ROOT / "webcams-success.json").read_text(encoding="utf-8"))
    return {
        "version": fixture["version"],
        "sourceUpdatedAt": fixture["source_updated_at"],
        "generatedAt": fixture["generated_at"],
        "webcams": fixture["webcams"],
    }


def valid_record(**overrides):
    record = {
        "id": "udine-matteotti",
        "name": "Udine - Piazza Matteotti",
        "group": "plain",
        "municipality": "Udine",
        "imageUrl": "https://camera.example.test/udine.jpg",
        "sourcePage": "https://camera.example.test/webcam/udine",
    }
    record.update(overrides)
    return record


def validation_codes(error):
    return {issue.code for issue in error.exception.issues}


class StubResponse:
    def __init__(self, payload, url="https://example.test/webcams.json"):
        self.payload = payload
        self.url = url

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


class StubSession:
    def __init__(self, result):
        self.result = result
        self.calls = 0

    def get(self, *args, **kwargs):
        self.calls += 1
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


class WebcamManifestServiceTests(unittest.TestCase):
    def write_manifest(self, directory):
        path = Path(directory) / "webcams.json"
        path.write_text(json.dumps(raw_manifest_from_fixture()), encoding="utf-8")
        return path

    def test_local_manifest_matches_shared_contract(self):
        with tempfile.TemporaryDirectory() as directory:
            service = WebcamManifestService(local_path=self.write_manifest(directory))
            actual = service.get_manifest().model_dump(exclude_none=True)
            expected = json.loads(
                (FIXTURE_ROOT / "webcams-success.json").read_text(encoding="utf-8")
            )

        self.assertEqual(actual, expected)

    def test_remote_manifest_is_preferred_and_cached(self):
        session = StubSession(StubResponse(raw_manifest_from_fixture()))
        with tempfile.TemporaryDirectory() as directory:
            service = WebcamManifestService(
                local_path=self.write_manifest(directory),
                manifest_url="https://example.test/webcams.json",
                session=session,
                now=lambda: 1000,
            )
            first = service.get_manifest()
            second = service.get_manifest()

        self.assertEqual(first.source, "remote")
        self.assertEqual(first.source_url, "https://example.test/webcams.json")
        self.assertEqual(second, first)
        self.assertEqual(session.calls, 1)

    def test_remote_source_removal_replaces_manifest_after_ten_minute_cache(self):
        sacile = valid_record(
            id="sacile",
            name="Sacile",
            municipality="Sacile",
            imageUrl="https://camera.example.test/sacile.jpg",
            sourcePage="https://camera.example.test/webcam/sacile",
        )
        remaining = valid_record()
        initial_manifest = {"version": 1, "webcams": [sacile, remaining]}
        updated_manifest = {"version": 2, "webcams": [remaining]}
        session = StubSession(StubResponse(initial_manifest))
        current_time = 1000

        with tempfile.TemporaryDirectory() as directory:
            service = WebcamManifestService(
                local_path=self.write_manifest(directory),
                manifest_url="https://example.test/webcams.json",
                session=session,
                now=lambda: current_time,
            )
            first = service.get_manifest()
            self.assertEqual(first.count, 2)
            self.assertIn("sacile", [record.id for record in first.webcams])

            session.result = StubResponse(updated_manifest)
            self.assertEqual(DEFAULT_MANIFEST_CACHE_SECONDS, 10 * 60)
            current_time += DEFAULT_MANIFEST_CACHE_SECONDS
            self.assertEqual(service.get_manifest(), first)
            self.assertEqual(session.calls, 1)

            current_time += 1
            refreshed = service.get_manifest()
            self.assertEqual(refreshed.source, "remote")
            self.assertEqual(refreshed.status, "ok")
            self.assertEqual(refreshed.version, 2)
            self.assertEqual(refreshed.count, 1)
            self.assertEqual([record.id for record in refreshed.webcams], [remaining["id"]])
            self.assertEqual(session.calls, 2)

            current_time += 1
            self.assertEqual(service.get_manifest(), refreshed)
            self.assertEqual(session.calls, 2)

    def test_remote_failure_uses_ready_local_manifest(self):
        session = StubSession(requests.Timeout("offline"))
        with tempfile.TemporaryDirectory() as directory:
            service = WebcamManifestService(
                local_path=self.write_manifest(directory),
                manifest_url="https://example.test/webcams.json",
                session=session,
            )
            manifest = service.get_manifest()

        self.assertTrue(manifest.ok)
        self.assertEqual(manifest.status, "fallback")
        self.assertEqual(manifest.source, "local")
        self.assertEqual(manifest.count, 2)

    def test_invalid_remote_manifest_falls_back_to_local(self):
        remote = raw_manifest_from_fixture()
        remote["webcams"].append(dict(remote["webcams"][0]))
        session = StubSession(StubResponse(remote))
        with tempfile.TemporaryDirectory() as directory:
            service = WebcamManifestService(
                local_path=self.write_manifest(directory),
                manifest_url="https://example.test/webcams.json",
                session=session,
            )
            manifest = service.get_manifest()

        self.assertTrue(manifest.ok)
        self.assertEqual(manifest.status, "fallback")
        self.assertEqual(manifest.source, "local")

    def test_missing_remote_and_local_manifest_is_explicitly_unavailable(self):
        service = WebcamManifestService(local_path=Path("missing-webcams.json"))
        manifest = service.get_manifest()

        self.assertFalse(manifest.ok)
        self.assertEqual(manifest.status, "unavailable")
        self.assertEqual(manifest.count, 0)

    def test_duplicate_ids_are_rejected_fail_closed(self):
        record = valid_record()
        with self.assertRaises(WebcamManifestValidationError) as error:
            validate_webcam_manifest({"version": 1, "webcams": [record, dict(record)]})

        self.assertIn("duplicate_id", validation_codes(error))

    def test_group_https_coordinates_source_page_and_attribution_are_validated(self):
        record = valid_record(
            group="city",
            imageUrl="http://camera.example.test/udine.jpg",
            sourcePage="https://camera.example.test/",
            attributionUrl="http://camera.example.test/credits",
            lat=91,
            lon="not-a-number",
        )
        with self.assertRaises(WebcamManifestValidationError) as error:
            validate_webcam_manifest({"version": 1, "webcams": [record]})

        codes = validation_codes(error)
        self.assertIn("invalid_group", codes)
        self.assertIn("invalid_https_url", codes)
        self.assertIn("invalid_coordinate", codes)
        self.assertIn("source_page_not_specific", codes)

    def test_external_only_record_accepts_local_fallback_and_aliases(self):
        catalog = validate_webcam_manifest(
            {
                "version": 1,
                "webcams": [
                    {
                        "id": "barcis-lago",
                        "name": "Barcis - Lago",
                        "group": "mountain",
                        "municipality": "Barcis",
                        "fallback_image_url": "/municipalities/photos/barcis.webp",
                        "source_page": "https://camera.example.test/webcam/barcis",
                        "source_check_url": "https://camera.example.test/api/webcams/9",
                        "source_check_expected_id": "9",
                        "latitude": "46.1901",
                        "longitude": 12.5602,
                        "attribution_text": "Foto redazionale Meteo Friûl",
                        "attribution_url": "https://camera.example.test/credits/barcis",
                    }
                ],
            }
        )

        record = catalog.records[0]
        self.assertIsNone(record.imageUrl)
        self.assertEqual(record.fallbackImageUrl, "/municipalities/photos/barcis.webp")
        self.assertEqual(record.sourcePage, "https://camera.example.test/webcam/barcis")
        self.assertEqual(
            record.sourceCheckUrl,
            "https://camera.example.test/api/webcams/9",
        )
        self.assertEqual(record.sourceCheckExpectedId, "9")
        self.assertEqual(record.lat, 46.1901)
        self.assertEqual(record.lon, 12.5602)
        self.assertEqual(record.municipality, "Barcis")

    def test_explicit_map_cluster_accepts_aliases_and_rejects_incomplete_or_invalid_pairs(self):
        catalog = validate_webcam_manifest(
            {
                "version": 1,
                "webcams": [valid_record(
                    map_cluster_id="lignano-sabbiadoro",
                    map_cluster_label="Lignano Sabbiadoro",
                )],
            }
        )
        record = catalog.records[0]
        self.assertEqual(record.mapClusterId, "lignano-sabbiadoro")
        self.assertEqual(record.mapClusterLabel, "Lignano Sabbiadoro")

        for overrides, expected_code in (
            ({"mapClusterId": "lignano-sabbiadoro"}, "incomplete_map_cluster"),
            ({"mapClusterLabel": "Lignano Sabbiadoro"}, "incomplete_map_cluster"),
            (
                {"mapClusterId": "Lignano Sabbiadoro", "mapClusterLabel": "Lignano"},
                "invalid_map_cluster_id",
            ),
        ):
            with self.subTest(overrides=overrides):
                with self.assertRaises(WebcamManifestValidationError) as error:
                    validate_webcam_manifest(
                        {"version": 1, "webcams": [valid_record(**overrides)]}
                    )
                self.assertIn(expected_code, validation_codes(error))

    def test_source_check_requires_an_explicit_expected_identity(self):
        with self.assertRaises(WebcamManifestValidationError) as error:
            validate_webcam_manifest(
                {
                    "version": 1,
                    "webcams": [
                        valid_record(
                            sourceCheckUrl="https://camera.example.test/api/webcams/9"
                        )
                    ],
                }
            )

        self.assertIn("source_check_expected_id_required", validation_codes(error))

    def test_expected_identity_requires_a_source_check_url(self):
        with self.assertRaises(WebcamManifestValidationError) as error:
            validate_webcam_manifest(
                {
                    "version": 1,
                    "webcams": [valid_record(sourceCheckExpectedId="9")],
                }
            )

        self.assertIn("source_check_expected_id_without_url", validation_codes(error))

    def test_root_page_is_allowed_only_for_a_dedicated_panomax_instance(self):
        dedicated = validate_webcam_manifest(
            {
                "version": 1,
                "webcams": [
                    valid_record(
                        id="san-daniele-centro",
                        sourcePage="https://sandanieledelfriuli.panomax.com/",
                    )
                ],
            }
        )
        self.assertEqual(
            dedicated.records[0].sourcePage,
            "https://sandanieledelfriuli.panomax.com/",
        )

        standalone_site = validate_webcam_manifest(
            {
                "version": 1,
                "webcams": [
                    valid_record(sourcePage="https://www.cervignanometeo.org/")
                ],
            }
        )
        self.assertEqual(
            standalone_site.records[0].sourcePage,
            "https://www.cervignanometeo.org/",
        )

        with self.assertRaises(WebcamManifestValidationError) as error:
            validate_webcam_manifest(
                {
                    "version": 1,
                    "webcams": [
                        valid_record(sourcePage="https://www.comune.example.test/")
                    ],
                }
            )
        self.assertIn("source_page_not_specific", validation_codes(error))

        with self.assertRaises(WebcamManifestValidationError) as error:
            validate_webcam_manifest(
                {
                    "version": 1,
                    "webcams": [
                        valid_record(sourcePage="https://camera.example.test/")
                    ],
                }
            )
        self.assertIn("source_page_not_specific", validation_codes(error))

    def test_local_fallback_must_be_root_relative_without_traversal(self):
        for unsafe_path in ("//cdn.example.test/photo.webp", "../photo.webp", "/../photo.webp"):
            with self.subTest(unsafe_path=unsafe_path):
                with self.assertRaises(WebcamManifestValidationError) as error:
                    validate_webcam_manifest(
                        {
                            "version": 1,
                            "webcams": [
                                valid_record(imageUrl=None, fallbackImageUrl=unsafe_path)
                            ],
                        }
                    )
                self.assertTrue(
                    {"invalid_local_asset", "invalid_https_url"}
                    & validation_codes(error)
                )

    def test_reviewed_panomax_iframe_players_are_allowed(self):
        for hostname in (
            "fornidisopra.panomax.com",
            "sandanieledelfriuli.panomax.com",
        ):
            with self.subTest(hostname=hostname):
                catalog = validate_webcam_manifest(
                    {
                        "version": 1,
                        "webcams": [
                            valid_record(
                                imageUrl=None,
                                fallbackImageUrl="/municipalities/photos/test.webp",
                                mediaType="IFRAME",
                                playerUrl=f"https://{hostname}/",
                            )
                        ],
                    }
                )

                self.assertEqual(catalog.records[0].mediaType, "iframe")
                self.assertEqual(
                    catalog.records[0].playerUrl,
                    f"https://{hostname}/",
                )

    def test_reviewed_weathercam_player_is_allowed_only_at_the_exact_url(self):
        player_url = "https://stream-meteoproject.eu/weathercam-player.php?code=18"
        catalog = validate_webcam_manifest(
            {
                "version": 1,
                "webcams": [
                    valid_record(
                        imageUrl=None,
                        fallbackImageUrl="/municipalities/photos/test.webp",
                        mediaType="iframe",
                        playerUrl=player_url,
                    )
                ],
            }
        )

        self.assertEqual(catalog.records[0].mediaType, "iframe")
        self.assertEqual(catalog.records[0].playerUrl, player_url)

        for altered_url in (
            "https://stream-meteoproject.eu/weathercam-player.php?code=19",
            "https://stream-meteoproject.eu/weathercam-player.php?code=18&next=1",
            "https://stream-meteoproject.eu/weathercam-player.php?code=18#player",
        ):
            with self.subTest(altered_url=altered_url):
                with self.assertRaises(WebcamManifestValidationError) as error:
                    validate_webcam_manifest(
                        {
                            "version": 1,
                            "webcams": [
                                valid_record(
                                    imageUrl=None,
                                    fallbackImageUrl="/municipalities/photos/test.webp",
                                    mediaType="iframe",
                                    playerUrl=altered_url,
                                )
                            ],
                        }
                    )
                self.assertIn("player_host_not_approved", validation_codes(error))

    def test_snapshot_and_player_modes_are_mutually_exclusive(self):
        with self.assertRaises(WebcamManifestValidationError) as error:
            validate_webcam_manifest(
                {
                    "version": 1,
                    "webcams": [
                        valid_record(
                            imageUrl=(
                                "https://www.meteoproject.it/ftp/webcam/"
                                "gemonadelfriuli/gemona.jpg"
                            ),
                            mediaType="iframe",
                            playerUrl=(
                                "https://stream-meteoproject.eu/"
                                "weathercam-player.php?code=18"
                            ),
                        )
                    ],
                }
            )

        self.assertIn("media_mode_conflict", validation_codes(error))

    def test_iframe_player_is_fail_closed_for_type_host_and_missing_url(self):
        invalid_records = (
            valid_record(
                mediaType="video",
                playerUrl="https://fornidisopra.panomax.com/",
            ),
            valid_record(
                mediaType="iframe",
                playerUrl="https://video.example.test/player",
            ),
            valid_record(mediaType="iframe"),
        )

        with self.assertRaises(WebcamManifestValidationError) as error:
            validate_webcam_manifest({"version": 1, "webcams": list(invalid_records)})

        codes = validation_codes(error)
        self.assertIn("player_media_type_required", codes)
        self.assertIn("player_host_not_approved", codes)
        self.assertIn("iframe_player_url_required", codes)

    def test_shadow_manifest_requires_explicit_non_publishing_markers(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "candidates.json"
            path.write_text(
                json.dumps({"version": 1, "candidates": [valid_record()]}),
                encoding="utf-8",
            )
            with self.assertRaises(WebcamManifestValidationError) as error:
                load_shadow_webcam_manifest(path)

        codes = validation_codes(error)
        self.assertIn("shadow_mode_required", codes)
        self.assertIn("shadow_publish_must_be_false", codes)

    def test_shadow_manifest_is_loaded_separately_from_active_catalog(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "candidates.json"
            path.write_text(
                json.dumps(
                    {
                        "version": 1,
                        "mode": "shadow",
                        "publish": False,
                        "candidates": [valid_record(id="maniago-centro")],
                    }
                ),
                encoding="utf-8",
            )
            catalog = load_shadow_webcam_manifest(path)

        self.assertEqual(catalog.mode, "shadow")
        self.assertEqual([record.id for record in catalog.records], ["maniago-centro"])

    def test_shadow_manifest_cannot_be_loaded_as_active_even_with_webcams_key(self):
        with self.assertRaises(WebcamManifestValidationError) as error:
            validate_webcam_manifest(
                {
                    "version": 1,
                    "mode": "shadow",
                    "publish": False,
                    "candidates": [],
                    "webcams": [valid_record()],
                }
            )

        self.assertIn("shadow_manifest_not_publishable", validation_codes(error))


if __name__ == "__main__":
    unittest.main()
