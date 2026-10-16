"""Weather acquisition/publication entrypoint. No scheduler is created here.

Two ICON and four CAMS UTC slots/day bound new dispatches.
ICON task retries reuse an authenticated durable publication checkpoint when present.
Durable ADS records prevent duplicate submission across separate slots.
"""
from datetime import datetime, timezone
import json
import os
import re
from pathlib import Path
from tempfile import TemporaryDirectory
from time import sleep, monotonic
from uuid import uuid4

from google.cloud import storage
from local_pipeline.gcs_object_store import GCSObjectStore
from local_pipeline.sqlite_object_store import ObjectNotFound, PreconditionFailed
from local_pipeline.operational_diagnostics import emit, phase

PROJECT = os.environ.get("WEATHER_CLOUD_PROJECT", "meteofriul-pilot-20260906")
DATA_BUCKET = os.environ.get("WEATHER_DATA_BUCKET", PROJECT + "-data")
STATE_BUCKET = os.environ.get("WEATHER_STATE_BUCKET", PROJECT + "-state")

def dispatch_slot(provider, now):
    return now.strftime("%Y%m%d") + (
        f"-q{now.hour // 6}" if provider == "cams" else ("-am" if now.hour < 12 else "-pm")
    )


def run(provider):
    if os.environ.get("GOOGLE_CLOUD_PROJECT") != PROJECT or provider not in {"icon", "cams"}:
        raise ValueError("weather production configuration required")
    recovery = os.environ.get("PILOT_ICON_RECOVER_RUN_ID")
    if recovery is not None:
        from local_pipeline.publication_intent import _source_run_id
        if provider != "icon" or _source_run_id(recovery)[9:11] not in {"00", "12"}:
            raise ValueError("ICON-only recovery configuration required")
    if provider == "icon":
        _icon_execution_identity()
    with phase("worker", provider=provider):
        return _run(provider)


def _run(provider):
    now = datetime.now(timezone.utc)
    client = storage.Client(project=PROJECT)
    state = GCSObjectStore(client.bucket(STATE_BUCKET))
    data = GCSObjectStore(client.bucket(DATA_BUCKET))
    if provider == "icon":
        return _run_icon(state, data, now)
    return _run_cams(state, data, now)


