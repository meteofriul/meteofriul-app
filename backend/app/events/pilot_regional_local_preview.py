"""Serve a dated TurismoFVG audit to the browser pilot on loopback only.

This is a local review surface, not a catalog publisher. Preparation can
reinspect saved official detail HTML without changing the source snapshot.
"""
import argparse
import json
import math
from datetime import date, datetime, timedelta
from hashlib import sha256
from pathlib import Path
from urllib.parse import parse_qs
from wsgiref.simple_server import make_server
from zoneinfo import ZoneInfo

from . import engine
from .pilot_catalog import coordinate
from .pilot_regional_display_audit import create_year_display_audit, summary
from .pilot_regional_historical import recheck_historical_result
from .pilot_regional_location import resolve_turismofvg_municipality
from .pilot_regional_sitemap_audit import write_snapshot
from .pilot_regional_year_control import (INSPECTION_VERSION, inspect_item,
                                          reconcile_same_edition_duplicates)
from .pilot_source_policy import validate_candidate


def prepare_display(control, *, today, manifest=None, html_dir=None):
    """Recheck supplied local evidence, then project only aligned details."""
    if control.get('as_of_date') != today.isoformat():
        raise ValueError('TurismoFVG control is not from today')
    revised = {**control, 'results': dict(control['results'])}
    rechecked = []
    if manifest:
        if html_dir is None:
            raise ValueError('detail HTML directory required')
        root = Path(html_dir).resolve()
        seen = set()
        for item in manifest:
            url, filename = item['url'], item['file']
            if (url in seen or url not in control['entries']
                    or not engine.is_trusted_turismofvg_event_url(url)
                    or Path(filename).name != filename or not filename.endswith('.html')):
                raise ValueError('invalid local detail manifest')
            seen.add(url)
            html = (root / filename).read_text(encoding='utf-8')
            inspected = inspect_item(url, control['entries'][url], html,
                                     today=today)
            prior = control['results'].get(url) or {}
            if (inspected.get('status') == 'ambiguous'
                    and recheck_historical_result(control['entries'][url],
                                                  html, prior, today=today)):
                inspected = prior
            revised['results'][url] = inspected
            rechecked.append(url)
    revised = reconcile_same_edition_duplicates(revised)
    audit = create_year_display_audit(revised, today=today)
    urls = [card['url'] for card in audit['cards']]
    if (len(urls) != len(set(urls))
            or any(validate_candidate(card, today=today) for card in audit['cards'])):
        raise ValueError('TurismoFVG preview contains invalid cards')
    return {**audit, 'local_preview_only': True,
            'source_control_inspection_version': control.get('inspection_version'),
            'local_recheck_inspection_version': INSPECTION_VERSION,
            'rechecked_detail_urls': rechecked}


def _distance_km(lat, lon, other_lat, other_lon):
    dlat = math.radians(other_lat - lat)
    dlon = math.radians(other_lon - lon)
    half = (math.sin(dlat / 2) ** 2
            + math.cos(math.radians(lat)) * math.cos(math.radians(other_lat))
            * math.sin(dlon / 2) ** 2)
    return 6371 * 2 * math.asin(math.sqrt(min(1, max(0, half))))


def nearby_events(display, *, lat, lon, radius, today):
    """One card per official detail, ordered by its next relevant date."""
    selected = []
    for card in display['cards']:
        try:
            if card.get('schedule_kind') != 'end_only':
                date.fromisoformat(card['start_date'])
            end = date.fromisoformat(card['end_date'])
            sort_day = date.fromisoformat(card['sort_date'])
        except (KeyError, TypeError, ValueError):
            continue
        if end < today or sort_day < today:
            continue
        places = card.get('listed_municipalities') or []
        if places:
            points = [(coordinate(place.get('lat'), 90),
                       coordinate(place.get('lon'), 180)) for place in places]
        else:
            points = [(coordinate(card.get('lat'), 90),
                       coordinate(card.get('lon'), 180))]
        distances = [_distance_km(lat, lon, a, b) for a, b in points
                     if a is not None and b is not None]
        if not distances or min(distances) > radius:
            continue
        days = card.get('verified_programme_occurrences') or []
        event = {**card,
                 **({'occurrences': days} if days else {}),
                 'distance_km': round(min(distances), 1),
                 'distance_is_approximate': card.get('location_confidence')
                    not in {'exact', 'venue'},
                 'source_status': 'verified_subset',
                 'preview_outside_window': sort_day > today + timedelta(days=15)}
        selected.append(event)
    selected.sort(key=lambda item: (
        item['sort_date'], engine.normalize_for_search(item.get('title')),
        item['url']))
    return selected


