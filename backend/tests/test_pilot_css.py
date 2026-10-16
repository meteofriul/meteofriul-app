import copy
import unittest
from datetime import date

from app.events.pilot_css import (
    BASE, SEASON_PATHS, collect_css, detail_excerpt, detail_image,
    parse_css, past_schedule, season_cards,
)
from app.events.pilot_source_policy import gate_batch


URL = 'https://www.cssudine.it/stagione-contatto/2026/123/prova'
CARD = '''<div class="news-v1"><span class="venue">Udine | Teatro Palamostre</span>
<span class="data">9 e 10 ottobre 2026 ore 20:30</span>
<h3><a href="/stagione-contatto/2026/123/prova">Prova</a></h3></div>'''
DETAIL = '''<p class="venue">Udine | Teatro Palamostre
<span>9 e 10 ottobre 2026 ore 20:30</span></p>
<img alt="Prova <br /> teatro" class="img-responsive"
src="/media/spettacoli/123_456_icona.jpg">
<div class="col-sm-8 dx"><h1>Prova</h1>
<p>Uno spettacolo che racconta una storia di famiglia attraverso la musica,
la scena e le parole degli attori, con incontri e momenti inattesi.</p></div>'''


class Response:
    status_code = 200
    def __init__(self, content):
        self.content = content
    def __enter__(self):
        return self
    def __exit__(self, *args):
        return False
    def raise_for_status(self):
        pass
    def iter_content(self, _):
        yield self.content.encode('utf-8')


def fixture(detail=DETAIL):
    pages = {BASE + path: CARD for path in SEASON_PATHS}
    pages[URL] = detail
    return collect_css(get=lambda url, **_: Response(pages[url]),
                       today=date(2026, 10, 7))


