"""Send the next-day evening preview to verified notification subscribers."""

from __future__ import annotations

import json

from app.repositories.push import PushRepositoryUnavailable
from app.services.evening_forecast_delivery import (
    EveningForecastConfigurationError,
    get_evening_forecast_delivery_service,
)
from app.services.local_notice_delivery import (
    LocalNoticeDeliveryDeviceStateUnavailable,
)


_SUCCESS_STATUSES = frozenset(
    {
        "disabled",
        "no_eligible_device",
        "no_forecast",
        "dry_run",
        "sent",
        "deduplicated",
        "in_progress",
        "retry_scheduled",
        "opted_out",
    }
)


def _failure_summary(status: str) -> dict[str, int | str]:
    return {
        "status": status,
        "eligible_devices": 0,
        "evaluated": 0,
        "attempted": 0,
        "sent": 0,
        "sent_unconfirmed": 0,
        "deduplicated": 0,
        "failed": 1,
        "groups": 0,
        "failed_groups": 0,
        "in_progress": 0,
        "retry_scheduled": 0,
        "opted_out": 0,
        "duplicate_targets": 0,
        "security_failed": 0,
        "device_failed": 0,
        "storage_failed": 0,
        "source_failed": 0,
        "pages_processed": 0,
        "delivery_batches": 0,
    }


def main() -> int:
    try:
        summary = get_evening_forecast_delivery_service().run().summary()
    except EveningForecastConfigurationError:
        summary = _failure_summary("configuration_invalid")
    except LocalNoticeDeliveryDeviceStateUnavailable:
        summary = _failure_summary("device_state_unavailable")
    except PushRepositoryUnavailable:
        summary = _failure_summary("delivery_storage_unavailable")

    print(json.dumps(summary, ensure_ascii=True))
    succeeded = (
        summary.get("status") in _SUCCESS_STATUSES
        and int(summary.get("failed") or 0) == 0
    )
    return 0 if succeeded else 1


if __name__ == "__main__":
    raise SystemExit(main())
