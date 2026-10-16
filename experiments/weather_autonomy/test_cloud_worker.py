import os
import json
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase, main
from unittest.mock import call, patch, Mock
from contextlib import redirect_stdout
from io import StringIO
from types import SimpleNamespace
from contextlib import ExitStack
from local_pipeline.contract_v1 import ICON_PROVIDER
from local_pipeline.sqlite_object_store import SQLiteObjectStore
from local_pipeline.job_outcomes import JobKind, JobStatus, JobResult
from cloud_worker import (
    run, PROJECT, dispatch_slot, _run_icon, _run_icon_result,
    _claim_icon_acquisition, _icon_slot, _verified_icon_source_run_high_water,
)


RUN = '20260908T000000Z'
NOW = datetime(2026, 9, 8, 6, tzinfo=timezone.utc)
PREPARED = SimpleNamespace(source_run_id=RUN, documents={'093033': b'{}'}, input_fingerprint_sha256='a' * 64)
CHECKPOINT = SimpleNamespace(intent=SimpleNamespace(source_run_id=RUN), prepared=PREPARED)
PUBLISHED = JobResult(JobKind.ICON, 'published', 'publication_committed', source_run_id=RUN,
                      published_providers=('icon2i',))


class WorkerTests(TestCase):
    def test_publication_failure_is_not_a_successful_cloud_job(self):
        with TemporaryDirectory() as directory:
            state = SQLiteObjectStore(Path(directory) / 'state.sqlite')
            data = SQLiteObjectStore(Path(directory) / 'data.sqlite')
            with patch.dict(os.environ, {'GOOGLE_CLOUD_PROJECT': PROJECT}), \
                    patch('cloud_worker.storage.Client'), \
                    patch('cloud_worker.GCSObjectStore', side_effect=[state, data]), \
                    patch('run_pilot.run_outputs'), \
                    patch('local_pipeline.job_entrypoints.prepare_icon_publication', return_value=PREPARED), \
                    patch('local_pipeline.icon_checkpoint.save_checkpoint', return_value=CHECKPOINT), \
                    patch('cloud_worker._publish_icon_checkpoint', return_value=JobResult(
                        JobKind.ICON, JobStatus.MANUAL_REVIEW, 'verified_pipeline_invariant_failed',
                        metrics={'error_type': 'ContractPublicationVerificationError',
                                 'provider': 'icon', 'status': 'failed', 'retryable': True})):
                output = StringIO()
                with redirect_stdout(output), self.assertRaises(RuntimeError):
                    run('icon')
                logs = [json.loads(line) for line in output.getvalue().splitlines()]
                result = next(log for log in logs if log.get('event') == 'publication_result')
                self.assertEqual(result['reason_code'], 'verified_pipeline_invariant_failed')
                self.assertEqual(result['error_type'], 'ContractPublicationVerificationError')
                self.assertEqual(result['status'], 'manual_review')
                self.assertFalse(result['retryable'])
                self.assertEqual(result['provider'], 'icon')

    def test_daily_dispatch_limits(self):
        hours = [datetime(2026, 9, 6, hour, tzinfo=timezone.utc) for hour in range(24)]
        self.assertEqual(len({dispatch_slot('icon', hour) for hour in hours}), 2)
        self.assertEqual(len({dispatch_slot('cams', hour) for hour in hours}), 4)

    def test_published_cams_skips_submission_and_dispatch(self):
        with TemporaryDirectory() as directory:
            state = SQLiteObjectStore(Path(directory) / "state.sqlite")
            data = SQLiteObjectStore(Path(directory) / "data.sqlite")
            data.put("weather/v1/families/cams/latest.json", json.dumps({
                "latest": {"source_run_id": datetime.now(timezone.utc).strftime("%Y%m%dT000000Z")}
            }).encode(), content_type="application/json")
            with patch.dict(os.environ, {"GOOGLE_CLOUD_PROJECT": PROJECT, 'PILOT_UV_ENABLED': '0'}), \
                    patch("cloud_worker.storage.Client"), \
                    patch("cloud_worker.GCSObjectStore", side_effect=[state, data]), \
                    patch('local_pipeline.contract_publisher.ContractV1Publisher.read_verified_cams_family_latest',
                          return_value={'latest': {'source_run_id': datetime.now(timezone.utc).strftime('%Y%m%dT000000Z')}}), \
                    patch('cams_readback.verify_cams', return_value={}), \
                    patch("retrieve_remote_cams.retrieve_remote_cams") as retrieve:
                run("cams")
                retrieve.assert_not_called()

    def test_refuses_beta_before_opening_client(self):
        with patch.dict(os.environ, {"GOOGLE_CLOUD_PROJECT": "meteo-friul"}), \
                patch("cloud_worker.storage.Client") as client:
            with self.assertRaises(ValueError):
                run("icon")
            client.assert_not_called()

    def test_slot_prevents_duplicate_acquisition(self):
        with TemporaryDirectory() as directory:
            state = SQLiteObjectStore(Path(directory) / "state.sqlite")
            data = SQLiteObjectStore(Path(directory) / "data.sqlite")
            with patch.dict(os.environ, {"GOOGLE_CLOUD_PROJECT": PROJECT}), \
                    patch("cloud_worker.storage.Client"), \
                    patch("cloud_worker.GCSObjectStore", side_effect=[state, data, state, data]), \
                    patch("run_pilot.run_outputs") as acquire, \
                    patch('local_pipeline.job_entrypoints.prepare_icon_publication', return_value=PREPARED), \
                    patch('local_pipeline.icon_checkpoint.save_checkpoint', return_value=CHECKPOINT), \
                    patch('publish_remote_icon.recover_remote_icon', return_value=PUBLISHED), \
                    patch("cloud_worker._publish_icon_checkpoint") as publish:
                publish.return_value = JobResult(JobKind.ICON, JobStatus.PUBLISHED,
                    'publication_committed', source_run_id='20260908T000000Z',
                    published_providers=('icon2i',))
                run("icon")
                run("icon")
                acquire.assert_called_once()
                publish.assert_called_once()


