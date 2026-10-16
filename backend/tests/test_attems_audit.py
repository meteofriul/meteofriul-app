from copy import deepcopy
from datetime import date
import unittest
from unittest.mock import MagicMock, patch

from app.events.pilot_attems_audit import (
    BASE, REVIEWED_DETAIL_VERSIONS, REVIEWED_EVENT_IDS,
    REVIEWED_EXHIBITION_PATHS, _fetch, audit_payloads, watch_changes,
)


TODAY = date(2026, 10, 7)
EVENT_PATH = '/incontro-123'
EXHIBITION_PATH = '/it/mostra-456'


def sample():
    event = {'id': 11, 'title': 'Incontro', 'full_url': EVENT_PATH,
             'start_event_date': '2026-10-08 00:00:00',
             'end_event_date': '2026-10-08 00:00:00'}
    return {
        'events': {'articles': [event]},
        'event_category': {'id': 15308, 'articles': [
            {**event, 'published_date': '2026-10-01T10:00:00'}]},
        'news': {'id': 15309, 'articles': []},
        'exhibitions': {'id': 13463, 'articles': []},
        'concluded': {'id': 14035, 'articles': []},
        'homepage': f'<a href="{EXHIBITION_PATH}">vai alla mostra</a>',
        'event_list': '<strong>1</strong> di <strong>1</strong> risultati',
        'details': {
            123: {'attribute': {'title': 'Incontro', 'full_url': EVENT_PATH,
                                'published': True,
                                'start_event_date_formatted': '2026-10-08T00:00:00',
                                'end_event_date_formatted': '2026-10-08T00:00:00'},
                  'modules': [{'module_type': 'event',
                               'start_event_date': '2026-10-08 00:00:00',
                               'end_event_date': '2026-10-08 00:00:00',
                               'intro': '8 ottobre 2026, Palazzo Attems Petzenstein',
                               'description': 'Incontro alle ore 19'}]},
            456: {'attribute': {'title': 'Mostra', 'full_url': '/mostra-456',
                                'published': True},
                  'modules': [{'module_type': 'content', 'description':
                               'Palazzo Attems Petzenstein, Gorizia. '
                               'Dal 27 giugno al 29 novembre 2026'}]},
        },
        'today': TODAY,
        'reviewed_news': {},
    }


class PalazzoAttemsAuditTests(unittest.TestCase):
    def test_temporary_gateway_error_is_retried_with_bounded_pause(self):
        failed = MagicMock(status_code=502)
        failed.__enter__.return_value = failed
        recovered = MagicMock(status_code=200)
        recovered.__enter__.return_value = recovered
        recovered.iter_content.return_value = [b'{}']
        with (patch('app.events.pilot_attems_audit.requests.get',
                    side_effect=[failed, recovered]) as get,
              patch('app.events.pilot_attems_audit.sleep') as pause):
            self.assertEqual(_fetch(BASE + '/it/'), b'{}')
        self.assertEqual(get.call_count, 2)
        pause.assert_called_once_with(2)

    def test_verified_event_and_current_exhibition(self):
        report = audit_payloads(**sample())
        self.assertTrue(report['source_complete'])
        self.assertEqual(len(report['verified']), 2)
        self.assertEqual(report['verified'][1]['end_date'], '2026-11-29')

    def test_missing_venue_or_multisite_poster_blocks_source(self):
        data = sample()
        data['details'][123]['modules'][0]['intro'] = '8 ottobre 2026, ore 19'
        report = audit_payloads(**data)
        self.assertFalse(report['source_complete'])
        self.assertIn('venue_not_in_event_text', report['blockers'][0]['reasons'])
        data = sample()
        data['details'][123]['modules'][0].update({
            'intro': 'Palazzo Attems Petzenstein e Galleria Spazzapan',
            'description': '<img src="/poster.jpg">'})
        report = audit_payloads(**data)
        self.assertEqual(report['blockers'][0]['reasons'],
                         ['multi_site_without_text_schedule', 'programme_image_only'])

    def test_future_cancellation_blocks_and_listing_loss_raises(self):
        data = sample()
        news = {'id': 22, 'title': 'Comunicazione', 'intro': 'Evento annullato',
                'full_url': '/avviso-789', 'published_date': '2026-10-07T10:00:00',
                'modified': '2026-10-07T10:15:00'}
        data['news']['articles'].append(news)
        data['reviewed_news'] = {22: '2026-10-07T10:15:00'}
        data['details'][789] = {
            'attribute': {'full_url': '/avviso-789',
                          'published_date': '2026-10-07T10:00:00',
                          'description': 'Domenica 11 ottobre evento cancellato'},
            'modules': []}
        report = audit_payloads(**data)
        self.assertEqual(report['recent_cancellations'][0]['event_date'], '2026-10-11')
        self.assertTrue(any('cancellation_requires_reconciliation' in
                            item['reasons'] for item in report['blockers']))
        changed = deepcopy(data)
        changed['event_list'] = '<strong>0</strong> di <strong>0</strong> risultati'
        with self.assertRaisesRegex(ValueError, 'count mismatch'):
            audit_payloads(**changed)

    def test_new_news_or_current_exhibition_category_requires_review(self):
        data = sample()
        data['news']['articles'].append({
            'id': 44, 'title': 'Nuovo appuntamento',
            'published_date': '2026-10-07T10:00:00',
            'modified': '2026-10-07T10:00:00'})
        report = audit_payloads(**data)
        self.assertIn(44, report['blockers'][0]['article_ids'])
        data = sample()
        data['exhibitions']['articles'].append({
            'id': 55, 'title': 'Nuova mostra', 'published_date': '2026-10-07T10:00:00'})
        with self.assertRaisesRegex(ValueError, 'unreviewed current content'):
            audit_payloads(**data)
        data = sample()
        data['news']['articles'].append({
            'id': 66, 'title': 'Scheda storica',
            'published_date': '2025-06-01T10:00:00',
            'modified': '2026-10-07T10:00:00'})
        report = audit_payloads(**data)
        self.assertIn('unreviewed_historical_news_update',
                      report['blockers'][0]['reasons'])

    def test_module_date_disagreement_blocks_source(self):
        data = sample()
        data['details'][123]['modules'][0]['end_event_date'] = '2026-10-09 00:00:00'
        with self.assertRaisesRegex(ValueError, 'module dates disagree'):
            audit_payloads(**data)

    def test_watch_ignores_known_gaps_and_flags_new_inventory_or_detail(self):
        report = {'as_of': '2026-10-07', 'event_api_ids': sorted(REVIEWED_EVENT_IDS),
                  'current_exhibition_paths': sorted(REVIEWED_EXHIBITION_PATHS),
                  'detail_versions': {str(key): value for key, value in
                                      REVIEWED_DETAIL_VERSIONS.items()},
                  'blockers': [{'reasons': ['venue_not_in_event_text']}]}
        self.assertEqual(watch_changes(report), [])
        changed = deepcopy(report)
        changed['event_api_ids'].append(999999)
        changed['detail_versions']['174333'] = '2026-10-08T12:00:00'
        self.assertEqual(watch_changes(changed),
                         ['detail_changed:174333', 'event_inventory_changed'])
        ready = deepcopy(report)
        ready['source_complete'] = True
        self.assertEqual(watch_changes(ready), ['source_ready_for_integration_review'])


if __name__ == '__main__':
    unittest.main()
