"""Verify yearless sitemap details against TurismoFVG's dated archive.

This is a bounded HTML search for unresolved URLs, never a date inferred from
the sitemap timestamp. An exact archived calendar card and the live detail
must agree before an old edition can be excluded.
"""
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from hashlib import sha256
import re

from . import engine
from .pilot_regional_filtered import fetch_year
from .pilot_regional_sitemap_audit import fetch_detail


TITLE = re.compile(r'<h1\b[^>]*>(.*?)</h1>', re.I | re.S)


def _modified_day(entry):
    try:
        return datetime.fromisoformat(
            entry['sitemap_lastmod'].replace('Z', '+00:00')).date()
    except (KeyError, AttributeError, ValueError):
        return None


def _detail_identity(html):
    metadata = engine.extract_turismofvg_detail_metadata(html)
    heading = TITLE.search(html)
    title = engine.clean_event_text(heading[1]) if heading else None
    return (title, metadata.get('event_city'), metadata.get('date_full') or '',
            engine.extract_turismofvg_description(html) or '')


def _description_hash(description):
    return sha256(description.encode('utf-8')).hexdigest()


def recheck_historical_result(entry, html, result, *, today):
    """Keep an archived witness only while its exact live detail is unchanged."""
    if (result.get('status') != 'past_event'
            or result.get('reason') != 'exact_historical_calendar_card'
            or result.get('anchor_sitemap_lastmod') != entry.get('sitemap_lastmod')
            or not isinstance(result.get('programme_year'), int)
            or result['programme_year'] >= today.year):
        return False
    title, city, row, description = _detail_identity(html)
    return (title == result.get('detail_title')
            and city == result.get('detail_city')
            and row == result.get('detail_date_full')
            and _description_hash(description) == result.get('detail_description_sha256'))


def resolve_historical_years(snapshot, *, fetch_window=fetch_year,
                             fetch_html=fetch_detail, now=None):
    """Resolve only old, yearless sitemap URLs with an exact dated search hit.

    One search per historical month is shared by all pending URLs in that
    month. A missed match or a request failure leaves the source incomplete.
    """
    today = date.fromisoformat(snapshot['as_of_date'])
    pending = defaultdict(list)
    results = dict(snapshot['results'])
    for url, result in snapshot['results'].items():
        if (result.get('reason') == 'exact_historical_calendar_card'
                and not result.get('detail_description_sha256')):
            result = {'status': 'ambiguous', 'reason': 'year_missing'}
            results[url] = result
        entry = snapshot['entries'][url]
        modified = _modified_day(entry)
        if (entry.get('kind') == 'sitemap_only'
                and result.get('status') == 'ambiguous'
                and result.get('reason') == 'year_missing'
                and modified and modified.year < today.year):
            pending[(modified.year, modified.month)].append((url, modified))
    if not pending:
        return {**snapshot, 'results': results}

    failures = {}
    for (year, month), items in sorted(pending.items()):
        start = min(modified for _, modified in items)
        end = min(max(modified for _, modified in items) + timedelta(days=31),
                  date(year, 12, 31))
        try:
            archive = fetch_window(start, end)
            if (archive['start'] != start.isoformat()
                    or archive['end'] != end.isoformat()
                    or archive['declared_results'] != archive['cards_seen']
                    or archive['cards_seen'] != len(archive['cards'])):
                raise ValueError('incomplete historical TurismoFVG search')
        except Exception as exc:
            for url, _ in items:
                failures[url] = type(exc).__name__
            continue
        cards = defaultdict(list)
        for card in archive['cards']:
            cards[card['url']].append(card)
        for url, modified in items:
            matches = cards.get(url, [])
            if not matches:
                continue
            try:
                html = fetch_html(url)
                title, city, row, description = _detail_identity(html)
                if (not title or not city or not row or not description
                        or re.search(r'\b20\d{2}\b', row)
                        or any(int(value) >= today.year for value in
                               re.findall(r'\b20\d{2}\b', description))
                        or not all(engine.normalize_for_search(card.get('title'))
                                   == engine.normalize_for_search(title)
                                   and engine.normalize_for_search(card.get('place'))
                                   == engine.normalize_for_search(city)
                                   for card in matches)):
                    continue
                results[url] = {
                    'status': 'past_event',
                    'reason': 'exact_historical_calendar_card',
                    'programme_year': year,
                    'historical_search_window': [start.isoformat(), end.isoformat()],
                    'historical_badges': sorted({card['badge_date'] for card in matches
                                                 if card.get('badge_date')}),
                    'historical_card_count': len(matches),
                    'anchor_sitemap_lastmod': snapshot['entries'][url]['sitemap_lastmod'],
                    'detail_title': title, 'detail_city': city,
                    'detail_date_full': row,
                    'detail_description_sha256': _description_hash(description),
                    'checked_at': (now or datetime.now(timezone.utc)).isoformat(),
                }
            except Exception as exc:
                failures[url] = type(exc).__name__
    return {**snapshot, 'results': results,
            'historical_lookup_failures': failures}
