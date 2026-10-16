"""Evidence based exclusions from the current TurismoFVG event year.

These rules only decide that a detail cannot be shown in the current-year
future list. They never infer an event date or publish a card.
"""
from datetime import date
import re
import unicodedata

from . import engine
from .pilot_details import english_provider_date_range, german_provider_date_range
from .pilot_schedule import schedule_notice


MONTHS = {name: number for number, name in enumerate(
    'gennaio febbraio marzo aprile maggio giugno luglio agosto settembre ottobre novembre dicembre'.split(), 1)}
WEEKDAYS = {name: number for number, name in enumerate(
    'lunedi martedi mercoledi giovedi venerdi sabato domenica'.split())}
MONTH = '|'.join(MONTHS)
WEEKDAY = '|'.join(WEEKDAYS)
YEAR = re.compile(r'(?<!\d)20\d{2}(?!\d)')
WEEKDAY_DATE = re.compile(
    rf'^(?P<weekday>{WEEKDAY})\s+(?P<day>\d{{1,2}})\s+'
    rf'(?P<month>{MONTH})(?!\w)')
REPLACEMENT = re.compile(
    rf'\brinviat[oaie]\s+a\s+(?:(?:{WEEKDAY})\s+)?'
    rf'(?P<day>\d{{1,2}})\s+(?P<month>{MONTH})\s+'
    r'(?P<year>20\d{2})\b')
OPENING = re.compile(
    rf'\binaugurazione\s+(?P<weekday>{WEEKDAY})\s+'
    rf'(?P<day>\d{{1,2}})\s+(?P<month>{MONTH})\b')


def plain(value):
    return unicodedata.normalize('NFKD', str(value or '').lower()).encode(
        'ascii', 'ignore').decode('ascii')


def _event_day(year, month, day):
    try:
        return date(year, MONTHS[month], int(day))
    except ValueError:
        return None


def current_year_exclusion(entry, html, *, today):
    """Return an exclusion only when public detail and calendar agree."""
    metadata = engine.extract_turismofvg_detail_metadata(html)
    date_text = metadata.get('date_full') or ''
    description = engine.extract_turismofvg_description(html) or ''
    if not date_text or not metadata.get('event_city'):
        return None
    candidate = entry.get('candidate') or {}
    badges = candidate.get('listing_occurrences') or []
    has_future_badge = any(day >= today.isoformat() for day in badges)
    row = plain(date_text)
    prose = plain(description)
    years = {int(value) for value in YEAR.findall(date_text)}

    if (re.match(r'^\s*evento\s+annullat[oaie]\b', prose)
            and schedule_notice(description)):
        return {'status': 'excluded_current_year',
                'reason': 'explicit_cancellation', 'detail_date_full': date_text}
    if has_future_badge:
        return None

    replacement = REPLACEMENT.search(row)
    if replacement:
        new_day = _event_day(int(replacement['year']),
                             replacement['month'], replacement['day'])
        if (new_day and new_day.year > today.year
                and new_day.year in years
                and f"{new_day.day} {replacement['month']} {new_day.year}" in prose):
            return {'status': 'excluded_current_year',
                    'reason': 'confirmed_replacement_next_year',
                    'detail_date_full': date_text}

    if not years:
        weekday = WEEKDAY_DATE.search(row)
        if weekday:
            day = _event_day(today.year, weekday['month'], weekday['day'])
            if day and day.weekday() != WEEKDAYS[weekday['weekday']]:
                return {'status': 'excluded_current_year',
                        'reason': 'weekday_date_not_current_year',
                        'detail_date_full': date_text}

    start, end = engine.parse_event_date_range(date_text)
    if not start:
        start, end = english_provider_date_range(date_text)
    if not start:
        start, end = german_provider_date_range(date_text)
    if (start and end and end < today
            and start.year in years and end.year in years):
        return {'status': 'excluded_current_year',
                'reason': 'explicit_detail_dates_past',
                'detail_date_full': date_text}
    if years and max(years) < today.year:
        return {'status': 'excluded_current_year',
                'reason': 'explicit_prior_edition', 'detail_date_full': date_text}

    opening = OPENING.search(prose)
    if (re.match(r'^inaugurazione\b', plain(candidate.get('title')))
            and len(badges) == 1 and opening):
        day = _event_day(today.year, opening['month'], opening['day'])
        if (day and day < today and day.weekday() == WEEKDAYS[opening['weekday']]
                and badges == [day.isoformat()]):
            return {'status': 'excluded_current_year',
                    'reason': 'past_inauguration', 'detail_date_full': date_text}

    if (re.fullmatch(rf'(?:primavera|estate|autunno|inverno)\s+{today.year}', row)
            and not re.search(rf'\b\d{{1,2}}\s+(?:{MONTH})\b', prose)
            and not re.search(r'\bcalendario\b|\bprogramma\b', prose)):
        return {'status': 'excluded_current_year',
                'reason': 'season_without_published_programme',
                'detail_date_full': date_text}
    return None
