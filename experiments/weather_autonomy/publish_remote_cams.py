"""Verified CAMS core/pollen publication using private remote state."""
import hashlib
from uuid import uuid4
from local_pipeline.cams_lifecycle import PreparedCamsRun, prepare_cams_lifecycle, commit_prepared_cams_lifecycle
from local_pipeline.cams_artifact_checkpoint import (
    CamsArtifactError, FILE_LIMITS, read_artifacts, save_artifacts,
    read_local_file, restore_local_file,
)
from local_pipeline.contract_v1 import load_catalog, canonical_json_bytes, validate_run_manifest
from local_pipeline.contracts import RunKey, Provider
from cams_request_plan import strict_json_loads
from local_pipeline.contract_publisher import ContractV1Publisher
from local_pipeline.job_outcomes import JobKind
from local_pipeline.publication_intent import PublicationIntent
from local_pipeline.remote_publication_intent import resolve_remote_publication_intent
from local_pipeline.object_state_store import ObjectStateStore
from local_pipeline.operational_diagnostics import emit
from retrieve_remote_cams import remote_cams_context
from retrieve_cams import _recover_completed_download


def _artifact_context(paths, catalog):
    paths = paths.normalized()
    prefix, identity = remote_cams_context(paths.artifacts_directory)
    completed = _recover_completed_download(paths.artifacts_directory / "source.grib", identity=identity)
    if completed is None:
        raise CamsArtifactError("CAMS decoded checkpoint requires a verified download")
    return paths, prefix, identity, {"source_sha256": completed["sha256"], "catalog_sha256": catalog.sha256}


def restore_remote_cams_decoded(*, paths, state_store):
    """Restore authenticated bytes only; publication still requires the full gate."""
    paths, prefix, identity, bindings = _artifact_context(paths, load_catalog())
    files = read_artifacts(state_store, prefix=prefix, stage="decoded", identity=identity, bindings=bindings)
    if files is None:
        return False
    restore_local_file(paths.decoded_payload, files["decoded.json"])
    restore_local_file(paths.decode_report, files["decode-report.json"])
    emit("cams_decoded_checkpoint", provider="cams", run_date=identity["run_date"], status="restored")
    return True


_CHECKPOINT_FIELDS = ('submitted_checkpoint', 'ready_checkpoint', 'downloaded_checkpoint', 'validated_checkpoint')
_HASH_FIELDS = ('catalog_sha256', 'validation_sha256', 'core_manifest_sha256', 'pollen_manifest_sha256')


def _prepared_document(prepared):
    return {'schema_version': 1,
            'key': {'source_run_id': prepared.key.source_run_id, 'request_hash': prepared.key.request_hash},
            **{name: dict(getattr(prepared, name)) for name in _CHECKPOINT_FIELDS},
            **{name: getattr(prepared, name) for name in _HASH_FIELDS},
            **{role + '_manifest_bytes': getattr(prepared, role + '_manifest_bytes').decode('utf-8')
               for role in ('core', 'pollen')},
            **{role + '_documents': {code: body.decode('utf-8') for code, body in
                                     getattr(prepared, role + '_documents').items()}
               for role in ('core', 'pollen')}}


def _verify_prepared(prepared, identity, bindings, catalog):
    if (prepared.catalog_sha256 != catalog.sha256
            or prepared.key.source_run_id != identity['run_date'].replace('-', '') + 'T000000Z'
            or prepared.key.request_hash != identity['request_sha256']
            or prepared.submitted_checkpoint['request_id'] != identity['request_id']
            or prepared.submitted_checkpoint['request_plan_sha256'] != identity['request_plan_sha256']
            or prepared.downloaded_checkpoint['artifact_sha256'] != bindings['source_sha256']):
        raise CamsArtifactError('CAMS prepared checkpoint identity differs')
    for role in ('core', 'pollen'):
        manifest = getattr(prepared, role + '_manifest')()
        validate_run_manifest(manifest, catalog, expected_provider=manifest['provider'],
                              object_bodies=getattr(prepared, role + '_documents'))


def save_remote_cams_prepared(*, paths, state_store, prepared):
    """Freeze materialized projections too: a publication retry must not rebuild them."""
    catalog = load_catalog()
    _, prefix, identity, bindings = _artifact_context(paths, catalog)
    _verify_prepared(prepared, identity, bindings, catalog)
    save_artifacts(state_store, prefix=prefix, stage='prepared', identity=identity,
                   bindings=bindings, files={'prepared.json': canonical_json_bytes(_prepared_document(prepared))})


