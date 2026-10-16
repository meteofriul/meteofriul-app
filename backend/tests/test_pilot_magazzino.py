"""Magazzino cards require complete API, sitemap, year and detail agreement."""
from datetime import date
import json
import unittest

from app.events.pilot_magazzino import collect_magazzino, event_url
from app.events.pilot_source_policy import gate_batch


BASE = 'https://magazzinodelleidee.it'
URL = BASE + '/evento/ila-beka-fotoni/'


class Response:
    status_code = 200
    def __init__(self, body, headers=None):
        self.body = body.encode('utf-8') if isinstance(body, str) else body
        self.headers = headers or {}
    def __enter__(self): return self
    def __exit__(self, *_): return None
    def raise_for_status(self): return None
    def iter_content(self, *_): yield self.body


def row(*, content=None):
    return {
        'id': 15505, 'status': 'publish', 'type': 'evento', 'link': URL,
        'title': {'rendered': 'Ila Bêka'},
        'content': {'rendered': content or (
            '<h2>Fotoni</h2><h2>27.06-11.10.2026</h2>'
            '<p>Dal 27 giugno all’11 ottobre 2026 il Magazzino delle Idee '
            'di Trieste ospita la mostra fotografica di Ila Bêka.</p>')},
        'featured_media': 0, 'modified': '2026-06-16T17:03:57',
        '_embedded': {'wp:term': [[{'taxonomy': 'anno', 'name': '2026'},
                                   {'taxonomy': 'tipologia', 'name': 'Mostra'}]]},
    }


def sitemap(*urls):
    return ('<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
            + ''.join(f'<url><loc>{url}</loc></url>' for url in urls)
            + '</urlset>')


def fake_get(record, *, archive=None, sitemap_text=None, mostre=None,
             eventi=None, detail=None):
    body = record['content']['rendered']
    pages = {
        BASE + '/anno/2026/': archive if archive is not None else
            f'<main><a href="{URL}">Ila Bêka</a></main>',
        BASE + '/evento-sitemap.xml': sitemap_text if sitemap_text is not None else sitemap(URL),
        BASE + '/mostre/': mostre if mostre is not None else
            f'<main><h1>ILA BÊKA FOTONI</h1><p>Dal 27.06 -11.10.2026</p>'
            f'<a href="{URL}">Scopri di più</a></main>',
        BASE + '/eventi/': eventi if eventi is not None else
            f'<main><a href="{URL}">Fotoni</a></main>',
        URL: detail if detail is not None else '<h1>Ila Bêka</h1>' + body,
    }

    def get(url, **_):
        if '/wp-json/' in url:
            return Response(json.dumps([record]),
                            {'X-WP-Total': '1', 'X-WP-TotalPages': '1'})
        return Response(pages[url])
    return get


class MagazzinoPilotTests(unittest.TestCase):
    today = date(2026, 10, 7)

    def test_complete_source_has_a_dated_exhibition_and_excerpt(self):
        batch = collect_magazzino(get=fake_get(row()), today=self.today)
        accepted = gate_batch('Magazzino delle Idee', batch, today=self.today)
        self.assertEqual(accepted['status'], 'ok')
        self.assertEqual(len(accepted['events']), 1)
        event = accepted['events'][0]
        self.assertEqual(event['title'], 'Ila Bêka - Fotoni')
        self.assertEqual((event['start_date'], event['end_date']),
                         ('2026-06-27', '2026-10-11'))
        self.assertEqual(event['event_city'], 'Trieste')
        self.assertTrue(event['description_excerpt'])
        self.assertEqual(accepted['verification']['exhibition_dates_checked'], 1)

    def test_sitemap_or_year_archive_omission_stops_source(self):
        with self.assertRaisesRegex(ValueError, 'sitemap/API mismatch'):
            collect_magazzino(get=fake_get(row(), sitemap_text=sitemap()),
                              today=self.today)
        with self.assertRaisesRegex(ValueError, 'archive/API mismatch'):
            collect_magazzino(get=fake_get(row(), archive='<main></main>'),
                              today=self.today)

    def test_official_detail_date_disagreement_stops_source(self):
        bad = ('<h1>Ila Bêka</h1><h2>Fotoni</h2><h2>27.06-12.10.2026</h2>'
               '<p>Dal 27 giugno all’11 ottobre 2026 il Magazzino delle Idee '
               'di Trieste ospita la mostra fotografica di Ila Bêka.</p>')
        batch = collect_magazzino(get=fake_get(row(), detail=bad), today=self.today)
        self.assertEqual(batch['status'], 'error')
        self.assertEqual(batch['review_required'][0]['reason'],
                         'detail date or text mismatch')

    def test_visible_exhibition_date_disagreement_stops_source(self):
        mostre = (f'<h1>ILA BÊKA FOTONI</h1><p>Dal 27.06 -12.10.2026</p>'
                  f'<a href="{URL}">Scopri di più</a>')
        batch = collect_magazzino(get=fake_get(row(), mostre=mostre),
                                  today=self.today)
        self.assertEqual(batch['status'], 'error')
        self.assertEqual(batch['review_required'][0]['reason'],
                         'exhibition listing date or title mismatch')

    def test_missing_venue_or_public_listing_stops_source(self):
        invalid = row(content='<h2>Fotoni</h2><h2>27.06-11.10.2026</h2>'
                      '<p>Una mostra fotografica di lunga durata con oltre '
                      'trecento fotografie inedite da una collezione privata.</p>')
        batch = collect_magazzino(get=fake_get(invalid), today=self.today)
        self.assertEqual(batch['status'], 'error')
        self.assertEqual(batch['verification']['review_count'], 1)
        with self.assertRaisesRegex(ValueError, 'public list/API mismatch'):
            collect_magazzino(get=fake_get(
                row(), mostre='<main></main>', eventi='<main></main>'),
                today=self.today)

    def test_disappearing_future_event_fails_gate(self):
        batch = collect_magazzino(get=fake_get(row()), today=self.today)
        old = {**batch['events'][0], 'url': BASE + '/evento/other/',
               'start_date': '2026-12-01', 'end_date': '2026-12-01'}
        self.assertEqual(gate_batch('Magazzino delle Idee', batch, today=self.today,
                                    previous_batch={'events': [old]})['status'], 'error')

    def test_untrusted_url_rejected(self):
        self.assertIsNone(event_url('https://magazzinodelleidee.it.evil.test/evento/x/'))


if __name__ == '__main__':
    unittest.main()
