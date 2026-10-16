"""Serve one verified national ICON v2 bundle on IPv4 loopback.

This entrypoint is intentionally local-pilot-only.  It opens no cloud client,
does not publish or mutate objects, and never serves arbitrary files.  At
startup it reads the complete bundle into memory, validates the independent
``weather/v2/icon2i`` contract and the pinned national municipality catalog,
then exposes only the verified pointer, manifest, index and block bytes.

The resolver is a convenience for the Android pilot because national search
results can arrive without an ISTAT code.  It accepts exact municipality names
only.  Province disambiguation is exact; coordinates may break a tie between
same-name municipalities but can never trigger an arbitrary nearest-place
lookup.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from functools import partial
import gzip
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import math
from pathlib import Path
from types import MappingProxyType
import re
from typing import Any, Callable, Iterable, Mapping, Sequence
import unicodedata
from urllib.parse import parse_qsl, urlsplit

try:  # Package import from the repository root.
    from .local_pipeline import national_icon_bundle as bundle_contract
    from .national_catalog import validate_catalog
except ImportError:  # Direct execution from experiments/weather_autonomy.
    from local_pipeline import national_icon_bundle as bundle_contract
    from national_catalog import validate_catalog


LOOPBACK_HOST = "127.0.0.1"
PROVIDER_PREFIX = "/weather/v2/icon2i"
POINTER_RELATIVE_PATH = "pilot.json"
RESOLVE_RELATIVE_PATH = "resolve.json"
SEARCH_RELATIVE_PATH = "search.json"
POINTER_KIND = "meteofriul.weather.icon.national.local_pilot_pointer"
RESOLUTION_KIND = "meteofriul.weather.icon.national.local_pilot_resolution"
SEARCH_KIND = "meteofriul.weather.icon.national.local_pilot_search"
LOCAL_DOCUMENT_SCHEMA_VERSION = 1
MAX_SEARCH_RESULTS = 8
NO_STORE_CACHE_CONTROL = "no-store"
IMMUTABLE_CACHE_CONTROL = "public, max-age=31536000, immutable"
DEFAULT_ALLOWED_ORIGINS = frozenset(
    {
        "http://127.0.0.1:5174",
        "http://localhost:5174",
        "https://localhost",
    }
)
_RUN_ID = re.compile(r"^\d{8}T\d{6}Z$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_MALFORMED_ESCAPE = re.compile(r"%(?![0-9A-Fa-f]{2})")
_ISTAT = re.compile(r"^\d{6}$")


class NationalBundleServerError(ValueError):
    """The local source cannot be exposed without weakening the contract."""


class ResolutionError(LookupError):
    """An exact national municipality identity could not be selected."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class ServerConfig:
    bundle_dir: Path
    catalog_json: Path
    port: int


@dataclass
class NationalBundleService:
    reader: "VerifiedNationalBundleReader"
    server: ThreadingHTTPServer
    closed: bool = False

    @property
    def url(self) -> str:
        host, port = self.server.server_address[:2]
        return f"http://{host}:{port}{PROVIDER_PREFIX}/"

    def close(self) -> None:
        if self.closed:
            return
        self.closed = True
        self.server.server_close()


def _canonical_json_bytes(value: Any) -> bytes:
    return bundle_contract.canonical_json_bytes(value)


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _canonical_error(code: str) -> bytes:
    return _canonical_json_bytes({"error": code})


def _normalize_identity(value: Any) -> str:
    decomposed = unicodedata.normalize("NFKD", str(value or "").casefold())
    without_marks = "".join(
        character for character in decomposed if not unicodedata.combining(character)
    )
    return " ".join(re.sub(r"[^0-9a-z]+", " ", without_marks).split())


def _is_link_or_junction(path: Path) -> bool:
    if path.is_symlink():
        return True
    is_junction = getattr(path, "is_junction", None)
    return bool(callable(is_junction) and is_junction())


def _assert_tree_has_no_links(root: Path) -> None:
    current = root
    while True:
        if _is_link_or_junction(current):
            raise NationalBundleServerError("bundle directory cannot be a link or junction")
        if current.parent == current:
            break
        current = current.parent
    for path in root.rglob("*"):
        if _is_link_or_junction(path):
            raise NationalBundleServerError("bundle tree contains a link or junction")


