from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest

from experiments.weather_autonomy.local_pipeline import national_forecast_points as points


BOUNDARY_SHA256 = "b" * 64
SOURCE_MANIFEST_SHA256 = "c" * 64
POLICY_SHA256 = "d" * 64


def _catalog() -> dict:
    municipalities = [
        {
            "istat_code": "001001",
            "representative_point": {
                "latitude": 45.0703,
                "longitude": 7.6869,
                "method": "istat_boundary_interior_point_v1",
            },
        },
        {
            "istat_code": "006002",
            "representative_point": {
                "latitude": 44.9123,
                "longitude": 8.6154,
                "method": "istat_boundary_interior_point_v1",
            },
        },
        {
            "istat_code": "012003",
            "representative_point": {
                "latitude": 45.8156,
                "longitude": 8.8251,
                "method": "istat_boundary_interior_point_v1",
            },
        },
        {
            "istat_code": "093033",
            "representative_point": {
                "latitude": 45.9567,
                "longitude": 12.6605,
                "method": "istat_boundary_interior_point_v1",
            },
        },
    ]
    document = {
        "catalog_version": "fixture-v1",
        "effective_at": "2026-09-20",
        "municipality_count": len(municipalities),
        "municipality_codes_sha256": points.sha256_hex(
            points.canonical_json_bytes(
                sorted(item["istat_code"] for item in municipalities)
            )
        ),
        "municipalities": municipalities,
        "sources": {
            "boundaries": {
                "dataset": "ISTAT generalized municipality boundaries",
                "reference_date": "2026-01-01",
                "sha256": BOUNDARY_SHA256,
                "url": "https://www.istat.it/example-boundaries.zip",
            }
        },
    }
    document["catalog_sha256"] = points.sha256_hex(
        points.canonical_json_bytes(document)
    )
    return document


def _source(code: str, quality: str) -> dict:
    common = {
        "current_istat_code": code,
        "reference_date": "2026-09-20",
        "source_crs": "EPSG:4326",
    }
    if quality == points.QUALITY_OFFICIAL_ISTAT_CAPOLUOGO:
        return {
            **common,
            "authority": "Istituto nazionale di statistica (Istat)",
            "dataset": "Località italiane ISTAT",
            "dataset_sha256": "a" * 64,
            "loc_id": "1000001",
            "mapping_method": "direct_current_istat_code_v1",
            "reference_date": "2021-12-31",
            "source_crs": "EPSG:32632",
            "source_istat_code": code,
            "url": "https://www.istat.it/example-localities.zip",
        }
    if quality == points.QUALITY_OFFICIAL_DBGT:
        return {
            **common,
            "authority": "Regione Friuli Venezia Giulia",
            "dataset": "Database geografico regionale",
            "dataset_sha256": "a" * 64,
            "feature_id": "COMUNE_SED-1",
            "layer_name": "COMUNE_SED",
            "mapping_method": "current_istat_code_exact_v1",
            "url": "https://www.regione.fvg.it/example-dbgt.zip",
        }
    if quality == points.QUALITY_EXACT_ACCESS:
        return {
            **common,
            "address_match_method": "indicepa_anncsu_exact_v1",
            "archive_sha256": "a" * 64,
            "authority": "Agenzia delle Entrate e Istat",
            "cadastral_code": "A001",
            "coordinate_method": "1",
            "dataset": "ANNCSU indirizzario regionale",
            "progressivo_accesso": "2000001",
            "progressivo_nazionale": "3000001",
            "reconciliation_audit_sha256": "e" * 64,
            "url": "https://www.anncsu.gov.it/example-addresses.zip",
        }
    if quality == points.QUALITY_SEAT_AREA_PROXY:
        return {
            **common,
            "authority": "Reviewed institutional-source resolver",
            "component_count": 3,
            "dataset": "Reviewed municipal seat-area derivation",
            "derivation_sha256": "a" * 64,
            "input_records_sha256": "e" * 64,
            "mapping_method": "reviewed_seat_area_proxy_v1",
            "max_radius_m": 125.0,
            "review_decision_sha256": "f" * 64,
            "url": "https://www.istat.it/example-boundaries.zip",
        }
    raise AssertionError(f"unsupported fixture quality: {quality}")


