"""Write a moderation digest synchronously to Cloud Logging, then ack it."""

from __future__ import annotations

import argparse
import json
import time
from typing import Any, Callable

from app.infrastructure.firebase import get_firestore_client
from app.services.community_moderation_digest import (
    CommunityModerationDigestError,
    acknowledge_moderation_digest,
    produce_moderation_digest,
)
from app.services.community_moderation_logging import (
    CommunityModerationLoggingError,
    publish_ready_event,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Produce il riepilogo privato della moderazione Territorio."
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Registra la deduplicazione ed emette l'evento consegnabile.",
    )
    return parser


def _event(result: dict[str, Any], *, apply: bool) -> dict[str, Any]:
    # A reused pending item must be emitted again. This is the deliberate
    # at-least-once side of the outbox: every retry carries the same digest_id.
    emitted = bool(apply and result.get("should_emit"))
    event = (
        "community_moderation_digest_ready"
        if emitted
        else (
            "community_moderation_digest_preview"
            if not apply
            else "community_moderation_digest_completed"
        )
    )
    if emitted:
        public_result = {
            key: result[key]
            for key in (
                "status",
                "should_emit",
                "digest_id",
                "created_at",
                "delivery_slot",
                "new_group_count",
                "new_flag_count",
                "groups",
            )
        }
    else:
        public_result = dict(result)
    if apply and not emitted:
        # Scheduled throttled/no-op executions may expose only aggregate
        # counters. The actionable group list belongs exclusively to the one
        # ready transition (or to an explicit operator preview), avoiding
        # repeated retention of the same moderation details in Cloud Logging.
        public_result.pop("groups", None)
    return {
        **public_result,
        "event": event,
        "severity": "WARNING" if emitted else "INFO",
        # The ready entry is written synchronously through entries.write.
        # Monitoring/email remains a separate, explicitly blocked transport.
        "notification_transport": (
            "cloud_logging_entries_write_pending_monitoring_configuration"
            if emitted
            else "none"
        ),
        "delivery_semantics": (
            "at_least_once_logging_acceptance" if emitted else "none"
        ),
        "dedupe_field": "digest_id" if emitted else None,
        "email_delivery_confirmed": False,
        "contains_private_keys": False,
        "contains_gps": False,
    }


def _failure_event(status: str, *, acknowledgement: bool = False) -> dict[str, Any]:
    return {
        "event": (
            "community_moderation_digest_ack_failed"
            if acknowledgement
            else "community_moderation_digest_failed"
        ),
        "severity": "ERROR",
        "status": status,
        "notification_transport": "cloud_monitoring_job_failure",
        "contains_private_keys": False,
        "contains_gps": False,
    }


def main(
    argv: list[str] | None = None,
    *,
    now: float | None = None,
    db: Any | None = None,
    transactional_decorator: Any | None = None,
    ready_event_publisher: (
        Callable[[dict[str, Any]], dict[str, Any]] | None
    ) = None,
    clock: Callable[[], float] | None = None,
) -> int:
    args = build_parser().parse_args(argv)
    selected_db = db if db is not None else get_firestore_client()
    if selected_db is None:
        payload = _failure_event("storage_unavailable")
        print(
            json.dumps(payload, ensure_ascii=True, sort_keys=True),
            flush=True,
        )
        return 1

    selected_clock = clock or time.time
    selected_now = float(now if now is not None else selected_clock())
    try:
        result = produce_moderation_digest(
            selected_db,
            now=selected_now,
            apply=bool(args.apply),
            transactional_decorator=transactional_decorator,
        )
    except CommunityModerationDigestError as error:
        payload = _failure_event(str(error).split(":", 1)[0])
        print(
            json.dumps(payload, ensure_ascii=True, sort_keys=True),
            flush=True,
        )
        return 1
    except Exception:
        payload = _failure_event("unexpected_failure")
        print(
            json.dumps(payload, ensure_ascii=True, sort_keys=True),
            flush=True,
        )
        return 1

    event = _event(result, apply=bool(args.apply))
    if bool(args.apply) and bool(result.get("should_emit")):
        try:
            receipt = (ready_event_publisher or publish_ready_event)(event)
            if (
                str(receipt.get("status") or "") != "accepted"
                or str(receipt.get("digest_id") or "")
                != str(result.get("digest_id") or "")
            ):
                raise CommunityModerationLoggingError(
                    "logging_acceptance_invalid"
                )
        except CommunityModerationLoggingError as error:
            print(
                json.dumps(
                    _failure_event(str(error).split(":", 1)[0]),
                    ensure_ascii=True,
                    sort_keys=True,
                ),
                flush=True,
            )
            return 1
        except Exception:
            print(
                json.dumps(
                    _failure_event("logging_write_unexpected_failure"),
                    ensure_ascii=True,
                    sort_keys=True,
                ),
                flush=True,
            )
            return 1
        try:
            acknowledgement = acknowledge_moderation_digest(
                selected_db,
                digest_id=str(result.get("digest_id") or ""),
                # Delivery can cross noon or midnight while waiting for the
                # synchronous Logging API. Consume the slot of the actual
                # acceptance, not the earlier claim.
                now=float(selected_clock()),
                transactional_decorator=transactional_decorator,
            )
        except CommunityModerationDigestError as error:
            print(
                json.dumps(
                    _failure_event(
                        str(error).split(":", 1)[0],
                        acknowledgement=True,
                    ),
                    ensure_ascii=True,
                    sort_keys=True,
                ),
                flush=True,
            )
            return 1
        except Exception:
            print(
                json.dumps(
                    _failure_event(
                        "unexpected_ack_failure",
                        acknowledgement=True,
                    ),
                    ensure_ascii=True,
                    sort_keys=True,
                ),
                flush=True,
            )
            return 1
        print(
            json.dumps(
                {
                    "event": "community_moderation_digest_completed",
                    "severity": "INFO",
                    "status": "logging_accepted_and_acknowledged",
                    "digest_id": str(result.get("digest_id") or ""),
                    "delivery_slot": str(
                        acknowledgement.get("delivery_slot") or ""
                    ),
                    "logging_accepted": True,
                    "acknowledged": bool(
                        acknowledgement.get("acknowledged")
                        or acknowledgement.get("status")
                        == "already_acknowledged"
                    ),
                    "email_delivery_confirmed": False,
                    "contains_private_keys": False,
                    "contains_gps": False,
                },
                ensure_ascii=True,
                sort_keys=True,
            ),
            flush=True,
        )
        return 0

    print(json.dumps(event, ensure_ascii=True, sort_keys=True), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
