"""Magazzino delle Idee: complete event API plus public lists and sitemap."""
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime
from html import unescape
import json
import re
from urllib.parse import urlsplit
from xml.etree import ElementTree
from zoneinfo import ZoneInfo

import requests

from . import engine
from .pilot_excerpt import attributed_excerpt
from .pilot_source_policy import validate_candidate
from .pilot_villa_manin import _links
from .sources.villa_manin import _ElementorTextExtractor, _SINGLE_DATE_RE, _MONTHS, _search_text


BASE = 'https://magazzinodelleidee.it'
API = BASE + '/wp-json/wp/v2/evento'
MOSTRE = BASE + '/mostre/'
EVENTI = BASE + '/eventi/'
SITEMAP = BASE + '/evento-sitemap.xml'
NS = '{http://www.sitemaps.org/schemas/sitemap/0.9}'
_NUMERIC_RANGE = re.compile(
    r'\b(?:dal\s+)?(?P<d1>\d{1,2})[./](?P<m1>\d{1,2})'
    r'(?:[./](?P<y1>20\d{2}))?\s*(?:-|–|—|al|all)\s*'
    r'(?P<d2>\d{1,2})[./](?P<m2>\d{1,2})[./](?P<y2>20\d{2})\b', re.I)


def event_url(value):
    path = urlsplit(str(value or ''))
    if (path.scheme != 'https' or path.hostname not in {
            'magazzinodelleidee.it', 'www.magazzinodelleidee.it'}
            or path.username or path.password or path.port or path.query or path.fragment
            or not re.fullmatch(r'/evento/[a-z0-9-]+/?', path.path)):
        return None
    return BASE + path.path.rstrip('/') + '/'


def image_url(value):
    path = urlsplit(str(value or ''))
    return (str(value) if path.scheme == 'https'
            and path.hostname in {'magazzinodelleidee.it', 'www.magazzinodelleidee.it'}
            and path.path.startswith('/wp-content/uploads/')
            and not (path.query or path.fragment or path.username or path.password or path.port)
            else None)


def _years(row):
    embedded = row.get('_embedded') or {}
    groups = embedded.get('wp:term') or []
    return {int(term['name']) for group in groups for term in group
            if term.get('taxonomy') == 'anno'
            and re.fullmatch(r'20\d{2}', str(term.get('name') or ''))}


def _date_heading(headings):
    for heading in headings[:8]:
        text = _search_text(heading)
        match = _NUMERIC_RANGE.search(text)
        if match:
            start = date(int(match['y1'] or match['y2']), int(match['m1']), int(match['d1']))
            end = date(int(match['y2']), int(match['m2']), int(match['d2']))
            if end < start:
                raise ValueError('inverted Magazzino dates')
            return start, end, heading
        match = _SINGLE_DATE_RE.search(text)
        if match:
            day = date(int(match['year']), _MONTHS[match['month']], int(match['day']))
            return day, day, heading
    raise ValueError('Magazzino event date missing')


def _listed_exhibition_matches(html, candidate):
    blocks = _ElementorTextExtractor()
    blocks.feed(html)
    expected_title = re.sub(r'\W+', ' ', _search_text(candidate['title'])).strip()
    for index, (tag, value) in enumerate(blocks.blocks):
        if (tag not in {'h1', 'h2', 'h3'}
                or re.sub(r'\W+', ' ', _search_text(value)).strip() != expected_title):
            continue
        for next_tag, next_value in blocks.blocks[index + 1:index + 3]:
            if next_tag != 'p':
                break
            try:
                start, end, _ = _date_heading([next_value])
            except ValueError:
                continue
            return (start.isoformat() == candidate['start_date']
                    and end.isoformat() == candidate['end_date'])
        return False
    return False


