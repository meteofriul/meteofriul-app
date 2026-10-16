"""Fast offline tests for create-only weather publication intents."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import socket
import tempfile
import threading
import unittest
from unittest import mock

from local_pipeline.job_outcomes import JobKind
from local_pipeline.publication_intent import (
    InvalidPublicationIntent,
    MAX_INTENT_BYTES,
    PublicationInputError,
    PublicationIntentConflict,
    PublicationIntentCorruption,
    PublicationIntentResolution,
    fingerprint_input_files,
    resolve_publication_intent,
)


RUN_ID = "20260905T000000Z"
PUBLISHED_AT = "2026-09-05T01:23:45Z"
FINGERPRINT = "a" * 64


class PublicationIntentTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(
            prefix="meteofriul-publication-intent-"
        )
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.intent_path = self.root / "icon-publication-intent.json"

    def resolve(self, **overrides):
        arguments = {
            "job": JobKind.ICON,
            "source_run_id": RUN_ID,
            "input_fingerprint_sha256": FINGERPRINT,
            "published_at": PUBLISHED_AT,
        }
        arguments.update(overrides)
        return resolve_publication_intent(self.intent_path, **arguments)

    def test_first_attempt_creates_exact_canonical_bytes_and_retry_reuses_time(self):
        first = self.resolve()
        original = self.intent_path.read_bytes()
        second = self.resolve(published_at=None)

        self.assertFalse(first.reused)
        self.assertTrue(second.reused)
        self.assertEqual(PUBLISHED_AT, second.intent.published_at)
        self.assertEqual(first.intent, second.intent)
        self.assertEqual(first.intent.canonical_bytes(), original)
        self.assertEqual(original, self.intent_path.read_bytes())
        self.assertEqual(
            [
                "input_fingerprint_sha256",
                "job",
                "kind",
                "published_at",
                "schema_version",
                "source_run_id",
            ],
            list(json.loads(original).keys()),
        )

    def test_first_attempt_requires_explicit_publication_time(self):
        with self.assertRaises(InvalidPublicationIntent):
            self.resolve(published_at=None)
        self.assertFalse(self.intent_path.exists())

    def test_valid_existing_intent_rejects_every_identity_conflict_without_overwrite(self):
        first = self.resolve()
        original = self.intent_path.read_bytes()
        conflicts = (
            {"job": JobKind.CAMS},
            {"source_run_id": "20260904T000000Z"},
            {"input_fingerprint_sha256": "b" * 64},
            {"published_at": "2026-09-05T01:23:46Z"},
        )
        for changes in conflicts:
            with self.subTest(changes=changes):
                with self.assertRaises(PublicationIntentConflict):
                    self.resolve(**changes)
                self.assertEqual(original, self.intent_path.read_bytes())
        self.assertEqual(first.intent.canonical_bytes(), original)

    def test_corrupt_noncanonical_or_oversized_intent_fails_closed(self):
        valid = self.resolve().intent.as_document()
        cases = {
            "truncated": b'{"schema_version":1',
            "noncanonical": json.dumps(valid, indent=2).encode("utf-8"),
            "duplicate_key": (
                b'{"input_fingerprint_sha256":"'
                + FINGERPRINT.encode("ascii")
                + b'","job":"icon","job":"cams","kind":"meteofriul.weather.publication_intent",'
                b'"published_at":"2026-09-05T01:23:45Z","schema_version":1,'
                b'"source_run_id":"20260905T000000Z"}'
            ),
            "oversized": b"x" * (MAX_INTENT_BYTES + 1),
        }
        for label, body in cases.items():
            with self.subTest(label=label):
                self.intent_path.write_bytes(body)
                before = self.intent_path.read_bytes()
                with self.assertRaises(PublicationIntentCorruption):
                    self.resolve(published_at=None)
                self.assertEqual(before, self.intent_path.read_bytes())

    def test_identical_concurrent_writers_choose_one_creator_and_one_intent(self):
        workers = 8
        barrier = threading.Barrier(workers)

        def create() -> PublicationIntentResolution:
            barrier.wait()
            return self.resolve()

        with ThreadPoolExecutor(max_workers=workers) as pool:
            results = list(pool.map(lambda _value: create(), range(workers)))

        self.assertEqual(1, sum(not result.reused for result in results))
        self.assertEqual(workers - 1, sum(result.reused for result in results))
        self.assertEqual(1, len({result.intent.canonical_bytes() for result in results}))
        self.assertEqual(results[0].intent.canonical_bytes(), self.intent_path.read_bytes())

    def test_conflicting_concurrent_writers_never_replace_the_winner(self):
        barrier = threading.Barrier(2)
        requested_times = (PUBLISHED_AT, "2026-09-05T01:23:46Z")

        def create(published_at):
            barrier.wait()
            try:
                return self.resolve(published_at=published_at)
            except PublicationIntentConflict as error:
                return error

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(create, requested_times))

        resolutions = [
            result for result in results if isinstance(result, PublicationIntentResolution)
        ]
        conflicts = [
            result for result in results if isinstance(result, PublicationIntentConflict)
        ]
        self.assertEqual(1, len(resolutions))
        self.assertEqual(1, len(conflicts))
        self.assertFalse(resolutions[0].reused)
        self.assertEqual(
            resolutions[0].intent.canonical_bytes(),
            self.intent_path.read_bytes(),
        )

    def test_invalid_run_and_timestamp_never_create_an_intent(self):
        for changes in (
            {"source_run_id": "20260230T000000Z"},
            {"source_run_id": "20260905T0000Z"},
            {"source_run_id": "20260905T000001Z"},
            {"published_at": "2026-02-30T00:00:00Z"},
            {"published_at": "2026-09-05T01:23:45+00:00"},
        ):
            with self.subTest(changes=changes):
                with self.assertRaises(InvalidPublicationIntent):
                    self.resolve(**changes)
                self.assertFalse(self.intent_path.exists())

    def test_module_never_opens_a_network_socket(self):
        with mock.patch.object(
            socket,
            "socket",
            side_effect=AssertionError("network access is forbidden"),
        ):
            first = self.resolve()
            second = self.resolve(published_at=None)
        self.assertFalse(first.reused)
        self.assertTrue(second.reused)


class InputFingerprintTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(
            prefix="meteofriul-input-fingerprint-"
        )
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.payload = self.root / "payload.json"
        self.report = self.root / "report.json"
        self.payload.write_bytes(b'{"payload":1}')
        self.report.write_bytes(b'{"report":1}')

    def test_fingerprint_is_order_independent_but_binds_labels_and_contents(self):
        first = fingerprint_input_files(
            {"payload": self.payload, "report": self.report}
        )
        reversed_order = fingerprint_input_files(
            {"report": self.report, "payload": self.payload}
        )
        relabelled = fingerprint_input_files(
            {"archive": self.payload, "report": self.report}
        )
        self.payload.write_bytes(b'{"payload":2}')
        changed = fingerprint_input_files(
            {"payload": self.payload, "report": self.report}
        )

        self.assertEqual(first, reversed_order)
        self.assertNotEqual(first, relabelled)
        self.assertNotEqual(first, changed)
        self.assertRegex(first, r"^[0-9a-f]{64}$")

    def test_missing_empty_duplicate_or_invalid_inputs_fail_closed(self):
        empty = self.root / "empty.json"
        empty.touch()
        missing = self.root / "missing.json"
        cases = (
            {},
            {"payload": missing},
            {"payload": empty},
            {"Bad Label": self.payload},
            {"payload": self.payload, "copy": self.payload},
        )
        for inputs in cases:
            with self.subTest(inputs=tuple(inputs)):
                with self.assertRaises(PublicationInputError):
                    fingerprint_input_files(inputs)


if __name__ == "__main__":
    unittest.main()
