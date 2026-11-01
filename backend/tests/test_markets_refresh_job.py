import copy
from datetime import date
from tempfile import TemporaryDirectory
from pathlib import Path
import unittest

from app.markets.model import MarketError
from app.markets.refresh import due_markets, next_month
from app.markets.refresh_job import run, sources_for
from app.markets.repository import SQLiteMarketRepository
from app.markets.service import MarketsService
from tests.test_markets_archive import small_seed


class MarketsRefreshJobTests(unittest.TestCase):
    def setUp(self):
        temporary = TemporaryDirectory(prefix="mf-refresh-job-")
        self.addCleanup(temporary.cleanup)
        self.service = MarketsService(SQLiteMarketRepository(Path(temporary.name) / "archive.sqlite3", seed=small_seed()))
        self.today = date(2026, 11, 1)

    def collect(self, market, editions, sources, *, as_of):
        return {"marketId": market["id"], "issues": [], "observations": [{
            "sourceUrl": market["url"], "retrievedAt": as_of.isoformat() + "T09:00:00Z", "contentHash": "a" * 64,
            "fields": {"place": "Piazza nuova"}, "editions": [],
            "evidence": [{"field": "place", "value": "Piazza nuova", "excerpt": "Nuova sede: Piazza nuova"}]}]}

    def test_preview_reads_sources_but_does_not_write(self):
        before = self.service.repository.read()
        result = run(self.service, as_of=self.today, collector=self.collect)
        self.assertFalse(result["applied"])
        self.assertEqual(result["changes"], 1)
        self.assertEqual(self.service.repository.read(), before)

    def test_apply_saves_without_publication_or_confirmation_and_repeat_is_not_due(self):
        catalogue = self.service.catalogue()
        result = run(self.service, as_of=self.today, apply=True, collector=self.collect)
        self.assertEqual(result["changes"], 1)
        self.assertEqual(self.service.state()["markets"][0]["place"], "Piazza nuova")
        self.assertEqual(self.service.catalogue(), catalogue)
        result = run(self.service, as_of=self.today, apply=True, collector=lambda *args, **kwargs: self.fail("not due"))
        self.assertEqual(result["status"], "not_due")
        self.assertEqual(self.service.state()["revision"], 1)

    def test_panel_edit_during_fetch_yields_conflict_without_lost_edit(self):
        def collect(*args, **kwargs):
            state = self.service.state()
            state["markets"][0]["place"] = "Correzione simultanea"
            self.service.mutate(action="save", state=state, expected_revision=0, operation_id="panel-concurrent",
                                reason="Segnalazione", actor="owner")
            return self.collect(*args, **kwargs)
        with self.assertRaisesRegex(MarketError, "markets_revision_conflict"):
            run(self.service, as_of=self.today, apply=True, collector=collect)
        self.assertEqual(self.service.state()["markets"][0]["place"], "Correzione simultanea")

    def test_due_month_uses_calendar_month_not_every_invocation(self):
        record = self.service.repository.read()
        record["state"]["dates"] = []
        record["state"]["markets"][0]["validThrough"] = "2027-12-31"
        record["refreshLedger"] = {"M001": {"lastAttempt": "2026-01-31"}}
        self.assertEqual(next_month(date(2026, 1, 31)), date(2026, 2, 28))
        self.assertEqual(due_markets(record, date(2026, 2, 27)), [])
        self.assertEqual(len(due_markets(record, date(2026, 2, 28))), 1)

    def test_near_edition_or_expiry_checked_weekly(self):
        record = self.service.repository.read()
        record["refreshLedger"] = {"M001": {"lastAttempt": "2026-10-25"}}
        self.assertEqual(due_markets(record, date(2026, 10, 31)), [])
        self.assertEqual(len(due_markets(record, self.today)), 1)
        record["state"]["dates"] = []
        record["state"]["markets"][0]["validThrough"] = "2026-11-02"
        self.assertEqual(len(due_markets(record, self.today)), 1)

    def test_collector_failure_is_recorded_and_retried_next_day(self):
        def fail(*args, **kwargs):
            raise RuntimeError("SECRET MUST NOT LEAK")
        report = run(self.service, as_of=self.today, apply=True, collector=fail)
        self.assertEqual(report["reports"][0]["issues"], ["collector_failure"])
        self.assertNotIn("SECRET", str(self.service.repository.read()))
        self.assertEqual(due_markets(self.service.repository.read(), self.today), [])
        self.assertEqual(len(due_markets(self.service.repository.read(), date(2026, 11, 2))), 1)

    def test_collector_cannot_redirect_an_update_to_another_identity(self):
        def wrong(*args, **kwargs):
            result = self.collect(*args, **kwargs)
            result["marketId"] = "M002"
            return result
        run(self.service, as_of=self.today, apply=True, collector=wrong)
        self.assertEqual(self.service.state()["markets"][0]["place"], "Piazza")

    def test_sources_include_original_research_without_mutating_it(self):
        state = self.service.state()
        state["drafts"] = [{"id": "R1", "linkedMarketIds": ["M001"], "sources": [{"url": "https://example.test/source"}],
                            "outstanding": ["Confermare festività"]}]
        original = copy.deepcopy(state)
        self.assertEqual(sources_for(state, state["markets"][0]), [{"url": "https://example.test/source"}])
        self.assertEqual(state, original)

    def test_inactive_markets_remain_skipped_even_with_force(self):
        state = self.service.state()
        state["markets"][0]["status"] = "archived"
        self.service.mutate(action="save", state=state, expected_revision=0, operation_id="archive-local",
                            actor="owner", reason="Mercato cessato")
        report = run(self.service, as_of=self.today, apply=True, force=True,
                     collector=lambda *args, **kwargs: self.fail("archived"))
        self.assertEqual(report["checkedMarkets"], 0)

    def test_deadline_saves_completed_work_and_leaves_remaining_markets_due(self):
        state = self.service.state()
        second = copy.deepcopy(state["markets"][0])
        second.update(id="M002", name="Secondo mercato")
        state["markets"].append(second)
        self.service.mutate(action="save", state=state, expected_revision=0, operation_id="add-market-two",
                            actor="owner", reason="Secondo mercato documentato")
        ticks = iter([0, 61])
        report = run(self.service, as_of=self.today, apply=True, collector=self.collect,
                     max_seconds=60, clock=lambda: next(ticks))
        self.assertEqual(report["checkedMarkets"], 1)
        self.assertEqual(report["remainingMarkets"], 1)
        self.assertTrue(report["budgetExhausted"])
        self.assertEqual([item["id"] for item in due_markets(self.service.repository.read(), self.today)], ["M002"])

    def test_unattempted_market_has_priority_over_retry_to_avoid_starvation(self):
        record = self.service.repository.read()
        second = copy.deepcopy(record["state"]["markets"][0])
        second.update(id="M002", name="Secondo mercato")
        record["state"]["markets"].append(second)
        record["refreshLedger"] = {"M001": {"lastAttempt": "2026-10-31", "retryable": True}}
        self.assertEqual([item["id"] for item in due_markets(record, self.today)], ["M002", "M001"])


if __name__ == "__main__":
    unittest.main()
