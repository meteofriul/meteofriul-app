"""ADS retrieval with durable submission checkpoints; no scheduler or deploy.

An intent without a saved job requires reconciliation, never another POST.
Only allowlisted credential-free JSON artifacts cross the storage boundary.
"""
import base64
from datetime import datetime
import json
from pathlib import Path
from uuid import UUID

from retrieve_cams import retrieve, _preflight_plan, PilotError, _load_json_record, _request_record, _recover_completed_download
from cams_request_plan import DATASET, request_sha256, strict_json_loads
from local_pipeline.sqlite_object_store import ObjectNotFound, PreconditionFailed
from local_pipeline.cams_artifact_checkpoint import (
    FILE_LIMITS, read_artifacts, save_artifacts, read_local_file, restore_local_file,
)
from local_pipeline.operational_diagnostics import emit

FILES = ("request-plan.json", "request.json", "submission-intent.json")
MAX_CHECKPOINT = 2 * 1024**2


def remote_cams_context(directory, *, request_plan_path=None):
    """Validate exact local submission identity without constructing an ADS client."""
    directory = Path(directory)
    plan_path = Path(request_plan_path) if request_plan_path is not None else directory / "request-plan.json"
    plan, plan_bytes, plan_hash, scope = _preflight_plan(plan_path, "fvg")
    if read_local_file(directory / "request-plan.json", MAX_CHECKPOINT) != plan_bytes:
        raise PilotError("Remote CAMS checkpoint plan differs")
    expected_request = _request_record(plan, plan_hash, "fvg", scope)
    if _load_json_record(directory / "request.json", maximum_bytes=MAX_CHECKPOINT, label="Saved request") != expected_request:
        raise PilotError("Remote CAMS checkpoint request differs")
    identity = {"dataset": DATASET, "run_date": plan["run_date"],
                "request_plan_sha256": plan_hash, "request_sha256": expected_request["request_sha256"]}
    intent = _load_json_record(directory / "submission-intent.json", maximum_bytes=16384, label="Submission intent")
    if (set(intent) != {"schema_version", "at_utc", "dataset", "scope", "run_date",
                       "request_plan_sha256", "request_sha256", "post_retries"}
            or intent.get("schema_version") != 2 or intent.get("scope") != "fvg"
            or intent.get("post_retries") != 0
            or any(intent.get(name) != value for name, value in identity.items())):
        raise PilotError("Remote CAMS checkpoint submission intent differs")
    try:
        if datetime.fromisoformat(intent["at_utc"].replace("Z", "+00:00")).tzinfo is None:
            raise ValueError()
    except (ValueError, TypeError, AttributeError):
        raise PilotError("Remote CAMS checkpoint intent timestamp is invalid") from None
    job = _load_json_record(directory / "job.json", maximum_bytes=16384, label="Saved job")
    if (set(job) != {"schema_version", "dataset", "request_id", "scope", "run_date",
                    "request_plan_sha256", "request_sha256"}
            or job.get("schema_version") != 2 or job.get("scope") != "fvg"
            or any(job.get(name) != value for name, value in identity.items())):
        raise PilotError("Remote CAMS checkpoint job differs")
    try:
        if str(UUID(job["request_id"])) != job["request_id"]:
            raise ValueError()
    except (ValueError, TypeError, AttributeError):
        raise PilotError("Remote CAMS checkpoint job identifier is invalid") from None
    identity["request_id"] = job["request_id"]
    return f"state/ads/{plan['run_date']}/{identity['request_sha256']}/", identity


