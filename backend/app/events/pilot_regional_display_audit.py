"""Build one diagnostic card per TurismoFVG detail for the current year.

A dated interval is shown as a period. Calendar badges do not imply that the
event is open on every intervening day or that the badges are exhaustive.
"""
from datetime import date
from calendar import monthrange
from pathlib import Path
import argparse
import json
import re

from . import engine
from .pilot_details import english_provider_date_range, german_provider_date_range
from .pilot_regional_forward_audit import FORWARD_AUDIT_SCHEMA
from .pilot_regional_identity import single_month_calendar_day
from .pilot_regional_semantic_audit import SCHEMA as SEMANTIC_SCHEMA
from .pilot_regional_discrepancy_audit import SCHEMA as DISCREPANCY_SCHEMA
from .pilot_regional_sitemap_cards import SCHEMA as SITEMAP_CARDS_SCHEMA
from .pilot_regional_year_control import (SCHEMA as YEAR_CONTROL_SCHEMA,
                                          INSPECTION_VERSION)
from .pilot_regional_location import resolve_turismofvg_municipality


MONTH_LABELS = 'gennaio febbraio marzo aprile maggio giugno luglio agosto settembre ottobre novembre dicembre'.split()
ATTEMS_PROGRAMME_TITLES = {
    'https://www.turismofvg.it/eventi/italia-settanta-la-creativita-come-antidoto-arte-moda-design-eventi-collaterali-502715':
        ('2026-09-01', '2026-11-29', 'Italia Settanta · visite guidate e iniziative'),
    'https://www.turismofvg.it/eventi/italia-settanta-la-creativita-come-antidoto-arte-moda-design-eventi-collaterali-505824':
        ('2026-10-01', '2026-10-15', 'Italia Settanta · eventi di ottobre'),
}


def reviewed_attems_programme_title(url, event, start, end):
    """Distinguish two verified programmes that the provider titles alike."""
    reviewed = ATTEMS_PROGRAMME_TITLES.get(url)
    if not reviewed or not start or not end:
        return event.get('title')
    title = engine.normalize_for_search(event.get('title'))
    venue = engine.normalize_for_search(event.get('venue'))
    if ((start.isoformat(), end.isoformat()) == reviewed[:2]
            and engine.normalize_for_search(event.get('event_city')) == 'gorizia'
            and 'palazzo attems' in venue
            and 'italia settanta' in title
            and 'eventi collaterali' in title):
        return reviewed[2]
    return event.get('title')


def programme_date_label(days):
    first, last = days[0], days[-1]
    if len(days) == 1:
        return f'{first.day} {MONTH_LABELS[first.month - 1]} {first.year}'
    return (f'{first.day} {MONTH_LABELS[first.month - 1]} – '
            f'{last.day} {MONTH_LABELS[last.month - 1]} {last.year} '
            f'· {len(days)} date nel programma')


def display_dates(date_text):
    if not re.search(r'\b20\d{2}\b', date_text or ''):
        return None, None
    start, end = engine.parse_event_date_range(date_text)
    if not start:
        start, end = english_provider_date_range(date_text)
    if not start:
        start, end = german_provider_date_range(date_text)
    if not start or not end or end < start:
        return None, None
    return start, end


