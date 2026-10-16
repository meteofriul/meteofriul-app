from __future__ import annotations

import calendar
import copy
import hashlib
import json
import os
from datetime import date as calendar_date
from datetime import datetime, timedelta, timezone
from threading import RLock
from typing import Any, Callable
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo


ADMIN_COLLECTION = "promotion_admin_state"
ADMIN_DOCUMENT = "current"
METRICS_COLLECTION = "promotion_daily_metrics"
CATALOG_MAX_AGE_SECONDS = 300
PUBLIC_CATALOG_SCHEMA_VERSION = 2
ROTATION_INTERVAL_SECONDS = 120
ROTATION_SESSION_MINUTES = ROTATION_INTERVAL_SECONDS // 60
ROTATION_INTERVAL_OPTIONS = frozenset({30, 60, 120, 300})
MAX_CAMPAIGNS = 200
MAX_STATE_BYTES = 1_000_000
PLACEMENTS = frozenset({"home", "events", "discover"})
STATUSES = frozenset({"draft", "scheduled", "active", "paused", "archived"})
RESERVING_STATUSES = frozenset({"scheduled", "active", "paused"})
BOOKING_MODES = frozenset({"exclusive", "mixed", "rotation"})
EVENT_TYPES = frozenset({"impression", "open"})
ROME = ZoneInfo("Europe/Rome")
MAX_ROTATION_SPONSORS = 5
MAX_AVAILABILITY_DAYS = 93
MINUTES_PER_DAY = 24 * 60


class PromotionStateConflict(RuntimeError):
    pass


class PromotionAvailabilityConflict(PromotionStateConflict):
    def __init__(
        self,
        *,
        page: str,
        day: str,
        start_time: str,
        end_time: str,
        occupying_campaign: dict[str, Any],
    ) -> None:
        super().__init__("promotion_availability_conflict")
        self.page = page
        self.day = day
        self.start_time = start_time
        self.end_time = end_time
        self.occupying_campaign_id = str(occupying_campaign.get("id") or "")
        self.occupying_campaign_title = str(
            occupying_campaign.get("businessName")
            or occupying_campaign.get("title")
            or self.occupying_campaign_id
        )

    def as_detail(self) -> dict[str, Any]:
        return {
            "code": str(self),
            "page": self.page,
            "date": self.day,
            "startTime": self.start_time,
            "endTime": self.end_time,
            "occupyingCampaignId": self.occupying_campaign_id,
            "occupyingCampaignTitle": self.occupying_campaign_title,
        }


class PromotionStorageUnavailable(RuntimeError):
    pass


class PromotionValidationError(ValueError):
    pass


def _now_iso(now: datetime | None = None) -> str:
    selected = now or datetime.now(timezone.utc)
    return selected.astimezone(timezone.utc).isoformat()


def default_admin_state() -> dict[str, Any]:
    return {
        "adsEnabled": False,
        "placementEnabled": {
            "home": True,
            "events": True,
            "discover": True,
        },
        "placementRotationIntervals": {
            placement: ROTATION_INTERVAL_SECONDS for placement in sorted(PLACEMENTS)
        },
        # Kept in the admin payload for backwards compatibility. Delivery is
        # governed by the per-placement intervals above.
        "sessionMinutes": ROTATION_SESSION_MINUTES,
        "maxAdsPerDay": 2,
        "maxAdvertiserPerDay": 1,
        "issuer": {},
        "campaigns": [],
    }


def default_public_catalog() -> dict[str, Any]:
    return {
        "schemaVersion": PUBLIC_CATALOG_SCHEMA_VERSION,
        "enabled": False,
        "revision": 0,
        "generatedAt": _now_iso(),
        "maxAgeSeconds": CATALOG_MAX_AGE_SECONDS,
        "timezone": "Europe/Rome",
        "placements": sorted(PLACEMENTS),
        "placementRotationIntervals": {
            placement: ROTATION_INTERVAL_SECONDS for placement in sorted(PLACEMENTS)
        },
        "rotationIntervalSeconds": ROTATION_INTERVAL_SECONDS,
        "maxRotationCampaigns": MAX_ROTATION_SPONSORS,
        "dailyCap": 0,
        "campaigns": [],
    }


def _bounded_text(value: Any, maximum: int) -> str:
    return str(value or "").strip()[:maximum]


