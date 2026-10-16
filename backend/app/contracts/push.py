from __future__ import annotations

from datetime import datetime
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


def _normalize_installation_id(value: str) -> str:
    normalized = value.strip().lower()
    if len(normalized) != 32 or any(
        character not in "0123456789abcdef" for character in normalized
    ):
        raise ValueError("installation_id_must_be_random_128_bit_hex")
    return normalized


class PushMunicipality(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    istat: str = Field(pattern=r"^\d{6}$")
    name: str = Field(min_length=1, max_length=120)


class PushLocality(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    id: str = Field(min_length=1, max_length=160)
    name: str = Field(min_length=1, max_length=160)


class PushLocationEvidence(BaseModel):
    """Fresh, quality-bounded evidence for location-targeted local notices."""

    model_config = ConfigDict(extra="forbid")

    captured_at: datetime
    accuracy_m: float = Field(ge=0, le=250)


class PushPreferences(BaseModel):
    model_config = ConfigDict(extra="forbid")

    official_alerts: bool = True
    weather_notices: bool = True


class PushRegistration(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    kind: Literal["firebase_installation_id"]
    value: str = Field(
        min_length=22,
        max_length=22,
        pattern=r"^[cdef][A-Za-z0-9_-]{21}$",
    )


class PushDeviceRegisterRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    installation_id: str = Field(min_length=32, max_length=32)
    token: str | None = Field(default=None, min_length=20, max_length=4096)
    platform: Literal["android", "web"]
    registration: PushRegistration | None = None
    app_version: str = Field(min_length=1, max_length=64)
    language: Literal["it", "fur"] = "it"
    municipality: PushMunicipality | None = None
    locality: PushLocality | None = None
    location_mode: Literal["automatic_gps", "manual_selection"] | None = None
    location_evidence: PushLocationEvidence | None = None
    preferences: PushPreferences = Field(default_factory=PushPreferences)

    @model_validator(mode="after")
    def locality_requires_municipality(self) -> "PushDeviceRegisterRequest":
        if self.locality is not None and self.municipality is None:
            raise ValueError("locality_requires_municipality")
        if self.location_mode is not None and self.municipality is None:
            raise ValueError("location_mode_requires_canonical_municipality")
        if self.location_mode == "automatic_gps" and self.platform != "android":
            raise ValueError("automatic_location_requires_android")
        if self.location_mode == "automatic_gps" and self.location_evidence is None:
            raise ValueError("automatic_location_requires_evidence")
        if self.location_mode == "manual_selection" and self.location_evidence is not None:
            raise ValueError("manual_location_forbids_gps_evidence")
        if self.location_evidence is not None and self.location_mode != "automatic_gps":
            raise ValueError("location_evidence_requires_automatic_mode")
        return self

    @field_validator("installation_id")
    @classmethod
    def installation_id_must_be_random_128_bit(cls, value: str) -> str:
        return _normalize_installation_id(value)

    @model_validator(mode="after")
    def registration_matches_platform(self) -> "PushDeviceRegisterRequest":
        if self.platform == "android":
            if not self.token or self.registration is not None:
                raise ValueError("android_requires_legacy_fcm_token")
            return self
        if self.token is not None or self.registration is None:
            raise ValueError("web_requires_firebase_installation_id")
        return self

    def delivery_target(self) -> tuple[str, str]:
        if self.platform == "android":
            return "fcm_token", str(self.token or "")
        assert self.registration is not None
        return self.registration.kind, self.registration.value


class PushDeviceUnregisterRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    installation_id: str = Field(min_length=32, max_length=32)

    @field_validator("installation_id")
    @classmethod
    def installation_id_must_be_random_128_bit(cls, value: str) -> str:
        return _normalize_installation_id(value)


class PushDeviceLocationUpdateRequest(BaseModel):
    """Ephemeral native fix used to refresh one registered Android target."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    installation_id: str = Field(min_length=32, max_length=32)
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    accuracy_m: float = Field(ge=0, le=250)
    captured_at: datetime
    trigger: Literal[
        "app_foreground",
        "boot",
        "configure",
        "geofence_exit",
        "manual_refresh",
        "periodic",
    ]

    @field_validator("installation_id")
    @classmethod
    def installation_id_must_be_random_128_bit(cls, value: str) -> str:
        return _normalize_installation_id(value)


class PushCanonicalDataPoint(BaseModel):
    """Public locality/municipality point approved for weather requests."""

    model_config = ConfigDict(extra="forbid")

    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    source: Literal[
        "rafvg_irdat_5000",
        "municipality_catalog",
        "nominatim_place",
    ]


class PushDeviceLocationUpdateResponse(BaseModel):
    updated: bool
    status: Literal[
        "ambiguous_boundary",
        "external_place",
        "outside_fvg",
        "resolved",
    ]
    local_target_eligible: bool = False
    display_name: str = ""
    municipality: PushMunicipality | None = None
    locality: PushLocality | None = None
    data_point: PushCanonicalDataPoint | None = None


class ActiveAlertDeliveryResponse(BaseModel):
    status: str
    attempted: int = 0
    sent: int = 0
    sent_unconfirmed: int = 0
    deduplicated: int = 0
    failed: int = 0


class PushDeviceRegisterResponse(BaseModel):
    device_id: str
    registered: bool = True
    created: bool
    local_target_eligible: bool = False
    active_alert_delivery: ActiveAlertDeliveryResponse


class PushDeviceUnregisterResponse(BaseModel):
    unregistered: bool
