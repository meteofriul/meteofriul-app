"""Synchronous, fail-closed Cloud Logging delivery for moderation digests."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Any


EXPECTED_PROJECT_ID = "meteo-friul"
LOG_ID = "meteofriul-community-moderation-digest"
LOG_NAME = f"projects/{EXPECTED_PROJECT_ID}/logs/{LOG_ID}"
LOGGING_WRITE_URL = "https://logging.googleapis.com/v2/entries:write"
LOGGING_WRITE_SCOPE = "https://www.googleapis.com/auth/logging.write"
LOGGING_WRITE_TIMEOUT_SECONDS = 15
MAX_READY_EVENT_BYTES = 200_000
DIGEST_ID_PATTERN = re.compile(r"^[0-9a-f]{64}$")
READY_EVENT_FIELDS = frozenset(
    {
        "status",
        "should_emit",
        "digest_id",
        "created_at",
        "delivery_slot",
        "new_group_count",
        "new_flag_count",
        "groups",
        "event",
        "severity",
        "notification_transport",
        "delivery_semantics",
        "dedupe_field",
        "email_delivery_confirmed",
        "contains_private_keys",
        "contains_gps",
    }
)
READY_GROUP_FIELDS = frozenset(
    {
        "group_ref",
        "flag_count",
        "report_count",
        "source_count",
        "reasons",
        "expires_at",
    }
)
ALLOWED_REASONS = frozenset({"inaccurate", "duplicate", "misuse"})
GROUP_REFERENCE_PATTERN = re.compile(r"^[0-9a-f]{24}$")
MAX_GROUPS = 200
MAX_FLAGS_PER_GROUP = 50
MAX_REPORTS_PER_GROUP = 200


class CommunityModerationLoggingError(RuntimeError):
    """A non-sensitive failure raised before digest acknowledgement."""


def _validated_timestamp(value: Any) -> str:
    try:
        selected = datetime.fromisoformat(str(value or ""))
        if selected.tzinfo is None:
            raise ValueError("timezone_missing")
        return selected.astimezone(timezone.utc).isoformat().replace(
            "+00:00", "Z"
        )
    except (TypeError, ValueError) as error:
        raise CommunityModerationLoggingError(
            "logging_ready_timestamp_invalid"
        ) from error


def _validated_count(value: Any, *, maximum: int) -> int:
    if isinstance(value, bool):
        raise CommunityModerationLoggingError("logging_ready_event_invalid")
    try:
        selected = int(value)
    except (TypeError, ValueError) as error:
        raise CommunityModerationLoggingError(
            "logging_ready_event_invalid"
        ) from error
    if selected < 0 or selected > maximum:
        raise CommunityModerationLoggingError("logging_ready_event_invalid")
    return selected


def _validated_group(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != READY_GROUP_FIELDS:
        raise CommunityModerationLoggingError("logging_ready_privacy_invalid")
    group_ref = str(value.get("group_ref") or "")
    if GROUP_REFERENCE_PATTERN.fullmatch(group_ref) is None:
        raise CommunityModerationLoggingError("logging_ready_event_invalid")
    flag_count = _validated_count(
        value.get("flag_count"), maximum=MAX_FLAGS_PER_GROUP
    )
    report_count = _validated_count(
        value.get("report_count"), maximum=MAX_REPORTS_PER_GROUP
    )
    source_count = _validated_count(
        value.get("source_count"), maximum=MAX_REPORTS_PER_GROUP
    )
    reasons = value.get("reasons")
    if not isinstance(reasons, dict) or set(reasons) - ALLOWED_REASONS:
        raise CommunityModerationLoggingError("logging_ready_event_invalid")
    normalized_reasons = {
        str(reason): _validated_count(count, maximum=MAX_FLAGS_PER_GROUP)
        for reason, count in sorted(reasons.items())
    }
    if sum(normalized_reasons.values()) != flag_count:
        raise CommunityModerationLoggingError("logging_ready_event_invalid")
    return {
        "group_ref": group_ref,
        "flag_count": flag_count,
        "report_count": report_count,
        "source_count": source_count,
        "reasons": normalized_reasons,
        "expires_at": _validated_timestamp(value.get("expires_at")),
    }


def build_ready_log_request(event: dict[str, Any]) -> dict[str, Any]:
    """Validate one sanitized ready event and build an immutable log entry."""

    if not isinstance(event, dict) or set(event) != READY_EVENT_FIELDS:
        raise CommunityModerationLoggingError("logging_ready_event_invalid")
    if (
        event.get("event") != "community_moderation_digest_ready"
        or event.get("status") != "ready"
        or event.get("should_emit") is not True
        or event.get("severity") != "WARNING"
        or event.get("notification_transport")
        != "cloud_logging_entries_write_pending_monitoring_configuration"
        or event.get("delivery_semantics")
        != "at_least_once_logging_acceptance"
        or event.get("dedupe_field") != "digest_id"
        or event.get("email_delivery_confirmed") is not False
    ):
        raise CommunityModerationLoggingError("logging_ready_event_invalid")
    digest_id = str(event.get("digest_id") or "")
    if DIGEST_ID_PATTERN.fullmatch(digest_id) is None:
        raise CommunityModerationLoggingError("logging_ready_digest_id_invalid")
    if event.get("contains_private_keys") is not False:
        raise CommunityModerationLoggingError("logging_ready_privacy_invalid")
    if event.get("contains_gps") is not False:
        raise CommunityModerationLoggingError("logging_ready_privacy_invalid")
    timestamp = _validated_timestamp(event.get("created_at"))
    delivery_slot = str(event.get("delivery_slot") or "")
    if re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}:(?:am|pm)", delivery_slot) is None:
        raise CommunityModerationLoggingError("logging_ready_event_invalid")
    raw_groups = event.get("groups")
    if not isinstance(raw_groups, list) or len(raw_groups) > MAX_GROUPS:
        raise CommunityModerationLoggingError("logging_ready_event_invalid")
    groups = [_validated_group(group) for group in raw_groups]
    if len({group["group_ref"] for group in groups}) != len(groups):
        raise CommunityModerationLoggingError("logging_ready_event_invalid")
    new_group_count = _validated_count(
        event.get("new_group_count"), maximum=MAX_GROUPS
    )
    new_flag_count = _validated_count(
        event.get("new_flag_count"), maximum=MAX_GROUPS * MAX_FLAGS_PER_GROUP
    )
    if new_group_count != len(groups) or new_flag_count > sum(
        group["flag_count"] for group in groups
    ):
        raise CommunityModerationLoggingError("logging_ready_event_invalid")
    canonical_event = {
        **{key: event[key] for key in READY_EVENT_FIELDS - {"groups"}},
        "created_at": timestamp,
        "delivery_slot": delivery_slot,
        "new_group_count": new_group_count,
        "new_flag_count": new_flag_count,
        "groups": groups,
    }
    try:
        encoded = json.dumps(
            canonical_event,
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    except (TypeError, ValueError) as error:
        raise CommunityModerationLoggingError(
            "logging_ready_event_invalid"
        ) from error
    if len(encoded) > MAX_READY_EVENT_BYTES:
        raise CommunityModerationLoggingError("logging_ready_event_too_large")

    return {
        "logName": LOG_NAME,
        "resource": {
            "type": "global",
            "labels": {"project_id": EXPECTED_PROJECT_ID},
        },
        "entries": [
            {
                "jsonPayload": canonical_event,
                "severity": "WARNING",
                # The same pending digest always keeps both fields stable.
                # Cloud Logging treats equal project/timestamp/insertId values
                # as duplicates in query results. Exports still need their own
                # downstream deduplication.
                "insertId": digest_id,
                "timestamp": timestamp,
            }
        ],
        "partialSuccess": False,
    }


def publish_ready_event(
    event: dict[str, Any],
    *,
    session: Any | None = None,
) -> dict[str, Any]:
    """Synchronously obtain Logging API acceptance for one ready event."""

    request = build_ready_log_request(event)
    selected_session = session
    if selected_session is None:
        import google.auth
        from google.auth.transport.requests import AuthorizedSession

        try:
            credentials, project_id = google.auth.default(
                scopes=[LOGGING_WRITE_SCOPE]
            )
        except Exception as error:
            raise CommunityModerationLoggingError(
                "logging_auth_unavailable"
            ) from error
        if str(project_id or "") != EXPECTED_PROJECT_ID:
            raise CommunityModerationLoggingError(
                "logging_project_mismatch"
            )
        selected_session = AuthorizedSession(credentials)

    try:
        response = selected_session.post(
            LOGGING_WRITE_URL,
            json=request,
            timeout=LOGGING_WRITE_TIMEOUT_SECONDS,
        )
    except Exception as error:
        raise CommunityModerationLoggingError(
            "logging_write_unavailable"
        ) from error
    if int(getattr(response, "status_code", 0) or 0) != 200:
        raise CommunityModerationLoggingError("logging_write_rejected")
    return {
        "status": "accepted",
        "digest_id": str(event["digest_id"]),
        "log_name": LOG_NAME,
    }
