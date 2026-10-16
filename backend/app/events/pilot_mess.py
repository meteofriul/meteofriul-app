"""Read MESS laboratories, museum addresses, and dated exhibition news."""
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime
import json
import re
import unicodedata
from zoneinfo import ZoneInfo

import requests

from . import engine
from .pilot_excerpt import attributed_excerpt


SOURCE = 'MESS'
BASE = 'https://mess.regione.fvg.it'
PROGRAMME_URL = BASE + '/it/didattica-museale-171043'
PROGRAMME_API = BASE + '/core/page/erpac_mess/171043/it/'
MUSEUM_API = BASE + '/core/page/erpac_mess/171271/it/'
NEWS_API = BASE + '/core/categories/erpac_mess/it/18221/'
MONTHS = {'agosto': 8, 'settembre': 9, 'ottobre': 10,
          'novembre': 11, 'dicembre': 12}
# The 2026 HTML spells this one month "novenbre".  This is a reviewed typo,
# not permission to guess an unrecognised month in a future programme.
MONTH_TYPO = {'novenbre': 11}
# Reviewed 2026 programme slots. A malformed label can be quarantined by its
# position without assigning a guessed date or museum to a published event.
REVIEWED_LABORATORY_SLOTS_2026 = (
    ('2026-08-01', 38554), ('2026-08-02', 38553),
    ('2026-08-07', 38557), ('2026-08-13', 38548),
    ('2026-08-20', 38543), ('2026-08-21', 38557),
    ('2026-08-22', 38553), ('2026-08-29', 38546),
    ('2026-09-01', 38549), ('2026-09-05', 38554),
    ('2026-09-11', 38551), ('2026-09-12', 38548),
    ('2026-09-13', 38549), ('2026-09-18', 38547),
    ('2026-09-19', 38543), ('2026-09-25', 38551),
    ('2026-09-28', 38560), ('2026-10-02', 38547),
    ('2026-10-03', 38560), ('2026-10-04', 38556),
    ('2026-10-10', 38555), ('2026-10-11', 38544),
    ('2026-10-17', 38558), ('2026-10-18', 38550),
    ('2026-10-24', 38552), ('2026-10-25', 38556),
    ('2026-11-14', 38558), ('2026-11-15', 38550),
    ('2026-11-22', 38545), ('2026-11-28', 38546),
    ('2026-11-29', 38545), ('2026-12-06', 38559),
    ('2026-12-12', 38552), ('2026-12-13', 38559),
    ('2026-12-19', 38555), ('2026-12-20', 38544),
)
VENUE_ALIASES = {
    'museo di storia contadina di fontanabona': 38554,
    'museo della cantieristica': 38560,
    'consorzio culturale del monfalconese': 38552,
}
REVIEWED_NEWS_2026 = {
    233061: '2026-09-23T10:14:57', 232542: '2026-09-14T11:29:42',
    232531: '2026-09-14T11:30:34', 231767: '2026-08-25T11:42:25',
    230848: '2026-07-30T13:27:00', 230714: '2026-07-28T11:20:53',
    230454: '2026-07-21T16:43:45', 229782: '2026-07-06T14:07:37',
    229430: '2026-06-29T12:02:25', 228192: '2026-06-05T11:41:44',
    228134: '2026-06-04T13:41:03', 227651: '2026-05-26T16:36:35',
    226528: '2026-05-06T14:59:07', 225938: '2026-04-23T14:49:12',
    225922: '2026-04-23T12:17:00', 225399: '2026-04-14T14:41:22',
    224954: '2026-04-07T15:32:35', 224163: '2026-03-19T13:12:47',
    223273: '2026-03-03T15:17:35', 222908: '2026-02-27T12:39:04',
    222784: '2026-02-24T10:31:26', 222781: '2026-02-24T10:33:05',
    221893: '2026-02-09T10:24:13', 221890: '2026-02-06T10:08:25',
}
REVIEWED_HISTORICAL_UPDATES = {141538: '2026-01-20T11:38:13'}
REVIEWED_ACTIVE_NEWS = {
    233061: {
        'path': '/not-173804', 'start': '2026-09-25', 'end': '2026-11-29',
        'city': 'Udine', 'venue': 'Museo Etnografico del Friuli',
        'intro_dates': ('25 settembre', '29 novembre'),
        'excerpt_marker': 'esposizione propone',
        'regional_url': 'https://www.turismofvg.it/eventi/sulla-soglia-simboli-e-rituali-della-morte-in-friuli-con-le-fotografie-di-carlo-innocenti',
    },
    232542: {
        'path': '/not-173318/no-173328', 'start': '2026-09-12',
        'end': '2026-10-31', 'city': 'San Pietro al Natisone',
        'venue': 'Beneška galerija', 'intro_dates': ('12.09', '31.10'),
        'excerpt_marker': 'questa mostra guarda al marmo',
        'regional_url': 'https://www.turismofvg.it/eventi/mostra-victor-oriecuia-spiriti-amuleti-e-memorie-ancestrali',
    },
    228134: {
        'path': '/not-169209', 'start': '2026-06-13', 'end': '2026-12-31',
        'city': 'Tolmezzo', 'venue': 'Museo Carnico delle Arti Popolari',
        'intro_dates': ('13 giugno', '31 dicembre'),
        'excerpt_marker': 'inaugura una nuova mostra',
        'regional_url': 'https://www.turismofvg.it/eventi/storie-di-erbe-un-percorso-tra-magia-miti-focolare-e-credenze',
    },
}


