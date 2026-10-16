"""Serve a collected Events candidate on loopback; never read or write Cloud Storage."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
from wsgiref.simple_server import make_server

from app.events import pilot_http


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", type=Path, required=True)
    options = parser.parse_args()
    raw = options.catalog.read_bytes()
    catalog = json.loads(raw)
    if catalog.get("schema") != "pilot-events-v1":
        parser.error("unexpected catalog schema")
    root = Path(__file__).resolve().parent.parent
    candidate = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    identity = {"service": "local-events-candidate", "commit": candidate,
                "catalog_sha256": hashlib.sha256(raw).hexdigest(),
                "snapshot": catalog.get("attempted_at"), "published": False}
    # Only the data loader is replaced; routing, filters, detail and pagination
    # run through the candidate's real production API implementation.
    pilot_http.load_catalog = lambda: catalog

    def application(environ, start_response):
        if environ.get("PATH_INFO") == "/health":
            start_response("200 OK", [("Content-Type", "application/json"), ("Cache-Control", "no-store")])
            return [json.dumps(identity).encode("utf-8")]
        return pilot_http.application(environ, start_response)

    print(json.dumps(identity), flush=True)
    with make_server("127.0.0.1", 8784, application) as server:
        server.serve_forever()


if __name__ == "__main__":
    main()
