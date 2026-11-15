"""The existing Firebase login, restricted to the verified panel owner."""
import os
from typing import Annotated

from fastapi import Header, HTTPException
from app.infrastructure.firebase import get_firebase_app


def require_events_admin(authorization: Annotated[str | None, Header(alias="Authorization")] = None):
    scheme, _, token = str(authorization or "").strip().partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(401, detail={"code": "events_login_required"})
    try:
        from firebase_admin import auth
        claims = auth.verify_id_token(token, app=get_firebase_app(), check_revoked=True)
    except Exception as error:
        raise HTTPException(401, detail={"code": "events_login_invalid"}) from error
    allowed = os.getenv("EVENTS_ADMIN_EMAIL", "meteofriul@gmail.com").strip().lower()
    if not allowed or claims.get("email_verified") is not True or str(claims.get("email", "")).lower() != allowed:
        raise HTTPException(403, detail={"code": "events_admin_forbidden"})
    return {"uid": str(claims.get("uid") or claims.get("sub") or "")[:128],
            "email": allowed}
