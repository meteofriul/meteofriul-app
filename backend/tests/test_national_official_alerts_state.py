import unittest
from copy import deepcopy
from datetime import datetime, timedelta

from app.repositories.national_official_alerts import (
    NATIONAL_OFFICIAL_ALERT_SNAPSHOT_DOCUMENT,
    NATIONAL_OFFICIAL_ALERT_SNAPSHOTS_COLLECTION,
    NationalOfficialAlertSnapshotRepository,
)
from app.repositories.official_alerts import (
    OFFICIAL_ALERT_SNAPSHOTS_COLLECTION,
)
from app.services.dpc_national_source import DpcNationalSourceError
from app.services.national_official_alerts_state import (
    NationalOfficialAlertsStateService,
    NationalOfficialAlertsUnavailable,
)

from tests.test_national_official_alerts import NOW, reconciled_snapshot
from tests.test_official_alerts_state import FakeFirestore


class FakeRepository:
    def __init__(self, payload=None, storage="firestore"):
        self.payload = deepcopy(payload)
        self.storage = storage
        self.saved = []

    def load(self):
        return deepcopy(self.payload), self.storage

    def save(self, payload):
        self.payload = deepcopy(payload)
        self.saved.append(deepcopy(payload))
        return "firestore" if self.storage == "firestore_empty" else self.storage


class NationalOfficialAlertsStateTests(unittest.TestCase):
    @staticmethod
    def non_public_cap():
        raise DpcNationalSourceError("dpc_source_cap_not_public")

    def test_repository_uses_a_collection_distinct_from_fvg(self):
        firestore = FakeFirestore()
        repository = NationalOfficialAlertSnapshotRepository(
            firestore_provider=lambda: firestore,
            read_ttl_seconds=0,
        )
        payload = reconciled_snapshot()

        self.assertEqual(repository.load(), (None, "firestore_empty"))
        self.assertEqual(repository.save(payload), "firestore")
        stored = firestore.collections[
            NATIONAL_OFFICIAL_ALERT_SNAPSHOTS_COLLECTION
        ].documents[NATIONAL_OFFICIAL_ALERT_SNAPSHOT_DOCUMENT].payload
        self.assertEqual(stored["payload"], payload)
        self.assertNotEqual(
            NATIONAL_OFFICIAL_ALERT_SNAPSHOTS_COLLECTION,
            OFFICIAL_ALERT_SNAPSHOTS_COLLECTION,
        )
        self.assertNotIn(OFFICIAL_ALERT_SNAPSHOTS_COLLECTION, firestore.collections)

    def test_refresh_persists_newer_verified_revision(self):
        repository = FakeRepository(None, "firestore_empty")
        fetched = reconciled_snapshot()
        service = NationalOfficialAlertsStateService(
            repository=repository,
            loader=lambda: deepcopy(fetched),
            now=lambda: NOW,
        )

        result = service.refresh()

        self.assertTrue(result.refreshed)
        self.assertEqual(result.reason, "stored")
        self.assertEqual(repository.saved, [fetched])

    def test_unconfirmed_read_does_not_authorize_overwrite(self):
        repository = FakeRepository(None, "unavailable")
        service = NationalOfficialAlertsStateService(
            repository=repository,
            loader=lambda: reconciled_snapshot(),
            now=lambda: NOW,
        )

        result = service.refresh()

        self.assertFalse(result.refreshed)
        self.assertEqual(result.reason, "persistent_snapshot_read_unconfirmed")
        self.assertEqual(repository.saved, [])

    def test_same_revision_conflict_and_rollback_fail_closed(self):
        previous = reconciled_snapshot()
        conflict = deepcopy(previous)
        conflict["cap_revision"]["sha256"] = "0" * 64
        repository = FakeRepository(previous)
        service = NationalOfficialAlertsStateService(
            repository=repository,
            loader=lambda: conflict,
            now=lambda: NOW,
        )
        with self.assertRaisesRegex(
            NationalOfficialAlertsUnavailable, "same_revision_conflict"
        ):
            service.refresh()

        rollback = deepcopy(previous)
        rollback["cap_revision"]["sent_at"] = "2026-09-23T14:34:00+02:00"
        repository = FakeRepository(previous)
        result = NationalOfficialAlertsStateService(
            repository=repository,
            loader=lambda: rollback,
            now=lambda: NOW,
        ).refresh()
        self.assertFalse(result.refreshed)
        self.assertEqual(result.reason, "revision_rollback_rejected")
        self.assertEqual(repository.saved, [])

    def test_non_public_cap_holds_only_a_current_persisted_snapshot(self):
        previous = reconciled_snapshot()
        repository = FakeRepository(previous)
        service = NationalOfficialAlertsStateService(
            repository=repository,
            loader=self.non_public_cap,
            now=lambda: NOW,
        )

        result = service.refresh()

        self.assertEqual(result.reason, "source_cap_not_public_held")
        self.assertFalse(result.refreshed)
        self.assertEqual(result.stored_in, "firestore")
        self.assertEqual(result.payload, previous)
        self.assertEqual(repository.saved, [])

    def test_non_public_cap_without_safe_previous_still_fails(self):
        cases = (
            (FakeRepository(None, "firestore_empty"), NOW),
            (FakeRepository(reconciled_snapshot(), "unavailable"), NOW),
            (FakeRepository(reconciled_snapshot()), NOW + timedelta(hours=35)),
            (FakeRepository(reconciled_snapshot()), NOW + timedelta(hours=37)),
        )
        for repository, current in cases:
            with self.subTest(storage=repository.storage, now=current):
                service = NationalOfficialAlertsStateService(
                    repository=repository,
                    loader=self.non_public_cap,
                    now=lambda: current,
                )
                with self.assertRaisesRegex(
                    DpcNationalSourceError, "dpc_source_cap_not_public"
                ):
                    service.refresh()
                self.assertEqual(repository.saved, [])

    def test_other_source_failures_are_not_held(self):
        def broken_source():
            raise DpcNationalSourceError("dpc_source_request_failed")

        service = NationalOfficialAlertsStateService(
            repository=FakeRepository(reconciled_snapshot()),
            loader=broken_source,
            now=lambda: NOW,
        )
        with self.assertRaisesRegex(
            DpcNationalSourceError, "dpc_source_request_failed"
        ):
            service.refresh()

    def test_read_projects_without_fetch_and_preserves_fvg_guard(self):
        repository = FakeRepository(reconciled_snapshot(zone="Friu-A"))
        loader_calls = []
        service = NationalOfficialAlertsStateService(
            repository=repository,
            loader=lambda: loader_calls.append(True),
            now=lambda: NOW,
        )

        response = service.get_for_municipality("093033")

        self.assertEqual(loader_calls, [])
        self.assertEqual(response["zones"], ["FVG-A"])
        self.assertFalse(response["standalone_display_allowed"])
        self.assertEqual(response["cache"]["storage"], "firestore")

    def test_missing_snapshot_is_unavailable_without_network(self):
        loader_calls = []
        service = NationalOfficialAlertsStateService(
            repository=FakeRepository(None, "firestore_empty"),
            loader=lambda: loader_calls.append(True),
            now=lambda: NOW,
        )
        with self.assertRaisesRegex(
            NationalOfficialAlertsUnavailable, "snapshot_unavailable"
        ):
            service.get_for_municipality("041067")
        self.assertEqual(loader_calls, [])


if __name__ == "__main__":
    unittest.main()
