import time
import unittest
from contextlib import ExitStack
from unittest.mock import patch
from app.events import engine


class ProgressiveEventsTests(unittest.TestCase):
    def test_late_source_is_collected_without_restarting_other_sources(self):
        sources = ['fetch_turismofvg_events', 'fetch_sagrefvg_events', 'fetch_prolocofvg_events',
                   'fetch_paesiinfesta_events', 'fetch_eventifvg_events']
        def slow(*args):
            time.sleep(.05)
            return [{'id': 'late'}]
        def assemble(city, limit, lat, lon, results, guarded, completed, pending):
            return {'events': [e for entries in results.values() for e in entries], 'pending': sorted(pending)}
        with ExitStack() as stack:
            mocks = [stack.enter_context(patch.object(engine, name, side_effect=slow if i == 0 else None,
                                                    return_value=[{'id': name}])) for i, name in enumerate(sources)]
            stack.enter_context(patch.object(engine, 'EVENTS_SOURCE_COLLECTION_TIMEOUT', .005))
            stack.enter_context(patch.object(engine, 'load_guarded_official_events', return_value=[]))
            stack.enter_context(patch.object(engine, '_assemble_local_events_response', side_effect=assemble))
            updates = []
            final = engine.build_local_events_response('Udine', 100, 46, 13, on_partial=updates.append)
        self.assertTrue(updates)
        self.assertIn('turismo', updates[0]['pending'])
        self.assertEqual(len(updates[0]['events']), 4)
        self.assertEqual(len(final['events']), 5)
        self.assertEqual(final['pending'], [])
        for mock in mocks:
            mock.assert_called_once()
