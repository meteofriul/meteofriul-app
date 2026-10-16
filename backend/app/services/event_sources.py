from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import dataclass
from datetime import date, datetime, timezone
from functools import lru_cache
from typing import Any, Callable

from app.events import engine
from app.events.audit import (
    DECISION_BLOCKED,
    DECISION_CONFLICT,
    DECISION_READY,
    DECISION_REVIEW_DUPLICATE,
    canonical_url,
)
from app.events.source_pipeline import build_live_event_source_audit
from app.infrastructure.firebase import get_firestore_client
from app.repositories.event_sources import (
    EVENT_SOURCE_STATE_SCHEMA,
    EventSourceStateRepository,
    EventSourceStateRepositoryUnavailable,
)
from app.services.location import LocationCatalog


EVENT_SOURCE_AUTOMATION_MODE_ENV = "EVENT_SOURCE_AUTOMATION_MODE"
EVENT_SOURCE_LOCAL_STATE_PATH_ENV = "EVENT_SOURCE_LOCAL_STATE_PATH"
EVENT_SOURCE_CONFIRMATIONS_ENV = "EVENT_SOURCE_CONFIRMATIONS_REQUIRED"
EVENT_SOURCE_ALERT_THRESHOLD_ENV = "EVENT_SOURCE_ALERT_FAILURE_THRESHOLD"
EVENT_SOURCE_ALERT_EMAIL_ENV = "EVENT_SOURCE_ALERT_EMAIL_TO"
EVENT_SOURCE_ACTIVE_LIMIT_ENV = "EVENT_SOURCE_ACTIVE_LIMIT"

AUTOMATION_SCHEMA_VERSION = "event-source-automation.v1"
DEFAULT_ALERT_EMAIL = "info@meteofriul.it"
ANOMALOUS_DECISIONS = frozenset(
    {DECISION_BLOCKED, DECISION_CONFLICT, DECISION_REVIEW_DUPLICATE}
)
EXPECTED_QUARANTINE_URLS = frozenset(
    {
        "https://galleriaspazzapan.regione.fvg.it/it/flowers-naturae-connessioni-tra-terra-e-arte-169385",
    }
)


class EventSourceAutomationConfigurationError(RuntimeError):
    """The automation remains disabled when its fail-closed config is invalid."""


@dataclass(frozen=True)
class EventSourceAutomationConfig:
    mode: str
    local_state_path: str | None
    confirmations_required: int
    alert_failure_threshold: int
    alert_email_to: str
    active_limit: int

    @classmethod
    def from_environment(cls) -> "EventSourceAutomationConfig":
        mode = os.getenv(EVENT_SOURCE_AUTOMATION_MODE_ENV, "off").strip().lower() or "off"
        if mode not in {"off", "shadow"}:
            raise EventSourceAutomationConfigurationError(
                "event_source_automation_mode_invalid"
            )
        local_state_path = os.getenv(EVENT_SOURCE_LOCAL_STATE_PATH_ENV, "").strip() or None
        if local_state_path and os.getenv("K_SERVICE", "").strip():
            raise EventSourceAutomationConfigurationError(
                "event_source_local_state_forbidden_in_cloud_run"
            )
        try:
            confirmations = int(os.getenv(EVENT_SOURCE_CONFIRMATIONS_ENV, "2"))
            alert_threshold = int(os.getenv(EVENT_SOURCE_ALERT_THRESHOLD_ENV, "2"))
            active_limit = int(os.getenv(EVENT_SOURCE_ACTIVE_LIMIT_ENV, "100"))
        except ValueError as error:
            raise EventSourceAutomationConfigurationError(
                "event_source_automation_numeric_config_invalid"
            ) from error
        if confirmations < 2 or confirmations > 3:
            raise EventSourceAutomationConfigurationError(
                "event_source_confirmations_invalid"
            )
        if alert_threshold < 2 or alert_threshold > 5:
            raise EventSourceAutomationConfigurationError(
                "event_source_alert_threshold_invalid"
            )
        if active_limit < 1 or active_limit > 100:
            raise EventSourceAutomationConfigurationError(
                "event_source_active_limit_invalid"
            )
        email = os.getenv(EVENT_SOURCE_ALERT_EMAIL_ENV, DEFAULT_ALERT_EMAIL).strip().lower()
        if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email):
            raise EventSourceAutomationConfigurationError(
                "event_source_alert_email_invalid"
            )
        return cls(
            mode=mode,
            local_state_path=local_state_path,
            confirmations_required=confirmations,
            alert_failure_threshold=alert_threshold,
            alert_email_to=email,
            active_limit=active_limit,
        )


