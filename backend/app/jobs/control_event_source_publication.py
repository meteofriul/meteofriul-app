"""Manual, fail-closed publication gate for guarded official event sources."""

from __future__ import annotations

import json
import os
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

from app.infrastructure.firebase import get_firestore_client
from app.repositories.event_sources import (
    EVENT_SOURCE_STATE_SCHEMA,
    EventSourceStateRepository,
    EventSourceStateRepositoryUnavailable,
)


ACTION_ENV = "EVENT_SOURCE_PUBLICATION_ACTION"
CONFIRM_ENV = "EVENT_SOURCE_PUBLICATION_CONFIRM"
EXPECTED_APPROVED_ENV = "EVENT_SOURCE_PUBLICATION_EXPECTED_APPROVED"
CONFIRMATION = "EVENT_SOURCE_PUBLICATION_CONTROL_V1"
MAX_STATE_AGE = timedelta(hours=24)


class PublicationControlError(RuntimeError):
    """The publication gate was not changed because a guard failed."""


@dataclass(frozen=True)
class PublicationControlConfig:
    action: str
    expected_approved: int | None

    @classmethod
    def from_environment(cls) -> "PublicationControlConfig":
        action = os.getenv(ACTION_ENV, "status").strip().lower() or "status"
        if action not in {"status", "enable", "disable"}:
            raise PublicationControlError("publication_action_invalid")

        expected_raw = os.getenv(EXPECTED_APPROVED_ENV, "").strip()
        try:
            expected = int(expected_raw) if expected_raw else None
        except ValueError as error:
            raise PublicationControlError("publication_expected_count_invalid") from error
        if expected is not None and not 1 <= expected <= 100:
            raise PublicationControlError("publication_expected_count_invalid")

        if action != "status" and os.getenv(CONFIRM_ENV, "").strip() != CONFIRMATION:
            raise PublicationControlError("publication_confirmation_missing")
        if action == "enable" and expected is None:
            raise PublicationControlError("publication_expected_count_required")
        return cls(action=action, expected_approved=expected)


def _updated_at(value: Any) -> datetime:
    try:
        parsed = datetime.fromisoformat(str(value or ""))
    except ValueError as error:
        raise PublicationControlError("publication_state_timestamp_invalid") from error
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _state_summary(state: dict, *, action: str, storage: str) -> dict[str, Any]:
    return {
        "status": "completed",
        "action": action,
        "storage": storage,
        "publication_enabled": state.get("publication_enabled") is True,
        "approved": len(state.get("approved") or []),
        "pending": len(state.get("pending") or []),
        "quarantined": len(state.get("quarantine") or []),
        "incident_active": (state.get("incident") or {}).get("active") is True,
    }


def run_publication_control(
    repository: EventSourceStateRepository | Any,
    config: PublicationControlConfig,
    *,
    now: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
) -> dict[str, Any]:
    state, storage = repository.load()
    if not isinstance(state, dict) or state.get("schema_version") != EVENT_SOURCE_STATE_SCHEMA:
        raise PublicationControlError("publication_state_invalid")
    if config.action == "status":
        return _state_summary(state, action="status", storage=storage)

    current = now()
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    current = current.astimezone(timezone.utc)

    if config.action == "enable":
        age = current - _updated_at(state.get("updated_at"))
        unexpected_quarantine = any(
            item.get("expected") is not True
            for item in state.get("quarantine") or []
            if isinstance(item, dict)
        )
        approved_count = len(state.get("approved") or [])
        if state.get("mode") != "shadow" or state.get("audit_status") != "ready_for_manual_review":
            raise PublicationControlError("publication_state_not_reviewed")
        if age < timedelta(minutes=-5) or age > MAX_STATE_AGE:
            raise PublicationControlError("publication_state_stale")
        if (state.get("incident") or {}).get("active") is True:
            raise PublicationControlError("publication_incident_active")
        if state.get("pending"):
            raise PublicationControlError("publication_candidates_pending")
        if unexpected_quarantine:
            raise PublicationControlError("publication_unexpected_quarantine")
        if approved_count != config.expected_approved:
            raise PublicationControlError("publication_approved_count_mismatch")

    updated = deepcopy(state)
    updated["publication_enabled"] = config.action == "enable"
    updated["publication_control"] = {
        "action": config.action,
        "changed_at": current.isoformat(timespec="seconds"),
        "method": "manual_cloud_run_job",
    }
    saved_to = repository.save(updated)
    return _state_summary(updated, action=config.action, storage=saved_to)


def main() -> int:
    try:
        result = run_publication_control(
            EventSourceStateRepository(get_firestore_client),
            PublicationControlConfig.from_environment(),
        )
        payload = {
            **result,
            "event": "event_source_publication_control",
            "severity": "INFO",
        }
        exit_code = 0
    except (PublicationControlError, EventSourceStateRepositoryUnavailable) as error:
        payload = {
            "status": str(error) or "publication_control_failed",
            "event": "event_source_publication_control",
            "severity": "ERROR",
        }
        exit_code = 1
    except Exception:
        payload = {
            "status": "publication_control_unexpected_failure",
            "event": "event_source_publication_control",
            "severity": "ERROR",
        }
        exit_code = 1
    print(json.dumps(payload, ensure_ascii=True, sort_keys=True))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
