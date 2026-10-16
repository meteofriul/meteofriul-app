import unittest
from unittest.mock import Mock

from app.events.pilot_regional_sitemap import compare_calendar_urls, discover_detail_urls


NS = 'http://www.sitemaps.org/schemas/sitemap/0.9'


class RegionalSitemapTests(unittest.TestCase):
    def test_reads_official_index_and_italian_detail_urls(self):
        index = (f'<sitemapindex xmlns="{NS}"><sitemap><loc>'
                 'https://www.turismofvg.it/sitemapcms?index=0'
                 '</loc></sitemap></sitemapindex>')
        child = (f'<urlset xmlns="{NS}"><url><loc>'
                 'https://www.turismofvg.it/eventi/festa'
                 '</loc><lastmod>2026-10-04T10:00:00Z</lastmod></url>'
                 '<url><loc>https://www.turismofvg.it/events/festival</loc></url>'
                 '</urlset>')
        def get(url, **_):
            return Mock(url=url, content=(index if 'index=' not in url else child).encode())
        result = discover_detail_urls(get=get)
        self.assertEqual(result['unique_urls'], 1)
        self.assertEqual(result['detail_urls'][0]['url'],
                         'https://www.turismofvg.it/eventi/festa')
        self.assertEqual(result['detail_urls'][0]['lastmod'], '2026-10-04T10:00:00Z')

    def test_calendar_catches_valid_page_missing_from_sitemap(self):
        sitemap = {'detail_urls': [{'url': 'https://www.turismofvg.it/eventi/festa'}]}
        cards = [{'url': 'https://www.turismofvg.it/eventi/festa'},
                 {'url': 'https://www.turismofvg.it/eventi/nuova'}]
        comparison = compare_calendar_urls(sitemap, cards)
        self.assertEqual(comparison['missing_from_sitemap'],
                         ['https://www.turismofvg.it/eventi/nuova'])
        self.assertEqual(comparison['calendar_unique_urls'], 2)


if __name__ == '__main__':
    unittest.main()
