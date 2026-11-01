"""Merge documented online facts, keeping the archive and its editorial context.

No network or publication happens here. The scheduler collects observations
first; the service applies this function behind the existing revision/CAS gate.
"""
from __future__ import annotations

import copy
import hashlib
import re
import unicodedata
from datetime import date, datetime, timedelta
from calendar import monthrange

from .model import MarketError, encode, validate_state, valid_date, valid_url
from .seed import edition_id


FIELDS = frozenset({"place", "directionsQuery", "hours", "cadence", "weekdaysIso",
                    "validFrom", "validThrough"})
EDITION_FIELDS = ("date", "status", "venue")


def fingerprint(value):
    return hashlib.sha256(encode(value)).hexdigest()


def _less_specific(field, before, after):
    """An address omitting a known sub-location is not evidence of its removal."""
    if field == "venue" and isinstance(before, dict) and isinstance(after, dict):
        before, after = before.get("place"), after.get("place")
    elif field not in {"place", "directionsQuery"}:
        return False
    if not isinstance(before, str) or not isinstance(after, str):
        return False
    def words(text):
        plain = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()
        return set(re.findall(r"[a-z0-9]+", plain))
    old, new = words(before), words(after)
    return bool(new) and new < old


def next_month(day):
    year, month = (day.year + 1, 1) if day.month == 12 else (day.year, day.month + 1)
    return date(year, month, min(day.day, monthrange(year, month)[1]))


def due_markets(record, as_of):
    """Daily invocation, monthly research, weekly checks for near editions/expiry."""
    ledger = record.get("refreshLedger", {})
    selected = []
    for market in record["state"]["markets"]:
        if market["status"] in {"archived", "suspended"}:
            continue
        previous = ledger.get(market["id"], {})
        attempt = previous.get("lastAttempt")
        if not attempt:
            selected.append(market)
            continue
        last = date.fromisoformat(attempt)
        near = any(as_of <= date.fromisoformat(item["date"]) <= as_of + timedelta(days=30)
                   for item in record["state"]["dates"]
                   if item["marketId"] == market["id"] and item["status"] not in {"cancelled", "postponed"})
        validity = market.get("validThrough")
        expiring = bool(validity and date.fromisoformat(validity) <= as_of + timedelta(days=30))
        if previous.get("retryable"):
            due = last + timedelta(days=1)
        elif near or expiring:
            due = last + timedelta(days=7)
        else:
            due = next_month(last)
        if as_of >= due:
            selected.append(market)
    return sorted(selected, key=lambda item: (ledger.get(item["id"], {}).get("lastAttempt", ""), item["id"]))


def _proof(observation, field, value):
    for proof in observation.get("evidence", []):
        if not isinstance(proof, dict):
            raise MarketError("markets_refresh_evidence_invalid")
        if proof.get("field") != field or not str(proof.get("excerpt") or "").strip():
            continue
        documented = proof.get("value")
        if documented == value or (field == "editions" and isinstance(documented, list) and value in documented):
            return str(proof["excerpt"])[:2000]
    raise MarketError("markets_refresh_evidence_required", field=field)


def _observation(observation, as_of):
    if not isinstance(observation, dict):
        raise MarketError("markets_refresh_observation_invalid")
    valid_url(observation.get("sourceUrl"))
    retrieved = datetime.fromisoformat(observation["retrievedAt"].replace("Z", "+00:00"))
    if retrieved.tzinfo is None or abs((retrieved.date() - as_of).days) > 1:
        raise MarketError("markets_refresh_retrieval_date_invalid")
    digest = observation.get("contentHash", "")
    if len(digest) != 64 or any(char not in "0123456789abcdef" for char in digest.lower()):
        raise MarketError("markets_refresh_digest_invalid")
    modified = observation.get("sourceUpdatedAt")
    if modified:
        valid_date(modified)
        if date.fromisoformat(modified) > as_of:
            raise MarketError("markets_refresh_future_source")
    if not isinstance(observation.get("fields", {}), dict) or not isinstance(observation.get("editions", []), list):
        raise MarketError("markets_refresh_observation_invalid")
    if not isinstance(observation.get("evidence", []), list):
        raise MarketError("markets_refresh_evidence_invalid")
    if len(observation.get("editions", [])) > 400 or len(observation.get("evidence", [])) > 1000:
        raise MarketError("markets_refresh_observation_too_large")


def _change(collection, item, field, value, observation, excerpt):
    before = copy.deepcopy(item.get(field))
    if before == value:
        return None
    item[field] = copy.deepcopy(value)
    return {"collection": collection, "id": item["id"], "fields": [field],
            "before": before, "after": copy.deepcopy(value),
            "sourceUrl": observation["sourceUrl"], "retrievedAt": observation["retrievedAt"],
            "contentHash": observation["contentHash"], "excerpt": excerpt}


