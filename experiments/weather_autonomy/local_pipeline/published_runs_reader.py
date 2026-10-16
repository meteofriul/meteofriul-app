"""Read only contract-v1 runs referenced by a verified ``latest`` pointer.

Immutable objects may be uploaded before the final compare-and-swap.  They are
not public until ``latest`` references their complete manifest.  This adapter
enforces that distinction for the local HTTP data plane and normally retains
the last verified snapshot if a concurrent or corrupt pointer cannot be
validated. A schema-valid revocation pointer never leaves its disabled active
or previous run available through that retained view.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import hashlib
import json
import re
from threading import RLock
from types import MappingProxyType
from typing import Any, Iterable, Mapping

from .contract_v1 import (
    CAMS_POLLEN_PROVIDER,
    CAMS_PROVIDER,
    PROVIDERS,
    Catalog,
    ContractError,
    canonical_json_bytes,
    validate_latest_document,
    validate_run_manifest,
)
from .object_store_ports import ObjectReader
from .sqlite_object_store import ObjectHead, ObjectNotFound, ObjectStoreError, StoredObject


class PublishedRunsReaderError(ObjectStoreError):
    """No safe published view can be constructed from the object store."""


@dataclass(frozen=True)
class _ProviderSnapshot:
    provider: str
    latest: StoredObject
    revision: int
    active_run_id: str
    allowed_keys: frozenset[str]
    disabled_run_ids: frozenset[str]
    pinned_objects: Mapping[str, StoredObject]
    payload_descriptors: Mapping[str, tuple[int, str]]


@dataclass(frozen=True)
class _CamsFamilySnapshot:
    latest: StoredObject
    revision: int
    active_run_id: str
    previous_run_id: str | None
    published_at: str
    disabled_run_ids: frozenset[str]
    allowed_keys: frozenset[str]
    pinned_objects: Mapping[str, StoredObject]
    payload_descriptors: Mapping[str, tuple[int, str]]


@dataclass(frozen=True)
class _CamsFamilyPointer:
    """Stable, schema-valid pointer read before its targets are verified."""

    latest: StoredObject
    revision: int
    active_run_id: str
    active_descriptor: Mapping[str, Any]
    previous_run_id: str | None
    published_at: str
    disabled_run_ids: frozenset[str]


class _CamsFamilyTargetVerificationError(PublishedRunsReaderError):
    """A valid pointer was observed, but its referenced family was not usable."""

    def __init__(self, pointer: _CamsFamilyPointer) -> None:
        super().__init__("published CAMS family target verification failed")
        self.pointer = pointer


def _validate_cams_family_transition(
    previous: _CamsFamilySnapshot,
    candidate: _CamsFamilySnapshot | _CamsFamilyPointer,
) -> None:
    """Accept only monotonic forward moves or explicit family revocations."""

    if candidate.revision <= previous.revision:
        raise PublishedRunsReaderError(
            "published CAMS family revision did not advance"
        )
    if candidate.published_at < previous.published_at:
        raise PublishedRunsReaderError(
            "published CAMS family publication time regressed"
        )
    if not previous.disabled_run_ids.issubset(candidate.disabled_run_ids):
        raise PublishedRunsReaderError(
            "published CAMS family dropped prior revocation evidence"
        )
    revision_gap = candidate.revision - previous.revision
    new_disabled_run_ids = candidate.disabled_run_ids - previous.disabled_run_ids
    if candidate.active_run_id in previous.disabled_run_ids:
        raise PublishedRunsReaderError(
            "published CAMS family attempts to reactivate a disabled run"
        )
    if candidate.active_run_id < previous.active_run_id:
        if previous.active_run_id not in candidate.disabled_run_ids:
            raise PublishedRunsReaderError(
                "published CAMS family regressed without an explicit rollback"
            )
        if candidate.active_run_id != previous.previous_run_id:
            raise PublishedRunsReaderError(
                "published CAMS family rollback did not target the cached previous release"
            )
        if candidate.previous_run_id is not None:
            raise PublishedRunsReaderError(
                "published CAMS family rollback retained an older fallback"
            )
        if (
            revision_gap == 1
            and new_disabled_run_ids != {previous.active_run_id}
        ):
            raise PublishedRunsReaderError(
                "published CAMS family consecutive rollback has inexact tombstones"
            )
    elif candidate.active_run_id == previous.active_run_id:
        if candidate.previous_run_id is not None:
            raise PublishedRunsReaderError(
                "published CAMS family same-run revocation retained a fallback"
            )
        if not new_disabled_run_ids:
            raise PublishedRunsReaderError(
                "published CAMS family run did not advance or revoke a release"
            )
        if (
            revision_gap == 1
            and (
                previous.previous_run_id is None
                or new_disabled_run_ids != {previous.previous_run_id}
            )
        ):
            raise PublishedRunsReaderError(
                "published CAMS family consecutive revocation did not remove its previous release"
            )
    elif revision_gap == 1:
        if (
            candidate.previous_run_id != previous.active_run_id
            or new_disabled_run_ids
        ):
            raise PublishedRunsReaderError(
                "published CAMS family consecutive publication has an invalid previous release"
            )
    elif candidate.previous_run_id is None:
        if previous.active_run_id not in candidate.disabled_run_ids:
            raise PublishedRunsReaderError(
                "published CAMS family skipped publication dropped the cached active release"
            )
    elif candidate.previous_run_id < previous.active_run_id:
        if (
            candidate.previous_run_id != previous.previous_run_id
            or previous.active_run_id not in candidate.disabled_run_ids
        ):
            raise PublishedRunsReaderError(
                "published CAMS family skipped publication has an unreachable previous release"
            )


_CAMS_FAMILY = "cams"
_CAMS_FAMILY_ROOT = f"weather/v1/families/{_CAMS_FAMILY}"
_CAMS_FAMILY_LATEST_KEY = f"{_CAMS_FAMILY_ROOT}/latest.json"
_CAMS_FAMILY_RELEASE_KIND = "meteofriul.weather.cams_family_release"
_CAMS_FAMILY_LATEST_KIND = "meteofriul.weather.cams_family_latest"
_CAMS_FAMILY_COMPONENTS = {
    "core": CAMS_PROVIDER,
    "pollen": CAMS_POLLEN_PROVIDER,
}
_CAMS_PROVIDERS = frozenset(_CAMS_FAMILY_COMPONENTS.values())
_RUN_ID = re.compile(r"^\d{8}T\d{6}Z$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


def _provider_root(provider: str) -> str:
    return f"weather/v1/{provider}"


def _latest_key(provider: str) -> str:
    return f"{_provider_root(provider)}/latest.json"


def _cams_family_release_key(source_run_id: str) -> str:
    return f"{_CAMS_FAMILY_ROOT}/runs/{source_run_id}/release.json"


def _key_run_id(key: str) -> str | None:
    segments = key.split("/")
    if len(segments) >= 5 and segments[3] == "runs":
        return segments[4]
    if (
        len(segments) >= 7
        and segments[2:5] == ["families", _CAMS_FAMILY, "runs"]
    ):
        return segments[5]
    return None


def _decode_canonical(stored: StoredObject, label: str) -> dict[str, Any]:
    try:
        document = json.loads(stored.body)
    except (UnicodeError, json.JSONDecodeError) as error:
        raise PublishedRunsReaderError(f"{label} is not valid JSON") from error
    if not isinstance(document, dict):
        raise PublishedRunsReaderError(f"{label} is not a JSON object")
    try:
        canonical = canonical_json_bytes(document)
    except ContractError as error:
        raise PublishedRunsReaderError(f"{label} is not canonical JSON data") from error
    if canonical != stored.body:
        raise PublishedRunsReaderError(f"{label} bytes are not canonical JSON")
    return document


def _exact_mapping(value: Any, expected: set[str], label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping) or set(value) != expected:
        raise PublishedRunsReaderError(f"{label} has missing or extra fields")
    return value


def _positive_integer(value: Any, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise PublishedRunsReaderError(f"{label} must be a positive integer")
    return value


def _sha256_value(value: Any, label: str) -> str:
    if not isinstance(value, str) or not _SHA256.fullmatch(value):
        raise PublishedRunsReaderError(f"{label} is not lowercase SHA-256")
    return value


def _publication_time(value: Any, label: str) -> str:
    if not isinstance(value, str):
        raise PublishedRunsReaderError(f"{label} is not a UTC timestamp")
    try:
        parsed = datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError as error:
        raise PublishedRunsReaderError(f"{label} is not a UTC timestamp") from error
    if parsed.strftime("%Y-%m-%dT%H:%M:%SZ") != value:
        raise PublishedRunsReaderError(f"{label} is not a canonical UTC timestamp")
    return value


def _validate_cams_release_descriptor(value: Any) -> Mapping[str, Any]:
    descriptor = _exact_mapping(
        value,
        {
            "source_run_id",
            "release_path",
            "release_json_bytes",
            "release_sha256",
        },
        "CAMS family release descriptor",
    )
    source_run_id = descriptor["source_run_id"]
    if (
        not isinstance(source_run_id, str)
        or not _RUN_ID.fullmatch(source_run_id)
        or descriptor["release_path"] != f"runs/{source_run_id}/release.json"
    ):
        raise PublishedRunsReaderError("CAMS family release identity is invalid")
    _positive_integer(descriptor["release_json_bytes"], "CAMS family release bytes")
    _sha256_value(descriptor["release_sha256"], "CAMS family release SHA-256")
    return descriptor


def _validate_cams_family_latest(
    value: Any,
    catalog: Catalog,
) -> Mapping[str, Any]:
    latest = _exact_mapping(
        value,
        {
            "schema_version",
            "kind",
            "family",
            "revision",
            "published_at",
            "catalog",
            "latest",
            "previous",
            "disabled_run_ids",
        },
        "CAMS family latest",
    )
    if (
        type(latest["schema_version"]) is not int
        or latest["schema_version"] != 1
        or latest["kind"] != _CAMS_FAMILY_LATEST_KIND
        or latest["family"] != _CAMS_FAMILY
        or latest["catalog"] != catalog.reference()
    ):
        raise PublishedRunsReaderError("CAMS family latest identity is invalid")
    _positive_integer(latest["revision"], "CAMS family latest revision")
    _publication_time(latest["published_at"], "CAMS family latest publication time")
    current = _validate_cams_release_descriptor(latest["latest"])
    previous = latest["previous"]
    if previous is not None:
        previous = _validate_cams_release_descriptor(previous)
        if previous["source_run_id"] >= current["source_run_id"]:
            raise PublishedRunsReaderError(
                "CAMS family previous release does not precede the active release"
            )
    disabled_run_ids = latest["disabled_run_ids"]
    if (
        not isinstance(disabled_run_ids, list)
        or any(
            not isinstance(run_id, str) or not _RUN_ID.fullmatch(run_id)
            for run_id in disabled_run_ids
        )
        or disabled_run_ids != sorted(set(disabled_run_ids))
    ):
        raise PublishedRunsReaderError(
            "CAMS family disabled runs must be sorted unique canonical run IDs"
        )
    visible_run_ids = {current["source_run_id"]}
    if previous is not None:
        visible_run_ids.add(previous["source_run_id"])
    if visible_run_ids.intersection(disabled_run_ids):
        raise PublishedRunsReaderError(
            "disabled CAMS family releases cannot remain publicly allow-listed"
        )
    return latest


def _validate_cams_component_descriptor(
    value: Any,
    *,
    role: str,
    source_run_id: str,
) -> Mapping[str, Any]:
    descriptor = _exact_mapping(
        value,
        {
            "provider",
            "source_run_id",
            "manifest_key",
            "manifest_json_bytes",
            "manifest_sha256",
        },
        f"CAMS family {role} component",
    )
    provider = _CAMS_FAMILY_COMPONENTS[role]
    expected_key = f"{_provider_root(provider)}/runs/{source_run_id}/manifest.json"
    if (
        descriptor["provider"] != provider
        or descriptor["source_run_id"] != source_run_id
        or descriptor["manifest_key"] != expected_key
    ):
        raise PublishedRunsReaderError(
            f"CAMS family {role} component identity is invalid"
        )
    _positive_integer(
        descriptor["manifest_json_bytes"],
        f"CAMS family {role} manifest bytes",
    )
    _sha256_value(
        descriptor["manifest_sha256"],
        f"CAMS family {role} manifest SHA-256",
    )
    return descriptor


def _validate_cams_family_release(
    value: Any,
    catalog: Catalog,
) -> Mapping[str, Any]:
    release = _exact_mapping(
        value,
        {
            "schema_version",
            "kind",
            "family",
            "source_run_id",
            "published_at",
            "validation_sha256",
            "catalog",
            "components",
        },
        "CAMS family release",
    )
    source_run_id = release["source_run_id"]
    if (
        type(release["schema_version"]) is not int
        or release["schema_version"] != 1
        or release["kind"] != _CAMS_FAMILY_RELEASE_KIND
        or release["family"] != _CAMS_FAMILY
        or not isinstance(source_run_id, str)
        or not _RUN_ID.fullmatch(source_run_id)
        or release["catalog"] != catalog.reference()
    ):
        raise PublishedRunsReaderError("CAMS family release identity is invalid")
    _publication_time(release["published_at"], "CAMS family release publication time")
    _sha256_value(release["validation_sha256"], "CAMS family validation SHA-256")
    components = _exact_mapping(
        release["components"],
        set(_CAMS_FAMILY_COMPONENTS),
        "CAMS family components",
    )
    for role in _CAMS_FAMILY_COMPONENTS:
        _validate_cams_component_descriptor(
            components[role],
            role=role,
            source_run_id=source_run_id,
        )
    return release


class PublishedRunsObjectReader:
    """Expose current/previous verified runs and hide uncommitted objects.

    ICON has its own provider snapshot.  CAMS core and pollen share one family
    snapshot rooted at ``families/cams/latest.json``; neither legacy CAMS
    provider pointer is read.  A new allow-list and its pinned documents are
    swapped together under a lock, so HTTP clients never observe half a CAMS
    release. A failed ordinary refresh keeps serving the previous verified
    view; explicit revocation evidence removes disabled runs fail-closed.
    """

    def __init__(
        self,
        reader: ObjectReader,
        catalog: Catalog,
        *,
        providers: Iterable[str] = PROVIDERS,
        max_refresh_attempts: int = 3,
    ) -> None:
        if not isinstance(reader, ObjectReader):
            raise TypeError("reader must provide head and get")
        if not isinstance(catalog, Catalog):
            raise TypeError("catalog must be a contract-v1 Catalog")
        selected = tuple(sorted(set(providers)))
        if not selected or any(provider not in PROVIDERS for provider in selected):
            raise ValueError("providers must be a non-empty contract-v1 subset")
        if (
            isinstance(max_refresh_attempts, bool)
            or not isinstance(max_refresh_attempts, int)
            or max_refresh_attempts < 1
            or max_refresh_attempts > 16
        ):
            raise ValueError("max_refresh_attempts must be between 1 and 16")
        self._reader = reader
        self._catalog = catalog
        self._providers = selected
        self._max_refresh_attempts = max_refresh_attempts
        self._lock = RLock()
        self._snapshots: dict[str, _ProviderSnapshot] = {}
        self._cams_family_snapshot: _CamsFamilySnapshot | None = None
        self._statuses: dict[str, dict[str, Any]] = {}

        for provider in selected:
            if provider not in _CAMS_PROVIDERS:
                self._refresh(provider, required=False)
        if _CAMS_PROVIDERS.intersection(selected):
            self._refresh_cams_family(required=False)
        if not self._snapshots and self._cams_family_snapshot is None:
            raise PublishedRunsReaderError("no verified published provider is available")

    @property
    def provider_statuses(self) -> Mapping[str, Mapping[str, Any]]:
        with self._lock:
            return MappingProxyType(
                {
                    provider: MappingProxyType(dict(status))
                    for provider, status in self._statuses.items()
                }
            )

    @staticmethod
    def _scope_for_key(key: str) -> str:
        segments = str(key).split("/")
        if len(segments) < 4 or segments[:2] != ["weather", "v1"]:
            raise ObjectNotFound(str(key))
        if len(segments) >= 5 and segments[2:4] == ["families", _CAMS_FAMILY]:
            return _CAMS_FAMILY
        provider = segments[2]
        if provider not in PROVIDERS:
            raise ObjectNotFound(str(key))
        return provider

    def _read_manifest(
        self,
        provider: str,
        descriptor: Mapping[str, Any],
    ) -> tuple[dict[str, Any], StoredObject, str]:
        manifest_path = descriptor["manifest_path"]
        manifest_key = f"{_provider_root(provider)}/{manifest_path}"
        stored = self._reader.get(manifest_key)
        if (
            stored.byte_length != descriptor["manifest_json_bytes"]
            or hashlib.sha256(stored.body).hexdigest() != descriptor["manifest_sha256"]
        ):
            raise PublishedRunsReaderError("published manifest descriptor mismatch")
        document = _decode_canonical(stored, "published manifest")
        try:
            validate_run_manifest(
                document,
                self._catalog,
                expected_provider=provider,
            )
        except ContractError as error:
            raise PublishedRunsReaderError("published manifest is invalid") from error
        if document["source_run_id"] != descriptor["source_run_id"]:
            raise PublishedRunsReaderError("published manifest run identity mismatch")
        return document, stored, manifest_key

    def _read_cams_family_release(
        self,
        descriptor: Mapping[str, Any],
    ) -> tuple[Mapping[str, Any], StoredObject, str]:
        descriptor = _validate_cams_release_descriptor(descriptor)
        release_key = _cams_family_release_key(descriptor["source_run_id"])
        stored = self._reader.get(release_key)
        actual_sha256 = hashlib.sha256(stored.body).hexdigest()
        if (
            stored.key != release_key
            or stored.content_type != "application/json"
            or stored.byte_length != len(stored.body)
            or stored.byte_length != descriptor["release_json_bytes"]
            or stored.sha256 != actual_sha256
            or actual_sha256 != descriptor["release_sha256"]
        ):
            raise PublishedRunsReaderError("CAMS family release descriptor mismatch")
        release = _decode_canonical(stored, "CAMS family release")
        _validate_cams_family_release(release, self._catalog)
        if release["source_run_id"] != descriptor["source_run_id"]:
            raise PublishedRunsReaderError("CAMS family release run identity mismatch")
        return release, stored, release_key

    def _read_cams_component_manifest(
        self,
        release: Mapping[str, Any],
        role: str,
    ) -> tuple[dict[str, Any], StoredObject, str]:
        source_run_id = release["source_run_id"]
        component = _validate_cams_component_descriptor(
            release["components"][role],
            role=role,
            source_run_id=source_run_id,
        )
        provider = _CAMS_FAMILY_COMPONENTS[role]
        manifest_key = component["manifest_key"]
        stored = self._reader.get(manifest_key)
        actual_sha256 = hashlib.sha256(stored.body).hexdigest()
        if (
            stored.key != manifest_key
            or stored.content_type != "application/json"
            or stored.byte_length != len(stored.body)
            or stored.byte_length != component["manifest_json_bytes"]
            or stored.sha256 != actual_sha256
            or actual_sha256 != component["manifest_sha256"]
        ):
            raise PublishedRunsReaderError(
                f"CAMS family {role} manifest descriptor mismatch"
            )
        document = _decode_canonical(stored, f"CAMS family {role} manifest")
        try:
            validate_run_manifest(
                document,
                self._catalog,
                expected_provider=provider,
            )
        except ContractError as error:
            raise PublishedRunsReaderError(
                f"CAMS family {role} manifest is invalid"
            ) from error
        if document["source_run_id"] != source_run_id:
            raise PublishedRunsReaderError(
                f"CAMS family {role} manifest run identity mismatch"
            )
        return document, stored, manifest_key

    def _build_cams_family_snapshot(self) -> _CamsFamilySnapshot:
        last_error: BaseException | None = None
        for _attempt in range(self._max_refresh_attempts):
            pointer: _CamsFamilyPointer | None = None
            try:
                before = self._reader.head(_CAMS_FAMILY_LATEST_KEY)
                latest_stored = self._reader.get(_CAMS_FAMILY_LATEST_KEY)
                if latest_stored.etag != before.etag:
                    continue
                actual_latest_sha256 = hashlib.sha256(latest_stored.body).hexdigest()
                if (
                    latest_stored.key != _CAMS_FAMILY_LATEST_KEY
                    or latest_stored.content_type != "application/json"
                    or latest_stored.byte_length != len(latest_stored.body)
                    or latest_stored.sha256 != actual_latest_sha256
                ):
                    raise PublishedRunsReaderError("CAMS family latest object mismatch")
                latest = _decode_canonical(latest_stored, "CAMS family latest")
                _validate_cams_family_latest(latest, self._catalog)
                previous = latest["previous"]
                pointer = _CamsFamilyPointer(
                    latest=latest_stored,
                    revision=latest["revision"],
                    active_run_id=latest["latest"]["source_run_id"],
                    active_descriptor=MappingProxyType(dict(latest["latest"])),
                    previous_run_id=(
                        None if previous is None else previous["source_run_id"]
                    ),
                    published_at=latest["published_at"],
                    disabled_run_ids=frozenset(latest["disabled_run_ids"]),
                )

                release_records = [
                    self._read_cams_family_release(latest["latest"]),
                ]
                if latest["previous"] is not None:
                    release_records.append(
                        self._read_cams_family_release(latest["previous"])
                    )
                current_release = release_records[0][0]
                if current_release["published_at"] > latest["published_at"]:
                    raise PublishedRunsReaderError(
                        "CAMS family latest predates its active release"
                    )

                allowed = {_CAMS_FAMILY_LATEST_KEY}
                pinned: dict[str, StoredObject] = {
                    _CAMS_FAMILY_LATEST_KEY: latest_stored,
                }
                payload_descriptors: dict[str, tuple[int, str]] = {}
                for release, release_stored, release_key in release_records:
                    allowed.add(release_key)
                    pinned[release_key] = release_stored
                    for role, provider in _CAMS_FAMILY_COMPONENTS.items():
                        manifest, manifest_stored, manifest_key = (
                            self._read_cams_component_manifest(release, role)
                        )
                        allowed.add(manifest_key)
                        pinned[manifest_key] = manifest_stored
                        for descriptor in manifest["objects"].values():
                            object_key = (
                                f"{_provider_root(provider)}/{descriptor['path']}"
                            )
                            head = self._reader.head(object_key)
                            expected = (descriptor["json_bytes"], descriptor["sha256"])
                            if (
                                head.key != object_key
                                or head.content_type != "application/json"
                                or (head.byte_length, head.sha256) != expected
                            ):
                                raise PublishedRunsReaderError(
                                    f"CAMS family {role} payload descriptor mismatch"
                                )
                            allowed.add(object_key)
                            payload_descriptors[object_key] = expected

                after = self._reader.head(_CAMS_FAMILY_LATEST_KEY)
                if after.etag != latest_stored.etag:
                    continue
                return _CamsFamilySnapshot(
                    latest=latest_stored,
                    revision=pointer.revision,
                    active_run_id=pointer.active_run_id,
                    previous_run_id=pointer.previous_run_id,
                    published_at=pointer.published_at,
                    disabled_run_ids=pointer.disabled_run_ids,
                    allowed_keys=frozenset(allowed),
                    pinned_objects=MappingProxyType(pinned),
                    payload_descriptors=MappingProxyType(payload_descriptors),
                )
            except (ContractError, ObjectStoreError, KeyError, TypeError, ValueError) as error:
                if pointer is not None:
                    raise _CamsFamilyTargetVerificationError(pointer) from error
                last_error = error
                break
        if last_error is not None:
            raise PublishedRunsReaderError("published CAMS family verification failed") from last_error
        raise PublishedRunsReaderError(
            "CAMS family latest changed during every verification attempt"
        )

    def _build_snapshot(self, provider: str) -> _ProviderSnapshot:
        latest_key = _latest_key(provider)
        last_error: BaseException | None = None
        for _attempt in range(self._max_refresh_attempts):
            try:
                before = self._reader.head(latest_key)
                latest_stored = self._reader.get(latest_key)
                if latest_stored.etag != before.etag:
                    continue
                latest = _decode_canonical(latest_stored, "latest document")
                validate_latest_document(
                    latest,
                    expected_provider=provider,
                    catalog=self._catalog,
                )
                current, current_stored, current_key = self._read_manifest(
                    provider,
                    latest["latest"],
                )
                previous = None
                previous_stored = None
                previous_key = None
                if latest["previous"] is not None:
                    previous, previous_stored, previous_key = self._read_manifest(
                        provider,
                        latest["previous"],
                    )
                    if previous["source_run_id"] >= current["source_run_id"]:
                        raise PublishedRunsReaderError(
                            "published previous run does not precede the active run"
                        )
                validate_latest_document(
                    latest,
                    expected_provider=provider,
                    catalog=self._catalog,
                    run_manifest=current,
                    previous_manifest=previous,
                )
                after = self._reader.head(latest_key)
                if after.etag != latest_stored.etag:
                    continue

                disabled = frozenset(latest["disabled_run_ids"])
                allowed = {latest_key, current_key}
                pinned: dict[str, StoredObject] = {
                    latest_key: latest_stored,
                    current_key: current_stored,
                }
                payload_descriptors: dict[str, tuple[int, str]] = {}
                for manifest in (current, previous):
                    if manifest is None or manifest["source_run_id"] in disabled:
                        continue
                    if manifest is previous and previous_key is not None:
                        allowed.add(previous_key)
                        if previous_stored is not None:
                            pinned[previous_key] = previous_stored
                    for descriptor in manifest["objects"].values():
                        object_key = f"{_provider_root(provider)}/{descriptor['path']}"
                        head = self._reader.head(object_key)
                        expected = (descriptor["json_bytes"], descriptor["sha256"])
                        if (head.byte_length, head.sha256) != expected:
                            raise PublishedRunsReaderError(
                                "published payload descriptor mismatch"
                            )
                        allowed.add(object_key)
                        payload_descriptors[object_key] = expected
                return _ProviderSnapshot(
                    provider=provider,
                    latest=latest_stored,
                    revision=latest["revision"],
                    active_run_id=current["source_run_id"],
                    allowed_keys=frozenset(allowed),
                    disabled_run_ids=disabled,
                    pinned_objects=MappingProxyType(pinned),
                    payload_descriptors=MappingProxyType(payload_descriptors),
                )
            except (ContractError, ObjectStoreError, KeyError, TypeError, ValueError) as error:
                last_error = error
                break
        if last_error is not None:
            raise PublishedRunsReaderError("published provider verification failed") from last_error
        raise PublishedRunsReaderError("latest changed during every verification attempt")

    def _refresh(self, provider: str, *, required: bool = True) -> _ProviderSnapshot | None:
        if provider in _CAMS_PROVIDERS:
            raise PublishedRunsReaderError(
                "CAMS providers must be refreshed through the family pointer"
            )
        with self._lock:
            previous = self._snapshots.get(provider)
            try:
                current_head = self._reader.head(_latest_key(provider))
                if previous is not None and current_head.etag == previous.latest.etag:
                    return previous
                candidate = self._build_snapshot(provider)
                if previous is not None and candidate.revision <= previous.revision:
                    raise PublishedRunsReaderError(
                        "published latest revision did not advance"
                    )
                if (
                    previous is not None
                    and candidate.active_run_id in previous.disabled_run_ids
                ):
                    raise PublishedRunsReaderError(
                        "published latest attempts to reactivate a disabled run"
                    )
                if (
                    previous is not None
                    and candidate.active_run_id < previous.active_run_id
                    and previous.active_run_id not in candidate.disabled_run_ids
                ):
                    raise PublishedRunsReaderError(
                        "published latest regressed without an explicit rollback"
                    )
            except (ObjectStoreError, ContractError, KeyError, TypeError, ValueError) as error:
                self._statuses[provider] = {
                    "status": "retained" if previous is not None else "unavailable",
                    "active_run_id": None if previous is None else previous.active_run_id,
                    "error_type": type(error).__name__,
                }
                if previous is not None:
                    return previous
                if required:
                    raise ObjectNotFound(_latest_key(provider)) from error
                return None
            if previous is not None:
                disabled = previous.disabled_run_ids | candidate.disabled_run_ids
                cumulative = previous.allowed_keys | candidate.allowed_keys
                cumulative = frozenset(
                    key
                    for key in cumulative
                    if _key_run_id(key) not in disabled
                )
                pinned = {
                    **previous.pinned_objects,
                    **candidate.pinned_objects,
                }
                payload_descriptors = {
                    **previous.payload_descriptors,
                    **candidate.payload_descriptors,
                }
                pinned = {
                    key: value
                    for key, value in pinned.items()
                    if _key_run_id(key) not in disabled
                }
                payload_descriptors = {
                    key: value
                    for key, value in payload_descriptors.items()
                    if _key_run_id(key) not in disabled
                }
                candidate = _ProviderSnapshot(
                    provider=candidate.provider,
                    latest=candidate.latest,
                    revision=candidate.revision,
                    active_run_id=candidate.active_run_id,
                    allowed_keys=cumulative,
                    disabled_run_ids=disabled,
                    pinned_objects=MappingProxyType(pinned),
                    payload_descriptors=MappingProxyType(payload_descriptors),
                )
            self._snapshots[provider] = candidate
            self._statuses[provider] = {
                "status": "verified",
                "active_run_id": candidate.active_run_id,
                "error_type": None,
            }
            return candidate

    def _set_cams_status(
        self,
        status: str,
        active_run_id: str | None,
        error_type: str | None,
    ) -> None:
        for provider in _CAMS_PROVIDERS.intersection(self._providers):
            self._statuses[provider] = {
                "status": status,
                "active_run_id": active_run_id,
                "error_type": error_type,
            }

    @staticmethod
    def _retain_cams_active_after_previous_revocation(
        previous: _CamsFamilySnapshot,
        pointer: _CamsFamilyPointer,
    ) -> _CamsFamilySnapshot | None:
        """Apply a previous-only tombstone while reusing the verified active pair."""

        revoked_previous = previous.previous_run_id
        if (
            revoked_previous is None
            or revoked_previous not in pointer.disabled_run_ids
            or pointer.active_run_id != previous.active_run_id
            or pointer.previous_run_id is not None
        ):
            return None
        previous_document = _decode_canonical(
            previous.latest,
            "retained CAMS family latest",
        )
        if previous_document["latest"] != pointer.active_descriptor:
            return None

        disabled = pointer.disabled_run_ids
        allowed = frozenset(
            key
            for key in previous.allowed_keys
            if _key_run_id(key) not in disabled
        )
        pinned = {
            key: value
            for key, value in previous.pinned_objects.items()
            if _key_run_id(key) not in disabled
        }
        pinned[_CAMS_FAMILY_LATEST_KEY] = pointer.latest
        payload_descriptors = {
            key: value
            for key, value in previous.payload_descriptors.items()
            if _key_run_id(key) not in disabled
        }
        return _CamsFamilySnapshot(
            latest=pointer.latest,
            revision=pointer.revision,
            active_run_id=pointer.active_run_id,
            previous_run_id=None,
            published_at=pointer.published_at,
            disabled_run_ids=disabled,
            allowed_keys=allowed,
            pinned_objects=MappingProxyType(pinned),
            payload_descriptors=MappingProxyType(payload_descriptors),
        )

    def _refresh_cams_family(
        self,
        *,
        required: bool = True,
    ) -> _CamsFamilySnapshot | None:
        with self._lock:
            previous = self._cams_family_snapshot
            try:
                current_head = self._reader.head(_CAMS_FAMILY_LATEST_KEY)
                if previous is not None and current_head.etag == previous.latest.etag:
                    return previous
                candidate = self._build_cams_family_snapshot()
                if previous is not None:
                    _validate_cams_family_transition(previous, candidate)
            except (ObjectStoreError, ContractError, KeyError, TypeError, ValueError) as error:
                # A fully valid revocation pointer is authoritative even when
                # one of its targets cannot be re-read. Every cached run named
                # by its cumulative tombstones must disappear. Retain the
                # active pair only when the new pointer can describe that exact
                # coherent view; otherwise clear the whole family.
                if (
                    previous is not None
                    and isinstance(error, _CamsFamilyTargetVerificationError)
                ):
                    try:
                        _validate_cams_family_transition(previous, error.pointer)
                    except PublishedRunsReaderError as transition_error:
                        error = transition_error
                    else:
                        cached_run_ids = {previous.active_run_id}
                        if previous.previous_run_id is not None:
                            cached_run_ids.add(previous.previous_run_id)
                        revoked_cached_run_ids = (
                            cached_run_ids & error.pointer.disabled_run_ids
                        )
                        if revoked_cached_run_ids:
                            retained = (
                                self._retain_cams_active_after_previous_revocation(
                                    previous,
                                    error.pointer,
                                )
                            )
                            if retained is not None:
                                self._cams_family_snapshot = retained
                                self._set_cams_status(
                                    "retained",
                                    retained.active_run_id,
                                    type(error).__name__,
                                )
                                return retained
                            self._cams_family_snapshot = None
                            self._set_cams_status(
                                "unavailable",
                                None,
                                type(error).__name__,
                            )
                            if required:
                                raise ObjectNotFound(
                                    _CAMS_FAMILY_LATEST_KEY
                                ) from error
                            return None
                self._set_cams_status(
                    "retained" if previous is not None else "unavailable",
                    None if previous is None else previous.active_run_id,
                    type(error).__name__,
                )
                if previous is not None:
                    return previous
                if required:
                    raise ObjectNotFound(_CAMS_FAMILY_LATEST_KEY) from error
                return None
            self._cams_family_snapshot = candidate
            self._set_cams_status("verified", candidate.active_run_id, None)
            return candidate

    def _authorized_snapshot(
        self,
        key: str,
    ) -> _ProviderSnapshot | _CamsFamilySnapshot:
        scope = self._scope_for_key(key)
        if scope == _CAMS_FAMILY:
            if not _CAMS_PROVIDERS.intersection(self._providers):
                raise ObjectNotFound(key)
            snapshot = self._refresh_cams_family()
        elif scope in _CAMS_PROVIDERS:
            if scope not in self._providers:
                raise ObjectNotFound(key)
            snapshot = self._refresh_cams_family()
        else:
            if scope not in self._providers:
                raise ObjectNotFound(key)
            snapshot = self._refresh(scope)
        if snapshot is None or key not in snapshot.allowed_keys:
            raise ObjectNotFound(key)
        return snapshot

    def head(self, key: str) -> ObjectHead:
        snapshot = self._authorized_snapshot(key)
        pinned = snapshot.pinned_objects.get(key)
        if pinned is not None:
            return pinned.head
        head = self._reader.head(key)
        expected = snapshot.payload_descriptors.get(key)
        if expected is None or (head.byte_length, head.sha256) != expected:
            raise ObjectNotFound(key)
        return head

    def get(self, key: str) -> StoredObject:
        snapshot = self._authorized_snapshot(key)
        pinned = snapshot.pinned_objects.get(key)
        if pinned is not None:
            return pinned
        stored = self._reader.get(key)
        expected = snapshot.payload_descriptors.get(key)
        if expected is None or (stored.byte_length, stored.sha256) != expected:
            raise ObjectNotFound(key)
        return stored

    def close(self) -> None:
        close = getattr(self._reader, "close", None)
        if callable(close):
            close()


__all__ = ["PublishedRunsObjectReader", "PublishedRunsReaderError"]
