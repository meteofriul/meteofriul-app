import unittest

from app.events.pilot_regional_sitemap_cards import create_snapshot, inspect_batch


class RegionalSitemapCardsTests(unittest.TestCase):
    base = 'https://www.turismofvg.it/eventi/'

    @staticmethod
    def detail(title='Festa', date_text='10 ottobre 2026'):
        return (f'<h1>{title}</h1><div class="body_col1">'
                '<h2>Descrizione</h2><p>Programma ufficiale della festa.</p></div>'
                '<div class="body_col2">'
                f'<div style="background-image: url(icn__calendar.svg)">{date_text}</div>'
                '<div style="background-image: url(icn__pin.svg)">Udine</div>'
                '<div style="background-image: url(icn__building.svg)">Piazza Primo Maggio</div>'
                '<div class="c-detail__actions"></div>')

    def source_snapshot(self):
        future, old = self.base + 'festa', self.base + 'archivio'
        return {'schema': 'turismofvg-sitemap-only-audit-v1',
                'as_of_date': '2026-10-05', 'snapshot_id': 'abc',
                'sitemap_only_urls': [future, old], 'attempts': {},
                'results': {
                    future: {'status': 'future_candidate', 'title': 'Festa',
                             'event_city': 'Udine', 'date_full': '10 ottobre 2026'},
                    old: {'status': 'past_event', 'title': 'Archivio',
                          'event_city': 'Udine', 'date_full': '10 ottobre 2024'}}}

    def test_only_future_details_are_eligible_and_match_live_detail(self):
        snapshot = create_snapshot(self.source_snapshot())
        self.assertEqual([item['url'] for item in snapshot['items']],
                         [self.base + 'festa'])
        seen = []
        def fetch(url):
            seen.append(url)
            return self.detail()
        audited = inspect_batch(snapshot, fetch_html=fetch)
        event = audited['results'][self.base + 'festa']['event']
        self.assertEqual(event['description_source_url'], self.base + 'festa')
        self.assertEqual(event['event_city'], 'Udine')
        self.assertEqual(len(seen), 1)
        self.assertEqual(len(inspect_batch(audited, fetch_html=fetch)['results']), 1)
        self.assertEqual(len(seen), 1)

    def test_changed_detail_requires_review(self):
        snapshot = create_snapshot(self.source_snapshot())
        audited = inspect_batch(snapshot, fetch_html=lambda _: self.detail(title='Altra festa'))
        self.assertEqual(audited['results'][self.base + 'festa']['reason'],
                         'sitemap_detail_changed')

    def test_incomplete_source_inventory_is_rejected(self):
        source = self.source_snapshot()
        source['results'].pop(self.base + 'archivio')
        with self.assertRaises(ValueError):
            create_snapshot(source)


if __name__ == '__main__':
    unittest.main()
