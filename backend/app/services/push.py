from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from typing import Any, Callable, Iterable
from urllib.parse import urlsplit

from app.contracts.push import (
    ActiveAlertDeliveryResponse,
    PushDeviceRegisterRequest,
    PushDeviceRegisterResponse,
    PushDeviceLocationUpdateRequest,
    PushDeviceLocationUpdateResponse,
    PushDeviceUnregisterResponse,
)
from app.infrastructure.firebase import get_firestore_client
from app.infrastructure.app_check import PushAppCheckContext
from app.push.fcm import (
    DEFAULT_WEB_APP_URL,
    DEFAULT_ANDROID_NOTIFICATION_CHANNEL,
    FcmBatchOutcome,
    FcmConfigurationError,
    FcmOfficialAlertMessage,
    FcmSenderUnavailable,
    FcmTokenInvalid,
    FirebaseCloudMessagingSender,
)
from app.repositories.push import (
    PUSH_TARGET_FCM_TOKEN,
    PushDeviceRepository,
    PushPilotCapacityReached,
    PushRepositoryUnavailable,
    hash_installation_id,
    hash_push_target,
    resolve_push_target,
)
from app.services.official_alerts import get_official_alerts_state
from app.services.location import LocationCatalog, LocationService
from app.services.national_municipalities import (
    NationalMunicipalityCatalog,
    get_default_national_municipality_catalog,
)
from app.services.fvg_geography import (
    FvgGeographyCatalog,
    get_default_fvg_geography_catalog,
)
from app.services.push_version_policy import (
    android_app_version_allowed,
    parse_min_play_version_code,
)


PUSH_MODE_ENV = "PUSH_OFFICIAL_ALERTS_MODE"
PUSH_MAX_DEVICES_ENV = "PUSH_PILOT_MAX_DEVICES"
PUSH_ALLOWED_INSTALLATION_HASHES_ENV = "PUSH_PILOT_ALLOWED_INSTALLATION_HASHES"
PUSH_ENROLLMENT_MODE_ENV = "PUSH_PILOT_ENROLLMENT_MODE"
PUSH_ENROLLMENT_GENERATION_ENV = "PUSH_ENROLLMENT_GENERATION"
PUSH_ANDROID_APP_IDS_ENV = "PUSH_APP_CHECK_ANDROID_APP_IDS"
PUSH_WEB_APP_IDS_ENV = "PUSH_APP_CHECK_WEB_APP_IDS"
PUSH_PLAY_BETA_ALLOWED_APP_VERSIONS_ENV = (
    "PUSH_PLAY_BETA_ALLOWED_APP_VERSIONS"
)
PUSH_PLAY_BETA_MIN_VERSION_CODE_ENV = "PUSH_PLAY_BETA_MIN_VERSION_CODE"
PUSH_TEST_MODE_ENV = "PUSH_PILOT_TEST_MODE"
PUSH_WEB_APP_URL_ENV = "PUSH_WEB_APP_URL"
PLAY_BETA_DEFAULT_PAGE_SIZE = 200
PLAY_BETA_MAX_PAGE_SIZE = 500
OFFICIAL_SOURCE_ID = "protezione_civile_fvg_alerts"
OFFICIAL_ACTIVE_SOURCE_MODES = frozenset(
    {
        "official_telegram_pdf_verified",
        "official_fvg_widget_arpa_corroborated",
        "official_page_arpa_corroborated",
        "official_telegram_arpa_corroborated",
    }
)
OFFICIAL_INACTIVE_SOURCE_MODES = frozenset(
    {
        "official_widget",
        "official_page",
        "arpa_pcr_mirror",
        "official_validity_expired",
    }
)
OFFICIAL_SOURCE_MODES = OFFICIAL_ACTIVE_SOURCE_MODES | OFFICIAL_INACTIVE_SOURCE_MODES
PUSH_TITLE = "Meteo Friûl"
MAX_NOTIFICATION_TTL_SECONDS = 6 * 60 * 60
MAX_OFFICIAL_SOURCE_AGE_SECONDS = 45 * 60
MAX_OFFICIAL_PDF_BYTES = 12 * 1024 * 1024
SOURCE_CLOCK_SKEW_SECONDS = 5 * 60
OFFICIAL_PDF_URL_PREFIX = "https://cfd.protezionecivile.fvg.it/docs/alerts/"
OFFICIAL_FVG_DOCUMENT_HOST = "pianiemergenza.protezionecivile.fvg.it"
_OFFICIAL_FVG_DOCUMENT_RE = re.compile(
    r"^/alerts/(?P<number>\d+)_(?P<year>\d{4})\.pdf$",
    re.IGNORECASE,
)
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_ENROLLMENT_GENERATION_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,63}$")
_ANDROID_FIREBASE_APP_ID_RE = re.compile(
    r"^1:\d+:android:[0-9a-f]+$", re.IGNORECASE
)
_WEB_FIREBASE_APP_ID_RE = re.compile(
    r"^1:\d+:web:[0-9a-f]+$", re.IGNORECASE
)
_CLIENT_APP_VERSION_RE = re.compile(r"^[a-z0-9][a-z0-9._+-]{0,63}$")
_LEVEL_RANK = {
    "verde": 0,
    "gialla": 1,
    "arancione": 2,
    "rossa": 3,
    "nera": 4,
}


class PushConfigurationError(RuntimeError):
    """A pilot setting is invalid; delivery must remain disabled."""


class PushInstallationNotAllowed(RuntimeError):
    """The installation is outside the optional owner allowlist."""


class PushMunicipalityInvalid(RuntimeError):
    """The supplied municipality does not match the canonical FVG catalog."""


class PushLocalityInvalid(RuntimeError):
    """The supplied locality is not canonical for the supplied municipality."""


class PushLocationEvidenceInvalid(RuntimeError):
    """The supplied GPS evidence is stale, imprecise, or temporally invalid."""


class PushPlatformNotAllowed(RuntimeError):
    """The verified Firebase app cannot register the requested platform."""


