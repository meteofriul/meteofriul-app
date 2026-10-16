import unittest
from copy import deepcopy
from datetime import date, datetime, timedelta, timezone
from unittest.mock import Mock, patch

from app.events.pilot_regional_checkpoint import decode_control, encode_control
from app.events.pilot_regional_verified import (collect_regional_verified,
                                                collect_regional_window_verified,
                                                detail_age_limit_hours,
                                                evidence_has_future_after_window,
                                                evidence_overlaps_window,
                                                job_results_fresh)
from app.events.pilot_catalog import PILOT_PROJECT, merge_collection
from app.events.pilot_source_policy import gate_batch


class VerifiedRegionalJobTests(unittest.TestCase):
    today = date(2026, 10, 5)
    url = 'https://www.turismofvg.it/eventi/prova'

    def calendar(self, start, end, *, max_workers):
        self.assertEqual((start, end, max_workers),
                         (date(2026, 1, 1), date(2026, 12, 31), 16))
        return {'start': start.isoformat(), 'end': end.isoformat(),
                'declared_results': 1, 'cards_seen': 1, 'pages': 1,
                'cards': [{'url': self.url, 'title': 'Festa di prova',
                           'place': 'Udine', 'badge_date': '2026-10-10'}]}

    def sitemap(self):
        return {'status': 'ok', 'unique_urls': 1,
                'detail_urls': [{'url': self.url,
                                 'lastmod': '2026-10-05'}]}

    def html(self, _):
        return ('<h1>Festa di prova</h1><div class="body_col1">'
                '<h2>Descrizione</h2><p>Una festa in piazza.</p></div>'
                '<div class="body_col2">'
                '<div style="background-image: url(icn__calendar.svg)">'
                '10 ottobre 2026</div>'
                '<div style="background-image: url(icn__pin.svg)">Udine</div>'
                '<div style="background-image: url(icn__building.svg)">'
                'Piazza Primo Maggio</div>'
                '</div><div class="c-detail__actions"></div>')

    def collect(self, **changes):
        options = {'today': self.today, 'fetch_calendar': self.calendar,
                   'fetch_sitemap': self.sitemap, 'fetch_html': self.html}
        return collect_regional_verified(**{**options, **changes})

    def test_complete_control_is_the_only_publishable_batch(self):
        batch = self.collect()
        self.assertEqual(batch['status'], 'ok')
        self.assertEqual(batch['verification']['cards_total'], 1)
        self.assertEqual(batch['events'][0]['description_source_url'], self.url)
        self.assertEqual(gate_batch('TurismoFVG', batch,
                                    today=self.today)['status'], 'ok')
        forged = {**batch, 'events': [{**batch['events'][0],
                                      'start_date': '2026-10-11'}]}
        self.assertEqual(gate_batch('TurismoFVG', forged,
                                    today=self.today)['error_type'],
                         'source_verification_failed')
        expired = deepcopy(batch)
        expired['year_control']['results'][self.url]['checked_at'] = (
            datetime.now(timezone.utc) - timedelta(hours=49)).isoformat()
        self.assertEqual(gate_batch('TurismoFVG', expired,
                                    today=self.today)['error_type'],
                         'source_verification_failed')
        restored = decode_control(encode_control(batch['year_control']))
        self.assertEqual(restored['index_fingerprint'],
                         batch['year_control']['index_fingerprint'])

    def test_bad_detail_keeps_checkpoint_and_blocks_publication(self):
        batch = self.collect(fetch_html=lambda _: '<h1>Festa di prova</h1>')
        self.assertEqual(batch['status'], 'error')
        self.assertEqual(batch['error_type'], 'incomplete_source')
        self.assertEqual(batch['events'], [])
        self.assertEqual(batch['verification']['source_complete'], False)
        self.assertEqual(len(batch['year_control']['entries']), 1)
        saved = merge_collection(PILOT_PROJECT, None, {'TurismoFVG': batch},
                                 '2026-10-05T12:00:00+00:00')
        self.assertEqual(saved['sources']['TurismoFVG']['status'], 'unavailable')
        recovered_control = decode_control(
            saved['sources']['TurismoFVG']['control_checkpoint'])
        recovered = self.collect(previous_control=recovered_control)
        self.assertEqual(recovered['status'], 'ok')

    def test_rolling_window_quarantines_one_detail_without_losing_other_cards(self):
        bad_url = self.url + '-senza-data'
        def calendar(start, end, *, max_workers):
            return {'start': start.isoformat(), 'end': end.isoformat(),
                    'declared_results': 2, 'cards_seen': 2, 'pages': 1,
                    'cards': [
                        {'url': url, 'title': 'Festa di prova', 'place': 'Udine',
                         'badge_date': '2026-10-10'}
                        for url in (self.url, bad_url)]}
        batch = collect_regional_window_verified(
            today=self.today, fetch_calendar=calendar,
            fetch_sitemap=lambda: {'status': 'ok', 'unique_urls': 2,
                                   'detail_urls': [
                                       {'url': url, 'lastmod': '2026-10-05'}
                                       for url in (self.url, bad_url)]},
            fetch_html=lambda url: (self.html(url) if url == self.url
                                    else '<h1>Festa di prova</h1>'))
        self.assertEqual(batch['status'], 'ok')
        gated = gate_batch('TurismoFVG', batch, today=self.today)
        self.assertEqual(gated['status'], 'partial')
        self.assertEqual([event['url'] for event in gated['events']], [self.url])
        self.assertEqual(gated['review_required'][0]['url'], bad_url)
        damaged = deepcopy(batch)
        damaged['year_control']['calendar_segments'][0]['declared_results'] = 3
        self.assertEqual(gate_batch('TurismoFVG', damaged,
                                    today=self.today)['status'], 'error')

    def test_checkpoint_rejects_corruption(self):
        with self.assertRaises(ValueError):
            decode_control({'schema': 'turismofvg-year-control-checkpoint-v1',
                            'encoding': 'zlib+base64', 'value': 'bad!'})

    @patch('app.events.pilot_regional_verified.fetch_detail')
    def test_default_detail_fetch_keeps_requests_independent(self, fetch_detail):
        fetch_detail.side_effect = self.html
        batch = self.collect(fetch_html=None)
        self.assertEqual(batch['status'], 'ok')
        fetch_detail.assert_called_once_with(self.url)

    def test_complete_checkpoint_renews_due_near_event(self):
        control = self.collect()['year_control']
        checked = datetime.now(timezone.utc) - timedelta(hours=25)
        control['results'][self.url]['checked_at'] = checked.isoformat()
        self.assertTrue(job_results_fresh(control, today=self.today))
        fetch = Mock(side_effect=self.html)
        batch = self.collect(previous_control=control, fetch_html=fetch)
        self.assertEqual(batch['status'], 'ok')
        fetch.assert_called_once_with(self.url)

    def test_near_far_and_inactive_freshness(self):
        self.assertEqual(detail_age_limit_hours(
            {'status': 'detail_aligned', 'event': {'start_date': '2026-10-10'}},
            today=self.today), 48)
        self.assertEqual(detail_age_limit_hours(
            {'status': 'detail_aligned', 'event': {'start_date': '2026-11-10'}},
            today=self.today), 96)
        self.assertEqual(detail_age_limit_hours(
            {'status': 'excluded_current_year'}, today=self.today), 168)

    def test_rolling_window_reuses_annual_evidence_and_has_independent_gate(self):
        annual = self.collect()
        prior = merge_collection(PILOT_PROJECT, None, {'TurismoFVG': annual},
                                 '2026-10-05T12:00:00+00:00')['sources']['TurismoFVG']

        def window_calendar(start, end, *, max_workers):
            self.assertEqual((start, end, max_workers),
                             (self.today, self.today + timedelta(days=45), 16))
            return {'start': start.isoformat(), 'end': end.isoformat(),
                    'declared_results': 1, 'cards_seen': 1, 'pages': 1,
                    'cards': [{'url': self.url, 'title': 'Festa di prova',
                               'place': 'Udine', 'badge_date': '2026-10-10'}]}

        batch = collect_regional_window_verified(
            annual['year_control'], prior, today=self.today,
            fetch_calendar=window_calendar, fetch_sitemap=self.sitemap,
            fetch_html=self.html)
        self.assertEqual(batch['status'], 'ok')
        self.assertEqual(batch['verification']['window_end'], '2026-11-19')
        self.assertEqual(len(batch['events']), 1)
        self.assertEqual(gate_batch('TurismoFVG', batch, today=self.today,
                                    previous_batch=prior)['status'], 'ok')
        forged = deepcopy(batch)
        forged['events'][0]['start_date'] = '2026-10-11'
        self.assertEqual(gate_batch('TurismoFVG', forged, today=self.today,
                                    previous_batch=prior)['error_type'],
                         'source_verification_failed')

    def test_rolling_window_splits_at_new_year(self):
        today = date(2026, 12, 20)
        url = 'https://www.turismofvg.it/eventi/prova-gennaio'
        calls = []

        def calendar(start, end, *, max_workers):
            calls.append((start, end))
            cards = ([{'url': url, 'title': 'Festa di gennaio',
                       'place': 'Udine', 'badge_date': '2027-01-05'}]
                     if start.year == 2027 else [])
            return {'start': start.isoformat(), 'end': end.isoformat(),
                    'declared_results': len(cards), 'cards_seen': len(cards),
                    'pages': 1, 'cards': cards}

        def html(_):
            return ('<h1>Festa di gennaio</h1><div class="body_col1">'
                    '<h2>Descrizione</h2><p>Una festa in piazza.</p></div>'
                    '<div class="body_col2">'
                    '<div style="background-image: url(icn__calendar.svg)">'
                    '5 gennaio 2027</div>'
                    '<div style="background-image: url(icn__pin.svg)">Udine</div>'
                    '<div style="background-image: url(icn__building.svg)">'
                    'Piazza Primo Maggio</div>'
                    '</div><div class="c-detail__actions"></div>')

        batch = collect_regional_window_verified(
            today=today, fetch_calendar=calendar,
            fetch_sitemap=lambda: {'status': 'ok', 'unique_urls': 1,
                                   'detail_urls': [{'url': url,
                                                    'lastmod': '2026-12-20'}]},
            fetch_html=html)
        self.assertEqual(calls, [(today, date(2026, 12, 31)),
                                 (date(2027, 1, 1), date(2027, 2, 3))])
        self.assertEqual(batch['status'], 'ok')
        self.assertEqual(batch['events'][0]['start_date'], '2027-01-05')
        self.assertEqual(gate_batch('TurismoFVG', batch, today=today)['status'],
                         'ok')

    def test_rolling_window_rechecks_prior_event_missing_from_both_indexes(self):
        annual = self.collect()
        prior = merge_collection(PILOT_PROJECT, None, {'TurismoFVG': annual},
                                 '2026-10-05T12:00:00+00:00')['sources']['TurismoFVG']
        fetch = Mock(side_effect=self.html)

        def empty_calendar(start, end, *, max_workers):
            return {'start': start.isoformat(), 'end': end.isoformat(),
                    'declared_results': 0, 'cards_seen': 0, 'pages': 1,
                    'cards': []}

        batch = collect_regional_window_verified(
            annual['year_control'], prior, today=self.today,
            fetch_calendar=empty_calendar,
            fetch_sitemap=lambda: {'status': 'ok', 'unique_urls': 0,
                                   'detail_urls': []},
            fetch_html=fetch)
        self.assertEqual(batch['status'], 'ok')
        self.assertEqual(batch['verification']['prior_detail_count'], 1)
        self.assertEqual(batch['verification']['carried_prior_count'], 1)
        self.assertEqual(batch['events'][0]['url'], self.url)
        fetch.assert_called_once_with(self.url)
        self.assertEqual(gate_batch('TurismoFVG', batch, today=self.today,
                                    previous_batch=prior)['status'], 'ok')

    def test_rolling_window_inspects_new_sitemap_detail(self):
        annual = self.collect()
        prior = merge_collection(PILOT_PROJECT, None, {'TurismoFVG': annual},
                                 '2026-10-05T12:00:00+00:00')['sources']['TurismoFVG']
        new_url = self.url + '-nuovo'
        fetched = []

        def calendar(start, end, *, max_workers):
            return {'start': start.isoformat(), 'end': end.isoformat(),
                    'declared_results': 1, 'cards_seen': 1, 'pages': 1,
                    'cards': [{'url': self.url, 'title': 'Festa di prova',
                               'place': 'Udine', 'badge_date': '2026-10-10'}]}

        def html(url):
            fetched.append(url)
            return self.html(url)

        batch = collect_regional_window_verified(
            annual['year_control'], prior, today=self.today,
            fetch_calendar=calendar,
            fetch_sitemap=lambda: {
                'status': 'ok', 'unique_urls': 2,
                'detail_urls': [
                    {'url': self.url, 'lastmod': '2026-10-05'},
                    {'url': new_url, 'lastmod': '2026-10-05'}]},
            fetch_html=html)
        self.assertEqual(batch['status'], 'ok')
        self.assertIn(new_url, fetched)
        self.assertEqual({item['url'] for item in batch['events']},
                         {self.url, new_url})
        self.assertEqual(gate_batch('TurismoFVG', batch, today=self.today,
                                    previous_batch=prior)['status'], 'ok')

    def test_verified_distant_event_enters_a_later_window_without_new_index_hit(self):
        url = 'https://www.turismofvg.it/eventi/festa-lontana'
        sitemap = lambda: {'status': 'ok', 'unique_urls': 1,
                           'detail_urls': [{'url': url,
                                            'lastmod': '2026-10-05'}]}

        def html(_):
            return ('<h1>Festa lontana</h1><div class="body_col1">'
                    '<h2>Descrizione</h2><p>Una festa in piazza.</p></div>'
                    '<div class="body_col2">'
                    '<div style="background-image: url(icn__calendar.svg)">'
                    '20 novembre 2026</div>'
                    '<div style="background-image: url(icn__pin.svg)">Udine</div>'
                    '<div style="background-image: url(icn__building.svg)">'
                    'Piazza Primo Maggio</div>'
                    '</div><div class="c-detail__actions"></div>')

        def calendar(start, end, *, max_workers):
            annual = start == date(2026, 1, 1)
            cards = ([{'url': url, 'title': 'Festa lontana',
                       'place': 'Udine', 'badge_date': '2026-11-20'}]
                     if annual else [])
            return {'start': start.isoformat(), 'end': end.isoformat(),
                    'declared_results': len(cards), 'cards_seen': len(cards),
                    'pages': 1, 'cards': cards}

        annual = collect_regional_verified(
            today=self.today, fetch_calendar=calendar,
            fetch_sitemap=sitemap, fetch_html=html)
        self.assertEqual(annual['status'], 'ok')
        first_prior = merge_collection(
            PILOT_PROJECT, None, {'TurismoFVG': annual},
            '2026-10-05T12:00:00+00:00')['sources']['TurismoFVG']
        first = collect_regional_window_verified(
            annual['year_control'], first_prior, today=self.today,
            fetch_calendar=calendar, fetch_sitemap=sitemap, fetch_html=html)
        self.assertEqual(first['status'], 'ok')
        self.assertEqual(first['events'], [])
        self.assertEqual(first['verification']['known_future_count'], 1)
        self.assertEqual(gate_batch('TurismoFVG', first, today=self.today,
                                    previous_batch=first_prior)['status'], 'ok')
        second_prior = merge_collection(
            PILOT_PROJECT, None, {'TurismoFVG': first},
            '2026-10-05T13:00:00+00:00')['sources']['TurismoFVG']
        second = collect_regional_window_verified(
            first['year_control'], second_prior, today=date(2026, 10, 6),
            fetch_calendar=calendar, fetch_sitemap=sitemap, fetch_html=html)
        self.assertEqual(second['status'], 'ok')
        self.assertEqual([item['url'] for item in second['events']], [url])
        self.assertEqual(second['verification']['known_future_count'], 0)
        self.assertEqual(gate_batch('TurismoFVG', second,
                                    today=date(2026, 10, 6),
                                    previous_batch=second_prior)['status'], 'ok')

    def test_recurring_evidence_waits_for_an_occurrence_in_the_window(self):
        witness = {
            'entry': {'candidate': {'listing_occurrences': [
                '2026-10-04', '2026-12-06']}},
            'result': {'status': 'detail_aligned',
                       'schedule_interpretation': 'recurrence_requires_expansion',
                       'event': {'start_date': '2026-10-04',
                                 'end_date': '2026-12-06',
                                 'schedule_kind': 'occurrences',
                                 'occurrences': ['2026-10-04', '2026-12-06']}}}
        self.assertFalse(evidence_overlaps_window(
            witness, today=date(2026, 10, 11), window_end=date(2026, 11, 25)))
        self.assertTrue(evidence_has_future_after_window(
            witness, window_end=date(2026, 11, 25)))
        self.assertTrue(evidence_overlaps_window(
            witness, today=date(2026, 10, 22), window_end=date(2026, 12, 6)))


if __name__ == '__main__':
    unittest.main()
