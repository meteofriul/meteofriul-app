"""Google REST adapters. Construct only after explicit cloud opt-in.

WeatherData exposes GET/list only. State writes are restricted to exactly two
monitor objects. No provisioning, deletes, reader changes or acquisition APIs.
"""
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
import re
import time
from urllib.parse import quote
from .collect import BudgetExpired, Object, Unavailable
from .http import Transport, PUBLIC_DOCUMENT_BYTES, PUBLIC_TIMEOUT_SECONDS, API_TIMEOUT_SECONDS
from .contracts import MAX_DOCUMENT, ROOTS
from .core import METRIC_PREFIX, METRICS, PRODUCTS, instant, stamp
from .runner import Conflict, Rejected

PROJECT = "meteo-friul"
REGION = "europe-west1"
DATA_BUCKET = "meteo-friul-weather-data"
STATE_BUCKET = "meteo-friul-weather-state"
STATE_PREFIX = "monitoring/icon2i-freshness/v1/"
STORAGE = "https://storage.googleapis.com/storage/v1/b/"
MONITORING = "https://monitoring.googleapis.com/v3/projects/" + PROJECT


def json_bytes(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


class PublicHTTP:
    def __init__(self, transport, *, timeout_seconds=PUBLIC_TIMEOUT_SECONDS):
        self.transport, self.timeout_seconds = transport, timeout_seconds

    def get(self, url, headers, budget):
        # Absolute request deadline, including startup and cancellation. Public
        # pointer/resolver JSON gets a smaller byte cap than manifests and lists.
        status, body, response_headers = self.transport.request(
            "GET", url, budget, headers=headers, timeout_seconds=self.timeout_seconds,
            maximum=PUBLIC_DOCUMENT_BYTES)
        if status in (408, 429) or status >= 500:
            raise Unavailable("reader HTTP " + str(status), transient=True,
                              failure_kind="http_status")
        # Only safe, useful headers are logged.
        allowed = {"cache-control", "age", "etag", "content-type", "content-encoding", "vary"}
        return {"status": status, "body": body,
                "headers": {k.lower(): v for k, v in response_headers.items() if k.lower() in allowed}}


class BucketReader:
    def __init__(self, transport, bucket):
        self.transport, self.bucket = transport, bucket

    def url(self, key):
        return STORAGE + self.bucket + "/o/" + quote(key, safe="")

    def meta(self, key, budget):
        meta = self.transport.read_json(self.url(key), budget)
        if (not isinstance(meta, dict) or not re.fullmatch(r"[1-9][0-9]*", str(meta.get("generation", "")))
                or not re.fullmatch(r"0|[1-9][0-9]*", str(meta.get("size", "")))):
            raise ValueError("invalid Storage generation/size")
        instant(meta["timeCreated"])
        return meta

    def head(self, key, budget):
        meta = self.meta(key, budget)
        return Object(b"", str(meta["generation"]), meta["timeCreated"], int(meta["size"]))

    def get(self, key, budget):
        meta = self.meta(key, budget)
        if int(meta["size"]) > MAX_DOCUMENT:
            raise ValueError("stored document byte limit")
        status, body, _ = self.transport.request("GET", self.url(key), budget,
            params={"alt": "media", "generation": str(meta["generation"])})
        if status != 200:
            raise Unavailable("Storage download HTTP " + str(status),
                              transient=status in (408, 412, 429) or status >= 500)
        if len(body) != int(meta["size"]):
            raise ValueError("stored size mismatch")
        digest = meta.get("metadata", {}).get("mf-sha256")
        if digest and hashlib.sha256(body).hexdigest() != digest:
            raise ValueError("stored hash mismatch")
        return Object(body, str(meta["generation"]), meta["timeCreated"], len(body))


class WeatherData(BucketReader):
    def __init__(self, transport):
        super().__init__(transport, DATA_BUCKET)

    def url(self, key):
        if not any(key.startswith(root) for root in ROOTS.values()) or ".." in key:
            raise ValueError("weather key outside monitor scope")
        return super().url(key)

    def list(self, prefix, budget):
        self.url(prefix)  # Scope guard before network access.
        result, token = {}, None
        for _ in range(10):
            params = {"prefix": prefix, "maxResults": 1000, "fields": "items(name,size),nextPageToken"}
            if token:
                params["pageToken"] = token
            page = self.transport.read_json(STORAGE + self.bucket + "/o", budget, params=params)
            for item in page.get("items", []):
                result[item["name"]] = int(item["size"])
            token = page.get("nextPageToken")
            if not token:
                return result
        raise ValueError("object listing page budget exceeded")


class MonitorState(BucketReader):
    def __init__(self, transport, *, sleep=time.sleep):
        super().__init__(transport, STATE_BUCKET)
        self.sleep = sleep

    @staticmethod
    def key(product):
        if product not in PRODUCTS:
            raise ValueError("unknown product")
        return STATE_PREFIX + product + ".json"

    def read(self, product, budget):
        key = self.key(product)
        status, meta_body, _ = self.transport.request("GET", self.url(key), budget)
        if status == 404:
            return "0", None
        if status != 200:
            raise Unavailable("monitor state metadata unavailable")
        meta = json.loads(meta_body)
        status, body, _ = self.transport.request("GET", self.url(key), budget,
            params={"alt": "media", "generation": str(meta["generation"])})
        if status != 200:
            raise Unavailable("monitor state body unavailable")
        return str(meta["generation"]), json.loads(body)

    def cas(self, product, generation, value, budget):
        if not re.fullmatch(r"0|[1-9][0-9]*", str(generation)):
            raise ValueError("invalid state generation")
        body = json_bytes(value)
        if len(body) > MAX_DOCUMENT:
            raise ValueError("state byte limit")
        url = "https://storage.googleapis.com/upload/storage/v1/b/" + STATE_BUCKET + "/o"
        # Every retry keeps the original generation precondition and bytes.
        # A lost response may hide a successful commit: reconcile before retrying.
        for attempt in range(3):
            budget.remaining()
            try:
                status, response, _ = self.transport.request("POST", url, budget,
                    params={"uploadType": "media", "name": self.key(product),
                            "ifGenerationMatch": str(generation)},
                    headers={"Content-Type": "application/json"}, data=body)
            except Unavailable as error:
                if not error.transient:
                    raise
                failure = error
            else:
                if status == 412:
                    raise Conflict()
                if status in (200, 201):
                    return str(json.loads(response)["generation"])
                failure = Unavailable("monitor state commit HTTP " + str(status),
                    transient=status in (408, 429) or 500 <= status < 600,
                    failure_kind="http_status")
                if not failure.transient:
                    raise failure
            current_generation, current = self.read(product, budget)
            if current_generation != str(generation):
                if current == value:
                    return current_generation
                raise Conflict()
            if attempt == 2:
                raise failure
            # Storage may throttle rapid writes to the same object. Wait only
            # within the existing job budget; no unbounded or blind retry.
            delay = 2 ** attempt
            if budget.remaining(delay + 1) <= delay:
                raise BudgetExpired()
            self.sleep(delay)
        raise AssertionError("unreachable state retry")


class Metrics:
    def __init__(self, transport):
        self.transport = transport

    @staticmethod
    def identity(product, metric):
        if product not in PRODUCTS or metric not in METRICS:
            raise ValueError("metric outside monitor scope")
        return {"type": METRIC_PREFIX + metric, "labels": {"product": product}}

    def latest(self, product, metric, timestamp, budget):
        identity = self.identity(product, metric)
        query = ('metric.type="' + identity["type"] + '" AND metric.labels.product="' + product
                 + '" AND resource.type="global" AND resource.labels.project_id="' + PROJECT + '"')
        # Include exact timestamp and any newer point. API returns newest first.
        result = self.transport.read_json(MONITORING + "/timeSeries", budget, params={
            "filter": query, "interval.startTime": stamp(instant(timestamp) - timedelta(seconds=1)),
            "interval.endTime": stamp(datetime.now(timezone.utc)),
            "view": "FULL", "pageSize": 1})
        series = result.get("timeSeries", [])
        points = [point for item in series for point in item.get("points", [])]
        if not points:
            return None
        point = max(points, key=lambda p: instant(p["interval"]["endTime"]))
        return point["interval"]["endTime"], int(point["value"]["int64Value"])

    def write(self, product, metric, timestamp, value, budget):
        identity = self.identity(product, metric)
        if type(value) is not int:
            raise ValueError("INT64 required")
        series = {"metric": identity, "resource": {"type": "global", "labels": {"project_id": PROJECT}},
                  "metricKind": "GAUGE", "valueType": "INT64",
                  "points": [{"interval": {"endTime": timestamp}, "value": {"int64Value": str(value)}}]}
        status, _, _ = self.transport.request("POST", MONITORING + "/timeSeries", budget,
            json={"timeSeries": [series]})
        if status in (400, 403, 404, 429):
            raise Rejected()
        if status != 200:
            raise Unavailable("Monitoring write outcome uncertain")


def transports(*, api_timeout_seconds=API_TIMEOUT_SECONDS):
    """Lazy isolated sessions: all credential discovery/network has a deadline."""
    if os.environ.get("ICON2I_MONITOR_ALLOW_CLOUD") != "1":
        raise ValueError("cloud mode disabled")
    return (Transport("authorized", timeout_seconds=api_timeout_seconds),
            Transport("public", timeout_seconds=api_timeout_seconds))
