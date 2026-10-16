"""Publish one complete local CAMS lifecycle into the weather/v1 store.

This command consumes only an existing acquisition directory plus decoded
artifacts.  It performs no ADS request, download, ICON work, server startup or
scheduler mutation.  CAMS core and pollen share one frozen publication intent.
"""

from __future__ import annotations

import argparse
from contextlib import ExitStack
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import sys
from typing import Any, Callable, Sequence, TextIO
from uuid import uuid4

from local_pipeline.cams_lifecycle import (
    CamsLifecyclePaths,
    PreparedCamsRun,
    prepare_cams_lifecycle,
)
from local_pipeline.contract_publisher import ContractV1Publisher
from local_pipeline.contract_v1 import Catalog, load_catalog
from local_pipeline.job_entrypoints import (
    CamsJobInputs,
    classify_job_failure,
    execute_cams_job,
)
from local_pipeline.job_outcomes import JobKind, JobResult
from local_pipeline.job_runtime import (
    emit_job_result,
    normalize_database_path,
    normalize_existing_directory,
    normalize_existing_file,
    normalize_intent_directory,
    normalize_owner_id,
    require_safe_sqlite_layout,
    resolve_job_publication_intent,
    with_intent_metric,
)
from local_pipeline.publication_intent import (
    PublicationIntentConflict,
    PublicationIntentResolution,
)
from local_pipeline.sqlite_object_store import SQLiteObjectStore
from local_pipeline.sqlite_state import SqliteStateStore


class _CliArgumentError(ValueError):
    """Private, message-free boundary signal for invalid CLI arguments."""


class _QuietArgumentParser(argparse.ArgumentParser):
    """Argument parser that never writes usage or rejected values to logs."""

    def error(self, _message: str) -> None:
        raise _CliArgumentError("invalid CAMS job arguments")


@dataclass(frozen=True)
class CamsRunnerConfig:
    artifacts_directory: Path
    decoded_payload: Path
    decode_report: Path
    state_db: Path
    object_db: Path
    intent_directory: Path


def create_cams_attempt_id() -> str:
    """Return a fresh, non-operator-controlled owner for one invocation."""

    return f"cams-attempt-{uuid4().hex}"


def build_parser() -> argparse.ArgumentParser:
    # This is a machine boundary rather than an interactive command.  Standard
    # argparse diagnostics can contain operator-supplied paths, so even --help
    # is deliberately handled as a safe structured result by ``main``.
    parser = _QuietArgumentParser(description=__doc__, add_help=False)
    parser.add_argument("--artifacts-directory", required=True, type=Path)
    parser.add_argument("--decoded-payload", required=True, type=Path)
    parser.add_argument("--decode-report", required=True, type=Path)
    parser.add_argument("--state-db", required=True, type=Path)
    parser.add_argument("--object-db", required=True, type=Path)
    parser.add_argument("--intent-directory", required=True, type=Path)
    return parser


def parse_config(argv: Sequence[str] | None = None) -> CamsRunnerConfig:
    args = build_parser().parse_args(argv)
    return CamsRunnerConfig(
        artifacts_directory=args.artifacts_directory,
        decoded_payload=args.decoded_payload,
        decode_report=args.decode_report,
        state_db=args.state_db,
        object_db=args.object_db,
        intent_directory=args.intent_directory,
    )


def _normalized(config: CamsRunnerConfig) -> tuple[CamsRunnerConfig, CamsLifecyclePaths]:
    if not isinstance(config, CamsRunnerConfig):
        raise TypeError("config must be a CamsRunnerConfig")
    paths = CamsLifecyclePaths(
        normalize_existing_directory(
            config.artifacts_directory,
            "CAMS artifacts directory",
        ),
        normalize_existing_file(config.decoded_payload, "CAMS decoded payload"),
        normalize_existing_file(config.decode_report, "CAMS decode report"),
    ).normalized()
    selected = CamsRunnerConfig(
        artifacts_directory=paths.artifacts_directory,
        decoded_payload=paths.decoded_payload,
        decode_report=paths.decode_report,
        state_db=normalize_database_path(config.state_db, "State database"),
        object_db=normalize_database_path(config.object_db, "Object database"),
        intent_directory=normalize_intent_directory(config.intent_directory),
    )
    require_safe_sqlite_layout(
        databases={
            "state database": selected.state_db,
            "object database": selected.object_db,
        },
        other_paths={
            "CAMS decoded payload": selected.decoded_payload,
            "CAMS decode report": selected.decode_report,
            "CAMS request plan": selected.artifacts_directory / "request-plan.json",
            "CAMS saved request": selected.artifacts_directory / "request.json",
            "CAMS submission intent": (
                selected.artifacts_directory / "submission-intent.json"
            ),
            "CAMS saved job": selected.artifacts_directory / "job.json",
            "CAMS completed download": (
                selected.artifacts_directory / "source.grib.complete.json"
            ),
            "CAMS partial download": (
                selected.artifacts_directory / "source.grib.part"
            ),
            "CAMS partial download metadata": (
                selected.artifacts_directory / "source.grib.part.json"
            ),
            "CAMS GRIB": selected.artifacts_directory / "source.grib",
        },
    )
    return selected, paths