def _read_bounded_file(path: Path, *, maximum: int, label: str) -> bytes:
    try:
        size = path.stat().st_size
    except OSError as error:
        raise NationalBundleServerError(f"{label} is unreadable") from error
    if not path.is_file() or not 1 <= size <= maximum:
        raise NationalBundleServerError(f"{label} has an invalid byte length")
    try:
        payload = path.read_bytes()
    except OSError as error:
        raise NationalBundleServerError(f"{label} is unreadable") from error
    if len(payload) != size:
        raise NationalBundleServerError(f"{label} changed while being read")
    return payload


def _parse_json(payload: bytes, label: str) -> Mapping[str, Any]:
    try:
        decoded = payload.decode("utf-8")
    except UnicodeDecodeError as error:
        raise NationalBundleServerError(f"{label} is not UTF-8 JSON") from error
    try:
        document = json.loads(decoded)
    except json.JSONDecodeError as error:
        raise NationalBundleServerError(f"{label} failed JSON validation") from error
    if not isinstance(document, Mapping):
        raise NationalBundleServerError(f"{label} must be a JSON object")
    if _canonical_json_bytes(document) != payload:
        raise NationalBundleServerError(f"{label} is not canonical JSON")
    return document


def _safe_relative_path(root: Path, relative: Any, label: str) -> Path:
    if (
        not isinstance(relative, str)
        or not relative
        or relative.startswith(("/", "\\"))
        or "\\" in relative
        or "%" in relative
        or "//" in relative
        or any(part in {"", ".", ".."} for part in relative.split("/"))
    ):
        raise NationalBundleServerError(f"{label} path is not canonical")
    candidate = root.joinpath(*relative.split("/"))
    try:
        resolved = candidate.resolve(strict=True)
    except OSError as error:
        raise NationalBundleServerError(f"{label} is missing") from error
    if not resolved.is_relative_to(root):
        raise NationalBundleServerError(f"{label} escaped the bundle directory")
    return resolved


def _load_catalog(path: Path) -> Mapping[str, Any]:
    payload = _read_bounded_file(path.resolve(strict=True), maximum=32 * 1024 * 1024, label="national catalog")
    # The reviewed repository artifact is canonical JSON followed by the usual
    # single POSIX text-file terminator.  Accept only that optional final LF:
    # CRLF, BOMs, multiple newlines and any other surrounding whitespace still
    # fail the canonical-byte comparison below.
    if payload.endswith(b"\n"):
        payload = payload[:-1]
    document = _parse_json(payload, "national catalog")
    try:
        validate_catalog(document)
    except ValueError as error:
        raise NationalBundleServerError("national catalog failed validation") from error
    return document


def _catalog_reference(document: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "version": document.get("catalog_version"),
        "sha256": document.get("catalog_sha256"),
        "municipality_count": document.get("municipality_count"),
        "municipality_codes_sha256": document.get("municipality_codes_sha256"),
    }


def _descriptor(document: Mapping[str, Any], *, block: bool = False) -> dict[str, Any]:
    keys = {"path", "json_bytes", "sha256"}
    if block:
        keys.update({"block_id", "municipality_count", "cell_count"})
    if not keys.issubset(document):
        raise NationalBundleServerError("bundle descriptor is incomplete")
    return {key: document[key] for key in sorted(keys)}


