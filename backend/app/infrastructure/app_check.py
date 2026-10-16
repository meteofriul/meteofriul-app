from __future__ import annotations

import os
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any, Annotated, Literal

from fastapi import Depends, HTTPException, Request, status

from app.infrastructure.firebase import (
    FirebaseInitializationError,
    community_storage_mode,
    get_firebase_app,
)


APP_CHECK_HEADER = "X-Firebase-AppCheck"
COMMUNITY_APP_CHECK_MODE_ENV = "COMMUNITY_APP_CHECK_MODE"
COMMUNITY_APP_CHECK_ALLOWED_APP_IDS_ENV = "COMMUNITY_APP_CHECK_ALLOWED_APP_IDS"
PUSH_APP_CHECK_MODE_ENV = "PUSH_APP_CHECK_MODE"
PUSH_APP_CHECK_ALLOWED_APP_IDS_ENV = "PUSH_APP_CHECK_ALLOWED_APP_IDS"
PUSH_APP_CHECK_ANDROID_APP_IDS_ENV = "PUSH_APP_CHECK_ANDROID_APP_IDS"
PUSH_APP_CHECK_WEB_APP_IDS_ENV = "PUSH_APP_CHECK_WEB_APP_IDS"

AppCheckClaims = Mapping[str, Any]
AppCheckVerifier = Callable[[str], AppCheckClaims]


@dataclass(frozen=True)
class PushAppCheckContext:
    claims: AppCheckClaims | None
    app_id: str = ""
    platform: Literal["android", "web"] | None = None


class AppCheckTokenInvalid(Exception):
    """The supplied token could not be authenticated."""


class AppCheckVerifierUnavailable(Exception):
    """The server could not perform App Check verification."""


def community_app_check_mode() -> str:
    """Return a safe mutation gate mode for local or deployed execution."""

    configured_mode = os.getenv(COMMUNITY_APP_CHECK_MODE_ENV, "").strip().lower()
    deployed = bool(os.getenv("K_SERVICE", "").strip())
    storage_mode = community_storage_mode()
    if storage_mode == "invalid":
        return "invalid"
    persistent = storage_mode in {"firestore", "auto"}

    if not configured_mode:
        return "enforce" if deployed or persistent else "off"
    if configured_mode == "off" and (deployed or persistent):
        return "invalid"
    return configured_mode


def allowed_community_app_ids() -> frozenset[str]:
    raw_ids = os.getenv(COMMUNITY_APP_CHECK_ALLOWED_APP_IDS_ENV, "")
    return frozenset(
        app_id.strip() for app_id in raw_ids.split(",") if app_id.strip()
    )


def push_app_check_mode() -> str:
    """Return the App Check gate used by Android push mutations.

    Push may be enabled before the community feature is published, so it has
    its own environment switch. Falling back to the community setting keeps a
    single Android App Check allowlist usable during the private pilot.
    """

    configured_mode = os.getenv(PUSH_APP_CHECK_MODE_ENV, "").strip().lower()
    if not configured_mode:
        configured_mode = os.getenv(COMMUNITY_APP_CHECK_MODE_ENV, "").strip().lower()

    deployed = bool(os.getenv("K_SERVICE", "").strip())
    storage_mode = community_storage_mode()
    if storage_mode == "invalid":
        return "invalid"
    persistent = storage_mode in {"firestore", "auto"}
    if not configured_mode:
        return "enforce" if deployed or persistent else "off"
    if configured_mode == "off" and (deployed or persistent):
        return "invalid"
    return configured_mode


def allowed_push_app_ids() -> frozenset[str]:
    mapping = allowed_push_app_ids_by_platform()
    return mapping["android"] | mapping["web"]


def _app_ids(raw_ids: str) -> frozenset[str]:
    return frozenset(
        app_id.strip() for app_id in raw_ids.split(",") if app_id.strip()
    )


def allowed_push_app_ids_by_platform() -> dict[str, frozenset[str]]:
    """Return fail-closed App Check allowlists for each push client.

    The legacy push/community fallback remains Android-only. Web registrations
    must always be explicitly authorized with their Firebase Web App ID.
    """

    raw_android_ids = os.getenv(PUSH_APP_CHECK_ANDROID_APP_IDS_ENV, "").strip()
    if not raw_android_ids:
        raw_android_ids = os.getenv(PUSH_APP_CHECK_ALLOWED_APP_IDS_ENV, "").strip()
    if not raw_android_ids:
        raw_android_ids = os.getenv(COMMUNITY_APP_CHECK_ALLOWED_APP_IDS_ENV, "")
    return {
        "android": _app_ids(raw_android_ids),
        "web": _app_ids(os.getenv(PUSH_APP_CHECK_WEB_APP_IDS_ENV, "")),
    }


