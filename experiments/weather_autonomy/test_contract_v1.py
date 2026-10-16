"""Offline contract-v1 tests; no network, provider, app, or cloud access."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from local_pipeline.contract_v1 import (
    CAMS_POLLEN_PROJECTION,
    CAMS_POLLEN_PROVIDER,
    CAMS_PROVIDER,
    CAMS_POLLEN_IDS,
    CAMS_POLLEN_VARIABLES,
    CAMS_VARIABLE_IDS,
    CAMS_VARIABLES,
    CATALOG_VERSION,
    ContractError,
    ICON_PROVIDER,
    build_cams_payload,
    build_cams_pollen_payload,
    build_freshness,
    build_icon_condition,
    build_icon_payload,
    build_latest_document,
    build_object_descriptor,
    build_run_manifest,
    canonical_json_bytes,
    canonical_run_id,
    classify_freshness,
    load_catalog,
    validate_cams_payload,
    validate_cams_pollen_payload,
    validate_icon_payload,
    validate_latest_document,
    validate_run_manifest,
)


RUN = datetime(2026, 9, 3, tzinfo=timezone.utc)
RUN_AT = "2026-09-03T00:00:00Z"
GENERATED_AT = "2026-09-03T14:00:00Z"


def iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def icon_hourly():
    rows = []
    for lead in range(73):
        valid = RUN + timedelta(hours=lead)
        rows.append(
            {
                "valid_at": iso(valid),
                "interval_start": None if lead == 0 else iso(valid - timedelta(hours=1)),
                "interval_end": None if lead == 0 else iso(valid),
                "temperature_c": 20 + lead / 10,
                "apparent_temperature_c": 20.5 + lead / 10,
                "relative_humidity_pct": 65,
                "pressure_msl_hpa": 1015,
                "wind_speed_m_s": 2,
                "wind_from_degrees": 180,
                "wind_gust_max_m_s": None if lead == 0 else 4,
                "cloud_cover_pct": 25,
                "precipitation_mm": None if lead == 0 else 0,
                "liquid_rain_mm": None if lead == 0 else 0,
                "snow_water_equivalent_mm": None if lead == 0 else 0,
                "condition": build_icon_condition(96 if lead == 10 else 0),
                "quality_flags": [],
            }
        )
    return rows


def cams_hourly():
    return [
        {
            "valid_at": iso(RUN + timedelta(hours=lead)),
            "values": {
                variable: (None if variable == "alder_pollen" and lead == 3 else float(lead))
                for variable in CAMS_VARIABLE_IDS
            },
            "quality_flags": {
                variable: (["source_missing"] if variable == "alder_pollen" and lead == 3 else [])
                for variable in CAMS_VARIABLE_IDS
            },
        }
        for lead in range(97)
    ]


class ContractV1Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog = load_catalog()
        cls.town = cls.catalog.municipality("093033")
        cls.model_point = {
            "lat": cls.town.latitude,
            "lon": cls.town.longitude,
            "distance_km": 0.0,
            "grid_index": 130,
        }

    def test_loads_and_canonically_hashes_the_complete_istat_catalog(self):
        self.assertEqual(215, self.catalog.municipality_count)
        self.assertEqual(CATALOG_VERSION, self.catalog.version)
        self.assertEqual(215, len(set(self.catalog.istat_codes)))
        self.assertEqual("Pordenone", self.town.name)
        self.assertRegex(self.catalog.sha256, r"^[0-9a-f]{64}$")
        self.assertEqual(
            "d5cb6f9efdf10151caa0508b07ed910488db01dc29de45b293ac9eb05652eca4",
            self.catalog.sha256,
        )

        source_path = Path(__file__).resolve().parents[2] / "backend/app/data/fvg_municipalities.json"
        source = json.loads(source_path.read_bytes())
        legacy = load_catalog(source_path)
        source["municipalities"].reverse()
        with tempfile.TemporaryDirectory() as directory:
            reordered = Path(directory) / "catalog.json"
            reordered.write_text(json.dumps(source, indent=7), encoding="utf-8")
            self.assertEqual(legacy.sha256, load_catalog(reordered).sha256)
            self.assertNotEqual(self.catalog.sha256, load_catalog(reordered).sha256)

    def test_run_id_and_freshness_boundaries_are_canonical(self):
        self.assertEqual("20260903T000000Z", canonical_run_id(RUN_AT))
        for invalid in (
            "2026-09-03T00:00:00+00:00",
            "2026-09-03T00:00:00.000Z",
            "2026-09-03T00:30:00Z",
        ):
            with self.subTest(invalid=invalid), self.assertRaises(ContractError):
                canonical_run_id(invalid)

        icon = build_freshness(ICON_PROVIDER, RUN_AT, "2026-09-06T00:00:00Z")
        cams = build_freshness(CAMS_PROVIDER, RUN_AT, "2026-09-07T00:00:00Z")
        self.assertEqual("2026-09-03T18:00:00Z", icon["fresh_until"])
        self.assertEqual("2026-09-04T00:00:00Z", icon["usable_until"])
        self.assertEqual("2026-09-04T00:00:00Z", cams["fresh_until"])
        self.assertEqual("2026-09-04T06:00:00Z", cams["usable_until"])
        coverage_limited = build_freshness(ICON_PROVIDER, RUN_AT, "2026-09-05T12:00:00Z")
        self.assertEqual("2026-09-03T12:00:00Z", coverage_limited["fresh_until"])
        self.assertEqual("2026-09-03T12:00:00Z", coverage_limited["usable_until"])
        with self.assertRaises(ContractError):
            build_freshness(ICON_PROVIDER, RUN_AT, "2026-09-04T23:00:00Z")
        self.assertEqual("fresh", classify_freshness(icon, "2026-09-03T18:00:00Z"))
        self.assertEqual("stale", classify_freshness(icon, "2026-09-03T18:00:01Z"))
        self.assertEqual("expired", classify_freshness(icon, "2026-09-04T00:00:01Z"))

    def test_icon_payload_has_73_hours_true_two_hour_aggregates_and_safe_ww96(self):
        payload = build_icon_payload(
            catalog=self.catalog,
            istat_code="093033",
            run_at=RUN_AT,
            generated_at=GENERATED_AT,
            model_point=self.model_point,
            hourly=icon_hourly(),
        )
        validate_icon_payload(payload, self.catalog, expected_istat_code="093033")
        self.assertEqual(73, len(payload["hourly"]))
        self.assertEqual(36, len(payload["two_hourly"]))
        self.assertEqual("093033", payload["municipality"]["istat_code"])
        ww96 = payload["hourly"][10]["condition"]
        self.assertEqual("strong_storm", ww96["semantic_key"])
        self.assertEqual("StrongStorm", ww96["icon_key"])
        self.assertNotIn("Hail", ww96["icon_key"])
        self.assertEqual(0, payload["two_hourly"][0]["precipitation_mm"])

        for mutation in (
            lambda value: value["units"].update(temperature_c="kelvin"),
            lambda value: value["municipality"].update(istat_code="030129"),
            lambda value: value["hourly"][10]["condition"].update(icon_key="StormHail"),
            lambda value: value["hourly"][10].update(temperature_c=float("nan")),
            lambda value: value["hourly"][11].update(valid_at=value["hourly"][12]["valid_at"]),
            lambda value: value.update(extra=True),
        ):
            broken = deepcopy(payload)
            mutation(broken)
            with self.subTest(mutation=mutation), self.assertRaises(ContractError):
                validate_icon_payload(broken, self.catalog, expected_istat_code="093033")

    def test_icon_payload_rejects_360_degree_wind_direction(self):
        hourly = icon_hourly()
        hourly[1]["wind_from_degrees"] = 360.0
        with self.assertRaisesRegex(ContractError, "below 360 degrees"):
            build_icon_payload(
                catalog=self.catalog,
                istat_code="093033",
                run_at=RUN_AT,
                generated_at=GENERATED_AT,
                model_point=self.model_point,
                hourly=hourly,
            )

    def test_cams_payload_has_independent_97_hour_28_variable_contract(self):
        payload = build_cams_payload(
            catalog=self.catalog,
            istat_code="093033",
            run_at=RUN_AT,
            generated_at=GENERATED_AT,
            model_point=self.model_point,
            hourly=cams_hourly(),
        )
        validate_cams_payload(payload, self.catalog, expected_istat_code="093033")
        self.assertEqual(97, len(payload["hourly"]))
        self.assertEqual(28, len(CAMS_VARIABLE_IDS))
        self.assertEqual(6, len(CAMS_POLLEN_IDS))
        self.assertEqual(22, len(set(CAMS_VARIABLE_IDS) - set(CAMS_POLLEN_IDS)))
        self.assertEqual(set(CAMS_VARIABLE_IDS), set(payload["hourly"][0]["values"]))
        self.assertEqual(
            7,
            sum(
                row["validation_status"] == "regularly_validated_in_situ_by_provider"
                for row in CAMS_VARIABLES
            ),
        )
        self.assertEqual({"grains/m3", "ug/m3"}, {row["unit"] for row in CAMS_VARIABLES})
        self.assertIsNone(payload["hourly"][3]["values"]["alder_pollen"])
        self.assertIsNone(payload["health_classification"])

        for invalid in (-1, float("inf"), True, "1"):
            broken = deepcopy(payload)
            broken["hourly"][4]["values"]["birch_pollen"] = invalid
            with self.subTest(invalid=invalid), self.assertRaises(ContractError):
                validate_cams_payload(broken, self.catalog)

        missing = deepcopy(payload)
        missing["hourly"][0]["values"].pop("ozone")
        with self.assertRaises(ContractError):
            validate_cams_payload(missing, self.catalog)

    def test_cams_pollen_projection_is_small_explicit_and_traceable(self):
        source = build_cams_payload(
            catalog=self.catalog,
            istat_code="093033",
            run_at=RUN_AT,
            generated_at=GENERATED_AT,
            model_point=self.model_point,
            hourly=cams_hourly(),
        )
        payload = build_cams_pollen_payload(
            catalog=self.catalog,
            istat_code="093033",
            run_at=RUN_AT,
            generated_at=GENERATED_AT,
            model_point=self.model_point,
            hourly=source["hourly"],
        )

        validate_cams_pollen_payload(
            payload,
            self.catalog,
            expected_istat_code="093033",
        )
        self.assertEqual(CAMS_POLLEN_PROVIDER, payload["provider"])
        self.assertEqual(CAMS_POLLEN_PROJECTION, payload["projection"])
        self.assertEqual(CAMS_POLLEN_VARIABLES, payload["variables"])
        self.assertEqual(97, len(payload["hourly"]))
        self.assertEqual(
            set(CAMS_POLLEN_IDS),
            set(payload["hourly"][0]["values"]),
        )
        self.assertIsNone(payload["hourly"][3]["values"]["alder_pollen"])
        self.assertEqual(
            ["source_missing"],
            payload["hourly"][3]["quality_flags"]["alder_pollen"],
        )

        extra = deepcopy(payload)
        extra["hourly"][0]["values"]["ozone"] = 12.0
        with self.assertRaises(ContractError):
            validate_cams_pollen_payload(extra, self.catalog)

        untraceable = deepcopy(payload)
        untraceable["projection"]["source_provider"] = CAMS_POLLEN_PROVIDER
        with self.assertRaises(ContractError):
            validate_cams_pollen_payload(untraceable, self.catalog)

    def test_payload_descriptor_hashes_only_canonical_uncompressed_json(self):
        payload = build_icon_payload(
            catalog=self.catalog,
            istat_code="093033",
            run_at=RUN_AT,
            generated_at=GENERATED_AT,
            model_point=self.model_point,
            hourly=icon_hourly(),
        )
        encoded = canonical_json_bytes(payload)
        descriptor = build_object_descriptor(
            provider=ICON_PROVIDER,
            source_run_id=canonical_run_id(RUN_AT),
            istat_code="093033",
            payload=payload,
            catalog=self.catalog,
        )
        self.assertEqual(len(encoded), descriptor["json_bytes"])
        self.assertEqual(hashlib.sha256(encoded).hexdigest(), descriptor["sha256"])
        self.assertEqual(
            descriptor,
            build_object_descriptor(
                provider=ICON_PROVIDER,
                source_run_id=canonical_run_id(RUN_AT),
                istat_code="093033",
                payload=encoded,
                catalog=self.catalog,
            ),
        )
        with self.assertRaises(ContractError):
            build_object_descriptor(
                provider=ICON_PROVIDER,
                source_run_id=canonical_run_id(RUN_AT),
                istat_code="093033",
                payload=json.dumps(payload).encode("utf-8"),
                catalog=self.catalog,
            )

    def descriptors(self, run_id):
        return {
            code: {
                "path": f"runs/{run_id}/municipalities/{code}.json",
                "json_bytes": 100,
                "sha256": hashlib.sha256(code.encode()).hexdigest(),
            }
            for code in self.catalog.istat_codes
        }

    def test_run_manifests_require_exactly_215_catalog_objects_and_stay_separate(self):
        run_id = canonical_run_id(RUN_AT)
        icon = build_run_manifest(
            provider=ICON_PROVIDER,
            run_at=RUN_AT,
            generated_at=GENERATED_AT,
            catalog=self.catalog,
            objects=self.descriptors(run_id),
        )
        cams = build_run_manifest(
            provider=CAMS_PROVIDER,
            run_at=RUN_AT,
            generated_at=GENERATED_AT,
            catalog=self.catalog,
            objects=self.descriptors(run_id),
        )
        validate_run_manifest(icon, self.catalog, expected_provider=ICON_PROVIDER)
        validate_run_manifest(cams, self.catalog, expected_provider=CAMS_PROVIDER)
        self.assertNotEqual(icon["provider"], cams["provider"])
        self.assertNotEqual(icon["model"], cams["model"])
        self.assertNotEqual(icon["freshness"], cams["freshness"])

        missing = deepcopy(icon)
        missing["objects"].pop("093033")
        with self.assertRaises(ContractError):
            validate_run_manifest(missing, self.catalog)
        extra = deepcopy(icon)
        extra["objects"]["999999"] = next(iter(extra["objects"].values()))
        with self.assertRaises(ContractError):
            validate_run_manifest(extra, self.catalog)
        with self.assertRaises(ContractError):
            validate_run_manifest(icon, self.catalog, expected_provider=CAMS_PROVIDER)

    def test_latest_hashes_the_immutable_manifest_and_rejects_revocation_or_tampering(self):
        run_id = canonical_run_id(RUN_AT)
        manifest = build_run_manifest(
            provider=ICON_PROVIDER,
            run_at=RUN_AT,
            generated_at=GENERATED_AT,
            catalog=self.catalog,
            objects=self.descriptors(run_id),
        )
        latest = build_latest_document(
            provider=ICON_PROVIDER,
            revision=1,
            published_at="2026-09-03T14:05:00Z",
            run_manifest=manifest,
            catalog=self.catalog,
        )
        validate_latest_document(
            latest,
            expected_provider=ICON_PROVIDER,
            catalog=self.catalog,
            run_manifest=manifest,
        )
        manifest_bytes = canonical_json_bytes(manifest)
        self.assertEqual(len(manifest_bytes), latest["latest"]["manifest_json_bytes"])
        self.assertEqual(hashlib.sha256(manifest_bytes).hexdigest(), latest["latest"]["manifest_sha256"])
        self.assertEqual(self.catalog.reference(), latest["catalog"])

        revoked = deepcopy(latest)
        revoked["disabled_run_ids"] = [run_id]
        with self.assertRaises(ContractError):
            validate_latest_document(revoked)
        tampered = deepcopy(manifest)
        tampered["generated_at"] = "2026-09-03T14:01:00Z"
        with self.assertRaises(ContractError):
            validate_latest_document(
                latest,
                catalog=self.catalog,
                run_manifest=tampered,
            )
        wrong_catalog = deepcopy(latest)
        wrong_catalog["catalog"]["sha256"] = "0" * 64
        with self.assertRaises(ContractError):
            validate_latest_document(wrong_catalog, catalog=self.catalog)

    def test_canonical_json_rejects_nonfinite_numbers(self):
        with self.assertRaises(ContractError):
            canonical_json_bytes({"bad": float("nan")})


if __name__ == "__main__":
    unittest.main()
