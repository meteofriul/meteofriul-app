"""Private, enrolled-device Community service for the separate pilot project.

No shared Firebase app, published application, or self-registration endpoint.
The bearer is provisioned into the pilot's Android no-backup directory, never
compiled into an APK. Its server-side digest is bound to the existing client ID.
"""
from __future__ import annotations

from collections import defaultdict, deque
from datetime import datetime, timezone
import hashlib
import hmac
import json
import os
import re
import threading
import time

from fastapi import FastAPI, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

from app.contracts.live import (
    CommunityReportConfirmationCreate, CommunityReportFlagCreate,
    CommunityReputationRequest,
)
from app.repositories.community import CommunityRepositoryUnavailable
from app.services.community_reports import CommunityReportsService, CommunityReportVote, CommunityHistoryQuery
from app.services.community import CommunityServiceError
from app.services.pilot_community import (
    PilotCommunityObservationUpdate, PilotCommunityReportCorrection,
    PilotCommunityReportCreate, PilotCommunityReportDelete,
    PilotCommunityResolve, PilotCommunityService, PilotOperation,
)
from app.services.pilot_community_geography import (
    PilotCommunityGeographyCatalog, PilotCommunityGeographyUnavailable,
)

PILOT_PROJECT = os.environ.get("COMMUNITY_CLOUD_PROJECT", "meteofriul-pilot-20260906")
DEFAULT_PILOT_HOSTS = {
    "pilot-community-335641913741.europe-west1.run.app",
    "pilot-community-bk4gvhptwa-ew.a.run.app",
}
PILOT_HOSTS = frozenset(filter(None, (
    value.strip().lower() for value in os.environ.get(
        "COMMUNITY_ALLOWED_HOSTS", ",".join(sorted(DEFAULT_PILOT_HOSTS)),
    ).split(",")
)))
PUBLIC_MODE = os.environ.get("COMMUNITY_PUBLIC_MODE", "0") == "1"
PUBLIC_ORIGINS = frozenset({
    "https://localhost",
    "https://meteofriul.app", "https://www.meteofriul.app",
    "https://meteofriul.it", "https://www.meteofriul.it",
})
APP_CHECK_HEADER = "x-firebase-appcheck"
INSTALLATION_HEADER = "x-meteo-pilot-installation"
AUTH_COLLECTION = "pilot_community_installations"
HEX_DIGEST = re.compile(r"^[0-9a-f]{64}$")
BEARER = re.compile(r"^Bearer ([A-Za-z0-9_-]{43})$")


class EnrolledInstallations:
    def __init__(self, client):
        if client.project != PILOT_PROJECT:
            raise ValueError("pilot_project_required")
        self.client = client

    def permits(self, token_digest: str, installation: str) -> bool:
        # No positive authorization cache: revocation applies on the next call.
        record = self.client.collection(AUTH_COLLECTION).document(token_digest).get(timeout=10, retry=None)
        value = record.to_dict() if record.exists else None
        if not isinstance(value, dict):
            return False
        expiry = value.get("expires_at")
        return (
            value.get("active") is True
            and value.get("project") == PILOT_PROJECT
            and isinstance(expiry, datetime) and expiry.tzinfo is not None
            and expiry > datetime.now(timezone.utc)
            and hmac.compare_digest(str(value.get("client_id_sha256", "")), installation)
        )


class IngressBudget:
    """Bound reads/auth work as well as writes; business ledgers stay durable.

    This extra per-instance limiter is not the durable anti-abuse ledger. Cloud
    Run is additionally deployed at max one instance and low concurrency.
    """
    def __init__(self, clock=time.monotonic):
        self.clock = clock
        self.lock = threading.Lock()
        self.requests = defaultdict(deque)

    def accept(self, key: str, limit: int) -> bool:
        with self.lock:
            now = self.clock()
            if len(self.requests) > 1024:
                self.requests = defaultdict(deque, {
                    k: v for k, v in self.requests.items() if v and v[-1] > now - 60
                })
                if key not in self.requests and len(self.requests) > 1024:
                    return False
            entries = self.requests[key]
            while entries and entries[0] <= now - 60:
                entries.popleft()
            if len(entries) >= limit:
                return False
            entries.append(now)
            return True


class ReportQuery(BaseModel):
    lat: float = Field(ge=-90, le=90, allow_inf_nan=False)
    lon: float = Field(ge=-180, le=180, allow_inf_nan=False)
    radius_km: float = Field(default=30, ge=1, le=100)


def _error(status, code, message, *, origin=None):
    headers = {"Cache-Control": "no-store"}
    # Isolation runs outside CORSMiddleware. Its early responses still need to
    # be readable by the enrolled Android WebView's one permitted origin.
    if origin == "https://localhost":
        headers.update({"Access-Control-Allow-Origin": origin, "Vary": "Origin"})
    return JSONResponse(status_code=status, content={"detail": {"code": code, "message": message}},
                        headers=headers)


