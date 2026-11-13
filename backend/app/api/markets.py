from __future__ import annotations

from functools import lru_cache
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, Field

from app.infrastructure.markets_admin_auth import MarketsAdminContext, require_markets_admin
from app.markets.model import MarketError
from app.markets.repository import configured_repository
from app.markets.service import MarketsService
from app.markets.weekly_audit import FirestoreWeeklyAuditStore


public_router = APIRouter(prefix="/api/markets", tags=["markets"])
admin_router = APIRouter(prefix="/api/admin/markets", tags=["markets-admin"])


class MarketOperation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expectedRevision: int = Field(ge=0, strict=True)
    operationId: str = Field(min_length=8, max_length=120)
    reason: str = Field(min_length=3, max_length=1000)


class MarketStateUpdate(MarketOperation):
    state: dict[str, Any]


class MarketReviewCompletion(MarketOperation):
    period: str = Field(pattern=r"^\d{4}-(0[1-9]|1[0-2])$")


class MarketEmailSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expectedRevision: int = Field(ge=0, strict=True)
    operationId: str = Field(min_length=8, max_length=120)
    recipient: str = Field(min_length=3, max_length=254)
    enabled: bool = Field(strict=True)


class MarketSourceReview(BaseModel):
    model_config = ConfigDict(extra="forbid")
    sourceUrl: str = Field(min_length=12, max_length=2000)
    outcome: Literal["verified", "needs_correction", "replace_source"]
    note: str = Field(min_length=5, max_length=500)
    reportRunId: str = Field(pattern=r"^[0-9a-f]{32}$")
    operationId: str = Field(min_length=8, max_length=120)


def _http_error(error):
    return HTTPException(status_code=error.status, detail=error.detail)


@lru_cache(maxsize=1)
def get_markets_service() -> MarketsService:
    try:
        return MarketsService(configured_repository())
    except MarketError as error:
        raise _http_error(error) from error


def get_weekly_audit_store(service: Annotated[MarketsService, Depends(get_markets_service)]):
    if service.repository.storage != "firestore":
        return None
    return FirestoreWeeklyAuditStore(service.repository.db)


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


@admin_router.get("/weekly-audit")
def weekly_audit(response: Response, _admin: Annotated[MarketsAdminContext, Depends(require_markets_admin)],
                 store: Annotated[FirestoreWeeklyAuditStore | None, Depends(get_weekly_audit_store)]):
    response.headers["Cache-Control"] = "no-store"
    try:
        return store.latest() if store else None
    except Exception as error:
        raise _http_error(MarketError("markets_audit_unavailable", 503)) from error


@admin_router.get("/weekly-audit/reviews")
def weekly_audit_reviews(response: Response,
                         _admin: Annotated[MarketsAdminContext, Depends(require_markets_admin)],
                         store: Annotated[FirestoreWeeklyAuditStore | None, Depends(get_weekly_audit_store)]):
    response.headers["Cache-Control"] = "no-store"
    try:
        return store.reviews() if store else []
    except Exception as error:
        raise _http_error(MarketError("markets_audit_unavailable", 503)) from error


@admin_router.get("/weekly-audit/{market_id}")
def weekly_audit_market(market_id: str, response: Response,
                        _admin: Annotated[MarketsAdminContext, Depends(require_markets_admin)],
                        store: Annotated[FirestoreWeeklyAuditStore | None, Depends(get_weekly_audit_store)]):
    response.headers["Cache-Control"] = "no-store"
    if not 1 <= len(market_id) <= 120 or "/" in market_id:
        raise HTTPException(status_code=404)
    try:
        detail = store.market(market_id) if store else None
    except Exception as error:
        raise _http_error(MarketError("markets_audit_unavailable", 503)) from error
    if detail is None:
        raise HTTPException(status_code=404)
    return detail


@admin_router.put("/weekly-audit/{market_id}/review")
def weekly_audit_save_review(market_id: str, command: MarketSourceReview, response: Response,
                             _admin: Annotated[MarketsAdminContext, Depends(require_markets_admin)],
                             store: Annotated[FirestoreWeeklyAuditStore | None, Depends(get_weekly_audit_store)]):
    response.headers["Cache-Control"] = "no-store"
    if not 1 <= len(market_id) <= 120 or "/" in market_id:
        raise HTTPException(status_code=404)
    if store is None:
        raise _http_error(MarketError("markets_audit_unavailable", 503))
    try:
        return store.save_review(market_id=market_id, source_url=command.sourceUrl,
                                 outcome=command.outcome, note=command.note,
                                 report_run_id=command.reportRunId,
                                 operation_id=command.operationId)
    except MarketError as error:
        raise _http_error(error) from error
    except Exception as error:
        raise _http_error(MarketError("markets_audit_unavailable", 503)) from error


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


@admin_router.post("/review-complete")
def complete_review(command: MarketReviewCompletion, response: Response,
                    admin: Annotated[MarketsAdminContext, Depends(require_markets_admin)],
                    service: Annotated[MarketsService, Depends(get_markets_service)]):
    response.headers["Cache-Control"] = "no-store"
    try:
        return service.complete_review(expected_revision=command.expectedRevision, operation_id=command.operationId,
                                       period=command.period, reason=command.reason, actor=admin.uid)
    except MarketError as error:
        raise _http_error(error) from error


@admin_router.put("/email-settings")
def configure_email(command: MarketEmailSettings, response: Response,
                    admin: Annotated[MarketsAdminContext, Depends(require_markets_admin)],
                    service: Annotated[MarketsService, Depends(get_markets_service)]):
    response.headers["Cache-Control"] = "no-store"
    try:
        return service.configure_email(expected_revision=command.expectedRevision, operation_id=command.operationId,
                                       recipient=command.recipient, enabled=command.enabled, actor=admin.uid)
    except MarketError as error:
        raise _http_error(error) from error
