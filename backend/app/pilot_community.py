"""Run the temporary national Community over loopback/ADB reverse only.

Usage (from backend): python -m app.pilot_community --port 8783
This entrypoint imports neither the published application nor Firebase setup.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from fastapi import FastAPI, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.contracts.live import (
    CommunityReportConfirmationCreate,
    CommunityReportFlagCreate, CommunityReputationRequest,
)
from app.services.community import CommunityServiceError
from app.repositories.community import CommunityRepositoryUnavailable
from app.services.pilot_community import (
    PilotCommunityObservationUpdate,
    PilotCommunityReportCorrection, PilotOperation,
    PilotCommunityReportCreate, PilotCommunityReportDelete, PilotCommunityResolve, PilotCommunityService,
)
from app.services.pilot_community_geography import PilotCommunityGeographyCatalog, PilotCommunityGeographyUnavailable


PILOT_KIND = "meteofriul.community.local-pilot.v1"
ALLOWED_ORIGINS = frozenset({
    "http://127.0.0.1:5174", "http://localhost:5174", "https://localhost",
})
PILOT_HEADER = "x-meteo-pilot-community"


def create_app(*, service: PilotCommunityService | None = None, port: int = 8783,
               health_kind: str = PILOT_KIND, health_project: str | None = None,
               health_check=None) -> FastAPI:
    app = FastAPI(title="Meteo Friul local Community pilot", docs_url=None, redoc_url=None, openapi_url=None)
    app.state.community = service or PilotCommunityService()
    app.add_middleware(
        CORSMiddleware, allow_origins=sorted(ALLOWED_ORIGINS),
        allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["content-type", PILOT_HEADER],
        expose_headers=["retry-after"], allow_credentials=False,
    )
    allowed_hosts = {f"127.0.0.1:{port}", f"localhost:{port}", f"[::1]:{port}"}

    @app.middleware("http")
    async def isolate(request: Request, call_next):
        host = request.headers.get("host", "").lower()
        origin = request.headers.get("origin")
        if host not in allowed_hosts or (origin and origin not in ALLOWED_ORIGINS):
            return JSONResponse(status_code=403, content={"detail": "Origine non consentita per la pilota locale."})
        if request.method not in {"GET", "HEAD", "OPTIONS"} and request.headers.get(PILOT_HEADER) != "local-only":
            return JSONResponse(status_code=403, content={"detail": "Richiesta non autorizzata alla pilota locale."})
        # These commands contain only a compact enum, alias and coordinates.
        # Bound streaming requests as well as requests with Content-Length.
        if request.method in {"POST", "PATCH", "DELETE"}:
            body_size = 0
            chunks = []
            async for chunk in request.stream():
                body_size += len(chunk)
                if body_size > 8192:
                    return JSONResponse(status_code=413, content={"detail": "Richiesta troppo grande."})
                chunks.append(chunk)
            request._body = b"".join(chunks)
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Meteo-Community-Pilot"] = f"local-{getattr(app.state.community.repository, 'storage_kind', 'memory')}"
        return response

    @app.exception_handler(CommunityServiceError)
    async def service_error(_request, error):
        headers = {}
        if isinstance(error.detail, dict) and error.detail.get("retry_after_seconds"):
            headers["Retry-After"] = str(error.detail["retry_after_seconds"])
        return JSONResponse(status_code=error.status_code, content={"detail": error.detail}, headers=headers)

    @app.exception_handler(CommunityRepositoryUnavailable)
    async def storage_error(_request, _error):
        return JSONResponse(status_code=503, content={"detail": {"code": "community_storage_unavailable", "message": "Il servizio segnalazioni non è disponibile. Riprova tra poco."}})

    @app.exception_handler(RequestValidationError)
    async def invalid_request(_request, _error):
        # Pydantic's normal response echoes offending input, including GPS.
        return JSONResponse(status_code=422, content={"detail": "Parametri della richiesta non validi."})

    @app.exception_handler(PilotCommunityGeographyUnavailable)
    async def geography_unavailable(_request, _error):
        return JSONResponse(status_code=503, content={"detail": "Il catalogo geografico della pilota non è disponibile."})

    @app.get("/api/community/health")
    def health():
        if health_check is not None:
            health_check()
        payload = {"ok": True, "kind": health_kind, "storage": getattr(app.state.community.repository, "storage_kind", "memory"), "scope": "IT", "published": False}
        if health_project is not None:
            payload["project_id"] = health_project
        return payload

    @app.get("/api/community/reports")
    def reports(
        istat_code: str | None = Query(default=None, pattern=r"^\d{6}$"),
        lat: float | None = Query(default=None, ge=-90, le=90),
        lon: float | None = Query(default=None, ge=-180, le=180),
        radius_km: float = Query(default=30, ge=1, le=100),
    ):
        return app.state.community.get_scoped_reports(istat_code=istat_code, lat=lat, lon=lon, radius_km=radius_km)

    @app.post("/api/community/resolve")
    def resolve(command: PilotCommunityResolve):
        return app.state.community.resolve_location(command)

    @app.post("/api/community/reports")
    def create(command: PilotCommunityReportCreate):
        return app.state.community.create_report(command, client_host="loopback-pilot")

    @app.patch("/api/community/reports/{report_id}")
    def update(report_id: str, command: PilotCommunityObservationUpdate):
        return app.state.community.update_observation(
            report_id, command, client_host="loopback-pilot",
        )

    @app.post("/api/community/reports/{report_id}/correction")
    def correct(report_id: str, command: PilotCommunityReportCorrection):
        return app.state.community.correct_observation(report_id, command, client_host="loopback-pilot")

    @app.post("/api/community/operations/{operation_id}")
    def operation(operation_id: str, command: PilotOperation):
        return app.state.community.operation_status(operation_id, command)

    @app.delete("/api/community/reports/{report_id}")
    def undo_or_withdraw(report_id: str, command: PilotCommunityReportDelete):
        return app.state.community.delete_report(report_id, command, client_host="loopback-pilot")

    @app.post("/api/community/reports/{group_id}/confirmation")
    def confirm(group_id: str, command: CommunityReportConfirmationCreate):
        result = app.state.community.confirm_report(group_id, command, client_host="loopback-pilot")
        payload = result.model_dump(mode="json", exclude_none=True)
        payload["group"] = app.state.community.public_payload(result.group)
        return payload

    @app.post("/api/community/reports/{group_id}/flags")
    def flag(group_id: str, command: CommunityReportFlagCreate):
        return app.state.community.flag_report_group(group_id, command, client_host="loopback-pilot")

    @app.post("/api/community/reputation")
    def reputation(command: CommunityReputationRequest):
        return app.state.community.get_reputation(command, client_host="loopback-pilot")

    return app


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", choices=["127.0.0.1"], default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8783)
    parser.add_argument("--geography-path", type=Path)
    parser.add_argument(
        "--state-path", type=Path,
        default=Path(__file__).resolve().parents[2] / ".dev-logs" / "community-pilot" / "state.sqlite3",
        help="Local pilot-only SQLite state file (observations and protection ledgers).",
    )
    args = parser.parse_args()
    if not 1024 <= args.port <= 65535:
        parser.error("port must be between 1024 and 65535")
    geography = PilotCommunityGeographyCatalog(data_path=args.geography_path)
    # Load and validate the local geometry artifact before binding the port.
    _ = geography.municipalities
    from app.repositories.pilot_community_sqlite import PilotSQLiteCommunityRepository
    repository = PilotSQLiteCommunityRepository(args.state_path)
    import uvicorn
    try:
        uvicorn.run(create_app(service=PilotCommunityService(geography=geography, repository=repository), port=args.port),
                    host=args.host, port=args.port, access_log=False)
    finally:
        repository.close()


if __name__ == "__main__":
    main()
