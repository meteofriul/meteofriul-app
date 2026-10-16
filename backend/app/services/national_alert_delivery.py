"""Opt-in national DPC notifications, isolated from the FVG dispatcher.

The service is off by default. It reads only a persistent, verified national
snapshot and exact manually selected Android Play municipalities. The separate
outbox is the only write path in send mode; dry-run never claims or sends.
"""

from __future__ import annotations

import hashlib
import json
import os
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Any, Callable

from app.infrastructure.firebase import get_firestore_client
from app.push.fcm import (
    DEFAULT_ANDROID_NATIONAL_ALERT_CHANNEL,
    FcmBatchOutcome,
    FcmConfigurationError,
    FcmOfficialAlertMessage,
    FcmSenderUnavailable,
    FirebaseCloudMessagingSender,
)
from app.repositories.national_alert_delivery import NationalAlertOutboxRepository
from app.repositories.national_official_alerts import (
    NationalOfficialAlertSnapshotRepository,
)
from app.repositories.push import PushDeviceRepository
from app.services.national_alert_push_dry_run import (
    NationalAlertCandidate,
    NationalAlertDryRunPolicy,
    select_national_alert_candidates,
)
from app.services.official_alert_zone_catalog import ALERT_ZONE_CATALOG_ZONE_COUNT
from app.services.push import PushPilotConfig
from app.services.push_version_policy import parse_min_play_version_code


NATIONAL_ALERT_DELIVERY_MODE_ENV = "NATIONAL_OFFICIAL_ALERTS_PUSH_MODE"
NATIONAL_ALERT_MIN_VERSION_ENV = "NATIONAL_OFFICIAL_ALERTS_MIN_VERSION_CODE"
NATIONAL_ALERT_SEND_GATE_ENV = "NATIONAL_OFFICIAL_ALERTS_SEND_GATE"
NATIONAL_ALERT_SEND_CAP_ENV = "NATIONAL_OFFICIAL_ALERTS_SEND_MAX_DEVICES"
NATIONAL_ALERT_MIN_VERSION_FLOOR = 300030
NATIONAL_ALERT_MAX_TTL_SECONDS = 6 * 60 * 60
_LEVEL_RANK = {"yellow": 1, "orange": 2, "red": 3}
_COPY = {
    "it": {
        "levels": {"yellow": "gialla", "orange": "arancione", "red": "rossa"},
        "risks": {
            "hydraulic": "rischio idraulico",
            "hydrogeological": "rischio idrogeologico",
            "thunderstorm": "temporali",
        },
        "body": "Allerta {level} DPC per {risks} in una zona che comprende {city}. Bollettino del {day}.",
    },
    "fur": {
        "levels": {"yellow": "zale", "orange": "naranç", "red": "rosse"},
        "risks": {
            "hydraulic": "risi idraulic",
            "hydrogeological": "risi idrogjologic",
            "thunderstorm": "temporâi",
        },
        "body": "Alerte {level} DPC par {risks} intune zone che e cjape dentri {city}. Boletin dai {day}.",
    },
}


class NationalAlertDeliveryUnavailable(RuntimeError):
    """The national sender cannot safely classify or deliver this run."""


