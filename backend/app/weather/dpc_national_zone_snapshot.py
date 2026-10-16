"""Complete same-revision DPC alert-zone state from the official SHP ZIP.

The geometry archive contains one DBF table for today and one for tomorrow.
Unlike CAP, these tables include green and ``not transmitted`` states for all
zones.  Only a successfully parsed and CAP-reconciled snapshot may therefore
confirm that an omitted CAP zone is green.

No network, persistence or production dispatcher is connected here.  The
module is pure so the national contract can mature without changing the
existing FVG alert service.
"""

from __future__ import annotations

import hashlib
import re
import struct
import unicodedata
from datetime import datetime, time, timedelta
from io import BytesIO
from typing import Any
from zipfile import BadZipFile, ZipFile
from zoneinfo import ZoneInfo

from app.weather.dpc_national_alerts import (
    DPC_NATIONAL_ALERTS_CONTRACT,
    DPC_NATIONAL_ALERTS_SOURCE_ID,
    canonical_dpc_zone_id,
)


DPC_ZONE_SNAPSHOT_CONTRACT = "meteofriul.official_alert_zone_snapshot.v1"
DPC_ZONE_ZIP_MAX_BYTES = 16 * 1024 * 1024
DPC_ZONE_MEMBER_MAX_BYTES = 8 * 1024 * 1024
DPC_ZONE_MIN_COUNT = 100
DPC_ZONE_MAX_COUNT = 300

_REVISION_FILE = re.compile(
    r"(?P<revision>\d{8}_\d{4})_(?P<period>today|tomorrow)\.(?P<extension>dbf|prj|shp|shx)\Z"
)
_LEVEL_RANK = {"green": 0, "yellow": 1, "orange": 2, "red": 3}
_RISK_FIELDS = (
    ("Idrogeo", "hydrogeological"),
    ("Temporali", "thunderstorm"),
    ("Idraulico", "hydraulic"),
)
_REQUIRED_DBF_FIELDS = {
    "Zona_all",
    "Nome_zona",
    "Criticita",
    *(field for field, _ in _RISK_FIELDS),
}
_ROME = ZoneInfo("Europe/Rome")


class DpcNationalZoneSnapshotError(ValueError):
    """The DPC zone dataset is incomplete, inconsistent or unsafe."""


def _normalized_text(value: Any) -> str:
    decomposed = unicodedata.normalize("NFKD", str(value or ""))
    without_marks = "".join(
        character
        for character in decomposed
        if not unicodedata.combining(character)
    )
    return " ".join(without_marks.upper().split())


def _level(value: Any) -> tuple[str | None, str]:
    normalized = _normalized_text(value)
    if "VALUTAZIONE NON TRASMESSA" in normalized:
        return None, "not_transmitted"
    matches = [
        level
        for markers, level in (
            (("ALLERTA ROSSA", "ELEVATA CRITICITA"), "red"),
            (("ALLERTA ARANCIONE", "MODERATA CRITICITA"), "orange"),
            (("ALLERTA GIALLA", "ORDINARIA CRITICITA"), "yellow"),
            (
                (
                    "NESSUNA ALLERTA",
                    "ASSENZA DI CRITICITA",
                    "ASSENZA DI FENOMENI SIGNIFICATIVI PREVEDIBILI",
                ),
                "green",
            ),
        )
        if any(marker in normalized for marker in markers)
    ]
    if len(matches) != 1:
        raise DpcNationalZoneSnapshotError("dpc_zone_invalid_level")
    return matches[0], "transmitted"


