"""Evidence of source recovery, emitted only after catalog persistence succeeds."""
from datetime import datetime
import json
from .pilot_catalog import source_age_failure


def _timestamp(value):
    try:
        stamp = datetime.fromisoformat(value.replace('Z', '+00:00'))
        return stamp if stamp.tzinfo is not None else None
    except (AttributeError, TypeError, ValueError):
        return None


def log_source_recovery(previous, catalog, selected_sources):
    """A rolling failure counter becoming zero is never recovery evidence.

    The caller must persist the catalog first. Recovery concerns the selected
    batches only: quarantined cards and failures of other sources stay explicit.
    """
    attempted = _timestamp(catalog.get('attempted_at'))
    if attempted is None:
        return
    sources = catalog.get('sources') or {}
    previous_sources = (previous or {}).get('sources') or {}
    recovered = []
    for name in sorted(selected_sources):
        old, new = previous_sources.get(name, {}), sources.get(name, {})
        failed_at = _timestamp(old.get('last_attempted_at'))
        updated_at = _timestamp(new.get('updated_at'))
        if (old.get('status') not in {'stale', 'unavailable'}
                or new.get('status') not in {'fresh', 'partial'}
                or not isinstance(new.get('events'), list)
                or new.get('last_attempt_error_type')
                or failed_at is None or updated_at != attempted
                or attempted <= failed_at):
            continue
        recovered.append({
            'source': name, 'previous_status': old['status'], 'status': new['status'],
            'previous_failed_at': old['last_attempted_at'],
            'updated_at': new['updated_at'], 'published_count': len(new['events']),
            'review_count': len(new.get('review_required') or []),
            'pending_count': len(new.get('detail_candidates') or []),
        })
    if recovered:
        print(json.dumps({
            'event': 'event_source_recovered', 'severity': 'INFO',
            'catalog_attempted_at': catalog['attempted_at'],
            'recovered': recovered,
            'remaining_unavailable_sources': sorted(
                name for name, batch in sources.items()
                if batch.get('status') not in {'fresh', 'partial'}
                or source_age_failure(batch, now=attempted)),
            'partial_sources': sorted(name for name, batch in sources.items()
                                      if batch.get('status') == 'partial'),
            'api_verified': False,
        }, ensure_ascii=False), flush=True)
