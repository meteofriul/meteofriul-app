from functools import lru_cache
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse

from app.contracts.events import LocalEventDetailResponse, LocalEventsResponse
from app.events import engine
from app.services.events import EventsService


router = APIRouter(prefix="/api", tags=["events"])


@lru_cache(maxsize=1)
def get_events_service() -> EventsService:
    return EventsService()


@router.get(
    "/local/events",
    response_model=LocalEventsResponse,
    response_model_exclude_none=True,
)
def get_local_events(
    city: Annotated[str, Query(min_length=1, max_length=120)],
    service: Annotated[EventsService, Depends(get_events_service)],
    limit: Annotated[int, Query(ge=1)] = 3,
    lat: Annotated[float | None, Query(ge=-90, le=90)] = None,
    lon: Annotated[float | None, Query(ge=-180, le=180)] = None,
) -> LocalEventsResponse:
    return service.get_local_events(
        city=city.strip(),
        limit=limit,
        lat=lat,
        lon=lon,
    )


@router.get(
    "/local/events/detail",
    response_model=LocalEventDetailResponse,
    response_model_exclude_none=True,
)
def get_local_event_detail(
    source: Annotated[str, Query(min_length=1, max_length=64)],
    url: Annotated[str, Query(min_length=1, max_length=2048)],
    service: Annotated[EventsService, Depends(get_events_service)],
) -> LocalEventDetailResponse:
    try:
        return service.get_event_detail(source=source, url=url)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid event detail request",
        ) from None


@router.get("/event-images/{filename}", response_class=FileResponse)
def get_event_image(filename: str) -> FileResponse:
    image_path = engine.event_image_cache_path_from_api_path(
        f"/api/event-images/{filename}"
    )
    if not image_path or not engine.event_image_cache_file_exists(
        f"/api/event-images/{filename}"
    ):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    suffix = Path(image_path).suffix.lower()
    media_type = {
        ".jpg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp",
    }.get(suffix, "application/octet-stream")
    return FileResponse(
        image_path,
        media_type=media_type,
        headers={"Cache-Control": "public, max-age=86400"},
    )
