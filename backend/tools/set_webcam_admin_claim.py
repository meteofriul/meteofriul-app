from __future__ import annotations

import argparse
import json
from typing import Any

from app.infrastructure.firebase import get_firebase_app


def build_webcam_admin_claims(
    current_claims: dict[str, Any] | None,
    *,
    enabled: bool,
) -> dict[str, Any]:
    claims = dict(current_claims or {})
    if enabled:
        claims["webcamAdmin"] = True
    else:
        claims.pop("webcamAdmin", None)
    return claims


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Grant or revoke the Firebase webcamAdmin custom claim.",
    )
    parser.add_argument("--email", required=True, help="Exact Firebase Auth email.")
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--enable", action="store_true", help="Grant webcamAdmin.")
    action.add_argument("--disable", action="store_true", help="Revoke webcamAdmin.")
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Persist the change. Without this flag the command is a dry run.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    from firebase_admin import auth

    firebase_app = get_firebase_app()
    user = auth.get_user_by_email(args.email.strip(), app=firebase_app)
    claims = build_webcam_admin_claims(user.custom_claims, enabled=args.enable)
    outcome = {
        "action": "enable" if args.enable else "disable",
        "webcamAdmin": claims.get("webcamAdmin") is True,
        "applied": bool(args.apply),
        "email": user.email,
        "uid": user.uid,
    }
    if args.apply:
        auth.set_custom_user_claims(user.uid, claims, app=firebase_app)
    print(json.dumps(outcome, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
