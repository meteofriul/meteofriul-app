"""Offline cold-reader regression: bounded metadata I/O, unchanged contracts."""
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
import gzip
import json
from threading import Event
from unittest import TestCase
from unittest.mock import Mock, patch

import cloud_reader
from cloud_reader import CachedReadOnlyStore, PilotApplication, ProviderScopedReader, build_reader
from local_pipeline.contract_v1 import (
    ICON_PROVIDER, CAMS_PROVIDER, CAMS_POLLEN_PROVIDER,
    build_latest_document, canonical_json_bytes, load_catalog,
)
from local_pipeline.gcs_object_store import GCSObjectStore
from local_pipeline.published_runs_reader import PublishedRunsObjectReader
from local_pipeline.sqlite_object_store import ObjectNotFound, ObjectStoreError
from test_contract_publisher import MemoryObjectStore
from test_published_runs_reader import (
    BODY, manifest, utc, manifest_key, object_key, family_release,
    family_latest, family_release_key, FAMILY_LATEST_KEY,
)


class OfflineBlob:
    def __init__(self, bucket, name):
        self.bucket, self.name = bucket, name
        self.key = name.removeprefix('pilot/')

    def load(self):
        obj = self.bucket.backing.get(self.key)
        self.size, self.content_type = obj.size, obj.content_type
        self.generation = self.bucket.backing.generations[self.key]
        self.metadata = {**obj.metadata, 'mf-sha256': obj.sha256}
        return self

    def reload(self, **kwargs):
        self.bucket.calls.append(('metadata_read', self.key))
        self.load()

    def download_as_bytes(self, *, if_generation_match, **kwargs):
        self.bucket.calls.append(('download', self.key))
        if if_generation_match != self.bucket.backing.generations[self.key]:
            raise RuntimeError('generation changed')
        return self.bucket.backing.get(self.key).body


class OfflineBucket:
    """No SDK client/credentials: records each would-be storage operation."""
    name = 'meteofriul-pilot-startup-test'

    def __init__(self, backing):
        self.backing, self.calls = backing, []
        self.list_options = []

    def blob(self, name):
        return OfflineBlob(self, name)

    def list_blobs(self, **options):
        self.list_options.append(options)
        prefix = options['prefix'].removeprefix('pilot/')
        self.calls.append(('metadata_list', prefix))
        for key in self.backing.list_keys(prefix)[:options['max_results']]:
            yield self.blob('pilot/' + key).load()


def fixture():
    catalog, store = load_catalog(), MemoryObjectStore()
    manifests = {}
    for provider in (ICON_PROVIDER, CAMS_PROVIDER, CAMS_POLLEN_PROVIDER):
        for day in (1, 2):
            doc = manifest(provider, utc(day), catalog)
            manifests[provider, day] = doc
            store.put(manifest_key(provider, doc), canonical_json_bytes(doc), content_type='application/json')
            for istat in catalog.istat_codes:
                store.put(object_key(provider, doc, istat), BODY, content_type='application/json')
    latest = build_latest_document(provider=ICON_PROVIDER, revision=2, published_at='2026-09-04T12:00:00Z',
        run_manifest=manifests[ICON_PROVIDER, 2], previous_manifest=manifests[ICON_PROVIDER, 1], catalog=catalog)
    store.put('weather/v1/icon2i/latest.json', canonical_json_bytes(latest), content_type='application/json')
    releases = [family_release(manifests[CAMS_PROVIDER, day], manifests[CAMS_POLLEN_PROVIDER, day], catalog) for day in (1, 2)]
    for release in releases:
        store.put(family_release_key(release), canonical_json_bytes(release), content_type='application/json')
    store.put(FAMILY_LATEST_KEY, canonical_json_bytes(family_latest(releases[1], catalog,
        previous=releases[0], revision=2)), content_type='application/json')
    return catalog, store, manifests


def app_for(bucket, catalog):
    def factory(providers):
        return PublishedRunsObjectReader(CachedReadOnlyStore(GCSObjectStore(bucket)), catalog, providers=providers)
    return PilotApplication(lambda: ProviderScopedReader(factory))