def _plain(value):
    return engine.clean_event_text(value).replace('\ufffd', '').strip()


def _key(value):
    value = unicodedata.normalize('NFKD', _plain(value).casefold())
    value = ''.join(char for char in value if not unicodedata.combining(char))
    return ' '.join(re.findall(r'[a-z0-9]+', value))


def _museum_locations(payload, programme_html):
    if (not isinstance(payload, dict) or payload.get('id') != 171271
            or payload.get('attribute', {}).get('published') is not True):
        raise ValueError('invalid MESS museum page')
    modules = [part for part in payload.get('modules') or []
               if part.get('module_type') == 'map-cantieri']
    if len(modules) != 1:
        raise ValueError('MESS museum map missing')
    rows = modules[0].get('locations')
    if not isinstance(rows, list) or len(rows) != 18:
        raise ValueError('MESS museum inventory changed')
    if not any('Frazione Pesariis' in str(row.get('address'))
               and str(row.get('address')).endswith(' - Prato Carnico')
               for row in rows):
        raise ValueError('MESS Pesariis municipality evidence missing')
    if 'Fontanabona (Pagnacco)' not in programme_html:
        raise ValueError('MESS Fontanabona municipality evidence missing')
    museums = {}
    names = set()
    for row in rows:
        if (not isinstance(row, dict) or not isinstance(row.get('id'), int)
                or not row.get('nome_sede') or not row.get('address')):
            raise ValueError('invalid MESS museum row')
        address = _plain(row['address'])
        tail = address.rsplit(' - ', 1)[-1]
        city = {'Fontanabona': 'Pagnacco', 'Pesariis': 'Prato Carnico'}.get(tail, tail)
        town = engine.fvg_municipality_catalog.match_names(city)
        if not town or not address or row['id'] in museums:
            raise ValueError('MESS museum municipality unresolved')
        name = _plain(row['nome_sede'])
        key = _key(name)
        if not key or key in names:
            raise ValueError('duplicate MESS museum name')
        names.add(key)
        museums[row['id']] = {'id': row['id'], 'name': name,
                              'city': town.name, 'address': address,
                              'lat': town.latitude, 'lon': town.longitude,
                              'key': key}
    return museums


