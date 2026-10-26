import json
import unittest
from datetime import date
from unittest.mock import Mock, patch

from app.events.pilot_catalog import PILOT_PROJECT, merge_collection
from app.events.pilot_cloud import annual_watch_due, publish
from app.events.pilot_regional_checkpoint import encode_control
from app.events.pilot_sources import source_adapters
from app.events.pilot_source_policy import APPROVED_SOURCES
from app.events.pilot_recovery import log_source_recovery


class SourceRecoveryTests(unittest.TestCase):
    OLD = '2026-10-26T04:00:00Z'
    NEW = '2026-10-27T04:00:00Z'

    def prior_failure(self):
        valid = merge_collection(PILOT_PROJECT, None, {
            'Barcolana': {'status': 'ok', 'events': [{'title': 'Old'}]}},
            '2026-10-25T04:00:00Z')
        return merge_collection(PILOT_PROJECT, valid, {
            'Barcolana': {'status': 'error', 'error_type': 'timeout'}}, self.OLD)

    @patch('app.events.pilot_cloud.collect')
    def test_recovery_is_logged_only_after_persistence_and_only_once(self, collect):
        for status, events in [('ok', [{'title': 'New'}]), ('ok', []),
                               ('partial', [{'title': 'Verified subset'}])]:
            with self.subTest(status=status, count=len(events)):
                previous = self.prior_failure()
                collected = merge_collection(PILOT_PROJECT, previous, {
                    'Barcolana': {'status': status, 'events': events,
                                  'review_required': ([{'reason': 'conflict'}]
                                                      if status == 'partial' else [])}
                }, self.NEW)
                collect.return_value = collected
                blob = Mock(generation=7, size=100)
                blob.download_as_bytes.return_value = json.dumps(previous).encode()
                client = Mock(project=PILOT_PROJECT)
                client.bucket.return_value.blob.return_value = blob
                seen = []
                def printed(line, **_):
                    blob.upload_from_string.assert_called_once()
                    seen.append(json.loads(line))
                with patch('builtins.print', side_effect=printed):
                    publish(client, project=PILOT_PROJECT, adapters={'Barcolana': object()})
                self.assertEqual(len(seen), 1)
                recovered = seen[0]['recovered'][0]
                self.assertEqual(recovered['published_count'], len(events))
                self.assertEqual(recovered['status'], 'partial' if status == 'partial' else 'fresh')
                self.assertEqual(seen[0]['partial_sources'], ['Barcolana'] if status == 'partial' else [])
                self.assertFalse(seen[0]['api_verified'])
                with patch('builtins.print') as output:
                    log_source_recovery(collected, collected, ['Barcolana'])
                output.assert_not_called()

    @patch('app.events.pilot_cloud.collect')
    def test_failed_storage_write_never_reports_recovery(self, collect):
        previous = self.prior_failure()
        collect.return_value = merge_collection(PILOT_PROJECT, previous, {
            'Barcolana': {'status': 'ok', 'events': []}}, self.NEW)
        blob = Mock(generation=7, size=100)
        blob.download_as_bytes.return_value = json.dumps(previous).encode()
        blob.upload_from_string.side_effect = RuntimeError('conditional write failed')
        client = Mock(project=PILOT_PROJECT)
        client.bucket.return_value.blob.return_value = blob
        with patch('builtins.print') as output:
            with self.assertRaisesRegex(RuntimeError, 'conditional write failed'):
                publish(client, project=PILOT_PROJECT, adapters={'Barcolana': object()})
        output.assert_not_called()

    def test_old_missing_invalid_or_unselected_batches_never_report_recovery(self):
        previous = self.prior_failure()
        current = merge_collection(PILOT_PROJECT, previous, {
            'Barcolana': {'status': 'ok', 'events': []}}, self.NEW)
        cases = [(previous, previous, ['Barcolana']), (previous, current, []),
                 (None, current, ['Barcolana'])]
        for timestamp in (self.OLD, None, 'invalid', '2026-10-27T04:00:00'):
            altered = json.loads(json.dumps(current))
            altered['sources']['Barcolana']['updated_at'] = timestamp
            cases.append((previous, altered, ['Barcolana']))
        for before, after, selected in cases:
            with self.subTest(after=after, selected=selected), patch('builtins.print') as output:
                log_source_recovery(before, after, selected)
                output.assert_not_called()

    @patch('app.events.pilot_cloud.collect')
    def test_one_source_recovered_does_not_hide_other_failure(self, collect):
        previous = self.prior_failure()
        collect.return_value = merge_collection(PILOT_PROJECT, previous, {
            'Barcolana': {'status': 'ok', 'events': []},
            'Azalea': {'status': 'error', 'error_type': 'timeout'}}, self.NEW)
        blob = Mock(generation=7, size=100)
        blob.download_as_bytes.return_value = json.dumps(previous).encode()
        client = Mock(project=PILOT_PROJECT)
        client.bucket.return_value.blob.return_value = blob
        with patch('builtins.print') as output:
            with self.assertRaisesRegex(RuntimeError, 'Azalea'):
                publish(client, project=PILOT_PROJECT,
                        adapters={'Barcolana': object(), 'Azalea': object()})
        messages = [json.loads(call.args[0]) for call in output.call_args_list]
        recovery = [item for item in messages if item.get('event') == 'event_source_recovered']
        self.assertEqual(len(recovery), 1)
        self.assertEqual(recovery[0]['remaining_unavailable_sources'], ['Azalea'])
        self.assertEqual([item['source'] for item in recovery[0]['recovered']], ['Barcolana'])

    def test_recovery_keeps_expired_unselected_source_explicit(self):
        previous = self.prior_failure()
        previous['sources']['Azalea'] = {
            'status': 'fresh', 'updated_at': '2026-10-24T04:00:00Z', 'events': []}
        current = merge_collection(PILOT_PROJECT, previous, {
            'Barcolana': {'status': 'ok', 'events': []}}, self.NEW)
        with patch('builtins.print') as output:
            log_source_recovery(previous, current, ['Barcolana'])
        self.assertEqual(json.loads(output.call_args.args[0])['remaining_unavailable_sources'],
                         ['Azalea'])