def _cams_region_step(state, data, now):
    from local_pipeline.contract_v1 import load_catalog
    from local_pipeline.contract_publisher import ContractV1Publisher
    from cams_readback import verify_cams
    run_id = now.strftime("%Y%m%dT000000Z")
    try:
        latest = json.loads(data.get("weather/v1/families/cams/latest.json").body)
        if latest['latest']['source_run_id'] >= run_id:
            # A pointer alone is insufficient. Verify the existing atomic family
            # before skipping acquisition, then check the actual public reader.
            family = ContractV1Publisher(data, load_catalog()).read_verified_cams_family_latest()
            current = family['latest']['source_run_id']
            return {'status': 'verified', 'source_run_id': current,
                    'reason_code': 'existing_family_verified', **verify_cams(data, current)}
    except ObjectNotFound:
        pass
    published_at = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    with TemporaryDirectory(prefix="meteofriul-job-") as scratch:
        root = Path(scratch)
        from cams_request_plan import (create_verified_request_plan, encode_request_plan,
                                       load_verified_request_plan)
        from retrieve_remote_cams import retrieve_remote_cams
        from decode_cams_region import run_file
        from publish_remote_cams import (publish_remote_cams, restore_remote_cams_decoded,
                                         save_remote_cams_decoded, restore_remote_cams_prepared,
                                         save_remote_cams_prepared)
        from local_pipeline.cams_lifecycle import CamsLifecyclePaths
        day = now.strftime("%Y-%m-%d")
        plan_path = root / "plan.json"
        key = f"state/plans/cams/{day}.json"
        with phase("metadata_validation", provider="cams", run_date=day):
            try:
                saved_plan = state.get(key).body
            except ObjectNotFound:
                saved_plan = None
            if saved_plan is None:
                plan_path.write_bytes(encode_request_plan(create_verified_request_plan(day)))
                try:
                    state.put(key, plan_path.read_bytes(), content_type="application/json")
                except PreconditionFailed:
                    plan_path.write_bytes(state.get(key).body)
            else:
                plan_path.write_bytes(saved_plan)
        with phase("acquisition", provider="cams", run_date=day):
            report = retrieve_remote_cams(credentials_path=Path("/secrets/ads/credentials"),
                request_plan_path=plan_path, scratch=root, state_store=state, max_wait=45)
        if report.get("status") != "downloaded_pending_decode_validation":
            emit("publication_result", provider="cams", run_date=day,
                 status="pending", reason_code="acquisition_not_completed",
                 publication_status=report.get("status"))
            return _cams_acquisition_outcome(report, run_id)
        artifacts = root / ("cams-" + day)
        payload, decoded_report = artifacts / "decoded.json", artifacts / "decode-report.json"
        paths = CamsLifecyclePaths(artifacts, payload, decoded_report)
        prepared = restore_remote_cams_prepared(paths=paths, state_store=state)
        if prepared is None:
            if not restore_remote_cams_decoded(paths=paths, state_store=state):
                plan, _, plan_hash = load_verified_request_plan(plan_path)
                with phase("decode_validation", provider="cams", run_date=day):
                    payload_bytes, report_bytes = run_file(artifacts / "source.grib",
                        request_plan=plan, request_plan_sha256=plan_hash)
                payload.write_bytes(payload_bytes)
                decoded_report.write_bytes(report_bytes)
            prepared = save_remote_cams_decoded(paths=paths, state_store=state)
            save_remote_cams_prepared(paths=paths, state_store=state, prepared=prepared)
        with phase("publication", provider="cams", run_date=day):
            publish_remote_cams(paths=paths, prepared=prepared,
                published_at=published_at, state_store=state, data_store=data)
        emit("publication_result", provider="cams", status="published", run_date=day)
        return {'status': 'verified', 'source_run_id': run_id,
                'reason_code': 'new_family_verified', **verify_cams(data, run_id)}


CAMS_RECOVERY_DELAYS = (60, 180, 300)
CAMS_RECOVERY_BUDGET_SECONDS = 480  # Existing Cloud Run timeout is 600 s.


def _cams_uv_policy(now):
    enabled = os.environ.get('WEATHER_UV_ENABLED', os.environ.get('PILOT_UV_ENABLED', '0')) == '1'
    if not enabled:
        return False, 'uv_not_enabled'
    raw_hours = os.environ.get('WEATHER_UV_UTC_HOURS', '').strip()
    if not raw_hours:
        return True, None
    if not re.fullmatch(r'(?:[01]?\d|2[0-3])(?:,(?:[01]?\d|2[0-3]))*', raw_hours):
        raise ValueError('WEATHER_UV_UTC_HOURS must be a comma-separated UTC hour list')
    hours = tuple(int(value) for value in raw_hours.split(','))
    if len(set(hours)) != len(hours):
        raise ValueError('WEATHER_UV_UTC_HOURS must not contain duplicates')
    if now.hour not in hours:
        return False, 'uv_outside_scheduled_window'
    return True, None


