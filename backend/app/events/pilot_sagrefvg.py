"""SagreFVG reader: complete annual API windows and structured event details."""

from datetime import date, datetime
from html import unescape
from math import asin, cos, radians, sin, sqrt
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo
import json
import re

import requests

from . import engine
from .pilot_excerpt import attributed_excerpt, clean_excerpt_text
from .pilot_schedule import schedule_notice


SOURCE = "SagreFVG"
API = "https://sagrefvg.it/wp-json/tribe/events/v1/events"
PER_PAGE = 50
MAX_PAGES = 100
MAX_BYTES = 8 * 1024 * 1024
TITLE_SEPARATOR = re.compile(r"\s+[–—-]\s+")
PROVINCE = re.compile(r"\((UD|PN|GO|TS)\)\s*$", re.I)
PROVINCE_NAMES = {'udine': 'UD', 'pordenone': 'PN',
                  'gorizia': 'GO', 'trieste': 'TS'}
PARENT_ALIAS = {"prata": "Prata di Pordenone",
                "camporosso": "Tarvisio",
                "camporosso in valcanale": "Tarvisio"}


def clean(value):
    return " ".join(unescape(str(value or "")).split())


def _fetch(get, *, start, end, page):
    params = {"start_date": start, "end_date": end, "per_page": PER_PAGE,
              "page": page}
    with get(API, params=params, timeout=(4, 12), allow_redirects=False,
             stream=True) as response:
        response.raise_for_status()
        if response.status_code != 200 or urlsplit(response.url).hostname != "sagrefvg.it":
            raise ValueError("SagreFVG API response changed")
        chunks, size = [], 0
        for chunk in response.iter_content(65536):
            size += len(chunk)
            if size > MAX_BYTES:
                raise ValueError("SagreFVG API page too large")
            chunks.append(chunk)
        payload = json.loads(b"".join(chunks).decode("utf-8-sig"))
        if not isinstance(payload, dict) or not isinstance(payload.get("events"), list):
            raise ValueError("SagreFVG API schema changed")
        return payload


def annual_window(get, year):
    """Read every page of one calendar year and reject count/order drift."""
    start, end = f"{year}-01-01", f"{year}-12-31"
    first = _fetch(get, start=start, end=end, page=1)
    total, pages = first.get("total"), first.get("total_pages")
    if (not isinstance(total, int) or isinstance(total, bool) or total < 0
            or not isinstance(pages, int) or isinstance(pages, bool)
            or pages != (total + PER_PAGE - 1) // PER_PAGE
            or pages > MAX_PAGES):
        raise ValueError("SagreFVG pagination changed")
    responses = [first]
    for page in range(2, pages + 1):
        responses.append(_fetch(get, start=start, end=end, page=page))
    rows, ids, urls, previous_start = [], set(), set(), None
    for page, payload in enumerate(responses, 1):
        expected = min(PER_PAGE, total - (page - 1) * PER_PAGE)
        if (payload.get("total") != total or payload.get("total_pages") != pages
                or len(payload["events"]) != expected):
            raise ValueError("SagreFVG page count changed during scan")
        for row in payload["events"]:
            if not isinstance(row, dict):
                raise ValueError("SagreFVG event schema changed")
            event_id, url = row.get("id"), row.get("url")
            parsed = urlsplit(str(url or ""))
            if (not isinstance(event_id, int) or isinstance(event_id, bool)
                    or event_id in ids or url in urls or parsed.scheme != "https"
                    or parsed.hostname != "sagrefvg.it"
                    or not parsed.path.startswith("/sagre/")
                    or not row.get("title") or row.get("status") != "publish"):
                raise ValueError("SagreFVG event identity changed")
            try:
                begin = datetime.fromisoformat(row["start_date"])
                finish = datetime.fromisoformat(row["end_date"])
            except (KeyError, TypeError, ValueError):
                raise ValueError("SagreFVG event date missing") from None
            if (begin.year != year or finish < begin or previous_start is not None
                    and begin < previous_start):
                raise ValueError("SagreFVG event dates or order changed")
            previous_start = begin
            ids.add(event_id)
            urls.add(url)
            rows.append(row)
    return rows, {"start": start, "end": end, "declared_results": total,
                  "records_read": len(rows), "pages_read": len(responses)}


