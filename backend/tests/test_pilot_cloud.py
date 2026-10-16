import json
import unittest
from datetime import date
from unittest.mock import Mock, patch

from app.events.pilot_catalog import PILOT_PROJECT
from app.events.pilot_cloud import annual_watch_due, publish
from app.events.pilot_regional_checkpoint import encode_control
from app.events.pilot_sources import source_adapters
from app.events.pilot_source_policy import APPROVED_SOURCES


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
                          'Teatro Verdi Pordenone': 50,
                          'Teatro Verdi Trieste': 25,
                          'Villa Manin': 65,
                          'Magazzino delle Idee': 30,
                          'MESS': 10, 'Galleria Spazzapan': 10,
                          'Barcolana': 35})
        self.assertEqual(sum(collect.call_args.kwargs['source_timeouts'].values()), 850)
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
    def test_girofvg_new_candidate_stops_job_without_publishing_a_card(
            self, collect, attems_audit, attems_changes):
        client, blob = self.client()
        collect.return_value = {'schema': 'pilot-events-v1', 'sources': {
            name: {'status': 'fresh', 'events': []} for name in APPROVED_SOURCES}}
        attems_audit.return_value = {'source_complete': False, 'event_api_count': 27,
                                     'current_exhibition_count': 1, 'blockers': []}
        self.giro_watch.return_value['changes'] = [
            {'reason': 'new_or_changed_active_card', 'url': 'https://www.girofvg.com/new'}]
        with self.assertRaisesRegex(RuntimeError, 'GiroFVG has changed event candidates'):
            publish(client, project=PILOT_PROJECT)
        self.assertNotIn('GiroFVG', collect.return_value['sources'])
        blob.upload_from_string.assert_called_once()

    @patch('app.events.pilot_cloud.attems_watch_changes', return_value=['event_inventory_changed'])
    @patch('app.events.pilot_cloud.collect_attems_audit')
    @patch('app.events.pilot_cloud.collect')
    def test_palazzo_watch_detects_new_event_after_catalog_is_saved(
            self, collect, attems_audit, attems_changes):
        client, blob = self.client()
        collect.return_value = {'schema': 'pilot-events-v1', 'sources': {
            name: {'status': 'fresh', 'events': []} for name in APPROVED_SOURCES
        }}
        attems_audit.return_value = {'source_complete': False, 'event_api_count': 28,
                                     'current_exhibition_count': 1, 'blockers': []}
        with self.assertRaisesRegex(RuntimeError, 'Palazzo Attems inventory changed'):
            publish(client, project=PILOT_PROJECT)
        blob.upload_from_string.assert_called_once()

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
