import unittest
from datetime import date, datetime
from app.events.pilot_css import parse_css
from app.events.pilot_pnpensa import parse_programme
from app.events.pilot_verdi_trieste import parse_calendar, explicit_slots
from app.events.pilot_catalog import merge_collection, query_catalog, PILOT_PROJECT

class ProgrammeTests(unittest.TestCase):
    def test_css_pairs_each_date_with_its_own_town(self):
        html = ('<h1>Presentazioni</h1><p class="venue"> | Udine, Cervignano, San Giorgio di Nogaro<span>'
                'giovedì 24 settembre 2026 ore 17-19<br>Udine, Teatro S. Giorgio<br>'
                'venerdì 25 settembre 2026 ore 17-19<br>Cervignano del Friuli, Teatro Pasolini<br>'
                'venerdì 2 ottobre 2026 ore 17-19<br>S. Giorgio di Nogaro, Biblioteca Villa Dora</span></p>')
        events = parse_css(html, '', today=date(2026,9,7))
        self.assertEqual([e['event_city'] for e in events], ['Udine', 'Cervignano del Friuli', 'San Giorgio di Nogaro'])
        self.assertEqual([e['start_date'] for e in events], ['2026-09-24', '2026-09-25', '2026-10-02'])
        self.assertEqual(len({(e['lat'], e['lon']) for e in events}), 3)
        self.assertEqual(events[2]['venue'], 'Biblioteca Villa Dora')

    def test_css_rejects_unpaired_multitown_programme(self):
        with self.assertRaisesRegex(ValueError, 'unpaired'):
            parse_css('<h1>Test</h1><p class="venue"> | Udine, Cervignano<span>24 settembre 2026 ore 17-19<br>Udine, Teatro<br>25 settembre 2026 ore 17-19</span></p>', '', today=date(2026,9,7))

    def test_css_dot_clock_and_course_hours(self):
        for schedule, expected in [('5 - 6 febbraio 2027 ore 20.30', [('20:30', None), ('20:30', None)]),
                                   ('venerdì 22 gennaio 2027 - dalle ore 16 alle 19', [('16:00', '19:00')])]:
            html = '<h1>Test</h1><p class="venue">Udine | Teatro<span>' + schedule + '</span></p>'
            result = parse_css(html, '', today=date(2026,9,7))
            self.assertEqual([(e['time'], e.get('end_time')) for e in result], expected)

    def test_css_does_not_guess_overnight_or_missing_year(self):
        for schedule in ('22 gennaio 2027 ore 19-16', 'aperta fino al 19 settembre'):
            with self.assertRaises(ValueError):
                parse_css('<h1>Test</h1><p class="venue">Udine | Teatro<span>' + schedule + '</span></p>', '', today=date(2026,9,7))

    def test_css_explicit_conjunction_dates_from_live_format(self):
        html = '<h1>Spettacolo</h1><p class="venue">Udine | Teatro<span>11 e 12 settembre 2026 ore 20:30</span></p>'
        result = parse_css(html, 'https://www.cssudine.it/test', today=date(2026,9,7))
        self.assertEqual([e['start_date'] for e in result], ['2026-09-11', '2026-09-12'])
        self.assertTrue(all(e['time'] == '20:30' for e in result))

    def test_css_cancelled_detail_requires_review(self):
        detail = '<h1>Prova annullata</h1><p class="venue">Udine | Teatro<span>7 novembre 2026 ore 20:30</span></p>'
        with self.assertRaisesRegex(ValueError, 'schedule_change_requires_review'):
            parse_css(detail, 'https://www.cssudine.it/stagione-contatto/2026/123/prova',
                      today=date(2026, 9, 6))

    def test_trieste_does_not_invent_replica_times(self):
        html = '<h2 class="spettacolo-list-title"><a href="https://www.teatroverdi-trieste.com/it/spettacoli/test/">Concerto</a></h2><span class="spettacolo-list-date">Domenica 20 settembre 2026 ore 18.00</span>'
        result = parse_calendar(html, today=date(2026,9,6))
        self.assertEqual(result['events'][0]['time'], '18:00')
        result = parse_calendar(html.replace('Domenica 20', '20, 21'), today=date(2026,9,6))
        self.assertEqual(len(result['events']), 2)
        self.assertEqual(len(result['review_required']), 0)

    def test_trieste_discontinuous_dates_without_inventing_hours(self):
        days, hour = explicit_slots('29, 30 settembre, 2, 3, 4, 6, 7, 8, 9, 10 ottobre 2026')
        self.assertEqual(len(days), 10)
        self.assertNotIn(date(2026,10,1), days)
        self.assertIsNone(hour)
        self.assertEqual(explicit_slots('sabato 28 e domenica 29 novembre 2026 ore 18.00')[1], '18:00')

    def test_trieste_rejects_ranges_and_ambiguous_year(self):
        for text in ('29-30 settembre 2026', '31 dicembre, 2 gennaio 2027', '30 febbraio 2027', '12 novembre'):
            with self.assertRaises(ValueError):
                explicit_slots(text)

    def test_css_multiline_schedule(self):
        html = '<h1>Prova</h1><p class="venue">Udine | Teatro<span>7 novembre 2026 ore 20:30<br />8 novembre 2026 ore 17:00</span></p>'
        self.assertEqual(len(parse_css(html, '', today=date(2026,9,6))), 2)
    def test_css_explicit_replicas(self):
        html = '<h1>Prova</h1><p class="venue">Udine | Teatro<span>17-18-19 dicembre 2026 ore 21:00</span></p>'
        events = parse_css(html, 'https://www.cssudine.it/prova', today=date(2026,9,6))
        self.assertEqual([e['start_date'] for e in events], ['2026-12-17','2026-12-18','2026-12-19'])

    def test_css_no_year_guess(self):
        with self.assertRaises(ValueError):
            parse_css('<h1>Prova</h1><p class="venue">Udine | Teatro<span>17 dicembre ore 21:00</span></p>', '', today=date(2026,9,6))

    def test_pensa_explicit_edition(self):
        html = '<h2>Pordenone 2026</h2><h4>Domenica 6 settembre<br>ore 18.30 Sala, in caso di maltempo Auditorium</h4><h3>Incontro</h3>'
        events = parse_programme(html, today=date(2026,9,6))['events']
        self.assertEqual(events[0]['time'], '18:30')
        self.assertIn('maltempo', events[0]['place'])
        self.assertEqual(events[0]['location_confidence'], 'municipality')
        self.assertEqual(events[0]['programme_id'], 'pordenone-pensa-in-giallo-2026')
        self.assertEqual(events[0]['programme_role'], 'session')

    def test_pensa_wrong_edition_rejected(self):
        with self.assertRaises(ValueError):
            parse_programme('<h2>Pordenone 2025</h2>', today=date(2026,9,6))

    def test_pensa_sessions_are_one_edition_card(self):
        html = ('<h2>Pordenone 2026</h2>'
                '<h4>Domenica 6 settembre ore 18.30 Sala A</h4><h3>Incontro A</h3>'
                '<h4>Lunedì 7 settembre ore 20.30 Sala B</h4><h3>Incontro B</h3>')
        batch = parse_programme(html, today=date(2026,9,6))
        catalog = merge_collection(PILOT_PROJECT, None, {"Pordenone Pensa": batch},
                                   "2026-09-06T08:00:00Z")
        result = query_catalog(catalog, batch['events'][0]['lat'], batch['events'][0]['lon'],
                               now=datetime.fromisoformat("2026-09-06T08:00:00Z"))
        self.assertEqual(len(result['events']), 1)
        programme = result['events'][0]
        self.assertEqual(programme['title'], 'Pordenone Pensa in Giallo 2026')
        self.assertEqual(programme['start_date'], '2026-09-05')
        self.assertEqual(programme['end_date'], '2026-09-07')
        self.assertEqual(programme['active_session_count'], 2)
        self.assertNotIn('session_count', programme)
        self.assertEqual(programme['venue'], 'Più sedi')
