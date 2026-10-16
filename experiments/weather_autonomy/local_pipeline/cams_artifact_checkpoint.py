"""Private CAMS artifacts: bounded immutable chunks and one atomic descriptor.

No credentials, URLs, source acquisition or decoding live here. Every restored
byte is authenticated before any file is made available to the lifecycle gate.
"""
import hashlib
import re
from uuid import UUID

from cams_request_plan import DATASET, strict_json_loads
from .contract_v1 import canonical_json_bytes
from .sqlite_object_store import ObjectNotFound, PreconditionFailed

CHUNK_BYTES = 4 * 1024 * 1024
MAX_DESCRIPTOR_BYTES = 128 * 1024
FILE_LIMITS = {
    "download": {"source.grib": 64 * 1024**2, "source.grib.complete.json": 16 * 1024},
    "decoded": {"decoded.json": 64 * 1024**2, "decode-report.json": 4 * 1024**2},
    "prepared": {"prepared.json": 128 * 1024**2},
}
_SHA = re.compile(r"[a-f0-9]{64}\Z")
_PREFIX = re.compile(r"state/ads/\d{4}-\d{2}-\d{2}/[a-f0-9]{64}/\Z")


class CamsArtifactError(RuntimeError):
    """A private checkpoint cannot be trusted; never reacquire on this signal."""


class CamsArtifactConflict(CamsArtifactError):
    """One immutable checkpoint already identifies different exact bytes."""


def _digest(body):
    return hashlib.sha256(body).hexdigest()


def _arguments(prefix, stage, identity, bindings):
    if not isinstance(prefix, str) or not _PREFIX.fullmatch(prefix) or stage not in FILE_LIMITS:
        raise CamsArtifactError("Invalid CAMS artifact checkpoint namespace")
    if not isinstance(identity, dict) or set(identity) != {
        "dataset", "request_id", "run_date", "request_plan_sha256", "request_sha256",
    }:
        raise CamsArtifactError("Invalid CAMS artifact checkpoint identity")
    if (not all(isinstance(value, str) for value in identity.values())
            or identity["dataset"] != DATASET
            or prefix != f"state/ads/{identity['run_date']}/{identity['request_sha256']}/"
            or not _SHA.fullmatch(identity["request_plan_sha256"])):
        raise CamsArtifactError("Invalid CAMS artifact checkpoint identity")
    try:
        if str(UUID(identity["request_id"])) != identity["request_id"]:
            raise ValueError()
    except (ValueError, TypeError):
        raise CamsArtifactError("Invalid CAMS artifact checkpoint identity") from None
    expected = set() if stage == "download" else {"source_sha256", "catalog_sha256"}
    if (not isinstance(bindings, dict) or set(bindings) != expected
            or any(not isinstance(value, str) or not _SHA.fullmatch(value) for value in bindings.values())):
        raise CamsArtifactError("Invalid CAMS artifact checkpoint bindings")


def _read(store, key, maximum, content_type):
    stored = store.get(key)
    body = stored.body
    if (not isinstance(body, bytes) or not 1 <= len(body) <= maximum
            or stored.byte_length != len(body) or stored.sha256 != _digest(body)
            or stored.content_type != content_type):
        raise CamsArtifactError("CAMS artifact storage integrity failed")
    return body


def _put_exact(store, key, body, content_type):
    try:
        store.put(key, body, content_type=content_type)
    except PreconditionFailed:
        pass
    except Exception as original_error:
        # A lost response may follow a completed create. Confirm exact bytes;
        # otherwise retain the original typed transport error for the worker.
        try:
            observed = _read(store, key, len(body), content_type)
        except Exception:
            raise original_error
        if observed != body:
            raise CamsArtifactConflict("CAMS artifact immutable conflict")
        return
    if _read(store, key, len(body), content_type) != body:
        raise CamsArtifactConflict("CAMS artifact immutable conflict")


