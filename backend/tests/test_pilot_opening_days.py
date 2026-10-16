"""EV-01: real source projection, deduplication and HTTP, with no network.

The --http-fixtures entry point feeds the same runtime output to Vitest.
"""
from copy import deepcopy
from datetime import datetime
import json
import sys
import unittest
from unittest.mock import patch

from app.events.engine import merge_duplicate_event_data
from app.events.pilot_catalog import PILOT_PROJECT, merge_collection
from app.events.pilot_http import application
from app.events.pilot_source_policy import gate_batch
from app.events.pilot_spazzapan import SOURCE, parse_spazzapan
from test_pilot_event_schedule_contract import project
from test_pilot_spazzapan import october_15_evidence

NOW = datetime.fromisoformat('2026-10-19T12:00:00+00:00')


def http_fixtures():
    with patch('requests.sessions.Session.request', side_effect=AssertionError('Network forbidden')):
        evidence = october_15_evidence()
        batch = gate_batch(SOURCE, parse_spazzapan(evidence['surfaces'], evidence['pages'],
            today=NOW.date()), today=NOW.date())
        assert batch['status'] == 'ok'
        official = next(card for card in batch['events'] if card['source_id'] == '232202')
        regional = project('Mostra "FVG70.02. Nuovi modelli di ricerca"',
            '23 luglio 2026 - 29 novembre 2026', event={"event_city": "Gradisca d'Isonzo"})
        regional['url'] = 'https://www.turismofvg.it/eventi/mostra-fvg70-02-nuovi-modelli-di-ricerca'
        cases = {}
        for case, card, secondary in (
                ('unknown', official, regional),
                ('legacy_official', {k: v for k, v in official.items() if k != 'opening_days_status'}, regional),
                ('daily', {**official, 'opening_days_status': 'daily'}, regional),
                ('explicit_days', {**official, 'occurrences': ['2026-10-18', '2026-10-21']},
                    {**regional, 'occurrences': ['2026-10-18', '2026-10-21']})):
            for reverse in (False, True):
                batches = [(SOURCE, {'status': 'ok', 'events': [card]}),
                           ('TurismoFVG', {'status': 'ok', 'events': [secondary]})]
                if reverse:
                    batches.reverse()
                catalog = merge_collection(PILOT_PROJECT, None, dict(batches), NOW.isoformat())
                status = []
                with patch('app.events.pilot_http.load_catalog', return_value=catalog), \
                        patch('app.events.pilot_http.datetime') as clock:
                    clock.now.return_value = NOW
                    body = application({'REQUEST_METHOD': 'GET', 'PATH_INFO': '/api/local/events',
                        'QUERY_STRING': f"lat={official['lat']}&lon={official['lon']}&radius=20"},
                        lambda code, headers: status.append(code))
                assert status == ['200 OK'], status
                cases[f'{case}_{"regional_first" if reverse else "official_first"}'] = json.loads(b''.join(body))
        return cases


class OpeningDaysTests(unittest.TestCase):
    def test_source_marks_exhibition_uncertain_without_affecting_single_events(self):
        data = october_15_evidence()
        batch = parse_spazzapan(data['surfaces'], data['pages'], today=NOW.date())
        cards = {card['source_id']: card for card in batch['events']}
        self.assertEqual(cards['232202']['opening_days_status'], 'unknown')
        self.assertNotIn('opening_days_status', cards['234126'])
        self.assertEqual(cards['234126']['time'], '18:00')

    def test_uncertainty_survives_generic_merge_without_mutating_inputs(self):
        for primary, secondary in (({}, {'opening_days_status': 'unknown'}),
                                    ({'opening_days_status': 'unknown'}, {})):
            before = deepcopy([primary, secondary])
            self.assertEqual(merge_duplicate_event_data(primary, secondary)['opening_days_status'], 'unknown')
            self.assertEqual([primary, secondary], before)

    def test_explicit_primary_evidence_is_preserved(self):
        unknown = {'opening_days_status': 'unknown'}
        self.assertEqual(merge_duplicate_event_data({'opening_days_status': 'daily'}, unknown)
                         ['opening_days_status'], 'daily')
        days = ['2026-10-18', '2026-10-21']
        self.assertEqual(merge_duplicate_event_data({'occurrences': days}, unknown)['occurrences'], days)

    def test_real_catalog_and_http_preserve_calendar_in_both_source_orders(self):
        for name, payload in http_fixtures().items():
            with self.subTest(case=name):
                self.assertEqual(payload['total'], 1)
                self.assertEqual(payload['catalog_status'], 'complete')
                card = payload['events'][0]
                self.assertEqual(card['source'], SOURCE)
                self.assertEqual(len(card['source_urls']), 2)
                self.assertEqual(card['start_date'], '2026-07-23')
                self.assertEqual(card['end_date'], '2026-11-29')
                if name.startswith(('unknown_', 'legacy_')):
                    self.assertEqual(card['opening_days_status'], 'unknown')
                    self.assertFalse(card.get('occurrences'))
                elif name.startswith('daily_'):
                    self.assertEqual(card['opening_days_status'], 'daily')
                else:
                    self.assertEqual(card['occurrences'], ['2026-10-18', '2026-10-21'])


if __name__ == '__main__':
    if sys.argv[1:] == ['--http-fixtures']:
        print(json.dumps(http_fixtures(), ensure_ascii=False))
    else:
        unittest.main()
