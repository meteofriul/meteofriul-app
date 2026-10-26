"""Bounded local ADS acquisition. Never print/store credentials or signed URLs.

Requires the user to have personally accepted dataset terms. One submission,
no automatic POST retries, no cleanup/delete, no production integration.
The official ecmwf-datastores-client 0.5.3 is installed in the pilot venv only.
"""

import argparse
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import time
from urllib.parse import urlsplit
from uuid import UUID
import warnings

import requests

from cams_request_plan import (
    DATASET,
    DEFAULT_AREA,
    PublicMetadataError,
    load_verified_request_plan,
    request_sha256,
    strict_json_loads,
)

ADS_URL = "https://ads.atmosphere.copernicus.eu/api"
PORDENONE_AREA = (46.1, 12.5, 45.8, 12.8)  # N,W,S,E; not whole Europe.
MAX_DOWNLOAD_BYTES = 64 * 1024 * 1024
TERMINAL_BAD = {"failed", "rejected", "dismissed", "deleted"}


class PilotError(Exception):
    """Only static, secret-free messages may be placed in this exception."""


def utc_now():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def write_new(path, value):
    encoded = json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    with Path(path).open("x", encoding="utf-8") as stream:
        stream.write(encoded)


def load_credentials(path):
    path = Path(path)
    if not path.is_file() or not 1 <= path.stat().st_size <= 4096:
        raise PilotError("Invalid credential file size or path")
    fields = {}
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if ":" not in line:
            raise PilotError("Credential file must contain url and key fields")
        name, value = line.split(":", 1)
        name = name.strip()
        if name not in {"url", "key"} or name in fields:
            raise PilotError("Unexpected or duplicate credential field")
        fields[name] = value.strip()
    if fields.get("url") != ADS_URL:
        raise PilotError("Credential URL must be the official ADS API")
    token = fields.get("key", "")
    if not token or len(token) > 2048 or any(c.isspace() for c in token):
        raise PilotError("Invalid or missing ADS token")
    return fields["url"], token


def is_ads_api(url):
    parsed = urlsplit(url)
    return (parsed.scheme == "https" and parsed.hostname == "ads.atmosphere.copernicus.eu"
            and parsed.port in (None, 443) and parsed.username is None
            and parsed.password is None and parsed.path.startswith("/api/"))


class AdsOnlySession(requests.Session):
    """API credentials can never follow cross-host links or redirects."""

    def request(self, method, url, **kwargs):
        if not is_ads_api(url):
            raise PilotError("Refused credential-bearing request outside official ADS API")
        kwargs["allow_redirects"] = False
        response = super().request(method, url, **kwargs)
        if 300 <= response.status_code < 400:
            response.close()
            raise PilotError("ADS redirect refused")
        return response


def safe_job_metadata(raw):
    """Discard provider logs, user metadata, links, and all non-timing fields."""
    status = raw.get("status")
    if status not in {"accepted", "queued", "running", "successful"} | TERMINAL_BAD:
        raise PilotError("Unexpected ADS job status")
    result = {"status": status}
    for key in ("created", "started", "finished", "updated"):
        value = raw.get(key)
        if value is not None:
            try:
                parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
                if parsed.tzinfo is None:
                    # Matches pinned official ecmwf.datastores.utils.
                    # string_to_datetime: ADS returns UTC without an offset.
                    parsed = parsed.replace(tzinfo=timezone.utc)
            except (AttributeError, TypeError, ValueError):
                raise PilotError("Invalid ADS timestamp") from None
            result[key] = parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    return result


def job_durations(metadata):
    def difference(end, start):
        if metadata.get(end) is None or metadata.get(start) is None:
            return None
        seconds = (datetime.fromisoformat(metadata[end].replace("Z", "+00:00"))
                   - datetime.fromisoformat(metadata[start].replace("Z", "+00:00"))).total_seconds()
        if seconds < 0:
            raise PilotError("ADS timestamps are not chronological")
        return seconds
    return {"server_queue_seconds": difference("started", "created"),
            "server_processing_seconds": difference("finished", "started"),
            "server_total_seconds": difference("finished", "created")}


