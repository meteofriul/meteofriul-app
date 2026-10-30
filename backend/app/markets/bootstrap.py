"""Explicit one-time provisioning; never invoked by an API request or import."""
from __future__ import annotations

import argparse
import os

from .model import MarketError
from .repository import FirestoreMarketRepository, configured_repository
from .seed import load_seed


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--confirm-project", required=True)
    arguments = parser.parse_args(argv)
    project = os.getenv("MARKETS_FIREBASE_PROJECT_ID", "").strip()
    if os.getenv("MARKETS_STORAGE", "").strip().lower() != "firestore" or not project or arguments.confirm_project != project:
        raise MarketError("markets_bootstrap_configuration_mismatch", 503)
    repository = configured_repository()
    if not isinstance(repository, FirestoreMarketRepository):
        raise MarketError("markets_bootstrap_firestore_required", 503)
    repository.initialize(load_seed())
    print("Mercati archive initialized: 60 existing identities, 53 existing public cards, 59 unpublished research drafts.")


if __name__ == "__main__":
    main()
