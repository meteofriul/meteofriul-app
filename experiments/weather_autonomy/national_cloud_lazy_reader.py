"""Verified national metadata plus bounded, on-demand immutable blocks.

The publisher validates the entire run before committing its pointer. This read
side independently validates the complete manifest/index and each requested
block against those immutable descriptors, without fetching the other 641 blocks.
The existing local identity/search implementation is reused unchanged.
"""
from collections import Counter, OrderedDict
from decimal import Decimal
import json
import re
from threading import RLock

from local_pipeline import national_icon_bundle as contract
from national_cloud_publication import PREFIX, _checked, parse_document, validate_descriptor
from serve_national_bundle_v2 import VerifiedNationalBundleReader, _catalog_reference


class _LazyMunicipalityCells(dict):
    def __init__(self, run):
        super().__init__()
        self.run = run

    def __missing__(self, code):
        block_id = self.run.index["municipality_blocks"][code]
        block = json.loads(self.run.block(block_id))
        self.update(block["municipality_cells"])
        return self[code]


def validate_index(index, manifest, catalog):
    expected = {"kind", "schema_version", "contract", "source_run_id", "catalog",
        "grid_sha256", "tile_size_microdegrees", "municipality_blocks"}
    if (set(index) != expected or index["kind"] != contract.INDEX_KIND
            or index["schema_version"] != contract.SCHEMA_VERSION
            or index["contract"] != contract.CONTRACT_ID
            or index["source_run_id"] != manifest["source_run_id"]
            or index["catalog"] != manifest["catalog"]
            or index["grid_sha256"] != manifest["grid"]["sha256"]
            or index["tile_size_microdegrees"] != manifest["tile_size_microdegrees"]):
        raise ValueError("national index differs from manifest")
    municipalities = index["municipality_blocks"]
    if not isinstance(municipalities, dict) or set(municipalities) != {item["istat_code"] for item in catalog["municipalities"]}:
        raise ValueError("national index differs from complete catalog")
    if not all(isinstance(value, str) for value in municipalities.values()):
        raise ValueError("invalid national index block identity")
    counts = Counter(municipalities.values())
    if counts != Counter({item["block_id"]: item["municipality_count"] for item in manifest["blocks"]}):
        raise ValueError("national index block counts differ")
    if contract.sha256_hex(contract.canonical_json_bytes(sorted(municipalities))) != manifest["catalog"]["municipality_codes_sha256"]:
        raise ValueError("national index municipality identity hash differs")


def validate_block(body, descriptor, manifest, index):
    block = parse_document(_checked(body, descriptor), maximum=contract.MAX_BLOCK_JSON_BYTES)
    expected = {"kind", "schema_version", "contract", "source_run_id", "block_id", "tile",
        "metadata", "time_axis", "municipality_cells", "cells"}
    block_id = descriptor["block_id"]
    if (set(block) != expected or block["kind"] != contract.BLOCK_KIND
            or block["schema_version"] != contract.SCHEMA_VERSION
            or block["contract"] != contract.CONTRACT_ID
            or block["source_run_id"] != manifest["source_run_id"] or block["block_id"] != block_id
            or block["tile"] != {"size_microdegrees": manifest["tile_size_microdegrees"],
                "bounds_microdegrees": contract._tile_bounds_microdegrees(block_id)}):
        raise ValueError("national block identity or tile differs")
    metadata = block["metadata"]
    if not isinstance(metadata, dict):
        raise ValueError("invalid national block metadata")
    normalized = contract._normalize_metadata({key: metadata.get(key) for key in ("model", "source", "variables")},
        catalog=manifest["catalog"], grid=manifest["grid"], run_at=manifest["run_at"], generated_at=manifest["generated_at"])
    if metadata != normalized or contract.sha256_hex(contract.canonical_json_bytes(metadata)) != manifest["metadata_sha256"]:
        raise ValueError("national block metadata differs")
    axis = contract._normalize_time_axis(block["time_axis"], run_at=manifest["run_at"])
    if (len(axis) != manifest["time_step_count"] or len(metadata["variables"]) != manifest["variable_count"]
            or contract.sha256_hex(contract.canonical_json_bytes(axis)) != manifest["time_axis_sha256"]):
        raise ValueError("national block time/variable coverage differs")
    mappings, cells = block["municipality_cells"], block["cells"]
    expected_codes = {code for code, tile in index["municipality_blocks"].items() if tile == block_id}
    if (not isinstance(mappings, dict) or set(mappings) != expected_codes
            or len(mappings) != descriptor["municipality_count"]
            or not isinstance(cells, list) or len(cells) != descriptor["cell_count"]):
        raise ValueError("national block municipality or cell coverage differs")
    if not all(isinstance(value, str) for value in mappings.values()):
        raise ValueError("invalid national municipality cell identity")
    cell_ids, grid_indexes = set(), []
    for raw in cells:
        if not isinstance(raw, dict):
            raise ValueError("invalid national cell")
        cell = contract._normalize_cell({key: raw.get(key) for key in ("grid_index", "latitude", "longitude", "values")},
            grid=manifest["grid"], variables=metadata["variables"], time_step_count=len(axis))
        if raw != cell or cell["cell_id"] in cell_ids:
            raise ValueError("national block cell differs or duplicates")
        tile = contract.tile_id_for_coordinate(cell["latitude"], cell["longitude"],
            tile_size_degrees=Decimal(manifest["tile_size_microdegrees"]) / contract.MICRODEGREES_PER_DEGREE)
        if tile != block_id:
            raise ValueError("national block contains foreign cell")
        cell_ids.add(cell["cell_id"])
        grid_indexes.append(cell["grid_index"])
    if grid_indexes != sorted(set(grid_indexes)) or set(mappings.values()) != cell_ids:
        raise ValueError("national block cell references differ")


