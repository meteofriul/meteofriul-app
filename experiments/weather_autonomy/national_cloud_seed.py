"""Explicit one-off seed of the exact locally reviewed 20 September pilot run.

This is separate from recurring acquisition and never downloads source GRIB.
It requires the pinned approved artifacts, checks the entire bundle and current
coverage, and uses the same immutable writes/full readback/CAS publisher.
"""
import argparse
from datetime import datetime, timezone
import json
import os
import sys
from pathlib import Path

from national_cloud_assets import PROJECT, CATALOG_PATH, load_inputs
from national_cloud_publication import create_or_verify, parse_document, publish_bundle
from local_pipeline.national_icon_bundle import NationalIconBundle, canonical_json_bytes, sha256_hex
from serve_national_bundle_v2 import VerifiedNationalBundleReader

SEED_MANIFEST_SHA256 = "77020ac7d1c17e4d33700f3b0854ebe47dcd7bf60716d9069690c4ae21bd4536"
SEED_MAPPING_SHA256 = "f251c2a9e5f2f0acfb286cd8569c8c74f17cdff372ea33271aff221e5230f7eb"


def load_seed(bundle_dir, mapping_path):
    catalog, points = load_inputs()
    reader = VerifiedNationalBundleReader.load(Path(bundle_dir), CATALOG_PATH)
    manifest = reader.manifest
    documents = reader._documents
    path = f"runs/{reader.source_run_id}/manifest.json"
    if sha256_hex(documents[path]) != SEED_MANIFEST_SHA256:
        raise ValueError("only the exactly reviewed local seed is allowed")
    mapping = parse_document(Path(mapping_path).read_bytes(), maximum=8 * 1024**2)
    content = dict(mapping)
    digest = content.pop("mapping_sha256", None)
    if (digest != SEED_MAPPING_SHA256 or sha256_hex(canonical_json_bytes(content)) != digest
            or mapping["source_run_id"] != reader.source_run_id
            or mapping["forecast_points"]["artifact_sha256"] != points["artifact_sha256"]):
        raise ValueError("reviewed seed mapping differs")
    bundle = NationalIconBundle(path, documents[path], manifest["index"]["path"],
        documents[manifest["index"]["path"]],
        tuple((item["path"], documents[item["path"]]) for item in manifest["blocks"]))
    return bundle, mapping, catalog, points


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle-dir", required=True, type=Path)
    parser.add_argument("--mapping", required=True, type=Path)
    parser.add_argument("--confirm-pilot-shadow-seed", action="store_true")
    parser.add_argument("--access-token-stdin", action="store_true",
        help="read a short-lived gcloud token privately from stdin instead of ADC")
    args = parser.parse_args(argv)
    if not args.confirm_pilot_shadow_seed or os.environ.get("GOOGLE_CLOUD_PROJECT") != PROJECT:
        raise ValueError("explicit seed authorization and isolated pilot project required")
    bundle, mapping, catalog, points = load_seed(args.bundle_dir, args.mapping)
    from national_cloud_publication import require_current_coverage
    now = datetime.now(timezone.utc)
    require_current_coverage(json.loads(bundle.manifest_json), now)
    from google.cloud import storage
    from local_pipeline.gcs_object_store import GCSObjectStore
    credentials = None
    if args.access_token_stdin:
        from google.oauth2.credentials import Credentials
        token = sys.stdin.read(8193).strip()
        if not token or len(token) > 8192 or any(character.isspace() for character in token):
            raise ValueError("invalid private access token input")
        credentials = Credentials(token)
    client = storage.Client(project=PROJECT, credentials=credentials)
    state = GCSObjectStore(client.bucket(PROJECT + "-state"))
    from national_cloud_worker import record_preparation
    record_preparation(state, bundle, mapping, catalog, points)
    pointer = publish_bundle(GCSObjectStore(client.bucket(PROJECT + "-data")), bundle, catalog,
        now=now, clock=lambda: datetime.now(timezone.utc))
    print(json.dumps({"status": "seeded_experimental_pilot", "source_run_id": pointer["source_run_id"],
        "manifest_sha256": pointer["manifest"]["sha256"]}, sort_keys=True))


if __name__ == "__main__":
    main()
