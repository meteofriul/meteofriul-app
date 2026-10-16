from __future__ import annotations

import hashlib
from copy import deepcopy
from datetime import datetime, timezone
from threading import RLock
from typing import Any, Callable


REPORTS_COLLECTION = "community_reports"
COOLDOWNS_COLLECTION = "community_report_cooldowns"
CONFIRMATIONS_COLLECTION = "community_report_confirmations"
FLAGS_COLLECTION = "community_report_flags"
MODERATION_COLLECTION = "community_report_moderation"
SOURCE_BLOCKS_COLLECTION = "community_source_blocks"
RATE_LIMITS_COLLECTION = "community_report_rate_limits"
REPUTATION_COLLECTION = "community_reputation"
REPUTATION_AWARDS_COLLECTION = "community_reputation_awards"
REPUTATION_RETENTION_SECONDS = 365 * 24 * 60 * 60
MAX_REPORTS = 200
GROUP_LOOKUP_LIMIT = MAX_REPORTS + 1
DENIAL_WITHDRAWAL_THRESHOLD = 3


class CommunityRepositoryUnavailable(RuntimeError):
    """Raised when strict Firestore persistence cannot be read or mutated."""


class CommunityCooldownActive(RuntimeError):
    def __init__(self, cooldown_until: float) -> None:
        super().__init__("community_report_cooldown_active")
        self.cooldown_until = float(cooldown_until)


class CommunityConfirmationCapacityReached(RuntimeError):
    pass


class CommunityFlagCapacityReached(RuntimeError):
    pass


class CommunityMutationTargetUnavailable(RuntimeError):
    """Raised when a strict mutation loses its active report target."""


class CommunitySelfConfirmationNotAllowed(RuntimeError):
    pass


class CommunityGroupHidden(RuntimeError):
    pass


class CommunitySourceBlocked(RuntimeError):
    def __init__(self, blocked_until: float) -> None:
        super().__init__("community_source_temporarily_blocked")
        self.blocked_until = float(blocked_until)


def _timestamp(value: Any, fallback: float = 0) -> float:
    if isinstance(value, datetime):
        return value.timestamp()
    try:
        return float(value)
    except (TypeError, ValueError):
        pass
    if isinstance(value, str) and value:
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
        except ValueError:
            return fallback
    return fallback


def _datetime(value: float) -> datetime:
    return datetime.fromtimestamp(float(value), timezone.utc)


def _field_filter(field: str, operator: str, value: Any) -> Any:
    try:
        from google.cloud.firestore_v1.base_query import FieldFilter

        return FieldFilter(field, operator, value)
    except ModuleNotFoundError:
        # Keeps the repository's dependency-free memory/fake test adapters
        # usable; real Firestore mode still obtains the SDK through _db().
        return type("FieldFilter", (), {
            "field_path": field,
            "op_string": operator,
            "value": value,
        })()


def _confirmation_document_id(group_id: str) -> str:
    return hashlib.sha256(group_id.encode("utf-8")).hexdigest()


def _flag_document_id(group_id: str, client_key: str) -> str:
    return hashlib.sha256(f"{group_id}:{client_key}".encode("utf-8")).hexdigest()


def _source_block_document_id(owner_key: str) -> str:
    return hashlib.sha256(owner_key.encode("utf-8")).hexdigest()


def _reputation_document_id(owner_key: str) -> str:
    return hashlib.sha256(f"community-reputation-v1:{owner_key}".encode("utf-8")).hexdigest()


def _reputation_episode_key(group_id: str) -> str:
    """Stable private episode reference without retaining the public group id."""

    return hashlib.sha256(f"community-episode-v1:{group_id}".encode("utf-8")).hexdigest()


def _reputation_award_document_id(group_id: str, owner_key: str) -> str:
    return hashlib.sha256(
        f"community-award-v1:{group_id}:{owner_key}".encode("utf-8")
    ).hexdigest()


def _reputation_summary(
    payload: dict[str, Any] | None,
    *,
    owner_key: str,
    award_day: str,
) -> dict[str, Any]:
    summary = dict(payload or {})
    stored_day = str(summary.get("daily_award_day") or "")
    return {
        "owner_key": owner_key,
        "points": max(0, int(summary.get("points", 0))),
        "total_reports": max(0, int(summary.get("total_reports", 0))),
        "validated_reports": max(0, int(summary.get("validated_reports", 0))),
        "revoked_reports": max(0, int(summary.get("revoked_reports", 0))),
        "daily_award_day": award_day,
        "daily_awards": (
            max(0, int(summary.get("daily_awards", 0)))
            if stored_day == award_day
            else 0
        ),
    }


def _reputation_award_payload(
    *,
    group_id: str,
    owner_key: str,
    status: str,
    reason: str,
    award_day: str,
    now: float,
) -> dict[str, Any]:
    return {
        "episode_key": _reputation_episode_key(group_id),
        "owner_key": owner_key,
        "status": status,
        "points_delta": 1 if status == "awarded" else 0,
        "validation_reason": reason,
        "award_day": award_day,
        "created_at_timestamp": _datetime(now),
        "updated_at": _datetime(now),
        "expires_at_timestamp": _datetime(now + REPUTATION_RETENTION_SECONDS),
    }


def normalize_stored_report(data: dict[str, Any], doc_id: str = "") -> dict[str, Any]:
    report = deepcopy(dict(data or {}))
    created_at = _timestamp(
        report.get("created_at"),
        _timestamp(report.get("created_at_timestamp"), 0),
    )
    expires_at = _timestamp(
        report.get("expires_at"),
        _timestamp(report.get("expires_at_timestamp"), created_at + 3600),
    )
    report.update({
        "id": str(report.get("id") or doc_id),
        "created_at": created_at,
        "expires_at": expires_at,
    })
    return report


def _report_payload(report: dict[str, Any]) -> dict[str, Any]:
    payload = deepcopy(dict(report))
    payload["created_at_timestamp"] = _datetime(report["created_at"])
    payload["expires_at_timestamp"] = _datetime(report["expires_at"])
    return payload


def _cooldown_payload(
    client_key: str,
    cooldown_until: float,
    *,
    report_id: str = "",
) -> dict[str, Any]:
    payload = {
        "client_key": client_key,
        "cooldown_until": cooldown_until,
        "expires_at_timestamp": _datetime(cooldown_until),
        "updated_at": datetime.now(timezone.utc),
    }
    if report_id:
        payload["report_id"] = report_id
    return payload


def _read_transaction_group_targets(
    db: Any,
    transaction: Any,
    *,
    group_id: str,
    report_ids: list[str],
    now: float,
) -> tuple[list[tuple[Any, dict[str, Any]]], list[str]]:
    targets: list[tuple[Any, dict[str, Any]]] = []
    unavailable_ids: list[str] = []
    for report_id in dict.fromkeys(
        str(value) for value in report_ids if str(value)
    ):
        document = db.collection(REPORTS_COLLECTION).document(report_id)
        snapshot = document.get(transaction=transaction)
        if not snapshot.exists:
            unavailable_ids.append(report_id)
            continue
        report = normalize_stored_report(snapshot.to_dict() or {}, report_id)
        if (
            str(report.get("group_id") or "") != group_id
            or float(report.get("expires_at") or 0) <= now
        ):
            unavailable_ids.append(report_id)
            continue
        targets.append((document, report))
    return targets, unavailable_ids


def _confirmation_payload(
    group_id: str,
    state: dict[str, Any],
    expires_at: float,
) -> dict[str, Any]:
    denial_count = max(0, int(state.get("no", 0)))
    report_ids = list(dict.fromkeys(
        str(value)
        for value in (state.get("report_ids") or [])
        if str(value)
    ))
    map_withdrawn = bool(
        state.get("map_withdrawn", False)
        or denial_count >= DENIAL_WITHDRAWAL_THRESHOLD
    )
    report_sources = {
        str(report_id): str(owner_key)
        for report_id, owner_key in dict(state.get("report_sources") or {}).items()
        if str(report_id) and str(owner_key)
    }
    validity_status = str(state.get("validity_status") or "unverified")
    if validity_status not in {"unverified", "verified", "rejected", "excluded"}:
        validity_status = "unverified"
    temporal_status = str(state.get("temporal_status") or "active")
    if temporal_status not in {"active", "ceased"}:
        temporal_status = "active"
    return {
        "group_id": group_id,
        "yes": max(0, int(state.get("yes", 0))),
        "no": denial_count,
        "votes": dict(state.get("votes") or {}),
        "report_ids": report_ids,
        "report_sources": report_sources,
        "validity_status": validity_status,
        "verified_at": state.get("verified_at"),
        "closed_unverified": bool(state.get("closed_unverified", False)),
        "temporal_status": temporal_status,
        "map_withdrawn": map_withdrawn,
        "map_withdrawn_at": state.get("map_withdrawn_at"),
        "updated_at": datetime.now(timezone.utc),
        "expires_at_timestamp": _datetime(expires_at),
    }


def _apply_group_validation_state(
    state: dict[str, Any],
    reports: list[dict[str, Any]],
    *,
    now: float,
    report_added: bool = False,
) -> tuple[dict[str, Any], list[str], str]:
    """Derive validity independently from the episode's temporal state."""

    updated = dict(state)
    report_ids = list(dict.fromkeys(
        str(report.get("id") or "")
        for report in reports
        if str(report.get("id") or "")
    ))
    report_sources = {
        str(report.get("id") or ""): str(report.get("owner_key") or "")
        for report in reports
        if str(report.get("id") or "") and str(report.get("owner_key") or "")
    }
    updated["report_ids"] = report_ids
    updated["report_sources"] = report_sources
    owner_keys = list(dict.fromkeys(
        owner_key for owner_key in report_sources.values() if owner_key
    ))
    type_id = str((reports[0] if reports else {}).get("type_id") or "").lower()

    existing_validity = str(updated.get("validity_status") or "unverified")
    closed_unverified = bool(updated.get("closed_unverified", False))
    if (
        max(0, int(updated.get("no", 0))) > 0
        and existing_validity != "verified"
        and max(0, int(updated.get("yes", 0))) == 0
        and len(owner_keys) < 2
    ):
        closed_unverified = True
    updated["closed_unverified"] = closed_unverified
    if type_id == "quiet":
        validity_status = "excluded"
    elif existing_validity == "rejected":
        validity_status = "rejected"
    elif closed_unverified:
        validity_status = "unverified"
    elif (
        existing_validity == "verified"
        or max(0, int(updated.get("yes", 0))) > 0
        or len(owner_keys) >= 2
    ):
        validity_status = "verified"
    else:
        validity_status = "unverified"
    updated["validity_status"] = validity_status
    if validity_status == "verified" and updated.get("verified_at") is None:
        updated["verified_at"] = _datetime(now)

    if report_added:
        updated["temporal_status"] = "active"
    elif max(0, int(updated.get("no", 0))) > 0:
        updated["temporal_status"] = "ceased"
    else:
        updated["temporal_status"] = str(
            updated.get("temporal_status") or "active"
        )

    reason = (
        "independent_report"
        if len(owner_keys) >= 2
        else "independent_confirmation"
    )
    return updated, owner_keys, reason