class PushDeviceNotRegistered(RuntimeError):
    """A background update cannot enroll or mutate an unknown installation."""


class PushAppVersionNotAllowed(RuntimeError):
    """The attested Play client build is outside the active release set."""


def _normalize_client_app_version(value: str) -> str:
    return str(value or "").strip().lower()


@dataclass(frozen=True)
class PushPilotConfig:
    mode: str
    max_devices: int
    allowed_installation_hashes: frozenset[str]
    enrollment_mode: str = "owner_allowlist"
    enrollment_generation: str = ""
    android_app_ids: frozenset[str] = frozenset()
    web_app_ids: frozenset[str] = frozenset()
    allowed_app_versions: frozenset[str] = frozenset()
    min_app_version_code: int | None = None
    web_app_url: str = DEFAULT_WEB_APP_URL

    @classmethod
    def from_environment(cls) -> "PushPilotConfig":
        mode = os.getenv(PUSH_MODE_ENV, "off").strip().lower() or "off"
        if mode not in {"off", "dry_run", "send"}:
            raise PushConfigurationError("push_mode_invalid")

        raw_hashes = os.getenv(PUSH_ALLOWED_INSTALLATION_HASHES_ENV, "")
        allowed_hashes = frozenset(
            value.strip().lower() for value in raw_hashes.split(",") if value.strip()
        )
        if any(not _SHA256_RE.fullmatch(value) for value in allowed_hashes):
            raise PushConfigurationError("push_installation_allowlist_invalid")

        enrollment_mode = (
            os.getenv(PUSH_ENROLLMENT_MODE_ENV, "owner_allowlist").strip().lower()
            or "owner_allowlist"
        )
        if enrollment_mode not in {"owner_allowlist", "private_test", "play_beta"}:
            raise PushConfigurationError("push_enrollment_mode_invalid")
        default_max_devices = (
            str(PLAY_BETA_DEFAULT_PAGE_SIZE)
            if enrollment_mode == "play_beta"
            else "1"
        )
        try:
            max_devices = int(
                os.getenv(PUSH_MAX_DEVICES_ENV, default_max_devices).strip()
                or default_max_devices
            )
        except ValueError as error:
            raise PushConfigurationError("push_max_devices_invalid") from error
        max_allowed_devices = (
            PLAY_BETA_MAX_PAGE_SIZE if enrollment_mode == "play_beta" else 10
        )
        if max_devices < 1 or max_devices > max_allowed_devices:
            raise PushConfigurationError("push_max_devices_invalid")

        if enrollment_mode in {"private_test", "play_beta"} and allowed_hashes:
            error_code = (
                "push_private_test_allowlist_conflict"
                if enrollment_mode == "private_test"
                else "push_play_beta_allowlist_conflict"
            )
            raise PushConfigurationError(error_code)
        if (
            mode == "send"
            and enrollment_mode == "owner_allowlist"
            and not allowed_hashes
        ):
            raise PushConfigurationError("push_owner_allowlist_required")

        enrollment_generation = os.getenv(
            PUSH_ENROLLMENT_GENERATION_ENV, ""
        ).strip().lower()
        if enrollment_mode == "play_beta":
            if not _ENROLLMENT_GENERATION_RE.fullmatch(enrollment_generation):
                raise PushConfigurationError(
                    "push_enrollment_generation_required"
                )
        elif enrollment_generation:
            raise PushConfigurationError(
                "push_enrollment_generation_mode_conflict"
            )

        android_app_ids = frozenset(
            value.strip()
            for value in os.getenv(PUSH_ANDROID_APP_IDS_ENV, "").split(",")
            if value.strip()
        )
        if any(
            not _ANDROID_FIREBASE_APP_ID_RE.fullmatch(value)
            for value in android_app_ids
        ):
            raise PushConfigurationError("push_android_app_id_invalid")
        if enrollment_mode == "play_beta" and not android_app_ids:
            raise PushConfigurationError("push_play_beta_android_app_id_required")

        web_app_ids = frozenset(
            value.strip()
            for value in os.getenv(PUSH_WEB_APP_IDS_ENV, "").split(",")
            if value.strip()
        )
        if any(
            not _WEB_FIREBASE_APP_ID_RE.fullmatch(value)
            for value in web_app_ids
        ):
            raise PushConfigurationError("push_web_app_id_invalid")
        if android_app_ids & web_app_ids:
            raise PushConfigurationError("push_app_id_platform_overlap")

        allowed_app_versions = frozenset(
            _normalize_client_app_version(value)
            for value in os.getenv(
                PUSH_PLAY_BETA_ALLOWED_APP_VERSIONS_ENV, ""
            ).split(",")
            if str(value or "").strip()
        )
        if any(
            not _CLIENT_APP_VERSION_RE.fullmatch(value)
            for value in allowed_app_versions
        ):
            raise PushConfigurationError("push_play_beta_app_version_invalid")
        try:
            min_app_version_code = parse_min_play_version_code(
                os.getenv(PUSH_PLAY_BETA_MIN_VERSION_CODE_ENV, "")
            )
        except ValueError as error:
            raise PushConfigurationError(
                "push_play_beta_min_version_code_invalid"
            ) from error
        if allowed_app_versions and min_app_version_code is not None:
            raise PushConfigurationError("push_play_beta_version_policy_conflict")
        if (
            enrollment_mode == "play_beta"
            and not allowed_app_versions
            and min_app_version_code is None
        ):
            raise PushConfigurationError(
                "push_play_beta_version_policy_required"
            )
        if enrollment_mode != "play_beta" and (
            allowed_app_versions or min_app_version_code is not None
        ):
            raise PushConfigurationError(
                "push_play_beta_version_policy_mode_conflict"
            )

        web_app_url = os.getenv(PUSH_WEB_APP_URL_ENV, DEFAULT_WEB_APP_URL).strip()
        try:
            parsed_web_url = urlsplit(web_app_url)
            invalid_port = parsed_web_url.port is None and ":" in parsed_web_url.netloc
        except ValueError as error:
            raise PushConfigurationError("push_web_app_url_invalid") from error
        if (
            parsed_web_url.scheme != "https"
            or not parsed_web_url.hostname
            or parsed_web_url.username is not None
            or parsed_web_url.password is not None
            or parsed_web_url.path not in {"", "/"}
            or parsed_web_url.query
            or parsed_web_url.fragment
            or invalid_port
        ):
            raise PushConfigurationError("push_web_app_url_invalid")
        web_app_url = f"https://{parsed_web_url.netloc.rstrip('/')}"

        return cls(
            mode=mode,
            max_devices=max_devices,
            allowed_installation_hashes=allowed_hashes,
            enrollment_mode=enrollment_mode,
            enrollment_generation=enrollment_generation,
            android_app_ids=android_app_ids,
            web_app_ids=web_app_ids,
            allowed_app_versions=allowed_app_versions,
            min_app_version_code=min_app_version_code,
            web_app_url=web_app_url,
        )


