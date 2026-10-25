"""Pilot-only WSGI read plane. IAM exposes only data; no ADS/state credentials."""
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
from threading import RLock
from time import monotonic
import hashlib
import json
import os
from google.cloud import storage
from local_pipeline.gcs_object_store import GCSObjectStore
from local_pipeline.contract_v1 import load_catalog, ICON_PROVIDER, CAMS_PROVIDER, CAMS_POLLEN_PROVIDER
from local_pipeline.published_runs_reader import PublishedRunsObjectReader
from local_pipeline.sqlite_object_store import ObjectNotFound, ObjectStoreError
from local_pipeline.http_data_plane import _request_object_key, _gzip_deterministic, _accepts_gzip, _if_none_match_matches

PROJECT = os.environ.get("WEATHER_CLOUD_PROJECT", "meteofriul-pilot-20260906")
DATA_BUCKET = os.environ.get("WEATHER_DATA_BUCKET", PROJECT + "-data")
ORIGINS = {"https://localhost", "http://localhost", "http://127.0.0.1:5176",
           "https://meteofriul.app", "https://www.meteofriul.app"}

class CachedReadOnlyStore:
    def __init__(self, store):
        self.store, self.cache, self.lock = store, OrderedDict(), RLock()
        self.bytes = 0
        self.heads = OrderedDict()

    def get(self, key):
        with self.lock:
            now = monotonic()
            cached = self.cache.get(key)
            if cached and now < cached[0]:
                self.cache.move_to_end(key)
                return cached[1]
            result = self.store.get(key)
            if key.endswith('/manifest.json') and '/runs/' in key:
                # Prefetch metadata only; the verified reader still checks every
                # descriptor before it exposes a run. Never download all towns.
                document = json.loads(result.body)
                objects = document.get('objects', {})
                if isinstance(objects, dict) and len(objects) == 215:
                    prefix = key.split('/runs/', 1)[0] + '/'
                    keys = [prefix + value['path'] for value in objects.values()]
                    for item in keys:
                        _request_object_key('/' + item)
                    batch = getattr(self.store, 'municipality_heads', None)
                    if callable(batch):
                        heads = batch(keys)
                        if set(heads) != set(keys):
                            raise ObjectStoreError('incomplete municipality metadata batch')
                    else:
                        with ThreadPoolExecutor(max_workers=8) as pool:
                            heads = dict(zip(keys, pool.map(self.store.head, keys)))
                    # Publish the cache only after the entire batch succeeds.
                    for item, head in heads.items():
                        self.heads[item] = (monotonic() + 3600, head)
                    while len(self.heads) > 1500:
                        self.heads.popitem(last=False)
            if cached:
                self.bytes -= cached[1].size
                del self.cache[key]
            self.cache[key] = (now + (30 if key.endswith('/latest.json') else 3600), result)
            self.bytes += result.size
            while self.bytes > 32 * 1024**2 or len(self.cache) > 512:
                _, (_, removed) = self.cache.popitem(last=False)
                self.bytes -= removed.size
            return result

    def head(self, key):
        with self.lock:
            cached = self.heads.get(key)
            if cached and monotonic() < cached[0]:
                return cached[1]
            return self.get(key).head

    def close(self):
        pass