def create_application(display, *, today, snapshot, clock=None):
    if (display.get('as_of_date') != today.isoformat()
            or display.get('local_preview_only') is not True
            or not isinstance(display.get('cards'), list)):
        raise ValueError('stale or invalid TurismoFVG local preview')

    clock = clock or (lambda: datetime.now(ZoneInfo('Europe/Rome')).date())

    def application(environ, start_response):
        headers = [('Content-Type', 'application/json; charset=utf-8'),
                   ('Cache-Control', 'no-store')]
        status = '200 OK'
        path = environ.get('PATH_INFO')
        if clock() != today:
            status, payload = '503 Service Unavailable', {'error': 'stale_preview'}
        elif environ.get('REQUEST_METHOD') != 'GET':
            status, payload = '405 Method Not Allowed', {'error': 'read_only'}
        elif path == '/health':
            payload = {'service': 'turismofvg-local-preview',
                       'as_of_date': display['as_of_date'],
                       'cards': len(display['cards'])}
        elif path == '/api/local/events':
            try:
                args = parse_qs(environ.get('QUERY_STRING', ''))
                radius = int(args.get('radius', ['20'])[0])
                limit = int(args.get('limit', ['100'])[0])
                offset = int(args.get('offset', ['0'])[0])
                if (radius not in range(5, 51, 5) or not 1 <= limit <= 500
                        or not 0 <= offset <= 10000):
                    raise ValueError('invalid pagination or radius')
                lat = coordinate(args.get('lat', [None])[0], 90)
                lon = coordinate(args.get('lon', [None])[0], 180)
                if lat is None or lon is None:
                    town = resolve_turismofvg_municipality(
                        args.get('city', [''])[0])
                    if town is None:
                        raise ValueError('unknown municipality')
                    lat, lon = town.latitude, town.longitude
            except (ValueError, TypeError, IndexError):
                status, payload = '400 Bad Request', {'error': 'invalid_query'}
            else:
                if args.get('snapshot', [snapshot])[0] != snapshot:
                    status, payload = '409 Conflict', {'error': 'catalog_changed'}
                else:
                    events = nearby_events(display, lat=lat, lon=lon,
                                           radius=radius, today=today)
                    payload = {'events': events[offset:offset + limit],
                               'total': len(events),
                               'next_offset': (offset + limit
                                               if offset + limit < len(events)
                                               else None),
                               'snapshot': snapshot,
                               'status': 'ready',
                               'source_status': {'TurismoFVG': 'verified_subset'},
                               'coverage': {'as_of_date': display['as_of_date'],
                                            'cards': len(display['cards']),
                                            'quarantined': len(display.get('quarantined') or []),
                                            'source_complete': display.get('source_complete')}}
        else:
            status, payload = '404 Not Found', {'error': 'not_found'}
        data = json.dumps(payload, ensure_ascii=False, allow_nan=False).encode('utf-8')
        start_response(status, headers + [('Content-Length', str(len(data)))])
        return [data]

    return application


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--prepare', action='store_true')
    mode.add_argument('--serve', action='store_true')
    parser.add_argument('--control', type=Path)
    parser.add_argument('--manifest', type=Path)
    parser.add_argument('--html-dir', type=Path)
    parser.add_argument('--display', required=True, type=Path)
    parser.add_argument('--port', type=int, default=8767)
    args = parser.parse_args()
    today = datetime.now(ZoneInfo('Europe/Rome')).date()
    if args.prepare:
        if not args.control:
            parser.error('--control required for preparation')
        with args.control.open(encoding='utf-8') as stream:
            control = json.load(stream)
        manifest = None
        if args.manifest:
            with args.manifest.open(encoding='utf-8') as stream:
                manifest = json.load(stream)
        display = prepare_display(control, today=today,
                                  manifest=manifest, html_dir=args.html_dir)
        write_snapshot(args.display, display)
        print(json.dumps(summary(display), ensure_ascii=False, indent=2))
    else:
        if not 1024 <= args.port <= 65535:
            parser.error('invalid port')
        data = args.display.read_bytes()
        display = json.loads(data)
        app = create_application(display, today=today,
                                 snapshot=sha256(data).hexdigest()[:20])
        with make_server('127.0.0.1', args.port, app) as server:
            print(f'TurismoFVG local preview on 127.0.0.1:{args.port}', flush=True)
            server.serve_forever()


if __name__ == '__main__':
    main()
