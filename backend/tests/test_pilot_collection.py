import time
import unittest
from app.events.pilot_catalog import PILOT_PROJECT
from app.events.pilot_collection import collect

def good():
    return {"status": "ok", "events": [{"title": "sample"}]}

def slow():
    time.sleep(20)

def ambiguous():
    return []

def broken():
    raise ValueError('invalid listing at https://example.test/?token=secret')

def pordenonelegge_programme():
    from datetime import date, timedelta
    from app.events.pilot_pordenonelegge import parse_programme
    from tests.test_pilot_pordenonelegge import card, page
    days = tuple((date(2026, 9, 16) + timedelta(days=index)).isoformat()
                 for index in range(5))
    return parse_programme(page(''.join(card(day=day) for day in days), days=days))

class CollectionTests(unittest.TestCase):
    def test_registered_source_cannot_bypass_publication_gate(self):
        result = collect(PILOT_PROJECT, {'Azalea': good}, None, '2026-09-06T18:00:00Z', timeout=5)
        batch = result['sources']['Azalea']
        self.assertEqual(batch['events'], [])
        self.assertEqual(batch['status'], 'unavailable')
        self.assertEqual(batch['last_attempt_error_type'], 'source_verification_failed')
    def test_total_budget_is_bounded(self):
        with self.assertRaisesRegex(ValueError, "total collection"):
            collect(PILOT_PROJECT, {str(i): good for i in range(8)}, None,
                    "2026-09-06T18:00:00Z", timeout=120)

    def test_unknown_timeout_source_rejected(self):
        with self.assertRaisesRegex(ValueError, "source timeout"):
            collect(PILOT_PROJECT, {"a": good}, None, "2026-09-06T18:00:00Z",
                    source_timeouts={"other": 300})

    def test_success(self):
        result = collect(PILOT_PROJECT, {"a": good}, None, "2026-09-06T18:00:00Z", timeout=5)
        self.assertEqual(result["sources"]["a"]["status"], "fresh")

    def test_ambiguous_result_does_not_erase_previous(self):
        previous = {"sources": {"a": {"events": [{"title": "old"}], "status": "fresh"}}}
        result = collect(PILOT_PROJECT, {"a": ambiguous}, previous, "2026-09-06T18:00:00Z", timeout=5)
        self.assertEqual(result["sources"]["a"]["events"][0]["title"], "old")

    def test_pordenonelegge_regression_keeps_previous_snapshot_out_of_live_query(self):
        from datetime import date, timedelta, datetime
        from app.events.pilot_catalog import query_catalog
        days = [(date(2026, 9, 16) + timedelta(days=index)).isoformat()
                for index in range(5)]
        previous = {"sources": {"Pordenonelegge": {
            "events": [{"title": "Old", "source": "Pordenonelegge",
                        "url": "https://www.pordenonelegge.it/eventi/old",
                        "start_date": days[0], "event_city": "Pordenone",
                        "lat": 45.9567, "lon": 12.6605}],
            "status": "fresh", "updated_at": "2026-09-14T12:00:00Z",
            "verification": {"edition_id": "2026", "tab_dates": days,
                             "records_scanned": 100},
        }}}
        result = collect(PILOT_PROJECT, {"Pordenonelegge": pordenonelegge_programme},
                         previous, "2026-09-15T12:00:00Z", timeout=5)
        batch = result["sources"]["Pordenonelegge"]
        self.assertEqual(batch["status"], "stale")
        self.assertEqual(batch["last_attempt_error_type"], "source_verification_failed")
        self.assertEqual(batch["events"][0]["title"], "Old")
        self.assertEqual(query_catalog(result, 45.9567, 12.6605,
                                       now=datetime.fromisoformat("2026-09-15T12:00:00Z"))["events"], [])

    def test_timeout_is_bounded(self):
        start = time.monotonic()
        result = collect(PILOT_PROJECT, {"a": slow}, None, "2026-09-06T18:00:00Z", timeout=0.2)
        self.assertLess(time.monotonic() - start, 5)
        self.assertEqual(result["sources"]["a"]["status"], "unavailable")
        self.assertEqual(result["sources"]["a"]["last_attempt_error_type"], "timeout")

    def test_timeout_does_not_block_following_source(self):
        result = collect(PILOT_PROJECT, {"slow": slow, "next": good}, None,
                         "2026-10-26T04:00:00Z", timeout=5,
                         source_timeouts={"slow": 0.2})
        self.assertEqual(result['sources']['slow']['status'], 'unavailable')
        self.assertEqual(result['sources']['slow']['last_attempt_error_type'], 'timeout')
        self.assertEqual(result['sources']['next']['status'], 'fresh')
        self.assertEqual(len(result['sources']['next']['events']), 1)

    def test_adapter_exception_has_a_tag_and_redacted_detail(self):
        result = collect(PILOT_PROJECT, {"a": broken}, None,
                         "2026-09-06T18:00:00Z", timeout=5)
        batch = result['sources']['a']
        self.assertEqual(batch['status'], 'unavailable')
        self.assertEqual(batch['last_attempt_error_type'], 'adapter_exception')
        self.assertEqual(batch['last_attempt_exception_type'], 'ValueError')
        self.assertEqual(batch['last_attempt_error_detail'],
                         'invalid listing at [url]')

    def test_beta_rejected_before_start(self):
        with self.assertRaises(ValueError):
            collect("meteo-friul", {"a": good}, None, "2026-09-06T18:00:00Z")