def _programme_rows(payload):
    if (not isinstance(payload, dict) or payload.get('id') != 171043
            or payload.get('attribute', {}).get('published') is not True):
        raise ValueError('invalid MESS programme page')
    modules = payload.get('modules') or []
    content = [part.get('description') or '' for part in modules
               if part.get('module_type') == 'content']
    accordion = [part for part in modules if part.get('module_type') == 'accordion']
    if len(accordion) != 1 or not isinstance(accordion[0].get('list'), list):
        raise ValueError('MESS programme accordion missing')
    declared = re.search(r'\b(\d{1,3})\s+appuntamenti\b', ' '.join(content), re.I)
    information = ' '.join(str(item.get('description') or '')
                           for item in accordion[0]['list'])
    year_match = re.search(r'\bda agosto a dicembre (20\d{2})\b', _plain(information), re.I)
    if not declared or not year_match or 'due appuntamenti per ogni museo' not in _plain(information):
        raise ValueError('MESS programme count or year missing')
    year = int(year_match[1])
    if year != 2026 or len(REVIEWED_LABORATORY_SLOTS_2026) != 36:
        raise ValueError('unreviewed MESS programme edition')
    candidates = [(item.get('description') or '') for item in accordion[0]['list']
                  if isinstance(item, dict) and '<li' in (item.get('description') or '')]
    if len(candidates) != 1:
        raise ValueError('MESS dated programme not unique')
    html = candidates[0]
    matches = list(re.finditer(r'<li\b[^>]*>(.*?)</li>', html, re.I | re.S))
    if len(matches) != int(declared[1]) or len(matches) != 36:
        raise ValueError('MESS dated programme count differs from declaration')
    rows = []
    for index, match in enumerate(matches):
        expected_date, expected_museum_id = REVIEWED_LABORATORY_SLOTS_2026[index]
        label = _plain(match[1])
        try:
            parsed = re.fullmatch(r'(\d{1,2})\s+([a-z]+)\s*/\s*(.+?)\s+-\s+(.+)',
                                  label, re.I)
            if not parsed:
                raise ValueError('unreadable MESS laboratory label')
            month_text = parsed[2].casefold()
            if month_text in MONTH_TYPO:
                if (year, int(parsed[1]), month_text) != (2026, 28, 'novenbre'):
                    raise ValueError('unreviewed MESS month typo')
                month = MONTH_TYPO[month_text]
            else:
                month = MONTHS.get(month_text)
            if not month:
                raise ValueError('unrecognised MESS laboratory month')
            day = date(year, month, int(parsed[1]))
            if day.isoformat() != expected_date:
                raise ValueError('MESS laboratory slot date changed')
            following = html[match.end():matches[index + 1].start()
                             if index + 1 < len(matches) else len(html)]
            paragraph = re.search(r'<p\b[^>]*>(.*?)</p>', following, re.I | re.S)
            description = _plain(paragraph[1]) if paragraph else ''
            if not description or len(description) < 40:
                raise ValueError('MESS laboratory description missing')
            rows.append({'slot': index + 1, 'museum_id': expected_museum_id,
                         'date': day, 'title': _plain(parsed[3]),
                         'venue_label': _plain(parsed[4]),
                         'description': description, 'date_evidence': label})
        except (TypeError, ValueError) as error:
            rows.append({'slot': index + 1, 'museum_id': expected_museum_id,
                         'date': date.fromisoformat(expected_date),
                         'review_reason': str(error)})
    dates = [date.fromisoformat(day) for day, _ in REVIEWED_LABORATORY_SLOTS_2026]
    if (dates != sorted(dates) or len(set(dates)) != 36
            or dates[0] != date(year, 8, 1) or dates[-1] != date(year, 12, 20)):
        raise ValueError('MESS programme date range inconsistent')
    return rows, html, year


def parse_laboratories(programme, museums_page, *, today):
    rows, programme_html, year = _programme_rows(programme)
    museums = _museum_locations(museums_page, programme_html)
    by_key = {item['key']: item for item in museums.values()}
    expected_by_id = {item['id']: [] for item in museums.values()}
    for day, museum_id in REVIEWED_LABORATORY_SLOTS_2026:
        if museum_id not in expected_by_id:
            raise ValueError('MESS reviewed museum missing from map')
        expected_by_id[museum_id].append(day)
    if (len(expected_by_id) != 18
            or any(len(days) != 2 for days in expected_by_id.values())):
        raise ValueError('MESS two-session-per-museum check failed')
    review_required, slot_records = [], []
    for row in rows:
        reason = row.get('review_reason')
        if not reason:
            key = _key(row['venue_label'])
            museum = (museums.get(VENUE_ALIASES[key])
                      if key in VENUE_ALIASES else by_key.get(key))
            if not museum or museum['id'] != row['museum_id']:
                reason = 'MESS programme museum unresolved or changed'
            else:
                row['museum'] = museum
        active = row['date'] >= today
        disposition = ('past' if not active else
                       'review_required' if reason else 'included')
        slot_records.append({'slot': row['slot'],
                             'date': row['date'].isoformat(),
                             'museum_id': row['museum_id'],
                             'parsed': not bool(reason),
                             'disposition': disposition})
        if reason and active:
            review_required.append({
                'url': PROGRAMME_URL + '#laboratorio-' + str(row['slot']),
                'source_id': f'mess-laboratori-{year}-{row["museum_id"]}-{row["date"].isoformat()}',
                'reason': 'laboratory_requires_review', 'detail': reason,
                'slot': row['slot'],
            })
    events = []
    for row in rows:
        if row['date'] < today or 'museum' not in row:
            continue
        museum = row['museum']
        span = expected_by_id[museum['id']]
        programme_id = f'mess-laboratori-{year}-{museum["id"]}'
        title = row['title']
        event = {
            'source': SOURCE, 'source_id': f'{programme_id}-{row["date"].isoformat()}',
            'title': title, 'url': PROGRAMME_URL,
            'start_date': row['date'].isoformat(),
            'end_date': row['date'].isoformat(),
            'event_city': museum['city'], 'venue': museum['name'],
            'place': museum['name'] + ', ' + museum['city'],
            'address': museum['address'], 'lat': museum['lat'],
            'lon': museum['lon'], 'location_confidence': 'municipality',
            'date_evidence_kind': 'event_schedule',
            'date_evidence': row['date_evidence'] + f' · edizione {year}',
            'schedule_kind': 'explicit_occurrence', 'is_real': True,
            'series_id': 'mess-laboratori', 'programme_id': programme_id,
            'programme_slot': row['slot'],
            'programme_role': 'session', 'edition_id': str(year),
            'programme_title': 'Laboratori MESS · ' + museum['name'],
            'programme_url': PROGRAMME_URL,
            'programme_start_date': span[0],
            'programme_end_date': span[-1],
            'programme_city': museum['city'],
            'programme_place_label': museum['city'],
            'programme_is_multi_place': False,
            'programme_is_multi_venue': False,
            'programme_source': SOURCE,
            'programme_display_mode': 'umbrella',
            **attributed_excerpt(row['description'], source_name=SOURCE,
                                 source_url=PROGRAMME_URL, title=title),
        }
        events.append(event)
    return {'status': 'ok', 'events': events,
            'review_required': review_required,
            'verification': {'collection_mode': 'complete-mess-programme-and-news',
                             'edition_year': year, 'declared_laboratories': 36,
                             'parsed_laboratories': sum('museum' in row for row in rows),
                             'reviewed_laboratories': sum('museum' not in row for row in rows),
                             'active_laboratory_review_count': len(review_required),
                             'slot_records': slot_records,
                             'museum_locations': len(museums),
                             'two_sessions_per_museum': True,
                             'projected_count': len(events),
                             'source_complete': True},
            'coverage': 'official-laboratories-and-museum-addresses'}