def _cams_acquisition_outcome(report, run_id):
    """The legacy retriever returns a report, including failures, not exceptions."""
    result = {'source_run_id': run_id, 'stage': 'acquisition'}
    if report.get('status') == 'submission_reconciliation_pending':
        return {**result, 'status': 'reconciling', 'reason_code': 'reconciliation_pending'}
    reason = report.get('safe_reason')
    remote = report.get('last_job_metadata', {}).get('status')
    code = report.get('http_status')
    if reason == 'ADS wait budget reached; job saved for explicit resume, not resubmitted':
        return {**result, 'status': 'remote_pending', 'reason_code': 'remote_processing'}
    if remote in ('failed', 'rejected', 'dismissed', 'deleted'):
        return {**result, 'status': 'permanent_failure', 'reason_code': 'remote_processing_failed'}
    if type(code) is int and 100 <= code <= 599:
        return {**result, 'http_status': code,
                'status': 'retryable_failure' if code in (408, 429) or code >= 500 else 'permanent_failure',
                'reason_code': 'acquisition_http_failure'}
    if report.get('error_type') in ('TimeoutError', 'Timeout', 'ConnectTimeout', 'ReadTimeout', 'ConnectionError',
                                    'RemoteObjectStoreError', 'PreconditionFailed'):
        return {**result, 'status': 'retryable_failure', 'reason_code': 'acquisition_transport_failure'}
    return {**result, 'status': 'manual_review', 'reason_code': 'acquisition_validation_or_state_failure'}


def _legacy_uv_timestamp(state, key, etag):
    """Legacy intent time from authoritative GCS metadata, pinned to generation."""
    blob = state._blob(key)
    state._call(blob.reload, _operation='metadata_read', _key=key,
                if_generation_match=int(etag))
    if str(blob.generation) != str(etag) or blob.time_created is None:
        raise ValueError('Legacy UV intent metadata changed')
    return blob.time_created


def _cams_failure(error):
    from local_pipeline.operational_diagnostics import error_fields
    from local_pipeline.gcs_object_store import _http_status, _transport_failure
    from cams_readback import ReadbackPending
    from cams_request_plan import PublicMetadataUnavailable
    from urllib.error import URLError, HTTPError
    details = error_fields(error)
    status = _http_status(error)
    if isinstance(error, PublicMetadataUnavailable):
        # Catalog availability is preliminary, not a failed ADS submission.
        # Keep safe constraint diagnostics and let the existing bounded recovery
        # loop persist the pending components and evaluate UV independently.
        return {**details, 'stage': 'public_metadata_plan', 'status': 'retryable_failure',
                'retryable': True, 'http_status': status,
                'reason_code': details.get('reason_code', 'public_metadata_unavailable')}
    transient = (getattr(error, 'retryable', False) or _transport_failure(error)
                 or isinstance(error, (ReadbackPending, PreconditionFailed))
                 or isinstance(error, URLError) and not isinstance(error, HTTPError)
                 or status in (408, 429) or status is not None and status >= 500)
    # Reconciliation failures are deliberately not interpreted as a fresh request.
    inconclusive = type(error).__name__ in {'ReconciliationPending', 'CamsLeaseUnavailable'}
    reason = ('readback_pending' if isinstance(error, ReadbackPending) else
              'reconciliation_pending' if inconclusive else
              'temporary_failure' if transient else 'nonrecoverable_failure')
    return {**details, 'http_status': status,
            'status': 'retryable_failure' if transient or inconclusive else 'manual_review',
            'reason_code': reason}


def _persist_cams_outcome(state, slot, outcomes, *, retry_after=None):
    # Append-only: existing worker IAM permits create/read, not overwriting state
    # outside leased lifecycle records. Every snapshot includes ALL components.
    stamp = datetime.now(timezone.utc)
    record = {'schema_version': 1, 'kind': 'meteofriul.cams.component_outcomes',
              'at_utc': stamp.isoformat(), 'components': outcomes,
              'complete': all(v['status'] in ('verified', 'disabled') for v in outcomes.values()),
              'retry_after_seconds': retry_after}
    key = f"state/dispatch/cams/{slot}/outcomes/{stamp.strftime('%Y%m%dT%H%M%S%fZ')}-{uuid4().hex}.json"
    body = json.dumps(record, sort_keys=True, allow_nan=False).encode()
    state.put(key, body, content_type='application/json')
    if state.get(key).body != body:
        raise ValueError('CAMS outcome persistence verification failed')
    print(json.dumps(record, sort_keys=True), flush=True)
    return record