@dataclass(frozen=True)
class EventSourceAutomationRunResult:
    status: str
    storage: str = ""
    approved: int = 0
    pending: int = 0
    quarantined: int = 0
    duplicates: int = 0
    publication_enabled: bool = False
    incident_active: bool = False
    alert_transition: str = "none"
    alert_email_to: str = DEFAULT_ALERT_EMAIL
    issues: tuple[str, ...] = ()
    incident_details: tuple[dict[str, Any], ...] = ()
    active_catalog_coverage: dict[str, Any] | None = None

    def summary(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "storage": self.storage,
            "approved": self.approved,
            "pending": self.pending,
            "quarantined": self.quarantined,
            "duplicates": self.duplicates,
            "publication_enabled": self.publication_enabled,
            "incident_active": self.incident_active,
            "alert_transition": self.alert_transition,
            "alert_email_to": self.alert_email_to,
            "issues": list(self.issues),
            "incident_details": [dict(item) for item in self.incident_details],
            "active_catalog_coverage": dict(self.active_catalog_coverage or {}),
        }


def _stable_hash(value: Any) -> str:
    serialized = json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _candidate_key(record: dict) -> str:
    return canonical_url(record.get("url")) or _stable_hash(
        [record.get("source"), record.get("title"), record.get("event_city")]
    )


def _critical_fingerprint(record: dict) -> str:
    return _stable_hash(
        {
            "url": canonical_url(record.get("url")),
            "title": record.get("title"),
            "start_date": record.get("start_date"),
            "end_date": record.get("end_date"),
            "occurrences": list(record.get("occurrences") or []),
            "event_city": record.get("event_city"),
            "venue": record.get("venue"),
            "time": record.get("time"),
            "status": record.get("status") or record.get("event_status"),
        }
    )


def _is_past(event: dict, as_of: date) -> bool:
    raw = str(event.get("end_date") or event.get("start_date") or "")[:10]
    try:
        return date.fromisoformat(raw) < as_of
    except ValueError:
        return True


def _next_occurrence_date_label(record: dict, *, as_of: date) -> str | None:
    upcoming = []
    for value in record.get("occurrences") or []:
        try:
            occurrence = date.fromisoformat(str(value or "")[:10])
        except ValueError:
            continue
        if occurrence >= as_of:
            upcoming.append(occurrence)
    if not upcoming:
        return None

    selected = min(upcoming)
    month = (
        "gennaio febbraio marzo aprile maggio giugno luglio agosto "
        "settembre ottobre novembre dicembre"
    ).split()[selected.month - 1]
    return f"{selected.day} {month} {selected.year}"