def validate_result_location(location):
    parsed = urlsplit(location)
    host = parsed.hostname or ""
    if (parsed.scheme != "https" or parsed.port not in (None, 443)
            or parsed.username is not None or parsed.password is not None
            or not (host.endswith(".ecmwf.int") or host == "ads.atmosphere.copernicus.eu")):
        raise PilotError("Unexpected result host; inspect official result metadata before downloading")
    return host


def _partial_download_record(path, *, expected, content_type, host, identity):
    expected_identity_keys = {
        "dataset",
        "request_id",
        "run_date",
        "request_plan_sha256",
        "request_sha256",
    }
    if not isinstance(identity, dict) or set(identity) != expected_identity_keys:
        raise PilotError("Download identity is incomplete")
    if type(expected) is not int or not 0 < expected <= MAX_DOWNLOAD_BYTES:
        raise PilotError("Download identity has an invalid result size")
    if content_type not in {"application/x-grib", "application/grib", "application/octet-stream"}:
        raise PilotError("Download identity has an invalid content type")
    if type(host) is not str or validate_result_location(f"https://{host}/") != host:
        raise PilotError("Download identity has an invalid result host")
    try:
        if str(UUID(identity["request_id"])) != identity["request_id"]:
            raise ValueError
    except (KeyError, TypeError, ValueError):
        raise PilotError("Download identity has an invalid job identifier") from None
    if identity.get("dataset") != DATASET:
        raise PilotError("Download identity has an unexpected dataset")
    if type(identity.get("run_date")) is not str or not identity["run_date"]:
        raise PilotError("Download identity is malformed")
    for key in ("request_plan_sha256", "request_sha256"):
        value = identity.get(key)
        if type(value) is not str or len(value) != 64 or any(
            character not in "0123456789abcdef" for character in value
        ):
            raise PilotError("Download identity is malformed")
    return {
        "schema_version": 1,
        "kind": "cams_result_partial_download",
        "target_name": Path(path).name,
        "expected_bytes": expected,
        "content_type": content_type,
        "result_host": host,
        **identity,
    }


def _prepare_partial_download(path, marker_path, expected_record):
    part_exists = path.exists()
    marker_exists = marker_path.exists()
    if not part_exists and not marker_exists:
        write_new(marker_path, expected_record)
        return
    if not marker_exists:
        raise PilotError("Unmarked partial result exists; it will not be deleted")
    saved = _load_json_record(
        marker_path, maximum_bytes=16384, label="Partial download marker"
    )
    if saved != expected_record:
        raise PilotError("Partial download marker does not match this exact job")
    if part_exists:
        if not path.is_file() or path.stat().st_size > expected_record["expected_bytes"]:
            raise PilotError("Marked partial result has an invalid type or size")
        path.unlink()
    marker_path.unlink()
    write_new(marker_path, expected_record)


def _completion_record(partial_record, digest):
    if type(digest) is not str or len(digest) != 64 or any(
        character not in "0123456789abcdef" for character in digest
    ):
        raise PilotError("Completed download digest is invalid")
    return {
        **partial_record,
        "kind": "cams_result_completed_download",
        "sha256": digest,
    }


