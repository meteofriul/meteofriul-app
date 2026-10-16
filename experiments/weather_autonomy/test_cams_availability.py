import json
import os
from contextlib import redirect_stdout
from datetime import datetime, timedelta, timezone
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import Mock, patch

from cams_request_plan import PublicMetadataError, PublicMetadataUnavailable
from cams_runtime import source_deferral, next_schedule_at, retry_reserve, TASK_TIMEOUT_SECONDS
from cloud_worker import _run_cams
from local_pipeline.operational_diagnostics import attach_error_fields
from local_pipeline.sqlite_object_store import SQLiteObjectStore

EARLY = datetime(2026, 10, 16, 9, tzinfo=timezone.utc)
VERIFIED = {'status': 'verified', 'source_run_id': '20261016T000000Z'}
PENDING = {'status': 'remote_pending', 'source_run_id': '20261016T000000Z'}

def unavailable(reason='constraints_incomplete_leads', cls=PublicMetadataUnavailable):
    error = cls('source not ready')
    attach_error_fields(error, reason_code=reason, leadcount=25, maxlead=24)
    return error

class AvailabilityPolicyTests(TestCase):
    def test_only_expected_pre_deadline_incompleteness_is_deferred(self):
        for reason in ('constraints_incomplete_leads', 'constraints_no_date_rows',
                       'catalogue_date_unavailable', 'form_date_unavailable'):
            with self.subTest(reason=reason):
                result = source_deferral(unavailable(reason), EARLY)
                self.assertEqual(result['status'], 'source_pending')
                self.assertEqual(result['next_schedule_at'], '2026-10-16T10:00:00Z')
        for reason in ('constraints_multiple_compatible_rows', 'constraints_no_compatible_rows',
                       'catalogue_disabled', 'catalogue_sanity_unavailable', 'public_metadata_unavailable'):
            with self.subTest(reason=reason):
                self.assertIsNone(source_deferral(unavailable(reason), EARLY))
        self.assertIsNone(source_deferral(unavailable(cls=PublicMetadataError), EARLY))
        self.assertIsNone(source_deferral(ConnectionError('network'), EARLY))

    def test_deadline_is_utc_and_has_no_silent_late_grace(self):
        self.assertIsNotNone(source_deferral(unavailable(), EARLY.replace(hour=9, minute=59)))
        self.assertIsNone(source_deferral(unavailable(), EARLY.replace(hour=10)))
        self.assertIsNone(source_deferral(unavailable(),
            datetime(2026, 10, 16, 12, tzinfo=timezone(timedelta(hours=2)))))
        with self.assertRaises(ValueError):
            source_deferral(unavailable(), EARLY.replace(tzinfo=None))

    def test_next_slot_and_day_rollover_preserve_utc_across_dst(self):
        self.assertEqual(next_schedule_at(EARLY.replace(hour=8, minute=59)), '2026-10-16T09:00:00Z')
        self.assertEqual(next_schedule_at(EARLY.replace(hour=11)), '2026-10-16T15:00:00Z')
        self.assertEqual(next_schedule_at(EARLY.replace(hour=20)), '2026-10-17T09:00:00Z')
        self.assertEqual(next_schedule_at(datetime(2026, 10, 25, 10, tzinfo=timezone(timedelta(hours=1)))),
                         '2026-10-25T10:00:00Z')

    def test_retry_reserves_both_components_and_skips_terminal_ones(self):
        self.assertEqual(retry_reserve({'air': PENDING, 'uv': PENDING}), 660)
        self.assertEqual(retry_reserve({'air': VERIFIED, 'uv': PENDING}), 180)
        self.assertEqual(retry_reserve({'air': PENDING, 'uv': {'status': 'disabled'}}), 480)
        self.assertEqual(retry_reserve({'air': {'status': 'source_pending'}, 'uv': {'status': 'disabled'}}), 0)

