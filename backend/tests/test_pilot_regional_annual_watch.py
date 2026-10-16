import unittest
from datetime import date

from app.events.pilot_regional_annual_watch import collect_watch


class AnnualInventoryWatchTests(unittest.TestCase):
    def calendar(self, start, end, *, max_workers):
        self.assertEqual((start, end, max_workers),
                         (date(2026, 1, 1), date(2026, 12, 31), 16))
        cards = [{'url': 'https://www.turismofvg.it/eventi/uno'},
                 {'url': 'https://www.turismofvg.it/eventi/due'}]
        return {'start': start.isoformat(), 'end': end.isoformat(),
                'declared_results': 2, 'cards_seen': 2, 'pages': 3,
                'cards': cards}

    def test_compares_current_year_window_to_complete_annual_index(self):
        report = collect_watch(
            date(2026, 10, 11),
            ['https://www.turismofvg.it/eventi/uno'],
            fetch_calendar=self.calendar)
        self.assertTrue(report['source_complete'])
        self.assertEqual(report['calendar_pages'], 3)

    def test_missing_window_url_requires_review(self):
        report = collect_watch(
            date(2026, 10, 11),
            ['https://www.turismofvg.it/eventi/tre'],
            fetch_calendar=self.calendar)
        self.assertFalse(report['source_complete'])
        self.assertEqual(report['missing_window_count'], 1)


if __name__ == '__main__':
    unittest.main()
