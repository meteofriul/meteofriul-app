import json
import unittest
from datetime import date

from app.events.pilot_regional_local_preview import (
    create_application, nearby_events, prepare_display,
)


TODAY = date(2026, 10, 5)
BASE = 'https://www.turismofvg.it/eventi/'


def request(app, query='', *, method='GET'):
    response = {}

    def start(status, headers):
        response['status'] = status
        response['headers'] = dict(headers)

    body = b''.join(app({'REQUEST_METHOD': method,
                         'PATH_INFO': '/api/local/events',
                         'QUERY_STRING': query}, start))
    return response['status'], json.loads(body)


class RegionalLocalPreviewTests(unittest.TestCase):
    def test_preparation_keeps_structured_period_and_excerpt(self):
        url = BASE + 'amelie-il-musical'
        control = {
            'schema': 'turismofvg-current-year-control-v1',
            'as_of_date': TODAY.isoformat(), 'attempts': {},
            'entries': {url: {'candidate': {'url': url,
                                           'listing_occurrences': ['2026-10-16']}}},
            'results': {url: {'status': 'detail_aligned',
                              'detail_date_full': '16 ottobre 2026 - 19 ottobre 2026',
                              'event': {'title': 'Amélie - Il Musical',
                                        'event_city': 'Udine',
                                        'description_excerpt': 'Uno spettacolo musicale.',
                                        'description_source_url': url}}},
        }
        display = prepare_display(control, today=TODAY)
        self.assertTrue(display['local_preview_only'])
        self.assertEqual(len(display['cards']), 1)
        card = display['cards'][0]
        self.assertEqual((card['start_date'], card['end_date']),
                         ('2026-10-16', '2026-10-19'))
        self.assertEqual(card['description_excerpt'], 'Uno spettacolo musicale.')
        self.assertEqual(card['url'], url)

    def test_geography_order_pagination_and_snapshot(self):
        def card(slug, day, latitude):
            return {'url': BASE + slug, 'title': slug,
                    'start_date': day, 'end_date': day, 'sort_date': day,
                    'lat': latitude, 'lon': 13.2346,
                    'location_confidence': 'municipality'}

        display = {'as_of_date': TODAY.isoformat(), 'local_preview_only': True,
                   'cards': [card('late', '2026-10-25', 46.0711),
                             card('outside-radius', '2026-10-06', 47.0),
                             card('early', '2026-10-06', 46.0711)],
                   'quarantined': [{'url': BASE + 'unresolved'}],
                   'source_complete': False}
        selected = nearby_events(display, lat=46.0711, lon=13.2346,
                                 radius=20, today=TODAY)
        self.assertEqual([event['title'] for event in selected], ['early', 'late'])
        self.assertFalse(selected[0]['preview_outside_window'])
        self.assertTrue(selected[1]['preview_outside_window'])
        app = create_application(display, today=TODAY, snapshot='snapshot-1',
                                 clock=lambda: TODAY)
        query = 'city=Udine&lat=46.0711&lon=13.2346&radius=20&limit=1'
        status, first = request(app, query)
        self.assertEqual(status, '200 OK')
        self.assertEqual(first['total'], 2)
        self.assertEqual(first['next_offset'], 1)
        self.assertEqual(first['coverage']['quarantined'], 1)
        self.assertFalse(first['coverage']['source_complete'])
        status, second = request(app, query + '&offset=1&snapshot=snapshot-1')
        self.assertEqual(status, '200 OK')
        self.assertEqual(second['events'][0]['title'], 'late')
        self.assertIsNone(second['next_offset'])
        status, conflict = request(app, query + '&offset=1&snapshot=old')
        self.assertEqual((status, conflict['error']),
                         ('409 Conflict', 'catalog_changed'))

    def test_service_rejects_preview_after_date_changes(self):
        display = {'as_of_date': TODAY.isoformat(), 'local_preview_only': True,
                   'cards': []}
        current = [TODAY]
        app = create_application(display, today=TODAY, snapshot='snapshot-1',
                                 clock=lambda: current[0])
        current[0] = date(2026, 10, 6)
        status, payload = request(app, 'city=Udine')
        self.assertEqual((status, payload['error']),
                         ('503 Service Unavailable', 'stale_preview'))

    def test_end_only_exhibition_is_returned_without_start_date(self):
        url = BASE + 'memorie-riflesse'
        display = {'as_of_date': TODAY.isoformat(), 'local_preview_only': True,
                   'cards': [{'url': url, 'title': 'Memorie riflesse',
                              'start_date': None, 'end_date': '2027-01-07',
                              'sort_date': '2027-01-07',
                              'date_label': 'Fino al 7 gennaio 2027',
                              'schedule_kind': 'end_only',
                              'lat': 46.0711, 'lon': 13.2346}],
                   'quarantined': [], 'source_complete': True}
        app = create_application(display, today=TODAY, snapshot='end-only',
                                 clock=lambda: TODAY)
        status, payload = request(app, 'city=Udine&lat=46.0711&lon=13.2346')
        self.assertEqual(status, '200 OK')
        self.assertEqual(payload['total'], 1)
        self.assertIsNone(payload['events'][0]['start_date'])
        self.assertEqual(payload['events'][0]['date_label'],
                         'Fino al 7 gennaio 2027')


if __name__ == '__main__':
    unittest.main()
