"""Official Giornate del Cinema Muto HTML calendar, one programme slot per row.

The page sitemap is the inventory. PDF files, film titles inside a screening,
and the separate evening articles are never treated as extra appointments.
"""
from datetime import date, timedelta
from html.parser import HTMLParser
from urllib.parse import urlsplit
from xml.etree import ElementTree
import re

import requests

from . import engine
from .http_client import read_with_single_transient_retry
from .pilot_programmes import cinema_muto_edition, programme_session_metadata
from .pilot_schedule import schedule_notice


SOURCE = "Le Giornate del Cinema Muto"
HOME = "https://www.giornatedelcinemamuto.it/"
SITEMAP = HOME + "page-sitemap.xml"
MONTHS = {name: index for index, name in enumerate((
    "GENNAIO", "FEBBRAIO", "MARZO", "APRILE", "MAGGIO", "GIUGNO",
    "LUGLIO", "AGOSTO", "SETTEMBRE", "OTTOBRE", "NOVEMBRE", "DICEMBRE"), 1)}
WEEKDAYS = ("LUNEDÌ", "MARTEDÌ", "MERCOLEDÌ", "GIOVEDÌ", "VENERDÌ", "SABATO", "DOMENICA")
CALENDAR_PATH = re.compile(r"/calendario-(\d{2})(\d{2})(\d{2})/")
SLOT = re.compile(r"^(\d{2}:\d{2})(?:\s*[-–]\s*(\d{2}:\d{2}))?\s*[-–]\s*(.+)$")
VENUES = {
    "Teatro Zancanaro Sacile": ("Sacile", "Teatro Zancanaro"),
    "Teatro Verdi 2° piano": ("Pordenone", "Teatro Verdi 2° piano"),
    "Teatro Verdi Ridotto": ("Pordenone", "Teatro Verdi Ridotto"),
    "Teatro Verdi": ("Pordenone", "Teatro Verdi"),
    "Palace Hotel Moderno": ("Pordenone", "Palace Hotel Moderno"),
    "Cinemazero": ("Pordenone", "Cinemazero"),
}


def clean(value):
    return " ".join(str(value or "").split())


