"""Bounded detail inspection for the pilot collector, never for HTTP readers.

Short excerpt reuse is opt-in per source after rights review. The caller owns
the network/time budget; failed inspection never invents a description.
"""
from datetime import date, datetime, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed
import re
import threading
import time
import requests
from . import engine
from .pilot_schedule import NOTICE_PATTERN, schedule_notice
from .pilot_excerpt import attributed_excerpt, remove_cross_page_duplicates

DETAIL_INSPECTION_VERSION = 11


def confirmed_rescheduled_single_date(description, date_text, listing_days):
    """Accept one announced replacement only when both source dates agree."""
    notices = list(NOTICE_PATTERN.finditer(description or ''))
    if len(notices) != 1 or not notices[0][0].lower().startswith('posticipat'):
        return False
    years = set(re.findall(r'\b20\d{2}\b', date_text or ''))
    if len(years) != 1:
        return False
    target = re.search(
        r'\bposticipat[oaie]\s+a\s+(?:luned[iì]|marted[iì]|mercoled[iì]|'
        r'gioved[iì]|venerd[iì]|sabato|domenica)\s+'
        r'(\d{1,2})\s+'
        r'(gennaio|febbraio|marzo|aprile|maggio|giugno|luglio|agosto|'
        r'settembre|ottobre|novembre|dicembre)\b',
        description or '', re.I)
    if not target:
        return False
    replacement, replacement_end = engine.parse_event_date_range(
        f'{target[1]} {target[2]} {next(iter(years))}')
    start, end = engine.parse_event_date_range(date_text or '')
    return bool(replacement and replacement == replacement_end == start == end
                and listing_days == [replacement.isoformat()])


def confirmed_rescheduled_range(description, date_text, listing_days):
    """Accept a postponed two-day period repeated in the labelled date row."""
    notices = list(NOTICE_PATTERN.finditer(description or ''))
    if len(notices) != 1 or not notices[0][0].lower().startswith('posticipat'):
        return False
    target = re.search(
        r'\bposticipat[oaie]\s+a\s+'
        r'(luned[iì]|marted[iì]|mercoled[iì]|gioved[iì]|venerd[iì]|sabato|domenica)\s+'
        r'(\d{1,2})\s+e\s+'
        r'(luned[iì]|marted[iì]|mercoled[iì]|gioved[iì]|venerd[iì]|sabato|domenica)\s+'
        r'(\d{1,2})\s+'
        r'(gennaio|febbraio|marzo|aprile|maggio|giugno|luglio|agosto|'
        r'settembre|ottobre|novembre|dicembre)\s+(20\d{2})\b',
        description or '', re.I)
    if not target:
        return False
    first, _ = engine.parse_event_date_range(f'{target[2]} {target[5]} {target[6]}')
    last, _ = engine.parse_event_date_range(f'{target[4]} {target[5]} {target[6]}')
    start, end = engine.parse_event_date_range(date_text or '')
    weekday_names = 'lunedi martedi mercoledi giovedi venerdi sabato domenica'.split()
    first_weekday = engine.normalize_for_search(target[1]).replace('ì', 'i')
    last_weekday = engine.normalize_for_search(target[3]).replace('ì', 'i')
    return bool(first and last and start == first and end == last
                and first < last and (last - first).days <= 2
                and first.weekday() == weekday_names.index(first_weekday)
                and last.weekday() == weekday_names.index(last_weekday)
                and all(start.isoformat() <= day <= end.isoformat()
                        for day in listing_days))


