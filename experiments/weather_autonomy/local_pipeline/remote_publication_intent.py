"""Durable publication identity on an injected conditional object store.

An ambiguous write is never followed by a blind retry. A later invocation
reads the same key and reuses the original publication time.
"""
from .publication_intent import (
    MAX_INTENT_BYTES, PublicationIntent, PublicationIntentResolution,
    PublicationIntentConflict, PublicationIntentCorruption,
    _record_from_document, _strict_json,
    _job, _source_run_id,
)
from .sqlite_object_store import ObjectNotFound, PreconditionFailed


def read_remote_publication_intent(store, *, job, source_run_id):
    """Read a frozen identity without creating or modifying any state."""
    job, source_run_id = _job(job), _source_run_id(source_run_id)
    raw = store.get(f"state/publication/{job.value}/{source_run_id}.json").body
    if not 1 <= len(raw) <= MAX_INTENT_BYTES:
        raise PublicationIntentCorruption("invalid remote intent size")
    record = _record_from_document(_strict_json(raw))
    if record.canonical_bytes() != raw:
        raise PublicationIntentCorruption("non-canonical remote intent")
    if (record.job, record.source_run_id) != (job, source_run_id):
        raise PublicationIntentConflict("remote publication identity conflict")
    return record


def resolve_remote_publication_intent(store, candidate: PublicationIntent):
    key = f"state/publication/{candidate.job.value}/{candidate.source_run_id}.json"

    def read():
        record = read_remote_publication_intent(
            store, job=candidate.job, source_run_id=candidate.source_run_id,
        )
        if (record.job, record.source_run_id, record.input_fingerprint_sha256) != (
                candidate.job, candidate.source_run_id, candidate.input_fingerprint_sha256):
            raise PublicationIntentConflict("remote publication input conflict")
        return record

    try:
        return PublicationIntentResolution(read(), reused=True)
    except ObjectNotFound:
        pass
    try:
        store.put(key, candidate.canonical_bytes(), content_type="application/json")
    except PreconditionFailed:
        return PublicationIntentResolution(read(), reused=True)
    # Readback validates persistence before any public objects are written.
    return PublicationIntentResolution(read(), reused=False)
