"""Read-only real-source probe. No Firestore or published cache writes."""
import json
from datetime import datetime, timezone
from .pilot_catalog import PILOT_PROJECT, query_catalog
from .pilot_collection import collect


def tourism_udine():
    from . import engine
    from .source_pipeline import normalize_visible_event
    events = engine.fetch_turismofvg_events("Udine", 100, 46.0711, 13.2346, strict=True)
    normalized = []
    for event in events:
        lat, lon = engine.event_location_coordinates(event)
        normalized.append({**normalize_visible_event(event), "lat": lat, "lon": lon})
    return {"status": "ok", "events": normalized}


if __name__ == "__main__":
    started = datetime.now(timezone.utc)
    result = collect(PILOT_PROJECT, {"TurismoFVG": tourism_udine}, None,
                     started.isoformat(), timeout=90)
    batch = result["sources"]["TurismoFVG"]
    summary = {"source_status": batch["status"], "count": len(batch["events"]),
               "seconds": (datetime.now(timezone.utc)-started).total_seconds(),
               "radii": {str(r): len(query_catalog(result, 46.0711, 13.2346, r)["events"])
                         for r in (5, 10, 20, 30, 50)},
               "unlocated": query_catalog(result, 46.0711, 13.2346)["unlocated_count"],
               "sample": [{k: e.get(k) for k in ("title", "date", "lat", "lon")}
                          for e in batch["events"][:3]]}
    print(json.dumps(summary, ensure_ascii=False, indent=2))