def parse_news(category, regional_details, *, today):
    """Recheck the reviewed news inventory and three active exhibition dates."""
    if (not isinstance(category, dict) or category.get('id') != 18221
            or not isinstance(category.get('articles'), list)
            or not 51 <= len(category['articles']) <= 500):
        raise ValueError('MESS news inventory incomplete')
    articles = category['articles']
    ids = [article.get('id') for article in articles if isinstance(article, dict)]
    if len(ids) != len(articles) or len(set(ids)) != len(ids):
        raise ValueError('MESS news IDs missing or repeated')
    by_id = {article['id']: article for article in articles}
    if not set(REVIEWED_NEWS_2026) <= set(by_id):
        raise ValueError('reviewed MESS news disappeared')
    changed_active = set()
    for article in articles:
        try:
            published = date.fromisoformat(str(article['published_date'])[:10])
            modified = date.fromisoformat(str(article['modified'])[:10])
        except (KeyError, TypeError, ValueError):
            raise ValueError('MESS news date metadata invalid') from None
        if published.year == 2026:
            if REVIEWED_NEWS_2026.get(article['id']) != article['modified']:
                if article['id'] in REVIEWED_ACTIVE_NEWS:
                    changed_active.add(article['id'])
                else:
                    raise ValueError('new or changed MESS news requires date review')
        elif ((published.year < 2026 and modified.year >= 2026
               and REVIEWED_HISTORICAL_UPDATES.get(article['id']) != article['modified'])
              or published.year > 2026):
            raise ValueError('unreviewed MESS news edition')
    events = []
    review_required = []
    for article_id, proof in REVIEWED_ACTIVE_NEWS.items():
        article = by_id[article_id]
        if date.fromisoformat(proof['end']) < today:
            continue
        try:
            if article_id in changed_active:
                raise ValueError('MESS active news record changed')
            if (article.get('full_url') != proof['path']
                    or not article.get('title') or not article.get('description')
                    or article.get('published') is not True):
                raise ValueError('MESS exhibition identity changed')
            intro = _plain(article.get('intro')).casefold()
            detail_text = _plain(article['description']).casefold()
            if (proof['city'].casefold() not in intro + ' ' + detail_text
                    or proof['venue'].casefold() not in intro
                    or any(value not in intro for value in proof['intro_dates'])):
                raise ValueError('MESS exhibition dates or venue changed')
            regional = regional_details.get(proof['regional_url'])
            if not isinstance(regional, dict):
                raise ValueError('MESS exhibition corroboration missing')
            start, end = engine.parse_event_date_range(regional.get('date_full') or '')
            if (not start or not end
                    or (start.isoformat(), end.isoformat()) != (proof['start'], proof['end'])
                    or _key(regional.get('event_city')) != _key(proof['city'])):
                raise ValueError('MESS and TurismoFVG exhibition dates disagree')
            paragraphs = [_plain(item) for item in re.findall(
                r'<p\b[^>]*>(.*?)</p>', str(article['description']), re.I | re.S)]
            prose = next((item for item in paragraphs
                          if proof['excerpt_marker'] in item.casefold()
                          and len(item) >= 80 and '\ufffd' not in item), '')
            if not prose:
                raise ValueError('MESS exhibition preview text changed')
            image_path = article.get('preview_image') or ''
            if not re.fullmatch(r'/media/files/erpac_mess/previews/[a-zA-Z0-9_.-]+', image_path):
                raise ValueError('MESS exhibition image missing or untrusted')
            town = engine.fvg_municipality_catalog.match_names(proof['city'])
            if not town:
                raise ValueError('MESS exhibition municipality unknown')
            url = BASE + '/it' + proof['path']
            title = _plain(article['title'])
            events.append({
                'source': SOURCE, 'source_id': f'mess-news-{article_id}',
                'title': title, 'url': url,
                'start_date': proof['start'], 'end_date': proof['end'],
                'event_city': proof['city'], 'venue': proof['venue'],
                'place': proof['venue'] + ', ' + proof['city'],
                'lat': town.latitude, 'lon': town.longitude,
                'location_confidence': 'municipality',
                'image': BASE + image_path,
                'date_evidence_kind': 'event_schedule',
                'date_evidence': _plain(article['intro']) + ' · ' + regional['date_full'],
                'schedule_kind': 'period', 'is_real': True,
                'mess_content_kind': 'news_exhibition',
                **attributed_excerpt(prose, source_name=SOURCE,
                                     source_url=url, title=title),
            })
        except (TypeError, ValueError) as error:
            review_required.append({
                'url': BASE + '/it' + proof['path'],
                'source_id': f'mess-news-{article_id}',
                'reason': 'news_exhibition_requires_review',
                'detail': str(error),
            })

    return events, {'news_category_id': 18221, 'news_records': len(articles),
                    'reviewed_2026_news': len(REVIEWED_NEWS_2026),
                    'corroborated_exhibitions': len(events),
                    'unresolved_news': len(review_required),
                    'news_review_required': review_required}


