"""Integrated LOCAL ICON pilot: one acquisition -> 215 towns -> JSON preview.

Downloads 14 selected variable files, 0..72 hours, from the public national
grid. This is an explicit bounded full-variable streaming experiment, NOT a
fallback from failed byte ranges and NOT a geographic crop. No app imports,
credentials, cloud writes, background ingestion or live-provider replacement.
Raw point snapshots allow offline derivation replay without a second download.
Live runs checkpoint each fully decoded field with immutable input binding, so
an interrupted late field does not force another download of earlier fields.
"""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timedelta, timezone
import gzip
import hashlib
import json
import math
import os
from pathlib import Path
import re
import tempfile
import time
from urllib.parse import urljoin, urlparse

from benchmark_icon2i import compact_json, load_points
from pilot_policy import assess_window, aggregate_two_hour, rain_interval
from probe_icon2i import BASE, FIELDS, SHORT_NAMES, PublicHTTPError, PublicReader, message_length
from probe_icon2i import relative_humidity_from_dewpoint
from thermal_comfort import calculate_thermal_comfort

MAX_BYTES = 1250 * 1024**2
MAX_FILE_BYTES = 100 * 1024**2
MAX_CHECKPOINT_BYTES = 32 * 1024**2
CHECKPOINT_SCHEMA_VERSION = 1
ACCUM_FIELDS = {"TOT_PREC", "RAIN_CON", "RAIN_GSP", "SNOW_CON", "SNOW_GSP", "GRAU_GSP"}
CONTRACTS = {
    key: dict(suffix=value[0], level_type=value[1], level=value[2],
              units=value[3], short_name=SHORT_NAMES[key],
              step_type="accum" if key == "TOT_PREC" else "instant")
    for key, value in FIELDS.items()
}
for _key, _short, _unit, _param in (
    ("RAIN_CON", "rain_con", "kg m**-2 s**-1", 500137),
    ("RAIN_GSP", "rain_gsp", "kg m**-2 s**-1", 500134),
    ("SNOW_CON", "csfwe", "kg m**-2", 231057),
    ("SNOW_GSP", "lsfwe", "kg m**-2", 231058),
    ("GRAU_GSP", "tgrp", "kg m**-2", 231040),
):
    CONTRACTS[_key] = dict(suffix="surface-0", level_type="surface", level=0,
                           units=_unit, short_name=_short, step_type="accum", param_id=_param)
CONTRACTS["VMAX_10M"] = dict(suffix="heightAboveGround-10", level_type="heightAboveGround",
                              level=10, units="m s**-1", short_name="max_i10fg",
                              step_type="max", param_id=237318)
META_KEYS = ("shortName", "paramId", "units", "typeOfLevel", "level", "dataDate", "dataTime",
             "validityDate", "validityTime", "startStep", "endStep", "stepUnits", "stepType",
             "gridType", "numberOfPoints", "Ni", "Nj", "uvRelativeToGrid", "md5GridSection",
             "packingType", "bitsPerValue", "referenceValue", "binaryScaleFactor", "decimalScaleFactor")


class IncompletePublicRun(ValueError):
    """A listed run does not yet expose the complete required field set."""


class SourceRunNotAdvanced(RuntimeError):
    """No complete usable source run advances the verified public high-water."""

    retryable = True
    reason_code = "source_not_advanced"

    def __init__(self, source_run_id, source_run_high_water=None):
        self.source_run_id = source_run_id
        self.source_run_high_water = source_run_high_water or source_run_id
        super().__init__("No complete usable ICON source run has advanced")


def iso(value):
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def validate_contract(meta, field, run, step):
    spec = CONTRACTS[field]
    if not isinstance(step, int) or isinstance(step, bool) or not 0 <= step <= 72:
        raise ValueError("Invalid native lead")
    if (meta["shortName"] != spec["short_name"] or meta["typeOfLevel"] != spec["level_type"]
            or meta["level"] != spec["level"] or spec["units"] and meta["units"] != spec["units"]):
        raise ValueError(f"Parameter, unit or level changed: {field}")
    if "param_id" in spec and meta["paramId"] != spec["param_id"]:
        raise ValueError("Unexpected parameter identity")
    if f"{meta['dataDate']}{meta['dataTime']:04d}" != run + "00" or meta["endStep"] != step or str(meta["stepUnits"]) != "1":
        raise ValueError("Run/lead mismatch")
    expected = datetime.strptime(run, "%Y%m%d%H") + timedelta(hours=step)
    if f"{meta['validityDate']}{meta['validityTime']:04d}" != expected.strftime("%Y%m%d%H%M"):
        raise ValueError("Validity mismatch")
    expected_start = 0 if field in ACCUM_FIELDS else max(0, step - 1) if field == "VMAX_10M" else step
    if meta["stepType"] != spec["step_type"] or meta["startStep"] != expected_start:
        raise ValueError(f"Unexpected interval semantics: {field}")
    if meta["gridType"] != "regular_ll" or meta["Ni"] <= 0 or meta["Nj"] <= 0 or meta["Ni"] * meta["Nj"] != meta["numberOfPoints"]:
        raise ValueError("Unexpected grid")
    if field in ("U_10M", "V_10M") and meta["uvRelativeToGrid"] != 0:
        raise ValueError("Grid-relative wind requires rotation")


def accumulation_quantum(meta):
    """Simple-packing lattice spacing; not a provider-certified error bound.

    With bits=0 the reference carries the exact decoded constant and the
    lattice spacing is zero. DWD notes that
    RAIN_CON/GSP descriptors retain flux units although the values are already
    accumulations: NEVER multiply those decoded accumulations by 3600.
    """
    reference = meta["referenceValue"]
    if (
        meta["packingType"] != "grid_simple"
        or isinstance(reference, bool)
        or not isinstance(reference, (int, float))
        or not math.isfinite(reference)
        or reference < 0
    ):
        raise ValueError("Rain encoding policy requires grid_simple and a finite non-negative reference")
    bits = meta["bitsPerValue"]
    if any(isinstance(meta[key], bool) or not isinstance(meta[key], int) for key in ("bitsPerValue", "binaryScaleFactor", "decimalScaleFactor")) or not 0 <= bits <= 32:
        raise ValueError("Unexpected packing precision")
    if bits == 0:
        return 0.0
    try:
        quantum = 2.0 ** meta["binaryScaleFactor"] * 10.0 ** (-meta["decimalScaleFactor"])
    except OverflowError as exc:
        raise ValueError("Invalid packing quantum") from exc
    if not math.isfinite(quantum) or quantum <= 0:
        raise ValueError("Invalid packing quantum")
    return quantum


