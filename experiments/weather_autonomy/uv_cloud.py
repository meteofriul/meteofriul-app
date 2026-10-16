"""Pilot UV enrichment, sharing the bounded CAMS job, never the beta.

214002 is documented as an instantaneous dose rate in W/m² despite the GRIB
table's '~' label. This exception is restricted to that exact CAMS parameter.
https://confluence.ecmwf.int/pages/viewpage.action?pageId=673323626
"""
from datetime import datetime, timedelta, timezone
import hashlib
import importlib.metadata
import json
import math
import warnings
from uuid import UUID, uuid4
from urllib.parse import urlsplit
from local_pipeline.sqlite_object_store import ObjectNotFound, PreconditionFailed
from local_pipeline.operational_diagnostics import emit, error_fields

KEY = 'weather/v1/uv/latest.json'
DATASET = 'cams-global-atmospheric-composition-forecasts'
MAX_SOURCE_BYTES = 2 * 1024 * 1024
MAX_DOCUMENT_BYTES = 1024 * 1024


def decode(path, day):
    import eccodes as ec
    import math
    run = datetime.fromisoformat(day).replace(tzinfo=timezone.utc)
    hours = {}
    grid = None
    with open(path, 'rb') as stream:
        while (h := ec.codes_grib_new_from_file(stream)) is not None:
            try:
                if (ec.codes_get(h, 'paramId') != 214002 or ec.codes_get(h, 'shortName') != 'uvbed'
                    or ec.codes_get(h, 'stepType') != 'instant' or ec.codes_get(h, 'units') not in ('~', 'W m-2', 'W m**-2')
                    or ec.codes_get(h, 'dataDate') != int(day.replace('-', '')) or ec.codes_get(h, 'dataTime') != 0):
                    raise ValueError('Unexpected UV field')
                valid = datetime.strptime(f"{ec.codes_get(h, 'validityDate')}{ec.codes_get(h, 'validityTime'):04d}", '%Y%m%d%H%M').replace(tzinfo=timezone.utc)
                step = int((valid-run).total_seconds()/3600)
                if valid != run+timedelta(hours=step) or step not in range(72) or step in hours:
                    raise ValueError('Invalid or duplicate UV hour')
                points = list(ec.codes_grib_get_data(h))
                coordinates = [[p['lat'], p['lon']] for p in points]
                if not 1 <= len(points) <= 100 or any(not (45 <= lat <= 47 and 11.8 <= lon <= 14.6) for lat, lon in coordinates):
                    raise ValueError('Unexpected UV grid')
                if grid is not None and grid != coordinates:
                    raise ValueError('Changing UV grid')
                grid = coordinates
                values = [p['value']*40 for p in points]
                if any(not math.isfinite(v) or v < 0 or v > 50 for v in values):
                    raise ValueError('Invalid UV value')
                hours[step] = {'time': valid.isoformat().replace('+00:00', 'Z'), 'values': values}
            finally:
                ec.codes_release(h)
    if set(hours) != set(range(72)):
        raise ValueError('Incomplete UV forecast')
    return {'schema': 'pilot-uv-v1', 'source': 'CAMS / Copernicus', 'unit': '1',
            'run_at': run.isoformat().replace('+00:00', 'Z'), 'grid': grid,
            'hours': [hours[i] for i in range(72)]}


class UvStateError(ValueError):
    """A curated reason, never a provider exception string."""


