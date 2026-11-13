"""One-shot weekly Markets source comparison. No archive or app writes."""
from __future__ import annotations

from datetime import datetime
import json
import os
import sys
from zoneinfo import ZoneInfo

from .model import MarketError
from .repository import configured_repository
from .weekly_audit import FirestoreWeeklyAuditStore, scan


def main():
    try:
        project = os.getenv("MARKETS_FIREBASE_PROJECT_ID", "").strip()
        if (os.getenv("MARKETS_STORAGE", "").strip().lower() != "firestore" or not project
                or os.getenv("FIREBASE_PROJECT_ID", "").strip() != project
                or os.getenv("MARKETS_ADMIN_LOCAL_TOKEN", "").strip()
                or os.getenv("MARKETS_SQLITE_PATH", "").strip()):
            raise MarketError("markets_audit_cloud_configuration_invalid")
        repository = configured_repository()
        if repository.storage != "firestore":
            raise MarketError("markets_audit_cloud_configuration_invalid")
        store = FirestoreWeeklyAuditStore(repository.db)
        report = scan(repository, as_of=datetime.now(ZoneInfo("Europe/Rome")).date(),
                      previous=store.latest())
        if report["status"] == "completed":
            store.save(report)
        result = {"status": report["status"], "checkedMarkets": report["checkedMarkets"],
                  "totalMarkets": report["totalMarkets"], "changedMarkets": report["changedMarkets"],
                  "marketsWithIssues": report["marketsWithIssues"]}
    except MarketError as error:
        result = {"status": "failed", "issue": error.detail["code"]}
    except Exception:
        result = {"status": "failed", "issue": "unexpected_failure"}
    print(json.dumps(result))
    return 0 if result["status"] == "completed" else 1


if __name__ == "__main__":
    sys.exit(main())
