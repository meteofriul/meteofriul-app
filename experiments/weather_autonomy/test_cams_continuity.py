"""Continuity publication/read compatibility; no network or ADS calls."""
import copy
import json
from datetime import timedelta
from unittest import TestCase
from unittest.mock import patch
from local_pipeline.cams_continuity import build_cams_continuity, continuity_key, validate_cams_continuity
from local_pipeline.contract_v1 import ContractError, canonical_json_bytes
from local_pipeline.contract_publisher import ContractV1Publisher
from local_pipeline.published_runs_reader import PublishedRunsObjectReader, PublishedRunsReaderError
from local_pipeline.sqlite_object_store import ObjectNotFound
from cams_readback import verify_cams, ReadbackPending
import test_contract_publisher as fixtures

class CamsContinuityTests(TestCase):
    @classmethod
    def setUpClass(cls):
        fixtures.ContractPublisherTests.setUpClass()

    def setUp(self):
        self.h = fixtures.ContractPublisherTests()
        self.h.setUp()
        self.addCleanup(self.h.tearDown)
        self.store = self.h.store
        self.publisher = ContractV1Publisher(self.store, self.h.catalog, cams_continuity=True)
        self.stages = self.h.stage_cams_family(self.h.old)
        self.kwargs = dict(validation_sha256="a"*64, published_at=fixtures.utc(self.h.old+timedelta(hours=11)))
        self.key = continuity_key(self.stages[0].source_run_id)
        self._reader = None

    @property
    def reader(self):
        if self._reader is None:
            self._reader = PublishedRunsObjectReader(self.store, self.h.catalog)
        return self._reader

    def publish(self):
        return self.publisher.release_cams_family(*self.stages, **self.kwargs)

    def test_policy_preserves_original_clock_and_legacy_bytes(self):
        self.publish()
        legacy = fixtures.MemoryObjectStore()
        p = ContractV1Publisher(legacy, self.h.catalog)
        stages = self.h.stage_cams_family(self.h.old, p)
        p.release_cams_family(*stages, **self.kwargs)
        self.assertEqual(set(self.store.objects)-set(legacy.objects), {self.key})
        for key, value in legacy.objects.items():
            self.assertEqual(value.body, self.store.get(key).body, key)
        doc = json.loads(self.reader.get(self.key).body)
        self.assertEqual(doc['fresh_until'], '2026-09-04T00:00:00Z')
        self.assertEqual(doc['usable_until'], '2026-09-04T12:00:00Z')
        self.assertEqual(doc['run_at'], '2026-09-03T00:00:00Z')
        self.assertEqual(self.reader.head(self.key).sha256, self.store.head(self.key).sha256)
        verify_cams(self.store, self.stages[0].source_run_id,
                    lambda key: self.reader.get(key).body, require_continuity=True)

    def test_legacy_active_family_is_never_retrofitted(self):
        self.h.publisher.release_cams_family(*self.stages, **self.kwargs)
        self.assertTrue(self.publish().idempotent)
        self.assertFalse(self.store.exists(self.key))
        verify_cams(self.store, self.stages[0].source_run_id, lambda key: self.reader.get(key).body)
        with self.assertRaises((ObjectNotFound, ReadbackPending)):
            verify_cams(self.store, self.stages[0].source_run_id,
                        lambda key: self.reader.get(key).body, require_continuity=True)

    def test_sidecar_failure_does_not_publish_pointer_and_retry_is_safe(self):
        original = self.store.put
        def fail_policy(key, *args, **kwargs):
            if key == self.key: raise OSError('interrupted policy upload')
            return original(key, *args, **kwargs)
        with patch.object(self.store, 'put', side_effect=fail_policy), self.assertRaises(OSError):
            self.publish()
        self.assertFalse(self.store.exists(self.publisher.cams_family_latest_key()))
        with self.assertRaises((ObjectNotFound, PublishedRunsReaderError)): self.reader.get(self.key)
        self.publish()
        self.assertTrue(self.publish().idempotent)
        self.assertEqual(self.reader.get(self.key).body, self.store.get(self.key).body)

    def test_unpublished_policy_is_not_readable(self):
        with patch.object(self.store, 'compare_and_swap', side_effect=OSError('before CAS')), self.assertRaises(OSError):
            self.publish()
        self.assertTrue(self.store.exists(self.key))
        with self.assertRaises((ObjectNotFound, PublishedRunsReaderError)): self.reader.get(self.key)

    def test_revocation_removes_policy_from_warm_and_cold_reader(self):
        self.publish()
        self.reader.get(self.key)
        newer = self.h.old + timedelta(days=1)
        stages = self.h.stage_cams_family(newer)
        self.publisher.release_cams_family(*stages, validation_sha256='b'*64,
            published_at=fixtures.utc(newer+timedelta(hours=11)))
        self.publisher.revoke_cams_family(self.stages[0].source_run_id,
            published_at=fixtures.utc(newer+timedelta(hours=12)))
        for reader in (self.reader, PublishedRunsObjectReader(self.store, self.h.catalog)):
            with self.assertRaises(ObjectNotFound): reader.get(self.key)
            with self.assertRaises(ObjectNotFound): reader.head(self.key)

    def test_invalid_grant_does_not_break_legacy_reads(self):
        self.publish()
        stored = self.store.get(self.key)
        bad = json.loads(stored.body)
        bad['usable_until'] = '2026-09-05T00:00:00Z'
        self.store.compare_and_swap(self.key, canonical_json_bytes(bad), expected_etag=stored.head.etag,
                                    content_type='application/json')
        with self.assertRaises(PublishedRunsReaderError): self.reader.get(self.key)
        verify_cams(self.store, self.stages[0].source_run_id, lambda key: self.reader.get(key).body)
        current = self.store.get(self.key)
        self.store.compare_and_swap(self.key, b" " * 4097, expected_etag=current.head.etag,
                                    content_type='application/json')
        with self.assertRaisesRegex(PublishedRunsReaderError, "oversized"):
            self.reader.get(self.key)

    def test_strict_binding_rejects_altered_fields(self):
        self.publish()
        release = self.store.get(self.publisher.cams_family_release_key(self.stages[0].source_run_id)).body
        release_doc = json.loads(release)
        policy = build_cams_continuity(release_doc, release)
        for field in policy:
            with self.subTest(field=field), self.assertRaises(ContractError):
                bad = copy.deepcopy(policy)
                bad[field] = None
                validate_cams_continuity(bad, release_doc, release)
        with self.assertRaises(ContractError):
            validate_cams_continuity({**policy, 'extra': True}, release_doc, release)

    def test_http_allowlist_does_not_accept_sibling_or_traversal(self):
        from local_pipeline.http_data_plane import _request_object_key
        self.assertEqual(_request_object_key('/'+self.key), self.key)
        for path in ('continuityXjson', '../continuity.json', 'continuity.json/extra'):
            with self.subTest(path=path), self.assertRaises(ValueError):
                _request_object_key('/'+self.key.replace('continuity.json', path))


