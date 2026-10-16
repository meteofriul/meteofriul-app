from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, ConfigDict, Field

from app.api.live import get_webcam_manifest_service
from app.infrastructure.webcam_admin_auth import (
    WebcamAdminContext,
    require_webcam_admin,
)
from app.services.webcam_controls import (
    WebcamControlConflict,
    WebcamControlService,
    WebcamControlStorageUnavailable,
    WebcamControlValidationError,
    get_webcam_control_service,
)
from app.services.webcams import WebcamManifestService


router = APIRouter(prefix="/api/admin/webcams", tags=["webcams-admin"])


class WebcamPreviewChange(BaseModel):
    model_config = ConfigDict(extra="forbid")

    webcamId: str = Field(min_length=1, max_length=120)
    previewEnabled: bool = Field(strict=True)
    reason: str = Field(default="", max_length=500)


class WebcamPreviewUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expectedRevision: int = Field(ge=0)
    changes: list[WebcamPreviewChange] = Field(min_length=1, max_length=500)


def _service_error(error: Exception) -> HTTPException:
    if isinstance(error, WebcamControlConflict):
        return HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": str(error)},
        )
    if isinstance(error, WebcamControlValidationError):
        return HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={"code": str(error)},
        )
    return HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail={"code": str(error) or "webcam_control_storage_unavailable"},
    )


@router.get("/state")
def get_admin_state(
    _admin: Annotated[WebcamAdminContext, Depends(require_webcam_admin)],
    manifest_service: Annotated[WebcamManifestService, Depends(get_webcam_manifest_service)],
    control_service: Annotated[WebcamControlService, Depends(get_webcam_control_service)],
    response: Response,
) -> dict[str, Any]:
    try:
        payload = control_service.admin_state(manifest_service.get_manifest())
    except WebcamControlStorageUnavailable as error:
        raise _service_error(error) from error
    response.headers["Cache-Control"] = "no-store"
    return payload


@router.put("/state")
def update_admin_state(
    request: WebcamPreviewUpdateRequest,
    admin: Annotated[WebcamAdminContext, Depends(require_webcam_admin)],
    manifest_service: Annotated[WebcamManifestService, Depends(get_webcam_manifest_service)],
    control_service: Annotated[WebcamControlService, Depends(get_webcam_control_service)],
    response: Response,
) -> dict[str, Any]:
    try:
        payload = control_service.update_previews(
            [change.model_dump() for change in request.changes],
            manifest=manifest_service.get_manifest(),
            expected_revision=request.expectedRevision,
            actor_uid=admin.uid,
            actor_email=admin.email,
        )
    except (
        WebcamControlConflict,
        WebcamControlStorageUnavailable,
        WebcamControlValidationError,
    ) as error:
        raise _service_error(error) from error
    response.headers["Cache-Control"] = "no-store"
    return payload
