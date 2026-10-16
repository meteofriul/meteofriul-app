"""Import existing pilot SQLite into the isolated cloud, create-only.

From backend: python -m tools.seed_pilot_community_cloud --project
meteofriul-pilot-20260906 --sqlite-state <absolute-path> [--execute]
Without --execute this only validates the local file and prints safe metadata.
"""

import argparse
import hashlib
import json
from pathlib import Path

from app.repositories.pilot_community_cloud import (
    PILOT_PROJECT, PilotCloudCommunityRepository, read_sqlite_seed, serialize_state,
)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", required=True, choices=[PILOT_PROJECT])
    parser.add_argument("--sqlite-state", required=True, type=Path)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    state = read_sqlite_seed(args.sqlite_state)
    payload = serialize_state(state)
    result = {"project": args.project, "execute": args.execute,
              "payload_bytes": len(payload), "payload_sha256": hashlib.sha256(payload).hexdigest(),
              "field_counts": {field: len(value) for field, value in state.items()}}
    if args.execute:
        from google.cloud import firestore, storage

        PilotCloudCommunityRepository.seed(
            firestore_client=firestore.Client(project=args.project),
            storage_client=storage.Client(project=args.project), state=state,
        )
        # Read back the committed schema/hash before reporting successful import.
        repository = PilotCloudCommunityRepository(
            firestore_client=firestore.Client(project=args.project),
            storage_client=storage.Client(project=args.project),
        )
        if serialize_state(repository._snapshot_state()) != payload:
            raise RuntimeError("pilot_cloud_seed_readback_mismatch")
        repository.close()
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
