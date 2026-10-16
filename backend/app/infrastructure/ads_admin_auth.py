from __future__ import annotations

import hmac
import os
from dataclasses import dataclass
from typing import Annotated, Any

from fastapi import Header, HTTPException, status

from app.infrastructure.firebase import get_firebase_app


ADS_ADMIN_AUTH_MODE_ENV = "ADS_ADMIN_AUTH_MODE"
ADS_ADMIN_LOCAL_TOKEN_ENV = "ADS_ADMIN_LOCAL_TOKEN"


@dataclass(frozen=True)
class AdsAdminContext:
    uid: str
    email: str
    claims: dict[str, Any]


def _bearer_token(authorization: str | None) -> str:
    scheme, _, token = str(authorization or "").strip().partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "ads_admin_auth_required"},
        )
    return token.strip()


def require_ads_admin(
    authorization: Annotated[str | None, Header(alias="Authorization")] = None,
) -> AdsAdminContext:
    token = _bearer_token(authorization)
    mode = os.getenv(ADS_ADMIN_AUTH_MODE_ENV, "firebase").strip().lower()

    if mode == "local":
        if os.getenv("K_SERVICE", "").strip():
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={"code": "ads_admin_local_auth_forbidden"},
            )
        expected = os.getenv(ADS_ADMIN_LOCAL_TOKEN_ENV, "").strip()
        if not expected or not hmac.compare_digest(token, expected):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"code": "ads_admin_forbidden"},
            )
        return AdsAdminContext(
            uid="local-ads-admin",
            email="local@meteofriul.invalid",
            claims={"adsAdmin": True, "local": True},
        )

    if mode != "firebase":
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"code": "ads_admin_auth_configuration_invalid"},
        )

    try:
        from firebase_admin import auth

        claims = dict(
            auth.verify_id_token(
                token,
                app=get_firebase_app(),
                check_revoked=True,
            )
            or {}
        )
    except Exception as error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "ads_admin_token_invalid"},
        ) from error

    if claims.get("adsAdmin") is not True:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "ads_admin_claim_required"},
        )
    uid = str(claims.get("uid") or claims.get("sub") or "").strip()
    if not uid:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "ads_admin_uid_required"},
        )
    return AdsAdminContext(
        uid=uid,
        email=str(claims.get("email") or "").strip()[:320],
        claims=claims,
    )