class CamsContinuityWorkerTests(TestCase):
    def test_enabling_flag_does_not_extend_existing_legacy_family(self):
        from cloud_worker import _cams_region_step
        from datetime import datetime, timezone
        from unittest.mock import Mock
        import os
        data = fixtures.MemoryObjectStore()
        run = '20260909T000000Z'
        data.put('weather/v1/families/cams/latest.json',canonical_json_bytes({'latest':{'source_run_id':run}}))
        before = dict(data.objects)
        with patch.dict(os.environ, {'WEATHER_CAMS_CONTINUITY_ENABLED': '1'}), \
             patch('local_pipeline.contract_publisher.ContractV1Publisher.read_verified_cams_family_latest',
                   return_value={'latest':{'source_run_id':run}}), \
             patch('cams_readback.verify_cams', return_value={}) as readback, \
             patch('retrieve_remote_cams.retrieve_remote_cams') as retrieve:
            result = _cams_region_step(Mock(),data,datetime(2026,9,9,12,tzinfo=timezone.utc))
        self.assertEqual(result['continuity_status'], 'legacy_no_grant')
        self.assertEqual(data.objects, before)
        readback.assert_called_once_with(data, run)
        retrieve.assert_not_called()

    def test_flag_controls_new_publication_and_public_readback(self):
        from cloud_worker import _cams_region_step
        from datetime import datetime, timezone
        from types import SimpleNamespace
        from unittest.mock import Mock
        import os
        now = datetime(2026,9,9,12,tzinfo=timezone.utc)
        for enabled in ('0','1'):
            data = Mock()
            data.get.side_effect = ObjectNotFound('no existing family')
            state = Mock()
            state.get.side_effect = ObjectNotFound('no saved plan')
            with self.subTest(enabled=enabled), patch.dict(os.environ, {'WEATHER_CAMS_CONTINUITY_ENABLED':enabled}), \
                 patch('cams_request_plan.create_verified_request_plan', return_value={}), \
                 patch('cams_request_plan.encode_request_plan', return_value=b'{}'), \
                 patch('retrieve_remote_cams.retrieve_remote_cams', return_value={'status':'downloaded_pending_decode_validation'}), \
                 patch('publish_remote_cams.restore_remote_cams_prepared', return_value=SimpleNamespace()), \
                 patch('publish_remote_cams.publish_remote_cams') as publish, \
                 patch('cams_readback.verify_cams', return_value={}) as readback:
                result = _cams_region_step(state,data,now)
                self.assertEqual(result['status'],'verified')
                self.assertEqual(result['continuity_status'], 'verified' if enabled == '1' else 'legacy_no_grant')
                self.assertEqual(publish.call_args.kwargs.get('cams_continuity',False), enabled=='1')
                self.assertEqual(readback.call_args.kwargs.get('require_continuity',False), enabled=='1')

    def test_existing_policy_must_pass_public_readback_on_recovery(self):
        from cloud_worker import _cams_region_step
        from datetime import datetime, timezone
        from types import SimpleNamespace
        from unittest.mock import Mock
        data = fixtures.MemoryObjectStore()
        run = '20260909T000000Z'
        data.put('weather/v1/families/cams/latest.json',canonical_json_bytes({'latest':{'source_run_id':run}}))
        data.put(continuity_key(run),b'{}')
        with patch('local_pipeline.contract_publisher.ContractV1Publisher.read_verified_cams_family_latest',
                   return_value={'latest':{'source_run_id':run}}), \
             patch('cams_readback.verify_cams', side_effect=ReadbackPending('policy not publicly readable')) as readback, \
             patch('retrieve_remote_cams.retrieve_remote_cams') as retrieve:
            with self.assertRaises(ReadbackPending):
                _cams_region_step(Mock(),data,datetime(2026,9,9,12,tzinfo=timezone.utc))
            readback.assert_called_once_with(data,run,require_continuity=True)
            retrieve.assert_not_called()
