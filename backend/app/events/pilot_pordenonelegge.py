"""Read-only festival adapter; deliberately absent from the shared beta registry."""
from datetime import date, time
from html.parser import HTMLParser
from urllib.parse import parse_qs, urljoin, urlsplit
import re
import requests
from . import engine
from .pilot_schedule import schedule_notice
from .pilot_programmes import pordenonelegge_edition, programme_session_metadata

URL = "https://www.pordenonelegge.it/programma?giorno=tutto"
VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}
FIELDS = {"festival-programme-event-title": "title", "festival-programme-event-hour": "time",
          "festival-programme-event-place": "place", "light-notice": "access_notes"}
WEEKDAYS = ("lun", "mar", "mer", "gio", "ven", "sab", "dom")


class ProgrammeParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack, self.records = [], []
        self.headings, self.day_tabs = [], []
        self.current = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag in VOID:
            return
        classes = attrs.get("class", "").split()
        root = "festival-programme-event" in classes
        tab = tag == "a" and "festival-programme-tab" in classes and "day" in classes
        if tag == "h1":
            self.headings.append("")
        if tab:
            self.day_tabs.append({"href": urljoin(URL, attrs.get("href", "")), "label": ""})
        if root:
            if self.current is not None:
                raise ValueError("nested event markup")
            self.current = {"start_date": attrs.get("data-giornoevento", ""), "source_id": attrs.get("id", "")}
        field = next((FIELDS[c] for c in classes if c in FIELDS), None)
        self.stack.append((tag, field, root, tab))
        if self.current is not None and tag == "a" and any(f == "title" for _, f, _, _ in self.stack):
            self.current["url"] = urljoin(URL, attrs.get("href", ""))

    def handle_endtag(self, tag):
        if tag in VOID:
            return
        index = next((i for i in range(len(self.stack)-1, -1, -1) if self.stack[i][0] == tag), None)
        if index is None:
            return
        closed = self.stack[index:]
        del self.stack[index:]
        if any(root for _, _, root, _ in closed) and self.current is not None:
            self.records.append(self.current)
            self.current = None

    def handle_data(self, data):
        if self.headings and any(tag == "h1" for tag, _, _, _ in self.stack):
            self.headings[-1] += data
        if self.day_tabs and any(tab for _, _, _, tab in self.stack):
            self.day_tabs[-1]["label"] += data
        if self.current is None:
            return
        for field in {f for _, f, _, _ in self.stack if f}:
            self.current[field] = self.current.get(field, "") + data


def parse_programme(html):
    parser = ProgrammeParser()
    parser.feed(html)
    if parser.current is not None or not parser.records:
        raise ValueError("incomplete or unrecognized programme")
    headings = [re.fullmatch(r"Programma completo\s+(20\d{2})", " ".join(h.split()), re.I)
                for h in parser.headings]
    edition_headings = [match for match in headings if match]
    if len(edition_headings) != 1:
        raise ValueError("missing or ambiguous complete-programme heading")
    year = int(edition_headings[0].group(1))
    tabs, all_tabs = [], 0
    for tab in parser.day_tabs:
        link = urlsplit(tab["href"])
        day_key = parse_qs(link.query).get("giorno", [])
        label_text = " ".join(tab["label"].split()).lower()
        if (link.scheme == "https" and link.hostname == "www.pordenonelegge.it"
                and link.path == "/programma" and day_key == ["tutto"]
                and label_text == "tutto"):
            all_tabs += 1
            continue
        label = re.fullmatch(r"(lun|mar|mer|gio|ven|sab|dom)\s+(\d{1,2})",
                             label_text, re.I)
        if (link.scheme != "https" or link.hostname != "www.pordenonelegge.it"
                or link.path != "/programma" or len(day_key) != 1
                or not label or day_key[0] != label.group(1).lower()):
            raise ValueError("invalid programme day tab")
        tabs.append((day_key[0], int(label.group(2))))
    if all_tabs != 1 or not 1 <= len(tabs) <= 10 or len(set(tabs)) != len(tabs):
        raise ValueError("missing or duplicate programme days")
    raw_days = [date.fromisoformat(raw.get("start_date") or "") for raw in parser.records]
    days = sorted(set(raw_days))
    if (len(days) != len(tabs) or any(day.year != year for day in days)
            or tabs != [(WEEKDAYS[day.weekday()], day.day) for day in days]):
        raise ValueError("programme days disagree with listing or edition")
    metadata = pordenonelegge_edition(days[0], days[-1])
    day_counts = {day.isoformat(): raw_days.count(day) for day in days}
    events, seen, review = [], set(), []
    for raw in parser.records:
        record = {k: " ".join(v.split()) for k, v in raw.items()}
        parsed_day = date.fromisoformat(record["start_date"])
        day = parsed_day.isoformat()
        hour = time.fromisoformat(record.get("time", "")).strftime("%H:%M")
        url = urlsplit(record.get("url", ""))
        if url.scheme != "https" or url.hostname != "www.pordenonelegge.it" or not url.path.startswith("/eventi/"):
            raise ValueError("invalid event link")
        if not record.get("title") or not record.get("place"):
            raise ValueError("missing title or venue")
        if schedule_notice(record.get('title'), record.get('access_notes'), record.get('place'), record.get('time')):
            review.append({'url': record.get('url'), 'source_id': record.get('source_id'), 'reason': 'schedule_change_requires_review'})
            continue
        identity = (record["url"], record["title"], day, hour, record["place"])
        if identity in seen:
            continue
        seen.add(identity)
        city = record["place"].split(",", 1)[0].strip()
        town = engine.fvg_municipality_catalog.match_names(city)
        events.append({**record, **programme_session_metadata(metadata),
                       "start_date": day, "end_date": day, "time": hour,
                       "date_evidence_kind": "event_schedule", "date_evidence": day + ' ' + hour,
                       "event_city": city, "source": "Pordenonelegge", "is_real": True,
                       "lat": town.latitude if town else None, "lon": town.longitude if town else None,
                       "location_confidence": "municipality" if town else "unknown"})
    return {"status": "ok", "events": events, "review_required": review,
            "coverage": "complete-programme-listing-not-detail-pages",
            "verification": {"collection_mode": "complete-official-programme",
                             "edition_id": str(year),
                             "start_date": days[0].isoformat(),
                             "end_date": days[-1].isoformat(),
                             "tab_dates": [day.isoformat() for day in days],
                             "day_counts": day_counts,
                             "records_scanned": len(parser.records),
                             "parsed_count": len(events),
                             "duplicate_count": len(parser.records) - len(events) - len(review),
                             "review_count": len(review)}}


def collect_pordenonelegge(*, get=requests.get):
    # One complete-programme request; no per-event requests or account access.
    with get(URL, timeout=(4, 20), stream=True, allow_redirects=False) as response:
        response.raise_for_status()
        if response.status_code != 200:
            raise ValueError("unexpected programme response")
        chunks, size = [], 0
        for chunk in response.iter_content(65536):
            size += len(chunk)
            if size > 12 * 1024 * 1024:
                raise ValueError("programme too large")
            chunks.append(chunk)
        return parse_programme(b"".join(chunks).decode("utf-8-sig"))


if __name__ == "__main__":
    result = collect_pordenonelegge()
    print({"records": len(result["events"]),
           "dates": sorted({e["start_date"] for e in result["events"]}),
           "municipalities": sorted({e["event_city"] for e in result["events"]}),
           "unlocated": sum(e["lat"] is None for e in result["events"])})
