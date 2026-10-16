"""Contracts for the local durable weather-pipeline state store.

The idempotency key is deliberately explicit: provider, source run and the
SHA-256 of the canonical provider request.  A lease only grants temporary
ownership; its monotonically increasing fencing token must accompany every
mutation so that a worker which lost its lease cannot resume writing.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
import re
from typing import Any, Mapping, Protocol


_RUN_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}\Z")
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")


class Provider(str, Enum):
    ICON = "icon"
    CAMS = "cams"


class RunState(str, Enum):
    CLAIMED = "CLAIMED"
    INTENT = "INTENT"
    SUBMITTED = "SUBMITTED"
    READY = "READY"
    DOWNLOADED = "DOWNLOADED"
    VALIDATED = "VALIDATED"
    PUBLISHED = "PUBLISHED"


class CamsState(str, Enum):
    INTENT = RunState.INTENT.value
    SUBMITTED = RunState.SUBMITTED.value
    READY = RunState.READY.value
    DOWNLOADED = RunState.DOWNLOADED.value
    VALIDATED = RunState.VALIDATED.value
    PUBLISHED = RunState.PUBLISHED.value


class ClaimDisposition(str, Enum):
    CREATED = "created"
    ALREADY_OWNED = "already_owned"
    HELD_BY_OTHER = "held_by_other"
    TAKEOVER_AFTER_EXPIRY = "takeover_after_expiry"


class StateStoreError(RuntimeError):
    """Base class with deliberately static, secret-free error messages."""


class RunNotFound(StateStoreError):
    pass


class LeaseLost(StateStoreError):
    pass


class InvalidTransition(StateStoreError):
    pass


class StateConflict(StateStoreError):
    pass


class InvalidCheckpoint(StateStoreError):
    pass


@dataclass(frozen=True)
class RunKey:
    provider: Provider
    source_run_id: str
    request_hash: str

    def __post_init__(self) -> None:
        try:
            provider = self.provider if isinstance(self.provider, Provider) else Provider(self.provider)
        except (TypeError, ValueError):
            raise ValueError("Unsupported weather provider") from None
        if not isinstance(self.source_run_id, str) or not _RUN_ID.fullmatch(self.source_run_id):
            raise ValueError("Invalid source run identifier")
        if not isinstance(self.request_hash, str) or not _SHA256.fullmatch(self.request_hash):
            raise ValueError("Request hash must be lowercase SHA-256")
        object.__setattr__(self, "provider", provider)


@dataclass(frozen=True)
class RunRecord:
    key: RunKey
    state: RunState
    checkpoint: Mapping[str, Any]
    owner_id: str
    fencing_token: int
    lease_expires_at: datetime
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class ClaimResult:
    acquired: bool
    disposition: ClaimDisposition
    record: RunRecord


@dataclass(frozen=True)
class TransitionResult:
    changed: bool
    record: RunRecord


@dataclass(frozen=True)
class TransitionRecord:
    sequence: int
    key: RunKey
    from_state: RunState | None
    to_state: RunState
    checkpoint: Mapping[str, Any]
    owner_id: str
    fencing_token: int
    occurred_at: datetime


class DurableStateStore(Protocol):
    """Minimal port shared by the local harness and later infrastructure adapters."""

    path: Path

    def claim(
        self,
        key: RunKey,
        *,
        owner_id: str,
        lease_for: timedelta,
        now: datetime | None = None,
    ) -> ClaimResult: ...

    def renew_lease(
        self,
        key: RunKey,
        *,
        owner_id: str,
        fencing_token: int,
        lease_for: timedelta,
        now: datetime | None = None,
    ) -> RunRecord: ...

    def release_lease(
        self,
        key: RunKey,
        *,
        owner_id: str,
        fencing_token: int,
        now: datetime | None = None,
    ) -> bool: ...

    def transition_cams(
        self,
        key: RunKey,
        *,
        owner_id: str,
        fencing_token: int,
        expected_state: CamsState,
        target_state: CamsState,
        checkpoint: Mapping[str, Any] | None = None,
        now: datetime | None = None,
    ) -> TransitionResult: ...

    def get(self, key: RunKey) -> RunRecord | None: ...

    def history(self, key: RunKey) -> tuple[TransitionRecord, ...]: ...

    def close(self) -> None: ...
