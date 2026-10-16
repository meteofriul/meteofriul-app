import unittest
from copy import deepcopy
from datetime import datetime, timedelta, timezone

from app.repositories.push import (
    PUSH_DEVICES_COLLECTION,
    PUSH_LOCAL_NOTICE_OUTBOX_COLLECTION,
    PUSH_LOCAL_NOTICE_OUTBOX_RETENTION_DAYS,
    PUSH_TARGET_FCM_TOKEN,
    PUSH_TARGET_FIREBASE_INSTALLATION_ID,
    PushDeviceRepository,
    hash_push_target,
    local_notice_delivery_id,
)


NOW = datetime(2026, 8, 14, 10, 0, tzinfo=timezone.utc)
DEVICE_ID = "a" * 64
TOKEN = "owner-token"
TOKEN_HASH = hash_push_target(TOKEN)
SIGNATURE = "b" * 64


class FakeSnapshot:
    def __init__(self, payload=None):
        self.payload = deepcopy(payload)
        self.exists = payload is not None

    def to_dict(self):
        return deepcopy(self.payload or {})


class FakeDocument:
    def __init__(self, collection, document_id):
        self.collection = collection
        self.id = document_id

    def get(self, transaction=None, **kwargs):
        return FakeSnapshot(self.collection.records.get(self.id))

    def set(self, payload, merge=False, **kwargs):
        current = self.collection.records.get(self.id, {}) if merge else {}
        self.collection.records[self.id] = {**deepcopy(current), **deepcopy(payload)}


class FakeCollection:
    def __init__(self):
        self.records = {}

    def document(self, document_id):
        return FakeDocument(self, document_id)


class FakeTransaction:
    def __init__(self):
        self.operations = []

    def set(self, document, payload, merge=False):
        self.operations.append((document, deepcopy(payload), merge))

    def commit(self):
        for document, payload, merge in self.operations:
            document.set(payload, merge=merge)

    def rollback(self):
        self.operations = []


class FakeFirestore:
    def __init__(self):
        self.collections = {}

    def collection(self, name):
        return self.collections.setdefault(name, FakeCollection())

    def transaction(self):
        return FakeTransaction()


def transactional(operation):
    def run(transaction, *args, **kwargs):
        try:
            result = operation(transaction, *args, **kwargs)
            transaction.commit()
            return result
        except BaseException:
            transaction.rollback()
            raise

    return run


def active_device(*, weather_notices=True, token=TOKEN):
    return {
        "schema_version": "2.0",
        "device_id": DEVICE_ID,
        "target_kind": PUSH_TARGET_FCM_TOKEN,
        "target_value": token,
        "target_hash": hash_push_target(token),
        "platform": "android",
        "active": True,
        "municipality": {"istat": "093022", "name": "Fontanafredda"},
        "locality": {
            "id": "irdat-5000:DBPRIOR_0411_LOCAL_PUNT.3931",
            "name": "Vigonovo",
        },
        "location_mode": "automatic_gps",
        "location_evidence": {
            "captured_at": NOW,
            "received_at": NOW,
            "accuracy_m": 25.0,
        },
        "preferences": {
            "official_alerts": True,
            "weather_notices": weather_notices,
        },
    }


