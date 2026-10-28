import unittest
import json
import copy
from unittest.mock import Mock, patch
from threading import Barrier, Event, Lock
import time

import requests
from datetime import date, datetime, timezone
from html import escape

from app.events.pilot_barcolana import (CALENDAR_DATA, EDITION_NEWS, SITEMAP, KNOWN_ORPHAN,
                                        REGIONAL_PIAZZA_PAGES, REGIONAL_MUSEUM,
                                        REGIONAL_TALKS, READ_BUDGET_SECONDS,
                                        MAX_PARALLEL_READS, _read, _read_pages,
                                        collect_barcolana, current_card, link_unique_details,
                                        parse_calendar, parse_regional_piazza)
from app.events.pilot_catalog import PILOT_PROJECT, merge_collection, query_catalog
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


def seasonality_fixture(*, today=date(2026, 10, 28), omit_award=False,
                        omit_past=False):
    """Synthetic complete calendar with one post-regatta date, as archived on 25 Oct."""
    rows = [row(index, day=DATES[index % 14]) for index in range(1, 511)
            if not (omit_past and index == 1)]
    if not omit_award:
        rows.append(row(90000, title="PREMIAZIONI 58° COPPA D'AUTUNNO",
                        day='29 novembre 2026',
                        place='Teatro Stabile del Friuli Venezia Giulia, Il Rossetti',
                        time='09:00:00'))
    sitemap = ('<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
               + ''.join('<url><loc>https://www.barcolana.it/it/eventi/terra/2026/'
                         f'event-{index}</loc></url>' for index in range(len(rows)))
               + '</urlset>')
    news = ('<title>Barcolana58 presented by Generali</title>'
            '<meta property="og:image" content="https://www.barcolana.it/hyve/image/2026/web/1200/630">'
            '<div class="c-news__text">Dal 2 all\'11 ottobre 2026 Barcolana58 '
            'porta la regata e gli incontri a Trieste.</div>')
    pages = {CALENDAR_DATA: ''.join(rows), SITEMAP: sitemap, EDITION_NEWS: news}
    return collect_barcolana(get=lambda url, **_: Response(pages[url]), today=today)