def _bounded_int(value: Any, minimum: int, maximum: int, fallback: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return fallback
    return min(maximum, max(minimum, parsed))


def _https_url(value: Any, *, required: bool = False) -> str:
    selected = _bounded_text(value, 2_000)
    if not selected and not required:
        return ""
    parsed = urlsplit(selected)
    if (
        parsed.scheme != "https"
        or not parsed.netloc
        or parsed.username
        or parsed.password
    ):
        raise PromotionValidationError("promotion_https_url_required")
    return selected


def _date(value: Any) -> str:
    selected = _bounded_text(value, 10)
    if not selected:
        return ""
    try:
        datetime.strptime(selected, "%Y-%m-%d")
    except ValueError as error:
        raise PromotionValidationError("promotion_date_invalid") from error
    return selected


def _time(value: Any, *, allow_end_of_day: bool = False) -> str:
    selected = _bounded_text(value, 5)
    if not selected:
        return ""
    if allow_end_of_day and selected == "24:00":
        return selected
    try:
        parsed = datetime.strptime(selected, "%H:%M")
    except ValueError as error:
        raise PromotionValidationError("promotion_time_invalid") from error
    if parsed.strftime("%H:%M") != selected:
        raise PromotionValidationError("promotion_time_invalid")
    return selected


def _time_to_minutes(value: str, *, fallback: int) -> int:
    if not value:
        return fallback
    if value == "24:00":
        return MINUTES_PER_DAY
    hours, minutes = value.split(":", 1)
    return int(hours) * 60 + int(minutes)


def _minutes_to_time(value: int) -> str:
    if value == MINUTES_PER_DAY:
        return "24:00"
    return f"{value // 60:02d}:{value % 60:02d}"


def _placements(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return list(dict.fromkeys(
        str(item).strip().lower()
        for item in value
        if str(item).strip().lower() in PLACEMENTS
    ))


def _placement_rotation_intervals(value: Any) -> dict[str, int]:
    source = value if isinstance(value, dict) else {}
    normalized = {}
    for placement in sorted(PLACEMENTS):
        try:
            interval = int(source.get(placement, ROTATION_INTERVAL_SECONDS))
        except (TypeError, ValueError):
            interval = ROTATION_INTERVAL_SECONDS
        normalized[placement] = (
            interval
            if interval in ROTATION_INTERVAL_OPTIONS
            else ROTATION_INTERVAL_SECONDS
        )
    return normalized


def _placement_assignments(
    value: Any,
    placements: list[str],
    *,
    legacy_mode: str,
) -> dict[str, dict[str, Any]]:
    source = value if isinstance(value, dict) else {}
    fallback_mode = "rotation" if legacy_mode == "rotation" else "exclusive"
    normalized = {}
    for placement in placements:
        explicit = source.get(placement)
        if explicit is not None and not isinstance(explicit, dict):
            raise PromotionValidationError("promotion_placement_assignment_invalid")
        raw_mode = _bounded_text((explicit or {}).get("mode"), 20).lower()
        if legacy_mode == "mixed" and not raw_mode:
            raise PromotionValidationError("promotion_placement_assignment_invalid")
        if raw_mode and raw_mode not in {"exclusive", "rotation"}:
            raise PromotionValidationError("promotion_placement_assignment_invalid")
        try:
            card_number = int((explicit or {}).get("cardNumber", 1))
        except (TypeError, ValueError) as error:
            raise PromotionValidationError(
                "promotion_placement_assignment_invalid"
            ) from error
        if card_number != 1:
            raise PromotionValidationError("promotion_placement_assignment_invalid")
        normalized[placement] = {
            "cardNumber": 1,
            "mode": raw_mode or fallback_mode,
        }
    return normalized


def _campaign_placement_mode(campaign: dict[str, Any], placement: str) -> str:
    assignment = dict(campaign.get("placementAssignments") or {}).get(placement)
    if isinstance(assignment, dict) and assignment.get("mode") in {
        "exclusive",
        "rotation",
    }:
        return str(assignment["mode"])
    return "rotation" if campaign.get("bookingMode") == "rotation" else "exclusive"


def _card_details(value: Any) -> list[str]:
    if not isinstance(value, list):
        return ["city"]
    allowed = {"address", "category", "city"}
    return list(dict.fromkeys(
        str(item).strip().lower()
        for item in value
        if str(item).strip().lower() in allowed
    ))


def _sanitize_campaign(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise PromotionValidationError("promotion_campaign_invalid")
    image_data = _bounded_text(value.get("imageDataUrl"), 32)
    if image_data:
        raise PromotionValidationError("promotion_base64_image_forbidden")
    campaign_id = _bounded_text(value.get("id"), 120)
    if not campaign_id:
        raise PromotionValidationError("promotion_campaign_id_required")
    status = _bounded_text(value.get("status"), 20).lower() or "draft"
    if status not in STATUSES:
        raise PromotionValidationError("promotion_status_invalid")
    raw_booking_mode = _bounded_text(
        value.get("bookingMode")
        or value.get("availabilityMode")
        or value.get("deliveryMode"),
        20,
    ).lower()
    if raw_booking_mode and raw_booking_mode not in BOOKING_MODES | {"all_selected"}:
        raise PromotionValidationError("promotion_booking_mode_invalid")
    placements = _placements(value.get("placements"))
    placement_assignments = _placement_assignments(
        value.get("placementAssignments"),
        placements,
        legacy_mode=raw_booking_mode,
    )
    assignment_modes = {
        assignment["mode"] for assignment in placement_assignments.values()
    }
    if len(assignment_modes) == 1:
        booking_mode = next(iter(assignment_modes))
    elif assignment_modes:
        booking_mode = "mixed"
    else:
        booking_mode = "rotation" if raw_booking_mode == "rotation" else "exclusive"
    schedule_mode = _bounded_text(value.get("scheduleMode"), 20).lower() or "period"
    if schedule_mode not in {"period", "days", "month"}:
        raise PromotionValidationError("promotion_schedule_invalid")
    active_dates = sorted(set(
        _date(item) for item in (value.get("activeDates") or []) if item
    ))
    campaign = copy.deepcopy(value)
    active_month = _bounded_text(value.get("activeMonth"), 7)
    if active_month:
        try:
            datetime.strptime(active_month, "%Y-%m")
        except ValueError as error:
            raise PromotionValidationError("promotion_month_invalid") from error
    start_time = _time(value.get("startTime"))
    end_time = _time(value.get("endTime"), allow_end_of_day=True)
    start_minutes = _time_to_minutes(start_time, fallback=0)
    end_minutes = _time_to_minutes(end_time, fallback=MINUTES_PER_DAY)
    if end_minutes <= start_minutes:
        raise PromotionValidationError("promotion_time_period_invalid")
    campaign.update({
        "id": campaign_id,
        "status": status,
        "businessName": _bounded_text(value.get("businessName"), 160),
        "businessAddress": _bounded_text(value.get("businessAddress"), 240),
        "city": _bounded_text(value.get("city"), 120),
        "category": _bounded_text(value.get("category"), 120),
        "title": _bounded_text(value.get("title"), 80),
        "description": _bounded_text(value.get("description"), 180),
        "cardDetails": _card_details(value.get("cardDetails")),
        "ctaLabel": _bounded_text(value.get("ctaLabel"), 50) or "Scopri l’attività",
        "destinationUrl": _https_url(value.get("destinationUrl")),
        "imageUrl": _https_url(value.get("imageUrl")),
        "imageDataUrl": "",
        "placements": placements,
        "placementAssignments": placement_assignments,
        "deliveryMode": "all_selected",
        "bookingMode": booking_mode,
        "scheduleMode": schedule_mode,
        "activeDates": active_dates,
        "activeMonth": active_month,
        "startDate": _date(value.get("startDate")),
        "endDate": _date(value.get("endDate")),
        "startTime": start_time,
        "endTime": end_time,
        "maxPerDay": _bounded_int(value.get("maxPerDay"), 1, 10, 1),
    })
    if status in RESERVING_STATUSES:
        if schedule_mode == "days" and not campaign["activeDates"]:
            raise PromotionValidationError("promotion_active_schedule_incomplete")
        if schedule_mode == "month" and not campaign["activeMonth"]:
            raise PromotionValidationError("promotion_active_schedule_incomplete")
        if (
            schedule_mode == "period"
            and campaign["startDate"]
            and campaign["endDate"]
            and campaign["endDate"] < campaign["startDate"]
        ):
            raise PromotionValidationError("promotion_period_invalid")
    if status == "active":
        required = (
            campaign["businessName"],
            campaign["city"],
            campaign["title"],
            campaign["description"],
            campaign["destinationUrl"],
            campaign["imageUrl"],
        )
        if not all(required) or not campaign["placements"]:
            raise PromotionValidationError("promotion_active_campaign_incomplete")
    return campaign


def sanitize_admin_state(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise PromotionValidationError("promotion_state_invalid")
    raw_campaigns = value.get("campaigns") or []
    if not isinstance(raw_campaigns, list) or len(raw_campaigns) > MAX_CAMPAIGNS:
        raise PromotionValidationError("promotion_campaign_limit_exceeded")
    placements = value.get("placementEnabled") or {}
    sanitized_campaigns = [_sanitize_campaign(item) for item in raw_campaigns]
    campaign_ids = [campaign["id"] for campaign in sanitized_campaigns]
    if len(campaign_ids) != len(set(campaign_ids)):
        raise PromotionValidationError("promotion_campaign_id_duplicate")
    state = copy.deepcopy(value)
    state.update({
        "adsEnabled": value.get("adsEnabled") is True,
        "placementEnabled": {
            placement: placements.get(placement) is not False
            for placement in sorted(PLACEMENTS)
        },
        "placementRotationIntervals": _placement_rotation_intervals(
            value.get("placementRotationIntervals")
        ),
        # Older panel snapshots stored configurable 10-60 minute sessions.
        # Keep their legacy field fixed while per-placement delivery uses the
        # normalized intervals above.
        "sessionMinutes": ROTATION_SESSION_MINUTES,
        "maxAdsPerDay": _bounded_int(value.get("maxAdsPerDay"), 0, 20, 2),
        "maxAdvertiserPerDay": _bounded_int(
            value.get("maxAdvertiserPerDay"), 0, 20, 1
        ),
        "issuer": copy.deepcopy(value.get("issuer") or {}),
        "campaigns": sanitized_campaigns,
    })
    encoded = json.dumps(state, ensure_ascii=False, separators=(",", ":")).encode()
    if len(encoded) > MAX_STATE_BYTES:
        raise PromotionValidationError("promotion_state_too_large")
    return state


def _campaign_reserves(campaign: dict[str, Any]) -> bool:
    return campaign.get("status") in RESERVING_STATUSES


def _campaign_time_range(campaign: dict[str, Any]) -> tuple[int, int]:
    return (
        _time_to_minutes(str(campaign.get("startTime") or ""), fallback=0),
        _time_to_minutes(
            str(campaign.get("endTime") or ""),
            fallback=MINUTES_PER_DAY,
        ),
    )


def _month_bounds(value: str) -> tuple[calendar_date, calendar_date]:
    first = datetime.strptime(f"{value}-01", "%Y-%m-%d").date()
    last = first.replace(day=calendar.monthrange(first.year, first.month)[1])
    return first, last


def _campaign_date_bounds(
    campaign: dict[str, Any],
) -> tuple[calendar_date, calendar_date] | None:
    mode = campaign.get("scheduleMode") or "period"
    if mode == "days":
        dates = [
            datetime.strptime(item, "%Y-%m-%d").date()
            for item in campaign.get("activeDates") or []
        ]
        return (min(dates), max(dates)) if dates else None
    if mode == "month":
        month = str(campaign.get("activeMonth") or "")
        return _month_bounds(month) if month else None
    start = str(campaign.get("startDate") or "")
    end = str(campaign.get("endDate") or "")
    return (
        datetime.strptime(start, "%Y-%m-%d").date() if start else calendar_date.min,
        datetime.strptime(end, "%Y-%m-%d").date() if end else calendar_date.max,
    )


def _campaign_reserves_on(campaign: dict[str, Any], day: calendar_date) -> bool:
    if not _campaign_reserves(campaign):
        return False
    selected = day.isoformat()
    mode = campaign.get("scheduleMode") or "period"
    if mode == "days":
        return selected in set(campaign.get("activeDates") or [])
    if mode == "month":
        month = str(campaign.get("activeMonth") or "")
        return bool(month) and selected.startswith(f"{month}-")
    start = str(campaign.get("startDate") or "")
    end = str(campaign.get("endDate") or "")
    return (not start or selected >= start) and (not end or selected <= end)


def _first_shared_date(
    left: dict[str, Any],
    right: dict[str, Any],
) -> calendar_date | None:
    left_mode = left.get("scheduleMode") or "period"
    right_mode = right.get("scheduleMode") or "period"
    if left_mode == "days":
        for item in left.get("activeDates") or []:
            day = datetime.strptime(item, "%Y-%m-%d").date()
            if _campaign_reserves_on(right, day):
                return day
        return None
    if right_mode == "days":
        return _first_shared_date(right, left)
    left_bounds = _campaign_date_bounds(left)
    right_bounds = _campaign_date_bounds(right)
    if left_bounds is None or right_bounds is None:
        return None
    first = max(left_bounds[0], right_bounds[0])
    last = min(left_bounds[1], right_bounds[1])
    if first > last:
        return None
    if first == calendar_date.min:
        today = datetime.now(ROME).date()
        return min(max(today, first), last)
    return first


def _candidate_overlap_dates(campaigns: list[dict[str, Any]]) -> set[calendar_date]:
    result = {datetime.now(ROME).date()}
    for campaign in campaigns:
        if not _campaign_reserves(campaign):
            continue
        if (campaign.get("scheduleMode") or "period") == "days":
            result.update(
                datetime.strptime(item, "%Y-%m-%d").date()
                for item in campaign.get("activeDates") or []
            )
            continue
        bounds = _campaign_date_bounds(campaign)
        if bounds is not None:
            if bounds[0] != calendar_date.min:
                result.add(bounds[0])
            if bounds[1] != calendar_date.max:
                result.add(bounds[1])
    return result


def _availability_conflict(
    campaigns: list[dict[str, Any]],
    *,
    required_campaign_ids: set[str] | None = None,
    preferred_occupant_ids: set[str] | None = None,
) -> PromotionAvailabilityConflict | None:
    reserving = [campaign for campaign in campaigns if _campaign_reserves(campaign)]
    required = required_campaign_ids or set()
    preferred = preferred_occupant_ids or set()

    for index, left in enumerate(reserving):
        for right in reserving[index + 1:]:
            involved = {str(left.get("id") or ""), str(right.get("id") or "")}
            if required and not involved.intersection(required):
                continue
            shared_pages = sorted(
                set(left.get("placements") or []).intersection(
                    right.get("placements") or []
                )
            )
            if not shared_pages:
                continue
            day = _first_shared_date(left, right)
            if day is None:
                continue
            left_start, left_end = _campaign_time_range(left)
            right_start, right_end = _campaign_time_range(right)
            overlap_start = max(left_start, right_start)
            overlap_end = min(left_end, right_end)
            if overlap_start >= overlap_end:
                continue
            for page in shared_pages:
                if (
                    _campaign_placement_mode(left, page) != "exclusive"
                    and _campaign_placement_mode(right, page) != "exclusive"
                ):
                    continue
                occupant = right
                if str(left.get("id") or "") in preferred:
                    occupant = left
                elif str(right.get("id") or "") in preferred:
                    occupant = right
                return PromotionAvailabilityConflict(
                    page=page,
                    day=day.isoformat(),
                    start_time=_minutes_to_time(overlap_start),
                    end_time=_minutes_to_time(overlap_end),
                    occupying_campaign=occupant,
                )

    for page in sorted(PLACEMENTS):
        page_campaigns = [
            campaign
            for campaign in reserving
            if page in (campaign.get("placements") or [])
            and _campaign_placement_mode(campaign, page) == "rotation"
        ]
        for day in sorted(_candidate_overlap_dates(page_campaigns)):
            daily = [
                campaign
                for campaign in page_campaigns
                if _campaign_reserves_on(campaign, day)
            ]
            events: list[tuple[int, int, dict[str, Any]]] = []
            for campaign in daily:
                start, end = _campaign_time_range(campaign)
                events.append((start, 1, campaign))
                events.append((end, -1, campaign))
            active: dict[str, dict[str, Any]] = {}
            for minute, event_type, campaign in sorted(
                events,
                key=lambda item: (item[0], item[1]),
            ):
                campaign_id = str(campaign.get("id") or "")
                if event_type < 0:
                    active.pop(campaign_id, None)
                    continue
                active[campaign_id] = campaign
                if len(active) <= MAX_ROTATION_SPONSORS:
                    continue
                if required and not set(active).intersection(required):
                    continue
                occupant = next(
                    (
                        item
                        for item_id, item in active.items()
                        if item_id in preferred
                    ),
                    next(iter(active.values())),
                )
                end = min(_campaign_time_range(item)[1] for item in active.values())
                return PromotionAvailabilityConflict(
                    page=page,
                    day=day.isoformat(),
                    start_time=_minutes_to_time(minute),
                    end_time=_minutes_to_time(end),
                    occupying_campaign=occupant,
                )
    return None


def validate_campaign_availability(state: dict[str, Any]) -> None:
    conflict = _availability_conflict(list(state.get("campaigns") or []))
    if conflict is not None:
        raise conflict


def _cross_state_availability_conflict(
    current_state: dict[str, Any],
    proposed_state: dict[str, Any],
    *,
    include_removed_as_occupants: bool,
) -> PromotionAvailabilityConflict | None:
    current_by_id = {
        str(campaign.get("id") or ""): campaign
        for campaign in current_state.get("campaigns") or []
    }
    proposed_by_id = {
        str(campaign.get("id") or ""): campaign
        for campaign in proposed_state.get("campaigns") or []
    }
    changed_ids = {
        campaign_id
        for campaign_id, campaign in proposed_by_id.items()
        if current_by_id.get(campaign_id) != campaign
    }
    if not changed_ids:
        return None
    occupants = [
        campaign
        for campaign_id, campaign in current_by_id.items()
        if campaign_id not in changed_ids
        and (include_removed_as_occupants or campaign_id in proposed_by_id)
    ]
    incoming = [proposed_by_id[campaign_id] for campaign_id in sorted(changed_ids)]
    return _availability_conflict(
        occupants + incoming,
        required_campaign_ids=changed_ids,
        preferred_occupant_ids=set(current_by_id).difference(changed_ids),
    )


def build_availability(
    state: dict[str, Any],
    *,
    start_date: str,
    end_date: str,
    placements: list[str] | None = None,
) -> dict[str, Any]:
    selected_start = _date(start_date)
    selected_end = _date(end_date)
    if not selected_start or not selected_end:
        raise PromotionValidationError("promotion_date_invalid")
    start = datetime.strptime(selected_start, "%Y-%m-%d").date()
    end = datetime.strptime(selected_end, "%Y-%m-%d").date()
    if end < start:
        raise PromotionValidationError("promotion_availability_period_invalid")
    if (end - start).days + 1 > MAX_AVAILABILITY_DAYS:
        raise PromotionValidationError("promotion_availability_period_too_large")
    selected_pages = sorted(set(placements or PLACEMENTS))
    if not selected_pages or any(page not in PLACEMENTS for page in selected_pages):
        raise PromotionValidationError("promotion_placement_invalid")

    reserving = [
        campaign
        for campaign in state.get("campaigns") or []
        if _campaign_reserves(campaign)
    ]
    days = []
    current = start
    while current <= end:
        for page in selected_pages:
            campaigns = [
                campaign
                for campaign in reserving
                if page in (campaign.get("placements") or [])
                and _campaign_reserves_on(campaign, current)
            ]
            boundaries = {0, MINUTES_PER_DAY}
            for campaign in campaigns:
                boundaries.update(_campaign_time_range(campaign))
            intervals = []
            ordered = sorted(boundaries)
            for interval_start, interval_end in zip(ordered, ordered[1:]):
                active = [
                    campaign
                    for campaign in campaigns
                    if _campaign_time_range(campaign)[0] <= interval_start
                    and _campaign_time_range(campaign)[1] >= interval_end
                ]
                exclusive = any(
                    _campaign_placement_mode(campaign, page) == "exclusive"
                    for campaign in active
                )
                rotations = sum(
                    _campaign_placement_mode(campaign, page) == "rotation"
                    for campaign in active
                )
                reservations = [
                    {
                        "campaignId": campaign["id"],
                        "campaignTitle": (
                            campaign.get("businessName")
                            or campaign.get("title")
                            or campaign["id"]
                        ),
                        "status": campaign["status"],
                        "mode": _campaign_placement_mode(campaign, page),
                    }
                    for campaign in active
                ]
                intervals.append({
                    "startTime": _minutes_to_time(interval_start),
                    "endTime": _minutes_to_time(interval_end),
                    "exclusiveAvailable": not active,
                    "rotationSlotsAvailable": (
                        0 if exclusive else max(0, MAX_ROTATION_SPONSORS - rotations)
                    ),
                    "reservations": reservations,
                })
            days.append({
                "page": page,
                "date": current.isoformat(),
                "intervals": intervals,
            })
        current += timedelta(days=1)
    return {
        "timezone": "Europe/Rome",
        "startDate": start.isoformat(),
        "endDate": end.isoformat(),
        "maxRotationSponsors": MAX_ROTATION_SPONSORS,
        "days": days,
    }


def _campaign_active_on(campaign: dict[str, Any], today: str) -> bool:
    if campaign.get("status") != "active":
        return False
    mode = campaign.get("scheduleMode") or "period"
    if mode == "days":
        return today in set(campaign.get("activeDates") or [])
    if mode == "month":
        month = str(campaign.get("activeMonth") or "")
        return len(month) == 7 and today.startswith(f"{month}-")
    start = str(campaign.get("startDate") or "")
    end = str(campaign.get("endDate") or "")
    return (not start or today >= start) and (not end or today <= end)


def _campaign_active_at(campaign: dict[str, Any], now: datetime) -> bool:
    local_now = now.astimezone(ROME)
    if not _campaign_active_on(campaign, local_now.date().isoformat()):
        return False
    start, end = _campaign_time_range(campaign)
    minute = local_now.hour * 60 + local_now.minute
    return start <= minute < end


def build_public_catalog(
    state: dict[str, Any],
    *,
    revision: int,
    now: datetime | None = None,
) -> dict[str, Any]:
    selected_now = now or datetime.now(timezone.utc)
    enabled = state.get("adsEnabled") is True
    placement_rotation_intervals = _placement_rotation_intervals(
        state.get("placementRotationIntervals")
    )
    enabled_placements = {
        placement
        for placement, placement_enabled in dict(
            state.get("placementEnabled") or {}
        ).items()
        if placement in PLACEMENTS and placement_enabled is True
    }
    campaigns = []
    if enabled:
        for campaign in state.get("campaigns") or []:
            if not _campaign_active_at(campaign, selected_now):
                continue
            placements = [
                placement
                for placement in campaign.get("placements") or []
                if placement in enabled_placements
            ]
            if not placements:
                continue
            placement_assignments = {
                placement: {
                    "cardNumber": 1,
                    "mode": _campaign_placement_mode(campaign, placement),
                }
                for placement in placements
            }
            assignment_modes = {
                assignment["mode"]
                for assignment in placement_assignments.values()
            }
            visible_details = set(campaign.get("cardDetails") or [])
            campaigns.append({
                "id": campaign["id"],
                "advertiserId": hashlib.sha256(
                    campaign["businessName"].casefold().encode("utf-8")
                ).hexdigest()[:20],
                "advertiserDailyCap": state["maxAdvertiserPerDay"],
                "campaignDailyCap": campaign["maxPerDay"],
                "enabled": True,
                "image": campaign["imageUrl"],
                "location": campaign["city"] if "city" in visible_details else "",
                "businessAddress": (
                    campaign["businessAddress"]
                    if "address" in visible_details else ""
                ),
                "category": (
                    campaign["category"]
                    if "category" in visible_details else ""
                ),
                "title": campaign["businessName"],
                "headline": campaign["title"],
                "text": campaign["description"],
                "ctaLabel": campaign["ctaLabel"],
                "url": campaign["destinationUrl"],
                "placements": placements,
                "placementAssignments": placement_assignments,
                "deliveryMode": "all_selected",
                "bookingMode": (
                    next(iter(assignment_modes))
                    if len(assignment_modes) == 1
                    else "mixed"
                ),
                "scheduleMode": campaign["scheduleMode"],
                "activeMonth": campaign["activeMonth"],
                "startsAt": campaign["startDate"],
                "endsAt": campaign["endDate"],
                "startTime": campaign["startTime"],
                "endTime": campaign["endTime"],
                "activeDates": campaign["activeDates"],
            })
    return {
        "schemaVersion": PUBLIC_CATALOG_SCHEMA_VERSION,
        "enabled": enabled and bool(campaigns),
        "revision": max(0, int(revision)),
        "generatedAt": _now_iso(selected_now),
        "maxAgeSeconds": CATALOG_MAX_AGE_SECONDS,
        "timezone": "Europe/Rome",
        "placements": sorted(PLACEMENTS),
        "placementRotationIntervals": placement_rotation_intervals,
        "rotationIntervalSeconds": placement_rotation_intervals["home"],
        "maxRotationCampaigns": MAX_ROTATION_SPONSORS,
        "dailyCap": state["maxAdsPerDay"] if enabled else 0,
        "campaigns": campaigns,
    }


class PromotionRepository:
    def __init__(self, firestore_provider: Callable[[], Any | None]):
        self._firestore_provider = firestore_provider
        self._lock = RLock()
        self._state = default_admin_state()
        self._revision = 0
        self._updated_at = ""
        self._updated_by_email = ""
        self._metrics: dict[str, dict[str, Any]] = {}

    def _db(self) -> Any | None:
        try:
            return self._firestore_provider()
        except Exception:
            return None

    @staticmethod
    def _persistent_required() -> bool:
        return bool(os.getenv("K_SERVICE", "").strip())

    def read_state(self) -> tuple[dict[str, Any], int, str, str, str]:
        db = self._db()
        if db is not None:
            try:
                snapshot = db.collection(ADMIN_COLLECTION).document(ADMIN_DOCUMENT).get()
                if snapshot.exists:
                    payload = dict(snapshot.to_dict() or {})
                    return (
                        sanitize_admin_state(payload.get("state") or {}),
                        max(0, int(payload.get("revision", 0))),
                        "firestore",
                        _now_iso(payload["updated_at"]) if isinstance(payload.get("updated_at"), datetime) else "",
                        str(payload.get("updated_by_email") or "")[:320],
                    )
                return default_admin_state(), 0, "firestore_empty", "", ""
            except Exception as error:
                raise PromotionStorageUnavailable("promotion_state_read_failed") from error
        if self._persistent_required():
            raise PromotionStorageUnavailable("promotion_firestore_required")
        with self._lock:
            return copy.deepcopy(self._state), self._revision, "memory", self._updated_at, self._updated_by_email

    def write_state(
        self,
        state: dict[str, Any],
        *,
        expected_revision: int | None,
        actor_uid: str,
        actor_email: str,
    ) -> tuple[dict[str, Any], int, str, str, str]:
        sanitized = sanitize_admin_state(state)
        db = self._db()
        if db is not None:
            try:
                from google.cloud import firestore

                document = db.collection(ADMIN_COLLECTION).document(ADMIN_DOCUMENT)
                transaction = db.transaction()

                @firestore.transactional
                def persist(transaction_in_progress: Any) -> tuple[int, datetime]:
                    snapshot = document.get(transaction=transaction_in_progress)
                    current = dict(snapshot.to_dict() or {}) if snapshot.exists else {}
                    current_revision = max(0, int(current.get("revision", 0)))
                    current_state = sanitize_admin_state(
                        current.get("state") or default_admin_state()
                    )
                    availability_conflict = _cross_state_availability_conflict(
                        current_state,
                        sanitized,
                        include_removed_as_occupants=(
                            expected_revision is not None
                            and expected_revision != current_revision
                        ),
                    )
                    if availability_conflict is not None:
                        raise availability_conflict
                    if (
                        expected_revision is not None
                        and expected_revision != current_revision
                    ):
                        raise PromotionStateConflict("promotion_revision_conflict")
                    validate_campaign_availability(sanitized)
                    next_revision = current_revision + 1
                    changed_at = datetime.now(timezone.utc)
                    transaction_in_progress.set(document, {
                        "revision": next_revision,
                        "state": sanitized,
                        "updated_at": changed_at,
                        "updated_by_uid": actor_uid,
                        "updated_by_email": actor_email,
                    }, merge=False)
                    return next_revision, changed_at

                revision, changed_at = persist(transaction)
                return sanitized, int(revision), "firestore", _now_iso(changed_at), actor_email[:320]
            except PromotionStateConflict:
                raise
            except Exception as error:
                raise PromotionStorageUnavailable("promotion_state_write_failed") from error
        if self._persistent_required():
            raise PromotionStorageUnavailable("promotion_firestore_required")
        with self._lock:
            availability_conflict = _cross_state_availability_conflict(
                self._state,
                sanitized,
                include_removed_as_occupants=(
                    expected_revision is not None
                    and expected_revision != self._revision
                ),
            )
            if availability_conflict is not None:
                raise availability_conflict
            if expected_revision is not None and expected_revision != self._revision:
                raise PromotionStateConflict("promotion_revision_conflict")
            validate_campaign_availability(sanitized)
            self._revision += 1
            self._updated_at = _now_iso()
            self._updated_by_email = actor_email[:320]
            self._state = copy.deepcopy(sanitized)
            return copy.deepcopy(self._state), self._revision, "memory", self._updated_at, self._updated_by_email

    def record_event(
        self,
        *,
        campaign_id: str,
        placement: str,
        event_type: str,
        now: datetime | None = None,
    ) -> str:
        selected_now = now or datetime.now(timezone.utc)
        day = selected_now.astimezone(ROME).date().isoformat()
        key = hashlib.sha256(
            f"{day}:{campaign_id}:{placement}".encode("utf-8")
        ).hexdigest()
        db = self._db()
        if db is not None:
            try:
                from google.cloud import firestore

                document = db.collection(METRICS_COLLECTION).document(key)
                document.set({
                    "day": day,
                    "campaign_id": campaign_id,
                    "placement": placement,
                    event_type: firestore.Increment(1),
                    "updated_at": selected_now,
                }, merge=True)
                return "firestore"
            except Exception as error:
                raise PromotionStorageUnavailable("promotion_metric_write_failed") from error
        if self._persistent_required():
            raise PromotionStorageUnavailable("promotion_firestore_required")
        with self._lock:
            metric = self._metrics.setdefault(key, {
                "day": day,
                "campaign_id": campaign_id,
                "placement": placement,
                "impression": 0,
                "open": 0,
            })
            metric[event_type] = int(metric.get(event_type, 0)) + 1
        return "memory"

    def read_metrics(self) -> list[dict[str, Any]]:
        db = self._db()
        if db is not None:
            try:
                return [
                    dict(snapshot.to_dict() or {})
                    for snapshot in db.collection(METRICS_COLLECTION).limit(500).stream()
                ]
            except Exception as error:
                raise PromotionStorageUnavailable("promotion_metric_read_failed") from error
        if self._persistent_required():
            raise PromotionStorageUnavailable("promotion_firestore_required")
        with self._lock:
            return copy.deepcopy(list(self._metrics.values()))


class PromotionService:
    def __init__(self, repository: PromotionRepository):
        self.repository = repository

    def public_catalog(self) -> dict[str, Any]:
        state, revision, _storage, _updated_at, _updated_by_email = self.repository.read_state()
        return build_public_catalog(state, revision=revision)

    def admin_state(self) -> dict[str, Any]:
        state, revision, storage, updated_at, updated_by_email = self.repository.read_state()
        return {
            "revision": revision,
            "state": state,
            "catalog": build_public_catalog(state, revision=revision),
            "metrics": self.repository.read_metrics(),
            "storage": storage,
            "updatedAt": updated_at,
            "updatedByEmail": updated_by_email,
        }

    def availability(
        self,
        *,
        start_date: str | None = None,
        end_date: str | None = None,
        placements: list[str] | None = None,
    ) -> dict[str, Any]:
        state, revision, storage, _updated_at, _updated_by_email = self.repository.read_state()
        today = datetime.now(ROME).date().isoformat()
        selected_start = start_date or today
        selected_end = end_date or selected_start
        result = build_availability(
            state,
            start_date=selected_start,
            end_date=selected_end,
            placements=placements,
        )
        result.update({"revision": revision, "storage": storage})
        return result

    def replace_state(
        self,
        state: dict[str, Any],
        *,
        expected_revision: int | None,
        actor_uid: str,
        actor_email: str,
    ) -> dict[str, Any]:
        stored, revision, storage, updated_at, updated_by_email = self.repository.write_state(
            state,
            expected_revision=expected_revision,
            actor_uid=actor_uid,
            actor_email=actor_email,
        )
        return {
            "revision": revision,
            "state": stored,
            "catalog": build_public_catalog(stored, revision=revision),
            "metrics": self.repository.read_metrics(),
            "storage": storage,
            "updatedAt": updated_at,
            "updatedByEmail": updated_by_email,
        }

    def record_event(self, payload: dict[str, Any]) -> dict[str, Any]:
        campaign_id = _bounded_text(payload.get("campaignId"), 120)
        placement = _bounded_text(payload.get("placement"), 20).lower()
        event_type = _bounded_text(payload.get("type"), 20).lower()
        if not campaign_id or placement not in PLACEMENTS or event_type not in EVENT_TYPES:
            raise PromotionValidationError("promotion_event_invalid")
        catalog = self.public_catalog()
        eligible = any(
            item.get("id") == campaign_id
            and placement in (item.get("placements") or [])
            for item in catalog.get("campaigns") or []
        )
        if not eligible:
            raise PromotionValidationError("promotion_event_campaign_inactive")
        storage = self.repository.record_event(
            campaign_id=campaign_id,
            placement=placement,
            event_type=event_type,
        )
        return {"accepted": True, "storage": storage}
