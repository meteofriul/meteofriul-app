from __future__ import annotations

import hashlib
import re
import unicodedata
from datetime import date
from html import unescape
from html.parser import HTMLParser
from typing import Callable
from urllib.parse import urljoin, urlsplit

import requests

from app.events.http_client import get_with_single_transient_retry


ERPAC_SOURCE = "ERPAC FVG"
ERPAC_HOME_URL = "https://erpac.regione.fvg.it/"
ERPAC_MAGAZZINO_HOSTS = {"magazzinodelleidee.it", "www.magazzinodelleidee.it"}
ERPAC_MAGAZZINO_API_URL = "https://magazzinodelleidee.it/wp-json/wp/v2/evento"
ERPAC_PARSER_VERSION = "erpac-curated-home-v2"
ERPAC_TARGET_SECTIONS = {
    "eventi, rassegne e concerti": "evento",
    "mostre": "mostra",
}
ERPAC_KNOWN_MUNICIPALITIES = (
    "Codroipo",
    "Gorizia",
    "Gradisca d'Isonzo",
    "San Vito al Tagliamento",
    "Trieste",
)
ERPAC_DEDUPE_STOPWORDS = {
    "a",
    "al",
    "alla",
    "arte",
    "codroipo",
    "con",
    "d",
    "da",
    "dal",
    "del",
    "della",
    "di",
    "e",
    "evento",
    "fvg",
    "friuli",
    "gli",
    "i",
    "il",
    "in",
    "la",
    "le",
    "lo",
    "manin",
    "mostra",
    "per",
    "un",
    "una",
    "venezia",
    "villa",
}

ERPAC_REVIEWED_RECORD_RESOLUTIONS = (
    {
        "url": "https://erpac.regione.fvg.it/it/dag-digital-art-gallery-gorizia-165754",
        "reviewed_on": "2026-08-19",
        "expected_fields": {
            "start_date": "2025-12-17",
            "end_date": None,
            "provider_home_place": "Galleria Bombi, Gorizia",
            "provider_detail_place": "Galleria Giorgio Bombi, Gorizia",
        },
        "set_fields": {
            "date": "dal 17 dicembre 2025 al 31 dicembre 2026",
            "date_source_text": "Fruibile dal 17/12/2025 al 31/12/2026",
            "date_confidence": "reviewed_official_range",
            "end_date": "2026-12-31",
            "provider_place": "Galleria Giorgio Bombi, Gorizia",
            "venue": "Galleria Giorgio Bombi",
            "event_city": "Gorizia",
            "place": "Gorizia",
        },
        "clear_flags": ("location_difference_detail", "open_ended_date"),
        "reason": "La pagina ERPAC di accesso indica l'intervallo completo; Galleria Bombi e Galleria Giorgio Bombi sono la stessa sede.",
        "evidence_urls": (
            "https://erpac.regione.fvg.it/it/dag-digital-art-gallery-gorizia-165754",
            "https://erpac.regione.fvg.it/it/dag-digital-art-gallery-singolo-ingresso-fruibile-dal-17122025-al-31122026-161410",
        ),
    },
    {
        "url": "https://palazzoattems.regione.fvg.it/it/italia-settanta-165450",
        "reviewed_on": "2026-08-19",
        "expected_fields": {
            "start_date": "2026-06-27",
            "end_date": "2026-11-29",
            "provider_detail_subtitle": "Dal 27 giugno al 29 novembre 2026",
        },
        "required_text": ("Palazzo Attems Petzenstein a Gorizia",),
        "set_fields": {
            "provider_place": "Palazzo Attems Petzenstein, Gorizia",
            "venue": "Palazzo Attems Petzenstein",
            "event_city": "Gorizia",
            "place": "Gorizia",
        },
        "clear_flags": ("missing_venue", "missing_event_city"),
        "reason": "La pagina dedicata nomina esplicitamente Palazzo Attems Petzenstein a Gorizia.",
        "evidence_urls": (
            "https://palazzoattems.regione.fvg.it/it/italia-settanta-165450",
        ),
    },
    {
        "url": "https://museiprovincialigorizia.regione.fvg.it/it/via-per-le-strade-paolo-gasparini-167022",
        "reviewed_on": "2026-08-19",
        "expected_fields": {
            "start_date": "2026-04-25",
            "end_date": "2026-09-27",
            "provider_home_place": "Casa Morassi, Gorizia",
            "provider_detail_place": "Borgo Castello 20, Gorizia",
        },
        "set_fields": {
            "provider_place": "Casa Panizzolo Morassi, Borgo Castello 20, Gorizia",
            "venue": "Casa Panizzolo Morassi",
            "event_city": "Gorizia",
            "place": "Gorizia",
        },
        "clear_flags": ("location_difference_detail",),
        "reason": "La home usa il nome Casa Morassi e il dettaglio il suo indirizzo Borgo Castello 20; il calendario ufficiale li associa alla stessa sede.",
        "evidence_urls": (
            "https://museiprovincialigorizia.regione.fvg.it/it/via-per-le-strade-paolo-gasparini-167022",
            "https://erpac.regione.fvg.it/media/files/ERPAC/attachment/erpac-calendarioeventi2026.pdf",
        ),
    },
    {
        "url": "https://erpac.regione.fvg.it/it/mostra-intrecci-di-segni-e-di-fili-169817",
        "reviewed_on": "2026-08-19",
        "expected_fields": {
            "start_date": "2026-06-25",
            "end_date": "2026-09-27",
            "provider_detail_subtitle": "Dal 25 giugno al 26 settembre, Showroom Merletto goriziano, Gorizia",
        },
        "set_fields": {
            "date": "dal 25 giugno al 26 settembre 2026",
            "date_source_text": "Dal 25 giugno al 26 settembre 2026",
            "date_confidence": "reviewed_official_range",
            "end_date": "2026-09-26",
        },
        "clear_flags": ("date_conflict_detail",),
        "reason": "La pagina dedicata e il calendario ERPAC concordano sul 26 settembre; la card home riporta 27 settembre.",
        "evidence_urls": (
            "https://erpac.regione.fvg.it/it/mostra-intrecci-di-segni-e-di-fili-169817",
            "https://erpac.regione.fvg.it/media/files/ERPAC/attachment/erpac-calendarioeventi2026.pdf",
        ),
    },
)

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
_TEXT_RANGE_RE = re.compile(
    rf"\b(?:dal|da)\s+(?P<d1>\d{{1,2}})(?:[°º])?\s+"
    rf"(?P<m1>{_MONTH_PATTERN})(?:\s+(?P<y1>20\d{{2}}))?\s+"
    rf"(?:al|all['’]|[-–—])\s*(?P<d2>\d{{1,2}})(?:[°º])?\s+"
    rf"(?P<m2>{_MONTH_PATTERN})\s+(?P<y2>20\d{{2}})\b",
    re.IGNORECASE,
)
_DATE_TOKEN_RE = re.compile(
    rf"\b(?P<day>\d{{1,2}})(?:[°º])?\s+(?P<month>{_MONTH_PATTERN})"
    rf"(?:\s+(?P<year>20\d{{2}}))?\b",
    re.IGNORECASE,
)


