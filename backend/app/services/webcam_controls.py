from __future__ import annotations

import copy
import os
import re
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from functools import lru_cache
from threading import RLock
from typing import Any, Callable, Iterable

from app.contracts.live import WebcamManifestResponse, WebcamRecord
from app.infrastructure.firebase import get_firestore_client


CONTROL_COLLECTION = "webcam_admin_state"
CONTROL_DOCUMENT = "current"
PUBLIC_CONTROL_CACHE_SECONDS = 60
MAX_CONTROL_REASON_LENGTH = 500
MAX_CONTROL_CHANGES = 500
WEBCAM_ID_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


class WebcamControlConflict(RuntimeError):
    pass


class WebcamControlStorageUnavailable(RuntimeError):
    pass


class WebcamControlValidationError(ValueError):
    pass


def _now_iso(now: datetime | None = None) -> str:
    selected = now or datetime.now(timezone.utc)
    return selected.astimezone(timezone.utc).isoformat()


def _timestamp_iso(value: Any) -> str:
    if isinstance(value, datetime):
        return _now_iso(value)
    return str(value or "").strip()[:64]


def _clean_reason(value: Any) -> str:
    reason = str(value or "").strip()
    if len(reason) > MAX_CONTROL_REASON_LENGTH:
        raise WebcamControlValidationError("webcam_control_reason_too_long")
    if any(ord(character) < 32 and character not in "\t\n\r" for character in reason):
        raise WebcamControlValidationError("webcam_control_reason_invalid")
    return reason


def _sanitize_stored_controls(value: Any) -> dict[str, dict[str, Any]]:
    if not isinstance(value, dict):
        return {}
    controls: dict[str, dict[str, Any]] = {}
    for raw_id, raw_control in value.items():
        webcam_id = str(raw_id or "").strip()
        if not WEBCAM_ID_PATTERN.fullmatch(webcam_id) or not isinstance(raw_control, dict):
            continue
        enabled = raw_control.get("previewEnabled")
        if not isinstance(enabled, bool):
            continue
        try:
            reason = _clean_reason(raw_control.get("reason"))
        except WebcamControlValidationError:
            reason = ""
        controls[webcam_id] = {
            "previewEnabled": enabled,
            "reason": reason,
            "updatedAt": _timestamp_iso(raw_control.get("updatedAt")),
            "updatedByUid": str(raw_control.get("updatedByUid") or "").strip()[:128],
            "updatedByEmail": str(raw_control.get("updatedByEmail") or "").strip()[:320],
        }
    return controls


def validate_control_changes(
    value: Any,
    *,
    manifest: WebcamManifestResponse,
) -> list[dict[str, Any]]:
    if not isinstance(value, list) or not value:
        raise WebcamControlValidationError("webcam_control_changes_required")
    if len(value) > MAX_CONTROL_CHANGES:
        raise WebcamControlValidationError("webcam_control_changes_too_many")

    catalog = {record.id: record for record in manifest.webcams}
    changes: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw_change in value:
        if not isinstance(raw_change, dict):
            raise WebcamControlValidationError("webcam_control_change_invalid")
        webcam_id = str(raw_change.get("webcamId") or "").strip()
        if not WEBCAM_ID_PATTERN.fullmatch(webcam_id):
            raise WebcamControlValidationError("webcam_control_id_invalid")
        if webcam_id in seen:
            raise WebcamControlValidationError("webcam_control_duplicate_id")
        seen.add(webcam_id)
        record = catalog.get(webcam_id)
        if record is None:
            raise WebcamControlValidationError("webcam_control_unknown_id")
        enabled = raw_change.get("previewEnabled")
        if not isinstance(enabled, bool):
            raise WebcamControlValidationError("webcam_control_enabled_invalid")
        if not enabled and not (record.imageUrl or record.playerUrl):
            raise WebcamControlValidationError("webcam_control_preview_not_available")
        changes.append({
            "webcamId": webcam_id,
            "previewEnabled": enabled,
            "reason": _clean_reason(raw_change.get("reason")),
        })
    return changes


@dataclass(frozen=True)
class WebcamControlSnapshot:
    controls: dict[str, dict[str, Any]]
    revision: int
    storage: str
    updated_at: str = ""
    updated_by_uid: str = ""
    updated_by_email: str = ""