def accumulation_reference_mm(meta):
    """Return the simple-packing reference in decoded accumulation units."""
    reference = meta["referenceValue"]
    decimal_scale = meta["decimalScaleFactor"]
    if (
        meta["packingType"] != "grid_simple"
        or isinstance(reference, bool)
        or not isinstance(reference, (int, float))
        or not math.isfinite(reference)
        or reference < 0
        or isinstance(decimal_scale, bool)
        or not isinstance(decimal_scale, int)
    ):
        raise ValueError("Invalid simple-packing accumulation reference")
    try:
        result = float(reference) * 10.0 ** (-decimal_scale)
    except OverflowError as exc:
        raise ValueError("Invalid simple-packing accumulation reference") from exc
    if not math.isfinite(result) or result < 0:
        raise ValueError("Invalid simple-packing accumulation reference")
    return result


def _valid_packing_error(value):
    """Optional encoding error must be finite and nonnegative, never a default zero."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    try:
        return math.isfinite(value) and value >= 0
    except OverflowError:
        return False


def stream_messages(chunks, expected_count=73):
    """Decode framing across arbitrary network chunks, bounded to one message."""
    buffer = bytearray()
    length = None
    count = 0
    for chunk in chunks:
        if len(chunk) > 64 * 1024:
            raise ValueError("Unbounded source chunk")
        buffer.extend(chunk)
        while True:
            if length is None:
                if len(buffer) < 16:
                    break
                length = message_length(buffer[:16])
            if len(buffer) < length:
                break
            if count >= expected_count:
                raise ValueError("Extra GRIB message")
            message = bytes(buffer[:length])
            del buffer[:length]
            length = None
            if message[-4:] != b"7777":
                raise ValueError("Corrupt GRIB trailer")
            count += 1
            yield message
    if buffer or count != expected_count:
        raise ValueError("Truncated stream or missing hourly messages")


class StreamingReader(PublicReader):
    def __init__(self):
        super().__init__(MAX_BYTES)
        self.network_seconds = 0.0
        self.calls = []

    def get(self, url, start=None, end=None):
        before, started = self.bytes_read, time.perf_counter()
        try:
            return super().get(url, start, end)
        finally:
            elapsed = time.perf_counter() - started
            self.network_seconds += elapsed
            self.calls.append(dict(url=url, bytes=self.bytes_read - before, network_seconds=elapsed, kind="metadata"))

    def chunks(self, url):
        parsed = urlparse(url)
        if not url.startswith(BASE) or parsed.hostname != urlparse(BASE).hostname or not parsed.path.endswith(".grib") or parsed.query:
            raise ValueError("Only anonymous public ICON variable files allowed")
        started = time.perf_counter()
        self.requests += 1
        response = self.session.get(url, stream=True, timeout=(15, 45), allow_redirects=False)
        network = time.perf_counter() - started
        count = 0
        digest = hashlib.sha256()
        success = False
        try:
            if response.status_code != 200:
                raise PublicHTTPError(response.status_code, operation="source_variable")
            if response.headers.get("Content-Encoding", "identity") != "identity":
                raise ValueError("Expected uncompressed full selected-variable HTTP 200")
            raw_length = response.headers.get("Content-Length", "")
            if not raw_length.isdigit():
                raise ValueError("Missing bounded Content-Length")
            total = int(raw_length)
            if not 20 <= total <= MAX_FILE_BYTES or self.bytes_read + total > self.max_bytes:
                raise ValueError("File or total download budget exceeded")
            iterator = iter(response.iter_content(64 * 1024))
            while True:
                started = time.perf_counter()
                try:
                    chunk = next(iterator)
                except StopIteration:
                    network += time.perf_counter() - started
                    break
                network += time.perf_counter() - started
                self.bytes_read += len(chunk)
                count += len(chunk)
                if count > total or self.bytes_read > self.max_bytes:
                    raise ValueError("Streaming transfer budget exceeded")
                digest.update(chunk)
                yield chunk
            if count != total:
                raise ValueError("Truncated HTTP body")
            success = True
        finally:
            response.close()
            self.network_seconds += network
            self.calls.append(dict(url=url, bytes=count, network_seconds=network,
                                   sha256=digest.hexdigest(), success=success, kind="full_variable_stream"))


class Decoder:
    def __init__(self, points):
        import eccodes
        self.ec = eccodes
        self.points = points
        self.grid_points = self.grid_hash = self.indexes = None
        self.seen = set()
        self.seconds = 0.0
        self.mapping_seconds = 0.0
        self.mapping_builds = 0

    def decode(self, data, field, run, step):
        identity = (field, run, step)
        if identity in self.seen:
            raise ValueError("Duplicate decoding")
        ec, started = self.ec, time.perf_counter()
        handle = ec.codes_new_from_message(data)
        try:
            ec.codes_set(handle, "stepUnits", 1)
            meta = {key: ec.codes_get(handle, key) for key in META_KEYS}
            # Optional ecCodes diagnostic; absence never changes the decoded value.
            try:
                packing_error = ec.codes_get(handle, "packingError")
                meta["packingError"] = float(packing_error) if _valid_packing_error(packing_error) else None
            except Exception:
                meta["packingError"] = None
            validate_contract(meta, field, run, step)
            if field in ACCUM_FIELDS:
                meta["encoding_quantum_mm"] = accumulation_quantum(meta)
            if self.grid_hash is None:
                mapping_start = time.perf_counter()
                nearest = ec.codes_grib_find_nearest_multiple(handle, False,
                    [p["latitude"] for p in self.points], [p["longitude"] for p in self.points])
                if len(nearest) != len(self.points) or any(
                    isinstance(p["distance"], bool) or not isinstance(p["distance"], (int, float))
                    or not math.isfinite(p["distance"]) or not 0 <= p["distance"] <= 5
                    or isinstance(p["index"], bool) or not isinstance(p["index"], int)
                    or not 0 <= p["index"] < meta["numberOfPoints"]
                    or any(isinstance(p[k], bool) or not isinstance(p[k], (int, float)) or not math.isfinite(p[k]) for k in ("lat", "lon"))
                    or not 45 <= p["lat"] <= 47 or not 12 <= p["lon"] <= 14.5
                    for p in nearest):
                    raise ValueError("Invalid grid-cell mapping")
                self.grid_points = [{k: p[k] for k in ("lat", "lon", "distance", "index")} for p in nearest]
                self.indexes = [p["index"] for p in nearest]
                self.grid_hash = meta["md5GridSection"]
                self.mapping_builds += 1
                values = [float(p["value"]) for p in nearest]
                self.mapping_seconds += time.perf_counter() - mapping_start
            else:
                if meta["md5GridSection"] != self.grid_hash:
                    raise ValueError("Grid changed; refusing cached cell indexes")
                values = [float(value) for value in ec.codes_get_elements(handle, "values", self.indexes)]
            missing = ec.codes_get(handle, "missingValue")
            if len(values) != len(self.points) or any(not math.isfinite(v) or v == missing for v in values):
                raise ValueError("Nonfinite/missing point data")
            self.seen.add(identity)
            return values, meta
        finally:
            ec.codes_release(handle)
            self.seconds += time.perf_counter() - started


def _canonical_bytes(value):
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
        allow_nan=False,
    ).encode("utf-8")


def _with_checkpoint_integrity(value):
    result = dict(value)
    result["checkpoint_sha256"] = hashlib.sha256(_canonical_bytes(result)).hexdigest()
    return result


def _verify_checkpoint_integrity(value, expected_keys):
    if not isinstance(value, dict) or set(value) != set(expected_keys) | {"checkpoint_sha256"}:
        raise ValueError("Checkpoint schema mismatch")
    digest = value.get("checkpoint_sha256")
    if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
        raise ValueError("Checkpoint digest is invalid")
    body = {key: item for key, item in value.items() if key != "checkpoint_sha256"}
    if hashlib.sha256(_canonical_bytes(body)).hexdigest() != digest:
        raise ValueError("Checkpoint digest mismatch")
    return body


def _run_times(run):
    run_time = datetime.strptime(run, "%Y%m%d%H").replace(tzinfo=timezone.utc)
    return run_time, [iso(run_time + timedelta(hours=step)) for step in range(73)]


def _direct_children(directory, links, *, directories):
    """Return unique direct child URLs from an untrusted HTML directory listing."""
    base = urlparse(directory)
    if not base.path.endswith("/"):
        raise ValueError("Directory URL must end with a slash")
    found = set()
    for link in links:
        if not isinstance(link, str):
            continue
        candidate = urlparse(urljoin(directory, link))
        if (
            candidate.scheme != base.scheme
            or candidate.netloc != base.netloc
            or candidate.query
            or candidate.fragment
            or not candidate.path.startswith(base.path)
        ):
            continue
        relative = candidate.path[len(base.path):]
        if directories:
            if not relative.endswith("/") or not relative[:-1] or "/" in relative[:-1]:
                continue
        elif not relative or relative.endswith("/") or "/" in relative:
            continue
        found.add(candidate.geturl())
    return sorted(found)


def _field_urls_for_run(reader, run):
    run_url = f"{BASE}{run}/"
    advertised = {
        urlparse(url).path.rstrip("/").rsplit("/", 1)[-1]
        for url in _direct_children(run_url, reader.links(run_url), directories=True)
    }
    missing_directories = set(CONTRACTS) - advertised
    if missing_directories:
        raise IncompletePublicRun(
            f"Run {run} is still partial; missing field directories: {','.join(sorted(missing_directories))}"
        )
    urls = {}
    for field, spec in CONTRACTS.items():
        directory = f"{run_url}{field}/"
        suffix = f"_{spec['suffix']}.grib"
        matches = [
            url for url in _direct_children(directory, reader.links(directory), directories=False)
            if urlparse(url).path.endswith(suffix)
        ]
        if len(matches) != 1:
            raise IncompletePublicRun(f"Run {run} has missing/ambiguous field {field}")
        urls[field] = matches[0]
    return urls


def _validated_source_run_id(source_run_id):
    if not isinstance(source_run_id, str) or not re.fullmatch(r"\d{8}T\d{6}Z", source_run_id):
        raise ValueError("ICON source run high-water is invalid")
    try:
        parsed = datetime.strptime(source_run_id, "%Y%m%dT%H%M%SZ")
    except ValueError as error:
        raise ValueError("ICON source run high-water is invalid") from error
    if parsed.strftime("%Y%m%dT%H%M%SZ") != source_run_id:
        raise ValueError("ICON source run high-water is invalid")
    return source_run_id


def _directory_source_run_id(run):
    return datetime.strptime(run, "%Y%m%d%H").strftime("%Y%m%dT%H0000Z")


def discover_complete_run(reader, now, requested_run=None, *, source_run_high_water=None):
    """Select the newest listed, complete run that still covers the next 48h.

    A newer directory can become visible while its variable files are still
    arriving. Automatic discovery skips such a partial run; an explicitly
    requested run fails closed rather than silently changing model cycle.  A
    verified public high-water lets the cloud worker stop after discovery when
    the provider has not advanced, before downloading or materializing a second
    representation of a run already observed (including revoked runs).
    """
    high_water = (
        None
        if source_run_high_water is None
        else _validated_source_run_id(source_run_high_water)
    )
    root_runs = {
        urlparse(url).path.rstrip("/").rsplit("/", 1)[-1]
        for url in _direct_children(BASE, reader.links(BASE), directories=True)
        if re.fullmatch(r"\d{10}", urlparse(url).path.rstrip("/").rsplit("/", 1)[-1])
    }
    if requested_run is not None and (
        not isinstance(requested_run, str)
        or not re.fullmatch(r"\d{10}", requested_run)
        or requested_run not in root_runs
    ):
        raise ValueError("Requested public run unavailable")
    candidates = [requested_run] if requested_run is not None else sorted(root_runs, reverse=True)
    incomplete = []
    for candidate in candidates:
        candidate_source_run_id = _directory_source_run_id(candidate)
        # Candidates are newest-first. Once discovery reaches the verified
        # high-water, neither it nor any remaining directory may be acquired.
        if high_water is not None and candidate_source_run_id <= high_water:
            raise SourceRunNotAdvanced(candidate_source_run_id, high_water)
        run_time, times = _run_times(candidate)
        if not assess_window(iso(run_time), times, iso(now))["usable"]:
            if requested_run is not None:
                raise ValueError("Requested public run cannot cover the next 48h under pilot policy")
            continue
        try:
            field_urls = _field_urls_for_run(reader, candidate)
            return candidate, run_time, times, field_urls
        except IncompletePublicRun as exc:
            if requested_run is not None:
                raise ValueError(str(exc)) from exc
            incomplete.append(candidate)
    if high_water is not None and requested_run is None:
        # A verified publication exists, but every newer provider directory was
        # future-dated, expired, under-covered or incomplete. That is a liveness
        # condition, not evidence of a malformed source or configuration.
        raise SourceRunNotAdvanced(high_water, high_water)
    suffix = f"; partial runs skipped: {','.join(incomplete)}" if incomplete else ""
    raise ValueError(f"No complete public run can cover the next 48h under pilot policy{suffix}")


def _checkpoint_intent(run, run_time, points, catalog_sha, field_urls):
    contracts = {field: dict(spec) for field, spec in CONTRACTS.items()}
    return _with_checkpoint_integrity({
        "schema_version": CHECKPOINT_SCHEMA_VERSION,
        "kind": "icon_extraction_checkpoint_intent",
        "run": run,
        "run_utc": iso(run_time),
        "catalog_sha256": catalog_sha,
        "points_sha256": hashlib.sha256(_canonical_bytes(points)).hexdigest(),
        "contracts_sha256": hashlib.sha256(_canonical_bytes(contracts)).hexdigest(),
        "field_urls": dict(field_urls),
    })


def _read_bounded_json(path):
    if path.is_symlink() or not path.is_file():
        raise ValueError("Checkpoint member must be a regular file")
    size = path.stat().st_size
    if not 1 <= size <= MAX_CHECKPOINT_BYTES:
        raise ValueError("Checkpoint member size is invalid")
    data = path.read_bytes()
    if len(data) != size:
        raise ValueError("Checkpoint member changed while reading")
    try:
        return json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("Checkpoint member is not valid JSON") from exc


def _fsync_directory(path):
    if os.name == "nt":
        return
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _commit_new_bytes(path, encoded, label):
    """Durably publish a new checkpoint member without any replace operation."""
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{label}.", suffix=".part", dir=path.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            descriptor = None
            stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())
        os.link(temporary, path)
        _fsync_directory(path.parent)
    finally:
        if descriptor is not None:
            os.close(descriptor)
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass


_INTENT_KEYS = {
    "schema_version", "kind", "run", "run_utc", "catalog_sha256",
    "points_sha256", "contracts_sha256", "field_urls",
}
_FIELD_CHECKPOINT_KEYS = {
    "schema_version", "kind", "intent_sha256", "run", "field", "url",
    "grid_hash", "grid_points", "data",
}


def _read_existing_checkpoint_intent(checkpoint_dir):
    if not checkpoint_dir.exists():
        return None
    if checkpoint_dir.is_symlink() or not checkpoint_dir.is_dir():
        raise ValueError("Checkpoint path must be a regular directory")
    entries = list(checkpoint_dir.iterdir())
    intent_path = checkpoint_dir / "intent.json"
    if not intent_path.exists():
        if any(not (entry.is_file() and not entry.is_symlink() and entry.name.startswith(".intent.") and entry.name.endswith(".part")) for entry in entries):
            raise ValueError("Checkpoint directory is non-empty but has no valid intent")
        return None
    allowed = {"intent.json", "fields"}
    if any(entry.name not in allowed and not (entry.is_file() and not entry.is_symlink() and entry.name.startswith(".intent.") and entry.name.endswith(".part")) for entry in entries):
        raise ValueError("Checkpoint directory contains unexpected members")
    record = _read_bounded_json(intent_path)
    body = _verify_checkpoint_integrity(record, _INTENT_KEYS)
    if (
        body["schema_version"] != CHECKPOINT_SCHEMA_VERSION
        or body["kind"] != "icon_extraction_checkpoint_intent"
        or not isinstance(body["run"], str)
        or not re.fullmatch(r"\d{10}", body["run"])
    ):
        raise ValueError("Checkpoint intent identity is invalid")
    return record


def _validate_checkpoint_layout(fields_dir):
    if fields_dir.is_symlink() or not fields_dir.is_dir():
        raise ValueError("Checkpoint fields path must be a regular directory")
    allowed = {f"{field}.json" for field in CONTRACTS}
    for entry in fields_dir.iterdir():
        if entry.name in allowed and entry.is_file() and not entry.is_symlink():
            continue
        if entry.is_file() and not entry.is_symlink() and entry.name.startswith(".") and entry.name.endswith(".part"):
            continue
        raise ValueError("Checkpoint fields directory contains unexpected members")


def _prepare_checkpoint(checkpoint_dir, expected_intent):
    if checkpoint_dir.is_symlink():
        raise ValueError("Checkpoint path cannot be a symlink")
    if not checkpoint_dir.exists():
        if not checkpoint_dir.parent.is_dir():
            raise ValueError("Checkpoint parent directory does not exist")
        checkpoint_dir.mkdir(exist_ok=True)
    existing = _read_existing_checkpoint_intent(checkpoint_dir)
    if existing is None:
        try:
            _commit_new_bytes(checkpoint_dir / "intent.json", _canonical_bytes(expected_intent), "intent")
        except FileExistsError:
            existing = _read_existing_checkpoint_intent(checkpoint_dir)
    if existing is not None and existing != expected_intent:
        raise ValueError("Checkpoint intent is bound to different inputs")
    fields_dir = checkpoint_dir / "fields"
    if not fields_dir.exists():
        fields_dir.mkdir(exist_ok=True)
    _validate_checkpoint_layout(fields_dir)
    return fields_dir, expected_intent["checkpoint_sha256"]


def _validate_checkpoint_mapping(points, grid_points, number_of_points):
    if not isinstance(grid_points, list) or len(grid_points) != len(points):
        raise ValueError("Checkpoint municipality mapping is incomplete")
    for point, grid in zip(points, grid_points, strict=True):
        if not isinstance(grid, dict) or set(grid) != {"lat", "lon", "distance", "index"}:
            raise ValueError("Checkpoint grid mapping schema mismatch")
        lat, lon, distance, index = grid["lat"], grid["lon"], grid["distance"], grid["index"]
        if (
            any(isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) for value in (lat, lon, distance))
            or not 45 <= lat <= 47
            or not 12 <= lon <= 14.5
            or not 0 <= distance <= 5
            or isinstance(index, bool)
            or not isinstance(index, int)
            or not 0 <= index < number_of_points
        ):
            raise ValueError("Checkpoint grid mapping is invalid")
        if not (45 <= point["latitude"] <= 47 and 12 <= point["longitude"] <= 14.5):
            raise ValueError("Checkpoint is bound to invalid municipality coordinates")


def _validate_field_checkpoint(record, *, intent_sha, field, run, url, points):
    body = _verify_checkpoint_integrity(record, _FIELD_CHECKPOINT_KEYS)
    if (
        body["schema_version"] != CHECKPOINT_SCHEMA_VERSION
        or body["kind"] != "icon_extracted_field_checkpoint"
        or body["intent_sha256"] != intent_sha
        or body["run"] != run
        or body["field"] != field
        or body["url"] != url
    ):
        raise ValueError("Checkpoint field binding mismatch")
    data = body["data"]
    expected_data_keys = {
        "url", "values", "metadata", "downloaded_bytes", "sha256",
        "network_seconds", "decode_seconds",
    }
    if not isinstance(data, dict) or set(data) != expected_data_keys or data["url"] != url:
        raise ValueError("Checkpoint field data schema mismatch")
    if (
        isinstance(data["downloaded_bytes"], bool)
        or not isinstance(data["downloaded_bytes"], int)
        or not 20 <= data["downloaded_bytes"] <= MAX_FILE_BYTES
        or not isinstance(data["sha256"], str)
        or not re.fullmatch(r"[0-9a-f]{64}", data["sha256"])
        or any(
            isinstance(data[key], bool)
            or not isinstance(data[key], (int, float))
            or not math.isfinite(data[key])
            or data[key] < 0
            for key in ("network_seconds", "decode_seconds")
        )
        or not isinstance(data["values"], list)
        or not isinstance(data["metadata"], list)
        or len(data["values"]) != 73
        or len(data["metadata"]) != 73
    ):
        raise ValueError("Checkpoint field metrics or dimensions are invalid")
    grid_hash = body["grid_hash"]
    if not isinstance(grid_hash, str) or not re.fullmatch(r"[0-9a-f]{32}", grid_hash):
        raise ValueError("Checkpoint grid hash is invalid")
    number_of_points = None
    for step, (values, meta) in enumerate(zip(data["values"], data["metadata"], strict=True)):
        expected_meta_keys = set(META_KEYS) | ({"encoding_quantum_mm"} if field in ACCUM_FIELDS else set())
        # Older field checkpoints omit packingError. Accept that one optional
        # key without relaxing the required metadata or allowing unknown keys.
        if not isinstance(meta, dict) or set(meta) - {"packingError"} != expected_meta_keys:
            raise ValueError("Checkpoint metadata is invalid")
        packing_error = meta.get("packingError")
        if packing_error is not None and not _valid_packing_error(packing_error):
            raise ValueError("Checkpoint packing error is invalid")
        validate_contract(meta, field, run, step)
        if meta["md5GridSection"] != grid_hash:
            raise ValueError("Checkpoint grid hash changed")
        number_of_points = number_of_points or meta["numberOfPoints"]
        if meta["numberOfPoints"] != number_of_points:
            raise ValueError("Checkpoint grid dimensions changed")
        if (
            not isinstance(values, list)
            or len(values) != len(points)
            or any(isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) for value in values)
        ):
            raise ValueError("Checkpoint point values are invalid")
        if field in ACCUM_FIELDS and meta.get("encoding_quantum_mm") != accumulation_quantum(meta):
            raise ValueError("Checkpoint accumulation precision is invalid")
    _validate_checkpoint_mapping(points, body["grid_points"], number_of_points)
    return body


def _load_field_checkpoint(fields_dir, *, intent_sha, field, run, url, points):
    path = fields_dir / f"{field}.json"
    if not path.exists():
        return None
    return _validate_field_checkpoint(
        _read_bounded_json(path), intent_sha=intent_sha, field=field,
        run=run, url=url, points=points,
    )


def _save_field_checkpoint(fields_dir, *, intent_sha, field, run, url, points, decoder, data):
    record = _with_checkpoint_integrity({
        "schema_version": CHECKPOINT_SCHEMA_VERSION,
        "kind": "icon_extracted_field_checkpoint",
        "intent_sha256": intent_sha,
        "run": run,
        "field": field,
        "url": url,
        "grid_hash": decoder.grid_hash,
        "grid_points": decoder.grid_points,
        "data": data,
    })
    _validate_field_checkpoint(
        record, intent_sha=intent_sha, field=field, run=run, url=url, points=points
    )
    _commit_new_bytes(fields_dir / f"{field}.json", _canonical_bytes(record), field)
    return record


def acquire(run=None, checkpoint_dir=None, now=None, *, source_run_high_water=None):
    from process_memory import process_memory_bytes
    started = time.perf_counter()
    points, catalog_sha = load_points()
    reader, decoder = StreamingReader(), Decoder(points)
    now = now or datetime.now(timezone.utc)
    checkpoint_dir = Path(checkpoint_dir) if checkpoint_dir is not None else None
    existing_intent = _read_existing_checkpoint_intent(checkpoint_dir) if checkpoint_dir else None
    if existing_intent is not None:
        intent_body = _verify_checkpoint_integrity(existing_intent, _INTENT_KEYS)
        local_contracts_sha = hashlib.sha256(
            _canonical_bytes({field: dict(spec) for field, spec in CONTRACTS.items()})
        ).hexdigest()
        if (
            intent_body["catalog_sha256"] != catalog_sha
            or intent_body["points_sha256"] != hashlib.sha256(_canonical_bytes(points)).hexdigest()
            or intent_body["contracts_sha256"] != local_contracts_sha
        ):
            raise ValueError("Checkpoint intent no longer matches the local catalog/contracts")
        if run is not None and run != intent_body["run"]:
            raise ValueError("Requested run conflicts with the existing checkpoint intent")
        run = intent_body["run"]
    run, run_time, times, field_urls = discover_complete_run(
        reader, now, run, source_run_high_water=source_run_high_water
    )
    fields_dir = intent_sha = None
    if checkpoint_dir:
        expected_intent = _checkpoint_intent(run, run_time, points, catalog_sha, field_urls)
        fields_dir, intent_sha = _prepare_checkpoint(checkpoint_dir, expected_intent)
    print(f"Integrated run {run}: 14 fields, 73 times, {len(points)} towns, budget {MAX_BYTES} bytes", flush=True)
    raw = {}
    resumed_fields = []
    acquired_fields = []
    for field in CONTRACTS:
        url = field_urls[field]
        restored = _load_field_checkpoint(
            fields_dir, intent_sha=intent_sha, field=field, run=run, url=url, points=points
        ) if fields_dir else None
        if restored is not None:
            if decoder.grid_hash is None:
                decoder.grid_hash = restored["grid_hash"]
                decoder.grid_points = restored["grid_points"]
                decoder.indexes = [item["index"] for item in decoder.grid_points]
            elif decoder.grid_hash != restored["grid_hash"] or decoder.grid_points != restored["grid_points"]:
                raise ValueError("Checkpoint fields disagree on the municipality grid mapping")
            decoder.seen.update((field, run, step) for step in range(73))
            raw[field] = restored["data"]
            resumed_fields.append(field)
            print(f"{field}: resumed from validated checkpoint", flush=True)
            continue
        values, metadata = [], []
        decode_before = decoder.seconds
        for step, message in enumerate(stream_messages(reader.chunks(url))):
            point_values, meta = decoder.decode(message, field, run, step)
            values.append(point_values)
            metadata.append(meta)
        call = reader.calls[-1]
        raw[field] = dict(url=url, values=values, metadata=metadata, downloaded_bytes=call["bytes"],
                          sha256=call["sha256"], network_seconds=call["network_seconds"],
                          decode_seconds=decoder.seconds - decode_before)
        if fields_dir:
            _save_field_checkpoint(
                fields_dir, intent_sha=intent_sha, field=field, run=run, url=url,
                points=points, decoder=decoder, data=raw[field],
            )
        acquired_fields.append(field)
        print(f"{field}: {len(values)} messages, {call['bytes']/1e6:.3f} MB, download {call['network_seconds']:.2f}s, decode {raw[field]['decode_seconds']:.2f}s", flush=True)
    source_downloaded_bytes = sum(item["downloaded_bytes"] for item in raw.values())
    source_download_seconds = sum(item["network_seconds"] for item in raw.values())
    source_decode_seconds = sum(item["decode_seconds"] for item in raw.values())
    return dict(schema_version=1, kind="extracted_source_snapshot", run=run, run_utc=iso(run_time),
                acquired_at_utc=iso(now), acquisition_finished_at_utc=iso(datetime.now(timezone.utc)),
                times_utc=times, points=points, catalog_sha256=catalog_sha, grid_points=decoder.grid_points,
                grid_hash=decoder.grid_hash, raw=raw,
                metrics=dict(downloaded_bytes=reader.bytes_read,
                             http_get_requests=reader.requests,
                             download_seconds=reader.network_seconds, decode_seconds=decoder.seconds,
                             current_execution_metrics_scope="This invocation, including discovery listings; resumed field bodies are not counted again.",
                             source_field_downloaded_bytes=source_downloaded_bytes,
                             source_field_download_seconds=source_download_seconds,
                             source_field_decode_seconds=source_decode_seconds,
                             resumed_fields=resumed_fields, newly_acquired_fields=acquired_fields,
                             mapping_seconds=decoder.mapping_seconds, grid_mapping_builds=decoder.mapping_builds,
                             unique_decoded_messages=len(decoder.seen), duplicate_decoded_messages=0,
                             acquisition_seconds=time.perf_counter()-started,
                             peak_working_set_bytes=process_memory_bytes()["peak_working_set_bytes"]))


def validate_snapshot(snapshot):
    if snapshot.get("schema_version") != 1 or snapshot.get("kind") != "extracted_source_snapshot":
        raise ValueError("Not an extracted source snapshot")
    points, raw, times = snapshot["points"], snapshot["raw"], snapshot["times_utc"]
    run = snapshot["run"]
    run_time = datetime.strptime(run, "%Y%m%d%H").replace(tzinfo=timezone.utc)
    if snapshot["run_utc"] != iso(run_time) or times != [iso(run_time + timedelta(hours=s)) for s in range(73)]:
        raise ValueError("Snapshot time coverage mismatch")
    if len(points) != 215 or len({p["slug"] for p in points}) != 215 or len(snapshot["grid_points"]) != 215:
        raise ValueError("Snapshot municipality mapping mismatch")
    for point, grid in zip(points, snapshot["grid_points"], strict=True):
        for record, lat_key, lon_key in ((point, "latitude", "longitude"), (grid, "lat", "lon")):
            lat, lon = record[lat_key], record[lon_key]
            if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) for v in (lat, lon)) or not 45 <= lat <= 47 or not 12 <= lon <= 14.5:
                raise ValueError("Invalid snapshot coordinates")
        if isinstance(grid["index"], bool) or not isinstance(grid["index"], int) or grid["index"] < 0:
            raise ValueError("Invalid snapshot grid index")
        if isinstance(grid["distance"], bool) or not isinstance(grid["distance"], (int, float)) or not math.isfinite(grid["distance"]) or not 0 <= grid["distance"] <= 5:
            raise ValueError("Invalid snapshot grid distance")
    if set(raw) != set(CONTRACTS):
        raise ValueError("Snapshot missing/extra fields")
    for field, data in raw.items():
        if len(data["values"]) != 73 or len(data["metadata"]) != 73:
            raise ValueError("Incomplete native hourly field")
        for step, (values, meta) in enumerate(zip(data["values"], data["metadata"], strict=True)):
            validate_contract(meta, field, run, step)
            if meta["md5GridSection"] != snapshot["grid_hash"]:
                raise ValueError("Snapshot grid mismatch")
            if any(grid["index"] >= meta["numberOfPoints"] for grid in snapshot["grid_points"]):
                raise ValueError("Snapshot grid index outside domain")
            if len(values) != 215 or any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) for v in values):
                raise ValueError("Missing/invalid raw point data")
            if field in ACCUM_FIELDS and meta["encoding_quantum_mm"] != accumulation_quantum(meta):
                raise ValueError("Snapshot encoding policy mismatch")


def rounded(value, digits=3):
    return round(value, digits) if value is not None else None


def derive(snapshot, now=None):
    from icon_semantics import icon_condition, pilot_capabilities
    from local_pipeline.accumulation_tolerance import build_accumulation_quality
    validate_snapshot(snapshot)
    now = now or datetime.now(timezone.utc)
    raw, times = snapshot["raw"], snapshot["times_utc"]
    towns, issues = [], Counter()
    for index, point in enumerate(snapshot["points"]):
        hourly = []
        for step, valid_at in enumerate(times):
            flags = []
            values = {field: data["values"][step][index] for field, data in raw.items()}
            t, td = values["T_2M"] - 273.15, values["TD_2M"] - 273.15
            wind = math.hypot(values["U_10M"], values["V_10M"])
            direction = (270 - math.degrees(math.atan2(values["V_10M"], values["U_10M"]))) % 360 if wind else None
            rh = at = hi = wc = None
            try:
                rh = relative_humidity_from_dewpoint(t, td)
            except ValueError:
                flags.append("invalid_T_Td_for_RH_no_clipping")
            if rh is not None:
                thermal = calculate_thermal_comfort(temperature_c=t, relative_humidity_pct=rh, wind_10m_m_s=wind)
                at, hi, wc = (thermal.apparent_temperature.value_c, thermal.heat_index.value_c, thermal.wind_chill.value_c)
            intervals = {}
            for field in sorted(ACCUM_FIELDS):
                if step == 0:
                    intervals[field] = dict(value_mm=None, raw_increment_mm=None, status="no_previous_interval", uncertainty_mm=None)
                else:
                    data = raw[field]
                    intervals[field] = rain_interval(data["values"][step-1][index], values[field],
                        data["metadata"][step-1]["encoding_quantum_mm"], data["metadata"][step]["encoding_quantum_mm"],
                        previous_reference_mm=accumulation_reference_mm(data["metadata"][step-1]),
                        current_reference_mm=accumulation_reference_mm(data["metadata"][step]))
                if intervals[field]["status"] != "valid":
                    flags.append(f"{field}:{intervals[field]['status']}")
            def component_total(fields):
                parts = [intervals[f]["value_mm"] for f in fields]
                return sum(parts) if all(value is not None for value in parts) else None
            packing_errors = {field: [raw[field]["metadata"][step-1].get("packingError"),
                                      raw[field]["metadata"][step].get("packingError")]
                              for field in ACCUM_FIELDS} if step else {}
            accumulation_quality = build_accumulation_quality(intervals, packing_errors)
            cloud = values["CLCT"]
            if not 0 <= cloud <= 100:
                cloud = None
                flags.append("invalid_cloud_cover")
            condition = icon_condition(values["WW"])
            if condition["status"] != "valid":
                flags.append("WW_unknown_or_unverified")
            gust = values["VMAX_10M"] if step > 0 and values["VMAX_10M"] >= 0 else None
            if gust is None:
                flags.append("gust_previous_hour_unavailable")
            row = dict(valid_at_utc=valid_at, temperature_c=rounded(t), dewpoint_c=rounded(td),
                relative_humidity_pct=rounded(rh), apparent_temperature_c=rounded(at),
                heat_index_c=rounded(hi), wind_chill_c=rounded(wc), wind_m_s=rounded(wind),
                wind_from_degrees=rounded(direction) % 360 if direction is not None else None,
                wind_gust_m_s=rounded(gust),
                pressure_msl_hpa=rounded(values["PMSL"]/100), cloud_cover_pct=rounded(cloud),
                condition=condition, precipitation_previous_hour_mm=intervals["TOT_PREC"]["value_mm"],
                rain_previous_hour_mm=component_total(("RAIN_CON", "RAIN_GSP")),
                convective_rain_previous_hour_mm=intervals["RAIN_CON"]["value_mm"],
                snow_water_equivalent_previous_hour_mm=component_total(("SNOW_CON", "SNOW_GSP")),
                graupel_water_equivalent_previous_hour_mm=intervals["GRAU_GSP"]["value_mm"],
                precipitation_probability_pct=None, visibility_m=None,
                precipitation_encoding=intervals, quality_flags=flags,
                accumulation_quality=accumulation_quality)
            hourly.append(row)
            issues.update(flags)
        past = [row for row in hourly if datetime.fromisoformat(row["valid_at_utc"].replace("Z", "+00:00")) <= now]
        towns.append(dict(id=point["slug"], name=point["name"], latitude=point["latitude"], longitude=point["longitude"],
            grid_point=snapshot["grid_points"][index], current=past[-1] if past else None,
            hourly=hourly, two_hourly=aggregate_two_hour(hourly[1:]),
            pollen=dict(status="blocked_credentials_and_dataset_terms", values=None), daily=[]))
    payload = dict(schema_version=1, status="partial_pilot_not_production", generated_at_utc=iso(now),
        run_utc=snapshot["run_utc"],
        sources=dict(icon=dict(status="acquired_and_decoded", run_utc=snapshot["run_utc"],
            attribution="Agenzia ItaliaMeteo / Arpae Emilia-Romagna Idro-Meteo-Clima", license="CC BY 4.0",
            url=BASE+snapshot["run"]+"/"),
            cams=dict(status="not_acquired", detail="Credenziali ADS e accettazione personale licenza necessarie; nessun fallback Open-Meteo."),
            observations=dict(status="not_compared", detail="Modello non ancora validato contro stazioni con tempi e quote allineati.")),
        capabilities=pilot_capabilities(), metrics=dict(snapshot["metrics"]),
        validation=assess_window(snapshot["run_utc"], times, iso(now)),
        processing=dict(location="Nearest cell, no elevation or coast correction; representative coordinates derived from local ISTAT boundaries and IRDAT localities.",
            pressure="MSLP only, never station pressure.",
            thermal="Steadman/BOM shade apparent temperature, RH derived from T/Td; Heat Index and Wind Chill separate, no blending.",
            ww="ICON significant weather of the previous hour, not a claim of Open-Meteo product equivalence.",
            rain="Same-run differences of decoded GRIB simple-packing values. Quantum is lattice spacing, not a certified error bar: equal decoded accumulations are zero; positive or negative changes within qprev+qcur remain unquantified. Tiny code-0 reference floors below binary64 resolution of one quantum are explicitly normalized to zero; negative changes are never dry-clipped and signed raw increments are retained.",
            components="RAIN_CON/GSP descriptors retain flux units but values are accumulated kg/m2 per DWD; no x3600. Snow/graupel water equivalent, not depth.",
            two_hourly="Sum of both interval precipitation amounts; max of both hourly gust maxima; min/max sampled temperatures, not continuous extrema.",
            time="Full native 0..72h retained; preview displays rolling future48h. Native coverage is not a guaranteed rolling72h.",
            scope="Separate local experiment. Main app, OSMER official bulletin, official alerts, cloud and schedulers untouched."),
        quality_flag_counts=dict(issues), municipalities=towns)
    return payload


def write_new(path, value):
    with path.open("xb") as stream:
        stream.write(compact_json(value))


def run_outputs(*, source_path, payload_path, report_path, run=None, replay=None,
                checkpoint_dir=None, source_run_high_water=None):
    """New immutable run artifacts only: failure cannot overwrite a valid cache."""
    from process_memory import process_memory_bytes
    paths = [payload_path, report_path] + ([] if replay else [source_path])
    if len({p.resolve() for p in paths}) != len(paths) or any(p.exists() or not p.parent.is_dir() for p in paths):
        raise ValueError("Outputs must be distinct NEW files in existing directories")
    if replay and any(p.resolve() == replay.resolve() for p in paths):
        raise ValueError("Cannot overwrite source snapshot")
    if replay and checkpoint_dir is not None:
        raise ValueError("Offline replay cannot consume or mutate a live checkpoint")
    if not replay:
        checkpoint_dir = checkpoint_dir or source_path.with_name(f"{source_path.name}.checkpoint")
        checkpoint_resolved = checkpoint_dir.resolve()
        resolved_outputs = {path.resolve() for path in paths}
        if checkpoint_resolved in resolved_outputs or any(
            checkpoint_resolved in path.parents for path in resolved_outputs
        ):
            raise ValueError("Checkpoint directory cannot alias a final output")
        if checkpoint_dir.exists() and not checkpoint_dir.is_dir():
            raise ValueError("Checkpoint path must be a directory")
        if not checkpoint_dir.exists() and not checkpoint_dir.parent.is_dir():
            raise ValueError("Checkpoint parent directory does not exist")
    started = time.perf_counter()
    if replay:
        snapshot = json.loads(replay.read_text(encoding="utf-8"))
    else:
        snapshot = acquire(
            run,
            checkpoint_dir=checkpoint_dir,
            source_run_high_water=source_run_high_water,
        )
        # Preserve complete extraction before deriving: offline fixes need no new transfer.
        write_new(source_path, snapshot)
    derive_start = time.perf_counter()
    payload = derive(snapshot)
    payload["metrics"]["derive_seconds"] = time.perf_counter() - derive_start
    payload["metrics"]["execution_mode"] = "offline_replay" if replay else "live_integrated"
    payload["metrics"]["total_seconds"] = time.perf_counter() - started
    payload["metrics"]["peak_working_set_bytes"] = process_memory_bytes()["peak_working_set_bytes"]
    # These sizes exclude their own self-referential metric values; actual file
    # bytes/hash are measured in the independent report after serialization.
    measured = compact_json(payload)
    payload["metrics"]["json_bytes"] = len(measured)
    payload["metrics"]["gzip_bytes"] = len(gzip.compress(measured, compresslevel=6, mtime=0))
    payload["metrics"]["size_scope"] = "Payload before adding size metrics; exact artifact sizes are in report"
    encoded = compact_json(payload)
    compressed = gzip.compress(encoded, compresslevel=6, mtime=0)
    with payload_path.open("xb") as destination:
        destination.write(encoded)
    town_sizes = []
    shared = {key: value for key, value in payload.items() if key != "municipalities"}
    for town in payload["municipalities"]:
        one = compact_json(dict(shared, municipalities=[town]))
        town_sizes.append(dict(id=town["id"], json_bytes=len(one), gzip_bytes=len(gzip.compress(one, compresslevel=6, mtime=0))))
    source = replay or source_path
    from local_pipeline.icon_quality import build_source_quality
    source_sha256 = hashlib.sha256(source.read_bytes()).hexdigest()
    source_quality = build_source_quality(snapshot, payload, source_sha256=source_sha256)
    report = dict(status=payload["status"], execution_mode=payload["metrics"]["execution_mode"],
        generated_at_utc=payload["generated_at_utc"], run_utc=payload["run_utc"],
        source_snapshot_sha256=source_sha256, source_quality=source_quality,
        catalog_sha256=snapshot["catalog_sha256"], grid_hash=snapshot["grid_hash"],
        metrics=dict(payload["metrics"], total_including_serialization_and_artifact_write_seconds=time.perf_counter()-started,
                     final_peak_working_set_bytes=process_memory_bytes()["peak_working_set_bytes"]),
        payload_sha256=hashlib.sha256(encoded).hexdigest(), payload_bytes=len(encoded), payload_gzip_bytes=len(compressed),
        municipalities=len(payload["municipalities"]), native_instants=73, municipality_hours=215*73,
        validation=payload["validation"], quality_flag_counts=payload["quality_flag_counts"],
        capabilities=payload["capabilities"], single_municipality_sizes=town_sizes,
        fields={key:{k:v for k,v in value.items() if k not in ("values", "metadata")} | dict(first_metadata=value["metadata"][0], last_metadata=value["metadata"][-1]) for key,value in snapshot["raw"].items()},
        aging_simulations={str(hours):assess_window(snapshot["run_utc"],snapshot["times_utc"],iso(datetime.fromisoformat(snapshot["run_utc"].replace("Z","+00:00"))+timedelta(hours=hours))) for hours in (18,24,25,31)},
        server_geographic_subset=dict(status="not_tested_requires_authenticated_supported_postprocessing", queue_wait_seconds=None, bytes=None),
        limits=["Single run and local Windows process; not a forecast-accuracy validation, availability SLA or measured cloud bill.",
                "14 fields and native72h; not the same workload as yesterday's 8-field/49-instant range benchmark.",
                "Network seconds exclude local decode pauses but include connection and body waits; no server extraction queue measured.",
                "Peak Windows working set includes native libraries and JSON artifacts; not cloud-container memory sizing.",
                "No public provider licence accepted, cloud job, application cache/provider change, commit, push or deploy.",
                "CAMS pollen, probability, visibility and 5-day app contract not fulfilled. Official OSMER text and official alerts remain independent."])
    write_new(report_path, report)
    print(json.dumps({key:report[key] for key in ("execution_mode","run_utc","metrics","payload_bytes","payload_gzip_bytes","validation","quality_flag_counts")}, ensure_ascii=False, indent=2), flush=True)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run")
    parser.add_argument("--source", type=Path, help="New extracted point snapshot (required for live run)")
    parser.add_argument("--replay", type=Path, help="Offline derivation only, never reported as live acquisition")
    parser.add_argument("--checkpoint-dir", type=Path,
                        help="Live per-field resume directory; default: <source>.checkpoint")
    parser.add_argument("--payload", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    if bool(args.source) == bool(args.replay) or args.replay and (args.run or args.checkpoint_dir):
        parser.error("Choose live --source [--run] OR offline --replay")
    run_outputs(source_path=args.source, payload_path=args.payload, report_path=args.report,
                run=args.run, replay=args.replay, checkpoint_dir=args.checkpoint_dir)


if __name__ == "__main__":
    main()
