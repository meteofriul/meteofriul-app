import unittest
from datetime import date
import copy
import json
from app.events.pilot_verdi_pordenone import (
    ARCHIVE_SITEMAP, BASE, RECENT_SITEMAP, SITEMAP_INDEX,
    SEASON_TERMS_API, SEASON_SHOWS_API,
    canonical_listing_link, collect_verdi_pordenone, detail_media,
    parse_performances,
)
from app.events.pilot_source_policy import gate_batch


URL = BASE + '/spettacolo/prova/'
DETAIL = '''<meta property="og:image" content="https://teatroverdipordenone.it/wp-content/uploads/2026/10/prova.jpg">
<h1>Prova</h1><div class="article-dates"><p>20 Ottobre 2026 Ore 20:30</p><p>Sala Grande</p></div>
<div class="col-12 col-lg-9"><p>Programma musiche e interpreti della serata presentati sul palco del teatro.</p></div>
<div class="col-12 col-lg-9"><p>Uno spettacolo dedicato alla musica e alle storie dei suoi protagonisti,
con un racconto scenico che accompagna il pubblico attraverso la serata.</p></div>'''


class Response:
    status_code = 200
    def __init__(self, body, headers=None):
        self.body = body.encode()
        self.headers = headers or {}
    def __enter__(self):
        return self
    def __exit__(self, *args):
        return False
    def raise_for_status(self):
        pass
    def iter_content(self, _):
        yield self.body


def fixture():
    head = ('<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">' +
            ''.join(f'<sitemap><loc>{url}</loc></sitemap>'
                    for url in (ARCHIVE_SITEMAP, RECENT_SITEMAP)) +
            '</sitemapindex>')
    archive = ('<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">' +
               ''.join(f'<url><loc>{BASE}/spettacolo/passato-{n}/</loc>'
                       '<lastmod>2026-09-01T00:00:00+00:00</lastmod></url>'
                       for n in range(1000)) + '</urlset>')
    recent = ('<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
              f'<url><loc>{URL}</loc></url></urlset>')
    show_api = (f'{SEASON_SHOWS_API}?spettacolo_stagione=215&per_page=100&page=1'
                '&_fields=id,link,modified,spettacolo_stagione')
    pages = {SITEMAP_INDEX: head, ARCHIVE_SITEMAP: archive,
             RECENT_SITEMAP: recent,
             BASE + '/la-stagione/': f'<a href="{URL}">Prova</a>',
             URL: DETAIL,
             SEASON_TERMS_API: json.dumps([{'id': 215, 'name': 'Programmazione 2026/2027', 'count': 1}]),
             show_api: json.dumps([{'id': 123, 'link': URL, 'modified': '2026-10-01T12:00:00',
                                    'spettacolo_stagione': [215]}])}
    def get(url, **_):
        headers = {'X-WP-Total': '1', 'X-WP-TotalPages': '1'} if url in {
            SEASON_TERMS_API, show_api} else {}
        return Response(pages[url], headers)
    return collect_verdi_pordenone(get=get,
                                   today=date(2026, 10, 7))

