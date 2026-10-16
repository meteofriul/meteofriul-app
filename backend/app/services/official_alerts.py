from __future__ import annotations

import os
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from typing import Any, Callable

from app.infrastructure.firebase import get_firestore_client
from app.repositories.official_alerts import OfficialAlertSnapshotRepository
from app.services.official_alert_sources import (
    fetch_official_alert_observations,
    reconcile_official_alert_observations,
)
from app.weather import alerts_engine


INACTIVE_SNAPSHOT_TTL_SECONDS = int(
    # The owner scheduler refreshes every two hours. Keep a 30-minute grace
    # period for scheduler jitter and cold starts without hiding a missed run.
    os.getenv("OFFICIAL_ALERTS_INACTIVE_SNAPSHOT_TTL_SECONDS", str(150 * 60))
)
ACTIVE_SNAPSHOT_FALLBACK_TTL_SECONDS = int(
    os.getenv("OFFICIAL_ALERTS_ACTIVE_SNAPSHOT_TTL_SECONDS", str(6 * 60 * 60))
)
CONFIRMED_SOURCE_MODES = frozenset(
    {
        "official_widget",
        "official_page",
        "official_telegram_pdf_verified",
        "official_fvg_widget_arpa_corroborated",
        "official_page_arpa_corroborated",
        "official_telegram_arpa_corroborated",
        "arpa_pcr_mirror",
        "official_validity_expired",
    }
)
AUTHORITATIVE_SNAPSHOT_LOAD_STATES = frozenset({"firestore", "firestore_empty"})


@dataclass(frozen=True)
class OfficialAlertSyncResult:
    payload: dict[str, Any]
    refreshed: bool
    stored_in: str


def _parse_datetime(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed
    except ValueError:
        return None


def _snapshot_age_seconds(payload: dict[str, Any], now: datetime) -> int | None:
    fetched_at = _parse_datetime(payload.get("fetched_at"))
    if fetched_at is None:
        return None
    return max(0, int((now - fetched_at.astimezone(now.tzinfo)).total_seconds()))


def _active_snapshot_expiry(payload: dict[str, Any]) -> datetime | None:
    expires_at = _parse_datetime(payload.get("expires_at"))
    if expires_at is not None:
        return expires_at

    valid_to = [
        _parse_datetime((alert or {}).get("valid_to"))
        for alert in payload.get("alerts") or []
        if isinstance(alert, dict)
    ]
    return max((value for value in valid_to if value is not None), default=None)


def official_alert_snapshot_is_usable(
    payload: dict[str, Any] | None,
    *,
    now: datetime | None = None,
) -> bool:
    if not isinstance(payload, dict) or payload.get("error"):
        return False

    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)

    if payload.get("active"):
        expiry = _active_snapshot_expiry(payload)
        if expiry is not None:
            return current <= expiry.astimezone(current.tzinfo) + timedelta(hours=1)
        age = _snapshot_age_seconds(payload, current)
        return age is not None and age <= ACTIVE_SNAPSHOT_FALLBACK_TTL_SECONDS

    age = _snapshot_age_seconds(payload, current)
    return age is not None and age <= INACTIVE_SNAPSHOT_TTL_SECONDS


def _confirmed_payload(payload: dict[str, Any]) -> bool:
    cache_status = str((payload.get("cache") or {}).get("status") or "").strip().lower()
    source_mode = str(payload.get("source_mode") or "").strip().lower()
    return (
        not payload.get("error")
        and cache_status == "fresh"
        and source_mode in CONFIRMED_SOURCE_MODES
    )


def _decorate_persistent_payload(
    payload: dict[str, Any],
    *,
    storage: str,
    now: datetime,
) -> dict[str, Any]:
    response = dict(payload)
    response["cache"] = {
        **(response.get("cache") or {}),
        "status": "fresh",
        "layer": "persistent",
        "storage": storage,
    }
    age = _snapshot_age_seconds(response, now)
    if age is not None:
        response["cache"]["age_seconds"] = age
    return response


