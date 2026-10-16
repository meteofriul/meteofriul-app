"""Read-only, loopback-only diagnostic preview for an explicitly selected pilot JSON.

This server is deliberately independent from the application and never downloads,
publishes or rewrites weather data. Run with ``--payload /path/to/pilot.json``.
An optional ``--cams-payload`` exposes a separate, explicitly selected snapshot;
it never merges with or changes the archived ICON file.
"""

from __future__ import annotations

import argparse
from functools import partial
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
from typing import Any


HOST = "127.0.0.1"
DEFAULT_PORT = 8767
MAX_PAYLOAD_BYTES = 32 * 1024 * 1024
HTML_PATH = Path(__file__).with_name("pilot_preview.html")
CSP = (
    "default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; "
    "connect-src 'self'; img-src data:; base-uri 'none'; form-action 'none'; "
    "frame-ancestors 'none'"
)


def _reject_nonfinite(value: str) -> None:
    raise ValueError(f"Non-finite JSON number: {value}")


def read_payload(payload_path: Path, *, cams: bool = False) -> bytes:
    """Read one bounded, well-formed file; never resolve request paths on disk."""
    if not payload_path.is_file():
        raise ValueError("The selected payload is not a regular file")
    with payload_path.open("rb") as payload_file:
        content = payload_file.read(MAX_PAYLOAD_BYTES + 1)
    if len(content) > MAX_PAYLOAD_BYTES:
        raise ValueError("The selected payload exceeds the 32 MiB preview limit")
    data: Any = json.loads(content, parse_constant=_reject_nonfinite)
    if not isinstance(data, dict) or type(data.get("schema_version")) is not int:
        raise ValueError("Expected an object with an integer schema_version")
    if data["schema_version"] not in ((1, 2) if cams else (1,)):
        raise ValueError("Unsupported preview schema version")
    if cams:
        if not isinstance(data.get("variables"), list) or not isinstance(data.get("run_utc"), str):
            raise ValueError("Expected a CAMS snapshot with variables and run_utc")
        if data["schema_version"] == 2 and (
            not isinstance(data.get("cells"), list)
            or not isinstance(data.get("municipalities"), list)
            or not isinstance(data.get("times_utc"), list)
        ):
            raise ValueError("Expected regional CAMS cells, municipalities and times_utc")
    elif not isinstance(data.get("municipalities"), list):
        raise ValueError("Expected pilot schema_version 1 and a municipalities array")
    return content


class PilotHandler(BaseHTTPRequestHandler):
    """Serve fixed resources, with no directory listing or CORS access."""

    server_version = "MeteoFriulPilot/1"
    sys_version = ""

    def __init__(self, *args: Any, payload_path: Path, cams_payload_path: Path | None = None, **kwargs: Any) -> None:
        self.payload_path = payload_path
        self.cams_payload_path = cams_payload_path
        super().__init__(*args, **kwargs)

    def _reply(self, status: int, content: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy", CSP)
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Cross-Origin-Resource-Policy", "same-origin")
        self.send_header("Cross-Origin-Opener-Policy", "same-origin")
        if status == 405:
            self.send_header("Allow", "GET")
        self.end_headers()
        if self.command != "HEAD" and status != 204:
            self.wfile.write(content)

    def _request_is_local(self) -> bool:
        port = self.server.server_port
        allowed = {f"127.0.0.1:{port}", f"localhost:{port}"}
        if port == 80:
            allowed.update({"127.0.0.1", "localhost"})
        host = self.headers.get("Host", "").lower()
        origin = self.headers.get("Origin")
        return host in allowed and (origin is None or origin == f"http://{host}")

    def do_GET(self) -> None:
        if not self._request_is_local():
            self._reply(403, b"Local preview only\n", "text/plain; charset=utf-8")
            return
        if self.path == "/":
            try:
                content = HTML_PATH.read_bytes()
            except OSError:
                self._reply(503, b"Preview unavailable\n", "text/plain; charset=utf-8")
                return
            self._reply(200, content, "text/html; charset=utf-8")
        elif self.path == "/pilot.json":
            try:
                content = read_payload(self.payload_path)
            except (OSError, ValueError, UnicodeError):
                self._reply(503, b"Pilot payload unavailable or invalid\n", "text/plain; charset=utf-8")
                return
            self._reply(200, content, "application/json; charset=utf-8")
        elif self.path == "/cams.json":
            if self.cams_payload_path is None:
                self._reply(204, b"", "application/json; charset=utf-8")
                return
            try:
                content = read_payload(self.cams_payload_path, cams=True)
            except (OSError, ValueError, UnicodeError):
                self._reply(503, b"CAMS payload unavailable or invalid\n", "text/plain; charset=utf-8")
                return
            self._reply(200, content, "application/json; charset=utf-8")
        elif self.path == "/favicon.ico":
            self._reply(204, b"", "image/x-icon")
        else:
            self._reply(404, b"Not found\n", "text/plain; charset=utf-8")

    def _unsupported(self) -> None:
        self._reply(405, b"Only GET is supported\n", "text/plain; charset=utf-8")

    do_HEAD = _unsupported
    do_POST = _unsupported
    do_PUT = _unsupported
    do_PATCH = _unsupported
    do_DELETE = _unsupported
    do_OPTIONS = _unsupported
    do_TRACE = _unsupported
    do_CONNECT = _unsupported


def make_server(payload_path: Path, port: int = DEFAULT_PORT, cams_payload_path: Path | None = None) -> ThreadingHTTPServer:
    if type(port) is not int or not 0 <= port <= 65535:
        raise ValueError("Port must be an integer between 0 and 65535")
    selected_path = payload_path.expanduser().resolve(strict=True)
    read_payload(selected_path)
    selected_cams_path = None
    if cams_payload_path is not None:
        selected_cams_path = cams_payload_path.expanduser().resolve(strict=True)
        if selected_cams_path == selected_path:
            raise ValueError("ICON and CAMS must be separate snapshot files")
        read_payload(selected_cams_path, cams=True)
    if not HTML_PATH.is_file():
        raise ValueError("The diagnostic HTML is missing")
    return ThreadingHTTPServer(
        (HOST, port), partial(PilotHandler, payload_path=selected_path, cams_payload_path=selected_cams_path)
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--payload", required=True, type=Path, help="Explicit pilot JSON file")
    parser.add_argument("--cams-payload", type=Path, help="Optional separate CAMS diagnostic JSON file")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    args = parser.parse_args()
    try:
        server = make_server(args.payload, args.port, args.cams_payload)
    except (OSError, ValueError) as error:
        parser.error(str(error))
    print(f"Local diagnostic preview: http://{HOST}:{server.server_port}/", flush=True)
    print("Read-only pilot; the application and external services are unchanged.", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
