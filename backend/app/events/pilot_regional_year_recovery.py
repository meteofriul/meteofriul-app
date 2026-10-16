"""Recover dated TurismoFVG programmes when its labelled date row is prose.

Only the current-year calendar can nominate these details. Every recovered
date must be corroborated by the public detail itself; an unverified year or
opening day stays in review.
"""
from datetime import date, datetime, timedelta
import re

from . import engine
from .pilot_details import promote_candidate
from .pilot_excerpt import attributed_excerpt
from .pilot_regional_location import extract_turismofvg_map_point
from .pilot_regional_year_exclusions import MONTHS, WEEKDAYS, plain


MONTH = '|'.join(MONTHS)
WEEKDAY = '|'.join(WEEKDAYS)
NAMED_DAY = re.compile(
    rf'\b(?P<weekday>{WEEKDAY})\s+(?P<day>\d{{1,2}})\s+'
    rf'(?P<month>{MONTH})\b')
DAY_MONTH = re.compile(rf'\b\d{{1,2}}\s+(?:{MONTH})\b')
TWO_PERIODS = re.compile(
    rf'^dal\s+(\d{{1,2}})\s+al\s+(\d{{1,2}})\s+({MONTH})'
    rf'\s+e\s+dal\s+(\d{{1,2}})\s+al\s+(\d{{1,2}})\s+({MONTH})$')
OPEN_WEEKENDS = re.compile(
    rf'^venerdi,?\s+sabato\s+e\s+domenica\s+fino\s+al\s+'
    rf'(\d{{1,2}})\s+({MONTH})$')
END_ONLY = re.compile(
    rf'^fino\s+al\s+(\d{{1,2}})\s+({MONTH})\s+(20\d{{2}})$')
MONTH_RANGE = re.compile(
    rf'\b({MONTH})\s*-\s*({MONTH})\s+(20\d{{2}})\b')
DISCRETE_DAY = re.compile(
    rf'\b(?P<day>\d{{1,2}})\s+(?P<month>{MONTH})'
    r'(?:\s+(?P<year>20\d{2}))?\b')


def recover_barcolana_2026_locale(url, entry, html, *, today):
    """Reconcile one Italian listing whose official detail is German-only."""
    if (today.year != 2026
            or url != 'https://www.turismofvg.it/eventi/58a-ed-barcolana'
            or entry.get('kind') != 'calendar' or entry.get('identity_conflict')):
        return None
    candidate = entry.get('candidate') or {}
    if (engine.normalize_for_search(candidate.get('title')) != '58a ed. barcolana.'
            or engine.normalize_for_search(candidate.get('event_city')) != 'trieste'
            or candidate.get('listing_occurrences')):
        return None
    metadata = engine.extract_turismofvg_detail_metadata(html)
    title_match = re.search(r'<h1\b[^>]*>(.*?)</h1>', html, re.I | re.S)
    detail_title = engine.clean_event_text(title_match[1]) if title_match else ''
    original_date = metadata.get('date_full') or ''
    if (engine.normalize_for_search(detail_title) != '58. barcolana'
            or engine.normalize_for_search(metadata.get('event_city')) != 'triest'
            or not re.fullmatch(
                r'Freitag, 2\. Oktober 2026\s*-\s*Sonntag, 11\. Oktober 2026',
                original_date, re.I)):
        return None
    resolved_date = '2 ottobre 2026 - 11 ottobre 2026'
    identity = {**metadata, 'date_full': resolved_date,
                'detail_title': candidate['title'], 'event_city': 'Trieste',
                'venue': None, 'official_site': None, 'provider_categories': None}
    event = promote_candidate(candidate, identity)
    if not event or (event['start_date'], event['end_date']) != ('2026-10-02', '2026-10-11'):
        return None
    event['date_evidence'] = original_date
    return {'status': 'detail_aligned', 'reason': 'reviewed_official_german_detail',
            'detail_date_full': original_date, 'resolved_date_full': resolved_date,
            'schedule_interpretation': 'labelled_interval',
            'description_status': 'source_text_other_locale', 'event': event}


