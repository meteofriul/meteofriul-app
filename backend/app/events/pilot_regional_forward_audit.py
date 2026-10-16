"""Resumable local inspection of every dated TurismoFVG calendar detail.

This is diagnostic only. It records compact evidence and never writes to the
published catalog. A failed or conflicting detail stays outside verified_event.
"""
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timezone
from pathlib import Path
import argparse
import json
import re

from . import engine
from .pilot_details import (enrich_details, english_provider_date_range,
                            german_provider_date_range)
from .pilot_excerpt import clean_excerpt_text
from .pilot_regional_identity import month_calendar_prose_conflict
from .pilot_regional_sitemap_audit import (AUDIT_SCHEMA, classify_detail,
                                           fetch_detail, write_snapshot)
from .pilot_source_policy import validate_candidate


FORWARD_AUDIT_SCHEMA = 'turismofvg-forward-detail-audit-v1'
MONTH_NAMES = 'gennaio febbraio marzo aprile maggio giugno luglio agosto settembre ottobre novembre dicembre'.split()
EVENT_FIELDS = ('url', 'title', 'event_city', 'lat', 'lon', 'listed_municipalities',
                'location_confidence', 'location_source_url', 'start_date', 'end_date',
                'schedule_kind', 'occurrences', 'verified_programme_occurrences',
                'confirmed_reschedule', 'title_reconciliation',
                'time', 'venue', 'place',
                'provider_categories', 'date_evidence', 'description_excerpt',
                'description_source_name', 'description_source_url',
                'description_checked_at')


def schedule_interpretation(date_text, event):
    """Record what the date row proves, without inventing daily openings."""
    if not date_text:
        return 'date_row_missing'
    explicit_days = engine.parse_turismofvg_discrete_occurrences(date_text)
    if explicit_days:
        return ('explicit_discrete_dates' if explicit_days == (event.get('occurrences') or [])
                else 'discrete_dates_conflict')
    normalized = engine.normalize_for_search(date_text)
    if any(token in normalized for token in ('ogni ', 'tutti ', 'tutte ')):
        return 'recurrence_requires_expansion'
    if not re.search(r'\b20\d{2}\b', date_text):
        return 'date_year_missing'
    start, end = engine.parse_event_date_range(date_text)
    if not start:
        start, end = english_provider_date_range(date_text)
    if not start:
        start, end = german_provider_date_range(date_text)
    if not start or not end:
        return 'date_row_unparsed'
    if start == end:
        return 'single_date'
    if event.get('occurrences'):
        return 'range_with_badges_needs_interpretation'
    return 'bounded_period_needs_opening_evidence'


def month_schedule_verified(date_text, description, listing_days):
    """A month label is usable only when every badge appears in its programme."""
    value = engine.normalize_for_search(date_text)
    match = re.fullmatch(r'(' + '|'.join(MONTH_NAMES) + r')\s+(20\d{2})', value)
    if not match or not listing_days:
        return False
    month, year = MONTH_NAMES.index(match[1]) + 1, int(match[2])
    prose = engine.normalize_for_search(description)
    try:
        days = [date.fromisoformat(day) for day in listing_days]
    except (TypeError, ValueError):
        return False
    return all(day.year == year and day.month == month
               and re.search(rf'\b{day.day}\s+{MONTH_NAMES[month - 1]}\b', prose)
               for day in days)


def create_snapshot(index_snapshot):
    verification = index_snapshot.get('index_verification') or {}
    candidates = index_snapshot.get('calendar_candidates') or []
    urls = [item.get('url') for item in candidates]
    if (index_snapshot.get('schema') != AUDIT_SCHEMA
            or verification.get('horizon_complete') is not True
            or verification.get('declared_results') != verification.get('cards_seen')
            or len(urls) != len(set(urls))
            or any(not engine.is_trusted_turismofvg_event_url(url) for url in urls)
            or set(index_snapshot.get('results') or {}) != set(index_snapshot.get('sitemap_only_urls') or [])
            or index_snapshot.get('attempts')):
        raise ValueError('TurismoFVG source index is not fully inspected')
    return {'schema': FORWARD_AUDIT_SCHEMA,
            'as_of_date': index_snapshot['as_of_date'],
            'index_snapshot_id': index_snapshot['snapshot_id'],
            'created_at': datetime.now(timezone.utc).isoformat(),
            'candidates': candidates, 'results': {}, 'attempts': {}}


