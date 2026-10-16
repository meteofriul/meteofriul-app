import re
import unicodedata
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


CommunityReportTypeId = Literal[
    "fog",
    "hail",
    "ice",
    "quiet",
    "rain",
    "snow",
    "storm",
    "wind",
]
CommunityFlagReason = Literal["inaccurate", "duplicate", "misuse"]
CommunityIdentitySubjectId = Literal[
    "crot",
    "ruie",
    "ors",
    "acuile",
    "pufe",
    "bolp",
    "suris",
    "sghirate",
    "cocal",
    "sarpint",
    "stele",
    "cjan",
    "gjat",
    "cisile",
    "cjaval",
    "cjavre",
    "flor",
    "plante",
    "rol",
    "cjariese",
    "claf",
    "cjampane",
    "clap",
    "cjistiel",
    "cjapiel",
    "cjicare",
    "cevron",
    "civo",
    "lof",
    "tasso",
    "gial",
    "scarpete",
    "cjar",
    "sfuei",
    "sedon",
    "cjalcjut",
    "tapon",
    "cenc",
]
CommunityIdentityPaletteId = Literal[
    "sky",
    "cobalt",
    "lagoon",
    "gold",
    "slate",
    "night",
]
CommunityIdentityPatternId = Literal[
    "diagonal",
    "halo",
    "split",
    "orbit",
]
COMMUNITY_IDENTITY_SUBJECT_LABELS = {
    "crot": "Crot",
    "ruie": "Ruie",
    "ors": "Ors",
    "acuile": "Acuile",
    "pufe": "Pufe",
    "bolp": "Bolp",
    "suris": "Surîs",
    "sghirate": "Sghirate",
    "cocal": "Cocâl",
    "sarpint": "Sarpint",
    "stele": "Stele",
    "cjan": "Cjan",
    "gjat": "Gjat",
    "cisile": "Cisile",
    "cjaval": "Cjaval",
    "cjavre": "Cjavre",
    "flor": "Flôr",
    "plante": "Plante",
    "rol": "Rôl",
    "cjariese": "Cjariese",
    "claf": "Clâf",
    "cjampane": "Cjampane",
    "clap": "Clap",
    "cjistiel": "Cjistiel",
    "cjapiel": "Cjapiel",
    "cjicare": "Cjicare",
    "cevron": "Cevron",
    "civo": "Civo",
    "lof": "Lôf",
    "tasso": "Tasso",
    "gial": "Gial",
    "scarpete": "Scarpete",
    "cjar": "Cjar",
    "sfuei": "Sfuei",
    "sedon": "Sedon",
    "cjalcjut": "Cjalcjut",
    "tapon": "Tapòn",
    "cenc": "Cenc",
}
COMMUNITY_IDENTITY_EPITHETS = frozenset({
    "di Aur",
    "dal Bosc",
    "dal Fogolâr",
    "dal Cîl",
    "de Tiare",
    "dal Troi",
    "de Mont",
    "dal Riu",
    "dal Vint",
    "de Lune",
    "dal Plan",
    "de Ploe",
})


class CommunityIdentityAvatarSnapshot(BaseModel):
    """Small allowlisted recipe used to render one anonymous avatar."""

    model_config = ConfigDict(extra="forbid")

    palette_id: CommunityIdentityPaletteId
    pattern_id: CommunityIdentityPatternId
    variant: int = Field(ge=0, le=3, strict=True)
    angle: Literal[45, 90, 135]

    @field_validator("angle", mode="before")
    @classmethod
    def validate_strict_angle(cls, value: object) -> object:
        if type(value) is not int:
            raise ValueError("identity_avatar_angle_must_be_integer")
        return value


