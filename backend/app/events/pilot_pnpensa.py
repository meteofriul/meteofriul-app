"""Pordenone Pensa public WordPress inventory and dated announcements."""
from datetime import date, datetime
from html.parser import HTMLParser
import json
import re
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo
from xml.etree import ElementTree
import requests
from .pilot_azalea import clean
from .pilot_excerpt import attributed_excerpt
from .pilot_verdi_pordenone import MONTHS
from . import engine
from .pilot_schedule import schedule_notice
from .pilot_programmes import PORDENONE_PENSA_2026, programme_session_metadata
from .pilot_source_policy import validate_candidate

URL = "https://www.pnpensa.it/pnpensa-giallo-settembre-2026-pordenone/"
BASE = "https://www.pnpensa.it/"
SITEMAP = BASE + "post-sitemap.xml"
API = BASE + "wp-json/wp/v2/posts"
FIELDS = "id,date,modified,slug,link,title,excerpt,content,categories,featured_media"
PAGE_SITEMAP = BASE + "page-sitemap.xml"
PAGE_API = BASE + "wp-json/wp/v2/pages"
PAGE_FIELDS = "id,link,title,content,modified"
MONTH_PATTERN = '|'.join(MONTHS)
DAY_MONTH = re.compile(r'\b(\d{1,2})\s+(' + MONTH_PATTERN + r')\b(?:\s+(20\d{2}))?', re.I)


def trusted_post_url(url):
    parsed = urlsplit(str(url or ''))
    return (parsed.scheme == 'https' and parsed.hostname == 'www.pnpensa.it'
            and bool(re.fullmatch(r'/[a-z0-9_-]+/', parsed.path))
            and not parsed.query and not parsed.fragment)


def trusted_page_url(url):
    parsed = urlsplit(str(url or ''))
    return (parsed.scheme == 'https' and parsed.hostname == 'www.pnpensa.it'
            and (parsed.path == '/' or bool(re.fullmatch(
                r'/(?:[a-z0-9_-]+/){1,3}', parsed.path)))
            and not parsed.query and not parsed.fragment)


