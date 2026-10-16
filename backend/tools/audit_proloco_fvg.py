"""Read-only inventory of Pro Loco FVG events and compare regional coverage.

This is an audit tool, not a source adapter for the production job. It reads
HTML listing/detail pages only; it does not download images or attachments.
"""

import argparse
import json
import re
import unicodedata
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime
from difflib import SequenceMatcher
from pathlib import Path
from urllib.parse import urljoin, urlsplit, urlunsplit
from zoneinfo import ZoneInfo

import requests
from lxml import html


BASE = "https://prolocoregionefvg.it"
INDEX = f"{BASE}/eventi-delle-associate/"
DATE_RE = re.compile(r"\b\d{1,2}/\d{1,2}/20\d{2}\b")
MONTHS = {name: number for number, name in enumerate((
    "gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno",
    "luglio", "agosto", "settembre", "ottobre", "novembre", "dicembre"), 1)}
TEXT_DATE_RE = re.compile(r"\b(\d{1,2})\s+(" + "|".join(MONTHS) + r")\s+(20\d{2})\b")
REVIEWED_ALIASES = {
    "/eventi-delle-associate/farine-di-flor-formandi/": "/eventi/formandi-il-sapore-delle-malghe",
    "/eventi-delle-associate/halloween-party-4/": "/eventi/halloween-party-2026",
}


def clean(value):
    return " ".join((value or "").split())


def canonical_url(value):
    parsed = urlsplit(urljoin(BASE, value))
    if parsed.netloc != "prolocoregionefvg.it":
        raise ValueError(f"Unexpected Pro Loco host: {value}")
    return urlunsplit(("https", parsed.netloc, parsed.path, "", ""))


def normalized(value):
    value = unicodedata.normalize("NFKD", value or "")
    value = "".join(c for c in value if not unicodedata.combining(c))
    return " ".join(re.findall(r"[a-z0-9]+", value.casefold()))


def first_text(tree, path):
    nodes = tree.xpath(path)
    return clean(nodes[0].text_content()) if nodes else ""


def fetch_tree(session, url):
    response = session.get(url, timeout=25)
    response.raise_for_status()
    return html.fromstring(response.content)


def inventory(session):
    pages = []
    occurrences = []
    page_url = INDEX
    seen_pages = set()
    while page_url:
        if page_url in seen_pages or len(pages) >= 30:
            raise RuntimeError(f"Pagination loop or excessive depth: {page_url}")
        seen_pages.add(page_url)
        tree = fetch_tree(session, page_url)
        cards = tree.xpath('//a[contains(concat(" ", normalize-space(@class), " "), " card ") and contains(@href, "/eventi-delle-associate/")]')
        if not cards:
            raise RuntimeError(f"No event cards at {page_url}")
        pages.append(page_url)
        for card in cards:
            occurrences.append({"url": canonical_url(card.get("href")), "listing_text": clean(card.text_content()), "page": page_url})
        next_page = len(pages) + 1
        links = tree.xpath(f'//a[contains(@href, "page={next_page}")]')
        page_url = urljoin(INDEX, links[0].get("href")) if links else None
    return pages, occurrences


def parse_detail(tree, url):
    title = first_text(tree, '//h2[contains(@class,"event-title")]')
    city = first_text(tree, '//h3[contains(@class,"event-date") and contains(@class,"mb-0")]')
    dates_in_sidebar = []
    for node in tree.xpath('//strong[normalize-space()="Quando"]/../following-sibling::li'):
        for value in DATE_RE.findall(clean(node.text_content())):
            dates_in_sidebar.append(datetime.strptime(value, "%d/%m/%Y").date().isoformat())
    h3_dates = [clean(node.text_content()) for node in tree.xpath('//h3[contains(@class,"event-date") and not(contains(@class,"mb-0"))]')]
    descriptions = [clean(node.text_content()) for node in tree.xpath('//div[contains(concat(" ", normalize-space(@class), " "), " testo ")]')]
    image_nodes = tree.xpath('//h2[contains(@class,"event-title")]/following::img[1]')
    image = urljoin(BASE, image_nodes[0].get("src")) if image_nodes and image_nodes[0].get("src") else ""
    if not urlsplit(image).path.startswith("/media/images/"):
        image = ""
    if not title or not city or not (dates_in_sidebar or h3_dates):
        raise RuntimeError(f"Missing title, city or date evidence: {url}")
    return {
        "url": url,
        "title": title,
        "city": city,
        "sidebar_dates": sorted(set(dates_in_sidebar)),
        "heading_dates": h3_dates,
        "description": descriptions[0] if descriptions else "",
        "image": image,
    }


