from __future__ import annotations

import hashlib
import math
import re
import secrets
import time
from datetime import datetime, timezone
from typing import Any, Callable, get_args

from pydantic import ValidationError

from app.contracts.live import (
    CommunityConfirmationResponse,
    CommunityIdentitySnapshot,
    CommunityLocation,
    CommunityReportCreate,
    CommunityReportCreatedResponse,
    CommunityReportDeletedResponse,
    CommunityReportDelete,
    CommunityReportGroup,
    CommunityReportFlagCreate,
    CommunityReportFlaggedResponse,
    CommunityReputationRank,
    CommunityReputationRequest,
    CommunityReputationResponse,
    CommunityReportPublic,
    CommunityReportsResponse,
    CommunityPublicSourceKeyContract,
    CommunitySafetyContract,
    CommunityReportConfirmationCreate,
    CommunitySource,
    CommunitySourceIdentity,
    ConfirmationCounts,
)
from app.repositories.community import (
    DENIAL_WITHDRAWAL_THRESHOLD,
    MAX_REPORTS,
    REPUTATION_RETENTION_SECONDS,
    CommunityCooldownActive,
    CommunityConfirmationCapacityReached,
    CommunityFlagCapacityReached,
    CommunityGroupHidden,
    CommunityMutationTargetUnavailable,
    CommunityRepository,
    CommunityRepositoryUnavailable,
    CommunitySelfConfirmationNotAllowed,
    CommunitySourceBlocked,
)
from app.services.fvg_geography import (
    FvgGeographyCatalog,
    get_default_fvg_geography_catalog,
)
from app.services.location import LocationCatalog, Municipality, haversine_km, normalize_text
from app.weather.timezone_support import get_fvg_timezone
from app.services.territory_policy import (
    FVG_REGION_ID,
)


REPORT_TTL_SECONDS = 60 * 60
REPORT_COOLDOWN_SECONDS = 45 * 60
REPORT_UNDO_SECONDS = 60
REPORT_MAX_DISTANCE_KM = 5
REPORT_GROUP_WINDOW_SECONDS = REPORT_TTL_SECONDS
COMMUNITY_GUIDELINES_POLICY_VERSION = "community-guidelines-v2"
REPORT_GLOBAL_WINDOW_SECONDS = 60
REPORT_GLOBAL_WINDOW_LIMIT = 20
CONFIRM_GLOBAL_WINDOW_SECONDS = 60
CONFIRM_GLOBAL_WINDOW_LIMIT = 60
CONFIRM_MAX_VOTERS_PER_GROUP = 500
REPUTATION_DAILY_AWARD_LIMIT = 3
FLAG_RETENTION_SECONDS = 24 * 60 * 60
FLAG_GLOBAL_WINDOW_SECONDS = 60
FLAG_GLOBAL_WINDOW_LIMIT = 60
FLAG_CLIENT_WINDOW_SECONDS = 60 * 60
FLAG_CLIENT_WINDOW_LIMIT = 10
FLAG_MAX_FLAGGERS_PER_GROUP = 50
PUBLIC_SOURCE_KEY_BUCKET_SECONDS = 24 * 60 * 60
PUBLIC_FEED_CACHE_SECONDS = 30
GROUP_MUTATION_MAX_REPORTS = MAX_REPORTS
COMMUNITY_SAFETY_SCHEMA_VERSION = "community-ephemeral-safety-v1"
COMMUNITY_LOCATION_PRECISION = "zone"
COMMUNITY_LOCATION_CATALOG_COUNT = 215
COMMUNITY_LOCATION_CATALOG_DIGEST_ALGORITHM = (
    "sha256-ordered-place-lat5-lon5-lines-v1"
)
PUBLIC_SOURCE_KEY_PATTERN = r"^[0-9a-f]{24}$"
PUBLIC_SOURCE_KEY_LENGTH = 24

_FREE_TEXT_FIELD_TOKENS = frozenset({
    "body",
    "caption",
    "comment",
    "description",
    "message",
    "text",
    "title",
})
_MEDIA_FIELD_TOKENS = frozenset({
    "attachment",
    "audio",
    "image",
    "media",
    "photo",
    "url",
    "video",
})
_ACCOUNT_FIELD_TOKENS = frozenset({
    "account",
    "displayname",
    "email",
    "phone",
    "profile",
    "user",
    "username",
})
_PRIVATE_PUBLIC_FIELD_TOKENS = frozenset({
    "account",
    "clientid",
    "deviceid",
    "email",
    "installationid",
    "ownerkey",
    "phone",
    "profile",
    "userid",
    "username",
})

REPORT_TYPES = {
    "rain": "Pioggia",
    "storm": "Temporale",
    "snow": "Neve",
    "hail": "Grandine",
    "fog": "Nebbia",
    "wind": "Vento",
    "ice": "Ghiaccio o gelata",
    "quiet": "Tutto tranquillo",
}

FVG_REPORT_BOUNDS = {
    "lat_min": 45.55,
    "lat_max": 46.65,
    "lon_min": 12.30,
    "lon_max": 14.00,
}


def _legacy_community_region_not_enabled_detail() -> dict[str, object]:
    """Describe the retired FVG-only endpoint without narrowing Community v2."""

    return {
        "code": "community_region_not_enabled",
        "message": "Questo endpoint Community legacy accetta solo localita FVG.",
        "policy_version": "legacy-community-fvg-v1",
        "read_scope": FVG_REGION_ID,
        "write_scope": "legacy_fvg",
        "enabled_regions": [FVG_REGION_ID],
    }

FVG_MAP_BOUNDS = {
    "lat_min": 45.52,
    "lat_max": 46.72,
    "lon_min": 12.24,
    "lon_max": 14.08,
}


