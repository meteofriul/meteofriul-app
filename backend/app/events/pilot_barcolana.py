"""Official Barcolana calendar, published as one dated programme card."""
from datetime import date, datetime, timezone
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from html import unescape
from html.parser import HTMLParser
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo
from xml.etree import ElementTree
import re
import unicodedata

import requests

from .pilot_excerpt import attributed_excerpt


SOURCE = 'Barcolana'
CALENDAR = 'https://www.barcolana.it/it/calendario-eventi'
CALENDAR_DATA = CALENDAR + '?search=1&_ds=0:Eventi&_cids=0:i1g43'
EDITION_NEWS = ('https://www.barcolana.it/it/news/2026/'
                'barcolana58-presented-by-generali-tutto-pronto-per-la-grande-regata')
SITEMAP = 'https://www.barcolana.it/sitemap-0.xml'
KNOWN_ORPHAN = ('https://www.barcolana.it/it/eventi/terra/2026/'
                'concerto-dei-ragazzi-del-collegio-del-mondo-unito-dell-adriatico')
MONTHS = {name: month for month, name in enumerate((
    'gennaio', 'febbraio', 'marzo', 'aprile', 'maggio', 'giugno',
    'luglio', 'agosto', 'settembre', 'ottobre', 'novembre', 'dicembre'), 1)}
DATE = re.compile(r'^(\d{1,2})\s+([a-z]+)\s+(20\d{2})$', re.I)
UTC_TIME = re.compile(r"new Date\('1900-01-01T(\d{2}:\d{2}:\d{2})\.\d{3}Z'\)")
PK = re.compile(r'^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$')
MAIN_START, MAIN_END = date(2026, 10, 2), date(2026, 10, 11)
VESPUCCI_CEREMONY = 'CERIMONIA DI CHIUSURA DEL TOUR MONDIALE VESPUCCI E INAUGURAZIONE VILLAGGIO IN ITALIA'
REGIONAL_PIAZZA_PAGES = {
    'https://www.turismofvg.it/eventi/barcolana-58-eventi-in-piazza': '2026-10-07',
    'https://www.turismofvg.it/eventi/barcolana-58-eventi-in-piazza-505759': '2026-10-08',
    'https://www.turismofvg.it/eventi/barcolana-58-eventi-in-piazza-505765': '2026-10-09',
    'https://www.turismofvg.it/eventi/barcolana-58-eventi-in-piazza-505790': '2026-10-10',
    'https://www.turismofvg.it/eventi/barcolana-58-eventi-in-piazza-505797': '2026-10-11',
}
REGIONAL_MUSEUM = 'https://www.turismofvg.it/eventi/barcolana-al-museo-museo-del-mare'
REGIONAL_TALKS = 'https://www.turismofvg.it/eventi/barcolana58-talk'
REGIONAL_PERIODS = {REGIONAL_MUSEUM: ('2026-10-03', '2026-10-10'),
                    REGIONAL_TALKS: ('2026-10-09', '2026-10-10')}
PIAZZA_TIME = re.compile(r'^(?:ore\s*)?(\d{1,2})[.:](\d{2})'
                         r'(?:\s*-\s*\d{1,2}[.:]\d{2})?\b(.*)$', re.I)


def clean(value):
    return ' '.join(str(value or '').split())


