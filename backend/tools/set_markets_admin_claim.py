"""Grant or revoke the dedicated Markets permission on an existing panel account."""
from __future__ import annotations

import argparse
import json
from typing import Any

from app.infrastructure.firebase import get_firebase_app


EXPECTED_PROJECT = "meteo-friul"


def build_markets_admin_claims(current: dict[str, Any] | None, *, enabled: bool) -> dict[str, Any]:
    claims = dict(current or {})
    if enabled:
        claims["marketsAdmin"] = True
    else:
        claims.pop("marketsAdmin", None)
    return claims


def main() -> int:
    parser = argparse.ArgumentParser(description="Change the Markets permission for an existing Firebase account.")
    parser.add_argument("--email", required=True, help="Exact Firebase Auth email.")
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--enable", action="store_true")
    action.add_argument("--disable", action="store_true")
    parser.add_argument("--apply", action="store_true", help="Persist the change; otherwise dry run.")
    args = parser.parse_args()

    from firebase_admin import auth

    app = get_firebase_app()
    if app.project_id != EXPECTED_PROJECT:
        raise SystemExit("Unexpected Firebase project; no claim changed")
    user = auth.get_user_by_email(args.email.strip(), app=app)
    before = dict(user.custom_claims or {})
    after = build_markets_admin_claims(before, enabled=args.enable)
    if args.apply and after != before:
        auth.set_custom_user_claims(user.uid, after, app=app)
    print(json.dumps({"project": app.project_id, "applied": bool(args.apply and after != before),
                      "marketsAdmin": after.get("marketsAdmin") is True,
                      "otherClaimsPreserved": all(after.get(key) == value for key, value in before.items()
                                                  if key != "marketsAdmin")}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