def parse_event(row, *, today):
    if (not isinstance(row, dict) or row.get('status') != 'publish'
            or row.get('type') != 'evento' or not isinstance(row.get('id'), int)
            or not isinstance(row.get('title'), dict)
            or not isinstance(row.get('content'), dict)):
        raise ValueError('invalid Magazzino API record')
    url = event_url(row.get('link'))
    title = unescape(str(row['title'].get('rendered') or '')).strip()
    html = row['content'].get('rendered')
    if not url or not title or not isinstance(html, str):
        raise ValueError('incomplete Magazzino API record')
    blocks = _ElementorTextExtractor()
    blocks.feed(html)
    start, end, evidence = _date_heading(blocks.headings)
    if end < today:
        return None
    if not blocks.headings or not blocks.paragraphs:
        raise ValueError('Magazzino detail text missing')
    subtitle = blocks.headings[0]
    name = title if _search_text(subtitle) == _search_text(title) else title + ' - ' + subtitle
    description = next((paragraph for paragraph in blocks.paragraphs
                        if len(paragraph) >= 40), '')
    if not description:
        raise ValueError('Magazzino event description missing')
    content_search = _search_text(' '.join(blocks.paragraphs[:4]))
    if ('magazzino delle idee' not in content_search or 'trieste' not in content_search):
        raise ValueError('Magazzino venue or city not explicit')
    media = (row.get('_embedded') or {}).get('wp:featuredmedia') or []
    image = image_url(media[0].get('source_url')) if media and isinstance(media[0], dict) else None
    if row.get('featured_media') and not image:
        raise ValueError('Magazzino featured image unavailable or untrusted')
    town = engine.fvg_municipality_catalog.match_names('Trieste')
    candidate = {
        'source': 'Magazzino delle Idee', 'source_id': str(row['id']),
        'title': name, 'url': url, 'start_date': start.isoformat(),
        'end_date': end.isoformat(), 'event_city': 'Trieste',
        'venue': 'Magazzino delle Idee', 'place': 'Magazzino delle Idee, Trieste',
        'lat': town.latitude, 'lon': town.longitude,
        'location_confidence': 'municipality', 'image': image,
        'date_evidence_kind': 'event_schedule', 'date_evidence': evidence,
        'schedule_kind': 'period' if start != end else 'single', 'is_real': True,
        **attributed_excerpt(description, source_name='Magazzino delle Idee',
                             source_url=url, title=name),
    }
    invalid = validate_candidate(candidate, today=today)
    if invalid:
        raise ValueError('invalid Magazzino event: ' + ','.join(invalid))
    return candidate


def _detail_matches(html, row, candidate):
    blocks = _ElementorTextExtractor()
    blocks.feed(html)
    if not blocks.headings or _search_text(blocks.headings[0]) != _search_text(
            unescape(row['title']['rendered'])):
        return False
    try:
        start, end, _ = _date_heading(blocks.headings)
    except ValueError:
        return False
    return (start.isoformat() == candidate['start_date']
            and end.isoformat() == candidate['end_date']
            and candidate.get('description_excerpt', '')[:70].casefold()
                in ' '.join(blocks.paragraphs).casefold())