def verify_firebase_app_check_token(token: str) -> AppCheckClaims:
    """Verify one Firebase App Check token without initializing at import time."""

    try:
        from firebase_admin import app_check

        firebase_app = get_firebase_app()
    except (FirebaseInitializationError, ImportError) as error:
        raise AppCheckVerifierUnavailable from error

    if not firebase_app.project_id:
        raise AppCheckVerifierUnavailable

    try:
        return app_check.verify_token(token, app=firebase_app)
    except ValueError as error:
        raise AppCheckTokenInvalid from error
    except Exception as error:
        raise AppCheckVerifierUnavailable from error


def get_app_check_verifier() -> AppCheckVerifier:
    """FastAPI dependency seam used by tests and future verifier variants."""

    return verify_firebase_app_check_token


def _reject(status_code: int, message: str, code: str) -> None:
    raise HTTPException(
        status_code=status_code,
        detail={"message": message, "code": code},
    )


def require_community_app_check(
    request: Request,
    verifier: Annotated[AppCheckVerifier, Depends(get_app_check_verifier)],
) -> AppCheckClaims | None:
    """Protect community mutations while leaving public reads untouched."""

    mode = community_app_check_mode()
    if mode == "off":
        return None
    if mode != "enforce":
        _reject(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Configurazione di sicurezza dell'app non valida.",
            "app_check_configuration_invalid",
        )

    allowed_app_ids = allowed_community_app_ids()
    if not allowed_app_ids:
        _reject(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Allowlist App Check non configurata.",
            "app_check_configuration_invalid",
        )

    token = request.headers.get(APP_CHECK_HEADER, "").strip()
    if not token:
        _reject(
            status.HTTP_401_UNAUTHORIZED,
            "Token di sicurezza dell'app richiesto.",
            "app_check_required",
        )

    try:
        claims = verifier(token)
    except AppCheckTokenInvalid:
        _reject(
            status.HTTP_401_UNAUTHORIZED,
            "Token di sicurezza dell'app non valido.",
            "app_check_invalid",
        )
    except AppCheckVerifierUnavailable:
        _reject(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Verifica di sicurezza temporaneamente non disponibile.",
            "app_check_unavailable",
        )
    except Exception:
        _reject(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Verifica di sicurezza temporaneamente non disponibile.",
            "app_check_unavailable",
        )

    app_id = claims.get("app_id")
    if not isinstance(app_id, str) or not app_id:
        _reject(
            status.HTTP_401_UNAUTHORIZED,
            "Token di sicurezza dell'app non valido.",
            "app_check_invalid",
        )
    if app_id not in allowed_app_ids:
        _reject(
            status.HTTP_403_FORBIDDEN,
            "L'app non e' autorizzata a inviare segnalazioni.",
            "app_check_app_not_allowed",
        )
    return claims


def require_push_app_check(
    request: Request,
    verifier: Annotated[AppCheckVerifier, Depends(get_app_check_verifier)],
) -> PushAppCheckContext:
    """Authenticate push mutations and bind the Firebase app to a platform."""

    mode = push_app_check_mode()
    if mode == "off":
        return PushAppCheckContext(claims=None)
    if mode != "enforce":
        _reject(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Configurazione di sicurezza push non valida.",
            "app_check_configuration_invalid",
        )

    allowed_by_platform = allowed_push_app_ids_by_platform()
    if allowed_by_platform["android"] & allowed_by_platform["web"]:
        _reject(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Allowlist App Check push ambigua.",
            "app_check_configuration_invalid",
        )
    allowed_app_ids = allowed_by_platform["android"] | allowed_by_platform["web"]
    if not allowed_app_ids:
        _reject(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Allowlist App Check push non configurata.",
            "app_check_configuration_invalid",
        )

    token = request.headers.get(APP_CHECK_HEADER, "").strip()
    if not token:
        _reject(
            status.HTTP_401_UNAUTHORIZED,
            "Token di sicurezza dell'app richiesto.",
            "app_check_required",
        )

    try:
        claims = verifier(token)
    except AppCheckTokenInvalid:
        _reject(
            status.HTTP_401_UNAUTHORIZED,
            "Token di sicurezza dell'app non valido.",
            "app_check_invalid",
        )
    except AppCheckVerifierUnavailable:
        _reject(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Verifica di sicurezza temporaneamente non disponibile.",
            "app_check_unavailable",
        )
    except Exception:
        _reject(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Verifica di sicurezza temporaneamente non disponibile.",
            "app_check_unavailable",
        )

    app_id = claims.get("app_id")
    if not isinstance(app_id, str) or not app_id:
        _reject(
            status.HTTP_401_UNAUTHORIZED,
            "Token di sicurezza dell'app non valido.",
            "app_check_invalid",
        )
    if app_id not in allowed_app_ids:
        _reject(
            status.HTTP_403_FORBIDDEN,
            "L'app non e' autorizzata al pilot push.",
            "app_check_app_not_allowed",
        )
    platform: Literal["android", "web"] = (
        "web" if app_id in allowed_by_platform["web"] else "android"
    )
    return PushAppCheckContext(
        claims=claims,
        app_id=app_id,
        platform=platform,
    )
