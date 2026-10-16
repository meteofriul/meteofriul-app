"""Read-only GiroFVG discovery watch; never publishes its editorial dates.

The sitemap catches changed articles, while all seven category archives catch
dated cards missing from the recent sitemap. A known historical HTTP 500 is
reported as incomplete coverage, never counted as a scanned page.
"""
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime
from html import unescape
from pathlib import Path
import json
import re
from threading import Lock, local
from urllib.parse import parse_qs, urljoin, urlsplit
import xml.etree.ElementTree as ET

import requests


BASE = 'https://www.girofvg.com'
INDEX = BASE + '/eventi'
SITEMAP = BASE + '/index.php?option=com_jmap&view=sitemap&format=xml'
CATEGORIES = (
    'enogastronomia', 'spettacoli-musica-e-rassegne',
    'visite-guidate-ed-escursioni', 'sport', 'fiere-e-mostre',
    'rievocazioni-storiche-e-folklore', 'altro',
)
BASELINE = Path(__file__).with_name('pilot_girofvg_baseline_2026.json')
SITEMAP_NS = {'s': 'http://www.sitemaps.org/schemas/sitemap/0.9'}
CARD = re.compile(r'<div\s+class="com-content-category-blog__item blog-item"[^>]*>', re.I)
FIELD = re.compile(r'<li\s+class="field-entry\s+([^"]+)"[^>]*>.*?'
                   r'<span\s+class="field-value[^"]*"[^>]*>(.*?)</span>', re.I | re.S)
TITLE = re.compile(r'<div\s+class="article-header"[^>]*>.*?'
                   r'<h2\b[^>]*>.*?<a\s+href="([^"]+)"[^>]*>(.*?)</a>', re.I | re.S)
PAGE_SIZE = 21
MIN_SITEMAP_URLS = 10000
MAX_SITEMAP_URLS = 20000
MIN_CATEGORY_PAGES = 70
MAX_CATEGORY_PAGES = 140
MAX_SITEMAP_BYTES = 5 * 1024 * 1024
MAX_HTML_BYTES = 2 * 1024 * 1024


def _text(markup):
    return ' '.join(unescape(re.sub(r'<[^>]*>', ' ', markup or '')).split())


def _same_host(url):
    parts = urlsplit(url)
    if parts.scheme != 'https' or parts.hostname != 'www.girofvg.com' or parts.fragment:
        raise ValueError('untrusted GiroFVG URL')
    return url


def _read_baseline():
    baseline = json.loads(BASELINE.read_text(encoding='utf-8'))
    if baseline.get('schema') != 'girofvg-watch-baseline-v1':
        raise ValueError('unexpected GiroFVG baseline schema')
    return baseline


def parse_sitemap(payload, today):
    if len(payload) > MAX_SITEMAP_BYTES:
        raise ValueError('oversized GiroFVG sitemap')
    root = ET.fromstring(payload)
    if root.tag != '{http://www.sitemaps.org/schemas/sitemap/0.9}urlset':
        raise ValueError('unexpected GiroFVG sitemap format')
    entries = {}
    for node in root.findall('s:url', SITEMAP_NS):
        url = _same_host(node.findtext('s:loc', default='', namespaces=SITEMAP_NS))
        modified = node.findtext('s:lastmod', default='', namespaces=SITEMAP_NS)
        if modified and not re.fullmatch(r'20\d{2}-\d{2}-\d{2}T[^<]+Z', modified):
            raise ValueError('invalid GiroFVG sitemap lastmod')
        if modified:
            try:
                datetime.fromisoformat(modified.replace('Z', '+00:00'))
            except ValueError as exc:
                raise ValueError('invalid GiroFVG sitemap timestamp') from exc
        if url in entries:
            raise ValueError('duplicate GiroFVG sitemap URL')
        entries[url] = modified
    if not MIN_SITEMAP_URLS <= len(entries) <= MAX_SITEMAP_URLS:
        raise ValueError('unexpected GiroFVG sitemap size')
    current = str(today.year)
    following = str(today.year + 1)
    recent = {url: modified for url, modified in entries.items()
              if modified[:4] >= current or current in url or following in url}
    return entries, recent


def parse_index_categories(markup):
    menu = re.search(r'href="/eventi"[^>]*>Eventi</a>.*?'
                     r'<ul\s+class="sp-dropdown-items"[^>]*>(.*?)</ul>',
                     markup, re.I | re.S)
    if not menu:
        raise ValueError('GiroFVG event menu missing')
    paths = {path for path in re.findall(r'href="/([a-z-]+)"', menu[1])}
    if paths != set(CATEGORIES):
        raise ValueError('GiroFVG event categories changed')
    return paths