def collect_magazzino(*, get=requests.get, today=None):
    today = today or datetime.now(ZoneInfo('Europe/Rome')).date()

    def fetch(url, *, max_bytes=8 * 1024 * 1024):
        allowed = (url in {MOSTRE, EVENTI, SITEMAP, BASE + f'/anno/{today.year}/'}
                   or re.fullmatch(re.escape(API) + r'\?_embed=1&per_page=100&page=\d+', url)
                   or re.fullmatch(re.escape(EVENTI) + r'\d+/', url)
                   or event_url(url) == url)
        if not allowed:
            raise ValueError('untrusted Magazzino URL')
        with get(url, timeout=(4, 15), stream=True, allow_redirects=False) as response:
            response.raise_for_status()
            if response.status_code != 200:
                raise ValueError('unexpected Magazzino redirect')
            chunks, size = [], 0
            for chunk in response.iter_content(65536):
                size += len(chunk)
                if size > max_bytes:
                    raise ValueError('oversized Magazzino response')
                chunks.append(chunk)
            return b''.join(chunks).decode('utf-8-sig'), response.headers

    def api_page(page):
        body, headers = fetch(f'{API}?_embed=1&per_page=100&page={page}')
        return json.loads(body), headers

    first, headers = api_page(1)
    total, page_count = int(headers['X-WP-Total']), int(headers['X-WP-TotalPages'])
    if (not isinstance(first, list) or not 1 <= total <= 2000
            or not 1 <= page_count <= 20 or page_count != (total + 99) // 100
            or len(first) != min(100, total)):
        raise ValueError('invalid Magazzino API pagination')
    pages = [(first, headers)]
    if page_count > 1:
        with ThreadPoolExecutor(max_workers=3) as pool:
            pages.extend(pool.map(api_page, range(2, page_count + 1)))
    rows = []
    for number, (page_rows, page_headers) in enumerate(pages, 1):
        if (not isinstance(page_rows, list)
                or int(page_headers['X-WP-Total']) != total
                or int(page_headers['X-WP-TotalPages']) != page_count
                or len(page_rows) != min(100, total - (number - 1) * 100)):
            raise ValueError('incomplete Magazzino API page')
        rows.extend(page_rows)
    api_urls = [event_url(row.get('link')) for row in rows if isinstance(row, dict)]
    ids = [row.get('id') for row in rows if isinstance(row, dict)]
    if (len(rows) != total or len(api_urls) != total or None in api_urls
            or None in ids
            or len(set(api_urls)) != total or len(set(ids)) != total):
        raise ValueError('duplicate or missing Magazzino API record')
    by_url = dict(zip(api_urls, rows))

    with ThreadPoolExecutor(max_workers=4) as pool:
        mostre, annual, sitemap, first_list = list(pool.map(
            lambda url: fetch(url)[0],
            (MOSTRE, BASE + f'/anno/{today.year}/', SITEMAP, EVENTI)))
    annual_urls = {event_url(link) for link in _links(annual) if event_url(link)}
    annual_api = {event_url(row['link']) for row in rows if today.year in _years(row)}
    if not annual_api or annual_urls != annual_api:
        raise ValueError('Magazzino year archive/API mismatch')
    xml = ElementTree.fromstring(sitemap)
    sitemap_entries = [node.findtext(NS + 'loc') for node in xml.findall(NS + 'url')]
    sitemap_urls = [event_url(url) for url in sitemap_entries]
    if (not sitemap_entries or None in sitemap_urls
            or set(sitemap_urls) != set(api_urls)):
        raise ValueError('Magazzino sitemap/API mismatch')

    queue = [EVENTI]
    list_html = {EVENTI: first_list}
    while queue:
        url = queue.pop(0)
        html = list_html[url]
        for link in _links(html):
            if re.fullmatch(re.escape(EVENTI) + r'\d+/', link) and link not in list_html:
                if len(list_html) >= 10:
                    raise ValueError('Magazzino events pagination limit')
                list_html[link] = fetch(link)[0]
                queue.append(link)
    list_urls = {event_url(link) for html in list_html.values() for link in _links(html)
                 if event_url(link)}
    mostre_urls = {event_url(link) for link in _links(mostre) if event_url(link)}
    if not list_urls or not mostre_urls or not (list_urls | mostre_urls) <= set(api_urls):
        raise ValueError('Magazzino public list/API mismatch')

    candidates, current_past, archived, review = [], 0, 0, []
    exhibition_dates_checked = 0
    for row in rows:
        url = event_url(row['link'])
        if any(year >= today.year for year in _years(row)):
            try:
                candidate = parse_event(row, today=today)
                if candidate:
                    if url not in list_urls | mostre_urls:
                        raise ValueError('active Magazzino event missing from public lists')
                    terms = (row.get('_embedded') or {}).get('wp:term') or []
                    is_exhibition = any(
                        term.get('taxonomy') == 'tipologia'
                        and _search_text(term.get('name')) == 'mostra'
                        for group in terms for term in group)
                    if is_exhibition:
                        if (url not in mostre_urls
                                or not _listed_exhibition_matches(mostre, candidate)):
                            raise ValueError('exhibition listing date or title mismatch')
                        exhibition_dates_checked += 1
                    candidates.append(candidate)
                else:
                    current_past += 1
            except ValueError as exc:
                review.append({'url': url, 'reason': str(exc)})
        elif str(row.get('modified') or '') >= '2026-10-07T00:00:00':
            review.append({'url': url, 'reason': 'changed legacy record requires review'})
        else:
            archived += 1
    if not review:
        with ThreadPoolExecutor(max_workers=3) as pool:
            details = list(pool.map(lambda event: fetch(event['url'])[0], candidates))
        for candidate, html in zip(candidates, details):
            if not _detail_matches(html, by_url[candidate['url']], candidate):
                review.append({'url': candidate['url'], 'reason': 'detail date or text mismatch'})
    if review:
        candidates = []
    candidates.sort(key=lambda item: (item['start_date'], item['title']))
    proof = {'collection_mode': 'complete-magazzino-api-sitemap-and-public-lists',
             'source_complete': not review, 'records_scanned': total,
             'api_pages': page_count, 'sitemap_entries': len(sitemap_entries),
             'sitemap_unique': len(set(sitemap_urls)),
             'year_archive_count': len(annual_urls),
             'event_list_pages': len(list_html), 'event_list_urls': len(list_urls),
             'exhibition_urls': len(mostre_urls),
             'exhibition_dates_checked': exhibition_dates_checked,
             'current_past': current_past,
             'archived': archived, 'active_count': len(candidates),
             'detail_count': len(candidates) if not review else 0,
             'review_count': len(review)}
    return {'status': 'ok' if not review else 'error',
            'error_type': None if not review else 'incomplete_source',
            'events': candidates, 'review_required': review, 'verification': proof,
            'coverage': 'complete-event-api-and-sitemap-with-year-and-list-reconciliation'}
