"""Offline integration tests for contract-v1 publication over SQLite."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import tempfile
import threading
import unittest

from local_pipeline.contract_publisher import (
    ContractPublicationVerificationError,
    ContractV1Publisher,
    ImmutableContractConflict,
    InvalidContractPublication,
    LatestCasExhausted,
    StaleContractRun,
)
from local_pipeline.contract_v1 import (
    CAMS_POLLEN_PROVIDER,
    CAMS_PROVIDER,
    CAMS_VARIABLE_IDS,
    ICON_PROVIDER,
    build_cams_pollen_payload,
    build_cams_payload,
    build_icon_condition,
    build_icon_payload,
    build_run_manifest,
    canonical_json_bytes,
    canonical_run_id,
    load_catalog,
    validate_latest_document,
    validate_run_manifest,
)
from local_pipeline.sqlite_object_store import (
    ObjectHead,
    ObjectNotFound,
    PreconditionFailed,
    SQLiteObjectStore,
    StoredObject,
)


def utc(value: datetime) -> str:
    return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def icon_rows(run: datetime, *, temperature_offset: float = 0.0):
    rows = []
    for lead in range(73):
        valid = run + timedelta(hours=lead)
        rows.append(
            {
                "valid_at": utc(valid),
                "interval_start": None if lead == 0 else utc(valid - timedelta(hours=1)),
                "interval_end": None if lead == 0 else utc(valid),
                "temperature_c": 15.0 + temperature_offset + lead / 20,
                "apparent_temperature_c": 14.5 + temperature_offset + lead / 20,
                "relative_humidity_pct": 70,
                "pressure_msl_hpa": 1012,
                "wind_speed_m_s": 2.0,
                "wind_from_degrees": 90,
                "wind_gust_max_m_s": None if lead == 0 else 4.0,
                "cloud_cover_pct": 30,
                "precipitation_mm": None if lead == 0 else 0.0,
                "liquid_rain_mm": None if lead == 0 else 0.0,
                "snow_water_equivalent_mm": None if lead == 0 else 0.0,
                "condition": build_icon_condition(0),
                "quality_flags": [],
            }
        )
    return rows


def cams_rows(run: datetime):
    return [
        {
            "valid_at": utc(run + timedelta(hours=lead)),
            "values": {
                variable: float((position + lead) % 17)
                for position, variable in enumerate(CAMS_VARIABLE_IDS)
            },
            "quality_flags": {variable: [] for variable in CAMS_VARIABLE_IDS},
        }
        for lead in range(97)
    ]


class MemoryObjectStore:
    """Fast locked test double; one dedicated test still crosses real SQLite."""

    def __init__(self):
        self.objects = {}
        self.generations = {}
        self.lock = threading.RLock()

    @staticmethod
    def _head(key, body, content_type, metadata, generation):
        normalized = {str(name): str(value) for name, value in (metadata or {}).items()}
        sha256 = hashlib.sha256(body).hexdigest()
        etag_input = canonical_json_bytes(
            {
                "body_sha256": sha256,
                "content_type": content_type,
                "generation": generation,
                "metadata": normalized,
            }
        )
        return ObjectHead(
            key=key,
            byte_length=len(body),
            sha256=sha256,
            etag='"memory-' + hashlib.sha256(etag_input).hexdigest() + '"',
            content_type=content_type,
            metadata=normalized,
        )

    def put(self, key, body, *, content_type="application/octet-stream", metadata=None):
        with self.lock:
            if key in self.objects:
                raise PreconditionFailed(key)
            payload = bytes(body)
            head = self._head(key, payload, content_type, metadata, 1)
            self.objects[key] = StoredObject(payload, head)
            self.generations[key] = 1
            return head

    def compare_and_swap(
        self,
        key,
        body,
        *,
        expected_etag,
        content_type="application/octet-stream",
        metadata=None,
    ):
        with self.lock:
            current = self.objects.get(key)
            if (expected_etag is None and current is not None) or (
                expected_etag is not None
                and (current is None or current.etag != expected_etag)
            ):
                raise PreconditionFailed(key)
            generation = self.generations.get(key, 0) + 1
            payload = bytes(body)
            head = self._head(key, payload, content_type, metadata, generation)
            self.objects[key] = StoredObject(payload, head)
            self.generations[key] = generation
            return head

    def get(self, key):
        with self.lock:
            try:
                stored = self.objects[key]
            except KeyError as error:
                raise ObjectNotFound(key) from error
            return StoredObject(stored.body, stored.head)

    def head(self, key):
        return self.get(key).head

    def exists(self, key):
        with self.lock:
            return key in self.objects

    def list_keys(self, prefix=""):
        with self.lock:
            return sorted(key for key in self.objects if key.startswith(prefix))


class RecordingStore:
    def __init__(self, inner: SQLiteObjectStore) -> None:
        self.inner = inner
        self.put_keys: list[str] = []
        self.cas_keys: list[str] = []
        self.get_keys: list[str] = []

    def put(self, key, body, **kwargs):
        self.put_keys.append(key)
        return self.inner.put(key, body, **kwargs)

    def compare_and_swap(self, key, body, **kwargs):
        self.cas_keys.append(key)
        return self.inner.compare_and_swap(key, body, **kwargs)

    def get(self, key):
        self.get_keys.append(key)
        return self.inner.get(key)

    def __getattr__(self, name):
        return getattr(self.inner, name)


class PartialPutFailureStore(RecordingStore):
    def __init__(self, inner, source_run_id, fail_on_payload):
        super().__init__(inner)
        self.marker = f"/runs/{source_run_id}/municipalities/"
        self.fail_on_payload = fail_on_payload
        self.attempts = 0

    def put(self, key, body, **kwargs):
        if self.marker in key:
            self.attempts += 1
            if self.attempts == self.fail_on_payload:
                raise OSError("synthetic interrupted municipality upload")
        return super().put(key, body, **kwargs)


class OneShotLatestFailureStore(RecordingStore):
    def __init__(self, inner):
        super().__init__(inner)
        self.failed = False

    def compare_and_swap(self, key, body, **kwargs):
        if key.endswith("/latest.json") and not self.failed:
            self.failed = True
            raise OSError("synthetic crash before latest CAS")
        return super().compare_and_swap(key, body, **kwargs)


class FirstLatestCasBarrierStore(RecordingStore):
    def __init__(self, inner):
        super().__init__(inner)
        self.barrier = threading.Barrier(2, timeout=20)
        self.lock = threading.Lock()
        self.seen_threads: set[int] = set()

    def compare_and_swap(self, key, body, **kwargs):
        thread_id = threading.get_ident()
        wait = False
        if key.endswith("/latest.json"):
            with self.lock:
                if thread_id not in self.seen_threads:
                    self.seen_threads.add(thread_id)
                    wait = True
        if wait:
            self.barrier.wait()
        return super().compare_and_swap(key, body, **kwargs)


class AlwaysFamilyLatestPreconditionStore(RecordingStore):
    def compare_and_swap(self, key, body, **kwargs):
        if key == "weather/v1/families/cams/latest.json":
            self.cas_keys.append(key)
            raise PreconditionFailed(key)
        return super().compare_and_swap(key, body, **kwargs)


class PostFamilyLatestCasFailureStore(RecordingStore):
    def __init__(self, inner):
        super().__init__(inner)
        self.failed = False

    def compare_and_swap(self, key, body, **kwargs):
        head = super().compare_and_swap(key, body, **kwargs)
        if key == "weather/v1/families/cams/latest.json" and not self.failed:
            self.failed = True
            raise OSError("synthetic lost response after CAMS family CAS")
        return head


class PauseFamilyLatestCasStore(RecordingStore):
    """Pause one family-pointer CAS immediately before or after it is applied."""

    # The other thread validates up to three complete 215-town CAMS releases.
    # This bounds test synchronization, not a production retry or network timeout.
    RESUME_TIMEOUT_SECONDS = 120

    def __init__(self, inner, *, after: bool):
        super().__init__(inner)
        self.after = after
        self.reached = threading.Event()
        self.resume = threading.Event()
        self.paused = False
        self.lock = threading.Lock()

    def compare_and_swap(self, key, body, **kwargs):
        pause = False
        if key == "weather/v1/families/cams/latest.json":
            with self.lock:
                if not self.paused:
                    self.paused = True
                    pause = True
        if pause and not self.after:
            self.reached.set()
            if not self.resume.wait(self.RESUME_TIMEOUT_SECONDS):
                raise TimeoutError("timed out before CAMS family CAS")
        head = super().compare_and_swap(key, body, **kwargs)
        if pause and self.after:
            self.reached.set()
            if not self.resume.wait(self.RESUME_TIMEOUT_SECONDS):
                raise TimeoutError("timed out after CAMS family CAS")
        return head


class ContractPublisherTests(unittest.TestCase):
    catalog = None
    bundles = {}

    @classmethod
    def setUpClass(cls):
        cls.catalog = load_catalog()

    @classmethod
    def icon_bundle(cls, run: datetime):
        cache_key = (ICON_PROVIDER, utc(run))
        if cache_key not in cls.bundles:
            run_at = utc(run)
            generated_at = utc(run + timedelta(hours=1))
            rows = icon_rows(run)
            documents = {}
            for index, municipality in enumerate(cls.catalog.municipalities):
                payload = build_icon_payload(
                    catalog=cls.catalog,
                    istat_code=municipality.istat_code,
                    run_at=run_at,
                    generated_at=generated_at,
                    model_point={
                        "lat": municipality.latitude,
                        "lon": municipality.longitude,
                        "distance_km": 0.0,
                        "grid_index": index,
                    },
                    hourly=rows,
                )
                documents[municipality.istat_code] = canonical_json_bytes(payload)
            manifest = build_run_manifest(
                provider=ICON_PROVIDER,
                run_at=run_at,
                generated_at=generated_at,
                catalog=cls.catalog,
                objects=documents,
            )
            cls.bundles[cache_key] = (documents, manifest)
        return cls.bundles[cache_key]

    @classmethod
    def cams_bundle(cls, run: datetime):
        cache_key = (CAMS_PROVIDER, utc(run))
        if cache_key not in cls.bundles:
            run_at = utc(run)
            generated_at = utc(run + timedelta(hours=10))
            rows = cams_rows(run)
            documents = {}
            for index, municipality in enumerate(cls.catalog.municipalities):
                payload = build_cams_payload(
                    catalog=cls.catalog,
                    istat_code=municipality.istat_code,
                    run_at=run_at,
                    generated_at=generated_at,
                    model_point={
                        "lat": municipality.latitude,
                        "lon": municipality.longitude,
                        "distance_km": 0.0,
                        "grid_index": index,
                    },
                    hourly=rows,
                )
                documents[municipality.istat_code] = canonical_json_bytes(payload)
            manifest = build_run_manifest(
                provider=CAMS_PROVIDER,
                run_at=run_at,
                generated_at=generated_at,
                catalog=cls.catalog,
                objects=documents,
            )
            cls.bundles[cache_key] = (documents, manifest)
        return cls.bundles[cache_key]

    @classmethod
    def cams_pollen_bundle(cls, run: datetime):
        cache_key = (CAMS_POLLEN_PROVIDER, utc(run))
        if cache_key not in cls.bundles:
            run_at = utc(run)
            generated_at = utc(run + timedelta(hours=10))
            rows = cams_rows(run)
            documents = {}
            for index, municipality in enumerate(cls.catalog.municipalities):
                payload = build_cams_pollen_payload(
                    catalog=cls.catalog,
                    istat_code=municipality.istat_code,
                    run_at=run_at,
                    generated_at=generated_at,
                    model_point={
                        "lat": municipality.latitude,
                        "lon": municipality.longitude,
                        "distance_km": 0.0,
                        "grid_index": index,
                    },
                    hourly=rows,
                )
                documents[municipality.istat_code] = canonical_json_bytes(payload)
            manifest = build_run_manifest(
                provider=CAMS_POLLEN_PROVIDER,
                run_at=run_at,
                generated_at=generated_at,
                catalog=cls.catalog,
                objects=documents,
            )
            cls.bundles[cache_key] = (documents, manifest)
        return cls.bundles[cache_key]

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="meteofriul-contract-publish-")
        self.store = MemoryObjectStore()
        self.publisher = ContractV1Publisher(self.store, self.catalog)
        self.old = datetime(2026, 9, 3, 0, tzinfo=timezone.utc)
        self.middle = datetime(2026, 9, 3, 6, tzinfo=timezone.utc)
        self.new = datetime(2026, 9, 3, 12, tzinfo=timezone.utc)

    def tearDown(self):
        self.temporary.cleanup()

    def publish(self, run: datetime, publisher=None):
        documents, manifest = self.icon_bundle(run)
        return (publisher or self.publisher).publish_run(
            ICON_PROVIDER,
            documents,
            manifest,
            published_at=utc(run + timedelta(hours=2)),
        )

    def stage_cams_family(self, run: datetime, publisher=None):
        publisher = publisher or self.publisher
        core_documents, core_manifest = self.cams_bundle(run)
        pollen_documents, pollen_manifest = self.cams_pollen_bundle(run)
        return (
            publisher.stage_run(CAMS_PROVIDER, core_documents, core_manifest),
            publisher.stage_run(
                CAMS_POLLEN_PROVIDER,
                pollen_documents,
                pollen_manifest,
            ),
        )

    def replace_cams_family_latest(self, document):
        key = self.publisher.cams_family_latest_key()
        current = self.store.get(key)
        return self.store.compare_and_swap(
            key,
            canonical_json_bytes(document),
            expected_etag=current.etag,
            content_type="application/json",
            metadata=self.publisher._cams_family_latest_metadata(document),
        )

    def test_exact_contract_paths_order_schema_and_idempotence(self):
        documents, manifest = self.icon_bundle(self.old)
        sqlite_store = SQLiteObjectStore(Path(self.temporary.name) / "objects.sqlite3")
        recording = RecordingStore(sqlite_store)
        publisher = ContractV1Publisher(recording, self.catalog)
        result = publisher.publish_run(
            ICON_PROVIDER,
            documents,
            manifest,
            published_at=utc(self.old + timedelta(hours=2)),
        )
        run_id = canonical_run_id(utc(self.old))
        expected_payload_keys = tuple(
            f"weather/v1/icon2i/runs/{run_id}/municipalities/{code}.json"
            for code in self.catalog.istat_codes
        )
        self.assertEqual(expected_payload_keys, result.payload_keys)
        self.assertEqual(list(expected_payload_keys), recording.put_keys[:215])
        self.assertEqual(
            f"weather/v1/icon2i/runs/{run_id}/manifest.json",
            result.manifest_key,
        )
        self.assertEqual(recording.put_keys[-1], result.manifest_key)
        self.assertEqual(recording.cas_keys, ["weather/v1/icon2i/latest.json"])
        self.assertEqual(217, len(sqlite_store.list_keys("weather/v1/icon2i/")))
        self.assertEqual(canonical_json_bytes(manifest), sqlite_store.get(result.manifest_key).body)
        latest = json.loads(sqlite_store.get(result.latest_key).body)
        validate_latest_document(
            latest,
            expected_provider=ICON_PROVIDER,
            catalog=self.catalog,
            run_manifest=manifest,
        )

        latest_head = sqlite_store.head(result.latest_key)
        put_count = len(recording.put_keys)
        repeated = publisher.publish_run(
            ICON_PROVIDER,
            documents,
            manifest,
            published_at=utc(self.old + timedelta(hours=3)),
        )
        self.assertTrue(repeated.idempotent)
        self.assertFalse(repeated.latest_updated)
        self.assertEqual(215, repeated.reused_payload_count)
        self.assertTrue(repeated.manifest_reused)
        self.assertEqual(latest_head, sqlite_store.head(result.latest_key))
        self.assertEqual([result.latest_key], recording.cas_keys)
        self.assertEqual(put_count, len(recording.put_keys))

    def test_icon_publishes_while_all_28_cams_fields_only_stage_immutably(self):
        icon_result = self.publish(self.old)
        cams_documents, cams_manifest = self.cams_bundle(self.old)
        cams_stage = self.publisher.stage_run(
            CAMS_PROVIDER,
            cams_documents,
            cams_manifest,
        )
        self.assertEqual("icon2i", self.publisher.read_latest(ICON_PROVIDER)["provider"])
        self.assertIsNone(self.publisher.read_latest(CAMS_PROVIDER))
        self.assertTrue(icon_result.latest_key.endswith("/icon2i/latest.json"))
        self.assertTrue(
            cams_stage.manifest_key.endswith(
                "/cams_europe/runs/20260903T000000Z/manifest.json"
            )
        )
        sample = json.loads(cams_documents["093033"])
        self.assertEqual(28, len(sample["variables"]))
        self.assertEqual(set(CAMS_VARIABLE_IDS), set(sample["hourly"][0]["values"]))
        validate_run_manifest(
            cams_manifest,
            self.catalog,
            expected_provider=CAMS_PROVIDER,
            object_bodies=cams_documents,
        )

    def test_partial_payload_and_post_manifest_crashes_resume_without_exposure(self):
        documents, manifest = self.icon_bundle(self.old)
        run_id = manifest["source_run_id"]
        failing = PartialPutFailureStore(self.store, run_id, fail_on_payload=8)
        with self.assertRaisesRegex(OSError, "interrupted"):
            ContractV1Publisher(failing, self.catalog).publish_run(
                ICON_PROVIDER,
                documents,
                manifest,
                published_at=utc(self.old + timedelta(hours=2)),
            )
        prefix = f"weather/v1/icon2i/runs/{run_id}/municipalities/"
        self.assertEqual(7, len(self.store.list_keys(prefix)))
        self.assertFalse(self.store.exists(self.publisher.manifest_key(ICON_PROVIDER, run_id)))
        self.assertIsNone(self.publisher.read_latest(ICON_PROVIDER))

        resumed = self.publish(self.old)
        self.assertEqual(7, resumed.reused_payload_count)
        self.assertTrue(resumed.latest_updated)

        new_documents, new_manifest = self.icon_bundle(self.new)
        crash_store = OneShotLatestFailureStore(self.store)
        with self.assertRaisesRegex(OSError, "before latest"):
            ContractV1Publisher(crash_store, self.catalog).publish_run(
                ICON_PROVIDER,
                new_documents,
                new_manifest,
                published_at=utc(self.new + timedelta(hours=2)),
            )
        self.assertEqual(run_id, self.publisher.read_latest(ICON_PROVIDER)["latest"]["source_run_id"])
        self.assertTrue(
            self.store.exists(self.publisher.manifest_key(ICON_PROVIDER, new_manifest["source_run_id"]))
        )
        after_crash = self.publish(self.new)
        self.assertEqual(215, after_crash.reused_payload_count)
        self.assertTrue(after_crash.manifest_reused)
        self.assertEqual(
            new_manifest["source_run_id"],
            self.publisher.read_latest(ICON_PROVIDER)["latest"]["source_run_id"],
        )

    def test_startup_recovery_revalidates_all_payloads_not_only_latest(self):
        result = self.publish(self.old)
        expected = self.publisher.read_latest(ICON_PROVIDER)
        self.assertEqual(expected, self.publisher.read_verified_latest(ICON_PROVIDER))

        # Simulate external database damage. The cheap pointer read remains
        # structurally valid, but startup recovery must refuse the run because
        # one of its 215 municipality bodies is gone.
        with self.store.lock:
            del self.store.objects[result.payload_keys[0]]
            del self.store.generations[result.payload_keys[0]]
        self.assertEqual(expected, self.publisher.read_latest(ICON_PROVIDER))
        with self.assertRaisesRegex(
            ContractPublicationVerificationError, "missing a municipality"
        ):
            self.publisher.read_verified_latest(ICON_PROVIDER)
        documents, manifest = self.icon_bundle(self.old)
        with self.assertRaisesRegex(
            ContractPublicationVerificationError, "missing a municipality"
        ):
            self.publisher.publish_run(
                ICON_PROVIDER,
                documents,
                manifest,
                published_at=utc(self.old + timedelta(hours=3)),
            )

    def test_cheap_latest_reuse_requires_the_exact_verified_etag(self):
        result = self.publish(self.old)
        expected = self.publisher.read_latest(ICON_PROVIDER)
        self.assertEqual(
            expected,
            self.publisher.read_latest_if_etag(
                ICON_PROVIDER,
                result.latest_etag,
            ),
        )
        self.assertIsNone(
            self.publisher.read_latest_if_etag(
                ICON_PROVIDER,
                '"different-generation"',
            )
        )

        # A structurally identical pointer written as a new CAS generation is
        # still a concurrent change and cannot reuse the earlier verification.
        stored = self.store.get(result.latest_key)
        advanced = self.store.compare_and_swap(
            result.latest_key,
            stored.body,
            expected_etag=stored.etag,
            content_type=stored.content_type,
            metadata=stored.metadata,
        )
        self.assertIsNone(
            self.publisher.read_latest_if_etag(
                ICON_PROVIDER,
                result.latest_etag,
            )
        )
        self.assertEqual(
            expected,
            self.publisher.read_latest_if_etag(
                ICON_PROVIDER,
                advanced.etag,
            ),
        )

    def test_verified_latest_snapshot_binds_original_generation_during_pointer_race(self):
        published = self.publish(self.old)
        original_get = self.store.get
        changed = []

        def racing_get(key):
            if key == published.payload_keys[0] and not changed:
                current = original_get(published.latest_key)
                changed.append(self.store.compare_and_swap(
                    published.latest_key, current.body, expected_etag=current.etag,
                    content_type=current.content_type, metadata=current.metadata,
                ))
            return original_get(key)

        self.store.get = racing_get
        snapshot = self.publisher.read_verified_latest_snapshot(ICON_PROVIDER)
        self.assertEqual(snapshot.etag, published.latest_etag)
        self.assertNotEqual(snapshot.etag, changed[0].etag)
        self.assertEqual(snapshot.document['latest']['source_run_id'], snapshot.manifest['source_run_id'])
        self.assertIsNone(self.publisher.read_latest_if_etag(ICON_PROVIDER, snapshot.etag))

    def test_verified_latest_snapshot_rejects_missing_body_and_handles_absence(self):
        self.assertIsNone(self.publisher.read_verified_latest_snapshot(ICON_PROVIDER))
        published = self.publish(self.old)
        snapshot = self.publisher.read_verified_latest_snapshot(ICON_PROVIDER)
        self.assertEqual(snapshot.etag, published.latest_etag)
        self.assertEqual(snapshot.document, self.publisher.read_verified_latest(ICON_PROVIDER))
        with self.store.lock:
            del self.store.objects[published.payload_keys[0]]
        with self.assertRaises(ContractPublicationVerificationError):
            self.publisher.read_verified_latest_snapshot(ICON_PROVIDER)

    def test_changed_payload_or_manifest_for_same_run_conflicts_immutably(self):
        documents, manifest = self.icon_bundle(self.old)
        result = self.publish(self.old)
        latest_before = self.store.get(result.latest_key)
        changed = dict(documents)
        municipality = self.catalog.municipalities[0]
        changed_payload = build_icon_payload(
            catalog=self.catalog,
            istat_code=municipality.istat_code,
            run_at=utc(self.old),
            generated_at=utc(self.old + timedelta(hours=1)),
            model_point={
                "lat": municipality.latitude,
                "lon": municipality.longitude,
                "distance_km": 0.0,
                "grid_index": 0,
            },
            hourly=icon_rows(self.old, temperature_offset=5),
        )
        changed[municipality.istat_code] = canonical_json_bytes(changed_payload)
        changed_manifest = build_run_manifest(
            provider=ICON_PROVIDER,
            run_at=utc(self.old),
            generated_at=utc(self.old + timedelta(hours=1)),
            catalog=self.catalog,
            objects=changed,
        )
        with self.assertRaises(ImmutableContractConflict):
            self.publisher.publish_run(
                ICON_PROVIDER,
                changed,
                changed_manifest,
                published_at=utc(self.old + timedelta(hours=2)),
            )

        conflicting_manifest = build_run_manifest(
            provider=ICON_PROVIDER,
            run_at=utc(self.old),
            generated_at=utc(self.old + timedelta(hours=2)),
            catalog=self.catalog,
            objects=documents,
        )
        with self.assertRaises(ImmutableContractConflict):
            self.publisher.publish_run(
                ICON_PROVIDER,
                documents,
                conflicting_manifest,
                published_at=utc(self.old + timedelta(hours=3)),
            )
        self.assertEqual(latest_before, self.store.get(result.latest_key))

    def test_concurrent_runs_finish_at_newest_and_known_old_run_is_preflight_rejected(self):
        barrier_store = FirstLatestCasBarrierStore(self.store)

        def concurrently_publish(run):
            publisher = ContractV1Publisher(barrier_store, self.catalog)
            try:
                return self.publish(run, publisher)
            except StaleContractRun:
                return "stale"

        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(concurrently_publish, (self.old, self.new)))
        latest = self.publisher.read_latest(ICON_PROVIDER)
        self.assertEqual(canonical_run_id(utc(self.new)), latest["latest"]["source_run_id"])
        self.assertTrue(any(result != "stale" for result in results))

        middle_documents, middle_manifest = self.icon_bundle(self.middle)
        with self.assertRaises(StaleContractRun):
            self.publisher.publish_run(
                ICON_PROVIDER,
                middle_documents,
                middle_manifest,
                published_at=utc(self.middle + timedelta(hours=2)),
            )
        self.assertFalse(
            self.store.exists(
                self.publisher.manifest_key(ICON_PROVIDER, middle_manifest["source_run_id"])
            )
        )

    def test_stage_run_is_invisible_and_idempotent(self):
        recording = RecordingStore(self.store)
        publisher = ContractV1Publisher(recording, self.catalog)
        documents, manifest = self.cams_bundle(self.old)

        stage = publisher.stage_run(CAMS_PROVIDER, documents, manifest)
        self.assertEqual(CAMS_PROVIDER, stage.provider)
        self.assertEqual(manifest["source_run_id"], stage.source_run_id)
        self.assertEqual(215, len(stage.payload_keys))
        self.assertEqual([], recording.cas_keys)
        self.assertFalse(self.store.exists(publisher.latest_key(CAMS_PROVIDER)))
        self.assertFalse(self.store.exists(publisher.cams_family_latest_key()))
        self.assertFalse(stage.idempotent)

        repeated = publisher.stage_run(CAMS_PROVIDER, documents, manifest)
        self.assertTrue(repeated.idempotent)
        self.assertEqual(215, repeated.reused_payload_count)
        self.assertTrue(repeated.manifest_reused)
        self.assertEqual(stage.manifest_etag, repeated.manifest_etag)
        self.assertEqual([], recording.cas_keys)

    def test_cams_family_release_has_one_pointer_and_verified_members(self):
        recording = RecordingStore(self.store)
        publisher = ContractV1Publisher(recording, self.catalog)
        core_stage, pollen_stage = self.stage_cams_family(self.old, publisher)
        recording.put_keys.clear()
        recording.cas_keys.clear()
        recording.get_keys.clear()
        validation_sha256 = "a" * 64

        result = publisher.release_cams_family(
            core_stage,
            pollen_stage,
            validation_sha256=validation_sha256,
            published_at=utc(self.old + timedelta(hours=11)),
        )
        self.assertEqual([result.release_key], recording.put_keys)
        self.assertEqual([publisher.cams_family_latest_key()], recording.cas_keys)
        self.assertFalse(
            any("/municipalities/" in key for key in recording.get_keys),
            "release must trust the already verified stage and avoid re-reading payloads",
        )
        self.assertFalse(self.store.exists(publisher.latest_key(CAMS_PROVIDER)))
        self.assertFalse(self.store.exists(publisher.latest_key(CAMS_POLLEN_PROVIDER)))

        latest = publisher.read_verified_cams_family_latest()
        self.assertEqual(result.source_run_id, latest["latest"]["source_run_id"])
        self.assertEqual(validation_sha256, json.loads(self.store.get(result.release_key).body)["validation_sha256"])
        release = json.loads(self.store.get(result.release_key).body)
        self.assertEqual(
            {"core", "pollen"},
            set(release["components"]),
        )
        self.assertEqual(CAMS_PROVIDER, release["components"]["core"]["provider"])
        self.assertEqual(
            CAMS_POLLEN_PROVIDER,
            release["components"]["pollen"]["provider"],
        )
        self.assertEqual(
            release["components"]["core"]["source_run_id"],
            release["components"]["pollen"]["source_run_id"],
        )

        put_count = len(recording.put_keys)
        cas_count = len(recording.cas_keys)
        repeated = publisher.release_cams_family(
            core_stage,
            pollen_stage,
            validation_sha256=validation_sha256,
            published_at=utc(self.old + timedelta(hours=11)),
        )
        self.assertTrue(repeated.idempotent)
        self.assertTrue(repeated.release_reused)
        self.assertFalse(repeated.latest_updated)
        self.assertEqual(put_count, len(recording.put_keys))
        self.assertEqual(cas_count, len(recording.cas_keys))

    def test_cams_family_rejects_mixed_members_conflict_and_stale_run(self):
        old_core, old_pollen = self.stage_cams_family(self.old)
        new_core, new_pollen = self.stage_cams_family(self.new)

        with self.assertRaises(InvalidContractPublication):
            self.publisher.release_cams_family(
                old_core,
                new_pollen,
                validation_sha256="a" * 64,
                published_at=utc(self.new + timedelta(hours=11)),
            )
        with self.assertRaises(InvalidContractPublication):
            self.publisher.release_cams_family(
                old_pollen,
                old_core,
                validation_sha256="a" * 64,
                published_at=utc(self.old + timedelta(hours=11)),
            )

        self.publisher.release_cams_family(
            new_core,
            new_pollen,
            validation_sha256="b" * 64,
            published_at=utc(self.new + timedelta(hours=11)),
        )
        latest_before = self.store.get(self.publisher.cams_family_latest_key())
        with self.assertRaises(StaleContractRun):
            self.publisher.release_cams_family(
                old_core,
                old_pollen,
                validation_sha256="a" * 64,
                published_at=utc(self.old + timedelta(hours=11)),
            )
        with self.assertRaises(ImmutableContractConflict):
            self.publisher.release_cams_family(
                new_core,
                new_pollen,
                validation_sha256="c" * 64,
                published_at=utc(self.new + timedelta(hours=11)),
            )
        self.assertEqual(
            latest_before,
            self.store.get(self.publisher.cams_family_latest_key()),
        )

    def test_cams_family_crash_before_cas_is_invisible_and_resumable(self):
        core_stage, pollen_stage = self.stage_cams_family(self.old)
        crashing_store = OneShotLatestFailureStore(self.store)
        crashing_publisher = ContractV1Publisher(crashing_store, self.catalog)
        published_at = utc(self.old + timedelta(hours=11))

        with self.assertRaisesRegex(OSError, "before latest"):
            crashing_publisher.release_cams_family(
                core_stage,
                pollen_stage,
                validation_sha256="a" * 64,
                published_at=published_at,
            )
        release_key = self.publisher.cams_family_release_key(core_stage.source_run_id)
        self.assertTrue(self.store.exists(release_key))
        self.assertFalse(self.store.exists(self.publisher.cams_family_latest_key()))
        self.assertFalse(self.store.exists(self.publisher.latest_key(CAMS_PROVIDER)))
        self.assertFalse(self.store.exists(self.publisher.latest_key(CAMS_POLLEN_PROVIDER)))

        resumed = self.publisher.release_cams_family(
            core_stage,
            pollen_stage,
            validation_sha256="a" * 64,
            published_at=published_at,
        )
        self.assertTrue(resumed.release_reused)
        self.assertTrue(resumed.latest_updated)
        self.assertIsNotNone(self.publisher.read_verified_cams_family_latest())

    def test_cams_family_retry_after_lost_cas_response_is_idempotent(self):
        core_stage, pollen_stage = self.stage_cams_family(self.old)
        failing_store = PostFamilyLatestCasFailureStore(self.store)
        failing_publisher = ContractV1Publisher(failing_store, self.catalog)
        published_at = utc(self.old + timedelta(hours=11))

        with self.assertRaisesRegex(OSError, "lost response"):
            failing_publisher.release_cams_family(
                core_stage,
                pollen_stage,
                validation_sha256="a" * 64,
                published_at=published_at,
            )
        self.assertIsNotNone(self.publisher.read_verified_cams_family_latest())
        resumed = self.publisher.release_cams_family(
            core_stage,
            pollen_stage,
            validation_sha256="a" * 64,
            published_at=published_at,
        )
        self.assertTrue(resumed.idempotent)
        self.assertFalse(resumed.latest_updated)

    def test_cams_family_412_retries_are_bounded(self):
        core_stage, pollen_stage = self.stage_cams_family(self.old)
        rejecting_store = AlwaysFamilyLatestPreconditionStore(self.store)
        publisher = ContractV1Publisher(
            rejecting_store,
            self.catalog,
            max_cas_attempts=3,
        )

        with self.assertRaises(LatestCasExhausted):
            publisher.release_cams_family(
                core_stage,
                pollen_stage,
                validation_sha256="a" * 64,
                published_at=utc(self.old + timedelta(hours=11)),
            )
        self.assertEqual(
            [publisher.cams_family_latest_key()] * 3,
            rejecting_store.cas_keys,
        )
        self.assertTrue(
            self.store.exists(publisher.cams_family_release_key(core_stage.source_run_id))
        )
        self.assertFalse(self.store.exists(publisher.cams_family_latest_key()))

    def test_verified_cams_family_reader_rejects_missing_member_payload(self):
        core_stage, pollen_stage = self.stage_cams_family(self.old)
        self.publisher.release_cams_family(
            core_stage,
            pollen_stage,
            validation_sha256="a" * 64,
            published_at=utc(self.old + timedelta(hours=11)),
        )
        with self.store.lock:
            del self.store.objects[pollen_stage.payload_keys[0]]
            del self.store.generations[pollen_stage.payload_keys[0]]

        with self.assertRaisesRegex(
            ContractPublicationVerificationError,
            "missing a municipality",
        ):
            self.publisher.read_verified_cams_family_latest()

    def test_concurrent_cams_family_releases_finish_at_newest_run(self):
        old_stages = self.stage_cams_family(self.old)
        new_stages = self.stage_cams_family(self.new)
        barrier_store = FirstLatestCasBarrierStore(self.store)

        def concurrently_release(stages, run):
            publisher = ContractV1Publisher(barrier_store, self.catalog)
            try:
                return publisher.release_cams_family(
                    *stages,
                    validation_sha256=("a" if run == self.old else "b") * 64,
                    published_at=utc(run + timedelta(hours=11)),
                )
            except StaleContractRun:
                return "stale"

        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [
                executor.submit(concurrently_release, old_stages, self.old),
                executor.submit(concurrently_release, new_stages, self.new),
            ]
            results = [future.result() for future in futures]

        latest = self.publisher.read_verified_cams_family_latest()
        self.assertEqual(canonical_run_id(utc(self.new)), latest["latest"]["source_run_id"])
        self.assertTrue(any(result != "stale" for result in results))

    def test_cams_family_release_observes_concurrent_previous_revocation(self):
        old_stages = self.stage_cams_family(self.old)
        new_stages = self.stage_cams_family(self.new)
        old_run_id = canonical_run_id(utc(self.old))
        self.publisher.release_cams_family(
            *old_stages,
            validation_sha256="a" * 64,
            published_at=utc(self.old + timedelta(hours=11)),
        )
        pausing_store = PauseFamilyLatestCasStore(self.store, after=True)
        publisher = ContractV1Publisher(pausing_store, self.catalog)

        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(
                publisher.release_cams_family,
                *new_stages,
                validation_sha256="b" * 64,
                published_at=utc(self.new + timedelta(hours=11)),
            )
            self.assertTrue(pausing_store.reached.wait(20))
            try:
                self.publisher.revoke_cams_family(
                    old_run_id,
                    published_at=utc(self.new + timedelta(hours=12)),
                )
            finally:
                pausing_store.resume.set()
            result = future.result()

        latest = self.publisher.read_verified_cams_family_latest()
        latest_head = self.store.head(self.publisher.cams_family_latest_key())
        self.assertTrue(result.superseded)
        self.assertEqual(latest_head.etag, result.latest_etag)
        self.assertEqual(latest["revision"], result.revision)
        self.assertEqual([old_run_id], latest["disabled_run_ids"])

    def test_cams_family_release_observes_its_concurrent_rollback_as_superseded(self):
        old_stages = self.stage_cams_family(self.old)
        middle_stages = self.stage_cams_family(self.middle)
        new_stages = self.stage_cams_family(self.new)
        middle_run_id = canonical_run_id(utc(self.middle))
        new_run_id = canonical_run_id(utc(self.new))
        self.publisher.release_cams_family(
            *old_stages,
            validation_sha256="a" * 64,
            published_at=utc(self.old + timedelta(hours=11)),
        )
        self.publisher.release_cams_family(
            *middle_stages,
            validation_sha256="b" * 64,
            published_at=utc(self.middle + timedelta(hours=11)),
        )
        pausing_store = PauseFamilyLatestCasStore(self.store, after=True)
        publisher = ContractV1Publisher(pausing_store, self.catalog)

        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(
                publisher.release_cams_family,
                *new_stages,
                validation_sha256="c" * 64,
                published_at=utc(self.new + timedelta(hours=11)),
            )
            self.assertTrue(pausing_store.reached.wait(20))
            try:
                self.publisher.rollback_cams_family(
                    middle_run_id,
                    published_at=utc(self.new + timedelta(hours=12)),
                )
            finally:
                pausing_store.resume.set()
            result = future.result()

        latest = self.publisher.read_verified_cams_family_latest()
        latest_head = self.store.head(self.publisher.cams_family_latest_key())
        self.assertTrue(result.superseded)
        self.assertEqual(latest_head.etag, result.latest_etag)
        self.assertEqual(latest["revision"], result.revision)
        self.assertEqual(middle_run_id, latest["latest"]["source_run_id"])
        self.assertEqual([new_run_id], latest["disabled_run_ids"])

    def test_cams_family_release_rejects_post_cas_rollback_past_its_previous(self):
        old_stages = self.stage_cams_family(self.old)
        middle_stages = self.stage_cams_family(self.middle)
        new_stages = self.stage_cams_family(self.new)
        new_run_id = canonical_run_id(utc(self.new))
        self.publisher.release_cams_family(
            *old_stages,
            validation_sha256="a" * 64,
            published_at=utc(self.old + timedelta(hours=11)),
        )
        self.publisher.release_cams_family(
            *middle_stages,
            validation_sha256="b" * 64,
            published_at=utc(self.middle + timedelta(hours=11)),
        )
        before_release = json.loads(
            self.store.get(self.publisher.cams_family_latest_key()).body
        )
        unintended_rollback = before_release["previous"]
        pausing_store = PauseFamilyLatestCasStore(self.store, after=True)
        publisher = ContractV1Publisher(pausing_store, self.catalog)

        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(
                publisher.release_cams_family,
                *new_stages,
                validation_sha256="c" * 64,
                published_at=utc(self.new + timedelta(hours=11)),
            )
            self.assertTrue(pausing_store.reached.wait(20))
            try:
                rewritten = json.loads(
                    self.store.get(self.publisher.cams_family_latest_key()).body
                )
                rewritten.update(
                    revision=rewritten["revision"] + 1,
                    published_at=utc(self.new + timedelta(hours=12)),
                    latest=unintended_rollback,
                    previous=None,
                    disabled_run_ids=[new_run_id],
                )
                self.replace_cams_family_latest(rewritten)
            finally:
                pausing_store.resume.set()
            with self.assertRaisesRegex(
                ContractPublicationVerificationError,
                "regressed after CAS",
            ):
                future.result()

    def test_cams_family_rollback_losing_to_publish_is_stale_not_previous_revocation(self):
        old_stages = self.stage_cams_family(self.old)
        middle_stages = self.stage_cams_family(self.middle)
        new_stages = self.stage_cams_family(self.new)
        old_run_id = canonical_run_id(utc(self.old))
        middle_run_id = canonical_run_id(utc(self.middle))
        new_run_id = canonical_run_id(utc(self.new))
        self.publisher.release_cams_family(
            *old_stages,
            validation_sha256="a" * 64,
            published_at=utc(self.old + timedelta(hours=11)),
        )
        self.publisher.release_cams_family(
            *middle_stages,
            validation_sha256="b" * 64,
            published_at=utc(self.middle + timedelta(hours=11)),
        )

        before = self.store.get(self.publisher.cams_family_latest_key())
        with self.assertRaisesRegex(StaleContractRun, "no longer the active"):
            self.publisher.revoke_cams_family(
                old_run_id,
                published_at=utc(self.middle + timedelta(hours=12)),
                rollback_to_run_id=old_run_id,
            )
        self.assertEqual(before, self.store.get(self.publisher.cams_family_latest_key()))

        pausing_store = PauseFamilyLatestCasStore(self.store, after=False)
        publisher = ContractV1Publisher(pausing_store, self.catalog)
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(
                publisher.rollback_cams_family,
                old_run_id,
                published_at=utc(self.new + timedelta(hours=12)),
            )
            self.assertTrue(pausing_store.reached.wait(20))
            try:
                self.publisher.release_cams_family(
                    *new_stages,
                    validation_sha256="c" * 64,
                    published_at=utc(self.new + timedelta(hours=11)),
                )
            finally:
                pausing_store.resume.set()
            with self.assertRaisesRegex(StaleContractRun, "no longer the active"):
                future.result()

        latest = self.publisher.read_verified_cams_family_latest()
        self.assertEqual(new_run_id, latest["latest"]["source_run_id"])
        self.assertEqual(middle_run_id, latest["previous"]["source_run_id"])
        self.assertEqual([], latest["disabled_run_ids"])

    def test_cams_family_rollback_rejects_post_cas_reinterpretation(self):
        old_stages = self.stage_cams_family(self.old)
        middle_stages = self.stage_cams_family(self.middle)
        new_stages = self.stage_cams_family(self.new)
        middle_run_id = canonical_run_id(utc(self.middle))
        new_run_id = canonical_run_id(utc(self.new))
        self.publisher.release_cams_family(
            *old_stages,
            validation_sha256="a" * 64,
            published_at=utc(self.old + timedelta(hours=11)),
        )
        self.publisher.release_cams_family(
            *middle_stages,
            validation_sha256="b" * 64,
            published_at=utc(self.middle + timedelta(hours=11)),
        )
        before_new = json.loads(
            self.store.get(self.publisher.cams_family_latest_key()).body
        )
        unintended_rollback = before_new["previous"]
        self.publisher.release_cams_family(
            *new_stages,
            validation_sha256="c" * 64,
            published_at=utc(self.new + timedelta(hours=11)),
        )
        pausing_store = PauseFamilyLatestCasStore(self.store, after=True)
        publisher = ContractV1Publisher(pausing_store, self.catalog)

        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(
                publisher.rollback_cams_family,
                middle_run_id,
                published_at=utc(self.new + timedelta(hours=12)),
            )
            self.assertTrue(pausing_store.reached.wait(20))
            try:
                rewritten = json.loads(
                    self.store.get(self.publisher.cams_family_latest_key()).body
                )
                rewritten.update(
                    revision=rewritten["revision"] + 1,
                    published_at=utc(self.new + timedelta(hours=13)),
                    latest=unintended_rollback,
                    previous=None,
                    disabled_run_ids=sorted([middle_run_id, new_run_id]),
                )
                self.replace_cams_family_latest(rewritten)
            finally:
                pausing_store.resume.set()
            with self.assertRaisesRegex(
                ContractPublicationVerificationError,
                "impossible active release",
            ):
                future.result()

    def test_cams_family_revocation_rejects_changed_body_at_same_revision(self):
        old_stages = self.stage_cams_family(self.old)
        new_stages = self.stage_cams_family(self.new)
        old_run_id = canonical_run_id(utc(self.old))
        self.publisher.release_cams_family(
            *old_stages,
            validation_sha256="a" * 64,
            published_at=utc(self.old + timedelta(hours=11)),
        )
        self.publisher.release_cams_family(
            *new_stages,
            validation_sha256="b" * 64,
            published_at=utc(self.new + timedelta(hours=11)),
        )
        pausing_store = PauseFamilyLatestCasStore(self.store, after=True)
        publisher = ContractV1Publisher(pausing_store, self.catalog)

        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(
                publisher.revoke_cams_family,
                old_run_id,
                published_at=utc(self.new + timedelta(hours=12)),
            )
            self.assertTrue(pausing_store.reached.wait(20))
            try:
                rewritten = json.loads(
                    self.store.get(self.publisher.cams_family_latest_key()).body
                )
                rewritten["published_at"] = utc(self.new + timedelta(hours=13))
                self.replace_cams_family_latest(rewritten)
            finally:
                pausing_store.resume.set()
            with self.assertRaisesRegex(
                ContractPublicationVerificationError,
                "without advancing its revision",
            ):
                future.result()

    def test_cams_family_revocation_rolls_back_one_pointer_and_blocks_high_water(self):
        old_stages = self.stage_cams_family(self.old)
        middle_stages = self.stage_cams_family(self.middle)
        new_stages = self.stage_cams_family(self.new)
        self.publisher.release_cams_family(
            *old_stages,
            validation_sha256="a" * 64,
            published_at=utc(self.old + timedelta(hours=11)),
        )
        self.publisher.release_cams_family(
            *new_stages,
            validation_sha256="c" * 64,
            published_at=utc(self.new + timedelta(hours=11)),
        )
        family_keys_before = self.store.list_keys("weather/v1/families/cams/")
        recording = RecordingStore(self.store)
        publisher = ContractV1Publisher(recording, self.catalog)
        old_run_id = canonical_run_id(utc(self.old))
        new_run_id = canonical_run_id(utc(self.new))

        rolled_back = publisher.rollback_cams_family(
            old_run_id,
            published_at=utc(self.new + timedelta(hours=12)),
        )

        self.assertTrue(rolled_back.latest_updated)
        self.assertTrue(rolled_back.rolled_back)
        self.assertFalse(rolled_back.superseded)
        self.assertEqual(old_run_id, rolled_back.active_run_id)
        self.assertEqual(
            [publisher.cams_family_latest_key()],
            recording.cas_keys,
        )
        latest = publisher.read_verified_cams_family_latest()
        self.assertEqual(old_run_id, latest["latest"]["source_run_id"])
        self.assertIsNone(latest["previous"])
        self.assertEqual([new_run_id], latest["disabled_run_ids"])
        self.assertEqual(
            family_keys_before,
            self.store.list_keys("weather/v1/families/cams/"),
        )
        self.assertFalse(self.store.exists(publisher.latest_key(CAMS_PROVIDER)))
        self.assertFalse(
            self.store.exists(publisher.latest_key(CAMS_POLLEN_PROVIDER))
        )

        cas_count = len(recording.cas_keys)
        repeated = publisher.revoke_cams_family(
            new_run_id,
            published_at=utc(self.new + timedelta(hours=13)),
        )
        self.assertTrue(repeated.idempotent)
        self.assertTrue(repeated.rolled_back)
        self.assertFalse(repeated.latest_updated)
        self.assertEqual(cas_count, len(recording.cas_keys))
        with self.assertRaisesRegex(InvalidContractPublication, "current or previous"):
            publisher.revoke_cams_family(
                canonical_run_id(utc(self.middle)),
                published_at=utc(self.new + timedelta(hours=13)),
            )

        for stages, fingerprint in (
            (middle_stages, "b" * 64),
            (new_stages, "c" * 64),
        ):
            with self.assertRaises(StaleContractRun):
                publisher.release_cams_family(
                    *stages,
                    validation_sha256=fingerprint,
                    published_at=utc(self.new + timedelta(hours=14)),
                )

    def test_cams_family_revoking_previous_keeps_current_pair(self):
        old_stages = self.stage_cams_family(self.old)
        new_stages = self.stage_cams_family(self.new)
        self.publisher.release_cams_family(
            *old_stages,
            validation_sha256="a" * 64,
            published_at=utc(self.old + timedelta(hours=11)),
        )
        self.publisher.release_cams_family(
            *new_stages,
            validation_sha256="b" * 64,
            published_at=utc(self.new + timedelta(hours=11)),
        )
        recording = RecordingStore(self.store)
        publisher = ContractV1Publisher(recording, self.catalog)
        old_run_id = canonical_run_id(utc(self.old))
        new_run_id = canonical_run_id(utc(self.new))

        revoked = publisher.revoke_cams_family(
            old_run_id,
            published_at=utc(self.new + timedelta(hours=12)),
        )

        self.assertFalse(revoked.rolled_back)
        self.assertEqual(new_run_id, revoked.active_run_id)
        self.assertEqual(
            [publisher.cams_family_latest_key()],
            recording.cas_keys,
        )
        latest = publisher.read_verified_cams_family_latest()
        self.assertEqual(new_run_id, latest["latest"]["source_run_id"])
        self.assertIsNone(latest["previous"])
        self.assertEqual([old_run_id], latest["disabled_run_ids"])

        future = self.new + timedelta(hours=6)
        future_stages = self.stage_cams_family(future, publisher)
        future_run_id = canonical_run_id(utc(future))
        publisher.release_cams_family(
            *future_stages,
            validation_sha256="c" * 64,
            published_at=utc(future + timedelta(hours=11)),
        )
        publisher.revoke_cams_family(
            new_run_id,
            published_at=utc(future + timedelta(hours=12)),
        )
        latest = publisher.read_verified_cams_family_latest()
        self.assertEqual(future_run_id, latest["latest"]["source_run_id"])
        self.assertIsNone(latest["previous"])
        self.assertEqual(
            sorted([old_run_id, new_run_id]),
            latest["disabled_run_ids"],
        )

    def test_cams_family_rollback_is_current_previous_only_and_lost_response_safe(self):
        old_stages = self.stage_cams_family(self.old)
        middle_stages = self.stage_cams_family(self.middle)
        new_stages = self.stage_cams_family(self.new)
        old_run_id = canonical_run_id(utc(self.old))
        middle_run_id = canonical_run_id(utc(self.middle))
        self.publisher.release_cams_family(
            *old_stages,
            validation_sha256="a" * 64,
            published_at=utc(self.old + timedelta(hours=11)),
        )
        with self.assertRaisesRegex(InvalidContractPublication, "previous release"):
            self.publisher.revoke_cams_family(
                old_run_id,
                published_at=utc(self.old + timedelta(hours=12)),
            )
        self.publisher.release_cams_family(
            *middle_stages,
            validation_sha256="b" * 64,
            published_at=utc(self.middle + timedelta(hours=11)),
        )
        self.publisher.release_cams_family(
            *new_stages,
            validation_sha256="c" * 64,
            published_at=utc(self.new + timedelta(hours=11)),
        )
        with self.assertRaisesRegex(InvalidContractPublication, "current previous"):
            self.publisher.rollback_cams_family(
                old_run_id,
                published_at=utc(self.new + timedelta(hours=12)),
            )

        failing = ContractV1Publisher(
            PostFamilyLatestCasFailureStore(self.store),
            self.catalog,
        )
        with self.assertRaisesRegex(OSError, "lost response"):
            failing.rollback_cams_family(
                middle_run_id,
                published_at=utc(self.new + timedelta(hours=12)),
            )
        resumed = self.publisher.rollback_cams_family(
            middle_run_id,
            published_at=utc(self.new + timedelta(hours=13)),
        )
        self.assertTrue(resumed.idempotent)
        self.assertTrue(resumed.rolled_back)
        self.assertFalse(resumed.latest_updated)
        with self.assertRaisesRegex(InvalidContractPublication, "published_at"):
            self.publisher.rollback_cams_family(
                middle_run_id,
                published_at="not-a-timestamp",
            )
        latest = self.publisher.read_verified_cams_family_latest()
        self.assertEqual(middle_run_id, latest["latest"]["source_run_id"])
        self.assertIsNone(latest["previous"])

    def test_generic_revocation_and_rollback_reject_both_legacy_cams_pointers(self):
        run_id = canonical_run_id(utc(self.old))
        for provider, bundle in (
            (CAMS_PROVIDER, self.cams_bundle(self.old)),
            (CAMS_POLLEN_PROVIDER, self.cams_pollen_bundle(self.old)),
        ):
            documents, manifest = bundle
            self.publisher.publish_run(
                provider,
                documents,
                manifest,
                published_at=utc(self.old + timedelta(hours=11)),
            )
            latest_key = self.publisher.latest_key(provider)
            before = self.store.get(latest_key)

            with self.assertRaisesRegex(InvalidContractPublication, "atomic family"):
                self.publisher.revoke_run(
                    provider,
                    run_id,
                    published_at=utc(self.old + timedelta(hours=12)),
                )
            with self.assertRaisesRegex(InvalidContractPublication, "atomic family"):
                self.publisher.rollback_latest(
                    provider,
                    run_id,
                    published_at=utc(self.old + timedelta(hours=12)),
                )

            self.assertEqual(before, self.store.get(latest_key))

    def test_revocation_rolls_back_by_cas_retains_objects_and_blocks_old_republication(self):
        old_result = self.publish(self.old)
        new_result = self.publish(self.new)
        keys_before = self.store.list_keys("weather/v1/icon2i/")
        rolled_back = self.publisher.rollback_latest(
            ICON_PROVIDER,
            canonical_run_id(utc(self.old)),
            published_at=utc(self.new + timedelta(hours=3)),
        )
        self.assertTrue(rolled_back.latest_updated)
        self.assertTrue(rolled_back.rolled_back)
        latest = self.publisher.read_latest(ICON_PROVIDER)
        self.assertEqual(canonical_run_id(utc(self.old)), latest["latest"]["source_run_id"])
        self.assertEqual([canonical_run_id(utc(self.new))], latest["disabled_run_ids"])
        self.assertIsNone(latest["previous"])
        self.assertEqual(keys_before, self.store.list_keys("weather/v1/icon2i/"))
        self.assertTrue(self.store.exists(old_result.manifest_key))
        self.assertTrue(self.store.exists(new_result.manifest_key))
        self.assertTrue(all(self.store.exists(key) for key in new_result.payload_keys))

        latest_head = self.store.head(new_result.latest_key)
        repeated = self.publisher.revoke_run(
            ICON_PROVIDER,
            canonical_run_id(utc(self.new)),
            published_at=utc(self.new + timedelta(hours=4)),
        )
        self.assertTrue(repeated.idempotent)
        self.assertFalse(repeated.latest_updated)
        self.assertEqual(latest_head, self.store.head(new_result.latest_key))

        for stale_run in (self.middle, self.new):
            documents, manifest = self.icon_bundle(stale_run)
            with self.subTest(stale_run=stale_run), self.assertRaises(StaleContractRun):
                self.publisher.publish_run(
                    ICON_PROVIDER,
                    documents,
                    manifest,
                    published_at=utc(stale_run + timedelta(hours=5)),
                )


if __name__ == "__main__":
    unittest.main()