def retrieve_remote_cams(*, credentials_path, request_plan_path, scratch,
                         state_store, max_wait=45, retrieve_fn=retrieve, reconcile_fn=None):
    plan, plan_bytes, _, _ = _preflight_plan(request_plan_path, "fvg")
    request_hash = request_sha256(plan["request_groups"][0]["request"])
    prefix = f"state/ads/{plan['run_date']}/{request_hash}/"
    directory = Path(scratch) / ("cams-" + plan["run_date"])
    if directory.exists():
        raise PilotError("Remote acquisition requires fresh scratch directory")

    def checkpoint(stage, source):
        names = FILES + (("job.json",) if stage == "submitted" else ())
        files = {}
        for name in names:
            path = source / name
            files[name] = base64.b64encode(read_local_file(path, MAX_CHECKPOINT)).decode("ascii")
        raw = json.dumps(files, sort_keys=True, separators=(",", ":")).encode()
        if len(raw) > MAX_CHECKPOINT:
            raise PilotError("Acquisition checkpoint too large")
        # In particular intent MUST be create-only, even if contents match.
        try:
            state_store.put(prefix + stage + ".json", raw, content_type="application/json")
        except PreconditionFailed:
            if stage != "submitted" or state_store.get(prefix + stage + ".json").body != raw:
                raise
        except Exception as original_error:
            if stage != "submitted":
                raise
            try:
                if state_store.get(prefix + stage + ".json").body != raw:
                    raise original_error
            except Exception:
                raise original_error
        if state_store.get(prefix + stage + ".json").body != raw:
            raise PilotError("Remote CAMS checkpoint readback differs")

    def restore(saved, names):
        if not 1 <= len(saved.body) <= MAX_CHECKPOINT:
            raise PilotError("Invalid acquisition checkpoint size")
        try:
            records = strict_json_loads(saved.body)
            if not isinstance(records, dict) or set(records) != set(names):
                raise ValueError()
            decoded = {name: base64.b64decode(value, validate=True) for name, value in records.items()}
            if (decoded["request-plan.json"] != plan_bytes
                    or any(not 1 <= len(raw) <= MAX_CHECKPOINT for raw in decoded.values())):
                raise ValueError()
        except (ValueError, TypeError):
            raise PilotError("Invalid acquisition checkpoint") from None
        directory.mkdir()
        for name, raw in decoded.items():
            restore_local_file(directory / name, raw)

    def finish(report):
        if isinstance(report, dict) and report.get("status") == "downloaded_pending_decode_validation":
            _, identity = remote_cams_context(directory, request_plan_path=request_plan_path)
            if _recover_completed_download(directory / "source.grib", identity=identity) is None:
                raise PilotError("Remote CAMS download completion record is missing")
            files = {name: read_local_file(directory / name, cap)
                     for name, cap in FILE_LIMITS["download"].items()}
            save_artifacts(state_store, prefix=prefix, stage="download", identity=identity, files=files)
            emit("cams_download_checkpoint", provider="cams", run_date=plan["run_date"], status="persisted")
        return report

    try:
        saved = state_store.get(prefix + "submitted.json")
    except ObjectNotFound:
        try:
            saved = state_store.get(prefix + "intent.json")
        except ObjectNotFound:
            return finish(retrieve_fn(credentials_path, request_plan_path=request_plan_path,
                artifacts_directory=directory, scope="fvg", max_wait=max_wait,
                checkpoint_saver=checkpoint))
        restore(saved, FILES)
        from reconcile_cams_job import ReconciliationInconclusive
        if reconcile_fn is None:
            from reconcile_cams_job import reconcile
            reconcile_fn = reconcile
        try:
            result = reconcile_fn(credentials_path, directory, request_plan_path=request_plan_path, scope="fvg")
        except ReconciliationInconclusive:
            emit("cams_submission_reconciliation", provider="cams", run_date=plan["run_date"],
                 status="pending", reason_code="reconciliation_inconclusive")
            return {"status": "submission_reconciliation_pending", "run_date": plan["run_date"],
                    "reason_code": "reconciliation_inconclusive"}
        if result.get("result") != "unique_existing_job_restored":
            emit("cams_submission_reconciliation", provider="cams", run_date=plan["run_date"],
                 status="pending", reason_code="reconciliation_not_unique")
            return {"status": "submission_reconciliation_pending", "run_date": plan["run_date"],
                    "reason_code": "reconciliation_not_unique"}
        remote_cams_context(directory, request_plan_path=request_plan_path)
        checkpoint("submitted", directory)
    else:
        restore(saved, FILES + ("job.json",))

    try:
        state_store.head(prefix + "artifacts/download.json")
    except ObjectNotFound:
        pass
    else:
        _, identity = remote_cams_context(directory, request_plan_path=request_plan_path)
        restored = read_artifacts(state_store, prefix=prefix, stage="download", identity=identity)
        if restored is None:
            raise PilotError("Remote CAMS download checkpoint disappeared")
        for name, raw in restored.items():
            restore_local_file(directory / name, raw)
        if _recover_completed_download(directory / "source.grib", identity=identity) is None:
            raise PilotError("Remote CAMS download checkpoint is incomplete")
        emit("cams_download_checkpoint", provider="cams", run_date=plan["run_date"], status="restored")
    # Existing retrieval preflight revalidates exact job/request/plan bindings.
    return finish(retrieve_fn(credentials_path, request_plan_path=request_plan_path,
        resume=directory, scope="fvg", max_wait=max_wait,
        checkpoint_saver=checkpoint))