class WebcamControlRepository:
    def __init__(self, firestore_provider: Callable[[], Any | None]):
        self._firestore_provider = firestore_provider
        self._lock = RLock()
        self._controls: dict[str, dict[str, Any]] = {}
        self._revision = 0
        self._updated_at = ""
        self._updated_by_uid = ""
        self._updated_by_email = ""

    def _db(self) -> Any | None:
        try:
            return self._firestore_provider()
        except Exception:
            return None

    @staticmethod
    def _persistent_required() -> bool:
        return bool(os.getenv("K_SERVICE", "").strip())

    def read_state(self) -> WebcamControlSnapshot:
        db = self._db()
        if db is not None:
            try:
                snapshot = db.collection(CONTROL_COLLECTION).document(CONTROL_DOCUMENT).get()
                if not snapshot.exists:
                    return WebcamControlSnapshot({}, 0, "firestore_empty")
                payload = dict(snapshot.to_dict() or {})
                return WebcamControlSnapshot(
                    controls=_sanitize_stored_controls(payload.get("controls")),
                    revision=max(0, int(payload.get("revision", 0))),
                    storage="firestore",
                    updated_at=_timestamp_iso(payload.get("updated_at")),
                    updated_by_uid=str(payload.get("updated_by_uid") or "").strip()[:128],
                    updated_by_email=str(payload.get("updated_by_email") or "").strip()[:320],
                )
            except Exception as error:
                raise WebcamControlStorageUnavailable("webcam_control_state_read_failed") from error
        if self._persistent_required():
            raise WebcamControlStorageUnavailable("webcam_control_firestore_required")
        with self._lock:
            return WebcamControlSnapshot(
                controls=copy.deepcopy(self._controls),
                revision=self._revision,
                storage="memory",
                updated_at=self._updated_at,
                updated_by_uid=self._updated_by_uid,
                updated_by_email=self._updated_by_email,
            )

    @staticmethod
    def _apply_changes(
        controls: dict[str, dict[str, Any]],
        changes: Iterable[dict[str, Any]],
        *,
        actor_uid: str,
        actor_email: str,
        changed_at: str,
    ) -> dict[str, dict[str, Any]]:
        updated = copy.deepcopy(controls)
        for change in changes:
            updated[change["webcamId"]] = {
                "previewEnabled": change["previewEnabled"],
                "reason": change["reason"],
                "updatedAt": changed_at,
                "updatedByUid": actor_uid[:128],
                "updatedByEmail": actor_email[:320],
            }
        return updated

    def write_changes(
        self,
        changes: list[dict[str, Any]],
        *,
        expected_revision: int | None,
        actor_uid: str,
        actor_email: str,
    ) -> WebcamControlSnapshot:
        db = self._db()
        changed_at = _now_iso()
        if db is not None:
            try:
                from google.cloud import firestore

                document = db.collection(CONTROL_COLLECTION).document(CONTROL_DOCUMENT)
                transaction = db.transaction()

                @firestore.transactional
                def persist(transaction_in_progress: Any) -> tuple[int, dict[str, dict[str, Any]]]:
                    snapshot = document.get(transaction=transaction_in_progress)
                    payload = dict(snapshot.to_dict() or {}) if snapshot.exists else {}
                    current_revision = max(0, int(payload.get("revision", 0)))
                    if expected_revision is not None and expected_revision != current_revision:
                        raise WebcamControlConflict("webcam_control_revision_conflict")
                    controls = self._apply_changes(
                        _sanitize_stored_controls(payload.get("controls")),
                        changes,
                        actor_uid=actor_uid,
                        actor_email=actor_email,
                        changed_at=changed_at,
                    )
                    next_revision = current_revision + 1
                    transaction_in_progress.set(document, {
                        "revision": next_revision,
                        "controls": controls,
                        "updated_at": datetime.now(timezone.utc),
                        "updated_by_uid": actor_uid,
                        "updated_by_email": actor_email,
                    }, merge=False)
                    return next_revision, controls

                revision, controls = persist(transaction)
                return WebcamControlSnapshot(
                    controls=controls,
                    revision=revision,
                    storage="firestore",
                    updated_at=changed_at,
                    updated_by_uid=actor_uid,
                    updated_by_email=actor_email,
                )
            except WebcamControlConflict:
                raise
            except Exception as error:
                raise WebcamControlStorageUnavailable("webcam_control_state_write_failed") from error
        if self._persistent_required():
            raise WebcamControlStorageUnavailable("webcam_control_firestore_required")
        with self._lock:
            if expected_revision is not None and expected_revision != self._revision:
                raise WebcamControlConflict("webcam_control_revision_conflict")
            self._controls = self._apply_changes(
                self._controls,
                changes,
                actor_uid=actor_uid,
                actor_email=actor_email,
                changed_at=changed_at,
            )
            self._revision += 1
            self._updated_at = changed_at
            self._updated_by_uid = actor_uid[:128]
            self._updated_by_email = actor_email[:320]
            return WebcamControlSnapshot(
                controls=copy.deepcopy(self._controls),
                revision=self._revision,
                storage="memory",
                updated_at=self._updated_at,
                updated_by_uid=self._updated_by_uid,
                updated_by_email=self._updated_by_email,
            )


