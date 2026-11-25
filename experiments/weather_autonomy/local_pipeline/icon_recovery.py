"""Opt-in bounded ICON discovery and fenced, product-independent recovery.

No timers, cloud clients or claim deletion. A clock never releases an owner.
Only a validated durable checkpoint permits another execution to resume work.
The rollout must first prove quiescence of legacy workers, which do not use
this product-wide fence. Ambiguous legacy claims are not migrated here.
"""
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
import re
from time import sleep
from uuid import uuid4

from .contract_v1 import canonical_json_bytes
from .operational_diagnostics import emit, error_fields
from .sqlite_object_store import ObjectNotFound, ObjectStoreError, PreconditionFailed

FEATURE_FLAG = "WEATHER_ICON_AUTOMATIC_RECOVERY_ENABLED"
BASE_HOURS_UTC = (6, 18)
RECOVERY_OFFSETS_HOURS = (0, 1, 2, 4)
SCHEDULE_HOURS_UTC = tuple(base + offset for base in BASE_HOURS_UTC for offset in RECOVERY_OFFSETS_HOURS)
MAX_DISCOVERY_ATTEMPTS = 2
MAX_POLLS_PER_PRODUCT_DAY = len(SCHEDULE_HOURS_UTC)
ROOT = "state/icon-recovery/v1/"
_RUN = re.compile(r"\d{8}T(?:00|12)0000Z\Z")
_OWNER = re.compile(r"[a-z][a-z0-9-]{0,127}\Z")
_SLOT = re.compile(r"\d{8}-(?:am|pm)\Z")
_INCIDENT = re.compile(r"[a-f0-9]{32}\Z")
_SHA256 = re.compile(r"[a-f0-9]{64}\Z")
_ETAG = re.compile(r'(?:[1-9][0-9]*|"sha256-[a-f0-9]{64}")\Z')


def enabled(environ=None):
    value = (os.environ if environ is None else environ).get(FEATURE_FLAG, "false")
    if value not in {"true", "false"}:
        raise ValueError("invalid ICON automatic recovery opt-in")
    return value == "true"


def window(now):
    if not isinstance(now, datetime) or now.tzinfo is None:
        raise ValueError("aware ICON recovery clock required")
    now = now.astimezone(timezone.utc)
    if now.hour not in SCHEDULE_HOURS_UTC:
        return None
    base = 6 if now.hour < 12 else 18
    return {"slot": now.strftime("%Y%m%d") + ("-am" if base == 6 else "-pm"),
            "poll": now.strftime("%Y%m%dT%H0000Z"),
            "expected_run": now.strftime("%Y%m%dT") + ("000000Z" if base == 6 else "120000Z"),
            "offset_hours": now.hour - base}


def run_id(value):
    if not isinstance(value, str) or not _RUN.fullmatch(value):
        raise ValueError("invalid ICON recovery cycle")
    parsed = datetime.strptime(value, "%Y%m%dT%H%M%SZ")
    if parsed.strftime("%Y%m%dT%H%M%SZ") != value:
        raise ValueError("invalid ICON recovery cycle")
    return value


def discovery(now, high_water):
    """Only bounded public HTML listings, never GRIB acquisition."""
    from run_pilot import discover_complete_run, SourceRunNotAdvanced
    from probe_icon2i import PublicReader
    try:
        run, *_ = discover_complete_run(PublicReader(max_bytes=4 * 1024**2), now,
                                        source_run_high_water=high_water)
        return run
    except SourceRunNotAdvanced:
        return None
    except ValueError as error:
        # Initial bootstrap has no verified high-water; the existing discovery
        # reports its empty/partial usable set with this explicit message.
        if str(error).startswith("No complete public run can cover the next 48h under pilot policy"):
            return None
        raise


