"""Incremental, fail-closed TurismoFVG control for the current calendar year.

Runs locally and stores resumable evidence. It never publishes a catalog.
"""
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timedelta, timezone
from hashlib import sha256
from pathlib import Path
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo
import argparse
import json
import re
import requests

from . import engine
from .pilot_details import english_provider_date_range, german_provider_date_range
from .pilot_regional_filtered import fetch_year
from .pilot_regional_historical import resolve_historical_years
from .pilot_regional_forward_audit import inspect_candidate
from .pilot_regional_sitemap import discover_detail_urls
from .pilot_regional_sitemap_audit import classify_detail, fetch_detail, write_snapshot
from .pilot_regional_year_exclusions import (MONTH, WEEKDAY,
                                             current_year_exclusion, plain)
from .pilot_regional_year_recovery import (recover_current_year_detail,
                                           recover_barcolana_2026_locale,
                                           recover_calendar_anchored_weekends,
                                           recover_discrete_edition,
                                           recover_end_only_exhibition,
                                           recover_month_range_exhibition,
                                           recover_prior_edition_in_description)


SCHEMA = 'turismofvg-current-year-control-v1'
INSPECTION_VERSION = 10
REFRESH_DAYS = {'detail_aligned': 1, 'past_event': 30,
                'non_event': 30, 'non_event_experience': 30}


def _fingerprint(value):
    data = json.dumps(value, sort_keys=True, ensure_ascii=False,
                      separators=(',', ':')).encode('utf-8')
    return sha256(data).hexdigest()