def _moderation_payload(
    group_id: str,
    state: dict[str, Any],
    expires_at: float,
) -> dict[str, Any]:
    flaggers = dict(state.get("flaggers") or {})
    report_ids = list(dict.fromkeys(
        str(value) for value in (state.get("report_ids") or []) if str(value)
    ))
    owner_keys = list(dict.fromkeys(
        str(value) for value in (state.get("owner_keys") or []) if str(value)
    ))
    report_sources = {
        str(report_id): str(owner_key)
        for report_id, owner_key in dict(state.get("report_sources") or {}).items()
        if str(report_id) and str(owner_key)
    }
    return {
        "group_id": group_id,
        "flag_count": len(flaggers),
        "flaggers": flaggers,
        "report_ids": report_ids,
        "owner_keys": owner_keys,
        "report_sources": report_sources,
        "hidden": bool(state.get("hidden", False)),
        "hidden_at": state.get("hidden_at"),
        "hidden_reason": str(state.get("hidden_reason") or ""),
        "updated_at": datetime.now(timezone.utc),
        "expires_at_timestamp": _datetime(expires_at),
    }


def _flag_payload(
    group_id: str,
    client_key: str,
    reason: str,
    *,
    report_ids: list[str],
    owner_keys: list[str],
    report_sources: dict[str, str],
    created_at: float,
    expires_at: float,
) -> dict[str, Any]:
    return {
        "group_id": group_id,
        "client_key": client_key,
        "reason": reason,
        "report_ids": list(dict.fromkeys(report_ids)),
        "owner_keys": list(dict.fromkeys(owner_keys)),
        "report_sources": dict(report_sources),
        "created_at_timestamp": _datetime(created_at),
        "expires_at_timestamp": _datetime(expires_at),
    }