def collect_mess(*, get=requests.get, today=None):
    today = today or datetime.now(ZoneInfo('Europe/Rome')).date()

    regional_urls = sorted({proof['regional_url'] for proof in REVIEWED_ACTIVE_NEWS.values()})

    def fetch(url):
        if url not in {PROGRAMME_API, MUSEUM_API, NEWS_API} | set(regional_urls):
            raise ValueError('untrusted MESS API URL')
        with get(url, timeout=(4, 15), stream=True, allow_redirects=False) as response:
            response.raise_for_status()
            if response.status_code != 200:
                raise ValueError('unexpected MESS HTTP response')
            chunks, size = [], 0
            for chunk in response.iter_content(65536):
                size += len(chunk)
                if size > 2 * 1024 * 1024:
                    raise ValueError('oversized MESS API response')
                chunks.append(chunk)
        return b''.join(chunks)

    programme = json.loads(fetch(PROGRAMME_API))
    museums = json.loads(fetch(MUSEUM_API))
    news = json.loads(fetch(NEWS_API))

    def fetch_regional(url):
        try:
            return fetch(url)
        except (requests.RequestException, ValueError):
            return None

    with ThreadPoolExecutor(max_workers=3) as pool:
        details = list(pool.map(fetch_regional, regional_urls))

    def parse_regional(body):
        if body is None:
            return None
        try:
            return engine.extract_turismofvg_detail_metadata(
                body.decode('utf-8', errors='replace'))
        except (TypeError, ValueError):
            return None

    regional = {url: parse_regional(body)
                for url, body in zip(regional_urls, details)}
    batch = parse_laboratories(programme, museums, today=today)
    news_events, news_proof = parse_news(news, regional, today=today)
    batch['verification']['laboratory_count'] = len(batch['events'])
    batch['events'].extend(news_events)
    batch['review_required'].extend(news_proof.pop('news_review_required'))
    batch['verification'].update(news_proof)
    batch['verification']['projected_count'] = len(batch['events'])
    batch['coverage'] = 'official-laboratories-museums-news-and-regional-date-corroboration'
    return batch
