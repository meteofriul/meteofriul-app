"""Run the complete TurismoFVG year control inside the shared pilot job."""
from datetime import date, datetime, timedelta, timezone
import time
from zoneinfo import ZoneInfo

from .pilot_regional_display_audit import create_year_display_audit
from .pilot_regional_filtered import fetch_year_partitioned
from .pilot_regional_historical import resolve_historical_years
from .pilot_regional_sitemap import discover_detail_urls
from .pilot_regional_sitemap_audit import fetch_detail
from .pilot_regional_year_control import (create_snapshot, inspect_batch,
                                          reconcile_removed_future,
                                          reconcile_same_edition_duplicates,
                                          summary)


NEAR_HOURS = 48
FAR_HOURS = 96
INACTIVE_HOURS = 7 * 24


def detail_age_limit_hours(result, *, today):
    """Keep near dates freshest for either annual or rolling verification."""
    if result.get('status') == 'detail_aligned':
        event = result.get('event') or {}
        try:
            start = date.fromisoformat(event['start_date'])
        except (KeyError, TypeError, ValueError):
            return NEAR_HOURS
        return NEAR_HOURS if start <= today + timedelta(days=7) else FAR_HOURS
    if result.get('status') in {'excluded_current_year', 'past_event',
                                'non_event', 'non_event_experience'}:
        return INACTIVE_HOURS
    return NEAR_HOURS


def job_results_fresh(control, *, today, now=None):
    now = now or datetime.now(timezone.utc)
    if set(control.get('results') or {}) != set(control.get('entries') or {}):
        return False
    for result in control['results'].values():
        try:
            checked = datetime.fromisoformat(result['checked_at'])
            age = now - checked
        except (KeyError, TypeError, ValueError):
            return False
        if (checked.tzinfo is None or age < timedelta(0)
                or age > timedelta(hours=detail_age_limit_hours(result, today=today))):
            return False
    return True


def _result_within_age(result, *, today, now):
    try:
        checked = datetime.fromisoformat(result['checked_at'])
        age = now - checked
    except (KeyError, TypeError, ValueError):
        return False
    return (checked.tzinfo is not None and timedelta(0) <= age
            <= timedelta(hours=detail_age_limit_hours(result, today=today)))


def known_future_evidence(previous_control, previous_batch):
    """Retain verified distant cards until they enter a later rolling window."""
    prior = previous_control or {}
    evidence = dict(prior.get('known_future') or {})
    for card in (previous_batch or {}).get('events', []):
        url = card.get('url')
        entry = (prior.get('entries') or {}).get(url)
        result = (prior.get('results') or {}).get(url)
        if (url and card.get('start_date') and entry
                and result and result.get('status') == 'detail_aligned'):
            evidence[url] = {'entry': entry, 'result': result}
    return evidence


def _evidence_occurrences(witness):
    result = witness['result']
    event = result.get('event') or {}
    if event.get('verified_programme_occurrences'):
        return event['verified_programme_occurrences']
    if (event.get('schedule_kind') == 'occurrences'
            or result.get('schedule_interpretation') == 'recurrence_requires_expansion'):
        return (event.get('occurrences')
                or (witness['entry'].get('candidate') or {}).get('listing_occurrences')
                or [])
    return None


def evidence_overlaps_window(witness, *, today, window_end):
    """A recurring listing needs an actual date in the publication window."""
    occurrences = _evidence_occurrences(witness)
    if occurrences is not None:
        return any(today.isoformat() <= day <= window_end.isoformat()
                   for day in occurrences if isinstance(day, str))
    event = witness['result'].get('event') or {}
    return ((event.get('start_date') or '') <= window_end.isoformat()
            and (event.get('end_date') or '') >= today.isoformat())


def evidence_has_future_after_window(witness, *, window_end):
    occurrences = _evidence_occurrences(witness)
    if occurrences is not None:
        return any(day > window_end.isoformat()
                   for day in occurrences if isinstance(day, str))
    event = witness['result'].get('event') or {}
    return (event.get('start_date') or '') > window_end.isoformat()


