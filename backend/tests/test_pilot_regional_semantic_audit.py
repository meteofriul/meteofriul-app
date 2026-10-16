import unittest
from datetime import date

from app.events.pilot_regional_semantic_audit import (
    create_snapshot, explicit_days, interpret_schedule,
)


class RegionalSemanticAuditTests(unittest.TestCase):
    today = date(2026, 10, 5)

    def interpret(self, detail_date, description, badges=()):
        return interpret_schedule(detail_date, description, badges,
                                  today=self.today)

    def test_weekend_dates_are_read_without_filling_the_range(self):
        result = self.interpret(
            '9 ottobre 2026 - 18 ottobre 2026',
            'I festeggiamenti si svolgeranno nei weekend 9-10-11 e 16-17-18 ottobre 2026.',
            ['2026-10-09', '2026-10-18'])
        self.assertEqual(result['status'], 'resolved_explicit_dates')
        self.assertEqual(result['occurrences'], [
            '2026-10-09', '2026-10-10', '2026-10-11',
            '2026-10-16', '2026-10-17', '2026-10-18'])

    def test_badge_not_in_detail_programme_is_quarantined(self):
        result = self.interpret(
            '8 ottobre 2026 - 18 ottobre 2026',
            'GIOVEDÌ 8 ottobre. VENERDÌ 9 ottobre. SABATO 10 ottobre. '
            'VENERDÌ 16 ottobre. SABATO 17 ottobre. DOMENICA 18 ottobre.',
            ['2026-10-11'])
        self.assertEqual(result['status'], 'review_required')
        self.assertEqual(result['reason'], 'badge_not_in_explicit_programme')

    def test_dated_headings_do_not_prove_an_exhaustive_programme(self):
        result = self.interpret(
            '2 ottobre 2026 - 11 ottobre 2026',
            'Da sabato 3 a domenica 11 ottobre la mostra è visitabile. '
            'L’inaugurazione è venerdì 2 ottobre. Orari di visita tutti i giorni.')
        self.assertEqual(result['status'], 'review_required')
        self.assertEqual(result['reason'], 'programme_not_explicit_or_complete')

    def test_unfinished_programme_is_quarantined_even_with_dates(self):
        result = self.interpret(
            '28 novembre 2026 - 20 dicembre 2026',
            'In fase di programmazione. Giornate: 28 e 29 novembre, '
            '6 e 8 dicembre. Programma disponibile dal 1 novembre.')
        self.assertEqual(result['reason'], 'programme_change_or_unfinished')

    def test_open_weekdays_are_not_expanded_to_all_calendar_days(self):
        result = self.interpret(
            '4 settembre 2026 - 31 ottobre 2026',
            'La mostra è visitabile da lunedì a sabato dalle 9 alle 19.')
        self.assertEqual(result['status'], 'resolved_weekly_opening')
        self.assertEqual(result['open_weekdays'], list(range(6)))

    def test_ambiguous_or_misspelled_date_group_is_quarantined(self):
        dates, reason = explicit_days(
            'Tre weekend: 3-4 ottobre, 10-11 ottobre, 17-18 ottorbe e 25 ottobre.',
            start=date(2026, 10, 3), end=date(2026, 10, 25))
        self.assertEqual(dates, [])
        self.assertEqual(reason, 'unparsed_day_group')
        dates, reason = explicit_days(
            'Calendario aperture: 17 ottorbe e 18 ottobre.',
            start=date(2026, 10, 17), end=date(2026, 10, 18))
        self.assertEqual((dates, reason), ([], 'unparsed_day_group'))
        dates, reason = explicit_days(
            'I weekend 9-12 ottobre.', start=date(2026, 10, 9),
            end=date(2026, 10, 12))
        self.assertEqual((dates, reason), ([], 'ambiguous_day_group'))

    def test_historical_biography_date_is_not_a_current_programme_day(self):
        dates, reason = explicit_days(
            'Venerdì 23 ottobre incontro sulla fotografa, nata il 16 agosto 1896. '
            'Venerdì 30 ottobre secondo incontro.',
            start=date(2026, 10, 23), end=date(2026, 10, 30))
        self.assertEqual(dates, ['2026-10-23', '2026-10-30'])
        self.assertIsNone(reason)
        dates, reason = explicit_days(
            'Venerdì 23 ottobre 2027 secondo incontro.',
            start=date(2026, 10, 23), end=date(2026, 10, 30))
        self.assertEqual((dates, reason), ([], 'day_year_outside_bounds'))

    def test_explicit_opening_range_covers_intermediate_badges(self):
        description = (
            'Vernissage sabato 17 ottobre. La mostra è visitabile nei seguenti '
            'orari: domenica 18 ottobre dalle 10 alle 20, da lunedì 19 ottobre '
            'a giovedì 22 ottobre dalle 16 alle 20. Finissage venerdì 23 ottobre.')
        result = self.interpret('17 ottobre 2026 - 23 ottobre 2026', description,
                                badges=[f'2026-10-{day:02}' for day in range(17, 24)])
        self.assertNotEqual(result['reason'], 'badge_not_in_explicit_programme')

    def test_excursion_dates_override_unrelated_gallery_opening_hours(self):
        description = (
            'La mostra è visitabile fino al 18 ottobre. Le escursioni si '
            'terranno venerdì 18 settembre, venerdì 25 settembre e sabato '
            '17 ottobre 2026. La galleria è aperta venerdì dalle 16 alle 19.')
        result = self.interpret('18 settembre 2026 - 17 ottobre 2026',
                                description, ['2026-09-18', '2026-09-25',
                                              '2026-10-17'])
        self.assertEqual(result['reason'], 'anchored_excursion_programme')
        self.assertEqual(result['occurrences'],
                         ['2026-09-18', '2026-09-25', '2026-10-17'])

    def test_other_excursions_are_separate_from_single_event(self):
        description = ('Sabato 10 ottobre 2026 si terrà la cicloescursione. '
                       'Prossime escursioni previste: sabato 31 ottobre 2026 '
                       'un altro percorso.')
        result = self.interpret('10 ottobre 2026', description,
                                ['2026-10-10'])
        self.assertEqual(result['reason'], 'related_event_dates_separated')

    def test_exhibition_end_is_separate_from_collateral_programme(self):
        description = ('Gli eventi collaterali sono giovedì 1 ottobre, '
                       'giovedì 8 ottobre e giovedì 15 ottobre. '
                       'La mostra sarà visitabile fino al 29 novembre.')
        result = self.interpret('1 ottobre 2026 - 15 ottobre 2026',
                                description,
                                ['2026-10-01', '2026-10-08', '2026-10-15'])
        self.assertEqual(result['reason'], 'related_event_dates_separated')
        mismatch = self.interpret('1 ottobre 2026 - 15 ottobre 2026',
                                  description, ['2026-10-01', '2026-10-09'])
        self.assertNotEqual(mismatch['reason'], 'related_event_dates_separated')

    def test_interval_without_programme_stays_under_review(self):
        result = self.interpret(
            '1 ottobre 2026 - 30 aprile 2027',
            'Una stagione di concerti: il primo appuntamento è annunciato per ottobre.')
        self.assertEqual(result['reason'], 'programme_not_explicit_or_complete')

    def test_snapshot_selects_only_unresolved_aligned_details(self):
        url = 'https://www.turismofvg.it/eventi/prova'
        forward = {'schema': 'turismofvg-forward-detail-audit-v1',
                   'as_of_date': '2026-10-05', 'index_snapshot_id': 'abc',
                   'candidates': [{'url': url,
                                   'listing_occurrences': ['2026-10-10']}],
                   'results': {url: {'status': 'detail_aligned',
                                     'schedule_interpretation':
                                         'range_with_badges_needs_interpretation',
                                     'detail_date_full': '10 ottobre 2026 - 11 ottobre 2026',
                                     'event': {'title': 'Prova', 'event_city': 'Udine'}}},
                   'attempts': {}}
        snapshot = create_snapshot(forward)
        self.assertEqual(len(snapshot['items']), 1)
        self.assertEqual(snapshot['items'][0]['listing_occurrences'], ['2026-10-10'])


if __name__ == '__main__':
    unittest.main()