class PilotApplication:
    def __init__(self, reader_factory):
        self.factory, self.reader, self.lock = reader_factory, None, RLock()

    def __call__(self, env, respond):
        method, path = env.get('REQUEST_METHOD'), env.get('PATH_INFO', '')
        origin = env.get('HTTP_ORIGIN')
        headers = [('X-Content-Type-Options', 'nosniff'), ('Vary', 'Origin, Accept-Encoding')]
        if origin in ORIGINS:
            headers += [('Access-Control-Allow-Origin', origin), ('Access-Control-Expose-Headers', 'ETag')]
        def answer(status, body, extra=()):
            respond(status, headers + [('Content-Type', 'application/json'), ('Content-Length', str(len(body))), *extra])
            return [] if method == 'HEAD' else [body]
        if origin and origin not in ORIGINS:
            return answer('403 Forbidden', b'{"error":"origin_not_allowed"}')
        if method not in ('GET', 'HEAD', 'OPTIONS'):
            return answer('405 Method Not Allowed', b'{}')
        if path == '/healthz' and method in ('GET', 'HEAD'):
            return answer('200 OK', b'{"service":"pilot-weather"}', [('Cache-Control', 'no-store')])
        try:
            if path == '/weather/v1/uv/latest.json' and not env.get('QUERY_STRING') and method in ('GET', 'HEAD'):
                if os.environ.get('GOOGLE_CLOUD_PROJECT') != PROJECT:
                    raise ValueError('weather production configuration required')
                obj = GCSObjectStore(storage.Client(project=PROJECT).bucket(DATA_BUCKET)).get('weather/v1/uv/latest.json')
                return answer('200 OK', obj.body, [('Cache-Control', 'public, max-age=300')])
        except ObjectNotFound:
            return answer('404 Not Found', b'{"error":"not_published"}')
        except ObjectStoreError:
            return answer('503 Service Unavailable', b'{"error":"unavailable"}')
        try:
            if env.get('QUERY_STRING'):
                raise ValueError()
            key = _request_object_key(env.get('RAW_URI', path))
        except ValueError:
            return answer('400 Bad Request', b'{"error":"invalid_path"}')
        if method == 'OPTIONS':
            requested = {v.strip().lower() for v in env.get('HTTP_ACCESS_CONTROL_REQUEST_HEADERS', '').split(',') if v.strip()}
            if not origin or env.get('HTTP_ACCESS_CONTROL_REQUEST_METHOD') not in ('GET', 'HEAD') or requested - {'if-none-match'}:
                return answer('403 Forbidden', b'{}')
            return answer('204 No Content', b'', [('Access-Control-Allow-Methods', 'GET, HEAD, OPTIONS'), ('Access-Control-Allow-Headers', 'If-None-Match')])
        try:
            with self.lock:
                if self.reader is None:
                    self.reader = self.factory()
                reader = self.reader
            obj = reader.get(key)
        except ObjectNotFound:
            return answer('404 Not Found', b'{"error":"not_published"}', [('Cache-Control', 'no-store')])
        except ObjectStoreError:
            return answer('503 Service Unavailable', b'{"error":"unavailable"}', [('Cache-Control', 'no-store')])
        body = obj.body
        extra = [('Cache-Control', 'public, max-age=30, must-revalidate')]
        if _accepts_gzip(env.get('HTTP_ACCEPT_ENCODING')):
            body = _gzip_deterministic(body)
            extra += [('Content-Encoding', 'gzip')]
        etag = '"' + hashlib.sha256(body).hexdigest() + '"'
        extra += [('ETag', etag)]
        if _if_none_match_matches(env.get('HTTP_IF_NONE_MATCH'), etag):
            respond('304 Not Modified', headers + extra)
            return []
        return answer('200 OK', body, extra)

class ProviderScopedReader:
    """Initialize ICON independently; core/pollen keep one atomic CAMS view."""
    def __init__(self, factory):
        self.factory = factory
        self.readers = {}
        self.locks = {'icon': RLock(), 'cams': RLock()}

    def get(self, key):
        if key.startswith(f'weather/v1/{ICON_PROVIDER}/'):
            scope, providers = 'icon', (ICON_PROVIDER,)
        elif key.startswith((f'weather/v1/{CAMS_PROVIDER}/',
                             f'weather/v1/{CAMS_POLLEN_PROVIDER}/',
                             'weather/v1/families/cams/')):
            scope, providers = 'cams', (CAMS_PROVIDER, CAMS_POLLEN_PROVIDER)
        else:
            raise ObjectNotFound(key)
        # Separate locks and stores prevent a slow CAMS startup from holding
        # an ICON request (including the second notice-job attempt).
        with self.locks[scope]:
            if scope not in self.readers:
                self.readers[scope] = self.factory(providers)
            return self.readers[scope].get(key)


def build_reader():
    if os.environ.get('GOOGLE_CLOUD_PROJECT') != PROJECT:
        raise ValueError('weather production configuration required')
    catalog = load_catalog()
    def factory(providers):
        client = storage.Client(project=PROJECT)
        return PublishedRunsObjectReader(
            CachedReadOnlyStore(GCSObjectStore(client.bucket(DATA_BUCKET))),
            catalog, providers=providers)
    return ProviderScopedReader(factory)

application = PilotApplication(build_reader)