class VerdiTests(unittest.TestCase):
    def test_ad_tag_on_pagination_is_removed_before_fetch(self):
        page = BASE + '/la-stagione/page/3/'
        self.assertEqual(canonical_listing_link(page + '?gclid=EAIaIQobChMIv7Lqy8Gz_QIVztnVCh0dSwdiEAAYASAAEgKsgPD_BwE'), page)
        self.assertEqual(canonical_listing_link(page), page)
        for query in ('?page=4', '?gclid=', '?gclid=abc&show=old', '#other'):
            with self.assertRaises(ValueError):
                canonical_listing_link(page + query)
        with self.assertRaises(ValueError):
            canonical_listing_link(URL + '?gclid=abc')

    def test_official_newsletter_tags_on_pagination_are_removed_before_fetch(self):
        page = BASE + '/la-stagione/page/4/'
        campaign = ('?utm_source=ActiveCampaign&utm_medium=email'
                    '&utm_content=Acquista+il+tuo+biglietto+per+la+programmazione+26%2F27'
                    '&utm_campaign=Newsletter+-+19_09+%28Copia%29')
        self.assertEqual(canonical_listing_link(page + campaign), page)
        for query in (campaign + '&page=5', campaign.replace('utm_medium=email', 'utm_medium=web'),
                      campaign.replace('utm_campaign=', 'utm_campaign=&utm_campaign='),
                      '?utm_source=ActiveCampaign&utm_medium=email',
                      '?utm_source=ActiveCampaign&utm_medium=email&utm_content=x&utm_campaign='):
            with self.subTest(query=query), self.assertRaises(ValueError):
                canonical_listing_link(page + query)
        with self.assertRaises(ValueError):
            canonical_listing_link(URL + campaign)

    def test_verified_spazio_due_keeps_two_hours(self):
        events = self.parse('<p>17 Aprile 2027 Ore 10:30</p><p>17 Aprile 2027 Ore 11:30</p><p>Spazio due</p>')
        self.assertEqual([e['time'] for e in events], ['10:30', '11:30'])
        self.assertTrue(all(e['event_city'] == 'Pordenone' for e in events))
    def parse(self, body):
        return parse_performances('<h1>Concerto</h1><div class="article-dates">' + body + '</div>',
                                  'https://teatroverdipordenone.it/spettacolo/test/', today=date(2026, 9, 6))

    def test_separate_performances(self):
        events = self.parse('<p>13 Settembre 2026 Ore 20:30</p><p>14 Settembre 2026 Ore 18:00</p><p>Sala Grande</p>')
        self.assertEqual(len(events), 2)
        self.assertEqual(events[1]['start_date'], '2026-09-14')
        self.assertEqual(events[0]['location_confidence'], 'municipality')

    def test_no_year_guess(self):
        with self.assertRaises(ValueError):
            self.parse('<p>13 Settembre Ore 20:30</p><p>Sala Grande</p>')

    def test_unknown_room_not_assumed(self):
        with self.assertRaises(ValueError):
            self.parse('<p>13 Settembre 2026 Ore 20:30</p><p>Teatro esterno</p>')

    def test_past_filtered(self):
        self.assertEqual(self.parse('<p>1 Settembre 2026 Ore 20:30</p><p>Sala Grande</p>'), [])

    def test_past_external_venue_does_not_block_current_season(self):
        self.assertEqual(self.parse('<p>22 Luglio 2026 Ore 21:00</p><p>Piazzetta Pescheria</p>'), [])

    def test_official_detail_supplies_narrative_and_image(self):
        media = detail_media(DETAIL, url=URL, title='Prova')
        self.assertEqual(media['image'],
                         BASE + '/wp-content/uploads/2026/10/prova.jpg')
        self.assertIn('Uno spettacolo', media['description_excerpt'])
        self.assertEqual(media['description_source_url'], URL)

    def test_collector_reconciles_recent_sitemap_and_gate(self):
        batch = fixture()
        proof = batch['verification']
        self.assertEqual((proof['listing_count'], proof['season_api_count'],
                          proof['recent_sitemap_count'],
                          proof['archive_sitemap_count'], proof['detail_count']),
                         (1, 1, 1, 1000, 1))
        self.assertEqual(gate_batch('Teatro Verdi Pordenone', batch,
                                    today=date(2026, 10, 7))['status'], 'ok')
        damaged = copy.deepcopy(batch)
        damaged['verification']['detail_count'] = 0
        self.assertEqual(gate_batch('Teatro Verdi Pordenone', damaged,
                                    today=date(2026, 10, 7))['status'], 'error')
        damaged = copy.deepcopy(batch)
        damaged['verification']['season_api_urls'] = []
        self.assertEqual(gate_batch('Teatro Verdi Pordenone', damaged,
                                    today=date(2026, 10, 7))['status'], 'error')

    def test_disappeared_future_replica_blocks_refresh(self):
        batch = fixture()
        prior = copy.deepcopy(batch['events'][0])
        prior['start_date'] = prior['end_date'] = '2026-10-21'
        failed = gate_batch('Teatro Verdi Pordenone', batch,
                            today=date(2026, 10, 7),
                            previous_batch={'events': [prior]})
        self.assertEqual(failed['error_type'], 'source_verification_failed')
