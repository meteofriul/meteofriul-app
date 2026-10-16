import unittest

from app.events.pilot_regional_index import build_candidate_index


class RegionalIndexTests(unittest.TestCase):
    def test_groups_calendar_occurrences_by_detail_and_reports_sitemap_gap(self):
        known = 'https://www.turismofvg.it/eventi/mercatino'
        missed = 'https://www.turismofvg.it/eventi/nuovo'
        sitemap = {'status': 'ok', 'unique_urls': 1,
                   'detail_urls': [{'url': known, 'lastmod': '2026-10-01T00:00:00Z'}]}
        calendar = {'status': 'ok', 'horizon_complete': True,
                    'collection_mode': 'annual-date-filters', 'windows': [],
                    'overflow': {'declared_results': 0},
                    'declared_results': 3, 'cards_seen': 3, 'pages': 1,
                    'cards': [
                        {'url': known, 'title': 'Mercatino', 'place': 'Gemona del Friuli',
                         'badge_date': '2026-10-04'},
                        {'url': known, 'title': 'Mercatino', 'place': 'Gemona del Friuli',
                         'badge_date': '2026-11-01'},
                        {'url': missed, 'title': 'Nuovo', 'place': 'Udine',
                         'badge_date': '2026-10-08'},
                    ]}
        result = build_candidate_index(sitemap, calendar)
        self.assertEqual(len(result['detail_candidates']), 2)
        market = result['detail_candidates'][0]
        self.assertEqual(market['listing_occurrences'], ['2026-10-04', '2026-11-01'])
        self.assertEqual(market['sitemap_lastmod'], '2026-10-01T00:00:00Z')
        self.assertEqual(result['verification']['missing_from_sitemap'], [missed])
        self.assertEqual(result['verification']['sitemap_only_unclassified'], 0)

    def test_sitemap_only_urls_remain_unclassified(self):
        listed = 'https://www.turismofvg.it/eventi/listed'
        unlisted = 'https://www.turismofvg.it/eventi/unlisted'
        sitemap = {'status': 'ok', 'unique_urls': 2,
                   'detail_urls': [{'url': listed}, {'url': unlisted}]}
        calendar = {'status': 'ok', 'horizon_complete': True,
                    'collection_mode': 'annual-date-filters', 'windows': [],
                    'overflow': {'declared_results': 0},
                    'declared_results': 1, 'cards_seen': 1, 'pages': 1,
                    'cards': [{'url': listed, 'title': 'Listed', 'badge_date': '2026-10-04'}]}
        result = build_candidate_index(sitemap, calendar)
        self.assertEqual(result['verification']['sitemap_only_unclassified'], 1)
        self.assertEqual(result['verification']['sitemap_only_urls'], [unlisted])

    def test_conflicting_titles_are_not_silently_merged(self):
        url = 'https://www.turismofvg.it/eventi/uno'
        sitemap = {'status': 'ok', 'unique_urls': 1,
                   'detail_urls': [{'url': url, 'lastmod': None}]}
        calendar = {'status': 'ok', 'horizon_complete': True,
                    'collection_mode': 'annual-date-filters', 'windows': [],
                    'overflow': {'declared_results': 0},
                    'declared_results': 2, 'cards_seen': 2, 'pages': 1,
                    'cards': [{'url': url, 'title': 'Prima', 'badge_date': '2026-10-04'},
                              {'url': url, 'title': 'Seconda', 'badge_date': '2026-10-05'}]}
        result = build_candidate_index(sitemap, calendar)
        self.assertEqual(result['detail_candidates'], [])
        self.assertEqual(result['review_required'][0]['review_reason'],
                         'conflicting_calendar_titles')


if __name__ == '__main__':
    unittest.main()
