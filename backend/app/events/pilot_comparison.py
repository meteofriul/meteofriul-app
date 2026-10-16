"""Offline, non-publishing comparison. A candidate match is never a merge."""
from collections import Counter, defaultdict
from datetime import date, time
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode
import unicodedata
from . import engine


def token(value):
    return ' '.join(unicodedata.normalize('NFKC', str(value or '')).casefold().split())


def reference(value):
    parsed = urlsplit(str(value or ''))
    if parsed.scheme not in {'https', 'http'} or not parsed.hostname or parsed.path in {'', '/'}:
        return ''
    query = sorted((k, v) for k, v in parse_qsl(parsed.query, keep_blank_values=True)
                   if not k.lower().startswith('utm_'))
    return urlunsplit((parsed.scheme, parsed.netloc.lower(), parsed.path, urlencode(query), ''))


def normalized(event):
    start, end = event.get('start_date'), event.get('end_date')
    if not start:
        a, b = engine.parse_event_date_range(event.get('date'))
        start, end = a.isoformat() if a else '', b.isoformat() if b else ''
    return {'url': reference(event.get('url')), 'title': token(event.get('title')),
            'start': start or '', 'end': end or start or '',
            'time': token(event.get('time') or event.get('start_time')),
            'city': token(event.get('event_city')), 'venue': token(event.get('venue')),
            'address': token(event.get('address')), 'place': token(event.get('place')),
            'occurrences': tuple(sorted(event.get('occurrences') or []))}


def inspect(events):
    issues, identities = [], defaultdict(list)
    for index, event in enumerate(events):
        item = normalized(event)
        reasons = []
        if not item['url']:
            reasons.append('missing_event_reference')
        if not item['title'] or not item['city']:
            reasons.append('missing_title_or_city')
        try:
            start, end = date.fromisoformat(item['start']), date.fromisoformat(item['end'])
            if end < start:
                reasons.append('inverted_dates')
            for occurrence in item['occurrences']:
                if not start <= date.fromisoformat(occurrence) <= end:
                    reasons.append('occurrence_outside_range')
        except (ValueError, TypeError):
            reasons.append('invalid_dates')
        if item['time']:
            try:
                time.fromisoformat(item['time'])
            except ValueError:
                reasons.append('invalid_time')
        else:
            reasons.append('unknown_time')
        if event.get('event_status') in {'cancelled', 'postponed', 'conflicting'}:
            reasons.append('schedule_requires_review')
        if not event.get('description'):
            reasons.append('missing_description')
        if reasons:
            issues.append({'index': index, 'source': event.get('source'), 'url': item['url'],
                           'reasons': sorted(set(reasons))})
        # Do not identify nameless/reference-less rows as certain duplicates.
        if item['url'] and item['title'] and item['city'] and item['start']:
            key = (event.get('source'), tuple(item.items()))
            identities[key].append(index)
    return {'count': len(events), 'by_source': dict(Counter(e.get('source', 'unknown') for e in events)),
            'issues': issues, 'exact_duplicate_groups': [v for v in identities.values() if len(v) > 1]}


def compare(legacy, pilot):
    """Report differences without assuming either pipeline is ground truth.

    Both arrays must describe the same acquisition scope. All matching is
    one-to-many: picking the first match would conceal lost replicas.
    """
    left, right = [normalized(e) for e in legacy], [normalized(e) for e in pilot]
    pairs, missing, matched_right = [], [], set()
    for index, item in enumerate(left):
        candidates = [j for j, other in enumerate(right)
                      if (item['url'] and item['url'] == other['url']) or
                      (item['title'] and item['city'] and item['title'] == other['title']
                       and item['city'] == other['city'])]
        if not candidates:
            missing.append(index)
            continue
        for j in candidates:
            matched_right.add(j)
            differences = [key for key in ('title', 'start', 'end', 'time', 'city', 'venue', 'address', 'place', 'occurrences')
                           if item[key] != right[j][key]]
            pairs.append({'legacy_index': index, 'pilot_index': j, 'differences': differences,
                          'same_reference': bool(item['url'] and item['url'] == right[j]['url'])})
    return {'status': 'requires_review', 'legacy': inspect(legacy), 'pilot': inspect(pilot),
            'candidate_pairs': pairs, 'legacy_without_candidate': missing,
            'pilot_without_candidate': [j for j in range(len(right)) if j not in matched_right],
            'warning': 'Candidates are not confirmed identities. Missing candidates are not proven lost events.'}
