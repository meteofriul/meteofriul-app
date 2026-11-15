"""Explicit per-source Eventi controls. The public catalog remains read-only."""
from datetime import date, datetime, timezone
from functools import lru_cache
import os
from typing import Annotated
from zoneinfo import ZoneInfo
from google.api_core.exceptions import PreconditionFailed

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, ConfigDict, Field

from app.events.pilot_catalog import PILOT_PROJECT, source_age_failure
from app.events.pilot_cloud import KEY
from app.events.pilot_sources import source_adapters
from app.events.source_controls import KEY as CONTROLS_KEY, paused_names, read_controls, reserve_verification, save_control
from app.infrastructure.events_admin_auth import require_events_admin

router = APIRouter(prefix="/api/admin/events/sources", tags=["events-admin"])
PROJECT = os.getenv("EVENTS_ADMIN_PROJECT", "meteo-friul")
BUCKET = os.getenv("EVENTS_ADMIN_BUCKET", "meteo-friul-weather-data")


class SourceControlUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expectedRevision: int = Field(ge=0, strict=True)
    enabled: bool = Field(strict=True)
    pausedUntil: date | None = None
    reason: str = Field(min_length=3, max_length=500)


@lru_cache(maxsize=1)
def _client():
    import google.auth
    credentials, detected_project = google.auth.default(
        scopes=["https://www.googleapis.com/auth/cloud-platform"])
    if detected_project != PROJECT:
        raise HTTPException(503, detail={"code": "events_project_mismatch"})
    from google.cloud import storage
    return storage.Client(project=PROJECT, credentials=credentials)


def _blob(key):
    return _client().bucket(BUCKET).blob(key)


def _allowed():
    return source_adapters(PILOT_PROJECT)


def _catalog():
    import json
    blob = _blob(KEY)
    blob.reload(timeout=10)
    if blob.size > 8 * 1024 * 1024:
        raise ValueError("catalog too large")
    result = json.loads(blob.download_as_bytes(if_generation_match=int(blob.generation), timeout=10))
    if result.get("schema") != "pilot-events-v1":
        raise ValueError("invalid catalog")
    return result


@router.get("")
def state(response: Response, _admin: Annotated[dict, Depends(require_events_admin)]):
    response.headers["Cache-Control"] = "no-store"
    try:
        controls, _ = read_controls(_blob(CONTROLS_KEY))
        catalog = _catalog()
        now = datetime.now(timezone.utc)
        paused = paused_names(controls, today=now.astimezone(ZoneInfo("Europe/Rome")).date())
        sources = []
        for name in _allowed():
            batch = catalog.get("sources", {}).get(name) or {}
            entry = controls["sources"].get(name) or {}
            status = ("paused" if name in paused else
                      "stale" if batch.get("status") in {"fresh", "partial"} and source_age_failure(batch, now=now)
                      else batch.get("status", "missing"))
            sources.append({"name": name, "status": status,
                            "lastVerifiedAt": batch.get("updated_at"),
                            "lastAttemptAt": batch.get("last_attempted_at"),
                            "errorType": batch.get("last_attempt_error_type"),
                            "enabled": entry.get("enabled", True),
                            "pausedUntil": entry.get("pausedUntil"),
                            "reason": entry.get("reason", "")})
        return {"revision": controls["revision"], "sources": sources,
                "catalogUpdatedAt": catalog.get("attempted_at")}
    except HTTPException:
        raise
    except Exception as error:
        raise HTTPException(503, detail={"code": "events_sources_unavailable"}) from error


@router.put("/{name}")
def update(name: str, command: SourceControlUpdate, response: Response,
           admin: Annotated[dict, Depends(require_events_admin)]):
    response.headers["Cache-Control"] = "no-store"
    if command.pausedUntil and (not command.enabled or command.pausedUntil < datetime.now(ZoneInfo("Europe/Rome")).date()):
        raise HTTPException(400, detail={"code": "events_pause_date_invalid"})
    try:
        saved = save_control(_blob(CONTROLS_KEY), name=name, enabled=command.enabled,
                             paused_until=command.pausedUntil.isoformat() if command.pausedUntil else None,
                             reason=command.reason, actor=admin["uid"],
                             expected_revision=command.expectedRevision,
                             allowed_sources=_allowed())
        return {"revision": saved["revision"]}
    except RuntimeError as error:
        raise HTTPException(409, detail={"code": "events_sources_changed"}) from error
    except PreconditionFailed as error:
        raise HTTPException(409, detail={"code": "events_sources_changed"}) from error
    except ValueError as error:
        raise HTTPException(400, detail={"code": "events_control_invalid"}) from error
    except Exception as error:
        raise HTTPException(503, detail={"code": "events_control_unavailable"}) from error


def _start_single_source(name):
    from google.auth import default
    from google.auth.transport.requests import AuthorizedSession
    credentials, _ = default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
    endpoint = (f"https://run.googleapis.com/v2/projects/{PROJECT}/locations/europe-west1/"
                "jobs/meteofriul-events-refresh:run")
    result = AuthorizedSession(credentials).post(
        endpoint, json={"overrides": {"containerOverrides": [{"args": ["--source", name]}]}},
        timeout=15)
    result.raise_for_status()
    operation = result.json()
    return operation.get("name", "")


@router.post("/{name}/verify", status_code=202)
def verify(name: str, response: Response, _admin: Annotated[dict, Depends(require_events_admin)]):
    response.headers["Cache-Control"] = "no-store"
    if name not in _allowed():
        raise HTTPException(404, detail={"code": "events_source_unknown"})
    try:
        reserve_verification(_blob(CONTROLS_KEY), name=name, actor=_admin["uid"],
                             allowed_sources=_allowed())
        return {"operation": _start_single_source(name), "source": name,
                "requestedAt": datetime.now(timezone.utc).isoformat()}
    except RuntimeError as error:
        raise HTTPException(429, detail={"code": "events_verification_recent"}) from error
    except PreconditionFailed as error:
        raise HTTPException(409, detail={"code": "events_sources_changed"}) from error
    except Exception as error:
        raise HTTPException(503, detail={"code": "events_verification_unavailable"}) from error
