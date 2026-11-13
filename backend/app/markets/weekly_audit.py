"""Read-only comparison of every online market with its documented sources.

The archive is never mutated. Only a separate report store may be written.
"""
from __future__ import annotations

import copy
from datetime import datetime
import hashlib
import re
import time
import unicodedata
import uuid

from .model import MarketError, timestamp
from .refresh import apply_refresh
from .refresh_job import sources_for


_DAYS = {name: index for index, name in enumerate(
    ("lunedi", "martedi", "mercoledi", "giovedi", "venerdi", "sabato", "domenica"), 1)}


def _same_hours(before, after, market):
    """Ignore wording changes only when times and named weekdays still agree."""
    if not isinstance(before, str) or not isinstance(after, str):
        return False
    times = lambda text: [f"{int(hour):02}:{minute}" for hour, minute in
                          re.findall(r"\b([01]?\d|2[0-3])[:.]([0-5]\d)\b", text)]
    old_times, new_times = times(before), times(after)
    if not old_times or old_times != new_times:
        return False
    def days(text):
        plain = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()
        return [_DAYS[name] for name in re.findall(r"\b(?:lunedi|martedi|mercoledi|giovedi|venerdi|sabato|domenica)\b", plain)]
    old_days, new_days = days(before), days(after)
    if old_days and new_days:
        return old_days == new_days
    if old_days or new_days:
        expected = market.get("weekdaysIso") or []
        return len(old_times) == 2 and len(expected) == 1 and (old_days or new_days) == expected
    return True


def scan(repository, *, as_of, collector=None, previous=None, max_seconds=1800,
         clock=time.monotonic):
    if collector is None:
        from .refresh_sources import collect_market
        collector = collect_market
    if not 60 <= max_seconds <= 3600:
        raise MarketError("markets_audit_duration_invalid")
    record = repository.read()
    state = record["state"]
    markets = sorted(state["markets"], key=lambda item: (item.get("comune", ""), item.get("name", ""), item["id"]))
    previous_checks = {entry["marketId"]: {source["url"]: source for source in entry.get("sources", [])}
                       for entry in (previous or {}).get("markets", [])}
    started = clock()
    details = {}
    summaries = []
    for market in markets:
        if summaries and clock() - started >= max_seconds:
            break
        editions = [item for item in state["dates"] if item["marketId"] == market["id"]]
        try:
            collected = collector(copy.deepcopy(market), copy.deepcopy(editions),
                                  sources_for(state, market), as_of=as_of)
            if collected.get("marketId") != market["id"]:
                raise ValueError("collector_identity")
        except Exception:
            # Never expose exception text: it may contain credentials or HTML.
            collected = {"marketId": market["id"], "observations": [],
                         "issues": ["collector_failure"], "sourceChecks": []}
        trial = copy.deepcopy(record)
        # The old apply path deliberately skips inactive cards. For a comparison
        # only, make the copied target eligible; retain its real status in output.
        target = next(item for item in trial["state"]["markets"] if item["id"] == market["id"])
        if target["status"] in {"suspended", "archived"}:
            target["status"] = "draft"
        plan = apply_refresh(trial, [collected], as_of=as_of, now=timestamp())
        entry = plan["automation"]["reports"][0]
        checks = copy.deepcopy(collected.get("sourceChecks", []))
        before_checks = previous_checks.get(market["id"], {})
        for source in checks:
            old = before_checks.get(source.get("url"), {})
            source["contentChanged"] = bool(source.get("status") in {"read", "document"}
                                            and old.get("status") == source.get("status")
                                            and old.get("hashMethod") and old.get("hashMethod") == source.get("hashMethod")
                                            and old.get("contentHash") and source.get("contentHash")
                                            and old["contentHash"] != source["contentHash"])
        changes = [change for change in plan["audit"][-1]["changes"]
                   if not (change["collection"] == "markets" and change["fields"] == ["hours"]
                           and _same_hours(change["before"], change["after"], market))]
        summary = {"marketId": market["id"], "name": market["name"], "comune": market["comune"],
                   "status": market["status"], "changes": len(changes),
                   "confirmedFacts": entry["confirmedFacts"], "issues": entry["issues"],
                   "sources": checks}
        summaries.append(summary)
        details[market["id"]] = {**summary, "changesDetail": changes[:100],
                                 "changesTruncated": len(changes) > 100,
                                 "considerations": entry.get("considerations", [])}
    complete = len(summaries) == len(markets)
    # An edit during the scan invalidates the comparison. A later edit is
    # visible in the panel because the report retains its archive revision.
    current_revision = repository.read()["revision"]
    return {"runId": uuid.uuid4().hex, "at": timestamp(), "asOf": as_of.isoformat(),
            "archiveRevision": record["revision"], "currentRevision": current_revision,
            "status": "completed" if complete and current_revision == record["revision"]
                      else "archive_changed" if current_revision != record["revision"] else "partial",
            "checkedMarkets": len(summaries), "totalMarkets": len(markets),
            "changedMarkets": sum(item["changes"] > 0 for item in summaries),
            "marketsWithIssues": sum(bool(item["issues"]) for item in summaries),
            "publicationEnabled": False, "markets": summaries, "details": details}


class FirestoreWeeklyAuditStore:
    """A separate namespace. The latest pointer is written after all details."""

    def __init__(self, client, collection="markets_weekly_audit"):
        if not collection or "/" in collection or collection == "markets_archive":
            raise MarketError("markets_audit_collection_invalid", 503)
        self.root = client.collection(collection)

    @staticmethod
    def _id(market_id):
        return hashlib.sha256(market_id.encode("utf-8")).hexdigest()

    def latest(self):
        snapshot = self.root.document("latest").get(timeout=15)
        return (snapshot.to_dict() or {}).get("report") if snapshot.exists else None

    def market(self, market_id):
        latest = self.latest()
        if not latest:
            return None
        ref = self.root.document("run-" + latest["runId"]).collection("markets").document(self._id(market_id))
        snapshot = ref.get(timeout=15)
        result = snapshot.to_dict() if snapshot.exists else None
        return result if result and result.get("marketId") == market_id else None

    def save(self, report):
        if report["status"] != "completed" or report["checkedMarkets"] != report["totalMarkets"]:
            raise MarketError("markets_audit_incomplete")
        run = self.root.document("run-" + report["runId"])
        for market_id, detail in report["details"].items():
            run.collection("markets").document(self._id(market_id)).set(detail, timeout=15)
        summary = {key: value for key, value in report.items() if key != "details"}
        self.root.document("latest").set({"report": summary}, timeout=15)
        return summary
