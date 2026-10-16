"""Offline regressions for audit EV-01/02/03, through projection and HTTP."""
import json
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from app.events.pilot_catalog import merge_collection, query_catalog, PILOT_PROJECT
from app.events.pilot_http import application
from app.events.pilot_regional_display_audit import create_year_display_audit
from app.events.pilot_regional_year_control import SCHEMA, INSPECTION_VERSION
from app.events.pilot_source_policy import gate_batch, validate_candidate
from app.events.pilot_spazzapan import SOURCE, parse_spazzapan
from app.events.pilot_sagrefvg import event_from_api


NOW = datetime.fromisoformat('2026-10-15T12:00:00+00:00')


def project(title, text, *, interpretation='', event=None):
    url = 'https://www.turismofvg.it/eventi/audit-schedule'
    control = {
        'schema': SCHEMA, 'inspection_version': INSPECTION_VERSION,
        'as_of_date': NOW.date().isoformat(), 'attempts': {},
        'entries': {url: {'candidate': {'url': url}}},
        'results': {url: {
            'status': 'detail_aligned', 'detail_date_full': text,
            'schedule_interpretation': interpretation,
            'event': {'title': title, 'event_city': 'Udine', **(event or {})},
        }},
    }
    audit = create_year_display_audit(control, today=NOW.date())
    assert not audit['review'], audit['review']
    return audit['cards'][0]


def catalogue(card, now=NOW):
    return merge_collection(PILOT_PROJECT, None, {
        card['source']: {'status': 'ok', 'events': [card]},
    }, now.isoformat())


