"""Pilot-only Azalea reader for the complete upcoming archive and its details."""
from datetime import date, datetime
from html import unescape
import json
from pathlib import Path
import re
from urllib.parse import urlsplit
from xml.etree import ElementTree
import requests

from . import engine
from .pilot_excerpt import attributed_excerpt, remove_cross_page_duplicates
from .pilot_source_policy import validate_candidate
from .pilot_schedule import schedule_notice


ARCHIVE = 'https://www.azalea.it/eventi/'
SITEMAP = 'https://www.azalea.it/sitemap_index.xml'
BASELINE = json.loads(Path(__file__).with_name('pilot_azalea_sitemap_baseline.json')
                      .read_text(encoding='utf-8'))['unlisted_lastmod']
EVENT_PATH = re.compile(r'/eventi/[^/]+/')
CARD = re.compile(r'<article\b[^>]*class="[^"]*\bevent-archive-card\b[^>]*>(.*?)</article>',
                  re.I | re.S)
MONTHS = ('', 'gennaio', 'febbraio', 'marzo', 'aprile', 'maggio', 'giugno',
          'luglio', 'agosto', 'settembre', 'ottobre', 'novembre', 'dicembre')


class ScheduleReviewRequired(ValueError):
    pass


def clean(value):
    return ' '.join(unescape(re.sub(r'<[^>]+>', ' ', value)).split())


def field(html, pattern, *, required=True):
    match = re.search(pattern, html, re.I | re.S)
    if not match:
        if required:
            raise ValueError('unrecognized Azalea event fields')
        return ''
    return clean(match.group(1))


def trusted_event_url(url):
    parsed = urlsplit(str(url or ''))
    return (parsed.scheme == 'https' and parsed.hostname == 'www.azalea.it'
            and EVENT_PATH.fullmatch(parsed.path) is not None
            and not parsed.query and not parsed.fragment)


def archive_cards(html):
    """Read the visible archive cards, excluding ticker and recommendations."""
    chunks = CARD.findall(html)
    if not chunks or len(chunks) > 100:
        raise ValueError('unrecognized Azalea archive cards')
    records = []
    for chunk in chunks:
        anchor = re.search(r'<a\b(?=[^>]*\bclass="[^"]*\bcard-title-link\b)[^>]*>.*?</a>',
                           chunk, re.I | re.S)
        href = re.search(r'\bhref="([^"]+)"', anchor.group(0)) if anchor else None
        if not href or not trusted_event_url(href.group(1)):
            raise ValueError('invalid Azalea archive card URL')
        title = clean(re.sub(r'^<a\b[^>]*>|</a>$', '', anchor.group(0), flags=re.I | re.S))
        date_text = field(chunk, r'<span\b[^>]*class="[^"]*\bevent-archive-date\b[^"]*"[^>]*>(.*?)</span>')
        city = field(chunk, r'<span\b[^>]*class="[^"]*\bevent-archive-city\b[^"]*"[^>]*>(.*?)</span>')
        if not title or not city or not re.fullmatch(r'\d{2}\.\d{2}\.\d{4}', date_text):
            raise ValueError('incomplete Azalea archive card')
        day = datetime.strptime(date_text, '%d.%m.%Y').date().isoformat()
        records.append({'url': href.group(1), 'title': title,
                        'date': day, 'city': city})
    if len({record['url'] for record in records}) != len(records):
        raise ValueError('duplicate Azalea archive card')
    return records


def archive_next(html, page):
    match = re.search(r'<link\b(?=[^>]*\brel="next")[^>]*\bhref="([^"]+)"',
                      html, re.I | re.S)
    if not match:
        return None
    expected = f'https://www.azalea.it/eventi/page/{page + 1}/'
    if unescape(match.group(1)) != expected:
        raise ValueError('unexpected Azalea archive pagination')
    return expected


def sitemap_events(xml):
    """Read Azalea's event URL index; the audited historical set is a delta baseline."""
    root = ElementTree.fromstring(xml)
    if root.tag != '{http://www.sitemaps.org/schemas/sitemap/0.9}urlset':
        raise ValueError('unexpected Azalea sitemap format')
    entries = {}
    for node in root.findall('{*}url'):
        url = node.findtext('{*}loc')
        if not trusted_event_url(url):
            continue
        lastmod = node.findtext('{*}lastmod')
        changed_at = datetime.fromisoformat(lastmod or '')
        if changed_at.tzinfo is None or url in entries:
            raise ValueError('invalid Azalea sitemap event entry')
        entries[url] = lastmod
    if not 1 <= len(entries) <= 1000:
        raise ValueError('invalid Azalea sitemap event count')
    return entries