def _run_cams(state, data, now, *, budget=CAMS_RECOVERY_BUDGET_SECONDS,
              wait=sleep, clock=monotonic):
    from uv_cloud import enrich
    from cams_readback import verify_uv
    slot = dispatch_slot('cams', now)
    uv_enabled, uv_disabled_reason = _cams_uv_policy(now)
    outcomes = {name: {'status': 'reconciling'} for name in ('air', 'pollen', 'uv')}
    if not uv_enabled:
        outcomes['uv'] = {'status': 'disabled', 'reason_code': uv_disabled_reason}
    started = clock()
    for attempt in range(len(CAMS_RECOVERY_DELAYS) + 1):
        # Regional failure must not suppress UV, nor vice versa.
        if outcomes['air']['status'] not in ('verified', 'manual_review', 'permanent_failure'):
            try:
                result = _cams_region_step(state, data, now)
            except Exception as error:
                result = _cams_failure(error)
            result.setdefault('source_run_id', now.strftime('%Y%m%dT000000Z'))
            outcomes['air'] = dict(result)
            outcomes['pollen'] = dict(result)  # Same atomic release, explicit separate outcomes.
            _persist_cams_outcome(state, slot, outcomes)
        if uv_enabled and outcomes['uv']['status'] not in ('verified', 'manual_review', 'permanent_failure'):
            try:
                with TemporaryDirectory(prefix='meteofriul-uv-') as scratch:
                    result = enrich(state, data, Path(scratch), now,
                        allow_submit=os.environ.get('PILOT_UV_RECOVER_EXISTING') != '1',
                        legacy_intent_timestamp=lambda key, etag: _legacy_uv_timestamp(state, key, etag))
                if result['status'] in ('published', 'no_op', 'verified'):
                    result = {**result, **verify_uv(data, result['source_run_id']), 'status': 'verified'}
                outcomes['uv'] = result
            except Exception as error:
                outcomes['uv'] = _cams_failure(error)
            _persist_cams_outcome(state, slot, outcomes)
        if all(item['status'] in ('verified', 'disabled') for item in outcomes.values()):
            return outcomes
        pending = any(item['status'] not in ('verified', 'disabled', 'manual_review', 'permanent_failure')
                      for item in outcomes.values())
        if not pending:
            break
        delay = CAMS_RECOVERY_DELAYS[min(attempt, len(CAMS_RECOVERY_DELAYS)-1)]
        _persist_cams_outcome(state, slot, outcomes, retry_after=delay)
        # Leave room for a new pass. No frequency/configuration changes and no
        # long-lived 50-minute task. Artifacts survive even a hard task timeout.
        if attempt == len(CAMS_RECOVERY_DELAYS) or clock() - started + delay + 60 >= budget:
            break
        wait(delay)
    raise RuntimeError('CAMS components not all verified; see persisted component outcomes')


ICON_PUBLICATION_RETRY_DELAYS = (1, 3)


def _icon_execution_identity():
    execution = os.environ.get("CLOUD_RUN_EXECUTION")
    if execution is not None and not re.fullmatch(r"[a-z][a-z0-9-]{0,127}", execution):
        raise ValueError("invalid ICON execution identity")
    attempt = os.environ.get("CLOUD_RUN_TASK_ATTEMPT", "0")
    if attempt not in {"0", "1", "2"}:
        raise ValueError("invalid ICON task attempt")
    return execution, int(attempt)