def restore_remote_cams_prepared(*, paths, state_store):
    catalog = load_catalog()
    _, prefix, identity, bindings = _artifact_context(paths, catalog)
    files = read_artifacts(state_store, prefix=prefix, stage='prepared', identity=identity, bindings=bindings)
    if files is None:
        return None
    raw = files['prepared.json']
    try:
        value = strict_json_loads(raw)
        expected = {'schema_version', 'key', *_CHECKPOINT_FIELDS, *_HASH_FIELDS,
                    'core_manifest_bytes', 'pollen_manifest_bytes', 'core_documents', 'pollen_documents'}
        if (set(value) != expected or type(value['schema_version']) is not int or value['schema_version'] != 1
                or canonical_json_bytes(value) != raw or set(value['key']) != {'source_run_id', 'request_hash'}):
            raise ValueError()
        kwargs = {name: value[name] for name in (*_CHECKPOINT_FIELDS, *_HASH_FIELDS)}
        for role in ('core', 'pollen'):
            kwargs[role + '_manifest_bytes'] = value[role + '_manifest_bytes'].encode('utf-8')
            kwargs[role + '_documents'] = {code: body.encode('utf-8')
                                          for code, body in value[role + '_documents'].items()}
        prepared = PreparedCamsRun(key=RunKey(Provider.CAMS, **value['key']), **kwargs)
        _verify_prepared(prepared, identity, bindings, catalog)
    except Exception as error:
        raise CamsArtifactError('CAMS prepared checkpoint verification failed') from error
    emit('cams_prepared_checkpoint', provider='cams', status='restored', source_run_id=prepared.source_run_id)
    return prepared


def save_remote_cams_decoded(*, paths, state_store):
    """Validate all 215 municipalities, then atomically advertise restart bytes."""
    catalog = load_catalog()
    prepared = prepare_cams_lifecycle(paths=paths, catalog=catalog)
    paths, prefix, identity, bindings = _artifact_context(paths, catalog)
    files = {
        "decoded.json": read_local_file(paths.decoded_payload, FILE_LIMITS["decoded"]["decoded.json"]),
        "decode-report.json": read_local_file(paths.decode_report, FILE_LIMITS["decoded"]["decode-report.json"]),
    }
    validated = prepared.validated_checkpoint
    if (hashlib.sha256(files["decoded.json"]).hexdigest() != validated["payload_sha256"]
            or len(files["decoded.json"]) != validated["payload_bytes"]
            or hashlib.sha256(files["decode-report.json"]).hexdigest() != validated["decode_report_sha256"]
            or bindings["source_sha256"] != prepared.downloaded_checkpoint["artifact_sha256"]
            or identity["request_sha256"] != prepared.key.request_hash
            or identity["request_plan_sha256"] != prepared.submitted_checkpoint["request_plan_sha256"]
            or identity["request_id"] != prepared.submitted_checkpoint["request_id"]
            or identity["run_date"] != prepared.submitted_checkpoint["run_date"]
            or prepared.catalog_sha256 != catalog.sha256):
        raise CamsArtifactError("CAMS decoded artifacts changed after validation")
    save_artifacts(state_store, prefix=prefix, stage="decoded", identity=identity, files=files, bindings=bindings)
    emit("cams_decoded_checkpoint", provider="cams", run_date=identity["run_date"], status="persisted",
         validation_status="passed", validated_count=215)
    return prepared


def publish_remote_cams(*, paths, published_at, state_store, data_store, prepared=None):
    if state_store is data_store:
        raise ValueError("private state and data stores must be separate")
    catalog = load_catalog()
    if prepared is None:
        prepared = save_remote_cams_decoded(paths=paths, state_store=state_store)
    if not isinstance(prepared, PreparedCamsRun) or prepared.catalog_sha256 != catalog.sha256:
        raise CamsArtifactError("CAMS prepared publication catalog differs")
    resolved = resolve_remote_publication_intent(state_store, PublicationIntent(
        job=JobKind.CAMS, source_run_id=prepared.key.source_run_id,
        published_at=published_at, input_fingerprint_sha256=prepared.validation_sha256,
    ))
    return commit_prepared_cams_lifecycle(
        prepared=prepared, catalog=catalog, state_store=ObjectStateStore(state_store),
        publisher=ContractV1Publisher(data_store, catalog),
        owner_id="cams-cloud-" + uuid4().hex,
        published_at=resolved.intent.published_at,
    )
