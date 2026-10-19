"""Create-only, bounded ICON publication checkpoints in the existing state prefix.

These are materialized, validated contract documents, not an acquisition cache.
The gzip object is atomic: an interrupted upload cannot expose half a checkpoint.
Every resume authenticates the frozen intent, catalog and all municipality bytes.
"""
from dataclasses import dataclass
import gzip
import hashlib
import io
import re

from .contract_v1 import ICON_PROVIDER, canonical_json_bytes, validate_run_manifest
from .job_entrypoints import PreparedIconPublication
from .job_outcomes import JobKind
from .publication_intent import (
    PublicationIntent, PublicationIntentCorruption, PublicationIntentConflict,
    _record_from_document, _strict_json,
)
from .sqlite_object_store import ObjectNotFound, PreconditionFailed
from .icon_quality import validate_source_quality

MAX_COMPRESSED_BYTES = 16 * 1024**2
MAX_EXPANDED_BYTES = 64 * 1024**2
_SLOT = re.compile(r"\d{8}-(?:am|pm)\Z")


@dataclass(frozen=True)
class IconCheckpoint:
    prepared: PreparedIconPublication
    intent: PublicationIntent
    sha256: str
    source_quality: dict | None = None


def checkpoint_key(slot):
    if not isinstance(slot, str) or not _SLOT.fullmatch(slot):
        raise PublicationIntentCorruption("invalid ICON checkpoint slot")
    return f"state/dispatch/icon/{slot}/checkpoint.json.gz"


def _validate(prepared, intent, catalog):
    if (intent.job is not JobKind.ICON
            or intent.source_run_id != prepared.source_run_id
            or intent.input_fingerprint_sha256 != prepared.input_fingerprint_sha256):
        raise PublicationIntentConflict("ICON checkpoint differs from publication intent")
    validate_run_manifest(prepared.manifest(), catalog, expected_provider=ICON_PROVIDER,
                          object_bodies=prepared.documents)


def encode_checkpoint(*, slot, prepared, intent, catalog, source_quality=None):
    checkpoint_key(slot)
    _validate(prepared, intent, catalog)
    envelope = {
        "schema_version": 1 if source_quality is None else 2, "kind": "meteofriul.icon.publication_checkpoint", "slot": slot,
        "intent": intent.as_document(), "manifest": prepared.manifest_bytes.decode("utf-8"),
        "documents": {key: value.decode("utf-8") for key, value in prepared.documents.items()},
    }
    if source_quality is not None:
        validate_source_quality(source_quality, source_run_id=intent.source_run_id)
        envelope["source_quality"] = source_quality
        envelope["source_quality_sha256"] = hashlib.sha256(canonical_json_bytes(source_quality)).hexdigest()
    raw = canonical_json_bytes(envelope)
    if len(raw) > MAX_EXPANDED_BYTES:
        raise PublicationIntentCorruption("ICON checkpoint expanded size exceeds limit")
    compressed = gzip.compress(raw, compresslevel=6, mtime=0)
    if len(compressed) > MAX_COMPRESSED_BYTES:
        raise PublicationIntentCorruption("ICON checkpoint compressed size exceeds limit")
    return compressed


def decode_checkpoint(body, *, slot, catalog):
    checkpoint_key(slot)
    if not isinstance(body, bytes) or not 1 <= len(body) <= MAX_COMPRESSED_BYTES:
        raise PublicationIntentCorruption("invalid ICON checkpoint size")
    try:
        with gzip.GzipFile(fileobj=io.BytesIO(body)) as stream:
            raw = stream.read(MAX_EXPANDED_BYTES + 1)
        if len(raw) > MAX_EXPANDED_BYTES:
            raise PublicationIntentCorruption("ICON checkpoint expanded size exceeds limit")
        value = _strict_json(raw)
        version = value.get("schema_version") if isinstance(value, dict) else None
        expected_keys = {"schema_version", "kind", "slot", "intent", "manifest", "documents"}
        if version == 2:
            expected_keys |= {"source_quality", "source_quality_sha256"}
        if (not isinstance(value, dict) or set(value) != expected_keys
                or version not in {1, 2}
                or value["kind"] != "meteofriul.icon.publication_checkpoint"
                or value["slot"] != slot or canonical_json_bytes(value) != raw
                or not isinstance(value["manifest"], str)
                or not isinstance(value["documents"], dict)
                or any(not isinstance(item, str) for item in value["documents"].values())):
            raise PublicationIntentCorruption("invalid ICON checkpoint envelope")
        intent = _record_from_document(value["intent"])
        prepared = PreparedIconPublication(
            source_run_id=intent.source_run_id,
            input_fingerprint_sha256=intent.input_fingerprint_sha256,
            documents={key: item.encode("utf-8") for key, item in value["documents"].items()},
            manifest_bytes=value["manifest"].encode("utf-8"),
        )
        _validate(prepared, intent, catalog)
        source_quality = value.get("source_quality")
        if version == 2:
            validate_source_quality(source_quality, source_run_id=intent.source_run_id)
            if hashlib.sha256(canonical_json_bytes(source_quality)).hexdigest() != value["source_quality_sha256"]:
                raise ValueError("ICON quality fingerprint mismatch")
    except (OSError, EOFError, UnicodeError, TypeError, ValueError) as error:
        raise PublicationIntentCorruption("ICON checkpoint cannot be authenticated") from error
    return IconCheckpoint(prepared, intent, hashlib.sha256(body).hexdigest(), source_quality)


def read_checkpoint(store, *, slot, catalog):
    try:
        stored = store.get(checkpoint_key(slot))
    except ObjectNotFound:
        return None
    if stored.content_type != "application/gzip" or stored.sha256 != hashlib.sha256(stored.body).hexdigest():
        raise PublicationIntentCorruption("ICON checkpoint storage integrity failed")
    return decode_checkpoint(stored.body, slot=slot, catalog=catalog)


def save_checkpoint(store, *, slot, prepared, intent, catalog, source_quality=None):
    body = encode_checkpoint(slot=slot, prepared=prepared, intent=intent, catalog=catalog, source_quality=source_quality)
    try:
        store.put(checkpoint_key(slot), body, content_type="application/gzip")
    except PreconditionFailed:
        pass
    observed = read_checkpoint(store, slot=slot, catalog=catalog)
    if observed is None or observed.sha256 != hashlib.sha256(body).hexdigest():
        raise PublicationIntentConflict("ICON checkpoint immutable conflict")
    return observed