def _read_dbf(payload: bytes) -> list[dict[str, str]]:
    if len(payload) < 34 or len(payload) > DPC_ZONE_MEMBER_MAX_BYTES:
        raise DpcNationalZoneSnapshotError("dpc_zone_invalid_dbf_size")
    record_count = struct.unpack_from("<I", payload, 4)[0]
    header_length, record_length = struct.unpack_from("<HH", payload, 8)
    if (
        not DPC_ZONE_MIN_COUNT <= record_count <= DPC_ZONE_MAX_COUNT
        or header_length < 33
        or record_length < 2
        or header_length + record_count * record_length > len(payload)
    ):
        raise DpcNationalZoneSnapshotError("dpc_zone_invalid_dbf_header")

    fields: list[tuple[str, int, int]] = []
    descriptor_offset = 32
    value_offset = 1
    while descriptor_offset < header_length:
        if payload[descriptor_offset] == 0x0D:
            break
        if descriptor_offset + 32 > header_length:
            raise DpcNationalZoneSnapshotError("dpc_zone_invalid_dbf_fields")
        name = (
            payload[descriptor_offset : descriptor_offset + 11]
            .split(b"\0", 1)[0]
            .decode("ascii", errors="strict")
            .strip()
        )
        field_type = chr(payload[descriptor_offset + 11])
        field_length = payload[descriptor_offset + 16]
        if (
            not name
            or field_type != "C"
            or field_length < 1
            or value_offset + field_length > record_length
        ):
            raise DpcNationalZoneSnapshotError("dpc_zone_invalid_dbf_fields")
        fields.append((name, value_offset, field_length))
        value_offset += field_length
        descriptor_offset += 32
    if (
        descriptor_offset >= header_length
        or payload[descriptor_offset] != 0x0D
        or value_offset != record_length
        or not _REQUIRED_DBF_FIELDS.issubset({field[0] for field in fields})
    ):
        raise DpcNationalZoneSnapshotError("dpc_zone_invalid_dbf_fields")

    rows: list[dict[str, str]] = []
    for index in range(record_count):
        start = header_length + index * record_length
        deletion_marker = payload[start]
        if deletion_marker != 0x20:
            raise DpcNationalZoneSnapshotError("dpc_zone_deleted_dbf_record")
        row = {
            name: payload[start + offset : start + offset + length]
            .decode("cp1252", errors="strict")
            .strip()
            for name, offset, length in fields
        }
        rows.append(row)
    return rows


def _validate_shape_pair(shp: bytes, shx: bytes, expected_records: int) -> None:
    for payload, label in ((shp, "shp"), (shx, "shx")):
        if len(payload) < 100 or len(payload) > DPC_ZONE_MEMBER_MAX_BYTES:
            raise DpcNationalZoneSnapshotError(f"dpc_zone_invalid_{label}_size")
        declared_bytes = struct.unpack_from(">I", payload, 24)[0] * 2
        if (
            struct.unpack_from(">I", payload, 0)[0] != 9994
            or struct.unpack_from("<I", payload, 28)[0] != 1000
            or struct.unpack_from("<I", payload, 32)[0] != 5
            or declared_bytes != len(payload)
        ):
            raise DpcNationalZoneSnapshotError(f"dpc_zone_invalid_{label}_header")
    shx_records = (len(shx) - 100) // 8
    if (len(shx) - 100) % 8 or shx_records != expected_records:
        raise DpcNationalZoneSnapshotError("dpc_zone_shape_record_mismatch")


def _read_members(payload: bytes) -> tuple[str, dict[str, bytes]]:
    if not payload or len(payload) > DPC_ZONE_ZIP_MAX_BYTES:
        raise DpcNationalZoneSnapshotError("dpc_zone_invalid_zip_size")
    try:
        with ZipFile(BytesIO(payload)) as archive:
            members: dict[str, bytes] = {}
            revisions: set[str] = set()
            for info in archive.infolist():
                name = info.filename.replace("\\", "/")
                if (
                    info.is_dir()
                    or "/" in name
                    or name.startswith(".")
                    or info.file_size > DPC_ZONE_MEMBER_MAX_BYTES
                    or info.compress_size > DPC_ZONE_MEMBER_MAX_BYTES
                    or name in members
                ):
                    raise DpcNationalZoneSnapshotError("dpc_zone_unsafe_zip_member")
                match = _REVISION_FILE.fullmatch(name)
                if match is None:
                    if name not in {"README.txt", "BCR_shape_RNDT.xml"}:
                        raise DpcNationalZoneSnapshotError(
                            "dpc_zone_unexpected_zip_member"
                        )
                    continue
                revisions.add(match.group("revision"))
                members[name] = archive.read(info)
    except (BadZipFile, OSError, RuntimeError) as error:
        raise DpcNationalZoneSnapshotError("dpc_zone_invalid_zip") from error
    if len(revisions) != 1:
        raise DpcNationalZoneSnapshotError("dpc_zone_mixed_revisions")
    revision = next(iter(revisions))
    expected_names = {
        f"{revision}_{period}.{extension}"
        for period in ("today", "tomorrow")
        for extension in ("dbf", "prj", "shp", "shx")
    }
    if set(members) != expected_names:
        raise DpcNationalZoneSnapshotError("dpc_zone_incomplete_zip")
    return revision, members