def create_app(*, service, installations=None, budget=None, public_mode=False,
               app_check_verifier=None, allowed_app_ids=frozenset()) -> FastAPI:
    app = FastAPI(title="Meteo Friul private Community pilot", docs_url=None,
                  redoc_url=None, openapi_url=None)
    limiter = budget or IngressBudget()
    allowed_origins = PUBLIC_ORIGINS if public_mode else frozenset({"https://localhost"})
    app.add_middleware(CORSMiddleware, allow_origins=sorted(allowed_origins),
                       allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
                       allow_headers=["content-type", "authorization", INSTALLATION_HEADER, APP_CHECK_HEADER],
                       expose_headers=["retry-after"], allow_credentials=False)

    @app.middleware("http")
    async def isolation(request: Request, call_next):
        def reject(status, code, message):
            return _error(status, code, message, origin=request.headers.get("origin"))

        if request.headers.get("host", "").lower() not in PILOT_HOSTS:
            return reject(403, "pilot_host_rejected", "Servizio pilota non autorizzato.")
        if request.headers.get("origin") not in ({None} | set(allowed_origins)):
            return reject(403, "pilot_origin_rejected", "Origine non autorizzata.")
        if request.method == "OPTIONS":
            return await call_next(request)
        if request.url.path == "/api/community/health" and request.method == "GET":
            return await call_next(request)
        if not limiter.accept("ingress", 240):
            return reject(429, "pilot_request_limit", "Troppe richieste. Riprova tra poco.")
        installation = request.headers.get(INSTALLATION_HEADER, "")
        public_read = request.method == "GET" or (
            request.method == "POST" and request.url.path in {
                "/api/community/resolve", "/api/community/reports/query",
            }
        )
        if public_mode:
            token_digest = "public-read"
            if not public_read:
                token = request.headers.get(APP_CHECK_HEADER, "").strip()
                if not token:
                    return reject(401, "app_check_required", "Token di sicurezza dell'app richiesto.")
                try:
                    claims = await run_in_threadpool(app_check_verifier, token)
                except ValueError:
                    return reject(401, "app_check_invalid", "Token di sicurezza dell'app non valido.")
                except Exception:
                    return reject(503, "app_check_unavailable", "Verifica di sicurezza non disponibile.")
                app_id = claims.get("app_id") if isinstance(claims, dict) else None
                if not isinstance(app_id, str) or app_id not in allowed_app_ids:
                    return reject(403, "app_check_app_not_allowed", "L'app non è autorizzata.")
                token_digest = "app:" + app_id
        else:
            match = BEARER.fullmatch(request.headers.get("authorization", ""))
            if not match or not HEX_DIGEST.fullmatch(installation):
                return reject(401, "pilot_enrollment_required", "Questa pilota deve essere autorizzata.")
            token_digest = hashlib.sha256(match[1].encode()).hexdigest()
            try:
                permitted = await run_in_threadpool(installations.permits, token_digest, installation)
            except Exception:
                return reject(503, "pilot_auth_unavailable", "Verifica accesso non disponibile. Riprova.")
            if not permitted:
                return reject(401, "pilot_enrollment_required", "Questa pilota deve essere autorizzata.")
        if not limiter.accept(token_digest, 120):
            return reject(429, "pilot_request_limit", "Troppe richieste. Riprova tra poco.")
        if any(key in request.query_params for key in ("lat", "lon", "client_id")):
            return reject(400, "pilot_private_query_rejected", "Usa il percorso protetto per questi dati.")
        if request.method in {"POST", "PATCH", "DELETE"}:
            chunks, size = [], 0
            async for chunk in request.stream():
                size += len(chunk)
                if size > 8192:
                    return reject(413, "pilot_body_too_large", "Richiesta troppo grande.")
                chunks.append(chunk)
            request._body = b"".join(chunks)
            try:
                body = json.loads(request._body)
            except (ValueError, UnicodeDecodeError):
                return reject(422, "pilot_invalid_body", "Parametri non validi.")
            if not isinstance(body, dict):
                return reject(422, "pilot_invalid_body", "Parametri non validi.")
            client_id = body.get("client_id")
            try:
                client_digest = hashlib.sha256(client_id.encode()).hexdigest() if isinstance(client_id, str) else ""
            except UnicodeEncodeError:
                client_digest = ""
            identity_optional = request.url.path in {
                "/api/community/resolve", "/api/community/reports/query",
            }
            if not public_mode and (not identity_optional or client_id is not None) and (
                not isinstance(client_id, str)
                or not hmac.compare_digest(client_digest, installation)
            ):
                return reject(403, "pilot_identity_mismatch", "Identità pilota non corrispondente.")
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Meteo-Community"] = "cloud-public-v2" if public_mode else "cloud-private"
        return response

    @app.exception_handler(CommunityServiceError)
    async def service_error(_request, error):
        seconds = error.detail.get("retry_after_seconds") if isinstance(error.detail, dict) else None
        return JSONResponse(status_code=error.status_code, content={"detail": error.detail},
                            headers={"Retry-After": str(seconds)} if seconds else {})

    @app.exception_handler(CommunityRepositoryUnavailable)
    async def storage_error(_request, _exception):
        return _error(503, "community_storage_unavailable", "Il servizio segnalazioni non è disponibile. Riprova tra poco.")

    @app.exception_handler(RequestValidationError)
    async def validation_error(_request, _exception):
        return _error(422, "pilot_invalid_body", "Parametri della richiesta non validi.")

    @app.exception_handler(PilotCommunityGeographyUnavailable)
    async def geography_error(_request, _exception):
        return _error(503, "pilot_geography_unavailable", "Catalogo geografico non disponibile.")

    @app.get("/api/community/health")
    def health():
        return {"ok": True, "kind": "meteofriul.community.cloud.v2", "project": PILOT_PROJECT,
                "storage": service.repository.storage_kind, "scope": "IT", "published": public_mode,
                "enrollment_required": not public_mode, "app_check": public_mode}

    @app.get("/api/community/reports")
    def reports(istat_code: str = Query(pattern=r"^\d{6}$")):
        return service.get_scoped_reports(istat_code=istat_code)

    @app.post("/api/community/reports/query")
    def reports_by_coordinates(command: ReportQuery):
        return service.get_scoped_reports(**command.model_dump())

    @app.post("/api/community/history")
    def history(command: CommunityHistoryQuery):
        return service.get_history(command)

    @app.post("/api/community/resolve")
    def resolve(command: PilotCommunityResolve):
        return service.resolve_location(command)

    @app.post("/api/community/reports")
    def create(command: PilotCommunityReportCreate):
        return service.create_report(command, client_host="enrolled-cloud-pilot")

    @app.patch("/api/community/reports/{report_id}")
    def update(report_id: str, command: PilotCommunityObservationUpdate):
        return service.update_observation(report_id, command, client_host="enrolled-cloud-pilot")

    @app.post("/api/community/reports/{report_id}/correction")
    def correct(report_id: str, command: PilotCommunityReportCorrection):
        return service.correct_observation(report_id, command, client_host="enrolled-cloud-pilot")

    @app.post("/api/community/operations/{operation_id}")
    def operation(operation_id: str, command: PilotOperation):
        return service.operation_status(operation_id, command)

    @app.delete("/api/community/reports/{report_id}")
    def withdraw(report_id: str, command: PilotCommunityReportDelete):
        return service.delete_report(report_id, command, client_host="enrolled-cloud-pilot")

    @app.post("/api/community/reports/{group_id}/confirmation")
    def confirm(group_id: str, command: CommunityReportVote):
        result = service.confirm_report(group_id, command, client_host="enrolled-cloud-pilot")
        payload = result.model_dump(mode="json", exclude_none=True)
        payload["group"] = service.public_payload(result.group)
        return payload

    @app.post("/api/community/reports/{group_id}/flags")
    def flag(group_id: str, command: CommunityReportFlagCreate):
        return service.flag_report_group(group_id, command, client_host="enrolled-cloud-pilot")

    @app.post("/api/community/reputation")
    def reputation(command: CommunityReputationRequest):
        return service.get_reputation(command, client_host="enrolled-cloud-pilot")

    return app


