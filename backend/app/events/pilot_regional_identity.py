"""Narrow, corroborated repairs for regional calendar/detail identity."""
from datetime import date
import re

from . import engine

MONTHS = 'gennaio febbraio marzo aprile maggio giugno luglio agosto settembre ottobre novembre dicembre'.split()


def month_label(value):
    match = re.fullmatch(r'(' + '|'.join(MONTHS) + r')\s+(20\d{2})',
                         engine.normalize_for_search(value).strip())
    return (int(match[2]), MONTHS.index(match[1]) + 1) if match else None


def single_month_calendar_day(candidate, date_text, event):
    """Preserve one exact day, never expand a month label into daily openings."""
    label = month_label(date_text)
    badges = candidate.get('listing_occurrences') or []
    if (not label or len(badges) != 1
            or candidate.get('discovery_kind') != 'filtered_calendar'
            or not engine.is_trusted_turismofvg_event_url(candidate.get('url') or '')
            or not candidate.get('event_city')
            or engine.normalize_for_search(candidate['event_city']) !=
               engine.normalize_for_search(event.get('event_city'))):
        return None
    try:
        day = date.fromisoformat(badges[0])
    except (TypeError, ValueError):
        return None
    if ((day.year, day.month) != label or event.get('occurrences') != badges
            or event.get('start_date') != badges[0] or event.get('end_date') != badges[0]):
        return None
    return day


def month_calendar_prose_conflict(date_text, description, listing_days):
    """An exact badge cannot override contradictory dates in a month-only detail."""
    label = month_label(date_text)
    if not label or len(listing_days) != 1:
        return False
    try:
        badge = date.fromisoformat(listing_days[0])
    except (TypeError, ValueError):
        return True
    pattern = r'\b(\d{1,2})\s+(' + '|'.join(MONTHS) + r')(?:\s+(20\d{2}))?\b'
    for match in re.finditer(pattern, engine.normalize_for_search(description)):
        year = int(match[3]) if match[3] else label[0]
        if year != label[0]:
            continue
        try:
            mentioned = date(year, MONTHS.index(match[2]) + 1, int(match[1]))
        except ValueError:
            return True
        if mentioned != badge:
            return True
    return False


def _tokens(value):
    return re.findall(r"[^\W_]+", engine.normalize_for_search(value))


def _one_transposed_word(left, right):
    """Only two adjacent letters in one long word; no substitutions or numbers."""
    if len(left) != len(right) or len(left) < 2:
        return False
    pairs = [(a, b) for a, b in zip(left, right) if a != b]
    if len(pairs) != 1:
        return False
    a, b = pairs[0]
    if len(a) != len(b) or len(a) < 8 or not a.isalpha() or not b.isalpha():
        return False
    changed = [i for i, (x, y) in enumerate(zip(a, b)) if x != y]
    return (len(changed) == 2 and changed[1] == changed[0] + 1
            and a[changed[0]:changed[1] + 1] == b[changed[0]:changed[1] + 1][::-1])


def corroborated_title_repair(candidate, metadata, start, end):
    """Repair spelling/venue decoration only with exact calendar bounds and town."""
    if (candidate.get('discovery_kind') != 'filtered_calendar'
            or not engine.is_trusted_turismofvg_event_url(candidate.get('url') or '')
            or not candidate.get('event_city')
            or engine.normalize_for_search(candidate['event_city']) !=
               engine.normalize_for_search(metadata.get('event_city'))
            or metadata.get('programme_occurrences')):
        return None
    # The date must be explicit in the detail, not inferred from calendar badges.
    detail_start, detail_end = engine.parse_event_date_range(metadata.get('date_full') or '')
    if (not re.search(r'\b20\d{2}\b', metadata.get('date_full') or '')
            or not detail_start or (detail_start, detail_end or detail_start) != (start, end)):
        return None
    try:
        days = sorted({date.fromisoformat(day) for day in candidate.get('listing_occurrences') or []})
    except (TypeError, ValueError):
        return None
    if not days or (days[0], days[-1]) != (start, end):
        return None
    listing, detail = candidate.get('title') or '', metadata.get('detail_title') or ''
    if _one_transposed_word(_tokens(listing), _tokens(detail)):
        return 'single_adjacent_transposition'
    # A colon may introduce the event after a venue, not an arbitrary series.
    prefix, separator, suffix = listing.partition(':')
    venue = re.split(r'\s+(?:in|a|presso)\s+(?:piazza|via|viale|piazzale|largo|corso)\b',
                     metadata.get('venue') or '', maxsplit=1, flags=re.I)[0]
    if (separator and len(_tokens(prefix)) >= 2
            and _tokens(prefix) == _tokens(venue)
            and _tokens(suffix) == _tokens(detail) and len(''.join(_tokens(detail))) >= 5):
        return 'verified_venue_prefix'
    return None
