"""National Community rules used exclusively by the standalone local pilot.

Atomic pilot transactions cover rolling quotas, corrections, replacement
lineages and retry receipts. Raw GPS samples are never put into storage.
"""

from __future__ import annotations

import hashlib
import json
import math
import secrets
import time
from copy import deepcopy
from datetime import datetime, timezone
from typing import Any, Callable, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.contracts.live import (
    CommunityReportCreate, CommunityReportPublic, CommunityReportGroup,
    CommunityLocation, CommunityReportDelete,
)
from app.repositories.pilot_community import (
    PilotMemoryCommunityRepository,
    PilotObservationExpired,
    PilotObservationGroupHidden,
    PilotObservationIdempotencyConflict,
    PilotObservationLocationChanged,
    PilotObservationNotUpdateable,
    PilotObservationOwnerMismatch,
    PilotObservationRevisionConflict,
    PilotObservationSourceBlocked,
    PilotObservationUnavailable,
)
from app.services.community import (
    CONFIRM_GLOBAL_WINDOW_LIMIT, CONFIRM_GLOBAL_WINDOW_SECONDS,
    CONFIRM_MAX_VOTERS_PER_GROUP,
    REPORT_GLOBAL_WINDOW_LIMIT, REPORT_GLOBAL_WINDOW_SECONDS,
    REPORT_MAX_DISTANCE_KM, REPORT_TTL_SECONDS, REPORT_TYPES,
    REPUTATION_DAILY_AWARD_LIMIT,
    CommunityService, CommunityServiceError,
)
from app.services.location import haversine_km, normalize_text
from app.services.pilot_community_geography import (
    PilotCommunityGeographyCatalog, get_default_pilot_community_geography_catalog,
)

PILOT_MINIMUM_INTERVAL = 120
PILOT_CORRECTION_SECONDS = 300
PILOT_HOURLY_LIMIT = 4
PILOT_DAILY_LIMIT = 12
PILOT_OPERATION_RETENTION_SECONDS = 48 * 3600


class PilotOperation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    client_id: str = Field(default="", max_length=128)


class PilotCommunityReportCreate(CommunityReportCreate):
    istat_code: str | None = Field(default=None, pattern=r"^\d{6}$")
    accuracy_m: float | None = Field(default=None, gt=0, allow_inf_nan=False)
    age_ms: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    operation_id: str = Field(min_length=16, max_length=128, pattern=r"^[A-Za-z0-9._:-]+$")
    replacement_token: str | None = Field(default=None, min_length=24, max_length=128)


class PilotCommunityReportCorrection(PilotCommunityReportCreate):
    expected_revision: int = Field(ge=1, le=1_000_000)


class PilotCommunityResolve(BaseModel):
    model_config = ConfigDict(extra="forbid")
    lat: float = Field(ge=-90, le=90, allow_inf_nan=False)
    lon: float = Field(ge=-180, le=180, allow_inf_nan=False)
    accuracy_m: float | None = Field(default=None, gt=0, allow_inf_nan=False)
    age_ms: float | None = Field(default=None, ge=0, allow_inf_nan=False)


class PilotCommunityReportDelete(CommunityReportDelete):
    # Owner commands always identify the operation and the revision they saw.
    action: Literal["withdraw", "replace"] = "withdraw"
    operation_id: str = Field(min_length=16, max_length=128, pattern=r"^[A-Za-z0-9._:-]+$")
    expected_revision: int = Field(ge=1, le=1_000_000)


class PilotCommunityObservationUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    client_id: str = Field(default="", max_length=128)
    operation_id: str = Field(
        min_length=16, max_length=128,
        pattern=r"^[A-Za-z0-9._:-]+$",
    )
    expected_revision: int = Field(ge=1, le=1_000_000)
    lat: float = Field(ge=-90, le=90, allow_inf_nan=False)
    lon: float = Field(ge=-180, le=180, allow_inf_nan=False)
    accuracy_m: float = Field(gt=0, allow_inf_nan=False)
    age_ms: float = Field(ge=0, allow_inf_nan=False)
    accepted_terms: bool = Field(default=False, strict=True)
    policy_version: str = Field(default="", max_length=64)


