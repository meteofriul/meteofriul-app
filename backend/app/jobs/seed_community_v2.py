"""Create the production Community v2 pointer once; never used by the API."""

from __future__ import annotations

import json
import os

from google.cloud import firestore, storage

from app.repositories.pilot_community import PilotMemoryCommunityRepository
from app.repositories.pilot_community_cloud import (
    PILOT_PROJECT,
    PilotCloudCommunityRepository,
)


def main() -> int:
    if os.environ.get("GOOGLE_CLOUD_PROJECT") != PILOT_PROJECT:
        raise RuntimeError("community_project_mismatch")
    source = PilotMemoryCommunityRepository()
    result = PilotCloudCommunityRepository.seed(
        firestore_client=firestore.Client(project=PILOT_PROJECT),
        storage_client=storage.Client(project=PILOT_PROJECT),
        state=source._snapshot_state(),
    )
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
