"""Rolling upgrade of the public Community API, over one atomic store.

An absent protocol header is the published 0.1.14 client. It must never be
interpreted as v3 or be used to vote/edit a v3 observation without its GPS and
observed-members checks. Protocol selection is not authentication.
"""
from copy import deepcopy

from app.services.community import CommunityServiceError
from app.services.community_reports import CommunityReportsService, RULES_VERSION
from app.services.pilot_community import PilotCommunityService


RULES_HEADER = "x-meteo-community-rules"
LEGACY_RULES_VERSION = "community-pilot-national-safety-v2"
V3_GROUP_PREFIX = "group-v3-"


def v3_group_id(legacy_id):
    # Preserve the public wire convention: the second ':' field is ISTAT.
    return V3_GROUP_PREFIX + legacy_id.removeprefix("group-")


def require_app_update():
    raise CommunityServiceError(426, {
        "code": "community_app_update_required",
        "message": "Aggiorna Meteo Friûl per interagire con le nuove segnalazioni.",
    })


class LegacyCommunityService(PilotCommunityService):
    """Preserve old operations, without letting them alter v3 records."""

    def _require_legacy_owner(self, owner):
        # Accepted receipts are permanent (their public content is redacted
        # after 48h). The marker is outside that content, so restarting or
        # expiring a report cannot re-enable the old rules for an upgraded ID.
        if any(key.startswith(owner + ":") and receipt.get("rules_version") == RULES_VERSION
               for key, receipt in self.repository._pilot_operations.items()):
            require_app_update()

    def create_report(self, command, *, client_host):
        self._require_client_id(command.client_id)
        owner = self._client_key("community-report", command.client_id)
        with self.repository.transaction():
            replay = self._replay(owner, command.operation_id, self._fingerprint("create", "", command))
            if replay:
                return replay
            self._require_legacy_owner(owner)
            result = super().create_report(command, client_host=client_host)
            self.repository.record_report_submission_memory(
                owner, award_day=self._reputation_award_day(self.now()), now=self.now())
            return result

    def _owned_report(self, report_id, owner_key, expected_revision, now):
        report = super()._owned_report(report_id, owner_key, expected_revision, now)
        if report.get("rules_version") == RULES_VERSION:
            require_app_update()
        self._require_legacy_owner(owner_key)
        return report

    def _require_editable(self, report, now, *, allow_withdrawn=False):
        if report.get("rules_version") == RULES_VERSION:
            require_app_update()
        self._require_legacy_owner(report["owner_key"])
        return super()._require_editable(report, now, allow_withdrawn=allow_withdrawn)

    def _owner_metadata(self, report):
        if report.get("rules_version") == RULES_VERSION:
            return {"correction_until": 0, "replacement_available": False}
        return super()._owner_metadata(report)

    def _merge_protections(self, source, target, confirmation, now):
        if source.get("rules_version") == RULES_VERSION:
            return confirmation
        return super()._merge_protections(source, target, confirmation, now)

    def _build_report(self, **kwargs):
        report = super()._build_report(**kwargs)
        if self.repository.get_group_moderation(v3_group_id(report["group_id"]), self.now()).get("hidden"):
            raise CommunityServiceError(409, {"code": "community_group_hidden", "message": "Osservazione nascosta dalla moderazione."})
        return report

    def confirm_report(self, group_id, command, *, client_host):
        with self.repository.transaction():
            members, _ = self.repository.list_group_reports(group_id, self.now())
            if group_id.startswith(V3_GROUP_PREFIX) or any(item.get("rules_version") == RULES_VERSION for item in members):
                require_app_update()
            result = super().confirm_report(group_id, command, client_host=client_host)
            # Keep the final counters when these legacy observations expire
            # and the new app subsequently reads the 48-hour history.
            for item in members:
                current = self.repository._reports.get(item["id"])
                history = self.repository._pilot_history.get(item["id"], [])
                if current and history:
                    history[-1]["report"] = deepcopy(current)
            return result


class CloudCommunityReportsService(CommunityReportsService):
    """v3 rules plus a safe bridge to still-active legacy observations."""

    def __init__(self, *, legacy_service, **kwargs):
        super().__init__(**kwargs)
        if legacy_service.repository is not self.repository:
            raise ValueError("community_compatibility_requires_shared_repository")
        self.legacy_service = legacy_service

    def _build_report(self, **kwargs):
        report = super()._build_report(**kwargs)
        if self.repository.get_group_moderation(report["group_id"], self.now()).get("hidden"):
            raise CommunityServiceError(409, {"code": "community_group_hidden", "message": "Osservazione nascosta dalla moderazione."})
        # Legacy confirmations do not identify the observations they saw.
        # Separate group identities stop those votes validating new content.
        report["group_id"] = v3_group_id(report["group_id"])
        return report

    def _receipt(self, owner_key, operation_id, fingerprint, result, now):
        super()._receipt(owner_key, operation_id, fingerprint, result, now)
        self.repository._pilot_operations[f"{owner_key}:{operation_id}"]["rules_version"] = RULES_VERSION

    def confirm_report(self, group_id, command, *, client_host):
        if group_id.startswith(V3_GROUP_PREFIX):
            return super().confirm_report(group_id, command, client_host=client_host)
        self._require_current_community_terms(command)
        self._require_client_id(command.client_id)
        self._require_gps(command)
        with self.repository.transaction():
            self._confirmation_members(group_id, command, self.now())
            # A legacy observation keeps its original award ledger/rules.
            # Calling v3's award path here would count it again when an old
            # client subsequently confirms the same group.
            return self.legacy_service.confirm_report(group_id, command, client_host=client_host)
