from __future__ import annotations

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.api.editorial import get_editorial_service
from app.infrastructure.editorial_admin_auth import EditorialAdminContext, require_editorial_admin
from app.main import create_app
from app.services.editorial import (
    EditorialError,
    EditorialService,
    apply_operation,
    initial_state,
    public_snapshot,
)


NOW = datetime(2026, 11, 8, 9, 0, tzinfo=timezone.utc)
CONTENT = {
    "type": "message", "title": "Una novità", "message": "Testo confermato",
    "enabled": True, "start": "2026-11-08T09:00", "end": "2026-11-09T09:00",
}


def change(state, action, draft_id="draft_123", content=None):
    return apply_operation(state, action=action, draft_id=draft_id, content=content, now=NOW)


def test_save_confirm_publish_are_distinct_and_public_reads_only_published_content():
    draft = change(initial_state(), "save", content=CONTENT)
    assert public_snapshot(draft, NOW)["item"] is None
    confirmed = change(draft, "confirm")
    assert confirmed["drafts"][0]["confirmedHash"]
    assert public_snapshot(confirmed, NOW)["item"] is None
    published = change(confirmed, "publish")
    assert public_snapshot(published, NOW)["item"]["message"] == "Testo confermato"
    assert public_snapshot(published, datetime(2026, 11, 9, 9, tzinfo=timezone.utc))["item"] is None

    edited = change(published, "save", content={**CONTENT, "message": "Bozza successiva"})
    assert edited["drafts"][0]["confirmedHash"] is None
    assert public_snapshot(edited, NOW)["item"]["message"] == "Testo confermato"
    with pytest.raises(EditorialError, match="editorial_confirmation_required"):
        change(edited, "publish")


def test_schedule_validation_rejects_ambiguous_clock_and_overlapping_publications():
    ambiguous = change(initial_state(), "save", content={**CONTENT, "start": "2026-10-25T02:30"})
    with pytest.raises(EditorialError, match="editorial_time_invalid"):
        change(ambiguous, "confirm")
    first = change(change(change(initial_state(), "save", content=CONTENT), "confirm"), "publish")
    second = change(first, "save", "draft_456", {**CONTENT, "title": "Secondo"})
    second = change(second, "confirm", "draft_456")
    with pytest.raises(EditorialError, match="editorial_period_overlap"):
        change(second, "publish", "draft_456")


def test_invalid_type_cannot_cause_server_error():
    with pytest.raises(EditorialError, match="editorial_content_invalid"):
        change(initial_state(), "save", content={**CONTENT, "type": ["message"]})


def test_editorial_permission_is_checked_separately_from_login(monkeypatch):
    import firebase_admin.auth as firebase_auth
    import app.infrastructure.editorial_admin_auth as editorial_auth

    monkeypatch.setattr(editorial_auth, "get_firebase_app", lambda: object())
    monkeypatch.setattr(firebase_auth, "verify_id_token", lambda *_args, **_kwargs: {"uid": "owner", "adsAdmin": True})
    with pytest.raises(HTTPException) as missing_role:
        require_editorial_admin("Bearer firebase-token")
    assert missing_role.value.status_code == 403
    monkeypatch.setattr(firebase_auth, "verify_id_token", lambda *_args, **_kwargs: {"uid": "owner", "editorialAdmin": True})
    assert require_editorial_admin("Bearer firebase-token").uid == "owner"


def test_publication_must_be_withdrawn_before_deleting_its_draft():
    published = change(change(change(initial_state(), "save", content=CONTENT), "confirm"), "publish")
    with pytest.raises(EditorialError, match="editorial_unpublish_required"):
        change(published, "delete")
    withdrawn = change(published, "unpublish")
    assert public_snapshot(withdrawn, NOW)["item"] is None
    deleted = change(withdrawn, "delete")
    assert deleted["drafts"] == []


def test_future_edit_cannot_silently_remove_current_publication():
    published = change(change(change(initial_state(), "save", content=CONTENT), "confirm"), "publish")
    future = {**CONTENT, "message": "Nuova versione", "start": "2026-11-08T12:00"}
    edited = change(change(published, "save", content=future), "confirm")
    with pytest.raises(EditorialError, match="editorial_future_replacement_requires_new_draft"):
        change(edited, "publish")
    assert public_snapshot(edited, NOW)["item"]["message"] == "Testo confermato"


def test_publication_switch_stays_closed_until_release_is_authorized():
    class MemoryRepository:
        def __init__(self, state):
            self.value = state

        def read(self):
            return self.value

        def mutate(self, **kwargs):
            self.value = apply_operation(self.value, action=kwargs["action"], draft_id=kwargs["draft_id"],
                                         content=kwargs["content"], now=kwargs["now"])
            return self.value

    confirmed = change(change(initial_state(), "save", content=CONTENT), "confirm")
    service = EditorialService(MemoryRepository(confirmed), publication_enabled=False)
    assert service.state()["publicationEnabled"] is False
    with pytest.raises(EditorialError, match="editorial_publication_disabled"):
        service.mutate(expected_revision=2, operation_id="operation_123", action="publish",
                       draft_id="draft_123", content=None, actor="owner")
    assert service.public(now=NOW)["item"] is None


def test_api_requires_login_and_separates_all_three_requests():
    class MemoryRepository:
        value = initial_state()

        def read(self):
            return self.value

        def mutate(self, **kwargs):
            if kwargs["expected_revision"] != self.value["revision"]:
                raise EditorialError("editorial_revision_conflict", 409)
            self.value = apply_operation(self.value, action=kwargs["action"], draft_id=kwargs["draft_id"],
                                         content=kwargs["content"], now=kwargs["now"])
            return self.value

    app = create_app()
    service = EditorialService(MemoryRepository(), publication_enabled=True)
    app.dependency_overrides[get_editorial_service] = lambda: service
    client = TestClient(app)
    assert client.get("/api/admin/editorial/home-advice/state").status_code == 401
    app.dependency_overrides[require_editorial_admin] = lambda: EditorialAdminContext("owner")
    base = "/api/admin/editorial/home-advice/drafts/draft_123"
    current = datetime.now(timezone.utc)
    rome = ZoneInfo("Europe/Rome")
    api_content = {**CONTENT,
        "start": (current - timedelta(hours=1)).astimezone(rome).strftime("%Y-%m-%dT%H:%M"),
        "end": (current + timedelta(days=1)).astimezone(rome).strftime("%Y-%m-%dT%H:%M")}
    saved = client.put(base, json={"expectedRevision": 0, "operationId": "operation_123", "content": api_content})
    assert saved.status_code == 200
    assert client.get("/api/editorial/home-advice").json()["item"] is None
    confirmed = client.post(base + "/confirm", json={"expectedRevision": 1, "operationId": "operation_456"})
    assert confirmed.status_code == 200
    assert client.get("/api/editorial/home-advice").json()["item"] is None
    published = client.post(base + "/publish", json={"expectedRevision": 2, "operationId": "operation_789"})
    assert published.status_code == 200
    assert client.get("/api/editorial/home-advice").json()["item"]["title"] == "Una novità"
