"""Full-catalog offline tests over the real verified pilot artifacts."""

from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from local_pipeline.contract_v1 import (
    CAMS_POLLEN_IDS,
    CAMS_POLLEN_PROVIDER,
    CAMS_PROVIDER,
    CAMS_VARIABLE_IDS,
    DEFAULT_CATALOG_PATH,
    ICON_PROVIDER,
    canonical_json_bytes,
    load_catalog,
    validate_cams_payload,
    validate_cams_pollen_payload,
    validate_icon_payload,
    validate_run_manifest,
)
from local_pipeline.snapshot_materializer import (
    DEFAULT_ICON_ARCHIVE,
    DEFAULT_ICON_REPORT,
    DEFAULT_CAMS_PAYLOAD,
    DEFAULT_CAMS_REPORT,
    SnapshotMaterializationError,
    load_verified_cams_snapshot,
    load_verified_icon_snapshot,
    load_verified_snapshots,
    materialize_verified_cams,
    materialize_verified_icon,
    materialize_snapshots,
)


class VerifiedPilotMaterializationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog = load_catalog(DEFAULT_CATALOG_PATH)
        cls.icon_source, cls.cams_source = load_verified_snapshots()
        before_icon = deepcopy(cls.icon_source)
        before_cams = deepcopy(cls.cams_source)
        cls.result = materialize_snapshots(
            cls.icon_source,
            cls.cams_source,
            catalog=cls.catalog,
        )
        cls.sources_unchanged = (
            before_icon == cls.icon_source and before_cams == cls.cams_source
        )

    def test_real_snapshots_split_into_independent_complete_and_derived_providers(self):
        icon = self.result["icon"]
        cams = self.result["cams"]
        cams_pollen = self.result["cams_pollen"]
        expected_codes = set(self.catalog.istat_codes)

        self.assertEqual(
            self.icon_source["catalog_sha256"],
            self.cams_source["catalog_sha256"],
        )
        self.assertEqual(expected_codes, set(icon["documents"]))
        self.assertEqual(expected_codes, set(cams["documents"]))
        self.assertEqual(expected_codes, set(cams_pollen["documents"]))
        self.assertEqual(215, len(icon["documents"]))
        self.assertEqual(215, len(cams["documents"]))
        self.assertEqual(215, len(cams_pollen["documents"]))
        self.assertEqual(ICON_PROVIDER, icon["manifest"]["provider"])
        self.assertEqual(CAMS_PROVIDER, cams["manifest"]["provider"])
        self.assertEqual(CAMS_POLLEN_PROVIDER, cams_pollen["manifest"]["provider"])
        self.assertEqual(CAMS_PROVIDER, cams_pollen["derived_from"])
        self.assertNotEqual(icon["manifest"]["source_run_id"] + ICON_PROVIDER,
                            cams["manifest"]["source_run_id"] + CAMS_PROVIDER)
        validate_run_manifest(
            icon["manifest"], self.catalog, expected_provider=ICON_PROVIDER,
            object_bodies=icon["documents"],
        )
        validate_run_manifest(
            cams["manifest"], self.catalog, expected_provider=CAMS_PROVIDER,
            object_bodies=cams["documents"],
        )
        validate_run_manifest(
            cams_pollen["manifest"], self.catalog,
            expected_provider=CAMS_POLLEN_PROVIDER,
            object_bodies=cams_pollen["documents"],
        )

    def test_pordenone_payloads_use_istat_and_preserve_native_hourly_horizons(self):
        icon = json.loads(self.result["icon"]["documents"]["093033"])
        cams = json.loads(self.result["cams"]["documents"]["093033"])
        cams_pollen = json.loads(
            self.result["cams_pollen"]["documents"]["093033"]
        )

        validate_icon_payload(icon, self.catalog, expected_istat_code="093033")
        validate_cams_payload(cams, self.catalog, expected_istat_code="093033")
        validate_cams_pollen_payload(
            cams_pollen, self.catalog, expected_istat_code="093033"
        )
        self.assertEqual("Pordenone", icon["municipality"]["name"])
        self.assertEqual("Pordenone", cams["municipality"]["name"])
        self.assertEqual(73, len(icon["hourly"]))
        self.assertEqual(36, len(icon["two_hourly"]))
        self.assertEqual(97, len(cams["hourly"]))
        self.assertEqual(97, len(cams_pollen["hourly"]))
        self.assertEqual(set(CAMS_VARIABLE_IDS), set(cams["hourly"][0]["values"]))
        self.assertEqual(set(CAMS_POLLEN_IDS), set(cams_pollen["hourly"][0]["values"]))
        self.assertLess(
            len(self.result["cams_pollen"]["documents"]["093033"]),
            len(self.result["cams"]["documents"]["093033"]),
        )
        self.assertTrue(all(
            isinstance(row["condition"]["native_code"], int)
            and row["condition"]["native_label_it"]
            for row in icon["hourly"]
        ))

    def test_all_28_cams_variables_remain_validated_in_the_private_archive(self):
        summary = self.result["cams"]["archive_summary"]
        self.assertEqual(28, summary["variable_count"])
        self.assertEqual(97, summary["hourly_instants"])
        self.assertEqual(215, summary["municipality_count"])
        self.assertGreater(summary["unique_cell_count"], 1)
        self.assertEqual(self.catalog.sha256, summary["catalog_sha256"])
        self.assertTrue(set(CAMS_POLLEN_IDS).issubset(summary["variable_ids"]))

    def test_every_manifest_hash_matches_the_exact_canonical_payload_bytes(self):
        for provider in ("icon", "cams", "cams_pollen"):
            bundle = self.result[provider]
            for istat_code, raw in bundle["documents"].items():
                descriptor = bundle["manifest"]["objects"][istat_code]
                self.assertEqual(raw, canonical_json_bytes(json.loads(raw)))
                self.assertEqual(len(raw), descriptor["json_bytes"])
                self.assertEqual(hashlib.sha256(raw).hexdigest(), descriptor["sha256"])

    def test_tampered_source_is_rejected_before_materialization(self):
        original = Path(DEFAULT_CAMS_PAYLOAD).read_bytes()
        report = json.loads(Path(DEFAULT_CAMS_REPORT).read_bytes())
        with tempfile.TemporaryDirectory(prefix="meteofriul-tampered-pilot-") as directory:
            root = Path(directory)
            payload = root / "cams.json"
            payload.write_bytes(original[:-1] + (b" " if original[-1:] != b" " else b"\n"))
            report_path = root / "report.json"
            report_path.write_text(json.dumps(report), encoding="utf-8")
            with self.assertRaisesRegex(SnapshotMaterializationError, "hash differs"):
                load_verified_snapshots(cams_payload=payload, cams_report=report_path)

            # The independent ICON family neither opens nor depends on the
            # corrupt CAMS path.
            icon_bundle = materialize_verified_icon(catalog=self.catalog)
            self.assertEqual(ICON_PROVIDER, icon_bundle["icon"]["manifest"]["provider"])

    def test_corrupt_icon_does_not_prevent_independent_cams_materialization(self):
        with tempfile.TemporaryDirectory(prefix="meteofriul-tampered-icon-") as directory:
            archive = Path(directory) / "icon.json"
            archive.write_bytes(b"{}")
            with self.assertRaises(SnapshotMaterializationError):
                load_verified_icon_snapshot(
                    icon_archive=archive,
                    icon_report=DEFAULT_ICON_REPORT,
                )

            cams_bundle = materialize_verified_cams(catalog=self.catalog)
            self.assertEqual(CAMS_PROVIDER, cams_bundle["cams"]["manifest"]["provider"])
            self.assertEqual(
                CAMS_POLLEN_PROVIDER,
                cams_bundle["cams_pollen"]["manifest"]["provider"],
            )

    def test_reports_cannot_relabel_authenticated_payload_runs(self):
        with tempfile.TemporaryDirectory(prefix="meteofriul-run-binding-") as directory:
            root = Path(directory)

            icon_report = json.loads(Path(DEFAULT_ICON_REPORT).read_bytes())
            icon_report["run_utc"] = "2026-09-02T00:00:00Z"
            icon_report_path = root / "icon-report.json"
            icon_report_path.write_text(json.dumps(icon_report), encoding="utf-8")
            with self.assertRaisesRegex(
                SnapshotMaterializationError,
                "different model runs",
            ):
                load_verified_icon_snapshot(
                    icon_archive=DEFAULT_ICON_ARCHIVE,
                    icon_report=icon_report_path,
                )

            cams_payload = {
                "schema_version": 2,
                "kind": "cams_region_point_extraction",
                "catalog_sha256": self.cams_source["catalog_sha256"],
                "run_utc": "2026-09-03T00:00:00Z",
                "request_plan_sha256": "a" * 64,
                "request_sha256": "b" * 64,
            }
            cams_payload_path = root / "cams-payload.json"
            cams_payload_raw = json.dumps(
                cams_payload,
                separators=(",", ":"),
            ).encode("utf-8")
            cams_payload_path.write_bytes(cams_payload_raw)
            cams_report = {
                "payload_sha256": hashlib.sha256(cams_payload_raw).hexdigest(),
                "catalog_sha256": self.cams_source["catalog_sha256"],
                "run_date": "2026-09-02",
                "request_plan_sha256": "a" * 64,
                "request_sha256": "b" * 64,
            }
            cams_report_path = root / "cams-report.json"
            cams_report_path.write_text(json.dumps(cams_report), encoding="utf-8")
            with self.assertRaisesRegex(
                SnapshotMaterializationError,
                "different model runs",
            ):
                load_verified_cams_snapshot(
                    cams_payload=cams_payload_path,
                    cams_report=cams_report_path,
                )

    def test_independent_loaders_preserve_authenticated_source_envelopes(self):
        self.assertEqual(self.icon_source, load_verified_icon_snapshot())
        self.assertEqual(self.cams_source, load_verified_cams_snapshot())

    def test_source_objects_are_not_mutated(self):
        self.assertTrue(self.sources_unchanged)


if __name__ == "__main__":
    unittest.main()
