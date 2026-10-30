from __future__ import annotations

import copy
from datetime import date, datetime, timedelta, timezone
import hashlib
import json
import math
import re
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

from .seed import edition_id


MAX_STATE_BYTES = 8 * 1024 * 1024
ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,119}$")
MARKET_STATUSES = {"draft", "published", "suspended", "archived"}
DATE_STATUSES = {"draft", "published", "cancelled", "postponed"}
PUBLIC_MARKET_FIELDS = {
    "id", "key", "name", "comune", "prov", "municipalityIstat", "kind", "cadence", "place", "url",
    "authority", "quality", "checked", "group", "weekdays", "weekdaysIso", "hours", "scheduleNote",
    "titleAliases", "directionsQuery", "validFrom", "validThrough", "status", "description", "descriptionFur",
}
PUBLIC_VENUE_FIELDS = {"id", "place", "directionsQuery", "lat", "lon", "validFrom", "validThrough"}


class MarketError(Exception):
    def __init__(self, code: str, status: int = 422, **detail):
        super().__init__(code)
        self.status = status
        self.detail = {"code": code, **detail}


def encode(value) -> bytes:
    try:
        data = json.dumps(value, ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(",", ":")).encode()
    except (ValueError, TypeError) as error:
        raise MarketError("markets_invalid_json") from error
    if len(data) > MAX_STATE_BYTES:
        raise MarketError("markets_state_too_large")
    return data


def timestamp() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def valid_date(value, *, optional=False):
    if optional and value in (None, ""):
        return
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        raise MarketError("markets_invalid_date")
    try:
        date.fromisoformat(value)
    except ValueError as error:
        raise MarketError("markets_invalid_date") from error


def valid_url(value, *, optional=False):
    if optional and value in (None, ""):
        return
    try:
        url = urlsplit(value)
        if url.scheme != "https" or not url.hostname or url.username or url.password:
            raise ValueError()
    except (TypeError, ValueError) as error:
        raise MarketError("markets_https_source_required") from error


def _identifier(value):
    if not isinstance(value, str) or not ID.fullmatch(value):
        raise MarketError("markets_invalid_id")


def _venue(value):
    if not isinstance(value, dict):
        raise MarketError("markets_invalid_venue")
    _identifier(value.get("id"))
    if not isinstance(value.get("place"), str) or not value["place"].strip():
        raise MarketError("markets_venue_place_required")
    for field in PUBLIC_VENUE_FIELDS - {"lat", "lon"}:
        if field in value and (not isinstance(value[field], str) or len(value[field]) > 2000):
            raise MarketError("markets_invalid_venue_text")
    for field in ("validFrom", "validThrough"):
        valid_date(value.get(field), optional=True)
    for field, bound in (("lat", 90), ("lon", 180)):
        if field in value and (type(value[field]) not in (int, float) or not math.isfinite(value[field]) or abs(value[field]) > bound):
            raise MarketError("markets_invalid_venue_coordinates")
    if ("lat" in value) != ("lon" in value):
        raise MarketError("markets_invalid_venue_coordinates")


