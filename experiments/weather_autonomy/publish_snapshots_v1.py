"""Publish verified local ICON/CAMS snapshots without starting a server.

This is a local-pilot bootstrap boundary.  It reuses the verified snapshot
materializers and atomic contract publisher, closes the writable store before
returning and never opens a network socket.  The long-lived data plane is a
different process (`serve_published_contract_v1.py`) with read-only storage
capabilities.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
from pathlib import Path
import sys
from typing import Any, Callable, Mapping, Sequence, TextIO

from local_pipeline.contract_v1 import (
    CAMS_POLLEN_PROVIDER,
    CAMS_PROVIDER,
    ICON_PROVIDER,
)
from serve_contract_v1 import EntrypointConfig, build_service


RESULT_KIND = "meteofriul.weather.local_snapshot_writer.result"


class SnapshotWriterError(RuntimeError):
    """The local snapshot writer could not leave a complete published view."""


class _CliArgumentError(ValueError):
    """Message-free boundary signal for invalid command-line input."""


class _QuietArgumentParser(argparse.ArgumentParser):
    def error(self, _message: str) -> None:
        raise _CliArgumentError("invalid snapshot writer arguments")


@dataclass(frozen=True)
class SnapshotWriterConfig:
    icon_payload: Path
    icon_report: Path
    cams_payload: Path
    cams_report: Path
    object_db: Path


class _NoSocketBoundary:
    """Minimal server-shaped close boundary that never binds a socket."""

    server_address = ("127.0.0.1", 0)

    def __init__(self) -> None:
        self.closed = False

    def server_close(self) -> None:
        self.closed = True


def build_parser() -> argparse.ArgumentParser:
    parser = _QuietArgumentParser(description=__doc__, add_help=False)
    parser.add_argument("--icon-payload", required=True, type=Path)
    parser.add_argument("--icon-report", required=True, type=Path)
    parser.add_argument("--cams-payload", required=True, type=Path)
    parser.add_argument("--cams-report", required=True, type=Path)
    parser.add_argument("--object-db", required=True, type=Path)
    return parser


def parse_config(argv: Sequence[str] | None = None) -> SnapshotWriterConfig:
    values = build_parser().parse_args(argv)
    return SnapshotWriterConfig(
        icon_payload=values.icon_payload,
        icon_report=values.icon_report,
        cams_payload=values.cams_payload,
        cams_report=values.cams_report,
        object_db=values.object_db,
    )


def _run_id(document: Any) -> str | None:
    latest = document.get("latest") if isinstance(document, Mapping) else None
    value = latest.get("source_run_id") if isinstance(latest, Mapping) else None
    return value if isinstance(value, str) else None


def publish_snapshots(
    config: SnapshotWriterConfig,
    *,
    service_builder: Callable[..., Any] = build_service,
) -> Mapping[str, Any]:
    """Commit both verified snapshot families and close every write capability."""

    if not isinstance(config, SnapshotWriterConfig):
        raise TypeError("config must be SnapshotWriterConfig")
    boundary: _NoSocketBoundary | None = None

    def no_socket_server(_reader: Any, *, port: int) -> _NoSocketBoundary:
        nonlocal boundary
        if port != 0:
            raise SnapshotWriterError("snapshot writer requested a listening port")
        boundary = _NoSocketBoundary()
        return boundary

    service = service_builder(
        EntrypointConfig(
            icon_payload=config.icon_payload,
            icon_report=config.icon_report,
            cams_payload=config.cams_payload,
            cams_report=config.cams_report,
            object_db=config.object_db,
            port=0,
        ),
        server_factory=no_socket_server,
    )
    try:
        if boundary is None:
            raise SnapshotWriterError("snapshot writer boundary was not created")
        providers: dict[str, Mapping[str, str]] = {}
        for provider in (ICON_PROVIDER, CAMS_PROVIDER, CAMS_POLLEN_PROVIDER):
            status = service.provider_statuses.get(provider)
            run_id = _run_id(service.latest.get(provider))
            state = status.get("status") if isinstance(status, Mapping) else None
            if not isinstance(run_id, str) or not isinstance(state, str):
                raise SnapshotWriterError("snapshot publication is incomplete")
            providers[provider] = {
                "source_run_id": run_id,
                "status": state,
            }
        if providers[CAMS_PROVIDER]["source_run_id"] != providers[CAMS_POLLEN_PROVIDER]["source_run_id"]:
            raise SnapshotWriterError("CAMS snapshot family is not correlated")
        return {
            "schema_version": 1,
            "kind": RESULT_KIND,
            "status": "ready",
            "providers": providers,
            "socket_opened": False,
        }
    finally:
        service.close()
        if boundary is not None and not boundary.closed:
            raise SnapshotWriterError("snapshot writer boundary was not closed")


def _emit(value: Mapping[str, Any], stream: TextIO) -> None:
    stream.write(json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":")))
    stream.write("\n")


def main(argv: Sequence[str] | None = None, *, stream: TextIO | None = None) -> int:
    target = sys.stdout if stream is None else stream
    try:
        result = publish_snapshots(parse_config(argv))
    except _CliArgumentError:
        result = {
            "schema_version": 1,
            "kind": RESULT_KIND,
            "status": "failed",
            "reason_code": "invalid_cli_arguments",
        }
        _emit(result, target)
        return 2
    except BaseException:
        result = {
            "schema_version": 1,
            "kind": RESULT_KIND,
            "status": "failed",
            "reason_code": "snapshot_publication_failed",
        }
        _emit(result, target)
        return 1
    _emit(result, target)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
