"""Bounded ephemeral national storage for the standalone loopback pilot.

The shared repository limits its FVG feed to 200 reports globally. The pilot
indexes reports by canonical municipality and applies that feed limit *after*
the geographic filter, so busy distant places cannot evict a local report.
"""

from copy import deepcopy
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Callable

from app.repositories.community import (
    CommunityRepository, CommunityRepositoryUnavailable, MAX_REPORTS,
    _reputation_award_document_id,
)
from app.services.location import haversine_km


MAX_PILOT_ACTIVE_REPORTS = 10_000
# Minimal reconciliation evidence remains private and invisible for one hour
# after public expiry. The cap is comfortably above the pilot's request budget
# while keeping process memory deterministic.
PILOT_EXPIRED_TOMBSTONE_GRACE_SECONDS = 60 * 60
MAX_PILOT_EXPIRED_TOMBSTONES = 20_000

# This list is also the versioned local SQLite schema: protection ledgers must
# survive exactly the same transaction as the visible observation they govern.
PILOT_STATE_FIELDS = (
    "_reports", "_cooldowns", "_confirmations", "_flags", "_moderation",
    "_source_blocks", "_rate_limits", "_reputations", "_reputation_awards",
    "_municipality_reports", "_municipality_points", "_owner_reports",
    "_expired_observations", "_update_receipts", "_pilot_requests",
    "_pilot_creations", "_pilot_operations", "_pilot_replacements",
    "_pilot_lineages", "_pilot_history", "_pilot_award_cooldowns",
)


class PilotObservationUnavailable(RuntimeError):
    pass


class PilotObservationOwnerMismatch(RuntimeError):
    pass


class PilotObservationExpired(RuntimeError):
    def __init__(self, state: dict[str, Any]) -> None:
        super().__init__("community_observation_expired")
        self.state = state


class PilotObservationRevisionConflict(RuntimeError):
    def __init__(self, state: dict[str, Any]) -> None:
        super().__init__("community_observation_revision_conflict")
        self.state = state


class PilotObservationIdempotencyConflict(RuntimeError):
    pass


class PilotObservationLocationChanged(RuntimeError):
    pass


class PilotObservationSourceBlocked(RuntimeError):
    def __init__(self, blocked_until: float) -> None:
        super().__init__("community_source_temporarily_blocked")
        self.blocked_until = float(blocked_until)


class PilotObservationGroupHidden(RuntimeError):
    pass


class PilotObservationNotUpdateable(RuntimeError):
    pass


