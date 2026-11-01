from __future__ import annotations

import copy
import hashlib
import re
from datetime import date

from .model import MarketError, audit_changes, build_catalogue, encode, publication_errors, timestamp, validate_state
from .review import reminder, review_queue
from .email_reminder import email_address, public_settings


class MarketsService:
    def __init__(self, repository):
        self.repository = repository

    def _admin(self, record, *, replay=False):
        return {**copy.deepcopy(record["state"]), "revision": record["revision"],
                "publishedRevision": record["publishedRevision"], "audit": copy.deepcopy(record["audit"]),
                "publishedAt": record["catalogue"]["publishedAt"], "storage": self.repository.storage,
                "idempotentReplay": replay, "publicationErrors": publication_errors(record["state"], record["catalogue"]),
                "reviewReminder": {**reminder(record), "items": review_queue(record)},
                "emailReminder": public_settings(record, self.repository),
                **({"automation": copy.deepcopy(record["automation"])} if "automation" in record else {})}

    def state(self):
        return self._admin(self.repository.read())

    def catalogue(self):
        return copy.deepcopy(self.repository.read()["catalogue"])

    def history(self):
        record = self.repository.read()
        return {"revision": record["revision"], "publishedRevision": record["publishedRevision"], "audit": record["audit"]}

    def mutate(self, *, action, expected_revision, operation_id, reason, actor, state=None):
        if type(expected_revision) is not int or expected_revision < 0:
            raise MarketError("markets_expected_revision_required")
        if not isinstance(operation_id, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:-]{7,119}", operation_id):
            raise MarketError("markets_operation_id_required")
        if not isinstance(reason, str) or not 3 <= len(reason.strip()) <= 1000:
            raise MarketError("markets_change_reason_required")
        if action not in {"save", "publish"}:
            raise MarketError("markets_invalid_action")
        request_hash = hashlib.sha256(encode({"action": action, "expectedRevision": expected_revision,
                                              "reason": reason, "state": state, "actor": actor})).hexdigest()

        def change(current):
            result = copy.deepcopy(current)
            revision = current["revision"] + 1
            now = timestamp()
            changes = []
            if action == "save":
                result["state"] = validate_state(state, current["state"])
                # Parser identity bindings are server-owned, just like the
                # refresh ledger stored outside the editable state payload.
                old_dates = {item["id"]: item for item in current["state"]["dates"]}
                for edition in result["state"]["dates"]:
                    edition.pop("refreshSourceKeys", None)
                    previous_keys = old_dates.get(edition["id"], {}).get("refreshSourceKeys")
                    if previous_keys:
                        edition["refreshSourceKeys"] = copy.deepcopy(previous_keys)
                changes = audit_changes(current["state"], result["state"])
            else:
                errors = publication_errors(current["state"], current["catalogue"])
                if errors:
                    raise MarketError("markets_publication_checks_required", checks=errors)
                result["catalogue"] = build_catalogue(current["state"], revision=revision, now=now, previous=current["catalogue"])
                result["publishedRevision"] = revision
            result["revision"] = revision
            result["audit"].append({"revision": revision, "action": action, "at": now, "actor": actor,
                                    "reason": reason.strip(), "changes": changes})
            return result

        record, replay = self.repository.mutate(expected_revision=expected_revision, operation_id=operation_id,
                                               request_hash=request_hash, change=change)
        return self._admin(record, replay=replay)

    def refresh(self, results, *, expected_revision, operation_id, as_of):
        """Internal job boundary; never exposed as an unauthenticated HTTP write."""
        from .refresh import apply_refresh

        if type(expected_revision) is not int or expected_revision < 0:
            raise MarketError("markets_expected_revision_required")
        if not isinstance(operation_id, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:-]{7,119}", operation_id):
            raise MarketError("markets_operation_id_required")
        if type(as_of) is not date or not isinstance(results, list) or not 1 <= len(results) <= 2000:
            raise MarketError("markets_refresh_input_invalid")
        request_hash = hashlib.sha256(encode({"action": "refresh", "expectedRevision": expected_revision,
                                              "asOf": as_of.isoformat(), "results": results})).hexdigest()

        def change(current):
            return apply_refresh(current, results, as_of=as_of, now=timestamp())

        record, replay = self.repository.mutate(expected_revision=expected_revision, operation_id=operation_id,
                                               request_hash=request_hash, change=change)
        return self._admin(record, replay=replay)

    def complete_review(self, *, expected_revision, operation_id, period, reason, actor):
        if type(expected_revision) is not int or expected_revision < 0:
            raise MarketError("markets_expected_revision_required")
        if not isinstance(operation_id, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:-]{7,119}", operation_id):
            raise MarketError("markets_operation_id_required")
        if not isinstance(period, str) or not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", period):
            raise MarketError("markets_review_period_required")
        if not isinstance(reason, str) or not 3 <= len(reason.strip()) <= 1000:
            raise MarketError("markets_change_reason_required")
        request_hash = hashlib.sha256(encode({"action": "review", "expectedRevision": expected_revision,
                                              "period": period, "reason": reason, "actor": actor})).hexdigest()

        def change(current):
            scheduled = reminder(current)
            if not scheduled["due"] or period != scheduled["period"]:
                raise MarketError("markets_review_not_due", status=409)
            result = copy.deepcopy(current)
            now = timestamp()
            result["manualReview"] = {"completedPeriod": period, "completedAt": now,
                                      "kind": scheduled["kind"], "note": reason.strip()}
            result["revision"] = current["revision"] + 1
            result["audit"].append({"revision": result["revision"], "action": "review", "at": now,
                                    "actor": actor, "period": period, "kind": scheduled["kind"],
                                    "reason": reason.strip(), "changes": []})
            return result

        record, replay = self.repository.mutate(expected_revision=expected_revision, operation_id=operation_id,
                                               request_hash=request_hash, change=change)
        return self._admin(record, replay=replay)

    def configure_email(self, *, expected_revision, operation_id, recipient, enabled, actor):
        recipient = email_address(recipient)
        if type(expected_revision) is not int or expected_revision < 0 or type(enabled) is not bool:
            raise MarketError("markets_email_settings_invalid")
        if not isinstance(operation_id, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:-]{7,119}", operation_id):
            raise MarketError("markets_operation_id_required")
        request_hash = hashlib.sha256(encode({"action": "email-settings", "expectedRevision": expected_revision,
                                              "recipient": recipient, "enabled": enabled, "actor": actor})).hexdigest()

        def change(current):
            result = copy.deepcopy(current)
            result["emailReminder"] = {**result.get("emailReminder", {}), "recipient": recipient, "enabled": enabled}
            result["revision"] += 1
            result["audit"].append({"revision": result["revision"], "action": "email-settings", "at": timestamp(),
                                    "actor": actor, "reason": "Impostazioni promemoria email aggiornate", "changes": []})
            return result

        record, replay = self.repository.mutate(expected_revision=expected_revision, operation_id=operation_id,
                                               request_hash=request_hash, change=change)
        return self._admin(record, replay=replay)
