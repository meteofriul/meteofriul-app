import unittest
from datetime import date, datetime, timezone

from app.events.pilot_regional_historical import (recheck_historical_result,
                                                   resolve_historical_years)


class HistoricalCalendarEvidenceTests(unittest.TestCase):
    first = 'https://www.turismofvg.it/eventi/il-pacchetto-rosso'
    second = 'https://www.turismofvg.it/eventi/giochi-per-bambini-aspettando-natale'

    def snapshot(self):
        return {'as_of_date': '2026-10-06',
                'entries': {url: {'kind': 'sitemap_only',
                                  'sitemap_lastmod': '2022-12-23'}
                            for url in (self.first, self.second)},
                'results': {url: {'status': 'ambiguous', 'reason': 'year_missing'}
                            for url in (self.first, self.second)}}

    @staticmethod
    def html(title, *, city='Moggio Udinese', description='Letture per bambini.'):
        return (f'<h1>{title}</h1><div class="body_col1"><h2>Descrizione</h2>'
                f'<p>{description}</p></div><div class="body_col2">'
                '<div style="background-image: url(icn__calendar.svg)">'
                'Natale a Moggio</div>'
                f'<div style="background-image: url(icn__pin.svg)">{city}</div>'
                '</div><div class="c-detail__actions"></div>')

    def cards(self, start, end):
        self.assertEqual((start, end), (date(2022, 12, 23), date(2022, 12, 31)))
        cards = [{'url': self.first, 'title': 'Il Pacchetto Rosso',
                  'place': 'Moggio Udinese', 'badge_date': '2022-12-24'},
                 {'url': self.second,
                  'title': 'Giochi per bambini aspettando Natale',
                  'place': 'Moggio Udinese', 'badge_date': '2022-12-24'}]
        return {'start': start.isoformat(), 'end': end.isoformat(),
                'declared_results': 2, 'cards_seen': 2, 'cards': cards}

    def test_exact_archive_matches_two_yearless_details_in_one_search(self):
        calls = []
        def fetch_window(start, end):
            calls.append((start, end))
            return self.cards(start, end)
        titles = {self.first: 'Il Pacchetto Rosso',
                  self.second: 'Giochi per bambini aspettando Natale'}
        resolved = resolve_historical_years(
            self.snapshot(), fetch_window=fetch_window,
            fetch_html=lambda url: self.html(titles[url]),
            now=datetime(2026, 10, 6, tzinfo=timezone.utc))
        self.assertEqual(len(calls), 1)
        for result in resolved['results'].values():
            self.assertEqual(result['status'], 'past_event')
            self.assertEqual(result['programme_year'], 2022)
            self.assertEqual(result['historical_badges'], ['2022-12-24'])
        original = self.html(titles[self.first])
        self.assertTrue(recheck_historical_result(
            resolved['entries'][self.first], original,
            resolved['results'][self.first], today=date(2026, 10, 6)))
        self.assertFalse(recheck_historical_result(
            resolved['entries'][self.first],
            original.replace('Letture per bambini.', 'Programma aggiornato.'),
            resolved['results'][self.first], today=date(2026, 10, 6)))

    def test_changed_identity_or_current_programme_stays_ambiguous(self):
        snapshot = self.snapshot()
        snapshot['entries'][self.second]['sitemap_lastmod'] = '2026-10-06'
        resolved = resolve_historical_years(
            snapshot, fetch_window=self.cards,
            fetch_html=lambda _: self.html('Il Pacchetto Rosso', city='Udine'))
        self.assertEqual(resolved['results'][self.first]['status'], 'ambiguous')
        self.assertEqual(resolved['results'][self.second]['status'], 'ambiguous')
        current = resolve_historical_years(
            self.snapshot(), fetch_window=self.cards,
            fetch_html=lambda _: self.html('Il Pacchetto Rosso',
                                           description='Programma 2026.'))
        self.assertEqual(current['results'][self.first]['status'], 'ambiguous')

    def test_missing_or_failed_archive_does_not_claim_completeness(self):
        def failed(*_):
            raise TimeoutError('archive unavailable')
        resolved = resolve_historical_years(self.snapshot(), fetch_window=failed,
                                            fetch_html=lambda _: '')
        self.assertEqual(set(resolved['historical_lookup_failures']),
                         {self.first, self.second})
        self.assertTrue(all(item['status'] == 'ambiguous'
                            for item in resolved['results'].values()))
        def empty(start, end):
            return {'start': start.isoformat(), 'end': end.isoformat(),
                    'declared_results': 0, 'cards_seen': 0, 'cards': []}
        missing = resolve_historical_years(self.snapshot(), fetch_window=empty,
                                           fetch_html=lambda _: '')
        self.assertTrue(all(item['status'] == 'ambiguous'
                            for item in missing['results'].values()))


if __name__ == '__main__':
    unittest.main()
