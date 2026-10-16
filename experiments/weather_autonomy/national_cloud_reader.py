"""Read-only WSGI entrypoint for the separate pilot-national-weather service."""
from datetime import datetime, timezone
import gzip
import hashlib
import os
import re
from threading import RLock
from time import monotonic
from urllib.parse import urlsplit

from national_cloud_assets import PROJECT, load_catalog
from national_cloud_publication import (PREFIX, read_pointer,
    require_current_coverage, verify_pointer_reader)
from national_cloud_lazy_reader import NationalLazyRun
from local_pipeline.sqlite_object_store import ObjectNotFound, ObjectStoreError
from serve_national_bundle_v2 import (_parse_resolve_query, _parse_search_query,
    _accepts_gzip, _if_none_match_matches, ResolutionError)

PUBLIC_HOST = os.environ.get("WEATHER_PUBLIC_HOST", "pilot-national-weather-335641913741.europe-west1.run.app")
DATA_BUCKET = os.environ.get("WEATHER_DATA_BUCKET", PROJECT + "-data")
ORIGINS = frozenset({"https://localhost", "http://localhost",
    "http://127.0.0.1:5174", "http://localhost:5174",
    "https://meteofriul.app", "https://www.meteofriul.app"})
IMMUTABLE_PATH = re.compile(r"^runs/(\d{8}T\d{6}Z)/(?:manifest\.json|municipality-index\.json|blocks/t\d{7}-y\d{4}-x\d{4}\.json)$")


def route(target):
    if not isinstance(target, str) or len(target) > 2048:
        raise ValueError("invalid_path")
    parsed = urlsplit(target)
    path = parsed.path
    if (parsed.scheme or parsed.netloc or parsed.fragment or "%" in path
            or "\\" in path or "//" in path or not path.startswith("/" + PREFIX)):
        raise ValueError("invalid_path")
    relative = path[len(PREFIX) + 1:]
    if relative == "resolve.json":
        return "resolve", _parse_resolve_query(parsed.query)
    if relative == "search.json":
        return "search", _parse_search_query(parsed.query)
    if parsed.query or not (relative == "pilot.json" or IMMUTABLE_PATH.fullmatch(relative)):
        raise ValueError("invalid_path")
    return "document", relative


class NationalReadPlane:
    """One current and one previous verified snapshot, refreshed atomically."""
    def __init__(self, store, catalog, *, clock=monotonic, now=None):
        self.store, self.catalog = store, catalog
        self.clock = clock
        self.now = now or (lambda: datetime.now(timezone.utc))
        self.lock = RLock()
        self.pointer = self.reader = self.previous_reader = None
        self.refresh_at = 0

    def current(self, *, fresh=True):
        with self.lock:
            if self.pointer is None or self.clock() >= self.refresh_at:
                pointer, _etag = read_pointer(self.store, self.catalog)
                if self.pointer is None or pointer != self.pointer:
                    candidate = NationalLazyRun(self.store, self.catalog, pointer["manifest"])
                    verify_pointer_reader(pointer, candidate)
                    self.previous_reader = self.reader
                    self.reader, self.pointer = candidate, pointer
                self.refresh_at = self.clock() + 30
            if fresh:
                require_current_coverage(self.reader.manifest, self.now())
            return self.reader

    def document(self, path):
        with self.lock:
            reader = self.current(fresh=path == "pilot.json")
            body = reader.document(path)
            if body is not None:
                return body
            previous = self.pointer["previous"]
            match = IMMUTABLE_PATH.fullmatch(path)
            if previous is None or not match or match[1] != previous["source_run_id"]:
                raise ObjectNotFound(path)
            if self.previous_reader is None or self.previous_reader.source_run_id != match[1]:
                self.previous_reader = NationalLazyRun(self.store, self.catalog, previous["manifest"])
            body = self.previous_reader.document(path)
            if body is None:
                raise ObjectNotFound(path)
            return body


