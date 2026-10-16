import unittest
import requests

from app.events.pilot_regional_reconcile import reconcile_snapshots, inspect_orphans


class RegionalReconciliationTests(unittest.TestCase):
    def snapshots(self):
        listed = 'https://www.turismofvg.it/eventi/listed'
        ongoing = 'https://www.turismofvg.it/eventi/ongoing'
        orphan = 'https://www.turismofvg.it/events20/details/123'
        forward = {
            'schema': 'turismofvg-sitemap-only-audit-v1',
            'as_of_date': '2026-10-05', 'snapshot_id': 'abc',
            'index_verification': {'horizon_complete': True,
                'declared_results': 1, 'cards_seen': 1,
                'sitemap_unique_urls': 1, 'missing_from_sitemap': [listed]},
            'calendar_candidates': [{'url': listed}],
            'sitemap_only_urls': [ongoing],
            'results': {ongoing: {'status': 'future_candidate',
                                  'title': 'Ongoing', 'date_full': '1 agosto - 31 dicembre 2026',
                                  'reason': 'detail_needs_reconciliation'}},
            'attempts': {},
        }
        retrospective = {
            'schema': 'turismofvg-retrospective-audit-v1',
            'as_of_date': '2026-10-05', 'horizon_complete': True,
            'windows': [
                {'start': '2026-01-01', 'end': '2026-10-04',
                 'declared_results': 2, 'cards_seen': 2, 'pages': 1},
                {'start': '2025-01-01', 'end': '2025-12-31',
                 'declared_results': 0, 'cards_seen': 0, 'pages': 1},
                {'start': '2024-01-01', 'end': '2024-12-31',
                 'declared_results': 0, 'cards_seen': 0, 'pages': 1},
            ],
            'cards': [{'url': ongoing, 'badge_date': '2026-08-01'},
                      {'url': orphan, 'badge_date': '2026-05-03'}],
            'older_overflow': {'start': '1900-01-01', 'end': '2023-12-31',
                               'declared_results': 0},
        }
        return forward, retrospective

    def test_joins_three_indexes_without_promoting_unverified_details(self):
        forward, retrospective = self.snapshots()
        result = reconcile_snapshots(forward, retrospective)
        self.assertEqual(result['union_urls'], 3)
        self.assertEqual(result['retrospective_only_urls'], 2)
        self.assertEqual(len(result['retrospective_orphan_urls']), 1)
        self.assertEqual(result['future_detail_candidates'][0]['historical_badges'],
                         ['2026-08-01'])
        self.assertFalse(result['publication_ready'])

    def test_reservation_only_experience_is_counted_but_not_promoted(self):
        forward, retrospective = self.snapshots()
        url = next(iter(forward['results']))
        forward['results'][url] = {'status': 'non_event_experience',
                                   'reason': 'reservation_only_experience'}
        result = reconcile_snapshots(forward, retrospective)
        self.assertEqual(result['detail_classification_counts']['non_event_experience'], 1)
        self.assertEqual(result['future_detail_candidates'], [])
        self.assertEqual(result['scope_excluded_details'][0]['historical_badges'],
                         ['2026-08-01'])

    def test_forward_detail_progress_is_joined_by_snapshot_identity(self):
        forward, retrospective = self.snapshots()
        detail = {'schema': 'turismofvg-forward-detail-audit-v1',
                  'as_of_date': '2026-10-05', 'index_snapshot_id': 'abc',
                  'candidates': forward['calendar_candidates'],
                  'results': {forward['calendar_candidates'][0]['url']:
                              {'status': 'review_required', 'reason': 'date_conflict'}},
                  'attempts': {}}
        result = reconcile_snapshots(forward, retrospective, detail)
        self.assertEqual(result['forward_details_pending'], 0)
        self.assertEqual(result['forward_detail_audit']['review_required'], 1)
        detail['index_snapshot_id'] = 'another'
        with self.assertRaisesRegex(ValueError, 'another index'):
            reconcile_snapshots(forward, retrospective, detail)

    def test_incomplete_or_mismatched_history_fails(self):
        forward, retrospective = self.snapshots()
        retrospective['as_of_date'] = '2026-10-04'
        with self.assertRaisesRegex(ValueError, 'coverage incomplete'):
            reconcile_snapshots(forward, retrospective)
        retrospective['as_of_date'] = '2026-10-05'
        retrospective['older_overflow']['declared_results'] = 1
        with self.assertRaisesRegex(ValueError, 'coverage incomplete'):
            reconcile_snapshots(forward, retrospective)

    def test_uninspected_sitemap_detail_fails(self):
        forward, retrospective = self.snapshots()
        forward['results'] = {}
        with self.assertRaisesRegex(ValueError, 'not fully inspected'):
            reconcile_snapshots(forward, retrospective)

    def test_historical_orphans_are_checked_and_404_is_recorded(self):
        old = 'https://www.turismofvg.it/events20/details/123'
        gone = 'https://www.turismofvg.it/eventi/old-gone'
        report = {'schema': 'turismofvg-index-reconciliation-v1',
                  'as_of_date': '2026-10-05',
                  'retrospective_orphan_urls': [old, gone],
                  'orphan_results': {}, 'orphan_attempts': {}}
        def fetch(url):
            if url == gone:
                response = requests.Response()
                response.status_code = 404
                raise requests.HTTPError(response=response)
            return ('<h1>Festa vecchia</h1>'
                    '<div style="background-image: url(icn__calendar.svg)">10 giugno 2022</div>'
                    '<div style="background-image: url(icn__pin.svg)">Udine</div>')
        checked = inspect_orphans(report, fetch_html=fetch)
        self.assertEqual(checked['orphan_results'][old]['status'], 'past_event')
        self.assertEqual(checked['orphan_results'][gone]['status'], 'removed_page')
        self.assertEqual(checked['orphan_attempts'], {})


if __name__ == '__main__':
    unittest.main()
