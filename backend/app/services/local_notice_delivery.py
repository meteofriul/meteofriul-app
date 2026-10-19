"""Delivery of conservative local weather notices to verified app cohorts."""

from __future__ import annotations

import os
import re
import uuid
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from typing import Any, Callable

from app.infrastructure.firebase import get_firestore_client
from app.push.fcm import (
    DEFAULT_ANDROID_LOCAL_NOTICE_CHANNEL,
    DEFAULT_WEB_APP_URL,
    FcmConfigurationError,
    FcmBatchOutcome,
    FcmOfficialAlertMessage,
    FcmSenderUnavailable,
    FcmTokenInvalid,
    FirebaseCloudMessagingSender,
)
from app.repositories.local_notice_delivery import (
    LocalNoticeDeliveryAuditRepository,
    LocalNoticeDeliveryAuditUnavailable,
)
from app.repositories.push import (
    PUSH_TARGET_FCM_TOKEN,
    PUSH_TARGET_FIREBASE_INSTALLATION_ID,
    PushDeviceRepository,
    PushRepositoryUnavailable,
    hash_push_target,
    resolve_push_target,
)
from app.services.local_notice_shadow import _source_failure_evaluation
from app.services.location import LocationCatalog, Municipality
from app.services.national_municipalities import (
    NationalMunicipalityCatalog,
)
from app.services.notice_municipalities import NoticeMunicipalityCatalog
from app.services.fvg_geography import (
    FvgGeographyCatalog,
    FvgLocality,
    get_default_fvg_geography_catalog,
)
from app.services.push_version_policy import (
    android_app_version_allowed,
    parse_min_play_version_code,
)
from app.weather.local_notice_shadow import (
    FVG_ZONE,
    NOTICE_MAX_LEAD_TIME,
    POLICY_VERSION,
    SCHEMA_VERSION,
    evaluate_local_notice_shadow,
)
from app.weather.local_notice_source import (
    DEFAULT_LOCAL_NOTICE_SOURCE_TIMEOUT_SECONDS,
    LocalNoticeSourceUnavailable,
    MAX_LOCAL_NOTICE_SOURCE_TIMEOUT_SECONDS,
    RoutedIconLocalNoticeSource,
)
from app.weather.local_notice_quality import QualityCounter, evaluation_quality


LOCAL_NOTICE_DELIVERY_MODE_ENV = "LOCAL_NOTICE_DELIVERY_MODE"
LOCAL_NOTICE_ALLOWED_HASHES_ENV = "LOCAL_NOTICE_ALLOWED_INSTALLATION_HASHES"
LOCAL_NOTICE_ENROLLMENT_MODE_ENV = "LOCAL_NOTICE_ENROLLMENT_MODE"
LOCAL_NOTICE_RETENTION_DAYS_ENV = "LOCAL_NOTICE_RETENTION_DAYS"
LOCAL_NOTICE_SOURCE_TIMEOUT_SECONDS_ENV = "LOCAL_NOTICE_SOURCE_TIMEOUT_SECONDS"
PUSH_PILOT_MAX_DEVICES_ENV = "PUSH_PILOT_MAX_DEVICES"
PUSH_ENROLLMENT_GENERATION_ENV = "PUSH_ENROLLMENT_GENERATION"
PUSH_APP_CHECK_ANDROID_APP_IDS_ENV = "PUSH_APP_CHECK_ANDROID_APP_IDS"
PUSH_APP_CHECK_WEB_APP_IDS_ENV = "PUSH_APP_CHECK_WEB_APP_IDS"
PUSH_APP_CHECK_ALLOWED_APP_IDS_ENV = "PUSH_APP_CHECK_ALLOWED_APP_IDS"
PUSH_PLAY_BETA_ALLOWED_APP_VERSIONS_ENV = (
    "PUSH_PLAY_BETA_ALLOWED_APP_VERSIONS"
)
PUSH_PLAY_BETA_MIN_VERSION_CODE_ENV = "PUSH_PLAY_BETA_MIN_VERSION_CODE"
LOCAL_NOTICE_TITLE = "Meteo Friûl"
LOCAL_NOTICE_TTL_MAX_SECONDS = int(NOTICE_MAX_LEAD_TIME.total_seconds())
LOCAL_NOTICE_LOCATION_MAX_AGE_SECONDS = 60 * 60
LOCAL_NOTICE_LOCATION_CLOCK_SKEW_SECONDS = 2 * 60
PLAY_BETA_DEFAULT_PAGE_SIZE = 200
PLAY_BETA_MAX_PAGE_SIZE = 500
LOCAL_NOTICE_KINDS = frozenset({"storm", "ice", "snow", "wind", "rain", "heat"})
_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
_ENROLLMENT_GENERATION_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._-]{0,63}$")
_FIREBASE_ANDROID_APP_ID_PATTERN = re.compile(
    r"^1:\d+:android:[0-9a-f]+$",
    re.IGNORECASE,
)
_FIREBASE_WEB_APP_ID_PATTERN = re.compile(
    r"^1:\d+:web:[0-9a-f]+$",
    re.IGNORECASE,
)
_CLIENT_APP_VERSION_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._+-]{0,63}$")


class LocalNoticeDeliveryConfigurationError(RuntimeError):
    """The delivery job is not safely configured."""


class LocalNoticeDeliveryDeviceStateUnavailable(RuntimeError):
    """The registered-device state could not be read safely."""