class CalendarMarkup(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.rows, self.row, self.depth, self.field, self.field_depth = [], None, 0, None, 0

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        classes = set(attrs.get('class', '').split())
        if tag == 'div' and 'hyve-repeater-i1g43-item' in classes:
            if self.row is not None:
                raise ValueError('nested calendar row')
            self.row = {'pk': attrs.get('data-item-pk'), 'times': []}
            self.depth = 1
            return
        if self.row is None:
            return
        if tag == 'div':
            self.depth += 1
        field = next((key for key, marker in (
            ('date', 'c-eventItem__date'), ('title', 'c-eventItem__title'),
            ('place', 'c-eventItem__location'), ('taxonomy', 'c-eventItem__tax'))
            if marker in classes), None)
        if field:
            if self.field is not None:
                raise ValueError('overlapping calendar fields')
            self.field, self.field_depth = field, 1
            self.row.setdefault(field, '')
        elif self.field is not None:
            self.field_depth += 1
        if tag == 'script':
            self.field = self.field or 'script'
            self.field_depth = self.field_depth or 1
            self.row.setdefault('script', '')

    def handle_endtag(self, tag):
        if self.row is None:
            return
        if self.field is not None:
            self.field_depth -= 1
            if self.field_depth == 0:
                if self.field == 'script':
                    self.row['times'].extend(UTC_TIME.findall(self.row.pop('script', '')))
                self.field = None
        if tag == 'div':
            self.depth -= 1
            if self.depth == 0:
                self.rows.append(self.row)
                self.row = None

    def handle_data(self, data):
        if self.row is not None and self.field is not None:
            self.row[self.field] += data


class NewsMarkup(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.title = ''
        self.image = ''
        self.in_title = False
        self.body_depth = 0
        self.body = ''

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'meta' and attrs.get('property') == 'og:image':
            self.image = attrs.get('content', '')
        if tag == 'title':
            self.in_title = True
        if tag == 'div' and 'c-news__text' in attrs.get('class', '').split():
            self.body_depth = 1
        elif tag == 'div' and self.body_depth:
            self.body_depth += 1

    def handle_endtag(self, tag):
        if tag == 'title':
            self.in_title = False
        if tag == 'div' and self.body_depth:
            self.body_depth -= 1

    def handle_data(self, data):
        if self.in_title:
            self.title += data
        if self.body_depth:
            self.body += data + ' '


class PiazzaMetadata(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.values = {}

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'meta' and attrs.get('property') in {'og:title', 'og:url', 'og:description'}:
            self.values[attrs['property']] = attrs.get('content', '')


def regional_lines(html, *, url, title):
    metadata = PiazzaMetadata()
    metadata.feed(html)
    values = metadata.values
    if (values.get('og:url') != url
            or clean(values.get('og:title')).casefold() != title.casefold()):
        raise ValueError('regional Barcolana page identity changed')
    markup = unescape(values.get('og:description', ''))
    if '<br' not in markup.lower():
        raise ValueError('regional Barcolana programme missing')
    lines = [clean(part) for part in
             re.sub(r'<br\s*/?>', '\n', markup, flags=re.I).splitlines()]
    lines = [line for line in lines if line]
    if not lines:
        raise ValueError('regional Barcolana programme empty')
    return lines


def parse_regional_piazza(html, *, url, day):
    """Read each dated TurismoFVG piazza programme without losing its rows."""
    lines = regional_lines(html, url=url, title='Barcolana 58 - eventi in piazza')
    header = re.fullmatch(r'[A-ZÌÍÈÉ]+\s+(\d{1,2})\s+OTTOBRE', lines[0], re.I)
    if not header or int(header[1]) != date.fromisoformat(day).day:
        raise ValueError('regional piazza date changed')
    sessions, pending = [], []
    footer = False
    for index, line in enumerate(lines[1:], 1):
        if line.casefold().startswith('il programma può subire variazioni'):
            footer = True
            break
        time = PIAZZA_TIME.fullmatch(line)
        if time:
            hour, minute = int(time[1]), int(time[2])
            if hour > 23 or minute > 59:
                raise ValueError('regional piazza time invalid')
            pending.append((f'{hour:02d}:{minute:02d}', clean(time[3])))
            continue
        if (pending and line.upper() == line and any(char.isalpha() for char in line)
                and not line.startswith('INFO')):
            if index + 1 == len(lines) or PIAZZA_TIME.fullmatch(lines[index + 1]):
                raise ValueError('regional piazza description missing')
            for start_time, place in pending:
                session = {'title': line, 'start_date': day, 'time': start_time,
                           'url': url}
                if place:
                    session['place'] = place
                sessions.append(session)
            pending = []
    if not footer or pending or not sessions:
        raise ValueError('regional piazza programme incomplete')
    return sessions


def parse_regional_museum(html):
    """Read every timed museum appointment from its labelled calendar."""
    lines = regional_lines(html, url=REGIONAL_MUSEUM,
                           title='Barcolana al museo - Museo del Mare')
    try:
        start = lines.index('CALENDARIO DEGLI APPUNTAMENTI')
        end = lines.index('PRENOTAZIONI', start + 1)
    except ValueError as exc:
        raise ValueError('regional museum calendar bounds missing') from exc
    sessions, day = [], None
    for line in lines[start + 1:end]:
        heading = re.fullmatch(r'[A-Za-zàèéìòù]+\s+(\d{1,2})\s+ottobre', line, re.I)
        if heading:
            day = f'2026-10-{int(heading[1]):02d}'
            if not REGIONAL_PERIODS[REGIONAL_MUSEUM][0] <= day <= REGIONAL_PERIODS[REGIONAL_MUSEUM][1]:
                raise ValueError('regional museum day outside event period')
            continue
        meeting = re.fullmatch(r'(\d{1,2})\.(\d{2})\s*[–-]\s*'
                               r'(\d{1,2})\.(\d{2})\s*\|\s*(.+)', line)
        if meeting:
            if not day:
                raise ValueError('regional museum appointment without day')
            if (int(meeting[1]) > 23 or int(meeting[2]) > 59
                    or int(meeting[3]) > 23 or int(meeting[4]) > 59):
                raise ValueError('regional museum time invalid')
            sessions.append({'title': clean(meeting[5]), 'start_date': day,
                             'time': f'{int(meeting[1]):02d}:{meeting[2]}',
                             'end_time': f'{int(meeting[3]):02d}:{meeting[4]}',
                             'place': 'Magazzino 26, Civico Museo del Mare',
                             'url': REGIONAL_MUSEUM})
        elif '|' in line or re.match(r'^\d{1,2}[.:]\d{2}', line):
            raise ValueError('regional museum appointment unparsed')
    if not sessions:
        raise ValueError('regional museum calendar empty')
    return sessions


def parse_regional_talks(html):
    """Read the two dated talks represented by three regional cards."""
    lines = regional_lines(html, url=REGIONAL_TALKS, title='Barcolana58 - Talk')
    sessions = []
    for index, line in enumerate(lines):
        heading = re.fullmatch(r'[A-Za-zàèéìòù]+\s+(\d{1,2})\s+ottobre\s+'
                               r'ore\s+(\d{1,2})\.(\d{2})', line, re.I)
        if not heading:
            continue
        day = f'2026-10-{int(heading[1]):02d}'
        if not REGIONAL_PERIODS[REGIONAL_TALKS][0] <= day <= REGIONAL_PERIODS[REGIONAL_TALKS][1]:
            raise ValueError('regional talk day outside event period')
        if int(heading[2]) > 23 or int(heading[3]) > 59:
            raise ValueError('regional talk time invalid')
        if index + 1 >= len(lines) or len(lines[index + 1]) < 12:
            raise ValueError('regional talk title missing')
        sessions.append({'title': lines[index + 1], 'start_date': day,
                         'time': f'{int(heading[2]):02d}:{heading[3]}',
                         'place': 'Area hospitality Io Sono Friuli Venezia Giulia',
                         'url': REGIONAL_TALKS})
    if len(sessions) != 2 or len({item['start_date'] for item in sessions}) != 2:
        raise ValueError('regional talk programme incomplete')
    return sessions


def merge_regional_piazza(sessions, regional):
    """Official date/time wins; add only appointments absent from its calendar."""
    keys = [(item['start_date'], _slug(item['title']), item['time'])
            for item in regional]
    if len(keys) != len(set(keys)):
        raise ValueError('regional Barcolana programme has repeated identity')
    by_title = defaultdict(list)
    for item in sessions:
        by_title[(item['start_date'], _slug(item['title']))].append(item)
    additions, disagreements = [], []
    for item in regional:
        peers = by_title[(item['start_date'], _slug(item['title']))]
        exact = [peer for peer in peers if peer.get('time') == item['time']]
        if len(exact) > 1:
            raise ValueError('Barcolana calendar has ambiguous regional match')
        if exact:
            continue
        if len(peers) == 1:
            disagreements.append({'day': item['start_date'], 'title': item['title'],
                                  'official_time': peers[0].get('time'),
                                  'regional_time': item['time']})
            continue
        if peers:
            raise ValueError('regional piazza duplicate time ambiguous')
        additions.append(item)
        by_title[(item['start_date'], _slug(item['title']))].append(item)
    sessions.extend(additions)
    sessions.sort(key=lambda item: (item['start_date'], item.get('time', ''), item['title']))
    return additions, disagreements


def parse_calendar(html):
    parser = CalendarMarkup()
    parser.feed(html)
    if parser.row is not None or not parser.rows:
        raise ValueError('calendar missing or truncated')
    sessions, identities, pks = [], set(), set()
    day_counts = {}
    duplicate_count = 0
    for row in parser.rows:
        pk = row.get('pk')
        match = DATE.fullmatch(clean(row.get('date')))
        if (not pk or not PK.fullmatch(pk) or pk in pks or not match
                or not clean(row.get('title')) or len(row['times']) > 2):
            raise ValueError('incomplete calendar row')
        pks.add(pk)
        day = date(int(match[3]), MONTHS[match[2].lower()], int(match[1]))
        if day.year != MAIN_START.year:
            raise ValueError('unexpected edition year')
        day_string = day.isoformat()
        day_counts[day_string] = day_counts.get(day_string, 0) + 1
        times = [datetime.fromisoformat('1900-01-01T' + value + '+00:00')
                 .astimezone(ZoneInfo('Europe/Rome')).strftime('%H:%M')
                 for value in row['times']]
        title, place = clean(row['title']), clean(row.get('place'))
        identity = (day_string, title.casefold(), place.casefold(), *times)
        if identity in identities:
            duplicate_count += 1
            continue
        identities.add(identity)
        session = {'title': title, 'start_date': day_string, 'url': CALENDAR}
        if place:
            session['place'] = place
        # Official news and the calendar disagree on this ceremony's start time.
        if times and title.upper() != VESPUCCI_CEREMONY:
            session['time'] = times[0]
        if len(times) == 2 and title.upper() != VESPUCCI_CEREMONY:
            session['end_time'] = times[1]
        sessions.append(session)
    # The provider publishes the same 10 October show twice under two names
    # for the same stage. The regional daily programme confirms one show.
    same_stage = [item for item in sessions
                  if (item['start_date'] == '2026-10-10'
                      and item['title'].casefold() == 'crossroads vocal group'
                      and item.get('time') == '16:00')]
    if (len(same_stage) == 2
            and {item.get('place') for item in same_stage}
            == {'Palco Cavana', 'Palco Piazza Cavana'}
            and all(not item.get('end_time') for item in same_stage)):
        sessions.remove(next(item for item in same_stage
                             if item['place'] == 'Palco Cavana'))
        duplicate_count += 1
    # The official calendar repeats Barcolana Ski under a broken CMS type name.
    # Its correctly named official land-event page confirms the same ski race.
    broken_ski = [item for item in sessions
                  if item['title'] == 'OfficeOpenXml.Style.ExcelRichTextCollection']
    if broken_ski:
        canonical_ski = [item for item in sessions
                         if (item['title'] == "BARCOLANA SKI - COPPA D'AUTUNNO"
                             and item['start_date'] == '2026-10-10'
                             and item.get('place') == 'Centro Federale "Neve Sole"'
                             and item.get('time') == '09:00')]
        if (len(broken_ski) != 1 or len(canonical_ski) != 1
                or broken_ski[0]['start_date'] != '2026-10-10'
                or broken_ski[0].get('place') != 'Sci Club 70'
                or broken_ski[0].get('time') != '09:30'):
            raise ValueError('unresolved malformed Barcolana Ski calendar row')
        sessions.remove(broken_ski[0])
        duplicate_count += 1
    sessions.sort(key=lambda item: (item['start_date'], item.get('time', ''), item['title']))
    return sessions, {'records_scanned': len(parser.rows), 'parsed_count': len(sessions),
                      'duplicate_count': duplicate_count,
                      'day_counts': dict(sorted(day_counts.items()))}


def _read(get, url, limit):
    response = get(url, timeout=25, headers={'User-Agent': 'MeteoFriulEvents/1.0'})
    response.raise_for_status()
    data = response.content
    if len(data) > limit:
        raise ValueError('Barcolana response too large')
    return data.decode('utf-8-sig')


def parse_sitemap(xml):
    root = ElementTree.fromstring(xml)
    urls = [clean(item.text) for item in root.iter()
            if item.tag.endswith('}loc') and item.text]
    events = [url for url in urls
              if urlsplit(url).hostname == 'www.barcolana.it'
              and urlsplit(url).path.startswith('/it/eventi/')
              and '/2026/' in urlsplit(url).path]
    if not events or len(events) != len(set(events)):
        raise ValueError('invalid event sitemap')
    return set(events)


def _slug(value):
    value = unicodedata.normalize('NFKD', clean(value).casefold())
    value = ''.join(char for char in value if not unicodedata.combining(char))
    return '-'.join(re.findall(r'[a-z0-9]+', value))


def link_unique_details(sessions, sitemap_urls):
    """Use a detail URL only for a unique exact title slug on both surfaces."""
    title_counts = Counter(_slug(item['title']) for item in sessions)
    urls_by_slug = defaultdict(list)
    for url in sitemap_urls:
        urls_by_slug[urlsplit(url).path.rsplit('/', 1)[-1]].append(url)
    linked = 0
    for session in sessions:
        key = _slug(session['title'])
        if title_counts[key] == len(urls_by_slug[key]) == 1:
            session['url'] = urls_by_slug[key][0]
            linked += 1
    return linked


def collect_barcolana(*, get=requests.get, today=None):
    today = today or datetime.now(ZoneInfo('Europe/Rome')).date()
    sessions, proof = parse_calendar(_read(get, CALENDAR_DATA, 3 * 1024 * 1024))
    sitemap_urls = parse_sitemap(_read(get, SITEMAP, 2 * 1024 * 1024))
    if KNOWN_ORPHAN in sitemap_urls:
        orphan = get(KNOWN_ORPHAN, timeout=15,
                     headers={'User-Agent': 'MeteoFriulEvents/1.0'})
        if orphan.status_code != 404:
            raise ValueError('orphan event page changed')
        orphan_count = 1
    else:
        orphan_count = 0
    # The live calendar can publish rows before their detail URLs reach the
    # sitemap. It is the primary programme surface; a sitemap surplus instead
    # signals possible events missing from the calendar and remains blocking.
    if len(sitemap_urls) - orphan_count > proof['records_scanned']:
        raise ValueError('event sitemap has rows absent from calendar')
    sitemap_lag = proof['records_scanned'] - (len(sitemap_urls) - orphan_count)
    detail_url_count = link_unique_details(sessions, sitemap_urls)
    regional = []
    active_piazza = {url: day for url, day in REGIONAL_PIAZZA_PAGES.items()
                     if day >= today.isoformat()}
    active_periods = {url: period for url, period in REGIONAL_PERIODS.items()
                      if period[1] >= today.isoformat()}
    urls = [*active_piazza, *active_periods]
    if urls:
        with ThreadPoolExecutor(max_workers=len(urls)) as executor:
            pages = dict(zip(urls, executor.map(
                lambda url: _read(get, url, 512 * 1024), urls)))
    else:
        pages = {}
    for url, day in active_piazza.items():
        regional.extend(parse_regional_piazza(pages[url], url=url, day=day))
    piazza_rows = len(regional)
    museum = (parse_regional_museum(pages[REGIONAL_MUSEUM])
              if REGIONAL_MUSEUM in pages else [])
    talks = (parse_regional_talks(pages[REGIONAL_TALKS])
             if REGIONAL_TALKS in pages else [])
    regional.extend(museum)
    regional.extend(talks)
    supplements, time_disagreements = merge_regional_piazza(sessions, regional)
    news = NewsMarkup()
    news.feed(_read(get, EDITION_NEWS, 1024 * 1024))
    if (news.body_depth or news.in_title
            or 'barcolana58' not in news.title.casefold()
            or '2026' not in news.body
            or '11 ottobre' not in news.body.casefold()):
        raise ValueError('current edition news not verified')
    image = news.image
    if (urlsplit(image).scheme != 'https'
            or urlsplit(image).hostname != 'www.barcolana.it'):
        raise ValueError('current edition cover unavailable')
    excerpt = attributed_excerpt(news.body, source_name=SOURCE,
                                 source_url=EDITION_NEWS, title='Barcolana 2026')
    if not excerpt:
        raise ValueError('current edition description unavailable')
    dates = sorted(proof['day_counts'])
    if not MAIN_START.isoformat() in dates or not MAIN_END.isoformat() in dates:
        raise ValueError('festival dates missing from calendar')
    event = {'source': SOURCE, 'url': CALENDAR, 'title': 'Barcolana 2026',
             'event_city': 'Trieste', 'lat': 45.64953, 'lon': 13.77678,
             'location_confidence': 'municipality', 'place': 'Trieste',
             'category': 'sport', 'image': image,
             'start_date': dates[0], 'end_date': dates[-1],
             'occurrences': dates,
             'date_label': '2–11 ottobre 2026',
             'date_evidence_kind': 'event_schedule',
             'date_evidence': 'Barcolana 2026: 2–11 ottobre; calendario ufficiale',
             'display_mode': 'umbrella', 'programme_city': 'Trieste',
             'programme_sessions': sessions,
             'regional_mirror_days': active_piazza,
             'regional_mirror_periods': active_periods,
             'active_session_count': sum(item['start_date'] >= today.isoformat()
                                         for item in sessions),
             **excerpt}
    return {'status': 'ok', 'events': [event], 'review_required': [],
            'coverage': 'complete-official-html-calendar',
            'verification': {'collection_mode': 'complete-official-html-calendar',
                             'as_of_date': today.isoformat(),
                             'edition_id': '2026', 'main_start_date': MAIN_START.isoformat(),
                             'main_end_date': MAIN_END.isoformat(),
                             'first_date': dates[0], 'last_date': dates[-1],
                             'image_source_url': EDITION_NEWS,
                             'sitemap_event_url_count': len(sitemap_urls),
                             'sitemap_known_orphan_count': orphan_count,
                             'sitemap_lag_rows': sitemap_lag,
                             'detail_url_count': detail_url_count,
                             'regional_piazza_page_count': len(active_piazza),
                             'regional_piazza_row_count': piazza_rows,
                             'regional_museum_row_count': len(museum),
                             'regional_talk_row_count': len(talks),
                             'regional_supplement_count': len(supplements),
                             'regional_piazza_supplement_count': sum(
                                 item['url'] in active_piazza
                                 for item in supplements),
                             'regional_piazza_time_disagreements': time_disagreements,
                             **proof}}


def current_card(event, today):
    """Show the complete upcoming programme without replaying elapsed sessions."""
    if event.get('source') != SOURCE or not isinstance(event.get('programme_sessions'), list):
        return event
    sessions = [item for item in event['programme_sessions']
                if item.get('start_date', '') >= today.isoformat()]
    dates = sorted({item['start_date'] for item in sessions})
    label = event.get('date_label')
    if today > MAIN_END and dates:
        next_day = date.fromisoformat(dates[0])
        month = next(name for name, number in MONTHS.items() if number == next_day.month)
        label = f'{next_day.day} {month} {next_day.year}'
    return {**event, 'programme_sessions': sessions, 'active_session_count': len(sessions),
            'occurrences': dates, 'date_label': label}
