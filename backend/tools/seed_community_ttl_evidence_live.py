r"""Create six bounded LIVE Community TTL samples for evidence capture.

The tool is read-only unless ``--apply`` is supplied.  An applied run creates
one synthetic document in each Community collection not covered by the
moderation smoke, emits an aggregate evidence-ready event, optionally holds the
documents for at most 120 seconds, and removes only marker-owned documents from
a Firestore transaction.

The synthetic report is already expired and is also marked moderation-hidden.
The tagged public API and a fresh local instance of the public service are
checked before the write, after the write, during every hold interval, and
after cleanup.  No document identifier, marker, pseudonymous key, coordinates,
or report content is printed.
"""

from __future__ import annotations

import argparse
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
from urllib.parse import urlsplit, urlunsplit

import requests


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.infrastructure.firebase import get_firestore_client  # noqa: E402
from app.repositories.community import (  # noqa: E402
    CONFIRMATIONS_COLLECTION,
    COOLDOWNS_COLLECTION,
    RATE_LIMITS_COLLECTION,
    REPUTATION_AWARDS_COLLECTION,
    REPUTATION_COLLECTION,
    REPUTATION_RETENTION_SECONDS,
    REPORTS_COLLECTION,
    CommunityRepository,
    _confirmation_document_id,
    _confirmation_payload,
    _cooldown_payload,
    _datetime,
    _report_payload,
    _reputation_award_document_id,
    _reputation_award_payload,
    _reputation_document_id,
)
from app.services.community import CommunityService  # noqa: E402


EXPECTED_FIRESTORE_PROJECT_ID = "meteo-friul"
QA_MARKER_FIELD = "qa_ttl_evidence_marker"
MAX_HOLD_SECONDS = 120
PUBLIC_PROBE_INTERVAL_SECONDS = 5
PUBLIC_API_TIMEOUT_SECONDS = 15
REPORT_TTL_SECONDS = 60 * 60
COOLDOWN_TTL_SECONDS = 45 * 60
CONFIRMATION_TTL_SECONDS = 60 * 60
RATE_LIMIT_TTL_SECONDS = 2 * 60 * 60
RUN_TOKEN_PATTERN = re.compile(r"^[a-f0-9]{12,32}$")
TAGGED_API_HOST_PATTERN = re.compile(
    r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?"
    r"---meteofriul-api-[a-z0-9-]+\.a\.run\.app$"
)


class CommunityTtlEvidenceSeedError(RuntimeError):
    """A sanitized failure code safe to expose in aggregate CLI output."""

    def __init__(self, code: str) -> None:
        safe_code = str(code or "unexpected_failure").strip().lower()
        if re.fullmatch(r"[a-z0-9_]+", safe_code) is None:
            safe_code = "unexpected_failure"
        self.code = safe_code
        super().__init__(safe_code)


@dataclass(frozen=True)
class QaIdentity:
    marker: str
    report_id: str
    group_id: str
    client_key: str
    confirmation_document_id: str
    rate_limit_document_id: str
    reputation_document_id: str
    reputation_award_document_id: str


def _qa_identity(run_token: str, *, now: float) -> QaIdentity:
    token = str(run_token or "").strip().lower()
    if RUN_TOKEN_PATTERN.fullmatch(token) is None:
        raise CommunityTtlEvidenceSeedError("qa_run_token_invalid")
    marker = f"community-ttl-evidence-seed:{token}"
    group_id = f"group-quiet:qa-ttl-evidence-{token}:{max(1, int(now))}"
    report_id = "qa-ttl-" + hashlib.sha256(
        f"{marker}:report".encode("utf-8")
    ).hexdigest()[:32]
    client_key = hashlib.sha256(
        f"{marker}:client".encode("utf-8")
    ).hexdigest()
    reputation_document_id = _reputation_document_id(client_key)
    reputation_award_document_id = _reputation_award_document_id(
        group_id,
        client_key,
    )
    return QaIdentity(
        marker=marker,
        report_id=report_id,
        group_id=group_id,
        client_key=client_key,
        confirmation_document_id=_confirmation_document_id(group_id),
        rate_limit_document_id="qa-ttl-" + hashlib.sha256(
            f"{marker}:rate-limit".encode("utf-8")
        ).hexdigest()[:32],
        reputation_document_id=reputation_document_id,
        reputation_award_document_id=reputation_award_document_id,
    )


