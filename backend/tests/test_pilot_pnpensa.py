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


def programme_post():
    post = copy.deepcopy(POST)
    post['content']['rendered'] += ''.join(
        f'<section><div><img src="https://www.pnpensa.it/wp-content/uploads/2026/{day}.jpg"></div>'
        f'<div><p><strong>Martedì {day} {month}, ore 19</strong></p>'
        f'<p><strong>Pordenone, <a href="https://example.test/">{venue}</a></strong></p>'
        f'<p><b>Incontro {index}: {title}</b></p>'
        '<p>Un approfondimento sui rischi e sulle scelte assicurative, aperto al pubblico.</p>'
        '</div></section>'
        for index, (day, month, venue, title) in enumerate([
            (27, 'ottobre', 'Spazio Zero, Piazza Maestri del lavoro 3', 'Il rischio'),
            (3, 'novembre', 'Biblioteca Civica, sala Degan', 'I beni'),
            (10, 'novembre', 'Biblioteca Civica, sala Degan', 'La persona'),
            (17, 'novembre', 'Ex convento di San Francesco', 'Le imprese'),
            (24, 'novembre', 'Biblioteca Civica, sala Degan', 'Il patrimonio')], 1))
    return post


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


def fixture(*, missing_sitemap=False, posts=None):
    posts = posts or [POST, PAST]
    sitemap_urls = [posts[0]['link']] if missing_sitemap else [
        post['link'] for post in posts]
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
             api_url: Response(json.dumps(posts).encode(),
                               {'X-WP-Total': str(len(posts)),
                                'X-WP-TotalPages': '1'}),
             PAGE_SITEMAP: Response(page_xml),
             page_api_url: Response(json.dumps([page]).encode(),
                                    {'X-WP-Total': '1', 'X-WP-TotalPages': '1'})}
    return collect_pnpensa(get=lambda url, **_: pages[url],
                           today=date(2026, 10, 7))


