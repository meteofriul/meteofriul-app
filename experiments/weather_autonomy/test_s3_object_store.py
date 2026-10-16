import io
import unittest
from unittest.mock import Mock

from local_pipeline.s3_object_store import S3ObjectStore
from local_pipeline.sqlite_object_store import ObjectStoreError, ObjectNotFound, PreconditionFailed


class RemoteError(Exception):
    def __init__(self, status):
        self.response = {"ResponseMetadata": {"HTTPStatusCode": status}}
        super().__init__("SECRET must not appear")


class S3StoreTests(unittest.TestCase):
    def setUp(self):
        self.client = Mock()
        self.client.put_object.return_value = {"ETag": '"remote-token"'}
        self.store = S3ObjectStore(self.client, bucket="meteofriul-pilot-weather")

    def test_immutable_create_and_opaque_cas(self):
        first = self.store.put("weather/v1/latest.json", b"{}")
        args = self.client.put_object.call_args.kwargs
        self.assertEqual(args["IfNoneMatch"], "*")
        self.assertEqual(args["Key"], "pilot/weather/v1/latest.json")
        self.assertEqual(first.etag, '"remote-token"')
        self.store.compare_and_swap("weather/v1/latest.json", b"[]", expected_etag=first.etag)
        args = self.client.put_object.call_args.kwargs
        self.assertEqual(args["IfMatch"], first.etag)
        self.assertNotIn("IfNoneMatch", args)

    def test_rejects_shared_bucket(self):
        with self.assertRaises(ValueError):
            S3ObjectStore(self.client, bucket="meteofriul-production")

    def test_invalid_paths_do_not_call_network(self):
        for key in ("../beta", "/weather", "a//b", "a/../b", "a?query", "a\\b"):
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.store.put(key, b"{}")
        self.client.put_object.assert_not_called()

    def test_byte_cap_before_upload(self):
        store = S3ObjectStore(self.client, bucket="meteofriul-pilot-weather", max_bytes=2)
        with self.assertRaises(ValueError):
            store.put("x", b"123")
        self.client.put_object.assert_not_called()

    def test_status_translation_no_secret_no_blind_retry(self):
        for status, error in ((404, ObjectNotFound), (412, PreconditionFailed), (500, ObjectStoreError)):
            self.client.put_object.reset_mock()
            self.client.put_object.side_effect = RemoteError(status)
            with self.assertRaises(error) as caught:
                self.store.put("x", b"{}")
            self.assertNotIn("SECRET", str(caught.exception))
            self.client.put_object.assert_called_once()

    def test_integrity_and_stream_closure(self):
        self.store.put("x", b"{}", metadata={"kind": "test"})
        args = self.client.put_object.call_args.kwargs
        for body, valid in ((b"{}", True), (b"[]", False), (b"{", False)):
            stream = io.BytesIO(body)
            self.client.get_object.return_value = {
                "Body": stream, "ETag": '"token"', "ContentLength": 2,
                "ContentType": args["ContentType"], "Metadata": args["Metadata"],
            }
            if valid:
                self.assertEqual(self.store.get("x").body, body)
            else:
                with self.assertRaises(ObjectStoreError):
                    self.store.get("x")
            self.assertTrue(stream.closed)

    def test_exists_does_not_hide_outage(self):
        self.client.head_object.side_effect = RemoteError(404)
        self.assertFalse(self.store.exists("x"))
        self.client.head_object.side_effect = RemoteError(503)
        with self.assertRaises(ObjectStoreError):
            self.store.exists("x")


if __name__ == "__main__":
    unittest.main()
