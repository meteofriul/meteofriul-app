"""Read-only validation of the existing v1/v2 contracts, without payload reads."""
from datetime import timedelta
from functools import lru_cache
from types import SimpleNamespace
import hashlib
import json

from local_pipeline import contract_v1 as v1, national_icon_bundle as v2
from national_cloud_assets import load_catalog as national_catalog
from national_cloud_publication import read_pointer as national_pointer
from national_cloud_lazy_reader import validate_index
from .core import instant, stamp

ROOTS = {"fvg": "pilot/weather/v1/icon2i/", "national": "pilot/weather/v2/icon2i/"}
POINTERS = {"fvg": "latest.json", "national": "pilot.json"}
BASES = {
    "fvg": "https://meteofriul-weather-49007668366.europe-west1.run.app/weather/v1/icon2i/",
    "national": "https://meteofriul-national-weather-49007668366.europe-west1.run.app/weather/v2/icon2i/",
}
RESOLVER = "resolve.json?city=Roma&province=RM"
MAX_DOCUMENT = 2 * 1024 * 1024


def decode(body):
    if not isinstance(body, bytes) or not 0 < len(body) <= MAX_DOCUMENT:
        raise ValueError("document byte limit")
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate JSON key")
            result[key] = value
        return result
    def invalid(value):
        raise ValueError("nonfinite JSON number")
    value = json.loads(body.decode("utf-8"), object_pairs_hook=unique, parse_constant=invalid)
    if not isinstance(value, dict):
        raise ValueError("JSON object required")
    return value


@lru_cache(maxsize=1)
def catalogs():
    return v1.load_catalog(), national_catalog()


def pointer(product, body, *, catalog_pair=None):
    pair = catalog_pair or catalogs()
    value = decode(body)
    if product == "fvg":
        v1.validate_latest_document(value, expected_provider="icon2i", catalog=pair[0])
        active = value["latest"]
        descriptor = {"path": active["manifest_path"], "json_bytes": active["manifest_json_bytes"],
                      "sha256": active["manifest_sha256"]}
    else:
        # Reuse production validation with an in-memory, read-only capability.
        store = SimpleNamespace(get=lambda key: SimpleNamespace(body=body, etag="1"))
        value, _ = national_pointer(store, pair[1])
        active, descriptor = value, value["manifest"]
    return value, {"source_run_id": active["source_run_id"], "run_at": active["run_at"]}, descriptor


def common(product, value):
    keys = (("schema_version", "kind", "provider", "catalog", "latest", "disabled_run_ids")
            if product == "fvg" else
            ("schema_version", "kind", "contract", "status", "source_run_id", "run_at",
             "generated_at", "catalog", "grid", "metadata_sha256", "manifest", "index"))
    return {key: value[key] for key in keys}


def http_identity(product, value, *, resolver=False):
    if resolver:
        if not isinstance(value.get("municipality"), dict) or not isinstance(value.get("cell_id"), str):
            raise ValueError("invalid resolver municipality/cell shape")
        if (value.get("schema_version") != 1
                or value.get("kind") != "meteofriul.weather.icon.national.local_pilot_resolution"
                or value.get("contract") != "weather/v2/icon2i"
                or value.get("status") != "experimental_local_pilot_only"
                or value.get("pointer_path") != "pilot.json"
                or value.get("municipality", {}).get("istat_code") != "058091"
                or value["municipality"].get("name") != "Roma"
                or value["municipality"].get("province") != "RM"):
            raise ValueError("resolver identity differs")
        active = value
    elif product == "fvg":
        v1.validate_latest_document(value, expected_provider="icon2i")
        active = value["latest"]
    else:
        if (value.get("schema_version") != 1
                or value.get("kind") != "meteofriul.weather.icon.national.local_pilot_pointer"
                or value.get("contract") != "weather/v2/icon2i"):
            raise ValueError("public pointer identity differs")
        common(product, value)  # Mandatory common fields, not bucket-only fields.
        active = value
    run = instant(active["run_at"])
    if active["source_run_id"] != run.strftime("%Y%m%dT%H%M%SZ") or run.minute or run.second:
        raise ValueError("HTTP run identity differs")
    return active["source_run_id"]


def checked(body, descriptor):
    if (len(body) != descriptor["json_bytes"]
            or hashlib.sha256(body).hexdigest() != descriptor["sha256"]):
        raise ValueError("descriptor integrity mismatch")
    return decode(body)


def manifest(product, body, descriptor, ptr, *, catalog_pair=None):
    pair = catalog_pair or catalogs()
    value = checked(body, descriptor)
    if product == "fvg":
        v1.validate_latest_document(ptr, expected_provider="icon2i", catalog=pair[0], run_manifest=value)
        return value, list(value["objects"].values()), value["valid_to"]
    v2._validate_manifest(value)
    for key in ("source_run_id", "run_at", "generated_at", "catalog", "grid", "metadata_sha256", "index"):
        if value[key] != ptr[key]:
            raise ValueError("manifest and pointer differ")
    return value, [value["index"], *value["blocks"]], stamp(
        instant(value["run_at"]) + timedelta(hours=value["time_step_count"] - 1))


def index(body, manifest_doc, *, catalog_pair=None):
    pair = catalog_pair or catalogs()
    value = checked(body, manifest_doc["index"])
    validate_index(value, manifest_doc, pair[1])
    return value


def resolution(value, ptr, manifest_doc, index_doc):
    http_identity("national", value, resolver=True)
    for key in ("source_run_id", "run_at", "generated_at", "manifest", "index"):
        if value[key] != ptr[key]:
            raise ValueError("resolver and pointer differ")
    block_id = index_doc["municipality_blocks"]["058091"]
    block = next(item for item in manifest_doc["blocks"] if item["block_id"] == block_id)
    for field, expected in (("block_id", block_id), ("block_path", block["path"]),
                            ("block_json_bytes", block["json_bytes"]), ("block_sha256", block["sha256"])):
        if value[field] != expected:
            raise ValueError("resolver block descriptor differs")
