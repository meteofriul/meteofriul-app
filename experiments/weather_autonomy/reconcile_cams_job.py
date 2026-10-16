"""Read-only ADS reconciliation after an ambiguous submission; never POST.

Only a unique exact request match created near the persisted submission intent
may restore the missing local job handle. Never prints provider payloads.
"""
import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import importlib.metadata
import json
from pathlib import Path
import re
from time import monotonic
from uuid import UUID
import warnings

from retrieve_cams import (
    ADS_URL,
    AdsOnlySession,
    PilotError,
    _load_json_record,
    _preflight_plan,
    _request_record,
    _validate_dated_directory,
    is_ads_api,
    load_credentials,
    safe_job_metadata,
    write_new,
)

PAGE_SIZE = 20
MAX_SUBMISSION_WINDOW_SECONDS = 300
MAX_COMPLETE_PAGES = 10
MAX_COMPLETE_JOBS = 200
MAX_COMPLETE_SECONDS = 45


class ReconciliationInconclusive(PilotError):
    """GET evidence is incomplete; this is not a corrupt local preflight."""


class ReadOnlyAdsSession(AdsOnlySession):
    """Fail before transport if a client change attempts any mutation."""

    def request(self, method, url, **kwargs):
        if str(method).upper() != "GET":
            raise PilotError("Reconciliation permits only read-only GET requests")
        return super().request(method, url, **kwargs)


def canonical(request):
    return {key: sorted(value, key=str) if isinstance(value, list) and key != "area" else value
             for key, value in request.items()}


def find_existing_job(client, *, dataset, request, intended_at):
    """Bounded GET-only matching shared by regional CAMS and global UV.

    The caller supplies a ReadOnlyAdsSession client and a verified intent. An
    empty result is evidence only for this bounded search, never POST authority.
    The returned identifier is internal state, not a public diagnostic field.
    """
    if not isinstance(intended_at, datetime) or intended_at.tzinfo is None:
        raise PilotError("Submission intent must include a timezone")
    since = intended_at - timedelta(seconds=5)
    until = intended_at + timedelta(seconds=MAX_SUBMISSION_WINDOW_SECONDS)
    jobs = client.get_jobs(limit=PAGE_SIZE, sortby="-created")
    request_ids = list(jobs.request_ids)
    # Inspect already-returned links; Jobs.next would issue another request.
    links = getattr(jobs, '_get_links', None)
    has_next = bool(links(rel='next')) if callable(links) else vars(jobs).get('next') is not None
    if len(request_ids) > PAGE_SIZE or len(set(request_ids)) != len(request_ids):
        raise ReconciliationInconclusive("Recent job page is inconclusive")
    matches, checked, crossed_cutoff, previous_created = [], 0, False, None
    for request_id in request_ids:
        try:
            valid_identifier = str(UUID(request_id)) == request_id
        except (TypeError, ValueError, AttributeError):
            valid_identifier = False
        if not valid_identifier:
            raise ReconciliationInconclusive("Invalid returned job identifier")
        raw = client.get_remote(request_id).json
        checked += 1
        try:
            meta = safe_job_metadata(raw)
        except (PilotError, AttributeError, TypeError):
            raise ReconciliationInconclusive("Recent job metadata is inconclusive") from None
        if "created" not in meta:
            raise ReconciliationInconclusive("Recent job lacks creation time; reconciliation is inconclusive")
        created = datetime.fromisoformat(meta["created"].replace("Z", "+00:00"))
        if previous_created is not None and created > previous_created:
            raise ReconciliationInconclusive("Job ordering is inconclusive")
        previous_created = created
        if created < since:
            crossed_cutoff = True
            break
        if created > until or raw.get("processID") != dataset:
            continue
        metadata = raw.get("metadata")
        recorded_request = metadata.get("request") if isinstance(metadata, dict) else None
        submitted = recorded_request.get("ids") if isinstance(recorded_request, dict) else None
        if not isinstance(submitted, dict):
            raise ReconciliationInconclusive("Recent job lacks request metadata; reconciliation is inconclusive")
        if canonical(submitted) == canonical(request):
            matches.append((request_id, meta))
    if (len(request_ids) >= PAGE_SIZE or has_next) and not crossed_cutoff:
        raise ReconciliationInconclusive("Recent job page is full; reconciliation is inconclusive")
    return matches, checked


