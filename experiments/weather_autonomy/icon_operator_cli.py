"""Explicit national ICON operator inspection and isolated recovery entrypoint.

`inspect` is read-only. `--execute` is usable only from a separately approved
Cloud Run operator job with the reviewed image and a live maintenance window.
The ordinary scheduled national worker never calls this module.
"""
import argparse
import base64
from datetime import datetime, timezone
import hashlib
import json
import os
import re
from urllib.parse import urlsplit


_DIGEST = re.compile(r"sha256:[a-f0-9]{64}\Z")
_COMMIT = re.compile(r"[a-f0-9]{40}\Z")
_NAME = re.compile(r"[a-z][a-z0-9-]{0,62}\Z")
_PROJECT = re.compile(r"[a-z][a-z0-9-]{5,62}\Z")
_BUCKET = re.compile(r"[a-z0-9][a-z0-9._-]{2,222}\Z")
_PREFIX = re.compile(r"[A-Za-z0-9_-]+\Z")


def _utc(value):
    if not isinstance(value, str):
        raise ValueError("invalid ICON evidence timestamp")
    try:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except ValueError:
        raise ValueError("invalid ICON evidence timestamp") from None


def _image(job):
    try:
        containers = job["template"]["template"]["containers"]
        if len(containers) != 1:
            raise ValueError()
        return containers[0]["image"], containers[0].get("env", [])
    except (KeyError, IndexError, TypeError, ValueError):
        raise ValueError("ICON Cloud Run job template is incomplete") from None


def _env_value(items, name):
    values = [item.get("value") for item in items if isinstance(item, dict) and item.get("name") == name]
    if len(values) != 1 or not isinstance(values[0], str):
        raise ValueError("ICON Cloud Run job environment is ambiguous")
    return values[0]


def _completed(row):
    value = row.get("completionTime")
    if value is None:
        return False
    if not isinstance(value, str) or not value.endswith("Z"):
        raise ValueError("ICON execution completion timestamp is invalid")
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise ValueError("ICON execution completion timestamp is invalid") from None
    return True


def _inventory_bytes(args):
    if bool(args.writer_inventory) == bool(args.writer_inventory_b64):
        raise ValueError("exactly one ICON writer inventory source required")
    if args.writer_inventory_b64:
        try:
            data = base64.b64decode(args.writer_inventory_b64, altchars=b"-_", validate=True)
        except (ValueError, base64.binascii.Error):
            raise ValueError("invalid ICON writer inventory encoding") from None
    else:
        with open(args.writer_inventory, "rb") as stream:
            data = stream.read(4097)
    if len(data) > 4096 or hashlib.sha256(data).hexdigest() != args.writer_inventory_sha256:
        raise ValueError("ICON writer inventory size or digest differs")
    value = json.loads(data)
    if not isinstance(value, dict):
        raise ValueError("ICON writer inventory is not an object")
    return value


