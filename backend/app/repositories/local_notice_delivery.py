"""Sanitized, bounded audit history for local weather-notice delivery."""

from __future__ import annotations

import hashlib
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Mapping

from app.repositories.local_notice_shadow import (
    build_sanitized_shadow_record,
    shadow_run_bucket,
)
from app.services.location import Municipality


LOCAL_NOTICE_DELIVERY_RUNS_COLLECTION = "local_notice_pilot_runs"
LOCAL_NOTICE_DELIVERY_RECORD_SCHEMA = "local-weather-pilot-run.v2"
LOCAL_NOTICE_DELIVERY_FIRESTORE_TIMEOUT_SECONDS = 5.0


class LocalNoticeDeliveryAuditUnavailable(RuntimeError):
    """Firestore could not durably store the local-notice audit record."""


def _aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def local_notice_run_document_id(
    *,
    policy_version: str,
    istat_code: str,
    bucket: datetime,
    locality_id: str = "",
    attempt_id: str = "",
) -> str:
    raw = (
        f"{str(policy_version).strip()}:{str(istat_code).strip()}:"
        f"{shadow_run_bucket(bucket).isoformat()}"
    )
    normalized_locality_id = str(locality_id or "").strip()
    if normalized_locality_id:
        raw = f"{raw}:{normalized_locality_id}"
    normalized_attempt_id = str(attempt_id or "").strip().lower()
    if normalized_attempt_id:
        raw = f"{raw}:{normalized_attempt_id}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def build_local_notice_audit_record(
    *,
    evaluation: Mapping[str, Any],
    municipality: Municipality,
    now: datetime,
    retention_days: int,
    delivery_mode: str,
    delivery_status: str,
    selected_kind: str = "",
    source_error_code: str = "",
    attempt_id: str = "",
) -> dict[str, Any]:
    current = _aware_utc(now)
    record = build_sanitized_shadow_record(
        evaluation=evaluation,
        municipality=municipality,
        now=current,
        retention_days=retention_days,
        source_error_code=source_error_code,
    )
    record.update(
        {
            "schema_version": LOCAL_NOTICE_DELIVERY_RECORD_SCHEMA,
            "attempt_id": str(attempt_id or "").strip().lower()[:64],
            "mode": str(delivery_mode or "off")[:20],
            "shadow_only": False,
            "can_send": delivery_mode == "send",
            "delivery": {
                "status": str(delivery_status or "unknown")[:60],
                "selected_kind": str(selected_kind or "")[:40],
            },
            "expires_at": current + timedelta(days=int(retention_days)),
        }
    )
    return record


class LocalNoticeDeliveryAuditRepository:
    """Persist one idempotent audit record per canonical point and quarter-hour."""

    def __init__(
        self,
        firestore_provider: Callable[[], Any | None],
        *,
        operation_timeout_seconds: float = LOCAL_NOTICE_DELIVERY_FIRESTORE_TIMEOUT_SECONDS,
    ) -> None:
        self._firestore_provider = firestore_provider
        self._operation_timeout_seconds = max(
            0.1,
            float(operation_timeout_seconds),
        )

    def _db(self) -> Any:
        try:
            db = self._firestore_provider()
        except Exception as error:
            raise LocalNoticeDeliveryAuditUnavailable(
                "local_notice_audit_firestore_unavailable"
            ) from error
        if db is None:
            raise LocalNoticeDeliveryAuditUnavailable(
                "local_notice_audit_firestore_unavailable"
            )
        return db

    def save_run(
        self,
        *,
        evaluation: Mapping[str, Any],
        municipality: Municipality,
        now: datetime,
        retention_days: int,
        delivery_mode: str,
        delivery_status: str,
        selected_kind: str = "",
        source_error_code: str = "",
        locality_id: str = "",
        attempt_id: str = "",
    ) -> str:
        record = build_local_notice_audit_record(
            evaluation=evaluation,
            municipality=municipality,
            now=now,
            retention_days=retention_days,
            delivery_mode=delivery_mode,
            delivery_status=delivery_status,
            selected_kind=selected_kind,
            source_error_code=source_error_code,
            attempt_id=attempt_id,
        )
        document_id = local_notice_run_document_id(
            policy_version=record["policy_version"],
            istat_code=municipality.istat_code,
            bucket=record["run_bucket"],
            locality_id=locality_id,
            attempt_id=record["attempt_id"],
        )
        try:
            (
                self._db()
                .collection(LOCAL_NOTICE_DELIVERY_RUNS_COLLECTION)
                .document(document_id)
                .set(
                    deepcopy(record),
                    retry=None,
                    timeout=self._operation_timeout_seconds,
                )
            )
        except LocalNoticeDeliveryAuditUnavailable:
            raise
        except Exception as error:
            raise LocalNoticeDeliveryAuditUnavailable(
                "local_notice_audit_write_failed"
            ) from error
        return document_id


__all__ = [
    "LOCAL_NOTICE_DELIVERY_RECORD_SCHEMA",
    "LOCAL_NOTICE_DELIVERY_RUNS_COLLECTION",
    "LocalNoticeDeliveryAuditRepository",
    "LocalNoticeDeliveryAuditUnavailable",
    "build_local_notice_audit_record",
    "local_notice_run_document_id",
]