def _production_event(record: dict, *, verified_at: datetime) -> dict:
    title = str(record.get("title") or "").strip()
    description = str(record.get("description") or "").strip()
    provider_categories = str(record.get("provider_categories") or "").strip()
    classification = engine.classify_event(
        title,
        f"{description} {provider_categories}",
    )
    normalized_title = engine.normalize_for_search(title)
    if re.search(r"\bcena\b", normalized_title):
        classification = {
            "category": "food_wine",
            "category_label": "Enogastronomia",
            "priority": 86,
            "weather_sensitivity": "medium",
        }
    elif (
        record.get("source") in {"Villa Manin", "ERPAC FVG"}
        and classification.get("category") in {"generico", "sagra"}
        and not engine.has_strong_traditional_event_signal(
            title,
            provider_categories,
        )
    ):
        classification = {
            "category": "cultura",
            "category_label": "Cultura",
            "priority": 72,
            "weather_sensitivity": "low",
        }
    city = str(record.get("event_city") or "").strip()
    municipality = LocationCatalog().match_names(city)
    event = {
        "title": title,
        "url": canonical_url(record.get("url")) or str(record.get("url") or ""),
        "official_site": canonical_url(record.get("url")) or str(record.get("url") or ""),
        "date": _next_occurrence_date_label(
            record,
            as_of=verified_at.date(),
        ) or record.get("date"),
        "start_date": record.get("start_date"),
        "end_date": record.get("end_date"),
        "occurrences": list(record.get("occurrences") or []),
        "event_city": city,
        "venue": record.get("venue"),
        "place": record.get("place") or city,
        "description": description,
        "image": record.get("image"),
        "image_original": record.get("image_original") or record.get("image"),
        "source": record.get("source"),
        "provider_categories": provider_categories or None,
        "provider_category_list": list(record.get("provider_category_list") or []),
        "location_confidence": "municipality",
        "is_real": True,
        "category": classification.get("category"),
        "category_label": classification.get("category_label"),
        "priority": classification.get("priority"),
        "weather_sensitivity": classification.get("weather_sensitivity"),
        "verified_at": verified_at.isoformat(timespec="seconds"),
        "automation_schema": AUTOMATION_SCHEMA_VERSION,
    }
    if municipality:
        event["lat"] = municipality.latitude
        event["lon"] = municipality.longitude
    return {key: value for key, value in event.items() if value not in (None, "", [])}


def _active_catalog_coverage_summary(report: dict) -> dict[str, Any]:
    visible_catalog = report.get("visible_catalog") or {}
    raw_coverage = report.get("active_catalog_coverage") or {}
    complete = bool(
        raw_coverage.get("complete", visible_catalog.get("complete", False))
    )
    warnings = [
        str(value).strip()
        for value in (raw_coverage.get("warnings") or visible_catalog.get("warnings") or [])
        if str(value).strip()
    ]
    incomplete_cities = {
        str(value).strip()
        for value in visible_catalog.get("incomplete_cities") or []
        if str(value).strip()
    }
    failures = []
    for city, city_status in (raw_coverage.get("cities") or {}).items():
        city_name = str(city or "").strip()
        if city_status.get("complete") is not False:
            continue
        if city_name:
            incomplete_cities.add(city_name)
        for source, source_status in (city_status.get("sources") or {}).items():
            status = str(source_status.get("status") or "unknown").strip().lower()
            if status == "ok":
                continue
            failure = {
                "city": city_name or None,
                "source": str(source or "").strip() or None,
                "status": status,
            }
            error = str(source_status.get("error") or "").strip()
            if error:
                failure["error"] = error[:500]
            failures.append(failure)

    return {
        "complete": complete,
        "incomplete_cities": sorted(incomplete_cities, key=str.casefold),
        "failures": sorted(
            failures,
            key=lambda item: (
                str(item.get("city") or "").casefold(),
                str(item.get("source") or "").casefold(),
            ),
        ),
        "warnings": warnings,
    }


