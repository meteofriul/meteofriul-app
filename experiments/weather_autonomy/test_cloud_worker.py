import os
import json
from datetime import datetime, timedelta, timezone
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
QUALITY = dict(schema_version='icon2i-source-quality.v1', source_run_id=RUN, source_snapshot_sha256='c'*64,
               counts=dict(municipality_hours=215*73, municipalities=215), anomaly_samples=[], near_saturation_controls=[],
               sampling=dict(anomaly_samples_truncated=False))
CHECKPOINT = SimpleNamespace(intent=SimpleNamespace(source_run_id=RUN), prepared=PREPARED, source_quality=QUALITY)
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
                    patch('run_pilot.run_outputs', return_value={'source_quality': QUALITY}), \
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
                    patch("cams_storage.CamsObjectStore", side_effect=[state, data]), \
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
                    patch('run_pilot.run_outputs', return_value={'source_quality': QUALITY}) as acquire, \
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
                patch('run_pilot.run_outputs', return_value={'source_quality': QUALITY}) as acquire, \
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
        with patch('run_pilot.run_outputs', return_value={'source_quality': QUALITY}) as acquire:
            result = _run_icon(self.state, self.data, NOW)
            self.assertEqual(result.reason_code, 'slot_already_claimed')
            acquire.assert_not_called()

    def test_valid_checkpoint_survives_process_kill_without_redownload(self):
        with patch('local_pipeline.icon_checkpoint.read_checkpoint', side_effect=[None, CHECKPOINT]), \
                patch('local_pipeline.icon_checkpoint.save_checkpoint', return_value=CHECKPOINT), \
                patch('local_pipeline.job_entrypoints.prepare_icon_publication', return_value=PREPARED), \
                patch('run_pilot.run_outputs', return_value={'source_quality': QUALITY}) as acquire, \
                patch('cloud_worker._publish_icon_checkpoint', side_effect=[KeyboardInterrupt(), PUBLISHED]) as publish:
            with self.assertRaises(KeyboardInterrupt):
                _run_icon(self.state, self.data, NOW)
            with patch.dict(os.environ, {'CLOUD_RUN_TASK_ATTEMPT': '1'}):
                self.assertEqual(_run_icon(self.state, self.data, NOW), PUBLISHED)
            acquire.assert_called_once()
            self.assertEqual(publish.call_count, 2)
            self.state.get('state/dispatch/icon/20260908-am.json')  # Claim is never deleted.

    def test_quality_reaches_actual_stdout_on_resume_without_acquisition(self):
        output = StringIO()
        with patch('local_pipeline.icon_checkpoint.read_checkpoint', return_value=CHECKPOINT), \
                patch('run_pilot.run_outputs') as acquire, \
                patch('cloud_worker._publish_icon_checkpoint', return_value=PUBLISHED), redirect_stdout(output):
            self.assertEqual(_run_icon(self.state, self.data, NOW), PUBLISHED)
        acquire.assert_not_called()
        record = next(json.loads(line) for line in output.getvalue().splitlines() if json.loads(line).get('event') == 'source_quality')
        self.assertTrue(record['quality_available'])
        self.assertEqual(record['quality_municipality_hours'], 15695)
        self.assertEqual(record['source_run_id'], RUN)
        self.assertEqual(len(record['quality_sha256']), 64)
        self.assertNotIn('anomaly_samples', record)

    def test_kill_before_checkpoint_allows_same_execution_task_retry(self):
        with patch('run_pilot.run_outputs', side_effect=[KeyboardInterrupt(), {'source_quality': QUALITY}]) as acquire, \
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
                patch('run_pilot.run_outputs', return_value={'source_quality': QUALITY}) as acquire, \
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
                patch('run_pilot.run_outputs', return_value={'source_quality': QUALITY}) as acquire, \
                patch('cloud_worker._publish_icon_checkpoint', return_value=failure) as publish:
            for attempt in ['0', '1']:
                with patch.dict(os.environ, {'CLOUD_RUN_TASK_ATTEMPT': attempt}), self.assertRaises(RuntimeError):
                    _run_icon(self.state, self.data, NOW)
            publish.assert_called_once()
            acquire.assert_not_called()

    def test_corrupt_checkpoint_never_falls_back_to_acquisition(self):
        self.state.put('state/dispatch/icon/20260908-am/checkpoint.json.gz', b'not-gzip',
                       content_type='application/gzip')
        with patch('run_pilot.run_outputs', return_value={'source_quality': QUALITY}) as acquire, self.assertRaises(RuntimeError):
            _run_icon(self.state, self.data, NOW)
        acquire.assert_not_called()

    def test_checkpoint_precedes_intent_and_publication(self):
        calls = []
        with patch('run_pilot.run_outputs', return_value={'source_quality': QUALITY}), \
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
                patch('run_pilot.run_outputs', return_value={'source_quality': QUALITY}) as acquire:
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


