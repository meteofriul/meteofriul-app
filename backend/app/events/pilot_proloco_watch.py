"""Read-only Pro Loco index watch against the verified TurismoFVG catalog.

Pro Loco currently repeats regional events and sometimes omits dates in its
detail sidebar. The watch reads only paginated listing HTML. A new or changed
listing without a unique regional counterpart is reported for review; it never
publishes a second event card or reads images, posters, or PDF files.
"""

from datetime import date
from html.parser import HTMLParser
import re
import unicodedata
from urllib.parse import urljoin, urlsplit, urlunsplit

import requests


BASE = 'https://prolocoregionefvg.it'
INDEX = BASE + '/eventi-delle-associate/'
MAX_BYTES = 2 * 1024 * 1024
MONTHS = {'gen': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'mag': 5, 'giu': 6,
          'lug': 7, 'ago': 8, 'set': 9, 'ott': 10, 'nov': 11, 'dic': 12}
FULL_MONTHS = {'gennaio': 1, 'febbraio': 2, 'marzo': 3, 'aprile': 4,
               'maggio': 5, 'giugno': 6, 'luglio': 7, 'agosto': 8,
               'settembre': 9, 'ottobre': 10, 'novembre': 11, 'dicembre': 12}
DATE_RE = re.compile(r'\b(\d{1,2})\s+(' + '|'.join((*FULL_MONTHS, *MONTHS)) +
                     r')\b(?:\s+(20\d{2}))?')
REVIEWED_ALIASES = {
    '/eventi-delle-associate/farine-di-flor-formandi/': '/eventi/formandi-il-sapore-delle-malghe',
    '/eventi-delle-associate/halloween-party-4/': '/eventi/halloween-party-2026',
}


def _plain(value):
    value = unicodedata.normalize('NFKD', value or '')
    value = ''.join(char for char in value if not unicodedata.combining(char))
    return ' '.join(re.findall(r'[a-z0-9]+', value.casefold()))


def _url(value):
    parts = urlsplit(urljoin(BASE, value))
    if parts.scheme != 'https' or parts.netloc != 'prolocoregionefvg.it' or not parts.path.startswith('/eventi-delle-associate/'):
        raise ValueError('unexpected Pro Loco listing URL')
    return urlunsplit(('https', parts.netloc, parts.path, '', ''))


class _Listing(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.cards = []
        self.pages = set()
        self.card = None
        self.capture = None
        self.buffer = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        href = attrs.get('href', '')
        if tag == 'a' and re.search(r'[?&]page=\d+\b', href):
            self.pages.add(urljoin(INDEX, href))
        if tag == 'a' and 'card' in attrs.get('class', '').split() and self.card is None:
            self.card = {'url': _url(href), 'headings': [], 'title': ''}
        elif tag == 'h3' and self.card is not None:
            self.capture = 'title' if 'card-title' in attrs.get('class', '').split() else 'headings'
            self.buffer = []

    def handle_data(self, data):
        if self.capture:
            self.buffer.append(data)

    def handle_endtag(self, tag):
        if tag == 'h3' and self.capture and self.card is not None:
            value = ' '.join(''.join(self.buffer).split())
            if self.capture == 'title':
                self.card['title'] = value
            else:
                self.card['headings'].append(value)
            self.capture = None
            self.buffer = []
        elif tag == 'a' and self.card is not None:
            if len(self.card['headings']) != 2 or not self.card['title']:
                raise ValueError('Pro Loco card markup changed')
            self.card['city'], self.card['date_text'] = self.card.pop('headings')
            self.cards.append(self.card)
            self.card = None


def parse_listing(markup):
    parser = _Listing()
    parser.feed(markup)
    parser.close()
    if not parser.cards:
        raise ValueError('Pro Loco listing has no cards')
    return parser.cards, parser.pages


def _fetch(url):
    _url(url)
    with requests.get(url, timeout=(3, 12), stream=True, allow_redirects=False,
                      headers={'User-Agent': 'MeteoFriulEventsWatch/1.0'}) as response:
        response.raise_for_status()
        if response.status_code != 200 or 'text/html' not in response.headers.get('Content-Type', ''):
            raise ValueError('unexpected Pro Loco index response')
        chunks, size = [], 0
        for chunk in response.iter_content(65536):
            size += len(chunk)
            if size > MAX_BYTES:
                raise ValueError('oversized Pro Loco index')
            chunks.append(chunk)
        return b''.join(chunks).decode('utf-8', errors='replace')


def collect_index():
    pages, cards, page_url = [], [], INDEX
    while page_url:
        if page_url in pages or len(pages) >= 30:
            raise ValueError('Pro Loco pagination loop or excessive depth')
        page_cards, page_links = parse_listing(_fetch(page_url))
        pages.append(page_url)
        cards.extend(page_cards)
        expected = len(pages) + 1
        next_pages = [url for url in page_links if re.search(r'[?&]page=' + str(expected) + r'\b', url)]
        if any(re.search(r'[?&]page=(\d+)\b', url) and int(re.search(r'[?&]page=(\d+)\b', url).group(1)) > expected
               for url in page_links):
            raise ValueError('Pro Loco pagination gap')
        page_url = next_pages[0] if next_pages else None
    if len({(card['url'], card['date_text']) for card in cards}) != len(cards):
        raise ValueError('duplicate Pro Loco listing occurrence')
    return {'pages': len(pages), 'cards': cards, 'distinct_urls': len({card['url'] for card in cards})}


def _dates(value, today):
    found = DATE_RE.findall(_plain(value))
    if not found or len(found) > 2:
        raise ValueError('unreadable Pro Loco listing date')
    dates = []
    for day, month, year_text in found:
        month_number = FULL_MONTHS.get(month) or MONTHS.get(month)
        year = int(year_text) if year_text else today.year + (month_number < today.month)
        dates.append(date(year, month_number, int(day)))
    if dates != sorted(dates):
        raise ValueError('reversed Pro Loco date range')
    return dates[0].isoformat(), dates[-1].isoformat()


def watch_changes(index, tourism_events, today, *, window_end=None):
    """Return uncovered listing items in the verified publication window."""
    if not isinstance(index, dict) or not isinstance(tourism_events, list):
        raise ValueError('invalid Pro Loco watch input')
    changes = []
    for card in index['cards']:
        start, end = _dates(card['date_text'], today)
        if window_end is not None and (end < today.isoformat()
                                       or start > window_end.isoformat()):
            continue
        matches = []
        for event in tourism_events:
            if (_plain(card['city']) != _plain(event.get('event_city'))
                    or not event.get('start_date') or not event.get('end_date')
                    or not event['start_date'] <= start <= end <= event['end_date']):
                continue
            exact_title = _plain(card['title']) == _plain(event.get('title'))
            alias = (REVIEWED_ALIASES.get(urlsplit(card['url']).path)
                     == urlsplit(event.get('url') or '').path)
            if exact_title or alias:
                matches.append(event.get('url'))
        if len(set(matches)) != 1:
            changes.append({'url': card['url'], 'title': card['title'],
                            'city': card['city'], 'date': card['date_text'],
                            'reason': 'uncovered' if not matches else 'ambiguous'})
    return changes