class LiveCloudEvidence:
    """Read-only REST adapter. Every guard call fetches all pages afresh."""

    def __init__(self, session, *, project, region, job, scheduler, operator_job,
                 image, source_commit, state_bucket, data_bucket, object_prefix, writer_inventory,
                 operator_service_account=None, execution=None, clock=None):
        for value, pattern in ((project, _PROJECT), (region, _NAME), (job, _NAME),
                               (scheduler, _NAME), (operator_job, _NAME),
                               (state_bucket, _BUCKET), (data_bucket, _BUCKET),
                               (object_prefix, _PREFIX)):
            if not isinstance(value, str) or not pattern.fullmatch(value):
                raise ValueError("invalid ICON operator resource identity")
        if (not isinstance(image, str) or "@" not in image
                or not _DIGEST.fullmatch(image.rsplit("@", 1)[-1])
                or not isinstance(source_commit, str) or not _COMMIT.fullmatch(source_commit)
                or operator_job == job):
            raise ValueError("approved isolated ICON image and operator job required")
        self.session = session
        self.project, self.region, self.job = project, region, job
        self.scheduler, self.operator_job, self.image = scheduler, operator_job, image
        self.source_commit = source_commit
        self.state_bucket, self.data_bucket, self.object_prefix = state_bucket, data_bucket, object_prefix
        self.writer_inventory = writer_inventory
        self.operator_service_account = operator_service_account
        self.execution = execution
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.run_root = f"projects/{project}/locations/{region}/jobs/"
        self.scheduler_name = f"projects/{project}/locations/{region}/jobs/{scheduler}"

    def _get(self, url):
        response = self.session.get(url, timeout=15)
        response.raise_for_status()
        value = response.json()
        if not isinstance(value, dict):
            raise ValueError("ICON cloud response is not an object")
        return value

    def _run_job(self, name):
        return self._get("https://run.googleapis.com/v2/" + self.run_root + name)

    def _executions(self, job):
        url = "https://run.googleapis.com/v2/" + self.run_root + job + "/executions?pageSize=100"
        seen = set()
        for _ in range(100):
            if url in seen:
                raise ValueError("ICON execution pagination repeated")
            seen.add(url)
            page = self._get(url)
            rows = page.get("executions", [])
            if not isinstance(rows, list):
                raise ValueError("ICON execution list is invalid")
            for row in rows:
                if not isinstance(row, dict) or not isinstance(row.get("name"), str) or not row["name"].startswith(self.run_root + job + "/executions/"):
                    raise ValueError("ICON execution identity is invalid")
                yield row
            token = page.get("nextPageToken")
            if not token:
                return
            if not isinstance(token, str) or len(token) > 2048:
                raise ValueError("ICON execution page token is invalid")
            from urllib.parse import quote
            url = ("https://run.googleapis.com/v2/" + self.run_root + job
                   + "/executions?pageSize=100&pageToken=" + quote(token, safe=""))
        raise ValueError("ICON execution pagination exceeded limit")

    def _writer_inventory_valid(self, now):
        item = self.writer_inventory
        expected = {"schema_version", "project", "region", "state_bucket", "data_bucket",
                    "object_prefix", "scheduled_job", "operator_job", "approved_image",
                    "approved_source_commit", "other_writers_blocked", "observed_at_utc"}
        return (isinstance(item, dict) and set(item) == expected and item["schema_version"] == 1
            and item["project"] == self.project and item["region"] == self.region
            and item["state_bucket"] == self.state_bucket and item["data_bucket"] == self.data_bucket
            and item["object_prefix"] == self.object_prefix and item["scheduled_job"] == self.job
            and item["operator_job"] == self.operator_job and item["approved_image"] == self.image
            and item["approved_source_commit"] == self.source_commit
            and item["other_writers_blocked"] is True
            and 0 <= (now - _utc(item["observed_at_utc"])).total_seconds() <= 60)

    def guard(self):
        now = self.clock().astimezone(timezone.utc)
        scheduler = self._get("https://cloudscheduler.googleapis.com/v1/" + self.scheduler_name)
        target = scheduler.get("httpTarget", {}).get("uri") if isinstance(scheduler.get("httpTarget"), dict) else None
        parsed = urlsplit(target) if isinstance(target, str) else None
        target_ok = (parsed is not None and parsed.scheme == "https" and parsed.netloc == "run.googleapis.com"
            and parsed.path == "/v2/" + self.run_root + self.job + ":run" and not parsed.query and not parsed.fragment)
        if scheduler.get("name") != self.scheduler_name or scheduler.get("state") != "PAUSED" or not target_ok:
            raise ValueError("ICON scheduler is not paused on the expected job")
        job = self._run_job(self.job)
        image, env = _image(job)
        if (job.get("name") != self.run_root + self.job or image != self.image
                or _env_value(env, "WEATHER_ICON_AUTOMATIC_RECOVERY_ENABLED") != "true"
                or _env_value(env, "WEATHER_SOURCE_COMMIT") != self.source_commit):
            raise ValueError("ICON scheduled job is not the approved fenced image")
        active = [row for row in self._executions(self.job) if not _completed(row)]
        if active:
            raise ValueError("ICON scheduled job has active executions")
        if not self._writer_inventory_valid(now):
            raise ValueError("ICON other-writer isolation evidence is missing or stale")
        operator = None
        if self.execution is not None:
            operator = self._run_job(self.operator_job)
            operator_image, operator_env = _image(operator)
            if operator.get("name") != self.run_root + self.operator_job or operator_image != self.image:
                raise ValueError("ICON operator job image differs")
            try:
                template = operator["template"]
                task = template["template"]
                container = task["containers"][0]
                memory = container["resources"]["limits"]["memory"]
                timeout = task["timeout"]
                service_account = task["serviceAccount"]
                isolated = (template["taskCount"] == 1 and template["parallelism"] == 1
                    and task["maxRetries"] == 0 and timeout.endswith("s")
                    and float(timeout[:-1]) >= 1800
                    and memory in {"2Gi", "3Gi", "4Gi", "5Gi", "6Gi", "7Gi", "8Gi"}
                    and service_account == self.operator_service_account
                    and container["command"] == ["python", "icon_operator_cli.py"]
                    and _env_value(operator_env, "WEATHER_NATIONAL_ACQUISITION") == "approved"
                    and _env_value(operator_env, "WEATHER_SOURCE_COMMIT") == self.source_commit)
            except (KeyError, IndexError, TypeError, ValueError):
                isolated = False
            if not isolated:
                raise ValueError("ICON isolated operator runtime is unverified")
            active_operator = [row["name"].rsplit("/", 1)[-1] for row in self._executions(self.operator_job)
                               if not _completed(row)]
            if active_operator != [self.execution]:
                raise ValueError("ICON operator execution is not isolated")
        fingerprint = {"scheduler": scheduler["name"], "scheduler_state": scheduler["state"],
            "scheduler_target": target, "scheduled_job": job["name"],
            "scheduled_image": image, "scheduled_etag": job.get("etag"),
            "operator_job": operator["name"] if operator else None,
            "operator_etag": operator.get("etag") if operator else None,
            "source_commit": self.source_commit, "writer_inventory": self.writer_inventory,
            "active_executions": 0}
        evidence_hash = hashlib.sha256(json.dumps(fingerprint, sort_keys=True,
            separators=(",", ":"), ensure_ascii=True).encode("utf-8")).hexdigest()
        return {"scheduler_paused": True, "active_executions": 0,
                "deployed_fence_aware": True, "legacy_invocations_blocked": True,
                "observed_at_utc": now.replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "evidence_sha256": evidence_hash}