class AutomaticIconWorkerTests(TestCase):
    def setUp(self):
        from local_pipeline.icon_recovery import FEATURE_FLAG
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.state = SQLiteObjectStore(Path(self.temp.name) / 'state.sqlite')
        self.data = SQLiteObjectStore(Path(self.temp.name) / 'data.sqlite')
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(patch.dict(os.environ, {FEATURE_FLAG: 'true',
            'CLOUD_RUN_EXECUTION': 'pilot-icon-automatic-one', 'CLOUD_RUN_TASK_ATTEMPT': '0'}))
        os.environ.pop('PILOT_ICON_RECOVER_RUN_ID', None)
        self.stack.enter_context(redirect_stdout(StringIO()))
        self.pointer = None
        self.checkpoints = {}
        self.elapsed = 0.0
        self.stack.enter_context(patch('cloud_worker.monotonic', side_effect=lambda: self.elapsed))
        self.stack.enter_context(patch.object(PREPARED, 'manifest', create=True, return_value={
            'run_at': '2026-09-08T00:00:00Z',
            'freshness': {'usable_until': '2026-09-09T00:00:00Z'},
        }))
        self.stack.enter_context(patch('local_pipeline.contract_publisher.ContractV1Publisher.read_verified_latest_snapshot',
            side_effect=lambda *_: SimpleNamespace(document=self.pointer, manifest=PREPARED.manifest(), etag='fixture-etag')
                if self.pointer is not None else None))
        self.stack.enter_context(patch('local_pipeline.contract_publisher.ContractV1Publisher.read_latest_if_etag',
            side_effect=lambda *_: self.pointer))
        self.stack.enter_context(patch('local_pipeline.icon_checkpoint.read_checkpoint',
            side_effect=lambda _state, *, slot, catalog: self.checkpoints.get(slot)))
        self.stack.enter_context(patch('local_pipeline.icon_checkpoint.save_checkpoint', side_effect=self.save))
        self.stack.enter_context(patch('local_pipeline.job_entrypoints.prepare_icon_publication', return_value=PREPARED))
        self.acquisition = self.stack.enter_context(patch('run_pilot.run_outputs', return_value={'source_quality': QUALITY}))
        self.discovery = self.stack.enter_context(patch('local_pipeline.icon_recovery.discovery', return_value='2026090800'))
        self.publication = self.stack.enter_context(patch('cloud_worker._publish_icon_checkpoint', side_effect=self.publish))

    def save(self, _state, *, slot, **_kwargs):
        self.checkpoints[slot] = CHECKPOINT
        return CHECKPOINT

    def publish(self, frozen, **_kwargs):
        self.pointer = {'latest': {'source_run_id': frozen.intent.source_run_id},
                        'previous': None, 'disabled_run_ids': []}
        return PUBLISHED

    def test_pending_then_recovery_pins_run_and_verifies_publication(self):
        from local_pipeline.icon_recovery import Recovery
        self.discovery.side_effect = [None, '2026090800']
        pending = _run_icon_result(self.state, self.data, NOW)
        self.assertEqual(pending.status, JobStatus.RETRYABLE_FAILURE)
        self.assertEqual(pending.metrics['recovery_state'], 'pending')
        self.assertFalse(pending.metrics['published_pointer_verified'])
        self.acquisition.assert_not_called()
        self.assertIsNone(Recovery(self.state, 'fvg').active())
        # A task retry crossing an hour keeps the already-spent poll.
        _run_icon_result(self.state, self.data, NOW + timedelta(hours=1))
        self.discovery.assert_called_once()
        with patch.dict(os.environ, {'CLOUD_RUN_EXECUTION': 'pilot-icon-automatic-two'}):
            published = _run_icon_result(self.state, self.data, NOW + timedelta(hours=1))
        self.assertEqual(published.status, JobStatus.PUBLISHED)
        self.assertTrue(published.metrics['published_pointer_verified'])
        self.assertEqual(self.acquisition.call_args.kwargs['run'], '2026090800')
        self.assertEqual(self.acquisition.call_count, 1)
        with patch.dict(os.environ, {'CLOUD_RUN_EXECUTION': 'pilot-icon-automatic-three'}):
            duplicate = _run_icon_result(self.state, self.data, NOW + timedelta(hours=2))
        self.assertEqual(duplicate.status, JobStatus.NO_OP)
        self.assertEqual(self.acquisition.call_count, 1)

    def test_complete_checkpoint_resumes_before_unavailable_discovery(self):
        from local_pipeline.icon_recovery import Recovery
        Recovery(self.state, 'fvg').begin(None, RUN, '20260908-am', 'pilot-icon-old')
        self.checkpoints['20260908-am'] = CHECKPOINT
        self.discovery.side_effect = AssertionError('must not probe')
        outcome = _run_icon_result(self.state, self.data, NOW + timedelta(hours=3))
        self.assertEqual(outcome.status, JobStatus.PUBLISHED)
        self.discovery.assert_not_called()
        self.acquisition.assert_not_called()

    def test_ambiguous_legacy_claim_cannot_publish_or_acquire(self):
        self.state.put('state/dispatch/icon/20260908-am.json', b'{}')
        outcome = _run_icon_result(self.state, self.data, NOW)
        self.assertEqual(outcome.status, JobStatus.MANUAL_REVIEW)
        self.assertEqual(outcome.reason_code, 'legacy_acquisition_owner_unresolved')
        self.discovery.assert_not_called()
        self.acquisition.assert_not_called()
        self.publication.assert_not_called()

    def test_expired_checkpoint_never_publishes_or_reacquires(self):
        from local_pipeline.icon_recovery import Recovery
        Recovery(self.state, 'fvg').begin(None, RUN, '20260908-am', 'pilot-icon-old')
        self.checkpoints['20260908-am'] = CHECKPOINT
        outcome = _run_icon_result(self.state, self.data, NOW + timedelta(days=3))
        self.assertEqual(outcome.status, JobStatus.MANUAL_REVIEW)
        self.assertEqual(Recovery(self.state, 'fvg').active().record['phase'], 'manual_review')
        self.acquisition.assert_not_called()
        self.discovery.assert_not_called()
        self.publication.assert_not_called()

    def test_checkpoint_coverage_is_checked_again_immediately_before_pointer_cas(self):
        from local_pipeline.contract_publisher import ContractV1Publisher
        from local_pipeline.contract_v1 import load_catalog
        from local_pipeline.sqlite_object_store import ObjectNotFound
        from local_pipeline.icon_recovery import Recovery
        Recovery(self.state, 'fvg').begin(None, RUN, '20260908-am', 'pilot-icon-old')
        self.checkpoints['20260908-am'] = CHECKPOINT
        pointer_key = ContractV1Publisher(self.data, load_catalog()).latest_key(ICON_PROVIDER)

        def slow_publication(frozen, *, data, **_kwargs):
            self.elapsed = 120.0
            data.compare_and_swap(pointer_key, b'{}', expected_etag=None, content_type='application/json')
            return self.publish(frozen)

        self.publication.side_effect = slow_publication
        outcome = _run_icon_result(self.state, self.data, NOW.replace(hour=23, minute=59))
        self.assertEqual(outcome.status, JobStatus.MANUAL_REVIEW)
        with self.assertRaises(ObjectNotFound):
            self.data.get(pointer_key)
        self.assertIsNone(self.pointer)
        self.acquisition.assert_not_called()
        self.discovery.assert_not_called()


