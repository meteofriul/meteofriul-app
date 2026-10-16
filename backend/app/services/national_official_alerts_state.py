"""Persistent national DPC state, isolated from the regional FVG service."""

from __future__ import annotations

import os
import re
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from typing import Any, Callable

from app.infrastructure.firebase import get_firestore_client
from app.repositories.national_official_alerts import (
    NationalOfficialAlertSnapshotRepository,
)
from app.services.dpc_national_source import (
    DpcNationalSource,
    DpcNationalSourceError,
)
from app.services.national_official_alerts import (
    NATIONAL_ALERT_SNAPSHOT_MAX_AGE,
    NationalOfficialAlertsProjectionError,
    project_national_official_alerts,
)
from app.weather.dpc_national_zone_snapshot import DPC_ZONE_SNAPSHOT_CONTRACT


AUTHORITATIVE_NATIONAL_LOAD_STATES = frozenset(
    {"firestore", "firestore_empty"}
)


class NationalOfficialAlertsUnavailable(RuntimeError):
    """No verified, current national snapshot is available for this request."""


@dataclass(frozen=True)
class NationalOfficialAlertSyncResult:
    payload: dict[str, Any]
    refreshed: bool
    stored_in: str
    reason: str


def _revision_identity(payload: dict[str, Any]) -> tuple[datetime, str, str]:
    try:
        sent = datetime.fromisoformat(
            str(payload["cap_revision"]["sent_at"]).replace("Z", "+00:00")
        )
        cap_hash = str(payload["cap_revision"]["sha256"])
        zone_hash = str(payload["revision"]["sha256"])
    except (KeyError, TypeError, ValueError) as error:
        raise NationalOfficialAlertsUnavailable(
            "national_official_alert_revision_invalid"
        ) from error
    if (
        sent.tzinfo is None
        or re.fullmatch(r"[0-9a-f]{64}", cap_hash) is None
        or re.fullmatch(r"[0-9a-f]{64}", zone_hash) is None
    ):
        raise NationalOfficialAlertsUnavailable(
            "national_official_alert_revision_invalid"
        )
    return sent.astimezone(timezone.utc), cap_hash, zone_hash


def _verified_snapshot(payload: Any) -> bool:
    return (
        isinstance(payload, dict)
        and payload.get("contract") == DPC_ZONE_SNAPSHOT_CONTRACT
        and payload.get("coverage") == "all_zones_two_days"
        and payload.get("can_confirm_green") is True
        and payload.get("reconciled") is True
        and isinstance(payload.get("records"), list)
        and bool(payload.get("records"))
    )


def _snapshot_can_be_held(payload: Any, now: datetime) -> bool:
    if not _verified_snapshot(payload) or now.tzinfo is None:
        return False
    current = now.astimezone(timezone.utc)
    try:
        sent, _, _ = _revision_identity(payload)
        valid_until = [
            datetime.fromisoformat(
                str(record["valid_to"]).replace("Z", "+00:00")
            )
            for record in payload["records"]
        ]
    except (KeyError, TypeError, ValueError, NationalOfficialAlertsUnavailable):
        return False
    return (
        sent <= current + timedelta(minutes=5)
        and current - sent <= NATIONAL_ALERT_SNAPSHOT_MAX_AGE
        and all(deadline.tzinfo is not None for deadline in valid_until)
        and any(
            deadline.astimezone(timezone.utc) >= current
            for deadline in valid_until
        )
    )


