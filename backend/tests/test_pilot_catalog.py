import unittest
from datetime import datetime
from app.events.pilot_catalog import merge_collection, query_catalog, PILOT_PROJECT

NOW = "2026-09-06T18:00:00Z"
REAL_QUERY = query_catalog
def query_catalog(*args, **kwargs):
    kwargs.setdefault("now", datetime.fromisoformat(NOW))
    return REAL_QUERY(*args, **kwargs)

class PilotCatalogTests(unittest.TestCase):
    def test_named_sagra_keeps_one_card_and_enters_sagre_filter(self):
        regional = {'title': 'Sagra del Rosario', 'source': 'TurismoFVG',
                    'url': 'https://www.turismofvg.it/eventi/sagra-del-rosario',
                    'event_city': 'Caneva', 'place': 'Caneva',
                    'start_date': '2026-10-02', 'end_date': '2026-10-18',
                    'lat': 45.968, 'lon': 12.452, 'category': 'musica'}
        sagra = {**regional, 'source': 'SagreFVG',
                 'url': 'https://sagrefvg.it/sagre/caneva/', 'category': None}
        catalog = merge_collection(PILOT_PROJECT, None, {
            'TurismoFVG': {'status': 'ok', 'events': [regional]},
            'SagreFVG': {'status': 'ok', 'events': [sagra]}},
            '2026-10-08T08:00:00Z')
        visible = query_catalog(catalog, 45.968, 12.452,
                                now=datetime.fromisoformat('2026-10-08T08:00:00Z'))['events']
        self.assertEqual(len(visible), 1)
        self.assertEqual(visible[0]['category'], 'sagra')
        self.assertEqual(len(visible[0]['source_urls']), 2)

    def test_concert_at_a_sagra_keeps_its_music_category(self):
        event = {'title': 'Concerto alla Sagra del Rosario', 'source': 'TurismoFVG',
                 'url': 'https://www.turismofvg.it/eventi/concerto-rosario',
                 'event_city': 'Caneva', 'start_date': '2026-10-10',
                 'lat': 45.968, 'lon': 12.452, 'category': 'musica'}
        catalog = merge_collection(PILOT_PROJECT, None,
                                   {'TurismoFVG': {'status': 'ok', 'events': [event]}},
                                   '2026-10-08T08:00:00Z')
        visible = query_catalog(catalog, 45.968, 12.452,
                                now=datetime.fromisoformat('2026-10-08T08:00:00Z'))['events']
        self.assertEqual(visible[0]['category'], 'musica')

    def test_numbered_sagre_enter_sagre_filter(self):
        for title in ('40\ufffd Sagra della Castagna', '1\ufffd Sagra da la Cjavrute',
                      '39a Sagra della Castagna', '40ª Sagra della Castagna',
                      '40° Sagra della Castagna'):
            with self.subTest(title=title):
                event = {'title': title, 'source': 'TurismoFVG',
                         'url': 'https://www.turismofvg.it/eventi/sagra-numerata',
                         'event_city': 'Polcenigo', 'start_date': '2026-10-10',
                         'lat': 46.04, 'lon': 12.50, 'category': 'food_wine'}
                catalog = merge_collection(PILOT_PROJECT, None,
                                           {'TurismoFVG': {'status': 'ok', 'events': [event]}},
                                           '2026-10-08T08:00:00Z')
                visible = query_catalog(catalog, 46.04, 12.50,
                                        now=datetime.fromisoformat('2026-10-08T08:00:00Z'))['events']
                self.assertEqual(visible[0]['category'], 'sagra')

    def test_query_shows_one_best_card_for_two_verified_sources(self):
        official = {'source': 'CSS Udine', 'url': 'https://cssudine.it/spettacolo/a/',
                    'title': 'Lo spettacolo', 'event_city': 'Udine',
                    'venue': 'Teatro Palamostre', 'place': 'Teatro Palamostre, Udine',
                    'start_date': '2026-11-12', 'end_date': '2026-11-12',
                    'lat': 46.0635, 'lon': 13.2358,
                    'location_confidence': 'municipality'}
        regional = {**official, 'source': 'TurismoFVG',
                    'url': 'https://www.turismofvg.it/eventi/lo-spettacolo',
                    'place': 'Udine',
                    'description_excerpt': 'Una descrizione verificata della rappresentazione.',
                    'description_source_name': 'TurismoFVG',
                    'description_source_url': 'https://www.turismofvg.it/eventi/lo-spettacolo',
                    'description_checked_at': '2026-10-07T08:00:00Z'}
        catalog = merge_collection(PILOT_PROJECT, None, {
            'TurismoFVG': {'status': 'ok', 'events': [regional]},
            'CSS Udine': {'status': 'ok', 'events': [official]},
        }, '2026-10-07T08:00:00Z')
        visible = query_catalog(catalog, 46.0635, 13.2358,
                                now=datetime.fromisoformat('2026-10-07T08:00:00Z'))['events']
        self.assertEqual(len(visible), 1)
        self.assertEqual(visible[0]['source'], 'CSS Udine')
        self.assertEqual(visible[0]['description_source_name'], 'TurismoFVG')
        self.assertEqual(len(visible[0]['source_urls']), 2)

    def test_multi_municipality_card_qualifies_near_either_town_once(self):
        event = {'source': 'TurismoFVG', 'url': 'https://www.turismofvg.it/eventi/festival',
                 'title': 'Festival', 'event_city': 'Udine, Trieste',
                 'start_date': '2026-09-07', 'end_date': '2026-09-08',
                 'lat': None, 'lon': None,
                 'location_confidence': 'multiple_municipalities',
                 'listed_municipalities': [
                     {'name': 'Udine', 'lat': 46.0635, 'lon': 13.2358},
                     {'name': 'Trieste', 'lat': 45.6495, 'lon': 13.7768}]}
        catalog = merge_collection(PILOT_PROJECT, None,
                                   {'TurismoFVG': {'status': 'ok', 'events': [event]}}, NOW)
        for lat, lon in ((46.0635, 13.2358), (45.6495, 13.7768)):
            found = query_catalog(catalog, lat, lon)['events']
            self.assertEqual(len(found), 1)
            self.assertNotIn('distance_km', found[0])
            self.assertEqual(found[0]['event_city'], 'Udine, Trieste')
        self.assertEqual(query_catalog(catalog, 45.9567, 12.6605, 5)['events'], [])

    def test_query_preserves_conflicting_end_times_and_occurrences(self):
        event = dict(title='Festa', source='TurismoFVG', url='https://www.turismofvg.it/eventi/festa',
                     event_city='Udine', lat=46, lon=13, start_date='2026-09-07',
                     end_date='2026-09-09', time='18:00', end_time='19:00')
        for changed in ({'end_time': '20:00'}, {'occurrences': ['2026-09-07', '2026-09-09']},
                        {'title': 'Altro incontro'}):
            with self.subTest(changed=changed):
                catalog = merge_collection(PILOT_PROJECT, None, {'test': {'status': 'ok',
                    'events': [event, {**event, **changed}]}}, NOW)
                self.assertEqual(len(query_catalog(catalog, 46, 13)['events']), 2)

    def test_legacy_exact_and_pilot_venue_have_same_precision(self):
        for confidence in ('exact', 'venue'):
            catalog = self.catalog()
            catalog['sources']['test']['events'][0]['location_confidence'] = confidence
            self.assertFalse(query_catalog(catalog, 46, 13)['events'][0]['distance_is_approximate'])

    def test_unavailable_source_does_not_break_valid_results(self):
        catalog = self.catalog()
        catalog['sources']['offline'] = {'status': 'unavailable', 'updated_at': None, 'events': []}
        self.assertTrue(query_catalog(catalog, 46, 13)['events'])
    def catalog(self):
        return merge_collection(PILOT_PROJECT, None, {"test": {"status": "ok", "events": [
            {"title": "near", "lat": 46, "lon": 13, "start_date": "2026-09-06"},
            {"title": "farther", "lat": 46.2, "lon": 13, "start_date": "2026-09-07"},
            {"title": "unknown", "lat": None, "lon": None, "start_date": "2026-09-06"}]}}, NOW)

    def test_expired_snapshot_is_not_served(self):
        self.assertEqual(query_catalog(self.catalog(), 46, 13, now=datetime.fromisoformat("2026-09-09T18:00:00Z"))["events"], [])

    def test_past_and_undated_events_are_hidden(self):
        catalog = self.catalog()
        catalog["sources"]["test"]["events"][0]["start_date"] = "2026-09-05"
        del catalog["sources"]["test"]["events"][1]["start_date"]
        self.assertEqual(query_catalog(catalog, 46, 13)["events"], [])

    def test_municipality_distance_is_approximate(self):
        self.assertTrue(query_catalog(self.catalog(), 46, 13)["events"][0]["distance_is_approximate"])

    def test_rejects_beta(self):
        with self.assertRaises(ValueError):
            merge_collection("meteo-friul", None, {}, NOW)

    def test_failure_retains_last_source(self):
        old = self.catalog()
        new = merge_collection(PILOT_PROJECT, old, {"test": {"status": "error"}}, NOW)
        self.assertEqual(len(new["sources"]["test"]["events"]), 3)
        self.assertEqual(new["sources"]["test"]["status"], "stale")
        self.assertEqual(old["sources"]["test"]["status"], "fresh")
        self.assertEqual(query_catalog(new, 46, 13)['events'], [])

    def test_failed_community_source_is_tagged_but_not_visible(self):
        old = merge_collection(PILOT_PROJECT, None, {'Paesi in Festa': {
            'status': 'ok', 'events': [{'title': 'Sagra', 'source': 'Paesi in Festa',
                                      'start_date': '2026-09-07', 'lat': 46, 'lon': 13}]}}, NOW)
        failed = merge_collection(PILOT_PROJECT, old, {'Paesi in Festa': {
            'status': 'error', 'error_type': 'adapter_exception',
            'exception_type': 'ValueError', 'error_detail': 'invalid listing'}}, NOW)
        batch = failed['sources']['Paesi in Festa']
        self.assertEqual(batch['last_attempt_error_type'], 'adapter_exception')
        self.assertEqual(batch['last_attempt_exception_type'], 'ValueError')
        self.assertEqual(batch['last_attempt_error_detail'], 'invalid listing')
        self.assertEqual(len(batch['events']), 1)
        self.assertEqual(query_catalog(failed, 46, 13)['events'], [])

    def test_paesi_partial_publishes_only_verified_cards(self):
        good = {'title': 'Festa verificata', 'source': 'Paesi in Festa',
                'url': 'https://paesiinfesta.com/good/',
                'start_date': '2026-09-07', 'end_date': '2026-09-08',
                'lat': 46, 'lon': 13}
        bad_url = 'https://paesiinfesta.com/bad/'
        catalog = merge_collection(PILOT_PROJECT, None, {'Paesi in Festa': {
            'status': 'partial', 'events': [good],
            'review_required': [{'url': bad_url, 'reason': 'detail_conflict'}],
            'verification': {'review_count': 1}}}, NOW)
        batch = catalog['sources']['Paesi in Festa']
        self.assertEqual(batch['status'], 'partial')
        self.assertEqual(batch['review_required'][0]['url'], bad_url)
        visible = query_catalog(catalog, 46, 13)['events']
        self.assertEqual([item['url'] for item in visible], [good['url']])
        self.assertEqual(visible[0]['source_status'], 'partial')

    def test_failed_source_can_recover_without_recollecting_other_sources(self):
        day = '2026-09-07'
        primary = {'title': 'Festa', 'source': 'Paesi in Festa', 'url': 'https://example.test/a',
                   'start_date': day, 'lat': 46, 'lon': 13}
        secondary = {**primary, 'source': 'SagreFVG', 'url': 'https://example.test/b'}
        previous = merge_collection(PILOT_PROJECT, None, {
            'Paesi in Festa': {'status': 'ok', 'events': [primary]},
            'SagreFVG': {'status': 'ok', 'events': [secondary]}}, NOW)
        failed = merge_collection(PILOT_PROJECT, previous, {
            'Paesi in Festa': {'status': 'error', 'error_type': 'timeout'}}, NOW)
        self.assertEqual({item['source'] for item in query_catalog(failed, 46, 13)['events']},
                         {'SagreFVG'})
        recovered = merge_collection(PILOT_PROJECT, failed, {
            'Paesi in Festa': {'status': 'ok', 'events': [primary]}}, NOW)
        self.assertEqual(recovered['sources']['SagreFVG'], failed['sources']['SagreFVG'])
        self.assertEqual(recovered['sources']['Paesi in Festa']['status'], 'fresh')
        self.assertNotIn('last_attempt_error_type', recovered['sources']['Paesi in Festa'])
        self.assertEqual({item['source'] for item in query_catalog(recovered, 46, 13)['events']},
                         {'Paesi in Festa', 'SagreFVG'})

    def test_turismofvg_failed_refresh_keeps_checkpoint_but_hides_old_cards(self):
        event = {'source': 'TurismoFVG',
                 'url': 'https://www.turismofvg.it/eventi/festa',
                 'title': 'Festa', 'event_city': 'Udine',
                 'start_date': '2026-09-07', 'end_date': '2026-09-07',
                 'lat': 46.0635, 'lon': 13.2358}
        old = merge_collection(PILOT_PROJECT, None, {
            'TurismoFVG': {'status': 'ok', 'events': [event]}}, NOW)
        failed = merge_collection(PILOT_PROJECT, old, {
            'TurismoFVG': {'status': 'error', 'reason': 'network'}}, NOW)
        self.assertEqual(failed['sources']['TurismoFVG']['status'], 'stale')
        self.assertEqual(len(failed['sources']['TurismoFVG']['events']), 1)
        self.assertEqual(query_catalog(failed, 46.0635, 13.2358)['events'], [])

    def test_failed_rolling_refresh_keeps_last_verified_control(self):
        verified = {'schema': 'turismofvg-current-year-control-v1',
                    'as_of_date': '2026-10-11', 'entries': {'verified': {}}}
        partial = {'schema': 'turismofvg-current-year-control-v1',
                   'as_of_date': '2026-10-11', 'entries': {'partial': {}}}
        old = merge_collection(PILOT_PROJECT, None, {'TurismoFVG': {
            'status': 'ok', 'events': [],
            'year_control': verified}}, NOW)
        failed = merge_collection(PILOT_PROJECT, old, {'TurismoFVG': {
            'status': 'error', 'error_type': 'incomplete_source',
            'verification': {'collection_mode': 'verified-rolling-45-day-window'},
            'year_control': partial}}, NOW)
        self.assertEqual(failed['sources']['TurismoFVG']['status'], 'stale')
        self.assertEqual(failed['sources']['TurismoFVG']['control_checkpoint'],
                         old['sources']['TurismoFVG']['control_checkpoint'])

    def test_azalea_failed_refresh_hides_old_cards(self):
        event = {'source': 'Azalea', 'url': 'https://www.azalea.it/eventi/festa/',
                 'title': 'Festa', 'event_city': 'Udine',
                 'start_date': '2026-09-07', 'end_date': '2026-09-07',
                 'lat': 46.0635, 'lon': 13.2358}
        old = merge_collection(PILOT_PROJECT, None,
                               {'Azalea': {'status': 'ok', 'events': [event]}}, NOW)
        failed = merge_collection(PILOT_PROJECT, old,
                                  {'Azalea': {'status': 'error', 'reason': 'network'}}, NOW)
        self.assertEqual(failed['sources']['Azalea']['status'], 'stale')
        self.assertEqual(len(failed['sources']['Azalea']['events']), 1)
        self.assertEqual(query_catalog(failed, 46.0635, 13.2358)['events'], [])

    def test_css_failed_refresh_hides_old_cards(self):
        event = {'source': 'CSS Udine',
                 'url': 'https://www.cssudine.it/stagione-contatto/2026/123/prova',
                 'title': 'Prova', 'event_city': 'Udine',
                 'start_date': '2026-09-07', 'end_date': '2026-09-07',
                 'lat': 46.0635, 'lon': 13.2358}
        old = merge_collection(PILOT_PROJECT, None,
                               {'CSS Udine': {'status': 'ok', 'events': [event]}}, NOW)
        failed = merge_collection(PILOT_PROJECT, old,
                                  {'CSS Udine': {'status': 'error', 'reason': 'network'}}, NOW)
        self.assertEqual(failed['sources']['CSS Udine']['status'], 'stale')
        self.assertEqual(query_catalog(failed, 46.0635, 13.2358)['events'], [])

    def test_pnpensa_failed_refresh_hides_old_cards(self):
        event = {'source': 'Pordenone Pensa',
                 'url': 'https://www.pnpensa.it/abc-finanza-2026/',
                 'title': 'ABC finanza', 'event_city': 'Pordenone',
                 'start_date': '2026-10-27', 'end_date': '2026-10-27',
                 'lat': 45.95689, 'lon': 12.66051}
        old = merge_collection(PILOT_PROJECT, None,
                               {'Pordenone Pensa': {'status': 'ok', 'events': [event]}}, NOW)
        failed = merge_collection(PILOT_PROJECT, old,
                                  {'Pordenone Pensa': {'status': 'error', 'reason': 'network'}}, NOW)
        self.assertEqual(failed['sources']['Pordenone Pensa']['status'], 'stale')
        self.assertEqual(query_catalog(failed, 45.95689, 12.66051,
                                       now=datetime.fromisoformat('2026-10-07T08:00:00+00:00'))['events'], [])

    def test_verdi_pordenone_failed_refresh_hides_old_cards(self):
        event = {'source': 'Teatro Verdi Pordenone',
                 'url': 'https://teatroverdipordenone.it/spettacolo/prova/',
                 'title': 'Prova', 'event_city': 'Pordenone',
                 'start_date': '2026-10-27', 'end_date': '2026-10-27',
                 'lat': 45.95689, 'lon': 12.66051}
        old = merge_collection(PILOT_PROJECT, None,
                               {'Teatro Verdi Pordenone': {'status': 'ok', 'events': [event]}}, NOW)
        failed = merge_collection(PILOT_PROJECT, old,
                                  {'Teatro Verdi Pordenone': {'status': 'error', 'reason': 'network'}}, NOW)
        self.assertEqual(failed['sources']['Teatro Verdi Pordenone']['status'], 'stale')
        self.assertEqual(query_catalog(failed, 45.95689, 12.66051,
                                       now=datetime.fromisoformat('2026-10-07T08:00:00+00:00'))['events'], [])

    def test_verdi_trieste_failed_refresh_hides_old_cards(self):
        event = {'source': 'Teatro Verdi Trieste',
                 'url': 'https://www.teatroverdi-trieste.com/it/spettacoli/prova/',
                 'title': 'Prova', 'event_city': 'Trieste',
                 'start_date': '2026-10-27', 'end_date': '2026-10-27',
                 'lat': 45.6495, 'lon': 13.7768}
        old = merge_collection(PILOT_PROJECT, None,
                               {'Teatro Verdi Trieste': {'status': 'ok', 'events': [event]}}, NOW)
        failed = merge_collection(PILOT_PROJECT, old,
                                  {'Teatro Verdi Trieste': {'status': 'error', 'reason': 'network'}}, NOW)
        self.assertEqual(failed['sources']['Teatro Verdi Trieste']['status'], 'stale')
        self.assertEqual(query_catalog(failed, 45.6495, 13.7768,
                                       now=datetime.fromisoformat('2026-10-07T08:00:00+00:00'))['events'], [])

    def test_incomplete_source_keeps_verified_events_and_saves_detail_progress(self):
        old = self.catalog()
        old['sources']['test']['detail_cache'] = {'https://example.test/a': {'checked_at': 'before'}}
        result = {'status': 'error', 'error_type': 'incomplete_source',
                  'verification': {'declared_results': 707, 'unresolved_count': 3},
                  'review_required': [{'url': 'https://example.test/b'}],
                  'detail_candidates': [{'url': 'https://example.test/c',
                                         'review_reason': 'detail_not_verified'}],
                  'detail_cache': {'https://example.test/b': {'checked_at': 'after'}}}
        new = merge_collection(PILOT_PROJECT, old, {'test': result}, NOW)
        source = new['sources']['test']
        self.assertEqual(source['status'], 'stale')
        self.assertEqual([event['title'] for event in source['events']],
                         [event['title'] for event in old['sources']['test']['events']])
        self.assertEqual(source['last_attempt_error_type'], 'incomplete_source')
        self.assertEqual(source['last_attempt_verification']['unresolved_count'], 3)
        self.assertEqual(source['last_attempt_pending_count'], 1)
        self.assertEqual({item['url'] for item in source['last_attempt_issues']},
                         {'https://example.test/b', 'https://example.test/c'})
        self.assertEqual(set(source['detail_cache']),
                         {'https://example.test/a', 'https://example.test/b'})
        self.assertEqual(query_catalog(new, 46, 13)['events'], [])

    def test_successful_empty_is_not_failure(self):
        new = merge_collection(PILOT_PROJECT, self.catalog(), {"test": {"status": "ok", "events": []}}, NOW)
        self.assertEqual(new["sources"]["test"]["events"], [])

    def test_radius_without_moving_device(self):
        for radius in range(5, 51, 5):
            self.assertTrue(query_catalog(self.catalog(), 46, 13, radius)["events"])
        self.assertEqual(len(query_catalog(self.catalog(), 46, 13, 20)["events"]), 1)
        self.assertEqual(len(query_catalog(self.catalog(), 46, 13, 30)["events"]), 2)
        self.assertEqual(query_catalog(self.catalog(), 46, 13)["unlocated_count"], 1)

    def test_invalid_coordinates_and_radius(self):
        for lat, radius in [(None, 20), (float("nan"), 20), (91, 20), (46, 500), (46, 12), (46, 0), (46, 55)]:
            with self.assertRaises(ValueError):
                query_catalog(self.catalog(), lat, 13, radius)

    def test_reviewed_cross_source_programme_is_one_card(self):
        sessions = [{
            "source": "Pordenonelegge", "title": f"Sessione {index}",
            "url": f"https://www.pordenonelegge.it/eventi/sessione-{index}",
            "event_city": "Pordenone", "place": f"Pordenone, Sala {index}",
            "lat": 45.9567, "lon": 12.6605, "start_date": day, "end_date": day,
            "time": f"{9+index:02d}:00", "location_confidence": "municipality",
        } for index, day in enumerate(("2026-09-17", "2026-09-20"))]
        regional = {
            "source": "TurismoFVG", "title": "Pordenonelegge 2026",
            "url": "https://www.turismofvg.it/eventi/pordenonelegge-2026",
            "event_city": "Pordenone", "place": "Pordenone", "lat": 45.9567,
            "lon": 12.6605, "start_date": "2026-09-16", "end_date": "2026-09-20",
            "image": "https://example.test/pordenonelegge.jpg",
            "location_confidence": "municipality",
        }
        regional_child = {
            **regional,
            "title": "Scimmia sapiens",
            "url": "https://www.turismofvg.it/eventi/pordenonelegge-scimmia-sapiens",
            "image": "https://example.test/session-poster.jpg",
            "start_date": "2026-09-18",
            "end_date": "2026-09-18",
        }
        catalog = merge_collection(PILOT_PROJECT, None, {
            "Pordenonelegge": {"status": "ok", "events": sessions},
            "TurismoFVG": {"status": "ok", "events": [regional_child, regional]},
        }, "2026-09-17T08:00:00Z")
        result = query_catalog(catalog, 45.9567, 12.6605,
                               now=datetime.fromisoformat("2026-09-17T08:00:00Z"))
        self.assertEqual(len(result["events"]), 1)
        event = result["events"][0]
        self.assertEqual(event["title"], "Pordenonelegge 2026")
        self.assertEqual(event["start_date"], "2026-09-16")
        self.assertEqual(event["end_date"], "2026-09-20")
        self.assertEqual(event["active_session_count"], 2)
        self.assertNotIn("session_count", event)
        self.assertEqual(event["venue"], "Più sedi")
        self.assertEqual(event["image"], "https://example.test/pordenonelegge.jpg")
        self.assertEqual(event["sources"], ["Pordenonelegge", "TurismoFVG"])
        self.assertEqual([(item["start_date"], item["title"]) for item in event["programme_sessions"]],
                         [("2026-09-17", "Sessione 0"), ("2026-09-20", "Sessione 1")])

    def test_programme_projection_happens_after_date_and_radius_gates(self):
        sessions = [{
            "source": "Pordenonelegge", "title": title,
            "url": f"https://www.pordenonelegge.it/eventi/{title.lower()}",
            "event_city": city, "place": city, "lat": lat, "lon": 12.6605,
            "start_date": day, "end_date": day, "time": "10:00",
        } for title, city, lat, day in (
            ("Passata", "Pordenone", 45.9567, "2026-09-16"),
            ("Vicina", "Pordenone", 45.9567, "2026-09-18"),
            ("Lontana", "Udine", 46.0635, "2026-09-19"),
        )]
        catalog = merge_collection(PILOT_PROJECT, None, {
            "Pordenonelegge": {"status": "ok", "events": sessions},
        }, "2026-09-17T08:00:00Z")
        event = query_catalog(catalog, 45.9567, 12.6605, 5,
                              now=datetime.fromisoformat("2026-09-17T08:00:00Z"))["events"][0]
        self.assertEqual(event["active_session_count"], 1)
        self.assertEqual([item["title"] for item in event["programme_sessions"]], ["Vicina"])
        self.assertNotIn("session_count", event)
        self.assertEqual(event["start_date"], "2026-09-16")
        self.assertEqual(event["end_date"], "2026-09-20")
        self.assertEqual(event["event_city"], "Pordenone e territorio")
        self.assertEqual(event["venue"], "Più sedi")
        self.assertNotIn("distance_km", event)
        self.assertNotIn("lat", event)
        self.assertNotIn("lon", event)
        self.assertEqual(event["nearest_session_distance_km"], 0.0)

    def test_satellite_town_does_not_become_false_umbrella_location(self):
        session = {
            "source": "Pordenonelegge", "title": "Incontro a Sacile",
            "url": "https://www.pordenonelegge.it/eventi/incontro-a-sacile",
            "event_city": "Sacile", "place": "Sacile, Teatro Pileo",
            "lat": 45.9541, "lon": 12.5027, "start_date": "2026-09-19",
            "end_date": "2026-09-19", "time": "18:00",
            "location_confidence": "municipality",
        }
        catalog = merge_collection(PILOT_PROJECT, None, {
            "Pordenonelegge": {"status": "ok", "events": [session]},
        }, "2026-09-17T08:00:00Z")
        programme = query_catalog(
            catalog, session["lat"], session["lon"], 5,
            now=datetime.fromisoformat("2026-09-17T08:00:00Z"),
        )["events"][0]
        self.assertEqual(programme["event_city"], "Pordenone e territorio")
        self.assertNotIn("distance_km", programme)
        self.assertNotIn("lat", programme)
        self.assertNotIn("lon", programme)
        self.assertEqual(programme["nearest_session_distance_km"], 0.0)

    def test_similar_unreviewed_title_is_not_grouped(self):
        event = {
            "source": "TurismoFVG", "title": "Pordenonelegge - evento futuro",
            "url": "https://www.turismofvg.it/eventi/unrelated-reviewed-later",
            "event_city": "Pordenone", "place": "Pordenone", "lat": 45.9567,
            "lon": 12.6605, "start_date": "2026-09-18", "end_date": "2026-09-18",
        }
        catalog = merge_collection(PILOT_PROJECT, None, {
            "TurismoFVG": {"status": "ok", "events": [event]},
        }, "2026-09-17T08:00:00Z")
        result = query_catalog(catalog, 45.9567, 12.6605,
                               now=datetime.fromisoformat("2026-09-17T08:00:00Z"))
        self.assertEqual(result["events"][0]["title"], event["title"])
        self.assertNotIn("programme_id", result["events"][0])
