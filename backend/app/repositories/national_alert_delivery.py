"""Isolated, transactional outbox for national DPC Android notifications."""

from __future__ import annotations

import hashlib
import re
import uuid
from datetime import datetime, timedelta
from typing import Any, Callable

from app.repositories.push import (
    PUSH_DEVICES_COLLECTION,
    PUSH_DEVICE_SCHEMA_VERSION,
    PUSH_MAX_DELIVERY_ATTEMPTS,
    PUSH_OFFICIAL_ALERT_OUTBOX_RETENTION_DAYS,
    PUSH_TARGET_FCM_TOKEN,
    PUSH_TRANSIENT_RETRY_DELAY_SECONDS,
    PushDeliveryClaim,
    PushRepositoryUnavailable,
    resolve_push_target,
)
from app.services.push_version_policy import android_app_version_allowed


PUSH_NATIONAL_ALERT_OUTBOX_COLLECTION = "push_national_alert_outbox"
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_ISTAT = re.compile(r"^[0-9]{6}$")
_LEASE = timedelta(minutes=15)


def national_alert_delivery_id(device_id: str, signature: str) -> str:
    return hashlib.sha256(
        f"national-alert-v1:{device_id}:{signature}".encode("utf-8")
    ).hexdigest()


def _data(snapshot: Any) -> dict[str, Any]:
    return dict(snapshot.to_dict() or {}) if getattr(snapshot, "exists", False) else {}


