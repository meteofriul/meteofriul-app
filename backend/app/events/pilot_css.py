"""CSS official season indexes and event details for the pilot catalogue."""
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta
from html import escape
from html.parser import HTMLParser
import re
from threading import Lock, local
from urllib.parse import urljoin, urlsplit
from zoneinfo import ZoneInfo
import requests
from .pilot_azalea import clean
from .pilot_excerpt import attributed_excerpt
from .pilot_source_policy import validate_candidate
from .pilot_verdi_pordenone import MONTHS
from . import engine
from .pilot_schedule import require_schedule_review

BASE = "https://www.cssudine.it/"
SEASON_PATHS = ('', 'stagione-contatto', 'stagione-festil',
                'stagione-pasolini', 'stagione-tig', 'stagione-tig-in-famiglia')
EVENT_PATH = re.compile(r'/stagione-[^/]+/20\d{2}/\d+/[^/#]+')


def trusted_event_url(url):
    parsed = urlsplit(str(url or ''))
    return (parsed.scheme == 'https' and parsed.hostname == 'www.cssudine.it'
            and EVENT_PATH.fullmatch(parsed.path) is not None
            and not parsed.query and not parsed.fragment)


class SeasonCards(HTMLParser):
    """Only programme cards, never menu, press article or related links."""
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.cards = []
        self.depth = 0
        self.card = None
        self.capture = None
        self.linked_event_ids = set()
        self.linked_event_urls = {}

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        classes = set((values.get('class') or '').split())
        if tag == 'a':
            linked = urljoin(BASE, values.get('href') or '')
            if trusted_event_url(linked):
                event_id = urlsplit(linked).path.split('/')[3]
                self.linked_event_ids.add(event_id)
                self.linked_event_urls.setdefault(event_id, linked)
        if tag == 'div':
            self.depth += 1
            if 'news-v1' in classes and self.card is None:
                self.card = {'depth': self.depth, 'url': '', 'title': '',
                             'schedule': '', 'venue': ''}
        if self.card is None:
            return
        if tag == 'h3':
            self.capture = 'title'
        elif tag == 'span' and 'data' in classes:
            self.capture = 'schedule'
        elif tag == 'span' and 'venue' in classes:
            self.capture = 'venue'
        elif tag == 'a' and self.capture == 'title':
            self.card['url'] = urljoin(BASE, values.get('href') or '')
        elif tag == 'br' and self.capture:
            self.card[self.capture] += ' '

    def handle_data(self, data):
        if self.card is not None and self.capture:
            self.card[self.capture] += data + ' '

    def handle_endtag(self, tag):
        if self.card is not None:
            if tag == 'h3' and self.capture == 'title':
                self.capture = None
            elif tag == 'span' and self.capture in {'schedule', 'venue'}:
                self.capture = None
        if tag == 'div':
            if self.card is not None and self.depth == self.card['depth']:
                card = {key: clean(value) for key, value in self.card.items()
                        if key != 'depth'}
                parsed = urlsplit(card['url'])
                if (parsed.hostname == 'www.cssudine.it'
                        and parsed.path.startswith('/stagione-')
                        and not trusted_event_url(card['url'])):
                    raise ValueError('unrecognized CSS season card URL')
                if (card['title'] and card['schedule'] and card['venue']
                        and not trusted_event_url(card['url'])):
                    raise ValueError('unrecognized complete CSS programme card')
                if trusted_event_url(card['url']):
                    if not card['title'] or not card['schedule'] or not card['venue']:
                        raise ValueError('incomplete CSS season card: ' + str(card))
                    self.cards.append(card)
                self.card = None
                self.capture = None
            self.depth -= 1


def _season_surface(html):
    parser = SeasonCards()
    parser.feed(html)
    if parser.card is not None or not parser.cards or len(parser.cards) > 250:
        raise ValueError('invalid CSS season inventory')
    return parser


def season_cards(html):
    parser = _season_surface(html)
    card_ids = {urlsplit(card['url']).path.split('/')[3] for card in parser.cards}
    if parser.linked_event_ids - card_ids:
        raise ValueError('CSS event link missing from season cards')
    return parser.cards


def _clock(value):
    value = value.replace('.', ':')
    return datetime.strptime(value if ':' in value else value + ':00', '%H:%M').strftime('%H:%M')


def _days(value, month, year):
    numbers = [int(number) for number in re.findall(r'\d{1,2}', value)]
    if not numbers:
        raise ValueError('ambiguous schedule')
    days = set(numbers)
    for match in re.finditer(r'(\d{1,2})\s*(?:-|\bal\b)\s*(\d{1,2})', value, re.I):
        first, last = map(int, match.groups())
        if last < first or last - first > 31:
            raise ValueError('ambiguous schedule')
        days.update(range(first, last + 1))
    return [date(year, month, number) for number in sorted(days)]


