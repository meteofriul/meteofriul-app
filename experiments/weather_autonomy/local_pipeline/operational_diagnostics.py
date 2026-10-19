"""Small, secret-free diagnostics for the pilot weather pipeline.

Never serialize provider exception text, URLs, response bodies or credentials.
Infrastructure adapters can attach typed, already-safe scalar details. Other
errors retain their type and local source location; only exact messages from
the controlled vocabulary below may be emitted. Diagnostics do not schedule,
retry or change the outcome of an operation.
"""
from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime, timezone
import json
import math
import re
from time import monotonic
from typing import Mapping


_CONTEXT = ContextVar("weather_operational_context", default={})
_TOKEN = re.compile(r"[A-Za-z0-9_][A-Za-z0-9_.:-]{0,127}\Z")
_KEY = re.compile(r"[A-Za-z0-9_./-]{1,256}\Z")
_RUN = re.compile(r"\d{8}T\d{6}Z\Z")
_MUNICIPALITY = re.compile(r"(?:^|/)municipalities/(\d{6})\.json\Z")
_FIELDS = frozenset({
    "provider", "job", "stage", "source_run_id", "run_id", "run_date", "attempt_id",
    "execution_id", "operation", "http_method", "object_key", "municipality_code", "status",
    "reason_code", "error_type", "cause_type", "error_summary", "cause_summary",
    "http_status", "retryable", "failure_file", "failure_function", "failure_line",
    "validation_status", "publication_status", "acquisition_status", "payload_count", "validated_count",
    "municipality_count",
    "reused_payload_count", "manifest_reused", "latest_updated", "attempt",
    "retry_after_seconds", "elapsed_seconds", "duration_seconds", "exit_code",
    "expected_count", "actual_count", "core_stage_idempotent", "pollen_stage_idempotent",
    "family_idempotent", "family_latest_updated", "severity", "event",
    "compatible_rows", "date_rows", "leadcount", "maxlead", "metadata_sha256",
    "constraints_rows", "missing_model_rows", "missing_level_rows", "missing_type_rows",
    "missing_time_rows", "missing_variable_rows", "missing_variable_count", "missing_lead_count",
    "quality_available", "quality_reason", "quality_sha256", "raw_diagnostic_samples", "diagnostic_samples_truncated",
    "quality_municipality_hours", "quality_municipalities", "quality_grid_hours",
    "quality_humidity_anomaly_rows", "quality_humidity_anomaly_grid_hours",
    "quality_null_precipitation", "quality_null_rain", "quality_null_snow",
    "quality_resolution_null_precipitation", "quality_resolution_null_rain", "quality_resolution_null_snow",
}) | frozenset(
    f"quality_tolerance_{metric}_{field}"
    for field in ("precipitation", "rain", "snow")
    for metric in ("expected", "verified")
) | frozenset(
    f"quality_guard_{field}_{reason}"
    for field in ("precipitation", "rain", "snow")
    for reason in ("resolution_metadata_missing", "resolution_budget_exceeded", "missing_or_invalid_accumulation")
)
_SAFE_MESSAGES = frozenset({
    "CAMS artifact storage integrity failed", "CAMS artifact immutable conflict",
    "CAMS artifact descriptor is invalid", "CAMS artifact checkpoint is incomplete",
    "CAMS artifact chunk hash differs", "CAMS artifact file hash differs",
    "CAMS decoded checkpoint requires a verified download",
    "CAMS decoded artifacts changed after validation", "CAMS prepared publication catalog differs",
    "Remote CAMS checkpoint plan differs", "Remote CAMS checkpoint request differs",
    "Remote CAMS checkpoint submission intent differs", "Remote CAMS checkpoint intent timestamp is invalid",
    "Remote CAMS checkpoint job differs", "Remote CAMS checkpoint job identifier is invalid",
    "Remote CAMS checkpoint readback differs", "Remote CAMS download completion record is missing",
    "Remote CAMS download checkpoint disappeared", "Remote CAMS download checkpoint is incomplete",
    "Invalid acquisition checkpoint", "Invalid acquisition checkpoint size",
    "CAMS artifact file exceeds its byte limit", "CAMS scratch artifact differs from checkpoint",
    "public_reader_not_current", "public_reader_unavailable", "public_uv_run_mismatch",
    "public_cams_run_mismatch", "public_uv_pointer_changed", "public_cams_pointer_changed",
    "lease expired during remote state commit", "remote state changed repeatedly",
    "latest CAS retry budget exhausted", "revocation CAS retry budget exhausted",
    "latest disappeared after CAS", "latest regressed after CAS",
    "latest changed to a conflicting manifest after CAS",
    "latest supersession did not advance its revision",
    "immutable object disappeared after create conflict",
    "referenced run manifest is missing", "stored run manifest content type is invalid",
    "stored run manifest fails contract-v1 validation",
    "stored run manifest has the wrong run identity", "stored run manifest metadata is invalid",
    "stored run is missing a municipality payload",
    "stored municipality payload differs from its manifest descriptor",
    "stored municipality payload metadata is invalid",
    "stored run payloads fail contract-v1 validation", "latest manifest path is not canonical",
    "stored manifest differs from publication intent", "recovery manifest changed during verification",
    "recovery manifest SHA-256 is invalid", "publication-only recovery is ICON-only",
    "invalid ICON checkpoint slot", "ICON checkpoint differs from publication intent",
    "ICON checkpoint expanded size exceeds limit", "ICON checkpoint compressed size exceeds limit",
    "invalid ICON checkpoint size", "invalid ICON checkpoint envelope",
    "ICON checkpoint cannot be authenticated", "ICON checkpoint storage integrity failed",
    "ICON checkpoint immutable conflict", "invalid ICON execution slot",
    "invalid ICON acquisition claim", "invalid ICON terminal outcome",
    "invalid remote intent size", "non-canonical remote intent",
    "remote publication identity conflict", "remote publication input conflict",
    "ICON recovery requires an ICON publication intent",
    "published_at cannot regress",
    "ICON public source returned an unexpected HTTP status",
    "latest content type is invalid", "latest metadata is invalid",
    "invalid remote object metadata", "remote object integrity mismatch",
    "storage object not found", "storage generation precondition failed",
    "storage request timed out", "storage request was throttled",
    "storage service temporarily unavailable", "storage transport failed",
    "storage access denied", "storage authentication failed", "storage request failed",
    "ICON publication identity is inconsistent", "CAMS publication identity is inconsistent",
    "Prepared ICON manifest fingerprint changed", "Materializer omitted ICON",
    "Materializer returned incomplete ICON", "Materialized ICON run differs from its publication intent",
    "ICON inputs changed after publication intent resolution",
    "Prepared ICON data differs from its publication intent",
    "Materialized ICON family does not match the authoritative catalog",
    "Decoded CAMS archive is not the complete 215x28x97 matrix",
    "CAMS decode analysis does not confirm 215x28x97 coverage",
    "CAMS constraints do not contain one unambiguous surface ensemble row",
    "CAMS constraints do not contain unambiguous complete surface ensemble coverage",
    "CAMS catalogue sanity status is not available",
    "CAMS catalogue is explicitly disabled",
    "exception details withheld; inspect the typed error and local source location",
})


