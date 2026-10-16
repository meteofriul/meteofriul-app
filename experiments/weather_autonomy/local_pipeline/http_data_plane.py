"""Loopback-only, read-only HTTP view of the simulated SQLite object store."""

from __future__ import annotations

from functools import partial
import gzip
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import re
from typing import Iterable
from urllib.parse import urlsplit

from .object_store_ports import ObjectReader
from .sqlite_object_store import ObjectNotFound, ObjectStoreError


DEFAULT_ALLOWED_ORIGINS = frozenset(
    {
        "http://127.0.0.1:5174",
        "http://localhost:5174",
        "https://localhost",
    }
)
DEFAULT_MAX_RESPONSE_BYTES = 16 * 1024 * 1024
LATEST_CACHE_CONTROL = "public, max-age=30, must-revalidate"
IMMUTABLE_CACHE_CONTROL = "public, max-age=31536000, immutable"
_ALLOWED_PROVIDERS = frozenset({"icon2i", "cams_europe", "cams_europe_pollen"})
_ICON_LATEST_KEY = "weather/v1/icon2i/latest.json"
_CAMS_FAMILY_LATEST_KEY = "weather/v1/families/cams/latest.json"
_RUN_ID = re.compile(r"^\d{8}T\d{6}Z$")
_ISTAT_CODE = re.compile(r"^\d{6}$")


def _canonical_error(error: str) -> bytes:
    return json.dumps(
        {"error": error},
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _normalize_origins(origins: Iterable[str]) -> frozenset[str]:
    normalized: set[str] = set()
    for raw_origin in origins:
        origin = str(raw_origin or "").strip().rstrip("/")
        parsed = urlsplit(origin)
        if (
            parsed.scheme not in {"http", "https"}
            or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}
            or parsed.username
            or parsed.password
            or parsed.path
            or parsed.query
            or parsed.fragment
            or "*" in origin
        ):
            raise ValueError(f"allowed origin must be an exact loopback origin: {raw_origin}")
        normalized.add(origin)
    if not normalized:
        raise ValueError("at least one explicit loopback CORS origin is required")
    return frozenset(normalized)


def _accepts_gzip(value: str | None) -> bool:
    explicit: bool | None = None
    wildcard: bool | None = None
    for raw_item in str(value or "").split(","):
        fields = [field.strip() for field in raw_item.split(";")]
        coding = fields[0].lower()
        if not coding:
            continue
        quality = 1.0
        for parameter in fields[1:]:
            if parameter.lower().startswith("q="):
                try:
                    quality = float(parameter[2:])
                except ValueError:
                    quality = 0.0
        accepted = quality > 0
        if coding == "gzip":
            explicit = accepted
        elif coding == "*":
            wildcard = accepted
    return explicit if explicit is not None else bool(wildcard)


def _gzip_deterministic(body: bytes) -> bytes:
    return gzip.compress(body, compresslevel=6, mtime=0)


def _weak_etag_value(value: str) -> str:
    candidate = value.strip()
    if candidate[:2].lower() == "w/":
        candidate = candidate[2:].strip()
    return candidate


def _if_none_match_matches(header: str | None, etag: str) -> bool:
    if not header:
        return False
    expected = _weak_etag_value(etag)
    for candidate in header.split(","):
        candidate = candidate.strip()
        if candidate == "*" or _weak_etag_value(candidate) == expected:
            return True
    return False


