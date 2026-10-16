import unittest
from datetime import date
from unittest.mock import patch
from app.events.pilot_source_policy import validate_candidate, APPROVED_SOURCES, gate_batch
from app.events.pilot_pordenonelegge import parse_programme
from app.events.pilot_cinema_muto import collect_cinema_muto
from tests.test_pilot_cinema_muto import CinemaMutoTests
from tests.test_pilot_pordenonelegge import card, page


class SourcePolicyTests(unittest.TestCase):
    @staticmethod
    def azalea_proof():
        url = 'https://www.azalea.it/eventi/example/'
        return {'collection_mode': 'complete-official-upcoming-archive',
                'source_complete': True,
                'archive_pages': [{'url': 'https://www.azalea.it/eventi/',
                                   'cards': 1, 'new_urls': 1}],
                'listing_count': 1, 'detail_count': 1, 'included_count': 1,
                'sitemap_event_urls': 1, 'sitemap_unlisted_delta_checked': 0,
                'review_count': 0,
                'listing_records': [{'url': url, 'title': 'Example',
                                     'date': '2026-09-06', 'city': 'Codroipo'}],
                'detail_records': [{'url': url, 'disposition': 'included'}]}

    @staticmethod
    def retrospective_proof():
        return {'as_of_date': '2026-09-06', 'horizon_complete': True,
                'windows': [
                    {'start': '2026-01-01', 'end': '2026-09-05',
                     'declared_results': 1, 'cards_seen': 1, 'pages': 1},
                    {'start': '2025-01-01', 'end': '2025-12-31',
                     'declared_results': 0, 'cards_seen': 0, 'pages': 1},
                    {'start': '2024-01-01', 'end': '2024-12-31',
                     'declared_results': 0, 'cards_seen': 0, 'pages': 1}],
                'older_overflow': {'start': '1900-01-01', 'end': '2023-12-31',
                                   'declared_results': 0},
                'declared_results': 1, 'cards_seen': 1,
                'unresolved_orphans': 0}

    def candidate(self, **changes):
        return {"source": "Azalea", "url": "https://www.azalea.it/eventi/example/",
                "title": "Example", "event_city": "Codroipo", "start_date": "2026-09-06",
                "date_evidence_kind": "event_schedule", "date_evidence": "06.09.2026", **changes}

    def check(self, **changes):
        return validate_candidate(self.candidate(**changes), today=date(2026, 9, 6))

    def test_verified_date_accepted(self):
        self.assertEqual(self.check(), [])

    def test_coordinates_must_be_finite_and_paired(self):
        self.assertIn('invalid_lat', self.check(lat=float('nan'), lon=13))
        self.assertIn('incomplete_coordinates', self.check(lat=46))
        self.assertIn('invalid_lon', self.check(lat=46, lon=200))
        self.assertEqual(self.check(lat=None, lon=None), [])

    def test_editorial_date_rejected(self):
        self.assertIn("event_date_not_verified", self.check(date_evidence_kind="datePublished"))

    def test_missing_year_rejected(self):
        self.assertIn("invalid_dates", self.check(start_date="6 settembre"))

    def test_past_event_rejected(self):
        self.assertIn("past_event", self.check(start_date="2026-09-05"))

    def test_turismofvg_end_only_deadline_has_no_fabricated_start(self):
        event = self.candidate(
            source='TurismoFVG',
            url='https://www.turismofvg.it/eventi/mostra',
            start_date=None, end_date='2027-01-07',
            schedule_kind='end_only', date_evidence='Fino al 7 gennaio 2027')
        self.assertEqual(validate_candidate(event, today=date(2026, 10, 5)), [])
        self.assertIn('invalid_end_only_schedule', validate_candidate(
            {**event, 'start_date': '2026-10-05'}, today=date(2026, 10, 5)))
        self.assertIn('invalid_end_only_schedule', validate_candidate(
            {**event, 'date_evidence': 'Fino al 8 gennaio 2027'},
            today=date(2026, 10, 5)))
        self.assertIn('invalid_dates', validate_candidate(
            {**event, 'end_date': '7 gennaio 2027'}, today=date(2026, 10, 5)))

    def test_cancelled_requires_review(self):
        self.assertIn("schedule_requires_review", self.check(event_status="cancelled"))

    def test_untrusted_link_rejected(self):
        self.assertIn("invalid_source_url", self.check(url="https://www.azalea.it.evil.test/eventi/a"))

    def test_all_sources_registered(self):
        self.assertEqual(len(APPROVED_SOURCES), 15)

    def test_every_source_passes_same_gate(self):
        for source, url in APPROVED_SOURCES.items():
            event = self.candidate(source=source, url=url, time='25:00')
            batch = {'status': 'ok', 'events': [event]}
            if source == 'Azalea':
                event['url'] = 'https://www.azalea.it/eventi/example/'
                event['end_date'] = '2026-09-06'
                batch['verification'] = self.azalea_proof()
            elif source in {'CSS Udine', 'Pordenone Pensa', 'Teatro Verdi Pordenone',
                            'Teatro Verdi Trieste', 'Villa Manin',
                            'Magazzino delle Idee', 'MESS',
                            'Galleria Spazzapan', 'Barcolana'}:
                result = gate_batch(source, batch, today=date(2026, 9, 6))
                self.assertEqual(result['status'], 'error')
                self.assertEqual(result['error_type'], 'source_verification_failed')
                continue
            elif source == 'Pordenonelegge':
                days = ('2026-09-16', '2026-09-17', '2026-09-18')
                batch = parse_programme(page(''.join(card(day=day) for day in days), days=days))
                for item in batch['events']:
                    item['time'] = '25:00'
            elif source == 'Le Giornate del Cinema Muto':
                _, _, _, get = CinemaMutoTests().fixture()
                batch = collect_cinema_muto(get=get)
                batch['events'][0]['time'] = '25:00'
                result = gate_batch(source, batch, today=date(2026, 9, 6))
                self.assertEqual(result['status'], 'error')
                self.assertEqual(result['error_type'], 'source_verification_failed')
                continue
            elif source == 'TurismoFVG':
                event['detail_status'] = 'inspected'
                batch['verification'] = {'collection_mode': 'annual-date-filters',
                    'horizon_complete': True,
                    'overflow': {'start': '2029-01-01', 'end': '2099-12-31',
                                 'declared_results': 0},
                    'windows': [{'start': '2026-09-06', 'end': '2026-12-31',
                                 'declared_results': 1, 'cards_seen': 1, 'pages': 1},
                                {'start': '2027-01-01', 'end': '2027-12-31',
                                 'declared_results': 0, 'cards_seen': 0, 'pages': 1},
                                {'start': '2028-01-01', 'end': '2028-12-31',
                                 'declared_results': 0, 'cards_seen': 0, 'pages': 1}],
                    'declared_results': 1, 'cards_seen': 1,
                    'pages': 3, 'verified_events': 1, 'unresolved_count': 0,
                    'sitemap_only_unclassified': 0,
                    'retrospective': self.retrospective_proof()}
            elif source == 'Paesi in Festa':
                batch['excluded'] = [{'reason': 'outside_fvg'}]
                batch['verification'] = {
                    'list_counts': {'sagre': 1, 'rievocazioni': 1},
                    'listed_cards': 2, 'detail_urls': 2,
                    'detail_pages_read': 1, 'outside_fvg_urls': 1,
                    'quarantined_before_detail': 0,
                    'surface_counts': {name: {'fvg_cards_examined': 1,
                                              'active_fvg_urls': 1}
                                       for name in ('home', 'fvg', 'udine',
                                                    'pordenone', 'archive')},
                    'surface_date': '2026-09-06',
                    'surface_active_urls': 1, 'extra_active_urls': 0,
                    'sitemap': {'baseline': '2026-10-06T00:00:00+00:00',
                                'post_maps_read': 1, 'posts_seen': 2,
                                'posts_in_scope': 1, 'changed_unlisted': 0,
                                'changed_checked': 0, 'unknown_paths': 0,
                                'active_added': 0, 'review_count': 0},
                    'review_count': 0, 'excluded_count': 1}
            elif source == 'SagreFVG':
                batch['verification'] = {
                    'collection_mode': 'complete-annual-api-pages',
                    'windows': [
                        {'start': '2026-01-01', 'end': '2026-12-31',
                         'declared_results': 1, 'records_read': 1, 'pages_read': 1},
                        {'start': '2027-01-01', 'end': '2027-12-31',
                         'declared_results': 0, 'records_read': 0, 'pages_read': 1},
                        {'start': '2028-01-01', 'end': '2028-12-31',
                         'declared_results': 0, 'records_read': 0, 'pages_read': 1}],
                    'overflow_start': '2029-01-01', 'overflow_total': 0,
                    'records_scanned': 1, 'past_count': 0,
                    'active_count': 1, 'review_count': 0}
            result = gate_batch(source, batch, today=date(2026,9,6))
            self.assertEqual(result['events'], [])
            self.assertIn('invalid_time', result['review_required'][0]['reasons'])

    @patch('app.events.pilot_source_policy.azalea_batch_verified', return_value=True)
    def test_one_identifiable_generic_exclusion_is_quarantined(self, verified):
        valid = self.candidate(url='https://www.azalea.it/eventi/valid/')
        invalid = self.candidate(url='https://www.azalea.it/eventi/invalid/',
                                 time='25:00')
        result = gate_batch('Azalea', {'status': 'ok', 'events': [valid, invalid]},
                            today=date(2026, 9, 6))
        self.assertEqual(result['status'], 'partial')
        self.assertEqual(result['events'], [valid])
        self.assertEqual(result['review_required'][0]['url'], invalid['url'])
        self.assertEqual(result['publication_gate']['excluded_count'], 1)

    @patch('app.events.pilot_source_policy.azalea_batch_verified', return_value=True)
    def test_generic_exclusion_still_blocks_systemic_or_untraceable_failures(
            self, verified):
        valid = self.candidate(url='https://www.azalea.it/eventi/valid/')
        invalid = self.candidate(url='https://www.azalea.it/eventi/invalid/',
                                 time='25:00')
        cases = (
            [invalid],
            [valid, invalid, self.candidate(
                url='https://www.azalea.it/eventi/other-invalid/', time='25:00')],
            [valid, self.candidate(url='https://wrong.example/eventi/bad/',
                                   time='25:00')],
            [valid, self.candidate(url=valid['url'], time='25:00')],
        )
        for events in cases:
            with self.subTest(events=events):
                result = gate_batch('Azalea', {'status': 'ok', 'events': events},
                                    today=date(2026, 9, 6))
                self.assertEqual(result['status'], 'error')
                self.assertEqual(result['error_type'],
                                 'publication_gate_exclusions')

    def test_turismofvg_needs_complete_batch_proof(self):
        event = self.candidate(source='TurismoFVG',
            url='https://www.turismofvg.it/eventi/prova', detail_status='inspected')
        batch = {'status': 'ok', 'events': [event]}
        failed = gate_batch('TurismoFVG', batch, today=date(2026, 9, 6))
        self.assertEqual(failed['status'], 'error')
        self.assertEqual(failed['error_type'], 'source_verification_failed')
        batch['verification'] = {'declared_results': 2, 'cards_seen': 1, 'pages': 1,
                                 'verified_events': 1, 'unresolved_count': 0}
        self.assertEqual(gate_batch('TurismoFVG', batch, today=date(2026, 9, 6))['status'], 'error')
        batch['verification']['cards_seen'] = 2
        self.assertEqual(gate_batch('TurismoFVG', batch, today=date(2026, 9, 6))['status'], 'error')
        batch['verification'].update(collection_mode='annual-date-filters',
            horizon_complete=True, pages=3,
            overflow={'start': '2029-01-01', 'end': '2099-12-31',
                      'declared_results': 0},
            windows=[{'start': '2026-09-06', 'end': '2026-12-31',
                      'declared_results': 2, 'cards_seen': 2, 'pages': 1},
                     {'start': '2027-01-01', 'end': '2027-12-31',
                      'declared_results': 0, 'cards_seen': 0, 'pages': 1},
                     {'start': '2028-01-01', 'end': '2028-12-31',
                      'declared_results': 0, 'cards_seen': 0, 'pages': 1}],
            sitemap_only_unclassified=0,
            retrospective=self.retrospective_proof())
        self.assertEqual(gate_batch('TurismoFVG', batch, today=date(2026, 9, 6))['status'], 'ok')
        batch['verification']['retrospective']['unresolved_orphans'] = 1
        self.assertEqual(gate_batch('TurismoFVG', batch, today=date(2026, 9, 6))['status'], 'error')
        batch['verification']['retrospective']['unresolved_orphans'] = 0
        batch['verification']['sitemap_only_unclassified'] = 1
        self.assertEqual(gate_batch('TurismoFVG', batch, today=date(2026, 9, 6))['status'], 'error')
        batch['verification']['sitemap_only_unclassified'] = 0
        batch['verification']['overflow']['declared_results'] = 1
        self.assertEqual(gate_batch('TurismoFVG', batch, today=date(2026, 9, 6))['status'], 'error')

    def test_unknown_time_is_allowed_but_conflicting_occurrence_is_not(self):
        self.assertEqual(self.check(time=None), [])
        self.assertIn('occurrence_outside_range', self.check(occurrences=['2026-09-10']))

    def test_gate_does_not_mutate_input_or_revive_rejected_batch(self):
        batch = {'status': 'ok', 'events': [self.candidate(time='25:00')]}
        result = gate_batch('Azalea', batch, today=date(2026,9,6))
        self.assertEqual(len(batch['events']), 1)
        self.assertEqual(result['status'], 'error')
        self.assertEqual(result['error_type'], 'source_verification_failed')

    def test_azalea_proof_checks_counts_and_prior_future_cards(self):
        event = self.candidate(end_date='2026-09-06')
        batch = {'status': 'ok', 'events': [event],
                 'verification': self.azalea_proof()}
        self.assertEqual(gate_batch('Azalea', batch, today=date(2026, 9, 6))['status'], 'ok')
        batch['verification']['detail_count'] = 0
        self.assertEqual(gate_batch('Azalea', batch, today=date(2026, 9, 6))['status'], 'error')
        batch['verification']['detail_count'] = 1
        old = self.azalea_proof()
        old['listing_records'].append({'url': 'https://www.azalea.it/eventi/missing/',
                                       'title': 'Missing', 'date': '2026-09-07',
                                       'city': 'Codroipo'})
        failed = gate_batch('Azalea', batch, today=date(2026, 9, 6),
                            previous_batch={'verification': old})
        self.assertEqual(failed['error_type'], 'source_verification_failed')
