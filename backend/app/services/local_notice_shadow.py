"""Owner-only runtime orchestration for local weather shadow evaluations."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from functools import lru_cache
from typing import Any, Callable

from app.infrastructure.firebase import get_firestore_client
from app.repositories.local_notice_shadow import (
    LocalNoticeShadowRepository,
    LocalNoticeShadowRepositoryUnavailable,
)
from app.repositories.push import PushDeviceRepository, PushRepositoryUnavailable
from app.services.location import LocationCatalog, Municipality
from app.services.fvg_geography import (
    FvgGeographyCatalog,
    FvgLocality,
    get_default_fvg_geography_catalog,
)
from app.weather.local_notice_shadow import (
    FVG_TIMEZONE,
    POLICY_VERSION,
    SCHEMA_VERSION,
    SOURCE_ID,
    evaluate_local_notice_shadow,
)
from app.weather.local_notice_source import (
    DEFAULT_LOCAL_NOTICE_SOURCE_TIMEOUT_SECONDS,
    IconLocalNoticeSource,
    LocalNoticeSourceUnavailable,
    MAX_LOCAL_NOTICE_SOURCE_TIMEOUT_SECONDS,
)


LOCAL_NOTICE_SHADOW_MODE_ENV = "LOCAL_NOTICE_SHADOW_MODE"
LOCAL_NOTICE_SHADOW_RETENTION_DAYS_ENV = "LOCAL_NOTICE_SHADOW_RETENTION_DAYS"
LOCAL_NOTICE_SOURCE_TIMEOUT_SECONDS_ENV = "LOCAL_NOTICE_SOURCE_TIMEOUT_SECONDS"
LOCAL_NOTICE_SHADOW_MAX_MUNICIPALITIES_ENV = (
    "LOCAL_NOTICE_SHADOW_MAX_MUNICIPALITIES"
)
PUSH_PILOT_MAX_DEVICES_ENV = "PUSH_PILOT_MAX_DEVICES"


class LocalNoticeShadowConfigurationError(RuntimeError):
    """The shadow runner configuration is invalid and remains disabled."""


class LocalNoticeShadowDeviceStateUnavailable(RuntimeError):
    """The registered pilot device state could not be read safely."""


@dataclass(frozen=True)
class LocalNoticeShadowConfig:
    mode: str
    retention_days: int
    source_timeout_seconds: float
    max_municipalities: int
    max_devices: int

    @classmethod
    def from_environment(cls) -> "LocalNoticeShadowConfig":
        mode = (
            os.getenv(LOCAL_NOTICE_SHADOW_MODE_ENV, "off").strip().lower()
            or "off"
        )
        if mode not in {"off", "shadow"}:
            raise LocalNoticeShadowConfigurationError(
                "local_notice_shadow_mode_invalid"
            )

        try:
            retention_days = int(
                os.getenv(LOCAL_NOTICE_SHADOW_RETENTION_DAYS_ENV, "14").strip()
                or "14"
            )
            source_timeout_seconds = float(
                os.getenv(
                    LOCAL_NOTICE_SOURCE_TIMEOUT_SECONDS_ENV,
                    str(DEFAULT_LOCAL_NOTICE_SOURCE_TIMEOUT_SECONDS),
                ).strip()
                or str(DEFAULT_LOCAL_NOTICE_SOURCE_TIMEOUT_SECONDS)
            )
            max_municipalities = int(
                os.getenv(
                    LOCAL_NOTICE_SHADOW_MAX_MUNICIPALITIES_ENV,
                    "1",
                ).strip()
                or "1"
            )
            max_devices = int(
                os.getenv(PUSH_PILOT_MAX_DEVICES_ENV, "1").strip() or "1"
            )
        except ValueError as error:
            raise LocalNoticeShadowConfigurationError(
                "local_notice_shadow_numeric_config_invalid"
            ) from error

        if retention_days < 1 or retention_days > 30:
            raise LocalNoticeShadowConfigurationError(
                "local_notice_shadow_retention_invalid"
            )
        if (
            source_timeout_seconds < 1
            or source_timeout_seconds > MAX_LOCAL_NOTICE_SOURCE_TIMEOUT_SECONDS
        ):
            raise LocalNoticeShadowConfigurationError(
                "local_notice_shadow_timeout_invalid"
            )
        if max_municipalities != 1:
            raise LocalNoticeShadowConfigurationError(
                "local_notice_shadow_owner_limit_invalid"
            )
        if max_devices < 1 or max_devices > 10:
            raise LocalNoticeShadowConfigurationError(
                "local_notice_shadow_device_limit_invalid"
            )

        return cls(
            mode=mode,
            retention_days=retention_days,
            source_timeout_seconds=source_timeout_seconds,
            max_municipalities=max_municipalities,
            max_devices=max_devices,
        )


@dataclass(frozen=True)
class LocalNoticeShadowRunResult:
    status: str
    eligible_municipalities: int = 0
    evaluated: int = 0
    candidates: int = 0
    rejected: int = 0
    persisted: int = 0
    failed: int = 0

    def summary(self) -> dict[str, int | str]:
        return {
            "status": self.status,
            "eligible_municipalities": self.eligible_municipalities,
            "evaluated": self.evaluated,
            "candidates": self.candidates,
            "rejected": self.rejected,
            "persisted": self.persisted,
            "failed": self.failed,
        }


def _source_failure_evaluation(*, now: datetime) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "policy_version": POLICY_VERSION,
        "mode": "shadow",
        "shadow_only": True,
        "can_send": False,
        "status": "source_unavailable",
        "evaluated_at": now.isoformat(timespec="minutes"),
        "snapshot": {
            "source": SOURCE_ID,
            "fetched_at": "",
            "timezone": FVG_TIMEZONE,
            "eligible_slots": 0,
        },
        "validation_errors": [],
        "candidates": [],
        "observations": [],
    }


class LocalNoticeShadowService:
    """Evaluate registered municipalities and persist evidence, never notifications."""

    def __init__(
        self,
        *,
        device_repository: PushDeviceRepository | Any,
        shadow_repository: LocalNoticeShadowRepository | Any,
        source: IconLocalNoticeSource | Any,
        config: LocalNoticeShadowConfig,
        location_catalog: LocationCatalog | None = None,
        geography_catalog: FvgGeographyCatalog | None = None,
        now: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    ) -> None:
        self._device_repository = device_repository
        self._shadow_repository = shadow_repository
        self._source = source
        self._config = config
        self._location_catalog = location_catalog or LocationCatalog()
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
    ) -> tuple[list[tuple[Municipality, FvgLocality | None]], int]:
        targets: dict[str, tuple[Municipality, FvgLocality | None]] = {}
        invalid_targets = 0
        for device in devices:
            preferences = device.get("preferences")
            if (
                device.get("active") is not True
                or device.get("platform") != "android"
                or not isinstance(preferences, Mapping)
                or preferences.get("weather_notices") is not True
            ):
                continue
            stored = device.get("municipality")
            if not isinstance(stored, Mapping):
                continue
            canonical = self._location_catalog.match_istat(stored.get("istat"))
            if canonical is None or str(stored.get("name") or "") != canonical.name:
                invalid_targets += 1
                continue
            locality = None
            stored_locality = device.get("locality")
            if stored_locality is not None:
                if not isinstance(stored_locality, Mapping):
                    invalid_targets += 1
                    continue
                locality = self._geography_catalog.match_locality_id(
                    stored_locality.get("id")
                )
                if (
                    locality is None
                    or locality.municipality_istat != canonical.istat_code
                    or str(stored_locality.get("name") or "") != locality.name
                ):
                    invalid_targets += 1
                    continue
            target_key = locality.id if locality is not None else canonical.istat_code
            targets[target_key] = (canonical, locality)
        return list(targets.values()), invalid_targets

    def run(self) -> LocalNoticeShadowRunResult:
        if self._config.mode == "off":
            return LocalNoticeShadowRunResult(status="disabled")

        try:
            devices = self._device_repository.list_active_devices(
                max_devices=self._config.max_devices
            )
        except PushRepositoryUnavailable as error:
            raise LocalNoticeShadowDeviceStateUnavailable(
                "local_notice_shadow_device_state_unavailable"
            ) from error

        targets, invalid_targets = self._eligible_targets(devices)
        if len(targets) > self._config.max_municipalities:
            return LocalNoticeShadowRunResult(
                status="target_limit_exceeded",
                eligible_municipalities=len(targets),
                rejected=invalid_targets,
                failed=1,
            )
        if not targets:
            if invalid_targets:
                return LocalNoticeShadowRunResult(
                    status="invalid_target_state",
                    rejected=invalid_targets,
                    failed=1,
                )
            return LocalNoticeShadowRunResult(status="no_eligible_municipality")

        current = self._current_time()
        municipality, locality = targets[0]
        try:
            snapshot = self._source.fetch(municipality, locality)
        except LocalNoticeSourceUnavailable as error:
            self._shadow_repository.save_run(
                evaluation=_source_failure_evaluation(now=current),
                municipality=municipality,
                now=current,
                retention_days=self._config.retention_days,
                source_error_code=error.code,
            )
            return LocalNoticeShadowRunResult(
                status="source_unavailable",
                eligible_municipalities=1,
                persisted=1,
                failed=1,
            )

        evaluation = evaluate_local_notice_shadow(
            municipality.istat_code,
            snapshot,
            now=current,
            catalog=self._location_catalog,
            locality=locality,
        )
        if (
            evaluation.get("shadow_only") is not True
            or evaluation.get("can_send") is not False
        ):
            raise LocalNoticeShadowConfigurationError(
                "local_notice_shadow_send_guard_failed"
            )
        candidates = evaluation.get("candidates") or []
        if not isinstance(candidates, list) or any(
            not isinstance(candidate, Mapping)
            or candidate.get("shadow_only") is not True
            or candidate.get("can_notify") is not False
            for candidate in candidates
        ):
            raise LocalNoticeShadowConfigurationError(
                "local_notice_shadow_candidate_guard_failed"
            )

        self._shadow_repository.save_run(
            evaluation=evaluation,
            municipality=municipality,
            now=current,
            retention_days=self._config.retention_days,
        )
        candidate_count = len(candidates)
        rejected = int(evaluation.get("status") == "rejected")
        return LocalNoticeShadowRunResult(
            status="rejected" if rejected else "completed",
            eligible_municipalities=1,
            evaluated=1,
            candidates=candidate_count,
            rejected=rejected + invalid_targets,
            persisted=1,
            failed=rejected,
        )


@lru_cache(maxsize=1)
def get_local_notice_shadow_service() -> LocalNoticeShadowService:
    config = LocalNoticeShadowConfig.from_environment()
    return LocalNoticeShadowService(
        device_repository=PushDeviceRepository(get_firestore_client),
        shadow_repository=LocalNoticeShadowRepository(get_firestore_client),
        source=IconLocalNoticeSource(
            timeout_seconds=config.source_timeout_seconds
        ),
        config=config,
    )


def reset_local_notice_shadow_service_for_tests() -> None:
    get_local_notice_shadow_service.cache_clear()


__all__ = [
    "LocalNoticeShadowConfig",
    "LocalNoticeShadowConfigurationError",
    "LocalNoticeShadowDeviceStateUnavailable",
    "LocalNoticeShadowRepositoryUnavailable",
    "LocalNoticeShadowRunResult",
    "LocalNoticeShadowService",
    "get_local_notice_shadow_service",
    "reset_local_notice_shadow_service_for_tests",
]
