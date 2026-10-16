from functools import lru_cache
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.contracts.location import (
    LocationSearchItem,
    ReverseLocationRequest,
    ReverseLocationResponse,
)
from app.services.location import (
    LocationSearchSourceUnavailable,
    LocationService,
    LocationSourceUnavailable,
)
from app.services.national_municipalities import NationalMunicipalityCatalogError
from app.services.verified_municipality_search import search_verified_municipalities


router = APIRouter(prefix="/api/location", tags=["location"])


@lru_cache(maxsize=1)
def get_location_service() -> LocationService:
    return LocationService()


@router.get("/search", response_model=list[LocationSearchItem])
def search_locations(
    q: Annotated[str, Query(min_length=2, max_length=120)],
    service: Annotated[LocationService, Depends(get_location_service)],
) -> list[LocationSearchItem]:
    try:
        return service.search(q)
    except LocationSearchSourceUnavailable as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "location_search_source_unavailable",
                "message": "Ricerca nazionale temporaneamente non raggiungibile.",
            },
        ) from error


@router.get("/municipalities/search", response_model=list[LocationSearchItem])
def search_municipalities(
    q: Annotated[str, Query(min_length=2, max_length=120)],
) -> list[LocationSearchItem]:
    """Search the pinned ISTAT catalog, independently of the place geocoder."""

    try:
        return search_verified_municipalities(q)
    except NationalMunicipalityCatalogError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "municipality_catalog_unavailable",
                "message": "Elenco dei Comuni verificati temporaneamente non disponibile.",
            },
        ) from error


def _resolve_reverse_location(
    *,
    lat: float,
    lon: float,
    accuracy_m: float | None,
    service: LocationService,
) -> ReverseLocationResponse:
    try:
        return service.reverse(lat=lat, lon=lon, accuracy_m=accuracy_m)
    except LocationSourceUnavailable as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "location_source_unavailable",
                "message": "Servizio di localizzazione temporaneamente non raggiungibile.",
            },
        ) from error


@router.post(
    "/reverse",
    response_model=ReverseLocationResponse,
    responses={
        status.HTTP_503_SERVICE_UNAVAILABLE: {
            "description": "Offline geography catalog unavailable",
        },
    },
)
def reverse_location(
    request: ReverseLocationRequest,
    service: Annotated[LocationService, Depends(get_location_service)],
) -> ReverseLocationResponse:
    return _resolve_reverse_location(
        lat=request.lat,
        lon=request.lon,
        accuracy_m=request.accuracyM,
        service=service,
    )


@router.get(
    "/reverse",
    response_model=ReverseLocationResponse,
    deprecated=True,
    responses={
        status.HTTP_503_SERVICE_UNAVAILABLE: {
            "description": "Offline geography catalog unavailable",
        },
    },
)
def reverse_location_legacy(
    lat: Annotated[float, Query(ge=-90, le=90)],
    lon: Annotated[float, Query(ge=-180, le=180)],
    service: Annotated[LocationService, Depends(get_location_service)],
) -> ReverseLocationResponse:
    return _resolve_reverse_location(
        lat=lat,
        lon=lon,
        accuracy_m=None,
        service=service,
    )
