"""Canonical municipality routing for nationwide local weather notices."""

from __future__ import annotations

from typing import Any

from app.services.location import LocationCatalog, Municipality
from app.services.national_municipalities import (
    NationalMunicipality,
    NationalMunicipalityCatalog,
    get_default_national_municipality_catalog,
)


class NoticeMunicipalityCatalog:
    """Prefer polygon-backed FVG identities and extend exact lookup nationwide."""

    def __init__(
        self,
        *,
        fvg_catalog: LocationCatalog | None = None,
        national_catalog: NationalMunicipalityCatalog | None = None,
    ) -> None:
        self.fvg_catalog = fvg_catalog or LocationCatalog()
        self.national_catalog = (
            national_catalog or get_default_national_municipality_catalog()
        )

    def match_istat(
        self,
        value: Any,
    ) -> Municipality | NationalMunicipality | None:
        return self.fvg_catalog.match_istat(value) or self.national_catalog.match_istat(
            value
        )

    def match_names(
        self,
        *values: Any,
    ) -> Municipality | NationalMunicipality | None:
        return self.fvg_catalog.match_names(
            *values
        ) or self.national_catalog.match_names(*values)


__all__ = ["NoticeMunicipalityCatalog"]
