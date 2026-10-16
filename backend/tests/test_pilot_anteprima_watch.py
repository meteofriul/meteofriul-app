import unittest
import hashlib
from datetime import date
from unittest.mock import patch

from app.events import pilot_anteprima_watch as watch


class AnteprimaWatchTests(unittest.TestCase):
    def test_future_dates_require_explicit_year_and_day(self):
        today = date(2026, 10, 7)
        self.assertEqual(watch.future_dates(
            '<p>Terzo e quarto fine settimana di ottobre. Le date del 2026 '
            'non sono ancora state comunicate.</p>', today), [])
        self.assertEqual(watch.future_dates(
            '<p>Dal 17 al 18 ottobre 2026. Il 4 ottobre 2026 era una prova.</p>',
            today), ['2026-10-18'])
        self.assertEqual(watch.future_dates(
            '<p>Programma: 18/10/2026; arrivederci al 2027!</p>', today),
            ['2026-10-18'])
        self.assertEqual(watch.future_yearless_dates(
            '<p>Il 18 ottobre si torna a Rosa, ma le date 2026 non sono confermate.</p>',
            today), ['2026-10-18'])

    def test_complete_api_inventory_flags_a_dated_post(self):
        rows = [
            {'id': 1, 'categories': [1706], 'link': 'https://www.anteprimasagre.it/festa/',
             'modified': '2026-10-07T12:00:00',
             'title': {'rendered': 'Festa a Rosa'},
             'content': {'rendered': '<p>Sabato 10 ottobre 2026 a Rosa.</p>'}},
            {'id': 2, 'categories': [1706], 'link': 'https://www.anteprimasagre.it/pan-zal/',
             'modified': '2026-10-07T12:00:00',
             'title': {'rendered': 'Sagra del Pan-Zal'},
             'content': {'rendered': '<p>Date 2026 non ancora comunicate.</p>'}},
        ]
        with patch.object(watch, '_fetch', return_value=(
                rows, {'X-WP-Total': '2', 'X-WP-TotalPages': '1'})):
            result = watch.collect_watch(date(2026, 10, 7))
        self.assertEqual((result['posts'], result['pages']), (2, 1))
        self.assertEqual([candidate['id'] for candidate in result['future_candidates']], [1])
        self.assertEqual(result['undated_candidates'], [])

    def test_count_mismatch_blocks_a_partial_inventory(self):
        with patch.object(watch, '_fetch', return_value=(
                [], {'X-WP-Total': '1', 'X-WP-TotalPages': '1'})):
            with self.assertRaisesRegex(ValueError, 'incomplete'):
                watch.collect_watch(date(2026, 10, 7))

    def test_html_challenge_is_diagnosed_without_logging_page_body(self):
        class Response:
            status_code = 202
            headers = {'Content-Type': 'text/html; charset=UTF-8', 'Server': 'nginx'}

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def raise_for_status(self):
                return None

            def iter_content(self, size):
                yield b'<html><title>Request verification</title><p>private token</p></html>'

        with patch.object(watch.requests, 'get', return_value=Response()):
            with self.assertRaisesRegex(ValueError, 'http=202.*title=Request verification') as error:
                watch._fetch({'page': 1})
        self.assertNotIn('private token', str(error.exception))
        self.assertIn('body_sha256=', str(error.exception))
        self.assertIn('headers=', str(error.exception))

    def test_siteground_captcha_has_distinct_error_type(self):
        class Response:
            status_code = 202
            headers = {'Content-Type': 'text/html', 'sg-captcha': '1'}

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def raise_for_status(self):
                return None

            def iter_content(self, size):
                yield b'<html>CAPTCHA</html>'

        with patch.object(watch.requests, 'get', return_value=Response()):
            with self.assertRaises(watch.AnteprimaChallengeError):
                watch._fetch({'page': 1})

    def test_pagination_waits_between_public_api_requests(self):
        rows = [{'id': ident} for ident in range(1, 102)]
        headers = {'X-WP-Total': '101', 'X-WP-TotalPages': '2'}
        observed = []

        def fetch(params):
            page = params['page']
            observed.append(('fetch', page))
            return (rows[:100] if page == 1 else rows[100:]), headers

        with patch.object(watch, '_fetch', side_effect=fetch), \
                patch.object(watch, 'sleep',
                             side_effect=lambda seconds: observed.append(('sleep', seconds))):
            result = watch.collect_watch(date(2026, 10, 7))

        self.assertEqual(result['posts'], 101)
        self.assertEqual(observed, [('fetch', 1), ('sleep', 10), ('fetch', 2)])

    def test_known_undated_post_is_reopened_when_edited(self):
        row = {'id': 3673, 'categories': [1706],
               'link': 'https://www.anteprimasagre.it/sagra-del-pan-zal-rosa-san-vito-al-tagliamento/',
               'title': {'rendered': 'Sagra del Pan-Zal'},
               'content': {'rendered': '<p>Il 18 ottobre. Le date 2026 non sono ancora comunicate.</p>'},
               'modified': '2026-09-10T11:54:06'}
        headers = {'X-WP-Total': '1', 'X-WP-TotalPages': '1'}
        fingerprint = hashlib.sha256(row['content']['rendered'].encode('utf-8')).hexdigest()
        with patch.object(watch, 'KNOWN_UNDATED', {3673: (row['modified'], fingerprint)}), \
                patch.object(watch, '_fetch', return_value=([row], headers)):
            result = watch.collect_watch(date(2026, 10, 7))
        self.assertTrue(result['undated_candidates'][0]['known_pending'])
        row['modified'] = '2026-10-08T11:54:06'
        with patch.object(watch, 'KNOWN_UNDATED', {3673: ('2026-09-10T11:54:06', fingerprint)}), \
                patch.object(watch, '_fetch', return_value=([row], headers)):
            updated = watch.collect_watch(date(2026, 10, 8))
        self.assertFalse(updated['undated_candidates'][0]['known_pending'])


if __name__ == '__main__':
    unittest.main()
