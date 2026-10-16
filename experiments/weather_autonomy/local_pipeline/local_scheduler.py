"""Durable local scheduler for the independent ICON and CAMS jobs.

The scheduler deliberately knows nothing about provider networks or cloud
services.  Callers supply explicit daily UTC slots and one in-process runner
per :class:`~local_pipeline.job_outcomes.JobKind`.  SQLite stores the logical
attempt chain for every ``(job, slot)`` and provides the transaction boundary
for single-flight claims.  The runner is always called after that transaction
has committed.

Only a ``retryable_failure`` result creates a timed retry.  An interrupted
runner keeps its lease, so another worker may recover it after expiry with a
larger fencing token.  Documents returned by this module contain only fields
owned and validated by the scheduler; runner metrics and exception details are
never copied into them.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
import math
from pathlib import Path
import re
import sqlite3
from types import MappingProxyType
from typing import Iterator

from .job_outcomes import JobKind, JobResult, JobStatus


SCHEDULER_SCHEMA_VERSION = 1
SCHEDULER_APPLICATION_ID = 0x4D46534A  # ``MFSJ``
MAX_SECONDS = 24 * 60 * 60
MAX_ATTEMPTS = 32

_EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)
_LATEST_SUPPORTED = datetime(9998, 12, 31, 23, 59, 59, tzinfo=timezone.utc)
_LATEST_EPOCH = int((_LATEST_SUPPORTED - _EPOCH).total_seconds())
_OWNER_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}\Z")
_DAILY_SLOT = re.compile(r"(?:[01][0-9]|2[0-3]):[0-5][0-9]:[0-5][0-9]Z\Z")
_CANONICAL_INSTANT = re.compile(
    r"[0-9]{4}-(?:0[1-9]|1[0-2])-(?:0[1-9]|[12][0-9]|3[01])"
    r"T(?:[01][0-9]|2[0-3]):[0-5][0-9]:[0-5][0-9]Z\Z"
)


class SchedulerError(RuntimeError):
    """Base error for durable scheduler invariants."""


class SchedulerClockRegression(SchedulerError):
    """The clock moved behind a timestamp already observed for this job."""


class SchedulerLeaseLost(SchedulerError):
    """An attempt no longer owns the live fenced lease."""


class SchedulerState(str, Enum):
    RUNNING = "running"
    RETRY_WAIT = "retry_wait"
    PUBLISHED = "published"
    NO_OP = "no_op"
    MANUAL_REVIEW = "manual_review"
    PERMANENT_FAILURE = "permanent_failure"
    RETRY_EXHAUSTED = "retry_exhausted"
    SUPERSEDED = "superseded"


class ClaimDisposition(str, Enum):
    ACQUIRED = "acquired"
    HELD = "held"
    WAITING = "waiting"
    TERMINAL = "terminal"


_TERMINAL_STATES = frozenset(
    {
        SchedulerState.PUBLISHED,
        SchedulerState.NO_OP,
        SchedulerState.MANUAL_REVIEW,
        SchedulerState.PERMANENT_FAILURE,
        SchedulerState.RETRY_EXHAUSTED,
        SchedulerState.SUPERSEDED,
    }
)


def _canonical_clock(value: datetime) -> tuple[datetime, int]:
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise ValueError("Scheduler clock must return a timezone-aware datetime")
    try:
        result = value.astimezone(timezone.utc).replace(microsecond=0)
    except (OverflowError, OSError, ValueError):
        raise ValueError("Scheduler clock is outside the supported range") from None
    if result < _EPOCH or result > _LATEST_SUPPORTED:
        raise ValueError("Scheduler clock is outside the supported range")
    # Avoid float conversion: at far dates ``total_seconds()`` can round a
    # sub-second clock forward instead of flooring it.
    delta = result - _EPOCH
    epoch = delta.days * MAX_SECONDS + delta.seconds
    return result, epoch


def _format_epoch(value: int | None) -> str | None:
    if value is None:
        return None
    if type(value) is not int or not 0 <= value <= _LATEST_EPOCH:
        raise SchedulerError("Corrupt scheduler timestamp")
    return (_EPOCH + timedelta(seconds=value)).strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_instant(value: str) -> int:
    if not isinstance(value, str) or _CANONICAL_INSTANT.fullmatch(value) is None:
        raise ValueError("Slot timestamp must be canonical UTC")
    try:
        parsed = datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=timezone.utc
        )
    except ValueError:
        raise ValueError("Slot timestamp must be canonical UTC") from None
    if parsed.strftime("%Y-%m-%dT%H:%M:%SZ") != value:
        raise ValueError("Slot timestamp must be canonical UTC")
    _, epoch = _canonical_clock(parsed)
    return epoch


def _job(value: JobKind | str) -> JobKind:
    try:
        return value if isinstance(value, JobKind) else JobKind(value)
    except (TypeError, ValueError):
        raise ValueError("Unsupported scheduled weather job") from None


def _owner(value: str) -> str:
    if not isinstance(value, str) or _OWNER_ID.fullmatch(value) is None:
        raise ValueError("Invalid scheduler owner identifier")
    return value


def _positive_int(value: int, name: str, maximum: int) -> int:
    if type(value) is not int or not 1 <= value <= maximum:
        raise ValueError(f"{name} must be between 1 and {maximum}")
    return value


@dataclass(frozen=True)
class ProviderSchedule:
    """Explicit daily UTC slots for one independent provider job."""

    job: JobKind
    slots_utc: tuple[str, ...]

    def __post_init__(self) -> None:
        job = _job(self.job)
        if isinstance(self.slots_utc, (str, bytes)):
            raise ValueError("UTC slots must be a sequence")
        slots = tuple(self.slots_utc)
        if not slots:
            raise ValueError("At least one explicit UTC slot is required")
        if len(slots) > 86400:
            raise ValueError("Too many UTC slots")
        if any(not isinstance(slot, str) or _DAILY_SLOT.fullmatch(slot) is None for slot in slots):
            raise ValueError("UTC slots must use canonical HH:MM:SSZ form")
        if tuple(sorted(set(slots))) != slots:
            raise ValueError("UTC slots must be sorted and unique")
        object.__setattr__(self, "job", job)
        object.__setattr__(self, "slots_utc", slots)

    @property
    def seconds_of_day(self) -> tuple[int, ...]:
        return tuple(
            int(slot[0:2]) * 3600 + int(slot[3:5]) * 60 + int(slot[6:8])
            for slot in self.slots_utc
        )


@dataclass(frozen=True)
class RetryPolicy:
    lease_seconds: int = 300
    max_attempts: int = 3
    backoff_base_seconds: int = 60
    max_backoff_seconds: int = 3600

    def __post_init__(self) -> None:
        _positive_int(self.lease_seconds, "Lease seconds", MAX_SECONDS)
        _positive_int(self.max_attempts, "Maximum attempts", MAX_ATTEMPTS)
        _positive_int(self.backoff_base_seconds, "Backoff base seconds", MAX_SECONDS)
        _positive_int(self.max_backoff_seconds, "Maximum backoff seconds", MAX_SECONDS)
        if self.backoff_base_seconds > self.max_backoff_seconds:
            raise ValueError("Backoff base cannot exceed the maximum backoff")

    def retry_delay(self, result: JobResult, attempt: int) -> int:
        if result.status is not JobStatus.RETRYABLE_FAILURE:
            raise ValueError("Only retryable failures have a retry delay")
        _positive_int(attempt, "Attempt", self.max_attempts)
        if result.retry_after_seconds is not None:
            return min(result.retry_after_seconds, self.max_backoff_seconds)
        # max_attempts is bounded, but cap the exponent before multiplication as
        # an additional guard against accidental unbounded arithmetic.
        factor = 1 << min(attempt - 1, 30)
        return min(self.backoff_base_seconds * factor, self.max_backoff_seconds)


@dataclass(frozen=True)
class ScheduledAttempt:
    job: JobKind
    slot_utc: str
    attempt: int
    fencing_token: int
    lease_expires_at: str
    recovered_lease: bool
    _owner_id: str

    def as_document(self) -> dict[str, object]:
        return {
            "job": self.job.value,
            "slot_utc": self.slot_utc,
            "attempt": self.attempt,
            "fencing_token": self.fencing_token,
            "lease_expires_at": self.lease_expires_at,
            "recovered_lease": self.recovered_lease,
        }


@dataclass(frozen=True)
class SchedulerRecord:
    job: JobKind
    slot_utc: str
    state: SchedulerState
    attempt_count: int
    fencing_token: int
    lease_expires_at: str | None
    next_attempt_at: str | None
    result_status: JobStatus | None
    reason_code: str | None
    source_run_id: str | None
    updated_at: str

    @property
    def terminal(self) -> bool:
        return self.state in _TERMINAL_STATES

    def as_document(self) -> dict[str, object]:
        return {
            "job": self.job.value,
            "slot_utc": self.slot_utc,
            "state": self.state.value,
            "attempt_count": self.attempt_count,
            "fencing_token": self.fencing_token,
            "lease_expires_at": self.lease_expires_at,
            "next_attempt_at": self.next_attempt_at,
            "result_status": None if self.result_status is None else self.result_status.value,
            "reason_code": self.reason_code,
            "source_run_id": self.source_run_id,
            "updated_at": self.updated_at,
        }


@dataclass(frozen=True)
class ClaimResult:
    disposition: ClaimDisposition
    record: SchedulerRecord
    scheduled_attempt: ScheduledAttempt | None = None
    terminal_transition: bool = False


@dataclass(frozen=True)
class CompletionResult:
    record: SchedulerRecord
    retry_delay_seconds: int | None = None


@dataclass(frozen=True)
class SchedulerOutcome:
    job: JobKind
    slot_utc: str | None
    action: str
    state: SchedulerState | None
    attempt: int | None = None
    fencing_token: int | None = None
    reason_code: str | None = None
    next_attempt_at: str | None = None
    recovered_lease: bool = False

    def as_document(self) -> dict[str, object]:
        return {
            "job": self.job.value,
            "slot_utc": self.slot_utc,
            "action": self.action,
            "state": None if self.state is None else self.state.value,
            "attempt": self.attempt,
            "fencing_token": self.fencing_token,
            "reason_code": self.reason_code,
            "next_attempt_at": self.next_attempt_at,
            "recovered_lease": self.recovered_lease,
        }


@dataclass(frozen=True)
class SchedulerCycle:
    observed_at: str
    outcomes: tuple[SchedulerOutcome, ...]
    metrics: Mapping[str, int]

    def __post_init__(self) -> None:
        object.__setattr__(self, "metrics", MappingProxyType(dict(self.metrics)))

    def as_document(self) -> dict[str, object]:
        return {
            "schema_version": 1,
            "kind": "meteofriul.weather.local_scheduler_cycle",
            "observed_at": self.observed_at,
            "outcomes": [outcome.as_document() for outcome in self.outcomes],
            "metrics": dict(self.metrics),
        }


def _latest_due_slot(schedule: ProviderSchedule, now: datetime) -> str | None:
    canonical, _ = _canonical_clock(now)
    day_start = canonical.replace(hour=0, minute=0, second=0)
    elapsed = canonical.hour * 3600 + canonical.minute * 60 + canonical.second
    due_today = [second for second in schedule.seconds_of_day if second <= elapsed]
    if due_today:
        slot = day_start + timedelta(seconds=due_today[-1])
    else:
        if day_start == _EPOCH:
            return None
        slot = day_start - timedelta(days=1) + timedelta(seconds=schedule.seconds_of_day[-1])
    return slot.strftime("%Y-%m-%dT%H:%M:%SZ")


class SQLiteSchedulerStore:
    """Dedicated durable store for scheduler claims and terminal outcomes."""

    def __init__(self, path: str | Path, *, busy_timeout_seconds: float = 10.0) -> None:
        if str(path) == ":memory:":
            raise ValueError("The durable scheduler cannot use an in-memory database")
        self.path = Path(path)
        if self.path.exists() and not self.path.is_file():
            raise ValueError("SQLite scheduler path must be a file")
        if not self.path.parent.is_dir():
            raise ValueError("SQLite scheduler parent directory must already exist")
        if isinstance(busy_timeout_seconds, bool) or not isinstance(
            busy_timeout_seconds, (int, float)
        ):
            raise ValueError("Busy timeout must be numeric")
        if not math.isfinite(float(busy_timeout_seconds)) or not 0 < float(
            busy_timeout_seconds
        ) <= 60:
            raise ValueError("Busy timeout must be between zero and 60 seconds")
        self._busy_timeout_ms = round(float(busy_timeout_seconds) * 1000)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(
            self.path,
            timeout=self._busy_timeout_ms / 1000,
            isolation_level=None,
        )
        connection.row_factory = sqlite3.Row
        connection.execute(f"PRAGMA busy_timeout={self._busy_timeout_ms}")
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA synchronous=FULL")
        return connection

    def _initialize(self) -> None:
        connection = self._connect()
        try:
            application_id = int(connection.execute("PRAGMA application_id").fetchone()[0])
            version = int(connection.execute("PRAGMA user_version").fetchone()[0])
            tables = {
                str(row[0])
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
                )
            }
            if application_id == 0:
                if version != 0 or tables:
                    raise SchedulerError("SQLite file is not an empty scheduler database")
            elif application_id != SCHEDULER_APPLICATION_ID:
                raise SchedulerError("SQLite file belongs to a different application")
            if version not in (0, SCHEDULER_SCHEMA_VERSION):
                raise SchedulerError("Unsupported SQLite scheduler schema version")
            mode = str(connection.execute("PRAGMA journal_mode=WAL").fetchone()[0]).lower()
            if mode != "wal":
                raise SchedulerError("SQLite WAL mode could not be enabled")

            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS scheduler_runs (
                    job TEXT NOT NULL CHECK (job IN ('icon', 'cams')),
                    slot_utc TEXT NOT NULL,
                    slot_epoch INTEGER NOT NULL CHECK (slot_epoch >= 0),
                    state TEXT NOT NULL CHECK (state IN (
                        'running', 'retry_wait', 'published', 'no_op',
                        'manual_review', 'permanent_failure',
                        'retry_exhausted', 'superseded'
                    )),
                    attempt_count INTEGER NOT NULL CHECK (attempt_count >= 1),
                    fencing_token INTEGER NOT NULL CHECK (fencing_token >= 1),
                    owner_id TEXT,
                    lease_expires_at INTEGER,
                    next_attempt_at INTEGER,
                    result_status TEXT,
                    reason_code TEXT,
                    source_run_id TEXT,
                    created_at INTEGER NOT NULL,
                    updated_at INTEGER NOT NULL,
                    completed_at INTEGER,
                    PRIMARY KEY (job, slot_utc),
                    UNIQUE (job, slot_epoch),
                    CHECK (result_status IS NULL OR result_status IN (
                        'published', 'no_op', 'retryable_failure',
                        'manual_review', 'permanent_failure'
                    )),
                    CHECK (
                        (state = 'running' AND owner_id IS NOT NULL
                           AND lease_expires_at IS NOT NULL AND next_attempt_at IS NULL)
                        OR
                        (state = 'retry_wait' AND owner_id IS NULL
                           AND lease_expires_at IS NULL AND next_attempt_at IS NOT NULL)
                        OR
                        (state NOT IN ('running', 'retry_wait') AND owner_id IS NULL
                           AND lease_expires_at IS NULL AND next_attempt_at IS NULL)
                    )
                ) WITHOUT ROWID
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS scheduler_clock (
                    job TEXT PRIMARY KEY CHECK (job IN ('icon', 'cams')),
                    last_observed_at INTEGER NOT NULL CHECK (last_observed_at >= 0),
                    last_fencing_token INTEGER NOT NULL
                        CHECK (last_fencing_token >= 0)
                ) WITHOUT ROWID
                """
            )
            connection.execute(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS scheduler_one_running_per_job
                ON scheduler_runs (job) WHERE state='running'
                """
            )
            if application_id == 0:
                connection.execute(f"PRAGMA application_id={SCHEDULER_APPLICATION_ID}")
            if version == 0:
                connection.execute(f"PRAGMA user_version={SCHEDULER_SCHEMA_VERSION}")
            connection.commit()
        except Exception:
            if connection.in_transaction:
                connection.rollback()
            raise
        finally:
            connection.close()

    @contextmanager
    def _transaction(self) -> Iterator[sqlite3.Connection]:
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            yield connection
            connection.commit()
        except Exception:
            if connection.in_transaction:
                connection.rollback()
            raise
        finally:
            connection.close()

    @staticmethod
    def _observe_clock(connection: sqlite3.Connection, job: JobKind, now_epoch: int) -> None:
        row = connection.execute(
            "SELECT last_observed_at FROM scheduler_clock WHERE job=?", (job.value,)
        ).fetchone()
        if row is not None and now_epoch < int(row[0]):
            raise SchedulerClockRegression("Scheduler clock moved backwards")
        connection.execute(
            """
            INSERT INTO scheduler_clock (
                job, last_observed_at, last_fencing_token
            ) VALUES (?, ?, 0)
            ON CONFLICT(job) DO UPDATE SET last_observed_at=excluded.last_observed_at
            """,
            (job.value, now_epoch),
        )

    @staticmethod
    def _next_fence(connection: sqlite3.Connection, job: JobKind) -> int:
        updated = connection.execute(
            """
            UPDATE scheduler_clock
            SET last_fencing_token=last_fencing_token+1
            WHERE job=?
            """,
            (job.value,),
        )
        if updated.rowcount != 1:
            raise SchedulerError("Scheduler fence allocator is unavailable")
        row = connection.execute(
            "SELECT last_fencing_token FROM scheduler_clock WHERE job=?",
            (job.value,),
        ).fetchone()
        if row is None:
            raise SchedulerError("Scheduler fence allocator is unavailable")
        return int(row[0])

    @staticmethod
    def _select(
        connection: sqlite3.Connection, job: JobKind, slot_utc: str
    ) -> sqlite3.Row | None:
        return connection.execute(
            "SELECT * FROM scheduler_runs WHERE job=? AND slot_utc=?",
            (job.value, slot_utc),
        ).fetchone()

    @staticmethod
    def _record(row: sqlite3.Row) -> SchedulerRecord:
        try:
            state = SchedulerState(row["state"])
            status = None if row["result_status"] is None else JobStatus(row["result_status"])
        except (TypeError, ValueError):
            raise SchedulerError("Corrupt scheduler state") from None
        return SchedulerRecord(
            job=_job(row["job"]),
            slot_utc=str(row["slot_utc"]),
            state=state,
            attempt_count=int(row["attempt_count"]),
            fencing_token=int(row["fencing_token"]),
            lease_expires_at=_format_epoch(row["lease_expires_at"]),
            next_attempt_at=_format_epoch(row["next_attempt_at"]),
            result_status=status,
            reason_code=row["reason_code"],
            source_run_id=row["source_run_id"],
            updated_at=_format_epoch(int(row["updated_at"])) or "",
        )

    @staticmethod
    def _attempt(row: sqlite3.Row, *, recovered: bool) -> ScheduledAttempt:
        lease = _format_epoch(int(row["lease_expires_at"]))
        if lease is None or row["owner_id"] is None:
            raise SchedulerError("Corrupt running scheduler state")
        return ScheduledAttempt(
            job=_job(row["job"]),
            slot_utc=str(row["slot_utc"]),
            attempt=int(row["attempt_count"]),
            fencing_token=int(row["fencing_token"]),
            lease_expires_at=lease,
            recovered_lease=recovered,
            _owner_id=str(row["owner_id"]),
        )

    def claim(
        self,
        job: JobKind,
        slot_utc: str,
        *,
        owner_id: str,
        policy: RetryPolicy,
        now: datetime,
    ) -> ClaimResult:
        job = _job(job)
        owner_id = _owner(owner_id)
        slot_epoch = _parse_instant(slot_utc)
        _, now_epoch = _canonical_clock(now)
        if slot_epoch > now_epoch:
            raise ValueError("A future scheduler slot cannot be claimed")

        with self._transaction() as connection:
            self._observe_clock(connection, job, now_epoch)
            target = self._select(connection, job, slot_utc)
            if target is not None and SchedulerState(target["state"]) in _TERMINAL_STATES:
                return ClaimResult(ClaimDisposition.TERMINAL, self._record(target))

            live = connection.execute(
                """
                SELECT * FROM scheduler_runs
                WHERE job=? AND state='running' AND lease_expires_at>?
                ORDER BY slot_epoch DESC LIMIT 1
                """,
                (job.value, now_epoch),
            ).fetchone()
            if live is not None:
                return ClaimResult(ClaimDisposition.HELD, self._record(live))

            # Latest-only catch-up discards work for older slots once no live
            # worker can still own it.  A live older lease was handled above.
            connection.execute(
                """
                UPDATE scheduler_runs
                SET state='superseded', owner_id=NULL, lease_expires_at=NULL,
                    next_attempt_at=NULL, result_status=NULL,
                    reason_code='newer_slot_due', source_run_id=NULL,
                    updated_at=?, completed_at=?
                WHERE job=? AND slot_epoch<?
                  AND (state='retry_wait'
                       OR (state='running' AND lease_expires_at<=?))
                """,
                (now_epoch, now_epoch, job.value, slot_epoch, now_epoch),
            )

            target = self._select(connection, job, slot_utc)
            lease_expires = now_epoch + policy.lease_seconds
            if lease_expires > _LATEST_EPOCH:
                raise ValueError("Lease expiry is outside the supported clock range")

            if target is None:
                fencing_token = self._next_fence(connection, job)
                connection.execute(
                    """
                    INSERT INTO scheduler_runs (
                        job, slot_utc, slot_epoch, state, attempt_count,
                        fencing_token, owner_id, lease_expires_at,
                        next_attempt_at, result_status, reason_code,
                        source_run_id, created_at, updated_at, completed_at
                    ) VALUES (?, ?, ?, 'running', 1, ?, ?, ?, NULL, NULL,
                              NULL, NULL, ?, ?, NULL)
                    """,
                    (
                        job.value,
                        slot_utc,
                        slot_epoch,
                        fencing_token,
                        owner_id,
                        lease_expires,
                        now_epoch,
                        now_epoch,
                    ),
                )
                row = self._select(connection, job, slot_utc)
                assert row is not None
                return ClaimResult(
                    ClaimDisposition.ACQUIRED,
                    self._record(row),
                    self._attempt(row, recovered=False),
                )

            state = SchedulerState(target["state"])
            if state is SchedulerState.RUNNING:
                recovered = True
            elif state is SchedulerState.RETRY_WAIT:
                retry_at = int(target["next_attempt_at"])
                if retry_at > now_epoch:
                    return ClaimResult(ClaimDisposition.WAITING, self._record(target))
                recovered = False
            else:
                return ClaimResult(ClaimDisposition.TERMINAL, self._record(target))

            attempts = int(target["attempt_count"])
            if attempts >= policy.max_attempts:
                exhausted_state = (
                    SchedulerState.MANUAL_REVIEW
                    if state is SchedulerState.RUNNING
                    else SchedulerState.RETRY_EXHAUSTED
                )
                exhausted_status = (
                    None
                    if state is SchedulerState.RUNNING
                    else JobStatus.RETRYABLE_FAILURE.value
                )
                exhausted_reason = (
                    "lease_recovery_exhausted"
                    if state is SchedulerState.RUNNING
                    else "attempts_exhausted"
                )
                connection.execute(
                    """
                    UPDATE scheduler_runs
                    SET state=?, owner_id=NULL,
                        lease_expires_at=NULL, next_attempt_at=NULL,
                        result_status=?, reason_code=?, source_run_id=NULL,
                        updated_at=?, completed_at=?
                    WHERE job=? AND slot_utc=?
                    """,
                    (
                        exhausted_state.value,
                        exhausted_status,
                        exhausted_reason,
                        now_epoch,
                        now_epoch,
                        job.value,
                        slot_utc,
                    ),
                )
                row = self._select(connection, job, slot_utc)
                assert row is not None
                return ClaimResult(
                    ClaimDisposition.TERMINAL,
                    self._record(row),
                    terminal_transition=True,
                )

            fencing_token = self._next_fence(connection, job)
            connection.execute(
                """
                UPDATE scheduler_runs
                SET state='running', attempt_count=attempt_count+1,
                    fencing_token=?, owner_id=?,
                    lease_expires_at=?, next_attempt_at=NULL,
                    result_status=NULL, reason_code=NULL, source_run_id=NULL,
                    updated_at=?, completed_at=NULL
                WHERE job=? AND slot_utc=?
                """,
                (
                    fencing_token,
                    owner_id,
                    lease_expires,
                    now_epoch,
                    job.value,
                    slot_utc,
                ),
            )
            row = self._select(connection, job, slot_utc)
            assert row is not None
            return ClaimResult(
                ClaimDisposition.ACQUIRED,
                self._record(row),
                self._attempt(row, recovered=recovered),
            )

    def complete(
        self,
        scheduled_attempt: ScheduledAttempt,
        result: JobResult,
        *,
        policy: RetryPolicy,
        now: datetime,
    ) -> CompletionResult:
        if not isinstance(scheduled_attempt, ScheduledAttempt):
            raise ValueError("A scheduled attempt is required")
        if not isinstance(result, JobResult) or result.job is not scheduled_attempt.job:
            raise ValueError("Job result does not match the scheduled attempt")
        _, now_epoch = _canonical_clock(now)
        with self._transaction() as connection:
            row = self._select(connection, scheduled_attempt.job, scheduled_attempt.slot_utc)
            if (
                row is None
                or row["state"] != SchedulerState.RUNNING.value
                or row["owner_id"] != scheduled_attempt._owner_id
                or int(row["fencing_token"]) != scheduled_attempt.fencing_token
                or int(row["attempt_count"]) != scheduled_attempt.attempt
                or int(row["lease_expires_at"]) <= now_epoch
            ):
                raise SchedulerLeaseLost("Scheduled attempt no longer owns a live lease")
            self._observe_clock(connection, scheduled_attempt.job, now_epoch)

            retry_delay: int | None = None
            if result.status is JobStatus.RETRYABLE_FAILURE:
                if scheduled_attempt.attempt >= policy.max_attempts:
                    state = SchedulerState.RETRY_EXHAUSTED
                    next_attempt = None
                    completed_at = now_epoch
                else:
                    state = SchedulerState.RETRY_WAIT
                    retry_delay = policy.retry_delay(result, scheduled_attempt.attempt)
                    next_attempt = now_epoch + retry_delay
                    if next_attempt > _LATEST_EPOCH:
                        raise ValueError("Retry time is outside the supported clock range")
                    completed_at = None
            else:
                state = {
                    JobStatus.PUBLISHED: SchedulerState.PUBLISHED,
                    JobStatus.NO_OP: SchedulerState.NO_OP,
                    JobStatus.MANUAL_REVIEW: SchedulerState.MANUAL_REVIEW,
                    JobStatus.PERMANENT_FAILURE: SchedulerState.PERMANENT_FAILURE,
                }[result.status]
                next_attempt = None
                completed_at = now_epoch

            updated = connection.execute(
                """
                UPDATE scheduler_runs
                SET state=?, owner_id=NULL, lease_expires_at=NULL,
                    next_attempt_at=?, result_status=?, reason_code=?,
                    source_run_id=?, updated_at=?, completed_at=?
                WHERE job=? AND slot_utc=? AND state='running'
                  AND owner_id=? AND fencing_token=? AND attempt_count=?
                  AND lease_expires_at>?
                """,
                (
                    state.value,
                    next_attempt,
                    result.status.value,
                    result.reason_code,
                    result.source_run_id,
                    now_epoch,
                    completed_at,
                    scheduled_attempt.job.value,
                    scheduled_attempt.slot_utc,
                    scheduled_attempt._owner_id,
                    scheduled_attempt.fencing_token,
                    scheduled_attempt.attempt,
                    now_epoch,
                ),
            )
            if updated.rowcount != 1:
                raise SchedulerLeaseLost("Scheduled attempt lost its fenced lease")
            completed = self._select(
                connection, scheduled_attempt.job, scheduled_attempt.slot_utc
            )
            assert completed is not None
            return CompletionResult(self._record(completed), retry_delay)

    def renew(
        self,
        scheduled_attempt: ScheduledAttempt,
        *,
        policy: RetryPolicy,
        now: datetime,
    ) -> ScheduledAttempt:
        if not isinstance(scheduled_attempt, ScheduledAttempt):
            raise ValueError("A scheduled attempt is required")
        _, now_epoch = _canonical_clock(now)
        lease_expires = now_epoch + policy.lease_seconds
        if lease_expires > _LATEST_EPOCH:
            raise ValueError("Lease expiry is outside the supported clock range")
        with self._transaction() as connection:
            row = self._select(connection, scheduled_attempt.job, scheduled_attempt.slot_utc)
            if (
                row is None
                or row["state"] != SchedulerState.RUNNING.value
                or row["owner_id"] != scheduled_attempt._owner_id
                or int(row["fencing_token"]) != scheduled_attempt.fencing_token
                or int(row["attempt_count"]) != scheduled_attempt.attempt
                or int(row["lease_expires_at"]) <= now_epoch
            ):
                raise SchedulerLeaseLost("Scheduled attempt no longer owns a live lease")
            self._observe_clock(connection, scheduled_attempt.job, now_epoch)
            connection.execute(
                """
                UPDATE scheduler_runs SET lease_expires_at=?, updated_at=?
                WHERE job=? AND slot_utc=? AND state='running'
                  AND owner_id=? AND fencing_token=? AND lease_expires_at>?
                """,
                (
                    lease_expires,
                    now_epoch,
                    scheduled_attempt.job.value,
                    scheduled_attempt.slot_utc,
                    scheduled_attempt._owner_id,
                    scheduled_attempt.fencing_token,
                    now_epoch,
                ),
            )
            renewed = self._select(
                connection, scheduled_attempt.job, scheduled_attempt.slot_utc
            )
            assert renewed is not None
            return self._attempt(renewed, recovered=scheduled_attempt.recovered_lease)

    def get(self, job: JobKind, slot_utc: str) -> SchedulerRecord | None:
        job = _job(job)
        _parse_instant(slot_utc)
        connection = self._connect()
        try:
            row = self._select(connection, job, slot_utc)
            return None if row is None else self._record(row)
        finally:
            connection.close()


Runner = Callable[[ScheduledAttempt], JobResult]


class LocalScheduler:
    """One non-blocking scheduler tick over explicit provider schedules."""

    def __init__(
        self,
        store: SQLiteSchedulerStore,
        *,
        schedules: Sequence[ProviderSchedule],
        runners: Mapping[JobKind, Runner],
        owner_id: str,
        policy: RetryPolicy,
        clock: Callable[[], datetime],
    ) -> None:
        if not isinstance(store, SQLiteSchedulerStore):
            raise ValueError("A SQLite scheduler store is required")
        if not isinstance(policy, RetryPolicy):
            raise ValueError("A scheduler retry policy is required")
        if not callable(clock):
            raise ValueError("Scheduler clock must be callable")
        normalized_schedules: dict[JobKind, ProviderSchedule] = {}
        for schedule in schedules:
            if not isinstance(schedule, ProviderSchedule):
                raise ValueError("Invalid provider schedule")
            if schedule.job in normalized_schedules:
                raise ValueError("Each provider job may have only one schedule")
            normalized_schedules[schedule.job] = schedule
        if not normalized_schedules:
            raise ValueError("At least one provider schedule is required")
        normalized_runners: dict[JobKind, Runner] = {}
        for job, runner in runners.items():
            normalized_job = _job(job)
            if normalized_job in normalized_runners:
                raise ValueError("Each provider job may have only one runner")
            if not callable(runner):
                raise ValueError("Each scheduled job requires a callable runner")
            normalized_runners[normalized_job] = runner
        if set(normalized_runners) != set(normalized_schedules):
            raise ValueError("Schedules and runners must name the same provider jobs")
        self._store = store
        self._schedules = dict(sorted(normalized_schedules.items(), key=lambda item: item[0].value))
        self._runners = normalized_runners
        self._owner_id = _owner(owner_id)
        self._policy = policy
        self._clock = clock

    def _now(self) -> datetime:
        value = self._clock()
        return _canonical_clock(value)[0]

    def renew(self, attempt: ScheduledAttempt) -> ScheduledAttempt:
        return self._store.renew(attempt, policy=self._policy, now=self._now())

    def run_due(self) -> SchedulerCycle:
        observed = self._now()
        outcomes: list[SchedulerOutcome] = []
        for job, schedule in self._schedules.items():
            slot_utc = _latest_due_slot(schedule, observed)
            if slot_utc is None:
                outcomes.append(
                    SchedulerOutcome(job, None, "no_due_slot", None, reason_code="no_due_slot")
                )
                continue
            claim = self._store.claim(
                job,
                slot_utc,
                owner_id=self._owner_id,
                policy=self._policy,
                now=observed,
            )
            if claim.disposition is not ClaimDisposition.ACQUIRED:
                if claim.terminal_transition:
                    action = (
                        "lease_recovery_exhausted"
                        if claim.record.reason_code == "lease_recovery_exhausted"
                        else "attempts_exhausted"
                    )
                else:
                    action = {
                        ClaimDisposition.HELD: "lease_held",
                        ClaimDisposition.WAITING: "retry_wait",
                        ClaimDisposition.TERMINAL: "already_terminal",
                    }[claim.disposition]
                outcomes.append(
                    SchedulerOutcome(
                        job,
                        claim.record.slot_utc,
                        action,
                        claim.record.state,
                        attempt=claim.record.attempt_count,
                        fencing_token=claim.record.fencing_token,
                        reason_code=claim.record.reason_code,
                        next_attempt_at=claim.record.next_attempt_at,
                    )
                )
                continue

            attempt = claim.scheduled_attempt
            assert attempt is not None
            try:
                candidate = self._runners[job](attempt)
            except Exception:
                # The lease remains live.  Its bounded recovery path is the
                # only durable fact; exception text/type is intentionally lost.
                outcomes.append(
                    SchedulerOutcome(
                        job,
                        slot_utc,
                        "runner_interrupted",
                        SchedulerState.RUNNING,
                        attempt=attempt.attempt,
                        fencing_token=attempt.fencing_token,
                        reason_code="runner_interrupted",
                        recovered_lease=attempt.recovered_lease,
                    )
                )
                continue

            if not isinstance(candidate, JobResult) or candidate.job is not job:
                result = JobResult(
                    job=job,
                    status=JobStatus.MANUAL_REVIEW,
                    reason_code="invalid_runner_result",
                )
            else:
                result = candidate
            try:
                completion = self._store.complete(
                    attempt, result, policy=self._policy, now=self._now()
                )
            except SchedulerLeaseLost:
                outcomes.append(
                    SchedulerOutcome(
                        job,
                        slot_utc,
                        "lease_lost",
                        SchedulerState.RUNNING,
                        attempt=attempt.attempt,
                        fencing_token=attempt.fencing_token,
                        reason_code="lease_lost",
                        recovered_lease=attempt.recovered_lease,
                    )
                )
                continue
            record = completion.record
            action = (
                "retry_scheduled"
                if record.state is SchedulerState.RETRY_WAIT
                else "completed"
            )
            outcomes.append(
                SchedulerOutcome(
                    job,
                    slot_utc,
                    action,
                    record.state,
                    attempt=record.attempt_count,
                    fencing_token=record.fencing_token,
                    reason_code=record.reason_code,
                    next_attempt_at=record.next_attempt_at,
                    recovered_lease=attempt.recovered_lease,
                )
            )

        counts = {
            "configured_jobs": len(self._schedules),
            "claimed_attempts": sum(
                outcome.action
                in {"completed", "retry_scheduled", "runner_interrupted", "lease_lost"}
                for outcome in outcomes
            ),
            "terminal_successes": sum(
                outcome.state in {SchedulerState.PUBLISHED, SchedulerState.NO_OP}
                and outcome.action == "completed"
                for outcome in outcomes
            ),
            "terminal_failures": sum(
                outcome.state
                in {
                    SchedulerState.MANUAL_REVIEW,
                    SchedulerState.PERMANENT_FAILURE,
                    SchedulerState.RETRY_EXHAUSTED,
                }
                and outcome.action
                in {"completed", "lease_recovery_exhausted", "attempts_exhausted"}
                for outcome in outcomes
            ),
            "retries_scheduled": sum(
                outcome.action == "retry_scheduled" for outcome in outcomes
            ),
            "held_claims": sum(outcome.action == "lease_held" for outcome in outcomes),
            "interrupted_jobs": sum(
                outcome.action == "runner_interrupted" for outcome in outcomes
            ),
            "recovered_leases": sum(outcome.recovered_lease for outcome in outcomes),
        }
        return SchedulerCycle(
            observed.strftime("%Y-%m-%dT%H:%M:%SZ"), tuple(outcomes), counts
        )


__all__ = [
    "ClaimDisposition",
    "ClaimResult",
    "CompletionResult",
    "LocalScheduler",
    "ProviderSchedule",
    "RetryPolicy",
    "SCHEDULER_APPLICATION_ID",
    "SCHEDULER_SCHEMA_VERSION",
    "ScheduledAttempt",
    "SchedulerClockRegression",
    "SchedulerCycle",
    "SchedulerError",
    "SchedulerLeaseLost",
    "SchedulerOutcome",
    "SchedulerRecord",
    "SchedulerState",
    "SQLiteSchedulerStore",
]
