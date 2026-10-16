"""Verified Galleria Spazzapan events across its distinct public inventories."""
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime
import json
import re
from zoneinfo import ZoneInfo

import requests

from . import engine
from .pilot_excerpt import attributed_excerpt


SOURCE = 'Galleria Spazzapan'
BASE = 'https://galleriaspazzapan.regione.fvg.it'
API_ROOT = BASE + '/core/'
SURFACES = {
    'events': 'events/erpac_spazzapan/it/',
    'event_category': 'categories/erpac_spazzapan/it/14038/',
    'current_exhibitions': 'categories/erpac_spazzapan/it/16101/',
    'exhibitions': 'categories/erpac_spazzapan/it/13346/',
    'news': 'categories/erpac_spazzapan/it/15922/',
    'historical_plural': 'categories/erpac_spazzapan/it/16102/',
}
DETAILS = {
    'mario': 75485,
    'paesaggio': 174329,
    'pausig_event': 172996,
    'pausig_exhibition': 173388,
    'fvg7002_exhibition': 173006,
    'fvg7002_news': 172985,
    'fvg_settanta': 170166,
    'together': 170074,
}
EXPECTED_INVENTORIES = {
    'events': {618890, 285613, 616198},
    'event_category': {84819, 233611},
    'current_exhibitions': {232607, 232202, 229043, 229146},
    'exhibitions': {232607, 232202, 229043, 229146, 134335, 121574, 115755},
    'historical_plural': {121574},
}
REVIEWED_NEWS_2026 = {
    84819: '2026-10-05T13:44:44', 233611: '2026-10-09T11:52:48',
    233851: '2026-10-09T11:55:07',
    232171: '2026-10-02T12:03:50', 233615: '2026-10-05T10:44:36',
    233446: '2026-09-30T14:39:19', 232609: '2026-09-30T14:40:15',
    232598: '2026-09-21T09:30:32', 232558: '2026-09-14T13:59:32',
    232257: '2026-09-07T16:15:16', 233567: '2026-10-02T12:02:02',
    232059: '2026-09-01T11:53:02', 232093: '2026-09-01T14:50:47',
    232062: '2026-09-01T11:57:33', 231926: '2026-08-27T14:06:30',
    230747: '2026-07-29T09:14:58', 230286: '2026-07-17T11:20:19',
    229566: '2026-07-01T09:59:55', 228878: '2026-07-01T10:00:24',
    228329: '2026-07-01T10:00:41', 228095: '2026-06-04T10:19:29',
    227895: '2026-05-29T12:21:24', 227906: '2026-05-29T12:40:54',
    227559: '2026-05-25T10:38:13', 226799: '2026-05-13T13:29:06',
    226795: '2026-05-13T13:30:16', 226836: '2026-05-13T13:27:57',
    226791: '2026-05-12T11:36:13', 225999: '2026-04-24T13:31:29',
    224365: '2026-03-24T12:30:55', 223968: '2026-03-17T11:28:45',
    223520: '2026-05-19T15:15:11', 223183: '2026-03-09T13:25:00',
    222936: '2026-05-19T15:13:53', 222709: '2026-02-26T12:07:38',
    222918: '2026-02-26T12:34:50', 222932: '2026-02-26T13:06:48',
    222123: '2026-02-26T12:27:18', 222202: '2026-02-11T12:02:04',
    221801: '2026-02-05T11:49:42', 221645: '2026-01-30T13:54:37',
    221631: '2026-01-30T12:38:07', 221394: '2026-01-23T14:02:56',
    220656: '2026-01-19T14:02:16',
}
REVIEWED_HISTORICAL_UPDATE = {187914: '2026-03-02T09:55:36'}
EVENT_PAGES = {
    '/eventi-collaterali-ottobre-174329': ('2026-10-14', '2026-10-14'),
    '/giornata-del-contemporaneo-2026-75485': ('2026-10-10', '2026-10-10'),
    '/donazione-sergio-pausig-172996': ('2026-09-11', '2026-10-11'),
}
EXHIBITION_PAGES = {
    '/fvg7003-sergio-pausig-173388': 232607,
    '/fvg7002-nuovi-modelli-di-ricerca-173006': 232202,
    '/progetto-togetherinsieme-170074': 229043,
    '/fvg-settanta-170166': 229146,
}
KNOWN_WRONG_EXHIBITION_DATES = ('2026-06-27', '2027-01-15')


def _text(value):
    return engine.clean_event_text(value).strip()


def _date(value):
    return date.fromisoformat(str(value or '')[:10])


