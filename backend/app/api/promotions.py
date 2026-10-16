from __future__ import annotations

from functools import lru_cache
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel, ConfigDict, Field

from app.infrastructure.ads_admin_auth import AdsAdminContext, require_ads_admin
from app.infrastructure.app_check import require_community_app_check
from app.infrastructure.firebase import get_firestore_client
from app.services.promotions import (
    PromotionRepository,
    PromotionService,
    PromotionAvailabilityConflict,
    PromotionStateConflict,
    PromotionStorageUnavailable,
    PromotionValidationError,
)
from app.services.site_import import SiteImportError, SiteImportService


public_router = APIRouter(prefix="/api/promotions", tags=["promotions"])
admin_router = APIRouter(prefix="/api/admin/promotions", tags=["promotions-admin"])


class PromotionEventRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    campaignId: str = Field(min_length=1, max_length=120)
    placement: str = Field(min_length=1, max_length=20)
    type: str = Field(min_length=1, max_length=20)


class PromotionStateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expectedRevision: int | None = Field(default=None, ge=0)
    state: dict[str, Any]


class PromotionSiteImportRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    url: str = Field(min_length=4, max_length=2048)


@lru_cache(maxsize=1)
def get_promotion_service() -> PromotionService:
    return PromotionService(PromotionRepository(get_firestore_client))


@lru_cache(maxsize=1)
def get_site_import_service() -> SiteImportService:
    return SiteImportService()


def _service_error(error: Exception) -> HTTPException:
    if isinstance(error, PromotionAvailabilityConflict):
        return HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=error.as_detail(),
        )
    if isinstance(error, PromotionStateConflict):
        return HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": str(error)},
        )
    if isinstance(error, PromotionValidationError):
        return HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={"code": str(error)},
        )
    return HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail={"code": str(error) or "promotion_storage_unavailable"},
    )


@public_router.get("/catalog")
def get_public_catalog(
    response: Response,
    service: Annotated[PromotionService, Depends(get_promotion_service)],
) -> dict[str, Any]:
    try:
        catalog = service.public_catalog()
    except PromotionStorageUnavailable as error:
        raise _service_error(error) from error
    response.headers["Cache-Control"] = "public, max-age=60, must-revalidate"
    response.headers["ETag"] = f'"promotions-{catalog["revision"]}"'
    return catalog


@public_router.post("/events", status_code=status.HTTP_202_ACCEPTED)
def record_public_event(
    request: PromotionEventRequest,
    _app_check: Annotated[dict | None, Depends(require_community_app_check)],
    service: Annotated[PromotionService, Depends(get_promotion_service)],
) -> dict[str, Any]:
    try:
        return service.record_event(request.model_dump())
    except (PromotionStorageUnavailable, PromotionValidationError) as error:
        raise _service_error(error) from error


@admin_router.get("/state")
def get_admin_state(
    _admin: Annotated[AdsAdminContext, Depends(require_ads_admin)],
    service: Annotated[PromotionService, Depends(get_promotion_service)],
) -> dict[str, Any]:
    try:
        return service.admin_state()
    except PromotionStorageUnavailable as error:
        raise _service_error(error) from error


@admin_router.get("/availability")
def get_admin_availability(
    _admin: Annotated[AdsAdminContext, Depends(require_ads_admin)],
    service: Annotated[PromotionService, Depends(get_promotion_service)],
    start_date: Annotated[str | None, Query(alias="startDate")] = None,
    end_date: Annotated[str | None, Query(alias="endDate")] = None,
    page: Annotated[list[str] | None, Query()] = None,
) -> dict[str, Any]:
    try:
        return service.availability(
            start_date=start_date,
            end_date=end_date,
            placements=page,
        )
    except (PromotionStorageUnavailable, PromotionValidationError) as error:
        raise _service_error(error) from error


@admin_router.post("/import-site")
def import_promotion_site(
    request: PromotionSiteImportRequest,
    _admin: Annotated[AdsAdminContext, Depends(require_ads_admin)],
    service: Annotated[SiteImportService, Depends(get_site_import_service)],
) -> dict[str, Any]:
    try:
        return service.import_site(request.url)
    except SiteImportError as error:
        raise HTTPException(
            status_code=error.status_code,
            detail={"code": error.code},
        ) from error


@admin_router.put("/state")
def replace_admin_state(
    request: PromotionStateRequest,
    admin: Annotated[AdsAdminContext, Depends(require_ads_admin)],
    service: Annotated[PromotionService, Depends(get_promotion_service)],
) -> dict[str, Any]:
    try:
        return service.replace_state(
            request.state,
            expected_revision=request.expectedRevision,
            actor_uid=admin.uid,
            actor_email=admin.email,
        )
    except (
        PromotionStateConflict,
        PromotionStorageUnavailable,
        PromotionValidationError,
    ) as error:
        raise _service_error(error) from error
