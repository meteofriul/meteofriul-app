from unittest import TestCase
from unittest.mock import Mock, patch
import os
from cloud_reader import PilotApplication, build_reader, CachedReadOnlyStore
from local_pipeline.sqlite_object_store import ObjectNotFound

class ReaderTests(TestCase):
    def request(self, app, **env):
        result = []
        body = b''.join(app({'REQUEST_METHOD': 'GET', 'PATH_INFO': '/weather/v1/icon2i/latest.json', **env}, lambda s,h: result.append((s,h))))
        return result[0][0], body

    def test_beta_rejected_before_client(self):
        with patch.dict(os.environ, {'GOOGLE_CLOUD_PROJECT': 'meteo-friul'}), patch('cloud_reader.storage.Client') as client:
            with self.assertRaises(ValueError): build_reader()
            client.assert_not_called()

    def test_invalid_requests_do_not_open_storage(self):
        factory = Mock()
        app = PilotApplication(factory)
        for env, status in [({'REQUEST_METHOD':'POST'}, '405'), ({'PATH_INFO':'/state/ads/key'}, '400'), ({'HTTP_ORIGIN':'https://evil.example'}, '403'), ({'QUERY_STRING':'a=1'}, '400'), ({'RAW_URI':'/weather/v1/%69con2i/latest.json'}, '400')]:
            self.assertTrue(self.request(app, **env)[0].startswith(status))
        factory.assert_not_called()

    def test_only_verified_reader_is_used(self):
        reader = Mock()
        reader.get.side_effect = ObjectNotFound('private')
        self.assertEqual(self.request(PilotApplication(lambda: reader))[0], '404 Not Found')

    def test_cache_read_only_and_bounded_refresh(self):
        source = Mock()
        source.get.return_value = Mock(size=2)
        cache = CachedReadOnlyStore(source)
        with patch('cloud_reader.monotonic', side_effect=[0, 1, 31]):
            cache.get('x/latest.json'); cache.get('x/latest.json'); cache.get('x/latest.json')
        self.assertEqual(source.get.call_count, 2)
        self.assertFalse(hasattr(cache, 'put'))