class ErpacStructureError(ValueError):
    """The reviewed ERPAC home or detail structure has changed."""


class ErpacRecordRejected(ValueError):
    """A curated card is not precise enough to become an event record."""

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


def _clean_text(value: object) -> str:
    return re.sub(r"[ \t\f\v]+", " ", unescape(str(value or ""))).strip()


def _clean_inline_text(value: object) -> str:
    return re.sub(r"\s+", " ", unescape(str(value or ""))).strip()


def _search_text(value: object) -> str:
    normalized = unicodedata.normalize("NFKD", _clean_text(value))
    return normalized.encode("ascii", "ignore").decode("ascii").lower()


def _trusted_content_url(value: object) -> str | None:
    url = _clean_text(value)
    if not url:
        return None
    parsed = urlsplit(url)
    host = (parsed.hostname or "").lower()
    is_official_region = host == "regione.fvg.it" or host.endswith(".regione.fvg.it")
    is_villa_manin = host in {"villamanin.it", "www.villamanin.it"}
    is_magazzino = host in ERPAC_MAGAZZINO_HOSTS
    if parsed.scheme != "https" or not (
        is_official_region or is_villa_manin or is_magazzino
    ):
        return None
    if parsed.username or parsed.password or parsed.port or parsed.query or parsed.fragment:
        return None
    if is_villa_manin and not re.fullmatch(r"/evento/[a-z0-9-]+/", parsed.path):
        return None
    if is_magazzino and not re.fullmatch(r"/evento/[a-z0-9-]+/", parsed.path):
        return None
    if is_official_region and not parsed.path.startswith("/it/"):
        return None
    return url


def _response_utf8(response) -> str:
    content = getattr(response, "content", None)
    if isinstance(content, bytes):
        return content.decode("utf-8")
    return str(getattr(response, "text", ""))


def _trusted_erpac_image_url(value: object) -> str | None:
    url = urljoin(ERPAC_HOME_URL, _clean_text(value))
    parsed = urlsplit(url)
    if (
        parsed.scheme != "https"
        or parsed.hostname != "erpac.regione.fvg.it"
        or parsed.username
        or parsed.password
        or parsed.port
        or parsed.query
        or parsed.fragment
        or not parsed.path.startswith("/media/files/ERPAC/")
    ):
        return None
    return url


def is_trusted_erpac_content_url(value: object) -> bool:
    return bool(_trusted_content_url(value))


def is_trusted_erpac_image_url(value: object) -> bool:
    return bool(_trusted_erpac_image_url(value))


