import unittest
from datetime import date, datetime, timedelta, timezone
import requests
from app.events.pilot_details import english_provider_date_range

from app.events.pilot_regional_year_control import (
    create_snapshot, finish_snapshot, inspect_batch, inspect_item,
    reconcile_removed_future, reconcile_same_edition_duplicates,
    results_within_age, summary,
)


class RegionalYearControlTests(unittest.TestCase):
    event_url = 'https://www.turismofvg.it/eventi/festa'
    navigation_url = 'https://www.turismofvg.it/eventi/festival'
    today = date(2026, 10, 5)
    now = datetime(2026, 10, 5, 12, tzinfo=timezone.utc)

    def sources(self):
        calendar = {'start': '2026-01-01', 'end': '2026-12-31',
                    'declared_results': 1, 'cards_seen': 1, 'pages': 1,
                    'cards': [{'url': self.event_url, 'title': 'Festa',
                               'place': 'Udine', 'badge_date': '2026-10-10'}]}
        sitemap = {'status': 'ok', 'unique_urls': 2,
                   'detail_urls': [
                       {'url': self.event_url, 'lastmod': '2026-10-05'},
                       {'url': self.navigation_url, 'lastmod': None}]}
        return calendar, sitemap

    @staticmethod
    def detail():
        return ('<h1>Festa</h1><div class="body_col1"><h2>Descrizione</h2>'
                '<p>La festa si svolge in piazza.</p></div><div class="body_col2">'
                '<div style="background-image: url(icn__calendar.svg)">10 ottobre 2026</div>'
                '<div style="background-image: url(icn__pin.svg)">Udine</div>'
                '<div style="background-image: url(icn__building.svg)">Piazza Primo Maggio</div>'
                '</div><div class="c-detail__actions"></div>')

    def test_complete_index_is_resumable_and_navigation_is_local(self):
        calendar, sitemap = self.sources()
        snapshot = create_snapshot(calendar, sitemap, today=self.today, now=self.now)
        seen = []
        def fetch(url):
            seen.append(url)
            return self.detail()
        checked = inspect_batch(snapshot, fetch_html=fetch, now=self.now)
        self.assertEqual(seen, [self.event_url])
        self.assertEqual(checked['results'][self.event_url]['status'], 'detail_aligned')
        self.assertEqual(checked['results'][self.navigation_url]['status'], 'non_event')
        self.assertTrue(summary(checked)['source_complete'])
        resumed = create_snapshot(calendar, sitemap, today=self.today,
                                  previous=checked, now=self.now + timedelta(hours=1))
        self.assertEqual(len(resumed['results']), 2)
        sitemap['detail_urls'][0]['lastmod'] = '2026-10-06'
        changed = create_snapshot(calendar, sitemap, today=self.today,
                                  previous=checked, now=self.now + timedelta(hours=1))
        self.assertNotIn(self.event_url, changed['results'])
        self.assertEqual(summary(changed)['pending'], 1)

    def test_full_inspection_checkpoints_and_reconciles_both_indexes(self):
        calendar, sitemap = self.sources()
        snapshot = create_snapshot(calendar, sitemap, today=self.today, now=self.now)
        checkpoints = []
        checked = finish_snapshot(snapshot, batch_size=1,
                                  fetch_html=lambda _: self.detail(),
                                  checkpoint=lambda state: checkpoints.append(
                                      len(state['results'])))
        self.assertEqual(checkpoints, [1, 2])
        self.assertEqual(summary(checked)['inspected'],
                         summary(checked)['inventory_urls'])
        self.assertTrue(summary(checked)['source_complete'])

    def test_full_inspection_stops_after_three_failed_html_reads(self):
        calendar, sitemap = self.sources()
        snapshot = create_snapshot(calendar, sitemap, today=self.today, now=self.now)
        calls = []
        def unavailable(url):
            calls.append(url)
            raise requests.ConnectionError('offline')
        checked = finish_snapshot(snapshot, batch_size=1, fetch_html=unavailable)
        self.assertEqual(calls, [self.event_url] * 3)
        self.assertEqual(checked['attempts'][self.event_url]['count'], 3)
        self.assertFalse(summary(checked)['source_complete'])

    def test_labelled_period_wins_over_partial_prose_programme(self):
        url = 'https://www.turismofvg.it/eventi/amelie-il-musical'
        entry = {'kind': 'calendar', 'identity_conflict': False,
                 'candidate': {'source': 'TurismoFVG', 'url': url,
                               'title': 'Amelie - Il Musical',
                               'event_city': 'Udine',
                               'discovery_kind': 'filtered_calendar',
                               'listing_occurrences': [
                                   '2026-10-16', '2026-10-17',
                                   '2026-10-18', '2026-10-19']}}
        html = ('<h1>Amelie - Il Musical</h1>'
                '<div class="body_col1"><h2>Descrizione</h2>'
                '<p>Previsto nelle seguenti giornate: 16 ottobre 2026, '
                '17 ottobre 2026 e 18 ottobre 2026.</p></div>'
                '<div class="body_col2">'
                '<div style="background-image: url(icn__calendar.svg)">'
                'venerdì 16 ottobre 2026 - lunedì 19 ottobre 2026</div>'
                '<div style="background-image: url(icn__pin.svg)">Udine</div>'
                '<div style="background-image: url(icn__building.svg)">'
                'Teatro Nuovo Giovanni da Udine</div>'
                '</div><div class="c-detail__actions"></div>')
        result = inspect_item(url, entry, html, today=self.today, now=self.now)
        self.assertEqual(result['status'], 'detail_aligned')
        self.assertEqual(result['detail_date_full'],
                         'venerdì 16 ottobre 2026 - lunedì 19 ottobre 2026')
        self.assertEqual(result['event']['start_date'], '2026-10-16')
        self.assertEqual(result['event']['end_date'], '2026-10-19')
        self.assertEqual(result['event']['description_source_url'], url)

        entry['candidate']['listing_occurrences'].append('2026-10-20')
        outside = inspect_item(url, entry, html, today=self.today, now=self.now)
        self.assertEqual(outside['status'], 'review_required')

    def test_old_badge_is_removed_only_for_verified_updated_period(self):
        url = 'https://www.turismofvg.it/eventi/gruppi-di-cammino'
        entry = {'kind': 'calendar', 'identity_conflict': False,
                 'candidate': {'source': 'TurismoFVG', 'url': url,
                               'title': 'Gruppi di Cammino',
                               'event_city': 'Udine',
                               'discovery_kind': 'filtered_calendar',
                               'listing_occurrences': [
                                   '2026-09-18', '2026-10-07', '2026-11-04']}}
        html = ('<h1>Gruppi di Cammino</h1>'
                '<div class="body_col1"><h2>Descrizione</h2>'
                '<p>Incontri settimanali con inizio venerdì 2 ottobre.</p></div>'
                '<div class="body_col2">'
                '<div style="background-image: url(icn__calendar.svg)">'
                'venerdì 2 ottobre 2026 - mercoledì 4 novembre 2026</div>'
                '<div style="background-image: url(icn__pin.svg)">Udine</div>'
                '</div><div class="c-detail__actions"></div>')
        result = inspect_item(url, entry, html, today=self.today)
        self.assertEqual(result['status'], 'detail_aligned')
        self.assertEqual(result['ignored_listing_occurrences'], ['2026-09-18'])
        self.assertEqual(result['event']['start_date'], '2026-10-02')
        entry['candidate']['listing_occurrences'].append('2026-11-10')
        self.assertEqual(inspect_item(url, entry, html, today=self.today)['status'],
                         'review_required')
        entry['candidate']['listing_occurrences'].remove('2026-11-10')
        self.assertEqual(inspect_item(url, entry,
                                      html.replace('Gruppi di Cammino</h1>',
                                                   'Altro evento</h1>'),
                                      today=self.today)['status'],
                         'review_required')

    def test_second_exhibition_detail_needs_unique_matching_sections(self):
        first = 'https://www.turismofvg.it/eventi/radici-nella-pietra'
        second = first + '-490917'
        canonical = {'status': 'detail_aligned', 'event': {
            'title': 'Radici nella pietra', 'event_city': 'Moggio Udinese',
            'schedule_kind': 'month_range', 'provider_categories': 'Mostre',
            'start_date': '2026-05-01',
            'official_site': 'https://www.comune.moggioudinese.ud.it/',
            'description_excerpt': 'Mostra fotografica: sezione interna - '
                                   'Palazzo Municipale; sezione esterna - vie del Paese.'}}
        claim = {'title': 'radici nella pietra', 'city': 'moggio udinese',
                 'year': 2026, 'official_host': 'comune.moggioudinese.ud.it',
                 'sections': 'internal_and_external_municipal_exhibition'}
        reviewed = {'status': 'review_required', 'reason': 'publication_gate',
                    'duplicate_claim': claim}
        snapshot = {'entries': {first: {}, second: {}},
                    'results': {first: canonical, second: reviewed}}
        resolved = reconcile_same_edition_duplicates(snapshot)
        self.assertEqual(resolved['results'][second]['status'], 'duplicate_detail')
        self.assertEqual(resolved['results'][second]['duplicate_of'], first)
        self.assertEqual(snapshot['results'][second]['status'], 'review_required')
        different = {**snapshot, 'results': {**snapshot['results'], first: {
            **canonical, 'event': {**canonical['event'],
                                   'official_site': 'https://unrelated.example/'}}}}
        self.assertEqual(reconcile_same_edition_duplicates(different)
                         ['results'][second]['status'], 'review_required')
        third = first + '-copy'
        ambiguous = {**snapshot, 'entries': {**snapshot['entries'], third: {}},
                     'results': {**snapshot['results'], third: canonical}}
        self.assertEqual(reconcile_same_edition_duplicates(ambiguous)
                         ['results'][second]['status'], 'review_required')

    def test_official_page_title_can_reconcile_translated_heading(self):
        url = 'https://www.turismofvg.it/eventi/film-festival'
        entry = {'kind': 'calendar', 'identity_conflict': False,
                 'candidate': {'source': 'TurismoFVG', 'url': url,
                               'title': 'Festival del Cinema 2026',
                               'event_city': 'Trieste',
                               'discovery_kind': 'filtered_calendar',
                               'listing_occurrences': []}}
        html = ('<title>Festival del Cinema 2026</title>'
                '<h1>Film Festival 2026</h1>'
                '<div class="body_col1"><h2>Descrizione</h2>'
                '<p>Films from around the world.</p></div>'
                '<div class="body_col2">'
                '<div style="background-image: url(icn__calendar.svg)">'
                'Sunday, October 25, 2026 - Sunday, November 1, 2026</div>'
                '<div style="background-image: url(icn__pin.svg)">Trieste</div>'
                '</div><div class="c-detail__actions"></div>')
        result = inspect_item(url, entry, html, today=self.today, now=self.now)
        self.assertEqual(result['status'], 'detail_aligned')
        self.assertEqual(result['event']['title'], 'Festival del Cinema 2026')
        mismatched = html.replace('<title>Festival del Cinema 2026</title>',
                                  '<title>Un altro evento</title>')
        self.assertEqual(inspect_item(url, entry, mismatched, today=self.today,
                                      now=self.now)['status'], 'review_required')

    def test_german_date_row_on_italian_page_keeps_verified_tournament(self):
        url = ('https://www.turismofvg.it/eventi/'
               'wtt-youth-contender-lignano-2026')
        entry = {'kind': 'calendar', 'identity_conflict': False,
                 'candidate': {'source': 'TurismoFVG', 'url': url,
                               'title': 'WTT Youth Contender Lignano 2026',
                               'event_city': 'Lignano Sabbiadoro',
                               'discovery_kind': 'filtered_calendar',
                               'listing_occurrences': []}}
        html = ('<title>WTT Youth Contender Lignano 2026</title>'
                '<h1>WTT Youth Contender Lignano 2026</h1>'
                '<div class="body_col1"><h2>Descrizione</h2>'
                '<p>Vom 21. bis 27. Oktober 2026 findet das '
                'Tischtennisturnier statt.</p></div>'
                '<div class="body_col2">'
                '<div style="background-image: url(icn__calendar.svg)">'
                'Mittwoch, 21. Oktober 2026 - Dienstag, 27. Oktober 2026'
                '</div><div style="background-image: url(icn__pin.svg)">'
                'Lignano Sabbiadoro</div>'
                '<div style="background-image: url(icn__building.svg)">'
                'Bella Italia Efa Village</div>'
                '</div><div class="c-detail__actions"></div>')
        result = inspect_item(url, entry, html, today=date(2026, 10, 8),
                              now=self.now)
        self.assertEqual(result['status'], 'detail_aligned')
        self.assertEqual(result['event']['start_date'], '2026-10-21')
        self.assertEqual(result['event']['end_date'], '2026-10-27')
        self.assertTrue(result['event']['description_excerpt'])
        invalid = html.replace('Dienstag, 27.', 'Montag, 27.')
        self.assertEqual(inspect_item(url, entry, invalid,
                                      today=date(2026, 10, 8),
                                      now=self.now)['status'], 'review_required')

    def test_english_day_first_ordinal_requires_matching_weekday(self):
        self.assertEqual(english_provider_date_range('Sunday 18th October 2026'),
                         (date(2026, 10, 18), date(2026, 10, 18)))
        self.assertEqual(english_provider_date_range(
            'Sunday 18th October 2026 - Monday 19th October 2026'),
            (date(2026, 10, 18), date(2026, 10, 19)))
        self.assertEqual(english_provider_date_range('Saturday 18th October 2026'),
                         (None, None))

    def test_incomplete_year_index_never_carries_results(self):
        calendar, sitemap = self.sources()
        calendar['declared_results'] = 2
        with self.assertRaises(ValueError):
            create_snapshot(calendar, sitemap, today=self.today, now=self.now)

    def test_refresh_after_one_day_even_when_index_is_unchanged(self):
        calendar, sitemap = self.sources()
        snapshot = inspect_batch(create_snapshot(calendar, sitemap, today=self.today,
                                                now=self.now),
                                 fetch_html=lambda _: self.detail(), now=self.now)
        later = create_snapshot(calendar, sitemap, today=date(2026, 10, 6),
                                previous=snapshot,
                                now=self.now + timedelta(days=1, minutes=1))
        self.assertNotIn(self.event_url, later['results'])

    def test_shared_job_reuses_unchanged_detail_for_at_most_48_hours(self):
        calendar, sitemap = self.sources()
        checked = inspect_batch(create_snapshot(calendar, sitemap,
                                                today=self.today, now=self.now),
                                fetch_html=lambda _: self.detail(), now=self.now)
        retained = create_snapshot(calendar, sitemap,
                                   today=date(2026, 10, 6), previous=checked,
                                   now=self.now + timedelta(hours=25),
                                   max_result_age_days=2)
        self.assertIn(self.event_url, retained['results'])
        self.assertTrue(results_within_age(
            checked, now=self.now + timedelta(hours=47)))
        self.assertFalse(results_within_age(
            checked, now=self.now + timedelta(hours=49)))
        expired = create_snapshot(calendar, sitemap,
                                  today=date(2026, 10, 7), previous=checked,
                                  now=self.now + timedelta(hours=49),
                                  max_result_age_days=2)
        self.assertNotIn(self.event_url, expired['results'])

    def test_parser_version_change_invalidates_reused_results(self):
        calendar, sitemap = self.sources()
        checked = inspect_batch(create_snapshot(calendar, sitemap, today=self.today,
                                                now=self.now),
                                fetch_html=lambda _: self.detail(), now=self.now)
        checked['inspection_version'] = -1
        self.assertFalse(summary(checked)['source_complete'])
        with self.assertRaisesRegex(ValueError, 'stale'):
            finish_snapshot(checked, fetch_html=lambda _: self.detail())
        refreshed = create_snapshot(calendar, sitemap, today=self.today,
                                    previous=checked, now=self.now + timedelta(hours=1))
        self.assertEqual(refreshed['results'], {})

    def test_changed_calendar_badge_invalidates_reused_detail(self):
        calendar, sitemap = self.sources()
        checked = inspect_batch(create_snapshot(calendar, sitemap, today=self.today,
                                                now=self.now),
                                fetch_html=lambda _: self.detail(), now=self.now)
        calendar['cards'][0]['badge_date'] = '2026-10-11'
        refreshed = create_snapshot(calendar, sitemap, today=self.today,
                                    previous=checked, now=self.now + timedelta(hours=1))
        self.assertNotIn(self.event_url, refreshed['results'])
        self.assertEqual(summary(refreshed)['pending'], 1)

    def test_missing_listed_detail_is_reviewed(self):
        calendar, sitemap = self.sources()
        snapshot = create_snapshot(calendar, sitemap, today=self.today, now=self.now)
        def fetch(url):
            if url == self.event_url:
                response = requests.Response()
                response.status_code = 404
                raise requests.HTTPError(response=response)
            raise AssertionError('navigation page should not be fetched')
        checked = inspect_batch(snapshot, fetch_html=fetch, now=self.now)
        self.assertEqual(checked['results'][self.event_url]['status'],
                         'review_required')
        self.assertEqual(summary(checked)['attempts'], 0)
        self.assertFalse(summary(checked)['source_complete'])

    def test_future_event_removed_from_both_indexes_blocks_completion(self):
        calendar, sitemap = self.sources()
        checked = inspect_batch(create_snapshot(calendar, sitemap, today=self.today,
                                                now=self.now),
                                fetch_html=lambda _: self.detail(), now=self.now)
        calendar.update({'declared_results': 0, 'cards_seen': 0, 'cards': []})
        sitemap.update({'unique_urls': 1,
                        'detail_urls': [sitemap['detail_urls'][1]]})
        changed = create_snapshot(calendar, sitemap, today=self.today,
                                  previous=checked, now=self.now + timedelta(hours=1))
        self.assertEqual(changed['removed_future_urls'], [self.event_url])
        completed = inspect_batch(changed, fetch_html=lambda _: self.fail('no fetch'),
                                  now=self.now + timedelta(hours=1))
        self.assertEqual(summary(completed)['pending'], 0)
        self.assertFalse(summary(completed)['source_complete'])

    def test_renamed_detail_requires_unique_matching_title_city_and_dates(self):
        calendar, sitemap = self.sources()
        old = inspect_batch(create_snapshot(calendar, sitemap, today=self.today,
                                            now=self.now),
                            fetch_html=lambda _: self.detail(), now=self.now)
        replacement = 'https://www.turismofvg.it/eventi/festa-2026'
        calendar['cards'][0]['url'] = replacement
        sitemap['detail_urls'][0]['url'] = replacement
        fresh = inspect_batch(create_snapshot(calendar, sitemap, today=self.today,
                                              previous=old,
                                              now=self.now + timedelta(hours=1)),
                              fetch_html=lambda _: self.detail(),
                              now=self.now + timedelta(hours=1))
        self.assertFalse(summary(fresh)['source_complete'])
        resolved = reconcile_removed_future(fresh, old)
        self.assertEqual(resolved['replaced_urls'], {self.event_url: replacement})
        self.assertEqual(resolved['removed_future_urls'], [])
        self.assertTrue(summary(resolved)['source_complete'])
        second = 'https://www.turismofvg.it/eventi/festa-copia'
        fresh['entries'][second] = dict(fresh['entries'][replacement])
        fresh['results'][second] = dict(fresh['results'][replacement])
        self.assertEqual(reconcile_removed_future(fresh, old)['removed_future_urls'],
                         [self.event_url])
        del fresh['entries'][second]
        del fresh['results'][second]
        fresh['results'][replacement]['event']['end_date'] = '2026-10-11'
        self.assertEqual(reconcile_removed_future(fresh, old)['removed_future_urls'],
                         [self.event_url])

    def test_removed_event_starting_next_year_does_not_block_this_year(self):
        calendar, sitemap = self.sources()
        future_url = 'https://www.turismofvg.it/eventi/fila-a-teatro-2027'
        sitemap['detail_urls'].append({'url': future_url, 'lastmod': '2026-10-05'})
        sitemap['unique_urls'] += 1
        old = create_snapshot(calendar, sitemap, today=self.today, now=self.now)
        old['results'][future_url] = {
            'status': 'detail_aligned', 'detail_date_full': '17 gennaio 2027',
            'event': {'title': 'Fila a Teatro', 'event_city': 'Maniago',
                      'start_date': '2027-01-17', 'end_date': '2027-01-17'}}
        sitemap['detail_urls'].pop()
        sitemap['unique_urls'] -= 1
        changed = create_snapshot(calendar, sitemap, today=self.today,
                                  previous=old, now=self.now + timedelta(hours=1))
        self.assertIn(future_url, changed['removed_urls'])
        self.assertEqual(changed['removed_future_urls'], [])

    def test_duplicate_calendar_card_fails_index(self):
        calendar, sitemap = self.sources()
        calendar['cards'].append(dict(calendar['cards'][0]))
        calendar['declared_results'] = calendar['cards_seen'] = 2
        with self.assertRaisesRegex(ValueError, 'duplicate'):
            create_snapshot(calendar, sitemap, today=self.today, now=self.now)


if __name__ == '__main__':
    unittest.main()
