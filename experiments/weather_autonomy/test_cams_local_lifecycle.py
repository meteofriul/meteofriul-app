"""Offline end-to-end tests for the durable CAMS lifecycle gate."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone
import gzip
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

import cams_request_plan
import local_pipeline.cams_lifecycle as cams_lifecycle_module
from cams_test_fixtures import valid_plan
from local_pipeline.cams_lifecycle import (
    CAMS_LEASE_DURATION,
    CamsEvidenceError,
    CamsLeaseUnavailable,
    CamsLifecyclePaths,
    advance_cams_lifecycle,
    commit_prepared_cams_lifecycle,
    prepare_cams_lifecycle,
)
from local_pipeline.contract_publisher import ContractV1Publisher, StaleContractRun
from local_pipeline.contract_v1 import (
    CAMS_POLLEN_PROVIDER,
    CAMS_PROVIDER,
    load_catalog,
)
from local_pipeline.contracts import Provider, RunKey, RunState
from local_pipeline.job_entrypoints import classify_job_failure
from local_pipeline.job_outcomes import JobKind, JobStatus
from local_pipeline.sqlite_state import SqliteStateStore
from test_contract_publisher import MemoryObjectStore


ROOT = Path(__file__).resolve().parent
SOURCE_PAYLOAD = ROOT / "cams_fvg_payload_20260903.json"
RUN_DATE = "2026-09-03"
RUN_ID = "20260903T000000Z"
REQUEST_ID = "12345678-1234-1234-1234-123456789abc"
PUBLISHED_AT = "2026-09-04T10:00:00Z"
NOW = datetime(2026, 9, 4, 10, tzinfo=timezone.utc)


def encoded(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def write_json(path, value):
    path.write_bytes(encoded(value))


def make_fixture(directory: Path, catalog):
    artifacts = directory / "cams-fvg-20260903"
    artifacts.mkdir()
    plan = valid_plan(run_date=RUN_DATE)
    plan_raw = cams_request_plan.encode_request_plan(plan)
    plan_hash = hashlib.sha256(plan_raw).hexdigest()
    request = plan["request_groups"][0]["request"]
    request_hash = cams_request_plan.request_sha256(request)
    (artifacts / "request-plan.json").write_bytes(plan_raw)

    points = [
        {
            "slug": town.slug,
            "name": town.name,
            "province": town.province,
            "provinceName": town.province_name,
            "istatCode": town.istat_code,
            "latitude": town.latitude,
            "longitude": town.longitude,
            "coordinateSource": "synthetic_lifecycle_fixture",
        }
        for town in catalog.municipalities
    ]
    write_json(
        artifacts / "request.json",
        {
            "schema_version": 2,
            "dataset": cams_request_plan.DATASET,
            "scope": "fvg",
            "run_date": RUN_DATE,
            "request_plan_sha256": plan_hash,
            "request_sha256": request_hash,
            "request": request,
            "variables": plan["variables"],
            "scope_metadata": {
                "municipalities": points,
                "municipality_count": 215,
                "catalog_sha256": catalog.sha256,
                "coordinate_provenance": "Synthetic exact authoritative catalog fixture",
            },
            "licence": plan["licence"],
        },
    )
    write_json(
        artifacts / "submission-intent.json",
        {
            "schema_version": 2,
            "at_utc": "2026-09-03T12:00:00Z",
            "dataset": cams_request_plan.DATASET,
            "scope": "fvg",
            "run_date": RUN_DATE,
            "request_plan_sha256": plan_hash,
            "request_sha256": request_hash,
            "post_retries": 0,
        },
    )
    write_json(
        artifacts / "job.json",
        {
            "schema_version": 2,
            "dataset": cams_request_plan.DATASET,
            "request_id": REQUEST_ID,
            "scope": "fvg",
            "run_date": RUN_DATE,
            "request_plan_sha256": plan_hash,
            "request_sha256": request_hash,
        },
    )
    grib = b"GRIB-local-lifecycle-fixture-7777"
    grib_hash = hashlib.sha256(grib).hexdigest()
    (artifacts / "source.grib").write_bytes(grib)
    write_json(
        artifacts / "source.grib.complete.json",
        {
            "schema_version": 1,
            "kind": "cams_result_completed_download",
            "target_name": "source.grib",
            "expected_bytes": len(grib),
            "content_type": "application/x-grib",
            "result_host": "object-store.os-api.cci2.ecmwf.int",
            "dataset": cams_request_plan.DATASET,
            "request_id": REQUEST_ID,
            "run_date": RUN_DATE,
            "request_plan_sha256": plan_hash,
            "request_sha256": request_hash,
            "sha256": grib_hash,
        },
    )

    payload = json.loads(SOURCE_PAYLOAD.read_bytes())
    payload["catalog_sha256"] = catalog.sha256
    catalog_by_slug = {town.slug: town for town in catalog.municipalities}
    for municipality in payload["municipalities"]:
        town = catalog_by_slug[municipality["id"]]
        municipality.update(
            name=town.name,
            latitude=town.latitude,
            longitude=town.longitude,
            province=town.province,
        )
    payload["sources"]["grib"] = {
        "filename": "source.grib",
        "bytes": len(grib),
        "sha256": grib_hash,
    }
    payload["request_plan_sha256"] = plan_hash
    payload["request_sha256"] = request_hash
    payload["sources"]["request_plan"] = {
        "sha256": plan_hash,
        "run_date": RUN_DATE,
        "request_sha256": request_hash,
        "metadata_documents": plan["metadata_evidence"]["documents"],
    }
    payload_raw = encoded(payload)
    payload_path = artifacts / "cams-fvg-2026-09-03.json"
    payload_path.write_bytes(payload_raw)
    zipped = gzip.compress(payload_raw, mtime=0)
    report = {
        "schema_version": 1,
        "status": "offline_regional_decode_measurement_not_acquisition",
        "analysis": {"municipalities": 215, "variables": 28, "hourly_instants": 97},
        "input": payload["sources"]["grib"],
        "catalog_sha256": catalog.sha256,
        "run_date": RUN_DATE,
        "request_plan_sha256": plan_hash,
        "request_sha256": request_hash,
        "payload_bytes": len(payload_raw),
        "payload_sha256": hashlib.sha256(payload_raw).hexdigest(),
        "payload_gzip_bytes": len(zipped),
        "payload_gzip_sha256": hashlib.sha256(zipped).hexdigest(),
    }
    report_path = artifacts / "cams-fvg-2026-09-03-report.json"
    write_json(report_path, report)
    return artifacts, payload_path, report_path, request_hash


class CamsLifecycleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog = load_catalog()

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="cams-lifecycle-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        artifacts, payload, report, request_hash = make_fixture(self.root, self.catalog)
        self.paths = CamsLifecyclePaths(artifacts, payload, report)
        self.key = RunKey(Provider.CAMS, RUN_ID, request_hash)
        self.state = SqliteStateStore(self.root / "state.sqlite")
        self.addCleanup(self.state.close)
        self.objects = MemoryObjectStore()
        self.publisher = ContractV1Publisher(self.objects, self.catalog)

    def run_lifecycle(self, **kwargs):
        owner_id = kwargs.pop("owner_id", "test-attempt-one")
        now = kwargs.pop("now", NOW)
        return advance_cams_lifecycle(
            paths=self.paths,
            catalog=self.catalog,
            state_store=self.state,
            publisher=self.publisher,
            owner_id=owner_id,
            published_at=PUBLISHED_AT,
            now=now,
            **kwargs,
        )

    def test_crash_after_core_staging_keeps_both_views_invisible(self):
        def crash(step):
            if step == "CORE_STAGED":
                raise RuntimeError("simulated crash")

        with self.assertRaisesRegex(RuntimeError, "simulated crash"):
            self.run_lifecycle(after_step=crash)
        interrupted = self.state.get(self.key)
        self.assertEqual(RunState.VALIDATED, interrupted.state)
        self.assertEqual(NOW, interrupted.lease_expires_at)
        self.assertIsNone(self.publisher.read_verified_cams_family_latest())
        self.assertIsNone(self.publisher.read_verified_latest(CAMS_PROVIDER))
        self.assertIsNone(self.publisher.read_verified_latest(CAMS_POLLEN_PROVIDER))

        second = self.run_lifecycle(owner_id="test-attempt-two")

        self.assertEqual(second.record.state, RunState.PUBLISHED)
        self.assertEqual(2, second.record.fencing_token)
        self.assertTrue(second.core_stage.idempotent)
        self.assertFalse(second.pollen_stage.idempotent)
        self.assertTrue(second.family_publication.latest_updated)
        self.assertIsNotNone(self.publisher.read_verified_cams_family_latest())
        checkpoint = second.record.checkpoint
        self.assertEqual(215, checkpoint["municipality_count"])
        self.assertEqual(28, checkpoint["variable_count"])
        self.assertEqual(97, checkpoint["hourly_instants"])
        self.assertEqual(215, checkpoint["core_object_count"])
        self.assertEqual(215, checkpoint["pollen_object_count"])
        self.assertEqual(
            [event.to_state for event in self.state.history(self.key)],
            [
                RunState.INTENT,
                RunState.SUBMITTED,
                RunState.READY,
                RunState.DOWNLOADED,
                RunState.VALIDATED,
                RunState.PUBLISHED,
            ],
        )

    def test_prepared_commit_never_reopens_inputs_or_uses_later_mutations(self):
        with mock.patch.object(
            cams_lifecycle_module,
            "_read_bytes",
            wraps=cams_lifecycle_module._read_bytes,
        ) as reader:
            prepared = prepare_cams_lifecycle(paths=self.paths, catalog=self.catalog)

        read_names = [call.args[0].name for call in reader.call_args_list]
        self.assertEqual(1, read_names.count("source.grib"))
        self.assertEqual(1, read_names.count(self.paths.decoded_payload.name))

        forged_hash = "a" * 64
        forged_checkpoint = {
            **prepared.validated_checkpoint,
            "validation_sha256": forged_hash,
        }
        with self.assertRaisesRegex(CamsEvidenceError, "does not bind"):
            replace(
                prepared,
                validation_sha256=forged_hash,
                validated_checkpoint=forged_checkpoint,
            )

        self.paths.decoded_payload.write_bytes(b"mutated after preparation")
        self.paths.decode_report.write_bytes(b"mutated after preparation")
        (self.paths.artifacts_directory / "source.grib").write_bytes(
            b"mutated after preparation"
        )

        with mock.patch.object(
            cams_lifecycle_module,
            "_read_bytes",
            side_effect=AssertionError("commit must not reopen CAMS source paths"),
        ):
            result = commit_prepared_cams_lifecycle(
                prepared=prepared,
                catalog=self.catalog,
                state_store=self.state,
                publisher=self.publisher,
                owner_id="prepared-attempt-one",
                published_at=PUBLISHED_AT,
                now=NOW,
            )

        self.assertEqual(RunState.PUBLISHED, result.record.state)
        self.assertEqual(prepared.validation_sha256, result.validation_sha256)
        self.assertEqual(215, len(result.core_stage.payload_keys))
        self.assertEqual(215, len(result.pollen_stage.payload_keys))
        family = self.publisher.read_verified_cams_family_latest()
        self.assertIsNotNone(family)
        self.assertEqual(RUN_ID, family["latest"]["source_run_id"])

    def test_crash_after_both_stages_keeps_family_invisible_until_retry(self):
        def crash(step):
            if step == "POLLEN_STAGED":
                raise RuntimeError("simulated crash")

        with self.assertRaisesRegex(RuntimeError, "simulated crash"):
            self.run_lifecycle(after_step=crash)

        self.assertEqual(RunState.VALIDATED, self.state.get(self.key).state)
        self.assertIsNone(self.publisher.read_verified_cams_family_latest())
        self.assertIsNone(self.publisher.read_verified_latest(CAMS_PROVIDER))
        self.assertIsNone(self.publisher.read_verified_latest(CAMS_POLLEN_PROVIDER))

        resumed = self.run_lifecycle(owner_id="test-attempt-two")

        self.assertTrue(resumed.core_stage.idempotent)
        self.assertTrue(resumed.pollen_stage.idempotent)
        self.assertTrue(resumed.family_publication.latest_updated)
        self.assertEqual(RunState.PUBLISHED, resumed.record.state)
        self.assertIsNotNone(self.publisher.read_verified_cams_family_latest())

    def test_crash_after_family_release_replays_without_pointer_change(self):
        def crash(step):
            if step == "FAMILY_RELEASED":
                raise RuntimeError("simulated crash")

        with self.assertRaisesRegex(RuntimeError, "simulated crash"):
            self.run_lifecycle(after_step=crash)

        interrupted = self.state.get(self.key)
        self.assertEqual(RunState.VALIDATED, interrupted.state)
        visible = self.publisher.read_verified_cams_family_latest()
        self.assertIsNotNone(visible)
        self.assertEqual(RUN_ID, visible["latest"]["source_run_id"])
        latest_key = self.publisher.cams_family_latest_key()
        first_etag = self.objects.head(latest_key).etag

        resumed = self.run_lifecycle(owner_id="test-attempt-two")

        self.assertEqual(RunState.PUBLISHED, resumed.record.state)
        self.assertTrue(resumed.core_stage.idempotent)
        self.assertTrue(resumed.pollen_stage.idempotent)
        self.assertTrue(resumed.family_publication.idempotent)
        self.assertFalse(resumed.family_publication.latest_updated)
        self.assertEqual(first_etag, self.objects.head(latest_key).etag)

    def test_newer_family_during_post_release_verification_is_safe_no_op(self):
        newer_family = {
            "latest": {
                "source_run_id": "20260904T000000Z",
                "release_sha256": "a" * 64,
            }
        }

        with mock.patch.object(
            self.publisher,
            "read_verified_cams_family_latest",
            return_value=newer_family,
        ):
            with self.assertRaises(StaleContractRun) as caught:
                self.run_lifecycle()

        self.assertEqual(RunState.VALIDATED, self.state.get(self.key).state)
        outcome = classify_job_failure(JobKind.CAMS, caught.exception)
        self.assertIsNotNone(outcome)
        self.assertEqual(JobStatus.NO_OP, outcome.status)
        self.assertEqual("newer_run_already_active", outcome.reason_code)

    def test_newer_family_between_verified_read_and_head_is_safe_no_op(self):
        newer_family = {
            "latest": {
                "source_run_id": "20260904T000000Z",
                "release_sha256": "a" * 64,
            }
        }
        original_read = self.publisher.read_verified_cams_family_latest
        original_head = self.objects.head
        family_latest_key = self.publisher.cams_family_latest_key()
        read_count = 0

        def racing_read():
            nonlocal read_count
            read_count += 1
            if read_count == 1:
                return original_read()
            return newer_family

        def racing_head(key):
            observed = original_head(key)
            if key == family_latest_key and read_count == 1:
                return replace(observed, etag='"newer-family"')
            return observed

        with mock.patch.object(
            self.publisher,
            "read_verified_cams_family_latest",
            side_effect=racing_read,
        ), mock.patch.object(self.objects, "head", side_effect=racing_head):
            with self.assertRaises(StaleContractRun) as caught:
                self.run_lifecycle()

        self.assertEqual(2, read_count)
        self.assertEqual(RunState.VALIDATED, self.state.get(self.key).state)
        outcome = classify_job_failure(JobKind.CAMS, caught.exception)
        self.assertIsNotNone(outcome)
        self.assertEqual(JobStatus.NO_OP, outcome.status)
        self.assertEqual("newer_run_already_active", outcome.reason_code)

    def test_regressed_family_during_post_release_verification_fails_closed(self):
        regressed_family = {
            "latest": {
                "source_run_id": "20260902T000000Z",
                "release_sha256": "a" * 64,
            }
        }

        with mock.patch.object(
            self.publisher,
            "read_verified_cams_family_latest",
            return_value=regressed_family,
        ):
            with self.assertRaisesRegex(CamsEvidenceError, "regressed after release"):
                self.run_lifecycle()

        self.assertEqual(RunState.VALIDATED, self.state.get(self.key).state)

    def test_crash_after_download_resumes_without_repeating_committed_transitions(self):
        def crash(step):
            if step == "DOWNLOADED":
                raise RuntimeError("simulated crash")

        with self.assertRaisesRegex(RuntimeError, "simulated crash"):
            self.run_lifecycle(after_step=crash)
        self.assertEqual(RunState.DOWNLOADED, self.state.get(self.key).state)

        resumed = self.run_lifecycle(owner_id="test-attempt-two")
        self.assertEqual(RunState.PUBLISHED, resumed.record.state)
        self.assertEqual(6, len(self.state.history(self.key)))

    def test_live_lease_reports_its_remaining_crash_bound(self):
        claim = self.state.claim(
            self.key,
            owner_id="hard-killed-attempt",
            lease_for=CAMS_LEASE_DURATION,
            now=NOW,
        )
        self.assertTrue(claim.acquired)

        with self.assertRaises(CamsLeaseUnavailable) as caught:
            self.run_lifecycle(
                owner_id="replacement-attempt",
                now=NOW + timedelta(minutes=2, seconds=1),
            )

        self.assertEqual(13 * 60 - 1, caught.exception.retry_after_seconds)
        self.assertEqual("hard-killed-attempt", self.state.get(self.key).owner_id)

    def test_payload_tamper_fails_before_state_or_public_objects(self):
        raw = self.paths.decoded_payload.read_bytes()
        self.paths.decoded_payload.write_bytes(raw[:-1] + b" ")
        with self.assertRaisesRegex(CamsEvidenceError, "payload|decode report"):
            self.run_lifecycle()
        self.assertIsNone(self.state.get(self.key))
        self.assertEqual([], self.objects.list_keys())

    def test_incomplete_matrix_cannot_create_state_or_publish(self):
        payload = json.loads(self.paths.decoded_payload.read_bytes())
        payload["times_utc"] = payload["times_utc"][:-1]
        for cell in payload["cells"]:
            for collection in (cell["values"], cell["raw_values"]):
                for variable in collection:
                    collection[variable] = collection[variable][:-1]
        payload_raw = encoded(payload)
        self.paths.decoded_payload.write_bytes(payload_raw)
        report = json.loads(self.paths.decode_report.read_bytes())
        zipped = gzip.compress(payload_raw, mtime=0)
        report["analysis"]["hourly_instants"] = 96
        report["payload_bytes"] = len(payload_raw)
        report["payload_sha256"] = hashlib.sha256(payload_raw).hexdigest()
        report["payload_gzip_bytes"] = len(zipped)
        report["payload_gzip_sha256"] = hashlib.sha256(zipped).hexdigest()
        write_json(self.paths.decode_report, report)

        with self.assertRaisesRegex(CamsEvidenceError, "97 hourly|215x28x97"):
            self.run_lifecycle()
        self.assertIsNone(self.state.get(self.key))
        self.assertEqual([], self.objects.list_keys())

    def test_changed_job_after_durable_submission_is_rejected_on_resume(self):
        def crash(step):
            if step == "SUBMITTED":
                raise RuntimeError("simulated crash")

        with self.assertRaises(RuntimeError):
            self.run_lifecycle(after_step=crash)
        job_path = self.paths.artifacts_directory / "job.json"
        job = json.loads(job_path.read_bytes())
        job["request_id"] = "00000000-0000-0000-0000-000000000000"
        write_json(job_path, job)
        completion_path = self.paths.artifacts_directory / "source.grib.complete.json"
        completion = json.loads(completion_path.read_bytes())
        completion["request_id"] = job["request_id"]
        write_json(completion_path, completion)

        with self.assertRaisesRegex(CamsEvidenceError, "Durable CAMS state differs"):
            self.run_lifecycle()
        self.assertEqual(RunState.SUBMITTED, self.state.get(self.key).state)


if __name__ == "__main__":
    unittest.main()