def _recover_completed_download(path, *, identity):
    """Finish or recognize only a hash-verified download for this exact job."""
    path = Path(path)
    partial_path = path.with_name(path.name + ".part")
    marker_path = path.with_name(path.name + ".part.json")
    complete_path = path.with_name(path.name + ".complete.json")
    if not complete_path.exists():
        if path.exists():
            raise PilotError("Final result exists without a verified completion record")
        return None
    complete = _load_json_record(
        complete_path, maximum_bytes=16384, label="Completed download record"
    )
    expected_keys = {
        "schema_version", "kind", "target_name", "expected_bytes", "content_type",
        "result_host", "dataset", "request_id", "run_date", "request_plan_sha256",
        "request_sha256", "sha256",
    }
    if set(complete) != expected_keys or complete.get("kind") != "cams_result_completed_download":
        raise PilotError("Completed download record is malformed")
    base = dict(complete)
    digest = base.pop("sha256")
    base["kind"] = "cams_result_partial_download"
    expected_base = _partial_download_record(
        path,
        expected=base.get("expected_bytes"),
        content_type=base.get("content_type"),
        host=base.get("result_host"),
        identity=identity,
    )
    if base != expected_base or not 0 < complete["expected_bytes"] <= MAX_DOWNLOAD_BYTES:
        raise PilotError("Completed download record does not match this exact job")
    validate_result_location(f"https://{complete['result_host']}/")
    if complete["content_type"] not in {
        "application/x-grib", "application/grib", "application/octet-stream"
    }:
        raise PilotError("Completed download record has an invalid content type")
    candidate = path if path.exists() else partial_path
    if not candidate.is_file() or candidate.stat().st_size != complete["expected_bytes"]:
        raise PilotError("Completed result has an invalid type or size")
    actual_digest = hashlib.sha256(candidate.read_bytes()).hexdigest()
    if actual_digest != digest:
        raise PilotError("Completed result digest does not match its record")
    if path.exists() and partial_path.exists() and not os.path.samefile(path, partial_path):
        raise PilotError("Final and partial results are not the same verified file")
    if not path.exists():
        if not marker_path.is_file():
            raise PilotError("Completed partial is missing its ownership marker")
        if _load_json_record(marker_path, maximum_bytes=16384, label="Partial download marker") != base:
            raise PilotError("Completed partial ownership marker does not match")
        os.link(partial_path, path)
    if partial_path.exists():
        partial_path.unlink()
    if marker_path.exists():
        if _load_json_record(marker_path, maximum_bytes=16384, label="Partial download marker") != base:
            raise PilotError("Partial ownership marker changed during recovery")
        marker_path.unlink()
    return {
        "download_bytes": complete["expected_bytes"],
        "download_seconds": 0.0,
        "sha256": digest,
        "result_host": complete["result_host"],
        "content_type": complete["content_type"],
        "credentials_sent_to_result_host": False,
        "download_recovered_after_atomic_publication": True,
    }


def download_result(results, path, *, identity):
    # Deliberately NOT the authenticated API session. No auth header/netrc/cookie.
    location = results.location
    host = validate_result_location(location)
    expected = results.content_length
    if type(expected) is not int or not 0 < expected <= MAX_DOWNLOAD_BYTES:
        raise PilotError("Result exceeds bounded regional pilot download size")
    content_type = results.content_type
    if content_type not in {"application/x-grib", "application/grib", "application/octet-stream"}:
        raise PilotError("Unexpected result content type")
    path = Path(path)
    if path.exists():
        raise FileExistsError(path)
    partial_path = path.with_name(path.name + ".part")
    marker_path = path.with_name(path.name + ".part.json")
    complete_path = path.with_name(path.name + ".complete.json")
    if complete_path.exists():
        raise PilotError("Completed download record already exists")
    partial_record = _partial_download_record(
        path,
        expected=expected,
        content_type=content_type,
        host=host,
        identity=identity,
    )
    _prepare_partial_download(partial_path, marker_path, partial_record)
    started = time.perf_counter()
    digest = hashlib.sha256()
    size = 0
    with requests.Session() as session:
        session.trust_env = False
        with session.get(location, stream=True, timeout=(15, 45), allow_redirects=False,
                         headers={"Accept-Encoding": "identity"}) as response:
            if response.status_code != 200:
                raise PilotError("Result download did not return HTTP 200; no redirects followed")
            if response.headers.get("Content-Encoding", "identity").lower() != "identity":
                raise PilotError("Unexpected result transfer encoding")
            declared = response.headers.get("Content-Length")
            if declared is not None and int(declared) != expected:
                raise PilotError("Result Content-Length mismatch")
            with partial_path.open("xb") as stream:
                for chunk in response.iter_content(64 * 1024):
                    if time.perf_counter() - started > 180:
                        raise PilotError("Result download wall-time budget exceeded")
                    size += len(chunk)
                    if size > expected or size > MAX_DOWNLOAD_BYTES:
                        raise PilotError("Result exceeded expected bytes")
                    stream.write(chunk)
                    digest.update(chunk)
                stream.flush()
                os.fsync(stream.fileno())
    if size != expected:
        raise PilotError("Incomplete result download")
    write_new(complete_path, _completion_record(partial_record, digest.hexdigest()))
    # A hard link gives create-if-absent atomic publication on both NTFS and
    # POSIX filesystems. It cannot replace a concurrently created final file.
    os.link(partial_path, path)
    partial_path.unlink()
    marker_path.unlink()
    return {"download_bytes": size, "download_seconds": round(time.perf_counter() - started, 6),
            "sha256": digest.hexdigest(), "result_host": host,
            "content_type": content_type, "credentials_sent_to_result_host": False}