class PilotCommunityService(CommunityService):
    def __init__(
        self, *, geography: PilotCommunityGeographyCatalog | None = None,
        now: Callable[[], float] = time.time,
        report_id_factory: Callable[[], str] | None = None,
        repository: PilotMemoryCommunityRepository | None = None,
    ) -> None:
        if repository is not None and not isinstance(repository, PilotMemoryCommunityRepository):
            raise TypeError("pilot_repository_required")
        # Only a pilot repository is accepted. Ambient production credentials
        # and storage environment variables cannot enable cloud I/O.
        super().__init__(
            repository=repository if repository is not None else PilotMemoryCommunityRepository(), now=now,
            report_id_factory=report_id_factory,
        )
        self.pilot_geography = geography or get_default_pilot_community_geography_catalog()
        self._pilot_contract: dict[str, Any] | None = None

    @staticmethod
    def _require_gps(command: Any) -> None:
        if (
            command.accuracy_m is None or command.age_ms is None
            or not math.isfinite(command.accuracy_m)
            or not math.isfinite(command.age_ms)
            or not 0 < command.accuracy_m <= 500
            or not 0 <= command.age_ms <= 120_000
        ):
            raise CommunityServiceError(400, {
                "code": "community_fresh_gps_required",
                "message": "Rileva nuovamente una posizione GPS precisa per segnalare.",
            })

    def resolve_location(self, command: PilotCommunityResolve) -> dict[str, Any]:
        self._require_gps(command)
        municipality = self.pilot_geography.resolve_municipality(command.lat, command.lon)
        if municipality is None:
            raise CommunityServiceError(403, {
                "code": "community_location_outside_italy",
                "message": "Le segnalazioni sono disponibili solo da una posizione in Italia.",
            })
        nearby = self.pilot_geography.nearby_municipalities(
            command.lat, command.lon, radius_km=REPORT_MAX_DISTANCE_KM, limit=8,
        )
        # A municipality's public point can be farther away than 5 km inside
        # large municipalities: containment is sufficient for the detected one.
        choices = [municipality, *[
            item for item in nearby
            if item.istat_code != municipality.istat_code
            and item.region_iso == municipality.region_iso
        ]]
        return {
            "ok": True, "detectedPlace": municipality.name,
            "selectedPlace": municipality.name, "istatCode": municipality.istat_code,
            "regionId": municipality.region_iso, "provinceCode": municipality.province,
            "nearbyPlaces": [self._location_payload(item) for item in choices],
        }

    def _resolve_report_municipality(self, command: PilotCommunityReportCreate):
        self._require_gps(command)
        detected = self.pilot_geography.resolve_municipality(command.lat, command.lon)
        if detected is None:
            raise CommunityServiceError(403, {
                "code": "community_location_outside_italy",
                "message": "Le segnalazioni sono disponibili solo da una posizione in Italia.",
            })
        selected = detected
        if command.istat_code:
            selected = self.pilot_geography.match_istat(command.istat_code)
        elif command.selected_place and normalize_text(command.selected_place) != normalize_text(detected.name):
            selected = self.pilot_geography.match_name(command.selected_place)
        if selected is None:
            raise CommunityServiceError(400, "Comune selezionato non valido o ambiguo.")
        if command.selected_place and normalize_text(command.selected_place) != normalize_text(selected.name):
            raise CommunityServiceError(400, "Comune e codice ISTAT non corrispondono.")
        if selected.istat_code != detected.istat_code and (
            selected.region_iso != detected.region_iso
            or haversine_km(command.lat, command.lon, selected.latitude, selected.longitude)
            > REPORT_MAX_DISTANCE_KM
        ):
            raise CommunityServiceError(400, "Puoi correggere solo verso un Comune vicino alla posizione GPS.")
        return selected

    def _check_rate(self, key: str, limit: int, window: int) -> None:
        now = self.now()
        start, count = self.repository._pilot_requests.get(key, (now, 0))
        if now >= start + window:
            start, count = now, 0
        if count >= limit:
            raise CommunityServiceError(429, {
                "code": "community_local_rate_limit",
                "message": "Troppe operazioni in questo momento. Riprova tra poco.",
                "retry_after_seconds": max(1, math.ceil(start + window - now)),
            })
        self.repository._pilot_requests[key] = (start, count + 1)

    def _charge_request(self, kind: str) -> None:
        # This transaction commits separately, including when a business rule
        # subsequently rejects the command. No successful-operation quota is used.
        with self.repository.transaction():
            self.repository._prune_memory(self.now())
            self._check_rate(kind, REPORT_GLOBAL_WINDOW_LIMIT, REPORT_GLOBAL_WINDOW_SECONDS)

    @staticmethod
    def _fingerprint(action: str, report_id: str, command: BaseModel) -> str:
        data = command.model_dump(mode="json", exclude={
            "client_id", "operation_id", "lat", "lon", "accuracy_m", "age_ms",
            "accepted_terms", "policy_version",
        })
        return hashlib.sha256(json.dumps([action, report_id, data], sort_keys=True).encode()).hexdigest()

    def _replay(self, owner_key: str, operation_id: str, fingerprint: str):
        receipt = self.repository._pilot_operations.get(f"{owner_key}:{operation_id}")
        if receipt is None:
            return None
        if receipt["fingerprint"] != fingerprint:
            raise CommunityServiceError(409, {"code": "community_idempotency_conflict", "message": "L’operazione non corrisponde alla richiesta originale."})
        result = deepcopy(receipt["result"])
        result["idempotent_replay"] = True
        return result

    def _receipt(self, owner_key: str, operation_id: str, fingerprint: str, result: dict, now: float):
        self.repository._pilot_operations[f"{owner_key}:{operation_id}"] = {
            "fingerprint": fingerprint, "result": deepcopy(result),
            "expires_at": now + PILOT_OPERATION_RETENTION_SECONDS,
        }

    def operation_status(self, operation_id: str, command: PilotOperation):
        self._require_client_id(command.client_id)
        owner_key = self._client_key("community-report", command.client_id)
        self._charge_request("operation-read")
        with self.repository.transaction():
            receipt = self.repository._pilot_operations.get(f"{owner_key}:{operation_id}")
            return {"status": "accepted", "result": deepcopy(receipt["result"])} if receipt else {"status": "not_found"}

    def _require_source_allowed(self, owner_key: str, now: float):
        block = self.repository.get_source_block(owner_key, now)
        blocked_until = float((block or {}).get("blocked_until") or 0)
        if blocked_until > now:
            raise CommunityServiceError(403, {"code": "community_source_temporarily_blocked", "message": "Questa installazione non può inviare osservazioni al momento.", "blocked_until": int(blocked_until * 1000)})

    def _require_unique(self, owner_key, code, type_id, now, excluding=None):
        self.repository._prune_memory(now)
        for report in self.repository._reports.values():
            if report["id"] != excluding and report["owner_key"] == owner_key and report["istat_code"] == code and report["type_id"] == type_id:
                raise CommunityServiceError(409, {
                    "code": "community_observation_already_recent",
                    "message": f"Hai già segnalato questo fenomeno a {report['place']}.",
                    "state": self._server_observation_state(report, now=now),
                })

    def _creation_budget(self, owner_key, now, *, bypass_interval=False):
        recent = [value for value in self.repository._pilot_creations.get(owner_key, []) if value > now - 86400]
        hourly = [value for value in recent if value > now - 3600]
        for values, maximum, seconds, code, message in [
            (recent, PILOT_DAILY_LIMIT, 86400, "community_daily_limit", "Hai raggiunto il limite delle ultime 24 ore."),
            (hourly, PILOT_HOURLY_LIMIT, 3600, "community_hourly_limit", "Hai raggiunto il limite degli ultimi 60 minuti."),
        ]:
            if len(values) >= maximum:
                raise CommunityServiceError(429, {"code": code, "message": message, "retry_after_seconds": max(1, math.ceil(values[-maximum] + seconds - now))})
        if recent and not bypass_interval and now < recent[-1] + PILOT_MINIMUM_INTERVAL:
            raise CommunityServiceError(429, {"code": "community_minimum_interval", "message": "Attendi prima di inviare una nuova osservazione.", "retry_after_seconds": max(1, math.ceil(recent[-1] + PILOT_MINIMUM_INTERVAL - now))})
        return recent

    def _owner_metadata(self, report):
        lineage = str(report.get("lineage_id") or report["id"])
        replacement_available = not self.repository._pilot_lineages.get(lineage, False)
        try:
            self._require_editable(report, self.now())
        except CommunityServiceError:
            replacement_available = False
        return {
            "correction_until": int((float(report["created_at"]) + PILOT_CORRECTION_SECONDS) * 1000),
            "replacement_available": replacement_available,
        }

    def _stored_payload(self, report):
        payload = self.public_payload(self._public_report(report, self.now()), updated_at=report.get("updated_at", report["created_at"]), revision=report.get("revision", 1))
        metadata = self._owner_metadata(report)
        payload.update({"correctionUntil": metadata["correction_until"], "replacementAvailable": metadata["replacement_available"], "lineageGroupIds": list(report.get("protection_group_ids", []))})
        return payload

    def create_report(self, command: PilotCommunityReportCreate, *, client_host: str):
        del client_host
        self._require_client_id(command.client_id)
        owner_key = self._client_key("community-report", command.client_id)
        fingerprint = self._fingerprint("create", "", command)
        self._charge_request("create")
        with self.repository.transaction():
            replay = self._replay(owner_key, command.operation_id, fingerprint)
            if replay:
                return replay
            self._require_current_community_terms(command)
            type_id = command.type_id.strip().lower()
            if type_id not in REPORT_TYPES:
                raise CommunityServiceError(400, "Tipo segnalazione non valido.")
            selected = self._resolve_report_municipality(command)
            now = self.now()
            self._require_source_allowed(owner_key, now)
            self._require_unique(owner_key, selected.istat_code, type_id, now)
            grant = None
            if command.replacement_token:
                grant = self.repository._pilot_replacements.get(command.replacement_token)
                if not grant or grant["owner_key"] != owner_key or grant["used"] or grant["expires_at"] <= now:
                    raise CommunityServiceError(409, {"code": "community_replacement_unavailable", "message": "La sostituzione senza attesa non è disponibile. Avvia un nuovo invio ordinario."})
                self._require_editable(grant["source_report"], now, allow_withdrawn=True)
            recent = self._creation_budget(owner_key, now, bypass_interval=grant is not None)
            report = self._build_report(type_id=type_id, municipality=selected, owner_key=owner_key, identity=command.identity, now=now)
            report.update({"lineage_id": grant["lineage_id"] if grant else report["id"], "protection_group_ids": []})
            confirmation = self.repository.get_confirmation(report["group_id"])
            if self.repository.get_group_moderation(report["group_id"], now).get("hidden"):
                raise CommunityServiceError(409, {"code": "community_group_hidden", "message": "Questa osservazione è nascosta dalla moderazione."})
            if grant:
                report["protection_group_ids"] = list(dict.fromkeys([*grant["source_report"].get("protection_group_ids", []), grant["source_report"]["group_id"]]))
                confirmation = self._merge_protections(grant["source_report"], report, confirmation, now)
            else:
                members, _ = self.repository.list_group_reports(report["group_id"], now)
                confirmation = self.repository.apply_group_reputation_memory(report["group_id"], reports=[*members, report], confirmation_state=confirmation, report_added=True, award_day=self._reputation_award_day(now), daily_limit=REPUTATION_DAILY_AWARD_LIMIT, now=now)
            self._apply_confirmation(report, confirmation)
            storage = self.repository.save_report(report)
            self.repository.protect_lineage_award(report, now)
            members, _ = self.repository.list_group_reports(report["group_id"], now)
            if confirmation.get("votes") or confirmation.get("validity_status") == "verified" or grant:
                self.repository.save_confirmation(report["group_id"], confirmation, max(float(item["expires_at"]) for item in members))
            self.repository.materialize_confirmation_counts([item["id"] for item in members], yes=report["confirmation_yes"], no=report["confirmation_no"], map_withdrawn=report["map_withdrawn"], validity_status=report["validity_status"], temporal_status=report["temporal_status"])
            self.repository._pilot_creations[owner_key] = [*recent, now]
            self.repository.set_cooldown(owner_key, now + PILOT_MINIMUM_INTERVAL)
            if grant:
                grant["used"] = True
            self.repository._pilot_history.setdefault(report["id"], []).append({"action": "created", "at": now, "report": deepcopy(report)})
            result = {"ok": True, "action": "created", "operation_id": command.operation_id, "report": self._stored_payload(report), "revision": 1, "updated_at": int(now * 1000), "cooldown_until": int((now + PILOT_MINIMUM_INTERVAL) * 1000), "undo_until": 0, "undo_window_seconds": 0, "ttl_seconds": REPORT_TTL_SECONDS, "idempotent_replay": False, **self._owner_metadata(report), "limits": {"minimum_interval_seconds": PILOT_MINIMUM_INTERVAL, "hourly_limit": PILOT_HOURLY_LIMIT, "daily_limit": PILOT_DAILY_LIMIT}, "source": {"id": "community_reports", "type": "informative_unverified", "verified": False, "storage": storage}}
            self._receipt(owner_key, command.operation_id, fingerprint, result, now)
            self._invalidate_reports_cache()
            return result

    def update_observation(
        self,
        report_id: str,
        command: PilotCommunityObservationUpdate,
        *,
        client_host: str,
    ) -> dict[str, Any]:
        del client_host
        self._require_client_id(command.client_id)
        owner_key = self._client_key("community-report", command.client_id)
        fingerprint = self._fingerprint("update", report_id, command)
        self._charge_request("update-request")
        with self.repository.transaction():
            replay = self._replay(owner_key, command.operation_id, fingerprint)
            if replay:
                return replay
        self._require_current_community_terms(command)
        self._require_gps(command)
        detected = self.pilot_geography.resolve_municipality(
            command.lat, command.lon,
        )
        if detected is None:
            raise CommunityServiceError(403, {
                "code": "community_location_outside_italy",
                "message": "Le segnalazioni sono disponibili solo da una posizione in Italia.",
            })
        def location_matches(istat_code: str) -> bool:
            selected = self.pilot_geography.match_istat(istat_code)
            return bool(selected) and selected.istat_code == detected.istat_code
        owner_key = self._client_key("community-report", command.client_id)
        try:
            with self.repository.transaction():
                replay = self._replay(owner_key, command.operation_id, fingerprint)
                if replay:
                    return replay
                current = self.repository._reports.get(report_id)
                if current is not None and current.get("owner_key") == owner_key:
                    self._require_editable(current, self.now())
                result = self.repository.refresh_observation_atomic(
                    report_id,
                    owner_key=owner_key,
                    operation_id=command.operation_id,
                    expected_revision=command.expected_revision,
                    location_matches=location_matches,
                    ttl_seconds=REPORT_TTL_SECONDS,
                    now_factory=self.now,
                )
                updated = result["report"]
                payload = {"ok": True, "action": "updated", "operation_id": command.operation_id, "report": self._stored_payload(updated), "revision": result["revision"], "updated_at": int(result["updated_at"] * 1000), "previous_expires_at": int(result["previous_expires_at"] * 1000), "idempotent_replay": result["idempotent_replay"], **self._owner_metadata(updated), "source": {"id": "community_reports", "type": "informative_unverified", "verified": False, "storage": result["storage"]}}
                self._receipt(owner_key, command.operation_id, fingerprint, payload, self.now())
                self.repository._pilot_history.setdefault(report_id, []).append({"action": "updated", "at": self.now(), "report": deepcopy(updated)})
        except PilotObservationExpired as error:
            raise CommunityServiceError(409, {
                "code": "community_observation_expired",
                "message": "Questa osservazione è scaduta. Per descrivere la situazione attuale, invia una nuova osservazione.",
                "state": self._server_observation_state(error.state),
            }) from error
        except PilotObservationUnavailable as error:
            raise CommunityServiceError(404, {
                "code": "community_observation_not_active",
                "message": "Questa osservazione non è più disponibile.",
            }) from error
        except PilotObservationOwnerMismatch as error:
            raise CommunityServiceError(403, {
                "code": "community_observation_owner_mismatch",
                "message": "Puoi aggiornare solo la tua osservazione.",
            }) from error
        except PilotObservationRevisionConflict as error:
            raise CommunityServiceError(409, {
                "code": "community_observation_revision_conflict",
                "message": "L’osservazione è già stata aggiornata. Ricarica lo stato corrente.",
                "state": self._server_observation_state(error.state),
            }) from error
        except PilotObservationIdempotencyConflict as error:
            raise CommunityServiceError(409, {
                "code": "community_idempotency_conflict",
                "message": "La richiesta di aggiornamento non corrisponde all’operazione originale.",
            }) from error
        except PilotObservationLocationChanged as error:
            raise CommunityServiceError(409, {
                "code": "community_observation_location_changed",
                "message": "La posizione attuale non corrisponde al Comune dell’osservazione. Invia una nuova osservazione.",
            }) from error
        except PilotObservationSourceBlocked as error:
            raise CommunityServiceError(403, {
                "code": "community_source_temporarily_blocked",
                "message": "Questa installazione non può aggiornare osservazioni al momento.",
                "blocked_until": int(error.blocked_until * 1000),
            }) from error
        except PilotObservationGroupHidden as error:
            raise CommunityServiceError(409, {
                "code": "community_group_hidden",
                "message": "Questa osservazione non è aggiornabile.",
            }) from error
        except PilotObservationNotUpdateable as error:
            raise CommunityServiceError(409, {
                "code": "community_observation_not_updateable",
                "message": "Questa osservazione non è più aggiornabile.",
            }) from error

        self._invalidate_reports_cache()
        return payload

    @staticmethod
    def _apply_confirmation(report, confirmation):
        report.update({
            "confirmation_yes": int(confirmation.get("yes", 0)),
            "confirmation_no": int(confirmation.get("no", 0)),
            "denial_count": int(confirmation.get("no", 0)),
            "map_withdrawn": bool(confirmation.get("map_withdrawn", False)) or int(confirmation.get("no", 0)) >= 3,
            "validity_status": confirmation.get("validity_status", "unverified"),
            "temporal_status": confirmation.get("temporal_status", "active"),
        })

    def _merge_protections(self, source, target, confirmation, now):
        state = deepcopy(confirmation)
        votes = dict(state.get("votes") or {})
        groups = list(dict.fromkeys([source["group_id"], *source.get("protection_group_ids", [])]))
        for group_id in groups:
            previous = self.repository.get_confirmation(group_id)
            for voter, value in (previous.get("votes") or {}).items():
                # A denial is never replaced by a yes when histories merge.
                if votes.get(voter) != "no" or value == "no":
                    votes[voter] = value
        state["votes"] = votes
        state["yes"] = max(int(state.get("yes", 0)), sum(value == "yes" for value in votes.values()))
        state["no"] = max(int(state.get("no", 0)), int(source.get("confirmation_no", 0)), sum(value == "no" for value in votes.values()))
        if state["no"] >= 3:
            state["map_withdrawn"] = True
            state["validity_status"] = "rejected"
        return state

    def _require_editable(self, report, now, *, allow_withdrawn=False):
        del allow_withdrawn
        if now >= float(report["expires_at"]):
            raise CommunityServiceError(409, {"code": "community_observation_expired", "message": "Questa osservazione è scaduta. Per descrivere la situazione attuale, invia una nuova osservazione.", "state": self._server_observation_state(report, now=now)})
        self._require_source_allowed(report["owner_key"], now)
        for group_id in dict.fromkeys([report["group_id"], *report.get("protection_group_ids", [])]):
            confirmation = self.repository.get_confirmation(group_id)
            if report.get("moderation_hidden") or self.repository.get_group_moderation(group_id, now).get("hidden"):
                raise CommunityServiceError(409, {"code": "community_group_hidden", "message": "Questa osservazione è nascosta dalla moderazione."})
            if report.get("map_withdrawn") or confirmation.get("map_withdrawn") or confirmation.get("validity_status", report.get("validity_status")) == "rejected" or confirmation.get("temporal_status", report.get("temporal_status")) == "ceased":
                raise CommunityServiceError(409, {"code": "community_observation_not_updateable", "message": "Questa osservazione è stata smentita o conclusa e non può essere modificata o sostituita."})

    def _owned_report(self, report_id, owner_key, expected_revision, now):
        report = self.repository._reports.get(report_id)
        if report is None:
            expired = self.repository._expired_observations.get(report_id)
            if expired and expired["owner_key"] == owner_key:
                raise CommunityServiceError(409, {"code": "community_observation_expired", "message": "Questa osservazione è scaduta. Invia una nuova osservazione.", "state": self._server_observation_state(expired, now=now)})
            raise CommunityServiceError(404, {"code": "community_observation_not_active", "message": "Questa osservazione non è più disponibile."})
        if report["owner_key"] != owner_key:
            raise CommunityServiceError(403, {"code": "community_observation_owner_mismatch", "message": "Puoi gestire solo le tue osservazioni."})
        if int(report.get("revision", 1)) != expected_revision:
            raise CommunityServiceError(409, {"code": "community_observation_revision_conflict", "message": "L’osservazione è stata modificata. Ricarica lo stato corrente.", "state": self._server_observation_state(report, now=now)})
        return deepcopy(report)

    def correct_observation(self, report_id, command: PilotCommunityReportCorrection, *, client_host: str):
        del client_host
        self._require_client_id(command.client_id)
        owner_key = self._client_key("community-report", command.client_id)
        fingerprint = self._fingerprint("correct", report_id, command)
        self._charge_request("correct")
        with self.repository.transaction():
            replay = self._replay(owner_key, command.operation_id, fingerprint)
            if replay:
                return replay
            self._require_current_community_terms(command)
            if command.replacement_token:
                raise CommunityServiceError(400, "Una correzione non può usare una sostituzione.")
            selected = self._resolve_report_municipality(command)
            type_id = command.type_id.strip().lower()
            if type_id not in REPORT_TYPES:
                raise CommunityServiceError(400, "Tipo segnalazione non valido.")
            now = self.now()
            original = self._owned_report(report_id, owner_key, command.expected_revision, now)
            self._require_editable(original, now)
            if now >= original["created_at"] + PILOT_CORRECTION_SECONDS:
                raise CommunityServiceError(409, {"code": "community_correction_window_closed", "message": "I 5 minuti per correggere questa osservazione sono trascorsi."})
            self._require_unique(owner_key, selected.istat_code, type_id, now, excluding=report_id)
            corrected = deepcopy(original)
            corrected.update({"type_id": type_id, "place": selected.name, "istat_code": selected.istat_code, "region_id": selected.region_iso, "province_code": selected.province, "lat": selected.latitude, "lon": selected.longitude, "group_id": self._group_id(type_id, selected.istat_code, original["created_at"]), "corrected_at": now, "revision": int(original.get("revision", 1)) + 1, "protection_group_ids": list(dict.fromkeys([*original.get("protection_group_ids", []), original["group_id"]]))})
            corrected["selected_place"] = selected.name
            corrected["type_category"] = "status" if type_id == "quiet" else "phenomenon"
            corrected["x"], corrected["y"] = self._map_position(selected.latitude, selected.longitude)
            if self.repository.get_group_moderation(corrected["group_id"], now).get("hidden"):
                raise CommunityServiceError(409, {"code": "community_group_hidden", "message": "Questa osservazione è nascosta dalla moderazione."})
            state = self._merge_protections(original, corrected, self.repository.get_confirmation(corrected["group_id"]), now)
            self._apply_confirmation(corrected, state)
            storage = self.repository.save_report(corrected)
            members, _ = self.repository.list_group_reports(corrected["group_id"], now)
            self.repository.save_confirmation(corrected["group_id"], state, max(float(item["expires_at"]) for item in members))
            self.repository.materialize_confirmation_counts([item["id"] for item in members], yes=corrected["confirmation_yes"], no=corrected["confirmation_no"], map_withdrawn=corrected["map_withdrawn"], validity_status=corrected["validity_status"], temporal_status=corrected["temporal_status"])
            self.repository._pilot_history.setdefault(report_id, []).append({"action": "corrected", "at": now, "report": deepcopy(corrected)})
            result = {"ok": True, "action": "corrected", "operation_id": command.operation_id, "report": self._stored_payload(corrected), "revision": corrected["revision"], "updated_at": int(corrected["updated_at"] * 1000), "idempotent_replay": False, **self._owner_metadata(corrected), "source": {"id": "community_reports", "storage": storage}}
            self._receipt(owner_key, command.operation_id, fingerprint, result, now)
            self._invalidate_reports_cache()
            return result

    def delete_report(self, report_id: str, command: PilotCommunityReportDelete, *, client_host: str):
        """Retire the record without erasing quotas, lineage or vote history."""
        del client_host
        self._require_client_id(command.client_id)
        owner_key = self._client_key("community-report", command.client_id)
        fingerprint = self._fingerprint("withdraw", report_id, command)
        self._charge_request("withdraw")
        with self.repository.transaction():
            replay = self._replay(owner_key, command.operation_id, fingerprint)
            if replay:
                return replay
            now = self.now()
            report = self._owned_report(report_id, owner_key, command.expected_revision, now)
            token = None
            if command.action == "replace":
                self._require_editable(report, now)
                lineage = str(report.get("lineage_id") or report_id)
                if self.repository._pilot_lineages.get(lineage, False):
                    raise CommunityServiceError(409, {"code": "community_replacement_unavailable", "message": "La sostituzione senza attesa è già stata utilizzata per questa osservazione."})
                token = secrets.token_urlsafe(32)
                self.repository._pilot_lineages[lineage] = True
                self.repository._pilot_replacements[token] = {"owner_key": owner_key, "lineage_id": lineage, "source_report": deepcopy(report), "used": False, "expires_at": report["expires_at"]}
            elif now >= report["expires_at"]:
                raise CommunityServiceError(409, {"code": "community_observation_expired", "message": "Questa osservazione è già scaduta.", "state": self._server_observation_state(report, now=now)})
            removed_from = self.repository.delete_report(report_id)
            cooldown_until = self.repository.get_cooldown(owner_key, now)
            self.repository._pilot_history.setdefault(report_id, []).append({"action": "replacement_ready" if token else "withdrawn", "at": now, "report": deepcopy(report)})
            self._invalidate_reports_cache()
            result = {"ok": True, "report_id": report_id, "operation_id": command.operation_id, "action": "replacement_ready" if token else "withdrawn", "replacement_token": token, "cooldown_until": int(cooldown_until * 1000) if cooldown_until > now else None, "idempotent_replay": False, "source": {"id": "community_reports", "storage": removed_from}}
            if token:
                result["replacement_expires_at"] = int(report["expires_at"] * 1000)
            self._receipt(owner_key, command.operation_id, fingerprint, result, now)
            return result

    def confirm_report(self, group_id, command, *, client_host: str):
        self._charge_request("confirm-request")
        with self.repository.transaction():
            self._check_rate("confirm", CONFIRM_GLOBAL_WINDOW_LIMIT, CONFIRM_GLOBAL_WINDOW_SECONDS)
            votes = self.repository.get_confirmation(group_id).get("votes", {})
            voter = self._client_key("community-report-confirmation", command.client_id)
            if voter not in votes and len(votes) >= CONFIRM_MAX_VOTERS_PER_GROUP:
                raise CommunityServiceError(429, "Questa segnalazione ha raggiunto il limite di conferme.")
            return super().confirm_report(group_id, command, client_host=client_host)

    def flag_report_group(self, group_id, command, *, client_host: str):
        self._charge_request("flag-request")
        with self.repository.transaction():
            return super().flag_report_group(group_id, command, client_host=client_host)

    def get_reputation(self, command, *, client_host: str):
        with self.repository.transaction():
            return super().get_reputation(command, client_host=client_host)

    def _build_report(self, *, municipality, **kwargs):
        report = super()._build_report(municipality=municipality, **kwargs)
        report.update({
            "istat_code": municipality.istat_code,
            "region_id": municipality.region_iso,
            "province_code": municipality.province,
            "group_id": self._group_id(report["type_id"], municipality.istat_code, report["created_at"]),
        })
        return report

    def _public_report(self, report: dict[str, Any], now: float) -> CommunityReportPublic:
        municipality = self.pilot_geography.match_istat(report.get("istat_code", ""))
        if municipality is None:
            raise ValueError("noncanonical_pilot_community_municipality")
        lat, lon = municipality.latitude, municipality.longitude
        x, y = self._map_position(lat, lon)
        type_id = str(report["type_id"])
        return CommunityReportPublic(
            id=report["id"], typeId=type_id,
            typeCategory="status" if type_id == "quiet" else "phenomenon",
            groupId=report["group_id"], place=municipality.name,
            lat=lat, lon=lon, locationPrecision="zone", x=x, y=y,
            createdAt=int(report["created_at"] * 1000),
            expiresAt=int(report["expires_at"] * 1000), time="", source="community",
            sourceKey=self._public_source_key(report), identity=self._public_identity(report),
        )

    def public_payload(
        self, public: Any, *, updated_at: float | None = None,
        revision: int | None = None,
    ) -> dict[str, Any]:
        payload = public.model_dump(mode="json", exclude_none=True)
        # Group id carries canonical identity and avoids requiring any raw GPS
        # or mutable name-based index during serialisation of groups.
        code = payload["groupId"].split(":")[1]
        municipality = self.pilot_geography.match_istat(code)
        payload.update({
            "istatCode": code, "regionId": municipality.region_iso,
            "provinceCode": municipality.province,
        })
        if updated_at is not None:
            payload["updatedAt"] = int(float(updated_at) * 1000)
        if revision is not None:
            payload["revision"] = max(1, int(revision))
        return payload

    def _publishable_stored_report_expiry(self, report: dict[str, Any], now: float):
        if (
            report.get("type_id") not in REPORT_TYPES or not report.get("owner_key")
            or self.pilot_geography.match_istat(report.get("istat_code", "")) is None
        ):
            return None
        try:
            created = float(report["created_at"])
            updated = float(report.get("updated_at") or created)
            expiry = float(report["expires_at"])
        except (KeyError, TypeError, ValueError, OverflowError):
            return None
        if not all(map(math.isfinite, (created, updated, expiry))):
            return None
        return expiry if (
            created <= updated <= now < expiry
            and math.isclose(
                expiry - updated, REPORT_TTL_SECONDS,
                rel_tol=0.0, abs_tol=1e-6,
            )
        ) else None

    @staticmethod
    def _server_observation_state(
        report: dict[str, Any], *, now: float | None = None,
    ) -> dict[str, Any]:
        server_time = float(
            report.get("server_time")
            if now is None
            else now
        )
        return {
            "report_id": str(report.get("id") or report.get("report_id") or ""),
            "status": str(report.get("status") or (
                "expired"
                if float(report.get("expires_at") or 0) <= server_time
                else "recent"
            )),
            "expires_at": int(float(report.get("expires_at") or 0) * 1000),
            "server_time": int(server_time * 1000),
            "revision": max(1, int(report.get("revision") or 1)),
        }

    @staticmethod
    def _location_payload(municipality) -> dict[str, Any]:
        return {
            "place": municipality.name, "istatCode": municipality.istat_code,
            "regionId": municipality.region_iso, "provinceCode": municipality.province,
            "lat": municipality.latitude, "lon": municipality.longitude,
        }

    def get_scoped_reports(
        self, *, istat_code: str | None = None, lat: float | None = None,
        lon: float | None = None, radius_km: float = 30,
    ) -> dict[str, Any]:
        if not math.isfinite(radius_km) or not 1 <= radius_km <= 100:
            raise CommunityServiceError(400, "Raggio geografico non valido.")
        if istat_code:
            if lat is not None or lon is not None:
                raise CommunityServiceError(400, "Usa un Comune oppure le coordinate per delimitare la mappa.")
            municipality = self.pilot_geography.match_istat(istat_code)
            if municipality is None:
                raise CommunityServiceError(400, "Comune non valido.")
            lat, lon = municipality.latitude, municipality.longitude
        elif lat is not None and lon is not None and math.isfinite(lat) and math.isfinite(lon):
            municipality = self.pilot_geography.resolve_municipality(lat, lon)
            if municipality is None:
                raise CommunityServiceError(403, "Localita fuori Italia.")
        else:
            raise CommunityServiceError(400, "Seleziona una localita italiana per leggere le segnalazioni.")
        now = self.now()
        with self.repository.transaction():
            stored, storage = self.repository.list_scoped_reports(
                now=now, lat=lat, lon=lon, radius_km=radius_km,
            )
            hidden = self.repository.list_hidden_group_ids(now)
            reports, states = [], {}
            report_metadata: dict[str, dict[str, float | int]] = {}
            for item in stored:
                if self._publishable_stored_report_expiry(item, now) is None:
                    continue
                if item.get("moderation_hidden") or item["group_id"] in hidden or any(group_id in hidden for group_id in item.get("protection_group_ids", [])):
                    continue
                public = self._public_report(item, now)
                if haversine_km(lat, lon, public.lat, public.lon) > radius_km:
                    continue
                reports.append(public)
                report_metadata[public.id] = {
                    "updated_at": float(
                        item.get("updated_at") or item.get("created_at") or now
                    ),
                    "revision": max(1, int(item.get("revision") or 1)),
                    **self._owner_metadata(item),
                    "lineageGroupIds": list(item.get("protection_group_ids", [])),
                }
                inherited = self._merge_protections(item, item, self.repository.get_confirmation(item["group_id"]), now)
                state = states.setdefault(public.groupId, {"yes": 0, "no": 0})
                state["yes"] = max(state["yes"], int(item.get("confirmation_yes", 0)), int(inherited.get("yes", 0)))
                state["no"] = max(state["no"], int(item.get("confirmation_no", 0)), int(inherited.get("no", 0)))
            groups = self._group_reports(reports, states)
        # Location suggestions are scoped too: no all-Italy catalog per poll.
        locations = self.pilot_geography.nearby_municipalities(lat, lon, radius_km=radius_km, limit=16)
        contract = self._get_pilot_contract()
        return {
            "reports": [
                {**self.public_payload(
                    item,
                    updated_at=float(report_metadata[item.id]["updated_at"]),
                    revision=int(report_metadata[item.id]["revision"]),
                ), "correctionUntil": report_metadata[item.id]["correction_until"], "replacementAvailable": report_metadata[item.id]["replacement_available"], "lineageGroupIds": report_metadata[item.id]["lineageGroupIds"]}
                for item in reports
            ],
            "map_groups": [
                {**self.public_payload(
                    item,
                    updated_at=max(
                        float(report_metadata[report_id]["updated_at"])
                        for report_id in item.reportIds
                        if report_id in report_metadata
                    ),
                ), "lineageGroupIds": list(dict.fromkeys(group_id for report_id in item.reportIds for group_id in report_metadata[report_id]["lineageGroupIds"]))}
                for item in groups
            ],
            "ttl_seconds": REPORT_TTL_SECONDS, "cooldown_seconds": PILOT_MINIMUM_INTERVAL,
            "max_distance_km": REPORT_MAX_DISTANCE_KM,
            "locations": [self._location_payload(item) for item in locations],
            "generated_at": datetime.fromtimestamp(now, timezone.utc).isoformat(),
            "source": {"id": "community_reports", "type": "informative_unverified", "verified": False, "storage": storage},
            "scope": {"istatCode": municipality.istat_code, "radiusKm": radius_km},
            "contract": contract,
        }

    def _get_pilot_contract(self) -> dict[str, Any]:
        if self._pilot_contract is not None:
            return self._pilot_contract
        contract = self._safety_contract.model_dump(mode="json")
        municipalities = self.pilot_geography.municipalities
        contract.update({
            "schema_version": "community-pilot-national-safety-v2",
            "minimum_interval_seconds": PILOT_MINIMUM_INTERVAL,
            "cooldown_seconds": PILOT_MINIMUM_INTERVAL,
            "undo_window_seconds": 0,
            "hourly_limit": PILOT_HOURLY_LIMIT, "daily_limit": PILOT_DAILY_LIMIT,
            "quota_windows": "rolling-server-time",
            "correction_window_seconds": PILOT_CORRECTION_SECONDS,
            "uniqueness": "installation-istat-phenomenon",
            "location_catalog_count": len(municipalities),
            "location_catalog_sha256": hashlib.sha256("".join(
                f"{item.istat_code}\t{item.latitude:.5f}\t{item.longitude:.5f}\n"
                for item in municipalities
            ).encode("utf-8")).hexdigest(),
            "location_catalog_digest_algorithm": "sha256-ordered-istat-lat5-lon5-lines-v1",
            "create_fields": list(PilotCommunityReportCreate.model_fields),
            "update_fields": list(PilotCommunityObservationUpdate.model_fields),
            "update_action": "renew_same_observation",
            "update_requires_fresh_gps": True,
            "update_idempotency": "report-operation-revision-v1",
            "public_report_fields": [*CommunityReportPublic.model_fields, "istatCode", "regionId", "provinceCode"],
            "public_group_fields": [*CommunityReportGroup.model_fields, "istatCode", "regionId", "provinceCode"],
            "location_fields": [*CommunityLocation.model_fields, "istatCode", "regionId", "provinceCode"],
            "pilot_public_report_extension_fields": ["updatedAt", "revision", "correctionUntil", "replacementAvailable", "lineageGroupIds"],
            "pilot_public_group_extension_fields": ["updatedAt", "lineageGroupIds"],
        })
        self._pilot_contract = contract
        return contract

    @staticmethod
    def _group_from_reports(group_id, items, state):
        group = CommunityService._group_from_reports(group_id, items, state)
        return group.model_copy(update={
            "expiresAt": max(item.expiresAt for item in items),
        })
