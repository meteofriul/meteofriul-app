"""Read-only pilot Eventi HTTP service; no scraping on requests."""
import json
from datetime import datetime, timezone
import os
from threading import Lock
from time import monotonic
from urllib.parse import parse_qs
from .pilot_catalog import PILOT_PROJECT, query_catalog, source_age_failure
from .pilot_cloud import BUCKET, KEY, MAX_BYTES

_cache = None
_until = 0
_lock = Lock()


def load_catalog():
    global _cache, _until
    if os.environ.get('GOOGLE_CLOUD_PROJECT') != PILOT_PROJECT:
        raise ValueError('isolated events project required')
    with _lock:
        if _cache is not None and monotonic() < _until:
            return _cache
        from google.cloud import storage
        blob = storage.Client(project=PILOT_PROJECT).bucket(BUCKET).blob(KEY)
        blob.reload(timeout=10)
        if blob.size > MAX_BYTES:
            raise ValueError('oversized catalog')
        data = blob.download_as_bytes(if_generation_match=int(blob.generation), timeout=10)
        catalog = json.loads(data)
        if catalog.get('schema') != 'pilot-events-v1':
            raise ValueError('invalid catalog')
        _cache, _until = catalog, monotonic()+60
        return catalog


def application(environ, start_response):
    headers = [('Content-Type', 'application/json; charset=utf-8'), ('Cache-Control', 'no-store')]
    origin = environ.get('HTTP_ORIGIN', '')
    if origin in {'http://127.0.0.1:5176', 'https://localhost', 'http://localhost',
                  'https://meteofriul.app', 'https://www.meteofriul.app'}:
        headers += [('Access-Control-Allow-Origin', origin), ('Vary', 'Origin')]
    status, payload = '200 OK', {}
    if environ.get('REQUEST_METHOD') != 'GET':
        status, payload = '405 Method Not Allowed', {'error': 'read_only'}
    elif environ.get('PATH_INFO') == '/health':
        payload = {'service': 'pilot-events'}
    elif environ.get('PATH_INFO') == '/api/local/events':
        try:
            args = parse_qs(environ.get('QUERY_STRING', ''))
            lat, lon = float(args['lat'][0]), float(args['lon'][0])
            radius = int(args.get('radius', ['20'])[0])
            limit = int(args.get('limit', ['100'])[0])
            offset = int(args.get('offset', ['0'])[0])
            if not 0 <= offset <= 10000:
                raise ValueError('offset')
            if not 1 <= limit <= 500:
                raise ValueError('limit')
        except (KeyError, ValueError, IndexError):
            status, payload = '400 Bad Request', {'error': 'invalid_query'}
        else:
            try:
                catalog = load_catalog()
                now = datetime.now(timezone.utc)
                payload = query_catalog(catalog, lat, lon, radius, now=now)
                payload['total'] = len(payload['events'])
                payload['events'] = payload['events'][offset:offset+limit]
                payload['next_offset'] = offset+limit if offset+limit < payload['total'] else None
                payload['snapshot'] = catalog.get('attempted_at')
                if args.get('snapshot', [payload['snapshot']])[0] != payload['snapshot']:
                    status, payload = '409 Conflict', {'error': 'catalog_changed'}
                    data = json.dumps(payload).encode('utf-8')
                    start_response(status, headers)
                    return [data]
                payload['source_status'] = {name: batch['status'] for name, batch in catalog['sources'].items()}
                payload['source_updated_at'] = {
                    name: batch.get('updated_at') for name, batch in catalog['sources'].items()}
                payload['source_failure_tags'] = {}
                for name, batch in catalog['sources'].items():
                    if batch['status'] in {'fresh', 'partial'}:
                        tag = source_age_failure(batch, now=now) or (
                            'quarantined_cards' if batch['status'] == 'partial' else None)
                    else:
                        tag = batch.get('last_attempt_error_type') or 'source_error'
                    if tag:
                        payload['source_failure_tags'][name] = tag
                payload['catalog_status'] = (
                    'degraded' if payload['source_failure_tags'] else 'complete')
                payload['monitor_status'] = catalog.get('monitors') or {}
                payload['status'] = 'ready'
            except ValueError:
                status, payload = '400 Bad Request', {'error': 'invalid_query_or_catalog'}
            except Exception:
                status, payload = '503 Service Unavailable', {'error': 'catalog_unavailable'}
    else:
        status, payload = '404 Not Found', {'error': 'not_found'}
    data = json.dumps(payload, ensure_ascii=False, allow_nan=False).encode('utf-8')
    start_response(status, headers + [('Content-Length', str(len(data)))])
    return [data]
