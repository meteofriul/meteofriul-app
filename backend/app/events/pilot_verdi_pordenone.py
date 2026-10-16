"""Pilot reader for explicitly dated Teatro Verdi Pordenone performances."""
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime
from html.parser import HTMLParser
import json
import re
from urllib.parse import parse_qs, urlsplit
from zoneinfo import ZoneInfo
from xml.etree import ElementTree
import requests
from .pilot_azalea import clean
from .pilot_excerpt import attributed_excerpt
from .pilot_source_probe import Markup
from . import engine
from .pilot_schedule import schedule_notice
from .pilot_source_policy import validate_candidate

BASE = "https://teatroverdipordenone.it"
SITEMAP_INDEX = BASE + '/sitemap_index.xml'
ARCHIVE_SITEMAP = BASE + '/spettacolo-sitemap.xml'
RECENT_SITEMAP = BASE + '/spettacolo-sitemap2.xml'
SEASON_TERMS_API = BASE + '/wp-json/wp/v2/spettacolo_stagione?per_page=100&_fields=id,name,count'
SEASON_SHOWS_API = BASE + '/wp-json/wp/v2/spettacolo'
AUDIT_BASELINE = '2026-10-07T00:00:00+00:00'
MONTHS = {name: index for index, name in enumerate(
    "gennaio febbraio marzo aprile maggio giugno luglio agosto settembre ottobre novembre dicembre".split(), 1)}


def canonical_listing_link(link):
    """Discard only the theatre's verified advertising tag on page links."""
    parsed = urlsplit(link)
    if parsed.scheme != 'https' or parsed.hostname != 'teatroverdipordenone.it':
        return None
    path = parsed.path
    if re.fullmatch(r'/spettacolo/[^/]+/', path):
        if parsed.query or parsed.fragment:
            raise ValueError('unexpected Teatro Verdi show link parameters')
        return BASE + path
    if path != '/la-stagione/' and not re.fullmatch(r'/la-stagione/page/\d+/', path):
        return None
    if parsed.fragment:
        raise ValueError('unexpected Teatro Verdi pagination fragment')
    if parsed.query:
        params = parse_qs(parsed.query, keep_blank_values=True)
        ad_click = (set(params) == {'gclid'} and len(params['gclid']) == 1
                    and re.fullmatch(r'[A-Za-z0-9_-]{1,256}', params['gclid'][0]))
        newsletter_keys = {'utm_source', 'utm_medium', 'utm_content', 'utm_campaign'}
        newsletter = (set(params) == newsletter_keys
                      and params['utm_source'] == ['ActiveCampaign']
                      and params['utm_medium'] == ['email']
                      and all(len(values) == 1 and 0 < len(values[0]) <= 256
                              and values[0].isprintable() for values in params.values()))
        if not (ad_click or newsletter):
            raise ValueError('unexpected Teatro Verdi pagination parameters: '
                             + ','.join(sorted(params)))
    return BASE + path


class VenueReviewRequired(ValueError):
    pass


class DetailMedia(HTMLParser):
    """Official event image and narrative paragraphs, excluding ticket boilerplate."""
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.image = None
        self.div_classes = []
        self.paragraph = None
        self.paragraphs = []

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if tag == 'meta' and values.get('property') == 'og:image':
            image = values.get('content') or ''
            parsed = urlsplit(image)
            if (parsed.scheme == 'https' and parsed.hostname == 'teatroverdipordenone.it'
                    and parsed.path.startswith('/wp-content/uploads/')):
                self.image = image
        if tag == 'div':
            self.div_classes.append(set((values.get('class') or '').split()))
        elif tag == 'p' and self.div_classes and {
                'col-12', 'col-lg-9'} <= self.div_classes[-1]:
            self.paragraph = []
        elif tag == 'br' and self.paragraph is not None:
            self.paragraph.append(' ')

    def handle_data(self, value):
        if self.paragraph is not None:
            self.paragraph.append(value)

    def handle_endtag(self, tag):
        if tag == 'p' and self.paragraph is not None:
            self.paragraphs.append(clean(' '.join(self.paragraph)))
            self.paragraph = None
        elif tag == 'div' and self.div_classes:
            self.div_classes.pop()


