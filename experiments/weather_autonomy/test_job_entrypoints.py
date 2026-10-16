"""Fast, offline tests for the provider-isolated job application layer."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sqlite3
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

from local_pipeline.cams_lifecycle import CamsEvidenceError, CamsLeaseUnavailable
from local_pipeline.contract_publisher import StaleContractRun
from local_pipeline.contract_v1 import (
    CAMS_POLLEN_PROVIDER,
    CAMS_PROVIDER,
    ICON_PROVIDER,
    load_catalog,
)
from local_pipeline.job_entrypoints import (
    CamsJobInputs,
    IconJobInputs,
    InvalidJobInputs,
    PreparedIconPublication,
    classify_job_failure,
    execute_cams_job,
    execute_icon_job,
    execute_icon_recovery,
)
from local_pipeline.job_outcomes import JobKind, JobResult, JobStatus
from local_pipeline.contracts import LeaseLost, RunState
from local_pipeline.gcs_object_store import RemoteObjectStoreError
from local_pipeline.publication_intent import (
    InvalidPublicationIntent,
    PublicationInputError,
    PublicationIntentConflict,
    PublicationIntentCorruption,
    fingerprint_input_files,
    PublicationIntent,
)


RUN_ID = "20260904T000000Z"
PUBLISHED_AT = "2026-09-04T01:23:45Z"


def publication(provider, *, updated=True, idempotent=False, superseded=False):
    return SimpleNamespace(
        provider=provider,
        source_run_id=RUN_ID,
        payload_keys=(f"{provider}/one", f"{provider}/two"),
        manifest_key=f"{provider}/manifest",
        latest_key=f"{provider}/latest",
        latest_etag=f"etag:{provider}",
        reused_payload_count=2 if idempotent else 0,
        manifest_reused=idempotent,
        idempotent=idempotent,
        latest_updated=updated,
        superseded=superseded,
    )


def stage(provider, *, idempotent=False):
    return SimpleNamespace(
        provider=provider,
        source_run_id=RUN_ID,
        payload_keys=(f"{provider}/one", f"{provider}/two"),
        manifest_key=f"{provider}/manifest",
        idempotent=idempotent,
    )


def family_publication(*, updated=True, idempotent=False, superseded=False):
    return SimpleNamespace(
        source_run_id=RUN_ID,
        latest_updated=updated,
        idempotent=idempotent,
        superseded=superseded,
    )


class FakePublisher:
    def __init__(self, result=None, error=None):
        self.result = result
        self.error = error
        self.calls = []

    def publish_run(self, provider, documents, manifest, *, published_at):
        self.calls.append((provider, documents, manifest, published_at))
        if self.error is not None:
            raise self.error
        return self.result


class JobResultTests(unittest.TestCase):
    def test_classified_remote_failure_keeps_run_http_operation_and_safe_cause(self):
        error = RemoteObjectStoreError(
            "storage service temporarily unavailable", original_type="ServiceUnavailable",
            http_status=503, operation="upload", retryable=True,
            object_key="weather/v1/icon2i/runs/20260908T000000Z/municipalities/093033.json",
        )
        result = classify_job_failure(JobKind.ICON, error)
        self.assertEqual(result.status, JobStatus.RETRYABLE_FAILURE)
        self.assertEqual(result.reason_code, "remote_storage_temporary_failure")
        self.assertEqual(result.source_run_id, "20260908T000000Z")
        self.assertEqual(result.metrics["http_status"], 503)
        self.assertEqual(result.metrics["cause_type"], "ServiceUnavailable")
        self.assertEqual(result.metrics["municipality_code"], "093033")

    def test_known_failed_run_is_preserved_but_unsafe_identifier_is_not_logged(self):
        result = classify_job_failure(JobKind.ICON, LeaseLost("lease expired during remote state commit"),
                                      source_run_id=RUN_ID)
        self.assertEqual(result.source_run_id, RUN_ID)
        self.assertEqual(result.metrics["error_summary"], "lease expired during remote state commit")
        unsafe = classify_job_failure(JobKind.ICON, LeaseLost("secret"), source_run_id="secret?token=secret")
        self.assertIsNone(unsafe.source_run_id)
        self.assertNotIn("secret", json.dumps(unsafe.as_document()))

    def test_result_envelope_and_exit_codes_are_stable(self):
        result = JobResult(
            job=JobKind.ICON,
            status=JobStatus.PUBLISHED,
            reason_code="publication_committed",
            source_run_id=RUN_ID,
            published_providers=(ICON_PROVIDER,),
            metrics={"payload_count": 215},
        )
        self.assertEqual(0, result.exit_code)
        self.assertFalse(result.retryable)
        self.assertEqual(
            {
                "schema_version": 1,
                "kind": "meteofriul.weather.job_result",
                "job": "icon",
                "status": "published",
                "reason_code": "publication_committed",
                "retryable": False,
                "source_run_id": RUN_ID,
                "published_providers": [ICON_PROVIDER],
                "retry_after_seconds": None,
                "metrics": {"payload_count": 215},
            },
            result.as_document(),
        )
        retry = JobResult(
            job=JobKind.CAMS,
            status=JobStatus.RETRYABLE_FAILURE,
            reason_code="temporary_state_or_storage_failure",
        )
        self.assertEqual(75, retry.exit_code)
        self.assertTrue(retry.retryable)

    def test_invalid_or_misleading_results_fail_closed(self):
        with self.assertRaises(ValueError):
            JobResult(
                job=JobKind.ICON,
                status=JobStatus.PUBLISHED,
                reason_code="publication_committed",
            )
        with self.assertRaises(ValueError):
            JobResult(
                job=JobKind.CAMS,
                status=JobStatus.MANUAL_REVIEW,
                reason_code="review",
                published_providers=(CAMS_PROVIDER,),
            )
        with self.assertRaises(ValueError):
            JobResult(
                job=JobKind.ICON,
                status=JobStatus.NO_OP,
                reason_code="contains-secret?",
            )
        with self.assertRaises(ValueError):
            JobResult(
                job=JobKind.ICON,
                status=JobStatus.PUBLISHED,
                reason_code="publication_committed",
                source_run_id=RUN_ID,
                published_providers=(CAMS_PROVIDER, CAMS_POLLEN_PROVIDER),
            )

    def test_publication_intent_and_local_io_failures_are_secret_free(self):
        cases = (
            (
                InvalidPublicationIntent("secret"),
                JobStatus.PERMANENT_FAILURE,
                "invalid_publication_intent_configuration",
            ),
            (
                PublicationInputError("secret"),
                JobStatus.MANUAL_REVIEW,
                "publication_intent_verification_failed",
            ),
            (
                PublicationIntentConflict("secret"),
                JobStatus.MANUAL_REVIEW,
                "publication_intent_verification_failed",
            ),
            (
                PublicationIntentCorruption("secret"),
                JobStatus.MANUAL_REVIEW,
                "publication_intent_verification_failed",
            ),
            (
                PermissionError("secret"),
                JobStatus.MANUAL_REVIEW,
                "local_storage_failure",
            ),
        )
        for error, status, reason in cases:
            with self.subTest(error=type(error).__name__):
                result = classify_job_failure(JobKind.ICON, error)
                self.assertIsNotNone(result)
                self.assertEqual(status, result.status)
                self.assertEqual(reason, result.reason_code)
                self.assertNotIn("secret", str(result.as_document()))


class IconEntrypointTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog = load_catalog()

    def inputs(self):
        return IconJobInputs(Path("icon.zip"), Path("icon-report.json"), PUBLISHED_AT)

    def test_recovery_uses_only_existing_publication_with_frozen_identity(self):
        intent = PublicationIntent(JobKind.ICON, RUN_ID, PUBLISHED_AT, 'a' * 64)
        publisher = mock.Mock()
        publisher.publish_existing_run.return_value = publication(ICON_PROVIDER, idempotent=True)
        result = execute_icon_recovery(intent=intent, publisher=publisher)
        self.assertEqual(result.status, JobStatus.PUBLISHED)
        publisher.publish_existing_run.assert_called_once_with(ICON_PROVIDER, RUN_ID,
            expected_manifest_sha256='a' * 64, published_at=PUBLISHED_AT)
        publisher.publish_run.assert_not_called()

    def test_recovery_preserves_retry_classification_and_run(self):
        intent = PublicationIntent(JobKind.ICON, RUN_ID, PUBLISHED_AT, 'a' * 64)
        publisher = mock.Mock()
        publisher.publish_existing_run.side_effect = RemoteObjectStoreError(
            'storage service temporarily unavailable', original_type='ServiceUnavailable', http_status=503,
            operation='download', retryable=True)
        result = execute_icon_recovery(intent=intent, publisher=publisher)
        self.assertTrue(result.retryable)
        self.assertEqual(result.source_run_id, RUN_ID)
        self.assertEqual(result.metrics['http_status'], 503)

    def test_recovery_refuses_cams_without_touching_publisher(self):
        publisher = mock.Mock()
        result = execute_icon_recovery(intent=PublicationIntent(JobKind.CAMS, RUN_ID, PUBLISHED_AT, 'a' * 64),
                                       publisher=publisher)
        self.assertEqual(result.status, JobStatus.PERMANENT_FAILURE)
        self.assertFalse(publisher.mock_calls)

    def materializer(self, calls, error=None):
        def materialize(**kwargs):
            calls.append(kwargs)
            if error is not None:
                raise error
            return {
                "catalog": self.catalog,
                "icon": {
                    "documents": {"fixture": b"icon"},
                    "manifest": {"provider": ICON_PROVIDER, "source_run_id": RUN_ID},
                },
            }

        return materialize

    def test_icon_job_publishes_only_icon(self):
        materializer_calls = []
        publisher = FakePublisher(publication(ICON_PROVIDER))
        result = execute_icon_job(
            self.inputs(),
            catalog=self.catalog,
            publisher=publisher,
            materializer=self.materializer(materializer_calls),
        )
        self.assertEqual(JobStatus.PUBLISHED, result.status)
        self.assertEqual((ICON_PROVIDER,), result.published_providers)
        self.assertEqual(ICON_PROVIDER, publisher.calls[0][0])
        self.assertEqual(PUBLISHED_AT, publisher.calls[0][3])
        self.assertEqual(Path("icon.zip"), materializer_calls[0]["icon_archive"])
        self.assertNotIn("cams_payload", materializer_calls[0])

    def test_icon_replay_and_old_run_are_successful_no_ops(self):
        for publisher, expected_reason in (
            (
                FakePublisher(publication(ICON_PROVIDER, updated=False, idempotent=True)),
                "run_already_published",
            ),
            (
                FakePublisher(
                    publication(ICON_PROVIDER, updated=True, superseded=True)
                ),
                "newer_run_already_active",
            ),
            (FakePublisher(error=StaleContractRun("old")), "newer_run_already_active"),
        ):
            with self.subTest(reason=expected_reason):
                result = execute_icon_job(
                    self.inputs(),
                    catalog=self.catalog,
                    publisher=publisher,
                    materializer=self.materializer([]),
                )
                self.assertEqual(JobStatus.NO_OP, result.status)
                self.assertEqual(expected_reason, result.reason_code)
                self.assertEqual(0, result.exit_code)

    def test_ambiguous_sqlite_failure_requires_review_without_leaking_messages(self):
        secret = "token-never-log"
        result = execute_icon_job(
            self.inputs(),
            catalog=self.catalog,
            publisher=FakePublisher(),
            materializer=self.materializer([], sqlite3.OperationalError(secret)),
        )
        self.assertEqual(JobStatus.MANUAL_REVIEW, result.status)
        self.assertEqual(2, result.exit_code)
        self.assertNotIn(secret, str(result.as_document()))

    def test_wrong_icon_provider_requires_review(self):
        result = execute_icon_job(
            self.inputs(),
            catalog=self.catalog,
            publisher=FakePublisher(publication(CAMS_PROVIDER)),
            materializer=self.materializer([]),
        )
        self.assertEqual(JobStatus.MANUAL_REVIEW, result.status)

    def test_unknown_programming_failure_is_not_hidden(self):
        with self.assertRaisesRegex(RuntimeError, "unexpected defect"):
            execute_icon_job(
                self.inputs(),
                catalog=self.catalog,
                publisher=FakePublisher(),
                materializer=self.materializer([], RuntimeError("unexpected defect")),
            )

    def test_icon_publish_gate_rejects_changed_bytes_or_wrong_run(self):
        with tempfile.TemporaryDirectory(prefix="icon-publish-gate-") as directory:
            root = Path(directory)
            payload = root / "payload.json"
            report = root / "report.json"
            payload.write_bytes(b'{"payload":1}')
            report.write_bytes(b'{"report":1}')
            fingerprint = fingerprint_input_files(
                {"payload": payload, "report": report}
            )

            for manifest_run, mutate in (
                (RUN_ID, True),
                ("20260903T000000Z", False),
            ):
                with self.subTest(manifest_run=manifest_run, mutate=mutate):
                    payload.write_bytes(b'{"payload":1}')
                    publisher = FakePublisher(publication(ICON_PROVIDER))

                    def materializer(**_kwargs):
                        if mutate:
                            payload.write_bytes(b'{"payload":2}')
                        return {
                            "catalog": self.catalog,
                            "icon": {
                                "documents": {"fixture": b"icon"},
                                "manifest": {
                                    "provider": ICON_PROVIDER,
                                    "source_run_id": manifest_run,
                                },
                            },
                        }

                    result = execute_icon_job(
                        IconJobInputs(
                            payload,
                            report,
                            PUBLISHED_AT,
                            source_run_id=RUN_ID,
                            input_fingerprint_sha256=fingerprint,
                        ),
                        catalog=self.catalog,
                        publisher=publisher,
                        materializer=materializer,
                    )
                    self.assertEqual(JobStatus.MANUAL_REVIEW, result.status)
                    self.assertEqual([], publisher.calls)

    def test_prepared_icon_commit_never_reopens_source_paths(self):
        manifest_bytes = json.dumps(
            {"provider": ICON_PROVIDER, "source_run_id": RUN_ID},
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        fingerprint = hashlib.sha256(manifest_bytes).hexdigest()
        prepared = PreparedIconPublication(
            source_run_id=RUN_ID,
            input_fingerprint_sha256=fingerprint,
            documents={"fixture": b"icon"},
            manifest_bytes=manifest_bytes,
        )
        publisher = FakePublisher(publication(ICON_PROVIDER))

        with mock.patch(
            "local_pipeline.job_entrypoints.validate_run_manifest"
        ) as validator:
            result = execute_icon_job(
                IconJobInputs(
                    Path("missing-payload.json"),
                    Path("missing-report.json"),
                    PUBLISHED_AT,
                    source_run_id=RUN_ID,
                    input_fingerprint_sha256=fingerprint,
                    prepared=prepared,
                ),
                catalog=self.catalog,
                publisher=publisher,
                materializer=lambda **_kwargs: (_ for _ in ()).throw(
                    AssertionError("prepared commit must not materialize again")
                ),
            )

        self.assertEqual(JobStatus.PUBLISHED, result.status)
        self.assertEqual(1, validator.call_count)
        self.assertEqual(1, len(publisher.calls))

    def test_prepared_icon_binds_run_and_fingerprint_before_intent(self):
        manifest_bytes = json.dumps(
            {"provider": ICON_PROVIDER, "source_run_id": RUN_ID},
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        fingerprint = hashlib.sha256(manifest_bytes).hexdigest()

        with self.assertRaisesRegex(InvalidJobInputs, "inconsistent"):
            PreparedIconPublication(
                source_run_id="20260905T000000Z",
                input_fingerprint_sha256=fingerprint,
                documents={"fixture": b"icon"},
                manifest_bytes=manifest_bytes,
            )
        with self.assertRaisesRegex(InvalidJobInputs, "inconsistent"):
            PreparedIconPublication(
                source_run_id=RUN_ID,
                input_fingerprint_sha256="a" * 64,
                documents={"fixture": b"icon"},
                manifest_bytes=manifest_bytes,
            )


class CamsEntrypointTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog = load_catalog()

    @staticmethod
    def inputs():
        return CamsJobInputs(
            paths=SimpleNamespace(label="paths"),
            owner_id="worker-1",
            published_at=PUBLISHED_AT,
        )

    def test_cams_job_publishes_both_views_without_icon(self):
        calls = []
        lifecycle_result = SimpleNamespace(
            key=SimpleNamespace(source_run_id=RUN_ID),
            record=SimpleNamespace(state=RunState.PUBLISHED),
            core_stage=stage(CAMS_PROVIDER),
            pollen_stage=stage(CAMS_POLLEN_PROVIDER),
            family_publication=family_publication(),
        )

        def lifecycle(**kwargs):
            calls.append(kwargs)
            return lifecycle_result

        result = execute_cams_job(
            self.inputs(),
            catalog=self.catalog,
            state_store="state-port",
            publisher="publisher-port",
            lifecycle=lifecycle,
        )
        self.assertEqual(JobStatus.PUBLISHED, result.status)
        self.assertEqual((CAMS_PROVIDER, CAMS_POLLEN_PROVIDER), result.published_providers)
        self.assertNotIn(ICON_PROVIDER, result.published_providers)
        self.assertEqual("state-port", calls[0]["state_store"])
        self.assertEqual("publisher-port", calls[0]["publisher"])

    def test_cams_replay_is_no_op_but_held_lease_requests_retry(self):
        replay = SimpleNamespace(
            key=SimpleNamespace(source_run_id=RUN_ID),
            record=SimpleNamespace(state=RunState.PUBLISHED),
            core_stage=stage(CAMS_PROVIDER, idempotent=True),
            pollen_stage=stage(CAMS_POLLEN_PROVIDER, idempotent=True),
            family_publication=family_publication(updated=False, idempotent=True),
        )
        replay_result = execute_cams_job(
            self.inputs(),
            catalog=self.catalog,
            state_store=object(),
            publisher=object(),
            lifecycle=lambda **_kwargs: replay,
        )
        self.assertEqual(JobStatus.NO_OP, replay_result.status)
        self.assertEqual("run_already_published", replay_result.reason_code)

        lease_result = execute_cams_job(
            self.inputs(),
            catalog=self.catalog,
            state_store=object(),
            publisher=object(),
            lifecycle=lambda **_kwargs: (_ for _ in ()).throw(
                CamsLeaseUnavailable(779)
            ),
        )
        self.assertEqual(JobStatus.RETRYABLE_FAILURE, lease_result.status)
        self.assertEqual("lease_still_held", lease_result.reason_code)
        self.assertEqual(779, lease_result.retry_after_seconds)
        self.assertEqual(75, lease_result.exit_code)

    def test_invalid_evidence_requires_review_and_is_not_retried(self):
        result = execute_cams_job(
            self.inputs(),
            catalog=self.catalog,
            state_store=object(),
            publisher=object(),
            lifecycle=lambda **_kwargs: (_ for _ in ()).throw(
                CamsEvidenceError("provider body omitted")
            ),
        )
        self.assertEqual(JobStatus.MANUAL_REVIEW, result.status)
        self.assertFalse(result.retryable)
        self.assertEqual(2, result.exit_code)

    def test_classifier_rejects_guessing_for_unknown_errors(self):
        self.assertIsNone(classify_job_failure(JobKind.CAMS, RuntimeError("unknown")))
        self.assertIsNone(classify_job_failure(JobKind.CAMS, TypeError("internal")))

    def test_lost_lease_is_retryable_but_invalid_evidence_is_not(self):
        lost = classify_job_failure(JobKind.CAMS, LeaseLost("lost"))
        invalid = classify_job_failure(JobKind.CAMS, CamsEvidenceError("invalid"))
        self.assertIsNotNone(lost)
        self.assertIsNotNone(invalid)
        self.assertEqual(JobStatus.RETRYABLE_FAILURE, lost.status)
        self.assertEqual(JobStatus.MANUAL_REVIEW, invalid.status)

    def test_mixed_or_superseded_cams_publication_requires_review(self):
        wrong_run_pollen = stage(CAMS_POLLEN_PROVIDER)
        wrong_run_pollen.source_run_id = "20260903T000000Z"
        for core, pollen, family in (
            (
                stage(CAMS_PROVIDER),
                stage(CAMS_POLLEN_PROVIDER),
                family_publication(superseded=True),
            ),
            (stage(ICON_PROVIDER), stage(CAMS_POLLEN_PROVIDER), family_publication()),
            (stage(CAMS_PROVIDER), wrong_run_pollen, family_publication()),
        ):
            with self.subTest(core=core.provider, pollen=pollen.provider):
                lifecycle_result = SimpleNamespace(
                    key=SimpleNamespace(source_run_id=RUN_ID),
                    record=SimpleNamespace(state=RunState.PUBLISHED),
                    core_stage=core,
                    pollen_stage=pollen,
                    family_publication=family,
                )
                result = execute_cams_job(
                    self.inputs(),
                    catalog=self.catalog,
                    state_store=object(),
                    publisher=object(),
                    lifecycle=lambda **_kwargs: lifecycle_result,
                )
                self.assertEqual(JobStatus.MANUAL_REVIEW, result.status)


if __name__ == "__main__":
    unittest.main()