class CommunityServiceError(RuntimeError):
    def __init__(self, status_code: int, detail: str | dict[str, Any]) -> None:
        super().__init__(str(detail))
        self.status_code = status_code
        self.detail = detail


class CommunitySafetyContractDrift(RuntimeError):
    """Raised fail-closed when code and the public safety contract diverge."""


def _model_field_names(model: type[Any]) -> tuple[str, ...]:
    return tuple(model.model_fields)


def _field_matches_capability(field_name: str, tokens: frozenset[str]) -> bool:
    compact = re.sub(r"[^a-z0-9]+", "", field_name.lower())
    return any(token in compact for token in tokens)


def _location_catalog_sha256(catalog: LocationCatalog) -> str:
    canonical_lines = "".join(
        f"{municipality.name}\t{municipality.latitude:.5f}\t"
        f"{municipality.longitude:.5f}\n"
        for municipality in catalog.municipalities
    )
    return hashlib.sha256(canonical_lines.encode("utf-8")).hexdigest()


def build_community_safety_contract(
    catalog: LocationCatalog,
) -> CommunitySafetyContract:
    """Derive the public contract from executable models and policy constants."""

    locations = tuple(catalog.municipalities)
    if len(locations) != COMMUNITY_LOCATION_CATALOG_COUNT:
        raise CommunitySafetyContractDrift("location_catalog_count_drift")
    if len({municipality.name for municipality in locations}) != len(locations):
        raise CommunitySafetyContractDrift("location_catalog_name_drift")

    create_fields = _model_field_names(CommunityReportCreate)
    public_report_fields = _model_field_names(CommunityReportPublic)
    public_group_fields = _model_field_names(CommunityReportGroup)
    confirmation_fields = _model_field_names(ConfirmationCounts)
    location_fields = _model_field_names(CommunityLocation)
    source_fields = _model_field_names(CommunitySource)

    if any(
        _field_matches_capability(field_name, _FREE_TEXT_FIELD_TOKENS)
        for field_name in create_fields
    ):
        raise CommunitySafetyContractDrift("free_text_field_drift")
    if any(
        _field_matches_capability(field_name, _MEDIA_FIELD_TOKENS)
        for field_name in create_fields
    ):
        raise CommunitySafetyContractDrift("media_field_drift")
    if any(
        _field_matches_capability(field_name, _ACCOUNT_FIELD_TOKENS)
        for field_name in create_fields
    ):
        raise CommunitySafetyContractDrift("account_field_drift")
    if any(
        _field_matches_capability(field_name, _PRIVATE_PUBLIC_FIELD_TOKENS)
        for field_name in {*public_report_fields, *public_group_fields}
    ):
        raise CommunitySafetyContractDrift("private_public_field_drift")

    flag_reasons = tuple(
        str(reason)
        for reason in get_args(
            CommunityReportFlagCreate.model_fields["reason"].annotation
        )
    )
    if not flag_reasons:
        raise CommunitySafetyContractDrift("flag_reason_contract_missing")

    return CommunitySafetyContract(
        schema_version=COMMUNITY_SAFETY_SCHEMA_VERSION,
        guidelines_policy_version=COMMUNITY_GUIDELINES_POLICY_VERSION,
        allowed_report_types=tuple(sorted(REPORT_TYPES)),
        create_fields=create_fields,
        public_report_fields=public_report_fields,
        public_group_fields=public_group_fields,
        confirmation_fields=confirmation_fields,
        location_fields=location_fields,
        source_fields=source_fields,
        flag_reasons=flag_reasons,
        ttl_seconds=REPORT_TTL_SECONDS,
        cooldown_seconds=REPORT_COOLDOWN_SECONDS,
        max_distance_km=REPORT_MAX_DISTANCE_KM,
        location_catalog_count=len(locations),
        location_catalog_sha256=_location_catalog_sha256(catalog),
        location_catalog_digest_algorithm=(
            COMMUNITY_LOCATION_CATALOG_DIGEST_ALGORITHM
        ),
        location_precision=COMMUNITY_LOCATION_PRECISION,
        accepts_free_text=False,
        accepts_media=False,
        requires_account=False,
        user_flag_visibility="local_only",
        automatic_global_hide=False,
        public_source_key=CommunityPublicSourceKeyContract(
            algorithm="sha256-truncated-lower-hex",
            pattern=PUBLIC_SOURCE_KEY_PATTERN,
            length=PUBLIC_SOURCE_KEY_LENGTH,
            rotation_bucket_seconds=PUBLIC_SOURCE_KEY_BUCKET_SECONDS,
        ),
    )


