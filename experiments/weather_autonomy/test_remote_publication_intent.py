from dataclasses import replace
from tempfile import TemporaryDirectory
from pathlib import Path
from unittest import TestCase, main
from unittest.mock import Mock
from local_pipeline.publication_intent import PublicationIntent, PublicationIntentConflict, PublicationIntentCorruption
from local_pipeline.job_outcomes import JobKind
from local_pipeline.sqlite_object_store import SQLiteObjectStore, ObjectNotFound, ObjectStoreError
from local_pipeline.remote_publication_intent import resolve_remote_publication_intent, read_remote_publication_intent


class RemoteIntentTests(TestCase):
    def setUp(self):
        self.directory = TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.store = SQLiteObjectStore(Path(self.directory.name) / "state.sqlite")
        self.intent = PublicationIntent(JobKind.ICON, "20260906T000000Z",
                                        "2026-09-06T13:00:00Z", "a" * 64)

    def test_restart_reuses_original_time(self):
        first = resolve_remote_publication_intent(self.store, self.intent)
        resumed = resolve_remote_publication_intent(self.store, replace(
            self.intent, published_at="2026-09-06T14:00:00Z"))
        self.assertFalse(first.reused)
        self.assertTrue(resumed.reused)
        self.assertEqual(first.intent, resumed.intent)

    def test_changed_inputs_fail_closed(self):
        resolve_remote_publication_intent(self.store, self.intent)
        with self.assertRaises(PublicationIntentConflict):
            resolve_remote_publication_intent(self.store, replace(
                self.intent, input_fingerprint_sha256="b" * 64))

    def test_ambiguous_write_is_not_retried(self):
        store = Mock()
        store.get.side_effect = ObjectNotFound("missing")
        store.put.side_effect = ObjectStoreError("timeout")
        with self.assertRaises(ObjectStoreError):
            resolve_remote_publication_intent(store, self.intent)
        store.put.assert_called_once()

    def test_provider_isolation(self):
        resolve_remote_publication_intent(self.store, self.intent)
        other = replace(self.intent, job=JobKind.CAMS)
        self.assertFalse(resolve_remote_publication_intent(self.store, other).reused)

    def test_read_only_recovery_preserves_frozen_intent(self):
        resolve_remote_publication_intent(self.store, self.intent)
        self.store.put = Mock(side_effect=AssertionError('recovery may not write'))
        self.assertEqual(read_remote_publication_intent(self.store, job=JobKind.ICON,
                         source_run_id=self.intent.source_run_id), self.intent)
        self.store.put.assert_not_called()

    def test_recovery_rejects_identity_and_noncanonical_json(self):
        key = f'state/publication/icon/{self.intent.source_run_id}.json'
        self.store.put(key, replace(self.intent, job=JobKind.CAMS).canonical_bytes(), content_type='application/json')
        with self.assertRaises(PublicationIntentConflict):
            read_remote_publication_intent(self.store, job=JobKind.ICON, source_run_id=self.intent.source_run_id)
        other = Mock()
        other.get.return_value.body = self.intent.canonical_bytes() + b'\n'
        with self.assertRaises(PublicationIntentCorruption):
            read_remote_publication_intent(other, job=JobKind.ICON, source_run_id=self.intent.source_run_id)


if __name__ == "__main__":
    main()
