"""Separate national pilot job; two bounded dispatch slots/day, no v1 writes.

Fresh acquisition reuses the real 14 x 73 GRIB decoder and approved national
points. A frozen per-run intent makes an interrupted immutable publication
reproducible. A complete manifest is reused without another source download.
Incomplete source acquisition may be retried in the next slot; old latest is
never advanced unless all national objects pass readback.
"""
from datetime import datetime, timezone
import json
import os
import re

from national_cloud_assets import PROJECT, load_inputs
from national_cloud_publication import (PREFIX, create_or_verify, descriptor_for,
    load_run, parse_document, publish_bundle, read_pointer, require_current_coverage,
    utc, verify_pointer_reader)
from local_pipeline.national_icon_bundle import canonical_json_bytes, canonical_run_id
from local_pipeline.national_icon_bundle import sha256_hex
from local_pipeline.operational_diagnostics import phase
from local_pipeline.sqlite_object_store import ObjectNotFound, PreconditionFailed

STATE_PREFIX = "state/national-icon/"


def acquire_real_bundle(*, catalog, points, run, generated_at, now):
    from benchmark_national_icon_real import acquire_real_source, build_real_bundle, build_mapping_artifact
    snapshot = acquire_real_source(forecast_points=points, run=run, now=now)
    # Runtime measurements are not stable source evidence. Exclude them from the
    # immutable mapping so a retry with identical GRIB bytes reproduces it.
    for provenance in snapshot["provenance"].values():
        provenance.pop("elapsed_seconds", None)
    bundle = build_real_bundle(snapshot=snapshot, catalog=catalog, generated_at=generated_at)
    mapping = build_mapping_artifact(snapshot=snapshot, catalog=catalog, generated_at=generated_at)
    return bundle, mapping


def record_preparation(state, bundle, mapping, catalog, points):
    run_id = json.loads(bundle.manifest_json)["source_run_id"]
    root = STATE_PREFIX + f"runs/{run_id}/"
    mapping_bytes = canonical_json_bytes(mapping)
    create_or_verify(state, root + "mapping.json", mapping_bytes)
    prepared = {"schema_version": 1, "source_run_id": run_id, "manifest": descriptor_for(bundle),
        "mapping_sha256": sha256_hex(mapping_bytes), "catalog_sha256": catalog["catalog_sha256"],
        "points_sha256": points["artifact_sha256"]}
    create_or_verify(state, root + "prepared.json", canonical_json_bytes(prepared))


def verify_preparation(state, bundle, catalog, points):
    run_id = json.loads(bundle.manifest_json)["source_run_id"]
    root = STATE_PREFIX + f"runs/{run_id}/"
    prepared = parse_document(state.get(root + "prepared.json").body)
    expected = {"schema_version": 1, "source_run_id": run_id, "manifest": descriptor_for(bundle),
        "mapping_sha256": sha256_hex(state.get(root + "mapping.json").body),
        "catalog_sha256": catalog["catalog_sha256"], "points_sha256": points["artifact_sha256"]}
    if prepared != expected:
        raise ValueError("national checkpoint evidence differs")


def discover_run(now, high_water):
    from run_pilot import StreamingReader, discover_complete_run, SourceRunNotAdvanced
    try:
        run, _time, _axis, _urls = discover_complete_run(StreamingReader(), now, source_run_high_water=high_water)
        return run
    except SourceRunNotAdvanced:
        return None