def _request_object_key(raw_target: str) -> str:
    parsed = urlsplit(raw_target)
    if parsed.scheme or parsed.netloc or parsed.query or parsed.fragment:
        raise ValueError("query_or_absolute_target_not_allowed")
    path = parsed.path
    if "%" in path or "\\" in path or "//" in path or not path.startswith("/"):
        raise ValueError("encoded_or_ambiguous_path_not_allowed")
    segments = path[1:].split("/")
    if len(segments) < 4 or segments[:2] != ["weather", "v1"]:
        raise ValueError("object_path_not_allowed")

    is_cams_family_latest = (
        len(segments) == 5
        and segments[2:4] == ["families", "cams"]
        and segments[4] == "latest.json"
    )
    is_cams_family_release = (
        len(segments) == 7
        and segments[2:5] == ["families", "cams", "runs"]
        and _RUN_ID.fullmatch(segments[5]) is not None
        and segments[6] == "release.json"
    )
    if is_cams_family_latest or is_cams_family_release:
        return "/".join(segments)

    provider = segments[2]
    if provider not in _ALLOWED_PROVIDERS:
        raise ValueError("object_path_not_allowed")

    # CAMS core and pollen become visible only through the single family
    # pointer above.  Authorizing either legacy provider pointer would let a
    # client reconstruct a mixed pair from two independently changing files.
    is_latest = (
        provider == "icon2i"
        and len(segments) == 4
        and segments[3] == "latest.json"
    )
    is_manifest = (
        len(segments) == 6
        and segments[3] == "runs"
        and _RUN_ID.fullmatch(segments[4]) is not None
        and segments[5] == "manifest.json"
    )
    is_municipality = (
        len(segments) == 7
        and segments[3] == "runs"
        and _RUN_ID.fullmatch(segments[4]) is not None
        and segments[5] == "municipalities"
        and segments[6].endswith(".json")
        and _ISTAT_CODE.fullmatch(segments[6][:-5]) is not None
    )
    if not (is_latest or is_manifest or is_municipality):
        raise ValueError("object_path_not_allowed")
    return "/".join(segments)


