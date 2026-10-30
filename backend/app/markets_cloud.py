"""Standalone market catalogue and administration; no other product APIs."""
from __future__ import annotations

import os

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware

from app.api.markets import admin_router, public_router
from app.infrastructure.markets_admin_auth import require_markets_admin


ALLOWED_ORIGINS = (
    "https://meteofriul-inserzioni.web.app",
    "https://meteofriul.app",
    "https://localhost",
)


def create_app() -> FastAPI:
    project = os.getenv("MARKETS_FIREBASE_PROJECT_ID", "").strip()
    public_mode = os.getenv("MARKETS_PUBLIC_CATALOGUE_ENABLED", "false").strip().lower()
    if (
        os.getenv("MARKETS_STORAGE", "").strip().lower() != "firestore"
        or os.getenv("MARKETS_ADMIN_AUTH_MODE", "firebase").strip().lower() != "firebase"
        or os.getenv("MARKETS_ADMIN_LOCAL_TOKEN", "").strip()
        or not project
        or os.getenv("FIREBASE_PROJECT_ID", "").strip() != project
        or public_mode not in {"true", "false"}
    ):
        raise ValueError("markets_cloud_configuration_invalid")
    public_enabled = public_mode == "true"
    app = FastAPI(title="Meteo Friul Markets", docs_url=None, redoc_url=None, openapi_url=None)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(ALLOWED_ORIGINS if public_enabled else ALLOWED_ORIGINS[:1]),
        allow_credentials=False,
        allow_methods=["GET", "PUT", "POST", "OPTIONS"],
        allow_headers=["Accept", "Content-Type", "Authorization", "If-None-Match"],
        expose_headers=["ETag"],
        max_age=600,
    )
    if public_enabled:
        app.include_router(public_router)

    def require_online_access(request: Request, _admin=Depends(require_markets_admin)):
        if not public_enabled and request.url.path == "/api/admin/markets/publish":
            raise HTTPException(status_code=423, detail={"code": "markets_publication_disabled"},
                                headers={"Cache-Control": "no-store"})

    app.include_router(admin_router, dependencies=[Depends(require_online_access)])

    @app.get("/healthz")
    def health():
        # Liveness does not provision data or make a cloud request.
        return {"status": "ok", "service": "markets", "sourceCommit": os.getenv("MARKETS_SOURCE_COMMIT", ""),
                "publicCatalogueEnabled": public_enabled}

    return app
