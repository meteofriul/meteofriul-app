from __future__ import annotations

from functools import lru_cache
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, Field

from app.infrastructure.markets_admin_auth import MarketsAdminContext, require_markets_admin
from app.markets.model import MarketError
from app.markets.repository import configured_repository
from app.markets.service import MarketsService


public_router = APIRouter(prefix="/api/markets", tags=["markets"])
admin_router = APIRouter(prefix="/api/admin/markets", tags=["markets-admin"])


class MarketOperation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expectedRevision: int = Field(ge=0, strict=True)
    operationId: str = Field(min_length=8, max_length=120)
    reason: str = Field(min_length=3, max_length=1000)


class MarketStateUpdate(MarketOperation):
    state: dict[str, Any]


def _http_error(error):
    return HTTPException(status_code=error.status, detail=error.detail)


@lru_cache(maxsize=1)
def get_markets_service() -> MarketsService:
    try:
        return MarketsService(configured_repository())
    except MarketError as error:
        raise _http_error(error) from error


@public_router.get("/catalogue")
def catalogue(request: Request, response: Response, service: Annotated[MarketsService, Depends(get_markets_service)]):
    try:
        payload = service.catalogue()
    except MarketError as error:
        raise _http_error(error) from error
    etag = '"' + payload["snapshotId"] + '"'
    headers = {"Cache-Control": "public, max-age=60, must-revalidate", "ETag": etag}
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304, headers=headers)
    response.headers.update(headers)
    return payload


@admin_router.get("/state")
def state(response: Response, _admin: Annotated[MarketsAdminContext, Depends(require_markets_admin)],
          service: Annotated[MarketsService, Depends(get_markets_service)]):
    response.headers["Cache-Control"] = "no-store"
    try:
        return service.state()
    except MarketError as error:
        raise _http_error(error) from error


@admin_router.get("/history")
def history(response: Response, _admin: Annotated[MarketsAdminContext, Depends(require_markets_admin)],
            service: Annotated[MarketsService, Depends(get_markets_service)]):
    response.headers["Cache-Control"] = "no-store"
    try:
        return service.history()
    except MarketError as error:
        raise _http_error(error) from error


@admin_router.put("/state")
def save(command: MarketStateUpdate, response: Response, admin: Annotated[MarketsAdminContext, Depends(require_markets_admin)],
         service: Annotated[MarketsService, Depends(get_markets_service)]):
    response.headers["Cache-Control"] = "no-store"
    try:
        return service.mutate(action="save", expected_revision=command.expectedRevision, operation_id=command.operationId,
                              reason=command.reason, actor=admin.uid, state=command.state)
    except MarketError as error:
        raise _http_error(error) from error


@admin_router.post("/publish")
def publish(command: MarketOperation, response: Response, admin: Annotated[MarketsAdminContext, Depends(require_markets_admin)],
            service: Annotated[MarketsService, Depends(get_markets_service)]):
    response.headers["Cache-Control"] = "no-store"
    try:
        return service.mutate(action="publish", expected_revision=command.expectedRevision, operation_id=command.operationId,
                              reason=command.reason, actor=admin.uid)
    except MarketError as error:
        raise _http_error(error) from error
