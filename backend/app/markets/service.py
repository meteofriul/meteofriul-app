from __future__ import annotations

import copy
import hashlib
import re

from .model import MarketError, audit_changes, build_catalogue, encode, publication_errors, timestamp, validate_state


class MarketsService:
    def __init__(self, repository):
        self.repository = repository

    def _admin(self, record, *, replay=False):
        return {**copy.deepcopy(record["state"]), "revision": record["revision"],
                "publishedRevision": record["publishedRevision"], "audit": copy.deepcopy(record["audit"]),
                "publishedAt": record["catalogue"]["publishedAt"], "storage": self.repository.storage,
                "idempotentReplay": replay, "publicationErrors": publication_errors(record["state"], record["catalogue"])}

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
