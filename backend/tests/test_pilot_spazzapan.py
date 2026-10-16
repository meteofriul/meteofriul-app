from copy import deepcopy
from datetime import date, datetime
import json
from pathlib import Path
import unittest

from app.events.pilot_dedupe import deduplicate
from app.events.pilot_catalog import PILOT_PROJECT, merge_collection, query_catalog
from app.events.pilot_source_policy import gate_batch
from app.events.pilot_spazzapan import parse_spazzapan


FIXTURE = Path(__file__).with_name('fixtures') / 'spazzapan_2026.json'
TODAY = date(2026, 10, 7)


def evidence():
    return json.loads(FIXTURE.read_text(encoding='utf-8'))


def batch():
    data = evidence()
    return parse_spazzapan(data['surfaces'], data['pages'], today=TODAY)


class SpazzapanTests(unittest.TestCase):
    def test_four_distinct_cards_with_detail_dates_and_previews(self):
        result = batch()
        self.assertEqual(result['verification']['event_api_count'], 3)
        self.assertEqual(result['verification']['news_count'], 78)
        self.assertEqual(result['verification']['reviewed_2026_news'], 44)
        self.assertEqual(len(result['events']), 4)
        self.assertEqual(gate_batch('Galleria Spazzapan', result,
                                    today=TODAY)['status'], 'ok')
        by_id = {event['source_id']: event for event in result['events']}
        self.assertEqual((by_id['232202']['start_date'],
                          by_id['232202']['end_date']),
                         ('2026-07-23', '2026-11-29'))
        self.assertEqual((by_id['232607']['start_date'],
                          by_id['232607']['end_date']),
                         ('2026-09-11', '2026-10-11'))
        self.assertEqual(by_id['84819']['venue'], 'Studio di Mario Palli')
        self.assertTrue(by_id['84819']['description_excerpt'])
        self.assertIn('Damiano Gullì', by_id['233611']['title'])
        self.assertEqual(by_id['233611']['time'], '18:00')
        self.assertTrue(by_id['233611']['description_excerpt'])
        self.assertTrue(all(event.get('image') for event in result['events']))

    def test_inventory_or_new_news_blocks_source(self):
        data = evidence()
        data['surfaces']['events']['articles'].pop()
        with self.assertRaisesRegex(ValueError, 'inventory changed'):
            parse_spazzapan(data['surfaces'], data['pages'], today=TODAY)
        data = evidence()
        data['surfaces']['news']['articles'][0]['modified'] = '2026-10-07T15:00:00'
        with self.assertRaisesRegex(ValueError, 'changed Spazzapan news'):
            parse_spazzapan(data['surfaces'], data['pages'], today=TODAY)
        data = evidence()
        data['surfaces']['news']['articles'].append({
            'id': 999999, 'published_date': '2026-10-07T12:00:00',
            'modified': '2026-10-07T12:00:00', 'published': True})
        with self.assertRaisesRegex(ValueError, 'new or changed Spazzapan news'):
            parse_spazzapan(data['surfaces'], data['pages'], today=TODAY)

    def test_duplicate_news_is_reconciled_with_one_detailed_event(self):
        data = evidence()
        result = parse_spazzapan(data['surfaces'], data['pages'],
                                 today=date(2026, 10, 11))
        self.assertEqual([event['source_id'] for event in result['events']
                          if event['start_date'] == '2026-10-14'], ['233611'])
        duplicate = next(row for row in data['surfaces']['news']['articles']
                         if row['id'] == 233851)
        duplicate['intro'] = 'Mercoledì 21 ottobre, ore 18.00'
        with self.assertRaisesRegex(ValueError, 'duplicate news does not match'):
            parse_spazzapan(data['surfaces'], data['pages'],
                            today=date(2026, 10, 11))

    def test_detail_dates_and_museum_studio_are_required(self):
        data = evidence()
        module = data['pages']['fvg7002_news']['modules'][2]
        module['end_event_date'] = '2027-01-15 00:00:00'
        with self.assertRaisesRegex(ValueError, 'FVG70.02 detail'):
            parse_spazzapan(data['surfaces'], data['pages'], today=TODAY)
        data = evidence()
        module = data['pages']['mario']['modules'][0]
        module['description'] = 'Una visita alla Galleria il 10 ottobre 2026 a Gradisca.'
        with self.assertRaisesRegex(ValueError, 'Mario date or studio'):
            parse_spazzapan(data['surfaces'], data['pages'], today=TODAY)
        data = evidence()
        data['surfaces']['current_exhibitions']['articles'][0][
            'end_event_date_formatted'] = '2027-02-01T00:00:00'
        with self.assertRaisesRegex(ValueError, 'structured dates changed'):
            parse_spazzapan(data['surfaces'], data['pages'], today=TODAY)

    def test_missing_active_card_or_fake_preview_fails_gate(self):
        result = batch()
        changed = deepcopy(result)
        changed['events'].pop()
        changed['verification']['projected_count'] = len(changed['events'])
        self.assertEqual(gate_batch('Galleria Spazzapan', changed,
                                    today=TODAY)['status'], 'error')
        changed = deepcopy(result)
        next(event for event in changed['events'] if event['source_id'] == '233611')[
            'description_excerpt'] = 'A breve ulteriori dettagli.'
        self.assertEqual(gate_batch('Galleria Spazzapan', changed,
                                    today=TODAY)['status'], 'error')

    def test_regional_fvg7002_duplicate_keeps_official_card(self):
        direct = next(event for event in batch()['events']
                      if event['source_id'] == '232202')
        regional = {**direct, 'source': 'TurismoFVG',
                    'url': 'https://www.turismofvg.it/eventi/mostra-fvg70-02-nuovi-modelli-di-ricerca',
                    'title': 'Mostra "FVG70.02. Nuovi modelli di ricerca"',
                    'venue': 'Galleria Regionale di Arte contemporanea Luigi Spazzapan',
                    'place': "Galleria Spazzapan, Gradisca d'Isonzo"}
        deduped = deduplicate([regional, direct])
        self.assertEqual(len(deduped), 1)
        self.assertEqual(deduped[0]['source'], 'Galleria Spazzapan')
        self.assertEqual(set(deduped[0]['source_urls']),
                         {regional['url'], direct['url']})
        changed = {**regional, 'event_city': 'Udine'}
        self.assertEqual(len(deduplicate([changed, direct])), 2)

    def test_failed_refresh_hides_spazzapan_cards(self):
        event = next(item for item in batch()['events']
                     if item['source_id'] == '232202')
        now = '2026-10-07T08:00:00+00:00'
        old = merge_collection(PILOT_PROJECT, None, {
            'Galleria Spazzapan': {'status': 'ok', 'events': [event]}}, now)
        failed = merge_collection(PILOT_PROJECT, old, {
            'Galleria Spazzapan': {'status': 'error', 'reason': 'news changed'}}, now)
        self.assertEqual(failed['sources']['Galleria Spazzapan']['status'], 'stale')
        self.assertEqual(query_catalog(
            failed, event['lat'], event['lon'],
            now=datetime.fromisoformat(now))['events'], [])


if __name__ == '__main__':
    unittest.main()