def detail_media(html, *, url, title):
    parser = DetailMedia()
    parser.feed(html)
    excerpt = next((paragraph for paragraph in parser.paragraphs
                    if len(paragraph) >= 80 and not re.match(
                        r'(?i)^(?:programma\b|fonte\b|regia\b|con\b|musiche\b|testo\b|riconoscimenti\b)',
                        paragraph)), '')
    return {'image': parser.image,
            **attributed_excerpt(excerpt, source_name='Teatro Verdi Pordenone',
                                 source_url=url, title=title)}


def parse_performances(html, url, *, today):
    title = re.search(r'<h1\b[^>]*>(.*?)</h1>', html, re.S)
    dates = re.search(r'<div class="article-dates">(.*?)</div>', html, re.S)
    if title and not dates:
        raise VenueReviewRequired("missing schedule requires review: " + url)
    if not title or not dates:
        raise ValueError("unrecognized performance page: " + url)
    blocks = re.findall(r'<p\b[^>]*>(.*?)</p>', dates[1], re.S)
    rooms = [clean(b) for b in blocks if not re.search(r"\b20\d{2}\b", clean(b))]
    if not rooms:
        raise ValueError("missing performance room")
    slots = []
    for block in blocks:
        text = clean(block)
        if text in rooms:
            continue
        match = re.search(r"\b(\d{1,2})\s+(\w+)\s+(20\d{2})\b", text, re.I)
        hour = re.search(r"\bOre\s+(\d{1,2}[:.]\d{2})\b", text, re.I)
        if not match or not hour or match[2].lower() not in MONTHS:
            raise ValueError("ambiguous performance date")
        day = date(int(match[3]), MONTHS[match[2].lower()], int(match[1]))
        clock = datetime.strptime(hour[1].replace(".", ":"), "%H:%M").strftime("%H:%M")
        slots.append((day, clock, text))
    if not slots:
        raise ValueError('missing explicit performance dates')
    if not any(day >= today for day, _, _ in slots):
        return []
    if schedule_notice(title[1], dates[1]):
        raise VenueReviewRequired("schedule_change_requires_review")
    # Only these verified in-theatre rooms may inherit the theatre municipality.
    # Spazio Due confirmed by the theatre's /le-sale/ page, 2026-09-07.
    if any(room.casefold() not in {"sala grande", "sala ridotto", "ridotto", "palco", "spazio due"} for room in rooms):
        raise VenueReviewRequired("external or unknown venue requires review: " + url + " " + repr(rooms))
    town = engine.fvg_municipality_catalog.match_names("Pordenone")
    events = []
    media = detail_media(html, url=url, title=clean(title[1]))
    for day, clock, text in slots:
        if day < today:
            continue
        events.append({"source": "Teatro Verdi Pordenone", "title": clean(title[1]), "url": url,
                       "start_date": day.isoformat(), "end_date": day.isoformat(), "time": clock,
                       "event_city": "Pordenone", "venue": "Teatro Verdi · " + ", ".join(rooms),
                       "place": "Teatro Verdi, Pordenone", "lat": town.latitude, "lon": town.longitude,
                       "location_confidence": "municipality", "date_evidence": text,
                       "date_evidence_kind": "event_schedule", "is_real": True,
                       **media})
    return events


