"""Revision-bound editorial drafts and publication for the Home advice slot."""
from __future__ import annotations

import copy
import hashlib
import json
import os
import re
from datetime import datetime, timezone
from typing import Any, Callable
from zoneinfo import ZoneInfo


ROME = ZoneInfo("Europe/Rome")
COLLECTION = "editorial_publication_state"
DOCUMENT = "home_advice"
TYPES = frozenset({"advice", "news", "message"})
MAX_DRAFTS = 100
MAX_OPERATIONS = 100
ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{8,120}$")


class EditorialError(Exception):
    def __init__(self, code: str, status: int = 422, **detail: Any):
        super().__init__(code)
        self.status = status
        self.detail = {"code": code, **detail}


def initial_state() -> dict[str, Any]:
    return {"revision": 0, "drafts": [], "publications": [], "operations": []}


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()


def _rome_instant(value: str) -> datetime:
    try:
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}", value):
            raise ValueError("format")
        wall = datetime.fromisoformat(value)
        matches = set()
        for fold in (0, 1):
            candidate = wall.replace(tzinfo=ROME, fold=fold).astimezone(timezone.utc)
            if candidate.astimezone(ROME).replace(tzinfo=None) == wall:
                matches.add(candidate)
        if len(matches) != 1:
            raise ValueError("ambiguous_or_missing")
        return matches.pop()
    except (TypeError, ValueError) as error:
        raise EditorialError("editorial_time_invalid") from error