def _distance_km(lat1, lon1, lat2, lon2):
    dlat, dlon = radians(lat2-lat1), radians(lon2-lon1)
    value = sin(dlat/2)**2 + cos(radians(lat1))*cos(radians(lat2))*sin(dlon/2)**2
    return 6371 * 2 * asin(sqrt(min(1, max(0, value))))


def resolve_municipality(title, venue):
    """Reconcile title locality, municipality and explicit venue province."""
    left = TITLE_SEPARATOR.split(clean(title), maxsplit=1)[0]
    province_match = PROVINCE.search(left)
    province = province_match[1].upper() if province_match else None
    locality = PROVINCE.sub("", left).strip() if province_match else left
    named_parent = re.split(r"\s+di\s+", locality, flags=re.I)[-1]
    named_parent = named_parent.replace('/', ' ')
    named_parent = PARENT_ALIAS.get(named_parent.casefold(), named_parent)
    catalog = engine.fvg_municipality_catalog
    from_title = catalog.match_names(named_parent)
    venue_city = clean(venue.get("city"))
    from_venue = catalog.match_names(PARENT_ALIAS.get(venue_city.casefold(), venue_city))
    if from_title and from_venue and from_title.name != from_venue.name:
        raise ValueError("SagreFVG title/venue municipality conflict")
    town = from_title or from_venue
    if not province:
        venue_label = clean(venue.get('venue'))
        venue_province = PROVINCE.search(venue_label)
        venue_url = urlsplit(clean(venue.get('url')))
        tokens = lambda value: re.findall(
            r'[a-z0-9]+', engine.normalize_for_search(value))
        if (not town or not from_title or not from_venue or not venue_province
                or venue_province[1].upper() != town.province
                or PROVINCE_NAMES.get(clean(venue.get('province')).casefold())
                   != town.province
                or PROVINCE_NAMES.get(clean(venue.get('stateprovince')).casefold())
                   != town.province
                or tokens(locality) != tokens(PROVINCE.sub('', venue_label))
                or venue_url.scheme != 'https' or venue_url.hostname != 'sagrefvg.it'
                or venue_url.path != '/luogo/' + '-'.join(tokens(locality))
                   + '-' + town.province.lower() + '/'
                or venue_url.query or venue_url.fragment):
            raise ValueError("SagreFVG title lacks verified province")
        province = town.province
    if not town or town.province != province:
        raise ValueError("SagreFVG municipality or province unresolved")
    return town, locality


def edition_preview_image(row, year):
    """Use the API's card crop only when it belongs to the event edition."""
    image = row.get('image')
    if not isinstance(image, dict):
        return None
    sizes = image.get('sizes')
    crop = sizes.get('qi_blocks_image_size_landscape') if isinstance(sizes, dict) else None
    url = crop.get('url') if isinstance(crop, dict) else None
    parsed = urlsplit(url or '')
    if (parsed.scheme != 'https' or parsed.hostname != 'sagrefvg.it'
            or not re.fullmatch(rf'/wp-content/uploads/{year}/(?:0[1-9]|1[0-2])/[A-Za-z0-9._~-]+\.(?:jpe?g|png|webp)',
                                parsed.path, re.I)
            or parsed.query or parsed.fragment):
        return None
    return url


