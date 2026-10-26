"""CAMS-only bounded recovery of idempotent Storage reads.

No SDK retries, no repeated writes and no relaxed TLS validation. The two extra
reads are shared by data/state for the entire execution, not per municipality.
"""
import ssl
from time import monotonic, sleep

from cams_runtime import RECOVERY_BUDGET_SECONDS
from local_pipeline.gcs_object_store import GCSObjectStore, RemoteObjectStoreError
from local_pipeline.operational_diagnostics import attach_error_fields, emit, error_fields


def tls_failure_kind(error):
    """Inspect typed SDK wrappers, never log/parse exception text or URLs."""
    pending, seen, kinds = [error], set(), set()
    while pending and len(seen) < 32:
        item = pending.pop()
        if not isinstance(item, BaseException) or id(item) in seen:
            continue
        seen.add(id(item))
        if isinstance(item, (ssl.SSLCertVerificationError, ssl.CertificateError)):
            kinds.add('tls_certificate_invalid')
        elif isinstance(item, (ssl.SSLEOFError, ssl.SSLZeroReturnError)):
            kinds.add('tls_connection_interrupted')
        elif isinstance(item, ssl.SSLError):
            reason = getattr(item, 'reason', None)
            kinds.add('tls_certificate_invalid' if reason == 'CERTIFICATE_VERIFY_FAILED'
                      else 'tls_connection_interrupted' if reason == 'UNEXPECTED_EOF_WHILE_READING'
                      else 'tls_unclassified')
        elif any(cls.__name__ == 'SSLError' and cls.__module__.startswith(
                ('requests.exceptions', 'urllib3.exceptions')) for cls in type(item).__mro__):
            kinds.add('tls_unclassified')
        pending.extend(value for value in (*item.args, item.__cause__,
            None if item.__suppress_context__ else item.__context__,
            getattr(item, 'reason', None)) if isinstance(value, BaseException))
    # A certificate error always wins, even if an outer layer reports EOF.
    for kind in ('tls_certificate_invalid', 'tls_connection_interrupted', 'tls_unclassified'):
        if kind in kinds:
            return kind
    return None


class CamsReadRecovery:
    def __init__(self, *, clock=monotonic, wait=sleep):
        self.clock, self.wait = clock, wait
        self.deadline = clock() + RECOVERY_BUDGET_SECONDS
        self.retries = 0

    def pause_for_retry(self, error):
        delay = self.retries + 1
        if self.retries >= 2 or self.clock() + delay + 30 >= self.deadline:
            return False
        self.retries += 1
        emit('cams_storage_read_retry', **{**error_fields(error), 'provider': 'cams',
             'attempt': self.retries, 'retry_after_seconds': delay, 'severity': 'WARNING'})
        self.wait(delay)
        return True


class CamsObjectStore(GCSObjectStore):
    def __init__(self, bucket, *, recovery):
        super().__init__(bucket)
        self.recovery = recovery

    def _call(self, operation, *, _operation=None, _key=None, **kwargs):
        while True:
            failure = [None]

            def observed(**sdk_kwargs):
                try:
                    return operation(**sdk_kwargs)
                except Exception as error:
                    failure[0] = tls_failure_kind(error)
                    raise

            try:
                return super()._call(observed, _operation=_operation, _key=_key, **kwargs)
            except RemoteObjectStoreError as error:
                if failure[0]:
                    error.retryable = failure[0] == 'tls_connection_interrupted'
                    attach_error_fields(error, transport_reason=failure[0], retryable=error.retryable)
                if (_operation not in {'metadata_read', 'metadata_list', 'download'}
                        or not error.retryable or not self.recovery.pause_for_retry(error)):
                    raise
