"""Conditional S3/R2 storage port. No provisioning, deletes or blind overwrites.

The caller supplies a scoped SDK client with bounded timeouts/retries. Remote
ETags are opaque CAS tokens, never content hashes. Deployment requires real
provider contract tests; offline tests alone do not authorize activation.
"""
import hashlib
import re

from .sqlite_object_store import (
    ObjectHead, StoredObject, ObjectStoreError, ObjectNotFound,
    PreconditionFailed, _canonical_metadata, _body_bytes,
)


class S3ObjectStore:
    def __init__(self, client, *, bucket, prefix="pilot/", max_bytes=16 * 1024**2):
        if not re.fullmatch(r"meteofriul-pilot-[a-z0-9-]+", bucket):
            raise ValueError("dedicated pilot bucket required")
        if prefix != "pilot/" or not 0 < max_bytes <= 16 * 1024**2:
            raise ValueError("invalid pilot storage limits")
        self.client, self.bucket, self.prefix = client, bucket, prefix
        self.max_bytes = max_bytes

    def _key(self, key):
        if not isinstance(key, str) or not re.fullmatch(r"[A-Za-z0-9_./-]+", key):
            raise ValueError("invalid object key")
        if any(part in {"", ".", ".."} for part in key.split("/")):
            raise ValueError("invalid object path")
        return self.prefix + key

    def _call(self, operation, key, **kwargs):
        try:
            return getattr(self.client, operation)(Bucket=self.bucket, Key=self._key(key), **kwargs)
        except Exception as exc:
            response = getattr(exc, "response", {})
            status = response.get("ResponseMetadata", {}).get("HTTPStatusCode")
            if status == 404:
                raise ObjectNotFound(key) from None
            if status == 412:
                raise PreconditionFailed(key) from None
            # Do not leak signed URLs, credentials or SDK diagnostics.
            raise ObjectStoreError("remote object operation failed") from None

    def _head(self, key, response):
        size = response.get("ContentLength")
        metadata = dict(response.get("Metadata") or {})
        sha = metadata.pop("mf-sha256", "")
        etag = response.get("ETag")
        if (type(size) is not int or not 0 <= size <= self.max_bytes
                or not re.fullmatch(r"[a-f0-9]{64}", sha)
                or not isinstance(etag, str) or not etag
                or any(ord(c) < 32 for c in etag)):
            raise ObjectStoreError("invalid remote object envelope")
        return ObjectHead(key, size, sha, etag,
                          response.get("ContentType", "application/octet-stream"), metadata)

    def head(self, key):
        return self._head(key, self._call("head_object", key))

    def get(self, key):
        response = self._call("get_object", key)
        stream = response["Body"]
        try:
            head = self._head(key, response)
            body = stream.read(self.max_bytes + 1)
            if len(body) != head.byte_length or hashlib.sha256(body).hexdigest() != head.sha256:
                raise ObjectStoreError("remote object integrity mismatch")
            return StoredObject(body, head)
        finally:
            stream.close()

    def exists(self, key):
        try:
            self.head(key)
            return True
        except ObjectNotFound:
            return False

    def put(self, key, body, *, content_type="application/octet-stream", metadata=None):
        return self.compare_and_swap(key, body, expected_etag=None,
                                     content_type=content_type, metadata=metadata)

    def compare_and_swap(self, key, body, *, expected_etag,
                         content_type="application/octet-stream", metadata=None):
        self._key(key)
        body = _body_bytes(body)
        if len(body) > self.max_bytes:
            raise ValueError("object exceeds pilot byte cap")
        if not isinstance(content_type, str) or not content_type or any(ord(c) < 32 for c in content_type):
            raise ValueError("invalid content type")
        normalized, _ = _canonical_metadata(metadata)
        if any(k != k.lower() or k == "mf-sha256" for k in normalized):
            raise ValueError("metadata keys must be lowercase and not reserved")
        if expected_etag is not None and (not isinstance(expected_etag, str)
                or not expected_etag or any(ord(c) < 32 for c in expected_etag)):
            raise ValueError("invalid CAS token")
        digest = hashlib.sha256(body).hexdigest()
        condition = {"IfNoneMatch": "*"} if expected_etag is None else {"IfMatch": expected_etag}
        response = self._call("put_object", key, Body=body, ContentType=content_type,
                              Metadata={**normalized, "mf-sha256": digest}, **condition)
        return self._head(key, {**response, "ContentLength": len(body),
                              "ContentType": content_type,
                              "Metadata": {**normalized, "mf-sha256": digest}})
