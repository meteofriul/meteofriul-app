"""Pilot-only atomic catalog publication. No beta or weather object access."""
from datetime import datetime, timezone
import json
import os
import time
from functools import partial
from zoneinfo import ZoneInfo
from .pilot_attems_audit import collect_audit as collect_attems_audit, watch_changes as attems_watch_changes
from .pilot_girofvg_watch import collect_watch as collect_girofvg_watch
from .pilot_catalog import PILOT_PROJECT
from .pilot_collection import collect
from .pilot_regional_checkpoint import decode_control
from .pilot_regional_annual_watch import run_bounded_watch
from .pilot_sources import source_adapters

BUCKET = os.environ.get('EVENTS_DATA_BUCKET', 'meteofriul-pilot-20260906-data')
KEY = os.environ.get('EVENTS_CATALOG_KEY', 'pilot/events/v1/catalog.json')
MAX_BYTES = 8 * 1024 * 1024


def annual_watch_due(today, previous=None):
    if today.weekday() != 0:
        return False
    try:
        checked = datetime.fromisoformat(previous['checked_at'])
        checked_today = checked.astimezone(ZoneInfo('Europe/Rome')).date() == today
    except (KeyError, TypeError, ValueError):
        checked_today = False
    return not ((previous or {}).get('status') == 'checked' and checked_today)


def _save_catalog(blob, generation, catalog):
    data = json.dumps(catalog, ensure_ascii=False, allow_nan=False).encode('utf-8')
    if len(data) > MAX_BYTES:
        raise ValueError('catalog too large')
    # Compare-and-swap prevents an overlapping job from overwriting a newer run.
    blob.upload_from_string(data, content_type='application/json',
                            if_generation_match=generation, timeout=30)