def main(argv=None):
    parser = argparse.ArgumentParser(description="Inspect or explicitly recover the national ICON manual-review fence")
    for key in ("project", "region", "job", "scheduler", "operator-job", "state-bucket",
                "data-bucket", "object-prefix", "approved-image", "approved-source-commit"):
        parser.add_argument("--" + key, required=True)
    parser.add_argument("--writer-inventory-sha256")
    parser.add_argument("--writer-inventory")
    parser.add_argument("--writer-inventory-b64")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--operator-service-account")
    for key in ("incident-id", "expected-etag", "expected-owner-sha256", "failed-run",
                "new-run", "published-run"):
        parser.add_argument("--" + key)
    args = parser.parse_args(argv)
    if args.execute and (os.environ.get("CLOUD_RUN_JOB") != args.operator_job
            or os.environ.get("GOOGLE_CLOUD_PROJECT") != args.project
            or not os.environ.get("CLOUD_RUN_EXECUTION", "").startswith(args.operator_job + "-")
            or os.environ.get("WEATHER_NATIONAL_ACQUISITION") != "approved"
            or not args.operator_service_account or not args.writer_inventory_b64
            or not args.writer_inventory_sha256):
        raise ValueError("ICON execution requires the approved isolated Cloud Run operator job")
    os.environ["WEATHER_CLOUD_PROJECT"] = args.project
    os.environ["WEATHER_STATE_BUCKET"] = args.state_bucket
    os.environ["WEATHER_DATA_BUCKET"] = args.data_bucket
    os.environ["WEATHER_OBJECT_PREFIX"] = args.object_prefix
    import google.auth
    from google.auth.transport.requests import AuthorizedSession
    from google.cloud import storage
    from local_pipeline.gcs_object_store import GCSObjectStore
    from local_pipeline.icon_recovery import Recovery
    from local_pipeline.contract_v1 import canonical_json_bytes
    from national_cloud_assets import load_inputs
    from national_cloud_publication import read_pointer
    credentials, authenticated_project = google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
    if authenticated_project != args.project:
        raise ValueError("ICON operator authenticated project differs")
    inventory = _inventory_bytes(args) if (args.writer_inventory or args.writer_inventory_b64) else None
    execution = os.environ.get("CLOUD_RUN_EXECUTION") if args.execute else None
    evidence = LiveCloudEvidence(AuthorizedSession(credentials), project=args.project,
        region=args.region, job=args.job, scheduler=args.scheduler, operator_job=args.operator_job,
        image=args.approved_image, source_commit=args.approved_source_commit,
        state_bucket=args.state_bucket, data_bucket=args.data_bucket,
        object_prefix=args.object_prefix, writer_inventory=inventory,
        operator_service_account=args.operator_service_account, execution=execution)
    try:
        evidence.guard()
    except Exception:
        if args.execute:
            raise
        guard_status = "blocked"
    else:
        guard_status = "ready"
    client = storage.Client(project=args.project, credentials=credentials)
    state = GCSObjectStore(client.bucket(args.state_bucket))
    data = GCSObjectStore(client.bucket(args.data_bucket))
    catalog, points = load_inputs()
    active = Recovery(state, "national").active()
    pointer, _etag = read_pointer(data, catalog)
    observed = {"active_phase": active.record["phase"] if active else None,
        "active_run": active.record["source_run_id"] if active else None,
        "active_etag": active.etag if active else None,
        "active_sha256": hashlib.sha256(canonical_json_bytes(active.record)).hexdigest() if active else None,
        "published_run": pointer["source_run_id"]}
    if not args.execute:
        print(json.dumps({"status": "inspected", "operator_guard": guard_status,
            **observed}, sort_keys=True), flush=True)
        return 0
    if (not all((args.incident_id, args.expected_etag, args.expected_owner_sha256,
                 args.failed_run, args.new_run, args.published_run))
            or observed["active_phase"] != "manual_review"
            or observed["active_etag"] != args.expected_etag
            or observed["active_sha256"] != args.expected_owner_sha256
            or observed["published_run"] != args.published_run):
        raise ValueError("ICON operator evidence differs from live state")
    import eccodes  # noqa: F401 -- prove the acquisition decoder exists in this image.
    import numpy  # noqa: F401
    from national_cloud_worker import run_operator_once
    result = run_operator_once(state, data, catalog, points, now=datetime.now(timezone.utc),
        execution=execution, operator={"incident_id": args.incident_id,
            "expected_etag": args.expected_etag, "expected_owner_sha256": args.expected_owner_sha256,
            "failed_run": args.failed_run, "new_run": args.new_run,
            "published_run": args.published_run}, quiescent=evidence.guard)
    print(json.dumps(result, sort_keys=True), flush=True)
    return 0 if result["status"] in {"published", "no_op"} else 1


if __name__ == "__main__":
    from local_pipeline.operational_diagnostics import emit, error_fields
    try:
        raise SystemExit(main())
    except Exception as error:
        reason = {
            "ICON scheduler is not paused on the expected job": "scheduler_not_paused_or_target_changed",
            "ICON scheduled job is not the approved fenced image": "scheduled_image_unverified",
            "ICON scheduled job has active executions": "scheduled_execution_active",
            "ICON other-writer isolation evidence is missing or stale": "writer_isolation_unverified",
            "ICON operator job image differs": "operator_image_unverified",
            "ICON isolated operator runtime is unverified": "operator_runtime_unverified",
            "ICON operator execution is not isolated": "operator_execution_not_isolated",
            "ICON operator authenticated project differs": "project_identity_mismatch",
            "ICON execution requires the approved isolated Cloud Run operator job": "operator_runtime_required",
            "ICON operator evidence differs from live state": "fence_evidence_changed",
        }.get(str(error), "operator_validation_failed") if type(error) is ValueError else "operator_error"
        emit("icon_operator_failed", **{**error_fields(error), "provider": "icon",
            "stage": "operator", "reason_code": reason, "status": "failed", "severity": "ERROR"})
        raise SystemExit(2) from None