def _day(year, month, number):
    try:
        return date(year, MONTHS[month], int(number))
    except ValueError:
        return None


def _dated_programme(row, prose, title, *, year):
    """Return exact days or a bounded exhibition period with source evidence."""
    deadline = END_ONLY.fullmatch(row)
    if deadline and int(deadline[3]) == year:
        opening = re.search(
            rf'\bsi\s+inaugura\s+({WEEKDAY})\s+'
            rf'(\d{{1,2}})\s+({MONTH})\b', prose)
        daily_end = re.search(
            rf'\bsara\s+aperta\s+tutti\s+i\s+giorni\s+fino\s+al\s+'
            rf'{deadline[1]}\s+{deadline[2]}\s+{year}\b', prose)
        if opening and daily_end:
            start = _day(year, opening[3], opening[2])
            end = _day(year, deadline[2], deadline[1])
            if (start and end and start <= end
                    and start.weekday() == WEEKDAYS[opening[1]]
                    and (end - start).days <= 366):
                return start, end, [], 'inauguration_and_daily_opening_until_end'

    if (row == title and str(year) in row and prose.startswith('programma:')
            and not re.search(r'\b20\d{2}\b', prose)):
        matches = list(NAMED_DAY.finditer(prose))
        days = [_day(year, m['month'], m['day']) for m in matches]
        if (len(days) >= 2 and len(days) == len(DAY_MONTH.findall(prose))
                and all(day and day.weekday() == WEEKDAYS[m['weekday']]
                        for day, m in zip(days, matches))
                and days == sorted(set(days))):
            return days[0], days[-1], days, 'dated_programme_with_weekdays'

    month_row = re.fullmatch(rf'({MONTH})\s+{year}', row)
    if month_row:
        public = re.search(
            rf'\bil\s+momento\s+pubblico\s+principale\s+sara\s+'
            rf'(?P<weekday>{WEEKDAY})\s+(?P<day>\d{{1,2}})\s+'
            rf'(?P<month>{MONTH})\b', prose)
        if public and len(DAY_MONTH.findall(prose)) == 1:
            day = _day(year, public['month'], public['day'])
            if (day and public['month'] == month_row[1]
                    and day.weekday() == WEEKDAYS[public['weekday']]):
                return day, day, [day], 'named_public_day_in_month'

    if str(year) in row:
        period = re.search(
            rf'\bla\s+mostra\s+sara\s+visitabile\s+dal\s+giorno\s+'
            rf'(\d{{1,2}})\s+({MONTH})\s+al\s+'
            rf'(\d{{1,2}})\s+({MONTH})\b', prose)
        if period and not re.search(r'\b20\d{2}\b', prose):
            start = _day(year, period[2], period[1])
            end = _day(year, period[4], period[3])
            if start and end and start <= end and (end - start).days <= 60:
                return start, end, [], 'bounded_exhibition_in_description'

    ranges = TWO_PERIODS.fullmatch(row)
    if ranges and f'{row} {year}' in prose:
        first = _day(year, ranges[3], ranges[1])
        first_end = _day(year, ranges[3], ranges[2])
        second = _day(year, ranges[6], ranges[4])
        second_end = _day(year, ranges[6], ranges[5])
        if (first and first_end and second and second_end
                and first <= first_end < second <= second_end
                and (first_end - first).days <= 7
                and (second_end - second).days <= 7):
            days = ([first + timedelta(days=index)
                     for index in range((first_end - first).days + 1)]
                    + [second + timedelta(days=index)
                       for index in range((second_end - second).days + 1)])
            return first, second_end, days, 'two_explicit_programme_periods'

    opening = OPEN_WEEKENDS.fullmatch(row)
    if opening:
        beginning = re.search(
            rf'\bda\s+sabato\s+(\d{{1,2}})\s+({MONTH})\s+{year}\b', prose)
        repeated_end = re.search(
            rf'\bvisitabile\s+ogni\s+venerdi,?\s+sabato\s+e\s+domenica'
            rf'\s+fino\s+al\s+{opening[1]}\s+{opening[2]}\b', prose)
        if beginning and repeated_end:
            start = _day(year, beginning[2], beginning[1])
            end = _day(year, opening[2], opening[1])
            if (start and end and start <= end
                    and start.weekday() == WEEKDAYS['sabato']
                    and end.weekday() == WEEKDAYS['domenica']
                    and (end - start).days <= 120):
                return start, end, [], 'bounded_weekend_exhibition_from_calendar'
    return None


