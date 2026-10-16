import unittest
from datetime import date
from app.events.pilot_details import enrich_details

from app.events.pilot_regional_forward_audit import (
    audit_summary, augment_previews, classify_saved_schedules, create_snapshot,
    inspect_batch, inspect_candidate, month_schedule_verified,
    quarantine_duplicate_previews,
    reclassify_alignment, schedule_interpretation,
)


class RegionalForwardAuditTests(unittest.TestCase):
    url = 'https://www.turismofvg.it/eventi/prova'

    def candidate(self):
        return {'source': 'TurismoFVG', 'url': self.url, 'title': 'Festa',
                'event_city': 'Udine', 'listing_occurrences': ['2026-10-10'],
                'discovery_kind': 'filtered_calendar'}

    @staticmethod
    def detail(title='Festa', date_text='10 ottobre 2026',
               description='Programma ufficiale.'):
        return (f'<h1>{title}</h1><div class="body_col1">'
                f'<h2>Descrizione</h2><p>{description}</p></div>'
                '<div class="body_col2">'
                f'<div style="background-image: url(icn__calendar.svg)">{date_text}</div>'
                '<div style="background-image: url(icn__pin.svg)">Udine</div>'
                '<div style="background-image: url(icn__building.svg)">Piazza Primo Maggio</div>'
                '<div class="c-detail__actions"></div>')

    def test_matching_detail_is_verified_and_conflict_is_quarantined(self):
        verified = inspect_candidate(self.candidate(), self.detail(),
                                     today=date(2026, 10, 5))
        self.assertEqual(verified['status'], 'detail_aligned')
        self.assertEqual(verified['event']['start_date'], '2026-10-10')
        self.assertEqual(verified['event']['event_city'], 'Udine')
        self.assertEqual(verified['description_status'], 'available')
        self.assertEqual(verified['event']['description_source_url'], self.url)
        self.assertLessEqual(len(verified['event']['description_excerpt']), 180)
        self.assertEqual(verified['schedule_interpretation'], 'single_date')
        conflict = inspect_candidate(self.candidate(),
                                     self.detail(date_text='11 ottobre 2026'),
                                     today=date(2026, 10, 5))
        self.assertEqual(conflict['status'], 'review_required')

    def test_booking_offer_without_programme_is_excluded_even_with_badge(self):
        candidate = {**self.candidate(), 'title': 'Cjarsons e Vino'}
        page = self.detail(title='Cjarsons e Vino',
                           date_text='12 giugno 2026 - 31 dicembre 2027',
                           description='Un’esperienza guidata con degustazione.')
        page = page.replace('<div style="background-image: url(icn__calendar.svg)">',
                            '<div style="background-image: url(icn__tag.svg)">'
                            'Enogastronomia, Strada del vino e dei sapori</div>'
                            '<div style="background-image: url(icn__calendar.svg)">')
        page = page.replace('<div class="c-detail__actions"></div>',
                            '<div style="background-image: url(icn__people.svg)">'
                            'solo su prenotazione</div><div class="c-detail__actions"></div>')
        result = inspect_candidate(candidate, page, today=date(2026, 10, 5))
        self.assertEqual(result['status'], 'non_event_experience')
        self.assertEqual(result['reason'], 'reservation_only_experience')

    def test_complex_calendar_text_can_be_one_verified_period_card(self):
        page = self.detail(
            date_text='17 settembre 2026 - 18 novembre 2026',
            description=('In calendario: sabato 10 ottobre concerto in piazza. '
                         'Domenica 18 ottobre visita guidata.'))
        strict = enrich_details([self.candidate()], fetch_html=lambda _: page,
                                allow_description_excerpt=True)
        self.assertEqual(len(strict['detail_candidates']), 1)
        result = inspect_candidate(self.candidate(), page,
                                   today=date(2026, 10, 5))
        self.assertEqual(result['status'], 'detail_aligned')
        self.assertEqual(result['detail_date_full'],
                         '17 settembre 2026 - 18 novembre 2026')
        self.assertTrue(result['event']['description_excerpt'])

    def test_confirmed_postponement_matches_date_row_and_badge(self):
        candidate = {**self.candidate(),
                     'listing_occurrences': ['2026-10-11']}
        text = ('Il mercatino della terza domenica è stato posticipato '
                'a domenica 11 ottobre.')
        result = inspect_candidate(
            candidate, self.detail(date_text='11 ottobre 2026',
                                   description=text), today=date(2026, 10, 5))
        self.assertEqual(result['status'], 'detail_aligned')
        mismatch = inspect_candidate(
            candidate, self.detail(date_text='11 ottobre 2026',
                                   description=text.replace('11 ottobre', '18 ottobre')),
            today=date(2026, 10, 5))
        self.assertEqual(mismatch['status'], 'review_required')

    def test_calendar_and_full_programme_can_correct_wrong_detail_end(self):
        candidate = {**self.candidate(),
                     'listing_occurrences': ['2026-10-18', '2026-10-24',
                                             '2026-10-25']}
        page = self.detail(
            date_text='18 ottobre 2026 - 24 ottobre 2026',
            description=('Domenica 18 ottobre apertura. Sabato 24 ottobre '
                         'festa. Domenica 25 ottobre chiusura.'))
        result = inspect_candidate(candidate, page,
                                   today=date(2026, 10, 5))
        self.assertEqual(result['status'], 'detail_aligned')
        self.assertEqual(result['schedule_interpretation'],
                         'programme_bounds_corroborated')
        self.assertEqual(result['event']['end_date'], '2026-10-25')
        self.assertEqual(result['event']['verified_programme_occurrences'],
                         candidate['listing_occurrences'])

    def test_month_label_requires_programme_day_matching_badge(self):
        self.assertTrue(month_schedule_verified('ottobre 2026',
                                                'Passeggiata il 9 ottobre.',
                                                ['2026-10-09']))
        self.assertFalse(month_schedule_verified('ottobre 2026',
                                                 'Passeggiata il 9 ottobre.',
                                                 ['2026-10-10']))
        candidate = {**self.candidate(),
                     'listing_occurrences': ['2026-10-09']}
        result = inspect_candidate(
            candidate, self.detail(date_text='ottobre 2026',
                                   description='Passeggiata il 9 ottobre.'),
            today=date(2026, 10, 5))
        self.assertEqual(result['status'], 'detail_aligned')
        self.assertTrue(result['event']['month_schedule_verified'])

    def test_snapshot_resumes_and_retries_failed_url(self):
        candidate = self.candidate()
        index = {'schema': 'turismofvg-sitemap-only-audit-v1',
                 'as_of_date': '2026-10-05', 'snapshot_id': 'abc',
                 'index_verification': {'horizon_complete': True,
                                        'declared_results': 1, 'cards_seen': 1},
                 'calendar_candidates': [candidate],
                 'sitemap_only_urls': [], 'results': {}, 'attempts': {}}
        snapshot = create_snapshot(index)
        def fail(_):
            raise TimeoutError()
        failed = inspect_batch(snapshot, fetch_html=fail)
        self.assertEqual(audit_summary(failed)['remaining'], 1)
        self.assertEqual(failed['attempts'][self.url]['count'], 1)
        recovered = inspect_batch(failed, fetch_html=lambda _: self.detail())
        self.assertEqual(audit_summary(recovered)['detail_aligned'], 1)
        self.assertEqual(audit_summary(recovered)['remaining'], 0)
        self.assertEqual(recovered['attempts'], {})

    def test_old_alignment_label_can_be_corrected_without_fetching(self):
        snapshot = {'schema': 'turismofvg-forward-detail-audit-v1',
                    'results': {self.url: {'status': 'verified_event', 'event': {'title': 'Festa'}}}}
        revised = reclassify_alignment(snapshot)
        self.assertEqual(revised['results'][self.url]['status'], 'detail_aligned')
        self.assertEqual(revised['results'][self.url]['event']['title'], 'Festa')
        self.assertEqual(snapshot['results'][self.url]['status'], 'verified_event')

    def test_preview_augmentation_is_resumable_and_deduplicates_boilerplate(self):
        second = 'https://www.turismofvg.it/eventi/seconda'
        old = {'status': 'detail_aligned', 'event': {'title': 'Festa'}}
        snapshot = {'schema': 'turismofvg-forward-detail-audit-v1',
                    'as_of_date': '2026-10-05', 'index_snapshot_id': 'abc',
                    'candidates': [self.candidate(),
                                   {**self.candidate(), 'url': second,
                                    'title': 'Seconda Festa'}],
                    'results': {self.url: old, second: old}, 'attempts': {}}
        revised = augment_previews(snapshot, fetch_html=lambda url:
                                   self.detail(title='Festa' if url == self.url
                                               else 'Seconda Festa'))
        self.assertEqual(audit_summary(revised)['preview_available'], 2)
        self.assertEqual(audit_summary(revised)['preview_pending'], 0)
        deduplicated = quarantine_duplicate_previews(revised)
        self.assertEqual(audit_summary(deduplicated)['preview_missing_or_unusable'], 2)
        self.assertTrue(all('description_excerpt' not in item['event']
                            for item in deduplicated['results'].values()))

    def test_same_event_title_keeps_excerpt_across_distinct_urls(self):
        second = 'https://www.turismofvg.it/eventi/seconda'
        snapshot = {'schema': 'turismofvg-forward-detail-audit-v1',
                    'results': {url: {'status': 'detail_aligned',
                                      'description_status': 'available',
                                      'event': {'title': 'La stessa festa',
                                                'description_excerpt': 'La stessa descrizione dettagliata.'}}
                                for url in (self.url, second)}}
        result = quarantine_duplicate_previews(snapshot)
        self.assertTrue(all(item['description_status'] == 'available'
                            for item in result['results'].values()))

    def test_range_badges_are_not_assumed_daily_or_complete(self):
        self.assertEqual(schedule_interpretation(
            '1 ottobre 2026 - 31 dicembre 2026',
            {'occurrences': ['2026-10-10']}),
            'range_with_badges_needs_interpretation')
        self.assertEqual(schedule_interpretation(
            '1 ottobre 2026 - 31 dicembre 2026', {}),
            'bounded_period_needs_opening_evidence')
        self.assertEqual(schedule_interpretation(
            'Ogni domenica', {'occurrences': ['2026-10-11']}),
            'recurrence_requires_expansion')
        snapshot = {'schema': 'turismofvg-forward-detail-audit-v1',
                    'results': {self.url: {'status': 'detail_aligned',
                                           'detail_date_full': '1 ottobre 2026 - 31 dicembre 2026',
                                           'event': {'occurrences': ['2026-10-10']}}}}
        revised = classify_saved_schedules(snapshot)
        self.assertEqual(revised['results'][self.url]['schedule_interpretation'],
                         'range_with_badges_needs_interpretation')


if __name__ == '__main__':
    unittest.main()
