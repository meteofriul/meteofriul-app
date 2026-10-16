import unittest
from datetime import date

from app.events.pilot_regional_display_audit import (
    create_display_audit, create_year_display_audit,
    reviewed_attems_programme_title, summary,
)
from app.events.pilot_regional_year_control import INSPECTION_VERSION


class RegionalDisplayAuditTests(unittest.TestCase):
    base = 'https://www.turismofvg.it/eventi/'

    def test_attems_collateral_programmes_have_distinct_verified_titles(self):
        common = 'italia-settanta-la-creativita-come-antidoto-arte-moda-design-eventi-collaterali-'
        event = {'title': 'Italia Settanta - Eventi collaterali',
                 'event_city': 'Gorizia', 'venue': 'Palazzo Attems Petzenstein'}
        for suffix, first, last, expected in (
                ('502715', '2026-09-01', '2026-11-29',
                 'Italia Settanta · visite guidate e iniziative'),
                ('505824', '2026-10-01', '2026-10-15',
                 'Italia Settanta · eventi di ottobre')):
            url = self.base + common + suffix
            self.assertEqual(reviewed_attems_programme_title(
                url, event, date.fromisoformat(first), date.fromisoformat(last)), expected)
            self.assertEqual(reviewed_attems_programme_title(
                url, event, date.fromisoformat(first), date(2027, 11, 29)), event['title'])

    def test_discrete_detail_uses_all_six_days_and_next_date_for_order(self):
        forward, semantic = self.snapshots()
        url = self.base + '46a-mostra-mercato-regionale-della-patata'
        days = ['2026-09-26', '2026-09-27', '2026-10-03',
                '2026-10-04', '2026-10-10', '2026-10-11']
        forward['candidates'].append({'url': url, 'listing_occurrences': days})
        forward['results'][url] = {
            'status': 'detail_aligned',
            'detail_date_full': '26, 27 settembre / 3, 4 / 10, 11 ottobre 2026',
            'schedule_interpretation': 'explicit_discrete_dates',
            'event': {'title': 'Mostra Mercato Regionale della Patata',
                      'event_city': 'Udine', 'start_date': days[0],
                      'end_date': days[-1], 'occurrences': days}}
        audit = create_display_audit(forward, semantic, today=date(2026, 10, 5))
        card = next(item for item in audit['cards'] if item['url'] == url)
        self.assertEqual((card['start_date'], card['end_date'], card['sort_date']),
                         (days[0], days[-1], '2026-10-10'))
        self.assertEqual(card['schedule_kind'], 'explicit_dates')
        self.assertFalse(audit['review'])

    def test_german_interval_uses_bounded_calendar_days(self):
        forward, semantic = self.snapshots()
        url = self.base + 'concerti-candlelight-a-udine'
        days = ['2026-10-09', '2026-11-13', '2026-12-19']
        forward['candidates'].append({'url': url, 'listing_occurrences': days})
        forward['results'][url] = {
            'status': 'detail_aligned',
            'detail_date_full': 'Freitag, 9. Oktober 2026 - Samstag, 19. Dezember 2026',
            'event': {'title': 'Concerti Candlelight a Udine',
                      'event_city': 'Udine', 'schedule_kind': 'occurrences',
                      'start_date': days[0], 'end_date': days[-1],
                      'occurrences': days}}
        audit = create_display_audit(forward, semantic, today=date(2026, 10, 5))
        card = next(item for item in audit['cards'] if item['url'] == url)
        self.assertEqual(card['schedule_kind'], 'explicit_dates')
        self.assertEqual(card['sort_date'], days[0])
        self.assertIn('3 date nel calendario', card['date_label'])
        self.assertFalse(audit['review'])

        forward['results'][url]['event']['occurrences'] = days[:-1]
        audit = create_display_audit(forward, semantic, today=date(2026, 10, 5))
        self.assertIn({'url': url, 'reason': 'foreign_calendar_dates_conflict'},
                      audit['review'])

    def snapshots(self):
        period = self.base + 'mostra'
        single = self.base + 'festa'
        conflict = self.base + 'conflitto'
        urls = [period, single, conflict]
        forward = {
            'schema': 'turismofvg-forward-detail-audit-v1',
            'as_of_date': '2026-10-05', 'index_snapshot_id': 'abc',
            'candidates': [{'url': url} for url in urls], 'attempts': {},
            'results': {
                period: {'status': 'detail_aligned',
                         'detail_date_full': '2 ottobre 2026 - 11 ottobre 2026',
                         'schedule_interpretation': 'range_with_badges_needs_interpretation',
                         'event': {'title': 'Mostra', 'event_city': 'Udine',
                                   'occurrences': ['2026-10-02', '2026-10-11'],
                                   'description_excerpt': 'Una mostra aperta al pubblico.',
                                   'description_source_url': period}},
                single: {'status': 'detail_aligned',
                         'detail_date_full': '8 ottobre 2026',
                         'schedule_interpretation': 'single_date',
                         'event': {'title': 'Festa', 'event_city': 'Udine'}},
                conflict: {'status': 'detail_aligned',
                           'detail_date_full': '8 ottobre 2026 - 18 ottobre 2026',
                           'schedule_interpretation': 'range_with_badges_needs_interpretation',
                           'event': {'title': 'Conflitto', 'event_city': 'Udine'}},
            }}
        semantic = {'schema': 'turismofvg-semantic-schedule-audit-v1',
                    'as_of_date': '2026-10-05', 'index_snapshot_id': 'abc',
                    'items': [{'url': period}, {'url': conflict}],
                    'results': {
                        period: {'status': 'review_required',
                                 'reason': 'programme_not_explicit_or_complete'},
                        conflict: {'status': 'review_required',
                                   'reason': 'badge_not_in_explicit_programme'}},
                    'attempts': {}}
        return forward, semantic

    def test_period_is_one_card_without_invented_daily_occurrences(self):
        forward, semantic = self.snapshots()
        audit = create_display_audit(forward, semantic, today=date(2026, 10, 5))
        cards = {item['url']: item for item in audit['cards']}
        period = cards[self.base + 'mostra']
        self.assertEqual(period['schedule_kind'], 'period')
        self.assertEqual(period['start_date'], '2026-10-02')
        self.assertEqual(period['end_date'], '2026-10-11')
        self.assertEqual(period['sort_date'], '2026-10-05')
        self.assertNotIn('explicit_occurrences', period)
        self.assertEqual(period['description_excerpt'], 'Una mostra aperta al pubblico.')
        self.assertIn(self.base + 'conflitto', cards)
        self.assertEqual(cards[self.base + 'conflitto']['schedule_kind'], 'period')
        self.assertEqual(summary(audit)['hard_conflicts'], 0)

    def test_end_only_exhibition_preserves_unknown_start(self):
        forward, semantic = self.snapshots()
        url = self.base + 'memorie-riflesse'
        forward['candidates'].append({'url': url})
        forward['results'][url] = {
            'status': 'detail_aligned',
            'detail_date_full': 'Fino al 7 gennaio 2027',
            'schedule_interpretation': 'end_only',
            'event': {'title': 'Memorie riflesse',
                      'event_city': 'Udine', 'start_date': None,
                      'end_date': '2027-01-07', 'schedule_kind': 'end_only'}}
        audit = create_display_audit(forward, semantic, today=date(2026, 10, 5))
        card = next(item for item in audit['cards'] if item['url'] == url)
        self.assertIsNone(card['start_date'])
        self.assertEqual(card['end_date'], '2027-01-07')
        self.assertEqual(card['date_label'], 'Fino al 7 gennaio 2027')
        self.assertEqual(card['sort_date'], '2027-01-07')
        self.assertEqual(card['schedule_kind'], 'end_only')
        self.assertEqual(summary(audit)['end_only_cards'], 1)

    def test_month_range_card_shows_months_instead_of_invented_days(self):
        forward, semantic = self.snapshots()
        url = self.base + 'radici-nella-pietra'
        forward['candidates'].append({'url': url})
        forward['results'][url] = {
            'status': 'detail_aligned',
            'detail_date_full': 'Maggio 2026',
            'resolved_date_full': '1 maggio 2026 - 31 dicembre 2026',
            'event': {'title': 'Radici nella pietra', 'event_city': 'Udine',
                      'schedule_kind': 'month_range',
                      'date_label': 'maggio–dicembre 2026'}}
        audit = create_display_audit(forward, semantic, today=date(2026, 10, 5))
        card = next(item for item in audit['cards'] if item['url'] == url)
        self.assertEqual(card['schedule_kind'], 'month_range')
        self.assertEqual(card['date_label'], 'maggio–dicembre 2026')
        self.assertEqual(card['date_precision'], 'month')
        self.assertNotIn('verified_programme_occurrences', card)

    def test_single_public_day_has_plain_date_label(self):
        forward, semantic = self.snapshots()
        url = self.base + 'risvegli'
        forward['candidates'].append({'url': url})
        forward['results'][url] = {
            'status': 'detail_aligned',
            'resolved_date_full': '11 ottobre 2026',
            'event': {'title': 'Risvegli', 'event_city': 'Udine',
                      'verified_programme_occurrences': ['2026-10-11']}}
        audit = create_display_audit(forward, semantic, today=date(2026, 10, 5))
        card = next(item for item in audit['cards'] if item['url'] == url)
        self.assertEqual(card['date_label'], '11 ottobre 2026')
        self.assertEqual(card['schedule_kind'], 'single')

    def test_english_day_first_detail_retains_one_dated_card(self):
        forward, semantic = self.snapshots()
        url = self.base + 'music-live-danza-diffusa'
        forward['candidates'].append({'url': url})
        forward['results'][url] = {
            'status': 'detail_aligned',
            'detail_date_full': 'Sunday 18th October 2026',
            'event': {'title': 'Music Live', 'event_city': 'Trieste',
                      'start_date': '2026-10-18', 'end_date': '2026-10-18'}}
        audit = create_display_audit(forward, semantic, today=date(2026, 10, 5))
        card = next(item for item in audit['cards'] if item['url'] == url)
        self.assertEqual(card['start_date'], '2026-10-18')
        self.assertEqual(card['schedule_kind'], 'single')

    def test_detail_changed_after_index_still_requires_review(self):
        forward, semantic = self.snapshots()
        url = self.base + 'conflitto'
        semantic['results'][url]['reason'] = 'detail_changed_since_index'
        audit = create_display_audit(forward, semantic, today=date(2026, 10, 5))
        self.assertNotIn(url, {item['url'] for item in audit['cards']})
        self.assertIn({'url': url, 'reason': 'detail_changed_since_index'},
                      audit['review'])

    def test_snapshots_must_match(self):
        forward, semantic = self.snapshots()
        semantic['index_snapshot_id'] = 'other'
        with self.assertRaises(ValueError):
            create_display_audit(forward, semantic, today=date(2026, 10, 5))

    def test_rechecked_detail_can_supply_one_more_card(self):
        forward, semantic = self.snapshots()
        url = self.base + 'riallineato'
        forward['candidates'].append({'url': url})
        forward['results'][url] = {'status': 'review_required'}
        discrepancy = {
            'schema': 'turismofvg-discrepancy-audit-v1',
            'as_of_date': '2026-10-05', 'index_snapshot_id': 'abc',
            'items': [{'url': url}], 'attempts': {},
            'results': {url: {
                'status': 'identity_aligned_on_recheck',
                'detail_date_full': '10 ottobre 2026',
                'event': {'title': 'Riallineato', 'event_city': 'Udine',
                          'description_excerpt': 'Dettaglio aggiornato.',
                          'description_source_url': url}}}}
        audit = create_display_audit(forward, semantic, discrepancy=discrepancy,
                                     today=date(2026, 10, 5))
        card = next(item for item in audit['cards'] if item['url'] == url)
        self.assertEqual(card['description_excerpt'], 'Dettaglio aggiornato.')

    def test_sitemap_only_detail_adds_a_source_linked_card(self):
        forward, semantic = self.snapshots()
        url = self.base + 'solo-sitemap'
        sitemap_cards = {
            'schema': 'turismofvg-sitemap-detail-cards-v1',
            'as_of_date': '2026-10-05', 'index_snapshot_id': 'abc',
            'items': [{'url': url}], 'attempts': {},
            'results': {url: {'status': 'detail_aligned',
                              'detail_date_full': '1 ottobre 2026 - 31 ottobre 2026',
                              'event': {'title': 'Solo sitemap', 'event_city': 'Udine',
                                        'description_excerpt': 'Programma della festa.',
                                        'description_source_url': url}}}}
        audit = create_display_audit(forward, semantic, sitemap_cards=sitemap_cards,
                                     today=date(2026, 10, 5))
        card = next(item for item in audit['cards'] if item['url'] == url)
        self.assertEqual(card['sort_date'], '2026-10-05')
        self.assertEqual(card['schedule_kind'], 'period')
        self.assertEqual(card['description_source_url'], url)
        self.assertEqual(audit['source_candidates'], 4)
        sitemap_cards['index_snapshot_id'] = 'other'
        with self.assertRaises(ValueError):
            create_display_audit(forward, semantic, sitemap_cards=sitemap_cards,
                                 today=date(2026, 10, 5))

    def test_official_badges_anchor_yearless_recurrence_without_daily_claim(self):
        forward, semantic = self.snapshots()
        url = self.base + 'mercatino'
        forward['candidates'].append({'url': url,
                                      'listing_occurrences': ['2026-10-11', '2026-11-08']})
        forward['results'][url] = {
            'status': 'detail_aligned',
            'schedule_interpretation': 'recurrence_requires_expansion',
            'detail_date_full': 'Seconda domenica di ogni mese',
            'event': {'title': 'Mercatino', 'event_city': 'Udine'}}
        audit = create_display_audit(forward, semantic, today=date(2026, 10, 5))
        card = next(item for item in audit['cards'] if item['url'] == url)
        self.assertEqual(card['schedule_kind'], 'recurring')
        self.assertEqual(card['start_date'], '2026-10-11')
        self.assertEqual(card['sort_date'], '2026-10-11')
        self.assertIn('2026', card['date_label'])
        self.assertNotIn('occurrences', card)

    def test_full_year_past_badges_do_not_hide_future_recurrence(self):
        forward, semantic = self.snapshots()
        url = self.base + 'mercatino-annuale'
        forward['candidates'].append({'url': url,
                                      'listing_occurrences': ['2026-01-11', '2026-10-11']})
        forward['results'][url] = {
            'status': 'detail_aligned',
            'schedule_interpretation': 'recurrence_requires_expansion',
            'detail_date_full': 'Seconda domenica di ogni mese',
            'event': {'title': 'Mercatino', 'event_city': 'Udine'}}
        audit = create_display_audit(forward, semantic, today=date(2026, 10, 5))
        card = next(item for item in audit['cards'] if item['url'] == url)
        self.assertEqual(card['start_date'], '2026-10-11')
        self.assertEqual(card['schedule_kind'], 'recurring')

    def test_past_inauguration_does_not_hide_current_exhibition(self):
        forward, semantic = self.snapshots()
        url = self.base + 'mostra'
        semantic['results'][url] = {'status': 'review_required',
                                    'reason': 'no_future_explicit_dates'}
        audit = create_display_audit(forward, semantic, today=date(2026, 10, 5))
        self.assertIn(url, {item['url'] for item in audit['cards']})

    def test_elapsed_dates_in_detail_stay_in_one_discrete_card(self):
        forward, semantic = self.snapshots()
        url = self.base + 'sagra'
        forward['candidates'].append({'url': url,
                                      'listing_occurrences': ['2026-10-07', '2026-10-11']})
        forward['results'][url] = {
            'status': 'detail_aligned',
            'schedule_interpretation': 'discrete_dates_conflict',
            'detail_date_full': '1, 2, 3, 4 / 7, 8, 9, 10, 11 ottobre 2026',
            'event': {'title': 'Sagra', 'event_city': 'Udine'}}
        audit = create_display_audit(forward, semantic, today=date(2026, 10, 5))
        card = next(item for item in audit['cards'] if item['url'] == url)
        self.assertEqual(card['schedule_kind'], 'explicit_dates')
        self.assertEqual(card['start_date'], '2026-10-01')
        self.assertEqual(card['end_date'], '2026-10-11')

    def test_new_year_index_detail_adds_card_only_after_inspection(self):
        forward, semantic = self.snapshots()
        url = self.base + 'nuova'
        year_control = {
            'schema': 'turismofvg-current-year-control-v1',
            'as_of_date': '2026-10-05', 'attempts': {},
            'entries': {url: {'candidate': {'url': url,
                                           'listing_occurrences': ['2026-10-12']}}},
            'results': {url: {'status': 'detail_aligned',
                              'detail_date_full': '12 ottobre 2026',
                              'event': {'title': 'Nuova', 'event_city': 'Udine'}}}}
        audit = create_display_audit(forward, semantic, today=date(2026, 10, 5),
                                     year_control=year_control)
        self.assertIn(url, {card['url'] for card in audit['cards']})
        year_control['results'] = {}
        with self.assertRaises(ValueError):
            create_display_audit(forward, semantic, today=date(2026, 10, 5),
                                 year_control=year_control)

    def test_annual_control_is_direct_source_for_next_cycle(self):
        url = self.base + 'annuale'
        control = {
            'schema': 'turismofvg-current-year-control-v1',
            'inspection_version': INSPECTION_VERSION,
            'as_of_date': '2026-10-05', 'attempts': {},
            'index_fingerprint': 'annual-1',
            'entries': {url: {'candidate': {'url': url,
                                           'listing_occurrences': ['2026-10-12']},
                              'listing_display': {'category': 'sagra',
                                                  'image': 'https://example.test/a.jpg'}}},
            'results': {url: {'status': 'detail_aligned',
                              'detail_date_full': '12 ottobre 2026',
                              'event': {'title': 'Festa', 'event_city': 'Udine',
                                        'description_excerpt': 'Festa in piazza.',
                                        'description_source_url': url}}},
        }
        audit = create_year_display_audit(control, today=date(2026, 10, 5))
        self.assertTrue(audit['source_complete'])
        self.assertEqual(summary(audit)['cards_total'], 1)
        self.assertEqual(audit['cards'][0]['category'], 'sagra')
        self.assertEqual(audit['cards'][0]['description_excerpt'], 'Festa in piazza.')
        control['inspection_version'] = 1
        self.assertFalse(create_year_display_audit(
            control, today=date(2026, 10, 5))['source_complete'])
        control['inspection_version'] = INSPECTION_VERSION
        control['results'][url] = {'status': 'review_required',
                                   'reason': 'badge_not_in_explicit_programme'}
        audit = create_year_display_audit(control, today=date(2026, 10, 5))
        self.assertFalse(audit['source_complete'])
        self.assertEqual(summary(audit)['quarantined'], 1)
        self.assertEqual(summary(audit)['cards_total'], 0)
        control['results'] = {}
        with self.assertRaises(ValueError):
            create_year_display_audit(control, today=date(2026, 10, 5))

    def test_corrobated_programme_overrides_wrong_structured_end(self):
        forward, semantic = self.snapshots()
        url = self.base + 'zucche'
        forward['candidates'].append({'url': url})
        forward['results'][url] = {
            'status': 'detail_aligned',
            'detail_date_full': '18 ottobre 2026 - 24 ottobre 2026',
            'event': {'title': 'Festa delle Zucche', 'event_city': 'Udine',
                      'verified_programme_occurrences': [
                          '2026-10-18', '2026-10-24', '2026-10-25']}}
        audit = create_display_audit(forward, semantic, today=date(2026, 10, 5))
        card = next(item for item in audit['cards'] if item['url'] == url)
        self.assertEqual(card['end_date'], '2026-10-25')
        self.assertEqual(card['schedule_kind'], 'explicit_dates')
        self.assertIn('3 date nel programma', card['date_label'])

    def test_verified_month_label_stays_month_precision(self):
        forward, semantic = self.snapshots()
        url = self.base + 'ottobre-rosa'
        forward['candidates'].append({'url': url,
                                      'listing_occurrences': ['2026-10-09']})
        forward['results'][url] = {
            'status': 'detail_aligned', 'detail_date_full': 'ottobre 2026',
            'event': {'title': 'Ottobre Rosa', 'event_city': 'Udine',
                      'month_schedule_verified': True}}
        audit = create_display_audit(forward, semantic, today=date(2026, 10, 5))
        card = next(item for item in audit['cards'] if item['url'] == url)
        self.assertEqual(card['schedule_kind'], 'month')
        self.assertEqual(card['date_label'], 'ottobre 2026')
        self.assertEqual(card['sort_date'], '2026-10-09')


if __name__ == '__main__':
    unittest.main()
