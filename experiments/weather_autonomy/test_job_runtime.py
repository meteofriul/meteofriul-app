"""Fast offline tests for the shared executable-job runtime helpers."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import io
import hashlib
import json
import os
from pathlib import Path
import socket
import tempfile
import threading
import unittest
from unittest import mock

from local_pipeline.contract_v1 import ICON_PROVIDER, canonical_json_bytes
from local_pipeline.job_entrypoints import InvalidJobInputs
from local_pipeline.job_outcomes import JobKind, JobResult, JobStatus
from local_pipeline.job_runtime import (
    MAX_IDENTITY_REPORT_BYTES,
    cams_source_run_id_from_file,
    emit_job_result,
    icon_source_run_id_from_file,
    icon_source_run_id_from_inputs,
    normalize_database_path,
    normalize_existing_directory,
    normalize_existing_file,
    normalize_intent_directory,
    normalize_owner_id,
    require_distinct_paths,
    require_safe_sqlite_layout,
    resolve_job_publication_intent,
    sqlite_reserved_paths,
    with_intent_metric,
)
from local_pipeline.publication_intent import PublicationIntentConflict


RUN_ID = "20260905T000000Z"


class FlushRecordingStream(io.StringIO):
    def __init__(self) -> None:
        super().__init__()
        self.flush_count = 0

    def flush(self) -> None:
        self.flush_count += 1
        super().flush()


class JobRuntimeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix="meteofriul-job-runtime-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.payload = self.root / "payload.json"
        self.report = self.root / "report.json"
        self.payload.write_bytes(b'{"payload":1}')
        self.report.write_bytes(b'{"report":1}')

    @staticmethod
    def _write_report(path: Path, document: object) -> None:
        path.write_text(
            json.dumps(document, ensure_ascii=False, separators=(",", ":")),
            encoding="utf-8",
        )

    def test_extracts_canonical_icon_and_cams_source_run_ids(self) -> None:
        icon_report = self.root / "icon-report.json"
        cams_report = self.root / "cams-report.json"
        self._write_report(icon_report, {"run_utc": "2026-09-05T00:00:00Z"})
        self._write_report(cams_report, {"run_date": "2026-09-05"})

        self.assertEqual(RUN_ID, icon_source_run_id_from_file(icon_report))
        self.assertEqual(RUN_ID, cams_source_run_id_from_file(cams_report))

    def test_icon_identity_is_derived_only_after_payload_report_authentication(self) -> None:
        payload = self.root / "icon-payload.json"
        report = self.root / "icon-report-bound.json"
        payload_raw = canonical_json_bytes(
            {
                "schema_version": 1,
                "status": "partial_pilot_not_production",
                "run_utc": "2026-09-05T00:00:00Z",
                "generated_at_utc": "2026-09-05T01:00:00Z",
            }
        )
        payload.write_bytes(payload_raw)
        self._write_report(
            report,
            {
                "run_utc": "2026-09-05T00:00:00Z",
                "payload_sha256": hashlib.sha256(payload_raw).hexdigest(),
                "catalog_sha256": "c" * 64,
            },
        )
        self.assertEqual(RUN_ID, icon_source_run_id_from_inputs(payload, report))

        document = json.loads(report.read_text(encoding="utf-8"))
        document["run_utc"] = "2026-09-04T00:00:00Z"
        self._write_report(report, document)
        with self.assertRaisesRegex(Exception, "different model runs"):
            icon_source_run_id_from_inputs(payload, report)

    def test_identity_reports_reject_duplicate_keys(self) -> None:
        cases = (
            (
                icon_source_run_id_from_file,
                b'{"run_utc":"2026-09-05T00:00:00Z",'
                b'"run_utc":"2026-09-05T06:00:00Z"}',
            ),
            (
                cams_source_run_id_from_file,
                b'{"run_date":"2026-09-05","run_date":"2026-09-06"}',
            ),
        )
        for position, (resolver, raw) in enumerate(cases):
            with self.subTest(resolver=resolver.__name__):
                path = self.root / f"duplicate-{position}.json"
                path.write_bytes(raw)
                with self.assertRaisesRegex(InvalidJobInputs, "duplicate JSON keys"):
                    resolver(path)

    def test_identity_reports_reject_noncanonical_run_values(self) -> None:
        cases = (
            (
                icon_source_run_id_from_file,
                {"run_utc": "2026-09-05T00:01:00Z"},
            ),
            (
                icon_source_run_id_from_file,
                {"run_utc": "2026-09-05T00:00:00+00:00"},
            ),
            (cams_source_run_id_from_file, {"run_date": "2026-9-05"}),
            (cams_source_run_id_from_file, {"run_date": "2026-02-30"}),
        )
        for position, (resolver, document) in enumerate(cases):
            with self.subTest(resolver=resolver.__name__, value=next(iter(document.values()))):
                path = self.root / f"noncanonical-{position}.json"
                self._write_report(path, document)
                with self.assertRaises(InvalidJobInputs):
                    resolver(path)

    def test_identity_reports_reject_oversize_files_before_decoding(self) -> None:
        oversized = self.root / "oversized-report.json"
        oversized.write_bytes(b"{" + b" " * MAX_IDENTITY_REPORT_BYTES)

        for resolver in (icon_source_run_id_from_file, cams_source_run_id_from_file):
            with self.subTest(resolver=resolver.__name__):
                with self.assertRaisesRegex(InvalidJobInputs, "size is invalid"):
                    resolver(oversized)

    def test_normalizes_files_databases_intent_directory_and_owner(self) -> None:
        database = self.root / "objects.sqlite3"

        self.assertEqual(self.payload.resolve(), normalize_existing_file(self.payload, "Payload"))
        self.assertEqual(
            self.root.resolve(),
            normalize_existing_directory(self.root, "Artifacts"),
        )
        self.assertEqual(database.resolve(), normalize_database_path(database, "Database"))
        self.assertEqual(self.root.resolve(), normalize_intent_directory(self.root))
        self.assertEqual("worker-1:retry.2", normalize_owner_id("worker-1:retry.2"))

        missing_parent = self.root / "missing" / "state.sqlite3"
        with self.assertRaisesRegex(InvalidJobInputs, "parent directory"):
            normalize_database_path(missing_parent, "State database")
        with self.assertRaisesRegex(InvalidJobInputs, "must be a regular file"):
            normalize_existing_file(self.root, "Payload")
        with self.assertRaisesRegex(InvalidJobInputs, "must be a directory"):
            normalize_existing_directory(self.payload, "Artifacts")
        with self.assertRaisesRegex(InvalidJobInputs, "must be a directory"):
            normalize_intent_directory(self.payload)

    def test_rejects_path_aliases_and_invalid_owner_ids(self) -> None:
        with self.assertRaisesRegex(InvalidJobInputs, "aliases payload"):
            require_distinct_paths(
                {"payload": self.payload.resolve(), "report": self.payload.resolve()}
            )

        hardlink = self.root / "payload-hardlink.json"
        os.link(self.payload, hardlink)
        with self.assertRaisesRegex(InvalidJobInputs, "aliases payload"):
            require_distinct_paths(
                {"payload": self.payload.resolve(), "report": hardlink.resolve()}
            )

        for owner in ("", "worker name", "worker@host", "a" * 129):
            with self.subTest(owner=owner[:20]):
                with self.assertRaisesRegex(InvalidJobInputs, "owner identifier"):
                    normalize_owner_id(owner)

    def test_rejects_win32_path_alias_spellings_before_filesystem_access(self) -> None:
        unsafe_paths = (
            (self.root / "payload.json.", "trailing space or dot"),
            (self.root / "payload.json ", "trailing space or dot"),
            (Path(f"{self.payload}:metadata"), "alternate data stream"),
            (self.root / "NUL.json", "reserved Win32 device name"),
            (self.root / "COM1" / "payload.json", "reserved Win32 device name"),
            (Path(r"\\server\share\payload.json"), "network share"),
        )
        for path, message in unsafe_paths:
            with self.subTest(path=path):
                with mock.patch.object(
                    Path,
                    "exists",
                    side_effect=AssertionError("unsafe path must not touch the filesystem"),
                ):
                    with self.assertRaisesRegex(InvalidJobInputs, message):
                        require_distinct_paths({"payload": path})

    def test_path_identity_is_win32_case_insensitive(self) -> None:
        with self.assertRaisesRegex(InvalidJobInputs, "aliases first"):
            require_distinct_paths(
                {
                    "first": self.root / "WEATHER.JSON",
                    "second": self.root / "weather.json",
                }
            )

    def test_sqlite_layout_reserves_main_wal_shm_and_journal_paths(self) -> None:
        database = self.root / "objects.sqlite3"
        reserved = sqlite_reserved_paths({"object database": database})

        self.assertEqual(
            {
                "object database": database,
                "object database WAL": Path(f"{database}-wal"),
                "object database SHM": Path(f"{database}-shm"),
                "object database journal": Path(f"{database}-journal"),
            },
            reserved,
        )

    def test_sqlite_layout_rejects_database_and_sidecar_aliases(self) -> None:
        object_database = self.root / "objects.sqlite3"
        cases = (
            (
                {"object database": object_database},
                {"payload": Path(f"{object_database}-wal")},
                "payload aliases object database WAL",
            ),
            (
                {
                    "object database": object_database,
                    "state database": Path(f"{object_database}-shm"),
                },
                {},
                "state database aliases object database SHM",
            ),
            (
                {"object database": object_database},
                {"intent": self.root / "OBJECTS.SQLITE3-JOURNAL"},
                "intent aliases object database journal",
            ),
        )
        for databases, other_paths, message in cases:
            with self.subTest(message=message):
                with self.assertRaisesRegex(InvalidJobInputs, message):
                    require_safe_sqlite_layout(
                        databases=databases,
                        other_paths=other_paths,
                    )

    def test_sqlite_layout_accepts_distinct_safe_paths(self) -> None:
        require_safe_sqlite_layout(
            databases={
                "object database": self.root / "objects.sqlite3",
                "state database": self.root / "state.sqlite3",
            },
            other_paths={
                "payload": self.payload,
                "report": self.report,
                "intent": self.root / "intents" / "icon-run.json",
            },
        )

    def test_publication_intent_is_created_then_reused_without_calling_clock(self) -> None:
        first = resolve_job_publication_intent(
            self.root,
            job=JobKind.ICON,
            source_run_id=RUN_ID,
            input_files={"payload": self.payload, "report": self.report},
            clock=lambda: datetime(
                2026,
                9,
                5,
                3,
                4,
                5,
                999999,
                tzinfo=timezone(timedelta(hours=2)),
            ),
        )

        def unexpected_clock() -> datetime:
            raise AssertionError("the frozen publication clock must not run on replay")

        second = resolve_job_publication_intent(
            self.root,
            job=JobKind.ICON,
            source_run_id=RUN_ID,
            input_files={"report": self.report, "payload": self.payload},
            clock=unexpected_clock,
        )

        self.assertFalse(first.reused)
        self.assertTrue(second.reused)
        self.assertEqual("2026-09-05T01:04:05Z", first.intent.published_at)
        self.assertEqual(first.intent, second.intent)
        self.assertEqual(
            first.intent.canonical_bytes(),
            (self.root / f"icon-{RUN_ID}.json").read_bytes(),
        )

    def test_verified_fingerprint_can_be_reused_without_reopening_inputs(self) -> None:
        fingerprint = "d" * 64
        with mock.patch(
            "local_pipeline.job_runtime.fingerprint_input_files",
            side_effect=AssertionError("verified inputs must not be read a third time"),
        ):
            resolution = resolve_job_publication_intent(
                self.root,
                job=JobKind.ICON,
                source_run_id=RUN_ID,
                input_fingerprint_sha256=fingerprint,
                clock=lambda: datetime(2026, 9, 5, 1, 23, 45, tzinfo=timezone.utc),
            )
        self.assertEqual(fingerprint, resolution.intent.input_fingerprint_sha256)

        with self.assertRaisesRegex(InvalidJobInputs, "either"):
            resolve_job_publication_intent(
                self.root,
                job=JobKind.CAMS,
                source_run_id=RUN_ID,
                input_files={"payload": self.payload},
                input_fingerprint_sha256=fingerprint,
                clock=lambda: datetime(2026, 9, 5, 1, 23, 45, tzinfo=timezone.utc),
            )

    def test_concurrent_workers_with_neighbouring_clock_seconds_share_winner(self) -> None:
        barrier = threading.Barrier(2, timeout=10)
        instants = (
            datetime(2026, 9, 5, 1, 23, 45, tzinfo=timezone.utc),
            datetime(2026, 9, 5, 1, 23, 46, tzinfo=timezone.utc),
        )

        def worker(instant: datetime):
            def clock() -> datetime:
                barrier.wait()
                return instant

            return resolve_job_publication_intent(
                self.root,
                job=JobKind.CAMS,
                source_run_id=RUN_ID,
                input_files={"decoded_payload": self.payload, "decode_report": self.report},
                clock=clock,
            )

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(worker, instants))

        self.assertEqual([False, True], sorted(result.reused for result in results))
        self.assertEqual(1, len({result.intent.published_at for result in results}))
        self.assertIn(
            results[0].intent.published_at,
            {"2026-09-05T01:23:45Z", "2026-09-05T01:23:46Z"},
        )
        self.assertEqual(results[0].intent, results[1].intent)

    def test_publication_intent_rejects_changed_input_for_same_run(self) -> None:
        resolve_job_publication_intent(
            self.root,
            job=JobKind.ICON,
            source_run_id=RUN_ID,
            input_files={"payload": self.payload, "report": self.report},
            clock=lambda: datetime(2026, 9, 5, 1, 23, 45, tzinfo=timezone.utc),
        )
        self.payload.write_bytes(b'{"payload":2}')

        with self.assertRaises(PublicationIntentConflict):
            resolve_job_publication_intent(
                self.root,
                job=JobKind.ICON,
                source_run_id=RUN_ID,
                input_files={"payload": self.payload, "report": self.report},
                clock=lambda: datetime(2026, 9, 5, 1, 23, 46, tzinfo=timezone.utc),
            )

    def test_intent_metric_and_emitted_job_json_are_canonical(self) -> None:
        resolution = resolve_job_publication_intent(
            self.root,
            job=JobKind.ICON,
            source_run_id=RUN_ID,
            input_files={"payload": self.payload, "report": self.report},
            clock=lambda: datetime(2026, 9, 5, 1, 23, 45, tzinfo=timezone.utc),
        )
        result = JobResult(
            job=JobKind.ICON,
            status=JobStatus.PUBLISHED,
            reason_code="publication_committed",
            source_run_id=RUN_ID,
            published_providers=(ICON_PROVIDER,),
            metrics={"payload_count": 215},
        )
        enriched = with_intent_metric(result, resolution)
        stream = FlushRecordingStream()

        emit_job_result(enriched, stream)

        expected = canonical_json_bytes(enriched.as_document()).decode("utf-8") + "\n"
        self.assertEqual(expected, stream.getvalue())
        self.assertEqual(1, stream.flush_count)
        document = json.loads(stream.getvalue())
        self.assertEqual(215, document["metrics"]["payload_count"])
        self.assertFalse(document["metrics"]["publication_intent_reused"])

    def test_runtime_helpers_do_not_open_network_sockets(self) -> None:
        icon_report = self.root / "icon-report.json"
        self._write_report(icon_report, {"run_utc": "2026-09-05T00:00:00Z"})
        with mock.patch.object(
            socket,
            "socket",
            side_effect=AssertionError("network access is forbidden"),
        ):
            self.assertEqual(RUN_ID, icon_source_run_id_from_file(icon_report))
            resolution = resolve_job_publication_intent(
                self.root,
                job=JobKind.ICON,
                source_run_id=RUN_ID,
                input_files={"payload": self.payload, "report": icon_report},
                clock=lambda: datetime(2026, 9, 5, 1, 23, 45, tzinfo=timezone.utc),
            )
            stream = FlushRecordingStream()
            emit_job_result(
                JobResult(
                    job=JobKind.ICON,
                    status=JobStatus.NO_OP,
                    reason_code="run_already_published",
                    source_run_id=RUN_ID,
                    metrics={"publication_intent_reused": resolution.reused},
                ),
                stream,
            )
        self.assertEqual("no_op", json.loads(stream.getvalue())["status"])


if __name__ == "__main__":
    unittest.main()
