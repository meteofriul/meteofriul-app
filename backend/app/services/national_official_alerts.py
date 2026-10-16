"""Location-aware projection of one reconciled national DPC snapshot.

The projector is pure: it does not fetch, persist, publish or send anything.
FVG projections are explicitly marked as requiring the existing regional
reconciliation, so a caller cannot silently replace the current FVG service
with the national base layer.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

from app.services.national_municipalities import (
    NationalMunicipalityCatalog,
    get_default_national_municipality_catalog,
)
from app.services.official_alert_zone_catalog import (
    FVG_REGION_ISO,
    OfficialAlertZoneCatalog,
    get_default_official_alert_zone_catalog,
)
from app.weather.dpc_national_alerts import DPC_NATIONAL_ALERTS_SOURCE_ID
from app.weather.dpc_national_zone_snapshot import DPC_ZONE_SNAPSHOT_CONTRACT


NATIONAL_LOCATION_ALERTS_CONTRACT = (
    "meteofriul.official_alerts.location.v1"
)
NATIONAL_ALERT_SNAPSHOT_MAX_AGE = timedelta(hours=36)
_LEVEL_RANK = {"green": 0, "yellow": 1, "orange": 2, "red": 3}
_RISKS = frozenset({"hydrogeological", "thunderstorm", "hydraulic"})
_ROME = ZoneInfo("Europe/Rome")


class NationalOfficialAlertsProjectionError(ValueError):
    """A location projection cannot be produced without guessing."""


def _aware_datetime(value: Any, error_code: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError as error:
        raise NationalOfficialAlertsProjectionError(error_code) from error
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise NationalOfficialAlertsProjectionError(error_code)
    return parsed


def project_national_official_alerts(
    snapshot: dict[str, Any],
    municipality_istat: Any,
    *,
    now: datetime | None = None,
    zone_catalog: OfficialAlertZoneCatalog | None = None,
    municipality_catalog: NationalMunicipalityCatalog | None = None,
) -> dict[str, Any]:
    """Return the complete zonal state for one exact ISTAT municipality."""

    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None or current.utcoffset() is None:
        raise NationalOfficialAlertsProjectionError("national_alert_now_invalid")
    current = current.astimezone(timezone.utc)
    zones = zone_catalog or get_default_official_alert_zone_catalog()
    municipalities = (
        municipality_catalog or get_default_national_municipality_catalog()
    )
    mapping = zones.match_istat(municipality_istat)
    identity = municipalities.match_istat(municipality_istat)
    if mapping is None or identity is None or mapping.region_iso != identity.region_iso:
        raise NationalOfficialAlertsProjectionError(
            "national_alert_municipality_unresolved"
        )
    if (
        not isinstance(snapshot, dict)
        or snapshot.get("contract") != DPC_ZONE_SNAPSHOT_CONTRACT
        or snapshot.get("coverage") != "all_zones_two_days"
        or snapshot.get("can_confirm_green") is not True
        or snapshot.get("reconciled") is not True
        or snapshot.get("source", {}).get("id")
        != DPC_NATIONAL_ALERTS_SOURCE_ID
    ):
        raise NationalOfficialAlertsProjectionError(
            "national_alert_snapshot_unverified"
        )
    try:
        sent_at = _aware_datetime(
            snapshot["cap_revision"]["sent_at"],
            "national_alert_revision_invalid",
        ).astimezone(timezone.utc)
        revision_id = str(snapshot["cap_revision"]["id"])
        zone_revision = str(snapshot["revision"]["source_revision"])
    except (KeyError, TypeError) as error:
        raise NationalOfficialAlertsProjectionError(
            "national_alert_revision_invalid"
        ) from error
    if not revision_id or zone_revision != sent_at.astimezone(_ROME).strftime(
        "%Y%m%d_%H%M"
    ):
        raise NationalOfficialAlertsProjectionError(
            "national_alert_revision_invalid"
        )
    if sent_at > current + timedelta(minutes=5):
        raise NationalOfficialAlertsProjectionError(
            "national_alert_revision_from_future"
        )
    if current - sent_at > NATIONAL_ALERT_SNAPSHOT_MAX_AGE:
        raise NationalOfficialAlertsProjectionError(
            "national_alert_snapshot_stale"
        )

    raw_records = snapshot.get("records")
    if not isinstance(raw_records, list):
        raise NationalOfficialAlertsProjectionError(
            "national_alert_records_missing"
        )
    selected: list[dict[str, Any]] = []
    identities = set()
    expected_source_zone = {
        zone.zone_id: zone.source_zone_id for zone in zones.zones
    }
    for raw in raw_records:
        if not isinstance(raw, dict) or raw.get("zone_id") not in mapping.zone_ids:
            continue
        try:
            zone_id = str(raw["zone_id"])
            source_zone_id = str(raw["source_zone_id"])
            risk = str(raw["risk"])
            forecast_day = str(raw["forecast_day"])
            valid_from = _aware_datetime(
                raw["valid_from"], "national_alert_record_invalid"
            )
            valid_to = _aware_datetime(
                raw["valid_to"], "national_alert_record_invalid"
            )
            transmission_status = str(raw["transmission_status"])
            level = raw.get("level")
        except (KeyError, TypeError) as error:
            raise NationalOfficialAlertsProjectionError(
                "national_alert_record_invalid"
            ) from error
        key = (zone_id, risk, forecast_day)
        if (
            source_zone_id != expected_source_zone.get(zone_id)
            or risk not in _RISKS
            or key in identities
            or valid_to <= valid_from
            or transmission_status not in {"transmitted", "not_transmitted"}
            or (
                transmission_status == "transmitted"
                and level not in _LEVEL_RANK
            )
            or (
                transmission_status == "not_transmitted" and level is not None
            )
        ):
            raise NationalOfficialAlertsProjectionError(
                "national_alert_record_invalid"
            )
        identities.add(key)
        if valid_to.astimezone(timezone.utc) < current:
            continue
        selected.append(
            {
                "zone_id": zone_id,
                "source_zone_id": source_zone_id,
                "zone_name": str(raw.get("zone_name") or "").strip(),
                "risk": risk,
                "level": level,
                "level_rank": None if level is None else _LEVEL_RANK[level],
                "transmission_status": transmission_status,
                "forecast_day": forecast_day,
                "valid_from": valid_from.isoformat(),
                "valid_to": valid_to.isoformat(),
            }
        )
    if not selected:
        raise NationalOfficialAlertsProjectionError(
            "national_alert_snapshot_expired"
        )

    by_zone_day: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for record in selected:
        by_zone_day[(record["zone_id"], record["forecast_day"])].append(record)
    expected_zone_days = {
        (record["zone_id"], record["forecast_day"])
        for record in selected
    }
    if any(
        {record["risk"] for record in records} != _RISKS
        or len(records) != len(_RISKS)
        for records in by_zone_day.values()
    ) or {zone_id for zone_id, _ in expected_zone_days} != set(mapping.zone_ids):
        raise NationalOfficialAlertsProjectionError(
            "national_alert_location_coverage_incomplete"
        )

    selected.sort(
        key=lambda item: (item["forecast_day"], item["zone_id"], item["risk"])
    )
    summaries = []
    for (zone_id, forecast_day), records in sorted(by_zone_day.items()):
        transmitted = [
            record for record in records if record["transmission_status"] == "transmitted"
        ]
        highest = max(
            (record["level"] for record in transmitted),
            key=lambda level: _LEVEL_RANK[level],
            default=None,
        )
        summaries.append(
            {
                "zone_id": zone_id,
                "forecast_day": forecast_day,
                "level": highest,
                "level_rank": None if highest is None else _LEVEL_RANK[highest],
                "complete": len(transmitted) == len(_RISKS),
            }
        )

    active = any((record["level_rank"] or 0) > 0 for record in selected)
    partial = any(
        record["transmission_status"] == "not_transmitted" for record in selected
    )
    highest_level = max(
        (record["level"] for record in selected if record["level"] is not None),
        key=lambda level: _LEVEL_RANK[level],
        default=None,
    )
    status = (
        "active_partial"
        if active and partial
        else "active"
        if active
        else "not_transmitted"
        if partial
        else "green"
    )
    is_fvg = identity.region_iso == FVG_REGION_ISO
    return {
        "contract": NATIONAL_LOCATION_ALERTS_CONTRACT,
        "schema_version": 1,
        "status": status,
        "active": active,
        "complete": not partial,
        "highest_level": highest_level,
        "highest_level_rank": (
            None if highest_level is None else _LEVEL_RANK[highest_level]
        ),
        "municipality": {
            "istat": identity.istat_code,
            "name": identity.name,
            "region_iso": identity.region_iso,
        },
        "zones": list(mapping.zone_ids),
        "conservative_multi_zone_display": len(mapping.zone_ids) > 1,
        "regional_detail": {
            "required": is_fvg,
            "authority": "Protezione Civile FVG / ARPA OSMER" if is_fvg else None,
            "reconciled": False if is_fvg else None,
        },
        "standalone_display_allowed": not is_fvg,
        "source": dict(snapshot["source"]),
        "revision": {
            "id": revision_id,
            "sent_at": sent_at.isoformat(),
            "zone_state_revision": zone_revision,
            "zone_catalog_sha256": zones.catalog_sha256,
        },
        "records": selected,
        "zone_day_summaries": summaries,
        "expires_at": max(record["valid_to"] for record in selected),
        "generated_at": current.isoformat(),
    }


__all__ = [
    "NATIONAL_LOCATION_ALERTS_CONTRACT",
    "NationalOfficialAlertsProjectionError",
    "project_national_official_alerts",
]