class PilotMemoryCommunityRepository(CommunityRepository):
    storage_kind = "memory"

    def _snapshot_state(self):
        return {
            field: deepcopy(getattr(self, field, {}))
            for field in PILOT_STATE_FIELDS
        }

    def _restore_state(self, state):
        for field in PILOT_STATE_FIELDS:
            setattr(self, field, deepcopy(state[field]))

    @contextmanager
    def transaction(self):
        """Apply one service operation atomically, including nested operations.

        A failed inner operation poisons its outer transaction even if a caller
        catches the exception, so partially changed quotas cannot be committed.
        The durable local repository overrides only this boundary.
        """
        with self.lock:
            depth = getattr(self, "_pilot_transaction_depth", 0)
            outermost = depth == 0
            if outermost:
                before = self._snapshot_state()
                self._pilot_transaction_failed = False
            self._pilot_transaction_depth = depth + 1
            try:
                yield self
                if outermost and self._pilot_transaction_failed:
                    raise CommunityRepositoryUnavailable("pilot_transaction_aborted")
            except BaseException:
                self._pilot_transaction_failed = True
                if outermost:
                    self._restore_state(before)
                raise
            finally:
                self._pilot_transaction_depth = depth

    def __init__(self):
        super().__init__(storage_mode="memory")
        self._municipality_reports: dict[str, set[str]] = {}
        self._municipality_points: dict[str, tuple[float, float]] = {}
        self._owner_reports: dict[str, set[str]] = {}
        self._expired_observations: dict[str, dict[str, Any]] = {}
        # One receipt per report is sufficient: after a later successful
        # revision an older operation is rejected by expected_revision.
        self._update_receipts: dict[str, dict[str, Any]] = {}
        self._pilot_requests: dict[str, tuple[float, int]] = {}
        self._pilot_creations: dict[str, list[float]] = {}
        self._pilot_operations: dict[str, dict[str, Any]] = {}
        self._pilot_replacements: dict[str, dict[str, Any]] = {}
        self._pilot_lineages: dict[str, bool] = {}
        self._pilot_history: dict[str, list[dict[str, Any]]] = {}
        self._pilot_award_cooldowns: dict[str, float] = {}

    def _record_reputation_awards_memory(self, *, owner_keys, now, **kwargs):
        # The 45-minute window is only an award rule, never a posting block.
        group_id = kwargs["group_id"]
        lineage_owners = {
            report["owner_key"] for report in self._reports.values()
            if report["group_id"] == group_id
            and self._pilot_award_cooldowns.get(f"lineage:{report.get('lineage_id') or report['id']}", 0) > now
        }
        eligible = [key for key in owner_keys if key not in lineage_owners and self._pilot_award_cooldowns.get(key, 0) <= now]
        before = set(self._reputation_awards)
        super()._record_reputation_awards_memory(owner_keys=eligible, now=now, **kwargs)
        added = [value for key, value in self._reputation_awards.items() if key not in before]
        for owner_key in eligible:
            if any(item.get("owner_key") == owner_key and item.get("status") == "awarded" for item in added):
                self._pilot_award_cooldowns[owner_key] = now + 45 * 60
        for report in self._reports.values():
            if report["group_id"] == group_id:
                self.protect_lineage_award(report, now)

    def protect_lineage_award(self, report, now):
        award = self._reputation_awards.get(_reputation_award_document_id(report["group_id"], report["owner_key"]))
        if award and award.get("status") in {"awarded", "revoked"}:
            lineage = str(report.get("lineage_id") or report["id"])
            self._pilot_award_cooldowns[f"lineage:{lineage}"] = now + 48 * 3600

    def _db(self):
        return None

    def _trim_memory(self):
        # Capacity is checked before inserting, never by dropping other places.
        return None

    def save_report(self, report):
        report.setdefault("revision", 1)
        report.setdefault("updated_at", float(report["created_at"]))
        self._prune_memory(float(report["updated_at"]))
        report_id = str(report["id"])
        code = str(report["istat_code"])
        if report_id not in self._reports and len(self._reports) >= MAX_PILOT_ACTIVE_REPORTS:
            raise CommunityRepositoryUnavailable("pilot_community_memory_capacity_reached")
        previous = self._reports.get(report_id)
        if previous:
            self._remove_indexes(report_id, previous)
        else:
            self._update_receipts.pop(report_id, None)
        self._expired_observations.pop(report_id, None)
        result = super().save_report(report)
        self._municipality_reports.setdefault(code, set()).add(report_id)
        owner_key = str(report.get("owner_key") or "")
        if owner_key:
            self._owner_reports.setdefault(owner_key, set()).add(report_id)
        # Report coordinates here are already canonical public points from the
        # verified geography service; the raw device GPS never reaches storage.
        self._municipality_points[code] = (float(report["lat"]), float(report["lon"]))
        return result

    def _remove_index(self, report_id, code):
        members = self._municipality_reports.get(code)
        if members is not None:
            members.discard(report_id)
            if not members:
                self._municipality_reports.pop(code, None)
                self._municipality_points.pop(code, None)

    def _remove_indexes(self, report_id, report):
        self._remove_index(report_id, str(report.get("istat_code") or ""))
        owner_key = str(report.get("owner_key") or "")
        owner_members = self._owner_reports.get(owner_key)
        if owner_members is not None:
            owner_members.discard(report_id)
            if not owner_members:
                self._owner_reports.pop(owner_key, None)

    def delete_report(self, report_id):
        previous = self._reports.get(report_id)
        result = super().delete_report(report_id)
        if previous:
            self._remove_indexes(report_id, previous)
        self._update_receipts.pop(str(report_id), None)
        self._expired_observations.pop(str(report_id), None)
        return result

    def get_report(self, report_id, now):
        # The shared implementation silently discards an expired memory record.
        # Pilot reconciliation must first retain its minimal authoritative state.
        with self.lock:
            self._prune_memory(now)
            report = self._reports.get(str(report_id))
            return (deepcopy(report) if report is not None else None, "memory")

    def _prune_memory(self, now):
        for report_id, report in list(self._reports.items()):
            if float(report.get("expires_at") or 0) <= now:
                self._remember_expired(report, now=now)
        super()._prune_memory(now)
        for code, members in list(self._municipality_reports.items()):
            members.intersection_update(self._reports)
            if not members:
                self._municipality_reports.pop(code, None)
                self._municipality_points.pop(code, None)
        for owner_key, members in list(self._owner_reports.items()):
            members.intersection_update(self._reports)
            if not members:
                self._owner_reports.pop(owner_key, None)
        self._expired_observations = {
            report_id: state
            for report_id, state in self._expired_observations.items()
            if float(state.get("reconcile_until") or 0) > now
        }
        self._update_receipts = {
            report_id: receipt
            for report_id, receipt in self._update_receipts.items()
            if float(receipt.get("expires_at") or 0) > now
        }
        # Private retry/audit records have a bounded 48-hour retention, separate
        # from the public one-hour observation. Quotas retain their full window.
        self._pilot_creations = {
            key: recent for key, values in self._pilot_creations.items()
            if (recent := [value for value in values if value > now - 86400])
        }
        # Accepted operation identities never become executable again. After
        # 48 hours keep only a private receipt, removing report/alias content.
        for receipt in self._pilot_operations.values():
            if receipt["expires_at"] <= now and not receipt["result"].get("reconciled_only"):
                original = receipt["result"]
                report = original.get("report") or {}
                receipt["result"] = {
                    "ok": True, "action": original.get("action"),
                    "operation_id": original.get("operation_id"),
                    "report_id": original.get("report_id") or report.get("id"),
                    "revision": original.get("revision") or report.get("revision"),
                    "idempotent_replay": True, "reconciled_only": True,
                }
        self._pilot_replacements = {key: value for key, value in self._pilot_replacements.items() if value["expires_at"] + 48 * 3600 > now}
        self._pilot_history = {
            key: recent for key, values in self._pilot_history.items()
            if (recent := [value for value in values if value["at"] > now - 48 * 3600])
        }
        protected_lineages = {
            str(value.get("lineage_id") or value["id"]) for value in self._reports.values()
        } | {value["lineage_id"] for value in self._pilot_replacements.values()}
        self._pilot_lineages = {key: value for key, value in self._pilot_lineages.items() if key in protected_lineages}
        active_lineage_keys = {f"lineage:{value.get('lineage_id') or value['id']}" for value in self._reports.values()}
        self._pilot_award_cooldowns = {
            key: max(value, now + 48 * 3600) if key in active_lineage_keys else value
            for key, value in self._pilot_award_cooldowns.items()
            if value > now or key in active_lineage_keys
        }

    def _remember_expired(self, report: dict[str, Any], *, now: float) -> None:
        report_id = str(report.get("id") or "")
        owner_key = str(report.get("owner_key") or "")
        expires_at = float(report.get("expires_at") or 0)
        if not report_id or not owner_key or expires_at <= 0:
            return
        self._expired_observations[report_id] = {
            "report_id": report_id,
            "owner_key": owner_key,
            "status": "expired",
            "expires_at": expires_at,
            "revision": max(1, int(report.get("revision") or 1)),
            "reconcile_until": expires_at + PILOT_EXPIRED_TOMBSTONE_GRACE_SECONDS,
        }
        if len(self._expired_observations) > MAX_PILOT_EXPIRED_TOMBSTONES:
            oldest = min(
                self._expired_observations,
                key=lambda key: (
                    float(self._expired_observations[key].get("reconcile_until") or 0),
                    key,
                ),
            )
            self._expired_observations.pop(oldest, None)

    @staticmethod
    def _observation_state(report: dict[str, Any], *, now: float) -> dict[str, Any]:
        return {
            "report_id": str(report.get("id") or report.get("report_id") or ""),
            "status": "expired" if float(report.get("expires_at") or 0) <= now else "recent",
            "expires_at": float(report.get("expires_at") or 0),
            "server_time": now,
            "revision": max(1, int(report.get("revision") or 1)),
        }

    def get_active_owner_observation(
        self, owner_key: str, *, now: float,
    ) -> dict[str, Any] | None:
        with self.lock:
            self._prune_memory(now)
            reports = [
                self._reports[report_id]
                for report_id in self._owner_reports.get(owner_key, set())
                if report_id in self._reports
                and float(self._reports[report_id].get("expires_at") or 0) > now
            ]
            if not reports:
                return None
            reports.sort(
                key=lambda item: (
                    float(item.get("updated_at") or item.get("created_at") or 0),
                    str(item.get("id") or ""),
                ),
                reverse=True,
            )
            return deepcopy(reports[0])

    def refresh_observation_atomic(
        self,
        report_id: str,
        *,
        owner_key: str,
        operation_id: str,
        expected_revision: int,
        location_matches: Callable[[str], bool],
        ttl_seconds: int,
        now_factory: Callable[[], float],
    ) -> dict[str, Any]:
        """Renew one pilot observation at a single in-memory linearization point."""

        with self.lock:
            accepted_at = float(now_factory())
            self._prune_memory(accepted_at)

            receipt = self._update_receipts.get(report_id)
            if receipt and str(receipt.get("operation_id") or "") == operation_id:
                if (
                    str(receipt.get("owner_key") or "") != owner_key
                    or int(receipt.get("expected_revision") or 0) != expected_revision
                ):
                    raise PilotObservationIdempotencyConflict(
                        "community_idempotency_conflict"
                    )
                result = deepcopy(dict(receipt.get("result") or {}))
                result["idempotent_replay"] = True
                return result

            report = self._reports.get(report_id)
            if report is None:
                tombstone = self._expired_observations.get(report_id)
                if tombstone is not None:
                    if str(tombstone.get("owner_key") or "") != owner_key:
                        raise PilotObservationOwnerMismatch(
                            "community_observation_owner_mismatch"
                        )
                    raise PilotObservationExpired(
                        self._observation_state(tombstone, now=accepted_at)
                    )
                raise PilotObservationUnavailable(
                    "community_observation_not_active"
                )

            if str(report.get("owner_key") or "") != owner_key:
                raise PilotObservationOwnerMismatch(
                    "community_observation_owner_mismatch"
                )
            if accepted_at >= float(report.get("expires_at") or 0):
                self._remember_expired(report, now=accepted_at)
                self._remove_indexes(report_id, report)
                self._reports.pop(report_id, None)
                raise PilotObservationExpired(
                    self._observation_state(report, now=accepted_at)
                )

            revision = max(1, int(report.get("revision") or 1))
            if expected_revision != revision:
                raise PilotObservationRevisionConflict(
                    self._observation_state(report, now=accepted_at)
                )
            if not location_matches(str(report.get("istat_code") or "")):
                raise PilotObservationLocationChanged(
                    "community_observation_location_changed"
                )

            block = self.get_source_block(owner_key, accepted_at)
            blocked_until = (
                float(block.get("blocked_until") or 0)
                if isinstance(block, dict)
                else 0
            )
            if blocked_until > accepted_at:
                raise PilotObservationSourceBlocked(blocked_until)
            moderation = self.get_group_moderation(
                str(report.get("group_id") or ""), accepted_at,
            )
            if bool(report.get("moderation_hidden", False)) or bool(
                moderation.get("hidden", False)
            ):
                raise PilotObservationGroupHidden("community_group_hidden")
            confirmation = self.get_confirmation(
                str(report.get("group_id") or "")
            )
            map_withdrawn = bool(
                report.get("map_withdrawn", False)
                or confirmation.get("map_withdrawn", False)
            )
            validity_status = str(
                confirmation.get("validity_status")
                or report.get("validity_status")
                or "unverified"
            )
            temporal_status = str(
                confirmation.get("temporal_status")
                or report.get("temporal_status")
                or "active"
            )
            if (
                map_withdrawn
                or validity_status == "rejected"
                or temporal_status == "ceased"
            ):
                raise PilotObservationNotUpdateable(
                    "community_observation_not_updateable"
                )

            previous_expires_at = float(report["expires_at"])
            updated = deepcopy(report)
            updated.update({
                "updated_at": accepted_at,
                "expires_at": accepted_at + int(ttl_seconds),
                "revision": revision + 1,
            })
            storage = self.save_report(updated)
            confirmation = self._confirmations.get(
                str(updated.get("group_id") or "")
            )
            if confirmation is not None:
                extended_confirmation = deepcopy(confirmation)
                extended_confirmation["expires_at_timestamp"] = datetime.fromtimestamp(
                    float(updated["expires_at"]), timezone.utc,
                )
                extended_confirmation["updated_at"] = datetime.fromtimestamp(
                    accepted_at, timezone.utc,
                )
                self._confirmations[str(updated.get("group_id") or "")] = (
                    extended_confirmation
                )
            result = {
                "report": deepcopy(updated),
                "revision": revision + 1,
                "updated_at": accepted_at,
                "previous_expires_at": previous_expires_at,
                "idempotent_replay": False,
                "storage": storage,
            }
            self._update_receipts[report_id] = {
                "operation_id": operation_id,
                "owner_key": owner_key,
                "expected_revision": expected_revision,
                "expires_at": float(updated["expires_at"]),
                "result": deepcopy(result),
            }
            self._expired_observations.pop(report_id, None)
            return result

    def list_scoped_reports(self, *, now, lat, lon, radius_km):
        self._prune_memory(now)
        hidden = self.list_hidden_group_ids(now)
        matching_ids = set()
        for code, point in self._municipality_points.items():
            if haversine_km(lat, lon, *point) <= radius_km:
                matching_ids.update(self._municipality_reports[code])
        # Expired/hidden records must not consume any of the visible slots.
        reports = [
            self._reports[report_id] for report_id in matching_ids
            if not self._reports[report_id].get("moderation_hidden", False)
            and self._reports[report_id].get("group_id") not in hidden
        ]
        reports.sort(
            key=lambda item: (
                float(item.get("updated_at") or item["created_at"]),
                str(item["id"]),
            ),
            reverse=True,
        )
        return [deepcopy(report) for report in reports[:MAX_REPORTS]], "memory"