class _ErpacHomeParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.sections_seen: set[str] = set()
        self.cards: list[dict] = []
        self._section: str | None = None
        self._heading_parts: list[str] | None = None
        self._title_parts: list[str] | None = None
        self._card: dict | None = None
        self._card_div_depth: int | None = None
        self._description_started = False

    @staticmethod
    def _attrs(attrs) -> dict[str, str]:
        return {str(key): str(value or "") for key, value in attrs}

    def handle_starttag(self, tag: str, attrs):
        tag = tag.lower()
        attributes = self._attrs(attrs)
        if tag == "h3" and "h4" in attributes.get("class", "").split():
            self._heading_parts = []

        if (
            tag == "div"
            and "splide__slide" in attributes.get("class", "").split()
            and self._section in ERPAC_TARGET_SECTIONS
            and self._card is None
        ):
            self._card = {
                "section": self._section,
                "title": None,
                "url": None,
                "image": None,
                "summary_parts": [],
            }
            self._card_div_depth = 1
            self._description_started = False
        elif tag == "div" and self._card is not None:
            self._card_div_depth += 1

        if self._card is None:
            return
        if tag == "img" and not self._card["image"]:
            self._card["image"] = attributes.get("src")
        if tag == "h4":
            self._title_parts = []
        if tag == "a" and self._title_parts is not None:
            self._card["url"] = attributes.get("href")
        if tag == "p" and self._card.get("title"):
            self._description_started = True
        if tag == "br" and self._description_started:
            self._card["summary_parts"].append("\n")

    def handle_startendtag(self, tag: str, attrs):
        if self._card is not None and tag.lower() == "br" and self._description_started:
            self._card["summary_parts"].append("\n")

    def handle_data(self, data: str):
        if self._heading_parts is not None:
            self._heading_parts.append(data)
        if self._title_parts is not None:
            self._title_parts.append(data)
        elif self._card is not None and self._description_started:
            self._card["summary_parts"].append(data)

    def handle_endtag(self, tag: str):
        tag = tag.lower()
        if tag == "h3" and self._heading_parts is not None:
            heading = _search_text(" ".join(self._heading_parts))
            self._section = heading
            if heading in ERPAC_TARGET_SECTIONS:
                self.sections_seen.add(heading)
            self._heading_parts = None

        if tag == "h4" and self._title_parts is not None and self._card is not None:
            self._card["title"] = _clean_text(" ".join(self._title_parts))
            self._title_parts = None

        if tag == "div" and self._card is not None:
            self._card_div_depth -= 1
            if self._card_div_depth == 0:
                summary = "".join(self._card.pop("summary_parts"))
                self._card["summary"] = re.sub(
                    r" *\n *", "\n", _clean_text(summary)
                )
                self.cards.append(self._card)
                self._card = None
                self._card_div_depth = None
                self._description_started = False


class _ErpacRegionalDetailParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.canonical_url: str | None = None
        self.title: str | None = None
        self.subtitle: str | None = None
        self.paragraphs: list[str] = []
        self._capture: str | None = None
        self._capture_depth = 0
        self._parts: list[str] = []
        self._inside_description = False
        self._description_div_depth = 0

    @staticmethod
    def _attrs(attrs) -> dict[str, str]:
        return {str(key): str(value or "") for key, value in attrs}

    def _begin_capture(self, kind: str):
        self._capture = kind
        self._capture_depth = 1
        self._parts = []

    def handle_starttag(self, tag: str, attrs):
        tag = tag.lower()
        attributes = self._attrs(attrs)
        classes = attributes.get("class", "").split()
        if tag == "link" and "canonical" in attributes.get("rel", "").split():
            self.canonical_url = attributes.get("href")

        if tag == "div" and "testolungo" in classes and not self._inside_description:
            self._inside_description = True
            self._description_div_depth = 1
        elif tag == "div" and self._inside_description:
            self._description_div_depth += 1

        if self._capture:
            if tag == "br":
                self._parts.append(" ")
            else:
                self._capture_depth += 1
            return
        if tag == "h2" and "title-xxxlarge" in classes:
            self._begin_capture("title")
        elif tag == "p" and "fst-italic" in classes and self.subtitle is None:
            self._begin_capture("subtitle")
        elif tag == "p" and self._inside_description:
            self._begin_capture("paragraph")

    def handle_startendtag(self, tag: str, attrs):
        if self._capture and tag.lower() == "br":
            self._parts.append(" ")

    def handle_data(self, data: str):
        if self._capture:
            self._parts.append(data)

    def handle_endtag(self, tag: str):
        tag = tag.lower()
        if self._capture:
            self._capture_depth -= 1
            if self._capture_depth == 0:
                value = _clean_inline_text(" ".join(self._parts))
                if self._capture == "title":
                    self.title = value or None
                elif self._capture == "subtitle":
                    self.subtitle = value or None
                elif value:
                    self.paragraphs.append(value)
                self._capture = None
                self._parts = []

        if tag == "div" and self._inside_description:
            self._description_div_depth -= 1
            if self._description_div_depth == 0:
                self._inside_description = False


