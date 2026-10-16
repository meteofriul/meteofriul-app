import unittest
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from threading import Event, Thread

from app.repositories.official_alerts import (
    OFFICIAL_ALERT_SNAPSHOT_DOCUMENT,
    OFFICIAL_ALERT_SNAPSHOTS_COLLECTION,
    OfficialAlertSnapshotRepository,
)
from app.services.official_alerts import (
    OfficialAlertsStateService,
    official_alert_snapshot_is_usable,
)


def make_payload(*, active=False, fetched_at=None, valid_to="", unavailable=False):
    fetched = fetched_at or datetime.now(timezone.utc)
    alert = {
        "id": "regional-alert",
        "title": "Allerta regionale",
        "level": "gialla",
        "valid_from": fetched.isoformat(),
        "valid_to": valid_to,
        "official_text": "Allerta gialla per temporali.",
    }
    payload = {
        "active": active,
        "count": 1 if active else 0,
        "alerts": [alert] if active else [],
        "source": {"id": "protezione_civile_fvg_alerts"},
        "source_mode": "official_widget",
        "fetched_at": fetched.isoformat(),
        "expires_at": valid_to,
        "cache": {"status": "fresh"},
    }
    if unavailable:
        payload["cache"] = {"status": "unavailable"}
        payload["error"] = "official_alerts_unavailable"
    return payload


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
        return self.storage


class FakeSnapshot:
    def __init__(self, document):
        self._document = document

    @property
    def exists(self):
        return self._document.payload is not None

    def to_dict(self):
        return deepcopy(self._document.payload)


class FakeDocument:
    def __init__(self):
        self.payload = None
        self.get_calls = 0
        self.get_retry = "unset"
        self.get_timeout = None
        self.set_retry = "unset"
        self.set_timeout = None

    def get(self, *, retry="unset", timeout=None):
        self.get_calls += 1
        self.get_retry = retry
        self.get_timeout = timeout
        return FakeSnapshot(self)

    def set(self, payload, *, retry="unset", timeout=None):
        self.payload = deepcopy(payload)
        self.set_retry = retry
        self.set_timeout = timeout


class FakeCollection:
    def __init__(self):
        self.documents = {}

    def document(self, document_id):
        return self.documents.setdefault(document_id, FakeDocument())


class FakeFirestore:
    def __init__(self):
        self.collections = {}

    def collection(self, name):
        return self.collections.setdefault(name, FakeCollection())


class BlockingDocument(FakeDocument):
    def __init__(self):
        super().__init__()
        self.started = Event()
        self.release = Event()

    def get(self, *, retry="unset", timeout=None):
        self.get_calls += 1
        self.get_retry = retry
        self.get_timeout = timeout
        self.started.set()
        self.release.wait(timeout=1)
        return FakeSnapshot(self)


class OfficialAlertsStateTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 8, 11, 15, 0, tzinfo=timezone.utc)

    def test_recent_inactive_snapshot_is_used_without_network(self):
        repository = FakeRepository(
            make_payload(fetched_at=self.now - timedelta(minutes=130))
        )
        loader_calls = []
        service = OfficialAlertsStateService(
            repository=repository,
            loader=lambda **kwargs: loader_calls.append(kwargs),
            now=lambda: self.now,
        )

        payload = service.get()

        self.assertEqual(loader_calls, [])
        self.assertEqual(payload["cache"]["layer"], "persistent")
        self.assertEqual(payload["cache"]["storage"], "firestore")
        self.assertEqual(payload["cache"]["age_seconds"], 130 * 60)

    def test_refresh_reconciles_the_loaded_snapshot_before_persisting(self):
        previous = make_payload(fetched_at=self.now - timedelta(minutes=20))
        repository = FakeRepository(previous)
        observations = {"telegram": {"alerts": ["raw"]}, "arpa_pcr": None}
        reconciler_calls = []
        reconciled = make_payload(
            active=True,
            fetched_at=self.now,
            valid_to=(self.now + timedelta(hours=6)).isoformat(),
        )
        reconciled["source_mode"] = "official_telegram_pdf_verified"

        def reconcile(snapshot, loaded, *, now):
            reconciler_calls.append((snapshot, loaded, now))
            return deepcopy(reconciled)

        service = OfficialAlertsStateService(
            repository=repository,
            loader=lambda **kwargs: deepcopy(observations),
            reconciler=reconcile,
            now=lambda: self.now,
        )

        result = service.refresh()

        self.assertTrue(result.refreshed)
        self.assertEqual(result.payload, reconciled)
        self.assertEqual(repository.saved, [reconciled])
        self.assertEqual(reconciler_calls, [(previous, observations, self.now)])

    def test_unconfirmed_persistent_read_never_authorizes_snapshot_overwrite(self):
        for active, source_mode in (
            (False, "arpa_pcr_mirror"),
            (True, "official_telegram_pdf_verified"),
        ):
            with self.subTest(active=active, source_mode=source_mode):
                repository = FakeRepository(None, storage="unavailable")
                reconciled = make_payload(
                    active=active,
                    fetched_at=self.now,
                    valid_to=(self.now + timedelta(hours=6)).isoformat(),
                )
                reconciled["source_mode"] = source_mode
                service = OfficialAlertsStateService(
                    repository=repository,
                    loader=lambda **kwargs: {"raw": True},
                    reconciler=lambda snapshot, loaded, *, now: deepcopy(reconciled),
                    now=lambda: self.now,
                )

                result = service.refresh()

                self.assertFalse(result.refreshed)
                self.assertEqual(result.stored_in, "unchanged")
                self.assertEqual(repository.saved, [])
                self.assertEqual(
                    result.payload["warning"],
                    "persistent_snapshot_read_unconfirmed",
                )

    def test_expired_inactive_snapshot_is_refreshed_and_saved(self):
        repository = FakeRepository(
            make_payload(fetched_at=self.now - timedelta(minutes=151))
        )
        fresh = make_payload(fetched_at=self.now)
        service = OfficialAlertsStateService(
            repository=repository,
            loader=lambda **kwargs: deepcopy(fresh),
            now=lambda: self.now,
        )

        payload = service.get()

        self.assertEqual(payload, fresh)
        self.assertEqual(repository.saved, [fresh])

    def test_cloud_read_returns_fast_unavailable_without_direct_fetch(self):
        repository = FakeRepository(
            make_payload(fetched_at=self.now - timedelta(minutes=151))
        )
        loader_calls = []
        service = OfficialAlertsStateService(
            repository=repository,
            loader=lambda **kwargs: loader_calls.append(kwargs),
            now=lambda: self.now,
            direct_fetch_on_read=False,
        )

        payload = service.get()

        self.assertEqual(loader_calls, [])
        self.assertEqual(payload["error"], "official_alerts_unavailable")
        self.assertEqual(payload["cache"]["reason"], "persistent_snapshot_unavailable")
        self.assertEqual(payload["cache"]["layer"], "persistent")
        self.assertEqual(payload["cache"]["storage"], "firestore")

    def test_forced_cloud_read_does_not_trigger_upstream_refresh(self):
        repository = FakeRepository()
        loader_calls = []
        service = OfficialAlertsStateService(
            repository=repository,
            loader=lambda **kwargs: loader_calls.append(kwargs) or deepcopy(fresh),
            now=lambda: self.now,
            direct_fetch_on_read=False,
        )

        payload = service.get(force=True)

        self.assertEqual(loader_calls, [])
        self.assertEqual(payload["error"], "official_alerts_unavailable")
        self.assertEqual(payload["cache"]["storage"], "firestore")
        self.assertEqual(repository.saved, [])

    def test_active_snapshot_stays_usable_until_official_expiry(self):
        valid_to = (self.now + timedelta(hours=2)).isoformat()
        payload = make_payload(
            active=True,
            fetched_at=self.now - timedelta(hours=2),
            valid_to=valid_to,
        )

        self.assertTrue(official_alert_snapshot_is_usable(payload, now=self.now))

    def test_refresh_failure_keeps_valid_active_snapshot(self):
        valid_to = (self.now + timedelta(hours=2)).isoformat()
        active = make_payload(
            active=True,
            fetched_at=self.now - timedelta(hours=1),
            valid_to=valid_to,
        )
        repository = FakeRepository(active)
        unavailable = make_payload(
            fetched_at=self.now,
            unavailable=True,
        )
        unavailable["cache"]["upstream_failure"] = {
            "attempts": [
                {
                    "source": "widget",
                    "category": "http",
                    "status_code": 503,
                    "body": "private body",
                }
            ]
        }
        service = OfficialAlertsStateService(
            repository=repository,
            loader=lambda **kwargs: deepcopy(unavailable),
            now=lambda: self.now,
        )

        result = service.refresh()

        self.assertFalse(result.refreshed)
        self.assertTrue(result.payload["active"])
        self.assertEqual(result.payload["cache"]["status"], "stale")
        self.assertEqual(
            result.payload["cache"]["upstream_failure"],
            {
                "attempts": [
                    {"source": "widget", "category": "http", "status_code": 503}
                ]
            },
        )
        self.assertEqual(repository.saved, [])

    def test_stale_loader_response_is_not_saved_as_fresh(self):
        valid_to = (self.now + timedelta(hours=2)).isoformat()
        active = make_payload(
            active=True,
            fetched_at=self.now - timedelta(hours=1),
            valid_to=valid_to,
        )
        repository = FakeRepository(active)
        stale_loader_payload = deepcopy(active)
        stale_loader_payload["cache"] = {"status": "stale"}
        stale_loader_payload["warning"] = "official_alerts_refresh_failed"
        service = OfficialAlertsStateService(
            repository=repository,
            loader=lambda **kwargs: deepcopy(stale_loader_payload),
            now=lambda: self.now,
        )

        result = service.refresh()

        self.assertFalse(result.refreshed)
        self.assertEqual(result.payload["cache"]["status"], "stale")
        self.assertEqual(repository.saved, [])

    def test_refresh_failure_does_not_republish_stale_inactive_snapshot(self):
        repository = FakeRepository(
            make_payload(fetched_at=self.now - timedelta(minutes=25))
        )
        unavailable = make_payload(fetched_at=self.now, unavailable=True)
        service = OfficialAlertsStateService(
            repository=repository,
            loader=lambda **kwargs: deepcopy(unavailable),
            now=lambda: self.now,
        )

        result = service.refresh()

        self.assertFalse(result.refreshed)
        self.assertEqual(result.payload["error"], "official_alerts_unavailable")
        self.assertEqual(repository.saved, [])


