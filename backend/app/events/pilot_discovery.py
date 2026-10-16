"""Discover highlighted event references without treating start dates as schedules."""
from html import unescape
import re
from urllib.parse import urljoin, urlsplit
from . import engine


def highlighted_candidates(html):
    chunks = re.split(r'<div\b[^>]*class=["\'][^"\']*\bc-events_showreel__slide\b[^"\']*["\'][^>]*>', html, flags=re.I)
    result, seen = [], set()
    for chunk in chunks[1:]:
        # The caption/end of this slide is outside its identifying info block.
        block = chunk.split('c-events_showreel__caption', 1)[0]
        title = re.search(r'<h2\b[^>]*class=["\'][^"\']*c-events_showreel__title[^"\']*["\'][^>]*>(.*?)</h2>', block, re.I | re.S)
        anchor = re.search(r'<a\b(?=[^>]*class=["\'][^"\']*c-events_showreel__link)[^>]*href=["\']([^"\']+)["\']', block, re.I)
        if not title or not anchor:
            continue
        url = urljoin('https://www.turismofvg.it', unescape(anchor[1]))
        parsed = urlsplit(url)
        if not engine.is_trusted_turismofvg_event_url(url) or url in seen:
            continue
        seen.add(url)
        date_hint = re.search(r'<h3\b[^>]*>(.*?)</h3>', block, re.I | re.S)
        city = re.search(r'<h4\b[^>]*>\s*<strong\b[^>]*>(.*?)</strong>', block, re.I | re.S)
        result.append({'source': 'TurismoFVG', 'url': url,
                       'title': engine.clean_event_text(title[1]),
                       'event_city': engine.clean_event_text(city[1]) if city else None,
                       'date_hint': engine.clean_event_text(date_hint[1]) if date_hint else None,
                       'discovery_kind': 'highlight', 'review_reason': 'full_schedule_requires_detail'})
    return result