def date_span(event, year):
    dates = [value for value in event["sidebar_dates"] if int(value[:4]) >= year]
    if dates:
        return min(dates), max(dates)
    heading = normalized(" ".join(event["heading_dates"]))
    found = TEXT_DATE_RE.findall(heading)
    if found:
        converted = [date(int(year), MONTHS[month], int(day)).isoformat()
                     for day, month, year in found]
        return min(converted), max(converted)
    return "", ""


def candidates_for(event, tourism, year):
    start, end = date_span(event, year)
    city = normalized(event["city"])
    title = normalized(event["title"])
    candidates = []
    for other in tourism:
        other_city = normalized(other.get("event_city"))
        if city != other_city:
            continue
        other_start, other_end = other.get("start_date") or "", other.get("end_date") or ""
        overlap = bool(start and end and other_start and other_end and start <= other_end and other_start <= end)
        similarity = SequenceMatcher(None, title, normalized(other.get("title"))).ratio()
        if not overlap and similarity < 0.8:
            continue
        candidates.append({
            "url": other["url"], "title": other["title"],
            "start_date": other_start, "end_date": other_end,
            "similarity": round(similarity, 3), "date_overlap": overlap,
            "description_available": bool(other.get("description_excerpt")),
            "image_available": bool(other.get("image")),
        })
    return sorted(candidates, key=lambda item: (item["date_overlap"], item["similarity"]), reverse=True)[:5]


def coverage(event, candidates):
    path = urlsplit(event["url"]).path
    for candidate in candidates:
        if not candidate["date_overlap"]:
            continue
        if normalized(event["title"]) == normalized(candidate["title"]):
            return "same_title", candidate["url"]
        if REVIEWED_ALIASES.get(path) == urlsplit(candidate["url"]).path:
            return "reviewed_alias", candidate["url"]
    return "review_required", ""


def run(snapshot_path, output_path):
    today = datetime.now(ZoneInfo("Europe/Rome")).date()
    session = requests.Session()
    session.headers.update({"User-Agent": "MeteoFriulEventsAudit/1.0 (read-only HTML inventory)"})
    pages, occurrences = inventory(session)
    urls = list(dict.fromkeys(card["url"] for card in occurrences))
    with ThreadPoolExecutor(max_workers=2) as pool:
        details = list(pool.map(lambda url: parse_detail(fetch_tree(session, url), url), urls))
    tourism = json.loads(snapshot_path.read_text(encoding="utf-8"))["events"]
    for detail in details:
        detail["tourism_candidates"] = candidates_for(detail, tourism, today.year)
        detail["coverage_status"], detail["covered_by"] = coverage(detail, detail["tourism_candidates"])
        detail["listing_occurrences"] = sum(card["url"] == detail["url"] for card in occurrences)
    result = {
        "audit_date": today.isoformat(), "source": INDEX,
        "listing_pages": pages, "listing_occurrences": len(occurrences),
        "distinct_details": len(details), "details": details,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"pages={len(pages)} cards={len(occurrences)} details={len(details)}")
    for detail in details:
        best = detail["tourism_candidates"][0] if detail["tourism_candidates"] else None
        print(f"{detail['city']} | {detail['title']} | {date_span(detail, today.year)} | "
              f"{best['similarity'] if best else '-'} / {best['date_overlap'] if best else '-'} | "
              f"{detail['coverage_status']} | {best['title'] if best else 'NO CANDIDATE'}")
    if any(item["coverage_status"] == "review_required" for item in details):
        raise RuntimeError("Pro Loco has event details absent from the reviewed regional coverage")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tourism-snapshot", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    run(args.tourism_snapshot, args.output)