class ReadOnlyDataPlaneHandler(BaseHTTPRequestHandler):
    server_version = "MeteoFriulLocalDataPlane/1"
    sys_version = ""

    def __init__(
        self,
        *args,
        object_store: ObjectReader,
        allowed_origins: frozenset[str],
        max_response_bytes: int,
        **kwargs,
    ) -> None:
        self.object_store = object_store
        self.allowed_origins = allowed_origins
        self.max_response_bytes = max_response_bytes
        super().__init__(*args, **kwargs)

    def log_message(self, _format: str, *_args: object) -> None:
        pass  # Object keys and request headers are intentionally not logged.

    def _host_allowed(self) -> bool:
        port = int(self.server.server_port)
        allowed = {
            f"127.0.0.1:{port}",
            f"localhost:{port}",
            f"[::1]:{port}",
        }
        if port in {80, 443}:
            allowed.update({"127.0.0.1", "localhost", "[::1]"})
        return self.headers.get("Host", "").strip().lower() in allowed

    def _request_origin(self) -> tuple[str | None, bool]:
        raw_origin = self.headers.get("Origin")
        if raw_origin is None:
            return None, True
        origin = raw_origin.strip().rstrip("/")
        return origin, origin in self.allowed_origins

    def _base_headers(self, origin: str | None = None) -> None:
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Vary", "Origin, Accept-Encoding")
        if origin is not None:
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Access-Control-Expose-Headers", "ETag")

    def _error(self, status: int, code: str, *, origin: str | None = None) -> None:
        body = _canonical_error(code)
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self._base_headers(origin)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _authorize_request(self) -> tuple[str | None, bool]:
        if not self._host_allowed():
            self._error(403, "host_not_allowed")
            return None, False
        origin, origin_allowed = self._request_origin()
        if not origin_allowed:
            self._error(403, "origin_not_allowed")
            return None, False
        return origin, True

    def _serve_object(self, *, include_body: bool) -> None:
        origin, authorized = self._authorize_request()
        if not authorized:
            return
        try:
            object_key = _request_object_key(self.path)
        except ValueError as error:
            self._error(400, str(error), origin=origin)
            return
        try:
            head = self.object_store.head(object_key)
        except ObjectNotFound:
            self._error(404, "object_not_found", origin=origin)
            return
        except ObjectStoreError:
            self._error(503, "object_store_unavailable", origin=origin)
            return
        if head.byte_length > self.max_response_bytes:
            self._error(413, "response_limit_exceeded", origin=origin)
            return
        try:
            stored = self.object_store.get(object_key)
        except ObjectNotFound:
            self._error(404, "object_not_found", origin=origin)
            return
        except ObjectStoreError:
            self._error(503, "object_store_unavailable", origin=origin)
            return
        if stored.byte_length > self.max_response_bytes:
            self._error(413, "response_limit_exceeded", origin=origin)
            return

        use_gzip = _accepts_gzip(self.headers.get("Accept-Encoding"))
        response_body = _gzip_deterministic(stored.body) if use_gzip else stored.body
        if len(response_body) > self.max_response_bytes:
            self._error(413, "response_limit_exceeded", origin=origin)
            return
        etag = stored.etag
        if use_gzip:
            # Encoding-specific strong ETags avoid treating distinct wire bytes
            # as the same representation while Vary protects shared caches.
            import hashlib

            etag = '"gzip-sha256-' + hashlib.sha256(response_body).hexdigest() + '"'
        cache_control = (
            LATEST_CACHE_CONTROL
            if object_key in {_ICON_LATEST_KEY, _CAMS_FAMILY_LATEST_KEY}
            else IMMUTABLE_CACHE_CONTROL
        )
        if _if_none_match_matches(self.headers.get("If-None-Match"), etag):
            self.send_response(304)
            self.send_header("ETag", etag)
            self.send_header("Cache-Control", cache_control)
            self._base_headers(origin)
            self.end_headers()
            return

        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(response_body)))
        self.send_header("Cache-Control", cache_control)
        self.send_header("ETag", etag)
        if use_gzip:
            self.send_header("Content-Encoding", "gzip")
        self._base_headers(origin)
        self.end_headers()
        if include_body:
            self.wfile.write(response_body)

    def do_GET(self) -> None:
        self._serve_object(include_body=True)

    def do_HEAD(self) -> None:
        self._serve_object(include_body=False)

    def do_OPTIONS(self) -> None:
        origin, authorized = self._authorize_request()
        if not authorized:
            return
        try:
            _request_object_key(self.path)
        except ValueError as error:
            self._error(400, str(error), origin=origin)
            return
        requested_method = self.headers.get("Access-Control-Request-Method", "").upper()
        if origin is None or requested_method not in {"GET", "HEAD"}:
            self._error(403, "cors_preflight_not_allowed", origin=origin)
            return
        requested_headers = {
            item.strip().lower()
            for item in self.headers.get("Access-Control-Request-Headers", "").split(",")
            if item.strip()
        }
        if requested_headers - {"if-none-match"}:
            self._error(403, "cors_headers_not_allowed", origin=origin)
            return
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", origin)
        self.send_header("Access-Control-Allow-Methods", "GET, HEAD, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "If-None-Match")
        self.send_header("Access-Control-Max-Age", "600")
        self.send_header("Cache-Control", "no-store")
        self._base_headers()
        self.end_headers()

    def _method_not_allowed(self) -> None:
        origin, authorized = self._authorize_request()
        if not authorized:
            return
        self.close_connection = True
        body = _canonical_error("read_only")
        self.send_response(405)
        self.send_header("Allow", "GET, HEAD, OPTIONS")
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self._base_headers(origin)
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(body)

    do_POST = _method_not_allowed
    do_PUT = _method_not_allowed
    do_PATCH = _method_not_allowed
    do_DELETE = _method_not_allowed


def make_server(
    object_store: ObjectReader,
    *,
    port: int = 0,
    allowed_origins: Iterable[str] = DEFAULT_ALLOWED_ORIGINS,
    max_response_bytes: int = DEFAULT_MAX_RESPONSE_BYTES,
) -> ThreadingHTTPServer:
    """Create an IPv4 loopback server; no public bind option is exposed."""

    if not isinstance(port, int) or isinstance(port, bool) or not 0 <= port <= 65535:
        raise ValueError("port must be between 0 and 65535")
    if (
        not isinstance(max_response_bytes, int)
        or isinstance(max_response_bytes, bool)
        or max_response_bytes < 1
    ):
        raise ValueError("max_response_bytes must be a positive integer")
    origins = _normalize_origins(allowed_origins)
    handler = partial(
        ReadOnlyDataPlaneHandler,
        object_store=object_store,
        allowed_origins=origins,
        max_response_bytes=max_response_bytes,
    )
    server = ThreadingHTTPServer(("127.0.0.1", port), handler)
    server.daemon_threads = True
    return server


__all__ = [
    "DEFAULT_ALLOWED_ORIGINS",
    "DEFAULT_MAX_RESPONSE_BYTES",
    "IMMUTABLE_CACHE_CONTROL",
    "LATEST_CACHE_CONTROL",
    "ReadOnlyDataPlaneHandler",
    "make_server",
]
