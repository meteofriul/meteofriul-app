"""Durable, offline CAMS evidence-to-publication lifecycle.

The acquisition tools intentionally keep ADS submission and download recovery
separate from publication.  This module closes the local hand-off: it binds the
immutable request plan, submission intent, ADS job, completed GRIB, decoded
215x28x97 archive, authoritative catalog and both contract-v1 publications to
one fenced SQLite run record.

No function in this module opens a network connection or reads credentials.
Re-running the same inputs after a crash is idempotent.  A changed byte, run,
request, catalog, manifest or latest pointer fails closed instead of advancing
the durable state.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import gzip
import hashlib
import json
import math
from pathlib import Path
import re
from types import MappingProxyType
from typing import Any, Callable, Mapping
from urllib.parse import urlsplit
from uuid import UUID

from cams_request_plan import (
    DATASET,
    DEFAULT_AREA,
    EXPECTED_VARIABLE_IDS,
    PublicMetadataError,
    load_verified_request_plan,
    request_sha256,
    strict_json_loads,
)

from .contract_publisher import (
    CamsFamilyPublicationResult,
    ContractStageResult,
    ContractV1Publisher,
    StaleContractRun,
)
from .contract_v1 import (
    CATALOG_VERSION,
    CAMS_POLLEN_PROVIDER,
    CAMS_PROVIDER,
    Catalog,
    ContractError,
    canonical_json_bytes,
    canonical_run_id,
    validate_run_manifest,
)
from .contracts import CamsState, Provider, RunKey, RunRecord, RunState
from .snapshot_materializer import (
    MAX_CAMS_JSON_BYTES,
    SnapshotMaterializationError,
    materialize_cams_core_documents,
)
from .sqlite_state import SqliteStateStore


MAX_RECORD_BYTES = 1024 * 1024
MAX_REPORT_BYTES = 4 * 1024 * 1024
MAX_DOWNLOAD_BYTES = 64 * 1024 * 1024
EXPECTED_MUNICIPALITIES = 215
EXPECTED_VARIABLES = 28
EXPECTED_HOURS = 97
CAMS_LEASE_DURATION = timedelta(minutes=15)
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_RUN_ID = re.compile(r"\d{8}T\d{6}Z\Z")
_STATE_ORDER = {
    RunState.INTENT: 0,
    RunState.SUBMITTED: 1,
    RunState.READY: 2,
    RunState.DOWNLOADED: 3,
    RunState.VALIDATED: 4,
    RunState.PUBLISHED: 5,
}


class CamsLifecycleError(RuntimeError):
    """The local lifecycle cannot advance safely."""


class CamsEvidenceError(CamsLifecycleError):
    """An acquisition, decode or publication proof is missing or inconsistent."""


class CamsLeaseUnavailable(CamsLifecycleError):
    """Another still-leased worker owns this exact CAMS run."""

    def __init__(self, retry_after_seconds: int) -> None:
        if (
            isinstance(retry_after_seconds, bool)
            or not isinstance(retry_after_seconds, int)
            or not 1 <= retry_after_seconds <= 24 * 60 * 60
        ):
            raise ValueError("CAMS lease retry delay must be between one second and one day")
        super().__init__("Exact CAMS run is leased by another worker")
        self.retry_after_seconds = retry_after_seconds


@dataclass(frozen=True)
class CamsLifecyclePaths:
    artifacts_directory: Path
    decoded_payload: Path
    decode_report: Path

    def normalized(self) -> "CamsLifecyclePaths":
        raw_directory = Path(self.artifacts_directory).expanduser()
        raw_payload = Path(self.decoded_payload).expanduser()
        raw_report = Path(self.decode_report).expanduser()
        for path, label in (
            (raw_directory, "CAMS artifact directory"),
            (raw_payload, "Decoded CAMS payload"),
            (raw_report, "CAMS decode report"),
        ):
            if path.is_symlink() or path.is_junction():
                raise CamsEvidenceError(
                    f"{label} cannot be a symbolic link or junction"
                )
        directory = raw_directory.resolve()
        payload = raw_payload.resolve()
        report = raw_report.resolve()
        if not directory.is_dir():
            raise CamsEvidenceError("CAMS artifact directory is missing")
        if payload == report:
            raise CamsEvidenceError("Decoded payload and report must be distinct files")
        try:
            payload.relative_to(directory)
            report.relative_to(directory)
        except ValueError:
            raise CamsEvidenceError(
                "Decoded CAMS payload and report must remain inside the acquisition directory"
            ) from None
        return CamsLifecyclePaths(directory, payload, report)


@dataclass(frozen=True)
class CamsLifecycleResult:
    key: RunKey
    record: RunRecord
    core_stage: ContractStageResult
    pollen_stage: ContractStageResult
    family_publication: CamsFamilyPublicationResult
    validation_sha256: str
    publication_sha256: str


@dataclass(frozen=True)
class _AcquisitionEvidence:
    key: RunKey
    run_date: str
    request_plan_sha256: str
    request_record_sha256: str
    intent_sha256: str
    job_sha256: str
    request_id: str
    ready_evidence_sha256: str
    download_record_sha256: str
    artifact_sha256: str
    artifact_bytes: int
    catalog_sha256: str
    plan: Mapping[str, Any]

    def submitted_checkpoint(self) -> dict[str, Any]:
        return {
            "run_date": self.run_date,
            "request_plan_sha256": self.request_plan_sha256,
            "request_record_sha256": self.request_record_sha256,
            "intent_sha256": self.intent_sha256,
            "job_sha256": self.job_sha256,
            "request_id": self.request_id,
            "catalog_sha256": self.catalog_sha256,
        }

    def ready_checkpoint(self) -> dict[str, Any]:
        return {"ready_evidence_sha256": self.ready_evidence_sha256}

    def downloaded_checkpoint(self) -> dict[str, Any]:
        return {
            "download_record_sha256": self.download_record_sha256,
            "artifact_sha256": self.artifact_sha256,
            "artifact_bytes": self.artifact_bytes,
        }


@dataclass(frozen=True)
class _ValidatedEvidence:
    bundle: Mapping[str, Any]
    checkpoint: Mapping[str, Any]
    validation_sha256: str
    core_manifest_sha256: str
    pollen_manifest_sha256: str


@dataclass(frozen=True)
class PreparedCamsRun:
    """Immutable verified CAMS data passed from preparation to storage commit."""

    key: RunKey
    catalog_sha256: str
    submitted_checkpoint: Mapping[str, Any]
    ready_checkpoint: Mapping[str, Any]
    downloaded_checkpoint: Mapping[str, Any]
    validated_checkpoint: Mapping[str, Any]
    validation_sha256: str
    core_documents: Mapping[str, bytes]
    core_manifest_bytes: bytes
    core_manifest_sha256: str
    pollen_documents: Mapping[str, bytes]
    pollen_manifest_bytes: bytes
    pollen_manifest_sha256: str

    def __post_init__(self) -> None:
        if not isinstance(self.key, RunKey) or self.key.provider is not Provider.CAMS:
            raise CamsEvidenceError("Prepared CAMS run key is invalid")
        for label, digest in (
            ("catalog", self.catalog_sha256),
            ("validation", self.validation_sha256),
            ("core manifest", self.core_manifest_sha256),
            ("pollen manifest", self.pollen_manifest_sha256),
        ):
            if not isinstance(digest, str) or not _SHA256.fullmatch(digest):
                raise CamsEvidenceError(f"Prepared CAMS {label} hash is invalid")
        for label, documents in (
            ("core", self.core_documents),
            ("pollen", self.pollen_documents),
        ):
            if not isinstance(documents, Mapping) or any(
                not isinstance(code, str) or not isinstance(body, bytes)
                for code, body in documents.items()
            ):
                raise CamsEvidenceError(f"Prepared CAMS {label} documents are invalid")
        for label, body, expected_hash, expected_provider in (
            (
                "core",
                self.core_manifest_bytes,
                self.core_manifest_sha256,
                CAMS_PROVIDER,
            ),
            (
                "pollen",
                self.pollen_manifest_bytes,
                self.pollen_manifest_sha256,
                CAMS_POLLEN_PROVIDER,
            ),
        ):
            if (
                not isinstance(body, bytes)
                or not body
                or _sha256(body) != expected_hash
            ):
                raise CamsEvidenceError(f"Prepared CAMS {label} manifest is invalid")
            try:
                manifest = strict_json_loads(body)
            except PublicMetadataError:
                raise CamsEvidenceError(
                    f"Prepared CAMS {label} manifest is not strict JSON"
                ) from None
            if (
                not isinstance(manifest, Mapping)
                or canonical_json_bytes(manifest) != body
                or manifest.get("source_run_id") != self.key.source_run_id
                or manifest.get("provider") != expected_provider
            ):
                raise CamsEvidenceError(
                    f"Prepared CAMS {label} manifest identity is inconsistent"
                )

        for field in (
            "submitted_checkpoint",
            "ready_checkpoint",
            "downloaded_checkpoint",
            "validated_checkpoint",
        ):
            checkpoint = getattr(self, field)
            if not isinstance(checkpoint, Mapping):
                raise CamsEvidenceError("Prepared CAMS checkpoint is invalid")
            object.__setattr__(self, field, MappingProxyType(dict(checkpoint)))

        submitted = self.submitted_checkpoint
        downloaded = self.downloaded_checkpoint
        validated = self.validated_checkpoint
        request_plan_sha256 = _exact_sha256(
            submitted.get("request_plan_sha256"),
            "Prepared CAMS request plan hash",
        )
        artifact_sha256 = _exact_sha256(
            downloaded.get("artifact_sha256"),
            "Prepared CAMS artifact hash",
        )
        payload_sha256 = _exact_sha256(
            validated.get("payload_sha256"),
            "Prepared CAMS payload hash",
        )
        decode_report_sha256 = _exact_sha256(
            validated.get("decode_report_sha256"),
            "Prepared CAMS decode report hash",
        )
        if (
            submitted.get("catalog_sha256") != self.catalog_sha256
            or validated.get("municipality_count") != EXPECTED_MUNICIPALITIES
            or validated.get("variable_count") != EXPECTED_VARIABLES
            or validated.get("hourly_instants") != EXPECTED_HOURS
            or validated.get("validation_sha256") != self.validation_sha256
        ):
            raise CamsEvidenceError("Prepared CAMS checkpoints are inconsistent")
        validation_document = {
            "schema_version": 1,
            "kind": "cams_local_validation_attestation",
            "source_run_id": self.key.source_run_id,
            "request_sha256": self.key.request_hash,
            "request_plan_sha256": request_plan_sha256,
            "catalog_sha256": self.catalog_sha256,
            "artifact_sha256": artifact_sha256,
            "payload_sha256": payload_sha256,
            "decode_report_sha256": decode_report_sha256,
            "municipality_count": EXPECTED_MUNICIPALITIES,
            "variable_count": EXPECTED_VARIABLES,
            "hourly_instants": EXPECTED_HOURS,
            "core_manifest_sha256": self.core_manifest_sha256,
            "pollen_manifest_sha256": self.pollen_manifest_sha256,
        }
        if _sha256(canonical_json_bytes(validation_document)) != self.validation_sha256:
            raise CamsEvidenceError(
                "Prepared CAMS validation hash does not bind the publication"
            )
        object.__setattr__(
            self,
            "core_documents",
            MappingProxyType(dict(self.core_documents)),
        )
        object.__setattr__(
            self,
            "pollen_documents",
            MappingProxyType(dict(self.pollen_documents)),
        )

    @property
    def source_run_id(self) -> str:
        return self.key.source_run_id

    @property
    def input_fingerprint_sha256(self) -> str:
        return self.validation_sha256

    @staticmethod
    def _manifest(body: bytes, label: str) -> Mapping[str, Any]:
        try:
            value = strict_json_loads(body)
        except PublicMetadataError:
            raise CamsEvidenceError(f"Prepared CAMS {label} manifest is corrupt") from None
        if not isinstance(value, Mapping):
            raise CamsEvidenceError(f"Prepared CAMS {label} manifest is corrupt")
        return value

    def core_manifest(self) -> Mapping[str, Any]:
        return self._manifest(self.core_manifest_bytes, "core")

    def pollen_manifest(self) -> Mapping[str, Any]:
        return self._manifest(self.pollen_manifest_bytes, "pollen")


def _sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _read_bytes(path: Path, maximum: int, label: str) -> bytes:
    if path.is_symlink() or path.is_junction():
        raise CamsEvidenceError(f"{label} cannot be a symbolic link or junction")
    if not path.is_file():
        raise CamsEvidenceError(f"{label} is missing")
    size = path.stat().st_size
    if not 1 <= size <= maximum:
        raise CamsEvidenceError(f"{label} has an invalid byte size")
    raw = path.read_bytes()
    if len(raw) != size:
        raise CamsEvidenceError(f"{label} changed while it was read")
    return raw


def _read_json(path: Path, maximum: int, label: str) -> tuple[dict[str, Any], bytes]:
    raw = _read_bytes(path, maximum, label)
    try:
        value = strict_json_loads(raw)
    except PublicMetadataError:
        raise CamsEvidenceError(f"{label} is not strict UTF-8 JSON") from None
    if not isinstance(value, dict):
        raise CamsEvidenceError(f"{label} must be a JSON object")
    return value, raw


def _exact_sha256(value: Any, label: str) -> str:
    if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
        raise CamsEvidenceError(f"{label} is not a lowercase SHA-256")
    return value


def _canonical_publication_time(value: str) -> str:
    if not isinstance(value, str):
        raise CamsEvidenceError("Publication time must be canonical UTC seconds")
    try:
        parsed = datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=timezone.utc
        )
    except ValueError:
        raise CamsEvidenceError("Publication time must be canonical UTC seconds") from None
    if parsed.strftime("%Y-%m-%dT%H:%M:%SZ") != value:
        raise CamsEvidenceError("Publication time must be canonical UTC seconds")
    return value


def _timestamp_with_timezone(value: Any, label: str) -> None:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (AttributeError, ValueError):
        raise CamsEvidenceError(f"{label} timestamp is invalid") from None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise CamsEvidenceError(f"{label} timestamp must carry a timezone")


def _validate_scope_metadata(value: Any, catalog: Catalog) -> None:
    if not isinstance(value, Mapping) or set(value) != {
        "municipalities",
        "municipality_count",
        "catalog_sha256",
        "coordinate_provenance",
    }:
        raise CamsEvidenceError("Saved request has invalid FVG scope metadata")
    if (
        value.get("municipality_count") != EXPECTED_MUNICIPALITIES
        or value.get("catalog_sha256") != catalog.sha256
    ):
        raise CamsEvidenceError("Saved request does not identify the authoritative catalog")
    points = value.get("municipalities")
    if not isinstance(points, list) or len(points) != EXPECTED_MUNICIPALITIES:
        raise CamsEvidenceError("Saved request does not cover all 215 municipalities")
    catalog_by_slug = {municipality.slug: municipality for municipality in catalog.municipalities}
    observed: dict[str, Mapping[str, Any]] = {}
    for point in points:
        if not isinstance(point, Mapping) or not isinstance(point.get("slug"), str):
            raise CamsEvidenceError("Saved request contains an invalid municipality point")
        slug = point["slug"]
        if slug in observed:
            raise CamsEvidenceError("Saved request contains a duplicate municipality point")
        observed[slug] = point
    if set(observed) != set(catalog_by_slug):
        raise CamsEvidenceError("Saved request and authoritative municipality catalog differ")
    for slug, municipality in catalog_by_slug.items():
        point = observed[slug]
        expected = {
            "name": municipality.name,
            "province": municipality.province,
            "istatCode": municipality.istat_code,
            "latitude": municipality.latitude,
            "longitude": municipality.longitude,
        }
        if any(point.get(field) != wanted for field, wanted in expected.items()):
            raise CamsEvidenceError(
                "Saved request municipality identity or representative point changed"
            )


def _validate_result_host(value: Any) -> str:
    if not isinstance(value, str):
        raise CamsEvidenceError("Completed CAMS download host is invalid")
    try:
        parsed = urlsplit(f"https://{value}/")
        port = parsed.port
    except ValueError:
        raise CamsEvidenceError("Completed CAMS download host is invalid") from None
    if (
        parsed.hostname != value
        or port not in (None, 443)
        or not (value.endswith(".ecmwf.int") or value == "ads.atmosphere.copernicus.eu")
    ):
        raise CamsEvidenceError("Completed CAMS download host is not approved")
    return value


def _verify_acquisition(paths: CamsLifecyclePaths, catalog: Catalog) -> _AcquisitionEvidence:
    directory = paths.artifacts_directory
    try:
        plan, plan_raw, plan_hash = load_verified_request_plan(
            directory / "request-plan.json"
        )
    except PublicMetadataError as error:
        raise CamsEvidenceError(str(error)) from None
    request = plan["request_groups"][0]["request"]
    request_hash = request_sha256(request)
    if (
        request.get("data_format") != "grib"
        or request.get("area") != list(map(float, DEFAULT_AREA))
    ):
        raise CamsEvidenceError(
            "CAMS lifecycle requires the verified full-FVG GRIB request"
        )
    run_date = plan["run_date"]
    run_id = canonical_run_id(f"{run_date}T00:00:00Z")

    saved_request, saved_request_raw = _read_json(
        directory / "request.json", MAX_RECORD_BYTES, "Saved CAMS request"
    )
    if set(saved_request) != {
        "schema_version",
        "dataset",
        "scope",
        "run_date",
        "request_plan_sha256",
        "request_sha256",
        "request",
        "variables",
        "scope_metadata",
        "licence",
    }:
        raise CamsEvidenceError("Saved CAMS request schema changed")
    if (
        saved_request.get("schema_version") != 2
        or saved_request.get("dataset") != DATASET
        or saved_request.get("scope") != "fvg"
        or saved_request.get("run_date") != run_date
        or saved_request.get("request_plan_sha256") != plan_hash
        or saved_request.get("request_sha256") != request_hash
        or saved_request.get("request") != request
        or saved_request.get("variables") != plan["variables"]
        or saved_request.get("licence") != plan["licence"]
    ):
        raise CamsEvidenceError("Saved CAMS request does not match its immutable plan")
    _validate_scope_metadata(saved_request["scope_metadata"], catalog)

    intent, intent_raw = _read_json(
        directory / "submission-intent.json", 16 * 1024, "CAMS submission intent"
    )
    if set(intent) != {
        "schema_version",
        "at_utc",
        "dataset",
        "scope",
        "run_date",
        "request_plan_sha256",
        "request_sha256",
        "post_retries",
    } or any(
        (
            intent.get("schema_version") != 2,
            intent.get("dataset") != DATASET,
            intent.get("scope") != "fvg",
            intent.get("run_date") != run_date,
            intent.get("request_plan_sha256") != plan_hash,
            intent.get("request_sha256") != request_hash,
            intent.get("post_retries") != 0,
        )
    ):
        raise CamsEvidenceError("CAMS submission intent does not match its immutable plan")
    _timestamp_with_timezone(intent.get("at_utc"), "CAMS submission intent")

    job, job_raw = _read_json(directory / "job.json", 16 * 1024, "Saved CAMS job")
    if set(job) != {
        "schema_version",
        "dataset",
        "request_id",
        "scope",
        "run_date",
        "request_plan_sha256",
        "request_sha256",
    } or any(
        (
            job.get("schema_version") != 2,
            job.get("dataset") != DATASET,
            job.get("scope") != "fvg",
            job.get("run_date") != run_date,
            job.get("request_plan_sha256") != plan_hash,
            job.get("request_sha256") != request_hash,
        )
    ):
        raise CamsEvidenceError("Saved CAMS job does not match its immutable plan")
    try:
        if str(UUID(job["request_id"])) != job["request_id"]:
            raise ValueError
    except (KeyError, TypeError, ValueError):
        raise CamsEvidenceError("Saved CAMS job identifier is invalid") from None

    complete, complete_raw = _read_json(
        directory / "source.grib.complete.json",
        16 * 1024,
        "Completed CAMS download record",
    )
    if set(complete) != {
        "schema_version",
        "kind",
        "target_name",
        "expected_bytes",
        "content_type",
        "result_host",
        "dataset",
        "request_id",
        "run_date",
        "request_plan_sha256",
        "request_sha256",
        "sha256",
    } or any(
        (
            complete.get("schema_version") != 1,
            complete.get("kind") != "cams_result_completed_download",
            complete.get("target_name") != "source.grib",
            complete.get("dataset") != DATASET,
            complete.get("request_id") != job["request_id"],
            complete.get("run_date") != run_date,
            complete.get("request_plan_sha256") != plan_hash,
            complete.get("request_sha256") != request_hash,
        )
    ):
        raise CamsEvidenceError("Completed CAMS download record does not match its job")
    expected_bytes = complete.get("expected_bytes")
    if type(expected_bytes) is not int or not 0 < expected_bytes <= MAX_DOWNLOAD_BYTES:
        raise CamsEvidenceError("Completed CAMS download size is invalid")
    if complete.get("content_type") not in {
        "application/x-grib",
        "application/grib",
        "application/octet-stream",
    }:
        raise CamsEvidenceError("Completed CAMS download content type is invalid")
    _validate_result_host(complete.get("result_host"))
    source_hash = _exact_sha256(complete.get("sha256"), "Completed CAMS download hash")
    if (directory / "source.grib.part").exists() or (
        directory / "source.grib.part.json"
    ).exists():
        raise CamsEvidenceError(
            "CAMS download recovery is unfinished; resume the exact saved job first"
        )
    source_raw = _read_bytes(directory / "source.grib", MAX_DOWNLOAD_BYTES, "CAMS GRIB")
    if len(source_raw) != expected_bytes or _sha256(source_raw) != source_hash:
        raise CamsEvidenceError("CAMS GRIB differs from its completed download record")

    job_hash = _sha256(job_raw)
    complete_hash = _sha256(complete_raw)
    ready_hash = _sha256(
        canonical_json_bytes(
            {
                "request_id": job["request_id"],
                "job_sha256": job_hash,
                "download_record_sha256": complete_hash,
            }
        )
    )
    return _AcquisitionEvidence(
        key=RunKey(Provider.CAMS, run_id, request_hash),
        run_date=run_date,
        request_plan_sha256=_sha256(plan_raw),
        request_record_sha256=_sha256(saved_request_raw),
        intent_sha256=_sha256(intent_raw),
        job_sha256=job_hash,
        request_id=job["request_id"],
        ready_evidence_sha256=ready_hash,
        download_record_sha256=complete_hash,
        artifact_sha256=source_hash,
        artifact_bytes=expected_bytes,
        catalog_sha256=catalog.sha256,
        plan=plan,
    )


def _verify_decoded(
    paths: CamsLifecyclePaths,
    catalog: Catalog,
    acquisition: _AcquisitionEvidence,
) -> _ValidatedEvidence:
    report, report_raw = _read_json(
        paths.decode_report, MAX_REPORT_BYTES, "CAMS decode report"
    )
    payload_raw = _read_bytes(
        paths.decoded_payload, MAX_CAMS_JSON_BYTES, "Decoded CAMS payload"
    )
    try:
        payload = strict_json_loads(payload_raw)
    except PublicMetadataError:
        raise CamsEvidenceError("Decoded CAMS payload is not strict UTF-8 JSON") from None
    if not isinstance(payload, dict):
        raise CamsEvidenceError("Decoded CAMS payload must be a JSON object")
    payload_hash = _sha256(payload_raw)
    source_record = {
        "filename": "source.grib",
        "bytes": acquisition.artifact_bytes,
        "sha256": acquisition.artifact_sha256,
    }
    if (
        report.get("schema_version") != 1
        or report.get("status") != "offline_regional_decode_measurement_not_acquisition"
        or report.get("run_date") != acquisition.run_date
        or report.get("request_plan_sha256") != acquisition.request_plan_sha256
        or report.get("request_sha256") != acquisition.key.request_hash
        or report.get("catalog_sha256") != catalog.sha256
        or report.get("input") != source_record
        or report.get("payload_bytes") != len(payload_raw)
        or report.get("payload_sha256") != payload_hash
    ):
        raise CamsEvidenceError("CAMS decode report does not bind the selected evidence")
    compressed = gzip.compress(payload_raw, mtime=0)
    if (
        report.get("payload_gzip_bytes") != len(compressed)
        or report.get("payload_gzip_sha256") != _sha256(compressed)
    ):
        raise CamsEvidenceError("CAMS decode report gzip evidence is inconsistent")
    if (
        payload.get("dataset") != DATASET
        or payload.get("run_utc") != f"{acquisition.run_date}T00:00:00Z"
        or payload.get("request_plan_sha256") != acquisition.request_plan_sha256
        or payload.get("request_sha256") != acquisition.key.request_hash
        or payload.get("catalog_sha256") != catalog.sha256
    ):
        raise CamsEvidenceError("Decoded CAMS payload has a different plan, run or catalog")
    if payload.get("sources", {}).get("grib") != source_record:
        raise CamsEvidenceError("Decoded CAMS payload does not identify the completed GRIB")
    expected_plan_source = {
        "sha256": acquisition.request_plan_sha256,
        "run_date": acquisition.run_date,
        "request_sha256": acquisition.key.request_hash,
        "metadata_documents": acquisition.plan["metadata_evidence"]["documents"],
    }
    if payload.get("sources", {}).get("request_plan") != expected_plan_source:
        raise CamsEvidenceError("Decoded CAMS payload plan provenance is incomplete")
    variable_ids = [
        row.get("id") for row in payload.get("variables", []) if isinstance(row, Mapping)
    ]
    if (
        len(variable_ids) != EXPECTED_VARIABLES
        or set(variable_ids) != set(EXPECTED_VARIABLE_IDS)
    ):
        raise CamsEvidenceError("Decoded CAMS payload is not the approved 28-variable set")

    try:
        (
            documents,
            manifest,
            pollen_documents,
            pollen_manifest,
            archive_summary,
        ) = materialize_cams_core_documents(payload, catalog)
    except (KeyError, TypeError, ValueError, SnapshotMaterializationError) as error:
        raise CamsEvidenceError(f"Decoded CAMS archive validation failed: {error}") from None
    if archive_summary != {
        **archive_summary,
        "municipality_count": EXPECTED_MUNICIPALITIES,
        "variable_count": EXPECTED_VARIABLES,
        "hourly_instants": EXPECTED_HOURS,
        "catalog_sha256": catalog.sha256,
    }:
        raise CamsEvidenceError("Decoded CAMS archive is not the complete 215x28x97 matrix")
    analysis = report.get("analysis")
    if not isinstance(analysis, Mapping) or any(
        analysis.get(field) != value
        for field, value in {
            "municipalities": EXPECTED_MUNICIPALITIES,
            "variables": EXPECTED_VARIABLES,
            "hourly_instants": EXPECTED_HOURS,
        }.items()
    ):
        raise CamsEvidenceError("CAMS decode analysis does not confirm 215x28x97 coverage")

    core_manifest_hash = _sha256(canonical_json_bytes(manifest))
    pollen_manifest_hash = _sha256(canonical_json_bytes(pollen_manifest))
    validation_document = {
        "schema_version": 1,
        "kind": "cams_local_validation_attestation",
        "source_run_id": acquisition.key.source_run_id,
        "request_sha256": acquisition.key.request_hash,
        "request_plan_sha256": acquisition.request_plan_sha256,
        "catalog_sha256": catalog.sha256,
        "artifact_sha256": acquisition.artifact_sha256,
        "payload_sha256": payload_hash,
        "decode_report_sha256": _sha256(report_raw),
        "municipality_count": archive_summary["municipality_count"],
        "variable_count": archive_summary["variable_count"],
        "hourly_instants": archive_summary["hourly_instants"],
        "core_manifest_sha256": core_manifest_hash,
        "pollen_manifest_sha256": pollen_manifest_hash,
    }
    validation_hash = _sha256(canonical_json_bytes(validation_document))
    return _ValidatedEvidence(
        bundle={
            "cams": {"documents": documents, "manifest": manifest},
            "cams_pollen": {
                "documents": pollen_documents,
                "manifest": pollen_manifest,
            },
        },
        checkpoint={
            "payload_sha256": payload_hash,
            "payload_bytes": len(payload_raw),
            "decode_report_sha256": _sha256(report_raw),
            "municipality_count": EXPECTED_MUNICIPALITIES,
            "variable_count": EXPECTED_VARIABLES,
            "hourly_instants": EXPECTED_HOURS,
            "validation_sha256": validation_hash,
        },
        validation_sha256=validation_hash,
        core_manifest_sha256=core_manifest_hash,
        pollen_manifest_sha256=pollen_manifest_hash,
    )


def prepare_cams_lifecycle(
    *,
    paths: CamsLifecyclePaths,
    catalog: Catalog,
) -> PreparedCamsRun:
    """Verify and materialize one CAMS run without opening writable stores.

    The returned object contains the exact immutable bytes later committed by
    :func:`commit_prepared_cams_lifecycle`; the commit phase never reopens the
    GRIB, decoded JSON, reports or acquisition records.
    """

    if (
        not isinstance(catalog, Catalog)
        or catalog.version != CATALOG_VERSION
        or catalog.municipality_count != EXPECTED_MUNICIPALITIES
    ):
        raise CamsEvidenceError("Lifecycle requires the authoritative 215-town catalog")
    selected = paths.normalized()
    acquisition = _verify_acquisition(selected, catalog)
    validated = _verify_decoded(selected, catalog, acquisition)
    core = validated.bundle.get("cams")
    pollen = validated.bundle.get("cams_pollen")
    if not isinstance(core, Mapping) or not isinstance(pollen, Mapping):
        raise CamsEvidenceError("Prepared CAMS bundle is incomplete")
    core_documents = core.get("documents")
    pollen_documents = pollen.get("documents")
    core_manifest = core.get("manifest")
    pollen_manifest = pollen.get("manifest")
    if any(
        not isinstance(value, Mapping)
        for value in (
            core_documents,
            pollen_documents,
            core_manifest,
            pollen_manifest,
        )
    ):
        raise CamsEvidenceError("Prepared CAMS bundle has invalid components")
    core_manifest_bytes = canonical_json_bytes(core_manifest)
    pollen_manifest_bytes = canonical_json_bytes(pollen_manifest)
    if (
        _sha256(core_manifest_bytes) != validated.core_manifest_sha256
        or _sha256(pollen_manifest_bytes) != validated.pollen_manifest_sha256
    ):
        raise CamsEvidenceError("Prepared CAMS manifest hashes changed")
    return PreparedCamsRun(
        key=acquisition.key,
        catalog_sha256=catalog.sha256,
        submitted_checkpoint=acquisition.submitted_checkpoint(),
        ready_checkpoint=acquisition.ready_checkpoint(),
        downloaded_checkpoint=acquisition.downloaded_checkpoint(),
        validated_checkpoint=validated.checkpoint,
        validation_sha256=validated.validation_sha256,
        core_documents=core_documents,
        core_manifest_bytes=core_manifest_bytes,
        core_manifest_sha256=validated.core_manifest_sha256,
        pollen_documents=pollen_documents,
        pollen_manifest_bytes=pollen_manifest_bytes,
        pollen_manifest_sha256=validated.pollen_manifest_sha256,
    )


def _ensure_committed_fields(record: RunRecord, expected: Mapping[str, Any]) -> None:
    for field, value in expected.items():
        if record.checkpoint.get(field) != value:
            raise CamsEvidenceError(
                f"Durable CAMS state differs from verified evidence at {field}"
            )


def _advance_state(
    state_store: SqliteStateStore,
    key: RunKey,
    record: RunRecord,
    *,
    owner_id: str,
    target: CamsState,
    checkpoint: Mapping[str, Any],
    now: datetime,
    after_step: Callable[[str], None] | None,
) -> RunRecord:
    target_state = RunState(target.value)
    if _STATE_ORDER[record.state] >= _STATE_ORDER[target_state]:
        _ensure_committed_fields(record, checkpoint)
        return record
    expected = {
        CamsState.SUBMITTED: CamsState.INTENT,
        CamsState.READY: CamsState.SUBMITTED,
        CamsState.DOWNLOADED: CamsState.READY,
        CamsState.VALIDATED: CamsState.DOWNLOADED,
        CamsState.PUBLISHED: CamsState.VALIDATED,
    }[target]
    if record.state is not RunState(expected.value):
        raise CamsEvidenceError("Durable CAMS state is not on the expected monotonic edge")
    result = state_store.transition_cams(
        key,
        owner_id=owner_id,
        fencing_token=record.fencing_token,
        expected_state=expected,
        target_state=target,
        checkpoint=checkpoint,
        now=now,
    )
    if after_step is not None:
        after_step(target.value)
    return result.record


def _commit_prepared_cams_lifecycle(
    *,
    prepared: PreparedCamsRun,
    catalog: Catalog,
    state_store: SqliteStateStore,
    publisher: ContractV1Publisher,
    owner_id: str,
    published_at: str,
    now: datetime | None = None,
    lease_for: timedelta = CAMS_LEASE_DURATION,
    after_step: Callable[[str], None] | None = None,
    lease_observer: Callable[[RunKey, RunRecord], None] | None = None,
) -> CamsLifecycleResult:
    """Commit one already verified CAMS run without reopening source paths.

    ``after_step`` exists solely for deterministic offline crash tests.  If it
    raises, all work completed before that point remains durable and the same
    invocation can be replayed safely.
    """

    if not isinstance(prepared, PreparedCamsRun):
        raise CamsEvidenceError("CAMS commit requires one prepared run")
    if (
        not isinstance(catalog, Catalog)
        or catalog.version != CATALOG_VERSION
        or catalog.municipality_count != 215
        or catalog.sha256 != prepared.catalog_sha256
    ):
        raise CamsEvidenceError("Lifecycle requires the authoritative 215-town catalog")
    core_manifest = prepared.core_manifest()
    pollen_manifest = prepared.pollen_manifest()
    try:
        validate_run_manifest(
            core_manifest,
            catalog,
            expected_provider=CAMS_PROVIDER,
            object_bodies=prepared.core_documents,
        )
        validate_run_manifest(
            pollen_manifest,
            catalog,
            expected_provider=CAMS_POLLEN_PROVIDER,
            object_bodies=prepared.pollen_documents,
        )
    except ContractError as error:
        raise CamsEvidenceError("Prepared CAMS contract data is invalid") from error
    published_at = _canonical_publication_time(published_at)
    fixed_instant = now
    if fixed_instant is not None and (
        not isinstance(fixed_instant, datetime) or fixed_instant.tzinfo is None
    ):
        raise CamsEvidenceError("Lifecycle clock must be timezone-aware")

    def current_time() -> datetime:
        value = datetime.now(timezone.utc) if fixed_instant is None else fixed_instant
        return value.astimezone(timezone.utc)

    claim_time = current_time()
    claim = state_store.claim(
        prepared.key,
        owner_id=owner_id,
        lease_for=lease_for,
        now=claim_time,
    )
    if not claim.acquired:
        remaining = math.ceil(
            (claim.record.lease_expires_at - claim_time).total_seconds()
        )
        raise CamsLeaseUnavailable(max(1, min(24 * 60 * 60, remaining)))
    record = claim.record
    if lease_observer is not None:
        lease_observer(prepared.key, record)
    record = _advance_state(
        state_store,
        prepared.key,
        record,
        owner_id=owner_id,
        target=CamsState.SUBMITTED,
        checkpoint=dict(prepared.submitted_checkpoint),
        now=current_time(),
        after_step=after_step,
    )
    record = _advance_state(
        state_store,
        prepared.key,
        record,
        owner_id=owner_id,
        target=CamsState.READY,
        checkpoint=dict(prepared.ready_checkpoint),
        now=current_time(),
        after_step=after_step,
    )
    record = _advance_state(
        state_store,
        prepared.key,
        record,
        owner_id=owner_id,
        target=CamsState.DOWNLOADED,
        checkpoint=dict(prepared.downloaded_checkpoint),
        now=current_time(),
        after_step=after_step,
    )

    if _STATE_ORDER[record.state] >= _STATE_ORDER[RunState.VALIDATED]:
        stored_publication_intent = record.checkpoint.get("publication_intent_at")
        if stored_publication_intent != published_at:
            raise CamsEvidenceError(
                "Publication time differs from the durable validated lifecycle intent"
            )
    validated_checkpoint = {
        **prepared.validated_checkpoint,
        "publication_intent_at": published_at,
    }
    record = _advance_state(
        state_store,
        prepared.key,
        record,
        owner_id=owner_id,
        target=CamsState.VALIDATED,
        checkpoint=validated_checkpoint,
        now=current_time(),
        after_step=after_step,
    )

    # Staging is create-only and invisible. A stale worker may leave immutable
    # orphan objects, but only the single CAMS-family CAS can expose a run.
    state_store.renew_lease(
        prepared.key,
        owner_id=owner_id,
        fencing_token=record.fencing_token,
        lease_for=lease_for,
        now=current_time(),
    )
    core = publisher.stage_run(
        CAMS_PROVIDER,
        prepared.core_documents,
        core_manifest,
    )
    if after_step is not None:
        after_step("CORE_STAGED")

    state_store.renew_lease(
        prepared.key,
        owner_id=owner_id,
        fencing_token=record.fencing_token,
        lease_for=lease_for,
        now=current_time(),
    )
    pollen = publisher.stage_run(
        CAMS_POLLEN_PROVIDER,
        prepared.pollen_documents,
        pollen_manifest,
    )
    if after_step is not None:
        after_step("POLLEN_STAGED")

    state_store.renew_lease(
        prepared.key,
        owner_id=owner_id,
        fencing_token=record.fencing_token,
        lease_for=lease_for,
        now=current_time(),
    )
    family = publisher.release_cams_family(
        core,
        pollen,
        validation_sha256=prepared.validation_sha256,
        published_at=published_at,
    )
    if family.superseded:
        raise StaleContractRun(
            "CAMS family release was superseded before lifecycle commit"
        )
    if after_step is not None:
        after_step("FAMILY_RELEASED")

    verified_family = publisher.read_verified_cams_family_latest()
    verified_latest = (
        verified_family.get("latest")
        if isinstance(verified_family, Mapping)
        else None
    )
    verified_run_id = (
        verified_latest.get("source_run_id")
        if isinstance(verified_latest, Mapping)
        else None
    )
    if isinstance(verified_run_id, str) and _RUN_ID.fullmatch(verified_run_id):
        if verified_run_id > prepared.source_run_id:
            raise StaleContractRun(
                "CAMS family release was superseded during lifecycle verification"
            )
        if verified_run_id < prepared.source_run_id:
            raise CamsEvidenceError(
                "Verified CAMS family latest regressed after release"
            )
    if (
        not isinstance(verified_latest, Mapping)
        or verified_run_id != prepared.source_run_id
        or verified_latest.get("release_sha256") != family.release_sha256
    ):
        raise CamsEvidenceError(
            "Verified CAMS family latest differs from the released run"
        )
    if publisher.store.head(family.latest_key).etag != family.latest_etag:
        # The family may legitimately advance after the verified read above
        # but before the separate head check. Re-read the complete family once
        # to distinguish that monotonic supersession from corruption, an ABA,
        # or a regression; only the former is a safe scheduler no-op.
        refreshed_family = publisher.read_verified_cams_family_latest()
        refreshed_latest = (
            refreshed_family.get("latest")
            if isinstance(refreshed_family, Mapping)
            else None
        )
        refreshed_run_id = (
            refreshed_latest.get("source_run_id")
            if isinstance(refreshed_latest, Mapping)
            else None
        )
        if isinstance(refreshed_run_id, str) and _RUN_ID.fullmatch(
            refreshed_run_id
        ):
            if refreshed_run_id > prepared.source_run_id:
                raise StaleContractRun(
                    "CAMS family release was superseded after lifecycle verification"
                )
            if refreshed_run_id < prepared.source_run_id:
                raise CamsEvidenceError(
                    "Verified CAMS family latest regressed after lifecycle verification"
                )
        raise CamsEvidenceError(
            "Verified CAMS family latest changed without a monotonic supersession"
        )
    publication_document = {
        "schema_version": 1,
        "kind": "cams_local_publication_attestation",
        "source_run_id": prepared.source_run_id,
        "validation_sha256": prepared.validation_sha256,
        "publication_intent_at": published_at,
        "core_manifest_sha256": prepared.core_manifest_sha256,
        "pollen_manifest_sha256": prepared.pollen_manifest_sha256,
        "family_release_sha256": family.release_sha256,
        "family_latest_etag": family.latest_etag,
        "family_revision": family.revision,
        "core_object_count": len(core.payload_keys),
        "pollen_object_count": len(pollen.payload_keys),
    }
    publication_hash = _sha256(canonical_json_bytes(publication_document))
    published_checkpoint = {
        "core_manifest_sha256": prepared.core_manifest_sha256,
        "pollen_manifest_sha256": prepared.pollen_manifest_sha256,
        "family_release_sha256": family.release_sha256,
        "family_latest_etag": family.latest_etag,
        "family_revision": family.revision,
        "core_object_count": len(core.payload_keys),
        "pollen_object_count": len(pollen.payload_keys),
        "publication_sha256": publication_hash,
    }
    record = _advance_state(
        state_store,
        prepared.key,
        record,
        owner_id=owner_id,
        target=CamsState.PUBLISHED,
        checkpoint=published_checkpoint,
        now=current_time(),
        after_step=after_step,
    )
    return CamsLifecycleResult(
        key=prepared.key,
        record=record,
        core_stage=core,
        pollen_stage=pollen,
        family_publication=family,
        validation_sha256=prepared.validation_sha256,
        publication_sha256=publication_hash,
    )


def commit_prepared_cams_lifecycle(
    *,
    prepared: PreparedCamsRun,
    catalog: Catalog,
    state_store: SqliteStateStore,
    publisher: ContractV1Publisher,
    owner_id: str,
    published_at: str,
    now: datetime | None = None,
    lease_for: timedelta = CAMS_LEASE_DURATION,
    after_step: Callable[[str], None] | None = None,
) -> CamsLifecycleResult:
    """Commit a prepared run and release its fenced lease on every clean exit."""

    held: tuple[RunKey, RunRecord] | None = None
    failed = False

    def observe_lease(key: RunKey, record: RunRecord) -> None:
        nonlocal held
        held = (key, record)

    try:
        return _commit_prepared_cams_lifecycle(
            prepared=prepared,
            catalog=catalog,
            state_store=state_store,
            publisher=publisher,
            owner_id=owner_id,
            published_at=published_at,
            now=now,
            lease_for=lease_for,
            after_step=after_step,
            lease_observer=observe_lease,
        )
    except BaseException:
        failed = True
        raise
    finally:
        if held is not None:
            key, claimed = held
            release_at = (
                datetime.now(timezone.utc)
                if now is None
                else now.astimezone(timezone.utc)
            )
            try:
                state_store.release_lease(
                    key,
                    owner_id=owner_id,
                    fencing_token=claimed.fencing_token,
                    now=release_at,
                )
            except Exception:
                # Preserve the causal pipeline failure. If release itself
                # fails, the bounded lease remains the safe fallback.
                if not failed:
                    raise


def advance_cams_lifecycle(
    *,
    paths: CamsLifecyclePaths,
    catalog: Catalog,
    state_store: SqliteStateStore,
    publisher: ContractV1Publisher,
    owner_id: str,
    published_at: str,
    now: datetime | None = None,
    lease_for: timedelta = CAMS_LEASE_DURATION,
    after_step: Callable[[str], None] | None = None,
) -> CamsLifecycleResult:
    """Compatibility wrapper that prepares, then commits one CAMS run.

    The 15-minute lease is a crash bound, not a scheduler delay: a handled
    failure releases immediately, while a hard-killed process can block a
    successor only until the lease expires.  This local checkpoint has no
    heartbeat, so the lifecycle renews at the existing publication boundaries
    and deliberately fails closed if a stage ever outlives its lease.
    """

    prepared = prepare_cams_lifecycle(paths=paths, catalog=catalog)
    return commit_prepared_cams_lifecycle(
        prepared=prepared,
        catalog=catalog,
        state_store=state_store,
        publisher=publisher,
        owner_id=owner_id,
        published_at=published_at,
        now=now,
        lease_for=lease_for,
        after_step=after_step,
    )


__all__ = [
    "CAMS_LEASE_DURATION",
    "CamsEvidenceError",
    "CamsLeaseUnavailable",
    "CamsLifecycleError",
    "CamsLifecyclePaths",
    "CamsLifecycleResult",
    "PreparedCamsRun",
    "advance_cams_lifecycle",
    "commit_prepared_cams_lifecycle",
    "prepare_cams_lifecycle",
]