class CommunityService:
    def __init__(
        self,
        *,
        catalog: LocationCatalog | None = None,
        geography: FvgGeographyCatalog | None = None,
        repository: CommunityRepository | None = None,
        now: Callable[[], float] = time.time,
        report_id_factory: Callable[[], str] | None = None,
    ) -> None:
        self.catalog = catalog or LocationCatalog()
        self.geography = geography or get_default_fvg_geography_catalog()
        self.repository = repository or CommunityRepository()
        self.now = now
        self.report_id_factory = report_id_factory or (
            lambda: f"community-{secrets.token_hex(8)}"
        )
        self._safety_contract = build_community_safety_contract(self.catalog)
        self._reports_cache: tuple[float, CommunityReportsResponse] | None = None

    def get_reports(self) -> CommunityReportsResponse:
        now = self.now()
        try:
            with self.repository.lock:
                if (
                    self._reports_cache is not None
                    and self._reports_cache[0] > now
                ):
                    return self._reports_cache[1].model_copy(deep=True)
                stored_reports, storage = self.repository.list_reports(now)
                hidden_group_ids = self.repository.list_hidden_group_ids(now)
                visible_reports: list[
                    tuple[dict[str, Any], CommunityReportPublic]
                ] = []
                visible_expirations: list[float] = []
                for report in stored_reports:
                    expires_at = self._publishable_stored_report_expiry(
                        report,
                        now,
                    )
                    if expires_at is None:
                        continue
                    public_report = self._public_report(report, now)
                    if (
                        bool(report.get("moderation_hidden", False))
                        or public_report.groupId in hidden_group_ids
                    ):
                        continue
                    visible_reports.append((report, public_report))
                    visible_expirations.append(expires_at)
                confirmation_states: dict[str, dict[str, int]] = {}
                for report, public_report in visible_reports:
                    group_id = public_report.groupId
                    state = confirmation_states.setdefault(
                        group_id,
                        {"yes": 0, "no": 0},
                    )
                    for key in ("yes", "no"):
                        try:
                            count = max(
                                0,
                                int(report.get(f"confirmation_{key}", 0)),
                            )
                        except (TypeError, ValueError):
                            count = 0
                        state[key] = max(state[key], count)
                reports = [public_report for _, public_report in visible_reports]
                groups = self._group_reports(reports, confirmation_states)
                response = CommunityReportsResponse(
                    reports=reports,
                    map_groups=groups,
                    ttl_seconds=REPORT_TTL_SECONDS,
                    cooldown_seconds=REPORT_COOLDOWN_SECONDS,
                    max_distance_km=REPORT_MAX_DISTANCE_KM,
                    locations=[
                        CommunityLocation(
                            place=municipality.name,
                            lat=municipality.latitude,
                            lon=municipality.longitude,
                        )
                        for municipality in self.catalog.municipalities
                    ],
                    generated_at=datetime.fromtimestamp(now, timezone.utc).isoformat(),
                    source=CommunitySource(
                        id="community_reports",
                        type="informative_unverified",
                        verified=False,
                        storage=storage,
                    ),
                    contract=self._safety_contract.model_copy(deep=True),
                )
                cache_deadline = now + PUBLIC_FEED_CACHE_SECONDS
                if visible_expirations:
                    cache_deadline = min(cache_deadline, min(visible_expirations))
                self._reports_cache = (
                    cache_deadline,
                    response.model_copy(deep=True),
                )
        except CommunityRepositoryUnavailable as error:
            raise self._storage_unavailable() from error

        return response

    def get_reputation(
        self,
        command: CommunityReputationRequest,
        *,
        client_host: str,
    ) -> CommunityReputationResponse:
        """Return only the calling installation's pseudonymous ledger totals."""

        del client_host
        self._require_client_id(command.client_id)
        owner_key = self._client_key("community-report", command.client_id)
        try:
            with self.repository.lock:
                summary, storage = self.repository.get_reputation(
                    owner_key,
                    now=self.now(),
                )
        except CommunityRepositoryUnavailable as error:
            raise self._storage_unavailable() from error

        points = max(0, int(summary.get("points", 0)))
        return CommunityReputationResponse(
            points=points,
            total_reports=max(0, int(summary.get("total_reports", 0))),
            validated_reports=max(
                0,
                int(summary.get("validated_reports", 0)),
            ),
            pending_reports=max(0, int(summary.get("pending_reports", 0))),
            rank=self._reputation_rank(points),
            max_daily_awards=REPUTATION_DAILY_AWARD_LIMIT,
            retention_seconds=REPUTATION_RETENTION_SECONDS,
            source=CommunitySource(
                id="community_reputation",
                type="validated_contributions",
                verified=True,
                storage=storage,
            ),
        )

    def create_report(
        self,
        command: CommunityReportCreate,
        *,
        client_host: str,
    ) -> CommunityReportCreatedResponse:
        now = self.now()
        self._require_current_community_terms(command)
        type_id = command.type_id.strip().lower()
        self._require_client_id(command.client_id)
        if type_id not in REPORT_TYPES:
            raise CommunityServiceError(400, "Tipo segnalazione non valido.")
        selected = self._resolve_report_municipality(command)

        return self._create_resolved_report(
            command, type_id=type_id, selected=selected, now=now,
        )

    def _resolve_report_municipality(
        self,
        command: CommunityReportCreate,
    ) -> Municipality:
        """Resolve the default FVG policy before the shared mutation pipeline."""

        report_region_id = (
            FVG_REGION_ID
            if self._is_in_fvg_bounds(command.lat, command.lon)
            and self.geography.resolve_municipality_istat(command.lat, command.lon)
            else None
        )
        if report_region_id != FVG_REGION_ID:
            raise CommunityServiceError(
                403,
                _legacy_community_region_not_enabled_detail(),
            )

        nearest, nearest_distance = self.catalog.nearest(command.lat, command.lon)
        if nearest_distance > REPORT_MAX_DISTANCE_KM:
            raise CommunityServiceError(
                400,
                "Segnalazione consentita solo vicino a una zona supportata.",
            )

        selected = nearest
        selected_distance = nearest_distance
        if command.selected_place:
            selected = self.catalog.match_names(command.selected_place)
            if selected is None:
                raise CommunityServiceError(400, "Localita selezionata non valida.")
            selected_distance = haversine_km(
                command.lat,
                command.lon,
                selected.latitude,
                selected.longitude,
            )
            if selected_distance > REPORT_MAX_DISTANCE_KM:
                raise CommunityServiceError(
                    400,
                    "Puoi correggere solo verso una localita vicina alla posizione GPS.",
                )
        return selected

    def _create_resolved_report(
        self,
        command: CommunityReportCreate,
        *,
        type_id: str,
        selected: Municipality,
        now: float,
    ) -> CommunityReportCreatedResponse:
        client_key = self._client_key("community-report", command.client_id)
        report = self._build_report(
            type_id=type_id,
            municipality=selected,
            owner_key=client_key,
            identity=command.identity,
            now=now,
        )
        cooldown_until = now + REPORT_COOLDOWN_SECONDS
        try:
            with self.repository.lock:
                block = self.repository.get_source_block(client_key, now)
                blocked_until = (
                    float(block.get("blocked_until") or 0)
                    if isinstance(block, dict)
                    else 0
                )
                if blocked_until > now:
                    raise CommunitySourceBlocked(blocked_until)
                if self.repository.requires_firestore:
                    self.repository.create_report_strict(
                        report,
                        client_key=client_key,
                        cooldown_until=cooldown_until,
                        global_limit=REPORT_GLOBAL_WINDOW_LIMIT,
                        global_window_seconds=REPORT_GLOBAL_WINDOW_SECONDS,
                        now=now,
                        reputation_award_day=self._reputation_award_day(now),
                        reputation_daily_limit=REPUTATION_DAILY_AWARD_LIMIT,
                    )
                    stored_in = "firestore"
                    cooldown_storage = "firestore"
                else:
                    moderation = self.repository.get_group_moderation(
                        str(report.get("group_id") or ""),
                        now,
                    )
                    if bool(moderation.get("hidden", False)):
                        raise CommunityGroupHidden("community_group_hidden")
                    active_until = self.repository.get_cooldown(client_key, now)
                    if active_until > now:
                        raise CommunityCooldownActive(active_until)
                    confirmation = self.repository.get_confirmation(
                        str(report.get("group_id") or "")
                    )
                    active_group_reports, _group_storage = (
                        self.repository.list_group_reports(
                            str(report.get("group_id") or ""),
                            now,
                        )
                    )
                    active_group_reports = [
                        stored_report
                        for stored_report in active_group_reports
                        if str(stored_report.get("group_id") or "")
                        == str(report.get("group_id") or "")
                    ]
                    active_group_reports.append(report)
                    self.repository.record_report_submission_memory(
                        client_key,
                        award_day=self._reputation_award_day(now),
                        now=now,
                    )
                    confirmation = self.repository.apply_group_reputation_memory(
                        str(report.get("group_id") or ""),
                        reports=active_group_reports,
                        confirmation_state=confirmation,
                        report_added=True,
                        award_day=self._reputation_award_day(now),
                        daily_limit=REPUTATION_DAILY_AWARD_LIMIT,
                        now=now,
                    )
                    report["confirmation_yes"] = max(
                        0,
                        int(confirmation.get("yes", 0)),
                    )
                    report["confirmation_no"] = max(
                        0,
                        int(confirmation.get("no", 0)),
                    )
                    report["denial_count"] = report["confirmation_no"]
                    report["map_withdrawn"] = bool(
                        confirmation.get("map_withdrawn", False)
                        or report["confirmation_no"]
                            >= DENIAL_WITHDRAWAL_THRESHOLD
                    )
                    report["validity_status"] = str(
                        confirmation.get("validity_status") or "unverified"
                    )
                    report["temporal_status"] = str(
                        confirmation.get("temporal_status") or "active"
                    )
                    stored_in = self.repository.save_report(report)
                    group_expires_at = max(
                        float(item.get("expires_at") or now)
                        for item in active_group_reports
                    )
                    if (
                        dict(confirmation.get("votes") or {})
                        or str(confirmation.get("validity_status") or "")
                        == "verified"
                    ):
                        self.repository.save_confirmation(
                            str(report.get("group_id") or ""),
                            confirmation,
                            group_expires_at,
                        )
                    self.repository.materialize_confirmation_counts(
                        [
                            str(item.get("id") or "")
                            for item in active_group_reports
                            if str(item.get("id") or "")
                        ],
                        yes=int(confirmation.get("yes", 0)),
                        no=int(confirmation.get("no", 0)),
                        map_withdrawn=bool(
                            confirmation.get("map_withdrawn", False)
                        ),
                        validity_status=report["validity_status"],
                        temporal_status=report["temporal_status"],
                    )
                    cooldown_storage = self.repository.set_cooldown(
                        client_key,
                        cooldown_until,
                    )
                self._invalidate_reports_cache()
        except CommunityCooldownActive as error:
            raise CommunityServiceError(429, {
                "message": "Puoi inviare una nuova segnalazione piu tardi.",
                "retry_after_seconds": int(math.ceil(error.cooldown_until - now)),
            }) from error
        except CommunitySourceBlocked as error:
            raise CommunityServiceError(403, {
                "message": "Questa installazione non può inviare nuove segnalazioni al momento.",
                "code": "community_source_temporarily_blocked",
                "blocked_until": int(error.blocked_until * 1000),
            }) from error
        except CommunityGroupHidden as error:
            raise CommunityServiceError(409, {
                "message": "Questa segnalazione è già stata nascosta dalla moderazione.",
                "code": "community_group_hidden",
            }) from error
        except CommunityRepositoryUnavailable as error:
            raise self._storage_unavailable() from error

        return CommunityReportCreatedResponse(
            report=self._public_report(report, now),
            cooldown_until=int(cooldown_until * 1000),
            undo_until=int((now + REPORT_UNDO_SECONDS) * 1000),
            undo_window_seconds=REPORT_UNDO_SECONDS,
            ttl_seconds=REPORT_TTL_SECONDS,
            source=CommunitySource(
                id="community_reports",
                type="informative_unverified",
                verified=False,
                storage=stored_in,
                cooldown_storage=cooldown_storage,
            ),
        )

    def delete_report(
        self,
        report_id: str,
        command: CommunityReportDelete,
        *,
        client_host: str,
    ) -> CommunityReportDeletedResponse:
        now = self.now()
        client_key = self._client_key("community-report", command.client_id)
        try:
            with self.repository.lock:
                report, _storage = self.repository.get_report(report_id, now)
                if report is None:
                    raise CommunityServiceError(404, "Segnalazione non piu attiva.")
                if report.get("owner_key") != client_key:
                    raise CommunityServiceError(403, "Puoi annullare solo la tua segnalazione.")
                if now > float(report.get("created_at") or 0) + REPORT_UNDO_SECONDS:
                    raise CommunityServiceError(
                        409,
                        "Il tempo per annullare la segnalazione e scaduto.",
                    )
                if self.repository.requires_firestore:
                    self.repository.delete_report_and_cooldown_strict(
                        report_id,
                        client_key=client_key,
                    )
                    removed_from = "firestore"
                    cooldown_storage = "firestore"
                else:
                    removed_from = self.repository.delete_report(report_id)
                    cooldown_storage = self.repository.clear_cooldown(client_key)
                self._invalidate_reports_cache()
        except CommunityRepositoryUnavailable as error:
            raise self._storage_unavailable() from error

        return CommunityReportDeletedResponse(
            ok=True,
            report_id=report_id,
            source=CommunitySource(
                id="community_reports",
                storage=removed_from,
                cooldown_storage=cooldown_storage,
            ),
        )

    def confirm_report(
        self,
        group_id: str,
        command: CommunityReportConfirmationCreate,
        *,
        client_host: str,
    ) -> CommunityConfirmationResponse:
        self._require_confirmation_terms_or_legacy(command)
        vote = command.vote.strip().lower()
        if vote not in {"yes", "no"}:
            raise CommunityServiceError(400, "Voto non valido.")
        self._require_client_id(command.client_id)

        client_key = self._client_key(
            "community-report-confirmation",
            command.client_id,
        )
        owner_key = self._client_key("community-report", command.client_id)
        now = self.now()
        try:
            with self.repository.lock:
                stored_reports, _storage = self.repository.list_group_reports(
                    group_id,
                    now,
                )
                self._require_group_mutation_capacity(stored_reports)
                matching_reports = [
                    self._public_report(report, now)
                    for report in stored_reports
                    if str(report.get("group_id") or "") == group_id
                    and not bool(report.get("moderation_hidden", False))
                ]
                if not matching_reports:
                    raise CommunityServiceError(404, "Segnalazione non piu attiva.")
                if any(
                    str(report.get("owner_key") or "") == owner_key
                    for report in stored_reports
                ):
                    raise CommunityServiceError(403, {
                        "message": "Non puoi confermare un contenuto inviato da questa installazione.",
                        "code": "community_self_confirmation_not_allowed",
                    })
                matching_report_ids = [
                    report.id for report in matching_reports if report.id
                ]
                group_expires_at = max(
                    float(report.get("expires_at") or now)
                    for report in stored_reports
                    if str(report.get("group_id") or "") == group_id
                    and not bool(report.get("moderation_hidden", False))
                )

                if self.repository.requires_firestore:
                    state = self.repository.update_confirmation_strict(
                        group_id,
                        report_ids=matching_report_ids,
                        client_key=client_key,
                        vote=vote,
                        expires_at=group_expires_at,
                        global_limit=CONFIRM_GLOBAL_WINDOW_LIMIT,
                        global_window_seconds=CONFIRM_GLOBAL_WINDOW_SECONDS,
                        max_voters=CONFIRM_MAX_VOTERS_PER_GROUP,
                        now=now,
                        voter_owner_key=owner_key,
                        reputation_award_day=self._reputation_award_day(now),
                        reputation_daily_limit=REPUTATION_DAILY_AWARD_LIMIT,
                    )
                    stored_in = "firestore"
                else:
                    state = self.repository.get_confirmation(group_id)
                    state.setdefault("yes", 0)
                    state.setdefault("no", 0)
                    state.setdefault("votes", {})
                    previous_vote = state["votes"].get(client_key)
                    effective_vote = str(previous_vote or vote)
                    if previous_vote != "no" and previous_vote != vote:
                        if previous_vote in {"yes", "no"}:
                            state[previous_vote] = max(
                                0,
                                int(state.get(previous_vote, 0)) - 1,
                            )
                        state[vote] = int(state.get(vote, 0)) + 1
                        state["votes"][client_key] = vote
                        effective_vote = vote
                    if int(state.get("no", 0)) >= DENIAL_WITHDRAWAL_THRESHOLD:
                        state["map_withdrawn"] = True
                        if state.get("map_withdrawn_at") is None:
                            state["map_withdrawn_at"] = datetime.fromtimestamp(
                                now,
                                timezone.utc,
                            )

                    active_matching_stored = [
                        report
                        for report in stored_reports
                        if str(report.get("group_id") or "") == group_id
                        and not bool(report.get("moderation_hidden", False))
                    ]
                    state = self.repository.apply_group_reputation_memory(
                        group_id,
                        reports=active_matching_stored,
                        confirmation_state=state,
                        report_added=False,
                        award_day=self._reputation_award_day(now),
                        daily_limit=REPUTATION_DAILY_AWARD_LIMIT,
                        now=now,
                    )

                    stored_in = self.repository.save_confirmation(
                        group_id,
                        state,
                        group_expires_at,
                    )
                    self.repository.materialize_confirmation_counts(
                        matching_report_ids,
                        yes=int(state.get("yes", 0)),
                        no=int(state.get("no", 0)),
                        map_withdrawn=bool(state.get("map_withdrawn", False)),
                        validity_status=str(
                            state.get("validity_status") or "unverified"
                        ),
                        temporal_status=str(
                            state.get("temporal_status") or "active"
                        ),
                    )
                    state["_effective_vote"] = effective_vote
                group = self._group_from_reports(
                    group_id,
                    matching_reports,
                    state,
                )
                self._invalidate_reports_cache()
        except CommunityCooldownActive as error:
            raise CommunityServiceError(429, {
                "message": "Troppe conferme in questo momento. Riprova più tardi.",
                "retry_after_seconds": int(math.ceil(error.cooldown_until - now)),
            }) from error
        except CommunityConfirmationCapacityReached as error:
            raise CommunityServiceError(429, {
                "message": "Questa segnalazione ha raggiunto il limite di conferme.",
                "code": "community_confirmation_capacity_reached",
            }) from error
        except CommunityMutationTargetUnavailable as error:
            raise CommunityServiceError(
                404,
                "Segnalazione non piu attiva.",
            ) from error
        except CommunitySelfConfirmationNotAllowed as error:
            raise CommunityServiceError(403, {
                "message": "Non puoi confermare un contenuto inviato da questa installazione.",
                "code": "community_self_confirmation_not_allowed",
            }) from error
        except CommunityRepositoryUnavailable as error:
            raise self._storage_unavailable() from error

        return CommunityConfirmationResponse(
            group_id=group_id,
            vote=str(state.get("_effective_vote") or vote),
            confirmations=ConfirmationCounts(
                yes=int(state.get("yes", 0)),
                no=int(state.get("no", 0)),
            ),
            group=group,
            source=CommunitySource(
                id="community_report_confirmations",
                type="crowd_signal",
                verified=False,
                storage=stored_in,
            ),
        )

    def flag_report_group(
        self,
        group_id: str,
        command: CommunityReportFlagCreate,
        *,
        client_host: str,
    ) -> CommunityReportFlaggedResponse:
        reason = command.reason.strip().lower()
        if reason not in {"inaccurate", "duplicate", "misuse"}:
            raise CommunityServiceError(400, "Motivo della segnalazione non valido.")
        self._require_client_id(command.client_id)

        now = self.now()
        owner_key = self._client_key("community-report", command.client_id)
        flagger_key = self._client_key("community-report-flag", command.client_id)
        expires_at = now + FLAG_RETENTION_SECONDS
        try:
            with self.repository.lock:
                stored_reports, _storage = self.repository.list_group_reports(
                    group_id,
                    now,
                )
                self._require_group_mutation_capacity(stored_reports)
                matching_reports = [
                    report
                    for report in stored_reports
                    if self._stored_group_id(report) == group_id
                ]
                if not matching_reports:
                    raise CommunityServiceError(404, "Segnalazione non piu attiva.")
                if any(
                    str(report.get("owner_key") or "") == owner_key
                    for report in matching_reports
                ):
                    raise CommunityServiceError(403, {
                        "message": "Non puoi segnalare un contenuto inviato da questa installazione.",
                        "code": "community_self_flag_not_allowed",
                    })

                report_ids = [
                    str(report.get("id") or "")
                    for report in matching_reports
                    if str(report.get("id") or "")
                ]
                owner_keys = list(dict.fromkeys(
                    str(report.get("owner_key") or "")
                    for report in matching_reports
                    if str(report.get("owner_key") or "")
                ))
                report_sources = {
                    str(report.get("id") or ""): str(report.get("owner_key") or "")
                    for report in matching_reports
                    if str(report.get("id") or "")
                    and str(report.get("owner_key") or "")
                }

                if self.repository.requires_firestore:
                    state = self.repository.flag_group_strict(
                        group_id,
                        report_ids=report_ids,
                        owner_keys=owner_keys,
                        report_sources=report_sources,
                        client_key=flagger_key,
                        reason=reason,
                        expires_at=expires_at,
                        global_limit=FLAG_GLOBAL_WINDOW_LIMIT,
                        global_window_seconds=FLAG_GLOBAL_WINDOW_SECONDS,
                        client_limit=FLAG_CLIENT_WINDOW_LIMIT,
                        client_window_seconds=FLAG_CLIENT_WINDOW_SECONDS,
                        max_flaggers=FLAG_MAX_FLAGGERS_PER_GROUP,
                        now=now,
                    )
                    stored_in = "firestore"
                else:
                    state, stored_in = self.repository.flag_group(
                        group_id,
                        report_ids=report_ids,
                        owner_keys=owner_keys,
                        report_sources=report_sources,
                        client_key=flagger_key,
                        reason=reason,
                        expires_at=expires_at,
                        global_limit=FLAG_GLOBAL_WINDOW_LIMIT,
                        global_window_seconds=FLAG_GLOBAL_WINDOW_SECONDS,
                        client_limit=FLAG_CLIENT_WINDOW_LIMIT,
                        client_window_seconds=FLAG_CLIENT_WINDOW_SECONDS,
                        max_flaggers=FLAG_MAX_FLAGGERS_PER_GROUP,
                        now=now,
                    )
                self._invalidate_reports_cache()
        except CommunityCooldownActive as error:
            raise CommunityServiceError(429, {
                "message": "Troppe segnalazioni in questo momento. Riprova più tardi.",
                "retry_after_seconds": max(
                    1,
                    int(math.ceil(error.cooldown_until - now)),
                ),
            }) from error
        except CommunityFlagCapacityReached as error:
            raise CommunityServiceError(429, {
                "message": "Questo contenuto ha raggiunto il limite di segnalazioni.",
                "code": "community_flag_capacity_reached",
            }) from error
        except CommunityMutationTargetUnavailable as error:
            raise CommunityServiceError(
                404,
                "Segnalazione non piu attiva.",
            ) from error
        except CommunityRepositoryUnavailable as error:
            raise self._storage_unavailable() from error

        hidden = bool(state.get("hidden", False))
        return CommunityReportFlaggedResponse(
            ok=True,
            group_id=group_id,
            reason=str(state.get("_reason") or reason),
            hidden=True,
            hidden_global=hidden,
            flag_count=max(0, int(state.get("flag_count", 0))),
            already_reported=bool(state.get("_already_reported", False)),
            retention_seconds=FLAG_RETENTION_SECONDS,
            source=CommunitySource(
                id="community_report_flags",
                type="moderation_signal",
                verified=False,
                storage=stored_in,
            ),
        )

    def _build_report(
        self,
        *,
        type_id: str,
        municipality: Municipality,
        owner_key: str,
        identity: CommunityIdentitySnapshot | None = None,
        now: float,
    ) -> dict[str, Any]:
        x, y = self._map_position(municipality.latitude, municipality.longitude)
        return {
            "id": self.report_id_factory(),
            "type_id": type_id,
            "type_category": "status" if type_id == "quiet" else "phenomenon",
            "place": municipality.name,
            "lat": municipality.latitude,
            "lon": municipality.longitude,
            "x": x,
            "y": y,
            "created_at": now,
            "expires_at": now + REPORT_TTL_SECONDS,
            "group_id": self._group_id(type_id, municipality.name, now),
            "location_precision": COMMUNITY_LOCATION_PRECISION,
            "selected_place": municipality.name,
            "owner_key": owner_key,
            "identity": (
                identity.model_dump(mode="python")
                if identity is not None
                else None
            ),
        }

    def _public_report(self, report: dict[str, Any], now: float) -> CommunityReportPublic:
        created_at = float(report["created_at"])
        expires_at = float(report["expires_at"])
        type_id = str(report.get("type_id") or "").strip().lower()
        place = str(report.get("place") or "").strip()
        municipality = self.catalog.match_names(place)
        if municipality is None:
            raise ValueError("noncanonical_community_place")
        lat = municipality.latitude
        lon = municipality.longitude
        x, y = self._map_position(lat, lon)
        return CommunityReportPublic(
            id=str(report.get("id") or ""),
            typeId=type_id,
            typeCategory="status" if type_id == "quiet" else "phenomenon",
            groupId=str(
                report.get("group_id")
                or self._group_id(type_id, municipality.name, created_at)
            ),
            place=municipality.name,
            lat=lat,
            lon=lon,
            locationPrecision=COMMUNITY_LOCATION_PRECISION,
            x=float(x),
            y=float(y),
            createdAt=int(created_at * 1000),
            expiresAt=int(expires_at * 1000),
            time="",
            source="community",
            sourceKey=self._public_source_key(report),
            identity=self._public_identity(report),
        )

    def _publishable_stored_report_expiry(
        self,
        report: dict[str, Any],
        now: float,
    ) -> float | None:
        type_id = str(report.get("type_id") or "").strip().lower()
        place = str(report.get("place") or "").strip()
        owner_key = str(report.get("owner_key") or "").strip()
        if (
            type_id not in REPORT_TYPES
            or self.catalog.match_names(place) is None
            or not owner_key
        ):
            return None
        try:
            created_at = float(report["created_at"])
            expires_at = float(report["expires_at"])
        except (KeyError, TypeError, ValueError, OverflowError):
            return None
        if not math.isfinite(created_at) or not math.isfinite(expires_at):
            return None
        if created_at > now or expires_at <= now:
            return None
        if not math.isclose(
            expires_at - created_at,
            REPORT_TTL_SECONDS,
            rel_tol=0.0,
            abs_tol=1e-6,
        ):
            return None
        return expires_at

    @staticmethod
    def _storage_unavailable() -> CommunityServiceError:
        return CommunityServiceError(503, {
            "message": "Il servizio segnalazioni è temporaneamente non disponibile.",
            "code": "community_storage_unavailable",
        })

    @staticmethod
    def _reputation_award_day(now: float) -> str:
        return datetime.fromtimestamp(now, get_fvg_timezone()).date().isoformat()

    @staticmethod
    def _reputation_rank(points: int) -> CommunityReputationRank:
        if points >= 20:
            return CommunityReputationRank(
                id="sentinel",
                label="Sentinele dal Teritori",
                min_points=20,
                next_rank_at=None,
            )
        if points >= 5:
            return CommunityReputationRank(
                id="lookout",
                label="Vuaite dal Timp",
                min_points=5,
                next_rank_at=20,
            )
        return CommunityReputationRank(
            id="novice",
            label="Osservadôr dal Cîl",
            min_points=0,
            next_rank_at=5,
        )

    def _invalidate_reports_cache(self) -> None:
        self._reports_cache = None

    @staticmethod
    def _require_group_mutation_capacity(
        reports: list[dict[str, Any]],
    ) -> None:
        if len(reports) > GROUP_MUTATION_MAX_REPORTS:
            raise CommunityServiceError(503, {
                "message": "Il gruppo contiene troppe segnalazioni attive; riprova più tardi.",
                "code": "community_group_temporarily_too_large",
                "maximum_active_reports": GROUP_MUTATION_MAX_REPORTS,
            })

    def _group_reports(
        self,
        reports: list[CommunityReportPublic],
        confirmation_states: dict[str, dict[str, int]] | None = None,
    ) -> list[CommunityReportGroup]:
        grouped: dict[str, list[CommunityReportPublic]] = {}
        for report in reports:
            grouped.setdefault(report.groupId, []).append(report)

        groups = []
        for group_id, items in grouped.items():
            items.sort(key=lambda item: item.createdAt, reverse=True)
            newest = items[0]
            state = (confirmation_states or {}).get(
                group_id,
                {"yes": 0, "no": 0},
            )
            groups.append(self._group_from_reports(group_id, items, state))
        return sorted(groups, key=lambda group: group.createdAt, reverse=True)

    @staticmethod
    def _group_from_reports(
        group_id: str,
        items: list[CommunityReportPublic],
        state: dict[str, Any],
    ) -> CommunityReportGroup:
        sorted_items = sorted(items, key=lambda item: item.createdAt, reverse=True)
        newest = sorted_items[0]
        group_payload = newest.model_dump()
        group_payload.update({"id": group_id, "groupId": group_id})
        source_keys = list(dict.fromkeys(
            item.sourceKey for item in sorted_items if item.sourceKey
        ))
        identities: list[CommunitySourceIdentity] = []
        seen_sources: set[str] = set()
        for item in sorted_items:
            source_key = str(item.sourceKey or "")
            if not source_key or source_key in seen_sources:
                continue
            seen_sources.add(source_key)
            identities.append(CommunitySourceIdentity(
                sourceKey=source_key,
                identity=(
                    item.identity.model_copy(deep=True)
                    if item.identity is not None
                    else None
                ),
            ))
        return CommunityReportGroup(
            **group_payload,
            reportIds=[item.id for item in sorted_items],
            sourceKeys=source_keys,
            identities=identities or None,
            count=len(sorted_items),
            confirmations=ConfirmationCounts(
                yes=max(0, int(state.get("yes", 0))),
                no=max(0, int(state.get("no", 0))),
            ),
        )

    @staticmethod
    def _group_id(type_id: str, place: str, created_at: float) -> str:
        normalized_type = re.sub(r"[^a-z0-9_-]+", "-", type_id.lower()).strip("-") or "report"
        normalized_place = re.sub(
            r"[^a-z0-9_-]+",
            "-",
            normalize_text(place),
        ).strip("-") or "zona"
        bucket = int(created_at // REPORT_GROUP_WINDOW_SECONDS)
        return f"group-{normalized_type}:{normalized_place}:{bucket}"

    def _stored_group_id(self, report: dict[str, Any]) -> str:
        stored = str(report.get("group_id") or "").strip()
        if stored:
            return stored
        return self._group_id(
            str(report.get("type_id") or ""),
            str(report.get("place") or ""),
            float(report.get("created_at") or self.now()),
        )

    @staticmethod
    def _public_source_key(report: dict[str, Any]) -> str:
        owner_key = str(report.get("owner_key") or "").strip()
        if not owner_key:
            return ""
        created_at = float(report.get("created_at") or 0)
        bucket = int(created_at // PUBLIC_SOURCE_KEY_BUCKET_SECONDS)
        return hashlib.sha256(
            f"community-source-v1:{bucket}:{owner_key}".encode("utf-8")
        ).hexdigest()[:PUBLIC_SOURCE_KEY_LENGTH]

    @staticmethod
    def _public_identity(
        report: dict[str, Any],
    ) -> CommunityIdentitySnapshot | None:
        identity = report.get("identity")
        if not isinstance(identity, dict):
            return None
        try:
            return CommunityIdentitySnapshot.model_validate(identity)
        except ValidationError:
            # Legacy or malformed stored display data must never make the
            # otherwise valid ephemeral report disappear from the feed.
            return None

    @staticmethod
    def _require_current_community_terms(
        command: CommunityReportCreate | CommunityReportConfirmationCreate,
    ) -> None:
        if (
            command.accepted_terms is not True
            or command.policy_version != COMMUNITY_GUIDELINES_POLICY_VERSION
        ):
            raise CommunityServiceError(400, {
                "message": "Devi accettare le linee guida community correnti.",
                "code": "community_terms_required",
                "policy_version": COMMUNITY_GUIDELINES_POLICY_VERSION,
            })

    @staticmethod
    def _require_confirmation_terms_or_legacy(
        command: CommunityReportConfirmationCreate,
    ) -> None:
        terms_fields = {"accepted_terms", "policy_version"}
        provided_terms_fields = command.model_fields_set & terms_fields
        if not provided_terms_fields:
            # The Play 300011 client sends only vote and client_id. Keep that
            # exact legacy shape valid while the closed-test cohort updates.
            return
        if provided_terms_fields != terms_fields:
            raise CommunityServiceError(400, {
                "message": "Devi accettare le linee guida community correnti.",
                "code": "community_terms_required",
                "policy_version": COMMUNITY_GUIDELINES_POLICY_VERSION,
            })
        CommunityService._require_current_community_terms(command)

    @staticmethod
    def _require_client_id(client_id: str) -> None:
        normalized = re.sub(
            r"[^a-zA-Z0-9._:-]+",
            "",
            str(client_id or ""),
        ).strip()
        if not normalized:
            raise CommunityServiceError(400, {
                "message": "Identificatore installazione non valido.",
                "code": "community_client_id_required",
            })

    @staticmethod
    def _client_key(scope: str, client_id: str) -> str:
        normalized_client_id = re.sub(
            r"[^a-zA-Z0-9._:-]+",
            "",
            str(client_id or ""),
        ).strip()[:128]
        return hashlib.sha256(
            f"{scope}:{normalized_client_id}".encode("utf-8")
        ).hexdigest()

    @staticmethod
    def _is_in_fvg_bounds(lat: float, lon: float) -> bool:
        return (
            FVG_REPORT_BOUNDS["lat_min"] <= lat <= FVG_REPORT_BOUNDS["lat_max"]
            and FVG_REPORT_BOUNDS["lon_min"] <= lon <= FVG_REPORT_BOUNDS["lon_max"]
        )

    @staticmethod
    def _map_position(lat: float, lon: float) -> tuple[float, float]:
        x = (lon - FVG_MAP_BOUNDS["lon_min"]) / (
            FVG_MAP_BOUNDS["lon_max"] - FVG_MAP_BOUNDS["lon_min"]
        ) * 100
        y = (FVG_MAP_BOUNDS["lat_max"] - lat) / (
            FVG_MAP_BOUNDS["lat_max"] - FVG_MAP_BOUNDS["lat_min"]
        ) * 100
        return round(min(100, max(0, x)), 2), round(min(100, max(0, y)), 2)
