"""Local, resumable interpretation of ambiguous TurismoFVG date ranges.

Only explicit, exhaustive schedules are resolved. The full description is
read for evidence and discarded; the snapshot stores compact date facts.
"""
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
import argparse
import difflib
import json
import re
import unicodedata

from . import engine
from .pilot_regional_forward_audit import FORWARD_AUDIT_SCHEMA
from .pilot_regional_sitemap_audit import classify_detail, fetch_detail, write_snapshot
from .pilot_schedule import schedule_notice


SCHEMA = 'turismofvg-semantic-schedule-audit-v1'
CARD_HARD_CONFLICTS = {
    'badge_not_in_explicit_programme', 'badge_conflicts_with_open_weekdays',
    'badge_outside_detail_bounds', 'detail_changed_since_index',
    'programme_change_or_unfinished', 'day_outside_detail_bounds',
    'day_year_outside_bounds',
}
NEEDS_INTERPRETATION = {
    'bounded_period_needs_opening_evidence',
    'range_with_badges_needs_interpretation',
    'recurrence_requires_expansion',
    'discrete_dates_conflict',
}
MONTHS = {name: index for index, name in enumerate(
    'gennaio febbraio marzo aprile maggio giugno luglio agosto settembre ottobre novembre dicembre'.split(), 1)}
WEEKDAYS = {name: index for index, name in enumerate(
    'lunedi martedi mercoledi giovedi venerdi sabato domenica'.split())}
MONTH_PATTERN = '|'.join(MONTHS)
DAY_GROUP = re.compile(
    rf'(?<!\d)(?P<days>\d{{1,2}}(?:\s*(?:-|–|/|,|\be\b)\s*\d{{1,2}})*)'
    rf'\s+(?P<month>{MONTH_PATTERN})(?:\s+(?P<year>(?:18|19|20)\d{{2}}))?\b', re.I)
WEEKDAY_HEADING = re.compile(
    rf'\b(?:{"|".join(WEEKDAYS)})\s+\d{{1,2}}\s+(?:{MONTH_PATTERN})\b', re.I)
EXHAUSTIVE_DATES = re.compile(
    r'\b(?:calendario\s+(?:delle\s+)?aperture|le\s+date\s+(?:per\s+il\s+20\d{2}\s+)?sono|'
    r'festeggiamenti\s+si\s+svolgeranno\s+nei\s+weekend|giornate\s*:)', re.I)
WEEKLY_OPENING = re.compile(
    rf'\b(?:visitabile|apert[oaie])\s+(?:da|dal)\s+(?P<first>{"|".join(WEEKDAYS)})'
    rf'\s+(?:a|al|alla)\s+(?P<last>{"|".join(WEEKDAYS)})\b', re.I)
DATED_OPEN_RANGE = re.compile(
    rf'\bda\s+(?P<first_weekday>{"|".join(WEEKDAYS)})\s+'
    rf'(?P<first_day>\d{{1,2}})\s+(?P<first_month>{MONTH_PATTERN})\s+'
    rf'a\s+(?P<last_weekday>{"|".join(WEEKDAYS)})\s+'
    rf'(?P<last_day>\d{{1,2}})\s+(?P<last_month>{MONTH_PATTERN})\b', re.I)
UNFINISHED_PROGRAMME = re.compile(
    r'\b(?:in\s+fase\s+di\s+programmazione|date\s+da\s+confermare|'
    r'programma\s+(?:non\s+ancora\s+disponibile|disponibile\s+dal))\b', re.I)
EXCEPTIONS = re.compile(r'\b(?:esclus[oi]|chius[oi]|festiv[oi]|eccetto|tranne)\b', re.I)


def plain(value):
    return unicodedata.normalize('NFKD', str(value or '').lower()).encode('ascii', 'ignore').decode('ascii')


def date_bounds(value):
    years = {int(year) for year in re.findall(r'\b20\d{2}\b', value or '')}
    start, end = engine.parse_event_date_range(value or '')
    if (not start or not end or start.year not in years or end.year not in years
            or end < start):
        return None, None
    return start, end


