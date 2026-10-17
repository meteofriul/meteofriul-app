"""Daily morning forecast delivery for verified notification subscribers."""

from __future__ import annotations

import hashlib
import math
import os
import re
from collections.abc import Mapping
from dataclasses import dataclass, replace
from datetime import date, datetime, timedelta, timezone
from functools import lru_cache
from typing import Any, Callable

from app.infrastructure.firebase import get_firestore_client
from app.push.fcm import (
    DEFAULT_ANDROID_LOCAL_NOTICE_CHANNEL,
    DEFAULT_WEB_APP_URL,
    FcmBatchOutcome,
    FcmConfigurationError,
    FcmOfficialAlertMessage,
    FcmSenderUnavailable,
    FcmTokenInvalid,
    FirebaseCloudMessagingSender,
)
from app.repositories.push import PushDeviceRepository, PushRepositoryUnavailable
from app.services.fvg_geography import FvgLocality
from app.services.local_notice_delivery import (
    LocalNoticeDeliveryConfig,
    LocalNoticeDeliveryConfigurationError,
    LocalNoticeDeliveryDeviceStateUnavailable,
    LocalNoticeDeliveryService,
    LocalNoticeDeliveryTarget,
)
from app.services.location import LocationCatalog, Municipality
from app.services.notice_municipalities import NoticeMunicipalityCatalog
from app.weather.local_notice_shadow import FVG_ZONE
from app.weather.local_notice_source import (
    LocalNoticeSourceUnavailable,
    RoutedIconLocalNoticeSource,
)


MORNING_FORECAST_MODE_ENV = "MORNING_FORECAST_DELIVERY_MODE"
MORNING_FORECAST_REQUIRE_SINGLE_TARGET_ENV = (
    "MORNING_FORECAST_REQUIRE_SINGLE_TARGET"
)
MORNING_FORECAST_TEST_RUN_ID_ENV = "MORNING_FORECAST_TEST_RUN_ID"
MORNING_FORECAST_TEST_PLATFORM_ENV = "MORNING_FORECAST_TEST_PLATFORM"
MORNING_FORECAST_TITLE = "Meteo Friûl"
MORNING_FORECAST_KIND = "morning_forecast"
MORNING_FORECAST_HOURS = 24
MORNING_FORECAST_TTL_SECONDS = 3 * 60 * 60
MORNING_SAVED_LOCATION_MAX_AGE_SECONDS = 10 * 365 * 24 * 60 * 60


class MorningForecastConfigurationError(RuntimeError):
    """The morning dispatcher is not configured safely."""


@dataclass(frozen=True)
class ForecastNotificationContent:
    title: str
    body: str


@dataclass(frozen=True)
class MorningForecastDeliveryResult:
    status: str
    eligible_devices: int = 0
    evaluated: int = 0
    attempted: int = 0
    sent: int = 0
    sent_unconfirmed: int = 0
    deduplicated: int = 0
    failed: int = 0
    groups: int = 0
    failed_groups: int = 0
    in_progress: int = 0
    retry_scheduled: int = 0
    opted_out: int = 0
    retired_targets: int = 0
    duplicate_targets: int = 0
    security_failed: int = 0
    device_failed: int = 0
    storage_failed: int = 0
    source_failed: int = 0
    pages_processed: int = 0
    delivery_batches: int = 0

    def summary(self) -> dict[str, int | str]:
        return {
            "status": self.status,
            "eligible_devices": self.eligible_devices,
            "evaluated": self.evaluated,
            "attempted": self.attempted,
            "sent": self.sent,
            "sent_unconfirmed": self.sent_unconfirmed,
            "deduplicated": self.deduplicated,
            "failed": self.failed,
            "groups": self.groups,
            "failed_groups": self.failed_groups,
            "in_progress": self.in_progress,
            "retry_scheduled": self.retry_scheduled,
            "opted_out": self.opted_out,
            "retired_targets": self.retired_targets,
            "duplicate_targets": self.duplicate_targets,
            "security_failed": self.security_failed,
            "device_failed": self.device_failed,
            "storage_failed": self.storage_failed,
            "source_failed": self.source_failed,
            "pages_processed": self.pages_processed,
            "delivery_batches": self.delivery_batches,
        }


def _finite_number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    numeric = float(value)
    return numeric if math.isfinite(numeric) else None


