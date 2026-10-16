"""Independent pilot v2 publication: immutable runs, full readback, pointer CAS.

The public pointer retains the experimental local-pilot wire contract so the
same national clients work over the separate HTTPS transport. No v1 path is
read or written. A manifest is a durable, fully verified publication checkpoint.
"""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import json
import re

from local_pipeline import national_icon_bundle as contract
from local_pipeline.sqlite_object_store import ObjectNotFound, ObjectStoreError, PreconditionFailed
from serve_national_bundle_v2 import VerifiedNationalBundleReader, _catalog_reference

PREFIX = "weather/v2/icon2i/"
POINTER_KEY = PREFIX + "pilot.json"
RUN_ID = re.compile(r"^\d{8}T\d{6}Z$")
SHA256 = re.compile(r"^[a-f0-9]{64}$")
POINTER_FIELDS = {"schema_version", "kind", "contract", "status", "source_run_id", "run_at",
                  "generated_at", "catalog", "grid", "metadata_sha256", "manifest", "index",
                  "published_at", "previous", "revision"}


def utc(value):
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise ValueError("aware publication clock required")
    return value.astimezone(timezone.utc).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_document(body, *, maximum=16384):
    if not isinstance(body, bytes) or not 0 < len(body) <= maximum:
        raise ValueError("invalid national document size")
    value = json.loads(body)
    if not isinstance(value, dict) or contract.canonical_json_bytes(value) != body:
        raise ValueError("noncanonical national document")
    return value


def descriptor_for(bundle):
    return {"path": bundle.manifest_path, "json_bytes": len(bundle.manifest_json),
            "sha256": contract.sha256_hex(bundle.manifest_json)}


def validate_descriptor(value, run_id):
    if not isinstance(value, dict) or set(value) != {"path", "json_bytes", "sha256"}:
        raise ValueError("invalid national manifest descriptor")
    if not isinstance(run_id, str) or not RUN_ID.fullmatch(run_id):
        raise ValueError("invalid national run identity")
    if (value["path"] != f"runs/{run_id}/manifest.json"
            or type(value["json_bytes"]) is not int
            or not 0 < value["json_bytes"] <= contract.MAX_MANIFEST_JSON_BYTES
            or not isinstance(value["sha256"], str) or not SHA256.fullmatch(value["sha256"])):
        raise ValueError("invalid national manifest descriptor")
    return value


def read_pointer(store, catalog):
    obj = store.get(POINTER_KEY)
    pointer = parse_document(obj.body)
    if (set(pointer) != POINTER_FIELDS or pointer["schema_version"] != 1
            or pointer["kind"] != "meteofriul.weather.icon.national.local_pilot_pointer"
            or pointer["contract"] != contract.CONTRACT_ID
            or pointer["status"] != "experimental_local_pilot_only"
            or pointer["catalog"] != _catalog_reference(catalog)
            or type(pointer["revision"]) is not int or pointer["revision"] < 1):
        raise ValueError("invalid national pilot pointer")
    validate_descriptor(pointer["manifest"], pointer["source_run_id"])
    if contract.canonical_run_id(pointer["run_at"]) != pointer["source_run_id"]:
        raise ValueError("national pointer run time differs")
    for field in ("generated_at", "published_at"):
        if utc(datetime.strptime(pointer[field], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)) != pointer[field]:
            raise ValueError("invalid pointer time")
    previous = pointer["previous"]
    if previous is not None:
        if not isinstance(previous, dict) or set(previous) != {"source_run_id", "manifest"}:
            raise ValueError("invalid previous national run")
        validate_descriptor(previous["manifest"], previous["source_run_id"])
        if previous["source_run_id"] >= pointer["source_run_id"]:
            raise ValueError("previous national run is not older")
    return pointer, obj.etag


def _checked(body, descriptor):
    if len(body) != descriptor["json_bytes"] or contract.sha256_hex(body) != descriptor["sha256"]:
        raise ValueError("national object failed descriptor integrity")
    return body


def reader_for_bundle(bundle, catalog):
    contract.validate_national_icon_bundle(bundle)
    manifest = json.loads(bundle.manifest_json)
    if manifest["catalog"] != _catalog_reference(catalog):
        raise ValueError("national bundle catalog differs")
    blocks = {}
    for _path, payload in bundle.block_documents:
        block = json.loads(payload)
        blocks[block["block_id"]] = block
    return VerifiedNationalBundleReader(bundle=bundle, manifest=manifest,
        index=json.loads(bundle.index_json), blocks=blocks, catalog=catalog)