def run_once(state, data, catalog, points, *, now, execution, acquire=acquire_real_bundle, discover=discover_run, clock=None):
    from local_pipeline.icon_recovery import enabled
    if enabled():
        return run_automatic(state, data, catalog, points, now=now, execution=execution,
                             acquire=acquire, discover=discover, clock=clock)
    slot = now.strftime("%Y%m%d") + ("-am" if now.hour < 12 else "-pm")
    claim_key = STATE_PREFIX + f"dispatch/{slot}.json"
    claim = canonical_json_bytes({"schema_version": 1, "slot": slot, "execution": execution})
    try:
        state.put(claim_key, claim, content_type="application/json")
    except PreconditionFailed:
        if state.get(claim_key).body != claim:
            return {"status": "no_op", "reason": "slot_already_claimed"}
    try:
        pointer, _ = read_pointer(data, catalog)
    except ObjectNotFound:
        pointer, high_water = None, None
    else:
        # Missing/corrupt referenced blocks must not become an empty publication.
        _bundle, existing = load_run(data, pointer["manifest"], catalog)
        verify_pointer_reader(pointer, existing)
        high_water = pointer["source_run_id"]
    run = discover(now, high_water)
    if run is None:
        if pointer is None:
            raise ValueError("no national run published or discovered")
        require_current_coverage(existing.manifest, now)
        return {"status": "no_op", "reason": "source_not_advanced", "source_run_id": high_water}
    run_time = datetime.strptime(run, "%Y%m%d%H").replace(tzinfo=timezone.utc)
    run_id = canonical_run_id(utc(run_time))
    if high_water is not None and run_id <= high_water:
        raise ValueError("national discovery attempted a run regression")
    intent_key = STATE_PREFIX + f"runs/{run_id}/intent.json"
    intent = {"schema_version": 1, "source_run_id": run_id, "generated_at": utc(now),
        "catalog_sha256": catalog["catalog_sha256"], "points_sha256": points["artifact_sha256"]}
    try:
        state.put(intent_key, canonical_json_bytes(intent), content_type="application/json")
    except PreconditionFailed:
        saved = parse_document(state.get(intent_key).body)
        if set(saved) != set(intent) or any(saved[k] != v for k, v in intent.items() if k != "generated_at"):
            raise ValueError("national acquisition intent differs")
        datetime.strptime(saved["generated_at"], "%Y-%m-%dT%H:%M:%SZ")
        intent = saved
    manifest_key = PREFIX + f"runs/{run_id}/manifest.json"
    try:
        manifest_obj = data.get(manifest_key)
    except ObjectNotFound:
        with phase("national_acquisition", provider="icon", source_run_id=run_id):
            bundle, mapping = acquire(catalog=catalog, points=points, run=run,
                generated_at=intent["generated_at"], now=now)
        if json.loads(bundle.manifest_json)["source_run_id"] != run_id:
            raise ValueError("acquisition returned a different national run")
        # Mapping/provenance is private; the public reader can never request state.
        record_preparation(state, bundle, mapping, catalog, points)
    else:
        descriptor = {"path": f"runs/{run_id}/manifest.json", "json_bytes": manifest_obj.size,
            "sha256": manifest_obj.sha256}
        bundle, _reader = load_run(data, descriptor, catalog)
        verify_preparation(state, bundle, catalog, points)
    with phase("national_publication", provider="icon", source_run_id=run_id):
        pointer = publish_bundle(data, bundle, catalog, now=now, clock=clock)
    return {"status": "published", "source_run_id": pointer["source_run_id"],
        "manifest_sha256": pointer["manifest"]["sha256"], "municipality_count": pointer["catalog"]["municipality_count"]}


