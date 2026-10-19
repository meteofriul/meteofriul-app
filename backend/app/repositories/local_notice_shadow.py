"""Bounded, sanitized Firestore history for local-notice shadow runs."""

from __future__ import annotations

import hashlib
import math
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Mapping

from app.services.location import Municipality
from app.weather.local_notice_quality import run_identity, sanitize_quality


LOCAL_NOTICE_SHADOW_COLLECTION = "local_notice_shadow_runs"
LOCAL_NOTICE_SHADOW_RECORD_SCHEMA = "local-weather-shadow-run.v1"
LOCAL_NOTICE_SHADOW_BUCKET_MINUTES = 15
LOCAL_NOTICE_SHADOW_FIRESTORE_TIMEOUT_SECONDS = 5.0

_FORBIDDEN_KEYS = frozenset(
    {
        "token",
        "token_hash",
        "installation_id",
        "device_id",
        "latitude",
        "longitude",
        "event_key",
        "raw_snapshot",
        "response_body",
        "url",
    }
)


class LocalNoticeShadowRepositoryUnavailable(RuntimeError):
    """Firestore could not durably store a shadow evaluation."""


def _aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def shadow_run_bucket(value: datetime) -> datetime:
    current = _aware_utc(value)
    minute = (
        current.minute // LOCAL_NOTICE_SHADOW_BUCKET_MINUTES
    ) * LOCAL_NOTICE_SHADOW_BUCKET_MINUTES
    return current.replace(minute=minute, second=0, microsecond=0)


def shadow_run_document_id(
    *,
    policy_version: str,
    istat_code: str,
    bucket: datetime,
) -> str:
    identity = (
        f"{str(policy_version).strip()}:{str(istat_code).strip()}:"
        f"{shadow_run_bucket(bucket).isoformat()}"
    )
    return hashlib.sha256(identity.encode("utf-8")).hexdigest()


def _safe_copy(value: Any, *, depth: int = 0) -> Any:
    if depth > 8:
        return None
    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, str):
        return value[:500]
    if isinstance(value, Mapping):
        return {
            str(key)[:80]: _safe_copy(item, depth=depth + 1)
            for key, item in list(value.items())[:50]
            if str(key).strip().lower() not in _FORBIDDEN_KEYS
        }
    if isinstance(value, (list, tuple)):
        return [_safe_copy(item, depth=depth + 1) for item in list(value)[:50]]
    return str(value)[:500]


def _sanitized_candidate(candidate: Mapping[str, Any]) -> dict[str, Any]:
    dedupe = candidate.get("dedupe")
    if not isinstance(dedupe, Mapping):
        dedupe = {}
    confidence = candidate.get("confidence")
    return {
        "kind": str(candidate.get("kind") or "")[:40],
        "category": str(candidate.get("category") or "")[:40],
        "severity": int(candidate.get("severity") or 0),
        "priority": int(candidate.get("priority") or 0),
        "event_at": str(candidate.get("event_at") or "")[:80],
        "event_end": str(candidate.get("event_end") or "")[:80],
        "threshold": _safe_copy(candidate.get("threshold") or {}),
        "evidence": _safe_copy(candidate.get("evidence") or []),
        "confidence": (
            _safe_copy(confidence) if isinstance(confidence, Mapping) else None
        ),
        "dedupe": {
            "event_bucket": str(dedupe.get("event_bucket") or "")[:40],
            "signature": str(dedupe.get("signature") or "")[:64],
        },
        "shadow_only": True,
        "can_notify": False,
    }