def create_snapshot(calendar, sitemap, *, today, previous=None, now=None,
                    max_result_age_days=None, window_end=None,
                    prior_active_urls=()):
    """Only a complete, explicitly bounded index may carry old detail results."""
    now = now or datetime.now(timezone.utc)
    if max_result_age_days is not None and not 1 <= max_result_age_days <= 30:
        raise ValueError('invalid TurismoFVG result age')
    start, end = ((today, window_end) if window_end is not None
                  else (date(today.year, 1, 1), date(today.year, 12, 31)))
    if window_end is not None and (end < start or end > today + timedelta(days=45)):
        raise ValueError('invalid TurismoFVG control window')
    cards = calendar.get('cards') or []
    sitemap_urls = sitemap.get('detail_urls') or []
    if (calendar.get('start') != start.isoformat()
            or calendar.get('end') != end.isoformat()
            or calendar.get('declared_results') != calendar.get('cards_seen')
            or calendar.get('cards_seen') != len(cards)
            or not isinstance(calendar.get('pages'), int)
            or calendar['pages'] < 1
            or sitemap.get('status') != 'ok'
            or sitemap.get('unique_urls') != len(sitemap_urls)):
        raise ValueError('incomplete TurismoFVG current-year index')
    sitemap_dates = {item['url']: item.get('lastmod') for item in sitemap_urls}
    if len(sitemap_dates) != len(sitemap_urls):
        raise ValueError('duplicate TurismoFVG sitemap URL')
    grouped = defaultdict(list)
    seen_cards = set()
    for card in cards:
        url = card.get('url')
        if not engine.is_trusted_turismofvg_event_url(url):
            raise ValueError('untrusted TurismoFVG calendar URL: ' + str(url)[:300])
        badge = card.get('badge_date')
        if badge and not start <= date.fromisoformat(badge) <= end:
            raise ValueError('calendar badge outside verified window')
        identity = (url, badge, engine.normalize_for_search(card.get('title')),
                    engine.normalize_for_search(card.get('place')))
        if identity in seen_cards:
            raise ValueError('duplicate TurismoFVG calendar card')
        seen_cards.add(identity)
        grouped[url].append(card)
    entries = {}
    for url in sorted(set(grouped) | set(sitemap_dates)):
        listing = grouped.get(url) or []
        titles = sorted({engine.normalize_for_search(card.get('title'))
                         for card in listing})
        cities = sorted({card['place'] for card in listing if card.get('place')})
        badges = sorted({card['badge_date'] for card in listing if card.get('badge_date')})
        candidate = ({'source': 'TurismoFVG', 'url': url,
                      'title': listing[0].get('title'),
                      'event_city': cities[0] if len(cities) == 1 else None,
                      'listing_places': cities, 'listing_occurrences': badges,
                      'listing_card_count': len(listing),
                      'discovery_kind': 'filtered_calendar'} if listing else None)
        identity_conflict = bool(listing and (len(titles) != 1 or not titles[0]))
        signature = _fingerprint({'candidate': candidate,
                                  'identity_conflict': identity_conflict,
                                  'lastmod': sitemap_dates.get(url)})
        entries[url] = {'signature': signature,
                        'kind': 'calendar' if listing else 'sitemap_only',
                        'in_sitemap': url in sitemap_dates,
                        'sitemap_lastmod': sitemap_dates.get(url),
                        'identity_conflict': identity_conflict,
                        'listing_display': {
                            'category': listing[0].get('classification', {}).get('category'),
                            'image': listing[0].get('image'),
                        } if listing else {},
                        **({'candidate': candidate} if candidate else {})}
    for url in prior_active_urls:
        if not engine.is_trusted_turismofvg_event_url(url):
            raise ValueError('invalid prior TurismoFVG event URL')
        prior_entry = (previous or {}).get('entries', {}).get(url) or {}
        prior_result = (previous or {}).get('results', {}).get(url) or {}
        if (prior_entry.get('candidate')
                and prior_result.get('status') == 'detail_aligned'):
            entry = {**(entries.get(url) or {}),
                     'kind': 'calendar', 'listing_origin': 'prior_verified',
                     'in_sitemap': url in sitemap_dates,
                     'sitemap_lastmod': sitemap_dates.get(url),
                     'identity_conflict': False,
                     'candidate': prior_entry['candidate'],
                     'listing_display': prior_entry.get('listing_display', {})}
            entry['signature'] = _fingerprint({
                'prior_verified': prior_entry['candidate'],
                'lastmod': entry['sitemap_lastmod']})
            entries[url] = entry
        elif url not in entries:
            entries[url] = {
                'signature': _fingerprint({'prior_active_detail': url}),
                'kind': 'prior_detail', 'in_sitemap': False,
                'sitemap_lastmod': None, 'identity_conflict': False,
                'listing_display': prior_entry.get('listing_display', {}),
            }
    if previous is not None:
        previous_day = date.fromisoformat(previous['as_of_date'])
        if (previous.get('schema') != SCHEMA
                or previous_day > today
                or (previous_day.year != today.year if window_end is None
                    else previous_day < today - timedelta(days=30))):
            raise ValueError('unrelated TurismoFVG year-control snapshot')
    retained = {}
    for url, entry in entries.items():
        prior_entry = (previous or {}).get('entries', {}).get(url) or {}
        prior_result = (previous or {}).get('results', {}).get(url) or {}
        if prior_result.get('status') in {'duplicate_detail', 'ambiguous',
                                          'review_required'}:
            continue
        if (entry['signature'] != prior_entry.get('signature')
                or (previous or {}).get('inspection_version', INSPECTION_VERSION)
                   != INSPECTION_VERSION):
            continue
        try:
            checked = datetime.fromisoformat(prior_result['checked_at'])
            age = now - checked
        except (KeyError, TypeError, ValueError):
            continue
        max_age = (max_result_age_days if max_result_age_days is not None else
                   1 if prior_result.get('reason') ==
                   'exact_historical_calendar_card' else
                   REFRESH_DAYS.get(prior_result.get('status'), 1))
        if checked.tzinfo and timedelta(0) <= age <= timedelta(days=max_age):
            retained[url] = prior_result
    removed, removed_future = (removed_from_previous(entries, previous, today=today)
                                if window_end is None else ([], []))
    return {'schema': SCHEMA, 'inspection_version': INSPECTION_VERSION,
            'as_of_date': today.isoformat(),
            **({'window_end': window_end.isoformat()} if window_end else {}),
            'created_at': now.isoformat(),
            'index_fingerprint': _fingerprint({url: item['signature']
                                               for url, item in entries.items()}),
            'declared_results': calendar['declared_results'],
            'calendar_pages': calendar['pages'],
            'calendar_urls': len(grouped), 'sitemap_urls': len(sitemap_dates),
            'entries': entries, 'results': retained, 'attempts': {},
            'removed_urls': removed, 'removed_future_urls': removed_future}


def results_within_age(snapshot, *, now=None, max_hours=48):
    """Independent freshness gate for a job checkpoint's complete inventory."""
    now = now or datetime.now(timezone.utc)
    if (not isinstance(max_hours, int) or not 1 <= max_hours <= 720
            or set(snapshot.get('results') or {}) != set(snapshot.get('entries') or {})):
        return False
    for result in snapshot['results'].values():
        try:
            checked = datetime.fromisoformat(result['checked_at'])
            age = now - checked
        except (KeyError, TypeError, ValueError):
            return False
        if not checked.tzinfo or not timedelta(0) <= age <= timedelta(hours=max_hours):
            return False
    return True


