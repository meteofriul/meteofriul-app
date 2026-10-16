"""Paesi in Festa pilot reader with cross-checked public discovery surfaces."""

from dataclasses import dataclass, field
from datetime import date, datetime
from html.parser import HTMLParser
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo
from xml.etree import ElementTree
import json
import re

import requests

from . import engine
from .pilot_excerpt import attributed_excerpt, extract_meta_excerpt
from .pilot_schedule import schedule_notice


SOURCE = "Paesi in Festa"
BASE = "https://paesiinfesta.com"
LISTS = {
    "sagre": BASE + "/sagre-in-friuli-venezia-giulia-e-veneto-orientale/",
    "rievocazioni": BASE + "/rievocazioni-storiche/",
}
SURFACES = {
    "home": BASE + "/",
    "fvg": BASE + "/friuli-venezia-giulia/",
    "udine": BASE + "/friuli-venezia-giulia/udine/",
    "pordenone": BASE + "/friuli-venezia-giulia/pordenone/",
    "archive": BASE + "/archivio/",
}
SITEMAP_INDEX = BASE + "/sitemap_index.xml"
# The public post sitemap was checked on 2026-10-06: all unlisted FVG/root
# posts were past events or undated video/editorial pages. Inspect later edits.
SITEMAP_AUDIT_BASELINE = datetime.fromisoformat("2026-10-06T00:00:00+00:00")
ROUNDUPS = {
    BASE + "/appuntamenti-con-i-presepi/": "presepi",
    BASE + "/carnevale-in-piazza/": "carnevale",
}
# Aliases are locality-to-municipality facts, not inferred from event titles.
# Versutta: https://www.comune.casarsadelladelizia.pn.it/it/turismo-54328/i-luoghi-di-pasolini-90398
# Castelmonte: https://www.turismofvg.it/santuario-della-madonna-di-castelmonte
PLACE_ALIASES = {
    "versutta di san giovanni di casarsa": "Casarsa della Delizia",
    "castelmonte": "Prepotto",
    "maniagolibero": "Maniago",
    "cornino": "Forgaria nel Friuli",
    "prodolone": "San Vito al Tagliamento",
}
MONTHS = {name: index for index, name in enumerate((
    "gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno",
    "luglio", "agosto", "settembre", "ottobre", "novembre", "dicembre"), 1)}
MONTH_RE = "(?:" + "|".join(MONTHS) + ")"
FULL_DATE = re.compile(rf"\b(\d{{1,2}})\s+({MONTH_RE})\s+(20\d{{2}})\b", re.I)
NUMERIC_DATE = re.compile(r"^(dal|al)\s+(\d{1,2})/(\d{1,2})/(20\d{2})$", re.I)
VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input",
        "link", "meta", "param", "source", "track", "wbr"}


def clean(value):
    return " ".join(str(value or "").split())


@dataclass
class Node:
    tag: str
    attrs: dict = field(default_factory=dict)
    children: list = field(default_factory=list)

    def has_class(self, name):
        return name in self.attrs.get("class", "").split()

    def walk(self):
        yield self
        for child in self.children:
            if isinstance(child, Node):
                yield from child.walk()

    def text(self):
        return clean("".join(" " if isinstance(child, Node) and child.tag == "br" else
                             child.text() if isinstance(child, Node) else child
                             for child in self.children))


