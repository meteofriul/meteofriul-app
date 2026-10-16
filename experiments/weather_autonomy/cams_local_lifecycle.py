"""Advance one fully local CAMS run through durable validation/publication.

This command is offline: it reads only explicit local artifacts and writes two
separate SQLite files (lifecycle state and the local object-store simulator).
It never imports ADS credentials, submits a request, calls cloud services,
changes ICON, or starts an HTTP server.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import json

from local_pipeline.cams_lifecycle import (
    CamsLifecycleError,
    CamsLifecyclePaths,
    advance_cams_lifecycle,
)
from local_pipeline.contract_publisher import (
    ContractPublicationError,
    ContractV1Publisher,
)
from local_pipeline.contract_v1 import ContractError, load_catalog
from local_pipeline.sqlite_object_store import ObjectStoreError, SQLiteObjectStore
from local_pipeline.sqlite_state import SqliteStateStore


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifacts-directory", required=True, type=Path)
    parser.add_argument("--decoded-payload", required=True, type=Path)
    parser.add_argument("--decode-report", required=True, type=Path)
    parser.add_argument("--state-db", required=True, type=Path)
    parser.add_argument("--object-db", required=True, type=Path)
    parser.add_argument("--owner-id", required=True)
    parser.add_argument(
        "--published-at",
        required=True,
        help="Timestamp UTC canonico e stabile, per esempio 2026-09-04T12:30:00Z",
    )
    return parser


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    state_path = args.state_db.expanduser().resolve()
    object_path = args.object_db.expanduser().resolve()
    if state_path == object_path:
        parser.error("State DB and object DB must be distinct files")
    if not state_path.parent.is_dir() or not object_path.parent.is_dir():
        parser.error("Both SQLite parent directories must already exist")

    try:
        catalog = load_catalog()
        with SqliteStateStore(state_path) as state_store, SQLiteObjectStore(
            object_path,
            state_database_path=state_path,
        ) as object_store:
            publisher = ContractV1Publisher(object_store, catalog)
            result = advance_cams_lifecycle(
                paths=CamsLifecyclePaths(
                    args.artifacts_directory,
                    args.decoded_payload,
                    args.decode_report,
                ),
                catalog=catalog,
                state_store=state_store,
                publisher=publisher,
                owner_id=args.owner_id,
                published_at=args.published_at,
            )
    except (
        CamsLifecycleError,
        ContractError,
        ContractPublicationError,
        ObjectStoreError,
        OSError,
        ValueError,
    ) as error:
        print(
            json.dumps(
                {
                    "status": "stopped",
                    "error_type": type(error).__name__,
                    "safe_reason": str(error),
                },
                ensure_ascii=False,
                separators=(",", ":"),
            )
        )
        return 1

    print(
        json.dumps(
            {
                "status": "published",
                "source_run_id": result.key.source_run_id,
                "durable_state": result.record.state.value,
                "request_sha256": result.key.request_hash,
                "validation_sha256": result.validation_sha256,
                "publication_sha256": result.publication_sha256,
                "core_stage_idempotent": result.core_stage.idempotent,
                "pollen_stage_idempotent": result.pollen_stage.idempotent,
                "family_idempotent": result.family_publication.idempotent,
                "family_latest_updated": result.family_publication.latest_updated,
                "family_revision": result.family_publication.revision,
            },
            ensure_ascii=False,
            separators=(",", ":"),
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