def _bytes(document):
    return json.dumps(document, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def _hash(body):
    return hashlib.sha256(body).hexdigest()


def _json(body, maximum=MAX_DOCUMENT_BYTES):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise UvStateError('uv_checkpoint_invalid')
            result[key] = value
        return result
    if not 0 < len(body) <= maximum:
        raise UvStateError('uv_checkpoint_invalid')
    try:
        return json.loads(body, object_pairs_hook=pairs,
                          parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
    except (TypeError, ValueError, UnicodeError):
        raise UvStateError('uv_checkpoint_invalid') from None


def _timestamp(value):
    try:
        parsed = value if isinstance(value, datetime) else datetime.fromisoformat(value.replace('Z', '+00:00'))
        if parsed.tzinfo is None:
            raise ValueError()
        return parsed.astimezone(timezone.utc)
    except (AttributeError, TypeError, ValueError):
        raise UvStateError('uv_intent_timestamp_invalid') from None


def _optional(store, key):
    try:
        return store.get(key)
    except ObjectNotFound:
        return None


def _verified(stored, *, maximum, content_type, metadata=None):
    if (not 0 < len(stored.body) <= maximum or stored.head.size != len(stored.body)
            or stored.head.sha256 != _hash(stored.body) or stored.head.content_type != content_type
            or any(stored.head.metadata.get(k) != v for k, v in (metadata or {}).items())):
        raise UvStateError('uv_checkpoint_integrity_failed')
    return stored.body


def _create(store, key, body, *, content_type='application/json', metadata=None):
    """Create-only + verified readback handles races and lost write responses."""
    try:
        store.put(key, body, content_type=content_type, metadata=metadata)
    except Exception as error:
        if not isinstance(error, PreconditionFailed) and not _transient(error):
            raise
        existing = _optional(store, key)
        if existing is None:
            raise
        if existing.body != body:
            raise UvStateError('uv_checkpoint_conflict') from None
    observed = store.get(key)
    _verified(observed, maximum=max(len(body), 1), content_type=content_type, metadata=metadata)
    if observed.body != body:
        raise UvStateError('uv_checkpoint_conflict')
    return observed


def _http_status(error):
    value = getattr(getattr(error, 'response', None), 'status_code', None)
    if type(value) is not int:
        value = getattr(error, 'weather_diagnostics', {}).get('http_status')
    return value if type(value) is int and 100 <= value <= 599 else None


def _transient(error):
    import requests
    code = _http_status(error)
    return (code in {408, 429} or code is not None and 500 <= code <= 599
            or isinstance(error, (requests.Timeout, requests.ConnectionError, TimeoutError, ConnectionError))
            or getattr(error, 'retryable', False) is True)


def validate_document(document, day=None):
    """Revalidate a decoded checkpoint and latest; never trust a cached result."""
    try:
        run = _timestamp(document['run_at'])
        grid, hours = document['grid'], document['hours']
        if (set(document) != {'schema', 'source', 'unit', 'run_at', 'grid', 'hours'}
                or document['schema'] != 'pilot-uv-v1' or document['source'] != 'CAMS / Copernicus'
                or document['unit'] != '1' or document['run_at'] != run.strftime('%Y-%m-%dT00:00:00Z')
                or day is not None and run.strftime('%Y-%m-%d') != day
                or not isinstance(grid, list) or not 1 <= len(grid) <= 100
                or not isinstance(hours, list) or len(hours) != 72):
            raise ValueError()
        def number(value):
            return type(value) in {int, float} and math.isfinite(value)
        for point in grid:
            if (not isinstance(point, list) or len(point) != 2 or not all(map(number, point))
                    or not 45 <= point[0] <= 47 or not 11.8 <= point[1] <= 14.6):
                raise ValueError()
        if len({tuple(point) for point in grid}) != len(grid):
            raise ValueError()
        for index, row in enumerate(hours):
            if (set(row) != {'time', 'values'} or row['time'] != (run+timedelta(hours=index)).strftime('%Y-%m-%dT%H:%M:%SZ')
                    or not isinstance(row['values'], list) or len(row['values']) != len(grid)
                    or any(not number(v) or not 0 <= v <= 50 for v in row['values'])):
                raise ValueError()
    except (KeyError, TypeError, ValueError, OverflowError):
        raise UvStateError('uv_document_invalid') from None
    return document


def _publish(data, body, day):
    """Existing atomic pointer, with bounded CAS and a verified storage readback."""
    for _ in range(3):
        old = _optional(data, KEY)
        if old is not None:
            previous = validate_document(_json(_verified(old, maximum=MAX_DOCUMENT_BYTES,
                                                        content_type='application/json')))
            if previous['run_at'][:10] > day:
                return 'no_op', 'uv_superseded', previous['run_at'].replace('-', '').replace(':', '')
            if previous['run_at'][:10] == day:
                if _bytes(previous) != body:
                    raise UvStateError('uv_publication_conflict')
                return 'published', 'uv_publication_verified', day.replace('-', '')+'T000000Z'
        try:
            data.compare_and_swap(KEY, body, expected_etag=old.head.etag if old else None,
                                  content_type='application/json')
        except Exception as error:
            if not isinstance(error, PreconditionFailed) and not _transient(error):
                raise
            observed = _optional(data, KEY)
            if observed is None or observed.body != body:
                if isinstance(error, PreconditionFailed):
                    continue
                raise
        observed = data.get(KEY)
        validate_document(_json(_verified(observed, maximum=MAX_DOCUMENT_BYTES,
                                          content_type='application/json')))
        if observed.body == body:
            return 'published', 'uv_publication_verified', day.replace('-', '')+'T000000Z'
        if _json(observed.body)['run_at'][:10] > day:
            return 'no_op', 'uv_superseded', _json(observed.body)['run_at'].replace('-', '').replace(':', '')
        raise UvStateError('uv_publication_readback_failed')
    raise PreconditionFailed(KEY, 'UV latest contention')


def enrich(state, data, root, now, *, allow_submit=True, legacy_intent_timestamp=None, utc_now=None):
    """One bounded step; the existing worker owns progressive retry scheduling.

    Preserve original intent/job keys. New intents add authenticated bindings;
    legacy intents need a generation-pinned creation timestamp from the adapter.
    One replacement is allowed only after a conclusive, error-free empty search.
    The immutable attempt selection fences every artifact and publication write.
    """
    from retrieve_cams import AdsOnlySession, ADS_URL, load_credentials, safe_job_metadata, PilotError
    from reconcile_cams_job import ReadOnlyAdsSession, find_existing_job_complete
    from uv_attempts import Attempts
    from ecmwf.datastores import Client
    import requests
    now = _timestamp(now)
    utc_now = utc_now or (lambda: datetime.now(timezone.utc))
    day = (now-timedelta(days=1) if now.hour < 10 else now).strftime('%Y-%m-%d')
    request = {'variable': ['uv_biologically_effective_dose'], 'date': day,
               'time': ['00:00'], 'leadtime_hour': [str(i) for i in range(72)],
               'type': ['forecast'], 'area': [46.8, 12.0, 45.2, 14.4], 'data_format': 'grib'}
    request_hash, prefix = _hash(_bytes(request)), f'state/uv/{day}/'
    identity = {'component': 'uv', 'source_run_id': day.replace('-', '')+'T000000Z'}
    stage = 'checkpoint_validation'

    def report(status, reason, **fields):
        result = {**identity, 'status': status, 'stage': stage, 'reason_code': reason, **fields}
        stamp = _timestamp(utc_now())
        record = _bytes({'schema_version': 1, 'request_sha256': request_hash,
                         'updated_at': stamp.isoformat().replace('+00:00', 'Z'), **result})
        # Existing UV IAM permits create/read only, not mutable progress writes.
        progress_key = prefix+'progress/'+stamp.strftime('%Y%m%dT%H%M%S')+'-'+uuid4().hex+'.json'
        _create(state, progress_key, record)
        emit('uv_progress', provider='uv', **{k: v for k, v in result.items() if k != 'component'})
        return result

    def client_for(session, url, key):
        session.trust_env = False
        return Client(url=url, key=key, session=session, maximum_tries=1,
                      timeout=(10, 20), retry_after=0, progress=False, cleanup=False,
                      log_callback=lambda *a, **k: None)

    def credentials():
        url, key = load_credentials('/secrets/ads/credentials')
        if url != ADS_URL:
            raise UvStateError('uv_ads_endpoint_invalid')
        return url, key

    def reconcile(at, url, key):
        if importlib.metadata.version('ecmwf-datastores-client') != '0.5.3':
            raise UvStateError('uv_reconciliation_client_version')
        with ReadOnlyAdsSession() as session, warnings.catch_warnings(record=True):
            warnings.simplefilter('always')
            return find_existing_job_complete(client_for(session, url, key), dataset=DATASET,
                request=request, intended_at=at, observed_at=_timestamp(utc_now()))

    def audit_duplicates(attempts, selection, identifier, url=None, key=None):
        if selection['attempt'] != 2 or identifier is None:
            return
        # Known canonical work does not lose its authority because a later GET
        # fails. The immutable selector still prevents every old worker write.
        try:
            if url is None:
                url, key = credentials()
            matches, _ = reconcile(attempts.intended_at, url, key)
        except Exception as error:
            emit('uv_duplicate_audit_pending', provider='uv', stage='reconciliation',
                 error_type=type(error).__name__, reason_code='uv_duplicate_audit_pending')
            return
        for duplicate_id, _ in matches:
            if duplicate_id != identifier:
                attempts.supersede(selection, duplicate_id)

    try:
        already_published = None
        old = _optional(data, KEY)
        if old is not None:
            previous = validate_document(_json(_verified(old, maximum=MAX_DOCUMENT_BYTES,
                                                        content_type='application/json')))
            if previous['run_at'][:10] >= day:
                already_published = previous['run_at'].replace('-', '').replace(':', '')
                if _optional(state, prefix+'canonical-attempt.json') is None:
                    return report('no_op', 'uv_already_published', publication_status='storage_verified',
                                  source_run_id=already_published)
        intent = _optional(state, prefix+'intent.json')
        intended_at = None
        if intent is not None:
            saved_intent = _json(_verified(intent, maximum=16384, content_type='application/json'))
            if saved_intent == request:
                if legacy_intent_timestamp is not None:
                    value = legacy_intent_timestamp(prefix+'intent.json', intent.head.etag)
                    intended_at = _timestamp(value) if value is not None else None
            elif (isinstance(saved_intent, dict) and set(saved_intent) ==
                  {'schema_version', 'dataset', 'request', 'request_sha256', 'at_utc'}
                  and type(saved_intent['schema_version']) is int and saved_intent['schema_version'] == 2
                  and saved_intent['dataset'] == DATASET
                  and saved_intent['request'] == request and saved_intent['request_sha256'] == request_hash):
                intended_at = _timestamp(saved_intent['at_utc'])
            else:
                raise UvStateError('uv_intent_mismatch')
        job_record = _optional(state, prefix+'job.json')
        identifier = None
        if job_record is not None:
            job = _json(_verified(job_record, maximum=16384, content_type='application/json'))
            if set(job) != {'id', 'request'} or job['request'] != request or str(UUID(job['id'])) != job['id']:
                raise UvStateError('uv_job_mismatch')
            if intent is None:
                raise UvStateError('uv_job_without_intent')
            identifier = job['id']

        attempts = Attempts(state, prefix, request, intent, intended_at) if intent is not None else None
        selection = attempts.read() if attempts is not None else None
        if selection is None and identifier is not None:
            selection = attempts.choose_original(_timestamp(utc_now()), identifier)
        artifact_prefix = prefix
        if selection is not None:
            identity.update(attempt=selection['attempt'], attempt_id=selection['attempt_id'])
            artifact_prefix = attempts.artifact_prefix(selection)
            if selection['attempt'] == 1 and identifier is None:
                identifier = selection['remote_id']
                attempts.record_remote(selection, identifier)
            if selection['attempt'] == 2:
                if identifier is not None:
                    attempts.supersede(selection, identifier)
                attempts.restore_remote(selection)
                job_record = _optional(state, artifact_prefix+'job.json')
                identifier = None
                if job_record is not None:
                    job = _json(_verified(job_record, maximum=16384, content_type='application/json'))
                    if (set(job) != {'id', 'request'} or job['request'] != request
                            or str(UUID(job['id'])) != job['id']):
                        raise UvStateError('uv_job_mismatch')
                    identifier = job['id']
            if identifier is not None:
                attempts.fence(selection, identifier)
        if already_published is not None:
            if selection is not None:
                audit_duplicates(attempts, selection, identifier)
            return report('no_op', 'uv_already_published', publication_status='storage_verified',
                          source_run_id=already_published)

        # Durable decoded checkpoint is sufficient for publication-only recovery.
        decoded = _optional(state, artifact_prefix+'decoded.json')
        metadata = {'request-sha256': request_hash, 'dataset': DATASET}
        if decoded is not None:
            if intent is None or identifier is None:
                raise UvStateError('uv_checkpoint_without_job')
            envelope = _json(_verified(decoded, maximum=MAX_DOCUMENT_BYTES,
                                       content_type='application/json', metadata=metadata))
            if (set(envelope) != {'schema_version', 'request_sha256', 'source_sha256', 'document'}
                    or type(envelope['schema_version']) is not int or envelope['schema_version'] != 1
                    or envelope['request_sha256'] != request_hash):
                raise UvStateError('uv_decoded_checkpoint_mismatch')
            source = state.head(artifact_prefix+'source.grib')
            if (source.sha256 != envelope['source_sha256'] or not 0 < source.size < MAX_SOURCE_BYTES
                    or source.content_type != 'application/x-grib'
                    or any(source.metadata.get(k) != v for k, v in metadata.items())):
                raise UvStateError('uv_decoded_source_mismatch')
            document = validate_document(envelope['document'], day)
        else:
            source = _optional(state, artifact_prefix+'source.grib')
            if source is not None:
                if intent is None or identifier is None:
                    raise UvStateError('uv_checkpoint_without_job')
                body = _verified(source, maximum=MAX_SOURCE_BYTES, content_type='application/x-grib', metadata=metadata)
            else:
                if intent is not None and identifier is None and intended_at is None:
                    return report('manual_review', 'uv_reconciliation_timestamp_missing')
                if intent is None and not allow_submit:
                    return report('manual_review', 'uv_recovery_requires_intent')
                url, key = credentials()
                replacement_post = False
                if identifier is None and intent is not None:
                    stage = 'reconciliation'
                    report('reconciling', 'uv_existing_intent_without_job')
                    search_at = _timestamp(selection['at_utc']) if selection is not None else intended_at
                    matches, evidence = reconcile(search_at, url, key)
                    if len(matches) > 1:
                        return report('manual_review', 'uv_reconciliation_multiple_matches')
                    if matches:
                        identifier = matches[0][0]
                        if selection is not None and selection['attempt'] == 2 and attempts.was_superseded(identifier):
                            return report('manual_review', 'uv_replacement_only_superseded_match')
                        if selection is None:
                            selection = attempts.choose_original(_timestamp(utc_now()), identifier)
                            if selection['attempt'] != 1:
                                attempts.supersede(selection, identifier)
                                return report('reconciling', 'uv_attempt_superseded')
                        artifact_prefix = attempts.artifact_prefix(selection)
                        attempts.record_remote(selection, identifier, reconciliation=evidence)
                    else:
                        if (_timestamp(utc_now()) - search_at).total_seconds() < 360:
                            return report('reconciling', 'uv_submission_visibility_window_open')
                        if selection is not None:
                            return report('manual_review', 'uv_replacement_exhausted_no_match')
                        if not allow_submit:
                            return report('manual_review', 'uv_replacement_submission_disabled')
                        stage = 'submission'
                        selection, replacement_post = attempts.claim_replacement(evidence, _timestamp(utc_now()))
                        if not replacement_post:
                            return report('reconciling', 'uv_attempt_already_selected')
                        artifact_prefix = attempts.artifact_prefix(selection)
                        identity.update(attempt=selection['attempt'], attempt_id=selection['attempt_id'])
                with AdsOnlySession() as session, warnings.catch_warnings(record=True):
                    warnings.simplefilter('always')
                    client = client_for(session, url, key)
                    if identifier is None:
                        stage = 'submission'
                        report('submitting', 'uv_submission_starting')
                        if replacement_post:
                            if attempts.read() != selection:
                                raise UvStateError('uv_attempt_superseded')
                            if (_timestamp(utc_now()) - _timestamp(selection['at_utc'])).total_seconds() > 60:
                                return report('reconciling', 'uv_submission_claim_expired')
                        else:
                            # Never reconcile an ambiguous intent write into authority to POST.
                            intended_at = _timestamp(utc_now())
                            try:
                                state.put(prefix+'intent.json', _bytes({'schema_version': 2, 'dataset': DATASET,
                                          'request': request, 'request_sha256': request_hash,
                                          'at_utc': intended_at.isoformat().replace('+00:00', 'Z')}), content_type='application/json')
                            except PreconditionFailed:
                                return report('reconciling', 'uv_intent_claimed')
                            intent = state.get(prefix+'intent.json')
                            attempts = Attempts(state, prefix, request, intent, intended_at)
                            if (attempts.read() is not None
                                    or (_timestamp(utc_now()) - intended_at).total_seconds() > 60):
                                return report('reconciling', 'uv_submission_claim_expired')
                        remote = client.submit(DATASET, request)
                        identifier = str(UUID(remote.request_id))
                        if not replacement_post:
                            selection = attempts.choose_original(_timestamp(utc_now()), identifier)
                            if selection['attempt'] != 1:
                                attempts.supersede(selection, identifier)
                                return report('reconciling', 'uv_attempt_superseded')
                        attempts.record_remote(selection, identifier)
                        identity.update(attempt=selection['attempt'], attempt_id=selection['attempt_id'])
                    else:
                        remote = client.get_remote(identifier)
                    attempts.fence(selection, identifier)
                    report('remote_ref', 'uv_remote_reference_persisted')
                    stage = 'polling'
                    status = safe_job_metadata(remote.json)['status']
                    if status in {'accepted', 'queued', 'running'}:
                        return report('pending', 'uv_provider_processing', acquisition_status=status)
                    if status != 'successful':
                        return report('permanent_failure', 'uv_provider_terminal_failure', acquisition_status=status)
                    stage = 'download'
                    report('downloading', 'uv_download_starting')
                    attempts.fence(selection, identifier)
                    response = session.get(url+'/retrieve/v1/jobs/'+identifier+'/results',
                                           headers={'PRIVATE-TOKEN': key}, timeout=20)
                    response.raise_for_status()
                    asset = response.json()['asset']['value']
                    parsed = urlsplit(asset['href'])
                    if (parsed.scheme != 'https' or parsed.hostname != 'object-store.os-api.cci2.ecmwf.int'
                            or parsed.username or parsed.password or parsed.port not in {None, 443} or parsed.fragment):
                        raise UvStateError('uv_download_host_invalid')
                    size = asset['file:size']
                    if type(size) is not int or not 0 < size < MAX_SOURCE_BYTES:
                        raise UvStateError('uv_download_size_invalid')
                    with requests.get(asset['href'], stream=True, timeout=(10, 20), allow_redirects=False) as response:
                        if 300 <= response.status_code < 400:
                            raise UvStateError('uv_download_redirect_refused')
                        response.raise_for_status()
                        chunks = bytearray()
                        for chunk in response.iter_content(16384):
                            chunks.extend(chunk)
                            if len(chunks) > size:
                                raise UvStateError('uv_download_overflow')
                    body = bytes(chunks)
                    if len(body) != size or not body.startswith(b'GRIB') or not body.endswith(b'7777'):
                        raise UvStateError('uv_download_incomplete')
                    attempts.fence(selection, identifier)
                    _create(state, artifact_prefix+'source.grib', body, content_type='application/x-grib', metadata=metadata)
                    report('downloaded', 'uv_source_checkpointed')
            stage = 'decode_validation'
            report('validating', 'uv_validation_starting')
            attempts.fence(selection, identifier)
            path = root/'uv.grib'
            path.write_bytes(body)
            document = validate_document(decode(path, day), day)
            attempts.fence(selection, identifier)
            _create(state, artifact_prefix+'decoded.json', _bytes({'schema_version': 1, 'request_sha256': request_hash,
                    'source_sha256': _hash(body), 'document': document}), metadata=metadata)
            report('validated', 'uv_document_checkpointed', validation_status='passed')
        stage = 'publication'
        attempts.fence(selection, identifier)
        audit_duplicates(attempts, selection, identifier)
        attempts.fence(selection, identifier)
        report('publishing', 'uv_publication_starting', validation_status='passed')
        status, reason, served_run = _publish(data, _bytes(document), day)
        return report(status, reason, validation_status='passed', publication_status='storage_verified',
                      source_run_id=served_run)
    except Exception as error:
        if isinstance(error, UvStateError):
            status, reason = 'manual_review', str(error)
        elif isinstance(error, PilotError) and stage == 'reconciliation':
            status, reason = 'reconciling', 'uv_reconciliation_inconclusive'
        elif stage == 'submission' and _transient(error):
            status, reason = 'reconciling', 'uv_submission_uncertain'
        elif _transient(error) or isinstance(error, PreconditionFailed):
            status, reason = 'retryable_failure', 'uv_transient_failure'
        elif _http_status(error) is not None:
            status, reason = 'permanent_failure', 'uv_http_failure'
        else:
            status, reason = 'manual_review', 'uv_validation_or_state_failure'
        fields = {'error_type': type(error).__name__}
        if _http_status(error) is not None:
            fields['http_status'] = _http_status(error)
        emit('uv_failure', **{**error_fields(error), 'provider': 'uv', 'stage': stage,
                             'reason_code': reason, **fields})
        try:
            return report(status, reason, **fields)
        except Exception as progress_error:
            emit('uv_progress_write_failed', **{**error_fields(progress_error), 'provider': 'uv', 'stage': stage})
            return {**identity, 'status': 'retryable_failure' if _transient(progress_error) else 'manual_review',
                    'stage': stage, 'reason_code': 'uv_progress_write_failed', 'error_type': type(progress_error).__name__}
