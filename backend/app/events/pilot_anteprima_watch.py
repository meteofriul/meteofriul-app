"""Read-only watch for dated future posts on Anteprima Sagre.

The site has editorial WordPress posts, not structured event dates. This
monitor inventories public posts modified in the current or preceding year
and flags explicit future calendar dates for source-specific review. It does
not infer dates from annual recurrence or publish an event card.
"""

from datetime import date, timedelta
from html.parser import HTMLParser
import hashlib
import json
import math
import re
from time import sleep

import requests


API = 'https://www.anteprimasagre.it/wp-json/wp/v2/posts'
MONTHS = {name: number for number, name in enumerate((
    'gennaio', 'febbraio', 'marzo', 'aprile', 'maggio', 'giugno',
    'luglio', 'agosto', 'settembre', 'ottobre', 'novembre', 'dicembre'), 1)}
TEXT_DATE = re.compile(r'\b(\d{1,2})\s+(' + '|'.join(MONTHS) + r')\s+(20\d{2})\b', re.I)
NUMERIC_DATE = re.compile(r'\b(\d{1,2})[./-](\d{1,2})[./-](20\d{2})\b')
MAX_PAGES = 12
MAX_BYTES_PER_PAGE = 2 * 1024 * 1024
# The site's public robots.txt asks all crawlers to wait 10 seconds.
CRAWL_DELAY_SECONDS = 10
KNOWN_UNDATED = {
    3673: ('2026-09-10T11:54:06',
           '85909903928a48647b98491dc3e6be5f25a3eb4c952de42b0fa5593243faf159'),
}
YEARLESS_DATE = re.compile(r'\b(\d{1,2})\s+(' + '|'.join(MONTHS) +
                           r')\b(?!\s+20\d{2})', re.I)


class AnteprimaChallengeError(ValueError):
    """The origin returned a CAPTCHA instead of the public inventory."""