class AvailabilityWorkerTests(TestCase):
    def setUp(self):
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.state = SQLiteObjectStore(Path(directory.name)/'state.sqlite')
        self.data = SQLiteObjectStore(Path(directory.name)/'data.sqlite')
        self.output = StringIO()

    def run_worker(self, now=EARLY, **kwargs):
        kwargs.setdefault('wait', Mock())
        kwargs.setdefault('clock', lambda: 0)
        with patch.dict(os.environ, {'WEATHER_UV_ENABLED': '1', 'WEATHER_UV_UTC_HOURS': '15,20'}, clear=True), redirect_stdout(self.output):
            return _run_cams(self.state, self.data, now, **kwargs)

    def test_live_metadata_deferral_never_submits_or_relabels_old_family(self):
        key = 'weather/v1/families/cams/latest.json'
        previous = b'{"latest":{"source_run_id":"20261015T000000Z"},"published_at":"2026-10-15T22:22:52Z"}'
        self.data.put(key, previous, content_type='application/json')
        wait = Mock()
        with patch('cams_request_plan.fetch_verified_metadata', side_effect=unavailable()) as metadata, \
             patch('retrieve_remote_cams.retrieve_remote_cams') as retrieval, \
             patch('uv_cloud.enrich') as uv:
            result = self.run_worker(wait=wait)
        metadata.assert_called_once()
        retrieval.assert_not_called()
        uv.assert_not_called()
        wait.assert_not_called()
        self.assertEqual(result['air']['status'], 'source_pending')
        self.assertEqual(result['air'], result['pollen'])
        self.assertEqual(self.data.get(key).body, previous)
        self.assertEqual(self.state.list_keys('state/ads/'), [])
        self.assertEqual(self.state.list_keys('state/plans/cams/'), [])
        rows = [json.loads(line) for line in self.output.getvalue().splitlines()]
        outcomes = [row for row in rows if 'components' in row]
        self.assertTrue(outcomes)
        self.assertTrue(all(not row['complete'] for row in outcomes))
        self.assertEqual(rows[-1]['status'], 'deferred')

    def test_same_partial_source_after_deadline_is_a_failed_job(self):
        with patch('cloud_worker._cams_region_step', side_effect=unavailable()) as region, \
             self.assertRaises(RuntimeError):
            self.run_worker(now=EARLY.replace(hour=10), budget=1)
        region.assert_called_once()
        rows = [json.loads(line) for line in self.output.getvalue().splitlines()]
        self.assertNotIn('source_pending', str(rows))
        self.assertEqual(rows[-1]['reason_code'], 'execution_budget_exhausted')

    def test_slow_validation_crossing_deadline_is_not_deferred(self):
        elapsed = [0]
        def slow(*args):
            elapsed[0] = 120
            raise unavailable()
        with patch('cloud_worker._cams_region_step', side_effect=slow), self.assertRaises(RuntimeError):
            self.run_worker(now=EARLY.replace(minute=59), clock=lambda: elapsed[0], budget=121)
        self.assertNotIn('source_pending', self.output.getvalue())

    def test_corrupt_metadata_never_becomes_a_successful_probe(self):
        for error in (unavailable('constraints_multiple_compatible_rows'),
                      unavailable(cls=PublicMetadataError), ConnectionError('transport')):
            with self.subTest(error=type(error).__name__), \
                 patch('cloud_worker._cams_region_step', side_effect=error), self.assertRaises(RuntimeError):
                self.run_worker(budget=1)

    def test_regional_reserve_stops_a_late_retry_before_waiting(self):
        elapsed = [0]
        def slow(*args):
            elapsed[0] += 500
            return dict(PENDING)
        wait = Mock()
        with patch('cloud_worker._cams_region_step', side_effect=slow) as region, self.assertRaises(RuntimeError):
            self.run_worker(clock=lambda: elapsed[0], wait=wait)
        region.assert_called_once()
        wait.assert_not_called()
        self.assertIn('execution_budget_exhausted', self.output.getvalue())

    def test_pending_download_recovers_with_room_for_publication(self):
        elapsed = [0]
        calls = [0]
        pauses = []
        def region(*args):
            calls[0] += 1
            elapsed[0] += 120 if calls[0] == 1 else 360
            return dict(PENDING if calls[0] == 1 else VERIFIED)
        def wait(seconds):
            pauses.append(seconds)
            elapsed[0] += seconds
        with patch('cloud_worker._cams_region_step', side_effect=region):
            result = self.run_worker(clock=lambda: elapsed[0], wait=wait)
        self.assertEqual(pauses, [30])
        self.assertEqual(calls[0], 2)
        self.assertEqual(result['pollen']['status'], 'verified')
        self.assertEqual(elapsed[0], 510)
        self.assertGreater(TASK_TIMEOUT_SECONDS - elapsed[0], 300)

    def test_deferral_cannot_mask_a_uv_failure(self):
        with patch.dict(os.environ, {'WEATHER_UV_ENABLED': '1'}, clear=True), redirect_stdout(self.output), \
             patch('cloud_worker._cams_region_step', side_effect=unavailable()), \
             patch('uv_cloud.enrich', return_value={'status': 'manual_review'}), self.assertRaises(RuntimeError):
            _run_cams(self.state, self.data, EARLY, clock=lambda: 0, wait=Mock())

class DateDiagnosticTests(TestCase):
    def test_catalogue_and_form_date_limits_have_controlled_reason_codes(self):
        from cams_test_fixtures import public_metadata_documents
        from test_cams_request_plan import validate_documents
        for where, expected in [('catalogue', 'catalogue_date_unavailable'), ('form', 'form_date_unavailable')]:
            docs = public_metadata_documents()
            if where == 'catalogue':
                docs['catalogue']['extent']['temporal']['interval'] = [['2026-09-01T00:00:00Z','2026-09-03T00:00:00Z']]
            else:
                next(row for row in docs['form'] if row['name'] == 'date')['details']['maxEnd'] = '2026-09-03'
            with self.subTest(where=where), self.assertRaises(PublicMetadataUnavailable) as caught:
                validate_documents(docs)
            self.assertEqual(source_deferral(caught.exception, EARLY)['status'], 'source_pending')
            from local_pipeline.operational_diagnostics import error_fields
            self.assertEqual(error_fields(caught.exception)['reason_code'], expected)