def run_automatic(state, data, catalog, points, *, now, execution, acquire, discover, clock=None):
    """Opt-in recovery; complete immutable manifests remain the checkpoint."""
    from local_pipeline.icon_recovery import Recovery, FenceLost, discovery, transient, result

    try:
        try:
            pointer, _ = read_pointer(data, catalog)
        except ObjectNotFound:
            pointer = None
        verified_manifests = {}
        if pointer is not None:
            _bundle, existing = load_run(data, pointer["manifest"], catalog)
            verify_pointer_reader(pointer, existing)
            verified_manifests[canonical_json_bytes(pointer["manifest"])] = existing
        high_water = pointer["source_run_id"] if pointer else None

        def verify(cycle):
            current, _ = read_pointer(data, catalog)
            descriptor_key = canonical_json_bytes(current["manifest"])
            reader = verified_manifests.get(descriptor_key)
            if reader is None:
                _bundle, reader = load_run(data, current["manifest"], catalog)
                verified_manifests[descriptor_key] = reader
            verify_pointer_reader(current, reader)
            return current["source_run_id"] >= cycle

        def checkpoint(cycle, _slot):
            try:
                manifest = data.get(PREFIX + f"runs/{cycle}/manifest.json")
            except ObjectNotFound:
                return None
            descriptor = {"path": f"runs/{cycle}/manifest.json", "json_bytes": manifest.size, "sha256": manifest.sha256}
            frozen, _reader = load_run(data, descriptor, catalog)
            verify_preparation(state, frozen, catalog, points)
            return frozen

        def freeze(cycle, slot):
            run = datetime.strptime(cycle, "%Y%m%dT%H%M%SZ").strftime("%Y%m%d%H")
            intent_key = STATE_PREFIX + f"runs/{cycle}/intent.json"
            intent = {"schema_version": 1, "source_run_id": cycle, "generated_at": utc(now),
                "catalog_sha256": catalog["catalog_sha256"], "points_sha256": points["artifact_sha256"]}
            try:
                state.put(intent_key, canonical_json_bytes(intent), content_type="application/json")
            except PreconditionFailed:
                saved = parse_document(state.get(intent_key).body)
                if set(saved) != set(intent) or any(saved[key] != value for key, value in intent.items() if key != "generated_at"):
                    raise ValueError("national acquisition intent differs")
                datetime.strptime(saved["generated_at"], "%Y-%m-%dT%H:%M:%SZ")
                intent = saved
            with phase("national_acquisition", provider="icon", source_run_id=cycle):
                frozen, mapping = acquire(catalog=catalog, points=points, run=run,
                    generated_at=intent["generated_at"], now=now)
            if json.loads(frozen.manifest_json)["source_run_id"] != cycle:
                raise ValueError("national acquisition changed the discovered cycle")
            # Validate the entire in-memory bundle before staging any public byte.
            from national_cloud_publication import reader_for_bundle
            reader_for_bundle(frozen, catalog)
            record_preparation(state, frozen, mapping, catalog, points)
            # Pointer is untouched. Manifest-last is the existing atomic boundary
            # after which another execution may resume without a GRIB download.
            for path, body in frozen.publication_order():
                create_or_verify(data, PREFIX + path, body)
            return checkpoint(cycle, slot)

        def publish(frozen):
            current = publish_bundle(data, frozen, catalog, now=now, clock=clock)
            verified_manifests.clear()  # Final readback is fresh after pointer publication.
            return result("published", "publication_committed", current["source_run_id"])

        def legacy():
            slot = now.strftime("%Y%m%d") + ("-am" if now.hour < 12 else "-pm")
            try:
                state.get(STATE_PREFIX + f"dispatch/{slot}.json")
            except ObjectNotFound:
                return None
            cycle = now.strftime("%Y%m%dT") + ("000000Z" if now.hour < 12 else "120000Z")
            frozen = checkpoint(cycle, slot)
            return {"slot": slot, "source_run_id": cycle, "checkpoint": frozen}

        probe = (lambda water: discovery(now, water)) if discover is discover_run else (lambda water: discover(now, water))
        return Recovery(state, "national").run(now=now, execution=execution, high_water=high_water,
            verified_run=high_water, discover=probe, checkpoint=checkpoint, acquire=freeze,
            publish=publish, verify=verify, legacy=legacy)
    except FenceLost:
        return result("in_progress", "recovery_owner_changed")
    except Exception as error:
        return result("pending" if transient(error) else "manual_review",
                      "national_transport_pending" if transient(error) else "national_recovery_invalid")


def run():
    expected_job = os.environ.get("WEATHER_NATIONAL_JOB_NAME", "pilot-national-icon")
    acquisition = os.environ.get("WEATHER_NATIONAL_ACQUISITION", os.environ.get("PILOT_NATIONAL_ACQUISITION"))
    if (os.environ.get("GOOGLE_CLOUD_PROJECT") != PROJECT
            or os.environ.get("CLOUD_RUN_JOB") != expected_job
            or acquisition not in {"approved", "experimental-approved"}):
        raise ValueError("explicit isolated national weather job required")
    execution = os.environ.get("CLOUD_RUN_EXECUTION", "")
    if not re.fullmatch(re.escape(expected_job) + r"-[a-z0-9-]+", execution):
        raise ValueError("national job execution identity required")
    catalog, points = load_inputs()
    from google.cloud import storage
    from local_pipeline.gcs_object_store import GCSObjectStore
    client = storage.Client(project=PROJECT)
    state_bucket = os.environ.get("WEATHER_STATE_BUCKET", PROJECT + "-state")
    data_bucket = os.environ.get("WEATHER_DATA_BUCKET", PROJECT + "-data")
    result = run_once(GCSObjectStore(client.bucket(state_bucket)),
        GCSObjectStore(client.bucket(data_bucket)), catalog, points,
        now=datetime.now(timezone.utc), execution=execution, clock=lambda: datetime.now(timezone.utc))
    print(json.dumps(result, sort_keys=True), flush=True)
    if result.get("status") not in {"published", "no_op"}:
        raise RuntimeError("national ICON publication did not complete; inspect structured status")
    return result


if __name__ == "__main__":
    run()
