import unittest
from copy import deepcopy
from datetime import datetime, timedelta, timezone

from app.repositories.local_notice_delivery import (
    LOCAL_NOTICE_DELIVERY_RUNS_COLLECTION,
    LocalNoticeDeliveryAuditRepository,
    LocalNoticeDeliveryAuditUnavailable,
    build_local_notice_audit_record,
    local_notice_run_document_id,
)
from app.services.location import LocationCatalog
from app.weather.local_notice_shadow import POLICY_VERSION, SCHEMA_VERSION, SOURCE_ID


NOW = datetime(2026, 8, 14, 10, 7, tzinfo=timezone.utc)


def evaluation():
    return {
        "schema_version": SCHEMA_VERSION,
        "policy_version": POLICY_VERSION,
        "status": "candidates",
        "snapshot": {
            "source": SOURCE_ID,
            "fetched_at": "2026-08-14T12:05:00+02:00",
            "timezone": "Europe/Rome",
            "eligible_slots": 6,
        },
        "validation_errors": [],
        "candidates": [
            {
                "kind": "wind",
                "category": "wind",
                "severity": 2,
                "priority": 60,
                "event_at": "2026-08-14T13:00:00+02:00",
                "event_end": "2026-08-14T14:00:00+02:00",
                "threshold": {"wind_gust_kmh": 70},
                "evidence": [{"metric": "wind", "value": 72}],
                "dedupe": {
                    "event_bucket": "2026-08-14T12",
                    "event_key": "must-not-survive",
                    "signature": "a" * 64,
                },
                "shadow_only": True,
                "can_notify": False,
                "token": "must-not-survive",
                "latitude": 45.9,
            }
        ],
        "observations": [],
        "device_id": "must-not-survive",
    }


class FakeDocument:
    def __init__(self, collection, document_id):
        self.collection = collection
        self.document_id = document_id

    def set(self, payload, **kwargs):
        if self.collection.db.fail:
            raise RuntimeError("write_failed")
        self.collection.records[self.document_id] = deepcopy(payload)


class FakeCollection:
    def __init__(self, db):
        self.db = db
        self.records = {}

    def document(self, document_id):
        return FakeDocument(self, document_id)


class FakeFirestore:
    def __init__(self, *, fail=False):
        self.fail = fail
        self.collections = {}

    def collection(self, name):
        return self.collections.setdefault(name, FakeCollection(self))


def all_keys(value):
    if isinstance(value, dict):
        keys = set(value)
        for item in value.values():
            keys.update(all_keys(item))
        return keys
    if isinstance(value, list):
        keys = set()
        for item in value:
            keys.update(all_keys(item))
        return keys
    return set()


