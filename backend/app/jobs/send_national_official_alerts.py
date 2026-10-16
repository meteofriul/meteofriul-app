"""Separate national DPC notification job; never invoked by the FVG sync."""

from __future__ import annotations

import json

from app.repositories.push import PushRepositoryUnavailable
from app.services.national_alert_delivery import (
    NationalAlertDeliveryUnavailable,
    get_national_alert_delivery_service,
)
from app.services.national_alert_push_dry_run import NationalAlertDryRunUnavailable
from app.services.push import PushConfigurationError


_SUCCESS = frozenset({
    "disabled", "dry_run", "no_candidate", "sent", "deduplicated", "in_progress"
})


def main() -> int:
    try:
        summary = get_national_alert_delivery_service().run()
    except (
        NationalAlertDeliveryUnavailable,
        NationalAlertDryRunUnavailable,
        PushConfigurationError,
        PushRepositoryUnavailable,
    ) as error:
        summary = {"status": "failed", "reason": str(error), "sent": 0, "failed": 1}
    except Exception:
        # Never expose a token, device ID, Firestore document or exception body.
        summary = {
            "status": "failed",
            "reason": "national_alert_internal_error",
            "sent": 0,
            "failed": 1,
        }
    print(json.dumps(summary, ensure_ascii=True, sort_keys=True))
    return 0 if summary.get("status") in _SUCCESS and not summary.get("failed") else 1


if __name__ == "__main__":
    raise SystemExit(main())