class ContentMedia(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.image = None
        self.paragraphs = []
        self.paragraph = None

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if tag == 'img' and self.image is None:
            source = values.get('src') or ''
            parsed = urlsplit(source)
            if (parsed.scheme == 'https' and parsed.hostname == 'www.pnpensa.it'
                    and parsed.path.startswith('/wp-content/uploads/')):
                self.image = source
        if tag == 'p' and self.paragraph is None:
            self.paragraph = []

    def handle_data(self, data):
        if self.paragraph is not None:
            self.paragraph.append(data)

    def handle_endtag(self, tag):
        if tag == 'p' and self.paragraph is not None:
            value = clean(' '.join(self.paragraph))
            if value:
                self.paragraphs.append(value)
            self.paragraph = None



WEEKDAYS = ('lunedì', 'martedì', 'mercoledì', 'giovedì', 'venerdì', 'sabato', 'domenica')
SESSION_DATE = re.compile(
    r'^(?:(?P<weekday>' + '|'.join(WEEKDAYS) + r')\s+)?'
    r'(?P<day>\d{1,2})\s+(?P<month>' + MONTH_PATTERN + r')'
    r'(?:\s+(?P<year>20\d{2}))?\s*,?\s*ore\s+'
    r'(?P<hour>\d{1,2})(?:[:.](?P<minute>\d{2}))?\s*$', re.I)


class ProgrammeSections(HTMLParser):
    """Keep WordPress programme rows separate, including each row's own image."""
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.sections = []
        self.current = None

    def handle_starttag(self, tag, attrs):
        if tag == 'section':
            if self.current is not None:
                raise ValueError('nested programme sections need review')
            self.current = ContentMedia()
        elif self.current is not None:
            self.current.handle_starttag(tag, attrs)

    def handle_data(self, data):
        if self.current is not None:
            self.current.handle_data(data)

    def handle_endtag(self, tag):
        if tag == 'section' and self.current is not None:
            if self.current.paragraph is not None:
                raise ValueError('truncated programme paragraph')
            self.sections.append(self.current)
            self.current = None
        elif self.current is not None:
            self.current.handle_endtag(tag)


def programme_year(post):
    title = clean(post['title']['rendered'])
    html = post['content']['rendered']
    years = set(re.findall(r'\b20\d{2}\b', title))
    years.update(re.findall(r'\bedizione\s+(20\d{2})\b', clean(html), re.I))
    for heading in re.findall(r'<h[1-6]\b[^>]*>(.*?)</h[1-6]>', html, re.S | re.I):
        text = clean(heading)
        if re.search(r'pensa|edizione', text, re.I):
            years.update(re.findall(r'\b20\d{2}\b', text))
    if len(years) > 1:
        raise ValueError('conflicting programme years in title and content')
    return int(next(iter(years))) if years else None


def structured_sessions(post, *, year, today):
    """Extract only explicit date/time, municipality/venue and title rows.

    No publication-year guess for a programme. Extra future dates or incomplete
    rows quarantine the whole post, rather than publishing a partial programme.
    """
    html = post['content']['rendered']
    media = ContentMedia()
    media.feed(html)
    if not any(SESSION_DATE.fullmatch(text) for text in media.paragraphs):
        return None
    if re.search(r'\bdal\s+\d{1,2}\s+al\s+\d{1,2}',
                 clean(post['title']['rendered']), re.I):
        raise ValueError('programme title date range needs review')
    parser = ProgrammeSections()
    parser.feed(html)
    if parser.current is not None:
        raise ValueError('truncated programme section')
    rows = []
    for section in parser.sections:
        slots = [(index, SESSION_DATE.fullmatch(text))
                 for index, text in enumerate(section.paragraphs)]
        slots = [(index, match) for index, match in slots if match]
        first = section.paragraphs[0] if section.paragraphs else ''
        first = re.sub(r'^(?:' + '|'.join(WEEKDAYS) + r')\s+', '', first, flags=re.I)
        if not slots and DAY_MONTH.match(first):
            raise ValueError('dated programme row without verified time')
        if slots:
            if len(slots) != 1 or slots[0][0] != 0:
                raise ValueError('multiple or unassigned programme sessions')
            rows.append((section, slots[0][1]))
    if not rows:
        return None
    if year is None:
        raise ValueError('programme year not verified')
    events, dates, identities = [], set(), set()
    for section, slot in rows:
        if slot['year'] and int(slot['year']) != year:
            raise ValueError('conflicting programme session year')
        day = date(year, MONTHS[slot['month'].lower()], int(slot['day']))
        if slot['weekday'] and slot['weekday'].casefold() != WEEKDAYS[day.weekday()]:
            raise ValueError('programme weekday/date mismatch')
        hour, minute = int(slot['hour']), int(slot['minute'] or 0)
        if hour > 23 or minute > 59:
            raise ValueError('invalid programme time')
        dates.add(day)
        paragraphs = section.paragraphs
        if len(paragraphs) < 4:
            raise ValueError('incomplete programme session')
        city, separator, venue = paragraphs[1].partition(',')
        town = engine.fvg_municipality_catalog.match_names(city.strip())
        if not separator or not venue.strip() or not town:
            raise ValueError('programme municipality/venue not verified')
        venue = re.sub(r'\s+([,.;:])', r'\1', venue).strip()
        title = paragraphs[2]
        if schedule_notice(*paragraphs):
            raise ValueError('schedule_change_requires_review')
        identity = (day, hour, minute, town.name, venue.strip(), title)
        if identity in identities:
            raise ValueError('duplicate programme session')
        identities.add(identity)
        event = {'source': 'Pordenone Pensa', 'url': post['link'], 'title': title,
                 'start_date': day.isoformat(), 'end_date': day.isoformat(),
                 'time': f'{hour:02d}:{minute:02d}', 'event_city': town.name,
                 'place': venue.strip(), 'venue': venue.strip(),
                 'location_confidence': 'municipality',
                 'lat': town.latitude, 'lon': town.longitude,
                 'date_evidence_kind': 'event_schedule',
                 'date_evidence': f'{paragraphs[0]} [edizione {year}]', 'is_real': True}
        if section.image:
            event['image'] = section.image
        event.update(attributed_excerpt(paragraphs[3], source_name='Pordenone Pensa',
                                        source_url=post['link'], title=title))
        if not event.get('description_excerpt'):
            raise ValueError('programme session description unavailable')
        if day >= today:
            invalid = validate_candidate(event, today=today)
            if invalid:
                raise ValueError('invalid programme session: ' + ','.join(invalid))
            events.append(event)
    # This also catches a newly added date in a layout that we cannot extract.
    text = clean(post['title']['rendered']) + ' ' + clean(post['content']['rendered'])
    for match in DAY_MONTH.finditer(text):
        other = date(int(match[3]) if match[3] else year,
                     MONTHS[match[2].lower()], int(match[1]))
        if other >= today and other not in dates:
            raise ValueError('additional future date needs session extraction')
    return events, 'included' if events else 'past'


def post_date(post):
    title = clean(post['title']['rendered'])
    matches = list(DAY_MONTH.finditer(title))
    if not matches:
        return None
    match = matches[-1]
    year = match[3]
    if not year:
        years = set(re.findall(r'\b20\d{2}\b', title))
        if len(years) == 1:
            year = years.pop()
    evidence = title
    if not year:
        edition = set(re.findall(r'\bedizione\s+(20\d{2})\b',
                                 clean(post['content']['rendered']), re.I))
        if len(edition) == 1:
            year = edition.pop()
            evidence += f' [edizione {year}]'
    if not year:
        # A new announcement can omit the year when its dated meeting follows
        # publication in that same year. Older or cross-year text is ambiguous.
        published = date.fromisoformat(post['date'][:10])
        candidate = date(published.year, MONTHS[match[2].lower()], int(match[1]))
        if published <= candidate and (candidate - published).days <= 180:
            year = str(published.year)
            evidence += f' [pubblicato {published.isoformat()}]'
        elif (candidate <= published and published.month < 11
              and candidate < published):
            year = str(published.year)
            evidence += f' [resoconto pubblicato {published.isoformat()}]'
    if not year:
        return None
    return date(int(year), MONTHS[match[2].lower()], int(match[1])), evidence


def post_city(title, body):
    aliases = {'Azzano X': 'Azzano Decimo'}
    for alias, canonical in aliases.items():
        if re.search(r'\b' + re.escape(alias) + r'\b', title, re.I):
            return canonical
    towns = sorted(engine.fvg_municipality_catalog.municipalities,
                   key=lambda item: -len(item.name))
    for town in towns:
        if re.search(r'\b' + re.escape(town.name) + r'\b', title, re.I):
            return town.name
    for town in towns:
        if re.search(r'\b(?:a|ad|in)\s+' + re.escape(town.name) + r'\b',
                     body[:1800], re.I):
            return town.name
    return None


def classify_post(post, *, today):
    url = post['link']
    if not trusted_post_url(url):
        raise ValueError('untrusted Pordenone Pensa post URL')
    title = clean(post['title']['rendered'])
    body = clean(post['content']['rendered'])
    sessions = structured_sessions(post, year=programme_year(post), today=today)
    if sessions is not None:
        return sessions
    dated = post_date(post)
    if dated is None:
        if DAY_MONTH.search(title):
            raise ValueError('year of dated announcement not verified')
        # A dated future programme in the body without a recognised title
        # cannot be dismissed as an ordinary undated article.
        for match in DAY_MONTH.finditer(body):
            year = int(match[3]) if match[3] else date.fromisoformat(post['date'][:10]).year
            if date(year, MONTHS[match[2].lower()], int(match[1])) >= today:
                raise ValueError('future date outside recognised announcement')
        return [], 'no_defined_event_date'
    day, evidence = dated
    for match in DAY_MONTH.finditer(title):
        other = date(int(match[3]) if match[3] else day.year,
                     MONTHS[match[2].lower()], int(match[1]))
        if other >= today and other != day:
            raise ValueError('multiple title dates need session extraction')
    for match in DAY_MONTH.finditer(body):
        other = date(int(match[3]) if match[3] else day.year,
                     MONTHS[match[2].lower()], int(match[1]))
        if other >= today and other != day:
            raise ValueError('additional future date needs session extraction')
    if day < today:
        return [], 'past'
    if (len(DAY_MONTH.findall(title)) > 1
            or re.search(r'\bprogramma\b|\bdal\s+\d{1,2}\s+al\s+\d{1,2}',
                         title, re.I)):
        raise ValueError('future multi-session programme needs session extraction')
    city = post_city(title, body)
    town = engine.fvg_municipality_catalog.match_names(city)
    if not town:
        raise ValueError('future announcement without verified municipality')
    times = {f'{int(hour):02d}:{int(minute or 0):02d}'
             for hour, minute in re.findall(
                 r'\b(?:ore|alle)\s+(\d{1,2})(?:[:.](\d{2}))?\b', body[:1800], re.I)}
    if len(times) > 1:
        raise ValueError('multiple unassigned times in future announcement')
    media = ContentMedia()
    media.feed(post['content']['rendered'])
    excerpt = next((paragraph for paragraph in media.paragraphs
                    if len(paragraph) >= 80), '')
    event = {'source': 'Pordenone Pensa', 'url': url, 'title': title,
             'start_date': day.isoformat(), 'end_date': day.isoformat(),
             'event_city': city, 'place': city,
             'location_confidence': 'municipality',
             'lat': town.latitude, 'lon': town.longitude,
             'date_evidence_kind': 'event_schedule',
             'date_evidence': evidence, 'is_real': True}
    if times:
        event['time'] = times.pop()
    if media.image:
        event['image'] = media.image
    event.update(attributed_excerpt(excerpt, source_name='Pordenone Pensa',
                                    source_url=url, title=title))
    invalid = validate_candidate(event, today=today)
    if invalid:
        raise ValueError('invalid Pordenone Pensa event: ' + ','.join(invalid))
    return [event], 'included'


def parse_programme(html, *, today):
    headings = re.findall(r'<h[12]\b[^>]*>(.*?)</h[12]>', html, re.S)
    if not any("2026" in clean(h) and "Pordenone" in clean(h) for h in headings):
        raise ValueError("edition not verified")
    slots = re.findall(r'<h4\b[^>]*>(.*?)</h4>\s*<h3\b[^>]*>(.*?)</h3>', html, re.S)
    if not slots:
        raise ValueError("unrecognized programme")
    town = engine.fvg_municipality_catalog.match_names("Pordenone")
    events, review = [], []
    for slot, title in slots:
        if schedule_notice(slot, title):
            review.append({'url': URL, 'title': clean(title), 'reason': 'schedule_change_requires_review'})
            continue
        text = clean(slot)
        match = re.search(r'\b(\d{1,2})\s+(\w+)\s+ore\s+(\d{1,2}[:.]\d{2})\s+(.+)', text, re.I)
        if not match or match[2].lower() not in MONTHS:
            raise ValueError("unrecognized session date")
        day = date(2026, MONTHS[match[2].lower()], int(match[1]))
        if not date(2026, 9, 5) <= day <= date(2026, 9, 7):
            raise ValueError("session outside verified edition")
        hour = datetime.strptime(match[3].replace('.', ':'), '%H:%M').strftime('%H:%M')
        if day < today:
            continue
        events.append({**programme_session_metadata(PORDENONE_PENSA_2026),
                       "source": "Pordenone Pensa", "url": URL, "title": clean(title),
                       "start_date": day.isoformat(), "end_date": day.isoformat(), "time": hour,
                       "event_city": "Pordenone", "place": match[4], "venue": match[4],
                       "location_confidence": "municipality", "lat": town.latitude, "lon": town.longitude,
                       "date_evidence_kind": "event_schedule", "date_evidence": text,
                       "is_real": True})
    return {"status": "ok", "events": events, "review_required": review, "coverage": "in-giallo-2026"}


def collect_pnpensa(*, get=requests.get, today=None):
    today = today or datetime.now(ZoneInfo('Europe/Rome')).date()

    def fetch(url, *, max_bytes):
        post_api = (re.escape(API) + r'\?per_page=100&page=\d+&_fields=' +
                    re.escape(FIELDS))
        page_api = (re.escape(PAGE_API) + r'\?per_page=100&_fields=' +
                    re.escape(PAGE_FIELDS))
        if (url not in {SITEMAP, PAGE_SITEMAP}
                and not re.fullmatch(post_api, url)
                and not re.fullmatch(page_api, url)):
            raise ValueError('untrusted Pordenone Pensa fetch URL')
        with get(url, timeout=(4, 15), stream=True, allow_redirects=False) as response:
            response.raise_for_status()
            if response.status_code != 200:
                raise ValueError('unexpected Pordenone Pensa response')
            chunks, size = [], 0
            for chunk in response.iter_content(65536):
                size += len(chunk)
                if size > max_bytes:
                    raise ValueError('oversized Pordenone Pensa response')
                chunks.append(chunk)
            return b''.join(chunks), response.headers

    sitemap_data, _ = fetch(SITEMAP, max_bytes=2*1024*1024)
    sitemap_urls = {
        item.text for item in ElementTree.fromstring(sitemap_data).findall(
            './/{http://www.sitemaps.org/schemas/sitemap/0.9}loc')}
    if not sitemap_urls or any(not trusted_post_url(url) for url in sitemap_urls):
        raise ValueError('invalid Pordenone Pensa post sitemap')
    posts, total = [], None
    for page in range(1, 11):
        url = f'{API}?per_page=100&page={page}&_fields={FIELDS}'
        raw, headers = fetch(url, max_bytes=8*1024*1024)
        page_total = int(headers['X-WP-Total'])
        page_count = int(headers['X-WP-TotalPages'])
        if (page_count < 1 or page_count > 10 or page_total < 1
                or page_total > 1000 or page_count != (page_total + 99) // 100
                or (total is not None and total != page_total)):
            raise ValueError('unstable Pordenone Pensa inventory')
        total = page_total
        batch = json.loads(raw.decode('utf-8-sig'))
        if not isinstance(batch, list) or len(batch) != min(100, total - len(posts)):
            raise ValueError('incomplete Pordenone Pensa API page')
        posts.extend(batch)
        if page == page_count:
            break
    if (len(posts) != total or len({post['id'] for post in posts}) != total
            or {post['link'] for post in posts} != sitemap_urls):
        raise ValueError('Pordenone Pensa API/sitemap mismatch')

    page_xml, _ = fetch(PAGE_SITEMAP, max_bytes=1024*1024)
    page_urls = {
        item.text for item in ElementTree.fromstring(page_xml).findall(
            './/{http://www.sitemaps.org/schemas/sitemap/0.9}loc')}
    page_raw, page_headers = fetch(
        f'{PAGE_API}?per_page=100&_fields={PAGE_FIELDS}', max_bytes=4*1024*1024)
    pages = json.loads(page_raw.decode('utf-8-sig'))
    if (not isinstance(pages, list) or not 1 <= len(pages) <= 100
            or int(page_headers['X-WP-Total']) != len(pages)
            or int(page_headers['X-WP-TotalPages']) != 1
            or len({page['id'] for page in pages}) != len(pages)
            or {page['link'] for page in pages} != page_urls
            or any(not trusted_page_url(url) for url in page_urls)):
        raise ValueError('Pordenone Pensa page API/sitemap mismatch')

    events, review, dispositions = [], [], []
    for post in posts:
        try:
            parsed, disposition = classify_post(post, today=today)
            events.extend(parsed)
        except (KeyError, TypeError, ValueError) as exc:
            disposition = 'review_required'
            review.append({'url': post.get('link'), 'reason': str(exc)})
        dispositions.append({'url': post.get('link'), 'disposition': disposition})
    for page in pages:
        content = clean(page['content']['rendered'])
        for match in DAY_MONTH.finditer(content):
            if (match[3] and date(int(match[3]), MONTHS[match[2].lower()],
                                  int(match[1])) >= today):
                review.append({'url': page['link'],
                               'reason': 'future date on static page needs review'})
                break
    events.sort(key=lambda item: (item['start_date'], item.get('time') or '',
                                  item['event_city'], item['title'], item['url']))
    proof = {'collection_mode': 'complete-pnpensa-post-api-and-sitemap',
             'sitemap_count': len(sitemap_urls), 'post_count': total,
             'page_sitemap_count': len(page_urls), 'page_count': len(pages),
             'page_records': [{'id': page['id'], 'url': page['link'],
                               'modified': page['modified']}
                              for page in pages],
             'post_records': [{'id': post['id'], 'url': post['link'],
                               'modified': post['modified']}
                              for post in posts],
             'detail_records': dispositions, 'event_count': len(events),
             'review_count': len(review), 'source_complete': True}
    return {'status': 'ok', 'events': events, 'review_required': review,
            'verification': proof, 'coverage': 'all-public-posts-and-pages-with-sitemaps'}


if __name__ == '__main__':
    result = collect_pnpensa()
    print({"events": len(result['events']), "coverage": result['coverage']})