def explicit_days(description, *, start, end):
    """Read day/month groups only within a single explicitly dated year."""
    if start.year != end.year:
        return [], 'cross_year_inference'
    normalized = plain(description)
    groups = list(DAY_GROUP.finditer(normalized))
    if not groups:
        return [], 'no_explicit_day_groups'
    dates = set()
    for match in groups:
        year = int(match['year']) if match['year'] else start.year
        # Biographical dates in the event prose describe people or places,
        # not additional days of the current programme.
        if year < 2000:
            continue
        if year != start.year:
            return [], 'day_year_outside_bounds'
        day_numbers = [int(value) for value in re.findall(r'\d{1,2}', match['days'])]
        hyphen_pairs = re.findall(r'(?<!\d)(?=(\d{1,2})\s*[-–]\s*(\d{1,2}))', match['days'])
        if (not day_numbers or any(not 1 <= value <= 31 for value in day_numbers)
                or any(int(right) - int(left) > 1 for left, right in hyphen_pairs)):
            return [], 'ambiguous_day_group'
        for day_number in day_numbers:
            try:
                candidate = date(year, MONTHS[match['month']], day_number)
            except ValueError:
                return [], 'invalid_calendar_day'
            if not start <= candidate <= end:
                return [], 'day_outside_detail_bounds'
            dates.add(candidate)
    # A misspelled month in a numeric group must not silently drop that day.
    for match in re.finditer(r'\b\d{1,2}(?:\s*[-–/]\s*\d{1,2})+\s+([a-z]{3,12})\b', normalized):
        if match[1] not in MONTHS:
            return [], 'unparsed_day_group'
    for match in re.finditer(r'\b\d{1,2}\s+([a-z]{5,12})\b', normalized):
        if (match[1] not in MONTHS
                and difflib.get_close_matches(match[1], MONTHS, n=1, cutoff=0.78)):
            return [], 'unparsed_day_group'
    return [item.isoformat() for item in sorted(dates)], None


def dated_open_range_days(description, *, start, end):
    """Expand only a bounded opening range with matching named weekdays."""
    prose = plain(description)
    days = set()
    for match in DATED_OPEN_RANGE.finditer(prose):
        context = prose[max(0, match.start() - 150):match.start()]
        if not re.search(r'\b(?:visitabil|apert|orari)\w*\b', context):
            continue
        try:
            first = date(start.year, MONTHS[match['first_month']],
                         int(match['first_day']))
            last = date(start.year, MONTHS[match['last_month']],
                        int(match['last_day']))
        except ValueError:
            return [], 'invalid_calendar_day'
        if (first.weekday() != WEEKDAYS[match['first_weekday']]
                or last.weekday() != WEEKDAYS[match['last_weekday']]
                or not start <= first <= last <= end
                or (last - first).days > 31):
            return [], 'ambiguous_open_range'
        days.update(first + timedelta(days=offset)
                    for offset in range((last - first).days + 1))
    return [item.isoformat() for item in sorted(days)], None


def anchored_programme_days(description, *, start, end):
    """Read dates in a sentence explicitly naming when excursions occur."""
    match = re.search(
        r'\b(?:escursioni|gite|visite\s+guidate)\s+si\s+terranno\s+'
        r'([^.]{20,250})\.', description or '', re.I)
    if not match:
        return []
    days, reason = explicit_days(match[1], start=start, end=end)
    return days if not reason and len(days) >= 2 else []


def separated_programme_days(description, *, start, end):
    """Exclude clearly labelled related events from this detail's programme."""
    prose = plain(description)
    if start == end and 'prossime escursioni previste:' in prose:
        primary = prose.split('prossime escursioni previste:', 1)[0]
    elif ('eventi collaterali' in prose
          and 'la mostra sara visitabile fino' in prose):
        primary = prose.split('la mostra sara visitabile fino', 1)[0]
    else:
        return []
    days, reason = explicit_days(primary, start=start, end=end)
    return days if not reason and days else []


