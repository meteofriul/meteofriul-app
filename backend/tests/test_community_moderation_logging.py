import unittest
from unittest.mock import patch

from app.services.community_moderation_logging import (
    LOGGING_WRITE_TIMEOUT_SECONDS,
    LOGGING_WRITE_URL,
    CommunityModerationLoggingError,
    build_ready_log_request,
    publish_ready_event,
)


def ready_event():
    return {
        "event": "community_moderation_digest_ready",
        "severity": "WARNING",
        "status": "ready",
        "should_emit": True,
        "digest_id": "a" * 64,
        "created_at": "2026-08-24T06:40:00+00:00",
        "delivery_slot": "2026-08-24:am",
        "new_group_count": 1,
        "new_flag_count": 1,
        "groups": [
            {
                "group_ref": "b" * 24,
                "flag_count": 1,
                "report_count": 1,
                "source_count": 1,
                "reasons": {"inaccurate": 1},
                "expires_at": "2026-08-25T06:40:00+00:00",
            }
        ],
        "notification_transport": (
            "cloud_logging_entries_write_pending_monitoring_configuration"
        ),
        "delivery_semantics": "at_least_once_logging_acceptance",
        "dedupe_field": "digest_id",
        "email_delivery_confirmed": False,
        "contains_private_keys": False,
        "contains_gps": False,
    }


class FakeResponse:
    def __init__(self, status_code):
        self.status_code = status_code


class FakeSession:
    def __init__(self, status_code=200):
        self.status_code = status_code
        self.calls = []

    def post(self, url, *, json, timeout):
        self.calls.append((url, json, timeout))
        return FakeResponse(self.status_code)


class CommunityModerationLoggingTests(unittest.TestCase):
    def test_request_uses_stable_insert_id_and_timestamp(self):
        request = build_ready_log_request(ready_event())
        entry = request["entries"][0]

        self.assertEqual(entry["insertId"], "a" * 64)
        self.assertEqual(entry["timestamp"], "2026-08-24T06:40:00Z")
        self.assertEqual(entry["jsonPayload"]["groups"][0]["group_ref"], "b" * 24)
        self.assertFalse(request["partialSuccess"])

    def test_synchronous_acceptance_returns_matching_receipt(self):
        session = FakeSession()
        receipt = publish_ready_event(ready_event(), session=session)

        self.assertEqual(receipt["status"], "accepted")
        self.assertEqual(receipt["digest_id"], "a" * 64)
        self.assertEqual(len(session.calls), 1)
        self.assertEqual(session.calls[0][0], LOGGING_WRITE_URL)
        self.assertEqual(session.calls[0][2], LOGGING_WRITE_TIMEOUT_SECONDS)

    def test_non_2xx_and_network_errors_fail_without_receipt(self):
        with self.assertRaisesRegex(
            CommunityModerationLoggingError,
            "logging_write_rejected",
        ):
            publish_ready_event(ready_event(), session=FakeSession(503))

        broken = FakeSession()
        broken.post = lambda *args, **kwargs: (_ for _ in ()).throw(
            OSError("network details must not escape")
        )
        with self.assertRaisesRegex(
            CommunityModerationLoggingError,
            "logging_write_unavailable",
        ):
            publish_ready_event(ready_event(), session=broken)

    def test_private_fields_and_wrong_project_fail_closed(self):
        unsafe = ready_event()
        unsafe["groups"][0]["group_id"] = "private-group"
        with self.assertRaisesRegex(
            CommunityModerationLoggingError,
            "logging_ready_privacy_invalid",
        ):
            build_ready_log_request(unsafe)

        with patch("google.auth.default", return_value=(object(), "wrong")):
            with self.assertRaisesRegex(
                CommunityModerationLoggingError,
                "logging_project_mismatch",
            ):
                publish_ready_event(ready_event())

    def test_unknown_top_level_and_nested_fields_fail_closed(self):
        unsafe_top_level = ready_event()
        unsafe_top_level["future_sensitive_field"] = "must-not-pass"
        with self.assertRaisesRegex(
            CommunityModerationLoggingError,
            "logging_ready_event_invalid",
        ):
            build_ready_log_request(unsafe_top_level)

        unsafe_nested = ready_event()
        unsafe_nested["groups"][0]["future_sensitive_field"] = (
            "must-not-pass"
        )
        with self.assertRaisesRegex(
            CommunityModerationLoggingError,
            "logging_ready_privacy_invalid",
        ):
            build_ready_log_request(unsafe_nested)


if __name__ == "__main__":
    unittest.main()
