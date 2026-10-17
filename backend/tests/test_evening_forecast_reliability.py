"""No FCM or Firestore calls: retirement and uncertain-claim regressions."""
import io
import json
import unittest
from contextlib import redirect_stdout
from types import SimpleNamespace
from unittest.mock import Mock, patch

from google.api_core.exceptions import Aborted, DeadlineExceeded, PermissionDenied, ServiceUnavailable
from firebase_admin import messaging
from app.push.fcm import (FcmBatchOutcome, FcmConfigurationError,
    FcmSenderUnavailable, FirebaseCloudMessagingSender)
from app.repositories.push import PushRepositoryUnavailable
from app.services.evening_forecast_delivery import EveningForecastDeliveryService
from app.services.notice_municipalities import NoticeMunicipalityCatalog
from app.jobs import send_evening_forecast
from test_evening_forecast_delivery import (FakeDeviceRepository, FakeSource,
    FakeSender, config, device, snapshot, NOW)
import test_push_fcm as fcm_tests
import test_morning_forecast_delivery as morning_tests


def storage_error(cause):
    error = PushRepositoryUnavailable("private storage message")
    error.__cause__ = cause
    return error


class EveningReliabilityTests(unittest.TestCase):
    def service(self, repository, sender):
        return EveningForecastDeliveryService(device_repository=repository,
            source=FakeSource(snapshot()), sender=sender, config=config(),
            require_single_target=False, location_catalog=NoticeMunicipalityCatalog(),
            now=lambda: NOW)

    def run_case(self, *, outcomes=None, disable=True, finish=True):
        outcomes = outcomes or [FcmBatchOutcome(error_code="fcm_token_invalid")]
        devices = [device(device_id=hex(n + 1)[2:] * 64, token=f"token-{n}")
                   for n in range(len(outcomes))]
        repo = FakeDeviceRepository(devices)
        repo.disable_device = Mock(return_value=disable)
        repo.finish_local_notice_delivery = Mock(return_value=finish)
        sender = FakeSender()
        sender.send_batch = Mock(return_value=outcomes)
        return repo, sender, self.service(repo, sender)

    def test_confirmed_retirements_are_counted_separately_from_successful_sends(self):
        repo, sender, service = self.run_case(outcomes=[FcmBatchOutcome(message_id="m1"),
            FcmBatchOutcome(error_code="fcm_token_invalid"),
            FcmBatchOutcome(error_code="fcm_token_invalid")])
        result = service.run()
        self.assertEqual((result.status, result.sent, result.retired_targets, result.failed),
                         ("sent", 1, 2, 0))
        self.assertEqual(repo.disable_device.call_count, 2)
        for call in repo.disable_device.call_args_list:
            self.assertTrue(call.kwargs["expected_target_hash"])
            self.assertEqual(call.kwargs["expected_target_kind"], "fcm_token")
        self.assertEqual(sender.send_batch.call_count, 1)
        self.assertNotIn("token-", json.dumps(result.summary()))

    def test_only_retirements_exit_successfully_without_claiming_a_delivery(self):
        repo, sender, service = self.run_case()
        result = service.run()
        self.assertEqual((result.status, result.retired_targets, result.sent),
                         ("retired_targets", 1, 0))
        output = io.StringIO()
        with patch.object(send_evening_forecast, "get_evening_forecast_delivery_service",
                          return_value=SimpleNamespace(run=lambda: result)), redirect_stdout(output):
            self.assertEqual(send_evening_forecast.main(), 0)
        self.assertEqual(json.loads(output.getvalue())["retired_targets"], 1)

    def test_unconfirmed_finish_or_rotation_never_counts_as_retired(self):
        for disable, finish in [(True, False), (False, True)]:
            with self.subTest(disable=disable, finish=finish):
                repo, sender, service = self.run_case(disable=disable, finish=finish)
                result = service.run()
                self.assertEqual((result.retired_targets, result.failed), (0, 1))
                if not finish:
                    repo.disable_device.assert_not_called()

    def test_cleanup_failure_is_not_hidden(self):
        repo, sender, service = self.run_case()
        repo.disable_device.side_effect = PushRepositoryUnavailable("secret")
        result = service.run()
        self.assertEqual((result.retired_targets, result.failed), (0, 1))

    def test_real_sender_errors_keep_failure_and_configuration_classification(self):
        for error, state in [(FcmConfigurationError("secret"), "failed_configuration"),
                             (FcmSenderUnavailable("secret"), "failed_transient")]:
            with self.subTest(state=state):
                repo, sender, service = self.run_case()
                sender.send_batch.side_effect = error
                result = service.run()
                self.assertEqual(result.failed, 1)
                self.assertEqual(result.retired_targets, 0)
                self.assertEqual(repo.finish_local_notice_delivery.call_args.kwargs["state"], state)
                repo.disable_device.assert_not_called()

    def test_transient_pre_send_storage_read_retries_once_and_sends_once(self):
        for cause in [ServiceUnavailable("secret"), DeadlineExceeded("secret"), Aborted("secret")]:
            with self.subTest(cause=type(cause).__name__):
                repo, sender, service = self.run_case(outcomes=[FcmBatchOutcome(message_id="m")])
                claim = SimpleNamespace(claimed=True, state="sending", claim_id="c", delivery_id="d")
                repo.claim_local_notice_delivery = Mock(side_effect=[storage_error(cause), claim])
                with patch("app.services.evening_forecast_delivery.sleep") as sleep:
                    result = service.run()
                self.assertEqual((result.sent, result.failed), (1, 0))
                self.assertEqual(repo.claim_local_notice_delivery.call_count, 2)
                self.assertEqual(sender.send_batch.call_count, 1)
                sleep.assert_called_once_with(0.2)

    def test_permission_and_unknown_storage_errors_are_not_retried(self):
        for cause in [PermissionDenied("secret"), ValueError("secret"), None]:
            with self.subTest(cause=type(cause).__name__):
                repo, sender, service = self.run_case()
                repo.claim_local_notice_delivery = Mock(side_effect=storage_error(cause))
                with patch("app.services.evening_forecast_delivery.sleep") as sleep:
                    result = service.run()
                self.assertEqual((result.failed, result.storage_failed), (1, 1))
                self.assertEqual(repo.claim_local_notice_delivery.call_count, 1)
                sleep.assert_not_called()
                sender.send_batch.assert_not_called()

    def test_persistent_storage_failure_is_bounded_and_keeps_job_failed(self):
        repo, sender, service = self.run_case()
        repo.claim_local_notice_delivery = Mock(side_effect=storage_error(ServiceUnavailable("secret")))
        with patch("app.services.evening_forecast_delivery.sleep"):
            result = service.run()
        self.assertEqual((result.failed, result.storage_failed), (1, 1))
        self.assertEqual(repo.claim_local_notice_delivery.call_count, 2)
        sender.send_batch.assert_not_called()

    def test_lost_claim_commit_response_never_sends_or_reports_recovery(self):
        repo, sender, service = self.run_case()
        repo.claim_local_notice_delivery = Mock(side_effect=[storage_error(DeadlineExceeded("secret")),
            SimpleNamespace(claimed=False, state="delivery_in_progress")])
        with patch("app.services.evening_forecast_delivery.sleep"):
            result = service.run()
        self.assertEqual((result.failed, result.storage_failed, result.in_progress), (1, 1, 0))
        sender.send_batch.assert_not_called()

    def test_finish_failure_after_send_never_repeats_fcm(self):
        repo, sender, service = self.run_case(outcomes=[FcmBatchOutcome(message_id="m")])
        repo.finish_local_notice_delivery.side_effect = storage_error(ServiceUnavailable("secret"))
        result = service.run()
        self.assertEqual((result.sent_unconfirmed, result.storage_failed, result.failed_groups), (1, 1, 1))
        self.assertEqual(result.failed, 1)
        self.assertEqual(sender.send_batch.call_count, 1)
        self.assertEqual(repo.finish_local_notice_delivery.call_count, 1)

    def test_morning_delivery_keeps_existing_invalid_token_failure_policy(self):
        repo = morning_tests.FakeDeviceRepository([morning_tests.device()])
        sender = morning_tests.FakeSender()
        sender.send_batch = Mock(return_value=[FcmBatchOutcome(error_code="fcm_token_invalid")])
        service = morning_tests.MorningForecastDeliveryService(
            device_repository=repo,
            source=morning_tests.FakeSource(morning_tests.snapshot()),
            sender=sender,
            config=morning_tests.config(),
            require_single_target=False,
            location_catalog=NoticeMunicipalityCatalog(),
            now=lambda: morning_tests.NOW,
        )
        result = service.run()
        self.assertEqual((result.status, result.failed, result.retired_targets), ("failed", 1, 0))
        self.assertEqual(len(repo.disabled), 1)

    def test_sender_mismatch_is_configuration_failure_in_single_and_batch_send(self):
        sender = FirebaseCloudMessagingSender(firebase_app_provider=object)
        payload = fcm_tests.FirebaseCloudMessagingSenderTests().make_payload()
        with patch.object(messaging, "send", side_effect=messaging.SenderIdMismatchError("secret")):
            with self.assertRaises(FcmConfigurationError):
                sender.send(payload)
        response = SimpleNamespace(responses=[SimpleNamespace(success=False, message_id=None,
            exception=messaging.SenderIdMismatchError("secret"))])
        with patch.object(messaging, "send_each", return_value=response):
            self.assertEqual(sender.send_batch([payload])[0].error_code, "fcm_configuration_error")
        with patch.object(messaging, "send_each", side_effect=messaging.SenderIdMismatchError("secret")):
            with self.assertRaises(FcmConfigurationError):
                sender.send_batch([payload])


if __name__ == "__main__":
    unittest.main()
