import unittest
from datetime import date

from app.events.pilot_regional_year_exclusions import current_year_exclusion


TODAY = date(2026, 10, 5)


def detail(date_text, description):
    return ('<h1>Evento</h1><div class="body_col1"><h2>Descrizione</h2>'
            f'<p>{description}</p></div><div class="body_col2">'
            '<div style="background-image: url(icn__calendar.svg)">'
            f'{date_text}</div>'
            '<div style="background-image: url(icn__pin.svg)">Udine</div>'
            '</div><div class="c-detail__actions"></div>')


def entry(title='Evento', badges=None):
    return {'kind': 'calendar', 'candidate': {
        'title': title, 'listing_occurrences': badges or []}}


class RegionalYearExclusionTests(unittest.TestCase):
    def classify(self, date_text, description, *, title='Evento', badges=None):
        return current_year_exclusion(
            entry(title, badges), detail(date_text, description), today=TODAY)

    def test_cancelled_event_is_excluded_but_conditional_notice_is_not(self):
        cancelled = self.classify('10 ottobre 2026', 'EVENTO ANNULLATO! Non avrà luogo.',
                                  badges=['2026-10-10'])
        self.assertEqual(cancelled['reason'], 'explicit_cancellation')
        titled = self.classify('domenica 11 ottobre 2026',
                              'EVENTO ANNULLATO UP! - Peter Gabriel Tribute Show',
                              title='Up! Peter Gabriel - tribute show - ANNULLATO',
                              badges=['2026-10-11'])
        self.assertEqual(titled['reason'], 'explicit_cancellation')
        conditional = self.classify('10 ottobre 2026',
                                    'In caso di annullamento i biglietti saranno rimborsati.',
                                    badges=['2026-10-10'])
        self.assertIsNone(conditional)
        weather = self.classify('10 ottobre 2026',
                                'Evento annullato in caso di maltempo.',
                                badges=['2026-10-10'])
        self.assertIsNone(weather)

    def test_past_date_with_notice_and_future_badge_conflict(self):
        past = self.classify('Dal 14 al 18 dicembre 2022',
                             'Lo spettacolo è stato riprogrammato nel 2022.')
        self.assertEqual(past['reason'], 'explicit_detail_dates_past')
        conflicting = self.classify('Dal 14 al 18 dicembre 2022',
                                    'Lo spettacolo è stato riprogrammato nel 2022.',
                                    badges=['2026-10-10'])
        self.assertIsNone(conflicting)

    def test_yearless_weekday_can_only_rule_out_current_year(self):
        mismatch = self.classify('Martedì 13 dicembre ore 17:00',
                                 'Conferenza il martedì 13 dicembre.')
        self.assertEqual(mismatch['reason'], 'weekday_date_not_current_year')
        matching = self.classify('Venerdì 9 ottobre ore 20:30',
                                 'Presentazione il venerdì 9 ottobre.')
        self.assertIsNone(matching)

    def test_explicit_prior_edition_and_replacement_next_year(self):
        old = self.classify('Maggio a Moggio2023', 'Concerto corale.')
        self.assertEqual(old['reason'], 'explicit_prior_edition')
        moved = self.classify(
            'Venerdì 3 luglio 2026 RINVIATO A Giovedì 1° luglio 2027',
            'Il concerto è posticipato. Nuovo calendario: 1° luglio 2027.')
        self.assertEqual(moved['reason'], 'confirmed_replacement_next_year')
        unconfirmed = self.classify(
            'Venerdì 3 luglio 2026 RINVIATO A Giovedì 1° luglio 2027',
            'Il concerto è posticipato: data da confermare.')
        self.assertIsNone(unconfirmed)

    def test_past_opening_and_season_without_programme(self):
        opening = self.classify(
            'Ogni sabato e domenica dalle 16:00 alle 18:30',
            'Mostra. Inaugurazione DOMENICA 4 OTTOBRE, ore 18:00.',
            title='Inaugurazione mostra', badges=['2026-10-04'])
        self.assertEqual(opening['reason'], 'past_inauguration')
        ordinary_exhibit = self.classify(
            'Ogni sabato e domenica dalle 16:00 alle 18:30',
            'Mostra. Inaugurazione DOMENICA 4 OTTOBRE, ore 18:00.',
            title='Mostra', badges=['2026-10-04'])
        self.assertIsNone(ordinary_exhibit)
        unscheduled = self.classify('Estate 2026',
                                    'Vivere in piena armonia con la natura.',
                                    badges=['2026-06-01'])
        self.assertEqual(unscheduled['reason'],
                         'season_without_published_programme')
        scheduled = self.classify('Estate 2026',
                                  'Programma: 10 ottobre alle ore 16.',
                                  badges=['2026-06-01'])
        self.assertIsNone(scheduled)


if __name__ == '__main__':
    unittest.main()
