"""Grant the editorial role to an existing Firebase login without replacing other roles."""
from __future__ import annotations

import argparse
import json
from typing import Any

from app.infrastructure.firebase import get_firebase_app


def build_editorial_admin_claims(current_claims: dict[str, Any] | None, *, enabled: bool) -> dict[str, Any]:
    claims = dict(current_claims or {})
    if enabled:
        claims["editorialAdmin"] = True
    else:
        claims.pop("editorialAdmin", None)
    return claims


def main() -> int:
    parser = argparse.ArgumentParser(description="Grant or revoke the editorialAdmin Firebase claim.")
    parser.add_argument("--email", required=True, help="Exact Firebase Auth email.")
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--enable", action="store_true")
    action.add_argument("--disable", action="store_true")
    parser.add_argument("--apply", action="store_true", help="Persist the change; otherwise dry run.")
    args = parser.parse_args()

    from firebase_admin import auth

    app = get_firebase_app()
    user = auth.get_user_by_email(args.email.strip(), app=app)
    if user.email != args.email.strip():
        raise ValueError("editorial_email_mismatch")
    claims = build_editorial_admin_claims(user.custom_claims, enabled=args.enable)
    if args.apply:
        auth.set_custom_user_claims(user.uid, claims, app=app)
        actual = auth.get_user(user.uid, app=app).custom_claims or {}
        if actual != claims:
            raise RuntimeError("editorial_claim_readback_mismatch")
    print(json.dumps({"email": user.email, "editorialAdmin": claims.get("editorialAdmin") is True,
                      "otherClaimsPreserved": all(claims.get(key) == value for key, value in (user.custom_claims or {}).items()
                                                  if key != "editorialAdmin"), "applied": bool(args.apply)},
                     ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