@dataclass(frozen=True)
class LocalNoticeDeliveryConfig:
    mode: str
    allowed_installation_hash: str
    retention_days: int
    source_timeout_seconds: float
    max_devices: int
    enrollment_mode: str = "owner_allowlist"
    enrollment_generation: str = ""
    allowed_app_ids: frozenset[str] = frozenset()
    web_app_ids: frozenset[str] = frozenset()
    allowed_app_versions: frozenset[str] = frozenset()
    min_app_version_code: int | None = None

    @classmethod
    def from_environment(cls) -> "LocalNoticeDeliveryConfig":
        mode = (
            os.getenv(LOCAL_NOTICE_DELIVERY_MODE_ENV, "off").strip().lower()
            or "off"
        )
        if mode not in {"off", "dry_run", "send"}:
            raise LocalNoticeDeliveryConfigurationError(
                "local_notice_delivery_mode_invalid"
            )
        enrollment_mode = (
            os.getenv(
                LOCAL_NOTICE_ENROLLMENT_MODE_ENV,
                "owner_allowlist",
            ).strip().lower()
            or "owner_allowlist"
        )
        if enrollment_mode not in {"owner_allowlist", "play_beta"}:
            raise LocalNoticeDeliveryConfigurationError(
                "local_notice_enrollment_mode_invalid"
            )

        hashes = {
            item.strip().lower()
            for item in os.getenv(LOCAL_NOTICE_ALLOWED_HASHES_ENV, "").split(",")
            if item.strip()
        }
        if mode != "off":
            if enrollment_mode == "owner_allowlist" and (
                len(hashes) != 1
                or not _SHA256_PATTERN.fullmatch(next(iter(hashes), ""))
            ):
                raise LocalNoticeDeliveryConfigurationError(
                    "local_notice_owner_allowlist_invalid"
                )
            if enrollment_mode == "play_beta" and hashes:
                raise LocalNoticeDeliveryConfigurationError(
                    "local_notice_play_beta_allowlist_conflict"
                )

        enrollment_generation = os.getenv(
            PUSH_ENROLLMENT_GENERATION_ENV,
            "",
        ).strip().lower()
        raw_app_ids = os.getenv(
            PUSH_APP_CHECK_ANDROID_APP_IDS_ENV,
            "",
        ).strip()
        if not raw_app_ids:
            raw_app_ids = os.getenv(PUSH_APP_CHECK_ALLOWED_APP_IDS_ENV, "").strip()
        allowed_app_ids = frozenset(
            item.strip() for item in raw_app_ids.split(",") if item.strip()
        )
        web_app_ids = frozenset(
            item.strip()
            for item in os.getenv(PUSH_APP_CHECK_WEB_APP_IDS_ENV, "").split(",")
            if item.strip()
        )
        allowed_app_versions = frozenset(
            item.strip().lower()
            for item in os.getenv(
                PUSH_PLAY_BETA_ALLOWED_APP_VERSIONS_ENV, ""
            ).split(",")
            if item.strip()
        )
        try:
            min_app_version_code = parse_min_play_version_code(
                os.getenv(PUSH_PLAY_BETA_MIN_VERSION_CODE_ENV, "")
            )
        except ValueError as error:
            raise LocalNoticeDeliveryConfigurationError(
                "local_notice_min_version_code_invalid"
            ) from error
        if allowed_app_versions and min_app_version_code is not None:
            raise LocalNoticeDeliveryConfigurationError(
                "local_notice_version_policy_conflict"
            )
        if mode != "off" and enrollment_mode == "play_beta":
            if not _ENROLLMENT_GENERATION_PATTERN.fullmatch(enrollment_generation):
                raise LocalNoticeDeliveryConfigurationError(
                    "local_notice_enrollment_generation_invalid"
                )
            if not allowed_app_ids or any(
                not _FIREBASE_ANDROID_APP_ID_PATTERN.fullmatch(app_id)
                for app_id in allowed_app_ids
            ):
                raise LocalNoticeDeliveryConfigurationError(
                    "local_notice_android_app_ids_invalid"
                )
            if any(
                not _FIREBASE_WEB_APP_ID_PATTERN.fullmatch(app_id)
                for app_id in web_app_ids
            ):
                raise LocalNoticeDeliveryConfigurationError(
                    "local_notice_web_app_ids_invalid"
                )
            if (
                not allowed_app_versions
                and min_app_version_code is None
            ) or any(
                not _CLIENT_APP_VERSION_PATTERN.fullmatch(app_version)
                for app_version in allowed_app_versions
            ):
                raise LocalNoticeDeliveryConfigurationError(
                    "local_notice_app_versions_invalid"
                )
        elif enrollment_mode != "play_beta" and enrollment_generation:
            raise LocalNoticeDeliveryConfigurationError(
                "local_notice_enrollment_generation_mode_conflict"
            )
        if enrollment_mode != "play_beta" and (
            allowed_app_versions or min_app_version_code is not None
        ):
            raise LocalNoticeDeliveryConfigurationError(
                "local_notice_app_versions_mode_conflict"
            )
        try:
            retention_days = int(
                os.getenv(LOCAL_NOTICE_RETENTION_DAYS_ENV, "14").strip() or "14"
            )
            source_timeout_seconds = float(
                os.getenv(
                    LOCAL_NOTICE_SOURCE_TIMEOUT_SECONDS_ENV,
                    str(DEFAULT_LOCAL_NOTICE_SOURCE_TIMEOUT_SECONDS),
                ).strip()
                or str(DEFAULT_LOCAL_NOTICE_SOURCE_TIMEOUT_SECONDS)
            )
            default_page_size = (
                str(PLAY_BETA_DEFAULT_PAGE_SIZE)
                if enrollment_mode == "play_beta"
                else "1"
            )
            max_devices = int(
                os.getenv(PUSH_PILOT_MAX_DEVICES_ENV, default_page_size).strip()
                or default_page_size
            )
        except ValueError as error:
            raise LocalNoticeDeliveryConfigurationError(
                "local_notice_delivery_numeric_config_invalid"
            ) from error
        if retention_days < 1 or retention_days > 30:
            raise LocalNoticeDeliveryConfigurationError(
                "local_notice_retention_invalid"
            )
        if (
            source_timeout_seconds < 1
            or source_timeout_seconds > MAX_LOCAL_NOTICE_SOURCE_TIMEOUT_SECONDS
        ):
            raise LocalNoticeDeliveryConfigurationError(
                "local_notice_timeout_invalid"
            )
        max_allowed_devices = (
            PLAY_BETA_MAX_PAGE_SIZE if enrollment_mode == "play_beta" else 10
        )
        if max_devices < 1 or max_devices > max_allowed_devices:
            raise LocalNoticeDeliveryConfigurationError(
                "local_notice_device_limit_invalid"
            )
        return cls(
            mode=mode,
            allowed_installation_hash=next(iter(hashes), ""),
            retention_days=retention_days,
            source_timeout_seconds=source_timeout_seconds,
            max_devices=max_devices,
            enrollment_mode=enrollment_mode,
            enrollment_generation=enrollment_generation,
            allowed_app_ids=allowed_app_ids,
            web_app_ids=web_app_ids,
            allowed_app_versions=allowed_app_versions,
            min_app_version_code=min_app_version_code,
        )