def _detail_fields(html):
    metadata = engine.extract_turismofvg_detail_metadata(html)
    title_match = re.search(r'<h1\b[^>]*>(.*?)</h1>', html, re.I | re.S)
    title = engine.clean_event_text(title_match[1]) if title_match else None
    description = engine.extract_turismofvg_description(html) or ''
    return metadata, title, description


def _promoted(url, entry, html, metadata, title, description, *, date_text,
              programme=None, schedule_kind=None, date_label=None):
    resolved = {**metadata, 'date_full': date_text, 'detail_title': title}
    point = extract_turismofvg_map_point(html)
    if point:
        resolved['map_lat'], resolved['map_lon'] = point
    if programme:
        resolved['programme_occurrences'] = programme
    event = promote_candidate(entry['candidate'], resolved)
    if not event:
        return None
    event.update(attributed_excerpt(
        description, source_name='TurismoFVG', source_url=url, title=title))
    if schedule_kind:
        event['schedule_kind'] = schedule_kind
    if date_label:
        event['date_label'] = date_label
    return event


def recover_discrete_edition(url, entry, html, *, today):
    """Use a fully parsed cross-year list; discard only obsolete past badges."""
    if entry.get('kind') != 'calendar' or entry.get('identity_conflict'):
        return None
    metadata, title, description = _detail_fields(html)
    original = metadata.get('date_full') or ''
    row = plain(original)
    if not title or not metadata.get('event_city') or not description:
        return None
    matches = list(DISCRETE_DAY.finditer(row))
    if len(matches) < 2 or not any(match['year'] for match in matches):
        return None
    remainder = row
    for match in reversed(matches):
        remainder = remainder[:match.start()] + remainder[match.end():]
    if re.sub(r'[\s,;]+|\be\b', '', remainder):
        return None
    inherited_year = None
    parsed = []
    for match in reversed(matches):
        inherited_year = int(match['year']) if match['year'] else inherited_year
        if inherited_year is None:
            return None
        day = _day(inherited_year, match['month'], match['day'])
        if not day:
            return None
        parsed.append(day)
    parsed.reverse()
    if (parsed != sorted(set(parsed))
            or {day.year for day in parsed} != {today.year, today.year + 1}):
        return None
    current_days = [day.isoformat() for day in parsed if day.year == today.year]
    if not current_days or current_days[-1] < today.isoformat():
        return None
    badges = (entry.get('candidate') or {}).get('listing_occurrences') or []
    if (not any(day >= today.isoformat() for day in badges)
            or any(day >= today.isoformat() and day not in current_days
                   for day in badges)):
        return None
    candidate = {**entry['candidate'],
                 'listing_occurrences': [day for day in badges
                                         if day in current_days]}
    resolved = ', '.join(
        f'{day.day} {list(MONTHS)[day.month - 1]}' for day in parsed
        if day.year == today.year) + f' {today.year}'
    event = _promoted(url, {**entry, 'candidate': candidate}, html,
                      metadata, title, description, date_text=resolved,
                      programme=current_days)
    if not event:
        return None
    event['date_evidence'] = original
    return {'status': 'detail_aligned',
            'reason': 'complete_discrete_cross_year_schedule',
            'detail_date_full': original,
            'resolved_date_full': resolved,
            'schedule_interpretation': 'explicit_days_current_year',
            'ignored_listing_occurrences': sorted(set(badges) - set(current_days)),
            'description_status': ('available' if event.get('description_excerpt')
                                   else 'unusable_excerpt'),
            'event': event}