def _page_start(href, category):
    parts = urlsplit(urljoin(BASE, href))
    if (parts.scheme != 'https' or parts.hostname != 'www.girofvg.com'
            or parts.path != '/' + category or parts.fragment):
        raise ValueError('unexpected GiroFVG pagination URL')
    if not parts.query:
        return 0
    params = parse_qs(parts.query)
    if set(params) != {'start'} or len(params['start']) != 1:
        raise ValueError('unexpected GiroFVG pagination parameters')
    start = int(params['start'][0])
    if start < PAGE_SIZE or start % PAGE_SIZE or start > 3000:
        raise ValueError('unexpected GiroFVG page offset')
    return start


def parse_listing(markup, category):
    markers = list(CARD.finditer(markup))
    if not 1 <= len(markers) <= PAGE_SIZE:
        raise ValueError('GiroFVG category has no cards or too many')
    cards = []
    for index, marker in enumerate(markers):
        block = markup[marker.end():markers[index + 1].start() if index + 1 < len(markers) else len(markup)]
        title = TITLE.search(block)
        if not title:
            raise ValueError('GiroFVG category card title missing')
        url = _same_host(urljoin(BASE, unescape(title[1])))
        fields = {key.strip(): _text(value) for key, value in FIELD.findall(block)}
        cards.append({'url': url, 'title': _text(title[2]),
                      'start': fields.get('data-inizio'),
                      'end': fields.get('data-fine'),
                      'place': fields.get('luogo')})
    end_link = re.search(r'aria-label="Vai alla pagina fine"\s+href="([^"]+)"', markup)
    if end_link:
        last_start = _page_start(unescape(end_link[1]), category)
    else:
        numbered = re.findall(r'aria-label="Vai alla pagina \d+"\s+href="([^"]+)"', markup)
        last_start = max((_page_start(unescape(href), category) for href in numbered), default=0)
    return cards, last_start


def _date(value):
    try:
        return datetime.strptime(value, '%d-%m-%Y').date()
    except (TypeError, ValueError):
        return None


def _fetch(get, url, *, xml=False):
    _same_host(url)
    with get(url, timeout=(4, 18), stream=True, allow_redirects=False,
             headers={'User-Agent': 'MeteoFriulEventsWatch/1.0'}) as response:
        status = response.status_code
        if status != 200:
            return status, b''
        content_type = response.headers.get('Content-Type', '').lower()
        if (xml and 'xml' not in content_type) or (not xml and 'html' not in content_type):
            raise ValueError('unexpected GiroFVG response type')
        cap = MAX_SITEMAP_BYTES if xml else MAX_HTML_BYTES
        chunks, size = [], 0
        for chunk in response.iter_content(65536):
            size += len(chunk)
            if size > cap:
                raise ValueError('oversized GiroFVG response')
            chunks.append(chunk)
        return status, b''.join(chunks)


def _expect_html(get, url):
    status, payload = _fetch(get, url)
    if status != 200:
        raise ValueError(f'GiroFVG HTTP {status}: {url}')
    return payload.decode('utf-8-sig')