def interpret_schedule(date_text, description, listing_days, *, today):
    start, end = date_bounds(date_text)
    if not start:
        return {'status': 'review_required', 'reason': 'unparsed_explicit_bounds'}
    prose = plain(description)
    if schedule_notice(description) or UNFINISHED_PROGRAMME.search(prose):
        return {'status': 'review_required', 'reason': 'programme_change_or_unfinished'}
    if not description:
        return {'status': 'review_required', 'reason': 'missing_description_schedule'}
    try:
        badges = {date.fromisoformat(day) for day in listing_days or []}
    except (ValueError, TypeError):
        return {'status': 'review_required', 'reason': 'invalid_listing_badges'}
    if any(not start <= day <= end for day in badges):
        return {'status': 'review_required', 'reason': 'badge_outside_detail_bounds'}

    programme_days = anchored_programme_days(description, start=start, end=end)
    if programme_days and {day.isoformat() for day in badges} == set(programme_days):
        return {'status': 'resolved_explicit_dates',
                'reason': 'anchored_excursion_programme',
                'occurrences': programme_days,
                'future_occurrences': [day for day in programme_days
                                       if date.fromisoformat(day) >= today]}
    separated_days = separated_programme_days(description, start=start, end=end)
    if separated_days and {day.isoformat() for day in badges} == set(separated_days):
        return {'status': 'resolved_explicit_dates',
                'reason': 'related_event_dates_separated',
                'occurrences': separated_days,
                'future_occurrences': [day for day in separated_days
                                       if date.fromisoformat(day) >= today]}

    weekly = WEEKLY_OPENING.search(prose)
    if weekly:
        if EXCEPTIONS.search(prose):
            return {'status': 'review_required', 'reason': 'weekly_opening_with_exceptions'}
        first, last = WEEKDAYS[weekly['first']], WEEKDAYS[weekly['last']]
        if first > last:
            return {'status': 'review_required', 'reason': 'wrapped_weekday_range'}
        weekdays = list(range(first, last + 1))
        if any(day.weekday() not in weekdays for day in badges):
            return {'status': 'review_required', 'reason': 'badge_conflicts_with_open_weekdays'}
        return {'status': 'resolved_weekly_opening',
                'reason': 'explicit_open_weekdays_in_detail',
                'start_date': start.isoformat(), 'end_date': end.isoformat(),
                'open_weekdays': weekdays}

    dates, parse_error = explicit_days(description, start=start, end=end)
    range_days, range_error = dated_open_range_days(description, start=start, end=end)
    if range_error:
        return {'status': 'review_required', 'reason': range_error}
    dates = sorted(set(dates) | set(range_days))
    exhaustive = bool(EXHAUSTIVE_DATES.search(prose))
    dated_headings = len(WEEKDAY_HEADING.findall(prose)) >= 2
    if parse_error and (exhaustive or dated_headings):
        return {'status': 'review_required', 'reason': parse_error}
    if dated_headings and any(day.isoformat() not in dates for day in badges):
        return {'status': 'review_required', 'reason': 'badge_not_in_explicit_programme'}
    if exhaustive and len(dates) >= 2:
        if any(day.isoformat() not in dates for day in badges):
            return {'status': 'review_required', 'reason': 'badge_not_in_explicit_programme'}
        future_dates = [day for day in dates if date.fromisoformat(day) >= today]
        if not future_dates:
            return {'status': 'review_required', 'reason': 'no_future_explicit_dates'}
        return {'status': 'resolved_explicit_dates',
                'reason': 'complete_dated_programme_in_detail',
                'occurrences': dates, 'future_occurrences': future_dates}
    return {'status': 'review_required',
            'reason': 'programme_not_explicit_or_complete',
            'detected_day_groups': len(dates)}


def create_snapshot(forward):
    if forward.get('schema') != FORWARD_AUDIT_SCHEMA or forward.get('attempts'):
        raise ValueError('incomplete TurismoFVG forward audit')
    candidates = {item['url']: item for item in forward['candidates']}
    if set(forward['results']) != set(candidates):
        raise ValueError('incomplete TurismoFVG detail inventory')
    items = []
    for url, result in sorted(forward['results'].items()):
        if result.get('status') != 'detail_aligned' or result.get('schedule_interpretation') not in NEEDS_INTERPRETATION:
            continue
        event = result.get('event') or {}
        items.append({'url': url, 'title': event.get('title'),
                      'event_city': event.get('event_city'),
                      'detail_date_full': result.get('detail_date_full'),
                      'listing_occurrences': candidates[url].get('listing_occurrences') or [],
                      'prior_interpretation': result['schedule_interpretation']})
    return {'schema': SCHEMA, 'as_of_date': forward['as_of_date'],
            'index_snapshot_id': forward['index_snapshot_id'],
            'created_at': datetime.now(timezone.utc).isoformat(),
            'items': items, 'results': {}, 'attempts': {}}