def _rows(payload, *, category_id=None):
    if not isinstance(payload, dict) or not isinstance(payload.get('articles'), list):
        raise ValueError('invalid Spazzapan inventory')
    if category_id is not None and payload.get('id') != category_id:
        raise ValueError('Spazzapan category changed')
    articles = payload['articles']
    if any(not isinstance(item, dict) or not isinstance(item.get('id'), int)
           for item in articles):
        raise ValueError('invalid Spazzapan inventory row')
    ids = [item['id'] for item in articles]
    if len(ids) != len(set(ids)):
        raise ValueError('repeated Spazzapan inventory row')
    return articles


def _inventory(surfaces):
    categories = {'event_category': 14038, 'current_exhibitions': 16101,
                  'exhibitions': 13346, 'news': 15922,
                  'historical_plural': 16102}
    rows = {name: _rows(surfaces.get(name), category_id=categories.get(name))
            for name in SURFACES}
    for name, expected in EXPECTED_INVENTORIES.items():
        if {row['id'] for row in rows[name]} != expected:
            raise ValueError('Spazzapan ' + name + ' inventory changed')
    events = {item['full_url']: item for item in rows['events']}
    if (set(events) != set(EVENT_PAGES)
            or {item['full_url'] for item in rows['event_category']}
                != set(EVENT_PAGES) - {'/donazione-sergio-pausig-172996'}):
        raise ValueError('Spazzapan event lists disagree')
    for path, (start, end) in EVENT_PAGES.items():
        if (_date(events[path].get('start_event_date')),
                _date(events[path].get('end_event_date'))) != (
                    date.fromisoformat(start), date.fromisoformat(end)):
            raise ValueError('Spazzapan event API dates changed')
    current = {item['full_url']: item for item in rows['current_exhibitions']}
    if (set(current) != set(EXHIBITION_PAGES)
            or not set(current) <= {item['full_url'] for item in rows['exhibitions']}
            or any(current[path]['id'] != article_id
                   for path, article_id in EXHIBITION_PAGES.items())):
        raise ValueError('Spazzapan exhibition lists disagree')
    for path in list(EXHIBITION_PAGES)[:2]:
        listed = current[path]
        structured = (_date(listed.get('start_event_date_formatted')),
                      _date(listed.get('end_event_date_formatted')))
        allowed = {tuple(date.fromisoformat(value)
                         for value in KNOWN_WRONG_EXHIBITION_DATES),
                   (date(2026, 9, 11), date(2026, 10, 11))
                   if listed['id'] == 232607 else
                   (date(2026, 7, 23), date(2026, 11, 29))}
        if structured not in allowed:
            raise ValueError('Spazzapan exhibition structured dates changed')
    if ({item['id'] for item in rows['historical_plural']} != {121574}
            or any(item.get('published_date', '')[:4] != '2024'
                   for item in rows['historical_plural'])):
        raise ValueError('Spazzapan historical category changed')
    return rows


def _news_review(rows):
    if not 78 <= len(rows) <= 200 or not set(REVIEWED_NEWS_2026) <= {row['id'] for row in rows}:
        raise ValueError('Spazzapan news inventory incomplete')
    for row in rows:
        if row.get('published') is not True:
            raise ValueError('Spazzapan news publication changed')
        try:
            published = _date(row['published_date'])
            modified = _date(row['modified'])
        except (KeyError, TypeError, ValueError):
            raise ValueError('Spazzapan news date metadata invalid') from None
        if published.year == 2026:
            if REVIEWED_NEWS_2026.get(row['id']) != row['modified']:
                raise ValueError('new or changed Spazzapan news requires review')
        elif published.year > 2026 or (modified.year >= 2026 and
                REVIEWED_HISTORICAL_UPDATE.get(row['id']) != row['modified']):
            raise ValueError('unreviewed Spazzapan news edition')
    return {row['id']: row for row in rows}


def _detail(pages, key, *, title=None):
    page = pages.get(key)
    if (not isinstance(page, dict) or page.get('id') != DETAILS[key]
            or page.get('attribute', {}).get('published') is not True
            or not isinstance(page.get('modules'), list)
            or not page['modules']):
        raise ValueError('Spazzapan detail missing: ' + key)
    if title and _text(page['attribute'].get('title')) != title:
        raise ValueError('Spazzapan detail identity changed: ' + key)
    return page


def _module(page, kind, *, title=None):
    found = [item for item in page['modules']
             if item.get('module_type') == kind and
             (title is None or _text(item.get('title')) == title)]
    if len(found) != 1:
        raise ValueError('Spazzapan detail module changed')
    return found[0]


def _image(path):
    if not re.fullmatch(r'/media/files/erpac_spazzapan/previews/(?:[A-Za-z0-9_.-]|%[0-9A-Fa-f]{2})+',
                        str(path or '')):
        raise ValueError('untrusted Spazzapan image')
    return BASE + path


def _exhibition_attribute_dates(page, expected):
    structured = (_date(page['attribute'].get('start_event_date_formatted')),
                  _date(page['attribute'].get('end_event_date_formatted')))
    wrong = tuple(date.fromisoformat(value)
                  for value in KNOWN_WRONG_EXHIBITION_DATES)
    if structured not in {wrong, expected}:
        raise ValueError('Spazzapan exhibition detail dates changed')


