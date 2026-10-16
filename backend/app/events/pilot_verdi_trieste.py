"""Official Trieste season API, public calendar and performance detail pages."""
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime
from html.parser import HTMLParser
import json
import re
from zoneinfo import ZoneInfo
from urllib.parse import urlsplit
from xml.etree import ElementTree
import requests
from .pilot_azalea import clean
from .pilot_excerpt import attributed_excerpt
from .pilot_verdi_pordenone import MONTHS
from . import engine
from .pilot_schedule import schedule_notice
from .pilot_source_policy import validate_candidate

BASE = 'https://www.teatroverdi-trieste.com'
URL = BASE + '/it/calendario-spettacoli/'
SITEMAP_INDEX = BASE + '/sitemap_index.xml'
SHOW_SITEMAP = BASE + '/spettacoli-sitemap.xml'
SEASON_API = BASE + '/wp-json/wp/v2/stagione?per_page=100&lang=it&_fields=id,name,slug,count'
SHOW_API = BASE + '/wp-json/wp/v2/spettacoli'
AUDIT_BASELINE = '2026-10-07T00:00:00+00:00'

def explicit_slots(text):
    """Read enumerated calendar dates; absent time is not midnight."""
    match = re.fullmatch(r'(.+?)\s+(20\d{2})(?:\s+ore\s+(\d{1,2}[:.]\d{2}))?', text, re.I)
    if not match:
        raise ValueError('unrecognized explicit dates')
    body = re.sub(r'\b(?:lunedì|martedì|mercoledì|giovedì|venerdì|sabato|domenica)\b', '', match[1], flags=re.I)
    body = re.sub(r'\be\b', ',', body, flags=re.I).strip()
    dates, cursor = [], 0
    for segment in re.finditer(r'(\d{1,2}(?:\s*,\s*\d{1,2})*)\s+([a-z]+)', body, re.I):
        if body[cursor:segment.start()].strip(' ,') or segment[2].lower() not in MONTHS:
            raise ValueError('ambiguous date separator')
        dates.extend(date(int(match[2]), MONTHS[segment[2].lower()], int(day.strip()))
                     for day in segment[1].split(','))
        cursor = segment.end()
    if not dates or body[cursor:].strip(' ,') or dates != sorted(set(dates)):
        raise ValueError('ambiguous calendar dates')
    hour = datetime.strptime(match[3].replace('.', ':'), '%H:%M').strftime('%H:%M') if match[3] else None
    return dates, hour

def parse_calendar(html, *, today):
    cards = re.findall(r'<h2 class="spettacolo-list-title">(.*?)</h2>\s*<span class="spettacolo-list-date">(.*?)</span>', html, re.S)
    if not cards:
        raise ValueError('unrecognized public calendar')
    events, review = [], []
    town = engine.fvg_municipality_catalog.match_names('Trieste')
    for title, schedule in cards:
        link = re.search(r'href="([^"]+)"', title)
        if not link or urlsplit(link[1]).hostname != 'www.teatroverdi-trieste.com' or urlsplit(link[1]).scheme != 'https':
            raise ValueError('invalid event link')
        text = clean(schedule)
        if schedule_notice(title, schedule):
            review.append({'url': link[1], 'reason': 'schedule_change_requires_review'})
            continue
        try:
            days, hour = explicit_slots(text)
        except ValueError:
            review.append({'url': link[1], 'reason': 'replica_dates_or_time_require_review'})
            continue
        for day in days:
            if day >= today:
                event = dict(source='Teatro Verdi Trieste', title=clean(title), url=link[1],
                    start_date=day.isoformat(), end_date=day.isoformat(),
                    event_city='Trieste', place='Trieste', lat=town.latitude, lon=town.longitude,
                    location_confidence='municipality', date_evidence=text,
                    date_evidence_kind='event_schedule', is_real=True)
                if hour:
                    event['time'] = hour
                events.append(event)
    return {'status': 'ok', 'events': events, 'review_required': review, 'coverage': 'public-calendar-explicit-dates-times-when-specified'}