def load_run(store, descriptor, catalog):
    match = re.fullmatch(r"runs/(\d{8}T\d{6}Z)/manifest.json", str(descriptor.get("path", "")))
    if not match:
        raise ValueError("invalid national manifest path")
    validate_descriptor(descriptor, match[1])
    manifest_bytes = _checked(store.get(PREFIX + descriptor["path"]).body, descriptor)
    manifest = contract._validate_manifest(parse_document(manifest_bytes, maximum=contract.MAX_MANIFEST_JSON_BYTES))
    if manifest["source_run_id"] != match[1] or manifest["catalog"] != _catalog_reference(catalog):
        raise ValueError("national manifest identity differs")
    descriptors = [manifest["index"], *manifest["blocks"]]
    if (manifest["index"]["json_bytes"] > contract.MAX_INDEX_JSON_BYTES
            or any(item["json_bytes"] > contract.MAX_BLOCK_JSON_BYTES for item in manifest["blocks"])):
        raise ValueError("national object exceeds byte budget")
    if sum(item["json_bytes"] for item in descriptors) + len(manifest_bytes) > contract.MAX_BUNDLE_JSON_BYTES:
        raise ValueError("national bundle exceeds byte budget")
    def fetch(item):
        return _checked(store.get(PREFIX + item["path"]).body, item)
    with ThreadPoolExecutor(max_workers=8) as pool:
        payloads = list(pool.map(fetch, descriptors))
    bundle = contract.NationalIconBundle(descriptor["path"], manifest_bytes,
        manifest["index"]["path"], payloads[0],
        tuple((item["path"], body) for item, body in zip(manifest["blocks"], payloads[1:], strict=True)))
    return bundle, reader_for_bundle(bundle, catalog)


def verify_pointer_reader(pointer, reader):
    if any(pointer[key] != value for key, value in reader.pointer.items()):
        raise ValueError("national pointer differs from verified manifest")


def require_current_coverage(manifest, now):
    if now.tzinfo is None:
        raise ValueError("aware freshness clock required")
    run = datetime.strptime(manifest["run_at"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    last = run + timedelta(hours=manifest["time_step_count"] - 1)
    # Twelve hourly rows at or after now, matching the pilot client policy.
    if now < run or now > last - timedelta(hours=11):
        raise ValueError("national run lacks current sample or twelve future hours")


def create_or_verify(store, key, body):
    """Never overwrite immutable data, including after an uncertain response."""
    try:
        store.put(key, body, content_type="application/json")
    except ObjectStoreError:
        # A lost success response and a create-only conflict are reconciled by bytes.
        if store.get(key).body != body:
            raise ValueError("conflicting immutable national object")
    if store.get(key).body != body:
        raise ValueError("national immutable write failed readback")


def publish_bundle(store, bundle, catalog, *, now, clock=None):
    reader = reader_for_bundle(bundle, catalog)
    require_current_coverage(reader.manifest, now)
    try:
        old, etag = read_pointer(store, catalog)
    except ObjectNotFound:
        old, etag = None, None
    if old is not None and old["source_run_id"] >= reader.source_run_id:
        if old["source_run_id"] != reader.source_run_id or old["manifest"] != descriptor_for(bundle):
            raise ValueError("national pointer regression or conflicting run")
        _bundle, verified = load_run(store, old["manifest"], catalog)
        verify_pointer_reader(old, verified)
        return old
    # Independent immutable objects may be uploaded concurrently; the manifest
    # remains a strict barrier after every object and its readback has succeeded.
    def upload(item):
        path, body = item
        create_or_verify(store, PREFIX + path, body)
    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(upload, bundle.publication_order()[:-1]))
    upload(bundle.publication_order()[-1])
    _bundle, verified = load_run(store, descriptor_for(bundle), catalog)
    committed_at = clock() if clock is not None else now
    require_current_coverage(verified.manifest, committed_at)
    pointer = {**dict(verified.pointer), "published_at": utc(committed_at),
        "revision": 1 if old is None else old["revision"] + 1,
        "previous": None if old is None else {"source_run_id": old["source_run_id"], "manifest": old["manifest"]}}
    body = contract.canonical_json_bytes(pointer)
    try:
        store.compare_and_swap(POINTER_KEY, body, expected_etag=etag, content_type="application/json")
    except ObjectStoreError:
        observed, _ = read_pointer(store, catalog)
        if observed != pointer:
            raise
    observed, _ = read_pointer(store, catalog)
    if observed != pointer:
        raise PreconditionFailed(POINTER_KEY, "national pointer changed during readback")
    return observed
