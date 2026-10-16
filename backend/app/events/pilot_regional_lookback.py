"""Resumable historical date-window audit for ongoing TurismoFVG events.

This reads official search windows by year, saves each complete window, and
does not publish records. It complements the future calendar and sitemap.
"""
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo
import argparse
import json

from .pilot_regional_filtered import fetch_page, fetch_year, year_search_url
from .pilot_regional_sitemap_audit import write_snapshot


LOOKBACK_SCHEMA = 'turismofvg-retrospective-audit-v1'
EARLIEST_SEARCH_YEAR = 1900


def new_snapshot(*, today, max_years=12):
    if not isinstance(today, date) or not 1 <= max_years <= 50:
        raise ValueError('invalid TurismoFVG retrospective horizon')
    return {'schema': LOOKBACK_SCHEMA, 'as_of_date': today.isoformat(),
            'created_at': datetime.now(timezone.utc).isoformat(),
            'max_years': max_years, 'windows': [], 'cards': [],
            'older_overflow': None, 'horizon_complete': False}


def step_snapshot(snapshot, *, fetch_window=fetch_year, fetch_overflow=fetch_page):
    if snapshot.get('schema') != LOOKBACK_SCHEMA:
        raise ValueError('invalid TurismoFVG retrospective snapshot')
    if snapshot.get('horizon_complete'):
        return snapshot
    today = date.fromisoformat(snapshot['as_of_date'])
    windows = list(snapshot['windows'])
    cards = list(snapshot['cards'])
    first_year = today.year if today > date(today.year, 1, 1) else today.year - 1
    next_year = first_year - len(windows)
    if next_year < EARLIEST_SEARCH_YEAR:
        raise ValueError('TurismoFVG retrospective lower bound reached')
    empty_streak = (len(windows) >= 2
                    and windows[-1]['declared_results'] == 0
                    and windows[-2]['declared_results'] == 0)
    if empty_streak:
        older_end = date(next_year, 12, 31)
        page = fetch_overflow(year_search_url(date(EARLIEST_SEARCH_YEAR, 1, 1), older_end))
        empty = page['total'] == 0 and not page['cards'] and not page['next_url']
        if not empty:
            raise ValueError('TurismoFVG older search has unscanned results')
        return {**snapshot, 'older_overflow': {
                    'start': date(EARLIEST_SEARCH_YEAR, 1, 1).isoformat(),
                    'end': older_end.isoformat(),
                    'declared_results': page['total']},
                'horizon_complete': True}
    if len(windows) >= snapshot['max_years']:
        raise ValueError('TurismoFVG retrospective year limit reached')
    start = date(next_year, 1, 1)
    end = today - timedelta(days=1) if next_year == today.year else date(next_year, 12, 31)
    window = fetch_window(start, end)
    if (window['start'] != start.isoformat() or window['end'] != end.isoformat()
            or window['declared_results'] != window['cards_seen']
            or window['cards_seen'] != len(window['cards'])):
        raise ValueError('TurismoFVG retrospective window incomplete')
    windows.append({key: window[key] for key in
                    ('start', 'end', 'declared_results', 'cards_seen', 'pages')})
    cards.extend(window['cards'])
    return {**snapshot, 'windows': windows, 'cards': cards}


def summary(snapshot):
    return {'as_of_date': snapshot['as_of_date'],
            'windows_scanned': len(snapshot['windows']),
            'last_window': snapshot['windows'][-1] if snapshot['windows'] else None,
            'cards_seen': len(snapshot['cards']),
            'unique_urls': len({card['url'] for card in snapshot['cards']}),
            'older_overflow': snapshot['older_overflow'],
            'horizon_complete': snapshot['horizon_complete']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--snapshot', required=True, type=Path)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--create', action='store_true')
    group.add_argument('--run', action='store_true')
    args = parser.parse_args()
    if args.create:
        if args.snapshot.exists():
            parser.error('snapshot already exists')
        today = datetime.now(ZoneInfo('Europe/Rome')).date()
        snapshot = new_snapshot(today=today)
        write_snapshot(args.snapshot, snapshot)
        print(json.dumps(summary(snapshot), ensure_ascii=False), flush=True)
        return
    with args.snapshot.open(encoding='utf-8') as stream:
        snapshot = json.load(stream)
    while not snapshot['horizon_complete']:
        snapshot = step_snapshot(snapshot)
        write_snapshot(args.snapshot, snapshot)
        print(json.dumps(summary(snapshot), ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