def removed_from_previous(entries, previous, *, today):
    """Flag vanished URLs that could still occur in the current year."""
    if previous is not None and (
            previous.get('schema') != SCHEMA
            or date.fromisoformat(previous['as_of_date']).year != today.year
            or previous['as_of_date'] > today.isoformat()):
        raise ValueError('unrelated TurismoFVG year-control snapshot')
    removed = sorted(set((previous or {}).get('entries', {})) - set(entries))
    removed_future = []
    year_end = date(today.year, 12, 31)
    for url in removed:
        old_entry = previous['entries'][url]
        old_result = previous.get('results', {}).get(url) or {}
        if old_result.get('status') in {'past_event', 'non_event',
                                        'non_event_experience', 'excluded_current_year'}:
            continue
        old_badges = (old_entry.get('candidate') or {}).get('listing_occurrences') or []
        date_text = old_result.get('detail_date_full') or ''
        start_day, end_day = engine.parse_event_date_range(date_text)
        if not end_day:
            start_day, end_day = english_provider_date_range(date_text)
        if not end_day:
            start_day, end_day = german_provider_date_range(date_text)
        if (any(today.isoformat() <= day <= year_end.isoformat()
                for day in old_badges)
                or end_day and end_day >= today
                and (start_day is None or start_day <= year_end)):
            removed_future.append(url)
    return removed, removed_future


def reconcile_removed_future(snapshot, previous):
    """Accept a changed URL only after an exact, uniquely inspected identity.

    Title, municipality and both date bounds must agree. Ambiguous matches,
    uninspected replacements and withdrawn events remain in review.
    """
    today = date.fromisoformat(snapshot['as_of_date'])
    removed, future = removed_from_previous(snapshot['entries'], previous,
                                            today=today)
    def identity(event):
        if not event:
            return None
        title = engine.normalize_for_search(event.get('title'))
        city = engine.normalize_for_search(event.get('event_city'))
        start, end = event.get('start_date'), event.get('end_date')
        try:
            if not title or not city or date.fromisoformat(start) > date.fromisoformat(end):
                return None
        except (TypeError, ValueError):
            return None
        return title, city, start, end
    current = defaultdict(list)
    for url, result in snapshot['results'].items():
        if result.get('status') == 'detail_aligned':
            key = identity(result.get('event'))
            if key:
                current[key].append(url)
    replaced, unresolved = {}, []
    for url in future:
        prior = (previous.get('results') or {}).get(url) or {}
        key = identity(prior.get('event')) if prior.get('status') == 'detail_aligned' else None
        matches = current.get(key, []) if key else []
        if len(matches) == 1:
            replaced[url] = matches[0]
        else:
            unresolved.append(url)
    return {**snapshot, 'removed_urls': removed,
            'replaced_urls': replaced,
            'removed_future_urls': unresolved}


