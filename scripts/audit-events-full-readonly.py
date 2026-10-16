"""Run the full Events collection against a local catalog, without cloud writes.

The collector still reads the public event sites. Its Storage client is an
in-memory stand-in, so the published catalog is written only to --output.
"""

import argparse
import json
from pathlib import Path

from app.events.pilot_catalog import PILOT_PROJECT
from app.events.pilot_cloud import BUCKET, KEY, publish


class MemoryBlob:
    def __init__(self, previous):
        self.content = json.dumps(previous, ensure_ascii=False).encode("utf-8")
        self.generation = 1
        self.size = len(self.content)
        self.saved = False

    def reload(self, *, timeout):
        return None

    def download_as_bytes(self, *, if_generation_match, timeout):
        if if_generation_match != self.generation:
            raise ValueError("catalog generation changed")
        return self.content

    def upload_from_string(self, data, *, content_type, if_generation_match,
                           timeout):
        if if_generation_match != self.generation or content_type != "application/json":
            raise ValueError("invalid in-memory catalog write")
        self.content = data
        self.size = len(data)
        self.saved = True
        self.generation += 1


class MemoryClient:
    project = PILOT_PROJECT

    def __init__(self, previous):
        self._blob = MemoryBlob(previous)

    def bucket(self, name):
        return self

    def blob(self, name):
        return self._blob


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--previous", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--retry-failed", action="store_true", help="Retry only failed sources from the local input")
    options = parser.parse_args()
    if PILOT_PROJECT != "meteo-friul":
        parser.error("set EVENTS_CLOUD_PROJECT=meteo-friul for this audit")
    if BUCKET != "meteo-friul-weather-data" or KEY != "pilot/events/v1/catalog.json":
        parser.error("set the production EVENTS_DATA_BUCKET and EVENTS_CATALOG_KEY")
    if options.previous.resolve() == options.output.resolve():
        parser.error("--output must differ from --previous")
    previous = json.loads(options.previous.read_text(encoding="utf-8"))
    if previous.get("schema") != "pilot-events-v1":
        parser.error("unexpected previous catalog schema")
    client = MemoryClient(previous)
    print(json.dumps({
        "event_readonly_audit_start": {
            "project": PILOT_PROJECT,
            "previous": str(options.previous),
            "output": str(options.output),
            "sources": len(previous.get("sources", {})),
        }
    }), flush=True)
    failure = None
    try:
        publish(client, project=PILOT_PROJECT, retry_failed=options.retry_failed)
    except Exception as exc:
        failure = f"{type(exc).__name__}: {exc}"
    if not client._blob.saved:
        raise RuntimeError(failure or "collector did not save a catalog")
    options.output.write_bytes(client._blob.content)
    catalog = json.loads(client._blob.content)
    summary = {
        "result": "failed" if failure else "succeeded",
        "error": failure,
        "attempted_at": catalog.get("attempted_at"),
        "sources": {
            name: {
                "status": batch.get("status"),
                "events": len(batch.get("events", [])),
                "review": len(batch.get("review_required", [])),
                "error_type": batch.get("last_attempt_error_type"),
            }
            for name, batch in catalog.get("sources", {}).items()
        },
        "monitors": catalog.get("monitors", {}),
        "output": str(options.output),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2), flush=True)
    if failure:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
