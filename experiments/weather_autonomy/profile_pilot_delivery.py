"""Offline delivery-size proposal for an already acquired LOCAL ICON pilot.

No network, app imports, provider switch or raw-GRIB processing. This profiles
packing/serialization separately from the integrated acquisition benchmark.
The immutable diagnostic/source artifacts retain raw accumulations and signed
increments. The proposed transport preserves derived values, nulls, quality
flags, encoding uncertainty and capability gaps, but does not ship raw fields.
"""

from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import gzip
import hashlib
import json
import math
from pathlib import Path
import time

from pilot_policy import aggregate_two_hour, assess_window

MAX_INPUT_BYTES = 64 * 1024**2
ENCODING_FIELDS = ("TOT_PREC", "RAIN_CON", "RAIN_GSP", "SNOW_CON", "SNOW_GSP", "GRAU_GSP")
VALUE_COLUMNS = (
    "temperature_c", "dewpoint_c", "relative_humidity_pct", "apparent_temperature_c",
    "heat_index_c", "wind_chill_c", "wind_m_s", "wind_from_degrees", "wind_gust_m_s",
    "pressure_msl_hpa", "cloud_cover_pct", "precipitation_previous_hour_mm",
    "rain_previous_hour_mm", "convective_rain_previous_hour_mm",
    "snow_water_equivalent_previous_hour_mm", "graupel_water_equivalent_previous_hour_mm",
    "precipitation_probability_pct", "visibility_m",
)
COLUMNS = VALUE_COLUMNS + (
    "grid_scale_rain_previous_hour_mm", "convective_snow_water_equivalent_previous_hour_mm",
    "grid_scale_snow_water_equivalent_previous_hour_mm", "weather_code",
    "weather_condition_label", "weather_condition_status", "precipitation_uncertainty_mm",
    "quality_flags",
)
TWO_HOUR_COLUMNS = (
    "start_at_utc", "end_at_utc", "source_hours", "precipitation_mm", "wind_gust_max_m_s",
    "temperature_min_c", "temperature_max_c", "temperature_end_c", "status", "quality_flags",
)


def compact_json(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode("utf-8")


def utc(value, *, hourly=False):
    if not isinstance(value, str):
        raise ValueError("Expected an explicit UTC timestamp")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() != timedelta(0):
        raise ValueError("Expected an explicit UTC timestamp")
    if hourly and (parsed.minute or parsed.second or parsed.microsecond):
        raise ValueError("Forecast timestamp is not on an exact hour")
    return parsed.astimezone(timezone.utc)


def iso(value):
    return value.isoformat().replace("+00:00", "Z")


def number_or_null(value):
    if value is not None and (isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value)):
        raise ValueError("Expected a finite number or an explicit null")
    return value


def pack_row(row):
    """Keep explicit nulls and zero distinct; no meteorological recomputation."""
    values = [number_or_null(row[key]) for key in VALUE_COLUMNS]
    # These remain capability gaps in this specific pilot; do not advertise an
    # unexplained value as an ICON probability or a visibility observation.
    if row["precipitation_probability_pct"] is not None or row["visibility_m"] is not None:
        raise ValueError("Current pilot does not supply probability or visibility")
    encoding = row["precipitation_encoding"]
    values.extend(number_or_null(encoding[key]["value_mm"]) for key in ("RAIN_GSP", "SNOW_CON", "SNOW_GSP"))
    condition = row["condition"]
    code = number_or_null(condition["code"])
    if code is not None and int(code) != code:
        raise ValueError("WW code must be integer-valued")
    if condition["status"] not in ("valid", "unknown", "invalid") or not isinstance(condition["label"], str):
        raise ValueError("Missing weather-code interpretation status")
    values.extend((code, condition["label"], condition["status"]))
    values.append([number_or_null(encoding[key]["uncertainty_mm"]) for key in ENCODING_FIELDS])
    flags = row["quality_flags"]
    if not isinstance(flags, list) or not all(isinstance(flag, str) for flag in flags):
        raise ValueError("Invalid quality flags")
    values.append(list(flags))
    return values


