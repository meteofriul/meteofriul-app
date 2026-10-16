"""Pure Play candidate selection for manual national alert subscriptions.

The public dry-run reports only aggregate counts. The private selection can be
used by a separate dispatcher, but this module never sends or persists data.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable
from zoneinfo import ZoneInfo

from app.repositories.push import (
    PUSH_TARGET_FCM_TOKEN,
    hash_push_target,
    resolve_push_target,
)
from app.services.national_municipalities import (
    NationalMunicipalityCatalog,
    get_default_national_municipality_catalog,
)
from app.services.national_official_alerts import (
    NATIONAL_ALERT_SNAPSHOT_MAX_AGE,
    NationalOfficialAlertsProjectionError,
    project_national_official_alerts,
)
from app.services.official_alert_zone_catalog import (
    ALERT_ZONE_CATALOG_ZONE_COUNT,
    FVG_REGION_ISO,
    OfficialAlertZoneCatalog,
    get_default_official_alert_zone_catalog,
)
from app.services.push_version_policy import android_app_version_allowed
from app.weather.dpc_national_alerts import DPC_NATIONAL_ALERTS_SOURCE_ID
from app.weather.dpc_national_zone_snapshot import DPC_ZONE_SNAPSHOT_CONTRACT


DRY_RUN_CONTRACT = "meteofriul.national_alert_push_dry_run.v1"
_ROME = ZoneInfo("Europe/Rome")
_ACTIVE_LEVELS = frozenset({"yellow", "orange", "red"})
_SHA256 = re.compile(r"[0-9a-f]{64}")


class NationalAlertDryRunUnavailable(RuntimeError):
    """A candidate estimate would require trusting incomplete input."""


@dataclass(frozen=True, slots=True)
class NationalAlertDryRunPolicy:
    enrollment_generation: str
    android_app_ids: frozenset[str]
    min_app_version_code: int

    def __post_init__(self) -> None:
        if (
            not self.enrollment_generation
            or not self.android_app_ids
            or not isinstance(self.min_app_version_code, int)
            or isinstance(self.min_app_version_code, bool)
            or self.min_app_version_code < 1
        ):
            raise NationalAlertDryRunUnavailable("dry_run_policy_invalid")


@dataclass(frozen=True, slots=True)
class NationalAlertCandidate:
    device: dict[str, Any]
    municipality_istat: str
    municipality_name: str
    target_kind: str
    target_value: str
    target_hash: str
    projection: dict[str, Any]
    active_records: tuple[dict[str, Any], ...]


@dataclass(frozen=True, slots=True)
class NationalAlertSelection:
    source_revision: str
    zone_catalog_sha256: str
    devices_seen: int
    eligible_manual_devices: int
    candidate_records: int
    exclusions: dict[str, int]
    candidates: tuple[NationalAlertCandidate, ...]


def _current_time(now: datetime | None) -> datetime:
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None or current.utcoffset() is None:
        raise NationalAlertDryRunUnavailable("dry_run_clock_invalid")
    return current.astimezone(timezone.utc)


def _source_revision(
    snapshot: Any,
    storage: str,
    current: datetime,
    expected_zone_count: int,
) -> str:
    if storage != "firestore" or not isinstance(snapshot, dict):
        raise NationalAlertDryRunUnavailable("national_snapshot_not_persistent")
    records = snapshot.get("records")
    if (
        snapshot.get("contract") != DPC_ZONE_SNAPSHOT_CONTRACT
        or snapshot.get("coverage") != "all_zones_two_days"
        or snapshot.get("can_confirm_green") is not True
        or snapshot.get("reconciled") is not True
        or not isinstance(snapshot.get("source"), dict)
        or snapshot["source"].get("id") != DPC_NATIONAL_ALERTS_SOURCE_ID
        or snapshot.get("zone_count") != expected_zone_count
        or not isinstance(records, list)
        or len(records) != expected_zone_count * 3 * 2
    ):
        raise NationalAlertDryRunUnavailable("national_snapshot_unverified")
    try:
        sent_at = datetime.fromisoformat(
            str(snapshot["cap_revision"]["sent_at"]).replace("Z", "+00:00")
        )
        cap_id = str(snapshot["cap_revision"]["id"])
        cap_hash = str(snapshot["cap_revision"]["sha256"])
        zone_hash = str(snapshot["revision"]["sha256"])
        revision = str(snapshot["revision"]["source_revision"])
    except (KeyError, TypeError, ValueError) as error:
        raise NationalAlertDryRunUnavailable("national_revision_invalid") from error
    if (
        sent_at.tzinfo is None
        or sent_at.utcoffset() is None
        or not cap_id
        or _SHA256.fullmatch(cap_hash) is None
        or _SHA256.fullmatch(zone_hash) is None
        or revision != sent_at.astimezone(_ROME).strftime("%Y%m%d_%H%M")
        or sent_at.astimezone(timezone.utc) > current + timedelta(minutes=5)
        or current - sent_at.astimezone(timezone.utc)
        > NATIONAL_ALERT_SNAPSHOT_MAX_AGE
    ):
        raise NationalAlertDryRunUnavailable("national_revision_stale_or_invalid")
    return revision


def select_national_alert_candidates(
    snapshot: dict[str, Any] | None,
    devices: Iterable[dict[str, Any]],
    *,
    storage: str,
    policy: NationalAlertDryRunPolicy,
    now: datetime | None = None,
    zone_catalog: OfficialAlertZoneCatalog | None = None,
    municipality_catalog: NationalMunicipalityCatalog | None = None,
    expected_zone_count: int = ALERT_ZONE_CATALOG_ZONE_COUNT,
) -> NationalAlertSelection:
    """Validate the persistent source and select only exact manual Play targets."""

    current = _current_time(now)
    revision = _source_revision(snapshot, storage, current, expected_zone_count)
    zones = zone_catalog or get_default_official_alert_zone_catalog()
    municipalities = (
        municipality_catalog or get_default_national_municipality_catalog()
    )
    exclusions: Counter[str] = Counter()
    seen_targets: set[str] = set()
    projections: dict[str, dict[str, Any]] = {}
    seen = eligible = candidate_records = 0
    candidates: list[NationalAlertCandidate] = []

    for device in devices:
        seen += 1
        if device.get("active") is not True:
            exclusions["inactive"] += 1
            continue
        if (device.get("preferences") or {}).get("official_alerts") is not True:
            exclusions["preference_disabled"] += 1
            continue
        if (
            device.get("platform") != "android"
            or device.get("schema_version") != "2.1"
            or device.get("enrollment_generation") != policy.enrollment_generation
            or device.get("app_check_app_id") not in policy.android_app_ids
            or not android_app_version_allowed(
                str(device.get("app_version") or ""),
                allowed_app_versions=frozenset(),
                min_app_version_code=policy.min_app_version_code,
            )
        ):
            exclusions["play_policy_not_met"] += 1
            continue
        if device.get("location_mode") != "manual_selection":
            exclusions["not_manual_selection"] += 1
            continue
        municipality = device.get("municipality")
        if not isinstance(municipality, dict):
            exclusions["municipality_unresolved"] += 1
            continue
        istat = str(municipality.get("istat") or "").strip()
        identity = municipalities.match_istat(istat)
        mapping = zones.match_istat(istat)
        if (
            identity is None
            or mapping is None
            or municipality.get("name") != identity.name
            or mapping.region_iso != identity.region_iso
        ):
            exclusions["municipality_unresolved"] += 1
            continue
        if identity.region_iso == FVG_REGION_ISO:
            exclusions["fvg_uses_regional_dispatcher"] += 1
            continue
        target_kind, target_value, _ = resolve_push_target(device)
        if (
            not device.get("device_id")
            or target_kind != PUSH_TARGET_FCM_TOKEN
            or not target_value
        ):
            exclusions["delivery_target_missing"] += 1
            continue
        # The repository also checks uniqueness. Repeat it here so the pure
        # evaluator fails closed when used with a fixture or another reader.
        target_hash = hash_push_target(target_value)
        if target_hash in seen_targets:
            raise NationalAlertDryRunUnavailable("duplicate_delivery_target")
        seen_targets.add(target_hash)
        eligible += 1
        if istat not in projections:
            try:
                projections[istat] = project_national_official_alerts(
                    snapshot,
                    istat,
                    now=current,
                    zone_catalog=zones,
                    municipality_catalog=municipalities,
                )
            except NationalOfficialAlertsProjectionError as error:
                raise NationalAlertDryRunUnavailable(
                    "national_location_projection_failed"
                ) from error
        projected = projections[istat]
        if not projected.get("standalone_display_allowed"):
            raise NationalAlertDryRunUnavailable("national_fvg_boundary_invalid")
        if projected.get("complete") is not True:
            exclusions["official_state_partial"] += 1
            continue
        active_records = [
            record
            for record in projected["records"]
            if record.get("transmission_status") == "transmitted"
            and record.get("level") in _ACTIVE_LEVELS
        ]
        if active_records:
            candidate_records += len(active_records)

            candidates.append(NationalAlertCandidate(
                device=device,
                municipality_istat=istat,
                municipality_name=identity.name,
                target_kind=target_kind,
                target_value=target_value,
                target_hash=target_hash,
                projection=projected,
                active_records=tuple(active_records),
            ))

    return NationalAlertSelection(
        source_revision=revision,
        zone_catalog_sha256=zones.catalog_sha256,
        devices_seen=seen,
        eligible_manual_devices=eligible,
        candidate_records=candidate_records,
        exclusions=dict(sorted(exclusions.items())),
        candidates=tuple(candidates),
    )


def evaluate_national_alert_push_dry_run(
    snapshot: dict[str, Any] | None,
    devices: Iterable[dict[str, Any]],
    *,
    storage: str,
    policy: NationalAlertDryRunPolicy,
    now: datetime | None = None,
    zone_catalog: OfficialAlertZoneCatalog | None = None,
    municipality_catalog: NationalMunicipalityCatalog | None = None,
    expected_zone_count: int = ALERT_ZONE_CATALOG_ZONE_COUNT,
) -> dict[str, Any]:
    """Estimate candidates without claiming, sending or persisting them."""

    selection = select_national_alert_candidates(
        snapshot,
        devices,
        storage=storage,
        policy=policy,
        now=now,
        zone_catalog=zone_catalog,
        municipality_catalog=municipality_catalog,
        expected_zone_count=expected_zone_count,
    )

    return {
        "contract": DRY_RUN_CONTRACT,
        "status": "dry_run",
        "candidate_status": "candidate" if selection.candidates else "no_candidate",
        "push": "disabled_by_design",
        "sent": 0,
        "outbox_writes": 0,
        "source_revision": selection.source_revision,
        "zone_catalog_sha256": selection.zone_catalog_sha256,
        "devices_seen": selection.devices_seen,
        "eligible_manual_devices": selection.eligible_manual_devices,
        "candidate_devices": len(selection.candidates),
        "candidate_records": selection.candidate_records,
        "excluded": selection.exclusions,
    }