def _haversine_km(
    first_latitude: float,
    first_longitude: float,
    second_latitude: float,
    second_longitude: float,
) -> float:
    radius = 6371.0088
    lat1 = math.radians(first_latitude)
    lat2 = math.radians(second_latitude)
    delta_lat = lat2 - lat1
    delta_lon = math.radians(second_longitude - first_longitude)
    term = (
        math.sin(delta_lat / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin(delta_lon / 2) ** 2
    )
    return radius * 2 * math.atan2(math.sqrt(term), math.sqrt(max(0.0, 1 - term)))


class VerifiedNationalBundleReader:
    """Immutable in-memory view of one fully validated national run."""

    def __init__(
        self,
        *,
        bundle: bundle_contract.NationalIconBundle,
        manifest: Mapping[str, Any],
        index: Mapping[str, Any],
        blocks: Mapping[str, Mapping[str, Any]],
        catalog: Mapping[str, Any],
    ) -> None:
        self.manifest = MappingProxyType(dict(manifest))
        self.index = MappingProxyType(dict(index))
        self.catalog = catalog
        self.source_run_id = str(manifest["source_run_id"])
        self._documents = MappingProxyType(bundle.documents())
        self._manifest_descriptor = {
            "path": bundle.manifest_path,
            "json_bytes": len(bundle.manifest_json),
            "sha256": _sha256(bundle.manifest_json),
        }
        self._index_descriptor = dict(manifest["index"])
        self._block_descriptors = {
            descriptor["block_id"]: dict(descriptor)
            for descriptor in manifest["blocks"]
        }
        self._municipality_blocks = dict(index["municipality_blocks"])
        self._municipality_cells: dict[str, str] = {}
        for block_id, block in blocks.items():
            for istat_code, cell_id in block["municipality_cells"].items():
                if self._municipality_blocks.get(istat_code) != block_id:
                    raise NationalBundleServerError("resolver mapping differs from bundle index")
                self._municipality_cells[istat_code] = cell_id

        raw_municipalities = catalog.get("municipalities")
        if not isinstance(raw_municipalities, list):
            raise NationalBundleServerError("national catalog municipalities are invalid")
        self._municipalities = {
            record["istat_code"]: dict(record) for record in raw_municipalities
        }
        if set(self._municipalities) != set(self._municipality_blocks):
            raise NationalBundleServerError("catalog identities differ from bundle index")

        aliases: dict[str, dict[str, Mapping[str, Any]]] = {}
        for record in self._municipalities.values():
            for alias in {
                record.get("name"),
                record.get("italian_name"),
                record.get("alternate_name"),
            }:
                normalized = _normalize_identity(alias)
                if normalized:
                    aliases.setdefault(normalized, {})[record["istat_code"]] = record
        self._aliases = MappingProxyType(
            {
                name: tuple(sorted(records.values(), key=lambda item: item["istat_code"]))
                for name, records in aliases.items()
            }
        )
        self._search_records = tuple(
            (
                record,
                tuple(
                    sorted(
                        {
                            normalized
                            for alias in {
                                record.get("name"),
                                record.get("italian_name"),
                                record.get("alternate_name"),
                            }
                            if (normalized := _normalize_identity(alias))
                        }
                    )
                ),
            )
            for record in sorted(
                self._municipalities.values(), key=lambda item: item["istat_code"]
            )
        )
        self.pointer = MappingProxyType(
            {
                "schema_version": LOCAL_DOCUMENT_SCHEMA_VERSION,
                "kind": POINTER_KIND,
                "contract": bundle_contract.CONTRACT_ID,
                "status": "experimental_local_pilot_only",
                "source_run_id": self.source_run_id,
                "run_at": manifest["run_at"],
                "generated_at": manifest["generated_at"],
                "catalog": dict(manifest["catalog"]),
                "grid": dict(manifest["grid"]),
                "metadata_sha256": manifest["metadata_sha256"],
                "manifest": dict(self._manifest_descriptor),
                "index": dict(self._index_descriptor),
            }
        )
        self.pointer_json = _canonical_json_bytes(dict(self.pointer))

    @classmethod
    def load(
        cls,
        bundle_dir: Path,
        catalog_json: Path,
        *,
        catalog_loader: Callable[[Path], Mapping[str, Any]] = _load_catalog,
    ) -> "VerifiedNationalBundleReader":
        try:
            root = bundle_dir.expanduser().resolve(strict=True)
        except OSError as error:
            raise NationalBundleServerError("bundle directory does not exist") from error
        if not root.is_dir():
            raise NationalBundleServerError("bundle path is not a directory")
        _assert_tree_has_no_links(root)

        manifests = sorted(root.glob("runs/*/manifest.json"))
        if len(manifests) != 1:
            raise NationalBundleServerError("bundle directory must contain exactly one run manifest")
        manifest_file = manifests[0].resolve(strict=True)
        manifest_relative = manifest_file.relative_to(root).as_posix()
        manifest_json = _read_bounded_file(
            manifest_file,
            maximum=bundle_contract.MAX_MANIFEST_JSON_BYTES,
            label="national manifest",
        )
        manifest = _parse_json(manifest_json, "national manifest")
        source_run_id = manifest.get("source_run_id")
        if not isinstance(source_run_id, str) or _RUN_ID.fullmatch(source_run_id) is None:
            raise NationalBundleServerError("national manifest run id is invalid")
        expected_manifest_path = f"runs/{source_run_id}/manifest.json"
        if manifest_relative != expected_manifest_path:
            raise NationalBundleServerError("national manifest path is not canonical")

        raw_index_descriptor = manifest.get("index")
        raw_block_descriptors = manifest.get("blocks")
        if not isinstance(raw_index_descriptor, Mapping) or not isinstance(raw_block_descriptors, list):
            raise NationalBundleServerError("national manifest descriptors are invalid")
        index_path = str(raw_index_descriptor.get("path") or "")
        index_file = _safe_relative_path(root, index_path, "national index")
        index_json = _read_bounded_file(
            index_file,
            maximum=bundle_contract.MAX_INDEX_JSON_BYTES,
            label="national index",
        )

        block_documents: list[tuple[str, bytes]] = []
        parsed_blocks: dict[str, Mapping[str, Any]] = {}
        expected_files = {expected_manifest_path, index_path}
        total_bytes = len(manifest_json) + len(index_json)
        for position, raw_descriptor in enumerate(raw_block_descriptors):
            if not isinstance(raw_descriptor, Mapping):
                raise NationalBundleServerError("national block descriptor is invalid")
            block_id = str(raw_descriptor.get("block_id") or "")
            path = str(raw_descriptor.get("path") or "")
            block_file = _safe_relative_path(root, path, f"national block {position}")
            block_json = _read_bounded_file(
                block_file,
                maximum=bundle_contract.MAX_BLOCK_JSON_BYTES,
                label=f"national block {block_id}",
            )
            total_bytes += len(block_json)
            if total_bytes > bundle_contract.MAX_BUNDLE_JSON_BYTES:
                raise NationalBundleServerError("national bundle exceeds byte limit")
            if path in expected_files:
                raise NationalBundleServerError("national bundle contains duplicate paths")
            expected_files.add(path)
            block_documents.append((path, block_json))
            parsed_blocks[block_id] = _parse_json(block_json, f"national block {block_id}")

        observed_files = {
            path.resolve(strict=True).relative_to(root).as_posix()
            for path in root.rglob("*")
            if path.is_file()
        }
        if observed_files != expected_files:
            raise NationalBundleServerError("bundle directory contains missing or extra files")

        bundle = bundle_contract.NationalIconBundle(
            manifest_path=expected_manifest_path,
            manifest_json=manifest_json,
            index_path=index_path,
            index_json=index_json,
            block_documents=tuple(block_documents),
        )
        try:
            bundle_contract.validate_national_icon_bundle(bundle)
        except bundle_contract.NationalIconBundleError as error:
            raise NationalBundleServerError("national bundle failed validation") from error
        index = _parse_json(index_json, "national index")

        try:
            catalog = catalog_loader(catalog_json.expanduser())
        except NationalBundleServerError:
            raise
        except Exception as error:
            raise NationalBundleServerError("national catalog failed validation") from error
        if not isinstance(catalog, Mapping) or _catalog_reference(catalog) != manifest["catalog"]:
            raise NationalBundleServerError("national catalog differs from bundle manifest")
        return cls(
            bundle=bundle,
            manifest=manifest,
            index=index,
            blocks=parsed_blocks,
            catalog=catalog,
        )

    def document(self, relative_path: str) -> bytes | None:
        if relative_path == POINTER_RELATIVE_PATH:
            return self.pointer_json
        return self._documents.get(relative_path)

    def cache_control(self, relative_path: str) -> str:
        return (
            NO_STORE_CACHE_CONTROL
            if relative_path
            in {POINTER_RELATIVE_PATH, RESOLVE_RELATIVE_PATH, SEARCH_RELATIVE_PATH}
            else IMMUTABLE_CACHE_CONTROL
        )

    @staticmethod
    def _search_rank(query: str, aliases: Sequence[str]) -> tuple[int, int] | None:
        if query in aliases:
            return (0, min(len(alias) for alias in aliases if alias == query))
        prefix_lengths = [len(alias) for alias in aliases if alias.startswith(query)]
        if prefix_lengths:
            return (1, min(prefix_lengths))
        word_lengths = [
            len(alias)
            for alias in aliases
            if any(word.startswith(query) for word in alias.split())
        ]
        if word_lengths:
            return (2, min(word_lengths))
        contains_lengths = [len(alias) for alias in aliases if query in alias]
        if contains_lengths:
            return (3, min(contains_lengths))
        return None

    def search(self, query: str) -> bytes:
        normalized_query = _normalize_identity(query)
        ranked: list[tuple[int, int, str, str, Mapping[str, Any]]] = []
        for record, aliases in self._search_records:
            rank = self._search_rank(normalized_query, aliases)
            if rank is None:
                continue
            ranked.append(
                (
                    rank[0],
                    rank[1],
                    _normalize_identity(record["name"]),
                    record["istat_code"],
                    record,
                )
            )
        ranked.sort(key=lambda item: item[:4])

        results = []
        for _match_kind, _alias_length, _name, _istat_code, municipality in ranked[
            :MAX_SEARCH_RESULTS
        ]:
            point = municipality.get("representative_point")
            if not isinstance(point, Mapping):
                raise NationalBundleServerError(
                    "national catalog municipality representative point is invalid"
                )
            results.append(
                {
                    "name": municipality["name"],
                    "province": municipality["province_abbreviation"],
                    "province_name": municipality["uts_name"],
                    "region_name": municipality["region_name"],
                    "region_iso": municipality["region_iso"],
                    "latitude": point["latitude"],
                    "longitude": point["longitude"],
                    "istat_code": municipality["istat_code"],
                }
            )
        return _canonical_json_bytes(
            {
                "schema_version": LOCAL_DOCUMENT_SCHEMA_VERSION,
                "kind": SEARCH_KIND,
                "contract": bundle_contract.CONTRACT_ID,
                "status": "experimental_local_pilot_only",
                "query": normalized_query,
                "results": results,
            }
        )

    def _province_matches(self, record: Mapping[str, Any], province: str) -> bool:
        normalized = _normalize_identity(province)
        return normalized in {
            _normalize_identity(record.get("province_abbreviation")),
            _normalize_identity(record.get("uts_name")),
        }

    def resolve(
        self,
        *,
        city: str,
        province: str | None,
        latitude: float | None,
        longitude: float | None,
    ) -> bytes:
        candidates = list(self._aliases.get(_normalize_identity(city), ()))
        if province:
            candidates = [
                record for record in candidates if self._province_matches(record, province)
            ]
        if not candidates:
            raise ResolutionError("municipality_not_found")
        if len(candidates) > 1 and latitude is not None and longitude is not None:
            ranked: list[tuple[float, str, Mapping[str, Any]]] = []
            for record in candidates:
                point = record.get("representative_point")
                if not isinstance(point, Mapping):
                    continue
                try:
                    distance = _haversine_km(
                        latitude,
                        longitude,
                        float(point["latitude"]),
                        float(point["longitude"]),
                    )
                except (KeyError, TypeError, ValueError):
                    continue
                ranked.append((distance, record["istat_code"], record))
            ranked.sort(key=lambda item: (item[0], item[1]))
            if ranked and (len(ranked) == 1 or ranked[0][0] < ranked[1][0]):
                candidates = [ranked[0][2]]
        if len(candidates) != 1:
            raise ResolutionError("municipality_ambiguous")

        municipality = candidates[0]
        istat_code = municipality["istat_code"]
        block_id = self._municipality_blocks[istat_code]
        cell_id = self._municipality_cells[istat_code]
        block = self._block_descriptors[block_id]
        point = municipality.get("representative_point")
        response = {
            "schema_version": LOCAL_DOCUMENT_SCHEMA_VERSION,
            "kind": RESOLUTION_KIND,
            "contract": bundle_contract.CONTRACT_ID,
            "status": "experimental_local_pilot_only",
            "source_run_id": self.source_run_id,
            "run_at": self.manifest["run_at"],
            "generated_at": self.manifest["generated_at"],
            "pointer_path": POINTER_RELATIVE_PATH,
            "manifest": dict(self._manifest_descriptor),
            "index": dict(self._index_descriptor),
            "municipality": {
                "istat_code": istat_code,
                "name": municipality["name"],
                "province": municipality["province_abbreviation"],
                "province_name": municipality["uts_name"],
                "region_name": municipality["region_name"],
                "region_iso": municipality["region_iso"],
                "representative_point": {
                    "latitude": point["latitude"],
                    "longitude": point["longitude"],
                },
            },
            "block_id": block_id,
            "cell_id": cell_id,
            "block_path": block["path"],
            "block_json_bytes": block["json_bytes"],
            "block_sha256": block["sha256"],
        }
        return _canonical_json_bytes(response)


def _normalize_origins(origins: Iterable[str]) -> frozenset[str]:
    normalized: set[str] = set()
    for raw_origin in origins:
        origin = str(raw_origin or "").strip().rstrip("/")
        parsed = urlsplit(origin)
        if (
            parsed.scheme not in {"http", "https"}
            or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}
            or parsed.username
            or parsed.password
            or parsed.path
            or parsed.query
            or parsed.fragment
            or "*" in origin
        ):
            raise NationalBundleServerError("allowed origins must be exact loopback origins")
        normalized.add(origin)
    if not normalized:
        raise NationalBundleServerError("at least one loopback origin is required")
    return frozenset(normalized)