def run_cams(
    config: CamsRunnerConfig,
    *,
    clock: Callable[[], datetime],
    catalog_loader: Callable[[], Catalog] = load_catalog,
    preparer: Callable[..., PreparedCamsRun] = prepare_cams_lifecycle,
    intent_resolver: Callable[..., PublicationIntentResolution] = (
        resolve_job_publication_intent
    ),
    state_store_factory: Callable[..., Any] = SqliteStateStore,
    object_store_factory: Callable[..., Any] = SQLiteObjectStore,
    publisher_factory: Callable[..., Any] = ContractV1Publisher,
    executor: Callable[..., JobResult] = execute_cams_job,
    attempt_id_factory: Callable[[], str] = create_cams_attempt_id,
) -> JobResult:
    """Resolve identity first, then open state followed by object storage."""

    try:
        selected, paths = _normalized(config)
        catalog = catalog_loader()
        prepared = preparer(paths=paths, catalog=catalog)
        if not isinstance(prepared, PreparedCamsRun):
            raise TypeError("CAMS preparer returned an invalid value")
        source_run_id = prepared.source_run_id
        intent_path = selected.intent_directory / f"cams-{source_run_id}.json"
        require_safe_sqlite_layout(
            databases={
                "state database": selected.state_db,
                "object database": selected.object_db,
            },
            other_paths={
                "CAMS decoded payload": selected.decoded_payload,
                "CAMS decode report": selected.decode_report,
                "publication intent": intent_path,
            },
        )
        resolution = intent_resolver(
            selected.intent_directory,
            job=JobKind.CAMS,
            source_run_id=source_run_id,
            input_fingerprint_sha256=prepared.input_fingerprint_sha256,
            clock=clock,
        )
        if (
            resolution.intent.job is not JobKind.CAMS
            or resolution.intent.source_run_id != prepared.source_run_id
            or resolution.intent.input_fingerprint_sha256
            != prepared.input_fingerprint_sha256
        ):
            raise PublicationIntentConflict(
                "Resolved CAMS intent differs from the prepared run"
            )
        attempt_id = normalize_owner_id(attempt_id_factory())
        with ExitStack() as resources:
            state_store = resources.enter_context(
                state_store_factory(selected.state_db)
            )
            object_store = resources.enter_context(
                object_store_factory(
                    selected.object_db,
                    state_database_path=selected.state_db,
                )
            )
            publisher = publisher_factory(object_store, catalog)
            result = executor(
                CamsJobInputs(
                    paths=paths,
                    owner_id=attempt_id,
                    published_at=resolution.intent.published_at,
                    prepared=prepared,
                ),
                catalog=catalog,
                state_store=state_store,
                publisher=publisher,
            )
        return with_intent_metric(result, resolution)
    except Exception as error:
        classified = classify_job_failure(JobKind.CAMS, error)
        if classified is None:
            raise
        return classified


def main(
    argv: Sequence[str] | None = None,
    *,
    stream: TextIO | None = None,
    clock: Callable[[], datetime] | None = None,
) -> int:
    try:
        config = parse_config(argv)
        selected_clock = clock
        if selected_clock is None:
            from datetime import timezone

            selected_clock = lambda: datetime.now(timezone.utc)
        result = run_cams(config, clock=selected_clock)
        if not isinstance(result, JobResult) or result.job is not JobKind.CAMS:
            raise RuntimeError("CAMS runner returned an invalid result")
    except _CliArgumentError:
        result = JobResult(
            job=JobKind.CAMS,
            status="permanent_failure",
            reason_code="invalid_cli_arguments",
        )
    except BaseException:
        # Every invocation that reaches this boundary, including an orderly
        # interrupt, emits one safe result. A hard process kill or interpreter
        # startup/import failure is necessarily outside this guarantee.
        result = JobResult(
            job=JobKind.CAMS,
            status="manual_review",
            reason_code="unexpected_internal_failure",
        )
    emit_job_result(result, sys.stdout if stream is None else stream)
    return result.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
