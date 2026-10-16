"""Replacement authorization faults; entirely offline, real state transitions."""
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
import json
from threading import Barrier, Event, RLock
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch
from uuid import UUID

import requests
import test_uv_recovery as fixtures
import uv_cloud as uv
from uv_attempts import Attempts
from cams_readback import verify_uv

NOW, PREFIX = fixtures.NOW, fixtures.PREFIX
OLD_TIME = NOW - timedelta(hours=2)
NEW_ID = str(UUID(int=2))


class AtomicStore(fixtures.Store):
    def __init__(self):
        super().__init__(state=True)
        self.lock, self.claim_barrier = RLock(), None

    def put(self, key, body, **kwargs):
        if self.claim_barrier is not None and key.endswith('canonical-attempt.json'):
            self.claim_barrier.wait(timeout=10)
        with self.lock:
            return super().put(key, body, **kwargs)


class ReplacementTests(TestCase):
    def setUp(self):
        self.fx = fixtures.UvRecoveryTests()
        self.addCleanup(self.fx.doCleanups)
        self.fx.setUp()
        self.fx.state = AtomicStore()
        self.old_bytes = uv._bytes(fixtures.request())
        self.fx.state.put(PREFIX+'intent.json', self.old_bytes)
        self.fx.client.get_jobs.return_value = fixtures.JobPage([])
        self.fx.add_job(NEW_ID)
        self.fx.add_job(fixtures.IDENTIFIER, seconds=-7199)

        def accepted(*args):
            self.fx.client.get_jobs.return_value.request_ids = [NEW_ID]
            return SimpleNamespace(request_id=NEW_ID, json=self.fx.jobs[NEW_ID])
        self.fx.client.submit.side_effect = accepted

    def call(self, at=NOW, **kwargs):
        return self.fx.invoke(legacy_intent_timestamp=lambda *args: OLD_TIME,
                              utc_now=lambda: at, **kwargs)

    def selection(self):
        return uv._json(self.fx.state.get(PREFIX+'canonical-attempt.json').body)

    def test_conclusive_empty_search_creates_one_identified_attempt_and_preserves_history(self):
        result = self.call()
        self.assertEqual(result['status'], 'published')
        self.fx.client.submit.assert_called_once_with(uv.DATASET, fixtures.request())
        selected = self.selection()
        self.assertEqual(selected['attempt'], 2)
        self.assertEqual(selected['source_run_id'], '20260909T000000Z')
        history = uv._json(self.fx.state.get(selected['history_key']).body)
        self.assertEqual(history['status'], 'conclusive_no_match')
        self.assertEqual(history['original_intent'], fixtures.request())
        self.assertEqual(history['evidence']['matched_ids'], [])
        self.assertTrue(history['evidence']['complete'])
        self.assertEqual(self.fx.state.get(PREFIX+'intent.json').body, self.old_bytes)
        self.assertNotEqual(selected['attempt_id'], history['attempt_id'])
        path = PREFIX+'attempts/replacement-1/'
        for artifact in ('job.json', 'source.grib', 'decoded.json'):
            self.assertIn(path+artifact, self.fx.state.items)
            self.assertNotIn(PREFIX+artifact, self.fx.state.items)
        self.assertLess(self.fx.state.writes.index(path+'job.json'), self.fx.state.writes.index(path+'source.grib'))
        calls = []
        def endpoint(key):
            calls.append(key)
            return self.fx.data.get(key).body
        self.assertIn('readback_sha256', verify_uv(self.fx.data, '20260909T000000Z', endpoint))
        self.assertEqual(len(calls), 2)

    def test_two_concurrent_replacement_workers_submit_once(self):
        self.fx.state.claim_barrier = Barrier(2)
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: self.call(), range(2)))
        self.fx.client.submit.assert_called_once()
        self.assertEqual(sum(r['status'] == 'published' for r in results), 1)
        self.assertEqual(sum(r['reason_code'] == 'uv_attempt_already_selected' for r in results), 1)
        self.assertEqual(self.selection()['attempt'], 2)

    def test_lost_post_response_reconciles_same_new_job_without_second_post(self):
        def lost(*args):
            self.fx.client.get_jobs.return_value.request_ids = [NEW_ID]
            raise requests.Timeout('synthetic lost accepted response')
        self.fx.client.submit.side_effect = lost
        self.assertEqual(self.call()['status'], 'reconciling')
        self.assertNotIn(PREFIX+'attempts/replacement-1/job.json', self.fx.state.items)
        self.assertEqual(self.call()['status'], 'published')
        self.fx.client.submit.assert_called_once()

    def test_lost_claim_ack_cannot_authorize_post_or_reclaim(self):
        def lost(key, body):
            if key.endswith('canonical-attempt.json'):
                self.fx.state.after = None
                raise TimeoutError('selection committed but ACK lost')
        self.fx.state.after = lost
        self.assertEqual(self.call()['status'], 'reconciling')
        self.fx.client.submit.assert_not_called()
        result = self.call(NOW+timedelta(minutes=10))
        self.assertEqual(result['reason_code'], 'uv_replacement_exhausted_no_match')
        self.fx.client.submit.assert_not_called()

    def test_late_old_job_is_superseded_and_not_downloaded_or_published_twice(self):
        self.fx.jobs[NEW_ID]['status'] = 'running'
        self.assertEqual(self.call()['status'], 'pending')
        self.fx.client.get_jobs.return_value.request_ids = [NEW_ID, fixtures.IDENTIFIER]
        self.fx.jobs[NEW_ID]['status'] = 'successful'
        self.assertEqual(self.call()['status'], 'published')
        duplicate = uv._json(self.fx.state.get(PREFIX+'superseded/'+fixtures.IDENTIFIER+'.json').body)
        self.assertEqual(duplicate['status'], 'superseded')
        self.assertEqual(duplicate['canonical_attempt_id'], self.selection()['attempt_id'])
        later = str(UUID(int=3))
        self.fx.add_job(later, seconds=-7198)
        self.fx.client.get_jobs.return_value.request_ids = [NEW_ID, later, fixtures.IDENTIFIER]
        self.assertEqual(self.call()['status'], 'no_op')
        self.assertIn(PREFIX+'superseded/'+later+'.json', self.fx.state.items)
        self.assertEqual(self.fx.data.writes.count(uv.KEY), 1)
        self.fx.download.assert_called_once()
        self.fx.client.submit.assert_called_once()

    def test_original_reference_winning_selection_prevents_replacement_post(self):
        manager = Attempts(self.fx.state, PREFIX, fixtures.request(),
                           self.fx.state.get(PREFIX+'intent.json'), OLD_TIME)
        def old_wins(key, body):
            if key.endswith('canonical-attempt.json'):
                self.fx.state.before = None
                selected = manager.choose_original(NOW, fixtures.IDENTIFIER)
                manager.record_remote(selected, fixtures.IDENTIFIER)
        self.fx.state.before = old_wins
        self.assertEqual(self.call()['reason_code'], 'uv_attempt_already_selected')
        self.fx.client.submit.assert_not_called()
        self.assertEqual(self.call()['status'], 'published')
        self.assertEqual(self.selection()['attempt'], 1)

    def test_original_post_returning_after_replacement_is_fenced(self):
        # Original invocation pauses inside the provider after its intent write.
        self.fx.state = AtomicStore()
        started, release_original = Event(), Event()
        def submit(*args):
            if not started.is_set():
                started.set()
                if not release_original.wait(timeout=10):
                    raise AssertionError('replacement did not finish')
                return SimpleNamespace(request_id=fixtures.IDENTIFIER, json=self.fx.jobs[fixtures.IDENTIFIER])
            self.fx.client.get_jobs.return_value.request_ids = [NEW_ID]
            return SimpleNamespace(request_id=NEW_ID, json=self.fx.jobs[NEW_ID])
        self.fx.client.submit.side_effect = submit
        with ThreadPoolExecutor(max_workers=1) as pool:
            original = pool.submit(self.call, OLD_TIME)
            self.assertTrue(started.wait(timeout=10))
            try:
                self.assertEqual(self.call()['status'], 'published')
            finally:
                release_original.set()
            stale = original.result(timeout=10)
        self.assertEqual(stale['reason_code'], 'uv_attempt_superseded')
        self.assertEqual(self.fx.client.submit.call_count, 2)  # original + ONE replacement
        self.fx.download.assert_called_once()
        self.assertEqual(self.fx.data.writes.count(uv.KEY), 1)
        self.assertIn(PREFIX+'superseded/'+fixtures.IDENTIFIER+'.json', self.fx.state.items)
        self.assertNotIn(PREFIX+'source.grib', self.fx.state.items)

    def test_ambiguous_replacement_with_no_reference_never_gets_third_post(self):
        self.fx.client.submit.side_effect = requests.Timeout('synthetic uncertain submission')
        self.assertEqual(self.call()['status'], 'reconciling')
        for minutes in (10, 30):
            result = self.call(NOW+timedelta(minutes=minutes))
            self.assertEqual(result['reason_code'], 'uv_replacement_exhausted_no_match')
        self.fx.client.submit.assert_called_once()

    def test_transient_error_and_incomplete_search_do_not_claim(self):
        cases = [requests.Timeout('synthetic'),
                 requests.HTTPError('synthetic', response=fixtures.Response(code=503)),
                 SimpleNamespace(request_ids=[])]
        for value in cases:
            with self.subTest(value=type(value).__name__):
                self.fx.client.get_jobs.side_effect = value if isinstance(value, Exception) else None
                if not isinstance(value, Exception):
                    self.fx.client.get_jobs.return_value = value
                self.assertIn(self.call()['status'], ('reconciling', 'retryable_failure'))
                self.assertNotIn(PREFIX+'canonical-attempt.json', self.fx.state.items)
                self.fx.client.submit.assert_not_called()

    def test_other_run_cannot_reuse_history_or_selection(self):
        self.assertEqual(self.call()['status'], 'published')
        original = self.fx.state.get(PREFIX+'intent.json')
        different = {**fixtures.request(), 'date': '2026-09-10'}
        manager = Attempts(self.fx.state, PREFIX, different, original, OLD_TIME)
        with self.assertRaises(uv.UvStateError):
            manager.read()

    def test_verified_bucket_migration_may_change_only_the_intent_etag(self):
        original = self.fx.state.get(PREFIX+'intent.json')
        manager = Attempts(self.fx.state, PREFIX, fixtures.request(), original, OLD_TIME)
        expected = manager.choose_original(NOW, fixtures.IDENTIFIER)
        head = original.head
        migrated_head = head.__class__(head.key, head.byte_length, head.sha256,
                                       'migrated-gcs-etag', head.content_type, head.metadata)
        self.fx.state.items[PREFIX+'intent.json'] = original.__class__(original.body, migrated_head)
        migrated = Attempts(self.fx.state, PREFIX, fixtures.request(),
                            self.fx.state.get(PREFIX+'intent.json'), OLD_TIME)
        with self.assertRaises(uv.UvStateError):
            migrated.read()
        with patch.dict('os.environ', {'WEATHER_STATE_MIGRATED': '1'}):
            self.assertEqual(migrated.read(), expected)

    def test_lost_remote_checkpoint_ack_reuses_saved_id(self):
        def lost(key, body):
            if key.endswith('replacement-1/job.json'):
                self.fx.state.after = None
                raise TimeoutError('remote id persisted but response lost')
        self.fx.state.after = lost
        self.assertEqual(self.call()['status'], 'published')
        self.fx.client.submit.assert_called_once()

    def test_original_selection_cannot_resume_another_remote_reference(self):
        manager = Attempts(self.fx.state, PREFIX, fixtures.request(),
                           self.fx.state.get(PREFIX+'intent.json'), OLD_TIME)
        manager.choose_original(NOW, fixtures.IDENTIFIER)
        self.fx.state.put(PREFIX+'job.json', uv._bytes({'id': NEW_ID, 'request': fixtures.request()}))
        self.assertEqual(self.call()['reason_code'], 'uv_canonical_remote_conflict')
        self.fx.client.submit.assert_not_called()
        self.fx.download.assert_not_called()

    def test_unique_match_with_unconfirmed_post_origin_still_freezes_one_canonical_id(self):
        def lost(*args):
            raise requests.Timeout('synthetic response lost')
        self.fx.client.submit.side_effect = lost
        self.assertEqual(self.call()['status'], 'reconciling')
        # Same request can be accepted late. ADS cannot attest which POST created
        # a GET match: preserve uncertainty, but never run two canonical jobs.
        self.fx.add_job(fixtures.IDENTIFIER, seconds=1)
        self.fx.client.get_jobs.return_value.request_ids = [fixtures.IDENTIFIER]
        self.assertEqual(self.call(NOW+timedelta(seconds=2))['status'], 'published')
        reference = uv._json(self.fx.state.get(PREFIX+'attempts/replacement-1/remote-selection.json').body)
        self.assertEqual(reference['origin'], 'unique_exact_match_origin_unconfirmed')
        self.assertEqual(reference['remote_id'], fixtures.IDENTIFIER)
        self.fx.add_job(NEW_ID, seconds=2)
        self.fx.client.get_jobs.return_value.request_ids = [NEW_ID, fixtures.IDENTIFIER]
        self.assertEqual(self.call(NOW+timedelta(seconds=3))['status'], 'no_op')
        self.assertIn(PREFIX+'superseded/'+NEW_ID+'.json', self.fx.state.items)
        manager = Attempts(self.fx.state, PREFIX, fixtures.request(),
                           self.fx.state.get(PREFIX+'intent.json'), OLD_TIME)
        manager.supersede(self.selection(), fixtures.IDENTIFIER)
        self.assertNotIn(PREFIX+'superseded/'+fixtures.IDENTIFIER+'.json', self.fx.state.items)
        self.assertIn(PREFIX+'observations/'+fixtures.IDENTIFIER+'.json', self.fx.state.items)
        self.assertEqual(self.fx.data.writes.count(uv.KEY), 1)
        self.fx.download.assert_called_once()
        self.fx.client.submit.assert_called_once()

    def test_crash_after_remote_selection_restores_reference_before_any_new_lookup(self):
        def crash(key, body):
            if key.endswith('remote-selection.json'):
                self.fx.state.after = None
                raise KeyboardInterrupt()
        self.fx.state.after = crash
        with self.assertRaises(KeyboardInterrupt):
            self.call()
        self.assertNotIn(PREFIX+'attempts/replacement-1/job.json', self.fx.state.items)
        self.assertEqual(self.call()['status'], 'published')
        self.fx.client.submit.assert_called_once()
        reference = uv._json(self.fx.state.get(PREFIX+'attempts/replacement-1/remote-selection.json').body)
        self.assertEqual(reference['origin'], 'post_response')

    def test_replacement_publication_retry_reuses_validated_artifacts(self):
        self.fx.data.put(uv.KEY, uv._bytes(fixtures.document('2026-09-08')))
        def unavailable(*args):
            raise TimeoutError('synthetic publication transport outage')
        self.fx.data.before = unavailable
        self.assertEqual(self.call()['status'], 'retryable_failure')
        self.assertEqual(uv._json(self.fx.data.get(uv.KEY).body)['run_at'][:10], '2026-09-08')
        self.fx.data.before = None
        self.assertEqual(self.call()['status'], 'published')
        self.fx.client.submit.assert_called_once()
        self.fx.download.assert_called_once()
        self.fx.decoder.assert_called_once()

    def test_original_creator_stalled_before_post_loses_submission_authority(self):
        self.fx.state = AtomicStore()
        clock = [NOW]
        def delay(key, body):
            if key.endswith('intent.json'):
                clock[0] += timedelta(minutes=2)
        self.fx.state.after = delay
        result = self.fx.invoke(utc_now=lambda: clock[0])
        self.assertEqual(result['reason_code'], 'uv_submission_claim_expired')
        self.fx.client.submit.assert_not_called()

    def test_late_original_observation_racing_remote_selection_never_supersedes_canonical_id(self):
        def crash(key, body):
            if key.endswith('canonical-attempt.json'):
                self.fx.state.after = None
                raise KeyboardInterrupt()
        self.fx.state.after = crash
        with self.assertRaises(KeyboardInterrupt):
            self.call()
        manager = Attempts(self.fx.state, PREFIX, fixtures.request(),
                           self.fx.state.get(PREFIX+'intent.json'), OLD_TIME)
        selected = manager.read()
        reached, proceed = Event(), Event()
        original_reference = manager._reference
        def absent_then_concurrent_selection(selection):
            reached.set()
            if not proceed.wait(timeout=10):
                raise AssertionError('canonical write did not finish')
            return None  # Snapshot from just before the concurrent write.
        manager._reference = absent_then_concurrent_selection
        with ThreadPoolExecutor(max_workers=1) as pool:
            observer = pool.submit(manager.supersede, selected, NEW_ID)
            self.assertTrue(reached.wait(timeout=10))
            try:
                writer = Attempts(self.fx.state, PREFIX, fixtures.request(),
                                  self.fx.state.get(PREFIX+'intent.json'), OLD_TIME)
                writer.record_remote(selected, NEW_ID)
            finally:
                proceed.set()
            observer.result(timeout=10)
        manager._reference = original_reference
        manager.supersede(selected, NEW_ID)
        self.assertNotIn(PREFIX+'superseded/'+NEW_ID+'.json', self.fx.state.items)
        self.assertIn(PREFIX+'observations/original-'+NEW_ID+'.json', self.fx.state.items)
        self.assertEqual(manager._reference(selected)['remote_id'], NEW_ID)
