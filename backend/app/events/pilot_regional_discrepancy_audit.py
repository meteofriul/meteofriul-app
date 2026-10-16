"""Resumable local triage of TurismoFVG calendar/detail discrepancies.

Diagnostics only: a changed or ambiguous page never enters the live catalog.
"""
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timezone
from pathlib import Path
import argparse
import json
import re

from . import engine
from .pilot_details import english_provider_date_range, german_provider_date_range
from .pilot_regional_forward_audit import (FORWARD_AUDIT_SCHEMA,
                                           inspect_candidate)
from .pilot_regional_location import (extract_turismofvg_map_point,
                                      resolve_turismofvg_municipality,
                                      resolve_turismofvg_municipalities,
                                      source_map_is_single_venue)
from .pilot_regional_sitemap_audit import fetch_detail, write_snapshot
from .pilot_schedule import schedule_notice


SCHEMA = 'turismofvg-discrepancy-audit-v1'
NOTICE_PATTERN = re.compile(
    r'\b(?:annullat[oaie]|rinviat[oaie]|posticipat[oaie]|sospes[oaie]|'
    r'cancellat[oaie]|riprogrammat[oaie]|cambio\s+(?:di\s+)?(?:sede|orario)|'
    r'nuova\s+data)\b', re.I)


def create_snapshot(forward):
    if (forward.get('schema') != FORWARD_AUDIT_SCHEMA or forward.get('attempts')
            or set(forward.get('results') or {}) != {
                item['url'] for item in forward.get('candidates') or []}):
        raise ValueError('incomplete TurismoFVG forward detail audit')
    candidates = {item['url']: item for item in forward['candidates']}
    items = [{**candidates[url], 'prior_reason': result.get('reason')}
             for url, result in sorted(forward['results'].items())
             if result.get('status') == 'review_required']
    return {'schema': SCHEMA, 'as_of_date': forward['as_of_date'],
            'index_snapshot_id': forward['index_snapshot_id'],
            'created_at': datetime.now(timezone.utc).isoformat(),
            'items': items, 'results': {}, 'attempts': {}}


def inspect_item(item, html, *, today):
    url = item['url']
    metadata = engine.extract_turismofvg_detail_metadata(html)
    map_point = extract_turismofvg_map_point(html)
    title = re.search(r'<h1\b[^>]*>(.*?)</h1>', html, re.I | re.S)
    detail_title = engine.clean_event_text(title[1]) if title else None
    description = engine.extract_turismofvg_description(html) or ''
    date_text = metadata.get('date_full') or ''
    start, end = engine.parse_event_date_range(date_text)
    if not start:
        start, end = english_provider_date_range(date_text)
    if not start:
        start, end = german_provider_date_range(date_text)
    badges = item.get('listing_occurrences') or []
    flags = []
    if not all((detail_title, date_text, metadata.get('event_city'))):
        flags.append('detail_identity_field_missing')
    if detail_title and (engine.normalize_for_search(detail_title)
                         != engine.normalize_for_search(item.get('title'))):
        flags.append('listing_title_differs')
    if metadata.get('event_city') and (engine.normalize_for_search(metadata['event_city'])
                                        != engine.normalize_for_search(item.get('event_city'))):
        flags.append('listing_city_differs')
    if not start or not end:
        flags.append('detail_date_unparsed')
    elif any(not start <= date.fromisoformat(day) <= end for day in badges):
        flags.append('badge_outside_detail_bounds')
    if not re.search(r'\b20\d{2}\b', date_text):
        flags.append('year_absent_in_detail_date')
    city = metadata.get('event_city')
    mapped_venue = bool(map_point and city and (',' not in city or
                        source_map_is_single_venue(city, metadata.get('venue'))))
    if (city and not resolve_turismofvg_municipality(city)
            and not resolve_turismofvg_municipalities(city)
            and not mapped_venue):
        flags.append('multiple_cities_need_date_mapping' if ',' in city
                     else 'locality_not_in_municipality_catalog')
    notice = NOTICE_PATTERN.search(description)
    notice_context = None
    if notice:
        notice_context = ' '.join(description[
            max(0, notice.start() - 50):min(len(description), notice.end() + 70)
        ].split())
    if schedule_notice(description):
        flags.append('possible_schedule_change')
    live = inspect_candidate(item, html, today=today)
    if live['status'] == 'review_required' and not flags:
        flags.append('promotion_or_policy_needs_review')
    display_fields = ('title', 'event_city', 'venue', 'place', 'lat', 'lon',
                      'listed_municipalities',
                      'location_confidence',
                      'description_excerpt', 'description_source_name',
                      'description_source_url')
    aligned_event = live.get('event') or {}
    return {'status': ('identity_aligned_on_recheck'
                       if live['status'] == 'detail_aligned' else 'review_required'),
            'prior_reason': item.get('prior_reason'),
            'live_reason': live.get('reason'),
            'flags': flags,
            'listing_title': item.get('title'),
            'detail_title': detail_title,
            'listing_city': item.get('event_city'),
            'detail_city': metadata.get('event_city'),
            'listing_occurrences': badges,
            'detail_date_full': date_text or None,
            'detail_start': start.isoformat() if start else None,
            'detail_end': end.isoformat() if end else None,
            'notice_term': notice[0] if notice else None,
            'notice_context': notice_context,
            'description_present': bool(description),
            'preview_available': bool((live.get('event') or {}).get('description_excerpt')),
            **({'event': {key: aligned_event[key] for key in display_fields
                          if aligned_event.get(key)}}
               if live['status'] == 'detail_aligned' else {}),
            'checked_at': datetime.now(timezone.utc).isoformat()}


