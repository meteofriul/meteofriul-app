import json
import os
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch, Mock
from datetime import datetime, timezone
from local_pipeline.sqlite_object_store import SQLiteObjectStore
from cloud_worker import _run_cams, _cams_failure, _cams_acquisition_outcome, _cams_uv_policy
from cams_readback import ReadbackPending
from cams_request_plan import PublicMetadataUnavailable, PublicMetadataError, load_verified_request_plan
from cams_test_fixtures import valid_evidence
from local_pipeline.operational_diagnostics import attach_error_fields

NOW = datetime(2026, 9, 9, 12, tzinfo=timezone.utc)
VERIFIED = {'status': 'verified', 'source_run_id': '20260909T000000Z', 'reason_code': 'verified'}


class CamsWorkerRecoveryTests(TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.state = SQLiteObjectStore(Path(self.tmp.name) / 'state.sqlite')
        self.data = SQLiteObjectStore(Path(self.tmp.name) / 'data.sqlite')
        self.output = StringIO()

    def run_worker(self, **kwargs):
        kwargs.setdefault('wait', Mock())
        kwargs.setdefault('clock', lambda: 0)
        with patch.dict(os.environ, {'PILOT_UV_ENABLED': '1'}), redirect_stdout(self.output):
            return _run_cams(self.state, self.data, NOW, **kwargs)

    def test_pending_uv_does_not_repeat_verified_regional_pipeline(self):
        with patch('cloud_worker._cams_region_step', return_value=VERIFIED) as regional, \
             patch('uv_cloud.enrich', side_effect=[{'status': 'pending'}, {**VERIFIED, 'status': 'published'}]) as uv, \
             patch('cams_readback.verify_uv', return_value={}):
            result = self.run_worker()
        regional.assert_called_once()
        self.assertEqual(uv.call_count, 2)
        self.assertEqual(result['uv']['status'], 'verified')
        rows = [json.loads(line) for line in self.output.getvalue().splitlines()]
        pending = next(row for row in rows if row['components']['uv']['status'] == 'pending')
        self.assertFalse(pending['complete'])
        for component in ('air', 'pollen'):
            self.assertEqual(pending['components'][component]['status'], 'verified')

    def test_uv_runs_only_in_explicit_utc_windows(self):
        environment = {'WEATHER_UV_ENABLED': '1', 'WEATHER_UV_UTC_HOURS': '15,20'}
        with patch.dict(os.environ, environment, clear=True):
            self.assertEqual(_cams_uv_policy(datetime(2026, 9, 9, 10, tzinfo=timezone.utc)),
                             (False, 'uv_outside_scheduled_window'))
            self.assertEqual(_cams_uv_policy(datetime(2026, 9, 9, 15, tzinfo=timezone.utc)),
                             (True, None))
            self.assertEqual(_cams_uv_policy(datetime(2026, 9, 9, 20, tzinfo=timezone.utc)),
                             (True, None))

    def test_regional_window_succeeds_without_early_uv_submission(self):
        with patch.dict(os.environ, {'WEATHER_UV_UTC_HOURS': '15,20'}), \
             patch('cloud_worker._cams_region_step', return_value=VERIFIED), \
             patch('uv_cloud.enrich') as uv:
            result = self.run_worker()
        uv.assert_not_called()
        self.assertEqual(result['uv'], {
            'status': 'disabled', 'reason_code': 'uv_outside_scheduled_window'})
        self.assertEqual(result['air']['status'], 'verified')

    def test_invalid_uv_window_fails_closed(self):
        with patch.dict(os.environ, {
                'WEATHER_UV_ENABLED': '1', 'WEATHER_UV_UTC_HOURS': '15,15'}, clear=True), \
             self.assertRaises(ValueError):
            _cams_uv_policy(NOW)

    def test_uv_terminal_failure_never_masquerades_as_success(self):
        with patch('cloud_worker._cams_region_step', return_value=VERIFIED), \
             patch('uv_cloud.enrich', return_value={'status': 'manual_review', 'reason_code': 'request_ambiguous'}), \
             self.assertRaises(RuntimeError):
            self.run_worker()
        final = json.loads(self.output.getvalue().splitlines()[-1])
        self.assertFalse(final['complete'])
        self.assertEqual(final['components']['uv']['status'], 'manual_review')

    def test_regional_failure_does_not_suppress_uv(self):
        with patch('cloud_worker._cams_region_step', side_effect=ValueError('corrupt')), \
             patch('uv_cloud.enrich', return_value={**VERIFIED, 'status': 'published'}) as uv, \
             patch('cams_readback.verify_uv', return_value={}), self.assertRaises(RuntimeError):
            self.run_worker()
        uv.assert_called_once()

    def test_readback_delay_does_not_become_success(self):
        with patch('cloud_worker._cams_region_step', return_value=VERIFIED), \
             patch('uv_cloud.enrich', return_value={**VERIFIED, 'status': 'published'}), \
             patch('cams_readback.verify_uv', side_effect=ReadbackPending('public_reader_not_current')), \
             self.assertRaises(RuntimeError):
            self.run_worker(budget=1)
        last = json.loads(self.output.getvalue().splitlines()[-1])
        self.assertEqual(last['components']['uv']['reason_code'], 'readback_pending')
        self.assertEqual(last['retry_after_seconds'], 60)

    def test_regional_result_is_persisted_before_uv_crash(self):
        with patch('cloud_worker._cams_region_step', return_value=VERIFIED), \
             patch('uv_cloud.enrich', side_effect=KeyboardInterrupt()), self.assertRaises(KeyboardInterrupt):
            self.run_worker()
        record = json.loads(self.output.getvalue().splitlines()[-1])
        self.assertEqual(record['components']['air']['status'], 'verified')
        self.assertFalse(record['complete'])

    def test_exception_secrets_are_not_persisted(self):
        self.assertNotIn('token=secret', json.dumps(_cams_failure(ValueError('https://private?token=secret'))))

    def test_retriever_error_reports_are_not_mistaken_for_waiting(self):
        cases = [({'http_status': 403}, 'permanent_failure'),
                 ({'http_status': 503}, 'retryable_failure'),
                 ({'last_job_metadata': {'status': 'failed'}}, 'permanent_failure'),
                 ({'safe_reason': 'ADS wait budget reached; job saved for explicit resume, not resubmitted'}, 'remote_pending'),
                 ({'status': 'submission_reconciliation_pending'}, 'reconciling'),
                 ({'error_type': 'PilotError'}, 'manual_review')]
        for report, expected in cases:
            with self.subTest(expected=expected):
                self.assertEqual(_cams_acquisition_outcome(report, VERIFIED['source_run_id'])['status'], expected)

    def test_real_metadata_path_is_retryable_persisted_and_does_not_suppress_uv(self):
        elapsed = [0]
        pauses = []

        def wait(seconds):
            pauses.append(seconds)
            elapsed[0] += seconds

        def unavailable(*args, **kwargs):
            elapsed[0] += 5
            error = PublicMetadataUnavailable('catalog not ready')
            attach_error_fields(error, reason_code='constraints_no_compatible_rows',
                                compatible_rows=0, date_rows=20)
            raise error

        with patch('cams_request_plan.main') as cli, \
             patch('cams_request_plan.fetch_verified_metadata', side_effect=unavailable) as metadata, \
             patch('retrieve_remote_cams.retrieve_remote_cams') as acquisition, \
             patch('uv_cloud.enrich', return_value={**VERIFIED, 'status': 'published'}) as uv, \
             patch('cams_readback.verify_uv', return_value={}) as verify_uv, \
             self.assertRaises(RuntimeError):
            self.run_worker(wait=wait, clock=lambda: elapsed[0])
        cli.assert_not_called()
        acquisition.assert_not_called()
        self.assertEqual(metadata.call_count, 3)
        self.assertEqual(pauses, [60, 180])
        self.assertLess(elapsed[0], 480)
        uv.assert_called_once()
        verify_uv.assert_called_once()
        rows = [json.loads(line) for line in self.output.getvalue().splitlines()]
        outcomes = [row for row in rows if 'components' in row]
        self.assertTrue(outcomes)
        self.assertTrue(all(not row['complete'] for row in outcomes))
        last = outcomes[-1]
        self.assertEqual(last['components']['uv']['status'], 'verified')
        for name in ('air', 'pollen'):
            result = last['components'][name]
            self.assertEqual(result['status'], 'retryable_failure')
            self.assertEqual(result['reason_code'], 'constraints_no_compatible_rows')
            self.assertEqual(result['stage'], 'public_metadata_plan')
            self.assertEqual(result['error_type'], 'PublicMetadataUnavailable')
            self.assertEqual(result['compatible_rows'], 0)
            self.assertNotIn('cause_type', result)
            self.assertIsNone(result['http_status'])
            self.assertNotIn('object_key', result)
        keys = self.state.list_keys('state/dispatch/cams/')
        self.assertEqual(len(keys), len(outcomes))
        for key in keys:
            self.assertIn(json.loads(self.state.get(key).body), outcomes)
        self.assertEqual(self.state.list_keys('state/plans/cams/'), [])
        self.assertEqual(self.state.list_keys('state/ads/'), [])

    def test_catalog_can_recover_with_same_saved_plan_and_bounded_acquisition(self):
        elapsed = [0]
        seen_plans = []

        def wait(seconds):
            elapsed[0] += seconds

        def pending(**kwargs):
            plan, raw, digest = load_verified_request_plan(kwargs['request_plan_path'])
            seen_plans.append((plan['run_date'], raw, digest))
            self.assertEqual(kwargs['max_wait'], 45)
            return {'safe_reason': 'ADS wait budget reached; job saved for explicit resume, not resubmitted'}

        with patch('cams_request_plan.fetch_verified_metadata', side_effect=[
                 PublicMetadataUnavailable('not ready'), valid_evidence(run_date='2026-09-09')]) as metadata, \
             patch('retrieve_remote_cams.retrieve_remote_cams', side_effect=pending) as acquisition, \
             patch('uv_cloud.enrich', return_value={**VERIFIED, 'status': 'published'}) as uv, \
             patch('cams_readback.verify_uv', return_value={}), self.assertRaises(RuntimeError):
            self.run_worker(wait=wait, clock=lambda: elapsed[0])
        self.assertEqual(metadata.call_count, 2)
        self.assertEqual(acquisition.call_count, 2)
        self.assertEqual(len(seen_plans), 2)
        self.assertEqual(seen_plans[0], seen_plans[1])
        self.assertEqual(self.state.get('state/plans/cams/2026-09-09.json').body, seen_plans[0][1])
        uv.assert_called_once()
        last = json.loads(self.output.getvalue().splitlines()[-1])
        self.assertFalse(last['complete'])
        self.assertEqual(last['components']['air']['status'], 'remote_pending')

    def test_unavailable_catalog_recovery_does_not_repeat_successful_uv(self):
        with patch('cloud_worker._cams_region_step', side_effect=[
                 PublicMetadataUnavailable('not ready'), VERIFIED]) as regional, \
             patch('uv_cloud.enrich', return_value={**VERIFIED, 'status': 'published'}) as uv, \
             patch('cams_readback.verify_uv', return_value={}):
            result = self.run_worker()
        self.assertEqual(regional.call_count, 2)
        uv.assert_called_once()
        self.assertTrue(all(row['status'] == 'verified' for row in result.values()))
        rows = [json.loads(line) for line in self.output.getvalue().splitlines()]
        self.assertFalse(rows[0]['complete'])
        self.assertTrue(rows[-1]['complete'])

    def test_invalid_catalog_stays_terminal_but_uv_is_still_evaluated(self):
        with patch('cams_request_plan.fetch_verified_metadata', side_effect=PublicMetadataError('invalid')) as metadata, \
             patch('retrieve_remote_cams.retrieve_remote_cams') as acquisition, \
             patch('uv_cloud.enrich', return_value={**VERIFIED, 'status': 'published'}) as uv, \
             patch('cams_readback.verify_uv', return_value={}), self.assertRaises(RuntimeError):
            self.run_worker()
        metadata.assert_called_once()
        acquisition.assert_not_called()
        uv.assert_called_once()
        last = json.loads(self.output.getvalue().splitlines()[-1])
        self.assertFalse(last['complete'])
        self.assertEqual(last['components']['air']['status'], 'manual_review')