def _collect(get, today, baseline):
    status, sitemap_payload = _fetch(get, SITEMAP, xml=True)
    if status != 200:
        raise ValueError(f'GiroFVG sitemap HTTP {status}')
    inventory, recent = parse_sitemap(sitemap_payload, today)
    if sorted(url for url, modified in inventory.items() if not modified) != baseline['sitemap_undated']:
        raise ValueError('GiroFVG sitemap pages without lastmod changed')
    parse_index_categories(_expect_html(get, INDEX))
    first_pages = {}
    page_urls = []
    last_starts = {}
    for category in CATEGORIES:
        url = BASE + '/' + category
        cards, last_start = parse_listing(_expect_html(get, url), category)
        if last_start and len(cards) != PAGE_SIZE:
            raise ValueError('incomplete GiroFVG first category page')
        first_pages[url] = cards
        last_starts[category] = last_start
        page_urls.extend(BASE + '/' + category + '?start=' + str(offset)
                         for offset in range(PAGE_SIZE, last_start + 1, PAGE_SIZE))
    expected = len(CATEGORIES) + len(page_urls)
    if not MIN_CATEGORY_PAGES <= expected <= MAX_CATEGORY_PAGES:
        raise ValueError('unexpected GiroFVG category page count')

    known_errors = set(baseline['known_page_errors'])
    missing = []
    by_category = {category: list(first_pages[BASE + '/' + category])
                   for category in CATEGORIES}

    def fetch_page(url):
        status, payload = _fetch(get, url)
        if status == 500 and url in known_errors:
            return url, None
        if status != 200:
            raise ValueError(f'GiroFVG archive HTTP {status}: {url}')
        category = urlsplit(url).path.lstrip('/')
        cards, _ = parse_listing(payload.decode('utf-8-sig'), category)
        offset = _page_start(url, category)
        if offset < last_starts[category] and len(cards) != PAGE_SIZE:
            raise ValueError('incomplete GiroFVG category page')
        return url, cards

    with ThreadPoolExecutor(max_workers=4) as pool:
        for url, cards in pool.map(fetch_page, page_urls):
            if cards is None:
                missing.append(url)
            else:
                by_category[urlsplit(url).path.lstrip('/')].extend(cards)
    for category in CATEGORIES:
        url = BASE + '/' + category
        cards, last_start = parse_listing(_expect_html(get, url), category)
        if cards != first_pages[url] or last_start != last_starts[category]:
            raise ValueError('GiroFVG category changed while paging')
    end_status, end_sitemap = _fetch(get, SITEMAP, xml=True)
    if end_status != 200 or parse_sitemap(end_sitemap, today)[0] != inventory:
        raise ValueError('GiroFVG sitemap changed while paging')
    for category, cards in by_category.items():
        urls = [card['url'] for card in cards]
        if len(urls) != len(set(urls)):
            raise ValueError('duplicate GiroFVG category card: ' + category)

    category_cards = {}
    for cards in by_category.values():
        for card in cards:
            old = category_cards.get(card['url'])
            if old and old != card:
                raise ValueError('conflicting GiroFVG category cards')
            category_cards[card['url']] = card

    changes = []
    reviewed = baseline['active_cards']
    past_undated = baseline['known_past_undated_cards']
    for card in category_cards.values():
        start, end = _date(card['start']), _date(card['end'])
        if (not start or not end) and str(today.year) in (card['title'] + card['url']):
            known_end = past_undated.get(card['url'])
            if (known_end and today > date.fromisoformat(known_end)
                    and inventory.get(card['url']) == baseline['sitemap_recent'].get(card['url'])):
                continue
            changes.append({'reason': 'unreadable_current_card', 'url': card['url']})
            continue
        if not end or end < today:
            continue
        if not start or start > end or not card['place']:
            changes.append({'reason': 'incomplete_active_card', 'url': card['url']})
            continue
        if card['url'] not in inventory:
            changes.append({'reason': 'active_card_missing_from_sitemap', 'url': card['url']})
        expected_card = reviewed.get(card['url'])
        actual = {'start': card['start'], 'end': card['end'], 'place': card['place']}
        if expected_card != actual:
            changes.append({'reason': 'new_or_changed_active_card',
                            'url': card['url'], 'observed': actual})

    previous_recent = baseline['sitemap_recent']
    for url in baseline['category_active_urls']:
        reviewed_end = _date((reviewed.get(url) or {}).get('end'))
        if reviewed_end and reviewed_end >= today and url not in category_cards:
            changes.append({'reason': 'reviewed_future_card_disappeared', 'url': url})
    for url, reviewed_card in reviewed.items():
        reviewed_end = _date(reviewed_card.get('end'))
        if reviewed_end and reviewed_end >= today and url not in inventory:
            changes.append({'reason': 'reviewed_future_article_disappeared', 'url': url})
    changed_recent = {url: stamp for url, stamp in recent.items()
                      if previous_recent.get(url) != stamp}
    if len(changed_recent) > 30:
        raise ValueError('too many changed GiroFVG sitemap entries')
    for url, modified in changed_recent.items():
        if url in category_cards:
            changes.append({'reason': 'new_or_changed_category_article',
                            'url': url, 'modified': modified})
            continue
        markup = _expect_html(get, url)
        fields = {key.strip(): _text(value) for key, value in FIELD.findall(markup)}
        if any(key in fields for key in ('data-inizio', 'data-fine', 'luogo')):
            changes.append({'reason': 'new_or_changed_dated_article',
                            'url': url, 'modified': modified})

    deduped = {item['url'] + ':' + item['reason']: item for item in changes}
    return {'source_complete': not missing,
            'sitemap_urls': len(inventory), 'recent_sitemap_urls': len(recent),
            'category_pages_expected': expected,
            'category_pages_read': expected - len(missing),
            'category_cards': sum(len(cards) for cards in by_category.values()),
            'known_page_errors': sorted(missing),
            'changes': list(deduped.values())}


def collect_watch(today=None, *, get=None, baseline=None):
    today = today or date.today()
    baseline = baseline or _read_baseline()
    if get is not None:
        return _collect(get, today, baseline)
    sessions = []
    lock = Lock()
    state = local()

    def session_get(url, **kwargs):
        if not hasattr(state, 'session'):
            state.session = requests.Session()
            with lock:
                sessions.append(state.session)
        return state.session.get(url, **kwargs)

    try:
        return _collect(session_get, today, baseline)
    finally:
        for session in sessions:
            session.close()
