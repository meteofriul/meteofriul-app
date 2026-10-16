"""EV-04: real catalog filtering and public health must agree."""
from datetime import datetime, timedelta, timezone
import json
import unittest
from unittest.mock import patch

from app.events.pilot_http import application


NOW = datetime(2026, 10, 15, 12, tzinfo=timezone.utc)
EVENT = {'source': 'Azalea', 'title': 'Verified concert', 'start_date': '2026-10-16',
         'url': 'https://example.test/concert', 'lat': 46.07, 'lon': 13.23}


def batch(status='fresh', age=0, events=None):
    return {'status': status, 'updated_at': (NOW - timedelta(hours=age)).isoformat(),
            'events': [EVENT] if events is None else events}


class CatalogHealthTests(unittest.TestCase):
    def request(self, sources):
        status = []
        catalog = {'schema': 'pilot-events-v1', 'sources': sources,
                   'attempted_at': NOW.isoformat()}
        with patch('app.events.pilot_http.load_catalog', return_value=catalog), patch(
                'app.events.pilot_http.datetime') as clock:
            clock.now.return_value = NOW
            body = application({'REQUEST_METHOD': 'GET', 'PATH_INFO': '/api/local/events',
                                'QUERY_STRING': 'lat=46.07&lon=13.23&radius=20'},
                               lambda code, headers: status.append(code))
        self.assertEqual(status, ['200 OK'])
        return json.loads(b''.join(body))

    def test_complete_empty_is_distinct_from_expired_empty(self):
        complete = self.request({'Azalea': batch(events=[])})
        self.assertEqual(complete['catalog_status'], 'complete')
        expired = self.request({'Azalea': batch(age=49)})
        self.assertEqual(expired['events'], [])
        self.assertEqual(expired['catalog_status'], 'degraded')
        self.assertEqual(expired['source_failure_tags'], {'Azalea': 'source_expired'})
        self.assertEqual(expired['source_updated_at']['Azalea'], batch(age=49)['updated_at'])

    def test_partial_and_failed_sources_do_not_hide_healthy_events(self):
        result = self.request({'Azalea': batch(), 'partial': batch('partial', events=[]),
                               'failed': batch('stale'), 'new': batch('unavailable')})
        self.assertEqual(len(result['events']), 1)
        self.assertEqual(result['catalog_status'], 'degraded')
        self.assertEqual(result['source_status']['partial'], 'partial')
        self.assertEqual(result['source_failure_tags'], {
            'partial': 'quarantined_cards', 'failed': 'source_error', 'new': 'source_error'})

    def test_source_age_boundary_matches_visibility(self):
        for age, visible in [(48, True), (48.0001, False), (-1, False)]:
            with self.subTest(age=age):
                result = self.request({'Azalea': batch(age=age)})
                self.assertEqual(bool(result['events']), visible)
                self.assertEqual(result['catalog_status'], 'complete' if visible else 'degraded')

    def test_invalid_timestamps_cannot_look_like_healthy_empty(self):
        for timestamp in [None, '', 'not-a-date', '2026-10-15T12:00:00']:
            with self.subTest(timestamp=timestamp):
                source = {**batch(), 'updated_at': timestamp}
                result = self.request({'Azalea': source})
                self.assertEqual(result['events'], [])
                self.assertEqual(result['source_failure_tags'], {
                    'Azalea': 'source_timestamp_invalid'})

    def test_expired_partial_reports_expiry_before_quarantine(self):
        result = self.request({'Azalea': batch('partial', age=49)})
        self.assertEqual(result['events'], [])
        self.assertEqual(result['source_failure_tags']['Azalea'], 'source_expired')

    def test_health_never_exposes_internal_diagnostics(self):
        source = {**batch('stale'), 'last_attempt_error_type': 'adapter_exception',
                  'last_attempt_error_detail': 'private-error-detail',
                  'review_required': [{'detail': 'private-review-detail'}]}
        result = self.request({'Azalea': source})
        self.assertEqual(result['source_failure_tags']['Azalea'], 'adapter_exception')
        self.assertNotIn('private-', json.dumps(result))