def make_candidate(payload):
    if payload.get("schema_version") != 1 or payload.get("status") != "partial_pilot_not_production":
        raise ValueError("Expected a version-1 isolated pilot payload")
    if not isinstance(payload.get("validation"), dict) or payload["validation"].get("usable") is not True:
        raise ValueError("Refusing an unusable diagnostic payload")
    now = utc(payload["generated_at_utc"])
    utc(payload["run_utc"], hourly=True)
    floor = now.replace(minute=0, second=0, microsecond=0)
    ceiling = floor if now == floor else floor + timedelta(hours=1)
    end = ceiling + timedelta(hours=48)
    required = [floor + timedelta(hours=h) for h in range(1, int((end - floor).total_seconds() / 3600) + 1)]
    towns = payload.get("municipalities")
    if not isinstance(towns, list) or not towns or len({town["id"] for town in towns}) != len(towns):
        raise ValueError("Expected nonempty, unique municipality records")
    source = payload["sources"]["icon"]
    if source.get("status") != "acquired_and_decoded" or source.get("run_utc") != payload["run_utc"]:
        raise ValueError("ICON source does not match the verified run")
    if any(not isinstance(source.get(key), str) or not source[key] for key in ("attribution", "license", "url")):
        raise ValueError("Missing source attribution or licence")
    capabilities = payload.get("capabilities")
    if not isinstance(capabilities, list) or not all(isinstance(item, dict) and isinstance(item.get("status"), str) for item in capabilities):
        raise ValueError("Missing capability manifest")
    packed_towns = []
    common_times = None
    for town in towns:
        hourly = town["hourly"]
        times = [utc(row["valid_at_utc"], hourly=True) for row in hourly]
        check = assess_window(payload["run_utc"], [iso(value) for value in times], payload["generated_at_utc"])
        if not check["usable"]:
            raise ValueError("Incomplete or invalid native hourly coverage")
        if common_times is not None and times != common_times:
            raise ValueError("Municipalities have different forecast timelines")
        common_times = times
        selected = [row for row, instant in zip(hourly, times, strict=True) if now < instant <= end]
        if [utc(row["valid_at_utc"]) for row in selected] != required:
            raise ValueError("Cannot deliver a continuous full future 48-hour window")
        current = [row for row, instant in zip(hourly, times, strict=True) if instant <= now]
        if not current or utc(current[-1]["valid_at_utc"]) != floor:
            raise ValueError("Current model hour is unavailable")
        metadata = {key: deepcopy(town[key]) for key in ("id", "name", "latitude", "longitude", "grid_point")}
        metadata.update(
            current={"valid_at_utc": iso(floor), "values": pack_row(current[-1])},
            hourly=[pack_row(row) for row in selected],
            two_hourly=[[record[key] for key in TWO_HOUR_COLUMNS] for record in aggregate_two_hour(selected)],
        )
        packed_towns.append(metadata)
    candidate = dict(
        schema_version=1, status="offline_transport_candidate_not_production",
        run_utc=payload["run_utc"], generated_at_utc=payload["generated_at_utc"],
        validation=assess_window(payload["run_utc"], [iso(floor)] + [iso(value) for value in required], payload["generated_at_utc"]),
        source={key: source[key] for key in ("attribution", "license", "url")},
        capability_gaps=[deepcopy(item) for item in capabilities if item["status"] in ("missing", "blocked", "pending")],
        columns=list(COLUMNS), times_utc=[iso(value) for value in required],
        two_hourly_columns=list(TWO_HOUR_COLUMNS), precipitation_uncertainty_fields=list(ENCODING_FIELDS),
        delivery_policy=dict(
            mode="Offline packing proposal, not an integrated runtime or production endpoint",
            current="Latest model hour at or before generation; not an observation at the current minute",
            future="Strictly after generation through ceil(generation)+48h; 48 or 49 hourly end points",
            validation="Assesses the reduced transport window; source payload must independently be usable",
            two_hourly="Re-aggregate consecutive future hours, never skip an hour; final unpaired interval stays incomplete",
            omitted="Raw accumulations, signed increments and GRIB metadata stay in separate immutable source/diagnostic evidence",
            coordinates=payload.get("processing", {}).get("location", "Same local municipality catalog; no live geocoding"),
            processing=deepcopy(payload.get("processing", {})),
        ),
        municipalities=packed_towns,
    )
    compact_json(candidate)  # Fail closed on any nonfinite value in metadata.
    return candidate


