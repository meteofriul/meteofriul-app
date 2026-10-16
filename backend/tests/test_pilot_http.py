import json
import unittest
from datetime import datetime
from unittest.mock import patch
from app.events.pilot_http import application

class HttpTests(unittest.TestCase):
    now = datetime.fromisoformat('2026-10-13T12:00:00+00:00')

    def setUp(self):
        # Freeze both clocks so the real filtering and HTTP metadata agree.
        for module in ('pilot_catalog', 'pilot_http'):
            clock = patch(f'app.events.{module}.datetime', wraps=datetime)
            clock.start().now.return_value = self.now
            self.addCleanup(clock.stop)

    def catalog_response(self, sources):
        status = []
        catalog = {'attempted_at': 'v1', 'sources': sources}
        with patch('app.events.pilot_http.load_catalog', return_value=catalog):
            response = application({'REQUEST_METHOD': 'GET', 'PATH_INFO': '/api/local/events',
                                    'QUERY_STRING': 'lat=46&lon=13'},
                                   lambda code, headers: status.append(code))
        self.assertEqual(status, ['200 OK'])
        return json.loads(b''.join(response))

    def test_source_age_metadata_matches_actual_visibility(self):
        event = {'title': 'Evento', 'source': 'Azalea', 'url': 'https://azalea.it/evento/',
                 'start_date': '2026-10-14', 'end_date': '2026-10-14', 'lat': 46, 'lon': 13}
        cases = (
            ('2026-10-13T12:00:00Z', None),
            ('2026-10-11T12:00:00Z', None),  # Exactly 48h is still allowed.
            ('2026-10-11T11:59:59.999999Z', 'source_expired'),
            ('2026-10-13T14:00:00+02:00', None),
            ('2026-10-13T12:00:00.000001Z', 'source_timestamp_future'),
            (None, 'source_timestamp_invalid'),
            ('invalid', 'source_timestamp_invalid'),
            ('2026-10-13T12:00:00', 'source_timestamp_invalid'),
        )
        for status in ('fresh', 'partial'):
            for updated_at, age_tag in cases:
                with self.subTest(status=status, updated_at=updated_at):
                    payload = self.catalog_response({'Azalea': {
                        'status': status, 'updated_at': updated_at, 'events': [event]}})
                    tag = age_tag or ('quarantined_cards' if status == 'partial' else None)
                    self.assertEqual(len(payload['events']), 0 if age_tag else 1)
                    self.assertEqual(payload['source_status'], {'Azalea': status})
                    self.assertEqual(payload['source_updated_at'], {'Azalea': updated_at})
                    self.assertEqual(payload['source_failure_tags'], {'Azalea': tag} if tag else {})
                    self.assertEqual(payload['catalog_status'], 'degraded' if tag else 'complete')

    def test_healthy_empty_or_outside_radius_catalog_stays_complete(self):
        distant = {'title': 'Lontano', 'source': 'Azalea', 'start_date': '2026-10-14',
                   'lat': 45.65, 'lon': 13.77}
        for events in ([], [distant]):
            with self.subTest(events=events):
                payload = self.catalog_response({'Azalea': {'status': 'fresh',
                    'updated_at': self.now.isoformat(), 'events': events}})
                self.assertEqual(payload['events'], [])
                self.assertEqual(payload['catalog_status'], 'complete')
                self.assertEqual(payload['source_failure_tags'], {})

    def test_expired_source_does_not_hide_another_current_source(self):
        event = {'title': 'Evento', 'source': 'Azalea', 'start_date': '2026-10-14',
                 'lat': 46, 'lon': 13}
        payload = self.catalog_response({
            'Azalea': {'status': 'fresh', 'updated_at': self.now.isoformat(), 'events': [event]},
            'CSS Udine': {'status': 'fresh', 'updated_at': '2026-10-10T12:00:00Z',
                          'events': [{**event, 'source': 'CSS Udine', 'title': 'Altro'}]}})
        self.assertEqual(len(payload['events']), 1)
        self.assertEqual(payload['events'][0]['source'], 'Azalea')
        self.assertEqual(payload['source_failure_tags'], {'CSS Udine': 'source_expired'})
        self.assertEqual(payload['catalog_status'], 'degraded')

    def request(self, query):
        status = []
        with patch('app.events.pilot_http.load_catalog', return_value={'attempted_at':'v1','sources':{}}), patch('app.events.pilot_http.query_catalog', return_value={'events':list(range(230))}):
            data = application({'REQUEST_METHOD':'GET','PATH_INFO':'/api/local/events','QUERY_STRING':query}, lambda s,h: status.append(s))
        return status[0], json.loads(b''.join(data))

    def test_pages_do_not_truncate_or_overlap(self):
        base='lat=46&lon=13&limit=100'
        all_events=[]
        for offset in (0,100,200):
            status,payload=self.request(base+f'&offset={offset}&snapshot=v1')
            self.assertEqual(status,'200 OK')
            all_events += payload['events']
        self.assertEqual(all_events,list(range(230)))
        self.assertIsNone(payload['next_offset'])

    def test_changed_snapshot_rejected(self):
        self.assertEqual(self.request('lat=46&lon=13&snapshot=old')[0],'409 Conflict')

    def test_negative_offset_rejected(self):
        self.assertEqual(self.request('lat=46&lon=13&offset=-1')[0],'400 Bad Request')

    def test_failed_sources_have_tags_without_exposing_error_detail(self):
        catalog = {'attempted_at': 'v1', 'sources': {
            'good': {'status': 'fresh', 'updated_at': self.now.isoformat()},
            'failed': {'status': 'stale', 'last_attempt_error_type': 'adapter_exception',
                       'last_attempt_error_detail': 'private diagnostic'}}}
        status = []
        with patch('app.events.pilot_http.load_catalog', return_value=catalog), patch(
                'app.events.pilot_http.query_catalog', return_value={'events': []}):
            data = application({'REQUEST_METHOD': 'GET', 'PATH_INFO': '/api/local/events',
                                'QUERY_STRING': 'lat=46&lon=13'},
                               lambda code, headers: status.append(code))
        payload = json.loads(b''.join(data))
        self.assertEqual(status, ['200 OK'])
        self.assertEqual(payload['catalog_status'], 'degraded')
        self.assertEqual(payload['source_failure_tags'], {'failed': 'adapter_exception'})
        self.assertNotIn('private diagnostic', json.dumps(payload))

    def test_partial_paesi_source_is_tagged_without_exposing_card_detail(self):
        catalog = {'attempted_at': 'v1', 'sources': {
            'Paesi in Festa': {'status': 'partial', 'updated_at': self.now.isoformat(),
                               'review_required': [{'url': 'https://paesiinfesta.com/bad/',
                                                    'reason': 'detail_conflict',
                                                    'detail': 'private diagnostic'}]}}}
        with patch('app.events.pilot_http.load_catalog', return_value=catalog), patch(
                'app.events.pilot_http.query_catalog', return_value={'events': []}):
            data = application({'REQUEST_METHOD': 'GET', 'PATH_INFO': '/api/local/events',
                                'QUERY_STRING': 'lat=46&lon=13'}, lambda code, headers: None)
        payload = json.loads(b''.join(data))
        self.assertEqual(payload['source_status']['Paesi in Festa'], 'partial')
        self.assertEqual(payload['source_failure_tags'], {'Paesi in Festa': 'quarantined_cards'})
        self.assertNotIn('private diagnostic', json.dumps(payload))

    def test_unverified_inventory_monitor_is_visible_separately_from_sources(self):
        catalog = {'attempted_at': 'v1', 'sources': {
            'good': {'status': 'fresh', 'updated_at': self.now.isoformat()}}, 'monitors': {
            'Anteprima Sagre': {'status': 'unverified',
                                'tag': 'upstream_unavailable',
                                'checked_at': '2026-10-08T17:00:00+00:00'}}}
        with patch('app.events.pilot_http.load_catalog', return_value=catalog), patch(
                'app.events.pilot_http.query_catalog', return_value={'events': []}):
            data = application({'REQUEST_METHOD': 'GET', 'PATH_INFO': '/api/local/events',
                                'QUERY_STRING': 'lat=46&lon=13'}, lambda code, headers: None)
        payload = json.loads(b''.join(data))
        self.assertEqual(payload['catalog_status'], 'complete')
        self.assertEqual(payload['source_failure_tags'], {})
        self.assertEqual(payload['monitor_status']['Anteprima Sagre']['status'], 'unverified')