class CSSAuditTests(unittest.TestCase):
    def test_season_cards_ignore_unrelated_links(self):
        cards = season_cards('<a href="/stagione-contatto/2026/123/alternate-slug">Press</a>' +
                             '<div class="news-v1"><h3><a href="/produzioni/123/test">Test</a></h3></div>' +
                             CARD)
        self.assertEqual(len(cards), 1)
        self.assertEqual(cards[0]['url'], URL)

    def test_event_link_outside_cards_requires_review(self):
        with self.assertRaisesRegex(ValueError, 'missing from season cards'):
            season_cards('<a href="/stagione-contatto/2026/999/new-show">Show</a>' + CARD)

    def test_collector_checks_unlisted_link_dates_before_accepting_inventory(self):
        old_url = 'https://www.cssudine.it/stagione-contatto/2026/2863/old-show'
        other_url = 'https://www.cssudine.it/stagione-contatto/2026/999/new-show'
        linked = '<a href="/stagione-contatto/2026/2863/old-show">Past show</a>'
        pages = {BASE + path: CARD for path in SEASON_PATHS}
        pages[BASE] = linked + CARD
        pages[URL] = DETAIL
        pages[old_url] = '<h1>Past show</h1><p class="venue">Udine | Teatro<span>9 e 10 ottobre 2026 ore 20:30</span></p>'
        result = collect_css(get=lambda url, **_: Response(pages[url]),
                             today=date(2026, 10, 11))
        self.assertEqual(result['verification']['past_unlisted_links'], 1)
        self.assertTrue(result['verification']['source_complete'])
        pages[BASE] = pages[BASE].replace('/2863/old-show', '/999/new-show')
        pages[other_url] = pages[old_url].replace('9 e 10 ottobre', '12 ottobre')
        with self.assertRaisesRegex(ValueError, 'missing from season cards'):
            collect_css(get=lambda url, **_: Response(pages[url]),
                        today=date(2026, 10, 11))

    def test_cervignano_and_date_only_school_ranges(self):
        html = '''<h1>La foresta</h1><p class="venue">Cervignano | Teatro Pasolini
        <span>23-24 novembre 2026</span></p>'''
        events = parse_css(html, URL, today=date(2026, 10, 7))
        self.assertEqual([event['start_date'] for event in events],
                         ['2026-11-23', '2026-11-24'])
        self.assertEqual({event['event_city'] for event in events},
                         {'Cervignano del Friuli'})
        self.assertTrue(all('time' not in event for event in events))

    def test_cross_month_and_season_year_are_explicitly_bounded(self):
        cross = '<h1>Prova</h1><p class="venue">Udine | Teatro<span>30 novembre - 1-2 dicembre 2026</span></p>'
        self.assertEqual([event['start_date'] for event in parse_css(
            cross, URL, today=date(2026, 10, 7))],
            ['2026-11-30', '2026-12-01', '2026-12-02'])
        yearless = '<h1>Laboratorio</h1><p class="venue">Udine | Teatro<span>dal 22 al 27 febbraio</span></p>'
        with self.assertRaisesRegex(ValueError, 'year not explicit'):
            parse_css(yearless, URL, today=date(2026, 10, 7))
        events = parse_css(yearless, URL, today=date(2026, 10, 7),
                           season_year=2026)
        self.assertEqual((events[0]['start_date'], events[-1]['start_date']),
                         ('2027-02-22', '2027-02-27'))
        self.assertIn('stagione 2026/2027', events[0]['date_evidence'])

    def test_new_unyeared_opening_date_is_not_silently_ignored(self):
        html = '''<h1>Laboratorio</h1><p class="venue">Udine | Teatro<span>
        12 ottobre 2026 ore 18<br>giovedì 15 ottobre ore 21 apertura al pubblico
        </span></p>'''
        with self.assertRaises(ValueError):
            parse_css(html, URL, today=date(2026, 10, 7))

    def test_past_classification_does_not_hide_later_unyeared_date(self):
        schedule = '1 ottobre 2026 ore 18, 12 novembre ore 20'
        self.assertFalse(past_schedule(schedule, today=date(2026, 10, 7),
                                       season_year=2026))

    def test_official_detail_supplies_attributed_preview_and_image(self):
        self.assertEqual(detail_image(DETAIL),
                         'https://www.cssudine.it/media/spettacoli/123_456_icona.jpg')
        excerpt = detail_excerpt(DETAIL, url=URL, title='Prova')
        self.assertIn('Uno spettacolo', excerpt['description_excerpt'])
        self.assertEqual(excerpt['description_source_url'], URL)

    def test_schedule_paragraph_keeps_prose_and_never_uses_newsletter(self):
        html = '''<div class="col-sm-8 dx"><h1>Luz de luna</h1>
        <p><strong>mercoledì 6 gennaio 2027 ore 17<br></strong>
        Udine, Teatro Palamostre<br><br>
        Nel riparo intimo di una piccola stanza colorata la quotidianità vibra
        di particolari e racconta una storia attraverso il circo e la musica.</p>
        </div><p>Iscriviti al servizio newsletter: le notizie verranno inviate
        direttamente al tuo indirizzo email.</p>'''
        excerpt = detail_excerpt(html, url=URL, title='Luz de luna')
        self.assertTrue(excerpt['description_excerpt'].startswith('Nel riparo intimo'))
        self.assertNotIn('newsletter', excerpt['description_excerpt'])
        date_only = html.replace('Nel riparo intimo di una piccola stanza colorata la quotidianità vibra\n        di particolari e racconta una storia attraverso il circo e la musica.', '')
        self.assertEqual(detail_excerpt(date_only, url=URL, title='Luz de luna'), {})

        dated_range = '''<div class="col-sm-8 dx"><h1>Sapiens</h1>
        <p>18 settembre - 3 ottobre 2026 ore 19:00<br>Cervignano,
        Teatro Pasolini<br><br>Dopo Il labirinto di Orfeo, il CSS propone
        un'esperienza teatrale che intreccia realtà aumentata e virtuale
        e affronta le trasformazioni dell'umanità.</p></div>'''
        preview = detail_excerpt(dated_range, url=URL, title='Sapiens')
        self.assertTrue(preview['description_excerpt'].startswith('Dopo Il labirinto'))

    def test_collector_reconciles_six_surfaces_and_gate(self):
        batch = fixture()
        proof = batch['verification']
        self.assertEqual(proof['listing_count'], 1)
        self.assertEqual(proof['detail_count'], 1)
        self.assertEqual(proof['included_detail_urls'], 1)
        self.assertEqual(len(batch['events']), 2)
        self.assertEqual(gate_batch('CSS Udine', batch,
                                    today=date(2026, 10, 7))['status'], 'ok')
        damaged = copy.deepcopy(batch)
        damaged['verification']['detail_count'] = 0
        self.assertEqual(gate_batch('CSS Udine', damaged,
                                    today=date(2026, 10, 7))['status'], 'error')
        boilerplate = copy.deepcopy(batch)
        boilerplate['events'][0]['description_excerpt'] = (
            'Iscriviti al servizio newsletter: le notizie verranno inviate '
            'direttamente al tuo indirizzo email.')
        self.assertEqual(gate_batch('CSS Udine', boilerplate,
                                    today=date(2026, 10, 7))['status'], 'error')

    def test_changed_detail_and_disappeared_future_date_fail_closed(self):
        wrong = fixture(DETAIL.replace('9 e 10 ottobre', '11 ottobre'))
        self.assertEqual(len(wrong['review_required']), 1)
        self.assertEqual(gate_batch('CSS Udine', wrong,
                                    today=date(2026, 10, 7))['status'], 'error')
        good = fixture()
        prior = copy.deepcopy(good['events'][0])
        prior['start_date'] = prior['end_date'] = '2026-10-11'
        failed = gate_batch('CSS Udine', good, today=date(2026, 10, 7),
                            previous_batch={'events': [prior]})
        self.assertEqual(failed['error_type'], 'source_verification_failed')


if __name__ == '__main__':
    unittest.main()