def create_display_audit(forward, semantic, *, today, discrepancy=None,
                         sitemap_cards=None, year_control=None, window_end=None):
    if (forward.get('schema') != FORWARD_AUDIT_SCHEMA
            or semantic.get('schema') != SEMANTIC_SCHEMA
            or forward.get('index_snapshot_id') != semantic.get('index_snapshot_id')
            or forward.get('as_of_date') != semantic.get('as_of_date')
            or forward.get('attempts') or semantic.get('attempts')
            or set(forward.get('results') or {}) != {
                candidate['url'] for candidate in forward.get('candidates') or []}
            or set(semantic.get('results') or {}) != {
                item['url'] for item in semantic.get('items') or []}):
        raise ValueError('incomplete or mismatched TurismoFVG audits')
    if today.isoformat() != forward['as_of_date']:
        raise ValueError('display audit date differs from source snapshot')
    if discrepancy is not None and (
            discrepancy.get('schema') != DISCREPANCY_SCHEMA
            or discrepancy.get('index_snapshot_id') != forward['index_snapshot_id']
            or discrepancy.get('as_of_date') != forward['as_of_date']
            or discrepancy.get('attempts')
            or set(discrepancy.get('results') or {}) != {
                item['url'] for item in discrepancy.get('items') or []}):
        raise ValueError('incomplete or mismatched discrepancy audit')
    if sitemap_cards is not None and (
            sitemap_cards.get('schema') != SITEMAP_CARDS_SCHEMA
            or sitemap_cards.get('index_snapshot_id') != forward['index_snapshot_id']
            or sitemap_cards.get('as_of_date') != forward['as_of_date']
            or sitemap_cards.get('attempts')
            or set(sitemap_cards.get('results') or {}) != {
                item['url'] for item in sitemap_cards.get('items') or []}):
        raise ValueError('incomplete or mismatched sitemap detail audit')
    if year_control is not None and (
            year_control.get('schema') != YEAR_CONTROL_SCHEMA
            or year_control.get('as_of_date') != forward['as_of_date']
            or year_control.get('attempts')
            or set(year_control.get('results') or {}) !=
               set(year_control.get('entries') or {})):
        raise ValueError('incomplete or mismatched current-year detail audit')
    year_end = window_end or date(today.year, 12, 31)
    cards, review = [], []
    candidates = {item['url']: item for item in forward['candidates']}
    aligned = {url: result for url, result in forward['results'].items()
               if result.get('status') == 'detail_aligned'}
    if discrepancy is not None:
        aligned.update({url: result for url, result in discrepancy['results'].items()
                        if result.get('status') == 'identity_aligned_on_recheck'})
    if sitemap_cards is not None:
        if set(sitemap_cards['results']) & set(forward['results']):
            raise ValueError('sitemap details overlap dated calendar')
        aligned.update({url: result for url, result in sitemap_cards['results'].items()
                        if result.get('status') == 'detail_aligned'})
    if year_control is not None:
        if set(year_control['entries']) & (
                set(forward['results']) | set((sitemap_cards or {}).get('results') or {})):
            raise ValueError('current-year details overlap prior audits')
        candidates.update({url: entry['candidate']
                           for url, entry in year_control['entries'].items()
                           if entry.get('candidate')})
        aligned.update({url: result for url, result in year_control['results'].items()
                        if result.get('status') == 'detail_aligned'})
    for url, result in sorted(aligned.items()):
        event = result.get('event') or {}
        listing = candidates.get(url) or {}
        badges = sorted(set(listing.get('listing_occurrences') or []))
        date_text = result.get('resolved_date_full') or result.get('detail_date_full') or ''
        end_only = event.get('schedule_kind') == 'end_only'
        month_range = event.get('schedule_kind') == 'month_range'
        if end_only:
            try:
                end = date.fromisoformat(event['end_date'])
            except (KeyError, TypeError, ValueError):
                review.append({'url': url, 'reason': 'invalid_end_only_deadline'})
                continue
            start = None
        else:
            start, end = display_dates(date_text)
        exact_calendar_day = single_month_calendar_day(listing, date_text, event)
        if not start and exact_calendar_day:
            start = end = exact_calendar_day
            date_text = programme_date_label([exact_calendar_day])
        month_only = False
        if not start and event.get('month_schedule_verified'):
            match = re.fullmatch(r'\s*(' + '|'.join(MONTH_LABELS)
                                 + r')\s+(20\d{2})\s*',
                                 engine.normalize_for_search(date_text))
            if match:
                month, year = MONTH_LABELS.index(match[1]) + 1, int(match[2])
                start = date(year, month, 1)
                end = date(year, month, monthrange(year, month)[1])
                month_only = True
        verified_days = []
        if event.get('verified_programme_occurrences'):
            try:
                verified_days = [date.fromisoformat(day) for day in
                                 event['verified_programme_occurrences']]
            except (TypeError, ValueError):
                verified_days = []
            if (not verified_days or verified_days != sorted(set(verified_days))
                    or any(day.year not in {today.year, year_end.year}
                           for day in verified_days)):
                review.append({'url': url, 'reason': 'invalid_verified_programme'})
                continue
            start, end = verified_days[0], verified_days[-1]
        calendar_days = []
        foreign_start, foreign_end = german_provider_date_range(date_text)
        if (foreign_start and not verified_days and badges
                and event.get('schedule_kind') == 'occurrences'):
            try:
                calendar_days = [date.fromisoformat(day) for day in badges]
            except ValueError:
                calendar_days = []
            if (not calendar_days or any(day.year not in {today.year, year_end.year} or
                    not foreign_start <= day <= foreign_end for day in calendar_days)
                    or event.get('occurrences') != badges
                    or event.get('start_date') != badges[0]
                    or event.get('end_date') != badges[-1]):
                review.append({'url': url, 'reason': 'foreign_calendar_dates_conflict'})
                continue
            start, end = calendar_days[0], calendar_days[-1]
        recurrence = False
        if not start and result.get('schedule_interpretation') == 'recurrence_requires_expansion':
            try:
                days = [parsed for day in badges
                        if today <= (parsed := date.fromisoformat(day)) <= year_end]
            except ValueError:
                days = []
            if date_text and days:
                start, end = days[0], days[-1]
                recurrence = True
        if not start and not end_only:
            review.append({'url': url, 'reason': 'date_bounds_not_explicit'})
            continue
        if end < today or (start and start > year_end):
            continue
        semantic_result = (semantic.get('results') or {}).get(url)
        # Prose schedule analysis cannot veto an explicit date row. Only a
        # newly changed detail or an explicit programme-change notice can
        # invalidate a previously inspected page.
        if semantic_result and semantic_result.get('reason') in {
                'detail_changed_since_index', 'programme_change_or_unfinished'}:
            review.append({'url': url, 'reason': semantic_result['reason']})
            continue
        discrete = ([] if end_only else
                    engine.parse_turismofvg_discrete_occurrences(date_text))
        if discrete and not verified_days and result.get('schedule_interpretation') == 'explicit_discrete_dates':
            if (event.get('start_date') != discrete[0]
                    or event.get('end_date') != discrete[-1]):
                review.append({'url': url, 'reason': 'discrete_bounds_conflict'})
                continue
            start, end = date.fromisoformat(discrete[0]), date.fromisoformat(discrete[-1])
        if discrete and not verified_days and (discrete[0] != start.isoformat()
                         or discrete[-1] != end.isoformat()):
            review.append({'url': url, 'reason': 'discrete_bounds_conflict'})
            continue
        kind = ('end_only' if end_only else 'month_range' if month_range else
                'single' if len(verified_days) == 1 else
                'explicit_dates' if verified_days or calendar_days else 'month' if month_only else
                'recurring' if recurrence else 'single' if start == end
                else 'explicit_dates' if discrete else 'period')
        # Only an inspected programme/date row proves individual opening days.
        # Listing badges and the endpoints of a period are not that programme.
        occurrences = ([day.isoformat() for day in verified_days or calendar_days]
                       or discrete)
        opening_days_status = (
            'daily' if result.get('schedule_interpretation')
                == 'inauguration_and_daily_opening_until_end' else 'unknown')
        town = resolve_turismofvg_municipality(event.get('event_city'))
        source_point = (event.get('lat'), event.get('lon'))
        places = event.get('listed_municipalities') or []
        if not town and not places and (event.get('location_confidence') not in
                                        {'source_map', 'source_locality'}
                                        or any(value is None for value in source_point)):
            review.append({'url': url, 'reason': 'municipality_not_resolved'})
            continue
        lat, lon = ((town.latitude, town.longitude) if town else
                    source_point if not places else (None, None))
        cards.append({
            'source': 'TurismoFVG', 'url': url,
            'title': reviewed_attems_programme_title(url, event, start, end),
            'event_city': event.get('event_city'),
            'lat': lat, 'lon': lon,
            'location_confidence': ('municipality' if town else
                                    'multiple_municipalities' if places else
                                    event.get('location_confidence')),
            **({'location_source_url': event['location_source_url']}
               if event.get('location_source_url') else {}),
            **({'listed_municipalities': places} if places else {}),
            'venue': event.get('venue'), 'place': event.get('place'),
            'category': listing.get('category'), 'image': listing.get('image'),
            'start_date': start.isoformat() if start else None,
            'end_date': end.isoformat(),
            'date_label': (f'{date_text} · {today.year}'
                           if recurrence and str(today.year) not in date_text
                           else programme_date_label(verified_days)
                           if verified_days else
                           f'{calendar_days[0].day} {MONTH_LABELS[calendar_days[0].month - 1]} – '
                           f'{calendar_days[-1].day} {MONTH_LABELS[calendar_days[-1].month - 1]} '
                           f'{calendar_days[-1].year} · {len(calendar_days)} date nel calendario'
                           if calendar_days else event.get('date_label')
                           if month_range else date_text),
            'schedule_kind': kind,
            **({'occurrences': occurrences} if occurrences else {}),
            **({'opening_days_status': opening_days_status}
               if kind in {'period', 'recurring', 'month'} and not occurrences else {}),
            **{key: event[key] for key in ('time', 'end_time') if event.get(key)},
            **({'date_precision': 'month'} if month_range else {}),
            'date_evidence_kind': 'event_schedule',
            'date_evidence': (', '.join(day.isoformat() for day in verified_days)
                              if verified_days else ', '.join(badges)
                              if recurrence or calendar_days else date_text),
            **({'verified_programme_occurrences': [day.isoformat()
                                                   for day in verified_days]}
               if verified_days else {}),
            'detail_status': 'inspected',
            'sort_date': (end.isoformat() if end_only else
                          next(day for day in verified_days if day >= today).isoformat()
                          if verified_days else
                          next(day for day in calendar_days if day >= today).isoformat()
                          if calendar_days else
                          next((day for day in discrete if day >= today.isoformat()),
                               end.isoformat()) if discrete else
                          min((day for day in badges if day >= today.isoformat()),
                              default=max(start, today).isoformat())
                          if month_only else max(start, today).isoformat()),
            **{key: event[key] for key in ('description_excerpt',
                                          'description_source_name',
                                          'description_source_url') if event.get(key)},
        })
    cards.sort(key=lambda item: (item['sort_date'],
                                 engine.normalize_for_search(item.get('title')),
                                 item['url']))
    # The provider sometimes repeats boilerplate across unrelated pages.
    # Keep only excerpts that identify one title or a group of same-title pages.
    titles_by_excerpt = {}
    for card in cards:
        excerpt = engine.normalize_for_search(card.get('description_excerpt'))
        if excerpt:
            titles_by_excerpt.setdefault(excerpt, set()).add(
                engine.normalize_for_search(card.get('title')))
    for card in cards:
        excerpt = engine.normalize_for_search(card.get('description_excerpt'))
        if excerpt and len(titles_by_excerpt[excerpt]) > 1:
            for key in ('description_excerpt', 'description_source_name',
                        'description_source_url'):
                card.pop(key, None)
    return {'as_of_date': today.isoformat(), 'year_end': year_end.isoformat(),
            'source_candidates': len(forward['candidates']) + len(
                sitemap_cards['items'] if sitemap_cards else []) + len(
                year_control['entries'] if year_control else []),
            'cards': cards, 'review': review}


