"""Explicit tiny live test against the dedicated pilot bucket only."""
import os
from pathlib import Path
import subprocess
from uuid import uuid4
from google.cloud import storage
from google.oauth2.credentials import Credentials
from local_pipeline.gcs_object_store import GCSObjectStore
from local_pipeline.sqlite_object_store import PreconditionFailed


def main():
    gcloud = Path(os.environ["LOCALAPPDATA"]) / "Google/Cloud SDK/google-cloud-sdk/bin/gcloud.cmd"
    auth = subprocess.run([str(gcloud), "auth", "print-access-token"],
                          capture_output=True, text=True, check=True)
    client = storage.Client(project="meteofriul-pilot-20260906",
                            credentials=Credentials(auth.stdout.strip()))
    store = GCSObjectStore(client.bucket("meteofriul-pilot-20260906-state"))
    key = "smoke/" + uuid4().hex + ".json"
    first = store.put(key, b'{"version":1}', content_type="application/json")
    assert store.get(key).body == b'{"version":1}'
    try:
        store.put(key, b'{}')
        raise AssertionError("create-only not enforced")
    except PreconditionFailed:
        pass
    second = store.compare_and_swap(key, b'{"version":2}', expected_etag=first.etag)
    assert second.etag != first.etag
    try:
        store.compare_and_swap(key, b'{}', expected_etag=first.etag)
        raise AssertionError("stale CAS not rejected")
    except PreconditionFailed:
        pass
    assert store.get(key).body == b'{"version":2}'
    print("PASS: real GCS create-only, read integrity, CAS, stale-writer rejection")
    print("Retained tiny diagnostic object: pilot/" + key)


if __name__ == "__main__":
    main()