def recover_month_range_exhibition(url, entry, html, *, today):
    """Expose month precision only when the exhibition names both months."""
    if entry.get('kind') != 'calendar' or entry.get('identity_conflict'):
        return None
    metadata, title, description = _detail_fields(html)
    row = plain(metadata.get('date_full'))
    prose = plain(description)
    if (not title or not metadata.get('event_city') or not description
            or 'mostre' not in plain(metadata.get('provider_categories'))
            or not re.fullmatch(rf'({MONTH})\s+{today.year}', row)
            or not prose.startswith('mostra fotografica')):
        return None
    range_match = MONTH_RANGE.search(prose)
    if not range_match or int(range_match[3]) != today.year:
        return None
    first_month, last_month = MONTHS[range_match[1]], MONTHS[range_match[2]]
    if (first_month != MONTHS[row.split()[0]] or last_month <= first_month):
        return None
    start = date(today.year, first_month, 1)
    end = (date(today.year + 1, 1, 1) if last_month == 12 else
           date(today.year, last_month + 1, 1)) - timedelta(days=1)
    if end < today:
        return None
    label = f'{range_match[1]}–{range_match[2]} {today.year}'
    resolved = f'{start.day} {range_match[1]} {today.year} - '
    resolved += f'{end.day} {range_match[2]} {today.year}'
    event = _promoted(url, entry, html, metadata, title, description,
                      date_text=resolved, schedule_kind='month_range',
                      date_label=label)
    if not event:
        return None
    event['date_evidence'] = label
    return {'status': 'detail_aligned',
            'reason': 'exhibition_month_range_in_official_description',
            'detail_date_full': metadata['date_full'],
            'resolved_date_full': resolved,
            'schedule_interpretation': 'month_range',
            'description_status': ('available' if event.get('description_excerpt')
                                   else 'unusable_excerpt'),
            'event': event}


def recover_calendar_anchored_weekends(url, entry, html, *, today):
    """Anchor a yearless weekend exhibition to this year's dated inventory.

    The current-year calendar alone is insufficient: the sitemap modification
    must precede the named opening by at most two weeks, and both weekdays
    must agree with the same calendar year.
    """
    if (entry.get('kind') != 'calendar' or entry.get('identity_conflict')
            or not entry.get('in_sitemap')
            or (entry.get('candidate') or {}).get('listing_occurrences')):
        return None
    metadata, title, description = _detail_fields(html)
    original = metadata.get('date_full') or ''
    row, prose = plain(original), plain(description)
    deadline = OPEN_WEEKENDS.fullmatch(row)
    beginning = re.search(
        rf'\bda\s+sabato\s+(\d{{1,2}})\s+({MONTH})\b', prose)
    repeating = (re.search(
        rf'\bvisitabile\s+ogni\s+venerdi,?\s+sabato\s+e\s+domenica'
        rf'\s+fino\s+al\s+{deadline[1]}\s+{deadline[2]}\b', prose)
        if deadline else None)
    if (not title or not metadata.get('event_city') or not description
            or 'mostre' not in plain(metadata.get('provider_categories'))
            or not deadline or not beginning or not repeating
            or re.search(r'\b20\d{2}\b', row + ' ' + prose)):
        return None
    start = _day(today.year, beginning[2], beginning[1])
    end = _day(today.year, deadline[2], deadline[1])
    try:
        modified = datetime.fromisoformat(
            entry['sitemap_lastmod'].replace('Z', '+00:00')).date()
    except (KeyError, AttributeError, ValueError):
        return None
    if (not start or not end or not start < end
            or start.weekday() != WEEKDAYS['sabato']
            or end.weekday() != WEEKDAYS['domenica']
            or (end - start).days > 120
            or modified.year != today.year
            or not 0 <= (start - modified).days <= 14):
        return None
    if end < today:
        return {'status': 'past_event',
                'reason': 'calendar_and_sitemap_anchored_period_past',
                'detail_date_full': original,
                'anchor_sitemap_lastmod': entry['sitemap_lastmod']}
    resolved = (f'{start.day} {beginning[2]} {today.year} - '
                f'{end.day} {deadline[2]} {today.year}')
    event = _promoted(url, entry, html, metadata, title, description,
                      date_text=resolved)
    if not event:
        return None
    event['date_evidence'] = (f'{original}; {beginning[0]}; '
                              f'sitemap {entry["sitemap_lastmod"]}')
    return {'status': 'detail_aligned',
            'reason': 'calendar_and_sitemap_anchored_weekend_exhibition',
            'detail_date_full': original,
            'resolved_date_full': resolved,
            'anchor_sitemap_lastmod': entry['sitemap_lastmod'],
            'description_status': ('available' if event.get('description_excerpt')
                                   else 'unusable_excerpt'),
            'event': event}


