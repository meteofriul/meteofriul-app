import copy
from datetime import date, datetime
import json
import unittest

from app.events.pilot_pnpensa import (
    API, FIELDS, PAGE_API, PAGE_FIELDS, PAGE_SITEMAP, SITEMAP,
    classify_post, collect_pnpensa,
)
from app.events.pilot_programmes import reviewed_programme_metadata
from app.events.pilot_catalog import PILOT_PROJECT, merge_collection, query_catalog
from app.events.pilot_source_policy import gate_batch


URL = 'https://www.pnpensa.it/abc-finanza-2026/'
PAST_URL = 'https://www.pnpensa.it/concerto-passato/'
POST = {
    'id': 1, 'date': '2026-09-29T12:00:00', 'modified': '2026-10-06T12:00:00',
    'link': URL,
    'title': {'rendered': 'Cinque appuntamenti sull’educazione finanziaria dal 27 ottobre'},
    'content': {'rendered': '''<img src="https://www.pnpensa.it/wp-content/uploads/2026/09/finanza.jpg">
      <h4>Assicurazioni: istruzioni per l’uso</h4>
      <p>L’edizione 2026 dell’ABC dell’educazione finanziaria presenta cinque incontri
      per capire il rischio e scegliere con maggiore consapevolezza.</p>
      <p>Gli incontri si terranno il martedì sera, alle 19, a Pordenone.</p>'''},
}
PAST = {
    'id': 2, 'date': '2026-10-06T10:00:00', 'modified': '2026-10-06T10:00:00',
    'link': PAST_URL, 'title': {'rendered': 'Concerto a Pordenone 2 ottobre 2026'},
    'content': {'rendered': '<p>Resoconto della serata.</p>'},
}


class Response:
    status_code = 200

    def __init__(self, body, headers=None):
        self.body = body
        self.headers = headers or {}

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def raise_for_status(self):
        pass

    def iter_content(self, _):
        yield self.body


def fixture(*, missing_sitemap=False):
    sitemap_urls = [URL] if missing_sitemap else [URL, PAST_URL]
    xml = ('<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">' +
           ''.join(f'<url><loc>{url}</loc></url>' for url in sitemap_urls) +
           '</urlset>').encode()
    api_url = f'{API}?per_page=100&page=1&_fields={FIELDS}'
    page_api_url = f'{PAGE_API}?per_page=100&_fields={PAGE_FIELDS}'
    page = {'id': 9, 'link': 'https://www.pnpensa.it/',
            'modified': '2026-09-01T10:00:00',
            'content': {'rendered': '<p>Rassegne culturali</p>'}}
    page_xml = ('<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
                '<url><loc>https://www.pnpensa.it/</loc></url></urlset>').encode()
    pages = {SITEMAP: Response(xml),
             api_url: Response(json.dumps([POST, PAST]).encode(),
                               {'X-WP-Total': '2', 'X-WP-TotalPages': '1'}),
             PAGE_SITEMAP: Response(page_xml),
             page_api_url: Response(json.dumps([page]).encode(),
                                    {'X-WP-Total': '1', 'X-WP-TotalPages': '1'})}
    return collect_pnpensa(get=lambda url, **_: pages[url],
                           today=date(2026, 10, 7))


class PordenonePensaAuditTests(unittest.TestCase):
    def test_current_series_uses_only_published_first_date(self):
        events, disposition = classify_post(POST, today=date(2026, 10, 7))
        self.assertEqual(disposition, 'included')
        self.assertEqual(len(events), 1)
        self.assertEqual((events[0]['start_date'], events[0]['time'],
                          events[0]['event_city']),
                         ('2026-10-27', '19:00', 'Pordenone'))
        self.assertIn('edizione 2026', events[0]['date_evidence'])
        self.assertTrue(events[0]['description_excerpt'])
        self.assertTrue(events[0]['image'])

    def test_future_multi_session_programme_requires_session_extraction(self):
        unknown = copy.deepcopy(POST)
        unknown['title']['rendered'] = ('PordenonePensa in Giallo – '
                                        'dal 5 al 7 novembre 2026 Pordenone')
        with self.assertRaisesRegex(ValueError, 'multi-session'):
            classify_post(unknown, today=date(2026, 10, 7))

    def test_newly_published_second_date_cannot_be_silently_ignored(self):
        updated = copy.deepcopy(POST)
        updated['content']['rendered'] += '<p>Il secondo incontro sarà il 3 novembre.</p>'
        with self.assertRaisesRegex(ValueError, 'additional future date'):
            classify_post(updated, today=date(2026, 10, 7))

    def test_past_article_with_new_future_date_requires_review(self):
        updated = copy.deepcopy(PAST)
        updated['content']['rendered'] += '<p>Nuovo incontro il 27 ottobre 2026.</p>'
        with self.assertRaisesRegex(ValueError, 'additional future date'):
            classify_post(updated, today=date(2026, 10, 7))

    def test_all_posts_reconcile_with_sitemap_and_gate(self):
        batch = fixture()
        self.assertEqual(batch['verification']['post_count'], 2)
        self.assertEqual([item['disposition'] for item in
                          batch['verification']['detail_records']],
                         ['included', 'past'])
        self.assertEqual(gate_batch('Pordenone Pensa', batch,
                                    today=date(2026, 10, 7))['status'], 'ok')
        with self.assertRaisesRegex(ValueError, 'API/sitemap mismatch'):
            fixture(missing_sitemap=True)
        damaged = copy.deepcopy(batch)
        damaged['verification']['post_count'] = 1
        self.assertEqual(gate_batch('Pordenone Pensa', damaged,
                                    today=date(2026, 10, 7))['status'], 'error')

    def test_future_date_disappearance_blocks_refresh(self):
        batch = fixture()
        old = copy.deepcopy(batch['events'][0])
        old['start_date'] = old['end_date'] = '2026-10-28'
        result = gate_batch('Pordenone Pensa', batch,
                            today=date(2026, 10, 7),
                            previous_batch={'events': [old]})
        self.assertEqual(result['error_type'], 'source_verification_failed')

    def test_unrelated_pensa_event_is_not_grouped_into_2026_giallo(self):
        event = classify_post(POST, today=date(2026, 10, 7))[0][0]
        self.assertIsNone(reviewed_programme_metadata(event))
        catalog = merge_collection(PILOT_PROJECT, None,
                                   {'Pordenone Pensa': fixture()},
                                   '2026-10-07T08:00:00Z')
        rows = query_catalog(catalog, 45.95689, 12.66051, radius=20,
                             now=datetime.fromisoformat('2026-10-07T10:00:00+02:00'))['events']
        self.assertEqual(len(rows), 1)
        self.assertNotIn('programme_id', rows[0])
        self.assertTrue(rows[0]['image'])
        self.assertTrue(rows[0]['description_excerpt'])


if __name__ == '__main__':
    unittest.main()
