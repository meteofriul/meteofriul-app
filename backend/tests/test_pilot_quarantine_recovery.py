"""Regression tests for reusable quarantine recovery, using unchanged source data."""
from copy import deepcopy
from datetime import date, datetime, timezone
from pathlib import Path
import json
import unittest

from app.events.pilot_details import DETAIL_INSPECTION_VERSION, promote_candidate, reusable_detail
from app.events.pilot_regional_display_audit import create_year_display_audit
from app.events.pilot_regional_identity import single_month_calendar_day
from app.events.pilot_regional_forward_audit import inspect_candidate
from app.events.pilot_regional_year_control import INSPECTION_VERSION, inspect_item
from app.events.pilot_sagrefvg import event_from_api
from app.events.pilot_schedule import schedule_notice
from app.events.pilot_source_policy import validate_candidate

FIXTURE = json.loads((Path(__file__).parent / 'fixtures' /
                      'events_quarantine_october_15_2026.json').read_text(encoding='utf-8'))
TODAY = date(2026, 10, 15)


class QuarantineRecoveryTests(unittest.TestCase):
    def project(self, items):
        return create_year_display_audit({
            'schema': 'turismofvg-current-year-control-v1',
            'inspection_version': INSPECTION_VERSION,
            'as_of_date': TODAY.isoformat(), 'attempts': {},
            'entries': {x['url']: x['entry'] for x in items},
            'results': {x['url']: inspect_item(x['url'], x['entry'], x['html'], today=TODAY)
                        for x in items}}, today=TODAY)

    def test_all_nine_real_recoveries_use_unmodified_source_data(self):
        audit = self.project(FIXTURE['regional'])
        expected = {x['url'] for x in FIXTURE['regional'] if x['number'] in (2, 7, 10, 11, 12, 13, 14)}
        self.assertEqual({x['url'] for x in audit['cards']}, expected)
        for card in audit['cards']:
            with self.subTest(url=card['url']):
                self.assertEqual(validate_candidate(card, today=TODAY), [])
        for item in FIXTURE['sagre']:
            self.assertEqual(validate_candidate(event_from_api(item['row']), today=TODAY), [])
        self.assertEqual(len(audit['cards']) + len(FIXTURE['sagre']), 9)

    def test_cancelled_event_and_unparsed_programmes_remain_excluded(self):
        for item in FIXTURE['regional']:
            if item['number'] not in (1, 3, 4, 6):
                continue
            with self.subTest(number=item['number']):
                result = inspect_item(item['url'], item['entry'], item['html'], today=TODAY)
                self.assertNotEqual(result['status'], 'detail_aligned')
                self.assertEqual(self.project([item])['cards'], [])

    def test_month_calendar_days_survive_projection_without_expanding_month(self):
        items = [x for x in FIXTURE['regional'] if x['number'] in (11, 12, 13, 14)]
        expected = {x['url']: x['entry']['candidate']['listing_occurrences'][0] for x in items}
        for card in self.project(items)['cards']:
            self.assertEqual((card['start_date'], card['end_date'], card['sort_date']),
                             (expected[card['url']],) * 3)
            self.assertEqual(card['schedule_kind'], 'single')
            self.assertIn('ottobre 2026', card['date_label'])

    @staticmethod
    def candidate(title='Osservaizoni della natura', days=None):
        return {'source': 'TurismoFVG', 'url': 'https://www.turismofvg.it/eventi/altra-iniziativa',
                'title': title, 'event_city': 'Udine', 'discovery_kind': 'filtered_calendar',
                'listing_occurrences': days if days is not None else ['2027-02-12']}

    @staticmethod
    def metadata(title='Osservazioni della natura'):
        return {'date_full': '12 febbraio 2027', 'event_city': 'Udine',
                'detail_title': title, 'venue': 'Auditorium Comunale'}

    def test_transposition_generalizes_to_other_title_date_and_url(self):
        event = promote_candidate(self.candidate(), self.metadata())
        self.assertEqual(event['title'], 'Osservazioni della natura')
        self.assertEqual(event['title_reconciliation'], 'single_adjacent_transposition')
        self.assertEqual(event['start_date'], '2027-02-12')

    def test_title_repair_rejects_different_event_or_unproven_identity(self):
        variants = [
            ({'event_city': 'Gorizia'}, {}),
            ({'listing_occurrences': ['2027-02-13']}, {}),
            ({'listing_occurrences': []}, {}),
            ({'discovery_kind': 'sitemap_detail'}, {}),
            ({'url': 'https://example.com/evento'}, {}),
            ({'title': 'Osservazioni della cultura'}, {}),
            ({'title': 'Osservazxoni della natura'}, {}),
            ({'title': 'Osservaizoni della natura 2026'}, {'detail_title': 'Osservazioni della natura 2027'}),
            ({'title': 'Caro amico'}, {'detail_title': 'Caor amico'}),
            ({}, {'date_full': 'febbraio 2027'}),
        ]
        for changes, metadata in variants:
            with self.subTest(changes=changes, metadata=metadata):
                self.assertIsNone(promote_candidate({**self.candidate(), **changes},
                                                    {**self.metadata(), **metadata}))

    def test_venue_prefix_requires_matching_venue_dates_and_town(self):
        candidate = self.candidate('Auditorium Comunale: Racconti')
        metadata = {**self.metadata('Racconti'), 'venue': 'Auditorium Comunale in Via Roma, 10 Udine'}
        self.assertEqual(promote_candidate(candidate, metadata)['title_reconciliation'],
                         'verified_venue_prefix')
        for key, value in (('venue', 'Teatro Comunale'), ('date_full', '13 febbraio 2027'),
                           ('event_city', 'Pordenone'), ('detail_title', 'Racconti diversi')):
            with self.subTest(field=key):
                self.assertIsNone(promote_candidate(candidate, {**metadata, key: value}))
        self.assertIsNone(promote_candidate({**candidate, 'title': 'Rassegna culturale: Racconti'}, metadata))

    def test_month_label_rejects_badges_in_another_month_or_year(self):
        for days in (['2027-03-12'], ['2026-02-12'], ['2027-02-12', '2027-03-12']):
            self.assertIsNone(promote_candidate(self.candidate('Racconti', days),
                             {**self.metadata('Racconti'), 'date_full': 'febbraio 2027'}))

    def test_single_month_rule_rejects_missing_multiple_invalid_or_conflicting_dates(self):
        candidate = self.candidate('Racconti')
        event = {'event_city': 'Udine', 'start_date': '2027-02-12',
                 'end_date': '2027-02-12', 'occurrences': ['2027-02-12']}
        self.assertEqual(single_month_calendar_day(candidate, 'febbraio 2027', event), date(2027, 2, 12))
        for change in ({'listing_occurrences': []},
                       {'listing_occurrences': ['2027-02-12', '2027-02-13']},
                       {'listing_occurrences': ['2027-02-30']},
                       {'discovery_kind': 'sitemap_detail'}, {'event_city': 'Trieste'}):
            self.assertIsNone(single_month_calendar_day({**candidate, **change}, 'febbraio 2027', event))
        for change in ({'occurrences': []}, {'end_date': '2027-02-13'}, {'start_date': '2027-02-11'}):
            self.assertIsNone(single_month_calendar_day(candidate, 'febbraio 2027', {**event, **change}))
        self.assertIsNone(single_month_calendar_day(candidate, 'febbraio 2026', event))

    def test_weather_policy_and_joint_verbs_are_not_completed_cancellations(self):
        # Live regressions: Decora la tua zucca and both Borgo market dates.
        for text in (
                'In caso di maltempo verrà rinviato o annullato.',
                'Il mercatino viene annullato in caso di avverse condizioni meteo.',
                'L’evento verrà rinviato o annullato in caso di pioggia.',
                'In caso di pioggia viene rinviato oppure annullato.',
                'Il concerto viene annullato in caso di maltempo.',
                'In caso di maltempo sarà sospeso o rinviato o annullato.'):
            with self.subTest(text=text):
                self.assertFalse(schedule_notice(text))
        for text in (
                'Il mercatino viene annullato per maltempo.',
                'In caso di pioggia ingresso coperto, ma il mercatino viene annullato.',
                'Il concerto è stato annullato in caso di pioggia.',
                'In caso di pioggia sarà rinviato o annullato, ma oggi il concerto è stato cancellato.',
                'In caso di maltempo sarà rinviato o annullato; concerto rinviato a dicembre.',
                'Evento rinviato. Il mercatino viene annullato in caso di pioggia.',
                'In caso di pioggia sarà rinviato, spettacolo annullato.'):
            with self.subTest(text=text):
                self.assertTrue(schedule_notice(text))

    def test_weather_condition_does_not_hide_actual_notices(self):
        for text in ('In casodi maltempo il concerto sarà annullato.',
                     'Il concerto sarà annullato in caso di pioggia.',
                     'Sospeso in caso di condizioni meteo avverse.'):
            self.assertFalse(schedule_notice(text), text)
        for text in ('Evento annullato. In casodi maltempo il parcheggio è chiuso.',
                     'In caso di maltempo sarà annullato. Il concerto è rinviato.',
                     'In caso di maltempo sarà annullato; evento rinviato a dicembre.',
                     'In casodi maltempo sarà annullato, ma il concerto è stato cancellato.',
                     'In caso di pioggia la festa è stata annullata.',
                     'In caso di maltempo sarà annullato, concerto rinviato a dicembre.'):
            self.assertTrue(schedule_notice(text), text)
        self.assertTrue(schedule_notice('Evento annullato', 'In casodi maltempo parcheggio chiuso'))

    def test_sagra_separator_does_not_split_event_hyphens(self):
        source = deepcopy(FIXTURE['sagre'][0]['row'])
        for separator in ('-', '–', '—', ' - ', '– '):
            source['title'] = 'San Quirino (PN)' + separator + 'Musica folk-rock'
            self.assertEqual(event_from_api(source)['title'], 'Musica folk-rock')
        for title in ('San Quirino (GO)-Musica folk-rock', 'San Quirino (PN)-'):
            with self.subTest(title=title), self.assertRaises(ValueError):
                event_from_api({**source, 'title': title})

    def test_hamlet_uses_address_and_preserves_coordinates(self):
        source = deepcopy(FIXTURE['sagre'][1]['row'])
        event = event_from_api(source)
        self.assertEqual((event['event_city'], event['place']), ('Stregna', 'Tribil Superiore'))
        self.assertEqual((event['lat'], event['lon']), (46.1413638, 13.6186628))
        source.update(title='Borgo di prova (UD)-Festa del borgo',
                      start_date='2027-10-18 08:00:00', end_date='2027-10-18 23:00:00')
        source['venue'].update(city='Borgo di prova', address='Via Prova 1, 33100 Udine UD',
                               geo_lat=46.062, geo_lng=13.234)
        self.assertEqual(event_from_api(source)['event_city'], 'Udine')

    def test_hamlet_rejects_unproven_parent_province_or_coordinates(self):
        original = FIXTURE['sagre'][1]['row']
        for changes in ({'address': ''}, {'address': 'Tribil superiore 45, Stregna UD'},
                        {'address': 'Tribil superiore 45, 33040 Stregna GO'},
                        {'address': 'Tribil superiore 45, 33040 Comune inesistente UD'},
                        {'city': 'Altra frazione'}, {'province': 'Gorizia'},
                        {'geo_lat': None, 'geo_lng': None},
                        {'geo_lat': 45.8, 'geo_lng': 13.0}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                event_from_api({**original, 'venue': {**original['venue'], **changes}})

    def test_month_detail_with_conflicting_prose_stays_in_review(self):
        from tests.test_pilot_regional_forward_audit import RegionalForwardAuditTests
        # Reuse realistic provider markup; do not mock the parser.
        for description in ('Passeggiata il 10 ottobre.', 'Passeggiata il 9 novembre 2026.'):
            result = inspect_candidate(
                {**RegionalForwardAuditTests().candidate(), 'listing_occurrences': ['2026-10-09']},
                RegionalForwardAuditTests().detail(date_text='ottobre 2026', description=description),
                today=date(2026, 10, 5))
            self.assertEqual(result['status'], 'review_required')
            self.assertEqual(result['reason'], 'month_calendar_prose_conflict')

    def test_previous_detail_cache_is_invalidated(self):
        previous = {'checked_at': datetime.now(timezone.utc).isoformat(), 'facts': {},
                    'notice': False, 'inspection_version': DETAIL_INSPECTION_VERSION - 1}
        self.assertFalse(reusable_detail(previous, allow_description_excerpt=False))
        previous['inspection_version'] = DETAIL_INSPECTION_VERSION
        self.assertTrue(reusable_detail(previous, allow_description_excerpt=False))


if __name__ == '__main__':
    unittest.main()