def create_cloud_app():
    if os.environ.get("GOOGLE_CLOUD_PROJECT") != PILOT_PROJECT:
        raise RuntimeError("pilot_project_required")
    from google.cloud import firestore, storage
    from app.repositories.pilot_community_cloud import PilotCloudCommunityRepository
    firestore_client = firestore.Client(project=PILOT_PROJECT)
    storage_client = storage.Client(project=PILOT_PROJECT)
    repository = PilotCloudCommunityRepository(firestore_client=firestore_client, storage_client=storage_client)
    geography = PilotCommunityGeographyCatalog()
    _ = geography.municipalities
    if PUBLIC_MODE:
        allowed = frozenset(value.strip() for value in os.environ.get(
            "COMMUNITY_APP_CHECK_ALLOWED_APP_IDS", "",
        ).split(",") if value.strip())
        if not allowed:
            raise RuntimeError("community_app_check_allowlist_required")

        def verify(token):
            import firebase_admin
            from firebase_admin import app_check
            try:
                app = firebase_admin.get_app()
            except ValueError:
                app = firebase_admin.initialize_app()
            return app_check.verify_token(token, app=app)

        return create_app(service=CommunityReportsService(geography=geography, repository=repository),
                          public_mode=True, app_check_verifier=verify, allowed_app_ids=allowed)
    return create_app(service=CommunityReportsService(geography=geography, repository=repository),
                      installations=EnrolledInstallations(firestore_client))
