"""Local, resumable audit of TurismoFVG pages absent from its dated search.

The output is diagnostic. A future detail found here still needs schedule and
location reconciliation before it can enter the pilot catalog.
"""
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timezone
from hashlib import sha256
from pathlib import Path
from zoneinfo import ZoneInfo
from urllib.parse import urlsplit
import argparse
import json
import os
import re
import tempfile
import requests

from . import engine
from .http_client import get_with_single_transient_retry
from .pilot_details import (calendar_occurrences, english_provider_date_range,
                            german_provider_date_range,
                            unscheduled_bookable_experience)
from .pilot_regional_filtered import collect_filtered
from .pilot_regional_index import build_candidate_index
from .pilot_regional_sitemap import discover_detail_urls
from .pilot_schedule import schedule_notice


AUDIT_SCHEMA = 'turismofvg-sitemap-only-audit-v1'
LISTING_MARKER = re.compile(r'\bc-events_result__total\b', re.I)
TITLE = re.compile(r'<h1\b[^>]*>(.*?)</h1>', re.I | re.S)
RECURRENCE = re.compile(r'\b(?:ogni|tutti|tutte|escluso|esclusi|ricorrent[ei])\b', re.I)


def archival_year_result(evidence, *, today):
    """An entirely old explicit year is enough to rule out a future edition."""
    date_text = evidence.get('date_full') or ''
    years = {int(year) for year in re.findall(r'\b20\d{2}\b', date_text)}
    if years and max(years) < today.year and not RECURRENCE.search(date_text):
        return {**evidence, 'status': 'past_event',
                'reason': 'archival_detail_year'}
    return None


def classify_detail(url, html, *, today):
    """Classify only with evidence on the detail page; never infer an edition."""
    if not engine.is_trusted_turismofvg_event_url(url):
        parsed = urlsplit(url)
        if (parsed.scheme == 'https' and parsed.hostname == 'www.turismofvg.it'
                and parsed.port is None and not parsed.query and not parsed.fragment
                and parsed.path.rstrip('/').lower() in engine.TURISMOFVG_NAVIGATION_EVENT_PATHS):
            return {'status': 'non_event', 'reason': 'known_navigation_path'}
        raise ValueError('untrusted TurismoFVG detail URL')
    metadata = engine.extract_turismofvg_detail_metadata(html)
    title_match = TITLE.search(html)
    title = engine.clean_event_text(title_match[1]) if title_match else None
    date_text = metadata.get('date_full') or ''
    city = metadata.get('event_city')
    evidence = {'title': title, 'date_full': date_text or None,
                'event_city': city, 'venue': metadata.get('venue')}
    if not date_text and not city and LISTING_MARKER.search(html):
        return {'status': 'non_event', 'reason': 'event_listing_page',
                **evidence}
    if not title or not date_text or not city:
        return {'status': 'ambiguous', 'reason': 'missing_structured_identity',
                **evidence}
    if schedule_notice(engine.extract_turismofvg_description(html) or ''):
        return {'status': 'ambiguous', 'reason': 'possible_schedule_change',
                **evidence}
    if RECURRENCE.search(date_text):
        return {'status': 'ambiguous', 'reason': 'recurrence_needs_calendar',
                **evidence}
    years = {int(year) for year in re.findall(r'\b20\d{2}\b', date_text)}
    if not years:
        return {'status': 'ambiguous', 'reason': 'year_missing', **evidence}
    occurrences = engine.parse_turismofvg_discrete_occurrences(date_text)
    description = engine.extract_turismofvg_description(html) or ''
    if unscheduled_bookable_experience(
            {**metadata, 'occurrences': occurrences}, description,
            engine.extract_turismofvg_detail_rows(html)):
        start, end = engine.parse_event_date_range(date_text)
        return {'status': 'non_event_experience',
                'reason': 'reservation_only_experience',
                'start_date': start.isoformat(), 'end_date': end.isoformat(),
                **evidence}
    if re.search(r'\bCalendario\s*:', description, re.I):
        labelled = calendar_occurrences(metadata, description)
        if not labelled:
            return {'status': 'ambiguous', 'reason': 'unparsed_explicit_calendar',
                    **evidence}
        occurrences = labelled
    if occurrences:
        start, end = date.fromisoformat(occurrences[0]), date.fromisoformat(occurrences[-1])
    else:
        start, end = engine.parse_event_date_range(date_text)
        if not start:
            start, end = english_provider_date_range(date_text)
        if not start:
            start, end = german_provider_date_range(date_text)
    if not start or not end or end < start:
        return (archival_year_result(evidence, today=today)
                or {'status': 'ambiguous', 'reason': 'unparsed_event_date', **evidence})
    # The legacy range parser fills missing years with the machine's current
    # year. Do not use such a fabricated boundary to discard sitemap pages.
    if start.year not in years or end.year not in years:
        return (archival_year_result(evidence, today=today)
                or {'status': 'ambiguous', 'reason': 'inferred_year_boundary', **evidence})
    if end < today:
        return {'status': 'past_event', 'reason': 'explicit_detail_dates_past',
                'start_date': start.isoformat(), 'end_date': end.isoformat(),
                **evidence}
    return {'status': 'future_candidate', 'reason': 'detail_needs_reconciliation',
            'start_date': start.isoformat(), 'end_date': end.isoformat(),
            **({'occurrences': occurrences} if occurrences else {}), **evidence}


