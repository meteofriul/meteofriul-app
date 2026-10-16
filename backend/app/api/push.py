from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.contracts.push import (
    PushDeviceRegisterRequest,
    PushDeviceRegisterResponse,
    PushDeviceLocationUpdateRequest,
    PushDeviceLocationUpdateResponse,
    PushDeviceUnregisterRequest,
    PushDeviceUnregisterResponse,
)
from app.infrastructure.app_check import PushAppCheckContext, require_push_app_check
from app.repositories.push import (
    PushPilotCapacityReached,
    PushRepositoryUnavailable,
    PushTargetAlreadyRegistered,
)
from app.services.push import (
    PushAppVersionNotAllowed,
    PushConfigurationError,
    PushDeviceNotRegistered,
    PushInstallationNotAllowed,
    PushLocalityInvalid,
    PushLocationEvidenceInvalid,
    PushMunicipalityInvalid,
    PushPlatformNotAllowed,
    PushPilotService,
    get_push_pilot_service,
)


router = APIRouter(
    prefix="/api/push/devices",
    tags=["push"],
)


def _error(status_code: int, message: str, code: str) -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail={"message": message, "code": code},
    )


def get_push_service() -> PushPilotService:
    try:
        return get_push_pilot_service()
    except PushConfigurationError as error:
        raise _error(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Configurazione push non valida.",
            "push_configuration_invalid",
        ) from error


def _raise_service_error(error: Exception) -> None:
    if isinstance(error, PushAppVersionNotAllowed):
        raise _error(
            status.HTTP_403_FORBIDDEN,
            "Questa versione dell'app non e' autorizzata alla beta.",
            "push_app_version_not_allowed",
        ) from error
    if isinstance(error, PushPilotCapacityReached):
        raise _error(
            status.HTTP_409_CONFLICT,
            "Il pilot ha gia' raggiunto il numero massimo di dispositivi.",
            "push_pilot_capacity_reached",
        ) from error
    if isinstance(error, PushTargetAlreadyRegistered):
        raise _error(
            status.HTTP_409_CONFLICT,
            "Questo dispositivo di consegna risulta gia' registrato.",
            "push_target_already_registered",
        ) from error
    if isinstance(error, PushInstallationNotAllowed):
        raise _error(
            status.HTTP_403_FORBIDDEN,
            "Questo dispositivo non e' autorizzato al pilot.",
            "push_installation_not_allowed",
        ) from error
    if isinstance(error, PushPlatformNotAllowed):
        raise _error(
            status.HTTP_403_FORBIDDEN,
            "Questa app non e' autorizzata per la piattaforma richiesta.",
            "push_platform_not_allowed",
        ) from error
    if isinstance(error, PushDeviceNotRegistered):
        raise _error(
            status.HTTP_404_NOT_FOUND,
            "Il dispositivo non risulta registrato.",
            "push_device_not_registered",
        ) from error
    if isinstance(error, PushMunicipalityInvalid):
        raise _error(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "Il Comune indicato non corrisponde al catalogo FVG.",
            "push_municipality_invalid",
        ) from error
    if isinstance(error, PushLocalityInvalid):
        raise _error(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "La localita' indicata non corrisponde al catalogo FVG.",
            "push_locality_invalid",
        ) from error
    if isinstance(error, PushLocationEvidenceInvalid):
        raise _error(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "La posizione non e' abbastanza recente e precisa.",
            "push_location_evidence_invalid",
        ) from error
    if isinstance(error, PushConfigurationError):
        raise _error(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Configurazione push non valida.",
            "push_configuration_invalid",
        ) from error
    if isinstance(error, PushRepositoryUnavailable):
        raise _error(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Registrazione push temporaneamente non disponibile.",
            "push_storage_unavailable",
        ) from error
    raise error


@router.post("/register", response_model=PushDeviceRegisterResponse)
def register_push_device(
    request: PushDeviceRegisterRequest,
    service: Annotated[PushPilotService, Depends(get_push_service)],
    app_check_context: Annotated[
        PushAppCheckContext, Depends(require_push_app_check)
    ],
) -> PushDeviceRegisterResponse:
    try:
        return service.register(request, app_check_context=app_check_context)
    except (
        PushPilotCapacityReached,
        PushTargetAlreadyRegistered,
        PushAppVersionNotAllowed,
        PushInstallationNotAllowed,
        PushPlatformNotAllowed,
        PushLocalityInvalid,
        PushLocationEvidenceInvalid,
        PushMunicipalityInvalid,
        PushConfigurationError,
        PushRepositoryUnavailable,
    ) as error:
        _raise_service_error(error)
        raise AssertionError("unreachable")


@router.post("/unregister", response_model=PushDeviceUnregisterResponse)
def unregister_push_device(
    request: PushDeviceUnregisterRequest,
    service: Annotated[PushPilotService, Depends(get_push_service)],
    app_check_context: Annotated[
        PushAppCheckContext, Depends(require_push_app_check)
    ],
) -> PushDeviceUnregisterResponse:
    try:
        return service.unregister(
            request.installation_id,
            app_check_context=app_check_context,
        )
    except (
        PushInstallationNotAllowed,
        PushPlatformNotAllowed,
        PushConfigurationError,
        PushRepositoryUnavailable,
    ) as error:
        _raise_service_error(error)
        raise AssertionError("unreachable")


@router.post("/location", response_model=PushDeviceLocationUpdateResponse)
def update_push_device_location(
    request: PushDeviceLocationUpdateRequest,
    service: Annotated[PushPilotService, Depends(get_push_service)],
    app_check_context: Annotated[
        PushAppCheckContext, Depends(require_push_app_check)
    ],
) -> PushDeviceLocationUpdateResponse:
    try:
        return service.update_location(
            request,
            app_check_context=app_check_context,
        )
    except (
        PushDeviceNotRegistered,
        PushInstallationNotAllowed,
        PushLocationEvidenceInvalid,
        PushPlatformNotAllowed,
        PushConfigurationError,
        PushRepositoryUnavailable,
    ) as error:
        _raise_service_error(error)
        raise AssertionError("unreachable")