def refine_saved_flags(snapshot):
    """Classify saved public fields more precisely without fetching again."""
    if snapshot.get('schema') != SCHEMA:
        raise ValueError('invalid TurismoFVG discrepancy snapshot')
    results = {}
    for url, item in snapshot['results'].items():
        flags = [flag for flag in item.get('flags') or []
                 if flag != 'promotion_or_policy_needs_review']
        city = item.get('detail_city') or ''
        if (city and not resolve_turismofvg_municipality(city)
                and not resolve_turismofvg_municipalities(city)
                and (item.get('event') or {}).get('location_confidence') != 'source_map'):
            flag = ('multiple_cities_need_date_mapping' if ',' in city
                    else 'locality_not_in_municipality_catalog')
            if flag not in flags:
                flags.append(flag)
        if not re.search(r'\b20\d{2}\b', item.get('detail_date_full') or ''):
            if 'year_absent_in_detail_date' not in flags:
                flags.append('year_absent_in_detail_date')
        if not flags and item.get('status') == 'review_required':
            flags.append('promotion_or_policy_needs_review')
        results[url] = {**item, 'flags': flags}
    return {**snapshot, 'results': results}


def inspect_batch(snapshot, *, batch_size=24, max_workers=3,
                  max_attempts=3, fetch_html=fetch_detail):
    if (snapshot.get('schema') != SCHEMA or not 1 <= batch_size <= 256
            or not 1 <= max_workers <= 3 or not 1 <= max_attempts <= 10):
        raise ValueError('invalid TurismoFVG discrepancy batch')
    items = snapshot['items']
    urls = [item['url'] for item in items]
    if len(urls) != len(set(urls)) or any(not engine.is_trusted_turismofvg_event_url(url) for url in urls):
        raise ValueError('invalid TurismoFVG discrepancy inventory')
    results = dict(snapshot.get('results') or {})
    attempts = dict(snapshot.get('attempts') or {})
    if set(results) - set(urls) or set(attempts) - set(urls):
        raise ValueError('discrepancy progress outside inventory')
    todo = sorted((item for item in items if item['url'] not in results
                   and attempts.get(item['url'], {}).get('count', 0) < max_attempts),
                  key=lambda item: (attempts.get(item['url'], {}).get('count', 0),
                                    item['url']))[:batch_size]
    today = date.fromisoformat(snapshot['as_of_date'])
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(fetch_html, item['url']): item for item in todo}
        for future in as_completed(futures):
            item = futures[future]
            url = item['url']
            try:
                results[url] = inspect_item(item, future.result(), today=today)
                attempts.pop(url, None)
            except Exception as exc:
                attempts[url] = {'count': attempts.get(url, {}).get('count', 0) + 1,
                                 'last_error_type': type(exc).__name__}
    return {**snapshot, 'results': results, 'attempts': attempts}


