"""Private three-step workflow and public read-only Home advice."""
from __future__ import annotations

from functools import lru_cache
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, ConfigDict, Field

from app.infrastructure.editorial_admin_auth import EditorialAdminContext, require_editorial_admin
from app.infrastructure.firebase import get_firestore_client
from app.services.editorial import EditorialError, EditorialRepository, EditorialService


public_router = APIRouter(prefix="/api/editorial", tags=["editorial"])
admin_router = APIRouter(prefix="/api/admin/editorial", tags=["editorial-admin"])


class Operation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expectedRevision: int = Field(ge=0, strict=True)
    operationId: str = Field(min_length=8, max_length=120)


class SaveDraft(Operation):
    content: dict[str, Any]


@lru_cache(maxsize=1)
def get_editorial_service() -> EditorialService:
    return EditorialService(EditorialRepository(get_firestore_client))


def _error(error: EditorialError) -> HTTPException:
    return HTTPException(error.status, detail=error.detail)


@public_router.get("/home-advice")
def public_home_advice(response: Response,
                       service: Annotated[EditorialService, Depends(get_editorial_service)]):
    response.headers["Cache-Control"] = "public, max-age=30, must-revalidate"
    try:
        return service.public()
    except EditorialError as error:
        raise _error(error) from error


@admin_router.get("/home-advice/state")
def admin_state(response: Response,
                _admin: Annotated[EditorialAdminContext, Depends(require_editorial_admin)],
                service: Annotated[EditorialService, Depends(get_editorial_service)]):
    response.headers["Cache-Control"] = "no-store"
    try:
        return service.state()
    except EditorialError as error:
        raise _error(error) from error


@admin_router.put("/home-advice/drafts/{draft_id}")
def save_draft(draft_id: str, command: SaveDraft, response: Response,
               admin: Annotated[EditorialAdminContext, Depends(require_editorial_admin)],
               service: Annotated[EditorialService, Depends(get_editorial_service)]):
    response.headers["Cache-Control"] = "no-store"
    try:
        return service.mutate(expected_revision=command.expectedRevision, operation_id=command.operationId,
                              action="save", draft_id=draft_id, content=command.content, actor=admin.uid)
    except EditorialError as error:
        raise _error(error) from error


@admin_router.post("/home-advice/drafts/{draft_id}/confirm")
def confirm_draft(draft_id: str, command: Operation, response: Response,
                  admin: Annotated[EditorialAdminContext, Depends(require_editorial_admin)],
                  service: Annotated[EditorialService, Depends(get_editorial_service)]):
    response.headers["Cache-Control"] = "no-store"
    try:
        return service.mutate(expected_revision=command.expectedRevision, operation_id=command.operationId,
                              action="confirm", draft_id=draft_id, content=None, actor=admin.uid)
    except EditorialError as error:
        raise _error(error) from error


@admin_router.post("/home-advice/drafts/{draft_id}/publish")
def publish_draft(draft_id: str, command: Operation, response: Response,
                  admin: Annotated[EditorialAdminContext, Depends(require_editorial_admin)],
                  service: Annotated[EditorialService, Depends(get_editorial_service)]):
    response.headers["Cache-Control"] = "no-store"
    try:
        return service.mutate(expected_revision=command.expectedRevision, operation_id=command.operationId,
                              action="publish", draft_id=draft_id, content=None, actor=admin.uid)
    except EditorialError as error:
        raise _error(error) from error


@admin_router.post("/home-advice/drafts/{draft_id}/unpublish")
def unpublish_draft(draft_id: str, command: Operation, response: Response,
                    admin: Annotated[EditorialAdminContext, Depends(require_editorial_admin)],
                    service: Annotated[EditorialService, Depends(get_editorial_service)]):
    response.headers["Cache-Control"] = "no-store"
    try:
        return service.mutate(expected_revision=command.expectedRevision, operation_id=command.operationId,
                              action="unpublish", draft_id=draft_id, content=None, actor=admin.uid)
    except EditorialError as error:
        raise _error(error) from error


@admin_router.delete("/home-advice/drafts/{draft_id}")
def delete_draft(draft_id: str, command: Operation, response: Response,
                 admin: Annotated[EditorialAdminContext, Depends(require_editorial_admin)],
                 service: Annotated[EditorialService, Depends(get_editorial_service)]):
    response.headers["Cache-Control"] = "no-store"
    try:
        return service.mutate(expected_revision=command.expectedRevision, operation_id=command.operationId,
                              action="delete", draft_id=draft_id, content=None, actor=admin.uid)
    except EditorialError as error:
        raise _error(error) from error