@dataclass(frozen=True)
class PushDispatchResult:
    status: str
    attempted: int = 0
    sent: int = 0
    sent_unconfirmed: int = 0
    deduplicated: int = 0
    failed: int = 0
    pages_processed: int = 0
    delivery_batches: int = 0

    def response(self) -> ActiveAlertDeliveryResponse:
        return ActiveAlertDeliveryResponse(
            status=self.status,
            attempted=self.attempted,
            sent=self.sent,
            sent_unconfirmed=self.sent_unconfirmed,
            deduplicated=self.deduplicated,
            failed=self.failed,
        )

    def summary(self) -> dict[str, int | str]:
        return {
            "status": self.status,
            "attempted": self.attempted,
            "sent": self.sent,
            "sent_unconfirmed": self.sent_unconfirmed,
            "deduplicated": self.deduplicated,
            "failed": self.failed,
            "pages_processed": self.pages_processed,
            "delivery_batches": self.delivery_batches,
        }


@dataclass(frozen=True)
class PreparedOfficialState:
    signature: str
    alert_id: str
    issued_at: str
    area: str
    valid_to: datetime
    selected_alert: dict[str, Any]


def _parse_datetime(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _has_verified_official_pdf(alert: dict[str, Any], *, now: datetime) -> bool:
    pdf_sha256 = str(alert.get("pdf_sha256") or "").strip().lower()
    pdf_url = str(alert.get("pdf_url") or "").strip()
    published_at = _parse_datetime(alert.get("published_at"))
    verified_at = _parse_datetime(alert.get("pdf_verified_at"))
    try:
        pdf_size_bytes = int(alert.get("pdf_size_bytes") or 0)
    except (TypeError, ValueError):
        return False
    return bool(
        _SHA256_RE.fullmatch(pdf_sha256)
        and pdf_url.lower().startswith(OFFICIAL_PDF_URL_PREFIX)
        and 0 < pdf_size_bytes <= MAX_OFFICIAL_PDF_BYTES
        and published_at is not None
        and verified_at is not None
        and verified_at
        >= published_at - timedelta(seconds=SOURCE_CLOCK_SKEW_SECONDS)
        and verified_at <= now + timedelta(seconds=SOURCE_CLOCK_SKEW_SECONDS)
    )


def _has_official_metadata_arpa_corroboration(
    alert: dict[str, Any], *, now: datetime, source_mode: str
) -> bool:
    document_url = str(alert.get("pdf_url") or "").strip()
    try:
        parsed = urlsplit(document_url)
    except ValueError:
        return False
    match = _OFFICIAL_FVG_DOCUMENT_RE.fullmatch(parsed.path)
    if (
        parsed.scheme.lower() != "https"
        or (parsed.hostname or "").lower() != OFFICIAL_FVG_DOCUMENT_HOST
        or parsed.query
        or parsed.fragment
        or match is None
    ):
        return False
    try:
        identity = (int(alert.get("alert_year")), int(alert.get("alert_number")))
    except (TypeError, ValueError):
        return False
    if identity != (int(match.group("year")), int(match.group("number"))):
        return False
    corroborated_at = _parse_datetime(alert.get("corroborated_at"))
    corroboration = alert.get("corroboration")
    revision_hash = str(alert.get("revision_hash") or "").strip().lower()
    if not isinstance(corroboration, dict):
        return False
    expected_method = {
        "official_fvg_widget_arpa_corroborated": "official_fvg_widget_arpa",
        "official_page_arpa_corroborated": "official_fvg_page_arpa",
        "official_telegram_arpa_corroborated": "official_telegram_arpa",
    }.get(source_mode)
    return bool(
        expected_method
        and corroborated_at is not None
        and -SOURCE_CLOCK_SKEW_SECONDS
        <= (now - corroborated_at).total_seconds()
        <= MAX_OFFICIAL_SOURCE_AGE_SECONDS
        and corroboration.get("method") == expected_method
        and str(corroboration.get("identity") or "") == f"{identity[0]}:{identity[1]}"
        and _SHA256_RE.fullmatch(
            str(corroboration.get("pcr_revision") or "").strip().lower()
        )
        and _SHA256_RE.fullmatch(revision_hash)
    )


def _normalized_strings(value: Any) -> list[str]:
    if not isinstance(value, (list, tuple, set)):
        return []
    return sorted({str(item).strip() for item in value if str(item).strip()})


def _canonical_alert(alert: dict[str, Any]) -> dict[str, Any]:
    pdf_sha256 = str(alert.get("pdf_sha256") or "").strip().lower()
    canonical = {
        "id": str(alert.get("id") or "").strip(),
        "event_id": str(alert.get("event_id") or "").strip(),
        "alert_number": str(alert.get("alert_number") or "").strip(),
        "alert_year": str(alert.get("alert_year") or "").strip(),
        "revision": str(alert.get("revision") or "").strip(),
        "revision_id": str(alert.get("revision_id") or "").strip(),
        "pdf_url": str(alert.get("pdf_url") or "").strip(),
        "pdf_sha256": pdf_sha256,
        "document_url": str(alert.get("document_url") or "").strip(),
        "document_sha256": str(alert.get("document_sha256") or "").strip().lower(),
        "level": str(alert.get("level") or "").strip().lower(),
        "risks": _normalized_strings(alert.get("risks")),
        "area": str(alert.get("area") or "").strip(),
        "zones": _normalized_strings(alert.get("zones")),
        "valid_from": str(alert.get("valid_from") or "").strip(),
        "valid_to": str(alert.get("valid_to") or "").strip(),
    }
    # Preserve existing signatures for uniform alerts. A redistribution of
    # mixed severities is a material change even with the same regional maximum.
    if alert.get("mixed_levels") is True and isinstance(alert.get("zone_levels"), dict):
        canonical["zone_levels"] = dict(sorted(alert["zone_levels"].items()))
    # The corroboration revision hash binds source and observation time. It is
    # evidence for the current snapshot, not a stable notification identity.
    return canonical


def _alert_number(alert: dict[str, Any]) -> int:
    match = re.search(r"\d+", str(alert.get("alert_number") or ""))
    return int(match.group(0)) if match else -1


def _selection_key(alert: dict[str, Any]) -> tuple[int, float, int, str]:
    level = str(alert.get("level") or "").strip().lower()
    published_at = _parse_datetime(alert.get("published_at"))
    return (
        -_LEVEL_RANK.get(level, 0),
        -(published_at.timestamp() if published_at is not None else float("-inf")),
        -_alert_number(alert),
        str(alert.get("id") or ""),
    )


def _source_id(payload: dict[str, Any]) -> str:
    source = payload.get("source")
    if not isinstance(source, dict):
        return ""
    return str(source.get("id") or "").strip()


def _prepare_official_state(
    payload: dict[str, Any] | None,
    *,
    now: datetime,
) -> tuple[PreparedOfficialState | None, str]:
    if not isinstance(payload, dict) or payload.get("error"):
        return None, "source_unavailable"
    if str((payload.get("cache") or {}).get("status") or "").lower() != "fresh":
        return None, "source_unavailable"
    if _source_id(payload) != OFFICIAL_SOURCE_ID:
        return None, "source_unavailable"
    source_mode = str(payload.get("source_mode") or "").strip().lower()
    if source_mode not in OFFICIAL_SOURCE_MODES:
        return None, "source_unavailable"
    fetched_at = _parse_datetime(payload.get("fetched_at"))
    if fetched_at is None:
        return None, "source_unavailable"
    source_age_seconds = (now - fetched_at).total_seconds()
    if source_age_seconds < -5 * 60 or source_age_seconds > MAX_OFFICIAL_SOURCE_AGE_SECONDS:
        return None, "source_unavailable"
    if payload.get("active") is not True:
        if source_mode not in OFFICIAL_INACTIVE_SOURCE_MODES:
            return None, "source_unavailable"
        return None, "no_active_alert"
    if source_mode not in OFFICIAL_ACTIVE_SOURCE_MODES:
        return None, "source_unavailable"

    actionable: list[dict[str, Any]] = []
    for candidate in payload.get("alerts") or []:
        if not isinstance(candidate, dict):
            continue
        level = str(candidate.get("level") or "").strip().lower()
        if _LEVEL_RANK.get(level, 0) <= 0:
            continue
        valid_to = _parse_datetime(candidate.get("valid_to"))
        if valid_to is None or (valid_to - now).total_seconds() < 60:
            continue
        source_verified = (
            _has_verified_official_pdf(candidate, now=now)
            if source_mode == "official_telegram_pdf_verified"
            else _has_official_metadata_arpa_corroboration(
                candidate, now=now, source_mode=source_mode
            )
        )
        if not source_verified:
            return None, "source_unavailable"
        bodies = candidate.get("push_body_i18n")
        if not isinstance(bodies, dict) or not str(bodies.get("it") or "").strip():
            continue
        actionable.append(candidate)

    if not actionable:
        return None, "no_active_alert"

    ordered = sorted(actionable, key=_selection_key)
    selected = ordered[0]
    selected_valid_to = _parse_datetime(selected.get("valid_to"))
    if selected_valid_to is None:
        return None, "no_active_alert"

    canonical_state = {
        "source": OFFICIAL_SOURCE_ID,
        "alert": _canonical_alert(selected),
    }
    signature = hashlib.sha256(
        json.dumps(
            canonical_state,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()

    zones = _normalized_strings(selected.get("zones"))
    area = str(selected.get("area") or "").strip()
    if not area and zones:
        area = ", ".join(zones)
    if not area:
        area = "Friuli Venezia Giulia"
    issued_at = str(
        selected.get("valid_from") or payload.get("fetched_at") or ""
    ).strip()

    return (
        PreparedOfficialState(
            signature=signature,
            alert_id=str(selected.get("id") or signature[:16])[:200],
            issued_at=issued_at[:80],
            area=area[:200],
            valid_to=selected_valid_to,
            selected_alert=selected,
        ),
        "ready",
    )


class PushPilotService:
    def __init__(
        self,
        *,
        repository: PushDeviceRepository,
        sender: FirebaseCloudMessagingSender,
        official_alert_loader: Callable[[], dict[str, Any]],
        config: PushPilotConfig,
        location_catalog: LocationCatalog | None = None,
        national_location_catalog: NationalMunicipalityCatalog | None = None,
        geography_catalog: FvgGeographyCatalog | None = None,
        location_service: LocationService | None = None,
        now: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    ) -> None:
        self._repository = repository
        self._sender = sender
        self._official_alert_loader = official_alert_loader
        self._config = config
        self._location_catalog = location_catalog or LocationCatalog()
        self._national_location_catalog = (
            national_location_catalog
            or get_default_national_municipality_catalog()
        )
        self._geography_catalog = (
            geography_catalog or get_default_fvg_geography_catalog()
        )
        self._location_service = location_service or LocationService(
            catalog=self._location_catalog,
            geography=self._geography_catalog,
        )
        self._now = now

    def _current_time(self) -> datetime:
        current = self._now()
        if current.tzinfo is None:
            current = current.replace(tzinfo=timezone.utc)
        return current.astimezone(timezone.utc)

    def _authorize_device_id(self, installation_id: str) -> str:
        device_id = hash_installation_id(installation_id)
        allowed = self._config.allowed_installation_hashes
        if allowed and device_id not in allowed:
            raise PushInstallationNotAllowed("push_installation_not_allowed")
        return device_id

    def _device_is_allowed(self, device: dict[str, Any]) -> bool:
        if self._config.enrollment_mode == "play_beta":
            platform = str(device.get("platform") or "")
            app_id = str(device.get("app_check_app_id") or "")
            platform_allowed = (
                platform == "android"
                and app_id in self._config.android_app_ids
                and android_app_version_allowed(
                    str(device.get("app_version") or ""),
                    allowed_app_versions=self._config.allowed_app_versions,
                    min_app_version_code=self._config.min_app_version_code,
                )
            ) or (
                platform == "web"
                and app_id in self._config.web_app_ids
            )
            return bool(
                str(device.get("schema_version") or "") == "2.1"
                and str(device.get("enrollment_generation") or "")
                == self._config.enrollment_generation
                and platform_allowed
            )
        if self._config.enrollment_mode == "private_test":
            return str(device.get("platform") or "") == "android"
        allowed = self._config.allowed_installation_hashes
        return not allowed or str(device.get("device_id") or "") in allowed

    def _device_has_canonical_fvg_municipality(
        self,
        device: dict[str, Any],
    ) -> bool:
        municipality = device.get("municipality")
        if not isinstance(municipality, dict):
            return False

        istat = str(municipality.get("istat") or "").strip()
        name = str(municipality.get("name") or "").strip()
        if not istat or not name:
            return False

        canonical = self._location_catalog.match_istat(istat)
        return canonical is not None and canonical.name == name

    def _authorize_platform(
        self,
        platform: str,
        app_check_context: PushAppCheckContext | None,
    ) -> None:
        verified_platform = (
            app_check_context.platform if app_check_context is not None else None
        )
        if verified_platform is not None and verified_platform != platform:
            raise PushPlatformNotAllowed("push_platform_not_allowed")
        if self._config.enrollment_mode == "private_test":
            if platform != "android":
                raise PushPlatformNotAllowed("push_private_test_android_only")
        if self._config.enrollment_mode == "play_beta":
            app_id = str(
                app_check_context.app_id if app_check_context is not None else ""
            )
            expected_app_ids = (
                self._config.android_app_ids
                if platform == "android"
                else self._config.web_app_ids
                if platform == "web"
                else frozenset()
            )
            if (
                app_check_context is None
                or app_check_context.claims is None
                or app_check_context.platform != platform
                or app_id not in expected_app_ids
            ):
                raise PushPlatformNotAllowed(
                    "push_play_beta_app_check_required"
                )

    def _active_device_read(self) -> tuple[list[dict[str, Any]], int]:
        enrollment_generation = (
            self._config.enrollment_generation
            if self._config.enrollment_mode == "play_beta"
            else None
        )
        read_method = getattr(self._repository, "read_active_devices", None)
        if callable(read_method):
            result = read_method(
                max_devices=self._config.max_devices,
                enrollment_generation=enrollment_generation,
            )
            return list(result.devices), int(result.pages_processed)
        devices = self._repository.list_active_devices(
            max_devices=self._config.max_devices,
            enrollment_generation=enrollment_generation,
        )
        return list(devices), 1 if devices else 0

    def _active_devices(self) -> list[dict[str, Any]]:
        return self._active_device_read()[0]

    def _send_batch(
        self,
        messages: list[FcmOfficialAlertMessage],
    ) -> list[FcmBatchOutcome]:
        batch_sender = getattr(self._sender, "send_batch", None)
        if callable(batch_sender):
            return list(batch_sender(messages))
        outcomes: list[FcmBatchOutcome] = []
        for message in messages:
            try:
                message_id = self._sender.send(message)
            except FcmTokenInvalid:
                outcomes.append(FcmBatchOutcome(error_code="fcm_token_invalid"))
            except FcmConfigurationError:
                outcomes.append(
                    FcmBatchOutcome(error_code="fcm_configuration_error")
                )
            except FcmSenderUnavailable:
                outcomes.append(
                    FcmBatchOutcome(error_code="fcm_sender_unavailable")
                )
            else:
                outcomes.append(FcmBatchOutcome(message_id=str(message_id)))
        return outcomes

    def _authorized_app_version(self, platform: str, app_version: str) -> str:
        normalized = _normalize_client_app_version(app_version)
        if (
            self._config.enrollment_mode == "play_beta"
            and platform == "android"
            and not android_app_version_allowed(
                normalized,
                allowed_app_versions=self._config.allowed_app_versions,
                min_app_version_code=self._config.min_app_version_code,
            )
        ):
            raise PushAppVersionNotAllowed(
                "push_app_version_not_allowed"
            )
        return (
            normalized
            if self._config.enrollment_mode == "play_beta"
            else app_version
        )

    @staticmethod
    def _device_delivery_target(
        device: dict[str, Any],
    ) -> tuple[str, str, str] | None:
        platform = str(device.get("platform") or "")
        target_kind, target_value, _ = resolve_push_target(device)
        valid_pair = (
            platform == "android" and target_kind == "fcm_token"
        ) or (
            platform == "web"
            and target_kind == "firebase_installation_id"
        )
        if not valid_pair or not target_value:
            return None
        return target_kind, target_value, hash_push_target(target_value)

    def register(
        self,
        request: PushDeviceRegisterRequest,
        *,
        app_check_context: PushAppCheckContext | None = None,
    ) -> PushDeviceRegisterResponse:
        self._authorize_platform(request.platform, app_check_context)
        authorized_app_version = self._authorized_app_version(
            request.platform,
            request.app_version,
        )
        now = self._current_time()
        device_id = self._authorize_device_id(request.installation_id)
        municipality = None
        locality = None
        is_fvg_municipality = False
        if request.municipality is not None:
            canonical = self._national_location_catalog.match_istat(
                request.municipality.istat
            )
            if canonical is None or request.municipality.name != canonical.name:
                raise PushMunicipalityInvalid("push_municipality_invalid")
            municipality = {
                "istat": canonical.istat_code,
                "name": canonical.name,
            }
            is_fvg_municipality = (
                self._location_catalog.match_istat(canonical.istat_code)
                is not None
            )
        if request.locality is not None:
            canonical_locality = self._geography_catalog.match_locality_id(
                request.locality.id
            )
            if (
                canonical_locality is None
                or municipality is None
                or canonical_locality.municipality_istat != municipality["istat"]
                or canonical_locality.name != request.locality.name
            ):
                raise PushLocalityInvalid("push_locality_invalid")
            locality = {
                "id": canonical_locality.id,
                "name": canonical_locality.name,
            }
        location_mode = request.location_mode
        location_evidence = None
        if request.location_evidence is not None:
            captured_at = request.location_evidence.captured_at
            if captured_at.tzinfo is not None:
                captured_at = captured_at.astimezone(timezone.utc)
                age_seconds = (now - captured_at).total_seconds()
                if -120 <= age_seconds <= 10 * 60:
                    location_evidence = {
                        "captured_at": captured_at,
                        "accuracy_m": float(request.location_evidence.accuracy_m),
                        "received_at": now,
                    }
            if location_evidence is None:
                # A device clock can be skewed even when the rest of the push
                # registration is valid.  Degrade only the location-targeted
                # local notices; official regional alerts, token and
                # preferences must still be refreshed.
                location_mode = None
        if municipality is not None and not is_fvg_municipality:
            # National rollout is intentionally municipality-selected first.
            # Do not accept an automatic GPS assertion until the production
            # backend has a reviewed national boundary resolver.
            if location_mode != "manual_selection":
                location_mode = None
                location_evidence = None
        target_kind, target_value = request.delivery_target()
        result = self._repository.upsert_device(
            device_id=device_id,
            target_kind=target_kind,
            target_value=target_value,
            platform=request.platform,
            app_check_app_id=(
                app_check_context.app_id if app_check_context is not None else ""
            ),
            enrollment_mode=self._config.enrollment_mode,
            enrollment_generation=self._config.enrollment_generation,
            app_version=authorized_app_version,
            language=request.language,
            municipality=municipality,
            locality=locality,
            location_mode=location_mode,
            location_evidence=location_evidence,
            preferences=request.preferences.model_dump(),
            max_devices=self._config.max_devices,
            now=now,
        )

        if request.preferences.official_alerts is not True:
            delivery = PushDispatchResult(status="preference_disabled")
        elif self._config.mode == "off":
            delivery = PushDispatchResult(status="disabled")
        else:
            try:
                active_payload = self._official_alert_loader()
                delivery = self.dispatch_official_alerts(
                    active_payload,
                    devices=[result.device],
                )
            except PushRepositoryUnavailable:
                delivery = PushDispatchResult(status="storage_unavailable", failed=1)
            except Exception:
                delivery = PushDispatchResult(status="source_unavailable")

        return PushDeviceRegisterResponse(
            device_id=device_id,
            created=result.created,
            local_target_eligible=(
                municipality is not None
                and location_mode in {"automatic_gps", "manual_selection"}
            ),
            active_alert_delivery=delivery.response(),
        )

    def unregister(
        self,
        installation_id: str,
        *,
        app_check_context: PushAppCheckContext | None = None,
    ) -> PushDeviceUnregisterResponse:
        if self._config.enrollment_mode == "play_beta":
            verified_platform = (
                app_check_context.platform if app_check_context is not None else ""
            )
            self._authorize_platform(verified_platform, app_check_context)
        device_id = self._authorize_device_id(installation_id)
        removed = self._repository.unregister_device(
            device_id=device_id,
            now=self._current_time(),
            expected_platform=(
                app_check_context.platform if app_check_context is not None else ""
            )
            or "",
            expected_app_check_app_id=(
                app_check_context.app_id
                if self._config.enrollment_mode == "play_beta"
                and app_check_context is not None
                else ""
            ),
            expected_enrollment_generation=(
                self._config.enrollment_generation
                if self._config.enrollment_mode == "play_beta"
                else ""
            ),
        )
        return PushDeviceUnregisterResponse(unregistered=removed)

    def update_location(
        self,
        request: PushDeviceLocationUpdateRequest,
        *,
        app_check_context: PushAppCheckContext | None = None,
    ) -> PushDeviceLocationUpdateResponse:
        self._authorize_platform("android", app_check_context)
        now = self._current_time()
        device_id = self._authorize_device_id(request.installation_id)
        captured_at = request.captured_at
        if captured_at.tzinfo is None:
            raise PushLocationEvidenceInvalid("push_location_evidence_invalid")
        captured_at = captured_at.astimezone(timezone.utc)
        age_seconds = (now - captured_at).total_seconds()
        if age_seconds < -120 or age_seconds > 10 * 60:
            raise PushLocationEvidenceInvalid("push_location_evidence_invalid")

        resolved = self._location_service.reverse(
            lat=request.lat,
            lon=request.lon,
            accuracy_m=request.accuracy_m,
        )
        municipality = None
        locality = None
        location_evidence = None
        data_point = None
        status = resolved.resolution.status
        display_name = ""

        if status == "external_place":
            resolved_data_point = getattr(resolved, "dataPoint", None)
            if resolved_data_point is not None:
                data_point = {
                    "lat": resolved_data_point.lat,
                    "lon": resolved_data_point.lon,
                    "source": resolved_data_point.source,
                }
                display_name = resolved.displayName
        elif status != "outside_fvg" and resolved.municipality is not None:
            boundary_distance_m = resolved.resolution.boundaryDistanceM
            if (
                boundary_distance_m is None
                or request.accuracy_m + 10 >= boundary_distance_m
            ):
                status = "ambiguous_boundary"
            else:
                municipality = {
                    "istat": resolved.municipality.istatCode,
                    "name": resolved.municipality.name,
                }
                if resolved.locality is not None:
                    locality = {
                        "id": resolved.locality.id,
                        "name": resolved.locality.name,
                    }
                location_evidence = {
                    "accuracy_m": float(request.accuracy_m),
                    "captured_at": captured_at,
                    "received_at": now,
                    "trigger": request.trigger,
                }
                status = "resolved"
                display_name = resolved.displayName
                resolved_data_point = getattr(resolved, "dataPoint", None)
                if resolved_data_point is not None:
                    data_point = {
                        "lat": resolved_data_point.lat,
                        "lon": resolved_data_point.lon,
                        "source": resolved_data_point.source,
                    }

        updated = self._repository.update_android_location_target(
            device_id=device_id,
            app_check_app_id=(
                app_check_context.app_id if app_check_context is not None else ""
            ),
            expected_enrollment_generation=(
                self._config.enrollment_generation
                if self._config.enrollment_mode == "play_beta"
                else ""
            ),
            municipality=municipality,
            locality=locality,
            location_evidence=location_evidence,
            now=now,
        )
        if updated is None:
            raise PushDeviceNotRegistered("push_device_not_registered")

        return PushDeviceLocationUpdateResponse(
            updated=True,
            status=status,
            local_target_eligible=location_evidence is not None,
            display_name=display_name,
            municipality=municipality,
            locality=locality,
            data_point=data_point,
        )

    def dispatch_official_alerts(
        self,
        payload: dict[str, Any],
        *,
        devices: Iterable[dict[str, Any]] | None = None,
    ) -> PushDispatchResult:
        if self._config.mode == "off":
            return PushDispatchResult(status="disabled")

        now = self._current_time()
        prepared, state = _prepare_official_state(payload, now=now)
        if prepared is None:
            return PushDispatchResult(status=state)

        if devices is None:
            eligible_devices, pages_processed = self._active_device_read()
        else:
            eligible_devices = [dict(device) for device in devices]
            pages_processed = 1 if eligible_devices else 0

        eligible_targets = []
        for device in eligible_devices:
            target = self._device_delivery_target(device)
            if (
                device.get("active") is True
                and (device.get("preferences") or {}).get("official_alerts") is True
                and self._device_has_canonical_fvg_municipality(device)
                and self._device_is_allowed(device)
                and target is not None
            ):
                eligible_targets.append((device, target))
        if self._config.enrollment_mode == "play_beta":
            seen_fcm_targets: set[str] = set()
            for _, (target_kind, _, target_hash) in eligible_targets:
                if target_kind != PUSH_TARGET_FCM_TOKEN or not target_hash:
                    continue
                if target_hash in seen_fcm_targets:
                    raise PushRepositoryUnavailable(
                        "push_duplicate_fcm_target_detected"
                    )
                seen_fcm_targets.add(target_hash)
        if not eligible_targets:
            return PushDispatchResult(
                status="no_eligible_devices",
                pages_processed=pages_processed,
            )
        if (
            self._config.enrollment_mode != "play_beta"
            and len(eligible_targets) > self._config.max_devices
        ):
            raise PushRepositoryUnavailable("push_device_capacity_state_invalid")

        if self._config.mode == "dry_run":
            return PushDispatchResult(
                status="dry_run",
                attempted=len(eligible_targets),
                pages_processed=pages_processed,
            )

        attempted = sent = sent_unconfirmed = deduplicated = failed = 0
        delivery_batches = 0
        batch_size = max(1, min(self._config.max_devices, 500))
        for offset in range(0, len(eligible_targets), batch_size):
            pending = []
            messages: list[FcmOfficialAlertMessage] = []
            for device, target in eligible_targets[offset:offset + batch_size]:
                attempted += 1
                device_id = str(device.get("device_id") or "")
                if not device_id:
                    failed += 1
                    continue
                target_kind, target_value, target_hash = target
                claim = self._repository.claim_official_alert_delivery(
                    device_id=device_id,
                    alert_signature=prepared.signature,
                    alert_id=prepared.alert_id,
                    target_kind=target_kind,
                    target_hash=target_hash,
                    expected_enrollment_generation=(
                        self._config.enrollment_generation
                        if self._config.enrollment_mode == "play_beta"
                        else ""
                    ),
                    expected_app_check_app_id=(
                        str(device.get("app_check_app_id") or "")
                        if self._config.enrollment_mode == "play_beta"
                        else ""
                    ),
                    expected_app_version=(
                        _normalize_client_app_version(
                            str(device.get("app_version") or "")
                        )
                        if self._config.enrollment_mode == "play_beta"
                        else ""
                    ),
                    now=now,
                )
                if not claim.claimed:
                    if claim.state in {
                        "app_check_app_changed",
                        "app_version_changed",
                        "configuration_retry_scheduled",
                        "enrollment_generation_changed",
                        "retry_exhausted",
                        "schema_version_changed",
                    }:
                        failed += 1
                    else:
                        deduplicated += 1
                    continue
                expectations = {
                    "expected_claim_id": claim.claim_id,
                    "expected_target_kind": target_kind,
                    "expected_target_hash": target_hash,
                }
                language = str(device.get("language") or "it").strip().lower()
                if language not in {"it", "fur"}:
                    language = "it"
                bodies = prepared.selected_alert.get("push_body_i18n") or {}
                body = str(
                    bodies.get(language) or bodies.get("it") or ""
                ).strip()
                ttl_seconds = min(
                    MAX_NOTIFICATION_TTL_SECONDS,
                    max(60, int((prepared.valid_to - now).total_seconds())),
                )
                pending.append((claim, device, target, expectations))
                messages.append(FcmOfficialAlertMessage(
                    title=PUSH_TITLE,
                    body=body,
                    data={
                        "type": "official_alert",
                        "alert_id": prepared.alert_id,
                        "issued_at": prepared.issued_at,
                        "area": prepared.area,
                    },
                    ttl_seconds=ttl_seconds,
                    target_kind=target_kind,
                    target_value=target_value,
                    platform=str(device.get("platform") or ""),
                    channel_id=DEFAULT_ANDROID_NOTIFICATION_CHANNEL,
                    collapse_key="mf-official-alerts",
                    notification_tag="mf-official-alerts",
                    web_link=f"{self._config.web_app_url}/?tab=bulletin",
                ))

            if not messages:
                continue
            delivery_batches += 1
            try:
                outcomes = self._send_batch(messages)
            except FcmConfigurationError:
                outcomes = [
                    FcmBatchOutcome(error_code="fcm_configuration_error")
                    for _ in messages
                ]
            except FcmSenderUnavailable:
                outcomes = [
                    FcmBatchOutcome(error_code="fcm_sender_unavailable")
                    for _ in messages
                ]
            if len(outcomes) != len(pending):
                outcomes = [
                    FcmBatchOutcome(error_code="fcm_sender_unavailable")
                    for _ in pending
                ]

            for (claim, device, target, expectations), outcome in zip(
                pending, outcomes, strict=True
            ):
                target_kind, _, target_hash = target
                device_id = str(device.get("device_id") or "")
                if outcome.success:
                    confirmed = self._repository.finish_official_alert_delivery(
                        delivery_id=claim.delivery_id,
                        state="sent",
                        now=now,
                        message_id=outcome.message_id,
                        **expectations,
                    )
                    if confirmed:
                        sent += 1
                    else:
                        sent_unconfirmed += 1
                        failed += 1
                    continue
                finish_state = (
                    "failed_invalid_token"
                    if outcome.error_code == "fcm_token_invalid"
                    else "failed_configuration"
                    if outcome.error_code == "fcm_configuration_error"
                    else "failed_transient"
                )
                self._repository.finish_official_alert_delivery(
                    delivery_id=claim.delivery_id,
                    state=finish_state,
                    now=now,
                    error_code=outcome.error_code or "fcm_sender_unavailable",
                    **expectations,
                )
                if outcome.error_code == "fcm_token_invalid":
                    self._repository.disable_device(
                        device_id=device_id,
                        expected_target_kind=target_kind,
                        expected_target_hash=target_hash,
                        reason="fcm_token_invalid",
                        now=now,
                    )
                failed += 1

        if sent_unconfirmed and not sent and failed == sent_unconfirmed:
            status = "sent_unconfirmed"
        elif failed:
            status = "partial" if sent or deduplicated else "failed"
        elif sent:
            status = "sent"
        elif deduplicated:
            status = "deduplicated"
        else:
            status = "failed"
        return PushDispatchResult(
            status=status,
            attempted=attempted,
            sent=sent,
            sent_unconfirmed=sent_unconfirmed,
            deduplicated=deduplicated,
            failed=failed,
            pages_processed=pages_processed,
            delivery_batches=delivery_batches,
        )

    def send_pilot_test(self) -> PushDispatchResult:
        test_mode = os.getenv(PUSH_TEST_MODE_ENV, "off").strip().lower()
        if self._config.mode != "send" or test_mode != "send":
            raise PushConfigurationError("push_test_mode_not_enabled")

        devices = self._active_devices()
        eligible = []
        for device in devices:
            target = self._device_delivery_target(device)
            if (
                device.get("active") is True
                and device.get("platform") == "android"
                and target is not None
                and self._device_is_allowed(device)
            ):
                eligible.append((device, target))
        if len(eligible) != 1:
            raise PushConfigurationError("push_test_requires_one_device")

        device, target = eligible[0]
        target_kind, target_value, target_hash = target
        now = self._current_time()
        try:
            self._sender.send(
                FcmOfficialAlertMessage(
                    title=PUSH_TITLE,
                    body="Notifiche attive su questo dispositivo.",
                    data={},
                    ttl_seconds=5 * 60,
                    target_kind=target_kind,
                    target_value=target_value,
                    platform="android",
                    channel_id=DEFAULT_ANDROID_NOTIFICATION_CHANNEL,
                    collapse_key="mf-pilot-test",
                    notification_tag="mf-pilot-test",
                )
            )
        except FcmTokenInvalid:
            self._repository.disable_device(
                device_id=str(device.get("device_id") or ""),
                expected_target_kind=target_kind,
                expected_target_hash=target_hash,
                reason="fcm_token_invalid",
                now=now,
            )
            return PushDispatchResult(status="failed", attempted=1, failed=1)
        except FcmConfigurationError:
            return PushDispatchResult(status="failed", attempted=1, failed=1)
        except FcmSenderUnavailable:
            return PushDispatchResult(status="failed", attempted=1, failed=1)
        return PushDispatchResult(status="sent", attempted=1, sent=1)


@lru_cache(maxsize=1)
def get_push_pilot_service() -> PushPilotService:
    return PushPilotService(
        repository=PushDeviceRepository(get_firestore_client),
        sender=FirebaseCloudMessagingSender(),
        official_alert_loader=lambda: get_official_alerts_state(force=False),
        config=PushPilotConfig.from_environment(),
        location_catalog=LocationCatalog(),
    )


def reset_push_pilot_service_for_tests() -> None:
    get_push_pilot_service.cache_clear()


__all__ = [
    "PushConfigurationError",
    "PushAppVersionNotAllowed",
    "PushDeviceNotRegistered",
    "PushDispatchResult",
    "PushInstallationNotAllowed",
    "PushLocalityInvalid",
    "PushMunicipalityInvalid",
    "PushPlatformNotAllowed",
    "PushPilotCapacityReached",
    "PushPilotConfig",
    "PushPilotService",
    "PushRepositoryUnavailable",
    "get_push_pilot_service",
    "reset_push_pilot_service_for_tests",
]
