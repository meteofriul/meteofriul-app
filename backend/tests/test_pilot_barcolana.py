import unittest
from datetime import date, datetime, timezone
from html import escape

from app.events.pilot_barcolana import (CALENDAR_DATA, EDITION_NEWS, SITEMAP, KNOWN_ORPHAN,
                                        REGIONAL_PIAZZA_PAGES, REGIONAL_MUSEUM,
                                        REGIONAL_TALKS,
                                        collect_barcolana, current_card, link_unique_details,
                                        parse_calendar, parse_regional_piazza)
from app.events.pilot_catalog import PILOT_PROJECT, query_catalog
from app.events.pilot_dedupe import deduplicate
from app.events.pilot_source_policy import gate_batch


DATES = (['25 settembre 2026', '27 settembre 2026']
         + [f'{day:02d} ottobre 2026' for day in range(1, 13)]
         + ['29 novembre 2026'])


def row(index, *, title=None, place='Piazza Unità', day=None, time='15:00:00'):
    pk = f'00000000-0000-0000-0000-{index:012x}'
    start = (f"<span class='c-eventItem__time'><script>"
             f"new Date('1900-01-01T{time}.000Z')</script></span>"
             if time else '')
    location = f"<div class='c-eventItem__location'>{place}</div>" if place else ''
    return (f'<div class="hyve-repeater-i1g43-item" data-item-pk="{pk}">'
            f'<div class="c-eventItem"><span class="c-eventItem__date">'
            f'{day or DATES[index % len(DATES)]}</span>{start}{location}'
            f'<div class="c-eventItem__title">{title or f"Appuntamento {index}"}</div>'
            '</div></div>')


class Response:
    def __init__(self, body, status_code=200):
        self.content = body.encode('utf-8')
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise ValueError(f'HTTP {self.status_code}')