def build_reader():
    # Validate target before importing a cloud library or opening ADC credentials.
    if os.environ.get("GOOGLE_CLOUD_PROJECT") != PROJECT:
        raise ValueError("exclusive national weather project required")
    from google.cloud import storage
    from local_pipeline.gcs_object_store import GCSObjectStore
    return NationalReadPlane(GCSObjectStore(storage.Client(project=PROJECT).bucket(DATA_BUCKET)), load_catalog())


class NationalApplication:
    def __init__(self, factory=build_reader):
        self.factory, self.plane, self.lock = factory, None, RLock()

    def __call__(self, env, respond):
        method = env.get("REQUEST_METHOD", "")
        origin = env.get("HTTP_ORIGIN")
        headers = [("X-Content-Type-Options", "nosniff"), ("Vary", "Origin, Accept-Encoding")]
        if origin in ORIGINS:
            headers.extend([("Access-Control-Allow-Origin", origin), ("Access-Control-Expose-Headers", "ETag")])
        def answer(status, body, extra=()):
            respond(status, headers + [("Content-Type", "application/json; charset=utf-8"),
                ("Content-Length", str(len(body))), *extra])
            return [] if method == "HEAD" else [body]
        def error(status, code):
            return answer(status, ('{"error":"' + code + '"}').encode(), [("Cache-Control", "no-store")])
        if origin and origin not in ORIGINS:
            return error("403 Forbidden", "origin_not_allowed")
        if method not in {"GET", "HEAD", "OPTIONS"}:
            return error("405 Method Not Allowed", "method_not_allowed")
        host = env.get("HTTP_HOST", "").lower()
        if host not in {PUBLIC_HOST, PUBLIC_HOST + ":443", "localhost:8080", "127.0.0.1:8080"}:
            return error("403 Forbidden", "host_not_allowed")
        path, query = env.get("PATH_INFO", ""), env.get("QUERY_STRING", "")
        if path == "/healthz" and not query and method in {"GET", "HEAD"}:
            return answer("200 OK", b'{"service":"pilot-national-weather","experimental":true}', [("Cache-Control", "no-store")])
        target = env.get("RAW_URI", path + ("?" + query if query else ""))
        try:
            kind, value = route(target)
        except (TypeError, ValueError):
            return error("400 Bad Request", "invalid_path_or_query")
        if method == "OPTIONS":
            requested = {v.strip().lower() for v in env.get("HTTP_ACCESS_CONTROL_REQUEST_HEADERS", "").split(",") if v.strip()}
            if not origin or env.get("HTTP_ACCESS_CONTROL_REQUEST_METHOD") not in {"GET", "HEAD"} or requested - {"if-none-match"}:
                return error("403 Forbidden", "cors_preflight_not_allowed")
            return answer("204 No Content", b"", [("Cache-Control", "no-store"),
                ("Access-Control-Allow-Methods", "GET, HEAD, OPTIONS"), ("Access-Control-Allow-Headers", "If-None-Match")])
        try:
            with self.lock:
                if self.plane is None:
                    self.plane = self.factory()
            if kind == "resolve":
                body = self.plane.current().resolve(**value)
            elif kind == "search":
                body = self.plane.current().search(value)
            else:
                body = self.plane.document(value)
        except ResolutionError as exc:
            return error("409 Conflict" if exc.code == "municipality_ambiguous" else "404 Not Found", exc.code)
        except ObjectNotFound:
            return error("404 Not Found", "not_published")
        except (ObjectStoreError, ValueError):
            return error("503 Service Unavailable", "national_data_unavailable")
        cache = "public, max-age=31536000, immutable" if kind == "document" and value != "pilot.json" else "no-store"
        extra = [("Cache-Control", cache)]
        if _accepts_gzip(env.get("HTTP_ACCEPT_ENCODING")):
            body = gzip.compress(body, compresslevel=6, mtime=0)
            extra.append(("Content-Encoding", "gzip"))
        etag = '"' + hashlib.sha256(body).hexdigest() + '"'
        extra.append(("ETag", etag))
        if _if_none_match_matches(env.get("HTTP_IF_NONE_MATCH"), etag):
            respond("304 Not Modified", headers + extra)
            return []
        return answer("200 OK", body, extra)


application = NationalApplication()
