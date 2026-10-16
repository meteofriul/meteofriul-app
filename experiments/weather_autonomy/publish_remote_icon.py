"""Publish validated ICON artifacts through remote storage ports.

Not an acquisition command or scheduler. This boundary keeps the local SQLite
runner unchanged and persists the publication identity in remote state first.
The caller must supply separate private state and data stores with scoped IAM.
"""
from local_pipeline.contract_v1 import load_catalog
from local_pipeline.contract_publisher import ContractV1Publisher
from local_pipeline.job_entrypoints import (
    IconJobInputs, execute_icon_job, execute_icon_recovery, prepare_icon_publication,
)
from local_pipeline.job_outcomes import JobKind
from local_pipeline.publication_intent import PublicationIntent
from local_pipeline.remote_publication_intent import (
    resolve_remote_publication_intent, read_remote_publication_intent,
)
from local_pipeline.operational_diagnostics import emit, phase


def publish_remote_icon(*, payload, report, published_at, state_store, data_store):
    if state_store is data_store:
        raise ValueError("private state and data stores must be separate")
    catalog = load_catalog()
    with phase("validation", provider="icon"):
        prepared = prepare_icon_publication(payload=payload, report=report, catalog=catalog)
    emit("validation_result", provider="icon", source_run_id=prepared.source_run_id,
         status="validated", validated_count=len(prepared.documents))
    with phase("publication_intent", provider="icon", source_run_id=prepared.source_run_id):
        resolution = resolve_remote_publication_intent(state_store, PublicationIntent(
            job=JobKind.ICON, source_run_id=prepared.source_run_id,
            published_at=published_at,
            input_fingerprint_sha256=prepared.input_fingerprint_sha256,
        ))
    return execute_icon_job(IconJobInputs(
        payload=payload, report=report, published_at=resolution.intent.published_at,
        source_run_id=prepared.source_run_id,
        input_fingerprint_sha256=prepared.input_fingerprint_sha256,
        prepared=prepared,
    ), catalog=catalog, publisher=ContractV1Publisher(data_store, catalog))


def recover_remote_icon(*, source_run_id, state_store, data_store):
    """Recovery-only boundary: read original intent and the stored ICON snapshot."""
    if state_store is data_store:
        raise ValueError("private state and data stores must be separate")
    intent = read_remote_publication_intent(
        state_store, job=JobKind.ICON, source_run_id=source_run_id,
    )
    return execute_icon_recovery(
        intent=intent, publisher=ContractV1Publisher(data_store, load_catalog()),
    )
