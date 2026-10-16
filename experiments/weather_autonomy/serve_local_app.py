"""Loopback-only snapshot bridge for the real app's explicit local-pilot mode.

Only the numeric weather source is replaced. Official alerts are read from the
ordinary local API; the app loads the OSMER bulletin on its own separate route.
No provider refresh, cloud write, publication, token, arbitrary proxy or
model-file route exists here.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
from functools import partial
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import tempfile
import threading
import time
from urllib.parse import parse_qs, urlsplit
import zipfile

import requests

PREFIX = "/__local-weather-pilot"
ROOT = Path(__file__).resolve().parent
UPSTREAM = "http://127.0.0.1:8002/api"
MAX_JSON = 4 * 1024 * 1024


def unavailable_alerts():
    return dict(active=False, count=0, alerts=[], source={"name": "Protezione Civile FVG"},
                source_mode="official_alerts_unavailable_fast_fallback", fetched_at=None,
                expires_at="", cache={"status": "unavailable"},
                error="official_alerts_unavailable",
                warning="Il servizio ufficiale non è raggiungibile: assenza di allerte non verificata.")


class OfficialReader:
    """Bounded anonymous GETs to the exact official-alert route only."""
    def __init__(self, get=None):
        self.cache = {}
        self.lock = threading.Lock()
        self.get = get or self._get

    @staticmethod
    def _get(url):
        with requests.Session() as session:
            session.trust_env = False
            with session.get(url, timeout=(1, 12), stream=True, allow_redirects=False) as response:
                if response.status_code != 200:
                    return None
                body = bytearray()
                for chunk in response.iter_content(64 * 1024):
                    body.extend(chunk)
                    if len(body) > MAX_JSON:
                        return None
                result = json.loads(body)
                return result if isinstance(result, dict) else None

    def read(self, kind, city):
        if kind != "official-alerts":
            raise ValueError("Unsupported official resource")
        key = (kind, "region")
        with self.lock:
            cached = self.cache.get(key)
            if cached and time.monotonic() < cached[0]:
                return deepcopy(cached[1])
        url = UPSTREAM + "/weather/" + kind
        try:
            value = self.get(url)
        except (requests.RequestException, ValueError, OSError):
            value = None
        with self.lock:
            self.cache[key] = (time.monotonic() + (300 if value else 20), deepcopy(value))
        return value


def merge_official(current, forecast, alerts):
    """Keep ICON/CAMS intact and attach only the separately fetched alerts."""
    current, forecast = deepcopy(current), deepcopy(forecast)
    current["official"] = None
    forecast["official"] = None
    forecast["osmer_structured"] = None
    for item in (current, forecast):
        item.setdefault("data_quality", {})["official_bulletin_status"] = "separate_app_route"
    return dict(city=current["city"], current=current, forecast=forecast,
                official_alerts=deepcopy(alerts) if isinstance(alerts, dict) else unavailable_alerts(),
                cache={"status": "local_snapshot", "mode": "local_archived_snapshot"})


def query_location(query):
    params = parse_qs(query, keep_blank_values=True, max_num_fields=8)
    if set(params) - {"city", "lat", "lon", "_"} or any(len(v) != 1 for v in params.values()):
        raise ValueError("Unsupported or duplicated query")
    city = params.get("city", [""])[0].strip()
    if not 1 <= len(city) <= 120:
        raise ValueError("Missing municipality")
    values = [float(params[k][0]) if k in params else None for k in ("lat", "lon")]
    for value, limit in zip(values, (90, 180)):
        if value is not None and not -limit <= value <= limit:
            raise ValueError("Invalid coordinate")
    return city, *values


class Handler(BaseHTTPRequestHandler):
    server_version = "MeteoFriulLocalApp/1"
    sys_version = ""

    def __init__(self, *args, adapter, official_reader, **kwargs):
        self.adapter, self.official_reader = adapter, official_reader
        super().__init__(*args, **kwargs)

    def log_message(self, *_args):
        pass  # Do not log user locations, URLs or arbitrary request strings.

    def reply(self, status, payload):
        body = json.dumps(payload, ensure_ascii=False, allow_nan=False, separators=(",", ":")).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store, private")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Cross-Origin-Resource-Policy", "same-origin")
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def do_GET(self):
        host = self.headers.get("Host", "")
        allowed_hosts = {f"127.0.0.1:{self.server.server_port}", f"localhost:{self.server.server_port}"}
        if host not in allowed_hosts or self.headers.get("Origin") not in (
            None, "http://127.0.0.1:5174", "http://localhost:5174", f"http://{host}",
        ):
            self.reply(403, {"error": "loopback_only"})
            return
        parsed = urlsplit(self.path)
        if parsed.path == PREFIX + "/status" and not parsed.query:
            self.reply(200, {"mode": "local_archived_snapshot", "automatic_refresh": False,
                             "numerical_provider": "ICON-2I + CAMS", "ordinary_api": UPSTREAM,
                             "official_sources": "unchanged_separate_service", "production": False})
            return
        if parsed.path not in (PREFIX + "/weather/bootstrap", PREFIX + "/weather/current"):
            self.reply(404, {"error": "not_found"})
            return
        try:
            city, lat, lon = query_location(parsed.query)
            current = self.adapter.current(city, lat, lon)
            if parsed.path.endswith("/current"):
                self.reply(200, current)
                return
            forecast = self.adapter.forecast(city, lat, lon)
            alerts = self.official_reader.read("official-alerts", current["city"])
            result = merge_official(current, forecast, alerts)
            self.reply(200, result)
        except (ValueError, KeyError, TypeError, RuntimeError):
            self.reply(503, {"error": "local_snapshot_unavailable_or_expired",
                             "message": "Snapshot locale non valido, scaduto o Comune non coperto. Nessun ripiego su Open-Meteo."})

    def unsupported(self):
        self.reply(405, {"error": "read_only"})
    do_POST = do_PUT = do_PATCH = do_DELETE = do_HEAD = do_OPTIONS = unsupported


def make_server(adapter, port=8780, official_reader=None):
    return ThreadingHTTPServer(("127.0.0.1", port), partial(Handler, adapter=adapter,
                                 official_reader=official_reader or OfficialReader()))


def read_icon_archive(archive_path):
    with zipfile.ZipFile(archive_path) as archive:
        entry = archive.getinfo("pilot.json")
        if not 1 <= entry.file_size <= 32 * 1024 * 1024:
            raise ValueError("ICON archive member size invalid")
        with archive.open(entry) as member:
            raw = member.read(32 * 1024 * 1024 + 1)
    expected = json.loads((ROOT / "icon2i_integrated_report_20260903.json").read_bytes())["payload_sha256"]
    if len(raw) != entry.file_size or hashlib.sha256(raw).hexdigest() != expected:
        raise ValueError("ICON archive integrity mismatch")
    return raw


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--icon", type=Path, help="Existing complete ICON JSON; default: verified archived pilot")
    parser.add_argument("--cams", type=Path, default=ROOT / "cams_fvg_payload_20260903.json")
    parser.add_argument("--port", type=int, default=8780)
    args = parser.parse_args()
    from local_app_adapter import LocalSnapshotAdapter
    # Only generated data in a new OS temporary directory; no archive extraction paths.
    with tempfile.TemporaryDirectory(prefix="meteofriul-local-app-") as scratch:
        icon_path = args.icon
        if icon_path is None:
            icon_path = Path(scratch) / "pilot.json"
            icon_path.write_bytes(read_icon_archive(ROOT / "icon2i_integrated_payload_20260903.zip"))
        adapter = LocalSnapshotAdapter(icon_path, args.cams)
        server = make_server(adapter, args.port)
        print(f"Local snapshot bridge: http://127.0.0.1:{server.server_port}{PREFIX}/status", flush=True)
        print("Read-only snapshots. Official sources remain on the ordinary local API. No provider refresh.", flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            server.server_close()


if __name__ == "__main__":
    main()
