"""Pilot-only catalog primitives. No scraping or writes during consultation."""
from copy import deepcopy
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo
import math
import os
import re
from .pilot_regional_checkpoint import encode_control

PILOT_PROJECT = os.environ.get("EVENTS_CLOUD_PROJECT", "meteofriul-pilot-20260906")
RADII = tuple(range(5, 51, 5))


def failure_diagnostics(result, collected_at):
    reviews = list(result.get('review_required') or [])
    pending = list(result.get('detail_candidates') or [])
    return {
        'last_attempted_at': collected_at,
        'last_attempt_error_type': result.get('error_type') or result.get('reason') or 'source_error',
        'last_attempt_exception_type': result.get('exception_type'),
        'last_attempt_error_detail': result.get('error_detail'),
        'last_attempt_verification': deepcopy(result.get('verification', {})),
        'last_attempt_review_count': len(reviews),
        'last_attempt_pending_count': len(pending),
        'last_attempt_issues': [
            {'url': item.get('url'), 'reason': item.get('review_reason') or item.get('reason'),
             'reasons': item.get('reasons')}
            for item in reviews + pending if isinstance(item, dict)
        ],
    }


def merge_collection(project, previous, results, collected_at):
    """Only successful source batches replace earlier data, including valid empty batches."""
    if project != PILOT_PROJECT:
        raise ValueError("isolated pilot project required")
    timestamp = datetime.fromisoformat(collected_at.replace("Z", "+00:00"))
    if timestamp.tzinfo is None:
        raise ValueError("timezone required")
    sources = deepcopy((previous or {}).get("sources", {}))
    for name, result in results.items():
        checkpoint = (encode_control(result['year_control'])
                      if name == 'TurismoFVG' and isinstance(result.get('year_control'), dict)
                      else None)
        publishable = (result.get("status") == "ok" or
                       name == 'Paesi in Festa' and result.get("status") == "partial")
        if publishable and isinstance(result.get("events"), list):
            sources[name] = {"events": deepcopy(result["events"]), "updated_at": collected_at,
                             "status": ("partial" if result.get("status") == "partial" else "fresh"),
                             "review_required": deepcopy(result.get("review_required", [])),
                             "coverage": result.get("coverage", "source-adapter"),
                             "detail_cache": deepcopy(result.get("detail_cache", {})),
                             "detail_urls_checked": result.get("detail_urls_checked", 0)}
            sources[name]['publication_gate'] = deepcopy(result.get('publication_gate', {}))
            sources[name]['rejected_dates'] = result.get('rejected_dates', 0)
            sources[name]['detail_candidates'] = deepcopy(result.get('detail_candidates', []))
            sources[name]['verification'] = deepcopy(result.get('verification', {}))
            if checkpoint:
                sources[name]['control_checkpoint'] = checkpoint
        elif name in sources:
            # A failed rolling run must not replace the verified evidence used
            # to carry active, formerly listed pages into the next window.
            keep_verified_window_checkpoint = (
                name == 'TurismoFVG'
                and (result.get('verification') or {}).get('collection_mode')
                    == 'verified-rolling-45-day-window'
                and sources[name].get('control_checkpoint') is not None)
            sources[name]["status"] = "stale"
            sources[name].update(failure_diagnostics(result, collected_at))
            if isinstance(result.get('detail_cache'), dict):
                sources[name].setdefault('detail_cache', {}).update(deepcopy(result['detail_cache']))
            if checkpoint and not keep_verified_window_checkpoint:
                sources[name]['control_checkpoint'] = checkpoint
        else:
            sources[name] = {"events": [], "updated_at": None, "status": "unavailable",
                             **failure_diagnostics(result, collected_at),
                             'detail_cache': deepcopy(result.get('detail_cache', {}))}
            if checkpoint:
                sources[name]['control_checkpoint'] = checkpoint
    return {"schema": "pilot-events-v1", "sources": sources, "attempted_at": collected_at}


def coordinate(value, bound):
    if value is None or isinstance(value, bool) or value == "":
        return None
    try:
        number = float(value)
    except (ValueError, TypeError):
        return None
    return number if math.isfinite(number) and abs(number) <= bound else None