class Tree(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = Node("document")
        self.stack = [self.root]

    def handle_starttag(self, tag, attrs):
        node = Node(tag, dict(attrs))
        self.stack[-1].children.append(node)
        if tag not in VOID:
            self.stack.append(node)

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in VOID:
            self.handle_endtag(tag)

    def handle_endtag(self, tag):
        for index in range(len(self.stack) - 1, 0, -1):
            if self.stack[index].tag == tag:
                del self.stack[index:]
                return

    def handle_data(self, data):
        self.stack[-1].children.append(data)


def tree(html):
    parser = Tree()
    parser.feed(html)
    return parser.root


def first(node, predicate):
    return next((item for item in node.walk() if predicate(item)), None)


def trusted_url(url):
    parsed = urlsplit(url or "")
    return parsed.scheme == "https" and parsed.hostname == "paesiinfesta.com" and not parsed.query


def listing_range(value):
    """Read Italian list-card dates, including abbreviated first dates."""
    normalized = clean(value).casefold().replace("’", "'").replace("`", "'")
    normalized = normalized.replace("–", "-").replace("—", "-")
    normalized = re.sub(r"\bdall?'", "dal ", normalized)
    normalized = re.sub(r"\ball'", "al ", normalized)
    full = list(FULL_DATE.finditer(normalized))
    if not full:
        raise ValueError("listing date missing")
    end_match = full[-1]
    end = date(int(end_match[3]), MONTHS[end_match[2]], int(end_match[1]))
    if len(full) > 1:
        start_match = full[0]
        start = date(int(start_match[3]), MONTHS[start_match[2]], int(start_match[1]))
    else:
        prefix = normalized[:end_match.start()]
        month_start = re.search(rf"\b(\d{{1,2}})\s+({MONTH_RE})\s+al\s*$", prefix)
        day_start = re.search(r"\bdal\s+(\d{1,2})\s+al\s*$", prefix)
        sequence = re.search(r"\b(\d{1,2}(?:\s*-\s*\d{1,2})*)\s*-\s*$", prefix)
        if month_start:
            month = MONTHS[month_start[2]]
            year = end.year - (month > end.month)
            start = date(year, month, int(month_start[1]))
        elif day_start:
            start = date(end.year, end.month, int(day_start[1]))
        elif sequence:
            start = date(end.year, end.month, int(re.findall(r"\d{1,2}", sequence[1])[0]))
        else:
            start = end
    if start > end:
        raise ValueError("listing date inverted")
    return start, end


def listing_cards(html, *, kind):
    root = tree(html)
    main = first(root, lambda item: item.tag == "main" and item.attrs.get("id") == "content")
    if main is None:
        raise ValueError("Paesi in Festa list main missing")
    cards, seen = [], {}
    for node in main.walk():
        if not node.has_class("e-loop-item"):
            continue
        heading = first(node, lambda item: item.tag == "h2")
        anchor = first(heading, lambda item: item.tag == "a") if heading else None
        if anchor is None:
            if any(name.startswith("category-") for name in node.attrs.get("class", "").split()):
                raise ValueError("Paesi in Festa event card lost its title link")
            continue
        url = anchor.attrs.get("href", "")
        if not trusted_url(url):
            raise ValueError("unexpected Paesi in Festa card URL")
        widgets = [item.text() for item in node.walk()
                   if item.has_class("elementor-widget-text-editor")]
        if len(widgets) < 2:
            raise ValueError("Paesi in Festa card fields changed")
        region = ("fvg" if node.has_class("regione-friuli-venezia-giulia") else
                  "veneto" if node.has_class("regione-veneto") else "mixed")
        if kind == "rievocazioni" and region != "fvg":
            raise ValueError("unexpected reenactment region")
        card = {"url": url, "kind": kind, "locality": heading.text(),
                "label": widgets[0], "date_text": widgets[1], "region": region}
        if url in seen:
            if seen[url] != card:
                raise ValueError("same URL has inconsistent list cards")
            continue
        seen[url] = card
        cards.append(card)
    if any(node.tag == "a" and (
            "page-numbers" in node.attrs.get("class", "").split()
            or re.search(r"/page/\d+/?$", node.attrs.get("href", "")))
            for node in main.walk()):
        raise ValueError("Paesi in Festa listing pagination requires inspection")
    if not cards or len(cards) > 200:
        raise ValueError("Paesi in Festa list empty or excessive")
    return cards


def surface_cards(html, *, surface, today, quarantine=None):
    """Find still-active FVG posts outside the two primary lists."""
    root = tree(html)
    cards, examined = {}, 0
    for node in root.walk():
        if not node.has_class("e-loop-item") or not node.has_class("type-post"):
            continue
        heading = first(node, lambda item: item.tag == "h2")
        anchor = first(heading, lambda item: item.tag == "a") if heading else None
        url = anchor.attrs.get("href", "") if anchor else ""
        fvg_path = urlsplit(url).path.startswith("/friuli-venezia-giulia/")
        if not fvg_path and not node.has_class("regione-friuli-venezia-giulia"):
            continue
        examined += 1
        if not node.has_class("regione-friuli-venezia-giulia"):
            raise ValueError("Paesi in Festa FVG region tag missing: " + url)
        widgets = [item.text() for item in node.walk()
                   if item.has_class("elementor-widget-text-editor")]
        if anchor is None or len(widgets) < 2:
            raise ValueError("Paesi in Festa cross-check card changed: " + surface)
        if not trusted_url(url):
            raise ValueError("Paesi in Festa cross-check URL changed: " + surface)
        start, end = listing_range(widgets[1])
        if end < today:
            continue
        # The archive tag can be applied on the final scheduled day. Dates
        # still include that day; only a future end date is contradictory.
        archived_future = node.has_class("category-eventi-passati") and end > today
        kind = ("rievocazioni" if node.has_class("category-rievocazione-storica")
                else "sagre" if node.has_class("category-sagra") else None)
        if kind is None:
            raise ValueError("Paesi in Festa active card category unknown: " + url)
        card = {"url": url, "kind": kind, "locality": heading.text(),
                "label": widgets[0], "date_text": widgets[1], "region": "fvg"}
        if archived_future:
            if quarantine is None:
                raise ValueError("Paesi in Festa active card marked archived: " + url)
            quarantine[url] = {"url": url, "reason": "future_card_marked_archived"}
        prior = cards.setdefault(url, card)
        if (listing_range(prior["date_text"]) != (start, end)
                or clean(prior["label"]).casefold() != clean(card["label"]).casefold()
                or clean(prior["locality"]).casefold() != clean(card["locality"]).casefold()
                or prior["kind"] != kind):
            raise ValueError("Paesi in Festa cross-check card conflict: " + url)
    if examined == 0:
        raise ValueError("Paesi in Festa cross-check empty: " + surface)
    return list(cards.values()), examined


def numeric_date(value, expected_prefix):
    match = NUMERIC_DATE.fullmatch(clean(value))
    if not match or match[1].casefold() != expected_prefix:
        raise ValueError("detail date label missing")
    return date(int(match[4]), int(match[3]), int(match[2]))


def event_schema(root):
    events = []
    for script in root.walk():
        if script.tag != "script" or script.attrs.get("type") != "application/ld+json":
            continue
        try:
            payload = json.loads("".join(child for child in script.children if isinstance(child, str)))
        except (TypeError, ValueError):
            continue
        nodes = payload if isinstance(payload, list) else [payload]
        for item in nodes:
            if not isinstance(item, dict):
                continue
            candidates = [item] + (item.get("@graph") if isinstance(item.get("@graph"), list) else [])
            events.extend(candidate for candidate in candidates if isinstance(candidate, dict)
                          and (candidate.get("@type") == "Event" or
                               isinstance(candidate.get("@type"), list)
                               and "Event" in candidate["@type"]))
    return events


def municipality(locality, schema_description=""):
    catalog = engine.fvg_municipality_catalog
    alias_key = engine.normalize_for_search(locality).split(" (", 1)[0]
    for place, town_name in PLACE_ALIASES.items():
        if alias_key.startswith(place):
            return catalog.match_names(town_name)
    exact = catalog.match_names(locality)
    if exact:
        return exact
    for evidence in (locality,):
        normalized = engine.normalize_for_search(evidence)
        matches = [candidate for candidate in catalog.municipalities
                   if re.search(r"(?<!\w)" + re.escape(engine.normalize_for_search(candidate.name))
                                + r"(?!\w)", normalized)]
        if matches:
            return max(matches, key=lambda item: len(item.name))
    # Some detail pages name only a hamlet. The Event metadata explicitly
    # labels its municipality; arbitrary names elsewhere in the prose do not.
    match = re.search(r"\bComune\s+di\s+([^,.;|]+)", schema_description, re.I)
    if match:
        named_place = engine.normalize_for_search(match[1])
        candidates = [candidate for candidate in catalog.municipalities
                      if re.match(re.escape(engine.normalize_for_search(candidate.name))
                                  + r"(?!\w)", named_place)]
        return max(candidates, key=lambda item: len(item.name)) if candidates else None
    return None


def detail_event(html, card, *, today):
    root = tree(html)
    url = card["url"]
    headings = [item for item in root.walk() if item.tag in {"h1", "h2", "h3"}]
    h1 = next((item for item in headings if item.tag == "h1"), None)
    if h1 is None:
        raise ValueError("detail event heading missing: " + url)
    if card["kind"] == "sagre":
        title_node = next((item for item in headings if item.tag == "h2"
                           and item.text().casefold() != "prossimi appuntamenti"), None)
        title = title_node.text() if title_node else ""
    else:
        title = h1.text()
    if not title or not card["locality"]:
        raise ValueError("detail event identity missing: " + url)
    if clean(title).casefold().replace("–", "-").replace("’", "'") != \
            clean(card["label"]).casefold().replace("–", "-").replace("’", "'"):
        raise ValueError("listing/detail title conflict: " + url)
    widgets = [item for item in root.walk() if item.has_class("elementor-widget-text-editor")]
    starts = [item for item in widgets if NUMERIC_DATE.fullmatch(item.text())
              and item.text().casefold().startswith("dal ")]
    ends = [item for item in widgets if NUMERIC_DATE.fullmatch(item.text())
            and item.text().casefold().startswith("al ")]
    if len(starts) != 1 or len(ends) != 1:
        raise ValueError("detail has ambiguous date labels: " + url)
    start, end = numeric_date(starts[0].text(), "dal"), numeric_date(ends[0].text(), "al")
    listed_start, listed_end = listing_range(card["date_text"])
    if (start, end) != (listed_start, listed_end):
        raise ValueError("listing/detail date conflict: " + url)
    schemas = event_schema(root)
    if card["kind"] == "sagre" and len(schemas) != 1:
        raise ValueError("sagra Event metadata missing or ambiguous: " + url)
    if schemas:
        if len(schemas) != 1 or (schemas[0].get("startDate"), schemas[0].get("endDate")) != \
                (start.isoformat(), end.isoformat()):
            raise ValueError("visible/structured date conflict: " + url)
    if end < today:
        return None
    schema_description = schemas[0].get("description", "") if schemas else ""
    town = municipality(card["locality"], schema_description)
    if town is None:
        raise ValueError("detail municipality unresolved: " + url)
    event = {"source": SOURCE, "url": url, "title": title, "start_date": start.isoformat(),
             "end_date": end.isoformat(), "event_city": town.name, "place": card["locality"],
             "lat": town.latitude, "lon": town.longitude,
             "location_confidence": "municipality", "is_real": True,
             "date_evidence_kind": "event_schedule",
             "date_evidence": starts[0].text() + " " + ends[0].text()}
    if card["kind"] == "rievocazioni":
        end_index = widgets.index(ends[0])
        for widget in widgets[end_index + 1:]:
            prose = clean("".join(child.text() if isinstance(child, Node) else child
                                  for child in widget.children if not isinstance(child, Node)
                                  or child.tag not in {"h3", "h4"}))
            if len(prose) >= 30:
                event.update(attributed_excerpt(prose, source_name=SOURCE,
                                                source_url=url, title=title))
                break
    else:
        # The first list widget is the event title. A distinct phrase in the
        # second widget can be used as a short source-attributed preview.
        extra = re.split(r"\b(?:dal|dall['’])\s+\d", card["date_text"], maxsplit=1, flags=re.I)[0]
        if clean(extra):
            event.update(attributed_excerpt(extra, source_name=SOURCE,
                                            source_url=url, title=title))
    return event


def sitemap_detail_event(html, url, *, today):
    """Read an unlisted post from its own dated, localised programme."""
    root = tree(html)
    headings = [node for node in root.walk() if node.tag in {"h1", "h2", "h3", "h4"}]
    h1 = next((node for node in headings if node.tag == "h1"), None)
    if h1 is None:
        raise ValueError("sitemap detail heading missing")
    position = headings.index(h1)
    h1_text = h1.text()
    sagra = bool(re.match(r"^Sagra\s+di\s+", h1_text, re.I))
    if sagra:
        locality = re.sub(r"^Sagra\s+di\s+", "", h1_text, flags=re.I).strip()
        title_node = next((node for node in headings[position + 1:]
                           if node.tag == "h2"), None)
        title = title_node.text() if title_node else ""
    else:
        locality_node = next((node for node in reversed(headings[:position])
                              if node.tag == "h2"), None)
        locality = locality_node.text() if locality_node else ""
        title = h1_text
    if not locality or not title or title.casefold() == "prossimi appuntamenti":
        raise ValueError("sitemap detail title or locality missing")
    programme = next((index for index, node in enumerate(headings[position + 1:], position + 1)
                      if node.text().strip().casefold() == "programma"), None)
    footer = next((index for index, node in enumerate(headings[position + 1:], position + 1)
                   if node.text().strip().casefold() == "prossimi appuntamenti"), len(headings))
    if programme is None or programme >= footer:
        raise ValueError("sitemap detail programme missing")
    widgets = [node for node in root.walk() if node.has_class("elementor-widget-text-editor")]
    starts = [node for node in widgets if NUMERIC_DATE.fullmatch(node.text())
              and node.text().casefold().startswith("dal ")]
    ends = [node for node in widgets if NUMERIC_DATE.fullmatch(node.text())
            and node.text().casefold().startswith("al ")]
    if len(starts) != 1 or len(ends) != 1:
        raise ValueError("sitemap detail dates missing or ambiguous")
    start, end = numeric_date(starts[0].text(), "dal"), numeric_date(ends[0].text(), "al")
    if start > end:
        raise ValueError("sitemap detail dates inverted")
    if end < today:
        return None
    title_years = {int(value) for value in re.findall(r"(?<!\d)20\d{2}(?!\d)", title)}
    if title_years and not title_years.issubset({start.year, end.year}):
        raise ValueError("sitemap detail title/date year conflict")
    schemas = event_schema(root)
    if (sagra and len(schemas) != 1) or len(schemas) > 1:
        raise ValueError("sitemap detail Event metadata missing or ambiguous")
    schema = schemas[0] if schemas else {}
    if schema:
        if (schema.get("startDate"), schema.get("endDate")) != \
                (start.isoformat(), end.isoformat()):
            raise ValueError("sitemap visible/structured dates conflict")
        if schema.get("url") and schema["url"] != url:
            raise ValueError("sitemap Event URL conflict")
        if schema.get("eventStatus") and not str(schema["eventStatus"]).endswith("/EventScheduled"):
            raise ValueError("sitemap Event status requires review")
        named = clean(schema.get("name"))
        if sagra and named and engine.normalize_for_search(named) != \
                engine.normalize_for_search(locality):
            raise ValueError("sitemap visible/structured locality conflict")
    description = clean(schema.get("description"))
    town = municipality(locality, description)
    schema_town = municipality("", description) if description else None
    if town is None or schema_town and schema_town.name != town.name:
        raise ValueError("sitemap detail municipality unresolved or conflicting")
    path = urlsplit(url).path
    province_path = re.match(r"^/friuli-venezia-giulia/(pordenone|udine|gorizia|trieste)/", path)
    province_codes = {"pordenone": "PN", "udine": "UD", "gorizia": "GO", "trieste": "TS"}
    if province_path and town.province != province_codes[province_path[1]]:
        raise ValueError("sitemap detail URL/province conflict")
    location = schema.get("location") if isinstance(schema.get("location"), dict) else {}
    location_name = clean(location.get("name"))
    if location_name:
        location_town = municipality(location_name, description)
        if location_town is None or location_town.name != town.name:
            raise ValueError("sitemap Event location/municipality conflict")
    address = location.get("address") if isinstance(location.get("address"), dict) else {}
    country = clean(address.get("addressCountry")).casefold()
    if country and country not in {"it", "italia", "italy"}:
        raise ValueError("sitemap Event country outside Italy")
    intro = next((node.text() for node in widgets[widgets.index(ends[0]) + 1:]
                  if len(node.text()) >= 30 and node.text().casefold() != "contenuti sponsorizzati"), "")
    if schedule_notice(title, intro[:500]):
        raise ValueError("sitemap detail schedule change requires review")
    event = {"source": SOURCE, "url": url, "title": title,
             "start_date": start.isoformat(), "end_date": end.isoformat(),
             "event_city": town.name, "place": locality,
             "lat": town.latitude, "lon": town.longitude,
             "location_confidence": "municipality", "is_real": True,
             "date_evidence_kind": "event_schedule",
             "date_evidence": starts[0].text() + " " + ends[0].text(),
             "discovery_kind": "sitemap"}
    preview = (extract_meta_excerpt(html, title=title) if sagra else intro)
    if preview:
        event.update(attributed_excerpt(preview, source_name=SOURCE,
                                        source_url=url, title=title))
    return event


def presepi_events(html, card, *, today):
    """A roundup entry is one dated place, never the stale parent header."""
    root = tree(html)
    programme = next((node for node in root.walk()
                      if node.has_class("elementor-widget-text-editor")
                      and sum(isinstance(child, Node) and child.tag == "h4"
                              for child in node.children) >= 5), None)
    if programme is None:
        raise ValueError("Presepi programme structure changed")
    groups = []
    current = None
    for child in programme.children:
        if not isinstance(child, Node):
            continue
        if child.tag == "h4":
            current = {"heading": child.text(), "paragraphs": []}
            groups.append(current)
        elif current is not None and child.tag == "p":
            current["paragraphs"].append(child.text())
    if not 5 <= len(groups) <= 40:
        raise ValueError("Presepi group count changed")
    events, excluded, ranges = [], [], []
    for group in groups:
        heading = group["heading"]
        match = re.search(r"\b(?:dal\s|dall[’']|dicembre\s)", heading, re.I)
        if match is None:
            raise ValueError("Presepi group has no date or period")
        place = clean(heading[:match.start()]).strip(" -–")
        if not place:
            raise ValueError("Presepi group place missing")
        if "(VE)" in place.upper() or "(TV)" in place.upper():
            excluded.append({"place": place, "reason": "outside_fvg"})
            continue
        try:
            start, end = listing_range(heading[match.start():])
        except ValueError:
            # A month-only period cannot be turned into exact calendar dates.
            if re.search(r"\bdicembre\s+20\d{2}\s*[-–]\s*gennaio\s+20\d{2}",
                         heading, re.I):
                excluded.append({"place": place, "reason": "month_only_period"})
                continue
            raise
        ranges.append((start, end))
        if end < today:
            continue
        town = municipality(place)
        if town is None:
            raise ValueError("Presepi municipality unresolved: " + place)
        first_paragraph = next((value for value in group["paragraphs"]
                                if value and not re.match(r"^(?:info:|www\.)", value, re.I)), "")
        title = "Appuntamenti con i Presepi — " + re.sub(r"\s*\([^)]*\)", "", place).strip()
        event = {"source": SOURCE, "url": card["url"], "title": title,
                 "start_date": start.isoformat(), "end_date": end.isoformat(),
                 "event_city": town.name, "place": place, "lat": town.latitude,
                 "lon": town.longitude, "location_confidence": "municipality",
                 "is_real": True, "date_evidence_kind": "event_schedule",
                 "date_evidence": heading[match.start():]}
        event.update(attributed_excerpt(first_paragraph, source_name=SOURCE,
                                        source_url=card["url"], title=title))
        events.append(event)
    if not ranges:
        raise ValueError("Presepi has no precisely dated FVG group")
    listed_start, listed_end = listing_range(card["date_text"])
    if (min(start for start, _ in ranges), max(end for _, end in ranges)) != \
            (listed_start, listed_end):
        raise ValueError("Presepi list/programme date conflict")
    return events, excluded


def carnevale_exclusion(html):
    """The site calls this cross-town schedule provisional at present."""
    root = tree(html)
    main_text = clean(" ".join(node.text() for node in root.walk()
                               if node.tag == "h1" or node.tag == "h2"))
    body = clean(root.text())
    if "SFILATE CON I CARRI ALLEGORICI" not in main_text.upper():
        raise ValueError("Carnevale roundup identity changed")
    if not re.search(r"calendario\s+pregresso\s+2026", body, re.I):
        raise ValueError("Carnevale provisional notice changed; inspect individual dates")


def fetch_html(get, url):
    if not trusted_url(url):
        raise ValueError("Paesi in Festa URL outside source")
    with get(url, timeout=(4, 12), allow_redirects=False, stream=True) as response:
        response.raise_for_status()
        if response.status_code != 200 or urlsplit(response.url).hostname != "paesiinfesta.com":
            raise ValueError("unexpected source response")
        chunks, size = [], 0
        for chunk in response.iter_content(65536):
            size += len(chunk)
            if size > 4 * 1024 * 1024:
                raise ValueError("Paesi in Festa page too large")
            chunks.append(chunk)
        return b"".join(chunks).decode("utf-8-sig")


def _xml_children(node, name):
    return [child for child in node if child.tag.rsplit("}", 1)[-1] == name]


def _xml_text(node, name):
    children = _xml_children(node, name)
    return clean(children[0].text) if len(children) == 1 else ""


def sitemap_delta(get, known_urls, *, today):
    """Read eligible new sitemap events after the verified historical audit."""
    index = ElementTree.fromstring(fetch_html(get, SITEMAP_INDEX))
    if index.tag.rsplit("}", 1)[-1] != "sitemapindex":
        raise ValueError("Paesi in Festa sitemap index changed")
    sitemap_urls = [_xml_text(node, "loc") for node in _xml_children(index, "sitemap")]
    post_maps = [url for url in sitemap_urls
                 if re.fullmatch(re.escape(BASE) + r"/post-sitemap\d+\.xml", url)]
    if not 1 <= len(post_maps) <= 10 or len(post_maps) != len(set(post_maps)):
        raise ValueError("Paesi in Festa post sitemap set changed")
    rows = {}
    for sitemap_url in post_maps:
        root = ElementTree.fromstring(fetch_html(get, sitemap_url))
        if root.tag.rsplit("}", 1)[-1] != "urlset":
            raise ValueError("Paesi in Festa post sitemap schema changed")
        for node in _xml_children(root, "url"):
            url, lastmod = _xml_text(node, "loc"), _xml_text(node, "lastmod")
            if not trusted_url(url) or url in rows:
                raise ValueError("Paesi in Festa sitemap post identity changed")
            try:
                modified = datetime.fromisoformat(lastmod.replace("Z", "+00:00"))
            except ValueError:
                raise ValueError("Paesi in Festa sitemap modification date missing") from None
            if modified.tzinfo is None:
                raise ValueError("Paesi in Festa sitemap modification timezone missing")
            rows[url] = modified
    if not 1 <= len(rows) <= 2000:
        raise ValueError("Paesi in Festa sitemap post count changed")
    scoped = {url: modified for url, modified in rows.items()
              if urlsplit(url).path.startswith("/friuli-venezia-giulia/")
              or urlsplit(url).path.count("/") == 2}
    unknown_paths = [url for url, modified in rows.items()
                     if modified > SITEMAP_AUDIT_BASELINE and url not in scoped
                     and not urlsplit(url).path.startswith("/veneto/")]
    changed = {url: modified for url, modified in scoped.items()
               if modified > SITEMAP_AUDIT_BASELINE and url not in known_urls}
    events = []
    review = [{"url": url, "reason": "new sitemap post path needs classification"}
              for url in unknown_paths]
    if len(changed) > 8:
        review.append({"url": SITEMAP_INDEX,
                       "reason": "Paesi in Festa sitemap delta exceeds daily detail budget"})
    else:
        for url in changed:
            try:
                html = fetch_html(get, url)
                root = tree(html)
                widgets = [node.text() for node in root.walk()
                           if node.has_class("elementor-widget-text-editor")]
                starts = [value for value in widgets if NUMERIC_DATE.fullmatch(value)
                          and value.casefold().startswith("dal ")]
                ends = [value for value in widgets if NUMERIC_DATE.fullmatch(value)
                        and value.casefold().startswith("al ")]
                if len(starts) != 1 or len(ends) != 1:
                    raise ValueError("new sitemap post has no unambiguous dates")
                start, end = numeric_date(starts[0], "dal"), numeric_date(ends[0], "al")
                if start > end:
                    raise ValueError("new sitemap post has inverted dates")
                if end >= today:
                    event = sitemap_detail_event(html, url, today=today)
                    identity = (event["start_date"], event["end_date"],
                                engine.normalize_for_search(event["place"]))
                    for card in known_urls.values():
                        if (*map(str, listing_range(card["date_text"])),
                                engine.normalize_for_search(card["locality"])) == identity:
                            raise ValueError("sitemap event overlaps listed event at same place")
                    if any((prior["start_date"], prior["end_date"],
                            engine.normalize_for_search(prior["place"])) == identity
                           for prior in events):
                        raise ValueError("sitemap events overlap at same place")
                    events.append(event)
            except (ValueError, requests.RequestException) as exc:
                review.append({"url": url, "reason": str(exc)})
    return {"baseline": SITEMAP_AUDIT_BASELINE.isoformat(),
            "post_maps_read": len(post_maps), "posts_seen": len(rows),
            "posts_in_scope": len(scoped), "changed_unlisted": len(changed),
            "unknown_paths": len(unknown_paths),
            "changed_checked": 0 if len(changed) > 8 else len(changed),
            "active_added": len(events), "review_count": len(review)}, events, review


def collect_paesiinfesta(*, get=requests.get, today=None):
    today = today or datetime.now(ZoneInfo("Europe/Rome")).date()
    cards, list_counts = [], {}
    for kind, url in LISTS.items():
        found = listing_cards(fetch_html(get, url), kind=kind)
        list_counts[kind] = len(found)
        cards.extend(found)
    by_url = {}
    for card in cards:
        previous = by_url.setdefault(card["url"], card)
        if previous != card:
            raise ValueError("same detail occurs with conflicting category")
    surface_counts, surface_active_urls, extra_active_urls = {}, set(), set()
    quarantined = {}
    for name, url in SURFACES.items():
        found, examined = surface_cards(fetch_html(get, url), surface=name,
                                        today=today, quarantine=quarantined)
        surface_counts[name] = {"fvg_cards_examined": examined,
                                "active_fvg_urls": len(found)}
        for card in found:
            surface_active_urls.add(card["url"])
            previous = by_url.setdefault(card["url"], card)
            if previous is card:
                extra_active_urls.add(card["url"])
            elif (listing_range(previous["date_text"])
                  != listing_range(card["date_text"])
                  or clean(previous["label"]).casefold()
                  != clean(card["label"]).casefold()
                  or clean(previous["locality"]).casefold()
                  != clean(card["locality"]).casefold()
                  or previous["kind"] != card["kind"]):
                raise ValueError("Paesi in Festa list/cross-check conflict: " + card["url"])
    sitemap_proof, sitemap_events, sitemap_review = sitemap_delta(
        get, by_url, today=today)
    events, excluded = [], []
    review = list(sitemap_review)
    details_read = outside_fvg_urls = 0
    for card in by_url.values():
        url = card["url"]
        if card["region"] == "veneto":
            outside_fvg_urls += 1
            excluded.append({"url": url, "reason": "outside_fvg"})
            continue
        if card["region"] != "fvg" and url not in ROUNDUPS:
            raise ValueError("unrecognized event region: " + url)
        if url in quarantined:
            continue
        try:
            html = fetch_html(get, url)
            details_read += 1
            if ROUNDUPS.get(url) == "presepi":
                child_events, child_excluded = presepi_events(html, card, today=today)
                events.extend(child_events)
                excluded.extend(child_excluded)
                continue
            if ROUNDUPS.get(url) == "carnevale":
                carnevale_exclusion(html)
                excluded.append({"url": url, "reason": "provisional_cross_town_schedule"})
                continue
            event = detail_event(html, card, today=today)
        except ValueError as exc:
            quarantined[url] = {"url": url, "reason": "detail_conflict",
                                "detail": str(exc)[:240]}
            continue
        if event is not None:
            events.append(event)
    events.extend(sitemap_events)
    review.extend(quarantined.values())
    return {"status": "error" if sitemap_review else "ok", "events": events,
            "review_required": review, "excluded": excluded,
            "verification": {"listed_cards": len(cards), "detail_urls": len(by_url),
                             "detail_pages_read": details_read,
                             "outside_fvg_urls": outside_fvg_urls,
                             "quarantined_before_detail": sum(
                                 item["reason"] == "future_card_marked_archived"
                                 for item in quarantined.values()),
                             "list_counts": list_counts,
                             "surface_counts": surface_counts,
                             "surface_date": today.isoformat(),
                             "surface_active_urls": len(surface_active_urls),
                             "extra_active_urls": len(extra_active_urls),
                             "sitemap": sitemap_proof,
                             "review_count": len(review), "excluded_count": len(excluded)},
            "coverage": "two-lists-five-indices-sitemap-detail-discovery"}
