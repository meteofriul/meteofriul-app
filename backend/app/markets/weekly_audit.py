"""Read-only comparison of every online market with its documented sources.

The archive is never mutated. Only a separate report store may be written.
"""
from __future__ import annotations

import copy
from datetime import datetime, timedelta, timezone
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
    """Ignore wording or a documented 30-minute opening window."""
    if not isinstance(before, str) or not isinstance(after, str):
        return False
    times = lambda text: [f"{int(hour):02}:{minute}" for hour, minute in
                          re.findall(r"\b([01]?\d|2[0-3])[:.]([0-5]\d)\b", text)]
    old_times, new_times = times(before), times(after)
    if not old_times or len(old_times) != len(new_times):
        return False
    if old_times != new_times:
        note = market.get("scheduleNote", "")
        note_times = times(note)
        opening_window = (len(old_times) == 2 and old_times[1] == new_times[1]
                          and re.search(r"\b(?:tra|fra)\b", note, re.IGNORECASE)
                          and old_times[0] in note_times and new_times[0] in note_times
                          and abs(int(old_times[0][:2]) * 60 + int(old_times[0][3:])
                                  - int(new_times[0][:2]) * 60 - int(new_times[0][3:])) <= 30)
        if not opening_window:
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


def _location_tokens(value, *, comune=""):
    plain = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode().lower()
    words = re.findall(r"[a-z0-9]+", plain)
    town = re.findall(r"[a-z0-9]+", unicodedata.normalize("NFKD", comune).encode("ascii", "ignore").decode().lower())
    if town and words[-len(town):] == town:
        words = words[:-len(town)]
    return [word for word in words if not re.fullmatch(r"\d{5}", word)]


def _same_place(before, after, market):
    """Treat postcode, town suffix and punctuation as address formatting."""
    if not isinstance(before, str) or not isinstance(after, str):
        return False
    old = _location_tokens(before, comune=market.get("comune", ""))
    return bool(old) and old == _location_tokens(after, comune=market.get("comune", ""))


def _same_directions(before, after, market, source_place):
    """A route to the named complex is valid when the precise venue agrees."""
    if not all(isinstance(value, str) for value in (before, after, source_place)):
        return False
    if not _same_place(market.get("place"), source_place, market):
        return False
    old = _location_tokens(before)
    new = _location_tokens(after)
    return len(old) >= 3 and set(old).issubset(set(new))


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
        source_places = {item.get("sourceUrl"): item.get("fields", {}).get("place")
                         for item in collected.get("observations", [])}
        changes = []
        for change in plan["audit"][-1]["changes"]:
            if change["collection"] == "markets":
                field = change["fields"]
                if field == ["hours"] and _same_hours(change["before"], change["after"], market):
                    continue
                if field == ["place"] and _same_place(change["before"], change["after"], market):
                    continue
                if field == ["directionsQuery"] and _same_directions(
                        change["before"], change["after"], market,
                        source_places.get(change.get("sourceUrl"))):
                    continue
            changes.append(change)
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
        self.client = client
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

    @staticmethod
    def _review_id(market_id, source_url):
        return hashlib.sha256((market_id + "\n" + source_url).encode("utf-8")).hexdigest()

    def _reviews(self):
        return self.root.document("manual_reviews").collection("items")

    def reviews(self):
        latest = self.latest()
        if not latest:
            return []
        # The runtime role intentionally has entities.get but not entities.list.
        # Read only review documents named by sources in the current report.
        refs = [self._reviews().document(self._review_id(market["marketId"], source["url"]))
                for market in latest["markets"] for source in market.get("sources", [])]
        result = []
        for start in range(0, len(refs), 100):
            result.extend(item.to_dict() for item in self.client.get_all(refs[start:start + 100], timeout=15)
                          if item.exists)
        return result

    def save_review(self, *, market_id, source_url, outcome, note, report_run_id,
                    operation_id, now=None):
        latest = self.latest()
        if not latest or latest["runId"] != report_run_id:
            raise MarketError("markets_audit_report_stale", 409)
        detail = self.market(market_id)
        source = next((item for item in (detail or {}).get("sources", [])
                       if item.get("url") == source_url), None)
        if source is None:
            raise MarketError("markets_audit_source_missing", 404)
        if outcome not in {"verified", "needs_correction", "replace_source"}:
            raise MarketError("markets_audit_review_invalid")
        note = note.strip() if isinstance(note, str) else ""
        if not 5 <= len(note) <= 500:
            raise MarketError("markets_audit_review_note_invalid")
        ref = self._reviews().document(self._review_id(market_id, source_url))
        previous = ref.get(timeout=15)
        if previous.exists and (previous.to_dict() or {}).get("operationId") == operation_id:
            return previous.to_dict()
        checked_at = now or datetime.now(timezone.utc)
        if checked_at.tzinfo is None:
            raise MarketError("markets_audit_review_time_invalid")
        iso = lambda value: value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
        review = {"marketId": market_id, "sourceUrl": source_url,
                  "outcome": outcome, "note": note, "checkedAt": iso(checked_at),
                  "reviewUntil": iso(checked_at + timedelta(days=90)),
                  "sourceStatus": source["status"],
                  "sourceHash": source.get("contentHash") if source["status"] in {"read", "document"} else None,
                  "archiveRevision": latest["archiveRevision"], "reportRunId": report_run_id,
                  "operationId": operation_id}
        ref.set(review, timeout=15)
        return review

    def save(self, report):
        if report["status"] != "completed" or report["checkedMarkets"] != report["totalMarkets"]:
            raise MarketError("markets_audit_incomplete")
        run = self.root.document("run-" + report["runId"])
        for market_id, detail in report["details"].items():
            run.collection("markets").document(self._id(market_id)).set(detail, timeout=15)
        summary = {key: value for key, value in report.items() if key != "details"}
        self.root.document("latest").set({"report": summary}, timeout=15)
        return summary
