"""Firebase login and a dedicated role for editorial publication."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated

from fastapi import Header, HTTPException

from app.infrastructure.firebase import get_firebase_app


@dataclass(frozen=True)
class EditorialAdminContext:
    uid: str


def require_editorial_admin(
    authorization: Annotated[str | None, Header(alias="Authorization")] = None,
) -> EditorialAdminContext:
    scheme, _, token = str(authorization or "").strip().partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise HTTPException(401, detail={"code": "editorial_auth_required"})
    try:
        from firebase_admin import auth

        claims = dict(auth.verify_id_token(token.strip(), app=get_firebase_app(), check_revoked=True) or {})
    except Exception as error:
        raise HTTPException(401, detail={"code": "editorial_token_invalid"}) from error
    if claims.get("editorialAdmin") is not True:
        raise HTTPException(403, detail={"code": "editorial_permission_required"})
    uid = str(claims.get("uid") or claims.get("sub") or "").strip()
    if not uid:
        raise HTTPException(403, detail={"code": "editorial_uid_required"})
    return EditorialAdminContext(uid)
