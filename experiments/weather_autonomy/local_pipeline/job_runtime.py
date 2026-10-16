"""Shared local runtime helpers for the executable weather jobs.

The helpers in this module only inspect explicit local artifacts.  They derive
the immutable source-run identity, freeze one publication intent before any
database is opened and serialize the stable :class:`JobResult` envelope.
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path, PureWindowsPath
import re
from typing import Any, Callable, Mapping, TextIO

from .contract_v1 import ContractError, canonical_json_bytes, canonical_run_id
from .job_entrypoints import InvalidJobInputs
from .job_outcomes import JobKind, JobResult
from .publication_intent import (
    InvalidPublicationIntent,
    PublicationIntentConflict,
    PublicationIntentResolution,
    fingerprint_input_files,
    resolve_publication_intent,
)
from .snapshot_materializer import load_verified_icon_snapshot


MAX_IDENTITY_REPORT_BYTES = 4 * 1024 * 1024
_OWNER_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}\Z")
_RUN_DATE = re.compile(r"\d{4}-\d{2}-\d{2}\Z")
_WIN32_DEVICE_NAMES = frozenset(
    {
        "aux",
        "clock$",
        "con",
        "conin$",
        "conout$",
        "nul",
        "prn",
        *(f"com{number}" for number in range(1, 10)),
        *(f"lpt{number}" for number in range(1, 10)),
        "com¹",
        "com²",
        "com³",
        "lpt¹",
        "lpt²",
        "lpt³",
    }
)
_SQLITE_RESERVED_SUFFIXES = (
    ("", ""),
    ("-wal", " WAL"),
    ("-shm", " SHM"),
    ("-journal", " journal"),
)


def _win32_path_identity(path: Path, label: str) -> str:
    """Return a conservative Win32 identity or reject ambiguous spellings.

    SQLite may create sibling files by appending a suffix to the main database
    path.  Win32 also aliases names by case and accepts several legacy
    spellings that Python can otherwise pass through.  Rejecting those
    spellings keeps the pre-open path check meaningful on Windows and makes it
    deterministic on every host used by the offline tests.
    """

    raw = str(path)
    namespace = raw.replace("/", "\\").casefold()
    if namespace.startswith(("\\\\?\\", "\\\\.\\", "\\??\\")):
        raise InvalidJobInputs(f"{label} uses an unsupported Win32 namespace")

    windows_path = PureWindowsPath(raw)
    if windows_path.drive.startswith("\\\\"):
        raise InvalidJobInputs(f"{label} cannot use a network share")
    anchor = windows_path.anchor
    for position, component in enumerate(windows_path.parts):
        if position == 0 and component == anchor:
            continue
        if component.endswith((" ", ".")):
            raise InvalidJobInputs(
                f"{label} contains a Win32-ambiguous trailing space or dot"
            )
        if ":" in component:
            raise InvalidJobInputs(f"{label} cannot use an NTFS alternate data stream")

        # Device aliases remain reserved even when followed by an extension.
        device_stem = component.split(".", 1)[0].rstrip(" .").casefold()
        if device_stem in _WIN32_DEVICE_NAMES:
            raise InvalidJobInputs(f"{label} contains a reserved Win32 device name")

    return str(windows_path).casefold()


def _reject_reparse_chain(path: Path, label: str) -> None:
    """Reject symlinks and junctions at the leaf or in any existing ancestor."""

    current = path.absolute()
    while True:
        try:
            redirected = current.is_symlink() or current.is_junction()
        except OSError as error:
            raise InvalidJobInputs(f"{label} path identity cannot be verified") from error
        if redirected:
            raise InvalidJobInputs(
                f"{label} cannot traverse a symbolic link or junction"
            )
        parent = current.parent
        if parent == current:
            break
        current = parent


def normalize_existing_file(value: str | Path, label: str) -> Path:
    path = Path(value).expanduser()
    _win32_path_identity(path, label)
    _reject_reparse_chain(path, label)
    try:
        resolved = path.resolve(strict=True)
    except OSError as error:
        raise FileNotFoundError(f"{label} is missing") from error
    if not resolved.is_file():
        raise InvalidJobInputs(f"{label} must be a regular file")
    return resolved


def normalize_existing_directory(value: str | Path, label: str) -> Path:
    path = Path(value).expanduser()
    _win32_path_identity(path, label)
    _reject_reparse_chain(path, label)
    try:
        resolved = path.resolve(strict=True)
    except OSError as error:
        raise InvalidJobInputs(f"{label} must already exist") from error
    if not resolved.is_dir():
        raise InvalidJobInputs(f"{label} must be a directory")
    return resolved


def normalize_database_path(value: str | Path, label: str) -> Path:
    path = Path(value).expanduser()
    _win32_path_identity(path, label)
    _reject_reparse_chain(path, label)
    resolved = path.absolute()
    parent = resolved.parent
    if not parent.is_dir():
        raise InvalidJobInputs(f"{label} parent directory must already exist")
    if resolved.exists() and not resolved.is_file():
        raise InvalidJobInputs(f"{label} must be a regular file")
    return resolved.resolve()


def normalize_intent_directory(value: str | Path) -> Path:
    path = Path(value).expanduser()
    _win32_path_identity(path, "Publication-intent directory")
    _reject_reparse_chain(path, "Publication-intent directory")
    try:
        resolved = path.resolve(strict=True)
    except OSError as error:
        raise InvalidJobInputs(
            "Publication-intent directory must already exist"
        ) from error
    if not resolved.is_dir():
        raise InvalidJobInputs("Publication-intent path must be a directory")
    return resolved


def normalize_owner_id(value: str) -> str:
    if not isinstance(value, str) or not _OWNER_ID.fullmatch(value):
        raise InvalidJobInputs("Execution owner identifier is invalid")
    return value


def require_distinct_paths(paths: Mapping[str, Path]) -> None:
    observed: list[tuple[str, Path, str]] = []
    for label, path in paths.items():
        identity = _win32_path_identity(path, label)
        for previous_label, previous_path, previous_identity in observed:
            aliases = identity == previous_identity
            if not aliases and path.exists() and previous_path.exists():
                try:
                    aliases = os.path.samefile(path, previous_path)
                except OSError as error:
                    raise InvalidJobInputs(
                        "Job path identity cannot be verified"
                    ) from error
            if aliases:
                raise InvalidJobInputs(f"{label} aliases {previous_label}")
        observed.append((label, path, identity))


def sqlite_reserved_paths(databases: Mapping[str, Path]) -> dict[str, Path]:
    """Expand SQLite main paths to every sibling filename SQLite may create."""

    reserved: dict[str, Path] = {}
    for label, database in databases.items():
        for suffix, label_suffix in _SQLITE_RESERVED_SUFFIXES:
            reserved_label = f"{label}{label_suffix}"
            if reserved_label in reserved:
                raise InvalidJobInputs("SQLite database path labels must be distinct")
            reserved[reserved_label] = Path(f"{database}{suffix}")
    return reserved


def require_safe_sqlite_layout(
    *,
    databases: Mapping[str, Path],
    other_paths: Mapping[str, Path],
) -> None:
    """Reject aliases between inputs and all main/sidecar SQLite filenames."""

    reserved = sqlite_reserved_paths(databases)
    overlapping_labels = set(reserved).intersection(other_paths)
    if overlapping_labels:
        raise InvalidJobInputs("Job path labels must be distinct")
    require_distinct_paths({**reserved, **other_paths})


def _strict_object(raw: bytes, label: str) -> dict[str, Any]:
    def reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise InvalidJobInputs(f"{label} contains duplicate JSON keys")
            result[key] = value
        return result

    try:
        value = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=reject_duplicates,
            parse_constant=lambda _value: (_ for _ in ()).throw(
                InvalidJobInputs(f"{label} contains a non-finite number")
            ),
        )
    except InvalidJobInputs:
        raise
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise InvalidJobInputs(f"{label} is not strict UTF-8 JSON") from error
    if not isinstance(value, dict):
        raise InvalidJobInputs(f"{label} must be a JSON object")
    return value


def _read_identity_report(path: Path, label: str) -> dict[str, Any]:
    try:
        before = path.stat()
        if not 1 <= before.st_size <= MAX_IDENTITY_REPORT_BYTES:
            raise InvalidJobInputs(f"{label} size is invalid")
        with path.open("rb") as stream:
            raw = stream.read(MAX_IDENTITY_REPORT_BYTES + 1)
        after = path.stat()
    except InvalidJobInputs:
        raise
    except OSError as error:
        raise FileNotFoundError(f"{label} cannot be read") from error
    if (
        len(raw) != before.st_size
        or before.st_size != after.st_size
        or before.st_mtime_ns != after.st_mtime_ns
    ):
        raise InvalidJobInputs(f"{label} changed while it was read")
    return _strict_object(raw, label)


def report_run_at(report: Mapping[str, Any], field: str, label: str) -> str:
    value = report.get(field)
    if not isinstance(value, str):
        raise InvalidJobInputs(f"{label} does not contain {field}")
    return value


def icon_source_run_id_from_file(report_path: Path) -> str:
    report = _read_identity_report(report_path, "ICON report")
    try:
        return canonical_run_id(report_run_at(report, "run_utc", "ICON report"))
    except ContractError as error:
        raise InvalidJobInputs("ICON report run identity is invalid") from error


def icon_source_run_id_from_inputs(payload_path: Path, report_path: Path) -> str:
    """Authenticate both ICON files and derive the run from their shared identity."""

    snapshot = load_verified_icon_snapshot(
        icon_archive=payload_path,
        icon_report=report_path,
    )
    try:
        return canonical_run_id(snapshot.get("run_utc"))
    except (AttributeError, ContractError) as error:
        raise InvalidJobInputs("ICON input run identity is invalid") from error


def cams_source_run_id_from_file(report_path: Path) -> str:
    report = _read_identity_report(report_path, "CAMS decode report")
    run_date = report.get("run_date")
    if not isinstance(run_date, str) or not _RUN_DATE.fullmatch(run_date):
        raise InvalidJobInputs("CAMS decode report run date is invalid")
    try:
        datetime.strptime(run_date, "%Y-%m-%d")
        return canonical_run_id(f"{run_date}T00:00:00Z")
    except (ValueError, ContractError) as error:
        raise InvalidJobInputs("CAMS decode report run date is invalid") from error


def _publication_timestamp(clock: Callable[[], datetime]) -> str:
    instant = clock()
    if not isinstance(instant, datetime) or instant.tzinfo is None:
        raise InvalidJobInputs("Publication clock must be timezone-aware")
    return instant.astimezone(timezone.utc).replace(microsecond=0).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )


def resolve_job_publication_intent(
    intent_directory: Path,
    *,
    job: JobKind,
    source_run_id: str,
    input_files: Mapping[str, Path] | None = None,
    input_fingerprint_sha256: str | None = None,
    clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
) -> PublicationIntentResolution:
    """Reuse an existing intent or atomically create one with the current time."""

    directory = normalize_intent_directory(intent_directory)
    if (input_files is None) == (input_fingerprint_sha256 is None):
        raise InvalidJobInputs(
            "Provide either publication input files or one verified fingerprint"
        )
    fingerprint = (
        fingerprint_input_files(input_files)
        if input_files is not None
        else input_fingerprint_sha256
    )
    assert fingerprint is not None
    intent_path = directory / f"{job.value}-{source_run_id}.json"

    try:
        return resolve_publication_intent(
            intent_path,
            job=job,
            source_run_id=source_run_id,
            input_fingerprint_sha256=fingerprint,
            published_at=None,
        )
    except InvalidPublicationIntent:
        pass

    published_at = _publication_timestamp(clock)
    try:
        return resolve_publication_intent(
            intent_path,
            job=job,
            source_run_id=source_run_id,
            input_fingerprint_sha256=fingerprint,
            published_at=published_at,
        )
    except PublicationIntentConflict:
        # An identical concurrent worker may have won with a timestamp in the
        # neighbouring second.  Re-read without constraining the frozen time;
        # every other identity field must still match exactly.
        return resolve_publication_intent(
            intent_path,
            job=job,
            source_run_id=source_run_id,
            input_fingerprint_sha256=fingerprint,
            published_at=None,
        )


def with_intent_metric(
    result: JobResult,
    resolution: PublicationIntentResolution,
) -> JobResult:
    metrics = dict(result.metrics)
    metrics["publication_intent_reused"] = resolution.reused
    return JobResult(
        job=result.job,
        status=result.status,
        reason_code=result.reason_code,
        source_run_id=result.source_run_id,
        published_providers=result.published_providers,
        retry_after_seconds=result.retry_after_seconds,
        metrics=metrics,
    )


def emit_job_result(result: JobResult, stream: TextIO) -> None:
    stream.write(canonical_json_bytes(result.as_document()).decode("utf-8") + "\n")
    stream.flush()


__all__ = [
    "MAX_IDENTITY_REPORT_BYTES",
    "cams_source_run_id_from_file",
    "emit_job_result",
    "icon_source_run_id_from_file",
    "icon_source_run_id_from_inputs",
    "normalize_database_path",
    "normalize_existing_directory",
    "normalize_existing_file",
    "normalize_intent_directory",
    "normalize_owner_id",
    "require_distinct_paths",
    "require_safe_sqlite_layout",
    "resolve_job_publication_intent",
    "sqlite_reserved_paths",
    "with_intent_metric",
]
