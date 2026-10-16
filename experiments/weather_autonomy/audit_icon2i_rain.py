"""Audit two same-run rain accumulations, without changing the benchmark payload.

Only anonymous ranges from the fixed ICON-2I 2026090212 TOT_PREC file are read.
The two complete GRIB messages are decoded once each; no whole-file fallback,
clipping, application imports, credentials, provider writes or new dependencies.
For simple GRIB packing, the representable increment is 2**E * 10**(-D).
Compatibility with that increment alone cannot prove the cause of a decrease.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import json
import math
from pathlib import Path
import time

from benchmark_icon2i import message_span, validate_metadata
from probe_icon2i import BASE, PublicReader, message_length

RUN = "2026090212"
STEPS = (25, 26)
FIRST_MESSAGE_BYTES = 210
HOURLY_MESSAGE_BYTES = 1_158_452
FLAG = "negative_rain_accumulation_or_increment_no_clipping"
MAX_BYTES = 40 * 1024**2


def decode_rain(message, *, step, indexes, grid_hash):
    import eccodes as ec

    if len(message) != HOURLY_MESSAGE_BYTES or message_length(message[:16]) != len(message) or message[-4:] != b"7777":
        raise ValueError("Unexpected/truncated GRIB message")
    handle = ec.codes_new_from_message(message)
    try:
        ec.codes_set(handle, "stepUnits", 1)
        keys = ("shortName", "paramId", "units", "typeOfLevel", "level", "dataDate", "dataTime", "validityDate", "validityTime", "startStep", "endStep", "stepUnits", "stepType", "gridType", "numberOfPoints", "Ni", "Nj", "uvRelativeToGrid", "md5GridSection")
        meta = {key: ec.codes_get(handle, key) for key in keys}
        validate_metadata(meta, "TOT_PREC", RUN, step)
        if meta["md5GridSection"] != grid_hash:
            raise ValueError("Grid changed; cached municipality indexes are unsafe")
        if any(type(index) is not int or not 0 <= index < meta["numberOfPoints"] for index in indexes):
            raise ValueError("Invalid cached municipality grid index")
        packing = {key: ec.codes_get(handle, key) for key in ("packingType", "bitsPerValue", "binaryScaleFactor", "decimalScaleFactor", "referenceValue")}
        if packing["packingType"] != "grid_simple" or packing["bitsPerValue"] <= 0:
            raise ValueError("Quantization audit requires nonconstant simple packing")
        quantum = 2.0 ** packing["binaryScaleFactor"] * 10.0 ** (-packing["decimalScaleFactor"])
        if not math.isfinite(quantum) or quantum <= 0:
            raise ValueError("Invalid quantization step")
        packing["representable_increment_mm"] = quantum
        values = [float(value) for value in ec.codes_get_elements(handle, "values", indexes)]
        missing = ec.codes_get(handle, "missingValue")
        if len(values) != len(indexes) or any(not math.isfinite(value) or value == missing for value in values):
            raise ValueError("Missing/nonfinite rain accumulation")
        return {"metadata": meta, "packing": packing, "values": values, "grib_sha256": hashlib.sha256(message).hexdigest()}
    finally:
        ec.codes_release(handle)


def run_audit(report_path, payload_path):
    started = time.perf_counter()
    report = json.loads(report_path.read_text(encoding="utf-8"))
    payload_bytes = payload_path.read_bytes()
    if hashlib.sha256(payload_bytes).hexdigest() != report["json_sha256"]:
        raise ValueError("Payload checksum does not match the original benchmark")
    payload = json.loads(payload_bytes)
    expected_run_time = datetime.strptime(RUN, "%Y%m%d%H").replace(tzinfo=timezone.utc)
    if report["run"] != RUN or payload["run_utc"] != expected_run_time.isoformat():
        raise ValueError("This audit only covers the specified original run")
    points = payload["municipalities"]
    if len(points) != 215 or len({point["id"] for point in points}) != 215:
        raise ValueError("Expected 215 unique municipalities from the benchmark")
    indexes = [point["grid_point"]["index"] for point in points]
    columns = payload["columns"]
    flags_index = columns.index("quality_flags")
    rain_index = columns.index("precipitation_previous_hour_mm")
    target_time = (expected_run_time + timedelta(hours=STEPS[1])).isoformat()
    target_index = payload["times_utc"].index(target_time)
    flagged_ids = {point["id"] for point in points if FLAG in point["hourly"][target_index][flags_index]}
    all_flagged_count = sum(FLAG in row[flags_index] for point in points for row in point["hourly"])
    if len(flagged_ids) != 25 or all_flagged_count != 25:
        raise ValueError("Original anomaly pattern differs from the requested 25-point audit")

    field = report["fields"]["TOT_PREC"]
    url = field["url"]
    expected_url = f"{BASE}{RUN}/TOT_PREC/ICON_2I_SURFACE_PRESSURE_LEVELS_{RUN}_surface-0.grib"
    if url != expected_url:
        raise ValueError("Unexpected public rain-file URL")
    reader = PublicReader(max_bytes=MAX_BYTES)
    first_header, total = reader.get(url, 0, 15)
    if message_length(first_header) != FIRST_MESSAGE_BYTES or total != field["whole_file_bytes"]:
        raise ValueError("Original rain-file first message/size changed")
    second_header, second_total = reader.get(url, FIRST_MESSAGE_BYTES, FIRST_MESSAGE_BYTES + 15)
    if message_length(second_header) != HOURLY_MESSAGE_BYTES or second_total != total or total != FIRST_MESSAGE_BYTES + 72 * HOURLY_MESSAGE_BYTES:
        raise ValueError("Unverified hourly rain-file packing")

    decoded = {}
    for step in STEPS:
        start, end = message_span(FIRST_MESSAGE_BYTES, HOURLY_MESSAGE_BYTES, step, step)
        message, current_total = reader.get(url, start, end)
        if current_total != total:
            raise ValueError("Rain-file size changed during audit")
        decoded[step] = decode_rain(message, step=step, indexes=indexes, grid_hash=report["grid_hash"])
        del message
    q_previous = decoded[STEPS[0]]["packing"]["representable_increment_mm"]
    q_current = decoded[STEPS[1]]["packing"]["representable_increment_mm"]
    # These are diagnostic scales, not a clipping rule or a proof that either
    # the encoder or underlying model used a specific rounding convention.
    half_sum = (q_previous + q_current) / 2
    full_sum = q_previous + q_current
    rows = []
    for index, point in enumerate(points):
        previous = decoded[STEPS[0]]["values"][index]
        current = decoded[STEPS[1]]["values"][index]
        difference = current - previous
        original = point["hourly"][target_index][rain_index]
        negative = previous < 0 or current < 0 or difference < 0
        if negative != (point["id"] in flagged_ids):
            raise ValueError("Fresh raw data does not reproduce the original flagged municipalities")
        if negative and original is not None or not negative and original != round(difference, 3):
            raise ValueError("Fresh increment is inconsistent with the original unchanged payload")
        rows.append({
            "id": point["id"], "grid_index": indexes[index],
            "accumulation_step_25_mm": previous, "accumulation_step_26_mm": current,
            "raw_increment_mm": difference, "original_payload_increment_mm": original,
            "original_negative_flag": negative,
            "decrease_over_half_sum_quanta": -difference / half_sum if negative else None,
            "decrease_within_half_sum_quanta": -difference <= half_sum if negative else None,
            "decrease_within_sum_quanta": -difference <= full_sum if negative else None,
        })
    negative_rows = [row for row in rows if row["original_negative_flag"]]
    return {
        "status": "diagnostic_only_no_clipping_no_payload_change",
        "accessed_at_utc": datetime.now(timezone.utc).isoformat(),
        "run": RUN, "steps": list(STEPS), "url": url,
        "source_payload_sha256": report["json_sha256"], "grid_hash": report["grid_hash"],
        "downloaded_bytes": reader.bytes_read, "http_get_requests": reader.requests,
        "decoded_messages": len(decoded), "elapsed_seconds": time.perf_counter() - started,
        "messages": {str(step): {key: value for key, value in decoded[step].items() if key != "values"} for step in STEPS},
        "half_sum_of_quantization_steps_mm": half_sum,
        "sum_of_quantization_steps_mm": full_sum,
        "negative_count": len(negative_rows),
        "negative_minimum_mm": min(row["raw_increment_mm"] for row in negative_rows),
        "negative_maximum_mm": max(row["raw_increment_mm"] for row in negative_rows),
        "negative_within_half_sum_quanta_count": sum(row["decrease_within_half_sum_quanta"] for row in negative_rows),
        "negative_within_sum_quanta_count": sum(row["decrease_within_sum_quanta"] for row in negative_rows),
        "negative_rows": negative_rows, "all_municipality_rows": rows,
        "interpretation_limits": [
            "Representable grid-simple step = 2**binaryScaleFactor * 10**(-decimalScaleFactor).",
            "A decrease within packing resolution is compatible with quantization but does not prove its cause.",
            "Half-sum corresponds to a hypothetical nearest-rounding error envelope; no encoder rounding convention is assumed.",
            "Same-run and temporal metadata are verified, but upstream processing changes cannot be excluded from two messages.",
            "No values are clipped, corrected, re-promoted into the payload or integrated into the app.",
        ],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--payload", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists() or not args.output.parent.is_dir() or args.output.resolve() in (args.report.resolve(), args.payload.resolve()):
        parser.error("Audit output must be a distinct new file in an existing directory")
    result = run_audit(args.report, args.payload)
    with args.output.open("x", encoding="utf-8") as destination:
        json.dump(result, destination, ensure_ascii=False, indent=2, allow_nan=False)
        destination.write("\n")
    summary = {key: value for key, value in result.items() if key not in ("all_municipality_rows", "negative_rows")}
    print(json.dumps(summary, ensure_ascii=False, indent=2, allow_nan=False), flush=True)
    print(f"Audit: {args.output}", flush=True)


if __name__ == "__main__":
    main()