class _ParagraphExtractor(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.paragraphs: list[str] = []
        self._depth = 0
        self._parts: list[str] = []

    def handle_starttag(self, tag: str, attrs):
        tag = tag.lower()
        if self._depth:
            if tag == "br":
                self._parts.append(" ")
            else:
                self._depth += 1
        elif tag == "p":
            self._depth = 1
            self._parts = []

    def handle_startendtag(self, tag: str, attrs):
        if self._depth and tag.lower() == "br":
            self._parts.append(" ")

    def handle_data(self, data: str):
        if self._depth:
            self._parts.append(data)

    def handle_endtag(self, tag: str):
        if not self._depth:
            return
        self._depth -= 1
        if self._depth == 0:
            value = _clean_inline_text(" ".join(self._parts))
            if value:
                self.paragraphs.append(value)
            self._parts = []


def _valid_date(year: object, month: object, day: object) -> date:
    try:
        return date(int(year), int(month), int(day))
    except (TypeError, ValueError) as exc:
        raise ErpacRecordRejected("invalid_date") from exc


def _format_date(value: date) -> str:
    return f"{value.day} {_MONTH_LABELS[value.month - 1]} {value.year}"


def _extract_dates(summary: str):
    normalized = _search_text(summary)
    range_match = _TEXT_RANGE_RE.search(normalized)
    if range_match:
        end_year = int(range_match["y2"])
        start = _valid_date(
            int(range_match["y1"] or end_year),
            _MONTHS[range_match["m1"]],
            range_match["d1"],
        )
        end = _valid_date(end_year, _MONTHS[range_match["m2"]], range_match["d2"])
        if end < start:
            raise ErpacRecordRejected("invalid_date_range")
        return {
            "date": f"dal {_format_date(start)} al {_format_date(end)}",
            "date_source_text": _clean_text(range_match.group(0)),
            "date_confidence": "explicit_range",
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "occurrences": [],
        }

    matches = list(_DATE_TOKEN_RE.finditer(normalized))
    if not matches:
        raise ErpacRecordRejected("date_missing")

    current_year: int | None = None
    occurrences_reversed: list[date] = []
    unresolved = False
    for match in reversed(matches):
        if match["year"]:
            current_year = int(match["year"])
        if current_year is None:
            unresolved = True
            continue
        parsed = _valid_date(current_year, _MONTHS[match["month"]], match["day"])
        if parsed not in occurrences_reversed:
            occurrences_reversed.append(parsed)

    if unresolved or not occurrences_reversed:
        raise ErpacRecordRejected("date_year_missing")
    occurrences = sorted(occurrences_reversed)
    if len(occurrences) > 1:
        return {
            "date": " · ".join(_format_date(item) for item in occurrences),
            "date_source_text": _clean_text(summary.split("\n", 1)[0]),
            "date_confidence": "explicit_occurrences",
            "start_date": occurrences[0].isoformat(),
            "end_date": occurrences[-1].isoformat(),
            "occurrences": [item.isoformat() for item in occurrences],
        }

    single = occurrences[0]
    prefix = normalized[: matches[0].start()].strip()
    start_only = bool(re.search(r"\b(?:dal|da)\s*$", prefix))
    return {
        "date": _format_date(single),
        "date_source_text": _clean_text(matches[0].group(0)),
        "date_confidence": "explicit_start_only" if start_only else "explicit_single",
        "start_date": single.isoformat(),
        "end_date": None if start_only else single.isoformat(),
        "occurrences": [],
    }


def _extract_location(summary: str):
    normalized = _search_text(summary)
    cities = [
        municipality
        for municipality in ERPAC_KNOWN_MUNICIPALITIES
        if re.search(rf"\b{re.escape(_search_text(municipality))}\b", normalized)
    ]
    event_city = cities[0] if len(cities) == 1 else None
    lines = [_clean_text(line) for line in summary.splitlines() if _clean_text(line)]
    provider_place = lines[-1].rstrip(",") if len(lines) > 1 else None
    venue = None
    if provider_place:
        if re.search(r"\bvilla manin\b", _search_text(provider_place)):
            venue = "Villa Manin"
        else:
            first_part = _clean_text(provider_place.split(",", 1)[0])
            if first_part and _search_text(first_part) != _search_text(event_city):
                venue = first_part
    return provider_place, venue, event_city


def _extract_explicit_place(value: object):
    provider_place = _clean_inline_text(value).rstrip(",")
    parts = [part.strip() for part in provider_place.split(",") if part.strip()]
    if parts:
        first = _search_text(parts[0])
        if (
            re.search(rf"\b\d{{1,2}}\s+{_MONTH_PATTERN}\b", first)
            and re.search(r"\b(?:dal|da|fino al|al)\b", first)
        ):
            parts.pop(0)
            provider_place = ", ".join(parts)
    if not provider_place:
        return None, None, None
    _, venue, event_city = _extract_location(f"dettaglio\n{provider_place}")
    return provider_place, venue, event_city


def _extract_official_description(title: str, paragraphs: list[str]) -> str | None:
    normalized_title = _search_text(title)
    for paragraph in paragraphs:
        candidate = _clean_inline_text(paragraph)
        if len(candidate) < 40 or candidate.isupper():
            continue
        normalized = _search_text(candidate)
        if normalized_title and normalized.startswith(normalized_title):
            continue
        if normalized.startswith("data pubblicazione"):
            continue
        if len(candidate) <= 600:
            return candidate
        excerpt = candidate[:600]
        sentence_end = max(
            excerpt.rfind(". "), excerpt.rfind("! "), excerpt.rfind("? ")
        )
        if sentence_end >= 240:
            return excerpt[: sentence_end + 1].rstrip()
        return excerpt.rstrip(" ,;:-") + "…"
    return None


def _detail_date_conflicts(record: dict, subtitle: object) -> bool:
    normalized = _search_text(subtitle)
    tokens = list(_DATE_TOKEN_RE.finditer(normalized))
    if not tokens:
        return False
    start = date.fromisoformat(record["start_date"])
    end = date.fromisoformat(record["end_date"] or record["start_date"])
    values = [(_MONTHS[item["month"]], int(item["day"])) for item in tokens]
    if re.search(r"\bfino al\b", normalized):
        return values[-1] != (end.month, end.day)
    if re.search(r"\b(?:dal|da)\b", normalized):
        if values[0] != (start.month, start.day):
            return True
        return len(values) > 1 and values[-1] != (end.month, end.day)
    return False


def _same_canonical_url(left: object, right: object) -> bool:
    return _clean_text(left).rstrip("/") == _clean_text(right).rstrip("/")


def _apply_reviewed_record_resolution(record: dict) -> dict:
    resolution = next(
        (
            item
            for item in ERPAC_REVIEWED_RECORD_RESOLUTIONS
            if _same_canonical_url(record.get("url"), item["url"])
        ),
        None,
    )
    if not resolution:
        return record

    expected_fields = resolution.get("expected_fields") or {}
    evidence_matches = all(
        record.get(field) == expected
        for field, expected in expected_fields.items()
    )
    searchable_text = _search_text(
        " ".join(
            _clean_inline_text(record.get(field))
            for field in ("title", "description", "provider_detail_subtitle")
        )
    )
    required_text_matches = all(
        _search_text(value) in searchable_text
        for value in resolution.get("required_text") or ()
    )
    if not evidence_matches or not required_text_matches:
        record["manual_review_flags"] = sorted(
            set(record.get("manual_review_flags", []))
            | {"reviewed_resolution_evidence_changed"}
        )
        return record

    set_fields = resolution.get("set_fields") or {}
    original_fields = {field: record.get(field) for field in set_fields}
    record.update(set_fields)
    clear_flags = set(resolution.get("clear_flags") or ())
    record["manual_review_flags"] = sorted(
        flag
        for flag in record.get("manual_review_flags", [])
        if flag not in clear_flags
    )
    record["review_resolution"] = {
        "reviewed_on": resolution["reviewed_on"],
        "reason": resolution["reason"],
        "evidence_urls": list(resolution["evidence_urls"]),
        "original_fields": original_fields,
        "resolved_fields": dict(set_fields),
    }
    if any(field in set_fields for field in ("venue", "event_city", "place")):
        record["location_evidence"] = {
            "venue_explicit": bool(record.get("venue")),
            "municipality_explicit": bool(record.get("event_city")),
            "resolution": "reviewed_official_evidence",
        }
    return record


def parse_erpac_regional_detail_html(html: object, *, expected_url: str) -> dict:
    if not isinstance(html, str) or not html.strip():
        raise ErpacStructureError("regional detail payload is not HTML text")
    if not _trusted_content_url(expected_url):
        raise ErpacStructureError("regional detail expected URL is not trusted")

    parser = _ErpacRegionalDetailParser()
    parser.feed(html)
    canonical_url = _trusted_content_url(parser.canonical_url)
    if not canonical_url or not _same_canonical_url(canonical_url, expected_url):
        raise ErpacStructureError("regional detail canonical URL changed")
    if not parser.title:
        raise ErpacStructureError("regional detail title is missing")
    if "\ufffd" in parser.title:
        raise ErpacStructureError("regional detail title has invalid encoding")

    provider_place, venue, event_city = _extract_explicit_place(parser.subtitle)
    return {
        "detail_kind": "regional_prerender",
        "canonical_url": canonical_url,
        "title": parser.title,
        "description": _extract_official_description(
            parser.title, parser.paragraphs
        ),
        "provider_subtitle": parser.subtitle,
        "provider_place": provider_place,
        "venue": venue,
        "event_city": event_city,
    }


def parse_erpac_magazzino_payload(payload: object, *, expected_url: str) -> dict:
    if not isinstance(payload, list) or len(payload) != 1 or not isinstance(payload[0], dict):
        raise ErpacStructureError("Magazzino detail payload is not one event")
    record = payload[0]
    if record.get("type") != "evento" or record.get("status") != "publish":
        raise ErpacStructureError("Magazzino detail is not a published event")
    link = _trusted_content_url(record.get("link"))
    if not link or not _same_canonical_url(link, expected_url):
        raise ErpacStructureError("Magazzino detail canonical URL changed")

    title_data = record.get("title")
    content_data = record.get("content")
    if not isinstance(title_data, dict) or not isinstance(content_data, dict):
        raise ErpacStructureError("Magazzino title or content schema changed")
    title = _clean_inline_text(title_data.get("rendered"))
    content = content_data.get("rendered")
    if not title or not isinstance(content, str):
        raise ErpacStructureError("Magazzino title or content is missing")
    if "\ufffd" in title or "\ufffd" in content:
        raise ErpacStructureError("Magazzino detail has invalid encoding")

    parser = _ParagraphExtractor()
    parser.feed(content)
    return {
        "detail_kind": "magazzino_wordpress",
        "canonical_url": link,
        "title": title,
        "description": _extract_official_description(title, parser.paragraphs),
        "provider_place": None,
        "venue": None,
        "event_city": None,
    }


def _refresh_record_review_state(record: dict) -> dict:
    flags = [
        flag
        for flag in record.get("manual_review_flags", [])
        if flag != "open_ended_date" and not flag.startswith("missing_")
    ]
    if record.get("date_confidence") == "explicit_start_only":
        flags.append("open_ended_date")
    for field in ("description", "image", "venue", "event_city"):
        if not record.get(field):
            flags.append(f"missing_{field}")
    record["missing_fields"] = [
        value.removeprefix("missing_")
        for value in flags
        if value.startswith("missing_")
    ]
    record["manual_review_flags"] = flags
    record["eligible_for_review"] = not flags
    return record


def enrich_erpac_home_record(record: dict, detail: dict) -> dict:
    enriched = dict(record)
    enriched["provider_home_title"] = record.get("title")
    enriched["provider_detail_title"] = detail.get("title")
    if detail.get("detail_kind") == "regional_prerender" and detail.get("title"):
        enriched["title"] = detail["title"]
    enriched["description"] = detail.get("description")
    enriched["detail_status"] = detail.get("detail_kind")
    enriched["provider_detail_subtitle"] = detail.get("provider_subtitle")
    if _detail_date_conflicts(record, detail.get("provider_subtitle")):
        enriched["manual_review_flags"] = sorted(
            set(enriched.get("manual_review_flags", [])) | {"date_conflict_detail"}
        )

    if detail.get("provider_place"):
        enriched["provider_home_place"] = record.get("provider_place")
        enriched["provider_detail_place"] = detail["provider_place"]
        home_venue = _search_text(record.get("venue"))
        detail_venue = _search_text(detail.get("venue"))
        home_city = _search_text(record.get("event_city"))
        detail_city = _search_text(detail.get("event_city"))
        if home_city and detail_city and home_city != detail_city:
            enriched["manual_review_flags"] = sorted(
                set(enriched.get("manual_review_flags", []))
                | {"location_conflict_detail"}
            )
        elif home_venue and detail_venue and not (
            home_venue == detail_venue
            or home_venue in detail_venue
            or detail_venue in home_venue
        ):
            enriched["manual_review_flags"] = sorted(
                set(enriched.get("manual_review_flags", []))
                | {"location_difference_detail"}
            )
        enriched["provider_place"] = detail["provider_place"]
        enriched["venue"] = detail.get("venue")
        enriched["event_city"] = detail.get("event_city")
        enriched["place"] = detail.get("event_city") or detail.get("venue")
        enriched["location_evidence"] = {
            "venue_explicit": bool(detail.get("venue")),
            "municipality_explicit": bool(detail.get("event_city")),
        }
    return _refresh_record_review_state(_apply_reviewed_record_resolution(enriched))


def parse_erpac_home_card(card: object) -> dict:
    if not isinstance(card, dict):
        raise ErpacStructureError("card is not an object")
    title = _clean_text(card.get("title"))
    summary = _clean_text(card.get("summary"))
    section = _search_text(card.get("section"))
    if not title or not summary or section not in ERPAC_TARGET_SECTIONS:
        raise ErpacStructureError("card title, summary, or reviewed section is missing")
    if "\ufffd" in title or "\ufffd" in summary:
        raise ErpacRecordRejected("invalid_text_encoding")

    url = _trusted_content_url(card.get("url"))
    if not url:
        raw_url = _clean_text(card.get("url"))
        if raw_url.lower().endswith(".pdf"):
            raise ErpacRecordRejected("non_event_resource")
        raise ErpacRecordRejected("untrusted_content_url")
    image = _trusted_erpac_image_url(card.get("image"))
    dates = _extract_dates(summary)
    provider_place, venue, event_city = _extract_location(summary)
    source_id = hashlib.sha256(url.encode("utf-8")).hexdigest()[:20]

    record = {
        "shadow": True,
        "parser_version": ERPAC_PARSER_VERSION,
        "source": ERPAC_SOURCE,
        "source_id": source_id,
        "title": title,
        "url": url,
        "official_site": ERPAC_HOME_URL,
        "provider_section": section,
        "provider_summary": summary,
        "provider_categories": ERPAC_TARGET_SECTIONS[section],
        "provider_category_list": [ERPAC_TARGET_SECTIONS[section]],
        **dates,
        "description": None,
        "image": image,
        "image_original": image,
        "provider_place": provider_place,
        "venue": venue,
        "event_city": event_city,
        "place": event_city or venue,
        "location_evidence": {
            "venue_explicit": bool(venue),
            "municipality_explicit": bool(event_city),
        },
    }
    return _refresh_record_review_state(record)


def audit_erpac_home_html(html: object, *, as_of: date | None = None) -> dict:
    as_of = as_of or date.today()
    if not isinstance(html, str) or not html.strip():
        return {
            "status": "blocked",
            "shadow": True,
            "source": ERPAC_SOURCE,
            "parser_version": ERPAC_PARSER_VERSION,
            "records": [],
            "rejected": [],
            "structure_errors": ["home payload is not HTML text"],
            "counts": {"received": 0, "accepted": 0, "rejected": 0, "inactive": 0},
        }

    parser = _ErpacHomeParser()
    parser.feed(html)
    missing_sections = sorted(set(ERPAC_TARGET_SECTIONS) - parser.sections_seen)
    structure_errors = [f"missing section: {value}" for value in missing_sections]
    if parser.sections_seen and not parser.cards:
        structure_errors.append("reviewed sections contain no cards")

    records: list[dict] = []
    rejected: list[dict] = []
    inactive = 0
    for index, card in enumerate(parser.cards):
        try:
            record = parse_erpac_home_card(card)
            end_value = record["end_date"] or record["start_date"]
            if record["date_confidence"] == "explicit_start_only":
                record["active_basis"] = "curated_home"
                records.append(record)
            elif date.fromisoformat(end_value) < as_of:
                inactive += 1
            else:
                records.append(record)
        except ErpacRecordRejected as exc:
            rejected.append(
                {
                    "index": index,
                    "title": _clean_text(card.get("title")),
                    "url": _trusted_content_url(card.get("url")),
                    "summary": _clean_text(card.get("summary")) or None,
                    "section": _clean_text(card.get("section")) or None,
                    "reason": exc.reason,
                }
            )
        except ErpacStructureError as exc:
            structure_errors.append(f"card {index}: {exc}")

    return {
        "status": "blocked" if structure_errors else "ready_for_review",
        "shadow": True,
        "source": ERPAC_SOURCE,
        "parser_version": ERPAC_PARSER_VERSION,
        "records": records,
        "rejected": rejected,
        "structure_errors": structure_errors,
        "counts": {
            "received": len(parser.cards),
            "accepted": len(records),
            "rejected": len(rejected),
            "inactive": inactive,
        },
    }


def _fetch_erpac_detail(record: dict, *, session=requests) -> dict | None:
    parsed = urlsplit(record["url"])
    host = (parsed.hostname or "").lower()
    if host in {"villamanin.it", "www.villamanin.it"}:
        return None
    if host in ERPAC_MAGAZZINO_HOSTS:
        slug = parsed.path.rstrip("/").rsplit("/", 1)[-1]
        response = get_with_single_transient_retry(
            session.get,
            ERPAC_MAGAZZINO_API_URL,
            params={"slug": slug, "_embed": "1"},
            headers={"User-Agent": "Meteo-Friul-Source-Audit/1.0"},
            timeout=(4, 20),
        )
        return parse_erpac_magazzino_payload(response.json(), expected_url=record["url"])

    response = get_with_single_transient_retry(
        session.get,
        record["url"],
        params={"_escaped_fragment_": ""},
        headers={"User-Agent": "Meteo-Friul-Source-Audit/1.0"},
        timeout=(4, 20),
    )
    return parse_erpac_regional_detail_html(
        _response_utf8(response), expected_url=record["url"]
    )


def fetch_erpac_home_shadow(
    *,
    as_of: date | None = None,
    include_details: bool = False,
    session=requests,
) -> dict:
    response = get_with_single_transient_retry(
        session.get,
        ERPAC_HOME_URL,
        params={"_escaped_fragment_": ""},
        headers={"User-Agent": "Meteo-Friul-Source-Audit/1.0"},
        timeout=(4, 20),
    )
    report = audit_erpac_home_html(_response_utf8(response), as_of=as_of)
    report["fetch"] = {"url": ERPAC_HOME_URL, "mode": "official_prerender"}
    if not include_details or report["status"] == "blocked":
        return report

    enriched_records = []
    detail_errors = []
    detail_rejected = []
    for record in report["records"]:
        parsed = urlsplit(record["url"])
        host = (parsed.hostname or "").lower()
        if host in {"villamanin.it", "www.villamanin.it"}:
            covered = dict(record)
            covered["detail_status"] = "covered_by_villa_manin_source"
            covered["manual_review_flags"] = sorted(
                set(covered.get("manual_review_flags", []))
                | {"duplicate_source_villa_manin"}
            )
            covered["eligible_for_review"] = False
            enriched_records.append(covered)
            continue
        try:
            detail = _fetch_erpac_detail(record, session=session)
            enriched_records.append(enrich_erpac_home_record(record, detail))
        except requests.HTTPError as exc:
            status_code = getattr(getattr(exc, "response", None), "status_code", None)
            failed = dict(record)
            failed["eligible_for_review"] = False
            if status_code == 404:
                failed["detail_status"] = "rejected_not_found"
                failed["manual_review_flags"] = sorted(
                    set(failed.get("manual_review_flags", []))
                    | {"detail_not_found"}
                )
                detail_rejected.append(
                    {
                        "source_id": record.get("source_id"),
                        "title": record["title"],
                        "reason": "detail_not_found",
                    }
                )
            else:
                failed["detail_status"] = "blocked"
                failed["manual_review_flags"] = sorted(
                    set(failed.get("manual_review_flags", [])) | {"detail_blocked"}
                )
                detail_errors.append(
                    {
                        "source_id": record.get("source_id"),
                        "title": record["title"],
                        "error": str(exc),
                    }
                )
            enriched_records.append(failed)
        except (requests.RequestException, ErpacStructureError) as exc:
            failed = dict(record)
            failed["detail_status"] = "blocked"
            failed["eligible_for_review"] = False
            failed["manual_review_flags"] = sorted(
                set(failed.get("manual_review_flags", [])) | {"detail_blocked"}
            )
            enriched_records.append(failed)
            detail_errors.append(
                {"source_id": record.get("source_id"), "title": record["title"], "error": str(exc)}
            )

    report["records"] = enriched_records
    report["detail_errors"] = detail_errors
    report["detail_rejected"] = detail_rejected
    report["counts"]["detail_enriched"] = sum(
        item.get("detail_status")
        in {"regional_prerender", "magazzino_wordpress"}
        for item in enriched_records
    )
    report["counts"]["eligible_for_review"] = sum(
        bool(item.get("eligible_for_review")) for item in enriched_records
    )
    report["counts"]["manual_review"] = sum(
        not item.get("eligible_for_review") for item in enriched_records
    )
    report["counts"]["detail_rejected"] = len(detail_rejected)
    if detail_errors:
        report["status"] = "blocked"
    return report


def compare_erpac_with_existing_events(
    shadow_records: list[dict],
    existing_events: list[dict],
    *,
    comparator: Callable[[dict, dict], bool],
) -> list[dict]:
    matches: list[dict] = []
    for shadow in shadow_records:
        comparison_records = [shadow]
        if shadow.get("occurrences"):
            comparison_records = [
                {
                    **shadow,
                    "date": _format_date(date.fromisoformat(value)),
                    "start_date": value,
                    "end_date": value,
                }
                for value in shadow["occurrences"]
            ]
        for existing in existing_events:
            same_url = _same_canonical_url(shadow.get("url"), existing.get("url"))
            shadow_tokens = {
                token
                for token in re.findall(r"[a-z0-9]+", _search_text(shadow.get("title")))
                if token not in ERPAC_DEDUPE_STOPWORDS
                and not re.fullmatch(r"20\d{2}", token)
            }
            existing_tokens = {
                token
                for token in re.findall(r"[a-z0-9]+", _search_text(existing.get("title")))
                if token not in ERPAC_DEDUPE_STOPWORDS
                and not re.fullmatch(r"20\d{2}", token)
            }
            shared_tokens = shadow_tokens & existing_tokens
            titles_related = bool(shared_tokens) and (
                len(shared_tokens) >= 2
                or len(shared_tokens) == min(len(shadow_tokens), len(existing_tokens))
            )
            comparator_match = titles_related and any(
                comparator(candidate, existing) for candidate in comparison_records
            )
            if same_url or comparator_match:
                matches.append(
                    {
                        "erpac_source_id": shadow.get("source_id"),
                        "erpac_title": shadow.get("title"),
                        "existing_source": existing.get("source"),
                        "existing_title": existing.get("title"),
                        "existing_url": existing.get("url"),
                        "match_basis": "canonical_url" if same_url else "production_comparator",
                    }
                )
    return matches