@dataclass(frozen=True)
class LocalNoticeDeliveryResult:
    status: str
    eligible_devices: int = 0
    evaluated: int = 0
    candidates: int = 0
    selected_kind: str = ""
    attempted: int = 0
    sent: int = 0
    sent_unconfirmed: int = 0
    deduplicated: int = 0
    persisted: int = 0
    failed: int = 0
    groups: int = 0
    failed_groups: int = 0
    in_progress: int = 0
    retry_scheduled: int = 0
    opted_out: int = 0
    expired: int = 0
    duplicate_targets: int = 0
    security_failed: int = 0
    device_failed: int = 0
    storage_failed: int = 0
    audit_failed: int = 0
    source_failed: int = 0
    data_degraded_groups: int = 0
    pages_processed: int = 0
    delivery_batches: int = 0
    data_quality: dict[str, Any] = field(default_factory=lambda: QualityCounter().summary())

    def summary(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "eligible_devices": self.eligible_devices,
            "evaluated": self.evaluated,
            "candidates": self.candidates,
            "selected_kind": self.selected_kind,
            "attempted": self.attempted,
            "sent": self.sent,
            "sent_unconfirmed": self.sent_unconfirmed,
            "deduplicated": self.deduplicated,
            "persisted": self.persisted,
            "failed": self.failed,
            "groups": self.groups,
            "failed_groups": self.failed_groups,
            "in_progress": self.in_progress,
            "retry_scheduled": self.retry_scheduled,
            "opted_out": self.opted_out,
            "expired": self.expired,
            "duplicate_targets": self.duplicate_targets,
            "security_failed": self.security_failed,
            "device_failed": self.device_failed,
            "storage_failed": self.storage_failed,
            "audit_failed": self.audit_failed,
            "source_failed": self.source_failed,
            "data_degraded_groups": self.data_degraded_groups,
            "pages_processed": self.pages_processed,
            "delivery_batches": self.delivery_batches,
            "data_quality": self.data_quality,
        }


@dataclass(frozen=True)
class LocalNoticeDeliveryTarget:
    device: dict[str, Any]
    municipality: Municipality
    locality: FvgLocality | None
    target_value: str
    target_kind: str
    target_hash: str
    location_mode: str
    location_captured_at: datetime | None
    location_received_at: datetime | None
    location_accuracy_m: float | None

    @property
    def group_key(self) -> tuple[str, str]:
        return (
            self.municipality.istat_code,
            self.locality.id if self.locality is not None else "",
        )


def _parse_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return None
        return value.astimezone(timezone.utc)
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc)


def _candidate_signature(candidate: Mapping[str, Any]) -> str:
    dedupe = candidate.get("dedupe")
    if not isinstance(dedupe, Mapping):
        return ""
    signature = str(dedupe.get("signature") or "").strip().lower()
    return signature if _SHA256_PATTERN.fullmatch(signature) else ""


def _candidate_is_promotable(
    candidate: Mapping[str, Any],
    *,
    municipality: Municipality,
    locality: FvgLocality | None,
    now: datetime,
) -> bool:
    if (
        candidate.get("schema_version") != SCHEMA_VERSION
        or candidate.get("policy_version") != POLICY_VERSION
        or candidate.get("mode") != "shadow"
        or candidate.get("shadow_only") is not True
        or candidate.get("can_notify") is not False
    ):
        return False
    stored_locality = candidate.get("locality")
    if locality is None:
        if stored_locality is not None:
            return False
    elif (
        not isinstance(stored_locality, Mapping)
        or str(stored_locality.get("id") or "") != locality.id
        or str(stored_locality.get("name") or "") != locality.name
    ):
        return False
    kind = str(candidate.get("kind") or "")
    if kind not in LOCAL_NOTICE_KINDS or not _candidate_signature(candidate):
        return False
    stored_municipality = candidate.get("municipality")
    if (
        not isinstance(stored_municipality, Mapping)
        or str(stored_municipality.get("istat_code") or "")
        != municipality.istat_code
        or str(stored_municipality.get("city") or "") != municipality.name
    ):
        return False
    event_at = _parse_datetime(candidate.get("event_at"))
    event_end = _parse_datetime(candidate.get("event_end"))
    if (
        event_at is None
        or event_end is None
        or event_end <= now
        or event_at < now
        or (event_at - now).total_seconds() > LOCAL_NOTICE_TTL_MAX_SECONDS
        or event_end <= event_at
    ):
        return False
    if kind == "storm":
        confidence = candidate.get("confidence")
        if (
            not isinstance(confidence, Mapping)
            or confidence.get("corroborated") is not True
        ):
            return False
    return True


def _body(
    candidate: Mapping[str, Any],
    municipality: Municipality,
    locality: FvgLocality | None = None,
) -> str:
    event_at = _parse_datetime(candidate.get("event_at"))
    local_time = event_at.astimezone(FVG_ZONE).strftime("%H:%M") if event_at else ""
    place_phrase = (
        f"a {locality.name}"
        if locality is not None
        else f"nel Comune di {municipality.name}"
    )
    kind = str(candidate.get("kind") or "")
    if kind == "heat":
        suffix = (
            f" dalle {local_time} {place_phrase}."
            if local_time
            else f" {place_phrase}."
        )
    else:
        suffix = (
            f" per le {local_time} {place_phrase}."
            if local_time
            else f" {place_phrase}."
        )
    if kind == "storm":
        codes = {
            int(item.get("value"))
            for item in candidate.get("evidence") or []
            if isinstance(item, Mapping)
            and item.get("metric") == "weather_code"
            and isinstance(item.get("value"), (int, float))
        }
        prefix = "Temporali con grandine" if codes & {96, 99} else "Temporali"
    else:
        prefix = {
            "rain": "Pioggia intensa",
            "ice": "Precipitazioni gelate",
            "snow": "Nevicate",
            "wind": "Raffiche forti",
            "heat": "Caldo intenso",
        }.get(kind, "Fenomeno meteo")
    return prefix + suffix