def unscheduled_bookable_experience(metadata, description, rows):
    """Identify long reservation-only offerings with no published schedule.

    A defined exhibition opening period is still an event. Uncertain cases
    stay in the ordinary review path.
    """
    date_text = metadata.get('date_full') or ''
    start, end = engine.parse_event_date_range(date_text)
    explicit_years = {int(year) for year in re.findall(r'\b20\d{2}\b', date_text)}
    calendar_placeholder = bool(re.search(r'\bCalendario\s*:\s*QUI\b',
                                          description or '', re.I))
    if (not start or not end or start.year not in explicit_years
            or end.year not in explicit_years or (end - start).days < 60
            or metadata.get('occurrences')
            or (re.search(r'\bCalendario\s*:', description or '', re.I)
                and not calendar_placeholder)):
        return False
    if engine.parse_turismofvg_discrete_occurrences(date_text):
        return False
    categories = engine.normalize_for_search(metadata.get('provider_categories') or '')
    prose = engine.normalize_for_search(description or '')
    detail_rows = engine.normalize_for_search(' '.join(rows or []))
    if re.search(r'\b(?:ogni\s+(?:lunedi|martedi|mercoledi|giovedi|venerdi|sabato|domenica|giorno|settimana|mese|weekend)|tutti\s+i\s+(?:giorni|lunedi|martedi|mercoledi|giovedi|venerdi|sabati)|tutte\s+le\s+domeniche)\b', prose):
        return False
    if re.search(r'\b\d{1,2}\s+(?:gennaio|febbraio|marzo|aprile|maggio|giugno|luglio|agosto|settembre|ottobre|novembre|dicembre)\b', prose):
        return False
    return bool(
        ('enogastronomia' in categories or 'strada del vino' in categories)
        and ('solo su prenotazione' in detail_rows
             or (calendar_placeholder and 'prenotazioni via whatsapp' in prose
                 and 'visite guidate' in prose))
        and re.search(r'\b(?:esperienz[ae]|percorso di degustazione|degustazione guidata)\b', prose)
    )


def reusable_detail(previous, *, allow_description_excerpt):
    try:
        age = (datetime.now(timezone.utc) - datetime.fromisoformat(previous['checked_at'])).total_seconds()
        return (0 <= age < 24 * 3600
                and previous.get('inspection_version') == DETAIL_INSPECTION_VERSION
                and 'notice' in previous and isinstance(previous.get('facts'), dict)
                and (not allow_description_excerpt
                     or previous.get('description_excerpt_checked') is True))
    except (KeyError, TypeError, ValueError):
        return False


def prefetch_details(urls, fetch, *, deadline, max_workers=3, batch_size=24):
    """Bounded detail I/O; result parsing remains ordered and deterministic."""
    fetched = {}
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        for offset in range(0, len(urls), batch_size):
            if time.monotonic() >= deadline - 20:
                break
            futures = {executor.submit(fetch, url): url for url in urls[offset:offset + batch_size]}
            for future in as_completed(futures):
                url = futures[future]
                try:
                    fetched[url] = future.result()
                except Exception as exc:
                    fetched[url] = exc
    return fetched


def calendar_occurrences(metadata, description):
    """Read a labelled calendar, not dates mentioned incidentally in prose."""
    years = set(re.findall(r'\b20\d{2}\b', metadata.get('date_full') or ''))
    if len(years) != 1:
        return []
    block = re.search(r'\bCalendario\s*:\s*(.*?)(?=\b(?:Orario|Ingresso|Informazioni)\s*:|$)',
                      description or '', re.I | re.S)
    if not block:
        return []
    text = block[1].strip()
    dated_text = text if re.search(r'\b20\d{2}\b', text) else f'{text} {next(iter(years))}'
    explicit_days = engine.parse_turismofvg_discrete_occurrences(dated_text)
    if explicit_days:
        start, end = engine.parse_event_date_range(metadata['date_full'])
        if start and end and all(start <= date.fromisoformat(day) <= end for day in explicit_days):
            return explicit_days
        return []
    months = 'gennaio febbraio marzo aprile maggio giugno luglio agosto settembre ottobre novembre dicembre'.split()
    pattern = re.compile(r'(\d{1,2}(?:\s*[-,e]\s*\d{1,2})*)\s+(' + '|'.join(months) + r')\b', re.I)
    matches = list(pattern.finditer(text))
    # Consume the whole calendar: an unparsed closing day must not disappear.
    if not matches or re.sub(r'[\s;,]+', '', pattern.sub('', text)):
        return []
    try:
        days = sorted({date(int(next(iter(years))), months.index(m[2].lower()) + 1, int(d))
                       for m in matches for d in re.findall(r'\d{1,2}', m[1])})
        start, end = engine.parse_event_date_range(metadata['date_full'])
        if not start or not end or any(not start <= d <= end for d in days):
            return []
        return [d.isoformat() for d in days]
    except ValueError:
        return []