def seed_same_day_audits(snapshot, *, forward, sitemap_audit,
                         discrepancy, sitemap_cards, added, display, semantic):
    """Carry this audit's already-read details into the first annual baseline.

    Calendar identity and future badges must still match the fresh year index.
    Later cycles reuse only this module's signed entries via create_snapshot.
    """
    as_of = snapshot['as_of_date']
    if (snapshot.get('schema') != SCHEMA or snapshot.get('results')
            or any(source.get('as_of_date') != as_of for source in
                   (forward, sitemap_audit, discrepancy, sitemap_cards,
                    added, display, semantic))):
        raise ValueError('mismatched TurismoFVG bootstrap audits')
    old_candidates = {item['url']: item for item in forward['candidates']}
    reviews = {item['url']: item['reason'] for item in display['review']}
    seeded = {}
    for url, entry in snapshot['entries'].items():
        old = old_candidates.get(url)
        current = entry.get('candidate') or {}
        if old:
            if entry['kind'] == 'calendar':
                old_days = {day for day in old.get('listing_occurrences') or []
                            if as_of <= day <= f'{as_of[:4]}-12-31'}
                new_days = {day for day in current.get('listing_occurrences') or []
                            if as_of <= day <= f'{as_of[:4]}-12-31'}
                same = (old_days == new_days
                        and engine.normalize_for_search(old.get('title')) ==
                            engine.normalize_for_search(current.get('title'))
                        and engine.normalize_for_search(old.get('event_city')) ==
                            engine.normalize_for_search(current.get('event_city')))
            else:
                same = not any(as_of <= day <= f'{as_of[:4]}-12-31'
                               for day in old.get('listing_occurrences') or [])
            if (old.get('sitemap_lastmod') and entry.get('sitemap_lastmod')
                    and old['sitemap_lastmod'] != entry['sitemap_lastmod']):
                same = False
            if not same:
                continue
            prior = forward['results'].get(url) or {}
            rechecked = discrepancy['results'].get(url) or {}
            if rechecked.get('status') == 'identity_aligned_on_recheck':
                prior = {'status': 'detail_aligned',
                         'detail_date_full': rechecked.get('detail_date_full'),
                         'schedule_interpretation': prior.get('schedule_interpretation'),
                         'event': rechecked.get('event') or {}}
            elif rechecked.get('status') == 'review_required':
                prior = {'status': 'review_required',
                         'reason': rechecked.get('live_reason')}
            if url in reviews:
                prior = {'status': 'review_required', 'reason': reviews[url]}
            if prior.get('status'):
                checked = (rechecked.get('checked_at')
                           or (semantic.get('results', {}).get(url) or {}).get('checked_at')
                           or (prior.get('event') or {}).get('description_checked_at')
                           or forward.get('created_at'))
                seeded[url] = {**prior, 'checked_at': checked,
                               'reused_from': 'same_day_audit'}
            continue
        if url in added['results']:
            seeded[url] = added['results'][url]
            continue
        prior = sitemap_audit['results'].get(url)
        if not prior:
            continue
        days = current.get('listing_occurrences') or []
        if any(day >= as_of for day in days):
            continue
        if prior.get('status') == 'future_candidate':
            inspected = sitemap_cards['results'].get(url)
            if not inspected or inspected.get('status') != 'detail_aligned':
                continue
            prior = inspected
        elif prior.get('status') not in {
                'past_event', 'non_event', 'non_event_experience', 'ambiguous'}:
            continue
        seeded[url] = {**prior,
                       'checked_at': prior.get('checked_at') or
                                     sitemap_audit.get('created_at'),
                       'reused_from': 'same_day_audit'}
    return {**snapshot, 'results': seeded}


def inspect_item(url, entry, html, *, today, now=None):
    exclusion = (None if entry.get('identity_conflict') else
                 current_year_exclusion(entry, html, today=today))
    if exclusion:
        return {**exclusion, 'checked_at': (now or datetime.now(timezone.utc)).isoformat()}
    localized = recover_barcolana_2026_locale(url, entry, html, today=today)
    if localized:
        return {**localized, 'checked_at': (now or datetime.now(timezone.utc)).isoformat()}
    recovered = recover_current_year_detail(url, entry, html, today=today)
    if recovered:
        return {**recovered, 'checked_at': (now or datetime.now(timezone.utc)).isoformat()}
    for recover in (recover_discrete_edition, recover_month_range_exhibition):
        recovered = recover(url, entry, html, today=today)
        if recovered:
            return {**recovered,
                    'checked_at': (now or datetime.now(timezone.utc)).isoformat()}
    end_only = recover_end_only_exhibition(url, entry, html, today=today)
    if end_only:
        return {**end_only, 'checked_at': (now or datetime.now(timezone.utc)).isoformat()}
    detail = classify_detail(url, html, today=today)
    if entry.get('identity_conflict'):
        result = {'status': 'review_required', 'reason': 'conflicting_calendar_titles'}
    elif entry['kind'] == 'calendar':
        if detail['status'] == 'past_event':
            if any(day >= today.isoformat() for day in
                   entry['candidate']['listing_occurrences']):
                result = {'status': 'review_required',
                          'reason': 'future_badge_on_past_detail'}
            else:
                result = {'status': 'past_event', 'reason': detail['reason']}
        else:
            result = inspect_candidate(entry['candidate'], html, today=today)
            if result.get('status') == 'review_required':
                correction = _recheck_stale_calendar_badges(
                    entry['candidate'], html, today=today)
                if correction:
                    result = correction
    elif detail['status'] == 'future_candidate':
        candidate = {'source': 'TurismoFVG', 'url': url,
                     'title': detail['title'], 'event_city': detail['event_city'],
                     'listing_occurrences': [], 'discovery_kind': 'sitemap_detail'}
        result = inspect_candidate(candidate, html, today=today)
    else:
        result = {'status': detail['status'], 'reason': detail.get('reason')}
    if result.get('status') in {'ambiguous', 'review_required'}:
        if entry['kind'] == 'calendar':
            recovered = recover_calendar_anchored_weekends(
                url, entry, html, today=today)
            if recovered:
                result = recovered
            else:
                claim = _same_edition_exhibition_claim(html, today=today)
                if claim:
                    result = {**result, 'duplicate_claim': claim}
        else:
            archived = recover_prior_edition_in_description(
                entry, html, today=today)
            if archived:
                result = archived
    # The labelled date in this source's event detail is the event period.
    # Prose may describe a subset of performances and is not an exhaustive
    # replacement for that field. inspect_candidate has already checked the
    # detail identity and that calendar badges fit the labelled date bounds.
    return {**result, 'checked_at': (now or datetime.now(timezone.utc)).isoformat()}