def _normalize_tagged_api_base(value: str) -> str:
    try:
        parsed = urlsplit(str(value or "").strip())
        port = parsed.port
    except ValueError as error:
        raise CommunityTtlEvidenceSeedError("tagged_api_base_invalid") from error
    host = str(parsed.hostname or "").lower()
    if (
        parsed.scheme.lower() != "https"
        or parsed.username is not None
        or parsed.password is not None
        or port not in (None, 443)
        or TAGGED_API_HOST_PATTERN.fullmatch(host) is None
        or parsed.query
        or parsed.fragment
        or parsed.path.rstrip("/") != "/api"
    ):
        raise CommunityTtlEvidenceSeedError("tagged_api_base_invalid")
    authority = host if port is None else f"{host}:{port}"
    return urlunsplit(("https", authority, "/api", "", ""))


def _document_refs(db: Any, identity: QaIdentity) -> dict[str, Any]:
    return {
        "report": db.collection(REPORTS_COLLECTION).document(identity.report_id),
        "cooldown": db.collection(COOLDOWNS_COLLECTION).document(
            identity.client_key
        ),
        "confirmation": db.collection(CONFIRMATIONS_COLLECTION).document(
            identity.confirmation_document_id
        ),
        "rate_limit": db.collection(RATE_LIMITS_COLLECTION).document(
            identity.rate_limit_document_id
        ),
        "reputation": db.collection(REPUTATION_COLLECTION).document(
            identity.reputation_document_id
        ),
        "reputation_award": db.collection(
            REPUTATION_AWARDS_COLLECTION
        ).document(identity.reputation_award_document_id),
    }


def _snapshot(document: Any, *, transaction: Any | None = None) -> Any:
    if transaction is None:
        return document.get()
    return document.get(transaction=transaction)


def _payload(snapshot: Any) -> dict[str, Any]:
    return dict(snapshot.to_dict() or {}) if bool(snapshot.exists) else {}