def project_named_sagra(event):
    """Use the named event type after merging duplicate source categories."""
    if not re.match(r'^\s*(?:\d{1,3}\s*[^\d\s]?\s+)?sagra\b',
                    str(event.get('title') or ''), re.IGNORECASE):
        return event
    return {**event, 'category': 'sagra', 'category_label': 'Sagra / festa locale'}


def query_catalog(catalog, lat, lon, radius=20, *, now=None):
    """Distances are straight-line; unknown positions never qualify as nearby."""
    lat, lon = coordinate(lat, 90), coordinate(lon, 180)
    if lat is None or lon is None or isinstance(radius, bool) or radius not in RADII:
        raise ValueError("invalid location or radius")
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError("timezone required")
    today = now.astimezone(ZoneInfo("Europe/Rome")).date()
    selected, unknown = [], 0
    seen = set()
    for source_name, batch in catalog.get("sources", {}).items():
        if batch.get('status') != 'fresh' and not (
                source_name == 'Paesi in Festa' and batch.get('status') == 'partial'):
            # Failed batches retain their last verified snapshot for diagnosis
            # and a later source-only retry, but none of those events are live.
            continue
        try:
            if not isinstance(batch.get("updated_at"), str):
                continue
            updated = datetime.fromisoformat(batch["updated_at"].replace("Z", "+00:00"))
            age = (now - updated).total_seconds()
            if not 0 <= age <= 48 * 3600:
                continue
        except (ValueError, TypeError, KeyError):
            continue
        for event in batch.get("events", []):
            try:
                start = date.fromisoformat(event["start_date"])
                end = date.fromisoformat(event.get("end_date") or event["start_date"])
                if end < start or end < today:
                    continue
                occurrences = event.get("occurrences") or []
                if occurrences and not any(date.fromisoformat(d) >= today for d in occurrences):
                    continue
            except (ValueError, TypeError, KeyError):
                continue
            a, b = coordinate(event.get("lat"), 90), coordinate(event.get("lon"), 180)
            multi_place = (a is None and b is None
                           and event.get('location_confidence') == 'multiple_municipalities')
            if multi_place:
                places = event.get('listed_municipalities') or []
                points = [(coordinate(place.get('lat'), 90), coordinate(place.get('lon'), 180))
                          for place in places if isinstance(place, dict) and place.get('name')]
                if len(points) != len(places) or len(points) < 2:
                    unknown += 1
                    continue
            else:
                points = [(a, b)]
            if any(x is None or y is None for x, y in points):
                unknown += 1
                continue
            distances = []
            for x, y in points:
                dlat, dlon = math.radians(x-lat), math.radians(y-lon)
                h = math.sin(dlat/2)**2 + math.cos(math.radians(lat))*math.cos(math.radians(x))*math.sin(dlon/2)**2
                distances.append(6371 * 2 * math.asin(math.sqrt(min(1, max(0, h)))))
            distance = min(distances)
            if distance <= radius:
                identity = (event.get("source"), event.get("url") or event.get("title"), start, end,
                            event.get("time"), event.get("place"), event.get("event_city"),
                            event.get("venue"), event.get("address"), event.get("title"),
                            event.get("end_time"), tuple(sorted(event.get("occurrences") or [])))
                if identity in seen:
                    continue
                seen.add(identity)
                if source_name == 'Barcolana':
                    from .pilot_barcolana import current_card
                    event = current_card(event, today)
                selected.append({**event,
                                 **({'nearest_listed_municipality_distance_km': round(distance, 1)}
                                    if multi_place else {'distance_km': round(distance, 1)}),
                                 "distance_is_approximate": event.get("location_confidence") not in {"venue", "exact"},
                                 "source_status": batch["status"],
                                 "source_updated_at": batch["updated_at"]})
    from .pilot_dedupe import deduplicate
    selected = [project_named_sagra(event) for event in deduplicate(selected)]
    from .pilot_programmes import project_programme_editions
    selected = project_programme_editions(selected, today=today)
    selected.sort(key=lambda event: event.get(
        "distance_km", event.get("nearest_listed_municipality_distance_km",
                                  event.get("nearest_session_distance_km", float("inf")))))
    return {"events": selected, "radius_km": radius, "unlocated_count": unknown}
