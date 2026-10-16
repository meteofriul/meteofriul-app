from __future__ import annotations

import hashlib
import os
import re
import uuid
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Callable


PUSH_DEVICES_COLLECTION = "push_devices"
PUSH_OUTBOX_COLLECTION = "push_official_alert_outbox"
PUSH_LOCAL_NOTICE_OUTBOX_COLLECTION = "push_local_notice_outbox"
PUSH_STATE_COLLECTION = "push_pilot_state"
PUSH_TARGET_OWNERS_COLLECTION = "push_target_owners"
PUSH_DEVICE_CAPACITY_DOCUMENT = "device_capacity"
PUSH_DEVICE_SCHEMA_VERSION = "2.1"
PUSH_FIRESTORE_TIMEOUT_SECONDS = float(
    os.getenv("PUSH_FIRESTORE_TIMEOUT_SECONDS", "5")
)
PUSH_TRANSIENT_RETRY_DELAY_SECONDS = 15 * 60
PUSH_DELIVERY_LEASE_SECONDS = 15 * 60
PUSH_MAX_DELIVERY_ATTEMPTS = 3
PUSH_OFFICIAL_ALERT_OUTBOX_RETENTION_DAYS = 30
PUSH_LOCAL_NOTICE_OUTBOX_RETENTION_DAYS = 14
PUSH_INACTIVE_DEVICE_RETENTION_DAYS = 30
PUSH_TARGET_FCM_TOKEN = "fcm_token"
PUSH_TARGET_FIREBASE_INSTALLATION_ID = "firebase_installation_id"
_ENROLLMENT_GENERATION_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,63}$")


class PushRepositoryUnavailable(RuntimeError):
    """Firestore could not durably perform a required push operation."""


class PushPilotCapacityReached(RuntimeError):
    """The private pilot device cap has been reached."""


class PushTargetAlreadyRegistered(RuntimeError):
    """An active device already owns the same FCM delivery target."""


@dataclass(frozen=True)
class PushDeviceUpsertResult:
    device: dict[str, Any]
    created: bool


@dataclass(frozen=True)
class PushDeviceReadResult:
    devices: list[dict[str, Any]]
    pages_processed: int


@dataclass(frozen=True)
class PushDeliveryClaim:
    delivery_id: str
    claimed: bool
    state: str
    claim_id: str = ""
    target_kind: str = ""
    target_hash: str = ""


def hash_installation_id(installation_id: str) -> str:
    normalized = str(installation_id or "").strip().lower()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def hash_push_target(value: str) -> str:
    return hashlib.sha256(str(value or "").encode("utf-8")).hexdigest()


def hash_push_token(token: str) -> str:
    """Backward-compatible name for hashing a delivery target."""

    return hash_push_target(token)


def resolve_push_target(device: dict[str, Any]) -> tuple[str, str, str]:
    """Read schema v2 targets while accepting deployed schema v1 Android rows."""

    schema_version = str(device.get("schema_version") or "")
    legacy_token = str(device.get("token") or "")
    if schema_version.startswith("1.") and legacy_token:
        return (
            PUSH_TARGET_FCM_TOKEN,
            legacy_token,
            str(device.get("token_hash") or hash_push_target(legacy_token)),
        )

    target_kind = str(device.get("target_kind") or "")
    target_value = str(device.get("target_value") or "")
    if target_kind and target_value:
        return (
            target_kind,
            target_value,
            str(device.get("target_hash") or hash_push_target(target_value)),
        )
    target_hash = str(device.get("target_hash") or "")
    if target_kind and target_hash:
        return target_kind, "", target_hash
    if legacy_token:
        return (
            PUSH_TARGET_FCM_TOKEN,
            legacy_token,
            str(device.get("token_hash") or hash_push_target(legacy_token)),
        )
    legacy_hash = str(device.get("token_hash") or "")
    if legacy_hash:
        return PUSH_TARGET_FCM_TOKEN, "", legacy_hash
    return "", "", ""


def _outbox_target(existing: dict[str, Any]) -> tuple[str, str]:
    target_hash = str(
        existing.get("target_hash") or existing.get("token_hash") or ""
    )
    target_kind = str(existing.get("target_kind") or "")
    if target_hash and not target_kind:
        target_kind = PUSH_TARGET_FCM_TOKEN
    return target_kind, target_hash


def push_delivery_id(device_id: str, alert_signature: str) -> str:
    raw = f"official-alert:{device_id}:{alert_signature}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def local_notice_delivery_id(device_id: str, notice_signature: str) -> str:
    raw = f"local-notice:{device_id}:{notice_signature}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _snapshot_data(snapshot: Any) -> dict[str, Any]:
    if snapshot is None or not getattr(snapshot, "exists", False):
        return {}
    return dict(snapshot.to_dict() or {})


def _capacity_document_id(enrollment_generation: str = "") -> str:
    generation = str(enrollment_generation or "").strip().lower()
    if not generation:
        return PUSH_DEVICE_CAPACITY_DOCUMENT
    if not _ENROLLMENT_GENERATION_RE.fullmatch(generation):
        raise ValueError("invalid_push_enrollment_generation")
    return f"{PUSH_DEVICE_CAPACITY_DOCUMENT}__{generation}"


def _fcm_target_owner_document(db: Any, target_kind: str, target_hash: str) -> Any | None:
    if target_kind != PUSH_TARGET_FCM_TOKEN or not target_hash:
        return None
    return db.collection(PUSH_TARGET_OWNERS_COLLECTION).document(target_hash)