class CommunityIdentitySnapshot(BaseModel):
    """Immutable public display data copied into a community report."""

    model_config = ConfigDict(extra="forbid")

    version: Literal[1]
    alias: str = Field(min_length=3, max_length=64)
    subject_id: CommunityIdentitySubjectId
    avatar: CommunityIdentityAvatarSnapshot

    @field_validator("version", mode="before")
    @classmethod
    def validate_strict_version(cls, value: object) -> object:
        if type(value) is not int:
            raise ValueError("identity_version_must_be_integer")
        return value

    @field_validator("alias")
    @classmethod
    def validate_alias(cls, value: str) -> str:
        alias = re.sub(r" +", " ", unicodedata.normalize("NFC", value).strip())
        if len(alias) < 3 or len(alias) > 64:
            raise ValueError("identity_alias_length_invalid")
        if not alias[0].isalpha() or not alias[-1].isalpha():
            raise ValueError("identity_alias_boundary_invalid")

        previous_was_latin = False
        for character in alias:
            category = unicodedata.category(character)
            if category.startswith("L"):
                if "LATIN" not in unicodedata.name(character, ""):
                    raise ValueError("identity_alias_must_use_latin_letters")
                previous_was_latin = True
                continue
            if category.startswith("M"):
                if not previous_was_latin:
                    raise ValueError("identity_alias_combining_mark_invalid")
                continue
            if character in {" ", "'", "’", "-", "·"}:
                previous_was_latin = False
                continue
            raise ValueError("identity_alias_character_invalid")
        return alias

    @model_validator(mode="after")
    def validate_alias_subject_pair(self) -> "CommunityIdentitySnapshot":
        subject_label = COMMUNITY_IDENTITY_SUBJECT_LABELS[self.subject_id]
        current_aliases = {
            f"{subject_label} {epithet}"
            for epithet in COMMUNITY_IDENTITY_EPITHETS
        }
        legacy_prefix = f"{subject_label} di "
        is_legacy_alias = (
            self.alias.startswith(legacy_prefix)
            and len(self.alias) > len(legacy_prefix)
        )
        if self.alias not in current_aliases and not is_legacy_alias:
            raise ValueError("identity_alias_subject_mismatch")
        return self


class CommunitySourceIdentity(BaseModel):
    """One public source key paired with its optional report snapshot."""

    model_config = ConfigDict(extra="forbid")

    sourceKey: str = Field(
        min_length=24,
        max_length=24,
        pattern=r"^[0-9a-f]{24}$",
    )
    identity: CommunityIdentitySnapshot | None = None


class WebcamRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    group: str = ""
    category: str = ""
    area: str = ""
    municipality: str | None = None
    mapClusterId: str | None = Field(
        default=None,
        max_length=80,
        pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$",
    )
    mapClusterLabel: str | None = Field(default=None, max_length=120)
    imageUrl: str | None = None
    fallbackImageUrl: str | None = None
    provider: str = ""
    sourcePage: str = ""
    sourceCheckUrl: str | None = None
    sourceCheckExpectedId: str | None = Field(default=None, exclude=True)
    attribution: str | None = None
    attributionUrl: str | None = None
    lat: float | None = Field(default=None, ge=-90, le=90)
    lon: float | None = Field(default=None, ge=-180, le=180)
    health: str = "ok"
    checkedAt: str = ""
    sortOrder: int = 999
    playerUrl: str | None = None
    mediaType: str | None = None

    @model_validator(mode="after")
    def validate_map_cluster_pair(self):
        if bool(self.mapClusterId) != bool(self.mapClusterLabel):
            raise ValueError("mapClusterId and mapClusterLabel must be provided together")
        return self


class WebcamManifestResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ok: bool
    status: str
    source: str
    source_url: str = ""
    version: int = 1
    source_updated_at: str | None = None
    generated_at: str | None = None
    count: int = Field(ge=0)
    webcams: list[WebcamRecord]


class CommunityReportCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type_id: str = Field(min_length=2, max_length=24)
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    selected_place: str | None = Field(default=None, max_length=80)
    client_id: str = Field(default="", max_length=128)
    accepted_terms: bool = Field(default=False, strict=True)
    policy_version: str = Field(default="", max_length=64)
    identity: CommunityIdentitySnapshot | None = None


class CommunityReportConfirmationCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    vote: str = Field(min_length=2, max_length=3)
    client_id: str = Field(default="", max_length=128)
    accepted_terms: bool = Field(default=False, strict=True)
    policy_version: str = Field(default="", max_length=64)


class CommunityReportFlagCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: CommunityFlagReason
    client_id: str = Field(default="", max_length=128)


class CommunityReportDelete(BaseModel):
    model_config = ConfigDict(extra="forbid")

    client_id: str = Field(default="", max_length=128)


class CommunityReputationRequest(BaseModel):
    """Private lookup input; the raw installation id is never returned."""

    model_config = ConfigDict(extra="forbid")

    client_id: str = Field(default="", max_length=128)


