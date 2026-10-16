import unittest
from app.events.pilot_comparison import compare, inspect, reference


def event(**kwargs):
    return dict(dict(source='Test', title='Concerto', url='https://example.org/event/1',
                     event_city='Udine', start_date='2026-09-12', time='18:00'), **kwargs)


class ComparisonTests(unittest.TestCase):
    def test_replicas_not_hidden_by_first_match(self):
        result = compare([event(), event(time='21:00')], [event()])
        self.assertEqual(len(result['candidate_pairs']), 2)
        self.assertIn('time', result['candidate_pairs'][1]['differences'])

    def test_same_url_different_town_is_conflict(self):
        result = compare([event()], [event(event_city='Trieste')])
        self.assertIn('city', result['candidate_pairs'][0]['differences'])

    def test_different_url_and_town_not_matched(self):
        result = compare([event()], [event(url='https://example.org/event/2', event_city='Trieste')])
        self.assertEqual(result['legacy_without_candidate'], [0])
        self.assertEqual(result['pilot_without_candidate'], [0])

    def test_exact_duplicates_preserve_different_sessions(self):
        self.assertEqual(inspect([event(), event(), event(time='21:00')])['exact_duplicate_groups'], [[0, 1]])

    def test_date_and_time_validation(self):
        result = inspect([event(time='25:00', occurrences=['2026-09-13'])])
        self.assertIn('invalid_time', result['issues'][0]['reasons'])
        self.assertIn('occurrence_outside_range', result['issues'][0]['reasons'])

    def test_unknown_time_not_converted(self):
        result = compare([event(time='')], [event(time='00:00')])
        self.assertIn('time', result['candidate_pairs'][0]['differences'])

    def test_url_tracking_removed_identity_query_kept(self):
        self.assertEqual(reference('https://example.org/event?id=2&utm_source=a#x'), 'https://example.org/event?id=2')

    def test_does_not_modify_records(self):
        item = event()
        compare([item], [item])
        self.assertNotIn('end_date', item)