def collect_regional_verified(previous_control=None, *, today=None,
                              fetch_calendar=fetch_year_partitioned,
                              fetch_sitemap=discover_detail_urls,
                              fetch_html=None, max_seconds=335):
    """Collect once for the year, checkpointing a partial result without publishing it."""
    today = today or datetime.now(ZoneInfo('Europe/Rome')).date()
    if not isinstance(today, date) or not 30 <= max_seconds <= 335:
        raise ValueError('invalid TurismoFVG job bounds')
    deadline = time.monotonic() + max_seconds
    calendar = fetch_calendar(date(today.year, 1, 1),
                              date(today.year, 12, 31), max_workers=16)
    sitemap = fetch_sitemap()
    if previous_control and previous_control.get('as_of_date', '')[:4] != str(today.year):
        previous_control = None
    control = create_snapshot(calendar, sitemap, today=today,
                              previous=previous_control,
                              max_result_age_days=7)
    now = datetime.now(timezone.utc)
    retained = {}
    for url, result in control['results'].items():
        try:
            checked = datetime.fromisoformat(result['checked_at'])
            age = now - checked
        except (KeyError, TypeError, ValueError):
            continue
        if (checked.tzinfo is not None and timedelta(0) <= age
                <= timedelta(hours=detail_age_limit_hours(result, today=today))):
            retained[url] = result
    control = {**control, 'results': retained}

    def detail(url):
        return (fetch_html(url) if fetch_html is not None
                else fetch_detail(url))

    refreshed = set()
    while time.monotonic() < deadline - 20:
        pending = [url for url in control['entries']
                   if url not in control['results']
                   and control['attempts'].get(url, {}).get('count', 0) < 3]
        if not pending:
            if set(control['results']) != set(control['entries']):
                break
            now = datetime.now(timezone.utc)
            due = []
            for url, result in control['results'].items():
                if url in refreshed or result.get('status') == 'duplicate_detail':
                    continue
                try:
                    age = now - datetime.fromisoformat(result['checked_at'])
                    limit = detail_age_limit_hours(result, today=today)
                    if age >= timedelta(hours=limit / 2):
                        due.append((age.total_seconds() / (limit * 3600), url))
                except (KeyError, TypeError, ValueError):
                    due.append((1.0, url))
            if not due:
                break
            due.sort(reverse=True)
            chosen = {url for _, url in due[:48]}
            control = {**control, 'results': {
                url: result for url, result in control['results'].items()
                if url not in chosen}}
        updated = inspect_batch(control, batch_size=48, max_workers=16,
                                fetch_html=detail)
        if (updated['results'] == control['results']
                and updated['attempts'] == control['attempts']):
            raise RuntimeError('TurismoFVG detail inspection made no progress')
        refreshed.update(set(updated['results']) - set(control['results']))
        control = updated
    if (set(control['results']) == set(control['entries'])
            and not control['attempts'] and time.monotonic() < deadline - 20):
        control = reconcile_same_edition_duplicates(control)
        control = resolve_historical_years(
            control,
            fetch_window=lambda start, end: fetch_calendar(
                start, end, max_workers=16),
            fetch_html=detail)
        if previous_control:
            control = reconcile_removed_future(control, previous_control)

    stats = summary(control)
    within_budget = time.monotonic() <= deadline
    fresh_details = job_results_fresh(control, today=today)
    complete = stats['source_complete'] and fresh_details
    verification = {'collection_mode': 'complete-annual-year-control',
                    'as_of_date': today.isoformat(),
                    'index_fingerprint': control['index_fingerprint'],
                    'inventory_urls': stats['inventory_urls'],
                    'calendar_pages': stats['calendar_pages'],
                    'source_complete': complete,
                    'near_detail_age_hours': NEAR_HOURS,
                    'far_detail_age_hours': FAR_HOURS,
                    'inactive_detail_age_hours': INACTIVE_HOURS,
                    'within_budget': within_budget,
                    'pending': stats['pending'],
                    'ambiguous': stats['ambiguous'],
                    'review_required': stats['review_required']}
    if not complete or not within_budget:
        return {'status': 'error', 'error_type': 'incomplete_source',
                'year_control': control, 'verification': verification,
                'events': [], 'review_required': [
                    {'url': url, 'reason': result.get('reason')}
                    for url, result in control['results'].items()
                    if result.get('status') in {'ambiguous', 'review_required'}]}
    display = create_year_display_audit(control, today=today)
    if not display['source_complete'] or display['quarantined'] or display['review']:
        return {'status': 'error', 'error_type': 'source_verification_failed',
                'year_control': control, 'verification': verification,
                'events': [], 'review_required': display['review'] + display['quarantined']}
    verification['cards_total'] = len(display['cards'])
    verification['cards_with_preview'] = sum(
        bool(card.get('description_excerpt')) for card in display['cards'])
    return {'status': 'ok', 'events': display['cards'],
            'year_control': control, 'verification': verification,
            'coverage': 'regional-annual-calendar-sitemap-and-details-verified',
            'review_required': []}


