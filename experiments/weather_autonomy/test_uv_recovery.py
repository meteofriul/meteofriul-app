"""Offline UV recovery fault injection: no credentials or real HTTP traffic."""
import copy
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
from uuid import UUID

import requests
import uv_cloud as subject
from local_pipeline.sqlite_object_store import ObjectHead, StoredObject, ObjectNotFound, PreconditionFailed
from retrieve_cams import ADS_URL

NOW = datetime(2026, 9, 9, 12, tzinfo=timezone.utc)
DAY = '2026-09-09'
PREFIX = 'state/uv/'+DAY+'/'
FAKE_TOKEN = 'synthetic-secret-never-real'
GRIB = b'GRIBsynthetic-UV-field7777'
IDENTIFIER = str(UUID(int=1))


def document(day=DAY):
    run = datetime.fromisoformat(day).replace(tzinfo=timezone.utc)
    return {'schema': 'pilot-uv-v1', 'source': 'CAMS / Copernicus', 'unit': '1',
            'run_at': run.strftime('%Y-%m-%dT00:00:00Z'), 'grid': [[46, 13]],
            'hours': [{'time': (run+timedelta(hours=i)).strftime('%Y-%m-%dT%H:%M:%SZ'),
                       'values': [float(i % 12)]} for i in range(72)]}


def request(day=DAY):
    return {'variable': ['uv_biologically_effective_dose'], 'date': day, 'time': ['00:00'],
            'leadtime_hour': [str(i) for i in range(72)], 'type': ['forecast'],
            'area': [46.8, 12.0, 45.2, 14.4], 'data_format': 'grib'}


class Store:
    def __init__(self, *, state=False):
        self.items, self.generation, self.writes = {}, 0, []
        self.state, self.before, self.after = state, None, None

    def get(self, key):
        if key not in self.items:
            raise ObjectNotFound(key)
        return self.items[key]

    def head(self, key):
        return self.get(key).head

    def put(self, key, body, *, content_type='application/json', metadata=None):
        return self.compare_and_swap(key, body, expected_etag=None, content_type=content_type, metadata=metadata)

    def compare_and_swap(self, key, body, *, expected_etag, content_type='application/json', metadata=None):
        if self.state and expected_etag is not None:
            raise AssertionError('UV state IAM forbids overwrite')
        if self.before:
            self.before(key, body)
        existing = self.items.get(key)
        if (existing.head.etag if existing else None) != expected_etag:
            raise PreconditionFailed(key)
        self.generation += 1
        head = ObjectHead(key, len(body), hashlib.sha256(body).hexdigest(), str(self.generation),
                          content_type, dict(metadata or {}))
        self.items[key] = StoredObject(bytes(body), head)
        self.writes.append(key)
        if self.after:
            self.after(key, body)
        return head


class Response:
    def __init__(self, *, payload=None, body=GRIB, code=200):
        self.payload, self.body, self.status_code = payload, body, code

    def json(self):
        return self.payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(FAKE_TOKEN, response=self)

    def iter_content(self, size):
        yield self.body

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass


class Session:
    def __init__(self):
        self.trust_env = True
        self.get = Mock(return_value=Response(payload={'asset': {'value': {
            'href': 'https://object-store.os-api.cci2.ecmwf.int/result?signature='+FAKE_TOKEN,
            'file:size': len(GRIB)}}}))

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass


class JobPage:
    def __init__(self, identifiers):
        self.request_ids, self.next = identifiers, None

    @property
    def json(self):
        return {'jobs': [{'jobID': identifier} for identifier in self.request_ids],
                'links': [] if self.next is None else [
                    {'rel': 'next', 'href': ADS_URL+'/retrieve/v1/jobs?cursor=test'}]}


class UvRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.state, self.data = Store(state=True), Store()
        self.session = Session()
        self.client = Mock()
        self.jobs = {}
        self.add_job(IDENTIFIER)
        self.client.submit.return_value = SimpleNamespace(request_id=IDENTIFIER, json=self.jobs[IDENTIFIER])
        self.client.get_remote.side_effect = lambda identifier: SimpleNamespace(json=self.jobs[identifier])
        self.client.get_jobs.return_value = JobPage([IDENTIFIER])
        self.network = self.start(patch.object(requests.Session, 'request', side_effect=AssertionError('Network forbidden')))
        self.credentials = self.start(patch('retrieve_cams.load_credentials', return_value=(ADS_URL, FAKE_TOKEN)))
        self.start(patch('retrieve_cams.AdsOnlySession', return_value=self.session))
        self.start(patch('reconcile_cams_job.ReadOnlyAdsSession', return_value=self.session))
        self.factory = self.start(patch('ecmwf.datastores.Client', return_value=self.client))
        self.download = self.start(patch.object(requests, 'get', return_value=Response()))
        self.decoder = self.start(patch.object(subject, 'decode', return_value=document()))
        self.emit = self.start(patch.object(subject, 'emit'))

    def start(self, patcher):
        value = patcher.start()
        self.addCleanup(patcher.stop)
        return value

    def add_job(self, identifier, *, status='successful', seconds=0):
        self.jobs[identifier] = {'jobID': identifier, 'processID': subject.DATASET, 'status': status,
                                 'created': (NOW+timedelta(seconds=seconds)).isoformat(),
                                 'metadata': {'request': {'ids': request()}}}

    def save_job(self, *, legacy=True):
        intent = request() if legacy else {'schema_version': 2, 'dataset': subject.DATASET,
                  'request': request(), 'request_sha256': subject._hash(subject._bytes(request())),
                  'at_utc': NOW.isoformat()}
        self.state.put(PREFIX+'intent.json', subject._bytes(intent))
        self.state.put(PREFIX+'job.json', subject._bytes({'id': IDENTIFIER, 'request': request()}))

    def invoke(self, **options):
        options.setdefault('utc_now', lambda: NOW)
        with TemporaryDirectory(prefix='uv-offline-') as temp:
            result = subject.enrich(self.state, self.data, Path(temp), options.pop('now', NOW), **options)
        self.network.assert_not_called()
        self.assertNotIn(FAKE_TOKEN, json.dumps(result))
        self.assertNotIn(FAKE_TOKEN, str(self.emit.call_args_list))
        for key, value in self.state.items.items():
            self.assertNotIn(FAKE_TOKEN.encode(), value.body)
        return result

    def test_new_request_persists_intent_job_source_decoded_and_append_only_progress(self):
        result = self.invoke()
        self.assertEqual(result['status'], 'published')
        self.assertEqual(result['source_run_id'], '20260909T000000Z')
        self.assertEqual(self.data.get(subject.KEY).body, subject._bytes(document()))
        for name in ('intent.json', 'job.json', 'source.grib', 'decoded.json'):
            self.assertIn(PREFIX+name, self.state.items)
        intent = subject._json(self.state.get(PREFIX+'intent.json').body)
        self.assertEqual(intent['schema_version'], 2)
        self.assertEqual(intent['dataset'], subject.DATASET)
        self.assertEqual(intent['request_sha256'], subject._hash(subject._bytes(request())))
        self.client.submit.assert_called_once_with(subject.DATASET, request())
        self.assertTrue(any('/progress/' in key for key in self.state.writes))

    def test_existing_legacy_job_resumes_without_new_post(self):
        self.save_job()
        self.assertEqual(self.invoke(allow_submit=False)['status'], 'published')
        self.client.submit.assert_not_called()

    def test_pending_is_persisted_and_next_call_reuses_same_job_without_waiting(self):
        self.jobs[IDENTIFIER]['status'] = 'running'
        self.assertEqual(self.invoke()['status'], 'pending')
        self.assertEqual(self.invoke()['status'], 'pending')
        self.client.submit.assert_called_once()
        self.download.assert_not_called()
        progress = [subject._json(value.body) for key, value in self.state.items.items() if '/progress/' in key]
        self.assertEqual(sum(row['status'] == 'pending' for row in progress), 2)
        self.jobs[IDENTIFIER]['status'] = 'successful'
        self.assertEqual(self.invoke()['status'], 'published')

    def test_interruption_after_source_checkpoint_does_not_download_again(self):
        self.decoder.side_effect = [TimeoutError('synthetic'), document()]
        self.assertEqual(self.invoke()['status'], 'retryable_failure')
        self.assertIn(PREFIX+'source.grib', self.state.items)
        self.assertNotIn(PREFIX+'decoded.json', self.state.items)
        self.assertEqual(self.invoke()['status'], 'published')
        self.download.assert_called_once()
        self.credentials.assert_called_once()

    def test_publication_failure_resumes_only_publication_with_previous_latest_intact(self):
        old = subject._bytes(document('2026-09-08'))
        self.data.put(subject.KEY, old)
        self.data.before = Mock(side_effect=TimeoutError('synthetic'))
        self.assertEqual(self.invoke()['status'], 'retryable_failure')
        self.assertEqual(self.data.get(subject.KEY).body, old)
        self.data.before = None
        self.assertEqual(self.invoke()['status'], 'published')
        self.download.assert_called_once()
        self.decoder.assert_called_once()
        self.credentials.assert_called_once()

    def test_lost_cas_response_is_verified_as_published(self):
        def lost(key, body):
            self.data.after = None
            raise TimeoutError('synthetic lost success')
        self.data.after = lost
        self.assertEqual(self.invoke()['status'], 'published')
        self.assertEqual(self.data.get(subject.KEY).body, subject._bytes(document()))

    def test_lost_checkpoint_response_reuses_verified_object(self):
        def lost(key, body):
            if key.endswith('decoded.json'):
                self.state.after = None
                raise TimeoutError('lost decoded write response')
        self.state.after = lost
        self.assertEqual(self.invoke()['status'], 'published')

    def test_newer_latest_wins_concurrent_cas_without_downgrade(self):
        newer = subject._bytes(document('2026-09-10'))
        def race(key, body):
            self.data.before = None
            self.data.put(key, newer)
        self.data.before = race
        result = self.invoke()
        self.assertEqual((result['status'], result['reason_code']), ('no_op', 'uv_superseded'))
        self.assertEqual(result['source_run_id'], '20260910T000000Z')
        self.assertEqual(self.data.get(subject.KEY).body, newer)

    def test_legacy_intent_without_timestamp_is_not_false_absence(self):
        self.state.put(PREFIX+'intent.json', subject._bytes(request()))
        result = self.invoke()
        self.assertEqual(result['reason_code'], 'uv_reconciliation_timestamp_missing')
        self.credentials.assert_not_called()
        self.client.submit.assert_not_called()

    def test_generation_pinned_legacy_timestamp_allows_unique_existing_job_recovery(self):
        self.state.put(PREFIX+'intent.json', subject._bytes(request()))
        callback = Mock(return_value=NOW)
        self.assertEqual(self.invoke(legacy_intent_timestamp=callback)['status'], 'published')
        callback.assert_called_once_with(PREFIX+'intent.json', self.state.head(PREFIX+'intent.json').etag)
        self.client.get_jobs.assert_called_once_with(limit=20, sortby='-created')
        self.client.submit.assert_not_called()

    def test_post_response_lost_then_get_reconciliation_never_submits_twice(self):
        self.client.submit.side_effect = requests.Timeout(FAKE_TOKEN)
        first = self.invoke()
        self.assertEqual((first['status'], first['reason_code']), ('reconciling', 'uv_submission_uncertain'))
        self.assertNotIn(PREFIX+'job.json', self.state.items)
        self.assertEqual(self.invoke()['status'], 'published')
        self.client.submit.assert_called_once()

    def test_no_match_in_open_submission_window_never_authorizes_replacement_post(self):
        self.state.put(PREFIX+'intent.json', subject._bytes(request()))
        self.client.get_jobs.return_value.request_ids = []
        result = self.invoke(legacy_intent_timestamp=lambda *args: NOW)
        self.assertEqual(result['reason_code'], 'uv_submission_visibility_window_open')
        self.client.submit.assert_not_called()

    def test_multiple_matches_and_incomplete_page_never_authorize_post(self):
        self.state.put(PREFIX+'intent.json', subject._bytes(request()))
        second = str(UUID(int=2))
        self.add_job(second, seconds=0)
        self.client.get_jobs.return_value.request_ids = [IDENTIFIER, second]
        self.assertEqual(self.invoke(legacy_intent_timestamp=lambda *args: NOW)['reason_code'],
                         'uv_reconciliation_multiple_matches')
        identifiers = [str(UUID(int=i)) for i in range(1, 21)]
        for i, identifier in enumerate(identifiers):
            self.add_job(identifier, seconds=20-i)
        self.client.get_jobs.return_value.request_ids = identifiers
        self.assertEqual(self.invoke(legacy_intent_timestamp=lambda *args: NOW)['reason_code'],
                         'uv_reconciliation_inconclusive')
        self.client.submit.assert_not_called()

    def test_short_page_with_next_link_is_inconclusive_not_unique(self):
        self.state.put(PREFIX+'intent.json', subject._bytes(request()))
        self.client.get_jobs.return_value.next = SimpleNamespace(request_ids=[])
        result = self.invoke(legacy_intent_timestamp=lambda *args: NOW)
        self.assertEqual((result['status'], result['reason_code']),
                         ('reconciling', 'uv_reconciliation_inconclusive'))
        self.client.submit.assert_not_called()
        self.assertNotIn(PREFIX+'job.json', self.state.items)

    def test_lost_intent_write_response_never_authorizes_post(self):
        def lost(key, body):
            if key.endswith('intent.json'):
                self.state.after = None
                raise TimeoutError('intent persisted but reply lost')
        self.state.after = lost
        self.assertEqual(self.invoke()['status'], 'reconciling')
        self.client.submit.assert_not_called()
        self.client.get_jobs.return_value.request_ids = []
        self.assertEqual(self.invoke()['reason_code'], 'uv_submission_visibility_window_open')
        self.client.submit.assert_not_called()

    def test_conflicting_decoded_checkpoint_is_not_replaced(self):
        def race(key, body):
            if key.endswith('decoded.json'):
                self.state.before = None
                self.state.put(key, b'{}')
        self.state.before = race
        self.assertEqual(self.invoke()['reason_code'], 'uv_checkpoint_conflict')
        self.assertEqual(self.state.get(PREFIX+'decoded.json').body, b'{}')
        self.assertNotIn(subject.KEY, self.data.items)

    def test_legacy_timestamp_missing_or_naive_never_reads_provider(self):
        self.state.put(PREFIX+'intent.json', subject._bytes(request()))
        self.assertEqual(self.invoke(legacy_intent_timestamp=lambda *args: None)['reason_code'],
                         'uv_reconciliation_timestamp_missing')
        self.assertEqual(self.invoke(legacy_intent_timestamp=lambda *args: NOW.replace(tzinfo=None))['reason_code'],
                         'uv_intent_timestamp_invalid')
        self.credentials.assert_not_called()

    def test_before_ten_utc_keeps_existing_previous_day_selection(self):
        self.decoder.return_value = document('2026-09-08')
        self.assertEqual(self.invoke(now=NOW.replace(hour=5))['source_run_id'], '20260908T000000Z')
        self.client.submit.assert_called_once_with(subject.DATASET, request('2026-09-08'))

    def test_intent_and_progress_use_post_time_not_frozen_run_selection_clock(self):
        actual = NOW+timedelta(minutes=12)
        self.invoke(utc_now=lambda: actual)
        intent = subject._json(self.state.get(PREFIX+'intent.json').body)
        self.assertEqual(intent['at_utc'], actual.isoformat().replace('+00:00', 'Z'))
        progress = [subject._json(value.body) for key, value in self.state.items.items() if '/progress/' in key]
        self.assertTrue(all(row['updated_at'] == actual.isoformat().replace('+00:00', 'Z') for row in progress))
        self.assertEqual(intent['request']['date'], DAY)

    def test_existing_newer_latest_returns_served_run_id_for_public_readback(self):
        self.data.put(subject.KEY, subject._bytes(document('2026-09-10')))
        result = self.invoke()
        self.assertEqual((result['status'], result['source_run_id']), ('no_op', '20260910T000000Z'))
        self.credentials.assert_not_called()

    def test_wrong_request_intent_fails_before_loading_credentials(self):
        self.state.put(PREFIX+'intent.json', subject._bytes({**request(), 'date': '2026-09-08'}))
        self.assertEqual(self.invoke()['reason_code'], 'uv_intent_mismatch')
        self.credentials.assert_not_called()

    def test_unauthorized_submission_retains_http_status_without_secrets(self):
        self.client.submit.side_effect = requests.HTTPError(FAKE_TOKEN, response=Response(code=403))
        result = self.invoke()
        self.assertEqual((result['status'], result['stage'], result['http_status']),
                         ('permanent_failure', 'submission', 403))

    def test_redirect_or_oversized_download_is_never_checkpointed(self):
        self.download.return_value.status_code = 302
        self.assertEqual(self.invoke()['reason_code'], 'uv_download_redirect_refused')
        self.assertNotIn(PREFIX+'source.grib', self.state.items)
        self.download.return_value.status_code = 200
        self.session.get.return_value.payload['asset']['value']['file:size'] = subject.MAX_SOURCE_BYTES
        self.assertEqual(self.invoke()['reason_code'], 'uv_download_size_invalid')

    def test_terminal_remote_failure_preserves_old_latest(self):
        self.data.put(subject.KEY, subject._bytes(document('2026-09-08')))
        self.jobs[IDENTIFIER]['status'] = 'failed'
        self.assertEqual(self.invoke()['status'], 'permanent_failure')
        self.assertEqual(subject._json(self.data.get(subject.KEY).body)['run_at'][:10], '2026-09-08')
        self.download.assert_not_called()

    def test_current_valid_latest_is_noop_without_credentials(self):
        self.data.put(subject.KEY, subject._bytes(document()))
        self.assertEqual(self.invoke()['status'], 'no_op')
        self.credentials.assert_not_called()

    def test_decoded_metadata_tampering_fails_closed_not_redownload(self):
        self.data.before = Mock(side_effect=TimeoutError('synthetic'))
        self.invoke()
        self.data.before = None
        self.state.get(PREFIX+'decoded.json').head.metadata['request-sha256'] = '0'*64
        self.assertEqual(self.invoke()['reason_code'], 'uv_checkpoint_integrity_failed')
        self.download.assert_called_once()
        self.decoder.assert_called_once()

    def test_decoded_body_tampering_with_valid_storage_hash_still_rejected(self):
        self.data.before = Mock(side_effect=TimeoutError('synthetic'))
        self.invoke()
        self.data.before = None
        key = PREFIX+'decoded.json'
        old = self.state.items.pop(key)
        changed = subject._json(old.body)
        changed['document']['hours'][0]['values'] = [999]
        self.state.put(key, subject._bytes(changed), metadata=old.head.metadata)
        self.assertEqual(self.invoke()['reason_code'], 'uv_document_invalid')
        self.download.assert_called_once()

    def test_recovery_mode_without_intent_never_submits(self):
        self.assertEqual(self.invoke(allow_submit=False)['reason_code'], 'uv_recovery_requires_intent')
        self.credentials.assert_not_called()


class UvDocumentTests(unittest.TestCase):
    def test_complete_72_hours_accepts_real_zero_values(self):
        self.assertEqual(subject.validate_document(document(), DAY), document())

    def test_missing_duplicate_wrong_run_bad_grid_and_boolean_values_fail(self):
        variants = []
        value = document(); value['hours'].pop(); variants.append(value)
        value = document(); value['hours'][1] = copy.deepcopy(value['hours'][0]); variants.append(value)
        value = document(); value['run_at'] = '2026-09-09T01:00:00Z'; variants.append(value)
        value = document(); value['grid'][0][0] = 99; variants.append(value)
        value = document(); value['hours'][0]['values'][0] = True; variants.append(value)
        for value in variants:
            with self.subTest(value=value['run_at']), self.assertRaises(subject.UvStateError):
                subject.validate_document(value, DAY)


if __name__ == '__main__':
    unittest.main()
