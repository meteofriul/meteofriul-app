"""Google Cloud Storage port for the isolated weather data plane.

No provisioning or unconditional writes. Object generation is the opaque CAS
token. Reads are pinned to that generation to avoid mixing bytes and metadata.
"""
import hashlib
import os
import re

from .operational_diagnostics import attach_error_fields, safe_object_key
from .sqlite_object_store import (
    ObjectHead, StoredObject, ObjectStoreError, ObjectNotFound,
    PreconditionFailed, _canonical_metadata, _body_bytes,
)


class RemoteObjectStoreError(ObjectStoreError):
    """Storage failure whose safe HTTP/type/context survives classification."""

    def __init__(self, summary, *, original_type, http_status=None,
                 operation=None, object_key=None, retryable=False):
        super().__init__(summary)
        self.retryable = bool(retryable)
        attach_error_fields(self, error_type=original_type, http_status=http_status,
                            operation=operation, http_method=_http_method(operation), object_key=object_key,
                            retryable=self.retryable, error_summary=summary,
                            **_object_context(object_key))


def _http_method(operation):
    return {"metadata_read": "GET", "metadata_list": "GET", "download": "GET", "upload": "POST"}.get(operation)


def _object_context(key):
    key = safe_object_key(key)
    if key is None:
        return {}
    fields = {}
    municipality = re.search(r"(?:^|/)municipalities/(\d{6})\.json$", key)
    if municipality:
        fields["municipality_code"] = municipality.group(1)
    run = re.search(r"(?:^|/)runs/(\d{8}T\d{6}Z)(?:/|$)", key)
    if run:
        fields["source_run_id"] = run.group(1)
    return fields


def _http_status(error):
    status = getattr(error, "code", None)
    if not isinstance(status, int) or isinstance(status, bool):
        status = getattr(getattr(error, "response", None), "status_code", None)
    return int(status) if isinstance(status, int) and not isinstance(status, bool) and 100 <= status <= 599 else None


def _transport_failure(error):
    if isinstance(error, (TimeoutError, ConnectionError)):
        return True
    # Do not treat arbitrary OSError/programming exceptions as transient.
    return any(
        cls.__module__.startswith(("requests.exceptions", "urllib3.exceptions", "google.auth.exceptions"))
        and cls.__name__ in {"Timeout", "ConnectTimeout", "ReadTimeout", "ConnectionError", "TransportError", "ProtocolError"}
        for cls in type(error).__mro__
    )


