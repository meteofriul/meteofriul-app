"""Serve already-published weather/v1 objects from a strict read-only store.

Unlike the legacy local pilot entrypoint, this process never materializes or
publishes ICON/CAMS data.  It accepts only an existing object database, builds
a verified referenced-run view and exposes that view on IPv4 loopback.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from local_pipeline.contract_v1 import (
    CAMS_POLLEN_PROVIDER,
    CAMS_PROVIDER,
    ICON_PROVIDER,
    Catalog,
    ContractError,
    load_catalog,
)
from local_pipeline.http_data_plane import make_server
from local_pipeline.published_runs_reader import (
    PublishedRunsObjectReader,
    PublishedRunsReaderError,
)
from local_pipeline.sqlite_object_store import ObjectStoreError
from local_pipeline.sqlite_read_only_object_store import SQLiteReadOnlyObjectStore


LOOPBACK_HOST = "127.0.0.1"


class PublishedDataPlaneError(RuntimeError):
    """The read-only data plane cannot start without weakening its guarantees."""


@dataclass(frozen=True)
class ReaderConfig:
    object_db: Path
    port: int


@dataclass
class PublishedDataPlaneService:
    reader: PublishedRunsObjectReader
    server: Any
    closed: bool = False

    @property
    def url(self) -> str:
        host, port = self.server.server_address[:2]
        return f"http://{host}:{port}/weather/v1/"

    @property
    def provider_statuses(self) -> Mapping[str, Mapping[str, Any]]:
        return self.reader.provider_statuses

    def close(self) -> None:
        if self.closed:
            return
        self.closed = True
        try:
            self.server.server_close()
        finally:
            self.reader.close()


def _normalized_config(config: ReaderConfig) -> ReaderConfig:
    if not isinstance(config, ReaderConfig):
        raise TypeError("config must be a ReaderConfig")
    if (
        isinstance(config.port, bool)
        or not isinstance(config.port, int)
        or not 0 <= config.port <= 65535
    ):
        raise PublishedDataPlaneError("port must be between 0 and 65535")
    return ReaderConfig(
        object_db=Path(config.object_db).expanduser(),
        port=config.port,
    )


def build_service(
    config: ReaderConfig,
    *,
    catalog_loader: Callable[[], Catalog] = load_catalog,
    store_factory: Callable[[Path], SQLiteReadOnlyObjectStore] = (
        SQLiteReadOnlyObjectStore
    ),
    reader_factory: Callable[..., PublishedRunsObjectReader] = (
        PublishedRunsObjectReader
    ),
    server_factory: Callable[..., Any] = make_server,
) -> PublishedDataPlaneService:
    """Open only read capabilities, then bind the loopback HTTP server."""

    selected = _normalized_config(config)
    catalog = catalog_loader()
    if not isinstance(catalog, Catalog):
        raise PublishedDataPlaneError("catalog loader did not return a contract catalog")

    store = None
    reader = None
    server = None
    try:
        store = store_factory(selected.object_db)
        reader = reader_factory(store, catalog)
        server = server_factory(reader, port=selected.port)
        address = getattr(server, "server_address", None)
        if (
            not isinstance(address, tuple)
            or len(address) < 2
            or address[0] != LOOPBACK_HOST
        ):
            raise PublishedDataPlaneError("data plane did not bind IPv4 loopback")
        return PublishedDataPlaneService(reader=reader, server=server)
    except Exception:
        if server is not None:
            server.server_close()
        if reader is not None:
            reader.close()
        elif store is not None:
            close = getattr(store, "close", None)
            if callable(close):
                close()
        raise


def serve_service(
    service: PublishedDataPlaneService,
    *,
    emit: Callable[[str], None] = print,
) -> None:
    statuses = service.provider_statuses
    icon = statuses.get(ICON_PROVIDER)
    if icon is None or icon["status"] == "unavailable":
        emit(f"{ICON_PROVIDER}: non disponibile")
    else:
        emit(f"{ICON_PROVIDER}: {icon['active_run_id']} · {icon['status']}")

    cams_core = statuses.get(CAMS_PROVIDER)
    cams_pollen = statuses.get(CAMS_POLLEN_PROVIDER)
    if (
        cams_core is None
        or cams_pollen is None
        or cams_core.get("status") != cams_pollen.get("status")
        or cams_core.get("active_run_id") != cams_pollen.get("active_run_id")
    ):
        emit("cams (core + pollini): stato non correlato")
    elif cams_core["status"] == "unavailable":
        emit("cams (core + pollini): non disponibile")
    else:
        emit(
            f"cams (core + pollini): {cams_core['active_run_id']} · "
            f"{cams_core['status']}"
        )
    emit(f"Data plane locale strettamente read-only: {service.url}")
    emit("Arresto: Ctrl+C. Questo processo non possiede operazioni di scrittura.")
    try:
        service.server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        service.close()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--object-db", required=True, type=Path)
    parser.add_argument("--port", required=True, type=int)
    return parser


def parse_config(argv: Sequence[str] | None = None) -> ReaderConfig:
    args = build_parser().parse_args(argv)
    return ReaderConfig(object_db=args.object_db, port=args.port)


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        service = build_service(ReaderConfig(args.object_db, args.port))
    except (
        ContractError,
        ObjectStoreError,
        PublishedRunsReaderError,
        PublishedDataPlaneError,
        OSError,
        TypeError,
        ValueError,
    ) as error:
        parser.error(str(error))
    serve_service(service)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
