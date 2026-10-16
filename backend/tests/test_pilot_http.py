import json
import unittest
from unittest.mock import patch
from app.events.pilot_http import application

class HttpTests(unittest.TestCase):
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
            'good': {'status': 'fresh'},
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
            'Paesi in Festa': {'status': 'partial',
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
            'good': {'status': 'fresh'}}, 'monitors': {
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
