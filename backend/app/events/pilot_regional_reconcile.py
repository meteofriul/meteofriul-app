"""Reconcile the future search, retrospective search, and detail sitemap.

The report is local diagnostic evidence; it never promotes records.
"""
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, timedelta
from pathlib import Path
import argparse
import json
import requests

from . import engine
from .pilot_regional_forward_audit import FORWARD_AUDIT_SCHEMA, audit_summary as forward_audit_summary
from .pilot_regional_lookback import LOOKBACK_SCHEMA
from .pilot_regional_sitemap_audit import (AUDIT_SCHEMA, classify_detail,
                                           fetch_detail, write_snapshot)


def verify_retrospective(snapshot, *, today):
    if (snapshot.get('schema') != LOOKBACK_SCHEMA
            or snapshot.get('as_of_date') != today.isoformat()
            or snapshot.get('horizon_complete') is not True):
        return False
    windows = snapshot.get('windows') or []
    cards = snapshot.get('cards') or []
    overflow = snapshot.get('older_overflow') or {}
    if len(windows) < 3 or not isinstance(cards, list):
        return False
    try:
        expected_end = today - timedelta(days=1)
        for window in windows:
            start = date.fromisoformat(window['start'])
            end = date.fromisoformat(window['end'])
            if (start != date(expected_end.year, 1, 1) or end != expected_end
                    or window['declared_results'] != window['cards_seen']
                    or window['pages'] < 1):
                return False
            expected_end = start - timedelta(days=1)
        return (windows[-1]['declared_results'] == 0
                and windows[-2]['declared_results'] == 0
                and sum(window['cards_seen'] for window in windows) == len(cards)
                and date.fromisoformat(overflow['start']) == date(1900, 1, 1)
                and date.fromisoformat(overflow['end']) == expected_end
                and overflow['declared_results'] == 0)
    except (KeyError, TypeError, ValueError):
        return False


def reconcile_snapshots(forward, retrospective, forward_details=None):
    if forward.get('schema') != AUDIT_SCHEMA:
        raise ValueError('invalid TurismoFVG forward snapshot')
    today = date.fromisoformat(forward['as_of_date'])
    verification = forward.get('index_verification') or {}
    if (verification.get('horizon_complete') is not True
            or verification.get('declared_results') != verification.get('cards_seen')
            or not verify_retrospective(retrospective, today=today)):
        raise ValueError('TurismoFVG calendar coverage incomplete')
    forward_candidates = forward['calendar_candidates']
    forward_urls = {item['url'] for item in forward_candidates}
    sitemap_only_urls = set(forward['sitemap_only_urls'])
    results = forward['results']
    if (len(forward_urls) != len(forward_candidates)
            or len(sitemap_only_urls) != len(forward['sitemap_only_urls'])
            or set(results) != sitemap_only_urls
            or forward.get('attempts')):
        raise ValueError('TurismoFVG detail index not fully inspected')
    retro_cards = defaultdict(list)
    for card in retrospective['cards']:
        retro_cards[card['url']].append(card)
    retro_urls = set(retro_cards)
    future_candidates, ambiguous, scope_excluded = [], [], []
    for url, result in sorted(results.items()):
        status = result.get('status')
        if status not in {'future_candidate', 'past_event', 'non_event',
                          'non_event_experience', 'ambiguous'}:
            raise ValueError('unexpected TurismoFVG detail classification')
        if status not in {'future_candidate', 'ambiguous', 'non_event_experience'}:
            continue
        badges = sorted({card['badge_date'] for card in retro_cards[url]
                         if card.get('badge_date')})
        item = {'url': url, 'title': result.get('title'),
                'detail_status': status, 'reason': result.get('reason'),
                'date_full': result.get('date_full'), 'historical_badges': badges,
                'historical_card_count': len(retro_cards[url])}
        (future_candidates if status == 'future_candidate' else
         ambiguous if status == 'ambiguous' else scope_excluded).append(item)
    retro_orphans = sorted(retro_urls - forward_urls - sitemap_only_urls)
    missing_sitemap = verification.get('missing_from_sitemap') or []
    detail_report = None
    if forward_details is not None:
        if (forward_details.get('schema') != FORWARD_AUDIT_SCHEMA
                or forward_details.get('as_of_date') != today.isoformat()
                or forward_details.get('index_snapshot_id') != forward['snapshot_id']
                or {item['url'] for item in forward_details.get('candidates') or []} != forward_urls):
            raise ValueError('TurismoFVG forward details belong to another index')
        detail_report = forward_audit_summary(forward_details)
        detail_report['review_details'] = [
            {'url': url, 'reason': result.get('reason'),
             'detail_status': result.get('detail_status')}
            for url, result in sorted(forward_details['results'].items())
            if result.get('status') == 'review_required']
    return {'schema': 'turismofvg-index-reconciliation-v1',
            'as_of_date': today.isoformat(),
            'forward_snapshot_id': forward['snapshot_id'],
            'forward_cards': verification['cards_seen'],
            'forward_urls': len(forward_urls),
            'retrospective_cards': len(retrospective['cards']),
            'retrospective_urls': len(retro_urls),
            'sitemap_urls': verification['sitemap_unique_urls'],
            'calendar_only_urls': len(missing_sitemap),
            'sitemap_only_urls': len(sitemap_only_urls),
            'retrospective_only_urls': len(retro_urls - forward_urls),
            'retrospective_orphan_urls': retro_orphans,
            'orphan_results': {}, 'orphan_attempts': {},
            'union_urls': verification['sitemap_unique_urls']
                + len(missing_sitemap) + len(retro_orphans),
            'detail_classification_counts': {
                status: sum(item['status'] == status for item in results.values())
                for status in ('past_event', 'non_event', 'non_event_experience',
                               'future_candidate', 'ambiguous')},
            'future_detail_candidates': future_candidates,
            'ambiguous_details': ambiguous,
            'scope_excluded_details': scope_excluded,
            'forward_details_pending': (detail_report['remaining'] if detail_report
                                        else len(forward_candidates)),
            'forward_detail_audit': detail_report,
            'publication_ready': False}