class PushDeviceRepository:
    """Strict Firestore storage for push targets and an at-most-once outbox."""

    def __init__(
        self,
        firestore_provider: Callable[[], Any | None],
        *,
        transactional_decorator: Callable[[Callable[..., Any]], Callable[..., Any]] | None = None,
        operation_timeout_seconds: float = PUSH_FIRESTORE_TIMEOUT_SECONDS,
    ) -> None:
        self._firestore_provider = firestore_provider
        self._transactional_decorator = transactional_decorator
        self._operation_timeout_seconds = max(0.1, float(operation_timeout_seconds))

    def _db(self) -> Any:
        try:
            db = self._firestore_provider()
        except Exception as error:
            raise PushRepositoryUnavailable("push_firestore_unavailable") from error
        if db is None:
            raise PushRepositoryUnavailable("push_firestore_unavailable")
        return db

    def _run_transaction(self, operation: Callable[..., Any], transaction: Any) -> Any:
        decorator = self._transactional_decorator
        if decorator is None:
            try:
                from google.cloud import firestore
            except ImportError as error:
                raise PushRepositoryUnavailable("push_firestore_unavailable") from error
            decorator = firestore.transactional
        return decorator(operation)(transaction)

    def upsert_device(
        self,
        *,
        device_id: str,
        platform: str,
        app_version: str,
        language: str,
        municipality: dict[str, Any] | None,
        locality: dict[str, Any] | None = None,
        location_mode: str | None = None,
        location_evidence: dict[str, Any] | None = None,
        preferences: dict[str, bool],
        max_devices: int,
        now: datetime,
        token: str = "",
        target_kind: str = "",
        target_value: str = "",
        app_check_app_id: str = "",
        enrollment_mode: str = "",
        enrollment_generation: str = "",
    ) -> PushDeviceUpsertResult:
        resolved_kind = str(target_kind or PUSH_TARGET_FCM_TOKEN)
        resolved_value = str(target_value or token)
        valid_pair = (
            platform == "android"
            and resolved_kind == PUSH_TARGET_FCM_TOKEN
        ) or (
            platform == "web"
            and resolved_kind == PUSH_TARGET_FIREBASE_INSTALLATION_ID
        )
        if not resolved_value or not valid_pair:
            raise ValueError("invalid_push_delivery_target")
        resolved_hash = hash_push_target(resolved_value)

        db = self._db()
        device_document = db.collection(PUSH_DEVICES_COLLECTION).document(device_id)
        normalized_generation = str(enrollment_generation or "").strip().lower()
        capacity_limited = str(enrollment_mode or "").strip().lower() != "play_beta"
        capacity_document = db.collection(PUSH_STATE_COLLECTION).document(
            _capacity_document_id(normalized_generation)
        )
        target_owner_document = _fcm_target_owner_document(
            db,
            resolved_kind,
            resolved_hash,
        )
        transaction = db.transaction()

        def persist(transaction_in_progress: Any) -> PushDeviceUpsertResult:
            device_snapshot = device_document.get(transaction=transaction_in_progress)
            capacity_snapshot = (
                capacity_document.get(transaction=transaction_in_progress)
                if capacity_limited
                else None
            )
            existing = _snapshot_data(device_snapshot)
            capacity = _snapshot_data(capacity_snapshot)
            previous_generation = str(
                existing.get("enrollment_generation") or ""
            ).strip().lower()
            previous_capacity_document = None
            previous_capacity = {}
            if existing and previous_generation != normalized_generation:
                previous_capacity_document = db.collection(
                    PUSH_STATE_COLLECTION
                ).document(_capacity_document_id(previous_generation))
                previous_capacity = _snapshot_data(
                    previous_capacity_document.get(
                        transaction=transaction_in_progress
                    )
                )
            previous_kind, _, previous_hash = resolve_push_target(existing)
            previous_owner_document = _fcm_target_owner_document(
                db,
                previous_kind,
                previous_hash,
            )
            target_owner = {}
            target_owner_device = {}
            if target_owner_document is not None:
                target_owner = _snapshot_data(
                    target_owner_document.get(transaction=transaction_in_progress)
                )
                target_owner_device_id = str(target_owner.get("device_id") or "")
                if target_owner_device_id and target_owner_device_id != device_id:
                    target_owner_device = _snapshot_data(
                        db.collection(PUSH_DEVICES_COLLECTION)
                        .document(target_owner_device_id)
                        .get(transaction=transaction_in_progress)
                    )
            previous_owner = {}
            if (
                previous_owner_document is not None
                and (
                    target_owner_document is None
                    or previous_owner_document.id != target_owner_document.id
                )
            ):
                previous_owner = _snapshot_data(
                    previous_owner_document.get(transaction=transaction_in_progress)
                )

            target_owner_device_id = str(target_owner.get("device_id") or "")
            if target_owner_device_id and target_owner_device_id != device_id:
                owner_kind, _, owner_hash = resolve_push_target(target_owner_device)
                if (
                    target_owner_device.get("active") is True
                    and owner_kind == PUSH_TARGET_FCM_TOKEN
                    and owner_hash == resolved_hash
                ):
                    raise PushTargetAlreadyRegistered(
                        "push_target_already_registered"
                    )
            active_ids = {
                str(item)
                for item in capacity.get("active_device_ids") or []
                if str(item)
            }
            created = not bool(existing)

            if capacity_limited and device_id not in active_ids:
                if len(active_ids) >= max_devices:
                    raise PushPilotCapacityReached("push_pilot_capacity_reached")
                active_ids.add(device_id)

            created_at = existing.get("created_at") or now
            device = {
                "schema_version": PUSH_DEVICE_SCHEMA_VERSION,
                "device_id": device_id,
                "target_kind": resolved_kind,
                "target_value": resolved_value,
                "target_hash": resolved_hash,
                # Android is dual-written during the schema-v1 rolling cutover.
                "token": (
                    resolved_value if resolved_kind == PUSH_TARGET_FCM_TOKEN else ""
                ),
                "token_hash": (
                    resolved_hash if resolved_kind == PUSH_TARGET_FCM_TOKEN else ""
                ),
                "platform": platform,
                "app_check_app_id": str(app_check_app_id or "")[:200],
                "enrollment_mode": str(enrollment_mode or "")[:40],
                "enrollment_generation": normalized_generation,
                "app_version": app_version,
                "language": language,
                "municipality": deepcopy(municipality),
                "locality": deepcopy(locality),
                "location_mode": str(location_mode or ""),
                "location_evidence": deepcopy(location_evidence),
                "preferences": dict(preferences),
                "active": True,
                "created_at": created_at,
                "updated_at": now,
                "last_seen_at": now,
                "disabled_reason": "",
                # A previously invalid target can be enrolled again with a new
                # FCM token.  Firestore TTL ignores null values, so clearing the
                # old deadline prevents the reactivated device from being
                # deleted by the inactive-device retention policy.
                "expires_at": None,
            }
            transaction_in_progress.set(device_document, device, merge=True)
            if target_owner_document is not None:
                transaction_in_progress.set(
                    target_owner_document,
                    {
                        "target_kind": resolved_kind,
                        "target_hash": resolved_hash,
                        "device_id": device_id,
                        "updated_at": now,
                    },
                )
            if (
                previous_owner_document is not None
                and (
                    target_owner_document is None
                    or previous_owner_document.id != target_owner_document.id
                )
                and str(previous_owner.get("device_id") or "") == device_id
            ):
                transaction_in_progress.delete(previous_owner_document)
            if capacity_limited:
                transaction_in_progress.set(
                    capacity_document,
                    {
                        "enrollment_generation": normalized_generation,
                        "active_device_ids": sorted(active_ids),
                        "active_count": len(active_ids),
                        "configured_max_devices": max_devices,
                        "updated_at": now,
                    },
                    merge=True,
                )
            if previous_capacity_document is not None:
                previous_active_ids = {
                    str(item)
                    for item in previous_capacity.get("active_device_ids") or []
                    if str(item)
                }
                previous_active_ids.discard(device_id)
                transaction_in_progress.set(
                    previous_capacity_document,
                    {
                        "enrollment_generation": previous_generation,
                        "active_device_ids": sorted(previous_active_ids),
                        "active_count": len(previous_active_ids),
                        "updated_at": now,
                    },
                    merge=True,
                )
            return PushDeviceUpsertResult(device=deepcopy(device), created=created)

        try:
            return self._run_transaction(persist, transaction)
        except (PushPilotCapacityReached, PushTargetAlreadyRegistered):
            raise
        except Exception as error:
            raise PushRepositoryUnavailable(
                "push_device_upsert_transaction_failed"
            ) from error

    def unregister_device(
        self,
        *,
        device_id: str,
        now: datetime,
        expected_platform: str = "",
        expected_target_kind: str = "",
        expected_target_hash: str = "",
        expected_app_check_app_id: str = "",
        expected_enrollment_generation: str = "",
    ) -> bool:
        db = self._db()
        device_document = db.collection(PUSH_DEVICES_COLLECTION).document(device_id)
        transaction = db.transaction()

        def remove(transaction_in_progress: Any) -> bool:
            device_snapshot = device_document.get(transaction=transaction_in_progress)
            device = _snapshot_data(device_snapshot)
            generation = str(
                device.get("enrollment_generation")
                or expected_enrollment_generation
                or ""
            ).strip().lower()
            capacity_document = db.collection(PUSH_STATE_COLLECTION).document(
                _capacity_document_id(generation)
            )
            capacity_snapshot = capacity_document.get(
                transaction=transaction_in_progress
            )
            capacity = _snapshot_data(capacity_snapshot)
            current_kind, _, current_hash = resolve_push_target(device)
            target_owner_document = _fcm_target_owner_document(
                db,
                current_kind,
                current_hash,
            )
            target_owner = (
                _snapshot_data(
                    target_owner_document.get(transaction=transaction_in_progress)
                )
                if target_owner_document is not None
                else {}
            )
            active_ids = {
                str(item)
                for item in capacity.get("active_device_ids") or []
                if str(item)
            }
            if not device:
                if device_id in active_ids:
                    active_ids.discard(device_id)
                    transaction_in_progress.set(
                        capacity_document,
                        {
                            "active_device_ids": sorted(active_ids),
                            "active_count": len(active_ids),
                            "updated_at": now,
                        },
                        merge=True,
                    )
                return False
            if expected_platform and str(device.get("platform") or "") != expected_platform:
                return False
            if (
                expected_app_check_app_id
                and str(device.get("app_check_app_id") or "")
                != expected_app_check_app_id
            ):
                return False
            if (
                expected_enrollment_generation
                and generation != expected_enrollment_generation
            ):
                return False
            if expected_target_kind and current_kind != expected_target_kind:
                return False
            if expected_target_hash and current_hash != expected_target_hash:
                return False
            active_ids.discard(device_id)
            transaction_in_progress.delete(device_document)
            if (
                target_owner_document is not None
                and str(target_owner.get("device_id") or "") == device_id
            ):
                transaction_in_progress.delete(target_owner_document)
            transaction_in_progress.set(
                capacity_document,
                {
                    "active_device_ids": sorted(active_ids),
                    "active_count": len(active_ids),
                    "updated_at": now,
                },
                merge=True,
            )
            return True

        try:
            return bool(self._run_transaction(remove, transaction))
        except Exception as error:
            raise PushRepositoryUnavailable(
                "push_device_unregister_transaction_failed"
            ) from error

    def update_android_location_target(
        self,
        *,
        device_id: str,
        app_check_app_id: str,
        expected_enrollment_generation: str = "",
        municipality: dict[str, Any] | None,
        locality: dict[str, Any] | None,
        location_evidence: dict[str, Any] | None,
        now: datetime,
    ) -> dict[str, Any] | None:
        """Atomically refresh only canonical location fields for one device.

        Raw coordinates never enter Firestore.  A missing or mismatched device
        is indistinguishable to callers and therefore cannot be enrolled by
        the background endpoint.
        """

        db = self._db()
        device_document = db.collection(PUSH_DEVICES_COLLECTION).document(device_id)
        transaction = db.transaction()

        def persist(transaction_in_progress: Any) -> dict[str, Any] | None:
            existing = _snapshot_data(
                device_document.get(transaction=transaction_in_progress)
            )
            if (
                not existing
                or existing.get("active") is not True
                or str(existing.get("platform") or "") != "android"
            ):
                return None
            expected_app_id = str(app_check_app_id or "")
            stored_app_id = str(existing.get("app_check_app_id") or "")
            if expected_app_id and stored_app_id != expected_app_id:
                return None
            if (
                expected_enrollment_generation
                and str(existing.get("enrollment_generation") or "")
                != expected_enrollment_generation
            ):
                return None

            patch = {
                "municipality": deepcopy(municipality),
                "locality": deepcopy(locality),
                "location_mode": "automatic_gps" if location_evidence else "",
                "location_evidence": deepcopy(location_evidence),
                "last_seen_at": now,
                "updated_at": now,
            }
            transaction_in_progress.set(device_document, patch, merge=True)
            return {**deepcopy(existing), **deepcopy(patch)}

        try:
            return self._run_transaction(persist, transaction)
        except Exception as error:
            raise PushRepositoryUnavailable(
                "push_device_location_transaction_failed"
            ) from error

    def disable_device(
        self,
        *,
        device_id: str,
        expected_token_hash: str = "",
        expected_target_kind: str = "",
        expected_target_hash: str = "",
        reason: str,
        now: datetime,
    ) -> bool:
        db = self._db()
        device_document = db.collection(PUSH_DEVICES_COLLECTION).document(device_id)
        transaction = db.transaction()

        def disable(transaction_in_progress: Any) -> bool:
            device_snapshot = device_document.get(transaction=transaction_in_progress)
            device = _snapshot_data(device_snapshot)
            if not device:
                return False
            enrollment_generation = str(
                device.get("enrollment_generation") or ""
            ).strip().lower()
            capacity_limited = not enrollment_generation
            capacity_document = db.collection(PUSH_STATE_COLLECTION).document(
                _capacity_document_id(enrollment_generation)
            )
            capacity_snapshot = (
                capacity_document.get(transaction=transaction_in_progress)
                if capacity_limited
                else None
            )
            current_kind, _, current_hash = resolve_push_target(device)
            target_owner_document = _fcm_target_owner_document(
                db,
                current_kind,
                current_hash,
            )
            target_owner = (
                _snapshot_data(
                    target_owner_document.get(transaction=transaction_in_progress)
                )
                if target_owner_document is not None
                else {}
            )
            required_hash = expected_target_hash or expected_token_hash
            required_kind = expected_target_kind or (
                PUSH_TARGET_FCM_TOKEN if expected_token_hash else ""
            )
            if required_kind and current_kind != required_kind:
                return False
            if required_hash and current_hash != required_hash:
                return False
            capacity = _snapshot_data(capacity_snapshot)
            active_ids = {
                str(item)
                for item in capacity.get("active_device_ids") or []
                if str(item)
            }
            active_ids.discard(device_id)
            disabled_reason = str(reason or "delivery_failed")[:80]
            patch = {
                "active": False,
                "target_value": "",
                "token": "",
                "disabled_reason": disabled_reason,
                "updated_at": now,
            }
            if disabled_reason == "fcm_token_invalid":
                patch["expires_at"] = now + timedelta(
                    days=PUSH_INACTIVE_DEVICE_RETENTION_DAYS
                )
            transaction_in_progress.set(
                device_document,
                patch,
                merge=True,
            )
            if (
                target_owner_document is not None
                and str(target_owner.get("device_id") or "") == device_id
            ):
                transaction_in_progress.delete(target_owner_document)
            if capacity_limited:
                transaction_in_progress.set(
                    capacity_document,
                    {
                        "active_device_ids": sorted(active_ids),
                        "active_count": len(active_ids),
                        "updated_at": now,
                    },
                    merge=True,
                )
            return True

        try:
            return bool(self._run_transaction(disable, transaction))
        except Exception as error:
            raise PushRepositoryUnavailable("push_device_disable_failed") from error

    def read_active_devices(
        self,
        *,
        max_devices: int,
        enrollment_generation: str | None = None,
    ) -> PushDeviceReadResult:
        db = self._db()
        try:
            devices = []
            pages_processed = 0
            collection = db.collection(PUSH_DEVICES_COLLECTION)
            page_size = max(1, int(max_devices))
            if all(
                hasattr(collection, method)
                for method in ("order_by",)
            ):
                base_query = collection.order_by("__name__")
                cursor = None
                while True:
                    query = base_query.limit(page_size)
                    if cursor is not None:
                        query = query.start_after(cursor)
                    documents = list(query.stream(
                        retry=None,
                        timeout=self._operation_timeout_seconds,
                    ))
                    if not documents:
                        break
                    pages_processed += 1
                    for document in documents:
                        device = dict(document.to_dict() or {})
                        if (
                            device.get("active") is True
                            and (
                                enrollment_generation is None
                                or str(device.get("enrollment_generation") or "")
                                == enrollment_generation
                            )
                        ):
                            devices.append(device)
                    if len(documents) < page_size:
                        break
                    cursor = documents[-1]
            else:
                # In-memory repositories used by local tests do not expose the
                # Firestore query cursor API. Production always takes the
                # explicitly paginated branch above.
                documents = list(collection.stream(
                    retry=None,
                    timeout=self._operation_timeout_seconds,
                ))
                for offset in range(0, len(documents), page_size):
                    pages_processed += 1
                    for document in documents[offset:offset + page_size]:
                        device = dict(document.to_dict() or {})
                        if (
                            device.get("active") is True
                            and (
                                enrollment_generation is None
                                or str(device.get("enrollment_generation") or "")
                                == enrollment_generation
                            )
                        ):
                            devices.append(device)
        except Exception as error:
            raise PushRepositoryUnavailable("push_device_list_failed") from error

        if enrollment_generation is not None:
            seen_fcm_targets: set[str] = set()
            for device in devices:
                target_kind, _, target_hash = resolve_push_target(device)
                if target_kind != PUSH_TARGET_FCM_TOKEN or not target_hash:
                    continue
                if target_hash in seen_fcm_targets:
                    raise PushRepositoryUnavailable(
                        "push_duplicate_fcm_target_detected"
                    )
                seen_fcm_targets.add(target_hash)

        if enrollment_generation is None and len(devices) > max_devices:
            raise PushRepositoryUnavailable("push_device_capacity_state_invalid")
        return PushDeviceReadResult(
            devices=devices,
            pages_processed=pages_processed,
        )

    def list_active_devices(
        self,
        *,
        max_devices: int,
        enrollment_generation: str | None = None,
    ) -> list[dict[str, Any]]:
        return self.read_active_devices(
            max_devices=max_devices,
            enrollment_generation=enrollment_generation,
        ).devices

    def claim_official_alert_delivery(
        self,
        *,
        device_id: str,
        alert_signature: str,
        alert_id: str,
        token_hash: str = "",
        target_kind: str = "",
        target_hash: str = "",
        expected_enrollment_generation: str = "",
        expected_app_check_app_id: str = "",
        expected_app_version: str = "",
        now: datetime,
    ) -> PushDeliveryClaim:
        required_hash = str(target_hash or token_hash)
        required_kind = str(
            target_kind or (PUSH_TARGET_FCM_TOKEN if required_hash else "")
        )
        db = self._db()
        delivery_id = push_delivery_id(device_id, alert_signature)
        document = db.collection(PUSH_OUTBOX_COLLECTION).document(delivery_id)
        device_document = db.collection(PUSH_DEVICES_COLLECTION).document(device_id)
        transaction = db.transaction()

        def claim(transaction_in_progress: Any) -> PushDeliveryClaim:
            if required_hash:
                device = _snapshot_data(
                    device_document.get(transaction=transaction_in_progress)
                )
                if device.get("active") is not True:
                    return PushDeliveryClaim(
                        delivery_id=delivery_id,
                        claimed=False,
                        state="device_inactive",
                    )
                if (
                    expected_enrollment_generation
                    and str(device.get("schema_version") or "")
                    != PUSH_DEVICE_SCHEMA_VERSION
                ):
                    return PushDeliveryClaim(
                        delivery_id=delivery_id,
                        claimed=False,
                        state="schema_version_changed",
                    )
                if (
                    expected_enrollment_generation
                    and str(device.get("enrollment_generation") or "")
                    != expected_enrollment_generation
                ):
                    return PushDeliveryClaim(
                        delivery_id=delivery_id,
                        claimed=False,
                        state="enrollment_generation_changed",
                    )
                if (
                    expected_app_check_app_id
                    and str(device.get("app_check_app_id") or "")
                    != expected_app_check_app_id
                ):
                    return PushDeliveryClaim(
                        delivery_id=delivery_id,
                        claimed=False,
                        state="app_check_app_changed",
                    )
                if (
                    expected_app_version
                    and str(device.get("app_version") or "").strip().lower()
                    != expected_app_version
                ):
                    return PushDeliveryClaim(
                        delivery_id=delivery_id,
                        claimed=False,
                        state="app_version_changed",
                    )
                preferences = device.get("preferences")
                if (
                    not isinstance(preferences, dict)
                    or preferences.get("official_alerts") is not True
                ):
                    return PushDeliveryClaim(
                        delivery_id=delivery_id,
                        claimed=False,
                        state="official_alerts_disabled",
                    )
                current_kind, _, current_hash = resolve_push_target(device)
                if current_kind != required_kind or current_hash != required_hash:
                    return PushDeliveryClaim(
                        delivery_id=delivery_id,
                        claimed=False,
                        state="device_target_changed",
                    )
            snapshot = document.get(transaction=transaction_in_progress)
            existing = _snapshot_data(snapshot)
            if existing:
                state = str(existing.get("state") or "unknown")
                next_retry_at = existing.get("next_retry_at")
                claimed_at = existing.get("claimed_at")
                attempt_count = int(existing.get("attempt_count") or 0)
                existing_kind, existing_hash = _outbox_target(existing)
                target_rotated = bool(
                    required_hash
                    and existing_hash
                    and (required_kind, required_hash)
                    != (existing_kind, existing_hash)
                    and state not in {"sent", "sending", "failed_configuration"}
                )
                retry_due = (
                    isinstance(next_retry_at, datetime)
                    and next_retry_at <= now
                )
                lease_expired = (
                    state == "sending"
                    and isinstance(claimed_at, datetime)
                    and claimed_at + timedelta(seconds=PUSH_DELIVERY_LEASE_SECONDS) <= now
                )
                transient_retry_due = (
                    state == "failed_transient"
                    and retry_due
                    and attempt_count < PUSH_MAX_DELIVERY_ATTEMPTS
                )
                lease_retry_due = (
                    lease_expired
                    and attempt_count < PUSH_MAX_DELIVERY_ATTEMPTS
                )
                configuration_retry_due = (
                    state == "failed_configuration" and retry_due
                )
                if (
                    target_rotated
                    or transient_retry_due
                    or lease_retry_due
                    or configuration_retry_due
                ):
                    next_attempt_count = 1 if target_rotated else attempt_count + 1
                    next_claim_id = uuid.uuid4().hex
                    next_kind = required_kind or existing_kind
                    next_hash = required_hash or existing_hash
                    transaction_in_progress.set(
                        document,
                        {
                            "schema_version": "2.0",
                            "state": "sending",
                            "attempt_count": next_attempt_count,
                            "claimed_at": now,
                            "claim_id": next_claim_id,
                            "updated_at": now,
                            "expires_at": now + timedelta(
                                days=PUSH_OFFICIAL_ALERT_OUTBOX_RETENTION_DAYS
                            ),
                            "next_retry_at": None,
                            "error_code": "",
                            "target_kind": next_kind,
                            "target_hash": next_hash,
                            "token_hash": (
                                next_hash
                                if next_kind == PUSH_TARGET_FCM_TOKEN
                                else ""
                            ),
                        },
                        merge=True,
                    )
                    return PushDeliveryClaim(
                        delivery_id=delivery_id,
                        claimed=True,
                        state="sending",
                        claim_id=next_claim_id,
                        target_kind=next_kind,
                        target_hash=next_hash,
                    )
                if state == "failed_transient":
                    state = (
                        "retry_exhausted"
                        if attempt_count >= PUSH_MAX_DELIVERY_ATTEMPTS
                        else "retry_scheduled"
                    )
                elif state == "sending":
                    state = (
                        "retry_exhausted"
                        if attempt_count >= PUSH_MAX_DELIVERY_ATTEMPTS
                        else "delivery_in_progress"
                    )
                elif state == "failed_configuration":
                    state = "configuration_retry_scheduled"
                return PushDeliveryClaim(
                    delivery_id=delivery_id,
                    claimed=False,
                    state=state,
                )
            claim_id = uuid.uuid4().hex
            transaction_in_progress.set(
                document,
                {
                    "schema_version": "2.0",
                    "kind": "official_alert",
                    "device_id": device_id,
                    "alert_id": str(alert_id or "")[:200],
                    "alert_signature": alert_signature,
                    "state": "sending",
                    "attempt_count": 1,
                    "claimed_at": now,
                    "claim_id": claim_id,
                    "updated_at": now,
                    "expires_at": now + timedelta(
                        days=PUSH_OFFICIAL_ALERT_OUTBOX_RETENTION_DAYS
                    ),
                    "target_kind": required_kind,
                    "target_hash": required_hash,
                    "token_hash": (
                        required_hash
                        if required_kind == PUSH_TARGET_FCM_TOKEN
                        else ""
                    ),
                },
            )
            return PushDeliveryClaim(
                delivery_id=delivery_id,
                claimed=True,
                state="sending",
                claim_id=claim_id,
                target_kind=required_kind,
                target_hash=required_hash,
            )

        try:
            return self._run_transaction(claim, transaction)
        except Exception as error:
            raise PushRepositoryUnavailable("push_outbox_claim_failed") from error

    def finish_official_alert_delivery(
        self,
        *,
        delivery_id: str,
        state: str,
        now: datetime,
        message_id: str = "",
        error_code: str = "",
        expected_claim_id: str = "",
        expected_target_kind: str = "",
        expected_target_hash: str = "",
    ) -> bool:
        if state not in {
            "sent",
            "failed_configuration",
            "failed_invalid_token",
            "failed_transient",
        }:
            raise ValueError("invalid_push_outbox_state")
        db = self._db()
        payload = {
            "state": state,
            "updated_at": now,
            "finished_at": now,
            "expires_at": now + timedelta(
                days=PUSH_OFFICIAL_ALERT_OUTBOX_RETENTION_DAYS
            ),
            "message_id": str(message_id or "")[:300],
            "error_code": str(error_code or "")[:80],
            "next_retry_at": (
                now + timedelta(seconds=PUSH_TRANSIENT_RETRY_DELAY_SECONDS)
                if state in {"failed_configuration", "failed_transient"}
                else None
            ),
        }
        document = db.collection(PUSH_OUTBOX_COLLECTION).document(delivery_id)
        transaction = db.transaction()

        def finish(transaction_in_progress: Any) -> bool:
            existing = _snapshot_data(
                document.get(transaction=transaction_in_progress)
            )
            if not existing or str(existing.get("state") or "") != "sending":
                return False
            if (
                expected_claim_id
                and str(existing.get("claim_id") or "") != expected_claim_id
            ):
                return False
            existing_kind, existing_hash = _outbox_target(existing)
            if expected_target_kind and existing_kind != expected_target_kind:
                return False
            if expected_target_hash and existing_hash != expected_target_hash:
                return False
            transaction_in_progress.set(document, payload, merge=True)
            return True

        try:
            return bool(self._run_transaction(finish, transaction))
        except Exception as error:
            raise PushRepositoryUnavailable("push_outbox_finish_failed") from error

    def claim_local_notice_delivery(
        self,
        *,
        device_id: str,
        notice_signature: str,
        notice_kind: str,
        target_kind: str,
        target_hash: str,
        expected_municipality_istat: str,
        expected_locality_id: str,
        expected_location_mode: str,
        expected_location_captured_at: datetime | None,
        expected_location_received_at: datetime | None,
        expected_location_accuracy_m: float | None,
        max_location_age_seconds: int,
        expected_enrollment_generation: str = "",
        expected_app_check_app_id: str = "",
        expected_app_version: str = "",
        allow_saved_municipality_without_mode: bool = False,
        now: datetime,
    ) -> PushDeliveryClaim:
        """Claim one local-notice delivery after rechecking the live device state."""

        required_kind = str(target_kind or "")
        required_hash = str(target_hash or "")
        if required_kind not in {
            PUSH_TARGET_FCM_TOKEN,
            PUSH_TARGET_FIREBASE_INSTALLATION_ID,
        } or not required_hash:
            raise ValueError("invalid_local_notice_target")

        db = self._db()
        delivery_id = local_notice_delivery_id(device_id, notice_signature)
        document = db.collection(PUSH_LOCAL_NOTICE_OUTBOX_COLLECTION).document(
            delivery_id
        )
        device_document = db.collection(PUSH_DEVICES_COLLECTION).document(device_id)
        transaction = db.transaction()

        def claim(transaction_in_progress: Any) -> PushDeliveryClaim:
            device = _snapshot_data(
                device_document.get(transaction=transaction_in_progress)
            )
            platform = str(device.get("platform") or "")
            if device.get("active") is not True or platform not in {"android", "web"}:
                return PushDeliveryClaim(
                    delivery_id=delivery_id,
                    claimed=False,
                    state="device_inactive",
                )
            expected_kind = (
                PUSH_TARGET_FCM_TOKEN
                if platform == "android"
                else PUSH_TARGET_FIREBASE_INSTALLATION_ID
            )
            if required_kind != expected_kind:
                return PushDeliveryClaim(
                    delivery_id=delivery_id,
                    claimed=False,
                    state="device_target_changed",
                )
            if (
                expected_enrollment_generation
                and str(device.get("schema_version") or "")
                != PUSH_DEVICE_SCHEMA_VERSION
            ):
                return PushDeliveryClaim(
                    delivery_id=delivery_id,
                    claimed=False,
                    state="schema_version_changed",
                )
            if (
                expected_enrollment_generation
                and str(device.get("enrollment_generation") or "")
                != expected_enrollment_generation
            ):
                return PushDeliveryClaim(
                    delivery_id=delivery_id,
                    claimed=False,
                    state="enrollment_generation_changed",
                )
            if (
                expected_app_check_app_id
                and str(device.get("app_check_app_id") or "")
                != expected_app_check_app_id
            ):
                return PushDeliveryClaim(
                    delivery_id=delivery_id,
                    claimed=False,
                    state="app_check_app_changed",
                )
            if (
                expected_app_version
                and str(device.get("app_version") or "").strip().lower()
                != expected_app_version
            ):
                return PushDeliveryClaim(
                    delivery_id=delivery_id,
                    claimed=False,
                    state="app_version_changed",
                )
            preferences = device.get("preferences")
            if (
                not isinstance(preferences, dict)
                or preferences.get("weather_notices") is not True
            ):
                return PushDeliveryClaim(
                    delivery_id=delivery_id,
                    claimed=False,
                    state="weather_notices_disabled",
                )
            municipality = device.get("municipality")
            locality = device.get("locality")
            current_municipality_istat = (
                str(municipality.get("istat") or "")
                if isinstance(municipality, dict)
                else ""
            )
            current_locality_id = (
                str(locality.get("id") or "")
                if isinstance(locality, dict)
                else ""
            )
            if (
                current_municipality_istat != str(expected_municipality_istat or "")
                or current_locality_id != str(expected_locality_id or "")
            ):
                return PushDeliveryClaim(
                    delivery_id=delivery_id,
                    claimed=False,
                    state="device_location_changed",
                )
            current_location_mode = str(device.get("location_mode") or "")
            if current_location_mode != str(expected_location_mode or ""):
                return PushDeliveryClaim(
                    delivery_id=delivery_id,
                    claimed=False,
                    state="device_location_changed",
                )
            evidence = device.get("location_evidence")
            captured_at = (
                evidence.get("captured_at") if isinstance(evidence, dict) else None
            )
            received_at = (
                evidence.get("received_at") if isinstance(evidence, dict) else None
            )
            try:
                accuracy_m = float(evidence.get("accuracy_m"))
            except (AttributeError, TypeError, ValueError):
                accuracy_m = -1.0
            if (
                allow_saved_municipality_without_mode
                and current_location_mode == ""
            ):
                evidence_changed = evidence is not None
                evidence_stale = False
            elif current_location_mode == "manual_selection":
                evidence_changed = evidence is not None
                evidence_stale = False
            else:
                evidence_changed = (
                    captured_at != expected_location_captured_at
                    or received_at != expected_location_received_at
                    or expected_location_accuracy_m is None
                    or accuracy_m != float(expected_location_accuracy_m)
                )
                evidence_stale = (
                    not isinstance(captured_at, datetime)
                    or not isinstance(received_at, datetime)
                    or captured_at.tzinfo is None
                    or received_at.tzinfo is None
                    or (now - captured_at).total_seconds() > max_location_age_seconds
                    or (now - received_at).total_seconds() > max_location_age_seconds
                    or captured_at > now + timedelta(minutes=2)
                    or received_at > now + timedelta(minutes=2)
                )
            if evidence_changed or evidence_stale:
                return PushDeliveryClaim(
                    delivery_id=delivery_id,
                    claimed=False,
                    state="device_location_evidence_changed",
                )
            current_kind, _, current_hash = resolve_push_target(device)
            if current_kind != required_kind or current_hash != required_hash:
                return PushDeliveryClaim(
                    delivery_id=delivery_id,
                    claimed=False,
                    state="device_target_changed",
                )

            existing = _snapshot_data(
                document.get(transaction=transaction_in_progress)
            )
            if existing:
                state = str(existing.get("state") or "unknown")
                next_retry_at = existing.get("next_retry_at")
                claimed_at = existing.get("claimed_at")
                attempt_count = int(existing.get("attempt_count") or 0)
                existing_kind, existing_hash = _outbox_target(existing)
                retry_due = (
                    isinstance(next_retry_at, datetime) and next_retry_at <= now
                )
                lease_expired = (
                    state == "sending"
                    and isinstance(claimed_at, datetime)
                    and claimed_at + timedelta(seconds=PUSH_DELIVERY_LEASE_SECONDS)
                    <= now
                )
                target_rotated = (
                    (required_kind, required_hash) != (existing_kind, existing_hash)
                    and state not in {"sent", "sending", "failed_configuration"}
                )
                retryable = (
                    state == "failed_transient"
                    and retry_due
                    and attempt_count < PUSH_MAX_DELIVERY_ATTEMPTS
                ) or (
                    lease_expired and attempt_count < PUSH_MAX_DELIVERY_ATTEMPTS
                ) or (state == "failed_configuration" and retry_due)
                if target_rotated or retryable:
                    claim_id = uuid.uuid4().hex
                    transaction_in_progress.set(
                        document,
                        {
                            "schema_version": "1.0",
                            "state": "sending",
                            "attempt_count": 1 if target_rotated else attempt_count + 1,
                            "claimed_at": now,
                            "claim_id": claim_id,
                            "updated_at": now,
                            "expires_at": now + timedelta(
                                days=PUSH_LOCAL_NOTICE_OUTBOX_RETENTION_DAYS
                            ),
                            "next_retry_at": None,
                            "error_code": "",
                            "target_kind": required_kind,
                            "target_hash": required_hash,
                            "token_hash": required_hash,
                        },
                        merge=True,
                    )
                    return PushDeliveryClaim(
                        delivery_id=delivery_id,
                        claimed=True,
                        state="sending",
                        claim_id=claim_id,
                        target_kind=required_kind,
                        target_hash=required_hash,
                    )
                if state == "failed_transient":
                    state = (
                        "retry_exhausted"
                        if attempt_count >= PUSH_MAX_DELIVERY_ATTEMPTS
                        else "retry_scheduled"
                    )
                elif state == "sending":
                    state = (
                        "retry_exhausted"
                        if attempt_count >= PUSH_MAX_DELIVERY_ATTEMPTS
                        else "delivery_in_progress"
                    )
                elif state == "failed_configuration":
                    state = "configuration_retry_scheduled"
                return PushDeliveryClaim(
                    delivery_id=delivery_id,
                    claimed=False,
                    state=state,
                )

            claim_id = uuid.uuid4().hex
            transaction_in_progress.set(
                document,
                {
                    "schema_version": "1.0",
                    "kind": "local_weather_notice",
                    "device_id": device_id,
                    "notice_kind": str(notice_kind or "")[:40],
                    "notice_signature": notice_signature,
                    "state": "sending",
                    "attempt_count": 1,
                    "claimed_at": now,
                    "claim_id": claim_id,
                    "updated_at": now,
                    "expires_at": now + timedelta(
                        days=PUSH_LOCAL_NOTICE_OUTBOX_RETENTION_DAYS
                    ),
                    "target_kind": required_kind,
                    "target_hash": required_hash,
                    "token_hash": required_hash,
                },
            )
            return PushDeliveryClaim(
                delivery_id=delivery_id,
                claimed=True,
                state="sending",
                claim_id=claim_id,
                target_kind=required_kind,
                target_hash=required_hash,
            )

        try:
            return self._run_transaction(claim, transaction)
        except Exception as error:
            raise PushRepositoryUnavailable(
                "push_local_notice_outbox_claim_failed"
            ) from error

    def finish_local_notice_delivery(
        self,
        *,
        delivery_id: str,
        state: str,
        now: datetime,
        message_id: str = "",
        error_code: str = "",
        expected_claim_id: str,
        expected_target_kind: str,
        expected_target_hash: str,
    ) -> bool:
        if state not in {
            "sent",
            "skipped_expired",
            "failed_configuration",
            "failed_invalid_token",
            "failed_transient",
        }:
            raise ValueError("invalid_push_local_notice_outbox_state")
        db = self._db()
        document = db.collection(PUSH_LOCAL_NOTICE_OUTBOX_COLLECTION).document(
            delivery_id
        )
        transaction = db.transaction()

        def finish(transaction_in_progress: Any) -> bool:
            existing = _snapshot_data(
                document.get(transaction=transaction_in_progress)
            )
            if not existing or str(existing.get("state") or "") != "sending":
                return False
            if str(existing.get("claim_id") or "") != expected_claim_id:
                return False
            existing_kind, existing_hash = _outbox_target(existing)
            if (
                existing_kind != expected_target_kind
                or existing_hash != expected_target_hash
            ):
                return False
            transaction_in_progress.set(
                document,
                {
                    "state": state,
                    "updated_at": now,
                    "finished_at": now,
                    "expires_at": now + timedelta(
                        days=PUSH_LOCAL_NOTICE_OUTBOX_RETENTION_DAYS
                    ),
                    "message_id": str(message_id or "")[:300],
                    "error_code": str(error_code or "")[:80],
                    "next_retry_at": (
                        now + timedelta(seconds=PUSH_TRANSIENT_RETRY_DELAY_SECONDS)
                        if state in {"failed_configuration", "failed_transient"}
                        else None
                    ),
                },
                merge=True,
            )
            return True

        try:
            return bool(self._run_transaction(finish, transaction))
        except Exception as error:
            raise PushRepositoryUnavailable(
                "push_local_notice_outbox_finish_failed"
            ) from error