def inspect_item(item, html, *, today):
    detail = classify_detail(item['url'], html, today=today)
    if (engine.normalize_for_search(detail.get('date_full'))
            != engine.normalize_for_search(item.get('detail_date_full'))
            or engine.normalize_for_search(detail.get('title'))
            != engine.normalize_for_search(item.get('title'))
            or engine.normalize_for_search(detail.get('event_city'))
            != engine.normalize_for_search(item.get('event_city'))):
        return {'status': 'review_required', 'reason': 'detail_changed_since_index'}
    description = engine.extract_turismofvg_description(html) or ''
    result = interpret_schedule(item['detail_date_full'], description,
                                item['listing_occurrences'], today=today)
    return {**result, 'checked_at': datetime.now(timezone.utc).isoformat()}


def inspect_batch(snapshot, *, batch_size=24, max_workers=3,
                  max_attempts=3, fetch_html=fetch_detail):
    if (snapshot.get('schema') != SCHEMA or not 1 <= batch_size <= 256
            or not 1 <= max_workers <= 3):
        raise ValueError('invalid TurismoFVG semantic audit batch')
    items = snapshot['items']
    urls = [item['url'] for item in items]
    if len(urls) != len(set(urls)) or any(not engine.is_trusted_turismofvg_event_url(url) for url in urls):
        raise ValueError('invalid TurismoFVG semantic inventory')
    results = dict(snapshot.get('results') or {})
    attempts = dict(snapshot.get('attempts') or {})
    if set(results) - set(urls) or set(attempts) - set(urls):
        raise ValueError('semantic progress outside inventory')
    todo = sorted((item for item in items if item['url'] not in results
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
                results[url] = inspect_item(item, future.result(), today=today)
                attempts.pop(url, None)
            except Exception as exc:
                attempts[url] = {'count': attempts.get(url, {}).get('count', 0) + 1,
                                 'last_error_type': type(exc).__name__}
    return {**snapshot, 'results': results, 'attempts': attempts}


def summary(snapshot):
    results = snapshot['results']
    return {'as_of_date': snapshot['as_of_date'], 'items': len(snapshot['items']),
            'inspected': len(results), 'remaining': len(snapshot['items']) - len(results),
            'attempts': len(snapshot['attempts']),
            **{status: sum(item.get('status') == status for item in results.values())
               for status in ('resolved_explicit_dates', 'resolved_weekly_opening',
                              'review_required')}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--snapshot', required=True, type=Path)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--create-from', type=Path)
    group.add_argument('--batch', type=int)
    group.add_argument('--run', action='store_true')
    group.add_argument('--recheck-resolved', action='store_true')
    args = parser.parse_args()
    if args.create_from:
        if args.snapshot.exists():
            parser.error('snapshot already exists')
        with args.create_from.open(encoding='utf-8') as stream:
            snapshot = create_snapshot(json.load(stream))
    else:
        with args.snapshot.open(encoding='utf-8') as stream:
            snapshot = json.load(stream)
        if args.recheck_resolved:
            snapshot = {**snapshot, 'results': {
                url: item for url, item in snapshot['results'].items()
                if item.get('status') not in {'resolved_explicit_dates',
                                              'resolved_weekly_opening'}}}
        elif args.run:
            while True:
                revised = inspect_batch(snapshot)
                if revised['results'] == snapshot['results'] and revised['attempts'] == snapshot['attempts']:
                    break
                snapshot = revised
                write_snapshot(args.snapshot, snapshot)
                if len(snapshot['results']) % 120 < 24:
                    print(json.dumps(summary(snapshot), ensure_ascii=False), flush=True)
        else:
            snapshot = inspect_batch(snapshot, batch_size=args.batch)
    write_snapshot(args.snapshot, snapshot)
    print(json.dumps(summary(snapshot), ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