class CommunityReputationRank(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: Literal["novice", "lookout", "sentinel"]
    label: Literal[
        "Osservadôr dal Cîl",
        "Vuaite dal Timp",
        "Sentinele dal Teritori",
    ]
    min_points: int = Field(ge=0)
    next_rank_at: int | None = Field(default=None, ge=0)


class ConfirmationCounts(BaseModel):
    model_config = ConfigDict(extra="forbid")

    yes: int = Field(default=0, ge=0)
    no: int = Field(default=0, ge=0)


class CommunityReportPublic(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    typeId: str
    typeCategory: str
    groupId: str
    place: str
    lat: float
    lon: float
    locationPrecision: str = "zone"
    x: float
    y: float
    createdAt: int
    expiresAt: int
    time: str
    source: str = "community"
    sourceKey: str | None = None
    identity: CommunityIdentitySnapshot | None = None


class CommunityReportGroup(CommunityReportPublic):
    reportIds: list[str]
    sourceKeys: list[str] | None = None
    identities: list[CommunitySourceIdentity] | None = None
    count: int = Field(ge=1)
    confirmations: ConfirmationCounts


class CommunityLocation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    place: str
    lat: float
    lon: float


class CommunitySource(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    type: str | None = None
    verified: bool | None = None
    storage: str
    cooldown_storage: str | None = None


class CommunityPublicSourceKeyContract(BaseModel):
    model_config = ConfigDict(extra="forbid")

    algorithm: Literal["sha256-truncated-lower-hex"]
    pattern: Literal["^[0-9a-f]{24}$"]
    length: Literal[24]
    rotation_bucket_seconds: Literal[86400]


class CommunitySafetyContract(BaseModel):
    """Machine-readable safety contract owned by the running revision."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["community-ephemeral-safety-v1"]
    guidelines_policy_version: Literal["community-guidelines-v2"]
    allowed_report_types: tuple[CommunityReportTypeId, ...]
    create_fields: tuple[str, ...]
    public_report_fields: tuple[str, ...]
    public_group_fields: tuple[str, ...]
    confirmation_fields: tuple[str, ...]
    location_fields: tuple[str, ...]
    source_fields: tuple[str, ...]
    flag_reasons: tuple[CommunityFlagReason, ...]
    ttl_seconds: Literal[3600]
    cooldown_seconds: Literal[2700]
    max_distance_km: Literal[5]
    location_catalog_count: Literal[215]
    location_catalog_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    location_catalog_digest_algorithm: Literal[
        "sha256-ordered-place-lat5-lon5-lines-v1"
    ]
    location_precision: Literal["zone"]
    accepts_free_text: Literal[False]
    accepts_media: Literal[False]
    requires_account: Literal[False]
    user_flag_visibility: Literal["local_only"]
    automatic_global_hide: Literal[False]
    public_source_key: CommunityPublicSourceKeyContract


class CommunityReportsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reports: list[CommunityReportPublic]
    map_groups: list[CommunityReportGroup]
    ttl_seconds: int
    cooldown_seconds: int
    max_distance_km: int
    locations: list[CommunityLocation]
    generated_at: str
    source: CommunitySource
    contract: CommunitySafetyContract


class CommunityReportCreatedResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    report: CommunityReportPublic
    cooldown_until: int
    undo_until: int
    undo_window_seconds: int
    ttl_seconds: int
    source: CommunitySource


class CommunityReportDeletedResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ok: bool
    report_id: str
    source: CommunitySource


class CommunityReportFlaggedResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ok: bool
    group_id: str
    reason: CommunityFlagReason
    hidden: bool
    hidden_global: bool
    flag_count: int = Field(ge=0)
    already_reported: bool
    retention_seconds: int = Field(gt=0)
    source: CommunitySource


class CommunityConfirmationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    group_id: str
    vote: str
    confirmations: ConfirmationCounts
    group: CommunityReportGroup
    source: CommunitySource


class CommunityReputationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    points: int = Field(ge=0)
    total_reports: int = Field(ge=0)
    validated_reports: int = Field(ge=0)
    pending_reports: int = Field(ge=0)
    rank: CommunityReputationRank
    max_daily_awards: int | None = Field(default=None, gt=0)
    retention_seconds: int = Field(gt=0)
    source: CommunitySource