class LocalNoticeDeliveryService:
    def __init__(
        self,
        *,
        device_repository: PushDeviceRepository | Any,
        audit_repository: LocalNoticeDeliveryAuditRepository | Any,
        source: RoutedIconLocalNoticeSource | Any,
        sender: FirebaseCloudMessagingSender | Any,
        config: LocalNoticeDeliveryConfig,
        location_catalog: (
            LocationCatalog
            | NationalMunicipalityCatalog
            | NoticeMunicipalityCatalog
            | None
        ) = None,
        fvg_location_catalog: LocationCatalog | None = None,
        geography_catalog: FvgGeographyCatalog | None = None,
        now: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    ) -> None:
        self._device_repository = device_repository
        self._audit_repository = audit_repository
        self._source = source
        self._sender = sender
        self._config = config
        self._fvg_location_catalog = fvg_location_catalog or LocationCatalog()
        self._location_catalog = location_catalog or NoticeMunicipalityCatalog(
            fvg_catalog=self._fvg_location_catalog
        )
        self._geography_catalog = (
            geography_catalog or get_default_fvg_geography_catalog()
        )
        self._now = now

    def _current_time(self) -> datetime:
        current = self._now()
        if current.tzinfo is None:
            current = current.replace(tzinfo=timezone.utc)
        return current.astimezone(timezone.utc)

    def _eligible_targets(
        self,
        devices: list[dict[str, Any]],
        *,
        now: datetime,
        require_fresh_location: bool = True,
        allow_saved_municipality_without_mode: bool = False,
    ) -> list[LocalNoticeDeliveryTarget]:
        eligible: list[LocalNoticeDeliveryTarget] = []
        for device in devices:
            preferences = device.get("preferences")
            platform = str(device.get("platform") or "")
            if (
                device.get("active") is not True
                or platform not in {"android", "web"}
                or not isinstance(preferences, Mapping)
                or preferences.get("weather_notices") is not True
            ):
                continue
            device_id = str(device.get("device_id") or "")
            if not _SHA256_PATTERN.fullmatch(device_id):
                continue
            if self._config.enrollment_mode == "owner_allowlist":
                if device_id != self._config.allowed_installation_hash:
                    continue
            else:
                app_id = str(device.get("app_check_app_id") or "")
                platform_allowed = (
                    platform == "android"
                    and app_id in self._config.allowed_app_ids
                    and android_app_version_allowed(
                        str(device.get("app_version") or ""),
                        allowed_app_versions=self._config.allowed_app_versions,
                        min_app_version_code=self._config.min_app_version_code,
                    )
                ) or (
                    platform == "web" and app_id in self._config.web_app_ids
                )
                if (
                    str(device.get("schema_version") or "") != "2.1"
                    or str(device.get("enrollment_generation") or "")
                    != self._config.enrollment_generation
                    or not platform_allowed
                ):
                    continue
            target_kind, target_value, _ = resolve_push_target(device)
            valid_target = (
                platform == "android" and target_kind == PUSH_TARGET_FCM_TOKEN
            ) or (
                platform == "web"
                and target_kind == PUSH_TARGET_FIREBASE_INSTALLATION_ID
            )
            if not valid_target or not target_value:
                continue
            stored = device.get("municipality")
            if not isinstance(stored, Mapping):
                continue
            municipality = self._location_catalog.match_istat(stored.get("istat"))
            if (
                municipality is None
                or str(stored.get("name") or "") != municipality.name
            ):
                continue
            locality = None
            stored_locality = device.get("locality")
            if stored_locality is not None:
                if not isinstance(stored_locality, Mapping):
                    continue
                locality = self._geography_catalog.match_locality_id(
                    stored_locality.get("id")
                )
                if (
                    locality is None
                    or locality.municipality_istat != municipality.istat_code
                    or str(stored_locality.get("name") or "") != locality.name
                ):
                    continue
            location_mode = str(device.get("location_mode") or "")
            evidence = device.get("location_evidence")
            captured_at = None
            received_at = None
            accuracy_m = None
            if location_mode not in {"automatic_gps", "manual_selection"} and not (
                allow_saved_municipality_without_mode and not location_mode
            ):
                continue
            if not location_mode:
                if evidence is not None:
                    continue
            elif location_mode == "manual_selection":
                if evidence is not None:
                    continue
            else:
                if platform != "android":
                    continue
                if (
                    self._fvg_location_catalog.match_istat(
                        municipality.istat_code
                    )
                    is None
                ):
                    continue
                if not isinstance(evidence, Mapping):
                    continue
                captured_at = _parse_datetime(evidence.get("captured_at"))
                received_at = _parse_datetime(evidence.get("received_at"))
                try:
                    accuracy_m = float(evidence.get("accuracy_m"))
                except (TypeError, ValueError):
                    continue
                if (
                    captured_at is None
                    or received_at is None
                    or accuracy_m < 0
                    or accuracy_m > 250
                    or captured_at
                    > now + timedelta(seconds=LOCAL_NOTICE_LOCATION_CLOCK_SKEW_SECONDS)
                    or received_at
                    > now + timedelta(seconds=LOCAL_NOTICE_LOCATION_CLOCK_SKEW_SECONDS)
                    or (
                        require_fresh_location
                        and (
                            (now - captured_at).total_seconds()
                            > LOCAL_NOTICE_LOCATION_MAX_AGE_SECONDS
                            or (now - received_at).total_seconds()
                            > LOCAL_NOTICE_LOCATION_MAX_AGE_SECONDS
                        )
                    )
                ):
                    continue
            eligible.append(
                LocalNoticeDeliveryTarget(
                    device=device,
                    municipality=municipality,
                    locality=locality,
                    target_value=target_value,
                    target_kind=target_kind,
                    target_hash=hash_push_target(target_value),
                    location_mode=location_mode,
                    location_captured_at=captured_at,
                    location_received_at=received_at,
                    location_accuracy_m=accuracy_m,
                )
            )
        return eligible

    def eligible_targets(
        self,
        devices: list[dict[str, Any]],
        *,
        now: datetime,
        require_fresh_location: bool = True,
        allow_saved_municipality_without_mode: bool = False,
    ) -> list[LocalNoticeDeliveryTarget]:
        """Resolve verified delivery targets without exposing device tokens."""

        return self._eligible_targets(
            devices,
            now=now,
            require_fresh_location=require_fresh_location,
            allow_saved_municipality_without_mode=(
                allow_saved_municipality_without_mode
            ),
        )

    def _audit(
        self,
        *,
        evaluation: Mapping[str, Any],
        municipality: Municipality,
        locality: FvgLocality | None = None,
        now: datetime,
        status: str,
        attempt_id: str,
        selected_kind: str = "",
        source_error_code: str = "",
    ) -> None:
        self._audit_repository.save_run(
            evaluation=evaluation,
            municipality=municipality,
            now=now,
            retention_days=self._config.retention_days,
            delivery_mode=self._config.mode,
            delivery_status=status,
            selected_kind=selected_kind,
            source_error_code=source_error_code,
            locality_id=locality.id if locality is not None else "",
            attempt_id=attempt_id,
        )

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

    def _deliver_target(
        self,
        *,
        target: LocalNoticeDeliveryTarget,
        selected: Mapping[str, Any],
        selected_kind: str,
    ) -> str:
        device_id = str(target.device.get("device_id") or "")
        claim_time = self._current_time()
        if not _candidate_is_promotable(
            selected,
            municipality=target.municipality,
            locality=target.locality,
            now=claim_time,
        ):
            return "expired"
        try:
            claim = self._device_repository.claim_local_notice_delivery(
                device_id=device_id,
                notice_signature=_candidate_signature(selected),
                notice_kind=selected_kind,
                target_kind=target.target_kind,
                target_hash=target.target_hash,
                expected_municipality_istat=target.municipality.istat_code,
                expected_locality_id=(
                    target.locality.id if target.locality is not None else ""
                ),
                expected_location_mode=target.location_mode,
                expected_location_captured_at=target.location_captured_at,
                expected_location_received_at=target.location_received_at,
                expected_location_accuracy_m=target.location_accuracy_m,
                expected_enrollment_generation=(
                    self._config.enrollment_generation
                    if self._config.enrollment_mode == "play_beta"
                    else ""
                ),
                expected_app_check_app_id=(
                    str(target.device.get("app_check_app_id") or "")
                    if self._config.enrollment_mode == "play_beta"
                    else ""
                ),
                expected_app_version=(
                    str(target.device.get("app_version") or "").strip().lower()
                    if self._config.enrollment_mode == "play_beta"
                    and str(target.device.get("platform") or "") == "android"
                    else ""
                ),
                max_location_age_seconds=LOCAL_NOTICE_LOCATION_MAX_AGE_SECONDS,
                now=claim_time,
            )
        except PushRepositoryUnavailable:
            return "storage_unavailable"

        if not claim.claimed:
            if claim.state == "sent":
                return "deduplicated"
            if claim.state in {"delivery_in_progress", "sending"}:
                return "in_progress"
            if claim.state in {
                "configuration_retry_scheduled",
                "retry_scheduled",
            }:
                return "retry_scheduled"
            if claim.state in {"device_inactive", "weather_notices_disabled"}:
                return "opted_out"
            if claim.state == "skipped_expired":
                return "expired"
            if claim.state in {
                "app_check_app_changed",
                "app_version_changed",
                "device_location_changed",
                "device_location_evidence_changed",
                "device_target_changed",
                "enrollment_generation_changed",
                "schema_version_changed",
            }:
                return "security_failed"
            if claim.state in {
                "failed_configuration",
                "failed_invalid_token",
                "retry_exhausted",
            }:
                return "device_failed"
            return "security_failed"

        expectations = {
            "expected_claim_id": claim.claim_id,
            "expected_target_kind": target.target_kind,
            "expected_target_hash": target.target_hash,
        }
        send_time = self._current_time()
        event_at = _parse_datetime(selected.get("event_at"))
        event_end = _parse_datetime(selected.get("event_end"))
        remaining_seconds = int(((event_end or send_time) - send_time).total_seconds())
        if (
            not _candidate_is_promotable(
                selected,
                municipality=target.municipality,
                locality=target.locality,
                now=send_time,
            )
            or remaining_seconds < 60
        ):
            try:
                confirmed = self._device_repository.finish_local_notice_delivery(
                    delivery_id=claim.delivery_id,
                    state="skipped_expired",
                    now=send_time,
                    error_code="notice_expired_before_send",
                    **expectations,
                )
            except PushRepositoryUnavailable:
                return "storage_unavailable"
            return "expired" if confirmed else "storage_unconfirmed"
        ttl_seconds = min(
            LOCAL_NOTICE_TTL_MAX_SECONDS,
            remaining_seconds,
        )
        try:
            message_id = self._sender.send(
                FcmOfficialAlertMessage(
                    title=LOCAL_NOTICE_TITLE,
                    body=_body(selected, target.municipality, target.locality),
                    data={
                        "type": "local_weather_notice",
                        "kind": selected_kind,
                        "municipality_istat": target.municipality.istat_code,
                        "locality_id": (
                            target.locality.id if target.locality is not None else ""
                        ),
                        "target_scope": (
                            "locality" if target.locality is not None else "municipality"
                        ),
                        "data_point_source": (
                            "rafvg_irdat_5000"
                            if target.locality is not None
                            else "municipality_catalog"
                        ),
                        "event_at": event_at.isoformat() if event_at else "",
                    },
                    ttl_seconds=ttl_seconds,
                    target_kind=target.target_kind,
                    target_value=target.target_value,
                    platform=str(target.device.get("platform") or ""),
                    channel_id=DEFAULT_ANDROID_LOCAL_NOTICE_CHANNEL,
                    collapse_key="mf-local-weather",
                    notification_tag="mf-local-weather",
                    web_link=f"{DEFAULT_WEB_APP_URL}/?tab=weather",
                )
            )
        except FcmTokenInvalid:
            finish_state = "failed_invalid_token"
            error_code = "fcm_token_invalid"
            status = "failed_invalid_token"
        except FcmConfigurationError:
            finish_state = "failed_configuration"
            error_code = "fcm_configuration_error"
            status = "failed_configuration"
        except FcmSenderUnavailable:
            finish_state = "failed_transient"
            error_code = "fcm_sender_unavailable"
            status = "failed_transient"
        else:
            try:
                confirmed = self._device_repository.finish_local_notice_delivery(
                    delivery_id=claim.delivery_id,
                    state="sent",
                    now=self._current_time(),
                    message_id=message_id,
                    **expectations,
                )
            except PushRepositoryUnavailable:
                return "storage_unavailable"
            return "sent" if confirmed else "sent_unconfirmed"

        finish_time = self._current_time()
        try:
            confirmed = self._device_repository.finish_local_notice_delivery(
                delivery_id=claim.delivery_id,
                state=finish_state,
                now=finish_time,
                error_code=error_code,
                **expectations,
            )
            if not confirmed:
                return "device_failed_unconfirmed"
            if status == "failed_invalid_token":
                self._device_repository.disable_device(
                    device_id=device_id,
                    expected_target_kind=target.target_kind,
                    expected_target_hash=target.target_hash,
                    reason="fcm_token_invalid",
                    now=finish_time,
                )
        except PushRepositoryUnavailable:
            return "device_failed_unconfirmed"
        return "device_failed"

    def _deliver_targets_batch(
        self,
        *,
        targets: list[LocalNoticeDeliveryTarget],
        selected: Mapping[str, Any],
        selected_kind: str,
    ) -> tuple[list[str], int]:
        results = ["device_failed"] * len(targets)
        pending = []
        messages: list[FcmOfficialAlertMessage] = []
        for index, target in enumerate(targets):
            device_id = str(target.device.get("device_id") or "")
            claim_time = self._current_time()
            if not _candidate_is_promotable(
                selected,
                municipality=target.municipality,
                locality=target.locality,
                now=claim_time,
            ):
                results[index] = "expired"
                continue
            try:
                claim = self._device_repository.claim_local_notice_delivery(
                    device_id=device_id,
                    notice_signature=_candidate_signature(selected),
                    notice_kind=selected_kind,
                    target_kind=target.target_kind,
                    target_hash=target.target_hash,
                    expected_municipality_istat=target.municipality.istat_code,
                    expected_locality_id=(
                        target.locality.id if target.locality is not None else ""
                    ),
                    expected_location_mode=target.location_mode,
                    expected_location_captured_at=target.location_captured_at,
                    expected_location_received_at=target.location_received_at,
                    expected_location_accuracy_m=target.location_accuracy_m,
                    expected_enrollment_generation=(
                        self._config.enrollment_generation
                        if self._config.enrollment_mode == "play_beta"
                        else ""
                    ),
                    expected_app_check_app_id=(
                        str(target.device.get("app_check_app_id") or "")
                        if self._config.enrollment_mode == "play_beta"
                        else ""
                    ),
                    expected_app_version=(
                        str(target.device.get("app_version") or "").strip().lower()
                        if self._config.enrollment_mode == "play_beta"
                        and str(target.device.get("platform") or "") == "android"
                        else ""
                    ),
                    max_location_age_seconds=LOCAL_NOTICE_LOCATION_MAX_AGE_SECONDS,
                    now=claim_time,
                )
            except PushRepositoryUnavailable:
                results[index] = "storage_unavailable"
                continue

            if not claim.claimed:
                if claim.state == "sent":
                    results[index] = "deduplicated"
                elif claim.state in {"delivery_in_progress", "sending"}:
                    results[index] = "in_progress"
                elif claim.state in {
                    "configuration_retry_scheduled",
                    "retry_scheduled",
                }:
                    results[index] = "retry_scheduled"
                elif claim.state in {
                    "device_inactive",
                    "weather_notices_disabled",
                }:
                    results[index] = "opted_out"
                elif claim.state == "skipped_expired":
                    results[index] = "expired"
                elif claim.state in {
                    "app_check_app_changed",
                    "app_version_changed",
                    "device_location_changed",
                    "device_location_evidence_changed",
                    "device_target_changed",
                    "enrollment_generation_changed",
                    "schema_version_changed",
                }:
                    results[index] = "security_failed"
                elif claim.state in {
                    "failed_configuration",
                    "failed_invalid_token",
                    "retry_exhausted",
                }:
                    results[index] = "device_failed"
                else:
                    results[index] = "security_failed"
                continue

            expectations = {
                "expected_claim_id": claim.claim_id,
                "expected_target_kind": target.target_kind,
                "expected_target_hash": target.target_hash,
            }
            send_time = self._current_time()
            event_at = _parse_datetime(selected.get("event_at"))
            event_end = _parse_datetime(selected.get("event_end"))
            remaining_seconds = int(
                ((event_end or send_time) - send_time).total_seconds()
            )
            if (
                not _candidate_is_promotable(
                    selected,
                    municipality=target.municipality,
                    locality=target.locality,
                    now=send_time,
                )
                or remaining_seconds < 60
            ):
                try:
                    confirmed = (
                        self._device_repository.finish_local_notice_delivery(
                            delivery_id=claim.delivery_id,
                            state="skipped_expired",
                            now=send_time,
                            error_code="notice_expired_before_send",
                            **expectations,
                        )
                    )
                except PushRepositoryUnavailable:
                    results[index] = "storage_unavailable"
                else:
                    results[index] = (
                        "expired" if confirmed else "storage_unconfirmed"
                    )
                continue

            pending.append((index, target, claim, expectations))
            messages.append(FcmOfficialAlertMessage(
                title=LOCAL_NOTICE_TITLE,
                body=_body(selected, target.municipality, target.locality),
                data={
                    "type": "local_weather_notice",
                    "kind": selected_kind,
                    "municipality_istat": target.municipality.istat_code,
                    "locality_id": (
                        target.locality.id if target.locality is not None else ""
                    ),
                    "target_scope": (
                        "locality" if target.locality is not None else "municipality"
                    ),
                    "data_point_source": (
                        "rafvg_irdat_5000"
                        if target.locality is not None
                        else "municipality_catalog"
                    ),
                    "event_at": event_at.isoformat() if event_at else "",
                },
                ttl_seconds=min(
                    LOCAL_NOTICE_TTL_MAX_SECONDS,
                    remaining_seconds,
                ),
                target_kind=target.target_kind,
                target_value=target.target_value,
                platform=str(target.device.get("platform") or ""),
                channel_id=DEFAULT_ANDROID_LOCAL_NOTICE_CHANNEL,
                collapse_key="mf-local-weather",
                notification_tag="mf-local-weather",
                web_link=f"{DEFAULT_WEB_APP_URL}/?tab=weather",
            ))

        if not messages:
            return results, 0
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

        for (index, target, claim, expectations), outcome in zip(
            pending, outcomes, strict=True
        ):
            finish_time = self._current_time()
            try:
                if outcome.success:
                    confirmed = (
                        self._device_repository.finish_local_notice_delivery(
                            delivery_id=claim.delivery_id,
                            state="sent",
                            now=finish_time,
                            message_id=outcome.message_id,
                            **expectations,
                        )
                    )
                    results[index] = (
                        "sent" if confirmed else "sent_unconfirmed"
                    )
                    continue
                finish_state = (
                    "failed_invalid_token"
                    if outcome.error_code == "fcm_token_invalid"
                    else "failed_configuration"
                    if outcome.error_code == "fcm_configuration_error"
                    else "failed_transient"
                )
                confirmed = self._device_repository.finish_local_notice_delivery(
                    delivery_id=claim.delivery_id,
                    state=finish_state,
                    now=finish_time,
                    error_code=outcome.error_code or "fcm_sender_unavailable",
                    **expectations,
                )
                if not confirmed:
                    results[index] = "device_failed_unconfirmed"
                    continue
                if outcome.error_code == "fcm_token_invalid":
                    self._device_repository.disable_device(
                        device_id=str(target.device.get("device_id") or ""),
                        expected_target_kind=target.target_kind,
                        expected_target_hash=target.target_hash,
                        reason="fcm_token_invalid",
                        now=finish_time,
                    )
                results[index] = "device_failed"
            except PushRepositoryUnavailable:
                results[index] = "device_failed_unconfirmed"
        return results, 1

    def run(self) -> LocalNoticeDeliveryResult:
        if self._config.mode == "off":
            return LocalNoticeDeliveryResult(status="disabled")
        attempt_id = uuid.uuid4().hex
        try:
            enrollment_generation = (
                self._config.enrollment_generation
                if self._config.enrollment_mode == "play_beta"
                else None
            )
            read_method = getattr(
                self._device_repository,
                "read_active_devices",
                None,
            )
            if callable(read_method):
                read_result = read_method(
                    max_devices=self._config.max_devices,
                    enrollment_generation=enrollment_generation,
                )
                devices = list(read_result.devices)
                pages_processed = int(read_result.pages_processed)
            else:
                devices = self._device_repository.list_active_devices(
                    max_devices=self._config.max_devices,
                    enrollment_generation=enrollment_generation,
                )
                pages_processed = 1 if devices else 0
        except PushRepositoryUnavailable as error:
            raise LocalNoticeDeliveryDeviceStateUnavailable(
                "local_notice_device_state_unavailable"
            ) from error

        current = self._current_time()
        targets = self._eligible_targets(devices, now=current)
        if not targets:
            return LocalNoticeDeliveryResult(
                status="no_eligible_device",
                pages_processed=pages_processed,
            )

        canonical_group_count = len({target.group_key for target in targets})
        failed_group_keys: set[tuple[str, str]] = set()
        duplicate_targets = security_failed = failed = 0
        by_target_hash: dict[str, list[LocalNoticeDeliveryTarget]] = {}
        for target in targets:
            by_target_hash.setdefault(target.target_hash, []).append(target)
        collapsed_targets: list[LocalNoticeDeliveryTarget] = []
        for target_hash in sorted(by_target_hash):
            matching = sorted(
                by_target_hash[target_hash],
                key=lambda item: str(item.device.get("device_id") or ""),
            )
            if len(matching) == 1:
                collapsed_targets.append(matching[0])
                continue
            duplicate_targets += len(matching) - 1
            security_failed += 1
            failed += 1
            failed_group_keys.update(item.group_key for item in matching)
            if len({item.group_key for item in matching}) == 1:
                collapsed_targets.append(matching[0])

        grouped: dict[tuple[str, str], list[LocalNoticeDeliveryTarget]] = {}
        for target in collapsed_targets:
            grouped.setdefault(target.group_key, []).append(target)

        evaluated = candidates_total = attempted = sent = sent_unconfirmed = 0
        deduplicated = 0
        persisted = 0
        in_progress = retry_scheduled = opted_out = expired = 0
        device_failed = storage_failed = audit_failed = source_failed = 0
        selected_kinds: set[str] = set()
        outcomes: list[str] = []
        delivery_batches = 0
        quality_counter = QualityCounter()
        data_degraded_groups = 0

        for group_key in sorted(grouped):
            group_targets = grouped[group_key]
            primary = group_targets[0]
            municipality = primary.municipality
            locality = primary.locality

            try:
                snapshot = self._source.fetch(municipality, locality)
            except LocalNoticeSourceUnavailable as error:
                error_time = self._current_time()
                failure_evaluation = _source_failure_evaluation(now=error_time)
                failure_evaluation["data_quality"] = evaluation_quality({}, [], [], failure="source_unavailable")
                quality_counter.add(group_key, failure_evaluation["data_quality"])
                try:
                    self._audit(
                        evaluation=failure_evaluation,
                        municipality=municipality,
                        locality=locality,
                        now=error_time,
                        status="source_unavailable",
                        attempt_id=attempt_id,
                        source_error_code=error.code,
                    )
                    persisted += 1
                except LocalNoticeDeliveryAuditUnavailable:
                    audit_failed += 1
                    failed += 1
                outcomes.append("source_unavailable")
                source_failed += 1
                failed += 1
                failed_group_keys.add(group_key)
                continue
            except Exception:
                outcomes.append("source_error")
                quality_counter.add(group_key, evaluation_quality({}, [], [], failure="source_error"))
                source_failed += 1
                failed += 1
                failed_group_keys.add(group_key)
                continue

            evaluation_time = self._current_time()
            try:
                evaluation = evaluate_local_notice_shadow(
                    municipality.istat_code,
                    snapshot,
                    now=evaluation_time,
                    catalog=self._location_catalog,
                    locality=locality,
                )
            except Exception:
                outcomes.append("detector_error")
                quality_counter.add(group_key, evaluation_quality(snapshot, [], [], failure="detector_error"))
                source_failed += 1
                failed += 1
                failed_group_keys.add(group_key)
                continue
            group_candidates = evaluation.get("candidates")
            evaluated += len(group_targets)
            if (
                evaluation.get("shadow_only") is not True
                or evaluation.get("can_send") is not False
                or not isinstance(group_candidates, list)
            ):
                outcomes.append("detector_contract_invalid")
                quality_counter.add(group_key, evaluation_quality(snapshot, [], [], failure="detector_contract_invalid"))
                source_failed += 1
                failed += 1
                failed_group_keys.add(group_key)
                continue
            quality_counter.add(group_key, evaluation.get("data_quality"))
            data_degraded = evaluation.get("status") in {"partial_evaluation", "not_evaluable"}
            data_degraded_groups += int(data_degraded)
            candidates_total += len(group_candidates)
            if evaluation.get("status") == "rejected":
                try:
                    self._audit(
                        evaluation=evaluation,
                        municipality=municipality,
                        locality=locality,
                        now=evaluation_time,
                        status="rejected",
                        attempt_id=attempt_id,
                    )
                    persisted += 1
                except LocalNoticeDeliveryAuditUnavailable:
                    audit_failed += 1
                    failed += 1
                outcomes.append("rejected")
                source_failed += 1
                failed += 1
                failed_group_keys.add(group_key)
                continue

            promotable = [
                candidate
                for candidate in group_candidates
                if isinstance(candidate, Mapping)
                and _candidate_is_promotable(
                    candidate,
                    municipality=municipality,
                    locality=locality,
                    now=evaluation_time,
                )
            ]
            promotable.sort(
                key=lambda item: (
                    -int(item.get("priority") or 0),
                    str(item.get("event_at") or ""),
                    str(item.get("kind") or ""),
                )
            )
            if not promotable:
                group_status = (evaluation["status"] if data_degraded else
                                "no_candidate" if not group_candidates else "not_eligible")
                try:
                    self._audit(
                        evaluation=evaluation,
                        municipality=municipality,
                        locality=locality,
                        now=evaluation_time,
                        status=group_status,
                        attempt_id=attempt_id,
                    )
                    persisted += 1
                except LocalNoticeDeliveryAuditUnavailable:
                    audit_failed += 1
                    failed += 1
                    failed_group_keys.add(group_key)
                outcomes.append(group_status)
                continue

            selected = promotable[0]
            selected_kind = str(selected.get("kind") or "")
            selected_kinds.add(selected_kind)
            try:
                self._audit(
                    evaluation=evaluation,
                    municipality=municipality,
                    locality=locality,
                    now=evaluation_time,
                    status="planned" if self._config.mode == "send" else "dry_run",
                    attempt_id=attempt_id,
                    selected_kind=selected_kind,
                )
                persisted += 1
            except LocalNoticeDeliveryAuditUnavailable:
                outcomes.append("audit_storage_unavailable")
                audit_failed += 1
                failed += 1
                failed_group_keys.add(group_key)
                continue

            attempted += len(group_targets)
            if self._config.mode == "dry_run":
                outcomes.append("dry_run")
                continue

            group_sent = group_sent_unconfirmed = group_deduplicated = 0
            group_failed = 0
            group_in_progress = group_retry = group_opted_out = group_expired = 0
            delivery_statuses: list[str] = []
            batch_size = max(1, min(self._config.max_devices, 500))
            for offset in range(0, len(group_targets), batch_size):
                batch_targets = group_targets[offset:offset + batch_size]
                try:
                    batch_statuses, batch_count = self._deliver_targets_batch(
                        targets=batch_targets,
                        selected=selected,
                        selected_kind=selected_kind,
                    )
                except Exception:
                    batch_statuses = ["device_failed"] * len(batch_targets)
                    batch_count = 0
                delivery_statuses.extend(batch_statuses)
                delivery_batches += batch_count
            for delivery_status in delivery_statuses:
                if delivery_status == "sent":
                    sent += 1
                    group_sent += 1
                elif delivery_status == "sent_unconfirmed":
                    sent_unconfirmed += 1
                    storage_failed += 1
                    failed += 1
                    group_sent_unconfirmed += 1
                    group_failed += 1
                elif delivery_status == "deduplicated":
                    deduplicated += 1
                    group_deduplicated += 1
                elif delivery_status == "in_progress":
                    in_progress += 1
                    group_in_progress += 1
                elif delivery_status == "retry_scheduled":
                    retry_scheduled += 1
                    group_retry += 1
                elif delivery_status == "opted_out":
                    opted_out += 1
                    group_opted_out += 1
                elif delivery_status == "expired":
                    expired += 1
                    group_expired += 1
                elif delivery_status == "security_failed":
                    security_failed += 1
                    failed += 1
                    group_failed += 1
                elif delivery_status == "device_failed":
                    device_failed += 1
                    failed += 1
                    group_failed += 1
                elif delivery_status in {
                    "storage_unavailable",
                    "storage_unconfirmed",
                }:
                    storage_failed += 1
                    failed += 1
                    group_failed += 1
                elif delivery_status == "device_failed_unconfirmed":
                    device_failed += 1
                    storage_failed += 1
                    failed += 1
                    group_failed += 1
                else:
                    device_failed += 1
                    failed += 1
                    group_failed += 1

            if group_sent_unconfirmed:
                group_status = "sent_unconfirmed"
                failed_group_keys.add(group_key)
            elif group_failed:
                group_status = (
                    "partial"
                    if (
                        group_sent
                        or group_deduplicated
                        or group_in_progress
                        or group_retry
                        or group_opted_out
                        or group_expired
                    )
                    else "failed"
                )
                failed_group_keys.add(group_key)
            elif group_sent:
                group_status = "sent"
            elif group_deduplicated:
                group_status = "deduplicated"
            elif group_in_progress:
                group_status = "in_progress"
            elif group_retry:
                group_status = "retry_scheduled"
            elif group_opted_out:
                group_status = "opted_out"
            else:
                group_status = "expired"
            outcomes.append(group_status)
            try:
                self._audit(
                    evaluation=evaluation,
                    municipality=municipality,
                    locality=locality,
                    now=self._current_time(),
                    status=group_status,
                    attempt_id=attempt_id,
                    selected_kind=selected_kind,
                )
            except LocalNoticeDeliveryAuditUnavailable:
                audit_failed += 1
                failed += 1
                failed_group_keys.add(group_key)

        selected_kind = (
            next(iter(selected_kinds))
            if len(selected_kinds) == 1
            else "multiple" if selected_kinds else ""
        )
        successful_outcomes = {
            "deduplicated",
            "dry_run",
            "no_candidate",
            "not_eligible",
            "in_progress",
            "retry_scheduled",
            "opted_out",
            "expired",
            "sent",
        }
        if failed:
            if (
                sent
                or deduplicated
                or in_progress
                or retry_scheduled
                or opted_out
                or expired
                or any(outcome in successful_outcomes for outcome in outcomes)
            ):
                status = "partial"
            elif outcomes and set(outcomes) == {"source_unavailable"}:
                status = "source_unavailable"
            elif outcomes and set(outcomes) == {"rejected"}:
                status = "rejected"
            elif outcomes and set(outcomes) == {"sent_unconfirmed"}:
                status = "sent_unconfirmed"
            else:
                status = "failed"
        elif data_degraded_groups:
            # Deliberately absent from the job's success statuses until the
            # pre-release monitoring-policy check authorizes the exit change.
            status = "data_degraded"
        elif self._config.mode == "dry_run" and attempted:
            status = "dry_run"
        elif sent:
            status = "sent"
        elif deduplicated:
            status = "deduplicated"
        elif in_progress:
            status = "in_progress"
        elif retry_scheduled:
            status = "retry_scheduled"
        elif opted_out:
            status = "opted_out"
        elif expired:
            status = "expired"
        elif candidates_total:
            status = "not_eligible"
        else:
            status = "no_candidate"

        return LocalNoticeDeliveryResult(
            status=status,
            eligible_devices=len(targets),
            evaluated=evaluated,
            candidates=candidates_total,
            selected_kind=selected_kind,
            attempted=attempted,
            sent=sent,
            sent_unconfirmed=sent_unconfirmed,
            deduplicated=deduplicated,
            persisted=persisted,
            failed=failed,
            groups=canonical_group_count,
            failed_groups=len(failed_group_keys),
            in_progress=in_progress,
            retry_scheduled=retry_scheduled,
            opted_out=opted_out,
            expired=expired,
            duplicate_targets=duplicate_targets,
            security_failed=security_failed,
            device_failed=device_failed,
            storage_failed=storage_failed,
            audit_failed=audit_failed,
            source_failed=source_failed,
            data_degraded_groups=data_degraded_groups,
            pages_processed=pages_processed,
            delivery_batches=delivery_batches,
            data_quality=quality_counter.summary(),
        )


@lru_cache(maxsize=1)
def get_local_notice_delivery_service() -> LocalNoticeDeliveryService:
    config = LocalNoticeDeliveryConfig.from_environment()
    return LocalNoticeDeliveryService(
        device_repository=PushDeviceRepository(get_firestore_client),
        audit_repository=LocalNoticeDeliveryAuditRepository(get_firestore_client),
        source=RoutedIconLocalNoticeSource(
            timeout_seconds=config.source_timeout_seconds
        ),
        sender=FirebaseCloudMessagingSender(),
        config=config,
        location_catalog=NoticeMunicipalityCatalog(),
    )


def reset_local_notice_delivery_service_for_tests() -> None:
    get_local_notice_delivery_service.cache_clear()


__all__ = [
    "LocalNoticeDeliveryAuditUnavailable",
    "LocalNoticeDeliveryConfig",
    "LocalNoticeDeliveryConfigurationError",
    "LocalNoticeDeliveryDeviceStateUnavailable",
    "LocalNoticeDeliveryResult",
    "LocalNoticeDeliveryService",
    "get_local_notice_delivery_service",
    "reset_local_notice_delivery_service_for_tests",
]