class IconRecoveryWorkerTests(TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.state = SQLiteObjectStore(Path(self.temp.name) / 'state.sqlite')
        self.data = SQLiteObjectStore(Path(self.temp.name) / 'data.sqlite')
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(patch.dict(os.environ, {'CLOUD_RUN_EXECUTION': 'pilot-icon-test',
                                                        'CLOUD_RUN_TASK_ATTEMPT': '0'}))
        self.stack.enter_context(patch('cloud_worker.sleep'))
        self.stack.enter_context(redirect_stdout(StringIO()))

    def test_explicit_recovery_never_claims_or_acquires(self):
        with patch.dict(os.environ, {'PILOT_ICON_RECOVER_RUN_ID': RUN}), \
                patch.object(self.state, 'put') as put, \
                patch('run_pilot.run_outputs') as acquire, \
                patch('publish_remote_icon.recover_remote_icon', return_value=PUBLISHED) as recover:
            self.assertEqual(_run_icon(self.state, self.data, NOW), PUBLISHED)
            put.assert_not_called()
            acquire.assert_not_called()
            recover.assert_called_once_with(source_run_id=RUN, state_store=self.state, data_store=self.data)

    def test_recovery_configuration_rejected_before_cloud_access(self):
        for provider, recovery in [('cams', RUN), ('icon', '../secret'), ('icon', '20260908T060000Z')]:
            with self.subTest(provider=provider, recovery=recovery), \
                    patch.dict(os.environ, {'GOOGLE_CLOUD_PROJECT': PROJECT, 'PILOT_ICON_RECOVER_RUN_ID': recovery}), \
                    patch('cloud_worker.storage.Client') as client:
                with self.assertRaises(ValueError):
                    run(provider)
                client.assert_not_called()

    def test_execution_claim_allows_only_next_attempt_same_owner(self):
        self.assertTrue(_claim_icon_acquisition(self.state, '20260908-am', 'owner-one', 0))
        self.assertFalse(_claim_icon_acquisition(self.state, '20260908-am', 'owner-one', 0))
        self.assertFalse(_claim_icon_acquisition(self.state, '20260908-am', 'owner-two', 1))
        self.assertTrue(_claim_icon_acquisition(self.state, '20260908-am', 'owner-one', 1))
        self.assertFalse(_claim_icon_acquisition(self.state, '20260908-am', 'owner-one', 1))

    def test_execution_keeps_original_slot_after_midnight(self):
        first = _icon_slot(self.state, NOW)
        with patch.dict(os.environ, {'CLOUD_RUN_TASK_ATTEMPT': '1'}):
            second = _icon_slot(self.state, datetime(2026, 9, 9, 0, tzinfo=timezone.utc))
        self.assertEqual(first[:2], second[:2])
        self.assertEqual(second[2], 1)

    def test_legacy_claim_without_checkpoint_never_reacquires(self):
        self.state.put('state/dispatch/icon/20260908-am.json', b'{}', content_type='application/json')
        with patch('run_pilot.run_outputs') as acquire:
            result = _run_icon(self.state, self.data, NOW)
            self.assertEqual(result.reason_code, 'slot_already_claimed')
            acquire.assert_not_called()

    def test_valid_checkpoint_survives_process_kill_without_redownload(self):
        with patch('local_pipeline.icon_checkpoint.read_checkpoint', side_effect=[None, CHECKPOINT]), \
                patch('local_pipeline.icon_checkpoint.save_checkpoint', return_value=CHECKPOINT), \
                patch('local_pipeline.job_entrypoints.prepare_icon_publication', return_value=PREPARED), \
                patch('run_pilot.run_outputs') as acquire, \
                patch('cloud_worker._publish_icon_checkpoint', side_effect=[KeyboardInterrupt(), PUBLISHED]) as publish:
            with self.assertRaises(KeyboardInterrupt):
                _run_icon(self.state, self.data, NOW)
            with patch.dict(os.environ, {'CLOUD_RUN_TASK_ATTEMPT': '1'}):
                self.assertEqual(_run_icon(self.state, self.data, NOW), PUBLISHED)
            acquire.assert_called_once()
            self.assertEqual(publish.call_count, 2)
            self.state.get('state/dispatch/icon/20260908-am.json')  # Claim is never deleted.

    def test_kill_before_checkpoint_allows_same_execution_task_retry(self):
        with patch('run_pilot.run_outputs', side_effect=[KeyboardInterrupt(), None]) as acquire, \
                patch('local_pipeline.job_entrypoints.prepare_icon_publication', return_value=PREPARED), \
                patch('local_pipeline.icon_checkpoint.save_checkpoint', return_value=CHECKPOINT), \
                patch('cloud_worker._publish_icon_checkpoint', return_value=PUBLISHED):
            with self.assertRaises(KeyboardInterrupt):
                _run_icon(self.state, self.data, NOW)
            with patch.dict(os.environ, {'CLOUD_RUN_TASK_ATTEMPT': '1'}):
                self.assertEqual(_run_icon(self.state, self.data, NOW), PUBLISHED)
            self.assertEqual(acquire.call_count, 2)

    def test_transient_publication_is_bounded_and_never_reacquires(self):
        failure = JobResult(JobKind.ICON, 'retryable_failure', 'remote_storage_temporary_failure',
                            source_run_id=RUN, metrics={'http_status': 503})
        with patch('local_pipeline.icon_checkpoint.read_checkpoint', return_value=CHECKPOINT), \
                patch('run_pilot.run_outputs') as acquire, \
                patch('cloud_worker._publish_icon_checkpoint', return_value=failure) as publish, \
                patch('cloud_worker.sleep') as sleep:
            with self.assertRaises(RuntimeError):
                _run_icon(self.state, self.data, NOW)
            self.assertEqual(publish.call_count, 3)
            self.assertEqual([call.args[0] for call in sleep.call_args_list], [1, 3])
            acquire.assert_not_called()
            from local_pipeline.sqlite_object_store import ObjectNotFound
            with self.assertRaises(ObjectNotFound):
                self.state.get('state/dispatch/icon/20260908-am/outcome.json')

    def test_hard_error_stays_blocked_without_reacquisition_or_retry(self):
        failure = JobResult(JobKind.ICON, 'manual_review', 'verified_pipeline_invariant_failed', source_run_id=RUN)
        with patch('local_pipeline.icon_checkpoint.read_checkpoint', return_value=CHECKPOINT), \
                patch('run_pilot.run_outputs') as acquire, \
                patch('cloud_worker._publish_icon_checkpoint', return_value=failure) as publish:
            for attempt in ['0', '1']:
                with patch.dict(os.environ, {'CLOUD_RUN_TASK_ATTEMPT': attempt}), self.assertRaises(RuntimeError):
                    _run_icon(self.state, self.data, NOW)
            publish.assert_called_once()
            acquire.assert_not_called()

    def test_corrupt_checkpoint_never_falls_back_to_acquisition(self):
        self.state.put('state/dispatch/icon/20260908-am/checkpoint.json.gz', b'not-gzip',
                       content_type='application/gzip')
        with patch('run_pilot.run_outputs') as acquire, self.assertRaises(RuntimeError):
            _run_icon(self.state, self.data, NOW)
        acquire.assert_not_called()

    def test_checkpoint_precedes_intent_and_publication(self):
        calls = []
        with patch('run_pilot.run_outputs'), \
                patch('local_pipeline.job_entrypoints.prepare_icon_publication', return_value=PREPARED), \
                patch('local_pipeline.icon_checkpoint.save_checkpoint',
                      side_effect=lambda *a, **kw: calls.append('checkpoint') or CHECKPOINT), \
                patch('cloud_worker._publish_icon_checkpoint',
                      side_effect=lambda *a, **kw: calls.append('intent-and-publication') or PUBLISHED):
            _run_icon(self.state, self.data, NOW)
        self.assertEqual(calls, ['checkpoint', 'intent-and-publication'])

    def test_terminal_success_is_reverified_not_trusted_after_revocation(self):
        from local_pipeline.contract_v1 import canonical_json_bytes
        self.state.put('state/dispatch/icon/20260908-am/outcome.json',
                       canonical_json_bytes(PUBLISHED.as_document()), content_type='application/json')
        revoked = JobResult(JobKind.ICON, 'no_op', 'newer_run_already_active', source_run_id=RUN)
        with patch('publish_remote_icon.recover_remote_icon', return_value=revoked) as recover, \
                patch('run_pilot.run_outputs') as acquire:
            result = _run_icon(self.state, self.data, NOW)
            self.assertEqual(result, revoked)
            recover.assert_called_once()
            acquire.assert_not_called()

    def test_source_transport_failures_remain_retryable_without_blocked_marker(self):
        import requests
        from local_pipeline.sqlite_object_store import ObjectNotFound
        from cloud_worker import _icon_failure
        response = requests.Response()
        response.status_code = 503
        for error in [requests.Timeout('https://secret'), requests.ConnectionError('secret'),
                      requests.HTTPError('secret', response=response)]:
            with self.subTest(type=type(error).__name__):
                result = _icon_failure(error)
                self.assertTrue(result.retryable)
                self.assertNotIn('secret', str(result.as_document()))
        with patch('run_pilot.run_outputs', side_effect=requests.Timeout('secret')), self.assertRaises(RuntimeError):
            _run_icon(self.state, self.data, NOW)
        with self.assertRaises(ObjectNotFound):
            self.state.get('state/dispatch/icon/20260908-am/outcome.json')

    def test_verified_rollback_high_water_is_retryable_before_materialization_or_intent(self):
        from local_pipeline.sqlite_object_store import ObjectNotFound
        from run_pilot import SourceRunNotAdvanced

        boundaries = []

        def verified_latest(provider):
            boundaries.append(('verified_pointer', provider))
            return {
                'latest': {'source_run_id': '20260907T120000Z'},
                # Revoking the active run rolls latest back and clears previous.
                'previous': None,
                'disabled_run_ids': [RUN],
            }

        def source_not_advanced(**kwargs):
            self.assertEqual(kwargs['source_run_high_water'], RUN)
            self.assertEqual(boundaries[-1], ('verified_pointer', ICON_PROVIDER))
            boundaries.append(('source_discovery', RUN))
            raise SourceRunNotAdvanced(RUN, RUN)

        with patch(
                'local_pipeline.contract_publisher.ContractV1Publisher.read_verified_latest',
                side_effect=verified_latest,
             ) as read_latest, \
                patch('run_pilot.run_outputs', side_effect=source_not_advanced) as acquire, \
                patch('local_pipeline.job_entrypoints.prepare_icon_publication') as materialize, \
                patch('local_pipeline.icon_checkpoint.save_checkpoint') as save_checkpoint, \
                patch('cloud_worker._publish_icon_checkpoint') as publish:
            results = [_run_icon_result(self.state, self.data, NOW)]
            with patch.dict(os.environ, {'CLOUD_RUN_TASK_ATTEMPT': '1'}):
                results.append(_run_icon_result(self.state, self.data, NOW))

        self.assertTrue(all(result.retryable for result in results))
        self.assertEqual(
            [result.reason_code for result in results],
            ['source_not_advanced', 'source_not_advanced'],
        )
        self.assertEqual([result.source_run_id for result in results], [RUN, RUN])
        self.assertEqual(
            [result.metrics['verified_source_run_high_water'] for result in results],
            [RUN, RUN],
        )
        self.assertEqual(
            read_latest.call_args_list,
            [call(ICON_PROVIDER), call(ICON_PROVIDER)],
        )
        self.assertEqual(acquire.call_count, 2)
        materialize.assert_not_called()
        save_checkpoint.assert_not_called()
        publish.assert_not_called()
        with self.assertRaises(ObjectNotFound):
            self.state.get('state/dispatch/icon/20260908-am/checkpoint.json.gz')
        with self.assertRaises(ObjectNotFound):
            self.state.get('state/dispatch/icon/20260908-am/outcome.json')

    def test_verified_pointer_high_water_includes_real_contract_fields(self):
        self.assertEqual(_verified_icon_source_run_high_water({
            'latest': {'source_run_id': '20260908T000000Z'},
            'previous': {'source_run_id': '20260907T120000Z'},
            'disabled_run_ids': [],
        }), '20260908T000000Z')
        self.assertEqual(_verified_icon_source_run_high_water({
            'latest': {'source_run_id': '20260907T120000Z'},
            'previous': None,
            'disabled_run_ids': ['20260908T000000Z'],
        }), '20260908T000000Z')

    def test_typed_public_http_status_is_classified_without_message_parsing(self):
        from cloud_worker import _icon_failure
        from probe_icon2i import PublicHTTPError
        for status in [408, 429, 503]:
            result = _icon_failure(PublicHTTPError(status))
            self.assertTrue(result.retryable)
            self.assertEqual(result.reason_code, 'icon_transport_temporary_failure')
            self.assertEqual(result.metrics['http_status'], status)
        denied = _icon_failure(PublicHTTPError(403))
        self.assertFalse(denied.retryable)
        self.assertEqual(denied.reason_code, 'icon_source_http_failure')

    def test_conflicting_terminal_create_is_not_blindly_accepted(self):
        from local_pipeline.contract_v1 import canonical_json_bytes
        other = JobResult(JobKind.ICON, 'manual_review', 'verified_pipeline_invariant_failed',
                          source_run_id='20260907T120000Z')
        def publish(*a, **kwargs):
            self.state.put('state/dispatch/icon/20260908-am/outcome.json',
                           canonical_json_bytes(other.as_document()), content_type='application/json')
            return PUBLISHED
        with patch('local_pipeline.icon_checkpoint.read_checkpoint', return_value=CHECKPOINT), \
                patch('cloud_worker._publish_icon_checkpoint', side_effect=publish), self.assertRaises(RuntimeError):
            _run_icon(self.state, self.data, NOW)


if __name__ == "__main__":
    main()