class DetailMedia(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.image = None
        self.in_main = False
        self.paragraph = None
        self.paragraphs = []

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if tag == 'meta' and values.get('property') == 'og:image':
            candidate = values.get('content') or ''
            parsed = urlsplit(candidate)
            if (parsed.scheme == 'https' and parsed.hostname == 'www.teatroverdi-trieste.com'
                    and parsed.path.startswith('/wp-content/uploads/')):
                self.image = candidate
        if tag == 'main' and values.get('id') == 'spettacolo-content':
            self.in_main = True
        if tag == 'p' and self.in_main:
            self.paragraph = []

    def handle_data(self, data):
        if self.paragraph is not None:
            self.paragraph.append(data)

    def handle_endtag(self, tag):
        if tag == 'p' and self.paragraph is not None:
            self.paragraphs.append(clean(' '.join(self.paragraph)))
            self.paragraph = None
        if tag == 'main':
            self.in_main = False


def parse_detail(html, url, *, today):
    title_match = re.search(r'<h1\b[^>]*>(.*?)</h1>', html, re.S)
    if not title_match:
        raise ValueError('missing Teatro Verdi Trieste title')
    title = clean(title_match[1])
    blocks = re.findall(r'<div class="spettacolo-date-wrapper">(.*?)</div>', html, re.S)
    if not blocks:
        summary = re.search(r'<span class="spettacolo-header-small-title"><strong>'
                            r'(.*?)</strong></span>', html, re.S)
        if summary:
            days, hour = explicit_slots(clean(summary[1]))
            if all(day < today for day in days):
                return [], [(day, hour, clean(summary[1])) for day in days]
        raise ValueError('missing Teatro Verdi Trieste ticket dates')
    slots = []
    for block in blocks:
        date_match = re.search(r'<span class="spettacolo-ticket-date">(.*?)</span>', block, re.S)
        time_match = re.search(r'<span class="spettacolo-ticket-time">(.*?)</span>', block, re.S)
        if not date_match or not time_match:
            raise ValueError('incomplete Teatro Verdi Trieste ticket slot')
        day_text = clean(date_match[1])
        match = re.fullmatch(r'(\d{1,2})\s+([a-z]+)\s+(20\d{2})', day_text, re.I)
        clock = re.fullmatch(r'Ore\s+(\d{1,2}[:.]\d{2})', clean(time_match[1]), re.I)
        if not match or match[2].lower() not in MONTHS or not clock:
            raise ValueError('ambiguous Teatro Verdi Trieste ticket slot')
        day = date(int(match[3]), MONTHS[match[2].lower()], int(match[1]))
        hour = datetime.strptime(clock[1].replace('.', ':'), '%H:%M').strftime('%H:%M')
        slots.append((day, hour, day_text + ' ' + clean(time_match[1])))
    if len(slots) != len(set((day, hour) for day, hour, _ in slots)):
        raise ValueError('duplicate Teatro Verdi Trieste ticket slot')
    if not any(day >= today for day, _, _ in slots):
        return [], slots
    if schedule_notice(title, html):
        raise ValueError('schedule_change_requires_review')
    media = DetailMedia()
    media.feed(html)
    if not media.image:
        raise ValueError('missing Teatro Verdi Trieste event image')
    excerpt = next((paragraph for paragraph in media.paragraphs
                    if 25 <= len(paragraph) <= 600
                    and not re.match(r'(?i)^(?:stagione\b|programma\b|sala\b|teatro\b|'
                                     r'orchestra\b|direttore\b|maestro\b|'
                                     r'luned[iì]\b|marted[iì]\b|mercoled[iì]\b|'
                                     r'gioved[iì]\b|venerd[iì]\b|sabato\b|domenica\b|'
                                     r'\d{1,2}\b)', paragraph)
                    and not re.search(r'\b(?:20\d{2}|ore\s+\d{1,2}[:.]\d{2})\b', paragraph, re.I)
                    and paragraph.casefold() != title.casefold()), '')
    description = attributed_excerpt(excerpt, source_name='Teatro Verdi Trieste',
                                     source_url=url, title=title)
    town = engine.fvg_municipality_catalog.match_names('Trieste')
    events = []
    for day, hour, evidence in slots:
        if day >= today:
            event = {'source': 'Teatro Verdi Trieste', 'title': title, 'url': url,
                     'start_date': day.isoformat(), 'end_date': day.isoformat(),
                     'time': hour, 'event_city': 'Trieste', 'place': 'Trieste',
                     'lat': town.latitude, 'lon': town.longitude,
                     'location_confidence': 'municipality', 'date_evidence': evidence,
                     'date_evidence_kind': 'event_schedule', 'is_real': True,
                     'image': media.image, **description}
            invalid = validate_candidate(event, today=today)
            if invalid:
                raise ValueError('invalid Teatro Verdi Trieste event: ' + ','.join(invalid))
            events.append(event)
    return events, slots


def collect_verdi_trieste(*, get=requests.get, today=None):
    today = today or datetime.now(ZoneInfo('Europe/Rome')).date()
    def fetch(url, *, max_bytes=4*1024*1024):
        parsed = urlsplit(url)
        if (parsed.scheme != 'https' or parsed.hostname != 'www.teatroverdi-trieste.com'
                or parsed.query or parsed.fragment
                or (url not in {URL, SITEMAP_INDEX, SHOW_SITEMAP}
                    and not re.fullmatch(r'/it/spettacoli/[^/]+/', parsed.path))):
            raise ValueError('untrusted Teatro Verdi Trieste URL')
        with get(url, timeout=(4, 12), stream=True, allow_redirects=False) as response:
            response.raise_for_status()
            if response.status_code != 200:
                raise ValueError('Teatro Verdi Trieste redirect or unavailable page')
            chunks, size = [], 0
            for chunk in response.iter_content(65536):
                size += len(chunk)
                if size > max_bytes:
                    raise ValueError('oversized Teatro Verdi Trieste response')
                chunks.append(chunk)
            return b''.join(chunks).decode('utf-8-sig')

    def api(url):
        if (url != SEASON_API and not re.fullmatch(
                re.escape(SHOW_API) +
                r'\?stagione=\d+&per_page=100&lang=it&_fields=id,link,stagione,lang', url)):
            raise ValueError('untrusted Teatro Verdi Trieste API URL')
        with get(url, timeout=(4, 12), stream=True, allow_redirects=False) as response:
            response.raise_for_status()
            if response.status_code != 200:
                raise ValueError('Teatro Verdi Trieste API unavailable')
            chunks, size = [], 0
            for chunk in response.iter_content(65536):
                size += len(chunk)
                if size > 2*1024*1024:
                    raise ValueError('oversized Teatro Verdi Trieste API response')
                chunks.append(chunk)
            return json.loads(b''.join(chunks).decode('utf-8-sig')), response.headers

    namespace = '{http://www.sitemaps.org/schemas/sitemap/0.9}'
    index = ElementTree.fromstring(fetch(SITEMAP_INDEX, max_bytes=1024*1024))
    maps = {item.text for item in index.findall('.//' + namespace + 'loc')}
    if SHOW_SITEMAP not in maps or any('spettacoli-sitemap' in value and value != SHOW_SITEMAP
                                       for value in maps):
        raise ValueError('changed Teatro Verdi Trieste sitemap structure')
    root = ElementTree.fromstring(fetch(SHOW_SITEMAP, max_bytes=2*1024*1024))
    sitemap = {item.findtext(namespace + 'loc'): item.findtext(namespace + 'lastmod')
               for item in root.findall(namespace + 'url')}
    if not 1 <= len(sitemap) <= 1000 or any(not value for value in sitemap.values()):
        raise ValueError('invalid Teatro Verdi Trieste show sitemap')

    calendar = fetch(URL)
    cards = re.findall(r'<h2 class="spettacolo-list-title">(.*?)</h2>\s*'
                       r'<span class="spettacolo-list-date">(.*?)</span>', calendar, re.S)
    if not 1 <= len(cards) <= 100:
        raise ValueError('invalid Teatro Verdi Trieste calendar size')
    listed = {}
    for title, schedule in cards:
        link = re.search(r'href="([^"]+)"', title)
        if not link or link[1] in listed:
            raise ValueError('duplicate or missing Teatro Verdi Trieste calendar link')
        days, _ = explicit_slots(clean(schedule))
        listed[link[1]] = {day for day in days if day >= today}

    terms, headers = api(SEASON_API)
    if (not isinstance(terms, list) or not 1 <= len(terms) <= 100
            or int(headers['X-WP-Total']) != len(terms)
            or int(headers['X-WP-TotalPages']) != 1):
        raise ValueError('incomplete Teatro Verdi Trieste season terms')
    start_year = today.year if today.month >= 8 else today.year - 1
    active_terms = []
    for term in terms:
        match = re.fullmatch(r'(20\d{2})[/\-](\d{2}|20\d{2})', term['name'])
        if match:
            ending = int(match[2]) if len(match[2]) == 4 else 2000 + int(match[2])
            if ending == int(match[1]) + 1 and int(match[1]) >= start_year:
                active_terms.append(term)
    if not 1 <= len(active_terms) <= 3:
        raise ValueError('current Teatro Verdi Trieste season missing')
    season_links = set()
    for term in active_terms:
        url = (f'{SHOW_API}?stagione={term["id"]}&per_page=100&lang=it'
               '&_fields=id,link,stagione,lang')
        rows, headers = api(url)
        if (not isinstance(rows, list) or not 1 <= len(rows) <= 100
                or int(headers['X-WP-Total']) != len(rows)
                or int(headers['X-WP-TotalPages']) != 1
                or len({row['id'] for row in rows}) != len(rows)
                or any(row['lang'] != 'it' or term['id'] not in row['stagione']
                       for row in rows)):
            raise ValueError('incomplete Teatro Verdi Trieste season API')
        season_links.update(row['link'] for row in rows)
    urls = sorted(season_links | set(listed))
    if not set(urls) <= set(sitemap):
        raise ValueError('Teatro Verdi Trieste show absent from sitemap')
    # The show sitemap also contains language variants and archive indexes.
    # Only a newly changed Italian show detail can add an event to this source.
    changed_unlisted = [url for url, modified in sitemap.items()
                        if modified >= AUDIT_BASELINE and url not in urls
                        and re.fullmatch(
                            r'https://www\.teatroverdi-trieste\.com/it/spettacoli/[^/]+/',
                            url)]
    if changed_unlisted:
        raise ValueError('modified Teatro Verdi Trieste show outside inventory')
    with ThreadPoolExecutor(max_workers=4) as pool:
        html_by_url = dict(zip(urls, pool.map(fetch, urls)))
    events, review, checked = [], [], []
    for url in urls:
        try:
            parsed, slots = parse_detail(html_by_url[url], url, today=today)
            future_dates = sorted({day.isoformat() for day, _, _ in slots if day >= today})
            future_slot_count = len(parsed)
            if url in listed and set(future_dates) != {day.isoformat() for day in listed[url]}:
                raise ValueError('Teatro Verdi Trieste calendar/detail date mismatch')
            events.extend(parsed)
            disposition = 'included' if parsed else 'past'
        except ValueError as exc:
            review.append({'url': url, 'reason': str(exc)})
            disposition = 'review_required'
            future_dates, future_slot_count = [], 0
        checked.append({'url': url, 'disposition': disposition,
                        'future_dates': future_dates, 'future_slot_count': future_slot_count})
    events.sort(key=lambda item: (item['start_date'], item.get('time') or '',
                                  item['event_city'], item['title'], item['url']))
    proof = {'collection_mode': 'complete-verdi-trieste-season-api-calendar-details',
             'calendar_count': len(listed), 'calendar_urls': sorted(listed),
             'calendar_records': [{'url': url, 'future_dates': sorted(
                 day.isoformat() for day in listed[url])} for url in sorted(listed)],
             'season_term_ids': sorted(term['id'] for term in active_terms),
             'season_api_count': len(season_links), 'season_api_urls': sorted(season_links),
             'sitemap_count': len(sitemap), 'changed_unlisted_count': len(changed_unlisted),
             'detail_count': len(checked), 'detail_records': checked,
             'event_count': len(events), 'review_count': len(review),
             'source_complete': True}
    return {'status': 'ok', 'events': events, 'review_required': review,
            'verification': proof, 'coverage': 'complete-current-season-and-calendar-details'}

if __name__ == '__main__':
    result = collect_verdi_trieste()
    print({'events': len(result['events']), 'review': len(result['review_required'])})
