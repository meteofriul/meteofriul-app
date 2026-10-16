"""Evidence for rolling TurismoFVG detail failures; no network or publication."""
from datetime import datetime, timezone
import re
import requests

from . import engine

SCHEMA = 'turismofvg-detail-health-v1'
TRANSIENT_HTTP = {408, 429, 500, 502, 503, 504}


def failure_attempt(previous, exc, *, phase, now):
    status = getattr(getattr(exc, 'response', None), 'status_code', None)
    reason = ('invalid_detail_url' if phase == 'inventory' else
              'parser_exception' if phase == 'parse' else
              f'http_{status}' if status is not None else
              'network_timeout' if isinstance(exc, requests.Timeout) else
              'network_connection' if isinstance(exc, requests.ConnectionError) else
              'invalid_detail_response')
    return {'count': previous.get('count', 0) + 1,
            'last_error_type': type(exc).__name__, 'http_status': status,
            'phase': phase, 'reason': reason, 'checked_at': now.isoformat(),
            'retryable': phase == 'fetch' and isinstance(exc, requests.RequestException)}


def detail_observation(html, entry, result, *, now):
    metadata = engine.extract_turismofvg_detail_metadata(html)
    title = re.search(r'<h1\b[^>]*>(.*?)</h1>', html, re.I | re.S)
    evidence = {'title': engine.clean_event_text(title[1])[:500] if title else '',
                'date_full': str(metadata.get('date_full') or '')[:2000],
                'event_city': str(metadata.get('event_city') or '')[:500]}
    # Some official editions are already recovered by a source-specific parser.
    # Preserve that stronger proof instead of requiring the old CSS date field.
    if result.get('status') == 'detail_aligned':
        event = result.get('event') or {}
        evidence = {'title': evidence['title'] or event.get('title') or '',
                    'date_full': evidence['date_full'] or event.get('start_date') or '',
                    'event_city': evidence['event_city'] or event.get('event_city') or ''}
    outcome = ('structured' if all(evidence.values()) else 'recognized_exclusion'
               if result.get('status') in {'past_event', 'non_event', 'non_event_experience',
                                          'excluded_current_year'} else 'unstructured')
    return {'outcome': outcome,
            'checked_at': now.isoformat(), 'signature': entry['signature'],
            'evidence': evidence}


def structured_reads(control):
    return sum(row.get('outcome') == 'structured' for row in
               control.get('detail_observations', {}).values())


def has_read_failures(control):
    return bool(control.get('attempts') or any(
        row.get('outcome') == 'unstructured' for row in
        control.get('detail_observations', {}).values()))


def settle_detail_failures(control, fallbacks, *, today, stop_reason):
    """Account for attempted bad pages only with a current healthy detail witness."""
    from .pilot_regional_verified import _result_within_age
    results, attempts = dict(control['results']), dict(control['attempts'])
    diagnostics = {}
    healthy = structured_reads(control) > 0
    now = datetime.now(timezone.utc)
    for url, attempt in list(attempts.items()):
        row = {'url': url, **attempt, 'disposition': 'pending'}
        prior = fallbacks.get(url)
        transient = (attempt.get('phase') == 'fetch' and (
            attempt.get('reason') in {'network_timeout', 'network_connection'}
            or attempt.get('http_status') in TRANSIENT_HTTP))
        if (healthy and prior and transient
                and _result_within_age(prior, today=today, now=now)):
            results[url] = prior
            attempts.pop(url)
            row.update(disposition='retained_valid', original_checked_at=prior['checked_at'])
        elif (healthy and attempt.get('phase') in {'fetch', 'parse'}
              and (attempt.get('count', 0) >= 3 or not attempt.get('retryable', True))):
            results[url] = {'status': 'review_required',
                            'reason': f"detail_{attempt['phase']}_failed",
                            'checked_at': attempt['checked_at']}
            attempts.pop(url)
            row['disposition'] = 'quarantined'
        diagnostics[url] = row
    for url, row in control.get('detail_observations', {}).items():
        if row['outcome'] == 'unstructured':
            diagnostics[url] = {'url': url, 'phase': 'content',
                                'reason': 'missing_structured_detail', 'http_status': 200,
                                'count': 1, 'checked_at': row['checked_at'],
                                'disposition': 'quarantined' if healthy else 'source_unverified'}
    for url in set(control['entries']) - set(results):
        if url not in diagnostics:
            diagnostics[url] = {'url': url, 'phase': 'budget',
                                'reason': 'not_attempted_budget', 'count': 0,
                                'http_status': None, 'checked_at': now.isoformat(),
                                'disposition': 'pending'}
    return {**control, 'results': results, 'attempts': attempts,
            'detail_diagnostics': diagnostics, 'detail_stop_reason': stop_reason}