def _approved_points() -> list[dict]:
    qualities = (
        points.QUALITY_OFFICIAL_ISTAT_CAPOLUOGO,
        points.QUALITY_OFFICIAL_DBGT,
        points.QUALITY_EXACT_ACCESS,
        points.QUALITY_SEAT_AREA_PROXY,
    )
    coordinates = (
        (45.0703, 7.6869),
        (44.9123, 8.6154),
        (45.8156, 8.8251),
        (45.9567, 12.6605),
    )
    result = []
    for code, quality, coordinate in zip(
        ("001001", "006002", "012003", "093033"),
        qualities,
        coordinates,
        strict=True,
    ):
        result.append(
            {
                "istat_code": code,
                "latitude": coordinate[0],
                "longitude": coordinate[1],
                "method": points.METHOD_BY_QUALITY[quality],
                "quality": quality,
                "source": _source(code, quality),
            }
        )
    return result


def _approved_artifact() -> dict:
    return points.build_approved_forecast_points_artifact(
        catalog=_catalog(),
        points=reversed(_approved_points()),
        boundary_sha256=BOUNDARY_SHA256,
        source_manifest_sha256=SOURCE_MANIFEST_SHA256,
        resolution_policy_sha256=POLICY_SHA256,
    )


class ApprovedArtifactTests(unittest.TestCase):
    def test_mixed_approved_qualities_build_sorted_self_verifying_artifact(self):
        catalog = _catalog()
        artifact = points.build_approved_forecast_points_artifact(
            catalog=catalog,
            points=reversed(_approved_points()),
            boundary_sha256=BOUNDARY_SHA256,
            source_manifest_sha256=SOURCE_MANIFEST_SHA256,
            resolution_policy_sha256=POLICY_SHA256,
        )

        self.assertEqual(artifact["schema_version"], 2)
        self.assertEqual(artifact["status"], points.APPROVED_POINTS_STATUS)
        self.assertEqual(
            [item["istat_code"] for item in artifact["points"]],
            ["001001", "006002", "012003", "093033"],
        )
        self.assertEqual(
            artifact["quality_counts"],
            {
                points.QUALITY_EXACT_ACCESS: 1,
                points.QUALITY_EXPERIMENTAL_BOUNDARY_PROXY: 0,
                points.QUALITY_OFFICIAL_DBGT: 1,
                points.QUALITY_OFFICIAL_ISTAT_CAPOLUOGO: 1,
                points.QUALITY_SEAT_AREA_PROXY: 1,
            },
        )
        body = dict(artifact)
        digest = body.pop("artifact_sha256")
        self.assertEqual(digest, points.sha256_hex(points.canonical_json_bytes(body)))
        points.validate_forecast_points_artifact(artifact, catalog=catalog)

    def test_approved_artifact_rejects_experimental_quality(self):
        raw = _approved_points()
        raw[0] = points.build_experimental_proxy_artifact(_catalog())["points"][0]
        with self.assertRaisesRegex(
            points.NationalForecastPointsError, "experimental point quality"
        ):
            points.build_approved_forecast_points_artifact(
                catalog=_catalog(),
                points=raw,
                boundary_sha256=BOUNDARY_SHA256,
                source_manifest_sha256=SOURCE_MANIFEST_SHA256,
                resolution_policy_sha256=POLICY_SHA256,
            )

    def test_method_is_strictly_tied_to_quality(self):
        raw = _approved_points()
        raw[0]["method"] = points.METHOD_BY_QUALITY[points.QUALITY_OFFICIAL_DBGT]
        with self.assertRaisesRegex(
            points.NationalForecastPointsError, "method does not match quality"
        ):
            points.build_approved_forecast_points_artifact(
                catalog=_catalog(),
                points=raw,
                boundary_sha256=BOUNDARY_SHA256,
                source_manifest_sha256=SOURCE_MANIFEST_SHA256,
                resolution_policy_sha256=POLICY_SHA256,
            )

    def test_source_schema_and_coordinate_precision_fail_closed(self):
        extra_source = _approved_points()
        extra_source[0]["source"]["unexpected"] = "value"
        with self.assertRaisesRegex(
            points.NationalForecastPointsError, "missing or extra fields"
        ):
            points.build_approved_forecast_points_artifact(
                catalog=_catalog(),
                points=extra_source,
                boundary_sha256=BOUNDARY_SHA256,
                source_manifest_sha256=SOURCE_MANIFEST_SHA256,
                resolution_policy_sha256=POLICY_SHA256,
            )

        excessive_precision = _approved_points()
        excessive_precision[0]["latitude"] = 45.07030001
        with self.assertRaisesRegex(
            points.NationalForecastPointsError, "bounds or precision"
        ):
            points.build_approved_forecast_points_artifact(
                catalog=_catalog(),
                points=excessive_precision,
                boundary_sha256=BOUNDARY_SHA256,
                source_manifest_sha256=SOURCE_MANIFEST_SHA256,
                resolution_policy_sha256=POLICY_SHA256,
            )

    def test_quality_requires_its_discriminated_source_evidence(self):
        wrong_quality_source = _approved_points()
        wrong_quality_source[0]["source"] = _source(
            "001001", points.QUALITY_EXACT_ACCESS
        )
        with self.assertRaisesRegex(
            points.NationalForecastPointsError, "official ISTAT source"
        ):
            points.build_approved_forecast_points_artifact(
                catalog=_catalog(),
                points=wrong_quality_source,
                boundary_sha256=BOUNDARY_SHA256,
                source_manifest_sha256=SOURCE_MANIFEST_SHA256,
                resolution_policy_sha256=POLICY_SHA256,
            )

        incomplete_exact_access = _approved_points()
        del incomplete_exact_access[2]["source"]["progressivo_accesso"]
        with self.assertRaisesRegex(
            points.NationalForecastPointsError, "exact-access source"
        ):
            points.build_approved_forecast_points_artifact(
                catalog=_catalog(),
                points=incomplete_exact_access,
                boundary_sha256=BOUNDARY_SHA256,
                source_manifest_sha256=SOURCE_MANIFEST_SHA256,
                resolution_policy_sha256=POLICY_SHA256,
            )

    def test_official_istat_source_requires_istat_identity_and_host(self):
        arbitrary = _approved_points()
        arbitrary[0]["source"]["url"] = "https://example.test/localities.csv"
        with self.assertRaisesRegex(
            points.NationalForecastPointsError, "institutional source"
        ):
            points.build_approved_forecast_points_artifact(
                catalog=_catalog(),
                points=arbitrary,
                boundary_sha256=BOUNDARY_SHA256,
                source_manifest_sha256=SOURCE_MANIFEST_SHA256,
                resolution_policy_sha256=POLICY_SHA256,
            )

        wrong_municipality = _approved_points()
        wrong_municipality[0]["source"]["current_istat_code"] = "001002"
        with self.assertRaisesRegex(
            points.NationalForecastPointsError, "municipality binding"
        ):
            points.build_approved_forecast_points_artifact(
                catalog=_catalog(),
                points=wrong_municipality,
                boundary_sha256=BOUNDARY_SHA256,
                source_manifest_sha256=SOURCE_MANIFEST_SHA256,
                resolution_policy_sha256=POLICY_SHA256,
            )

    def test_official_istat_mapping_method_must_match_source_identity(self):
        incoherent_cases = (
            ("direct_current_istat_code_v1", "001002"),
            ("registry_2017_2025_code_v1", "001001"),
            ("reviewed_post_2021_seat_override_v1", "001001"),
        )
        for mapping_method, source_istat_code in incoherent_cases:
            with self.subTest(
                mapping_method=mapping_method,
                source_istat_code=source_istat_code,
            ):
                raw = _approved_points()
                raw[0]["source"]["mapping_method"] = mapping_method
                raw[0]["source"]["source_istat_code"] = source_istat_code
                with self.assertRaisesRegex(
                    points.NationalForecastPointsError,
                    "mapping method conflicts with source identity",
                ):
                    points.build_approved_forecast_points_artifact(
                        catalog=_catalog(),
                        points=raw,
                        boundary_sha256=BOUNDARY_SHA256,
                        source_manifest_sha256=SOURCE_MANIFEST_SHA256,
                        resolution_policy_sha256=POLICY_SHA256,
                    )

    def test_official_istat_loc_id_must_be_a_positive_integer_string(self):
        for invalid_loc_id in ("0", "-1", "abc", 1):
            with self.subTest(loc_id=invalid_loc_id):
                raw = _approved_points()
                raw[0]["source"]["loc_id"] = invalid_loc_id
                with self.assertRaisesRegex(
                    points.NationalForecastPointsError,
                    "LOC_ID must be a positive integer string",
                ):
                    points.build_approved_forecast_points_artifact(
                        catalog=_catalog(),
                        points=raw,
                        boundary_sha256=BOUNDARY_SHA256,
                        source_manifest_sha256=SOURCE_MANIFEST_SHA256,
                        resolution_policy_sha256=POLICY_SHA256,
                    )

    def test_official_istat_release_identity_is_fixed(self):
        for field, value in (
            ("source_crs", "EPSG:4326"),
            ("reference_date", "2022-01-01"),
        ):
            with self.subTest(field=field):
                raw = _approved_points()
                raw[0]["source"][field] = value
                with self.assertRaisesRegex(
                    points.NationalForecastPointsError,
                    "official ISTAT release identity is invalid",
                ):
                    points.build_approved_forecast_points_artifact(
                        catalog=_catalog(),
                        points=raw,
                        boundary_sha256=BOUNDARY_SHA256,
                        source_manifest_sha256=SOURCE_MANIFEST_SHA256,
                        resolution_policy_sha256=POLICY_SHA256,
                    )

    def test_complete_catalog_coverage_is_mandatory(self):
        with self.assertRaisesRegex(
            points.NationalForecastPointsError, "exactly cover"
        ):
            points.build_approved_forecast_points_artifact(
                catalog=_catalog(),
                points=_approved_points()[:-1],
                boundary_sha256=BOUNDARY_SHA256,
                source_manifest_sha256=SOURCE_MANIFEST_SHA256,
                resolution_policy_sha256=POLICY_SHA256,
            )

    def test_whole_artifact_hash_protects_top_level_provenance(self):
        artifact = _approved_artifact()
        artifact["source_manifest_sha256"] = "e" * 64
        with self.assertRaisesRegex(
            points.NationalForecastPointsError, "artifact SHA-256 mismatch"
        ):
            points.validate_forecast_points_artifact(artifact, catalog=_catalog())

    def test_catalog_and_boundary_bindings_are_enforced(self):
        catalog = _catalog()
        with self.assertRaisesRegex(
            points.NationalForecastPointsError, "boundary source differs"
        ):
            points.build_approved_forecast_points_artifact(
                catalog=catalog,
                points=_approved_points(),
                boundary_sha256="f" * 64,
                source_manifest_sha256=SOURCE_MANIFEST_SHA256,
                resolution_policy_sha256=POLICY_SHA256,
            )

        artifact = _approved_artifact()
        other_catalog = _catalog()
        other_catalog["catalog_version"] = "fixture-v2"
        other_catalog["catalog_sha256"] = points.sha256_hex(
            points.canonical_json_bytes(
                {key: value for key, value in other_catalog.items() if key != "catalog_sha256"}
            )
        )
        with self.assertRaisesRegex(
            points.NationalForecastPointsError, "another national catalog"
        ):
            points.validate_forecast_points_artifact(
                artifact, catalog=other_catalog
            )