def _event(*, source_id, title, path, start, end, venue, evidence,
           description='', image_path=None, today):
    if end < today:
        return None
    town = engine.fvg_municipality_catalog.match_names("Gradisca d'Isonzo")
    if not town:
        raise ValueError('Spazzapan municipality unresolved')
    url = BASE + '/it' + path
    event = {
        'source': SOURCE, 'source_id': str(source_id), 'title': title,
        'url': url, 'start_date': start.isoformat(),
        'end_date': end.isoformat(), 'event_city': town.name,
        'venue': venue, 'place': venue + ', ' + town.name,
        'lat': town.latitude, 'lon': town.longitude,
        'location_confidence': 'municipality',
        'date_evidence_kind': 'event_schedule', 'date_evidence': evidence,
        'schedule_kind': 'period' if start != end else 'single',
        'is_real': True, 'image': _image(image_path),
        **attributed_excerpt(description, source_name=SOURCE,
                             source_url=url, title=title),
    }
    return event


def parse_spazzapan(surfaces, pages, *, today):
    rows = _inventory(surfaces)
    news = _news_review(rows['news'])
    events = []
    for key, title, path, venue in (
            ('mario', 'Mario Palli / Studio Visit',
             '/giornata-del-contemporaneo-2026-75485', 'Studio di Mario Palli'),
            ('paesaggio', 'Nuovo paesaggio. Incontro con Damiano Gullì dalla triennale di Milano',
             '/eventi-collaterali-ottobre-174329',
             "Galleria Regionale d'Arte contemporanea Luigi Spazzapan")):
        page = _detail(pages, key, title=title)
        module = _module(page, 'event', title=title)
        start, end = (date.fromisoformat(value) for value in EVENT_PAGES[path])
        if (_date(module.get('start_event_date')),
                _date(module.get('end_event_date'))) != (start, end):
            raise ValueError('Spazzapan detail event dates disagree')
        article = next(item for item in rows['event_category']
                       if item['full_url'] == path)
        if (article['id'] not in news or _text(article['title']) != title
                or _text(module.get('intro')) != _text(article.get('intro'))):
            raise ValueError('Spazzapan event category/news mismatch')
        intro, prose = _text(module.get('intro')), _text(module.get('description'))
        if key == 'mario':
            if ('10 ottobre 2026' not in prose
                    or 'studio di Mario Palli' not in prose
                    or 'Gradisca' not in prose):
                raise ValueError('Spazzapan Mario date or studio missing')
            excerpt = prose
        else:
            duplicate = news[233851]
            if (duplicate.get('full_url') != '/eventi-collaterali-di-ottobre-174559'
                    or _text(duplicate.get('title')) != title
                    or _text(duplicate.get('intro')) != intro):
                raise ValueError('Spazzapan duplicate news does not match event')
            if ('14 ottobre' not in intro or 'ore 18.00' not in intro
                    or 'Via Marziano Ciotti 51' not in intro
                    or 'Damiano Gullì' not in prose or len(prose) < 200):
                raise ValueError('Spazzapan Paesaggio date/venue changed')
            excerpt = prose
        event = _event(source_id=article['id'], title=title, path=path,
                       start=start, end=end, venue=venue,
                       evidence=intro + ' · API Eventi 2026',
                       description=excerpt,
                       image_path=page['attribute'].get('preview_image'),
                       today=today)
        if event:
            if key == 'paesaggio':
                event['time'] = '18:00'
            events.append(event)

    pausig_event = _detail(pages, 'pausig_event', title='FVG70.03 - Sergio Pausig')
    pausig_exhibition = _detail(pages, 'pausig_exhibition',
                                title='FVG70.03 - Sergio Pausig')
    _exhibition_attribute_dates(pausig_exhibition,
                                (date(2026, 9, 11), date(2026, 10, 11)))
    event_module = _module(pausig_event, 'event', title='FVG70.03 - Sergio Pausig')
    exhibit_module = _module(pausig_exhibition, 'content',
                             title='FVG70.03 - Sergio Pausig')
    pausig_start, pausig_end = date(2026, 9, 11), date(2026, 10, 11)
    if ((_date(event_module.get('start_event_date')),
         _date(event_module.get('end_event_date'))) != (pausig_start, pausig_end)
            or '11 settembre' not in _text(exhibit_module.get('intro'))
            or '11 ottobre 2026' not in _text(exhibit_module.get('intro'))
            or 'via Marziano Ciotti 51' not in _text(event_module.get('intro'))
            or 'all’11 ottobre 2026' not in _text(exhibit_module.get('description'))):
        raise ValueError('Spazzapan Pausig detail date/venue mismatch')
    event = _event(source_id=232607, title='FVG70.03 - Sergio Pausig',
                   path='/fvg7003-sergio-pausig-173388',
                   start=pausig_start, end=pausig_end,
                   venue='Sala Patuna, Galleria Spazzapan',
                   evidence=_text(exhibit_module.get('intro')),
                   description=exhibit_module.get('description'),
                   image_path=pausig_exhibition['attribute'].get('preview_image'),
                   today=today)
    if event:
        events.append(event)

    fvg7002 = _detail(pages, 'fvg7002_exhibition',
                      title='FVG70.02 – Nuovi modelli di ricerca')
    _exhibition_attribute_dates(fvg7002,
                                (date(2026, 7, 23), date(2026, 11, 29)))
    fvg7002_news = _detail(pages, 'fvg7002_news',
                           title='Eventi collaterali di ottobre')
    placeholder = _module(fvg7002, 'content',
                          title='FVG70.02 – Nuovi modelli di ricerca')
    full = _module(fvg7002_news, 'event')
    full_intro = _text(full.get('intro'))
    fvg_start, fvg_end = date(2026, 7, 23), date(2026, 11, 29)
    if ((_date(full.get('start_event_date')),
         _date(full.get('end_event_date'))) != (fvg_start, fvg_end)
            or '23 luglio' not in full_intro
            or '29 novembre 2026' not in full_intro
            or "Gradisca d'Isonzo" not in full_intro
            or 'via Marziano Ciotti 51' not in full_intro
            or '23 luglio' not in _text(placeholder.get('intro'))
            or '29 novembre 2026' not in _text(placeholder.get('intro'))
            or len(_text(full.get('description'))) < 200):
        raise ValueError('Spazzapan FVG70.02 detail date/venue mismatch')
    event = _event(source_id=232202,
                   title='FVG70.02 – Nuovi modelli di ricerca',
                   path='/fvg7002-eventi-collaterali-di-ottobre-172985',
                   start=fvg_start, end=fvg_end,
                   venue='Galleria Spazzapan', evidence=full_intro,
                   description=full.get('description'),
                   image_path=full.get('preview_image'), today=today)
    if event:
        events.append(event)

    umbrella = _detail(pages, 'fvg_settanta')
    together = _detail(pages, 'together')
    if (not _text(umbrella['attribute'].get('title')).startswith('Progetto FVG Settanta')
            or _module(umbrella, 'event').get('end_event_date') !=
               '2027-01-15 00:00:00'
            or not _text(together['attribute'].get('title')).startswith(
                'Progetto Together/Insieme')
            or together['attribute'].get('start_event_date_formatted')
            or together['attribute'].get('end_event_date_formatted')):
        raise ValueError('Spazzapan project exclusion changed')

    events.sort(key=lambda item: (item['start_date'], item['title']))
    return {
        'status': 'ok', 'events': events, 'review_required': [],
        'verification': {
            'collection_mode': 'reconciled-spazzapan-event-exhibition-news',
            'source_complete': True, 'event_api_count': len(rows['events']),
            'event_category_count': len(rows['event_category']),
            'current_exhibition_count': len(rows['current_exhibitions']),
            'exhibition_count': len(rows['exhibitions']),
            'historical_plural_count': len(rows['historical_plural']),
            'news_count': len(rows['news']),
            'reviewed_2026_news': len(REVIEWED_NEWS_2026),
            'verified_distinct_current': 4,
            'projected_count': len(events),
        },
        'coverage': 'official-events-current-exhibitions-news-and-details',
    }


