import unittest
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import patch

from firebase_admin import exceptions as firebase_exceptions
from firebase_admin import messaging

from app.push.fcm import (
    FcmConfigurationError,
    FcmOfficialAlertMessage,
    FcmSenderUnavailable,
    FcmTokenInvalid,
    FirebaseCloudMessagingSender,
)
from app.infrastructure.firebase import FirebaseInitializationError


FCM_TOKEN = "fcm-token-that-is-long-enough-for-tests"
WEB_FID = "c123456789012345678901"
WEB_LINK = "https://meteofriul.app/?tab=bulletin"


class FirebaseCloudMessagingSenderTests(unittest.TestCase):
    def make_payload(self, **overrides):
        values = {
            "target_kind": "fcm_token",
            "target_value": FCM_TOKEN,
            "platform": "android",
            "title": "Meteo Fri\u00fbl",
            "body": "Allerta ufficiale attiva.",
            "data": {
                "type": "official_alert",
                "alert_id": "alert-1",
                "issued_at": "2026-08-14T10:00:00+00:00",
                "area": "FVG-A",
            },
            "ttl_seconds": 600,
            "channel_id": "mf_official_alerts_v1",
            "collapse_key": "mf-official-alerts",
            "notification_tag": "mf-official-alerts",
        }
        values.update(overrides)
        return FcmOfficialAlertMessage(**values)

    def test_android_target_uses_token_and_android_delivery_config_only(self):
        firebase_app = object()
        sender = FirebaseCloudMessagingSender(
            firebase_app_provider=lambda: firebase_app
        )
        with patch.object(
            messaging,
            "send",
            return_value="projects/test/messages/1",
        ) as send:
            message_id = sender.send(self.make_payload())

        self.assertEqual(message_id, "projects/test/messages/1")
        message = send.call_args.args[0]
        self.assertIs(send.call_args.kwargs["app"], firebase_app)
        self.assertEqual(message.token, FCM_TOKEN)
        self.assertIsNone(message.fid)
        self.assertEqual(message.notification.title, "Meteo Fri\u00fbl")
        self.assertEqual(message.android.collapse_key, "mf-official-alerts")
        self.assertEqual(message.android.ttl, timedelta(seconds=600))
        self.assertEqual(
            message.android.notification.channel_id,
            "mf_official_alerts_v1",
        )
        self.assertEqual(message.android.notification.tag, "mf-official-alerts")
        self.assertIsNone(message.webpush)

    def test_legacy_token_alias_still_builds_an_android_message(self):
        firebase_app = object()
        sender = FirebaseCloudMessagingSender(
            firebase_app_provider=lambda: firebase_app
        )
        payload = self.make_payload(target_value="", token=FCM_TOKEN)
        with patch.object(
            messaging,
            "send",
            return_value="projects/test/messages/legacy",
        ) as send:
            sender.send(payload)

        message = send.call_args.args[0]
        self.assertEqual(message.token, FCM_TOKEN)
        self.assertIsNone(message.fid)
        self.assertIsNotNone(message.android)
        self.assertIsNone(message.webpush)

    def test_web_target_uses_fid_and_complete_webpush_config_only(self):
        firebase_app = object()
        sender = FirebaseCloudMessagingSender(
            firebase_app_provider=lambda: firebase_app
        )
        payload = self.make_payload(
            target_kind="firebase_installation_id",
            target_value=WEB_FID,
            platform="web",
            web_link=WEB_LINK,
        )
        with patch.object(
            messaging,
            "send",
            return_value="projects/test/messages/web",
        ) as send:
            message_id = sender.send(payload)

        self.assertEqual(message_id, "projects/test/messages/web")
        message = send.call_args.args[0]
        self.assertIs(send.call_args.kwargs["app"], firebase_app)
        self.assertEqual(message.fid, WEB_FID)
        self.assertIsNone(message.token)
        self.assertIsNone(message.android)
        self.assertEqual(message.webpush.headers["TTL"], "600")
        self.assertEqual(message.webpush.notification.title, "Meteo Fri\u00fbl")
        self.assertEqual(
            message.webpush.notification.body,
            "Allerta ufficiale attiva.",
        )
        self.assertEqual(
            message.webpush.notification.icon,
            "/branding/web-notification-icon_mf-r4-20260927-192.png",
        )
        self.assertEqual(
            message.webpush.notification.tag,
            "mf-official-alerts",
        )
        self.assertEqual(message.webpush.fcm_options.link, WEB_LINK)

    def test_mismatched_platform_and_target_kind_are_configuration_errors(self):
        sender = FirebaseCloudMessagingSender(firebase_app_provider=object)
        invalid_targets = (
            {
                "platform": "web",
                "target_kind": "fcm_token",
                "target_value": FCM_TOKEN,
                "web_link": WEB_LINK,
            },
            {
                "platform": "android",
                "target_kind": "firebase_installation_id",
                "target_value": WEB_FID,
            },
            {
                "platform": "web",
                "target_kind": "firebase_installation_id",
                "target_value": "",
                "web_link": WEB_LINK,
            },
        )
        for invalid_target in invalid_targets:
            with self.subTest(invalid_target=invalid_target):
                with patch.object(messaging, "send") as send:
                    with self.assertRaises(FcmConfigurationError):
                        sender.send(self.make_payload(**invalid_target))
                send.assert_not_called()

    def test_web_target_rejects_a_non_https_or_relative_link(self):
        sender = FirebaseCloudMessagingSender(firebase_app_provider=object)
        for invalid_link in (
            "",
            "/?tab=bulletin",
            "http://meteofriul.app/?tab=bulletin",
        ):
            with self.subTest(invalid_link=invalid_link):
                payload = self.make_payload(
                    target_kind="firebase_installation_id",
                    target_value=WEB_FID,
                    platform="web",
                    web_link=invalid_link,
                )
                with patch.object(messaging, "send") as send:
                    with self.assertRaises(FcmConfigurationError):
                        sender.send(payload)
                send.assert_not_called()

    def test_only_terminal_token_errors_are_classified_as_invalid_token(self):
        sender = FirebaseCloudMessagingSender(firebase_app_provider=object)
        with patch.object(
            messaging,
            "send",
            side_effect=messaging.UnregisteredError("unregistered"),
        ):
            with self.assertRaises(FcmTokenInvalid):
                sender.send(self.make_payload())

    def test_invalid_argument_is_reported_as_configuration_error(self):
        sender = FirebaseCloudMessagingSender(firebase_app_provider=object)
        with patch.object(
            messaging,
            "send",
            side_effect=firebase_exceptions.InvalidArgumentError("bad payload"),
        ):
            with self.assertRaises(FcmConfigurationError):
                sender.send(self.make_payload())

    def test_firebase_initialization_failure_is_configuration_error(self):
        def fail_initialization():
            raise FirebaseInitializationError("firebase init failed")

        sender = FirebaseCloudMessagingSender(
            firebase_app_provider=fail_initialization
        )

        with self.assertRaises(FcmConfigurationError):
            sender.send(self.make_payload())

    def test_permission_denied_is_reported_as_configuration_error(self):
        sender = FirebaseCloudMessagingSender(firebase_app_provider=object)
        with patch.object(
            messaging,
            "send",
            side_effect=firebase_exceptions.PermissionDeniedError("missing IAM"),
        ):
            with self.assertRaises(FcmConfigurationError):
                sender.send(self.make_payload())

    def test_batch_preserves_per_device_success_and_failure(self):
        firebase_app = object()
        sender = FirebaseCloudMessagingSender(
            firebase_app_provider=lambda: firebase_app
        )
        response = SimpleNamespace(
            responses=[
                SimpleNamespace(
                    success=True,
                    message_id="projects/test/messages/1",
                    exception=None,
                ),
                SimpleNamespace(
                    success=False,
                    message_id=None,
                    exception=messaging.UnregisteredError("unregistered"),
                ),
            ]
        )
        with patch.object(
            messaging,
            "send_each",
            return_value=response,
        ) as send_each:
            outcomes = sender.send_batch([
                self.make_payload(target_value=f"{FCM_TOKEN}-1"),
                self.make_payload(target_value=f"{FCM_TOKEN}-2"),
            ])

        self.assertIs(send_each.call_args.kwargs["app"], firebase_app)
        self.assertEqual(len(send_each.call_args.args[0]), 2)
        self.assertTrue(outcomes[0].success)
        self.assertEqual(outcomes[0].message_id, "projects/test/messages/1")
        self.assertFalse(outcomes[1].success)
        self.assertEqual(outcomes[1].error_code, "fcm_token_invalid")


if __name__ == "__main__":
    unittest.main()
