from __future__ import annotations

import json

from app.repositories.push import PushRepositoryUnavailable
from app.services.push import PushConfigurationError, get_push_pilot_service


def main() -> int:
    try:
        result = get_push_pilot_service().send_pilot_test()
        summary = result.summary()
        success = result.status == "sent" and result.sent == 1
    except PushConfigurationError:
        summary = {
            "status": "configuration_invalid",
            "attempted": 0,
            "sent": 0,
            "sent_unconfirmed": 0,
            "deduplicated": 0,
            "failed": 0,
        }
        success = False
    except PushRepositoryUnavailable:
        summary = {
            "status": "storage_unavailable",
            "attempted": 0,
            "sent": 0,
            "sent_unconfirmed": 0,
            "deduplicated": 0,
            "failed": 0,
        }
        success = False

    print(json.dumps(summary, ensure_ascii=True))
    return 0 if success else 1


if __name__ == "__main__":
    raise SystemExit(main())
