import unittest
from copy import deepcopy
from datetime import datetime, timedelta, timezone

from app.repositories.push import (
    PUSH_DEVICES_COLLECTION,
    PUSH_INACTIVE_DEVICE_RETENTION_DAYS,
    PUSH_OFFICIAL_ALERT_OUTBOX_RETENTION_DAYS,
    PUSH_OUTBOX_COLLECTION,
    PUSH_TARGET_OWNERS_COLLECTION,
    PUSH_TARGET_FCM_TOKEN,
    PUSH_TARGET_FIREBASE_INSTALLATION_ID,
    PushDeviceRepository,
    PushPilotCapacityReached,
    PushRepositoryUnavailable,
    PushTargetAlreadyRegistered,
    hash_installation_id,
    hash_push_target,
    resolve_push_target,
)


NOW = datetime(2026, 8, 14, 10, 0, tzinfo=timezone.utc)
FIRST_ID = hash_installation_id("0123456789abcdef0123456789abcdef")
SECOND_ID = hash_installation_id("fedcba9876543210fedcba9876543210")
WEB_FID = "c123456789012345678901"


class FakeSnapshot:
    def __init__(self, document_id, payload=None):
        self.id = document_id
        self._payload = deepcopy(payload)
        self.exists = payload is not None

    def to_dict(self):
        return deepcopy(self._payload or {})


class FakeDocument:
    def __init__(self, collection, document_id):
        self.collection = collection
        self.id = document_id

    def get(self, transaction=None, **kwargs):
        if transaction is not None and not transaction.active:
            raise RuntimeError("transaction_not_active")
        if self.collection.db.fail_reads:
            raise RuntimeError("read_failed")
        return FakeSnapshot(self.id, self.collection.records.get(self.id))

    def set(self, payload, merge=False, **kwargs):
        if self.collection.db.fail_writes:
            raise RuntimeError("write_failed")
        current = self.collection.records.get(self.id, {}) if merge else {}
        self.collection.records[self.id] = {
            **deepcopy(current),
            **deepcopy(payload),
        }

    def delete(self, **kwargs):
        if self.collection.db.fail_writes:
            raise RuntimeError("write_failed")
        self.collection.records.pop(self.id, None)


class FakeCollection:
    def __init__(self, db):
        self.db = db
        self.records = {}

    def document(self, document_id):
        return FakeDocument(self, document_id)

    def stream(self, **kwargs):
        if self.db.fail_reads:
            raise RuntimeError("read_failed")
        return [
            FakeSnapshot(document_id, payload)
            for document_id, payload in self.records.items()
        ]

    def order_by(self, field):
        if field != "__name__":
            raise ValueError("unsupported_order")
        return FakeQuery(self)


class FakeQuery:
    def __init__(self, collection, *, limit_value=None, after_id=""):
        self.collection = collection
        self.limit_value = limit_value
        self.after_id = after_id

    def limit(self, value):
        return FakeQuery(
            self.collection,
            limit_value=int(value),
            after_id=self.after_id,
        )

    def start_after(self, snapshot):
        return FakeQuery(
            self.collection,
            limit_value=self.limit_value,
            after_id=str(snapshot.id),
        )

    def stream(self, **kwargs):
        if self.collection.db.fail_reads:
            raise RuntimeError("read_failed")
        identifiers = sorted(
            document_id
            for document_id in self.collection.records
            if document_id > self.after_id
        )
        if self.limit_value is not None:
            identifiers = identifiers[: self.limit_value]
        return [
            FakeSnapshot(
                document_id,
                self.collection.records[document_id],
            )
            for document_id in identifiers
        ]


class FakeTransaction:
    def __init__(self, db):
        self.db = db
        self.active = False
        self.operations = []

    def begin(self):
        self.active = True

    def set(self, document, payload, merge=False):
        self.operations.append(("set", document, deepcopy(payload), merge))

    def delete(self, document):
        self.operations.append(("delete", document, None, False))

    def commit(self):
        if self.db.fail_writes:
            raise RuntimeError("write_failed")
        for action, document, payload, merge in self.operations:
            if action == "set":
                document.set(payload, merge=merge)
            else:
                document.delete()
        self.active = False

    def rollback(self):
        self.operations = []
        self.active = False


class FakeFirestore:
    def __init__(self, *, fail_reads=False, fail_writes=False):
        self.collections = {}
        self.fail_reads = fail_reads
        self.fail_writes = fail_writes

    def collection(self, name):
        return self.collections.setdefault(name, FakeCollection(self))

    def transaction(self):
        return FakeTransaction(self)


def fake_transactional(operation):
    def run(transaction, *args, **kwargs):
        transaction.begin()
        try:
            result = operation(transaction, *args, **kwargs)
            transaction.commit()
            return result
        except BaseException:
            transaction.rollback()
            raise

    return run


