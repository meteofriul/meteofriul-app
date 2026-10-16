from copy import deepcopy
from datetime import date
import json
from pathlib import Path
import unittest

from app.events.pilot_mess import (parse_laboratories, parse_news,
                                    REVIEWED_ACTIVE_NEWS)
from app.events.pilot_dedupe import deduplicate
from app.events.pilot_programmes import project_programme_editions
from app.events.pilot_source_policy import gate_batch


FIXTURE = Path(__file__).with_name('fixtures') / 'mess_laboratori_2026.json'
NEWS_FIXTURE = Path(__file__).with_name('fixtures') / 'mess_notizie_2026.json'


def pages():
    data = json.loads(FIXTURE.read_text(encoding='utf-8'))
    return data['programme'], data['museums']


def news_pages():
    news = json.loads(NEWS_FIXTURE.read_text(encoding='utf-8'))
    labels = {'2026-09-25': '25 settembre 2026',
              '2026-11-29': '29 novembre 2026',
              '2026-09-12': '12 settembre 2026',
              '2026-10-31': '31 ottobre 2026',
              '2026-06-13': '13 giugno 2026',
              '2026-12-31': '31 dicembre 2026'}
    regional = {item['regional_url']: {
        'date_full': labels[item['start']] + ' - ' + labels[item['end']],
        'event_city': item['city']}
        for item in REVIEWED_ACTIVE_NEWS.values()}
    return news, regional


def complete_batch():
    programme, museums = pages()
    batch = parse_laboratories(programme, museums, today=date(2026, 10, 7))
    news, regional = news_pages()
    news_events, proof = parse_news(news, regional, today=date(2026, 10, 7))
    batch['verification']['laboratory_count'] = len(batch['events'])
    batch['events'].extend(news_events)
    batch['verification'].update(proof)
    batch['verification']['projected_count'] = len(batch['events'])
    return batch