def validate_state(candidate: dict, previous: dict) -> dict:
    if not isinstance(candidate, dict):
        raise MarketError("markets_state_required")
    state = {"schemaVersion": 2,
             "checked": candidate.get("checked", previous["checked"]),
             "validThrough": candidate.get("validThrough", previous["validThrough"]),
             "provenance": copy.deepcopy(previous.get("provenance", {}))}
    valid_date(state["checked"])
    valid_date(state["validThrough"])
    for key, limit in (("markets", 2000), ("dates", 20000), ("drafts", 1000)):
        value = candidate.get(key, previous[key])
        if not isinstance(value, list) or len(value) > limit or any(not isinstance(item, dict) for item in value):
            raise MarketError("markets_invalid_collection", collection=key)
        state[key] = copy.deepcopy(value)
        identifiers = [item.get("id") for item in value]
        for identifier in identifiers:
            _identifier(identifier)
        if len(set(identifiers)) != len(identifiers):
            raise MarketError("markets_duplicate_id", collection=key)
        if not {item["id"] for item in previous[key]}.issubset(identifiers):
            raise MarketError("markets_archive_instead_of_delete", collection=key)
    market_ids = {item["id"] for item in state["markets"]}
    previous_markets = {item["id"]: item for item in previous["markets"]}
    for market in state["markets"]:
        for key in ("name", "comune"):
            if not isinstance(market.get(key), str) or not 0 < len(market[key].strip()) <= 300:
                raise MarketError("markets_identity_required", marketId=market["id"])
        if not isinstance(market.get("status"), str) or market["status"] not in MARKET_STATUSES:
            raise MarketError("markets_invalid_status", marketId=market["id"])
        if type(market.get("publicationReady", False)) is not bool:
            raise MarketError("markets_publication_ready_boolean_required")
        if not isinstance(market.get("evidenceStatus"), str) or market["evidenceStatus"] not in {"documented", "unverified", "conflict", "historical"}:
            raise MarketError("markets_invalid_evidence_status")
        if not isinstance(market.get("group"), str) or market["group"] not in {"regular", "occasional"}:
            raise MarketError("markets_invalid_group")
        for field in PUBLIC_MARKET_FIELDS - {"weekdays", "weekdaysIso", "titleAliases"} | {"publicReason"}:
            if field in market and (not isinstance(market[field], str) or len(market[field]) > 5000):
                raise MarketError("markets_invalid_text", field=field)
        valid_date(market.get("checked"), optional=True)
        for key in ("validFrom", "validThrough"):
            valid_date(market.get(key), optional=True)
        if market.get("validFrom") and market.get("validThrough") and market["validFrom"] > market["validThrough"]:
            raise MarketError("markets_invalid_validity_range")
        valid_url(market.get("url"), optional=True)
        iso = market.get("weekdaysIso", [day or 7 for day in market.get("weekdays", [])])
        if not isinstance(iso, list) or any(type(day) is not int or not 1 <= day <= 7 for day in iso):
            raise MarketError("markets_iso_weekdays_required")
        market["weekdaysIso"] = sorted(set(iso))
        market["weekdays"] = [day % 7 for day in market["weekdaysIso"]]
        aliases = market.get("titleAliases", [])
        if not isinstance(aliases, list) or any(not isinstance(item, str) or len(item) > 300 for item in aliases):
            raise MarketError("markets_invalid_aliases")
        # Previously used identity evidence stays available to reconcile old feeds.
        old = previous_markets.get(market["id"], {})
        market["titleAliases"] = list(dict.fromkeys(aliases + old.get("titleAliases", []) +
                                                  ([old["name"]] if old.get("name") and old["name"] != market["name"] else [])))
        market["previousSourceUrls"] = sorted(set(old.get("previousSourceUrls", []) +
                                                  ([old["url"]] if old.get("url") and old["url"] != market.get("url") else [])))
        market["previousMunicipalities"] = sorted(set(old.get("previousMunicipalities", []) +
                                                       ([old["comune"]] if old.get("comune") and old["comune"] != market["comune"] else [])))
    previous_dates = {item["id"]: item for item in previous["dates"]}
    live_slots = set()
    for edition in state["dates"]:
        if not isinstance(edition.get("marketId"), str) or edition["marketId"] not in market_ids or not isinstance(edition.get("status"), str) or edition["status"] not in DATE_STATUSES:
            raise MarketError("markets_invalid_edition")
        valid_date(edition.get("date"))
        valid_url(edition.get("source"), optional=True)
        old = previous_dates.get(edition["id"])
        if old and old["marketId"] != edition["marketId"]:
            raise MarketError("markets_edition_identity_immutable")
        legacy = list(old.get("legacyDates", [])) if old else []
        if old and old["date"] != edition["date"]:
            legacy.append(old["date"])
        edition["legacyDates"] = sorted(set(legacy))
        if edition.get("venue") is not None:
            _venue(edition["venue"])
        if edition["status"] == "published":
            slot = (edition["marketId"], edition["date"])
            if slot in live_slots:
                raise MarketError("markets_duplicate_edition")
            live_slots.add(slot)
    old_drafts = {item["id"]: item for item in previous["drafts"]}
    for draft in state["drafts"]:
        if draft["id"] in old_drafts:
            # The imported evidence is provenance, not editable editorial copy.
            original = old_drafts[draft["id"]]
            allowed = {key: draft[key] for key in ("status", "linkedMarketIds", "editorialNotes") if key in draft}
            draft.clear()
            draft.update(copy.deepcopy(original))
            draft.update(allowed)
        if not isinstance(draft.get("status"), str) or draft["status"] not in {"draft", "in_review", "prepared", "archived"}:
            raise MarketError("markets_invalid_draft_status")
        if not isinstance(draft.get("linkedMarketIds", []), list) or any(not isinstance(item, str) or item not in market_ids for item in draft.get("linkedMarketIds", [])):
            raise MarketError("markets_invalid_draft_link")
    encode(state)
    return state


