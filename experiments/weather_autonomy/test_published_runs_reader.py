"""Fast tests for the verified, referenced-run read capability."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from local_pipeline.contract_v1 import (
    CAMS_POLLEN_PROVIDER,
    CAMS_PROVIDER,
    ICON_PROVIDER,
    build_latest_document,
    build_run_manifest,
    canonical_json_bytes,
    canonical_run_id,
    load_catalog,
)
from local_pipeline.published_runs_reader import (
    PublishedRunsObjectReader,
    PublishedRunsReaderError,
)
from local_pipeline.sqlite_object_store import ObjectNotFound, SQLiteObjectStore
from local_pipeline.sqlite_read_only_object_store import SQLiteReadOnlyObjectStore
from test_contract_publisher import MemoryObjectStore


BODY = b"{}"
FAMILY_ROOT = "weather/v1/families/cams"
FAMILY_LATEST_KEY = f"{FAMILY_ROOT}/latest.json"


def utc(day: int) -> str:
    return datetime(2026, 9, day, tzinfo=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def manifest(provider, run_at, catalog):
    run_id = canonical_run_id(run_at)
    digest = hashlib.sha256(BODY).hexdigest()
    descriptors = {
        istat_code: {
            "path": f"runs/{run_id}/municipalities/{istat_code}.json",
            "json_bytes": len(BODY),
            "sha256": digest,
        }
        for istat_code in catalog.istat_codes
    }
    generated = (
        datetime.strptime(run_at, "%Y-%m-%dT%H:%M:%SZ")
        .replace(tzinfo=timezone.utc)
        + timedelta(minutes=30)
    ).strftime("%Y-%m-%dT%H:%M:%SZ")
    return build_run_manifest(
        provider=provider,
        run_at=run_at,
        generated_at=generated,
        catalog=catalog,
        objects=descriptors,
    )


def root(provider):
    return f"weather/v1/{provider}"


def manifest_key(provider, document):
    return f"{root(provider)}/runs/{document['source_run_id']}/manifest.json"


def object_key(provider, document, istat_code):
    return f"{root(provider)}/runs/{document['source_run_id']}/municipalities/{istat_code}.json"


def family_release(
    core,
    pollen,
    catalog,
    *,
    validation_sha256="a" * 64,
    published_at="2026-09-04T12:00:00Z",
):
    run_id = core["source_run_id"]

    def component(role, provider, document):
        body = canonical_json_bytes(document)
        return role, {
            "provider": provider,
            "source_run_id": document["source_run_id"],
            "manifest_key": manifest_key(provider, document),
            "manifest_json_bytes": len(body),
            "manifest_sha256": hashlib.sha256(body).hexdigest(),
        }

    return {
        "schema_version": 1,
        "kind": "meteofriul.weather.cams_family_release",
        "family": "cams",
        "source_run_id": run_id,
        "published_at": published_at,
        "validation_sha256": validation_sha256,
        "catalog": catalog.reference(),
        "components": dict(
            (
                component("core", CAMS_PROVIDER, core),
                component("pollen", CAMS_POLLEN_PROVIDER, pollen),
            )
        ),
    }


def family_release_key(document):
    return f"{FAMILY_ROOT}/runs/{document['source_run_id']}/release.json"


def family_release_descriptor(document):
    body = canonical_json_bytes(document)
    return {
        "source_run_id": document["source_run_id"],
        "release_path": f"runs/{document['source_run_id']}/release.json",
        "release_json_bytes": len(body),
        "release_sha256": hashlib.sha256(body).hexdigest(),
    }


def family_latest(
    current,
    catalog,
    *,
    previous=None,
    revision=1,
    published_at=None,
    disabled=(),
):
    return {
        "schema_version": 1,
        "kind": "meteofriul.weather.cams_family_latest",
        "family": "cams",
        "revision": revision,
        "published_at": (
            current["published_at"] if published_at is None else published_at
        ),
        "catalog": catalog.reference(),
        "latest": family_release_descriptor(current),
        "previous": (
            None if previous is None else family_release_descriptor(previous)
        ),
        "disabled_run_ids": list(disabled),
    }


class RecordingReader:
    def __init__(self, backing):
        self.backing = backing
        self.read_keys = []

    def head(self, key):
        self.read_keys.append(("head", key))
        return self.backing.head(key)

    def get(self, key):
        self.read_keys.append(("get", key))
        return self.backing.get(key)

    def close(self):
        close = getattr(self.backing, "close", None)
        if callable(close):
            close()


class SwitchingReader(RecordingReader):
    def __init__(self, backing, switch):
        super().__init__(backing)
        self.switch = switch
        self.switched = False

    def get(self, key):
        stored = super().get(key)
        if key == FAMILY_LATEST_KEY and not self.switched:
            self.switched = True
            self.switch()
        return stored


class PublishedRunsObjectReaderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog = load_catalog()
        cls.istat_code = cls.catalog.istat_codes[0]
        cls.icon_a = manifest(ICON_PROVIDER, utc(1), cls.catalog)
        cls.icon_b = manifest(ICON_PROVIDER, utc(2), cls.catalog)
        cls.icon_c = manifest(ICON_PROVIDER, utc(3), cls.catalog)
        cls.cams_a = manifest(CAMS_PROVIDER, utc(1), cls.catalog)
        cls.cams_b = manifest(CAMS_PROVIDER, utc(2), cls.catalog)
        cls.cams_c = manifest(CAMS_PROVIDER, utc(3), cls.catalog)
        cls.cams_x = manifest(
            CAMS_PROVIDER,
            "2026-08-31T00:00:00Z",
            cls.catalog,
        )
        cls.pollen_a = manifest(CAMS_POLLEN_PROVIDER, utc(1), cls.catalog)
        cls.pollen_b = manifest(CAMS_POLLEN_PROVIDER, utc(2), cls.catalog)
        cls.pollen_c = manifest(CAMS_POLLEN_PROVIDER, utc(3), cls.catalog)
        cls.pollen_x = manifest(
            CAMS_POLLEN_PROVIDER,
            "2026-08-31T00:00:00Z",
            cls.catalog,
        )

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="weather-published-reader-")
        self.addCleanup(self.temporary.cleanup)
        self.path = Path(self.temporary.name) / "objects.sqlite3"
        self.writer = SQLiteObjectStore(self.path)

    def use_memory_store(self):
        self.writer = MemoryObjectStore()

    def put_run(
        self,
        provider,
        document,
        *,
        object_body=BODY,
        omit_istat_codes=(),
    ):
        self.writer.put(
            manifest_key(provider, document),
            canonical_json_bytes(document),
            content_type="application/json",
            metadata={"kind": "manifest"},
        )
        omitted = frozenset(omit_istat_codes)
        for istat_code in self.catalog.istat_codes:
            if istat_code in omitted:
                continue
            body = object_body if istat_code == self.istat_code else BODY
            self.writer.put(
                object_key(provider, document, istat_code),
                body,
                content_type="application/json",
                metadata={"kind": "municipality"},
            )

    def latest(
        self,
        provider,
        current,
        *,
        previous=None,
        disabled=(),
        revision=None,
    ):
        return build_latest_document(
            provider=provider,
            revision=(1 if previous is None else 2) if revision is None else revision,
            published_at="2026-09-04T12:00:00Z",
            run_manifest=current,
            previous_manifest=previous,
            disabled_run_ids=disabled,
            catalog=self.catalog,
        )

    def put_latest(self, provider, document):
        key = f"{root(provider)}/latest.json"
        body = canonical_json_bytes(document)
        if self.writer.exists(key):
            current = self.writer.head(key)
            return self.writer.compare_and_swap(
                key,
                body,
                expected_etag=current.etag,
                content_type="application/json",
                metadata={"kind": "latest"},
            )
        return self.writer.put(
            key,
            body,
            content_type="application/json",
            metadata={"kind": "latest"},
        )

    def put_family_release(self, document):
        return self.writer.put(
            family_release_key(document),
            canonical_json_bytes(document),
            content_type="application/json",
            metadata={"kind": "cams_family_release"},
        )

    def put_family_latest(self, document):
        body = canonical_json_bytes(document)
        if self.writer.exists(FAMILY_LATEST_KEY):
            current = self.writer.head(FAMILY_LATEST_KEY)
            return self.writer.compare_and_swap(
                FAMILY_LATEST_KEY,
                body,
                expected_etag=current.etag,
                content_type="application/json",
                metadata={"kind": "cams_family_latest"},
            )
        return self.writer.put(
            FAMILY_LATEST_KEY,
            body,
            content_type="application/json",
            metadata={"kind": "cams_family_latest"},
        )

    def put_family(
        self,
        core,
        pollen,
        *,
        previous=None,
        revision=1,
        published_at="2026-09-04T12:00:00Z",
        latest_published_at=None,
        disabled=(),
    ):
        current_release = family_release(
            core,
            pollen,
            self.catalog,
            published_at=published_at,
        )
        self.put_family_release(current_release)
        previous_release = None
        if previous is not None:
            previous_release = family_release(previous[0], previous[1], self.catalog)
            if not self.writer.exists(family_release_key(previous_release)):
                self.put_family_release(previous_release)
        latest = family_latest(
            current_release,
            self.catalog,
            previous=previous_release,
            revision=revision,
            published_at=latest_published_at,
            disabled=disabled,
        )
        self.put_family_latest(latest)
        return current_release, latest

    def reader(self):
        backing = (
            SQLiteReadOnlyObjectStore(self.path)
            if isinstance(self.writer, SQLiteObjectStore)
            else self.writer
        )
        return PublishedRunsObjectReader(
            backing,
            self.catalog,
        )

    def test_unreferenced_run_is_hidden_even_when_its_objects_exist(self):
        self.put_run(ICON_PROVIDER, self.icon_a)
        self.put_run(ICON_PROVIDER, self.icon_b)
        latest_a = self.latest(ICON_PROVIDER, self.icon_a)
        self.put_latest(ICON_PROVIDER, latest_a)
        reader = self.reader()

        self.assertEqual(
            canonical_json_bytes(latest_a),
            reader.get(f"{root(ICON_PROVIDER)}/latest.json").body,
        )
        self.assertEqual(
            BODY,
            reader.get(object_key(ICON_PROVIDER, self.icon_a, self.istat_code)).body,
        )
        with self.assertRaises(ObjectNotFound):
            reader.get(object_key(ICON_PROVIDER, self.icon_b, self.istat_code))

    def test_latest_refresh_is_atomic_and_keeps_in_flight_published_runs(self):
        for document in (self.icon_a, self.icon_b, self.icon_c):
            self.put_run(ICON_PROVIDER, document)
        self.put_latest(ICON_PROVIDER, self.latest(ICON_PROVIDER, self.icon_a))
        reader = self.reader()

        latest_b = self.latest(ICON_PROVIDER, self.icon_b, previous=self.icon_a)
        self.put_latest(ICON_PROVIDER, latest_b)
        self.assertEqual(
            canonical_json_bytes(latest_b),
            reader.get(f"{root(ICON_PROVIDER)}/latest.json").body,
        )
        self.assertEqual(
            BODY,
            reader.get(object_key(ICON_PROVIDER, self.icon_b, self.istat_code)).body,
        )

        latest_c = build_latest_document(
            provider=ICON_PROVIDER,
            revision=3,
            published_at="2026-09-04T13:00:00Z",
            run_manifest=self.icon_c,
            previous_manifest=self.icon_b,
            disabled_run_ids=(),
            catalog=self.catalog,
        )
        self.put_latest(ICON_PROVIDER, latest_c)
        reader.get(f"{root(ICON_PROVIDER)}/latest.json")
        self.assertEqual(
            BODY,
            reader.get(object_key(ICON_PROVIDER, self.icon_a, self.istat_code)).body,
        )

    def test_revoked_run_is_removed_from_the_cumulative_allow_list(self):
        self.put_run(ICON_PROVIDER, self.icon_a)
        self.put_run(ICON_PROVIDER, self.icon_b)
        self.put_latest(ICON_PROVIDER, self.latest(ICON_PROVIDER, self.icon_a))
        reader = self.reader()
        reader.get(object_key(ICON_PROVIDER, self.icon_a, self.istat_code))

        revoked = self.latest(
            ICON_PROVIDER,
            self.icon_b,
            previous=self.icon_a,
            disabled=(self.icon_a["source_run_id"],),
        )
        self.put_latest(ICON_PROVIDER, revoked)
        reader.get(f"{root(ICON_PROVIDER)}/latest.json")
        with self.assertRaises(ObjectNotFound):
            reader.get(object_key(ICON_PROVIDER, self.icon_a, self.istat_code))

    def test_later_pointer_cannot_reenable_a_previously_revoked_run(self):
        for document in (self.icon_a, self.icon_b, self.icon_c):
            self.put_run(ICON_PROVIDER, document)
        self.put_latest(ICON_PROVIDER, self.latest(ICON_PROVIDER, self.icon_a))
        reader = self.reader()

        revoked = self.latest(
            ICON_PROVIDER,
            self.icon_b,
            previous=self.icon_a,
            disabled=(self.icon_a["source_run_id"],),
        )
        self.put_latest(ICON_PROVIDER, revoked)
        reader.get(f"{root(ICON_PROVIDER)}/latest.json")

        later = self.latest(
            ICON_PROVIDER,
            self.icon_c,
            previous=self.icon_b,
            disabled=(),
            revision=3,
        )
        self.put_latest(ICON_PROVIDER, later)
        self.assertEqual(
            canonical_json_bytes(later),
            reader.get(f"{root(ICON_PROVIDER)}/latest.json").body,
        )
        with self.assertRaises(ObjectNotFound):
            reader.get(object_key(ICON_PROVIDER, self.icon_a, self.istat_code))

    def test_same_or_lower_revision_with_different_bytes_is_retained(self):
        self.put_run(ICON_PROVIDER, self.icon_a)
        self.put_run(ICON_PROVIDER, self.icon_b)
        latest_a = self.latest(ICON_PROVIDER, self.icon_a, revision=2)
        self.put_latest(ICON_PROVIDER, latest_a)
        reader = self.reader()

        regressed = self.latest(ICON_PROVIDER, self.icon_b, revision=2)
        self.put_latest(ICON_PROVIDER, regressed)
        self.assertEqual(
            canonical_json_bytes(latest_a),
            reader.get(f"{root(ICON_PROVIDER)}/latest.json").body,
        )
        with self.assertRaises(ObjectNotFound):
            reader.get(object_key(ICON_PROVIDER, self.icon_b, self.istat_code))
        self.assertEqual("retained", reader.provider_statuses[ICON_PROVIDER]["status"])

    def test_higher_revision_cannot_regress_without_explicit_revocation(self):
        self.put_run(ICON_PROVIDER, self.icon_a)
        self.put_run(ICON_PROVIDER, self.icon_c)
        latest_c = self.latest(ICON_PROVIDER, self.icon_c, revision=3)
        self.put_latest(ICON_PROVIDER, latest_c)
        reader = self.reader()

        silent_regression = self.latest(ICON_PROVIDER, self.icon_a, revision=4)
        self.put_latest(ICON_PROVIDER, silent_regression)
        self.assertEqual(
            canonical_json_bytes(latest_c),
            reader.get(f"{root(ICON_PROVIDER)}/latest.json").body,
        )
        self.assertEqual("retained", reader.provider_statuses[ICON_PROVIDER]["status"])

        explicit_rollback = self.latest(
            ICON_PROVIDER,
            self.icon_a,
            disabled=(self.icon_c["source_run_id"],),
            revision=5,
        )
        self.put_latest(ICON_PROVIDER, explicit_rollback)
        self.assertEqual(
            canonical_json_bytes(explicit_rollback),
            reader.get(f"{root(ICON_PROVIDER)}/latest.json").body,
        )
        with self.assertRaises(ObjectNotFound):
            reader.get(object_key(ICON_PROVIDER, self.icon_c, self.istat_code))

    def test_previous_run_must_precede_the_active_run(self):
        self.put_run(ICON_PROVIDER, self.icon_a)
        self.put_run(ICON_PROVIDER, self.icon_b)
        latest_b = self.latest(ICON_PROVIDER, self.icon_b)
        self.put_latest(ICON_PROVIDER, latest_b)
        reader = self.reader()

        invalid_order = self.latest(
            ICON_PROVIDER,
            self.icon_a,
            previous=self.icon_b,
            revision=2,
        )
        self.put_latest(ICON_PROVIDER, invalid_order)
        self.assertEqual(
            canonical_json_bytes(latest_b),
            reader.get(f"{root(ICON_PROVIDER)}/latest.json").body,
        )
        with self.assertRaises(ObjectNotFound):
            reader.get(object_key(ICON_PROVIDER, self.icon_a, self.istat_code))

    def test_invalid_new_latest_retains_the_last_verified_snapshot(self):
        self.put_run(ICON_PROVIDER, self.icon_a)
        self.put_run(ICON_PROVIDER, self.icon_b)
        latest_a = self.latest(ICON_PROVIDER, self.icon_a)
        self.put_latest(ICON_PROVIDER, latest_a)
        reader = self.reader()

        self.put_latest(ICON_PROVIDER, {})
        self.assertEqual(
            canonical_json_bytes(latest_a),
            reader.get(f"{root(ICON_PROVIDER)}/latest.json").body,
        )
        with self.assertRaises(ObjectNotFound):
            reader.get(object_key(ICON_PROVIDER, self.icon_b, self.istat_code))
        self.assertEqual("retained", reader.provider_statuses[ICON_PROVIDER]["status"])

    def test_provider_can_appear_later_without_restarting_the_reader(self):
        self.use_memory_store()
        self.put_run(ICON_PROVIDER, self.icon_a)
        self.put_latest(ICON_PROVIDER, self.latest(ICON_PROVIDER, self.icon_a))
        # A legacy provider pointer is intentionally insufficient after cutover.
        self.put_run(CAMS_PROVIDER, self.cams_a)
        self.put_latest(CAMS_PROVIDER, self.latest(CAMS_PROVIDER, self.cams_a))
        reader = self.reader()
        self.assertEqual("unavailable", reader.provider_statuses[CAMS_PROVIDER]["status"])
        self.assertEqual(
            "unavailable",
            reader.provider_statuses[CAMS_POLLEN_PROVIDER]["status"],
        )
        with self.assertRaises(ObjectNotFound):
            reader.get(f"{root(CAMS_PROVIDER)}/latest.json")

        self.put_run(CAMS_POLLEN_PROVIDER, self.pollen_a)
        _release, latest_cams = self.put_family(self.cams_a, self.pollen_a)
        self.assertEqual(
            canonical_json_bytes(latest_cams),
            reader.get(FAMILY_LATEST_KEY).body,
        )
        self.assertEqual(
            BODY,
            reader.get(object_key(CAMS_PROVIDER, self.cams_a, self.istat_code)).body,
        )
        self.assertEqual(
            BODY,
            reader.get(
                object_key(CAMS_POLLEN_PROVIDER, self.pollen_a, self.istat_code)
            ).body,
        )
        self.assertEqual("verified", reader.provider_statuses[CAMS_PROVIDER]["status"])
        self.assertEqual(
            "verified",
            reader.provider_statuses[CAMS_POLLEN_PROVIDER]["status"],
        )

    def test_cams_family_never_reads_or_authorizes_legacy_latest_objects(self):
        self.use_memory_store()
        self.put_run(CAMS_PROVIDER, self.cams_a)
        self.put_run(CAMS_POLLEN_PROVIDER, self.pollen_a)
        self.put_latest(CAMS_PROVIDER, self.latest(CAMS_PROVIDER, self.cams_a))
        self.put_latest(
            CAMS_POLLEN_PROVIDER,
            self.latest(CAMS_POLLEN_PROVIDER, self.pollen_a),
        )
        self.put_family(self.cams_a, self.pollen_a)
        recording = RecordingReader(self.writer)
        reader = PublishedRunsObjectReader(recording, self.catalog)

        self.assertEqual(BODY, reader.get(object_key(
            CAMS_PROVIDER,
            self.cams_a,
            self.istat_code,
        )).body)
        self.assertEqual(BODY, reader.get(object_key(
            CAMS_POLLEN_PROVIDER,
            self.pollen_a,
            self.istat_code,
        )).body)
        for provider in (CAMS_PROVIDER, CAMS_POLLEN_PROVIDER):
            legacy_key = f"{root(provider)}/latest.json"
            with self.assertRaises(ObjectNotFound):
                reader.get(legacy_key)
            self.assertNotIn(("head", legacy_key), recording.read_keys)
            self.assertNotIn(("get", legacy_key), recording.read_keys)

    def test_incomplete_cams_member_keeps_both_members_unavailable(self):
        self.use_memory_store()
        self.put_run(ICON_PROVIDER, self.icon_a)
        self.put_latest(ICON_PROVIDER, self.latest(ICON_PROVIDER, self.icon_a))
        self.put_run(CAMS_PROVIDER, self.cams_a)
        self.put_run(
            CAMS_POLLEN_PROVIDER,
            self.pollen_a,
            omit_istat_codes=(self.catalog.istat_codes[-1],),
        )
        self.put_family(self.cams_a, self.pollen_a)
        reader = self.reader()

        self.assertEqual("unavailable", reader.provider_statuses[CAMS_PROVIDER]["status"])
        self.assertEqual(
            "unavailable",
            reader.provider_statuses[CAMS_POLLEN_PROVIDER]["status"],
        )
        for provider, document in (
            (CAMS_PROVIDER, self.cams_a),
            (CAMS_POLLEN_PROVIDER, self.pollen_a),
        ):
            with self.assertRaises(ObjectNotFound):
                reader.get(object_key(provider, document, self.istat_code))

    def test_invalid_new_cams_family_retains_the_complete_previous_pair(self):
        self.use_memory_store()
        self.put_run(CAMS_PROVIDER, self.cams_a)
        self.put_run(CAMS_POLLEN_PROVIDER, self.pollen_a)
        _release_a, latest_a = self.put_family(self.cams_a, self.pollen_a)
        reader = self.reader()

        self.put_run(CAMS_PROVIDER, self.cams_b)
        self.put_run(
            CAMS_POLLEN_PROVIDER,
            self.pollen_b,
            omit_istat_codes=(self.catalog.istat_codes[-1],),
        )
        self.put_family(
            self.cams_b,
            self.pollen_b,
            previous=(self.cams_a, self.pollen_a),
            revision=2,
        )

        self.assertEqual(canonical_json_bytes(latest_a), reader.get(FAMILY_LATEST_KEY).body)
        for provider, old_document, rejected_document in (
            (CAMS_PROVIDER, self.cams_a, self.cams_b),
            (CAMS_POLLEN_PROVIDER, self.pollen_a, self.pollen_b),
        ):
            self.assertEqual(
                BODY,
                reader.get(object_key(provider, old_document, self.istat_code)).body,
            )
            with self.assertRaises(ObjectNotFound):
                reader.get(object_key(provider, rejected_document, self.istat_code))
            self.assertEqual("retained", reader.provider_statuses[provider]["status"])

    def test_cams_allow_list_contains_only_current_and_previous_release(self):
        self.use_memory_store()
        for provider, documents in (
            (CAMS_PROVIDER, (self.cams_a, self.cams_b, self.cams_c)),
            (CAMS_POLLEN_PROVIDER, (self.pollen_a, self.pollen_b, self.pollen_c)),
        ):
            for document in documents:
                self.put_run(provider, document)
        release_a, _latest_a = self.put_family(self.cams_a, self.pollen_a)
        reader = self.reader()

        release_b, _latest_b = self.put_family(
            self.cams_b,
            self.pollen_b,
            previous=(self.cams_a, self.pollen_a),
            revision=2,
        )
        reader.get(FAMILY_LATEST_KEY)
        for provider, document in (
            (CAMS_PROVIDER, self.cams_a),
            (CAMS_POLLEN_PROVIDER, self.pollen_a),
        ):
            self.assertEqual(BODY, reader.get(
                object_key(provider, document, self.istat_code)
            ).body)

        _release_c, latest_c = self.put_family(
            self.cams_c,
            self.pollen_c,
            previous=(self.cams_b, self.pollen_b),
            revision=3,
        )
        self.assertEqual(canonical_json_bytes(latest_c), reader.get(FAMILY_LATEST_KEY).body)
        with self.assertRaises(ObjectNotFound):
            reader.get(family_release_key(release_a))
        self.assertEqual(canonical_json_bytes(release_b), reader.get(
            family_release_key(release_b)
        ).body)
        for provider, old_document, previous_document, current_document in (
            (CAMS_PROVIDER, self.cams_a, self.cams_b, self.cams_c),
            (
                CAMS_POLLEN_PROVIDER,
                self.pollen_a,
                self.pollen_b,
                self.pollen_c,
            ),
        ):
            with self.assertRaises(ObjectNotFound):
                reader.get(object_key(provider, old_document, self.istat_code))
            self.assertEqual(BODY, reader.get(
                object_key(provider, previous_document, self.istat_code)
            ).body)
            self.assertEqual(BODY, reader.get(
                object_key(provider, current_document, self.istat_code)
            ).body)

    def test_cams_family_disabled_runs_are_exact_canonical_and_not_visible(self):
        third_run_id = self.cams_c["source_run_id"]
        older_run_id = "20260831T000000Z"
        cases = {
            "missing": None,
            "duplicate": [third_run_id, third_run_id],
            "unsorted": [third_run_id, older_run_id],
            "current": [self.cams_b["source_run_id"]],
            "previous": [self.cams_a["source_run_id"]],
        }
        for label, disabled in cases.items():
            with self.subTest(label=label):
                self.use_memory_store()
                for provider, documents in (
                    (CAMS_PROVIDER, (self.cams_a, self.cams_b)),
                    (CAMS_POLLEN_PROVIDER, (self.pollen_a, self.pollen_b)),
                ):
                    for document in documents:
                        self.put_run(provider, document)
                release_a, latest_a = self.put_family(self.cams_a, self.pollen_a)
                reader = self.reader()
                release_b = family_release(self.cams_b, self.pollen_b, self.catalog)
                self.put_family_release(release_b)
                rejected = family_latest(
                    release_b,
                    self.catalog,
                    previous=release_a,
                    revision=2,
                    disabled=() if disabled is None else disabled,
                )
                if disabled is None:
                    del rejected["disabled_run_ids"]
                self.put_family_latest(rejected)

                self.assertEqual(
                    canonical_json_bytes(latest_a),
                    reader.get(FAMILY_LATEST_KEY).body,
                )
                for provider in (CAMS_PROVIDER, CAMS_POLLEN_PROVIDER):
                    self.assertEqual(
                        "retained",
                        reader.provider_statuses[provider]["status"],
                    )

    def test_cams_family_rollback_switches_both_members_and_removes_revoked_keys(self):
        self.use_memory_store()
        for provider, documents in (
            (CAMS_PROVIDER, (self.cams_a, self.cams_b)),
            (CAMS_POLLEN_PROVIDER, (self.pollen_a, self.pollen_b)),
        ):
            for document in documents:
                self.put_run(provider, document)
        release_b, _latest_b = self.put_family(
            self.cams_b,
            self.pollen_b,
            previous=(self.cams_a, self.pollen_a),
            revision=2,
        )
        release_a = family_release(self.cams_a, self.pollen_a, self.catalog)
        reader = self.reader()

        rollback = family_latest(
            release_a,
            self.catalog,
            revision=3,
            published_at="2026-09-04T13:00:00Z",
            disabled=(self.cams_b["source_run_id"],),
        )
        self.put_family_latest(rollback)

        self.assertEqual(
            canonical_json_bytes(rollback),
            reader.get(FAMILY_LATEST_KEY).body,
        )
        for provider, restored, revoked in (
            (CAMS_PROVIDER, self.cams_a, self.cams_b),
            (CAMS_POLLEN_PROVIDER, self.pollen_a, self.pollen_b),
        ):
            self.assertEqual(
                BODY,
                reader.get(object_key(provider, restored, self.istat_code)).body,
            )
            for revoked_key in (
                manifest_key(provider, revoked),
                object_key(provider, revoked, self.istat_code),
            ):
                with self.assertRaises(ObjectNotFound):
                    reader.get(revoked_key)
        with self.assertRaises(ObjectNotFound):
            reader.get(family_release_key(release_b))

        reactivated = family_latest(
            release_b,
            self.catalog,
            revision=4,
            published_at="2026-09-04T14:00:00Z",
        )
        self.put_family_latest(reactivated)
        self.assertEqual(
            canonical_json_bytes(rollback),
            reader.get(FAMILY_LATEST_KEY).body,
        )
        with self.assertRaises(ObjectNotFound):
            reader.get(object_key(CAMS_PROVIDER, self.cams_b, self.istat_code))

    def test_cams_family_can_revoke_previous_without_changing_active_pair(self):
        self.use_memory_store()
        for provider, documents in (
            (CAMS_PROVIDER, (self.cams_a, self.cams_b)),
            (CAMS_POLLEN_PROVIDER, (self.pollen_a, self.pollen_b)),
        ):
            for document in documents:
                self.put_run(provider, document)
        release_b, _latest_b = self.put_family(
            self.cams_b,
            self.pollen_b,
            previous=(self.cams_a, self.pollen_a),
            revision=2,
        )
        reader = self.reader()
        revoked_previous = family_latest(
            release_b,
            self.catalog,
            revision=3,
            published_at="2026-09-04T13:00:00Z",
            disabled=(self.cams_a["source_run_id"],),
        )
        self.put_family_latest(revoked_previous)

        self.assertEqual(
            canonical_json_bytes(revoked_previous),
            reader.get(FAMILY_LATEST_KEY).body,
        )
        for provider, active, revoked in (
            (CAMS_PROVIDER, self.cams_b, self.cams_a),
            (CAMS_POLLEN_PROVIDER, self.pollen_b, self.pollen_a),
        ):
            self.assertEqual(
                BODY,
                reader.get(object_key(provider, active, self.istat_code)).body,
            )
            with self.assertRaises(ObjectNotFound):
                reader.get(object_key(provider, revoked, self.istat_code))

        no_new_tombstone = family_latest(
            release_b,
            self.catalog,
            revision=4,
            published_at="2026-09-04T14:00:00Z",
            disabled=(self.cams_a["source_run_id"],),
        )
        self.put_family_latest(no_new_tombstone)
        self.assertEqual(
            canonical_json_bytes(revoked_previous),
            reader.get(FAMILY_LATEST_KEY).body,
        )

    def test_valid_rollback_pointer_with_invalid_target_clears_cached_family(self):
        self.use_memory_store()
        for provider, documents in (
            (CAMS_PROVIDER, (self.cams_a, self.cams_b)),
            (CAMS_POLLEN_PROVIDER, (self.pollen_a, self.pollen_b)),
        ):
            for document in documents:
                self.put_run(provider, document)
        self.put_family(
            self.cams_b,
            self.pollen_b,
            previous=(self.cams_a, self.pollen_a),
            revision=2,
        )
        reader = self.reader()
        release_a = family_release(self.cams_a, self.pollen_a, self.catalog)
        missing_key = object_key(
            CAMS_PROVIDER,
            self.cams_a,
            self.catalog.istat_codes[-1],
        )
        del self.writer.objects[missing_key]
        del self.writer.generations[missing_key]
        rollback = family_latest(
            release_a,
            self.catalog,
            revision=3,
            published_at="2026-09-04T13:00:00Z",
            disabled=(self.cams_b["source_run_id"],),
        )
        self.put_family_latest(rollback)

        with self.assertRaises(ObjectNotFound):
            reader.get(FAMILY_LATEST_KEY)
        for provider in (CAMS_PROVIDER, CAMS_POLLEN_PROVIDER):
            self.assertEqual(
                "unavailable",
                reader.provider_statuses[provider]["status"],
            )
            with self.assertRaises(ObjectNotFound):
                reader.get(
                    object_key(
                        provider,
                        self.cams_b if provider == CAMS_PROVIDER else self.pollen_b,
                        self.istat_code,
                    )
                )

    def test_invalid_refresh_after_previous_revocation_retains_only_active_pair(self):
        self.use_memory_store()
        for provider, documents in (
            (CAMS_PROVIDER, (self.cams_a, self.cams_b)),
            (CAMS_POLLEN_PROVIDER, (self.pollen_a, self.pollen_b)),
        ):
            for document in documents:
                self.put_run(provider, document)
        release_b, _latest_b = self.put_family(
            self.cams_b,
            self.pollen_b,
            previous=(self.cams_a, self.pollen_a),
            revision=2,
        )
        release_a = family_release(self.cams_a, self.pollen_a, self.catalog)
        reader = self.reader()
        missing_key = object_key(
            CAMS_PROVIDER,
            self.cams_b,
            self.catalog.istat_codes[-1],
        )
        del self.writer.objects[missing_key]
        del self.writer.generations[missing_key]
        revoked_previous = family_latest(
            release_b,
            self.catalog,
            revision=3,
            published_at="2026-09-04T13:00:00Z",
            disabled=(self.cams_a["source_run_id"],),
        )
        self.put_family_latest(revoked_previous)

        self.assertEqual(
            canonical_json_bytes(revoked_previous),
            reader.get(FAMILY_LATEST_KEY).body,
        )
        for provider, active, revoked in (
            (CAMS_PROVIDER, self.cams_b, self.cams_a),
            (CAMS_POLLEN_PROVIDER, self.pollen_b, self.pollen_a),
        ):
            self.assertEqual(
                BODY,
                reader.get(object_key(provider, active, self.istat_code)).body,
            )
            for revoked_key in (
                manifest_key(provider, revoked),
                object_key(provider, revoked, self.istat_code),
            ):
                with self.assertRaises(ObjectNotFound):
                    reader.get(revoked_key)
            self.assertEqual(
                "retained",
                reader.provider_statuses[provider]["status"],
            )
        with self.assertRaises(ObjectNotFound):
            reader.get(family_release_key(release_a))

    def test_revision_gap_with_invalid_forward_target_applies_cached_tombstones(self):
        self.use_memory_store()
        for provider, documents in (
            (CAMS_PROVIDER, (self.cams_a, self.cams_b, self.cams_c)),
            (CAMS_POLLEN_PROVIDER, (self.pollen_a, self.pollen_b, self.pollen_c)),
        ):
            for document in documents:
                self.put_run(provider, document)
        release_b, _latest_b = self.put_family(
            self.cams_b,
            self.pollen_b,
            previous=(self.cams_a, self.pollen_a),
            revision=2,
        )
        reader = self.reader()

        missing_key = object_key(
            CAMS_PROVIDER,
            self.cams_c,
            self.catalog.istat_codes[-1],
        )
        del self.writer.objects[missing_key]
        del self.writer.generations[missing_key]
        release_c = family_release(self.cams_c, self.pollen_c, self.catalog)
        self.put_family_release(release_c)
        skipped_revocation = family_latest(
            release_c,
            self.catalog,
            previous=release_b,
            revision=4,
            published_at="2026-09-04T14:00:00Z",
            disabled=(self.cams_a["source_run_id"],),
        )
        self.put_family_latest(skipped_revocation)

        with self.assertRaises(ObjectNotFound):
            reader.get(FAMILY_LATEST_KEY)
        for provider, cached_active, revoked_previous in (
            (CAMS_PROVIDER, self.cams_b, self.cams_a),
            (CAMS_POLLEN_PROVIDER, self.pollen_b, self.pollen_a),
        ):
            self.assertEqual(
                "unavailable",
                reader.provider_statuses[provider]["status"],
            )
            for document in (cached_active, revoked_previous):
                with self.assertRaises(ObjectNotFound):
                    reader.get(object_key(provider, document, self.istat_code))

    def test_cams_family_rollback_requires_cached_previous_and_no_older_fallback(self):
        cases = ("wrong_target", "older_fallback")
        for case in cases:
            with self.subTest(case=case):
                self.use_memory_store()
                for provider, documents in (
                    (CAMS_PROVIDER, (self.cams_a, self.cams_b, self.cams_c)),
                    (
                        CAMS_POLLEN_PROVIDER,
                        (self.pollen_a, self.pollen_b, self.pollen_c),
                    ),
                ):
                    for document in documents:
                        self.put_run(provider, document)
                release_c, latest_c = self.put_family(
                    self.cams_c,
                    self.pollen_c,
                    previous=(self.cams_b, self.pollen_b),
                    revision=3,
                )
                reader = self.reader()
                release_a = family_release(self.cams_a, self.pollen_a, self.catalog)
                release_b = family_release(self.cams_b, self.pollen_b, self.catalog)
                self.put_family_release(release_a)
                rejected = family_latest(
                    release_a if case == "wrong_target" else release_b,
                    self.catalog,
                    previous=(None if case == "wrong_target" else release_a),
                    revision=4,
                    published_at="2026-09-04T14:00:00Z",
                    disabled=(self.cams_c["source_run_id"],),
                )
                self.put_family_latest(rejected)

                self.assertEqual(
                    canonical_json_bytes(latest_c),
                    reader.get(FAMILY_LATEST_KEY).body,
                )
                for provider, active in (
                    (CAMS_PROVIDER, self.cams_c),
                    (CAMS_POLLEN_PROVIDER, self.pollen_c),
                ):
                    self.assertEqual(
                        BODY,
                        reader.get(object_key(provider, active, self.istat_code)).body,
                    )
                    self.assertEqual(
                        "retained",
                        reader.provider_statuses[provider]["status"],
                    )
                self.assertEqual(
                    canonical_json_bytes(release_c),
                    reader.get(family_release_key(release_c)).body,
                )

    def test_consecutive_forward_cannot_inject_a_later_rollback_target(self):
        self.use_memory_store()
        for provider, documents in (
            (
                CAMS_PROVIDER,
                (self.cams_x, self.cams_a, self.cams_b, self.cams_c),
            ),
            (
                CAMS_POLLEN_PROVIDER,
                (self.pollen_x, self.pollen_a, self.pollen_b, self.pollen_c),
            ),
        ):
            for document in documents:
                self.put_run(provider, document)
        _release_b, latest_b = self.put_family(
            self.cams_b,
            self.pollen_b,
            previous=(self.cams_a, self.pollen_a),
            revision=2,
        )
        reader = self.reader()
        release_c = family_release(self.cams_c, self.pollen_c, self.catalog)
        release_x = family_release(self.cams_x, self.pollen_x, self.catalog)
        self.put_family_release(release_c)
        self.put_family_release(release_x)

        injected_previous = family_latest(
            release_c,
            self.catalog,
            previous=release_x,
            revision=3,
            published_at="2026-09-04T13:00:00Z",
        )
        self.put_family_latest(injected_previous)
        self.assertEqual(
            canonical_json_bytes(latest_b),
            reader.get(FAMILY_LATEST_KEY).body,
        )

        rollback_to_injected = family_latest(
            release_x,
            self.catalog,
            revision=4,
            published_at="2026-09-04T14:00:00Z",
            disabled=(self.cams_c["source_run_id"],),
        )
        self.put_family_latest(rollback_to_injected)
        self.assertEqual(
            canonical_json_bytes(latest_b),
            reader.get(FAMILY_LATEST_KEY).body,
        )
        for provider, injected in (
            (CAMS_PROVIDER, self.cams_x),
            (CAMS_POLLEN_PROVIDER, self.pollen_x),
        ):
            with self.assertRaises(ObjectNotFound):
                reader.get(object_key(provider, injected, self.istat_code))
            self.assertEqual(
                "retained",
                reader.provider_statuses[provider]["status"],
            )

    def test_consecutive_family_updates_require_exact_tombstones(self):
        self.use_memory_store()
        for provider, documents in (
            (
                CAMS_PROVIDER,
                (self.cams_x, self.cams_a, self.cams_b, self.cams_c),
            ),
            (
                CAMS_POLLEN_PROVIDER,
                (self.pollen_x, self.pollen_a, self.pollen_b, self.pollen_c),
            ),
        ):
            for document in documents:
                self.put_run(provider, document)
        release_b, latest_b = self.put_family(
            self.cams_b,
            self.pollen_b,
            previous=(self.cams_a, self.pollen_a),
            revision=2,
        )
        reader = self.reader()
        release_a = family_release(self.cams_a, self.pollen_a, self.catalog)
        release_c = family_release(self.cams_c, self.pollen_c, self.catalog)
        self.put_family_release(release_c)
        x_run_id = self.cams_x["source_run_id"]
        b_run_id = self.cams_b["source_run_id"]
        cases = (
            (
                "forward_with_tombstone",
                family_latest(
                    release_c,
                    self.catalog,
                    previous=release_b,
                    revision=3,
                    published_at="2026-09-04T13:00:00Z",
                    disabled=(x_run_id,),
                ),
            ),
            (
                "same_active_wrong_tombstone",
                family_latest(
                    release_b,
                    self.catalog,
                    revision=3,
                    published_at="2026-09-04T13:00:00Z",
                    disabled=(x_run_id,),
                ),
            ),
            (
                "rollback_with_extra_tombstone",
                family_latest(
                    release_a,
                    self.catalog,
                    revision=3,
                    published_at="2026-09-04T13:00:00Z",
                    disabled=(x_run_id, b_run_id),
                ),
            ),
        )
        for label, rejected in cases:
            with self.subTest(label=label):
                self.put_family_latest(rejected)
                self.assertEqual(
                    canonical_json_bytes(latest_b),
                    reader.get(FAMILY_LATEST_KEY).body,
                )
                for provider in (CAMS_PROVIDER, CAMS_POLLEN_PROVIDER):
                    self.assertEqual(
                        "retained",
                        reader.provider_statuses[provider]["status"],
                    )

    def test_skipped_same_active_transition_requires_previous_to_be_absent(self):
        for label, candidate_previous, accepted in (
            ("coherent_skipped_rollback", None, True),
            ("injected_previous", "x", False),
        ):
            with self.subTest(label=label):
                self.use_memory_store()
                for provider, documents in (
                    (CAMS_PROVIDER, (self.cams_x, self.cams_a, self.cams_b)),
                    (
                        CAMS_POLLEN_PROVIDER,
                        (self.pollen_x, self.pollen_a, self.pollen_b),
                    ),
                ):
                    for document in documents:
                        self.put_run(provider, document)
                release_b, latest_b = self.put_family(
                    self.cams_b,
                    self.pollen_b,
                    previous=(self.cams_a, self.pollen_a),
                    revision=2,
                )
                reader = self.reader()
                release_x = family_release(
                    self.cams_x,
                    self.pollen_x,
                    self.catalog,
                )
                self.put_family_release(release_x)
                skipped = family_latest(
                    release_b,
                    self.catalog,
                    previous=(
                        None if candidate_previous is None else release_x
                    ),
                    revision=4,
                    published_at="2026-09-04T14:00:00Z",
                    disabled=(self.cams_c["source_run_id"],),
                )
                self.put_family_latest(skipped)

                expected = skipped if accepted else latest_b
                self.assertEqual(
                    canonical_json_bytes(expected),
                    reader.get(FAMILY_LATEST_KEY).body,
                )
                expected_status = "verified" if accepted else "retained"
                for provider in (CAMS_PROVIDER, CAMS_POLLEN_PROVIDER):
                    self.assertEqual(
                        expected_status,
                        reader.provider_statuses[provider]["status"],
                    )

    def test_skipped_forward_transition_has_only_reachable_previous_states(self):
        cases = (
            ("cached_previous_after_rollback", "a", True, True),
            ("no_previous_after_revocation", None, True, True),
            ("arbitrary_older_previous", "x", True, False),
            ("no_previous_without_active_tombstone", None, False, False),
        )
        for label, previous_name, tombstone_active, accepted in cases:
            with self.subTest(label=label):
                self.use_memory_store()
                for provider, documents in (
                    (
                        CAMS_PROVIDER,
                        (self.cams_x, self.cams_a, self.cams_b, self.cams_c),
                    ),
                    (
                        CAMS_POLLEN_PROVIDER,
                        (
                            self.pollen_x,
                            self.pollen_a,
                            self.pollen_b,
                            self.pollen_c,
                        ),
                    ),
                ):
                    for document in documents:
                        self.put_run(provider, document)
                _release_b, latest_b = self.put_family(
                    self.cams_b,
                    self.pollen_b,
                    previous=(self.cams_a, self.pollen_a),
                    revision=2,
                )
                reader = self.reader()
                release_c = family_release(
                    self.cams_c,
                    self.pollen_c,
                    self.catalog,
                )
                release_x = family_release(
                    self.cams_x,
                    self.pollen_x,
                    self.catalog,
                )
                self.put_family_release(release_c)
                self.put_family_release(release_x)
                previous_release = {
                    None: None,
                    "a": family_release(
                        self.cams_a,
                        self.pollen_a,
                        self.catalog,
                    ),
                    "x": release_x,
                }[previous_name]
                skipped = family_latest(
                    release_c,
                    self.catalog,
                    previous=previous_release,
                    revision=4,
                    published_at="2026-09-04T14:00:00Z",
                    disabled=(
                        (self.cams_b["source_run_id"],)
                        if tombstone_active
                        else ()
                    ),
                )
                self.put_family_latest(skipped)

                expected = skipped if accepted else latest_b
                self.assertEqual(
                    canonical_json_bytes(expected),
                    reader.get(FAMILY_LATEST_KEY).body,
                )
                expected_status = "verified" if accepted else "retained"
                for provider in (CAMS_PROVIDER, CAMS_POLLEN_PROVIDER):
                    self.assertEqual(
                        expected_status,
                        reader.provider_statuses[provider]["status"],
                    )

    def test_cams_family_pointer_change_during_scan_retries_as_one_pair(self):
        self.use_memory_store()
        for provider, documents in (
            (CAMS_PROVIDER, (self.cams_a, self.cams_b)),
            (CAMS_POLLEN_PROVIDER, (self.pollen_a, self.pollen_b)),
        ):
            for document in documents:
                self.put_run(provider, document)
        self.put_family(self.cams_a, self.pollen_a)
        release_b = family_release(self.cams_b, self.pollen_b, self.catalog)
        self.put_family_release(release_b)
        latest_b = family_latest(release_b, self.catalog, revision=2)
        switching = SwitchingReader(
            self.writer,
            lambda: self.put_family_latest(latest_b),
        )

        reader = PublishedRunsObjectReader(
            switching,
            self.catalog,
            providers=(CAMS_PROVIDER, CAMS_POLLEN_PROVIDER),
        )

        self.assertTrue(switching.switched)
        self.assertEqual(canonical_json_bytes(latest_b), reader.get(FAMILY_LATEST_KEY).body)
        for provider, document in (
            (CAMS_PROVIDER, self.cams_b),
            (CAMS_POLLEN_PROVIDER, self.pollen_b),
        ):
            self.assertEqual(BODY, reader.get(
                object_key(provider, document, self.istat_code)
            ).body)

    def test_cams_family_regressions_retain_both_members(self):
        self.use_memory_store()
        for provider, documents in (
            (CAMS_PROVIDER, (self.cams_a, self.cams_b)),
            (CAMS_POLLEN_PROVIDER, (self.pollen_a, self.pollen_b)),
        ):
            for document in documents:
                self.put_run(provider, document)
        _release_a, latest_a = self.put_family(self.cams_a, self.pollen_a)
        reader = self.reader()

        self.put_family(
            self.cams_b,
            self.pollen_b,
            previous=(self.cams_a, self.pollen_a),
            revision=1,
        )
        self.assertEqual(canonical_json_bytes(latest_a), reader.get(FAMILY_LATEST_KEY).body)
        for provider in (CAMS_PROVIDER, CAMS_POLLEN_PROVIDER):
            self.assertEqual("retained", reader.provider_statuses[provider]["status"])

    def test_cams_family_run_and_publication_time_cannot_regress(self):
        for regression in ("run", "published_at"):
            with self.subTest(regression=regression):
                self.use_memory_store()
                for provider, documents in (
                    (CAMS_PROVIDER, (self.cams_a, self.cams_b)),
                    (CAMS_POLLEN_PROVIDER, (self.pollen_a, self.pollen_b)),
                ):
                    for document in documents:
                        self.put_run(provider, document)

                if regression == "run":
                    active_release = family_release(
                        self.cams_b,
                        self.pollen_b,
                        self.catalog,
                    )
                    rejected_release = family_release(
                        self.cams_a,
                        self.pollen_a,
                        self.catalog,
                    )
                else:
                    active_release = family_release(
                        self.cams_a,
                        self.pollen_a,
                        self.catalog,
                        published_at="2026-09-04T13:00:00Z",
                    )
                    rejected_release = family_release(
                        self.cams_b,
                        self.pollen_b,
                        self.catalog,
                        published_at="2026-09-04T12:00:00Z",
                    )
                self.put_family_release(active_release)
                active_latest = family_latest(active_release, self.catalog)
                self.put_family_latest(active_latest)
                reader = self.reader()

                self.put_family_release(rejected_release)
                rejected_latest = family_latest(
                    rejected_release,
                    self.catalog,
                    previous=(active_release if regression == "published_at" else None),
                    revision=2,
                )
                self.put_family_latest(rejected_latest)

                self.assertEqual(
                    canonical_json_bytes(active_latest),
                    reader.get(FAMILY_LATEST_KEY).body,
                )
                for provider in (CAMS_PROVIDER, CAMS_POLLEN_PROVIDER):
                    self.assertEqual(
                        "retained",
                        reader.provider_statuses[provider]["status"],
                    )

    def test_single_selected_cams_provider_still_requires_both_members(self):
        self.use_memory_store()
        self.put_run(CAMS_PROVIDER, self.cams_a)
        self.put_run(
            CAMS_POLLEN_PROVIDER,
            self.pollen_a,
            omit_istat_codes=(self.catalog.istat_codes[-1],),
        )
        self.put_family(self.cams_a, self.pollen_a)
        with self.assertRaisesRegex(PublishedRunsReaderError, "no verified"):
            PublishedRunsObjectReader(
                self.writer,
                self.catalog,
                providers=(CAMS_PROVIDER,),
            )

    def test_startup_fails_when_no_provider_has_a_verified_latest(self):
        with self.assertRaisesRegex(PublishedRunsReaderError, "no verified"):
            self.reader()

    def test_incomplete_run_is_not_made_visible(self):
        missing = self.catalog.istat_codes[-1]
        self.put_run(
            ICON_PROVIDER,
            self.icon_a,
            omit_istat_codes=(missing,),
        )
        self.put_latest(ICON_PROVIDER, self.latest(ICON_PROVIDER, self.icon_a))
        with self.assertRaisesRegex(PublishedRunsReaderError, "no verified"):
            self.reader()

    def test_payload_must_match_before_the_run_is_made_visible(self):
        self.put_run(
            ICON_PROVIDER,
            self.icon_a,
            object_body=b'{"tampered":true}',
        )
        self.put_latest(ICON_PROVIDER, self.latest(ICON_PROVIDER, self.icon_a))
        with self.assertRaisesRegex(PublishedRunsReaderError, "no verified"):
            self.reader()


if __name__ == "__main__":
    unittest.main()