def _edition_target(state, market_id, incoming, source):
    editions = [item for item in state["dates"] if item["marketId"] == market_id]
    source_key = incoming.get("sourceKey")
    linked = [item for item in editions if source_key and
              {"sourceUrl": source, "sourceKey": source_key} in item.get("refreshSourceKeys", [])]
    previous_date = incoming.get("previousDate")
    if not linked and previous_date:
        valid_date(previous_date)
        linked = [item for item in editions if item["date"] == previous_date]
        if len(linked) != 1:
            raise MarketError("markets_refresh_reschedule_unresolved")
    if not linked:
        linked = [item for item in editions if item["date"] == incoming["date"]]
    if len(linked) > 1:
        raise MarketError("markets_refresh_edition_ambiguous")
    return linked[0] if linked else None


def _merge_market(state, ledger, result, as_of):
    market = next(item for item in state["markets"] if item["id"] == result["marketId"])
    if market["status"] in {"archived", "suspended"}:
        return [], ["market_inactive"], 0
    changes, issues, candidates = [], list(result.get("issues", [])), {}
    known_calendar_conflict = market.get("evidenceStatus") == "conflict" or (
        market.get("evidenceStatus") != "documented" and "conflitt" in str(market.get("quality", "")).lower())
    sources = ledger.setdefault("sources", {})
    for observation in result.get("observations", []):
        _observation(observation, as_of)
        url = observation["sourceUrl"]
        prior = sources.get(url, {})
        modified = observation.get("sourceUpdatedAt", "")
        prior_date = prior.get("sourceUpdatedAt") or (market.get("checked") if not prior else "")
        if modified and prior_date and modified < prior_date:
            issues.append("older_source:" + url)
            continue
        # Keep the prior fingerprint while a conflict is unresolved. A later
        # successful run can apply it without requiring another source change.
        facts = prior.get("facts", {})
        for field, value in observation.get("fields", {}).items():
            if field not in FIELDS:
                issues.append("unsupported_field:" + field)
                continue
            if value in (None, "", []):
                issues.append("empty_field:" + field)
                continue
            if known_calendar_conflict and field in {"validFrom", "validThrough", "cadence", "weekdaysIso"}:
                issues.append("known_calendar_conflict")
                continue
            excerpt = _proof(observation, field, value)
            key = "market:" + field
            candidates.setdefault(key, []).append((observation, value, excerpt, facts.get(key)))
        for incoming in observation.get("editions", []):
            if known_calendar_conflict:
                issues.append("known_calendar_conflict")
                continue
            if not isinstance(incoming, dict):
                raise MarketError("markets_refresh_edition_invalid")
            valid_date(incoming.get("date"))
            if date.fromisoformat(incoming["date"]) < as_of:
                continue
            if incoming.get("source") not in (None, url):
                raise MarketError("markets_refresh_edition_source_mismatch")
            excerpt = _proof(observation, "editions", incoming)
            target = _edition_target(state, market["id"], incoming, url)
            identifier = target["id"] if target else edition_id(market["id"], incoming["date"])
            for field in EDITION_FIELDS:
                if field not in incoming or incoming[field] in (None, ""):
                    continue
                if field == "status" and incoming[field] not in {"published", "cancelled", "postponed"}:
                    issues.append("unconfirmed_edition:" + incoming["date"])
                    continue
                value = copy.deepcopy(incoming[field])
                if field == "venue":
                    value.setdefault("id", "venue-" + identifier)
                key = "edition:" + identifier + ":" + field
                candidates.setdefault(key, []).append((observation, value, excerpt, facts.get(key), incoming))
        sources[url] = {**prior, "contentHash": observation["contentHash"],
                        "retrievedAt": observation["retrievedAt"], "facts": copy.deepcopy(facts),
                        "evidence": copy.deepcopy(observation.get("evidence", []))}
        if modified:
            sources[url]["sourceUpdatedAt"] = modified
        considerations = ledger.setdefault("considerations", [])
        for proof in observation.get("evidence", []):
            if proof.get("field") != "calendarConsiderations" or not proof.get("excerpt"):
                continue
            identifier = fingerprint([url, proof.get("value"), proof["excerpt"]])
            existing = next((item for item in considerations if item["id"] == identifier), None)
            if existing:
                existing["lastSeen"] = as_of.isoformat()
            else:
                considerations.append({"id": identifier, "sourceUrl": url, "excerpt": proof["excerpt"],
                                       "firstSeen": as_of.isoformat(), "lastSeen": as_of.isoformat()})

    conflicted_editions = {key.rsplit(":", 1)[0] for key, choices in candidates.items()
                          if key.startswith("edition:") and len({fingerprint(choice[1]) for choice in choices}) > 1}
    confirmed = 0
    for key, choices in candidates.items():
        if (key.startswith("edition:") and key.rsplit(":", 1)[0] in conflicted_editions or
                len({fingerprint(choice[1]) for choice in choices}) > 1):
            issues.append("conflicting_sources:" + key)
            continue
        observation, value, excerpt, previous = choices[0][:4]
        digest = fingerprint(value)
        fresh = any(choice[3] != digest for choice in choices)
        if key.startswith("market:"):
            target, collection, field = market, "markets", key.split(":", 1)[1]
        else:
            identifier, field = key[len("edition:"):].rsplit(":", 1)
            incoming = choices[0][4]
            target = next((item for item in state["dates"] if item["id"] == identifier), None)
            # Only a confirmed date creates an edition. Existing editions can
            # be explicitly cancelled/postponed but never deleted by absence.
            if target is None:
                if incoming.get("status") != "published":
                    issues.append("unconfirmed_new_edition:" + incoming["date"])
                    continue
                target = {"id": identifier, "marketId": market["id"], "date": incoming["date"],
                          "status": "published", "source": observation["sourceUrl"], "legacyDates": []}
                state["dates"].append(target)
                changes.append({"collection": "dates", "id": identifier, "fields": ["created"],
                                "before": None, "after": copy.deepcopy(target),
                                "sourceUrl": observation["sourceUrl"], "retrievedAt": observation["retrievedAt"],
                                "contentHash": observation["contentHash"], "excerpt": excerpt})
            collection = "dates"
            for choice in choices:
                source_key = choice[4].get("sourceKey")
                if source_key:
                    link = {"sourceUrl": choice[0]["sourceUrl"], "sourceKey": source_key}
                    links = target.setdefault("refreshSourceKeys", [])
                    if link not in links:
                        links.append(link)
        if fresh:
            before = target.get(field)
            if field == "venue" and before is None:
                before = {"place": market.get("place")}
            if _less_specific(field, before, value):
                issues.append("less_specific_source:" + key)
                change = None
            else:
                change = _change(collection, target, field, value, observation, excerpt)
            if change:
                changes.append(change)
                if collection == "dates" and target.get("source") != observation["sourceUrl"]:
                    changes.append(_change("dates", target, "source", observation["sourceUrl"], observation, excerpt))
        confirmed += 1
        for choice in choices:
            sources[choice[0]["sourceUrl"]]["facts"][key] = digest
    return changes, sorted(set(issues)), confirmed


