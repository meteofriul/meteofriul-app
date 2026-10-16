"""Publication-only ICON recovery: no source acquisition or immutable writes."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import hashlib
import json
import unittest

import test_contract_publisher as fixtures
from local_pipeline.contract_publisher import (
    ContractPublicationVerificationError, ContractV1Publisher,
    ImmutableContractConflict, InvalidContractPublication, LatestCasExhausted,
    StaleContractRun,
)
from local_pipeline.contract_v1 import CAMS_PROVIDER, ICON_PROVIDER, canonical_json_bytes
from local_pipeline.operational_diagnostics import error_fields
from local_pipeline.sqlite_object_store import PreconditionFailed, StoredObject


class FaultStore(fixtures.RecordingStore):
    """One-shot faults before/after the only mutable write; no provider I/O."""
    def __init__(self, inner, fault):
        super().__init__(inner)
        self.fault = fault
        self.pending = True
        self.fail_readback = False

    def compare_and_swap(self, key, body, **kwargs):
        if self.fault == "cas_exhausted":
            self.cas_keys.append(key)
            raise PreconditionFailed(key)
        if self.pending:
            self.pending = False
            if self.fault == "before_cas":
                raise OSError("synthetic pre-commit interruption")
            head = super().compare_and_swap(key, body, **kwargs)
            if self.fault == "lost_response":
                raise OSError("synthetic lost commit response")
            self.fail_readback = self.fault == "readback"
            return head
        return super().compare_and_swap(key, body, **kwargs)

    def get(self, key):
        if self.fail_readback and key.endswith("/latest.json"):
            self.fail_readback = False
            raise OSError("synthetic readback interruption")
        return super().get(key)


class IconPublicationRecoveryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixtures.ContractPublisherTests.setUpClass()
        cls.catalog = fixtures.ContractPublisherTests.catalog
        cls.old = datetime(2026, 9, 7, 12, tzinfo=timezone.utc)
        cls.candidate_run = datetime(2026, 9, 8, 0, tzinfo=timezone.utc)
        cls.new = datetime(2026, 9, 8, 12, tzinfo=timezone.utc)
        cls.template = fixtures.MemoryObjectStore()
        publisher = ContractV1Publisher(cls.template, cls.catalog)
        cls.manifests = {}
        for run in (cls.old, cls.candidate_run, cls.new):
            documents, manifest = fixtures.ContractPublisherTests.icon_bundle(run)
            cls.manifests[run] = manifest
            if run == cls.old:
                publisher.publish_run(ICON_PROVIDER, documents, manifest,
                                      published_at=fixtures.utc(run + timedelta(hours=2)))
            else:
                publisher.stage_run(ICON_PROVIDER, documents, manifest)

    def setUp(self):
        self.memory = fixtures.MemoryObjectStore()
        self.memory.objects = dict(self.template.objects)
        self.memory.generations = dict(self.template.generations)
        self.store = fixtures.RecordingStore(self.memory)
        self.publisher = ContractV1Publisher(self.store, self.catalog, max_cas_attempts=3)
        self.original = self.memory.get(self.publisher.latest_key(ICON_PROVIDER))

    def tearDown(self):
        self.assertEqual(self.store.put_keys, [], "recovery must never write immutable objects")

    def recover(self, run=None, publisher=None, **overrides):
        run = run or self.candidate_run
        manifest = self.manifests[run]
        options = {
            "expected_manifest_sha256": hashlib.sha256(canonical_json_bytes(manifest)).hexdigest(),
            "published_at": fixtures.utc(run + timedelta(hours=2)),
            **overrides,
        }
        return (publisher or self.publisher).publish_existing_run(
            ICON_PROVIDER, manifest["source_run_id"], **options
        )

    def assert_previous_unchanged(self):
        current = self.memory.get(self.original.key)
        self.assertEqual(current.body, self.original.body)
        self.assertEqual(current.etag, self.original.etag)

    def replace(self, key, body, *, metadata=None):
        current = self.memory.get(key)
        self.memory.compare_and_swap(key, body, expected_etag=current.etag,
                                     content_type=current.content_type,
                                     metadata=current.metadata if metadata is None else metadata)

    def test_recovers_all_215_with_only_one_latest_cas(self):
        result = self.recover()
        latest = self.publisher.read_latest(ICON_PROVIDER)
        self.assertEqual(result.source_run_id, "20260908T000000Z")
        self.assertTrue(result.latest_updated)
        self.assertEqual(result.reused_payload_count, 215)
        self.assertTrue(result.manifest_reused)
        self.assertEqual(self.store.cas_keys, [self.original.key])
        self.assertEqual(latest["previous"]["source_run_id"], "20260907T120000Z")
        self.assertEqual(latest["published_at"], "2026-09-08T02:00:00Z")
        read_payloads = [key for key in self.store.get_keys
                         if "/20260908T000000Z/municipalities/" in key]
        self.assertEqual(len(read_payloads), 215)

    def test_repeated_success_is_idempotent_without_extra_revision(self):
        first = self.recover()
        body = self.memory.get(self.original.key).body
        second = self.recover()
        self.assertTrue(second.idempotent)
        self.assertFalse(second.latest_updated)
        self.assertEqual(second.latest_etag, first.latest_etag)
        self.assertEqual(self.memory.get(self.original.key).body, body)
        self.assertEqual(len(self.store.cas_keys), 1)

    def test_missing_manifest_retains_previous(self):
        del self.memory.objects[self.publisher.manifest_key(ICON_PROVIDER, "20260908T000000Z")]
        with self.assertRaises(ContractPublicationVerificationError):
            self.recover()
        self.assert_previous_unchanged()
        self.assertEqual(self.store.cas_keys, [])

    def test_missing_municipality_reports_exact_object_and_retains_previous(self):
        code = self.catalog.istat_codes[111]
        key = self.publisher.payload_key(ICON_PROVIDER, "20260908T000000Z", code)
        del self.memory.objects[key]
        with self.assertRaises(ContractPublicationVerificationError) as caught:
            self.recover()
        diagnostic = error_fields(caught.exception)
        self.assertEqual(diagnostic["stage"], "stored_payload_verification")
        self.assertEqual(diagnostic["municipality_code"], code)
        self.assertEqual(diagnostic["object_key"], key)
        self.assert_previous_unchanged()

    def test_actual_body_hash_is_checked_even_with_forged_stored_head(self):
        code = self.catalog.istat_codes[0]
        key = self.publisher.payload_key(ICON_PROVIDER, "20260908T000000Z", code)
        original = self.memory.get(key)
        body = json.loads(original.body)
        body["hourly"][0]["temperature_c"] += 1
        self.memory.objects[key] = StoredObject(canonical_json_bytes(body), original.head)
        with self.assertRaises(ContractPublicationVerificationError) as caught:
            self.recover()
        self.assertEqual(error_fields(caught.exception)["municipality_code"], code)
        self.assert_previous_unchanged()

    def test_full_payload_schema_not_only_hash_is_checked(self):
        code = self.catalog.istat_codes[0]
        key = self.publisher.payload_key(ICON_PROVIDER, "20260908T000000Z", code)
        original = self.memory.get(key)
        document = json.loads(original.body)
        document["hourly"][0]["temperature_c"] = "invalid"
        body = canonical_json_bytes(document)
        digest = hashlib.sha256(body).hexdigest()
        self.replace(key, body, metadata={**original.metadata, "body_sha256": digest})
        manifest_key = self.publisher.manifest_key(ICON_PROVIDER, "20260908T000000Z")
        stored_manifest = self.memory.get(manifest_key)
        manifest = json.loads(stored_manifest.body)
        manifest["objects"][code].update(json_bytes=len(body), sha256=digest)
        manifest_body = canonical_json_bytes(manifest)
        manifest_hash = hashlib.sha256(manifest_body).hexdigest()
        self.replace(manifest_key, manifest_body,
                     metadata={**stored_manifest.metadata, "body_sha256": manifest_hash})
        with self.assertRaises(ContractPublicationVerificationError) as caught:
            self.recover(expected_manifest_sha256=manifest_hash)
        self.assertEqual(error_fields(caught.exception)["municipality_code"], code)
        self.assert_previous_unchanged()

    def test_intent_fingerprint_mismatch_never_publishes(self):
        with self.assertRaises(ImmutableContractConflict):
            self.recover(expected_manifest_sha256="0" * 64)
        self.assert_previous_unchanged()
        self.assertEqual(self.store.cas_keys, [])

    def test_invalid_fingerprint_is_rejected_without_immutable_reads(self):
        with self.assertRaises(InvalidContractPublication):
            self.recover(expected_manifest_sha256="not-a-digest")
        self.assertEqual(self.store.get_keys, [])

    def test_cams_cannot_bypass_atomic_family_publication(self):
        with self.assertRaises(InvalidContractPublication):
            self.publisher.publish_existing_run(CAMS_PROVIDER, "20260908T000000Z",
                expected_manifest_sha256="0" * 64, published_at="2026-09-08T02:00:00Z")
        self.assert_previous_unchanged()

    def test_publication_timestamp_may_not_regress(self):
        with self.assertRaises(InvalidContractPublication):
            self.recover(published_at="2026-09-07T00:00:00Z")
        self.assert_previous_unchanged()

    def test_newer_latest_cannot_be_downgraded(self):
        self.recover(self.new)
        newest = self.memory.get(self.original.key)
        with self.assertRaises(StaleContractRun):
            self.recover()
        self.assertEqual(self.memory.get(self.original.key).body, newest.body)

    def test_revoked_run_cannot_be_revived(self):
        self.publisher.revoke_run(ICON_PROVIDER, "20260908T000000Z",
                                 published_at="2026-09-08T03:00:00Z")
        revoked = self.memory.get(self.original.key)
        with self.assertRaises(StaleContractRun):
            self.recover()
        self.assertEqual(self.memory.get(self.original.key).body, revoked.body)

    def test_interrupted_commit_retries_only_publication(self):
        for fault in ("before_cas", "lost_response", "readback"):
            with self.subTest(fault=fault):
                self.setUp()
                faulty = FaultStore(self.memory, fault)
                publisher = ContractV1Publisher(faulty, self.catalog)
                with self.assertRaises(OSError):
                    self.recover(publisher=publisher)
                if fault == "before_cas":
                    self.assert_previous_unchanged()
                result = self.recover(publisher=publisher)
                self.assertEqual(result.source_run_id, "20260908T000000Z")
                self.assertEqual(faulty.put_keys, [])
                self.assertEqual(publisher.read_latest(ICON_PROVIDER)["revision"], 2)
                self.assertEqual(len(faulty.cas_keys), 1)

    def test_concurrent_recoveries_share_one_revision_and_original_previous(self):
        store = fixtures.FirstLatestCasBarrierStore(self.memory)
        publisher = ContractV1Publisher(store, self.catalog)
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: self.recover(publisher=publisher), range(2)))
        latest = publisher.read_latest(ICON_PROVIDER)
        self.assertEqual(sum(result.latest_updated for result in results), 1)
        self.assertEqual(latest["revision"], 2)
        self.assertEqual(latest["previous"]["source_run_id"], "20260907T120000Z")
        self.assertEqual(store.put_keys, [])

    def test_cas_budget_exhaustion_retains_previous(self):
        store = FaultStore(self.memory, "cas_exhausted")
        publisher = ContractV1Publisher(store, self.catalog, max_cas_attempts=3)
        with self.assertRaises(LatestCasExhausted):
            self.recover(publisher=publisher)
        self.assertEqual(len(store.cas_keys), 3)
        self.assertEqual(store.put_keys, [])
        self.assert_previous_unchanged()

    def test_concurrent_newer_publication_wins_without_downgrade(self):
        owner = self

        class AdvanceBeforeCas(fixtures.RecordingStore):
            pending = True

            def compare_and_swap(self, key, body, **kwargs):
                if self.pending:
                    self.pending = False
                    owner.recover(owner.new)
                return super().compare_and_swap(key, body, **kwargs)

        store = AdvanceBeforeCas(self.memory)
        with self.assertRaises(StaleContractRun):
            self.recover(publisher=ContractV1Publisher(store, self.catalog))
        latest = self.publisher.read_latest(ICON_PROVIDER)
        self.assertEqual(latest["latest"]["source_run_id"], "20260908T120000Z")
        self.assertEqual(latest["previous"]["source_run_id"], "20260907T120000Z")
        self.assertEqual(store.put_keys, [])

    def test_revocation_immediately_after_commit_is_reported_superseded(self):
        owner = self

        class RevokeAfterCas(fixtures.RecordingStore):
            def compare_and_swap(self, key, body, **kwargs):
                head = super().compare_and_swap(key, body, **kwargs)
                owner.publisher.revoke_run(ICON_PROVIDER, "20260908T000000Z",
                                           published_at="2026-09-08T03:00:00Z")
                return head

        store = RevokeAfterCas(self.memory)
        result = self.recover(publisher=ContractV1Publisher(store, self.catalog))
        self.assertTrue(result.superseded)
        latest = self.publisher.read_latest(ICON_PROVIDER)
        self.assertEqual(latest["latest"]["source_run_id"], "20260907T120000Z")
        self.assertIn("20260908T000000Z", latest["disabled_run_ids"])
        self.assertEqual(store.put_keys, [])

    def test_manifest_generation_change_during_verification_fails_closed(self):
        owner = self
        manifest_key = self.publisher.manifest_key(ICON_PROVIDER, "20260908T000000Z")

        class ChangeManifestGeneration(fixtures.RecordingStore):
            reads = 0

            def get(self, key):
                if key == manifest_key:
                    self.reads += 1
                    if self.reads == 2:
                        current = self.inner.get(key)
                        owner.replace(key, current.body)
                return super().get(key)

        with self.assertRaises(ImmutableContractConflict):
            self.recover(publisher=ContractV1Publisher(ChangeManifestGeneration(self.memory), self.catalog))
        self.assert_previous_unchanged()


if __name__ == "__main__":
    unittest.main()
