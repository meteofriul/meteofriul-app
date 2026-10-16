import unittest
from datetime import date
from app.events.pilot_schedule import schedule_notice
from app.events.pilot_css import parse_css
from app.events.pilot_pnpensa import parse_programme as pensa
from app.events.pilot_pordenonelegge import parse_programme as legge
from app.events.pilot_verdi_trieste import parse_calendar
from app.events.pilot_verdi_pordenone import parse_performances, VenueReviewRequired
from app.events.pilot_azalea import parse_event, ScheduleReviewRequired
from tests.test_pilot_pordenonelegge import card, page


class ScheduleTests(unittest.TestCase):
    def test_notice_variants(self):
        for text in ('ANNULLATO', 'repliche rinviate', 'sospeso', 'nuova data', 'cambio di sede', 'riprogrammato'):
            with self.subTest(text=text):
                self.assertTrue(schedule_notice(text))
        self.assertFalse(schedule_notice('Prenotazione obbligatoria. In caso di maltempo in auditorium.'))
        self.assertFalse(schedule_notice('Sospeso in caso di condizioni meteo avverse.'))
        self.assertFalse(schedule_notice('In caso di maltempo l’evento sarà annullato.'))
        self.assertFalse(schedule_notice('La scena è sospesa tra realtà e fantasia.'))
        self.assertFalse(schedule_notice('Hanno cancellato e ridisegnato il testo.'))
        self.assertFalse(schedule_notice('Le visite sono sospese durante le funzioni religiose.'))
        self.assertTrue(schedule_notice('Le visite sono sospese fino a nuova comunicazione.'))

    def test_legge_isolates_cancelled_session(self):
        result = legge(page(card().replace('Riservato alle scuole', 'Incontro annullato') + card('11:00')))
        self.assertEqual([e['time'] for e in result['events']], ['11:00'])
        self.assertEqual(len(result['review_required']), 1)

    def test_pensa_isolates_changed_session(self):
        result = pensa('<h2>Pordenone 2026</h2><h4>6 settembre ore 18.30 Sala</h4><h3>Incontro rinviato</h3>'
                       '<h4>7 settembre ore 18.30 Sala</h4><h3>Altro incontro</h3>', today=date(2026, 9, 6))
        self.assertEqual(len(result['events']), 1)
        self.assertEqual(len(result['review_required']), 1)

    def test_trieste_title_notice(self):
        result = parse_calendar('<h2 class="spettacolo-list-title"><a href="https://www.teatroverdi-trieste.com/it/spettacoli/test/">Concerto sospeso</a></h2>'
                                '<span class="spettacolo-list-date">20 settembre 2026 ore 18.00</span>', today=date(2026,9,6))
        self.assertEqual(result['events'], [])
        self.assertEqual(len(result['review_required']), 1)

    def test_css_stops_changed_schedule(self):
        with self.assertRaisesRegex(ValueError, 'schedule_change'):
            parse_css('<h1>Prova rinviata</h1><p class="venue">Udine | Teatro<span>7 novembre 2026 ore 20:30</span></p>', '', today=date(2026,9,6))

    def test_verdi_pordenone_stops_notice(self):
        with self.assertRaises(VenueReviewRequired):
            parse_performances('<h1>Concerto annullato</h1><div class="article-dates"><p>Sala grande</p><p>20 settembre 2026 Ore 18.00</p></div>', '', today=date(2026,9,6))

    def test_azalea_stops_suspension(self):
        with self.assertRaises(ScheduleReviewRequired):
            parse_event('<h1>Concerto</h1><div class="single-event-date">'
                        '20.09.2026 21:00 h</div><div class="single-event-city">'
                        '<strong>Udine</strong></div><h2>luogo</h2><p>Teatro</p>'
                        '<div class="single-event-text">Spettacolo sospeso</div>',
                        'https://www.azalea.it/eventi/prova/', today=date(2026,9,6))