def corroborated_programme_occurrences(metadata, description, listing_days):
    """Repair a wrong structured end only when programme and badges agree exactly."""
    date_text = metadata.get('date_full') or ''
    start, end = engine.parse_event_date_range(date_text)
    years = set(re.findall(r'\b20\d{2}\b', date_text))
    if not start or not end or len(years) != 1 or len(set(listing_days)) < 2:
        return []
    try:
        badges = {date.fromisoformat(day) for day in listing_days}
    except (TypeError, ValueError):
        return []
    if (any(day.year != start.year for day in badges)
            or all(start <= day <= end for day in badges)):
        return []
    prose = engine.normalize_for_search(description or '')
    if any(year != str(start.year) for year in re.findall(r'\b20\d{2}\b', prose)):
        return []
    months = 'gennaio febbraio marzo aprile maggio giugno luglio agosto settembre ottobre novembre dicembre'.split()
    pattern = re.compile(r'\b(\d{1,2})\s+(' + '|'.join(months)
                         + r')(?:\s+(20\d{2}))?\b')
    days = set()
    try:
        for match in pattern.finditer(prose):
            days.add(date(int(match[3] or start.year),
                          months.index(match[2]) + 1, int(match[1])))
    except ValueError:
        return []
    return [day.isoformat() for day in sorted(days)] if days == badges else []


def english_provider_date_range(value):
    """Parse TurismoFVG's occasional English-localized detail date row."""
    months = {
        'january': 1, 'february': 2, 'march': 3, 'april': 4,
        'may': 5, 'june': 6, 'july': 7, 'august': 8,
        'september': 9, 'october': 10, 'november': 11, 'december': 12,
    }
    text = engine.normalize_for_search(value)
    matches = re.finditer(
        r'\b(' + '|'.join(months) + r')\s+(\d{1,2})(?:st|nd|rd|th)?(?:,\s*|\s+)(20\d{2})\b',
        text,
        re.I,
    )
    parsed = []
    for match in matches:
        try:
            parsed.append(date(int(match.group(3)), months[match.group(1).lower()], int(match.group(2))))
        except ValueError:
            return None, None
    weekdays = 'monday tuesday wednesday thursday friday saturday sunday'.split()
    day_first = re.finditer(
        r'\b(?:(?P<weekday>' + '|'.join(weekdays) + r')\s*,?\s+)?'
        r'(?P<day>\d{1,2})(?:st|nd|rd|th)?\s+'
        r'(?P<month>' + '|'.join(months) + r')\s+'
        r'(?P<year>20\d{2})\b', text, re.I)
    for match in day_first:
        try:
            day = date(int(match['year']), months[match['month'].lower()],
                       int(match['day']))
        except ValueError:
            return None, None
        if match['weekday'] and day.weekday() != weekdays.index(
                match['weekday'].lower()):
            return None, None
        parsed.append(day)
    return (min(parsed), max(parsed)) if parsed else (None, None)


def german_provider_date_range(value):
    """Read a fully labelled German detail interval and verify weekdays."""
    months = dict(zip('januar februar märz april mai juni juli august september oktober november dezember'.split(),
                      range(1, 13)))
    weekdays = 'montag dienstag mittwoch donnerstag freitag samstag sonntag'.split()
    pattern = re.compile(
        r'(?:(?P<weekday>' + '|'.join(weekdays) + r'),?\s+)?'
        r'(?P<day>\d{1,2})\.\s*(?P<month>' + '|'.join(months) + r')\s+'
        r'(?P<year>20\d{2})', re.I)
    parts = re.split(r'\s+-\s+', engine.normalize_for_search(value))
    if not 1 <= len(parts) <= 2:
        return None, None
    parsed = []
    for part in parts:
        match = pattern.fullmatch(part)
        if not match:
            return None, None
        try:
            day = date(int(match['year']), months[match['month'].lower()],
                       int(match['day']))
        except ValueError:
            return None, None
        if match['weekday'] and day.weekday() != weekdays.index(match['weekday'].lower()):
            return None, None
        parsed.append(day)
    if len(parsed) == 2 and parsed[1] < parsed[0]:
        return None, None
    return parsed[0], parsed[-1]