def request(app, path='weather/v1/icon2i/latest.json', **env):
    response = []
    body = b''.join(app({'REQUEST_METHOD': 'GET', 'PATH_INFO': '/' + path, **env},
                       lambda status, headers: response.append((status, dict(headers)))))
    return *response[0], body


class StartupTests(TestCase):
    def setUp(self):
        self.catalog, self.store, self.manifests = fixture()
        self.bucket = OfflineBucket(self.store)
        self.app = app_for(self.bucket, self.catalog)
        self.env = patch.dict('os.environ', {'WEATHER_OBJECT_PREFIX': 'pilot'})
        self.env.start()
        self.addCleanup(self.env.stop)

    def test_cold_icon_has_eight_storage_operations_and_no_cams_or_payload_reads(self):
        status, _, body = request(self.app)
        self.assertEqual(status, '200 OK')
        self.assertEqual(body, self.store.get('weather/v1/icon2i/latest.json').body)
        self.assertEqual(Counter(op for op, _ in self.bucket.calls),
                         {'metadata_read': 3, 'download': 3, 'metadata_list': 2})
        self.assertTrue(all('/icon2i/' in key for _, key in self.bucket.calls))
        self.assertFalse(any('/municipalities/' in key and op == 'download' for op, key in self.bucket.calls))
        for options in self.bucket.list_options:
            self.assertEqual(options['max_results'], 216)
            self.assertEqual(options['timeout'], 30)
            self.assertIsNone(options['retry'])

    def test_production_factory_reads_only_the_requested_product(self):
        client = Mock()
        client.bucket.return_value = self.bucket
        with patch.dict('os.environ', {'GOOGLE_CLOUD_PROJECT': cloud_reader.PROJECT}), \
                patch('cloud_reader.storage.Client', return_value=client) as factory:
            reader = build_reader()
            factory.assert_not_called()
            self.assertEqual(self.bucket.calls, [])
            self.assertEqual(reader.get('weather/v1/icon2i/latest.json').body,
                             self.store.get('weather/v1/icon2i/latest.json').body)
            factory.assert_called_once_with(project=cloud_reader.PROJECT)
            client.bucket.assert_called_once_with(cloud_reader.DATA_BUCKET)
            self.assertTrue(all('/icon2i/' in key for _, key in self.bucket.calls))
            # A later CAMS request opens its own reader, retaining the paired
            # core/pollen validation, without repeating ICON initialization.
            self.bucket.calls.clear()
            self.assertEqual(reader.get(FAMILY_LATEST_KEY).body,
                             self.store.get(FAMILY_LATEST_KEY).body)
            self.assertEqual(factory.call_count, 2)
            self.assertFalse(any('/icon2i/' in key for _, key in self.bucket.calls))

    def test_production_factory_serves_cams_when_icon_is_missing(self):
        del self.store.objects['weather/v1/icon2i/latest.json']
        client = Mock()
        client.bucket.return_value = self.bucket
        with patch.dict('os.environ', {'GOOGLE_CLOUD_PROJECT': cloud_reader.PROJECT}), \
                patch('cloud_reader.storage.Client', return_value=client):
            app = PilotApplication(build_reader)
            self.assertEqual(request(app, FAMILY_LATEST_KEY)[0], '200 OK')
            self.assertFalse(any('/icon2i/' in key for _, key in self.bucket.calls))
            self.assertEqual(request(app)[0], '503 Service Unavailable')
            self.assertEqual(request(app, FAMILY_LATEST_KEY)[0], '200 OK')

    def test_warm_pointer_needs_no_extra_io_and_single_payload_is_downloaded_on_demand(self):
        request(self.app)
        before = len(self.bucket.calls)
        request(self.app)
        self.assertEqual(len(self.bucket.calls), before)
        key = object_key(ICON_PROVIDER, self.manifests[ICON_PROVIDER, 2], self.catalog.istat_codes[0])
        self.assertEqual(request(self.app, key)[2], BODY)
        self.assertEqual(self.bucket.calls[before:], [('metadata_read', key), ('download', key)])

    def test_missing_or_mismatching_metadata_still_rejects_entire_run(self):
        key = object_key(ICON_PROVIDER, self.manifests[ICON_PROVIDER, 2], self.catalog.istat_codes[-1])
        del self.store.objects[key]
        self.assertEqual(request(self.app)[0], '503 Service Unavailable')
        self.store.put(key, b'[]', content_type='application/json')
        self.assertEqual(request(self.app)[0], '503 Service Unavailable')

    def test_broken_cams_does_not_block_icon_but_cams_remains_unavailable(self):
        del self.store.objects[FAMILY_LATEST_KEY]
        self.assertEqual(request(self.app, FAMILY_LATEST_KEY)[0], '503 Service Unavailable')
        self.assertEqual(request(self.app)[0], '200 OK')

    def test_cams_core_and_pollen_keep_one_verified_family(self):
        status, _, body = request(self.app, FAMILY_LATEST_KEY)
        self.assertEqual(status, '200 OK')
        self.assertEqual(body, self.store.get(FAMILY_LATEST_KEY).body)
        self.assertEqual(sum(op == 'metadata_list' for op, _ in self.bucket.calls), 4)
        self.assertFalse(any('/icon2i/' in key for _, key in self.bucket.calls))
        for provider in (CAMS_PROVIDER, CAMS_POLLEN_PROVIDER):
            key = object_key(provider, self.manifests[provider, 2], self.catalog.istat_codes[0])
            self.assertEqual(request(self.app, key)[2], BODY)
        self.assertEqual(len(self.app.reader.readers), 1)

    def test_bad_pollen_prevents_partial_cams_family_but_not_icon(self):
        key = object_key(CAMS_POLLEN_PROVIDER, self.manifests[CAMS_POLLEN_PROVIDER, 2], self.catalog.istat_codes[0])
        del self.store.objects[key]
        self.assertEqual(request(self.app, FAMILY_LATEST_KEY)[0], '503 Service Unavailable')
        self.assertEqual(request(self.app)[0], '200 OK')

    def test_http_bytes_gzip_etag_head_and_cors_unchanged(self):
        status, headers, body = request(self.app, HTTP_ACCEPT_ENCODING='gzip', HTTP_ORIGIN='https://localhost')
        self.assertEqual(status, '200 OK')
        self.assertEqual(gzip.decompress(body), self.store.get('weather/v1/icon2i/latest.json').body)
        self.assertEqual(headers['Access-Control-Allow-Origin'], 'https://localhost')
        self.assertEqual(request(self.app, HTTP_ACCEPT_ENCODING='gzip', HTTP_IF_NONE_MATCH=headers['ETag'])[0], '304 Not Modified')
        self.assertEqual(request(self.app, REQUEST_METHOD='HEAD')[2], b'')

    def test_cams_waiting_cannot_hold_icon_request(self):
        entered, release = Event(), Event()
        class Reader:
            def get(inner, key):
                return self.store.get(key)
        def factory(providers):
            if CAMS_PROVIDER in providers:
                entered.set()
                if not release.wait(5):
                    raise AssertionError('CAMS wait not released')
            return Reader()
        app = PilotApplication(lambda: ProviderScopedReader(factory))
        with ThreadPoolExecutor(max_workers=2) as pool:
            pending = pool.submit(request, app, FAMILY_LATEST_KEY)
            try:
                self.assertTrue(entered.wait(2))
                self.assertEqual(pool.submit(request, app).result(timeout=2)[0], '200 OK')
            finally:
                release.set()
            self.assertEqual(pending.result(timeout=2)[0], '200 OK')

    def test_invalid_path_never_starts_reader(self):
        self.assertEqual(request(self.app, 'state/private.json')[0], '400 Bad Request')
        self.assertEqual(self.bucket.calls, [])

    def test_unpublished_run_remains_hidden(self):
        key = object_key(ICON_PROVIDER, manifest(ICON_PROVIDER, utc(3), self.catalog), self.catalog.istat_codes[0])
        self.store.put(key, BODY, content_type='application/json')
        self.assertEqual(request(self.app, key)[0], '404 Not Found')

    def test_explicit_revocation_wins_after_pointer_cache_refresh(self):
        with patch('cloud_reader.monotonic', return_value=0):
            self.assertEqual(request(self.app)[0], '200 OK')
        key = 'weather/v1/icon2i/latest.json'
        revoked = build_latest_document(provider=ICON_PROVIDER, revision=3,
            published_at='2026-09-04T13:00:00Z', run_manifest=self.manifests[ICON_PROVIDER, 1],
            disabled_run_ids=[self.manifests[ICON_PROVIDER, 2]['source_run_id']], catalog=self.catalog)
        self.store.compare_and_swap(key, canonical_json_bytes(revoked),
            expected_etag=self.store.head(key).etag, content_type='application/json')
        revoked_key = object_key(ICON_PROVIDER, self.manifests[ICON_PROVIDER, 2], self.catalog.istat_codes[0])
        with patch('cloud_reader.monotonic', return_value=31):
            self.assertEqual(request(self.app)[2], canonical_json_bytes(revoked))
            self.assertEqual(request(self.app, revoked_key)[0], '404 Not Found')