def inspect_candidate(candidate, html, *, today):
    url = candidate['url']
    detail = classify_detail(url, html, today=today)
    inspection = enrich_details([candidate], fetch_html=lambda _: html, max_urls=1,
                                allow_description_excerpt=True,
                                allow_unparsed_calendar_for_period=True,
                                allow_dated_experience_exclusion=True,
                                allow_confirmed_reschedule=True,
                                allow_programme_reconciliation=True)
    if inspection['scope_excluded']:
        return {'status': 'non_event_experience',
                'reason': 'reservation_only_experience',
                'detail_status': detail['status']}
    if inspection['review_required']:
        review = inspection['review_required'][0]
        return {'status': 'review_required',
                'reason': review.get('review_reason') or 'detail_conflict',
                'detail_status': detail['status']}
    if inspection['detail_candidates']:
        candidate_result = inspection['detail_candidates'][0]
        return {'status': 'review_required',
                'reason': candidate_result.get('review_reason') or 'detail_not_resolved',
                'detail_status': detail['status']}
    events = inspection['events']
    if len(events) != 1 or events[0].get('detail_status') != 'inspected':
        return {'status': 'review_required', 'reason': 'detail_not_inspected',
                'detail_status': detail['status']}
    event = events[0]
    if month_calendar_prose_conflict(
            detail.get('date_full'), engine.extract_turismofvg_description(html) or '',
            candidate.get('listing_occurrences') or []):
        return {'status': 'review_required', 'reason': 'month_calendar_prose_conflict',
                'detail_status': detail['status']}
    problems = validate_candidate(event, today=today)
    if problems:
        return {'status': 'review_required', 'reason': 'publication_gate',
                'reasons': problems, 'detail_status': detail['status']}
    # Matching a badge to a range does not prove whether every intervening day
    # is open. A separate schedule-kind audit must inspect that meaning.
    month_verified = month_schedule_verified(
        detail.get('date_full'), engine.extract_turismofvg_description(html) or '',
        candidate.get('listing_occurrences') or [])
    return {'status': 'detail_aligned',
            'reason': 'listing_detail_identity_and_date_bounds_match',
            'detail_status': detail['status'],
            'detail_date_full': detail.get('date_full'),
            'schedule_interpretation': ('programme_bounds_corroborated'
                                        if event.get('verified_programme_occurrences')
                                        else schedule_interpretation(detail.get('date_full'), event)),
            'description_status': ('available' if event.get('description_excerpt')
                                   else 'source_text_missing' if not engine.extract_turismofvg_description(html)
                                   else 'unusable_excerpt'),
            'event': {**{key: event[key] for key in EVENT_FIELDS if event.get(key)},
                      **({'month_schedule_verified': True} if month_verified else {})}}