def _forecast_time(value: Any) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(str(value or "").replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=FVG_ZONE)
    return parsed.astimezone(FVG_ZONE)


def _condition_phrase(code: int) -> str:
    if code == 0:
        return "cielo sereno"
    if code == 1:
        return "cielo prevalentemente sereno"
    if code == 2:
        return "cielo parzialmente nuvoloso"
    if code == 3:
        return "cielo nuvoloso"
    if code in {45, 48}:
        return "nebbia"
    if code in {51, 53, 55, 56, 57}:
        return "pioviggine"
    if code in {61, 63, 65, 66, 67}:
        return "pioggia"
    if code in {71, 73, 75, 77, 85, 86}:
        return "neve"
    if code in {80, 81, 82}:
        return "rovesci"
    if code in {95, 96, 99}:
        return "temporali"
    return "tempo variabile"


def _period_phrase(hour: int) -> str:
    if hour < 12:
        return "in mattinata"
    if hour < 18:
        return "dal pomeriggio"
    return "in serata"


def _precipitation_phrase(rows: list[dict[str, Any]]) -> str:
    for row in rows:
        code = int(row["weather_code"])
        precipitation = max(
            float(row["precipitation"]),
            float(row["rain"]),
            float(row["showers"]),
        )
        if precipitation <= 0.1 and code not in {
            51, 53, 55, 56, 57, 61, 63, 65, 66, 67,
            71, 73, 75, 77, 80, 81, 82, 85, 86, 95, 96, 99,
        }:
            continue
        period = _period_phrase(row["time"].hour)
        if code in {95, 96, 99}:
            return f"possibili temporali {period}"
        if code in {71, 73, 75, 77, 85, 86}:
            return f"possibili nevicate {period}"
        if code in {56, 57, 66, 67}:
            return f"possibili precipitazioni gelate {period}"
        return f"possibili piogge {period}"
    return "non sono previste piogge"


def build_morning_forecast_body(
    snapshot: Mapping[str, Any],
    municipality: Municipality,
    locality: FvgLocality | None = None,
    *,
    now: datetime,
) -> str:
    """Build one compact Italian summary from verified hourly ICON data."""

    hourly = snapshot.get("hourly")
    if not isinstance(hourly, Mapping):
        return ""
    required = (
        "time",
        "temperature_2m",
        "precipitation",
        "rain",
        "showers",
        "weather_code",
    )
    series = {name: hourly.get(name) for name in required}
    if any(not isinstance(values, list) for values in series.values()):
        return ""
    lengths = {len(values) for values in series.values()}
    if len(lengths) != 1 or not lengths or next(iter(lengths)) < 1:
        return ""

    current_local = now.astimezone(FVG_ZONE)
    rows: list[dict[str, Any]] = []
    for index, value in enumerate(series["time"]):
        forecast_at = _forecast_time(value)
        temperature = _finite_number(series["temperature_2m"][index])
        precipitation = _finite_number(series["precipitation"][index])
        rain = _finite_number(series["rain"][index])
        showers = _finite_number(series["showers"][index])
        weather_code = _finite_number(series["weather_code"][index])
        if (
            forecast_at is None
            or temperature is None
            or precipitation is None
            or rain is None
            or showers is None
            or weather_code is None
            or forecast_at.date() != current_local.date()
            or forecast_at < current_local - timedelta(hours=1)
        ):
            continue
        rows.append(
            {
                "time": forecast_at,
                "temperature": temperature,
                "precipitation": max(0.0, precipitation),
                "rain": max(0.0, rain),
                "showers": max(0.0, showers),
                "weather_code": int(weather_code),
            }
        )
    if not rows:
        return ""

    place = locality.name if locality is not None else municipality.name
    current_temperature = round(rows[0]["temperature"])
    maximum_temperature = round(max(row["temperature"] for row in rows))
    condition = _condition_phrase(int(rows[0]["weather_code"]))
    precipitation = _precipitation_phrase(rows)
    return (
        f"{place}: {condition}, {current_temperature} °C. "
        f"Massima {maximum_temperature} °C; {precipitation}."
    )


def _read_mode() -> str:
    mode = os.getenv(MORNING_FORECAST_MODE_ENV, "off").strip().lower() or "off"
    if mode not in {"off", "dry_run", "send"}:
        raise MorningForecastConfigurationError("morning_forecast_mode_invalid")
    return mode