class GCSObjectStore:
    def __init__(self, bucket, *, max_bytes=16 * 1024**2):
        allowed_buckets = {
            value for value in (
                os.environ.get("WEATHER_DATA_BUCKET"),
                os.environ.get("WEATHER_STATE_BUCKET"),
            ) if value
        }
        legacy_pilot_bucket = re.fullmatch(r"meteofriul-pilot-[a-z0-9-]+", bucket.name)
        if bucket.name not in allowed_buckets and legacy_pilot_bucket is None:
            raise ValueError("dedicated weather bucket required")
        if type(max_bytes) is not int or not 0 < max_bytes <= 16 * 1024**2:
            raise ValueError("invalid object limit")
        self.bucket, self.max_bytes = bucket, max_bytes

    def _blob(self, key):
        if not isinstance(key, str) or not re.fullmatch(r"[A-Za-z0-9_./-]+", key):
            raise ValueError("invalid object key")
        if any(p in {"", ".", ".."} for p in key.split("/")):
            raise ValueError("invalid object path")
        prefix = os.environ.get("WEATHER_OBJECT_PREFIX", "pilot").strip("/")
        if not prefix or not re.fullmatch(r"[A-Za-z0-9_-]+", prefix):
            raise ValueError("invalid weather object prefix")
        return self.bucket.blob(prefix + "/" + key)

    @staticmethod
    def _call(operation, *, _operation=None, _key=None, **kwargs):
        try:
            return operation(timeout=30, retry=None, **kwargs)
        except Exception as exc:
            status = _http_status(exc)
            fields = {"error_type": type(exc).__name__, "http_status": status,
                      "operation": _operation, "http_method": _http_method(_operation),
                      "object_key": _key, **_object_context(_key)}
            if status == 404:
                raise attach_error_fields(ObjectNotFound("remote object not found"),
                                          **fields, retryable=False,
                                          error_summary="storage object not found") from None
            if status == 412:
                raise attach_error_fields(PreconditionFailed("remote object"),
                                          **fields, retryable=False,
                                          error_summary="storage generation precondition failed") from None
            transport = _transport_failure(exc)
            retryable = status in {408, 429} or (status is not None and 500 <= status <= 599) or transport
            summary = (
                "storage request timed out" if status == 408 or isinstance(exc, TimeoutError)
                else "storage request was throttled" if status == 429
                else "storage service temporarily unavailable" if status is not None and 500 <= status <= 599
                else "storage transport failed" if transport
                else "storage authentication failed" if status == 401
                else "storage access denied" if status == 403
                else "storage request failed"
            )
            raise RemoteObjectStoreError(summary, original_type=type(exc).__name__,
                                         http_status=status, operation=_operation,
                                         object_key=_key, retryable=retryable) from None

    def _head(self, key, blob):
        metadata = dict(blob.metadata or {})
        digest = metadata.pop("mf-sha256", "")
        # gcloud storage rsync adds this transport-only timestamp while
        # preserving application metadata. It is not part of any weather
        # contract and must not alter verified object identity after migration.
        metadata.pop("goog-reserved-file-mtime", None)
        generation = str(blob.generation)
        if (type(blob.size) is not int or not 0 <= blob.size <= self.max_bytes
                or not re.fullmatch(r"[a-f0-9]{64}", digest)
                or not re.fullmatch(r"[1-9][0-9]*", generation)):
            raise attach_error_fields(ObjectStoreError("invalid remote object metadata"),
                                      operation="verify_metadata", object_key=key,
                                      **_object_context(key))
        return ObjectHead(key, blob.size, digest, generation,
                          blob.content_type or "application/octet-stream", metadata)

    def head(self, key):
        blob = self._blob(key)
        self._call(blob.reload, _operation="metadata_read", _key=key)
        return self._head(key, blob)

    def municipality_heads(self, keys):
        """Read one immutable run's municipality metadata, never its payloads.

        Listing returns the same size/hash/generation metadata as individual
        reloads. Every requested object must be present and validated before
        any result is returned. No partial list authorizes a published run.
        """
        keys = tuple(keys)
        if not 1 <= len(keys) <= 215 or len(set(keys)) != len(keys):
            raise ValueError("invalid municipality metadata batch")
        pattern = r"weather/v1/(?:icon2i|cams_europe|cams_europe_pollen)/runs/\d{8}T\d{6}Z/municipalities/\d{6}\.json"
        if any(not isinstance(key, str) or not re.fullmatch(pattern, key) for key in keys):
            raise ValueError("invalid municipality metadata key")
        parents = {key.rsplit("/", 1)[0] for key in keys}
        if len(parents) != 1:
            raise ValueError("municipality metadata batch spans runs")
        names = {self._blob(key).name: key for key in keys}
        prefix = next(iter(names)).rsplit("/", 1)[0] + "/"

        def read(*, timeout, retry):
            # Consume the lazy iterator inside _call so page errors are also
            # classified/sanitized. Bound unexpected objects, not just pages.
            result = {}
            for blob in self.bucket.list_blobs(prefix=prefix, page_size=256,
                                                max_results=216, timeout=timeout, retry=retry):
                key = names.get(blob.name)
                if key is not None:
                    if key in result:
                        raise ObjectStoreError("duplicate municipality metadata")
                    result[key] = self._head(key, blob)
            return result

        result = self._call(read, _operation="metadata_list", _key=keys[0])
        if set(result) != set(keys):
            raise ObjectNotFound("incomplete municipality metadata batch")
        return result

    def get(self, key):
        blob = self._blob(key)
        self._call(blob.reload, _operation="metadata_read", _key=key)
        head = self._head(key, blob)
        body = self._call(blob.download_as_bytes, _operation="download", _key=key, if_generation_match=int(head.etag),
                          start=0, end=self.max_bytes, raw_download=True)
        if len(body) != head.size or hashlib.sha256(body).hexdigest() != head.sha256:
            raise attach_error_fields(ObjectStoreError("remote object integrity mismatch"),
                                      operation="verify_integrity", object_key=key,
                                      **_object_context(key))
        return StoredObject(body, head)

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
        blob = self._blob(key)
        body = _body_bytes(body)
        if len(body) > self.max_bytes:
            raise ValueError("object exceeds pilot limit")
        if not isinstance(content_type, str) or not content_type or any(ord(c) < 32 for c in content_type):
            raise ValueError("invalid content type")
        if expected_etag is not None and (not isinstance(expected_etag, str)
                or not re.fullmatch(r"[1-9][0-9]*", expected_etag)):
            raise ValueError("invalid generation token")
        normalized, _ = _canonical_metadata(metadata)
        if "mf-sha256" in normalized:
            raise ValueError("reserved integrity metadata")
        blob.metadata = {**normalized, "mf-sha256": hashlib.sha256(body).hexdigest()}
        self._call(blob.upload_from_string, _operation="upload", _key=key, data=body, content_type=content_type,
                   if_generation_match=0 if expected_etag is None else int(expected_etag))
        # SDK populates size/generation from this write response, not a later HEAD.
        return self._head(key, blob)