class NationalLazyRun:
    def __init__(self, store, catalog, descriptor):
        match = re.fullmatch(r"runs/(\d{8}T\d{6}Z)/manifest.json", str(descriptor.get("path", "")))
        if not match:
            raise ValueError("invalid national manifest path")
        validate_descriptor(descriptor, match[1])
        manifest_bytes = _checked(store.get(PREFIX + descriptor["path"]).body, descriptor)
        self.manifest = contract._validate_manifest(parse_document(manifest_bytes, maximum=contract.MAX_MANIFEST_JSON_BYTES))
        if self.manifest["source_run_id"] != match[1] or self.manifest["catalog"] != _catalog_reference(catalog):
            raise ValueError("national manifest identity differs")
        all_descriptors = [self.manifest["index"], *self.manifest["blocks"]]
        if (self.manifest["index"]["json_bytes"] > contract.MAX_INDEX_JSON_BYTES
                or any(item["json_bytes"] > contract.MAX_BLOCK_JSON_BYTES for item in self.manifest["blocks"])
                or len(manifest_bytes) + sum(item["json_bytes"] for item in all_descriptors) > contract.MAX_BUNDLE_JSON_BYTES):
            raise ValueError("national publication exceeds byte budget")
        index_descriptor = self.manifest["index"]
        index_bytes = _checked(store.get(PREFIX + index_descriptor["path"]).body, index_descriptor)
        self.index = parse_document(index_bytes, maximum=contract.MAX_INDEX_JSON_BYTES)
        validate_index(self.index, self.manifest, catalog)
        # The constructor only builds identity/search tables. The local server's
        # full load/validation path is unchanged; this wrapper owns block checks.
        metadata_documents = contract.NationalIconBundle(descriptor["path"], manifest_bytes,
            index_descriptor["path"], index_bytes, ())
        self.identity = VerifiedNationalBundleReader(bundle=metadata_documents, manifest=self.manifest,
            index=self.index, blocks={}, catalog=catalog)
        self.identity._municipality_cells = _LazyMunicipalityCells(self)
        self.source_run_id, self.pointer = self.identity.source_run_id, self.identity.pointer
        self.store = store
        self.descriptors = {item["block_id"]: item for item in self.manifest["blocks"]}
        self.paths = {item["path"]: item["block_id"] for item in self.manifest["blocks"]}
        self.cache, self.cache_bytes, self.lock = OrderedDict(), 0, RLock()

    def block(self, block_id):
        with self.lock:
            if block_id in self.cache:
                self.cache.move_to_end(block_id)
                return self.cache[block_id]
            descriptor = self.descriptors[block_id]
            body = self.store.get(PREFIX + descriptor["path"]).body
            validate_block(body, descriptor, self.manifest, self.index)
            self.cache[block_id] = body
            self.cache_bytes += len(body)
            while len(self.cache) > 16 or self.cache_bytes > 16 * 1024**2:
                _key, evicted = self.cache.popitem(last=False)
                self.cache_bytes -= len(evicted)
            return body

    def document(self, path):
        if path in self.paths:
            return self.block(self.paths[path])
        return self.identity.document(path)

    def resolve(self, **kwargs):
        return self.identity.resolve(**kwargs)

    def search(self, query):
        return self.identity.search(query)