class OfficialAlertSnapshotRepositoryTests(unittest.TestCase):
    def test_firestore_round_trip_survives_repository_recreation(self):
        db = FakeFirestore()
        payload = make_payload()
        writer = OfficialAlertSnapshotRepository(
            firestore_provider=lambda: db,
            operation_timeout_seconds=2.5,
        )

        self.assertEqual(writer.save(payload), "firestore")

        reader = OfficialAlertSnapshotRepository(
            firestore_provider=lambda: db,
            operation_timeout_seconds=2.5,
        )
        stored, storage = reader.load()

        self.assertEqual(storage, "firestore")
        self.assertEqual(stored, payload)
        document = db.collection(OFFICIAL_ALERT_SNAPSHOTS_COLLECTION).document(
            OFFICIAL_ALERT_SNAPSHOT_DOCUMENT
        )
        self.assertEqual(document.set_timeout, 2.5)
        self.assertEqual(document.get_timeout, 2.5)
        self.assertIsNone(document.set_retry)
        self.assertIsNone(document.get_retry)

    def test_repeated_loads_reuse_the_short_firestore_result_cache(self):
        db = FakeFirestore()
        document = db.collection(OFFICIAL_ALERT_SNAPSHOTS_COLLECTION).document(
            OFFICIAL_ALERT_SNAPSHOT_DOCUMENT
        )
        document.payload = {"payload": make_payload()}
        now = [100.0]
        repository = OfficialAlertSnapshotRepository(
            firestore_provider=lambda: db,
            read_ttl_seconds=30,
            monotonic=lambda: now[0],
        )

        first, first_storage = repository.load()
        now[0] += 10
        second, second_storage = repository.load()

        self.assertEqual(first, second)
        self.assertEqual(first_storage, "firestore")
        self.assertEqual(second_storage, "firestore")
        self.assertEqual(document.get_calls, 1)

    def test_parallel_load_returns_without_starting_a_second_firestore_read(self):
        db = FakeFirestore()
        collection = db.collection(OFFICIAL_ALERT_SNAPSHOTS_COLLECTION)
        document = BlockingDocument()
        collection.documents[OFFICIAL_ALERT_SNAPSHOT_DOCUMENT] = document
        repository = OfficialAlertSnapshotRepository(firestore_provider=lambda: db)
        first_result = []
        worker = Thread(target=lambda: first_result.append(repository.load()))

        worker.start()
        self.assertTrue(document.started.wait(timeout=1))
        parallel_result = repository.load()
        document.release.set()
        worker.join(timeout=1)

        self.assertFalse(worker.is_alive())
        self.assertEqual(parallel_result, (None, "refreshing"))
        self.assertEqual(document.get_calls, 1)
        self.assertEqual(first_result, [(None, "firestore_empty")])

    def test_memory_copy_is_kept_when_firestore_fails(self):
        repository = OfficialAlertSnapshotRepository(
            firestore_provider=lambda: (_ for _ in ()).throw(RuntimeError("offline"))
        )
        payload = make_payload()

        self.assertEqual(repository.save(payload), "memory")
        stored, storage = repository.load()

        self.assertEqual(storage, "memory")
        self.assertEqual(stored, payload)

if __name__ == "__main__":
    unittest.main()
