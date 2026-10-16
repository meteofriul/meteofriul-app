"""Simplified national reporting rules, sharing the existing atomic stores.

The older pilot service remains the reader for legacy snapshots. All new
commands go through this service; UI presentation is not a security boundary.
"""
from copy import deepcopy
import hashlib
import math

from pydantic import Field, model_validator

from app.contracts.live import (
    CommunityReportConfirmationCreate, CommunityReputationRequest,
    CommunityReputationRank, CommunityConfirmationResponse,
    ConfirmationCounts, CommunitySource,
)
from app.repositories.community import (
    REPUTATION_RETENTION_SECONDS, _datetime, _timestamp,
    _reputation_document_id, _reputation_award_document_id,
    _reputation_award_payload, _reputation_summary,
)
from app.services.community import (
    CommunityServiceError, REPORT_TYPES, REPORT_TTL_SECONDS,
    CONFIRM_MAX_VOTERS_PER_GROUP, CONFIRM_GLOBAL_WINDOW_LIMIT,
    CONFIRM_GLOBAL_WINDOW_SECONDS,
)
from app.services.location import haversine_km
from app.services.pilot_community import PilotCommunityService, PilotCommunityResolve

RULES_VERSION = "community-reports-v3"
MINIMUM_INTERVAL = 180
REWARD_INTERVAL = 3 * 3600
HISTORY_WINDOW = 48 * 3600


class CommunityReportVote(CommunityReportConfirmationCreate):
    # Optional at parsing only, so old clients get an actionable business error.
    lat: float | None = Field(default=None, ge=-90, le=90, allow_inf_nan=False)
    lon: float | None = Field(default=None, ge=-180, le=180, allow_inf_nan=False)
    accuracy_m: float | None = Field(default=None, gt=0, allow_inf_nan=False)
    age_ms: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    report_ids: list[str] = Field(default_factory=list, max_length=200)


class CommunityHistoryQuery(CommunityReputationRequest):
    grouped: bool = False
    istat_code: str | None = Field(default=None, pattern=r"^\d{6}$")
    lat: float | None = Field(default=None, ge=-90, le=90, allow_inf_nan=False)
    lon: float | None = Field(default=None, ge=-180, le=180, allow_inf_nan=False)
    radius_km: float = Field(default=30, ge=1, le=100, allow_inf_nan=False)
    offset: int = Field(default=0, ge=0, le=100_000)
    before_created_at: int | None = Field(default=None, ge=0)
    before_id: str | None = Field(default=None, min_length=1, max_length=200)

    @model_validator(mode="after")
    def validate_cursor(self):
        if (self.before_created_at is None) != (self.before_id is None):
            raise ValueError("Both history cursor fields are required")
        if self.before_id is not None and self.offset:
            raise ValueError("Use a cursor or an offset, not both")
        return self


