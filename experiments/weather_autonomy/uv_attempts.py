"""Append-only attempt selection inside the existing UV run namespace.

Not another pipeline: job/source/decoded recovery stays in uv_cloud. A single
create-only selector arbitrates original vs one replacement before any work.
Only an unambiguously acknowledged create grants this invocation POST authority.
"""
from datetime import timedelta
import os
import re
from uuid import UUID, uuid4

from local_pipeline.sqlite_object_store import PreconditionFailed


class Attempts:
    def __init__(self, state, prefix, request, original, intended_at):
        from uv_cloud import _bytes, _hash, _json, DATASET
        self.state, self.prefix, self.request = state, prefix, request
        self.original, self.intended_at = original, intended_at
        self.run = request['date'].replace('-', '') + 'T000000Z'
        self.request_hash = _hash(_bytes(request))
        self.original_hash = _hash(original.body)
        self.original_id = 'original-' + self.original_hash[:24]
        self.base = {'schema_version': 1, 'dataset': DATASET, 'source_run_id': self.run,
                     'request_sha256': self.request_hash,
                     'original_intent_sha256': self.original_hash,
                     'original_intent_etag': original.head.etag}
        self.original_document = _json(original.body)
        self.key = prefix + 'canonical-attempt.json'

    def read(self):
        from uv_cloud import _optional, _verified, _json, _timestamp, UvStateError
        stored = _optional(self.state, self.key)
        if stored is None:
            return None
        doc = _json(_verified(stored, maximum=16384, content_type='application/json'))
        migrated_state = os.getenv('WEATHER_STATE_MIGRATED', '').strip() == '1'
        stable_binding = all(
            doc.get(k) == v
            for k, v in self.base.items()
            if k != 'original_intent_etag'
        )
        etag_binding = doc.get('original_intent_etag') == self.base['original_intent_etag']
        if migrated_state and stable_binding and not etag_binding:
            # A verified cross-bucket copy preserves the immutable intent body
            # and SHA-256 but necessarily assigns a new GCS generation/ETag.
            # Adopt the already selected ETag so its append-only history remains
            # internally bound; this exception is opt-in for the one migration.
            old_etag = doc.get('original_intent_etag')
            if isinstance(old_etag, str) and old_etag:
                self.base = {**self.base, 'original_intent_etag': old_etag}
                etag_binding = True
        if (set(doc) != set(self.base) | {'attempt', 'attempt_id', 'at_utc', 'history_key', 'history_sha256', 'remote_id'}
                or not stable_binding or not etag_binding
                or type(doc['attempt']) is not int or doc['attempt'] not in (1, 2)):
            raise UvStateError('uv_attempt_selection_invalid')
        _timestamp(doc['at_utc'])
        if doc['attempt'] == 1:
            if doc['attempt_id'] != self.original_id or doc['history_key'] or doc['history_sha256']:
                raise UvStateError('uv_attempt_selection_invalid')
            try:
                if str(UUID(doc['remote_id'])) != doc['remote_id']:
                    raise ValueError()
            except (ValueError, TypeError, AttributeError):
                raise UvStateError('uv_attempt_selection_invalid') from None
        else:
            try:
                valid_id = str(UUID(doc['attempt_id'])) == doc['attempt_id']
            except (ValueError, TypeError, AttributeError):
                valid_id = False
            if (not valid_id or doc['remote_id'] != '' or not isinstance(doc['history_key'], str)
                    or not re.fullmatch(re.escape(self.prefix) + r'history/[0-9a-f]{32}\.json', doc['history_key'])):
                raise UvStateError('uv_attempt_selection_invalid')
            self._validate_history(doc)
        return doc

    def _validate_evidence(self, evidence, now):
        from reconcile_cams_job import canonical
        from uv_cloud import _timestamp, _bytes, _hash, DATASET, UvStateError
        # Reusing an old Boolean is insufficient: this proof belongs to exactly
        # this request and original attempt, with a closed observation window.
        try:
            end = _timestamp(evidence['until_utc'])
            if (self.intended_at is None or evidence['complete'] is not True
                    or evidence['dataset'] != DATASET
                    or evidence['request_sha256'] != _hash(_bytes(canonical(self.request)))
                    or evidence['match_count'] != 0 or evidence['matched_ids'] != []
                    or evidence['coverage_reason'] not in ('end_of_results', 'crossed_lower_cutoff')
                    or _timestamp(evidence['since_utc']) != self.intended_at - timedelta(seconds=5)
                    or end < self.intended_at + timedelta(seconds=360)
                    or not 0 <= (now - end).total_seconds() <= 60
                    or type(evidence['checked_count']) is not int or evidence['checked_count'] < 0
                    or len(evidence['checked_jobs']) != evidence['checked_count']):
                raise ValueError()
        except (KeyError, TypeError, ValueError):
            raise UvStateError('uv_replacement_evidence_invalid') from None

    def _validate_history(self, selection):
        from uv_cloud import _verified, _json, _hash, _timestamp, UvStateError
        stored = self.state.get(selection['history_key'])
        raw = _verified(stored, maximum=131072, content_type='application/json')
        doc = _json(raw)
        if (_hash(raw) != selection['history_sha256'] or doc.get('binding') != self.base
                or doc.get('attempt_id') != self.original_id
                or doc.get('original_intent') != self.original_document
                or doc.get('request') != self.request
                or doc.get('status') != 'conclusive_no_match'
                or self.intended_at is None or _timestamp(doc.get('at_utc')) != self.intended_at):
            raise UvStateError('uv_replacement_history_invalid')
        self._validate_evidence(doc.get('evidence', {}), _timestamp(selection['at_utc']))

    def choose_original(self, now, identifier):
        """A remote reference exists; arbitrate before touching its artifacts."""
        from uv_cloud import _bytes
        doc = {**self.base, 'attempt': 1, 'attempt_id': self.original_id,
               'at_utc': (self.intended_at or now).isoformat().replace('+00:00', 'Z'),
               'history_key': '', 'history_sha256': '', 'remote_id': identifier}
        try:
            self.state.put(self.key, _bytes(doc), content_type='application/json')
        except PreconditionFailed:
            pass
        return self.read()

    def claim_replacement(self, evidence, now):
        """Only this call's successful create + readback can return owned=True."""
        from uv_cloud import _bytes, _hash, _create, UvStateError
        self._validate_evidence(evidence, now)
        history = {'binding': self.base, 'attempt_id': self.original_id,
                   'at_utc': self.intended_at.isoformat().replace('+00:00', 'Z'),
                   'original_intent': self.original_document, 'request': self.request,
                   'status': 'conclusive_no_match', 'evidence': evidence}
        history_key = self.prefix + 'history/' + uuid4().hex + '.json'
        history_raw = _bytes(history)
        _create(self.state, history_key, history_raw)
        doc = {**self.base, 'attempt': 2, 'attempt_id': str(uuid4()),
               'at_utc': now.isoformat().replace('+00:00', 'Z'),
               'history_key': history_key, 'history_sha256': _hash(history_raw), 'remote_id': ''}
        # Do NOT use _create: a loser or lost ACK must never own a POST.
        try:
            self.state.put(self.key, _bytes(doc), content_type='application/json')
        except PreconditionFailed:
            return self.read(), False
        observed = self.read()
        if observed != doc:
            raise UvStateError('uv_attempt_selection_invalid')
        return observed, True

    def artifact_prefix(self, selection):
        return self.prefix if selection['attempt'] == 1 else self.prefix + 'attempts/replacement-1/'

    def _reference(self, selection):
        from uv_cloud import _optional, _verified, _json, _bytes, _hash, _timestamp, DATASET, UvStateError
        from reconcile_cams_job import canonical
        stored = _optional(self.state, self.artifact_prefix(selection)+'remote-selection.json')
        if stored is None:
            return None
        doc = _json(_verified(stored, maximum=131072, content_type='application/json'))
        try:
            if (set(doc) != {'schema_version', 'attempt_id', 'source_run_id', 'request_sha256',
                             'remote_id', 'origin', 'evidence'} or doc['schema_version'] != 1
                    or doc['attempt_id'] != selection['attempt_id'] or doc['source_run_id'] != self.run
                    or doc['request_sha256'] != self.request_hash
                    or str(UUID(doc['remote_id'])) != doc['remote_id']):
                raise ValueError()
            if doc['origin'] == 'post_response':
                if doc['evidence'] is not None:
                    raise ValueError()
            elif doc['origin'] == 'unique_exact_match_origin_unconfirmed':
                proof = doc['evidence']
                if (proof['complete'] is not True or proof['dataset'] != DATASET
                        or proof['request_sha256'] != _hash(_bytes(canonical(self.request)))
                        or proof['matched_ids'] != [doc['remote_id']] or proof['match_count'] != 1
                        or proof['coverage_reason'] not in ('end_of_results', 'crossed_lower_cutoff')
                        or _timestamp(proof['since_utc']) != _timestamp(selection['at_utc'])-timedelta(seconds=5)):
                    raise ValueError()
            else:
                raise ValueError()
        except (KeyError, TypeError, ValueError, AttributeError):
            raise UvStateError('uv_canonical_remote_invalid') from None
        return doc

    def restore_remote(self, selection):
        from uv_cloud import _create, _bytes
        reference = self._reference(selection)
        if reference is None:
            return None
        _create(self.state, self.artifact_prefix(selection)+'job.json',
                _bytes({'id': reference['remote_id'], 'request': self.request}))
        return reference['remote_id']

    def record_remote(self, selection, identifier, *, reconciliation=None):
        from uv_cloud import _create, _bytes, _transient, UvStateError
        if self.read() != selection:
            raise UvStateError('uv_attempt_superseded')
        if selection['attempt'] == 1 and selection['remote_id'] != identifier:
            raise UvStateError('uv_canonical_remote_conflict')
        if selection['attempt'] == 2:
            # Persist the canonical reference before compatibility job.json.
            # ADS has no per-attempt correlation field. A GET match authenticates
            # the request, not which POST created it; preserve that distinction.
            reference = {'schema_version': 1, 'attempt_id': selection['attempt_id'],
                         'source_run_id': self.run, 'request_sha256': self.request_hash,
                         'remote_id': identifier, 'origin': 'post_response' if reconciliation is None
                         else 'unique_exact_match_origin_unconfirmed', 'evidence': reconciliation}
            try:
                self.state.put(self.artifact_prefix(selection)+'remote-selection.json',
                               _bytes(reference), content_type='application/json')
            except Exception as error:
                if not isinstance(error, PreconditionFailed) and not _transient(error):
                    raise
                observed = self._reference(selection)
                if observed is None:
                    raise
            observed = self._reference(selection)
            if observed is None or observed['remote_id'] != identifier:
                raise UvStateError('uv_canonical_remote_conflict')
        _create(self.state, self.artifact_prefix(selection) + 'job.json',
                _bytes({'id': identifier, 'request': self.request}))

    def fence(self, selection, identifier):
        from uv_cloud import _verified, _json, UvStateError
        if self.read() != selection:
            raise UvStateError('uv_attempt_superseded')
        if selection['attempt'] == 1 and selection['remote_id'] != identifier:
            raise UvStateError('uv_canonical_remote_conflict')
        if selection['attempt'] == 2:
            reference = self._reference(selection)
            if reference is None or reference['remote_id'] != identifier:
                raise UvStateError('uv_canonical_remote_conflict')
        stored = self.state.get(self.artifact_prefix(selection) + 'job.json')
        doc = _json(_verified(stored, maximum=16384, content_type='application/json'))
        if doc != {'id': identifier, 'request': self.request}:
            raise UvStateError('uv_canonical_remote_conflict')

    def supersede(self, selection, identifier):
        from uv_cloud import _create, _bytes
        reference = self._reference(selection) if selection['attempt'] == 2 else None
        if selection['attempt'] == 2 and reference is None:
            # Another worker may select this very ID immediately after this read.
            # Until the canonical remote is frozen, record only an observation;
            # never race a definitive superseded mark against remote selection.
            _create(self.state, self.prefix+'observations/original-'+str(UUID(identifier))+'.json',
                    _bytes({'status': 'observed', 'source_run_id': self.run,
                            'remote_id': identifier, 'canonical_attempt_id': selection['attempt_id'],
                            'reason_code': 'original_reference_pending_canonical_remote'}))
            return
        if reference is not None and reference['remote_id'] == identifier:
            # A previously origin-unconfirmed canonical job can also be observed
            # by the delayed original invocation. Never supersede the canonical
            # ID itself or start the original pipeline alongside it.
            _create(self.state, self.prefix+'observations/'+str(UUID(identifier))+'.json',
                    _bytes({'status': 'canonical', 'source_run_id': self.run,
                            'remote_id': identifier, 'canonical_attempt_id': selection['attempt_id'],
                            'reason_code': 'canonical_reference_also_observed_by_original'}))
            return
        # Fixed key and deterministic record: repeated observation is idempotent.
        _create(self.state, self.prefix + 'superseded/' + str(UUID(identifier)) + '.json',
                _bytes({'schema_version': 1, 'source_run_id': self.run,
                        'request_sha256': self.request_hash, 'remote_id': identifier,
                        'status': 'superseded', 'canonical_attempt_id': selection['attempt_id'],
                        'reason_code': 'noncanonical_request_ignored'}))

    def was_superseded(self, identifier):
        from uv_cloud import _optional
        return _optional(self.state, self.prefix+'superseded/'+str(UUID(identifier))+'.json') is not None