class EventScheduleContractTests(unittest.TestCase):
    def test_audit_periods_keep_unknown_opening_days_through_http(self):
        for title, text in (
            ('Barbacan Produce 2026', '12 aprile 2026 - 13 dicembre 2026'),
            ('Sale cimeli Julia', '25 gennaio 2026 - 13 dicembre 2026'),
            ('Cose di vecchie case', '18 aprile 2026 - 17 ottobre 2026'),
        ):
            with self.subTest(title=title):
                card = project(title, text,
                               interpretation='bounded_period_needs_opening_evidence')
                self.assertEqual(card['opening_days_status'], 'unknown')
                self.assertNotIn('occurrences', card)
                self.assertEqual(validate_candidate(card, today=NOW.date()), [])
                visible = self.http_card(card)
                self.assertEqual(visible['opening_days_status'], 'unknown')

    def http_card(self, card):
        return self.http_payload(catalogue(card))['events'][0]

    def http_payload(self, catalog):
        status = []
        with patch('app.events.pilot_http.load_catalog', return_value=catalog), \
                patch('app.events.pilot_http.datetime') as clock:
            clock.now.return_value = NOW
            body = application({
                'REQUEST_METHOD': 'GET', 'PATH_INFO': '/api/local/events',
                'QUERY_STRING': 'lat=46.0635&lon=13.2358&radius=50&limit=100',
            }, lambda code, headers: status.append(code))
        self.assertEqual(status, ['200 OK'])
        return json.loads(b''.join(body))

    def test_integrated_degraded_catalog_preserves_schedules_and_reconciled_spazzapan(self):
        fixtures = Path(__file__).with_name('fixtures')
        data = json.loads((fixtures / 'spazzapan_2026.json').read_text(encoding='utf-8'))
        extra = json.loads((fixtures / 'spazzapan_october_15_2026.json').read_text(encoding='utf-8'))
        data['surfaces']['current_exhibitions']['articles'] = [
            row for row in data['surfaces']['current_exhibitions']['articles'] if row['id'] != 232607]
        data['surfaces']['news']['articles'] = [
            row for row in data['surfaces']['news']['articles'] if row['id'] != 232257]
        for name, rows in extra['surfaces'].items():
            data['surfaces'][name]['articles'].extend(rows)
        data['pages'].update(extra['pages'])
        spazzapan = gate_batch(SOURCE, parse_spazzapan(
            data['surfaces'], data['pages'], today=NOW.date()), today=NOW.date())
        self.assertEqual(spazzapan['status'], 'ok')
        cards = [
            project('Barbacan', '12 aprile 2026 - 13 dicembre 2026',
                    interpretation='bounded_period_needs_opening_evidence'),
            project('Le Rose', '15 ottobre 2026', event={'time': '17:00'}),
            project('Memorie riflesse', 'Fino al 7 gennaio 2027',
                    interpretation='end_only', event={'start_date': None,
                        'end_date': '2027-01-07', 'schedule_kind': 'end_only'}),
        ]
        for index, card in enumerate(cards):
            card['url'] = f'https://www.turismofvg.it/eventi/integration-{index}'
            self.assertEqual(validate_candidate(card, today=NOW.date()), [])
        catalog = merge_collection(PILOT_PROJECT, None, {
            'TurismoFVG': {'status': 'partial', 'events': cards},
            SOURCE: spazzapan, 'Azalea': {'status': 'error', 'error_type': 'timeout'},
        }, NOW.isoformat())
        payload = self.http_payload(catalog)
        self.assertEqual(payload['catalog_status'], 'degraded')
        self.assertEqual(payload['source_status'][SOURCE], 'fresh')
        self.assertEqual(payload['source_failure_tags'], {
            'TurismoFVG': 'quarantined_cards', 'Azalea': 'timeout'})
        self.assertEqual(payload['total'], 5)
        visible = {event['title']: event for event in payload['events']}
        self.assertEqual(visible['Barbacan']['opening_days_status'], 'unknown')
        self.assertNotIn('occurrences', visible['Barbacan'])
        self.assertEqual(visible['Le Rose']['time'], '17:00')
        self.assertIsNone(visible['Memorie riflesse']['start_date'])
        self.assertEqual(visible['Memorie riflesse']['end_date'], '2027-01-07')
        official = {event['source_id']: event for event in payload['events'] if event['source'] == SOURCE}
        self.assertEqual(set(official), {'232202', '234126'})
        self.assertEqual(official['234126']['time'], '18:00')
        # Neither the recovered source nor an end-only exhibition bypasses
        # EV-04's existing source age gate.
        for batch in catalog['sources'].values():
            batch['updated_at'] = (NOW - timedelta(hours=49)).isoformat()
        expired = self.http_payload(catalog)
        self.assertEqual(expired['events'], [])
        self.assertEqual(expired['source_failure_tags']['TurismoFVG'], 'source_expired')
        self.assertEqual(expired['source_failure_tags'][SOURCE], 'source_expired')

    def test_verified_discrete_programme_and_time_survive_projection_and_http(self):
        days = ['2026-10-16', '2026-10-18', '2026-10-25']
        card = project('Programma con giornate esplicite',
                       '16, 18, 25 ottobre 2026',
                       interpretation='explicit_discrete_dates',
                       event={'start_date': days[0], 'end_date': days[-1],
                              'occurrences': days, 'time': '17:00', 'end_time': '19:00'})
        self.assertEqual(validate_candidate(card, today=NOW.date()), [])
        visible = self.http_card(card)
        self.assertEqual(visible['occurrences'], days)
        self.assertEqual((visible['time'], visible['end_time']), ('17:00', '19:00'))

    def test_reconciled_programme_preserves_days_in_the_public_occurrences_field(self):
        days = ['2026-10-16', '2026-10-25']
        card = project('Programma verificato', '16 ottobre 2026 - 25 ottobre 2026',
                       interpretation='programme_bounds_corroborated',
                       event={'verified_programme_occurrences': days})
        self.assertEqual(self.http_card(card)['occurrences'], days)

    def test_recurrence_badges_are_not_promoted_to_a_complete_opening_calendar(self):
        # Listing endpoints can anchor a year, but cannot prove all exceptions.
        card = project('Aperture periodiche', '15 ottobre 2026 - 31 dicembre 2026',
                       interpretation='recurrence_requires_expansion',
                       event={'occurrences': ['2026-10-15', '2026-12-31']})
        self.assertEqual(card['opening_days_status'], 'unknown')
        self.assertNotIn('occurrences', card)

    def test_single_time_is_preserved_and_missing_time_is_not_midnight(self):
        for fields in ({'time': '17:00'}, {'time': '00:00'}, {}):
            with self.subTest(fields=fields):
                card = project('Incontro', '15 ottobre 2026', event=fields)
                visible = self.http_card(card)
                self.assertEqual(visible.get('time'), fields.get('time'))

    def test_verified_daily_exhibition_is_not_marked_as_unknown(self):
        card = project('Mostra aperta ogni giorno',
                       '1 ottobre 2026 - 31 ottobre 2026',
                       interpretation='inauguration_and_daily_opening_until_end')
        self.assertEqual(card['opening_days_status'], 'daily')
        self.assertNotIn('occurrences', card)

    def test_end_only_exhibition_survives_gate_catalog_and_http(self):
        card = project('Memorie riflesse', 'Fino al 7 gennaio 2027',
                       interpretation='end_only',
                       event={'start_date': None, 'end_date': '2027-01-07',
                              'schedule_kind': 'end_only'})
        self.assertEqual(validate_candidate(card, today=NOW.date()), [])
        visible = self.http_card(card)
        self.assertIsNone(visible['start_date'])
        self.assertEqual(visible['date_label'], 'Fino al 7 gennaio 2027')
        for timestamp, expected in [('2027-01-07T22:00:00+00:00', 1),
                                    ('2027-01-07T23:00:00+00:00', 0)]:
            instant = datetime.fromisoformat(timestamp)
            self.assertEqual(len(query_catalog(catalogue(card, instant), 46.0635,
                                               13.2358, now=instant)['events']), expected)

    def test_unknown_start_is_not_a_general_bypass_for_invalid_dates(self):
        base = project('Incontro', '15 ottobre 2026')
        for changed in ({'start_date': None},
                        {'schedule_kind': 'end_only', 'start_date': 'invalid'},
                        {'schedule_kind': 'end_only', 'start_date': None, 'end_date': None},
                        {'schedule_kind': 'end_only', 'start_date': None,
                         'occurrences': ['2026-10-15']}):
            card = {**base, **changed}
            self.assertEqual(query_catalog(catalogue(card), 46.0635, 13.2358,
                                           now=NOW)['events'], [])

    def test_sagre_period_is_not_evidence_of_daily_opening(self):
        card = event_from_api({
            'id': 1, 'url': 'https://sagrefvg.it/sagre/polcenigo-pn-festa-della-birra/',
            'title': 'Polcenigo (PN) – Festa della birra',
            'start_date': '2026-09-26 08:00:00', 'end_date': '2026-10-18 23:30:00',
            'description': 'Quattro fine settimana al Parco rurale San Floriano.',
            'venue': {'city': 'Polcenigo', 'country': 'Italy'},
        })
        self.assertEqual(card['opening_days_status'], 'unknown')
        self.assertNotIn('time', card)


if __name__ == '__main__':
    unittest.main()
