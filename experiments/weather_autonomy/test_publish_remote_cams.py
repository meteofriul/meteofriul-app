"""Credential-free integration of acquisition and decoded restart checkpoints."""
import base64
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest import TestCase, main
from unittest.mock import Mock, patch

from cams_test_fixtures import valid_plan
from cams_request_plan import DATASET, encode_request_plan
from retrieve_cams import _preflight_plan, _request_record, PilotError
from retrieve_remote_cams import FILES, remote_cams_context, retrieve_remote_cams
from publish_remote_cams import (restore_remote_cams_decoded, save_remote_cams_decoded, publish_remote_cams,
                                save_remote_cams_prepared, restore_remote_cams_prepared)
from local_pipeline.cams_artifact_checkpoint import CamsArtifactError, save_artifacts
from local_pipeline.cams_lifecycle import CamsLifecyclePaths, PreparedCamsRun
from local_pipeline.contract_v1 import load_catalog, canonical_json_bytes
from local_pipeline.contracts import RunKey, Provider
from local_pipeline.sqlite_object_store import ObjectNotFound
from test_contract_publisher import MemoryObjectStore
import test_contract_publisher as contract_fixtures


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def submission_fixture(root):
    directory = root / "cams-2026-09-03"
    directory.mkdir()
    plan_path = directory / "request-plan.json"
    plan_path.write_bytes(encode_request_plan(valid_plan(run_date="2026-09-03")))
    plan, _, plan_hash, scope = _preflight_plan(plan_path, "fvg")
    request = _request_record(plan, plan_hash, "fvg", scope)
    identity = {"dataset": DATASET, "request_id": "12345678-1234-1234-1234-123456789abc",
                "run_date": plan["run_date"], "request_plan_sha256": plan_hash,
                "request_sha256": request["request_sha256"]}
    (directory / "request.json").write_bytes(encoded(request))
    (directory / "submission-intent.json").write_bytes(encoded({
        "schema_version": 2, "at_utc": "2026-09-03T12:00:00Z", "scope": "fvg", "post_retries": 0,
        **{key: value for key, value in identity.items() if key != "request_id"},
    }))
    (directory / "job.json").write_bytes(encoded({"schema_version": 2, "scope": "fvg", **identity}))
    grib = b"GRIB-synthetic-completed-file-7777"
    (directory / "source.grib").write_bytes(grib)
    (directory / "source.grib.complete.json").write_bytes(encoded({
        "schema_version": 1, "kind": "cams_result_completed_download", "target_name": "source.grib",
        "expected_bytes": len(grib), "content_type": "application/x-grib",
        "result_host": "object-store.os-api.cci2.ecmwf.int", **identity,
        "sha256": hashlib.sha256(grib).hexdigest(),
    }))
    (directory / "decoded.json").write_bytes(b'{"synthetic":"decoded"}')
    (directory / "decode-report.json").write_bytes(b'{"synthetic":"report"}')
    return CamsLifecyclePaths(directory, directory / "decoded.json", directory / "decode-report.json")


