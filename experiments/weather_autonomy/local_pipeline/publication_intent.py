"""Create-only publication intents for the isolated weather jobs.

The first attempt for one provider run freezes its publication timestamp before
any externally visible publication can start.  Later attempts must present the
same job, source run and input fingerprint; they reuse the exact canonical JSON
bytes instead of replacing the intent.

This module is deliberately local-only.  It opens regular files, never a
network connection, and does not know about a concrete object store.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import tempfile
from types import MappingProxyType
from typing import Any, Mapping

from .contract_v1 import canonical_json_bytes
from .job_outcomes import JobKind


MAX_INTENT_BYTES = 4096
MAX_INPUT_FILES = 32
_READ_CHUNK_BYTES = 1024 * 1024
_INPUT_LABEL = re.compile(r"[a-z][a-z0-9_]{0,63}\Z")
_RUN_ID = re.compile(r"\d{8}T\d{6}Z\Z")
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_UTC_SECONDS = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z\Z")
_INTENT_KEYS = frozenset(
    {
        "schema_version",
        "kind",
        "job",
        "source_run_id",
        "published_at",
        "input_fingerprint_sha256",
    }
)
_INTENT_KIND = "meteofriul.weather.publication_intent"


class PublicationIntentError(RuntimeError):
    """Base class for an intent which cannot be used safely."""


class InvalidPublicationIntent(PublicationIntentError, ValueError):
    """The caller did not provide a complete, canonical intent identity."""


class PublicationIntentCorruption(PublicationIntentError):
    """An existing intent is malformed, non-canonical or changed while read."""


class PublicationIntentConflict(PublicationIntentError):
    """A valid existing intent belongs to different immutable inputs."""


class PublicationInputError(PublicationIntentError):
    """An input cannot be fingerprinted as one stable regular file."""


@dataclass(frozen=True)
class PublicationIntent:
    job: JobKind
    source_run_id: str
    published_at: str
    input_fingerprint_sha256: str

    def __post_init__(self) -> None:
        job = _job(self.job)
        source_run_id = _source_run_id(self.source_run_id)
        published_at = _published_at(self.published_at)
        input_fingerprint = _fingerprint(self.input_fingerprint_sha256)
        object.__setattr__(self, "job", job)
        object.__setattr__(self, "source_run_id", source_run_id)
        object.__setattr__(self, "published_at", published_at)
        object.__setattr__(
            self,
            "input_fingerprint_sha256",
            input_fingerprint,
        )

    def as_document(self) -> dict[str, object]:
        return {
            "schema_version": 1,
            "kind": _INTENT_KIND,
            "job": self.job.value,
            "source_run_id": self.source_run_id,
            "published_at": self.published_at,
            "input_fingerprint_sha256": self.input_fingerprint_sha256,
        }

    def canonical_bytes(self) -> bytes:
        return canonical_json_bytes(self.as_document())


@dataclass(frozen=True)
class PublicationIntentResolution:
    intent: PublicationIntent
    reused: bool


def _job(value: JobKind | str) -> JobKind:
    try:
        return value if isinstance(value, JobKind) else JobKind(value)
    except (TypeError, ValueError):
        raise InvalidPublicationIntent("Unsupported publication-intent job") from None


def _source_run_id(value: Any) -> str:
    if not isinstance(value, str) or not _RUN_ID.fullmatch(value):
        raise InvalidPublicationIntent("Source run identifier is not canonical")
    try:
        parsed = datetime.strptime(value, "%Y%m%dT%H%M%SZ")
    except ValueError:
        raise InvalidPublicationIntent("Source run identifier is not a valid UTC time") from None
    if (
        parsed.strftime("%Y%m%dT%H%M%SZ") != value
        or parsed.minute != 0
        or parsed.second != 0
    ):
        raise InvalidPublicationIntent("Source run identifier is not canonical")
    return value


def _published_at(value: Any) -> str:
    if not isinstance(value, str) or not _UTC_SECONDS.fullmatch(value):
        raise InvalidPublicationIntent("Publication time must use canonical UTC seconds")
    try:
        parsed = datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError:
        raise InvalidPublicationIntent("Publication time is not a valid UTC timestamp") from None
    if parsed.strftime("%Y-%m-%dT%H:%M:%SZ") != value:
        raise InvalidPublicationIntent("Publication time must use canonical UTC seconds")
    return value


def _fingerprint(value: Any) -> str:
    if not isinstance(value, str) or not _SHA256.fullmatch(value):
        raise InvalidPublicationIntent("Input fingerprint must be lowercase SHA-256")
    return value


def _strict_json(raw: bytes) -> Any:
    def reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise PublicationIntentCorruption(
                    "Publication intent contains a duplicate JSON key"
                )
            result[key] = value
        return result

    try:
        return json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=reject_duplicate_keys,
            parse_constant=lambda _value: (_ for _ in ()).throw(
                PublicationIntentCorruption(
                    "Publication intent contains a non-finite number"
                )
            ),
        )
    except PublicationIntentCorruption:
        raise
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise PublicationIntentCorruption(
            "Publication intent is not strict UTF-8 JSON"
        ) from None


def _record_from_document(value: Any) -> PublicationIntent:
    if not isinstance(value, Mapping) or set(value) != _INTENT_KEYS:
        raise PublicationIntentCorruption(
            "Publication intent has missing or extra fields"
        )
    if type(value.get("schema_version")) is not int or value["schema_version"] != 1:
        raise PublicationIntentCorruption("Publication intent schema is unsupported")
    if value.get("kind") != _INTENT_KIND:
        raise PublicationIntentCorruption("Publication intent kind is unsupported")
    try:
        return PublicationIntent(
            job=value.get("job"),
            source_run_id=value.get("source_run_id"),
            published_at=value.get("published_at"),
            input_fingerprint_sha256=value.get("input_fingerprint_sha256"),
        )
    except InvalidPublicationIntent as error:
        raise PublicationIntentCorruption(
            "Publication intent contains an invalid identity"
        ) from error


def _read_existing(path: Path) -> PublicationIntent:
    if path.is_symlink() or not path.is_file():
        raise PublicationIntentCorruption(
            "Publication intent must be a regular non-symlink file"
        )
    try:
        before = path.stat()
        if not 1 <= before.st_size <= MAX_INTENT_BYTES:
            raise PublicationIntentCorruption("Publication intent size is invalid")
        raw = path.read_bytes()
        after = path.stat()
    except PublicationIntentCorruption:
        raise
    except OSError as error:
        raise PublicationIntentCorruption("Publication intent cannot be read") from error
    if (
        len(raw) != before.st_size
        or before.st_size != after.st_size
        or before.st_mtime_ns != after.st_mtime_ns
        or getattr(before, "st_ino", None) != getattr(after, "st_ino", None)
    ):
        raise PublicationIntentCorruption(
            "Publication intent changed while it was read"
        )
    value = _strict_json(raw)
    record = _record_from_document(value)
    if raw != record.canonical_bytes():
        raise PublicationIntentCorruption(
            "Publication intent bytes are not canonical JSON"
        )
    return record


def _fsync_directory(path: Path) -> None:
    if os.name == "nt":
        return
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _create_only(path: Path, body: bytes) -> None:
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=".publication-intent.",
        suffix=".part",
        dir=path.parent,
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            descriptor = None
            stream.write(body)
            stream.flush()
            os.fsync(stream.fileno())
        os.link(temporary, path)
        _fsync_directory(path.parent)
    finally:
        if descriptor is not None:
            os.close(descriptor)
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass


def _stable_file_digest(path: Path) -> tuple[int, str]:
    if path.is_symlink():
        raise PublicationInputError("Publication input cannot be a symlink")
    try:
        with path.open("rb") as stream:
            before = os.fstat(stream.fileno())
            if not stat.S_ISREG(before.st_mode) or before.st_size < 1:
                raise PublicationInputError(
                    "Publication input must be a non-empty regular file"
                )
            digest = hashlib.sha256()
            observed_bytes = 0
            while True:
                chunk = stream.read(_READ_CHUNK_BYTES)
                if not chunk:
                    break
                observed_bytes += len(chunk)
                digest.update(chunk)
            after = os.fstat(stream.fileno())
        current = path.stat()
    except PublicationInputError:
        raise
    except OSError as error:
        raise PublicationInputError("Publication input cannot be read") from error
    stable_fields = ("st_dev", "st_ino", "st_size", "st_mtime_ns")
    if observed_bytes != before.st_size or any(
        getattr(before, field, None) != getattr(after, field, None)
        or getattr(after, field, None) != getattr(current, field, None)
        for field in stable_fields
    ):
        raise PublicationInputError("Publication input changed while fingerprinting")
    return observed_bytes, digest.hexdigest()


def fingerprint_input_files(input_files: Mapping[str, str | Path]) -> str:
    """Hash stable file contents and logical labels without embedding local paths."""

    if not isinstance(input_files, Mapping) or not 1 <= len(input_files) <= MAX_INPUT_FILES:
        raise PublicationInputError("Publication inputs must be a bounded mapping")
    records: dict[str, Mapping[str, int | str]] = {}
    selected_paths: set[str] = set()
    for label in sorted(input_files):
        if not isinstance(label, str) or not _INPUT_LABEL.fullmatch(label):
            raise PublicationInputError("Publication input label is invalid")
        raw_path = input_files[label]
        if not isinstance(raw_path, (str, Path)):
            raise PublicationInputError("Publication input path is invalid")
        path = Path(raw_path).expanduser().absolute()
        identity = os.path.normcase(os.path.realpath(path))
        if identity in selected_paths:
            raise PublicationInputError("Publication input paths must be distinct")
        selected_paths.add(identity)
        size, digest = _stable_file_digest(path)
        records[label] = MappingProxyType({"bytes": size, "sha256": digest})
    envelope = {
        "schema_version": 1,
        "kind": "meteofriul.weather.publication_inputs",
        "inputs": {label: dict(records[label]) for label in sorted(records)},
    }
    return hashlib.sha256(canonical_json_bytes(envelope)).hexdigest()


def _same_identity(
    observed: PublicationIntent,
    *,
    job: JobKind,
    source_run_id: str,
    input_fingerprint_sha256: str,
    published_at: str | None,
) -> None:
    if (
        observed.job is not job
        or observed.source_run_id != source_run_id
        or observed.input_fingerprint_sha256 != input_fingerprint_sha256
        or (published_at is not None and observed.published_at != published_at)
    ):
        raise PublicationIntentConflict(
            "Existing publication intent belongs to different immutable inputs"
        )


def resolve_publication_intent(
    path: str | Path,
    *,
    job: JobKind | str,
    source_run_id: str,
    input_fingerprint_sha256: str,
    published_at: str | None = None,
) -> PublicationIntentResolution:
    """Create an immutable intent once, or verify and reuse its exact identity.

    ``published_at`` is required only for the first attempt.  A retry may omit
    it and receives the timestamp frozen in the existing canonical intent.
    """

    selected_job = _job(job)
    selected_run = _source_run_id(source_run_id)
    selected_fingerprint = _fingerprint(input_fingerprint_sha256)
    selected_published_at = (
        None if published_at is None else _published_at(published_at)
    )
    selected_path = Path(path).expanduser().absolute()
    if selected_path.is_symlink():
        raise PublicationIntentCorruption("Publication intent path cannot be a symlink")
    if selected_path.exists():
        observed = _read_existing(selected_path)
        _same_identity(
            observed,
            job=selected_job,
            source_run_id=selected_run,
            input_fingerprint_sha256=selected_fingerprint,
            published_at=selected_published_at,
        )
        return PublicationIntentResolution(observed, reused=True)
    if not selected_path.parent.is_dir():
        raise InvalidPublicationIntent(
            "Publication intent parent directory must already exist"
        )
    if selected_published_at is None:
        raise InvalidPublicationIntent(
            "First publication attempt requires an explicit publication time"
        )
    candidate = PublicationIntent(
        selected_job,
        selected_run,
        selected_published_at,
        selected_fingerprint,
    )
    try:
        _create_only(selected_path, candidate.canonical_bytes())
        reused = False
    except FileExistsError:
        # Another writer won the create-only race.  Accept only its exact bytes
        # and identity; a different candidate is a deterministic conflict.
        reused = True
    observed = _read_existing(selected_path)
    _same_identity(
        observed,
        job=selected_job,
        source_run_id=selected_run,
        input_fingerprint_sha256=selected_fingerprint,
        published_at=selected_published_at,
    )
    return PublicationIntentResolution(observed, reused=reused)


__all__ = [
    "InvalidPublicationIntent",
    "MAX_INPUT_FILES",
    "MAX_INTENT_BYTES",
    "PublicationInputError",
    "PublicationIntent",
    "PublicationIntentConflict",
    "PublicationIntentCorruption",
    "PublicationIntentError",
    "PublicationIntentResolution",
    "fingerprint_input_files",
    "resolve_publication_intent",
]
