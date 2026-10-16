import unittest
from copy import deepcopy
from datetime import datetime, timedelta, timezone

from app.repositories.local_notice_shadow import (
    LOCAL_NOTICE_SHADOW_COLLECTION,
    LocalNoticeShadowRepository,
    LocalNoticeShadowRepositoryUnavailable,
    build_sanitized_shadow_record,
)
from app.services.location import LocationCatalog
from app.weather.local_notice_shadow import POLICY_VERSION, SCHEMA_VERSION, SOURCE_ID


NOW = datetime(2026, 8, 14, 10, 7, tzinfo=timezone.utc)


def evaluation_fixture():
    return {
        "schema_version": SCHEMA_VERSION,
        "policy_version": POLICY_VERSION,
        "status": "candidates",
        "can_send": False,
        "snapshot": {
            "source": SOURCE_ID,
            "fetched_at": "2026-08-14T12:05:00+02:00",
            "timezone": "Europe/Rome",
            "eligible_slots": 6,
            "raw_snapshot": {"token": "must-not-survive"},
        },
        "validation_errors": [],
        "candidates": [
            {
                "kind": "wind",
                "category": "wind",
                "severity": 2,
                "priority": 60,
                "event_at": "2026-08-14T13:00+02:00",
                "event_end": "2026-08-14T14:00+02:00",
                "municipality": {
                    "latitude": 45.9567,
                    "longitude": 12.6605,
                },
                "threshold": {"wind_gust_kmh": 70},
                "evidence": [
                    {
                        "metric": "wind_gusts_10m",
                        "value": 71,
                        "unit": "km/h",
                        "token": "must-not-survive",
                    }
                ],
                "dedupe": {
                    "event_bucket": "2026-08-14T12",
                    "event_key": "private-redundant-key",
                    "signature": "a" * 64,
                },
                "shadow_only": True,
                "can_notify": False,
                "device_id": "must-not-survive",
            }
        ],
        "observations": [],
        "token": "must-not-survive",
        "installation_id": "must-not-survive",
    }


class FakeDocument:
    def __init__(self, collection, document_id):
        self.collection = collection
        self.document_id = document_id

    def set(self, payload, **kwargs):
        if self.collection.db.fail_writes:
            raise RuntimeError("write_failed")
        self.collection.records[self.document_id] = deepcopy(payload)
        self.collection.calls.append((self.document_id, kwargs))


class FakeCollection:
    def __init__(self, db):
        self.db = db
        self.records = {}
        self.calls = []

    def document(self, document_id):
        return FakeDocument(self, document_id)


class FakeFirestore:
    def __init__(self, *, fail_writes=False):
        self.fail_writes = fail_writes
        self.collections = {}

    def collection(self, name):
        return self.collections.setdefault(name, FakeCollection(self))


def all_keys(value):
    if isinstance(value, dict):
        result = set(value)
        for item in value.values():
            result.update(all_keys(item))
        return result
    if isinstance(value, list):
        result = set()
        for item in value:
            result.update(all_keys(item))
        return result
    return set()


class LocalNoticeShadowRepositoryTests(unittest.TestCase):
    def setUp(self):
        self.municipality = LocationCatalog().match_istat("093033")
        self.assertIsNotNone(self.municipality)

    def test_record_is_allowlisted_and_excludes_device_and_coordinate_data(self):
        record = build_sanitized_shadow_record(
            evaluation=evaluation_fixture(),
            municipality=self.municipality,
            now=NOW,
            retention_days=14,
        )

        forbidden = {
            "token",
            "token_hash",
            "installation_id",
            "device_id",
            "latitude",
            "longitude",
            "event_key",
            "raw_snapshot",
        }
        self.assertTrue(forbidden.isdisjoint(all_keys(record)))
        self.assertNotIn("must-not-survive", str(record))
        self.assertEqual(
            record["municipality"],
            {"istat": "093033", "name": "Pordenone", "province": "PN"},
        )
        self.assertFalse(record["can_send"])
        self.assertFalse(record["candidates"][0]["can_notify"])
        self.assertEqual(record["expires_at"], NOW + timedelta(days=14))

    def test_same_policy_municipality_and_bucket_overwrites_one_document(self):
        db = FakeFirestore()
        repository = LocalNoticeShadowRepository(lambda: db)

        first_id = repository.save_run(
            evaluation=evaluation_fixture(),
            municipality=self.municipality,
            now=NOW,
            retention_days=14,
        )
        second_id = repository.save_run(
            evaluation=evaluation_fixture(),
            municipality=self.municipality,
            now=NOW + timedelta(minutes=7),
            retention_days=14,
        )

        collection = db.collections[LOCAL_NOTICE_SHADOW_COLLECTION]
        self.assertEqual(first_id, second_id)
        self.assertEqual(len(collection.records), 1)
        self.assertEqual(collection.calls[0][1]["retry"], None)
        self.assertEqual(collection.calls[0][1]["timeout"], 5.0)

    def test_next_quarter_hour_creates_a_new_history_document(self):
        db = FakeFirestore()
        repository = LocalNoticeShadowRepository(lambda: db)

        first_id = repository.save_run(
            evaluation=evaluation_fixture(),
            municipality=self.municipality,
            now=NOW,
            retention_days=14,
        )
        second_id = repository.save_run(
            evaluation=evaluation_fixture(),
            municipality=self.municipality,
            now=NOW + timedelta(minutes=8),
            retention_days=14,
        )

        self.assertNotEqual(first_id, second_id)
        self.assertEqual(
            len(db.collections[LOCAL_NOTICE_SHADOW_COLLECTION].records),
            2,
        )

    def test_missing_or_failed_firestore_is_fail_closed(self):
        unavailable = LocalNoticeShadowRepository(lambda: None)
        with self.assertRaises(LocalNoticeShadowRepositoryUnavailable):
            unavailable.save_run(
                evaluation=evaluation_fixture(),
                municipality=self.municipality,
                now=NOW,
                retention_days=14,
            )

        failing = LocalNoticeShadowRepository(
            lambda: FakeFirestore(fail_writes=True)
        )
        with self.assertRaises(LocalNoticeShadowRepositoryUnavailable):
            failing.save_run(
                evaluation=evaluation_fixture(),
                municipality=self.municipality,
                now=NOW,
                retention_days=14,
            )

    def test_retention_is_bounded_even_when_repository_is_called_directly(self):
        for retention_days in (0, 31):
            with self.subTest(retention_days=retention_days):
                with self.assertRaises(ValueError):
                    build_sanitized_shadow_record(
                        evaluation=evaluation_fixture(),
                        municipality=self.municipality,
                        now=NOW,
                        retention_days=retention_days,
                    )


if __name__ == "__main__":
    unittest.main()