def confirmed_postponement(title, description_html, *, day, city, venue):
    """Accept a new date only when Azalea links it to the prior one explicitly."""
    year = day.year
    description = clean(description_html)
    if (not re.search(rf'\brinviat[oaie]\s+al\s+{year}\b', title, re.I)
            or not re.search(rf'\bposticipat[oaie]\s+nel\s+{year}\b', description, re.I)
            or not re.search(r'nuovo calendario delle date', description, re.I)
            or re.search(r'\b(?:annullat[oaie]|cancellat[oaie])\b', description, re.I)):
        return ''
    day_pattern = rf'\b0?{day.day}(?:°|º)?\s+{MONTHS[day.month]}\s+{year}\b'
    venue_name = clean(venue.split(',')[0]).casefold()
    for paragraph in re.findall(r'<p\b[^>]*>(.*?)</p>', description_html, re.I | re.S):
        text = clean(paragraph)
        old_years = [int(value) for value in re.findall(
            r'posticipo\s+del\s+.{0,40}?\b(20\d{2})\b', text, re.I)]
        if (re.search(day_pattern, text, re.I)
                and city.casefold() in text.casefold()
                and venue_name and venue_name in text.casefold()
                and old_years and all(old < year for old in old_years)):
            return text
    return ''


def event_image(html):
    match = re.search(r'<meta\b[^>]*property="og:image"[^>]*content="([^"]+)"',
                      html, re.I | re.S)
    image = unescape(match.group(1)) if match else ''
    parsed = urlsplit(image)
    if (parsed.scheme == 'https' and parsed.hostname == 'www.azalea.it'
            and parsed.path.startswith('/wp-content/uploads/')
            and re.search(r'\.(?:jpe?g|png|webp)$', parsed.path, re.I)
            and 'az-ogimage' not in parsed.path.casefold()):
        return image
    return None


def parse_event(html, url, *, today, listing=None):
    if not trusted_event_url(url):
        raise ValueError('untrusted Azalea event URL')
    canonical = re.search(r'<link\b[^>]*rel="canonical"[^>]*href="([^"]+)"', html, re.I | re.S)
    if canonical and unescape(canonical.group(1)) != url:
        raise ValueError('Azalea detail canonical mismatch')
    title = field(html, r'<h1\b[^>]*>(.*?)</h1>')
    schedule = field(html, r'<div class="single-event-date">(.*?)</div>')
    city = field(html, r'<div class="single-event-city">.*?<strong[^>]*>(.*?)</strong>')
    venue = field(html, r'<h2[^>]*>luogo</h2>\s*<p[^>]*>(.*?)</p>')
    match = re.search(r'\b\d{2}\.\d{2}\.\d{4}\b', schedule)
    if not match:
        raise ValueError('missing explicit Azalea event date')
    day = datetime.strptime(match.group(), '%d.%m.%Y').date()
    if listing:
        hero = field(html, r'<div\b[^>]*class="[^"]*\bevent-hero-tour\b[^"]*"[^>]*>(.*?)</div>',
                     required=False)
        listed_title = engine.normalize_for_search(listing['title'])
        if (listing['url'] != url or listing['date'] != day.isoformat()
                or engine.normalize_for_search(listing['city']) != engine.normalize_for_search(city)
                or listed_title not in {engine.normalize_for_search(title),
                                        engine.normalize_for_search(hero)}):
            raise ValueError('Azalea archive and detail disagree')
    town = engine.fvg_municipality_catalog.match_names(city)
    if not town or day < today:
        return None
    hour = re.search(r'\b([0-2]\d:[0-5]\d)\s*h\b', schedule)
    description = re.search(r'<div class="single-event-text">(.*?)</div>', html, re.I | re.S)
    description_html = description.group(1) if description else ''
    postponement = confirmed_postponement(title, description_html,
                                         day=day, city=city, venue=venue)
    if schedule_notice(title, description_html) and not postponement:
        raise ScheduleReviewRequired('schedule change requires review: ' + url)
    event = {'source': 'Azalea', 'url': url, 'title': title,
             'start_date': day.isoformat(), 'end_date': day.isoformat(),
             'event_city': city, 'venue': venue, 'place': venue,
             'date_evidence': schedule, 'date_evidence_kind': 'event_schedule',
             'lat': town.latitude, 'lon': town.longitude,
             'location_confidence': 'municipality', 'is_real': True}
    if hour:
        datetime.strptime(hour[1], '%H:%M')
        event['time'] = hour[1]
    event.update(attributed_excerpt(postponement or description_html, source_name='Azalea',
                                    source_url=url, title=title))
    image = event_image(html)
    if image:
        event['image'] = image
    reasons = validate_candidate(event, today=today)
    if reasons:
        raise ValueError('invalid Azalea event: ' + ','.join(reasons))
    return event