def listing_days_match_schedule(candidate, start, end, occurrences):
    """Check every yearless result badge against the dated detail schedule."""
    active_days = {date.fromisoformat(day) for day in occurrences} if occurrences else None
    for hint in candidate.get('listing_day_months') or []:
        possible = []
        for year in range(start.year, end.year + 1):
            day, _ = engine.parse_event_date_range(f'{hint} {year}')
            if day and start <= day <= end:
                possible.append(day)
        if not possible or (active_days is not None and not any(day in active_days for day in possible)):
            return False
    return True


def promote_candidate(candidate, metadata):
    """Reuse legacy date parsing; retain intervals without inventing replicas."""
    date_text = metadata.get('date_full') or ''
    date_occurrences = engine.parse_turismofvg_discrete_occurrences(date_text)
    listing_occurrences = candidate.get('listing_occurrences') or []
    try:
        listing_occurrences = sorted({date.fromisoformat(day).isoformat()
                                      for day in listing_occurrences})
    except (TypeError, ValueError):
        return None
    programme_occurrences = metadata.get('programme_occurrences') or []
    # Calendar badges corroborate a labelled period; they are not its
    # replacement schedule. Use them as dates only when the detail has no
    # parseable bounds (for example a yearless recurrence).
    labelled_start, _ = engine.parse_event_date_range(date_text)
    if not labelled_start:
        labelled_start, _ = english_provider_date_range(date_text)
    if not labelled_start:
        labelled_start, _ = german_provider_date_range(date_text)
    occurrences = (programme_occurrences or metadata.get('occurrences')
                   or date_occurrences or
                   (listing_occurrences if not labelled_start else []))
    if not re.search(r'\b20\d{2}\b', date_text) and not listing_occurrences:
        return None
    # A list of separate days must never be published as a continuous interval
    # merely because only its last group was parsed.
    if re.search(r'\b\d{1,2}\s*[,/]\s*\d{1,2}\b', date_text) and not occurrences:
        return None
    # A recurrence rule is not a start date; the legacy range parser alone
    # cannot expand "every Monday until ..." faithfully.
    if not occurrences and re.search(r'\b(?:ogni|fino|escluso|esclusi)\b', date_text, re.I):
        return None
    detail_title = engine.normalize_for_search(metadata.get('detail_title'))
    listing_title = candidate.get('title') or ''
    normalized_title = engine.normalize_for_search(listing_title)
    page_title = engine.normalize_for_search(metadata.get('page_title'))
    truncated = re.search(r'(?:\.{3}|…)\s*$', listing_title)
    prefix = engine.normalize_for_search(listing_title[:truncated.start()]) if truncated else ''
    # The regional listing occasionally contains a replacement character in
    # its final word. A long matching prefix is still usable when the damaged
    # character is at the end; the detail page must independently verify town
    # and schedule below before we promote the record.
    damaged = re.search('\ufffd', listing_title)
    if not prefix and damaged and not listing_title[damaged.end():].strip(' \t\r\n\xa0"\'”’'):
        prefix = engine.normalize_for_search(listing_title[:damaged.start()])
    legacy_title = engine.normalize_for_search(engine.clean_event_title(metadata.get('detail_title') or ''))
    start, end = engine.parse_event_date_range(date_text)
    english_date = False
    if not start:
        start, end = english_provider_date_range(date_text)
        english_date = start is not None
    if not start:
        start, end = german_provider_date_range(date_text)
    if programme_occurrences:
        start, end = (date.fromisoformat(programme_occurrences[0]),
                      date.fromisoformat(programme_occurrences[-1]))
    elif date_occurrences:
        start, end = (date.fromisoformat(date_occurrences[0]),
                      date.fromisoformat(date_occurrences[-1]))
    if not start and listing_occurrences:
        start, end = (date.fromisoformat(listing_occurrences[0]),
                      date.fromisoformat(listing_occurrences[-1]))
    if not start or (end and end < start):
        return None
    if listing_occurrences and re.search(r'\b20\d{2}\b', date_text) and not programme_occurrences:
        if any(not start <= date.fromisoformat(day) <= (end or start)
               for day in listing_occurrences):
            return None
    if date_occurrences and not programme_occurrences and (date_occurrences[0] != start.isoformat()
                             or date_occurrences[-1] != (end or start).isoformat()):
        return None
    if (listing_occurrences and occurrences
            and not set(listing_occurrences).issubset(set(occurrences))):
        return None
    if not listing_days_match_schedule(candidate, start, end or start, occurrences):
        return None
    series = engine.normalize_for_search(listing_title.split(' - ', 1)[0])
    title_matches = (detail_title == normalized_title or legacy_title == normalized_title
                     or page_title == normalized_title
                     or (len(prefix) >= 30 and detail_title.startswith(prefix))
                     or (candidate.get('discovery_kind') == 'filtered_calendar'
                         and len(series) >= 13 and detail_title.startswith(series)))
    if not title_matches:
        hint_start, _ = engine.parse_event_date_range(candidate.get('date_hint') or '')
        translated_highlight = (english_date and candidate.get('discovery_kind') == 'highlight'
                                and hint_start == start)
        if not translated_highlight:
            return None
    city = metadata.get('event_city')
    from .pilot_regional_location import (resolve_turismofvg_municipality,
                                          resolve_turismofvg_municipalities,
                                          resolve_turismofvg_locality,
                                          source_map_is_single_venue)
    town = resolve_turismofvg_municipality(city)
    places = resolve_turismofvg_municipalities(city) if not town else None
    locality = resolve_turismofvg_locality(city) if not town and not places else None
    map_point = ((metadata['map_lat'], metadata['map_lon'])
                 if metadata.get('map_lat') is not None and metadata.get('map_lon') is not None
                 and city and (',' not in city or source_map_is_single_venue(
                     city, metadata.get('venue'))) else None)
    if ((not town and not map_point and not places and not locality)
            or (candidate.get('event_city')
                and engine.normalize_for_search(candidate['event_city'])
                != engine.normalize_for_search(city))):
        return None
    lat, lon = ((town.latitude, town.longitude) if town else
                map_point if map_point else locality[:2] if locality else (None, None))
    return {**candidate, 'title': (candidate.get('title') if page_title == normalized_title
                                  else metadata.get('detail_title') or candidate.get('title')),
            'start_date': occurrences[0] if occurrences else start.isoformat(),
            'end_date': occurrences[-1] if occurrences else (end or start).isoformat(),
            'schedule_kind': 'occurrences' if occurrences else ('interval' if end and end != start else 'single'),
            **({'occurrences': occurrences} if occurrences else {}),
            **{key: metadata[key] for key in ('venue', 'place', 'address', 'time', 'provider_categories', 'provider_category_list', 'official_site', 'audience') if metadata.get(key)},
            'date_evidence_kind': 'event_schedule',
            'date_evidence': (', '.join(occurrences) if occurrences
                              else date_text),
            **({'verified_programme_occurrences': programme_occurrences}
               if programme_occurrences else {}),
            **({'confirmed_reschedule': True}
               if metadata.get('confirmed_reschedule') else {}),
            'event_city': city, 'lat': lat, 'lon': lon,
            **({'listed_municipalities': places} if places else {}),
            'location_confidence': ('municipality' if town else
                                    'source_map' if map_point else
                                    'multiple_municipalities' if places else
                                    'source_locality'),
            **({'location_source_url': locality[2]} if locality and not map_point else {}),
            'is_real': True}