class CommunityRepository:
    """Memory-first persistence with an optional Firestore mirror."""

    def __init__(
        self,
        firestore_provider: Callable[[], Any | None] | None = None,
        *,
        storage_mode: str = "memory",
        transactional_decorator: Callable[[Callable[..., Any]], Callable[..., Any]] | None = None,
    ) -> None:
        self._firestore_provider = firestore_provider or (lambda: None)
        self._transactional_decorator = transactional_decorator
        self.storage_mode = str(storage_mode or "memory").strip().lower()
        self._reports: dict[str, dict[str, Any]] = {}
        self._cooldowns: dict[str, float] = {}
        self._confirmations: dict[str, dict[str, Any]] = {}
        self._flags: dict[str, dict[str, Any]] = {}
        self._moderation: dict[str, dict[str, Any]] = {}
        self._source_blocks: dict[str, dict[str, Any]] = {}
        self._rate_limits: dict[str, dict[str, float | int]] = {}
        self._reputations: dict[str, dict[str, Any]] = {}
        self._reputation_awards: dict[str, dict[str, Any]] = {}
        self.lock = RLock()

    @property
    def requires_firestore(self) -> bool:
        # ``auto`` may resolve to the real Firestore client on Cloud Run.  It
        # must therefore keep the same fail-closed/transactional guarantees as
        # the explicit persistent mode instead of silently falling back to the
        # process-local store after a write failure.
        return self.storage_mode != "memory"

    def _db(self) -> Any | None:
        try:
            return self._firestore_provider()
        except Exception:
            return None

    def _required_db(self) -> Any:
        db = self._db()
        if db is None:
            raise CommunityRepositoryUnavailable("firestore_unavailable")
        return db

    def _run_transaction(self, operation: Callable[..., Any], transaction: Any) -> Any:
        decorator = self._transactional_decorator
        if decorator is None:
            from google.cloud import firestore

            decorator = firestore.transactional
        return decorator(operation)(transaction)

    @staticmethod
    def _prepare_reputation_awards_strict(
        db: Any,
        transaction: Any,
        *,
        group_id: str,
        owner_keys: list[str],
        award_day: str,
        daily_limit: int,
        reason: str,
        now: float,
    ) -> list[tuple[Any, dict[str, Any], Any, dict[str, Any]]]:
        plans: list[tuple[Any, dict[str, Any], Any, dict[str, Any]]] = []
        for owner_key in dict.fromkeys(
            str(value) for value in owner_keys if str(value)
        ):
            award_document = db.collection(REPUTATION_AWARDS_COLLECTION).document(
                _reputation_award_document_id(group_id, owner_key)
            )
            award_snapshot = award_document.get(transaction=transaction)
            if (
                award_snapshot.exists
                and _timestamp(
                    (award_snapshot.to_dict() or {}).get("expires_at_timestamp"),
                    0,
                )
                > now
            ):
                continue

            reputation_document = db.collection(REPUTATION_COLLECTION).document(
                _reputation_document_id(owner_key)
            )
            reputation_snapshot = reputation_document.get(transaction=transaction)
            stored_summary = (
                dict(reputation_snapshot.to_dict() or {})
                if reputation_snapshot.exists
                else {}
            )
            if _timestamp(stored_summary.get("expires_at_timestamp"), 0) <= now:
                stored_summary = {}
            summary = _reputation_summary(
                stored_summary,
                owner_key=owner_key,
                award_day=award_day,
            )
            can_award_point = int(summary["daily_awards"]) < daily_limit
            status = "awarded" if can_award_point else "capped"
            summary["validated_reports"] = int(summary["validated_reports"]) + 1
            if can_award_point:
                summary["points"] = int(summary["points"]) + 1
                summary["daily_awards"] = int(summary["daily_awards"]) + 1
            summary["updated_at"] = _datetime(now)
            summary["expires_at_timestamp"] = _datetime(
                now + REPUTATION_RETENTION_SECONDS
            )
            plans.append((
                award_document,
                _reputation_award_payload(
                    group_id=group_id,
                    owner_key=owner_key,
                    status=status,
                    reason=reason,
                    award_day=award_day,
                    now=now,
                ),
                reputation_document,
                summary,
            ))
        return plans

    @staticmethod
    def _prepare_report_submission_strict(
        db: Any,
        transaction: Any,
        *,
        owner_key: str,
        award_day: str,
        now: float,
    ) -> tuple[Any, dict[str, Any]]:
        """Increment the accepted-submission total in the private ledger."""

        reputation_document = db.collection(REPUTATION_COLLECTION).document(
            _reputation_document_id(owner_key)
        )
        reputation_snapshot = reputation_document.get(transaction=transaction)
        stored_summary = (
            dict(reputation_snapshot.to_dict() or {})
            if reputation_snapshot.exists
            else {}
        )
        if _timestamp(stored_summary.get("expires_at_timestamp"), 0) <= now:
            stored_summary = {}
        summary = _reputation_summary(
            stored_summary,
            owner_key=owner_key,
            award_day=award_day,
        )
        summary["total_reports"] = int(summary["total_reports"]) + 1
        summary["updated_at"] = _datetime(now)
        summary["expires_at_timestamp"] = _datetime(
            now + REPUTATION_RETENTION_SECONDS
        )
        return reputation_document, summary

    @staticmethod
    def _write_reputation_awards_strict(
        transaction: Any,
        plans: list[tuple[Any, dict[str, Any], Any, dict[str, Any]]],
    ) -> None:
        for award_document, award_payload, reputation_document, summary in plans:
            transaction.set(award_document, award_payload, merge=False)
            transaction.set(reputation_document, summary, merge=False)

    def _record_reputation_awards_memory(
        self,
        *,
        group_id: str,
        owner_keys: list[str],
        award_day: str,
        daily_limit: int,
        reason: str,
        now: float,
    ) -> None:
        for owner_key in dict.fromkeys(
            str(value) for value in owner_keys if str(value)
        ):
            award_id = _reputation_award_document_id(group_id, owner_key)
            existing_award = self._reputation_awards.get(award_id)
            if (
                existing_award
                and _timestamp(existing_award.get("expires_at_timestamp"), 0) > now
            ):
                continue
            self._reputation_awards.pop(award_id, None)
            reputation_id = _reputation_document_id(owner_key)
            stored_summary = dict(self._reputations.get(reputation_id) or {})
            if _timestamp(stored_summary.get("expires_at_timestamp"), 0) <= now:
                stored_summary = {}
            summary = _reputation_summary(
                stored_summary,
                owner_key=owner_key,
                award_day=award_day,
            )
            can_award_point = int(summary["daily_awards"]) < daily_limit
            status = "awarded" if can_award_point else "capped"
            summary["validated_reports"] = int(summary["validated_reports"]) + 1
            if can_award_point:
                summary["points"] = int(summary["points"]) + 1
                summary["daily_awards"] = int(summary["daily_awards"]) + 1
            summary["updated_at"] = _datetime(now)
            summary["expires_at_timestamp"] = _datetime(
                now + REPUTATION_RETENTION_SECONDS
            )
            self._reputations[reputation_id] = summary
            self._reputation_awards[award_id] = _reputation_award_payload(
                group_id=group_id,
                owner_key=owner_key,
                status=status,
                reason=reason,
                award_day=award_day,
                now=now,
            )

    def record_report_submission_memory(
        self,
        owner_key: str,
        *,
        award_day: str,
        now: float,
    ) -> None:
        """Count one accepted report independently from validation or points."""

        reputation_id = _reputation_document_id(owner_key)
        stored_summary = dict(self._reputations.get(reputation_id) or {})
        if _timestamp(stored_summary.get("expires_at_timestamp"), 0) <= now:
            stored_summary = {}
        summary = _reputation_summary(
            stored_summary,
            owner_key=owner_key,
            award_day=award_day,
        )
        summary["total_reports"] = int(summary["total_reports"]) + 1
        summary["updated_at"] = _datetime(now)
        summary["expires_at_timestamp"] = _datetime(
            now + REPUTATION_RETENTION_SECONDS
        )
        self._reputations[reputation_id] = summary

    def create_report_strict(
        self,
        report: dict[str, Any],
        *,
        client_key: str,
        cooldown_until: float,
        global_limit: int,
        global_window_seconds: int,
        now: float,
        reputation_award_day: str = "",
        reputation_daily_limit: int = 3,
    ) -> None:
        """Atomically enforce cooldown and persist a report in Firestore."""

        db = self._required_db()
        try:
            report_document = db.collection(REPORTS_COLLECTION).document(report["id"])
            cooldown_document = db.collection(COOLDOWNS_COLLECTION).document(client_key)
            source_block_document = db.collection(SOURCE_BLOCKS_COLLECTION).document(
                _source_block_document_id(client_key)
            )
            moderation_document = db.collection(MODERATION_COLLECTION).document(
                _confirmation_document_id(str(report.get("group_id") or ""))
            )
            confirmation_document = db.collection(CONFIRMATIONS_COLLECTION).document(
                _confirmation_document_id(str(report.get("group_id") or ""))
            )
            global_window = int(now // global_window_seconds)
            global_limit_document = db.collection(RATE_LIMITS_COLLECTION).document(
                f"global-create-{global_window}"
            )
            transaction = db.transaction()

            def persist(transaction_in_progress: Any) -> dict[str, Any]:
                block_snapshot = source_block_document.get(
                    transaction=transaction_in_progress
                )
                blocked_until = (
                    _timestamp((block_snapshot.to_dict() or {}).get("blocked_until"), 0)
                    if block_snapshot.exists
                    else 0
                )
                if blocked_until > now:
                    raise CommunitySourceBlocked(blocked_until)

                moderation_snapshot = moderation_document.get(
                    transaction=transaction_in_progress
                )
                moderation = (
                    dict(moderation_snapshot.to_dict() or {})
                    if moderation_snapshot.exists
                    else {}
                )
                if (
                    bool(moderation.get("hidden", False))
                    and _timestamp(moderation.get("expires_at_timestamp"), 0) > now
                ):
                    raise CommunityGroupHidden("community_group_hidden")

                confirmation_snapshot = confirmation_document.get(
                    transaction=transaction_in_progress
                )
                confirmation = (
                    dict(confirmation_snapshot.to_dict() or {})
                    if confirmation_snapshot.exists
                    else {}
                )
                if _timestamp(
                    confirmation.get("expires_at_timestamp"),
                    0,
                ) <= now:
                    confirmation = {}
                tracked_reports, _unavailable_ids = _read_transaction_group_targets(
                    db,
                    transaction_in_progress,
                    group_id=str(report.get("group_id") or ""),
                    report_ids=list(confirmation.get("report_ids") or []),
                    now=now,
                )
                active_reports = [
                    stored_report for _document, stored_report in tracked_reports
                ]
                active_reports.append(dict(report))
                confirmation, owner_keys, validation_reason = (
                    _apply_group_validation_state(
                        confirmation,
                        active_reports,
                        now=now,
                        report_added=True,
                    )
                )

                snapshot = cooldown_document.get(transaction=transaction_in_progress)
                active_until = (
                    _timestamp((snapshot.to_dict() or {}).get("cooldown_until"), 0)
                    if snapshot.exists
                    else 0
                )
                if active_until > now:
                    raise CommunityCooldownActive(active_until)

                global_snapshot = global_limit_document.get(
                    transaction=transaction_in_progress
                )
                global_state = (
                    dict(global_snapshot.to_dict() or {})
                    if global_snapshot.exists
                    else {}
                )
                global_count = max(0, int(global_state.get("count", 0)))
                if global_count >= global_limit:
                    retry_at = (global_window + 1) * global_window_seconds
                    raise CommunityCooldownActive(retry_at)

                submission_document, submission_summary = (
                    self._prepare_report_submission_strict(
                        db,
                        transaction_in_progress,
                        owner_key=str(report.get("owner_key") or ""),
                        award_day=(
                            reputation_award_day
                            or _datetime(now).date().isoformat()
                        ),
                        now=now,
                    )
                )
                award_plans = []
                if confirmation.get("validity_status") == "verified":
                    award_plans = self._prepare_reputation_awards_strict(
                        db,
                        transaction_in_progress,
                        group_id=str(report.get("group_id") or ""),
                        owner_keys=owner_keys,
                        award_day=(
                            reputation_award_day
                            or _datetime(now).date().isoformat()
                        ),
                        daily_limit=max(1, int(reputation_daily_limit)),
                        reason=validation_reason,
                        now=now,
                    )
                submission_merged_into_award = False
                for (
                    _award_document,
                    _award,
                    reputation_document,
                    summary,
                ) in award_plans:
                    if str(reputation_document.id) == str(submission_document.id):
                        summary["total_reports"] = submission_summary["total_reports"]
                        submission_merged_into_award = True

                report_payload = _report_payload(report)
                report_payload["confirmation_yes"] = max(
                    0,
                    int(confirmation.get("yes", 0)),
                )
                report_payload["confirmation_no"] = max(
                    0,
                    int(confirmation.get("no", 0)),
                )
                report_payload["denial_count"] = report_payload["confirmation_no"]
                report_payload["map_withdrawn"] = bool(
                    confirmation.get("map_withdrawn", False)
                    or report_payload["confirmation_no"]
                    >= DENIAL_WITHDRAWAL_THRESHOLD
                )
                report_payload["validity_status"] = str(
                    confirmation.get("validity_status") or "unverified"
                )
                report_payload["temporal_status"] = str(
                    confirmation.get("temporal_status") or "active"
                )
                confirmation_payload = _confirmation_payload(
                    str(report.get("group_id") or ""),
                    confirmation,
                    max(
                        float(report.get("expires_at") or now),
                        _timestamp(
                            confirmation.get("expires_at_timestamp"),
                            0,
                        ),
                    ),
                )
                transaction_in_progress.set(
                    confirmation_document,
                    confirmation_payload,
                    merge=True,
                )
                for existing_document, _existing_report in tracked_reports:
                    transaction_in_progress.update(
                        existing_document,
                        {
                            "validity_status": report_payload["validity_status"],
                            "temporal_status": report_payload["temporal_status"],
                        },
                    )
                transaction_in_progress.set(
                    report_document,
                    report_payload,
                    merge=True,
                )
                transaction_in_progress.set(
                    cooldown_document,
                    _cooldown_payload(
                        client_key,
                        cooldown_until,
                        report_id=str(report.get("id") or ""),
                    ),
                    merge=True,
                )
                transaction_in_progress.set(
                    global_limit_document,
                    {
                        "count": global_count + 1,
                        "expires_at_timestamp": _datetime(
                            (global_window + 2) * global_window_seconds
                        ),
                        "updated_at": datetime.now(timezone.utc),
                        "window": global_window,
                    },
                    merge=True,
                )
                if not submission_merged_into_award:
                    transaction_in_progress.set(
                        submission_document,
                        submission_summary,
                        merge=False,
                    )
                self._write_reputation_awards_strict(
                    transaction_in_progress,
                    award_plans,
                )
                return {
                    "confirmation": confirmation_payload,
                    "validity_status": report_payload["validity_status"],
                    "temporal_status": report_payload["temporal_status"],
                }

            result = self._run_transaction(persist, transaction)
        except (
            CommunityCooldownActive,
            CommunityGroupHidden,
            CommunitySourceBlocked,
        ):
            raise
        except Exception as error:
            raise CommunityRepositoryUnavailable(
                "firestore_create_transaction_failed"
            ) from error

        report["validity_status"] = str(result["validity_status"])
        report["temporal_status"] = str(result["temporal_status"])
        self._confirmations[str(report.get("group_id") or "")] = dict(
            result["confirmation"]
        )
        self._reports[report["id"]] = deepcopy(dict(report))
        self._cooldowns[client_key] = cooldown_until
        self._trim_memory()

    def flag_group_strict(
        self,
        group_id: str,
        *,
        report_ids: list[str],
        owner_keys: list[str],
        report_sources: dict[str, str],
        client_key: str,
        reason: str,
        expires_at: float,
        global_limit: int,
        global_window_seconds: int,
        client_limit: int,
        client_window_seconds: int,
        max_flaggers: int,
        now: float,
    ) -> dict[str, Any]:
        """Atomically store one idempotent flag and update group moderation."""

        db = self._required_db()
        try:
            moderation_document = db.collection(MODERATION_COLLECTION).document(
                _confirmation_document_id(group_id)
            )
            flag_id = _flag_document_id(group_id, client_key)
            flag_document = db.collection(FLAGS_COLLECTION).document(flag_id)
            global_window = int(now // global_window_seconds)
            client_window = int(now // client_window_seconds)
            global_limit_document = db.collection(RATE_LIMITS_COLLECTION).document(
                f"global-flag-{global_window}"
            )
            client_limit_document = db.collection(RATE_LIMITS_COLLECTION).document(
                f"client-flag-{client_key}-{client_window}"
            )
            transaction = db.transaction()

            def persist(transaction_in_progress: Any) -> dict[str, Any]:
                moderation_snapshot = moderation_document.get(
                    transaction=transaction_in_progress
                )
                moderation = (
                    dict(moderation_snapshot.to_dict() or {})
                    if moderation_snapshot.exists
                    else {}
                )
                if _timestamp(moderation.get("expires_at_timestamp"), 0) <= now:
                    moderation = {}
                durable_moderation = dict(moderation)
                targets, unavailable_ids = _read_transaction_group_targets(
                    db,
                    transaction_in_progress,
                    group_id=group_id,
                    report_ids=report_ids,
                    now=now,
                )
                moderation_hidden = bool(moderation.get("hidden", False))
                if (unavailable_ids or not targets) and not moderation_hidden:
                    raise CommunityMutationTargetUnavailable(
                        "community_report_not_active"
                    )
                active_report_ids = [
                    str(report.get("id") or "")
                    for _document, report in targets
                    if str(report.get("id") or "")
                ]
                active_report_sources = {
                    str(report.get("id") or ""): str(
                        report.get("owner_key")
                        or report_sources.get(str(report.get("id") or ""))
                        or ""
                    )
                    for _document, report in targets
                    if str(report.get("id") or "")
                    and str(
                        report.get("owner_key")
                        or report_sources.get(str(report.get("id") or ""))
                        or ""
                    )
                }
                active_owner_keys = list(dict.fromkeys(
                    active_report_sources.values()
                ))
                moderation.setdefault("flaggers", {})
                moderation["flaggers"] = dict(moderation.get("flaggers") or {})
                moderation["report_ids"] = list(dict.fromkeys([
                    *(moderation.get("report_ids") or []),
                    *active_report_ids,
                ]))
                moderation["owner_keys"] = list(dict.fromkeys([
                    *(moderation.get("owner_keys") or []),
                    *active_owner_keys,
                ]))
                moderation["report_sources"] = {
                    **dict(moderation.get("report_sources") or {}),
                    **active_report_sources,
                }
                active_moderation_expires_at = _timestamp(
                    moderation.get("expires_at_timestamp"),
                    expires_at,
                )

                flag_snapshot = flag_document.get(transaction=transaction_in_progress)
                existing_flag = (
                    dict(flag_snapshot.to_dict() or {}) if flag_snapshot.exists else {}
                )
                if (
                    existing_flag
                    and _timestamp(existing_flag.get("expires_at_timestamp"), 0) > now
                ):
                    payload = _moderation_payload(
                        group_id,
                        moderation,
                        active_moderation_expires_at,
                    )
                    # An idempotent retry may include a report created later in
                    # the same group. Refresh the private 24h snapshot without
                    # consuming either rate limit or creating a second flag.
                    snapshot_changed = (
                        any(
                            report_id
                            not in set(existing_flag.get("report_ids") or [])
                            for report_id in active_report_ids
                        )
                        or any(
                            owner_key
                            not in set(existing_flag.get("owner_keys") or [])
                            for owner_key in active_owner_keys
                        )
                        or any(
                            dict(existing_flag.get("report_sources") or {}).get(
                                report_id
                            ) != owner_key
                            for report_id, owner_key in active_report_sources.items()
                        )
                    )
                    if snapshot_changed:
                        committed_moderation = {
                            **durable_moderation,
                            **payload,
                        }
                        persisted_flag = {
                            **existing_flag,
                            "report_ids": payload["report_ids"],
                            "owner_keys": payload["owner_keys"],
                            "report_sources": payload["report_sources"],
                        }
                        transaction_in_progress.set(
                            moderation_document,
                            payload,
                            merge=True,
                        )
                        transaction_in_progress.set(
                            flag_document,
                            persisted_flag,
                            merge=True,
                        )
                    else:
                        committed_moderation = durable_moderation
                        persisted_flag = dict(existing_flag)
                    if snapshot_changed and bool(payload.get("hidden", False)):
                        for report_document, _report in targets:
                            transaction_in_progress.update(
                                report_document,
                                {
                                    "moderation_hidden": True,
                                    "moderation_hidden_at_timestamp": _datetime(now),
                                    "moderation_reason": str(
                                        payload.get("hidden_reason")
                                        or "administrative_moderation"
                                    ),
                                },
                            )
                    return {
                        "payload": payload,
                        "already_reported": True,
                        "reason": str(existing_flag.get("reason") or reason),
                        "materialized_report_ids": (
                            active_report_ids
                            if snapshot_changed and bool(payload.get("hidden", False))
                            else []
                        ),
                        "persisted_moderation": committed_moderation,
                        "persisted_flag": persisted_flag,
                    }

                if bool(moderation.get("hidden", False)):
                    if not targets:
                        return {
                            "payload": dict(moderation),
                            "already_reported": True,
                            "reason": reason,
                            "materialized_report_ids": [],
                            "persisted_moderation": durable_moderation,
                            "persisted_flag": None,
                        }
                    payload = _moderation_payload(
                        group_id,
                        moderation,
                        active_moderation_expires_at,
                    )
                    committed_moderation = {
                        **durable_moderation,
                        **payload,
                    }
                    transaction_in_progress.set(
                        moderation_document,
                        payload,
                        merge=True,
                    )
                    for report_document, _report in targets:
                        transaction_in_progress.update(
                            report_document,
                            {
                                "moderation_hidden": True,
                                "moderation_hidden_at_timestamp": _datetime(now),
                                "moderation_reason": str(
                                    payload.get("hidden_reason")
                                    or "administrative_moderation"
                                ),
                            },
                        )
                    return {
                        "payload": payload,
                        "already_reported": True,
                        "reason": reason,
                        "materialized_report_ids": active_report_ids,
                        "persisted_moderation": committed_moderation,
                        "persisted_flag": None,
                    }

                if (
                    client_key not in moderation["flaggers"]
                    and len(moderation["flaggers"]) >= max_flaggers
                ):
                    raise CommunityFlagCapacityReached(
                        "community_flag_capacity_reached"
                    )

                global_snapshot = global_limit_document.get(
                    transaction=transaction_in_progress
                )
                global_state = (
                    dict(global_snapshot.to_dict() or {})
                    if global_snapshot.exists
                    else {}
                )
                global_count = max(0, int(global_state.get("count", 0)))
                if global_count >= global_limit:
                    raise CommunityCooldownActive(
                        (global_window + 1) * global_window_seconds
                    )

                client_snapshot = client_limit_document.get(
                    transaction=transaction_in_progress
                )
                client_state = (
                    dict(client_snapshot.to_dict() or {})
                    if client_snapshot.exists
                    else {}
                )
                client_count = max(0, int(client_state.get("count", 0)))
                if client_count >= client_limit:
                    raise CommunityCooldownActive(
                        (client_window + 1) * client_window_seconds
                    )

                moderation["flaggers"][client_key] = reason

                payload = _moderation_payload(group_id, moderation, expires_at)
                committed_moderation = {
                    **durable_moderation,
                    **payload,
                }
                persisted_flag = _flag_payload(
                    group_id,
                    client_key,
                    reason,
                    report_ids=active_report_ids,
                    owner_keys=active_owner_keys,
                    report_sources=active_report_sources,
                    created_at=now,
                    expires_at=expires_at,
                )
                transaction_in_progress.set(
                    flag_document,
                    persisted_flag,
                    merge=False,
                )
                transaction_in_progress.set(moderation_document, payload, merge=True)
                for limit_document, count, window, window_seconds in (
                    (
                        global_limit_document,
                        global_count,
                        global_window,
                        global_window_seconds,
                    ),
                    (
                        client_limit_document,
                        client_count,
                        client_window,
                        client_window_seconds,
                    ),
                ):
                    transaction_in_progress.set(
                        limit_document,
                        {
                            "count": count + 1,
                            "expires_at_timestamp": _datetime(
                                (window + 2) * window_seconds
                            ),
                            "updated_at": datetime.now(timezone.utc),
                            "window": window,
                        },
                        merge=True,
                    )
                return {
                    "payload": payload,
                    "already_reported": False,
                    "reason": reason,
                    "materialized_report_ids": [],
                    "persisted_moderation": committed_moderation,
                    "persisted_flag": persisted_flag,
                }

            result = self._run_transaction(persist, transaction)
        except (
            CommunityCooldownActive,
            CommunityFlagCapacityReached,
            CommunityMutationTargetUnavailable,
        ):
            raise
        except Exception as error:
            raise CommunityRepositoryUnavailable(
                "firestore_flag_transaction_failed"
            ) from error

        payload = dict(result["payload"])
        persisted_moderation = dict(result["persisted_moderation"])
        if persisted_moderation:
            self._moderation[group_id] = persisted_moderation
        else:
            self._moderation.pop(group_id, None)
        if bool(payload.get("hidden", False)):
            for report_id in result["materialized_report_ids"]:
                if report_id in self._reports:
                    self._reports[report_id].update({
                        "moderation_hidden": True,
                        "moderation_hidden_at": now,
                        "moderation_reason": str(
                            payload.get("hidden_reason")
                            or "administrative_moderation"
                        ),
                    })
        flag_id = _flag_document_id(group_id, client_key)
        persisted_flag = result["persisted_flag"]
        if persisted_flag is None:
            self._flags.pop(flag_id, None)
        else:
            self._flags[flag_id] = dict(persisted_flag)
        return {
            **payload,
            "_already_reported": bool(result["already_reported"]),
            "_reason": str(result["reason"]),
        }

    def delete_report_and_cooldown_strict(
        self,
        report_id: str,
        *,
        client_key: str,
    ) -> None:
        """Atomically undo a report and its cooldown in strict mode."""

        try:
            db = self._required_db()
            report_document = db.collection(REPORTS_COLLECTION).document(report_id)
            cooldown_document = db.collection(COOLDOWNS_COLLECTION).document(client_key)
            transaction = db.transaction()

            def persist(transaction_in_progress: Any) -> dict[str, bool]:
                report_snapshot = report_document.get(
                    transaction=transaction_in_progress
                )
                report = (
                    dict(report_snapshot.to_dict() or {})
                    if report_snapshot.exists
                    else {}
                )
                cooldown_snapshot = cooldown_document.get(
                    transaction=transaction_in_progress
                )
                cooldown = (
                    dict(cooldown_snapshot.to_dict() or {})
                    if cooldown_snapshot.exists
                    else {}
                )
                report_owned = (
                    report_snapshot.exists
                    and str(report.get("owner_key") or "") == client_key
                )
                cooldown_report_id = str(cooldown.get("report_id") or "")
                cooldown_matches = cooldown_snapshot.exists and (
                    (
                        cooldown_report_id == report_id
                        and (not report_snapshot.exists or report_owned)
                    )
                    or (not cooldown_report_id and report_owned)
                )
                if report_owned:
                    transaction_in_progress.delete(report_document)
                if cooldown_matches:
                    transaction_in_progress.delete(cooldown_document)
                return {
                    "report_deleted": report_owned,
                    "cooldown_deleted": cooldown_matches,
                }

            result = self._run_transaction(persist, transaction)
        except Exception as error:
            raise CommunityRepositoryUnavailable(
                "firestore_delete_transaction_failed"
            ) from error

        self._reports.pop(report_id, None)
        if bool(result["cooldown_deleted"]):
            self._cooldowns.pop(client_key, None)

    def update_confirmation_strict(
        self,
        group_id: str,
        *,
        client_key: str,
        vote: str,
        expires_at: float,
        global_limit: int,
        global_window_seconds: int,
        max_voters: int,
        now: float,
        report_ids: list[str] | None = None,
        voter_owner_key: str = "",
        reputation_award_day: str = "",
        reputation_daily_limit: int = 3,
    ) -> dict[str, Any]:
        """Atomically apply one idempotent yes/no vote in Firestore."""

        db = self._required_db()
        try:
            document = db.collection(CONFIRMATIONS_COLLECTION).document(
                _confirmation_document_id(group_id)
            )
            moderation_document = db.collection(MODERATION_COLLECTION).document(
                _confirmation_document_id(group_id)
            )
            global_window = int(now // global_window_seconds)
            global_limit_document = db.collection(RATE_LIMITS_COLLECTION).document(
                f"global-confirm-{global_window}"
            )
            transaction = db.transaction()

            def persist(transaction_in_progress: Any) -> dict[str, Any]:
                snapshot = document.get(transaction=transaction_in_progress)
                persisted_confirmation = (
                    dict(snapshot.to_dict() or {}) if snapshot.exists else {}
                )
                tracked_report_ids = [
                    str(value)
                    for value in (persisted_confirmation.get("report_ids") or [])
                    if str(value)
                ]
                requested_report_ids = [
                    str(value) for value in (report_ids or []) if str(value)
                ]
                targets, unavailable_ids = _read_transaction_group_targets(
                    db,
                    transaction_in_progress,
                    group_id=group_id,
                    report_ids=list(dict.fromkeys([
                        *requested_report_ids,
                        *tracked_report_ids,
                    ])),
                    now=now,
                )
                unavailable_requested_ids = set(unavailable_ids).intersection(
                    requested_report_ids
                )
                moderation_snapshot = moderation_document.get(
                    transaction=transaction_in_progress
                )
                moderation = (
                    dict(moderation_snapshot.to_dict() or {})
                    if moderation_snapshot.exists
                    else {}
                )
                moderation_hidden = (
                    bool(moderation.get("hidden", False))
                    and _timestamp(moderation.get("expires_at_timestamp"), 0) > now
                )
                if (
                    not targets
                    or unavailable_requested_ids
                    or moderation_hidden
                    or any(
                        bool(report.get("moderation_hidden", False))
                        for _target, report in targets
                    )
                ):
                    raise CommunityMutationTargetUnavailable(
                        "community_report_not_active"
                    )
                if voter_owner_key and any(
                    str(report.get("owner_key") or "") == voter_owner_key
                    for _target, report in targets
                ):
                    raise CommunitySelfConfirmationNotAllowed(
                        "community_self_confirmation_not_allowed"
                    )
                transaction_expires_at = max(
                    float(report.get("expires_at") or now)
                    for _target, report in targets
                )

                state = dict(persisted_confirmation)
                state.setdefault("yes", 0)
                state.setdefault("no", 0)
                state.setdefault("votes", {})
                state["votes"] = dict(state["votes"] or {})
                state["report_ids"] = list(dict.fromkeys(
                    str(report.get("id") or target.id)
                    for target, report in targets
                    if str(report.get("id") or target.id)
                ))
                state["map_withdrawn"] = bool(
                    state.get("map_withdrawn", False)
                    or max(0, int(state.get("no", 0)))
                    >= DENIAL_WITHDRAWAL_THRESHOLD
                )

                previous_vote = state["votes"].get(client_key)
                effective_vote = str(previous_vote or vote)
                vote_written = previous_vote != "no" and previous_vote != vote
                global_count = 0
                if vote_written:
                    global_snapshot = global_limit_document.get(
                        transaction=transaction_in_progress
                    )
                    global_state = (
                        dict(global_snapshot.to_dict() or {})
                        if global_snapshot.exists
                        else {}
                    )
                    global_count = max(0, int(global_state.get("count", 0)))
                    if global_count >= global_limit:
                        retry_at = (global_window + 1) * global_window_seconds
                        raise CommunityCooldownActive(retry_at)
                    if previous_vote is None and len(state["votes"]) >= max_voters:
                        raise CommunityConfirmationCapacityReached(
                            "community_confirmation_capacity_reached"
                        )
                    if previous_vote in {"yes", "no"}:
                        state[previous_vote] = max(
                            0,
                            int(state.get(previous_vote, 0)) - 1,
                        )
                    state[vote] = int(state.get(vote, 0)) + 1
                    state["votes"][client_key] = vote
                    effective_vote = vote
                    if (
                        vote == "no"
                        and int(state.get("no", 0))
                        >= DENIAL_WITHDRAWAL_THRESHOLD
                    ):
                        state["map_withdrawn"] = True
                        if state.get("map_withdrawn_at") is None:
                            state["map_withdrawn_at"] = _datetime(now)

                target_reports = [report for _document, report in targets]
                state, owner_keys, validation_reason = (
                    _apply_group_validation_state(
                        state,
                        target_reports,
                        now=now,
                    )
                )
                payload = _confirmation_payload(
                    group_id,
                    state,
                    transaction_expires_at,
                )
                report_confirmation_payload = {
                    "confirmation_yes": int(payload.get("yes", 0)),
                    "confirmation_no": int(payload.get("no", 0)),
                    "denial_count": int(payload.get("no", 0)),
                    "map_withdrawn": bool(payload.get("map_withdrawn", False)),
                    "validity_status": str(
                        payload.get("validity_status") or "unverified"
                    ),
                    "temporal_status": str(
                        payload.get("temporal_status") or "active"
                    ),
                }
                award_plans = []
                if payload.get("validity_status") == "verified":
                    award_plans = self._prepare_reputation_awards_strict(
                        db,
                        transaction_in_progress,
                        group_id=group_id,
                        owner_keys=owner_keys,
                        award_day=(
                            reputation_award_day
                            or _datetime(now).date().isoformat()
                        ),
                        daily_limit=max(1, int(reputation_daily_limit)),
                        reason=validation_reason,
                        now=now,
                    )

                coordination_fields = (
                    "report_ids",
                    "report_sources",
                    "validity_status",
                    "verified_at",
                    "closed_unverified",
                    "temporal_status",
                )
                coordination_changed = any(
                    persisted_confirmation.get(field) != payload.get(field)
                    for field in coordination_fields
                )
                reports_need_repair = vote_written or any(
                    int(report.get("confirmation_yes") or 0)
                    != report_confirmation_payload["confirmation_yes"]
                    or int(report.get("confirmation_no") or 0)
                    != report_confirmation_payload["confirmation_no"]
                    or int(report.get("denial_count") or 0)
                    != report_confirmation_payload["denial_count"]
                    or bool(report.get("map_withdrawn", False))
                    != report_confirmation_payload["map_withdrawn"]
                    or str(report.get("validity_status") or "unverified")
                    != report_confirmation_payload["validity_status"]
                    or str(report.get("temporal_status") or "active")
                    != report_confirmation_payload["temporal_status"]
                    for _target, report in targets
                )

                if vote_written:
                    transaction_in_progress.set(
                        global_limit_document,
                        {
                            "count": global_count + 1,
                            "expires_at_timestamp": _datetime(
                                (global_window + 2) * global_window_seconds
                            ),
                            "updated_at": datetime.now(timezone.utc),
                            "window": global_window,
                        },
                        merge=True,
                    )
                if vote_written or coordination_changed:
                    transaction_in_progress.set(document, payload, merge=True)
                if reports_need_repair:
                    for report_document, _report in targets:
                        transaction_in_progress.update(
                            report_document,
                            report_confirmation_payload,
                        )
                self._write_reputation_awards_strict(
                    transaction_in_progress,
                    award_plans,
                )
                committed_confirmation = (
                    {**persisted_confirmation, **payload}
                    if vote_written or coordination_changed
                    else persisted_confirmation
                )
                return {
                    "payload": payload,
                    "persisted_confirmation": committed_confirmation,
                    "effective_vote": effective_vote,
                    "written": vote_written,
                    "materialized_report_ids": (
                        [
                            str(report.get("id") or "")
                            for _document, report in targets
                            if str(report.get("id") or "")
                        ]
                        if reports_need_repair
                        else []
                    ),
                }

            result = self._run_transaction(persist, transaction)
        except (
            CommunityConfirmationCapacityReached,
            CommunityCooldownActive,
            CommunityMutationTargetUnavailable,
            CommunitySelfConfirmationNotAllowed,
        ):
            raise
        except Exception as error:
            raise CommunityRepositoryUnavailable(
                "firestore_confirmation_transaction_failed"
            ) from error

        payload = dict(result["payload"])
        self._confirmations[group_id] = dict(result["persisted_confirmation"])
        for report_id in result["materialized_report_ids"]:
            if report_id in self._reports:
                self._reports[report_id].update({
                    "confirmation_yes": int(payload.get("yes", 0)),
                    "confirmation_no": int(payload.get("no", 0)),
                    "denial_count": int(payload.get("no", 0)),
                    "map_withdrawn": bool(payload.get("map_withdrawn", False)),
                    "validity_status": str(
                        payload.get("validity_status") or "unverified"
                    ),
                    "temporal_status": str(
                        payload.get("temporal_status") or "active"
                    ),
                })
        return {
            **payload,
            "_effective_vote": str(result["effective_vote"]),
            "_written": bool(result["written"]),
        }

    def apply_group_reputation_memory(
        self,
        group_id: str,
        *,
        reports: list[dict[str, Any]],
        confirmation_state: dict[str, Any],
        report_added: bool,
        award_day: str,
        daily_limit: int,
        now: float,
    ) -> dict[str, Any]:
        """Apply the same ledger rules in the lock-protected memory backend."""

        state, owner_keys, reason = _apply_group_validation_state(
            confirmation_state,
            reports,
            now=now,
            report_added=report_added,
        )
        if state.get("validity_status") == "verified":
            self._record_reputation_awards_memory(
                group_id=group_id,
                owner_keys=owner_keys,
                award_day=award_day,
                daily_limit=max(1, int(daily_limit)),
                reason=reason,
                now=now,
            )
        return state

    def get_reputation(
        self,
        owner_key: str,
        *,
        now: float,
    ) -> tuple[dict[str, Any], str]:
        """Read one private pseudonymous summary and active pending episodes."""

        reputation_id = _reputation_document_id(owner_key)
        db = self._db()
        if db is None and self.requires_firestore:
            raise CommunityRepositoryUnavailable("firestore_reputation_unavailable")

        if db is not None and self.requires_firestore:
            try:
                reputation_document = db.collection(REPUTATION_COLLECTION).document(
                    reputation_id
                )
                query = (
                    db.collection(REPORTS_COLLECTION)
                    .where(
                        filter=_field_filter(
                            "owner_key",
                            "==",
                            owner_key,
                        )
                    )
                    .limit(MAX_REPORTS)
                )
                transaction = db.transaction()

                def read_snapshot(
                    transaction_in_progress: Any,
                ) -> tuple[dict[str, Any], list[dict[str, Any]]]:
                    snapshot = reputation_document.get(
                        transaction=transaction_in_progress
                    )
                    stored = (
                        dict(snapshot.to_dict() or {})
                        if snapshot.exists
                        else {}
                    )
                    owned_reports = [
                        normalize_stored_report(item.to_dict() or {}, item.id)
                        for item in query.stream(
                            transaction=transaction_in_progress
                        )
                    ]
                    return stored, owned_reports

                stored_summary, reports = self._run_transaction(
                    read_snapshot,
                    transaction,
                )
                if _timestamp(stored_summary.get("expires_at_timestamp"), 0) <= now:
                    stored_summary = {}
                summary = _reputation_summary(
                    stored_summary,
                    owner_key=owner_key,
                    award_day="",
                )
                storage = "firestore"
            except Exception as error:
                raise CommunityRepositoryUnavailable(
                    "firestore_reputation_read_failed"
                ) from error
        else:
            stored_summary = dict(self._reputations.get(reputation_id) or {})
            if _timestamp(stored_summary.get("expires_at_timestamp"), 0) <= now:
                stored_summary = {}
            summary = _reputation_summary(
                stored_summary,
                owner_key=owner_key,
                award_day="",
            )
            reports = [
                deepcopy(report)
                for report in self._reports.values()
                if str(report.get("owner_key") or "") == owner_key
            ]
            storage = "memory"

        pending_group_ids = {
            str(report.get("group_id") or "")
            for report in reports
            if float(report.get("expires_at") or 0) > now
            and str(report.get("type_id") or "").lower() != "quiet"
            and not bool(report.get("moderation_hidden", False))
            and str(report.get("validity_status") or "unverified")
            == "unverified"
            and str(report.get("temporal_status") or "active") == "active"
            and max(0, int(report.get("confirmation_yes", 0))) == 0
            and max(0, int(report.get("confirmation_no", 0))) == 0
            and str(report.get("group_id") or "")
        }
        return ({
            "points": max(0, int(summary.get("points", 0))),
            "total_reports": max(0, int(summary.get("total_reports", 0))),
            "validated_reports": max(
                0,
                int(summary.get("validated_reports", 0)),
            ),
            "pending_reports": len(pending_group_ids),
        }, storage)

    def revoke_group_reputation_strict(
        self,
        group_id: str,
        *,
        now: float,
        reason: str,
    ) -> int:
        """Atomically revoke every durable award for an administratively rejected episode."""

        db = self._required_db()
        try:
            snapshots = list(
                db.collection(REPUTATION_AWARDS_COLLECTION)
                .where(
                    filter=_field_filter(
                        "episode_key",
                        "==",
                        _reputation_episode_key(group_id),
                    )
                )
                .limit(GROUP_LOOKUP_LIMIT)
                .stream()
            )
            snapshots = [
                snapshot
                for snapshot in snapshots
                if _timestamp(
                    (snapshot.to_dict() or {}).get("expires_at_timestamp"),
                    0,
                )
                > now
            ]
            if len(snapshots) > MAX_REPORTS:
                raise CommunityRepositoryUnavailable(
                    "community_reputation_episode_too_large"
                )
            if not snapshots:
                return 0

            transaction = db.transaction()

            def revoke(transaction_in_progress: Any) -> int:
                plans: list[tuple[Any, dict[str, Any], Any, dict[str, Any]]] = []
                for snapshot in snapshots:
                    award_document = db.collection(
                        REPUTATION_AWARDS_COLLECTION
                    ).document(str(snapshot.id))
                    current_snapshot = award_document.get(
                        transaction=transaction_in_progress
                    )
                    if not current_snapshot.exists:
                        continue
                    award = dict(current_snapshot.to_dict() or {})
                    if (
                        str(award.get("status") or "") == "revoked"
                        or _timestamp(award.get("expires_at_timestamp"), 0) <= now
                    ):
                        continue
                    owner_key = str(award.get("owner_key") or "")
                    if not owner_key:
                        continue
                    reputation_document = db.collection(
                        REPUTATION_COLLECTION
                    ).document(_reputation_document_id(owner_key))
                    reputation_snapshot = reputation_document.get(
                        transaction=transaction_in_progress
                    )
                    stored_summary = (
                        dict(reputation_snapshot.to_dict() or {})
                        if reputation_snapshot.exists
                        else {}
                    )
                    if _timestamp(
                        stored_summary.get("expires_at_timestamp"),
                        0,
                    ) <= now:
                        stored_summary = {}
                    current_daily_day = str(
                        stored_summary.get("daily_award_day") or ""
                    )
                    summary = _reputation_summary(
                        stored_summary,
                        owner_key=owner_key,
                        award_day=current_daily_day,
                    )
                    points_delta = max(0, min(1, int(award.get("points_delta", 0))))
                    summary["points"] = max(
                        0,
                        int(summary["points"]) - points_delta,
                    )
                    summary["validated_reports"] = max(
                        0,
                        int(summary["validated_reports"]) - 1,
                    )
                    summary["revoked_reports"] = int(summary["revoked_reports"]) + 1
                    if (
                        points_delta
                        and current_daily_day == str(award.get("award_day") or "")
                    ):
                        summary["daily_awards"] = max(
                            0,
                            int(summary["daily_awards"]) - 1,
                        )
                    summary["updated_at"] = _datetime(now)
                    summary["expires_at_timestamp"] = _datetime(
                        now + REPUTATION_RETENTION_SECONDS
                    )
                    award.update({
                        "status": "revoked",
                        "points_delta": 0,
                        "revoked_at_timestamp": _datetime(now),
                        "revocation_reason": str(reason or "administrative_rejection")[:80],
                        "updated_at": _datetime(now),
                        "expires_at_timestamp": _datetime(
                            now + REPUTATION_RETENTION_SECONDS
                        ),
                    })
                    plans.append((
                        award_document,
                        award,
                        reputation_document,
                        summary,
                    ))

                for award_document, award, reputation_document, summary in plans:
                    transaction_in_progress.set(
                        award_document,
                        award,
                        merge=False,
                    )
                    transaction_in_progress.set(
                        reputation_document,
                        summary,
                        merge=False,
                    )
                return len(plans)

            return int(self._run_transaction(revoke, transaction))
        except CommunityRepositoryUnavailable:
            raise
        except Exception as error:
            raise CommunityRepositoryUnavailable(
                "firestore_reputation_revocation_failed"
            ) from error

    def revoke_group_reputation_memory(
        self,
        group_id: str,
        *,
        now: float,
        reason: str,
    ) -> int:
        episode_key = _reputation_episode_key(group_id)
        revoked = 0
        for award_id, stored_award in list(self._reputation_awards.items()):
            award = dict(stored_award)
            if (
                str(award.get("episode_key") or "") != episode_key
                or str(award.get("status") or "") == "revoked"
                or _timestamp(award.get("expires_at_timestamp"), 0) <= now
            ):
                continue
            owner_key = str(award.get("owner_key") or "")
            reputation_id = _reputation_document_id(owner_key)
            stored_summary = dict(self._reputations.get(reputation_id) or {})
            if _timestamp(stored_summary.get("expires_at_timestamp"), 0) <= now:
                stored_summary = {}
            current_daily_day = str(
                stored_summary.get("daily_award_day") or ""
            )
            summary = _reputation_summary(
                stored_summary,
                owner_key=owner_key,
                award_day=current_daily_day,
            )
            points_delta = max(0, min(1, int(award.get("points_delta", 0))))
            summary["points"] = max(0, int(summary["points"]) - points_delta)
            summary["validated_reports"] = max(
                0,
                int(summary["validated_reports"]) - 1,
            )
            summary["revoked_reports"] = int(summary["revoked_reports"]) + 1
            if (
                points_delta
                and current_daily_day == str(award.get("award_day") or "")
            ):
                summary["daily_awards"] = max(
                    0,
                    int(summary["daily_awards"]) - 1,
                )
            summary["updated_at"] = _datetime(now)
            summary["expires_at_timestamp"] = _datetime(
                now + REPUTATION_RETENTION_SECONDS
            )
            award.update({
                "status": "revoked",
                "points_delta": 0,
                "revoked_at_timestamp": _datetime(now),
                "revocation_reason": str(reason or "administrative_rejection")[:80],
                "updated_at": _datetime(now),
                "expires_at_timestamp": _datetime(
                    now + REPUTATION_RETENTION_SECONDS
                ),
            })
            self._reputations[reputation_id] = summary
            self._reputation_awards[award_id] = award
            revoked += 1
        return revoked

    def list_reports(self, now: float) -> tuple[list[dict[str, Any]], str]:
        self._prune_memory(now)
        memory_reports = list(self._reports.values())
        db = self._db()
        if db is None:
            if self.requires_firestore:
                raise CommunityRepositoryUnavailable("firestore_list_unavailable")
            return self._sorted(memory_reports), "memory"

        try:
            collection = db.collection(REPORTS_COLLECTION)
            firestore_reports = []
            if self.requires_firestore:
                documents = (
                    collection
                    .where(filter=_field_filter(
                        "expires_at_timestamp",
                        ">",
                        _datetime(now),
                    ))
                    .order_by("expires_at_timestamp", direction="DESCENDING")
                    .limit(MAX_REPORTS)
                    .stream()
                )
            else:
                documents = collection.stream()

            for document in documents:
                report = normalize_stored_report(document.to_dict() or {}, document.id)
                if report["expires_at"] <= now:
                    if not self.requires_firestore:
                        try:
                            collection.document(document.id).delete()
                        except Exception:
                            pass
                    continue
                firestore_reports.append(report)

            if self.requires_firestore:
                return self._sorted(firestore_reports), "firestore"

            merged = {report["id"]: report for report in firestore_reports}
            memory_only = False
            for report in memory_reports:
                if report["id"] not in merged:
                    memory_only = True
                    merged[report["id"]] = report
            return self._sorted(merged.values()), (
                "firestore_memory_fallback" if memory_only else "firestore"
            )
        except Exception as error:
            if self.requires_firestore:
                raise CommunityRepositoryUnavailable(
                    "firestore_list_failed"
                ) from error
            return self._sorted(memory_reports), "memory_fallback"

    def get_report(self, report_id: str, now: float) -> tuple[dict[str, Any] | None, str]:
        db = self._db()
        if db is not None:
            try:
                snapshot = db.collection(REPORTS_COLLECTION).document(report_id).get()
                if snapshot.exists:
                    report = normalize_stored_report(
                        snapshot.to_dict() or {},
                        report_id,
                    )
                    if float(report.get("expires_at") or 0) > now:
                        return report, "firestore"
                if self.requires_firestore:
                    return None, "firestore"
            except Exception as error:
                if self.requires_firestore:
                    raise CommunityRepositoryUnavailable(
                        "firestore_report_read_failed"
                    ) from error
        elif self.requires_firestore:
            raise CommunityRepositoryUnavailable("firestore_report_unavailable")

        report = deepcopy(dict(self._reports.get(report_id) or {}))
        if report and float(report.get("expires_at") or 0) > now:
            return report, "memory" if db is None else "memory_fallback"
        self._reports.pop(report_id, None)
        return None, "memory" if db is None else "memory_fallback"

    def list_group_reports(
        self,
        group_id: str,
        now: float,
    ) -> tuple[list[dict[str, Any]], str]:
        db = self._db()
        if db is not None:
            try:
                documents = (
                    db.collection(REPORTS_COLLECTION)
                    .where(filter=_field_filter("group_id", "==", group_id))
                    .limit(GROUP_LOOKUP_LIMIT)
                    .stream()
                )
                reports = []
                for document in documents:
                    report = normalize_stored_report(
                        document.to_dict() or {},
                        document.id,
                    )
                    if float(report.get("expires_at") or 0) > now:
                        reports.append(report)
                if self.requires_firestore:
                    return self._sorted_group(reports), "firestore"
                if reports:
                    return self._sorted_group(reports), "firestore"
            except Exception as error:
                if self.requires_firestore:
                    raise CommunityRepositoryUnavailable(
                        "firestore_group_reports_read_failed"
                    ) from error
        elif self.requires_firestore:
            raise CommunityRepositoryUnavailable(
                "firestore_group_reports_unavailable"
            )

        reports = [
            dict(report)
            for report in self._reports.values()
            if str(report.get("group_id") or "") == group_id
            and float(report.get("expires_at") or 0) > now
        ]
        return (
            self._sorted_group(reports),
            "memory" if db is None else "memory_fallback",
        )

    def list_hidden_group_ids(self, now: float) -> set[str]:
        """Return active administrative visibility gates in one bounded query.

        This is deliberately one feed-level lookup, never one moderation read
        per public group.  Materialized report fields remain the common path;
        the group gate also closes the narrow race where an in-flight create
        commits while an administrator is hiding/removing that group.
        """

        db = self._db()
        if db is not None:
            try:
                documents = (
                    db.collection(MODERATION_COLLECTION)
                    .where(filter=_field_filter("hidden", "==", True))
                    .stream()
                )
                hidden_group_ids = {
                    str(payload.get("group_id") or "")
                    for document in documents
                    for payload in [dict(document.to_dict() or {})]
                    if str(payload.get("group_id") or "")
                    and _timestamp(payload.get("expires_at_timestamp"), 0) > now
                }
                if self.requires_firestore or hidden_group_ids:
                    return hidden_group_ids
            except Exception as error:
                if self.requires_firestore:
                    raise CommunityRepositoryUnavailable(
                        "firestore_hidden_groups_read_failed"
                    ) from error
        elif self.requires_firestore:
            raise CommunityRepositoryUnavailable(
                "firestore_hidden_groups_unavailable"
            )

        return {
            str(group_id)
            for group_id, state in self._moderation.items()
            if bool(state.get("hidden", False))
            and _timestamp(state.get("expires_at_timestamp"), 0) > now
        }

    def save_report(self, report: dict[str, Any]) -> str:
        db = self._db()
        if db is None:
            if self.requires_firestore:
                raise CommunityRepositoryUnavailable("firestore_save_unavailable")
            self._reports[report["id"]] = deepcopy(dict(report))
            self._trim_memory()
            return "memory"
        try:
            db.collection(REPORTS_COLLECTION).document(report["id"]).set(
                _report_payload(report),
                merge=True,
            )
        except Exception as error:
            if self.requires_firestore:
                raise CommunityRepositoryUnavailable("firestore_save_failed") from error
            self._reports[report["id"]] = deepcopy(dict(report))
            self._trim_memory()
            return "memory_fallback"
        self._reports[report["id"]] = deepcopy(dict(report))
        self._trim_memory()
        return "firestore"

    def delete_report(self, report_id: str) -> str:
        db = self._db()
        if db is None:
            if self.requires_firestore:
                raise CommunityRepositoryUnavailable("firestore_delete_unavailable")
            self._reports.pop(report_id, None)
            return "memory"
        try:
            db.collection(REPORTS_COLLECTION).document(report_id).delete()
        except Exception as error:
            if self.requires_firestore:
                raise CommunityRepositoryUnavailable("firestore_delete_failed") from error
            self._reports.pop(report_id, None)
            return "memory_fallback"
        self._reports.pop(report_id, None)
        return "firestore"

    def get_cooldown(self, client_key: str, now: float) -> float:
        db = self._db()
        if db is None and self.requires_firestore:
            raise CommunityRepositoryUnavailable("firestore_cooldown_unavailable")
        if db is not None:
            try:
                document = db.collection(COOLDOWNS_COLLECTION).document(client_key)
                snapshot = document.get()
                if snapshot.exists:
                    cooldown_until = _timestamp((snapshot.to_dict() or {}).get("cooldown_until"), 0)
                    if cooldown_until > now:
                        return cooldown_until
                    document.delete()
            except Exception as error:
                if self.requires_firestore:
                    raise CommunityRepositoryUnavailable(
                        "firestore_cooldown_read_failed"
                    ) from error

            if self.requires_firestore:
                return 0

        cooldown_until = self._cooldowns.get(client_key, 0)
        if cooldown_until <= now:
            self._cooldowns.pop(client_key, None)
            return 0
        return cooldown_until

    def set_cooldown(self, client_key: str, cooldown_until: float) -> str:
        db = self._db()
        if db is None:
            if self.requires_firestore:
                raise CommunityRepositoryUnavailable("firestore_cooldown_unavailable")
            self._cooldowns[client_key] = cooldown_until
            return "memory"
        try:
            db.collection(COOLDOWNS_COLLECTION).document(client_key).set(
                _cooldown_payload(client_key, cooldown_until),
                merge=True,
            )
        except Exception as error:
            if self.requires_firestore:
                raise CommunityRepositoryUnavailable(
                    "firestore_cooldown_write_failed"
                ) from error
            self._cooldowns[client_key] = cooldown_until
            return "memory_fallback"
        self._cooldowns[client_key] = cooldown_until
        return "firestore"

    def clear_cooldown(self, client_key: str) -> str:
        db = self._db()
        if db is None:
            if self.requires_firestore:
                raise CommunityRepositoryUnavailable("firestore_cooldown_unavailable")
            self._cooldowns.pop(client_key, None)
            return "memory"
        try:
            db.collection(COOLDOWNS_COLLECTION).document(client_key).delete()
        except Exception as error:
            if self.requires_firestore:
                raise CommunityRepositoryUnavailable(
                    "firestore_cooldown_delete_failed"
                ) from error
            self._cooldowns.pop(client_key, None)
            return "memory_fallback"
        self._cooldowns.pop(client_key, None)
        return "firestore"

    def get_confirmation(self, group_id: str) -> dict[str, Any]:
        db = self._db()
        if db is None and self.requires_firestore:
            raise CommunityRepositoryUnavailable("firestore_confirmation_unavailable")
        if db is not None:
            try:
                snapshot = db.collection(CONFIRMATIONS_COLLECTION).document(
                    _confirmation_document_id(group_id)
                ).get()
                if snapshot.exists:
                    payload = dict(snapshot.to_dict() or {})
                    payload.setdefault("votes", {})
                    return payload
            except Exception as error:
                if self.requires_firestore:
                    raise CommunityRepositoryUnavailable(
                        "firestore_confirmation_read_failed"
                    ) from error
            if self.requires_firestore:
                return {"yes": 0, "no": 0, "votes": {}}
        return dict(self._confirmations.get(group_id) or {"yes": 0, "no": 0, "votes": {}})

    def save_confirmation(self, group_id: str, state: dict[str, Any], expires_at: float) -> str:
        payload = _confirmation_payload(group_id, state, expires_at)
        db = self._db()
        if db is None:
            if self.requires_firestore:
                raise CommunityRepositoryUnavailable("firestore_confirmation_unavailable")
            self._confirmations[group_id] = payload
            return "memory"
        try:
            db.collection(CONFIRMATIONS_COLLECTION).document(
                _confirmation_document_id(group_id)
            ).set(payload, merge=True)
        except Exception as error:
            if self.requires_firestore:
                raise CommunityRepositoryUnavailable(
                    "firestore_confirmation_write_failed"
                ) from error
            self._confirmations[group_id] = payload
            return "memory_fallback"
        self._confirmations[group_id] = payload
        return "firestore"

    def materialize_confirmation_counts(
        self,
        report_ids: list[str],
        *,
        yes: int,
        no: int,
        map_withdrawn: bool = False,
        validity_status: str | None = None,
        temporal_status: str | None = None,
    ) -> str:
        payload = {
            "confirmation_yes": max(0, int(yes)),
            "confirmation_no": max(0, int(no)),
            "denial_count": max(0, int(no)),
            "map_withdrawn": bool(
                map_withdrawn
                or max(0, int(no)) >= DENIAL_WITHDRAWAL_THRESHOLD
            ),
        }
        if validity_status is not None:
            payload["validity_status"] = str(validity_status)
        if temporal_status is not None:
            payload["temporal_status"] = str(temporal_status)
        db = self._db()
        if db is None:
            if self.requires_firestore:
                raise CommunityRepositoryUnavailable(
                    "firestore_confirmation_materialization_unavailable"
                )
            storage = "memory"
        else:
            try:
                batch = db.batch()
                for report_id in report_ids:
                    if report_id:
                        batch.set(
                            db.collection(REPORTS_COLLECTION).document(report_id),
                            payload,
                            merge=True,
                        )
                batch.commit()
                storage = "firestore"
            except Exception as error:
                if self.requires_firestore:
                    raise CommunityRepositoryUnavailable(
                        "firestore_confirmation_materialization_failed"
                    ) from error
                storage = "memory_fallback"
        for report_id in report_ids:
            if report_id in self._reports:
                self._reports[report_id].update(payload)
        return storage

    def flag_group(
        self,
        group_id: str,
        *,
        report_ids: list[str],
        owner_keys: list[str],
        report_sources: dict[str, str],
        client_key: str,
        reason: str,
        expires_at: float,
        global_limit: int,
        global_window_seconds: int,
        client_limit: int,
        client_window_seconds: int,
        max_flaggers: int,
        now: float,
    ) -> tuple[dict[str, Any], str]:
        """Store one idempotent flag in memory or the optional Firestore mirror."""

        flag_id = _flag_document_id(group_id, client_key)
        state = self.get_group_moderation(group_id, now)
        if bool(state.get("hidden", False)):
            for report_id in report_ids:
                if report_id in self._reports:
                    self._reports[report_id].update({
                        "moderation_hidden": True,
                        "moderation_hidden_at": now,
                        "moderation_reason": str(
                            state.get("hidden_reason")
                            or "administrative_moderation"
                        ),
                    })
            db = self._db()
            if db is not None:
                try:
                    batch = db.batch()
                    for report_id in report_ids:
                        if report_id:
                            batch.set(
                                db.collection(REPORTS_COLLECTION).document(report_id),
                                {
                                    "moderation_hidden": True,
                                    "moderation_hidden_at_timestamp": _datetime(now),
                                    "moderation_reason": str(
                                        state.get("hidden_reason")
                                        or "administrative_moderation"
                                    ),
                                },
                                merge=True,
                            )
                    batch.commit()
                    storage = "firestore"
                except Exception as error:
                    if self.requires_firestore:
                        raise CommunityRepositoryUnavailable(
                            "firestore_flag_write_failed"
                        ) from error
                    storage = "memory_fallback"
            else:
                storage = "memory"
            return ({
                **state,
                "_already_reported": True,
                "_reason": reason,
            }, storage)

        existing = self._flags.get(flag_id)
        if existing and _timestamp(existing.get("expires_at_timestamp"), 0) > now:
            state["report_ids"] = list(dict.fromkeys([
                *(state.get("report_ids") or []),
                *report_ids,
            ]))
            state["owner_keys"] = list(dict.fromkeys([
                *(state.get("owner_keys") or []),
                *owner_keys,
            ]))
            state["report_sources"] = {
                **dict(state.get("report_sources") or {}),
                **report_sources,
            }
            moderation_payload = _moderation_payload(
                group_id,
                state,
                _timestamp(existing.get("expires_at_timestamp"), expires_at),
            )
            existing_payload = {
                **existing,
                "report_ids": moderation_payload["report_ids"],
                "owner_keys": moderation_payload["owner_keys"],
                "report_sources": moderation_payload["report_sources"],
            }
            self._moderation[group_id] = moderation_payload
            self._flags[flag_id] = existing_payload
            return ({
                **moderation_payload,
                "_already_reported": True,
                "_reason": str(existing.get("reason") or reason),
            }, "memory")

        global_window = int(now // global_window_seconds)
        client_window = int(now // client_window_seconds)
        global_rate_key = f"global-flag-{global_window}"
        client_rate_key = f"client-flag-{client_key}-{client_window}"
        global_rate = dict(self._rate_limits.get(global_rate_key) or {})
        client_rate = dict(self._rate_limits.get(client_rate_key) or {})
        if int(global_rate.get("count", 0)) >= global_limit:
            raise CommunityCooldownActive(
                (global_window + 1) * global_window_seconds
            )
        if int(client_rate.get("count", 0)) >= client_limit:
            raise CommunityCooldownActive(
                (client_window + 1) * client_window_seconds
            )

        flaggers = dict(state.get("flaggers") or {})
        state["report_ids"] = list(dict.fromkeys([
            *(state.get("report_ids") or []),
            *report_ids,
        ]))
        state["owner_keys"] = list(dict.fromkeys([
            *(state.get("owner_keys") or []),
            *owner_keys,
        ]))
        state["report_sources"] = {
            **dict(state.get("report_sources") or {}),
            **report_sources,
        }
        if client_key not in flaggers and len(flaggers) >= max_flaggers:
            raise CommunityFlagCapacityReached("community_flag_capacity_reached")
        flaggers[client_key] = reason
        state["flaggers"] = flaggers

        moderation_payload = _moderation_payload(group_id, state, expires_at)
        flag_payload = _flag_payload(
            group_id,
            client_key,
            reason,
            report_ids=report_ids,
            owner_keys=owner_keys,
            report_sources=report_sources,
            created_at=now,
            expires_at=expires_at,
        )
        db = self._db()
        if db is None:
            if self.requires_firestore:
                raise CommunityRepositoryUnavailable("firestore_flag_unavailable")
            storage = "memory"
        else:
            try:
                batch = db.batch()
                batch.set(
                    db.collection(FLAGS_COLLECTION).document(flag_id),
                    flag_payload,
                    merge=False,
                )
                batch.set(
                    db.collection(MODERATION_COLLECTION).document(
                        _confirmation_document_id(group_id)
                    ),
                    moderation_payload,
                    merge=True,
                )
                batch.commit()
                storage = "firestore"
            except Exception as error:
                if self.requires_firestore:
                    raise CommunityRepositoryUnavailable(
                        "firestore_flag_write_failed"
                    ) from error
                storage = "memory_fallback"

        self._flags[flag_id] = flag_payload
        self._moderation[group_id] = moderation_payload
        if bool(moderation_payload.get("hidden", False)):
            for report_id in report_ids:
                if report_id in self._reports:
                    self._reports[report_id].update({
                        "moderation_hidden": True,
                        "moderation_hidden_at": now,
                        "moderation_reason": str(
                            moderation_payload.get("hidden_reason")
                            or "administrative_moderation"
                        ),
                    })
        self._rate_limits[global_rate_key] = {
            "count": int(global_rate.get("count", 0)) + 1,
            "expires_at": (global_window + 2) * global_window_seconds,
        }
        self._rate_limits[client_rate_key] = {
            "count": int(client_rate.get("count", 0)) + 1,
            "expires_at": (client_window + 2) * client_window_seconds,
        }
        return ({
            **moderation_payload,
            "_already_reported": False,
            "_reason": reason,
        }, storage)

    def get_group_moderation(self, group_id: str, now: float) -> dict[str, Any]:
        db = self._db()
        if db is None and self.requires_firestore:
            raise CommunityRepositoryUnavailable("firestore_moderation_unavailable")
        if db is not None:
            try:
                snapshot = db.collection(MODERATION_COLLECTION).document(
                    _confirmation_document_id(group_id)
                ).get()
                if snapshot.exists:
                    payload = dict(snapshot.to_dict() or {})
                    if _timestamp(payload.get("expires_at_timestamp"), 0) > now:
                        payload.setdefault("flaggers", {})
                        return payload
            except Exception as error:
                if self.requires_firestore:
                    raise CommunityRepositoryUnavailable(
                        "firestore_moderation_read_failed"
                    ) from error
            if self.requires_firestore:
                return {"flag_count": 0, "flaggers": {}, "hidden": False}

        state = dict(self._moderation.get(group_id) or {})
        if _timestamp(state.get("expires_at_timestamp"), now + 1) <= now:
            self._moderation.pop(group_id, None)
            return {"flag_count": 0, "flaggers": {}, "hidden": False}
        state.setdefault("flag_count", len(dict(state.get("flaggers") or {})))
        state.setdefault("flaggers", {})
        state.setdefault("hidden", False)
        return state

    def get_source_block(self, owner_key: str, now: float) -> dict[str, Any]:
        document_id = _source_block_document_id(owner_key)
        db = self._db()
        if db is None and self.requires_firestore:
            raise CommunityRepositoryUnavailable("firestore_source_block_unavailable")
        if db is not None:
            try:
                snapshot = db.collection(SOURCE_BLOCKS_COLLECTION).document(
                    document_id
                ).get()
                if snapshot.exists:
                    payload = dict(snapshot.to_dict() or {})
                    if _timestamp(payload.get("blocked_until"), 0) > now:
                        return payload
            except Exception as error:
                if self.requires_firestore:
                    raise CommunityRepositoryUnavailable(
                        "firestore_source_block_read_failed"
                    ) from error
            if self.requires_firestore:
                return {"blocked_until": 0}

        payload = dict(self._source_blocks.get(document_id) or {})
        if _timestamp(payload.get("blocked_until"), 0) <= now:
            self._source_blocks.pop(document_id, None)
            return {"blocked_until": 0}
        return payload

    def set_source_block(
        self,
        owner_key: str,
        *,
        blocked_until: float,
        reason: str,
        report_id: str = "",
    ) -> str:
        document_id = _source_block_document_id(owner_key)
        payload = {
            "blocked_until": float(blocked_until),
            "reason": str(reason or "administrative_moderation")[:120],
            "report_id": str(report_id or "")[:160],
            "updated_at": datetime.now(timezone.utc),
            "expires_at_timestamp": _datetime(blocked_until),
        }
        db = self._db()
        if db is None:
            if self.requires_firestore:
                raise CommunityRepositoryUnavailable(
                    "firestore_source_block_unavailable"
                )
            storage = "memory"
        else:
            try:
                db.collection(SOURCE_BLOCKS_COLLECTION).document(document_id).set(
                    payload,
                    merge=True,
                )
                storage = "firestore"
            except Exception as error:
                if self.requires_firestore:
                    raise CommunityRepositoryUnavailable(
                        "firestore_source_block_write_failed"
                    ) from error
                storage = "memory_fallback"
        self._source_blocks[document_id] = payload
        return storage

    def _prune_memory(self, now: float) -> None:
        self._reports = {
            report_id: report
            for report_id, report in self._reports.items()
            if float(report.get("expires_at") or 0) > now
        }
        self._cooldowns = {
            key: value for key, value in self._cooldowns.items() if value > now
        }
        self._confirmations = {
            group_id: state
            for group_id, state in self._confirmations.items()
            if _timestamp(state.get("expires_at_timestamp"), now + 1) > now
        }
        self._flags = {
            flag_id: state
            for flag_id, state in self._flags.items()
            if _timestamp(state.get("expires_at_timestamp"), now + 1) > now
        }
        self._moderation = {
            group_id: state
            for group_id, state in self._moderation.items()
            if _timestamp(state.get("expires_at_timestamp"), now + 1) > now
        }
        self._source_blocks = {
            document_id: state
            for document_id, state in self._source_blocks.items()
            if _timestamp(state.get("blocked_until"), now + 1) > now
        }
        self._rate_limits = {
            rate_id: state
            for rate_id, state in self._rate_limits.items()
            if _timestamp(state.get("expires_at"), now + 1) > now
        }
        self._reputations = {
            reputation_id: state
            for reputation_id, state in self._reputations.items()
            if _timestamp(state.get("expires_at_timestamp"), 0) > now
        }
        self._reputation_awards = {
            award_id: state
            for award_id, state in self._reputation_awards.items()
            if _timestamp(state.get("expires_at_timestamp"), 0) > now
        }

    def _trim_memory(self) -> None:
        sorted_reports = self._sorted(self._reports.values())[:MAX_REPORTS]
        self._reports = {report["id"]: report for report in sorted_reports}

    @staticmethod
    def _sorted(reports: Any) -> list[dict[str, Any]]:
        return sorted(
            (deepcopy(dict(report)) for report in reports),
            key=lambda report: float(report.get("created_at") or 0),
            reverse=True,
        )[:MAX_REPORTS]

    @staticmethod
    def _sorted_group(reports: Any) -> list[dict[str, Any]]:
        return sorted(
            (deepcopy(dict(report)) for report in reports),
            key=lambda report: float(report.get("created_at") or 0),
            reverse=True,
        )