def measure_candidate(candidate):
    started = time.perf_counter()
    encoded = compact_json(candidate)
    serialized_seconds = time.perf_counter() - started
    started = time.perf_counter()
    compressed = gzip.compress(encoded, compresslevel=6, mtime=0)
    compressed_seconds = time.perf_counter() - started
    shared = {key: value for key, value in candidate.items() if key != "municipalities"}
    singles = []
    for town in candidate["municipalities"]:
        data = compact_json(dict(shared, municipalities=[town]))
        zipped = gzip.compress(data, compresslevel=6, mtime=0)
        singles.append(dict(id=town["id"], json_bytes=len(data), gzip_bytes=len(zipped), sha256=hashlib.sha256(data).hexdigest()))
    return dict(
        mode="offline_delivery_packing_profile_not_integrated_runtime",
        municipality_count=len(singles), future_hourly_instants=len(candidate["times_utc"]),
        current_valid_at_utc=candidate["municipalities"][0]["current"]["valid_at_utc"],
        remaining_future_coverage_hours=candidate["validation"]["coverage_hours"],
        first_future_at_utc=candidate["times_utc"][0], last_future_at_utc=candidate["times_utc"][-1],
        json_bytes=len(encoded), gzip_bytes=len(compressed), sha256=hashlib.sha256(encoded).hexdigest(),
        gzip_sha256=hashlib.sha256(compressed).hexdigest(),
        json_serialize_seconds=serialized_seconds, gzip_seconds=compressed_seconds,
        single_municipality_sizes=singles,
        single_municipality_min_json_bytes=min(item["json_bytes"] for item in singles),
        single_municipality_max_json_bytes=max(item["json_bytes"] for item in singles),
        single_municipality_min_gzip_bytes=min(item["gzip_bytes"] for item in singles),
        single_municipality_max_gzip_bytes=max(item["gzip_bytes"] for item in singles),
        measurement_scope="Exact UTF-8 compact JSON and gzip level 6, mtime 0. Sizes exclude this separate report, not transport data. No network or serving overhead measured.",
    )


def run_profile(payload_path, candidate_path, report_path):
    paths = [Path(value) for value in (payload_path, candidate_path, report_path)]
    source, candidate_file, report_file = paths
    if len({path.resolve() for path in paths}) != 3:
        raise ValueError("Input and output paths must be distinct")
    if not source.is_file() or source.stat().st_size > MAX_INPUT_BYTES:
        raise ValueError("Input must be an existing file of at most 64 MiB")
    if any(path.exists() or not path.parent.is_dir() for path in paths[1:]):
        raise ValueError("Outputs must be NEW files in existing directories")
    with source.open("rb") as stream:
        raw = stream.read(MAX_INPUT_BYTES + 1)
    if len(raw) > MAX_INPUT_BYTES:
        raise ValueError("Input grew beyond the 64 MiB limit")
    started = time.perf_counter()
    payload = json.loads(raw)
    parse_seconds = time.perf_counter() - started
    started = time.perf_counter()
    candidate = make_candidate(payload)
    pack_seconds = time.perf_counter() - started
    report = measure_candidate(candidate)
    report.update(input_sha256=hashlib.sha256(raw).hexdigest(), input_bytes=len(raw),
                  parse_seconds=parse_seconds, packing_seconds=pack_seconds)
    with candidate_file.open("xb") as stream:
        stream.write(compact_json(candidate))
    with report_file.open("xb") as stream:
        stream.write(compact_json(report))
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--payload", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    report = run_profile(args.payload, args.candidate, args.report)
    print(json.dumps({key: value for key, value in report.items() if key != "single_municipality_sizes"}, indent=2))


if __name__ == "__main__":
    main()
