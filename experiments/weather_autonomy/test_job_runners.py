"""Fast offline tests for the two executable provider job runners."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest import mock

from local_pipeline.contract_v1 import (
    CAMS_POLLEN_PROVIDER,
    CAMS_PROVIDER,
    ICON_PROVIDER,
    canonical_json_bytes,
)
from local_pipeline.cams_lifecycle import CamsEvidenceError, PreparedCamsRun
from local_pipeline.contracts import Provider, RunKey
from local_pipeline.job_outcomes import JobKind, JobResult, JobStatus
from local_pipeline.job_entrypoints import PreparedIconPublication
from local_pipeline.publication_intent import (
    PublicationIntent,
    PublicationIntentConflict,
    PublicationIntentResolution,
    fingerprint_input_files,
)

import run_cams_job
import run_icon_job


RUN_ID = "20260904T000000Z"
PUBLISHED_AT = "2026-09-04T01:23:45Z"
NOW = datetime(2026, 9, 4, 1, 23, 45, tzinfo=timezone.utc)


def intent_resolution(
    job: JobKind,
    *,
    reused: bool = False,
    fingerprint: str = "a" * 64,
):
    return PublicationIntentResolution(
        PublicationIntent(job, RUN_ID, PUBLISHED_AT, fingerprint),
        reused=reused,
    )


def prepared_icon(seed: str = "fixture") -> PreparedIconPublication:
    manifest_bytes = canonical_json_bytes(
        {
            "provider": ICON_PROVIDER,
            "source_run_id": RUN_ID,
            "fixture_seed": seed,
        }
    )
    return PreparedIconPublication(
        source_run_id=RUN_ID,
        input_fingerprint_sha256=hashlib.sha256(manifest_bytes).hexdigest(),
        documents={"fixture": b"icon"},
        manifest_bytes=manifest_bytes,
    )


def prepared_cams() -> PreparedCamsRun:
    core_manifest = canonical_json_bytes(
        {"provider": CAMS_PROVIDER, "source_run_id": RUN_ID}
    )
    pollen_manifest = canonical_json_bytes(
        {"provider": CAMS_POLLEN_PROVIDER, "source_run_id": RUN_ID}
    )
    core_manifest_sha256 = hashlib.sha256(core_manifest).hexdigest()
    pollen_manifest_sha256 = hashlib.sha256(pollen_manifest).hexdigest()
    request_sha256 = "b" * 64
    request_plan_sha256 = "d" * 64
    catalog_sha256 = "c" * 64
    artifact_sha256 = "e" * 64
    payload_sha256 = "f" * 64
    decode_report_sha256 = "0" * 64
    validation_document = {
        "schema_version": 1,
        "kind": "cams_local_validation_attestation",
        "source_run_id": RUN_ID,
        "request_sha256": request_sha256,
        "request_plan_sha256": request_plan_sha256,
        "catalog_sha256": catalog_sha256,
        "artifact_sha256": artifact_sha256,
        "payload_sha256": payload_sha256,
        "decode_report_sha256": decode_report_sha256,
        "municipality_count": 215,
        "variable_count": 28,
        "hourly_instants": 97,
        "core_manifest_sha256": core_manifest_sha256,
        "pollen_manifest_sha256": pollen_manifest_sha256,
    }
    validation_sha256 = hashlib.sha256(
        canonical_json_bytes(validation_document)
    ).hexdigest()
    return PreparedCamsRun(
        key=RunKey(Provider.CAMS, RUN_ID, request_sha256),
        catalog_sha256=catalog_sha256,
        submitted_checkpoint={
            "request_plan_sha256": request_plan_sha256,
            "catalog_sha256": catalog_sha256,
        },
        ready_checkpoint={},
        downloaded_checkpoint={"artifact_sha256": artifact_sha256},
        validated_checkpoint={
            "payload_sha256": payload_sha256,
            "decode_report_sha256": decode_report_sha256,
            "municipality_count": 215,
            "variable_count": 28,
            "hourly_instants": 97,
            "validation_sha256": validation_sha256,
        },
        validation_sha256=validation_sha256,
        core_documents={"fixture": b"cams"},
        core_manifest_bytes=core_manifest,
        core_manifest_sha256=core_manifest_sha256,
        pollen_documents={"fixture": b"pollen"},
        pollen_manifest_bytes=pollen_manifest,
        pollen_manifest_sha256=pollen_manifest_sha256,
    )


class ContextResource:
    def __init__(self, events, label):
        self.events = events
        self.label = label

    def __enter__(self):
        self.events.append(f"{self.label}:enter")
        return self

    def __exit__(self, *_args):
        self.events.append(f"{self.label}:exit")


class RunnerTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="weather-job-runners-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.intents = self.root / "intents"
        self.intents.mkdir()

        self.icon_payload = self.root / "icon.json"
        self.icon_report = self.root / "icon-report.json"
        self.icon_payload.write_text('{"payload":1}', encoding="utf-8")
        self.icon_report.write_text(
            '{"run_utc":"2026-09-04T00:00:00Z"}', encoding="utf-8"
        )

        self.cams_directory = self.root / "cams"
        self.cams_directory.mkdir()
        self.cams_payload = self.cams_directory / "cams.json"
        self.cams_report = self.cams_directory / "cams-report.json"
        self.cams_payload.write_text('{"payload":1}', encoding="utf-8")
        self.cams_report.write_text(
            '{"run_date":"2026-09-04"}', encoding="utf-8"
        )

    def icon_config(self):
        return run_icon_job.IconRunnerConfig(
            payload=self.icon_payload,
            report=self.icon_report,
            object_db=self.root / "objects.sqlite3",
            intent_directory=self.intents,
        )

    def cams_config(self):
        return run_cams_job.CamsRunnerConfig(
            artifacts_directory=self.cams_directory,
            decoded_payload=self.cams_payload,
            decode_report=self.cams_report,
            state_db=self.root / "state.sqlite3",
            object_db=self.root / "objects.sqlite3",
            intent_directory=self.intents,
        )

    def test_parsers_require_only_the_explicit_local_inputs(self):
        icon = run_icon_job.parse_config(
            [
                "--payload",
                "icon.json",
                "--report",
                "report.json",
                "--object-db",
                "objects.sqlite3",
                "--intent-directory",
                "intents",
            ]
        )
        self.assertEqual(Path("icon.json"), icon.payload)
        self.assertFalse(hasattr(icon, "published_at"))

        cams = run_cams_job.parse_config(
            [
                "--artifacts-directory",
                "artifacts",
                "--decoded-payload",
                "artifacts/payload.json",
                "--decode-report",
                "artifacts/report.json",
                "--state-db",
                "state.sqlite3",
                "--object-db",
                "objects.sqlite3",
                "--intent-directory",
                "intents",
            ]
        )
        self.assertFalse(hasattr(cams, "owner_id"))
        self.assertFalse(hasattr(cams, "published_at"))
        forbidden = {
            "--credentials-file",
            "--max-wait",
            "--owner-id",
            "--published-at",
            "--run",
            "--scope",
        }
        for parser in (run_icon_job.build_parser(), run_cams_job.build_parser()):
            options = {
                option
                for action in parser._actions
                for option in action.option_strings
            }
            self.assertTrue(forbidden.isdisjoint(options))

    def test_cams_attempt_owner_is_generated_fresh_inside_the_runner(self):
        first_uuid = mock.Mock(hex="a" * 32)
        second_uuid = mock.Mock(hex="b" * 32)
        with mock.patch.object(
            run_cams_job,
            "uuid4",
            side_effect=(first_uuid, second_uuid),
        ):
            first = run_cams_job.create_cams_attempt_id()
            second = run_cams_job.create_cams_attempt_id()

        self.assertEqual("cams-attempt-" + "a" * 32, first)
        self.assertEqual("cams-attempt-" + "b" * 32, second)
        self.assertNotEqual(first, second)

    def test_icon_resolves_intent_before_store_and_closes_before_return(self):
        events = []
        observed = {}
        prepared = prepared_icon()

        def catalog_loader():
            events.append("catalog")
            return "catalog"

        def preparer(**_kwargs):
            events.append("prepare")
            return prepared

        def intent_resolver(_directory, **kwargs):
            events.append("intent")
            observed["intent"] = kwargs
            return intent_resolution(
                JobKind.ICON,
                fingerprint=prepared.input_fingerprint_sha256,
            )

        def store_factory(_path):
            events.append("object:init")
            return ContextResource(events, "object")

        def publisher_factory(store, catalog):
            events.append("publisher")
            observed["publisher"] = (store, catalog)
            return "publisher"

        def executor(inputs, **kwargs):
            events.append("execute")
            observed["inputs"] = inputs
            observed["execute"] = kwargs
            return JobResult(
                JobKind.ICON,
                JobStatus.PUBLISHED,
                "publication_committed",
                source_run_id=RUN_ID,
                published_providers=(ICON_PROVIDER,),
            )

        result = run_icon_job.run_icon(
            self.icon_config(),
            clock=lambda: NOW,
            catalog_loader=catalog_loader,
            preparer=preparer,
            intent_resolver=intent_resolver,
            store_factory=store_factory,
            publisher_factory=publisher_factory,
            executor=executor,
        )
        self.assertEqual(
            [
                "catalog",
                "prepare",
                "intent",
                "object:init",
                "object:enter",
                "publisher",
                "execute",
                "object:exit",
            ],
            events,
        )
        self.assertEqual(JobKind.ICON, observed["intent"]["job"])
        self.assertEqual(
            prepared.input_fingerprint_sha256,
            observed["intent"]["input_fingerprint_sha256"],
        )
        self.assertNotIn("input_files", observed["intent"])
        self.assertEqual(PUBLISHED_AT, observed["inputs"].published_at)
        self.assertIsNotNone(observed["inputs"].prepared)
        self.assertEqual("publisher", observed["execute"]["publisher"])
        self.assertFalse(result.metrics["publication_intent_reused"])

    def test_cams_wiring_is_isolated_and_resources_close_in_reverse_order(self):
        events = []
        observed = {}
        prepared = prepared_cams()

        def preparer(**_kwargs):
            events.append("prepare")
            return prepared

        def intent_resolver(_directory, **kwargs):
            events.append("intent")
            observed["intent"] = kwargs
            return intent_resolution(
                JobKind.CAMS,
                reused=True,
                fingerprint=prepared.input_fingerprint_sha256,
            )

        def state_factory(_path):
            events.append("state:init")
            return ContextResource(events, "state")

        def object_factory(_path, *, state_database_path):
            events.append("object:init")
            observed["state_database_path"] = state_database_path
            return ContextResource(events, "object")

        def executor(inputs, **kwargs):
            events.append("execute")
            observed["inputs"] = inputs
            observed["execute"] = kwargs
            return JobResult(
                JobKind.CAMS,
                JobStatus.PUBLISHED,
                "publication_committed",
                source_run_id=RUN_ID,
                published_providers=(CAMS_PROVIDER, CAMS_POLLEN_PROVIDER),
            )

        result = run_cams_job.run_cams(
            self.cams_config(),
            clock=lambda: NOW,
            catalog_loader=lambda: "catalog",
            preparer=preparer,
            intent_resolver=intent_resolver,
            state_store_factory=state_factory,
            object_store_factory=object_factory,
            publisher_factory=lambda _store, _catalog: "publisher",
            executor=executor,
            attempt_id_factory=lambda: "cams-attempt-test-1",
        )
        self.assertEqual(
            [
                "prepare",
                "intent",
                "state:init",
                "state:enter",
                "object:init",
                "object:enter",
                "execute",
                "object:exit",
                "state:exit",
            ],
            events,
        )
        self.assertEqual(JobKind.CAMS, observed["intent"]["job"])
        self.assertEqual(
            prepared.input_fingerprint_sha256,
            observed["intent"]["input_fingerprint_sha256"],
        )
        self.assertNotIn("input_files", observed["intent"])
        self.assertEqual(PUBLISHED_AT, observed["inputs"].published_at)
        self.assertIsNotNone(observed["inputs"].prepared)
        self.assertEqual("cams-attempt-test-1", observed["inputs"].owner_id)
        self.assertEqual("publisher", observed["execute"]["publisher"])
        self.assertNotIn(ICON_PROVIDER, result.published_providers)
        self.assertTrue(result.metrics["publication_intent_reused"])

    def test_intent_failure_never_opens_a_database(self):
        events = []

        def fail_intent(*_args, **_kwargs):
            events.append("intent")
            raise PublicationIntentConflict("secret-never-log")

        def forbidden_store(*_args, **_kwargs):
            events.append("store")
            raise AssertionError("store must not open")

        result = run_icon_job.run_icon(
            self.icon_config(),
            clock=lambda: NOW,
            catalog_loader=lambda: "catalog",
            preparer=lambda **_kwargs: prepared_icon(),
            intent_resolver=fail_intent,
            store_factory=forbidden_store,
        )
        self.assertEqual(["intent"], events)
        self.assertEqual(JobStatus.MANUAL_REVIEW, result.status)
        self.assertNotIn("secret-never-log", str(result.as_document()))

    def test_cams_preparation_failure_creates_neither_intent_nor_database(self):
        events = []

        def fail_prepare(**_kwargs):
            events.append("prepare")
            raise CamsEvidenceError("mismatched acquisition run")

        def forbidden(*_args, **_kwargs):
            events.append("forbidden")
            raise AssertionError("intent and stores must remain unopened")

        result = run_cams_job.run_cams(
            self.cams_config(),
            clock=lambda: NOW,
            catalog_loader=lambda: "catalog",
            preparer=fail_prepare,
            intent_resolver=forbidden,
            state_store_factory=forbidden,
            object_store_factory=forbidden,
        )

        self.assertEqual(["prepare"], events)
        self.assertEqual(JobStatus.MANUAL_REVIEW, result.status)
        self.assertEqual([], list(self.intents.iterdir()))

    def test_sqlite_sidecar_aliases_fail_before_preparation_or_intent(self):
        object_db = self.root / "objects.sqlite3"
        aliased_payload = self.root / "objects.sqlite3-wal"
        aliased_payload.write_bytes(b"not a database")
        events = []

        def forbidden(*_args, **_kwargs):
            events.append("called")
            raise AssertionError("unsafe layout must fail first")

        result = run_icon_job.run_icon(
            run_icon_job.IconRunnerConfig(
                payload=aliased_payload,
                report=self.icon_report,
                object_db=object_db,
                intent_directory=self.intents,
            ),
            clock=lambda: NOW,
            catalog_loader=lambda: "catalog",
            preparer=forbidden,
            intent_resolver=forbidden,
            store_factory=forbidden,
        )

        self.assertEqual([], events)
        self.assertEqual(JobStatus.PERMANENT_FAILURE, result.status)
        self.assertEqual([], list(self.intents.iterdir()))

    def test_cams_partial_download_sentinel_alias_fails_before_preparation(self):
        events = []

        def forbidden(*_args, **_kwargs):
            events.append("called")
            raise AssertionError("preparation must not start")

        config = self.cams_config()
        result = run_cams_job.run_cams(
            run_cams_job.CamsRunnerConfig(
                artifacts_directory=config.artifacts_directory,
                decoded_payload=config.decoded_payload,
                decode_report=config.decode_report,
                state_db=self.cams_directory / "source.grib.part",
                object_db=config.object_db,
                intent_directory=config.intent_directory,
            ),
            clock=lambda: NOW,
            catalog_loader=forbidden,
            preparer=forbidden,
        )

        self.assertEqual([], events)
        self.assertEqual(JobStatus.PERMANENT_FAILURE, result.status)

    def test_partial_cams_open_closes_state_and_returns_safe_review(self):
        events = []
        prepared = prepared_cams()

        def state_factory(_path):
            events.append("state:init")
            return ContextResource(events, "state")

        def fail_object(*_args, **_kwargs):
            events.append("object:init")
            raise sqlite3.OperationalError("token-never-log")

        result = run_cams_job.run_cams(
            self.cams_config(),
            clock=lambda: NOW,
            catalog_loader=lambda: "catalog",
            preparer=lambda **_kwargs: prepared,
            intent_resolver=lambda *_args, **_kwargs: intent_resolution(
                JobKind.CAMS,
                fingerprint=prepared.input_fingerprint_sha256,
            ),
            state_store_factory=state_factory,
            object_store_factory=fail_object,
        )
        self.assertEqual(
            ["state:init", "state:enter", "object:init", "state:exit"],
            events,
        )
        self.assertEqual(JobStatus.MANUAL_REVIEW, result.status)
        self.assertNotIn("token-never-log", str(result.as_document()))

    def test_unknown_programming_error_propagates_after_cleanup(self):
        events = []
        prepared = prepared_icon()

        def store_factory(_path):
            return ContextResource(events, "object")

        with self.assertRaisesRegex(RuntimeError, "unexpected defect"):
            run_icon_job.run_icon(
                self.icon_config(),
                clock=lambda: NOW,
                catalog_loader=lambda: "catalog",
                preparer=lambda **_kwargs: prepared,
                intent_resolver=lambda *_args, **_kwargs: intent_resolution(
                    JobKind.ICON,
                    fingerprint=prepared.input_fingerprint_sha256,
                ),
                store_factory=store_factory,
                publisher_factory=lambda *_args: "publisher",
                executor=lambda *_args, **_kwargs: (_ for _ in ()).throw(
                    RuntimeError("unexpected defect")
                ),
            )
        self.assertEqual(["object:enter", "object:exit"], events)

    def test_real_intent_is_reused_and_changed_input_fails_before_store(self):
        calls = []
        store_events = []

        def preparer(*, payload, report, **_kwargs):
            return prepared_icon(
                fingerprint_input_files({"payload": payload, "report": report})
            )

        def store_factory(_path):
            store_events.append("open")
            return ContextResource([], "object")

        def executor(inputs, **_kwargs):
            calls.append(inputs.published_at)
            return JobResult(JobKind.ICON, JobStatus.NO_OP, "run_already_published")

        first = run_icon_job.run_icon(
            self.icon_config(),
            clock=lambda: NOW,
            catalog_loader=lambda: "catalog",
            preparer=preparer,
            store_factory=store_factory,
            publisher_factory=lambda *_args: "publisher",
            executor=executor,
        )
        second = run_icon_job.run_icon(
            self.icon_config(),
            clock=lambda: datetime(2026, 9, 5, tzinfo=timezone.utc),
            catalog_loader=lambda: "catalog",
            preparer=preparer,
            store_factory=store_factory,
            publisher_factory=lambda *_args: "publisher",
            executor=executor,
        )
        self.assertEqual([PUBLISHED_AT, PUBLISHED_AT], calls)
        self.assertFalse(first.metrics["publication_intent_reused"])
        self.assertTrue(second.metrics["publication_intent_reused"])

        self.icon_payload.write_text('{"payload":2}', encoding="utf-8")
        store_events.clear()
        conflict = run_icon_job.run_icon(
            self.icon_config(),
            clock=lambda: NOW,
            catalog_loader=lambda: "catalog",
            preparer=preparer,
            store_factory=store_factory,
            publisher_factory=lambda *_args: "publisher",
            executor=executor,
        )
        self.assertEqual(JobStatus.MANUAL_REVIEW, conflict.status)
        self.assertEqual([], store_events)

    def test_main_emits_exactly_one_canonical_result_line_and_exit_code(self):
        argv = [
            "--payload",
            "icon.json",
            "--report",
            "report.json",
            "--object-db",
            "objects.sqlite3",
            "--intent-directory",
            "intents",
        ]
        results = (
            JobResult(
                JobKind.ICON,
                JobStatus.PUBLISHED,
                "publication_committed",
                source_run_id=RUN_ID,
                published_providers=(ICON_PROVIDER,),
            ),
            JobResult(JobKind.ICON, JobStatus.NO_OP, "run_already_published"),
            JobResult(
                JobKind.ICON,
                JobStatus.RETRYABLE_FAILURE,
                "temporary_state_or_storage_failure",
                retry_after_seconds=300,
            ),
            JobResult(JobKind.ICON, JobStatus.MANUAL_REVIEW, "review_required"),
            JobResult(JobKind.ICON, JobStatus.PERMANENT_FAILURE, "invalid_input"),
        )
        for result in results:
            with self.subTest(status=result.status):
                stream = io.StringIO()
                with mock.patch.object(run_icon_job, "run_icon", return_value=result):
                    exit_code = run_icon_job.main(
                        argv,
                        stream=stream,
                        clock=lambda: NOW,
                    )
                self.assertEqual(result.exit_code, exit_code)
                self.assertEqual(
                    canonical_json_bytes(result.as_document()).decode("utf-8") + "\n",
                    stream.getvalue(),
                )
                self.assertEqual(result.as_document(), json.loads(stream.getvalue()))

    def test_cli_argument_errors_are_one_safe_permanent_result(self):
        secret_path = r"C:\private\token-never-log.json"
        cases = (
            (run_icon_job, ["--payload", secret_path]),
            (run_icon_job, ["--help"]),
            (run_cams_job, ["--decoded-payload", secret_path]),
            (run_cams_job, ["--help"]),
        )
        for module, argv in cases:
            with self.subTest(module=module.__name__, argv=argv):
                stream = io.StringIO()
                stdout = io.StringIO()
                stderr = io.StringIO()
                with mock.patch.object(module.sys, "stdout", stdout), mock.patch.object(
                    module.sys, "stderr", stderr
                ):
                    exit_code = module.main(argv, stream=stream, clock=lambda: NOW)

                self.assertEqual(1, exit_code)
                self.assertEqual("", stdout.getvalue())
                self.assertEqual("", stderr.getvalue())
                self.assertEqual(1, stream.getvalue().count("\n"))
                document = json.loads(stream.getvalue())
                self.assertEqual("permanent_failure", document["status"])
                self.assertEqual("invalid_cli_arguments", document["reason_code"])
                self.assertFalse(document["retryable"])
                self.assertNotIn("private", stream.getvalue())
                self.assertNotIn("token-never-log", stream.getvalue())
                expected = JobResult(
                    JobKind(document["job"]),
                    JobStatus.PERMANENT_FAILURE,
                    "invalid_cli_arguments",
                )
                self.assertEqual(
                    canonical_json_bytes(expected.as_document()).decode("utf-8") + "\n",
                    stream.getvalue(),
                )

    def test_cli_configuration_failures_emit_one_safe_result(self):
        missing = self.root / "private-token-never-log.json"
        shared_db = self.root / "must-not-alias.sqlite3"
        cases = (
            (
                run_icon_job,
                [
                    "--payload",
                    str(missing),
                    "--report",
                    str(self.icon_report),
                    "--object-db",
                    str(self.root / "objects.sqlite3"),
                    "--intent-directory",
                    str(self.intents),
                ],
            ),
            (
                run_cams_job,
                [
                    "--artifacts-directory",
                    str(self.cams_directory),
                    "--decoded-payload",
                    str(self.cams_payload),
                    "--decode-report",
                    str(self.cams_report),
                    "--state-db",
                    str(shared_db),
                    "--object-db",
                    str(shared_db),
                    "--intent-directory",
                    str(self.intents),
                ],
            ),
        )
        for module, argv in cases:
            with self.subTest(module=module.__name__):
                stream = io.StringIO()
                exit_code = module.main(argv, stream=stream, clock=lambda: NOW)

                self.assertEqual(1, exit_code)
                self.assertEqual(1, stream.getvalue().count("\n"))
                document = json.loads(stream.getvalue())
                self.assertEqual("permanent_failure", document["status"])
                self.assertFalse(document["retryable"])
                self.assertNotIn("private-token-never-log", stream.getvalue())
                self.assertNotIn(str(self.root), stream.getvalue())
                self.assertEqual(
                    canonical_json_bytes(document).decode("utf-8") + "\n",
                    stream.getvalue(),
                )

    def test_unknown_cli_failures_are_one_safe_manual_review_result(self):
        icon_argv = [
            "--payload",
            "icon.json",
            "--report",
            "report.json",
            "--object-db",
            "objects.sqlite3",
            "--intent-directory",
            "intents",
        ]
        cams_argv = [
            "--artifacts-directory",
            "artifacts",
            "--decoded-payload",
            "artifacts/payload.json",
            "--decode-report",
            "artifacts/report.json",
            "--state-db",
            "state.sqlite3",
            "--object-db",
            "objects.sqlite3",
            "--intent-directory",
            "intents",
        ]
        cases = (
            (run_icon_job, "run_icon", icon_argv, JobKind.ICON),
            (run_cams_job, "run_cams", cams_argv, JobKind.CAMS),
        )
        for module, runner_name, argv, job in cases:
            with self.subTest(module=module.__name__):
                stream = io.StringIO()
                failure = RuntimeError(
                    r"unexpected defect: C:\private\token-never-log.json"
                )
                with mock.patch.object(module, runner_name, side_effect=failure):
                    exit_code = module.main(argv, stream=stream, clock=lambda: NOW)

                expected = JobResult(
                    job,
                    JobStatus.MANUAL_REVIEW,
                    "unexpected_internal_failure",
                )
                self.assertEqual(2, exit_code)
                self.assertEqual(1, stream.getvalue().count("\n"))
                self.assertEqual(
                    canonical_json_bytes(expected.as_document()).decode("utf-8") + "\n",
                    stream.getvalue(),
                )
                self.assertNotIn("private", stream.getvalue())
                self.assertNotIn("token-never-log", stream.getvalue())

    def test_orderly_cli_interrupts_are_one_safe_manual_review_result(self):
        cases = (
            (
                run_icon_job,
                "run_icon",
                [
                    "--payload",
                    "icon.json",
                    "--report",
                    "report.json",
                    "--object-db",
                    "objects.sqlite3",
                    "--intent-directory",
                    "intents",
                ],
                JobKind.ICON,
            ),
            (
                run_cams_job,
                "run_cams",
                [
                    "--artifacts-directory",
                    "artifacts",
                    "--decoded-payload",
                    "artifacts/payload.json",
                    "--decode-report",
                    "artifacts/report.json",
                    "--state-db",
                    "state.sqlite3",
                    "--object-db",
                    "objects.sqlite3",
                    "--intent-directory",
                    "intents",
                ],
                JobKind.CAMS,
            ),
        )
        for module, runner_name, argv, job in cases:
            with self.subTest(module=module.__name__):
                stream = io.StringIO()
                with mock.patch.object(
                    module,
                    runner_name,
                    side_effect=KeyboardInterrupt(),
                ):
                    exit_code = module.main(argv, stream=stream, clock=lambda: NOW)

                expected = JobResult(
                    job,
                    JobStatus.MANUAL_REVIEW,
                    "unexpected_internal_failure",
                )
                self.assertEqual(2, exit_code)
                self.assertEqual(
                    canonical_json_bytes(expected.as_document()).decode("utf-8") + "\n",
                    stream.getvalue(),
                )

    def test_invalid_runner_results_fail_closed_at_cli_boundary(self):
        argv = [
            "--payload",
            "icon.json",
            "--report",
            "report.json",
            "--object-db",
            "objects.sqlite3",
            "--intent-directory",
            "intents",
        ]
        stream = io.StringIO()
        wrong_job = JobResult(JobKind.CAMS, JobStatus.NO_OP, "run_already_published")
        with mock.patch.object(run_icon_job, "run_icon", return_value=wrong_job):
            exit_code = run_icon_job.main(argv, stream=stream, clock=lambda: NOW)

        self.assertEqual(2, exit_code)
        document = json.loads(stream.getvalue())
        self.assertEqual("icon", document["job"])
        self.assertEqual("manual_review", document["status"])
        self.assertEqual("unexpected_internal_failure", document["reason_code"])
        self.assertEqual(1, stream.getvalue().count("\n"))


if __name__ == "__main__":
    unittest.main()
