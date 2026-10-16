"""Offline CAMS regional extraction: one decode per field, shared native cells.

No network, credentials, production integration or hidden model interpolation.
The downloaded GRIB remains the raw source of truth. Conversion provenance is
global per variable; anomalous point/lead values get sparse explicit flags.
"""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timedelta, timezone
import gzip
import hashlib
import math
from pathlib import Path
import statistics
import time
import json

from benchmark_icon2i import load_points
from cams_request_plan import PublicMetadataError, load_verified_request_plan, request_sha256
from decode_cams import (
    DATASET, DATA_SOURCE, EXPECTED_VARIABLES, IDENTITY_SOURCE, NEW_COMPONENT_EVIDENCE,
    compact_json, convert_value, decoder_plan_options, grib_messages, identify_variable,
    iso, read_metadata, run_time, verify_metadata,
)
from process_memory import process_memory_bytes

AREA = (46.7, 12.2, 45.5, 14.0)
TIME_KEYS = {"validityDate", "validityTime", "startStep", "endStep"}


def finite(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


class RegionDecoder:
    def __init__(self, points, *, date, ec=None, area=AREA,
                 variables=EXPECTED_VARIABLES, leads=tuple(range(97))):
        if ec is None:
            import eccodes as ec
        self.ec, self.points, self.date, self.area = ec, list(points), date, tuple(area)
        self.variables, self.leads = tuple(variables), tuple(leads)
        run_time(date)
        if not self.variables or len(set(self.variables)) != len(self.variables) or not set(self.variables) <= set(EXPECTED_VARIABLES):
            raise ValueError("Invalid variable selection")
        if not self.leads or tuple(sorted(set(self.leads))) != self.leads or any(isinstance(v, bool) or not isinstance(v, int) or not 0 <= v <= 96 for v in self.leads):
            raise ValueError("Leads must be sorted, unique hourly integers 0..96")
        if len(self.area) != 4 or not all(finite(v) for v in self.area):
            raise ValueError("Invalid crop")
        north, west, south, east = self.area
        if not 45 <= south < north <= 47.2 or not 11.8 <= west < east <= 14.5:
            raise ValueError("Crop must stay within the FVG pilot")
        if not self.points or len(self.points) > 215 or len({p["slug"] for p in self.points}) != len(self.points):
            raise ValueError("Expected 1..215 unique municipality IDs")
        for point in self.points:
            if not isinstance(point["slug"], str) or not point["slug"] or not isinstance(point["name"], str):
                raise ValueError("Invalid municipality identity")
            if not all(finite(point[k]) for k in ("latitude", "longitude")) or not south <= point["latitude"] <= north or not west <= point["longitude"] <= east:
                raise ValueError("Municipality outside requested crop")
        self.seen, self.metadata, self.cells, self.municipalities = set(), {}, {}, []
        self.grid_hash, self.indexes = None, []
        self.seconds = Counter()
        self.mapping_builds = 0

    def _map(self, handle, meta):
        nearest = self.ec.codes_grib_find_nearest_multiple(handle, False,
                    [p["latitude"] for p in self.points], [p["longitude"] for p in self.points])
        if len(nearest) != len(self.points):
            raise ValueError("Incomplete municipality mapping")
        raw_by_index = {}
        for point, cell in zip(self.points, nearest):
            index = cell["index"]
            if isinstance(index, bool) or not isinstance(index, int) or not 0 <= index < meta["numberOfPoints"]:
                raise ValueError("Invalid nearest-cell index")
            if not all(finite(cell[k]) for k in ("lat", "lon", "distance")) or not 0 <= cell["distance"] <= 10:
                raise ValueError("Invalid/excessive nearest-cell distance")
            row, col = divmod(index, meta["Ni"])
            lat = meta["latitudeOfFirstGridPointInDegrees"] + row * (0.1 if meta["jScansPositively"] else -0.1)
            lon = meta["longitudeOfFirstGridPointInDegrees"] + col * (-0.1 if meta["iScansNegatively"] else 0.1)
            if abs(lat - cell["lat"]) > 1e-6 or abs(lon - cell["lon"]) > 1e-6:
                raise ValueError("Nearest index/coordinate mismatch")
            if index in raw_by_index:
                prior = raw_by_index[index]
                if finite(prior) and finite(cell["value"]) and prior != cell["value"]:
                    raise ValueError("Shared cell returned inconsistent values")
            else:
                raw_by_index[index] = cell["value"]
                self.cells[str(index)] = dict(id=str(index), lat=cell["lat"], lon=cell["lon"], grid_index=index,
                                              values={}, raw_values={}, quality_flags={})
            self.municipalities.append(dict(id=point["slug"], name=point["name"], latitude=point["latitude"],
                                           longitude=point["longitude"], province=point.get("province"),
                                           cell_id=str(index), distance_km=cell["distance"]))
        self.grid_hash, self.indexes = meta["md5GridSection"], sorted(raw_by_index)
        self.mapping_builds += 1
        return [raw_by_index[index] for index in self.indexes]

    def decode(self, message):
        ec, started = self.ec, time.perf_counter()
        handle = ec.codes_new_from_message(message)
        try:
            meta = read_metadata(ec, handle)
            lead = verify_metadata(meta, self.date, self.area)
            variable = identify_variable(meta)
            if variable not in self.variables or lead not in self.leads:
                raise ValueError("Unexpected CAMS variable/lead")
            key = (variable, lead)
            if key in self.seen:
                raise ValueError("Duplicate CAMS variable/lead")
            if variable in self.metadata:
                previous = self.metadata[variable]
                if any(meta[k] != previous[k] for k in meta if k not in TIME_KEYS):
                    raise ValueError("Variable metadata changed across leads")
            self.metadata.setdefault(variable, meta)
            self.seconds["metadata_validation"] += time.perf_counter() - started
            tick = time.perf_counter()
            if self.grid_hash is None:
                raw_values = self._map(handle, meta)
            else:
                if meta["md5GridSection"] != self.grid_hash or self.indexes[-1] >= meta["numberOfPoints"]:
                    raise ValueError("CAMS grid changed; cannot reuse municipality indexes")
                raw_values = None
            self.seconds["nearest_mapping"] += time.perf_counter() - tick
            tick = time.perf_counter()
            if raw_values is None:
                raw_values = ec.codes_get_elements(handle, "values", self.indexes)
            if len(raw_values) != len(self.indexes):
                raise ValueError("Incomplete unique-cell extraction")
            missing = ec.codes_get(handle, "missingValue")
            self.seconds["values_extract"] += time.perf_counter() - tick
            tick = time.perf_counter()
            position = self.leads.index(lead)
            provenance = convert_value(0, meta)["quality_flags"]
            for index, raw in zip(self.indexes, raw_values):
                raw = raw if raw is None or isinstance(raw, (int, float)) else float(raw)
                row = convert_value(raw, meta, missing)
                cell = self.cells[str(index)]
                cell["values"].setdefault(variable, [None] * len(self.leads))[position] = row["value"]
                cell["raw_values"].setdefault(variable, [None] * len(self.leads))[position] = row["raw_value"]
                flags = [flag for flag in row["quality_flags"] if flag not in provenance]
                if flags:
                    cell["quality_flags"].setdefault(variable, {})[str(position)] = flags
            self.seconds["unit_conversion_and_packing"] += time.perf_counter() - tick
            self.seen.add(key)
        finally:
            ec.codes_release(handle)
            self.seconds["decode_extract_total"] += time.perf_counter() - started

    def finish(self, *, catalog_sha256=None):
        expected = {(variable, lead) for variable in self.variables for lead in self.leads}
        if self.seen != expected:
            raise ValueError(f"Incomplete CAMS matrix: {len(self.seen)}/{len(expected)} unique fields")
        variables = []
        for variable in self.variables:
            meta = self.metadata[variable]
            conversion = convert_value(0, meta)
            info = dict(id=variable, metadata=meta,
                        **{k: conversion[k] for k in ("units", "source_units", "raw_units", "conversion_factor", "quality_flags")})
            info["identity_evidence"] = (dict(source="ECMWF ecCodes 2.48.0 bundled WMO table grib2/tables/21/4.230.table",
                                               constituent_label=NEW_COMPONENT_EVIDENCE[variable],
                                               scope="Chemical identity joined to this ADS regional dataset's PM2.5 catalogue selection")
                                         if variable in NEW_COMPONENT_EVIDENCE else dict(source=IDENTITY_SOURCE))
            variables.append(info)
        return dict(schema_version=2, kind="cams_region_point_extraction", status="isolated_offline_not_production",
                    dataset=DATASET, model="ensemble_median", run_utc=iso(run_time(self.date)),
                    generated_at_utc=iso(datetime.now(timezone.utc)), requested_level=0, requested_area=list(self.area),
                    variables=variables, times_utc=[iso(run_time(self.date) + timedelta(hours=lead)) for lead in self.leads],
                    cells=[self.cells[str(index)] for index in self.indexes], municipalities=self.municipalities,
                    grid_hash=self.grid_hash, catalog_sha256=catalog_sha256, native_resolution_degrees=0.1,
                    sources=dict(identification=IDENTITY_SOURCE, units_and_scope=DATA_SOURCE,
                                 constituent_table="ECMWF ecCodes 2.48.0 bundled grib2/tables/21/4.230.table",
                                 dataset=f"https://ads.atmosphere.copernicus.eu/datasets/{DATASET}", doi="10.24381/a4005cee"),
                    attribution="Copernicus Atmosphere Monitoring Service (CAMS), European regional ensemble providers, Atmosphere Data Store (ADS)",
                    quality_rules=dict(variable_flags="Apply to every cell/lead for that variable",
                                       cell_flags="Sparse additional flags indexed by variable and position in times_utc",
                                       missing="Null is unavailable, never a fabricated zero; inspect sparse flags",
                                       negative="Raw negative retained, converted value null, explicit flag"),
                    limitations=["Forecast grid-cell estimates, not municipality-specific observations or clinical advice.",
                                 "Nearby municipalities may share a native 0.1-degree cell; no finer resolution is invented.",
                                 "The surface selection represents model lowest layers, not an exact sensor at zero metres.",
                                 "No spatial interpolation, bias correction, AQI or threshold classifications.",
                                 "Research/experimental provider status is separate from numeric and structural checks."])


def analyze_payload(payload):
    by_cell = {}
    for municipality in payload["municipalities"]:
        by_cell.setdefault(municipality["cell_id"], []).append(municipality["id"])
    expected = len(payload["variables"]) * len(payload["times_utc"])
    flags, expanded_flags = Counter(), Counter()
    summaries = []
    for variable in payload["variables"]:
        vid, extrema, counts = variable["id"], {"minimum": None, "maximum": None}, Counter()
        for cell in payload["cells"]:
            rows = cell["values"][vid]
            if len(rows) != len(payload["times_utc"]) or len(cell["raw_values"][vid]) != len(rows):
                raise ValueError("Malformed shared-cell series")
            for position, value in enumerate(rows):
                counts["missing_or_invalid" if value is None else "numeric"] += 1
                if value == 0:
                    counts["exact_zero"] += 1
                for flag in cell["quality_flags"].get(vid, {}).get(str(position), []):
                    flags[flag] += 1
                    expanded_flags[flag] += len(by_cell[cell["id"]])
                if value is None:
                    continue
                for which in extrema:
                    old = extrema[which]
                    if old is None or (value < old["value"] if which == "minimum" else value > old["value"]):
                        extrema[which] = dict(value=value, cell_id=cell["id"], municipality_ids=by_cell[cell["id"]],
                                              valid_at_utc=payload["times_utc"][position])
        summaries.append(dict(id=vid, units=variable["units"], counts_unique_cells=dict(counts), **extrema))
    inconsistencies = []
    count, expanded_count = 0, 0
    if {"particulate_matter_2.5um", "particulate_matter_10um"} <= {v["id"] for v in payload["variables"]}:
        for cell in payload["cells"]:
            for position, (fine, coarse) in enumerate(zip(cell["values"]["particulate_matter_2.5um"], cell["values"]["particulate_matter_10um"])):
                if fine is not None and coarse is not None and fine > coarse:
                    count += 1
                    expanded_count += len(by_cell[cell["id"]])
                    if len(inconsistencies) < 25:
                        inconsistencies.append(dict(cell_id=cell["id"], municipality_ids=by_cell[cell["id"]],
                                                    valid_at_utc=payload["times_utc"][position], pm2_5=fine, pm10=coarse))
    distances = [p["distance_km"] for p in payload["municipalities"]]
    return dict(municipalities=len(payload["municipalities"]), variables=len(payload["variables"]), hourly_instants=len(payload["times_utc"]),
                unique_fields=expected, unique_cells=len(payload["cells"]), unique_cell_values=len(payload["cells"]) * expected,
                municipality_values=len(payload["municipalities"]) * expected,
                shared_cells=[dict(cell_id=cell, municipality_ids=ids) for cell, ids in by_cell.items() if len(ids) > 1],
                minimum_distance_km=min(distances), maximum_distance_km=max(distances),
                anomaly_counts_unique_cells=dict(flags), anomaly_counts_municipalities=dict(expanded_flags),
                variable_summary=summaries,
                pm2_5_greater_than_pm10=dict(unique_cell_hours=count, municipality_hours=expanded_count, first_25=inconsistencies,
                                           action="Diagnostic only; never corrected. Investigate member availability, definitions and packing; median alone does not explain an order violation for identical member sets"),
                daily_province_extremes=daily_province_extremes(payload))


def daily_province_extremes(payload):
    """UTC-day summaries of values, never exposure/health risk classifications."""
    groups, members = {}, {}
    day_instants = Counter(t[:10] for t in payload["times_utc"])
    for municipality in payload["municipalities"]:
        members.setdefault(municipality["cell_id"], {}).setdefault(municipality.get("province"), []).append(municipality["id"])
    for cell in payload["cells"]:
        for variable in payload["variables"]:
            vid = variable["id"]
            for position, value in enumerate(cell["values"][vid]):
                timestamp = payload["times_utc"][position]
                for province, ids in members[cell["id"]].items():
                    key = (province, vid, timestamp[:10])
                    group = groups.setdefault(key, dict(province=province, variable=vid, units=variable["units"], utc_date=timestamp[:10],
                                                        forecast_instants_in_day=day_instants[timestamp[:10]],
                                                        complete_utc_day=day_instants[timestamp[:10]] == 24,
                                                        numeric_cell_hours=0, missing_or_invalid_cell_hours=0, minimum=None, maximum=None))
                    group["missing_or_invalid_cell_hours" if value is None else "numeric_cell_hours"] += 1
                    if value is None:
                        continue
                    for which in ("minimum", "maximum"):
                        prior = group[which]
                        if prior is None or (value < prior["value"] if which == "minimum" else value > prior["value"]):
                            group[which] = dict(value=value, cell_id=cell["id"], municipality_ids=ids, valid_at_utc=timestamp)
    return sorted(groups.values(), key=lambda row: (row["province"] or "", row["variable"], row["utc_date"]))


def compare_pordenone(payload, previous):
    """Compare actual cell and timestamps, never cropped-file indexes or hashes."""
    if previous.get("schema_version") != 1 or previous.get("dataset") != DATASET or previous.get("run_utc") != payload["run_utc"]:
        raise ValueError("Pordenone comparison has an incompatible dataset/schema/run")
    municipality = next(p for p in payload["municipalities"] if p["id"] == "pordenone")
    cell = next(c for c in payload["cells"] if c["id"] == municipality["cell_id"])
    old = previous["grid_point"]
    if abs(old["lat"] - cell["lat"]) > 1e-6 or abs(old["lon"] - cell["lon"]) > 1e-6:
        return dict(status="not_comparable_different_native_cell", old_grid_point=old, new_grid_point={k: cell[k] for k in ("lat", "lon", "grid_index")})
    old_variables = {v["id"]: v for v in previous["variables"]}
    if set(old_variables) != {v["id"] for v in payload["variables"]}:
        raise ValueError("Pordenone comparison variable coverage differs")
    changed, summaries = 0, []
    for variable in payload["variables"]:
        vid, differences, raw_differences = variable["id"], [], []
        prior = old_variables[vid]["hourly"]
        if [r["valid_at_utc"] for r in prior] != payload["times_utc"]:
            raise ValueError("Pordenone comparison time coverage differs")
        for position, row in enumerate(prior):
            if row["units"] != variable["units"] or row["source_units"] != variable["source_units"]:
                raise ValueError("Pordenone comparison units differ")
            for key, series, target in (("value", "values", differences), ("raw_value", "raw_values", raw_differences)):
                a, b = row[key], cell[series][vid][position]
                if (a is None) != (b is None):
                    raise ValueError("Pordenone comparison availability changed")
                if a is not None:
                    target.append(abs(a - b))
            if row["value"] != cell["values"][vid][position]:
                changed += 1
        summaries.append(dict(id=vid, units=variable["units"], maximum_absolute_difference=max(differences, default=None),
                              maximum_raw_difference=max(raw_differences, default=None)))
    return dict(status="same_run_cell_and_times_compared", exact_equal_converted_values=changed == 0,
                changed_converted_values=changed, compared_fields=len(payload["variables"]) * len(payload["times_utc"]),
                previous_input_sha256=previous.get("input_sha256"), variable_differences=summaries,
                caveat="Different crop packing can alter numeric precision; this is not independent accuracy validation")


def run_file(path, *, request_plan, request_plan_sha256, previous_path=None):
    wall = time.perf_counter()
    initial_memory = process_memory_bytes()
    points, catalog_hash = load_points()
    options = decoder_plan_options(request_plan, request_plan_sha256, AREA)
    decoder = RegionDecoder(
        points,
        date=options["date"],
        area=options["area"],
        variables=options["expected_variables"],
        leads=options["expected_leads"],
    )
    digest = hashlib.sha256()
    for message in grib_messages(path):
        digest.update(message)
        decoder.decode(message)
    tick = time.perf_counter()
    payload = decoder.finish(catalog_sha256=catalog_hash)
    payload["sources"]["grib"] = dict(filename=Path(path).name, bytes=Path(path).stat().st_size, sha256=digest.hexdigest())
    request = request_plan["request_groups"][0]["request"]
    payload["request_plan_sha256"] = request_plan_sha256
    payload["request_sha256"] = request_sha256(request)
    payload["sources"]["request_plan"] = dict(
        sha256=request_plan_sha256,
        run_date=request_plan["run_date"],
        request_sha256=payload["request_sha256"],
        metadata_documents=request_plan["metadata_evidence"]["documents"],
    )
    analysis = analyze_payload(payload)
    comparison = None
    if previous_path:
        previous_path = Path(previous_path)
        if not previous_path.is_file() or previous_path.stat().st_size > 2 * 1024**2:
            raise ValueError("Expected existing bounded Pordenone JSON")
        comparison = compare_pordenone(payload, json.loads(previous_path.read_bytes()))
    analysis_seconds = time.perf_counter() - tick
    tick = time.perf_counter()
    encoded = compact_json(payload)
    json_seconds = time.perf_counter() - tick
    tick = time.perf_counter()
    compressed = gzip.compress(encoded, mtime=0)
    gzip_seconds = time.perf_counter() - tick
    report = dict(schema_version=1, status="offline_regional_decode_measurement_not_acquisition", analysis=analysis,
                  input=payload["sources"]["grib"], catalog_sha256=catalog_hash,
                  run_date=request_plan["run_date"], request_plan_sha256=request_plan_sha256,
                  request_sha256=payload["request_sha256"],
                  metrics=dict(decoder.seconds, grid_mapping_builds=decoder.mapping_builds, duplicate_decoded_fields=0,
                               analysis_seconds=analysis_seconds, json_serialize_seconds=json_seconds, gzip_seconds=gzip_seconds,
                               elapsed_seconds=time.perf_counter()-wall, memory_initial=initial_memory, memory_final=process_memory_bytes()),
                  payload_bytes=len(encoded), payload_gzip_bytes=len(compressed), payload_sha256=hashlib.sha256(encoded).hexdigest(),
                  payload_gzip_sha256=hashlib.sha256(compressed).hexdigest(), pordenone_comparison=comparison,
                  limitations=["Queue, remote processing and download are separate acquisition measurements.",
                               "Memory is the Windows process-lifetime peak resident working set, including native libraries.",
                               "One forecast run is not model accuracy validation, reliability statistics or cloud cost measurement."])
    return encoded, compact_json(report)


def transport_projection(payload, *, municipality_id=None, audit=True):
    """Proposed transport only; keep original float values without rounding."""
    if payload.get("schema_version") != 2 or payload.get("kind") != "cams_region_point_extraction":
        raise ValueError("Expected the verified regional extraction schema")
    municipalities, cells = payload["municipalities"], payload["cells"]
    if municipality_id is not None:
        municipalities = [p for p in municipalities if p["id"] == municipality_id]
        if len(municipalities) != 1:
            raise ValueError("Unknown/duplicate municipality")
        cells = [c for c in cells if c["id"] == municipalities[0]["cell_id"]]
        if len(cells) != 1:
            raise ValueError("Unknown/duplicate selected cell")
    if audit:
        return dict(payload, municipalities=municipalities, cells=cells)
    # Physical variable identity and conversion provenance are retained, while
    # binary-layout/run repetition remains in the archived GRIB/audit JSON.
    variable_keys = ("id", "units", "source_units", "raw_units", "conversion_factor", "quality_flags", "identity_evidence")
    variables = []
    for variable in payload["variables"]:
        compact = {key: variable[key] for key in variable_keys}
        compact["source_identity"] = {key: variable["metadata"][key] for key in
                                      ("centre", "subCentre", "discipline", "parameterCategory", "parameterNumber", "constituentType", "typeOfLevel", "level")}
        variables.append(compact)
    projected = dict(payload, kind="cams_display_transport_candidate", status="offline_projection_not_http_or_production",
                     variables=variables, municipalities=municipalities,
                     cells=[{key: cell[key] for key in ("id", "lat", "lon", "grid_index", "values", "quality_flags")} for cell in cells])
    projected["transport_scope"] = "Unrounded converted values only; raw source values remain in the separately retained GRIB/audit JSON identified by source hash"
    return projected


def profile_existing(path):
    path = Path(path)
    if not path.is_file() or not 1 <= path.stat().st_size <= 64 * 1024**2:
        raise ValueError("Expected an existing regional payload of at most 64 MiB")
    started = time.perf_counter()
    raw = path.read_bytes()
    payload = json.loads(raw)
    parse_seconds = time.perf_counter() - started
    if len(payload["municipalities"]) != 215 or len(payload["variables"]) != 28 or len(payload["times_utc"]) != 97:
        raise ValueError("This profile requires the complete 215 by 28 by 97 extraction")
    results = {}
    tick = time.perf_counter()
    for name, audit in (("full_audit_raw_and_converted", True), ("display_unrounded_converted_only", False)):
        whole = compact_json(transport_projection(payload, audit=audit))
        compressed = gzip.compress(whole, mtime=0)
        per_town = []
        for municipality in payload["municipalities"]:
            encoded = compact_json(transport_projection(payload, municipality_id=municipality["id"], audit=audit))
            zipped = gzip.compress(encoded, mtime=0)
            per_town.append(dict(id=municipality["id"], cell_id=municipality["cell_id"],
                                 json_bytes=len(encoded), gzip_bytes=len(zipped)))
        summaries = {}
        for key in ("json_bytes", "gzip_bytes"):
            values = [row[key] for row in per_town]
            minimum, maximum = min(values), max(values)
            summaries[key] = dict(minimum=minimum, median=statistics.median(values), maximum=maximum,
                                  minimum_municipalities=[row["id"] for row in per_town if row[key] == minimum],
                                  maximum_municipalities=[row["id"] for row in per_town if row[key] == maximum])
        results[name] = dict(all_region_json_bytes=len(whole), all_region_gzip_bytes=len(compressed),
                             all_region_json_sha256=hashlib.sha256(whole).hexdigest(),
                             all_region_gzip_sha256=hashlib.sha256(compressed).hexdigest(),
                             per_municipality_summary=summaries, per_municipality=per_town)
    return dict(schema_version=1, status="offline_transport_projection_not_http_traffic_or_production_cache",
                source_payload_sha256=hashlib.sha256(raw).hexdigest(), source_payload_bytes=len(raw),
                municipalities=215, variables=28, hourly_instants=97, unique_cells=len(payload["cells"]),
                run_utc=payload["run_utc"], results=results,
                metrics=dict(parse_seconds=parse_seconds, profile_seconds=time.perf_counter()-tick),
                limitations=["No GRIB was downloaded or decoded again; no server request or production traffic was measured.",
                             "Both proposals retain the same unrounded converted values, times, units, quality flags, run, cell and source hash.",
                             "Display-only omits raw-value duplication and low-level binary metadata from transport, not from retained source evidence.",
                             "Each per-municipality size includes common metadata; shared browser/server caching can change actual transferred bytes.",
                             "The all-region payload is not necessary for a user viewing only one municipality."])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument("--request-plan", type=Path,
                        help="Required immutable verified plan for regional GRIB decode")
    parser.add_argument("--compare-pordenone", type=Path)
    parser.add_argument("--profile-existing", type=Path, help="Only measure audit/display transport from existing JSON; do not decode GRIB")
    args = parser.parse_args()
    if args.profile_existing:
        if args.input or args.output or args.request_plan or args.compare_pordenone or args.report.exists() or not args.report.parent.is_dir() or args.profile_existing.resolve() == args.report.resolve():
            parser.error("Profile mode requires only an existing JSON and a new report")
        report = compact_json(profile_existing(args.profile_existing))
        with args.report.open("xb") as destination:
            destination.write(report)
        print(compact_json(dict(status="offline_projection_complete", report_bytes=len(report))).decode())
        return
    if not args.input or not args.output or not args.request_plan:
        parser.error("Decode mode requires --input, --output and --request-plan")
    inputs = [args.input.resolve()] + ([args.compare_pordenone.resolve()] if args.compare_pordenone else [])
    outputs = [args.output, args.report]
    if len({p.resolve() for p in outputs}) != 2 or any(p.resolve() in inputs or p.exists() or not p.parent.is_dir() for p in outputs):
        parser.error("Output and report must be new distinct files, never overwrite input/evidence")
    try:
        plan, _, plan_hash = load_verified_request_plan(args.request_plan)
    except PublicMetadataError as exc:
        parser.error(str(exc))
    encoded, report = run_file(
        args.input,
        request_plan=plan,
        request_plan_sha256=plan_hash,
        previous_path=args.compare_pordenone,
    )
    for path, data in zip(outputs, (encoded, report)):
        with path.open("xb") as destination:
            destination.write(data)
    print(compact_json(dict(status="complete", payload_bytes=len(encoded), report_bytes=len(report))).decode())


if __name__ == "__main__":
    main()