def _read_require_single_target() -> bool:
    value = os.getenv(
        MORNING_FORECAST_REQUIRE_SINGLE_TARGET_ENV,
        "false",
    ).strip().lower()
    if value not in {"true", "false"}:
        raise MorningForecastConfigurationError(
            "morning_forecast_single_target_invalid"
        )
    return value == "true"


def _read_test_run_id(*, require_single_target: bool) -> str:
    value = os.getenv(MORNING_FORECAST_TEST_RUN_ID_ENV, "").strip().lower()
    if not value:
        return ""
    if not require_single_target:
        raise MorningForecastConfigurationError(
            "morning_forecast_test_run_requires_single_target"
        )
    if re.fullmatch(r"[a-z0-9][a-z0-9._-]{0,63}", value) is None:
        raise MorningForecastConfigurationError(
            "morning_forecast_test_run_id_invalid"
        )
    return value


def _read_test_platform(*, require_single_target: bool) -> str:
    value = os.getenv(MORNING_FORECAST_TEST_PLATFORM_ENV, "").strip().lower()
    if not value:
        return ""
    if not require_single_target:
        raise MorningForecastConfigurationError(
            "morning_forecast_test_platform_requires_single_target"
        )
    if value not in {"android", "web"}:
        raise MorningForecastConfigurationError(
            "morning_forecast_test_platform_invalid"
        )
    return value