class NationalOfficialAlertsStateService:
    def __init__(
        self,
        *,
        repository: NationalOfficialAlertSnapshotRepository,
        loader: Callable[[], dict[str, Any]],
        now: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
        allow_memory_persistence: bool = False,
    ) -> None:
        self._repository = repository
        self._loader = loader
        self._now = now
        self._allow_memory_persistence = allow_memory_persistence

    def get_for_municipality(self, municipality_istat: Any) -> dict[str, Any]:
        snapshot, storage = self._repository.load()
        if not _verified_snapshot(snapshot):
            raise NationalOfficialAlertsUnavailable(
                "national_official_alert_snapshot_unavailable"
            )
        try:
            response = project_national_official_alerts(
                snapshot,
                municipality_istat,
                now=self._now(),
            )
        except NationalOfficialAlertsProjectionError as error:
            raise NationalOfficialAlertsUnavailable(str(error)) from error
        response["cache"] = {
            "status": "fresh",
            "layer": "persistent",
            "storage": storage,
        }
        return response

    def refresh(self) -> NationalOfficialAlertSyncResult:
        previous, storage = self._repository.load()
        try:
            fetched = self._loader()
        except DpcNationalSourceError as error:
            authoritative_previous = storage == "firestore" or (
                self._allow_memory_persistence and storage == "memory"
            )
            if (
                str(error) != "dpc_source_cap_not_public"
                or not authoritative_previous
                or not _snapshot_can_be_held(previous, self._now())
            ):
                raise
            return NationalOfficialAlertSyncResult(
                payload=deepcopy(previous),
                refreshed=False,
                stored_in=storage,
                reason="source_cap_not_public_held",
            )
        if not _verified_snapshot(fetched):
            raise NationalOfficialAlertsUnavailable(
                "national_official_alert_source_unverified"
            )
        fetched_revision = _revision_identity(fetched)
        if isinstance(previous, dict):
            if not _verified_snapshot(previous):
                raise NationalOfficialAlertsUnavailable(
                    "national_official_alert_stored_snapshot_invalid"
                )
            previous_revision = _revision_identity(previous)
            if fetched_revision[0] < previous_revision[0]:
                return NationalOfficialAlertSyncResult(
                    payload=deepcopy(previous),
                    refreshed=False,
                    stored_in=storage,
                    reason="revision_rollback_rejected",
                )
            if fetched_revision[0] == previous_revision[0]:
                if fetched_revision[1:] != previous_revision[1:]:
                    raise NationalOfficialAlertsUnavailable(
                        "national_official_alert_same_revision_conflict"
                    )
                return NationalOfficialAlertSyncResult(
                    payload=deepcopy(previous),
                    refreshed=False,
                    stored_in=storage,
                    reason="already_current",
                )

        authoritative = storage in AUTHORITATIVE_NATIONAL_LOAD_STATES or (
            self._allow_memory_persistence and storage in {"empty", "memory"}
        )
        if not authoritative:
            return NationalOfficialAlertSyncResult(
                payload=deepcopy(fetched),
                refreshed=False,
                stored_in="unchanged",
                reason="persistent_snapshot_read_unconfirmed",
            )
        stored_in = self._repository.save(fetched)
        persisted = stored_in == "firestore" or (
            self._allow_memory_persistence and stored_in == "memory"
        )
        return NationalOfficialAlertSyncResult(
            payload=deepcopy(fetched),
            refreshed=persisted,
            stored_in=stored_in,
            reason="stored" if persisted else "persistent_write_failed",
        )


@lru_cache(maxsize=1)
def get_national_official_alerts_state_service() -> (
    NationalOfficialAlertsStateService
):
    allow_memory = not bool(os.getenv("K_SERVICE"))
    source = DpcNationalSource()
    return NationalOfficialAlertsStateService(
        repository=NationalOfficialAlertSnapshotRepository(
            firestore_provider=get_firestore_client,
        ),
        loader=source.fetch,
        allow_memory_persistence=allow_memory,
    )


def reset_national_official_alerts_state_service_for_tests() -> None:
    get_national_official_alerts_state_service.cache_clear()


__all__ = [
    "NationalOfficialAlertSyncResult",
    "NationalOfficialAlertsStateService",
    "NationalOfficialAlertsUnavailable",
    "get_national_official_alerts_state_service",
]