def build_sanitized_shadow_record(
    *,
    evaluation: Mapping[str, Any],
    municipality: Municipality,
    now: datetime,
    retention_days: int,
    source_error_code: str = "",
) -> dict[str, Any]:
    if retention_days < 1 or retention_days > 30:
        raise ValueError("local_notice_shadow_retention_invalid")
    current = _aware_utc(now)
    snapshot = evaluation.get("snapshot")
    if not isinstance(snapshot, Mapping):
        snapshot = {}
    candidates = [
        _sanitized_candidate(candidate)
        for candidate in (evaluation.get("candidates") or [])[:10]
        if isinstance(candidate, Mapping)
    ]
    observations = [
        _safe_copy(observation)
        for observation in (evaluation.get("observations") or [])[:20]
        if isinstance(observation, Mapping)
    ]
    validation_errors = [
        str(error)[:120]
        for error in (evaluation.get("validation_errors") or [])[:30]
        if str(error).strip()
    ]
    return {
        "schema_version": LOCAL_NOTICE_SHADOW_RECORD_SCHEMA,
        "detector_schema_version": str(
            evaluation.get("schema_version") or ""
        )[:80],
        "policy_version": str(evaluation.get("policy_version") or "")[:80],
        "mode": "shadow",
        "shadow_only": True,
        "can_send": False,
        "status": str(evaluation.get("status") or "unknown")[:40],
        "municipality": {
            "istat": municipality.istat_code,
            "name": municipality.name,
            "province": municipality.province,
        },
        "locality": (
            {
                "id": str((evaluation.get("locality") or {}).get("id") or "")[:160],
                "name": str((evaluation.get("locality") or {}).get("name") or "")[:160],
            }
            if isinstance(evaluation.get("locality"), Mapping)
            else None
        ),
        "evaluated_at": current,
        "run_bucket": shadow_run_bucket(current),
        "snapshot": {
            "source": str(snapshot.get("source") or "")[:80],
            "fetched_at": str(snapshot.get("fetched_at") or "")[:80],
            "timezone": str(snapshot.get("timezone") or "")[:80],
            "eligible_slots": int(snapshot.get("eligible_slots") or 0),
            "source_run_id": run_identity(snapshot.get("source_run_id")),
        },
        "data_quality": sanitize_quality(evaluation.get("data_quality")),
        "validation_errors": validation_errors,
        "candidate_count": len(candidates),
        "candidates": candidates,
        "observations": observations,
        "source_error_code": str(source_error_code or "")[:80],
        "expires_at": current + timedelta(days=int(retention_days)),
    }


class LocalNoticeShadowRepository:
    """Write one idempotent history document per municipality and 15 minutes."""

    def __init__(
        self,
        firestore_provider: Callable[[], Any | None],
        *,
        operation_timeout_seconds: float = LOCAL_NOTICE_SHADOW_FIRESTORE_TIMEOUT_SECONDS,
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
            raise LocalNoticeShadowRepositoryUnavailable(
                "local_notice_shadow_firestore_unavailable"
            ) from error
        if db is None:
            raise LocalNoticeShadowRepositoryUnavailable(
                "local_notice_shadow_firestore_unavailable"
            )
        return db

    def save_run(
        self,
        *,
        evaluation: Mapping[str, Any],
        municipality: Municipality,
        now: datetime,
        retention_days: int,
        source_error_code: str = "",
    ) -> str:
        record = build_sanitized_shadow_record(
            evaluation=evaluation,
            municipality=municipality,
            now=now,
            retention_days=retention_days,
            source_error_code=source_error_code,
        )
        document_id = shadow_run_document_id(
            policy_version=record["policy_version"],
            istat_code=municipality.istat_code,
            bucket=record["run_bucket"],
        )
        try:
            (
                self._db()
                .collection(LOCAL_NOTICE_SHADOW_COLLECTION)
                .document(document_id)
                .set(
                    deepcopy(record),
                    retry=None,
                    timeout=self._operation_timeout_seconds,
                )
            )
        except LocalNoticeShadowRepositoryUnavailable:
            raise
        except Exception as error:
            raise LocalNoticeShadowRepositoryUnavailable(
                "local_notice_shadow_write_failed"
            ) from error
        return document_id


__all__ = [
    "LOCAL_NOTICE_SHADOW_COLLECTION",
    "LOCAL_NOTICE_SHADOW_RECORD_SCHEMA",
    "LocalNoticeShadowRepository",
    "LocalNoticeShadowRepositoryUnavailable",
    "build_sanitized_shadow_record",
    "shadow_run_bucket",
    "shadow_run_document_id",
]
