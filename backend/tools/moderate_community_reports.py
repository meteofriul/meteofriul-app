r"""Private Firestore moderation CLI for the Territorio community feed.

This tool is deliberately not exposed through the public API.  It requires
Firebase Admin credentials and ``COMMUNITY_STORAGE=firestore``.  Mutating
commands are dry-run unless ``--apply`` is supplied.

Examples (PowerShell, from ``backend``)::

    $env:COMMUNITY_STORAGE = "firestore"
    .\venv\Scripts\python.exe tools\moderate_community_reports.py list
    .\venv\Scripts\python.exe tools\moderate_community_reports.py hide GROUP_ID --apply
    .\venv\Scripts\python.exe tools\moderate_community_reports.py restore GROUP_ID --apply
    .\venv\Scripts\python.exe tools\moderate_community_reports.py remove GROUP_ID --apply
    .\venv\Scripts\python.exe tools\moderate_community_reports.py block-source REPORT_ID --hours 24 --apply
    .\venv\Scripts\python.exe tools\moderate_community_reports.py unblock-source REPORT_ID --apply

Normal output never prints the private owner key or individual flagger keys.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.infrastructure.firebase import get_firestore_client  # noqa: E402
from app.repositories.community import (  # noqa: E402
    CONFIRMATIONS_COLLECTION,
    FLAGS_COLLECTION,
    MODERATION_COLLECTION,
    REPORTS_COLLECTION,
    REPUTATION_AWARDS_COLLECTION,
    SOURCE_BLOCKS_COLLECTION,
    CommunityRepository,
)


DEFAULT_BLOCK_HOURS = 24
MAX_BLOCK_HOURS = 24
MODERATION_RETENTION_SECONDS = 24 * 60 * 60
EXPECTED_FIRESTORE_PROJECT_ID = "meteo-friul"
MAX_ADMIN_BATCH_WRITES = 450


def _timestamp(value: Any) -> float:
    if isinstance(value, datetime):
        return value.timestamp()
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0


def _utc_datetime(value: float) -> datetime:
    return datetime.fromtimestamp(float(value), timezone.utc)


def _moderation_document_id(group_id: str) -> str:
    return hashlib.sha256(group_id.encode("utf-8")).hexdigest()


def _moderation_group_reference(group_id: str) -> str:
    """Match the sanitized reference carried by moderation digest logs."""

    return _moderation_document_id(group_id)[:24]


def _source_block_document_id(owner_key: str) -> str:
    return hashlib.sha256(owner_key.encode("utf-8")).hexdigest()


def require_expected_project(db: Any) -> str:
    project_id = str(getattr(db, "project", "") or "").strip()
    if project_id != EXPECTED_FIRESTORE_PROJECT_ID:
        raise RuntimeError(
            "firestore_project_mismatch: expected "
            f"{EXPECTED_FIRESTORE_PROJECT_ID!r}, received {project_id or '<unknown>'!r}"
        )
    return project_id


def require_single_batch_capacity(action: str, write_count: int) -> None:
    if write_count > MAX_ADMIN_BATCH_WRITES:
        raise RuntimeError(
            "community_moderation_batch_limit_exceeded: "
            f"{action} requires {write_count} writes, maximum "
            f"{MAX_ADMIN_BATCH_WRITES}; wait for the 60-minute report TTL to "
            "reduce the active group, then inspect and retry. No writes were applied."
        )


def summarize_moderation(payload: dict[str, Any], *, now: float) -> dict[str, Any] | None:
    expires_at = _timestamp(payload.get("expires_at_timestamp"))
    flaggers = dict(payload.get("flaggers") or {})
    flag_count = max(int(payload.get("flag_count") or 0), len(flaggers))
    if expires_at <= now or flag_count <= 0:
        return None
    group_id = str(payload.get("group_id") or "")
    return {
        "group_id": group_id,
        # Lets an operator correlate a sanitized ready digest with this private
        # list without putting the raw group id in Cloud Logging or email.
        "group_ref": _moderation_group_reference(group_id),
        "flag_count": flag_count,
        "report_count": len(list(dict.fromkeys(payload.get("report_ids") or []))),
        "source_count": len(list(dict.fromkeys(payload.get("owner_keys") or []))),
        "reasons": dict(sorted(Counter(str(value) for value in flaggers.values()).items())),
        "hidden": bool(payload.get("hidden", False)),
        "hidden_reason": str(payload.get("hidden_reason") or ""),
        "expires_at": _utc_datetime(expires_at).isoformat(),
    }


def _field_filter(field: str, operator: str, value: Any) -> Any:
    try:
        from google.cloud.firestore_v1.base_query import FieldFilter

        return FieldFilter(field, operator, value)
    except ModuleNotFoundError:
        return type("FieldFilter", (), {
            "field_path": field,
            "op_string": operator,
            "value": value,
        })()


def _documents_for_group(
    db: Any,
    collection: str,
    group_id: str,
    *,
    transaction: Any | None = None,
) -> list[Any]:
    query = db.collection(collection).where(
        filter=_field_filter("group_id", "==", group_id)
    )
    return list(
        query.stream()
        if transaction is None
        else query.stream(transaction=transaction)
    )


def _get_document_snapshot(
    document: Any,
    *,
    transaction: Any | None = None,
) -> Any:
    if transaction is None:
        return document.get()
    return document.get(transaction=transaction)


def _selected_transactional_decorator(
    transactional_decorator: Any | None,
) -> Any:
    if transactional_decorator is not None:
        return transactional_decorator
    from google.cloud import firestore

    return firestore.transactional


def _require_owned_snapshot(
    snapshot: Any,
    *,
    expected_marker: str,
    marker_field: str,
) -> dict[str, Any]:
    if not snapshot.exists:
        raise RuntimeError("community_qa_document_missing")
    payload = dict(snapshot.to_dict() or {})
    if payload.get(marker_field) != expected_marker:
        raise RuntimeError("community_qa_document_ownership_lost")
    return payload


def _require_expected_report_count(
    reports: list[Any],
    expected_report_count: int | None,
) -> None:
    if (
        expected_report_count is not None
        and len(reports) != int(expected_report_count)
    ):
        raise RuntimeError("community_report_set_changed")


def _commit_report_visibility(
    db: Any,
    reports: list[Any],
    *,
    hidden: bool,
    now: float,
    reason: str,
) -> None:
    """Materialize visibility in bounded batches after the group gate exists."""

    for start in range(0, len(reports), MAX_ADMIN_BATCH_WRITES):
        batch = db.batch()
        for report in reports[start : start + MAX_ADMIN_BATCH_WRITES]:
            batch.set(
                report.reference,
                {
                    "moderation_hidden": hidden,
                    "moderation_hidden_at_timestamp": (
                        _utc_datetime(now) if hidden else None
                    ),
                    "moderation_reason": reason,
                    "validity_status": "rejected" if hidden else "unverified",
                },
                merge=True,
            )
        batch.commit()


def _commit_deletes(db: Any, snapshots: list[Any]) -> None:
    for start in range(0, len(snapshots), MAX_ADMIN_BATCH_WRITES):
        batch = db.batch()
        for snapshot in snapshots[start : start + MAX_ADMIN_BATCH_WRITES]:
            batch.delete(snapshot.reference)
        batch.commit()


def _mark_group_validity(
    db: Any,
    group_id: str,
    *,
    validity_status: str,
    now: float,
) -> None:
    confirmation_document = db.collection(CONFIRMATIONS_COLLECTION).document(
        _moderation_document_id(group_id)
    )
    confirmation_snapshot = confirmation_document.get()
    confirmation = (
        dict(confirmation_snapshot.to_dict() or {})
        if confirmation_snapshot.exists
        else {}
    )
    expires_at = max(
        _timestamp(confirmation.get("expires_at_timestamp")),
        now + MODERATION_RETENTION_SECONDS,
    )
    payload: dict[str, Any] = {
        "group_id": group_id,
        "validity_status": validity_status,
        "updated_at": _utc_datetime(now),
        "expires_at_timestamp": _utc_datetime(expires_at),
    }
    if validity_status == "rejected":
        payload["rejected_at_timestamp"] = _utc_datetime(now)
    else:
        # Restore is intentionally conservative: visibility returns, while
        # reputation needs a fresh explicit policy decision rather than a
        # silent re-award of a previously rejected episode.
        payload.update({
            "verified_at": None,
            "rejected_at_timestamp": None,
        })
    confirmation_document.set(payload, merge=True)


def _revoke_group_reputation(
    db: Any,
    group_id: str,
    *,
    now: float,
    reason: str,
    transactional_decorator: Any | None = None,
) -> int:
    episode_key = hashlib.sha256(
        f"community-episode-v1:{group_id}".encode("utf-8")
    ).hexdigest()
    awards = list(
        db.collection(REPUTATION_AWARDS_COLLECTION)
        .where(filter=_field_filter("episode_key", "==", episode_key))
        .limit(MAX_ADMIN_BATCH_WRITES)
        .stream()
    )
    if not awards:
        return 0
    if len(awards) >= MAX_ADMIN_BATCH_WRITES:
        raise RuntimeError("community_reputation_revocation_limit_exceeded")
    repository = CommunityRepository(
        lambda: db,
        storage_mode="firestore",
        transactional_decorator=transactional_decorator,
    )
    return repository.revoke_group_reputation_strict(
        group_id,
        now=now,
        reason=reason,
    )


def owner_key_from_moderation_snapshot(
    report_id: str,
    moderation: dict[str, Any],
) -> str:
    """Resolve one private source internally without returning it in CLI output."""

    return str(dict(moderation.get("report_sources") or {}).get(report_id) or "")


def list_active_flags(db: Any, *, now: float) -> list[dict[str, Any]]:
    rows = []
    for snapshot in db.collection(MODERATION_COLLECTION).stream():
        row = summarize_moderation(dict(snapshot.to_dict() or {}), now=now)
        if row is not None:
            rows.append(row)
    return sorted(rows, key=lambda row: (-int(row["flag_count"]), row["group_id"]))


def inspect_group(db: Any, group_id: str, *, now: float) -> dict[str, Any]:
    snapshot = db.collection(MODERATION_COLLECTION).document(
        _moderation_document_id(group_id)
    ).get()
    payload = dict(snapshot.to_dict() or {}) if snapshot.exists else {}
    summary = summarize_moderation(payload, now=now)
    reports = _documents_for_group(db, REPORTS_COLLECTION, group_id)
    snapshot_active = (
        snapshot.exists
        and _timestamp(payload.get("expires_at_timestamp")) > now
    )
    if not snapshot_active and not reports:
        raise RuntimeError("community_group_not_found")
    report_ids = list(dict.fromkeys([
        *(
            str(value)
            for value in (payload.get("report_ids") or [])
            if str(value)
        ),
        *(str(report.id) for report in reports),
    ]))
    return {
        "group_id": group_id,
        "report_ids": report_ids,
        "report_count": len(report_ids),
        "source_count": len(list(dict.fromkeys(
            str(value)
            for value in (payload.get("owner_keys") or [])
            if str(value)
        ))),
        "flag_count": int((summary or {}).get("flag_count", 0)),
        "reasons": dict((summary or {}).get("reasons") or {}),
        "hidden": bool(payload.get("hidden", False)),
        "expires_at": (summary or {}).get("expires_at"),
    }


def hide_group(
    db: Any,
    group_id: str,
    *,
    now: float,
    apply: bool,
    expected_report_count: int | None = None,
    expected_marker: str | None = None,
    marker_field: str = "qa_smoke_marker",
    transactional_decorator: Any | None = None,
) -> dict[str, Any]:
    moderation_document = db.collection(MODERATION_COLLECTION).document(
        _moderation_document_id(group_id)
    )
    moderation_snapshot = moderation_document.get()
    moderation = (
        dict(moderation_snapshot.to_dict() or {})
        if moderation_snapshot.exists
        else {}
    )
    reports = _documents_for_group(db, REPORTS_COLLECTION, group_id)
    _require_expected_report_count(reports, expected_report_count)
    if not reports and not moderation_snapshot.exists:
        raise RuntimeError("community_group_not_found")
    result = {"action": "hide", "group_id": group_id, "reports": len(reports), "applied": apply}
    if not apply:
        return result

    expires_at = now + MODERATION_RETENTION_SECONDS
    if expected_marker is not None:
        if expected_report_count != 0:
            raise RuntimeError("community_qa_expected_zero_reports")
        decorator = _selected_transactional_decorator(
            transactional_decorator
        )
        transaction = db.transaction()

        def hide_if_still_owned(transaction_in_progress: Any) -> None:
            current_moderation = _get_document_snapshot(
                moderation_document,
                transaction=transaction_in_progress,
            )
            current_payload = _require_owned_snapshot(
                current_moderation,
                expected_marker=expected_marker,
                marker_field=marker_field,
            )
            current_reports = _documents_for_group(
                db,
                REPORTS_COLLECTION,
                group_id,
                transaction=transaction_in_progress,
            )
            _require_expected_report_count(
                current_reports,
                expected_report_count,
            )
            transaction_in_progress.set(
                moderation_document,
                {
                    **current_payload,
                    "group_id": group_id,
                    "hidden": True,
                    "hidden_at": now,
                    "hidden_reason": "administrative_moderation",
                    "updated_at": _utc_datetime(now),
                    "expires_at_timestamp": _utc_datetime(expires_at),
                },
                merge=False,
            )

        decorator(hide_if_still_owned)(transaction)
        return {**result, "reputation_revoked": 0}

    # Close visibility first. A create transaction that already started may
    # still commit, but the public feed consults this one group gate and will
    # never expose that late report.
    moderation_document.set(
        {
            "group_id": group_id,
            "hidden": True,
            "hidden_at": now,
            "hidden_reason": "administrative_moderation",
            "updated_at": _utc_datetime(now),
            "expires_at_timestamp": _utc_datetime(expires_at),
        },
        merge=True,
    )
    _mark_group_validity(
        db,
        group_id,
        validity_status="rejected",
        now=now,
    )
    revoked = _revoke_group_reputation(
        db,
        group_id,
        now=now,
        reason="administrative_moderation",
        transactional_decorator=transactional_decorator,
    )
    reports = _documents_for_group(db, REPORTS_COLLECTION, group_id)
    # The optional smoke guard is checked again after the persistent group
    # gate exists and before any report snapshot can be materialized.
    _require_expected_report_count(reports, expected_report_count)
    report_ids = [str(report.id) for report in reports]
    report_sources = {
        **dict(moderation.get("report_sources") or {}),
        **{
        str(report.id): str((report.to_dict() or {}).get("owner_key") or "")
        for report in reports
        if str((report.to_dict() or {}).get("owner_key") or "")
        },
    }
    report_ids = list(dict.fromkeys([
        *(str(value) for value in (moderation.get("report_ids") or []) if str(value)),
        *report_ids,
    ]))
    owner_keys = list(dict.fromkeys([
        *(str(value) for value in (moderation.get("owner_keys") or []) if str(value)),
        *(str(value) for value in report_sources.values() if str(value)),
    ]))
    moderation_document.set(
        {
            "group_id": group_id,
            "hidden": True,
            "hidden_at": now,
            "hidden_reason": "administrative_moderation",
            "report_ids": report_ids,
            "owner_keys": owner_keys,
            "report_sources": report_sources,
            "updated_at": _utc_datetime(now),
            "expires_at_timestamp": _utc_datetime(expires_at),
        },
        merge=True,
    )
    _commit_report_visibility(
        db,
        reports,
        hidden=True,
        now=now,
        reason="administrative_moderation",
    )
    return {
        **result,
        "reports": len(reports),
        "reputation_revoked": revoked,
    }


def restore_group(
    db: Any,
    group_id: str,
    *,
    now: float,
    apply: bool,
    expected_report_count: int | None = None,
    expected_marker: str | None = None,
    marker_field: str = "qa_smoke_marker",
    transactional_decorator: Any | None = None,
) -> dict[str, Any]:
    reports = _documents_for_group(db, REPORTS_COLLECTION, group_id)
    _require_expected_report_count(reports, expected_report_count)
    flags = _documents_for_group(db, FLAGS_COLLECTION, group_id)
    moderation_document = db.collection(MODERATION_COLLECTION).document(
        _moderation_document_id(group_id)
    )
    moderation_snapshot = moderation_document.get()
    if not reports and not flags and not moderation_snapshot.exists:
        raise RuntimeError("community_group_not_found")
    result = {
        "action": "restore",
        "group_id": group_id,
        "reports": len(reports),
        "flags_cleared": len(flags),
        "applied": apply,
    }
    if not apply:
        return result

    if expected_marker is not None:
        if expected_report_count != 0:
            raise RuntimeError("community_qa_expected_zero_reports")
        decorator = _selected_transactional_decorator(
            transactional_decorator
        )
        transaction = db.transaction()
        applied_counts: dict[str, int] = {}

        def restore_if_still_owned(transaction_in_progress: Any) -> None:
            current_moderation = _get_document_snapshot(
                moderation_document,
                transaction=transaction_in_progress,
            )
            moderation = _require_owned_snapshot(
                current_moderation,
                expected_marker=expected_marker,
                marker_field=marker_field,
            )
            current_reports = _documents_for_group(
                db,
                REPORTS_COLLECTION,
                group_id,
                transaction=transaction_in_progress,
            )
            _require_expected_report_count(
                current_reports,
                expected_report_count,
            )
            current_flags = _documents_for_group(
                db,
                FLAGS_COLLECTION,
                group_id,
                transaction=transaction_in_progress,
            )
            # Re-read every flag selected before the transaction by its exact
            # document path. A concurrent replacement can remove ``group_id``
            # and disappear from the query; it must still fail closed rather
            # than being silently skipped.
            flags_by_id = {
                str(flag.id): flag
                for flag in [*flags, *current_flags]
            }
            for flag in flags_by_id.values():
                _require_owned_snapshot(
                    _get_document_snapshot(
                        flag.reference,
                        transaction=transaction_in_progress,
                    ),
                    expected_marker=expected_marker,
                    marker_field=marker_field,
                )
            expires_at = max(
                _timestamp(moderation.get("expires_at_timestamp")),
                now + MODERATION_RETENTION_SECONDS,
            )
            for flag in flags_by_id.values():
                transaction_in_progress.delete(flag.reference)
            transaction_in_progress.set(
                moderation_document,
                {
                    **moderation,
                    "group_id": group_id,
                    "flag_count": 0,
                    "flaggers": {},
                    "hidden": False,
                    "hidden_at": None,
                    "hidden_reason": "administrative_restore",
                    "updated_at": _utc_datetime(now),
                    "expires_at_timestamp": _utc_datetime(expires_at),
                },
                merge=False,
            )
            applied_counts["reports"] = len(current_reports)
            applied_counts["flags"] = len(flags_by_id)

        decorator(restore_if_still_owned)(transaction)
        return {
            **result,
            "reports": applied_counts.get("reports", 0),
            "flags_cleared": applied_counts.get("flags", 0),
        }

    require_single_batch_capacity("restore", len(reports) + len(flags) + 1)
    moderation = (
        dict(moderation_snapshot.to_dict() or {})
        if moderation_snapshot.exists
        else {}
    )
    expires_at = max(
        _timestamp(moderation.get("expires_at_timestamp")),
        now + MODERATION_RETENTION_SECONDS,
    )
    batch = db.batch()
    for flag in flags:
        batch.delete(flag.reference)
    batch.set(
        moderation_document,
        {
            **moderation,
            "group_id": group_id,
            "flag_count": 0,
            "flaggers": {},
            "hidden": False,
            "hidden_at": None,
            "hidden_reason": "administrative_restore",
            "updated_at": _utc_datetime(now),
            "expires_at_timestamp": _utc_datetime(expires_at),
        },
        merge=False,
    )
    for report in reports:
        batch.set(
            report.reference,
            {
                "moderation_hidden": False,
                "moderation_hidden_at_timestamp": None,
                "moderation_reason": "administrative_restore",
                "validity_status": "unverified",
            },
            merge=True,
        )
    batch.commit()
    _mark_group_validity(
        db,
        group_id,
        validity_status="unverified",
        now=now,
    )
    return result


def remove_group(
    db: Any,
    group_id: str,
    *,
    now: float,
    apply: bool,
    transactional_decorator: Any | None = None,
) -> dict[str, Any]:
    reports = _documents_for_group(db, REPORTS_COLLECTION, group_id)
    flags = _documents_for_group(db, FLAGS_COLLECTION, group_id)
    moderation_document = db.collection(MODERATION_COLLECTION).document(
        _moderation_document_id(group_id)
    )
    moderation_snapshot = moderation_document.get()
    result = {
        "action": "remove",
        "group_id": group_id,
        "reports": len(reports),
        "flags": len(flags),
        "applied": apply,
    }
    if not reports and not flags and not moderation_snapshot.exists:
        raise RuntimeError("community_group_not_found")
    if not apply:
        return result

    moderation = (
        dict(moderation_snapshot.to_dict() or {})
        if moderation_snapshot.exists
        else {}
    )
    # The persistent group gate is written before querying the deletion set.
    # Any in-flight late report remains globally hidden even if it commits
    # after the following query; subsequent creates are rejected.
    moderation_document.set(
        {
            "group_id": group_id,
            "hidden": True,
            "hidden_at": now,
            "hidden_reason": "administrative_removal",
            "updated_at": _utc_datetime(now),
            "expires_at_timestamp": _utc_datetime(
                now + MODERATION_RETENTION_SECONDS
            ),
        },
        merge=True,
    )
    _mark_group_validity(
        db,
        group_id,
        validity_status="rejected",
        now=now,
    )
    revoked = _revoke_group_reputation(
        db,
        group_id,
        now=now,
        reason="administrative_removal",
        transactional_decorator=transactional_decorator,
    )
    reports = _documents_for_group(db, REPORTS_COLLECTION, group_id)
    flags = _documents_for_group(db, FLAGS_COLLECTION, group_id)
    report_sources = {
        **dict(moderation.get("report_sources") or {}),
        **{
            str(report.id): str((report.to_dict() or {}).get("owner_key") or "")
            for report in reports
            if str((report.to_dict() or {}).get("owner_key") or "")
        },
    }
    report_ids = list(dict.fromkeys([
        *(str(value) for value in (moderation.get("report_ids") or []) if str(value)),
        *(str(report.id) for report in reports),
    ]))
    owner_keys = list(dict.fromkeys([
        *(str(value) for value in (moderation.get("owner_keys") or []) if str(value)),
        *(str(value) for value in report_sources.values() if str(value)),
    ]))
    moderation_document.set(
        {
            "group_id": group_id,
            "flag_count": 0,
            "flaggers": {},
            "hidden": True,
            "hidden_at": now,
            "hidden_reason": "administrative_removal",
            "report_ids": report_ids,
            "owner_keys": owner_keys,
            "report_sources": report_sources,
            "updated_at": _utc_datetime(now),
            "expires_at_timestamp": _utc_datetime(
                now + MODERATION_RETENTION_SECONDS
            ),
        },
        merge=False,
    )
    _commit_deletes(db, [*reports, *flags])
    return {
        **result,
        "reports": len(reports),
        "flags": len(flags),
        "reputation_revoked": revoked,
    }


def _resolve_owner_key_for_report(
    db: Any,
    report_id: str,
    *,
    expected_owner_key: str | None,
    require_report_absent: bool,
    transaction: Any | None = None,
    expected_marker: str | None = None,
    marker_field: str = "qa_smoke_marker",
) -> str:
    snapshot = _get_document_snapshot(
        db.collection(REPORTS_COLLECTION).document(report_id),
        transaction=transaction,
    )
    if require_report_absent and snapshot.exists:
        raise RuntimeError("community_public_report_unexpected")
    report = dict(snapshot.to_dict() or {}) if snapshot.exists else {}
    report_owner_key = str(report.get("owner_key") or "")
    selected_expected_owner_key = str(expected_owner_key or "")
    if (
        selected_expected_owner_key
        and report_owner_key
        and report_owner_key != selected_expected_owner_key
    ):
        raise RuntimeError("community_private_source_mismatch")
    if report_owner_key and not selected_expected_owner_key:
        return report_owner_key

    moderation_query = (
        db.collection(MODERATION_COLLECTION)
        .where(filter=_field_filter("report_ids", "array_contains", report_id))
        .limit(2)
    )
    moderation_documents = list(
        moderation_query.stream()
        if transaction is None
        else moderation_query.stream(transaction=transaction)
    )
    if len(moderation_documents) > 1:
        # A report belongs to exactly one moderation group.  Selecting an
        # owner from more than one snapshot would make block/unblock depend on
        # Firestore iteration order and could mutate the wrong anonymous
        # source.  Stop before any write instead.
        raise RuntimeError("community_private_source_ambiguous")
    if expected_marker is not None:
        if len(moderation_documents) != 1:
            raise RuntimeError("community_expected_private_source_not_found")
        _require_owned_snapshot(
            moderation_documents[0],
            expected_marker=expected_marker,
            marker_field=marker_field,
        )
    moderation_owner_keys = {
        owner_key_from_moderation_snapshot(
            report_id,
            dict(moderation_snapshot.to_dict() or {}),
        )
        for moderation_snapshot in moderation_documents
    }
    moderation_owner_keys.discard("")
    if selected_expected_owner_key:
        if selected_expected_owner_key not in moderation_owner_keys:
            raise RuntimeError("community_expected_private_source_not_found")
        return selected_expected_owner_key
    return next(iter(moderation_owner_keys), "")


def block_source(
    db: Any,
    report_id: str,
    *,
    hours: int,
    now: float,
    apply: bool,
    expected_owner_key: str | None = None,
    require_report_absent: bool = False,
    expected_target_marker: str | None = None,
    marker_field: str = "qa_smoke_marker",
    transactional_decorator: Any | None = None,
) -> dict[str, Any]:
    if hours < 1 or hours > MAX_BLOCK_HOURS:
        raise ValueError(f"hours_must_be_between_1_and_{MAX_BLOCK_HOURS}")
    owner_key = _resolve_owner_key_for_report(
        db,
        report_id,
        expected_owner_key=expected_owner_key,
        require_report_absent=require_report_absent,
        expected_marker=expected_target_marker,
        marker_field=marker_field,
    )
    if not owner_key:
        raise RuntimeError("community_report_or_private_snapshot_not_found")
    blocked_until = now + hours * 60 * 60
    result = {
        "action": "block-source",
        "report_id": report_id,
        "hours": hours,
        "blocked_until": _utc_datetime(blocked_until).isoformat(),
        "applied": apply,
    }
    if not apply:
        return result

    source_block_document = db.collection(SOURCE_BLOCKS_COLLECTION).document(
        _source_block_document_id(owner_key)
    )
    payload = {
        "blocked_until": blocked_until,
        "reason": "administrative_moderation",
        "report_id": report_id,
        "updated_at": _utc_datetime(now),
        "expires_at_timestamp": _utc_datetime(blocked_until),
    }
    if expected_target_marker is None:
        source_block_document.set(payload, merge=True)
        return result

    decorator = _selected_transactional_decorator(
        transactional_decorator
    )
    transaction = db.transaction()

    def block_if_still_owned(transaction_in_progress: Any) -> None:
        resolved_owner_key = _resolve_owner_key_for_report(
            db,
            report_id,
            expected_owner_key=expected_owner_key,
            require_report_absent=require_report_absent,
            transaction=transaction_in_progress,
            expected_marker=expected_target_marker,
            marker_field=marker_field,
        )
        if resolved_owner_key != owner_key:
            raise RuntimeError("community_private_source_mismatch")
        current_block = _get_document_snapshot(
            source_block_document,
            transaction=transaction_in_progress,
        )
        _require_owned_snapshot(
            current_block,
            expected_marker=expected_target_marker,
            marker_field=marker_field,
        )
        transaction_in_progress.set(
            source_block_document,
            payload,
            merge=True,
        )

    decorator(block_if_still_owned)(transaction)
    return result


def unblock_source(
    db: Any,
    report_id: str,
    *,
    apply: bool,
    expected_owner_key: str | None = None,
    require_report_absent: bool = False,
    expected_target_marker: str | None = None,
    marker_field: str = "qa_smoke_marker",
    transactional_decorator: Any | None = None,
) -> dict[str, Any]:
    owner_key = _resolve_owner_key_for_report(
        db,
        report_id,
        expected_owner_key=expected_owner_key,
        require_report_absent=require_report_absent,
    )
    if not owner_key:
        raise RuntimeError("community_report_or_private_snapshot_not_found")
    result = {
        "action": "unblock-source",
        "report_id": report_id,
        "applied": apply,
    }
    if not apply:
        return result
    source_block_document = db.collection(SOURCE_BLOCKS_COLLECTION).document(
        _source_block_document_id(owner_key)
    )
    if expected_target_marker is None:
        source_block_document.delete()
        return result

    decorator = _selected_transactional_decorator(
        transactional_decorator
    )
    transaction = db.transaction()

    def unblock_if_still_owned(transaction_in_progress: Any) -> None:
        resolved_owner_key = _resolve_owner_key_for_report(
            db,
            report_id,
            expected_owner_key=expected_owner_key,
            require_report_absent=require_report_absent,
            transaction=transaction_in_progress,
            expected_marker=expected_target_marker,
            marker_field=marker_field,
        )
        if resolved_owner_key != owner_key:
            raise RuntimeError("community_private_source_mismatch")
        current_block = _get_document_snapshot(
            source_block_document,
            transaction=transaction_in_progress,
        )
        _require_owned_snapshot(
            current_block,
            expected_marker=expected_target_marker,
            marker_field=marker_field,
        )
        transaction_in_progress.delete(source_block_document)

    decorator(unblock_if_still_owned)(transaction)
    return result


def block_group_sources(
    db: Any,
    group_id: str,
    *,
    hours: int,
    now: float,
    apply: bool,
) -> dict[str, Any]:
    if hours < 1 or hours > MAX_BLOCK_HOURS:
        raise ValueError(f"hours_must_be_between_1_and_{MAX_BLOCK_HOURS}")
    owner_keys = []
    moderation_snapshot = db.collection(MODERATION_COLLECTION).document(
        _moderation_document_id(group_id)
    ).get()
    if moderation_snapshot.exists:
        owner_keys.extend(
            str(value)
            for value in (
                (moderation_snapshot.to_dict() or {}).get("owner_keys") or []
            )
            if str(value)
        )
    for report_snapshot in _documents_for_group(db, REPORTS_COLLECTION, group_id):
        owner_key = str((report_snapshot.to_dict() or {}).get("owner_key") or "")
        if owner_key:
            owner_keys.append(owner_key)
    owner_keys = list(dict.fromkeys(owner_keys))
    if not owner_keys:
        raise RuntimeError("community_group_has_no_private_sources")

    blocked_until = now + hours * 60 * 60
    result = {
        "action": "block-group-sources",
        "group_id": group_id,
        "source_count": len(owner_keys),
        "hours": hours,
        "blocked_until": _utc_datetime(blocked_until).isoformat(),
        "applied": apply,
    }
    if not apply:
        return result

    require_single_batch_capacity("block-group-sources", len(owner_keys))
    batch = db.batch()
    for owner_key in owner_keys:
        batch.set(
            db.collection(SOURCE_BLOCKS_COLLECTION).document(
                _source_block_document_id(owner_key)
            ),
            {
                "blocked_until": blocked_until,
                "reason": "administrative_moderation",
                "group_id": group_id,
                "updated_at": _utc_datetime(now),
                "expires_at_timestamp": _utc_datetime(blocked_until),
            },
            merge=True,
        )
    batch.commit()
    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Moderazione privata delle segnalazioni Territorio."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("list", help="Elenca i gruppi con flag attivi.")
    inspect = subparsers.add_parser("inspect")
    inspect.add_argument("group_id")
    for command in ("hide", "restore", "remove"):
        action = subparsers.add_parser(command)
        action.add_argument("group_id")
        action.add_argument("--apply", action="store_true")
    block = subparsers.add_parser("block-source")
    block.add_argument("report_id")
    block.add_argument("--hours", type=int, default=DEFAULT_BLOCK_HOURS)
    block.add_argument("--apply", action="store_true")
    unblock = subparsers.add_parser("unblock-source")
    unblock.add_argument("report_id")
    unblock.add_argument("--apply", action="store_true")
    block_group = subparsers.add_parser("block-group-sources")
    block_group.add_argument("group_id")
    block_group.add_argument("--hours", type=int, default=DEFAULT_BLOCK_HOURS)
    block_group.add_argument("--apply", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    db = get_firestore_client()
    if db is None:
        raise RuntimeError(
            "Firestore Admin non disponibile: imposta COMMUNITY_STORAGE=firestore "
            "e credenziali Google/Firebase valide."
        )
    project_id = require_expected_project(db)
    now = time.time()
    if args.command == "list":
        result: Any = list_active_flags(db, now=now)
    elif args.command == "inspect":
        result = inspect_group(db, args.group_id, now=now)
    elif args.command == "hide":
        result = hide_group(db, args.group_id, now=now, apply=args.apply)
    elif args.command == "restore":
        result = restore_group(db, args.group_id, now=now, apply=args.apply)
    elif args.command == "remove":
        result = remove_group(db, args.group_id, now=now, apply=args.apply)
    elif args.command == "block-source":
        result = block_source(
            db,
            args.report_id,
            hours=args.hours,
            now=now,
            apply=args.apply,
        )
    elif args.command == "unblock-source":
        result = unblock_source(
            db,
            args.report_id,
            apply=args.apply,
        )
    else:
        result = block_group_sources(
            db,
            args.group_id,
            hours=args.hours,
            now=now,
            apply=args.apply,
        )
    print(json.dumps({
        "project_id": project_id,
        "result": result,
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