class NationalAlertOutboxRepository:
    """Never touches the regional FVG or local-notice outbox collections."""

    def __init__(
        self,
        firestore_provider: Callable[[], Any | None],
        *,
        transactional_decorator: Callable[[Callable[..., Any]], Callable[..., Any]] | None = None,
    ) -> None:
        self._firestore_provider = firestore_provider
        self._transactional_decorator = transactional_decorator

    def _db(self) -> Any:
        try:
            db = self._firestore_provider()
        except Exception as error:
            raise PushRepositoryUnavailable("national_alert_firestore_unavailable") from error
        if db is None:
            raise PushRepositoryUnavailable("national_alert_firestore_unavailable")
        return db

    def _transaction(self, operation: Callable[..., Any], transaction: Any) -> Any:
        decorator = self._transactional_decorator
        if decorator is None:
            try:
                from google.cloud import firestore
            except ImportError as error:
                raise PushRepositoryUnavailable("national_alert_firestore_unavailable") from error
            decorator = firestore.transactional
        return decorator(operation)(transaction)

    def claim(
        self,
        *,
        device_id: str,
        alert_signature: str,
        forecast_day: str,
        level: str,
        source_revision: str,
        target_hash: str,
        municipality_istat: str,
        municipality_name: str,
        enrollment_generation: str,
        app_check_app_id: str,
        app_version: str,
        min_app_version_code: int,
        now: datetime,
    ) -> PushDeliveryClaim:
        if (
            not device_id
            or _SHA256.fullmatch(alert_signature) is None
            or _SHA256.fullmatch(target_hash) is None
            or _ISTAT.fullmatch(municipality_istat) is None
            or not municipality_name
            or not enrollment_generation
            or not app_check_app_id
            or not android_app_version_allowed(
                app_version,
                allowed_app_versions=frozenset(),
                min_app_version_code=min_app_version_code,
            )
        ):
            raise ValueError("national_alert_claim_invalid")

        db = self._db()
        delivery_id = national_alert_delivery_id(device_id, alert_signature)
        document = db.collection(PUSH_NATIONAL_ALERT_OUTBOX_COLLECTION).document(
            delivery_id
        )
        device_document = db.collection(PUSH_DEVICES_COLLECTION).document(device_id)

        def persist(transaction: Any) -> PushDeliveryClaim:
            device = _data(device_document.get(transaction=transaction))
            if device.get("active") is not True:
                return PushDeliveryClaim(delivery_id, False, "device_inactive")
            if (
                device.get("platform") != "android"
                or device.get("schema_version") != PUSH_DEVICE_SCHEMA_VERSION
                or device.get("enrollment_generation") != enrollment_generation
                or device.get("app_check_app_id") != app_check_app_id
            ):
                return PushDeliveryClaim(delivery_id, False, "play_policy_changed")
            current_version = str(device.get("app_version") or "").strip().lower()
            if current_version != app_version or not android_app_version_allowed(
                current_version,
                allowed_app_versions=frozenset(),
                min_app_version_code=min_app_version_code,
            ):
                return PushDeliveryClaim(delivery_id, False, "app_version_changed")
            if (device.get("preferences") or {}).get("official_alerts") is not True:
                return PushDeliveryClaim(delivery_id, False, "preference_disabled")
            municipality = device.get("municipality") or {}
            if (
                device.get("location_mode") != "manual_selection"
                or municipality.get("istat") != municipality_istat
                or municipality.get("name") != municipality_name
            ):
                return PushDeliveryClaim(delivery_id, False, "municipality_changed")
            kind, _, current_hash = resolve_push_target(device)
            if kind != PUSH_TARGET_FCM_TOKEN or current_hash != target_hash:
                return PushDeliveryClaim(delivery_id, False, "device_target_changed")

            existing = _data(document.get(transaction=transaction))
            if existing:
                state = str(existing.get("state") or "unknown")
                if state == "sending":
                    claimed_at = existing.get("claimed_at")
                    if isinstance(claimed_at, datetime) and claimed_at + _LEASE <= now:
                        # The previous FCM outcome is unknown. Never resend on
                        # a lease expiry: a duplicate public alert is possible.
                        state = "delivery_uncertain"
                    else:
                        state = "delivery_in_progress"
                    return PushDeliveryClaim(delivery_id, False, state)
                if state in {"failed_transient", "failed_configuration"}:
                    retry_at = existing.get("next_retry_at")
                    attempts = int(existing.get("attempt_count") or 0)
                    if attempts >= PUSH_MAX_DELIVERY_ATTEMPTS:
                        return PushDeliveryClaim(delivery_id, False, "retry_exhausted")
                    if not isinstance(retry_at, datetime) or retry_at > now:
                        return PushDeliveryClaim(delivery_id, False, "retry_scheduled")
                    claim_id = uuid.uuid4().hex
                    transaction.set(document, {
                        "state": "sending",
                        "attempt_count": attempts + 1,
                        "claim_id": claim_id,
                        "claimed_at": now,
                        "updated_at": now,
                        "target_hash": target_hash,
                        "next_retry_at": None,
                    }, merge=True)
                    return PushDeliveryClaim(
                        delivery_id, True, "sending", claim_id,
                        PUSH_TARGET_FCM_TOKEN, target_hash,
                    )
                return PushDeliveryClaim(delivery_id, False, state)

            claim_id = uuid.uuid4().hex
            transaction.set(document, {
                "schema_version": "1.0",
                "kind": "national_official_alert",
                "device_id": device_id,
                "alert_signature": alert_signature,
                "forecast_day": forecast_day,
                "level": level,
                "source_revision": source_revision,
                "municipality_istat": municipality_istat,
                "target_kind": PUSH_TARGET_FCM_TOKEN,
                "target_hash": target_hash,
                "state": "sending",
                "attempt_count": 1,
                "claim_id": claim_id,
                "claimed_at": now,
                "updated_at": now,
                "expires_at": now + timedelta(
                    days=PUSH_OFFICIAL_ALERT_OUTBOX_RETENTION_DAYS
                ),
            })
            return PushDeliveryClaim(
                delivery_id, True, "sending", claim_id,
                PUSH_TARGET_FCM_TOKEN, target_hash,
            )

        try:
            return self._transaction(persist, db.transaction())
        except Exception as error:
            raise PushRepositoryUnavailable("national_alert_outbox_claim_failed") from error

    def finish(
        self,
        *,
        delivery_id: str,
        claim_id: str,
        target_hash: str,
        state: str,
        now: datetime,
        message_id: str = "",
        error_code: str = "",
    ) -> bool:
        if state not in {
            "sent", "failed_transient", "failed_configuration", "failed_invalid_token"
        }:
            raise ValueError("national_alert_finish_state_invalid")
        db = self._db()
        document = db.collection(PUSH_NATIONAL_ALERT_OUTBOX_COLLECTION).document(
            delivery_id
        )

        def persist(transaction: Any) -> bool:
            existing = _data(document.get(transaction=transaction))
            if (
                existing.get("state") != "sending"
                or existing.get("claim_id") != claim_id
                or existing.get("target_hash") != target_hash
            ):
                return False
            transaction.set(document, {
                "state": state,
                "updated_at": now,
                "finished_at": now,
                "message_id": str(message_id or "")[:300],
                "error_code": str(error_code or "")[:80],
                "next_retry_at": (
                    now + timedelta(seconds=PUSH_TRANSIENT_RETRY_DELAY_SECONDS)
                    if state in {"failed_transient", "failed_configuration"}
                    else None
                ),
            }, merge=True)
            return True

        try:
            return bool(self._transaction(persist, db.transaction()))
        except Exception as error:
            raise PushRepositoryUnavailable("national_alert_outbox_finish_failed") from error