def _icon_failure(error, source_run_id=None):
    from local_pipeline.job_entrypoints import classify_job_failure
    from local_pipeline.job_outcomes import JobKind, JobResult
    from local_pipeline.operational_diagnostics import error_fields
    from local_pipeline.gcs_object_store import _transport_failure, _http_status
    from run_pilot import SourceRunNotAdvanced
    if isinstance(error, SourceRunNotAdvanced):
        return JobResult(
            JobKind.ICON,
            "retryable_failure",
            "source_not_advanced",
            source_run_id=error.source_run_id,
            metrics={
                "published_pointer_verified": True,
                "verified_source_run_high_water": error.source_run_high_water,
            },
        )
    # Timeout/transport failures at the acquisition boundary are not data defects.
    status = _http_status(error)
    if _transport_failure(error) or status in {408, 429} or (status is not None and 500 <= status <= 599):
        return JobResult(JobKind.ICON, "retryable_failure", "icon_transport_temporary_failure",
                         source_run_id=source_run_id, metrics={**error_fields(error), "http_status": status})
    if status is not None:
        return JobResult(JobKind.ICON, "manual_review", "icon_source_http_failure",
                         source_run_id=source_run_id, metrics={**error_fields(error), "http_status": status})
    return classify_job_failure(JobKind.ICON, error, source_run_id=source_run_id) or JobResult(
        JobKind.ICON, "manual_review", "unexpected_internal_failure",
        source_run_id=source_run_id, metrics=error_fields(error),
    )


def _retry_icon_publication(action, *, source_run_id=None):
    """Bounded same-input retries only; never contains source acquisition."""
    from local_pipeline.job_outcomes import JobResult
    for attempt in range(len(ICON_PUBLICATION_RETRY_DELAYS) + 1):
        try:
            result = action()
        except Exception as error:
            result = _icon_failure(error, source_run_id)
        if not isinstance(result, JobResult) or not result.retryable:
            return result
        emit("publication_attempt", **{**dict(result.metrics), **result.as_document(),
             "provider": "icon", "attempt": attempt + 1})
        if attempt < len(ICON_PUBLICATION_RETRY_DELAYS):
            sleep(ICON_PUBLICATION_RETRY_DELAYS[attempt])
    return result


def _finish_icon(result):
    emit("publication_result", **{**dict(result.metrics), **result.as_document(), "provider": "icon"})
    if result.status.value not in {"published", "no_op"}:
        raise RuntimeError("ICON publication did not complete; inspect structured status")
    return result


def _icon_slot(state, now):
    """A Cloud Run execution keeps its initial slot even across a UTC boundary."""
    from local_pipeline.contract_v1 import canonical_json_bytes
    from local_pipeline.publication_intent import PublicationIntentCorruption, _strict_json
    execution, attempt = _icon_execution_identity()
    if execution is None:
        return dispatch_slot("icon", now), "local-" + uuid4().hex, attempt
    key = f"state/dispatch/icon/executions/{execution}.json"
    try:
        observed = state.get(key).body
    except ObjectNotFound:
        body = canonical_json_bytes({"execution_id": execution, "slot": dispatch_slot("icon", now)})
        try:
            state.put(key, body, content_type="application/json")
        except PreconditionFailed:
            pass
        observed = state.get(key).body
    record = _strict_json(observed)
    if (not isinstance(record, dict) or set(record) != {"execution_id", "slot"}
            or record["execution_id"] != execution or canonical_json_bytes(record) != observed
            or not isinstance(record["slot"], str) or not re.fullmatch(r"\d{8}-(?:am|pm)", record["slot"])):
        raise PublicationIntentCorruption("invalid ICON execution slot")
    return record["slot"], execution, attempt


def _claim_icon_acquisition(state, slot, execution, attempt):
    """Only the original execution may retry an unfinished acquisition, at most twice."""
    from local_pipeline.contract_v1 import canonical_json_bytes
    from local_pipeline.publication_intent import PublicationIntentCorruption, _strict_json
    key = f"state/dispatch/icon/{slot}.json"
    candidate = {"schema_version": 1, "execution_id": execution, "slot": slot}
    try:
        state.put(key, canonical_json_bytes(candidate), content_type="application/json")
    except PreconditionFailed:
        raw = state.get(key).body
        record = _strict_json(raw)
        if record == {}:  # Historical claims have no resumable acquisition owner.
            return False
        if (not isinstance(record, dict) or set(record) != set(candidate)
                or record["schema_version"] != 1 or record["slot"] != slot
                or not isinstance(record["execution_id"], str) or canonical_json_bytes(record) != raw):
            raise PublicationIntentCorruption("invalid ICON acquisition claim")
        if record["execution_id"] != execution:
            return False
    try:
        state.put(f"state/dispatch/icon/{slot}/acquisition-attempt-{attempt}.json", b"{}",
                  content_type="application/json")
    except PreconditionFailed:
        return False
    return True