def _seed_payloads(identity: QaIdentity, *, now: float) -> dict[str, dict[str, Any]]:
    report_expires_at = float(now) - 1.0
    report_created_at = report_expires_at - REPORT_TTL_SECONDS
    report = _report_payload({
        "id": identity.report_id,
        "type_id": "quiet",
        "type_category": "status",
        "place": "Udine",
        "lat": 46.0626,
        "lon": 13.2346,
        "x": 50.0,
        "y": 50.0,
        "group_id": identity.group_id,
        "location_precision": "zone",
        "selected_place": "Udine",
        "owner_key": identity.client_key,
        "created_at": report_created_at,
        "expires_at": report_expires_at,
        "moderation_hidden": True,
        "moderation_hidden_at_timestamp": _datetime(now),
    })
    report[QA_MARKER_FIELD] = identity.marker

    cooldown = _cooldown_payload(
        identity.client_key,
        float(now) + COOLDOWN_TTL_SECONDS,
    )
    # The production helper uses the wall clock.  Pin the same timestamp type
    # to this run's single baseline so all six horizons are deterministic.
    cooldown["updated_at"] = _datetime(now)
    cooldown[QA_MARKER_FIELD] = identity.marker

    confirmation = _confirmation_payload(
        identity.group_id,
        {"yes": 0, "no": 0, "votes": {}},
        float(now) + CONFIRMATION_TTL_SECONDS,
    )
    confirmation["updated_at"] = _datetime(now)
    confirmation[QA_MARKER_FIELD] = identity.marker

    # This is the exact schema written by the real strict create/confirm/flag
    # transactions, but uses a unique QA document instead of a shared global
    # production window counter.
    rate_limit = {
        "count": 0,
        "expires_at_timestamp": _datetime(
            float(now) + RATE_LIMIT_TTL_SECONDS
        ),
        "updated_at": _datetime(now),
        "window": int(float(now) // 3600),
        QA_MARKER_FIELD: identity.marker,
    }
    reputation = {
        "owner_key": identity.client_key,
        "points": 0,
        "validated_reports": 0,
        "revoked_reports": 0,
        "daily_award_day": "",
        "daily_awards": 0,
        "updated_at": _datetime(now),
        "expires_at_timestamp": _datetime(
            float(now) + REPUTATION_RETENTION_SECONDS
        ),
        QA_MARKER_FIELD: identity.marker,
    }
    reputation_award = _reputation_award_payload(
        group_id=identity.group_id,
        owner_key=identity.client_key,
        status="capped",
        reason="qa_ttl_evidence",
        award_day="",
        now=float(now),
    )
    reputation_award["updated_at"] = _datetime(now)
    reputation_award[QA_MARKER_FIELD] = identity.marker
    return {
        "report": report,
        "cooldown": cooldown,
        "confirmation": confirmation,
        "rate_limit": rate_limit,
        "reputation": reputation,
        "reputation_award": reputation_award,
    }


def _timestamp(value: Any) -> float:
    if isinstance(value, datetime):
        return value.timestamp()
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _require_owned_seed(
    refs: dict[str, Any],
    identity: QaIdentity,
    *,
    now: float,
) -> None:
    stored: dict[str, dict[str, Any]] = {}
    for name, document in refs.items():
        snapshot = _snapshot(document)
        if not bool(snapshot.exists):
            raise CommunityTtlEvidenceSeedError("qa_seed_document_missing")
        payload = _payload(snapshot)
        if payload.get(QA_MARKER_FIELD) != identity.marker:
            raise CommunityTtlEvidenceSeedError("qa_document_ownership_lost")
        stored[name] = payload

    report = stored["report"]
    if (
        not bool(report.get("moderation_hidden"))
        or _timestamp(report.get("expires_at_timestamp")) >= float(now)
        or abs(
            _timestamp(report.get("expires_at_timestamp"))
            - _timestamp(report.get("created_at_timestamp"))
            - REPORT_TTL_SECONDS
        )
        > 0.001
    ):
        raise CommunityTtlEvidenceSeedError("qa_report_inert_ttl_invalid")

    horizons = {
        "cooldown": COOLDOWN_TTL_SECONDS,
        "confirmation": CONFIRMATION_TTL_SECONDS,
        "rate_limit": RATE_LIMIT_TTL_SECONDS,
        "reputation": REPUTATION_RETENTION_SECONDS,
        "reputation_award": REPUTATION_RETENTION_SECONDS,
    }
    for name, expected in horizons.items():
        payload = stored[name]
        if abs(
            _timestamp(payload.get("expires_at_timestamp"))
            - _timestamp(payload.get("updated_at"))
            - expected
        ) > 0.001:
            raise CommunityTtlEvidenceSeedError("qa_seed_ttl_invalid")


def _require_no_document_collision(refs: dict[str, Any]) -> None:
    if any(bool(_snapshot(document).exists) for document in refs.values()):
        raise CommunityTtlEvidenceSeedError("qa_document_collision")


def _create_seed_documents(
    db: Any,
    refs: dict[str, Any],
    identity: QaIdentity,
    *,
    now: float,
) -> None:
    payloads = _seed_payloads(identity, now=now)
    batch = db.batch()
    for name in (
        "report",
        "cooldown",
        "confirmation",
        "rate_limit",
        "reputation",
        "reputation_award",
    ):
        batch.create(refs[name], payloads[name])
    try:
        batch.commit()
    except Exception as error:
        raise CommunityTtlEvidenceSeedError("qa_atomic_create_failed") from error
    _require_owned_seed(refs, identity, now=now)


def _cleanup_owned_documents(
    db: Any,
    refs: dict[str, Any],
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
        snapshots = {
            name: _snapshot(document, transaction=transaction_in_progress)
            for name, document in refs.items()
        }
        for snapshot in snapshots.values():
            if (
                bool(snapshot.exists)
                and _payload(snapshot).get(QA_MARKER_FIELD) != identity.marker
            ):
                raise CommunityTtlEvidenceSeedError(
                    "qa_document_ownership_lost"
                )
        for name, snapshot in snapshots.items():
            if bool(snapshot.exists):
                transaction_in_progress.delete(refs[name])

    try:
        decorator(delete_if_still_owned)(transaction)
    except CommunityTtlEvidenceSeedError:
        raise
    except Exception as error:
        raise CommunityTtlEvidenceSeedError("qa_cleanup_transaction_failed") from error

    for document in refs.values():
        if bool(_snapshot(document).exists):
            raise CommunityTtlEvidenceSeedError("qa_cleanup_incomplete")


def _public_payload_contains_identity(
    payload: dict[str, Any],
    identity: QaIdentity,
) -> bool:
    rows: list[dict[str, Any]] = []
    for key in ("reports", "map_groups", "mapGroups", "groups"):
        rows.extend(
            item for item in list(payload.get(key) or []) if isinstance(item, dict)
        )
    for row in rows:
        if str(row.get("id") or "") == identity.report_id:
            return True
        if str(row.get("groupId") or row.get("group_id") or "") == identity.group_id:
            return True
        report_ids = list(row.get("reportIds") or row.get("report_ids") or [])
        if identity.report_id in {str(value) for value in report_ids}:
            return True
    return False


def _require_public_absence_via_service(
    db: Any,
    identity: QaIdentity,
    *,
    now: float,
) -> None:
    try:
        repository = CommunityRepository(
            lambda: db,
            storage_mode="firestore",
        )
        response = CommunityService(
            repository=repository,
            now=lambda: float(now),
        ).get_reports()
        payload = response.model_dump(by_alias=True)
    except Exception as error:
        raise CommunityTtlEvidenceSeedError(
            "public_service_probe_failed"
        ) from error
    if _public_payload_contains_identity(payload, identity):
        raise CommunityTtlEvidenceSeedError("public_report_visible")


def _require_public_absence_via_api(
    api_base: str,
    identity: QaIdentity,
    *,
    http_get: Callable[..., Any],
) -> None:
    try:
        response = http_get(
            f"{api_base}/community/reports",
            timeout=PUBLIC_API_TIMEOUT_SECONDS,
            headers={
                "Accept": "application/json",
                "Cache-Control": "no-cache",
            },
        )
        response.raise_for_status()
        payload = response.json()
    except Exception as error:
        raise CommunityTtlEvidenceSeedError("public_api_probe_failed") from error
    if not isinstance(payload, dict):
        raise CommunityTtlEvidenceSeedError("public_api_payload_invalid")
    if _public_payload_contains_identity(payload, identity):
        raise CommunityTtlEvidenceSeedError("public_report_visible")


def _default_public_probe(
    db: Any,
    api_base: str,
    *,
    http_get: Callable[..., Any],
) -> Callable[[str, QaIdentity, float], None]:
    def probe(_phase: str, identity: QaIdentity, now: float) -> None:
        _require_public_absence_via_service(
            db,
            identity,
            now=now,
        )
        _require_public_absence_via_api(
            api_base,
            identity,
            http_get=http_get,
        )

    return probe


def _call_public_probe(
    probe: Callable[[str, QaIdentity, float], None],
    phase: str,
    identity: QaIdentity,
    now: float,
) -> None:
    try:
        probe(phase, identity, float(now))
    except CommunityTtlEvidenceSeedError:
        raise
    except Exception as error:
        raise CommunityTtlEvidenceSeedError("public_absence_check_failed") from error


def _validated_hold_seconds(value: Any, *, apply: bool) -> int:
    try:
        selected = int(value)
    except (TypeError, ValueError) as error:
        raise CommunityTtlEvidenceSeedError("hold_seconds_invalid") from error
    if selected < 0 or selected > MAX_HOLD_SECONDS:
        raise CommunityTtlEvidenceSeedError("hold_seconds_out_of_bounds")
    if selected and not apply:
        raise CommunityTtlEvidenceSeedError("hold_seconds_requires_apply")
    return selected


def _ready_payload(*, hold_seconds: int, public_probe_count: int) -> dict[str, Any]:
    return {
        "event": "community_ttl_evidence_seed_ready",
        "project_id": EXPECTED_FIRESTORE_PROJECT_ID,
        "mode": "apply",
        "applied": True,
        "temporary_collection_count": 6,
        "expired_hidden_report_count": 1,
        "public_absence_check_count": int(public_probe_count),
        "hold_seconds": int(hold_seconds),
        "contains_document_identifiers": False,
        "contains_private_data": False,
    }


def _print_payload(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, ensure_ascii=True, sort_keys=True), flush=True)


def run_seed(
    db: Any,
    *,
    api_base: str,
    apply: bool,
    now: float | None = None,
    run_token: str | None = None,
    hold_seconds: int = 0,
    transactional_decorator: (
        Callable[[Callable[..., Any]], Callable[..., Any]] | None
    ) = None,
    evidence_emitter: Callable[[dict[str, Any]], None] | None = None,
    sleep_fn: Callable[[float], None] | None = None,
    public_probe: Callable[[str, QaIdentity, float], None] | None = None,
    http_get: Callable[..., Any] | None = None,
) -> dict[str, Any]:
    """Run a read-only preview or the marker-owned, TTL-bounded seed."""

    if str(getattr(db, "project", "") or "").strip() != EXPECTED_FIRESTORE_PROJECT_ID:
        raise CommunityTtlEvidenceSeedError("firestore_project_mismatch")
    normalized_api_base = _normalize_tagged_api_base(api_base)
    selected_hold = _validated_hold_seconds(hold_seconds, apply=apply)
    selected_now = float(now if now is not None else time.time())
    identity = _qa_identity(
        run_token or secrets.token_hex(12),
        now=selected_now,
    )
    refs = _document_refs(db, identity)
    probe = public_probe or _default_public_probe(
        db,
        normalized_api_base,
        http_get=http_get or requests.get,
    )
    try:
        _require_no_document_collision(refs)
        _call_public_probe(probe, "before", identity, selected_now)
    except CommunityTtlEvidenceSeedError:
        raise
    except Exception as error:
        raise CommunityTtlEvidenceSeedError("live_preflight_failed") from error

    if not apply:
        return {
            "event": "community_ttl_evidence_seed_preview",
            "project_id": EXPECTED_FIRESTORE_PROJECT_ID,
            "mode": "dry-run",
            "applied": False,
            "planned_temporary_collection_count": 6,
            "public_absence_check_count": 1,
            "hold_seconds": 0,
            "contains_document_identifiers": False,
            "contains_private_data": False,
        }

    write_attempted = False
    public_probe_count = 1
    result: dict[str, Any] | None = None
    operation_error: BaseException | None = None
    cleanup_error: BaseException | None = None
    final_public_error: BaseException | None = None
    try:
        # A lost commit acknowledgement can still mean all six atomic creates
        # succeeded, so marker-checked cleanup starts before the commit call.
        write_attempted = True
        _create_seed_documents(
            db,
            refs,
            identity,
            now=selected_now,
        )
        _call_public_probe(probe, "after_seed", identity, selected_now)
        public_probe_count += 1
        ready = _ready_payload(
            hold_seconds=selected_hold,
            public_probe_count=public_probe_count,
        )
        try:
            (evidence_emitter or _print_payload)(ready)
        except BaseException as error:
            raise CommunityTtlEvidenceSeedError(
                "evidence_ready_emit_failed"
            ) from error

        remaining = selected_hold
        while remaining > 0:
            interval = min(PUBLIC_PROBE_INTERVAL_SECONDS, remaining)
            try:
                (sleep_fn or time.sleep)(float(interval))
            except BaseException as error:
                raise CommunityTtlEvidenceSeedError("evidence_hold_failed") from error
            remaining -= interval
            _call_public_probe(probe, "during_hold", identity, selected_now)
            public_probe_count += 1

        result = {
            "event": "community_ttl_evidence_seed_completed",
            "project_id": EXPECTED_FIRESTORE_PROJECT_ID,
            "mode": "apply",
            "applied": True,
            "checks": {
                "atomic_create": True,
                "collision_guard": True,
                "expired_report": True,
                "moderation_hidden": True,
                "ttl_contract": True,
                "public_absence": True,
                "marker_owned_cleanup": True,
            },
            "temporary_collection_count": 6,
            "public_absence_check_count": public_probe_count + 1,
            "hold_seconds": selected_hold,
            "contains_document_identifiers": False,
            "contains_private_data": False,
        }
    except BaseException as error:
        operation_error = error
    finally:
        if write_attempted:
            try:
                _cleanup_owned_documents(
                    db,
                    refs,
                    identity,
                    transactional_decorator=transactional_decorator,
                )
            except BaseException as error:
                cleanup_error = error
        try:
            _call_public_probe(
                probe,
                "after_cleanup",
                identity,
                selected_now,
            )
        except BaseException as error:
            final_public_error = error

    if final_public_error is not None:
        if isinstance(final_public_error, CommunityTtlEvidenceSeedError):
            raise final_public_error
        raise CommunityTtlEvidenceSeedError("public_absence_check_failed") from final_public_error
    if cleanup_error is not None:
        if isinstance(cleanup_error, CommunityTtlEvidenceSeedError):
            raise cleanup_error
        raise CommunityTtlEvidenceSeedError("qa_cleanup_failed") from cleanup_error
    if operation_error is not None:
        if isinstance(operation_error, CommunityTtlEvidenceSeedError):
            raise operation_error
        raise CommunityTtlEvidenceSeedError("unexpected_operation_failure") from operation_error
    if result is None:
        raise CommunityTtlEvidenceSeedError("unexpected_operation_failure")
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
            "Seed LIVE fail-closed di sei campioni TTL Community; "
            "read-only di default."
        ),
    )
    parser.add_argument(
        "--api-base",
        required=True,
        help=(
            "Base /api HTTPS della revisione Cloud Run tagged da verificare "
            "sulla superficie pubblica."
        ),
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Crea i sei campioni temporanei marker-owned e li pulisce.",
    )
    parser.add_argument(
        "--hold-seconds",
        type=_parse_hold_seconds_argument,
        default=0,
        metavar="SECONDS",
        help=(
            "Con --apply, mantiene i campioni dopo evidence-ready per "
            f"0-{MAX_HOLD_SECONDS} secondi."
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
    public_probe: Callable[[str, QaIdentity, float], None] | None = None,
    http_get: Callable[..., Any] | None = None,
) -> int:
    selected_argv = list(argv) if argv is not None else sys.argv[1:]
    parser = build_parser()
    args = parser.parse_args(selected_argv)
    hold_was_explicit = any(
        value == "--hold-seconds" or value.startswith("--hold-seconds=")
        for value in selected_argv
    )
    if hold_was_explicit and not args.apply:
        parser.error("--hold-seconds e' valido solo insieme a --apply")
    try:
        selected_db = db if db is not None else get_firestore_client()
    except Exception:
        selected_db = None
    if selected_db is None:
        _print_payload({
            "event": "community_ttl_evidence_seed_failed",
            "status": "storage_unavailable",
            "applied": False,
            "contains_document_identifiers": False,
            "contains_private_data": False,
        })
        return 1

    try:
        result = run_seed(
            selected_db,
            api_base=args.api_base,
            apply=bool(args.apply),
            now=now,
            run_token=run_token,
            hold_seconds=int(args.hold_seconds),
            transactional_decorator=transactional_decorator,
            evidence_emitter=evidence_emitter,
            sleep_fn=sleep_fn,
            public_probe=public_probe,
            http_get=http_get,
        )
    except CommunityTtlEvidenceSeedError as error:
        _print_payload({
            "event": "community_ttl_evidence_seed_failed",
            "status": error.code,
            "applied": False,
            "contains_document_identifiers": False,
            "contains_private_data": False,
        })
        return 1
    except KeyboardInterrupt:
        _print_payload({
            "event": "community_ttl_evidence_seed_failed",
            "status": "interrupted",
            "applied": False,
            "contains_document_identifiers": False,
            "contains_private_data": False,
        })
        return 130
    except Exception:
        _print_payload({
            "event": "community_ttl_evidence_seed_failed",
            "status": "unexpected_failure",
            "applied": False,
            "contains_document_identifiers": False,
            "contains_private_data": False,
        })
        return 1

    _print_payload(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