def _accepts_gzip(value: str | None) -> bool:
    explicit: bool | None = None
    wildcard: bool | None = None
    for raw_item in str(value or "").split(","):
        fields = [field.strip() for field in raw_item.split(";")]
        coding = fields[0].lower()
        if not coding:
            continue
        quality = 1.0
        for parameter in fields[1:]:
            if parameter.lower().startswith("q="):
                try:
                    quality = float(parameter[2:])
                except ValueError:
                    quality = 0.0
        accepted = quality > 0
        if coding == "gzip":
            explicit = accepted
        elif coding == "*":
            wildcard = accepted
    return explicit if explicit is not None else bool(wildcard)


def _weak_etag_value(value: str) -> str:
    candidate = value.strip()
    if candidate[:2].lower() == "w/":
        candidate = candidate[2:].strip()
    return candidate


def _if_none_match_matches(header: str | None, etag: str) -> bool:
    if not header:
        return False
    expected = _weak_etag_value(etag)
    return any(
        candidate.strip() == "*"
        or _weak_etag_value(candidate.strip()) == expected
        for candidate in header.split(",")
    )


def _parse_resolve_query(raw_query: str) -> dict[str, Any]:
    if len(raw_query) > 1024 or _MALFORMED_ESCAPE.search(raw_query):
        raise ValueError("resolve_query_invalid")
    try:
        pairs = parse_qsl(
            raw_query,
            keep_blank_values=True,
            strict_parsing=True,
            max_num_fields=4,
        )
    except ValueError as error:
        raise ValueError("resolve_query_invalid") from error
    allowed = {"city", "province", "lat", "lon"}
    if not pairs or any(key not in allowed for key, _value in pairs):
        raise ValueError("resolve_query_invalid")
    values: dict[str, str] = {}
    for key, value in pairs:
        if key in values:
            raise ValueError("resolve_query_invalid")
        values[key] = value
    city = values.get("city", "").strip()
    province = values.get("province", "").strip()
    if not 1 <= len(city) <= 120 or len(province) > 120:
        raise ValueError("resolve_query_invalid")
    raw_latitude = values.get("lat", "").strip()
    raw_longitude = values.get("lon", "").strip()
    if bool(raw_latitude) != bool(raw_longitude):
        raise ValueError("resolve_query_invalid")
    latitude = longitude = None
    if raw_latitude:
        try:
            latitude = float(raw_latitude)
            longitude = float(raw_longitude)
        except ValueError as error:
            raise ValueError("resolve_query_invalid") from error
        if (
            not math.isfinite(latitude)
            or not math.isfinite(longitude)
            or not -90 <= latitude <= 90
            or not -180 <= longitude <= 180
        ):
            raise ValueError("resolve_query_invalid")
    return {
        "city": city,
        "province": province or None,
        "latitude": latitude,
        "longitude": longitude,
    }


