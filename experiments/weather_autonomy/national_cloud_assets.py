"""Pinned, public national input assets; no credentials or cloud operations."""
from pathlib import Path
import argparse
import hashlib
import os

from serve_national_bundle_v2 import _load_catalog
from local_pipeline.national_forecast_points import load_forecast_points_artifact

PROJECT = os.environ.get("WEATHER_CLOUD_PROJECT", "meteofriul-pilot-20260906")
ROOT = Path(__file__).resolve().parents[2]
CATALOG_PATH = ROOT / "backend/app/data/italy_municipalities_2026.json"
POINTS_PATH = Path(__file__).parent / "national-assets/forecast-points.json"
CATALOG_SHA256 = "ee856c27ec135be45c4c7eaaf946158fdfc61bc83135cf9b6fbbce892ce3cf0d"
POINTS_FILE_SHA256 = "c0977fafef85276e1d29cc79891f95f9a1bf4d8388ecf63d73798b7880c94342"
POINTS_ARTIFACT_SHA256 = "f9d36d88a7724822b7eac2b6810b6a8e6dc9890ed6dad16a674dec68ee5aa038"


def load_catalog():
    catalog = _load_catalog(CATALOG_PATH)
    if catalog["catalog_sha256"] != CATALOG_SHA256 or catalog["municipality_count"] != 7894:
        raise ValueError("pinned national catalog required")
    return catalog


def load_inputs(points_path=POINTS_PATH):
    catalog = load_catalog()
    path = Path(points_path)
    if path.stat().st_size != 4975625 or hashlib.sha256(path.read_bytes()).hexdigest() != POINTS_FILE_SHA256:
        raise ValueError("pinned approved national forecast-point bytes required")
    points = load_forecast_points_artifact(path, catalog=catalog, allow_experimental=False)
    if points["artifact_sha256"] != POINTS_ARTIFACT_SHA256 or points["status"] != "approved_for_icon_mapping":
        raise ValueError("approved national forecast points required")
    return catalog, points


def stage_points(source):
    """Stage an already approved artifact create-only for an allowlisted build."""
    load_inputs(source)
    payload = Path(source).read_bytes()
    POINTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    try:
        with POINTS_PATH.open("xb") as output:
            output.write(payload)
    except FileExistsError:
        if POINTS_PATH.read_bytes() != payload:
            raise ValueError("staged forecast points differ; refusing replacement")
    load_inputs()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage-points", type=Path)
    args = parser.parse_args()
    if args.stage_points:
        stage_points(args.stage_points)
    else:
        load_inputs()
    print("Pinned national catalog and approved forecast points verified")
