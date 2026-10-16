"""One local UV request. Never retries a submission or emits credentials."""
import argparse
import json
from pathlib import Path
from urllib.parse import urlsplit
from uuid import UUID
import requests
from retrieve_cams import AdsOnlySession, load_credentials, write_new, safe_job_metadata


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--credentials-file", required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parent
    plan = json.loads((root / "uv_pilot_request.json").read_text())
    dataset = "cams-global-atmospheric-composition-forecasts"
    request = plan["request"]
    assert plan["dataset"] == dataset
    assert request["variable"] == ["uv_biologically_effective_dose"]
    assert request["area"] == [46.7, 12.2, 45.5, 14.0]
    assert request["leadtime_hour"] == [str(i) for i in range(24, 48)]
    directory = root / "uv-pilot-local"
    directory.mkdir(exist_ok=True)
    job_path = directory / "job.json"
    intent_path = directory / "submission-intent.json"
    if not job_path.exists():
        if intent_path.exists():
            raise ValueError("Existing intent without job: reconcile manually, do not resubmit")
        meta = requests.get(f"https://ads.atmosphere.copernicus.eu/api/catalogue/v1/collections/{dataset}", timeout=30)
        meta.raise_for_status()
        link = next(x["href"] for x in meta.json()["links"] if x["rel"] == "constraints")
        parsed = urlsplit(link)
        assert parsed.scheme == "https" and parsed.hostname == "object-store.os-api.cci2.ecmwf.int"
        assert f"/resources/{dataset}/" in parsed.path
        response = requests.get(link, timeout=30)
        response.raise_for_status()
        def matches(row, lead):
            dates = row.get("date", [])
            date_ok = any(d.split("/")[0] <= request["date"] <= d.split("/")[-1] for d in dates)
            return date_ok and lead in row.get("leadtime_hour", []) and all(set(request[k]).issubset(row.get(k, [])) for k in ("variable", "time", "type"))
        assert all(any(matches(row, lead) for row in response.json()) for lead in request["leadtime_hour"]), "Request not covered by constraints"
    from ecmwf.datastores import Client
    url, key = load_credentials(args.credentials_file)
    session = AdsOnlySession()
    session.trust_env = False
    client = Client(url=url, key=key, session=session, maximum_tries=1,
                    timeout=(15, 45), retry_after=0, progress=False, cleanup=False,
                    log_callback=lambda *a, **k: None)
    if job_path.exists():
        job = json.loads(job_path.read_text())
        remote = client.get_remote(str(UUID(job["request_id"])))
    else:
        write_new(intent_path, {"dataset": dataset, "request": request, "post_retries": 0})
        remote = client.submit(dataset, request)
        request_id = str(UUID(remote.request_id))
        write_new(job_path, {"dataset": dataset, "request_id": request_id})
    print(json.dumps({"request_id": remote.request_id, "metadata": safe_job_metadata(remote.json)}))


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(json.dumps({"status": "stopped", "error_type": type(error).__name__,
                          "note": "No automatic resubmission; no secrets logged"}))
        raise SystemExit(1)