class PordenonePensaAuditTests(unittest.TestCase):

    def test_programme_recovers_five_distinct_sessions_through_catalogue(self):
        batch = fixture(posts=[programme_post(), PAST])
        self.assertEqual(gate_batch('Pordenone Pensa', batch,
                                    today=date(2026, 10, 7))['status'], 'ok')
        events = batch['events']
        self.assertEqual([e['start_date'] for e in events],
                         ['2026-10-27', '2026-11-03', '2026-11-10', '2026-11-17', '2026-11-24'])
        self.assertEqual({e['time'] for e in events}, {'19:00'})
        self.assertEqual(events[3]['venue'], 'Ex convento di San Francesco')
        self.assertEqual(len({e['image'] for e in events}), 5)
        self.assertTrue(all(e.get('description_excerpt') for e in events))
        catalog = merge_collection(PILOT_PROJECT, None,
                                   {'Pordenone Pensa': batch}, '2026-10-07T08:00:00Z')
        rows = query_catalog(catalog, 45.95689, 12.66051, radius=20,
                             now=datetime.fromisoformat('2026-10-07T10:00:00+02:00'))['events']
        self.assertEqual(len(rows), 5)
        self.assertTrue(all('programme_id' not in e for e in rows))
        remaining, status = classify_post(programme_post(), today=date(2026, 11, 11))
        self.assertEqual(status, 'included')
        self.assertEqual([e['start_date'] for e in remaining], ['2026-11-17', '2026-11-24'])
        self.assertEqual(classify_post(programme_post(), today=date(2026, 11, 25)), ([], 'past'))

    def test_programme_conflicting_edition_remains_in_review(self):
        post = programme_post()
        post['title']['rendered'] = 'PordenonePensa Scienza 2026 dal 13 al 16 novembre'
        post['content']['rendered'] += '<h3>Gli appuntamenti di PordenonePensa Scienza 2025!</h3>'
        with self.assertRaisesRegex(ValueError, 'conflicting programme years'):
            classify_post(post, today=date(2026, 10, 25))
        valid = programme_post()
        valid['id'], valid['link'] = 3, 'https://www.pnpensa.it/programma-verificato/'
        batch = fixture(posts=[post, valid])
        gated = gate_batch('Pordenone Pensa', batch, today=date(2026, 10, 7))
        self.assertEqual(gated['status'], 'partial')
        self.assertEqual(len(gated['events']), 5)
        self.assertEqual(len(gated['review_required']), 1)

    def test_incomplete_or_ambiguous_session_never_publishes_partial_programme(self):
        changes = [
            (', ore 19', ''),
            ('Martedì 27 ottobre', 'Lunedì 27 ottobre'),
            ('Martedì 27 ottobre', 'Martedì 27 ottobre 2027'),
            ('ore 19', 'ore 25'),
            ('Pordenone, <a', 'Luogo ignoto, <a'),
            ('Incontro 1: Il rischio', 'Incontro 1 annullato'),
            ('</section>', ''),
        ]
        for before, after in changes:
            with self.subTest(change=(before, after)):
                post = programme_post()
                post['content']['rendered'] = post['content']['rendered'].replace(before, after, 1)
                with self.assertRaises(ValueError):
                    classify_post(post, today=date(2026, 10, 25))
        post = programme_post()
        post['content']['rendered'] += '<section><p>Martedì 27 ottobre</p><p>Altro incontro</p></section>'
        with self.assertRaisesRegex(ValueError, 'without verified time'):
            classify_post(post, today=date(2026, 10, 25))
        post = programme_post()
        post['content']['rendered'] += '<p>Nuova conferenza il 1 dicembre 2026.</p>'
        with self.assertRaisesRegex(ValueError, 'additional future date'):
            classify_post(post, today=date(2026, 10, 25))

    def test_unsupported_title_range_and_unrelated_layout(self):
        post = programme_post()
        post['title']['rendered'] = 'Programma dal 27 al 29 ottobre 2026'
        with self.assertRaisesRegex(ValueError, 'title date range needs review'):
            classify_post(post, today=date(2026, 10, 25))
        past = copy.deepcopy(PAST)
        past['content']['rendered'] = '<section><section><p>Resoconto della serata.</p></section></section>'
        self.assertEqual(classify_post(past, today=date(2026, 10, 25)), ([], 'past'))

    def test_programme_cannot_guess_year_from_publication(self):
        post = programme_post()
        post['content']['rendered'] = post['content']['rendered'].replace('edizione 2026', 'edizione')
        with self.assertRaisesRegex(ValueError, 'programme year not verified'):
            classify_post(post, today=date(2026, 10, 25))

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

    def test_reviewed_article_keeps_other_verified_card_live(self):
        changed = copy.deepcopy(POST)
        changed['content']['rendered'] += '<p>Il secondo incontro sarà il 3 novembre.</p>'
        valid = copy.deepcopy(POST)
        valid['id'] = 3
        valid['link'] = 'https://www.pnpensa.it/abc-finanza-verificata-2026/'
        batch = fixture(posts=[changed, PAST, valid])
        gated = gate_batch('Pordenone Pensa', batch,
                           today=date(2026, 10, 7))
        self.assertEqual(gated['status'], 'partial')
        self.assertEqual([event['url'] for event in gated['events']], [valid['link']])
        self.assertEqual(gated['review_required'][0]['url'], URL)
        damaged = copy.deepcopy(batch)
        damaged['verification']['sitemap_count'] -= 1
        self.assertEqual(gate_batch('Pordenone Pensa', damaged,
                                    today=date(2026, 10, 7))['status'], 'error')

    def test_only_future_article_can_be_quarantined_with_empty_catalog(self):
        changed = copy.deepcopy(POST)
        changed['content']['rendered'] += '<p>Il secondo incontro sarà il 3 novembre.</p>'
        batch = fixture(posts=[changed, PAST])
        gated = gate_batch('Pordenone Pensa', batch,
                           today=date(2026, 10, 7))
        self.assertEqual(gated['status'], 'partial')
        self.assertEqual(gated['events'], [])
        self.assertEqual(gated['review_required'][0]['url'], URL)

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
