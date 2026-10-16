from __future__ import annotations

import base64
import binascii
import json
import os
from threading import Lock
from typing import Any


_firebase_app: Any | None = None
_firestore_client: Any | None = None
_firebase_app_lock = Lock()
_firestore_client_lock = Lock()


class FirebaseInitializationError(RuntimeError):
    """Firebase Admin could not be initialized for this request."""


def community_storage_mode() -> str:
    mode = os.getenv("COMMUNITY_STORAGE", "memory").strip().lower()
    if mode not in {"memory", "firestore", "auto"}:
        return "invalid"
    if mode == "memory" and os.getenv("K_SERVICE", "").strip():
        # A deployed UGC API must never acknowledge writes held only inside one
        # ephemeral Cloud Run instance.
        return "invalid"
    return mode


def _firebase_is_configured() -> bool:
    return any(
        os.getenv(name, "").strip()
        for name in (
            "FIREBASE_SERVICE_ACCOUNT_JSON",
            "FIREBASE_SERVICE_ACCOUNT_B64",
            "FIREBASE_CREDENTIALS_PATH",
            "GOOGLE_APPLICATION_CREDENTIALS",
            "FIREBASE_PROJECT_ID",
        )
    ) or bool(os.getenv("K_SERVICE", "").strip())


def get_firebase_app() -> Any:
    """Return the shared default Firebase app, initializing it exactly once."""

    global _firebase_app

    if _firebase_app is not None:
        return _firebase_app

    with _firebase_app_lock:
        if _firebase_app is not None:
            return _firebase_app

        try:
            import firebase_admin
            from firebase_admin import credentials

            try:
                firebase_app = firebase_admin.get_app()
            except ValueError:
                credential = _build_credential(credentials)
                project_id = os.getenv("FIREBASE_PROJECT_ID", "").strip()
                options = {"projectId": project_id} if project_id else None
                firebase_app = firebase_admin.initialize_app(credential, options)
        except Exception as error:
            raise FirebaseInitializationError from error

        _firebase_app = firebase_app
        return _firebase_app


def get_firestore_client() -> Any | None:
    """Return Firestore only when persistence is explicitly enabled."""

    global _firestore_client

    mode = community_storage_mode()
    if mode not in {"firestore", "auto"}:
        return None
    if mode == "auto" and not _firebase_is_configured():
        return None
    if _firestore_client is not None:
        return _firestore_client

    with _firestore_client_lock:
        if _firestore_client is not None:
            return _firestore_client

        try:
            from firebase_admin import firestore

            firebase_app = get_firebase_app()
            _firestore_client = firestore.client(firebase_app)
        except (
            FirebaseInitializationError,
            ImportError,
            OSError,
            TypeError,
            ValueError,
            UnicodeDecodeError,
            binascii.Error,
            json.JSONDecodeError,
        ):
            return None

    return _firestore_client


def _build_credential(credentials_module: Any) -> Any:
    raw_json = os.getenv("FIREBASE_SERVICE_ACCOUNT_JSON", "").strip()
    encoded_json = os.getenv("FIREBASE_SERVICE_ACCOUNT_B64", "").strip()
    credentials_path = (
        os.getenv("FIREBASE_CREDENTIALS_PATH", "").strip()
        or os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "").strip()
    )

    if raw_json:
        return credentials_module.Certificate(json.loads(raw_json))
    if encoded_json:
        decoded = base64.b64decode(encoded_json).decode("utf-8")
        return credentials_module.Certificate(json.loads(decoded))
    if credentials_path:
        return credentials_module.Certificate(credentials_path)
    return credentials_module.ApplicationDefault()


def reset_firestore_client_for_tests() -> None:
    """Clear process-local Firebase caches without deleting the SDK app."""

    global _firebase_app, _firestore_client

    with _firestore_client_lock:
        _firestore_client = None
        with _firebase_app_lock:
            _firebase_app = None
