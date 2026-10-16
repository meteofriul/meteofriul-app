"""Run the owner-only local weather candidate evaluator without sending FCM."""

from __future__ import annotations

import json

from app.services.local_notice_shadow import (
    LocalNoticeShadowConfigurationError,
    LocalNoticeShadowDeviceStateUnavailable,
    LocalNoticeShadowRepositoryUnavailable,
    get_local_notice_shadow_service,
)


_SUCCESS_STATUSES = frozenset(
    {"disabled", "completed", "no_eligible_municipality"}
)


def _failure_summary(status: str) -> dict[str, int | str]:
    return {
        "status": status,
        "eligible_municipalities": 0,
        "evaluated": 0,
        "candidates": 0,
        "rejected": 0,
        "persisted": 0,
        "failed": 1,
    }


def main() -> int:
    try:
        summary = get_local_notice_shadow_service().run().summary()
    except LocalNoticeShadowConfigurationError:
        summary = _failure_summary("configuration_invalid")
    except LocalNoticeShadowDeviceStateUnavailable:
        summary = _failure_summary("device_state_unavailable")
    except LocalNoticeShadowRepositoryUnavailable:
        summary = _failure_summary("storage_unavailable")

    print(json.dumps(summary, ensure_ascii=True))
    succeeded = (
        summary.get("status") in _SUCCESS_STATUSES
        and int(summary.get("failed") or 0) == 0
    )
    return 0 if succeeded else 1


if __name__ == "__main__":
    raise SystemExit(main())