def _line_slots(raw, *, season_year=None):
    """Read explicit CSS dates, keeping hours optional when the page omits them."""
    line = clean(raw)
    if not line:
        return []
    if 'in via di definizione' in line.casefold() or 'su prenotazione' in line.casefold():
        raise ValueError('no defined programme dates')
    line = re.sub(r"^dall?[’']?\s*(\d{1,2})\s+al\s+(\d{1,2})\s+",
                  r'\1-\2 ', line, flags=re.I)
    line = re.sub(r"^dall?[’']?\s*(\d{1,2})\s+all?[’']?\s*(\d{1,2})\s+",
                  r'\1-\2 ', line, flags=re.I)
    if not re.search(r'\b20\d{2}\b', line):
        month_match = re.search(r'\b(febbraio|marzo)\b', line, re.I)
        if (season_year and month_match and re.search(r'\b\d{1,2}\b', line)
                and re.search(r"^(?:\w+\s+)?(?:dal|dall[’'])?\s*\d", line, re.I)):
            line = re.sub(r'\b' + month_match[1] + r'\b',
                          month_match[1] + f' {season_year + 1}', line, count=1, flags=re.I)
        else:
            raise ValueError('year not explicit')
    month_names = '|'.join(MONTHS)
    cross = re.match(
        rf'^\s*(\d{{1,2}})\s+({month_names})\s*-\s*'
        rf'(\d{{1,2}}(?:\s*(?:-|,|e)\s*\d{{1,2}})*)\s+'
        rf'({month_names})\s+(20\d{{2}})(.*)$', line, re.I)
    if cross:
        first = date(int(cross[5]), MONTHS[cross[2].lower()], int(cross[1]))
        last_dates = _days(cross[3], MONTHS[cross[4].lower()], int(cross[5]))
        last = max(last_dates)
        if not first < last or (last-first).days > 31:
            raise ValueError('ambiguous cross-month schedule')
        dates = [first + timedelta(days=offset) for offset in range((last-first).days + 1)]
        tail = cross[6]
    else:
        prefix = re.match(r'^(?:lunedì|martedì|mercoledì|giovedì|venerdì|sabato|domenica)\s*,?\s*',
                          line, re.I)
        if prefix:
            line = line[prefix.end():]
        match = re.match(
            rf'^\s*(\d{{1,2}}(?:\s*(?:-|,|e|al)\s*\d{{1,2}})*)\s+'
            rf'({month_names})\s+(20\d{{2}})(.*)$', line, re.I)
        if not match:
            raise ValueError('ambiguous schedule')
        dates = _days(match[1], MONTHS[match[2].lower()], int(match[3]))
        tail = match[4]
    except_days = re.search(r'\btranne\s+([\d\s,\-e]+)\s+(' + month_names + r')',
                            tail, re.I)
    if except_days:
        excluded = set(_days(except_days[1], MONTHS[except_days[2].lower()], dates[0].year))
        dates = [day for day in dates if day not in excluded]
        tail = tail[:except_days.start()] + tail[except_days.end():]
    times = re.findall(r'\b(?:ore\s*)?(\d{1,2}(?:[:.]\d{2})?)\b',
                       tail.split('(')[0], re.I)
    start_time = end_time = None
    if times and re.search(r'\bore\b', tail, re.I):
        if len(times) == 1:
            start_time = _clock(times[0])
        elif len(times) == 2 and re.search(r'\b(?:alle|-)\s*(?:ore\s*)?' + re.escape(times[1]), tail, re.I):
            start_time, end_time = _clock(times[0]), _clock(times[1])
            if end_time <= start_time:
                raise ValueError('ambiguous overnight schedule')
    return [(day, start_time, end_time, clean(raw)) for day in dates]


def _schedule_slots(lines, *, season_year=None):
    slots = []
    for raw in lines:
        line = clean(raw)
        if not line:
            continue
        try:
            new = _line_slots(raw, season_year=season_year)
        except ValueError as exc:
            if slots and 'apertura al pubblico' in line.casefold():
                day_month = re.search(
                    r'\b(\d{1,2})\s+(' + '|'.join(MONTHS) + r')\b', line, re.I)
                if (day_month and any(day.day == int(day_month[1])
                        and day.month == MONTHS[day_month[2].lower()]
                        for day, *_ in slots)):
                    continue
            if (slots and re.match(r'^(?:giovedì|venerdì|sabato|domenica)\b',
                                   line, re.I)
                    and not re.search(r'\b20\d{2}\b', line)
                    and not re.search(r'\b\d{1,2}\s+(' + '|'.join(MONTHS) + r')\b',
                                      line, re.I)):
                continue
            raise exc
        if ('masterclass' in line.casefold()
                and all(day in {item[0] for item in slots} for day, *_ in new)):
            continue
        slots.extend(new)
    if not slots:
        raise ValueError('no defined programme dates')
    deduped = {}
    for slot in slots:
        deduped.setdefault((slot[0], slot[1], slot[2]), slot)
    return list(deduped.values())