@dataclass(frozen=True, slots=True)
class NationalAlertDeliveryConfig:
    mode: str = "off"
    policy: NationalAlertDryRunPolicy | None = None
    page_size: int = 0
    send_max_devices: int = 0

    @classmethod
    def from_environment(cls) -> "NationalAlertDeliveryConfig":
        mode = os.getenv(NATIONAL_ALERT_DELIVERY_MODE_ENV, "off").strip().lower()
        if mode not in {"off", "dry_run", "send"}:
            raise NationalAlertDeliveryUnavailable("national_alert_mode_invalid")
        if mode == "off":
            return cls()

        base = PushPilotConfig.from_environment()
        if base.enrollment_mode != "play_beta":
            raise NationalAlertDeliveryUnavailable("national_alert_play_beta_required")
        try:
            minimum = parse_min_play_version_code(
                os.getenv(NATIONAL_ALERT_MIN_VERSION_ENV, "")
            )
        except ValueError as error:
            raise NationalAlertDeliveryUnavailable(
                "national_alert_min_version_invalid"
            ) from error
        if (
            minimum is None
            or minimum < NATIONAL_ALERT_MIN_VERSION_FLOOR
            or (
                base.min_app_version_code is not None
                and minimum < base.min_app_version_code
            )
        ):
            raise NationalAlertDeliveryUnavailable(
                "national_alert_min_version_invalid"
            )

        cap = 0
        if mode == "send":
            if os.getenv(NATIONAL_ALERT_SEND_GATE_ENV, "").strip() != "confirmed":
                raise NationalAlertDeliveryUnavailable("national_alert_send_gate_closed")
            raw_cap = os.getenv(NATIONAL_ALERT_SEND_CAP_ENV, "").strip()
            if not raw_cap.isdecimal():
                raise NationalAlertDeliveryUnavailable("national_alert_send_cap_invalid")
            cap = int(raw_cap)
            if not 1 <= cap <= 5000:
                raise NationalAlertDeliveryUnavailable("national_alert_send_cap_invalid")

        return cls(
            mode=mode,
            policy=NationalAlertDryRunPolicy(
                enrollment_generation=base.enrollment_generation,
                android_app_ids=base.android_app_ids,
                min_app_version_code=minimum,
            ),
            page_size=base.max_devices,
            send_max_devices=cap,
        )


@dataclass(frozen=True, slots=True)
class PreparedNationalAlert:
    signature: str
    forecast_day: str
    level: str
    body_it: str
    body_fur: str
    valid_to: datetime