def collect_spazzapan(*, get=requests.get, today=None):
    today = today or datetime.now(ZoneInfo('Europe/Rome')).date()
    urls = {name: API_ROOT + path for name, path in SURFACES.items()}
    urls.update({name: API_ROOT + f'page/erpac_spazzapan/{page_id}/it/'
                 for name, page_id in DETAILS.items()})
    trusted = set(urls.values())

    def fetch(url):
        if url not in trusted:
            raise ValueError('untrusted Spazzapan API URL')
        with get(url, timeout=(3, 9), stream=True, allow_redirects=False) as response:
            response.raise_for_status()
            if response.status_code != 200:
                raise ValueError('unexpected Spazzapan HTTP response')
            chunks, size = [], 0
            for chunk in response.iter_content(65536):
                size += len(chunk)
                if size > 2 * 1024 * 1024:
                    raise ValueError('oversized Spazzapan API response')
                chunks.append(chunk)
        return json.loads(b''.join(chunks))

    with ThreadPoolExecutor(max_workers=8) as pool:
        payloads = dict(zip(urls, pool.map(fetch, urls.values())))
    surfaces = {name: payloads[name] for name in SURFACES}
    pages = {name: payloads[name] for name in DETAILS}
    return parse_spazzapan(surfaces, pages, today=today)
