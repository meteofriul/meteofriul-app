"""Publication contracts for isolated TurismoFVG detail failures (offline)."""
import json
import unittest
from collections import Counter
from copy import deepcopy
from datetime import date, datetime, timedelta, timezone
from unittest.mock import Mock, patch
import requests

from app.events.pilot_catalog import PILOT_PROJECT, merge_collection
from app.events.pilot_cloud import publish
from app.events.pilot_regional_checkpoint import decode_control, encode_control
from app.events.pilot_regional_verified import collect_regional_window_verified
from app.events.pilot_source_policy import gate_batch


class RegionalFailureIsolationTests(unittest.TestCase):
    today = date(2026, 10, 13)
    urls = ['https://www.turismofvg.it/eventi/isolation-uno',
            'https://www.turismofvg.it/eventi/isolation-due']

    def setUp(self):
        self.now = datetime(2026, 10, 13, 12, tzinfo=timezone.utc)
        # Keep expiry and HTTP filtering reproducible after the fixture event date.
        for module in ('pilot_regional_verified', 'pilot_regional_year_control',
                       'pilot_regional_health', 'pilot_regional_historical',
                       'pilot_catalog', 'pilot_http', 'pilot_cloud', 'pilot_regional_checkpoint'):
            mocked = patch(f'app.events.{module}.datetime', wraps=datetime)
            clock = mocked.start()
            clock.now.side_effect = lambda tz=None: (self.now.astimezone(tz) if tz
                                                     else self.now.replace(tzinfo=None))
            self.addCleanup(mocked.stop)

    def html(self, url):
        title = 'Festa uno' if url == self.urls[0] else 'Festa due'
        return (f'<h1>{title}</h1><div class="body_col1"><h2>Descrizione</h2>'
                '<p>Festa in piazza.</p></div><div class="body_col2">'
                '<div style="background-image:url(icn__calendar.svg)">18 ottobre 2026</div>'
                '<div style="background-image:url(icn__pin.svg)">Udine</div>'
                '<div style="background-image:url(icn__building.svg)">Piazza Primo Maggio</div>'
                '</div><div class="c-detail__actions"></div>')

    def calendar(self, start, end, *, max_workers):
        return {'start': start.isoformat(), 'end': end.isoformat(),
                'declared_results': len(self.urls), 'cards_seen': len(self.urls), 'pages': 1,
                'cards': [{'url': u, 'title': 'Festa uno' if i == 0 else 'Festa due',
                           'place': 'Udine', 'badge_date': '2026-10-18'}
                          for i, u in enumerate(self.urls)]}

    def sitemap(self):
        return {'status': 'ok', 'unique_urls': len(self.urls),
                'detail_urls': [{'url': u, 'lastmod': '2026-10-13'} for u in self.urls]}

    def collect(self, **kwargs):
        return collect_regional_window_verified(**{
            'today': self.today, 'fetch_calendar': self.calendar,
            'fetch_sitemap': self.sitemap, 'fetch_html': self.html, **kwargs})

    def gate(self, batch, prior=None):
        return gate_batch('TurismoFVG', batch, today=self.today, previous_batch=prior)

    def previous(self, hours=25):
        batch = self.collect()
        for i, u in enumerate(self.urls):
            batch['year_control']['results'][u]['checked_at'] = (
                self.now - timedelta(hours=1 if i == 0 else hours)).isoformat()
        # This simulates a persisted, verified checkpoint from an earlier run.
        source = merge_collection(PILOT_PROJECT, None, {'TurismoFVG': batch},
                                  self.now.isoformat())['sources']['TurismoFVG']
        return batch['year_control'], source

    def failing_reader(self, error):
        counts = Counter()
        def read(url):
            counts[url] += 1
            if url == self.urls[1]:
                raise error
            return self.html(url)
        return read, counts

    def test_isolated_transport_failure_quarantines_only_that_url(self):
        for status in [None, 403, 429, 503]:
            with self.subTest(status=status):
                response = requests.Response(); response.status_code = status or 503
                error = (requests.HTTPError('failed', response=response) if status
                         else requests.ReadTimeout('private text must not be persisted'))
                reader, counts = self.failing_reader(error)
                batch = self.collect(fetch_html=reader)
                gated = self.gate(batch)
                self.assertEqual(gated['status'], 'partial')
                self.assertEqual([e['url'] for e in gated['events']], [self.urls[0]])
                self.assertEqual(gated['review_required'][0]['url'], self.urls[1])
                diagnostic = batch['detail_diagnostics'][self.urls[1]]
                self.assertEqual(diagnostic['phase'], 'fetch')
                self.assertEqual(diagnostic['http_status'], status)
                self.assertEqual(diagnostic['disposition'], 'quarantined')
                self.assertEqual(counts[self.urls[1]], 3)
                self.assertNotIn('private text', json.dumps(batch))
                self.assertEqual(batch['verification']['pending'], 0)

    def test_parser_exception_is_diagnosed_without_redownloading_three_times(self):
        from app.events.pilot_regional_year_control import inspect_item
        calls = Counter()
        def parse(url, *args, **kwargs):
            calls[url] += 1
            if url == self.urls[1]: raise ValueError('fixture parser error')
            return inspect_item(url, *args, **kwargs)
        with patch('app.events.pilot_regional_year_control.inspect_item', side_effect=parse):
            batch = self.collect()
        self.assertEqual(self.gate(batch)['status'], 'partial')
        self.assertEqual(calls[self.urls[1]], 1)
        self.assertEqual(batch['detail_diagnostics'][self.urls[1]]['phase'], 'parse')

    def test_all_details_timeout_remain_a_source_failure_with_persisted_urls(self):
        ctl, prior = self.previous()
        batch = self.collect(fetch_html=Mock(side_effect=requests.ReadTimeout('offline')))
        self.assertEqual(self.gate(batch)['status'], 'error')
        self.assertEqual(len(batch['detail_candidates']), 2)
        saved = merge_collection(PILOT_PROJECT, {'sources': {'TurismoFVG': prior}},
            {'TurismoFVG': self.gate(batch)}, self.now.isoformat())['sources']['TurismoFVG']
        self.assertEqual(saved['last_attempt_pending_count'], 2)
        self.assertEqual({r['url'] for r in saved['last_attempt_issues']}, set(self.urls))
        self.assertEqual(saved['last_attempt_detail_diagnostics'], batch['detail_diagnostics'])
        self.assertEqual(saved['control_checkpoint'], prior['control_checkpoint'])
        self.assertEqual(decode_control(saved['last_attempt_control_checkpoint'])['attempts'],
                         batch['year_control']['attempts'])

    def test_all_maintenance_html_cannot_replace_a_valid_batch_with_empty(self):
        _, prior = self.previous()
        batch = self.collect(fetch_html=lambda _: '<h1>Servizio momentaneamente non disponibile</h1>')
        self.assertEqual(self.gate(batch)['status'], 'error')
        saved = merge_collection(PILOT_PROJECT, {'sources': {'TurismoFVG': prior}},
            {'TurismoFVG': self.gate(batch)}, self.now.isoformat())['sources']['TurismoFVG']
        self.assertEqual(saved['status'], 'stale')
        self.assertEqual(saved['events'], prior['events'])

    def test_one_missing_structure_preserves_other_card(self):
        batch = self.collect(fetch_html=lambda u: self.html(u) if u == self.urls[0] else '<h1>Festa due</h1>')
        self.assertEqual(self.gate(batch)['status'], 'partial')
        self.assertEqual(len(self.gate(batch)['events']), 1)

    def test_optional_refresh_keeps_original_proof_and_records_failure(self):
        ctl, prior = self.previous()
        reader, _ = self.failing_reader(requests.ReadTimeout('offline'))
        batch = self.collect(previous_control=ctl, previous_batch=prior, fetch_html=reader)
        gated = self.gate(batch, prior)
        self.assertEqual(gated['status'], 'ok')
        self.assertEqual(len(gated['events']), 2)
        self.assertEqual(batch['year_control']['results'][self.urls[1]], ctl['results'][self.urls[1]])
        self.assertEqual(batch['detail_diagnostics'][self.urls[1]]['disposition'], 'retained_valid')
        self.assertGreater(batch['verification']['detail_health']['structured_reads'], 0)
        saved = merge_collection(PILOT_PROJECT, None, {'TurismoFVG': gated},
                                self.now.isoformat())['sources']['TurismoFVG']
        self.assertEqual(saved['detail_diagnostics'], batch['detail_diagnostics'])

    def test_expired_proof_is_never_restored(self):
        ctl, prior = self.previous(hours=49)
        reader, _ = self.failing_reader(requests.ReadTimeout('offline'))
        batch = self.collect(previous_control=ctl, previous_batch=prior, fetch_html=reader)
        self.assertEqual(self.gate(batch, prior)['status'], 'partial')
        self.assertNotIn(self.urls[1], [e['url'] for e in batch['events']])

    def test_changed_signature_is_never_restored(self):
        ctl, prior = self.previous()
        reader, _ = self.failing_reader(requests.ReadTimeout('offline'))
        def changed():
            value = self.sitemap(); value['detail_urls'][1]['lastmod'] = '2026-10-14'; return value
        batch = self.collect(previous_control=ctl, previous_batch=prior,
                             fetch_html=reader, fetch_sitemap=changed)
        self.assertEqual(self.gate(batch, prior)['status'], 'partial')
        self.assertNotIn(self.urls[1], [e['url'] for e in batch['events']])

    def test_successful_refresh_with_unreadable_content_does_not_keep_old_card(self):
        ctl, prior = self.previous()
        batch = self.collect(previous_control=ctl, previous_batch=prior,
                             fetch_html=lambda u: self.html(u) if u == self.urls[0] else '<h1>Festa due</h1>')
        self.assertEqual(self.gate(batch, prior)['status'], 'partial')
        self.assertEqual([e['url'] for e in batch['events']], [self.urls[0]])

    def test_budget_pending_is_not_fake_quarantine_and_has_url_reason(self):
        clock = [0.0]
        def calendar(*args, **kwargs): clock[0] = 316.; return self.calendar(*args, **kwargs)
        with patch('app.events.pilot_regional_verified.time.monotonic', side_effect=lambda: clock[0]):
            batch = self.collect(fetch_calendar=calendar)
        self.assertEqual(batch['status'], 'error')
        self.assertEqual(batch['verification']['pending'], 2)
        self.assertEqual(len(batch['detail_candidates']), 2)
        self.assertEqual({r['reason'] for r in batch['detail_candidates']}, {'not_attempted_budget'})
        self.assertEqual(batch['review_required'], [])

    def test_gate_rejects_tampered_failure_and_refresh_evidence(self):
        reader, _ = self.failing_reader(requests.ReadTimeout('offline'))
        batch = self.collect(fetch_html=reader)
        self.assertEqual(self.gate(batch)['status'], 'partial')
        damaged = deepcopy(batch)
        damaged['year_control']['detail_diagnostics'].clear()
        self.assertEqual(self.gate(damaged)['status'], 'error')
        damaged = deepcopy(batch)
        damaged['verification']['detail_health']['structured_reads'] = 999
        self.assertEqual(self.gate(damaged)['status'], 'error')
        ctl, prior = self.previous()
        batch = self.collect(previous_control=ctl, previous_batch=prior, fetch_html=reader)
        damaged = deepcopy(batch)
        damaged['year_control']['results'][self.urls[1]]['checked_at'] = self.now.isoformat()
        self.assertEqual(self.gate(damaged, prior)['status'], 'error')

    def test_valid_empty_inventory_remains_publishable(self):
        def empty(start, end, **kwargs):
            return {'start': start.isoformat(), 'end': end.isoformat(), 'declared_results': 0,
                    'cards_seen': 0, 'pages': 1, 'cards': []}
        batch = self.collect(fetch_calendar=empty,
                             fetch_sitemap=lambda: {'status':'ok','unique_urls':0,'detail_urls':[]})
        self.assertEqual(self.gate(batch)['status'], 'ok')
        self.assertEqual(batch['events'], [])

    def test_partial_catalog_is_saved_without_job_failure_and_visible_in_api(self):
        from app.events.pilot_http import application
        reader, _ = self.failing_reader(requests.ReadTimeout('offline'))
        batch = self.gate(self.collect(fetch_html=reader))
        stamp = self.now.isoformat()
        catalog = merge_collection(PILOT_PROJECT, None, {'TurismoFVG': batch}, stamp)
        client = Mock(project=PILOT_PROJECT); blob = client.bucket.return_value.blob.return_value
        blob.generation = 1; blob.size = 50
        blob.download_as_bytes.return_value = b'{"schema":"pilot-events-v1","sources":{}}'
        with patch('app.events.pilot_cloud.collect', return_value=catalog):
            report = publish(client, project=PILOT_PROJECT, adapters={'TurismoFVG': object()})
        saved = json.loads(blob.upload_from_string.call_args.args[0])
        self.assertEqual(saved['sources']['TurismoFVG']['status'], 'partial')
        self.assertEqual(report['TurismoFVG']['published_count'], 1)
        self.assertEqual(report['TurismoFVG']['pending_count'], 0)
        self.assertEqual(report['TurismoFVG']['detail_diagnostics'][0]['url'], self.urls[1])
        statuses = []
        with patch('app.events.pilot_http.load_catalog', return_value=saved):
            response = application({'REQUEST_METHOD':'GET','PATH_INFO':'/api/local/events',
                                    'QUERY_STRING':'lat=46.0635&lon=13.2358&radius=50'},
                                   lambda status, headers: statuses.append(status))
        payload = json.loads(b''.join(response))
        self.assertEqual(statuses, ['200 OK'])
        self.assertEqual(payload['total'], 1)
        self.assertEqual(payload['events'][0]['url'], self.urls[0])
        self.assertEqual(payload['source_failure_tags'], {'TurismoFVG':'quarantined_cards'})
        self.assertNotIn('detail_diagnostics', payload)

    def test_health_probe_failure_does_not_claim_cached_pages_prove_source_health(self):
        ctl, prior = self.previous()
        batch = self.collect(previous_control=ctl, previous_batch=prior,
                             fetch_html=Mock(side_effect=requests.ReadTimeout('offline')))
        self.assertEqual(self.gate(batch, prior)['status'], 'error')
        self.assertEqual(batch['verification']['detail_health']['structured_reads'], 0)
        self.assertEqual(len(batch['detail_candidates']), 2)

    def test_failure_diagnostics_match_observed_http_evidence(self):
        reader, _ = self.failing_reader(requests.ReadTimeout('offline'))
        batch = self.collect(fetch_html=reader)
        for field, value in [('http_status', 403), ('count', 999), ('phase', 'parse')]:
            with self.subTest(field=field):
                forged = deepcopy(batch)
                forged['detail_diagnostics'][self.urls[1]][field] = value
                forged['year_control']['detail_diagnostics'][self.urls[1]][field] = value
                self.assertEqual(self.gate(forged)['status'], 'error')

    def test_recovered_detail_proof_does_not_require_legacy_css_date(self):
        from app.events.pilot_regional_health import detail_observation
        result = {'status': 'detail_aligned', 'event': {'title': 'Evento',
                  'start_date':'2026-10-18', 'event_city':'Udine'}}
        observation = detail_observation('<h1>Evento</h1>', {'signature':'s'}, result,
                                         now=self.now)
        self.assertEqual(observation['outcome'], 'structured')
    def test_seven_failed_details_do_not_hide_the_healthy_card(self):
        self.urls = [self.urls[0]] + [
            f'https://www.turismofvg.it/eventi/isolation-failure-{i}' for i in range(7)]
        def reader(url):
            if url != self.urls[0]: raise requests.ReadTimeout('offline')
            return self.html(url)
        batch = self.gate(self.collect(fetch_html=reader))
        self.assertEqual(batch['status'], 'partial')
        self.assertEqual([event['url'] for event in batch['events']], [self.urls[0]])
        self.assertEqual(len(batch['review_required']), 7)
        self.assertEqual(len(batch['detail_diagnostics']), 7)
        self.assertEqual(batch['verification']['pending'], 0)

    def test_all_listed_details_missing_do_not_publish_empty(self):
        response = requests.Response(); response.status_code = 404
        batch = self.collect(fetch_html=Mock(side_effect=requests.HTTPError(response=response)))
        self.assertEqual(self.gate(batch)['status'], 'error')
        self.assertEqual(len(batch['review_required']), 2)

    def test_untrusted_sitemap_url_is_not_fetched_or_quarantined(self):
        url = 'https://untrusted.invalid/eventi/evento'
        def sitemap():
            value = self.sitemap()
            value['unique_urls'] += 1
            value['detail_urls'].append({'url': url, 'lastmod': '2026-10-13'})
            return value
        reader = Mock(side_effect=self.html)
        batch = self.collect(fetch_html=reader, fetch_sitemap=sitemap)
        self.assertEqual(self.gate(batch)['status'], 'error')
        self.assertNotIn(url, [call.args[0] for call in reader.call_args_list])
        self.assertEqual(batch['detail_candidates'][0]['reason'], 'invalid_detail_url')
        self.assertEqual(batch['detail_candidates'][0]['disposition'], 'pending')


    def budget_checkpoint(self):
        """Real partial inspection after a parser-version upgrade, then persist."""
        from app.events.pilot_regional_year_control import inspect_batch
        ctl, prior = self.previous(hours=1)
        ctl['inspection_version'] -= 1
        prior['control_checkpoint'] = encode_control(ctl)
        clock = [0.0]
        def one_read(control, **kwargs):
            kwargs['batch_size'] = 1
            result = inspect_batch(control, **kwargs)
            clock[0] = 316.
            return result
        with patch('app.events.pilot_regional_verified.time.monotonic', side_effect=lambda: clock[0]), \
             patch('app.events.pilot_regional_verified.inspect_batch', side_effect=one_read):
            batch = self.collect(previous_control=ctl, previous_batch=prior)
        self.assertEqual(batch['status'], 'error')
        self.assertEqual(batch['verification']['pending'], 1)
        self.assertEqual(batch['year_control']['detail_stop_reason'], 'budget_reserve')
        saved = merge_collection(PILOT_PROJECT, {'sources': {'TurismoFVG': prior}},
            {'TurismoFVG': self.gate(batch, prior)}, self.now.isoformat())['sources']['TurismoFVG']
        self.assertEqual(saved['control_checkpoint'], prior['control_checkpoint'])
        self.assertEqual(saved['events'], prior['events'])
        return ctl, saved

    def test_budget_resume_reads_only_missing_detail_and_passes_independent_gate(self):
        ctl, saved = self.budget_checkpoint()
        reader = Mock(side_effect=self.html)
        batch = self.collect(previous_control=ctl, previous_batch=saved, fetch_html=reader)
        self.assertEqual([c.args[0] for c in reader.call_args_list], [self.urls[0]])
        self.assertEqual(self.gate(batch, saved)['status'], 'ok')
        self.assertEqual(len(batch['events']), 2)
        self.assertEqual(batch['verification']['pending'], 0)
        published = merge_collection(PILOT_PROJECT, {'sources': {'TurismoFVG': saved}},
            {'TurismoFVG': self.gate(batch, saved)}, self.now.isoformat())['sources']['TurismoFVG']
        self.assertEqual(published['status'], 'fresh')
        self.assertNotIn('last_attempt_control_checkpoint', published)

    def test_resume_rejects_changed_expired_future_old_or_ambiguous_proof(self):
        ctl, saved = self.budget_checkpoint()
        for damage in ['signature', 'expired', 'future', 'version', 'day', 'review', 'corrupt']:
            with self.subTest(damage=damage):
                previous = deepcopy(saved)
                attempt = decode_control(previous['last_attempt_control_checkpoint'])
                url = self.urls[1]
                if damage == 'signature': attempt['entries'][url]['signature'] = 'changed'
                if damage == 'expired': attempt['results'][url]['checked_at'] = (self.now - timedelta(hours=49)).isoformat()
                if damage == 'future': attempt['results'][url]['checked_at'] = (self.now + timedelta(hours=1)).isoformat()
                if damage == 'version': attempt['inspection_version'] -= 1
                if damage == 'day': attempt['as_of_date'] = '2026-10-14'
                if damage == 'review': attempt['results'][url]['status'] = 'review_required'
                previous['last_attempt_control_checkpoint'] = ({} if damage == 'corrupt' else encode_control(attempt))
                reader = Mock(side_effect=self.html)
                batch = self.collect(previous_control=ctl, previous_batch=previous, fetch_html=reader)
                self.assertEqual(set(c.args[0] for c in reader.call_args_list), set(self.urls))
                self.assertEqual(self.gate(batch, previous)['status'], 'ok')

    def test_resume_cannot_replace_verified_inventory_or_skip_unlisted_active_card(self):
        ctl, saved = self.budget_checkpoint()
        attempt = decode_control(saved['last_attempt_control_checkpoint'])
        # A partial checkpoint must not erase the verified listing identity.
        attempt['entries'].pop(self.urls[1])
        saved['last_attempt_control_checkpoint'] = encode_control(attempt)
        def calendar(*args, **kwargs):
            value = self.calendar(*args, **kwargs)
            value.update(cards=value['cards'][:1], cards_seen=1, declared_results=1)
            return value
        reader = Mock(side_effect=self.html)
        batch = self.collect(previous_control=ctl, previous_batch=saved,
                             fetch_calendar=calendar, fetch_html=reader)
        self.assertEqual(self.gate(batch, saved)['status'], 'ok')
        self.assertEqual(batch['year_control']['carried_prior_urls'], [self.urls[1]])
        self.assertEqual(batch['year_control']['entries'][self.urls[1]]['candidate'],
                         ctl['entries'][self.urls[1]]['candidate'])
        self.assertEqual({e['url'] for e in batch['events']}, set(self.urls))

    def test_changed_live_inventory_invalidates_partial_detail_cache(self):
        ctl, saved = self.budget_checkpoint()
        def sitemap():
            value = self.sitemap(); value['detail_urls'][1]['lastmod'] = 'changed'; return value
        reader = Mock(side_effect=self.html)
        batch = self.collect(previous_control=ctl, previous_batch=saved,
                             fetch_sitemap=sitemap, fetch_html=reader)
        self.assertEqual(set(c.args[0] for c in reader.call_args_list), set(self.urls))
        self.assertEqual(self.gate(batch, saved)['status'], 'ok')

    def test_resume_does_not_publish_during_provider_outage(self):
        ctl, saved = self.budget_checkpoint()
        batch = self.collect(previous_control=ctl, previous_batch=saved,
                             fetch_html=Mock(side_effect=requests.ReadTimeout('offline')))
        self.assertEqual(self.gate(batch, saved)['status'], 'error')
        self.assertEqual(batch['verification']['detail_health']['structured_reads'], 0)

    def test_resume_refresh_fallback_keeps_original_timestamp_and_gate_rechecks_it(self):
        ctl, saved = self.budget_checkpoint()
        attempt = decode_control(saved['last_attempt_control_checkpoint'])
        attempt['results'][self.urls[1]]['checked_at'] = (self.now - timedelta(hours=25)).isoformat()
        saved['last_attempt_control_checkpoint'] = encode_control(attempt)
        def reader(url):
            if url == self.urls[1]: raise requests.ReadTimeout('offline')
            return self.html(url)
        batch = self.collect(previous_control=ctl, previous_batch=saved, fetch_html=reader)
        self.assertEqual(self.gate(batch, saved)['status'], 'ok')
        self.assertEqual(batch['year_control']['results'][self.urls[1]], attempt['results'][self.urls[1]])
        self.assertEqual(batch['detail_diagnostics'][self.urls[1]]['disposition'], 'retained_valid')
        forged = deepcopy(batch)
        forged['year_control']['results'][self.urls[1]]['checked_at'] = self.now.isoformat()
        self.assertEqual(self.gate(forged, saved)['status'], 'error')




if __name__ == '__main__':
    unittest.main()