class RemoteCamsArtifactIntegrationTests(TestCase):
    def setUp(self):
        self.temporary = TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.paths = submission_fixture(self.root)
        self.directory = self.paths.artifacts_directory
        self.store = MemoryObjectStore()
        self.catalog = load_catalog()
        self.prefix, self.identity = remote_cams_context(self.directory)

    def prepared_fixture(self):
        prepared = Mock(spec=PreparedCamsRun)
        prepared.catalog_sha256 = self.catalog.sha256
        prepared.key = SimpleNamespace(request_hash=self.identity["request_sha256"], source_run_id="20260903T000000Z")
        prepared.validation_sha256 = "a" * 64
        prepared.submitted_checkpoint = self.identity
        prepared.downloaded_checkpoint = {
            "artifact_sha256": hashlib.sha256((self.directory / "source.grib").read_bytes()).hexdigest(),
        }
        prepared.validated_checkpoint = {
            "payload_sha256": hashlib.sha256(self.paths.decoded_payload.read_bytes()).hexdigest(),
            "payload_bytes": self.paths.decoded_payload.stat().st_size,
            "decode_report_sha256": hashlib.sha256(self.paths.decode_report.read_bytes()).hexdigest(),
        }
        return prepared

    def checkpoint_download(self):
        files = {name: base64.b64encode((self.directory / name).read_bytes()).decode()
                 for name in FILES + ("job.json",)}
        self.store.put(self.prefix + "submitted.json", encoded(files), content_type="application/json")
        save_artifacts(self.store, prefix=self.prefix, stage="download", identity=self.identity, files={
            name: (self.directory / name).read_bytes() for name in ("source.grib", "source.grib.complete.json")})

    def test_completed_download_restores_and_actual_retrieve_uses_no_credentials_or_ads(self):
        self.checkpoint_download()
        scratch = self.root / "fresh"
        scratch.mkdir()
        with patch("retrieve_cams.load_credentials", side_effect=AssertionError("no credential access")) as credentials, \
             patch("retrieve_cams.download_result", side_effect=AssertionError("no second download")) as download, \
             patch("retrieve_cams.importlib.metadata.version", return_value="0.5.3"):
            result = retrieve_remote_cams(credentials_path="must-not-be-read",
                request_plan_path=self.directory / "request-plan.json", scratch=scratch, state_store=self.store)
        self.assertEqual(result["status"], "downloaded_pending_decode_validation")
        credentials.assert_not_called()
        download.assert_not_called()
        self.assertEqual((scratch / self.directory.name / "source.grib").read_bytes(),
                         (self.directory / "source.grib").read_bytes())

    def test_saved_job_request_mismatch_never_reaches_retrieve(self):
        self.checkpoint_download()
        scratch = self.root / "fresh"
        scratch.mkdir()
        original_get = self.store.get
        def mismatched(key):
            stored = original_get(key)
            if key == self.prefix + "submitted.json":
                from dataclasses import replace
                record = json.loads(stored.body)
                job = json.loads(base64.b64decode(record["job.json"]))
                job["request_sha256"] = "f" * 64
                record["job.json"] = base64.b64encode(encoded(job)).decode()
                return replace(stored, body=encoded(record))
            return stored
        fn = Mock()
        with patch.object(self.store, "get", side_effect=mismatched), self.assertRaises(PilotError):
            retrieve_remote_cams(credentials_path="unused", request_plan_path=self.directory / "request-plan.json",
                scratch=scratch, state_store=self.store, retrieve_fn=fn)
        fn.assert_not_called()

    def test_decoded_restart_restores_exact_bytes_and_still_requires_full_validation(self):
        prepared = self.prepared_fixture()
        with patch("publish_remote_cams.prepare_cams_lifecycle", return_value=prepared) as validate:
            self.assertIs(save_remote_cams_decoded(paths=self.paths, state_store=self.store), prepared)
        validate.assert_called_once()
        restored = CamsLifecyclePaths(self.directory, self.directory / "restored-decoded.json",
                                     self.directory / "restored-report.json")
        with patch("publish_remote_cams.prepare_cams_lifecycle", side_effect=AssertionError("restore is not decode")):
            self.assertTrue(restore_remote_cams_decoded(paths=restored, state_store=self.store))
        self.assertEqual(restored.decoded_payload.read_bytes(), self.paths.decoded_payload.read_bytes())
        self.assertEqual(restored.decode_report.read_bytes(), self.paths.decode_report.read_bytes())
        with patch("publish_remote_cams.prepare_cams_lifecycle", return_value=prepared) as revalidate:
            self.assertIs(save_remote_cams_decoded(paths=restored, state_store=self.store), prepared)
        revalidate.assert_called_once_with(paths=restored, catalog=self.catalog)

    def test_missing_decoded_checkpoint_returns_false_without_decoding_or_publishing(self):
        with patch("publish_remote_cams.prepare_cams_lifecycle") as validate, \
             patch("publish_remote_cams.commit_prepared_cams_lifecycle") as commit:
            self.assertFalse(restore_remote_cams_decoded(paths=self.paths, state_store=self.store))
        validate.assert_not_called()
        commit.assert_not_called()

    def test_validation_failure_never_advertises_decoded_checkpoint(self):
        with patch("publish_remote_cams.prepare_cams_lifecycle", side_effect=ValueError("invalid schema")):
            with self.assertRaises(ValueError):
                save_remote_cams_decoded(paths=self.paths, state_store=self.store)
        with self.assertRaises(ObjectNotFound):
            self.store.get(self.prefix + "artifacts/decoded.json")

    def test_bytes_changed_after_validation_never_create_checkpoint(self):
        prepared = self.prepared_fixture()
        def changed(**kwargs):
            self.paths.decoded_payload.write_bytes(b"changed")
            return prepared
        with patch("publish_remote_cams.prepare_cams_lifecycle", side_effect=changed), \
             self.assertRaisesRegex(CamsArtifactError, "after validation"):
            save_remote_cams_decoded(paths=self.paths, state_store=self.store)
        with self.assertRaises(ObjectNotFound):
            self.store.get(self.prefix + "artifacts/decoded.json")

    def test_prepared_publication_reuses_gate_without_redecode_or_reopening_sources(self):
        prepared = self.prepared_fixture()
        with patch("publish_remote_cams.save_remote_cams_decoded", side_effect=AssertionError("already prepared")), \
             patch("publish_remote_cams.commit_prepared_cams_lifecycle", return_value="atomic-family") as commit:
            result = publish_remote_cams(paths=self.paths, published_at="2026-09-04T10:00:00Z",
                state_store=self.store, data_store=MemoryObjectStore(), prepared=prepared)
        self.assertEqual(result, "atomic-family")
        self.assertIs(commit.call_args.kwargs["prepared"], prepared)

    def test_changed_download_prevents_decoded_restore(self):
        with patch("publish_remote_cams.prepare_cams_lifecycle", return_value=self.prepared_fixture()):
            save_remote_cams_decoded(paths=self.paths, state_store=self.store)
        (self.directory / "source.grib").write_bytes(b"modified")
        with self.assertRaises(PilotError):
            restore_remote_cams_decoded(paths=self.paths, state_store=self.store)

    def test_materialized_restart_reuses_all_430_real_contract_documents_without_processing(self):
        contract_fixtures.ContractPublisherTests.setUpClass()
        run = datetime(2026, 9, 3, tzinfo=timezone.utc)
        core, core_manifest = contract_fixtures.ContractPublisherTests.cams_bundle(run)
        pollen, pollen_manifest = contract_fixtures.ContractPublisherTests.cams_pollen_bundle(run)
        prototype = self.prepared_fixture()
        core_raw, pollen_raw = canonical_json_bytes(core_manifest), canonical_json_bytes(pollen_manifest)
        core_hash, pollen_hash = hashlib.sha256(core_raw).hexdigest(), hashlib.sha256(pollen_raw).hexdigest()
        attestation = {'schema_version': 1, 'kind': 'cams_local_validation_attestation',
            'source_run_id': '20260903T000000Z', 'request_sha256': self.identity['request_sha256'],
            'request_plan_sha256': self.identity['request_plan_sha256'], 'catalog_sha256': self.catalog.sha256,
            'artifact_sha256': prototype.downloaded_checkpoint['artifact_sha256'],
            'payload_sha256': prototype.validated_checkpoint['payload_sha256'],
            'decode_report_sha256': prototype.validated_checkpoint['decode_report_sha256'],
            'municipality_count': 215, 'variable_count': 28, 'hourly_instants': 97,
            'core_manifest_sha256': core_hash, 'pollen_manifest_sha256': pollen_hash}
        validation_hash = hashlib.sha256(canonical_json_bytes(attestation)).hexdigest()
        prepared = PreparedCamsRun(key=RunKey(Provider.CAMS, '20260903T000000Z', self.identity['request_sha256']),
            catalog_sha256=self.catalog.sha256,
            submitted_checkpoint={**self.identity, 'catalog_sha256': self.catalog.sha256},
            ready_checkpoint={}, downloaded_checkpoint=prototype.downloaded_checkpoint,
            validated_checkpoint={**prototype.validated_checkpoint, 'municipality_count': 215,
                                  'variable_count': 28, 'hourly_instants': 97, 'validation_sha256': validation_hash},
            validation_sha256=validation_hash, core_documents=core, core_manifest_bytes=core_raw,
            core_manifest_sha256=core_hash, pollen_documents=pollen, pollen_manifest_bytes=pollen_raw,
            pollen_manifest_sha256=pollen_hash)
        save_remote_cams_prepared(paths=self.paths, state_store=self.store, prepared=prepared)
        with patch('publish_remote_cams.prepare_cams_lifecycle', side_effect=AssertionError('must not recompute')):
            restored = restore_remote_cams_prepared(paths=self.paths, state_store=self.store)
        self.assertEqual(dict(restored.core_documents), core)
        self.assertEqual(dict(restored.pollen_documents), pollen)
        self.assertEqual(restored.validation_sha256, validation_hash)


if __name__ == "__main__":
    main()
