"""Google REST adapters. Construct only after explicit cloud opt-in.

WeatherData exposes GET/list only. State writes are restricted to exactly two
monitor objects. No provisioning, deletes, reader changes or acquisition APIs.
"""
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
import re
from urllib.parse import quote
from .collect import BudgetExpired, Object, Unavailable
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


class Transport:
    def __init__(self, session):
        self.session = session

    def request(self, method, url, budget, *, maximum=MAX_DOCUMENT, timeout_seconds=5, **kwargs):
        budget.remaining()
        try:
            response = self.session.request(method, url, timeout=budget.remaining(timeout_seconds),
                                            allow_redirects=False, stream=True, **kwargs)
            with response:
                chunks, count = [], 0
                for chunk in response.iter_content(65536):
                    budget.remaining()
                    count += len(chunk)
                    if count > maximum:
                        raise ValueError("response byte limit exceeded")
                    chunks.append(chunk)
                return response.status_code, b"".join(chunks), dict(response.headers)
        except (BudgetExpired, ValueError):
            raise
        except Exception as error:
            # Avoid leaking auth/header/url details from underlying exceptions.
            error_types = {cls.__name__ for cls in type(error).__mro__}
            failure_kind = ("timeout" if error_types & {"Timeout", "TimeoutError"}
                            else "connection" if "ConnectionError" in error_types
                            else "transport")
            raise Unavailable("transport request failed", transient=True,
                              failure_kind=failure_kind) from None

    def read_json(self, url, budget, **kwargs):
        status, body, _ = self.request("GET", url, budget, **kwargs)
        if status not in (200,):
            raise Unavailable("Google read HTTP " + str(status), transient=status in (408, 429) or status >= 500)
        return json.loads(body)


class PublicHTTP:
    def __init__(self, transport):
        self.transport = transport

    def get(self, url, headers, budget):
        # Public Cloud Run readers may need ~12 seconds for a cold start.
        # Google APIs keep 5 seconds; the 35s product/75s collection budgets
        # and the single retry still bound this read and persistent failures.
        status, body, response_headers = self.transport.request(
            "GET", url, budget, headers=headers, timeout_seconds=15)
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
    def __init__(self, transport):
        super().__init__(transport, STATE_BUCKET)

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
        status, response, _ = self.transport.request("POST", url, budget,
            params={"uploadType": "media", "name": self.key(product),
                    "ifGenerationMatch": str(generation)},
            headers={"Content-Type": "application/json"}, data=body)
        if status == 412:
            raise Conflict()
        if status not in (200, 201):
            raise Unavailable("monitor state commit uncertain")
        return str(json.loads(response)["generation"])


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


def transports():
    """No credentials, token refresh or network until cloud mode is opted into."""
    if os.environ.get("ICON2I_MONITOR_ALLOW_CLOUD") != "1":
        raise ValueError("cloud mode disabled")
    import google.auth
    from google.auth.transport.requests import AuthorizedSession
    import requests
    credentials, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
    authorized = AuthorizedSession(credentials, max_refresh_attempts=0, refresh_timeout=5)
    # Public readers must never receive Google credentials.
    return Transport(authorized), Transport(requests.Session())