def normalize_content(content: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(content, dict) or set(content) != {"type", "title", "message", "enabled", "start", "end"}:
        raise EditorialError("editorial_content_invalid")
    if not isinstance(content["type"], str) or content["type"] not in TYPES or not isinstance(content["enabled"], bool):
        raise EditorialError("editorial_content_invalid")
    for field, limit in (("title", 80), ("message", 400), ("start", 16), ("end", 16)):
        if not isinstance(content[field], str) or len(content[field]) > limit:
            raise EditorialError("editorial_content_invalid", field=field)
    return {field: content[field] for field in ("type", "title", "message", "enabled", "start", "end")}


def publication_window(content: dict[str, Any]) -> tuple[datetime, datetime]:
    if not content["enabled"] or not content["title"].strip() or not content["message"].strip():
        raise EditorialError("editorial_content_incomplete")
    start, end = _rome_instant(content["start"]), _rome_instant(content["end"])
    if end <= start:
        raise EditorialError("editorial_period_invalid")
    return start, end


def apply_operation(state: dict[str, Any], *, action: str, draft_id: str,
                    content: dict[str, Any] | None, now: datetime) -> dict[str, Any]:
    if not ID_PATTERN.fullmatch(draft_id):
        raise EditorialError("editorial_id_invalid")
    next_state = copy.deepcopy(state)
    drafts = next_state["drafts"]
    existing = next((item for item in drafts if item["id"] == draft_id), None)
    if action == "save":
        normalized = normalize_content(content)
        if existing is None:
            if len(drafts) >= MAX_DRAFTS:
                raise EditorialError("editorial_draft_limit", 409)
            existing = {"id": draft_id}
            drafts.append(existing)
        existing.update(content=normalized, confirmedHash=None, confirmedAt=None,
                        savedAt=_iso(now))
    elif action == "confirm":
        if existing is None:
            raise EditorialError("editorial_draft_missing", 404)
        publication_window(existing["content"])
        existing["confirmedHash"] = _digest(existing["content"])
        existing["confirmedAt"] = _iso(now)
    elif action == "publish":
        if existing is None:
            raise EditorialError("editorial_draft_missing", 404)
        if not existing.get("confirmedHash") or existing["confirmedHash"] != _digest(existing["content"]):
            raise EditorialError("editorial_confirmation_required", 409)
        start, end = publication_window(existing["content"])
        if end <= now:
            raise EditorialError("editorial_period_expired", 409)
        previous_version = next((item for item in next_state["publications"] if item["id"] == draft_id), None)
        if previous_version:
            previous_start = datetime.fromisoformat(previous_version["startAt"].replace("Z", "+00:00"))
            previous_end = datetime.fromisoformat(previous_version["endAt"].replace("Z", "+00:00"))
            if previous_start <= now < previous_end and start > now:
                raise EditorialError("editorial_future_replacement_requires_new_draft", 409)
        for item in next_state["publications"]:
            if item["id"] != draft_id and start < datetime.fromisoformat(item["endAt"].replace("Z", "+00:00")) and end > datetime.fromisoformat(item["startAt"].replace("Z", "+00:00")):
                raise EditorialError("editorial_period_overlap", 409, conflictingId=item["id"])
        next_state["publications"] = [item for item in next_state["publications"] if item["id"] != draft_id]
        next_state["publications"].append({"id": draft_id, "content": copy.deepcopy(existing["content"]),
                                           "startAt": _iso(start), "endAt": _iso(end), "publishedAt": _iso(now)})
    elif action == "unpublish":
        if not any(item["id"] == draft_id for item in next_state["publications"]):
            raise EditorialError("editorial_publication_missing", 404)
        next_state["publications"] = [item for item in next_state["publications"] if item["id"] != draft_id]
    elif action == "delete":
        if existing is None:
            raise EditorialError("editorial_draft_missing", 404)
        if any(item["id"] == draft_id for item in next_state["publications"]):
            raise EditorialError("editorial_unpublish_required", 409)
        next_state["drafts"] = [item for item in drafts if item["id"] != draft_id]
    else:
        raise EditorialError("editorial_action_invalid")
    next_state["revision"] = state["revision"] + 1
    return next_state


def public_snapshot(state: dict[str, Any], now: datetime) -> dict[str, Any]:
    current = None
    next_change = None
    for item in state["publications"]:
        start = datetime.fromisoformat(item["startAt"].replace("Z", "+00:00"))
        end = datetime.fromisoformat(item["endAt"].replace("Z", "+00:00"))
        if start <= now < end:
            current = item
            next_change = end if next_change is None else min(next_change, end)
        elif start > now:
            next_change = start if next_change is None else min(next_change, start)
    return {"schemaVersion": 1, "revision": state["revision"],
            "item": {"id": current["id"], **current["content"], "startAt": current["startAt"], "endAt": current["endAt"]} if current else None,
            "nextChangeAt": _iso(next_change) if next_change else None}


class EditorialRepository:
    def __init__(self, client_provider: Callable[[], Any]):
        self._client_provider = client_provider

    def _document(self):
        try:
            client = self._client_provider()
            if client is None:
                raise EditorialError("editorial_storage_unavailable", 503)
            return client.collection(COLLECTION).document(DOCUMENT), client
        except EditorialError:
            raise
        except Exception as error:
            raise EditorialError("editorial_storage_unavailable", 503) from error

    def read(self) -> dict[str, Any]:
        document, _ = self._document()
        try:
            snapshot = document.get()
            return copy.deepcopy(snapshot.to_dict()) if snapshot.exists else initial_state()
        except Exception as error:
            raise EditorialError("editorial_storage_unavailable", 503) from error

    def mutate(self, *, expected_revision: int, operation_id: str, action: str, draft_id: str,
               content: dict[str, Any] | None, actor: str, now: datetime) -> dict[str, Any]:
        if not ID_PATTERN.fullmatch(operation_id):
            raise EditorialError("editorial_operation_id_invalid")
        document, client = self._document()
        request_hash = _digest({"action": action, "draftId": draft_id, "content": content})
        try:
            from google.cloud import firestore

            @firestore.transactional
            def write(transaction):
                snapshot = document.get(transaction=transaction)
                state = copy.deepcopy(snapshot.to_dict()) if snapshot.exists else initial_state()
                previous = next((item for item in state["operations"] if item["id"] == operation_id), None)
                if previous:
                    if previous["requestHash"] != request_hash:
                        raise EditorialError("editorial_operation_conflict", 409)
                    return state
                if state["revision"] != expected_revision:
                    raise EditorialError("editorial_revision_conflict", 409, currentRevision=state["revision"])
                updated = apply_operation(state, action=action, draft_id=draft_id, content=content, now=now)
                updated["operations"] = (updated["operations"] + [{"id": operation_id,
                    "requestHash": request_hash, "action": action, "draftId": draft_id,
                    "actor": actor, "at": _iso(now)}])[-MAX_OPERATIONS:]
                transaction.set(document, updated)
                return updated

            return write(client.transaction())
        except EditorialError:
            raise
        except Exception as error:
            raise EditorialError("editorial_storage_unavailable", 503) from error


class EditorialService:
    def __init__(self, repository: EditorialRepository, *, publication_enabled: bool | None = None):
        self.repository = repository
        self.publication_enabled = (os.getenv("EDITORIAL_PUBLICATION_ENABLED", "false").lower() == "true"
                                    if publication_enabled is None else publication_enabled)

    def state(self) -> dict[str, Any]:
        return {**self.repository.read(), "publicationEnabled": self.publication_enabled}

    def public(self, *, now: datetime | None = None) -> dict[str, Any]:
        state = self.repository.read()
        if not self.publication_enabled:
            state = {**state, "publications": []}
        return public_snapshot(state, now or datetime.now(timezone.utc))

    def mutate(self, *, expected_revision: int, operation_id: str, action: str, draft_id: str,
               content: dict[str, Any] | None, actor: str) -> dict[str, Any]:
        if action == "publish" and not self.publication_enabled:
            raise EditorialError("editorial_publication_disabled", 409)
        state = self.repository.mutate(expected_revision=expected_revision, operation_id=operation_id,
                                       action=action, draft_id=draft_id, content=content, actor=actor,
                                       now=datetime.now(timezone.utc))
        return {**state, "publicationEnabled": self.publication_enabled}
