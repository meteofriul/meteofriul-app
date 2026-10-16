"""Strict, side-effect-free parser for the national DPC CAP bulletin.

The CAP document lists the criticalities explicitly transmitted in one
bulletin revision.  It is not a complete green-state catalogue: callers must
pair it with the matching, verified zone dataset before absence can mean
``green`` or before a location-aware notification can be sent.

This module deliberately has no network, persistence or FVG runtime hooks.
It establishes the national zone/risk contract while preserving the existing
regional alert path unchanged.
"""

from __future__ import annotations

import hashlib
import re
import unicodedata
from datetime import datetime, timedelta
from typing import Any
from xml.etree import ElementTree


DPC_CAP_NAMESPACE = "urn:oasis:names:tc:emergency:cap:1.2"
DPC_NATIONAL_ALERTS_CONTRACT = "meteofriul.official_alert_zones.v1"
DPC_NATIONAL_ALERTS_SOURCE_ID = "dpc_national_criticality_bulletin"
DPC_CAP_MAX_BYTES = 2 * 1024 * 1024

_CAP = f"{{{DPC_CAP_NAMESPACE}}}"
_SAFE_ZONE_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}\Z")
_SAFE_REVISION_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,159}\Z")
_FVG_DPC_ZONE = re.compile(r"Friu-([A-D])\Z", re.IGNORECASE)
_LEVEL_RANK = {"green": 0, "yellow": 1, "orange": 2, "red": 3}


class DpcNationalAlertContractError(ValueError):
    """The DPC document cannot safely satisfy the zonal alert contract."""


def _normalized_text(value: Any) -> str:
    decomposed = unicodedata.normalize("NFKD", str(value or ""))
    without_marks = "".join(
        character
        for character in decomposed
        if not unicodedata.combining(character)
    )
    return " ".join(without_marks.upper().split())


def _required_text(parent: ElementTree.Element, name: str) -> str:
    element = parent.find(f"{_CAP}{name}")
    value = "" if element is None else str(element.text or "").strip()
    if not value:
        raise DpcNationalAlertContractError(f"dpc_cap_missing_{name}")
    return value