def _issue_summary(
    report: dict,
) -> tuple[list[dict], list[str], list[dict], dict[str, Any]]:
    quarantined = []
    issue_codes = []
    incident_details = []
    coverage = _active_catalog_coverage_summary(report)
    for source in report.get("source_summaries") or []:
        if source.get("status") == "blocked":
            source_name = str(source.get("source") or "unknown").strip()
            source_cities = sorted(
                {
                    str(record.get("event_city") or "").strip()
                    for item in report.get("candidates") or []
                    if (
                        (record := item.get("source_record") or item.get("candidate") or {})
                        .get("source")
                        == source.get("source")
                    )
                    and str(record.get("event_city") or "").strip()
                },
                key=str.casefold,
            )
            issue_codes.append(f"source_blocked:{source_name}")
            incident_details.append(
                {
                    "type": "source_blocked",
                    "source": source_name,
                    "cities": source_cities,
                    "structure_errors": list(source.get("structure_errors") or []),
                }
            )
    if not coverage["complete"]:
        issue_codes.append("visible_catalog_incomplete")
        for failure in coverage["failures"]:
            city = failure.get("city") or "unknown"
            source = failure.get("source") or "unknown"
            status = failure.get("status") or "unknown"
            issue_codes.append(
                f"active_catalog_coverage:{city}:{source}:{status}"
            )
            incident_details.append(
                {
                    "type": "active_catalog_coverage",
                    **failure,
                }
            )
        if not coverage["failures"]:
            for city in coverage["incomplete_cities"] or [None]:
                incident_details.append(
                    {
                        "type": "active_catalog_coverage",
                        "city": city,
                        "source": None,
                        "status": "incomplete",
                    }
                )

    for item in report.get("candidates") or []:
        decision = item.get("decision")
        if decision not in ANOMALOUS_DECISIONS:
            continue
        record = item.get("source_record") or item.get("candidate") or {}
        url = canonical_url(record.get("url")) or ""
        expected = url in EXPECTED_QUARANTINE_URLS
        quarantine = {
            "source": record.get("source"),
            "title": record.get("title"),
            "url": url,
            "decision": decision,
            "blockers": list(item.get("blockers") or []),
            "expected": expected,
        }
        quarantined.append(quarantine)
        if not expected:
            issue_codes.append(
                f"candidate:{decision}:{url or _candidate_key(record)}"
            )
            incident_details.append(
                {
                    "type": "candidate",
                    "source": record.get("source"),
                    "city": record.get("event_city"),
                    "title": record.get("title"),
                    "url": url,
                    "decision": decision,
                    "blockers": list(item.get("blockers") or []),
                }
            )
    return quarantined, sorted(set(issue_codes)), incident_details, coverage