class PushDeviceRepositoryTests(unittest.TestCase):
    def make_repository(self, db):
        return PushDeviceRepository(
            lambda: db,
            transactional_decorator=fake_transactional,
        )

    def upsert(
        self,
        repository,
        *,
        device_id=FIRST_ID,
        token="token-one-long-enough",
        max_devices=1,
        enrollment_mode="",
        enrollment_generation="",
    ):
        return repository.upsert_device(
            device_id=device_id,
            token=token,
            platform="android",
            app_version="0.1.0-pilot",
            language="it",
            municipality={"istat": "093033", "name": "Pordenone"},
            preferences={"official_alerts": True, "weather_notices": True},
            max_devices=max_devices,
            enrollment_mode=enrollment_mode,
            enrollment_generation=enrollment_generation,
            now=NOW,
        )

    def upsert_web(
        self,
        repository,
        *,
        device_id=FIRST_ID,
        fid=WEB_FID,
    ):
        return repository.upsert_device(
            device_id=device_id,
            target_kind=PUSH_TARGET_FIREBASE_INSTALLATION_ID,
            target_value=fid,
            platform="web",
            app_check_app_id="1:1234567890:web:9876543210fedcba",
            app_version="web-2026.08.15",
            language="it",
            municipality={"istat": "093033", "name": "Pordenone"},
            preferences={"official_alerts": True, "weather_notices": True},
            max_devices=1,
            now=NOW,
        )

    def test_idempotent_upsert_rotates_token_without_consuming_capacity(self):
        db = FakeFirestore()
        repository = self.make_repository(db)

        first = self.upsert(repository)
        second = self.upsert(repository, token="rotated-token-long-enough")

        self.assertTrue(first.created)
        self.assertFalse(second.created)
        stored = db.collections[PUSH_DEVICES_COLLECTION].records[FIRST_ID]
        self.assertEqual(stored["token"], "rotated-token-long-enough")
        self.assertNotIn("0123456789abcdef0123456789abcdef", str(stored))
        capacity = db.collections["push_pilot_state"].records["device_capacity"]
        self.assertEqual(capacity["active_count"], 1)
        self.assertEqual(capacity["active_device_ids"], [FIRST_ID])

    def test_play_beta_has_no_global_registration_cap_and_reads_in_pages(self):
        db = FakeFirestore()
        repository = self.make_repository(db)

        self.upsert(
            repository,
            device_id=FIRST_ID,
            token="play-token-one-long-enough",
            max_devices=1,
            enrollment_mode="play_beta",
            enrollment_generation="play-beta-v1",
        )
        self.upsert(
            repository,
            device_id=SECOND_ID,
            token="play-token-two-long-enough",
            max_devices=1,
            enrollment_mode="play_beta",
            enrollment_generation="play-beta-v1",
        )

        read_result = repository.read_active_devices(
            max_devices=1,
            enrollment_generation="play-beta-v1",
        )
        devices = read_result.devices

        self.assertEqual(
            {device["device_id"] for device in devices},
            {FIRST_ID, SECOND_ID},
        )
        self.assertEqual(read_result.pages_processed, 2)
        self.assertNotIn(
            "device_capacity__play-beta-v1",
            db.collections["push_pilot_state"].records,
        )

    def test_fcm_target_has_one_transactional_active_owner(self):
        db = FakeFirestore()
        repository = self.make_repository(db)
        token = "shared-fcm-token-long-enough"

        self.upsert(repository, token=token, max_devices=2)
        target_hash = hash_push_target(token)
        owner = db.collections[PUSH_TARGET_OWNERS_COLLECTION].records[target_hash]
        self.assertEqual(owner["device_id"], FIRST_ID)

        with self.assertRaises(PushTargetAlreadyRegistered):
            self.upsert(
                repository,
                device_id=SECOND_ID,
                token=token,
                max_devices=2,
            )

        self.assertNotIn(SECOND_ID, db.collections[PUSH_DEVICES_COLLECTION].records)
        self.assertEqual(
            db.collections[PUSH_TARGET_OWNERS_COLLECTION].records[target_hash]["device_id"],
            FIRST_ID,
        )

    def test_fcm_target_repairs_missing_inactive_and_mismatched_stale_owners(self):
        stale_cases = ("missing", "inactive", "mismatched")
        for stale_case in stale_cases:
            with self.subTest(stale_case=stale_case):
                db = FakeFirestore()
                repository = self.make_repository(db)
                token = "repairable-fcm-token-long-enough"
                self.upsert(repository, token=token, max_devices=2)
                stored = db.collections[PUSH_DEVICES_COLLECTION].records
                if stale_case == "missing":
                    stored.pop(FIRST_ID)
                elif stale_case == "inactive":
                    stored[FIRST_ID]["active"] = False
                else:
                    stored[FIRST_ID]["token"] = "different-active-token-long-enough"
                    stored[FIRST_ID]["token_hash"] = hash_push_target(
                        stored[FIRST_ID]["token"]
                    )
                    stored[FIRST_ID]["target_value"] = stored[FIRST_ID]["token"]
                    stored[FIRST_ID]["target_hash"] = stored[FIRST_ID]["token_hash"]

                result = self.upsert(
                    repository,
                    device_id=SECOND_ID,
                    token=token,
                    max_devices=2,
                )

                self.assertTrue(result.created)
                self.assertEqual(
                    db.collections[PUSH_TARGET_OWNERS_COLLECTION]
                    .records[hash_push_target(token)]["device_id"],
                    SECOND_ID,
                )

    def test_fcm_rotation_releases_only_the_index_owned_by_the_same_device(self):
        db = FakeFirestore()
        repository = self.make_repository(db)
        old_token = "old-fcm-token-long-enough"
        new_token = "new-fcm-token-long-enough"
        old_hash = hash_push_target(old_token)
        new_hash = hash_push_target(new_token)

        self.upsert(repository, token=old_token)
        self.upsert(repository, token=new_token)

        owners = db.collections[PUSH_TARGET_OWNERS_COLLECTION].records
        self.assertNotIn(old_hash, owners)
        self.assertEqual(owners[new_hash]["device_id"], FIRST_ID)

        owners[new_hash]["device_id"] = SECOND_ID
        self.upsert(repository, token="third-fcm-token-long-enough")
        self.assertEqual(owners[new_hash]["device_id"], SECOND_ID)

    def test_unregister_and_disable_release_fcm_index_with_owner_cas(self):
        for operation in ("unregister", "disable"):
            with self.subTest(operation=operation):
                db = FakeFirestore()
                repository = self.make_repository(db)
                token = f"{operation}-fcm-token-long-enough"
                target_hash = hash_push_target(token)
                self.upsert(repository, token=token)

                if operation == "unregister":
                    changed = repository.unregister_device(
                        device_id=FIRST_ID,
                        now=NOW + timedelta(minutes=1),
                    )
                else:
                    changed = repository.disable_device(
                        device_id=FIRST_ID,
                        expected_target_kind=PUSH_TARGET_FCM_TOKEN,
                        expected_target_hash=target_hash,
                        reason="fcm_token_invalid",
                        now=NOW + timedelta(minutes=1),
                    )

                self.assertTrue(changed)
                self.assertNotIn(
                    target_hash,
                    db.collections[PUSH_TARGET_OWNERS_COLLECTION].records,
                )

                db = FakeFirestore()
                repository = self.make_repository(db)
                self.upsert(repository, token=token)
                db.collections[PUSH_TARGET_OWNERS_COLLECTION].records[target_hash][
                    "device_id"
                ] = SECOND_ID
                if operation == "unregister":
                    repository.unregister_device(
                        device_id=FIRST_ID,
                        now=NOW + timedelta(minutes=1),
                    )
                else:
                    repository.disable_device(
                        device_id=FIRST_ID,
                        expected_target_kind=PUSH_TARGET_FCM_TOKEN,
                        expected_target_hash=target_hash,
                        reason="fcm_token_invalid",
                        now=NOW + timedelta(minutes=1),
                    )
                self.assertEqual(
                    db.collections[PUSH_TARGET_OWNERS_COLLECTION]
                    .records[target_hash]["device_id"],
                    SECOND_ID,
                )

    def test_play_beta_list_fails_closed_on_preexisting_duplicate_fcm_targets(self):
        db = FakeFirestore()
        repository = self.make_repository(db)
        token = "duplicate-fcm-token-long-enough"
        target_hash = hash_push_target(token)
        for device_id in (FIRST_ID, SECOND_ID):
            db.collection(PUSH_DEVICES_COLLECTION).records[device_id] = {
                "schema_version": "2.1",
                "device_id": device_id,
                "target_kind": PUSH_TARGET_FCM_TOKEN,
                "target_value": token,
                "target_hash": target_hash,
                "token": token,
                "token_hash": target_hash,
                "platform": "android",
                "enrollment_generation": "play-beta-v1",
                "active": True,
            }

        with self.assertRaisesRegex(
            PushRepositoryUnavailable,
            "push_duplicate_fcm_target_detected",
        ):
            repository.list_active_devices(
                max_devices=100,
                enrollment_generation="play-beta-v1",
            )

    def test_upsert_persists_only_canonical_locality_identity(self):
        db = FakeFirestore()
        repository = self.make_repository(db)
        result = repository.upsert_device(
            device_id=FIRST_ID,
            token="token-one-long-enough",
            platform="android",
            app_version="0.1.0-pilot",
            language="it",
            municipality={"istat": "093022", "name": "Fontanafredda"},
            locality={"id": "official-locality-id", "name": "Vigonovo"},
            location_mode="automatic_gps",
            location_evidence={
                "captured_at": NOW - timedelta(seconds=20),
                "received_at": NOW,
                "accuracy_m": 18.0,
            },
            preferences={"official_alerts": True, "weather_notices": True},
            max_devices=1,
            now=NOW,
        )

        self.assertEqual(
            result.device["locality"],
            {"id": "official-locality-id", "name": "Vigonovo"},
        )
        self.assertEqual(result.device["location_evidence"]["accuracy_m"], 18.0)
        self.assertNotIn("lat", result.device["location_evidence"])
        self.assertNotIn("lon", result.device["location_evidence"])

    def test_background_location_update_is_atomic_and_never_persists_coordinates(self):
        db = FakeFirestore()
        repository = self.make_repository(db)
        repository.upsert_device(
            device_id=FIRST_ID,
            token="token-one-long-enough",
            platform="android",
            app_check_app_id="1:123:android:private",
            app_version="3.0.0-private",
            language="it",
            municipality={"istat": "093033", "name": "Pordenone"},
            preferences={"official_alerts": True, "weather_notices": True},
            max_devices=1,
            now=NOW,
        )

        updated = repository.update_android_location_target(
            device_id=FIRST_ID,
            app_check_app_id="1:123:android:private",
            municipality={"istat": "093022", "name": "Fontanafredda"},
            locality={"id": "irdat:vigonovo", "name": "Vigonovo"},
            location_evidence={
                "accuracy_m": 18.0,
                "captured_at": NOW - timedelta(seconds=20),
                "received_at": NOW,
                "trigger": "geofence_exit",
            },
            now=NOW,
        )

        self.assertIsNotNone(updated)
        stored = db.collections[PUSH_DEVICES_COLLECTION].records[FIRST_ID]
        self.assertEqual(stored["municipality"]["name"], "Fontanafredda")
        self.assertEqual(stored["locality"]["name"], "Vigonovo")
        self.assertEqual(stored["location_mode"], "automatic_gps")
        self.assertNotIn("lat", stored)
        self.assertNotIn("lon", stored)
        self.assertNotIn("lat", stored["location_evidence"])
        self.assertNotIn("lon", stored["location_evidence"])

        mismatched = repository.update_android_location_target(
            device_id=FIRST_ID,
            app_check_app_id="1:123:android:different",
            municipality=None,
            locality=None,
            location_evidence=None,
            now=NOW + timedelta(minutes=1),
        )
        self.assertIsNone(mismatched)
        self.assertEqual(
            db.collections[PUSH_DEVICES_COLLECTION].records[FIRST_ID]["locality"]["name"],
            "Vigonovo",
        )

    def test_web_upsert_writes_v2_fid_target_and_clears_legacy_token_fields(self):
        db = FakeFirestore()
        repository = self.make_repository(db)
        db.collection(PUSH_DEVICES_COLLECTION).records[FIRST_ID] = {
            "schema_version": "1.0",
            "device_id": FIRST_ID,
            "token": "stale-android-token",
            "token_hash": hash_push_target("stale-android-token"),
            "platform": "android",
            "active": True,
            "created_at": NOW - timedelta(days=1),
        }

        result = self.upsert_web(repository)

        self.assertFalse(result.created)
        stored = db.collections[PUSH_DEVICES_COLLECTION].records[FIRST_ID]
        self.assertEqual(stored["schema_version"], "2.1")
        self.assertEqual(
            stored["target_kind"],
            PUSH_TARGET_FIREBASE_INSTALLATION_ID,
        )
        self.assertEqual(stored["target_value"], WEB_FID)
        self.assertEqual(stored["target_hash"], hash_push_target(WEB_FID))
        self.assertEqual(stored["token"], "")
        self.assertEqual(stored["token_hash"], "")
        self.assertEqual(stored["platform"], "web")
        self.assertEqual(
            stored["app_check_app_id"],
            "1:1234567890:web:9876543210fedcba",
        )

    def test_play_beta_generation_is_persisted_without_capacity_document(self):
        db = FakeFirestore()
        repository = self.make_repository(db)
        self.upsert(repository)

        migrated = repository.upsert_device(
            device_id=FIRST_ID,
            token="play-beta-token-long-enough",
            platform="android",
            app_check_app_id="1:123:android:play",
            enrollment_mode="play_beta",
            enrollment_generation="play-beta-v1",
            app_version="3.0.0-play-beta",
            language="it",
            municipality={"istat": "093033", "name": "Pordenone"},
            preferences={"official_alerts": True, "weather_notices": True},
            max_devices=100,
            now=NOW + timedelta(minutes=1),
        )

        self.assertFalse(migrated.created)
        stored = db.collections[PUSH_DEVICES_COLLECTION].records[FIRST_ID]
        self.assertEqual(stored["schema_version"], "2.1")
        self.assertEqual(stored["enrollment_mode"], "play_beta")
        self.assertEqual(stored["enrollment_generation"], "play-beta-v1")
        self.assertEqual(stored["app_check_app_id"], "1:123:android:play")
        legacy_capacity = db.collections["push_pilot_state"].records[
            "device_capacity"
        ]
        self.assertEqual(legacy_capacity["active_count"], 0)
        self.assertNotIn(
            "device_capacity__play-beta-v1",
            db.collections["push_pilot_state"].records,
        )

    def test_play_beta_registration_does_not_use_capacity_document(self):
        db = FakeFirestore()
        repository = self.make_repository(db)
        self.upsert(repository)

        beta = repository.upsert_device(
            device_id=SECOND_ID,
            token="second-play-beta-token-long-enough",
            platform="android",
            app_check_app_id="1:123:android:play",
            enrollment_mode="play_beta",
            enrollment_generation="play-beta-v1",
            app_version="3.0.0-play-beta",
            language="it",
            municipality={"istat": "093033", "name": "Pordenone"},
            preferences={"official_alerts": True, "weather_notices": True},
            max_devices=1,
            now=NOW,
        )

        self.assertTrue(beta.created)
        self.assertEqual(
            db.collections["push_pilot_state"].records["device_capacity"][
                "active_device_ids"
            ],
            [FIRST_ID],
        )
        self.assertNotIn(
            "device_capacity__play-beta-v1",
            db.collections["push_pilot_state"].records,
        )

    def test_generation_filtered_listing_and_claim_exclude_legacy_records(self):
        db = FakeFirestore()
        repository = self.make_repository(db)
        db.collection(PUSH_DEVICES_COLLECTION).records.update(
            {
                FIRST_ID: {
                    "schema_version": "2.0",
                    "device_id": FIRST_ID,
                    "active": True,
                    "platform": "android",
                },
                SECOND_ID: {
                    "schema_version": "2.1",
                    "device_id": SECOND_ID,
                    "active": True,
                    "platform": "android",
                    "app_check_app_id": "1:123:android:play",
                    "enrollment_generation": "play-beta-v1",
                    "app_version": "1.0.0+300011",
                    "target_kind": PUSH_TARGET_FCM_TOKEN,
                    "target_value": "play-beta-token-long-enough",
                    "target_hash": hash_push_target(
                        "play-beta-token-long-enough"
                    ),
                    "preferences": {"official_alerts": True},
                },
            }
        )

        devices = repository.list_active_devices(
            max_devices=100,
            enrollment_generation="play-beta-v1",
        )
        self.assertEqual([item["device_id"] for item in devices], [SECOND_ID])

        rejected = repository.claim_official_alert_delivery(
            device_id=SECOND_ID,
            alert_signature="signature",
            alert_id="alert-1",
            target_kind=PUSH_TARGET_FCM_TOKEN,
            target_hash=hash_push_target("play-beta-token-long-enough"),
            expected_enrollment_generation="play-beta-v2",
            expected_app_check_app_id="1:123:android:play",
            expected_app_version="1.0.0+300011",
            now=NOW,
        )
        self.assertFalse(rejected.claimed)
        self.assertEqual(rejected.state, "enrollment_generation_changed")
        self.assertEqual(
            db.collection(PUSH_OUTBOX_COLLECTION).records,
            {},
        )

        wrong_app = repository.claim_official_alert_delivery(
            device_id=SECOND_ID,
            alert_signature="signature",
            alert_id="alert-1",
            target_kind=PUSH_TARGET_FCM_TOKEN,
            target_hash=hash_push_target("play-beta-token-long-enough"),
            expected_enrollment_generation="play-beta-v1",
            expected_app_check_app_id="1:123:android:different",
            expected_app_version="1.0.0+300011",
            now=NOW,
        )
        self.assertFalse(wrong_app.claimed)
        self.assertEqual(wrong_app.state, "app_check_app_changed")
        self.assertEqual(db.collection(PUSH_OUTBOX_COLLECTION).records, {})

        wrong_version = repository.claim_official_alert_delivery(
            device_id=SECOND_ID,
            alert_signature="signature",
            alert_id="alert-1",
            target_kind=PUSH_TARGET_FCM_TOKEN,
            target_hash=hash_push_target("play-beta-token-long-enough"),
            expected_enrollment_generation="play-beta-v1",
            expected_app_check_app_id="1:123:android:play",
            expected_app_version="1.0.0+300010",
            now=NOW,
        )
        self.assertFalse(wrong_version.claimed)
        self.assertEqual(wrong_version.state, "app_version_changed")
        self.assertEqual(db.collection(PUSH_OUTBOX_COLLECTION).records, {})

        db.collection(PUSH_DEVICES_COLLECTION).records[SECOND_ID][
            "schema_version"
        ] = "2.0"
        wrong_schema = repository.claim_official_alert_delivery(
            device_id=SECOND_ID,
            alert_signature="signature",
            alert_id="alert-1",
            target_kind=PUSH_TARGET_FCM_TOKEN,
            target_hash=hash_push_target("play-beta-token-long-enough"),
            expected_enrollment_generation="play-beta-v1",
            expected_app_check_app_id="1:123:android:play",
            expected_app_version="1.0.0+300011",
            now=NOW,
        )
        self.assertFalse(wrong_schema.claimed)
        self.assertEqual(wrong_schema.state, "schema_version_changed")
        self.assertEqual(db.collection(PUSH_OUTBOX_COLLECTION).records, {})

    def test_schema_v1_android_target_remains_readable(self):
        legacy = {
            "schema_version": "1.0",
            "token": "legacy-fcm-token",
            "token_hash": hash_push_target("legacy-fcm-token"),
            "platform": "android",
        }

        self.assertEqual(
            resolve_push_target(legacy),
            (
                PUSH_TARGET_FCM_TOKEN,
                "legacy-fcm-token",
                hash_push_target("legacy-fcm-token"),
            ),
        )

    def test_second_device_is_atomically_rejected_at_private_pilot_cap(self):
        db = FakeFirestore()
        repository = self.make_repository(db)
        self.upsert(repository)

        with self.assertRaises(PushPilotCapacityReached):
            self.upsert(
                repository,
                device_id=SECOND_ID,
                token="token-two-long-enough",
            )

        self.assertNotIn(
            SECOND_ID,
            db.collections[PUSH_DEVICES_COLLECTION].records,
        )

    def test_unregister_frees_capacity_for_replacement_device(self):
        db = FakeFirestore()
        repository = self.make_repository(db)
        self.upsert(repository)

        removed = repository.unregister_device(device_id=FIRST_ID, now=NOW)
        replacement = self.upsert(repository, device_id=SECOND_ID)

        self.assertTrue(removed)
        self.assertTrue(replacement.created)
        self.assertNotIn(FIRST_ID, db.collections[PUSH_DEVICES_COLLECTION].records)

    def test_unregister_remains_a_hard_delete_for_device_with_expiry(self):
        db = FakeFirestore()
        repository = self.make_repository(db)
        self.upsert(repository)
        db.collections[PUSH_DEVICES_COLLECTION].records[FIRST_ID]["expires_at"] = (
            NOW + timedelta(days=PUSH_INACTIVE_DEVICE_RETENTION_DAYS)
        )

        removed = repository.unregister_device(
            device_id=FIRST_ID,
            now=NOW + timedelta(minutes=1),
        )

        self.assertTrue(removed)
        self.assertNotIn(FIRST_ID, db.collections[PUSH_DEVICES_COLLECTION].records)

    def test_unregister_platform_cas_mismatch_preserves_device_and_capacity(self):
        db = FakeFirestore()
        repository = self.make_repository(db)
        self.upsert(repository)

        removed = repository.unregister_device(
            device_id=FIRST_ID,
            expected_platform="web",
            now=NOW + timedelta(minutes=1),
        )

        self.assertFalse(removed)
        self.assertIn(FIRST_ID, db.collections[PUSH_DEVICES_COLLECTION].records)
        capacity = db.collections["push_pilot_state"].records["device_capacity"]
        self.assertEqual(capacity["active_count"], 1)
        self.assertEqual(capacity["active_device_ids"], [FIRST_ID])

    def test_unregister_repairs_orphaned_capacity_entry(self):
        db = FakeFirestore()
        repository = self.make_repository(db)
        db.collection("push_pilot_state").records["device_capacity"] = {
            "active_device_ids": [FIRST_ID],
            "active_count": 1,
        }

        removed = repository.unregister_device(device_id=FIRST_ID, now=NOW)

        self.assertFalse(removed)
        capacity = db.collections["push_pilot_state"].records["device_capacity"]
        self.assertEqual(capacity["active_count"], 0)
        self.assertEqual(capacity["active_device_ids"], [])

    def test_play_beta_unregister_repairs_orphaned_generation_capacity_entry(self):
        db = FakeFirestore()
        repository = self.make_repository(db)
        capacity_id = "device_capacity__play-beta-v1"
        db.collection("push_pilot_state").records[capacity_id] = {
            "enrollment_generation": "play-beta-v1",
            "active_device_ids": [FIRST_ID],
            "active_count": 1,
        }

        removed = repository.unregister_device(
            device_id=FIRST_ID,
            expected_enrollment_generation="play-beta-v1",
            expected_app_check_app_id="1:123:android:play",
            now=NOW,
        )

        self.assertFalse(removed)
        capacity = db.collections["push_pilot_state"].records[capacity_id]
        self.assertEqual(capacity["active_count"], 0)
        self.assertEqual(capacity["active_device_ids"], [])
        self.assertNotIn(
            "device_capacity",
            db.collections["push_pilot_state"].records,
        )

    def test_missing_or_failed_firestore_is_fail_closed(self):
        unavailable = self.make_repository(None)
        with self.assertRaises(PushRepositoryUnavailable):
            self.upsert(unavailable)

        failing = self.make_repository(FakeFirestore(fail_writes=True))
        with self.assertRaises(PushRepositoryUnavailable):
            self.upsert(failing)

    def test_outbox_claim_is_terminal_after_sent(self):
        db = FakeFirestore()
        repository = self.make_repository(db)

        first = repository.claim_official_alert_delivery(
            device_id=FIRST_ID,
            alert_signature="a" * 64,
            alert_id="alert-1",
            now=NOW,
        )
        outbox = db.collections[PUSH_OUTBOX_COLLECTION].records[first.delivery_id]
        self.assertEqual(
            outbox["expires_at"],
            NOW + timedelta(days=PUSH_OFFICIAL_ALERT_OUTBOX_RETENTION_DAYS),
        )
        repository.finish_official_alert_delivery(
            delivery_id=first.delivery_id,
            state="sent",
            now=NOW,
            message_id="message-1",
        )
        outbox = db.collections[PUSH_OUTBOX_COLLECTION].records[first.delivery_id]
        self.assertEqual(
            outbox["expires_at"],
            NOW + timedelta(days=PUSH_OFFICIAL_ALERT_OUTBOX_RETENTION_DAYS),
        )
        duplicate = repository.claim_official_alert_delivery(
            device_id=FIRST_ID,
            alert_signature="a" * 64,
            alert_id="alert-1",
            now=NOW + timedelta(days=1),
        )

        self.assertTrue(first.claimed)
        self.assertFalse(duplicate.claimed)
        self.assertEqual(duplicate.state, "sent")

    def test_transient_failure_retries_after_delay_but_not_immediately(self):
        db = FakeFirestore()
        repository = self.make_repository(db)
        first = repository.claim_official_alert_delivery(
            device_id=FIRST_ID,
            alert_signature="b" * 64,
            alert_id="alert-2",
            now=NOW,
        )
        repository.finish_official_alert_delivery(
            delivery_id=first.delivery_id,
            state="failed_transient",
            now=NOW,
            error_code="fcm_sender_unavailable",
        )

        early = repository.claim_official_alert_delivery(
            device_id=FIRST_ID,
            alert_signature="b" * 64,
            alert_id="alert-2",
            now=NOW + timedelta(minutes=14),
        )
        retry = repository.claim_official_alert_delivery(
            device_id=FIRST_ID,
            alert_signature="b" * 64,
            alert_id="alert-2",
            now=NOW + timedelta(minutes=15),
        )

        self.assertFalse(early.claimed)
        self.assertEqual(early.state, "retry_scheduled")
        self.assertTrue(retry.claimed)
        outbox = db.collections[PUSH_OUTBOX_COLLECTION].records[first.delivery_id]
        self.assertEqual(outbox["attempt_count"], 2)

    def test_transient_failure_stops_after_bounded_attempts(self):
        db = FakeFirestore()
        repository = self.make_repository(db)
        claim = repository.claim_official_alert_delivery(
            device_id=FIRST_ID,
            alert_signature="d" * 64,
            alert_id="alert-4",
            now=NOW,
        )
        current = NOW
        for attempt in range(3):
            repository.finish_official_alert_delivery(
                delivery_id=claim.delivery_id,
                state="failed_transient",
                now=current,
                error_code="fcm_sender_unavailable",
            )
            if attempt < 2:
                current += timedelta(minutes=15)
                claim = repository.claim_official_alert_delivery(
                    device_id=FIRST_ID,
                    alert_signature="d" * 64,
                    alert_id="alert-4",
                    now=current,
                )
                self.assertTrue(claim.claimed)

        exhausted = repository.claim_official_alert_delivery(
            device_id=FIRST_ID,
            alert_signature="d" * 64,
            alert_id="alert-4",
            now=current + timedelta(days=1),
        )
        self.assertFalse(exhausted.claimed)
        self.assertEqual(exhausted.state, "retry_exhausted")

    def test_invalid_token_failure_never_retries(self):
        db = FakeFirestore()
        repository = self.make_repository(db)
        claim = repository.claim_official_alert_delivery(
            device_id=FIRST_ID,
            alert_signature="c" * 64,
            alert_id="alert-3",
            now=NOW,
        )
        repository.finish_official_alert_delivery(
            delivery_id=claim.delivery_id,
            state="failed_invalid_token",
            now=NOW,
            error_code="fcm_token_invalid",
        )

        terminal = repository.claim_official_alert_delivery(
            device_id=FIRST_ID,
            alert_signature="c" * 64,
            alert_id="alert-3",
            now=NOW + timedelta(days=1),
        )

        self.assertFalse(terminal.claimed)
        self.assertEqual(terminal.state, "failed_invalid_token")

    def test_stale_sending_lease_is_reclaimed_but_not_immediately(self):
        db = FakeFirestore()
        repository = self.make_repository(db)
        db.collection(PUSH_DEVICES_COLLECTION).records[FIRST_ID] = {
            "active": True,
            "device_id": FIRST_ID,
            "token_hash": "1" * 64,
            "preferences": {"official_alerts": True, "weather_notices": True},
        }
        first = repository.claim_official_alert_delivery(
            device_id=FIRST_ID,
            alert_signature="e" * 64,
            alert_id="alert-5",
            token_hash="1" * 64,
            now=NOW,
        )

        early = repository.claim_official_alert_delivery(
            device_id=FIRST_ID,
            alert_signature="e" * 64,
            alert_id="alert-5",
            token_hash="1" * 64,
            now=NOW + timedelta(minutes=14),
        )
        reclaimed = repository.claim_official_alert_delivery(
            device_id=FIRST_ID,
            alert_signature="e" * 64,
            alert_id="alert-5",
            token_hash="1" * 64,
            now=NOW + timedelta(minutes=15),
        )

        self.assertTrue(first.claimed)
        self.assertFalse(early.claimed)
        self.assertEqual(early.state, "delivery_in_progress")
        self.assertTrue(reclaimed.claimed)

    def test_stale_finish_after_lease_reclaim_cannot_overwrite_new_claim(self):
        db = FakeFirestore()
        repository = self.make_repository(db)
        target_hash = hash_push_target(WEB_FID)
        db.collection(PUSH_DEVICES_COLLECTION).records[FIRST_ID] = {
            "schema_version": "2.0",
            "active": True,
            "device_id": FIRST_ID,
            "platform": "web",
            "target_kind": PUSH_TARGET_FIREBASE_INSTALLATION_ID,
            "target_value": WEB_FID,
            "target_hash": target_hash,
            "preferences": {"official_alerts": True, "weather_notices": True},
        }
        first = repository.claim_official_alert_delivery(
            device_id=FIRST_ID,
            alert_signature="8" * 64,
            alert_id="alert-lease-cas",
            target_kind=PUSH_TARGET_FIREBASE_INSTALLATION_ID,
            target_hash=target_hash,
            now=NOW,
        )
        reclaimed = repository.claim_official_alert_delivery(
            device_id=FIRST_ID,
            alert_signature="8" * 64,
            alert_id="alert-lease-cas",
            target_kind=PUSH_TARGET_FIREBASE_INSTALLATION_ID,
            target_hash=target_hash,
            now=NOW + timedelta(minutes=15),
        )

        stale_finished = repository.finish_official_alert_delivery(
            delivery_id=first.delivery_id,
            state="failed_transient",
            now=NOW + timedelta(minutes=16),
            error_code="old_sender_finished_late",
            expected_claim_id=first.claim_id,
            expected_target_kind=first.target_kind,
            expected_target_hash=first.target_hash,
        )

        self.assertTrue(first.claimed)
        self.assertTrue(reclaimed.claimed)
        self.assertNotEqual(first.claim_id, reclaimed.claim_id)
        self.assertFalse(stale_finished)
        outbox = db.collections[PUSH_OUTBOX_COLLECTION].records[first.delivery_id]
        self.assertEqual(outbox["state"], "sending")
        self.assertEqual(outbox["claim_id"], reclaimed.claim_id)
        self.assertEqual(outbox["attempt_count"], 2)

    def test_token_rotation_does_not_preempt_an_active_sending_lease(self):
        db = FakeFirestore()
        repository = self.make_repository(db)
        device = {
            "active": True,
            "device_id": FIRST_ID,
            "token_hash": "1" * 64,
            "preferences": {"official_alerts": True, "weather_notices": True},
        }
        db.collection(PUSH_DEVICES_COLLECTION).records[FIRST_ID] = device
        first = repository.claim_official_alert_delivery(
            device_id=FIRST_ID,
            alert_signature="9" * 64,
            alert_id="alert-rotation-race",
            token_hash="1" * 64,
            now=NOW,
        )
        device["token_hash"] = "2" * 64

        early = repository.claim_official_alert_delivery(
            device_id=FIRST_ID,
            alert_signature="9" * 64,
            alert_id="alert-rotation-race",
            token_hash="2" * 64,
            now=NOW + timedelta(minutes=1),
        )
        reclaimed = repository.claim_official_alert_delivery(
            device_id=FIRST_ID,
            alert_signature="9" * 64,
            alert_id="alert-rotation-race",
            token_hash="2" * 64,
            now=NOW + timedelta(minutes=15),
        )

        self.assertTrue(first.claimed)
        self.assertFalse(early.claimed)
        self.assertEqual(early.state, "delivery_in_progress")
        self.assertTrue(reclaimed.claimed)
        outbox = db.collections[PUSH_OUTBOX_COLLECTION].records[first.delivery_id]
        self.assertEqual(outbox["token_hash"], "2" * 64)
        self.assertEqual(outbox["attempt_count"], 2)

    def test_claim_stops_if_official_alerts_were_disabled_after_listing(self):
        db = FakeFirestore()
        repository = self.make_repository(db)
        db.collection(PUSH_DEVICES_COLLECTION).records[FIRST_ID] = {
            "active": True,
            "device_id": FIRST_ID,
            "token_hash": "1" * 64,
            "preferences": {"official_alerts": False, "weather_notices": True},
        }

        claim = repository.claim_official_alert_delivery(
            device_id=FIRST_ID,
            alert_signature="9" * 64,
            alert_id="alert-disabled",
            token_hash="1" * 64,
            now=NOW,
        )

        self.assertFalse(claim.claimed)
        self.assertEqual(claim.state, "official_alerts_disabled")
        self.assertNotIn(
            claim.delivery_id,
            db.collection(PUSH_OUTBOX_COLLECTION).records,
        )

    def test_target_kind_is_part_of_claim_and_disable_cas(self):
        db = FakeFirestore()
        repository = self.make_repository(db)
        target_hash = hash_push_target(WEB_FID)
        db.collection(PUSH_DEVICES_COLLECTION).records[FIRST_ID] = {
            "schema_version": "2.0",
            "active": True,
            "device_id": FIRST_ID,
            "platform": "web",
            "target_kind": PUSH_TARGET_FIREBASE_INSTALLATION_ID,
            "target_value": WEB_FID,
            "target_hash": target_hash,
            "preferences": {"official_alerts": True, "weather_notices": True},
        }

        claim = repository.claim_official_alert_delivery(
            device_id=FIRST_ID,
            alert_signature="7" * 64,
            alert_id="alert-kind-cas",
            target_kind=PUSH_TARGET_FCM_TOKEN,
            target_hash=target_hash,
            now=NOW,
        )
        disabled = repository.disable_device(
            device_id=FIRST_ID,
            expected_target_kind=PUSH_TARGET_FCM_TOKEN,
            expected_target_hash=target_hash,
            reason="stale_invalid_target",
            now=NOW,
        )

        self.assertFalse(claim.claimed)
        self.assertEqual(claim.state, "device_target_changed")
        self.assertFalse(disabled)
        stored = db.collections[PUSH_DEVICES_COLLECTION].records[FIRST_ID]
        self.assertTrue(stored["active"])
        self.assertEqual(stored["target_value"], WEB_FID)

    def test_stale_invalid_web_target_cannot_disable_rotated_fid(self):
        db = FakeFirestore()
        repository = self.make_repository(db)
        old_fid = "c00000000000000000000"
        new_fid = "c99999999999999999999"
        new_hash = hash_push_target(new_fid)
        db.collection(PUSH_DEVICES_COLLECTION).records[FIRST_ID] = {
            "schema_version": "2.0",
            "active": True,
            "device_id": FIRST_ID,
            "platform": "web",
            "target_kind": PUSH_TARGET_FIREBASE_INSTALLATION_ID,
            "target_value": new_fid,
            "target_hash": new_hash,
        }
        db.collection("push_pilot_state").records["device_capacity"] = {
            "active_device_ids": [FIRST_ID],
            "active_count": 1,
        }

        disabled = repository.disable_device(
            device_id=FIRST_ID,
            expected_target_kind=PUSH_TARGET_FIREBASE_INSTALLATION_ID,
            expected_target_hash=hash_push_target(old_fid),
            reason="fcm_token_invalid",
            now=NOW,
        )

        self.assertFalse(disabled)
        stored = db.collections[PUSH_DEVICES_COLLECTION].records[FIRST_ID]
        self.assertTrue(stored["active"])
        self.assertEqual(stored["target_value"], new_fid)
        capacity = db.collections["push_pilot_state"].records["device_capacity"]
        self.assertEqual(capacity["active_count"], 1)

    def test_new_token_can_recover_a_terminal_invalid_token_delivery(self):
        db = FakeFirestore()
        repository = self.make_repository(db)
        db.collection(PUSH_DEVICES_COLLECTION).records[FIRST_ID] = {
            "active": True,
            "device_id": FIRST_ID,
            "token_hash": "1" * 64,
            "preferences": {"official_alerts": True, "weather_notices": True},
        }
        first = repository.claim_official_alert_delivery(
            device_id=FIRST_ID,
            alert_signature="f" * 64,
            alert_id="alert-6",
            token_hash="1" * 64,
            now=NOW,
        )
        repository.finish_official_alert_delivery(
            delivery_id=first.delivery_id,
            state="failed_invalid_token",
            now=NOW,
            error_code="fcm_token_invalid",
        )
        db.collection(PUSH_DEVICES_COLLECTION).records[FIRST_ID]["token_hash"] = "2" * 64

        recovered = repository.claim_official_alert_delivery(
            device_id=FIRST_ID,
            alert_signature="f" * 64,
            alert_id="alert-6",
            token_hash="2" * 64,
            now=NOW + timedelta(minutes=1),
        )

        self.assertTrue(recovered.claimed)
        outbox = db.collections[PUSH_OUTBOX_COLLECTION].records[first.delivery_id]
        self.assertEqual(outbox["attempt_count"], 1)
        self.assertEqual(outbox["token_hash"], "2" * 64)

    def test_stale_invalid_token_result_does_not_disable_a_rotated_token(self):
        db = FakeFirestore()
        repository = self.make_repository(db)
        db.collection(PUSH_DEVICES_COLLECTION).records[FIRST_ID] = {
            "active": True,
            "device_id": FIRST_ID,
            "token": "new-token",
            "token_hash": "2" * 64,
        }

        disabled = repository.disable_device(
            device_id=FIRST_ID,
            expected_token_hash="1" * 64,
            reason="fcm_token_invalid",
            now=NOW,
        )

        self.assertFalse(disabled)
        device = db.collections[PUSH_DEVICES_COLLECTION].records[FIRST_ID]
        self.assertTrue(device["active"])
        self.assertEqual(device["token"], "new-token")
        self.assertNotIn("expires_at", device)

    def test_invalid_fcm_token_sets_inactive_device_expiry_and_clears_target(self):
        db = FakeFirestore()
        repository = self.make_repository(db)
        token = "invalid-fcm-token-long-enough"
        target_hash = hash_push_target(token)
        self.upsert(repository, token=token)
        disabled_at = NOW + timedelta(minutes=1)

        disabled = repository.disable_device(
            device_id=FIRST_ID,
            expected_target_kind=PUSH_TARGET_FCM_TOKEN,
            expected_target_hash=target_hash,
            reason="fcm_token_invalid",
            now=disabled_at,
        )

        self.assertTrue(disabled)
        stored = db.collections[PUSH_DEVICES_COLLECTION].records[FIRST_ID]
        self.assertFalse(stored["active"])
        self.assertEqual(stored["target_value"], "")
        self.assertEqual(stored["token"], "")
        self.assertEqual(stored["target_hash"], target_hash)
        self.assertEqual(stored["token_hash"], target_hash)
        self.assertEqual(stored["disabled_reason"], "fcm_token_invalid")
        self.assertEqual(
            stored["expires_at"],
            disabled_at + timedelta(days=PUSH_INACTIVE_DEVICE_RETENTION_DAYS),
        )

    def test_non_invalid_disable_does_not_create_inactive_device_expiry(self):
        db = FakeFirestore()
        repository = self.make_repository(db)
        token = "manual-disable-token-long-enough"
        self.upsert(repository, token=token)

        disabled = repository.disable_device(
            device_id=FIRST_ID,
            expected_target_kind=PUSH_TARGET_FCM_TOKEN,
            expected_target_hash=hash_push_target(token),
            reason="manual_disable",
            now=NOW + timedelta(minutes=1),
        )

        self.assertTrue(disabled)
        stored = db.collections[PUSH_DEVICES_COLLECTION].records[FIRST_ID]
        self.assertIsNone(stored["expires_at"])

    def test_reenrollment_clears_inactive_device_expiry(self):
        db = FakeFirestore()
        repository = self.make_repository(db)
        old_token = "expired-fcm-token-long-enough"
        self.upsert(repository, token=old_token)
        repository.disable_device(
            device_id=FIRST_ID,
            expected_target_kind=PUSH_TARGET_FCM_TOKEN,
            expected_target_hash=hash_push_target(old_token),
            reason="fcm_token_invalid",
            now=NOW + timedelta(minutes=1),
        )

        result = self.upsert(repository, token="fresh-fcm-token-long-enough")

        self.assertFalse(result.created)
        stored = db.collections[PUSH_DEVICES_COLLECTION].records[FIRST_ID]
        self.assertTrue(stored["active"])
        self.assertIsNone(stored["expires_at"])
        self.assertEqual(stored["disabled_reason"], "")

    def test_configuration_failure_retries_without_becoming_terminal(self):
        db = FakeFirestore()
        repository = self.make_repository(db)
        first = repository.claim_official_alert_delivery(
            device_id=FIRST_ID,
            alert_signature="0" * 64,
            alert_id="alert-7",
            now=NOW,
        )
        repository.finish_official_alert_delivery(
            delivery_id=first.delivery_id,
            state="failed_configuration",
            now=NOW,
            error_code="fcm_configuration_error",
        )

        early = repository.claim_official_alert_delivery(
            device_id=FIRST_ID,
            alert_signature="0" * 64,
            alert_id="alert-7",
            now=NOW + timedelta(minutes=14),
        )
        retry = repository.claim_official_alert_delivery(
            device_id=FIRST_ID,
            alert_signature="0" * 64,
            alert_id="alert-7",
            now=NOW + timedelta(minutes=15),
        )

        self.assertFalse(early.claimed)
        self.assertEqual(early.state, "configuration_retry_scheduled")
        self.assertTrue(retry.claimed)

    def test_active_device_list_rejects_corrupt_capacity_state(self):
        db = FakeFirestore()
        repository = self.make_repository(db)
        db.collection(PUSH_DEVICES_COLLECTION).records[FIRST_ID] = {
            "device_id": FIRST_ID,
            "active": True,
        }
        db.collection(PUSH_DEVICES_COLLECTION).records[SECOND_ID] = {
            "device_id": SECOND_ID,
            "active": True,
        }

        with self.assertRaises(PushRepositoryUnavailable):
            repository.list_active_devices(max_devices=1)


if __name__ == "__main__":
    unittest.main()
