import io
import json
import unittest
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime
from unittest.mock import patch

from app.jobs import emit_community_moderation_digest as digest_job
from app.services.community_moderation_digest import (
    DIGEST_PENDING_FIELD,
    DIGEST_STATE_COLLECTION,
    DIGEST_STATE_DOCUMENT,
)
from app.weather.timezone_support import get_fvg_timezone
from tests.test_community_moderation_digest import (
    BASE_NOW,
    FakeFirestore,
    active_moderation,
    immediate_transaction,
)


class EmitCommunityModerationDigestJobTests(unittest.TestCase):
    def setUp(self):
        self.firestore = FakeFirestore()
        self.published = []
        self.firestore.collection("community_report_moderation").records["one"] = (
            active_moderation()
        )

    def publish(self, event):
        self.published.append(dict(event))
        return {
            "status": "accepted",
            "digest_id": event["digest_id"],
        }

    def run_job(
        self,
        argv,
        *,
        now=BASE_NOW,
        db=None,
        publisher=None,
        clock=None,
    ):
        stdout = io.StringIO()
        stderr = io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            exit_code = digest_job.main(
                argv,
                now=now,
                db=self.firestore if db is None else db,
                transactional_decorator=immediate_transaction,
                ready_event_publisher=publisher or self.publish,
                clock=clock or (lambda: now),
            )
        output = json.loads(stdout.getvalue())
        error = json.loads(stderr.getvalue()) if stderr.getvalue() else None
        return exit_code, output, error

    def state(self):
        return self.firestore.collection(DIGEST_STATE_COLLECTION).records[
            DIGEST_STATE_DOCUMENT
        ]

    def test_default_is_preview_and_cannot_trigger_delivery_event(self):
        exit_code, payload, error = self.run_job([])

        self.assertEqual(exit_code, 0)
        self.assertIsNone(error)
        self.assertEqual(payload["event"], "community_moderation_digest_preview")
        self.assertEqual(payload["severity"], "INFO")
        self.assertFalse(payload["applied"])
        self.assertTrue(payload["should_emit"])
        self.assertEqual(payload["delivery_semantics"], "none")

    def test_apply_flushes_ready_then_acknowledges_once(self):
        first_code, first, first_error = self.run_job(["--apply"])
        second_code, second, second_error = self.run_job(
            ["--apply"],
            now=BASE_NOW + 1,
        )

        self.assertEqual(first_code, 0)
        self.assertIsNone(first_error)
        self.assertEqual(first["event"], "community_moderation_digest_completed")
        self.assertEqual(first["status"], "logging_accepted_and_acknowledged")
        self.assertTrue(first["logging_accepted"])
        self.assertTrue(first["acknowledged"])
        self.assertEqual(len(self.published), 1)
        ready = self.published[0]
        self.assertEqual(ready["event"], "community_moderation_digest_ready")
        self.assertEqual(
            ready["delivery_semantics"],
            "at_least_once_logging_acceptance",
        )
        self.assertEqual(ready["dedupe_field"], "digest_id")
        self.assertIn("groups", ready)
        self.assertNotIn("group_id", ready["groups"][0])
        self.assertNotIn(DIGEST_PENDING_FIELD, self.state())
        self.assertEqual(self.state()["last_digest_id"], ready["digest_id"])

        self.assertEqual(second_code, 0)
        self.assertIsNone(second_error)
        self.assertEqual(second["event"], "community_moderation_digest_completed")
        self.assertEqual(second["status"], "no_new_actionable_flags")
        self.assertFalse(second["applied"])
        self.assertNotIn("groups", second)

    def test_crash_after_log_before_ack_retries_same_digest_id(self):
        with patch.object(
            digest_job,
            "acknowledge_moderation_digest",
            side_effect=RuntimeError("simulated_crash_after_flush"),
        ):
            failed_code, flushed, failure = self.run_job(["--apply"])

        self.assertEqual(failed_code, 1)
        self.assertEqual(flushed["event"], "community_moderation_digest_ack_failed")
        self.assertIsNone(failure)
        self.assertEqual(flushed["status"], "unexpected_ack_failure")
        self.assertEqual(len(self.published), 1)
        ready = self.published[0]
        self.assertIn(DIGEST_PENDING_FIELD, self.state())
        self.assertNotIn("last_digest_id", self.state())

        retry_code, retried, retry_error = self.run_job(
            ["--apply"],
            now=BASE_NOW + 5,
        )
        self.assertEqual(retry_code, 0)
        self.assertIsNone(retry_error)
        self.assertEqual(retried["event"], "community_moderation_digest_completed")
        self.assertEqual(len(self.published), 2)
        self.assertNotIn("pending_reused", self.published[1])
        self.assertNotIn("applied", self.published[1])
        self.assertEqual(self.published[1]["digest_id"], ready["digest_id"])
        self.assertNotIn(DIGEST_PENDING_FIELD, self.state())
        self.assertEqual(self.state()["last_digest_id"], ready["digest_id"])

    def test_logging_acceptance_happens_before_acknowledgement(self):
        observations = []

        def observe_publish(event):
            observations.append(("publish", dict(event)))
            return {"status": "accepted", "digest_id": event["digest_id"]}

        def observe_ack(*args, **kwargs):
            observations.append(("ack", kwargs["digest_id"]))
            return {"status": "acknowledged", "acknowledged": True}

        with patch.object(
            digest_job,
            "acknowledge_moderation_digest",
            side_effect=observe_ack,
        ):
            stdout = io.StringIO()
            with redirect_stdout(stdout):
                exit_code = digest_job.main(
                    ["--apply"],
                    now=BASE_NOW,
                    db=self.firestore,
                    transactional_decorator=immediate_transaction,
                    ready_event_publisher=observe_publish,
                    clock=lambda: BASE_NOW,
                )

        self.assertEqual(exit_code, 0)
        self.assertEqual([item[0] for item in observations], ["publish", "ack"])
        ready = observations[0][1]
        self.assertEqual(ready["event"], "community_moderation_digest_ready")
        self.assertEqual(observations[1][1], ready["digest_id"])

    def test_ack_consumes_slot_at_logging_acceptance_time(self):
        before_noon = datetime(
            2026,
            8,
            24,
            11,
            59,
            tzinfo=get_fvg_timezone(),
        ).timestamp()
        after_noon = datetime(
            2026,
            8,
            24,
            12,
            1,
            tzinfo=get_fvg_timezone(),
        ).timestamp()

        exit_code, payload, error = self.run_job(
            ["--apply"],
            now=before_noon,
            clock=lambda: after_noon,
        )

        self.assertEqual(exit_code, 0)
        self.assertIsNone(error)
        self.assertEqual(payload["delivery_slot"], "2026-08-24:pm")
        self.assertEqual(self.state()["last_delivered_slot"], "2026-08-24:pm")

    def test_logging_rejection_leaves_pending_and_never_acknowledges(self):
        exit_code, payload, error = self.run_job(
            ["--apply"],
            publisher=lambda _event: (_ for _ in ()).throw(
                RuntimeError("transport details")
            ),
        )

        self.assertEqual(exit_code, 1)
        self.assertIsNone(error)
        self.assertEqual(payload["event"], "community_moderation_digest_failed")
        self.assertEqual(payload["status"], "logging_write_unexpected_failure")
        self.assertIn(DIGEST_PENDING_FIELD, self.state())
        self.assertNotIn("last_digest_id", self.state())

    def test_throttled_apply_does_not_repeat_actionable_groups_in_logs(self):
        self.run_job(["--apply"])
        moderation = self.firestore.collection(
            "community_report_moderation"
        ).records["one"]
        moderation["flaggers"]["second-private-flagger"] = "duplicate"
        moderation["flag_count"] = 2
        same_am_slot = datetime(
            2026,
            8,
            24,
            11,
            59,
            tzinfo=get_fvg_timezone(),
        ).timestamp()

        exit_code, payload, error = self.run_job(
            ["--apply"],
            now=same_am_slot,
        )

        self.assertEqual(exit_code, 0)
        self.assertIsNone(error)
        self.assertEqual(payload["event"], "community_moderation_digest_completed")
        self.assertEqual(payload["status"], "throttled")
        self.assertFalse(payload["applied"])
        self.assertEqual(payload["new_group_count"], 1)
        self.assertEqual(payload["new_flag_count"], 1)
        self.assertNotIn("groups", payload)

    def test_storage_and_validation_failures_are_non_sensitive(self):
        stdout = io.StringIO()
        with patch.object(
            digest_job,
            "get_firestore_client",
            return_value=None,
        ), redirect_stdout(stdout):
            storage_code = digest_job.main(["--apply"], now=BASE_NOW)
        storage = json.loads(stdout.getvalue())
        self.firestore.project = "wrong-project"
        wrong_code, wrong, error = self.run_job(["--apply"])

        self.assertEqual(storage_code, 1)
        self.assertEqual(storage["status"], "storage_unavailable")
        self.assertEqual(wrong_code, 1)
        self.assertIsNone(error)
        self.assertEqual(wrong["event"], "community_moderation_digest_failed")
        self.assertEqual(wrong["status"], "firestore_project_mismatch")
        self.assertNotIn("private-owner-key", json.dumps(wrong))


if __name__ == "__main__":
    unittest.main()