def summary(snapshot):
    results = snapshot['results']
    return {'items': len(snapshot['items']), 'inspected': len(results),
            'remaining': len(snapshot['items']) - len(results),
            'attempts': len(snapshot['attempts']),
            'identity_aligned_on_recheck': sum(
                item['status'] == 'identity_aligned_on_recheck' for item in results.values()),
            'review_required': sum(item['status'] == 'review_required'
                                   for item in results.values())}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--snapshot', required=True, type=Path)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--create-from', type=Path)
    group.add_argument('--batch', type=int)
    group.add_argument('--run', action='store_true')
    group.add_argument('--refine-saved', action='store_true')
    group.add_argument('--recheck-notices', action='store_true')
    group.add_argument('--recheck-aligned', action='store_true')
    group.add_argument('--recheck-locality', action='store_true')
    group.add_argument('--recheck-multi-place', action='store_true')
    group.add_argument('--recheck-url')
    group.add_argument('--recheck-resolvable', action='store_true')
    args = parser.parse_args()
    if args.create_from:
        if args.snapshot.exists():
            parser.error('snapshot already exists')
        with args.create_from.open(encoding='utf-8') as stream:
            snapshot = create_snapshot(json.load(stream))
    else:
        with args.snapshot.open(encoding='utf-8') as stream:
            snapshot = json.load(stream)
        if args.refine_saved:
            snapshot = refine_saved_flags(snapshot)
        elif args.recheck_notices:
            snapshot = {**snapshot, 'results': {
                url: item for url, item in snapshot['results'].items()
                if 'possible_schedule_change' not in item.get('flags', [])}}
        elif args.recheck_aligned:
            snapshot = {**snapshot, 'results': {
                url: item for url, item in snapshot['results'].items()
                if item.get('status') != 'identity_aligned_on_recheck'}}
        elif args.recheck_locality:
            snapshot = {**snapshot, 'results': {
                url: item for url, item in snapshot['results'].items()
                if 'locality_not_in_municipality_catalog' not in item.get('flags', [])}}
        elif args.recheck_multi_place:
            snapshot = {**snapshot, 'results': {
                url: item for url, item in snapshot['results'].items()
                if 'multiple_cities_need_date_mapping' not in item.get('flags', [])}}
        elif args.recheck_url:
            if args.recheck_url not in {item['url'] for item in snapshot['items']}:
                parser.error('URL outside discrepancy inventory')
            snapshot = {**snapshot, 'results': {
                url: item for url, item in snapshot['results'].items()
                if url != args.recheck_url}}
        elif args.recheck_resolvable:
            snapshot = {**snapshot, 'results': {
                url: item for url, item in snapshot['results'].items()
                if not set(item.get('flags') or []) & {
                    'listing_title_differs', 'multiple_cities_need_date_mapping'}}}
        elif args.run:
            while True:
                revised = inspect_batch(snapshot)
                if revised['results'] == snapshot['results'] and revised['attempts'] == snapshot['attempts']:
                    break
                snapshot = revised
                write_snapshot(args.snapshot, snapshot)
                if len(snapshot['results']) % 120 < 24:
                    print(json.dumps(summary(snapshot), ensure_ascii=False), flush=True)
        else:
            snapshot = inspect_batch(snapshot, batch_size=args.batch)
    write_snapshot(args.snapshot, snapshot)
    print(json.dumps(summary(snapshot), ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
