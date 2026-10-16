r"""Guarded LIVE Firestore smoke test for Community moderation.

The target is deliberately fixed to the ``meteo-friul`` Firebase project.  A
run is read-only unless ``--apply`` is present.  The applied path creates only
private, synthetic QA documents; it never creates a ``community_reports``
document and never prints owner, flagger, or report identifiers.

Run from ``backend`` after configuring Firebase Admin credentials::

    $env:COMMUNITY_STORAGE = "firestore"
    .\venv\Scripts\python.exe tools\smoke_community_moderation_live.py
    .\venv\Scripts\python.exe tools\smoke_community_moderation_live.py --apply
    .\venv\Scripts\python.exe tools\smoke_community_moderation_live.py `
        --apply --hold-seconds 120

The applied run invokes the real moderation action functions and the real
digest producer with a unique, inert QA state document.  It never reads or
writes the production digest singleton.  Every owned QA document is removed
from a ``finally`` block and remains TTL-bounded after a hard process stop.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
import secrets
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.infrastructure.firebase import get_firestore_client  # noqa: E402
from app.repositories.community import (  # noqa: E402
    FLAGS_COLLECTION,
    MODERATION_COLLECTION,
    REPORTS_COLLECTION,
    SOURCE_BLOCKS_COLLECTION,
)
from app.services import community_moderation_digest as digest_service  # noqa: E402
from tools import moderate_community_reports as moderation_cli  # noqa: E402


EXPECTED_FIRESTORE_PROJECT_ID = "meteo-friul"
QA_MARKER_FIELD = "qa_smoke_marker"
QA_REASON = "misuse"
QA_RETENTION_SECONDS = 24 * 60 * 60
TTL_TOLERANCE_SECONDS = 0.001
MAX_HOLD_SECONDS = 120
RUN_TOKEN_PATTERN = re.compile(r"^[a-f0-9]{12,32}$")


class CommunityModerationLiveSmokeError(RuntimeError):
    """A public, non-sensitive smoke-test failure code."""

    def __init__(self, code: str) -> None:
        safe_code = str(code or "unexpected_failure").strip().lower()
        if re.fullmatch(r"[a-z0-9_]+", safe_code) is None:
            safe_code = "unexpected_failure"
        self.code = safe_code
        super().__init__(safe_code)


@dataclass(frozen=True)
class QaIdentity:
    """Private identifiers for one unguessable, non-publishable QA fixture."""

    marker: str
    group_id: str
    report_id: str
    owner_key: str
    flagger_key: str
    moderation_document_id: str
    flag_document_id: str
    source_block_document_id: str
    digest_state_document_id: str


@dataclass(frozen=True)
class DocumentBackup:
    exists: bool
    payload: dict[str, Any]


def _utc_datetime(value: float) -> datetime:
    return datetime.fromtimestamp(float(value), timezone.utc)


def _timestamp(value: Any) -> float:
    if isinstance(value, datetime):
        return value.timestamp()
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _qa_identity(run_token: str, *, now: float) -> QaIdentity:
    token = str(run_token or "").strip().lower()
    if RUN_TOKEN_PATTERN.fullmatch(token) is None:
        raise CommunityModerationLiveSmokeError("qa_run_token_invalid")
    marker = f"community-moderation-live-smoke:{token}"
    group_id = f"group-quiet:qa-smoke-{token}:{max(1, int(now))}"
    report_id = "qa-smoke-" + hashlib.sha256(
        f"{marker}:report".encode("utf-8")
    ).hexdigest()[:32]
    owner_key = hashlib.sha256(
        f"{marker}:owner".encode("utf-8")
    ).hexdigest()
    flagger_key = hashlib.sha256(
        f"{marker}:flagger".encode("utf-8")
    ).hexdigest()
    return QaIdentity(
        marker=marker,
        group_id=group_id,
        report_id=report_id,
        owner_key=owner_key,
        flagger_key=flagger_key,
        moderation_document_id=hashlib.sha256(
            group_id.encode("utf-8")
        ).hexdigest(),
        flag_document_id=hashlib.sha256(
            f"{group_id}:{flagger_key}".encode("utf-8")
        ).hexdigest(),
        source_block_document_id=hashlib.sha256(
            owner_key.encode("utf-8")
        ).hexdigest(),
        digest_state_document_id="qa-smoke-" + hashlib.sha256(
            f"{marker}:digest-state".encode("utf-8")
        ).hexdigest()[:32],
    )


def _snapshot(
    document: Any,
    *,
    transaction: Any | None = None,
) -> DocumentBackup:
    snapshot = (
        document.get()
        if transaction is None
        else document.get(transaction=transaction)
    )
    return DocumentBackup(
        exists=bool(snapshot.exists),
        payload=(
            copy.deepcopy(dict(snapshot.to_dict() or {}))
            if snapshot.exists
            else {}
        ),
    )


def _query_has_document(
    db: Any,
    collection: str,
    field: str,
    operator: str,
    value: Any,
) -> bool:
    query = db.collection(collection).where(
        filter=moderation_cli._field_filter(field, operator, value)
    ).limit(1)
    return next(iter(query.stream()), None) is not None


def _document_refs(db: Any, identity: QaIdentity) -> dict[str, Any]:
    return {
        "flag": db.collection(FLAGS_COLLECTION).document(
            identity.flag_document_id
        ),
        "moderation": db.collection(MODERATION_COLLECTION).document(
            identity.moderation_document_id
        ),
        "source_block": db.collection(SOURCE_BLOCKS_COLLECTION).document(
            identity.source_block_document_id
        ),
        # This reference is read-only.  It is guarded explicitly because the
        # real block-source action resolves an owner from a report first.
        "report": db.collection(REPORTS_COLLECTION).document(
            identity.report_id
        ),
        "digest_state": db.collection(
            digest_service.DIGEST_STATE_COLLECTION
        ).document(identity.digest_state_document_id),
    }


def _require_no_collision(
    db: Any,
    identity: QaIdentity,
    refs: dict[str, Any],
) -> None:
    if any(
        _snapshot(refs[name]).exists
        for name in (
            "flag",
            "moderation",
            "source_block",
            "digest_state",
            "report",
        )
    ):
        raise CommunityModerationLiveSmokeError("qa_document_collision")

    # Group queries protect the real hide/restore actions from touching a
    # malformed document stored under a non-canonical document id.
    for collection in (
        FLAGS_COLLECTION,
        MODERATION_COLLECTION,
        REPORTS_COLLECTION,
    ):
        if _query_has_document(
            db,
            collection,
            "group_id",
            "==",
            identity.group_id,
        ):
            raise CommunityModerationLiveSmokeError("qa_document_collision")

    # An expired report can still be resolved through a moderation snapshot.
    # Protect that fallback query from ever selecting a pre-existing source.
    if _query_has_document(
        db,
        MODERATION_COLLECTION,
        "report_ids",
        "array_contains",
        identity.report_id,
    ):
        raise CommunityModerationLiveSmokeError("qa_document_collision")


def _require_no_public_report(
    db: Any,
    identity: QaIdentity,
    refs: dict[str, Any],
) -> None:
    if _snapshot(refs["report"]).exists or _query_has_document(
        db,
        REPORTS_COLLECTION,
        "group_id",
        "==",
        identity.group_id,
    ):
        raise CommunityModerationLiveSmokeError(
            "community_report_collision"
        )


def _flag_payload(
    identity: QaIdentity,
    *,
    now: float,
) -> dict[str, Any]:
    return {
        QA_MARKER_FIELD: identity.marker,
        "group_id": identity.group_id,
        "client_key": identity.flagger_key,
        "reason": QA_REASON,
        "report_ids": [identity.report_id],
        "owner_keys": [identity.owner_key],
        "report_sources": {identity.report_id: identity.owner_key},
        "created_at_timestamp": _utc_datetime(now),
        "expires_at_timestamp": _utc_datetime(
            now + QA_RETENTION_SECONDS
        ),
    }


def _moderation_payload(
    identity: QaIdentity,
    *,
    now: float,
) -> dict[str, Any]:
    return {
        QA_MARKER_FIELD: identity.marker,
        "group_id": identity.group_id,
        "flag_count": 1,
        "flaggers": {identity.flagger_key: QA_REASON},
        "report_ids": [identity.report_id],
        "owner_keys": [identity.owner_key],
        "report_sources": {identity.report_id: identity.owner_key},
        "hidden": False,
        "hidden_at": None,
        "hidden_reason": "",
        "updated_at": _utc_datetime(now),
        "expires_at_timestamp": _utc_datetime(
            now + QA_RETENTION_SECONDS
        ),
    }


def _source_block_reservation_payload(
    identity: QaIdentity,
    *,
    now: float,
) -> dict[str, Any]:
    blocked_until = now + QA_RETENTION_SECONDS
    return {
        QA_MARKER_FIELD: identity.marker,
        "blocked_until": blocked_until,
        "reason": "qa_smoke_reservation",
        "report_id": identity.report_id,
        "updated_at": _utc_datetime(now),
        "expires_at_timestamp": _utc_datetime(blocked_until),
    }


def _digest_state_reservation_payload(
    identity: QaIdentity,
    *,
    now: float,
) -> dict[str, Any]:
    return {
        digest_service.DIGEST_STATE_OWNER_MARKER_FIELD: identity.marker,
        "seen": {},
        "flag_counts": {},
        "updated_at_timestamp": _utc_datetime(now),
        "expires_at_timestamp": _utc_datetime(
            now + digest_service.DIGEST_STATE_RETENTION_SECONDS
        ),
    }


def _require_timestamp_ttl(
    payload: dict[str, Any],
    *,
    expected: float,
    failure_code: str,
) -> None:
    value = payload.get("expires_at_timestamp")
    if not isinstance(value, datetime) or abs(
        _timestamp(value) - float(expected)
    ) > TTL_TOLERANCE_SECONDS:
        raise CommunityModerationLiveSmokeError(failure_code)


def _require_owned_payload(
    backup: DocumentBackup,
    identity: QaIdentity,
    *,
    missing_code: str,
) -> dict[str, Any]:
    if not backup.exists:
        raise CommunityModerationLiveSmokeError(missing_code)
    if backup.payload.get(QA_MARKER_FIELD) != identity.marker:
        raise CommunityModerationLiveSmokeError("qa_document_ownership_lost")
    return backup.payload


def _create_seed_documents(
    db: Any,
    identity: QaIdentity,
    refs: dict[str, Any],
    *,
    now: float,
    recreate: bool,
    transactional_decorator: (
        Callable[[Callable[..., Any]], Callable[..., Any]] | None
    ) = None,
) -> None:
    _require_no_public_report(db, identity, refs)
    flag_payload = _flag_payload(identity, now=now)
    moderation_payload = _moderation_payload(identity, now=now)
    if recreate:
        decorator = transactional_decorator
        if decorator is None:
            from google.cloud import firestore

            decorator = firestore.transactional
        transaction = db.transaction()

        def recreate_if_still_owned(
            transaction_in_progress: Any,
        ) -> None:
            moderation_backup = _snapshot(
                refs["moderation"],
                transaction=transaction_in_progress,
            )
            _require_owned_payload(
                moderation_backup,
                identity,
                missing_code="qa_moderation_create_failed",
            )
            flag_backup = _snapshot(
                refs["flag"],
                transaction=transaction_in_progress,
            )
            if flag_backup.exists:
                raise CommunityModerationLiveSmokeError(
                    "qa_document_collision"
                )
            transaction_in_progress.set(
                refs["flag"],
                flag_payload,
                merge=False,
            )
            transaction_in_progress.set(
                refs["moderation"],
                moderation_payload,
                merge=False,
            )

        decorator(recreate_if_still_owned)(transaction)
    else:
        batch = db.batch()
        batch.create(refs["flag"], flag_payload)
        batch.create(refs["moderation"], moderation_payload)
        batch.create(
            refs["digest_state"],
            _digest_state_reservation_payload(identity, now=now),
        )
        batch.commit()
    _require_no_public_report(db, identity, refs)

    stored_flag = _require_owned_payload(
        _snapshot(refs["flag"]),
        identity,
        missing_code="qa_flag_create_failed",
    )
    stored_moderation = _require_owned_payload(
        _snapshot(refs["moderation"]),
        identity,
        missing_code="qa_moderation_create_failed",
    )
    expected_expiry = now + QA_RETENTION_SECONDS
    _require_timestamp_ttl(
        stored_flag,
        expected=expected_expiry,
        failure_code="qa_flag_ttl_invalid",
    )
    _require_timestamp_ttl(
        stored_moderation,
        expected=expected_expiry,
        failure_code="qa_moderation_ttl_invalid",
    )
    if not recreate:
        digest_reservation = _snapshot(refs["digest_state"])
        if (
            not digest_reservation.exists
            or digest_reservation.payload.get(
                digest_service.DIGEST_STATE_OWNER_MARKER_FIELD
            )
            != identity.marker
        ):
            raise CommunityModerationLiveSmokeError(
                "qa_digest_state_create_failed"
            )
        _require_timestamp_ttl(
            digest_reservation.payload,
            expected=(
                now + digest_service.DIGEST_STATE_RETENTION_SECONDS
            ),
            failure_code="qa_digest_state_ttl_invalid",
        )


def _validated_hold_seconds(value: Any, *, apply: bool) -> int:
    try:
        selected = int(value)
    except (TypeError, ValueError) as error:
        raise CommunityModerationLiveSmokeError(
            "hold_seconds_invalid"
        ) from error
    if selected < 0 or selected > MAX_HOLD_SECONDS:
        raise CommunityModerationLiveSmokeError(
            "hold_seconds_out_of_bounds"
        )
    if selected and not apply:
        raise CommunityModerationLiveSmokeError(
            "hold_seconds_requires_apply"
        )
    return selected


def _evidence_ready_payload(*, hold_seconds: int) -> dict[str, Any]:
    return {
        "event": "community_moderation_live_smoke_evidence_ready",
        "project_id": EXPECTED_FIRESTORE_PROJECT_ID,
        "applied": True,
        "hold_seconds": int(hold_seconds),
        "ttl_sample_count": 4,
        "community_reports_created": 0,
        "contains_private_keys": False,
    }


def _print_evidence_ready(payload: dict[str, Any]) -> None:
    print(
        json.dumps(payload, ensure_ascii=True, sort_keys=True),
        flush=True,
    )


def _call_action(
    failure_code: str,
    action: Callable[[], dict[str, Any]],
) -> dict[str, Any]:
    try:
        return dict(action() or {})
    except CommunityModerationLiveSmokeError:
        raise
    except Exception as error:
        raise CommunityModerationLiveSmokeError(failure_code) from error


def _contains_group(result: dict[str, Any], group_id: str) -> bool:
    expected_reference = digest_service.moderation_group_reference(group_id)
    return any(
        str(group.get("group_ref") or "") == expected_reference
        for group in (result.get("groups") or [])
        if isinstance(group, dict)
    )


def _delete_owned_documents(
    db: Any,
    documents: dict[str, Any],
    identity: QaIdentity,
    *,
    transactional_decorator: (
        Callable[[Callable[..., Any]], Callable[..., Any]] | None
    ),
) -> None:
    decorator = transactional_decorator
    if decorator is None:
        from google.cloud import firestore

        decorator = firestore.transactional
    transaction = db.transaction()

    def delete_if_still_owned(transaction_in_progress: Any) -> None:
        current = {
            name: _snapshot(
                document,
                transaction=transaction_in_progress,
            )
            for name, document in documents.items()
        }
        # Validate every marker before scheduling any delete. Firestore binds
        # the deletes to these read versions; a concurrent replacement forces
        # a transaction retry, whose fresh marker check fails closed.
        for snapshot in current.values():
            if not snapshot.exists:
                continue
            marker = snapshot.payload.get(QA_MARKER_FIELD) or (
                snapshot.payload.get(
                    digest_service.DIGEST_STATE_OWNER_MARKER_FIELD
                )
            )
            if marker != identity.marker:
                raise CommunityModerationLiveSmokeError(
                    "qa_document_ownership_lost"
                )
        for name, snapshot in current.items():
            if snapshot.exists:
                transaction_in_progress.delete(documents[name])

    try:
        decorator(delete_if_still_owned)(transaction)
    except CommunityModerationLiveSmokeError:
        raise
    except Exception as error:
        raise CommunityModerationLiveSmokeError(
            "qa_cleanup_transaction_failed"
        ) from error

    for document in documents.values():
        if _snapshot(document).exists:
            raise CommunityModerationLiveSmokeError(
                "qa_cleanup_incomplete"
            )


def _cleanup(
    db: Any,
    identity: QaIdentity,
    refs: dict[str, Any],
    *,
    qa_write_attempted: bool,
    source_unblock_required: bool,
    transactional_decorator: (
        Callable[[Callable[..., Any]], Callable[..., Any]] | None
    ),
) -> None:
    failures: list[BaseException] = []
    if source_unblock_required:
        try:
            unblocked = moderation_cli.unblock_source(
                db,
                identity.report_id,
                apply=True,
                expected_owner_key=identity.owner_key,
                require_report_absent=True,
                expected_target_marker=identity.marker,
                marker_field=QA_MARKER_FIELD,
                transactional_decorator=transactional_decorator,
            )
            if not unblocked.get("applied") or _snapshot(
                refs["source_block"]
            ).exists:
                raise CommunityModerationLiveSmokeError(
                    "unblock_action_failed"
                )
        except BaseException as error:  # marker deletion below still runs
            failures.append(error)

    if qa_write_attempted:
        try:
            _delete_owned_documents(
                db,
                {
                    name: refs[name]
                    for name in (
                        "source_block",
                        "flag",
                        "moderation",
                        "digest_state",
                    )
                },
                identity,
                transactional_decorator=transactional_decorator,
            )
        except BaseException as error:
            failures.append(error)

    # A Community report is never owned by this tool and therefore is never
    # deleted by it.  Its appearance is a hard failure, not something to hide.
    try:
        if _snapshot(refs["report"]).exists or _query_has_document(
            db,
            REPORTS_COLLECTION,
            "group_id",
            "==",
            identity.group_id,
        ):
            failures.append(
                CommunityModerationLiveSmokeError(
                    "community_report_collision"
                )
            )
    except BaseException as error:
        failures.append(error)

    if failures:
        if any(
            isinstance(error, CommunityModerationLiveSmokeError)
            and error.code == "community_report_collision"
            for error in failures
        ):
            raise CommunityModerationLiveSmokeError(
                "community_report_collision"
            )
        raise CommunityModerationLiveSmokeError("smoke_cleanup_failed")


def _apply_smoke(
    db: Any,
    identity: QaIdentity,
    refs: dict[str, Any],
    *,
    now: float,
    digest_now: float,
    transactional_decorator: (
        Callable[[Callable[..., Any]], Callable[..., Any]] | None
    ),
    hold_seconds: int,
    evidence_emitter: Callable[[dict[str, Any]], None],
    sleep_fn: Callable[[float], None],
    on_source_unblock_required: Callable[[], None],
) -> dict[str, Any]:
    seed_now = float(now)
    _create_seed_documents(
        db,
        identity,
        refs,
        now=seed_now,
        recreate=False,
        transactional_decorator=transactional_decorator,
    )

    hide_now = seed_now
    _require_no_public_report(db, identity, refs)
    hidden = _call_action(
        "hide_action_failed",
        lambda: moderation_cli.hide_group(
            db,
            identity.group_id,
            now=hide_now,
            apply=True,
            expected_report_count=0,
            expected_marker=identity.marker,
            marker_field=QA_MARKER_FIELD,
            transactional_decorator=transactional_decorator,
        ),
    )
    _require_no_public_report(db, identity, refs)
    hidden_state = _require_owned_payload(
        _snapshot(refs["moderation"]),
        identity,
        missing_code="hide_action_failed",
    )
    _require_timestamp_ttl(
        hidden_state,
        expected=hide_now + QA_RETENTION_SECONDS,
        failure_code="qa_moderation_ttl_invalid",
    )
    if (
        not hidden.get("applied")
        or int(hidden.get("reports") or 0) != 0
        or not bool(hidden_state.get("hidden"))
    ):
        raise CommunityModerationLiveSmokeError("hide_action_failed")

    restore_now = seed_now
    _require_no_public_report(db, identity, refs)
    restored = _call_action(
        "restore_action_failed",
        lambda: moderation_cli.restore_group(
            db,
            identity.group_id,
            now=restore_now,
            apply=True,
            expected_report_count=0,
            expected_marker=identity.marker,
            marker_field=QA_MARKER_FIELD,
            transactional_decorator=transactional_decorator,
        ),
    )
    _require_no_public_report(db, identity, refs)
    restored_state = _require_owned_payload(
        _snapshot(refs["moderation"]),
        identity,
        missing_code="restore_action_failed",
    )
    _require_timestamp_ttl(
        restored_state,
        expected=restore_now + QA_RETENTION_SECONDS,
        failure_code="qa_moderation_ttl_invalid",
    )
    if (
        not restored.get("applied")
        or int(restored.get("reports") or 0) != 0
        or int(restored.get("flags_cleared") or 0) != 1
        or bool(restored_state.get("hidden"))
        or int(restored_state.get("flag_count") or 0) != 0
        or _snapshot(refs["flag"]).exists
    ):
        raise CommunityModerationLiveSmokeError("restore_action_failed")

    # Recreate the same private fixture so block-source and the digest operate
    # on an active flag after restore has proved that it clears the first one.
    actionable_now = seed_now
    _create_seed_documents(
        db,
        identity,
        refs,
        now=actionable_now,
        recreate=True,
        transactional_decorator=transactional_decorator,
    )

    block_now = seed_now
    _require_no_public_report(db, identity, refs)
    try:
        refs["source_block"].create(
            _source_block_reservation_payload(
                identity,
                now=block_now,
            )
        )
    except Exception as error:
        raise CommunityModerationLiveSmokeError(
            "source_block_reservation_failed"
        ) from error
    on_source_unblock_required()
    _require_no_public_report(db, identity, refs)
    blocked = _call_action(
        "block_action_failed",
        lambda: moderation_cli.block_source(
            db,
            identity.report_id,
            hours=24,
            now=block_now,
            apply=True,
            expected_owner_key=identity.owner_key,
            require_report_absent=True,
            expected_target_marker=identity.marker,
            marker_field=QA_MARKER_FIELD,
            transactional_decorator=transactional_decorator,
        ),
    )
    _require_no_public_report(db, identity, refs)
    blocked_state = _require_owned_payload(
        _snapshot(refs["source_block"]),
        identity,
        missing_code="block_action_failed",
    )
    expected_block_expiry = block_now + QA_RETENTION_SECONDS
    _require_timestamp_ttl(
        blocked_state,
        expected=expected_block_expiry,
        failure_code="qa_source_block_ttl_invalid",
    )
    if (
        not blocked.get("applied")
        or int(blocked.get("hours") or 0) != 24
        or abs(
            _timestamp(blocked_state.get("blocked_until"))
            - expected_block_expiry
        ) > TTL_TOLERANCE_SECONDS
    ):
        raise CommunityModerationLiveSmokeError("block_action_failed")

    _require_no_public_report(db, identity, refs)
    first_digest = _call_action(
        "digest_first_apply_failed",
        lambda: digest_service.produce_moderation_digest(
            db,
            now=digest_now,
            apply=True,
            transactional_decorator=transactional_decorator,
            state_document_id=identity.digest_state_document_id,
            state_owner_marker=identity.marker,
        ),
    )
    if (
        not first_digest.get("applied")
        or not first_digest.get("should_emit")
        or not _contains_group(first_digest, identity.group_id)
    ):
        raise CommunityModerationLiveSmokeError(
            "digest_first_apply_failed"
        )

    digest_state = _snapshot(refs["digest_state"])
    if not digest_state.exists:
        raise CommunityModerationLiveSmokeError(
            "digest_first_apply_failed"
        )
    if digest_state.payload.get(
        digest_service.DIGEST_STATE_OWNER_MARKER_FIELD
    ) != identity.marker:
        raise CommunityModerationLiveSmokeError(
            "qa_digest_state_ownership_lost"
        )
    _require_timestamp_ttl(
        digest_state.payload,
        expected=(
            digest_now + digest_service.DIGEST_STATE_RETENTION_SECONDS
        ),
        failure_code="qa_digest_state_ttl_invalid",
    )

    _require_no_public_report(db, identity, refs)
    second_digest = _call_action(
        "digest_second_apply_failed",
        lambda: digest_service.produce_moderation_digest(
            db,
            now=digest_now,
            apply=True,
            transactional_decorator=transactional_decorator,
            state_document_id=identity.digest_state_document_id,
            state_owner_marker=identity.marker,
        ),
    )
    deduplicated = (
        not bool(second_digest.get("applied"))
        and bool(second_digest.get("should_emit"))
        and bool(second_digest.get("pending_reused"))
        and second_digest.get("digest_id") == first_digest.get("digest_id")
        and _contains_group(second_digest, identity.group_id)
    )
    if not deduplicated:
        raise CommunityModerationLiveSmokeError(
            "digest_deduplication_failed"
        )

    acknowledged_digest = _call_action(
        "digest_acknowledgement_failed",
        lambda: digest_service.acknowledge_moderation_digest(
            db,
            digest_id=str(second_digest.get("digest_id") or ""),
            now=digest_now,
            transactional_decorator=transactional_decorator,
            state_document_id=identity.digest_state_document_id,
            state_owner_marker=identity.marker,
        ),
    )
    if not bool(acknowledged_digest.get("acknowledged")):
        raise CommunityModerationLiveSmokeError(
            "digest_acknowledgement_failed"
        )
    acknowledged_state = _snapshot(refs["digest_state"])
    if (
        not acknowledged_state.exists
        or acknowledged_state.payload.get(
            digest_service.DIGEST_STATE_OWNER_MARKER_FIELD
        )
        != identity.marker
        or acknowledged_state.payload.get("last_digest_id")
        != second_digest.get("digest_id")
        or digest_service.DIGEST_PENDING_FIELD
        in acknowledged_state.payload
    ):
        raise CommunityModerationLiveSmokeError(
            "digest_acknowledgement_failed"
        )

    _require_no_public_report(db, identity, refs)

    if not all(
        _snapshot(refs[name]).exists
        for name in ("flag", "moderation", "source_block", "digest_state")
    ):
        raise CommunityModerationLiveSmokeError(
            "ttl_evidence_not_ready"
        )
    evidence = _evidence_ready_payload(hold_seconds=hold_seconds)
    try:
        evidence_emitter(evidence)
    except Exception as error:
        raise CommunityModerationLiveSmokeError(
            "evidence_ready_emit_failed"
        ) from error
    if hold_seconds > 0:
        try:
            sleep_fn(float(hold_seconds))
        except Exception as error:
            raise CommunityModerationLiveSmokeError(
                "evidence_hold_failed"
            ) from error
    _require_no_public_report(db, identity, refs)

    # Deliberately expose only bounded booleans and counts.  Raw action and
    # digest payloads contain operator-useful group/report references and must
    # never become this tool's output.
    return {
        "event": "community_moderation_live_smoke_completed",
        "project_id": EXPECTED_FIRESTORE_PROJECT_ID,
        "mode": "apply",
        "applied": True,
        "checks": {
            "collision_guard": True,
            "flag_ttl": True,
            "moderation_ttl": True,
            "source_block_ttl": True,
            "digest_state_ttl": True,
            "hide": True,
            "restore": True,
            "block": True,
            "unblock": True,
            "evidence_ready": True,
            "digest_first_apply": True,
            "digest_retry_deduplicated": True,
            "digest_acknowledged": True,
            "cleanup": True,
            "isolated_digest_state": True,
            "shared_digest_state_untouched": True,
        },
        "community_reports_created": 0,
        "hold_seconds": int(hold_seconds),
        "contains_private_keys": False,
    }


def run_smoke(
    db: Any,
    *,
    apply: bool,
    now: float | None = None,
    run_token: str | None = None,
    hold_seconds: int = 0,
    transactional_decorator: (
        Callable[[Callable[..., Any]], Callable[..., Any]] | None
    ) = None,
    evidence_emitter: Callable[[dict[str, Any]], None] | None = None,
    sleep_fn: Callable[[float], None] | None = None,
) -> dict[str, Any]:
    """Run the guarded preview or applied smoke test against ``db``."""

    try:
        project_id = moderation_cli.require_expected_project(db)
    except Exception as error:
        raise CommunityModerationLiveSmokeError(
            "firestore_project_mismatch"
        ) from error
    if project_id != EXPECTED_FIRESTORE_PROJECT_ID:
        raise CommunityModerationLiveSmokeError(
            "firestore_project_mismatch"
        )

    selected_hold_seconds = _validated_hold_seconds(
        hold_seconds,
        apply=apply,
    )

    selected_now = float(now if now is not None else time.time())
    identity = _qa_identity(
        run_token or secrets.token_hex(12),
        now=selected_now,
    )
    refs = _document_refs(db, identity)
    try:
        _require_no_collision(db, identity, refs)
        _require_no_public_report(db, identity, refs)
        digest_now = selected_now
    except CommunityModerationLiveSmokeError:
        raise
    except Exception as error:
        raise CommunityModerationLiveSmokeError(
            "live_preflight_failed"
        ) from error

    if not apply:
        return {
            "event": "community_moderation_live_smoke_preview",
            "project_id": EXPECTED_FIRESTORE_PROJECT_ID,
            "mode": "dry-run",
            "applied": False,
            "checks": {
                "collision_guard": True,
                "isolated_digest_state_collision_guard": True,
            },
            "planned_private_qa_documents": 4,
            "hold_seconds": 0,
            "community_reports_created": 0,
            "contains_private_keys": False,
        }

    qa_write_attempted = False
    source_unblock_required = False
    result: dict[str, Any] | None = None
    operation_error: BaseException | None = None
    cleanup_error: BaseException | None = None
    try:
        # Set before the first atomic create: a lost acknowledgement may still
        # mean the server committed, so marker-checked cleanup must run.
        qa_write_attempted = True

        def mark_source_unblock_required() -> None:
            nonlocal source_unblock_required
            source_unblock_required = True

        result = _apply_smoke(
            db,
            identity,
            refs,
            now=selected_now,
            digest_now=digest_now,
            transactional_decorator=transactional_decorator,
            hold_seconds=selected_hold_seconds,
            evidence_emitter=evidence_emitter or _print_evidence_ready,
            sleep_fn=sleep_fn or time.sleep,
            on_source_unblock_required=mark_source_unblock_required,
        )
    except BaseException as error:
        operation_error = error
    finally:
        try:
            _cleanup(
                db,
                identity,
                refs,
                qa_write_attempted=qa_write_attempted,
                source_unblock_required=source_unblock_required,
                transactional_decorator=transactional_decorator,
            )
        except BaseException as error:
            cleanup_error = error

    if cleanup_error is not None:
        if isinstance(
            cleanup_error,
            CommunityModerationLiveSmokeError,
        ) and cleanup_error.code == "community_report_collision":
            raise cleanup_error
        raise CommunityModerationLiveSmokeError(
            "smoke_cleanup_failed"
        ) from cleanup_error
    if operation_error is not None:
        if isinstance(operation_error, CommunityModerationLiveSmokeError):
            raise operation_error
        raise CommunityModerationLiveSmokeError(
            "unexpected_operation_failure"
        ) from operation_error
    if result is None:
        raise CommunityModerationLiveSmokeError(
            "unexpected_operation_failure"
        )
    return result


def _parse_hold_seconds_argument(value: str) -> int:
    try:
        selected = int(value)
    except (TypeError, ValueError) as error:
        raise argparse.ArgumentTypeError(
            "--hold-seconds deve essere un intero"
        ) from error
    if selected < 0 or selected > MAX_HOLD_SECONDS:
        raise argparse.ArgumentTypeError(
            f"--hold-seconds deve essere tra 0 e {MAX_HOLD_SECONDS}"
        )
    return selected


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        allow_abbrev=False,
        description=(
            "Smoke LIVE privato della moderazione Community; target fisso "
            "meteo-friul, dry-run di default."
        )
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help=(
            "Crea temporaneamente i documenti QA privati, esegue le azioni "
            "reali e li elimina sempre al termine."
        ),
    )
    parser.add_argument(
        "--hold-seconds",
        type=_parse_hold_seconds_argument,
        default=0,
        metavar="SECONDS",
        help=(
            "Con --apply, mantiene disponibili i quattro campioni TTL dopo "
            f"l'evento evidence-ready (0-{MAX_HOLD_SECONDS} secondi)."
        ),
    )
    return parser


def main(
    argv: list[str] | None = None,
    *,
    db: Any | None = None,
    now: float | None = None,
    run_token: str | None = None,
    transactional_decorator: (
        Callable[[Callable[..., Any]], Callable[..., Any]] | None
    ) = None,
    evidence_emitter: Callable[[dict[str, Any]], None] | None = None,
    sleep_fn: Callable[[float], None] | None = None,
) -> int:
    selected_argv = list(argv) if argv is not None else sys.argv[1:]
    parser = build_parser()
    args = parser.parse_args(selected_argv)
    hold_was_explicit = any(
        value == "--hold-seconds"
        or value.startswith("--hold-seconds=")
        for value in selected_argv
    )
    if hold_was_explicit and not args.apply:
        parser.error("--hold-seconds e' valido solo insieme a --apply")
    try:
        selected_db = db if db is not None else get_firestore_client()
    except Exception:
        selected_db = None
    if selected_db is None:
        payload = {
            "event": "community_moderation_live_smoke_failed",
            "status": "storage_unavailable",
            "applied": False,
            "community_reports_created": 0,
            "contains_private_keys": False,
        }
        print(json.dumps(payload, ensure_ascii=True, sort_keys=True))
        return 1

    try:
        result = run_smoke(
            selected_db,
            apply=bool(args.apply),
            now=now,
            run_token=run_token,
            hold_seconds=int(args.hold_seconds),
            transactional_decorator=transactional_decorator,
            evidence_emitter=evidence_emitter,
            sleep_fn=sleep_fn,
        )
    except CommunityModerationLiveSmokeError as error:
        payload = {
            "event": "community_moderation_live_smoke_failed",
            "status": error.code,
            "applied": False,
            "community_reports_created": 0,
            "contains_private_keys": False,
        }
        print(json.dumps(payload, ensure_ascii=True, sort_keys=True))
        return 1
    except Exception:
        payload = {
            "event": "community_moderation_live_smoke_failed",
            "status": "unexpected_failure",
            "applied": False,
            "community_reports_created": 0,
            "contains_private_keys": False,
        }
        print(json.dumps(payload, ensure_ascii=True, sort_keys=True))
        return 1

    print(json.dumps(result, ensure_ascii=True, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