def _validity(revision: str, period: str) -> tuple[str, str, str]:
    try:
        issued_local = datetime.strptime(revision, "%Y%m%d_%H%M").replace(
            tzinfo=_ROME
        )
    except ValueError as error:
        raise DpcNationalZoneSnapshotError("dpc_zone_invalid_revision") from error
    day = issued_local.date() + timedelta(days=period == "tomorrow")
    start = datetime.combine(day, time.min, tzinfo=_ROME)
    end = datetime.combine(day + timedelta(days=1), time.min, tzinfo=_ROME)
    return day.isoformat(), start.isoformat(), (end - timedelta(seconds=1)).isoformat()


def parse_dpc_national_zone_zip(payload: bytes) -> dict[str, Any]:
    """Parse the complete two-day DPC zone ZIP without reading its geometry."""

    raw = bytes(payload)
    revision, members = _read_members(raw)
    records: list[dict[str, Any]] = []
    zone_names: dict[str, str] = {}
    source_zone_sets: dict[str, set[str]] = {}
    for period in ("today", "tomorrow"):
        prefix = f"{revision}_{period}"
        rows = _read_dbf(members[f"{prefix}.dbf"])
        _validate_shape_pair(
            members[f"{prefix}.shp"], members[f"{prefix}.shx"], len(rows)
        )
        forecast_day, valid_from, valid_to = _validity(revision, period)
        seen_source_zones: set[str] = set()
        for row in rows:
            source_zone_id = row["Zona_all"].strip()
            zone_name = row["Nome_zona"].strip()
            zone_id = canonical_dpc_zone_id(source_zone_id)
            if (
                not zone_name
                or source_zone_id in seen_source_zones
                or (zone_id in zone_names and zone_names[zone_id] != zone_name)
            ):
                raise DpcNationalZoneSnapshotError("dpc_zone_invalid_identity")
            seen_source_zones.add(source_zone_id)
            zone_names[zone_id] = zone_name
            risk_states = []
            for field, risk in _RISK_FIELDS:
                level, transmission_status = _level(row[field])
                risk_states.append((level, transmission_status))
                records.append(
                    {
                        "zone_id": zone_id,
                        "source_zone_id": source_zone_id,
                        "zone_name": zone_name,
                        "risk": risk,
                        "level": level,
                        "level_rank": None if level is None else _LEVEL_RANK[level],
                        "transmission_status": transmission_status,
                        "forecast_day": forecast_day,
                        "valid_from": valid_from,
                        "valid_to": valid_to,
                    }
                )
            summary_level, summary_status = _level(row["Criticita"])
            transmitted_levels = [
                level
                for level, status in risk_states
                if status == "transmitted" and level is not None
            ]
            expected_summary = (
                max(transmitted_levels, key=_LEVEL_RANK.get)
                if transmitted_levels
                else None
            )
            if summary_level != expected_summary or (
                expected_summary is None and summary_status != "not_transmitted"
            ):
                raise DpcNationalZoneSnapshotError(
                    "dpc_zone_summary_risk_mismatch"
                )
        source_zone_sets[period] = seen_source_zones
    if source_zone_sets["today"] != source_zone_sets["tomorrow"]:
        raise DpcNationalZoneSnapshotError("dpc_zone_period_catalog_mismatch")

    records.sort(
        key=lambda item: (item["forecast_day"], item["zone_id"], item["risk"])
    )
    return {
        "contract": DPC_ZONE_SNAPSHOT_CONTRACT,
        "schema_version": 1,
        "source": {
            "id": DPC_NATIONAL_ALERTS_SOURCE_ID,
            "authority": "Dipartimento della Protezione Civile",
        },
        "revision": {
            "id": f"DPC_ZONE_STATE_{revision}",
            "source_revision": revision,
            "sha256": hashlib.sha256(raw).hexdigest(),
        },
        "coverage": "all_zones_two_days",
        "can_confirm_green": True,
        "zone_count": len(source_zone_sets["today"]),
        "active": any(
            (record["level_rank"] or 0) > 0
            for record in records
            if record["transmission_status"] == "transmitted"
        ),
        "records": records,
    }


