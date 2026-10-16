"""Fail-closed adapter for the public ARPA FVG/OSMER risks page.

This source is deliberately kept separate from notification jobs.  The PCR
panel may confirm an alert or an explicit no-alert state, while the AMR and
BVMR sections remain distinct meteorological products.  Network acquisition
time is never promoted to an authoritative source timestamp.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from typing import Any, Callable, Iterable, Mapping
from urllib.parse import parse_qsl, urljoin, urlsplit, urlunsplit

import requests


ARPA_OSMER_RISKS_URL = "https://www.meteo.fvg.it/rischi_meteo.php?ln="
ARPA_OSMER_AMR_ARCHIVE_URL = "https://www.meteo.fvg.it/ajax/getPdfArchive.php"
ARPA_OSMER_USER_AGENT = "MeteoFriul/3.0 (+https://meteofriul.app/)"

PCR_INACTIVE_MARKER = "PCR - Nessuna allerta in corso"
PCR_ZONE_NAMES = ("FVG-A", "FVG-B", "FVG-C", "FVG-D")
PCR_MAP_DIMENSIONS = frozenset({"320", "346"})
BVMR_ZONE_NAMES = (
    "Carnia",
    "Tarvisiano",
    "Prealpi carniche",
    "Prealpi giulie",
    "Pianura PN",
    "Pianura UD",
    "Isontino",
    "Laguna",
    "Carso e Trieste",
)

_METEO_HOSTS = {"meteo.fvg.it", "www.meteo.fvg.it"}
_PCR_LINK_HOSTS = {
    "protezionecivile.fvg.it",
    "www.protezionecivile.fvg.it",
    "cfd.protezionecivile.fvg.it",
    "pianiemergenza.protezionecivile.fvg.it",
}
_VOID_TAGS = {
    "area",
    "base",
    "br",
    "col",
    "embed",
    "hr",
    "img",
    "input",
    "link",
    "meta",
    "param",
    "source",
    "track",
    "wbr",
}
_PCR_ACTIVE_RE = re.compile(
    r"^PCR - Allerta dalle ore "
    r"(?P<start_time>(?:[01]\d|2[0-3]):[0-5]\d|24:00) di "
    r"(?P<start_weekday>lunedì|martedì|mercoledì|giovedì|venerdì|sabato|domenica) "
    r"alle ore (?P<end_time>(?:[01]\d|2[0-3]):[0-5]\d|24:00) di "
    r"(?P<end_weekday>lunedì|martedì|mercoledì|giovedì|venerdì|sabato|domenica)$"
)
_AMR_PATH_RE = re.compile(
    r"^/cfd/amr/(?P<year>\d{4})/(?P<date>\d{8})/"
    r"OSMER-avviso_meteo-(?P=date)\.pdf$"
)


class ArpaOsmerRisksParseError(ValueError):
    """The response was reachable but not safely recognizable."""

    def __init__(self, code: str) -> None:
        self.code = str(code or "unrecognized_source")[:80]
        super().__init__(self.code)


class ArpaOsmerRisksUnavailable(RuntimeError):
    """The source could not provide a complete recognized snapshot."""

    def __init__(self, code: str) -> None:
        self.code = str(code or "source_unavailable")[:80]
        super().__init__(self.code)


@dataclass
class _Node:
    tag: str
    attrs: dict[str, str | None]
    parent: "_Node | None" = None
    children: list["_Node | str"] = field(default_factory=list)
    closed: bool = False

    @property
    def classes(self) -> set[str]:
        return set(str(self.attrs.get("class") or "").split())

    def text(self) -> str:
        pieces: list[str] = []

        def collect(node: "_Node") -> None:
            if node.tag in {"script", "style"}:
                return
            for child in node.children:
                if isinstance(child, str):
                    pieces.append(child)
                else:
                    collect(child)

        collect(self)
        return _normalize_text(" ".join(pieces))


class _TreeParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.root = _Node("#document", {}, closed=True)
        self._stack = [self.root]

    def handle_starttag(self, tag, attrs):
        tag_name = str(tag).lower()
        if tag_name == "option" and self._stack[-1].tag == "option":
            self._stack[-1].closed = True
            self._stack.pop()
        node = _Node(
            tag_name,
            {str(key).lower(): value for key, value in attrs},
            parent=self._stack[-1],
        )
        self._stack[-1].children.append(node)
        if tag_name in _VOID_TAGS:
            node.closed = True
        else:
            self._stack.append(node)

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if self._stack[-1].tag == str(tag).lower():
            self._stack[-1].closed = True
            self._stack.pop()

    def handle_endtag(self, tag):
        tag_name = str(tag).lower()
        match_index = next(
            (
                index
                for index in range(len(self._stack) - 1, 0, -1)
                if self._stack[index].tag == tag_name
            ),
            None,
        )
        if match_index is None:
            return
        for node in self._stack[match_index:]:
            node.closed = True
        del self._stack[match_index:]

    def handle_data(self, data):
        self._stack[-1].children.append(data)


def _normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _tree(html: str, error_code: str) -> _Node:
    parser = _TreeParser()
    try:
        parser.feed(str(html or ""))
        parser.close()
    except Exception as error:
        raise ArpaOsmerRisksParseError(error_code) from error
    return parser.root


def _descendants(node: _Node, *, tag: str | None = None) -> Iterable[_Node]:
    for child in node.children:
        if not isinstance(child, _Node):
            continue
        if tag is None or child.tag == tag:
            yield child
        yield from _descendants(child, tag=tag)


def _nearest_panel(node: _Node) -> _Node | None:
    current = node.parent
    while current is not None:
        if current.tag == "div" and "panel" in current.classes:
            return current
        current = current.parent
    return None


def _stable_hash(value: Any) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _canonical_url(
    raw_url: str,
    *,
    base_url: str,
    allowed_hosts: set[str],
    collapse_path_slashes: bool = False,
) -> str:
    absolute = urljoin(base_url, str(raw_url or "").strip())
    try:
        parsed = urlsplit(absolute)
        port = parsed.port
    except ValueError as error:
        raise ArpaOsmerRisksParseError("invalid_source_url") from error
    host = str(parsed.hostname or "").lower()
    if (
        parsed.scheme != "https"
        or host not in allowed_hosts
        or parsed.username is not None
        or parsed.password is not None
        or port not in (None, 443)
    ):
        raise ArpaOsmerRisksParseError("unexpected_source_url")
    path = re.sub(r"/{2,}", "/", parsed.path) if collapse_path_slashes else parsed.path
    netloc = host if port is None else f"{host}:{port}"
    return urlunsplit(("https", netloc, path, parsed.query, ""))


def _single_query(parsed_url: str, *, allowed_keys: set[str]) -> dict[str, str]:
    pairs = parse_qsl(urlsplit(parsed_url).query, keep_blank_values=True)
    if any(key not in allowed_keys for key, _ in pairs):
        raise ArpaOsmerRisksParseError("unexpected_map_query")
    values: dict[str, str] = {}
    for key, value in pairs:
        if key in values:
            raise ArpaOsmerRisksParseError("duplicate_map_query")
        values[key] = value
    return values


def _parse_levels(raw: str, *, expected_count: int) -> list[int | None]:
    tokens = str(raw or "").split(",")
    if len(tokens) != expected_count:
        raise ArpaOsmerRisksParseError("unexpected_zone_count")
    levels: list[int | None] = []
    for token in tokens:
        if token == "-":
            levels.append(None)
        elif token in {"0", "1", "2", "3"}:
            levels.append(int(token))
        else:
            raise ArpaOsmerRisksParseError("unexpected_zone_level")
    return levels


def _parse_pcr(root: _Node, *, page_url: str) -> dict[str, Any]:
    headings = [
        node
        for node in _descendants(root, tag="div")
        if node.attrs.get("id") == "allerta_head"
    ]
    if not headings:
        raise ArpaOsmerRisksParseError("missing_pcr_panel")

    alerts = []
    inactive_count = 0
    for heading in headings:
        panel = _nearest_panel(heading)
        if panel is None or not heading.closed:
            raise ArpaOsmerRisksParseError("incomplete_pcr_panel")
        bodies = [
            node
            for node in _descendants(panel, tag="div")
            if node.attrs.get("id") == "allerta_body"
        ]
        if len(bodies) != 1 or not bodies[0].closed:
            raise ArpaOsmerRisksParseError("incomplete_pcr_panel")
        body = bodies[0]
        images = [
            node
            for node in _descendants(body, tag="img")
            if urlsplit(urljoin(page_url, str(node.attrs.get("src") or ""))).path
            == "/mappa_zone_allerta.php"
        ]
        if len(images) != 1:
            raise ArpaOsmerRisksParseError("missing_pcr_map")
        map_url = _canonical_url(
            str(images[0].attrs.get("src") or ""),
            base_url=page_url,
            allowed_hosts=_METEO_HOSTS,
        )
        query = _single_query(map_url, allowed_keys={"cont", "dim", "z", "ln"})
        if (
            not {"cont", "dim", "z"}.issubset(query)
            or query["cont"] != ""
            or query["dim"] not in PCR_MAP_DIMENSIONS
        ):
            raise ArpaOsmerRisksParseError("unexpected_pcr_map")
        if query.get("ln", "") != "":
            raise ArpaOsmerRisksParseError("unexpected_pcr_map_language")

        links = []
        for anchor in _descendants(body, tag="a"):
            href = str(anchor.attrs.get("href") or "").strip()
            if not href:
                continue
            links.append(
                _canonical_url(
                    href,
                    base_url=page_url,
                    allowed_hosts=_PCR_LINK_HOSTS,
                    collapse_path_slashes=True,
                )
            )
        detail_urls = [url for url in links if not urlsplit(url).path.lower().endswith(".pdf")]
        document_urls = [url for url in links if urlsplit(url).path.lower().endswith(".pdf")]

        headline = heading.text()
        if headline == PCR_INACTIVE_MARKER:
            if query["z"] != "" or document_urls:
                raise ArpaOsmerRisksParseError("inconsistent_pcr_inactive_panel")
            inactive_count += 1
            continue

        match = _PCR_ACTIVE_RE.fullmatch(headline)
        if match is None:
            raise ArpaOsmerRisksParseError("unknown_pcr_marker")
        levels = _parse_levels(query["z"], expected_count=len(PCR_ZONE_NAMES))
        if not any(level is not None and level > 0 for level in levels):
            raise ArpaOsmerRisksParseError("inconsistent_pcr_active_panel")
        alert = {
            "headline": headline,
            "start_time": match.group("start_time"),
            "start_weekday": match.group("start_weekday"),
            "end_time": match.group("end_time"),
            "end_weekday": match.group("end_weekday"),
            "zone_levels": [
                {"zone": zone, "level": level}
                for zone, level in zip(PCR_ZONE_NAMES, levels)
            ],
            "map_url": map_url,
            "detail_url": detail_urls[0] if detail_urls else None,
            "document_urls": sorted(set(document_urls)),
        }
        alert["revision"] = _stable_hash(
            {
                "headline": alert["headline"],
                "zone_levels": alert["zone_levels"],
                "detail_url": alert["detail_url"],
                "document_urls": alert["document_urls"],
            }
        )
        alerts.append(alert)

    if inactive_count and alerts:
        raise ArpaOsmerRisksParseError("mixed_pcr_state")
    if inactive_count:
        if inactive_count != 1:
            raise ArpaOsmerRisksParseError("ambiguous_pcr_inactive_state")
        result = {
            "status": "inactive",
            "explicit": True,
            "marker": PCR_INACTIVE_MARKER,
            "alerts": [],
            "can_confirm_inactive": True,
        }
    elif alerts:
        result = {
            "status": "active",
            "explicit": True,
            "marker": "recognized_active_panel",
            "alerts": alerts,
            "can_confirm_inactive": False,
        }
    else:
        raise ArpaOsmerRisksParseError("unrecognized_pcr_state")
    result["revision"] = _stable_hash(
        {
            "status": result["status"],
            "marker": result["marker"],
            "alerts": [alert["revision"] for alert in result["alerts"]],
        }
    )
    return result


def _parse_bvmr(root: _Node, *, page_url: str) -> dict[str, Any]:
    anchors = [
        node
        for node in _descendants(root, tag="a")
        if node.attrs.get("title") == "Bollettino di vigilanza meteorologica regionale"
    ]
    candidates = []
    for anchor in anchors:
        panel = _nearest_panel(anchor)
        if panel is None:
            continue
        headings = [
            node
            for node in _descendants(panel, tag="div")
            if "panel-heading" in node.classes
            and node.text() == "CFD - Bollettino di vigilanza"
        ]
        images = [
            node
            for node in _descendants(anchor, tag="img")
            if node.attrs.get("alt") == "bvmr"
        ]
        if len(headings) == 1 and len(images) == 1:
            candidates.append((panel, anchor, images[0]))
    if len(candidates) != 1:
        raise ArpaOsmerRisksParseError("missing_or_ambiguous_bvmr_panel")
    panel, anchor, image = candidates[0]

    detail_url = _canonical_url(
        str(anchor.attrs.get("href") or ""),
        base_url=page_url,
        allowed_hosts=_METEO_HOSTS,
    )
    if urlsplit(detail_url).path != "/cfd.php":
        raise ArpaOsmerRisksParseError("unexpected_bvmr_detail_link")
    map_url = _canonical_url(
        str(image.attrs.get("src") or ""),
        base_url=page_url,
        allowed_hosts=_METEO_HOSTS,
    )
    if urlsplit(map_url).path != "/mappa_zone_cfd.php":
        raise ArpaOsmerRisksParseError("unexpected_bvmr_map")
    query = _single_query(map_url, allowed_keys={"cont", "dim", "z", "d", "ln"})
    if (
        set(query) != {"cont", "dim", "z", "d", "ln"}
        or query["cont"] != ""
        or query["dim"] != "346"
        or query["ln"] != ""
    ):
        raise ArpaOsmerRisksParseError("unexpected_bvmr_map")
    levels = _parse_levels(query["z"], expected_count=len(BVMR_ZONE_NAMES))
    try:
        source_date = datetime.strptime(query["d"], "%Y%m%d").date().isoformat()
    except ValueError as error:
        raise ArpaOsmerRisksParseError("invalid_bvmr_source_date") from error
    summaries = [
        node.text()
        for node in _descendants(panel, tag="div")
        if {"text-justify", "sipadd"}.issubset(node.classes) and node.text()
    ]
    if len(summaries) != 1:
        raise ArpaOsmerRisksParseError("missing_or_ambiguous_bvmr_summary")
    result = {
        "status": "present",
        "source_date": source_date,
        "summary": summaries[0],
        "detail_url": detail_url,
        "map_url": map_url,
        "zone_levels": [
            {"zone": zone, "level": level}
            for zone, level in zip(BVMR_ZONE_NAMES, levels)
        ],
    }
    result["revision"] = _stable_hash(
        {
            "source_date": result["source_date"],
            "summary": result["summary"],
            "detail_url": result["detail_url"],
            "zone_levels": result["zone_levels"],
        }
    )
    return result


def _parse_amr_form(root: _Node, *, page_url: str, expected_year: int) -> dict[str, Any]:
    forms = [
        node
        for node in _descendants(root, tag="form")
        if node.attrs.get("id") == "frm_amr" and node.attrs.get("name") == "amr"
    ]
    if len(forms) != 1 or not forms[0].closed:
        raise ArpaOsmerRisksParseError("missing_or_incomplete_amr_form")
    form = forms[0]
    if str(form.attrs.get("method") or "").lower() != "post" or "pdfCont" not in form.classes:
        raise ArpaOsmerRisksParseError("unrecognized_amr_form")
    action_url = _canonical_url(
        str(form.attrs.get("action") or ""),
        base_url=page_url,
        allowed_hosts=_METEO_HOSTS,
    )
    if urlsplit(action_url).path != "/rischi_meteo.php":
        raise ArpaOsmerRisksParseError("unrecognized_amr_form_action")
    selects = [
        node
        for node in _descendants(form, tag="select")
        if node.attrs.get("id") == "anno" and node.attrs.get("name") == "anno"
    ]
    placeholders = [
        node
        for node in _descendants(form, tag="div")
        if node.attrs.get("id") == "arch_amr" and node.attrs.get("name") == "amr"
    ]
    if len(selects) != 1 or len(placeholders) != 1 or placeholders[0].text() != "scegli l'anno":
        raise ArpaOsmerRisksParseError("unrecognized_amr_form_fields")
    years = []
    for option in _descendants(selects[0], tag="option"):
        value = str(option.attrs.get("value") or "")
        if not re.fullmatch(r"\d{4}", value) or option.text() != value:
            raise ArpaOsmerRisksParseError("invalid_amr_archive_year")
        years.append(int(value))
    if not years or len(years) != len(set(years)) or expected_year not in years:
        raise ArpaOsmerRisksParseError("missing_amr_archive_year")
    result = {
        "status": "available",
        "archive_url": ARPA_OSMER_AMR_ARCHIVE_URL,
        "requested_year": expected_year,
        "available_years": sorted(years, reverse=True),
    }
    result["revision"] = _stable_hash(result)
    return result


def parse_osmer_risks_page(
    html: str,
    *,
    page_url: str = ARPA_OSMER_RISKS_URL,
) -> dict[str, Any]:
    """Parse only the recognized Italian risks-page structures."""

    canonical_page_url = _canonical_url(
        page_url,
        base_url=ARPA_OSMER_RISKS_URL,
        allowed_hosts=_METEO_HOSTS,
    )
    if urlsplit(canonical_page_url).path != "/rischi_meteo.php":
        raise ArpaOsmerRisksParseError("unexpected_risks_page_url")
    root = _tree(html, "invalid_risks_page_html")
    pcr = _parse_pcr(root, page_url=canonical_page_url)
    bvmr = _parse_bvmr(root, page_url=canonical_page_url)
    amr_archive = _parse_amr_form(
        root,
        page_url=canonical_page_url,
        expected_year=int(bvmr["source_date"][:4]),
    )
    result = {"pcr": pcr, "bvmr": bvmr, "amr_archive": amr_archive}
    result["revision"] = _stable_hash(
        {
            "pcr": pcr["revision"],
            "bvmr": bvmr["revision"],
            "amr_archive": amr_archive["revision"],
        }
    )
    return result


def parse_osmer_pcr_page(
    html: str,
    *,
    page_url: str = ARPA_OSMER_RISKS_URL,
) -> dict[str, Any]:
    """Parse only PCR, independently from the BVMR and AMR sections."""

    canonical_page_url = _canonical_url(
        page_url,
        base_url=ARPA_OSMER_RISKS_URL,
        allowed_hosts=_METEO_HOSTS,
    )
    if urlsplit(canonical_page_url).path != "/rischi_meteo.php":
        raise ArpaOsmerRisksParseError("unexpected_risks_page_url")
    return _parse_pcr(
        _tree(html, "invalid_risks_page_html"), page_url=canonical_page_url
    )


def _canonical_amr_document(raw_url: str, *, page_url: str, year: int) -> tuple[str, str]:
    document_url = _canonical_url(
        raw_url,
        base_url=page_url,
        allowed_hosts=_METEO_HOSTS,
        collapse_path_slashes=True,
    )
    match = _AMR_PATH_RE.fullmatch(urlsplit(document_url).path)
    if match is None or int(match.group("year")) != year or match.group("date")[:4] != str(year):
        raise ArpaOsmerRisksParseError("unexpected_amr_document")
    try:
        source_date = datetime.strptime(match.group("date"), "%Y%m%d").date().isoformat()
    except ValueError as error:
        raise ArpaOsmerRisksParseError("invalid_amr_source_date") from error
    return document_url, source_date


def parse_osmer_amr_archive(
    payload: str,
    *,
    year: int,
    page_url: str = ARPA_OSMER_RISKS_URL,
) -> dict[str, Any]:
    """Parse the AJAX archive response without treating history as active state."""

    try:
        archive_html = json.loads(str(payload or ""))
    except (TypeError, ValueError) as error:
        raise ArpaOsmerRisksParseError("invalid_amr_archive_json") from error
    if not isinstance(archive_html, str):
        raise ArpaOsmerRisksParseError("invalid_amr_archive_payload")
    if _normalize_text(archive_html) == "file non presente":
        result = {
            "status": "no_emissions_for_year",
            "explicit": True,
            "archive_year": int(year),
            "emissions": [],
            "latest_source_date": None,
            "can_confirm_no_active_amr": False,
        }
        result["revision"] = _stable_hash(result)
        return result

    root = _tree(archive_html, "invalid_amr_archive_html")
    selects = [
        node
        for node in _descendants(root, tag="select")
        if node.attrs.get("id") == "sel_amr" and "files" in node.classes
    ]
    if len(selects) != 1 or not selects[0].closed:
        raise ArpaOsmerRisksParseError("missing_amr_archive_list")
    emissions = []
    selected_urls = []
    seen_urls = set()
    for option in _descendants(selects[0], tag="option"):
        raw_value = str(option.attrs.get("value") or "").strip()
        raw_href = str(option.attrs.get("data-href") or "").strip()
        value_url, source_date = _canonical_amr_document(raw_value, page_url=page_url, year=int(year))
        href_url, href_date = _canonical_amr_document(raw_href, page_url=page_url, year=int(year))
        if value_url != href_url or source_date != href_date or option.text() != source_date.replace("-", ""):
            raise ArpaOsmerRisksParseError("inconsistent_amr_archive_option")
        if value_url in seen_urls:
            raise ArpaOsmerRisksParseError("duplicate_amr_document")
        seen_urls.add(value_url)
        selected = "selected" in option.attrs
        emission = {
            "source_date": source_date,
            "document_url": value_url,
            "selected": selected,
        }
        emission["revision"] = _stable_hash(
            {"source_date": source_date, "document_url": value_url}
        )
        emissions.append(emission)
        if selected:
            selected_urls.append(value_url)
    if not emissions or len(selected_urls) != 1:
        raise ArpaOsmerRisksParseError("invalid_amr_archive_selection")
    emissions.sort(key=lambda item: (item["source_date"], item["document_url"]))
    if selected_urls[0] != emissions[-1]["document_url"]:
        raise ArpaOsmerRisksParseError("stale_amr_archive_selection")
    links = [
        node
        for node in _descendants(root, tag="a")
        if node.attrs.get("id") == "linkpdf_amr"
    ]
    objects = [
        node
        for node in _descendants(root, tag="object")
        if node.attrs.get("id") == "pdf_amr"
    ]
    if len(links) != 1 or len(objects) != 1:
        raise ArpaOsmerRisksParseError("incomplete_amr_archive_preview")
    link_url, _ = _canonical_amr_document(
        str(links[0].attrs.get("href") or ""), page_url=page_url, year=int(year)
    )
    object_url, _ = _canonical_amr_document(
        str(objects[0].attrs.get("data") or ""), page_url=page_url, year=int(year)
    )
    if link_url != selected_urls[0] or object_url != selected_urls[0]:
        raise ArpaOsmerRisksParseError("inconsistent_amr_archive_preview")
    result = {
        "status": "emissions_present",
        "explicit": True,
        "archive_year": int(year),
        "emissions": emissions,
        "latest_source_date": emissions[-1]["source_date"],
        # The endpoint is an archive: even an empty archive is not a statement
        # that no AMR is currently valid.
        "can_confirm_no_active_amr": False,
    }
    result["revision"] = _stable_hash(result)
    return result


def _utc_iso(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat(timespec="seconds")


def _http_datetime(value: str | None) -> str | None:
    if not value:
        return None
    try:
        parsed = parsedate_to_datetime(str(value))
    except (TypeError, ValueError, OverflowError):
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return _utc_iso(parsed)


def source_timing(
    headers: Mapping[str, Any] | None,
    *,
    fetched_at: datetime,
) -> dict[str, Any]:
    """Expose response timing while keeping acquisition time non-authoritative."""

    normalized = {str(key).lower(): str(value) for key, value in (headers or {}).items()}
    http_date = _http_datetime(normalized.get("date"))
    last_modified = _http_datetime(normalized.get("last-modified"))
    try:
        age_seconds = max(0, int(normalized["age"])) if "age" in normalized else None
    except ValueError:
        age_seconds = None
    max_age_match = re.search(
        r"(?:^|,)\s*max-age\s*=\s*(\d+)\b",
        normalized.get("cache-control", ""),
        re.I,
    )
    cache_max_age_seconds = int(max_age_match.group(1)) if max_age_match else None
    source_observed_at = http_date or last_modified
    return {
        "fetched_at": _utc_iso(fetched_at),
        "http_date": http_date,
        "last_modified": last_modified,
        "age_seconds": age_seconds,
        "cache_max_age_seconds": cache_max_age_seconds,
        "source_observed_at": source_observed_at,
        "source_timestamp_kind": (
            "http_date" if http_date else "last_modified" if last_modified else None
        ),
        "comparable_to_external_events": source_observed_at is not None,
    }


def parse_osmer_risks_snapshot(
    html: str,
    amr_archive_payload: str,
    *,
    response_headers: Mapping[str, Any] | None = None,
    amr_response_headers: Mapping[str, Any] | None = None,
    fetched_at: datetime | None = None,
    page_url: str = ARPA_OSMER_RISKS_URL,
) -> dict[str, Any]:
    page = parse_osmer_risks_page(html, page_url=page_url)
    amr = parse_osmer_amr_archive(
        amr_archive_payload,
        year=page["amr_archive"]["requested_year"],
        page_url=page_url,
    )
    acquired_at = fetched_at or datetime.now(timezone.utc)
    page_timing = source_timing(response_headers, fetched_at=acquired_at)
    result = {
        "status": "available",
        "source": {
            "id": "arpa_osmer_risks_page",
            "name": "ARPA FVG OSMER · Rischi meteorologici",
            "url": page_url,
        },
        "source_mode": "raw_official_page",
        "source_timing": page_timing,
        "amr_source_timing": source_timing(
            amr_response_headers, fetched_at=acquired_at
        ),
        "pcr": page["pcr"],
        "bvmr": page["bvmr"],
        "amr": amr,
        # This means only that the page carried the exact recognized marker.
        # Temporal reconciliation with Telegram belongs to the consumer.
        "can_confirm_pcr_inactive": page["pcr"]["can_confirm_inactive"],
    }
    result["revision"] = _stable_hash(
        {
            "pcr": page["pcr"]["revision"],
            "bvmr": page["bvmr"]["revision"],
            "amr": amr["revision"],
        }
    )
    return result


class ArpaOsmerRisksSource:
    """Fetch the page and its AMR archive without changing application state."""

    def __init__(
        self,
        *,
        session: requests.Session | Any | None = None,
        timeout_seconds: float = 8.0,
        now: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    ) -> None:
        self._session = session or requests.Session()
        self._timeout_seconds = max(1.0, min(float(timeout_seconds), 20.0))
        self._now = now

    def _get(self, url: str, *, params: Mapping[str, str] | None = None):
        try:
            response = self._session.get(
                url,
                params=params,
                headers={
                    "User-Agent": ARPA_OSMER_USER_AGENT,
                    "Accept": "application/json,text/html,application/xhtml+xml",
                    "Accept-Language": "it-IT,it;q=0.9",
                },
                timeout=self._timeout_seconds,
            )
            response.raise_for_status()
            return response
        except requests.Timeout as error:
            raise ArpaOsmerRisksUnavailable("source_timeout") from error
        except requests.RequestException as error:
            raise ArpaOsmerRisksUnavailable("source_request_failed") from error

    def fetch(self) -> dict[str, Any]:
        page_response = self._get(ARPA_OSMER_RISKS_URL)
        try:
            page = parse_osmer_risks_page(page_response.text)
        except ArpaOsmerRisksParseError as error:
            raise ArpaOsmerRisksUnavailable("source_page_unrecognized") from error
        year = page["amr_archive"]["requested_year"]
        archive_response = self._get(
            ARPA_OSMER_AMR_ARCHIVE_URL,
            params={"l": "", "ln": "", "a": str(year), "m": "", "t": "amr"},
        )
        try:
            return parse_osmer_risks_snapshot(
                page_response.text,
                archive_response.text,
                response_headers=page_response.headers,
                amr_response_headers=archive_response.headers,
                fetched_at=self._now(),
            )
        except ArpaOsmerRisksParseError as error:
            raise ArpaOsmerRisksUnavailable("source_archive_unrecognized") from error

    def fetch_pcr(self) -> dict[str, Any]:
        """Fetch PCR alone so unrelated ARPA sections cannot block alerts."""

        page_response = self._get(ARPA_OSMER_RISKS_URL)
        try:
            pcr = parse_osmer_pcr_page(page_response.text)
        except ArpaOsmerRisksParseError as error:
            raise ArpaOsmerRisksUnavailable("source_pcr_unrecognized") from error
        acquired_at = self._now()
        timing = source_timing(page_response.headers, fetched_at=acquired_at)
        return {
            "status": "available",
            "source": {
                "id": "arpa_osmer_risks_page",
                "name": "ARPA FVG OSMER · Rischi meteorologici",
                "url": ARPA_OSMER_RISKS_URL,
            },
            "source_mode": "raw_official_page",
            "source_timing": timing,
            "pcr": pcr,
            "can_confirm_pcr_inactive": pcr["can_confirm_inactive"],
            "revision": pcr["revision"],
        }


__all__ = [
    "ARPA_OSMER_AMR_ARCHIVE_URL",
    "ARPA_OSMER_RISKS_URL",
    "ArpaOsmerRisksParseError",
    "ArpaOsmerRisksSource",
    "ArpaOsmerRisksUnavailable",
    "parse_osmer_amr_archive",
    "parse_osmer_pcr_page",
    "parse_osmer_risks_page",
    "parse_osmer_risks_snapshot",
    "source_timing",
]
