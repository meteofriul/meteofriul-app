"""Offline, reversible compressed-schedule exercise for the weather/v1 pilot.

The command stages explicit, already verified ICON and CAMS artifacts into a
new directory below the operating-system temporary directory.  It then uses
two new SQLite databases to exercise this sequence:

1. publish the old ICON/CAMS baseline;
2. replay the first ICON tick idempotently;
3. crash CAMS immediately after ``CORE_STAGED`` and resume it without exposing
   either CAMS member until the family pointer is committed;
4. crash the second ICON tick immediately before the ``latest.json`` CAS and
   resume it, reusing its immutable objects.

Only a loopback HTTP data plane is exposed.  A process-wide socket guard blocks
outbound connections, CAMS acquisition evidence is copied from a strict file
allow-list, and the original inputs are hash-checked again before exit.  The
test directory is deliberately retained for inspection and rollback consists
of stopping this process and restarting the ordinary pilot with its untouched
database.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import http.client
import json
import os
from pathlib import Path
import shutil
import socket
import sqlite3
import tempfile
import threading
import time
from typing import Any, Iterable, Mapping, Sequence
import uuid

from local_pipeline.cams_lifecycle import (
    CamsLifecyclePaths,
    advance_cams_lifecycle,
)
from local_pipeline.contract_publisher import (
    CamsFamilyPublicationResult,
    ContractPublicationResult,
    ContractStageResult,
    ContractV1Publisher,
)
from local_pipeline.contract_v1 import (
    CAMS_POLLEN_PROVIDER,
    CAMS_PROVIDER,
    ICON_PROVIDER,
    Catalog,
    load_catalog,
)
from local_pipeline.http_data_plane import (
    DEFAULT_ALLOWED_ORIGINS,
    IMMUTABLE_CACHE_CONTROL,
    LATEST_CACHE_CONTROL,
    make_server,
)
from local_pipeline.snapshot_materializer import (
    materialize_verified_cams,
    materialize_verified_icon,
)
from local_pipeline.sqlite_object_store import SQLiteObjectStore
from local_pipeline.sqlite_state import SqliteStateStore


PORDENONE_ISTAT = "093033"
EVIDENCE_FILES = (
    "request-plan.json",
    "request.json",
    "submission-intent.json",
    "job.json",
    "source.grib",
    "source.grib.complete.json",
)
MAX_COPY_BYTES = 512 * 1024 * 1024
_UTC_FORMAT = "%Y-%m-%dT%H:%M:%SZ"
_MATERIALIZED_PROVIDER_KEYS = {
    ICON_PROVIDER: "icon",
    CAMS_PROVIDER: "cams",
    CAMS_POLLEN_PROVIDER: "cams_pollen",
}


class CompressedScheduleError(RuntimeError):
    """The offline exercise cannot continue without weakening its guarantees."""


class InjectedCamsCrash(RuntimeError):
    """Expected crash after the durable but externally invisible CAMS core stage."""


class InjectedIconCrash(RuntimeError):
    """Expected crash before the ICON latest compare-and-swap."""


@dataclass(frozen=True)
class SourceInputs:
    icon_first_payload: Path
    icon_first_report: Path
    icon_second_payload: Path
    icon_second_report: Path
    cams_first_payload: Path
    cams_first_report: Path
    cams_second_payload: Path
    cams_second_report: Path
    cams_second_evidence_directory: Path


@dataclass(frozen=True)
class StagedInputs:
    icon_first_payload: Path
    icon_first_report: Path
    icon_second_payload: Path
    icon_second_report: Path
    cams_first_payload: Path
    cams_first_report: Path
    cams_second_payload: Path
    cams_second_report: Path
    cams_second_evidence_directory: Path


@dataclass(frozen=True)
class CopyRecord:
    role: str
    original: Path
    staged: Path
    byte_length: int
    sha256: str

    def public(self, root: Path) -> dict[str, Any]:
        return {
            "role": self.role,
            "source_name": self.original.name,
            "staged_path": self.staged.relative_to(root).as_posix(),
            "byte_length": self.byte_length,
            "sha256": self.sha256,
        }


@dataclass(frozen=True)
class PreparedRun:
    icon_first: Mapping[str, Any]
    icon_second: Mapping[str, Any]
    cams_first: Mapping[str, Any]
    cams_second: Mapping[str, Any]
    virtual_now: datetime
    baseline_published_at: str
    cams_second_published_at: str
    icon_second_published_at: str


def _utc(value: datetime) -> str:
    return value.astimezone(timezone.utc).replace(microsecond=0).strftime(_UTC_FORMAT)


def _parse_utc(value: str, label: str) -> datetime:
    try:
        parsed = datetime.strptime(value, _UTC_FORMAT).replace(tzinfo=timezone.utc)
    except (TypeError, ValueError) as error:
        raise CompressedScheduleError(f"{label} must use canonical UTC seconds") from error
    return parsed


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _under(child: Path, parent: Path) -> bool:
    try:
        child.relative_to(parent)
    except ValueError:
        return False
    return True


def _new_test_directory(path: Path) -> Path:
    root = Path(tempfile.gettempdir()).resolve()
    candidate = Path(path).expanduser().resolve()
    if candidate == root or not _under(candidate, root):
        raise CompressedScheduleError("work directory must be a new child of the OS temp directory")
    if candidate.exists():
        raise CompressedScheduleError("work directory already exists; refusing to overwrite it")
    if not candidate.parent.is_dir():
        raise CompressedScheduleError("work directory parent must already exist")
    candidate.mkdir()
    return candidate


def _copy_verified(role: str, source: Path, destination: Path) -> CopyRecord:
    raw_source = Path(source).expanduser()
    if raw_source.is_symlink():
        raise CompressedScheduleError(f"{role} source cannot be a symbolic link")
    try:
        selected = raw_source.resolve(strict=True)
    except OSError as error:
        raise CompressedScheduleError(f"{role} source is missing") from error
    if not selected.is_file():
        raise CompressedScheduleError(f"{role} source is not a regular file")
    size = selected.stat().st_size
    if not 1 <= size <= MAX_COPY_BYTES:
        raise CompressedScheduleError(f"{role} source has an unsafe byte size")
    before = _sha256_file(selected)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with selected.open("rb") as source_stream, destination.open("xb") as target_stream:
        shutil.copyfileobj(source_stream, target_stream, length=1024 * 1024)
        target_stream.flush()
        os.fsync(target_stream.fileno())
    after = _sha256_file(selected)
    copied = _sha256_file(destination)
    if before != after or copied != before or destination.stat().st_size != size:
        raise CompressedScheduleError(f"{role} changed while it was being staged")
    return CopyRecord(role, selected, destination, size, before)


def _write_new_json(path: Path, value: Mapping[str, Any]) -> None:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2).encode("utf-8") + b"\n"
    with path.open("xb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())


def stage_inputs(inputs: SourceInputs, work_directory: Path) -> tuple[StagedInputs, tuple[CopyRecord, ...]]:
    root = _new_test_directory(work_directory)
    evidence_source = Path(inputs.cams_second_evidence_directory).expanduser()
    if evidence_source.is_symlink():
        raise CompressedScheduleError("CAMS evidence directory cannot be a symbolic link")
    try:
        evidence_source = evidence_source.resolve(strict=True)
    except OSError as error:
        raise CompressedScheduleError("CAMS evidence directory is missing") from error
    if not evidence_source.is_dir() or _under(root, evidence_source):
        raise CompressedScheduleError("CAMS evidence source and work directory must be separate")

    destinations = {
        "icon_first_payload": root / "inputs" / "icon-first" / "payload.json",
        "icon_first_report": root / "inputs" / "icon-first" / "report.json",
        "icon_second_payload": root / "inputs" / "icon-second" / "payload.json",
        "icon_second_report": root / "inputs" / "icon-second" / "report.json",
        "cams_first_payload": root / "inputs" / "cams-first" / "payload.json",
        "cams_first_report": root / "inputs" / "cams-first" / "report.json",
    }
    records: list[CopyRecord] = []
    for role, destination in destinations.items():
        records.append(_copy_verified(role, getattr(inputs, role), destination))

    evidence_target = root / "inputs" / "cams-second-evidence"
    for filename in EVIDENCE_FILES:
        records.append(
            _copy_verified(
                f"cams_evidence_{filename}",
                evidence_source / filename,
                evidence_target / filename,
            )
        )
    cams_second_payload = evidence_target / "decoded-payload.json"
    cams_second_report = evidence_target / "decode-report.json"
    records.append(_copy_verified("cams_second_payload", inputs.cams_second_payload, cams_second_payload))
    records.append(_copy_verified("cams_second_report", inputs.cams_second_report, cams_second_report))

    staged = StagedInputs(
        icon_first_payload=destinations["icon_first_payload"],
        icon_first_report=destinations["icon_first_report"],
        icon_second_payload=destinations["icon_second_payload"],
        icon_second_report=destinations["icon_second_report"],
        cams_first_payload=destinations["cams_first_payload"],
        cams_first_report=destinations["cams_first_report"],
        cams_second_payload=cams_second_payload,
        cams_second_report=cams_second_report,
        cams_second_evidence_directory=evidence_target,
    )
    _write_new_json(
        root / "staging-manifest.json",
        {
            "schema_version": 1,
            "kind": "meteofriul.weather.compressed_schedule_staging",
            "network_used": False,
            "credential_files_copied": False,
            "copies": [record.public(root) for record in records],
        },
    )
    return staged, tuple(records)


def verify_sources_unchanged(records: Iterable[CopyRecord]) -> None:
    for record in records:
        if (
            not record.original.is_file()
            or record.original.stat().st_size != record.byte_length
            or _sha256_file(record.original) != record.sha256
        ):
            raise CompressedScheduleError(f"original input changed during run: {record.role}")


class RunJournal:
    def __init__(self, root: Path, copies: Sequence[CopyRecord]) -> None:
        self.root = root
        self.events_path = root / "events.jsonl"
        self.report_path = root / "report.json"
        self.started = time.monotonic()
        self.events: list[dict[str, Any]] = []
        self.report: dict[str, Any] = {
            "schema_version": 1,
            "kind": "meteofriul.weather.compressed_schedule_report",
            "status": "starting",
            "work_directory": str(root),
            "network_policy": "loopback-only; no provider, credential, or cloud access",
            "source_copies": [record.public(root) for record in copies],
            "events": self.events,
        }
        self._flush_report()

    def _flush_report(self) -> None:
        raw = json.dumps(self.report, ensure_ascii=False, sort_keys=True, indent=2).encode("utf-8") + b"\n"
        temporary = self.root / f".report-{uuid.uuid4().hex}.tmp"
        with temporary.open("xb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, self.report_path)

    def event(self, name: str, **details: Any) -> dict[str, Any]:
        entry = {
            "sequence": len(self.events) + 1,
            "event": name,
            "elapsed_seconds": round(time.monotonic() - self.started, 3),
            "details": details,
        }
        raw = json.dumps(entry, ensure_ascii=False, sort_keys=True).encode("utf-8") + b"\n"
        with self.events_path.open("ab") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        self.events.append(entry)
        self._flush_report()
        print(raw.decode("utf-8").rstrip(), flush=True)
        return entry

    def finish(self, status: str, **details: Any) -> None:
        self.report.update(details)
        self.report["status"] = status
        self.report["elapsed_seconds"] = round(time.monotonic() - self.started, 3)
        self._flush_report()


class LoopbackOnlyNetworkGuard:
    """Block every Python socket destination except numeric/local loopback."""

    _HOSTS = frozenset(("127.0.0.1", "::1", "localhost"))

    def __init__(self) -> None:
        self._original_connect = socket.socket.connect
        self._original_connect_ex = socket.socket.connect_ex
        self._original_sendto = socket.socket.sendto
        self._original_getaddrinfo = socket.getaddrinfo

    @classmethod
    def require_loopback(cls, address: Any) -> None:
        if not isinstance(address, tuple) or not address or str(address[0]).lower() not in cls._HOSTS:
            raise OSError("offline schedule test blocked a non-loopback network destination")

    def __enter__(self) -> "LoopbackOnlyNetworkGuard":
        guard = self

        def connect(instance: socket.socket, address: Any) -> Any:
            guard.require_loopback(address)
            return guard._original_connect(instance, address)

        def connect_ex(instance: socket.socket, address: Any) -> Any:
            guard.require_loopback(address)
            return guard._original_connect_ex(instance, address)

        def sendto(instance: socket.socket, data: bytes, *args: Any) -> Any:
            if not args:
                raise OSError("offline schedule test blocked an unaddressed datagram")
            guard.require_loopback(args[-1])
            return guard._original_sendto(instance, data, *args)

        def getaddrinfo(host: Any, *args: Any, **kwargs: Any) -> Any:
            if str(host).lower() not in guard._HOSTS:
                raise OSError("offline schedule test blocked DNS for a non-loopback host")
            return guard._original_getaddrinfo(host, *args, **kwargs)

        socket.socket.connect = connect
        socket.socket.connect_ex = connect_ex
        socket.socket.sendto = sendto
        socket.getaddrinfo = getaddrinfo
        return self

    def __exit__(self, *_args: object) -> None:
        socket.socket.connect = self._original_connect
        socket.socket.connect_ex = self._original_connect_ex
        socket.socket.sendto = self._original_sendto
        socket.getaddrinfo = self._original_getaddrinfo


class FailBeforeLatestCasStore:
    """Delegate every operation except one selected latest CAS."""

    def __init__(self, store: SQLiteObjectStore, latest_key: str) -> None:
        self._store = store
        self.latest_key = latest_key
        self.triggered = False

    def compare_and_swap(self, key: str, body: bytes, **kwargs: Any) -> Any:
        if key == self.latest_key and not self.triggered:
            self.triggered = True
            raise InjectedIconCrash("injected crash before ICON latest CAS")
        return self._store.compare_and_swap(key, body, **kwargs)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._store, name)


class LoopbackDataPlane:
    def __init__(self, store: SQLiteObjectStore, port: int, origins: Iterable[str]) -> None:
        self.server = make_server(store, port=port, allowed_origins=origins)
        self.thread = threading.Thread(
            target=self.server.serve_forever,
            name="weather-compressed-schedule-http",
            daemon=True,
        )

    @property
    def port(self) -> int:
        return int(self.server.server_address[1])

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.port}/weather/v1/"

    def __enter__(self) -> "LoopbackDataPlane":
        self.thread.start()
        return self

    def __exit__(self, *_args: object) -> None:
        self.server.shutdown()
        self.thread.join(timeout=10)
        self.server.server_close()


class ContinuityMonitor:
    def __init__(
        self,
        port: int,
        publisher: ContractV1Publisher,
        interval_seconds: float = 0.25,
    ) -> None:
        self.port = port
        self.publisher = publisher
        self.interval_seconds = interval_seconds
        self.stop_event = threading.Event()
        self.lock = threading.Lock()
        self.thread = threading.Thread(target=self._run, name="weather-continuity-monitor", daemon=True)
        self.checks = 0
        self.failures: list[str] = []
        self.transitions: list[dict[str, str]] = []

    def _request(
        self,
        path: str,
        *,
        expected_cache_control: str,
    ) -> tuple[dict[str, Any], str, bytes]:
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=3)
        try:
            connection.request("GET", path, headers={"Accept-Encoding": "identity"})
            response = connection.getresponse()
            body = response.read(1024 * 1024 + 1)
            if response.status != 200 or len(body) > 1024 * 1024:
                raise CompressedScheduleError(f"local HTTP continuity status {response.status}")
            value = json.loads(body)
            if not isinstance(value, dict):
                raise CompressedScheduleError("local HTTP response is not a JSON object")
            etag = str(response.getheader("ETag") or "")
            if not etag:
                raise CompressedScheduleError("local HTTP response omitted its ETag")
            if response.getheader("Cache-Control") != expected_cache_control:
                raise CompressedScheduleError(
                    f"local HTTP response has invalid cache policy for {path}"
                )
        finally:
            connection.close()

        conditional = http.client.HTTPConnection("127.0.0.1", self.port, timeout=3)
        try:
            conditional.request(
                "GET",
                path,
                headers={"Accept-Encoding": "identity", "If-None-Match": etag},
            )
            cached = conditional.getresponse()
            cached_body = cached.read(1024 * 1024 + 1)
            cached_etag = str(cached.getheader("ETag") or "")
            cached_policy = cached.getheader("Cache-Control")
            if cached.status == 304:
                valid = (
                    not cached_body
                    and cached_etag == etag
                    and cached_policy == expected_cache_control
                )
            elif cached.status == 200 and expected_cache_control == LATEST_CACHE_CONTROL:
                # A latest pointer may legitimately switch between the GET and
                # its conditional revalidation.  Accept only a complete newer
                # JSON representation with a different strong ETag.
                try:
                    refreshed = json.loads(cached_body)
                except (UnicodeDecodeError, json.JSONDecodeError):
                    refreshed = None
                valid = (
                    isinstance(refreshed, dict)
                    and bool(cached_etag)
                    and cached_etag != etag
                    and cached_policy == expected_cache_control
                )
                if valid:
                    value = refreshed
                    etag = cached_etag
                    body = cached_body
            else:
                valid = False
            if not valid:
                raise CompressedScheduleError(
                    f"local HTTP conditional cache contract failed for {path}"
                )
        finally:
            conditional.close()
        return value, etag, body

    def _assert_legacy_latest_hidden(self, path: str) -> None:
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=3)
        try:
            connection.request("GET", path, headers={"Accept-Encoding": "identity"})
            response = connection.getresponse()
            response.read(1024 * 1024 + 1)
            if (
                response.status != 400
                or response.getheader("Cache-Control") != "no-store"
            ):
                raise CompressedScheduleError(
                    f"retired CAMS provider latest unexpectedly returned {response.status}"
                )
        finally:
            connection.close()

    def check_once(self) -> dict[str, str]:
        observed: dict[str, str] = {}
        latest, etag, _latest_body = self._request(
            f"/weather/v1/{ICON_PROVIDER}/latest.json",
            expected_cache_control=LATEST_CACHE_CONTROL,
        )
        descriptor = latest.get("latest")
        icon_run_id = (
            descriptor.get("source_run_id") if isinstance(descriptor, Mapping) else None
        )
        if (
            latest.get("provider") != ICON_PROVIDER
            or not isinstance(icon_run_id, str)
            or not etag
        ):
            raise CompressedScheduleError("invalid loopback latest response for ICON")
        observed[ICON_PROVIDER] = icon_run_id
        icon_payload, _payload_etag, _icon_payload_body = self._request(
            f"/weather/v1/{ICON_PROVIDER}/runs/{icon_run_id}/municipalities/"
            f"{PORDENONE_ISTAT}.json",
            expected_cache_control=IMMUTABLE_CACHE_CONTROL,
        )
        municipality = icon_payload.get("municipality")
        if (
            not isinstance(municipality, Mapping)
            or municipality.get("istat_code") != PORDENONE_ISTAT
        ):
            raise CompressedScheduleError("invalid Pordenone payload for ICON")

        # CAMS has one externally visible family pointer.  The old per-provider
        # latest paths must remain absent even while either immutable component
        # is being staged.
        for provider in (CAMS_PROVIDER, CAMS_POLLEN_PROVIDER):
            if self.publisher.read_latest(provider) is not None:
                raise CompressedScheduleError(
                    f"retired per-provider CAMS latest became visible for {provider}"
                )
            self._assert_legacy_latest_hidden(f"/weather/v1/{provider}/latest.json")

        family, family_etag, _family_body = self._request(
            "/weather/v1/families/cams/latest.json",
            expected_cache_control=LATEST_CACHE_CONTROL,
        )
        family_descriptor = family.get("latest") if isinstance(family, Mapping) else None
        cams_run_id = (
            family_descriptor.get("source_run_id")
            if isinstance(family_descriptor, Mapping)
            else None
        )
        release_path = (
            family_descriptor.get("release_path")
            if isinstance(family_descriptor, Mapping)
            else None
        )
        if (
            family.get("family") != "cams"
            or not isinstance(cams_run_id, str)
            or release_path != f"runs/{cams_run_id}/release.json"
            or not family_etag
        ):
            raise CompressedScheduleError("HTTP CAMS family latest is invalid")
        release, release_etag, release_body = self._request(
            f"/weather/v1/families/cams/{release_path}",
            expected_cache_control=IMMUTABLE_CACHE_CONTROL,
        )
        components = release.get("components")
        expected_release_sha256 = (
            family_descriptor.get("release_sha256")
            if isinstance(family_descriptor, Mapping)
            else None
        )
        expected_release_bytes = (
            family_descriptor.get("release_json_bytes")
            if isinstance(family_descriptor, Mapping)
            else None
        )
        if (
            release.get("family") != "cams"
            or release.get("source_run_id") != cams_run_id
            or not isinstance(components, Mapping)
            or not release_etag
            or expected_release_sha256 != hashlib.sha256(release_body).hexdigest()
            or expected_release_bytes != len(release_body)
        ):
            raise CompressedScheduleError("HTTP CAMS family release is invalid")
        for role, provider in (
            ("core", CAMS_PROVIDER),
            ("pollen", CAMS_POLLEN_PROVIDER),
        ):
            component = components.get(role)
            if (
                not isinstance(component, Mapping)
                or component.get("provider") != provider
                or component.get("source_run_id") != cams_run_id
            ):
                raise CompressedScheduleError(
                    f"HTTP CAMS family release has invalid {role} component"
                )
        observed[CAMS_PROVIDER] = cams_run_id
        observed[CAMS_POLLEN_PROVIDER] = cams_run_id
        for provider in (CAMS_PROVIDER, CAMS_POLLEN_PROVIDER):
            payload, _payload_etag, _payload_body = self._request(
                f"/weather/v1/{provider}/runs/{cams_run_id}/municipalities/"
                f"{PORDENONE_ISTAT}.json",
                expected_cache_control=IMMUTABLE_CACHE_CONTROL,
            )
            municipality = payload.get("municipality")
            if (
                not isinstance(municipality, Mapping)
                or municipality.get("istat_code") != PORDENONE_ISTAT
            ):
                raise CompressedScheduleError(f"invalid Pordenone payload for {provider}")
        with self.lock:
            self.checks += 1
            if not self.transitions or self.transitions[-1] != observed:
                self.transitions.append(dict(observed))
        return observed

    def _run(self) -> None:
        while not self.stop_event.is_set():
            try:
                self.check_once()
            except Exception as error:  # Observed and made fatal at the next gate.
                with self.lock:
                    if len(self.failures) < 50:
                        self.failures.append(f"{type(error).__name__}: {error}"[:500])
            self.stop_event.wait(self.interval_seconds)

    def start(self) -> None:
        self.check_once()
        self.thread.start()

    def assert_healthy(self) -> dict[str, str]:
        observed = self.check_once()
        with self.lock:
            failures = tuple(self.failures)
        if failures:
            raise CompressedScheduleError(f"continuity monitor observed {len(failures)} failure(s)")
        return observed

    def summary(self) -> dict[str, Any]:
        with self.lock:
            return {
                "checks": self.checks,
                "failure_count": len(self.failures),
                "failures": list(self.failures),
                "observed_transitions": list(self.transitions),
            }

    def close(self) -> None:
        self.stop_event.set()
        if self.thread.is_alive():
            self.thread.join(timeout=10)


def _provider_bundle(bundle: Mapping[str, Any], provider: str) -> Mapping[str, Any]:
    selected = bundle.get(_MATERIALIZED_PROVIDER_KEYS.get(provider, ""))
    if not isinstance(selected, Mapping):
        raise CompressedScheduleError(f"materializer omitted {provider} provider bundle")
    return selected


def _manifest(bundle: Mapping[str, Any], provider: str) -> Mapping[str, Any]:
    selected = _provider_bundle(bundle, provider)
    manifest = selected.get("manifest") if isinstance(selected, Mapping) else None
    if not isinstance(manifest, Mapping):
        raise CompressedScheduleError(f"materializer omitted {provider} manifest")
    return manifest


def _recommended_clock(manifests: Iterable[Mapping[str, Any]]) -> datetime:
    selected = tuple(manifests)
    starts = [_parse_utc(str(value["valid_from"]), "valid_from") for value in selected]
    ends = [_parse_utc(str(value["freshness"]["usable_until"]), "usable_until") for value in selected]
    candidate = max(starts) + timedelta(minutes=30)
    if candidate > min(ends):
        raise CompressedScheduleError("old and new artifacts have no freshness-compatible clock overlap")
    return candidate


def _publication_summary(result: ContractPublicationResult) -> dict[str, Any]:
    return {
        "provider": result.provider,
        "source_run_id": result.source_run_id,
        "object_count": len(result.payload_keys),
        "reused_payload_count": result.reused_payload_count,
        "manifest_reused": result.manifest_reused,
        "idempotent": result.idempotent,
        "latest_updated": result.latest_updated,
        "superseded": result.superseded,
        "latest_etag": result.latest_etag,
    }


def _stage_summary(result: ContractStageResult) -> dict[str, Any]:
    return {
        "provider": result.provider,
        "source_run_id": result.source_run_id,
        "object_count": len(result.payload_keys),
        "reused_payload_count": result.reused_payload_count,
        "manifest_reused": result.manifest_reused,
        "idempotent": result.idempotent,
        "manifest_etag": result.manifest_etag,
        "visible": False,
    }


def _family_publication_summary(
    result: CamsFamilyPublicationResult,
) -> dict[str, Any]:
    return {
        "source_run_id": result.source_run_id,
        "release_key": result.release_key,
        "release_reused": result.release_reused,
        "idempotent": result.idempotent,
        "latest_updated": result.latest_updated,
        "superseded": result.superseded,
        "latest_etag": result.latest_etag,
        "revision": result.revision,
    }


def _baseline_validation_sha256(
    core: ContractStageResult,
    pollen: ContractStageResult,
) -> str:
    identity = (
        f"compressed-schedule-baseline:{core.source_run_id}:"
        f"{core.manifest_sha256}:{pollen.manifest_sha256}"
    )
    return hashlib.sha256(identity.encode("ascii")).hexdigest()


class OfflineScheduleBackend:
    def __init__(self, root: Path, staged: StagedInputs, virtual_now: str | None) -> None:
        self.root = root
        self.staged = staged
        self.catalog: Catalog = load_catalog()
        self.object_db = root / "weather-objects.sqlite3"
        self.state_db = root / "cams-state.sqlite3"
        self.objects = SQLiteObjectStore(self.object_db, state_database_path=self.state_db)
        self.state = SqliteStateStore(self.state_db)
        self.publisher = ContractV1Publisher(self.objects, self.catalog)
        self.requested_virtual_now = virtual_now
        self.prepared: PreparedRun | None = None

    def prepare(self) -> PreparedRun:
        icon_first = materialize_verified_icon(
            catalog=self.catalog,
            icon_archive=self.staged.icon_first_payload,
            icon_report=self.staged.icon_first_report,
        )
        icon_second = materialize_verified_icon(
            catalog=self.catalog,
            icon_archive=self.staged.icon_second_payload,
            icon_report=self.staged.icon_second_report,
        )
        cams_first = materialize_verified_cams(
            catalog=self.catalog,
            cams_payload=self.staged.cams_first_payload,
            cams_report=self.staged.cams_first_report,
        )
        cams_second = materialize_verified_cams(
            catalog=self.catalog,
            cams_payload=self.staged.cams_second_payload,
            cams_report=self.staged.cams_second_report,
        )
        manifests = (
            _manifest(icon_first, ICON_PROVIDER),
            _manifest(icon_second, ICON_PROVIDER),
            _manifest(cams_first, CAMS_PROVIDER),
            _manifest(cams_first, CAMS_POLLEN_PROVIDER),
            _manifest(cams_second, CAMS_PROVIDER),
            _manifest(cams_second, CAMS_POLLEN_PROVIDER),
        )
        first_icon_run = str(manifests[0]["source_run_id"])
        second_icon_run = str(manifests[1]["source_run_id"])
        first_cams_run = str(manifests[2]["source_run_id"])
        second_cams_run = str(manifests[4]["source_run_id"])
        if not first_icon_run < second_icon_run or not first_cams_run < second_cams_run:
            raise CompressedScheduleError("second snapshots must be newer than first snapshots")
        recommended = _recommended_clock(manifests)
        virtual_now = (
            _parse_utc(self.requested_virtual_now, "virtual now")
            if self.requested_virtual_now
            else recommended
        )
        if virtual_now < max(_parse_utc(str(value["valid_from"]), "valid_from") for value in manifests):
            raise CompressedScheduleError("virtual now precedes a staged run")
        if virtual_now > min(
            _parse_utc(str(value["freshness"]["usable_until"]), "usable_until")
            for value in manifests
        ):
            raise CompressedScheduleError("virtual now is outside old/new usable overlap")
        prepared = PreparedRun(
            icon_first=icon_first,
            icon_second=icon_second,
            cams_first=cams_first,
            cams_second=cams_second,
            virtual_now=virtual_now,
            baseline_published_at=_utc(virtual_now - timedelta(minutes=3)),
            cams_second_published_at=_utc(virtual_now - timedelta(minutes=2)),
            icon_second_published_at=_utc(virtual_now - timedelta(minutes=1)),
        )
        self.prepared = prepared
        return prepared

    def _required(self) -> PreparedRun:
        if self.prepared is None:
            raise CompressedScheduleError("backend was not prepared")
        return self.prepared

    def publish_baseline(self) -> Mapping[str, Any]:
        prepared = self._required()
        icon = _provider_bundle(prepared.icon_first, ICON_PROVIDER)
        cams = _provider_bundle(prepared.cams_first, CAMS_PROVIDER)
        pollen = _provider_bundle(prepared.cams_first, CAMS_POLLEN_PROVIDER)
        icon_publication = self.publisher.publish_run(
            ICON_PROVIDER,
            icon["documents"],
            icon["manifest"],
            published_at=prepared.baseline_published_at,
        )
        core_stage = self.publisher.stage_run(
            CAMS_PROVIDER,
            cams["documents"],
            cams["manifest"],
        )
        pollen_stage = self.publisher.stage_run(
            CAMS_POLLEN_PROVIDER,
            pollen["documents"],
            pollen["manifest"],
        )
        family_publication = self.publisher.release_cams_family(
            core_stage,
            pollen_stage,
            validation_sha256=_baseline_validation_sha256(
                core_stage,
                pollen_stage,
            ),
            published_at=prepared.baseline_published_at,
        )
        if (
            self.publisher.read_latest(CAMS_PROVIDER) is not None
            or self.publisher.read_latest(CAMS_POLLEN_PROVIDER) is not None
        ):
            raise CompressedScheduleError(
                "baseline exposed a retired per-provider CAMS latest"
            )
        return {
            "icon": icon_publication,
            "core_stage": core_stage,
            "pollen_stage": pollen_stage,
            "family": family_publication,
        }

    def icon_first_tick(self) -> ContractPublicationResult:
        prepared = self._required()
        icon = _provider_bundle(prepared.icon_first, ICON_PROVIDER)
        return self.publisher.publish_run(
            ICON_PROVIDER,
            icon["documents"],
            icon["manifest"],
            published_at=prepared.baseline_published_at,
        )

    def _cams_paths(self) -> CamsLifecyclePaths:
        return CamsLifecyclePaths(
            self.staged.cams_second_evidence_directory,
            self.staged.cams_second_payload,
            self.staged.cams_second_report,
        )

    def cams_fault(self) -> Mapping[str, Any]:
        prepared = self._required()
        before = self.publisher.read_verified_cams_family_latest()
        before_descriptor = before.get("latest") if isinstance(before, Mapping) else None
        before_run_id = (
            before_descriptor.get("source_run_id")
            if isinstance(before_descriptor, Mapping)
            else None
        )
        if not isinstance(before_run_id, str):
            raise CompressedScheduleError("CAMS family baseline is unavailable")
        fired = False

        def crash(step: str) -> None:
            nonlocal fired
            if step == "CORE_STAGED":
                fired = True
                raise InjectedCamsCrash("injected crash after CAMS CORE_STAGED")

        try:
            advance_cams_lifecycle(
                paths=self._cams_paths(),
                catalog=self.catalog,
                state_store=self.state,
                publisher=self.publisher,
                owner_id="compressed-schedule-worker",
                published_at=prepared.cams_second_published_at,
                now=prepared.virtual_now,
                after_step=crash,
            )
        except InjectedCamsCrash:
            pass
        else:
            raise CompressedScheduleError("CAMS fault injection did not fire")
        if not fired:
            raise CompressedScheduleError("CAMS did not reach CORE_STAGED")
        after = self.publisher.read_verified_cams_family_latest()
        after_descriptor = after.get("latest") if isinstance(after, Mapping) else None
        after_run_id = (
            after_descriptor.get("source_run_id")
            if isinstance(after_descriptor, Mapping)
            else None
        )
        if after_run_id != before_run_id:
            raise CompressedScheduleError(
                "staging one CAMS member changed the atomic family latest"
            )
        if (
            self.publisher.read_latest(CAMS_PROVIDER) is not None
            or self.publisher.read_latest(CAMS_POLLEN_PROVIDER) is not None
        ):
            raise CompressedScheduleError(
                "CAMS staging exposed a retired per-provider latest"
            )
        return {
            **self.cams_state_summary(),
            "family_source_run_id": after_run_id,
            "provider_latest_visible": False,
        }

    def cams_retry(self) -> Mapping[str, Any]:
        prepared = self._required()
        result = advance_cams_lifecycle(
            paths=self._cams_paths(),
            catalog=self.catalog,
            state_store=self.state,
            publisher=self.publisher,
            owner_id="compressed-schedule-worker",
            published_at=prepared.cams_second_published_at,
            now=prepared.virtual_now,
        )
        if (
            result.record.state.value != "PUBLISHED"
            or not result.core_stage.idempotent
            or result.family_publication.superseded
        ):
            raise CompressedScheduleError("CAMS retry did not resume idempotently")
        if (
            self.publisher.read_latest(CAMS_PROVIDER) is not None
            or self.publisher.read_latest(CAMS_POLLEN_PROVIDER) is not None
        ):
            raise CompressedScheduleError(
                "CAMS retry exposed a retired per-provider latest"
            )
        return {
            "state": result.record.state.value,
            "core_stage": _stage_summary(result.core_stage),
            "pollen_stage": _stage_summary(result.pollen_stage),
            "family": _family_publication_summary(result.family_publication),
            "lifecycle": self.cams_state_summary(),
        }

    def cams_state_summary(self) -> Mapping[str, Any]:
        with sqlite3.connect(self.state_db) as connection:
            rows = connection.execute(
                "SELECT source_run_id, request_hash, state FROM runs ORDER BY created_at"
            ).fetchall()
            transitions = [
                value[0]
                for value in connection.execute(
                    "SELECT to_state FROM transitions ORDER BY sequence"
                ).fetchall()
            ]
        if len(rows) != 1:
            raise CompressedScheduleError("CAMS state DB must contain exactly one staged run")
        return {
            "source_run_id": rows[0][0],
            "request_hash": rows[0][1],
            "state": rows[0][2],
            "transitions": transitions,
        }

    def icon_fault(self) -> Mapping[str, Any]:
        prepared = self._required()
        icon = _provider_bundle(prepared.icon_second, ICON_PROVIDER)
        guarded_store = FailBeforeLatestCasStore(
            self.objects,
            self.publisher.latest_key(ICON_PROVIDER),
        )
        crashing_publisher = ContractV1Publisher(guarded_store, self.catalog)
        try:
            crashing_publisher.publish_run(
                ICON_PROVIDER,
                icon["documents"],
                icon["manifest"],
                published_at=prepared.icon_second_published_at,
            )
        except InjectedIconCrash:
            pass
        else:
            raise CompressedScheduleError("ICON fault injection did not fire")
        if not guarded_store.triggered:
            raise CompressedScheduleError("ICON did not reach the latest CAS")
        manifest = icon["manifest"]
        manifest_key = self.publisher.manifest_key(ICON_PROVIDER, str(manifest["source_run_id"]))
        if not self.objects.exists(manifest_key):
            raise CompressedScheduleError("ICON immutable manifest was not staged before the crash")
        return {"fault": "before_latest_cas", "immutable_manifest_present": True}

    def icon_retry(self) -> ContractPublicationResult:
        prepared = self._required()
        icon = _provider_bundle(prepared.icon_second, ICON_PROVIDER)
        result = self.publisher.publish_run(
            ICON_PROVIDER,
            icon["documents"],
            icon["manifest"],
            published_at=prepared.icon_second_published_at,
        )
        if result.reused_payload_count != 215 or not result.manifest_reused or not result.latest_updated:
            raise CompressedScheduleError("ICON retry did not reuse the complete staged run")
        return result

    def verified_latest(self) -> dict[str, str]:
        icon_latest = self.publisher.read_verified_latest(ICON_PROVIDER)
        icon_descriptor = (
            icon_latest.get("latest") if isinstance(icon_latest, Mapping) else None
        )
        icon_run_id = (
            icon_descriptor.get("source_run_id")
            if isinstance(icon_descriptor, Mapping)
            else None
        )
        family_latest = self.publisher.read_verified_cams_family_latest()
        family_descriptor = (
            family_latest.get("latest")
            if isinstance(family_latest, Mapping)
            else None
        )
        cams_run_id = (
            family_descriptor.get("source_run_id")
            if isinstance(family_descriptor, Mapping)
            else None
        )
        if not isinstance(icon_run_id, str) or not isinstance(cams_run_id, str):
            raise CompressedScheduleError("verified ICON/CAMS latest is unavailable")
        if (
            self.publisher.read_latest(CAMS_PROVIDER) is not None
            or self.publisher.read_latest(CAMS_POLLEN_PROVIDER) is not None
        ):
            raise CompressedScheduleError(
                "retired per-provider CAMS latest must remain absent"
            )
        return {
            ICON_PROVIDER: icon_run_id,
            CAMS_PROVIDER: cams_run_id,
            CAMS_POLLEN_PROVIDER: cams_run_id,
        }

    def expected_runs(self) -> tuple[dict[str, str], dict[str, str], dict[str, str], dict[str, str]]:
        prepared = self._required()
        old_icon = str(_manifest(prepared.icon_first, ICON_PROVIDER)["source_run_id"])
        new_icon = str(_manifest(prepared.icon_second, ICON_PROVIDER)["source_run_id"])
        old_cams = str(_manifest(prepared.cams_first, CAMS_PROVIDER)["source_run_id"])
        new_cams = str(_manifest(prepared.cams_second, CAMS_PROVIDER)["source_run_id"])
        baseline = {
            ICON_PROVIDER: old_icon,
            CAMS_PROVIDER: old_cams,
            CAMS_POLLEN_PROVIDER: old_cams,
        }
        cams_staged_invisible = {
            ICON_PROVIDER: old_icon,
            CAMS_PROVIDER: old_cams,
            CAMS_POLLEN_PROVIDER: old_cams,
        }
        cams_complete = {
            ICON_PROVIDER: old_icon,
            CAMS_PROVIDER: new_cams,
            CAMS_POLLEN_PROVIDER: new_cams,
        }
        final = {
            ICON_PROVIDER: new_icon,
            CAMS_PROVIDER: new_cams,
            CAMS_POLLEN_PROVIDER: new_cams,
        }
        return baseline, cams_staged_invisible, cams_complete, final

    def close(self) -> None:
        self.state.close()
        self.objects.close()


def _gate(
    backend: OfflineScheduleBackend,
    monitor: ContinuityMonitor,
    expected: Mapping[str, str],
) -> dict[str, str]:
    verified = backend.verified_latest()
    served = monitor.assert_healthy()
    if verified != dict(expected) or served != dict(expected):
        raise CompressedScheduleError(
            f"latest state mismatch: expected {dict(expected)}, verified {verified}, served {served}"
        )
    return verified


def run_sequence(
    backend: OfflineScheduleBackend,
    journal: RunJournal,
    monitor: ContinuityMonitor,
    *,
    step_delay_seconds: float,
    final_observation_seconds: float,
) -> dict[str, Any]:
    baseline, cams_staged_invisible, cams_complete, final = backend.expected_runs()

    def wait() -> None:
        if step_delay_seconds:
            time.sleep(step_delay_seconds)

    observed = _gate(backend, monitor, baseline)
    journal.event("baseline_served", latest=observed)
    wait()

    icon_first = backend.icon_first_tick()
    if not icon_first.idempotent or icon_first.latest_updated:
        raise CompressedScheduleError("first ICON tick was not idempotent")
    observed = _gate(backend, monitor, baseline)
    journal.event("icon_first_idempotent", publication=_publication_summary(icon_first), latest=observed)
    wait()

    cams_fault = backend.cams_fault()
    if cams_fault.get("state") != "VALIDATED":
        raise CompressedScheduleError("CAMS crash did not leave durable VALIDATED state")
    if cams_fault.get("provider_latest_visible") is not False:
        raise CompressedScheduleError(
            "CAMS crash did not prove per-provider latest remained invisible"
        )
    observed = _gate(backend, monitor, cams_staged_invisible)
    journal.event(
        "cams_expected_crash_after_core_stage",
        lifecycle=cams_fault,
        latest=observed,
    )
    wait()

    cams_retry = backend.cams_retry()
    observed = _gate(backend, monitor, cams_complete)
    journal.event("cams_retry_completed", result=cams_retry, latest=observed)
    wait()

    icon_fault = backend.icon_fault()
    observed = _gate(backend, monitor, cams_complete)
    journal.event("icon_expected_crash_before_latest_cas", fault=icon_fault, latest=observed)
    wait()

    icon_retry = backend.icon_retry()
    observed = _gate(backend, monitor, final)
    journal.event("icon_retry_completed", publication=_publication_summary(icon_retry), latest=observed)
    if final_observation_seconds:
        time.sleep(final_observation_seconds)
    observed = _gate(backend, monitor, final)
    journal.event("final_observation_completed", latest=observed, monitor=monitor.summary())
    return {
        "latest": observed,
        "monitor": monitor.summary(),
        "cams_lifecycle": backend.cams_state_summary(),
    }


def _bounded_seconds(value: str) -> float:
    try:
        number = float(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("duration must be numeric") from error
    if not 0 <= number <= 60:
        raise argparse.ArgumentTypeError("duration must be between 0 and 60 seconds")
    return number


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--icon-first-payload", type=Path, required=True)
    parser.add_argument("--icon-first-report", type=Path, required=True)
    parser.add_argument("--icon-second-payload", type=Path, required=True)
    parser.add_argument("--icon-second-report", type=Path, required=True)
    parser.add_argument("--cams-first-payload", type=Path, required=True)
    parser.add_argument("--cams-first-report", type=Path, required=True)
    parser.add_argument("--cams-second-payload", type=Path, required=True)
    parser.add_argument("--cams-second-report", type=Path, required=True)
    parser.add_argument("--cams-second-evidence-directory", type=Path, required=True)
    parser.add_argument("--work-directory", type=Path, required=True)
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--virtual-now", help="canonical UTC time used by the CAMS lifecycle")
    parser.add_argument("--step-delay-seconds", type=_bounded_seconds, default=20.0)
    parser.add_argument("--final-observation-seconds", type=_bounded_seconds, default=20.0)
    parser.add_argument("--allowed-origin", action="append", default=[])
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = build_parser().parse_args(argv)
    if isinstance(arguments.port, bool) or not 0 <= arguments.port <= 65535:
        raise SystemExit("--port must be between 0 and 65535")
    sources = SourceInputs(
        icon_first_payload=arguments.icon_first_payload,
        icon_first_report=arguments.icon_first_report,
        icon_second_payload=arguments.icon_second_payload,
        icon_second_report=arguments.icon_second_report,
        cams_first_payload=arguments.cams_first_payload,
        cams_first_report=arguments.cams_first_report,
        cams_second_payload=arguments.cams_second_payload,
        cams_second_report=arguments.cams_second_report,
        cams_second_evidence_directory=arguments.cams_second_evidence_directory,
    )
    staged, records = stage_inputs(sources, arguments.work_directory)
    root = Path(arguments.work_directory).expanduser().resolve()
    journal = RunJournal(root, records)
    backend: OfflineScheduleBackend | None = None
    monitor: ContinuityMonitor | None = None
    try:
        with LoopbackOnlyNetworkGuard():
            backend = OfflineScheduleBackend(root, staged, arguments.virtual_now)
            prepared = backend.prepare()
            baseline_results = backend.publish_baseline()
            journal.report.update(
                {
                    "status": "baseline_ready",
                    "virtual_now": _utc(prepared.virtual_now),
                    "object_database": str(backend.object_db),
                    "state_database": str(backend.state_db),
                }
            )
            journal.event(
                "inputs_verified_and_baseline_published",
                virtual_now=_utc(prepared.virtual_now),
                publications={
                    "icon": _publication_summary(baseline_results["icon"]),
                    "core_stage": _stage_summary(baseline_results["core_stage"]),
                    "pollen_stage": _stage_summary(baseline_results["pollen_stage"]),
                    "family": _family_publication_summary(baseline_results["family"]),
                },
            )
            origins = tuple(arguments.allowed_origin) or tuple(DEFAULT_ALLOWED_ORIGINS)
            with LoopbackDataPlane(backend.objects, arguments.port, origins) as plane:
                monitor = ContinuityMonitor(plane.port, backend.publisher)
                monitor.start()
                journal.report["loopback_url"] = plane.url
                journal.event("loopback_data_plane_ready", url=plane.url)
                outcome = run_sequence(
                    backend,
                    journal,
                    monitor,
                    step_delay_seconds=arguments.step_delay_seconds,
                    final_observation_seconds=arguments.final_observation_seconds,
                )
                monitor.close()
                monitor = None
            verify_sources_unchanged(records)
            journal.finish(
                "passed",
                outcome=outcome,
                original_inputs_unchanged=True,
                external_network_used=False,
                credential_files_read=False,
                recovery=(
                    "The test databases and copied artifacts remain in the work directory. "
                    "Stopping this process leaves ordinary pilot databases and artifacts untouched."
                ),
                limitations=(
                    "This compresses scheduler/fault/idempotency behavior only; it does not test "
                    "provider publication latency, Cloud Scheduler, R2, or real Internet failures."
                ),
            )
            print(str(journal.report_path), flush=True)
            return 0
    except KeyboardInterrupt:
        journal.finish("interrupted", original_inputs_unchanged=False)
        return 130
    except Exception as error:
        unchanged = False
        try:
            verify_sources_unchanged(records)
            unchanged = True
        except Exception:
            pass
        journal.finish(
            "failed",
            error={"type": type(error).__name__, "message": str(error)[:500]},
            original_inputs_unchanged=unchanged,
            external_network_used=False,
            recovery="Inspect the retained work directory; no ordinary pilot artifact was changed.",
        )
        raise
    finally:
        if monitor is not None:
            monitor.close()
        if backend is not None:
            backend.close()


if __name__ == "__main__":
    raise SystemExit(main())
