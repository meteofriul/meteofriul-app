"""Mercati authorization is deliberately independent of Sponsor and Webcam."""
from __future__ import annotations

from dataclasses import dataclass
import hmac
import os
from typing import Annotated, Any

from fastapi import Header, HTTPException

from app.infrastructure.firebase import get_firebase_app


@dataclass(frozen=True)
class MarketsAdminContext:
    uid: str
    claims: dict[str, Any]


def _reject(status, code):
    raise HTTPException(status_code=status, detail={"code": code})


def require_markets_admin(authorization: Annotated[str | None, Header(alias="Authorization")] = None) -> MarketsAdminContext:
    scheme, _, token = str(authorization or "").strip().partition(" ")
    token = token.strip()
    if scheme.lower() != "bearer" or not token:
        _reject(401, "markets_admin_auth_required")
    mode = os.getenv("MARKETS_ADMIN_AUTH_MODE", "firebase").strip().lower()
    if mode == "local":
        if os.getenv("K_SERVICE", "").strip():
            _reject(503, "markets_admin_local_auth_forbidden")
        expected = os.getenv("MARKETS_ADMIN_LOCAL_TOKEN", "").strip()
        if not expected or not hmac.compare_digest(token.encode(), expected.encode()):
            _reject(403, "markets_admin_forbidden")
        return MarketsAdminContext("local-markets-admin", {"marketsAdmin": True, "local": True})
    if mode != "firebase":
        _reject(503, "markets_admin_auth_configuration_invalid")
    try:
        from firebase_admin import auth
        claims = dict(auth.verify_id_token(token, app=get_firebase_app(), check_revoked=True) or {})
    except Exception:
        _reject(401, "markets_admin_token_invalid")
    if claims.get("marketsAdmin") is not True:
        _reject(403, "markets_admin_claim_required")
    uid = str(claims.get("uid") or claims.get("sub") or "").strip()
    if not uid:
        _reject(403, "markets_admin_uid_required")
    return MarketsAdminContext(uid, claims)