class MorningForecastDeliveryService:
    configuration_error_type = MorningForecastConfigurationError
    error_prefix = "morning_forecast"
    forecast_kind = MORNING_FORECAST_KIND
    signature_namespace = "meteofriul-morning-forecast-v1"
    notification_title = MORNING_FORECAST_TITLE
    notification_ttl_seconds = MORNING_FORECAST_TTL_SECONDS
    collapse_key = "mf-morning-forecast"
    notification_tag = "mf-morning-forecast"
    invalid_target_is_retirement = False

    def __init__(
        self,
        *,
        device_repository: PushDeviceRepository | Any,
        source: RoutedIconLocalNoticeSource | Any,
        sender: FirebaseCloudMessagingSender | Any,
        config: LocalNoticeDeliveryConfig,
        require_single_target: bool = False,
        test_run_id: str = "",
        test_platform: str = "",
        test_installation_hash: str = "",
        location_catalog: NoticeMunicipalityCatalog | None = None,
        now: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    ) -> None:
        self._device_repository = device_repository
        self._source = source
        self._sender = sender
        self._config = config
        self._require_single_target = require_single_target
        self._test_run_id = test_run_id.strip().lower()
        self._test_platform = test_platform.strip().lower()
        self._test_installation_hash = test_installation_hash.strip().lower()
        if self._test_run_id and not self._require_single_target:
            raise self.configuration_error_type(
                f"{self.error_prefix}_test_run_requires_single_target"
            )
        if self._test_run_id and re.fullmatch(
            r"[a-z0-9][a-z0-9._-]{0,63}",
            self._test_run_id,
        ) is None:
            raise self.configuration_error_type(
                f"{self.error_prefix}_test_run_id_invalid"
            )
        if self._test_platform and not self._require_single_target:
            raise self.configuration_error_type(
                f"{self.error_prefix}_test_platform_requires_single_target"
            )
        if self._test_platform and self._test_platform not in {"android", "web"}:
            raise self.configuration_error_type(
                f"{self.error_prefix}_test_platform_invalid"
            )
        if self._test_installation_hash and not self._require_single_target:
            raise self.configuration_error_type(
                f"{self.error_prefix}_test_installation_hash_requires_single_target"
            )
        if self._test_installation_hash and re.fullmatch(
            r"[a-f0-9]{64}",
            self._test_installation_hash,
        ) is None:
            raise self.configuration_error_type(
                f"{self.error_prefix}_test_installation_hash_invalid"
            )
        self._now = now
        self._target_resolver = LocalNoticeDeliveryService(
            device_repository=device_repository,
            audit_repository=None,
            source=source,
            sender=sender,
            config=config,
            location_catalog=location_catalog or NoticeMunicipalityCatalog(),
        )

    def _current_time(self) -> datetime:
        current = self._now()
        if current.tzinfo is None:
            current = current.replace(tzinfo=timezone.utc)
        return current.astimezone(timezone.utc)

    def _forecast_date(self, current: datetime) -> date:
        return current.astimezone(FVG_ZONE).date()

    def _delivery_signature(self, forecast_date: date) -> str:
        value = f"{self.signature_namespace}:{forecast_date.isoformat()}"
        if self._test_run_id:
            value = f"{value}:test:{self._test_run_id}"
        return hashlib.sha256(value.encode("utf-8")).hexdigest()

    def _notification_contents(
        self,
        snapshot: Mapping[str, Any],
        municipality: Municipality,
        locality: FvgLocality | None,
        *,
        now: datetime,
    ) -> Mapping[str, ForecastNotificationContent]:
        body = build_morning_forecast_body(
            snapshot,
            municipality,
            locality,
            now=now,
        )
        if not body:
            return {}
        content = ForecastNotificationContent(
            title=self.notification_title,
            body=body,
        )
        return {"it": content, "fur": content}

    @staticmethod
    def _content_for_target(
        contents: Mapping[str, ForecastNotificationContent],
        target: LocalNoticeDeliveryTarget,
    ) -> ForecastNotificationContent | None:
        language = str(target.device.get("language") or "it").strip().lower()
        return contents.get(language) or contents.get("it")

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

    def _claim(
        self,
        target: LocalNoticeDeliveryTarget,
        *,
        signature: str,
        now: datetime,
    ) -> Any:
        return self._device_repository.claim_local_notice_delivery(
            device_id=str(target.device.get("device_id") or ""),
            notice_signature=signature,
            notice_kind=self.forecast_kind,
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
            max_location_age_seconds=MORNING_SAVED_LOCATION_MAX_AGE_SECONDS,
            allow_saved_municipality_without_mode=True,
            now=now,
        )

    @staticmethod
    def _unclaimed_status(state: str) -> str:
        if state == "sent":
            return "deduplicated"
        if state in {"delivery_in_progress", "sending"}:
            return "in_progress"
        if state in {"configuration_retry_scheduled", "retry_scheduled"}:
            return "retry_scheduled"
        if state in {"device_inactive", "weather_notices_disabled"}:
            return "opted_out"
        if state in {
            "app_check_app_changed",
            "app_version_changed",
            "device_location_changed",
            "device_location_evidence_changed",
            "device_target_changed",
            "enrollment_generation_changed",
            "schema_version_changed",
        }:
            return "security_failed"
        return "device_failed"

    def _deliver_group(
        self,
        targets: list[LocalNoticeDeliveryTarget],
        *,
        contents: Mapping[str, ForecastNotificationContent],
        local_date: date,
    ) -> tuple[list[str], int]:
        statuses = ["device_failed"] * len(targets)
        pending: list[tuple[int, LocalNoticeDeliveryTarget, Any, dict[str, str]]] = []
        messages: list[FcmOfficialAlertMessage] = []
        signature = self._delivery_signature(local_date)

        for index, target in enumerate(targets):
            content = self._content_for_target(contents, target)
            if content is None:
                statuses[index] = "device_failed"
                continue
            claim_time = self._current_time()
            try:
                claim = self._claim(target, signature=signature, now=claim_time)
            except PushRepositoryUnavailable:
                statuses[index] = "storage_unavailable"
                continue
            if not claim.claimed:
                statuses[index] = self._unclaimed_status(str(claim.state or ""))
                continue

            expectations = {
                "expected_claim_id": claim.claim_id,
                "expected_target_kind": target.target_kind,
                "expected_target_hash": target.target_hash,
            }
            pending.append((index, target, claim, expectations))
            messages.append(
                FcmOfficialAlertMessage(
                    title=content.title,
                    body=content.body,
                    data={
                        "type": "local_weather_notice",
                        "kind": self.forecast_kind,
                        "tab": "bulletin",
                        "municipality_istat": target.municipality.istat_code,
                        "locality_id": (
                            target.locality.id if target.locality is not None else ""
                        ),
                        "forecast_date": local_date.isoformat(),
                    },
                    ttl_seconds=self.notification_ttl_seconds,
                    target_kind=target.target_kind,
                    target_value=target.target_value,
                    platform=str(target.device.get("platform") or ""),
                    channel_id=DEFAULT_ANDROID_LOCAL_NOTICE_CHANNEL,
                    collapse_key=self.collapse_key,
                    notification_tag=self.notification_tag,
                    web_link=f"{DEFAULT_WEB_APP_URL}/?tab=bulletin",
                )
            )

        if not messages:
            return statuses, 0
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
            pending,
            outcomes,
            strict=True,
        ):
            finish_time = self._current_time()
            try:
                if outcome.success:
                    confirmed = self._device_repository.finish_local_notice_delivery(
                        delivery_id=claim.delivery_id,
                        state="sent",
                        now=finish_time,
                        message_id=outcome.message_id,
                        **expectations,
                    )
                    statuses[index] = "sent" if confirmed else "sent_unconfirmed"
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
                    statuses[index] = "device_failed_unconfirmed"
                    continue
                if outcome.error_code == "fcm_token_invalid":
                    disabled = self._device_repository.disable_device(
                        device_id=str(target.device.get("device_id") or ""),
                        expected_target_kind=target.target_kind,
                        expected_target_hash=target.target_hash,
                        reason="fcm_token_invalid",
                        now=finish_time,
                    )
                    if self.invalid_target_is_retirement:
                        statuses[index] = (
                            "retired_target" if disabled else "device_failed_unconfirmed"
                        )
                        continue
                statuses[index] = "device_failed"
            except PushRepositoryUnavailable:
                statuses[index] = (
                    "sent_unconfirmed" if outcome.success else "device_failed_unconfirmed"
                )
        return statuses, 1

    def run(self) -> MorningForecastDeliveryResult:
        if self._config.mode == "off":
            return MorningForecastDeliveryResult(status="disabled")
        try:
            enrollment_generation = (
                self._config.enrollment_generation
                if self._config.enrollment_mode == "play_beta"
                else None
            )
            read_method = getattr(self._device_repository, "read_active_devices", None)
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
                f"{self.error_prefix}_device_state_unavailable"
            ) from error

        current = self._current_time()
        targets = self._target_resolver.eligible_targets(
            devices,
            now=current,
            require_fresh_location=False,
            allow_saved_municipality_without_mode=True,
        )
        if self._test_platform:
            targets = [
                target
                for target in targets
                if str(target.device.get("platform") or "")
                == self._test_platform
            ]
        if self._test_installation_hash:
            targets = [
                target
                for target in targets
                if str(target.device.get("device_id") or "").strip().lower()
                == self._test_installation_hash
            ]
        if not targets:
            return MorningForecastDeliveryResult(
                status="no_eligible_device",
                pages_processed=pages_processed,
            )

        duplicate_targets = security_failed = failed = 0
        failed_group_keys: set[tuple[str, str]] = set()
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

        if self._require_single_target and (
            len(collapsed_targets) != 1 or duplicate_targets or failed
        ):
            return MorningForecastDeliveryResult(
                status="target_count_invalid",
                eligible_devices=len(targets),
                failed=1,
                groups=len({target.group_key for target in collapsed_targets}),
                failed_groups=len({target.group_key for target in collapsed_targets}),
                duplicate_targets=duplicate_targets,
                security_failed=security_failed,
                pages_processed=pages_processed,
            )

        grouped: dict[tuple[str, str], list[LocalNoticeDeliveryTarget]] = {}
        for target in collapsed_targets:
            grouped.setdefault(target.group_key, []).append(target)

        evaluated = attempted = sent = sent_unconfirmed = deduplicated = 0
        in_progress = retry_scheduled = opted_out = retired_targets = 0
        device_failed = storage_failed = source_failed = delivery_batches = 0
        successful_group = False
        local_date = self._forecast_date(current)

        for group_key in sorted(grouped):
            group_targets = grouped[group_key]
            primary = group_targets[0]
            try:
                snapshot = self._source.fetch(
                    primary.municipality,
                    primary.locality,
                )
            except LocalNoticeSourceUnavailable:
                source_failed += 1
                failed += 1
                failed_group_keys.add(group_key)
                continue
            contents = self._notification_contents(
                snapshot,
                primary.municipality,
                primary.locality,
                now=current,
            )
            evaluated += len(group_targets)
            if not contents:
                source_failed += 1
                failed += 1
                failed_group_keys.add(group_key)
                continue
            attempted += len(group_targets)
            if self._config.mode == "dry_run":
                successful_group = True
                continue

            statuses, batch_count = self._deliver_group(
                group_targets,
                contents=contents,
                local_date=local_date,
            )
            delivery_batches += batch_count
            for status in statuses:
                if status == "sent":
                    sent += 1
                    successful_group = True
                elif status == "sent_unconfirmed":
                    sent_unconfirmed += 1
                    storage_failed += 1
                    failed += 1
                    failed_group_keys.add(group_key)
                elif status == "deduplicated":
                    deduplicated += 1
                    successful_group = True
                elif status == "in_progress":
                    in_progress += 1
                    successful_group = True
                elif status == "retry_scheduled":
                    retry_scheduled += 1
                    successful_group = True
                elif status == "opted_out":
                    opted_out += 1
                    successful_group = True
                elif status == "retired_target":
                    retired_targets += 1
                    successful_group = True
                elif status == "security_failed":
                    security_failed += 1
                    failed += 1
                    failed_group_keys.add(group_key)
                elif status == "storage_unavailable":
                    storage_failed += 1
                    failed += 1
                    failed_group_keys.add(group_key)
                else:
                    device_failed += 1
                    failed += 1
                    failed_group_keys.add(group_key)

        if failed:
            status = "partial" if successful_group else "failed"
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
        elif retired_targets:
            status = "retired_targets"
        else:
            status = "no_forecast"

        return MorningForecastDeliveryResult(
            status=status,
            eligible_devices=len(targets),
            evaluated=evaluated,
            attempted=attempted,
            sent=sent,
            sent_unconfirmed=sent_unconfirmed,
            deduplicated=deduplicated,
            failed=failed,
            groups=len(grouped),
            failed_groups=len(failed_group_keys),
            in_progress=in_progress,
            retry_scheduled=retry_scheduled,
            opted_out=opted_out,
            retired_targets=retired_targets,
            duplicate_targets=duplicate_targets,
            security_failed=security_failed,
            device_failed=device_failed,
            storage_failed=storage_failed,
            source_failed=source_failed,
            pages_processed=pages_processed,
            delivery_batches=delivery_batches,
        )