def publication_errors(state: dict, previous_catalogue: dict) -> list[dict]:
    errors = []
    old_ids = {item["marketId"] for item in previous_catalogue.get("identities", [])}
    identities = {}
    for market in state["markets"]:
        if market["status"] != "published":
            continue
        missing = []
        if market.get("publicationReady") is not True or market.get("evidenceStatus") != "documented":
            missing.append("editorial_review")
        if not market.get("url") or not market.get("checked"):
            missing.append("source_and_check_date")
        if not market.get("validThrough"):
            missing.append("verified_validity")
        if market["id"] not in old_ids and not market.get("place"):
            missing.append("venue")
        if market.get("group") == "regular" and not market.get("weekdaysIso"):
            missing.append("weekly_rule")
        editions = [item for item in state["dates"] if item["marketId"] == market["id"] and item["status"] == "published"]
        if market.get("group") == "occasional" and not editions and market["id"] not in old_ids:
            missing.append("documented_editions")
        if any(not item.get("source") for item in editions):
            missing.append("edition_sources")
        if any((market.get("validFrom") and item["date"] < market["validFrom"]) or
               (market.get("validThrough") and item["date"] > market["validThrough"]) for item in editions):
            missing.append("edition_outside_verified_validity")
        identity = (market["comune"].strip().casefold(), market["name"].strip().casefold())
        if identity in identities:
            missing.append("duplicate_identity:" + identities[identity])
        identities[identity] = market["id"]
        if missing:
            errors.append({"marketId": market["id"], "checks": missing})
    return errors


