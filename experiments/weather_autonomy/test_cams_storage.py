import hashlib
import json
import ssl
from contextlib import redirect_stdout
from io import StringIO
from unittest import TestCase
from unittest.mock import Mock, patch
from urllib.error import URLError

from requests.exceptions import SSLError as RequestsSSL
from urllib3.exceptions import MaxRetryError, SSLError as PoolSSL

from cams_storage import CamsObjectStore, CamsReadRecovery, tls_failure_kind
from cloud_worker import _cams_failure
from local_pipeline.gcs_object_store import GCSObjectStore, RemoteObjectStoreError
from local_pipeline.operational_diagnostics import error_fields
from local_pipeline.sqlite_object_store import ObjectStoreError, PreconditionFailed


def wrapped(error):
    return RequestsSSL(MaxRetryError(None, 'https://private?token=secret', PoolSSL(error)))


class CamsStorageTests(TestCase):
    def setUp(self):
        self.elapsed = 0
        self.pauses = []
        def wait(seconds):
            self.pauses.append(seconds)
            self.elapsed += seconds
        self.recovery = CamsReadRecovery(clock=lambda: self.elapsed, wait=wait)
        self.bucket = Mock(name='bucket')
        self.bucket.name = 'meteofriul-pilot-weather'
        self.blob = self.bucket.blob.return_value
        self.blob.size = 2
        self.blob.generation = 17
        self.blob.content_type = 'application/json'
        self.blob.metadata = {'mf-sha256': hashlib.sha256(b'{}').hexdigest()}
        self.blob.download_as_bytes.return_value = b'{}'
        self.store = CamsObjectStore(self.bucket, recovery=self.recovery)
        self.logs = StringIO()
        self.redirect = redirect_stdout(self.logs)
        self.redirect.__enter__()
        self.addCleanup(self.redirect.__exit__, None, None, None)

    def test_interrupted_download_recovers_same_generation_without_reloading(self):
        self.blob.download_as_bytes.side_effect = [wrapped(ssl.SSLEOFError(8, 'secret')), b'{}']
        self.assertEqual(self.store.get('weather/v1/cams_europe/runs/20261026T000000Z/municipalities/093033.json').body, b'{}')
        self.blob.reload.assert_called_once()
        self.assertEqual(self.pauses, [1])
        for call in self.blob.download_as_bytes.call_args_list:
            self.assertEqual(call.kwargs['if_generation_match'], 17)
            self.assertIsNone(call.kwargs['retry'])
            self.assertEqual(call.kwargs['timeout'], 30)
        self.assertIn('tls_connection_interrupted', self.logs.getvalue())
        self.assertNotIn('secret', self.logs.getvalue())
        self.assertNotIn('https://', self.logs.getvalue())

    def test_two_retries_shared_across_stores_not_per_object(self):
        self.blob.reload.side_effect = [ConnectionError(), None, ConnectionError(), None, ConnectionError()]
        other = CamsObjectStore(self.bucket, recovery=self.recovery)
        self.store.head('a')
        other.head('b')
        with self.assertRaises(RemoteObjectStoreError):
            self.store.head('c')
        self.assertEqual(self.blob.reload.call_count, 5)
        self.assertEqual(self.pauses, [1, 2])

    def test_certificate_and_unclassified_tls_never_retry(self):
        for inner, kind in ((ssl.SSLCertVerificationError(1, 'secret'), 'tls_certificate_invalid'),
                            (ssl.SSLError(1, 'secret'), 'tls_unclassified')):
            with self.subTest(kind=kind):
                self.blob.reload.reset_mock()
                self.blob.reload.side_effect = wrapped(inner)
                with self.assertRaises(RemoteObjectStoreError) as caught:
                    self.store.head('a')
                fields = error_fields(caught.exception)
                self.assertEqual(fields['transport_reason'], kind)
                self.assertFalse(fields['retryable'])
                result = _cams_failure(caught.exception)
                self.assertEqual(result['status'], 'manual_review')
                self.assertNotIn('secret', json.dumps(result))
                self.blob.reload.assert_called_once()
        self.assertEqual(self.pauses, [])

    def test_public_https_certificate_not_mistaken_for_retryable_url_error(self):
        result = _cams_failure(URLError(ssl.SSLCertVerificationError(1, 'secret')))
        self.assertEqual(result['reason_code'], 'tls_certificate_invalid')
        self.assertFalse(result['retryable'])
        self.assertEqual(_cams_failure(URLError(ssl.SSLEOFError(8, 'secret')))['status'], 'retryable_failure')

    def test_certificate_dominates_eof_and_cycles_are_bounded(self):
        error = ssl.SSLEOFError(8, 'secret')
        error.__cause__ = ssl.SSLCertVerificationError(1, 'secret')
        error.__cause__.__cause__ = error
        self.assertEqual(tls_failure_kind(error), 'tls_certificate_invalid')

    def test_retry_is_not_started_without_time_for_a_read(self):
        self.elapsed = 870
        self.blob.reload.side_effect = TimeoutError()
        with self.assertRaises(RemoteObjectStoreError):
            self.store.head('a')
        self.blob.reload.assert_called_once()
        self.assertEqual(self.pauses, [])

    def test_upload_never_repeated_even_on_transient_tls_failure(self):
        self.blob.upload_from_string.side_effect = wrapped(ssl.SSLEOFError(8, 'secret'))
        with self.assertRaises(RemoteObjectStoreError):
            self.store.put('a', b'{}')
        self.blob.upload_from_string.assert_called_once()
        self.assertEqual(self.pauses, [])

    def test_conflict_integrity_and_access_errors_never_retried(self):
        for code in (401, 403, 412):
            error = Exception('secret')
            error.code = code
            self.blob.reload.reset_mock()
            self.blob.reload.side_effect = error
            with self.subTest(code=code), self.assertRaises(ObjectStoreError):
                self.store.get('a')
            self.blob.reload.assert_called_once()
        self.blob.reload.side_effect = None
        self.blob.download_as_bytes.return_value = b'[]'
        with self.assertRaises(ObjectStoreError):
            self.store.get('a')
        self.assertEqual(self.pauses, [])

    def test_other_services_keep_single_attempt(self):
        self.blob.reload.side_effect = TimeoutError()
        with self.assertRaises(RemoteObjectStoreError):
            GCSObjectStore(self.bucket).head('a')
        self.blob.reload.assert_called_once()
        self.assertEqual(self.pauses, [])

    def test_worker_uses_cams_store_only_for_cams(self):
        import cloud_worker
        with patch('cloud_worker.storage.Client') as client, patch('cloud_worker._run_icon') as icon, \
             patch('cloud_worker._run_cams') as cams:
            client.return_value.bucket.return_value = self.bucket
            cloud_worker._run('icon')
            self.assertIs(type(icon.call_args.args[0]), GCSObjectStore)
            cloud_worker._run('cams')
            state, data, _ = cams.call_args.args
            self.assertIsInstance(data, CamsObjectStore)
            self.assertIs(data.recovery, state.recovery)
