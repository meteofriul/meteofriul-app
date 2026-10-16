"""Publish one already-acquired ICON run into the local weather/v1 store.

This command is deliberately offline.  It consumes explicit verified pilot
artifacts, freezes a durable publication intent and invokes only the ICON job.
It never acquires data, touches CAMS, starts a server or schedules another run.
"""

from __future__ import annotations

import argparse
from contextlib import ExitStack
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import sys
from typing import Any, Callable, Sequence, TextIO

from local_pipeline.contract_publisher import ContractV1Publisher
from local_pipeline.contract_v1 import Catalog, load_catalog
from local_pipeline.job_entrypoints import (
    IconJobInputs,
    PreparedIconPublication,
    classify_job_failure,
    execute_icon_job,
    prepare_icon_publication,
)
from local_pipeline.job_outcomes import JobKind, JobResult
from local_pipeline.job_runtime import (
    emit_job_result,
    normalize_database_path,
    normalize_existing_file,
    normalize_intent_directory,
    require_safe_sqlite_layout,
    resolve_job_publication_intent,
    with_intent_metric,
)
from local_pipeline.publication_intent import (
    PublicationIntentConflict,
    PublicationIntentResolution,
)
from local_pipeline.sqlite_object_store import SQLiteObjectStore


class _CliArgumentError(ValueError):
    """Private, message-free boundary signal for invalid CLI arguments."""


class _QuietArgumentParser(argparse.ArgumentParser):
    """Argument parser that never writes usage or rejected values to logs."""

    def error(self, _message: str) -> None:
        raise _CliArgumentError("invalid ICON job arguments")


@dataclass(frozen=True)
class IconRunnerConfig:
    payload: Path
    report: Path
    object_db: Path
    intent_directory: Path


def build_parser() -> argparse.ArgumentParser:
    # This is a machine boundary rather than an interactive command.  Standard
    # argparse diagnostics can contain operator-supplied paths, so even --help
    # is deliberately handled as a safe structured result by ``main``.
    parser = _QuietArgumentParser(description=__doc__, add_help=False)
    parser.add_argument("--payload", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument("--object-db", required=True, type=Path)
    parser.add_argument("--intent-directory", required=True, type=Path)
    return parser


def parse_config(argv: Sequence[str] | None = None) -> IconRunnerConfig:
    args = build_parser().parse_args(argv)
    return IconRunnerConfig(
        payload=args.payload,
        report=args.report,
        object_db=args.object_db,
        intent_directory=args.intent_directory,
    )


def _normalized(config: IconRunnerConfig) -> IconRunnerConfig:
    if not isinstance(config, IconRunnerConfig):
        raise TypeError("config must be an IconRunnerConfig")
    selected = IconRunnerConfig(
        payload=normalize_existing_file(config.payload, "ICON payload"),
        report=normalize_existing_file(config.report, "ICON report"),
        object_db=normalize_database_path(config.object_db, "Object database"),
        intent_directory=normalize_intent_directory(config.intent_directory),
    )
    require_safe_sqlite_layout(
        databases={"object database": selected.object_db},
        other_paths={
            "ICON payload": selected.payload,
            "ICON report": selected.report,
        },
    )
    return selected


def run_icon(
    config: IconRunnerConfig,
    *,
    clock: Callable[[], datetime],
    catalog_loader: Callable[[], Catalog] = load_catalog,
    preparer: Callable[..., PreparedIconPublication] = prepare_icon_publication,
    intent_resolver: Callable[..., PublicationIntentResolution] = (
        resolve_job_publication_intent
    ),
    store_factory: Callable[..., Any] = SQLiteObjectStore,
    publisher_factory: Callable[..., Any] = ContractV1Publisher,
    executor: Callable[..., JobResult] = execute_icon_job,
) -> JobResult:
    """Prepare all immutable identity before opening the writable object DB."""

    try:
        selected = _normalized(config)
        catalog = catalog_loader()
        prepared = preparer(
            payload=selected.payload,
            report=selected.report,
            catalog=catalog,
        )
        if not isinstance(prepared, PreparedIconPublication):
            raise TypeError("ICON preparer returned an invalid value")
        source_run_id = prepared.source_run_id
        intent_path = selected.intent_directory / f"icon-{source_run_id}.json"
        require_safe_sqlite_layout(
            databases={"object database": selected.object_db},
            other_paths={
                "ICON payload": selected.payload,
                "ICON report": selected.report,
                "publication intent": intent_path,
            },
        )
        resolution = intent_resolver(
            selected.intent_directory,
            job=JobKind.ICON,
            source_run_id=source_run_id,
            input_fingerprint_sha256=prepared.input_fingerprint_sha256,
            clock=clock,
        )
        if (
            resolution.intent.job is not JobKind.ICON
            or resolution.intent.source_run_id != prepared.source_run_id
            or resolution.intent.input_fingerprint_sha256
            != prepared.input_fingerprint_sha256
        ):
            raise PublicationIntentConflict(
                "Resolved ICON intent differs from the prepared run"
            )
        with ExitStack() as resources:
            object_store = resources.enter_context(store_factory(selected.object_db))
            publisher = publisher_factory(object_store, catalog)
            result = executor(
                IconJobInputs(
                    payload=selected.payload,
                    report=selected.report,
                    published_at=resolution.intent.published_at,
                    source_run_id=source_run_id,
                    input_fingerprint_sha256=(
                        resolution.intent.input_fingerprint_sha256
                    ),
                    prepared=prepared,
                ),
                catalog=catalog,
                publisher=publisher,
            )
        return with_intent_metric(result, resolution)
    except Exception as error:
        classified = classify_job_failure(JobKind.ICON, error)
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
        result = run_icon(config, clock=selected_clock)
        if not isinstance(result, JobResult) or result.job is not JobKind.ICON:
            raise RuntimeError("ICON runner returned an invalid result")
    except _CliArgumentError:
        result = JobResult(
            job=JobKind.ICON,
            status="permanent_failure",
            reason_code="invalid_cli_arguments",
        )
    except BaseException:
        # Every invocation that reaches this boundary, including an orderly
        # interrupt, emits one safe result. A hard process kill or interpreter
        # startup/import failure is necessarily outside this guarantee.
        result = JobResult(
            job=JobKind.ICON,
            status="manual_review",
            reason_code="unexpected_internal_failure",
        )
    emit_job_result(result, sys.stdout if stream is None else stream)
    return result.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
