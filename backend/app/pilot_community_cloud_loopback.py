"""Explicit owner-only localhost preview of the existing pilot cloud store.

There is no SQLite/memory fallback, automatic initialization, ADC, enrollment
token, or public listener. Browser client identity remains independent of phone.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path

from app.pilot_community import create_app
from app.repositories.pilot_community_cloud import PILOT_PROJECT, PilotCloudCommunityRepository
from app.services.community_reports import CommunityReportsService, CommunityReportVote, CommunityHistoryQuery
from app.services.pilot_community import PilotCommunityService
from app.services.pilot_community_geography import PilotCommunityGeographyCatalog

LOOPBACK_CLOUD_KIND = "meteofriul.community.loopback-cloud-pilot.v1"


def create_loopback_cloud_app(*, project: str, port: int = 8783,
                              geography=None, firestore_client=None, storage_client=None):
    if project != PILOT_PROJECT or port != 8783 or os.environ.get("K_SERVICE"):
        raise ValueError("pilot_loopback_cloud_configuration_rejected")
    if (firestore_client is None) != (storage_client is None):
        raise ValueError("pilot_loopback_cloud_clients_incomplete")
    if firestore_client is None:
        from google.cloud import firestore, storage
        from app.pilot_owner_credentials import create_owner_credentials
        credentials = create_owner_credentials()
        firestore_client = firestore.Client(project=PILOT_PROJECT, credentials=credentials)
        storage_client = storage.Client(project=PILOT_PROJECT, credentials=credentials)
    geography = geography or PilotCommunityGeographyCatalog()
    _ = geography.municipalities
    repository = PilotCloudCommunityRepository(firestore_client=firestore_client, storage_client=storage_client)

    def check_cloud_store():
        # Unchanged read-only transaction: validates pointer and snapshot, no write.
        with repository.transaction():
            pass

    return create_app(
        service=CommunityReportsService(geography=geography, repository=repository), port=port,
        health_kind=LOOPBACK_CLOUD_KIND, health_project=PILOT_PROJECT,
        health_check=check_cloud_store,
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", required=True, choices=[PILOT_PROJECT])
    parser.add_argument("--host", choices=["127.0.0.1"], default="127.0.0.1")
    parser.add_argument("--port", type=int, choices=[8783], default=8783)
    parser.add_argument("--geography-path", type=Path)
    args = parser.parse_args()
    repository = None
    try:
        application = create_loopback_cloud_app(
            project=args.project, port=args.port,
            geography=PilotCommunityGeographyCatalog(data_path=args.geography_path),
        )
        repository = application.state.community.repository
        import uvicorn
        uvicorn.run(application, host=args.host, port=args.port, workers=1, access_log=False)
    except Exception:
        raise SystemExit("pilot_loopback_cloud_unavailable") from None
    finally:
        if repository is not None:
            repository.close()


if __name__ == "__main__":
    main()