def recover_prior_edition_in_description(entry, html, *, today):
    """Exclude a sitemap-only exhibition with explicit old opening hours."""
    if entry.get('kind') != 'sitemap_only':
        return None
    metadata = engine.extract_turismofvg_detail_metadata(html)
    row = plain(metadata.get('date_full'))
    prose = plain(engine.extract_turismofvg_description(html))
    hours = re.search(
        rf'\borari\s+mostra\s+dal\s+\d{{1,2}}\s+(?:{MONTH})\s+'
        rf'all?[\s\']*\d{{1,2}}\s+(?:{MONTH})\s+(20\d{{2}})\b', prose)
    years = {int(year) for year in re.findall(r'\b20\d{2}\b', prose)}
    if (not metadata.get('event_city')
            or 'mostre' not in plain(metadata.get('provider_categories'))
            or re.search(r'\b20\d{2}\b', row)
            or not hours or not years or max(years) >= today.year):
        return None
    try:
        modified = datetime.fromisoformat(
            entry['sitemap_lastmod'].replace('Z', '+00:00')).date()
    except (KeyError, AttributeError, ValueError):
        return None
    edition_year = int(hours[1])
    if modified.year > edition_year or edition_year >= today.year:
        return None
    return {'status': 'past_event',
            'reason': 'prior_edition_opening_hours_in_official_description',
            'detail_date_full': metadata['date_full'],
            'programme_year': edition_year,
            'anchor_sitemap_lastmod': entry['sitemap_lastmod']}


