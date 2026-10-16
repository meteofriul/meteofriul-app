from copy import deepcopy
from datetime import date, datetime
from functools import partial
import json
from pathlib import Path
import unittest
from unittest.mock import Mock, patch

from app.events.pilot_dedupe import deduplicate
from app.events.pilot_catalog import PILOT_PROJECT, merge_collection, query_catalog
from app.events.pilot_source_policy import gate_batch
from app.events.pilot_spazzapan import (API_ROOT, DETAILS, SURFACES, SOURCE,
                                      collect_spazzapan, parse_spazzapan)
from app.events.pilot_cloud import publish


FIXTURE = Path(__file__).with_name('fixtures') / 'spazzapan_2026.json'
OCTOBER_15_FIXTURE = FIXTURE.with_name('spazzapan_october_15_2026.json')
TODAY = date(2026, 10, 7)


def evidence():
    return json.loads(FIXTURE.read_text(encoding='utf-8'))


def batch():
    data = evidence()
    return parse_spazzapan(data['surfaces'], data['pages'], today=TODAY)


def archived_evidence(*article_ids):
    data = evidence()
    rows = data['surfaces']['current_exhibitions']['articles']
    rows[:] = [row for row in rows if row['id'] not in article_ids]
    return data


def october_15_evidence():
    data = archived_evidence(232607)
    extra = json.loads(OCTOBER_15_FIXTURE.read_text(encoding='utf-8'))
    for name, rows in extra['surfaces'].items():
        data['surfaces'][name]['articles'].extend(rows)
    data['surfaces']['news']['articles'] = [row for row in data['surfaces']['news']['articles']
                                            if row['id'] != 232257]
    data['pages'].update(extra['pages'])
    return data