def create_year_display_audit(control, *, today):
    """Project a fully inspected annual or rolling control into pilot cards.

    Review and ambiguous details remain quarantined. This diagnostic does not
    publish a catalog, even if every detail has been inspected.
    """
    if (control.get('schema') != YEAR_CONTROL_SCHEMA
            or control.get('as_of_date') != today.isoformat()
            or control.get('attempts')
            or set(control.get('results') or {}) != set(control.get('entries') or {})):
        raise ValueError('incomplete or mismatched TurismoFVG year control')
    candidates = []
    for url, entry in control['entries'].items():
        candidate = dict(entry.get('candidate') or {'url': url})
        candidate.update(entry.get('listing_display') or {})
        candidates.append(candidate)
    index_id = control.get('index_fingerprint') or 'annual-control'
    forward = {'schema': FORWARD_AUDIT_SCHEMA, 'as_of_date': today.isoformat(),
               'index_snapshot_id': index_id, 'candidates': candidates,
               'results': control['results'], 'attempts': {}}
    semantic = {'schema': SEMANTIC_SCHEMA, 'as_of_date': today.isoformat(),
                'index_snapshot_id': index_id, 'items': [], 'results': {},
                'attempts': {}}
    window_end = (date.fromisoformat(control['window_end'])
                  if control.get('window_end') else None)
    audit = create_display_audit(forward, semantic, today=today,
                                 window_end=window_end)
    statuses = {}
    for result in control['results'].values():
        status = result.get('status') or 'unknown'
        statuses[status] = statuses.get(status, 0) + 1
    audit['control_statuses'] = statuses
    accepted = {'detail_aligned', 'past_event', 'non_event',
                'non_event_experience', 'excluded_current_year',
                'duplicate_detail'}
    audit['inventory_complete'] = (control.get('inspection_version') == INSPECTION_VERSION
                                and not control.get('removed_future_urls')
                                and set(statuses) <= accepted | {'ambiguous', 'review_required'})
    audit['source_complete'] = (audit['inventory_complete'] and not audit['review']
                                and set(statuses) <= accepted)
    audit['quarantined'] = [
        {'url': url, 'status': result.get('status'), 'reason': result.get('reason')}
        for url, result in control['results'].items()
        if result.get('status') in {'ambiguous', 'review_required'}]
    return audit