def _publish_icon_checkpoint(checkpoint, *, state, data, catalog):
    from local_pipeline.contract_v1 import ICON_PROVIDER
    from local_pipeline.contract_publisher import ContractV1Publisher
    from local_pipeline.job_entrypoints import IconJobInputs, execute_icon_job, execute_icon_recovery
    from local_pipeline.remote_publication_intent import resolve_remote_publication_intent
    intent = resolve_remote_publication_intent(state, checkpoint.intent).intent
    publisher = ContractV1Publisher(data, catalog)
    manifest_key = f"weather/v1/{ICON_PROVIDER}/runs/{intent.source_run_id}/manifest.json"
    try:
        data.get(manifest_key)
    except ObjectNotFound:
        # An interrupted immutable write is completed from the validated checkpoint.
        return execute_icon_job(IconJobInputs(
            payload=Path("unused-checkpoint-payload"), report=Path("unused-checkpoint-report"),
            published_at=intent.published_at, source_run_id=intent.source_run_id,
            input_fingerprint_sha256=intent.input_fingerprint_sha256, prepared=checkpoint.prepared,
        ), catalog=catalog, publisher=publisher)
    # A present but invalid manifest is never replaced or bypassed.
    return execute_icon_recovery(intent=intent, publisher=publisher)


def _run_icon(state, data, now):
    return _finish_icon(_run_icon_result(state, data, now))


def _read_icon_outcome(raw):
    from local_pipeline.contract_v1 import canonical_json_bytes
    from local_pipeline.job_outcomes import JobKind, JobResult
    from local_pipeline.publication_intent import PublicationIntentCorruption, _strict_json
    record = _strict_json(raw)
    if not isinstance(record, dict) or canonical_json_bytes(record) != raw:
        raise PublicationIntentCorruption("invalid ICON terminal outcome")
    try:
        result = JobResult(job=record["job"], status=record["status"],
            reason_code=record["reason_code"], source_run_id=record["source_run_id"],
            published_providers=tuple(record["published_providers"]), metrics=record["metrics"])
    except (KeyError, TypeError, ValueError) as error:
        raise PublicationIntentCorruption("invalid ICON terminal outcome") from error
    if result.job is not JobKind.ICON or result.retryable or result.as_document() != record:
        raise PublicationIntentCorruption("invalid ICON terminal outcome")
    return result


def _verified_icon_source_run_high_water(pointer):
    """Return the greatest run identity already covered by a verified pointer."""
    if pointer is None:
        return None
    run_ids = [pointer["latest"]["source_run_id"]]
    if pointer["previous"] is not None:
        run_ids.append(pointer["previous"]["source_run_id"])
    run_ids.extend(pointer["disabled_run_ids"])
    # Contract-v1 run identifiers are canonical fixed-width UTC values, so
    # lexical order equals chronological order after read_verified_latest.
    return max(run_ids)