def _parse_datetime(value: str, field: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise DpcNationalAlertContractError(
            f"dpc_cap_invalid_{field}"
        ) from error
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise DpcNationalAlertContractError(f"dpc_cap_invalid_{field}")
    return parsed


def canonical_dpc_zone_id(source_zone_id: Any) -> str:
    """Return one stable alert-zone identity without guessing aliases.

    DPC's ``Friu-A`` ... ``Friu-D`` are the same four official areas exposed
    by the regional FVG source as ``FVG-A`` ... ``FVG-D``.  They are the only
    cross-source aliases approved here.  Other national identifiers remain
    namespaced to DPC until a reviewed regional alias catalogue says otherwise.
    """

    value = str(source_zone_id or "").strip()
    if not _SAFE_ZONE_ID.fullmatch(value):
        raise DpcNationalAlertContractError("dpc_cap_invalid_zone_id")
    fvg_match = _FVG_DPC_ZONE.fullmatch(value)
    if fvg_match:
        return f"FVG-{fvg_match.group(1).upper()}"
    return f"DPC:{value}"


def _risk_from_event(event: str) -> str:
    normalized = _normalized_text(event)
    matches = [
        risk
        for marker, risk in (
            ("IDROGEOLOGIC", "hydrogeological"),
            ("TEMPORAL", "thunderstorm"),
            ("IDRAULIC", "hydraulic"),
        )
        if marker in normalized
    ]
    if len(matches) != 1:
        raise DpcNationalAlertContractError("dpc_cap_invalid_risk")
    return matches[0]


def _level_from_event(event: str, description: str) -> tuple[str | None, str]:
    normalized = _normalized_text(f"{event} {description}")
    if "VALUTAZIONE NON TRASMESSA" in normalized:
        return None, "not_transmitted"
    levels = [
        level
        for markers, level in (
            (("ALLERTA ROSSA", "ELEVATA CRITICITA"), "red"),
            (("ALLERTA ARANCIONE", "MODERATA CRITICITA"), "orange"),
            (("ALLERTA GIALLA", "ORDINARIA CRITICITA"), "yellow"),
            (("NESSUNA ALLERTA", "ASSENZA DI CRITICITA"), "green"),
        )
        if any(marker in normalized for marker in markers)
    ]
    if len(levels) != 1:
        raise DpcNationalAlertContractError("dpc_cap_invalid_level")
    return levels[0], "transmitted"


def _zone_from_area(area: ElementTree.Element) -> tuple[str, str, str]:
    zone_name = _required_text(area, "areaDesc")
    zone_values: list[str] = []
    for geocode in area.findall(f"{_CAP}geocode"):
        value_name = _normalized_text(_required_text(geocode, "valueName"))
        if value_name != "ZONA DI ALLERTA":
            continue
        zone_values.append(_required_text(geocode, "value"))
    if len(zone_values) != 1:
        raise DpcNationalAlertContractError("dpc_cap_invalid_zone_geocode")
    source_zone_id = zone_values[0]
    return canonical_dpc_zone_id(source_zone_id), source_zone_id, zone_name


def parse_dpc_national_cap(payload: bytes | str) -> dict[str, Any]:
    """Parse one DPC CAP revision into deterministic zone/risk records.

    The returned snapshot is safe for comparison and later reconciliation.  It
    explicitly sets ``can_confirm_green`` to ``False`` because CAP alone does
    not prove the state of omitted zones.  A separate, same-revision zone
    dataset must provide that proof.
    """

    raw = payload.encode("utf-8") if isinstance(payload, str) else bytes(payload)
    if not raw or len(raw) > DPC_CAP_MAX_BYTES:
        raise DpcNationalAlertContractError("dpc_cap_invalid_size")
    lowered_prefix = raw[:1024].lower()
    if b"<!doctype" in lowered_prefix or b"<!entity" in lowered_prefix:
        raise DpcNationalAlertContractError("dpc_cap_unsafe_xml")
    try:
        root = ElementTree.fromstring(raw)
    except ElementTree.ParseError as error:
        raise DpcNationalAlertContractError("dpc_cap_invalid_xml") from error
    if root.tag != f"{_CAP}alert":
        raise DpcNationalAlertContractError("dpc_cap_invalid_root")

    revision_id = _required_text(root, "identifier")
    if not _SAFE_REVISION_ID.fullmatch(revision_id):
        raise DpcNationalAlertContractError("dpc_cap_invalid_identifier")
    sender = _required_text(root, "sender")
    sent_text = _required_text(root, "sent")
    sent = _parse_datetime(sent_text, "sent")
    status = _required_text(root, "status")
    message_type = _required_text(root, "msgType")
    scope = _required_text(root, "scope")
    if status != "Actual" or message_type not in {"Alert", "Update"} or scope != "Public":
        raise DpcNationalAlertContractError("dpc_cap_not_public_actual")

    records: list[dict[str, Any]] = []
    identities: dict[tuple[str, str, str, str], tuple[str | None, str]] = {}
    for info in root.findall(f"{_CAP}info"):
        event = _required_text(info, "event")
        description = _required_text(info, "description")
        risk = _risk_from_event(event)
        level, transmission_status = _level_from_event(event, description)
        if risk == "thunderstorm" and level == "red":
            raise DpcNationalAlertContractError(
                "dpc_cap_thunderstorm_red_not_supported"
            )
        onset_text = _required_text(info, "onset")
        expires_text = _required_text(info, "expires")
        onset = _parse_datetime(onset_text, "onset")
        expires = _parse_datetime(expires_text, "expires")
        if expires <= onset or (expires - onset).total_seconds() > 72 * 60 * 60:
            raise DpcNationalAlertContractError("dpc_cap_invalid_validity")
        bulletin_floor = sent.replace(hour=0, minute=0, second=0, microsecond=0)
        if onset < bulletin_floor - timedelta(days=1):
            raise DpcNationalAlertContractError("dpc_cap_invalid_validity")

        areas = info.findall(f"{_CAP}area")
        if not areas:
            raise DpcNationalAlertContractError("dpc_cap_missing_area")
        for area in areas:
            zone_id, source_zone_id, zone_name = _zone_from_area(area)
            identity = (zone_id, risk, onset_text, expires_text)
            state = (level, transmission_status)
            previous = identities.get(identity)
            if previous is not None and previous != state:
                raise DpcNationalAlertContractError(
                    "dpc_cap_conflicting_zone_record"
                )
            if previous is not None:
                continue
            identities[identity] = state
            records.append(
                {
                    "zone_id": zone_id,
                    "source_zone_id": source_zone_id,
                    "zone_name": zone_name,
                    "risk": risk,
                    "level": level,
                    "level_rank": None if level is None else _LEVEL_RANK[level],
                    "transmission_status": transmission_status,
                    "valid_from": onset.isoformat(),
                    "valid_to": expires.isoformat(),
                }
            )

    records.sort(
        key=lambda item: (
            item["valid_from"],
            item["zone_id"],
            item["risk"],
            item["level_rank"] if item["level_rank"] is not None else -1,
        )
    )
    return {
        "contract": DPC_NATIONAL_ALERTS_CONTRACT,
        "schema_version": 1,
        "source": {
            "id": DPC_NATIONAL_ALERTS_SOURCE_ID,
            "authority": "Dipartimento della Protezione Civile",
            "sender": sender,
        },
        "revision": {
            "id": revision_id,
            "sent_at": sent.isoformat(),
            "message_type": message_type.lower(),
            "sha256": hashlib.sha256(raw).hexdigest(),
        },
        "coverage": "reported_zones_only",
        "can_confirm_green": False,
        "active": any(
            (record["level_rank"] or 0) > 0
            for record in records
            if record["transmission_status"] == "transmitted"
        ),
        "records": records,
    }


__all__ = [
    "DPC_NATIONAL_ALERTS_CONTRACT",
    "DPC_NATIONAL_ALERTS_SOURCE_ID",
    "DpcNationalAlertContractError",
    "canonical_dpc_zone_id",
    "parse_dpc_national_cap",
]