def summary(audit):
    cards = audit['cards']
    return {'as_of_date': audit['as_of_date'],
            'source_candidates': audit['source_candidates'],
            'period_cards': sum(item['schedule_kind'] == 'period' for item in cards),
            'month_range_cards': sum(item['schedule_kind'] == 'month_range'
                                     for item in cards),
            'end_only_cards': sum(item['schedule_kind'] == 'end_only' for item in cards),
            'month_cards': sum(item['schedule_kind'] == 'month' for item in cards),
            'single_date_cards': sum(item['schedule_kind'] == 'single' for item in cards),
            'explicit_date_cards': sum(item['schedule_kind'] == 'explicit_dates' for item in cards),
            'recurring_cards': sum(item['schedule_kind'] == 'recurring' for item in cards),
            'cards_with_preview': sum(bool(item.get('description_excerpt')) for item in cards),
            'cards_total': len(cards), 'hard_conflicts': len(audit['review']),
            **({'quarantined': len(audit['quarantined']),
                'source_complete': audit['source_complete']}
               if 'quarantined' in audit else {})}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--forward', type=Path)
    parser.add_argument('--semantic', type=Path)
    parser.add_argument('--annual-control', type=Path)
    parser.add_argument('--discrepancies', type=Path)
    parser.add_argument('--sitemap-cards', type=Path)
    parser.add_argument('--year-control', type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    if args.annual_control:
        if args.forward or args.semantic or args.discrepancies or args.sitemap_cards or args.year_control:
            parser.error('--annual-control cannot be combined with legacy audits')
        with args.annual_control.open(encoding='utf-8') as stream:
            control = json.load(stream)
        audit = create_year_display_audit(
            control, today=date.fromisoformat(control['as_of_date']))
        from .pilot_regional_sitemap_audit import write_snapshot
        write_snapshot(args.output, audit)
        print(json.dumps(summary(audit), ensure_ascii=False, indent=2))
        return
    if not args.forward or not args.semantic:
        parser.error('--forward and --semantic are required without --annual-control')
    with args.forward.open(encoding='utf-8') as stream:
        forward = json.load(stream)
    with args.semantic.open(encoding='utf-8') as stream:
        semantic = json.load(stream)
    if args.discrepancies:
        with args.discrepancies.open(encoding='utf-8') as stream:
            discrepancy = json.load(stream)
    else:
        discrepancy = None
    if args.sitemap_cards:
        with args.sitemap_cards.open(encoding='utf-8') as stream:
            sitemap_cards = json.load(stream)
    else:
        sitemap_cards = None
    if args.year_control:
        with args.year_control.open(encoding='utf-8') as stream:
            year_control = json.load(stream)
    else:
        year_control = None
    audit = create_display_audit(
        forward, semantic, today=date.fromisoformat(forward['as_of_date']),
        discrepancy=discrepancy, sitemap_cards=sitemap_cards,
        year_control=year_control)
    from .pilot_regional_sitemap_audit import write_snapshot
    write_snapshot(args.output, audit)
    print(json.dumps(summary(audit), ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