class MessLaboratoriesTests(unittest.TestCase):
    def test_complete_programme_and_museum_addresses(self):
        programme, museums = pages()
        batch = parse_laboratories(programme, museums, today=date(2026, 10, 7))
        self.assertEqual(batch['verification']['declared_laboratories'], 36)
        self.assertEqual(batch['verification']['museum_locations'], 18)
        self.assertEqual(len(batch['events']), 16)
        self.assertEqual(gate_batch('MESS', complete_batch(),
                                    today=date(2026, 10, 7))['status'], 'ok')
        telaio = next(event for event in batch['events']
                      if event['start_date'] == '2026-11-28')
        self.assertEqual(telaio['event_city'], 'Udine')
        self.assertEqual(telaio['programme_id'], 'mess-laboratori-2026-38546')
        self.assertTrue(telaio['description_excerpt'])
        vino = next(event for event in batch['events']
                    if event['start_date'] == '2026-10-25')
        self.assertEqual(vino['event_city'], 'Buttrio')
        self.assertEqual(vino['location_confidence'], 'municipality')
        unattributed = complete_batch()
        unattributed['events'][0]['description_source_name'] = 'unknown'
        self.assertEqual(gate_batch('MESS', unattributed,
                                    today=date(2026, 10, 7))['status'], 'error')

    def test_missing_day_or_new_typo_stops_source(self):
        programme, museums = pages()
        index = programme['modules'][1]['list'][1]
        index['description'] = index['description'].replace('28 novenbre', '28 nuvenbre')
        with self.assertRaisesRegex(ValueError, 'unreadable|unrecognised'):
            parse_laboratories(programme, museums, today=date(2026, 10, 7))
        programme, museums = pages()
        index = programme['modules'][1]['list'][1]
        index['description'] = index['description'].replace('28 novenbre', '28 novembre')
        self.assertEqual(len(parse_laboratories(programme, museums,
                                                today=date(2026, 10, 7))['events']), 16)
        programme, museums = pages()
        index = programme['modules'][1]['list'][1]
        index['description'] = index['description'].replace(
            '<ul><li>28 novenbre', '<ul><p>28 novenbre', 1)
        with self.assertRaisesRegex(ValueError, 'count differs'):
            parse_laboratories(programme, museums, today=date(2026, 10, 7))

    def test_unresolved_museum_or_lost_future_day_blocks_gate(self):
        programme, museums = pages()
        museums['modules'][0]['locations'][2]['address'] = 'Sede senza comune'
        with self.assertRaisesRegex(ValueError, 'municipality unresolved'):
            parse_laboratories(programme, museums, today=date(2026, 10, 7))
        programme, museums = pages()
        batch = complete_batch()
        damaged = deepcopy(batch)
        damaged['events'] = damaged['events'][1:]
        damaged['verification']['projected_count'] -= 1
        previous = {'events': batch['events']}
        self.assertEqual(gate_batch('MESS', damaged,
                                    today=date(2026, 10, 7),
                                    previous_batch=previous)['status'], 'error')

    def test_news_requires_unchanged_inventory_and_regional_year(self):
        news, regional = news_pages()
        events, proof = parse_news(news, regional, today=date(2026, 10, 7))
        self.assertEqual(len(events), 3)
        self.assertEqual(proof['news_records'], 51)
        self.assertTrue(all(event.get('description_excerpt') for event in events))
        changed = deepcopy(news)
        changed['articles'][0]['modified'] = '2026-10-07T12:00:00'
        with self.assertRaisesRegex(ValueError, 'changed MESS news'):
            parse_news(changed, regional, today=date(2026, 10, 7))
        changed = deepcopy(regional)
        changed[REVIEWED_ACTIVE_NEWS[232542]['regional_url']]['date_full'] = (
            '12 settembre 2025 - 31 ottobre 2025')
        with self.assertRaisesRegex(ValueError, 'dates disagree'):
            parse_news(news, changed, today=date(2026, 10, 7))
        changed = deepcopy(news)
        changed['articles'].append({**changed['articles'][0],
                                    'id': 999999, 'modified': '2026-10-07T12:00:00'})
        with self.assertRaisesRegex(ValueError, 'changed MESS news'):
            parse_news(changed, regional, today=date(2026, 10, 7))

    def test_mess_news_and_regional_detail_become_one_card(self):
        news = next(item for item in complete_batch()['events']
                    if item.get('source_id') == 'mess-news-232542')
        regional = {**news, 'source': 'TurismoFVG',
                    'url': REVIEWED_ACTIVE_NEWS[232542]['regional_url'],
                    'title': 'Mostra Victor Oriecuia - Spiriti, amuleti e memorie ancestrali',
                    'venue': 'Museo SMO - San Pietro al Natisone',
                    'place': 'Museo SMO, San Pietro al Natisone',
                    'mess_content_kind': None}
        result = deduplicate([regional, news])
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['source'], 'MESS')
        self.assertEqual(set(result[0]['source_urls']),
                         {regional['url'], news['url']})
        different_city = {**regional, 'event_city': 'Udine'}
        self.assertEqual(len(deduplicate([different_city, news])), 2)

    def test_regional_programme_and_detail_join_museum_card(self):
        programme, museums = pages()
        batch = complete_batch()
        regional = [
            {'source': 'TurismoFVG',
             'url': 'https://www.turismofvg.it/eventi/mess-laboratori-cose-cos-e-2026',
             'start_date': '2026-08-01', 'end_date': '2026-12-20',
             'location_confidence': 'multiple_municipalities',
             'title': "Mess - Laboratori Cose, Cos'è? 2026"},
            {'source': 'TurismoFVG',
             'url': 'https://www.turismofvg.it/eventi/mess-laboratori-cose-cos-e-498424',
             'start_date': '2026-11-28', 'end_date': '2026-11-28',
             'event_city': 'Udine', 'title': "Mess - Laboratori Cose, Cos'è?",
             'image': 'https://www.turismofvg.it/cover.jpg'},
            {'source': 'TurismoFVG',
             'url': 'https://www.turismofvg.it/eventi/tra-percorsi-nascosti-in-belle-giornate',
             'start_date': '2026-10-24', 'end_date': '2026-10-24',
             'event_city': 'Ronchi dei Legionari',
             'title': 'Tra percorsi nascosti in belle giornate'},
            {'source': 'TurismoFVG',
             'url': 'https://www.turismofvg.it/eventi/cose-cos-e-in-viaggio-nei-musei-etnografici-e-storici-del-friuli-venezia-giulia',
             'start_date': '2026-12-06', 'end_date': '2026-12-13',
             'event_city': 'Maniago', 'title': 'Cose, cos’è? Nei musei'},
        ]
        cards = project_programme_editions(regional + batch['events'],
                                            today=date(2026, 10, 7))
        self.assertEqual(len(cards), 12)
        self.assertFalse(any(card.get('source') == 'TurismoFVG' for card in cards))
        udine = next(card for card in cards if card.get('programme_id') ==
                     'mess-laboratori-2026-38546')
        self.assertEqual(udine['active_session_count'], 1)
        self.assertEqual(udine['image'], 'https://www.turismofvg.it/cover.jpg')
        self.assertTrue(udine['description_excerpt'])


if __name__ == '__main__':
    unittest.main()