def create_snapshot(sitemap, calendar, *, today):
    index = build_candidate_index(sitemap, calendar)
    verification = dict(index['verification'])
    sitemap_only = verification.pop('sitemap_only_urls')
    fingerprint = sha256(json.dumps({
        'as_of': today.isoformat(), 'sitemap': sitemap['detail_urls'],
        'calendar': calendar['cards'], 'windows': calendar['windows'],
    }, ensure_ascii=False, sort_keys=True).encode('utf-8')).hexdigest()
    return {'schema': AUDIT_SCHEMA, 'as_of_date': today.isoformat(),
            'created_at': datetime.now(timezone.utc).isoformat(),
            'snapshot_id': fingerprint, 'index_verification': verification,
            'calendar_candidates': index['detail_candidates'],
            'index_review_required': index['review_required'],
            'sitemap_only_urls': sitemap_only, 'results': {}, 'attempts': {}}


def fetch_detail(url, *, get=requests.get):
    if not engine.is_trusted_turismofvg_event_url(url):
        raise ValueError('unsafe TurismoFVG detail URL')
    response = get_with_single_transient_retry(
        get, url, timeout=(4, 15), allow_redirects=False,
        headers={'User-Agent': 'Meteo-Friul-Pilot-Catalog/1.0'},
    )
    if response.status_code != 200 or response.url != requests.utils.requote_uri(url):
        raise ValueError('unexpected TurismoFVG detail response')
    content = response.content
    if len(content) > 4 * 1024 * 1024:
        raise ValueError('TurismoFVG detail too large')
    return content.decode('utf-8', errors='replace')


def inspect_batch(snapshot, *, batch_size=24, max_workers=3, fetch_html=fetch_detail):
    if (snapshot.get('schema') != AUDIT_SCHEMA or not 1 <= batch_size <= 256
            or not 1 <= max_workers <= 3):
        raise ValueError('invalid TurismoFVG sitemap audit batch')
    today = date.fromisoformat(snapshot['as_of_date'])
    urls = snapshot['sitemap_only_urls']
    if len(set(urls)) != len(urls) or any(not url.startswith('https://www.turismofvg.it/eventi/') for url in urls):
        raise ValueError('invalid TurismoFVG sitemap inventory')
    results = dict(snapshot.get('results') or {})
    attempts = dict(snapshot.get('attempts') or {})
    if set(results) - set(urls) or set(attempts) - set(urls):
        raise ValueError('TurismoFVG audit progress outside inventory')
    # A persistently failing URL must not occupy the first slot forever.
    todo = sorted((url for url in urls if url not in results),
                  key=lambda url: (attempts.get(url, {}).get('count', 0), url))[:batch_size]
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(fetch_html, url): url for url in todo
                   if engine.is_trusted_turismofvg_event_url(url)}
        for url in todo:
            if not engine.is_trusted_turismofvg_event_url(url):
                results[url] = classify_detail(url, '', today=today)
        for future in as_completed(futures):
            url = futures[future]
            try:
                results[url] = classify_detail(url, future.result(), today=today)
                attempts.pop(url, None)
            except Exception as exc:
                attempts[url] = {'count': attempts.get(url, {}).get('count', 0) + 1,
                                 'last_error_type': type(exc).__name__}
    return {**snapshot, 'results': results, 'attempts': attempts}


def audit_summary(snapshot):
    urls = snapshot['sitemap_only_urls']
    results = snapshot['results']
    counts = {status: sum(item.get('status') == status for item in results.values())
              for status in ('future_candidate', 'past_event', 'non_event',
                             'non_event_experience', 'ambiguous')}
    return {'snapshot_id': snapshot['snapshot_id'], 'as_of_date': snapshot['as_of_date'],
            'sitemap_only_total': len(urls), 'inspected': len(results),
            'remaining_uninspected': len(urls) - len(results),
            'retrieval_failures': len(snapshot['attempts']), **counts}


def reclassify_archival_results(snapshot):
    """Apply stronger past-only evidence to an existing snapshot, without I/O."""
    if snapshot.get('schema') != AUDIT_SCHEMA:
        raise ValueError('invalid TurismoFVG sitemap audit snapshot')
    today = date.fromisoformat(snapshot['as_of_date'])
    results = dict(snapshot['results'])
    for url, result in results.items():
        if (result.get('status') == 'ambiguous'
                and result.get('reason') in {'unparsed_event_date', 'inferred_year_boundary'}):
            results[url] = archival_year_result(result, today=today) or result
    return {**snapshot, 'results': results}


def write_snapshot(path, snapshot):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=path.name + '.', suffix='.tmp', dir=path.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as stream:
            json.dump(snapshot, stream, ensure_ascii=False, indent=2, allow_nan=False)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--snapshot', required=True, type=Path)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--create', action='store_true')
    group.add_argument('--batch', type=int)
    group.add_argument('--reclassify', action='store_true')
    group.add_argument('--recheck-url')
    args = parser.parse_args()
    if args.create:
        if args.snapshot.exists():
            parser.error('snapshot already exists')
        today = datetime.now(ZoneInfo('Europe/Rome')).date()
        sitemap = discover_detail_urls()
        calendar = collect_filtered(today=today)
        snapshot = create_snapshot(sitemap, calendar, today=today)
    else:
        with args.snapshot.open(encoding='utf-8') as stream:
            snapshot = json.load(stream)
        if args.reclassify:
            snapshot = reclassify_archival_results(snapshot)
        elif args.recheck_url:
            if args.recheck_url not in snapshot['sitemap_only_urls']:
                parser.error('URL outside sitemap-only inventory')
            result = classify_detail(args.recheck_url, fetch_detail(args.recheck_url),
                                     today=date.fromisoformat(snapshot['as_of_date']))
            snapshot = {**snapshot,
                        'results': {**snapshot['results'], args.recheck_url: result},
                        'attempts': {key: value for key, value in snapshot['attempts'].items()
                                     if key != args.recheck_url}}
        else:
            snapshot = inspect_batch(snapshot, batch_size=args.batch)
    write_snapshot(args.snapshot, snapshot)
    print(json.dumps(audit_summary(snapshot), ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
