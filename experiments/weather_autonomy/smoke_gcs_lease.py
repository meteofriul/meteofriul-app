"""Bounded real pilot-state concurrency test; no ADS or public feed writes."""
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
import hashlib
import os
from pathlib import Path
import subprocess
from threading import Barrier
from uuid import uuid4
from google.cloud import storage
from google.oauth2.credentials import Credentials
from local_pipeline.gcs_object_store import GCSObjectStore
from local_pipeline.object_state_store import ObjectStateStore
from local_pipeline.contracts import RunKey, Provider


def main():
    gcloud = Path(os.environ["LOCALAPPDATA"]) / "Google/Cloud SDK/google-cloud-sdk/bin/gcloud.cmd"
    token = subprocess.run([str(gcloud), "auth", "print-access-token"],
                           capture_output=True, text=True, check=True).stdout.strip()
    key = RunKey(Provider.CAMS, "20260906T000000Z", hashlib.sha256(uuid4().bytes).hexdigest())
    barrier = Barrier(2)
    def attempt(owner):
        client = storage.Client(project="meteofriul-pilot-20260906", credentials=Credentials(token))
        state = ObjectStateStore(GCSObjectStore(client.bucket("meteofriul-pilot-20260906-state")))
        barrier.wait()
        return state, state.claim(key, owner_id=owner, lease_for=timedelta(minutes=2))
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(attempt, ("smoke-one", "smoke-two")))
    assert sum(result.acquired for _, result in results) == 1
    state, winner = next(pair for pair in results if pair[1].acquired)
    assert state.get(key).owner_id == winner.record.owner_id
    state.release_lease(key, owner_id=winner.record.owner_id, fencing_token=winner.record.fencing_token)
    print("PASS real GCS: two concurrent workers, one owner, durable record, clean release")


if __name__ == "__main__":
    main()
