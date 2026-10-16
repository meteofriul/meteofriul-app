"""Central rollout policy for territory-scoped Meteo Friûl capabilities.

Eligibility is intentionally separate from provider freshness and health. An
unsupported source must never be presented as a temporary network failure.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


TerritoryStatus = Literal["enabled", "pilot", "planned", "unsupported"]

TERRITORY_POLICY_VERSION = "territory-policy-v2"
ITALY_SCOPE_ID = "IT"
FVG_REGION_ID = "IT-36"
ITALIAN_REGION_IDS = frozenset({
    "IT-21", "IT-23", "IT-25", "IT-32", "IT-34", "IT-36", "IT-42",
    "IT-45", "IT-52", "IT-55", "IT-57", "IT-62", "IT-65", "IT-67",
    "IT-72", "IT-75", "IT-77", "IT-78", "IT-82", "IT-88",
})

COMMUNITY_READ_SCOPE = ITALY_SCOPE_ID
COMMUNITY_WRITE_SCOPE = ITALY_SCOPE_ID
EDITORIAL_SCOPE_ID = FVG_REGION_ID

COMMUNITY_REGION_NOT_ENABLED_CODE = "community_region_not_enabled"
COMMUNITY_REGION_NOT_ENABLED_MESSAGE = (
    "Le segnalazioni partecipative sono disponibili solo da una posizione in Italia."
)


@dataclass(frozen=True)
class SourceEligibility:
    provider: str
    scope_id: str
    status: TerritoryStatus


def source_eligibility(*, region_id: str | None) -> dict[str, SourceEligibility]:
    """Return source coverage without inspecting provider runtime state."""

    normalized_region = str(region_id or "").strip().upper()
    in_italy = normalized_region == ITALY_SCOPE_ID or normalized_region in ITALIAN_REGION_IDS
    in_fvg = normalized_region == FVG_REGION_ID
    return {
        "forecast": SourceEligibility(
            "icon-2i", ITALY_SCOPE_ID, "enabled" if in_italy else "unsupported"
        ),
        "radar": SourceEligibility(
            "radar-dpc", ITALY_SCOPE_ID, "enabled" if in_italy else "unsupported"
        ),
        "national_alerts": SourceEligibility(
            "dpc", ITALY_SCOPE_ID, "planned" if in_italy else "unsupported"
        ),
        "icon2i": SourceEligibility(
            "icon-2i", ITALY_SCOPE_ID, "enabled" if in_italy else "unsupported"
        ),
        "osmer": SourceEligibility(
            "osmer-arpa-fvg",
            FVG_REGION_ID,
            "enabled" if in_fvg else "unsupported",
        ),
        "webcams": SourceEligibility(
            "fvg-editorial-webcams",
            FVG_REGION_ID,
            "enabled" if in_fvg else "unsupported",
        ),
    }


def community_write_enabled(*, region_id: str | None) -> bool:
    normalized_region = str(region_id or "").strip().upper()
    return normalized_region == ITALY_SCOPE_ID or normalized_region in ITALIAN_REGION_IDS


def community_region_not_enabled_detail() -> dict[str, object]:
    return {
        "code": COMMUNITY_REGION_NOT_ENABLED_CODE,
        "message": COMMUNITY_REGION_NOT_ENABLED_MESSAGE,
        "policy_version": TERRITORY_POLICY_VERSION,
        "read_scope": COMMUNITY_READ_SCOPE,
        "write_scope": COMMUNITY_WRITE_SCOPE,
        "enabled_regions": sorted(ITALIAN_REGION_IDS),
    }