class BatchMetadataTests(TestCase):
    def setUp(self):
        self.catalog, self.backing, self.manifests = fixture()
        self.bucket = OfflineBucket(self.backing)
        self.store = GCSObjectStore(self.bucket)
        self.keys = [object_key(ICON_PROVIDER, self.manifests[ICON_PROVIDER, 2], code) for code in self.catalog.istat_codes]
        env = patch.dict('os.environ', {'WEATHER_OBJECT_PREFIX': 'pilot'})
        env.start()
        self.addCleanup(env.stop)

    def test_same_metadata_as_individual_heads(self):
        batch = self.store.municipality_heads(self.keys)
        self.assertEqual(set(batch), set(self.keys))
        for key in self.keys:
            self.assertEqual(batch[key], self.store.head(key))

    def test_scope_is_restricted_before_storage(self):
        for keys in ([], self.keys + [self.keys[0]], [self.keys[0], self.keys[0]],
                     ['state/private.json'], [self.keys[0].replace('20260902', '20260901'), self.keys[1]]):
            with self.subTest(keys=keys[:2]), self.assertRaises(ValueError):
                self.store.municipality_heads(keys)
        self.assertEqual(self.bucket.calls, [])

    def test_incomplete_batch_rejected_and_not_cached(self):
        del self.backing.objects[self.keys[-1]]
        cache = CachedReadOnlyStore(self.store)
        with self.assertRaises(ObjectNotFound):
            cache.get(manifest_key(ICON_PROVIDER, self.manifests[ICON_PROVIDER, 2]))
        self.assertEqual(len(cache.heads), 0)
        self.assertEqual(len(cache.cache), 0)

    def test_page_error_is_sanitized_and_does_not_cache_partial_metadata(self):
        def broken(**kwargs):
            yield self.bucket.blob('pilot/' + self.keys[0]).load()
            raise TimeoutError('private transport URL/token')
        self.bucket.list_blobs = broken
        cache = CachedReadOnlyStore(self.store)
        with self.assertRaises(ObjectStoreError) as caught:
            cache.get(manifest_key(ICON_PROVIDER, self.manifests[ICON_PROVIDER, 2]))
        self.assertNotIn('private', str(caught.exception))
        self.assertEqual(len(cache.heads), 0)

    def test_invalid_hash_generation_size_and_duplicate_metadata_rejected(self):
        for attribute, bad_value in [('metadata', {'mf-sha256': 'invalid'}), ('generation', 0), ('size', -1)]:
            def broken(**kwargs):
                blob = self.bucket.blob('pilot/' + self.keys[0]).load()
                setattr(blob, attribute, bad_value)
                yield blob
            with self.subTest(attribute=attribute), patch.object(self.bucket, 'list_blobs', broken):
                with self.assertRaises(ObjectStoreError):
                    self.store.municipality_heads(self.keys)
        blob = self.bucket.blob('pilot/' + self.keys[0]).load()
        with patch.object(self.bucket, 'list_blobs', return_value=iter([blob, blob])):
            with self.assertRaises(ObjectStoreError):
                self.store.municipality_heads(self.keys)
