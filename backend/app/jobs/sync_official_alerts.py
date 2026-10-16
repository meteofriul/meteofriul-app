from __future__ import annotations

import json
import os

from app.repositories.push import PushRepositoryUnavailable
from app.services.official_alerts import get_official_alerts_state_service
from app.services.push import PushConfigurationError, get_push_pilot_service
from app.weather.alerts_engine import sanitize_official_alerts_upstream_failure


def main() -> int:
    result = get_official_alerts_state_service().refresh()
    require_persistent_storage = (
        os.getenv("OFFICIAL_ALERTS_REQUIRE_PERSISTENT_STORAGE", "false")
        .strip()
        .lower()
        in {"1", "true", "yes", "on"}
    )
    persisted = result.stored_in == "firestore"
    refresh_succeeded = result.refreshed and (
        persisted or not require_persistent_storage
    )
    push_summary = {
        "status": "skipped_refresh_failed",
        "attempted": 0,
        "sent": 0,
        "sent_unconfirmed": 0,
        "deduplicated": 0,
        "failed": 0,
        "pages_processed": 0,
        "delivery_batches": 0,
    }
    push_succeeded = True
    push_required = (
        os.getenv("PUSH_OFFICIAL_ALERTS_REQUIRED", "false").strip().lower()
        in {"1", "true", "yes", "on"}
    )
    if refresh_succeeded:
        try:
            push_result = get_push_pilot_service().dispatch_official_alerts(
                result.payload
            )
            push_summary = push_result.summary()
            push_succeeded = (
                push_result.status not in {
                    "failed",
                    "partial",
                    "sent_unconfirmed",
                    "source_unavailable",
                    "storage_unavailable",
                }
                and int(push_summary.get("failed") or 0) == 0
                and int(push_summary.get("sent_unconfirmed") or 0) == 0
            )
            if push_required and push_result.status in {"disabled", "dry_run"}:
                push_summary = {**push_summary, "status": "send_mode_required"}
                push_succeeded = False
        except PushConfigurationError:
            push_summary = {**push_summary, "status": "configuration_invalid"}
            push_succeeded = False
        except PushRepositoryUnavailable:
            push_summary = {**push_summary, "status": "storage_unavailable"}
            push_succeeded = False
    upstream_failure = sanitize_official_alerts_upstream_failure(
        (result.payload.get("cache") or {}).get("upstream_failure")
    )
    print(
        json.dumps(
            {
                "active": bool(result.payload.get("active")),
                "cache_status": (result.payload.get("cache") or {}).get("status"),
                "count": int(result.payload.get("count") or 0),
                "refreshed": result.refreshed,
                "source_mode": result.payload.get("source_mode"),
                "stored_in": result.stored_in,
                "upstream_failure": upstream_failure,
                "push": push_summary,
            },
            ensure_ascii=True,
        )
    )
    return 0 if refresh_succeeded and push_succeeded else 1


if __name__ == "__main__":
    raise SystemExit(main())
