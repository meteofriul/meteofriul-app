import os
from urllib.parse import urlsplit

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.events import router as events_router
from app.api.live import router as live_router
from app.api.location import router as location_router
from app.api.push import router as push_router
from app.api.promotions import admin_router as promotions_admin_router
from app.api.promotions import public_router as promotions_public_router
from app.api.weather import router as weather_router
from app.api.webcam_admin import router as webcam_admin_router
from app.infrastructure.open_meteo_policy import (
    LOCAL_WEATHER_PILOT_HEADER,
    provider_policy_status,
)


CAPACITOR_ORIGIN = "https://localhost"
WEB_APP_ORIGIN = "https://meteofriul.app"
ADS_PANEL_ORIGIN = "https://meteofriul-inserzioni.web.app"
CORS_ADDITIONAL_ORIGINS_ENV = "CORS_ADDITIONAL_ORIGINS"


def _normalize_cors_origin(value: str) -> str:
    origin = str(value or "").strip().rstrip("/")
    parsed = urlsplit(origin)
    if (
        parsed.scheme != "https"
        or not parsed.netloc
        or "*" in (parsed.hostname or "")
        or parsed.username
        or parsed.password
        or parsed.path
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("cors_origin_must_be_absolute_https_origin")
    return origin


def get_cors_allowed_origins() -> list[str]:
    origins = [CAPACITOR_ORIGIN, WEB_APP_ORIGIN, ADS_PANEL_ORIGIN]
    configured = os.getenv(CORS_ADDITIONAL_ORIGINS_ENV, "")
    for raw_origin in configured.split(","):
        if not raw_origin.strip():
            continue
        origin = _normalize_cors_origin(raw_origin)
        if origin not in origins:
            origins.append(origin)
    return origins


def create_app() -> FastAPI:
    app = FastAPI(
        title="Meteo Friul UI3 API",
        version="0.1.0",
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=get_cors_allowed_origins(),
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=[
            "Accept",
            "Content-Type",
            "Authorization",
            "X-Firebase-AppCheck",
            LOCAL_WEATHER_PILOT_HEADER,
        ],
        expose_headers=["ETag", "Retry-After"],
        max_age=600,
    )
    app.include_router(location_router)
    app.include_router(live_router)
    app.include_router(events_router)
    app.include_router(weather_router)
    app.include_router(push_router)
    app.include_router(promotions_public_router)
    app.include_router(promotions_admin_router)
    app.include_router(webcam_admin_router)

    @app.get("/api/healthz", tags=["infrastructure"])
    @app.get("/healthz", tags=["infrastructure"])
    async def healthcheck() -> dict[str, object]:
        return {
            "status": "ok",
            "weather_provider_policy": provider_policy_status(),
        }

    return app


app = create_app()