def parse_css(html, url, *, today, season_year=None):
    title = re.search(r'<h1\b[^>]*>(.*?)</h1>', html, re.S)
    venues = re.findall(r'<p class="venue">(.*?)</p>', html, re.S)
    if not title or not venues:
        raise ValueError('missing venue schedule')
    require_schedule_review(title[1], *venues)
    events = []
    for venue in venues:
        span = re.search(r'<span>(.*?)</span>', venue, re.S)
        if not span:
            raise ValueError('missing date')
        lines = [line for line in re.split(r'<br\s*/?>', span[1], flags=re.I) if clean(line)]
        location_header = clean(venue[:span.start()])
        if len(lines) > 1 and location_header.startswith('|'):
            # Explicit alternating schedule/location rows. Never assign all
            # performances to the first town listed in a programme heading.
            if len(lines) % 2:
                raise ValueError('unpaired schedule and venue')
            for offset in range(0, len(lines), 2):
                location_line = clean(lines[offset + 1])
                if ',' not in location_line:
                    raise ValueError('missing per-session venue')
                city, place = [value.strip() for value in location_line.split(',', 1)]
                city = re.sub(r'^S\.\s+Giorgio di Nogaro$', 'San Giorgio di Nogaro', city, flags=re.I)
                if not city or not place:
                    raise ValueError('missing per-session venue')
                fragment = ('<h1>' + title[1] + '</h1><p class="venue">'
                            + escape(city) + ' | ' + escape(place)
                            + '<span>' + lines[offset] + '</span></p>')
                events.extend(parse_css(fragment, url, today=today,
                                        season_year=season_year))
            continue
        location = clean(venue[:span.start()])
        if '|' not in location:
            raise ValueError('missing municipality')
        city, place = [x.strip() for x in location.split('|', 1)]
        if city.casefold() == 'cervignano':
            city = 'Cervignano del Friuli'
        town = engine.fvg_municipality_catalog.match_names(city)
        if not town:
            raise ValueError('unknown municipality')
        for day, hour, end_time, evidence in _schedule_slots(lines,
                season_year=season_year):
            if day >= today:
                events.append(dict(source='CSS Udine', url=url, title=clean(title[1]),
                    start_date=day.isoformat(), end_date=day.isoformat(),
                    event_city=city, place=location, venue=place, lat=town.latitude, lon=town.longitude,
                    location_confidence='municipality', is_real=True,
                    date_evidence_kind='event_schedule',
                    date_evidence=(evidence + (f' [stagione {season_year}/{season_year+1}]'
                                              if season_year and not re.search(r'\b20\d{2}\b', evidence)
                                              else ''))))
                if hour:
                    events[-1]['time'] = hour
                if end_time:
                    events[-1]['end_time'] = end_time
    return events


def detail_fields(html):
    heading = re.search(r'<h1\b[^>]*>(.*?)</h1>', html, re.I | re.S)
    block = re.search(r'<p\s+class="venue"[^>]*>(.*?)</p>', html, re.I | re.S)
    if not heading or not block:
        raise ValueError('missing CSS detail identity or venue')
    span = re.search(r'<span\b[^>]*>(.*?)</span>', block[1], re.I | re.S)
    if not span:
        raise ValueError('missing CSS detail schedule')
    return {'title': clean(heading[1]),
            'venue': clean(block[1][:span.start()]),
            'schedule': clean(span[1])}


def matching_schedule(card_schedule, detail_schedule):
    if card_schedule == detail_schedule:
        return True
    months = '|'.join(MONTHS)
    pattern = rf'\b\d{{1,2}}\s+(?:{months})\s+20\d{{2}}\b'
    cards = {clean(match) for match in re.findall(pattern, card_schedule, re.I)}
    details = {clean(match) for match in re.findall(pattern, detail_schedule, re.I)}
    return len(cards) >= 2 and cards == details