def _official_host(value):
    host = urlsplit(value or '').hostname or ''
    return host.removeprefix('www.')


def _same_edition_exhibition_claim(html, *, today):
    metadata = engine.extract_turismofvg_detail_metadata(html)
    row = plain(metadata.get('date_full'))
    if not re.fullmatch(
            rf'anno {today.year} - celebrazioni 50esimo del terremoto', row):
        return None
    title_match = re.search(r'<h1\b[^>]*>(.*?)</h1>', html, re.I | re.S)
    title = engine.clean_event_text(title_match[1]) if title_match else ''
    city = metadata.get('event_city') or ''
    body = plain(' '.join(str(metadata.get(key) or '') for key in
                          ('description', 'venue', 'address')))
    official_host = _official_host(metadata.get('official_site'))
    if (not title or not city or not official_host
            or not all(token in body for token in
                       ('percorso interno', 'percorso esterno',
                        'municipale', 'vie del paese'))):
        return None
    return {'title': engine.normalize_for_search(title),
            'city': engine.normalize_for_search(city),
            'year': today.year, 'official_host': official_host,
            'sections': 'internal_and_external_municipal_exhibition'}


def reconcile_same_edition_duplicates(snapshot):
    """Suppress only a uniquely corroborated second detail of one exhibition."""
    if set(snapshot.get('results') or {}) != set(snapshot.get('entries') or {}):
        return snapshot
    results = dict(snapshot['results'])
    for url, prior in results.items():
        if prior.get('status') == 'duplicate_detail':
            results[url] = {key: value for key, value in prior.items()
                            if key not in {'duplicate_of', 'duplicate_evidence'}}
            results[url].update(status='review_required', reason='duplicate_unverified')
    for url, result in list(results.items()):
        claim = result.get('duplicate_claim')
        if result.get('status') != 'review_required' or not claim:
            continue
        matches = []
        for other_url, other in results.items():
            event = other.get('event') or {}
            if (other_url == url or other.get('status') != 'detail_aligned'
                    or event.get('schedule_kind') != 'month_range'
                    or 'mostre' not in plain(event.get('provider_categories'))
                    or engine.normalize_for_search(event.get('title')) != claim['title']
                    or engine.normalize_for_search(event.get('event_city')) != claim['city']
                    or _official_host(event.get('official_site'))
                    != claim['official_host']
                    or not str(event.get('start_date') or '').startswith(
                        str(claim['year']))):
                continue
            body = plain(' '.join(str(event.get(key) or '') for key in
                                  ('description_excerpt', 'venue', 'address')))
            if all(token in body for token in
                   ('sezione interna', 'sezione esterna',
                    'palazzo municipale', 'vie del paese')):
                matches.append(other_url)
        if len(matches) == 1:
            results[url] = {**result, 'status': 'duplicate_detail',
                            'reason': 'same_edition_same_exhibition_sections',
                            'duplicate_of': matches[0],
                            'duplicate_evidence': claim['sections']}
    return {**snapshot, 'results': results}


