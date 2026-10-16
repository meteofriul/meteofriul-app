"""Coverage and fail-closed checks for the read-only GiroFVG monitor."""
from datetime import date
import unittest
from unittest.mock import patch

from app.events import pilot_girofvg_watch as watch


EVENT = watch.BASE + '/festa-2026'
PAGE = watch.BASE + '/fiere-e-mostre?start=1'
STAMP = '2026-10-07T12:00:00Z'


def card(*, place='Udine', end='09-10-2026', url='/festa-2026'):
    return ('<div class="com-content-category-blog__item blog-item">'
            f'<div class="article-header"><h2><a href="{url}">Festa 2026</a></h2></div>'
            '<li class="field-entry data-inizio "><span class="field-value ">08-10-2026</span></li>'
            f'<li class="field-entry data-fine "><span class="field-value ">{end}</span></li>'
            f'<li class="field-entry luogo "><span class="field-value ">{place}</span></li>'
            '</div>')


def sitemap(*, modified=STAMP):
    return ('<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
            f'<url><loc>{EVENT}</loc><lastmod>{modified}</lastmod></url>'
            '</urlset>').encode()


def baseline():
    return {'schema': 'girofvg-watch-baseline-v1', 'sitemap_recent': {EVENT: STAMP},
            'sitemap_undated': [],
            'active_cards': {EVENT: {'start': '08-10-2026', 'end': '09-10-2026',
                                     'place': 'Udine'}},
            'category_active_urls': [EVENT],
            'known_past_undated_cards': {}, 'known_page_errors': [PAGE]}


class Response:
    def __init__(self, status, payload, content_type):
        self.status_code = status
        self.payload = payload if isinstance(payload, bytes) else payload.encode()
        self.headers = {'Content-Type': content_type}

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def iter_content(self, _size):
        yield self.payload


def fake_get(*, place='Udine', second_status=500, event_url='/festa-2026',
             end='09-10-2026'):
    page1 = card(place=place, end=end, url=event_url) + (
        '<a aria-label="Vai alla pagina fine" href="/fiere-e-mostre?start=1">fine</a>')
    responses = {
        watch.SITEMAP: Response(200, sitemap(), 'application/xml'),
        watch.INDEX: Response(200,
                              '<a href="/eventi">Eventi</a><ul class="sp-dropdown-items">'
                              '<a href="/fiere-e-mostre">Fiere</a></ul>', 'text/html'),
        watch.BASE + '/fiere-e-mostre': Response(200, page1, 'text/html'),
        PAGE: Response(second_status, card(end='07-10-2026'), 'text/html'),
    }
    return lambda url, **_kwargs: responses[url]


