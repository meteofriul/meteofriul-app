import hashlib
import json
import unittest
from datetime import datetime, timezone

from app.services.community_moderation_digest import (
    DIGEST_PENDING_FIELD,
    DIGEST_STATE_COLLECTION,
    DIGEST_STATE_DOCUMENT,
    DIGEST_STATE_OWNER_MARKER_FIELD,
    DIGEST_STATE_RETENTION_SECONDS,
    MAX_ACTIONABLE_GROUPS,
    CommunityModerationDigestError,
    acknowledge_moderation_digest,
    delivery_slot_for_timestamp,
    produce_moderation_digest,
)
from app.weather.timezone_support import get_fvg_timezone


ROME = get_fvg_timezone()
BASE_NOW = datetime(2026, 8, 24, 8, 40, tzinfo=ROME).timestamp()


class FakeSnapshot:
    def __init__(self, payload=None):
        self.payload = payload
        self.exists = payload is not None

    def to_dict(self):
        return dict(self.payload or {})


class FakeDocument:
    def __init__(self, collection, document_id):
        self.collection = collection
        self.document_id = document_id

    def get(self, transaction=None):
        return FakeSnapshot(self.collection.records.get(self.document_id))

    def set(self, payload, merge=False):
        current = dict(self.collection.records.get(self.document_id) or {})
        self.collection.records[self.document_id] = (
            {**current, **payload} if merge else dict(payload)
        )


class FakeQuery:
    def __init__(self, collection, filters=None, limit_count=None):
        self.collection = collection
        self.filters = list(filters or [])
        self.limit_count = limit_count

    def where(self, *, filter):
        return FakeQuery(
            self.collection,
            [
                *self.filters,
                (filter.field_path, filter.op_string, filter.value),
            ],
            self.limit_count,
        )

    def limit(self, count):
        return FakeQuery(self.collection, self.filters, int(count))

    def stream(self, transaction=None):
        rows = []
        for payload in self.collection.records.values():
            accepted = True
            for field, operator, expected in self.filters:
                value = payload.get(field)
                if operator == ">":
                    accepted = value > expected
                elif operator == "==":
                    accepted = value == expected
                else:
                    raise AssertionError(f"unsupported operator {operator}")
                if not accepted:
                    break
            if accepted:
                rows.append(FakeSnapshot(payload))
        return rows[: self.limit_count] if self.limit_count is not None else rows


class FakeCollection:
    def __init__(self):
        self.records = {}

    def document(self, document_id):
        return FakeDocument(self, document_id)

    def where(self, *, filter):
        return FakeQuery(self).where(filter=filter)


class FakeTransaction:
    def set(self, document, payload, merge=False):
        document.set(payload, merge=merge)


class FakeFirestore:
    def __init__(self, project="meteo-friul"):
        self.project = project
        self.collections = {}

    def collection(self, name):
        return self.collections.setdefault(name, FakeCollection())

    def transaction(self):
        return FakeTransaction()


def immediate_transaction(operation):
    return operation


def active_moderation(
    group_id="group-rain:pordenone:1",
    *,
    now=BASE_NOW,
    flaggers=None,
    hidden=False,
):
    selected_flaggers = (
        {"private-flagger": "inaccurate"}
        if flaggers is None
        else flaggers
    )
    return {
        "group_id": group_id,
        "flag_count": len(selected_flaggers),
        "flaggers": dict(selected_flaggers),
        "report_ids": ["report-private-link"],
        "owner_keys": ["private-owner-key"],
        "hidden": hidden,
        # Extra coordinates model a corrupted/legacy private snapshot and must
        # never be copied into state or logs.
        "lat": 46.123456,
        "lon": 13.123456,
        "expires_at_timestamp": datetime.fromtimestamp(
            now + 24 * 60 * 60,
            timezone.utc,
        ),
    }


