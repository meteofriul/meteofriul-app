"""Complete Villa Manin API reader, checked against the public calendar."""
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime
from html.parser import HTMLParser
import json
import re
import time
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

import requests

from . import engine
from .pilot_excerpt import attributed_excerpt
from .pilot_source_policy import validate_candidate
from .sources.villa_manin import (
    VILLA_MANIN_API_URL, VILLA_MANIN_SOURCE, _ElementorTextExtractor,
    _SINGLE_DATE_RE, _embedded_years, _search_text, audit_villa_manin_payload,
    is_trusted_villa_manin_event_url,
)


BASE = 'https://www.villamanin.it'
LIST_URL = BASE + '/eventi/'
MAX_API_PAGES = 20
MAX_ARCHIVE_PAGES = 20
_CARD = re.compile(r'<article\b[^>]*\bid="post-(\d+)"[^>]*>(.*?)</article>', re.S)
_LABEL = r'\blabel_{name}\b[^>]*>.*?<h2\b[^>]*>(.*?)</h2>'


class Links(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.links = []

    def handle_starttag(self, tag, attrs):
        if tag == 'a':
            href = dict(attrs).get('href')
            if href:
                self.links.append(href)


def _links(html):
    parser = Links()
    parser.feed(html)
    return parser.links


def _card_date(value):
    match = _SINGLE_DATE_RE.fullmatch(_search_text(value))
    if not match:
        raise ValueError('unrecognized Villa Manin calendar date')
    from .sources.villa_manin import _MONTHS
    return date(int(match['year']), _MONTHS[match['month']], int(match['day']))


def parse_listing_cards(html):
    """The public Eventi cards have separate from/to labels and an event URL."""
    cards = {}
    blocks = _CARD.findall(html)
    if not 1 <= len(blocks) <= 200:
        raise ValueError('Villa Manin calendar cards missing or excessive')
    for raw_id, block in blocks:
        urls = {url for url in _links(block) if is_trusted_villa_manin_event_url(url)}
        labels = {}
        for name in ('from', 'to'):
            found = re.findall(_LABEL.format(name=name), block, re.S)
            if len(found) != 1:
                raise ValueError('Villa Manin calendar date label missing')
            labels[name] = _card_date(found[0])
        if len(urls) != 1 or int(raw_id) in cards:
            raise ValueError('invalid Villa Manin calendar card')
        cards[int(raw_id)] = {'url': urls.pop(), 'start': labels['from'],
                              'end': labels['to']}
    if len(cards) != len(blocks) or len({x['url'] for x in cards.values()}) != len(cards):
        raise ValueError('duplicate Villa Manin calendar card')
    return cards


def _archive_urls(html):
    return {url for url in _links(html) if is_trusted_villa_manin_event_url(url)}


def _archive_pages(html, year):
    return {url for url in _links(html)
            if re.fullmatch(rf'{re.escape(BASE)}/anno/{year}/page/\d+/', url)}


def _detail_matches(html, record):
    headings = _ElementorTextExtractor()
    headings.feed(html)
    title = _search_text(record['title'])
    evidence = _search_text(record['date_source_text'])
    return (bool(headings.headings) and _search_text(headings.headings[0]) == title
            and any(_search_text(heading) == evidence for heading in headings.headings[:16])
            and (not record['description'] or _search_text(record['description'])
                 in _search_text(' '.join(headings.paragraphs))))


def _project(record, *, today):
    town = engine.fvg_municipality_catalog.match_names(record['event_city'])
    if not town or record['venue'] != 'Villa Manin':
        raise ValueError('Villa Manin venue or municipality missing')
    occurrences = record['occurrences'] or [record['start_date']]
    days = [date.fromisoformat(value) for value in occurrences]
    if record['date_confidence'] == 'explicit_range':
        days = [date.fromisoformat(record['start_date'])]
    result = []
    for day in days:
        if record['date_confidence'] == 'explicit_range':
            if date.fromisoformat(record['end_date']) < today:
                continue
            start, end = record['start_date'], record['end_date']
        elif day >= today:
            start = end = day.isoformat()
        else:
            continue
        candidate = {
            'source': VILLA_MANIN_SOURCE, 'source_id': record['source_id'],
            'title': record['title'], 'url': record['url'],
            'start_date': start, 'end_date': end,
            'event_city': record['event_city'], 'venue': record['venue'],
            'place': record['place'], 'lat': town.latitude, 'lon': town.longitude,
            'location_confidence': 'municipality', 'image': record['image'],
            'date_evidence_kind': 'event_schedule',
            'date_evidence': record['date_source_text'], 'is_real': True,
            'schedule_kind': ('explicit_occurrence' if record['occurrences']
                              else 'period' if record['date_confidence'] == 'explicit_range'
                              else 'single'),
            **attributed_excerpt(record['description'], source_name=VILLA_MANIN_SOURCE,
                                 source_url=record['url'], title=record['title']),
        }
        invalid = validate_candidate(candidate, today=today)
        if invalid:
            raise ValueError('incomplete Villa Manin candidate: ' + ','.join(invalid))
        result.append(candidate)
    return result


def collect_villa_manin(*, get=requests.get, today=None):
    today = today or datetime.now(ZoneInfo('Europe/Rome')).date()

    def fetch(url, *, max_bytes=8 * 1024 * 1024):
        path = urlsplit(url)
        allowed = (url == LIST_URL or url == BASE + f'/anno/{today.year}/'
                   or re.fullmatch(rf'{re.escape(BASE)}/anno/{today.year}/page/\d+/', url)
                   or is_trusted_villa_manin_event_url(url)
                   or re.fullmatch(re.escape(VILLA_MANIN_API_URL) +
                                   r'\?_embed=1&per_page=100&page=\d+', url))
        if path.scheme != 'https' or path.hostname != 'www.villamanin.it' or not allowed:
            raise ValueError('untrusted Villa Manin URL')
        for attempt in range(2):
            try:
                with get(url, timeout=(4, 15), stream=True, allow_redirects=False) as response:
                    response.raise_for_status()
                    if response.status_code != 200:
                        raise ValueError('unexpected Villa Manin redirect')
                    chunks, size = [], 0
                    for chunk in response.iter_content(65536):
                        size += len(chunk)
                        if size > max_bytes:
                            raise ValueError('oversized Villa Manin page')
                        chunks.append(chunk)
                    return b''.join(chunks).decode('utf-8-sig'), response.headers
            except (requests.Timeout, requests.ConnectionError):
                if attempt:
                    raise
                time.sleep(0.5)

    def api_page(page):
        url = f'{VILLA_MANIN_API_URL}?_embed=1&per_page=100&page={page}'
        body, headers = fetch(url)
        return json.loads(body), headers

    first, first_headers = api_page(1)
    total = int(first_headers['X-WP-Total'])
    page_count = int(first_headers['X-WP-TotalPages'])
    if (not isinstance(first, list) or not 1 <= total <= 2000
            or not 1 <= page_count <= MAX_API_PAGES
            or page_count != (total + 99) // 100 or len(first) != min(100, total)):
        raise ValueError('invalid Villa Manin API pagination')
    pages = [(first, first_headers)]
    if page_count > 1:
        with ThreadPoolExecutor(max_workers=2) as pool:
            pages.extend(pool.map(api_page, range(2, page_count + 1)))
    rows = []
    for number, (page_rows, headers) in enumerate(pages, 1):
        if (not isinstance(page_rows, list) or int(headers['X-WP-Total']) != total
                or int(headers['X-WP-TotalPages']) != page_count
                or len(page_rows) != min(100, total - 100 * (number - 1))):
            raise ValueError('incomplete Villa Manin API page')
        rows.extend(page_rows)
    ids = [row.get('id') for row in rows if isinstance(row, dict)]
    urls = [row.get('link') for row in rows if isinstance(row, dict)]
    if (len(rows) != total or len(ids) != total or len(set(ids)) != total
            or len(set(urls)) != total):
        raise ValueError('duplicate or missing Villa Manin API record')
    by_id = {row['id']: row for row in rows}

    listing_html, _ = fetch(LIST_URL)
    cards = parse_listing_cards(listing_html)
    if any(source_id not in by_id or by_id[source_id].get('link') != card['url']
           for source_id, card in cards.items()):
        raise ValueError('Villa Manin calendar/API mismatch')

    archive_url = BASE + f'/anno/{today.year}/'
    first_archive, _ = fetch(archive_url)
    archive_links = _archive_urls(first_archive)
    discovered = _archive_pages(first_archive, today.year)
    seen_pages = {archive_url}
    while discovered - seen_pages:
        if len(seen_pages) >= MAX_ARCHIVE_PAGES:
            raise ValueError('Villa Manin year archive pagination limit')
        url = sorted(discovered - seen_pages)[0]
        seen_pages.add(url)
        html, _ = fetch(url)
        archive_links.update(_archive_urls(html))
        discovered.update(_archive_pages(html, today.year))
    annual_api = {row['link'] for row in rows if today.year in _embedded_years(row)}
    if not annual_api or annual_api != archive_links:
        raise ValueError('Villa Manin annual archive/API mismatch')

    report = audit_villa_manin_payload(rows, as_of=today)
    if report['structure_errors']:
        raise ValueError('Villa Manin API record schema changed')
    rejected_past_cards = 0
    rejected_outside_current_surfaces = 0
    review = []
    historical_card_conflicts = 0
    for source_id, card in cards.items():
        if card['end'] < card['start']:
            if max(card['start'], card['end']) >= today:
                review.append({'url': card['url'], 'reason': 'inverted_calendar_dates'})
            else:
                historical_card_conflicts += 1
    for excluded in report['rejected']:
        row = by_id[int(excluded['source_id'])]
        card = cards.get(row['id'])
        years = _embedded_years(row)
        current_or_future = any(year >= today.year for year in years)
        recently_changed = str(row.get('modified') or '') >= '2026-10-07T00:00:00'
        if card and card['end'] < today and not any(year > today.year for year in years):
            rejected_past_cards += 1
        elif current_or_future or card or recently_changed:
            review.append({'url': row.get('link'), 'reason': excluded['reason']})
        else:
            rejected_outside_current_surfaces += 1

    active = report['records']
    for record in active:
        row = by_id[int(record['source_id'])]
        card = cards.get(row['id'])
        start, end = date.fromisoformat(record['start_date']), date.fromisoformat(record['end_date'])
        # The "anno" term denotes an edition, not every occurrence year:
        # the 2026 Scrigno card explicitly ends in January 2027.
        if (not card or start < card['start'] or end > card['end']
                or not any(year >= today.year for year in _embedded_years(row))):
            review.append({'url': record['url'], 'reason': 'calendar_or_year_disagreement'})
    if not review:
        with ThreadPoolExecutor(max_workers=4) as pool:
            detail_pages = list(pool.map(lambda item: fetch(item['url'])[0], active))
        for record, html in zip(active, detail_pages):
            if not _detail_matches(html, record):
                review.append({'url': record['url'], 'reason': 'detail_date_disagreement'})

    events = []
    if not review:
        for record in active:
            events.extend(_project(record, today=today))
    events.sort(key=lambda event: (event['start_date'], event['title'], event['url']))
    proof = {'collection_mode': 'complete-villa-manin-api-calendar-year-archive',
             'source_complete': not review, 'records_scanned': total,
             'api_pages': page_count, 'year_archive_pages': len(seen_pages),
             'year_archive_count': len(archive_links), 'calendar_cards': len(cards),
             'historical_card_conflicts': historical_card_conflicts,
             'active_records': len(active), 'inactive_records': report['counts']['inactive'],
             'rejected_records': len(report['rejected']),
             'rejected_past_cards': rejected_past_cards,
             'rejected_outside_current_surfaces': rejected_outside_current_surfaces,
             'review_count': len(review), 'detail_pages_checked': len(active) if not review else 0,
             'projected_count': len(events)}
    return {'status': 'ok' if not review else 'error',
            'error_type': None if not review else 'incomplete_source',
            'events': events, 'review_required': review, 'verification': proof,
            'coverage': 'full-api-current-year-archive-calendar-and-active-details'}
