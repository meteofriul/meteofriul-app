"""Publish weather/v1 snapshots and serve them on local loopback.

All four snapshot/sidecar paths, the SQLite object database and the port must
be selected explicitly. A failed provider family may retain a completely
verified previous run, but it can never make another family unavailable. The
command never downloads data, contacts cloud services, exposes a non-loopback
bind, or reads OSMER/alert data.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import sqlite3
from typing import Any, Callable, Mapping, Sequence

from local_pipeline.contract_publisher import (
    CamsFamilyPublicationResult,
    ContractPublicationError,
    ContractPublicationResult,
    ContractStageResult,
    ContractV1Publisher,
)
from local_pipeline.contract_v1 import (
    CAMS_POLLEN_PROVIDER,
    CAMS_PROVIDER,
    ICON_PROVIDER,
    Catalog,
    ContractError,
    canonical_json_bytes,
    load_catalog,
)
from local_pipeline.http_data_plane import make_server
from local_pipeline.published_runs_reader import PublishedRunsObjectReader
from local_pipeline.snapshot_materializer import (
    SnapshotMaterializationError,
    materialize_verified_cams,
    materialize_verified_icon,
)
from local_pipeline.sqlite_object_store import ObjectStoreError, SQLiteObjectStore


LOOPBACK_HOST = "127.0.0.1"


class ContractV1EntrypointError(RuntimeError):
    """The local data plane was not safe to start."""


@dataclass(frozen=True)
class EntrypointConfig:
    icon_payload: Path
    icon_report: Path
    cams_payload: Path
    cams_report: Path
    object_db: Path
    port: int
    published_at: str | None = None


@dataclass
class LocalContractV1Service:
    catalog: Catalog
    object_store: SQLiteObjectStore
    server: Any
    publications: Mapping[str, Any]
    latest: Mapping[str, Mapping[str, Any]]
    provider_statuses: Mapping[str, Mapping[str, Any]]
    closed: bool = False

    @property
    def url(self) -> str:
        host, port = self.server.server_address[:2]
        return f"http://{host}:{port}/weather/v1/"

    def close(self) -> None:
        if self.closed:
            return
        self.closed = True
        try:
            self.server.server_close()
        finally:
            self.object_store.close()


def _normalized_config(config: EntrypointConfig) -> EntrypointConfig:
    if not isinstance(config, EntrypointConfig):
        raise TypeError("config must be an EntrypointConfig")
    if isinstance(config.port, bool) or not isinstance(config.port, int) or not 0 <= config.port <= 65535:
        raise ContractV1EntrypointError("port must be between 0 and 65535")
    artifact_paths = tuple(
        Path(value).expanduser().resolve()
        for value in (
            config.icon_payload,
            config.icon_report,
            config.cams_payload,
            config.cams_report,
        )
    )
    if len(set(artifact_paths)) != len(artifact_paths):
        raise ContractV1EntrypointError("the four snapshot and report paths must be distinct")
    object_db = Path(config.object_db).expanduser().resolve()
    if object_db in artifact_paths:
        raise ContractV1EntrypointError("object database cannot overwrite an input artifact")
    published_at = config.published_at
    if published_at is not None:
        if not isinstance(published_at, str):
            raise ContractV1EntrypointError("published_at must be a UTC timestamp")
        try:
            parsed = datetime.strptime(published_at, "%Y-%m-%dT%H:%M:%SZ")
        except ValueError as error:
            raise ContractV1EntrypointError(
                "published_at must use canonical UTC seconds"
            ) from error
        if parsed.strftime("%Y-%m-%dT%H:%M:%SZ") != published_at:
            raise ContractV1EntrypointError("published_at must use canonical UTC seconds")
    return EntrypointConfig(
        icon_payload=artifact_paths[0],
        icon_report=artifact_paths[1],
        cams_payload=artifact_paths[2],
        cams_report=artifact_paths[3],
        object_db=object_db,
        port=config.port,
        published_at=published_at,
    )


def _utc_now(clock: Callable[[], datetime]) -> str:
    value = clock()
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ContractV1EntrypointError("clock must return a timezone-aware datetime")
    return value.astimezone(timezone.utc).replace(microsecond=0).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )


def _catalog_matches(expected: Catalog, observed: Any) -> bool:
    return (
        isinstance(observed, Catalog)
        and observed.reference() == expected.reference()
        and observed.istat_codes == expected.istat_codes
    )


_PROVIDER_FAILURES = (
    ContractError,
    ContractPublicationError,
    ContractV1EntrypointError,
    ObjectStoreError,
    OSError,
)


def _provider_failure(error: BaseException) -> str:
    return f"{type(error).__name__}: {error}"


def _verified_run_id(provider: str, document: Any) -> str:
    if (
        not isinstance(document, Mapping)
        or document.get("provider") != provider
        or not isinstance(document.get("latest"), Mapping)
        or not isinstance(document["latest"].get("source_run_id"), str)
    ):
        raise ContractV1EntrypointError(
            f"verified latest for {provider} has an invalid envelope"
        )
    return document["latest"]["source_run_id"]


def _retain_verified_latest(
    publisher: ContractV1Publisher,
    provider: str,
    *,
    cause: BaseException,
    latest: dict[str, Mapping[str, Any]],
    statuses: dict[str, Mapping[str, Any]],
) -> None:
    """Retain only a previous run whose complete active body set revalidates."""

    try:
        observed = publisher.read_verified_latest(provider)
        if observed is None:
            statuses[provider] = {
                "status": "unavailable",
                "active_run_id": None,
                "reason": _provider_failure(cause),
            }
            return
        run_id = _verified_run_id(provider, observed)
    except _PROVIDER_FAILURES as recovery_error:
        statuses[provider] = {
            "status": "unavailable",
            "active_run_id": None,
            "reason": (
                f"{_provider_failure(cause)}; recovery failed: "
                f"{_provider_failure(recovery_error)}"
            ),
        }
        return
    latest[provider] = observed
    statuses[provider] = {
        "status": "retained",
        "active_run_id": run_id,
        "reason": _provider_failure(cause),
    }


def _publish_provider_bundle(
    publisher: ContractV1Publisher,
    provider: str,
    provider_bundle: Any,
    *,
    published_at: str,
    publications: dict[str, ContractPublicationResult],
    latest: dict[str, Mapping[str, Any]],
    statuses: dict[str, Mapping[str, Any]],
) -> None:
    try:
        if not isinstance(provider_bundle, Mapping):
            raise ContractV1EntrypointError(f"materializer omitted {provider}")
        documents = provider_bundle.get("documents")
        manifest = provider_bundle.get("manifest")
        if not isinstance(documents, Mapping) or not isinstance(manifest, Mapping):
            raise ContractV1EntrypointError(
                f"materializer returned an incomplete {provider} bundle"
            )
        publication = publisher.publish_run(
            provider,
            documents,
            manifest,
            published_at=published_at,
        )
        # publish_run has already verified all 215 immutable bodies before it
        # returns. Reuse that strong verification only while the exact latest
        # ETag is still current; a concurrent advance must be verified in full.
        observed = None
        if not publication.superseded:
            observed = publisher.read_latest_if_etag(
                provider,
                publication.latest_etag,
            )
        if observed is None:
            observed = publisher.read_verified_latest(provider)
        observed_run_id = _verified_run_id(provider, observed)
        supplied_run_id = manifest.get("source_run_id")
        if not isinstance(supplied_run_id, str):
            raise ContractV1EntrypointError(
                f"materialized {provider} manifest has no run identity"
            )
        if observed_run_id < supplied_run_id:
            raise ContractV1EntrypointError(
                f"verified {provider} latest regressed behind the supplied run"
            )
        publications[provider] = publication
        latest[provider] = observed
        statuses[provider] = {
            "status": (
                "published" if observed_run_id == supplied_run_id else "superseded"
            ),
            "active_run_id": observed_run_id,
            "reason": None,
        }
    except _PROVIDER_FAILURES as error:
        _retain_verified_latest(
            publisher,
            provider,
            cause=error,
            latest=latest,
            statuses=statuses,
        )


def _cams_family_run_id(document: Any) -> str:
    if (
        not isinstance(document, Mapping)
        or document.get("family") != "cams"
        or not isinstance(document.get("latest"), Mapping)
        or not isinstance(document["latest"].get("source_run_id"), str)
    ):
        raise ContractV1EntrypointError("verified CAMS family has an invalid envelope")
    return document["latest"]["source_run_id"]


def _set_cams_statuses(
    statuses: dict[str, Mapping[str, Any]],
    *,
    status: str,
    active_run_id: str | None,
    reason: str | None,
) -> None:
    for provider in (CAMS_PROVIDER, CAMS_POLLEN_PROVIDER):
        statuses[provider] = {
            "status": status,
            "active_run_id": active_run_id,
            "reason": reason,
        }


def _retain_verified_cams_family(
    publisher: ContractV1Publisher,
    *,
    cause: BaseException,
    latest: dict[str, Mapping[str, Any]],
    statuses: dict[str, Mapping[str, Any]],
) -> None:
    """Retain CAMS only as one fully reverified core+pollen release."""

    try:
        observed = publisher.read_verified_cams_family_latest()
        if observed is None:
            _set_cams_statuses(
                statuses,
                status="unavailable",
                active_run_id=None,
                reason=_provider_failure(cause),
            )
            return
        run_id = _cams_family_run_id(observed)
    except _PROVIDER_FAILURES as recovery_error:
        _set_cams_statuses(
            statuses,
            status="unavailable",
            active_run_id=None,
            reason=(
                f"{_provider_failure(cause)}; recovery failed: "
                f"{_provider_failure(recovery_error)}"
            ),
        )
        return
    latest[CAMS_PROVIDER] = observed
    latest[CAMS_POLLEN_PROVIDER] = observed
    _set_cams_statuses(
        statuses,
        status="retained",
        active_run_id=run_id,
        reason=_provider_failure(cause),
    )


def _publish_cams_family(
    publisher: ContractV1Publisher,
    bundle: Mapping[str, Any],
    *,
    published_at: str,
    publications: dict[str, Any],
    latest: dict[str, Mapping[str, Any]],
    statuses: dict[str, Mapping[str, Any]],
) -> None:
    """Stage both projections, then expose them with the sole family CAS."""

    try:
        members: dict[str, Mapping[str, Any]] = {}
        for provider, bundle_key in (
            (CAMS_PROVIDER, "cams"),
            (CAMS_POLLEN_PROVIDER, "cams_pollen"),
        ):
            member = bundle.get(bundle_key)
            if not isinstance(member, Mapping):
                raise ContractV1EntrypointError(f"materializer omitted {provider}")
            documents = member.get("documents")
            manifest = member.get("manifest")
            if not isinstance(documents, Mapping) or not isinstance(manifest, Mapping):
                raise ContractV1EntrypointError(
                    f"materializer returned an incomplete {provider} bundle"
                )
            if manifest.get("provider") != provider:
                raise ContractV1EntrypointError(
                    f"materializer mixed the {provider} manifest identity"
                )
            members[provider] = member

        core_manifest = members[CAMS_PROVIDER]["manifest"]
        pollen_manifest = members[CAMS_POLLEN_PROVIDER]["manifest"]
        source_run_id = core_manifest.get("source_run_id")
        if (
            not isinstance(source_run_id, str)
            or pollen_manifest.get("source_run_id") != source_run_id
        ):
            raise ContractV1EntrypointError(
                "materialized CAMS projections do not identify the same run"
            )

        core_stage: ContractStageResult = publisher.stage_run(
            CAMS_PROVIDER,
            members[CAMS_PROVIDER]["documents"],
            core_manifest,
        )
        pollen_stage: ContractStageResult = publisher.stage_run(
            CAMS_POLLEN_PROVIDER,
            members[CAMS_POLLEN_PROVIDER]["documents"],
            pollen_manifest,
        )
        validation_sha256 = hashlib.sha256(
            canonical_json_bytes(
                {
                    "schema_version": 1,
                    "kind": "meteofriul.weather.local_materialization_validation",
                    "source_run_id": source_run_id,
                    "catalog": publisher.catalog.reference(),
                    "core_manifest_sha256": core_stage.manifest_sha256,
                    "pollen_manifest_sha256": pollen_stage.manifest_sha256,
                }
            )
        ).hexdigest()
        # A local pilot is restarted repeatedly against the same verified
        # artifacts.  The immutable family release includes published_at, so
        # replay the timestamp already bound to that run instead of creating a
        # conflicting release merely because the process restarted later.
        existing_family = publisher.read_verified_cams_family_latest()
        release_published_at = published_at
        if (
            existing_family is not None
            and _cams_family_run_id(existing_family) == source_run_id
        ):
            existing_published_at = existing_family.get("published_at")
            if not isinstance(existing_published_at, str):
                raise ContractV1EntrypointError(
                    "verified CAMS family omitted its publication time"
                )
            release_published_at = existing_published_at
            release_path = existing_family["latest"].get("release_path")
            if not isinstance(release_path, str):
                raise ContractV1EntrypointError(
                    "verified CAMS family omitted its release path"
                )
            stored_release = publisher.store.get(
                f"{publisher.cams_family_root()}/{release_path}"
            )
            try:
                existing_release = json.loads(stored_release.body.decode("utf-8"))
                validation_sha256 = existing_release["validation_sha256"]
            except (KeyError, UnicodeDecodeError, json.JSONDecodeError) as error:
                raise ContractV1EntrypointError(
                    "verified CAMS family release evidence is unreadable"
                ) from error
        family: CamsFamilyPublicationResult = publisher.release_cams_family(
            core_stage,
            pollen_stage,
            validation_sha256=validation_sha256,
            published_at=release_published_at,
        )
        observed = publisher.read_verified_cams_family_latest()
        observed_run_id = _cams_family_run_id(observed)
        if observed_run_id < source_run_id:
            raise ContractV1EntrypointError(
                "verified CAMS family regressed behind the supplied run"
            )
        publications[CAMS_PROVIDER] = core_stage
        publications[CAMS_POLLEN_PROVIDER] = pollen_stage
        publications["families/cams"] = family
        latest[CAMS_PROVIDER] = observed
        latest[CAMS_POLLEN_PROVIDER] = observed
        _set_cams_statuses(
            statuses,
            status=("published" if observed_run_id == source_run_id else "superseded"),
            active_run_id=observed_run_id,
            reason=None,
        )
    except _PROVIDER_FAILURES as error:
        _retain_verified_cams_family(
            publisher,
            cause=error,
            latest=latest,
            statuses=statuses,
        )


def build_service(
    config: EntrypointConfig,
    *,
    catalog_loader: Callable[[], Catalog] = load_catalog,
    icon_materializer: Callable[..., Mapping[str, Any]] = materialize_verified_icon,
    cams_materializer: Callable[..., Mapping[str, Any]] = materialize_verified_cams,
    store_factory: Callable[[Path], SQLiteObjectStore] = SQLiteObjectStore,
    publisher_factory: Callable[[SQLiteObjectStore, Catalog], ContractV1Publisher] = (
        ContractV1Publisher
    ),
    reader_factory: Callable[..., Any] = PublishedRunsObjectReader,
    server_factory: Callable[..., Any] = make_server,
    clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
) -> LocalContractV1Service:
    """Publish ICON and one atomic CAMS family, then serve verified objects."""

    selected = _normalized_config(config)
    # No path argument is passed: load_catalog() must use the authoritative
    # ISTAT/IRDAT catalog, never the explicit legacy fixture loader.
    catalog = catalog_loader()
    if not isinstance(catalog, Catalog):
        raise ContractV1EntrypointError("catalog loader did not return a contract catalog")
    published_at = selected.published_at or _utc_now(clock)

    object_store: SQLiteObjectStore | None = None
    server = None
    try:
        object_store = store_factory(selected.object_db)
        publisher = publisher_factory(object_store, catalog)
        publications: dict[str, Any] = {}
        latest: dict[str, Mapping[str, Any]] = {}
        statuses: dict[str, Mapping[str, Any]] = {}
        try:
            icon_bundle = icon_materializer(
                catalog=catalog,
                icon_archive=selected.icon_payload,
                icon_report=selected.icon_report,
            )
            if (
                not isinstance(icon_bundle, Mapping)
                or not _catalog_matches(catalog, icon_bundle.get("catalog"))
            ):
                raise ContractV1EntrypointError(
                    "materialized ICON family does not match the authoritative catalog"
                )
            _publish_provider_bundle(
                publisher,
                ICON_PROVIDER,
                icon_bundle.get("icon"),
                published_at=published_at,
                publications=publications,
                latest=latest,
                statuses=statuses,
            )
        except _PROVIDER_FAILURES as error:
            _retain_verified_latest(
                publisher,
                ICON_PROVIDER,
                cause=error,
                latest=latest,
                statuses=statuses,
            )

        try:
            cams_bundle = cams_materializer(
                catalog=catalog,
                cams_payload=selected.cams_payload,
                cams_report=selected.cams_report,
            )
            if (
                not isinstance(cams_bundle, Mapping)
                or not _catalog_matches(catalog, cams_bundle.get("catalog"))
            ):
                raise ContractV1EntrypointError(
                    "materialized CAMS family does not match the authoritative catalog"
                )
            _publish_cams_family(
                publisher,
                cams_bundle,
                published_at=published_at,
                publications=publications,
                latest=latest,
                statuses=statuses,
            )
        except _PROVIDER_FAILURES as error:
            _retain_verified_cams_family(
                publisher,
                cause=error,
                latest=latest,
                statuses=statuses,
            )

        if not latest:
            raise ContractV1EntrypointError(
                "no provider has a completely verified run to serve"
            )

        # Socket creation is deliberately last. Every selectable provider now
        # has a fully verified latest pointer; failed candidate runs remain
        # unreferenced and cannot become latest.
        selected_providers = tuple(
            provider
            for provider in (ICON_PROVIDER, CAMS_PROVIDER, CAMS_POLLEN_PROVIDER)
            if provider in latest
        )
        serving_reader = reader_factory(
            object_store,
            catalog,
            providers=selected_providers,
        )
        server = server_factory(serving_reader, port=selected.port)
        address = getattr(server, "server_address", None)
        if (
            not isinstance(address, tuple)
            or len(address) < 2
            or address[0] != LOOPBACK_HOST
        ):
            raise ContractV1EntrypointError("data plane did not bind IPv4 loopback")
        return LocalContractV1Service(
            catalog=catalog,
            object_store=object_store,
            server=server,
            publications=publications,
            latest=latest,
            provider_statuses=statuses,
        )
    except Exception:
        if server is not None:
            server.server_close()
        if object_store is not None:
            object_store.close()
        raise


def serve_service(
    service: LocalContractV1Service,
    *,
    emit: Callable[[str], None] = print,
) -> None:
    """Serve until Ctrl+C, closing the listening socket deterministically."""

    emit(
        f"Catalogo ufficiale: {service.catalog.version} "
        f"({service.catalog.municipality_count} Comuni)"
    )
    for provider in (ICON_PROVIDER, CAMS_PROVIDER, CAMS_POLLEN_PROVIDER):
        status = service.provider_statuses[provider]
        if provider in service.latest:
            emit(
                f"{provider}: {status['active_run_id']} · {status['status']}"
            )
        else:
            emit(f"{provider}: non disponibile · {status['reason']}")
    emit(f"Data plane locale read-only: {service.url}")
    emit("Arresto: Ctrl+C. Nessun cloud, OSMER o allerta viene modificato.")
    try:
        service.server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        service.close()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--icon-payload", required=True, type=Path)
    parser.add_argument("--icon-report", required=True, type=Path)
    parser.add_argument("--cams-payload", required=True, type=Path)
    parser.add_argument("--cams-report", required=True, type=Path)
    parser.add_argument("--object-db", required=True, type=Path)
    parser.add_argument("--port", required=True, type=int)
    parser.add_argument(
        "--published-at",
        help="UTC canonico opzionale per test riproducibili; altrimenti usa l'ora UTC corrente",
    )
    return parser


def parse_config(argv: Sequence[str] | None = None) -> EntrypointConfig:
    args = build_parser().parse_args(argv)
    return EntrypointConfig(
        icon_payload=args.icon_payload,
        icon_report=args.icon_report,
        cams_payload=args.cams_payload,
        cams_report=args.cams_report,
        object_db=args.object_db,
        port=args.port,
        published_at=args.published_at,
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    config = EntrypointConfig(
        icon_payload=args.icon_payload,
        icon_report=args.icon_report,
        cams_payload=args.cams_payload,
        cams_report=args.cams_report,
        object_db=args.object_db,
        port=args.port,
        published_at=args.published_at,
    )
    try:
        service = build_service(config)
    except (
        ContractError,
        SnapshotMaterializationError,
        ContractPublicationError,
        ObjectStoreError,
        ContractV1EntrypointError,
        OSError,
        sqlite3.Error,
        ValueError,
    ) as error:
        parser.error(str(error))
    serve_service(service)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