def inspect_orphans(report, *, fetch_html=fetch_detail, max_workers=3):
    if report.get('schema') != 'turismofvg-index-reconciliation-v1' or not 1 <= max_workers <= 3:
        raise ValueError('invalid TurismoFVG reconciliation report')
    today = date.fromisoformat(report['as_of_date'])
    urls = report['retrospective_orphan_urls']
    if len(urls) != len(set(urls)) or any(not engine.is_trusted_turismofvg_event_url(url) for url in urls):
        raise ValueError('untrusted retrospective orphan URL')
    results = dict(report.get('orphan_results') or {})
    attempts = dict(report.get('orphan_attempts') or {})
    if set(results) - set(urls) or set(attempts) - set(urls):
        raise ValueError('orphan inspection outside inventory')
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(fetch_html, url): url for url in urls if url not in results}
        for future in as_completed(futures):
            url = futures[future]
            try:
                results[url] = classify_detail(url, future.result(), today=today)
                attempts.pop(url, None)
            except requests.HTTPError as exc:
                response = exc.response
                if response is not None and response.status_code in {404, 410}:
                    results[url] = {'status': 'removed_page', 'reason': f'http_{response.status_code}'}
                    attempts.pop(url, None)
                else:
                    attempts[url] = {'last_error_type': type(exc).__name__}
            except Exception as exc:
                attempts[url] = {'last_error_type': type(exc).__name__}
    return {**report, 'orphan_results': results, 'orphan_attempts': attempts}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--forward-snapshot', required=True, type=Path)
    parser.add_argument('--lookback-snapshot', required=True, type=Path)
    parser.add_argument('--forward-detail-snapshot', type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--inspect-orphans', action='store_true')
    args = parser.parse_args()
    with args.forward_snapshot.open(encoding='utf-8') as stream:
        forward = json.load(stream)
    with args.lookback_snapshot.open(encoding='utf-8') as stream:
        retrospective = json.load(stream)
    forward_details = None
    if args.forward_detail_snapshot:
        with args.forward_detail_snapshot.open(encoding='utf-8') as stream:
            forward_details = json.load(stream)
    report = reconcile_snapshots(forward, retrospective, forward_details)
    if args.inspect_orphans:
        if args.output.exists():
            with args.output.open(encoding='utf-8') as stream:
                previous = json.load(stream)
            if (previous.get('forward_snapshot_id') != report['forward_snapshot_id']
                    or previous.get('as_of_date') != report['as_of_date']):
                raise ValueError('orphan progress belongs to another snapshot')
            report['orphan_results'] = previous.get('orphan_results') or {}
            report['orphan_attempts'] = previous.get('orphan_attempts') or {}
        report = inspect_orphans(report)
    write_snapshot(args.output, report)
    printable = {key: value for key, value in report.items()
                 if key not in {'future_detail_candidates', 'ambiguous_details',
                                'scope_excluded_details', 'retrospective_orphan_urls'}}
    if printable.get('forward_detail_audit'):
        printable['forward_detail_audit'] = {
            key: value for key, value in printable['forward_detail_audit'].items()
            if key != 'review_details'}
    print(json.dumps(printable, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
