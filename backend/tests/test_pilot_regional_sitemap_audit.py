import unittest
from datetime import date
import requests

from app.events.pilot_regional_sitemap_audit import (
    audit_summary, classify_detail, create_snapshot, fetch_detail, inspect_batch,
    reclassify_archival_results,
)


class RegionalSitemapAuditTests(unittest.TestCase):
    base = 'https://www.turismofvg.it/eventi/'

    def test_unicode_path_uses_requests_encoded_url_without_redirect(self):
        url = self.base + '40ª-sagra-della-castagna'
        response = requests.Response()
        response.status_code = 200
        response.url = self.base + '40%C2%AA-sagra-della-castagna'
        response._content = b'<h1>Sagra</h1>'
        self.assertEqual(fetch_detail(url, get=lambda *_args, **_kwargs: response),
                         '<h1>Sagra</h1>')
        response.url = self.base + 'altra-pagina'
        with self.assertRaisesRegex(ValueError, 'unexpected'):
            fetch_detail(url, get=lambda *_args, **_kwargs: response)

    @staticmethod
    def detail(title, date_text, city='Udine', description='Programma ufficiale.'):
        return (f'<h1>{title}</h1><div class="body_col1"><h2>Descrizione</h2>'
                f'<p>{description}</p></div><div class="body_col2">'
                f'<div style="background-image: url(icn__calendar.svg)">{date_text}</div>'
                f'<div style="background-image: url(icn__pin.svg)">{city}</div>'
                '<div style="background-image: url(icn__building.svg)">Piazza Primo Maggio</div>'
                '</div><div class="c-detail__actions"></div>')

    def test_listing_is_not_mistaken_for_event(self):
        result = classify_detail(self.base + 'festival',
                                 '<h1>Festival</h1><div class="c-events_result__total">10 eventi</div>',
                                 today=date(2026, 10, 5))
        self.assertEqual(result['status'], 'non_event')

    def test_explicit_future_and_past_details(self):
        future = classify_detail(self.base + 'festa',
                                 self.detail('Festa', '10 ottobre 2026'),
                                 today=date(2026, 10, 5))
        self.assertEqual(future['status'], 'future_candidate')
        self.assertEqual(future['start_date'], '2026-10-10')
        self.assertEqual(future['event_city'], 'Udine')
        past = classify_detail(self.base + 'festa-vecchia',
                               self.detail('Festa vecchia', '3 ottobre 2026'),
                               today=date(2026, 10, 5))
        self.assertEqual(past['status'], 'past_event')

    def test_long_bookable_experience_is_outside_events_scope(self):
        page = self.detail(
            'Cjarsons e Vino', '12 giugno 2026 - 31 dicembre 2027',
            city='Cormons', description='Un’esperienza guidata con degustazione in cantina.')
        page = page.replace('<div style="background-image: url(icn__calendar.svg)">',
                            '<div style="background-image: url(icn__tag.svg)">'
                            'Enogastronomia, Strada del vino e dei sapori</div>'
                            '<div style="background-image: url(icn__calendar.svg)">')
        page = page.replace('</div><div class="c-detail__actions"></div>',
                            '</div><div style="background-image: url(icn__people.svg)">'
                            'solo su prenotazione, entro le 20:00 del giorno precedente'
                            '</div><div class="c-detail__actions"></div>')
        result = classify_detail(self.base + 'cjarsons-e-vino', page,
                                 today=date(2026, 10, 5))
        self.assertEqual(result['status'], 'non_event_experience')
        self.assertEqual(result['reason'], 'reservation_only_experience')
        self.assertEqual(result['end_date'], '2027-12-31')
        exhibition = classify_detail(self.base + 'mostra',
            self.detail('Mostra', '1 agosto 2026 - 31 dicembre 2026',
                        description='Mostra aperta al pubblico nel periodo indicato.'),
            today=date(2026, 10, 5))
        self.assertEqual(exhibition['status'], 'future_candidate')

    def test_recurring_or_yearless_detail_stays_ambiguous(self):
        recurring = classify_detail(self.base + 'mercatino',
                                    self.detail('Mercatino', 'Ogni prima domenica del mese'),
                                    today=date(2026, 10, 5))
        self.assertEqual(recurring['reason'], 'recurrence_needs_calendar')
        yearless = classify_detail(self.base + 'fiera',
                                   self.detail('Fiera', '12 ottobre'),
                                   today=date(2026, 10, 5))
        self.assertEqual(yearless['reason'], 'year_missing')

    def test_unparsed_calendar_does_not_become_continuous_event(self):
        page = self.detail('Escursioni', 'dal 5 al 30 ottobre 2026',
                           description='Calendario: date da confermare')
        result = classify_detail(self.base + 'escursioni', page,
                                 today=date(2026, 10, 5))
        self.assertEqual(result['reason'], 'unparsed_explicit_calendar')

    def test_external_calendar_placeholder_does_not_publish_bookable_experience(self):
        page = self.detail(
            'Cocambo Time', '4 ottobre 2026 - 5 gennaio 2027', city='Aquileia',
            description=('Visite guidate in fabbrica di cioccolato, degustazioni, '
                         'laboratori ed esperienze in coppia. '
                         'Calendario: QUI. Prenotazioni via WhatsApp: 346 4792028'))
        page = page.replace('<div style="background-image: url(icn__calendar.svg)">',
                            '<div style="background-image: url(icn__tag.svg)">'
                            'Enogastronomia, Family</div>'
                            '<div style="background-image: url(icn__calendar.svg)">')
        result = classify_detail(self.base + 'cocambo-time-2026-2027', page,
                                 today=date(2026, 10, 8))
        self.assertEqual(result['status'], 'non_event_experience', result)
        self.assertEqual(result['reason'], 'reservation_only_experience')

    def test_old_year_without_day_is_archival_but_current_year_is_ambiguous(self):
        old = classify_detail(self.base + 'archivio',
                              self.detail('Archivio', 'Settembre 2023'),
                              today=date(2026, 10, 5))
        self.assertEqual(old['status'], 'past_event')
        self.assertEqual(old['reason'], 'archival_detail_year')
        current = classify_detail(self.base + 'stagione',
                                  self.detail('Stagione', 'Estate 2026'),
                                  today=date(2026, 10, 5))
        self.assertEqual(current['status'], 'ambiguous')

    def test_existing_snapshot_can_reclassify_old_year_without_network(self):
        url = self.base + 'archivio'
        snapshot = {'schema': 'turismofvg-sitemap-only-audit-v1',
                    'as_of_date': '2026-10-05', 'snapshot_id': 'test',
                    'sitemap_only_urls': [url], 'attempts': {},
                    'results': {url: {'status': 'ambiguous', 'reason': 'unparsed_event_date',
                                      'date_full': 'Settembre 2023'}}}
        revised = reclassify_archival_results(snapshot)
        self.assertEqual(revised['results'][url]['status'], 'past_event')
        self.assertEqual(snapshot['results'][url]['status'], 'ambiguous')

    def test_snapshot_resumes_without_refetching_completed_details(self):
        first, second = self.base + 'prima', self.base + 'seconda'
        sitemap = {'status': 'ok', 'unique_urls': 2,
                   'detail_urls': [{'url': first, 'lastmod': '2026-10-05'},
                                   {'url': second, 'lastmod': '2026-10-05'}]}
        calendar = {'status': 'ok', 'horizon_complete': True,
                    'collection_mode': 'annual-date-filters', 'windows': [],
                    'overflow': {'declared_results': 0}, 'declared_results': 0,
                    'cards_seen': 0, 'pages': 1, 'cards': []}
        snapshot = create_snapshot(sitemap, calendar, today=date(2026, 10, 5))
        seen = []
        def fetch(url):
            seen.append(url)
            return self.detail('Festa', '10 ottobre 2026')
        first_batch = inspect_batch(snapshot, batch_size=1, fetch_html=fetch)
        second_batch = inspect_batch(first_batch, batch_size=1, fetch_html=fetch)
        self.assertEqual(len(seen), 2)
        self.assertEqual(audit_summary(second_batch)['future_candidate'], 2)
        self.assertEqual(audit_summary(second_batch)['remaining_uninspected'], 0)
        self.assertEqual(audit_summary(inspect_batch(second_batch, fetch_html=fetch))['inspected'], 2)
        self.assertEqual(len(seen), 2)

    def test_retrieval_failure_remains_retryable(self):
        url = self.base + 'prova'
        snapshot = {'schema': 'turismofvg-sitemap-only-audit-v1',
                    'as_of_date': '2026-10-05', 'snapshot_id': 'test',
                    'sitemap_only_urls': [url], 'results': {}, 'attempts': {}}
        def fail(_):
            raise TimeoutError()
        failed = inspect_batch(snapshot, fetch_html=fail)
        self.assertEqual(audit_summary(failed)['remaining_uninspected'], 1)
        self.assertEqual(failed['attempts'][url]['count'], 1)
        recovered = inspect_batch(failed, fetch_html=lambda _: self.detail('Festa', '10 ottobre 2026'))
        self.assertEqual(audit_summary(recovered)['future_candidate'], 1)
        self.assertEqual(recovered['attempts'], {})

    def test_failed_url_does_not_starve_unseen_url(self):
        first, second = self.base + 'a', self.base + 'b'
        snapshot = {'schema': 'turismofvg-sitemap-only-audit-v1',
                    'as_of_date': '2026-10-05', 'snapshot_id': 'test',
                    'sitemap_only_urls': [first, second], 'results': {}, 'attempts': {}}
        def fetch(url):
            if url == first:
                raise TimeoutError()
            return self.detail('Festa', '10 ottobre 2026')
        once = inspect_batch(snapshot, batch_size=1, fetch_html=fetch)
        twice = inspect_batch(once, batch_size=1, fetch_html=fetch)
        self.assertEqual(twice['results'][second]['status'], 'future_candidate')
        self.assertEqual(twice['attempts'][first]['count'], 1)


if __name__ == '__main__':
    unittest.main()
