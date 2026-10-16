"""Read TurismoFVG's dated search, retaining each official occurrence card.

This is an audit collector. It does not publish or geolocate records.
"""
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from zoneinfo import ZoneInfo
import math
import re
import requests
import time

from . import engine
from .http_client import get_with_single_transient_retry
from .pilot_regional import declared_result_total


EMPTY_RESULT = re.compile(r'<div>\s*Nessun evento trovato\s*</div>', re.I)
PAGE_SIZE_LIMIT = 384
PARTITION_RESULT_LIMIT = 512
PARTITION_WINDOW_LIMIT = 64


def year_search_url(start, end):
    return engine.TURISMOFVG_EVENTS_URL + '?' + urlencode({
        'hidehighlights': 'true', 'start': start.isoformat(), 'end': end.isoformat(),
    })


def page_url(first_url, page):
    parts = urlsplit(first_url)
    query = [(key, value) for key, value in parse_qsl(parts.query)
             if key.lower() != 'page']
    if page:
        query.append(('page', str(page)))
    return urlunsplit((parts.scheme, parts.netloc, parts.path,
                       urlencode(query), ''))


def page_number(url):
    values = [value for key, value in parse_qsl(urlsplit(url).query)
              if key.lower() == 'page']
    if len(values) != 1 or not values[0].isdigit():
        return None
    return int(values[0])


def fetch_page(url, *, get=requests.get):
    requested = urlsplit(url)
    if requested.scheme != 'https' or requested.hostname != 'www.turismofvg.it' or requested.path != '/eventi':
        raise ValueError('unsafe TurismoFVG search URL')
    try:
        response = get_with_single_transient_retry(
            get, url, timeout=(4, 15),
            headers={'User-Agent': 'Meteo-Friul-Pilot-Catalog/1.0'},
        )
    except (requests.Timeout, requests.ConnectionError):
        # The dated index is large: one reset must not discard an otherwise
        # complete window. Keep this extra attempt local to TurismoFVG.
        time.sleep(1)
        response = get_with_single_transient_retry(
            get, url, timeout=(4, 15),
            headers={'User-Agent': 'Meteo-Friul-Pilot-Catalog/1.0'},
        )
    actual = urlsplit(response.url)
    if (actual.scheme != 'https' or actual.hostname != requested.hostname
            or actual.path != requested.path
            or dict(parse_qsl(actual.query)) != dict(parse_qsl(requested.query))):
        raise ValueError('unexpected TurismoFVG search redirect')
    cards = engine.extract_turismofvg_card_links(response.text, require_explicit_year=True)
    try:
        total = declared_result_total(response.text)
    except ValueError:
        if not EMPTY_RESULT.search(response.text) or cards:
            raise
        total = 0
    next_url = engine.extract_turismofvg_next_page_url(response.text, response.url)
    return {'total': total, 'cards': cards, 'next_url': next_url, 'url': response.url}


def add_year_evidence(card, *, year, start, end):
    result = dict(card)
    badge = card.get('listing_day_month')
    if badge:
        day, last = engine.parse_event_date_range(f'{badge} {year}')
        if day is None or day != last or not start <= day <= end:
            raise ValueError('TurismoFVG badge outside selected year window')
        result['badge_date'] = day.isoformat()
    result['search_window'] = [start.isoformat(), end.isoformat()]
    return result


