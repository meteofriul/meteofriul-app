"""Additive 36h policy bound to an immutable, complete CAMS family.

The v1 manifests and payloads retain their original 24h/30h contract. Only new
clients that validate this explicit, separately versioned document may use the
same native hourly forecast up to 36h. A family revocation always wins.
"""
from datetime import datetime, timedelta, timezone
import hashlib
import re

from .contract_v1 import ContractError, canonical_json_bytes

POLICY_ID = "cams_continuity_36h_v1"
KIND = "meteofriul.weather.cams_continuity"
KEY_PATTERN = re.compile(r"weather/v1/families/cams/runs/(\d{8}T000000Z)/continuity\.json\Z")

def continuity_key(run_id, prefix="weather/v1"):
    if not isinstance(run_id, str) or not re.fullmatch(r"\d{8}T000000Z", run_id):
        raise ContractError("invalid CAMS continuity run")
    return f"{prefix}/families/cams/runs/{run_id}/continuity.json"

def build_cams_continuity(release, release_body):
    run_id = release["source_run_id"]
    continuity_key(run_id)
    try:
        run = datetime.strptime(run_id, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
    except ValueError as error:
        raise ContractError("invalid CAMS continuity date") from error
    if canonical_json_bytes(release) != release_body:
        raise ContractError("continuity requires the canonical release bytes")
    iso = lambda value: value.strftime("%Y-%m-%dT%H:%M:%SZ")
    return {
        "schema_version": 1, "kind": KIND, "policy_id": POLICY_ID,
        "source_run_id": run_id, "catalog": release["catalog"],
        "release_sha256": hashlib.sha256(release_body).hexdigest(),
        "release_json_bytes": len(release_body),
        "issued_at": release["published_at"], "run_at": iso(run),
        "fresh_until": iso(run + timedelta(hours=24)),
        "usable_until": iso(run + timedelta(hours=36)),
        "current_sample_max_lag_minutes": 60,
    }

def validate_cams_continuity(value, release, release_body):
    expected = build_cams_continuity(release, release_body)
    if canonical_json_bytes(value) != canonical_json_bytes(expected):
        raise ContractError("CAMS continuity policy or release binding mismatch")
    return value