class AutomaticIconVerificationCacheTests(TestCase):
    @classmethod
    def setUpClass(cls):
        # Reuse the publisher's real 215-town contract fixtures, never mock its
        # verifier. Generation changes are modeled by the locked memory store.
        import test_contract_publisher as fixtures
        from local_pipeline.contract_publisher import ContractV1Publisher
        fixtures.ContractPublisherTests.setUpClass()
        cls.catalog = fixtures.ContractPublisherTests.catalog
        cls.memory_store = fixtures.MemoryObjectStore
        cls.template = cls.memory_store()
        cls.old_run = NOW.replace(hour=0)
        cls.new_run = NOW.replace(hour=12)
        publisher = ContractV1Publisher(cls.template, cls.catalog)
        cls.bundles = {}
        for run in (cls.old_run, cls.new_run):
            docs, manifest = fixtures.ContractPublisherTests.icon_bundle(run)
            cls.bundles[manifest['source_run_id']] = (docs, manifest)
            publication = publisher.publish_run(ICON_PROVIDER, docs, manifest,
                published_at=(run + timedelta(hours=2)).strftime('%Y-%m-%dT%H:%M:%SZ'))
            if run == cls.old_run:
                cls.old_pointer = cls.template.get(publication.latest_key)
            else:
                cls.new_pointer = cls.template.get(publication.latest_key)
        cls.pointer_key = publication.latest_key
        publisher.revoke_run(ICON_PROVIDER, '20260908T120000Z',
            published_at='2026-09-08T18:00:00Z', rollback_to_run_id=RUN)
        cls.revoked_pointer = cls.template.get(cls.pointer_key)

    def setUp(self):
        from local_pipeline.contract_publisher import ContractV1Publisher
        from local_pipeline.icon_recovery import FEATURE_FLAG, Recovery
        self.data, self.state = self.memory_store(), self.memory_store()
        self.data.objects = dict(self.template.objects)
        self.data.generations = dict(self.template.generations)
        self.data.objects[self.pointer_key] = self.old_pointer
        self.data.generations[self.pointer_key] = 1
        self.publisher = ContractV1Publisher(self.data, self.catalog)
        self.controller = Recovery(self.state, 'fvg')
        owner = self.controller.begin(None, RUN, '20260908-am', 'pilot-icon-previous')
        self.controller.transition(owner, 'completed')
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(patch.dict(os.environ, {FEATURE_FLAG: 'true',
            'CLOUD_RUN_EXECUTION': 'pilot-icon-cache-one', 'CLOUD_RUN_TASK_ATTEMPT': '0'}))
        os.environ.pop('PILOT_ICON_RECOVER_RUN_ID', None)
        self.stack.enter_context(redirect_stdout(StringIO()))
        self.stack.enter_context(patch('cloud_worker.monotonic', return_value=0.0))
        self.discovery = self.stack.enter_context(patch('local_pipeline.icon_recovery.discovery'))
        self.acquisition = self.stack.enter_context(patch('run_pilot.run_outputs'))
        self.original_get = self.data.get
        self.reads = []
        self.on_get = None

        def counted_get(key):
            self.reads.append(key)
            if self.on_get is not None:
                self.on_get(key)
            return self.original_get(key)

        self.stack.enter_context(patch.object(self.data, 'get', side_effect=counted_get))

    def municipality_reads(self):
        return [key for key in self.reads if '/municipalities/' in key]

    def replace_pointer(self, stored):
        before = self.original_get(self.pointer_key)
        return self.data.compare_and_swap(self.pointer_key, stored.body, expected_etag=before.etag,
            content_type=stored.content_type, metadata=stored.metadata)

    def test_no_op_reads_215_bodies_instead_of_three_complete_passes(self):
        # Baseline equivalent: three legacy strong reads, same actual objects.
        for _ in range(3):
            self.publisher.read_verified_latest(ICON_PROVIDER)
        self.assertEqual(len(self.municipality_reads()), 645)
        self.reads.clear()
        outcome = _run_icon_result(self.state, self.data, NOW)
        self.assertEqual(outcome.status, JobStatus.NO_OP)
        self.assertEqual(len(self.municipality_reads()), 215)
        self.discovery.assert_not_called()
        self.acquisition.assert_not_called()

    def test_verification_cache_does_not_survive_next_invocation(self):
        self.assertEqual(_run_icon_result(self.state, self.data, NOW).status, JobStatus.NO_OP)
        self.reads.clear()
        self.assertEqual(_run_icon_result(self.state, self.data, NOW).status, JobStatus.NO_OP)
        self.assertEqual(len(self.municipality_reads()), 215)

    def test_same_document_new_generation_requires_complete_verification(self):
        def change_on_second_pointer_read(key):
            if key == self.pointer_key and self.reads.count(key) == 2:
                self.on_get = None
                self.replace_pointer(self.old_pointer)
        self.on_get = change_on_second_pointer_read
        self.assertEqual(_run_icon_result(self.state, self.data, NOW).status, JobStatus.NO_OP)
        self.assertEqual(len(self.municipality_reads()), 430)

    def test_advanced_pointer_during_verification_is_not_given_old_proof(self):
        def advance_during_first_body(key):
            if '/municipalities/' in key:
                self.on_get = None
                self.replace_pointer(self.new_pointer)
        self.on_get = advance_during_first_body
        # The original execution ticket still refers to the completed AM cycle.
        self.controller.execution_window(NOW, 'pilot-icon-cache-one')
        outcome = _run_icon_result(self.state, self.data, NOW.replace(hour=18))
        self.assertEqual(outcome.status, JobStatus.NO_OP)
        self.assertEqual(len(self.municipality_reads()), 430)
        self.assertEqual(sum('/20260908T120000Z/' in key for key in self.municipality_reads()), 215)

    def test_corrupt_body_is_detected_at_start_and_after_generation_change(self):
        from local_pipeline.sqlite_object_store import StoredObject
        key = self.publisher.payload_key(ICON_PROVIDER, RUN, self.catalog.istat_codes[0])
        original = self.original_get(key)
        self.data.objects[key] = StoredObject(b'{}', original.head)
        outcome = _run_icon_result(self.state, self.data, NOW)
        self.assertNotIn(outcome.status, (JobStatus.PUBLISHED, JobStatus.NO_OP))
        self.data.objects[key] = original
        self.reads.clear()

        def corrupt_after_snapshot(key_read):
            if key_read == self.pointer_key and self.reads.count(key_read) == 2:
                self.on_get = None
                self.replace_pointer(self.old_pointer)
                self.data.objects[key] = StoredObject(b'{}', original.head)
        self.on_get = corrupt_after_snapshot
        outcome = _run_icon_result(self.state, self.data, NOW)
        self.assertNotIn(outcome.status, (JobStatus.PUBLISHED, JobStatus.NO_OP))
        self.assertGreater(len(self.municipality_reads()), 215)
        self.acquisition.assert_not_called()

    def test_expired_cached_publication_never_reports_no_op_success(self):
        self.controller.execution_window(NOW, 'pilot-icon-cache-one')
        outcome = _run_icon_result(self.state, self.data, NOW + timedelta(days=3))
        self.assertEqual(outcome.status, JobStatus.MANUAL_REVIEW)
        self.assertEqual(outcome.reason_code, 'publication_current_coverage_expired')
        self.assertEqual(len(self.municipality_reads()), 215)

    def test_rollback_and_revocation_force_full_validation_and_reject_completed_cycle(self):
        self.replace_pointer(self.new_pointer)
        owner = self.controller.begin(self.controller.active(), '20260908T120000Z', '20260908-pm', 'pilot-icon-pm')
        self.controller.transition(owner, 'completed')

        def rollback_on_second_pointer_read(key):
            if key == self.pointer_key and self.reads.count(key) == 2:
                self.on_get = None
                self.publisher.revoke_run(ICON_PROVIDER, '20260908T120000Z',
                    published_at='2026-09-08T18:00:00Z', rollback_to_run_id=RUN)
                self.reads.clear()  # Count the verification after the administrative operation.
        self.on_get = rollback_on_second_pointer_read
        outcome = _run_icon_result(self.state, self.data, NOW.replace(hour=18))
        self.assertEqual(outcome.status, JobStatus.MANUAL_REVIEW)
        self.assertEqual(outcome.reason_code, 'completed_publication_not_verified')
        self.assertEqual(len(self.municipality_reads()), 215)
        self.acquisition.assert_not_called()

    def current_checkpoint(self):
        from local_pipeline.job_entrypoints import PreparedIconPublication
        from local_pipeline.contract_v1 import canonical_json_bytes
        import hashlib
        owner = self.controller.active()
        self.controller.replace(owner, {**owner.record, 'phase': 'checkpointed'})
        docs, manifest = self.bundles[RUN]
        body = canonical_json_bytes(manifest)
        prepared = PreparedIconPublication(RUN, hashlib.sha256(body).hexdigest(), docs, body)
        return SimpleNamespace(prepared=prepared, intent=SimpleNamespace(source_run_id=RUN))

    def test_publication_invalidates_cache_even_when_pointer_generation_is_unchanged(self):
        # Simulate interrupted completion after immutable publication, so the
        # checkpoint identifies the already-current run and publisher is a no-op.
        frozen = self.current_checkpoint()
        with patch('local_pipeline.icon_checkpoint.read_checkpoint', return_value=frozen), \
                patch('cloud_worker._publish_icon_checkpoint', return_value=PUBLISHED):
            outcome = _run_icon_result(self.state, self.data, NOW)
        self.assertEqual(outcome.status, JobStatus.PUBLISHED)
        self.assertEqual(len(self.municipality_reads()), 430)
        self.discovery.assert_not_called()
        self.acquisition.assert_not_called()

    def test_second_change_during_full_revalidation_cannot_reuse_superseded_proof(self):
        def change_twice(key):
            if key == self.pointer_key and self.reads.count(key) == 2:
                self.replace_pointer(self.new_pointer)
            elif '/20260908T120000Z/municipalities/' in key:
                self.on_get = None
                self.replace_pointer(self.revoked_pointer)
        self.on_get = change_twice
        self.controller.execution_window(NOW, 'pilot-icon-cache-one')
        outcome = _run_icon_result(self.state, self.data, NOW.replace(hour=18))
        self.assertEqual(outcome.status, JobStatus.MANUAL_REVIEW)
        self.assertEqual(outcome.reason_code, 'completed_publication_not_verified')
        self.assertEqual(len(self.municipality_reads()), 430)

    def test_generation_change_during_postpublication_readback_cannot_report_success(self):
        frozen = self.current_checkpoint()

        def change_during_final_readback(key):
            if '/municipalities/' in key and len(self.municipality_reads()) > 215:
                self.on_get = None
                self.replace_pointer(self.old_pointer)
        self.on_get = change_during_final_readback
        with patch('local_pipeline.icon_checkpoint.read_checkpoint', return_value=frozen), \
                patch('cloud_worker._publish_icon_checkpoint', return_value=PUBLISHED):
            outcome = _run_icon_result(self.state, self.data, NOW)
        self.assertEqual(outcome.status, JobStatus.MANUAL_REVIEW)
        self.assertEqual(outcome.reason_code, 'publication_readback_failed')
        self.assertEqual(len(self.municipality_reads()), 430)

    def test_corrupt_body_after_publication_cannot_use_prepublication_proof(self):
        from local_pipeline.sqlite_object_store import StoredObject
        frozen = self.current_checkpoint()
        key = self.publisher.payload_key(ICON_PROVIDER, RUN, self.catalog.istat_codes[0])

        def corrupt_after_publish(*_args, **_kwargs):
            original = self.original_get(key)
            self.data.objects[key] = StoredObject(b'{}', original.head)
            return PUBLISHED
        with patch('local_pipeline.icon_checkpoint.read_checkpoint', return_value=frozen), \
                patch('cloud_worker._publish_icon_checkpoint', side_effect=corrupt_after_publish):
            outcome = _run_icon_result(self.state, self.data, NOW)
        self.assertNotIn(outcome.status, (JobStatus.PUBLISHED, JobStatus.NO_OP))
        self.assertGreater(len(self.municipality_reads()), 215)


if __name__ == "__main__":
    main()