def fetch_year(start, end, *, get=requests.get, max_workers=3):
    """Fetch an inclusive single-year search with exact page-count checks."""
    if start.year != end.year or end < start or not 1 <= max_workers <= 16:
        raise ValueError('invalid TurismoFVG year window')
    first_url = year_search_url(start, end)
    first = fetch_page(first_url, get=get)
    total = first['total']
    if total == 0:
        if first['cards'] or first['next_url']:
            raise ValueError('nonempty TurismoFVG zero-result page')
        return {'start': start.isoformat(), 'end': end.isoformat(),
                'declared_results': 0, 'cards_seen': 0, 'pages': 1, 'cards': []}
    if not first['cards'] or len(first['cards']) > total:
        raise ValueError('TurismoFVG missing initial cards')
    pages = {0: first}
    if len(first['cards']) < total:
        second_url = first['next_url']
        if not second_url or page_number(second_url) != 1:
            raise ValueError('TurismoFVG missing second page')
        second = fetch_page(second_url, get=get)
        if second['total'] != total or not second['cards']:
            raise ValueError('TurismoFVG changed result total or page size')
        pages[1] = second
        page_size = len(second['cards'])
        page_count = 1 + math.ceil((total - len(first['cards'])) / page_size)
        if page_count > PAGE_SIZE_LIMIT:
            raise ValueError('TurismoFVG page budget exceeded')
        remaining_urls = [page_url(first_url, page) for page in range(2, page_count)]
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(fetch_page, url, get=get): index
                       for index, url in enumerate(remaining_urls, start=2)}
            for future in as_completed(futures):
                pages[futures[future]] = future.result()
    else:
        page_count = 1
        page_size = 0
    cards = []
    for index in range(page_count):
        page = pages[index]
        expected_cards = (len(first['cards']) if index == 0 else
                          min(page_size, total - len(first['cards']) - (index - 1) * page_size))
        if page['total'] != total or len(page['cards']) != expected_cards:
            raise ValueError(
                'TurismoFVG page count differs from declared results: '
                f'page={index}, total={page["total"]}/{total}, '
                f'cards={len(page["cards"])}/{expected_cards}')
        next_url = page['next_url']
        if index + 1 < page_count:
            if not next_url or page_number(next_url) != index + 1:
                raise ValueError('TurismoFVG missing intermediate pagination')
        elif next_url:
            raise ValueError('TurismoFVG unexpected extra pagination')
        cards.extend(add_year_evidence(card, year=start.year, start=start, end=end)
                     for card in page['cards'])
    if len(cards) != total:
        raise ValueError('TurismoFVG incomplete filtered result')
    final = fetch_page(first_url, get=get)
    if final['total'] != total:
        raise ValueError('TurismoFVG changed result total or page size')
    if final['cards'] != first['cards']:
        raise ValueError('TurismoFVG first page changed during scan')
    return {'start': start.isoformat(), 'end': end.isoformat(),
            'declared_results': total, 'cards_seen': len(cards),
            'pages': page_count, 'cards': cards}


def _card_identity(card):
    return (card.get('url'), card.get('badge_date'),
            engine.normalize_for_search(card.get('title')),
            engine.normalize_for_search(card.get('place')))