def safe_object_key(value):
    """Only a relative storage key, never an endpoint, signed URL or local path."""
    if not isinstance(value, str) or not _KEY.fullmatch(value):
        return None
    return value if all(part not in {"", ".", ".."} for part in value.split("/")) else None


def safe_source_run_id(value):
    return value if isinstance(value, str) and _RUN.fullmatch(value) else None


def _safe_fields(fields):
    safe = {}
    for key, value in fields.items():
        if key not in _FIELDS or value is None:
            continue
        if key == "object_key":
            value = safe_object_key(value)
        elif key in {"source_run_id", "run_id"}:
            value = safe_source_run_id(value)
        elif key == "municipality_code":
            value = value if isinstance(value, str) and re.fullmatch(r"\d{6}", value) else None
        elif key in {"error_summary", "cause_summary"}:
            value = value if isinstance(value, str) and value in _SAFE_MESSAGES else None
        elif isinstance(value, str):
            value = value if _TOKEN.fullmatch(value) else None
        elif not isinstance(value, (bool, int, float)) or (isinstance(value, float) and not math.isfinite(value)):
            value = None
        if value is not None:
            safe[key] = value
    return safe


def attach_error_fields(error, **fields):
    """Attach only validated diagnostic scalars; never the original SDK error."""
    try:
        previous = getattr(error, "weather_diagnostics", {})
        previous = previous if isinstance(previous, Mapping) else {}
        error.weather_diagnostics = {**_CONTEXT.get(), **_safe_fields(previous), **_safe_fields(fields)}
    except Exception:
        pass
    return error