class OfficialAlertsStateService:
    def __init__(
        self,
        *,
        repository: OfficialAlertSnapshotRepository,
        loader: Callable[..., dict[str, Any]] = alerts_engine.fetch_official_alerts,
        reconciler: Callable[..., dict[str, Any]] | None = None,
        now: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
        direct_fetch_on_read: bool = True,
    ) -> None:
        self._repository = repository
        self._loader = loader
        self._reconciler = reconciler
        self._now = now
        self._direct_fetch_on_read = direct_fetch_on_read

    def get(self, *, force: bool = False) -> dict[str, Any]:
        # A public cache-buster may refresh the persistent snapshot read, but in
        # Cloud Run it must not trigger upstream scraping or Firestore writes.
        # The scheduled sync job calls refresh() directly.
        if force and self._direct_fetch_on_read:
            return self.refresh().payload

        now = self._now()
        snapshot, storage = self._repository.load()
        if official_alert_snapshot_is_usable(snapshot, now=now):
            return _decorate_persistent_payload(snapshot, storage=storage, now=now)

        if not self._direct_fetch_on_read:
            unavailable = alerts_engine.build_official_alerts_unavailable_response(
                "persistent_snapshot_unavailable"
            )
            unavailable["cache"] = {
                **(unavailable.get("cache") or {}),
                "layer": "persistent",
                "storage": storage,
            }
            return unavailable

        return self.refresh().payload

    def refresh(self) -> OfficialAlertSyncResult:
        now = self._now()
        snapshot, storage = self._repository.load()
        loaded = self._loader(force=True)
        payload = (
            self._reconciler(snapshot, loaded, now=now)
            if self._reconciler is not None
            else loaded
        )
        if _confirmed_payload(payload) and storage in AUTHORITATIVE_SNAPSHOT_LOAD_STATES:
            stored_in = self._repository.save(payload)
            return OfficialAlertSyncResult(
                payload=payload,
                refreshed=True,
                stored_in=stored_in,
            )

        if _confirmed_payload(payload):
            guarded = deepcopy(payload)
            guarded["cache"] = {
                **(guarded.get("cache") or {}),
                "reason": "persistent_snapshot_read_unconfirmed",
                "storage": storage,
            }
            guarded["warning"] = "persistent_snapshot_read_unconfirmed"
            return OfficialAlertSyncResult(
                payload=guarded,
                refreshed=False,
                stored_in="unchanged",
            )

        if (
            isinstance(snapshot, dict)
            and snapshot.get("active")
            and official_alert_snapshot_is_usable(snapshot, now=now)
        ):
            stale = _decorate_persistent_payload(snapshot, storage=storage, now=now)
            stale_cache = {
                **(stale.get("cache") or {}),
                "status": "stale",
                "reason": "official_alerts_refresh_failed",
            }
            upstream_failure = alerts_engine.sanitize_official_alerts_upstream_failure(
                (payload.get("cache") or {}).get("upstream_failure")
            )
            if upstream_failure is not None:
                stale_cache["upstream_failure"] = upstream_failure
            stale["cache"] = stale_cache
            stale["warning"] = "official_alerts_refresh_failed"
            return OfficialAlertSyncResult(
                payload=stale,
                refreshed=False,
                stored_in="unchanged",
            )

        return OfficialAlertSyncResult(
            payload=payload,
            refreshed=False,
            stored_in="unchanged",
        )


@lru_cache(maxsize=1)
def get_official_alerts_state_service() -> OfficialAlertsStateService:
    direct_fetch_default = "false" if os.getenv("K_SERVICE") else "true"
    direct_fetch_on_read = (
        os.getenv("OFFICIAL_ALERTS_DIRECT_FETCH_ON_READ", direct_fetch_default)
        .strip()
        .lower()
        in {"1", "true", "yes", "on"}
    )
    return OfficialAlertsStateService(
        repository=OfficialAlertSnapshotRepository(
            firestore_provider=get_firestore_client,
        ),
        loader=fetch_official_alert_observations,
        reconciler=reconcile_official_alert_observations,
        direct_fetch_on_read=direct_fetch_on_read,
    )


def get_official_alerts_state(*, force: bool = False) -> dict[str, Any]:
    return get_official_alerts_state_service().get(force=force)


def reset_official_alerts_state_service_for_tests() -> None:
    get_official_alerts_state_service.cache_clear()