def enrich_details(events, *, fetch_html, max_urls=10, allow_description_excerpt=False,
                   allow_unparsed_calendar_for_period=False,
                   allow_dated_experience_exclusion=False,
                   allow_confirmed_reschedule=False,
                   allow_programme_reconciliation=False,
                   previous_cache=None, deadline=None):
    if max_urls is None and deadline is None:
        raise ValueError("deadline required without URL budget")
    if max_urls is not None and not 0 <= max_urls <= 2048:
        raise ValueError("invalid detail budget")
    if max_urls is not None and max_urls > 100 and deadline is None:
        raise ValueError("deadline required for large detail budget")
    cache, result, review, pending, excluded = {}, [], [], [], {}
    checked_at = datetime.now(timezone.utc).isoformat()
    saved = {}
    requested = 0
    for original in events:
        event = dict(original)
        candidate = bool(event.get('discovery_kind')) and not event.get('start_date')
        url = event.get("url") or ""
        if event.get("source") != "TurismoFVG" or not engine.is_trusted_turismofvg_event_url(url):
            (pending if candidate else result).append(event)
            continue
        previous = (previous_cache or {}).get(url)
        if previous:
            saved[url] = dict(previous)
        if url not in cache and previous and reusable_detail(
                previous, allow_description_excerpt=allow_description_excerpt):
            cache[url] = (previous.get('facts', {}), previous.get("description_excerpt", ""), previous["notice"])
            saved[url] = previous
        if url not in cache and (max_urls is None or requested < max_urls) and (deadline is None or time.monotonic() < deadline):
            requested += 1
            try:
                html = fetch_html(url)
                metadata = engine.extract_turismofvg_detail_metadata(html)
                from .pilot_regional_location import extract_turismofvg_map_point
                map_point = extract_turismofvg_map_point(html)
                if map_point:
                    metadata['map_lat'], metadata['map_lon'] = map_point
                description = engine.extract_turismofvg_description(html) or ""
                notice = schedule_notice(description)
                if (notice and allow_confirmed_reschedule
                        and (confirmed_rescheduled_single_date(
                            description, metadata.get('date_full'),
                            event.get('listing_occurrences') or [])
                             or confirmed_rescheduled_range(
                                 description, metadata.get('date_full'),
                                 event.get('listing_occurrences') or []))):
                    notice = False
                    metadata['confirmed_reschedule'] = True
                title = re.search(r'<h1\b[^>]*>(.*?)</h1>', html, re.I | re.S)
                metadata['detail_title'] = engine.clean_event_text(title[1]) if title else None
                page_title = re.search(r'<title\b[^>]*>(.*?)</title>', html, re.I | re.S)
                metadata['page_title'] = (engine.clean_event_text(page_title[1])
                                          if page_title else None)
                # Some genuine details have a labelled date and town but no
                # description. Require those structured identity fields instead.
                if not notice and not all(metadata.get(key) for key in ('date_full', 'event_city', 'detail_title')):
                    raise ValueError("unrecognized_event_detail")
                occurrences = calendar_occurrences(metadata, description)
                if occurrences:
                    metadata['occurrences'] = occurrences
                elif (re.search(r'\bCalendario\s*:', description, re.I)
                      and not (allow_unparsed_calendar_for_period
                               and candidate and event.get('listing_occurrences'))):
                    raise ValueError('unparsed_explicit_calendar')
                if allow_programme_reconciliation and candidate:
                    programme = corroborated_programme_occurrences(
                        metadata, description, event.get('listing_occurrences') or [])
                    if programme:
                        metadata['programme_occurrences'] = programme
                if unscheduled_bookable_experience(
                        metadata, description, engine.extract_turismofvg_detail_rows(html)):
                    metadata['scope_exclusion'] = 'reservation_only_experience'
                excerpt_fields = attributed_excerpt(
                    description,
                    source_name="TurismoFVG",
                    source_url=url,
                    title=metadata.get("detail_title") or event.get("title"),
                    checked_at=checked_at,
                ) if allow_description_excerpt else {}
                excerpt = excerpt_fields.get("description_excerpt", "")
                # Persist only the bounded excerpt and inspection verdict, not full prose.
                saved[url] = {"checked_at": checked_at, 'last_attempt_at': checked_at, "notice": bool(notice), "inspection_version": DETAIL_INSPECTION_VERSION,
                              "description_excerpt_checked": bool(allow_description_excerpt),
                              **excerpt_fields,
                              'facts': {key: metadata[key] for key in ('date_full', 'event_city', 'detail_title', 'page_title', 'venue', 'place', 'address', 'occurrences', 'programme_occurrences', 'confirmed_reschedule', 'time', 'provider_categories', 'provider_category_list', 'official_site', 'audience', 'scope_exclusion', 'map_lat', 'map_lon') if metadata.get(key)}}
                cache[url] = (metadata, excerpt, bool(notice))
            except Exception:
                cache[url] = None
                # Rotate failed URLs too; otherwise the same first failures
                # can consume all twenty requests on every run indefinitely.
                saved[url] = {**(previous or {}), 'last_attempt_at': checked_at}
        detail = cache.get(url)
        event["detail_status"] = ("inspected" if cache.get(url) is not None else "unavailable") if url in cache else "pending"
        if detail is None:
            if previous and previous.get("notice"):
                review.append({**event, "review_reason": "schedule_change_not_rechecked"})
                continue
            (pending if candidate else result).append(event)
            continue
        metadata, description, notice = detail
        if notice:
            review.append({**event, "review_reason": "possible_schedule_change", "detail_checked_at": saved[url]["checked_at"]})
            continue
        if metadata.get('scope_exclusion') == 'reservation_only_experience':
            if event.get('listing_occurrences') and not allow_dated_experience_exclusion:
                review.append({**event, 'review_reason': 'bookable_experience_with_dated_listing',
                               'detail_checked_at': saved[url]['checked_at']})
                continue
            excluded[url] = {'url': url, 'reason': metadata['scope_exclusion'],
                             'detail_checked_at': saved[url]['checked_at']}
            continue
        detail_identity_verified = False
        if candidate:
            promoted = promote_candidate(event, metadata)
            if promoted is None:
                pending.append({**event, 'review_reason': 'detail_identity_or_schedule_requires_review'})
                continue
            event = promoted
            detail_identity_verified = True
        else:
            # A listing record also needs the explicit time and venue. Apply
            # them only when detail identity AND schedule match that record.
            promoted = promote_candidate(event, metadata)
            detail_identity_verified = promoted is not None
            if not promoted or (event.get('start_date'), event.get('end_date') or event.get('start_date')) != (promoted['start_date'], promoted['end_date']):
                review.append({**event, 'review_reason': 'listing_detail_identity_or_schedule_conflict'})
                continue
            if promoted:
                conflicts = [key for key in ('time', 'venue', 'address')
                             if event.get(key) and promoted.get(key)
                             and engine.normalize_for_search(event[key]) != engine.normalize_for_search(promoted[key])]
                if conflicts:
                    review.append({**event, 'review_reason': 'listing_detail_conflict', 'conflicting_fields': conflicts})
                    continue
                event.update({key: promoted[key] for key in ('title', 'time', 'venue', 'place', 'address', 'provider_categories', 'provider_category_list', 'official_site', 'audience', 'occurrences') if promoted.get(key)})
        event.update(detail_status="inspected", detail_checked_at=saved[url]["checked_at"], detail_source_url=url)
        # Do not overwrite dates, coordinates or venue based on an uncorrelated
        # festival detail page: it may describe several separate performances.
        if description and allow_description_excerpt and detail_identity_verified:
            event.update({key: saved[url][key] for key in (
                "description_excerpt", "description_source_name",
                "description_source_url", "description_checked_at",
            ) if saved[url].get(key)})
        result.append(event)
    return {"events": result, "review_required": review, "detail_urls_checked": requested, "detail_cache": saved,
            'detail_candidates': pending, 'scope_excluded': list(excluded.values())}


