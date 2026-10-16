from __future__ import annotations

import re
import unicodedata
from datetime import date
from html import unescape
from html.parser import HTMLParser
from typing import Callable
from urllib.parse import urlsplit

import requests

from app.events.http_client import get_with_single_transient_retry


VILLA_MANIN_SOURCE = "Villa Manin"
VILLA_MANIN_API_URL = "https://www.villamanin.it/wp-json/wp/v2/evento"
VILLA_MANIN_SITE_URL = "https://www.villamanin.it"
VILLA_MANIN_PARSER_VERSION = "villa-manin-wp-v2"
VILLA_MANIN_HOSTS = {"villamanin.it", "www.villamanin.it"}
VILLA_MANIN_CANONICAL_VENUE = "Villa Manin"
VILLA_MANIN_CANONICAL_CITY = "Codroipo"
VILLA_MANIN_CANONICAL_LOCALITY = "Passariano di Codroipo"
VILLA_MANIN_CANONICAL_ADDRESS = "Piazza Manin 10"

_MONTHS = {
    "gennaio": 1,
    "febbraio": 2,
    "marzo": 3,
    "aprile": 4,
    "maggio": 5,
    "giugno": 6,
    "luglio": 7,
    "agosto": 8,
    "settembre": 9,
    "ottobre": 10,
    "novembre": 11,
    "dicembre": 12,
}
_MONTH_LABELS = tuple(_MONTHS)
_MONTH_PATTERN = "(?:" + "|".join(_MONTH_LABELS) + ")"
_WEEKDAY_PATTERN = (
    r"(?:lunedi|martedi|mercoledi|giovedi|venerdi|sabato|domenica)"
)
_NUMERIC_RANGE_RE = re.compile(
    r"\b(?:dal\s+)?(?P<d1>\d{1,2})[./](?P<m1>\d{1,2})[./](?P<y1>\d{4})"
    r"\s+(?:al|[-–—])\s+"
    r"(?P<d2>\d{1,2})[./](?P<m2>\d{1,2})[./](?P<y2>\d{4})\b",
    re.IGNORECASE,
)
_NUMERIC_SHARED_YEAR_RANGE_RE = re.compile(
    r"\b(?:dal\s+)?(?P<d1>\d{1,2})[./](?P<m1>\d{1,2})"
    r"\s+(?:al|[-–—])\s+"
    r"(?P<d2>\d{1,2})[./](?P<m2>\d{1,2})[./](?P<y2>\d{4})\b",
    re.IGNORECASE,
)
_TEXT_RANGE_RE = re.compile(
    rf"\b(?:dal\s+)?(?P<d1>\d{{1,2}})\s+(?P<m1>{_MONTH_PATTERN})"
    rf"(?:\s+(?P<y1>\d{{4}}))?\s+(?:al|[-–—])\s+"
    rf"(?P<d2>\d{{1,2}})\s+(?P<m2>{_MONTH_PATTERN})\s+(?P<y2>\d{{4}})\b",
    re.IGNORECASE,
)
_SINGLE_DATE_RE = re.compile(
    rf"\b(?:{_WEEKDAY_PATTERN}\s+)?(?P<day>\d{{1,2}})\s+"
    rf"(?P<month>{_MONTH_PATTERN})\s+(?P<year>\d{{4}})\b",
    re.IGNORECASE,
)
_DAY_MONTH_RE = re.compile(
    rf"\b(?P<day>\d{{1,2}})\s+(?P<month>{_MONTH_PATTERN})"
    rf"(?:\s+(?P<year>\d{{4}}))?\b",
    re.IGNORECASE,
)
_WRITTEN_DATE_TOKEN_RE = re.compile(
    rf"\b\d{{1,2}}\s+{_MONTH_PATTERN}(?:\s+\d{{4}})?\b",
    re.IGNORECASE,
)
_NUMERIC_DATE_TOKEN_RE = re.compile(
    r"\b\d{1,2}[./]\d{1,2}[./]\d{4}\b",
    re.IGNORECASE,
)


class VillaManinStructureError(ValueError):
    """The official feed no longer matches its reviewed public schema."""


class VillaManinRecordRejected(ValueError):
    """A valid feed record cannot be imported without making an assumption."""

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