def find_existing_job_complete(client, *, dataset, request, intended_at, observed_at):
    """Collect bounded GET evidence over the full original-attempt interval.

    Unlike the compatibility matcher above, this search follows the pinned
    client's explicit next links and includes delayed jobs through observed_at.
    Only a complete, error-free traversal returns evidence. The caller supplies
    a ReadOnlyAdsSession client; evidence alone never authorizes a POST, nor
    proves that an unseen request cannot appear after the observation interval.
    """
    if (not isinstance(intended_at, datetime) or intended_at.tzinfo is None
            or not isinstance(observed_at, datetime) or observed_at.tzinfo is None
            or observed_at < intended_at):
        raise ReconciliationInconclusive("Invalid complete reconciliation interval")
    if not isinstance(dataset, str) or not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,199}", dataset):
        raise ReconciliationInconclusive("Invalid reconciliation dataset")
    try:
        if not isinstance(request, dict):
            raise ValueError()
        wanted = canonical(request)
        wanted_json = json.dumps(
            wanted, sort_keys=True, separators=(",", ":"), allow_nan=False
        )
        fingerprint = hashlib.sha256(wanted_json.encode()).hexdigest()
    except (TypeError, ValueError):
        raise ReconciliationInconclusive("Invalid reconciliation request") from None
    if importlib.metadata.version("ecmwf-datastores-client") != "0.5.3":
        raise ReconciliationInconclusive("Client version changed; reconciliation is inconclusive")
    since = intended_at.astimezone(timezone.utc) - timedelta(seconds=5)
    until = observed_at.astimezone(timezone.utc)
    started = monotonic()

    def budget():
        if monotonic() - started >= MAX_COMPLETE_SECONDS:
            raise ReconciliationInconclusive("Complete reconciliation time limit reached")

    def stamp(value):
        return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")

    def page_metadata(page):
        # _get_links silently supplies [] when links are missing. For absence
        # evidence require the actual response to declare its pagination state.
        try:
            payload = page.json
            if (not isinstance(payload, dict) or not isinstance(payload.get("jobs"), list)
                    or not isinstance(payload.get("links"), list)):
                raise ValueError()
            identifiers = [item["jobID"] for item in payload["jobs"]]
            if (identifiers != list(page.request_ids) or len(identifiers) > PAGE_SIZE
                    or any(not isinstance(value, str) or str(UUID(value)) != value for value in identifiers)):
                raise ValueError()
            links = payload["links"]
            if any(not isinstance(link, dict) or not isinstance(link.get("rel"), str)
                   or not isinstance(link.get("href"), str) for link in links):
                raise ValueError()
            next_links = [link for link in links if link["rel"] == "next"]
            if len(next_links) > 1:
                raise ValueError()
            next_url = next_links[0]["href"] if next_links else None
            if next_url is not None and (not is_ads_api(next_url) or "#" in next_url):
                raise ValueError()
            if not identifiers and next_url is not None:
                raise ValueError()
            return identifiers, next_url
        except (AttributeError, KeyError, TypeError, ValueError, AssertionError):
            raise ReconciliationInconclusive("Job page or pagination is inconclusive") from None

    matches, checked_jobs, seen_ids, seen_links = [], [], set(), set()
    page_count, previous_created, coverage = 0, None, None
    jobs = client.get_jobs(limit=PAGE_SIZE, sortby="-created")
    while True:
        budget()
        page_count += 1
        identifiers, next_url = page_metadata(jobs)
        if len(set(identifiers)) != len(identifiers) or seen_ids.intersection(identifiers):
            raise ReconciliationInconclusive("Duplicate jobs make reconciliation inconclusive")
        seen_ids.update(identifiers)
        if len(seen_ids) > MAX_COMPLETE_JOBS:
            raise ReconciliationInconclusive("Complete reconciliation job limit reached")
        for identifier in identifiers:
            budget()
            remote = client.get_remote(identifier)
            budget()
            try:
                raw = remote.json
                budget()
                if (not isinstance(raw, dict) or raw.get("jobID") != identifier
                        or not isinstance(raw.get("processID"), str)
                        or not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,199}", raw["processID"])):
                    raise ValueError()
                meta = safe_job_metadata(raw)
                created = datetime.fromisoformat(meta["created"].replace("Z", "+00:00"))
                if previous_created is not None and created > previous_created:
                    raise ValueError()
                previous_created = created
                checked_jobs.append({"id": identifier, "dataset": raw["processID"],
                                     "created": meta["created"], "status": meta["status"]})
                if created < since:
                    coverage = "crossed_lower_cutoff"
                    break
                if raw["processID"] != dataset:
                    continue
                metadata = raw.get("metadata")
                recorded = metadata.get("request") if isinstance(metadata, dict) else None
                submitted = recorded.get("ids") if isinstance(recorded, dict) else None
                if not isinstance(submitted, dict):
                    raise ValueError()
                submitted_json = json.dumps(canonical(submitted), sort_keys=True,
                                            separators=(",", ":"), allow_nan=False)
                if submitted_json == wanted_json:
                    if created > until:
                        # Known newly appeared evidence cannot establish absence
                        # merely because it lies beyond the starting snapshot.
                        raise ValueError()
                    matches.append((identifier, meta))
            except (PilotError, AttributeError, KeyError, TypeError, ValueError):
                raise ReconciliationInconclusive("Job identity or metadata is inconclusive") from None
        if coverage is not None:
            break
        if next_url is None:
            if len(identifiers) >= PAGE_SIZE:
                raise ReconciliationInconclusive("Full job page has no explicit continuation")
            coverage = "end_of_results"
            break
        if next_url in seen_links:
            raise ReconciliationInconclusive("Repeated pagination link is inconclusive")
        if page_count >= MAX_COMPLETE_PAGES or len(seen_ids) >= MAX_COMPLETE_JOBS:
            raise ReconciliationInconclusive("Complete reconciliation page or job limit reached")
        seen_links.add(next_url)
        budget()
        jobs = jobs.next  # Pinned 0.5.3 Jobs.next performs a single GET.
        if jobs is None:
            raise ReconciliationInconclusive("Declared continuation returned no page")
    budget()
    evidence = {"schema_version": 1, "dataset": dataset, "request_sha256": fingerprint,
                "since_utc": stamp(since), "until_utc": stamp(until),
                "completed_at_utc": stamp(datetime.now(timezone.utc)), "complete": True,
                "coverage_reason": coverage, "page_count": page_count,
                "checked_count": len(checked_jobs), "checked_jobs": checked_jobs,
                "matched_ids": [identifier for identifier, _ in matches], "match_count": len(matches)}
    return matches, evidence