def prepare_national_alerts(
    candidate: NationalAlertCandidate,
) -> tuple[PreparedNationalAlert, ...]:
    """At most one alert per forecast day, stable across source revisions."""

    by_day: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in candidate.active_records:
        day = str(record.get("forecast_day") or "")
        if record.get("level") not in _LEVEL_RANK:
            raise NationalAlertDeliveryUnavailable("national_alert_record_invalid")
        try:
            date.fromisoformat(day)
        except ValueError as error:
            raise NationalAlertDeliveryUnavailable(
                "national_alert_forecast_day_invalid"
            ) from error
        by_day[day].append(record)

    prepared = []
    for day, records in sorted(by_day.items()):
        level = max((record["level"] for record in records), key=_LEVEL_RANK.get)
        highest = [record for record in records if record["level"] == level]
        try:
            valid_to = min(
                datetime.fromisoformat(str(record["valid_to"]).replace("Z", "+00:00"))
                for record in highest
            )
        except (KeyError, ValueError) as error:
            raise NationalAlertDeliveryUnavailable(
                "national_alert_validity_invalid"
            ) from error
        if valid_to.tzinfo is None:
            raise NationalAlertDeliveryUnavailable("national_alert_validity_invalid")
        stable_records = sorted({
            (str(record["zone_id"]), str(record["risk"]), str(record["level"]))
            for record in records
        })
        signature = hashlib.sha256(json.dumps({
            "contract": "national-official-alert-notification-v1",
            "municipality_istat": candidate.municipality_istat,
            "forecast_day": day,
            "records": stable_records,
        }, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
        display_day = date.fromisoformat(day).strftime("%d/%m/%Y")
        risks = sorted({str(record["risk"]) for record in highest})
        bodies = {}
        for language, copy in _COPY.items():
            if any(risk not in copy["risks"] for risk in risks):
                raise NationalAlertDeliveryUnavailable("national_alert_risk_invalid")
            bodies[language] = copy["body"].format(
                level=copy["levels"][level],
                risks=" e ".join(copy["risks"][risk] for risk in risks),
                city=candidate.municipality_name,
                day=display_day,
            )
        prepared.append(PreparedNationalAlert(
            signature=signature,
            forecast_day=day,
            level=level,
            body_it=bodies["it"],
            body_fur=bodies["fur"],
            valid_to=valid_to.astimezone(timezone.utc),
        ))
    return tuple(prepared)


class NationalAlertDeliveryService:
    def __init__(
        self,
        *,
        snapshot_repository: NationalOfficialAlertSnapshotRepository,
        device_repository: PushDeviceRepository,
        outbox_repository: NationalAlertOutboxRepository,
        sender: FirebaseCloudMessagingSender,
        config: NationalAlertDeliveryConfig,
        now: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
        expected_zone_count: int = ALERT_ZONE_CATALOG_ZONE_COUNT,
    ) -> None:
        self._snapshot_repository = snapshot_repository
        self._device_repository = device_repository
        self._outbox_repository = outbox_repository
        self._sender = sender
        self._config = config
        self._now = now
        self._expected_zone_count = expected_zone_count

    def run(self) -> dict[str, Any]:
        if self._config.mode == "off":
            return {"status": "disabled", "sent": 0, "outbox_writes": 0}
        if self._config.policy is None or self._config.page_size < 1:
            raise NationalAlertDeliveryUnavailable("national_alert_policy_missing")

        current = self._now()
        snapshot, storage = self._snapshot_repository.load()
        devices = self._device_repository.read_active_devices(
            max_devices=self._config.page_size,
            enrollment_generation=self._config.policy.enrollment_generation,
        )
        selection = select_national_alert_candidates(
            snapshot,
            devices.devices,
            storage=storage,
            policy=self._config.policy,
            now=current,
            expected_zone_count=self._expected_zone_count,
        )
        base = {
            "source_revision": selection.source_revision,
            "devices_seen": selection.devices_seen,
            "eligible_manual_devices": selection.eligible_manual_devices,
            "candidate_devices": len(selection.candidates),
            "candidate_records": selection.candidate_records,
            "excluded": selection.exclusions,
            "pages_processed": devices.pages_processed,
            "sent": 0,
            "outbox_writes": 0,
        }
        if self._config.mode == "dry_run":
            return {**base, "status": "dry_run", "candidate_status": (
                "candidate" if selection.candidates else "no_candidate"
            )}
        if len(selection.candidates) > self._config.send_max_devices:
            raise NationalAlertDeliveryUnavailable(
                "national_alert_audience_cap_exceeded"
            )

        prepared = [
            (candidate, alert)
            for candidate in selection.candidates
            for alert in prepare_national_alerts(candidate)
        ]
        counts = {
            "attempted": 0,
            "sent": 0,
            "sent_unconfirmed": 0,
            "deduplicated": 0,
            "failed": 0,
            "in_progress": 0,
            "opted_out": 0,
            "expired": 0,
            "delivery_batches": 0,
            "outbox_writes": 0,
        }
        for offset in range(0, len(prepared), 500):
            pending = []
            messages = []
            for candidate, alert in prepared[offset:offset + 500]:
                now = self._now()
                remaining = int((alert.valid_to - now).total_seconds())
                if remaining <= 60:
                    counts["expired"] += 1
                    continue
                counts["attempted"] += 1
                device = candidate.device
                claim = self._outbox_repository.claim(
                    device_id=str(device["device_id"]),
                    alert_signature=alert.signature,
                    forecast_day=alert.forecast_day,
                    level=alert.level,
                    source_revision=selection.source_revision,
                    target_hash=candidate.target_hash,
                    municipality_istat=candidate.municipality_istat,
                    municipality_name=candidate.municipality_name,
                    enrollment_generation=self._config.policy.enrollment_generation,
                    app_check_app_id=str(device["app_check_app_id"]),
                    app_version=str(device["app_version"]).strip().lower(),
                    min_app_version_code=self._config.policy.min_app_version_code,
                    now=now,
                )
                if not claim.claimed:
                    if claim.state == "sent":
                        counts["deduplicated"] += 1
                    elif claim.state in {"preference_disabled", "device_inactive", "municipality_changed"}:
                        counts["opted_out"] += 1
                    elif claim.state in {"delivery_in_progress", "retry_scheduled"}:
                        counts["in_progress"] += 1
                    else:
                        counts["failed"] += 1
                    continue
                counts["outbox_writes"] += 1
                day_tag = alert.forecast_day.replace("-", "")
                language = "fur" if device.get("language") == "fur" else "it"
                messages.append(FcmOfficialAlertMessage(
                    title="Meteo Friûl",
                    body=alert.body_fur if language == "fur" else alert.body_it,
                    data={
                        "type": "national_official_alert",
                        "tab": "bulletin",
                        "municipality_istat": candidate.municipality_istat,
                    },
                    ttl_seconds=min(NATIONAL_ALERT_MAX_TTL_SECONDS, remaining),
                    target_kind=candidate.target_kind,
                    target_value=candidate.target_value,
                    platform="android",
                    channel_id=DEFAULT_ANDROID_NATIONAL_ALERT_CHANNEL,
                    collapse_key=f"mf-national-{day_tag}",
                    notification_tag=f"mf-national-{day_tag}",
                ))
                pending.append((candidate, claim))

            if not messages:
                continue
            counts["delivery_batches"] += 1
            try:
                outcomes = self._sender.send_batch(messages)
            except FcmConfigurationError:
                outcomes = [FcmBatchOutcome(error_code="fcm_configuration_error") for _ in messages]
            except FcmSenderUnavailable:
                outcomes = [FcmBatchOutcome(error_code="fcm_sender_unavailable") for _ in messages]
            if len(outcomes) != len(messages):
                outcomes = [FcmBatchOutcome(error_code="fcm_sender_unavailable") for _ in messages]

            for (candidate, claim), outcome in zip(pending, outcomes, strict=True):
                state = (
                    "sent" if outcome.success else
                    "failed_invalid_token" if outcome.error_code == "fcm_token_invalid" else
                    "failed_configuration" if outcome.error_code == "fcm_configuration_error" else
                    "failed_transient"
                )
                confirmed = self._outbox_repository.finish(
                    delivery_id=claim.delivery_id,
                    claim_id=claim.claim_id,
                    target_hash=candidate.target_hash,
                    state=state,
                    now=self._now(),
                    message_id=outcome.message_id,
                    error_code=outcome.error_code,
                )
                if outcome.success:
                    if confirmed:
                        counts["sent"] += 1
                    else:
                        counts["sent_unconfirmed"] += 1
                        counts["failed"] += 1
                else:
                    counts["failed"] += 1
                    if outcome.error_code == "fcm_token_invalid" and confirmed:
                        self._device_repository.disable_device(
                            device_id=str(candidate.device["device_id"]),
                            expected_target_kind=candidate.target_kind,
                            expected_target_hash=candidate.target_hash,
                            reason="fcm_token_invalid",
                            now=self._now(),
                        )

        if counts["failed"]:
            status = "partial" if counts["sent"] or counts["deduplicated"] else "failed"
        elif counts["sent"]:
            status = "sent"
        elif counts["deduplicated"]:
            status = "deduplicated"
        elif counts["in_progress"]:
            status = "in_progress"
        else:
            status = "no_candidate"
        return {**base, **counts, "status": status}


def get_national_alert_delivery_service() -> NationalAlertDeliveryService:
    return NationalAlertDeliveryService(
        snapshot_repository=NationalOfficialAlertSnapshotRepository(
            firestore_provider=get_firestore_client,
        ),
        device_repository=PushDeviceRepository(get_firestore_client),
        outbox_repository=NationalAlertOutboxRepository(get_firestore_client),
        sender=FirebaseCloudMessagingSender(),
        config=NationalAlertDeliveryConfig.from_environment(),
    )