class BarcolanaTests(unittest.TestCase):
    def test_detail_links_require_one_title_and_one_sitemap_slug(self):
        sessions = [{'title': 'La regata', 'url': 'calendar'},
                    {'title': 'Mostra', 'url': 'calendar'},
                    {'title': 'Mostra', 'url': 'calendar'}]
        urls = {'https://www.barcolana.it/it/eventi/mare/2026/la-regata',
                'https://www.barcolana.it/it/eventi/terra/2026/mostra'}
        self.assertEqual(link_unique_details(sessions, urls), 1)
        self.assertEqual(sessions[0]['url'], 'https://www.barcolana.it/it/eventi/mare/2026/la-regata')
        self.assertEqual([item['url'] for item in sessions[1:]], ['calendar', 'calendar'])

    def test_calendar_deduplicates_exact_rows_and_omits_conflicting_ceremony_time(self):
        html = (row(1, title='CONCERTO LES BABETTES', day='09 ottobre 2026')
                + row(2, title='CONCERTO LES BABETTES', day='09 ottobre 2026')
                + row(3, title='CERIMONIA DI CHIUSURA DEL TOUR MONDIALE VESPUCCI '
                       'E INAUGURAZIONE VILLAGGIO IN ITALIA',
                       day='08 ottobre 2026', place='') )
        sessions, proof = parse_calendar(html)
        self.assertEqual((proof['records_scanned'], proof['parsed_count'],
                          proof['duplicate_count']), (3, 2, 1))
        self.assertEqual(sessions[0]['title'], 'CERIMONIA DI CHIUSURA DEL TOUR MONDIALE VESPUCCI E INAUGURAZIONE VILLAGGIO IN ITALIA')
        self.assertNotIn('time', sessions[0])
        self.assertNotIn('place', sessions[0])
        self.assertEqual(sessions[1]['time'], '16:00')

    def test_calendar_unifies_reviewed_stage_alias(self):
        html = (row(1, title='CROSSROADS VOCAL GROUP', day='10 ottobre 2026',
                    place='Palco Cavana')
                + row(2, title='CROSSROADS VOCAL GROUP', day='10 ottobre 2026',
                      place='Palco Piazza Cavana'))
        sessions, proof = parse_calendar(html)
        self.assertEqual(proof['duplicate_count'], 1)
        self.assertEqual(len(sessions), 1)
        self.assertEqual(sessions[0]['place'], 'Palco Piazza Cavana')

    def test_calendar_omits_broken_cms_title_only_with_verified_ski_event(self):
        broken = row(2, title='OfficeOpenXml.Style.ExcelRichTextCollection',
                     day='10 ottobre 2026', place='Sci Club 70', time='08:30:00')
        canonical = row(1, title="BARCOLANA SKI - COPPA D'AUTUNNO",
                        day='10 ottobre 2026', place='Centro Federale "Neve Sole"',
                        time='08:00:00')
        sessions, proof = parse_calendar(canonical + broken)
        self.assertEqual([item['title'] for item in sessions],
                         ["BARCOLANA SKI - COPPA D'AUTUNNO"])
        self.assertEqual(proof['duplicate_count'], 1)
        with self.assertRaisesRegex(ValueError, 'unresolved malformed'):
            parse_calendar(broken)

    def test_complete_official_programme_and_regional_preference(self):
        calendar = ''.join(row(index) for index in range(1, 511))
        calendar += row(999, title='Appuntamento 1', day=DATES[1 % 15])
        for index, day in enumerate(range(7, 12), 1001):
            title = ('CONCERTO DI MUSICA SACRA SERBO-ORTODOSSA' if day == 7
                     else f'REGIONAL GIORNO {day}')
            calendar += row(index, title=title, day=f'{day:02d} ottobre 2026',
                            time='18:30:00' if day == 7 else '15:00:00')
        calendar += row(1006, title='TRIESTE E IL MARE',
                        day='03 ottobre 2026', time='14:00:00')
        news = ('<title>Barcolana 57 - Barcolana58 presented by Generali</title>'
                '<meta property="og:image" content="https://www.barcolana.it/hyve/image/2026/web/1200/630">'
                '<div class="c-news__text">Dal 2 all\'11 ottobre 2026 Barcolana58 '
                'porta la regata e gli incontri a Trieste.</div>')
        sitemap = ('<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
                   + ''.join(f'<url><loc>https://www.barcolana.it/it/eventi/terra/2026/event-{index}</loc></url>'
                             for index in range(517))
                   + f'<url><loc>{KNOWN_ORPHAN}</loc></url></urlset>')
        mirrors = {}
        for url, day in REGIONAL_PIAZZA_PAGES.items():
            number = int(day[-2:])
            title = ('CONCERTO DI MUSICA SACRA SERBO-ORTODOSSA' if number == 7
                     else f'REGIONAL GIORNO {number}')
            programme = (f'MERCOLEDI {number} OTTOBRE<br>'
                         + ("ore 16.00 Piazza Cavana<br>CONCERTO DEI RAGAZZI DEL COLLEGIO "
                            "DEL MONDO UNITO DELL'ADRIATICO<br>Concerto degli studenti.<br>"
                            if number == 8 else '')
                         + f'ore {"19.00" if number == 7 else "16.00"} Piazza Cavana<br>'
                           f'{title}<br>Una esibizione musicale.<br>'
                           'Il programma può subire variazioni. Consultare il sito di Barcolana 58')
            mirrors[url] = ('<meta property="og:title" '
                            'content="Barcolana 58 - eventi in piazza">'
                            f'<meta property="og:url" content="{url}">'
                            f'<meta property="og:description" content="{escape(programme, quote=True)}">')
        def regional_meta(url, title, description):
            return (f'<meta property="og:title" content="{title}">'
                    f'<meta property="og:url" content="{url}">'
                    f'<meta property="og:description" content="{escape(description, quote=True)}">')
        mirrors[REGIONAL_MUSEUM] = regional_meta(
            REGIONAL_MUSEUM, 'Barcolana al museo - Museo del Mare',
            'CALENDARIO DEGLI APPUNTAMENTI<br>Sabato 3 ottobre<br>'
            '15.00 – 16.00 | Trieste e il mare<br>PRENOTAZIONI')
        mirrors[REGIONAL_TALKS] = regional_meta(
            REGIONAL_TALKS, 'Barcolana58 - Talk',
            "Venerdì 9 ottobre ore 18.00<br>L'incanto dei castelli d'acqua: "
            'Miramare e Duino protagonisti della riviera triestina<br>'
            'Guido Comis in dialogo<br>Sabato 10 ottobre ore 11.00<br>'
            'Le frontiere che uniscono: storie di popoli, viaggi, identità<br>'
            'Toni Capuozzo in dialogo')
        def get(url, **_kwargs):
            if url == KNOWN_ORPHAN:
                return Response('', 404)
            return Response({CALENDAR_DATA: calendar, EDITION_NEWS: news,
                             SITEMAP: sitemap, **mirrors}[url])
        batch = collect_barcolana(get=get, today=date(2026, 10, 7))
        self.assertEqual(batch['verification']['records_scanned'], 517)
        self.assertEqual(batch['verification']['parsed_count'], 516)
        self.assertEqual(batch['verification']['duplicate_count'], 1)
        self.assertEqual(batch['verification']['regional_piazza_supplement_count'], 1)
        self.assertEqual(batch['verification']['regional_supplement_count'], 3)
        self.assertEqual(gate_batch('Barcolana', batch, today=date(2026, 10, 7))['status'], 'ok')
        def get_calendar_ahead(url, **kwargs):
            if url == CALENDAR_DATA:
                return Response(calendar + row(2000, title='Nuovo incontro',
                                               day='09 ottobre 2026'))
            return get(url, **kwargs)
        calendar_ahead = collect_barcolana(get=get_calendar_ahead,
                                           today=date(2026, 10, 7))
        self.assertEqual(calendar_ahead['verification']['sitemap_lag_rows'], 1)
        self.assertEqual(gate_batch('Barcolana', calendar_ahead,
                                    today=date(2026, 10, 7))['status'], 'ok')
        def get_sitemap_ahead(url, **kwargs):
            if url == SITEMAP:
                return Response(sitemap.replace('</urlset>',
                    '<url><loc>https://www.barcolana.it/it/eventi/terra/2026/senza-calendario</loc></url></urlset>'))
            return get(url, **kwargs)
        with self.assertRaisesRegex(ValueError, 'sitemap has rows absent'):
            collect_barcolana(get=get_sitemap_ahead, today=date(2026, 10, 7))
        past_page = next(iter(REGIONAL_PIAZZA_PAGES))
        def get_after_first_day(url, **kwargs):
            if url == past_page:
                return Response('', 404)
            return get(url, **kwargs)
        next_day = collect_barcolana(get=get_after_first_day,
                                     today=date(2026, 10, 8))
        self.assertEqual(next_day['verification']['regional_piazza_page_count'], 4)
        self.assertEqual(next_day['verification']['regional_piazza_supplement_count'], 1)
        self.assertNotIn(past_page, next_day['events'][0]['regional_mirror_days'])
        self.assertEqual(gate_batch('Barcolana', next_day,
                                    today=date(2026, 10, 8))['status'], 'ok')
        def get_without_orphan(url, **kwargs):
            if url == SITEMAP:
                return Response(sitemap.replace(
                    f'<url><loc>{KNOWN_ORPHAN}</loc></url>', ''))
            return get_after_first_day(url, **kwargs)
        orphan_removed = collect_barcolana(get=get_without_orphan,
                                            today=date(2026, 10, 8))
        self.assertEqual(orphan_removed['verification']['sitemap_known_orphan_count'], 0)
        self.assertEqual(orphan_removed['verification']['regional_piazza_supplement_count'], 1)
        self.assertEqual(gate_batch('Barcolana', orphan_removed,
                                    today=date(2026, 10, 8))['status'], 'ok')
        late = collect_barcolana(get=get_after_first_day,
                                 today=date(2026, 10, 12))
        self.assertEqual(late['verification']['regional_piazza_page_count'], 0)
        self.assertEqual(late['verification']['regional_museum_row_count'], 0)
        self.assertEqual(late['verification']['regional_talk_row_count'], 0)
        self.assertEqual(gate_batch('Barcolana', late,
                                    today=date(2026, 10, 12))['status'], 'ok')
        active_page = list(REGIONAL_PIAZZA_PAGES)[1]
        def get_missing_active_day(url, **kwargs):
            return Response('', 404) if url == active_page else get_after_first_day(url, **kwargs)
        with self.assertRaises(ValueError):
            collect_barcolana(get=get_missing_active_day,
                              today=date(2026, 10, 8))
        partial = {**batch, 'verification': {**batch['verification'], 'records_scanned': 100}}
        self.assertEqual(gate_batch('Barcolana', partial, today=date(2026, 10, 7))['status'], 'error')
        wrong_cover = {**batch, 'events': [{**batch['events'][0],
                                            'image': 'https://example.test/cover.jpg'}]}
        self.assertEqual(gate_batch('Barcolana', wrong_cover, today=date(2026, 10, 7))['status'], 'error')
        event = batch['events'][0]
        regional = {'source': 'TurismoFVG', 'url': 'https://www.turismofvg.it/eventi/58a-ed-barcolana',
                    'title': '58a Ed. Barcolana.', 'event_city': 'Trieste',
                    'start_date': '2026-10-02', 'end_date': '2026-10-11',
                    'lat': 45.64953, 'lon': 13.77678}
        distinct = {'source': 'TurismoFVG', 'url': 'https://www.turismofvg.it/eventi/barcolana-ski',
                    'title': 'Barcolana Ski', 'event_city': 'Duino Aurisina',
                    'start_date': '2026-10-10', 'end_date': '2026-10-10',
                    'lat': 45.753, 'lon': 13.674}
        mirrored = {'source': 'TurismoFVG', 'url': next(iter(REGIONAL_PIAZZA_PAGES)),
                    'title': 'Barcolana 58 - eventi in piazza', 'event_city': 'Trieste',
                    'start_date': '2026-10-07', 'end_date': '2026-10-07',
                    'lat': 45.64953, 'lon': 13.77678}
        catalog = {'schema': 'pilot-events-v1', 'sources': {
            'Barcolana': {'status': 'fresh', 'updated_at': '2026-10-07T12:00:00Z',
                          'events': [event]},
            'TurismoFVG': {'status': 'fresh', 'updated_at': '2026-10-07T12:00:00Z',
                           'events': [regional, mirrored, distinct]}}}
        result = query_catalog(catalog, 45.64953, 13.77678, radius=20,
                               now=datetime(2026, 10, 7, 14, tzinfo=timezone.utc))
        self.assertEqual(len([item for item in result['events']
                              if item['title'] in {'Barcolana 2026', '58a Ed. Barcolana.'}]), 1)
        self.assertEqual(len(result['events']), 2)
        self.assertEqual(result['events'][0]['source'], 'Barcolana')
        self.assertEqual(result['events'][0]['programme_sessions'][0]['start_date'], '2026-10-07')
        self.assertIn(regional['url'], result['events'][0]['source_urls'])
        self.assertIn(mirrored['url'], result['events'][0]['source_urls'])
        self.assertEqual(len([item for item in result['events'][0]['programme_sessions']
                              if "COLLEGIO DEL MONDO UNITO" in item['title']]), 1)
        late = current_card(event, date(2026, 10, 13))
        self.assertEqual(late['date_label'], '29 novembre 2026')
        self.assertGreater(late['active_session_count'], 0)
        self.assertEqual({item['start_date'] for item in late['programme_sessions']},
                         {'2026-11-29'})

    def test_regional_programme_rejects_identity_or_truncation(self):
        url = next(iter(REGIONAL_PIAZZA_PAGES))
        header = ('<meta property="og:title" content="Barcolana 58 - eventi in piazza">'
                  f'<meta property="og:url" content="{url}">')
        body = ('MERCOLEDI 7 OTTOBRE<br>ore 16.00 Piazza Cavana<br>'
                'MUSICA IN PIAZZA<br>Concerto per tutti.<br>'
                'Il programma può subire variazioni. Consultare il sito di Barcolana 58')
        self.assertEqual(len(parse_regional_piazza(header + '<meta property="og:description" '
                              f'content="{escape(body, quote=True)}">',
                              url=url, day='2026-10-07')), 1)
        for broken in (body.replace('MERCOLEDI 7', 'MERCOLEDI 8'),
                       body.replace('Il programma può subire variazioni.', ''),
                       body.replace('MUSICA IN PIAZZA<br>Concerto per tutti.<br>', '')):
            with self.assertRaises(ValueError):
                parse_regional_piazza(header + '<meta property="og:description" '
                                      f'content="{escape(broken, quote=True)}">',
                                      url=url, day='2026-10-07')

    def test_local_ski_card_is_absorbed_only_when_umbrella_is_visible(self):
        ski = {'source': 'TurismoFVG',
               'url': 'https://www.turismofvg.it/eventi/barcolana-ski-coppa-d-autunno-il-10-ottobre-la-sfida-ad-aurisina',
               'title': 'Barcolana Ski – Coppa d’Autunno: il 10 ottobre la sfida ad Aurisina',
               'event_city': 'Duino-Aurisina', 'start_date': '2026-10-10',
               'end_date': '2026-10-10', 'distance_km': 1.0}
        official = {'source': 'Barcolana', 'title': 'Barcolana 2026',
                    'url': 'https://www.barcolana.it/it/calendario-eventi',
                    'distance_km': 12.0,
                    'programme_sessions': [{'title': "BARCOLANA SKI - COPPA D'AUTUNNO",
                                            'start_date': '2026-10-10'}]}
        result = deduplicate([official, ski])
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['distance_km'], 1.0)
        self.assertIn(ski['url'], result[0]['source_urls'])
        self.assertEqual(deduplicate([ski]), [ski])


if __name__ == '__main__':
    unittest.main()
