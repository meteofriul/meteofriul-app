"""Deterministic, offline publication protocol for weather data-plane tests."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
import json
import re
from typing import Iterable, Mapping

try:  # Supports both namespace-package imports and direct local test discovery.
    from .sqlite_object_store import (
        ObjectHead,
        ObjectNotFound,
        PreconditionFailed,
        SQLiteObjectStore,
    )
except ImportError:  # pragma: no cover - direct script fallback
    from sqlite_object_store import (  # type: ignore
        ObjectHead,
        ObjectNotFound,
        PreconditionFailed,
        SQLiteObjectStore,
    )


_SEGMENT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]*$")
_RESERVED_OBJECT_METADATA = frozenset(
    {"kind", "provider", "run_id", "logical_key", "body_sha256", "byte_length"}
)


class PublicationError(RuntimeError):
    """Base error for a rejected or incomplete local publication."""


class InvalidPublication(PublicationError, ValueError):
    pass


class PublicationSizeExceeded(InvalidPublication):
    pass


class ImmutableObjectConflict(PublicationError):
    pass


class PublicationVerificationError(PublicationError):
    pass


class StaleRun(PublicationError):
    pass


StaleRunError = StaleRun
ManifestConflict = ImmutableObjectConflict


@dataclass(frozen=True)
class PublicationObject:
    key: str
    body: bytes
    content_type: str = "application/json"
    metadata: Mapping[str, object] = field(default_factory=dict)


PublishObject = PublicationObject


@dataclass(frozen=True)
class PublicationResult:
    provider: str
    run_id: str
    object_keys: tuple[str, ...]
    manifest_key: str
    manifest_etag: str
    latest_key: str
    latest_etag: str
    idempotent: bool
    latest_updated: bool
    superseded: bool = False


@dataclass(frozen=True)
class RevocationResult:
    provider: str
    run_id: str
    revocation_key: str
    latest_updated: bool
    idempotent: bool


def _canonical_json(value: object) -> bytes:
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    except (TypeError, ValueError) as error:
        raise InvalidPublication("publication metadata is not canonical JSON") from error


def _decode_json(body: bytes, *, label: str) -> dict[str, object]:
    try:
        value = json.loads(body)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise PublicationVerificationError(f"{label} is not valid JSON") from error
    if not isinstance(value, dict):
        raise PublicationVerificationError(f"{label} must be a JSON object")
    return value


def _safe_segment(value: object, *, label: str) -> str:
    segment = str(value or "").strip()
    if not _SEGMENT.fullmatch(segment):
        raise InvalidPublication(f"invalid {label}")
    return segment


def _safe_logical_key(value: object) -> str:
    key = str(value or "").strip()
    if (
        not key
        or key.startswith("/")
        or key.endswith("/")
        or "\\" in key
        or "//" in key
        or any(part in {"", ".", ".."} for part in key.split("/"))
        or any(ord(char) < 32 for char in key)
    ):
        raise InvalidPublication("invalid logical object key")
    return key


def _string_metadata(metadata: Mapping[str, object] | None) -> dict[str, str]:
    normalized: dict[str, str] = {}
    for raw_key, raw_value in (metadata or {}).items():
        key = str(raw_key).strip()
        if not key or raw_value is None:
            raise InvalidPublication("invalid object metadata")
        normalized[key] = str(raw_value)
    return normalized


def _run_order_key(run_id: str) -> tuple[str, object]:
    if run_id.isdecimal():
        return "numeric", int(run_id)
    candidate = run_id[:-1] + "+00:00" if run_id.endswith("Z") else run_id
    try:
        parsed = datetime.fromisoformat(candidate)
    except ValueError:
        return "lexical", run_id
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return "timestamp", parsed.astimezone(timezone.utc)


def _compare_runs(candidate: str, reference: str) -> int:
    candidate_kind, candidate_value = _run_order_key(candidate)
    reference_kind, reference_value = _run_order_key(reference)
    if candidate_kind != reference_kind:
        raise InvalidPublication("provider run identifiers use incompatible ordering formats")
    return (candidate_value > reference_value) - (candidate_value < reference_value)


class LocalPublisher:
    """Publish immutable run objects, then a manifest, then a CAS latest pointer."""

    def __init__(
        self,
        object_store: SQLiteObjectStore,
        *,
        prefix: str = "weather/v1",
        max_cas_attempts: int = 8,
        max_object_bytes: int = 16 * 1024 * 1024,
        max_run_bytes: int = 256 * 1024 * 1024,
    ) -> None:
        if not hasattr(object_store, "put") or not hasattr(object_store, "compare_and_swap"):
            raise TypeError("object_store does not implement the required operations")
        normalized_prefix = str(prefix or "").strip().strip("/")
        if not normalized_prefix or any(
            part in {"", ".", ".."} or not _SEGMENT.fullmatch(part)
            for part in normalized_prefix.split("/")
        ):
            raise ValueError("invalid publication prefix")
        if max_cas_attempts < 1:
            raise ValueError("max_cas_attempts must be positive")
        if (
            not isinstance(max_object_bytes, int)
            or isinstance(max_object_bytes, bool)
            or max_object_bytes < 1
            or not isinstance(max_run_bytes, int)
            or isinstance(max_run_bytes, bool)
            or max_run_bytes < 1
        ):
            raise ValueError("publication byte caps must be positive integers")
        self.store = object_store
        self.prefix = normalized_prefix
        self.max_cas_attempts = int(max_cas_attempts)
        self.max_object_bytes = max_object_bytes
        self.max_run_bytes = max_run_bytes

    def object_key(self, provider: str, run_id: str, logical_key: str) -> str:
        return (
            f"{self.prefix}/{_safe_segment(provider, label='provider')}/runs/"
            f"{_safe_segment(run_id, label='run id')}/objects/{_safe_logical_key(logical_key)}"
        )

    def manifest_key(self, provider: str, run_id: str) -> str:
        return (
            f"{self.prefix}/{_safe_segment(provider, label='provider')}/runs/"
            f"{_safe_segment(run_id, label='run id')}/manifest.json"
        )

    def latest_key(self, provider: str) -> str:
        return f"{self.prefix}/{_safe_segment(provider, label='provider')}/latest.json"

    def revocation_key(self, provider: str, run_id: str) -> str:
        return (
            f"{self.prefix}/{_safe_segment(provider, label='provider')}/revocations/"
            f"{_safe_segment(run_id, label='run id')}.json"
        )

    @staticmethod
    def _coerce_objects(
        objects: Mapping[str, object] | Iterable[PublicationObject | tuple[str, bytes]],
    ) -> list[PublicationObject]:
        values: list[PublicationObject] = []
        if isinstance(objects, Mapping):
            source = objects.items()
            for raw_key, raw_value in source:
                logical_key = _safe_logical_key(raw_key)
                if isinstance(raw_value, PublicationObject):
                    if _safe_logical_key(raw_value.key) != logical_key:
                        raise InvalidPublication("mapping key and publication object key differ")
                    values.append(raw_value)
                elif isinstance(raw_value, (bytes, bytearray, memoryview)):
                    values.append(PublicationObject(logical_key, bytes(raw_value)))
                else:
                    raise InvalidPublication("mapping values must be bytes or PublicationObject")
        else:
            for raw_value in objects:
                if isinstance(raw_value, PublicationObject):
                    values.append(raw_value)
                elif (
                    isinstance(raw_value, tuple)
                    and len(raw_value) == 2
                    and isinstance(raw_value[1], (bytes, bytearray, memoryview))
                ):
                    values.append(PublicationObject(str(raw_value[0]), bytes(raw_value[1])))
                else:
                    raise InvalidPublication("invalid publication object")

        normalized: list[PublicationObject] = []
        seen: set[str] = set()
        for item in values:
            logical_key = _safe_logical_key(item.key)
            if logical_key in seen:
                raise InvalidPublication(f"duplicate logical object key: {logical_key}")
            if not isinstance(item.body, (bytes, bytearray, memoryview)):
                raise InvalidPublication(f"object body is not bytes: {logical_key}")
            content_type = str(item.content_type or "").strip()
            if not content_type:
                raise InvalidPublication(f"object content type is empty: {logical_key}")
            seen.add(logical_key)
            normalized.append(
                PublicationObject(
                    key=logical_key,
                    body=bytes(item.body),
                    content_type=content_type,
                    metadata=_string_metadata(item.metadata),
                )
            )
        return sorted(normalized, key=lambda item: item.key)

    def _verify_object(
        self,
        key: str,
        body: bytes,
        content_type: str,
        metadata: Mapping[str, str],
        expected_head: ObjectHead | None = None,
    ) -> ObjectHead:
        head = self.store.head(key)
        stored = self.store.get(key)
        expected_sha256 = hashlib.sha256(body).hexdigest()
        if (
            head != stored.head
            or stored.body != body
            or head.byte_length != len(body)
            or head.sha256 != expected_sha256
            or head.content_type != content_type
            or head.metadata != dict(metadata)
            or (expected_head is not None and head != expected_head)
        ):
            raise PublicationVerificationError(f"published object verification failed: {key}")
        return head

    def _write_immutable(
        self,
        key: str,
        body: bytes,
        *,
        content_type: str,
        metadata: Mapping[str, str],
    ) -> tuple[ObjectHead, bool]:
        try:
            written = self.store.put(
                key,
                body,
                content_type=content_type,
                metadata=metadata,
            )
            reused = False
        except PreconditionFailed as error:
            try:
                existing = self.store.get(key)
            except ObjectNotFound as missing:
                raise PublicationError(f"object disappeared after create conflict: {key}") from missing
            if (
                existing.body != body
                or existing.content_type != content_type
                or existing.metadata != dict(metadata)
            ):
                raise ImmutableObjectConflict(f"immutable object conflicts: {key}") from error
            written = existing.head
            reused = True
        return self._verify_object(key, body, content_type, metadata, written), reused

    def _read_latest(self, provider: str) -> tuple[dict[str, object], ObjectHead] | None:
        key = self.latest_key(provider)
        try:
            stored = self.store.get(key)
        except ObjectNotFound:
            return None
        payload = _decode_json(stored.body, label="latest pointer")
        if payload.get("schema_version") != 1 or payload.get("provider") != provider:
            raise PublicationVerificationError(f"latest pointer identity is invalid: {key}")
        run_id = payload.get("run_id")
        high_water = payload.get("high_water_run_id")
        manifest_key = payload.get("manifest_key")
        manifest_sha256 = payload.get("manifest_sha256")
        manifest_etag = payload.get("manifest_etag")
        if (
            not isinstance(run_id, str)
            or not isinstance(high_water, str)
            or not isinstance(manifest_key, str)
            or not isinstance(manifest_sha256, str)
            or not isinstance(manifest_etag, str)
            or payload.get("status") not in {"active", "revoked"}
        ):
            raise PublicationVerificationError(f"latest pointer run identity is invalid: {key}")
        if _compare_runs(high_water, run_id) < 0:
            raise PublicationVerificationError(f"latest pointer regresses its high-water mark: {key}")
        try:
            manifest = self.store.get(manifest_key)
        except ObjectNotFound as error:
            raise PublicationVerificationError(f"latest manifest is missing: {manifest_key}") from error
        if manifest.sha256 != manifest_sha256 or manifest.etag != manifest_etag:
            raise PublicationVerificationError(f"latest manifest identity does not match: {manifest_key}")
        manifest_payload = _decode_json(manifest.body, label="run manifest")
        if (
            manifest_payload.get("provider") != provider
            or manifest_payload.get("run_id") != run_id
        ):
            raise PublicationVerificationError(f"latest manifest has wrong run identity: {manifest_key}")
        return payload, stored.head

    def _verify_latest_after_cas(
        self,
        *,
        provider: str,
        run_id: str,
        manifest_key: str,
        manifest_sha256: str,
        body: bytes,
        metadata: Mapping[str, str],
        written: ObjectHead,
    ) -> tuple[ObjectHead, bool]:
        """Verify our pointer or accept a valid pointer that already advanced.

        A successful CAS is allowed to be immediately superseded by another
        publisher. That is not a failed write. A same/older conflicting pointer
        remains a hard failure.
        """

        key = self.latest_key(provider)
        try:
            return (
                self._verify_object(
                    key,
                    body,
                    "application/json",
                    metadata,
                    written,
                ),
                False,
            )
        except PublicationVerificationError as original_error:
            current = self._read_latest(provider)
            if current is None:
                raise original_error
            payload, head = current
            current_run = str(payload["run_id"])
            if current_run == run_id:
                if (
                    payload.get("manifest_key") == manifest_key
                    and payload.get("manifest_sha256") == manifest_sha256
                ):
                    return head, payload.get("status") != "active"
                raise ImmutableObjectConflict(
                    f"latest points to conflicting manifest for run: {run_id}"
                ) from original_error
            if _compare_runs(current_run, run_id) > 0:
                return head, True
            raise PublicationVerificationError(
                f"latest pointer regressed after successful CAS: {key}"
            ) from original_error

    def read_latest(self, provider: str) -> dict[str, object] | None:
        normalized_provider = _safe_segment(provider, label="provider")
        current = self._read_latest(normalized_provider)
        return None if current is None else dict(current[0])

    def publish_run(
        self,
        provider: str,
        run_id: str,
        objects: Mapping[str, object] | Iterable[PublicationObject | tuple[str, bytes]],
        *,
        expected_count: int,
        run_metadata: Mapping[str, object] | None = None,
    ) -> PublicationResult:
        normalized_provider = _safe_segment(provider, label="provider")
        normalized_run_id = _safe_segment(run_id, label="run id")
        normalized_objects = self._coerce_objects(objects)
        if not isinstance(expected_count, int) or isinstance(expected_count, bool) or expected_count < 1:
            raise InvalidPublication("expected_count must be a positive integer")
        if len(normalized_objects) != expected_count:
            raise InvalidPublication(
                f"object count mismatch: expected {expected_count}, received {len(normalized_objects)}"
            )
        normalized_run_metadata = json.loads(_canonical_json(dict(run_metadata or {})))

        # Both limits are checked before the first object-store write. A run is
        # therefore rejected as a unit instead of being partially admitted
        # merely because the oversized member appears late in iteration order.
        oversized = [
            item.key for item in normalized_objects if len(item.body) > self.max_object_bytes
        ]
        total_bytes = sum(len(item.body) for item in normalized_objects)
        if oversized:
            raise PublicationSizeExceeded(
                f"object exceeds max_object_bytes={self.max_object_bytes}: {oversized[0]}"
            )
        if total_bytes > self.max_run_bytes:
            raise PublicationSizeExceeded(
                f"run exceeds max_run_bytes={self.max_run_bytes}: {total_bytes}"
            )
        for item in normalized_objects:
            reserved_overlap = _RESERVED_OBJECT_METADATA.intersection(item.metadata)
            if reserved_overlap:
                raise InvalidPublication(
                    "reserved object metadata supplied: " + ", ".join(sorted(reserved_overlap))
                )

        manifest_entries: list[dict[str, object]] = []
        stored_keys: list[str] = []
        all_reused = True
        for item in normalized_objects:
            digest = hashlib.sha256(item.body).hexdigest()
            custom_metadata = _string_metadata(item.metadata)
            metadata = {
                **custom_metadata,
                "kind": "run-object",
                "provider": normalized_provider,
                "run_id": normalized_run_id,
                "logical_key": item.key,
                "body_sha256": digest,
                "byte_length": str(len(item.body)),
            }
            storage_key = self.object_key(normalized_provider, normalized_run_id, item.key)
            head, reused = self._write_immutable(
                storage_key,
                item.body,
                content_type=item.content_type,
                metadata=metadata,
            )
            all_reused = all_reused and reused
            stored_keys.append(storage_key)
            manifest_entries.append(
                {
                    "logical_key": item.key,
                    "object_key": storage_key,
                    "byte_length": head.byte_length,
                    "sha256": head.sha256,
                    "etag": head.etag,
                    "content_type": head.content_type,
                    "metadata": custom_metadata,
                }
            )

        manifest = {
            "schema_version": 1,
            "provider": normalized_provider,
            "run_id": normalized_run_id,
            "expected_object_count": expected_count,
            "object_count": len(manifest_entries),
            "objects": manifest_entries,
            "run_metadata": normalized_run_metadata,
        }
        manifest_body = _canonical_json(manifest)
        manifest_digest = hashlib.sha256(manifest_body).hexdigest()
        manifest_metadata = {
            "kind": "run-manifest",
            "provider": normalized_provider,
            "run_id": normalized_run_id,
            "body_sha256": manifest_digest,
            "byte_length": str(len(manifest_body)),
            "object_count": str(expected_count),
        }
        manifest_key = self.manifest_key(normalized_provider, normalized_run_id)
        manifest_head, manifest_reused = self._write_immutable(
            manifest_key,
            manifest_body,
            content_type="application/json",
            metadata=manifest_metadata,
        )
        all_reused = all_reused and manifest_reused

        latest_key = self.latest_key(normalized_provider)
        last_precondition: PreconditionFailed | None = None
        for _attempt in range(self.max_cas_attempts):
            current = self._read_latest(normalized_provider)
            current_payload, current_head = current if current is not None else (None, None)
            if current_payload is not None:
                current_run = str(current_payload["run_id"])
                high_water = str(current_payload["high_water_run_id"])
                if current_run == normalized_run_id:
                    if (
                        current_payload.get("manifest_key") != manifest_key
                        or current_payload.get("manifest_sha256") != manifest_digest
                    ):
                        raise ImmutableObjectConflict(
                            f"latest points to conflicting manifest for run: {normalized_run_id}"
                        )
                    return PublicationResult(
                        provider=normalized_provider,
                        run_id=normalized_run_id,
                        object_keys=tuple(stored_keys),
                        manifest_key=manifest_key,
                        manifest_etag=manifest_head.etag,
                        latest_key=latest_key,
                        latest_etag=current_head.etag,
                        idempotent=True,
                        latest_updated=False,
                    )
                if _compare_runs(normalized_run_id, high_water) <= 0:
                    raise StaleRun(
                        f"run {normalized_run_id} cannot replace high-water run {high_water}"
                    )

            latest = {
                "schema_version": 1,
                "provider": normalized_provider,
                "run_id": normalized_run_id,
                "high_water_run_id": normalized_run_id,
                "manifest_key": manifest_key,
                "manifest_sha256": manifest_digest,
                "manifest_etag": manifest_head.etag,
                "status": "active",
            }
            latest_body = _canonical_json(latest)
            latest_metadata = {
                "kind": "latest-pointer",
                "provider": normalized_provider,
                "run_id": normalized_run_id,
            }
            try:
                latest_head = self.store.compare_and_swap(
                    latest_key,
                    latest_body,
                    expected_etag=None if current_head is None else current_head.etag,
                    content_type="application/json",
                    metadata=latest_metadata,
                )
            except PreconditionFailed as error:
                last_precondition = error
                continue
            observed_latest_head, superseded = self._verify_latest_after_cas(
                provider=normalized_provider,
                run_id=normalized_run_id,
                manifest_key=manifest_key,
                manifest_sha256=manifest_digest,
                body=latest_body,
                metadata=latest_metadata,
                written=latest_head,
            )
            return PublicationResult(
                provider=normalized_provider,
                run_id=normalized_run_id,
                object_keys=tuple(stored_keys),
                manifest_key=manifest_key,
                manifest_etag=manifest_head.etag,
                latest_key=latest_key,
                latest_etag=observed_latest_head.etag,
                idempotent=all_reused,
                latest_updated=True,
                superseded=superseded,
            )
        assert last_precondition is not None
        raise last_precondition

    publish = publish_run

    def revoke_run(self, provider: str, run_id: str, *, reason: str) -> RevocationResult:
        """Write an immutable revocation and mark latest if it selects this run."""

        normalized_provider = _safe_segment(provider, label="provider")
        normalized_run_id = _safe_segment(run_id, label="run id")
        normalized_reason = str(reason or "").strip()
        if not normalized_reason or len(normalized_reason) > 500:
            raise InvalidPublication("revocation reason must contain 1 to 500 characters")
        manifest_key = self.manifest_key(normalized_provider, normalized_run_id)
        try:
            manifest = self.store.get(manifest_key)
        except ObjectNotFound as error:
            raise InvalidPublication(f"cannot revoke missing run: {normalized_run_id}") from error

        marker = {
            "schema_version": 1,
            "provider": normalized_provider,
            "run_id": normalized_run_id,
            "manifest_key": manifest_key,
            "manifest_sha256": manifest.sha256,
            "reason": normalized_reason,
            "status": "revoked",
        }
        marker_body = _canonical_json(marker)
        marker_key = self.revocation_key(normalized_provider, normalized_run_id)
        _marker_head, marker_reused = self._write_immutable(
            marker_key,
            marker_body,
            content_type="application/json",
            metadata={
                "kind": "revocation",
                "provider": normalized_provider,
                "run_id": normalized_run_id,
            },
        )

        last_precondition: PreconditionFailed | None = None
        for _attempt in range(self.max_cas_attempts):
            current = self._read_latest(normalized_provider)
            if current is None:
                return RevocationResult(
                    normalized_provider, normalized_run_id, marker_key, False, marker_reused
                )
            payload, head = current
            if payload["run_id"] != normalized_run_id:
                return RevocationResult(
                    normalized_provider, normalized_run_id, marker_key, False, marker_reused
                )
            if payload.get("status") == "revoked":
                if payload.get("revocation_key") != marker_key:
                    raise ImmutableObjectConflict("latest contains a conflicting revocation")
                return RevocationResult(
                    normalized_provider, normalized_run_id, marker_key, False, True
                )
            revoked_latest = {
                **payload,
                "status": "revoked",
                "revocation_key": marker_key,
            }
            body = _canonical_json(revoked_latest)
            metadata = {
                "kind": "latest-pointer",
                "provider": normalized_provider,
                "run_id": normalized_run_id,
                "status": "revoked",
            }
            try:
                written = self.store.compare_and_swap(
                    self.latest_key(normalized_provider),
                    body,
                    expected_etag=head.etag,
                    content_type="application/json",
                    metadata=metadata,
                )
            except PreconditionFailed as error:
                last_precondition = error
                continue
            self._verify_object(
                self.latest_key(normalized_provider),
                body,
                "application/json",
                metadata,
                written,
            )
            return RevocationResult(
                normalized_provider, normalized_run_id, marker_key, True, marker_reused
            )
        assert last_precondition is not None
        raise last_precondition

    revoke = revoke_run


Publisher = LocalPublisher


__all__ = [
    "ImmutableObjectConflict",
    "InvalidPublication",
    "LocalPublisher",
    "ManifestConflict",
    "PublicationError",
    "PublicationObject",
    "PublicationResult",
    "PublicationSizeExceeded",
    "PublicationVerificationError",
    "PublishObject",
    "Publisher",
    "RevocationResult",
    "StaleRun",
    "StaleRunError",
]
