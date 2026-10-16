from __future__ import annotations

import json
import os

from app.services.dpc_national_source import DpcNationalSourceError
from app.services.national_official_alerts_state import (
    NationalOfficialAlertsUnavailable,
    get_national_official_alerts_state_service,
)


def main() -> int:
    require_persistent = (
        os.getenv("NATIONAL_OFFICIAL_ALERTS_REQUIRE_PERSISTENT_STORAGE", "true")
        .strip()
        .lower()
        in {"1", "true", "yes", "on"}
    )
    try:
        result = get_national_official_alerts_state_service().refresh()
        persistent_ok = result.stored_in == "firestore" or not require_persistent
        deferred = result.reason == "source_cap_not_public_held"
        successful_reason = result.reason in {
            "stored", "already_current", "source_cap_not_public_held"
        }
        success = persistent_ok and successful_reason
        payload = {
            "status": "deferred" if success and deferred else "ok" if success else "failed",
            "reason": result.reason,
            "refreshed": result.refreshed,
            "stored_in": result.stored_in,
            "revision": (result.payload.get("revision") or {}).get(
                "source_revision"
            ),
            "zone_count": int(result.payload.get("zone_count") or 0),
            "record_count": len(result.payload.get("records") or []),
            "active": bool(result.payload.get("active")),
            "push": "disabled_by_design",
        }
    except (DpcNationalSourceError, NationalOfficialAlertsUnavailable) as error:
        success = False
        payload = {
            "status": "failed",
            "reason": str(error),
            "refreshed": False,
            "stored_in": "unchanged",
            "push": "disabled_by_design",
        }
    print(json.dumps(payload, ensure_ascii=True, sort_keys=True))
    return 0 if success else 1


if __name__ == "__main__":
    raise SystemExit(main())
