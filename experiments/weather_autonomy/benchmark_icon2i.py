"""Bounded, anonymous 48h ICON-2I benchmark, entirely outside the app.

49 hourly instants, eight fields, all municipality points in the local catalog.
Contiguous ranges contain at most eight GRIB messages, not whole files. Each
message is decoded once; nearest-cell indexes are reused only for an identical
GRIB grid section. No credentials, server-side jobs, cloud writes or retries.
"""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timedelta, timezone
import gzip
import hashlib
import json
import math
from pathlib import Path
import re
import time
from urllib.parse import urljoin

from probe_icon2i import BASE, FIELDS, SHORT_NAMES, PublicReader, message_length, relative_humidity_from_dewpoint
from thermal_comfort import calculate_thermal_comfort

CATALOG = Path(__file__).resolve().parents[2] / "backend/app/data/fvg_municipalities.json"
MAX_BYTES = 550 * 1024**2
COLUMNS = ["temperature_c", "dewpoint_c", "relative_humidity_derived_pct", "wind_10m_m_s", "wind_from_degrees", "pressure_msl_hpa", "cloud_cover_pct", "precipitation_previous_hour_mm", "weather_code_raw", "apparent_temperature_shade_c", "heat_index_c", "wind_chill_c", "quality_flags"]


def compact_json(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode("utf-8")


def load_points(path=None):
    """Load model points from ISTAT polygons and IRDAT localities by default.

    ``path`` remains available only for explicit historical-fixture replay; new
    acquisitions must not inherit the legacy Open-Meteo-derived coordinates.
    """
    if path is None:
        from local_pipeline.authoritative_catalog import (
            load_authoritative_catalog,
            verify_catalog_hash,
        )

        catalog = load_authoritative_catalog()
        if not verify_catalog_hash(catalog):
            raise ValueError("Authoritative municipality catalog hash is invalid")
        points = [
            {
                "slug": record["slug"],
                "name": record["name"],
                "province": record["province"],
                "provinceName": record["province_name"],
                "istatCode": record["istat_code"],
                "latitude": record["representative_point"]["latitude"],
                "longitude": record["representative_point"]["longitude"],
                "coordinateSource": record["representative_point"]["method"],
            }
            for record in catalog["municipalities"]
        ]
        digest = catalog["catalog_sha256"]
    else:
        data = Path(path).read_bytes()
        source = json.loads(data)
        points = source["municipalities"]
        digest = hashlib.sha256(data).hexdigest()
    if len(points) != 215 or len({p["slug"] for p in points}) != 215:
        raise ValueError("Expected 215 unique municipality slugs")
    for p in points:
        if not (math.isfinite(p["latitude"]) and math.isfinite(p["longitude"]) and 45 <= p["latitude"] <= 47 and 12 <= p["longitude"] <= 14.5):
            raise ValueError("Missing/out-of-region municipality coordinates")
    return points, digest


def forecast_steps(run_time, now):
    next_hour = now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
    first = int((next_hour - run_time).total_seconds() // 3600)
    # One preceding rain accumulation is needed, including at the first instant.
    if first < 1 or first + 48 > 72:
        raise ValueError("Available run does not cover 49 instants plus preceding rain")
    return list(range(first, first + 49))


def message_span(first_size, size, first_step, last_step):
    if not (0 <= first_step <= last_step <= 72):
        raise ValueError("Invalid hourly range")
    start = 0 if first_step == 0 else first_size + (first_step - 1) * size
    end = first_size + last_step * size - 1
    return start, end


def split_messages(data, expected_count):
    offset = 0
    for _ in range(expected_count):
        length = message_length(data[offset:offset + 16])
        message = data[offset:offset + length]
        if len(message) != length or message[-4:] != b"7777":
            raise ValueError("Truncated/corrupt GRIB message")
        yield message
        offset += length
    if offset != len(data):
        raise ValueError("Unexpected extra bytes/messages in range")


class TimedReader(PublicReader):
    def __init__(self):
        super().__init__(MAX_BYTES)
        self.calls = []

    def get(self, url, start=None, end=None):
        before = self.bytes_read
        started = time.perf_counter()
        success = False
        try:
            result = super().get(url, start, end)
            success = True
            return result
        finally:
            self.calls.append({"url": url, "range": [start, end] if start is not None else None, "bytes": self.bytes_read - before, "seconds": time.perf_counter() - started, "success": success})


class PointDecoder:
    def __init__(self, points):
        import eccodes

        self.ec = eccodes
        self.points = points
        self.grid_hash = None
        self.grid_points = None
        self.indexes = None
        self.seen = set()
        self.metadata_seconds = 0.0
        self.mapping_seconds = 0.0
        self.values_seconds = 0.0
        self.total_seconds = 0.0
        self.mapping_builds = 0

    def decode(self, data, field, run, step):
        identity = (field, run, step)
        if identity in self.seen:
            raise ValueError("Duplicate GRIB decode requested")
        ec = self.ec
        started = time.perf_counter()
        handle = ec.codes_new_from_message(data)
        try:
            ec.codes_set(handle, "stepUnits", 1)
            keys = ("shortName", "paramId", "units", "typeOfLevel", "level", "dataDate", "dataTime", "validityDate", "validityTime", "startStep", "endStep", "stepUnits", "stepType", "gridType", "numberOfPoints", "Ni", "Nj", "uvRelativeToGrid", "md5GridSection")
            meta = {key: ec.codes_get(handle, key) for key in keys}
            validate_metadata(meta, field, run, step)
            self.metadata_seconds += time.perf_counter() - started
            mapping_started = time.perf_counter()
            if self.grid_hash is None:
                nearest = ec.codes_grib_find_nearest_multiple(handle, False, [p["latitude"] for p in self.points], [p["longitude"] for p in self.points])
                if len(nearest) != len(self.points):
                    raise ValueError("Incomplete nearest-cell mapping")
                if any(not math.isfinite(p["distance"]) or p["distance"] > 5 or not 0 <= p["index"] < meta["numberOfPoints"] for p in nearest):
                    raise ValueError("Invalid cell index or excessive grid distance")
                self.grid_points = [{k: p[k] for k in ("lat", "lon", "distance", "index")} for p in nearest]
                self.indexes = [p["index"] for p in nearest]
                self.grid_hash = meta["md5GridSection"]
                self.mapping_builds += 1
                # The mapping call already extracts the first message's values.
                values = [float(p["value"]) for p in nearest]
            else:
                if meta["md5GridSection"] != self.grid_hash:
                    raise ValueError("Grid changed: refusing to reuse cell indexes")
                values = None
            self.mapping_seconds += time.perf_counter() - mapping_started
            values_started = time.perf_counter()
            if values is None:
                values = [float(v) for v in ec.codes_get_elements(handle, "values", self.indexes)]
            missing = ec.codes_get(handle, "missingValue")
            if len(values) != len(self.points) or any(not math.isfinite(v) or v == missing for v in values):
                raise ValueError("Missing/nonfinite municipality data")
            self.values_seconds += time.perf_counter() - values_started
            self.seen.add(identity)
            return values, meta
        finally:
            ec.codes_release(handle)
            self.total_seconds += time.perf_counter() - started


def validate_metadata(meta, field, run, step):
    _, level_type, level, units = FIELDS[field]
    if meta["shortName"] != SHORT_NAMES[field] or meta["typeOfLevel"] != level_type or meta["level"] != level:
        raise ValueError(f"Parameter/level mismatch: {field}")
    if units and meta["units"] != units:
        raise ValueError(f"Unit mismatch: {field}")
    if f"{meta['dataDate']}{meta['dataTime']:04d}" != run + "00" or meta["endStep"] != step or str(meta["stepUnits"]) != "1":
        raise ValueError("Run/lead mismatch")
    expected_time = datetime.strptime(run, "%Y%m%d%H") + timedelta(hours=step)
    if f"{meta['validityDate']}{meta['validityTime']:04d}" != expected_time.strftime("%Y%m%d%H%M"):
        raise ValueError("Validity timestamp mismatch")
    if field == "TOT_PREC":
        if meta["stepType"] != "accum" or meta["startStep"] != 0:
            raise ValueError("Rain is not accumulated since the same run")
    elif meta["stepType"] != "instant" or meta["startStep"] != step:
        raise ValueError("Expected instantaneous variable")
    if meta["gridType"] != "regular_ll" or meta["Ni"] <= 0 or meta["Nj"] <= 0 or meta["Ni"] * meta["Nj"] != meta["numberOfPoints"]:
        raise ValueError("Unexpected grid representation")
    if field in ("U_10M", "V_10M") and meta["uvRelativeToGrid"] != 0:
        raise ValueError("Wind components require grid rotation")


def derive_row(raw, previous_rain):
    flags = []
    t, td = raw["T_2M"] - 273.15, raw["TD_2M"] - 273.15
    wind = math.hypot(raw["U_10M"], raw["V_10M"])
    direction = (270 - math.degrees(math.atan2(raw["V_10M"], raw["U_10M"]))) % 360 if wind > 0 else None
    rh = at = hi = wc = None
    try:
        rh = relative_humidity_from_dewpoint(t, td)
    except ValueError:
        flags.append("invalid_T_Td_for_RH_no_clipping")
    if rh is not None:
        thermal = calculate_thermal_comfort(temperature_c=t, relative_humidity_pct=rh, wind_10m_m_s=wind)
        at = thermal.apparent_temperature.value_c
        hi = thermal.heat_index.value_c
        wc = thermal.wind_chill.value_c
    rain = raw["TOT_PREC"] - previous_rain
    if raw["TOT_PREC"] < 0 or previous_rain < 0 or rain < 0:
        rain = None
        flags.append("negative_rain_accumulation_or_increment_no_clipping")
    cloud = raw["CLCT"]
    if not 0 <= cloud <= 100:
        cloud = None
        flags.append("invalid_cloud_cover")
    code = raw["WW"]
    if not 0 <= code <= 99 or code != int(code):
        flags.append("unverified_noninteger_or_out_of_range_WW")
    rounded_direction = round(direction, 3) % 360 if direction is not None else None
    values = [t, td, rh, wind, rounded_direction, raw["PMSL"] / 100, cloud, rain, code, at, hi, wc]
    return [round(v, 3) if v is not None else None for v in values] + [flags]


def run_benchmark(run=None):
    from process_memory import process_memory_bytes

    wall_started = time.perf_counter()
    initial_memory = process_memory_bytes()
    points, catalog_hash = load_points()
    reader = TimedReader()
    decoder = PointDecoder(points)
    now = datetime.now(timezone.utc)
    runs = sorted(link.rstrip("/") for link in reader.links(BASE) if re.fullmatch(r"\d{10}/", link))
    if not runs or run is not None and run not in runs:
        raise ValueError("Requested public run is unavailable")
    run = run or runs[-1]
    run_time = datetime.strptime(run, "%Y%m%d%H").replace(tzinfo=timezone.utc)
    steps = forecast_steps(run_time, now)
    print(f"Run {run}, steps {steps[0]}..{steps[-1]}, {len(points)} municipalities; budget {MAX_BYTES} bytes", flush=True)
    fields, raw_values = {}, {}
    for field, (suffix, _, _, _) in FIELDS.items():
        directory = f"{BASE}{run}/{field}/"
        files = [link for link in reader.links(directory) if link.endswith(f"_{suffix}.grib")]
        if len(files) != 1:
            raise ValueError(f"Ambiguous/missing public file: {field}")
        url = urljoin(directory, files[0])
        header, total = reader.get(url, 0, 15)
        first_size = size = message_length(header)
        if total != 73 * size:
            header, second_total = reader.get(url, size, size + 15)
            size = message_length(header)
            if total != second_total or total != first_size + 72 * size:
                raise ValueError("Unverified hourly packing; no full-file fallback")
        field_steps = ([steps[0] - 1] + steps) if field == "TOT_PREC" else steps
        raw_values[field] = {}
        digest = hashlib.sha256()
        bytes_before, calls_before = reader.bytes_read, len(reader.calls)
        decode_before = decoder.total_seconds
        first_meta = last_meta = None
        for batch_index in range(0, len(field_steps), 8):
            batch = field_steps[batch_index:batch_index + 8]
            start, end = message_span(first_size, size, batch[0], batch[-1])
            data, current_total = reader.get(url, start, end)
            if current_total != total:
                raise ValueError("Public file size changed during benchmark")
            digest.update(data)
            for step, message in zip(batch, split_messages(data, len(batch)), strict=True):
                values, meta = decoder.decode(message, field, run, step)
                raw_values[field][step] = values
                first_meta = first_meta or meta
                last_meta = meta
            del data, message
        fields[field] = {"url": url, "whole_file_bytes": total, "selected_bytes": reader.bytes_read - bytes_before, "selected_grib_sha256": digest.hexdigest(), "message_count": len(field_steps), "steps": field_steps, "range_requests": len(reader.calls) - calls_before, "download_seconds": sum(c["seconds"] for c in reader.calls[calls_before:]), "decode_extract_seconds": decoder.total_seconds - decode_before, "first_metadata": first_meta, "last_metadata": last_meta}
        print(f"{field}: {len(field_steps)} messages, {fields[field]['selected_bytes'] / 1e6:.2f} MB, network {fields[field]['download_seconds']:.2f}s, decode/extract {fields[field]['decode_extract_seconds']:.2f}s", flush=True)
    derive_started = time.perf_counter()
    times = [(run_time + timedelta(hours=step)).isoformat() for step in steps]
    rows, issues = [], Counter()
    for index, point in enumerate(points):
        series = []
        for step in steps:
            raw = {field: raw_values[field][step][index] for field in FIELDS}
            row = derive_row(raw, raw_values["TOT_PREC"][step - 1][index])
            issues.update(row[-1])
            series.append(row)
        rows.append({"id": point["slug"], "name": point["name"], "requested_latitude": point["latitude"], "requested_longitude": point["longitude"], "grid_point": decoder.grid_points[index], "hourly": series})
    derive_seconds = time.perf_counter() - derive_started
    payload = {"status": "experiment_not_production", "provider": "Agenzia ItaliaMeteo / Arpae Emilia-Romagna Idro-Meteo-Clima", "license": "CC BY 4.0", "license_url": "https://creativecommons.org/licenses/by/4.0/", "run_utc": run_time.isoformat(), "times_utc": times, "columns": COLUMNS, "processing": {"location": "Nearest model grid point; no altitude/coast correction or interpolation", "rh": "Magnus over-water approximation from T2m/Td2m, not native ICON RH2m", "apparent_temperature": "BOM/Steadman shade, 10m wind; no switch/blend", "heat_index_wind_chill": "Separate comparison indices; null outside conservative applicability domain or for invalid RH; see quality_flags", "precipitation": "Difference of same-run accumulations over (timestamp-1h,timestamp]; null on negative differences; no clipping", "weather_code": "Raw WW, not validated as app icon mapping", "coordinates": "Local catalog originally geocoded with Open-Meteo; no live geocoding requests", "precision": "Values rounded to 0.001 output units; not an accuracy claim"}, "municipalities": rows}
    json_started = time.perf_counter()
    encoded = compact_json(payload)
    json_seconds = time.perf_counter() - json_started
    gzip_started = time.perf_counter()
    compressed = gzip.compress(encoded, compresslevel=6, mtime=0)
    gzip_seconds = time.perf_counter() - gzip_started
    per_town_sizes = []
    for row in rows:
        single = {k: v for k, v in payload.items() if k != "municipalities"}
        single["municipalities"] = [row]
        town_json = compact_json(single)
        per_town_sizes.append({"id": row["id"], "json_bytes": len(town_json), "gzip_bytes": len(gzip.compress(town_json, compresslevel=6, mtime=0))})
    report = {"status": "isolated_hourly_benchmark_not_production", "accessed_at_utc": now.isoformat(), "run": run, "first_valid_at_utc": times[0], "last_valid_at_utc": times[-1], "hourly_instants": len(steps), "municipality_count": len(points), "municipality_hours": len(points) * len(steps), "catalog_sha256": catalog_hash, "fields": fields, "downloaded_bytes_including_metadata": reader.bytes_read, "http_get_requests": reader.requests, "network_seconds_including_metadata": sum(c["seconds"] for c in reader.calls), "decode_extract_seconds": decoder.total_seconds, "metadata_validation_seconds": decoder.metadata_seconds, "nearest_mapping_seconds": decoder.mapping_seconds, "values_extract_seconds": decoder.values_seconds, "derived_weather_and_thermal_seconds": derive_seconds, "json_serialize_seconds": json_seconds, "gzip_seconds": gzip_seconds, "elapsed_seconds": time.perf_counter() - wall_started, "memory_initial": initial_memory, "memory_final": process_memory_bytes(), "json_bytes_all_municipalities": len(encoded), "gzip_bytes_all_municipalities": len(compressed), "json_sha256": hashlib.sha256(encoded).hexdigest(), "single_municipality_sizes": per_town_sizes, "grid_hash": decoder.grid_hash, "grid_mapping_builds": decoder.mapping_builds, "unique_decoded_messages": len(decoder.seen), "duplicate_decoded_messages": 0, "quality_flag_counts": dict(issues), "server_geographic_subset": {"status": "not_measured_requires_authenticated_service_and_supported_postprocessor", "queue_wait_seconds": None, "processing_seconds": None, "bytes": None}, "limits": ["One run and one local Windows machine: not meteorological accuracy validation, reliability statistics, cloud sizing or monetary cost.", "Eight selected fields; no gusts, precipitation probability, elevation/coastal correction or production icon mapping.", "No server-side crop performed; each selected message still contains the national domain.", "Network timing includes HTTP connection/response/body, not a measured extraction queue.", "Process peak working set is OS-reported for the entire process including native libraries, not a Python-only allocation counter.", "No production integration, Firebase/Cloudflare write, scheduler, commit, push or deployment."]}
    return report, payload


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", help="UTC model run YYYYMMDDHH; default latest public")
    parser.add_argument("--report", type=Path, required=True, help="New JSON report; never overwrite")
    parser.add_argument("--payload", type=Path, required=True, help="New compact full JSON; never overwrite")
    args = parser.parse_args()
    if args.report.resolve() == args.payload.resolve() or any(p.exists() or not p.parent.is_dir() for p in (args.report, args.payload)):
        parser.error("Output files must be distinct, new, in existing directories (checked before download)")
    report, payload = run_benchmark(args.run)
    with args.payload.open("xb") as destination:
        destination.write(compact_json(payload))
    with args.report.open("x", encoding="utf-8") as destination:
        json.dump(report, destination, ensure_ascii=False, indent=2, allow_nan=False)
        destination.write("\n")
    summary = {k: v for k, v in report.items() if k not in ("fields", "single_municipality_sizes")}
    print(json.dumps(summary, ensure_ascii=False, indent=2, allow_nan=False), flush=True)
    print(f"Report: {args.report}\nPayload: {args.payload}", flush=True)


if __name__ == "__main__":
    main()
