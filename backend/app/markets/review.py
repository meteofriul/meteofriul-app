"""Persistent monthly research reminder, separate from automatic fact updates."""
from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

ROME = ZoneInfo("Europe/Rome")
START = 2026 * 12 + 10  # November 2026; quarterly research from February 2027.


def scheduled_at(month):
    year, index = divmod(month, 12)
    first = datetime(year, index + 1, 1, 9, tzinfo=ROME)
    return first + timedelta(days=(-first.weekday()) % 7)


def period(month):
    year, index = divmod(month, 12)
    return f"{year:04d}-{index + 1:02d}"


def reminder(record, *, now=None):
    now = (now or datetime.now(ROME)).astimezone(ROME)
    month = now.year * 12 + now.month - 1
    latest = month if now >= scheduled_at(month) else month - 1
    completed = record.get("manualReview", {})
    through = completed.get("completedPeriod")
    last = int(through[:4]) * 12 + int(through[5:7]) - 1 if through else START - 1
    first_pending = max(START, last + 1)
    due = latest >= first_pending
    next_month = latest + 1 if due else first_pending
    quarterly = due and any(index > START and (index - START) % 3 == 0
                            for index in range(first_pending, latest + 1))
    return {"due": due, "period": period(latest) if due else None,
            "dueAt": scheduled_at(first_pending).isoformat(),
            "nextDueAt": scheduled_at(next_month).isoformat(),
            "kind": "quarterly" if quarterly else "monthly",
            "lastCompletedAt": completed.get("completedAt"),
            "lastCompletedPeriod": through, "timezone": "Europe/Rome"}


def review_queue(record):
    """Use per-market results: a partial job must not hide other unresolved sources."""
    queue = []
    state = record["state"]
    for market in state["markets"]:
        if market["status"] in {"archived", "suspended"}:
            continue
        meta = record.get("refreshLedger", {}).get(market["id"], {})
        issues = list(meta.get("issues", []))
        if not meta.get("lastAttempt"):
            issues.append("not_checked")
        if (market.get("evidenceStatus") == "conflict" or
                market.get("evidenceStatus") != "documented" and "conflitt" in str(market.get("quality", "")).lower()):
            issues.append("known_calendar_conflict")
        if meta.get("considerations"):
            issues.append("source_considerations")
        if not issues:
            continue
        urls = [market.get("url"), *meta.get("sources", {})]
        sources = list(market.get("sources", []))
        for practice in state["drafts"]:
            if (market["id"] in practice.get("linkedMarketIds", []) or
                    practice["id"] == market.get("researchId") or
                    practice["id"] in market.get("researchIds", [])):
                sources.extend(practice.get("sources", []))
        urls.extend(source.get("url") for source in sources if isinstance(source, dict))
        priority = any("conflict" in issue or "identity" in issue for issue in issues)
        queue.append({"marketId": market["id"], "name": market["name"], "comune": market["comune"],
                      "issues": sorted(set(issues)), "priority": priority,
                      "lastAttempt": meta.get("lastAttempt"),
                      "sources": sorted({url for url in urls if isinstance(url, str) and url.startswith("https://")})})
    return sorted(queue, key=lambda item: (not item["priority"], item["comune"].casefold(), item["name"].casefold()))
