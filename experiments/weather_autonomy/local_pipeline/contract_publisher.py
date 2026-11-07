"""Atomic offline publication of :mod:`contract_v1` documents.

The generic local publisher intentionally has its own transport manifest.  This
adapter instead persists the contract-v1 bodies verbatim and therefore uses the
paths carried by that contract:

``weather/v1/<provider>/runs/<run>/municipalities/<istat>.json``
``weather/v1/<provider>/runs/<run>/manifest.json``
``weather/v1/<provider>/latest.json``

Municipality documents and manifests are create-only.  Only ``latest.json`` is
mutable, and every mutation uses the SQLite object's ETag as a compare-and-swap
precondition.  The module performs no network, cloud or application I/O.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
import hashlib
import json
import re
from typing import Any, Mapping

try:  # Namespace-package import and direct local unittest discovery.
    from .operational_diagnostics import attach_error_fields, phase
    from .contract_v1 import (
        CAMS_POLLEN_PROVIDER,
        CAMS_PROVIDER,
        EXPECTED_MUNICIPALITIES,
        ICON_PROVIDER,
        LATEST_KIND,
        PROVIDERS,
        RUN_MANIFEST_KIND,
        Catalog,
        ContractError,
        build_latest_document,
        build_object_descriptor,
        canonical_json_bytes,
        validate_latest_document,
        validate_run_manifest,
    )
    from .sqlite_object_store import (
        ObjectHead,
        ObjectNotFound,
        PreconditionFailed,
        SQLiteObjectStore,
        StoredObject,
    )
except ImportError:  # pragma: no cover - direct script fallback
    from operational_diagnostics import attach_error_fields, phase
    from contract_v1 import (  # type: ignore
        CAMS_POLLEN_PROVIDER,
        CAMS_PROVIDER,
        EXPECTED_MUNICIPALITIES,
        ICON_PROVIDER,
        LATEST_KIND,
        PROVIDERS,
        RUN_MANIFEST_KIND,
        Catalog,
        ContractError,
        build_latest_document,
        build_object_descriptor,
        canonical_json_bytes,
        validate_latest_document,
        validate_run_manifest,
    )
    from sqlite_object_store import (  # type: ignore
        ObjectHead,
        ObjectNotFound,
        PreconditionFailed,
        SQLiteObjectStore,
        StoredObject,
    )


_SEGMENT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
_RUN_ID = re.compile(r"^\d{8}T\d{6}Z$")
_UTC_SECONDS = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
_JSON_CONTENT_TYPE = "application/json"
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_CAMS_FAMILY = "cams"
_CAMS_FAMILY_RELEASE_KIND = "meteofriul.weather.cams_family_release"
_CAMS_FAMILY_LATEST_KIND = "meteofriul.weather.cams_family_latest"
_CAMS_FAMILY_COMPONENTS = {
    "core": CAMS_PROVIDER,
    "pollen": CAMS_POLLEN_PROVIDER,
}


class ContractPublicationError(RuntimeError):
    """Base class for a contract-v1 publication failure."""


class InvalidContractPublication(ContractPublicationError, ValueError):
    pass


class ImmutableContractConflict(ContractPublicationError):
    pass


class ContractPublicationVerificationError(ContractPublicationError):
    pass


class StaleContractRun(ContractPublicationError):
    pass


class LatestCasExhausted(ContractPublicationError):
    pass


@dataclass(frozen=True)
class VerifiedLatestSnapshot:
    """One verified pointer generation and the manifest authenticated with it."""

    document: dict[str, Any]
    manifest: dict[str, Any]
    etag: str


@dataclass(frozen=True)
class ContractPublicationResult:
    provider: str
    source_run_id: str
    payload_keys: tuple[str, ...]
    manifest_key: str
    latest_key: str
    latest_etag: str
    reused_payload_count: int
    manifest_reused: bool
    idempotent: bool
    latest_updated: bool
    superseded: bool = False


@dataclass(frozen=True)
class ContractStageResult:
    """One complete immutable provider run, not yet made current."""

    provider: str
    source_run_id: str
    payload_keys: tuple[str, ...]
    manifest_key: str
    manifest_etag: str
    manifest_json_bytes: int
    manifest_sha256: str
    reused_payload_count: int
    manifest_reused: bool

    @property
    def idempotent(self) -> bool:
        return (
            self.reused_payload_count == EXPECTED_MUNICIPALITIES
            and self.manifest_reused
        )


@dataclass(frozen=True)
class CamsFamilyPublicationResult:
    """Result of the sole externally visible CAMS-family CAS."""

    source_run_id: str
    release_key: str
    release_sha256: str
    release_reused: bool
    latest_key: str
    latest_etag: str
    revision: int
    idempotent: bool
    latest_updated: bool
    superseded: bool = False


@dataclass(frozen=True)
class CamsFamilyRevocationResult:
    """Result of removing one complete CAMS release from the family allow-list."""

    revoked_run_id: str
    active_run_id: str
    latest_key: str
    latest_etag: str
    revision: int
    latest_updated: bool
    idempotent: bool
    rolled_back: bool
    superseded: bool = False


@dataclass(frozen=True)
class ContractRevocationResult:
    provider: str
    revoked_run_id: str
    active_run_id: str
    latest_key: str
    latest_etag: str
    latest_updated: bool
    idempotent: bool
    rolled_back: bool


@dataclass(frozen=True)
class _Candidate:
    provider: str
    source_run_id: str
    payload_bodies: dict[str, bytes]
    manifest: dict[str, Any]
    manifest_body: bytes
    quality_bodies: dict[str, bytes] = field(default_factory=dict)


@dataclass(frozen=True)
class _LatestSnapshot:
    document: dict[str, Any]
    head: ObjectHead
    manifest: dict[str, Any]
    manifest_body: bytes
    previous_manifest: dict[str, Any] | None


@dataclass(frozen=True)
class _CamsFamilySnapshot:
    document: dict[str, Any]
    head: ObjectHead
    release: dict[str, Any]
    release_body: bytes
    previous_release: dict[str, Any] | None


def _normalize_prefix(value: str) -> str:
    prefix = str(value or "").strip().strip("/")
    if not prefix or any(not _SEGMENT.fullmatch(part) for part in prefix.split("/")):
        raise ValueError("invalid contract publication prefix")
    return prefix


def _provider(value: str) -> str:
    if value not in PROVIDERS:
        raise InvalidContractPublication("unsupported contract-v1 provider")
    return value


def _publication_time(value: str) -> str:
    if not isinstance(value, str) or not _UTC_SECONDS.fullmatch(value):
        raise InvalidContractPublication("published_at must use canonical UTC seconds")
    try:
        datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError as error:
        raise InvalidContractPublication("published_at is not a valid UTC timestamp") from error
    return value


def _exact_keys(value: Any, expected: set[str], label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping) or set(value) != expected:
        raise ContractPublicationVerificationError(
            f"{label} has missing or extra fields"
        )
    return value


def _sha256_value(value: Any, label: str) -> str:
    if not isinstance(value, str) or not _SHA256.fullmatch(value):
        raise ContractPublicationVerificationError(f"{label} is not lowercase SHA-256")
    return value


def _positive_integer(value: Any, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ContractPublicationVerificationError(f"{label} must be a positive integer")
    return value


def _canonical_document(body: bytes, label: str) -> dict[str, Any]:
    try:
        value = json.loads(body)
    except (UnicodeError, json.JSONDecodeError) as error:
        raise ContractPublicationVerificationError(f"{label} is not valid JSON") from error
    if not isinstance(value, dict):
        raise ContractPublicationVerificationError(f"{label} is not a JSON object")
    try:
        canonical = canonical_json_bytes(value)
    except ContractError as error:
        raise ContractPublicationVerificationError(f"{label} is not canonical JSON data") from error
    if canonical != body:
        raise ContractPublicationVerificationError(f"{label} bytes are not canonical contract JSON")
    return value


class ContractV1Publisher:
    """Persist complete provider runs and advance a validated latest pointer."""

    def __init__(
        self,
        object_store: SQLiteObjectStore,
        catalog: Catalog,
        *,
        prefix: str = "weather/v1",
        max_cas_attempts: int = 16,
        cams_continuity: bool = False,
    ) -> None:
        if not all(
            hasattr(object_store, operation)
            for operation in ("put", "compare_and_swap", "get", "head", "exists")
        ):
            raise TypeError("object_store does not implement the required operations")
        if not isinstance(catalog, Catalog) or catalog.municipality_count != EXPECTED_MUNICIPALITIES:
            raise ValueError("publisher requires the complete contract-v1 catalog")
        if isinstance(max_cas_attempts, bool) or not isinstance(max_cas_attempts, int) or max_cas_attempts < 1:
            raise ValueError("max_cas_attempts must be a positive integer")
        self.store = object_store
        self.catalog = catalog
        self.prefix = _normalize_prefix(prefix)
        self.max_cas_attempts = max_cas_attempts
        if type(cams_continuity) is not bool:
            raise TypeError("cams_continuity must be boolean")
        self.cams_continuity = cams_continuity

    def provider_root(self, provider: str) -> str:
        return f"{self.prefix}/{_provider(provider)}"

    def payload_key(self, provider: str, source_run_id: str, istat_code: str) -> str:
        # Run and ISTAT syntax is ultimately checked by the contract validator;
        # this public path helper also rejects traversal before touching storage.
        if not _RUN_ID.fullmatch(str(source_run_id)) or not re.fullmatch(r"\d{6}", str(istat_code)):
            raise InvalidContractPublication("invalid run or ISTAT path identity")
        return (
            f"{self.provider_root(provider)}/runs/{source_run_id}/"
            f"municipalities/{istat_code}.json"
        )

    def manifest_key(self, provider: str, source_run_id: str) -> str:
        if not _RUN_ID.fullmatch(str(source_run_id)):
            raise InvalidContractPublication("invalid run path identity")
        return f"{self.provider_root(provider)}/runs/{source_run_id}/manifest.json"

    def latest_key(self, provider: str) -> str:
        return f"{self.provider_root(provider)}/latest.json"

    def cams_family_root(self) -> str:
        return f"{self.prefix}/families/{_CAMS_FAMILY}"

    def cams_family_release_key(self, source_run_id: str) -> str:
        if not _RUN_ID.fullmatch(str(source_run_id)):
            raise InvalidContractPublication("invalid CAMS family run path identity")
        return f"{self.cams_family_root()}/runs/{source_run_id}/release.json"

    def cams_family_latest_key(self) -> str:
        return f"{self.cams_family_root()}/latest.json"

    @staticmethod
    def _payload_metadata(
        provider: str,
        source_run_id: str,
        istat_code: str,
        body_sha256: str,
        kind: str,
    ) -> dict[str, str]:
        return {
            "kind": kind,
            "provider": provider,
            "source_run_id": source_run_id,
            "istat_code": istat_code,
            "schema_version": "1",
            "body_sha256": body_sha256,
        }

    @staticmethod
    def _manifest_metadata(provider: str, source_run_id: str, body: bytes) -> dict[str, str]:
        return {
            "kind": RUN_MANIFEST_KIND,
            "provider": provider,
            "source_run_id": source_run_id,
            "schema_version": "1",
            "body_sha256": hashlib.sha256(body).hexdigest(),
            "municipality_count": str(EXPECTED_MUNICIPALITIES),
        }

    @staticmethod
    def _latest_metadata(document: Mapping[str, Any]) -> dict[str, str]:
        return {
            "kind": LATEST_KIND,
            "provider": str(document["provider"]),
            "source_run_id": str(document["latest"]["source_run_id"]),
            "schema_version": "1",
            "revision": str(document["revision"]),
        }

    @staticmethod
    def _cams_family_release_metadata(
        document: Mapping[str, Any],
        body: bytes,
    ) -> dict[str, str]:
        return {
            "kind": _CAMS_FAMILY_RELEASE_KIND,
            "family": _CAMS_FAMILY,
            "source_run_id": str(document["source_run_id"]),
            "schema_version": "1",
            "body_sha256": hashlib.sha256(body).hexdigest(),
            "validation_sha256": str(document["validation_sha256"]),
            "component_count": str(len(_CAMS_FAMILY_COMPONENTS)),
        }

    @staticmethod
    def _cams_family_latest_metadata(document: Mapping[str, Any]) -> dict[str, str]:
        return {
            "kind": _CAMS_FAMILY_LATEST_KIND,
            "family": _CAMS_FAMILY,
            "source_run_id": str(document["latest"]["source_run_id"]),
            "schema_version": "1",
            "revision": str(document["revision"]),
        }

    def _write_immutable(self, key, body, metadata):
        try:
            return self._write_immutable_checked(key, body, metadata)
        except Exception as error:
            fields = {"stage": "immutable_write_verification", "object_key": key}
            if "/municipalities/" in key:
                fields["municipality_code"] = key.rsplit("/", 1)[-1].removesuffix(".json")
            attach_error_fields(error, **fields)
            raise

    def _write_immutable_checked(
        self,
        key: str,
        body: bytes,
        metadata: Mapping[str, str],
    ) -> tuple[ObjectHead, bool]:
        try:
            head = self.store.put(
                key,
                body,
                content_type=_JSON_CONTENT_TYPE,
                metadata=metadata,
            )
            reused = False
        except PreconditionFailed as error:
            try:
                existing = self.store.get(key)
            except ObjectNotFound as missing:
                raise ContractPublicationVerificationError(
                    "immutable object disappeared after create conflict"
                ) from missing
            if (
                existing.body != body
                or existing.content_type != _JSON_CONTENT_TYPE
                or existing.metadata != dict(metadata)
            ):
                raise ImmutableContractConflict(f"immutable contract object conflicts: {key}") from error
            head = existing.head
            reused = True
        observed = self.store.get(key)
        if (
            observed.head != head
            or observed.body != body
            or observed.byte_length != len(body)
            or observed.sha256 != hashlib.sha256(body).hexdigest()
            or observed.content_type != _JSON_CONTENT_TYPE
            or observed.metadata != dict(metadata)
        ):
            raise ContractPublicationVerificationError(
                f"immutable contract object verification failed: {key}"
            )
        return observed.head, reused

    def _candidate(
        self,
        provider: str,
        payloads: Mapping[str, Mapping[str, Any] | bytes],
        manifest: Mapping[str, Any],
    ) -> _Candidate:
        normalized_provider = _provider(provider)
        if not isinstance(payloads, Mapping) or set(payloads) != set(self.catalog.istat_codes):
            raise InvalidContractPublication(
                "publication must contain exactly the catalog's 215 municipality payloads"
            )
        try:
            manifest_body = canonical_json_bytes(manifest)
            normalized_manifest = json.loads(manifest_body)
        except (ContractError, json.JSONDecodeError) as error:
            raise InvalidContractPublication("run manifest is not canonical JSON data") from error
        bodies: dict[str, bytes] = {}
        for istat_code in self.catalog.istat_codes:
            payload = payloads[istat_code]
            if isinstance(payload, bytes):
                body = payload
            elif isinstance(payload, Mapping):
                try:
                    body = canonical_json_bytes(payload)
                except ContractError as error:
                    raise InvalidContractPublication("municipality payload is not JSON data") from error
            else:
                raise InvalidContractPublication("municipality payload must be an object or bytes")
            bodies[istat_code] = body
        try:
            validate_run_manifest(
                normalized_manifest,
                self.catalog,
                expected_provider=normalized_provider,
                object_bodies=bodies,
            )
        except ContractError as error:
            raise InvalidContractPublication("run bundle fails contract-v1 validation") from error
        quality_bodies = {}
        if normalized_provider == ICON_PROVIDER:
            from .icon_accumulation_sidecar import split_document
            for istat_code, body in bodies.items():
                public, evidence = split_document(body)
                bodies[istat_code] = public
                if evidence is not None:
                    quality_bodies[istat_code] = evidence
            if quality_bodies:
                # Never add keys to the manifest consumed by installed clients.
                normalized_manifest['objects'] = {
                    code: build_object_descriptor(provider=ICON_PROVIDER,
                        source_run_id=normalized_manifest['source_run_id'],
                        istat_code=code, payload=body, catalog=self.catalog)
                    for code, body in bodies.items()
                }
                manifest_body = canonical_json_bytes(normalized_manifest)
        return _Candidate(
            provider=normalized_provider,
            source_run_id=normalized_manifest["source_run_id"],
            payload_bodies=bodies,
            manifest=normalized_manifest,
            manifest_body=manifest_body,
            quality_bodies=quality_bodies,
        )

    def _read_manifest_by_run(
        self,
        provider: str,
        source_run_id: str,
        *,
        verify_payloads: bool,
    ) -> tuple[dict[str, Any], bytes, StoredObject]:
        try:
            return self._read_manifest_by_run_checked(
                provider, source_run_id, verify_payloads=verify_payloads
            )
        except Exception as error:
            existing = getattr(error, "weather_diagnostics", {})
            attach_error_fields(error, **{
                "provider": provider,
                "source_run_id": source_run_id,
                "stage": "stored_run_verification",
                "object_key": self.manifest_key(provider, source_run_id),
                **(existing if isinstance(existing, Mapping) else {}),
            })
            raise

    def _read_manifest_by_run_checked(
        self,
        provider: str,
        source_run_id: str,
        *,
        verify_payloads: bool,
    ) -> tuple[dict[str, Any], bytes, StoredObject]:
        key = self.manifest_key(provider, source_run_id)
        try:
            stored = self.store.get(key)
        except ObjectNotFound as error:
            raise ContractPublicationVerificationError("referenced run manifest is missing") from error
        if stored.content_type != _JSON_CONTENT_TYPE:
            raise ContractPublicationVerificationError("stored run manifest content type is invalid")
        document = _canonical_document(stored.body, "run manifest")
        try:
            validate_run_manifest(
                document,
                self.catalog,
                expected_provider=provider,
            )
        except ContractError as error:
            raise ContractPublicationVerificationError(
                "stored run manifest fails contract-v1 validation"
            ) from error
        if document["source_run_id"] != source_run_id:
            raise ContractPublicationVerificationError("stored run manifest has the wrong run identity")
        if stored.metadata != self._manifest_metadata(provider, source_run_id, stored.body):
            raise ContractPublicationVerificationError("stored run manifest metadata is invalid")
        if verify_payloads:
            for istat_code in self.catalog.istat_codes:
                descriptor = document["objects"][istat_code]
                key = self.payload_key(provider, source_run_id, istat_code)
                try:
                    self._verify_stored_municipality(provider, source_run_id, istat_code, descriptor)
                except Exception as error:
                    attach_error_fields(error, stage="stored_payload_verification",
                                        object_key=key, municipality_code=istat_code)
                    raise
        return document, stored.body, stored

    def _verify_stored_municipality(
        self,
        provider: str,
        source_run_id: str,
        istat_code: str,
        descriptor: Mapping[str, Any],
    ) -> None:
        key = self.payload_key(provider, source_run_id, istat_code)
        try:
            payload = self.store.get(key)
        except ObjectNotFound as error:
            raise ContractPublicationVerificationError(
                "stored run is missing a municipality payload"
            ) from error
        if (
            descriptor["path"] != f"runs/{source_run_id}/municipalities/{istat_code}.json"
            or payload.content_type != _JSON_CONTENT_TYPE
            or payload.byte_length != descriptor["json_bytes"]
            or payload.sha256 != descriptor["sha256"]
        ):
            raise ContractPublicationVerificationError(
                "stored municipality payload differs from its manifest descriptor"
            )
        payload_document = _canonical_document(payload.body, "municipality payload")
        expected_metadata = self._payload_metadata(
            provider, source_run_id, istat_code, descriptor["sha256"], payload_document.get("kind")
        )
        if payload.metadata != expected_metadata:
            raise ContractPublicationVerificationError("stored municipality payload metadata is invalid")
        # The manifest has already passed its structural/catalog validation.
        # Validate each body with the same descriptor builder used by
        # validate_run_manifest(object_bodies=...), retaining the failing ISTAT.
        try:
            expected = build_object_descriptor(
                provider=provider, source_run_id=source_run_id, istat_code=istat_code,
                payload=payload.body, catalog=self.catalog,
            )
            if descriptor != expected:
                raise ContractError("stored run object integrity mismatch")
        except ContractError as error:
            raise ContractPublicationVerificationError(
                "stored run payloads fail contract-v1 validation"
            ) from error

    def _read_manifest_descriptor(
        self,
        provider: str,
        descriptor: Mapping[str, Any],
    ) -> tuple[dict[str, Any], bytes]:
        source_run_id = descriptor["source_run_id"]
        expected_path = f"runs/{source_run_id}/manifest.json"
        if descriptor["manifest_path"] != expected_path:
            raise ContractPublicationVerificationError("latest manifest path is not canonical")
        document, body, stored = self._read_manifest_by_run(
            provider,
            source_run_id,
            verify_payloads=False,
        )
        if (
            len(body) != descriptor["manifest_json_bytes"]
            or hashlib.sha256(body).hexdigest() != descriptor["manifest_sha256"]
            or stored.sha256 != descriptor["manifest_sha256"]
            or document["run_at"] != descriptor["run_at"]
        ):
            raise ContractPublicationVerificationError(
                "latest manifest descriptor does not match stored bytes"
            )
        return document, body

    def _read_latest_snapshot(self, provider: str) -> _LatestSnapshot | None:
        normalized_provider = _provider(provider)
        key = self.latest_key(normalized_provider)
        try:
            stored = self.store.get(key)
        except ObjectNotFound:
            return None
        if stored.content_type != _JSON_CONTENT_TYPE:
            raise ContractPublicationVerificationError("latest content type is invalid")
        document = _canonical_document(stored.body, "latest")
        try:
            validate_latest_document(
                document,
                expected_provider=normalized_provider,
                catalog=self.catalog,
            )
        except ContractError as error:
            raise ContractPublicationVerificationError(
                "latest fails contract-v1 validation"
            ) from error
        if stored.metadata != self._latest_metadata(document):
            raise ContractPublicationVerificationError("latest metadata is invalid")
        manifest, manifest_body = self._read_manifest_descriptor(
            normalized_provider,
            document["latest"],
        )
        previous_manifest = None
        if document["previous"] is not None:
            previous_manifest, _previous_body = self._read_manifest_descriptor(
                normalized_provider,
                document["previous"],
            )
            if (
                document["latest"]["source_run_id"]
                <= document["previous"]["source_run_id"]
            ):
                raise ContractPublicationVerificationError(
                    "latest does not follow its previous run"
                )
        try:
            validate_latest_document(
                document,
                expected_provider=normalized_provider,
                catalog=self.catalog,
                run_manifest=manifest,
                previous_manifest=previous_manifest,
            )
        except ContractError as error:
            raise ContractPublicationVerificationError(
                "latest and immutable manifests are inconsistent"
            ) from error
        return _LatestSnapshot(
            document=document,
            head=stored.head,
            manifest=manifest,
            manifest_body=manifest_body,
            previous_manifest=previous_manifest,
        )

    @staticmethod
    def _high_water(document: Mapping[str, Any]) -> str:
        run_ids = [document["latest"]["source_run_id"], *document["disabled_run_ids"]]
        if document["previous"] is not None:
            run_ids.append(document["previous"]["source_run_id"])
        return max(run_ids)

    def _assert_may_publish(
        self,
        source_run_id: str,
        current: _LatestSnapshot | None,
    ) -> None:
        if current is None or source_run_id == current.document["latest"]["source_run_id"]:
            return
        high_water = self._high_water(current.document)
        if source_run_id <= high_water:
            raise StaleContractRun(
                f"run {source_run_id} cannot replace high-water run {high_water}"
            )

    def _quality_key(self, candidate, istat_code):
        return f"{self.provider_root(ICON_PROVIDER)}/runs/{candidate.source_run_id}/accumulation-quality/{istat_code}.json"

    def _verify_stored_candidate(self, candidate: _Candidate) -> None:
        for code, expected in candidate.quality_bodies.items():
            stored = self.store.get(self._quality_key(candidate, code))
            if (stored.body != expected or stored.byte_length != len(expected)
                    or stored.sha256 != hashlib.sha256(expected).hexdigest()
                    or stored.content_type != _JSON_CONTENT_TYPE):
                raise ContractPublicationVerificationError('ICON sidecar read-back failed')
        with phase("stored_run_verification", provider=candidate.provider, source_run_id=candidate.source_run_id):
            manifest, body, _stored = self._read_manifest_by_run(
                candidate.provider,
                candidate.source_run_id,
                verify_payloads=True,
            )
        if body != candidate.manifest_body or manifest != candidate.manifest:
            raise ContractPublicationVerificationError(
                "stored run manifest differs from the publication candidate"
            )

    def _stage_candidate(self, candidate: _Candidate) -> ContractStageResult:
        # All evidence is durable and verified before the public manifest/latest.
        for code, body in candidate.quality_bodies.items():
            self._write_immutable(self._quality_key(candidate, code), body,
                                  {'kind': 'icon-accumulation-sidecar.v1',
                                   'source_run_id': candidate.source_run_id, 'istat_code': code})
        payload_keys: list[str] = []
        reused_payloads = 0
        for istat_code in self.catalog.istat_codes:
            descriptor = candidate.manifest["objects"][istat_code]
            body = candidate.payload_bodies[istat_code]
            key = self.payload_key(candidate.provider, candidate.source_run_id, istat_code)
            payload_document = _canonical_document(body, "municipality payload")
            metadata = self._payload_metadata(
                candidate.provider,
                candidate.source_run_id,
                istat_code,
                descriptor["sha256"],
                payload_document["kind"],
            )
            _head, reused = self._write_immutable(key, body, metadata)
            payload_keys.append(key)
            reused_payloads += int(reused)

        manifest_key = self.manifest_key(candidate.provider, candidate.source_run_id)
        manifest_head, manifest_reused = self._write_immutable(
            manifest_key,
            candidate.manifest_body,
            self._manifest_metadata(
                candidate.provider,
                candidate.source_run_id,
                candidate.manifest_body,
            ),
        )
        # This full read-back is the staging gate. A release pointer may never
        # identify this run unless every immutable object has been verified.
        self._verify_stored_candidate(candidate)
        return ContractStageResult(
            provider=candidate.provider,
            source_run_id=candidate.source_run_id,
            payload_keys=tuple(payload_keys),
            manifest_key=manifest_key,
            manifest_etag=manifest_head.etag,
            manifest_json_bytes=len(candidate.manifest_body),
            manifest_sha256=hashlib.sha256(candidate.manifest_body).hexdigest(),
            reused_payload_count=reused_payloads,
            manifest_reused=manifest_reused,
        )

    def stage_run(
        self,
        provider: str,
        payloads: Mapping[str, Mapping[str, Any] | bytes],
        manifest: Mapping[str, Any],
    ) -> ContractStageResult:
        """Persist and verify one immutable run without advancing any pointer."""

        return self._stage_candidate(self._candidate(provider, payloads, manifest))

    def _verify_stage_result(
        self,
        stage: ContractStageResult,
        expected_provider: str,
    ) -> tuple[dict[str, Any], bytes]:
        if not isinstance(stage, ContractStageResult):
            raise InvalidContractPublication("CAMS family member is not a staged run")
        if stage.provider != expected_provider:
            raise InvalidContractPublication("CAMS family member provider is invalid")
        if not _RUN_ID.fullmatch(stage.source_run_id):
            raise InvalidContractPublication("CAMS family member run identity is invalid")
        expected_payload_keys = tuple(
            self.payload_key(stage.provider, stage.source_run_id, istat_code)
            for istat_code in self.catalog.istat_codes
        )
        if (
            stage.payload_keys != expected_payload_keys
            or stage.manifest_key
            != self.manifest_key(stage.provider, stage.source_run_id)
            or not isinstance(stage.manifest_etag, str)
            or not stage.manifest_etag
            or isinstance(stage.manifest_json_bytes, bool)
            or not isinstance(stage.manifest_json_bytes, int)
            or stage.manifest_json_bytes < 1
            or not isinstance(stage.reused_payload_count, int)
            or isinstance(stage.reused_payload_count, bool)
            or not 0 <= stage.reused_payload_count <= EXPECTED_MUNICIPALITIES
            or not isinstance(stage.manifest_reused, bool)
        ):
            raise InvalidContractPublication("CAMS family staged-run result is invalid")
        try:
            _sha256_value(stage.manifest_sha256, "staged manifest SHA-256")
        except ContractPublicationVerificationError as error:
            raise InvalidContractPublication("CAMS family staged-run result is invalid") from error

        # stage_run already performed the expensive 215-payload read-back before
        # returning this handle. Re-read only its immutable manifest here: its
        # canonical object table binds every payload key, byte length and SHA.
        manifest, body, stored = self._read_manifest_by_run(
            stage.provider,
            stage.source_run_id,
            verify_payloads=False,
        )
        if (
            stored.head.etag != stage.manifest_etag
            or len(body) != stage.manifest_json_bytes
            or hashlib.sha256(body).hexdigest() != stage.manifest_sha256
            or stored.sha256 != stage.manifest_sha256
        ):
            raise ContractPublicationVerificationError(
                "CAMS family staged run differs from its immutable objects"
            )
        return manifest, body

    @staticmethod
    def _cams_component_descriptor(
        stage: ContractStageResult,
        manifest_body: bytes,
    ) -> dict[str, Any]:
        return {
            "provider": stage.provider,
            "source_run_id": stage.source_run_id,
            "manifest_key": stage.manifest_key,
            "manifest_json_bytes": len(manifest_body),
            "manifest_sha256": hashlib.sha256(manifest_body).hexdigest(),
        }

    def _validate_cams_component_descriptor(
        self,
        value: Any,
        *,
        role: str,
        source_run_id: str,
    ) -> Mapping[str, Any]:
        descriptor = _exact_keys(
            value,
            {
                "provider",
                "source_run_id",
                "manifest_key",
                "manifest_json_bytes",
                "manifest_sha256",
            },
            f"CAMS family {role} descriptor",
        )
        expected_provider = _CAMS_FAMILY_COMPONENTS[role]
        if (
            descriptor["provider"] != expected_provider
            or descriptor["source_run_id"] != source_run_id
            or descriptor["manifest_key"]
            != self.manifest_key(expected_provider, source_run_id)
        ):
            raise ContractPublicationVerificationError(
                f"CAMS family {role} descriptor identity is inconsistent"
            )
        _positive_integer(
            descriptor["manifest_json_bytes"],
            f"CAMS family {role} manifest byte length",
        )
        _sha256_value(
            descriptor["manifest_sha256"],
            f"CAMS family {role} manifest SHA-256",
        )
        return descriptor

    def _validate_cams_family_release(self, value: Any) -> Mapping[str, Any]:
        release = _exact_keys(
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
        if (
            type(release["schema_version"]) is not int
            or release["schema_version"] != 1
            or release["kind"] != _CAMS_FAMILY_RELEASE_KIND
            or release["family"] != _CAMS_FAMILY
            or not isinstance(release["source_run_id"], str)
            or not _RUN_ID.fullmatch(release["source_run_id"])
            or release["catalog"] != self.catalog.reference()
        ):
            raise ContractPublicationVerificationError(
                "CAMS family release identity is invalid"
            )
        try:
            _publication_time(release["published_at"])
        except InvalidContractPublication as error:
            raise ContractPublicationVerificationError(
                "CAMS family release publication time is invalid"
            ) from error
        _sha256_value(
            release["validation_sha256"],
            "CAMS family validation SHA-256",
        )
        components = _exact_keys(
            release["components"],
            set(_CAMS_FAMILY_COMPONENTS),
            "CAMS family components",
        )
        for role in _CAMS_FAMILY_COMPONENTS:
            self._validate_cams_component_descriptor(
                components[role],
                role=role,
                source_run_id=release["source_run_id"],
            )
        try:
            canonical_json_bytes(release)
        except ContractError as error:
            raise ContractPublicationVerificationError(
                "CAMS family release is not canonical JSON data"
            ) from error
        return release

    def _build_cams_family_release(
        self,
        core_stage: ContractStageResult,
        pollen_stage: ContractStageResult,
        *,
        validation_sha256: str,
        published_at: str,
    ) -> dict[str, Any]:
        _core_manifest, core_body = self._verify_stage_result(
            core_stage,
            CAMS_PROVIDER,
        )
        _pollen_manifest, pollen_body = self._verify_stage_result(
            pollen_stage,
            CAMS_POLLEN_PROVIDER,
        )
        if core_stage.source_run_id != pollen_stage.source_run_id:
            raise InvalidContractPublication(
                "CAMS family components must identify the same source run"
            )
        if not isinstance(validation_sha256, str) or not _SHA256.fullmatch(
            validation_sha256
        ):
            raise InvalidContractPublication(
                "CAMS family validation fingerprint must be lowercase SHA-256"
            )
        published_at = _publication_time(published_at)
        release = {
            "schema_version": 1,
            "kind": _CAMS_FAMILY_RELEASE_KIND,
            "family": _CAMS_FAMILY,
            "source_run_id": core_stage.source_run_id,
            "published_at": published_at,
            "validation_sha256": validation_sha256,
            "catalog": self.catalog.reference(),
            "components": {
                "core": self._cams_component_descriptor(core_stage, core_body),
                "pollen": self._cams_component_descriptor(pollen_stage, pollen_body),
            },
        }
        self._validate_cams_family_release(release)
        return release

    @staticmethod
    def _cams_family_release_descriptor(
        release: Mapping[str, Any],
        release_body: bytes,
    ) -> dict[str, Any]:
        return {
            "source_run_id": release["source_run_id"],
            "release_path": f"runs/{release['source_run_id']}/release.json",
            "release_json_bytes": len(release_body),
            "release_sha256": hashlib.sha256(release_body).hexdigest(),
        }

    def _validate_cams_family_release_descriptor(
        self,
        value: Any,
    ) -> Mapping[str, Any]:
        descriptor = _exact_keys(
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
            or descriptor["release_path"]
            != f"runs/{source_run_id}/release.json"
        ):
            raise ContractPublicationVerificationError(
                "CAMS family release descriptor identity is invalid"
            )
        _positive_integer(
            descriptor["release_json_bytes"],
            "CAMS family release byte length",
        )
        _sha256_value(
            descriptor["release_sha256"],
            "CAMS family release SHA-256",
        )
        return descriptor

    def _validate_cams_family_latest(self, value: Any) -> Mapping[str, Any]:
        latest = _exact_keys(
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
            or latest["catalog"] != self.catalog.reference()
        ):
            raise ContractPublicationVerificationError(
                "CAMS family latest identity is invalid"
            )
        _positive_integer(latest["revision"], "CAMS family latest revision")
        try:
            _publication_time(latest["published_at"])
        except InvalidContractPublication as error:
            raise ContractPublicationVerificationError(
                "CAMS family latest publication time is invalid"
            ) from error
        current = self._validate_cams_family_release_descriptor(latest["latest"])
        previous = latest["previous"]
        if previous is not None:
            previous = self._validate_cams_family_release_descriptor(previous)
            if previous["source_run_id"] >= current["source_run_id"]:
                raise ContractPublicationVerificationError(
                    "CAMS family previous release must precede latest"
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
            raise ContractPublicationVerificationError(
                "CAMS family disabled runs must be sorted unique canonical run IDs"
            )
        visible_run_ids = {current["source_run_id"]}
        if previous is not None:
            visible_run_ids.add(previous["source_run_id"])
        if visible_run_ids.intersection(disabled_run_ids):
            raise ContractPublicationVerificationError(
                "disabled CAMS family releases cannot remain publicly allow-listed"
            )
        try:
            canonical_json_bytes(latest)
        except ContractError as error:
            raise ContractPublicationVerificationError(
                "CAMS family latest is not canonical JSON data"
            ) from error
        return latest

    def _read_cams_family_release_descriptor(
        self,
        descriptor: Mapping[str, Any],
        *,
        verify_payloads: bool,
    ) -> tuple[dict[str, Any], bytes]:
        descriptor = self._validate_cams_family_release_descriptor(descriptor)
        source_run_id = descriptor["source_run_id"]
        release, body, stored = self._read_cams_family_release_by_run(
            source_run_id,
            verify_payloads=verify_payloads,
        )
        if (
            stored.byte_length != descriptor["release_json_bytes"]
            or stored.sha256 != descriptor["release_sha256"]
            or hashlib.sha256(body).hexdigest() != descriptor["release_sha256"]
        ):
            raise ContractPublicationVerificationError(
                "CAMS family release descriptor differs from stored bytes"
            )
        return release, body

    def _read_cams_family_release_by_run(
        self,
        source_run_id: str,
        *,
        verify_payloads: bool,
    ) -> tuple[dict[str, Any], bytes, StoredObject]:
        if not isinstance(source_run_id, str) or not _RUN_ID.fullmatch(source_run_id):
            raise InvalidContractPublication("invalid CAMS family run identity")
        release_key = self.cams_family_release_key(source_run_id)
        try:
            stored = self.store.get(release_key)
        except ObjectNotFound as error:
            raise ContractPublicationVerificationError(
                "referenced CAMS family release is missing"
            ) from error
        if (
            stored.content_type != _JSON_CONTENT_TYPE
            or stored.byte_length != len(stored.body)
            or stored.sha256 != hashlib.sha256(stored.body).hexdigest()
        ):
            raise ContractPublicationVerificationError(
                "stored CAMS family release bytes are inconsistent"
            )
        release = _canonical_document(stored.body, "CAMS family release")
        self._validate_cams_family_release(release)
        if (
            release["source_run_id"] != source_run_id
            or stored.metadata
            != self._cams_family_release_metadata(release, stored.body)
        ):
            raise ContractPublicationVerificationError(
                "stored CAMS family release identity is inconsistent"
            )
        for role, provider in _CAMS_FAMILY_COMPONENTS.items():
            component = release["components"][role]
            manifest, body, stored_manifest = self._read_manifest_by_run(
                provider,
                source_run_id,
                verify_payloads=verify_payloads,
            )
            if (
                manifest["provider"] != component["provider"]
                or stored_manifest.head.key != component["manifest_key"]
                or len(body) != component["manifest_json_bytes"]
                or hashlib.sha256(body).hexdigest()
                != component["manifest_sha256"]
                or stored_manifest.sha256 != component["manifest_sha256"]
            ):
                raise ContractPublicationVerificationError(
                    f"CAMS family {role} manifest differs from its release descriptor"
                )
        return release, stored.body, stored

    def _read_cams_family_snapshot(
        self,
        *,
        verify_payloads: bool,
    ) -> _CamsFamilySnapshot | None:
        key = self.cams_family_latest_key()
        try:
            stored = self.store.get(key)
        except ObjectNotFound:
            return None
        if stored.content_type != _JSON_CONTENT_TYPE:
            raise ContractPublicationVerificationError(
                "CAMS family latest content type is invalid"
            )
        document = _canonical_document(stored.body, "CAMS family latest")
        self._validate_cams_family_latest(document)
        if stored.metadata != self._cams_family_latest_metadata(document):
            raise ContractPublicationVerificationError(
                "CAMS family latest metadata is invalid"
            )
        release, release_body = self._read_cams_family_release_descriptor(
            document["latest"],
            verify_payloads=verify_payloads,
        )
        if release["published_at"] > document["published_at"]:
            raise ContractPublicationVerificationError(
                "CAMS family latest predates its active release"
            )
        previous_release = None
        if document["previous"] is not None:
            previous_release, _previous_body = (
                self._read_cams_family_release_descriptor(
                    document["previous"],
                    verify_payloads=False,
                )
            )
        return _CamsFamilySnapshot(
            document=document,
            head=stored.head,
            release=release,
            release_body=release_body,
            previous_release=previous_release,
        )

    def read_verified_cams_family_latest(self) -> dict[str, Any] | None:
        """Return the sole CAMS pointer after verifying both complete members."""

        snapshot = self._read_cams_family_snapshot(verify_payloads=True)
        return (
            None
            if snapshot is None
            else json.loads(canonical_json_bytes(snapshot.document))
        )

    @staticmethod
    def _cams_family_high_water(document: Mapping[str, Any]) -> str:
        run_ids = [
            document["latest"]["source_run_id"],
            *document["disabled_run_ids"],
        ]
        if document["previous"] is not None:
            run_ids.append(document["previous"]["source_run_id"])
        return max(run_ids)

    def _assert_may_release_cams_family(
        self,
        source_run_id: str,
        current: _CamsFamilySnapshot | None,
    ) -> None:
        if current is None or source_run_id == current.document["latest"]["source_run_id"]:
            return
        high_water = self._cams_family_high_water(current.document)
        if source_run_id <= high_water:
            raise StaleContractRun(
                f"CAMS family run {source_run_id} cannot replace high-water run {high_water}"
            )

    def release_cams_family(
        self,
        core_stage: ContractStageResult,
        pollen_stage: ContractStageResult,
        *,
        validation_sha256: str,
        published_at: str,
    ) -> CamsFamilyPublicationResult:
        """Atomically expose two staged CAMS members through one family pointer."""

        release = self._build_cams_family_release(
            core_stage,
            pollen_stage,
            validation_sha256=validation_sha256,
            published_at=published_at,
        )
        published_at = release["published_at"]
        source_run_id = release["source_run_id"]
        release_body = canonical_json_bytes(release)
        release_sha256 = hashlib.sha256(release_body).hexdigest()
        release_key = self.cams_family_release_key(source_run_id)
        latest_key = self.cams_family_latest_key()

        current = self._read_cams_family_snapshot(verify_payloads=False)
        self._assert_may_release_cams_family(source_run_id, current)
        if current is not None and (
            current.document["latest"]["source_run_id"] == source_run_id
        ):
            if current.release_body != release_body or current.release != release:
                raise ImmutableContractConflict(
                    "active CAMS family run has a conflicting immutable release"
                )
            return CamsFamilyPublicationResult(
                source_run_id=source_run_id,
                release_key=release_key,
                release_sha256=release_sha256,
                release_reused=True,
                latest_key=latest_key,
                latest_etag=current.head.etag,
                revision=current.document["revision"],
                idempotent=True,
                latest_updated=False,
            )

        _release_head, release_reused = self._write_immutable(
            release_key,
            release_body,
            self._cams_family_release_metadata(release, release_body),
        )
        # Write the optional policy BEFORE exposing this new family. Idempotent
        # reads of an already-active legacy family above never add a retroactive
        # extension. Failed/concurrent publications leave an unreachable sidecar.
        if self.cams_continuity:
            from .cams_continuity import build_cams_continuity, continuity_key
            policy = build_cams_continuity(release, release_body)
            policy_body = canonical_json_bytes(policy)
            self._write_immutable(
                continuity_key(source_run_id, self.prefix), policy_body,
                {"kind": policy["kind"], "source_run_id": source_run_id,
                 "sha256": hashlib.sha256(policy_body).hexdigest()},
            )
        release_descriptor = self._cams_family_release_descriptor(
            release,
            release_body,
        )
        last_precondition: PreconditionFailed | None = None
        for _attempt in range(self.max_cas_attempts):
            current = self._read_cams_family_snapshot(verify_payloads=False)
            self._assert_may_release_cams_family(source_run_id, current)
            if current is not None and (
                current.document["latest"]["source_run_id"] == source_run_id
            ):
                if current.release_body != release_body or current.release != release:
                    raise ImmutableContractConflict(
                        "active CAMS family run has a conflicting immutable release"
                    )
                return CamsFamilyPublicationResult(
                    source_run_id=source_run_id,
                    release_key=release_key,
                    release_sha256=release_sha256,
                    release_reused=release_reused,
                    latest_key=latest_key,
                    latest_etag=current.head.etag,
                    revision=current.document["revision"],
                    idempotent=True,
                    latest_updated=False,
                )
            if current is not None and published_at < current.document["published_at"]:
                raise InvalidContractPublication(
                    "CAMS family published_at cannot regress"
                )
            latest = {
                "schema_version": 1,
                "kind": _CAMS_FAMILY_LATEST_KIND,
                "family": _CAMS_FAMILY,
                "revision": 1 if current is None else current.document["revision"] + 1,
                "published_at": published_at,
                "catalog": self.catalog.reference(),
                "latest": release_descriptor,
                "previous": None if current is None else current.document["latest"],
                "disabled_run_ids": (
                    [] if current is None else current.document["disabled_run_ids"]
                ),
            }
            self._validate_cams_family_latest(latest)
            latest_body = canonical_json_bytes(latest)
            try:
                written = self.store.compare_and_swap(
                    latest_key,
                    latest_body,
                    expected_etag=None if current is None else current.head.etag,
                    content_type=_JSON_CONTENT_TYPE,
                    metadata=self._cams_family_latest_metadata(latest),
                )
            except PreconditionFailed as error:
                last_precondition = error
                continue

            observed = self._read_cams_family_snapshot(verify_payloads=False)
            if observed is None:
                raise ContractPublicationVerificationError(
                    "CAMS family latest disappeared after CAS"
                )
            observed_run = observed.document["latest"]["source_run_id"]
            if observed_run == source_run_id:
                if observed.release_body != release_body or observed.release != release:
                    raise ImmutableContractConflict(
                        "CAMS family latest changed to a conflicting release after CAS"
                    )
                if observed.document["revision"] < latest["revision"]:
                    raise ContractPublicationVerificationError(
                        "CAMS family latest revision regressed after CAS"
                    )
            elif observed_run > source_run_id:
                if observed.document["revision"] <= latest["revision"]:
                    raise ContractPublicationVerificationError(
                        "CAMS family supersession did not advance its revision"
                    )
            elif (
                latest["previous"] is not None
                and observed_run == latest["previous"]["source_run_id"]
                and observed.document["previous"] is None
                and source_run_id in observed.document["disabled_run_ids"]
                and observed.document["revision"] > latest["revision"]
            ):
                # A verified revocation may win after this CAS but before the
                # post-write read. That is safe supersession, not a corrupt
                # regression: the just-published run is no longer allow-listed.
                pass
            else:
                raise ContractPublicationVerificationError(
                    "CAMS family latest regressed after CAS"
                )
            if not set(latest["disabled_run_ids"]).issubset(
                observed.document["disabled_run_ids"]
            ):
                raise ContractPublicationVerificationError(
                    "CAMS family publication lost disabled-run history after CAS"
                )
            superseded = observed.document != latest or observed.head.etag != written.etag
            if superseded and observed.document["revision"] <= latest["revision"]:
                raise ContractPublicationVerificationError(
                    "CAMS family pointer changed without advancing its revision"
                )
            return CamsFamilyPublicationResult(
                source_run_id=source_run_id,
                release_key=release_key,
                release_sha256=release_sha256,
                release_reused=release_reused,
                latest_key=latest_key,
                latest_etag=observed.head.etag,
                revision=observed.document["revision"],
                idempotent=False,
                latest_updated=True,
                superseded=superseded,
            )
        raise LatestCasExhausted(
            "CAMS family latest CAS retry budget exhausted"
        ) from last_precondition

    def revoke_cams_family(
        self,
        source_run_id: str,
        *,
        published_at: str,
        rollback_to_run_id: str | None = None,
    ) -> CamsFamilyRevocationResult:
        """Remove one complete CAMS release with one family-pointer CAS.

        Only the releases named by ``latest`` and ``previous`` are mutable
        members of the public allow-list. Revoking the active release rolls the
        whole core+pollen family back to its verified previous release;
        revoking ``previous`` only removes that fallback. Immutable releases and
        provider-level latest pointers are never changed.
        """

        if not isinstance(source_run_id, str) or not _RUN_ID.fullmatch(source_run_id):
            raise InvalidContractPublication("invalid CAMS family run identity")
        if rollback_to_run_id is not None and (
            not isinstance(rollback_to_run_id, str)
            or not _RUN_ID.fullmatch(rollback_to_run_id)
        ):
            raise InvalidContractPublication("invalid CAMS family rollback target")
        published_at = _publication_time(published_at)
        latest_key = self.cams_family_latest_key()
        last_precondition: PreconditionFailed | None = None

        for _attempt in range(self.max_cas_attempts):
            current = self._read_cams_family_snapshot(verify_payloads=True)
            if current is None:
                raise InvalidContractPublication(
                    "cannot revoke without an active CAMS family release"
                )
            active_descriptor = current.document["latest"]
            previous_descriptor = current.document["previous"]
            active_run_id = active_descriptor["source_run_id"]
            previous_run_id = (
                None
                if previous_descriptor is None
                else previous_descriptor["source_run_id"]
            )
            disabled = set(current.document["disabled_run_ids"])

            if source_run_id in disabled:
                self._read_cams_family_release_by_run(
                    source_run_id,
                    verify_payloads=True,
                )
                return CamsFamilyRevocationResult(
                    revoked_run_id=source_run_id,
                    active_run_id=active_run_id,
                    latest_key=latest_key,
                    latest_etag=current.head.etag,
                    revision=current.document["revision"],
                    latest_updated=False,
                    idempotent=True,
                    rolled_back=(
                        source_run_id > active_run_id
                        and (
                            rollback_to_run_id is None
                            or active_run_id == rollback_to_run_id
                        )
                    ),
                    superseded=(
                        rollback_to_run_id is not None
                        and active_run_id != rollback_to_run_id
                    ),
                )
            if source_run_id not in {active_run_id, previous_run_id}:
                raise InvalidContractPublication(
                    "CAMS family revocation is limited to current or previous"
                )
            if source_run_id == previous_run_id and rollback_to_run_id is not None:
                raise StaleContractRun(
                    "CAMS family rollback source is no longer the active release"
                )

            if published_at < current.document["published_at"]:
                raise InvalidContractPublication(
                    "CAMS family published_at cannot regress"
                )

            if source_run_id == active_run_id:
                if previous_descriptor is None:
                    raise InvalidContractPublication(
                        "revoking the first CAMS family release requires a previous release"
                    )
                if (
                    rollback_to_run_id is not None
                    and rollback_to_run_id != previous_run_id
                ):
                    raise InvalidContractPublication(
                        "CAMS family rollback target must be the current previous release"
                    )
                self._read_cams_family_release_descriptor(
                    previous_descriptor,
                    verify_payloads=True,
                )
                next_active = previous_descriptor
                rolled_back = True
            else:
                # ``source_run_id`` is the only previous release. Removing it
                # never changes the active core+pollen pair.
                self._read_cams_family_release_descriptor(
                    previous_descriptor,
                    verify_payloads=True,
                )
                next_active = active_descriptor
                rolled_back = False

            disabled.add(source_run_id)
            latest = {
                "schema_version": 1,
                "kind": _CAMS_FAMILY_LATEST_KIND,
                "family": _CAMS_FAMILY,
                "revision": current.document["revision"] + 1,
                "published_at": published_at,
                "catalog": self.catalog.reference(),
                "latest": next_active,
                "previous": None,
                "disabled_run_ids": sorted(disabled),
            }
            self._validate_cams_family_latest(latest)
            latest_body = canonical_json_bytes(latest)
            try:
                self.store.compare_and_swap(
                    latest_key,
                    latest_body,
                    expected_etag=current.head.etag,
                    content_type=_JSON_CONTENT_TYPE,
                    metadata=self._cams_family_latest_metadata(latest),
                )
            except PreconditionFailed as error:
                last_precondition = error
                continue

            observed = self._read_cams_family_snapshot(verify_payloads=False)
            if observed is None:
                raise ContractPublicationVerificationError(
                    "CAMS family latest disappeared after revocation CAS"
                )
            observed_visible = {
                observed.document["latest"]["source_run_id"],
                None
                if observed.document["previous"] is None
                else observed.document["previous"]["source_run_id"],
            }
            if source_run_id in observed_visible:
                raise ContractPublicationVerificationError(
                    "revoked CAMS family release remained publicly allow-listed"
                )
            if (
                observed.document["revision"] < latest["revision"]
                or source_run_id not in observed.document["disabled_run_ids"]
                or not disabled.issubset(observed.document["disabled_run_ids"])
            ):
                raise ContractPublicationVerificationError(
                    "CAMS family revocation lost monotonic pointer state"
                )
            observed_active = observed.document["latest"]["source_run_id"]
            expected_active = next_active["source_run_id"]
            if observed_active != expected_active and observed_active <= active_run_id:
                raise ContractPublicationVerificationError(
                    "CAMS family revocation changed to an impossible active release"
                )
            superseded = observed.document != latest
            if superseded and observed.document["revision"] <= latest["revision"]:
                raise ContractPublicationVerificationError(
                    "CAMS family revocation pointer changed without advancing its revision"
                )
            return CamsFamilyRevocationResult(
                revoked_run_id=source_run_id,
                active_run_id=observed_active,
                latest_key=latest_key,
                latest_etag=observed.head.etag,
                revision=observed.document["revision"],
                latest_updated=True,
                idempotent=False,
                rolled_back=rolled_back,
                superseded=superseded,
            )
        raise LatestCasExhausted(
            "CAMS family revocation CAS retry budget exhausted"
        ) from last_precondition

    def rollback_cams_family(
        self,
        to_run_id: str,
        *,
        published_at: str,
    ) -> CamsFamilyRevocationResult:
        """Roll the active CAMS pair back only to its verified previous pair."""

        if not isinstance(to_run_id, str) or not _RUN_ID.fullmatch(to_run_id):
            raise InvalidContractPublication("invalid CAMS family rollback target")
        published_at = _publication_time(published_at)
        current = self._read_cams_family_snapshot(verify_payloads=True)
        if current is None:
            raise InvalidContractPublication(
                "cannot roll back without an active CAMS family release"
            )
        active_run_id = current.document["latest"]["source_run_id"]
        if active_run_id == to_run_id:
            rolled_back_runs = [
                run_id
                for run_id in current.document["disabled_run_ids"]
                if run_id > active_run_id
            ]
            if not rolled_back_runs:
                raise InvalidContractPublication(
                    "CAMS family rollback target is already active without revocation evidence"
                )
            return CamsFamilyRevocationResult(
                revoked_run_id=max(rolled_back_runs),
                active_run_id=active_run_id,
                latest_key=self.cams_family_latest_key(),
                latest_etag=current.head.etag,
                revision=current.document["revision"],
                latest_updated=False,
                idempotent=True,
                rolled_back=True,
            )
        previous = current.document["previous"]
        if previous is None or previous["source_run_id"] != to_run_id:
            raise InvalidContractPublication(
                "CAMS family rollback target must be the current previous release"
            )
        return self.revoke_cams_family(
            active_run_id,
            published_at=published_at,
            rollback_to_run_id=to_run_id,
        )

    def read_latest(self, provider: str) -> dict[str, Any] | None:
        snapshot = self._read_latest_snapshot(provider)
        return None if snapshot is None else json.loads(canonical_json_bytes(snapshot.document))

    def read_latest_if_etag(
        self,
        provider: str,
        expected_etag: str,
    ) -> dict[str, Any] | None:
        """Return the cheap latest snapshot only when its exact ETag is unchanged.

        This is intentionally not a substitute for ``read_verified_latest``.
        It lets the same ``publish_run`` call reuse the full body verification it
        has just completed, while forcing callers to fall back to a fresh strong
        verification whenever another writer has changed the latest pointer.
        """

        if not isinstance(expected_etag, str) or not expected_etag:
            raise ValueError("expected_etag must be a non-empty string")
        snapshot = self._read_latest_snapshot(provider)
        if snapshot is None or snapshot.head.etag != expected_etag:
            return None
        return json.loads(canonical_json_bytes(snapshot.document))

    def read_verified_latest(self, provider: str) -> dict[str, Any] | None:
        """Return latest only after revalidating every active municipality body.

        ``read_latest`` is intentionally inexpensive for ordinary pointer reads.
        Startup recovery is a stronger trust boundary: a previous run may be
        retained only after its manifest, all 215 payloads, hashes and metadata
        have been checked again against the current authoritative catalog.
        """

        snapshot = self._read_latest_snapshot(provider)
        if snapshot is None:
            return None
        manifest, body, _stored = self._read_manifest_by_run(
            snapshot.document["provider"],
            snapshot.document["latest"]["source_run_id"],
            verify_payloads=True,
        )
        if manifest != snapshot.manifest or body != snapshot.manifest_body:
            raise ContractPublicationVerificationError(
                "verified active manifest differs from latest"
            )
        return json.loads(canonical_json_bytes(snapshot.document))

    def read_verified_latest_snapshot(self, provider: str) -> VerifiedLatestSnapshot | None:
        """Bind complete verification to its original pointer generation.

        No later HEAD may label an older verification with a newer ETag. Callers
        must use read_latest_if_etag before reusing this proof, and discard it
        after publication or at the end of the current invocation.
        """
        snapshot = self._read_latest_snapshot(provider)
        if snapshot is None:
            return None
        manifest, body, _stored = self._read_manifest_by_run(
            snapshot.document["provider"], snapshot.document["latest"]["source_run_id"],
            verify_payloads=True,
        )
        if manifest != snapshot.manifest or body != snapshot.manifest_body:
            raise ContractPublicationVerificationError("verified active manifest differs from latest")
        return VerifiedLatestSnapshot(
            document=json.loads(canonical_json_bytes(snapshot.document)),
            manifest=json.loads(canonical_json_bytes(manifest)),
            etag=snapshot.head.etag,
        )

    def publish_run(
        self,
        provider: str,
        payloads: Mapping[str, Mapping[str, Any] | bytes],
        manifest: Mapping[str, Any],
        *,
        published_at: str,
    ) -> ContractPublicationResult:
        """Publish one provider pointer.

        The operational contract uses this primitive for ICON only. CAMS core
        and pollen must use ``stage_run`` followed by ``release_cams_family``;
        their legacy provider pointers are rejected by the public data plane.
        """

        published_at = _publication_time(published_at)
        candidate = self._candidate(provider, payloads, manifest)
        # Fast stale rejection prevents a known old run from creating objects.
        # The CAS loop repeats this check to cover a concurrent advancement.
        current = self._read_latest_snapshot(candidate.provider)
        self._assert_may_publish(candidate.source_run_id, current)

        # A local preview commonly restarts against the same immutable run.
        # Replaying 216 create-only writes in that case is both unnecessary and
        # very slow on a FULL-synchronous SQLite store. Revalidate the complete
        # stored run once, then return only if latest stayed on the exact ETag
        # observed before verification. A concurrent advance is handled by the
        # normal high-water check below instead of being mistaken for success.
        if current is not None and (
            current.document["latest"]["source_run_id"] == candidate.source_run_id
        ):
            if (
                current.manifest_body != candidate.manifest_body
                or current.manifest != candidate.manifest
            ):
                raise ImmutableContractConflict(
                    "latest identifies a conflicting immutable run manifest"
                )
            self._verify_stored_candidate(candidate)
            confirmed = self._read_latest_snapshot(candidate.provider)
            if confirmed is not None and confirmed.head.etag == current.head.etag:
                return ContractPublicationResult(
                    provider=candidate.provider,
                    source_run_id=candidate.source_run_id,
                    payload_keys=tuple(
                        self.payload_key(
                            candidate.provider,
                            candidate.source_run_id,
                            istat_code,
                        )
                        for istat_code in self.catalog.istat_codes
                    ),
                    manifest_key=self.manifest_key(
                        candidate.provider,
                        candidate.source_run_id,
                    ),
                    latest_key=self.latest_key(candidate.provider),
                    latest_etag=current.head.etag,
                    reused_payload_count=EXPECTED_MUNICIPALITIES,
                    manifest_reused=True,
                    idempotent=True,
                    latest_updated=False,
                )
            self._assert_may_publish(candidate.source_run_id, confirmed)

        stage = self._stage_candidate(candidate)
        return self._commit_staged_candidate(candidate, stage, published_at=published_at)

    def _authenticate_projected_intent(self, manifest, expected_hash):
        """Recover the checkpoint fingerprint from public bytes plus sidecars.

        A different or missing proof changes that fingerprint and cannot authorize
        recovery. No immutable object is created or overwritten by this path.
        """
        from .icon_accumulation_sidecar import validate_sidecar
        originals = {}
        original_manifest = json.loads(canonical_json_bytes(manifest))
        for code in self.catalog.istat_codes:
            public = self.store.get(self.payload_key(ICON_PROVIDER, manifest['source_run_id'], code))
            value = json.loads(public.body)
            key = f"{self.provider_root(ICON_PROVIDER)}/runs/{manifest['source_run_id']}/accumulation-quality/{code}.json"
            try:
                sidecar = self.store.get(key)
            except ObjectNotFound:
                originals[code] = public.body
            else:
                if (sidecar.content_type != _JSON_CONTENT_TYPE
                        or sidecar.byte_length != len(sidecar.body)
                        or sidecar.sha256 != hashlib.sha256(sidecar.body).hexdigest()):
                    raise ContractPublicationVerificationError('invalid recovery evidence')
                evidence = validate_sidecar(sidecar.body, public.body)
                for row, item in zip(value['hourly'], evidence['hourly']):
                    if item['accumulation_quality'] is not None:
                        row['accumulation_quality'] = item['accumulation_quality']
                originals[code] = canonical_json_bytes(value)
        original_manifest['objects'] = {
            code: build_object_descriptor(provider=ICON_PROVIDER,
                source_run_id=manifest['source_run_id'], istat_code=code,
                payload=body, catalog=self.catalog) for code, body in originals.items()
        }
        if hashlib.sha256(canonical_json_bytes(original_manifest)).hexdigest() != expected_hash:
            raise ImmutableContractConflict('public projection differs from frozen ICON intent')
        return self._candidate(ICON_PROVIDER, originals, original_manifest)

    def publish_existing_run(
        self,
        provider: str,
        source_run_id: str,
        *,
        expected_manifest_sha256: str,
        published_at: str,
    ) -> ContractPublicationResult:
        """Recover ICON publication using only already-stored immutable objects.

        The caller supplies the fingerprint and publication time from the
        original durable PublicationIntent. No municipality or manifest is
        created/replaced here: every body is revalidated before the ordinary
        conditional latest commit. Repeating an ambiguous commit is safe.
        """

        provider = _provider(provider)
        if provider != ICON_PROVIDER:
            raise InvalidContractPublication("publication-only recovery is ICON-only")
        published_at = _publication_time(published_at)
        manifest_key = self.manifest_key(provider, source_run_id)
        try:
            expected_manifest_sha256 = _sha256_value(
                expected_manifest_sha256, "recovery manifest SHA-256"
            )
        except ContractPublicationVerificationError as error:
            raise InvalidContractPublication("recovery manifest SHA-256 is invalid") from error
        current = self._read_latest_snapshot(provider)
        self._assert_may_publish(source_run_id, current)
        with phase("publication_recovery_validation", provider=provider, source_run_id=source_run_id):
            manifest, body, stored = self._read_manifest_by_run(
                provider, source_run_id, verify_payloads=False
            )
            candidate = None
            if hashlib.sha256(body).hexdigest() != expected_manifest_sha256:
                candidate = self._authenticate_projected_intent(manifest, expected_manifest_sha256)
                if candidate.manifest_body != body:
                    raise ImmutableContractConflict('recovered projection differs from stored manifest')
                self._verify_stored_candidate(candidate)
            if (stored.sha256 != hashlib.sha256(body).hexdigest()
                    or stored.byte_length != len(body)):
                raise ContractPublicationVerificationError('stored recovery manifest integrity failed')
            verified_manifest, verified_body, verified_stored = self._read_manifest_by_run(
                provider, source_run_id, verify_payloads=True
            )
            if (
                verified_body != body or verified_manifest != manifest
                or verified_stored.etag != stored.etag
            ):
                error = ImmutableContractConflict("recovery manifest changed during verification")
                attach_error_fields(error, object_key=manifest_key)
                raise error
        candidate = candidate or _Candidate(provider, source_run_id, {}, manifest, body)
        stage = ContractStageResult(
            provider=provider,
            source_run_id=source_run_id,
            payload_keys=tuple(self.payload_key(provider, source_run_id, code)
                               for code in self.catalog.istat_codes),
            manifest_key=manifest_key,
            manifest_etag=stored.etag,
            manifest_json_bytes=len(body),
            manifest_sha256=hashlib.sha256(body).hexdigest(),
            reused_payload_count=EXPECTED_MUNICIPALITIES,
            manifest_reused=True,
        )
        with phase("publication_recovery_commit", provider=provider, source_run_id=source_run_id):
            return self._commit_staged_candidate(candidate, stage, published_at=published_at)

    def _commit_staged_candidate(
        self,
        candidate: _Candidate,
        stage: ContractStageResult,
        *,
        published_at: str,
    ) -> ContractPublicationResult:
        """Commit a fully verified immutable candidate through the one CAS path."""

        payload_keys = stage.payload_keys
        reused_payloads = stage.reused_payload_count
        manifest_key = stage.manifest_key
        manifest_reused = stage.manifest_reused

        latest_key = self.latest_key(candidate.provider)
        last_precondition: PreconditionFailed | None = None
        for _attempt in range(self.max_cas_attempts):
            current = self._read_latest_snapshot(candidate.provider)
            self._assert_may_publish(candidate.source_run_id, current)
            if current is not None and (
                current.document["latest"]["source_run_id"] == candidate.source_run_id
            ):
                if (
                    current.manifest_body != candidate.manifest_body
                    or current.manifest != candidate.manifest
                ):
                    raise ImmutableContractConflict(
                        "latest identifies a conflicting immutable run manifest"
                    )
                return ContractPublicationResult(
                    provider=candidate.provider,
                    source_run_id=candidate.source_run_id,
                    payload_keys=tuple(payload_keys),
                    manifest_key=manifest_key,
                    latest_key=latest_key,
                    latest_etag=current.head.etag,
                    reused_payload_count=reused_payloads,
                    manifest_reused=manifest_reused,
                    idempotent=(
                        reused_payloads == EXPECTED_MUNICIPALITIES and manifest_reused
                    ),
                    latest_updated=False,
                )

            if current is not None and published_at < current.document["published_at"]:
                raise InvalidContractPublication("published_at cannot regress")

            latest = build_latest_document(
                provider=candidate.provider,
                revision=1 if current is None else current.document["revision"] + 1,
                published_at=published_at,
                run_manifest=candidate.manifest,
                catalog=self.catalog,
                previous_manifest=None if current is None else current.manifest,
                disabled_run_ids=()
                if current is None
                else current.document["disabled_run_ids"],
            )
            latest_body = canonical_json_bytes(latest)
            try:
                written = self.store.compare_and_swap(
                    latest_key,
                    latest_body,
                    expected_etag=None if current is None else current.head.etag,
                    content_type=_JSON_CONTENT_TYPE,
                    metadata=self._latest_metadata(latest),
                )
            except PreconditionFailed as error:
                last_precondition = error
                continue

            observed = self._read_latest_snapshot(candidate.provider)
            if observed is None:
                raise ContractPublicationVerificationError("latest disappeared after CAS")
            observed_run = observed.document["latest"]["source_run_id"]
            if observed_run == candidate.source_run_id:
                if observed.manifest_body != candidate.manifest_body:
                    raise ImmutableContractConflict(
                        "latest changed to a conflicting manifest after CAS"
                    )
                superseded = False
            elif (
                observed_run > candidate.source_run_id
                or candidate.source_run_id in observed.document["disabled_run_ids"]
            ):
                if observed.document["revision"] <= latest["revision"]:
                    raise ContractPublicationVerificationError(
                        "latest supersession did not advance its revision"
                    )
                superseded = True
            else:
                raise ContractPublicationVerificationError("latest regressed after CAS")
            return ContractPublicationResult(
                provider=candidate.provider,
                source_run_id=candidate.source_run_id,
                payload_keys=tuple(payload_keys),
                manifest_key=manifest_key,
                latest_key=latest_key,
                latest_etag=observed.head.etag if superseded else written.etag,
                reused_payload_count=reused_payloads,
                manifest_reused=manifest_reused,
                idempotent=False,
                latest_updated=True,
                superseded=superseded,
            )
        raise LatestCasExhausted("latest CAS retry budget exhausted") from last_precondition

    publish = publish_run

    def revoke_run(
        self,
        provider: str,
        source_run_id: str,
        *,
        published_at: str,
        rollback_to_run_id: str | None = None,
    ) -> ContractRevocationResult:
        """Revoke an independent provider run (currently operational for ICON).

        CAMS revocation/rollback is deliberately not emulated through this
        compatibility primitive; callers must use the atomic family methods.
        """

        published_at = _publication_time(published_at)
        normalized_provider = _provider(provider)
        if normalized_provider in {CAMS_PROVIDER, CAMS_POLLEN_PROVIDER}:
            raise InvalidContractPublication(
                "CAMS revocation must use the atomic family API"
            )
        # A revocation is meaningful only for a complete immutable run.  This
        # also validates the run identifier without duplicating contract regexes.
        self._read_manifest_by_run(
            normalized_provider,
            source_run_id,
            verify_payloads=True,
        )
        last_precondition: PreconditionFailed | None = None
        for _attempt in range(self.max_cas_attempts):
            current = self._read_latest_snapshot(normalized_provider)
            if current is None:
                raise InvalidContractPublication("cannot revoke without an active latest run")
            disabled = set(current.document["disabled_run_ids"])
            if source_run_id in disabled:
                return ContractRevocationResult(
                    provider=normalized_provider,
                    revoked_run_id=source_run_id,
                    active_run_id=current.document["latest"]["source_run_id"],
                    latest_key=self.latest_key(normalized_provider),
                    latest_etag=current.head.etag,
                    latest_updated=False,
                    idempotent=True,
                    rolled_back=False,
                )

            if published_at < current.document["published_at"]:
                raise InvalidContractPublication("published_at cannot regress")

            active_run_id = current.document["latest"]["source_run_id"]
            rolled_back = source_run_id == active_run_id
            if rolled_back:
                if rollback_to_run_id is None:
                    if current.previous_manifest is None:
                        raise InvalidContractPublication(
                            "revoking the first run requires an explicit complete rollback target"
                        )
                    target_manifest = current.previous_manifest
                else:
                    target_manifest, _body, _stored = self._read_manifest_by_run(
                        normalized_provider,
                        rollback_to_run_id,
                        verify_payloads=True,
                    )
                target_run_id = target_manifest["source_run_id"]
                if rollback_to_run_id is None:
                    target_manifest, _body, _stored = self._read_manifest_by_run(
                        normalized_provider,
                        target_run_id,
                        verify_payloads=True,
                    )
                if target_run_id >= source_run_id:
                    raise InvalidContractPublication("rollback target must precede the revoked run")
                if target_run_id in disabled:
                    raise InvalidContractPublication("rollback target is disabled")
                previous_manifest = None
            else:
                if rollback_to_run_id is not None:
                    raise InvalidContractPublication(
                        "rollback target is allowed only when revoking the active run"
                    )
                target_manifest = current.manifest
                target_run_id = active_run_id
                previous_manifest = current.previous_manifest
                if (
                    previous_manifest is not None
                    and previous_manifest["source_run_id"] == source_run_id
                ):
                    previous_manifest = None

            disabled.add(source_run_id)
            latest = build_latest_document(
                provider=normalized_provider,
                revision=current.document["revision"] + 1,
                published_at=published_at,
                run_manifest=target_manifest,
                catalog=self.catalog,
                previous_manifest=previous_manifest,
                disabled_run_ids=sorted(disabled),
            )
            body = canonical_json_bytes(latest)
            try:
                self.store.compare_and_swap(
                    self.latest_key(normalized_provider),
                    body,
                    expected_etag=current.head.etag,
                    content_type=_JSON_CONTENT_TYPE,
                    metadata=self._latest_metadata(latest),
                )
            except PreconditionFailed as error:
                last_precondition = error
                continue
            observed = self._read_latest_snapshot(normalized_provider)
            if observed is None or source_run_id not in observed.document["disabled_run_ids"]:
                raise ContractPublicationVerificationError(
                    "revocation disappeared after latest CAS"
                )
            if observed.document["revision"] < latest["revision"]:
                raise ContractPublicationVerificationError(
                    "revocation did not preserve monotonic latest revision"
                )
            return ContractRevocationResult(
                provider=normalized_provider,
                revoked_run_id=source_run_id,
                active_run_id=observed.document["latest"]["source_run_id"],
                latest_key=self.latest_key(normalized_provider),
                latest_etag=observed.head.etag,
                latest_updated=True,
                idempotent=False,
                rolled_back=rolled_back,
            )
        raise LatestCasExhausted("revocation CAS retry budget exhausted") from last_precondition

    revoke = revoke_run

    def rollback_latest(
        self,
        provider: str,
        to_run_id: str,
        *,
        published_at: str,
    ) -> ContractRevocationResult:
        normalized_provider = _provider(provider)
        if normalized_provider in {CAMS_PROVIDER, CAMS_POLLEN_PROVIDER}:
            raise InvalidContractPublication(
                "CAMS rollback must use the atomic family API"
            )
        current = self._read_latest_snapshot(normalized_provider)
        if current is None:
            raise InvalidContractPublication("cannot roll back without an active latest run")
        return self.revoke_run(
            normalized_provider,
            current.document["latest"]["source_run_id"],
            published_at=published_at,
            rollback_to_run_id=to_run_id,
        )


__all__ = [
    "CamsFamilyPublicationResult",
    "CamsFamilyRevocationResult",
    "ContractPublicationError",
    "ContractPublicationResult",
    "ContractPublicationVerificationError",
    "ContractRevocationResult",
    "ContractStageResult",
    "ContractV1Publisher",
    "ImmutableContractConflict",
    "InvalidContractPublication",
    "LatestCasExhausted",
    "StaleContractRun",
    "VerifiedLatestSnapshot",
]
