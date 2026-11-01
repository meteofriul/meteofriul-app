"""Unattended online research for the existing Markets archive.

python -m app.markets.refresh_job --apply --report <private-local-report.json>
Without --apply, retrieve sources and compute a preview without any write.
"""
from __future__ import annotations

import argparse
import copy
from datetime import datetime
import json
import os
from pathlib import Path
import sys
import time
import uuid
from zoneinfo import ZoneInfo

from .model import MarketError, timestamp
from .refresh import apply_refresh, due_markets
from .repository import configured_repository
from .service import MarketsService


def sources_for(state, market):
    sources = list(market.get("sources", []))
    for practice in state["drafts"]:
        if (market["id"] in practice.get("linkedMarketIds", []) or
                practice["id"] == market.get("researchId") or
                practice["id"] in market.get("researchIds", [])):
            sources.extend(practice.get("sources", []))
    unique = {}
    for source in sources:
        if isinstance(source, dict) and source.get("url"):
            unique[source["url"]] = copy.deepcopy(source)
    return list(unique.values())


def run(service, *, as_of, apply=False, force=False, market_ids=(), limit=2000, collector=None, max_seconds=1800, clock=time.monotonic):
    if collector is None:
        from .refresh_sources import collect_market
        collector = collect_market
    if not 1 <= limit <= 2000:
        raise MarketError("markets_refresh_limit_invalid")
    record = service.repository.read()
    available = {item["id"] for item in record["state"]["markets"]}
    if set(market_ids) - available:
        raise MarketError("markets_refresh_unknown_market")
    selected = record["state"]["markets"] if force else due_markets(record, as_of)
    selected = [item for item in selected if item["status"] not in {"archived", "suspended"}
                and (not market_ids or item["id"] in market_ids)][:limit]
    if not 60 <= max_seconds <= 2100:
        raise MarketError("markets_refresh_duration_invalid")
    started = clock()
    results = []
    for market in selected:
        if results and clock() - started >= max_seconds:
            break
        editions = [item for item in record["state"]["dates"] if item["marketId"] == market["id"]]
        try:
            result = collector(copy.deepcopy(market), copy.deepcopy(editions), sources_for(record["state"], market), as_of=as_of)
            if result.get("marketId") != market["id"]:
                raise ValueError("collector_identity")
        except Exception:
            # Exception messages can contain credentials or response bodies.
            result = {"marketId": market["id"], "observations": [], "issues": ["collector_failure"]}
        results.append(result)
    if not results:
        return {"status": "not_due", "applied": False, "revisionBefore": record["revision"],
                "revisionAfter": record["revision"], "checkedMarkets": 0, "changes": 0,
                "publicationEnabled": False, "at": timestamp(), "reports": []}
    plan = apply_refresh(record, results, as_of=as_of, now=timestamp())
    if apply:
        # A panel edit during acquisition must never be silently overwritten.
        # Leave a conflict for the next scheduled retry against a fresh state.
        saved = service.refresh(results, expected_revision=record["revision"],
                                operation_id="refresh-" + uuid.uuid4().hex, as_of=as_of)
        summary = saved["automation"]
        revision_after = saved["revision"]
    else:
        summary, revision_after = plan["automation"], record["revision"]
    status = "completed_with_issues" if summary["marketsWithIssues"] else "completed"
    if not any(item["confirmedFacts"] for item in summary["reports"]):
        status = "completed_without_facts"
    return {**summary, "status": status, "remainingMarkets": len(selected) - len(results),
            "budgetExhausted": len(results) < len(selected),
            "applied": apply, "revisionBefore": record["revision"], "revisionAfter": revision_after,
            "changesDetail": plan["audit"][-1]["changes"]}


def _write_report(path, report):
    target = Path(path).resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(target.name + "." + uuid.uuid4().hex + ".tmp")
    temporary.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(target)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Save documented changes without confirmation; never publish")
    parser.add_argument("--force", action="store_true", help="Check also markets not due yet")
    parser.add_argument("--market-id", action="append", default=[])
    parser.add_argument("--limit", type=int, default=2000)
    parser.add_argument("--report")
    args = parser.parse_args(argv)
    try:
        if os.getenv("K_SERVICE") or os.getenv("CLOUD_RUN_JOB"):
            project = os.getenv("MARKETS_FIREBASE_PROJECT_ID", "").strip()
            if (os.getenv("MARKETS_STORAGE", "").strip().lower() != "firestore" or not project
                    or os.getenv("FIREBASE_PROJECT_ID", "").strip() != project
                    or os.getenv("MARKETS_ADMIN_LOCAL_TOKEN", "").strip()
                    or os.getenv("MARKETS_SQLITE_PATH", "").strip()):
                raise MarketError("markets_refresh_cloud_configuration_invalid")
        if not (os.getenv("K_SERVICE") or os.getenv("CLOUD_RUN_JOB")) and os.getenv("MARKETS_STORAGE", "sqlite") == "sqlite":
            default = Path(__file__).resolve().parents[3] / ".dev-logs/markets/archive.sqlite3"
            path = Path(os.getenv("MARKETS_SQLITE_PATH") or default)
            if not path.is_file():
                raise MarketError("markets_refresh_archive_missing")
        report = run(MarketsService(configured_repository()),
                     as_of=datetime.now(ZoneInfo("Europe/Rome")).date(), apply=args.apply,
                     force=args.force, market_ids=args.market_id, limit=args.limit)
    except MarketError as error:
        uncertain = args.apply and error.detail["code"] == "markets_storage_unavailable"
        report = {"status": "failed", "issue": error.detail["code"], "applied": None if uncertain else False,
                  "commitUnknown": uncertain, "at": timestamp()}
    except Exception:
        report = {"status": "failed", "issue": "unexpected_failure", "applied": False, "at": timestamp()}
    if args.report:
        _write_report(args.report, report)
    # Only counts and codes on stdout. Research details stay in the local report
    # and authenticated archive history, not infrastructure logs.
    print(json.dumps({key: value for key, value in report.items() if key not in {"reports", "changesDetail"}}, ensure_ascii=True))
    return 1 if report["status"] == "failed" else 2 if report["status"] == "completed_without_facts" else 0


if __name__ == "__main__":
    sys.exit(main())