class CommunityReportsService(PilotCommunityService):
    def _creation_budget(self, owner_key, now, *, bypass_interval=False):
        # Keep the existing rolling 4/hour and 12/day quotas. No bypass tokens.
        recent = super()._creation_budget(owner_key, now, bypass_interval=True)
        if recent and now < recent[-1] + MINIMUM_INTERVAL:
            raise CommunityServiceError(429, {
                "code": "community_minimum_interval",
                "message": "Attendi 3 minuti tra due invii.",
                "retry_after_seconds": math.ceil(recent[-1] + MINIMUM_INTERVAL - now),
            })
        return recent

    def _owner_metadata(self, report):
        return {"correction_until": 0, "replacement_available": False}

    def _merge_protections(self, source, target, confirmation, now):
        # Never import votes from a previous observation or a different type.
        return confirmation

    def _get_pilot_contract(self):
        return {**super()._get_pilot_contract(),
                "schema_version": RULES_VERSION,
                "minimum_interval_seconds": MINIMUM_INTERVAL,
                "cooldown_seconds": MINIMUM_INTERVAL,
                "correction_window_seconds": 0, "update_fields": [],
                "update_action": "new_observation_only",
                "uniqueness": "installation", "history_seconds": HISTORY_WINDOW,
                "max_daily_awards": None, "reward_interval_seconds": REWARD_INTERVAL,
                "confirmation_requires_fresh_gps": True,
                "confirmation_requires_report_ids": True}

    def get_scoped_reports(self, **kwargs):
        result = super().get_scoped_reports(**kwargs)
        result["cooldown_seconds"] = MINIMUM_INTERVAL
        return result

    @staticmethod
    def _retired_action(*args, **kwargs):
        raise CommunityServiceError(409, {
            "code": "community_new_observation_required",
            "message": "Invia una nuova osservazione con Segnala: sostituirà automaticamente la precedente.",
        })

    update_observation = _retired_action
    correct_observation = _retired_action
    delete_report = _retired_action

    def operation_status(self, operation_id, command):
        return {**super().operation_status(operation_id, command), "rules_version": RULES_VERSION}

    def _archive(self, report, status, now):
        self.repository._pilot_history.setdefault(report["id"], []).append({
            "action": status, "at": now, "report": deepcopy(report),
        })
        self.repository.delete_report(report["id"])

    @staticmethod
    def _reward_key(report):
        identity = f"{report['owner_key']}:{report['type_id']}:{report['istat_code']}"
        return "episode:" + hashlib.sha256(identity.encode()).hexdigest()

    def _last_reward_deadline(self, report, now):
        key = self._reward_key(report)
        deadline = self.repository._pilot_award_cooldowns.get(key, 0)
        # Respect points earned before the cutover too, when the old retained
        # observations can map their private award ledger to type/municipality.
        candidates = list(self.repository._reports.values()) + [
            event["report"] for events in self.repository._pilot_history.values()
            for event in events if event.get("report")
        ]
        for item in candidates:
            if (item.get("rules_version") == RULES_VERSION
                    or any(item.get(field) != report.get(field)
                           for field in ("owner_key", "type_id", "istat_code"))):
                continue
            award = self.repository._reputation_awards.get(
                _reputation_award_document_id(item["group_id"], report["owner_key"]), {})
            if award.get("status") in {"awarded", "revoked"}:
                deadline = max(deadline, _timestamp(award.get("created_at_timestamp"), 0) + REWARD_INTERVAL)
        return deadline

    def _validate(self, report, now, reason):
        owner = report["owner_key"]
        # Per-observation ledger: validations count even during the reward wait.
        award_id = _reputation_award_document_id("observation:" + report["id"], owner)
        award = self.repository._reputation_awards.get(award_id)
        legacy = self.repository._reputation_awards.get(
            _reputation_award_document_id(report["group_id"], owner))
        if report.get("rules_version") != RULES_VERSION and legacy:
            report["validated"] = legacy.get("status") != "revoked"
            return  # Never recount old validations or reaward an old report.
        if award and award.get("status") == "revoked":
            return
        reputation_id = _reputation_document_id(owner)
        stored = self.repository._reputations.get(reputation_id, {})
        if _timestamp(stored.get("expires_at_timestamp"), 0) <= now:
            stored = {}
        day = self._reputation_award_day(now)
        summary = _reputation_summary(stored, owner_key=owner, award_day=day)
        if award is None:
            summary["validated_reports"] += 1
            award = _reputation_award_payload(group_id=report["group_id"], owner_key=owner,
                                             status="validated", reason=reason, award_day=day, now=now)
        if (report["type_id"] != "quiet" and award["status"] != "awarded"
                and now >= self._last_reward_deadline(report, now)):
            summary["points"] += 1
            summary["daily_awards"] += 1  # Metric only; never a cap.
            award.update(status="awarded", points_delta=1, award_day=day,
                         awarded_at_timestamp=_datetime(now))
            self.repository._pilot_award_cooldowns[self._reward_key(report)] = now + REWARD_INTERVAL
        summary.update(updated_at=_datetime(now),
                       expires_at_timestamp=_datetime(now + REPUTATION_RETENTION_SECONDS))
        self.repository._reputations[reputation_id] = summary
        self.repository._reputation_awards[award_id] = award
        report["validated"] = True

    def _sync_group(self, group_id, members, state, now, *, allow_awards):
        owners = {item["owner_key"] for item in members}
        valid = state.get("yes", 0) > 0 or len(owners) >= 2
        ceased = state.get("no", 0) >= 3
        state.update(report_ids=[item["id"] for item in members],
                     validity_status="verified" if valid else "unverified",
                     temporal_status="ceased" if ceased else "active", map_withdrawn=ceased)
        # An hourly group can be reused after every observation has retired.
        # Keep those episodes separate in history, just as their votes are.
        history_episode = members[0].get("history_episode_id", members[0]["id"])
        for item in members:
            if valid and allow_awards and not ceased:
                self._validate(item, now, "independent_report" if len(owners) >= 2 else "confirmation")
            self._apply_confirmation(item, state)
            item.update(history_episode_id=history_episode, history_counts_at=now)
            self.repository.save_report(item)
            # Keep the latest public-history snapshot through expiry/pruning.
            events = self.repository._pilot_history.setdefault(item["id"], [])
            snapshot = {"action": "active", "at": item["created_at"], "report": deepcopy(item)}
            if events and events[-1]["action"] in {"active", "created"}:
                events[-1] = snapshot
            else:
                events.append(snapshot)
        self.repository.save_confirmation(group_id, state, max(item["expires_at"] for item in members))
        return state

    def create_report(self, command, *, client_host):
        self._require_client_id(command.client_id)
        owner = self._client_key("community-report", command.client_id)
        fingerprint = self._fingerprint("create", "", command)
        self._charge_request("create")
        with self.repository.transaction():
            replay = self._replay(owner, command.operation_id, fingerprint)
            if replay:
                return replay
            self._require_current_community_terms(command)
            if command.replacement_token:
                self._retired_action()
            type_id = command.type_id.strip().lower()
            if type_id not in REPORT_TYPES:
                raise CommunityServiceError(400, "Tipo segnalazione non valido.")
            selected = self._resolve_report_municipality(command)
            now = self.now()
            self.repository._prune_memory(now)
            self._require_source_allowed(owner, now)
            recent = self._creation_budget(owner, now)
            report = self._build_report(type_id=type_id, municipality=selected,
                                        owner_key=owner, identity=command.identity, now=now)
            report.update(rules_version=RULES_VERSION, protection_group_ids=[])
            group_id = report["group_id"]
            if self.repository.get_group_moderation(group_id, now).get("hidden"):
                raise CommunityServiceError(409, {"code": "community_group_hidden", "message": "Osservazione nascosta dalla moderazione."})
            replaced = []
            for old in list(self.repository._reports.values()):
                if old.get("owner_key") == owner:
                    replaced.append(old["id"])
                    self._archive(old, "replaced", now)
            members, _ = self.repository.list_group_reports(group_id, now)
            # No active evidence remains: do not resurrect the old group's votes.
            state = self.repository.get_confirmation(group_id) if members else {"yes": 0, "no": 0, "votes": {}}
            self.repository.record_report_submission_memory(owner, award_day=self._reputation_award_day(now), now=now)
            self._sync_group(group_id, [*members, report], state, now, allow_awards=True)
            self.repository._pilot_creations[owner] = [*recent, now]
            self.repository.set_cooldown(owner, now + MINIMUM_INTERVAL)
            result = {"ok": True, "action": "created", "operation_id": command.operation_id,
                      "report": self._stored_payload(report), "replaced_report_ids": replaced,
                      "revision": 1, "updated_at": int(now * 1000),
                      "cooldown_until": int((now + MINIMUM_INTERVAL) * 1000),
                      "undo_until": 0, "undo_window_seconds": 0, "ttl_seconds": REPORT_TTL_SECONDS,
                      "idempotent_replay": False, **self._owner_metadata(report),
                      "limits": {"minimum_interval_seconds": MINIMUM_INTERVAL, "hourly_limit": 4, "daily_limit": 12},
                      "source": {"id": "community_reports", "storage": self.repository.storage_kind}}
            self._receipt(owner, command.operation_id, fingerprint, result, now)
            self._invalidate_reports_cache()
            return result

    def confirm_report(self, group_id, command, *, client_host):
        self._require_current_community_terms(command)
        self._require_client_id(command.client_id)
        self._require_gps(command)
        if command.lat is None or command.lon is None:
            raise CommunityServiceError(400, {"code": "community_fresh_gps_required", "message": "Rileva la posizione per votare."})
        vote = command.vote.lower().strip()
        if vote not in {"yes", "no"}:
            raise CommunityServiceError(400, "Voto non valido.")
        self._charge_request("confirm-request")
        with self.repository.transaction():
            now = self.now()
            self._check_rate("confirm", CONFIRM_GLOBAL_WINDOW_LIMIT, CONFIRM_GLOBAL_WINDOW_SECONDS)
            members = self._confirmation_members(group_id, command, now)
            state = self.repository.get_confirmation(group_id)
            votes = state.setdefault("votes", {})
            voter = self._client_key("community-report-confirmation", command.client_id)
            previous = votes.get(voter)
            if previous is None and len(votes) >= CONFIRM_MAX_VOTERS_PER_GROUP:
                raise CommunityServiceError(429, "Questa segnalazione ha raggiunto il limite di conferme.")
            changed = previous != "no" and previous != vote
            effective = previous if not changed else vote
            if changed:
                if previous:
                    state[previous] = max(0, state.get(previous, 0) - 1)
                state[vote] = state.get(vote, 0) + 1
                votes[voter] = vote
            self._sync_group(group_id, members, state, now, allow_awards=changed and vote == "yes")
            group = self._group_from_reports(group_id, [self._public_report(item, now) for item in members], state)
            if state["map_withdrawn"]:
                for item in members:
                    self._archive(item, "ceased", now)
            self._invalidate_reports_cache()
            return CommunityConfirmationResponse(group_id=group_id, vote=effective,
                confirmations=ConfirmationCounts(yes=state.get("yes", 0), no=state.get("no", 0)),
                group=group, source=CommunitySource(id="community_report_confirmations",
                type="crowd_signal", verified=False, storage=self.repository.storage_kind))

    def _confirmation_members(self, group_id, command, now):
        """Check the observed content and location inside the caller's transaction."""
        if command.lat is None or command.lon is None:
            raise CommunityServiceError(400, {"code": "community_fresh_gps_required", "message": "Rileva la posizione per votare."})
        members, _ = self.repository.list_group_reports(group_id, now)
        members = [item for item in members if not item.get("moderation_hidden")]
        if not members or self.repository.get_group_moderation(group_id, now).get("hidden"):
            raise CommunityServiceError(404, {"code": "community_observation_not_active", "message": "Segnalazione non più attiva."})
        if set(command.report_ids) != {item["id"] for item in members}:
            raise CommunityServiceError(409, {"code": "community_observation_changed", "message": "Le osservazioni sono cambiate. Aggiorna la mappa prima di votare."})
        owner = self._client_key("community-report", command.client_id)
        self._require_source_allowed(owner, now)
        if any(item["owner_key"] == owner for item in members):
            raise CommunityServiceError(403, {"code": "community_self_confirmation_not_allowed", "message": "Non puoi confermare la tua osservazione."})
        resolved = self.resolve_location(PilotCommunityResolve(
            lat=command.lat, lon=command.lon, accuracy_m=command.accuracy_m, age_ms=command.age_ms))
        if members[0]["istat_code"] not in {item["istatCode"] for item in resolved["nearbyPlaces"]}:
            raise CommunityServiceError(403, {"code": "community_vote_location_mismatch", "message": "La posizione non è compatibile con il Comune della segnalazione."})
        return members

    @staticmethod
    def _reputation_rank(points):
        if points >= 15:
            return CommunityReputationRank(id="sentinel", label="Sentinele dal Teritori", min_points=15)
        if points >= 5:
            return CommunityReputationRank(id="lookout", label="Vuaite dal Timp", min_points=5, next_rank_at=15)
        return CommunityReputationRank(id="novice", label="Osservadôr dal Cîl", min_points=0, next_rank_at=5)

    def get_reputation(self, command, *, client_host):
        result = super().get_reputation(command, client_host=client_host)
        return result.model_copy(update={"max_daily_awards": None})

    def get_history(self, command):
        self._require_client_id(command.client_id)
        owner = self._client_key("community-report", command.client_id)
        # Reuse the existing geographic validation; never expose a national feed.
        scope = self.get_scoped_reports(istat_code=command.istat_code, lat=command.lat,
                                        lon=command.lon, radius_km=command.radius_km)["scope"]
        municipality = self.pilot_geography.match_istat(scope["istatCode"])
        lat = command.lat if command.lat is not None else municipality.latitude
        lon = command.lon if command.lon is not None else municipality.longitude
        with self.repository.transaction():
            now = self.now()
            self.repository._prune_memory(now)
            entries = {key: (events[-1]["report"], events[-1]["action"])
                       for key, events in self.repository._pilot_history.items() if events and events[-1].get("report")}
            entries.update({key: (value, "active") for key, value in self.repository._reports.items()})
            hidden = self.repository.list_hidden_group_ids(now)
            items = []
            archive_groups = {}
            for report, status in entries.values():
                if (report["created_at"] <= now - HISTORY_WINDOW
                        or report.get("moderation_hidden") or report["group_id"] in hidden
                        or haversine_km(lat, lon, report["lat"], report["lon"]) > command.radius_km):
                    continue
                if status in {"created", "active", "corrected", "updated"}:
                    status = "expired" if report["expires_at"] <= now else "active"
                elif status in {"withdrawn", "replacement_ready"}:
                    status = "replaced"
                mine = report["owner_key"] == owner
                item = {"id": report["id"], "typeId": report["type_id"], "place": report["place"],
                        "istatCode": report["istat_code"], "createdAt": int(report["created_at"] * 1000),
                        "expiresAt": int(report["expires_at"] * 1000), "status": status, "mine": mine,
                        "count": 1, "confirmations": {
                            "yes": max(0, int(report.get("confirmation_yes", 0))),
                            "no": max(0, int(report.get("confirmation_no", 0))),
                        }}
                if mine:
                    award = self.repository._reputation_awards.get(_reputation_award_document_id("observation:" + report["id"], owner))
                    if award is None and report.get("rules_version") != RULES_VERSION:
                        award = self.repository._reputation_awards.get(_reputation_award_document_id(report["group_id"], owner))
                    item.update(point=bool(award and award.get("status") == "awarded"),
                                validated=bool(award and award.get("status") != "revoked"))
                if command.grouped and status != "active":
                    # Never merge different statuses or legacy records whose
                    # episode cannot be reconstructed with certainty.
                    key = (report.get("history_episode_id", report["id"]),
                           report["group_id"], status)
                    archive_groups.setdefault(key, []).append((item,
                        report.get("history_counts_at", report["created_at"])))
                else:
                    items.append(item)
            for records in archive_groups.values():
                rows = [row for row, _ in records]
                latest = max(rows, key=lambda row: (row["createdAt"], row["id"]))
                # Votes are a group total, not a sum across its observations.
                counts, _ = max(records, key=lambda pair: (pair[1], pair[0]["createdAt"], pair[0]["id"]))
                summary = {**latest, "count": len(rows),
                           "expiresAt": max(row["expiresAt"] for row in rows),
                           "mine": any(row["mine"] for row in rows),
                           "confirmations": counts["confirmations"]}
                summary.pop("point", None)
                summary.pop("validated", None)
                if summary["mine"]:
                    summary.update(point=any(row.get("point") for row in rows),
                                   validated=any(row.get("validated") for row in rows))
                items.append(summary)
            items.sort(key=lambda item: (item["createdAt"], item["id"]), reverse=True)
            if command.before_id is not None:
                items = [item for item in items if (item["createdAt"], item["id"])
                         < (command.before_created_at, command.before_id)]
            end = command.offset + 50
            page = items[command.offset:end]
            cursor = ({"createdAt": page[-1]["createdAt"], "id": page[-1]["id"]}
                      if page and end < len(items) else None)
            return {"reports": page, "next_offset": end if end < len(items) else None,
                    "next_cursor": cursor,
                    "history_seconds": HISTORY_WINDOW, "generated_at": int(now * 1000)}