def error_fields(error):
    """Retain typed causes/context without ever stringifying untrusted errors."""
    chain, seen = [], set()
    current = error
    while isinstance(current, BaseException) and id(current) not in seen and len(chain) < 8:
        seen.add(id(current))
        chain.append(current)
        current = current.__cause__ or (None if current.__suppress_context__ else current.__context__)
    result = dict(_CONTEXT.get())
    for item in reversed(chain):
        attached = getattr(item, "weather_diagnostics", {})
        if isinstance(attached, Mapping):
            result.update(_safe_fields(attached))
    adapter_error_type = result.get("error_type")
    result["error_type"] = type(error).__name__
    if adapter_error_type and adapter_error_type != result["error_type"]:
        result["cause_type"] = adapter_error_type
    elif len(chain) > 1:
        result["cause_type"] = type(chain[-1]).__name__
    if "error_summary" not in result:
        # Only exact, controlled messages, even for local validation errors.
        args = getattr(error, "args", ())
        result["error_summary"] = (
            args[0] if len(args) == 1 and isinstance(args[0], str) and args[0] in _SAFE_MESSAGES
            else "exception details withheld; inspect the typed error and local source location"
        )
    for item in chain:
        trace = item.__traceback__
        while trace is not None:
            filename = trace.tb_frame.f_code.co_filename.replace("\\", "/")
            if "/local_pipeline/" in filename or filename.endswith((
                "/cloud_worker.py", "/cams_request_plan.py", "/retrieve_cams.py", "/publish_remote_icon.py",
            )):
                result.update(failure_file=filename.rsplit("/", 1)[-1],
                              failure_function=trace.tb_frame.f_code.co_name,
                              failure_line=trace.tb_lineno)
            trace = trace.tb_next
    return _safe_fields(result)


def emit(event, **safe_fields):
    """Emit one bounded JSON log. Logging failure never changes pipeline results."""
    fields = _safe_fields({**_CONTEXT.get(), **safe_fields, "event": event})
    fields.setdefault("severity", "INFO")
    fields["timestamp"] = datetime.now(timezone.utc).isoformat(timespec="milliseconds")
    try:
        print(json.dumps(fields, sort_keys=True, separators=(",", ":")), flush=True)
    except Exception:
        pass


@contextmanager
def phase(name, **context):
    """Attach the innermost failed stage; preserve SystemExit and other failures."""
    token = _CONTEXT.set(_safe_fields({**_CONTEXT.get(), **_safe_fields(context), "stage": name}))
    started = monotonic()
    emit("phase_started", status="started")
    try:
        yield
    except BaseException as error:
        # Inner phase context wins when this exception crosses outer phases.
        existing = getattr(error, "weather_diagnostics", {})
        existing = existing if isinstance(existing, Mapping) else {}
        attach_error_fields(error, **{**_CONTEXT.get(), **existing})
        emit("phase_failed", **{**error_fields(error), "severity": "ERROR", "status": "failed",
                               "elapsed_seconds": round(monotonic() - started, 3)})
        raise
    else:
        emit("phase_completed", status="completed", elapsed_seconds=round(monotonic() - started, 3))
    finally:
        _CONTEXT.reset(token)


__all__ = ["attach_error_fields", "emit", "error_fields", "phase", "safe_object_key", "safe_source_run_id"]