class ExperimentalProxyTests(unittest.TestCase):
    def test_catalog_proxy_has_separate_status_quality_and_opt_in(self):
        catalog = _catalog()
        artifact = points.build_experimental_proxy_artifact(catalog)
        self.assertEqual(artifact["status"], points.EXPERIMENTAL_POINTS_STATUS)
        self.assertEqual(
            {item["quality"] for item in artifact["points"]},
            {points.QUALITY_EXPERIMENTAL_BOUNDARY_PROXY},
        )
        with self.assertRaisesRegex(
            points.NationalForecastPointsError, "explicit opt-in"
        ):
            points.validate_forecast_points_artifact(artifact, catalog=catalog)
        points.validate_forecast_points_artifact(
            artifact, catalog=catalog, allow_experimental=True
        )

    def test_catalog_proxy_rejects_non_wgs84_source_crs(self):
        catalog = _catalog()
        artifact = points.build_experimental_proxy_artifact(catalog)
        raw = deepcopy(artifact["points"])
        raw[0]["source"]["source_crs"] = "EPSG:32632"
        with self.assertRaisesRegex(
            points.NationalForecastPointsError,
            "experimental proxy source CRS is invalid",
        ):
            points.build_forecast_points_artifact(
                catalog=catalog,
                points=raw,
                status=points.EXPERIMENTAL_POINTS_STATUS,
                boundary_sha256=artifact["boundary_sha256"],
                source_manifest_sha256=artifact["source_manifest_sha256"],
                resolution_policy_sha256=artifact["resolution_policy_sha256"],
            )