class SpazzapanTests(unittest.TestCase):
    def test_october_15_inventories_reconcile_archival_and_new_event_without_false_excerpt(self):
        data = october_15_evidence()
        data['pages']['genius']['attribute']['description'] = 'Nuovo paesaggio: 14 ottobre, Damiano Gullì.'
        result = parse_spazzapan(data['surfaces'], data['pages'], today=date(2026, 10, 15))
        self.assertEqual(gate_batch(SOURCE, result, today=date(2026, 10, 15),
                                    previous_batch=batch())['status'], 'ok')
        by_id = {item['source_id']: item for item in result['events']}
        self.assertEqual(set(by_id), {'232202', '234126'})
        self.assertEqual(by_id['234126']['start_date'], '2026-10-28')
        self.assertEqual(by_id['234126']['time'], '18:00')
        self.assertFalse(by_id['234126'].get('description_excerpt'))
        self.assertTrue(by_id['234126']['image'])
        self.assertEqual(result['verification']['event_api_count'], 4)
        self.assertEqual(result['verification']['reviewed_2026_news'], 45)
        self.assertEqual(result['verification']['retired_news_ids'], [232257])
        self.assertEqual(result['verification']['current_exhibition_count'], 3)

    def test_october_28_expiry_is_inclusive_and_does_not_block_remaining_exhibition(self):
        data = october_15_evidence()
        for today, expected in ((date(2026, 10, 28), {'232202', '234126'}),
                                (date(2026, 10, 29), {'232202'})):
            result = parse_spazzapan(data['surfaces'], data['pages'], today=today)
            with self.subTest(today=today):
                self.assertEqual({item['source_id'] for item in result['events']}, expected)
                self.assertEqual(gate_batch(SOURCE, result, today=today)['status'], 'ok')

    def test_new_event_disagreement_is_quarantined_without_hiding_verified_exhibition(self):
        for change in ('date', 'duplicate', 'prose', 'revision', 'identity'):
            data = october_15_evidence()
            if change == 'date':
                data['pages']['genius']['modules'][0]['end_event_date'] = '2026-10-29 00:00:00'
            elif change == 'duplicate':
                next(row for row in data['surfaces']['news']['articles'] if row['id'] == 234129)[
                    'intro'] = 'Mercoledì 21 ottobre, ore 18.00'
            elif change == 'prose':
                data['pages']['genius']['modules'][0]['description'] = 'Testo nuovo da verificare.'
            elif change == 'identity':
                data['pages']['genius']['attribute']['title'] = 'Altro evento'
            else:
                next(row for row in data['surfaces']['news']['articles'] if row['id'] == 234129)[
                    'modified'] = '2026-10-16T10:00:00'
            result = parse_spazzapan(data['surfaces'], data['pages'], today=date(2026, 10, 15))
            with self.subTest(change=change):
                self.assertEqual([item['source_id'] for item in result['events']], ['232202'])
                self.assertEqual([item['source_id'] for item in result['review_required']], ['234126'])
                self.assertEqual(gate_batch(SOURCE, result, today=date(2026, 10, 15))['status'], 'partial')

    def test_new_event_must_be_reconciled_across_all_inventories(self):
        for surface, article_id in (('events', 619735), ('event_category', 234126),
                                    ('news', 234129)):
            data = october_15_evidence()
            rows = data['surfaces'][surface]['articles']
            rows[:] = [row for row in rows if row['id'] != article_id]
            with self.subTest(surface=surface), self.assertRaises(ValueError):
                parse_spazzapan(data['surfaces'], data['pages'], today=date(2026, 10, 15))

    def test_gate_does_not_accept_unreconciled_event_inventory(self):
        data = october_15_evidence()
        result = parse_spazzapan(data['surfaces'], data['pages'], today=date(2026, 10, 15))
        for value in (None, [], [619735], [618890, 285613, 616198, 999999],
                      [618890, 285613, 616198, 619735, 619735]):
            changed = deepcopy(result)
            changed['verification']['event_inventory_ids'] = value
            with self.subTest(value=value):
                self.assertEqual(gate_batch(SOURCE, changed, today=date(2026, 10, 15))['status'], 'error')

    def test_retired_exhibition_notice_does_not_mask_missing_active_or_unknown_news(self):
        for removed in (232171, 84819):
            data = october_15_evidence()
            rows = data['surfaces']['news']['articles']
            rows[:] = [row for row in rows if row['id'] != removed]
            with self.subTest(removed=removed), self.assertRaisesRegex(ValueError, 'news inventory incomplete'):
                parse_spazzapan(data['surfaces'], data['pages'], today=date(2026, 10, 15))
        data = evidence()
        rows = data['surfaces']['news']['articles']
        rows[:] = [row for row in rows if row['id'] != 232257]
        with self.assertRaisesRegex(ValueError, 'news inventory incomplete'):
            parse_spazzapan(data['surfaces'], data['pages'], today=date(2026, 10, 11))
        data = october_15_evidence()
        result = parse_spazzapan(data['surfaces'], data['pages'], today=date(2026, 10, 15))
        for value in ([232171], [232257, 232257], [99999], None):
            changed = deepcopy(result)
            changed['verification']['retired_news_ids'] = value
            with self.subTest(value=value):
                self.assertEqual(gate_batch(SOURCE, changed, today=date(2026, 10, 15))['status'], 'error')

    def test_archived_exhibition_uses_own_end_date_and_preserves_other_cards(self):
        data = archived_evidence(232607)
        result = parse_spazzapan(data['surfaces'], data['pages'], today=date(2026, 10, 12))
        proof = result['verification']
        self.assertEqual(proof['current_exhibition_count'], 3)
        self.assertEqual(proof['archived_exhibitions'][0]['end_date'], '2026-10-11')
        self.assertEqual({item['source_id'] for item in result['events']}, {'232202', '233611'})
        self.assertEqual(gate_batch(SOURCE, result, today=date(2026, 10, 12),
                                    previous_batch=batch())['status'], 'ok')

    def test_archival_is_allowed_only_after_the_inclusive_last_day(self):
        data = archived_evidence(232607)
        for today in (date(2026, 10, 10), date(2026, 10, 11)):
            with self.subTest(today=today), self.assertRaisesRegex(ValueError, 'inventory changed'):
                parse_spazzapan(data['surfaces'], data['pages'], today=today)
        data = archived_evidence(232202)
        with self.assertRaisesRegex(ValueError, 'inventory changed'):
            parse_spazzapan(data['surfaces'], data['pages'], today=date(2026, 11, 29))
        result = parse_spazzapan(data['surfaces'], data['pages'], today=date(2026, 11, 30))
        self.assertEqual(gate_batch(SOURCE, result, today=date(2026, 11, 30))['status'], 'ok')

    def test_all_verified_shows_expired_is_a_valid_empty_source(self):
        data = archived_evidence(232607, 232202)
        result = parse_spazzapan(data['surfaces'], data['pages'], today=date(2026, 11, 30))
        self.assertEqual(result['events'], [])
        self.assertEqual(result['verification']['current_exhibition_count'], 2)
        self.assertEqual(len(result['verification']['archived_exhibitions']), 2)
        self.assertEqual(gate_batch(SOURCE, result, today=date(2026, 11, 30),
                                    previous_batch=batch())['status'], 'ok')

    def test_expired_show_retained_in_current_list_is_not_republished(self):
        data = evidence()
        result = parse_spazzapan(data['surfaces'], data['pages'], today=date(2026, 10, 15))
        self.assertEqual([item['source_id'] for item in result['events']], ['232202'])
        self.assertEqual(result['verification']['archived_exhibitions'], [])

    def test_archive_requires_matching_identity_publication_and_reviewed_period(self):
        for field, value in (('id', 99999), ('full_url', '/other-show'),
                             ('published', False), ('intro', 'Prorogata al 20 ottobre 2026'),
                             ('end_event_date_formatted', '2026-10-20T00:00:00')):
            data = archived_evidence(232607)
            row = next(item for item in data['surfaces']['exhibitions']['articles']
                       if item['id'] == 232607)
            row[field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                parse_spazzapan(data['surfaces'], data['pages'], today=date(2026, 10, 15))
        data = archived_evidence(232607)
        data['surfaces']['exhibitions']['articles'] = [
            row for row in data['surfaces']['exhibitions']['articles'] if row['id'] != 232607]
        with self.assertRaises(ValueError):
            parse_spazzapan(data['surfaces'], data['pages'], today=date(2026, 10, 15))

    def test_archival_does_not_allow_unknown_or_missing_active_exhibitions(self):
        for removed in (232202, 229043, 229146):
            data = archived_evidence(232607, removed)
            with self.subTest(removed=removed), self.assertRaises(ValueError):
                parse_spazzapan(data['surfaces'], data['pages'], today=date(2026, 10, 15))
        data = archived_evidence(232607)
        data['surfaces']['current_exhibitions']['articles'].append({'id': 99999})
        with self.assertRaises(ValueError):
            parse_spazzapan(data['surfaces'], data['pages'], today=date(2026, 10, 15))

    def test_gate_rejects_unproven_or_forged_archival(self):
        data = archived_evidence(232607)
        result = parse_spazzapan(data['surfaces'], data['pages'], today=date(2026, 10, 15))
        mutations = (
            ('current_exhibition_count', 2), ('current_exhibition_ids', [229043, 229146]),
            ('archived_exhibitions', []), ('archived_exhibitions', None),
            ('current_exhibition_ids', [232202, 229043, 229146, 229146]),
        )
        for key, value in mutations:
            changed = deepcopy(result)
            changed['verification'][key] = value
            with self.subTest(key=key, value=value):
                self.assertEqual(gate_batch(SOURCE, changed, today=date(2026, 10, 15))['status'], 'error')
        for key, value in (('source_id', '232202'), ('end_date', '2026-10-10'),
                           ('date_evidence', ''), ('url', 'https://example.com/')):
            changed = deepcopy(result)
            changed['verification']['archived_exhibitions'][0][key] = value
            with self.subTest(key=key):
                self.assertEqual(gate_batch(SOURCE, changed, today=date(2026, 10, 15))['status'], 'error')

    def test_collector_does_not_request_retired_detail_pages(self):
        data = archived_evidence(232607)
        responses = {API_ROOT + path: data['surfaces'][name] for name, path in SURFACES.items()}
        responses.update({API_ROOT + f'page/erpac_spazzapan/{DETAILS[name]}/it/': data['pages'][name]
                          for name in ('fvg7002_exhibition', 'fvg7002_news', 'fvg_settanta', 'together')})
        def get(url, **kwargs):
            response = Mock(status_code=200)
            response.__enter__ = Mock(return_value=response)
            response.__exit__ = Mock(return_value=False)
            response.iter_content.return_value = [json.dumps(responses[url]).encode()]
            return response
        result = collect_spazzapan(get=get, today=date(2026, 10, 15))
        self.assertEqual(gate_batch(SOURCE, result, today=date(2026, 10, 15))['status'], 'ok')

    def test_job_completes_and_api_retains_active_show_after_archival(self):
        data = archived_evidence(232607)
        previous = merge_collection(PILOT_PROJECT, None, {SOURCE: batch()}, '2026-10-07T08:00:00+00:00')
        blob = Mock(generation=7, size=100)
        blob.download_as_bytes.return_value = json.dumps(previous).encode()
        client = Mock(project=PILOT_PROJECT)
        client.bucket.return_value.blob.return_value = blob
        adapter = partial(parse_spazzapan, data['surfaces'], data['pages'], today=date(2026, 10, 15))
        now = datetime.fromisoformat('2026-10-15T08:00:00+00:00')
        with patch('app.events.pilot_cloud.datetime') as clock:
            clock.now.return_value = now
            report = publish(client, project=PILOT_PROJECT, adapters={SOURCE: adapter})
        self.assertEqual(report[SOURCE]['status'], 'fresh')
        blob.upload_from_string.assert_called_once()
        self.assertEqual(blob.upload_from_string.call_args.kwargs['if_generation_match'], 7)
        saved = json.loads(blob.upload_from_string.call_args.args[0])
        event = saved['sources'][SOURCE]['events'][0]
        self.assertEqual([item['source_id'] for item in query_catalog(
            saved, event['lat'], event['lon'], now=now)['events']], ['232202'])

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
        data['surfaces']['news']['articles'][2]['modified'] = '2026-10-07T15:00:00'
        with self.assertRaisesRegex(ValueError, 'changed Spazzapan news'):
            parse_spazzapan(data['surfaces'], data['pages'], today=TODAY)
        data = evidence()
        data['surfaces']['news']['articles'][1]['modified'] = '2026-10-07T15:00:00'
        quarantined = parse_spazzapan(data['surfaces'], data['pages'], today=TODAY)
        self.assertEqual([item['source_id'] for item in quarantined['review_required']],
                         ['233611'])
        self.assertEqual(gate_batch('Galleria Spazzapan', quarantined,
                                    today=TODAY)['status'], 'partial')
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
        quarantined = parse_spazzapan(data['surfaces'], data['pages'],
                                      today=date(2026, 10, 11))
        self.assertEqual([item['source_id'] for item in quarantined['review_required']],
                         ['233611'])
        self.assertEqual(gate_batch('Galleria Spazzapan', quarantined,
                                    today=date(2026, 10, 11))['status'], 'partial')

    def test_detail_dates_and_museum_studio_are_required(self):
        data = evidence()
        module = data['pages']['fvg7002_news']['modules'][2]
        module['end_event_date'] = '2027-01-15 00:00:00'
        quarantined = parse_spazzapan(data['surfaces'], data['pages'], today=TODAY)
        self.assertEqual([item['source_id'] for item in quarantined['review_required']],
                         ['232202'])
        self.assertEqual(gate_batch('Galleria Spazzapan', quarantined,
                                    today=TODAY, previous_batch=batch())['status'],
                         'partial')
        data = evidence()
        module = data['pages']['mario']['modules'][0]
        module['description'] = 'Una visita alla Galleria il 10 ottobre 2026 a Gradisca.'
        quarantined = parse_spazzapan(data['surfaces'], data['pages'], today=TODAY)
        self.assertEqual([item['source_id'] for item in quarantined['review_required']],
                         ['84819'])
        self.assertEqual(gate_batch('Galleria Spazzapan', quarantined,
                                    today=TODAY)['status'], 'partial')
        data = evidence()
        data['surfaces']['current_exhibitions']['articles'][0][
            'end_event_date_formatted'] = '2027-02-01T00:00:00'
        quarantined = parse_spazzapan(data['surfaces'], data['pages'], today=TODAY)
        self.assertEqual([item['source_id'] for item in quarantined['review_required']],
                         ['232607'])
        self.assertEqual(gate_batch('Galleria Spazzapan', quarantined,
                                    today=TODAY)['status'], 'partial')

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

    def test_quarantine_needs_exact_identity_and_does_not_hide_empty_source(self):
        data = evidence()
        data['pages']['paesaggio']['modules'][0]['description'] = 'Dettagli da verificare.'
        one_review = parse_spazzapan(data['surfaces'], data['pages'],
                                     today=date(2026, 10, 13))
        self.assertEqual(gate_batch('Galleria Spazzapan', one_review,
                                    today=date(2026, 10, 13))['status'], 'partial')
        tampered = deepcopy(one_review)
        tampered['review_required'][0]['source_id'] = '232607'
        self.assertEqual(gate_batch('Galleria Spazzapan', tampered,
                                    today=date(2026, 10, 13))['status'], 'error')
        data['pages']['fvg7002_news']['modules'][2]['end_event_date'] = (
            '2027-01-15 00:00:00')
        no_valid = parse_spazzapan(data['surfaces'], data['pages'],
                                   today=date(2026, 10, 13))
        self.assertEqual(len(no_valid['review_required']), 2)
        self.assertEqual(gate_batch('Galleria Spazzapan', no_valid,
                                    today=date(2026, 10, 13))['status'], 'error')

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
