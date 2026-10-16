import unittest
from datetime import date
from unittest.mock import patch
from app.events.pilot_details import (calendar_occurrences,
                                      corroborated_programme_occurrences,
                                      enrich_details,
                                      german_provider_date_range,
                                      prefetch_details, promote_candidate,
                                      unscheduled_bookable_experience)


class DetailTests(unittest.TestCase):
    def test_german_date_row_checks_both_weekdays_and_range(self):
        self.assertEqual(german_provider_date_range(
            'Mittwoch, 29. Juli 2026 - Freitag, 31. Dezember 2027'),
            (date(2026, 7, 29), date(2027, 12, 31)))
        self.assertEqual(german_provider_date_range(
            'Freitag, 9. Oktober 2026 - Samstag, 19. Dezember 2026'),
            (date(2026, 10, 9), date(2026, 12, 19)))
        self.assertEqual(german_provider_date_range(
            'Montag, 9. Oktober 2026 - Samstag, 19. Dezember 2026'),
            (None, None))

    def test_programme_repairs_structured_end_only_when_all_badges_agree(self):
        metadata = {'date_full': '18 ottobre 2026 - 24 ottobre 2026'}
        description = ('Domenica 18 ottobre inizia la festa. '
                       'Sabato 24 ottobre apertura. Domenica 25 ottobre chiusura.')
        badges = ['2026-10-18', '2026-10-24', '2026-10-25']
        self.assertEqual(corroborated_programme_occurrences(
            metadata, description, badges), badges)
        self.assertEqual(corroborated_programme_occurrences(
            metadata, description, badges[:-1]), [])
        self.assertEqual(corroborated_programme_occurrences(
            metadata, description + ' Una replica il 26 ottobre.', badges), [])

    def test_multi_municipality_detail_keeps_one_card_without_single_point(self):
        candidate = {'source': 'TurismoFVG', 'title': 'Festival',
                     'event_city': 'Udine, Trieste',
                     'listing_occurrences': ['2026-10-10']}
        metadata = {'detail_title': 'Festival', 'event_city': 'Udine, Trieste',
                    'date_full': '10 ottobre 2026 - 11 ottobre 2026'}
        event = promote_candidate(candidate, metadata)
        self.assertEqual(event['location_confidence'], 'multiple_municipalities')
        self.assertIsNone(event['lat'])
        self.assertIsNone(event['lon'])
        self.assertEqual([place['name'] for place in event['listed_municipalities']],
                         ['Udine', 'Trieste'])
        self.assertIsNone(promote_candidate(
            {**candidate, 'event_city': 'Udine, Aprilia Marittima'},
            {**metadata, 'event_city': 'Udine, Aprilia Marittima'}))

    def test_named_hamlet_venue_uses_its_source_map_point(self):
        city = 'Latisana, Aprilia Marittima'
        candidate = {'source': 'TurismoFVG', 'title': 'Nautilia',
                     'event_city': city, 'listing_occurrences': ['2026-10-17']}
        metadata = {'detail_title': 'Nautilia', 'event_city': city,
                    'date_full': '17 ottobre 2026 - 25 ottobre 2026',
                    'venue': 'Centro Nautico di Aprilia Marittima',
                    'map_lat': 45.69467, 'map_lon': 13.06707}
        event = promote_candidate(candidate, metadata)
        self.assertEqual(event['location_confidence'], 'source_map')
        self.assertEqual((event['lat'], event['lon']), (45.69467, 13.06707))
        self.assertIsNone(promote_candidate(candidate,
            {**metadata, 'venue': 'varie sedi'}))

    def test_official_locality_point_does_not_claim_exact_venue(self):
        candidate = {'source': 'TurismoFVG', 'title': 'Pipistrelli on the rock',
                     'event_city': 'Sistiana',
                     'listing_occurrences': ['2026-10-17']}
        metadata = {'detail_title': 'Pipistrelli on the rock',
                    'event_city': 'Sistiana', 'date_full': '17 ottobre 2026',
                    'venue': 'Sentiero Rilke'}
        event = promote_candidate(candidate, metadata)
        self.assertEqual(event['location_confidence'], 'source_locality')
        self.assertEqual((event['lat'], event['lon']), (45.7728922, 13.6391125))
        self.assertEqual(event['location_source_url'],
                         'https://www.turismofvg.it/sistiana')

    def test_calendar_series_title_can_lead_to_more_specific_detail(self):
        candidate = {'source': 'TurismoFVG',
                     'title': 'FILA A TEATRO - XII edizione della rassegna',
                     'event_city': 'Maniago',
                     'listing_occurrences': ['2026-10-25'],
                     'discovery_kind': 'filtered_calendar'}
        metadata = {'detail_title': 'FILA A TEATRO 2026-2027 - XII edizione: I vestiti nuovi',
                    'event_city': 'Maniago', 'date_full': '25 ottobre 2026'}
        self.assertEqual(promote_candidate(candidate, metadata)['title'],
                         metadata['detail_title'])
        self.assertIsNone(promote_candidate(candidate,
            {**metadata, 'date_full': '26 ottobre 2026'}))

    def test_bookable_experience_requires_no_published_program(self):
        metadata = {'date_full': '12 giugno 2026 - 31 dicembre 2027',
                    'provider_categories': 'Enogastronomia, Strada del vino e dei sapori'}
        rows = ['solo su prenotazione, entro le 20:00 del giorno precedente']
        description = 'Un’esperienza guidata con degustazione in cantina. Ogni portata incontra un vino.'
        self.assertTrue(unscheduled_bookable_experience(metadata, description, rows))
        self.assertFalse(unscheduled_bookable_experience(
            metadata, 'Esperienza guidata il 24 ottobre con degustazione.', rows))
        self.assertFalse(unscheduled_bookable_experience(
            {**metadata, 'occurrences': ['2026-10-24']}, description, rows))
        self.assertFalse(unscheduled_bookable_experience(
            {**metadata, 'provider_categories': 'Mostre'}, description, rows))

    @patch('app.events.pilot_details.engine.extract_turismofvg_description',
           return_value='Un’esperienza guidata con degustazione in cantina.')
    @patch('app.events.pilot_details.engine.extract_turismofvg_detail_metadata',
           return_value={'date_full': '12 giugno 2026 - 31 dicembre 2027',
                         'event_city': 'Cormons',
                         'provider_categories': 'Enogastronomia, Strada del vino e dei sapori'})
    def test_bookable_experience_excluded_and_cached(self, metadata, description):
        candidate = {**self.candidate(), 'url': 'https://www.turismofvg.it/eventi/cjarsons-e-vino',
                     'title': 'Cjarsons e Vino', 'event_city': 'Cormons'}
        html = ('<h1>Cjarsons e Vino</h1><div class="body_col2">'
                '<div style="background-image: url(icn__people.svg)">'
                'solo su prenotazione, entro le 20:00 del giorno precedente</div>'
                '<div class="c-detail__actions"></div>')
        result = enrich_details([candidate], fetch_html=lambda _: html)
        self.assertEqual(result['events'], [])
        self.assertEqual(result['detail_candidates'], [])
        self.assertEqual(result['scope_excluded'][0]['reason'], 'reservation_only_experience')
        cached = enrich_details([candidate], fetch_html=lambda _: self.fail('network'),
                                previous_cache=result['detail_cache'], max_urls=0)
        self.assertEqual(cached['scope_excluded'][0]['url'], candidate['url'])
        dated = enrich_details([{**candidate, 'listing_occurrences': ['2026-10-24']}],
                               fetch_html=lambda _: self.fail('network'),
                               previous_cache=result['detail_cache'], max_urls=0)
        self.assertEqual(dated['scope_excluded'], [])
        self.assertEqual(dated['review_required'][0]['review_reason'],
                         'bookable_experience_with_dated_listing')

    def test_prefetch_retains_each_url_and_failure_for_ordered_verification(self):
        from time import monotonic
        def fetch(url):
            if url == 'bad':
                raise TimeoutError('slow detail')
            return '<h1>Evento</h1>'
        fetched = prefetch_details(['good', 'bad'], fetch,
                                   deadline=monotonic() + 30, max_workers=2, batch_size=2)
        self.assertEqual(fetched['good'], '<h1>Evento</h1>')
        self.assertIsInstance(fetched['bad'], TimeoutError)

    @patch('app.events.pilot_details.engine.extract_turismofvg_description',
           return_value='Programma disponibile.')
    @patch('app.events.pilot_details.engine.extract_turismofvg_detail_metadata',
           return_value={'date_full': '12 settembre 2026', 'event_city': 'Udine'})
    def test_large_detail_budget_requires_deadline(self, metadata, description):
        from time import monotonic
        items = [{**self.candidate(), 'url': f'https://www.turismofvg.it/eventi/item-{n}'}
                 for n in range(101)]
        with self.assertRaisesRegex(ValueError, 'deadline required'):
            enrich_details(items, fetch_html=lambda _: '<h1>Festa</h1>', max_urls=101)
        result = enrich_details(items, fetch_html=lambda _: '<h1>Festa</h1>',
                                max_urls=101, deadline=monotonic() + 10)
        self.assertEqual(len(result['events']), 101)

    @patch('app.events.pilot_details.time.monotonic', return_value=1)
    @patch('app.events.pilot_details.engine.extract_turismofvg_description', return_value='Programma disponibile.')
    @patch('app.events.pilot_details.engine.extract_turismofvg_detail_metadata', return_value={'date_full': '12 settembre 2026', 'event_city': 'Udine'})
    def test_deadline_budget_has_no_twenty_url_ceiling(self, metadata, description, clock):
        items = [{**self.candidate(), 'url': f'https://www.turismofvg.it/eventi/item-{n}'} for n in range(25)]
        result = enrich_details(items, fetch_html=lambda _: '<h1>Festa</h1>', max_urls=None, deadline=2)
        self.assertEqual(len(result['events']), 25)
        self.assertEqual(result['detail_urls_checked'], 25)
        expired = enrich_details(items, fetch_html=lambda _: self.fail('expired network'), max_urls=None, deadline=0)
        self.assertEqual(expired['detail_urls_checked'], 0)
        self.assertEqual(len(expired['detail_candidates']), 25)

    @patch('app.events.pilot_details.engine.extract_turismofvg_description', return_value='Programma disponibile.')
    @patch('app.events.pilot_details.engine.extract_turismofvg_detail_metadata', return_value={'date_full': '12 settembre 2026', 'event_city': 'Udine'})
    def test_shared_budget_is_twenty_unique_urls(self, metadata, description):
        items = [{**self.candidate(), 'url': f'https://www.turismofvg.it/eventi/item-{n}'} for n in range(25)]
        calls = []
        result = enrich_details(items, fetch_html=lambda url: calls.append(url) or '<h1>Festa</h1>', max_urls=20)
        self.assertEqual(len(calls), 20)
        self.assertEqual(len(result['events']), 20)
        self.assertEqual(len(result['detail_candidates']), 5)

    @patch('app.events.pilot_details.engine.extract_turismofvg_description', return_value='Programma disponibile.')
    @patch('app.events.pilot_details.engine.extract_turismofvg_detail_metadata', return_value={'date_full': '12 settembre 2026', 'event_city': 'Trieste'})
    def test_conflicting_town_does_not_promote(self, metadata, description):
        result = enrich_details([self.candidate()], fetch_html=lambda _: '<h1>Festa</h1>')
        self.assertEqual(result['events'], [])
        self.assertEqual(len(result['detail_candidates']), 1)

    @patch('app.events.pilot_details.engine.extract_turismofvg_description', return_value='Programme available.')
    @patch('app.events.pilot_details.engine.extract_turismofvg_detail_metadata', return_value={
        'date_full': 'Saturday, October 3, 2026 - Saturday, October 10, 2026',
        'event_city': 'Pordenone',
    })
    def test_translated_highlight_is_promoted_only_with_matching_city_and_date_hint(self, metadata, description):
        event = {
            'source': 'TurismoFVG',
            'url': 'https://www.turismofvg.it/eventi/45-le-giornate-del-cinema-muto',
            'title': '45° Le Giornate del Cinema Muto',
            'event_city': 'Pordenone',
            'date_hint': '3 OTTOBRE 2026',
            'discovery_kind': 'highlight',
        }
        result = enrich_details([event], fetch_html=lambda _: '<h1>45th Silent Film Days</h1>')
        self.assertEqual(result['events'][0]['title'], '45th Silent Film Days')
        self.assertEqual(result['events'][0]['start_date'], '2026-10-03')
        self.assertEqual(result['events'][0]['end_date'], '2026-10-10')

        wrong_hint = enrich_details(
            [{**event, 'date_hint': '4 OTTOBRE 2026'}],
            fetch_html=lambda _: '<h1>45th Silent Film Days</h1>',
        )
        self.assertEqual(wrong_hint['events'], [])
        self.assertEqual(len(wrong_hint['detail_candidates']), 1)

    def candidate(self):
        return dict(source='TurismoFVG', url='https://www.turismofvg.it/eventi/festa',
                    title='Festa', event_city='Udine', discovery_kind='listing')

    def test_filtered_calendar_dates_resolve_yearless_recurrence(self):
        candidate = {**self.candidate(), 'title': 'Mercatino',
                     'event_city': 'Gemona del Friuli',
                     'listing_occurrences': ['2026-10-04', '2026-11-01', '2026-12-06']}
        detail = {'detail_title': 'Mercatino', 'event_city': 'Gemona del Friuli',
                  'date_full': 'Ogni prima domenica del mese (escluso agosto)'}
        event = promote_candidate(candidate, detail)
        self.assertEqual(event['occurrences'], candidate['listing_occurrences'])
        self.assertEqual(event['start_date'], '2026-10-04')
        self.assertEqual(event['end_date'], '2026-12-06')

    def test_sparse_calendar_preserves_labelled_detail_period(self):
        candidate = {**self.candidate(), 'title': 'Escursioni',
                     'event_city': 'Caneva',
                     'listing_occurrences': ['2026-10-04']}
        detail = {'detail_title': 'Escursioni', 'event_city': 'Caneva',
                  'date_full': 'domenica 10 maggio 2026 - domenica 4 ottobre 2026'}
        event = promote_candidate(candidate, detail)
        self.assertNotIn('occurrences', event)
        self.assertEqual(event['schedule_kind'], 'interval')
        self.assertEqual(event['start_date'], '2026-05-10')
        self.assertEqual(event['end_date'], '2026-10-04')
        self.assertEqual(event['date_evidence'], detail['date_full'])

    def test_programme_excerpt_does_not_shorten_labelled_period(self):
        candidate = {**self.candidate(), 'title': 'Amelie - Il Musical',
                     'listing_occurrences': ['2026-10-16', '2026-10-17',
                                             '2026-10-18', '2026-10-19']}
        detail = {'detail_title': 'Amelie - Il Musical', 'event_city': 'Udine',
                  'date_full': 'venerdì 16 ottobre 2026 - lunedì 19 ottobre 2026'}
        event = promote_candidate(candidate, detail)
        self.assertEqual(event['start_date'], '2026-10-16')
        self.assertEqual(event['end_date'], '2026-10-19')
        self.assertEqual(event['schedule_kind'], 'interval')
        self.assertNotIn('occurrences', event)
        self.assertEqual(event['date_evidence'], detail['date_full'])

    @patch('app.events.pilot_details.engine.extract_turismofvg_description', return_value='Programma disponibile.')
    @patch('app.events.pilot_details.engine.extract_turismofvg_detail_metadata', return_value={'date_full': '12 settembre 2026', 'event_city': 'Udine'})
    def test_candidate_promoted_and_cached_without_extra_requests(self, metadata, description):
        result = enrich_details([self.candidate()], fetch_html=lambda _: '<h1>Festa</h1>', max_urls=1)
        self.assertEqual(result['events'][0]['start_date'], '2026-09-12')
        self.assertNotIn('description', result['events'][0])
        again = enrich_details([self.candidate()], fetch_html=lambda _: self.fail('network'),
                               previous_cache=result['detail_cache'], max_urls=0)
        self.assertEqual(len(again['events']), 1)
        self.assertEqual(again['detail_urls_checked'], 0)

    @patch('app.events.pilot_details.engine.extract_turismofvg_description', return_value=None)
    @patch('app.events.pilot_details.engine.extract_turismofvg_detail_metadata',
           return_value={'date_full': '12 settembre 2026', 'event_city': 'Udine'})
    def test_structured_detail_without_description_is_still_verified(self, metadata, description):
        result = enrich_details([self.candidate()], fetch_html=lambda _: '<h1>Festa</h1>')
        self.assertEqual(result['events'][0]['start_date'], '2026-09-12')
        self.assertEqual(result['events'][0]['detail_status'], 'inspected')

    @patch('app.events.pilot_details.engine.extract_turismofvg_description', return_value='Programma disponibile.')
    @patch('app.events.pilot_details.engine.extract_turismofvg_detail_metadata', return_value={'date_full': 'dal 12 al 14 settembre 2026', 'event_city': 'Udine'})
    def test_legacy_range_is_preserved_without_generated_occurrences(self, metadata, description):
        result = enrich_details([self.candidate()], fetch_html=lambda _: '<h1>Festa</h1>')
        self.assertEqual(result['events'][0]['start_date'], '2026-09-12')
        self.assertEqual(result['events'][0]['end_date'], '2026-09-14')
        self.assertEqual(result['events'][0]['schedule_kind'], 'interval')
        self.assertNotIn('occurrences', result['events'][0])

    def test_candidates_without_budget_never_leak_into_catalog(self):
        result = enrich_details([self.candidate()], fetch_html=lambda _: self.fail('network'), max_urls=0)
        self.assertEqual(result['events'], [])
        self.assertEqual(len(result['detail_candidates']), 1)

    @patch("app.events.pilot_details.engine.extract_turismofvg_detail_metadata", return_value={})
    @patch("app.events.pilot_details.engine.extract_turismofvg_description", return_value=None)
    def test_empty_detail_never_clears_previous_warning(self, description, metadata):
        event = self.event("2026-09-12")
        previous = {event['url']: {'checked_at': '2026-01-01T00:00:00+00:00', 'notice': True}}
        result = enrich_details([event], fetch_html=lambda _: '<html>Consent</html>', previous_cache=previous)
        self.assertEqual(result['events'], [])
        self.assertTrue(result['detail_cache'][event['url']]['notice'])

    @patch("app.events.pilot_details.engine.extract_turismofvg_detail_metadata", return_value={})
    @patch("app.events.pilot_details.engine.extract_turismofvg_description", return_value=None)
    def test_empty_detail_is_unavailable_not_inspected(self, description, metadata):
        result = enrich_details([self.event('2026-09-12')], fetch_html=lambda _: 'html')
        self.assertEqual(result['events'][0]['detail_status'], 'unavailable')
        verdict = result['detail_cache'][self.event('2026-09-12')['url']]
        self.assertIn('last_attempt_at', verdict)
        self.assertNotIn('checked_at', verdict)

    @patch('app.events.pilot_details.enrich_details')
    @patch('app.events.pilot_regional.collect_regional')
    def test_wrapper_preserves_listing_review_evidence(self, collect, enrich):
        from app.events.pilot_details import collect_regional_with_details
        collect.return_value = {'events': [], 'review_required': [{'review_reason': 'missing_explicit_event_date'}]}
        enrich.return_value = {'events': [], 'review_required': [{'review_reason': 'possible_schedule_change'}]}
        result = collect_regional_with_details()
        self.assertEqual(len(result['review_required']), 2)

    @patch('app.events.pilot_details.engine.extract_turismofvg_description', return_value='Programma disponibile.')
    @patch('app.events.pilot_details.engine.extract_turismofvg_detail_metadata', return_value={'date_full': '12 settembre 2026', 'event_city': 'Udine', 'time': '16:00', 'venue': 'Teatro'})
    def test_existing_listing_receives_verified_detail_fields(self, metadata, description):
        event = {**self.event('2026-09-12'), 'event_city': 'Udine'}
        result = enrich_details([event], fetch_html=lambda _: '<h1>Festa</h1>')
        self.assertEqual(result['events'][0]['time'], '16:00')
        self.assertEqual(result['events'][0]['venue'], 'Teatro')
        conflict = enrich_details([{**event, 'time': '18:00'}], fetch_html=lambda _: '<h1>Festa</h1>')
        self.assertEqual(conflict['events'], [])
        self.assertEqual(conflict['review_required'][0]['review_reason'], 'listing_detail_conflict')

    @patch('app.events.pilot_details.prefetch_details', return_value={})
    @patch('app.events.pilot_details.enrich_details')
    @patch('app.events.pilot_regional.collect_regional')
    def test_failed_attempt_rotates_behind_unchecked_candidates(self, collect, enrich, prefetch):
        from app.events.pilot_details import collect_regional_with_details
        first = self.candidate()
        second = {**first, 'url': 'https://www.turismofvg.it/eventi/second'}
        collect.return_value = {'events': [], 'detail_candidates': [first, second]}
        enrich.return_value = {}
        collect_regional_with_details({first['url']: {'last_attempt_at': '2026-09-07T00:00:00+00:00'}})
        self.assertEqual(enrich.call_args.args[0][0]['url'], second['url'])
        self.assertEqual(enrich.call_args.kwargs['max_urls'], 0)
        self.assertIsNotNone(enrich.call_args.kwargs['deadline'])

    def test_cached_notice_remains_quarantined_without_network_budget(self):
        event = self.event("2026-09-12")
        cache = {event["url"]: {"checked_at": "2026-01-01T00:00:00+00:00", "notice": True}}
        result = enrich_details([event], fetch_html=lambda _: self.fail("network"), max_urls=0, previous_cache=cache)
        self.assertEqual(result["events"], [])
        self.assertEqual(result["detail_cache"], cache)

    def event(self, day):
        return dict(source="TurismoFVG", url="https://www.turismofvg.it/eventi/festa",
                    start_date=day, title="Festa")

    @patch("app.events.pilot_details.engine.extract_turismofvg_detail_metadata", return_value={
        "date_full": "12 settembre 2026", "event_city": "Udine", "detail_title": "Festa",
    })
    @patch("app.events.pilot_details.engine.extract_turismofvg_description", return_value="Programma verificato.")
    def test_one_fetch_per_url_and_explicit_excerpt_gate(self, description, metadata):
        calls = []
        fetch = lambda url: calls.append(url) or "<h1>Festa</h1>"
        events = [self.event("2026-09-12"), self.event("2026-09-12")]
        result = enrich_details(events, fetch_html=fetch)
        self.assertEqual(len(calls), 1)
        self.assertNotIn("description", result["events"][0])
        result = enrich_details(events, fetch_html=fetch, allow_description_excerpt=True)
        self.assertEqual(result["events"][1]["description_excerpt"], "Programma verificato.")
        self.assertEqual(result["events"][1]["description_source_name"], "TurismoFVG")
        self.assertEqual(result["events"][1]["description_source_url"], events[1]["url"])
        self.assertNotIn("description", result["events"][1])
        self.assertEqual(result["events"][1]["start_date"], "2026-09-12")
        self.assertNotIn("detail_status", events[0])

        cached = enrich_details(events, fetch_html=lambda _: self.fail("network"),
                                allow_description_excerpt=True,
                                previous_cache=result["detail_cache"], max_urls=0)
        self.assertEqual(cached["events"][0]["description_excerpt"], "Programma verificato.")
        self.assertEqual(cached["detail_urls_checked"], 0)

    @patch("app.events.pilot_details.engine.extract_turismofvg_detail_metadata", return_value={
        "date_full": "12 settembre 2026", "event_city": "Udine", "detail_title": "Un altro evento",
    })
    @patch("app.events.pilot_details.engine.extract_turismofvg_description", return_value="Testo di un altro evento verificato.")
    def test_excerpt_is_not_attached_without_verified_page_identity(self, description, metadata):
        result = enrich_details([self.event("2026-09-12")],
                                fetch_html=lambda _: "<h1>Un altro evento</h1>",
                                allow_description_excerpt=True)
        self.assertEqual(result['events'], [])
        self.assertEqual(result['review_required'][0]['review_reason'],
                         'listing_detail_identity_or_schedule_conflict')

    def test_listing_badges_verify_every_discrete_day(self):
        metadata = {'date_full': '10, 11 /17, 18 / 24, 25 ottobre 2026',
                    'event_city': 'Polcenigo', 'detail_title': '40ª Sagra della Castagna'}
        candidate = {'title': '40ª Sagra della Castagna', 'event_city': 'Polcenigo',
                     'listing_day_months': ['10 ottobre', '17 ottobre', '24 ottobre']}
        event = promote_candidate(candidate, metadata)
        self.assertEqual(event['occurrences'], ['2026-10-10', '2026-10-11', '2026-10-17',
                                                '2026-10-18', '2026-10-24', '2026-10-25'])
        self.assertIsNone(promote_candidate({**candidate,
            'listing_day_months': ['10 ottobre', '19 ottobre']}, metadata))

    def test_discrete_dates_across_months_use_all_explicit_days(self):
        metadata = {'date_full': '26, 27 settembre / 3, 4 / 10, 11 ottobre 2026',
                    'event_city': 'Reana del Rojale',
                    'detail_title': '46ª Mostra Mercato Regionale della Patata'}
        candidate = {'title': metadata['detail_title'],
                     'event_city': 'Reana del Rojale',
                     'discovery_kind': 'filtered_calendar',
                     'listing_occurrences': ['2026-09-26', '2026-09-27',
                                             '2026-10-03', '2026-10-04',
                                             '2026-10-10', '2026-10-11']}
        event = promote_candidate(candidate, metadata)
        self.assertEqual(event['occurrences'], candidate['listing_occurrences'])
        self.assertEqual((event['start_date'], event['end_date']),
                         ('2026-09-26', '2026-10-11'))
        self.assertIsNone(promote_candidate({**candidate,
            'listing_occurrences': candidate['listing_occurrences'] + ['2026-10-12']}, metadata))

    def test_labelled_calendar_must_be_fully_parsed(self):
        metadata = {'date_full': 'dal 10 al 25 ottobre 2026'}
        self.assertEqual(calendar_occurrences(metadata,
            'Calendario: 10, 11 /17, 18 /24, 25 ottobre Orario: 10:00'),
            ['2026-10-10', '2026-10-11', '2026-10-17',
             '2026-10-18', '2026-10-24', '2026-10-25'])
        self.assertEqual(calendar_occurrences(metadata, 'Calendario: date da confermare'), [])

    @patch('app.events.pilot_details.engine.extract_turismofvg_description',
           return_value='Calendario: date da confermare')
    @patch('app.events.pilot_details.engine.extract_turismofvg_detail_metadata',
           return_value={'date_full': 'dal 10 al 25 ottobre 2026', 'event_city': 'Udine'})
    def test_unparsed_labelled_calendar_stays_pending(self, metadata, description):
        result = enrich_details([self.candidate()],
                                fetch_html=lambda _: '<h1>Festa</h1>')
        self.assertEqual(result['events'], [])
        self.assertEqual(len(result['detail_candidates']), 1)

    @patch('app.events.pilot_details.prefetch_details', return_value={})
    @patch('app.events.pilot_details.enrich_details')
    @patch('app.events.pilot_regional.collect_regional')
    def test_unresolved_detail_cannot_be_marked_complete(self, collect, enrich, prefetch):
        from app.events.pilot_details import collect_regional_with_details
        candidate = self.candidate()
        collect.return_value = {'status': 'ok', 'events': [], 'pages': 1,
                                'declared_results': 1, 'cards_seen': 1,
                                'detail_candidates': [candidate],
                                'review_required': [{'url': candidate['url'],
                                                     'reason': 'missing_explicit_event_date'}]}
        enrich.return_value = {'events': [], 'detail_candidates': [candidate],
                               'review_required': [], 'detail_cache': {}}
        result = collect_regional_with_details()
        self.assertEqual(result['status'], 'error')
        self.assertEqual(result['error_type'], 'incomplete_source')
        self.assertEqual(result['verification']['unresolved_count'], 1)

    @patch('app.events.pilot_details.prefetch_details', return_value={})
    @patch('app.events.pilot_details.enrich_details')
    @patch('app.events.pilot_regional.collect_regional')
    def test_scope_exclusion_resolves_listing_review(self, collect, enrich, prefetch):
        from app.events.pilot_details import collect_regional_with_details
        candidate = self.candidate()
        collect.return_value = {'status': 'ok', 'events': [], 'pages': 1,
                                'declared_results': 1, 'cards_seen': 1,
                                'detail_candidates': [candidate],
                                'review_required': [{'url': candidate['url'],
                                                     'reason': 'missing_explicit_event_date'}]}
        enrich.return_value = {'events': [], 'detail_candidates': [],
                               'review_required': [], 'detail_cache': {},
                               'scope_excluded': [{'url': candidate['url'],
                                                   'reason': 'reservation_only_experience'}]}
        result = collect_regional_with_details()
        self.assertEqual(result['verification']['unresolved_count'], 0)
        self.assertEqual(result['verification']['scope_excluded_count'], 1)
        self.assertEqual(result['review_required'], [])

    @patch('app.events.pilot_details.engine.extract_turismofvg_detail_metadata', return_value={
        'date_full': 'giovedì 20 agosto 2026 - sabato 3 ottobre 2026',
        'event_city': 'Pordenone',
    })
    @patch('app.events.pilot_details.engine.extract_turismofvg_description',
           return_value='La mostra racconta la storia del quotidiano e della comunità attraverso fotografie e prime pagine.')
    def test_verified_truncated_listing_receives_attributed_excerpt(self, description, metadata):
        title = 'Mostra "Testimoni del tempo - Il Messaggero Veneto: ottant’anni di Friuli tra cronaca, cultura e comunità"'
        event = {
            'source': 'TurismoFVG',
            'url': 'https://www.turismofvg.it/eventi/mostra-testimoni-del-tempo',
            'title': 'Mostra "Testimoni del tempo - Il Messaggero Veneto: ottant’anni di Friuli tra cronaca,...',
            'event_city': 'Pordenone',
            'start_date': '2026-08-20',
            'end_date': '2026-10-03',
        }
        result = enrich_details([event], fetch_html=lambda _: f'<h1>{title}</h1>',
                                allow_description_excerpt=True)
        enriched = result['events'][0]
        self.assertEqual(enriched['detail_status'], 'inspected')
        self.assertEqual(enriched['description_source_name'], 'TurismoFVG')
        self.assertEqual(enriched['description_source_url'], event['url'])
        self.assertIn('storia del quotidiano', enriched['description_excerpt'])

        damaged = {**event, 'title': 'Mostra "Testimoni del tempo - Il Messaggero Veneto: ottant’anni di Friuli tra cronaca, cultura e comunit�\xa0"'}
        recovered = enrich_details([damaged], fetch_html=lambda _: f'<h1>{title}</h1>',
                                   allow_description_excerpt=True)['events'][0]
        self.assertEqual(recovered['title'], title)
        self.assertEqual(recovered['description_source_url'], event['url'])

    @patch("app.events.pilot_details.engine.extract_turismofvg_detail_metadata", return_value={})
    @patch("app.events.pilot_details.engine.extract_turismofvg_description", return_value="Evento annullato")
    def test_schedule_notice_quarantines_every_occurrence(self, description, metadata):
        result = enrich_details([self.event("2026-09-12")], fetch_html=lambda _: "html")
        self.assertEqual(result["events"], [])
        self.assertEqual(len(result["review_required"]), 1)

    def test_budget_and_network_failure_do_not_create_text(self):
        event = self.event("2026-09-12")
        result = enrich_details([event], fetch_html=lambda _: self.fail("network"), max_urls=0)
        self.assertEqual(result["events"][0]["detail_status"], "pending")
        def fail(_):
            raise TimeoutError()
        result = enrich_details([event], fetch_html=fail)
        self.assertEqual(result["events"][0]["detail_status"], "unavailable")