def past_schedule(schedule, *, today, season_year):
    months = '|'.join(MONTHS)
    full = list(re.finditer(
        rf'\b(\d{{1,2}})\s+({months})\s+(20\d{{2}})\b', schedule, re.I))
    explicit = [date(int(match[3]), MONTHS[match[2].lower()], int(match[1]))
                for match in full]
    if explicit:
        last = max(explicit)
        for match in re.finditer(
                rf'\b(\d{{1,2}})\s+({months})\b(?!\s+20\d{{2}})',
                schedule[full[-1].end():], re.I):
            if (MONTHS[match[2].lower()], int(match[1])) > (last.month, last.day):
                return False
        return last < today
    end = re.search(rf'^aperta\s+fino\s+al\s+(\d{{1,2}})\s+({months})\b',
                    schedule, re.I)
    return bool(end and date(season_year, MONTHS[end[2].lower()], int(end[1])) < today)


def detail_image(html):
    class Images(HTMLParser):
        def __init__(self):
            super().__init__(convert_charrefs=True)
            self.matches = []

        def handle_starttag(self, tag, attrs):
            if tag != 'img':
                return
            values = dict(attrs)
            source = values.get('src') or ''
            if re.fullmatch(r'/media/spettacoli/[^?#]+_icona\.(?:jpe?g|png|webp)',
                            source, re.I):
                self.matches.append(source)

    parser = Images()
    parser.feed(html)
    return urljoin(BASE, parser.matches[-1]) if parser.matches else None


def detail_excerpt(html, *, url, title):
    body = html.split('<div class="col-sm-8 dx">', 1)
    if len(body) != 2:
        return {}
    paragraphs = re.findall(
        r'<p\b[^>]*>(.*?)</p>', body[1], re.I | re.S)
    artist = clean(title.split('/', 1)[-1]) if '/' in title else ''
    artist_candidates = []
    candidates = []
    for raw in paragraphs:
        paragraph = clean(raw)
        if paragraph.casefold().startswith((
                'ricerca tra tutti gli spettacoli', 'ricerca tramite google',
                'iscriviti al servizio newsletter', 'css teatro stabile di innovazione',
                'il sito utilizza cookie')):
            break
        if len(paragraph) < 80:
            continue
        if re.search(r'^\s*(?:\d{1,2}\s+\w+.{0,35}\b20\d{2}\b|(?:lunedì|martedì|mercoledì|giovedì|venerdì|sabato|domenica)\b)',
                     paragraph, re.I):
            parts = re.split(r'(?:<br\s*/?>\s*){2,}', raw, maxsplit=1, flags=re.I)
            prose = clean(parts[1]) if len(parts) == 2 else ''
            age = re.search(r'fascia\s+d[’\']età\s*:\s*\d+\+\s*(.*)', paragraph, re.I | re.S)
            if len(prose) >= 80:
                paragraph = prose
            elif age and len(age[1]) >= 80:
                paragraph = age[1]
            else:
                continue
        if paragraph.casefold().startswith('dialoghi open lab, giunto'):
            continue
        if artist and artist.casefold() in paragraph.casefold():
            artist_candidates.append(paragraph)
        candidates.append(paragraph)
    selected = (artist_candidates or candidates or [''])[0]
    return attributed_excerpt(selected, source_name='CSS Udine',
                              source_url=url, title=title)


def omitted_reason(card, detail, *, today, season_year):
    schedule = detail['schedule']
    lower = schedule.casefold()
    if 'in via di definizione' in lower or 'disponibile su prenotazione' in lower:
        return 'dates_not_defined'
    if (lower.startswith('da ottobre ') and ' a marzo ' in lower
            or card['title'].casefold().startswith('la scuola dello sguardo #7')
            and '/' not in card['title'] and ' al ' in card['schedule'].casefold()):
        return 'season_umbrella'
    if not detail['venue'].split('|', 1)[0].strip() and any(
            token in detail['venue'].casefold()
            for token in ('plessi scolastici', 'scuole o altri spazi')):
        return 'municipality_not_fixed'
    if past_schedule(schedule, today=today, season_year=season_year):
        return 'past'
    return None


def collect_css(*, get=None, today=None):
    if get is not None:
        return _collect_css(get=get, today=today)
    sessions = []
    sessions_lock = Lock()
    thread_state = local()

    def session_get(url, **kwargs):
        if not hasattr(thread_state, 'session'):
            thread_state.session = requests.Session()
            with sessions_lock:
                sessions.append(thread_state.session)
        return thread_state.session.get(url, **kwargs)

    try:
        return _collect_css(get=session_get, today=today)
    finally:
        for session in sessions:
            session.close()


