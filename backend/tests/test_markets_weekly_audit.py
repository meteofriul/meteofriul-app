import copy
from datetime import date
import unittest

from app.markets.model import initial_record, MarketError
from app.markets.weekly_audit import scan, FirestoreWeeklyAuditStore
from tests.test_markets_archive import small_seed


class ReadOnlyRepository:
    storage = "firestore"

    def __init__(self, record):
        self.record = record
        self.reads = 0

    def read(self):
        self.reads += 1
        return copy.deepcopy(self.record)

    def mutate(self, **_):
        raise AssertionError("The weekly audit must never mutate the archive")


class FakeFirestore:
    def __init__(self):
        self.docs = {}
        self.fail_detail = False

    def collection(self, path):
        return FakeCollection(self, path)


class FakeCollection:
    def __init__(self, db, path):
        self.db, self.path = db, path

    def document(self, name):
        return FakeDocument(self.db, self.path + "/" + name)


class FakeDocument:
    def __init__(self, db, path):
        self.db, self.path = db, path

    def collection(self, name):
        return FakeCollection(self.db, self.path + "/" + name)

    def set(self, value, timeout=None):
        if self.db.fail_detail and "/markets/" in self.path:
            raise RuntimeError("simulated interruption")
        self.db.docs[self.path] = copy.deepcopy(value)

    def get(self, timeout=None):
        value = self.db.docs.get(self.path)
        return type("Snapshot", (), {"exists": value is not None,
                                     "to_dict": lambda self: copy.deepcopy(value)})()


class MarketsWeeklyAuditTests(unittest.TestCase):
    def setUp(self):
        record = initial_record(small_seed())
        original = record["state"]["markets"][0]
        record["state"]["markets"] = [{**copy.deepcopy(original), "id": f"M{i:03}", "status": status}
                                         for i, status in enumerate(("published", "draft", "suspended", "archived"), 1)]
        record["state"]["dates"] = []
        self.repository = ReadOnlyRepository(record)

    @staticmethod
    def collect(market, _editions, _sources, *, as_of):
        url = market["url"]
        return {"marketId": market["id"], "issues": [],
                "sourceChecks": [{"url": url, "status": "read", "contentHash": "b" * 64, "issues": []}],
                "observations": [{"sourceUrl": url, "retrievedAt": as_of.isoformat() + "T09:00:00Z",
                                  "contentHash": "b" * 64, "fields": {"place": "Piazza nuova"},
                                  "editions": [], "evidence": [{"field": "place", "value": "Piazza nuova",
                                                              "excerpt": "Sede: Piazza nuova"}]}]}

    def test_every_status_is_compared_without_archive_write(self):
        before = copy.deepcopy(self.repository.record)
        report = scan(self.repository, as_of=date(2026, 11, 13), collector=self.collect)
        self.assertEqual(report["status"], "completed")
        self.assertEqual(report["checkedMarkets"], 4)
        self.assertEqual(report["changedMarkets"], 4)
        self.assertEqual({item["status"] for item in report["markets"]},
                         {"published", "draft", "suspended", "archived"})
        self.assertTrue(all(item["changes"] == 1 for item in report["markets"]))
        self.assertEqual(report["details"]["M003"]["changesDetail"][0]["before"], "Piazza")
        self.assertEqual(report["details"]["M003"]["changesDetail"][0]["after"], "Piazza nuova")
        self.assertEqual(self.repository.record, before)

    def test_previous_source_hash_flags_page_change_without_invented_fact(self):
        previous = {"markets": [{"marketId": "M001", "sources": [{"url": "https://example.test/mercato",
                                                               "contentHash": "a" * 64}]}]}
        report = scan(self.repository, as_of=date(2026, 11, 13), collector=self.collect, previous=previous)
        self.assertTrue(next(item for item in report["markets"] if item["marketId"] == "M001")["sources"][0]["contentChanged"])
        self.assertFalse(next(item for item in report["markets"] if item["marketId"] == "M002")["sources"][0]["contentChanged"])

    def test_partial_scan_cannot_be_saved_as_latest(self):
        ticks = iter([0, 61])
        report = scan(self.repository, as_of=date(2026, 11, 13), collector=self.collect,
                      max_seconds=60, clock=lambda: next(ticks))
        self.assertEqual(report["status"], "partial")
        with self.assertRaisesRegex(MarketError, "markets_audit_incomplete"):
            FirestoreWeeklyAuditStore(type("Client", (), {"collection": lambda self, _: None})()).save(report)

    def test_collector_exception_redacts_sensitive_text(self):
        def fail(*_, **__):
            raise RuntimeError("secret token in source response")
        report = scan(self.repository, as_of=date(2026, 11, 13), collector=fail)
        self.assertNotIn("secret token", str(report))
        self.assertEqual(report["checkedMarkets"], 4)
        self.assertEqual(report["marketsWithIssues"], 4)

    def test_report_pointer_changes_only_after_all_market_details(self):
        db = FakeFirestore()
        store = FirestoreWeeklyAuditStore(db)
        report = scan(self.repository, as_of=date(2026, 11, 13), collector=self.collect)
        summary = store.save(report)
        self.assertNotIn("details", summary)
        self.assertEqual(store.latest(), summary)
        self.assertEqual(store.market("M003")["status"], "suspended")
        db.fail_detail = True
        later = scan(self.repository, as_of=date(2026, 11, 14), collector=self.collect)
        with self.assertRaisesRegex(RuntimeError, "simulated interruption"):
            store.save(later)
        self.assertEqual(store.latest(), summary)


if __name__ == "__main__":
    unittest.main()