@lru_cache(maxsize=1)
def get_morning_forecast_delivery_service() -> MorningForecastDeliveryService:
    mode = _read_mode()
    require_single_target = _read_require_single_target()
    try:
        base_config = LocalNoticeDeliveryConfig.from_environment()
    except LocalNoticeDeliveryConfigurationError as error:
        raise MorningForecastConfigurationError(
            "morning_forecast_base_config_invalid"
        ) from error
    if mode != "off" and base_config.mode == "off":
        raise MorningForecastConfigurationError(
            "morning_forecast_base_delivery_mode_required"
        )
    config = replace(base_config, mode=mode)
    return MorningForecastDeliveryService(
        device_repository=PushDeviceRepository(get_firestore_client),
        source=RoutedIconLocalNoticeSource(
            timeout_seconds=config.source_timeout_seconds,
            forecast_hours=MORNING_FORECAST_HOURS,
        ),
        sender=FirebaseCloudMessagingSender(),
        config=config,
        require_single_target=require_single_target,
        test_run_id=_read_test_run_id(
            require_single_target=require_single_target,
        ),
        test_platform=_read_test_platform(
            require_single_target=require_single_target,
        ),
        location_catalog=NoticeMunicipalityCatalog(),
    )


def reset_morning_forecast_delivery_service_for_tests() -> None:
    get_morning_forecast_delivery_service.cache_clear()


__all__ = [
    "ForecastNotificationContent",
    "MORNING_FORECAST_HOURS",
    "MORNING_FORECAST_KIND",
    "MORNING_FORECAST_MODE_ENV",
    "MORNING_FORECAST_REQUIRE_SINGLE_TARGET_ENV",
    "MORNING_FORECAST_TEST_RUN_ID_ENV",
    "MORNING_FORECAST_TEST_PLATFORM_ENV",
    "MorningForecastConfigurationError",
    "MorningForecastDeliveryResult",
    "MorningForecastDeliveryService",
    "build_morning_forecast_body",
    "get_morning_forecast_delivery_service",
    "reset_morning_forecast_delivery_service_for_tests",
]
