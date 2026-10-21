"""Regression of the three source failures seen in the ordinary 21 October job."""
from copy import deepcopy
from datetime import date
import json
from pathlib import Path
import unittest
from unittest.mock import Mock, patch

import requests
from app.events import pilot_barcolana as barcolana, pilot_cinema_muto as cinema
from app.events.pilot_source_policy import gate_batch
from app.events.pilot_spazzapan import SOURCE, parse_spazzapan, collect_spazzapan, API_ROOT, DETAILS, SURFACES
from test_pilot_spazzapan import october_15_evidence
from test_pilot_cinema_muto import FakeResponse

FIXTURE = Path(__file__).with_name('fixtures') / 'spazzapan_october_21_2026.json'
TODAY = date(2026, 10, 21)


def evidence():
    data = october_15_evidence()
    extra = json.loads(FIXTURE.read_text(encoding='utf-8'))
    data['surfaces']['news']['articles'].append(extra['article'])
    data['pages']['brene'] = extra['page']
    return data


def parsed(data=None, today=TODAY):
    data = data or evidence()
    return parse_spazzapan(data['surfaces'], data['pages'], today=today)


class SpazzapanOctober21Tests(unittest.TestCase):
    def test_news_only_appointment_is_verified_without_changing_event_inventory(self):
        result = parsed()
        self.assertEqual(gate_batch(SOURCE, result, today=TODAY)['status'], 'ok')
        by_id = {event['source_id']: event for event in result['events']}
        self.assertEqual(set(by_id), {'232202', '234126', '234240'})
        event = by_id['234240']
        self.assertEqual((event['start_date'], event['end_date'], event['time']),
                         ('2026-10-21', '2026-10-21', '18:00'))
        self.assertEqual(event['event_city'], "Gradisca d'Isonzo")
        self.assertTrue(event['description_excerpt'])
        self.assertEqual(result['verification']['event_api_count'], 4)
        self.assertEqual(result['verification']['news_event_ids'], [234240])
        self.assertEqual(result['verification']['reviewed_2026_news'], 46)

    def test_expiry_does_not_republish_yesterday_or_block_the_remaining_cards(self):
        result = parsed(today=date(2026, 10, 22))
        self.assertEqual({e['source_id'] for e in result['events']}, {'232202', '234126'})
        self.assertEqual(gate_batch(SOURCE, result, today=date(2026, 10, 22),
                                    previous_batch=parsed())['status'], 'ok')

    def test_changed_detail_or_announcement_is_quarantined_not_silently_accepted(self):
        for change in ('revision', 'date', 'venue', 'identity', 'publication', 'structured_date'):
            data = evidence()
            if change == 'revision':
                data['surfaces']['news']['articles'][-1]['modified'] = '2026-10-21T09:00:00'
            elif change == 'date':
                data['pages']['brene']['modules'][0]['description'] = 'Appuntamento rinviato.'
            elif change == 'venue':
                data['pages']['brene']['modules'][0]['intro'] = '21 ottobre, Udine'
            elif change == 'identity':
                data['pages']['brene']['attribute']['full_url'] = '/another-event'
            elif change == 'publication':
                data['pages']['brene']['attribute']['published'] = False
            else:
                data['pages']['brene']['modules'][0]['start_event_date'] = '2026-10-22'
            with self.subTest(change=change):
                result = parsed(data)
                self.assertEqual({e['source_id'] for e in result['events']}, {'232202', '234126'})
                self.assertEqual([e['source_id'] for e in result['review_required']], ['234240'])
                self.assertEqual(gate_batch(SOURCE, result, today=TODAY)['status'], 'partial')

    def test_forged_inventory_time_and_disappearing_active_card_fail_the_gate(self):
        good = parsed()
        for ids in ([True], [234240, 234240], [99999], None):
            changed = deepcopy(good); changed['verification']['news_event_ids'] = ids
            self.assertEqual(gate_batch(SOURCE, changed, today=TODAY)['status'], 'error')
        changed = deepcopy(good)
        next(e for e in changed['events'] if e['source_id'] == '234240')['time'] = '19:00'
        self.assertEqual(gate_batch(SOURCE, changed, today=TODAY)['status'], 'error')
        old = october_15_evidence()
        self.assertEqual(gate_batch(SOURCE, parsed(old), today=TODAY,
                                    previous_batch=good)['status'], 'error')

    def test_unknown_news_still_requires_review(self):
        data = evidence()
        data['surfaces']['news']['articles'].append({
            'id': 999999, 'published_date': '2026-10-21T08:00:00',
            'modified': '2026-10-21T08:00:00', 'published': True})
        with self.assertRaisesRegex(ValueError, 'news requires review'):
            parsed(data)

    def test_collector_fetches_new_detail_only_while_active_and_announced(self):
        data = evidence()
        replies = {API_ROOT+path: data['surfaces'][name] for name,path in SURFACES.items()}
        replies.update({API_ROOT+f'page/erpac_spazzapan/{DETAILS[name]}/it/': page
                        for name,page in data['pages'].items()})
        def get(url, **kwargs):
            return FakeResponse(json.dumps(replies[url]))
        for day in (TODAY, date(2026,10,22)):
            get_mock = Mock(side_effect=get)
            result = collect_spazzapan(get=get_mock, today=day)
            self.assertEqual(gate_batch(SOURCE,result,today=day)['status'], 'ok')
            read_new = any('/174928/' in call.args[0] for call in get_mock.call_args_list)
            self.assertEqual(read_new, day == TODAY)


class EventReadRecoveryTests(unittest.TestCase):
    def setUp(self):
        pause = patch('app.events.http_client.time.sleep')
        self.pause = pause.start(); self.addCleanup(pause.stop)

    def test_barcolana_retries_one_timeout_and_closes_the_response(self):
        response = Mock(status_code=200, content=b'complete calendar')
        get = Mock(side_effect=[requests.ReadTimeout('first attempt'), response])
        self.assertEqual(barcolana._read(get,'https://example.test/calendar',100), 'complete calendar')
        self.assertEqual(get.call_count,2); response.close.assert_called_once()
        self.pause.assert_called_once_with(0.5)

    def test_stream_read_failure_discards_partial_bytes(self):
        response = FakeResponse('unused')
        def broken(_):
            yield b'partial data that must not survive'
            raise requests.ConnectionError('read timeout while streaming')
        response.iter_content = broken
        get = Mock(side_effect=[response, FakeResponse('complete calendar')])
        self.assertEqual(cinema._read(get,'https://example.test/calendar',limit=100), 'complete calendar')
        self.assertEqual(get.call_count,2)

    def test_two_timeouts_remain_an_error_for_both_sources(self):
        for read in (lambda get: barcolana._read(get,'https://example.test',100),
                     lambda get: cinema._read(get,'https://example.test',limit=100)):
            get = Mock(side_effect=[requests.ReadTimeout('first'),requests.ReadTimeout('second')])
            with self.assertRaisesRegex(requests.ReadTimeout,'second'):
                read(get)
            self.assertEqual(get.call_count,2)

    def test_body_size_failure_is_not_retried_or_reported_successful(self):
        for read, response in ((lambda get: barcolana._read(get,'https://example.test',2),
                                Mock(status_code=200,content=b'large')),
                               (lambda get: cinema._read(get,'https://example.test',limit=2),
                                FakeResponse('large'))):
            get = Mock(return_value=response)
            with self.assertRaisesRegex(ValueError,'too large'):
                read(get)
            get.assert_called_once()


if __name__ == '__main__':
    unittest.main()