class LocalNoticeDeliveryOutboxTests(unittest.TestCase):
    def make_repository(self, db):
        return PushDeviceRepository(
            lambda: db,
            transactional_decorator=transactional,
        )

    def seed_device(self, db, payload):
        db.collection(PUSH_DEVICES_COLLECTION).records[DEVICE_ID] = deepcopy(payload)

    def claim(self, repository, **overrides):
        values = {
            "device_id": DEVICE_ID,
            "notice_signature": SIGNATURE,
            "notice_kind": "wind",
            "target_kind": PUSH_TARGET_FCM_TOKEN,
            "target_hash": TOKEN_HASH,
            "expected_municipality_istat": "093022",
            "expected_locality_id": "irdat-5000:DBPRIOR_0411_LOCAL_PUNT.3931",
            "expected_location_mode": "automatic_gps",
            "expected_location_captured_at": NOW,
            "expected_location_received_at": NOW,
            "expected_location_accuracy_m": 25.0,
            "max_location_age_seconds": 30 * 60,
            "now": NOW,
        }
        values.update(overrides)
        return repository.claim_local_notice_delivery(**values)

    def test_claim_rechecks_weather_preference_and_target_transactionally(self):
        for payload, expected_state in (
            (active_device(weather_notices=False), "weather_notices_disabled"),
            (active_device(token="rotated-token"), "device_target_changed"),
            ({**active_device(), "active": False}, "device_inactive"),
        ):
            with self.subTest(expected_state=expected_state):
                db = FakeFirestore()
                self.seed_device(db, payload)
                claim = self.claim(self.make_repository(db))
                self.assertFalse(claim.claimed)
                self.assertEqual(claim.state, expected_state)
                self.assertEqual(
                    db.collections[PUSH_LOCAL_NOTICE_OUTBOX_COLLECTION].records,
                    {},
                )

    def test_play_beta_claim_rejects_legacy_schema_transactionally(self):
        db = FakeFirestore()
        payload = {
            **active_device(),
            "schema_version": "2.0",
            "enrollment_generation": "play-beta-v1",
            "app_check_app_id": "1:123:android:play",
            "app_version": "1.0.0+300011",
        }
        self.seed_device(db, payload)

        claim = self.claim(
            self.make_repository(db),
            expected_enrollment_generation="play-beta-v1",
            expected_app_check_app_id="1:123:android:play",
            expected_app_version="1.0.0+300011",
        )

        self.assertFalse(claim.claimed)
        self.assertEqual(claim.state, "schema_version_changed")
        self.assertEqual(
            db.collections[PUSH_LOCAL_NOTICE_OUTBOX_COLLECTION].records,
            {},
        )

    def test_claim_rejects_location_changed_after_evaluation(self):
        db = FakeFirestore()
        payload = active_device()
        payload["municipality"] = {"istat": "093015", "name": "Claut"}
        payload["locality"] = {
            "id": "irdat-5000:DBPRIOR_0411_LOCAL_PUNT.1283",
            "name": "Cellino",
        }
        self.seed_device(db, payload)

        claim = self.claim(self.make_repository(db))

        self.assertFalse(claim.claimed)
        self.assertEqual(claim.state, "device_location_changed")
        self.assertEqual(
            db.collections[PUSH_LOCAL_NOTICE_OUTBOX_COLLECTION].records,
            {},
        )

    def test_claim_rejects_same_location_when_gps_evidence_was_cleared(self):
        db = FakeFirestore()
        payload = active_device()
        payload["location_evidence"] = None
        self.seed_device(db, payload)

        claim = self.claim(self.make_repository(db))

        self.assertFalse(claim.claimed)
        self.assertEqual(claim.state, "device_location_evidence_changed")

    def test_manual_location_claim_requires_evidence_to_remain_absent(self):
        db = FakeFirestore()
        payload = active_device()
        payload["location_mode"] = "manual_selection"
        payload["location_evidence"] = None
        self.seed_device(db, payload)
        repository = self.make_repository(db)

        claim = self.claim(
            repository,
            expected_location_mode="manual_selection",
            expected_location_captured_at=None,
            expected_location_received_at=None,
            expected_location_accuracy_m=None,
        )

        self.assertTrue(claim.claimed)

    def test_saved_municipality_without_mode_requires_explicit_morning_gate(self):
        db = FakeFirestore()
        payload = active_device()
        payload["location_mode"] = ""
        payload["location_evidence"] = None
        self.seed_device(db, payload)
        repository = self.make_repository(db)

        rejected = self.claim(
            repository,
            expected_location_mode="",
            expected_location_captured_at=None,
            expected_location_received_at=None,
            expected_location_accuracy_m=None,
        )
        accepted = self.claim(
            repository,
            notice_signature="d" * 64,
            expected_location_mode="",
            expected_location_captured_at=None,
            expected_location_received_at=None,
            expected_location_accuracy_m=None,
            allow_saved_municipality_without_mode=True,
        )

        self.assertFalse(rejected.claimed)
        self.assertEqual(rejected.state, "device_location_evidence_changed")
        self.assertTrue(accepted.claimed)

    def test_web_manual_location_claim_accepts_only_the_current_fid(self):
        fid = "c123456789012345678901"
        db = FakeFirestore()
        payload = active_device(token=fid)
        payload.update({
            "platform": "web",
            "target_kind": PUSH_TARGET_FIREBASE_INSTALLATION_ID,
            "location_mode": "manual_selection",
            "location_evidence": None,
        })
        self.seed_device(db, payload)
        repository = self.make_repository(db)

        claim = self.claim(
            repository,
            target_kind=PUSH_TARGET_FIREBASE_INSTALLATION_ID,
            target_hash=hash_push_target(fid),
            expected_location_mode="manual_selection",
            expected_location_captured_at=None,
            expected_location_received_at=None,
            expected_location_accuracy_m=None,
        )

        self.assertTrue(claim.claimed)
        rotated = self.claim(
            repository,
            notice_signature="c" * 64,
            target_kind=PUSH_TARGET_FIREBASE_INSTALLATION_ID,
            target_hash=hash_push_target("d123456789012345678901"),
            expected_location_mode="manual_selection",
            expected_location_captured_at=None,
            expected_location_received_at=None,
            expected_location_accuracy_m=None,
        )
        self.assertFalse(rotated.claimed)
        self.assertEqual(rotated.state, "device_target_changed")

    def test_municipality_only_claim_uses_empty_locality_as_cas_identity(self):
        db = FakeFirestore()
        payload = active_device()
        payload["locality"] = None
        self.seed_device(db, payload)
        repository = self.make_repository(db)

        claim = self.claim(repository, expected_locality_id="")

        self.assertTrue(claim.claimed)

    def test_municipality_only_claim_rejects_a_new_locality_after_evaluation(self):
        db = FakeFirestore()
        self.seed_device(db, active_device())
        repository = self.make_repository(db)

        claim = self.claim(repository, expected_locality_id="")

        self.assertFalse(claim.claimed)
        self.assertEqual(claim.state, "device_location_changed")

    def test_sent_delivery_is_deduplicated_and_finish_is_claim_bound(self):
        db = FakeFirestore()
        self.seed_device(db, active_device())
        repository = self.make_repository(db)
        claim = self.claim(repository)
        self.assertTrue(claim.claimed)
        outbox = db.collections[PUSH_LOCAL_NOTICE_OUTBOX_COLLECTION].records[
            claim.delivery_id
        ]
        self.assertEqual(
            outbox["expires_at"],
            NOW + timedelta(days=PUSH_LOCAL_NOTICE_OUTBOX_RETENTION_DAYS),
        )
        self.assertEqual(
            claim.delivery_id,
            local_notice_delivery_id(DEVICE_ID, SIGNATURE),
        )
        self.assertFalse(
            repository.finish_local_notice_delivery(
                delivery_id=claim.delivery_id,
                state="sent",
                now=NOW,
                expected_claim_id="wrong",
                expected_target_kind=PUSH_TARGET_FCM_TOKEN,
                expected_target_hash=TOKEN_HASH,
            )
        )
        self.assertTrue(
            repository.finish_local_notice_delivery(
                delivery_id=claim.delivery_id,
                state="sent",
                now=NOW,
                expected_claim_id=claim.claim_id,
                expected_target_kind=PUSH_TARGET_FCM_TOKEN,
                expected_target_hash=TOKEN_HASH,
            )
        )
        outbox = db.collections[PUSH_LOCAL_NOTICE_OUTBOX_COLLECTION].records[
            claim.delivery_id
        ]
        self.assertEqual(
            outbox["expires_at"],
            NOW + timedelta(days=PUSH_LOCAL_NOTICE_OUTBOX_RETENTION_DAYS),
        )
        duplicate = self.claim(repository)
        self.assertFalse(duplicate.claimed)
        self.assertEqual(duplicate.state, "sent")


if __name__ == "__main__":
    unittest.main()
