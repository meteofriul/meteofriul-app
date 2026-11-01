import copy
from datetime import date, datetime
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.markets import admin_router, get_markets_service
from app.markets.model import MarketError
from app.markets.repository import SQLiteMarketRepository
from app.markets.review import ROME, reminder, review_queue
from app.markets.service import MarketsService
from tests.test_markets_archive import small_seed


class MarketsReviewTests(unittest.TestCase):
    def setUp(self):
        temporary = TemporaryDirectory(prefix="mf-markets-review-")
        self.addCleanup(temporary.cleanup)
        self.repository = SQLiteMarketRepository(Path(temporary.name) / "archive.sqlite3", seed=small_seed())
        self.service = MarketsService(self.repository)

    def at(self, value, record=None):
        return reminder(record or self.repository.read(), now=datetime.fromisoformat(value).replace(tzinfo=ROME))

    def test_first_monday_nine_and_month_rollover(self):
        before = self.at("2026-11-02T08:59:59")
        self.assertFalse(before["due"])
        self.assertEqual(before["dueAt"], "2026-11-02T09:00:00+01:00")
        due = self.at("2026-11-02T09:00:00")
        self.assertTrue(due["due"])
        self.assertEqual(due["period"], "2026-11")
        self.assertEqual(due["nextDueAt"], "2026-12-07T09:00:00+01:00")

    def test_overdue_remains_visible_and_quarterly_scope_is_not_lost(self):
        overdue = self.at("2027-03-01T09:01:00")
        self.assertEqual(overdue["dueAt"], "2026-11-02T09:00:00+01:00")
        self.assertEqual(overdue["period"], "2027-03")
        self.assertEqual(overdue["kind"], "quarterly")
        record = self.repository.read()
        record["manualReview"] = {"completedPeriod": "2027-03", "completedAt": "2027-03-01T09:05:00Z"}
        next_one = self.at("2027-04-05T09:00:00", record)
        self.assertEqual(next_one["kind"], "monthly")
        self.assertEqual(next_one["dueAt"], "2027-04-05T09:00:00+02:00")
        self.assertEqual(self.at("2027-05-03T09:00:00", record)["kind"], "quarterly")

    def test_queue_retains_issues_from_other_markets_after_partial_run(self):
        record = self.repository.read()
        market = record["state"]["markets"][0]
        other = {**market, "id": "another-market", "name": "Altro mercato"}
        record["state"]["markets"].append(other)
        record["refreshLedger"] = {
            market["id"]: {"lastAttempt": "2026-11-01", "issues": ["unsupported_source_format"]},
            other["id"]: {"lastAttempt": "2026-11-02", "issues": ["known_calendar_conflict"]},
        }
        record["automation"] = {"reports": [{"marketId": other["id"], "issues": []}]}
        result = review_queue(record)
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["marketId"], other["id"])
        self.assertIn("unsupported_source_format", result[1]["issues"])
        record["state"]["markets"][1]["status"] = "archived"
        self.assertEqual(len(review_queue(record)), 1)
        record["refreshLedger"][market["id"]]["issues"] = []
        market["evidenceStatus"] = "conflict"
        self.assertEqual(review_queue(record)[0]["issues"], ["known_calendar_conflict"])

    def complete(self, **kwargs):
        return self.service.complete_review(**{"expected_revision": 0, "operation_id": "review-operation-one",
            "period": "2026-11", "reason": "Verificate fonti; note conservate nelle schede", "actor": "test-owner", **kwargs})

    def test_ack_is_persistent_idempotent_and_does_not_verify_or_publish_facts(self):
        initial = self.repository.read()
        with patch("app.markets.service.reminder", side_effect=lambda record: self.at("2026-11-02T10:00:00", record)):
            saved = self.complete()
            self.assertFalse(saved["reviewReminder"]["due"])
            self.assertEqual(saved["reviewReminder"]["nextDueAt"], "2026-12-07T09:00:00+01:00")
            self.assertTrue(self.complete()["idempotentReplay"])
            with self.assertRaises(MarketError) as failure:
                self.complete(operation_id="other-review-operation")
            self.assertEqual(failure.exception.status, 409)
        after = self.repository.read()
        self.assertEqual(after["state"], initial["state"])
        self.assertEqual(after["catalogue"], initial["catalogue"])
        self.assertEqual(after["revision"], 1)
        self.assertEqual(after["audit"][-1]["action"], "review")
        self.assertEqual(after["manualReview"]["completedPeriod"], "2026-11")

    def test_cannot_ack_future_or_stale_period(self):
        for now, period in (("2026-11-01T09:00:00", "2026-11"), ("2026-12-07T10:00:00", "2026-11")):
            with patch("app.markets.service.reminder", side_effect=lambda record: self.at(now, record)):
                with self.assertRaises(MarketError):
                    self.complete(period=period)
        self.assertEqual(self.repository.read()["revision"], 0)

    def test_refresh_preserves_ack_and_regular_save_cannot_forge_it(self):
        with patch("app.markets.service.reminder", side_effect=lambda record: self.at("2026-11-02T10:00:00", record)):
            self.complete()
        before = copy.deepcopy(self.repository.read()["manualReview"])
        state = self.service.state()
        state["manualReview"] = {"completedPeriod": "2099-01"}
        self.service.mutate(action="save", expected_revision=1, operation_id="save-review-operation", reason="Test metadata", actor="test-owner", state=state)
        market_id = state["markets"][0]["id"]
        self.service.refresh([{"marketId": market_id, "observations": [], "issues": ["source_unavailable"]}],
                             expected_revision=2, operation_id="refresh-review-operation", as_of=date(2026, 11, 2))
        self.assertEqual(self.repository.read()["manualReview"], before)
        self.assertEqual(self.service.state()["reviewReminder"]["items"][0]["issues"], ["source_unavailable"])

    def test_review_endpoint_requires_auth_and_validates_payload(self):
        app = FastAPI()
        app.include_router(admin_router)
        app.dependency_overrides[get_markets_service] = lambda: self.service
        client = TestClient(app)
        payload = {"expectedRevision": 0, "operationId": "api-review-operation", "reason": "Ricerca completata", "period": "2026-11"}
        env = {"K_SERVICE": "", "CLOUD_RUN_JOB": "", "MARKETS_ADMIN_AUTH_MODE": "local", "MARKETS_ADMIN_LOCAL_TOKEN": "test-review-token"}
        with patch.dict(os.environ, env), patch("app.markets.service.reminder", side_effect=lambda record: self.at("2026-11-02T10:00:00", record)):
            self.assertEqual(client.post("/api/admin/markets/review-complete", json=payload).status_code, 401)
            auth = {"Authorization": "Bearer test-review-token"}
            self.assertEqual(client.post("/api/admin/markets/review-complete", json={**payload, "period": "2026-13"}, headers=auth).status_code, 422)
            accepted = client.post("/api/admin/markets/review-complete", json=payload, headers=auth)
            self.assertEqual(accepted.status_code, 200)
            self.assertEqual(accepted.headers["cache-control"], "no-store")
            self.assertFalse(accepted.json()["reviewReminder"]["due"])


if __name__ == "__main__":
    unittest.main()