def _parse_search_query(raw_query: str) -> str:
    if len(raw_query) > 512 or _MALFORMED_ESCAPE.search(raw_query):
        raise ValueError("search_query_invalid")
    try:
        pairs = parse_qsl(
            raw_query,
            keep_blank_values=True,
            strict_parsing=True,
            max_num_fields=1,
        )
    except ValueError as error:
        raise ValueError("search_query_invalid") from error
    if len(pairs) != 1 or pairs[0][0] != "q":
        raise ValueError("search_query_invalid")
    query = pairs[0][1].strip()
    normalized = _normalize_identity(query)
    if not 2 <= len(normalized) <= 120:
        raise ValueError("search_query_invalid")
    return normalized


class NationalBundleHandler(BaseHTTPRequestHandler):
    server_version = "MeteoFriulNationalPilot/2"
    sys_version = ""

    def __init__(
        self,
        *args: Any,
        reader: VerifiedNationalBundleReader,
        allowed_origins: frozenset[str],
        **kwargs: Any,
    ) -> None:
        self.reader = reader
        self.allowed_origins = allowed_origins
        super().__init__(*args, **kwargs)

    def log_message(self, _format: str, *_args: object) -> None:
        pass  # Never log municipality queries or object paths.

    def _host_allowed(self) -> bool:
        port = int(self.server.server_port)
        allowed = {f"127.0.0.1:{port}", f"localhost:{port}", f"[::1]:{port}"}
        return self.headers.get("Host", "").strip().lower() in allowed

    def _request_origin(self) -> tuple[str | None, bool]:
        raw_origin = self.headers.get("Origin")
        if raw_origin is None:
            return None, True
        origin = raw_origin.strip().rstrip("/")
        return origin, origin in self.allowed_origins

    def _base_headers(self, origin: str | None = None) -> None:
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Vary", "Origin, Accept-Encoding")
        if origin is not None:
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Access-Control-Expose-Headers", "ETag")

    def _error(self, status: int, code: str, origin: str | None = None) -> None:
        body = _canonical_error(code)
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", NO_STORE_CACHE_CONTROL)
        self._base_headers(origin)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _authorize(self) -> tuple[str | None, bool]:
        if not self._host_allowed():
            self._error(403, "host_not_allowed")
            return None, False
        origin, allowed = self._request_origin()
        if not allowed:
            self._error(403, "origin_not_allowed")
            return None, False
        return origin, True

    def _route(self) -> tuple[str, str | dict[str, Any]]:
        if len(self.path) > 2048:
            raise ValueError("object_path_not_allowed")
        parsed = urlsplit(self.path)
        if parsed.scheme or parsed.netloc or parsed.fragment:
            raise ValueError("object_path_not_allowed")
        path = parsed.path
        if "%" in path or "\\" in path or "//" in path or not path.startswith("/"):
            raise ValueError("object_path_not_allowed")
        if path == f"{PROVIDER_PREFIX}/{RESOLVE_RELATIVE_PATH}":
            return "resolve", _parse_resolve_query(parsed.query)
        if path == f"{PROVIDER_PREFIX}/{SEARCH_RELATIVE_PATH}":
            return "search", _parse_search_query(parsed.query)
        if parsed.query or not path.startswith(PROVIDER_PREFIX + "/"):
            raise ValueError("object_path_not_allowed")
        relative = path[len(PROVIDER_PREFIX) + 1 :]
        if relative == POINTER_RELATIVE_PATH or relative in self.reader._documents:
            return "document", relative
        raise ValueError("object_path_not_allowed")

    def _serve_bytes(
        self,
        body: bytes,
        *,
        cache_control: str,
        origin: str | None,
        include_body: bool,
    ) -> None:
        use_gzip = _accepts_gzip(self.headers.get("Accept-Encoding"))
        response_body = gzip.compress(body, compresslevel=6, mtime=0) if use_gzip else body
        etag = f'"sha256-{_sha256(body)}"'
        if use_gzip:
            etag = f'"gzip-sha256-{_sha256(response_body)}"'
        if _if_none_match_matches(self.headers.get("If-None-Match"), etag):
            self.send_response(304)
            self.send_header("ETag", etag)
            self.send_header("Cache-Control", cache_control)
            self._base_headers(origin)
            self.end_headers()
            return
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(response_body)))
        self.send_header("Cache-Control", cache_control)
        self.send_header("ETag", etag)
        if use_gzip:
            self.send_header("Content-Encoding", "gzip")
        self._base_headers(origin)
        self.end_headers()
        if include_body:
            self.wfile.write(response_body)

    def _serve(self, *, include_body: bool) -> None:
        origin, authorized = self._authorize()
        if not authorized:
            return
        try:
            kind, value = self._route()
        except ValueError as error:
            self._error(400, str(error), origin)
            return
        if kind == "resolve":
            try:
                body = self.reader.resolve(**value)  # type: ignore[arg-type]
            except ResolutionError as error:
                status = 409 if error.code == "municipality_ambiguous" else 404
                self._error(status, error.code, origin)
                return
            self._serve_bytes(
                body,
                cache_control=NO_STORE_CACHE_CONTROL,
                origin=origin,
                include_body=include_body,
            )
            return
        if kind == "search":
            self._serve_bytes(
                self.reader.search(str(value)),
                cache_control=NO_STORE_CACHE_CONTROL,
                origin=origin,
                include_body=include_body,
            )
            return
        relative = str(value)
        body = self.reader.document(relative)
        if body is None:
            self._error(404, "object_not_found", origin)
            return
        self._serve_bytes(
            body,
            cache_control=self.reader.cache_control(relative),
            origin=origin,
            include_body=include_body,
        )

    def do_GET(self) -> None:
        self._serve(include_body=True)

    def do_HEAD(self) -> None:
        self._serve(include_body=False)

    def do_OPTIONS(self) -> None:
        origin, authorized = self._authorize()
        if not authorized:
            return
        try:
            self._route()
        except ValueError as error:
            self._error(400, str(error), origin)
            return
        requested_method = self.headers.get("Access-Control-Request-Method", "").upper()
        requested_headers = {
            item.strip().lower()
            for item in self.headers.get("Access-Control-Request-Headers", "").split(",")
            if item.strip()
        }
        if (
            origin is None
            or requested_method not in {"GET", "HEAD"}
            or requested_headers - {"if-none-match"}
        ):
            self._error(403, "cors_preflight_not_allowed", origin)
            return
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", origin)
        self.send_header("Access-Control-Allow-Methods", "GET, HEAD, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "If-None-Match")
        self.send_header("Access-Control-Max-Age", "600")
        self.send_header("Cache-Control", NO_STORE_CACHE_CONTROL)
        self._base_headers()
        self.end_headers()

    def _method_not_allowed(self) -> None:
        origin, authorized = self._authorize()
        if not authorized:
            return
        body = _canonical_error("read_only")
        self.close_connection = True
        self.send_response(405)
        self.send_header("Allow", "GET, HEAD, OPTIONS")
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", NO_STORE_CACHE_CONTROL)
        self._base_headers(origin)
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(body)

    do_POST = _method_not_allowed
    do_PUT = _method_not_allowed
    do_PATCH = _method_not_allowed
    do_DELETE = _method_not_allowed


def make_server(
    reader: VerifiedNationalBundleReader,
    *,
    port: int,
    allowed_origins: Iterable[str] = DEFAULT_ALLOWED_ORIGINS,
) -> ThreadingHTTPServer:
    if isinstance(port, bool) or not isinstance(port, int) or not 0 <= port <= 65535:
        raise NationalBundleServerError("port must be between 0 and 65535")
    handler = partial(
        NationalBundleHandler,
        reader=reader,
        allowed_origins=_normalize_origins(allowed_origins),
    )
    return ThreadingHTTPServer((LOOPBACK_HOST, port), handler)


def build_service(
    config: ServerConfig,
    *,
    catalog_loader: Callable[[Path], Mapping[str, Any]] = _load_catalog,
    server_factory: Callable[..., ThreadingHTTPServer] = make_server,
) -> NationalBundleService:
    if not isinstance(config, ServerConfig):
        raise TypeError("config must be a ServerConfig")
    if isinstance(config.port, bool) or not isinstance(config.port, int) or not 0 <= config.port <= 65535:
        raise NationalBundleServerError("port must be between 0 and 65535")
    reader = VerifiedNationalBundleReader.load(
        Path(config.bundle_dir),
        Path(config.catalog_json),
        catalog_loader=catalog_loader,
    )
    server = None
    try:
        server = server_factory(reader, port=config.port)
        address = getattr(server, "server_address", None)
        if not isinstance(address, tuple) or len(address) < 2 or address[0] != LOOPBACK_HOST:
            raise NationalBundleServerError("national data plane did not bind IPv4 loopback")
        return NationalBundleService(reader=reader, server=server)
    except Exception:
        if server is not None:
            server.server_close()
        raise


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle-dir", required=True, type=Path)
    parser.add_argument("--catalog-json", required=True, type=Path)
    parser.add_argument("--port", required=True, type=int)
    return parser


def parse_config(argv: Sequence[str] | None = None) -> ServerConfig:
    arguments = build_parser().parse_args(argv)
    return ServerConfig(
        bundle_dir=arguments.bundle_dir,
        catalog_json=arguments.catalog_json,
        port=arguments.port,
    )


def serve_service(
    service: NationalBundleService,
    *,
    emit: Callable[[str], None] = print,
) -> None:
    emit(
        "ICON nazionale v2 locale verificato: "
        f"{service.reader.source_run_id} · {service.url}"
    )
    emit("Servizio sperimentale della sola pilota, strettamente read-only.")
    try:
        service.server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        service.close()


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    arguments = parser.parse_args(argv)
    try:
        service = build_service(
            ServerConfig(arguments.bundle_dir, arguments.catalog_json, arguments.port)
        )
    except (NationalBundleServerError, OSError, TypeError, ValueError) as error:
        parser.error(str(error))
    serve_service(service)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