def publish(client, *, project, adapters=None, retry_failed=False):
    started = time.monotonic()
    if project != PILOT_PROJECT or client.project != PILOT_PROJECT:
        raise ValueError('isolated events project required')
    if adapters is not None and retry_failed:
        raise ValueError('explicit adapters cannot be combined with failed-source retry')
    blob = client.bucket(BUCKET).blob(KEY)
    from google.api_core.exceptions import NotFound
    try:
        blob.reload(timeout=20)
        generation = int(blob.generation)
        if blob.size > MAX_BYTES:
            raise ValueError('catalog too large')
        previous = json.loads(blob.download_as_bytes(if_generation_match=generation, timeout=20))
        if previous.get('schema') != 'pilot-events-v1':
            raise ValueError('unexpected catalog schema')
    except NotFound:
        previous, generation = None, 0
    registered_adapters = source_adapters(project) if adapters is None else None
    if retry_failed:
        failed = {name for name, batch in (previous or {}).get('sources', {}).items()
                  if isinstance(batch, dict) and batch.get('status') != 'fresh'}
        selected_adapters = {name: adapter for name, adapter in registered_adapters.items()
                             if name in failed}
        if not selected_adapters:
            raise ValueError('no failed registered source to retry')
    else:
        selected_adapters = adapters if adapters is not None else registered_adapters
    if adapters is None:
        from .pilot_regional_verified import collect_regional_window_verified
        checkpoint = ((previous or {}).get('sources', {}).get('TurismoFVG', {})
                      .get('control_checkpoint'))
        try:
            previous_control = decode_control(checkpoint) if checkpoint else None
        except (TypeError, ValueError):
            previous_control = None
        if 'TurismoFVG' in selected_adapters:
            selected_adapters['TurismoFVG'] = partial(
                collect_regional_window_verified, previous_control,
                previous_batch=(previous or {}).get('sources', {}).get('TurismoFVG'))
    source_timeouts = {name: budget for name, budget in
                       (("TurismoFVG", 360), ("Paesi in Festa", 90),
                        ("SagreFVG", 60), ("Pordenonelegge", 20),
                        ("Pordenone Pensa", 25),
                        ("Le Giornate del Cinema Muto", 30),
                        ("Azalea", 20), ("CSS Udine", 20),
                        ("Teatro Verdi Pordenone", 50),
                        ("Teatro Verdi Trieste", 25),
                        ("Villa Manin", 65),
                        ("Magazzino delle Idee", 30),
                        ("MESS", 10),
                        ("Galleria Spazzapan", 10),
                        ("Barcolana", 35))
                       if name in selected_adapters}
    # Fifteen bounded sources leave room for read-only inventory watches.
    catalog = collect(project, selected_adapters, previous,
                      datetime.now(timezone.utc).isoformat(), timeout=55,
                      source_timeouts=source_timeouts)
    # A source-only retry does not claim to have rerun the inventory monitors.
    catalog['monitors'] = dict((previous or {}).get('monitors') or {})
    # Retire old diagnostic entries even when this run only retries sources.
    catalog['monitors'].pop('Anteprima Sagre', None)
    catalog['monitors'].pop('Pro Loco FVG', None)
    report = {name: {'status': batch['status'], 'count': len(batch['events']),
                     'published_count': (len(batch['events']) if batch['status'] in {'fresh', 'partial'} else 0),
                     'failure_tag': ('quarantined_cards' if batch['status'] == 'partial' else
                                     (batch.get('last_attempt_error_type') or 'source_error')
                                     if batch['status'] != 'fresh' else None),
                     'review_count': len(batch.get('review_required', [])),
                     'verification': (batch.get('verification') if batch['status'] in {'fresh', 'partial'}
                                      else batch.get('last_attempt_verification')) or {}}
              for name, batch in catalog['sources'].items()}
    incomplete = [name for name in selected_adapters
                  if name in {'TurismoFVG', 'Azalea', 'CSS Udine', 'Pordenone Pensa',
                              'Teatro Verdi Pordenone', 'Teatro Verdi Trieste',
                              'Paesi in Festa', 'SagreFVG', 'Villa Manin',
                              'Magazzino delle Idee', 'MESS',
                              'Galleria Spazzapan',
                              'Pordenonelegge', 'Le Giornate del Cinema Muto',
                              'Barcolana'}
                  and catalog['sources'].get(name, {}).get('status') != 'fresh'
                  and not (name == 'Paesi in Festa' and
                           catalog['sources'].get(name, {}).get('status') == 'partial')]
    if incomplete:
        # The catalog retains the last verified source data and detail progress,
        # but the scheduled job must not appear successful after a partial run.
        _save_catalog(blob, generation, catalog)
        print(json.dumps({'event_source_verification': report}, ensure_ascii=False), flush=True)
        raise RuntimeError('event source verification failed: ' + ', '.join(sorted(incomplete)))
    watch_failures = []
    if adapters is None and not retry_failed:
        monitored_at = catalog.get('attempted_at') or datetime.now(timezone.utc).isoformat()
        monitor_status = {}
        try:
            attems = collect_attems_audit(datetime.now(ZoneInfo('Europe/Rome')).date())
            changes = attems_watch_changes(attems)
        except Exception as exc:
            monitor_status['Palazzo Attems'] = {
                'status': 'unverified', 'tag': 'upstream_unavailable',
                'checked_at': monitored_at}
            watch_failures.append('Palazzo Attems inventory watch unavailable: '
                                  + type(exc).__name__ + ': ' + str(exc))
        else:
            monitor_status['Palazzo Attems'] = {
                'status': 'review_required' if changes else 'checked',
                'source_complete': attems['source_complete'],
                'checked_at': monitored_at}
            print(json.dumps({'palazzo_attems_watch': {
                'source_complete': attems['source_complete'],
                'event_api_count': attems['event_api_count'],
                'current_exhibition_count': attems['current_exhibition_count'],
                'known_blockers': len(attems['blockers']),
                'changes': changes}}, ensure_ascii=False), flush=True)
            if changes:
                watch_failures.append('Palazzo Attems inventory changed: ' + ', '.join(changes))
        try:
            girofvg = collect_girofvg_watch(datetime.now(ZoneInfo('Europe/Rome')).date())
        except Exception as exc:
            monitor_status['GiroFVG'] = {
                'status': 'unverified', 'tag': 'upstream_unavailable',
                'checked_at': monitored_at}
            watch_failures.append('GiroFVG discovery watch unavailable: '
                                  + type(exc).__name__ + ': ' + str(exc))
        else:
            monitor_status['GiroFVG'] = {
                'status': 'review_required' if girofvg['changes'] else 'checked',
                'source_complete': girofvg['source_complete'],
                'checked_at': monitored_at}
            print(json.dumps({'girofvg_watch': {
                'source_complete': girofvg['source_complete'],
                'sitemap_urls': girofvg['sitemap_urls'],
                'category_pages_expected': girofvg['category_pages_expected'],
                'category_pages_read': girofvg['category_pages_read'],
                'known_page_errors': girofvg['known_page_errors'],
                'changes': girofvg['changes']}}, ensure_ascii=False), flush=True)
            if girofvg['changes']:
                watch_failures.append('GiroFVG has changed event candidates requiring review')
        annual_name = 'TurismoFVG annual inventory'
        previous_annual = ((previous or {}).get('monitors') or {}).get(annual_name)
        local_today = datetime.now(ZoneInfo('Europe/Rome')).date()
        if annual_watch_due(local_today, previous_annual):
            try:
                if time.monotonic() - started >= 600:
                    raise TimeoutError('insufficient remaining job budget')
                regional_control = decode_control(
                    catalog['sources']['TurismoFVG']['control_checkpoint'])
                window_urls = regional_control['current_year_window_urls']
                annual = run_bounded_watch(local_today, window_urls)
            except Exception as exc:
                monitor_status[annual_name] = {
                    'status': 'unverified', 'tag': 'annual_inventory_unavailable',
                    'checked_at': monitored_at,
                    'exception_type': type(exc).__name__}
                watch_failures.append('TurismoFVG annual inventory watch unavailable: '
                                      + type(exc).__name__)
            else:
                monitor_status[annual_name] = {
                    'status': 'checked' if annual['source_complete']
                              else 'review_required',
                    'source_complete': annual['source_complete'],
                    'checked_at': monitored_at,
                    'calendar_cards': annual['calendar_cards'],
                    'calendar_pages': annual['calendar_pages'],
                    'missing_window_count': annual['missing_window_count']}
                print(json.dumps({'turismofvg_annual_inventory_watch': annual},
                                 ensure_ascii=False), flush=True)
                if not annual['source_complete']:
                    watch_failures.append('TurismoFVG annual inventory mismatch')
        elif previous_annual:
            monitor_status[annual_name] = previous_annual
        catalog['monitors'] = monitor_status
    _save_catalog(blob, generation, catalog)
    if watch_failures:
        raise RuntimeError(' | '.join(watch_failures))
    return report


if __name__ == '__main__':
    import argparse
    from google.cloud import storage
    parser = argparse.ArgumentParser(description='Refresh the verified Events catalog')
    actions = parser.add_mutually_exclusive_group()
    actions.add_argument('--retry-failed', action='store_true',
                         help='recollect only registered sources tagged as failed')
    options = parser.parse_args()
    project = os.environ.get('GOOGLE_CLOUD_PROJECT')
    if project != PILOT_PROJECT:
        raise ValueError('isolated events project required')
    print(json.dumps(publish(storage.Client(project=project), project=project,
                             retry_failed=options.retry_failed)))
