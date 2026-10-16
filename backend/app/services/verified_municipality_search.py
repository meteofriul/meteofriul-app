"""Search canonical ISTAT municipality identities for manual selection.

These records complement, but never infer an identity from, geocoder results.
The representative point is used only when an exact geocoder city result is
unavailable; the alert identity always comes from the pinned ISTAT catalog.
"""

from __future__ import annotations

from app.contracts.location import LocationSearchItem
from app.services.national_municipalities import (
    NationalMunicipality,
    NationalMunicipalityCatalog,
    get_default_national_municipality_catalog,
    normalize_municipality_identity,
)


def _rank(municipality: NationalMunicipality, query: str) -> int:
    name = normalize_municipality_identity(municipality.name)
    province = normalize_municipality_identity(municipality.province_code)
    if query in {name, f"{name} {province}"}:
        return 100
    if name.startswith(query):
        return 90
    if any(part.startswith(query) for part in name.split()):
        return 80
    if query in name:
        return 70
    return 0


def search_verified_municipalities(
    query: str,
    *,
    catalog: NationalMunicipalityCatalog | None = None,
    limit: int = 8,
) -> list[LocationSearchItem]:
    """Return actual Comuni; never create an ISTAT code from a place name."""

    normalized_query = normalize_municipality_identity(query)
    if len(normalized_query) < 2:
        return []
    source = catalog or get_default_national_municipality_catalog()
    matches = [
        municipality
        for municipality in source.municipalities
        if _rank(municipality, normalized_query) > 0
        and municipality.latitude is not None
        and municipality.longitude is not None
    ]
    matches.sort(
        key=lambda municipality: (
            -_rank(municipality, normalized_query),
            normalize_municipality_identity(municipality.name),
            municipality.province_code,
            municipality.istat_code,
        )
    )
    return [
        LocationSearchItem(
            name=municipality.name,
            # The pinned ISTAT source uses a hyphen here; preserve the
            # established app region label so FVG quick places and routing
            # continue to share the same territorial identity.
            admin1=(
                "Friuli Venezia Giulia"
                if municipality.region_iso == "IT-36"
                else municipality.region_name
            ),
            latitude=municipality.latitude,
            longitude=municipality.longitude,
            province=municipality.province_code,
            provinceName=municipality.province_name,
            istatCode=municipality.istat_code,
            country="Italia",
            countryCode="IT",
            provider="istat_municipality_catalog",
            providerId=municipality.istat_code,
        )
        for municipality in matches[: max(1, min(limit, 8))]
    ]
