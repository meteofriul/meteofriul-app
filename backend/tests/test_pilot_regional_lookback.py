import unittest
from datetime import date

from app.events.pilot_regional_lookback import new_snapshot, step_snapshot, summary


class RegionalLookbackTests(unittest.TestCase):
    def test_scans_backward_and_checks_older_overflow(self):
        seen = []
        counts = {2026: 2, 2025: 1, 2024: 0, 2023: 0}
        def fetch_window(start, end):
            seen.append((start, end))
            cards = [{'url': f'https://www.turismofvg.it/eventi/{start.year}-{i}'}
                     for i in range(counts[start.year])]
            return {'start': start.isoformat(), 'end': end.isoformat(),
                    'declared_results': len(cards), 'cards_seen': len(cards),
                    'pages': 1, 'cards': cards}
        overflow_urls = []
        def fetch_overflow(url):
            overflow_urls.append(url)
            return {'total': 0, 'cards': [], 'next_url': None}
        snapshot = new_snapshot(today=date(2026, 10, 5))
        for _ in range(5):
            snapshot = step_snapshot(snapshot, fetch_window=fetch_window,
                                     fetch_overflow=fetch_overflow)
        self.assertTrue(snapshot['horizon_complete'])
        self.assertEqual(seen[0], (date(2026, 1, 1), date(2026, 10, 4)))
        self.assertEqual(seen[-1], (date(2023, 1, 1), date(2023, 12, 31)))
        self.assertIn('end=2022-12-31', overflow_urls[0])
        self.assertEqual(summary(snapshot)['cards_seen'], 3)
        self.assertIs(step_snapshot(snapshot), snapshot)

    def test_nonempty_older_overflow_cannot_be_declared_complete(self):
        snapshot = new_snapshot(today=date(2026, 10, 5))
        snapshot['windows'] = [
            {'start': '2026-01-01', 'end': '2026-10-04', 'declared_results': 0,
             'cards_seen': 0, 'pages': 1},
            {'start': '2025-01-01', 'end': '2025-12-31', 'declared_results': 0,
             'cards_seen': 0, 'pages': 1},
        ]
        with self.assertRaisesRegex(ValueError, 'unscanned results'):
            step_snapshot(snapshot, fetch_overflow=lambda _: {
                'total': 1, 'cards': [{}], 'next_url': None})
        self.assertFalse(snapshot['horizon_complete'])

    def test_window_count_mismatch_does_not_advance_snapshot(self):
        snapshot = new_snapshot(today=date(2026, 10, 5))
        with self.assertRaisesRegex(ValueError, 'window incomplete'):
            step_snapshot(snapshot, fetch_window=lambda start, end: {
                'start': start.isoformat(), 'end': end.isoformat(),
                'declared_results': 2, 'cards_seen': 1, 'pages': 1,
                'cards': [{'url': 'https://www.turismofvg.it/eventi/uno'}]})
        self.assertEqual(snapshot['windows'], [])


if __name__ == '__main__':
    unittest.main()