class BarcolanaTests(unittest.TestCase):

    def test_independent_evidence_is_read_in_parallel_with_a_bounded_pool(self):
        # Two waves fill the pool; a serial reader cannot cross the barrier.
        barrier, lock = Barrier(MAX_PARALLEL_READS), Lock()
        active, peak = 0, 0
        def get(url, **kwargs):
            nonlocal active, peak
            self.assertLessEqual(sum(kwargs['timeout']), 11)
            with lock:
                active += 1
                peak = max(peak, active)
            try:
                barrier.wait(timeout=5)
                return Response(url)
            finally:
                with lock:
                    active -= 1
        specs = {f'page_{i}': (f'https://example.test/{i}', 100)
                 for i in range(MAX_PARALLEL_READS * 2)}
        pages = _read_pages(get, specs, deadline=time.monotonic() + READ_BUDGET_SECONDS)
        self.assertEqual(set(pages), {url for url, _ in specs.values()})
        self.assertEqual(peak, MAX_PARALLEL_READS)

    def test_slow_required_page_rejects_all_pages_at_shared_deadline(self):
        release = Event()
        def get(url, **_):
            if url == SITEMAP:
                release.wait(timeout=5)
            return Response('complete document')
        try:
            with self.assertRaisesRegex(ValueError, 'budget exhausted; pending: sitemap'):
                _read_pages(get, {'calendar': (CALENDAR_DATA, 100),
                                  'sitemap': (SITEMAP, 100)},
                            deadline=time.monotonic() + 0.15)
        finally:
            release.set()

    def test_read_retries_once_without_resetting_deadline(self):
        now, timeouts = [100.0], []
        success = Response('complete document')
        success.close = Mock()
        def get(*_, **kwargs):
            timeouts.append(kwargs['timeout'])
            if len(timeouts) == 1:
                now[0] += 23
                raise requests.ReadTimeout('temporary stall')
            now[0] += 1
            return success
        with patch('app.events.pilot_barcolana.time.monotonic', side_effect=lambda: now[0]), \
                patch('app.events.http_client.time.sleep', side_effect=lambda n: now.__setitem__(0, now[0]+n)):
            self.assertEqual(_read(get, CALENDAR_DATA, 100, deadline=128), 'complete document')
        self.assertEqual(len(timeouts), 2)
        self.assertEqual(timeouts[0], (3, 8))
        self.assertLessEqual(sum(timeouts[1]), 4.5)
        success.close.assert_called_once()

    def test_expired_deadline_does_not_start_another_request(self):
        get = Mock()
        with self.assertRaisesRegex(ValueError, 'budget exhausted'):
            _read(get, CALENDAR_DATA, 100, deadline=time.monotonic() - 1)
        get.assert_not_called()

    def test_second_read_can_recover_a_response_slower_than_eight_seconds(self):
        now, timeouts = [100.0], []
        def get(*_, **kwargs):
            timeouts.append(kwargs['timeout'])
            latency = 10  # Both requests exceed the previous 8s read timeout.
            now[0] += min(latency, kwargs['timeout'][1])
            if kwargs['timeout'][1] < latency:
                raise requests.ReadTimeout('slow calendar')
            return Response('complete calendar')
        with patch('app.events.pilot_barcolana.time.monotonic', side_effect=lambda: now[0]), \
                patch('app.events.http_client.time.sleep', side_effect=lambda n: now.__setitem__(0, now[0]+n)), \
                patch('builtins.print') as output:
            self.assertEqual(_read(get, CALENDAR_DATA, 100, deadline=128,
                                   stage='calendar'), 'complete calendar')
        self.assertEqual(timeouts, [(3, 8), (3, 16)])
        self.assertLess(now[0], 128)
        diagnostic = json.loads(output.call_args.args[0])
        self.assertEqual((diagnostic['attempts'], diagnostic['status']), (2, 'read'))
        self.assertEqual(diagnostic['stage'], 'calendar')
        self.assertNotIn(CALENDAR_DATA, output.call_args.args[0])

    def test_retry_cannot_extend_remaining_budget_after_connect_and_read_timeout(self):
        now, timeouts = [100.0], []
        def get(*_, **kwargs):
            timeout = kwargs['timeout']
            timeouts.append(timeout)
            self.assertLessEqual(sum(timeout), 128 - now[0])
            now[0] += sum(timeout)
            raise requests.ReadTimeout('still unavailable')
        with patch('app.events.pilot_barcolana.time.monotonic', side_effect=lambda: now[0]), \
                patch('app.events.http_client.time.sleep', side_effect=lambda n: now.__setitem__(0, now[0]+n)), \
                patch('builtins.print') as output:
            with self.assertRaises(requests.ReadTimeout):
                _read(get, CALENDAR_DATA, 100, deadline=128, stage='calendar')
        self.assertEqual(timeouts, [(3, 8), (3, 13.5)])
        self.assertEqual(now[0], 128)
        diagnostic = json.loads(output.call_args.args[0])
        self.assertEqual((diagnostic['attempts'], diagnostic['status']), (2, 'failed'))
        self.assertEqual(diagnostic['remaining_seconds'], 0)

    def test_queued_read_only_uses_remaining_budget(self):
        now = [126.0]
        get = Mock(return_value=Response('ok'))
        with patch('app.events.pilot_barcolana.time.monotonic', side_effect=lambda: now[0]):
            self.assertEqual(_read(get, SITEMAP, 100, deadline=128), 'ok')
        self.assertAlmostEqual(sum(get.call_args.kwargs['timeout']), 2)

    def test_no_retry_starts_after_deadline_is_consumed(self):
        now = [100.0]
        def get(*_, **__):
            now[0] = 128
            raise requests.ReadTimeout('budget consumed')
        read = Mock(side_effect=get)
        with patch('app.events.pilot_barcolana.time.monotonic', side_effect=lambda: now[0]), \
                patch('app.events.http_client.time.sleep'):
            with self.assertRaisesRegex(ValueError, 'budget exhausted'):
                _read(read, SITEMAP, 100, deadline=128)
        read.assert_called_once()

    def test_late_success_is_not_published(self):
        now = [100.0]
        response = Response('complete but late')
        response.close = Mock()
        def get(*_, **__):
            now[0] = 129
            return response
        with patch('app.events.pilot_barcolana.time.monotonic', side_effect=lambda: now[0]):
            with self.assertRaisesRegex(ValueError, 'budget exhausted'):
                _read(get, SITEMAP, 100, deadline=128)
        response.close.assert_called_once()

    def test_terminal_http_failure_has_stage_and_never_returns_partial_evidence(self):
        response = Response('', 404)
        response.close = Mock()
        response.raise_for_status = Mock(side_effect=requests.HTTPError('HTTP 404', response=response))
        get = Mock(return_value=response)
        with self.assertRaisesRegex(ValueError, 'edition_news read failed.*HTTP 404'):
            _read_pages(get, {'edition_news': (EDITION_NEWS, 100)},
                        deadline=time.monotonic() + READ_BUDGET_SECONDS)
        get.assert_called_once()
        response.close.assert_called_once()

    def test_read_closes_success_error_oversize_and_known_orphan(self):
        for response, limit, status in [(Response('ok'), 100, 200),
                                        (Response('too large'), 1, 200),
                                        (Response('not needed', 404), 0, 404),
                                        (Response('new page'), 0, 404)]:
            with self.subTest(limit=limit, expected_status=status):
                response.close = Mock()
                get = Mock(return_value=response)
                if len(response.content) > limit and status == 200 or response.status_code != status:
                    with self.assertRaises(ValueError):
                        _read(get, CALENDAR_DATA, limit, deadline=time.monotonic()+28,
                              expected_status=status)
                else:
                    _read(get, CALENDAR_DATA, limit, deadline=time.monotonic()+28,
                          expected_status=status)
                get.assert_called_once()
                response.close.assert_called_once()

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
        for day, phase in ((date(2026, 9, 24), 'programme_upcoming'),
                           (date(2026, 9, 25), 'programme_active'),
                           (date(2026, 10, 11), 'programme_active')):
            with self.subTest(day=day):
                dated = collect_barcolana(get=get, today=day)
                verified = gate_batch('Barcolana', dated, today=day)
                self.assertEqual(verified['status'], 'ok')
                self.assertEqual(verified['verification']['season_phase'], phase)
                self.assertGreater(verified['verification']['remaining_session_count'], 0)
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
        official_reads = Barrier(3)
        def concurrent_after_festival(url, **kwargs):
            if url in {CALENDAR_DATA, SITEMAP, EDITION_NEWS}:
                official_reads.wait(timeout=5)
            if url in mirrors:
                self.fail('past regional page must not be fetched')
            return get_without_orphan(url, **kwargs)
        october25 = collect_barcolana(get=concurrent_after_festival, today=date(2026, 10, 25))
        self.assertEqual(gate_batch('Barcolana', october25, today=date(2026, 10, 25))['status'], 'ok')
        card = current_card(october25['events'][0], date(2026, 10, 25))
        self.assertEqual(card['date_label'], '29 novembre 2026')
        self.assertGreater(card['active_session_count'], 0)
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


class BarcolanaSeasonalityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.previous = seasonality_fixture()

    def gate(self, batch, *, today=date(2026, 10, 28), previous=None):
        return gate_batch('Barcolana', batch, today=today, previous_batch=previous)

    def test_loss_of_single_future_award_below_count_tolerance_is_rejected(self):
        missing = seasonality_fixture(omit_award=True)
        self.assertEqual(self.previous['verification']['records_scanned']
                         - missing['verification']['records_scanned'], 1)
        self.assertGreater(missing['verification']['records_scanned'],
                           self.previous['verification']['records_scanned'] * .9)
        self.assertEqual(self.gate(missing)['status'], 'ok')
        rejected = self.gate(missing, previous=self.previous)
        self.assertEqual(rejected['status'], 'error')
        self.assertEqual(rejected['error_type'], 'source_verification_failed')

    def test_past_session_can_disappear_without_losing_future_award(self):
        current = seasonality_fixture(omit_past=True)
        previous = {**self.previous, 'status': 'stale'}
        result = self.gate(current, previous=previous)
        self.assertEqual(result['status'], 'ok')
        self.assertEqual(result['verification']['remaining_session_count'], 1)
        self.assertEqual(result['verification']['next_session_date'], '2026-11-29')

    def test_session_today_and_stale_previous_are_still_protected(self):
        for day in (date(2026, 10, 28), date(2026, 11, 29)):
            with self.subTest(day=day):
                missing = seasonality_fixture(today=day, omit_award=True)
                result = self.gate(missing, today=day,
                                   previous={**self.previous, 'status': 'stale'})
                self.assertEqual(result['status'], 'error')

    def test_future_title_venue_or_time_change_requires_review(self):
        for field, value in (('title', 'Premiazione diversa'), ('place', 'Altra sede'),
                             ('time', '11:00'), ('end_time', '14:00'),
                             ('start_date', '2026-11-30')):
            with self.subTest(field=field):
                previous = copy.deepcopy(self.previous)
                previous['events'][0]['programme_sessions'][-1][field] = value
                self.assertEqual(self.gate(self.previous, previous=previous)['status'], 'error')

    def test_season_phase_boundaries_and_untrusted_metadata_are_recomputed(self):
        for day, phase, count, next_day in (
                (date(2026, 10, 12), 'post_regatta_events', None, '2026-10-12'),
                (date(2026, 10, 28), 'post_regatta_events', 1, '2026-11-29'),
                (date(2026, 11, 29), 'post_regatta_events', 1, '2026-11-29'),
                (date(2026, 11, 30), 'verified_programme_elapsed', 0, None),
                (date(2026, 12, 31), 'verified_programme_elapsed', 0, None)):
            with self.subTest(day=day):
                current = seasonality_fixture(today=day)
                current['verification'].update(season_phase='officially_closed',
                                               remaining_session_count=-1,
                                               next_session_date='2099-01-01')
                unchanged = copy.deepcopy(current)
                result = self.gate(current, today=day, previous=self.previous)
                self.assertEqual(result['status'], 'ok')
                self.assertEqual(result['verification']['season_phase'], phase)
                self.assertEqual(result['verification']['next_session_date'], next_day)
                if count is not None:
                    self.assertEqual(result['verification']['remaining_session_count'], count)
                    self.assertEqual(len(result['events']), int(count > 0))
                self.assertEqual(current, unchanged)

    def test_elapsed_proof_survives_empty_catalog_and_next_success(self):
        day = date(2026, 11, 30)
        result = self.gate(seasonality_fixture(today=day), today=day,
                           previous=self.previous)
        catalog = merge_collection(PILOT_PROJECT, None, {'Barcolana': result},
                                   '2026-11-30T04:00:00Z')
        previous = catalog['sources']['Barcolana']
        self.assertEqual(previous['events'], [])
        self.assertEqual(previous['verification']['last_date'], '2026-11-29')
        following = date(2026, 12, 1)
        again = self.gate(seasonality_fixture(today=following), today=following,
                          previous=previous)
        self.assertEqual(again['status'], 'ok')
        self.assertEqual(again['events'], [])
        self.assertEqual(again['verification']['season_phase'], 'verified_programme_elapsed')

    def test_empty_previous_requires_valid_elapsed_last_date(self):
        for last_day in (None, 'invalid', '2026-02-30', '2026-10-28', '2026-11-29'):
            with self.subTest(last_day=last_day):
                previous = copy.deepcopy(self.previous)
                previous['events'] = []
                previous['verification']['last_date'] = last_day
                self.assertEqual(self.gate(self.previous, previous=previous)['status'], 'error')

    def test_first_success_after_unavailable_is_not_mistaken_for_lost_programme(self):
        failed = merge_collection(PILOT_PROJECT, None, {
            'Barcolana': {'status': 'error', 'error_type': 'adapter_exception'}},
            '2026-10-27T04:00:00Z')['sources']['Barcolana']
        self.assertEqual(failed['status'], 'unavailable')
        self.assertIsNone(failed['updated_at'])
        for previous in (None, failed):
            with self.subTest(previous=previous):
                self.assertEqual(self.gate(self.previous, previous=previous)['status'], 'ok')
        for field in ('verification', 'events', 'updated_at'):
            previous = copy.deepcopy(self.previous)
            previous.update(status='stale', updated_at='2026-10-25T04:00:00Z')
            previous.pop(field)
            with self.subTest(missing=field):
                # A missing timestamp alone cannot erase valid programme evidence.
                missing = seasonality_fixture(omit_award=True)
                self.assertEqual(self.gate(missing, previous=previous)['status'], 'error')

    def test_malformed_previous_does_not_escape_gate(self):
        malformed = [[], ['not-a-batch'], 'invalid', 42,
                     {'verification': ['invalid'], 'events': []},
                     {'verification': {'edition_id': '2026'}, 'events': []},
                     {'status': 'unavailable', 'updated_at': None, 'events': [],
                      'verification': []}]
        for field, value in (('title', None), ('place', {}), ('start_date', 'invalid'),
                             ('time', [])):
            previous = copy.deepcopy(self.previous)
            previous['events'][0]['programme_sessions'][-1][field] = value
            malformed.append(previous)
        for sessions in (None, [], ['invalid']):
            previous = copy.deepcopy(self.previous)
            previous['events'][0]['programme_sessions'] = sessions
            malformed.append(previous)
        for previous in malformed:
            with self.subTest(previous_type=type(previous).__name__):
                result = self.gate(self.previous, previous=previous)
                self.assertEqual(result['status'], 'error')
                self.assertEqual(result['error_type'], 'source_verification_failed')

    def test_new_year_does_not_certify_old_edition_or_relabel_transport_failure(self):
        today = date(2027, 1, 1)
        outdated = self.gate(seasonality_fixture(today=today), today=today,
                             previous=self.previous)
        self.assertEqual(outdated['status'], 'error')
        self.assertEqual(outdated['error_type'], 'edition_not_current')
        for day in (date(2026, 10, 28), date(2026, 11, 30), today):
            for error in ('timeout', 'adapter_exception'):
                with self.subTest(day=day, error=error):
                    failure = {'status': 'error', 'error_type': error,
                               'exception_type': 'ReadTimeout'}
                    self.assertIs(self.gate(failure, today=day), failure)
                    old_catalog = merge_collection(PILOT_PROJECT, None,
                        {'Barcolana': self.gate(self.previous)}, '2026-10-28T04:00:00Z')
                    failed = merge_collection(PILOT_PROJECT, old_catalog,
                        {'Barcolana': failure}, day.isoformat() + 'T05:00:00Z')
                    self.assertEqual(failed['sources']['Barcolana']['status'], 'stale')
                    self.assertEqual(failed['sources']['Barcolana']['updated_at'],
                                     '2026-10-28T04:00:00Z')


if __name__ == '__main__':
    unittest.main()