def study_scope(scope):
    if scope == "pordenone":
        return PORDENONE_AREA, {"point": {"id": "pordenone", "latitude": 45.95689,
                                         "longitude": 12.66051}}
    if scope != "fvg":
        raise PilotError("Scope must be pordenone or fvg")
    from benchmark_icon2i import load_points
    points, digest = load_points()
    north, west, south, east = DEFAULT_AREA
    if any(not south + .05 <= p["latitude"] <= north - .05
           or not west + .05 <= p["longitude"] <= east - .05 for p in points):
        raise PilotError("Regional crop does not cover all catalog points with grid margin")
    return DEFAULT_AREA, {"municipalities": points, "municipality_count": len(points),
                          "catalog_sha256": digest,
                          "coordinate_provenance": "Representative points derived locally from ISTAT boundaries and IRDAT localities; no Open-Meteo geocoding"}


def _load_json_record(path, *, maximum_bytes, label):
    path = Path(path)
    if not path.is_file() or not 1 <= path.stat().st_size <= maximum_bytes:
        raise PilotError(f"{label} path or byte size is invalid")
    try:
        value = strict_json_loads(path.read_bytes())
    except PublicMetadataError:
        raise PilotError(f"{label} is not strict JSON") from None
    if not isinstance(value, dict):
        raise PilotError(f"{label} must be a JSON object")
    return value


def _request_record(plan, plan_hash, scope, scope_metadata):
    request = plan["request_groups"][0]["request"]
    return {
        "schema_version": 2,
        "dataset": DATASET,
        "scope": scope,
        "run_date": plan["run_date"],
        "request_plan_sha256": plan_hash,
        "request_sha256": request_sha256(request),
        "request": request,
        "variables": plan["variables"],
        "scope_metadata": scope_metadata,
        "licence": plan["licence"],
    }


def _validate_dated_directory(path, run_date, *, must_exist):
    directory = Path(path)
    marker_ok = run_date in directory.name or run_date.replace("-", "") in directory.name
    if not marker_ok:
        raise PilotError("Artifact directory name must include the verified run date")
    if must_exist:
        if not directory.is_dir():
            raise PilotError("Resume artifact directory does not exist")
    elif directory.exists() or not directory.parent.is_dir():
        raise PilotError("Artifact directory must be a new child of an existing directory")
    return directory