class _ElementorTextExtractor(HTMLParser):
    _CAPTURE_TAGS = {"h1", "h2", "h3", "p"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.headings: list[str] = []
        self.paragraphs: list[str] = []
        self.blocks: list[tuple[str, str]] = []
        self._capture_tag: str | None = None
        self._capture_depth = 0
        self._parts: list[str] = []

    def handle_starttag(self, tag: str, attrs):
        tag = tag.lower()
        if self._capture_tag:
            if tag == "br":
                self._parts.append(" ")
                return
            self._capture_depth += 1
            return
        if tag in self._CAPTURE_TAGS:
            self._capture_tag = tag
            self._capture_depth = 1
            self._parts = []

    def handle_startendtag(self, tag: str, attrs):
        if self._capture_tag and tag.lower() == "br":
            self._parts.append(" ")

    def handle_data(self, data: str):
        if self._capture_tag:
            self._parts.append(data)

    def handle_endtag(self, tag: str):
        if not self._capture_tag:
            return
        self._capture_depth -= 1
        if self._capture_depth > 0:
            return

        value = _clean_text(" ".join(self._parts))
        if value:
            if self._capture_tag == "p":
                self.paragraphs.append(value)
            else:
                self.headings.append(value)
            self.blocks.append((self._capture_tag, value))
        self._capture_tag = None
        self._parts = []


def _clean_text(value: object) -> str:
    return re.sub(r"\s+", " ", unescape(str(value or ""))).strip()


def _search_text(value: object) -> str:
    normalized = unicodedata.normalize("NFKD", _clean_text(value))
    return normalized.encode("ascii", "ignore").decode("ascii").lower()


def _trusted_url(value: object, *, event_page: bool = False, image: bool = False) -> str | None:
    url = _clean_text(value)
    if not url:
        return None
    parsed = urlsplit(url)
    if parsed.scheme != "https" or parsed.hostname not in VILLA_MANIN_HOSTS:
        return None
    if parsed.username or parsed.password or parsed.port or parsed.query or parsed.fragment:
        return None
    if event_page and not re.fullmatch(r"/evento/[a-z0-9-]+/", parsed.path):
        return None
    if image and not parsed.path.startswith("/wp-content/uploads/"):
        return None
    return url


def is_trusted_villa_manin_event_url(value: object) -> bool:
    return bool(_trusted_url(value, event_page=True))


def is_trusted_villa_manin_image_url(value: object) -> bool:
    return bool(_trusted_url(value, image=True))


def _as_date(year: object, month: object, day: object) -> date:
    try:
        return date(int(year), int(month), int(day))
    except (TypeError, ValueError) as exc:
        raise VillaManinRecordRejected("invalid_date") from exc


def _parse_explicit_range(value: str):
    normalized = _search_text(value)
    match = _NUMERIC_RANGE_RE.search(normalized)
    if match:
        start = _as_date(match["y1"], match["m1"], match["d1"])
        end = _as_date(match["y2"], match["m2"], match["d2"])
        if end < start:
            raise VillaManinRecordRejected("invalid_date_range")
        return start, end, _clean_text(match.group(0)), "explicit_range"

    match = _NUMERIC_SHARED_YEAR_RANGE_RE.search(normalized)
    if match:
        start = _as_date(match["y2"], match["m1"], match["d1"])
        end = _as_date(match["y2"], match["m2"], match["d2"])
        if end < start:
            raise VillaManinRecordRejected("invalid_date_range")
        return start, end, _clean_text(match.group(0)), "explicit_range"

    match = _TEXT_RANGE_RE.search(normalized)
    if not match:
        return None
    shared_year = match["y2"]
    start = _as_date(match["y1"] or shared_year, _MONTHS[match["m1"]], match["d1"])
    end = _as_date(shared_year, _MONTHS[match["m2"]], match["d2"])
    if end < start:
        raise VillaManinRecordRejected("invalid_date_range")
    return start, end, _clean_text(match.group(0)), "explicit_range"


def _date_token_count(value: str) -> int:
    normalized = _search_text(value)
    return len(_WRITTEN_DATE_TOKEN_RE.findall(normalized)) + len(
        _NUMERIC_DATE_TOKEN_RE.findall(normalized)
    )


def _embedded_taxonomy_terms(record: dict, taxonomy_name: str) -> list[str]:
    embedded = record.get("_embedded")
    if not isinstance(embedded, dict):
        return []
    groups = embedded.get("wp:term")
    if not isinstance(groups, list):
        return []
    names: list[str] = []
    for group in groups:
        if not isinstance(group, list):
            continue
        for term in group:
            if not isinstance(term, dict):
                continue
            name = _clean_text(term.get("name"))
            taxonomy = _clean_text(term.get("taxonomy"))
            if name and taxonomy == taxonomy_name and name not in names:
                names.append(name)
    return names


def _embedded_years(record: dict) -> list[int]:
    return sorted(
        int(value)
        for value in _embedded_taxonomy_terms(record, "anno")
        if re.fullmatch(r"20\d{2}", value)
    )


def _valid_date_or_none(year: object, month: object, day: object) -> date | None:
    try:
        return date(int(year), int(month), int(day))
    except (TypeError, ValueError):
        return None


def _compact_numeric_occurrences(value: str, context_years: list[int]) -> list[date]:
    normalized = _search_text(value)
    occurrences: list[date] = []
    previous_year_end = 0
    explicit_years = list(re.finditer(r"\b20\d{2}\b", normalized))
    for year_match in explicit_years:
        prefix = normalized[previous_year_end : year_match.start()]
        for day_value, month_value in re.findall(r"\b(\d{1,2})[./](\d{1,2})\b", prefix):
            parsed = _valid_date_or_none(year_match.group(0), month_value, day_value)
            if parsed and parsed not in occurrences:
                occurrences.append(parsed)
        previous_year_end = year_match.end()

    if not explicit_years and len(context_years) == 1:
        for day_value, month_value in re.findall(r"\b(\d{1,2})[./](\d{1,2})\b", normalized):
            parsed = _valid_date_or_none(context_years[0], month_value, day_value)
            if parsed and parsed not in occurrences:
                occurrences.append(parsed)
    return occurrences


def _format_occurrences(occurrences: list[date]) -> str:
    return " · ".join(
        f"{item.day} {_MONTH_LABELS[item.month - 1]} {item.year}"
        for item in occurrences
    )


def _extract_date_from_candidates(candidates: list[str], context_years: list[int]):
    for candidate in candidates:
        parsed_range = _parse_explicit_range(candidate)
        if parsed_range:
            return (*parsed_range, [])

    for candidate in candidates:
        compact = _compact_numeric_occurrences(candidate, context_years)
        if len(compact) > 1:
            compact = sorted(compact)
            return (
                compact[0],
                compact[-1],
                _clean_text(candidate),
                "explicit_occurrences",
                compact,
            )

    occurrences: list[date] = []
    source_texts: list[str] = []
    ambiguous = False
    context_year = context_years[0] if len(context_years) == 1 else None
    for candidate in candidates:
        normalized = _search_text(candidate)
        candidate_dates = _compact_numeric_occurrences(candidate, context_years)
        token_count = _date_token_count(candidate)
        for match in _DAY_MONTH_RE.finditer(normalized):
            year_value = match["year"] or context_year
            if not year_value:
                continue
            parsed = _valid_date_or_none(
                year_value,
                _MONTHS[match["month"]],
                match["day"],
            )
            if parsed and parsed not in candidate_dates:
                candidate_dates.append(parsed)

        if token_count > len(candidate_dates) and token_count > 1:
            ambiguous = True
        if candidate_dates:
            source_texts.append(_clean_text(candidate))
            for parsed in candidate_dates:
                if parsed not in occurrences:
                    occurrences.append(parsed)

    occurrences.sort()
    month_days: dict[tuple[int, int], set[int]] = {}
    for item in occurrences:
        month_days.setdefault((item.month, item.day), set()).add(item.year)
    if any(len(years) > 1 for years in month_days.values()):
        raise VillaManinRecordRejected("conflicting_header_dates")
    if ambiguous:
        raise VillaManinRecordRejected("ambiguous_multiple_dates")
    if len(occurrences) > 1:
        return (
            occurrences[0],
            occurrences[-1],
            " | ".join(source_texts),
            "explicit_occurrences",
            occurrences,
        )
    if len(occurrences) == 1:
        event_date = occurrences[0]
        return (
            event_date,
            event_date,
            source_texts[0],
            "explicit_single",
            [],
        )

    raise VillaManinRecordRejected("date_missing")


def _extract_date(blocks: list[tuple[str, str]], context_years: list[int]):
    headings = [value for tag, value in blocks[:16] if tag in {"h1", "h2", "h3"}]
    if headings:
        try:
            return _extract_date_from_candidates(headings, context_years)
        except VillaManinRecordRejected as exc:
            if exc.reason != "date_missing":
                raise

    calendar_start = None
    for index, (_, value) in enumerate(blocks):
        normalized = _search_text(value)
        if normalized == "programma" or "calendario completo degli appuntamenti" in normalized:
            calendar_start = index + 1
            break
    if calendar_start is not None:
        calendar_candidates = []
        for _, value in blocks[calendar_start : calendar_start + 48]:
            normalized = _search_text(value)
            if _DAY_MONTH_RE.match(normalized) or re.match(r"^\d{1,2}[./]\d{1,2}\b", normalized):
                calendar_candidates.append(value)
        if calendar_candidates:
            return _extract_date_from_candidates(calendar_candidates, context_years)

    early_content = [value for _, value in blocks[:8]]
    return _extract_date_from_candidates(early_content, context_years)


def _format_date(start: date, end: date) -> str:
    start_label = f"{start.day} {_MONTH_LABELS[start.month - 1]} {start.year}"
    if start == end:
        return start_label
    end_label = f"{end.day} {_MONTH_LABELS[end.month - 1]} {end.year}"
    return f"dal {start_label} al {end_label}"


def _extract_description(title: str, paragraphs: list[str]) -> str | None:
    normalized_title = _search_text(title)
    for paragraph in paragraphs:
        candidate = _clean_text(paragraph)
        if len(candidate) < 40 or candidate.isupper():
            continue
        candidate_search = _search_text(candidate)
        if normalized_title and candidate_search.startswith(normalized_title):
            continue
        parsed_range = _parse_explicit_range(candidate)
        if parsed_range and len(candidate) <= len(parsed_range[2]) + 12:
            continue
        if _SINGLE_DATE_RE.fullmatch(candidate_search):
            continue
        return candidate[:600].rstrip()
    return None


def _embedded_terms(record: dict) -> list[str]:
    return _embedded_taxonomy_terms(record, "tipologia")


def _featured_image(record: dict) -> str | None:
    featured_media = record.get("featured_media")
    if not isinstance(featured_media, int):
        raise VillaManinStructureError("featured_media is not an integer")
    if featured_media == 0:
        return None

    embedded = record.get("_embedded")
    media = embedded.get("wp:featuredmedia") if isinstance(embedded, dict) else None
    if not isinstance(media, list) or not media or not isinstance(media[0], dict):
        return None
    image = _trusted_url(media[0].get("source_url"), image=True)
    if not image:
        raise VillaManinStructureError("featured media URL is not trusted")
    return image


def _validate_record_structure(record: object) -> dict:
    if not isinstance(record, dict):
        raise VillaManinStructureError("record is not an object")
    required = {"id", "status", "type", "link", "title", "content", "featured_media"}
    missing = sorted(required - record.keys())
    if missing:
        raise VillaManinStructureError(f"missing fields: {', '.join(missing)}")
    if not isinstance(record.get("title"), dict) or "rendered" not in record["title"]:
        raise VillaManinStructureError("title.rendered is missing")
    if not isinstance(record.get("content"), dict) or "rendered" not in record["content"]:
        raise VillaManinStructureError("content.rendered is missing")
    if not isinstance(record.get("id"), int):
        raise VillaManinStructureError("id is not an integer")
    return record


def parse_villa_manin_record(record: object) -> dict:
    record = _validate_record_structure(record)
    if record.get("status") != "publish" or record.get("type") != "evento":
        raise VillaManinRecordRejected("not_a_published_event")

    title = _clean_text(record["title"].get("rendered"))
    if not title:
        raise VillaManinStructureError("title.rendered is empty")
    event_url = _trusted_url(record.get("link"), event_page=True)
    if not event_url:
        raise VillaManinRecordRejected("untrusted_event_url")

    content_html = record["content"].get("rendered")
    if not isinstance(content_html, str):
        raise VillaManinStructureError("content.rendered is not text")
    extractor = _ElementorTextExtractor()
    extractor.feed(content_html)
    start, end, date_source_text, date_confidence, occurrences = _extract_date(
        extractor.blocks,
        _embedded_years(record),
    )

    all_text = _clean_text(" ".join([*extractor.headings, *extractor.paragraphs]))
    venue = (
        VILLA_MANIN_CANONICAL_VENUE
        if re.search(r"\bvilla manin\b", _search_text(all_text))
        else None
    )
    explicit_event_city = bool(re.search(r"\bcodroipo\b", _search_text(all_text)))
    event_city = VILLA_MANIN_CANONICAL_CITY if explicit_event_city else None
    municipality_resolution = "explicit_event_text" if explicit_event_city else None
    if venue == VILLA_MANIN_CANONICAL_VENUE and not event_city:
        event_city = VILLA_MANIN_CANONICAL_CITY
        municipality_resolution = "approved_canonical_venue"
    description = _extract_description(title, extractor.paragraphs)
    image = _featured_image(record)
    categories = _embedded_terms(record)
    missing_fields = [
        field
        for field, value in (
            ("description", description),
            ("image", image),
            ("venue", venue),
            ("event_city", event_city),
        )
        if not value
    ]

    return {
        "shadow": True,
        "eligible_for_review": True,
        "parser_version": VILLA_MANIN_PARSER_VERSION,
        "source": VILLA_MANIN_SOURCE,
        "source_id": str(record["id"]),
        "title": title,
        "url": event_url,
        "official_site": VILLA_MANIN_SITE_URL,
        "date": _format_occurrences(occurrences) if occurrences else _format_date(start, end),
        "date_source_text": date_source_text,
        "date_confidence": date_confidence,
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "occurrences": [item.isoformat() for item in occurrences],
        "description": description,
        "image": image,
        "image_original": image,
        "venue": venue,
        "event_city": event_city,
        "place": f"{venue} - {event_city}" if venue and event_city else event_city or venue,
        "canonical_venue": {
            "venue": VILLA_MANIN_CANONICAL_VENUE,
            "locality": VILLA_MANIN_CANONICAL_LOCALITY,
            "municipality": VILLA_MANIN_CANONICAL_CITY,
            "address": VILLA_MANIN_CANONICAL_ADDRESS,
        }
        if municipality_resolution == "approved_canonical_venue"
        else None,
        "provider_categories": ", ".join(categories) or None,
        "provider_category_list": categories,
        "location_evidence": {
            "venue_explicit": bool(venue),
            "municipality_explicit": explicit_event_city,
            "municipality_resolution": municipality_resolution,
        },
        "missing_fields": missing_fields,
    }


def audit_villa_manin_payload(payload: object, *, as_of: date | None = None) -> dict:
    as_of = as_of or date.today()
    if not isinstance(payload, list):
        return {
            "status": "blocked",
            "shadow": True,
            "source": VILLA_MANIN_SOURCE,
            "parser_version": VILLA_MANIN_PARSER_VERSION,
            "records": [],
            "rejected": [],
            "structure_errors": ["payload is not a list"],
            "counts": {"received": 0, "accepted": 0, "rejected": 0, "inactive": 0},
        }

    records: list[dict] = []
    rejected: list[dict] = []
    structure_errors: list[str] = []
    inactive = 0
    for index, item in enumerate(payload):
        source_id = str(item.get("id")) if isinstance(item, dict) and item.get("id") else None
        source_title = None
        source_url = None
        if isinstance(item, dict):
            raw_title = item.get("title")
            if isinstance(raw_title, dict):
                source_title = _clean_text(raw_title.get("rendered")) or None
            source_url = _trusted_url(item.get("link"), event_page=True)
        try:
            parsed = parse_villa_manin_record(item)
            parsed["upcoming_occurrences"] = [
                value
                for value in parsed["occurrences"]
                if date.fromisoformat(value) >= as_of
            ]
            if date.fromisoformat(parsed["end_date"]) < as_of:
                inactive += 1
            else:
                records.append(parsed)
        except VillaManinRecordRejected as exc:
            rejected.append(
                {
                    "index": index,
                    "source_id": source_id,
                    "title": source_title,
                    "url": source_url,
                    "reason": exc.reason,
                }
            )
        except VillaManinStructureError as exc:
            structure_errors.append(f"record {source_id or index}: {exc}")

    status = "blocked" if structure_errors else "ready_for_review"
    return {
        "status": status,
        "shadow": True,
        "source": VILLA_MANIN_SOURCE,
        "parser_version": VILLA_MANIN_PARSER_VERSION,
        "records": records,
        "rejected": rejected,
        "structure_errors": structure_errors,
        "counts": {
            "received": len(payload),
            "accepted": len(records),
            "rejected": len(rejected),
            "inactive": inactive,
        },
    }


def fetch_villa_manin_shadow(
    *,
    page: int = 1,
    per_page: int = 100,
    as_of: date | None = None,
    session=requests,
) -> dict:
    if not 1 <= page:
        raise ValueError("page must be positive")
    if not 1 <= per_page <= 100:
        raise ValueError("per_page must be between 1 and 100")

    response = get_with_single_transient_retry(
        session.get,
        VILLA_MANIN_API_URL,
        params={"page": page, "per_page": per_page, "_embed": "1"},
        headers={"User-Agent": "Meteo-Friul-Source-Audit/1.0"},
        timeout=(4, 15),
    )
    report = audit_villa_manin_payload(response.json(), as_of=as_of)
    report["fetch"] = {
        "page": page,
        "per_page": per_page,
        "total": response.headers.get("X-WP-Total"),
        "total_pages": response.headers.get("X-WP-TotalPages"),
    }
    return report


def fetch_villa_manin_shadow_catalog(
    *,
    per_page: int = 100,
    as_of: date | None = None,
    session=requests,
) -> dict:
    if not 1 <= per_page <= 100:
        raise ValueError("per_page must be between 1 and 100")

    payload: list[dict] = []
    total = None
    total_pages = 1
    page = 1
    while page <= total_pages:
        response = get_with_single_transient_retry(
            session.get,
            VILLA_MANIN_API_URL,
            params={"page": page, "per_page": per_page, "_embed": "1"},
            headers={"User-Agent": "Meteo-Friul-Source-Audit/1.0"},
            timeout=(4, 15),
        )
        page_payload = response.json()
        if not isinstance(page_payload, list):
            return audit_villa_manin_payload(page_payload, as_of=as_of)
        payload.extend(page_payload)

        if page == 1:
            total = response.headers.get("X-WP-Total")
            try:
                total_pages = int(response.headers.get("X-WP-TotalPages") or 1)
            except (TypeError, ValueError):
                total_pages = 1
            if not 1 <= total_pages <= 20:
                raise VillaManinStructureError("unexpected pagination size")
        page += 1

    report = audit_villa_manin_payload(payload, as_of=as_of)
    report["fetch"] = {
        "pages": total_pages,
        "per_page": per_page,
        "total": total,
    }
    return report


def compare_villa_manin_with_visible_events(
    shadow_records: list[dict],
    visible_events: list[dict],
    *,
    comparator: Callable[[dict, dict], bool],
) -> list[dict]:
    matches: list[dict] = []
    for shadow in shadow_records:
        for visible in visible_events:
            comparison_records = [shadow]
            if shadow.get("occurrences"):
                comparison_records = [
                    {**shadow, "date": _format_date(date.fromisoformat(value), date.fromisoformat(value))}
                    for value in shadow["occurrences"]
                ]
            if any(comparator(candidate, visible) for candidate in comparison_records):
                matches.append(
                    {
                        "villa_manin_source_id": shadow.get("source_id"),
                        "villa_manin_title": shadow.get("title"),
                        "visible_source": visible.get("source"),
                        "visible_title": visible.get("title"),
                        "visible_url": visible.get("url"),
                    }
                )
    return matches
