"""Provider-isolated application entrypoints for local ICON and CAMS jobs.

The functions in this module perform no scheduling and open no network or
storage connection themselves.  Acquisition, durable state and object storage
are injected ports.  This keeps the orchestration testable with fakes and lets
later local/cloud adapters reuse the already verified pipeline primitives.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
import hashlib
import json
import sqlite3
from pathlib import Path
from types import MappingProxyType
from typing import Any, Callable, Mapping

from .cams_lifecycle import (
    CamsEvidenceError,
    CamsLeaseUnavailable,
    CamsLifecycleError,
    CamsLifecyclePaths,
    CamsLifecycleResult,
    PreparedCamsRun,
    advance_cams_lifecycle,
    commit_prepared_cams_lifecycle,
)
from .contract_publisher import (
    ContractPublicationError,
    ContractPublicationResult,
    ContractPublicationVerificationError,
    ContractV1Publisher,
    ImmutableContractConflict,
    LatestCasExhausted,
    StaleContractRun,
)
from .contract_v1 import (
    CAMS_POLLEN_PROVIDER,
    CAMS_PROVIDER,
    ICON_PROVIDER,
    Catalog,
    ContractError,
    canonical_json_bytes,
    validate_run_manifest,
)
from .contracts import (
    InvalidCheckpoint,
    InvalidTransition,
    LeaseLost,
    RunState,
    StateConflict,
)
from .job_outcomes import JobKind, JobResult, JobStatus
from .gcs_object_store import RemoteObjectStoreError
from .operational_diagnostics import error_fields, phase, safe_source_run_id
from .publication_intent import (
    fingerprint_input_files,
    InvalidPublicationIntent,
    PublicationInputError,
    PublicationIntentConflict,
    PublicationIntentCorruption,
    PublicationIntentError,
    PublicationIntent,
)
from .snapshot_materializer import (
    SnapshotMaterializationError,
    materialize_verified_icon,
)
from .sqlite_object_store import ObjectStoreError


class InvalidJobInputs(ValueError):
    """Deterministic operator/configuration error, safe to mark permanent."""


class JobResultInvariantError(RuntimeError):
    """A pipeline primitive returned an internally inconsistent result."""


class RetryableJobError(RuntimeError):
    """Typed transient failure raised by a concrete infrastructure adapter."""

    def __init__(self, reason_code: str, *, retry_after_seconds: int | None = None):
        super().__init__("typed retryable weather job failure")
        self.reason_code = reason_code
        self.retry_after_seconds = retry_after_seconds


@dataclass(frozen=True)
class PreparedIconPublication:
    """Immutable, fully validated ICON documents ready for storage commit."""

    source_run_id: str
    input_fingerprint_sha256: str
    documents: Mapping[str, bytes]
    manifest_bytes: bytes

    def __post_init__(self) -> None:
        if not isinstance(self.source_run_id, str):
            raise InvalidJobInputs("Prepared ICON run identity is invalid")
        if (
            not isinstance(self.input_fingerprint_sha256, str)
            or len(self.input_fingerprint_sha256) != 64
            or any(
                character not in "0123456789abcdef"
                for character in self.input_fingerprint_sha256
            )
        ):
            raise InvalidJobInputs("Prepared ICON fingerprint is invalid")
        if not isinstance(self.documents, Mapping) or any(
            not isinstance(key, str) or not isinstance(value, bytes)
            for key, value in self.documents.items()
        ):
            raise InvalidJobInputs("Prepared ICON documents are invalid")
        if not isinstance(self.manifest_bytes, bytes) or not self.manifest_bytes:
            raise InvalidJobInputs("Prepared ICON manifest is invalid")
        try:
            manifest = json.loads(self.manifest_bytes)
            canonical_manifest = canonical_json_bytes(manifest)
        except (UnicodeError, json.JSONDecodeError, ContractError) as error:
            raise InvalidJobInputs("Prepared ICON manifest is not canonical JSON") from error
        if (
            not isinstance(manifest, Mapping)
            or canonical_manifest != self.manifest_bytes
            or hashlib.sha256(self.manifest_bytes).hexdigest()
            != self.input_fingerprint_sha256
            or manifest.get("provider") != ICON_PROVIDER
            or manifest.get("source_run_id") != self.source_run_id
        ):
            raise InvalidJobInputs(
                "Prepared ICON manifest identity or fingerprint is inconsistent"
            )
        object.__setattr__(self, "documents", MappingProxyType(dict(self.documents)))

    def manifest(self) -> Mapping[str, Any]:
        try:
            value = json.loads(self.manifest_bytes)
        except (UnicodeError, json.JSONDecodeError) as error:
            raise JobResultInvariantError("Prepared ICON manifest is not JSON") from error
        if not isinstance(value, Mapping):
            raise JobResultInvariantError("Prepared ICON manifest is not an object")
        return value


@dataclass(frozen=True)
class IconJobInputs:
    payload: Path
    report: Path
    published_at: str
    source_run_id: str | None = None
    input_fingerprint_sha256: str | None = None
    prepared: PreparedIconPublication | None = None


@dataclass(frozen=True)
class CamsJobInputs:
    paths: CamsLifecyclePaths
    owner_id: str
    published_at: str
    prepared: PreparedCamsRun | None = None


def prepare_icon_publication(
    *,
    payload: Path,
    report: Path,
    catalog: Catalog,
    materializer: Callable[..., Mapping[str, Any]] = materialize_verified_icon,
) -> PreparedIconPublication:
    """Authenticate and materialize ICON once, before intent or writable stores."""

    bundle = materializer(
        catalog=catalog,
        icon_archive=Path(payload),
        icon_report=Path(report),
    )
    if not isinstance(bundle, Mapping) or not _catalog_matches(
        catalog, bundle.get("catalog")
    ):
        raise SnapshotMaterializationError(
            "Materialized ICON family does not match the authoritative catalog"
        )
    icon = bundle.get("icon")
    if not isinstance(icon, Mapping):
        raise SnapshotMaterializationError("Materializer omitted ICON")
    documents = icon.get("documents")
    manifest = icon.get("manifest")
    if not isinstance(documents, Mapping) or not isinstance(manifest, Mapping):
        raise SnapshotMaterializationError("Materializer returned incomplete ICON")
    validate_run_manifest(
        manifest,
        catalog,
        expected_provider=ICON_PROVIDER,
        object_bodies=documents,
    )
    source_run_id = manifest.get("source_run_id")
    if not isinstance(source_run_id, str):
        raise SnapshotMaterializationError("ICON manifest run identity is missing")
    manifest_bytes = canonical_json_bytes(manifest)
    return PreparedIconPublication(
        source_run_id=source_run_id,
        input_fingerprint_sha256=hashlib.sha256(manifest_bytes).hexdigest(),
        documents=documents,
        manifest_bytes=manifest_bytes,
    )


def _catalog_matches(expected: Catalog, observed: Any) -> bool:
    return (
        isinstance(observed, Catalog)
        and observed.reference() == expected.reference()
        and observed.istat_codes == expected.istat_codes
    )


def _icon_publication_result(publication: ContractPublicationResult) -> JobResult:
    if (
        publication.provider != ICON_PROVIDER
        or not isinstance(publication.source_run_id, str)
    ):
        raise JobResultInvariantError("ICON publication identity is inconsistent")
    metrics = {
        "validation_status": "passed",
        "publication_status": "verified",
        "latest_updated": publication.latest_updated,
        "manifest_reused": publication.manifest_reused,
        "payload_count": len(publication.payload_keys),
        "reused_payload_count": publication.reused_payload_count,
    }
    if publication.superseded:
        return JobResult(
            job=JobKind.ICON,
            status=JobStatus.NO_OP,
            reason_code="newer_run_already_active",
            source_run_id=publication.source_run_id,
            metrics=metrics,
        )
    if not publication.latest_updated:
        return JobResult(
            job=JobKind.ICON,
            status=JobStatus.NO_OP,
            reason_code="run_already_published",
            source_run_id=publication.source_run_id,
            metrics=metrics,
        )
    return JobResult(
        job=JobKind.ICON,
        status=JobStatus.PUBLISHED,
        reason_code="publication_committed",
        source_run_id=publication.source_run_id,
        published_providers=(ICON_PROVIDER,),
        metrics=metrics,
    )


def _cams_publication_result(result: CamsLifecycleResult) -> JobResult:
    stages = (result.core_stage, result.pollen_stage)
    family = result.family_publication
    source_run_id = getattr(result.key, "source_run_id", None)
    if (
        getattr(result.record, "state", None) is not RunState.PUBLISHED
        or not isinstance(source_run_id, str)
        or result.core_stage.provider != CAMS_PROVIDER
        or result.pollen_stage.provider != CAMS_POLLEN_PROVIDER
        or any(stage.source_run_id != source_run_id for stage in stages)
        or family.source_run_id != source_run_id
        or family.superseded
    ):
        raise JobResultInvariantError("CAMS publication identity is inconsistent")
    metrics = {
        "validation_status": "passed",
        "publication_status": "verified",
        "core_stage_idempotent": result.core_stage.idempotent,
        "pollen_stage_idempotent": result.pollen_stage.idempotent,
        "family_idempotent": family.idempotent,
        "family_latest_updated": family.latest_updated,
    }
    if not family.latest_updated:
        return JobResult(
            job=JobKind.CAMS,
            status=JobStatus.NO_OP,
            reason_code="run_already_published",
            source_run_id=source_run_id,
            metrics=metrics,
        )
    return JobResult(
        job=JobKind.CAMS,
        status=JobStatus.PUBLISHED,
        reason_code="publication_committed",
        source_run_id=source_run_id,
        published_providers=(CAMS_PROVIDER, CAMS_POLLEN_PROVIDER),
        metrics=metrics,
    )


def _classify_job_failure(job: JobKind, error: BaseException) -> JobResult | None:
    """Classify only failures whose retry semantics are unambiguous.

    Unknown exceptions return ``None`` and must remain visible to the caller;
    silently guessing that an internal programming error is retryable would
    create retry storms and hide defects.
    """

    safe_metric = error_fields(error)
    if isinstance(error, RemoteObjectStoreError):
        return JobResult(
            job=job,
            status=JobStatus.RETRYABLE_FAILURE if error.retryable else JobStatus.MANUAL_REVIEW,
            reason_code="remote_storage_temporary_failure" if error.retryable else "remote_storage_failure",
            metrics=safe_metric,
        )
    if isinstance(error, CamsLeaseUnavailable):
        return JobResult(
            job=job,
            status=JobStatus.RETRYABLE_FAILURE,
            reason_code="lease_still_held",
            retry_after_seconds=error.retry_after_seconds,
            metrics=safe_metric,
        )
    if isinstance(error, StaleContractRun):
        return JobResult(
            job=job,
            status=JobStatus.NO_OP,
            reason_code="newer_run_already_active",
            metrics=safe_metric,
        )
    if isinstance(error, RetryableJobError):
        return JobResult(
            job=job,
            status=JobStatus.RETRYABLE_FAILURE,
            reason_code=error.reason_code,
            retry_after_seconds=error.retry_after_seconds,
            metrics=safe_metric,
        )
    if isinstance(error, (LatestCasExhausted, LeaseLost)):
        return JobResult(
            job=job,
            status=JobStatus.RETRYABLE_FAILURE,
            reason_code="temporary_state_or_storage_failure",
            metrics=safe_metric,
        )
    if isinstance(
        error,
        (
            CamsEvidenceError,
            ContractPublicationError,
            ImmutableContractConflict,
            ContractPublicationVerificationError,
            InvalidCheckpoint,
            InvalidTransition,
            StateConflict,
            SnapshotMaterializationError,
            JobResultInvariantError,
            sqlite3.OperationalError,
        ),
    ):
        return JobResult(
            job=job,
            status=JobStatus.MANUAL_REVIEW,
            reason_code="verified_pipeline_invariant_failed",
            metrics=safe_metric,
        )
    if isinstance(error, FileNotFoundError):
        return JobResult(
            job=job,
            status=JobStatus.PERMANENT_FAILURE,
            reason_code="required_input_missing",
            metrics=safe_metric,
        )
    if isinstance(error, InvalidPublicationIntent):
        return JobResult(
            job=job,
            status=JobStatus.PERMANENT_FAILURE,
            reason_code="invalid_publication_intent_configuration",
            metrics=safe_metric,
        )
    if isinstance(
        error,
        (
            PublicationInputError,
            PublicationIntentConflict,
            PublicationIntentCorruption,
            PublicationIntentError,
        ),
    ):
        return JobResult(
            job=job,
            status=JobStatus.MANUAL_REVIEW,
            reason_code="publication_intent_verification_failed",
            metrics=safe_metric,
        )
    if isinstance(error, OSError):
        return JobResult(
            job=job,
            status=JobStatus.MANUAL_REVIEW,
            reason_code="local_storage_failure",
            metrics=safe_metric,
        )
    if isinstance(error, (ContractError, CamsLifecycleError, ObjectStoreError)):
        return JobResult(
            job=job,
            status=JobStatus.MANUAL_REVIEW,
            reason_code="pipeline_validation_failed",
            metrics=safe_metric,
        )
    if isinstance(error, InvalidJobInputs):
        return JobResult(
            job=job,
            status=JobStatus.PERMANENT_FAILURE,
            reason_code="invalid_job_configuration",
            metrics=safe_metric,
        )
    return None


def classify_job_failure(
    job: JobKind, error: BaseException, *, source_run_id: str | None = None,
) -> JobResult | None:
    """Preserve the known run and typed, bounded diagnostics in every failure."""
    result = _classify_job_failure(job, error)
    if result is None:
        return None
    run = safe_source_run_id(source_run_id) or safe_source_run_id(result.metrics.get("source_run_id"))
    return replace(result, source_run_id=run)


def execute_icon_job(
    inputs: IconJobInputs,
    *,
    catalog: Catalog,
    publisher: ContractV1Publisher,
    materializer: Callable[..., Mapping[str, Any]] = materialize_verified_icon,
) -> JobResult:
    """Materialize and publish only ICON; CAMS is never read or modified."""

    source_run_id = safe_source_run_id(getattr(inputs, "source_run_id", None))
    try:
        if not isinstance(inputs, IconJobInputs):
            raise InvalidJobInputs("inputs must be IconJobInputs")
        if (inputs.source_run_id is None) != (
            inputs.input_fingerprint_sha256 is None
        ):
            raise InvalidJobInputs(
                "ICON publication identity must include both run and fingerprint"
            )
        if inputs.prepared is not None:
            if not isinstance(inputs.prepared, PreparedIconPublication):
                raise InvalidJobInputs("Prepared ICON publication is invalid")
            if (
                inputs.source_run_id != inputs.prepared.source_run_id
                or inputs.input_fingerprint_sha256
                != inputs.prepared.input_fingerprint_sha256
            ):
                raise PublicationIntentConflict(
                    "Prepared ICON data differs from its publication intent"
                )
            documents = inputs.prepared.documents
            manifest = inputs.prepared.manifest()
            with phase("icon_validation", provider="icon", source_run_id=source_run_id):
                validate_run_manifest(
                    manifest,
                    catalog,
                    expected_provider=ICON_PROVIDER,
                    object_bodies=documents,
                )
            if (
                hashlib.sha256(canonical_json_bytes(manifest)).hexdigest()
                != inputs.prepared.input_fingerprint_sha256
            ):
                raise JobResultInvariantError("Prepared ICON manifest fingerprint changed")
        else:
            with phase("icon_materialization", provider="icon", source_run_id=source_run_id):
                bundle = materializer(
                    catalog=catalog,
                    icon_archive=Path(inputs.payload),
                    icon_report=Path(inputs.report),
                )
            if not isinstance(bundle, Mapping) or not _catalog_matches(
                catalog, bundle.get("catalog")
            ):
                raise SnapshotMaterializationError(
                    "Materialized ICON family does not match the authoritative catalog"
                )
            icon = bundle.get("icon")
            if not isinstance(icon, Mapping):
                raise SnapshotMaterializationError("Materializer omitted ICON")
            documents = icon.get("documents")
            manifest = icon.get("manifest")
            if not isinstance(documents, Mapping) or not isinstance(manifest, Mapping):
                raise SnapshotMaterializationError(
                    "Materializer returned incomplete ICON"
                )
        if inputs.source_run_id is not None and inputs.prepared is None:
            if manifest.get("source_run_id") != inputs.source_run_id:
                raise SnapshotMaterializationError(
                    "Materialized ICON run differs from its publication intent"
                )
            observed_fingerprint = fingerprint_input_files(
                {"payload": Path(inputs.payload), "report": Path(inputs.report)}
            )
            if observed_fingerprint != inputs.input_fingerprint_sha256:
                raise PublicationIntentConflict(
                    "ICON inputs changed after publication intent resolution"
                )
        source_run_id = safe_source_run_id(manifest.get("source_run_id")) or source_run_id
        with phase("icon_publication", provider="icon", source_run_id=source_run_id):
            publication = publisher.publish_run(
                ICON_PROVIDER,
                documents,
                manifest,
                published_at=inputs.published_at,
            )
        return _icon_publication_result(publication)
    except Exception as error:
        classified = classify_job_failure(JobKind.ICON, error, source_run_id=source_run_id)
        if classified is None:
            raise
        return classified


def execute_icon_recovery(*, intent: PublicationIntent, publisher: ContractV1Publisher) -> JobResult:
    """Publish only a fully stored ICON run; never acquire or rewrite inputs."""
    source_run_id = safe_source_run_id(getattr(intent, "source_run_id", None))
    try:
        if not isinstance(intent, PublicationIntent) or intent.job is not JobKind.ICON:
            raise InvalidJobInputs("ICON recovery requires an ICON publication intent")
        with phase("icon_publication_recovery", provider="icon", source_run_id=source_run_id):
            publication = publisher.publish_existing_run(
                ICON_PROVIDER, intent.source_run_id,
                expected_manifest_sha256=intent.input_fingerprint_sha256,
                published_at=intent.published_at,
            )
        return _icon_publication_result(publication)
    except Exception as error:
        classified = classify_job_failure(JobKind.ICON, error, source_run_id=source_run_id)
        if classified is None:
            raise
        return classified


def execute_cams_job(
    inputs: CamsJobInputs,
    *,
    catalog: Catalog,
    state_store: Any,
    publisher: ContractV1Publisher,
    lifecycle: Callable[..., CamsLifecycleResult] = advance_cams_lifecycle,
    prepared_lifecycle: Callable[..., CamsLifecycleResult] = (
        commit_prepared_cams_lifecycle
    ),
) -> JobResult:
    """Advance and publish only CAMS; ICON is never read or modified."""

    source_run_id = safe_source_run_id(getattr(getattr(getattr(inputs, "prepared", None), "key", None), "source_run_id", None))
    try:
        if not isinstance(inputs, CamsJobInputs):
            raise InvalidJobInputs("inputs must be CamsJobInputs")
        common = {
            "catalog": catalog,
            "state_store": state_store,
            "publisher": publisher,
            "owner_id": inputs.owner_id,
            "published_at": inputs.published_at,
        }
        with phase("cams_publication", provider="cams", source_run_id=source_run_id):
            if inputs.prepared is None:
                result = lifecycle(paths=inputs.paths, **common)
            else:
                if not isinstance(inputs.prepared, PreparedCamsRun):
                    raise InvalidJobInputs("Prepared CAMS publication is invalid")
                result = prepared_lifecycle(prepared=inputs.prepared, **common)
        return _cams_publication_result(result)
    except Exception as error:
        classified = classify_job_failure(JobKind.CAMS, error, source_run_id=source_run_id)
        if classified is None:
            raise
        return classified


__all__ = [
    "CamsJobInputs",
    "IconJobInputs",
    "InvalidJobInputs",
    "JobResultInvariantError",
    "PreparedIconPublication",
    "RetryableJobError",
    "classify_job_failure",
    "execute_cams_job",
    "execute_icon_job",
    "execute_icon_recovery",
    "prepare_icon_publication",
]