class CommunityModerationDigestTests(unittest.TestCase):
    def setUp(self):
        self.firestore = FakeFirestore()
        self.firestore.collection("community_report_moderation").records["one"] = (
            active_moderation()
        )

    def produce(self, *, now=BASE_NOW, apply=False, **kwargs):
        return produce_moderation_digest(
            self.firestore,
            now=now,
            apply=apply,
            transactional_decorator=immediate_transaction,
            **kwargs,
        )

    def acknowledge(self, digest_id, *, now=BASE_NOW + 1, **kwargs):
        return acknowledge_moderation_digest(
            self.firestore,
            digest_id=digest_id,
            now=now,
            transactional_decorator=immediate_transaction,
            **kwargs,
        )

    def state(self, document_id=DIGEST_STATE_DOCUMENT):
        return self.firestore.collection(DIGEST_STATE_COLLECTION).records[
            document_id
        ]

    def test_preview_is_sanitized_and_does_not_write_state(self):
        result = self.produce()

        self.assertEqual(result["status"], "ready")
        self.assertTrue(result["should_emit"])
        self.assertFalse(result["applied"])
        self.assertEqual(result["new_group_count"], 1)
        self.assertEqual(result["new_flag_count"], 1)
        self.assertEqual(result["groups"][0]["source_count"], 1)
        self.assertEqual(
            result["groups"][0]["group_ref"],
            hashlib.sha256(
                b"group-rain:pordenone:1"
            ).hexdigest()[:24],
        )
        self.assertNotIn("group_id", result["groups"][0])
        serialized = json.dumps(result, sort_keys=True)
        for private_value in (
            "group-rain:pordenone:1",
            "private-flagger",
            "private-owner-key",
            "report-private-link",
            "46.123456",
            "13.123456",
        ):
            self.assertNotIn(private_value, serialized)
        self.assertEqual(
            self.firestore.collection(DIGEST_STATE_COLLECTION).records,
            {},
        )

    def test_crash_before_log_reuses_pending_with_stable_digest_id(self):
        first = self.produce(apply=True)
        claimed_state = dict(self.state())

        # A retry must not reread a now-corrupt source before returning the
        # already sanitized pending digest.
        self.firestore.collection(
            "community_report_moderation"
        ).records["one"]["flag_count"] = 99
        retry = self.produce(now=BASE_NOW + 10, apply=True)

        self.assertTrue(first["applied"])
        self.assertTrue(first["pending_created"])
        self.assertFalse(retry["applied"])
        self.assertTrue(retry["pending_reused"])
        self.assertTrue(retry["should_emit"])
        self.assertEqual(retry["digest_id"], first["digest_id"])
        self.assertEqual(self.state(), claimed_state)
        self.assertEqual(self.state()["seen"], {})
        self.assertEqual(self.state()["flag_counts"], {})
        self.assertIn(DIGEST_PENDING_FIELD, self.state())

        serialized = json.dumps(self.state(), default=str, sort_keys=True)
        for private_value in (
            "group-rain:pordenone:1",
            "private-flagger",
            "private-owner-key",
            "report-private-link",
            "46.123456",
            "13.123456",
        ):
            self.assertNotIn(private_value, serialized)

    def test_ack_promotes_seen_clears_pending_and_is_idempotent(self):
        pending = self.produce(apply=True)
        result = self.acknowledge(pending["digest_id"])
        acknowledged_state = dict(self.state())
        repeated = self.acknowledge(pending["digest_id"], now=BASE_NOW + 2)

        self.assertTrue(result["acknowledged"])
        self.assertEqual(result["status"], "acknowledged")
        self.assertNotIn(DIGEST_PENDING_FIELD, acknowledged_state)
        self.assertTrue(acknowledged_state["seen"])
        self.assertEqual(acknowledged_state["last_digest_id"], pending["digest_id"])
        self.assertEqual(
            acknowledged_state["last_delivered_slot"],
            pending["delivery_slot"],
        )
        self.assertEqual(repeated["status"], "already_acknowledged")
        self.assertFalse(repeated["acknowledged"])
        self.assertEqual(self.state(), acknowledged_state)

    def test_wrong_ack_id_fails_without_changing_pending(self):
        pending = self.produce(apply=True)
        original = dict(self.state())
        wrong_id = "f" * 64
        self.assertNotEqual(wrong_id, pending["digest_id"])

        with self.assertRaisesRegex(
            CommunityModerationDigestError,
            "digest_ack_id_mismatch",
        ):
            self.acknowledge(wrong_id)

        self.assertEqual(self.state(), original)

    def test_same_slot_is_throttled_and_next_slot_is_ready(self):
        morning = self.produce(apply=True)
        self.acknowledge(morning["digest_id"])
        moderation = self.firestore.collection(
            "community_report_moderation"
        ).records["one"]
        moderation["flaggers"]["second-private-flagger"] = "duplicate"
        moderation["flag_count"] = 2

        same_slot = datetime(2026, 8, 24, 11, 59, tzinfo=ROME).timestamp()
        next_slot = datetime(2026, 8, 24, 12, 0, tzinfo=ROME).timestamp()
        throttled = self.produce(now=same_slot, apply=True)
        ready = self.produce(now=next_slot, apply=True)

        self.assertEqual(throttled["status"], "throttled")
        self.assertEqual(
            throttled["throttle_reason"],
            "delivery_slot_acknowledged",
        )
        self.assertFalse(throttled["applied"])
        self.assertEqual(ready["status"], "ready")
        self.assertEqual(ready["delivery_slot"], "2026-08-24:pm")
        self.assertEqual(ready["new_flag_count"], 1)
        self.assertTrue(ready["applied"])

    def test_slot_uses_rome_local_date_across_midnight_and_dst(self):
        # Rome midnight is 23:00 UTC in winter.
        self.assertEqual(
            delivery_slot_for_timestamp(
                datetime(2026, 12, 31, 22, 59, tzinfo=timezone.utc).timestamp()
            ),
            "2026-12-31:pm",
        )
        self.assertEqual(
            delivery_slot_for_timestamp(
                datetime(2026, 12, 31, 23, 0, tzinfo=timezone.utc).timestamp()
            ),
            "2027-01-01:am",
        )

        # Both sides of the spring-forward transition remain the same local AM
        # slot (01:30 CET then 03:30 CEST).
        self.assertEqual(
            delivery_slot_for_timestamp(
                datetime(2026, 3, 29, 0, 30, tzinfo=timezone.utc).timestamp()
            ),
            "2026-03-29:am",
        )
        self.assertEqual(
            delivery_slot_for_timestamp(
                datetime(2026, 3, 29, 1, 30, tzinfo=timezone.utc).timestamp()
            ),
            "2026-03-29:am",
        )

        # The repeated 02:30 values at fall-back also map to one AM slot.
        for utc_hour in (0, 1):
            self.assertEqual(
                delivery_slot_for_timestamp(
                    datetime(
                        2026,
                        10,
                        25,
                        utc_hour,
                        30,
                        tzinfo=timezone.utc,
                    ).timestamp()
                ),
                "2026-10-25:am",
            )

    def test_isolated_document_and_owner_marker_survive_claim_and_ack(self):
        singleton = {
            "last_digest_id": "preexisting-sanitized-id",
            "seen": {"legacy-ref": "legacy-fingerprint"},
            "flag_counts": {"legacy-ref": 2},
            "expires_at_timestamp": datetime.fromtimestamp(
                BASE_NOW + 100_000,
                timezone.utc,
            ),
        }
        states = self.firestore.collection(DIGEST_STATE_COLLECTION).records
        states[DIGEST_STATE_DOCUMENT] = dict(singleton)

        pending = self.produce(
            apply=True,
            state_document_id="qa-smoke-isolated",
            state_owner_marker="qa-owner-marker",
        )
        acknowledged = self.acknowledge(
            pending["digest_id"],
            state_document_id="qa-smoke-isolated",
            state_owner_marker="qa-owner-marker",
        )

        self.assertTrue(pending["applied"])
        self.assertTrue(acknowledged["acknowledged"])
        self.assertEqual(states[DIGEST_STATE_DOCUMENT], singleton)
        self.assertEqual(
            states["qa-smoke-isolated"][DIGEST_STATE_OWNER_MARKER_FIELD],
            "qa-owner-marker",
        )
        self.assertNotIn(
            DIGEST_PENDING_FIELD,
            states["qa-smoke-isolated"],
        )

    def test_isolated_claim_rejects_existing_state_without_owner_marker(self):
        states = self.firestore.collection(DIGEST_STATE_COLLECTION).records
        states["qa-smoke-isolated"] = {
            "sentinel": "foreign-state",
            "expires_at_timestamp": datetime.fromtimestamp(
                BASE_NOW + 100_000,
                timezone.utc,
            ),
        }

        with self.assertRaisesRegex(
            CommunityModerationDigestError,
            "digest_state_owner_mismatch",
        ):
            self.produce(
                apply=True,
                state_document_id="qa-smoke-isolated",
                state_owner_marker="qa-owner-marker",
            )

        self.assertEqual(states["qa-smoke-isolated"]["sentinel"], "foreign-state")
        self.assertNotIn(
            DIGEST_STATE_OWNER_MARKER_FIELD,
            states["qa-smoke-isolated"],
        )

    def test_isolated_claim_rejects_existing_empty_state(self):
        states = self.firestore.collection(DIGEST_STATE_COLLECTION).records
        states["qa-smoke-isolated"] = {}

        with self.assertRaisesRegex(
            CommunityModerationDigestError,
            "digest_state_owner_mismatch",
        ):
            self.produce(
                apply=True,
                state_document_id="qa-smoke-isolated",
                state_owner_marker="qa-owner-marker",
            )

        self.assertEqual(states["qa-smoke-isolated"], {})

    def test_isolated_ack_rejects_foreign_replacement_without_owner_marker(self):
        states = self.firestore.collection(DIGEST_STATE_COLLECTION).records
        pending = self.produce(
            apply=True,
            state_document_id="qa-smoke-isolated",
            state_owner_marker="qa-owner-marker",
        )
        states["qa-smoke-isolated"] = {
            "sentinel": "foreign-replacement",
            "expires_at_timestamp": datetime.fromtimestamp(
                BASE_NOW + 100_000,
                timezone.utc,
            ),
        }

        with self.assertRaisesRegex(
            CommunityModerationDigestError,
            "digest_state_owner_mismatch",
        ):
            self.acknowledge(
                pending["digest_id"],
                state_document_id="qa-smoke-isolated",
                state_owner_marker="qa-owner-marker",
            )

        self.assertEqual(
            states["qa-smoke-isolated"]["sentinel"],
            "foreign-replacement",
        )
        self.assertNotIn(
            DIGEST_STATE_OWNER_MARKER_FIELD,
            states["qa-smoke-isolated"],
        )

    def test_pending_and_acknowledged_state_have_48_hour_ttl(self):
        pending = self.produce(apply=True)
        self.assertEqual(
            self.state()["expires_at_timestamp"].timestamp(),
            BASE_NOW + DIGEST_STATE_RETENTION_SECONDS,
        )
        ack_now = BASE_NOW + 5
        self.acknowledge(pending["digest_id"], now=ack_now)
        self.assertEqual(
            self.state()["expires_at_timestamp"].timestamp(),
            ack_now + DIGEST_STATE_RETENTION_SECONDS,
        )

    def test_state_without_ttl_fails_closed(self):
        self.firestore.collection(DIGEST_STATE_COLLECTION).records[
            DIGEST_STATE_DOCUMENT
        ] = {"seen": {}, "flag_counts": {}}

        with self.assertRaisesRegex(
            CommunityModerationDigestError,
            "digest_state_expiry_invalid",
        ):
            self.produce(apply=True)

    def test_expired_pending_is_cleared_without_stale_delivery(self):
        self.produce(apply=True)
        after_group_expiry = BASE_NOW + 24 * 60 * 60 + 1

        result = self.produce(now=after_group_expiry, apply=True)

        self.assertEqual(result["status"], "no_new_actionable_flags")
        self.assertFalse(result["should_emit"])
        self.assertNotIn(DIGEST_PENDING_FIELD, self.state())

    def test_delayed_pending_consumes_the_actual_ack_slot(self):
        previous_pm = datetime(
            2026, 8, 23, 20, 40, tzinfo=ROME
        ).timestamp()
        self.firestore.collection(
            "community_report_moderation"
        ).records["one"] = active_moderation(now=previous_pm)
        delayed = self.produce(now=previous_pm, apply=True)

        acknowledged = self.acknowledge(delayed["digest_id"], now=BASE_NOW)
        self.assertEqual(acknowledged["delivery_slot"], "2026-08-24:am")
        self.assertEqual(
            self.state()["last_delivered_slot"],
            "2026-08-24:am",
        )

        moderation = self.firestore.collection(
            "community_report_moderation"
        ).records["one"]
        moderation["flaggers"]["second-private-flagger"] = "duplicate"
        moderation["flag_count"] = 2
        same_am = self.produce(now=BASE_NOW + 60, apply=True)
        self.assertEqual(same_am["status"], "throttled")
        self.assertFalse(same_am["should_emit"])

    def test_hidden_expired_and_empty_groups_are_not_actionable(self):
        records = self.firestore.collection(
            "community_report_moderation"
        ).records
        records["one"]["hidden"] = True
        records["empty"] = active_moderation(
            "group-rain:empty:1",
            flaggers={},
        )
        records["expired"] = {
            **active_moderation("group-rain:expired:2"),
            "expires_at_timestamp": datetime.fromtimestamp(
                BASE_NOW - 1,
                timezone.utc,
            ),
        }

        result = self.produce()

        self.assertEqual(result["status"], "no_new_actionable_flags")
        self.assertEqual(result["groups"], [])

    def test_malformed_private_state_fails_closed_without_claim(self):
        self.firestore.collection(
            "community_report_moderation"
        ).records["one"]["flag_count"] = 2

        with self.assertRaisesRegex(
            CommunityModerationDigestError,
            "moderation_flag_count_mismatch",
        ):
            self.produce(apply=True)

        self.assertEqual(
            self.firestore.collection(DIGEST_STATE_COLLECTION).records,
            {},
        )

    def test_noncanonical_group_id_cannot_leak_in_error(self):
        private_value = "private-owner-key-that-must-not-reach-monitoring"
        self.firestore.collection(
            "community_report_moderation"
        ).records["one"]["group_id"] = private_value

        with self.assertRaisesRegex(
            CommunityModerationDigestError,
            "moderation_group_id_invalid",
        ) as context:
            self.produce(apply=True)

        self.assertNotIn(private_value, str(context.exception))

    def test_wrong_project_and_capacity_fail_closed(self):
        self.firestore.project = "wrong-project"
        with self.assertRaisesRegex(
            CommunityModerationDigestError,
            "firestore_project_mismatch",
        ):
            self.produce(apply=True)

        self.firestore.project = "meteo-friul"
        records = self.firestore.collection(
            "community_report_moderation"
        ).records
        for index in range(MAX_ACTIONABLE_GROUPS + 1):
            records[str(index)] = active_moderation(
                f"group-rain:capacity-{index}:{index + 1}"
            )
        with self.assertRaisesRegex(
            CommunityModerationDigestError,
            "moderation_digest_capacity_exceeded",
        ):
            self.produce(apply=True)


if __name__ == "__main__":
    unittest.main()