def collect_regional_with_details(previous_cache=None):
    from .pilot_regional import collect_regional
    # Includes listing time: preserve the existing 360-second source budget.
    deadline = time.monotonic() + 335
    # The catalog's pagination changes when its session cookies are reused.
    # Keep listing requests independent; detail workers have separate sessions.
    batch = collect_regional()
    # Inspect never-checked entries first, then the oldest cached URLs.
    existing_urls = {e.get('url') for e in batch['events']}
    candidates = [e for e in batch.get('detail_candidates', []) if e.get('url') not in existing_urls]
    def priority(event):
        previous = (previous_cache or {}).get(event.get('url'), {})
        return (previous.get('last_attempt_at') or previous.get('checked_at', ''),
                0 if event.get('discovery_kind') else 1)
    events = sorted(batch["events"] + candidates, key=priority)
    urls = list(dict.fromkeys(event.get('url') for event in events
                              if engine.is_trusted_turismofvg_event_url(event.get('url'))
                              and not reusable_detail((previous_cache or {}).get(event.get('url'), {}),
                                                      allow_description_excerpt=True)))
    local = threading.local()
    sessions, sessions_lock = [], threading.Lock()
    def fetch(url):
        if not hasattr(local, 'session'):
            local.session = requests.Session()
            with sessions_lock:
                sessions.append(local.session)
        with local.session.get(url, timeout=(3, 5), allow_redirects=False, stream=True,
                               headers={"User-Agent": "Meteo-Friul-Pilot-Catalog/1.0"}) as response:
            response.raise_for_status()
            if response.status_code != 200:
                raise ValueError("unexpected detail response")
            chunks, size = [], 0
            for chunk in response.iter_content(65536):
                size += len(chunk)
                if size > 4 * 1024 * 1024 or time.monotonic() >= deadline:
                    raise ValueError("detail budget exceeded")
                chunks.append(chunk)
            return b"".join(chunks).decode("utf-8", errors="replace")
    try:
        prefetched = prefetch_details(urls, fetch, deadline=deadline)
    finally:
        for session in sessions:
            session.close()
    def fetched_html(url):
        value = prefetched[url]
        if isinstance(value, Exception):
            raise value
        return value
    details = enrich_details(events, fetch_html=fetched_html, max_urls=len(prefetched),
                             allow_description_excerpt=True,
                             previous_cache=previous_cache, deadline=deadline)
    details['events'] = remove_cross_page_duplicates(details.get('events', []))
    verified_urls = {event.get('url') for event in details['events']
                     if event.get('detail_status') == 'inspected'}
    excluded_urls = {item['url'] for item in details.get('scope_excluded', [])}
    unresolved_listing = [item for item in batch.get('review_required', [])
                          if item.get('url') not in verified_urls | excluded_urls]
    unverified_events = [event.get('url') for event in details['events']
                         if event.get('detail_status') != 'inspected']
    unresolved_items = (details.get('detail_candidates', [])
                        + details.get('review_required', []) + unresolved_listing)
    unresolved_urls = {item.get('url') for item in unresolved_items if item.get('url')}
    unresolved_urls.update(url for url in unverified_events if url)
    unresolved_count = len(unresolved_urls) + sum(not item.get('url') for item in unresolved_items)
    verification = {
        'declared_results': batch.get('declared_results'),
        'cards_seen': batch.get('cards_seen'),
        'pages': batch.get('pages'),
        'verified_events': len(details['events']) - len(unverified_events),
        'unresolved_count': unresolved_count,
        'pending_detail_count': len(details.get('detail_candidates', [])),
        'review_issue_count': len(details.get('review_required', [])) + len(unresolved_listing),
        'scope_excluded_count': len(excluded_urls),
    }
    return {**batch, **details,
            'status': 'ok' if unresolved_count == 0 else 'error',
            'coverage': ('regional-listing-and-details-verified' if unresolved_count == 0
                         else 'regional-listing-or-details-incomplete'),
            'verification': verification,
            'error_type': 'incomplete_source' if unresolved_count else None,
            'review_required': unresolved_listing + details.get('review_required', [])
                + [{'url': url, 'review_reason': 'detail_not_inspected'} for url in unverified_events]}
