import hashlib
import json
from http import HTTPStatus
import unittest
from unittest.mock import Mock
from local_pipeline.gcs_object_store import GCSObjectStore, RemoteObjectStoreError
from local_pipeline.operational_diagnostics import error_fields
from local_pipeline.sqlite_object_store import ObjectStoreError, ObjectNotFound, PreconditionFailed


class GCSStoreTests(unittest.TestCase):
    def setUp(self):
        self.bucket = Mock()
        self.bucket.name = "meteofriul-pilot-weather"
        self.blob = self.bucket.blob.return_value
        self.blob.size = 2
        self.blob.generation = 17
        self.blob.content_type = "application/json"
        self.blob.metadata = {"mf-sha256": hashlib.sha256(b"{}").hexdigest()}
        self.store = GCSObjectStore(self.bucket)

    def test_create_only_and_cas(self):
        self.assertEqual(self.store.put("x", b"{}").etag, "17")
        self.assertEqual(self.blob.upload_from_string.call_args.kwargs["if_generation_match"], 0)
        self.store.compare_and_swap("x", b"{}", expected_etag="17")
        self.assertEqual(self.blob.upload_from_string.call_args.kwargs["if_generation_match"], 17)
        self.assertIsNone(self.blob.upload_from_string.call_args.kwargs["retry"])

    def test_get_pins_generation(self):
        self.blob.download_as_bytes.return_value = b"{}"
        self.assertEqual(self.store.get("x").body, b"{}")
        self.assertEqual(self.blob.download_as_bytes.call_args.kwargs["if_generation_match"], 17)

    def test_corruption_rejected(self):
        self.blob.download_as_bytes.return_value = b"[]"
        with self.assertRaises(ObjectStoreError):
            self.store.get("x")

    def test_wrong_bucket_rejected(self):
        self.bucket.name = "meteo-friul_cloudbuild"
        with self.assertRaises(ValueError):
            GCSObjectStore(self.bucket)

    def test_invalid_key_token_and_size(self):
        for key in ("../beta", "/x", "a//b"):
            with self.assertRaises(ValueError):
                self.store.put(key, b"{}")
        with self.assertRaises(ValueError):
            self.store.compare_and_swap("x", b"{}", expected_etag="*")
        self.store.max_bytes = 1
        with self.assertRaises(ValueError):
            self.store.put("x", b"{}")
        self.blob.upload_from_string.assert_not_called()

    def test_conflict_is_not_retried(self):
        error = Exception("secret")
        error.code = 412
        self.blob.upload_from_string.side_effect = error
        with self.assertRaises(PreconditionFailed) as caught:
            self.store.put("x", b"{}")
        self.assertNotIn("secret", str(caught.exception))
        self.blob.upload_from_string.assert_called_once()

    def test_typed_storage_failures_keep_safe_details_and_never_retry(self):
        key = "weather/v1/icon2i/runs/20260908T000000Z/municipalities/093033.json"
        for status, expected_type, retryable in (
            (404, ObjectNotFound, False), (412, PreconditionFailed, False),
            (408, RemoteObjectStoreError, True), (429, RemoteObjectStoreError, True),
            (500, RemoteObjectStoreError, True), (503, RemoteObjectStoreError, True),
            (401, RemoteObjectStoreError, False), (403, RemoteObjectStoreError, False),
        ):
            with self.subTest(status=status):
                self.blob.upload_from_string.reset_mock()
                error = Exception("GET https://host?X-Goog-Signature=secret Authorization: secret")
                error.code = HTTPStatus(status)
                self.blob.upload_from_string.side_effect = error
                with self.assertRaises(expected_type) as caught:
                    self.store.put(key, b"{}")
                fields = error_fields(caught.exception)
                self.assertEqual(fields["http_status"], status)
                self.assertEqual(fields["retryable"], retryable)
                self.assertEqual(fields["operation"], "upload")
                self.assertEqual(fields["http_method"], "POST")
                self.assertEqual(fields["object_key"], key)
                self.assertEqual(fields["municipality_code"], "093033")
                self.assertEqual(fields["source_run_id"], "20260908T000000Z")
                self.assertEqual(fields["cause_type"], "Exception")
                self.assertNotIn("secret", json.dumps(fields))
                self.assertNotIn("host", str(caught.exception))
                self.blob.upload_from_string.assert_called_once()
                self.assertIsNone(self.blob.upload_from_string.call_args.kwargs["retry"])

    def test_timeout_connection_and_nontransient_unknown_failures(self):
        for error, retryable in ((TimeoutError("secret"), True),
                                 (ConnectionError("secret"), True),
                                 (ValueError("secret"), False)):
            with self.subTest(error=type(error).__name__):
                self.blob.reload.side_effect = error
                with self.assertRaises(RemoteObjectStoreError) as caught:
                    self.store.head("weather/v1/icon2i/latest.json")
                fields = error_fields(caught.exception)
                self.assertEqual(fields["retryable"], retryable)
                self.assertEqual(fields["operation"], "metadata_read")
                self.assertEqual(fields["cause_type"], type(error).__name__)
                self.assertNotIn("http_status", fields)

    def test_response_status_and_static_call_compatibility(self):
        error = Exception("secret")
        error.response = Mock(status_code=503)
        operation = Mock(side_effect=error)
        with self.assertRaises(RemoteObjectStoreError) as caught:
            GCSObjectStore._call(operation)
        self.assertEqual(error_fields(caught.exception)["http_status"], 503)
        operation.assert_called_once_with(timeout=30, retry=None)

    def test_integrity_failure_keeps_the_object_key_without_payload(self):
        self.blob.download_as_bytes.return_value = b"[]"
        with self.assertRaises(ObjectStoreError) as caught:
            self.store.get("weather/v1/icon2i/runs/20260908T000000Z/municipalities/093033.json")
        fields = error_fields(caught.exception)
        self.assertEqual(fields["operation"], "verify_integrity")
        self.assertEqual(fields["municipality_code"], "093033")
        self.assertEqual(fields["error_summary"], "remote object integrity mismatch")


if __name__ == "__main__":
    unittest.main()