class WebcamControlService:
    def __init__(
        self,
        repository: WebcamControlRepository,
        *,
        now: Callable[[], float] = time.time,
        cache_seconds: int = PUBLIC_CONTROL_CACHE_SECONDS,
    ) -> None:
        self.repository = repository
        self.now = now
        self.cache_seconds = max(0, int(cache_seconds))
        self._cache: tuple[float, WebcamControlSnapshot] | None = None
        self._cache_lock = RLock()

    def _public_snapshot(self) -> WebcamControlSnapshot:
        with self._cache_lock:
            if self._cache and self.now() - self._cache[0] <= self.cache_seconds:
                return self._cache[1]
            snapshot = self.repository.read_state()
            self._cache = (self.now(), snapshot)
            return snapshot

    def _store_snapshot(self, snapshot: WebcamControlSnapshot) -> None:
        with self._cache_lock:
            self._cache = (self.now(), snapshot)

    @staticmethod
    def _without_preview(record: WebcamRecord) -> WebcamRecord:
        return record.model_copy(update={
            "imageUrl": None,
            "mediaType": None,
            "playerUrl": None,
        })

    def apply_public_controls(
        self,
        manifest: WebcamManifestResponse,
    ) -> WebcamManifestResponse:
        if not manifest.ok or not manifest.webcams:
            return manifest
        try:
            snapshot = self._public_snapshot()
        except WebcamControlStorageUnavailable:
            # A deployed API must never revive previews when the control plane
            # cannot confirm their current state. Existing fallbacks remain.
            return manifest.model_copy(update={
                "webcams": [self._without_preview(record) for record in manifest.webcams],
            })
        disabled = {
            webcam_id
            for webcam_id, control in snapshot.controls.items()
            if control.get("previewEnabled") is False
        }
        if not disabled:
            return manifest
        return manifest.model_copy(update={
            "webcams": [
                self._without_preview(record) if record.id in disabled else record
                for record in manifest.webcams
            ],
        })

    @staticmethod
    def _admin_payload(
        snapshot: WebcamControlSnapshot,
        manifest: WebcamManifestResponse,
    ) -> dict[str, Any]:
        webcams = []
        for record in manifest.webcams:
            control = snapshot.controls.get(record.id) or {}
            webcams.append({
                "id": record.id,
                "name": record.name,
                "municipality": record.municipality or "",
                "area": record.area,
                "provider": record.provider,
                "sourcePage": record.sourcePage,
                "hasPreview": bool(record.imageUrl or record.playerUrl),
                "hasFallback": bool(record.fallbackImageUrl),
                "previewEnabled": control.get("previewEnabled") is not False,
                "reason": str(control.get("reason") or ""),
                "updatedAt": str(control.get("updatedAt") or ""),
                "updatedByEmail": str(control.get("updatedByEmail") or ""),
            })
        return {
            "revision": snapshot.revision,
            "storage": snapshot.storage,
            "updatedAt": snapshot.updated_at,
            "updatedByEmail": snapshot.updated_by_email,
            "webcams": webcams,
        }

    def admin_state(self, manifest: WebcamManifestResponse) -> dict[str, Any]:
        snapshot = self.repository.read_state()
        self._store_snapshot(snapshot)
        return self._admin_payload(snapshot, manifest)

    def update_previews(
        self,
        changes: Any,
        *,
        manifest: WebcamManifestResponse,
        expected_revision: int | None,
        actor_uid: str,
        actor_email: str,
    ) -> dict[str, Any]:
        validated = validate_control_changes(changes, manifest=manifest)
        snapshot = self.repository.write_changes(
            validated,
            expected_revision=expected_revision,
            actor_uid=actor_uid,
            actor_email=actor_email,
        )
        self._store_snapshot(snapshot)
        return self._admin_payload(snapshot, manifest)


@lru_cache(maxsize=1)
def get_webcam_control_service() -> WebcamControlService:
    return WebcamControlService(WebcamControlRepository(get_firestore_client))