def _recheck_stale_calendar_badges(candidate, html, *, today):
    """A superseded past badge cannot veto a fully dated, verified period."""
    badges = candidate.get('listing_occurrences') or []
    metadata = engine.extract_turismofvg_detail_metadata(html)
    row = metadata.get('date_full') or ''
    start, end = engine.parse_event_date_range(row)
    if (not start or not end or start.year != today.year
            or end.year != today.year or end < today
            or not re.fullmatch(
                rf'(?:(?:{WEEKDAY}) )?\d{{1,2}} (?:{MONTH}) 20\d{{2}} - '
                rf'(?:(?:{WEEKDAY}) )?\d{{1,2}} (?:{MONTH}) 20\d{{2}}',
                plain(row))
            or not badges or not any(day >= today.isoformat() for day in badges)
            or not any(day < start.isoformat() for day in badges)
            or any(day >= today.isoformat() and
                   not start.isoformat() <= day <= end.isoformat()
                   for day in badges)
            or any(day > end.isoformat() for day in badges)
            or any(day < start.isoformat() and day >= today.isoformat()
                   for day in badges)):
        return None
    retained = [day for day in badges if start.isoformat() <= day <= end.isoformat()]
    if not any(day >= today.isoformat() for day in retained):
        return None
    result = inspect_candidate({**candidate, 'listing_occurrences': retained},
                               html, today=today)
    if result.get('status') != 'detail_aligned':
        return None
    return {**result, 'reason': 'superseded_past_calendar_badge',
            'ignored_listing_occurrences': sorted(set(badges) - set(retained))}


def inspect_batch(snapshot, *, batch_size=24, max_workers=3,
                  fetch_html=fetch_detail, now=None):
    if (snapshot.get('schema') != SCHEMA or not 1 <= batch_size <= 256
            or not 1 <= max_workers <= 16):
        raise ValueError('invalid TurismoFVG year-control batch')
    entries = snapshot['entries']
    results = dict(snapshot.get('results') or {})
    attempts = dict(snapshot.get('attempts') or {})
    if set(results) - set(entries) or set(attempts) - set(entries):
        raise ValueError('year-control progress outside inventory')
    today = date.fromisoformat(snapshot['as_of_date'])
    now = now or datetime.now(timezone.utc)
    todo = sorted((url for url in entries if url not in results
                   and attempts.get(url, {}).get('count', 0) < 3),
                  key=lambda url: (attempts.get(url, {}).get('count', 0),
                                   entries[url]['kind'] != 'calendar', url))[:batch_size]
    for url in todo:
        if not engine.is_trusted_turismofvg_event_url(url):
            try:
                detail = classify_detail(url, '', today=today)
                results[url] = {'status': detail['status'],
                                'reason': detail.get('reason'),
                                'checked_at': now.isoformat()}
            except Exception as exc:
                attempts[url] = {'count': attempts.get(url, {}).get('count', 0) + 1,
                                 'last_error_type': type(exc).__name__}
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(fetch_html, url): url for url in todo
                   if engine.is_trusted_turismofvg_event_url(url)}
        for future in as_completed(futures):
            url = futures[future]
            try:
                results[url] = inspect_item(url, entries[url], future.result(),
                                            today=today, now=now)
                attempts.pop(url, None)
            except requests.HTTPError as exc:
                response = exc.response
                if response is not None and response.status_code in {404, 410}:
                    results[url] = {'status': 'review_required'
                                    if entries[url]['kind'] in {'calendar', 'prior_detail'}
                                    else 'non_event',
                                    'reason': f'listed_detail_http_{response.status_code}'
                                    if entries[url]['kind'] in {'calendar', 'prior_detail'}
                                    else f'detail_http_{response.status_code}',
                                    'checked_at': now.isoformat()}
                    attempts.pop(url, None)
                else:
                    attempts[url] = {'count': attempts.get(url, {}).get('count', 0) + 1,
                                     'last_error_type': type(exc).__name__}
            except Exception as exc:
                attempts[url] = {'count': attempts.get(url, {}).get('count', 0) + 1,
                                 'last_error_type': type(exc).__name__}
    return {**snapshot, 'results': results, 'attempts': attempts}