def reconcile(credentials, directory, *, request_plan_path, scope):
    """Recover one job handle using GET only after the same local plan preflight."""
    plan, plan_bytes, plan_hash, scope_metadata = _preflight_plan(request_plan_path, scope)
    directory = _validate_dated_directory(directory, plan["run_date"], must_exist=True)
    copied_plan = directory / "request-plan.json"
    if not copied_plan.is_file() or copied_plan.read_bytes() != plan_bytes:
        raise PilotError("Reconciliation request-plan bytes do not match the explicit plan")
    desired = _load_json_record(
        directory / "request.json", maximum_bytes=1024 * 1024, label="Saved request"
    )
    expected = _request_record(plan, plan_hash, scope, scope_metadata)
    if desired != expected:
        raise PilotError("Reconciliation request record does not match the explicit plan")
    intent = _load_json_record(
        directory / "submission-intent.json", maximum_bytes=16384, label="Submission intent"
    )
    expected_intent_keys = {
        "schema_version", "at_utc", "dataset", "scope", "run_date",
        "request_plan_sha256", "request_sha256", "post_retries",
    }
    if (
        set(intent) != expected_intent_keys
        or intent.get("schema_version") != 2
        or intent.get("dataset") != desired["dataset"]
        or intent.get("scope") != scope
        or intent.get("run_date") != plan["run_date"]
        or intent.get("request_plan_sha256") != plan_hash
        or intent.get("request_sha256") != desired["request_sha256"]
        or intent.get("post_retries") != 0
    ):
        raise PilotError("Submission intent does not match the explicit plan")
    try:
        intended_at = datetime.fromisoformat(intent["at_utc"].replace("Z", "+00:00"))
    except (AttributeError, ValueError):
        raise PilotError("Submission intent timestamp is invalid") from None
    if intended_at.tzinfo is None:
        raise PilotError("Submission intent must include a timezone")
    if (directory / "job.json").exists():
        raise PilotError("Job handle already exists; resume it instead")
    if importlib.metadata.version("ecmwf-datastores-client") != "0.5.3":
        raise PilotError("Client version changed; review API before reconciliation")

    # No credentials or ADS client exist until all local immutable-plan checks
    # above have passed.
    url, key = load_credentials(credentials)
    if url != ADS_URL:
        raise PilotError("Unexpected API")
    from ecmwf.datastores import Client

    with ReadOnlyAdsSession() as session, warnings.catch_warnings(record=True):
        warnings.simplefilter("always")
        session.trust_env = False
        client = Client(url=url, key=key, session=session, maximum_tries=1, retry_after=0,
                        timeout=(15, 45), cleanup=False, progress=False, log_callback=lambda *a, **k: None)
        matches, checked = find_existing_job(client, dataset=desired["dataset"],
                                             request=desired["request"], intended_at=intended_at)
        if len(matches) == 1:
            request_id, meta = matches[0]
            write_new(
                directory / "job.json",
                {
                    "schema_version": 2,
                    "dataset": desired["dataset"],
                    "request_id": request_id,
                    "scope": scope,
                    "run_date": plan["run_date"],
                    "request_plan_sha256": plan_hash,
                    "request_sha256": desired["request_sha256"],
                },
            )
            return {"result": "unique_existing_job_restored", "job_status": meta["status"], "checked": checked}
        return {"result": "no_matching_job_found" if not matches else "multiple_matching_jobs_stop", "matches": len(matches), "checked": checked}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--credentials-file", type=Path, required=True)
    parser.add_argument("--directory", type=Path, required=True)
    parser.add_argument("--request-plan", type=Path, required=True)
    parser.add_argument("--scope", choices=("pordenone", "fvg"), required=True)
    args = parser.parse_args(argv)
    try:
        result = reconcile(
            args.credentials_file,
            args.directory,
            request_plan_path=args.request_plan,
            scope=args.scope,
        )
        print(json.dumps(result))
        return 0 if result.get("result") == "unique_existing_job_restored" else 1
    except Exception as exc:
        import requests
        result = {"result": "inconclusive", "error_type": type(exc).__name__}
        if isinstance(exc, PilotError):
            result["safe_reason"] = str(exc)
        elif isinstance(exc, requests.HTTPError) and exc.response is not None:
            result["http_status"] = exc.response.status_code
        print(json.dumps(result))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
