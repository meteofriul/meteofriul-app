"""Run the full Events collection against a local catalog, without cloud writes.

The collector still reads the public event sites. Its Storage client is an
in-memory stand-in, so the published catalog is written only to --output.
"""

import argparse
import json
from pathlib import Path

from app.events.pilot_catalog import PILOT_PROJECT
from app.events.pilot_cloud import BUCKET, CONTROLS_KEY, KEY, publish
from app.events.source_controls import decode_controls, empty_controls


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

    def __init__(self, previous, controls):
        self._blob = MemoryBlob(previous)
        self._controls_blob = MemoryBlob(controls)

    def bucket(self, name):
        return self

    def blob(self, name):
        if name == KEY:
            return self._blob
        if name == CONTROLS_KEY:
            return self._controls_blob
        raise ValueError("unexpected audit object key")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--previous", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--controls", type=Path,
                        help="Local copy of the source controls used by the job")
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
    controls = decode_controls(options.controls.read_bytes()) if options.controls else empty_controls()
    client = MemoryClient(previous, controls)
    print(json.dumps({
        "event_readonly_audit_start": {
            "project": PILOT_PROJECT,
            "previous": str(options.previous),
            "output": str(options.output),
            "sources": len(previous.get("sources", {})),
            "controls_revision": controls["revision"],
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
        "paused_sources": catalog.get("paused_sources", []),
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