def event_from_api(row):
    url = row["url"]
    venue = row.get("venue") if isinstance(row.get("venue"), dict) else {}
    country = clean(venue.get("country")).casefold()
    if country and country not in {"it", "italia", "italy"}:
        raise ValueError("SagreFVG venue outside Italy: " + url)
    title = clean(row["title"])
    if "\ufffd" in title:
        raise ValueError("SagreFVG title encoding broken: " + url)
    title_parts = TITLE_SEPARATOR.split(title, maxsplit=1)
    if len(title_parts) != 2 or not title_parts[1]:
        raise ValueError("SagreFVG event title missing after locality: " + url)
    event_title = title_parts[1]
    town, locality = resolve_municipality(title, venue)
    begin = datetime.fromisoformat(row["start_date"])
    finish = datetime.fromisoformat(row["end_date"])
    prose = clean_excerpt_text(row.get("description")).lstrip(" |•-–")
    if schedule_notice(title, prose[:400]):
        raise ValueError("SagreFVG schedule requires review: " + url)
    if url == 'https://sagrefvg.it/sagre/gonars-ud-gonars-si-veste-dautunno-duplicate-1-2/':
        if begin.date() == date(2026, 10, 10) and finish.date() == begin.date():
            if (not re.search(r'sabato\s+10\s+ottobre', prose, re.I)
                    or not re.search(r'domenica\s+11\s+ottobre', prose, re.I)):
                raise ValueError('SagreFVG Gonars programme/date mismatch: ' + url)
            finish = finish.replace(day=11)
    raw_lat, raw_lon = venue.get("geo_lat"), venue.get("geo_lng")
    if (raw_lat is None) != (raw_lon is None):
        raise ValueError("SagreFVG incomplete venue coordinates: " + url)
    if raw_lat is None:
        lat, lon = town.latitude, town.longitude
        confidence = "municipality"
    else:
        try:
            lat, lon = float(raw_lat), float(raw_lon)
        except (TypeError, ValueError):
            raise ValueError("SagreFVG invalid venue coordinates: " + url) from None
        bounds = engine.FVG_BOUNDS
        if (not bounds["lat_min"] <= lat <= bounds["lat_max"]
                or not bounds["lon_min"] <= lon <= bounds["lon_max"]
                or _distance_km(lat, lon, town.latitude, town.longitude) > 20):
            raise ValueError("SagreFVG venue outside municipality area: " + url)
        confidence = "venue"
    event = {"source": SOURCE, "url": url, "title": event_title,
             "source_title": title,
             "start_date": begin.date().isoformat(), "end_date": finish.date().isoformat(),
             "event_city": town.name, "place": locality,
             "lat": lat, "lon": lon, "location_confidence": confidence,
             "image": edition_preview_image(row, begin.year),
             "is_real": True, "date_evidence_kind": "event_schedule",
             "date_evidence": (row["start_date"] + " / " + row["end_date"]
                               + ('; programme 10-11 ottobre 2026'
                                  if url.endswith('gonars-si-veste-dautunno-duplicate-1-2/')
                                  and finish.date() == date(2026, 10, 11) else ''))}
    event.update(attributed_excerpt(prose, source_name=SOURCE,
                                    source_url=url, title=event_title))
    return event


def collect_sagrefvg(*, get=requests.get, today=None):
    today = today or datetime.now(ZoneInfo("Europe/Rome")).date()
    events, review, windows, seen_ids = [], [], [], set()
    past_count = 0
    empty_years = 0
    year = today.year
    while empty_years < 2 and year <= today.year + 5:
        rows, proof = annual_window(get, year)
        windows.append(proof)
        empty_years = empty_years + 1 if not rows else 0
        for row in rows:
            if row["id"] in seen_ids:
                raise ValueError("SagreFVG event repeated across years")
            seen_ids.add(row["id"])
            if date.fromisoformat(row["end_date"][:10]) < today:
                past_count += 1
                continue
            try:
                events.append(event_from_api(row))
            except ValueError as exc:
                review.append({"url": row["url"], "reason": str(exc)})
        year += 1
    if empty_years < 2:
        raise ValueError("SagreFVG future horizon did not close")
    overflow = _fetch(get, start=f"{year}-01-01", end="2099-12-31", page=1)
    if (overflow.get("total") != 0 or overflow.get("total_pages") != 0
            or overflow["events"]):
        raise ValueError("SagreFVG unseen future events beyond annual windows")
    scanned = sum(window["records_read"] for window in windows)
    return {"status": "error" if review else "ok", "events": events,
            "review_required": review,
            "verification": {"collection_mode": "complete-annual-api-pages",
                             "windows": windows, "overflow_start": f"{year}-01-01",
                             "overflow_total": 0, "records_scanned": scanned,
                             "past_count": past_count, "active_count": len(events),
                             "review_count": len(review)},
            "coverage": "current-year-and-future-api-windows"}
