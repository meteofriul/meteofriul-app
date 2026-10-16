"""Offline authentication and interrupted-write tests for ICON checkpoints."""
from dataclasses import replace
from datetime import datetime, timezone
import gzip
import hashlib
import json
from unittest import TestCase, main
from unittest.mock import patch

import test_contract_publisher as fixtures
from local_pipeline.contract_v1 import canonical_json_bytes, ContractError
from local_pipeline.gcs_object_store import RemoteObjectStoreError
from local_pipeline.icon_checkpoint import (
    encode_checkpoint, decode_checkpoint, read_checkpoint, save_checkpoint, checkpoint_key,
)
from local_pipeline.job_entrypoints import PreparedIconPublication
from local_pipeline.job_outcomes import JobKind
from local_pipeline.publication_intent import (
    PublicationIntent, PublicationIntentCorruption, PublicationIntentConflict,
)

SLOT = '20260908-am'


class IconCheckpointTests(TestCase):
    @classmethod
    def setUpClass(cls):
        fixtures.ContractPublisherTests.setUpClass()
        cls.catalog = fixtures.ContractPublisherTests.catalog
        documents, manifest = fixtures.ContractPublisherTests.icon_bundle(datetime(2026, 9, 8, tzinfo=timezone.utc))
        manifest_bytes = canonical_json_bytes(manifest)
        cls.prepared = PreparedIconPublication(manifest['source_run_id'], hashlib.sha256(manifest_bytes).hexdigest(),
                                               documents, manifest_bytes)
        cls.intent = PublicationIntent(JobKind.ICON, cls.prepared.source_run_id, '2026-09-08T06:00:00Z',
                                        cls.prepared.input_fingerprint_sha256)
        cls.body = encode_checkpoint(slot=SLOT, prepared=cls.prepared, intent=cls.intent, catalog=cls.catalog)

    def setUp(self):
        self.store = fixtures.MemoryObjectStore()

    def test_round_trip_authenticates_all_215_and_preserves_exact_bytes(self):
        restored = decode_checkpoint(self.body, slot=SLOT, catalog=self.catalog)
        self.assertEqual(len(restored.prepared.documents), 215)
        self.assertEqual(restored.prepared.documents, self.prepared.documents)
        self.assertEqual(restored.prepared.manifest_bytes, self.prepared.manifest_bytes)
        self.assertEqual(restored.intent, self.intent)
        self.assertLess(len(self.body), 16 * 1024**2)

    def test_restart_read_has_no_writes(self):
        self.store.put(checkpoint_key(SLOT), self.body, content_type='application/gzip')
        with patch.object(self.store, 'put') as put:
            self.assertEqual(read_checkpoint(self.store, slot=SLOT, catalog=self.catalog).intent, self.intent)
            put.assert_not_called()

    def test_lost_checkpoint_response_reconciles_identical_create(self):
        original = self.store.put
        calls = []
        def lost_response(key, body, **kwargs):
            calls.append(key)
            result = original(key, body, **kwargs)
            if len(calls) == 1:
                raise RemoteObjectStoreError('storage request timed out', original_type='TimeoutError', retryable=True)
            return result
        with patch.object(self.store, 'put', side_effect=lost_response):
            with self.assertRaises(RemoteObjectStoreError):
                save_checkpoint(self.store, slot=SLOT, prepared=self.prepared, intent=self.intent, catalog=self.catalog)
            restored = save_checkpoint(self.store, slot=SLOT, prepared=self.prepared, intent=self.intent, catalog=self.catalog)
        self.assertEqual(restored.intent, self.intent)
        self.assertEqual(len(self.store.objects), 1)

    def test_frozen_time_conflict_is_not_overwritten(self):
        self.store.put(checkpoint_key(SLOT), self.body, content_type='application/gzip')
        with self.assertRaises(PublicationIntentConflict):
            save_checkpoint(self.store, slot=SLOT, prepared=self.prepared,
                intent=replace(self.intent, published_at='2026-09-08T07:00:00Z'), catalog=self.catalog)
        self.assertEqual(self.store.get(checkpoint_key(SLOT)).body, self.body)

    def test_bad_gzip_truncation_and_wrong_slot_are_rejected(self):
        for body, slot in [(b'bad', SLOT), (self.body[:-8], SLOT), (self.body, '20260908-pm')]:
            with self.subTest(slot=slot, size=len(body)), self.assertRaises(PublicationIntentCorruption):
                decode_checkpoint(body, slot=slot, catalog=self.catalog)

    def test_gzip_expansion_is_bounded_before_json_parse(self):
        with patch('local_pipeline.icon_checkpoint.MAX_EXPANDED_BYTES', 512), \
                self.assertRaises(PublicationIntentCorruption):
            decode_checkpoint(gzip.compress(b' ' * 513), slot=SLOT, catalog=self.catalog)

    def test_tampered_payload_and_intent_fingerprint_fail_closed(self):
        base = json.loads(gzip.decompress(self.body))
        mutations = [lambda doc: doc['documents'].__setitem__(next(iter(doc['documents'])), '{}'),
                     lambda doc: doc['intent'].__setitem__('input_fingerprint_sha256', '0' * 64)]
        for mutate in mutations:
            value = json.loads(json.dumps(base))
            mutate(value)
            with self.assertRaises((PublicationIntentCorruption, ContractError)):
                decode_checkpoint(gzip.compress(canonical_json_bytes(value)), slot=SLOT, catalog=self.catalog)

    def test_wrong_storage_hash_or_mime_is_rejected(self):
        self.store.put(checkpoint_key(SLOT), self.body, content_type='text/plain')
        with self.assertRaises(PublicationIntentCorruption):
            read_checkpoint(self.store, slot=SLOT, catalog=self.catalog)
        observed = self.store.get(checkpoint_key(SLOT))
        changed = replace(observed, head=replace(observed.head, content_type='application/gzip', sha256='0' * 64))
        with patch.object(self.store, 'get', return_value=changed), self.assertRaises(PublicationIntentCorruption):
            read_checkpoint(self.store, slot=SLOT, catalog=self.catalog)

    def test_changed_authoritative_catalog_rejects_old_checkpoint(self):
        changed_catalog = replace(self.catalog, sha256='0' * 64)
        with self.assertRaises((PublicationIntentCorruption, ContractError)):
            decode_checkpoint(self.body, slot=SLOT, catalog=changed_catalog)


if __name__ == '__main__':
    main()
