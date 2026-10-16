from functools import lru_cache
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request

from app.contracts.live import (
    CommunityConfirmationResponse,
    CommunityReportConfirmationCreate,
    CommunityReportCreate,
    CommunityReportCreatedResponse,
    CommunityReportDelete,
    CommunityReportDeletedResponse,
    CommunityReportFlagCreate,
    CommunityReportFlaggedResponse,
    CommunityReputationRequest,
    CommunityReputationResponse,
    CommunityReportsResponse,
    WebcamManifestResponse,
)
from app.infrastructure.app_check import require_community_app_check
from app.infrastructure.firebase import community_storage_mode, get_firestore_client
from app.repositories.community import CommunityRepository
from app.services.community import CommunityService, CommunityServiceError
from app.services.webcam_controls import (
    WebcamControlService,
    get_webcam_control_service,
)
from app.services.webcams import WebcamManifestService


router = APIRouter(prefix="/api", tags=["live"])


@lru_cache(maxsize=1)
def get_webcam_manifest_service() -> WebcamManifestService:
    return WebcamManifestService()


@lru_cache(maxsize=1)
def get_community_service() -> CommunityService:
    return CommunityService(
        repository=CommunityRepository(
            firestore_provider=get_firestore_client,
            storage_mode=community_storage_mode(),
        )
    )


def _client_host(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def _raise_http(error: CommunityServiceError) -> None:
    headers = None
    if isinstance(error.detail, dict):
        retry_after = error.detail.get("retry_after_seconds")
        if isinstance(retry_after, int) and retry_after > 0:
            headers = {"Retry-After": str(retry_after)}
    raise HTTPException(
        status_code=error.status_code,
        detail=error.detail,
        headers=headers,
    ) from error


@router.get(
    "/live/webcams",
    response_model=WebcamManifestResponse,
    response_model_exclude_none=True,
)
def get_live_webcams(
    service: Annotated[WebcamManifestService, Depends(get_webcam_manifest_service)],
    control_service: Annotated[
        WebcamControlService,
        Depends(get_webcam_control_service),
    ],
) -> WebcamManifestResponse:
    return control_service.apply_public_controls(service.get_manifest())


@router.get(
    "/community/reports",
    response_model=CommunityReportsResponse,
    response_model_exclude_none=True,
)
def get_community_reports(
    service: Annotated[CommunityService, Depends(get_community_service)],
) -> CommunityReportsResponse:
    try:
        return service.get_reports()
    except CommunityServiceError as error:
        _raise_http(error)


@router.post(
    "/community/reputation",
    response_model=CommunityReputationResponse,
    response_model_exclude_none=True,
)
def get_community_reputation(
    command: CommunityReputationRequest,
    request: Request,
    service: Annotated[CommunityService, Depends(get_community_service)],
    _app_check: Annotated[dict | None, Depends(require_community_app_check)],
) -> CommunityReputationResponse:
    try:
        return service.get_reputation(
            command,
            client_host=_client_host(request),
        )
    except CommunityServiceError as error:
        _raise_http(error)


@router.post(
    "/community/reports",
    response_model=CommunityReportCreatedResponse,
    response_model_exclude_none=True,
)
def create_community_report(
    command: CommunityReportCreate,
    request: Request,
    service: Annotated[CommunityService, Depends(get_community_service)],
    _app_check: Annotated[dict | None, Depends(require_community_app_check)],
) -> CommunityReportCreatedResponse:
    try:
        return service.create_report(command, client_host=_client_host(request))
    except CommunityServiceError as error:
        _raise_http(error)


@router.delete(
    "/community/reports/{report_id}",
    response_model=CommunityReportDeletedResponse,
    response_model_exclude_none=True,
)
def delete_community_report(
    report_id: str,
    command: CommunityReportDelete,
    request: Request,
    service: Annotated[CommunityService, Depends(get_community_service)],
    _app_check: Annotated[dict | None, Depends(require_community_app_check)],
) -> CommunityReportDeletedResponse:
    try:
        return service.delete_report(
            report_id,
            command,
            client_host=_client_host(request),
        )
    except CommunityServiceError as error:
        _raise_http(error)


@router.post(
    "/community/reports/{group_id}/confirmation",
    response_model=CommunityConfirmationResponse,
    response_model_exclude_none=True,
)
def confirm_community_report(
    group_id: str,
    command: CommunityReportConfirmationCreate,
    request: Request,
    service: Annotated[CommunityService, Depends(get_community_service)],
    _app_check: Annotated[dict | None, Depends(require_community_app_check)],
) -> CommunityConfirmationResponse:
    try:
        return service.confirm_report(
            group_id,
            command,
            client_host=_client_host(request),
        )
    except CommunityServiceError as error:
        _raise_http(error)


@router.post(
    "/community/reports/{group_id}/flags",
    response_model=CommunityReportFlaggedResponse,
    response_model_exclude_none=True,
)
def flag_community_report(
    group_id: str,
    command: CommunityReportFlagCreate,
    request: Request,
    service: Annotated[CommunityService, Depends(get_community_service)],
    _app_check: Annotated[dict | None, Depends(require_community_app_check)],
) -> CommunityReportFlaggedResponse:
    try:
        return service.flag_report_group(
            group_id,
            command,
            client_host=_client_host(request),
        )
    except CommunityServiceError as error:
        _raise_http(error)
