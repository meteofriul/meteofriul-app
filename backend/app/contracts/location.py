from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class LocationSearchItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    admin1: str = "Friuli Venezia Giulia"
    latitude: float
    longitude: float
    population: int = Field(default=0, ge=0)
    # Preserve the original non-null response shape for distributed clients.
    # National results use empty strings when the upstream geocoder does not
    # expose an ISTAT/province identity.
    province: str = ""
    provinceName: str = ""
    istatCode: str = ""
    # Additive identity fields keep the original search shape compatible
    # while allowing clients to distinguish Italian results without inference.
    country: str = "Italia"
    countryCode: str = Field(default="IT", pattern=r"^[A-Z]{2}$")
    provider: str = ""
    providerId: str = ""


class ReverseLocationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    # Native GPS clients send the operating-system uncertainty radius.  Its
    # presence selects the fully offline FVG resolver.
    accuracyM: float | None = Field(default=None, ge=0, le=10_000)


class ReverseLocationLocality(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    kind: str
    source: Literal["rafvg_irdat_5000"]
    datasetVersion: str


class ReverseLocationMunicipality(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    istatCode: str = Field(pattern=r"^\d{6}$")
    province: str
    provinceName: str
    source: Literal["istat_boundaries"]
    datasetVersion: str


class ReverseLocationDataPoint(BaseModel):
    model_config = ConfigDict(extra="forbid")

    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    source: Literal[
        "rafvg_irdat_5000",
        "municipality_catalog",
        "nominatim_place",
    ]


class ReverseLocationResolution(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal[
        "resolved",
        "municipality_only",
        "external_place",
        "outside_fvg",
    ]
    municipalityResolved: bool
    localityCorroborated: bool
    matchMethod: Literal["name", "nearest"] | None = None
    distanceM: float | None = Field(default=None, ge=0)
    runnerUpDistanceM: float | None = Field(default=None, ge=0)
    boundaryDistanceM: float | None = Field(default=None, ge=0)


class ReverseLocationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # ``city`` remains the canonical municipality for compatibility with
    # already distributed clients. New clients should render ``displayName``.
    city: str
    displayName: str
    region: str
    country: str | None = None
    countryCode: str | None = Field(default=None, pattern=r"^[A-Z]{2}$")
    lat: float
    lon: float
    province: str | None = None
    provinceName: str | None = None
    istatCode: str | None = None
    locality: ReverseLocationLocality | None = None
    municipality: ReverseLocationMunicipality | None = None
    dataPoint: ReverseLocationDataPoint | None = None
    resolution: ReverseLocationResolution
