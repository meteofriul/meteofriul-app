"""Verify future TurismoFVG details that the official date filter omits."""
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timezone
from pathlib import Path
import argparse
import json

from . import engine
from .pilot_regional_forward_audit import inspect_candidate
from .pilot_regional_sitemap_audit import (AUDIT_SCHEMA, classify_detail,
                                           fetch_detail, write_snapshot)


SCHEMA = 'turismofvg-sitemap-detail-cards-v1'


def create_snapshot(sitemap):
    if (sitemap.get('schema') != AUDIT_SCHEMA or sitemap.get('attempts')
            or set(sitemap.get('results') or {}) != set(sitemap.get('sitemap_only_urls') or [])):
        raise ValueError('incomplete TurismoFVG sitemap-only audit')
    items = [{'url': url, 'title': result['title'],
              'event_city': result['event_city'],
              'date_full': result['date_full']}
             for url, result in sorted(sitemap['results'].items())
             if result.get('status') == 'future_candidate']
    return {'schema': SCHEMA, 'as_of_date': sitemap['as_of_date'],
            'index_snapshot_id': sitemap['snapshot_id'],
            'created_at': datetime.now(timezone.utc).isoformat(),
            'items': items, 'results': {}, 'attempts': {}}


def inspect_item(item, html, *, today):
    detail = classify_detail(item['url'], html, today=today)
    if (detail.get('status') != 'future_candidate'
            or any(engine.normalize_for_search(detail.get(detail_key))
                   != engine.normalize_for_search(item.get(saved_key))
                   for detail_key, saved_key in (('title', 'title'),
                                                 ('event_city', 'event_city'),
                                                 ('date_full', 'date_full')))):
        return {'status': 'review_required', 'reason': 'sitemap_detail_changed'}
    candidate = {'source': 'TurismoFVG', 'url': item['url'],
                 'title': item['title'], 'event_city': item['event_city'],
                 'listing_occurrences': [], 'discovery_kind': 'sitemap_detail'}
    inspected = inspect_candidate(candidate, html, today=today)
    if inspected.get('status') != 'detail_aligned':
        return {'status': 'review_required',
                'reason': inspected.get('reason') or 'detail_not_aligned'}
    return {'status': 'detail_aligned', 'detail_date_full': detail['date_full'],
            'event': inspected['event'],
            'checked_at': datetime.now(timezone.utc).isoformat()}


def inspect_batch(snapshot, *, batch_size=24, max_workers=3,
                  max_attempts=3, fetch_html=fetch_detail):
    if (snapshot.get('schema') != SCHEMA or not 1 <= batch_size <= 256
            or not 1 <= max_workers <= 3):
        raise ValueError('invalid sitemap detail batch')
    items = snapshot['items']
    urls = [item['url'] for item in items]
    if len(urls) != len(set(urls)) or any(not engine.is_trusted_turismofvg_event_url(url) for url in urls):
        raise ValueError('invalid sitemap detail inventory')
    results = dict(snapshot.get('results') or {})
    attempts = dict(snapshot.get('attempts') or {})
    if set(results) - set(urls) or set(attempts) - set(urls):
        raise ValueError('sitemap detail progress outside inventory')
    todo = [item for item in items if item['url'] not in results
            and attempts.get(item['url'], {}).get('count', 0) < max_attempts][:batch_size]
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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--snapshot', required=True, type=Path)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--create-from', type=Path)
    group.add_argument('--batch', type=int)
    args = parser.parse_args()
    if args.create_from:
        if args.snapshot.exists():
            parser.error('snapshot already exists')
        with args.create_from.open(encoding='utf-8') as stream:
            snapshot = create_snapshot(json.load(stream))
    else:
        with args.snapshot.open(encoding='utf-8') as stream:
            snapshot = inspect_batch(json.load(stream), batch_size=args.batch)
    write_snapshot(args.snapshot, snapshot)
    print(json.dumps({'items': len(snapshot['items']),
                      'inspected': len(snapshot['results']),
                      'aligned': sum(item['status'] == 'detail_aligned'
                                     for item in snapshot['results'].values()),
                      'attempts': len(snapshot['attempts'])}, ensure_ascii=False))


if __name__ == '__main__':
    main()