def detail_health(control):
    rows = control.get('detail_diagnostics', {})
    return {'schema': SCHEMA, 'structured_reads': structured_reads(control),
            'failed_reads': sum(row.get('outcome') in {'failure', 'unstructured'}
                                for row in control.get('detail_observations', {}).values()),
            'quarantined_reads': sum(row['disposition'] == 'quarantined' for row in rows.values()),
            'retained_refreshes': sum(row['disposition'] == 'retained_valid' for row in rows.values()),
            'pending': len(set(control['entries']) - set(control['results'])),
            'stop_reason': control.get('detail_stop_reason'),
            'health_witness_required': bool(rows)}


def pending_details(control):
    return [dict(control['detail_diagnostics'][url]) for url in
            sorted(set(control['entries']) - set(control['results']))]


def detail_health_verified(control, *, previous_control=None, today, resumed_results=None):
    """Recheck failure dispositions and retained evidence in the independent gate."""
    from .pilot_regional_verified import _result_within_age
    observations = control.get('detail_observations')
    diagnostics = control.get('detail_diagnostics')
    if not isinstance(observations, dict) or not isinstance(diagnostics, dict):
        return False
    entries, results = control['entries'], control['results']
    if (set(observations) - set(entries) or set(diagnostics) - set(entries)
            or any(row.get('disposition') in {'pending', 'source_unverified'}
                   for row in diagnostics.values())):
        return False
    now = datetime.now(timezone.utc)
    for url, observation in observations.items():
        if observation.get('signature') != entries[url]['signature']:
            return False
        checked = datetime.fromisoformat(observation['checked_at'])
        if (checked.tzinfo is None or checked > now
                or checked < datetime.fromisoformat(control['created_at'])):
            return False
        outcome = observation.get('outcome')
        if outcome == 'structured' and not all(
                observation.get('evidence', {}).get(key) for key in ('title', 'date_full', 'event_city')):
            return False
        if (outcome == 'recognized_exclusion' and results.get(url, {}).get('status') not in
                {'past_event', 'non_event', 'non_event_experience', 'excluded_current_year'}):
            return False
        if outcome in {'failure', 'unstructured'} and url not in diagnostics:
            return False
        if outcome not in {'structured', 'unstructured', 'failure', 'missing', 'recognized_exclusion'}:
            return False
    if diagnostics and not structured_reads(control):
        return False
    for url, row in diagnostics.items():
        result = results.get(url) or {}
        if row.get('url') != url or url not in observations:
            return False
        observation = observations[url]
        if row['phase'] != 'content' and (
                observation.get('outcome') != 'failure'
                or {k: v for k, v in row.items() if k not in
                    {'url', 'disposition', 'original_checked_at'}} != observation.get('attempt')):
            return False
        if row.get('phase') not in {'fetch', 'parse', 'content'}:
            return False
        if row['phase'] == 'content' and (
                observation.get('outcome') != 'unstructured'
                or row.get('checked_at') != observation.get('checked_at')
                or row.get('http_status') != 200 or row.get('count') != 1
                or row.get('reason') != 'missing_structured_detail'):
            return False
        if row['disposition'] == 'retained_valid':
            prior = previous_control or {}
            entry = prior.get('entries', {}).get(url)
            old = prior.get('results', {}).get(url)
            if not entry or not old:
                witness = prior.get('known_future', {}).get(url, {})
                entry, old = witness.get('entry'), witness.get('result')
            # The caller revalidates saved partial reads against this run's
            # inventory, inspection version and expiry before supplying them.
            resumed = (resumed_results or {}).get(url)
            if resumed is not None and result == resumed:
                entry, old = entries[url], resumed
            if (not entry or result != old or entry['signature'] != entries[url]['signature']
                    or row.get('original_checked_at') != result.get('checked_at')
                    or row.get('phase') != 'fetch'
                    or not (row.get('reason') in {'network_timeout', 'network_connection'}
                            or row.get('http_status') in TRANSIENT_HTTP)
                    or not _result_within_age(result, today=today, now=now)):
                return False
        elif row['disposition'] == 'quarantined':
            if result.get('status') not in {'ambiguous', 'review_required'}:
                return False
            if row['phase'] != 'content' and (
                    result.get('reason') != f"detail_{row['phase']}_failed"
                    or result.get('checked_at') != row.get('checked_at')
                    or (row.get('count', 0) < 3 and row.get('retryable', True))):
                return False
        else:
            return False
    for url, result in results.items():
        if result.get('reason') in {'detail_fetch_failed', 'detail_parse_failed'} and url not in diagnostics:
            return False
    return True