def reconcile_dpc_cap_and_zone_snapshot(
    cap: dict[str, Any], zone_snapshot: dict[str, Any]
) -> dict[str, Any]:
    """Require CAP and complete zone tables to describe one coherent revision."""

    if (
        cap.get("contract") != DPC_NATIONAL_ALERTS_CONTRACT
        or zone_snapshot.get("contract") != DPC_ZONE_SNAPSHOT_CONTRACT
        or cap.get("source", {}).get("id") != DPC_NATIONAL_ALERTS_SOURCE_ID
        or zone_snapshot.get("source", {}).get("id")
        != DPC_NATIONAL_ALERTS_SOURCE_ID
    ):
        raise DpcNationalZoneSnapshotError("dpc_zone_contract_mismatch")
    try:
        cap_sent = datetime.fromisoformat(
            str(cap["revision"]["sent_at"]).replace("Z", "+00:00")
        ).astimezone(_ROME)
        source_revision = str(zone_snapshot["revision"]["source_revision"])
    except (KeyError, TypeError, ValueError) as error:
        raise DpcNationalZoneSnapshotError("dpc_zone_revision_mismatch") from error
    if cap_sent.strftime("%Y%m%d_%H%M") != source_revision:
        raise DpcNationalZoneSnapshotError("dpc_zone_revision_mismatch")

    zone_records = zone_snapshot.get("records")
    cap_records = cap.get("records")
    if not isinstance(zone_records, list) or not isinstance(cap_records, list):
        raise DpcNationalZoneSnapshotError("dpc_zone_records_missing")
    complete_by_key = {
        (record["zone_id"], record["risk"], record["forecast_day"]): record
        for record in zone_records
    }
    expected_reported: set[tuple[str, str, str, str | None, str]] = set()
    for record in zone_records:
        if record.get("level") != "green":
            expected_reported.add(
                (
                    record["zone_id"],
                    record["risk"],
                    record["forecast_day"],
                    record.get("level"),
                    record["transmission_status"],
                )
            )

    observed_reported: set[tuple[str, str, str, str | None, str]] = set()
    for record in cap_records:
        try:
            valid_from = datetime.fromisoformat(record["valid_from"])
            valid_to = datetime.fromisoformat(record["valid_to"])
            zone_id = record["zone_id"]
            risk = record["risk"]
        except (KeyError, TypeError, ValueError) as error:
            raise DpcNationalZoneSnapshotError("dpc_zone_cap_record_invalid") from error
        matched = False
        for day_record in zone_records:
            if day_record["zone_id"] != zone_id or day_record["risk"] != risk:
                continue
            day_start = datetime.fromisoformat(day_record["valid_from"])
            day_end = datetime.fromisoformat(day_record["valid_to"])
            if day_start < valid_to and day_end >= valid_from:
                key = (zone_id, risk, day_record["forecast_day"])
                complete = complete_by_key[key]
                state = (
                    complete.get("level"),
                    complete["transmission_status"],
                )
                if state != (
                    record.get("level"),
                    record["transmission_status"],
                ):
                    raise DpcNationalZoneSnapshotError(
                        "dpc_zone_cap_state_mismatch"
                    )
                observed_reported.add(
                    (
                        zone_id,
                        risk,
                        complete["forecast_day"],
                        complete.get("level"),
                        complete["transmission_status"],
                    )
                )
                matched = True
        if not matched:
            raise DpcNationalZoneSnapshotError("dpc_zone_cap_zone_missing")
    if observed_reported != expected_reported:
        raise DpcNationalZoneSnapshotError("dpc_zone_cap_coverage_mismatch")

    reconciled = dict(zone_snapshot)
    reconciled["cap_revision"] = dict(cap["revision"])
    reconciled["reconciled"] = True
    reconciled["active"] = bool(cap.get("active"))
    return reconciled


__all__ = [
    "DPC_ZONE_SNAPSHOT_CONTRACT",
    "DpcNationalZoneSnapshotError",
    "parse_dpc_national_zone_zip",
    "reconcile_dpc_cap_and_zone_snapshot",
]