def transient(error):
    from .gcs_object_store import _http_status, _transport_failure, RemoteObjectStoreError
    status = _http_status(error)
    return (isinstance(error, RemoteObjectStoreError) and error.retryable
            or _transport_failure(error) or status in {408, 429}
            or (status is not None and 500 <= status <= 599))


def result(status, reason, source_run_id=None):
    return {"status": status, "reason": reason, "source_run_id": source_run_id}


class FenceLost(RuntimeError):
    pass


@dataclass(frozen=True)
class Fence:
    record: dict
    etag: str


class Recovery:
    def __init__(self, state, product):
        if product not in {"fvg", "national"}:
            raise ValueError("unknown ICON recovery product")
        self.state, self.product = state, product
        self.prefix = ROOT + product + "/"
        self.key = self.prefix + "active.json"

    def create_record(self, key, record):
        """Reconcile a lost create response with one exact read, never a retry."""
        payload = canonical_json_bytes(record)
        try:
            self.state.put(key, payload, content_type="application/json")
        except PreconditionFailed:
            return self.state.get(key), False
        except (ObjectStoreError, TimeoutError, ConnectionError):
            observed = self.state.get(key)
            if observed.body != payload:
                raise FenceLost("ICON immutable record has another owner") from None
            return observed, True
        observed = self.state.get(key)
        if observed.body != payload:
            raise FenceLost("ICON immutable record changed")
        return observed, True

    def execution_window(self, now, execution):
        """Freeze the first scheduled poll across Cloud Run task retries."""
        key = self.prefix + f"executions/{execution}.json"
        initial = {"schema_version": 1, "product": self.product, "execution": execution, "window": window(now)}
        obj, _created = self.create_record(key, initial)
        saved = json.loads(obj.body)
        if (not isinstance(saved, dict) or set(saved) != set(initial) or canonical_json_bytes(saved) != obj.body
                or saved["schema_version"] != 1 or saved["product"] != self.product or saved["execution"] != execution):
            raise ValueError("invalid ICON execution poll binding")
        info = saved["window"]
        if info is not None:
            if not isinstance(info, dict) or set(info) != {"slot", "poll", "expected_run", "offset_hours"}:
                raise ValueError("invalid ICON execution recovery window")
            try:
                at = datetime.strptime(info["poll"], "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
            except (TypeError, ValueError):
                raise ValueError("invalid ICON execution poll clock") from None
            if at.minute or at.second or at.strftime("%Y%m%dT%H%M%SZ") != info["poll"] or window(at) != info:
                raise ValueError("invalid ICON execution recovery schedule")
        return info

    def active(self):
        try:
            obj = self.state.get(self.key)
        except ObjectNotFound:
            return None
        value = json.loads(obj.body)
        if (not isinstance(value, dict) or canonical_json_bytes(value) != obj.body
                or set(value) != {"schema_version", "product", "phase", "source_run_id", "slot", "execution", "fence"}
                or value["schema_version"] != 1 or value["product"] != self.product
                or value["phase"] not in {"acquiring", "checkpointed", "completed", "manual_review"}
                or not isinstance(value["execution"], str) or not _OWNER.fullmatch(value["execution"])
                or not isinstance(value["slot"], str) or not _SLOT.fullmatch(value["slot"])
                or not isinstance(value["fence"], str) or not re.fullmatch(r"[a-f0-9]{32}", value["fence"])):
            raise ValueError("invalid ICON recovery owner record")
        run_id(value["source_run_id"])
        return Fence(value, obj.etag)

    def replace(self, previous, value):
        payload = canonical_json_bytes(value)
        try:
            self.state.compare_and_swap(self.key, payload,
                expected_etag=previous.etag if previous else None, content_type="application/json")
        except (ObjectStoreError, TimeoutError, ConnectionError):
            observed = self.active()
            if observed is None or observed.record != value:
                raise FenceLost("ICON recovery owner changed") from None
            return observed
        observed = self.active()
        if observed is None or observed.record != value:
            raise FenceLost("ICON recovery owner changed")
        return observed

    def transition(self, fence, phase):
        return self.replace(fence, {**fence.record, "phase": phase})

    def begin(self, previous, cycle, slot, execution, *, checkpointed=False):
        run_id(cycle)
        if previous is not None:
            if previous.record["phase"] != "completed" or cycle <= previous.record["source_run_id"]:
                raise FenceLost("ICON acquisition cannot replace unresolved owner")
        record = {"schema_version": 1, "product": self.product, "phase": "checkpointed" if checkpointed else "acquiring",
                  "source_run_id": cycle, "slot": slot, "execution": execution, "fence": uuid4().hex}
        fence = self.replace(previous, record)
        # Never reuse a cycle's acquisition claim, including after state damage.
        _obj, created = self.create_record(self.prefix + f"runs/{cycle}/acquisition.json", record)
        if not created:
            self.transition(fence, "manual_review")
            raise ValueError("ICON cycle already has an acquisition owner") from None
        return fence

    def probe(self, info, execution, discover, high_water):
        key = self.prefix + "polls/" + info["poll"] + ".json"
        initial = {"schema_version": 1, "product": self.product, "poll": info["poll"],
                   "execution": execution, "fence": uuid4().hex,
                   "status": "in_progress", "reason": "source_probe_in_progress",
                   "source_run_id": None, "attempts": 0}
        obj, created = self.create_record(key, initial)
        if not created:
            saved = json.loads(obj.body)
            if (not isinstance(saved, dict) or set(saved) != set(initial)
                    or canonical_json_bytes(saved) != obj.body or saved["schema_version"] != 1
                    or saved["product"] != self.product or saved["poll"] != info["poll"]
                    or saved["status"] not in {"in_progress", "ready", "pending", "manual_review"}
                    or type(saved["attempts"]) is not int or not 0 <= saved["attempts"] <= MAX_DISCOVERY_ATTEMPTS
                    or not isinstance(saved["reason"], str) or not re.fullmatch(r"[a-z_]{1,80}", saved["reason"])
                    or not isinstance(saved["fence"], str) or not re.fullmatch(r"[a-f0-9]{32}", saved["fence"])
                    or not isinstance(saved["execution"], str) or not _OWNER.fullmatch(saved["execution"])):
                raise ValueError("invalid ICON recovery poll record")
            if saved["source_run_id"] is not None:
                run_id(saved["source_run_id"])
            if (saved["status"] == "ready") != (saved["source_run_id"] is not None):
                raise ValueError("invalid ICON recovery poll cycle")
            return result(saved["status"], saved["reason"], saved["source_run_id"])
        outcome = result("pending", "source_not_advanced")
        for attempt in range(MAX_DISCOVERY_ATTEMPTS):
            try:
                observed = discover(high_water)
                if observed is not None:
                    if not isinstance(observed, str) or not re.fullmatch(r"\d{10}", observed):
                        raise ValueError("invalid ICON discovery cycle")
                    cycle = datetime.strptime(observed, "%Y%m%d%H").strftime("%Y%m%dT%H0000Z")
                    run_id(cycle)
                    if high_water is not None and cycle <= high_water:
                        raise ValueError("ICON discovery attempted regression")
                    outcome = (result("pending", "source_not_advanced") if cycle < info["expected_run"]
                               else result("ready", "source_complete", cycle))
                break
            except Exception as error:
                if not transient(error):
                    outcome = result("manual_review", "source_probe_invalid")
                    break
                outcome = result("pending", "source_transport_pending")
                if attempt + 1 < MAX_DISCOVERY_ATTEMPTS:
                    sleep(1)
        saved = {**initial, **outcome, "attempts": attempt + 1}
        payload = canonical_json_bytes(saved)
        try:
            self.state.compare_and_swap(key, payload, expected_etag=obj.etag, content_type="application/json")
        except (ObjectStoreError, TimeoutError, ConnectionError):
            if self.state.get(key).body != payload:
                raise FenceLost("ICON probe owner changed") from None
        return outcome

    def run(self, *, now, execution, high_water, verified_run, discover,
            checkpoint, acquire, publish, verify, legacy=None):
        """Callbacks validate checkpoint bytes and perform existing publication.

        checkpoint(cycle, slot) must validate complete immutable input, or return
        None. acquire(cycle, slot) freezes and validates it before returning.
        verify(cycle) proves current publication/readback. No callback may delete
        a claim or silently substitute a different source cycle.
        """
        if not isinstance(execution, str) or not _OWNER.fullmatch(execution):
            raise ValueError("ICON recovery requires a durable execution identity")
        if high_water is not None:
            run_id(high_water)
        if verified_run is not None:
            run_id(verified_run)
        window(now)  # Validate the clock even when recovering an existing checkpoint.
        owner = self.active()
        if owner is not None and owner.record["phase"] == "manual_review":
            return result("manual_review", "acquisition_requires_review", owner.record["source_run_id"])
        if owner is not None and owner.record["phase"] in {"acquiring", "checkpointed"}:
            cycle, slot = owner.record["source_run_id"], owner.record["slot"]
            prepared = checkpoint(cycle, slot)  # Before any network source probe.
            if prepared is None:
                return result("in_progress", "acquisition_owner_unresolved", cycle)
            owner = self.replace(owner, {**owner.record, "phase": "checkpointed",
                                         "execution": execution, "fence": uuid4().hex})
            return self.publish(owner, prepared, publish, verify)
        if owner is not None and not verify(owner.record["source_run_id"]):
            return result("manual_review", "completed_publication_not_verified", owner.record["source_run_id"])
        if owner is None and legacy is not None:
            old = legacy()
            if old is not None:
                if old.get("checkpoint") is None:
                    return result("manual_review", "legacy_acquisition_owner_unresolved", old.get("source_run_id"))
                cycle, slot = old["source_run_id"], old["slot"]
                owner = self.begin(owner, cycle, slot, execution, checkpointed=True)
                return self.publish(owner, old["checkpoint"], publish, verify)
        info = self.execution_window(now, execution)
        if info is None:
            return result("pending", "outside_recovery_window")
        if verified_run is not None and verified_run >= info["expected_run"]:
            if not verify(verified_run):
                return result("manual_review", "published_pointer_not_verified", verified_run)
            return result("no_op", "publication_already_verified", verified_run)
        candidate = self.probe(info, execution, discover, high_water)
        if candidate["status"] != "ready":
            return candidate
        cycle = candidate["source_run_id"]
        if utc_run(cycle) > now.astimezone(timezone.utc):
            return result("manual_review", "source_cycle_in_future", cycle)
        owner = self.begin(owner, cycle, info["slot"], execution)
        return self.acquire_and_publish(owner, cycle, info["slot"], checkpoint, acquire, publish, verify)

    def acquire_and_publish(self, owner, cycle, slot, checkpoint, acquire, publish, verify):
        """One acquisition for an immutable claim; never called on a retry."""
        try:
            prepared = acquire(cycle, slot)
            if prepared is None:
                raise ValueError("ICON acquisition did not freeze a checkpoint")
            # Re-read complete durable state, not just the in-process return.
            prepared = checkpoint(cycle, slot)
            if prepared is None:
                raise ValueError("ICON checkpoint is not durable")
            owner = self.transition(owner, "checkpointed")
        except FenceLost:
            raise
        except Exception as error:
            details = error_fields(error)
            details.setdefault("stage", "acquisition")
            emit("icon_recovery_exception", **{**details, "provider": "icon",
                "source_run_id": cycle, "status": "failed", "severity": "ERROR"})
            durable = checkpoint(cycle, slot)
            if durable is not None:
                self.transition(owner, "checkpointed")
                return result("pending", "checkpoint_ready_for_recovery", cycle)
            self.transition(owner, "manual_review")
            return result("manual_review", "acquisition_requires_review", cycle)
        return self.publish(owner, prepared, publish, verify)

    def supersede_manual_review(self, *, now, incident_id, expected_etag,
            expected_owner_sha256, failed_run, new_run, published_run, execution,
            quiescent, current_run, discover, failed_cycle_evidence, checkpoint,
            acquire, publish, verify):
        """Explicit national-only operator handoff; never used by scheduled run.

        The immutable incident is written before replacing the failed owner.
        A new acquisition claim is written after the active-owner CAS and before
        acquisition. If a call dies after the claim, a retry refuses a second
        acquisition; a complete durable checkpoint can still be resumed by the
        ordinary recovery path. Neither old claims nor public pointers are
        deleted or rewritten here.
        """
        if self.product != "national":
            raise ValueError("operator supersession is national-only")
        if (not isinstance(now, datetime) or now.tzinfo is None
                or not isinstance(incident_id, str) or not _INCIDENT.fullmatch(incident_id)
                or not isinstance(expected_etag, str) or not _ETAG.fullmatch(expected_etag)
                or not isinstance(expected_owner_sha256, str) or not _SHA256.fullmatch(expected_owner_sha256)
                or not isinstance(execution, str) or not _OWNER.fullmatch(execution)
                or not re.search(r"(?:^|-)operator(?:-|$)", execution)):
            raise ValueError("invalid ICON operator identity or evidence")
        failed_run, new_run, published_run = (run_id(value) for value in (failed_run, new_run, published_run))
        if (not published_run < failed_run < new_run
                or utc_run(new_run) > now.astimezone(timezone.utc)):
            raise ValueError("ICON operator cycle order is invalid")
        slot = new_run[:8] + ("-am" if new_run[9:11] == "00" else "-pm")
        key = self.prefix + f"incidents/{incident_id}.json"
        try:
            saved_obj = self.state.get(key)
        except ObjectNotFound:
            saved_obj = None

        if saved_obj is None:
            old = self.active()
            if (old is None or old.etag != expected_etag
                    or old.record["phase"] != "manual_review"
                    or old.record["source_run_id"] != failed_run
                    or hashlib.sha256(canonical_json_bytes(old.record)).hexdigest() != expected_owner_sha256):
                raise FenceLost("ICON failed owner differs from operator evidence")
            claim_sha256, guard = self.operator_preflight(old, published_run, new_run,
                now, quiescent, current_run, discover, failed_cycle_evidence, checkpoint, verify)
            owner = {"schema_version": 1, "product": self.product, "phase": "acquiring",
                     "source_run_id": new_run, "slot": slot, "execution": execution, "fence": uuid4().hex}
            incident = {"schema_version": 1, "kind": "icon_manual_review_supersession",
                        "incident_id": incident_id, "product": self.product,
                        "failed_owner": old.record, "failed_owner_etag": expected_etag,
                        "failed_owner_sha256": expected_owner_sha256,
                        "failed_claim_sha256": claim_sha256,
                        "quiescence_at_creation": guard,
                        "published_source_run_id": published_run, "new_owner": owner,
                        "created_at_utc": now.astimezone(timezone.utc).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")}
            saved_obj, _created = self.create_record(key, incident)
        saved = json.loads(saved_obj.body)
        if (not isinstance(saved, dict) or canonical_json_bytes(saved) != saved_obj.body
                or set(saved) != {"schema_version", "kind", "incident_id", "product", "failed_owner",
                                  "failed_owner_etag", "failed_owner_sha256", "failed_claim_sha256",
                                  "quiescence_at_creation",
                                  "published_source_run_id", "new_owner", "created_at_utc"}
                or saved["schema_version"] != 1 or saved["kind"] != "icon_manual_review_supersession"
                or saved["incident_id"] != incident_id or saved["product"] != self.product
                or saved["failed_owner_etag"] != expected_etag
                or saved["failed_owner_sha256"] != expected_owner_sha256
                or saved["failed_owner"]["source_run_id"] != failed_run
                or saved["published_source_run_id"] != published_run
                or saved["new_owner"]["source_run_id"] != new_run
                or saved["new_owner"]["execution"] != execution
                or saved["new_owner"]["slot"] != slot
                or saved["new_owner"]["phase"] != "acquiring"
                or saved["new_owner"]["fence"] == saved["failed_owner"]["fence"]
                or not isinstance(saved["failed_claim_sha256"], str)
                or not _SHA256.fullmatch(saved["failed_claim_sha256"])
                or not isinstance(saved["quiescence_at_creation"], dict)
                or set(saved["quiescence_at_creation"]) != {"scheduler_paused", "active_executions",
                    "deployed_fence_aware", "legacy_invocations_blocked", "observed_at_utc",
                    "evidence_sha256"}):
            raise ValueError("invalid ICON operator incident record")
        owner = self.active()
        old_record, new_record = saved["failed_owner"], saved["new_owner"]
        if (hashlib.sha256(canonical_json_bytes(old_record)).hexdigest() != expected_owner_sha256
                or set(new_record) != set(old_record)
                or new_record["product"] != self.product
                or not _INCIDENT.fullmatch(new_record["fence"])):
            raise ValueError("ICON operator incident owner differs")
        if owner is not None and owner.record == old_record and owner.etag == expected_etag:
            claim_sha256, _guard = self.operator_preflight(owner, published_run, new_run,
                now, quiescent, current_run, discover, failed_cycle_evidence, checkpoint, verify)
            if claim_sha256 != saved["failed_claim_sha256"]:
                raise FenceLost("ICON failed acquisition claim changed")
            owner = self.replace(owner, new_record)
        elif owner is None or owner.record.get("source_run_id") != new_run or owner.record.get("fence") != new_record["fence"]:
            raise FenceLost("ICON operator incident lost active owner")
        elif owner.record != new_record:
            if owner.record == {**new_record, "phase": "manual_review"}:
                return result("manual_review", "operator_new_cycle_requires_review", new_run)
            if owner.record == {**new_record, "phase": "completed"}:
                if current_run() != new_run or verify(new_run) is not True:
                    raise FenceLost("ICON completed operator publication is not verified")
                return result("no_op", "operator_publication_already_completed", new_run)
            if owner.record == {**new_record, "phase": "checkpointed"}:
                self.operator_guard(quiescent, now)
                prepared = checkpoint(new_run, slot)
                if prepared is None:
                    raise FenceLost("ICON operator checkpoint disappeared")
                pointer_run = current_run()
                if pointer_run == new_run and verify(new_run) is True:
                    self.transition(owner, "completed")
                    return result("no_op", "operator_publication_reconciled", new_run)
                if pointer_run == published_run and verify(published_run) is True:
                    return self.publish(owner, prepared, publish, verify)
                raise FenceLost("ICON operator public pointer changed")
            raise FenceLost("ICON operator owner changed unexpectedly")

        self.operator_guard(quiescent, now)
        if current_run() != published_run or verify(published_run) is not True:
            raise FenceLost("ICON operator publication or quiescence changed")
        claim_key = self.prefix + f"runs/{new_run}/acquisition.json"
        _claim, created = self.create_record(claim_key, new_record)
        if _claim.body != canonical_json_bytes(new_record):
            raise FenceLost("ICON operator cycle already has another owner")
        if not created:
            prepared = checkpoint(new_run, slot)
            if prepared is None:
                return result("in_progress", "operator_acquisition_owner_unresolved", new_run)
            owner = self.transition(owner, "checkpointed")
            return self.publish(owner, prepared, publish, verify)
        return self.acquire_and_publish(owner, new_run, slot, checkpoint, acquire, publish, verify)

    def operator_guard(self, quiescent, now):
        """Require a live maintenance attestation, not a zero-executions snapshot."""
        if not callable(quiescent):
            raise FenceLost("ICON operator quiescence check missing")
        guard = quiescent()
        if (not isinstance(guard, dict)
                or set(guard) != {"scheduler_paused", "active_executions",
                    "deployed_fence_aware", "legacy_invocations_blocked", "observed_at_utc",
                    "evidence_sha256"}
                or guard["scheduler_paused"] is not True
                or type(guard["active_executions"]) is not int or guard["active_executions"] != 0
                or guard["deployed_fence_aware"] is not True
                or guard["legacy_invocations_blocked"] is not True
                or not isinstance(guard["observed_at_utc"], str)
                or not isinstance(guard["evidence_sha256"], str)
                or not _SHA256.fullmatch(guard["evidence_sha256"])):
            raise FenceLost("ICON operator maintenance guard is incomplete")
        try:
            observed = datetime.strptime(guard["observed_at_utc"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        except ValueError:
            raise FenceLost("ICON operator maintenance guard timestamp is invalid") from None
        if not 0 <= (now.astimezone(timezone.utc) - observed).total_seconds() <= 60:
            raise FenceLost("ICON operator maintenance guard is stale")
        return guard

    def operator_preflight(self, old, published_run, new_run, now, quiescent,
            current_run, discover, failed_cycle_evidence, checkpoint, verify):
        """Read-only checks before a manual-review CAS or its exact retry."""
        guard = self.operator_guard(quiescent, now)
        if current_run() != published_run or verify(published_run) is not True:
            raise FenceLost("ICON operator preflight is not quiescent or published")
        old_run, old_slot = old.record["source_run_id"], old.record["slot"]
        claim_obj = self.state.get(self.prefix + f"runs/{old_run}/acquisition.json")
        expected_claim = {**old.record, "phase": "acquiring"}
        if (claim_obj.body != canonical_json_bytes(expected_claim)
                or checkpoint(old_run, old_slot) is not None
                or failed_cycle_evidence(old_run) != {"intent": True, "mapping": False,
                                                       "prepared": False, "manifest": False}):
            raise ValueError("ICON failed cycle evidence is incomplete")
        candidate = discover(published_run)
        if (not isinstance(candidate, str) or not re.fullmatch(r"\d{10}", candidate)
                or datetime.strptime(candidate, "%Y%m%d%H").strftime("%Y%m%dT%H0000Z") != new_run):
            raise ValueError("ICON operator source discovery differs")
        try:
            self.state.get(self.prefix + f"runs/{new_run}/acquisition.json")
        except ObjectNotFound:
            pass
        else:
            raise FenceLost("ICON new cycle already has an acquisition claim")
        return hashlib.sha256(claim_obj.body).hexdigest(), guard

    def publish(self, owner, prepared, publish, verify):
        if self.active() != owner:
            raise FenceLost("ICON publication owner changed")
        cycle = owner.record["source_run_id"]
        try:
            outcome = publish(prepared)
        except Exception as error:
            details = error_fields(error)
            details.setdefault("stage", "publication")
            emit("icon_recovery_exception", **{**details, "provider": "icon",
                "source_run_id": cycle, "status": "failed", "severity": "ERROR"})
            if transient(error):
                return result("pending", "checkpoint_publication_pending", cycle)
            self.transition(owner, "manual_review")
            return result("manual_review", "checkpoint_publication_invalid", cycle)
        if outcome.get("status") not in {"published", "no_op"}:
            if outcome.get("status") == "manual_review":
                self.transition(owner, "manual_review")
            return outcome
        if outcome.get("source_run_id") != cycle or not verify(cycle):
            self.transition(owner, "manual_review")
            return result("manual_review", "publication_readback_failed", cycle)
        self.transition(owner, "completed")
        return outcome


def utc_run(cycle):
    return datetime.strptime(run_id(cycle), "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