class GiroFVGWatchTests(unittest.TestCase):
    def test_sitemap_rejects_missing_or_duplicate_inventory(self):
        with patch.object(watch, 'MIN_SITEMAP_URLS', 1):
            entries, recent = watch.parse_sitemap(sitemap(), date(2026, 10, 8))
            self.assertEqual(recent, {EVENT: STAMP})
            self.assertEqual(len(entries), 1)
            duplicate = sitemap().replace(b'</urlset>',
                                           f'<url><loc>{EVENT}</loc><lastmod>{STAMP}</lastmod></url></urlset>'.encode())
            with self.assertRaisesRegex(ValueError, 'duplicate'):
                watch.parse_sitemap(duplicate, date(2026, 10, 8))
            with self.assertRaisesRegex(ValueError, 'timestamp'):
                watch.parse_sitemap(sitemap(modified='2026-99-99T12:00:00Z'),
                                    date(2026, 10, 8))

    def test_listing_reads_structured_fields_and_page_one_link(self):
        html = card() + ('<a aria-label="Vai alla pagina 1" href="/fiere-e-mostre">1</a>'
                         '<a aria-label="Vai alla pagina fine" '
                         'href="/fiere-e-mostre?start=21">fine</a>')
        rows, last = watch.parse_listing(html, 'fiere-e-mostre')
        self.assertEqual(rows[0]['place'], 'Udine')
        self.assertEqual(last, 21)
        self.assertEqual(watch._page_start('/fiere-e-mostre', 'fiere-e-mostre'), 0)
        with self.assertRaisesRegex(ValueError, 'pagination'):
            watch._page_start('/fiere-e-mostre?start=21&tracking=x', 'fiere-e-mostre')

    def test_known_historical_500_is_explicitly_incomplete(self):
        with (patch.object(watch, 'MIN_SITEMAP_URLS', 1),
              patch.object(watch, 'MIN_CATEGORY_PAGES', 1),
              patch.object(watch, 'CATEGORIES', ('fiere-e-mostre',)),
              patch.object(watch, 'PAGE_SIZE', 1)):
            result = watch.collect_watch(date(2026, 10, 8),
                                         get=fake_get(), baseline=baseline())
        self.assertFalse(result['source_complete'])
        self.assertEqual((result['category_pages_expected'],
                          result['category_pages_read']), (2, 1))
        self.assertEqual(result['known_page_errors'], [PAGE])
        self.assertEqual(result['changes'], [])

    def test_new_place_requires_review_without_publishing(self):
        with (patch.object(watch, 'MIN_SITEMAP_URLS', 1),
              patch.object(watch, 'MIN_CATEGORY_PAGES', 1),
              patch.object(watch, 'CATEGORIES', ('fiere-e-mostre',)),
              patch.object(watch, 'PAGE_SIZE', 1)):
            result = watch.collect_watch(date(2026, 10, 8),
                                         get=fake_get(place='Trieste'), baseline=baseline())
        self.assertEqual(result['changes'][0]['reason'], 'new_or_changed_active_card')
        self.assertNotIn('events', result)

    def test_disappearing_reviewed_future_card_requires_review(self):
        with (patch.object(watch, 'MIN_SITEMAP_URLS', 1),
              patch.object(watch, 'MIN_CATEGORY_PAGES', 1),
              patch.object(watch, 'CATEGORIES', ('fiere-e-mostre',)),
              patch.object(watch, 'PAGE_SIZE', 1)):
            result = watch.collect_watch(date(2026, 10, 8),
                                         get=fake_get(event_url='/old-past', end='07-10-2026'),
                                         baseline=baseline())
        self.assertIn('reviewed_future_card_disappeared',
                      {change['reason'] for change in result['changes']})

    def test_unrecognized_archive_failure_blocks_watch(self):
        with (patch.object(watch, 'MIN_SITEMAP_URLS', 1),
              patch.object(watch, 'MIN_CATEGORY_PAGES', 1),
              patch.object(watch, 'CATEGORIES', ('fiere-e-mostre',)),
              patch.object(watch, 'PAGE_SIZE', 1)):
            with self.assertRaisesRegex(ValueError, 'HTTP 503'):
                watch.collect_watch(date(2026, 10, 8),
                                    get=fake_get(second_status=503), baseline=baseline())

    def test_sitemap_drift_during_archive_scan_blocks_watch(self):
        original_get = fake_get()
        sitemap_reads = 0

        def changing_get(url, **kwargs):
            nonlocal sitemap_reads
            if url == watch.SITEMAP:
                sitemap_reads += 1
                if sitemap_reads == 2:
                    return Response(200, sitemap(modified='2026-10-08T12:00:00Z'),
                                    'application/xml')
            return original_get(url, **kwargs)

        with (patch.object(watch, 'MIN_SITEMAP_URLS', 1),
              patch.object(watch, 'MIN_CATEGORY_PAGES', 1),
              patch.object(watch, 'CATEGORIES', ('fiere-e-mostre',)),
              patch.object(watch, 'PAGE_SIZE', 1)):
            with self.assertRaisesRegex(ValueError, 'changed while paging'):
                watch.collect_watch(date(2026, 10, 8),
                                    get=changing_get, baseline=baseline())


if __name__ == '__main__':
    unittest.main()