def _preflight_plan(request_plan_path, scope):
    try:
        plan, plan_bytes, plan_hash = load_verified_request_plan(request_plan_path)
    except PublicMetadataError as exc:
        raise PilotError(str(exc)) from None
    if plan["request_groups"][0]["request"]["data_format"] != "grib":
        raise PilotError("Acquisition and decoders require a GRIB request plan")
    area, scope_metadata = study_scope(scope)
    if plan["request_groups"][0]["request"]["area"] != list(map(float, area)):
        raise PilotError("Request plan area does not match the selected study scope")
    return plan, plan_bytes, plan_hash, scope_metadata


def retrieve(
    credentials_path,
    *,
    request_plan_path,
    artifacts_directory=None,
    resume=None,
    max_wait=900,
    scope="pordenone",
    checkpoint_saver=None,
):
    """Submit once or resume only after an entirely local verified-plan preflight."""
    if resume is not None and artifacts_directory is not None:
        raise PilotError("Choose a new artifact directory or resume, never both")
    if resume is None and artifacts_directory is None:
        raise PilotError("A new dated artifact directory is required")
    if type(max_wait) is not int or not 1 <= max_wait <= 900:
        raise PilotError("Wait budget must be between 1 and 900 seconds")

    # This must happen before credentials are read, the ADS client is imported,
    # or any authenticated transport can exist.
    plan, plan_bytes, plan_hash, scope_metadata = _preflight_plan(request_plan_path, scope)
    request = plan["request_groups"][0]["request"]
    request_hash = request_sha256(request)
    expected_request_record = _request_record(plan, plan_hash, scope, scope_metadata)
    if importlib.metadata.version("ecmwf-datastores-client") != "0.5.3":
        raise PilotError("Client version changed; review API before running")

    if resume is not None:
        directory = _validate_dated_directory(resume, plan["run_date"], must_exist=True)
        copied_plan = directory / "request-plan.json"
        if not copied_plan.is_file() or copied_plan.read_bytes() != plan_bytes:
            raise PilotError("Resume request-plan bytes do not match the explicit plan")
        if _load_json_record(
            directory / "request.json", maximum_bytes=1024 * 1024, label="Saved request"
        ) != expected_request_record:
            raise PilotError("Resume request record does not match the explicit plan")
        intent = _load_json_record(
            directory / "submission-intent.json", maximum_bytes=16384, label="Submission intent"
        )
        expected_intent_keys = {
            "schema_version",
            "at_utc",
            "dataset",
            "scope",
            "run_date",
            "request_plan_sha256",
            "request_sha256",
            "post_retries",
        }
        if (
            set(intent) != expected_intent_keys
            or intent.get("schema_version") != 2
            or intent.get("dataset") != DATASET
            or intent.get("scope") != scope
            or intent.get("run_date") != plan["run_date"]
            or intent.get("request_plan_sha256") != plan_hash
            or intent.get("request_sha256") != request_hash
            or intent.get("post_retries") != 0
        ):
            raise PilotError("Submission intent does not match the explicit plan")
        try:
            intended_at = datetime.fromisoformat(intent["at_utc"].replace("Z", "+00:00"))
        except (AttributeError, ValueError):
            raise PilotError("Submission intent timestamp is invalid") from None
        if intended_at.tzinfo is None:
            raise PilotError("Submission intent timestamp must carry a timezone")
        saved = _load_json_record(
            directory / "job.json", maximum_bytes=16384, label="Saved job"
        )
        expected_job_keys = {
            "schema_version",
            "dataset",
            "request_id",
            "scope",
            "run_date",
            "request_plan_sha256",
            "request_sha256",
        }
        if (
            set(saved) != expected_job_keys
            or saved.get("schema_version") != 2
            or saved.get("dataset") != DATASET
            or saved.get("scope") != scope
            or saved.get("run_date") != plan["run_date"]
            or saved.get("request_plan_sha256") != plan_hash
            or saved.get("request_sha256") != request_hash
        ):
            raise PilotError("Resume job does not match the explicit plan")
        try:
            if str(UUID(saved["request_id"])) != saved["request_id"]:
                raise ValueError
        except (KeyError, TypeError, ValueError):
            raise PilotError("Invalid saved ADS job identifier") from None
        recovered_download = _recover_completed_download(
            directory / "source.grib",
            identity={
                "dataset": DATASET,
                "request_id": saved["request_id"],
                "run_date": plan["run_date"],
                "request_plan_sha256": plan_hash,
                "request_sha256": request_hash,
            },
        )
    else:
        directory = _validate_dated_directory(
            artifacts_directory, plan["run_date"], must_exist=False
        )
        directory.mkdir()
        with (directory / "request-plan.json").open("xb") as destination:
            destination.write(plan_bytes)
        write_new(directory / "request.json", expected_request_record)
        saved = None
        recovered_download = None

    print(json.dumps({"artifacts_directory": str(directory)}), flush=True)
    report_path = directory / (
        "retrieval-report-" + datetime.now(timezone.utc).strftime("%H%M%S%f") + ".json"
    )
    report = {
        "schema_version": 2,
        "dataset": DATASET,
        "run_date": plan["run_date"],
        "request_plan_sha256": plan_hash,
        "request_sha256": request_hash,
        "metadata_documents": plan["metadata_evidence"]["documents"],
        "started_at_utc": utc_now(),
        "commercial_app_unchanged": True,
        "credentials_stored_in_artifacts": False,
        "terms_accepted_by_tool": False,
        "terms_acceptance": "personally_accepted_by_user_before_test",
        "resumed_existing_job": resume is not None,
        "client_version": "0.5.3",
        "scope": scope,
    }
    started = time.perf_counter()
    if recovered_download is not None:
        report.update(recovered_download)
        report["status"] = "downloaded_pending_decode_validation"
        report["finished_at_utc"] = utc_now()
        report["total_acquisition_seconds"] = round(time.perf_counter() - started, 6)
        write_new(report_path, report)
        print(json.dumps({"status": report["status"], "report": str(report_path)}), flush=True)
        return report
    session = AdsOnlySession()
    session.trust_env = False
    try:
        # Credentials and the client are deliberately below every plan/artifact
        # preflight. Constructor retry is pinned to one attempt.
        url, token = load_credentials(credentials_path)
        from ecmwf.datastores import Client

        with warnings.catch_warnings(record=True):
            warnings.simplefilter("always")
            client = Client(
                url=url,
                key=token,
                session=session,
                timeout=(15, 45),
                maximum_tries=1,
                retry_after=0,
                progress=False,
                cleanup=False,
                log_callback=lambda *args, **kwargs: None,
            )
        if resume is not None:
            remote = client.get_remote(saved["request_id"])
        else:
            # Persist the complete intent and detached hashes BEFORE the only
            # POST. Any ambiguous failure is reconciled separately using GET.
            write_new(
                directory / "submission-intent.json",
                {
                    "schema_version": 2,
                    "at_utc": utc_now(),
                    "dataset": DATASET,
                    "scope": scope,
                    "run_date": plan["run_date"],
                    "request_plan_sha256": plan_hash,
                    "request_sha256": request_hash,
                    "post_retries": 0,
                },
            )
            if checkpoint_saver is not None:
                checkpoint_saver("intent", directory)
            remote = client.submit(DATASET, request)
            try:
                if str(UUID(remote.request_id)) != remote.request_id:
                    raise ValueError
            except (AttributeError, TypeError, ValueError):
                raise PilotError("Invalid ADS job identifier") from None
            write_new(
                directory / "job.json",
                {
                    "schema_version": 2,
                    "dataset": DATASET,
                    "request_id": remote.request_id,
                    "scope": scope,
                    "run_date": plan["run_date"],
                    "request_plan_sha256": plan_hash,
                    "request_sha256": request_hash,
                },
            )
            if checkpoint_saver is not None:
                checkpoint_saver("submitted", directory)
        report["submission_or_resume_seconds"] = round(time.perf_counter() - started, 6)
        previous_status = None
        poll_count = 0
        while True:
            metadata = safe_job_metadata(remote.json)
            poll_count += 1
            report["last_job_metadata"] = metadata
            elapsed = time.perf_counter() - started
            if metadata["status"] != previous_status:
                print(
                    json.dumps(
                        {"ads_status": metadata["status"], "elapsed_seconds": round(elapsed, 1)}
                    ),
                    flush=True,
                )
                previous_status = metadata["status"]
            if metadata["status"] == "successful":
                break
            if metadata["status"] in TERMINAL_BAD:
                raise PilotError("ADS processing ended without a successful result")
            if elapsed >= max_wait:
                raise PilotError(
                    "ADS wait budget reached; job saved for explicit resume, not resubmitted"
                )
            time.sleep(min(15, max_wait - elapsed))
        report["poll_count"] = poll_count
        report["submission_to_ready_observed_seconds"] = round(
            time.perf_counter() - started, 6
        )
        report.update(job_durations(metadata))
        results = remote._make_results(wait=False)
        report.update(
            download_result(
                results,
                directory / "source.grib",
                identity={
                    "dataset": DATASET,
                    "request_id": remote.request_id,
                    "run_date": plan["run_date"],
                    "request_plan_sha256": plan_hash,
                    "request_sha256": request_hash,
                },
            )
        )
        report["status"] = "downloaded_pending_decode_validation"
    except Exception as exc:
        report["status"] = "stopped"
        report["error_type"] = type(exc).__name__
        from local_pipeline.operational_diagnostics import error_fields
        from cams_storage import tls_failure_kind
        details = error_fields(exc)
        if type(details.get('retryable')) is bool:
            report['retryable'] = details['retryable']
        tls = details.get('transport_reason') or tls_failure_kind(exc)
        if tls:
            report['transport_reason'] = tls
            report['retryable'] = tls == 'tls_connection_interrupted'
        if isinstance(exc, PilotError):
            report["safe_reason"] = str(exc)
        elif isinstance(exc, requests.HTTPError) and exc.response is not None:
            report["http_status"] = exc.response.status_code
        print(
            json.dumps(
                {
                    key: report[key]
                    for key in ("status", "error_type", "safe_reason", "http_status", "transport_reason", "retryable")
                    if key in report
                }
            ),
            flush=True,
        )
    finally:
        session.close()
        report["finished_at_utc"] = utc_now()
        report["total_acquisition_seconds"] = round(time.perf_counter() - started, 6)
        write_new(report_path, report)
    print(json.dumps({"status": report["status"], "report": str(report_path)}), flush=True)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--credentials-file", required=True, type=Path)
    parser.add_argument("--request-plan", required=True, type=Path,
                        help="Explicit immutable plan produced from public metadata")
    parser.add_argument("--artifacts-directory", type=Path,
                        help="NEW directory whose name contains the verified run date")
    parser.add_argument("--resume", type=Path, help="Existing artifact directory containing job.json")
    parser.add_argument("--max-wait", type=int, default=900)
    parser.add_argument("--scope", choices=("pordenone", "fvg"), default="pordenone")
    args = parser.parse_args()
    if (args.resume is None) == (args.artifacts_directory is None):
        parser.error("Choose exactly one of --artifacts-directory or --resume")
    try:
        with warnings.catch_warnings(record=True):
            warnings.simplefilter("always")
            report = retrieve(
                args.credentials_file,
                request_plan_path=args.request_plan,
                artifacts_directory=args.artifacts_directory,
                resume=args.resume,
                max_wait=args.max_wait,
                scope=args.scope,
            )
    except Exception as exc:
        print(json.dumps({"status": "not_started", "error_type": type(exc).__name__,
                          "safe_reason": str(exc) if isinstance(exc, PilotError) else "Local setup check failed"}))
        return 1
    return 0 if report["status"] == "downloaded_pending_decode_validation" else 1


if __name__ == "__main__":
    raise SystemExit(main())