def recover_current_year_detail(url, entry, html, *, today):
    if entry.get('kind') != 'calendar' or entry.get('identity_conflict'):
        return None
    candidate = entry.get('candidate') or {}
    metadata = engine.extract_turismofvg_detail_metadata(html)
    date_text = metadata.get('date_full') or ''
    title_match = re.search(r'<h1\b[^>]*>(.*?)</h1>', html, re.I | re.S)
    detail_title = engine.clean_event_text(title_match[1]) if title_match else None
    description = engine.extract_turismofvg_description(html) or ''
    if (not date_text or not detail_title or not metadata.get('event_city')
            or not description):
        return None
    row, prose = plain(date_text), plain(description)
    title = plain(detail_title)
    # These recoveries rely on the calendar's current-year inventory and an
    # explicit matching year in the detail row or in the full programme text.
    programme = _dated_programme(row, prose, title, year=today.year)
    if not programme:
        return None
    start, end, days, kind = programme
    if str(today.year) not in row and str(today.year) not in prose:
        return None
    if end < today or start.year != today.year or end.year != today.year:
        return None
    badges = candidate.get('listing_occurrences') or []
    if badges and (any(not start.isoformat() <= day <= end.isoformat()
                       for day in badges)
                   or days and not set(badges).issubset(
                       {day.isoformat() for day in days})):
        return None
    resolved_date = (f'{start.day} {list(MONTHS)[start.month - 1]} {start.year}'
                     if start == end else
                     f'{start.day} {list(MONTHS)[start.month - 1]} {start.year} - '
                     f'{end.day} {list(MONTHS)[end.month - 1]} {end.year}')
    metadata = {**metadata, 'date_full': resolved_date,
                'detail_title': detail_title}
    map_point = extract_turismofvg_map_point(html)
    if map_point:
        metadata['map_lat'], metadata['map_lon'] = map_point
    if days:
        metadata['programme_occurrences'] = [day.isoformat() for day in days]
    event = promote_candidate(candidate, metadata)
    if not event:
        return None
    excerpt = attributed_excerpt(
        description, source_name='TurismoFVG', source_url=url,
        title=detail_title)
    event.update(excerpt)
    event['date_evidence'] = (f'Riga data: {date_text}. '
                              f'Programma: {description[:500]}')
    return {'status': 'detail_aligned',
            'reason': 'programme_recovered_from_official_detail',
            'detail_date_full': date_text,
            'resolved_date_full': resolved_date,
            'schedule_interpretation': kind,
            'description_status': ('available' if event.get('description_excerpt')
                                   else 'unusable_excerpt'),
            'event': event}


def recover_end_only_exhibition(url, entry, html, *, today):
    """Keep a proven exhibition deadline without manufacturing its opening day."""
    if (entry.get('kind') != 'calendar' or entry.get('identity_conflict')
            or (entry.get('candidate') or {}).get('listing_occurrences')):
        return None
    metadata = engine.extract_turismofvg_detail_metadata(html)
    original = metadata.get('date_full') or ''
    deadline = END_ONLY.fullmatch(plain(original))
    if not deadline or not metadata.get('event_city'):
        return None
    end = _day(int(deadline[3]), deadline[2], deadline[1])
    if not end or end < today or end.year not in {today.year, today.year + 1}:
        return None
    description = engine.extract_turismofvg_description(html) or ''
    prose = plain(description)
    categories = plain(metadata.get('provider_categories'))
    if (not description or 'mostre' not in categories
            or not re.search(r'\borari\s+di\s+apertura\b', prose)
            or not re.search(rf'\b(?:{WEEKDAY})\b', prose)):
        return None
    title_match = re.search(r'<h1\b[^>]*>(.*?)</h1>', html, re.I | re.S)
    detail_title = engine.clean_event_text(title_match[1]) if title_match else None
    if not detail_title:
        return None
    # The temporary date is used only for the existing title and municipality
    # identity checks. It is removed before the event leaves this function.
    identity_metadata = {**metadata,
                         'date_full': f'{end.day} {deadline[2]} {end.year}',
                         'detail_title': detail_title}
    map_point = extract_turismofvg_map_point(html)
    if map_point:
        identity_metadata['map_lat'], identity_metadata['map_lon'] = map_point
    event = promote_candidate(entry['candidate'], identity_metadata)
    if not event:
        return None
    event.update({'start_date': None, 'end_date': end.isoformat(),
                  'schedule_kind': 'end_only',
                  'date_evidence': original})
    event.update(attributed_excerpt(
        description, source_name='TurismoFVG', source_url=url,
        title=detail_title))
    return {'status': 'detail_aligned',
            'reason': 'official_exhibition_deadline_with_opening_hours',
            'detail_date_full': original,
            'schedule_interpretation': 'end_only',
            'description_status': ('available' if event.get('description_excerpt')
                                   else 'unusable_excerpt'),
            'event': event}
