"""Email reminder contract: temporary archives and simulated SMTP only."""
from __future__ import annotations

import copy
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import smtplib
from tempfile import TemporaryDirectory
from threading import Event
import unittest
from unittest.mock import Mock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.markets import admin_router, get_markets_service
from app.markets.email_reminder import email_address, message_for, public_settings, run, send_smtp, smtp_config
from app.markets.model import MarketError
from app.markets.repository import SQLiteMarketRepository
from app.markets.review import ROME, reminder
from app.markets.service import MarketsService
from tests.test_markets_archive import small_seed


CONFIG = {"host": "smtp.example.test", "username": "test-account",
          "password": "SIMULATED-SMTP-PASSWORD", "from": "system@example.test"}
SMTP_ENV = {"MARKETS_REMINDER_SMTP_" + key: "" for key in ("HOST", "USERNAME", "PASSWORD", "FROM")}


class AfterClaimRepository:
    """Insert a concurrent panel edit after the durable claim, before sending."""
    def __init__(self, repository, after_claim):
        self.repository, self.after_claim = repository, after_claim

    def read(self):
        return self.repository.read()

    def mutate(self, **kwargs):
        result = self.repository.mutate(**kwargs)
        delivery = result[0].get("emailReminder", {}).get("delivery", {})
        if delivery.get("status") == "sending" and self.after_claim:
            callback, self.after_claim = self.after_claim, None
            callback()
        return result


