import unittest
from datetime import date

from app.events.pilot_regional_discrepancy_audit import (
    create_snapshot, inspect_batch, inspect_item, refine_saved_flags,
)


class RegionalDiscrepancyAuditTests(unittest.TestCase):
    url = 'https://www.turismofvg.it/eventi/prova'

    def item(self):
        return {'url': self.url, 'source': 'TurismoFVG',
                'title': 'Festa', 'event_city': 'Udine',
                'listing_occurrences': ['2026-10-10'],
                'discovery_kind': 'filtered_calendar',
                'prior_reason': 'detail_identity_or_schedule_requires_review'}

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

    def test_conflicting_badge_stays_in_review_with_specific_flag(self):
        result = inspect_item(self.item(), self.detail(date_text='11 ottobre 2026'),
                              today=date(2026, 10, 5))
        self.assertEqual(result['status'], 'review_required')
        self.assertIn('badge_outside_detail_bounds', result['flags'])

    def test_schedule_change_is_flagged(self):
        result = inspect_item(self.item(),
                              self.detail(description='Concerto rinviato al 10 ottobre.'),
                              today=date(2026, 10, 5))
        self.assertEqual(result['status'], 'review_required')
        self.assertIn('possible_schedule_change', result['flags'])
        self.assertEqual(result['notice_term'], 'rinviato')

    def test_recheck_can_report_alignment_without_publishing(self):
        result = inspect_item(self.item(), self.detail(), today=date(2026, 10, 5))
        self.assertEqual(result['status'], 'identity_aligned_on_recheck')
        self.assertTrue(result['preview_available'])
        self.assertEqual(result['event']['description_source_url'], self.url)

    def test_single_locality_can_use_its_own_checked_map_point(self):
        item = {**self.item(), 'event_city': 'Sistiana'}
        html = self.detail().replace('>Udine</div>', '>Sistiana</div>')
        html += ('<iframe id="gmap_canvas" src="https://www.google.com/maps/'
                 'embed/v1/place?q=45.76575%2013.637&amp;zoom=13"></iframe>')
        result = inspect_item(item, html, today=date(2026, 10, 5))
        self.assertEqual(result['status'], 'identity_aligned_on_recheck')
        self.assertEqual(result['event']['location_confidence'], 'source_map')
        self.assertEqual(result['event']['lat'], 45.76575)

    def test_snapshot_is_resumable_and_only_selects_discrepancies(self):
        forward = {'schema': 'turismofvg-forward-detail-audit-v1',
                   'as_of_date': '2026-10-05', 'index_snapshot_id': 'abc',
                   'candidates': [self.item()],
                   'results': {self.url: {'status': 'review_required',
                                          'reason': 'detail_conflict'}},
                   'attempts': {}}
        snapshot = create_snapshot(forward)
        self.assertEqual(len(snapshot['items']), 1)
        failed = inspect_batch(snapshot, fetch_html=lambda _: (_ for _ in ()).throw(TimeoutError()))
        self.assertEqual(failed['attempts'][self.url]['count'], 1)
        recovered = inspect_batch(failed, fetch_html=lambda _: self.detail())
        self.assertEqual(recovered['attempts'], {})
        self.assertEqual(recovered['results'][self.url]['status'],
                         'identity_aligned_on_recheck')

    def test_saved_multicity_result_flags_only_unresolved_place(self):
        snapshot = {'schema': 'turismofvg-discrepancy-audit-v1',
                    'results': {self.url: {
                        'status': 'review_required',
                        'flags': ['promotion_or_policy_needs_review'],
                        'detail_city': 'Latisana, Aprilia Marittima',
                        'detail_date_full': '10 ottobre 2026'}}}
        refined = refine_saved_flags(snapshot)
        self.assertEqual(refined['results'][self.url]['flags'],
                         ['multiple_cities_need_date_mapping'])


if __name__ == '__main__':
    unittest.main()
