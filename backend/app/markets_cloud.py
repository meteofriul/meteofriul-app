"""Standalone market catalogue and administration; no other product APIs."""
from __future__ import annotations

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.markets import admin_router, public_router


ALLOWED_ORIGINS = (
    "https://meteofriul-inserzioni.web.app",
    "https://meteofriul.app",
    "https://localhost",
)


def create_app() -> FastAPI:
    project = os.getenv("MARKETS_FIREBASE_PROJECT_ID", "").strip()
    if (
        os.getenv("MARKETS_STORAGE", "").strip().lower() != "firestore"
        or os.getenv("MARKETS_ADMIN_AUTH_MODE", "firebase").strip().lower() != "firebase"
        or os.getenv("MARKETS_ADMIN_LOCAL_TOKEN", "").strip()
        or not project
        or os.getenv("FIREBASE_PROJECT_ID", "").strip() != project
    ):
        raise ValueError("markets_cloud_configuration_invalid")
    app = FastAPI(title="Meteo Friul Markets", docs_url=None, redoc_url=None, openapi_url=None)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(ALLOWED_ORIGINS),
        allow_credentials=False,
        allow_methods=["GET", "PUT", "POST", "OPTIONS"],
        allow_headers=["Accept", "Content-Type", "Authorization", "If-None-Match"],
        expose_headers=["ETag"],
        max_age=600,
    )
    app.include_router(public_router)
    app.include_router(admin_router)

    @app.get("/healthz")
    def health():
        # Liveness does not provision data or make a cloud request.
        return {"status": "ok", "service": "markets", "sourceCommit": os.getenv("MARKETS_SOURCE_COMMIT", "")}

    return app