class LocalNoticeDeliveryAuditRepositoryTests(unittest.TestCase):
    def setUp(self):
        self.municipality = LocationCatalog().match_istat("093033")
        self.assertIsNotNone(self.municipality)

    def test_record_has_sanitized_evidence_and_delivery_outcome(self):
        record = build_local_notice_audit_record(
            evaluation=evaluation(),
            municipality=self.municipality,
            now=NOW,
            retention_days=14,
            delivery_mode="send",
            delivery_status="sent",
            selected_kind="wind",
        )
        self.assertEqual(record["delivery"], {"status": "sent", "selected_kind": "wind"})
        self.assertTrue(record["can_send"])
        self.assertEqual(record["expires_at"], NOW + timedelta(days=14))
        self.assertTrue(
            {"token", "device_id", "latitude", "event_key"}.isdisjoint(
                all_keys(record)
            )
        )
        self.assertNotIn("must-not-survive", str(record))

    def test_sent_unconfirmed_is_a_sanitized_audit_status(self):
        record = build_local_notice_audit_record(
            evaluation=evaluation(),
            municipality=self.municipality,
            now=NOW,
            retention_days=14,
            delivery_mode="send",
            delivery_status="sent_unconfirmed",
            selected_kind="wind",
            attempt_id="c" * 32,
        )

        self.assertEqual(
            record["delivery"],
            {"status": "sent_unconfirmed", "selected_kind": "wind"},
        )
        self.assertEqual(record["attempt_id"], "c" * 32)
        self.assertTrue(
            {"token", "device_id", "latitude", "event_key"}.isdisjoint(
                all_keys(record)
            )
        )

    def test_quarter_hour_document_is_idempotent_and_firestore_failure_is_fatal(self):
        db = FakeFirestore()
        repository = LocalNoticeDeliveryAuditRepository(lambda: db)
        arguments = {
            "evaluation": evaluation(),
            "municipality": self.municipality,
            "retention_days": 14,
            "delivery_mode": "dry_run",
            "selected_kind": "wind",
        }
        first = repository.save_run(
            **arguments, now=NOW, delivery_status="planned"
        )
        second = repository.save_run(
            **arguments,
            now=NOW + timedelta(minutes=7),
            delivery_status="dry_run",
        )
        self.assertEqual(first, second)
        records = db.collections[LOCAL_NOTICE_DELIVERY_RUNS_COLLECTION].records
        self.assertEqual(len(records), 1)
        self.assertEqual(records[first]["delivery"]["status"], "dry_run")

        failing = LocalNoticeDeliveryAuditRepository(
            lambda: FakeFirestore(fail=True)
        )
        with self.assertRaises(LocalNoticeDeliveryAuditUnavailable):
            failing.save_run(
                **arguments, now=NOW, delivery_status="planned"
            )

    def test_localities_in_the_same_municipality_have_distinct_audit_documents(self):
        municipality_only = local_notice_run_document_id(
            policy_version=POLICY_VERSION,
            istat_code=self.municipality.istat_code,
            bucket=NOW,
        )
        first_locality = local_notice_run_document_id(
            policy_version=POLICY_VERSION,
            istat_code=self.municipality.istat_code,
            bucket=NOW,
            locality_id="irdat:one",
        )
        second_locality = local_notice_run_document_id(
            policy_version=POLICY_VERSION,
            istat_code=self.municipality.istat_code,
            bucket=NOW,
            locality_id="irdat:two",
        )

        self.assertEqual(
            municipality_only,
            local_notice_run_document_id(
                policy_version=POLICY_VERSION,
                istat_code=self.municipality.istat_code,
                bucket=NOW + timedelta(minutes=7),
                locality_id="",
            ),
        )
        self.assertEqual(len({municipality_only, first_locality, second_locality}), 3)

        db = FakeFirestore()
        repository = LocalNoticeDeliveryAuditRepository(lambda: db)
        arguments = {
            "evaluation": evaluation(),
            "municipality": self.municipality,
            "retention_days": 14,
            "delivery_mode": "dry_run",
            "delivery_status": "dry_run",
            "now": NOW,
        }
        first = repository.save_run(**arguments, locality_id="irdat:one")
        second = repository.save_run(**arguments, locality_id="irdat:two")
        self.assertNotEqual(first, second)
        self.assertEqual(
            len(db.collections[LOCAL_NOTICE_DELIVERY_RUNS_COLLECTION].records),
            2,
        )

    def test_dry_run_attempt_cannot_overwrite_a_concurrent_sent_attempt(self):
        db = FakeFirestore()
        repository = LocalNoticeDeliveryAuditRepository(lambda: db)
        arguments = {
            "evaluation": evaluation(),
            "municipality": self.municipality,
            "retention_days": 14,
            "now": NOW,
        }
        sent_id = repository.save_run(
            **arguments,
            delivery_mode="send",
            delivery_status="sent",
            attempt_id="a" * 32,
        )
        dry_run_id = repository.save_run(
            **arguments,
            delivery_mode="dry_run",
            delivery_status="dry_run",
            attempt_id="b" * 32,
        )

        self.assertNotEqual(sent_id, dry_run_id)
        records = db.collections[LOCAL_NOTICE_DELIVERY_RUNS_COLLECTION].records
        self.assertEqual(records[sent_id]["delivery"]["status"], "sent")
        self.assertEqual(records[sent_id]["attempt_id"], "a" * 32)
        self.assertEqual(records[dry_run_id]["delivery"]["status"], "dry_run")


if __name__ == "__main__":
    unittest.main()