def collect_regional_window_verified(previous_control=None, previous_batch=None,
                                     *, today=None,
                                     fetch_calendar=fetch_year_partitioned,
                                     fetch_sitemap=discover_detail_urls,
                                     fetch_html=None, max_seconds=335):
    """Verify the next 45 days, including active events and sitemap changes.

    The first run may inspect the full sitemap. Later runs use the saved
    control to inspect only dated cards, still-active URLs and changed sitemap
    entries. Every listed detail in the window must pass before publication.
    """
    today = today or datetime.now(ZoneInfo('Europe/Rome')).date()
    if not isinstance(today, date) or not 30 <= max_seconds <= 335:
        raise ValueError('invalid TurismoFVG job bounds')
    deadline = time.monotonic() + max_seconds
    window_end = today + timedelta(days=45)
    segments, cards, current_year_window_urls = [], [], set()
    cursor = today
    while cursor <= window_end:
        end = min(window_end, date(cursor.year, 12, 31))
        part = fetch_calendar(cursor, end, max_workers=16)
        if (part.get('start') != cursor.isoformat()
                or part.get('end') != end.isoformat()
                or part.get('declared_results') != part.get('cards_seen')
                or part.get('cards_seen') != len(part.get('cards') or [])
                or not isinstance(part.get('pages'), int) or part['pages'] < 1):
            raise ValueError('incomplete TurismoFVG dated window')
        segments.append({key: part[key] for key in
                         ('start', 'end', 'declared_results', 'cards_seen', 'pages')})
        cards.extend(part['cards'])
        if cursor.year == today.year:
            current_year_window_urls.update(card['url'] for card in part['cards'])
        cursor = end + timedelta(days=1)
    unique = {}
    for card in cards:
        identity = (card.get('url'), card.get('badge_date'),
                    card.get('title'), card.get('place'))
        unique[identity] = card
    calendar = {'start': today.isoformat(), 'end': window_end.isoformat(),
                'declared_results': len(unique), 'cards_seen': len(unique),
                'pages': sum(part['pages'] for part in segments),
                'cards': list(unique.values())}
    sitemap = fetch_sitemap()
    if (sitemap.get('status') != 'ok'
            or sitemap.get('unique_urls') != len(sitemap.get('detail_urls') or [])):
        raise ValueError('incomplete TurismoFVG sitemap')
    listed = {card['url'] for card in calendar['cards']}
    indexed = {item['url']: item for item in sitemap['detail_urls']}
    old_entries = (previous_control or {}).get('entries') or {}
    old_sitemap_index = ((previous_control or {}).get('sitemap_index')
                         or {url: entry.get('sitemap_lastmod')
                             for url, entry in old_entries.items()
                             if entry.get('in_sitemap')})
    future_evidence = known_future_evidence(previous_control, previous_batch)
    due_future = {
        url for url, witness in future_evidence.items()
        if evidence_overlaps_window(witness, today=today, window_end=window_end)
    }
    active_prior = {
        item['url'] for item in (previous_batch or {}).get('events', [])
        if item.get('url') and (item.get('end_date') or '') >= today.isoformat()
        and (not item.get('start_date')
             or item['start_date'] <= window_end.isoformat())
    } | due_future
    carried_prior = sorted(active_prior - listed)
    missing_prior = sorted(set(carried_prior) - set(indexed))
    changed = {
        url for url, item in indexed.items()
        if url not in old_sitemap_index
        or item.get('lastmod') != old_sitemap_index[url]
    }
    selected = listed | active_prior | changed
    narrowed_sitemap = {
        'status': 'ok',
        'detail_urls': [item for item in sitemap['detail_urls']
                        if item['url'] in selected],
        'unique_urls': len(set(indexed) & selected),
    }
    basis = previous_control
    if previous_control and due_future:
        basis = {**previous_control,
                 'entries': {**old_entries,
                             **{url: future_evidence[url]['entry']
                                for url in due_future}},
                 'results': {**(previous_control.get('results') or {}),
                             **{url: future_evidence[url]['result']
                                for url in due_future}}}
    control = create_snapshot(calendar, narrowed_sitemap, today=today,
                              previous=basis, max_result_age_days=7,
                              window_end=window_end,
                              prior_active_urls=carried_prior)
    control.update(calendar_segments=segments,
                   current_year_window_urls=sorted(current_year_window_urls),
                   sitemap_total_urls=sitemap['unique_urls'],
                   sitemap_selected_urls=narrowed_sitemap['unique_urls'],
                   sitemap_index={url: item.get('lastmod')
                                  for url, item in indexed.items()},
                   carried_prior_urls=carried_prior,
                   prior_detail_urls=missing_prior)
    now = datetime.now(timezone.utc)
    control = {**control, 'results': {
        url: result for url, result in control['results'].items()
        if _result_within_age(result, today=today, now=now)
    }}

    def detail(url):
        return fetch_html(url) if fetch_html is not None else fetch_detail(url)

    refreshed = set()
    while time.monotonic() < deadline - 20:
        pending = [url for url in control['entries']
                   if url not in control['results']
                   and control['attempts'].get(url, {}).get('count', 0) < 3]
        if not pending:
            if set(control['results']) != set(control['entries']):
                break
            due = []
            now = datetime.now(timezone.utc)
            for url, result in control['results'].items():
                if url in refreshed or result.get('status') == 'duplicate_detail':
                    continue
                try:
                    age = now - datetime.fromisoformat(result['checked_at'])
                    limit = detail_age_limit_hours(result, today=today)
                    if age >= timedelta(hours=limit / 2):
                        due.append((age.total_seconds() / (limit * 3600), url))
                except (KeyError, TypeError, ValueError):
                    due.append((1.0, url))
            if not due:
                break
            due.sort(reverse=True)
            chosen = {url for _, url in due[:48]}
            control = {**control, 'results': {
                url: result for url, result in control['results'].items()
                if url not in chosen}}
        updated = inspect_batch(control, batch_size=48, max_workers=16,
                                fetch_html=detail)
        if (updated['results'] == control['results']
                and updated['attempts'] == control['attempts']):
            raise RuntimeError('TurismoFVG window inspection made no progress')
        refreshed.update(set(updated['results']) - set(control['results']))
        control = updated
    if (set(control['results']) == set(control['entries'])
            and not control['attempts'] and time.monotonic() < deadline - 20):
        control = reconcile_same_edition_duplicates(control)
        control = resolve_historical_years(
            control, fetch_window=lambda start, end: fetch_calendar(
                start, end, max_workers=16), fetch_html=detail)
    future_evidence.update({
        url: {'entry': control['entries'][url], 'result': result}
        for url, result in control['results'].items()
        if (result.get('status') == 'detail_aligned'
            and evidence_has_future_after_window(
                {'entry': control['entries'][url], 'result': result},
                window_end=window_end))
    })
    control['known_future'] = {
        url: witness for url, witness in future_evidence.items()
        if evidence_has_future_after_window(witness, window_end=window_end)
    }
    stats = summary(control)
    within_budget = time.monotonic() <= deadline
    complete = stats['source_complete'] and job_results_fresh(control, today=today)
    verification = {'collection_mode': 'verified-rolling-45-day-window',
                    'as_of_date': today.isoformat(),
                    'window_end': window_end.isoformat(),
                    'source_complete': complete,
                    'within_budget': within_budget,
                    'index_fingerprint': control['index_fingerprint'],
                    'calendar_pages': stats['calendar_pages'],
                    'inventory_urls': stats['inventory_urls'],
                    'sitemap_total_urls': sitemap['unique_urls'],
                    'sitemap_selected_urls': narrowed_sitemap['unique_urls'],
                    'prior_detail_count': len(missing_prior),
                    'carried_prior_count': len(carried_prior),
                    'known_future_count': len(control['known_future']),
                    'calendar_segments': segments,
                    'pending': stats['pending'],
                    'ambiguous': stats['ambiguous'],
                    'review_required': stats['review_required']}
    if not complete or not within_budget:
        return {'status': 'error', 'error_type': 'incomplete_source',
                'year_control': control, 'verification': verification,
                'events': [], 'review_required': [
                    {'url': url, 'reason': result.get('reason')}
                    for url, result in control['results'].items()
                    if result.get('status') in {'ambiguous', 'review_required'}]}
    display = create_year_display_audit(control, today=today)
    if not display['source_complete'] or display['quarantined'] or display['review']:
        return {'status': 'error', 'error_type': 'source_verification_failed',
                'year_control': control, 'verification': verification,
                'events': [], 'review_required': display['review'] + display['quarantined']}
    verification['cards_total'] = len(display['cards'])
    verification['cards_with_preview'] = sum(
        bool(card.get('description_excerpt')) for card in display['cards'])
    return {'status': 'ok', 'events': display['cards'],
            'year_control': control, 'verification': verification,
            'coverage': 'regional-rolling-calendar-sitemap-delta-and-details-verified',
            'review_required': []}