def _collect_css(*, get, today):
    today = today or datetime.now(ZoneInfo('Europe/Rome')).date()
    def fetch(url):
        if url not in {urljoin(BASE, path) for path in SEASON_PATHS} and not trusted_event_url(url):
            raise ValueError('untrusted CSS fetch URL')
        with get(url, timeout=(4, 12), stream=True, allow_redirects=False) as response:
            response.raise_for_status()
            if response.status_code != 200:
                raise ValueError('unexpected response')
            chunks, size = [], 0
            for chunk in response.iter_content(65536):
                size += len(chunk)
                if size > 4*1024*1024:
                    raise ValueError('oversized page')
                chunks.append(chunk)
            return b''.join(chunks).decode('utf-8-sig')
    inventory, surfaces, unlisted_links = {}, [], {}
    for path in SEASON_PATHS:
        page_url = urljoin(BASE, path)
        surface = _season_surface(fetch(page_url))
        cards = surface.cards
        card_ids = {urlsplit(card['url']).path.split('/')[3] for card in cards}
        for event_id in surface.linked_event_ids - card_ids:
            unlisted_links[event_id] = surface.linked_event_urls[event_id]
        new = 0
        for card in cards:
            old = inventory.get(card['url'])
            if old and old != card:
                raise ValueError('conflicting CSS season cards: ' + card['url'])
            if not old:
                inventory[card['url']] = card
                new += 1
        surfaces.append({'url': page_url, 'cards': len(cards), 'new_urls': new})
    if not 1 <= len(inventory) <= 250:
        raise ValueError('invalid CSS event inventory')

    listed_ids = {urlsplit(url).path.split('/')[3] for url in inventory}
    unlisted_links = {event_id: url for event_id, url in unlisted_links.items()
                      if event_id not in listed_ids}
    if len(unlisted_links) > 12:
        raise ValueError('too many unlisted CSS event links')
    for event_id, url in sorted(unlisted_links.items()):
        detail = detail_fields(fetch(url))
        season_year = int(urlsplit(url).path.split('/')[2])
        if not past_schedule(detail['schedule'], today=today,
                             season_year=season_year):
            raise ValueError('CSS event link missing from season cards: ' + url)

    urls = sorted(inventory)
    with ThreadPoolExecutor(max_workers=4) as pool:
        details = dict(zip(urls, pool.map(fetch, urls)))
    events, review, checked, excluded = [], [], [], []
    for url in urls:
        html = details[url]
        card = inventory[url]
        year = int(urlsplit(url).path.split('/')[2])
        try:
            detail = detail_fields(html)
            if (detail['venue'] != card['venue']
                    or not matching_schedule(card['schedule'], detail['schedule'])):
                raise ValueError('CSS season card and detail disagree')
            reason = omitted_reason(card, detail, today=today, season_year=year)
            if reason:
                excluded.append({'url': url, 'reason': reason})
                disposition = reason
            else:
                season_year = year if re.search(rf'\b{year}/{year+1}\b', html) else None
                parsed = parse_css(html, url, today=today, season_year=season_year)
                if not parsed:
                    disposition = 'past'
                    excluded.append({'url': url, 'reason': 'past'})
                else:
                    image = detail_image(html)
                    excerpt = detail_excerpt(html, url=url, title=card['title'])
                    for event in parsed:
                        event['title'] = card['title']
                        event['source_title'] = detail['title']
                        if image:
                            event['image'] = image
                        event.update(excerpt)
                        invalid = validate_candidate(event, today=today)
                        if invalid:
                            raise ValueError('invalid CSS event: ' + ','.join(invalid))
                    events.extend(parsed)
                    disposition = 'included'
        except ValueError as exc:
            review.append({'url': url, 'reason': str(exc)})
            disposition = 'review_required'
        checked.append({'url': url, 'disposition': disposition})
    events.sort(key=lambda event: (event['start_date'], event.get('time') or '',
                                   event['event_city'], event['title'], event['url']))
    verification = {'collection_mode': 'complete-css-current-season-indexes',
                    'surface_counts': surfaces, 'listing_count': len(inventory),
                    'detail_count': len(checked),
                    'listing_records': list(inventory.values()),
                    'detail_records': checked,
                    'included_detail_urls': sum(item['disposition'] == 'included'
                                                for item in checked),
                    'event_count': len(events), 'excluded_count': len(excluded),
                    'past_unlisted_links': len(unlisted_links),
                    'review_count': len(review), 'source_complete': True}
    return {'status': 'ok', 'events': events, 'review_required': review,
            'excluded': excluded, 'verification': verification,
            'coverage': 'homepage-and-all-five-current-season-indexes'}

if __name__ == '__main__':
    result = collect_css()
    print({'performances': len(result['events']), 'review': result['review_required']})
