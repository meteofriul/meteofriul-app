"""Offline fault injection for bounded private CAMS restart artifacts."""
from dataclasses import replace
import hashlib
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase, main
from unittest.mock import patch

from cams_request_plan import DATASET
from local_pipeline import cams_artifact_checkpoint as checkpoint
from local_pipeline.sqlite_object_store import ObjectNotFound
from test_contract_publisher import MemoryObjectStore


class ArtifactCheckpointTests(TestCase):
    def setUp(self):
        self.store = MemoryObjectStore()
        self.identity = {"dataset": DATASET, "request_id": "12345678-1234-1234-1234-123456789abc",
                         "run_date": "2026-09-03", "request_plan_sha256": "a" * 64,
                         "request_sha256": "b" * 64}
        self.prefix = "state/ads/2026-09-03/" + "b" * 64 + "/"
        self.files = {"source.grib": b"GRIB-data-7777", "source.grib.complete.json": b'{"complete":true}'}

    def save(self, **kwargs):
        checkpoint.save_artifacts(self.store, prefix=self.prefix, stage="download",
                                  identity=self.identity, files=self.files, **kwargs)

    def read(self, **kwargs):
        return checkpoint.read_artifacts(self.store, prefix=self.prefix, stage="download",
                                         identity=self.identity, **kwargs)

    def test_chunks_are_bounded_and_descriptor_is_committed_last(self):
        original_put = self.store.put
        writes = []
        def record(key, body, **kwargs):
            writes.append((key, len(body)))
            return original_put(key, body, **kwargs)
        with patch.object(checkpoint, "CHUNK_BYTES", 8), patch.object(self.store, "put", side_effect=record):
            self.save()
            self.assertEqual(self.read(), self.files)
        self.assertTrue(writes[-1][0].endswith("artifacts/download.json"))
        self.assertTrue(all(size <= 8 for _, size in writes[:-1]))

    def test_repeat_is_idempotent(self):
        self.save()
        before = self.store.get(self.prefix + "artifacts/download.json")
        self.save()
        self.assertEqual(self.read(), self.files)
        self.assertEqual(before.etag, self.store.get(before.key).etag)

    def test_lost_create_responses_are_verified_for_chunks_and_descriptor(self):
        original_put = self.store.put
        def lost(key, body, **kwargs):
            original_put(key, body, **kwargs)
            raise TimeoutError("response lost")
        with patch.object(self.store, "put", side_effect=lost):
            self.save()
        self.assertEqual(self.read(), self.files)

    def test_failed_chunk_upload_does_not_advertise_completed_download(self):
        original_put = self.store.put
        def fail(key, body, **kwargs):
            if body == self.files["source.grib"]:
                raise TimeoutError("transport failed")
            return original_put(key, body, **kwargs)
        with patch.object(self.store, "put", side_effect=fail):
            with self.assertRaises(TimeoutError):
                self.save()
        self.assertIsNone(self.read())

    def test_missing_referenced_chunk_is_not_treated_as_a_cache_miss(self):
        self.save()
        original_get = self.store.get
        def missing(key):
            if key.endswith(hashlib.sha256(self.files["source.grib"]).hexdigest() + ".bin"):
                raise ObjectNotFound(key)
            return original_get(key)
        with patch.object(self.store, "get", side_effect=missing):
            with self.assertRaisesRegex(checkpoint.CamsArtifactError, "incomplete"):
                self.read()

    def test_corrupt_chunk_fails_hash_even_if_storage_metadata_is_recomputed(self):
        self.save()
        original_get = self.store.get
        def corrupt(key):
            stored = original_get(key)
            if key.endswith(".bin"):
                body = b"X" * len(stored.body)
                return replace(stored, body=body, head=replace(stored.head, sha256=hashlib.sha256(body).hexdigest()))
            return stored
        with patch.object(self.store, "get", side_effect=corrupt):
            with self.assertRaisesRegex(checkpoint.CamsArtifactError, "chunk hash"):
                self.read()

    def test_changed_job_identity_never_restores_another_submission(self):
        self.save()
        self.identity["request_id"] = "22345678-1234-1234-1234-123456789abc"
        with self.assertRaisesRegex(checkpoint.CamsArtifactError, "descriptor"):
            self.read()

    def test_changed_plan_identity_never_restores_another_plan(self):
        self.save()
        self.identity["request_plan_sha256"] = "c" * 64
        with self.assertRaises(checkpoint.CamsArtifactError):
            self.read()

    def test_different_immutable_download_does_not_replace_original(self):
        self.save()
        original = dict(self.files)
        self.files["source.grib"] = b"OTHER"
        with self.assertRaises(checkpoint.CamsArtifactError):
            self.save()
        self.assertEqual(self.read(), original)

    def test_extra_file_is_rejected_before_any_write(self):
        self.files["credentials.txt"] = b"never persisted"
        with patch.object(self.store, "put") as put:
            with self.assertRaises(checkpoint.CamsArtifactError):
                self.save()
            put.assert_not_called()

    def test_source_and_catalog_bind_decoded_stage(self):
        files = {"decoded.json": b"{}", "decode-report.json": b"{}"}
        bindings = {"source_sha256": "c" * 64, "catalog_sha256": "d" * 64}
        checkpoint.save_artifacts(self.store, prefix=self.prefix, stage="decoded",
                                  identity=self.identity, files=files, bindings=bindings)
        bindings["source_sha256"] = "e" * 64
        with self.assertRaises(checkpoint.CamsArtifactError):
            checkpoint.read_artifacts(self.store, prefix=self.prefix, stage="decoded",
                                      identity=self.identity, bindings=bindings)

    def test_local_restore_never_overwrites_existing_different_bytes(self):
        with TemporaryDirectory() as directory:
            target = Path(directory) / "source.grib"
            checkpoint.restore_local_file(target, b"original")
            with self.assertRaises(checkpoint.CamsArtifactError):
                checkpoint.restore_local_file(target, b"changed!")
            self.assertEqual(target.read_bytes(), b"original")


if __name__ == "__main__":
    main()
