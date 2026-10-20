"""Offline byte-limit regressions and a full 215x73 synthetic publication.

The observed byte count is real; the test payload is explicitly synthetic.
No provider acquisition, cloud writes or notification service is involved.
"""
from contextlib import redirect_stdout
from datetime import timedelta
import gc
import gzip
import hashlib
import io
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import zipfile

from local_pipeline import snapshot_materializer as materializer
from local_pipeline.operational_diagnostics import phase

OBSERVED_PAYLOAD_BYTES = 34_601_901
LEGACY_LIMIT = 32 * 1024**2


class IconSnapshotLimitTests(unittest.TestCase):
    def write_minimal(self, root, target, *, zipped=False):
        payload = dict(schema_version=1, status="partial_pilot_not_production",
                       run_utc="2026-10-20T12:00:00Z")
        raw = json.dumps(payload).encode()
        raw += b" " * (target - len(raw))
        report = root / "report.json"
        report.write_text(json.dumps(dict(
            payload_sha256=hashlib.sha256(raw).hexdigest(),
            catalog_sha256="a"*64, run_utc=payload["run_utc"],
        )))
        path = root / ("payload.zip" if zipped else "payload.json")
        if zipped:
            with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                archive.writestr(materializer.ICON_ARCHIVE_MEMBER, raw)
        else:
            path.write_bytes(raw)
        return path, report

    def test_observed_size_is_rejected_before_and_read_after_json_and_zip(self):
        self.assertEqual(materializer.MAX_ICON_JSON_BYTES, 64 * 1024**2)
        with tempfile.TemporaryDirectory() as directory:
            for zipped in (False, True):
                with self.subTest(zipped=zipped):
                    path, report = self.write_minimal(Path(directory), OBSERVED_PAYLOAD_BYTES, zipped=zipped)
                    with patch.object(materializer, "MAX_ICON_JSON_BYTES", LEGACY_LIMIT):
                        with self.assertRaises(materializer.SnapshotMaterializationError):
                            materializer.load_verified_icon_snapshot(icon_archive=path, icon_report=report)
                    loaded = materializer.load_verified_icon_snapshot(icon_archive=path, icon_report=report)
                    self.assertEqual(loaded["run_utc"], "2026-10-20T12:00:00Z")

    def test_exact_limit_and_one_byte_over_remain_bounded_for_both_formats(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(
                materializer, "MAX_ICON_JSON_BYTES", 512):
            for zipped in (False, True):
                for size in (512, 513):
                    with self.subTest(zipped=zipped, size=size):
                        path, report = self.write_minimal(Path(directory), size, zipped=zipped)
                        if size == 512:
                            materializer.load_verified_icon_snapshot(icon_archive=path, icon_report=report)
                        else:
                            with self.assertRaisesRegex(materializer.SnapshotMaterializationError, "size bound"):
                                materializer.load_verified_icon_snapshot(icon_archive=path, icon_report=report)

    def test_hash_run_and_envelope_checks_are_not_bypassed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for change, expected in (
                (lambda doc: doc.update(payload_sha256="0"*64), "hash differs"),
                (lambda doc: doc.update(run_utc="2026-10-19T12:00:00Z"), "different model runs"),
            ):
                path, report = self.write_minimal(root, 512)
                doc = json.loads(report.read_text())
                change(doc)
                report.write_text(json.dumps(doc))
                with self.assertRaisesRegex(materializer.SnapshotMaterializationError, expected):
                    materializer.load_verified_icon_snapshot(icon_archive=path, icon_report=report)
            path, report = self.write_minimal(root, 512)
            raw = json.loads(path.read_bytes())
            raw["schema_version"] = 2
            encoded = json.dumps(raw).encode()
            path.write_bytes(encoded)
            doc = json.loads(report.read_text())
            doc["payload_sha256"] = hashlib.sha256(encoded).hexdigest()
            report.write_text(json.dumps(doc))
            with self.assertRaisesRegex(materializer.SnapshotMaterializationError, "envelope"):
                materializer.load_verified_icon_snapshot(icon_archive=path, icon_report=report)

    def test_read_is_bounded_even_if_file_grows_after_stat(self):
        stream = io.BytesIO(b"x"*100)
        with (patch.object(Path, "is_file", return_value=True),
              patch.object(Path, "stat", return_value=SimpleNamespace(st_size=8)),
              patch.object(Path, "open", return_value=stream),
              patch.object(stream, "read", wraps=stream.read) as read):
            with self.assertRaisesRegex(materializer.SnapshotMaterializationError, "size bound"):
                materializer._read_bounded(Path("never-opened"), 16, "ICON payload")
            read.assert_called_once_with(17)

    def test_diagnostics_explain_size_without_disclosing_paths(self):
        output = io.StringIO()
        with (patch.object(Path, "is_file", return_value=True),
              patch.object(Path, "stat", return_value=SimpleNamespace(st_size=OBSERVED_PAYLOAD_BYTES)),
              patch.object(Path, "open") as opened,
              redirect_stdout(output), self.assertRaises(materializer.SnapshotMaterializationError)):
            with phase("validation", provider="icon"):
                materializer._read_bounded(Path("private-secret-path"), LEGACY_LIMIT, "ICON payload")
        opened.assert_not_called()
        row = json.loads(output.getvalue().splitlines()[-1])
        self.assertEqual(row["observed_bytes"], OBSERVED_PAYLOAD_BYTES)
        self.assertEqual(row["limit_bytes"], LEGACY_LIMIT)
        self.assertEqual(row["artifact_kind"], "icon_payload")
        self.assertEqual(row["error_summary"], "ICON payload exceeds its local size bound")
        self.assertNotIn("private-secret", output.getvalue())

    def test_zero_length_report_limit_and_changed_file_still_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "empty"
            path.touch()
            with self.assertRaises(materializer.SnapshotMaterializationError):
                materializer._read_bounded(path, 512, "ICON payload")
            path, report = self.write_minimal(Path(directory), 512)
            with report.open("wb") as stream:
                stream.truncate(4 * 1024**2 + 1)
            with self.assertRaisesRegex(materializer.SnapshotMaterializationError, "ICON report"):
                materializer.load_verified_icon_snapshot(icon_archive=path, icon_report=report)
        with (patch.object(Path, "is_file", return_value=True),
              patch.object(Path, "stat", return_value=SimpleNamespace(st_size=8)),
              patch.object(Path, "open", return_value=io.BytesIO(b"short"))):
            with self.assertRaisesRegex(materializer.SnapshotMaterializationError, "changed"):
                materializer._read_bounded(Path("never-opened"), 16, "ICON payload")


class FullIconSnapshotLimitRegression(unittest.TestCase):
    def test_enriched_215_by_73_reaches_checkpoint_publication_and_legacy_read(self):
        import run_pilot as pilot
        from test_run_pilot import snapshot_fixture, RUN_TIME
        from test_contract_publisher import MemoryObjectStore
        from local_pipeline.contract_v1 import load_catalog
        from local_pipeline.contract_publisher import ContractV1Publisher
        from local_pipeline.icon_accumulation_sidecar import validate_sidecar
        from local_pipeline.icon_checkpoint import save_checkpoint, read_checkpoint
        from local_pipeline.icon_quality import build_source_quality
        from local_pipeline.job_entrypoints import prepare_icon_publication, execute_icon_job, IconJobInputs
        from local_pipeline.job_outcomes import JobKind
        from local_pipeline.publication_intent import PublicationIntent
        from process_memory import process_memory_bytes

        catalog = load_catalog()
        snapshot = snapshot_fixture()
        snapshot["points"], snapshot["catalog_sha256"] = pilot.load_points()
        snapshot["grid_points"] = [
            dict(lat=p["latitude"], lon=p["longitude"], index=i, distance=.2)
            for i, p in enumerate(snapshot["points"])
        ]
        for field in pilot.ACCUM_FIELDS:
            for meta in snapshot["raw"][field]["metadata"]:
                meta["packingError"] = 0.0005
        # Exercise verified resolution tolerance as well as quantified values.
        for field in ("TOT_PREC", "RAIN_GSP", "SNOW_GSP"):
            for lead, values in enumerate(snapshot["raw"][field]["values"]):
                snapshot["raw"][field]["values"][lead] = [
                    .0001 * lead if i % 3 == 0 else value for i, value in enumerate(values)]
        now = RUN_TIME + timedelta(hours=6)
        payload = pilot.derive(snapshot, now=now)
        quality = build_source_quality(snapshot, payload, source_sha256="d"*64)
        raw = pilot.compact_json(payload)
        # Whitespace raises a smaller fixture to the observed byte count without
        # altering weather semantics; naturally larger fixtures need no padding.
        size_before_padding = len(raw)
        raw += b" " * max(0, OBSERVED_PAYLOAD_BYTES - len(raw))
        self.assertGreater(len(raw), LEGACY_LIMIT)
        self.assertLess(len(raw), materializer.MAX_ICON_JSON_BYTES)
        report = dict(payload_sha256=hashlib.sha256(raw).hexdigest(),
                      catalog_sha256=catalog.sha256, run_utc=payload["run_utc"])
        del snapshot, payload
        gc.collect()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "payload.json"
            report_path = Path(directory) / "report.json"
            path.write_bytes(raw)
            payload_bytes = len(raw)
            report_path.write_text(json.dumps(report))
            del raw
            # This is the real pre-publication entrypoint, not a mock materializer.
            with patch.object(materializer, "MAX_ICON_JSON_BYTES", LEGACY_LIMIT):
                with self.assertRaises(materializer.SnapshotMaterializationError):
                    prepare_icon_publication(payload=path, report=report_path, catalog=catalog)
            prepared = prepare_icon_publication(payload=path, report=report_path, catalog=catalog)
            intent = PublicationIntent(JobKind.ICON, prepared.source_run_id, pilot.iso(now),
                                       prepared.input_fingerprint_sha256)
            state = MemoryObjectStore()
            checkpoint = save_checkpoint(state, slot="20260903-am", prepared=prepared,
                                         intent=intent, catalog=catalog, source_quality=quality)
            restored = read_checkpoint(state, slot="20260903-am", catalog=catalog)
            self.assertEqual(restored.prepared.documents, prepared.documents)
            self.assertEqual(restored.source_quality, quality)
            body = next(iter(state.objects.values())).body
            expanded_bytes = len(gzip.decompress(body))
            self.assertEqual(json.loads(gzip.decompress(body))["schema_version"], 2)
            store = MemoryObjectStore()
            publisher = ContractV1Publisher(store, catalog)
            inputs = IconJobInputs(path, report_path, pilot.iso(now),
                                   source_run_id=restored.intent.source_run_id,
                                   input_fingerprint_sha256=restored.intent.input_fingerprint_sha256,
                                   prepared=restored.prepared)
            result = execute_icon_job(inputs, catalog=catalog, publisher=publisher)
            self.assertEqual(result.status.value, "published", result.as_document())
            self.assertEqual(len(prepared.documents), 215)
            sidecars = 0
            for code, enriched in prepared.documents.items():
                key = publisher.payload_key("icon2i", prepared.source_run_id, code)
                public = store.get(key).body
                side = store.get(key.replace("/municipalities/", "/accumulation-quality/")).body
                validate_sidecar(side, public)
                document = json.loads(public)
                expected = json.loads(enriched)
                for row in expected["hourly"]:
                    row.pop("accumulation_quality")
                self.assertEqual(document, expected)
                self.assertEqual(len(document["hourly"]), 73)
                sidecars += 1
            repeat = execute_icon_job(inputs, catalog=catalog, publisher=publisher)
            self.assertFalse(repeat.metrics["latest_updated"])
            self.assertEqual(restored.sha256, checkpoint.sha256)
            print(json.dumps({
                "regression": "synthetic_full_catalog_not_failed_live_payload",
                "payload_bytes": payload_bytes, "before_padding_bytes": size_before_padding,
                "old_limit_reproduced": True, "municipalities": 215, "hours": 73,
                "checkpoint_schema": 2, "checkpoint_gzip_bytes": len(body),
                "checkpoint_expanded_bytes": expanded_bytes,
                "largest_enriched_document_bytes": max(map(len, prepared.documents.values())),
                "sidecars_verified": sidecars, "repeat_latest_changed": False,
                "tolerance_verified": sum(item["count"] for item in quality["counts"]["accumulation_tolerance"]
                                          if item["state"] == "resolution_tolerance_verified"),
                "memory": process_memory_bytes(), "storage": "memory_only",
            }, sort_keys=True))


if __name__ == "__main__":
    unittest.main()
