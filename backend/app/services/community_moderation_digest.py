"""Durable, privacy-bounded moderation digests for Territorio.

An applied producer transaction creates (or reuses) a sanitized pending
digest. The caller publishes that pending digest, then acknowledges it in a
separate transaction. A crash before publication therefore leaves work
pending, while a crash after publication can produce only an at-least-once
duplicate carrying the same stable ``digest_id``.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from datetime import datetime, timezone
from typing import Any, Callable

from app.repositories.community import MODERATION_COLLECTION
from app.weather.timezone_support import get_fvg_timezone


DIGEST_STATE_COLLECTION = "community_moderation_digest_state"
DIGEST_STATE_DOCUMENT = "territorio"
DIGEST_STATE_OWNER_MARKER_FIELD = "qa_smoke_marker"
DIGEST_PENDING_FIELD = "pending_digest"
DIGEST_STATE_RETENTION_SECONDS = 48 * 60 * 60
DIGEST_PENDING_MAX_AGE_SECONDS = 24 * 60 * 60
MAX_ACTIONABLE_GROUPS = 200
EXPECTED_FIRESTORE_PROJECT_ID = "meteo-friul"
ALLOWED_REASONS = frozenset({"inaccurate", "duplicate", "misuse"})
MAX_FLAGS_PER_GROUP = 50
MAX_REPORTS_PER_GROUP = 200
CANONICAL_GROUP_ID_PATTERN = re.compile(
    r"^group-(?:rain|storm|snow|hail|fog|wind|ice|quiet):"
    r"[a-z0-9_-]{1,96}:[0-9]{1,16}$"
)
GROUP_REFERENCE_PATTERN = re.compile(r"^[0-9a-f]{24}$")
FINGERPRINT_PATTERN = re.compile(r"^[0-9a-f]{64}$")
DIGEST_ID_PATTERN = re.compile(r"^[0-9a-f]{64}$")
DELIVERY_SLOT_PATTERN = re.compile(
    r"^[0-9]{4}-[0-9]{2}-[0-9]{2}:(?:am|pm)$"
)


class CommunityModerationDigestError(RuntimeError):
    """Raised before emitting or persisting an incomplete digest."""


def _timestamp(value: Any) -> float:
    if isinstance(value, datetime):
        return value.timestamp()
    try:
        return float(value)
    except (TypeError, ValueError):
        try:
            selected = datetime.fromisoformat(str(value or ""))
            return selected.timestamp() if selected.tzinfo is not None else 0
        except (TypeError, ValueError):
            return 0


def _utc_datetime(value: float) -> datetime:
    return datetime.fromtimestamp(float(value), timezone.utc)


def _field_filter(field: str, operator: str, value: Any) -> Any:
    from google.cloud.firestore_v1.base_query import FieldFilter

    return FieldFilter(field, operator, value)


def require_digest_project(db: Any) -> str:
    project_id = str(getattr(db, "project", "") or "").strip()
    if project_id != EXPECTED_FIRESTORE_PROJECT_ID:
        raise CommunityModerationDigestError(
            "firestore_project_mismatch: expected "
            f"{EXPECTED_FIRESTORE_PROJECT_ID!r}, received "
            f"{project_id or '<unknown>'!r}"
        )
    return project_id


def moderation_group_reference(group_id: str) -> str:
    """Return the only group reference permitted in digest state and logs."""

    return hashlib.sha256(group_id.encode("utf-8")).hexdigest()[:24]


def _fingerprint(group_id: str, flag_count: int, reasons: dict[str, int]) -> str:
    serialized = json.dumps(
        {
            "group_id": group_id,
            "flag_count": flag_count,
            "reasons": reasons,
        },
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def delivery_slot_for_timestamp(now: float) -> str:
    """Map an instant to an explicit Europe/Rome local AM/PM slot."""

    local = _utc_datetime(now).astimezone(get_fvg_timezone())
    half_day = "am" if local.hour < 12 else "pm"
    return f"{local.date().isoformat()}:{half_day}"


def _validated_delivery_slot(value: Any) -> str:
    selected = str(value or "").strip()
    if DELIVERY_SLOT_PATTERN.fullmatch(selected) is None:
        raise CommunityModerationDigestError("digest_delivery_slot_invalid")
    try:
        datetime.strptime(selected[:10], "%Y-%m-%d")
    except ValueError as error:
        raise CommunityModerationDigestError(
            "digest_delivery_slot_invalid"
        ) from error
    return selected


def _sanitize_actionable_group(
    payload: dict[str, Any],
    *,
    now: float,
) -> dict[str, Any] | None:
    expires_at = _timestamp(payload.get("expires_at_timestamp"))
    if expires_at <= now or bool(payload.get("hidden", False)):
        return None

    group_id = str(payload.get("group_id") or "").strip()
    if not group_id:
        raise CommunityModerationDigestError("moderation_group_id_missing")
    if CANONICAL_GROUP_ID_PATTERN.fullmatch(group_id) is None:
        # Never echo a corrupted raw identifier through an exception or digest.
        raise CommunityModerationDigestError("moderation_group_id_invalid")

    flaggers = payload.get("flaggers")
    if not isinstance(flaggers, dict):
        raise CommunityModerationDigestError("moderation_flaggers_invalid")
    if len(flaggers) > MAX_FLAGS_PER_GROUP or any(
        not isinstance(key, str) or not key.strip() for key in flaggers
    ):
        raise CommunityModerationDigestError("moderation_flaggers_invalid")
    reason_values = [str(value or "").strip() for value in flaggers.values()]
    if any(reason not in ALLOWED_REASONS for reason in reason_values):
        raise CommunityModerationDigestError("moderation_reason_invalid")

    try:
        flag_count = int(payload.get("flag_count") or 0)
    except (TypeError, ValueError) as error:
        raise CommunityModerationDigestError(
            "moderation_flag_count_invalid"
        ) from error
    if flag_count != len(flaggers):
        raise CommunityModerationDigestError("moderation_flag_count_mismatch")
    if flag_count <= 0:
        return None

    raw_report_ids = payload.get("report_ids") or []
    raw_owner_keys = payload.get("owner_keys") or []
    if not isinstance(raw_report_ids, list) or not isinstance(raw_owner_keys, list):
        raise CommunityModerationDigestError("moderation_private_snapshot_invalid")
    if len(raw_report_ids) > MAX_REPORTS_PER_GROUP or len(
        raw_owner_keys
    ) > MAX_REPORTS_PER_GROUP:
        raise CommunityModerationDigestError(
            "moderation_private_snapshot_capacity_exceeded"
        )
    if any(not isinstance(value, str) for value in raw_report_ids) or any(
        not isinstance(value, str) for value in raw_owner_keys
    ):
        raise CommunityModerationDigestError("moderation_private_snapshot_invalid")

    report_ids = {str(value) for value in raw_report_ids if str(value)}
    owner_keys = {str(value) for value in raw_owner_keys if str(value)}
    reasons = dict(sorted(Counter(reason_values).items()))
    group_reference = moderation_group_reference(group_id)
    return {
        # ``group_id`` exists only in process memory and is removed before
        # state or logs are built.
        "group_id": group_id,
        "group_ref": group_reference,
        "flag_count": flag_count,
        "report_count": len(report_ids),
        "source_count": len(owner_keys),
        "reasons": reasons,
        "expires_at": _utc_datetime(expires_at).isoformat(),
        "fingerprint": _fingerprint(group_id, flag_count, reasons),
    }


def collect_actionable_groups(
    db: Any,
    *,
    now: float,
    transaction: Any | None = None,
) -> list[dict[str, Any]]:
    """Read a complete bounded active set or fail without changing state."""

    query = (
        db.collection(MODERATION_COLLECTION)
        .where(
            filter=_field_filter(
                "expires_at_timestamp",
                ">",
                _utc_datetime(now),
            )
        )
        .limit(MAX_ACTIONABLE_GROUPS + 1)
    )
    snapshots = list(
        query.stream(transaction=transaction)
        if transaction is not None
        else query.stream()
    )
    if len(snapshots) > MAX_ACTIONABLE_GROUPS:
        raise CommunityModerationDigestError(
            "moderation_digest_capacity_exceeded"
        )

    groups = []
    seen_references: set[str] = set()
    for snapshot in snapshots:
        group = _sanitize_actionable_group(
            dict(snapshot.to_dict() or {}),
            now=now,
        )
        if group is None:
            continue
        if group["group_ref"] in seen_references:
            raise CommunityModerationDigestError(
                "moderation_group_reference_collision"
            )
        seen_references.add(group["group_ref"])
        groups.append(group)
    return sorted(groups, key=lambda item: item["group_id"])


def _active_seen(groups: list[dict[str, Any]]) -> dict[str, str]:
    return {
        str(group["group_ref"]): str(group["fingerprint"])
        for group in groups
    }


def _active_flag_counts(groups: list[dict[str, Any]]) -> dict[str, int]:
    return {
        str(group["group_ref"]): int(group["flag_count"])
        for group in groups
    }


def _validated_seen(value: Any) -> dict[str, str]:
    if value is None:
        return {}
    if not isinstance(value, dict) or len(value) > MAX_ACTIONABLE_GROUPS:
        raise CommunityModerationDigestError("digest_state_seen_invalid")
    normalized: dict[str, str] = {}
    for key, fingerprint in value.items():
        reference = str(key or "")
        selected_fingerprint = str(fingerprint or "")
        if (
            GROUP_REFERENCE_PATTERN.fullmatch(reference) is None
            or FINGERPRINT_PATTERN.fullmatch(selected_fingerprint) is None
        ):
            raise CommunityModerationDigestError("digest_state_seen_invalid")
        normalized[reference] = selected_fingerprint
    return normalized


def _validated_flag_counts(value: Any) -> dict[str, int]:
    if value is None:
        return {}
    if not isinstance(value, dict) or len(value) > MAX_ACTIONABLE_GROUPS:
        raise CommunityModerationDigestError("digest_state_flag_counts_invalid")
    normalized: dict[str, int] = {}
    for key, raw_count in value.items():
        reference = str(key or "")
        if GROUP_REFERENCE_PATTERN.fullmatch(reference) is None:
            raise CommunityModerationDigestError(
                "digest_state_flag_counts_invalid"
            )
        if isinstance(raw_count, bool):
            raise CommunityModerationDigestError(
                "digest_state_flag_counts_invalid"
            )
        try:
            count = int(raw_count)
        except (TypeError, ValueError) as error:
            raise CommunityModerationDigestError(
                "digest_state_flag_counts_invalid"
            ) from error
        if count < 0 or count > MAX_FLAGS_PER_GROUP:
            raise CommunityModerationDigestError(
                "digest_state_flag_counts_invalid"
            )
        normalized[reference] = count
    return normalized


def _public_group(group: dict[str, Any]) -> dict[str, Any]:
    return {
        "group_ref": str(group["group_ref"]),
        "flag_count": int(group["flag_count"]),
        "report_count": int(group["report_count"]),
        "source_count": int(group["source_count"]),
        "reasons": dict(group["reasons"]),
        "expires_at": str(group["expires_at"]),
    }


def _validated_count(
    value: Any,
    *,
    maximum: int,
    error_code: str,
) -> int:
    if isinstance(value, bool):
        raise CommunityModerationDigestError(error_code)
    try:
        count = int(value)
    except (TypeError, ValueError) as error:
        raise CommunityModerationDigestError(error_code) from error
    if count < 0 or count > maximum:
        raise CommunityModerationDigestError(error_code)
    return count


def _validated_pending_group(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != {
        "group_ref",
        "flag_count",
        "report_count",
        "source_count",
        "reasons",
        "expires_at",
    }:
        raise CommunityModerationDigestError("digest_pending_group_invalid")
    reference = str(value.get("group_ref") or "")
    if GROUP_REFERENCE_PATTERN.fullmatch(reference) is None:
        raise CommunityModerationDigestError("digest_pending_group_invalid")
    flag_count = _validated_count(
        value.get("flag_count"),
        maximum=MAX_FLAGS_PER_GROUP,
        error_code="digest_pending_group_invalid",
    )
    report_count = _validated_count(
        value.get("report_count"),
        maximum=MAX_REPORTS_PER_GROUP,
        error_code="digest_pending_group_invalid",
    )
    source_count = _validated_count(
        value.get("source_count"),
        maximum=MAX_REPORTS_PER_GROUP,
        error_code="digest_pending_group_invalid",
    )
    reasons = value.get("reasons")
    if not isinstance(reasons, dict) or any(
        str(reason) not in ALLOWED_REASONS for reason in reasons
    ):
        raise CommunityModerationDigestError("digest_pending_group_invalid")
    normalized_reasons = {
        str(reason): _validated_count(
            count,
            maximum=MAX_FLAGS_PER_GROUP,
            error_code="digest_pending_group_invalid",
        )
        for reason, count in reasons.items()
    }
    if sum(normalized_reasons.values()) != flag_count:
        raise CommunityModerationDigestError("digest_pending_group_invalid")
    try:
        expires_at = datetime.fromisoformat(str(value.get("expires_at") or ""))
        if expires_at.tzinfo is None:
            raise ValueError("timezone_missing")
        normalized_expiry = expires_at.astimezone(timezone.utc).isoformat()
    except (TypeError, ValueError) as error:
        raise CommunityModerationDigestError(
            "digest_pending_group_invalid"
        ) from error
    return {
        "group_ref": reference,
        "flag_count": flag_count,
        "report_count": report_count,
        "source_count": source_count,
        "reasons": dict(sorted(normalized_reasons.items())),
        "expires_at": normalized_expiry,
    }


def _validated_pending(value: Any) -> dict[str, Any] | None:
    if value is None:
        return None
    if not isinstance(value, dict) or set(value) != {
        "schema_version",
        "digest_id",
        "delivery_slot",
        "created_at_timestamp",
        "new_group_count",
        "new_flag_count",
        "groups",
        "seen",
        "flag_counts",
    }:
        raise CommunityModerationDigestError("digest_pending_state_invalid")
    if value.get("schema_version") != 1:
        raise CommunityModerationDigestError("digest_pending_state_invalid")
    digest_id = str(value.get("digest_id") or "")
    if DIGEST_ID_PATTERN.fullmatch(digest_id) is None:
        raise CommunityModerationDigestError("digest_pending_state_invalid")
    delivery_slot = _validated_delivery_slot(value.get("delivery_slot"))
    created_at = _timestamp(value.get("created_at_timestamp"))
    if created_at <= 0:
        raise CommunityModerationDigestError("digest_pending_state_invalid")
    raw_groups = value.get("groups")
    if not isinstance(raw_groups, list) or len(raw_groups) > MAX_ACTIONABLE_GROUPS:
        raise CommunityModerationDigestError("digest_pending_state_invalid")
    groups = [_validated_pending_group(group) for group in raw_groups]
    if len({group["group_ref"] for group in groups}) != len(groups):
        raise CommunityModerationDigestError("digest_pending_state_invalid")
    new_group_count = _validated_count(
        value.get("new_group_count"),
        maximum=MAX_ACTIONABLE_GROUPS,
        error_code="digest_pending_state_invalid",
    )
    new_flag_count = _validated_count(
        value.get("new_flag_count"),
        maximum=MAX_ACTIONABLE_GROUPS * MAX_FLAGS_PER_GROUP,
        error_code="digest_pending_state_invalid",
    )
    if new_group_count != len(groups):
        raise CommunityModerationDigestError("digest_pending_state_invalid")
    seen = _validated_seen(value.get("seen"))
    flag_counts = _validated_flag_counts(value.get("flag_counts"))
    if set(seen) != set(flag_counts):
        raise CommunityModerationDigestError("digest_pending_state_invalid")
    return {
        "schema_version": 1,
        "digest_id": digest_id,
        "delivery_slot": delivery_slot,
        "created_at_timestamp": _utc_datetime(created_at),
        "new_group_count": new_group_count,
        "new_flag_count": new_flag_count,
        "groups": groups,
        "seen": seen,
        "flag_counts": flag_counts,
    }


def _state_snapshot(
    document: Any,
    *,
    transaction: Any | None = None,
) -> tuple[bool, dict[str, Any]]:
    snapshot = (
        document.get(transaction=transaction)
        if transaction is not None
        else document.get()
    )
    return (
        bool(snapshot.exists),
        dict(snapshot.to_dict() or {}) if snapshot.exists else {},
    )


def _validate_state_owner(
    state: dict[str, Any],
    selected_owner_marker: str | None,
    *,
    state_exists: bool,
) -> None:
    if selected_owner_marker is None or not state_exists:
        return
    existing_marker = state.get(DIGEST_STATE_OWNER_MARKER_FIELD)
    if existing_marker != selected_owner_marker:
        raise CommunityModerationDigestError("digest_state_owner_mismatch")


def _active_state(state: dict[str, Any], *, now: float) -> dict[str, Any]:
    if not state:
        return {}
    expires_at = state.get("expires_at_timestamp")
    if not isinstance(expires_at, datetime):
        raise CommunityModerationDigestError("digest_state_expiry_invalid")
    if expires_at.timestamp() <= now:
        return {}
    return state


def _pending_is_current(pending: dict[str, Any], *, now: float) -> bool:
    created_at = _timestamp(pending.get("created_at_timestamp"))
    if created_at <= 0 or now - created_at >= DIGEST_PENDING_MAX_AGE_SECONDS:
        return False
    return bool(pending.get("groups")) and all(
        _timestamp(group.get("expires_at")) > now
        for group in pending["groups"]
    )


def _last_delivery(state: dict[str, Any]) -> tuple[str | None, float]:
    explicit_slot = state.get("last_delivered_slot")
    delivered_at = _timestamp(state.get("last_delivered_at_timestamp"))
    if explicit_slot is not None:
        return _validated_delivery_slot(explicit_slot), delivered_at

    # Read-only migration support for a pre-outbox state. Its emitted timestamp
    # represented an already delivered transition.
    legacy_emitted_at = _timestamp(state.get("last_emitted_at_timestamp"))
    if legacy_emitted_at > 0:
        return delivery_slot_for_timestamp(legacy_emitted_at), legacy_emitted_at
    return None, 0


def _evaluate(
    state: dict[str, Any],
    groups: list[dict[str, Any]],
    *,
    now: float,
) -> dict[str, Any]:
    seen = _validated_seen(state.get("seen"))
    seen_flag_counts = _validated_flag_counts(state.get("flag_counts"))
    new_groups = [
        group
        for group in groups
        if seen.get(str(group["group_ref"])) != str(group["fingerprint"])
    ]
    delivery_slot = delivery_slot_for_timestamp(now)
    last_delivered_slot, last_delivered_at = _last_delivery(state)
    if not new_groups:
        status = "no_new_actionable_flags"
    elif last_delivered_slot == delivery_slot:
        status = "throttled"
    else:
        status = "ready"

    public_groups = [_public_group(group) for group in new_groups]
    new_flag_count = sum(
        max(
            0,
            int(group["flag_count"])
            - seen_flag_counts.get(str(group["group_ref"]), 0),
        )
        for group in public_groups
    )
    return {
        "status": status,
        "should_emit": status == "ready",
        "delivery_slot": delivery_slot,
        "new_group_count": len(public_groups),
        "new_flag_count": new_flag_count,
        "groups": public_groups,
        "last_delivered_slot": last_delivered_slot,
        "last_delivered_at": (
            _utc_datetime(last_delivered_at).isoformat()
            if last_delivered_at > 0
            else None
        ),
        "throttle_reason": (
            "delivery_slot_acknowledged" if status == "throttled" else None
        ),
        "seen": _active_seen(groups),
        "flag_counts": _active_flag_counts(groups),
    }


def _digest_id(evaluation: dict[str, Any]) -> str:
    basis = json.dumps(
        {
            "schema_version": 1,
            "delivery_slot": evaluation["delivery_slot"],
            "groups": evaluation["groups"],
            "seen": evaluation["seen"],
            "flag_counts": evaluation["flag_counts"],
        },
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(basis.encode("utf-8")).hexdigest()


def _new_pending(
    evaluation: dict[str, Any],
    *,
    now: float,
) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "digest_id": _digest_id(evaluation),
        "delivery_slot": str(evaluation["delivery_slot"]),
        "created_at_timestamp": _utc_datetime(now),
        "new_group_count": int(evaluation["new_group_count"]),
        "new_flag_count": int(evaluation["new_flag_count"]),
        "groups": [dict(group) for group in evaluation["groups"]],
        "seen": dict(evaluation["seen"]),
        "flag_counts": dict(evaluation["flag_counts"]),
    }


def _pending_result(
    pending: dict[str, Any],
    *,
    created: bool,
    state: dict[str, Any],
) -> dict[str, Any]:
    last_delivered_slot, last_delivered_at = _last_delivery(state)
    return {
        "status": "ready",
        "should_emit": True,
        "digest_id": str(pending["digest_id"]),
        "created_at": _utc_datetime(
            _timestamp(pending["created_at_timestamp"])
        ).isoformat(),
        "delivery_slot": str(pending["delivery_slot"]),
        "new_group_count": int(pending["new_group_count"]),
        "new_flag_count": int(pending["new_flag_count"]),
        "groups": [dict(group) for group in pending["groups"]],
        "last_delivered_slot": last_delivered_slot,
        "last_delivered_at": (
            _utc_datetime(last_delivered_at).isoformat()
            if last_delivered_at > 0
            else None
        ),
        "throttle_reason": None,
        "pending_created": created,
        "pending_reused": not created,
        "applied": created,
    }


def _pending_state_payload(
    state: dict[str, Any],
    pending: dict[str, Any],
    *,
    now: float,
    state_owner_marker: str | None,
) -> dict[str, Any]:
    last_delivered_slot, last_delivered_at = _last_delivery(state)
    payload: dict[str, Any] = {
        "seen": _validated_seen(state.get("seen")),
        "flag_counts": _validated_flag_counts(state.get("flag_counts")),
        DIGEST_PENDING_FIELD: pending,
        "updated_at_timestamp": _utc_datetime(now),
        "expires_at_timestamp": _utc_datetime(
            now + DIGEST_STATE_RETENTION_SECONDS
        ),
    }
    last_digest_id = str(state.get("last_digest_id") or "")
    if DIGEST_ID_PATTERN.fullmatch(last_digest_id) is not None:
        payload["last_digest_id"] = last_digest_id
    if last_delivered_slot is not None:
        payload["last_delivered_slot"] = last_delivered_slot
    if last_delivered_at > 0:
        payload["last_delivered_at_timestamp"] = _utc_datetime(last_delivered_at)
    existing_marker = state.get(DIGEST_STATE_OWNER_MARKER_FIELD)
    if state_owner_marker is not None:
        payload[DIGEST_STATE_OWNER_MARKER_FIELD] = state_owner_marker
    elif existing_marker is not None:
        payload[DIGEST_STATE_OWNER_MARKER_FIELD] = existing_marker
    return payload


def _acknowledged_state_payload(
    state: dict[str, Any],
    pending: dict[str, Any],
    *,
    now: float,
    acknowledged_slot: str,
    state_owner_marker: str | None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "last_digest_id": str(pending["digest_id"]),
        # A delayed pending item consumes the slot in which it is actually
        # accepted, preventing old-PM + new-AM + new-PM from producing three
        # deliveries on one local day.
        "last_delivered_slot": acknowledged_slot,
        "last_delivered_at_timestamp": _utc_datetime(now),
        "seen": dict(pending["seen"]),
        "flag_counts": dict(pending["flag_counts"]),
        "updated_at_timestamp": _utc_datetime(now),
        "expires_at_timestamp": _utc_datetime(
            now + DIGEST_STATE_RETENTION_SECONDS
        ),
    }
    existing_marker = state.get(DIGEST_STATE_OWNER_MARKER_FIELD)
    if state_owner_marker is not None:
        payload[DIGEST_STATE_OWNER_MARKER_FIELD] = state_owner_marker
    elif existing_marker is not None:
        payload[DIGEST_STATE_OWNER_MARKER_FIELD] = existing_marker
    return payload


def _validated_state_selection(
    state_document_id: str,
    state_owner_marker: str | None,
) -> tuple[str, str | None]:
    selected_state_document_id = str(state_document_id or "").strip()
    if (
        not selected_state_document_id
        or "/" in selected_state_document_id
        or len(selected_state_document_id) > 500
    ):
        raise CommunityModerationDigestError("digest_state_document_id_invalid")
    selected_owner_marker = (
        str(state_owner_marker).strip()
        if state_owner_marker is not None
        else None
    )
    if selected_owner_marker is not None and (
        not selected_owner_marker or len(selected_owner_marker) > 256
    ):
        raise CommunityModerationDigestError(
            "digest_state_owner_marker_invalid"
        )
    return selected_state_document_id, selected_owner_marker


def produce_moderation_digest(
    db: Any,
    *,
    now: float,
    apply: bool,
    transactional_decorator: (
        Callable[[Callable[..., Any]], Callable[..., Any]] | None
    ) = None,
    state_document_id: str = DIGEST_STATE_DOCUMENT,
    state_owner_marker: str | None = None,
) -> dict[str, Any]:
    """Preview or transactionally create/reuse one sanitized pending digest.

    ``state_document_id`` and ``state_owner_marker`` retain the isolated live
    smoke API. A current pending digest wins over newly collected source state,
    so a retry returns the same payload and ``digest_id`` until acknowledgement.
    Retry is limited to less than 24 hours and to groups that are still active;
    the surrounding technical state remains TTL-bounded to 48 hours.
    """

    require_digest_project(db)
    selected_document_id, selected_owner_marker = _validated_state_selection(
        state_document_id,
        state_owner_marker,
    )
    state_document = db.collection(DIGEST_STATE_COLLECTION).document(
        selected_document_id
    )

    if not apply:
        state_exists, state = _state_snapshot(state_document)
        _validate_state_owner(
            state,
            selected_owner_marker,
            state_exists=state_exists,
        )
        state = _active_state(state, now=now)
        pending = _validated_pending(state.get(DIGEST_PENDING_FIELD))
        if pending is not None and _pending_is_current(pending, now=now):
            return _pending_result(pending, created=False, state=state)
        if pending is not None:
            state = dict(state)
            state.pop(DIGEST_PENDING_FIELD, None)
        evaluation = _evaluate(
            state,
            collect_actionable_groups(db, now=now),
            now=now,
        )
        if evaluation["should_emit"]:
            evaluation["digest_id"] = _digest_id(evaluation)
        evaluation.pop("seen", None)
        evaluation.pop("flag_counts", None)
        return {
            **evaluation,
            "pending_created": False,
            "pending_reused": False,
            "applied": False,
        }

    if transactional_decorator is None:
        from google.cloud import firestore

        transactional_decorator = firestore.transactional
    transaction = db.transaction()

    def claim(transaction_in_progress: Any) -> dict[str, Any]:
        state_exists, raw_state = _state_snapshot(
            state_document,
            transaction=transaction_in_progress,
        )
        _validate_state_owner(
            raw_state,
            selected_owner_marker,
            state_exists=state_exists,
        )
        state = _active_state(raw_state, now=now)
        pending = _validated_pending(state.get(DIGEST_PENDING_FIELD))
        if pending is not None and _pending_is_current(pending, now=now):
            return _pending_result(pending, created=False, state=state)
        stale_pending = pending is not None
        if stale_pending:
            state = dict(state)
            state.pop(DIGEST_PENDING_FIELD, None)

        # New or corrupt source records cannot prevent retrying an already
        # claimed item because this query occurs only when no pending exists.
        groups = collect_actionable_groups(
            db,
            now=now,
            transaction=transaction_in_progress,
        )
        evaluation = _evaluate(state, groups, now=now)
        if not evaluation["should_emit"]:
            if stale_pending:
                clean_payload = _pending_state_payload(
                    state,
                    {},
                    now=now,
                    state_owner_marker=selected_owner_marker,
                )
                clean_payload.pop(DIGEST_PENDING_FIELD, None)
                transaction_in_progress.set(
                    state_document,
                    clean_payload,
                    merge=False,
                )
            evaluation.pop("seen", None)
            evaluation.pop("flag_counts", None)
            return {
                **evaluation,
                "pending_created": False,
                "pending_reused": False,
                "applied": False,
            }

        pending = _new_pending(evaluation, now=now)
        transaction_in_progress.set(
            state_document,
            _pending_state_payload(
                state,
                pending,
                now=now,
                state_owner_marker=selected_owner_marker,
            ),
            merge=False,
        )
        return _pending_result(pending, created=True, state=state)

    return transactional_decorator(claim)(transaction)


def acknowledge_moderation_digest(
    db: Any,
    *,
    digest_id: str,
    now: float,
    transactional_decorator: (
        Callable[[Callable[..., Any]], Callable[..., Any]] | None
    ) = None,
    state_document_id: str = DIGEST_STATE_DOCUMENT,
    state_owner_marker: str | None = None,
) -> dict[str, Any]:
    """Promote a pending digest after synchronous Logging API acceptance."""

    require_digest_project(db)
    selected_digest_id = str(digest_id or "").strip()
    if DIGEST_ID_PATTERN.fullmatch(selected_digest_id) is None:
        raise CommunityModerationDigestError("digest_ack_id_invalid")
    selected_document_id, selected_owner_marker = _validated_state_selection(
        state_document_id,
        state_owner_marker,
    )
    state_document = db.collection(DIGEST_STATE_COLLECTION).document(
        selected_document_id
    )
    if transactional_decorator is None:
        from google.cloud import firestore

        transactional_decorator = firestore.transactional
    transaction = db.transaction()

    def acknowledge(transaction_in_progress: Any) -> dict[str, Any]:
        state_exists, raw_state = _state_snapshot(
            state_document,
            transaction=transaction_in_progress,
        )
        _validate_state_owner(
            raw_state,
            selected_owner_marker,
            state_exists=state_exists,
        )
        state = _active_state(raw_state, now=now)
        if str(state.get("last_digest_id") or "") == selected_digest_id:
            last_slot, _last_at = _last_delivery(state)
            return {
                "status": "already_acknowledged",
                "acknowledged": False,
                "digest_id": selected_digest_id,
                "delivery_slot": last_slot,
            }

        pending = _validated_pending(state.get(DIGEST_PENDING_FIELD))
        if pending is None:
            raise CommunityModerationDigestError("digest_ack_pending_missing")
        if str(pending["digest_id"]) != selected_digest_id:
            raise CommunityModerationDigestError("digest_ack_id_mismatch")

        transaction_in_progress.set(
            state_document,
            _acknowledged_state_payload(
                state,
                pending,
                now=now,
                acknowledged_slot=delivery_slot_for_timestamp(now),
                state_owner_marker=selected_owner_marker,
            ),
            merge=False,
        )
        return {
            "status": "acknowledged",
            "acknowledged": True,
            "digest_id": selected_digest_id,
            "delivery_slot": delivery_slot_for_timestamp(now),
        }

    return transactional_decorator(acknowledge)(transaction)