def apply_refresh(current, results, *, as_of, now):
    """Build a new immutable revision without changing any public snapshot."""
    valid_date(as_of.isoformat())
    result = copy.deepcopy(current)
    state = result["state"]
    ledger = result.setdefault("refreshLedger", {})
    all_changes, reports, seen = [], [], set()
    for collected in results:
        identifier = collected.get("marketId")
        if identifier in seen or not any(item["id"] == identifier for item in state["markets"]):
            raise MarketError("markets_refresh_identity_invalid")
        seen.add(identifier)
        trial, meta = copy.deepcopy(state), copy.deepcopy(ledger.get(identifier, {}))
        try:
            changes, issues, confirmed = _merge_market(trial, meta, collected, as_of)
            trial = validate_state(trial, state)
            state = trial
            all_changes.extend(changes)
        except (MarketError, ValueError, KeyError, TypeError, AttributeError) as error:
            issues = [str(error) if isinstance(error, MarketError) else "invalid_observation"]
            changes, confirmed, meta = [], 0, copy.deepcopy(ledger.get(identifier, {}))
        meta.update(lastAttempt=as_of.isoformat(), issues=issues,
                    retryable=any("fetch" in issue or "timeout" in issue or "http_5" in issue or issue in {"collector_failure", "source_unavailable", "source_http_429"} for issue in issues))
        if confirmed:
            meta["lastSuccess"] = as_of.isoformat()
        ledger[identifier] = meta
        reports.append({"marketId": identifier, "changes": len(changes), "confirmedFacts": confirmed,
                        "issues": issues, "considerations": copy.deepcopy(meta.get("considerations", []))})
    result["state"] = state
    summary = {"lastRunAt": now, "checkedMarkets": len(reports),
               "changedMarkets": sum(item["changes"] > 0 for item in reports),
               "changes": len(all_changes), "marketsWithIssues": sum(bool(item["issues"]) for item in reports),
               "publicationEnabled": False, "reports": reports}
    result["automation"] = summary
    result["revision"] = current["revision"] + 1
    result["audit"].append({"revision": result["revision"], "action": "refresh", "actor": "markets-automation",
                            "at": now, "reason": f"Controllo automatico: {len(reports)} mercati, {len(all_changes)} modifiche documentate",
                            "changes": all_changes, "reports": reports})
    return result