class MarketsEmailReminderTests(unittest.TestCase):
    def setUp(self):
        temporary = TemporaryDirectory(prefix="mf-market-email-")
        self.addCleanup(temporary.cleanup)
        self.path = Path(temporary.name) / "archive.sqlite3"
        self.seed = small_seed()
        self.seed["markets"][0]["internalNotes"] = "PRIVATE-MARKET-NOTE"
        self.seed["markets"][0]["scheduleNote"] = "Verificare le variazioni per le festività."
        self.seed["drafts"] = [{"id": "email-test-practice", "status": "draft", "linkedMarketIds": ["M001"],
                                "editorialNotes": "PRIVATE-PRACTICE-NOTE",
                                "sources": [{"url": "https://private.example.test/research"}]}]
        self.repository = SQLiteMarketRepository(self.path, seed=self.seed)
        self.service = MarketsService(self.repository)
        self.now = datetime(2026, 11, 2, 9, 0, tzinfo=ROME)
        self.serial = 0
        environment = patch.dict(os.environ, SMTP_ENV)
        environment.start()
        self.addCleanup(environment.stop)
        network = patch("app.markets.email_reminder.smtplib.SMTP_SSL",
                        side_effect=AssertionError("Real SMTP is forbidden in these tests"))
        network.start()
        self.addCleanup(network.stop)

    def configure(self, *, recipient="info@example.test", enabled=True, revision=None, operation=None):
        self.serial += 1
        return self.service.configure_email(
            expected_revision=self.service.state()["revision"] if revision is None else revision,
            operation_id=operation or f"email-settings-test-{self.serial}", recipient=recipient,
            enabled=enabled, actor="test-owner",
        )

    def test_settings_are_durable_idempotent_and_preserve_market_data(self):
        before = self.repository.read()
        first = self.configure(recipient="info@EXAMPLE.TEST", revision=0, operation="email-configure-once")
        replay = self.configure(recipient="info@EXAMPLE.TEST", revision=0, operation="email-configure-once")
        self.assertTrue(replay["idempotentReplay"])
        self.assertEqual(replay["revision"], first["revision"])
        restarted = MarketsService(SQLiteMarketRepository(self.path))
        self.assertEqual(restarted.state()["emailReminder"]["recipient"], "info@example.test")
        self.assertTrue(restarted.state()["emailReminder"]["enabled"])
        after = self.repository.read()
        self.assertEqual(after["state"], before["state"])
        self.assertEqual(after["catalogue"], before["catalogue"])
        self.assertEqual(len(after["audit"]), 1)

    def test_settings_enforce_revision_and_operation_payload(self):
        self.configure(revision=0, operation="email-configure-once")
        with self.assertRaisesRegex(MarketError, "markets_revision_conflict"):
            self.configure(revision=0, operation="email-configure-other")
        with self.assertRaisesRegex(MarketError, "markets_operation_conflict"):
            self.configure(revision=0, operation="email-configure-once", recipient="other@example.test")
        self.assertEqual(self.service.state()["emailReminder"]["recipient"], "info@example.test")

    def test_settings_reject_invalid_addresses_and_nonboolean_enable(self):
        for address in ("", "not-an-email", "one@example.test,two@example.test", "a@b.test\r\nBcc: other@example.test",
                        ".first@example.test", "first..last@example.test", "first@example..test"):
            with self.subTest(address=address), self.assertRaises(MarketError):
                self.configure(recipient=address)
        with self.assertRaises(MarketError):
            self.configure(enabled="true")
        self.assertEqual(self.repository.read()["revision"], 0)

    def test_normal_state_save_cannot_forge_email_preferences_or_delivery(self):
        self.configure()
        before = copy.deepcopy(self.repository.read()["emailReminder"])
        state = self.service.state()
        state["emailReminder"] = {"enabled": False, "recipient": "other@example.test",
                                  "delivery": {"status": "accepted", "period": "2099-01"}}
        self.service.mutate(action="save", expected_revision=state["revision"], operation_id="email-forged-state",
                            reason="Verifica metadata", actor="test-owner", state=state)
        self.assertEqual(self.repository.read()["emailReminder"], before)

    def test_email_settings_endpoint_requires_auth_and_strict_payload(self):
        app = FastAPI()
        app.include_router(admin_router)
        def no_read():
            self.fail("Unauthenticated email settings must not read archive")
        app.dependency_overrides[get_markets_service] = no_read
        payload = {"expectedRevision": 0, "operationId": "email-api-operation", "recipient": "info@example.test", "enabled": True}
        environment = {"K_SERVICE": "", "CLOUD_RUN_JOB": "", "MARKETS_ADMIN_AUTH_MODE": "local",
                       "MARKETS_ADMIN_LOCAL_TOKEN": "email-test-only-token"}
        with TestClient(app) as client, patch.dict(os.environ, environment):
            self.assertEqual(client.put("/api/admin/markets/email-settings", json=payload).status_code, 401)
            app.dependency_overrides[get_markets_service] = lambda: self.service
            headers = {"Authorization": "Bearer email-test-only-token"}
            for changed in ({"enabled": "true"}, {"expectedRevision": True}, {"recipient": "bad-address"}, {"smtpPassword": "forbidden"}):
                with self.subTest(changed=changed):
                    response = client.put("/api/admin/markets/email-settings", json={**payload, **changed}, headers=headers)
                    self.assertEqual(response.status_code, 422)
            response = client.put("/api/admin/markets/email-settings", json=payload, headers=headers)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.headers["cache-control"], "no-store")
            self.assertEqual(response.json()["emailReminder"]["recipient"], "info@example.test")

    def test_no_send_and_no_write_until_enabled_due_and_configured(self):
        sender = Mock(return_value={"status": "accepted", "errorCode": None})
        before = self.repository.read()
        self.assertEqual(run(self.repository, now=self.now, config=CONFIG, sender=sender)["status"], "disabled")
        self.assertEqual(self.repository.read(), before)
        self.configure()
        before = self.repository.read()
        early = datetime(2026, 11, 2, 8, 59, 59, tzinfo=ROME)
        self.assertEqual(run(self.repository, now=early, config=CONFIG, sender=sender)["status"], "not_due")
        self.assertEqual(run(self.repository, now=self.now, sender=sender)["status"], "not_configured")
        sender.assert_not_called()
        self.assertEqual(self.repository.read(), before)

    def test_accepted_once_per_period_survives_restart_and_keeps_catalogue_unchanged(self):
        self.configure()
        before = self.repository.read()
        sender = Mock(return_value={"status": "accepted", "errorCode": None})
        first = run(self.repository, now=self.now, config=CONFIG, sender=sender)
        self.assertEqual(first["status"], "accepted")
        self.assertEqual(run(SQLiteMarketRepository(self.path), now=datetime(2026,11,20,9,tzinfo=ROME),
                             config=CONFIG, sender=sender)["status"], "skipped")
        self.assertEqual(sender.call_count, 1)
        next_month = run(self.repository, now=datetime(2026,12,7,9,tzinfo=ROME), config=CONFIG, sender=sender)
        self.assertEqual(next_month["status"], "accepted")
        self.assertEqual(sender.call_count, 2)
        after = self.repository.read()
        self.assertEqual(after["state"], before["state"])
        self.assertEqual(after["catalogue"], before["catalogue"])
        self.assertEqual(after["publishedRevision"], before["publishedRevision"])
        self.assertNotIn("delivered", json.dumps(after["emailReminder"]))

    def test_failed_delivery_retries_only_on_next_italian_day(self):
        self.configure()
        sender = Mock(return_value={"status": "failed", "errorCode": "connection_failed"})
        self.assertEqual(run(self.repository, now=self.now, config=CONFIG, sender=sender)["status"], "failed")
        same_day = datetime(2026,11,2,23,59,tzinfo=ROME)
        self.assertEqual(run(self.repository, now=same_day, config=CONFIG, sender=sender)["status"], "skipped")
        following = datetime(2026,11,3,0,1,tzinfo=ROME)
        self.assertEqual(run(self.repository, now=following, config=CONFIG, sender=sender)["status"], "failed")
        self.assertEqual(sender.call_count, 2)

    def test_retry_day_is_normalized_to_rome_even_if_caller_passes_utc(self):
        self.configure()
        sender = Mock(return_value={"status": "failed", "errorCode": "connection_failed"})
        first = datetime(2026,11,3,0,5,tzinfo=ROME)
        run(self.repository, now=first, config=CONFIG, sender=sender)
        same_italian_day = datetime(2026,11,2,23,10,tzinfo=timezone.utc)
        self.assertEqual(run(self.repository, now=same_italian_day, config=CONFIG, sender=sender)["status"], "skipped")
        self.assertEqual(sender.call_count, 1)

    def test_uncertain_outcome_is_not_retried_and_exception_details_do_not_leak(self):
        self.configure()
        sender = Mock(side_effect=RuntimeError("PRIVATE-SERVER-RESPONSE"))
        result = run(self.repository, now=self.now, config=CONFIG, sender=sender)
        self.assertEqual(result, {"status": "uncertain", "period": "2026-11", "errorCode": "delivery_unknown"})
        self.assertEqual(run(self.repository, now=datetime(2026,11,3,9,tzinfo=ROME), config=CONFIG, sender=sender)["status"], "skipped")
        self.assertEqual(sender.call_count, 1)
        self.assertNotIn("PRIVATE-SERVER-RESPONSE", json.dumps(self.repository.read()))

    def test_interrupted_send_leaves_durable_uncertain_claim_without_duplicate(self):
        self.configure()
        sender = Mock(side_effect=SystemExit("simulated process interruption"))
        with self.assertRaises(SystemExit):
            run(self.repository, now=self.now, config=CONFIG, sender=sender)
        self.assertEqual(self.repository.read()["emailReminder"]["delivery"]["status"], "sending")
        self.assertEqual(self.service.state()["emailReminder"]["lastDelivery"]["status"], "uncertain")
        restarted = SQLiteMarketRepository(self.path)
        self.assertEqual(run(restarted, now=datetime(2026,11,3,9,tzinfo=ROME), config=CONFIG, sender=sender)["status"], "skipped")
        self.assertEqual(sender.call_count, 1)

    def test_concurrent_claims_send_only_once(self):
        self.configure()
        entered, release = Event(), Event()
        def sender(message, config):
            entered.set()
            if not release.wait(timeout=5):
                raise AssertionError("Test did not release sender")
            return {"status": "accepted", "errorCode": None}
        with ThreadPoolExecutor(max_workers=2) as executor:
            first = executor.submit(run, self.repository, now=self.now, config=CONFIG, sender=sender)
            try:
                self.assertTrue(entered.wait(timeout=5))
                second = run(SQLiteMarketRepository(self.path), now=self.now, config=CONFIG,
                             sender=lambda *args: self.fail("A second send must not start"))
                self.assertEqual(second["status"], "skipped")
            finally:
                release.set()
            self.assertEqual(first.result(timeout=5)["status"], "accepted")

    def test_recipient_change_after_claim_cancels_old_address_and_allows_unsent_new_address(self):
        self.configure()
        sender = Mock(return_value={"status": "accepted", "errorCode": None})
        wrapped = AfterClaimRepository(self.repository, lambda: self.configure(recipient="new@example.test"))
        first = run(wrapped, now=self.now, config=CONFIG, sender=sender)
        self.assertEqual(first["status"], "cancelled")
        sender.assert_not_called()
        second = run(self.repository, now=self.now, config=CONFIG, sender=sender)
        self.assertEqual(second["status"], "accepted")
        self.assertEqual(sender.call_args.args[0]["To"], "new@example.test")

    def test_disable_after_claim_prevents_send_and_does_not_erase_settings(self):
        self.configure()
        sender = Mock(return_value={"status": "accepted", "errorCode": None})
        wrapped = AfterClaimRepository(self.repository, lambda: self.configure(enabled=False))
        self.assertEqual(run(wrapped, now=self.now, config=CONFIG, sender=sender)["status"], "cancelled")
        sender.assert_not_called()
        self.assertFalse(self.repository.read()["emailReminder"]["enabled"])
        self.assertEqual(run(self.repository, now=self.now, config=CONFIG, sender=sender)["status"], "disabled")

    def test_review_completed_after_claim_cancels_message_without_changing_facts(self):
        self.configure()
        before = self.repository.read()
        def complete():
            with patch("app.markets.service.reminder", side_effect=lambda record: reminder(record, now=self.now)):
                self.service.complete_review(expected_revision=self.service.state()["revision"],
                    operation_id="email-complete-review", period="2026-11", reason="Ricerca completata", actor="test-owner")
        wrapped = AfterClaimRepository(self.repository, complete)
        sender = Mock(return_value={"status": "accepted", "errorCode": None})
        self.assertEqual(run(wrapped, now=self.now, config=CONFIG, sender=sender)["status"], "cancelled")
        sender.assert_not_called()
        after = self.repository.read()
        self.assertEqual(before["state"], after["state"])
        self.assertEqual(before["catalogue"], after["catalogue"])

    def test_panel_disable_during_send_is_preserved_when_outcome_is_saved(self):
        self.configure()
        def sender(message, config):
            self.configure(enabled=False)
            return {"status": "accepted", "errorCode": None}
        self.assertEqual(run(self.repository, now=self.now, config=CONFIG, sender=sender)["status"], "accepted")
        settings = self.repository.read()["emailReminder"]
        self.assertFalse(settings["enabled"])
        self.assertEqual(settings["delivery"]["status"], "accepted")

    def test_message_contains_only_aggregate_reminder_and_no_private_research_or_password(self):
        self.configure()
        record = self.repository.read()
        message = message_for(record, config=CONFIG, now=self.now)
        text = message.as_string()
        for private in ("PRIVATE-MARKET-NOTE", "PRIVATE-PRACTICE-NOTE", "private.example.test", CONFIG["password"], "INTERNAL-NOTE"):
            self.assertNotIn(private, text)
        self.assertEqual(message["From"], CONFIG["from"])
        self.assertEqual(message["To"], "info@example.test")
        self.assertIn("Scopri", message.get_content())
        self.assertNotIn("calendari stagionali", message.get_content())
        quarterly = message_for(record, config=CONFIG, now=datetime(2027,2,1,9,tzinfo=ROME))
        self.assertIn("calendari stagionali", quarterly.get_content())

    def test_configuration_and_public_settings_do_not_expose_smtp_secrets(self):
        self.assertIsNone(smtp_config())
        environment = {"MARKETS_REMINDER_SMTP_" + key.upper(): value for key, value in CONFIG.items()}
        with patch.dict(os.environ, environment):
            self.assertEqual(smtp_config(), CONFIG)
            settings = public_settings(self.repository.read(), self.repository)
            self.assertTrue(settings["senderConfigured"])
            for value in (CONFIG["username"], CONFIG["password"], CONFIG["host"]):
                self.assertNotIn(value, json.dumps(settings))

    def test_smtp_uses_implicit_tls_and_records_acceptance_not_delivery(self):
        self.configure()
        message = message_for(self.repository.read(), config=CONFIG, now=self.now)
        connection = Mock()
        connection.send_message.return_value = {}
        with patch("app.markets.email_reminder.smtplib.SMTP_SSL", return_value=connection) as factory:
            result = send_smtp(message, CONFIG)
        self.assertEqual(result, {"status": "accepted", "errorCode": None})
        self.assertEqual(factory.call_args.args, (CONFIG["host"], 465))
        self.assertEqual(factory.call_args.kwargs["timeout"], 30)
        self.assertIsNotNone(factory.call_args.kwargs["context"])
        connection.login.assert_called_once_with(CONFIG["username"], CONFIG["password"])
        connection.send_message.assert_called_once_with(message)
        connection.close.assert_called_once()

    def test_smtp_failures_before_send_are_retryable_and_send_disconnect_is_uncertain(self):
        self.configure()
        message = message_for(self.repository.read(), config=CONFIG, now=self.now)
        with patch("app.markets.email_reminder.smtplib.SMTP_SSL", side_effect=OSError("PRIVATE-CONNECTION-ERROR")):
            self.assertEqual(send_smtp(message, CONFIG), {"status": "failed", "errorCode": "connection_failed"})
        for stage, error, expected in (
            ("login", smtplib.SMTPAuthenticationError(535, b"PRIVATE-AUTH-RESPONSE"), {"status": "failed", "errorCode": "authentication_failed"}),
            ("send_message", smtplib.SMTPDataError(554, b"PRIVATE-REJECT-RESPONSE"), {"status": "failed", "errorCode": "message_rejected"}),
            ("send_message", smtplib.SMTPServerDisconnected("PRIVATE-DISCONNECT"), {"status": "uncertain", "errorCode": "delivery_unknown"}),
        ):
            with self.subTest(stage=stage, exception=type(error).__name__):
                connection = Mock()
                getattr(connection, stage).side_effect = error
                with patch("app.markets.email_reminder.smtplib.SMTP_SSL", return_value=connection):
                    self.assertEqual(send_smtp(message, CONFIG), expected)
                if stage == "login":
                    connection.send_message.assert_not_called()
                connection.close.assert_called_once()


if __name__ == "__main__":
    unittest.main()
