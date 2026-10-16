import unittest
from app.events.pilot_details import calendar_occurrences, promote_candidate


class DetailCalendarTests(unittest.TestCase):
    def test_legacy_discrete_dates_are_retained(self):
        result = promote_candidate({'title': 'Festa', 'event_city': 'Udine'},
            {'detail_title': 'Festa', 'event_city': 'Udine', 'date_full': '12 e 19 settembre 2026'})
        self.assertEqual(result['occurrences'], ['2026-09-12', '2026-09-19'])
        self.assertEqual(result['schedule_kind'], 'occurrences')

    def test_recurrence_until_date_is_not_treated_as_single_date(self):
        self.assertIsNone(promote_candidate({'title': 'Festa', 'event_city': 'Udine'},
            {'detail_title': 'Festa', 'event_city': 'Udine', 'date_full': 'ogni lunedì fino al 28 settembre 2026'}))

    def test_source_truncated_title_matches_complete_detail(self):
        title = 'Workshop di espressione corporea e teatro'
        metadata = {'date_full': '7 settembre 2026', 'event_city': 'Pordenone', 'detail_title': title}
        for abbreviated in ('Workshop di espressione corporea...', 'Workshop di espressione corporea…'):
            result = promote_candidate({'title': abbreviated, 'event_city': 'Pordenone'}, metadata)
            self.assertEqual(result['title'], title)
        self.assertIsNone(promote_candidate({'title': 'Un altro evento completamente diverso...', 'event_city': 'Pordenone'}, metadata))

    def test_explicit_calendar_with_year_from_detail_range(self):
        metadata = {'date_full': 'giovedì 3 settembre 2026 - giovedì 10 dicembre 2026',
                    'event_city': 'Pordenone', 'detail_title': 'Letture', 'venue': 'Centro per le Famiglie'}
        days = calendar_occurrences(metadata,
            'Calendario: 3 - 17 settembre 1 - 15 - 29 ottobre 12 - 26 novembre 10 dicembre Orario: dalle 17:00 alle 18:00')
        self.assertEqual(days, ['2026-09-03', '2026-09-17', '2026-10-01', '2026-10-15',
                                '2026-10-29', '2026-11-12', '2026-11-26', '2026-12-10'])
        event = promote_candidate({'title': 'Letture', 'event_city': 'Pordenone'},
                                  {**metadata, 'occurrences': days})
        self.assertEqual(event['occurrences'], days)
        self.assertEqual(event['venue'], metadata['venue'])
        self.assertEqual(event['location_confidence'], 'municipality')

    def test_incomplete_or_unrelated_calendar_not_inferred(self):
        metadata = {'date_full': '3 settembre 2026 - 10 dicembre 2026'}
        for text in ('Racconto del 17 settembre', 'Calendario: dal 3 al 17 settembre',
                     'Calendario: 3 settembre escluso lunedì', 'Calendario: 31 novembre',
                     'Calendario: 1 gennaio', 'Calendario: 3 settembre 2027'):
            with self.subTest(text=text):
                self.assertEqual(calendar_occurrences(metadata, text), [])

    def test_year_must_come_from_event_not_today(self):
        self.assertEqual(calendar_occurrences({'date_full': '3 settembre'}, 'Calendario: 3 settembre'), [])