def inspect_batch(snapshot, *, batch_size=24, max_workers=3,
                  max_attempts=3, fetch_html=fetch_detail):
    if (snapshot.get('schema') != FORWARD_AUDIT_SCHEMA
            or not 1 <= batch_size <= 256 or not 1 <= max_workers <= 3
            or not 1 <= max_attempts <= 10):
        raise ValueError('invalid TurismoFVG forward detail batch')
    candidates = snapshot['candidates']
    urls = [item['url'] for item in candidates]
    if len(urls) != len(set(urls)) or any(not engine.is_trusted_turismofvg_event_url(url) for url in urls):
        raise ValueError('invalid TurismoFVG forward detail inventory')
    results = dict(snapshot.get('results') or {})
    attempts = dict(snapshot.get('attempts') or {})
    if set(results) - set(urls) or set(attempts) - set(urls):
        raise ValueError('TurismoFVG forward progress outside inventory')
    todo = sorted((item for item in candidates
                   if item['url'] not in results
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
                results[url] = inspect_candidate(item, future.result(), today=today)
                attempts.pop(url, None)
            except Exception as exc:
                attempts[url] = {'count': attempts.get(url, {}).get('count', 0) + 1,
                                 'last_error_type': type(exc).__name__}
    return {**snapshot, 'results': results, 'attempts': attempts}


def audit_summary(snapshot):
    total = len(snapshot['candidates'])
    results = snapshot['results']
    return {'as_of_date': snapshot['as_of_date'], 'index_snapshot_id': snapshot['index_snapshot_id'],
            'candidates': total, 'inspected': len(results),
            'remaining': total - len(results),
            'retrieval_or_inspection_failures': len(snapshot['attempts']),
            'preview_retryable_failures': len(snapshot.get('preview_attempts') or {}),
            'preview_pending': sum(item.get('status') == 'detail_aligned'
                                   and 'description_status' not in item
                                   for item in results.values()),
            'preview_available': sum(item.get('description_status') == 'available'
                                     for item in results.values()),
            'preview_missing_or_unusable': sum(item.get('description_status') in
                                               {'source_text_missing', 'unusable_excerpt',
                                                'duplicate_across_pages'}
                                               for item in results.values()),
            'schedule_interpretations': {
                kind: sum(item.get('schedule_interpretation') == kind
                          for item in results.values())
                for kind in sorted({item['schedule_interpretation']
                                    for item in results.values()
                                    if item.get('schedule_interpretation')})},
            **{status: sum(item.get('status') == status for item in results.values())
               for status in ('detail_aligned', 'non_event_experience', 'review_required')}}


def reclassify_alignment(snapshot):
    """Correct old diagnostic labels without changing saved event evidence."""
    if snapshot.get('schema') != FORWARD_AUDIT_SCHEMA:
        raise ValueError('invalid TurismoFVG forward detail snapshot')
    results = {}
    for url, item in snapshot['results'].items():
        if item.get('status') == 'verified_event':
            results[url] = {**item, 'status': 'detail_aligned',
                            'reason': 'listing_detail_identity_and_date_bounds_match'}
        else:
            results[url] = item
    return {**snapshot, 'results': results}


def classify_saved_schedules(snapshot):
    if snapshot.get('schema') != FORWARD_AUDIT_SCHEMA:
        raise ValueError('invalid TurismoFVG forward detail snapshot')
    results = {}
    for url, item in snapshot['results'].items():
        if item.get('status') == 'detail_aligned' and item.get('detail_date_full'):
            results[url] = {**item, 'schedule_interpretation': schedule_interpretation(
                item['detail_date_full'], item.get('event') or {})}
        else:
            results[url] = item
    return {**snapshot, 'results': results}


def augment_previews(snapshot, *, batch_size=24, max_workers=3,
                     max_attempts=3, include_duplicates=False,
                     fetch_html=fetch_detail):
    """Recheck an aligned detail and retain only a short attributed preview."""
    if (snapshot.get('schema') != FORWARD_AUDIT_SCHEMA
            or not 1 <= batch_size <= 256 or not 1 <= max_workers <= 3):
        raise ValueError('invalid TurismoFVG preview batch')
    results = dict(snapshot['results'])
    attempts = dict(snapshot.get('preview_attempts') or {})
    candidates = {item['url']: item for item in snapshot['candidates']}
    if set(attempts) - set(candidates):
        raise ValueError('preview progress outside inventory')
    todo = sorted((url for url, item in results.items()
                   if item.get('status') == 'detail_aligned'
                   and ('description_status' not in item
                        or (include_duplicates and item.get('description_status')
                            == 'duplicate_across_pages'))
                   and attempts.get(url, {}).get('count', 0) < max_attempts),
                  key=lambda url: (attempts.get(url, {}).get('count', 0), url))[:batch_size]
    today = date.fromisoformat(snapshot['as_of_date'])
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(fetch_html, url): url for url in todo}
        for future in as_completed(futures):
            url = futures[future]
            try:
                revised = inspect_candidate(candidates[url], future.result(), today=today)
                results[url] = revised
                attempts.pop(url, None)
            except Exception as exc:
                attempts[url] = {'count': attempts.get(url, {}).get('count', 0) + 1,
                                 'last_error_type': type(exc).__name__}
    return {**snapshot, 'results': results, 'preview_attempts': attempts}


def quarantine_duplicate_previews(snapshot):
    """Withhold identical excerpts on distinct pages until context is checked."""
    if snapshot.get('schema') != FORWARD_AUDIT_SCHEMA:
        raise ValueError('invalid TurismoFVG forward detail snapshot')
    titles_by_text = {}
    for url, item in snapshot['results'].items():
        excerpt = (item.get('event') or {}).get('description_excerpt')
        if excerpt:
            title = engine.normalize_for_search((item.get('event') or {}).get('title'))
            titles_by_text.setdefault(clean_excerpt_text(excerpt).casefold(), set()).add(title)
    repeated = {text for text, titles in titles_by_text.items() if len(titles) > 1}
    results = {}
    for url, item in snapshot['results'].items():
        event = item.get('event') or {}
        excerpt = event.get('description_excerpt')
        normalized = clean_excerpt_text(excerpt) if excerpt else ''
        if normalized and normalized.casefold() in repeated:
            event = {key: value for key, value in event.items()
                     if key not in {'description_excerpt', 'description_source_name',
                                    'description_source_url', 'description_checked_at'}}
            results[url] = {**item, 'event': event,
                            'description_status': 'duplicate_across_pages'}
        elif normalized and normalized != excerpt:
            results[url] = {**item, 'event': {**event, 'description_excerpt': normalized}}
        else:
            results[url] = ({**item, 'description_status': 'duplicate_across_pages'}
                            if item.get('description_status') == 'duplicate_boilerplate'
                            else item)
    return {**snapshot, 'results': results}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--snapshot', required=True, type=Path)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--create-from', type=Path)
    group.add_argument('--batch', type=int)
    group.add_argument('--run', action='store_true')
    group.add_argument('--reclassify', action='store_true')
    group.add_argument('--retry-failures', action='store_true')
    group.add_argument('--augment-batch', type=int)
    group.add_argument('--augment-run', action='store_true')
    group.add_argument('--restore-duplicates', action='store_true')
    group.add_argument('--classify-schedules', action='store_true')
    args = parser.parse_args()
    if args.create_from:
        if args.snapshot.exists():
            parser.error('snapshot already exists')
        with args.create_from.open(encoding='utf-8') as stream:
            snapshot = create_snapshot(json.load(stream))
    else:
        with args.snapshot.open(encoding='utf-8') as stream:
            snapshot = json.load(stream)
        if args.reclassify:
            snapshot = reclassify_alignment(snapshot)
        elif args.retry_failures:
            snapshot = {**snapshot, 'attempts': {}}
        elif args.classify_schedules:
            snapshot = classify_saved_schedules(snapshot)
        elif args.augment_run or args.restore_duplicates:
            while True:
                revised = augment_previews(snapshot,
                                           include_duplicates=args.restore_duplicates)
                if (revised['results'] == snapshot['results']
                        and revised['preview_attempts'] == snapshot.get('preview_attempts', {})):
                    break
                snapshot = revised
                write_snapshot(args.snapshot, snapshot)
                if audit_summary(snapshot)['preview_pending'] % 120 < 24:
                    print(json.dumps(audit_summary(snapshot), ensure_ascii=False), flush=True)
            snapshot = quarantine_duplicate_previews(snapshot)
        elif args.augment_batch is not None:
            snapshot = augment_previews(snapshot, batch_size=args.augment_batch)
        elif args.run:
            while True:
                revised = inspect_batch(snapshot)
                if revised['results'] == snapshot['results'] and revised['attempts'] == snapshot['attempts']:
                    break
                snapshot = revised
                write_snapshot(args.snapshot, snapshot)
                if len(snapshot['results']) % 120 < 24:
                    print(json.dumps(audit_summary(snapshot), ensure_ascii=False), flush=True)
        else:
            snapshot = inspect_batch(snapshot, batch_size=args.batch)
    write_snapshot(args.snapshot, snapshot)
    print(json.dumps(audit_summary(snapshot), ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