class ArtifactIoTests(unittest.TestCase):
    def test_create_only_round_trip_and_existing_output_rejection(self):
        catalog = _catalog()
        artifact = _approved_artifact()
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "forecast-points.json"
            points.write_forecast_points_create_only(
                output, artifact, catalog=catalog
            )
            self.assertEqual(
                output.read_bytes(), points.canonical_json_bytes(artifact)
            )
            loaded = points.load_forecast_points_artifact(
                output, catalog=catalog
            )
            self.assertEqual(loaded, artifact)
            with self.assertRaisesRegex(
                points.NationalForecastPointsError, "create-only"
            ):
                points.write_forecast_points_create_only(
                    output, artifact, catalog=catalog
                )

    def test_loader_rejects_noncanonical_json(self):
        artifact = _approved_artifact()
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "pretty.json"
            output.write_text(
                json.dumps(artifact, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(
                points.NationalForecastPointsError, "not canonical JSON"
            ):
                points.load_forecast_points_artifact(output, catalog=_catalog())

    def test_experimental_io_requires_opt_in_on_write_and_read(self):
        catalog = _catalog()
        artifact = points.build_experimental_proxy_artifact(catalog)
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "proxy.json"
            with self.assertRaisesRegex(
                points.NationalForecastPointsError, "explicit opt-in"
            ):
                points.write_forecast_points_create_only(
                    output, artifact, catalog=catalog
                )
            points.write_forecast_points_create_only(
                output,
                artifact,
                catalog=catalog,
                allow_experimental=True,
            )
            with self.assertRaisesRegex(
                points.NationalForecastPointsError, "explicit opt-in"
            ):
                points.load_forecast_points_artifact(output, catalog=catalog)
            self.assertEqual(
                points.load_forecast_points_artifact(
                    output,
                    catalog=catalog,
                    allow_experimental=True,
                ),
                artifact,
            )


if __name__ == "__main__":
    unittest.main()
