import unittest
from datetime import date
from unittest.mock import patch

from app.events import pilot_proloco_watch as watch


def page(cards, next_page=''):
    markup = '<html><body>'
    for slug, city, when, title in cards:
        markup += (f'<a class="card" href="/eventi-delle-associate/{slug}/?return=1">'
                   f'<div class="card-head"><h3>{city}</h3><h3>{when}</h3></div>'
                   f'<div class="card-body"><h3 class="card-title">{title}</h3></div></a>')
    if next_page:
        markup += f'<a href="/eventi-delle-associate/?page={next_page}">Pagina {next_page}</a>'
    return markup + '</body></html>'


class ProLocoWatchTests(unittest.TestCase):
    def test_paginated_index_matches_regional_dates_without_duplicate_cards(self):
        first = page([('festa-dautunno-12', 'Gonars', '10 ott', "Festa d'Autunno")], 2)
        second = page([('farine-di-flor-formandi', 'Sutrio', 'domenica 18 ottobre 2026',
                        'Farine di flôr / Formandi')])
        with patch.object(watch, '_fetch', side_effect=[first, second]) as fetch:
            index = watch.collect_index()
        self.assertEqual(fetch.call_count, 2)
        self.assertEqual((index['pages'], index['distinct_urls']), (2, 2))
        tourism = [
            {'title': "Festa d'Autunno", 'event_city': 'Gonars',
             'start_date': '2026-10-10', 'end_date': '2026-10-11',
             'url': 'https://www.turismofvg.it/eventi/festa-d-autunno-504304'},
            {'title': 'ForMandi: il sapore delle Malghe', 'event_city': 'Sutrio',
             'start_date': '2026-10-18', 'end_date': '2026-10-18',
             'url': 'https://www.turismofvg.it/eventi/formandi-il-sapore-delle-malghe'},
        ]
        self.assertEqual(watch.watch_changes(index, tourism, date(2026, 10, 7)), [])

    def test_new_or_wrong_year_card_requires_review(self):
        cards, _ = watch.parse_listing(page([
            ('nuova-sagra', 'Gonars', '11 ott', 'Nuova sagra'),
            ('festa-dautunno-12', 'Gonars', '10 ott', "Festa d'Autunno"),
        ]))
        tourism = [{'title': "Festa d'Autunno", 'event_city': 'Gonars',
                    'start_date': '2025-10-10', 'end_date': '2025-10-11',
                    'url': 'https://www.turismofvg.it/eventi/festa-d-autunno-504304'}]
        changes = watch.watch_changes({'cards': cards}, tourism, date(2026, 10, 7))
        self.assertEqual(len(changes), 2)
        self.assertTrue(all(change['reason'] == 'uncovered' for change in changes))

    def test_daily_watch_ignores_cards_beyond_verified_window(self):
        cards, _ = watch.parse_listing(page([
            ('dicembre', 'Udine', '20 dicembre 2026', 'Evento lontano'),
            ('ottobre', 'Udine', '18 ottobre 2026', 'Evento vicino'),
        ]))
        changes = watch.watch_changes(
            {'cards': cards}, [], date(2026, 10, 11),
            window_end=date(2026, 11, 25))
        self.assertEqual([item['title'] for item in changes], ['Evento vicino'])


if __name__ == '__main__':
    unittest.main()