class CloudPublicationTests(unittest.TestCase):
    def setUp(self):
        annual_patcher = patch('app.events.pilot_cloud.annual_watch_due',
                               return_value=False)
        annual_patcher.start()
        self.addCleanup(annual_patcher.stop)
        giro_patcher = patch('app.events.pilot_cloud.collect_girofvg_watch')
        self.giro_watch = giro_patcher.start()
        self.addCleanup(giro_patcher.stop)
        self.giro_watch.return_value = {
            'source_complete': False, 'sitemap_urls': 12297,
            'category_pages_expected': 90, 'category_pages_read': 89,
            'known_page_errors': ['https://www.girofvg.com/fiere-e-mostre?start=168'],
            'changes': []}

    def client(self):
        blob = Mock()
        blob.generation = 7
        blob.size = 100
        blob.download_as_bytes.return_value = json.dumps({
            'schema': 'pilot-events-v1', 'sources': {},
        }).encode('utf-8')
        client = Mock(project=PILOT_PROJECT)
        client.bucket.return_value.blob.return_value = blob
        return client, blob

    def test_weekly_inventory_runs_once_per_monday(self):
        monday = date(2026, 10, 12)
        self.assertTrue(annual_watch_due(monday))
        self.assertFalse(annual_watch_due(monday, {
            'status': 'checked', 'checked_at': '2026-10-12T04:00:00+00:00'}))
        self.assertTrue(annual_watch_due(monday, {
            'status': 'unverified', 'checked_at': '2026-10-12T04:00:00+00:00'}))

    @patch('app.events.pilot_cloud.attems_watch_changes', return_value=[])
    @patch('app.events.pilot_cloud.collect_attems_audit')
    @patch('app.events.pilot_cloud.collect')
    @patch('app.events.pilot_regional_verified.collect_regional_window_verified')
    def test_default_job_collects_every_registered_source(self, regional, collect,
                                                          attems_audit, attems_changes):
        client, blob = self.client()
        prior_control = {'schema': 'turismofvg-current-year-control-v1',
                         'as_of_date': '2026-10-05'}
        blob.download_as_bytes.return_value = json.dumps({
            'schema': 'pilot-events-v1', 'sources': {'TurismoFVG': {
                'control_checkpoint': encode_control(prior_control)}},
            'monitors': {'Pro Loco FVG': {
                'status': 'review_required', 'checked_at': '2026-10-11T04:00:00+00:00'}}
        }).encode('utf-8')
        expected = set(APPROVED_SOURCES)
        collect.return_value = {'schema': 'pilot-events-v1', 'sources': {
            name: {'status': 'fresh', 'events': []} for name in expected
        }}
        attems_audit.return_value = {'source_complete': False, 'event_api_count': 27,
                                     'current_exhibition_count': 1, 'blockers': [
                                         {'reasons': ['venue_not_in_event_text']}]}
        publish(client, project=PILOT_PROJECT)

        selected = collect.call_args.args[1]
        self.assertEqual(set(selected), expected)
        self.assertEqual(set(selected), set(source_adapters(PILOT_PROJECT)))
        self.assertIs(selected['TurismoFVG'].func, regional)
        self.assertEqual(selected['TurismoFVG'].args[0], prior_control)
        self.assertEqual(collect.call_args.kwargs['timeout'], 55)
        self.assertEqual(collect.call_args.kwargs['source_timeouts'],
                         {'TurismoFVG': 360, 'Paesi in Festa': 90,
                          'SagreFVG': 60, 'Pordenonelegge': 20,
                          'Pordenone Pensa': 25,
                          'Le Giornate del Cinema Muto': 30,
                          'Azalea': 20, 'CSS Udine': 20,
                          'Teatro Verdi Pordenone': 60,
                          'Teatro Verdi Trieste': 25,
                          'Villa Manin': 65,
                          'Magazzino delle Idee': 30,
                          'MESS': 10, 'Galleria Spazzapan': 10,
                          'Barcolana': 35})
        self.assertEqual(sum(collect.call_args.kwargs['source_timeouts'].values()), 860)
        blob.upload_from_string.assert_called_once()
        attems_audit.assert_called_once()
        attems_changes.assert_called_once_with(attems_audit.return_value)
        self.giro_watch.assert_called_once()
        saved = json.loads(blob.upload_from_string.call_args.args[0])
        self.assertEqual({name: item['status'] for name, item in saved['monitors'].items()},
                         {'Palazzo Attems': 'checked', 'GiroFVG': 'checked'})

    @patch('app.events.pilot_cloud.run_bounded_watch')
    @patch('app.events.pilot_cloud.attems_watch_changes', return_value=[])
    @patch('app.events.pilot_cloud.collect_attems_audit')
    @patch('app.events.pilot_cloud.collect')
    def test_weekly_annual_inventory_is_diagnostic_after_rolling_publication(
            self, collect, attems_audit, attems_changes, annual_watch):
        client, blob = self.client()
        from app.events import pilot_cloud
        with patch.object(pilot_cloud, 'annual_watch_due', return_value=True):
            control = {'schema': 'turismofvg-current-year-control-v1',
                       'current_year_window_urls': [
                           'https://www.turismofvg.it/eventi/prova']}
            collect.return_value = {'schema': 'pilot-events-v1', 'sources': {
                name: {'status': 'fresh', 'events': [],
                       **({'control_checkpoint': encode_control(control)}
                          if name == 'TurismoFVG' else {})}
                for name in APPROVED_SOURCES}}
            attems_audit.return_value = {
                'source_complete': False, 'event_api_count': 1,
                'current_exhibition_count': 0, 'blockers': []}
            annual_watch.return_value = {
                'source_complete': False, 'calendar_cards': 2,
                'calendar_pages': 1, 'missing_window_count': 1,
                'missing_window_urls': [
                    'https://www.turismofvg.it/eventi/prova']}
            with self.assertRaisesRegex(RuntimeError, 'annual inventory mismatch'):
                publish(client, project=PILOT_PROJECT)
        annual_watch.assert_called_once()
        saved = json.loads(blob.upload_from_string.call_args.args[0])
        self.assertEqual(saved['sources']['TurismoFVG']['status'], 'fresh')
        self.assertEqual(saved['monitors']['TurismoFVG annual inventory']['status'],
                         'review_required')

    @patch('app.events.pilot_cloud.attems_watch_changes', return_value=[])
    @patch('app.events.pilot_cloud.collect_attems_audit')
    @patch('app.events.pilot_cloud.collect')
    def test_girofvg_new_candidate_is_logged_without_failing_publication(
            self, collect, attems_audit, attems_changes):
        client, blob = self.client()
        collect.return_value = {'schema': 'pilot-events-v1', 'sources': {
            name: {'status': 'fresh', 'events': []} for name in APPROVED_SOURCES}}
        attems_audit.return_value = {'source_complete': False, 'event_api_count': 27,
                                     'current_exhibition_count': 1, 'blockers': []}
        self.giro_watch.return_value['changes'] = [
            {'reason': 'new_or_changed_active_card', 'url': 'https://www.girofvg.com/new'}]
        with patch('builtins.print') as output:
            publish(client, project=PILOT_PROJECT)
        self.assertNotIn('GiroFVG', collect.return_value['sources'])
        blob.upload_from_string.assert_called_once()
        saved = json.loads(blob.upload_from_string.call_args.args[0])
        self.assertEqual(saved['monitors']['GiroFVG']['status'], 'review_required')
        alerts = [json.loads(call.args[0]) for call in output.call_args_list
                  if 'event_candidate_watch_alert' in call.args[0]]
        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0]['alerts'][0]['monitor'], 'GiroFVG')
        self.assertEqual(alerts[0]['alerts'][0]['change_count'], 1)

    @patch('app.events.pilot_cloud.attems_watch_changes', return_value=['event_inventory_changed'])
    @patch('app.events.pilot_cloud.collect_attems_audit')
    @patch('app.events.pilot_cloud.collect')
    def test_palazzo_watch_detects_new_event_without_failing_publication(
            self, collect, attems_audit, attems_changes):
        client, blob = self.client()
        collect.return_value = {'schema': 'pilot-events-v1', 'sources': {
            name: {'status': 'fresh', 'events': []} for name in APPROVED_SOURCES
        }}
        attems_audit.return_value = {'source_complete': False, 'event_api_count': 28,
                                     'current_exhibition_count': 1, 'blockers': []}
        with patch('builtins.print') as output:
            publish(client, project=PILOT_PROJECT)
        blob.upload_from_string.assert_called_once()
        saved = json.loads(blob.upload_from_string.call_args.args[0])
        self.assertEqual(saved['monitors']['Palazzo Attems']['status'],
                         'review_required')
        self.assertTrue(any('event_candidate_watch_alert' in call.args[0]
                            for call in output.call_args_list))

    @patch('app.events.pilot_cloud.attems_watch_changes', return_value=[])
    @patch('app.events.pilot_cloud.collect_attems_audit')
    @patch('app.events.pilot_cloud.collect')
    def test_candidate_watch_unavailable_has_separate_alert(
            self, collect, attems_audit, attems_changes):
        client, blob = self.client()
        collect.return_value = {'schema': 'pilot-events-v1', 'sources': {
            name: {'status': 'fresh', 'events': []} for name in APPROVED_SOURCES}}
        attems_audit.return_value = {'source_complete': False,
                                     'event_api_count': 27,
                                     'current_exhibition_count': 1,
                                     'blockers': []}
        self.giro_watch.side_effect = TimeoutError('probe timed out')
        with patch('builtins.print') as output:
            publish(client, project=PILOT_PROJECT)
        saved = json.loads(blob.upload_from_string.call_args.args[0])
        self.assertEqual(saved['monitors']['GiroFVG']['status'], 'unverified')
        alerts = [json.loads(call.args[0]) for call in output.call_args_list
                  if 'event_candidate_watch_alert' in call.args[0]]
        self.assertEqual(alerts[0]['alerts'][0]['exception_type'], 'TimeoutError')

    @patch('app.events.pilot_cloud.collect')
    def test_partial_source_is_saved_as_stale_and_job_fails(self, collect):
        client, blob = self.client()
        collect.return_value = {'schema': 'pilot-events-v1', 'sources': {
            'TurismoFVG': {'status': 'stale', 'events': [{'title': 'Ultimo valido'}],
                           'last_attempt_verification': {'unresolved_count': 2}},
            'Azalea': {'status': 'fresh', 'events': [{'title': 'Nuovo'}]},
        }}
        with self.assertRaisesRegex(RuntimeError, 'TurismoFVG'):
            publish(client, project=PILOT_PROJECT,
                    adapters={'TurismoFVG': object(), 'Azalea': object()})
        blob.upload_from_string.assert_called_once()
        saved = json.loads(blob.upload_from_string.call_args.args[0])
        self.assertEqual(saved['sources']['TurismoFVG']['status'], 'stale')
        self.assertEqual(saved['sources']['TurismoFVG']['events'][0]['title'], 'Ultimo valido')

    @patch('app.events.pilot_cloud.collect')
    def test_failed_report_uses_latest_issues_instead_of_retained_snapshot(self, collect):
        old_review = {'url': 'https://www.villamanin.it/evento/old/', 'reason': 'old_issue'}
        previous = merge_collection(PILOT_PROJECT, None, {'Villa Manin': {
            'status': 'partial', 'events': [{'title': 'Last verified'}],
            'review_required': [old_review]}}, '2026-10-12T04:00:00Z')
        reviews = [
            {'url': 'https://www.villamanin.it/evento/new-a/', 'reason': 'publication_gate',
             'reasons': ['invalid_dates'], 'detail': 'private diagnostic'},
            {'url': 'https://www.villamanin.it/evento/new-b/', 'reason': 'detail_unavailable'}]
        pending = {'url': 'https://www.villamanin.it/evento/pending/',
                   'review_reason': 'pending_detail', 'detail': 'private diagnostic'}
        for prior in (previous, None):
            with self.subTest(previous=prior is not None):
                client, blob = self.client()
                collect.return_value = merge_collection(PILOT_PROJECT, prior, {'Villa Manin': {
                    'status': 'error', 'error_type': 'source_verification_failed',
                    'review_required': reviews, 'detail_candidates': [pending],
                    'verification': {'review_count': 2}}}, '2026-10-13T04:00:00Z')
                with patch('builtins.print') as output:
                    with self.assertRaisesRegex(RuntimeError, 'Villa Manin'):
                        publish(client, project=PILOT_PROJECT, adapters={'Villa Manin': object()})
                report = json.loads(output.call_args.args[0])['event_source_verification']['Villa Manin']
                self.assertEqual(report['review_count'], 2)
                self.assertEqual(report['pending_count'], 1)
                self.assertEqual(report['verification']['review_count'], 2)
                self.assertEqual([issue['url'] for issue in report['review_issues']],
                                 [item['url'] for item in reviews + [pending]])
                self.assertEqual(report['review_issues'][0]['reasons'], ['invalid_dates'])
                self.assertNotIn('private diagnostic', json.dumps(report))
                if prior:
                    saved = json.loads(blob.upload_from_string.call_args.args[0])
                    self.assertEqual(saved['sources']['Villa Manin']['review_required'], [old_review])

    @patch('app.events.pilot_cloud.collect')
    def test_recovered_report_uses_current_review_and_drops_failed_attempt(self, collect):
        client, blob = self.client()
        failed = merge_collection(PILOT_PROJECT, None, {'Villa Manin': {
            'status': 'error', 'review_required': [{'url': 'old', 'reason': 'old_issue'}]}},
            '2026-10-12T04:00:00Z')
        current = {'url': 'https://www.villamanin.it/evento/current/', 'reason': 'detail_conflict'}
        collect.return_value = merge_collection(PILOT_PROJECT, failed, {'Villa Manin': {
            'status': 'partial', 'events': [{'title': 'Verified'}],
            'review_required': [current], 'verification': {'review_count': 1}}},
            '2026-10-13T04:00:00Z')
        report = publish(client, project=PILOT_PROJECT, adapters={'Villa Manin': object()})['Villa Manin']
        self.assertEqual(report['review_count'], 1)
        self.assertEqual(report['pending_count'], 0)
        self.assertEqual(report['review_issues'], [current])
        self.assertEqual(report['failure_tag'], 'quarantined_cards')

    @patch('app.events.pilot_cloud.collect')
    def test_all_failed_sources_publish_failure_tags_and_fail_job(self, collect):
        client, blob = self.client()
        collect.return_value = {'schema': 'pilot-events-v1', 'sources': {
            'TurismoFVG': {'status': 'stale', 'events': [{'title': 'Ultimo valido'}],
                           'last_attempt_error_type': 'timeout'}}}
        with self.assertRaisesRegex(RuntimeError, 'TurismoFVG'):
            publish(client, project=PILOT_PROJECT, adapters={'TurismoFVG': object()})
        blob.upload_from_string.assert_called_once()
        saved = json.loads(blob.upload_from_string.call_args.args[0])
        self.assertEqual(saved['sources']['TurismoFVG']['status'], 'stale')

    @patch('app.events.pilot_cloud.collect')
    @patch('app.events.pilot_regional_verified.collect_regional_window_verified')
    def test_retry_failed_recollects_only_failed_source_with_checkpoint(
            self, regional, collect):
        client, blob = self.client()
        previous_control = {'schema': 'turismofvg-current-year-control-v1',
                            'as_of_date': '2026-10-05'}
        blob.download_as_bytes.return_value = json.dumps({
            'schema': 'pilot-events-v1', 'sources': {
                'TurismoFVG': {'status': 'stale',
                               'control_checkpoint': encode_control(previous_control)},
                'Azalea': {'status': 'fresh', 'events': []}},
            'monitors': {
                'Anteprima Sagre': {
                    'status': 'unverified', 'tag': 'upstream_unavailable',
                    'checked_at': '2026-10-08T08:00:00+00:00'},
                'Pro Loco FVG': {
                    'status': 'review_required',
                    'checked_at': '2026-10-11T04:00:00+00:00'}}}).encode('utf-8')
        collect.return_value = {'schema': 'pilot-events-v1', 'sources': {
            'TurismoFVG': {'status': 'fresh', 'events': []},
            'Azalea': {'status': 'fresh', 'events': []}}}
        publish(client, project=PILOT_PROJECT, retry_failed=True)
        selected = collect.call_args.args[1]
        self.assertEqual(set(selected), {'TurismoFVG'})
        self.assertIs(selected['TurismoFVG'].func, regional)
        self.assertEqual(selected['TurismoFVG'].args[0], previous_control)
        blob.upload_from_string.assert_called_once()
        self.giro_watch.assert_not_called()
        saved = json.loads(blob.upload_from_string.call_args.args[0])
        self.assertNotIn('Anteprima Sagre', saved['monitors'])
        self.assertNotIn('Pro Loco FVG', saved['monitors'])

    @patch('app.events.pilot_cloud.collect')
    def test_retry_failed_refuses_when_no_source_is_tagged(self, collect):
        client, blob = self.client()
        blob.download_as_bytes.return_value = json.dumps({
            'schema': 'pilot-events-v1', 'sources': {
                'Azalea': {'status': 'fresh', 'events': []}}}).encode('utf-8')
        with self.assertRaisesRegex(ValueError, 'no failed registered source'):
            publish(client, project=PILOT_PROJECT, retry_failed=True)
        collect.assert_not_called()
        blob.upload_from_string.assert_not_called()

    @patch('app.events.pilot_cloud.collect')
    def test_azalea_incomplete_source_fails_job(self, collect):
        client, blob = self.client()
        collect.return_value = {'schema': 'pilot-events-v1', 'sources': {
            'Azalea': {'status': 'stale', 'events': [{'title': 'Ultimo valido'}],
                       'last_attempt_verification': {'review_count': 1}},
            'TurismoFVG': {'status': 'fresh', 'events': []},
        }}
        with self.assertRaisesRegex(RuntimeError, 'Azalea'):
            publish(client, project=PILOT_PROJECT,
                    adapters={'Azalea': object(), 'TurismoFVG': object()})
        blob.upload_from_string.assert_called_once()

    @patch('app.events.pilot_cloud.collect')
    def test_spazzapan_inventory_change_fails_job(self, collect):
        client, blob = self.client()
        collect.return_value = {'schema': 'pilot-events-v1', 'sources': {
            'Galleria Spazzapan': {
                'status': 'stale', 'events': [{'title': 'Ultimo valido'}],
                'last_attempt_verification': {'review_count': 1}},
            'TurismoFVG': {'status': 'fresh', 'events': []},
        }}
        with self.assertRaisesRegex(RuntimeError, 'Galleria Spazzapan'):
            publish(client, project=PILOT_PROJECT,
                    adapters={'Galleria Spazzapan': object(),
                              'TurismoFVG': object()})
        blob.upload_from_string.assert_called_once()

    @patch('app.events.pilot_cloud.collect')
    def test_css_incomplete_source_fails_job(self, collect):
        client, blob = self.client()
        collect.return_value = {'schema': 'pilot-events-v1', 'sources': {
            'CSS Udine': {'status': 'stale', 'events': [],
                          'last_attempt_verification': {'review_count': 1}},
            'Azalea': {'status': 'fresh', 'events': []},
        }}
        with self.assertRaisesRegex(RuntimeError, 'CSS Udine'):
            publish(client, project=PILOT_PROJECT,
                    adapters={'CSS Udine': object(), 'Azalea': object()})
        blob.upload_from_string.assert_called_once()

    @patch('app.events.pilot_cloud.collect')
    def test_villa_manin_incomplete_source_fails_job(self, collect):
        client, blob = self.client()
        collect.return_value = {'schema': 'pilot-events-v1', 'sources': {
            'Villa Manin': {'status': 'stale', 'events': [],
                            'last_attempt_verification': {'review_count': 1}},
            'Azalea': {'status': 'fresh', 'events': []},
        }}
        with self.assertRaisesRegex(RuntimeError, 'Villa Manin'):
            publish(client, project=PILOT_PROJECT,
                    adapters={'Villa Manin': object(), 'Azalea': object()})
        blob.upload_from_string.assert_called_once()

    @patch('app.events.pilot_cloud.collect')
    def test_magazzino_incomplete_source_fails_job(self, collect):
        client, blob = self.client()
        collect.return_value = {'schema': 'pilot-events-v1', 'sources': {
            'Magazzino delle Idee': {'status': 'stale', 'events': [],
                                     'last_attempt_verification': {'review_count': 1}},
            'Azalea': {'status': 'fresh', 'events': []},
        }}
        with self.assertRaisesRegex(RuntimeError, 'Magazzino delle Idee'):
            publish(client, project=PILOT_PROJECT,
                    adapters={'Magazzino delle Idee': object(), 'Azalea': object()})
        blob.upload_from_string.assert_called_once()

    @patch('app.events.pilot_cloud.collect')
    def test_pnpensa_incomplete_source_fails_job(self, collect):
        client, blob = self.client()
        collect.return_value = {'schema': 'pilot-events-v1', 'sources': {
            'Pordenone Pensa': {'status': 'stale', 'events': [],
                                'last_attempt_verification': {'review_count': 1}},
            'Azalea': {'status': 'fresh', 'events': []},
        }}
        with self.assertRaisesRegex(RuntimeError, 'Pordenone Pensa'):
            publish(client, project=PILOT_PROJECT,
                    adapters={'Pordenone Pensa': object(), 'Azalea': object()})
        blob.upload_from_string.assert_called_once()

    @patch('app.events.pilot_cloud.collect')
    def test_verdi_pordenone_incomplete_source_fails_job(self, collect):
        client, blob = self.client()
        collect.return_value = {'schema': 'pilot-events-v1', 'sources': {
            'Teatro Verdi Pordenone': {
                'status': 'stale', 'events': [],
                'last_attempt_verification': {'review_count': 1}},
            'Azalea': {'status': 'fresh', 'events': []},
        }}
        with self.assertRaisesRegex(RuntimeError, 'Teatro Verdi Pordenone'):
            publish(client, project=PILOT_PROJECT,
                    adapters={'Teatro Verdi Pordenone': object(), 'Azalea': object()})
        blob.upload_from_string.assert_called_once()

    @patch('app.events.pilot_cloud.collect')
    def test_verdi_trieste_incomplete_source_fails_job(self, collect):
        client, blob = self.client()
        collect.return_value = {'schema': 'pilot-events-v1', 'sources': {
            'Teatro Verdi Trieste': {
                'status': 'stale', 'events': [],
                'last_attempt_verification': {'review_count': 1}},
            'Azalea': {'status': 'fresh', 'events': []},
        }}
        with self.assertRaisesRegex(RuntimeError, 'Teatro Verdi Trieste'):
            publish(client, project=PILOT_PROJECT,
                    adapters={'Teatro Verdi Trieste': object(), 'Azalea': object()})
        blob.upload_from_string.assert_called_once()

    @patch('app.events.pilot_cloud.collect')
    def test_paesi_in_festa_incomplete_source_fails_job(self, collect):
        client, blob = self.client()
        collect.return_value = {'schema': 'pilot-events-v1', 'sources': {
            'Paesi in Festa': {'status': 'stale', 'events': [{'title': 'Ultimo valido'}],
                               'last_attempt_verification': {'review_count': 1}},
            'Azalea': {'status': 'fresh', 'events': [{'title': 'Nuovo'}]},
        }}
        with self.assertRaisesRegex(RuntimeError, 'Paesi in Festa'):
            publish(client, project=PILOT_PROJECT,
                    adapters={'Paesi in Festa': object(), 'Azalea': object()})
        blob.upload_from_string.assert_called_once()

    @patch('app.events.pilot_cloud.collect')
    def test_paesi_in_festa_partial_source_does_not_fail_job(self, collect):
        client, blob = self.client()
        collect.return_value = {'schema': 'pilot-events-v1', 'sources': {
            'Paesi in Festa': {'status': 'partial', 'events': [{'title': 'Verificato'}],
                               'review_required': [{'url': 'https://paesiinfesta.com/bad/',
                                                    'reason': 'detail_conflict'}],
                               'verification': {'review_count': 1}},
            'Azalea': {'status': 'fresh', 'events': []},
        }}
        publish(client, project=PILOT_PROJECT,
                adapters={'Paesi in Festa': object(), 'Azalea': object()})
        blob.upload_from_string.assert_called_once()

    @patch('app.events.pilot_cloud.collect')
    def test_verified_partial_sources_do_not_fail_job(self, collect):
        client, blob = self.client()
        collect.return_value = {'schema': 'pilot-events-v1', 'sources': {
            'TurismoFVG': {'status': 'partial', 'events': [{'title': 'Valido'}],
                           'review_required': [{'url': 'https://www.turismofvg.it/eventi/bad',
                                                'reason': 'schedule_change'}],
                           'verification': {'source_complete': True, 'review_count': 1}},
            'Pordenone Pensa': {'status': 'partial', 'events': [{'title': 'Valido'}],
                                'review_required': [{'url': 'https://www.pnpensa.it/bad/',
                                                     'reason': 'additional_date'}],
                                'verification': {'source_complete': True, 'review_count': 1}},
        }}
        report = publish(client, project=PILOT_PROJECT,
                         adapters={'TurismoFVG': object(),
                                   'Pordenone Pensa': object()})
        self.assertEqual(report['TurismoFVG']['failure_tag'], 'quarantined_cards')
        self.assertEqual(report['Pordenone Pensa']['published_count'], 1)
        blob.upload_from_string.assert_called_once()

    @patch('app.events.pilot_cloud.collect')
    def test_sagrefvg_incomplete_source_fails_job(self, collect):
        client, blob = self.client()
        collect.return_value = {'schema': 'pilot-events-v1', 'sources': {
            'SagreFVG': {'status': 'stale', 'events': [{'title': 'Ultimo valido'}],
                         'last_attempt_verification': {'review_count': 1}},
            'Azalea': {'status': 'fresh', 'events': [{'title': 'Nuovo'}]},
        }}
        with self.assertRaisesRegex(RuntimeError, 'SagreFVG'):
            publish(client, project=PILOT_PROJECT,
                    adapters={'SagreFVG': object(), 'Azalea': object()})
        blob.upload_from_string.assert_called_once()

    @patch('app.events.pilot_cloud.collect')
    def test_pordenonelegge_incomplete_source_fails_job(self, collect):
        client, blob = self.client()
        collect.return_value = {'schema': 'pilot-events-v1', 'sources': {
            'Pordenonelegge': {'status': 'stale', 'events': [],
                               'last_attempt_verification': {'records_scanned': 120}},
            'Azalea': {'status': 'fresh', 'events': [{'title': 'Nuovo'}]},
        }}
        with self.assertRaisesRegex(RuntimeError, 'Pordenonelegge'):
            publish(client, project=PILOT_PROJECT,
                    adapters={'Pordenonelegge': object(), 'Azalea': object()})
        blob.upload_from_string.assert_called_once()

    @patch('app.events.pilot_cloud.collect')
    def test_cinema_muto_incomplete_source_fails_job(self, collect):
        client, blob = self.client()
        collect.return_value = {'schema': 'pilot-events-v1', 'sources': {
            'Le Giornate del Cinema Muto': {
                'status': 'stale', 'events': [],
                'last_attempt_verification': {'parsed_count': 87}},
            'Azalea': {'status': 'fresh', 'events': [{'title': 'Nuovo'}]},
        }}
        with self.assertRaisesRegex(RuntimeError, 'Le Giornate del Cinema Muto'):
            publish(client, project=PILOT_PROJECT,
                    adapters={'Le Giornate del Cinema Muto': object(),
                              'Azalea': object()})
        blob.upload_from_string.assert_called_once()


if __name__ == '__main__':
    unittest.main()