def save_artifacts(store, *, prefix, stage, identity, files, bindings=None):
    bindings = {} if bindings is None else bindings
    _arguments(prefix, stage, identity, bindings)
    limits = FILE_LIMITS[stage]
    if not isinstance(files, dict) or set(files) != set(limits):
        raise CamsArtifactError("CAMS artifact file allowlist differs")
    for name, maximum in limits.items():
        if not isinstance(files[name], bytes) or not 1 <= len(files[name]) <= maximum:
            raise CamsArtifactError("CAMS artifact file exceeds its byte limit")
    descriptors = {}
    for name in sorted(files):
        body = files[name]
        chunks = []
        for offset in range(0, len(body), CHUNK_BYTES):
            chunk = body[offset:offset + CHUNK_BYTES]
            digest = _digest(chunk)
            _put_exact(store, prefix + f"artifacts/chunks/{digest}.bin", chunk,
                       "application/octet-stream")
            chunks.append({"sha256": digest, "bytes": len(chunk)})
        descriptors[name] = {"sha256": _digest(body), "bytes": len(body), "chunks": chunks}
    descriptor = canonical_json_bytes({
        "schema_version": 1, "kind": "meteofriul.cams.artifact_checkpoint",
        "stage": stage, "identity": identity, "bindings": bindings, "files": descriptors,
    })
    if len(descriptor) > MAX_DESCRIPTOR_BYTES:
        raise CamsArtifactError("CAMS artifact descriptor exceeds its byte limit")
    # This create is the completion boundary: partial chunk uploads never
    # advertise a completed download/decoded checkpoint.
    _put_exact(store, prefix + f"artifacts/{stage}.json", descriptor, "application/json")


def read_artifacts(store, *, prefix, stage, identity, bindings=None):
    bindings = {} if bindings is None else bindings
    _arguments(prefix, stage, identity, bindings)
    try:
        raw = _read(store, prefix + f"artifacts/{stage}.json", MAX_DESCRIPTOR_BYTES, "application/json")
    except ObjectNotFound:
        return None
    try:
        record = strict_json_loads(raw)
        if (not isinstance(record, dict) or set(record) != {
                "schema_version", "kind", "stage", "identity", "bindings", "files"}
                or type(record["schema_version"]) is not int or record["schema_version"] != 1
                or record["kind"] != "meteofriul.cams.artifact_checkpoint"
                or record["stage"] != stage or record["identity"] != identity
                or record["bindings"] != bindings or canonical_json_bytes(record) != raw
                or not isinstance(record["files"], dict)
                or set(record["files"]) != set(FILE_LIMITS[stage])):
            raise ValueError()
        for name, desc in record["files"].items():
            if (not isinstance(desc, dict) or set(desc) != {"sha256", "bytes", "chunks"}
                    or not isinstance(desc["sha256"], str) or not _SHA.fullmatch(desc["sha256"])
                    or type(desc["bytes"]) is not int or not 1 <= desc["bytes"] <= FILE_LIMITS[stage][name]
                    or not isinstance(desc["chunks"], list)
                    or len(desc["chunks"]) != (desc["bytes"] + CHUNK_BYTES - 1) // CHUNK_BYTES):
                raise ValueError()
            for index, chunk in enumerate(desc["chunks"]):
                expected_bytes = min(CHUNK_BYTES, desc["bytes"] - index * CHUNK_BYTES)
                if (not isinstance(chunk, dict) or set(chunk) != {"sha256", "bytes"}
                        or not isinstance(chunk["sha256"], str) or not _SHA.fullmatch(chunk["sha256"])
                        or type(chunk["bytes"]) is not int or chunk["bytes"] != expected_bytes):
                    raise ValueError()
    except Exception as error:
        raise CamsArtifactError("CAMS artifact descriptor is invalid") from error
    files = {}
    for name, desc in record["files"].items():
        chunks = []
        for chunk in desc["chunks"]:
            try:
                body = _read(store, prefix + f"artifacts/chunks/{chunk['sha256']}.bin",
                             CHUNK_BYTES, "application/octet-stream")
            except ObjectNotFound as error:
                raise CamsArtifactError("CAMS artifact checkpoint is incomplete") from error
            if len(body) != chunk["bytes"] or _digest(body) != chunk["sha256"]:
                raise CamsArtifactError("CAMS artifact chunk hash differs")
            chunks.append(body)
        body = b"".join(chunks)
        if len(body) != desc["bytes"] or _digest(body) != desc["sha256"]:
            raise CamsArtifactError("CAMS artifact file hash differs")
        files[name] = body
    return files


def read_local_file(path, maximum):
    if path.is_symlink() or path.is_junction() or not path.is_file() or not 1 <= path.stat().st_size <= maximum:
        raise CamsArtifactError("Invalid CAMS checkpoint local file")
    with path.open("rb") as source:
        body = source.read(maximum + 1)
    if not 1 <= len(body) <= maximum:
        raise CamsArtifactError("CAMS checkpoint local file changed size")
    return body


def restore_local_file(path, body):
    if path.exists() or path.is_symlink():
        if read_local_file(path, len(body)) != body:
            raise CamsArtifactConflict("CAMS scratch artifact differs from checkpoint")
        return
    with path.open("xb") as target:
        target.write(body)
