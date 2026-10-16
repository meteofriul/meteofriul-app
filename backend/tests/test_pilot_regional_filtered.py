import unittest
from datetime import date
from unittest.mock import Mock, patch
from urllib.parse import parse_qs, urlsplit
import requests

from app.events.pilot_regional_filtered import (
    collect_filtered, fetch_page, fetch_year, fetch_year_partitioned,
    fetch_year_resilient,
)


class FilteredRegionalTests(unittest.TestCase):
    @staticmethod
    def card(day):
        return (f'<a class="c-eventsResults__item" href="/eventi/prova-{day}">'
                f'<div class="info_date"><div class="col1"><strong>{day}</strong>'
                '<p>OTT</p></div></div><h1 class="title">Evento prova</h1></a>')

    def page(self, url, days, total, *, more):
        query = parse_qs(urlsplit(url).query)
        page = int(query.get('page', [0])[0])
        next_link = (f'<a class="c-load_more js-loadmorebox__button" '
                     f'href="/eventi?hidehighlights=true&amp;start=2026-10-04'
                     f'&amp;end=2026-12-31&amp;page={page + 1}">Carica altri eventi</a>'
                     if more else '')
        html = (f'<div class="c-events_result__total"><span>{total} eventi trovati</span></div>'
                + ''.join(self.card(day) for day in days) + next_link)
        return Mock(text=html, url=url)

    def test_annual_pages_preserve_year_and_reconcile_total(self):
        def get(url, **_):
            page = int(parse_qs(urlsplit(url).query).get('page', [0])[0])
            rows = {0: [4, 5], 1: [6, 7, 8, 9], 2: [10, 11, 12, 13]}
            return self.page(url, rows[page], 10, more=page < 2)
        result = fetch_year(date(2026, 10, 4), date(2026, 12, 31), get=get)
        self.assertEqual(result['cards_seen'], 10)
        self.assertEqual(result['pages'], 3)
        self.assertEqual(result['cards'][0]['badge_date'], '2026-10-04')
        self.assertEqual(result['cards'][-1]['badge_date'], '2026-10-13')

    def test_missing_card_fails_even_with_reported_total(self):
        def get(url, **_):
            page = int(parse_qs(urlsplit(url).query).get('page', [0])[0])
            rows = {0: [4, 5], 1: [6, 7, 8, 9], 2: [10, 11, 12]}
            return self.page(url, rows[page], 10, more=page < 2)
        with self.assertRaisesRegex(ValueError, 'page count differs'):
            fetch_year(date(2026, 10, 4), date(2026, 12, 31), get=get)

    def test_changed_first_page_fails_after_all_pages_arrive(self):
        first_reads = 0

        def get(url, **_):
            nonlocal first_reads
            page = int(parse_qs(urlsplit(url).query).get('page', [0])[0])
            if page == 0:
                first_reads += 1
                return self.page(url, [4 if first_reads == 1 else 5], 2,
                                 more=True)
            return self.page(url, [6], 2, more=False)

        with self.assertRaisesRegex(ValueError, 'first page changed'):
            fetch_year(date(2026, 10, 4), date(2026, 12, 31), get=get)

    def test_explicit_empty_year_is_valid(self):
        def get(url, **_):
            return Mock(text='<div class="c-events_result"><div>Nessun evento trovato</div></div>',
                        url=url)
        result = fetch_year(date(2029, 1, 1), date(2029, 12, 31),
                            get=get)
        self.assertEqual(result['declared_results'], 0)
        self.assertEqual(result['cards'], [])

    @patch('app.events.pilot_regional_filtered.time.sleep')
    def test_calendar_page_recovers_from_two_transport_resets(self, pause):
        url = 'https://www.turismofvg.it/eventi?hidehighlights=true&start=2026-10-01&end=2026-10-01'
        empty = Mock(text='<div class="c-events_result"><div>Nessun evento trovato</div></div>',
                     url=url, status_code=200)
        empty.raise_for_status.return_value = None
        get = Mock(side_effect=[requests.ConnectionError('reset'),
                                requests.ConnectionError('reset'), empty])
        result = fetch_page(url, get=get)
        self.assertEqual(result['total'], 0)
        self.assertEqual(get.call_count, 3)
        self.assertEqual([call.args[0] for call in pause.call_args_list], [0.5, 1])

    @patch('app.events.pilot_regional_filtered.fetch_year')
    @patch('app.events.pilot_regional_filtered.fetch_page')
    def test_partitioned_windows_deduplicate_without_adding_totals(self, page, year):
        start, end = date(2026, 10, 1), date(2026, 10, 2)

        def card(letter, *, offset=0):
            return {'url': f'https://www.turismofvg.it/eventi/prova-{letter}',
                    'title': f'Evento {letter}', 'place': 'Udine',
                    'badge_date': None, 'start': offset, 'end': offset + 10,
                    'search_window': ['2026-10-01', '2026-10-02']}

        def page_result(url, **_):
            query = parse_qs(urlsplit(url).query)
            window = (query['start'][0], query['end'][0])
            if window == ('2026-10-01', '2026-10-02'):
                return {'total': 6, 'cards': [card('A'), card('B')]}
            self.assertIn(window, {('2026-10-01', '2026-10-01'),
                                   ('2026-10-02', '2026-10-02')})
            return {'total': 4, 'cards': []}

        def year_result(first, last, **_):
            letters = 'ABCD' if first == start else 'CDEF'
            return {'declared_results': 4, 'pages': 2,
                    'cards': [card(letter, offset=100 if first != start else 0)
                              for letter in letters]}

        page.side_effect = page_result
        year.side_effect = year_result
        result = fetch_year_partitioned(start, end, result_limit=4,
                                        max_workers=4)
        self.assertEqual(result['declared_results'], 6)
        self.assertEqual(result['cards_seen'], 6)
        self.assertEqual(len(result['cards']), 6)
        self.assertEqual(year.call_count, 2)

        root_totals = iter([6, 7])

        def changing_page(url, **_):
            result = page_result(url)
            query = parse_qs(urlsplit(url).query)
            if query['start'][0] != query['end'][0]:
                result['total'] = next(root_totals)
            return result

        page.side_effect = changing_page
        with self.assertRaisesRegex(ValueError, 'annual result changed'):
            fetch_year_partitioned(start, end, result_limit=4, max_workers=4)

        page.side_effect = page_result

        def missing_card(first, last, **_):
            result = year_result(first, last)
            if first != start:
                result['cards'][-1] = card('E', offset=200)
            return result

        year.side_effect = missing_card
        with self.assertRaisesRegex(ValueError, 'partition union count differs'):
            fetch_year_partitioned(start, end, result_limit=4, max_workers=4)

        def changed_window(first, last, **_):
            result = year_result(first, last)
            if first != start:
                result['declared_results'] = 5
            return result

        year.side_effect = changed_window
        with self.assertRaisesRegex(ValueError, 'partition window changed'):
            fetch_year_partitioned(start, end, result_limit=4, max_workers=4)

    @patch('app.events.pilot_regional_filtered.fetch_year_partitioned')
    @patch('app.events.pilot_regional_filtered.fetch_year')
    def test_resilient_scan_partitions_only_after_changed_total(self, year, partitioned):
        start, end = date(2026, 1, 1), date(2026, 12, 31)
        year.side_effect = ValueError(
            'TurismoFVG page count differs from declared results: '
            'page=66, total=2467/2464, cards=8/8')
        partitioned.return_value = {'declared_results': 2467}
        self.assertEqual(fetch_year_resilient(start, end, max_workers=8),
                         partitioned.return_value)
        partitioned.assert_called_once_with(
            start, end, get=requests.get, max_workers=8, result_limit=128)

        partitioned.reset_mock()
        year.side_effect = ValueError(
            'TurismoFVG page count differs from declared results: '
            'page=66, total=2464/2464, cards=7/8')
        with self.assertRaisesRegex(ValueError, 'cards=7/8'):
            fetch_year_resilient(start, end, max_workers=8)
        partitioned.assert_not_called()

    @patch('app.events.pilot_regional_filtered.fetch_page')
    @patch('app.events.pilot_regional_filtered.fetch_year')
    def test_scan_stops_after_two_empty_years_and_checks_overflow(self, fetch_year_mock, fetch_page_mock):
        fetch_year_mock.side_effect = [
            {'start': '2026-10-04', 'end': '2026-12-31', 'declared_results': 1,
             'cards_seen': 1, 'pages': 1, 'cards': [{'url': 'https://www.turismofvg.it/eventi/a', 'badge_date': '2026-10-04'}]},
            {'start': '2027-01-01', 'end': '2027-12-31', 'declared_results': 0,
             'cards_seen': 0, 'pages': 1, 'cards': []},
            {'start': '2028-01-01', 'end': '2028-12-31', 'declared_results': 0,
             'cards_seen': 0, 'pages': 1, 'cards': []},
        ]
        fetch_page_mock.return_value = {'total': 0, 'cards': [], 'next_url': None}
        result = collect_filtered(today=date(2026, 10, 4))
        self.assertEqual(fetch_year_mock.call_count, 3)
        self.assertTrue(result['horizon_complete'])
        self.assertEqual(result['badge_dates'], 1)
        self.assertEqual(result['overflow'], {'start': '2029-01-01',
                                             'end': '2099-12-31',
                                             'declared_results': 0})
        fetch_page_mock.return_value = {'total': 1, 'cards': [{}], 'next_url': None}
        fetch_year_mock.side_effect = [
            {'start': '2026-10-04', 'end': '2026-12-31', 'declared_results': 1,
             'cards_seen': 1, 'pages': 1, 'cards': [{'url': 'https://www.turismofvg.it/eventi/a'}]},
            {'start': '2027-01-01', 'end': '2027-12-31', 'declared_results': 0,
             'cards_seen': 0, 'pages': 1, 'cards': []},
            {'start': '2028-01-01', 'end': '2028-12-31', 'declared_results': 0,
             'cards_seen': 0, 'pages': 1, 'cards': []},
        ]
        self.assertFalse(collect_filtered(today=date(2026, 10, 4))['horizon_complete'])


if __name__ == '__main__':
    unittest.main()
