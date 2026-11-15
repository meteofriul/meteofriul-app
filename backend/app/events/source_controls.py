"""Small, revisioned control file shared by the Eventi admin API and collector."""
from datetime import date, datetime, timezone, timedelta
import json

SCHEMA = "event-source-controls-v1"
KEY = "pilot/events/v1/source-controls.json"
MAX_BYTES = 64_000


def empty_controls():
    return {"schema": SCHEMA, "revision": 0, "sources": {}}


def decode_controls(data):
    if not data:
        return empty_controls()
    if isinstance(data, bytes):
        if len(data) > MAX_BYTES:
            raise ValueError("source controls too large")
        data = json.loads(data)
    if not isinstance(data, dict) or data.get("schema") != SCHEMA:
        raise ValueError("invalid source controls schema")
    if type(data.get("revision")) is not int or data["revision"] < 0:
        raise ValueError("invalid source controls revision")
    if not isinstance(data.get("sources"), dict):
        raise ValueError("invalid source controls entries")
    return data


def source_is_paused(entry, *, today=None):
    if not isinstance(entry, dict):
        return False
    if entry.get("enabled") is False:
        return True
    until = entry.get("pausedUntil")
    if not until:
        return False
    try:
        return date.fromisoformat(until) >= (today or date.today())
    except (TypeError, ValueError):
        raise ValueError("invalid pause date")


def paused_names(controls, *, today):
    return {name for name, entry in controls["sources"].items()
            if source_is_paused(entry, today=today)}


def read_controls(blob):
    from google.api_core.exceptions import NotFound
    try:
        blob.reload(timeout=10)
        generation = int(blob.generation)
        if blob.size > MAX_BYTES:
            raise ValueError("source controls too large")
        return decode_controls(blob.download_as_bytes(
            if_generation_match=generation, timeout=10)), generation
    except NotFound:
        return empty_controls(), 0


def save_control(blob, *, name, enabled, paused_until, reason, actor,
                 expected_revision, allowed_sources):
    if name not in allowed_sources:
        raise ValueError("unknown source")
    if len(reason.strip()) < 3 or len(reason) > 500:
        raise ValueError("reason required")
    if paused_until:
        date.fromisoformat(paused_until)
    current, generation = read_controls(blob)
    if current["revision"] != expected_revision:
        raise RuntimeError("source controls revision conflict")
    updated = {**current, "revision": expected_revision + 1,
               "sources": dict(current["sources"])}
    updated["sources"][name] = {**updated["sources"].get(name, {}),
        "enabled": enabled, "pausedUntil": paused_until,
        "reason": reason.strip(), "updatedBy": actor,
        "updatedAt": datetime.now().astimezone().isoformat(),
    }
    encoded = json.dumps(updated, ensure_ascii=False, allow_nan=False).encode("utf-8")
    if len(encoded) > MAX_BYTES:
        raise ValueError("source controls too large")
    blob.upload_from_string(encoded, content_type="application/json",
                            if_generation_match=generation, timeout=15)
    return updated


def reserve_verification(blob, *, name, actor, allowed_sources, now=None):
    if name not in allowed_sources:
        raise ValueError("unknown source")
    now = now or datetime.now(timezone.utc)
    current, generation = read_controls(blob)
    entry = dict(current["sources"].get(name) or {})
    last = entry.get("lastVerificationRequestedAt")
    if last and now - datetime.fromisoformat(last) < timedelta(minutes=10):
        raise RuntimeError("source verification cooldown")
    entry["lastVerificationRequestedAt"] = now.isoformat()
    entry["lastVerificationRequestedBy"] = actor
    updated = {**current, "revision": current["revision"] + 1,
               "sources": {**current["sources"], name: entry}}
    blob.upload_from_string(json.dumps(updated, ensure_ascii=False).encode("utf-8"),
                            content_type="application/json",
                            if_generation_match=generation, timeout=15)
    return updated
