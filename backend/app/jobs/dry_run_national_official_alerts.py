"""Read-only national Play candidate audit; never sends or claims deliveries.

This entrypoint is separate from the scheduled national snapshot sync and the
live FVG notification writer.  It is not wired to a scheduler or deploy script.
"""

from __future__ import annotations

import json

from app.infrastructure.firebase import get_firestore_client
from app.repositories.national_official_alerts import (
    NationalOfficialAlertSnapshotRepository,
)
from app.repositories.push import PushDeviceRepository, PushRepositoryUnavailable
from app.services.national_alert_push_dry_run import (
    NationalAlertDryRunPolicy,
    NationalAlertDryRunUnavailable,
    evaluate_national_alert_push_dry_run,
)
from app.services.push import PushConfigurationError, PushPilotConfig


def main() -> int:
    try:
        config = PushPilotConfig.from_environment()
        if (
            config.mode != "dry_run"
            or config.enrollment_mode != "play_beta"
            or config.min_app_version_code is None
        ):
            raise NationalAlertDryRunUnavailable("dry_run_mode_required")
        policy = NationalAlertDryRunPolicy(
            enrollment_generation=config.enrollment_generation,
            android_app_ids=config.android_app_ids,
            min_app_version_code=config.min_app_version_code,
        )
        snapshot, storage = NationalOfficialAlertSnapshotRepository(
            firestore_provider=get_firestore_client,
        ).load()
        # The evaluator checks persistence and source integrity before it can
        # produce any candidate count.  The device reader never writes.
        devices = PushDeviceRepository(get_firestore_client).read_active_devices(
            max_devices=config.max_devices,
            enrollment_generation=config.enrollment_generation,
        )
        summary = evaluate_national_alert_push_dry_run(
            snapshot,
            devices.devices,
            storage=storage,
            policy=policy,
        )
        summary["pages_processed"] = devices.pages_processed
    except (
        NationalAlertDryRunUnavailable,
        PushConfigurationError,
        PushRepositoryUnavailable,
    ) as error:
        print(json.dumps({
            "status": "failed",
            "reason": str(error),
            "push": "disabled_by_design",
            "sent": 0,
        }, sort_keys=True))
        return 1
    except Exception:
        # Never print a traceback that might include a stored delivery target.
        print(json.dumps({
            "status": "failed",
            "reason": "national_dry_run_internal_error",
            "push": "disabled_by_design",
            "sent": 0,
        }, sort_keys=True))
        return 1
    print(json.dumps(summary, ensure_ascii=True, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