def fetch_year_partitioned(start, end, *, get=requests.get, max_workers=16,
                           result_limit=PARTITION_RESULT_LIMIT):
    """Scan small dated windows, then reconcile their union with the year.

    The provider returns a card in every window that intersects its event,
    so window totals cannot be added. Exact card identities are deduplicated.
    A changed listing or an unreconciled union fails closed.
    """
    if (start.year != end.year or end < start or not 1 <= max_workers <= 16
            or not 1 <= result_limit <= 512):
        raise ValueError('invalid TurismoFVG partition bounds')
    root = fetch_page(year_search_url(start, end), get=get)
    if root['total'] <= result_limit:
        return fetch_year(start, end, get=get, max_workers=max_workers)

    leaves = []
    pending = [(start, end, root)]
    page_reads = 1
    with ThreadPoolExecutor(max_workers=min(max_workers, 8)) as executor:
        while pending:
            next_windows = []
            child_queries = []
            for first, last, page in pending:
                if page['total'] <= result_limit or first == last:
                    leaves.append((first, last, page))
                    continue
                midpoint = date.fromordinal((first.toordinal() + last.toordinal()) // 2)
                child_queries.extend(((first, midpoint),
                                      (date.fromordinal(midpoint.toordinal() + 1), last)))
            if len(leaves) + len(child_queries) > PARTITION_WINDOW_LIMIT:
                raise ValueError('TurismoFVG partition window budget exceeded')
            futures = {executor.submit(fetch_page, year_search_url(first, last), get=get):
                       (first, last) for first, last in child_queries}
            for future in as_completed(futures):
                first, last = futures[future]
                next_windows.append((first, last, future.result()))
                page_reads += 1
            pending = sorted(next_windows, key=lambda item: item[0])
    if not leaves:
        raise ValueError('TurismoFVG partition has no dated windows')

    window_workers = min(4, max_workers)
    page_workers = max(1, max_workers // window_workers)
    results = {}
    with ThreadPoolExecutor(max_workers=window_workers) as executor:
        futures = {executor.submit(fetch_year, first, last, get=get,
                                   max_workers=page_workers):
                   (first, last, page) for first, last, page in leaves}
        for future in as_completed(futures):
            first, last, page = futures[future]
            result = future.result()
            if result['declared_results'] != page['total']:
                raise ValueError('TurismoFVG partition window changed during scan')
            results[(first, last)] = result
            page_reads += result['pages']

    final = fetch_page(year_search_url(start, end), get=get)
    page_reads += 1
    if final['total'] != root['total'] or final['cards'] != root['cards']:
        raise ValueError('TurismoFVG annual result changed during partition scan')
    unique = {}
    for window in sorted(results):
        for card in results[window]['cards']:
            identity = _card_identity(card)
            material = {key: value for key, value in card.items()
                        if key not in {'search_window', 'start', 'end'}}
            if identity in unique:
                if unique[identity][0] != material:
                    raise ValueError('TurismoFVG overlapping window card changed')
            else:
                unique[identity] = material, card
    if len(unique) != root['total']:
        raise ValueError('TurismoFVG partition union count differs from annual results')
    return {'start': start.isoformat(), 'end': end.isoformat(),
            'declared_results': root['total'], 'cards_seen': len(unique),
            'pages': page_reads,
            'cards': [card for _, card in unique.values()]}


def fetch_year_resilient(start, end, *, get=requests.get, max_workers=16):
    """Prefer the smaller annual scan; partition only after count drift."""
    try:
        return fetch_year(start, end, get=get, max_workers=max_workers)
    except ValueError as exc:
        message = str(exc)
        totals = re.search(r'total=(\d+)/(\d+)', message)
        changed_total = (message.startswith(
            'TurismoFVG page count differs from declared results:')
            and totals is not None and totals.group(1) != totals.group(2))
        if not changed_total and message != 'TurismoFVG changed result total or page size':
            raise
    # A rolling window can stay below the normal 512-result partition
    # threshold while its count changes during parallel page reads. Force
    # smaller dated windows on this retry, then require their exact union to
    # match a stable full-window snapshot.
    return fetch_year_partitioned(start, end, get=get,
                                  max_workers=max_workers,
                                  result_limit=128)


def collect_filtered(*, today=None, get=requests.get, max_years=5):
    """Scan annual windows, then prove no later results through year 2099."""
    today = today or datetime.now(ZoneInfo('Europe/Rome')).date()
    if not isinstance(today, date) or not 1 <= max_years <= 5:
        raise ValueError('invalid TurismoFVG scan horizon')
    windows, cards, empty_streak = [], [], 0
    for offset in range(max_years):
        year = today.year + offset
        start = today if offset == 0 else date(year, 1, 1)
        window = fetch_year(start, date(year, 12, 31), get=get)
        windows.append({key: window[key] for key in
                        ('start', 'end', 'declared_results', 'cards_seen', 'pages')})
        cards.extend(window['cards'])
        empty_streak = empty_streak + 1 if window['declared_results'] == 0 else 0
        if empty_streak >= 2:
            break
    overflow_start = date(today.year + len(windows), 1, 1)
    overflow_end = date(2099, 12, 31)
    if overflow_start > overflow_end:
        raise ValueError('TurismoFVG overflow horizon exceeded')
    overflow = fetch_page(year_search_url(overflow_start, overflow_end), get=get)
    overflow_complete = (overflow['total'] == 0 and not overflow['cards']
                         and not overflow['next_url'])
    return {'status': 'ok', 'collection_mode': 'annual-date-filters',
            'windows': windows, 'cards': cards,
            'cards_seen': len(cards),
            'declared_results': sum(item['declared_results'] for item in windows),
            'pages': sum(item['pages'] for item in windows),
            'unique_urls': len({card['url'] for card in cards}),
            'badge_dates': sum(bool(card.get('badge_date')) for card in cards),
            'overflow': {'start': overflow_start.isoformat(),
                         'end': overflow_end.isoformat(),
                         'declared_results': overflow['total']},
            'horizon_complete': overflow_complete}
