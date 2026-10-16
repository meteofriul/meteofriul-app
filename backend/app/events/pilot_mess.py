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
        label = _plain(match[1])
        parsed = re.fullmatch(r'(\d{1,2})\s+([a-z]+)\s*/\s*(.+?)\s+-\s+(.+)',
                              label, re.I)
        if not parsed:
            raise ValueError('unreadable MESS laboratory label: ' + label[:120])
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
        following = html[match.end():matches[index + 1].start()
                         if index + 1 < len(matches) else len(html)]
        paragraph = re.search(r'<p\b[^>]*>(.*?)</p>', following, re.I | re.S)
        description = _plain(paragraph[1]) if paragraph else ''
        if not description or len(description) < 40 or '\ufffd' in description:
            raise ValueError('MESS laboratory description missing')
        rows.append({'date': day, 'title': _plain(parsed[3]),
                     'venue_label': _plain(parsed[4]),
                     'description': description, 'date_evidence': label})
    dates = [row['date'] for row in rows]
    if (dates != sorted(dates) or len(set(dates)) != 36
            or dates[0] != date(year, 8, 1) or dates[-1] != date(year, 12, 20)):
        raise ValueError('MESS programme date range inconsistent')
    return rows, html, year


def parse_laboratories(programme, museums_page, *, today):
    rows, programme_html, year = _programme_rows(programme)
    museums = _museum_locations(museums_page, programme_html)
    by_key = {item['key']: item for item in museums.values()}
    by_id = {item['id']: [] for item in museums.values()}
    for row in rows:
        key = _key(row['venue_label'])
        museum = museums.get(VENUE_ALIASES[key]) if key in VENUE_ALIASES else by_key.get(key)
        if not museum:
            raise ValueError('MESS programme museum unresolved: ' + row['venue_label'])
        row['museum'] = museum
        by_id[museum['id']].append(row)
    if len(by_id) != 18 or any(len(items) != 2 for items in by_id.values()):
        raise ValueError('MESS two-session-per-museum check failed')
    events = []
    for row in rows:
        if row['date'] < today:
            continue
        museum = row['museum']
        span = by_id[museum['id']]
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
            'programme_role': 'session', 'edition_id': str(year),
            'programme_title': 'Laboratori MESS · ' + museum['name'],
            'programme_url': PROGRAMME_URL,
            'programme_start_date': span[0]['date'].isoformat(),
            'programme_end_date': span[-1]['date'].isoformat(),
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
            'review_required': [],
            'verification': {'collection_mode': 'complete-mess-programme-and-news',
                             'edition_year': year, 'declared_laboratories': 36,
                             'parsed_laboratories': len(rows),
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
    for article in articles:
        try:
            published = date.fromisoformat(str(article['published_date'])[:10])
            modified = date.fromisoformat(str(article['modified'])[:10])
        except (KeyError, TypeError, ValueError):
            raise ValueError('MESS news date metadata invalid') from None
        if published.year == 2026:
            if REVIEWED_NEWS_2026.get(article['id']) != article['modified']:
                raise ValueError('new or changed MESS news requires date review')
        elif ((published.year < 2026 and modified.year >= 2026
               and REVIEWED_HISTORICAL_UPDATES.get(article['id']) != article['modified'])
              or published.year > 2026):
            raise ValueError('unreviewed MESS news edition')
    events = []
    for article_id, proof in REVIEWED_ACTIVE_NEWS.items():
        article = by_id[article_id]
        if date.fromisoformat(proof['end']) < today:
            continue
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
    return events, {'news_category_id': 18221, 'news_records': len(articles),
                    'reviewed_2026_news': len(REVIEWED_NEWS_2026),
                    'corroborated_exhibitions': len(events),
                    'unresolved_news': 0}


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
    with ThreadPoolExecutor(max_workers=3) as pool:
        details = list(pool.map(fetch, regional_urls))
    regional = {url: engine.extract_turismofvg_detail_metadata(
        body.decode('utf-8', errors='replace')) for url, body in zip(regional_urls, details)}
    batch = parse_laboratories(programme, museums, today=today)
    news_events, news_proof = parse_news(news, regional, today=today)
    batch['verification']['laboratory_count'] = len(batch['events'])
    batch['events'].extend(news_events)
    batch['verification'].update(news_proof)
    batch['verification']['projected_count'] = len(batch['events'])
    batch['coverage'] = 'official-laboratories-museums-news-and-regional-date-corroboration'
    return batch