def summary(snapshot):
    entries, results = snapshot['entries'], snapshot['results']
    counts = {status: sum(item.get('status') == status for item in results.values())
              for status in ('detail_aligned', 'past_event', 'non_event',
                             'non_event_experience', 'excluded_current_year',
                             'ambiguous', 'review_required', 'duplicate_detail')}
    return {'as_of_date': snapshot['as_of_date'],
            'declared_results': snapshot['declared_results'],
            'calendar_pages': snapshot['calendar_pages'],
            'calendar_urls': snapshot['calendar_urls'],
            'sitemap_urls': snapshot['sitemap_urls'],
            'calendar_only_urls': sum(item['kind'] == 'calendar'
                                      and not item['in_sitemap']
                                      for item in entries.values()),
            'inventory_urls': len(entries), 'inspected': len(results),
            'pending': len(entries) - len(results), 'attempts': len(snapshot['attempts']),
            'removed_urls': len(snapshot['removed_urls']),
            'replaced_urls': len(snapshot.get('replaced_urls') or {}),
            'removed_future_urls': len(snapshot.get('removed_future_urls') or []),
            'historical_lookup_failures': len(snapshot.get('historical_lookup_failures') or {}),
            'source_complete': (snapshot.get('inspection_version') == INSPECTION_VERSION
                                and len(results) == len(entries)
                                and not snapshot['attempts']
                                and not snapshot.get('removed_future_urls')
                                and all(item.get('detail_description_sha256')
                                        for item in results.values()
                                        if item.get('reason') ==
                                        'exact_historical_calendar_card')
                                and not any(item.get('status') in
                                            {'ambiguous', 'review_required'}
                                            for item in results.values())),
            **counts}


def finish_snapshot(snapshot, *, batch_size=48, fetch_html=fetch_detail,
                    checkpoint=None):
    """Inspect every detail, checkpointing progress and stopping after retries.

    This reads only the event detail HTML. An unresolved detail keeps the
    source incomplete; a failed request is retried at most three times.
    """
    if snapshot.get('inspection_version') != INSPECTION_VERSION:
        raise ValueError('stale TurismoFVG detail recognizer; collect a new index')
    while True:
        pending = [url for url in snapshot['entries']
                   if url not in snapshot['results']
                   and snapshot['attempts'].get(url, {}).get('count', 0) < 3]
        if not pending:
            return reconcile_same_edition_duplicates(snapshot)
        updated = inspect_batch(snapshot, batch_size=batch_size,
                                fetch_html=fetch_html)
        if (updated['results'] == snapshot['results']
                and updated['attempts'] == snapshot['attempts']):
            raise RuntimeError('TurismoFVG detail inspection made no progress')
        snapshot = updated
        if checkpoint:
            checkpoint(snapshot)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--snapshot', required=True, type=Path)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--collect', action='store_true')
    group.add_argument('--batch', type=int)
    group.add_argument('--finish', action='store_true')
    group.add_argument('--run', action='store_true')
    parser.add_argument('--previous', type=Path)
    parser.add_argument('--batch-size', type=int, default=48)
    args = parser.parse_args()
    if args.previous and not (args.collect or args.run or args.finish):
        parser.error('--previous applies only to --collect, --run or --finish')
    if not 1 <= args.batch_size <= 256:
        parser.error('--batch-size must be between 1 and 256')
    prior = None
    if args.collect or args.run:
        today = datetime.now(ZoneInfo('Europe/Rome')).date()
        previous = None
        if args.previous:
            with args.previous.open(encoding='utf-8') as stream:
                previous = json.load(stream)
        calendar = fetch_year(date(today.year, 1, 1), date(today.year, 12, 31),
                              max_workers=4)
        sitemap = discover_detail_urls()
        snapshot = create_snapshot(calendar, sitemap, today=today,
                                   previous=previous)
    else:
        with args.snapshot.open(encoding='utf-8') as stream:
            snapshot = json.load(stream)
        if args.finish and args.previous:
            with args.previous.open(encoding='utf-8') as stream:
                prior = json.load(stream)
        if args.finish and snapshot.get('as_of_date') != datetime.now(
                ZoneInfo('Europe/Rome')).date().isoformat():
            raise ValueError('cannot finish a stale TurismoFVG annual control')
        if args.batch is not None:
            snapshot = inspect_batch(snapshot, batch_size=args.batch)
    write_snapshot(args.snapshot, snapshot)
    if args.finish or args.run:
        def checkpoint(current):
            write_snapshot(args.snapshot, current)
            print(json.dumps(summary(current), ensure_ascii=False), flush=True)
        snapshot = finish_snapshot(snapshot, batch_size=args.batch_size,
                                   checkpoint=checkpoint)
        snapshot = resolve_historical_years(snapshot)
        if prior or (args.run and previous):
            snapshot = reconcile_removed_future(snapshot, prior or previous)
        write_snapshot(args.snapshot, snapshot)
    print(json.dumps(summary(snapshot), ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