class CalendarMarkup(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.headings, self.widgets, self.og_images = [], [], []
        self.heading = None
        self.widget_depth = 0
        self.lines, self.line = [], []

    def _line(self):
        value = clean("".join(self.line))
        if value:
            self.lines.append(value)
        self.line = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "meta" and attrs.get("property", "").lower() == "og:image":
            self.og_images.append(attrs.get("content", ""))
        if tag in {"h1", "h3", "h4", "title"}:
            self.heading = [tag, ""]
        if tag == "div":
            if self.widget_depth:
                self.widget_depth += 1
            elif "siteorigin-widget-tinymce" in attrs.get("class", "").split():
                self.widget_depth, self.lines, self.line = 1, [], []
        if self.widget_depth and tag in {"p", "br"}:
            self._line()

    def handle_endtag(self, tag):
        if self.widget_depth and tag in {"p", "br"}:
            self._line()
        if tag == "div" and self.widget_depth:
            self.widget_depth -= 1
            if self.widget_depth == 0:
                self._line()
                self.widgets.append(self.lines)
                self.lines, self.line = [], []
        if self.heading and tag == self.heading[0]:
            self.headings.append((self.heading[0], clean(self.heading[1])))
            self.heading = None

    def handle_data(self, data):
        if self.heading:
            self.heading[1] += data
        if self.widget_depth:
            self.line.append(data)


def markup(html):
    parser = CalendarMarkup()
    parser.feed(html)
    if parser.widget_depth or parser.heading:
        raise ValueError("truncated calendar markup")
    return parser


def parse_home(html):
    page = markup(html)
    names = [text for tag, text in page.headings if tag == "h3"
             and text.upper().startswith("LE GIORNATE DEL CINEMA MUTO")]
    candidates = [re.search(r"PORDENONE\s+(\d{1,2})\s*\|\s*(\d{1,2})\s+"
                            r"([A-ZÀ-Ù]+)\s+(20\d{2})\b", text, re.I)
                  for tag, text in page.headings if tag == "h4"]
    dates = [match for match in candidates if match]
    if len(names) != 1 or len(dates) != 1:
        raise ValueError("edition heading or dates missing")
    first, last, month, year = dates[0].groups()
    try:
        start = date(int(year), MONTHS[month.upper()], int(first))
        end = date(int(year), MONTHS[month.upper()], int(last))
    except (KeyError, ValueError) as error:
        raise ValueError("invalid edition dates") from error
    if not 3 <= (end - start).days + 1 <= 10:
        raise ValueError("unexpected edition span")
    return start, end


def is_edition_cover_url(image, *, year):
    """Reject generic, foreign and previous-edition social images."""
    image = str(image or "").strip()
    parsed = urlsplit(image)
    return (parsed.scheme == "https"
            and parsed.netloc.lower() == "www.giornatedelcinemamuto.it"
            and not parsed.query and not parsed.fragment
            and bool(re.fullmatch(
                rf"/wp-content/uploads/{year}/(?:0[1-9]|1[0-2])/[^/]+\.(?:jpe?g|png|webp)",
                parsed.path, re.I))
            and str(year) in parsed.path.rsplit("/", 1)[-1])


def edition_cover(html, *, year):
    """Use only the official home page's image uploaded for this edition."""
    images = markup(html).og_images
    if len(images) != 1:
        return None
    image = images[0].strip()
    return image if is_edition_cover_url(image, year=year) else None


def parse_sitemap(xml, *, main_start, main_end):
    root = ElementTree.fromstring(xml)
    namespace = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    pages = {}
    for item in root.findall("s:url", namespace):
        url = (item.findtext("s:loc", default="", namespaces=namespace) or "").strip()
        parsed = urlsplit(url)
        if parsed.scheme != "https" or parsed.hostname != "www.giornatedelcinemamuto.it":
            continue
        match = CALENDAR_PATH.fullmatch(parsed.path)
        if not match or parsed.query or parsed.fragment:
            continue
        day, month, year = map(int, match.groups())
        if year != main_start.year % 100:
            continue
        scheduled = date(2000 + year, month, day)
        if scheduled in pages:
            raise ValueError("duplicate calendar page")
        pages[scheduled] = url
    days = sorted(pages)
    main_days = {main_start + timedelta(days=index)
                 for index in range((main_end - main_start).days + 1)}
    if (not main_days.issubset(pages) or not 3 <= len(days) <= 12
            or days != [days[0] + timedelta(days=index) for index in range(len(days))]
            or days[0] < main_start - timedelta(days=1)
            or days[-1] > main_end + timedelta(days=1)):
        raise ValueError("incomplete or unexpected calendar inventory")
    if main_start.year == 2026 and (days[0] != date(2026, 10, 2)
                                    or days[-1] != date(2026, 10, 11)):
        # The organizer explicitly announced these two 2026 appointments.
        raise ValueError("announced 2026 extra dates missing")
    return [(day, pages[day]) for day in days]


def parse_day(html, *, day, url, metadata):
    page = markup(html)
    heading = f"CALENDARIO {WEEKDAYS[day.weekday()]} {day.day} "
    heading += next(name for name, number in MONTHS.items() if number == day.month)
    if ([text.upper() for tag, text in page.headings if tag == "h1" and text] != [heading]
            or not any(tag == "title" and re.search(rf"Calendario\s+{day.year}\b", text, re.I)
                       for tag, text in page.headings)):
        raise ValueError("calendar heading disagrees with URL")
    events, ignored, review = [], [], []
    for widget_index, lines in enumerate(page.widgets, start=1):
        if not lines:
            continue
        match = SLOT.fullmatch(lines[0])
        if not match:
            ignored.append(lines)
            continue
        hour, end_hour, first = match.groups()
        source_id = f"{day.isoformat()}-{widget_index}"
        if (int(hour[:2]) > 23 or int(hour[3:]) > 59
                or (end_hour and (int(end_hour[:2]) > 23 or int(end_hour[3:]) > 59
                                  or end_hour <= hour))):
            review.append({'url': url, 'source_id': source_id,
                           'reason': 'invalid_calendar_time'})
            continue
        if first in VENUES:
            city, venue = VENUES[first]
            if len(lines) < 2:
                review.append({'url': url, 'source_id': source_id,
                               'reason': 'venue_without_title'})
                continue
            title = lines[1]
            if title.lower().startswith("evento di pre-apertura"):
                if len(lines) < 3:
                    review.append({'url': url, 'source_id': source_id,
                                   'reason': 'preopening_title_missing'})
                    continue
                title = lines[2]
            place = f"{city}, {venue}"
        else:
            if re.match(r"^(teatro|palace|auditorium)\b", first, re.I):
                review.append({'url': url, 'source_id': source_id,
                               'reason': 'unknown_calendar_venue'})
                continue
            city, venue, title, place = "Pordenone", None, first, "Pordenone"
        town = engine.fvg_municipality_catalog.match_names(city)
        if not title or not town or schedule_notice(*lines):
            review.append({'url': url, 'source_id': source_id,
                           'reason': 'incomplete_or_changed_slot'})
            continue
        access = next((line for line in lines[1:4]
                       if "prenotazione obbligatoria" in line.lower()
                       or "ingresso gratuito" in line.lower()), "")
        event = {**programme_session_metadata(metadata), "source": SOURCE,
                 "source_id": source_id, "url": url,
                 "title": title, "start_date": day.isoformat(), "end_date": day.isoformat(),
                 "time": hour, "date_evidence_kind": "event_schedule",
                 "date_evidence": f"{day.isoformat()} {hour}", "event_city": city,
                 "place": place, "lat": town.latitude, "lon": town.longitude,
                 "location_confidence": "municipality", "is_real": True}
        if venue:
            event["venue"] = venue
        if end_hour:
            event["end_time"] = end_hour
        if access:
            event["access_notes"] = access
        events.append(event)
    if (len(ignored) != 1 or ignored[0][0].upper() != heading
            or any(SLOT.fullmatch(line) for line in ignored[0][1:])
            or not events and not review):
        raise ValueError("unclassified calendar widget")
    unique, identities = [], set()
    for event in events:
        identity = (event["start_date"], event["time"], event["title"], event["place"])
        if identity in identities:
            review.append({'url': url, 'source_id': event['source_id'],
                           'reason': 'duplicate_programme_slot'})
        else:
            identities.add(identity)
            unique.append(event)
    return unique, review, {"widgets_scanned": len(page.widgets),
                            "slots_parsed": len(unique),
                            "slots_reviewed": len(review)}


def _read(get, url, *, limit):
    def read():
        with get(url, timeout=(4, 12), stream=True, allow_redirects=False) as response:
            response.raise_for_status()
            if response.status_code != 200:
                raise ValueError("unexpected calendar response")
            chunks, size = [], 0
            for chunk in response.iter_content(65536):
                size += len(chunk)
                if size > limit:
                    raise ValueError("calendar response too large")
                chunks.append(chunk)
            return b"".join(chunks).decode("utf-8-sig")

    return read_with_single_transient_retry(read)


def collect_cinema_muto(*, get=requests.get):
    home_html = _read(get, HOME, limit=512 * 1024)
    main_start, main_end = parse_home(home_html)
    pages = parse_sitemap(_read(get, SITEMAP, limit=1024 * 1024),
                          main_start=main_start, main_end=main_end)
    metadata = cinema_muto_edition(pages[0][0], pages[-1][0], main_start, main_end)
    cover = edition_cover(home_html, year=main_start.year)
    if cover:
        metadata["image"] = cover
    events, days, review = [], [], []
    for day, url in pages:
        parsed, issues, proof = parse_day(_read(get, url, limit=1024 * 1024),
                                          day=day, url=url, metadata=metadata)
        events.extend(parsed)
        review.extend(issues)
        days.append({"date": day.isoformat(), "url": url, **proof})
    return {"status": "ok" if events else "error",
            "error_type": None if events else "no_verified_cards",
            "events": events, "review_required": review,
            "coverage": "official-html-calendar-pages-in-page-sitemap",
            "verification": {"collection_mode": "complete-official-html-calendar",
                             "edition_id": str(main_start.year),
                             "main_start_date": main_start.isoformat(),
                             "main_end_date": main_end.isoformat(),
                             "start_date": pages[0][0].isoformat(),
                             "end_date": pages[-1][0].isoformat(),
                             "sitemap_page_count": len(pages),
                             "records_scanned": sum(day["widgets_scanned"] for day in days),
                             "parsed_count": len(events),
                             "review_count": len(review), "days": days}}