class _Text(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.ignored = 0

    def handle_starttag(self, tag, attrs):
        if tag in {'script', 'style'}:
            self.ignored += 1

    def handle_endtag(self, tag):
        if tag in {'script', 'style'} and self.ignored:
            self.ignored -= 1

    def handle_data(self, data):
        if not self.ignored:
            self.parts.append(data)


def _plain(markup):
    parser = _Text()
    parser.feed(markup or '')
    parser.close()
    return ' '.join(' '.join(parser.parts).split())


def future_dates(content, today):
    """Use only explicit day, month and year; publication dates are irrelevant."""
    value = _plain(content).casefold()
    dates = set()
    for day, month, year in TEXT_DATE.findall(value):
        try:
            parsed = date(int(year), MONTHS[month], int(day))
            if parsed >= today:
                dates.add(parsed.isoformat())
        except ValueError:
            continue
    for day, month, year in NUMERIC_DATE.findall(value):
        try:
            parsed = date(int(year), int(month), int(day))
            if parsed >= today:
                dates.add(parsed.isoformat())
        except ValueError:
            continue
    return sorted(dates)


def future_yearless_dates(content, today):
    """Flag recent articles with a plausible date but no year to prove it."""
    value = _plain(content).casefold()
    dates = set()
    for day, month in YEARLESS_DATE.findall(value):
        try:
            parsed = date(today.year, MONTHS[month], int(day))
            if parsed >= today:
                dates.add(parsed.isoformat())
        except ValueError:
            continue
    return sorted(dates)


def _fetch(params):
    with requests.get(API, params=params, timeout=(3, 18), stream=True,
                      allow_redirects=False,
                      headers={'User-Agent': 'MeteoFriulEventsWatch/1.0'}) as response:
        response.raise_for_status()
        if response.status_code != 200 or 'application/json' not in response.headers.get('Content-Type', ''):
            # A 202 HTML page is not an empty WordPress result. Keep enough
            # metadata to identify the upstream response without logging its body.
            prefix = next(response.iter_content(4096), b'')[:4096]
            title = re.search(rb'<title[^>]*>(.*?)</title>', prefix, re.I | re.S)
            safe_title = re.sub(r'\s+', ' ', title.group(1).decode('utf-8', 'replace')).strip()[:100] if title else ''
            lower = prefix.lower()
            markers = [marker for marker in ('captcha', 'challenge', 'imunify',
                       'cloudflare', 'sucuri', 'javascript', 'cookie', 'bot')
                       if marker.encode() in lower]
            header_names = sorted(name.lower() for name in response.headers
                                  if name.lower() != 'set-cookie')
            error_type = (AnteprimaChallengeError if response.status_code == 202
                          and ('sg-captcha' in {name.lower() for name in response.headers}
                               or 'captcha' in markers) else ValueError)
            raise error_type(
                'unexpected Anteprima Sagre API response: '
                f'http={response.status_code} '
                f'content_type={response.headers.get("Content-Type", "")[:80]} '
                f'server={response.headers.get("Server", "")[:80]} '
                f'title={safe_title} body_bytes={len(prefix)} '
                f'body_sha256={hashlib.sha256(prefix).hexdigest()[:12]} '
                f'markers={markers} headers={header_names}')
        chunks, size = [], 0
        for chunk in response.iter_content(65536):
            size += len(chunk)
            if size > MAX_BYTES_PER_PAGE:
                raise ValueError('oversized Anteprima Sagre API page')
            chunks.append(chunk)
        return json.loads(b''.join(chunks)), response.headers


def collect_watch(today):
    """Reconcile REST pagination, excluding the site's members-only category."""
    params = {
        'per_page': 100,
        'modified_after': f'{today.year - 1}-01-01T00:00:00',
        'categories_exclude': 6145,
        '_fields': 'id,date,modified,link,title,categories,content',
    }
    first, headers = _fetch({**params, 'page': 1})
    total = int(headers['X-WP-Total'])
    total_pages = int(headers['X-WP-TotalPages'])
    if (not 1 <= total_pages <= MAX_PAGES or total_pages != math.ceil(total / 100)
            or not isinstance(first, list)):
        raise ValueError('invalid Anteprima Sagre inventory count')
    posts = list(first)
    for page in range(2, total_pages + 1):
        sleep(CRAWL_DELAY_SECONDS)
        rows, page_headers = _fetch({**params, 'page': page})
        if (not isinstance(rows, list) or int(page_headers['X-WP-Total']) != total
                or int(page_headers['X-WP-TotalPages']) != total_pages):
            raise ValueError('Anteprima Sagre inventory changed while paging')
        posts.extend(rows)
    ids = [post.get('id') for post in posts if isinstance(post, dict)]
    if (len(posts) != total or len(ids) != total or len(set(ids)) != total
            or any(not isinstance(ident, int) for ident in ids)):
        raise ValueError('incomplete Anteprima Sagre inventory')
    candidates, undated = [], []
    for post in posts:
        if 6145 in post.get('categories', []):
            raise ValueError('members-only Anteprima Sagre post exposed in public inventory')
        dates = future_dates((post.get('content') or {}).get('rendered'), today)
        if dates:
            candidates.append({'id': post['id'], 'url': post.get('link'),
                               'title': _plain((post.get('title') or {}).get('rendered')),
                               'modified': post.get('modified'), 'dates': dates})
        elif (post.get('modified') or '')[:10] >= (today - timedelta(days=90)).isoformat() \
                and str(today.year) in _plain((post.get('content') or {}).get('rendered')):
            rendered = (post.get('content') or {}).get('rendered') or ''
            yearless = future_yearless_dates(rendered, today)
            if yearless:
                fingerprint = hashlib.sha256(rendered.encode('utf-8')).hexdigest()
                undated.append({'id': post['id'], 'url': post.get('link'),
                                'modified': post.get('modified'), 'possible_dates': yearless,
                                'known_pending': KNOWN_UNDATED.get(post['id'])
                                == (post.get('modified'), fingerprint)})
    return {'posts': total, 'pages': total_pages,
            'future_candidates': candidates, 'undated_candidates': undated}
