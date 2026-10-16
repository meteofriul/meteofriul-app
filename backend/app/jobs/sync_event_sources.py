"""Refresh guarded official event sources without publishing them."""

from __future__ import annotations

import json

from app.repositories.event_sources import EventSourceStateRepositoryUnavailable
from app.services.event_sources import (
    EventSourceAutomationConfigurationError,
    get_event_source_automation_service,
)


def _failure_summary(status: str) -> dict:
    return {
        "status": status,
        "storage": "",
        "approved": 0,
        "pending": 0,
        "quarantined": 0,
        "duplicates": 0,
        "publication_enabled": False,
        "incident_active": True,
        "alert_transition": "configuration_error",
        "alert_email_to": "info@meteofriul.it",
        "issues": [status],
        "incident_details": [],
        "active_catalog_coverage": {},
    }


def main() -> int:
    try:
        summary = get_event_source_automation_service().run().summary()
    except EventSourceAutomationConfigurationError:
        summary = _failure_summary("configuration_invalid")
    except EventSourceStateRepositoryUnavailable:
        summary = _failure_summary("storage_unavailable")
    except Exception:
        summary = _failure_summary("unexpected_failure")

    severity = "ERROR" if summary.get("incident_active") else "INFO"
    payload = {
        **summary,
        "severity": severity,
        "event": (
            "event_source_automation_incident"
            if summary.get("incident_active")
            else "event_source_automation_completed"
        ),
        "notification_transport": "cloud_monitoring_email",
    }
    print(json.dumps(payload, ensure_ascii=True, sort_keys=True))
    return 1 if summary.get("incident_active") else 0


if __name__ == "__main__":
    raise SystemExit(main())
