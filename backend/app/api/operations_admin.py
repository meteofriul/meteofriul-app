"""Owner-only, read-only operational status for the management panel."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, Response

from app.api.events_admin import _catalog
from app.api.events_admin import _blob, CONTROLS_KEY
from app.events.source_controls import paused_names, read_controls
from app.infrastructure.events_admin_auth import require_events_admin
from app.services.operational_status import build_operational_status
from zoneinfo import ZoneInfo


router = APIRouter(prefix="/api/admin/operations", tags=["operations-admin"])
PROJECT = "meteo-friul"
LOGGING_URL = "https://logging.googleapis.com/v2/entries:list"


def _forecast_entries(now: datetime) -> list[dict]:
    import google.auth
    from google.auth.transport.requests import AuthorizedSession

    credentials, project = google.auth.default(
        scopes=["https://www.googleapis.com/auth/cloud-platform"])
    if project != PROJECT:
        raise RuntimeError("operations_project_mismatch")
    since = (now - timedelta(days=7)).strftime("%Y-%m-%dT%H:%M:%SZ")
    result = AuthorizedSession(credentials).post(
        LOGGING_URL,
        json={
            "resourceNames": [f"projects/{PROJECT}"],
            "filter": (
                'resource.type="cloud_run_job" AND '
                '(resource.labels.job_name="meteofriul-morning-forecast" OR '
                'resource.labels.job_name="meteofriul-evening-forecast") AND '
                f'jsonPayload.execution_context.schema_version=1 AND timestamp>="{since}"'
            ),
            "orderBy": "timestamp desc", "pageSize": 100,
        },
        timeout=12,
    )
    result.raise_for_status()
    entries = result.json().get("entries", [])
    if not isinstance(entries, list):
        raise ValueError("operations_logs_invalid")
    return entries


@router.get("")
def state(response: Response, _admin: Annotated[dict, Depends(require_events_admin)]):
    response.headers["Cache-Control"] = "no-store"
    now = datetime.now(timezone.utc)
    try:
        entries = _forecast_entries(now)
    except Exception:
        entries = None
    try:
        catalog = _catalog()
        controls, _ = read_controls(_blob(CONTROLS_KEY))
        paused = paused_names(controls, today=now.astimezone(ZoneInfo("Europe/Rome")).date())
    except Exception:
        catalog = None
        paused = None
    return build_operational_status(entries=entries, catalog=catalog, now=now,
                                    paused_sources=paused)