def collect_azalea(*, get=requests.get, today=None):
    from zoneinfo import ZoneInfo
    today = today or datetime.now(ZoneInfo('Europe/Rome')).date()

    def fetch(url):
        if url not in {ARCHIVE, SITEMAP} and not trusted_event_url(url) and not re.fullmatch(
                r'https://www\.azalea\.it/eventi/page/[2-9]/|https://www\.azalea\.it/eventi/page/10/', url):
            raise ValueError('untrusted Azalea fetch URL')
        with get(url, timeout=(4, 12), allow_redirects=False, stream=True) as response:
            response.raise_for_status()
            if response.status_code != 200 or response.url != url:
                raise ValueError('unexpected Azalea response')
            chunks, size = [], 0
            for chunk in response.iter_content(65536):
                size += len(chunk)
                if size > 4 * 1024 * 1024:
                    raise ValueError('Azalea page too large')
                chunks.append(chunk)
            return b''.join(chunks).decode('utf-8-sig')

    inventory, pages, seen = [], [], {}
    url, repeat_streak = ARCHIVE, 0
    for page in range(1, 11):
        html = fetch(url)
        cards = archive_cards(html)
        added = 0
        for card in cards:
            prior = seen.get(card['url'])
            if prior and prior != card:
                raise ValueError('conflicting Azalea archive cards')
            if not prior:
                inventory.append(card)
                seen[card['url']] = card
                added += 1
        pages.append({'url': url, 'cards': len(cards), 'new_urls': added})
        repeat_streak = repeat_streak + 1 if not added else 0
        next_url = archive_next(html, page)
        if repeat_streak >= 2 or not next_url:
            break
        url = next_url
    else:
        raise ValueError('Azalea archive exceeds page budget')
    if not inventory or len(inventory) > 200:
        raise ValueError('invalid Azalea archive inventory')

    sitemap = sitemap_events(fetch(SITEMAP))
    unlisted_delta = [event_url for event_url, lastmod in sitemap.items()
                      if event_url not in seen and BASELINE.get(event_url) != lastmod]
    if len(unlisted_delta) > 50:
        raise ValueError('Azalea sitemap delta exceeds detail budget')
    for event_url in unlisted_delta:
        if parse_event(fetch(event_url), event_url, today=today):
            raise ValueError('future FVG event absent from Azalea archive: ' + event_url)

    events, reviewed, checked = [], [], []
    for card in inventory:
        url = card['url']
        try:
            event = parse_event(fetch(url), url, today=today, listing=card)
            if event:
                events.append(event)
                disposition = 'included'
            elif date.fromisoformat(card['date']) < today:
                disposition = 'past'
            else:
                disposition = 'outside_region'
        except ScheduleReviewRequired:
            reviewed.append({'url': url, 'reason': 'schedule_change'})
            disposition = 'review_required'
        checked.append({'url': url, 'disposition': disposition})
    events = remove_cross_page_duplicates(events)
    events.sort(key=lambda item: (item['start_date'], item.get('time') or '',
                                  item['event_city'], item['title']))
    verification = {'collection_mode': 'complete-official-upcoming-archive',
                    'archive_pages': pages, 'listing_count': len(inventory),
                    'detail_count': len(checked), 'listing_records': inventory,
                    'detail_records': checked, 'included_count': len(events),
                    'review_count': len(reviewed),
                    'sitemap_event_urls': len(sitemap),
                    'sitemap_unlisted_delta_checked': len(unlisted_delta),
                    'source_complete': True}
    return {'status': 'ok', 'events': events, 'review_required': reviewed,
            'verification': verification,
            'coverage': 'official-upcoming-archive-and-every-detail'}


if __name__ == '__main__':
    result = collect_azalea()
    print({'records': len(result['events']),
           'cities': sorted({e['event_city'] for e in result['events']}),
           'review': result['review_required'],
           'verification': result['verification']})