def build_catalogue(state: dict, *, revision: int, now: str, previous: dict | None = None) -> dict:
    previous = previous or {}
    # A saved draft is not a withdrawal. Publishing another market must leave
    # the last approved projection of an unfinished edit untouched.
    state = copy.deepcopy(state)
    previous_markets = {item["id"]: item for item in previous.get("markets", [])}
    draft_market_ids = {item["id"] for item in state["markets"] if item["status"] == "draft" and item["id"] in previous_markets}
    state["markets"] = [copy.deepcopy(previous_markets[item["id"]]) if item["id"] in draft_market_ids else item
                        for item in state["markets"]]
    previous_editions = {item["id"]: item for item in previous.get("dates", [])}
    dates = []
    for item in state["dates"]:
        if item["marketId"] in draft_market_ids:
            continue
        if item["status"] == "draft" and item["id"] in previous_editions:
            dates.append(copy.deepcopy(previous_editions[item["id"]]))
        else:
            dates.append(item)
    dates.extend(copy.deepcopy(item) for item in previous.get("dates", []) if item["marketId"] in draft_market_ids)
    state["dates"] = dates
    current = {item["id"]: item for item in state["markets"]}
    visible = {key for key, item in current.items() if item["status"] == "published"}
    identities = {item["marketId"]: copy.deepcopy(item) for item in previous.get("identities", [])}
    for identifier in visible | set(identities):
        market = current[identifier]
        old = identities.get(identifier, {})
        identities[identifier] = {
            "marketId": identifier, "name": market["name"], "comune": market["comune"],
            "municipalityAliases": sorted(set(old.get("municipalityAliases", []) + market.get("previousMunicipalities", []) +
                                               ([old["comune"]] if old.get("comune") and old["comune"] != market["comune"] else []))),
            "titleAliases": sorted(set(old.get("titleAliases", []) + market.get("titleAliases", []) +
                                       ([old["name"]] if old.get("name") and old["name"] != market["name"] else []))),
            "sourceUrls": sorted(set(old.get("sourceUrls", []) + market.get("previousSourceUrls", []) +
                                     ([market["url"]] if market.get("url") else []) +
                                     [item["source"] for item in state["dates"] if item["marketId"] == identifier and item.get("source")])),
            "status": market["status"] if market["status"] != "draft" else "archived",
        }
    tombstones = []
    for identifier, item in identities.items():
        if identifier not in visible:
            tombstones.append({"marketId": identifier, "status": item["status"],
                               "reason": str(current[identifier].get("publicReason") or "")[:500]})
    public_dates, aliases = [], {item["legacyId"]: copy.deepcopy(item) for item in previous.get("editionAliases", [])}
    previous_date_ids = {item["id"] for item in previous.get("dates", [])}
    for edition in state["dates"]:
        market_id = edition["marketId"]
        if market_id not in identities:
            continue
        was_public = edition["id"] in previous_date_ids or any(item.get("editionId") == edition["id"] for item in aliases.values())
        if edition["status"] != "draft" or was_public:
            for day in [edition["date"], *edition.get("legacyDates", [])]:
                legacy_id = f"market:{market_id}:{day}"
                aliases[legacy_id] = {"legacyId": legacy_id, "editionId": edition["id"], "marketId": market_id}
        if market_id in visible and edition["status"] != "draft":
            projected = {key: copy.deepcopy(edition[key]) for key in ("id", "marketId", "date", "status", "source", "legacyDates") if key in edition}
            if edition.get("venue"):
                projected["venue"] = {key: copy.deepcopy(value) for key, value in edition["venue"].items() if key in PUBLIC_VENUE_FIELDS}
            public_dates.append(projected)
        for old_day in edition.get("legacyDates", []):
            if old_day != edition["date"]:
                tombstones.append({"marketId": market_id, "editionId": edition["id"], "date": old_day,
                                   "status": "rescheduled", "replacementDate": edition["date"], "reason": str(edition.get("publicReason") or "")[:500]})
        if edition["status"] in {"cancelled", "postponed"}:
            tombstones.append({"marketId": market_id, "editionId": edition["id"], "date": edition["date"],
                               "status": "cancelled", "reason": str(edition.get("publicReason") or "")[:500]})
    horizon = max([state["validThrough"], *[current[key].get("validThrough") or state["validThrough"] for key in visible],
                   *[item["date"] for item in public_dates if item["status"] == "published"]])
    expiry = datetime.combine(date.fromisoformat(horizon) + timedelta(days=1), datetime.min.time(),
                              tzinfo=ZoneInfo("Europe/Rome")).astimezone(timezone.utc)
    result = {
        "schemaVersion": 2, "revision": revision, "publishedAt": now,
        "expiresAt": expiry.isoformat().replace("+00:00", "Z"),
        "checked": state["checked"], "validThrough": horizon, "timezone": "Europe/Rome",
        "markets": [{**{key: copy.deepcopy(value) for key, value in item.items() if key in PUBLIC_MARKET_FIELDS},
                     "quality": "Documentato"} for item in state["markets"] if item["id"] in visible],
        "dates": public_dates, "identities": list(identities.values()), "tombstones": tombstones,
        "editionAliases": list(aliases.values()),
    }
    result["snapshotId"] = f"markets-{revision}-" + hashlib.sha256(encode(result)).hexdigest()[:16]
    return result


def initial_record(seed: dict) -> dict:
    now = timestamp()
    return {"revision": 0, "publishedRevision": 0, "state": copy.deepcopy(seed), "audit": [],
            "catalogue": build_catalogue(seed, revision=0, now=now)}


def audit_changes(before: dict, after: dict) -> list[dict]:
    changes = []
    for collection in ("markets", "dates", "drafts"):
        old = {item["id"]: item for item in before[collection]}
        for item in after[collection]:
            prior = old.get(item["id"], {})
            fields = sorted(key for key in set(item) | set(prior) if item.get(key) != prior.get(key))
            if fields:
                changes.append({"collection": collection, "id": item["id"], "fields": fields})
    for key in ("checked", "validThrough"):
        if before[key] != after[key]:
            changes.append({"collection": "catalogue", "id": key, "before": before[key], "after": after[key]})
    return changes
