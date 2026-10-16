import json
import unittest
from datetime import date

from app.events.pilot_eventifvg_audit import (
    API, audit_future_archive, location_evidence,
)


class Response:
    def __init__(self, body):
        self.body, self.status_code, self.url = body, 200, API

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def raise_for_status(self):
        pass

    def iter_content(self, _):
        yield json.dumps(self.body).encode('utf-8')


def event(event_id, venue=None):
    return {'id': event_id, 'url': f'https://www.eventifvg.it/evento/test-{event_id}/',
            'title': f'Evento {event_id}', 'status': 'publish',
            'start_date': '2026-10-09 09:00:00', 'end_date': '2026-10-11 21:00:00',
            'venue': venue or {'city': 'Udine'}}


class EventiFvgAuditTests(unittest.TestCase):
    def test_rauscedo_postal_place_beats_via_udine_street(self):
        evidence = location_evidence(event(1, {'address': 'Via Udine 19, 33095 Rauscedo, Italy'}))
        self.assertEqual(evidence, {'kind': 'postal_city',
                                    'city': 'San Giorgio della Richinvelda'})
        self.assertEqual(location_evidence(event(1, {'address': 'Via Udine 19'})),
                         {'kind': 'unresolved'})

    def test_foreign_country_is_not_geocoded_as_fvg(self):
        self.assertEqual(location_evidence(event(1, {'city': 'Udine', 'country': 'SI'})),
                         {'kind': 'foreign_country'})

    def test_pagination_verifies_totals_and_unique_ids(self):
        first = [event(i) for i in range(1, 51)]
        second = [event(51, {'address': 'Via Udine 19'})]
        calls = []

        def get(url, *, params, **_):
            calls.append((url, params.copy()))
            return Response({'events': first if params['page'] == 1 else second,
                             'total': 51, 'total_pages': 2})

        result = audit_future_archive(get=get, today=date(2026, 10, 6))
        self.assertEqual((result['total'], result['pages_read'], result['unique_ids']),
                         (51, 2, 51))
        self.assertEqual(result['location_evidence'],
                         {'structured_city': 50, 'unresolved': 1})
        self.assertEqual(len(result['unresolved_location_urls']), 1)
        self.assertFalse(result['ongoing_started_before_today_verified'])
        self.assertEqual({call[1]['page'] for call in calls}, {1, 2})

        second[0]['id'] = 1
        with self.assertRaisesRegex(ValueError, 'identity changed'):
            audit_future_archive(get=get, today=date(2026, 10, 6))

        second.clear()
        with self.assertRaisesRegex(ValueError, 'missing records'):
            audit_future_archive(get=get, today=date(2026, 10, 6))

        second.append(event(51))
        second[0]['start_date'] = '2026-10-08 09:00:00'
        with self.assertRaisesRegex(ValueError, 'order changed'):
            audit_future_archive(get=get, today=date(2026, 10, 6))


if __name__ == '__main__':
    unittest.main()
