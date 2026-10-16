"""Correlate TurismoFVG's detail sitemap with dated calendar cards."""
from collections import defaultdict

from . import engine
from .pilot_regional_sitemap import compare_calendar_urls


def build_candidate_index(sitemap, calendar):
    if sitemap.get('status') != 'ok' or calendar.get('status') != 'ok':
        raise ValueError('incomplete TurismoFVG source index')
    if not calendar.get('horizon_complete'):
        raise ValueError('TurismoFVG future search not complete')
    grouped = defaultdict(list)
    for card in calendar['cards']:
        url = card.get('url')
        if not engine.is_trusted_turismofvg_event_url(url):
            raise ValueError('untrusted TurismoFVG calendar card')
        grouped[url].append(card)
    sitemap_dates = {item['url']: item.get('lastmod')
                     for item in sitemap['detail_urls']}
    candidates, review = [], []
    for url, cards in grouped.items():
        titles = {engine.normalize_for_search(card.get('title')) for card in cards}
        if len(titles) != 1 or not next(iter(titles)):
            review.append({'url': url, 'review_reason': 'conflicting_calendar_titles'})
            continue
        places = sorted({card['place'] for card in cards if card.get('place')})
        first = cards[0]
        dates = sorted({card['badge_date'] for card in cards if card.get('badge_date')})
        candidate = {
            'source': 'TurismoFVG', 'url': url, 'title': first['title'],
            'event_city': places[0] if len(places) == 1 else None,
            'listing_places': places, 'listing_occurrences': dates,
            'listing_card_count': len(cards),
            'discovery_kind': 'filtered_calendar',
            'sitemap_lastmod': sitemap_dates.get(url),
            **(first.get('classification') or {}),
        }
        if first.get('image'):
            candidate['image'] = first['image']
        if len(places) > 1:
            review.append({'url': url, 'review_reason': 'multiple_listing_places',
                           'places': places})
        candidates.append(candidate)
    comparison = compare_calendar_urls(sitemap, calendar['cards'])
    return {'status': 'ok', 'detail_candidates': candidates,
            'review_required': review,
            'verification': {
                'collection_mode': calendar['collection_mode'],
                'windows': calendar['windows'], 'overflow': calendar['overflow'],
                'horizon_complete': calendar['horizon_complete'],
                'declared_results': calendar['declared_results'],
                'cards_seen': calendar['cards_seen'], 'pages': calendar['pages'],
                'calendar_unique_urls': comparison['calendar_unique_urls'],
                'sitemap_unique_urls': sitemap['unique_urls'],
                'missing_from_sitemap': comparison['missing_from_sitemap'],
                'sitemap_only_unclassified': len(comparison['sitemap_only_urls']),
                'sitemap_only_urls': comparison['sitemap_only_urls'],
            }}