class EventSourceAutomationService:
    def __init__(
        self,
        *,
        repository: EventSourceStateRepository | Any,
        config: EventSourceAutomationConfig,
        audit_builder: Callable[..., dict] = build_live_event_source_audit,
        now: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    ) -> None:
        self._repository = repository
        self._config = config
        self._audit_builder = audit_builder
        self._now = now

    def _current_time(self) -> datetime:
        current = self._now()
        if current.tzinfo is None:
            current = current.replace(tzinfo=timezone.utc)
        return current.astimezone(timezone.utc)

    def run(self) -> EventSourceAutomationRunResult:
        if self._config.mode == "off":
            return EventSourceAutomationRunResult(
                status="disabled",
                alert_email_to=self._config.alert_email_to,
            )

        previous, _ = self._repository.load()
        previous = previous if isinstance(previous, dict) else {}
        now = self._current_time()
        report = self._audit_builder(
            as_of=now.date(),
            active_limit=self._config.active_limit,
        )
        quarantine, issue_codes, incident_details, active_catalog_coverage = (
            _issue_summary(report)
        )

        previous_approved = {
            item["key"]: item
            for item in previous.get("approved") or []
            if isinstance(item, dict) and item.get("key")
        }
        previous_pending = {
            item["key"]: item
            for item in previous.get("pending") or []
            if isinstance(item, dict) and item.get("key")
        }
        approved: dict[str, dict] = {}
        pending: dict[str, dict] = {}
        current_decisions: dict[str, str] = {}
        duplicate_count = 0

        for item in report.get("candidates") or []:
            record = item.get("source_record") or {}
            key = _candidate_key(record)
            decision = str(item.get("decision") or "")
            current_decisions[key] = decision
            if decision.startswith("confirmed_duplicate") or decision.startswith("consolidated"):
                duplicate_count += 1
            if decision != DECISION_READY:
                continue

            fingerprint = _critical_fingerprint(record)
            old_approved = previous_approved.get(key)
            if old_approved and old_approved.get("fingerprint") == fingerprint:
                approved[key] = {
                    **old_approved,
                    "event": _production_event(record, verified_at=now),
                    "last_confirmed_at": now.isoformat(timespec="seconds"),
                }
                continue

            old_pending = previous_pending.get(key)
            confirmations = (
                int(old_pending.get("confirmations") or 0) + 1
                if old_pending and old_pending.get("fingerprint") == fingerprint
                else 1
            )
            pending_record = {
                "key": key,
                "fingerprint": fingerprint,
                "confirmations": confirmations,
                "first_seen_at": (
                    old_pending.get("first_seen_at")
                    if old_pending and old_pending.get("fingerprint") == fingerprint
                    else now.isoformat(timespec="seconds")
                ),
                "last_seen_at": now.isoformat(timespec="seconds"),
                "event": _production_event(record, verified_at=now),
            }
            if confirmations >= self._config.confirmations_required:
                approved[key] = {
                    **pending_record,
                    "approved_at": now.isoformat(timespec="seconds"),
                }
            else:
                pending[key] = pending_record
                if old_approved:
                    approved[key] = old_approved

        for key, old in previous_approved.items():
            if key in approved:
                continue
            decision = current_decisions.get(key)
            if decision and (
                decision.startswith("confirmed_duplicate")
                or decision.startswith("consolidated")
            ):
                continue
            if not _is_past(old.get("event") or {}, now.date()):
                approved[key] = old

        previous_incident = previous.get("incident") or {}
        issue_signature = _stable_hash(issue_codes) if issue_codes else ""
        same_observation = bool(
            issue_signature
            and issue_signature == previous_incident.get("signature")
        )
        observation_count = (
            int(previous_incident.get("observation_count") or 0) + 1
            if same_observation
            else (1 if issue_signature else 0)
        )
        was_active = bool(previous_incident.get("active"))
        incident_active = bool(
            issue_signature
            and (
                was_active
                or observation_count >= self._config.alert_failure_threshold
            )
        )
        if incident_active and not was_active:
            alert_transition = "opened"
        elif not incident_active and was_active and not issue_signature:
            alert_transition = "recovered"
        else:
            alert_transition = "none"

        state = {
            "schema_version": EVENT_SOURCE_STATE_SCHEMA,
            "automation_schema": AUTOMATION_SCHEMA_VERSION,
            "mode": "shadow",
            # The scanner can never enable publication by itself. It only
            # preserves a gate that an operator enabled explicitly after QA.
            "publication_enabled": previous.get("publication_enabled") is True,
            "updated_at": now.isoformat(timespec="seconds"),
            "audit_status": report.get("status"),
            "approved": sorted(approved.values(), key=lambda item: item["key"]),
            "pending": sorted(pending.values(), key=lambda item: item["key"]),
            "quarantine": quarantine,
            "incident": {
                "active": incident_active,
                "signature": issue_signature,
                "observation_count": observation_count,
                "issues": issue_codes,
                "details": incident_details,
                "active_catalog_coverage": active_catalog_coverage,
                "alert_email_to": self._config.alert_email_to,
                "transition": alert_transition,
            },
            "counts": {
                "approved": len(approved),
                "pending": len(pending),
                "quarantined": len(quarantine),
                "duplicates": duplicate_count,
            },
        }
        storage = self._repository.save(state)
        status = "incident" if incident_active else "completed"
        return EventSourceAutomationRunResult(
            status=status,
            storage=storage,
            approved=len(approved),
            pending=len(pending),
            quarantined=len(quarantine),
            duplicates=duplicate_count,
            publication_enabled=state["publication_enabled"],
            incident_active=incident_active,
            alert_transition=alert_transition,
            alert_email_to=self._config.alert_email_to,
            issues=tuple(issue_codes),
            incident_details=tuple(incident_details),
            active_catalog_coverage=active_catalog_coverage,
        )


@lru_cache(maxsize=1)
def get_event_source_automation_service() -> EventSourceAutomationService:
    config = EventSourceAutomationConfig.from_environment()
    return EventSourceAutomationService(
        repository=EventSourceStateRepository(
            get_firestore_client,
            local_state_path=config.local_state_path,
        ),
        config=config,
    )


def reset_event_source_automation_service_for_tests() -> None:
    get_event_source_automation_service.cache_clear()


__all__ = [
    "AUTOMATION_SCHEMA_VERSION",
    "DEFAULT_ALERT_EMAIL",
    "EventSourceAutomationConfig",
    "EventSourceAutomationConfigurationError",
    "EventSourceAutomationRunResult",
    "EventSourceAutomationService",
    "EventSourceStateRepositoryUnavailable",
    "get_event_source_automation_service",
    "reset_event_source_automation_service_for_tests",
]
