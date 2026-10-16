"""Read-only EventiFVG API audit; deliberately not a publishing adapter.

The public REST archive filters by event start. Its future pages alone cannot
prove that an event which started earlier and is still open was discovered.
"""

from datetime import date, datetime
from math import ceil
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo
import json
import re

import requests

from . import engine


SOURCE = "EventiFVG"
API = "https://www.eventifvg.it/wp-json/tribe/events/v1/events"
PER_PAGE = 50  # The site's API caps larger requests at 50.
MAX_PAGES = 200
MAX_RESPONSE_BYTES = 8 * 1024 * 1024
FOREIGN_COUNTRIES = {"SI", "SLOVENIA", "AT", "AUSTRIA", "HR", "CROATIA"}
PLACE_ALIASES = {"rauscedo": "San Giorgio della Richinvelda"}


def _read_page(get, *, start, end, page):
    params = {"start_date": start, "end_date": end, "per_page": PER_PAGE,
              "page": page}
    with get(API, params=params, timeout=(4, 20), stream=True,
             allow_redirects=False) as response:
        response.raise_for_status()
        if response.status_code != 200 or urlsplit(response.url).hostname != "www.eventifvg.it":
            raise ValueError("EventiFVG API response changed")
        chunks, size = [], 0
        for chunk in response.iter_content(65536):
            size += len(chunk)
            if size > MAX_RESPONSE_BYTES:
                raise ValueError("EventiFVG API page too large")
            chunks.append(chunk)
        payload = json.loads(b"".join(chunks).decode("utf-8-sig"))
        if not isinstance(payload, dict) or not isinstance(payload.get("events"), list):
            raise ValueError("EventiFVG API schema changed")
        return payload


def _town(text):
    normalized = engine.normalize_for_search(text)
    if not normalized:
        return None
    alias = PLACE_ALIASES.get(normalized)
    if alias:
        return engine.fvg_municipality_catalog.match_names(alias)
    return engine.fvg_municipality_catalog.match_names(text)


def location_evidence(raw):
    """Accept a named city or postal/venue tail; street names are not cities."""
    venue = raw.get("venue") if isinstance(raw.get("venue"), dict) else {}
    country = str(venue.get("country") or "").upper()
    if country in FOREIGN_COUNTRIES:
        return {"kind": "foreign_country"}
    city = _town(venue.get("city"))
    if city:
        return {"kind": "structured_city", "city": city.name}
    for field in ("address", "venue"):
        value = str(venue.get(field) or "")
        parts = [part.strip() for part in value.split(",")]
        # Postal code plus town is explicit even when venue.city is empty.
        for part in reversed(parts):
            match = re.search(r"\b\d{5}\s+(.+?)(?:\s+(?:UD|PN|GO|TS))?$", part, re.I)
            if match:
                city = _town(match[1].strip())
                if city:
                    return {"kind": "postal_city", "city": city.name}
        # A final comma-separated town or a town at the end of a venue name
        # is stronger than a municipality name embedded in a street address.
        for part in reversed(parts):
            if not part or re.fullmatch(r"(?:Italy|Italia|IT)", part, re.I):
                continue
            city = _town(part)
            if city:
                return {"kind": "venue_city", "city": city.name}
            normalized = engine.normalize_for_search(part)
            matches = [candidate for candidate in engine.fvg_municipality_catalog.municipalities
                       if normalized.endswith(" " + engine.normalize_for_search(candidate.name))]
            if matches:
                city = max(matches, key=lambda item: len(item.name))
                return {"kind": "venue_city", "city": city.name}
    return {"kind": "unresolved"}


def audit_future_archive(*, get=requests.get, today=None):
    """Prove API pagination and report geographic gaps; publish no events."""
    today = today or datetime.now(ZoneInfo("Europe/Rome")).date()
    if not isinstance(today, date):
        raise TypeError("today must be a date")
    start, end = today.isoformat(), "2099-12-31"
    first = _read_page(get, start=start, end=end, page=1)
    total, total_pages = first.get("total"), first.get("total_pages")
    if (not isinstance(total, int) or isinstance(total, bool) or total < 0
            or not isinstance(total_pages, int) or isinstance(total_pages, bool)
            or total_pages != ceil(total / PER_PAGE)
            or total_pages > MAX_PAGES):
        raise ValueError("EventiFVG API pagination changed")
    pages = [first]
    for page in range(2, total_pages + 1):
        pages.append(_read_page(get, start=start, end=end, page=page))
    rows = []
    for number, payload in enumerate(pages, 1):
        if payload.get("total") != total or payload.get("total_pages") != total_pages:
            raise ValueError("EventiFVG API totals changed during scan")
        expected = min(PER_PAGE, total - (number - 1) * PER_PAGE)
        if len(payload["events"]) != expected:
            raise ValueError("EventiFVG API page has missing records")
        rows.extend(payload["events"])
    ids, urls, counts, unresolved = set(), set(), {}, []
    previous_start = None
    for raw in rows:
        if not isinstance(raw, dict):
            raise ValueError("EventiFVG API event changed")
        event_id, url = raw.get("id"), raw.get("url")
        parsed = urlsplit(str(url or ""))
        if (not isinstance(event_id, int) or isinstance(event_id, bool)
                or event_id in ids or url in urls or parsed.scheme != "https"
                or parsed.hostname != "www.eventifvg.it"
                or not parsed.path.startswith("/evento/")
                or not raw.get("title") or raw.get("status") != "publish"):
            raise ValueError("EventiFVG API event identity changed")
        ids.add(event_id)
        urls.add(url)
        try:
            start_day = date.fromisoformat(str(raw["start_date"])[:10])
            end_day = date.fromisoformat(str(raw["end_date"])[:10])
        except (KeyError, ValueError, TypeError):
            raise ValueError("EventiFVG API event dates changed") from None
        if start_day < today or end_day < start_day:
            raise ValueError("EventiFVG API date range invalid")
        start_value = str(raw["start_date"])
        if previous_start is not None and start_value < previous_start:
            raise ValueError("EventiFVG API event order changed")
        previous_start = start_value
        evidence = location_evidence(raw)
        kind = evidence["kind"]
        counts[kind] = counts.get(kind, 0) + 1
        if kind == "unresolved":
            unresolved.append(url)
    return {"source": SOURCE, "status": "diagnostic_only", "total": total,
            "pages_read": len(pages), "unique_ids": len(ids),
            "location_evidence": counts,
            "unresolved_location_urls": unresolved,
            "coverage": "future-starts-only",
            "ongoing_started_before_today_verified": False,
            "descriptions_republished": False}


if __name__ == "__main__":
    result = audit_future_archive()
    result["unresolved_location_urls"] = result["unresolved_location_urls"][:20]
    print(json.dumps(result, ensure_ascii=True, indent=2))