def _run_icon_result(state, data, now):
    from local_pipeline.contract_v1 import ICON_PROVIDER, load_catalog, canonical_json_bytes
    from local_pipeline.contract_publisher import ContractV1Publisher
    from local_pipeline.icon_checkpoint import read_checkpoint, save_checkpoint
    from local_pipeline.job_entrypoints import prepare_icon_publication
    from local_pipeline.job_outcomes import JobKind, JobResult
    from local_pipeline.publication_intent import PublicationIntent, PublicationIntentConflict
    recovery = os.environ.get("PILOT_ICON_RECOVER_RUN_ID")
    if recovery is not None:
        from publish_remote_icon import recover_remote_icon
        return _retry_icon_publication(lambda: recover_remote_icon(
            source_run_id=recovery, state_store=state, data_store=data), source_run_id=recovery)
    source_run_id = None
    marker_key = None
    try:
        catalog = load_catalog()
        slot, execution, attempt = _icon_slot(state, now)
        marker_key = f"state/dispatch/icon/{slot}/outcome.json"
        try:
            raw = state.get(marker_key).body
        except ObjectNotFound:
            raw = None
        if raw is not None:
            result = _read_icon_outcome(raw)
            if result.status.value in {"published", "no_op"} and result.source_run_id is not None:
                # A historical success is not proof that latest is still active/unrevoked.
                from publish_remote_icon import recover_remote_icon
                return _retry_icon_publication(lambda: recover_remote_icon(
                    source_run_id=result.source_run_id, state_store=state, data_store=data),
                    source_run_id=result.source_run_id)
            return result
        checkpoint = read_checkpoint(state, slot=slot, catalog=catalog)
        if checkpoint is None:
            # Keep the existing single-owner boundary: task retries belonging to
            # this execution may repeat discovery, while a different execution
            # in the same slot still cannot start a competing acquisition.
            if not _claim_icon_acquisition(state, slot, execution, attempt):
                return JobResult(JobKind.ICON, "no_op", "slot_already_claimed")
            from run_pilot import run_outputs
            verified_latest = ContractV1Publisher(data, catalog).read_verified_latest(ICON_PROVIDER)
            source_run_high_water = _verified_icon_source_run_high_water(verified_latest)
            with TemporaryDirectory(prefix="meteofriul-icon-") as scratch:
                root = Path(scratch)
                with phase("acquisition", provider="icon"):
                    run_outputs(
                        source_path=root / "source.json",
                        payload_path=root / "payload.json",
                        report_path=root / "report.json",
                        source_run_high_water=source_run_high_water,
                    )
                with phase("validation", provider="icon"):
                    prepared = prepare_icon_publication(payload=root / "payload.json", report=root / "report.json",
                                                        catalog=catalog)
                source_run_id = prepared.source_run_id
                emit("validation_result", provider="icon", source_run_id=source_run_id, status="validated",
                     validated_count=len(prepared.documents))
                intent = PublicationIntent(JobKind.ICON, source_run_id, now.strftime("%Y-%m-%dT%H:%M:%SZ"),
                                           prepared.input_fingerprint_sha256)
                # Freeze all resumable bytes atomically BEFORE creating the publication intent.
                checkpoint = _retry_icon_publication(lambda: save_checkpoint(state, slot=slot, prepared=prepared,
                    intent=intent, catalog=catalog), source_run_id=source_run_id)
        if isinstance(checkpoint, JobResult):
            result = checkpoint
        else:
            source_run_id = checkpoint.intent.source_run_id
            result = _retry_icon_publication(lambda: _publish_icon_checkpoint(checkpoint, state=state, data=data,
                                              catalog=catalog), source_run_id=source_run_id)
    except Exception as error:
        result = _icon_failure(error, source_run_id)
    if marker_key is not None and not result.retryable:
        # Terminal outcomes are create-only; a killed write is reconciled next attempt.
        def record_outcome():
            try:
                state.put(marker_key, canonical_json_bytes(result.as_document()), content_type="application/json")
            except PreconditionFailed:
                observed = _read_icon_outcome(state.get(marker_key).body)
                both_succeeded = all(item.status.value in {"published", "no_op"} for item in (result, observed))
                if observed != result and not (both_succeeded and observed.source_run_id == result.source_run_id):
                    raise PublicationIntentConflict("ICON terminal outcome conflicts with recorded result")
            return result
        result = _retry_icon_publication(record_outcome, source_run_id=source_run_id)
    return result


if __name__ == "__main__":
    run(os.environ.get("WEATHER_PROVIDER", os.environ.get("PILOT_PROVIDER")))