def collect_verdi_pordenone(*, get=requests.get, today=None):
    today = today or datetime.now(ZoneInfo("Europe/Rome")).date()
    def fetch(url, *, max_bytes=4*1024*1024):
        path = urlsplit(url)
        if (path.scheme != 'https' or path.hostname != 'teatroverdipordenone.it'
                or path.query or path.fragment
                or (url not in {SITEMAP_INDEX, ARCHIVE_SITEMAP, RECENT_SITEMAP,
                                BASE + '/la-stagione/'}
                    and not re.fullmatch(
                        r'/(?:la-stagione/page/\d+|spettacolo/[^/]+)/', path.path))):
            raise ValueError('untrusted Teatro Verdi Pordenone URL')
        with get(url, timeout=(4, 12), stream=True, allow_redirects=False) as response:
            response.raise_for_status()
            if response.status_code != 200:
                raise ValueError("unexpected redirect or response")
            chunks, size = [], 0
            for chunk in response.iter_content(65536):
                size += len(chunk)
                if size > max_bytes:
                    raise ValueError("page too large")
                chunks.append(chunk)
            return b"".join(chunks).decode("utf-8-sig")

    def api_json(url):
        if (url != SEASON_TERMS_API and not re.fullmatch(
                re.escape(SEASON_SHOWS_API) +
                r'\?spettacolo_stagione=\d+&per_page=100&page=\d+&' +
                r'_fields=id,link,modified,spettacolo_stagione', url)):
            raise ValueError('untrusted Teatro Verdi API URL')
        with get(url, timeout=(4, 12), stream=True, allow_redirects=False) as response:
            response.raise_for_status()
            if response.status_code != 200:
                raise ValueError('unexpected Teatro Verdi API response')
            chunks, size = [], 0
            for chunk in response.iter_content(65536):
                size += len(chunk)
                if size > 2*1024*1024:
                    raise ValueError('oversized Teatro Verdi API response')
                chunks.append(chunk)
            return json.loads(b''.join(chunks).decode('utf-8-sig')), response.headers

    namespace = '{http://www.sitemaps.org/schemas/sitemap/0.9}'
    index = ElementTree.fromstring(fetch(SITEMAP_INDEX, max_bytes=1024*1024))
    show_maps = {item.text for item in index.findall('.//' + namespace + 'loc')
                 if 'spettacolo-sitemap' in (item.text or '')}
    if show_maps != {ARCHIVE_SITEMAP, RECENT_SITEMAP}:
        raise ValueError('unknown Teatro Verdi sitemap structure')
    def sitemap(url):
        root = ElementTree.fromstring(fetch(url, max_bytes=2*1024*1024))
        return {node.findtext(namespace + 'loc'): node.findtext(namespace + 'lastmod')
                for node in root.findall(namespace + 'url')
                if re.fullmatch(r'/spettacolo/[^/]+/',
                                urlsplit(node.findtext(namespace + 'loc') or '').path)}
    archive = sitemap(ARCHIVE_SITEMAP)
    recent = sitemap(RECENT_SITEMAP)
    if (not 1 <= len(archive) <= 1000 or not 1 <= len(recent) <= 1000
            or set(archive) & set(recent)
            or any(not modified for modified in archive.values())):
        raise ValueError('invalid Teatro Verdi spectacle sitemaps')
    queue, seen, links, listing_pages = [BASE + "/la-stagione/"], set(), set(), []
    while queue:
        url = queue.pop(0)
        if url in seen:
            continue
        if len(seen) >= 10:
            raise ValueError("pagination limit")
        seen.add(url)
        parser = Markup()
        parser.feed(fetch(url))
        page_links = set()
        for link in parser.links:
            canonical = canonical_listing_link(link)
            if not canonical:
                continue
            path = urlsplit(canonical).path
            if re.fullmatch(r"/spettacolo/[^/]+/", path):
                links.add(canonical)
                page_links.add(canonical)
            elif re.fullmatch(r"/la-stagione/page/\d+/", path) and canonical not in seen:
                queue.append(canonical)
        listing_pages.append({'url': url, 'links': len(page_links)})
    if not links or len(links) > 150:
        raise ValueError("invalid listing size")
    terms, term_headers = api_json(SEASON_TERMS_API)
    if (not isinstance(terms, list) or not 1 <= len(terms) <= 100
            or int(term_headers['X-WP-Total']) != len(terms)
            or int(term_headers['X-WP-TotalPages']) != 1):
        raise ValueError('invalid Teatro Verdi season taxonomy')
    start_year = today.year if today.month >= 8 else today.year - 1
    active_terms = []
    for term in terms:
        match = re.fullmatch(r'(?:Programmazione|Spettacoli)\s+(20\d{2})/(20\d{2})',
                             term['name'], re.I)
        if match and int(match[2]) == int(match[1]) + 1 and int(match[1]) >= start_year:
            active_terms.append(term)
    if not active_terms or len(active_terms) > 3:
        raise ValueError('current Teatro Verdi season term missing')
    season_api_urls = set()
    for term in active_terms:
        found, declared = [], None
        for page in range(1, 4):
            url = (f'{SEASON_SHOWS_API}?spettacolo_stagione={term["id"]}'
                   f'&per_page=100&page={page}&_fields=id,link,modified,spettacolo_stagione')
            rows, headers = api_json(url)
            total = int(headers['X-WP-Total'])
            page_count = int(headers['X-WP-TotalPages'])
            if (not isinstance(rows, list) or not 1 <= page_count <= 3
                    or total < 1 or total > 300
                    or page_count != (total + 99) // 100
                    or (declared is not None and declared != total)
                    or len(rows) != min(100, total - len(found))):
                raise ValueError('incomplete Teatro Verdi season API')
            declared = total
            found.extend(rows)
            if page == page_count:
                break
        if len(found) != declared or len({row['id'] for row in found}) != declared:
            raise ValueError('duplicate or missing Teatro Verdi API show')
        season_api_urls.update(row['link'] for row in found)
    if season_api_urls != links:
        raise ValueError('Teatro Verdi season API/listing mismatch')
    if not links <= set(archive) | set(recent):
        raise ValueError('listing URL absent from Teatro Verdi sitemap')
    changed_archive = [url for url, modified in archive.items()
                       if modified and modified >= AUDIT_BASELINE
                       and url not in links and url not in recent]
    if changed_archive:
        raise ValueError('changed Teatro Verdi archive URL outside current inventory')

    urls = sorted(set(recent) | links)
    with ThreadPoolExecutor(max_workers=4) as pool:
        html_by_url = dict(zip(urls, pool.map(fetch, urls)))
    events, review, checked = [], [], []
    for link in urls:
        try:
            parsed = parse_performances(html_by_url[link], link, today=today)
            if parsed and link not in links:
                raise ValueError('future spectacle absent from season listing')
            for event in parsed:
                invalid = validate_candidate(event, today=today)
                if invalid or not event.get('image') or not event.get('description_excerpt'):
                    raise ValueError('incomplete Teatro Verdi event: ' + ','.join(invalid))
            events.extend(parsed)
            disposition = 'included' if parsed else 'past'
        except (ValueError, VenueReviewRequired) as exc:
            review.append({'url': link, 'reason': str(exc)})
            disposition = 'review_required'
        checked.append({'url': link, 'disposition': disposition})
    events.sort(key=lambda item: (item['start_date'], item.get('time') or '',
                                  item['event_city'], item['title'], item['url']))
    proof = {'collection_mode': 'complete-verdi-pordenone-current-list-and-sitemap',
             'listing_pages': listing_pages, 'listing_count': len(links),
             'listing_urls': sorted(links), 'recent_sitemap_count': len(recent),
             'recent_sitemap_urls': sorted(recent),
             'season_term_ids': sorted(term['id'] for term in active_terms),
             'season_api_count': len(season_api_urls),
             'season_api_urls': sorted(season_api_urls),
             'archive_sitemap_count': len(archive),
             'archive_changed_unlisted': len(changed_archive),
             'detail_count': len(checked), 'detail_records': checked,
             'event_count': len(events), 'review_count': len(review),
             'source_complete': True}
    return {"status": "ok", "events": events, "review_required": review,
            'verification': proof,
            "coverage": "complete-current-list-and-recent-sitemap-details"}


if __name__ == "__main__":
    result = collect_verdi_pordenone()
    print({"performances": len(result["events"]), "review": result["review_required"]})
