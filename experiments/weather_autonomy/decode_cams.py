"""Strict, OFFLINE point extraction of a separately downloaded CAMS GRIB2.

No credentials, remote access or application imports. Identity follows ECMWF's
regional-CAMS documentation, not ecCodes' possibly generic/unknown paramId:
https://forum.ecmwf.int/t/how-to-identify-fields-in-european-air-quality-forecast-grib-files/1563
Units and vertical scope:
https://confluence.ecmwf.int/spaces/CKB/pages/202173092/CAMS+Regional+European+air+quality+analysis+and+forecast+data+documentation

The three newer PM2.5 components additionally use ECMWF ecCodes' bundled WMO
table grib2/tables/21/4.230.table (verified using ecCodes 2.48.0 on 2026-09-03):
62003 Ammonium dry, 62004 Nitrate dry, 62006 Sulphate dry. The chemical names
are joined to the official ADS catalogue's PM2.5 selections, not inferred from
file ordering or magnitudes. This mapping is scoped to this regional dataset.
Unknown identities fail rather than silently removing requested variables.
"""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timedelta, timezone
import hashlib
import gzip
import json
import math
from pathlib import Path
import time

from cams_request_plan import (
    DATASET,
    EXPECTED_LEADS,
    EXPECTED_VARIABLE_IDS,
    PublicMetadataError,
    load_verified_request_plan,
    request_sha256,
    validate_request_plan,
)

MAX_FILE_BYTES = 128 * 1024**2
MAX_MESSAGE_BYTES = 4 * 1024**2
POINT = (45.95689, 12.66051)
AREA = (46.1, 12.5, 45.8, 12.8)
IDENTITY_SOURCE = "https://forum.ecmwf.int/t/how-to-identify-fields-in-european-air-quality-forecast-grib-files/1563"
DATA_SOURCE = "https://confluence.ecmwf.int/spaces/CKB/pages/202173092/CAMS+Regional+European+air+quality+analysis+and+forecast+data+documentation"
VARIABLE_IDENTITIES = {
    "alder_pollen": (59, 62100), "ammonia": (0, 9), "birch_pollen": (59, 62101),
    "carbon_monoxide": (0, 4), "formaldehyde": (0, 7), "glyoxal": (0, 10038),
    "grass_pollen": (59, 62300), "mugwort_pollen": (59, 62201),
    "nitrogen_dioxide": (0, 5), "nitrogen_monoxide": (0, 11),
    "non_methane_vocs": (0, 60013), "olive_pollen": (59, 64002), "ozone": (0, 0),
    "particulate_matter_2.5um": (0, 40009), "particulate_matter_10um": (0, 40008),
    "dust": (0, 62001), "pm10_sea_salt_dry": (0, 62008), "pm10_wildfires": (0, 62096),
    "peroxyacyl_nitrates": (0, 60018), "ragweed_pollen": (59, 62200),
    "residential_elementary_carbon": (0, 62094), "secondary_inorganic_aerosol": (0, 62099),
    "total_elementary_carbon": (0, 62095), "pm2.5_total_organic_matter": (0, 62010),
    "sulphur_dioxide": (0, 8),
    "pm2.5_ammonium": (0, 62003), "pm2.5_nitrate": (0, 62004), "pm2.5_sulphate": (0, 62006),
}
NEW_COMPONENT_EVIDENCE = {
    "pm2.5_ammonium": "Ammonium dry", "pm2.5_nitrate": "Nitrate dry", "pm2.5_sulphate": "Sulphate dry",
}
EXPECTED_VARIABLES = EXPECTED_VARIABLE_IDS
META_KEYS = (
    "edition", "subCentre", "discipline", "parameterCategory", "parameterNumber",
    "constituentType", "shortName", "paramId", "name", "units", "typeOfLevel", "level",
    "typeOfFirstFixedSurface", "typeOfSecondFixedSurface", "dataDate", "dataTime",
    "validityDate", "validityTime", "stepType", "startStep", "endStep", "stepUnits",
    "gridType", "Ni", "Nj", "numberOfPoints", "md5GridSection",
    "latitudeOfFirstGridPointInDegrees", "longitudeOfFirstGridPointInDegrees",
    "latitudeOfLastGridPointInDegrees", "longitudeOfLastGridPointInDegrees",
    "iDirectionIncrementInDegrees", "jDirectionIncrementInDegrees",
    "iScansNegatively", "jScansPositively", "jPointsAreConsecutive", "alternativeRowScanning",
    "productDefinitionTemplateNumber", "typeOfProcessedData", "typeOfGeneratingProcess",
    "productionStatusOfProcessedData", "tablesVersion", "localTablesVersion",
)


def compact_json(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode("utf-8")


def run_time(run_date):
    if type(run_date) is not str:
        raise ValueError("Run date must be an explicit YYYY-MM-DD string")
    try:
        value = datetime.strptime(run_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except ValueError:
        raise ValueError("Run date must be YYYY-MM-DD") from None
    if value.strftime("%Y-%m-%d") != run_date:
        raise ValueError("Run date must be YYYY-MM-DD")
    return value


def iso(value):
    return value.isoformat().replace("+00:00", "Z")


def _finite(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def identity(meta):
    if meta["discipline"] != 0 or meta["parameterCategory"] != 20:
        raise ValueError("Not an atmospheric chemical constituent field")
    return (meta["parameterNumber"], meta["constituentType"])


def identify_variable(meta):
    matches = [variable for variable, pair in VARIABLE_IDENTITIES.items() if pair == identity(meta)]
    if len(matches) != 1:
        raise ValueError(f"Unverified CAMS variable identity {identity(meta)}; use inventory, do not guess")
    return matches[0]


def verify_metadata(meta, date, area=AREA):
    """Verify ensemble, surface selection, hourly validity and bounded grid."""
    if meta["edition"] != 2 or meta["centre"] != 85 or meta["subCentre"] != 2:
        raise ValueError("Expected GRIB2 CAMS ensemble median, centre 85/subCentre 2")
    if meta["productDefinitionTemplateNumber"] != 40 or meta["typeOfProcessedData"] != 1 or meta["typeOfGeneratingProcess"] != 2:
        raise ValueError("Expected a forecast constituent product, not an analysis or probability field")
    identity(meta)
    if meta["typeOfLevel"] not in ("surface", "heightAboveGround") or meta["level"] != 0:
        raise ValueError("Expected the surface/0-metre dataset selection")
    if meta["typeOfFirstFixedSurface"] not in (1, 103) or meta["typeOfSecondFixedSurface"] != 255:
        raise ValueError("Unexpected vertical layer or second surface")
    expected_type = "surface" if meta["typeOfFirstFixedSurface"] == 1 else "heightAboveGround"
    if meta["typeOfLevel"] != expected_type:
        raise ValueError("Inconsistent vertical metadata")
    start = run_time(date)
    if meta["dataDate"] != int(start.strftime("%Y%m%d")) or meta["dataTime"] != 0:
        raise ValueError("CAMS run date/time mismatch")
    step = meta["endStep"]
    if isinstance(step, bool) or not isinstance(step, int) or not 0 <= step <= 96:
        raise ValueError("Expected hourly leads 0..96")
    if str(meta["stepUnits"]) != "1" or meta["startStep"] != step or meta["stepType"] != "instant":
        raise ValueError("Not an instantaneous hourly CAMS forecast field")
    expected = start + timedelta(hours=step)
    if meta["validityDate"] != int(expected.strftime("%Y%m%d")) or meta["validityTime"] != int(expected.strftime("%H%M")):
        raise ValueError("CAMS validity does not match run plus lead")
    ni, nj, count = meta["Ni"], meta["Nj"], meta["numberOfPoints"]
    if meta["gridType"] != "regular_ll" or any(isinstance(v, bool) or not isinstance(v, int) for v in (ni, nj, count)):
        raise ValueError("Expected a regular latitude-longitude grid")
    if ni < 2 or nj < 2 or count != ni * nj or count > 10000:
        raise ValueError("Unexpected grid size for a bounded Pordenone crop")
    if any(not _finite(meta[key]) or abs(meta[key] - 0.1) > 1e-6
           for key in ("iDirectionIncrementInDegrees", "jDirectionIncrementInDegrees")):
        raise ValueError("Expected native 0.1-degree CAMS regional spacing")
    if meta["iScansNegatively"] not in (0, 1) or meta["jScansPositively"] not in (0, 1) or meta["jPointsAreConsecutive"] != 0 or meta["alternativeRowScanning"] != 0:
        raise ValueError("Unsupported grid scanning layout")
    north, west, south, east = area
    for edge in ("First", "Last"):
        lat, lon = meta[f"latitudeOf{edge}GridPointInDegrees"], meta[f"longitudeOf{edge}GridPointInDegrees"]
        if not _finite(lat) or not _finite(lon) or not south - 0.100001 <= lat <= north + 0.100001 or not west - 0.100001 <= lon <= east + 0.100001:
            raise ValueError("GRIB area is outside the bounded requested crop")
    expected_last_lat = meta["latitudeOfFirstGridPointInDegrees"] + (nj - 1) * (0.1 if meta["jScansPositively"] else -0.1)
    expected_last_lon = meta["longitudeOfFirstGridPointInDegrees"] + (ni - 1) * (-0.1 if meta["iScansNegatively"] else 0.1)
    if abs(meta["latitudeOfLastGridPointInDegrees"] - expected_last_lat) > 1e-6 or abs(meta["longitudeOfLastGridPointInDegrees"] - expected_last_lon) > 1e-6:
        raise ValueError("Grid shape/corners/scanning are inconsistent")
    if not isinstance(meta["md5GridSection"], str) or not meta["md5GridSection"]:
        raise ValueError("Missing grid fingerprint")
    return step


def convert_value(raw, meta, missing_value=None):
    """Retain raw units/value, only apply documented mass/count conversions.

    Some regional local constituents have units='unknown' in ecCodes. Once
    identity is independently recognized, the documented parameter encoding
    and CAMS regional unit table establish kg/m3 (number 0) or grains/m3 (59).
    An incompatible explicit unit fails, instead of applying a guessed scale.
    """
    variable = identify_variable(meta)
    pollen = variable.endswith("_pollen")
    raw_units = meta["units"]
    accepted = {"unknown", "~", "", None}
    accepted |= ({"m**-3", "m^-3", "m-3", "1/m3", "1 m**-3", "grains m**-3", "grains m^-3", "grains/m3"}
                 if pollen else {"kg m**-3", "kg m^-3", "kg/m3", "kg m-3"})
    if raw_units not in accepted:
        raise ValueError(f"Incompatible explicit GRIB unit for {variable}: {raw_units}")
    result = dict(raw_value=raw if _finite(raw) else None, raw_units=raw_units,
                  source_units="grains/m3" if pollen else "kg/m3",
                  value=None, units="grains/m3" if pollen else "ug/m3",
                  conversion_factor=1.0 if pollen else 1e9, status="valid", quality_flags=[])
    if raw_units in {"unknown", "~", "", None}:
        result["quality_flags"].append("unit_resolved_from_verified_parameter_identity_and_provider_documentation")
    if raw is None or missing_value is not None and raw == missing_value:
        result.update(raw_value=None, status="missing")
        result["quality_flags"].append("missing_model_value")
    elif not _finite(raw):
        result["status"] = "invalid"
        result["quality_flags"].append("nonfinite_or_nonnumeric_model_value")
    elif raw < 0:
        result["status"] = "invalid"
        result["quality_flags"].append("negative_concentration_not_clipped")
    else:
        value = raw * result["conversion_factor"]
        if math.isfinite(value):
            result["value"] = value
        else:
            result["status"] = "invalid"
            result["quality_flags"].append("conversion_overflow")
    return result


def grib_messages(path):
    path = Path(path)
    if not path.is_file() or not 20 <= path.stat().st_size <= MAX_FILE_BYTES:
        raise ValueError("Expected an existing GRIB file of at most 128 MiB")
    total = 0
    with path.open("rb") as stream:
        while True:
            header = stream.read(16)
            if not header:
                break
            if len(header) != 16 or header[:4] != b"GRIB" or header[7] != 2:
                raise ValueError("Expected contiguous GRIB2 messages, not ZIP/HTML or trailing bytes")
            size = int.from_bytes(header[8:16], "big")
            if not 20 <= size <= MAX_MESSAGE_BYTES or total + size > MAX_FILE_BYTES:
                raise ValueError("GRIB message/file exceeds bounded size")
            tail = stream.read(size - 16)
            if len(tail) != size - 16 or tail[-4:] != b"7777":
                raise ValueError("Truncated or corrupt GRIB message")
            total += size
            yield header + tail


def read_metadata(ec, handle):
    ec.codes_set(handle, "stepUnits", 1)
    meta = {key: ec.codes_get(handle, key) for key in META_KEYS}
    # ecCodes' native type for some code tables is a string ("sfc", "fc",
    # "lfpw"). Numeric codes make validation independent of display aliases.
    for key in ("centre", "typeOfFirstFixedSurface", "typeOfSecondFixedSurface", "typeOfProcessedData"):
        meta[key] = ec.codes_get_long(handle, key)
    return meta


class CamsPointDecoder:
    def __init__(self, *, date, point=POINT, area=AREA,
                 expected_variables=EXPECTED_VARIABLES, expected_leads=tuple(range(97)), ec=None):
        if ec is None:
            import eccodes as ec
        self.ec, self.date, self.point, self.area = ec, date, tuple(point), tuple(area)
        run_time(date)
        if len(self.point) != 2 or len(self.area) != 4 or not all(_finite(v) for v in self.point + self.area):
            raise ValueError("Invalid point or area coordinates")
        north, west, south, east = self.area
        lat, lon = self.point
        if not 45 <= south < north <= 47.2 or not 11.8 <= west < east <= 14.5 or not south <= lat <= north or not west <= lon <= east:
            raise ValueError("Point/crop must be within the isolated FVG pilot")
        self.expected_variables, self.expected_leads = tuple(expected_variables), tuple(expected_leads)
        if not self.expected_variables or len(set(self.expected_variables)) != len(self.expected_variables) or not set(self.expected_variables) <= set(EXPECTED_VARIABLES):
            raise ValueError("Invalid expected variable list")
        if not self.expected_leads or len(set(self.expected_leads)) != len(self.expected_leads) or any(isinstance(v, bool) or not isinstance(v, int) or not 0 <= v <= 96 for v in self.expected_leads):
            raise ValueError("Invalid expected hourly leads")
        self.grid_hash = self.grid_point = None
        self.series, self.first_metadata = {}, {}
        self.mapping_builds = 0
        self.seconds = 0.0

    def decode(self, message):
        ec, started = self.ec, time.perf_counter()
        handle = ec.codes_new_from_message(message)
        try:
            meta = read_metadata(ec, handle)
            step = verify_metadata(meta, self.date, self.area)
            variable = identify_variable(meta)
            if variable not in self.expected_variables or step not in self.expected_leads:
                raise ValueError("Unexpected variable or lead in downloaded product")
            records = self.series.setdefault(variable, {})
            if step in records:
                raise ValueError(f"Duplicate field: {variable}, lead {step}")
            if self.grid_hash is None:
                nearest = ec.codes_grib_find_nearest(handle, *self.point, npoints=1)[0]
                index = nearest["index"]
                if isinstance(index, bool) or not isinstance(index, int) or not 0 <= index < meta["numberOfPoints"]:
                    raise ValueError("Invalid nearest-cell index")
                if not all(_finite(nearest[key]) for key in ("lat", "lon", "distance")) or not 0 <= nearest["distance"] <= 10:
                    raise ValueError("Invalid or excessive nearest-grid distance")
                row, column = divmod(index, meta["Ni"])
                expected_lat = meta["latitudeOfFirstGridPointInDegrees"] + row * (0.1 if meta["jScansPositively"] else -0.1)
                expected_lon = meta["longitudeOfFirstGridPointInDegrees"] + column * (-0.1 if meta["iScansNegatively"] else 0.1)
                if abs(nearest["lat"] - expected_lat) > 1e-6 or abs(nearest["lon"] - expected_lon) > 1e-6:
                    raise ValueError("Nearest-cell coordinates do not match its grid index")
                self.grid_point = {key: nearest[key] for key in ("lat", "lon", "distance", "index")}
                self.grid_hash = meta["md5GridSection"]
                self.mapping_builds += 1
                raw = nearest["value"]
            else:
                if meta["md5GridSection"] != self.grid_hash or self.grid_point["index"] >= meta["numberOfPoints"]:
                    raise ValueError("CAMS grid changed; cannot reuse cell index")
                values = ec.codes_get_elements(handle, "values", [self.grid_point["index"]])
                if len(values) != 1:
                    raise ValueError("Missing selected grid value")
                raw = float(values[0])
            converted = convert_value(raw, meta, ec.codes_get(handle, "missingValue"))
            records[step] = dict(lead_hour=step, valid_at_utc=iso(run_time(self.date) + timedelta(hours=step)), **converted)
            self.first_metadata.setdefault(variable, meta)
            return variable, step
        finally:
            ec.codes_release(handle)
            self.seconds += time.perf_counter() - started

    def finish(self):
        if set(self.series) != set(self.expected_variables) or any(set(records) != set(self.expected_leads) for records in self.series.values()):
            absent = sorted(set(self.expected_variables) - set(self.series))
            raise ValueError(f"Incomplete CAMS variable/time matrix; absent variables: {absent}")
        flags = Counter(flag for records in self.series.values() for record in records.values() for flag in record["quality_flags"])
        return dict(schema_version=1, status="isolated_cams_point_extraction_not_production", dataset=DATASET,
                    run_utc=iso(run_time(self.date)), model="ensemble_median", requested_level=0,
                    requested_point=dict(latitude=self.point[0], longitude=self.point[1]), requested_area=list(self.area),
                    grid_point=self.grid_point, grid_hash=self.grid_hash,
                    native_resolution_degrees=0.1, fields=len(self.expected_variables)*len(self.expected_leads),
                    variables=[dict(id=variable, metadata=self.first_metadata[variable],
                                    identity_evidence=(dict(source="ECMWF ecCodes 2.48.0 bundled WMO table grib2/tables/21/4.230.table", constituent_label=NEW_COMPONENT_EVIDENCE[variable],
                                                            scope="Chemical identity joined to the PM2.5 variable in this ADS regional dataset catalogue; no inference from message order")
                                                       if variable in NEW_COMPONENT_EVIDENCE else dict(source=IDENTITY_SOURCE)),
                                    hourly=[self.series[variable][step] for step in sorted(self.expected_leads)]) for variable in self.expected_variables],
                    metrics=dict(decode_seconds=self.seconds, grid_mapping_builds=self.mapping_builds,
                                 unique_fields=sum(len(records) for records in self.series.values()), duplicate_fields=0),
                    quality_flag_counts=dict(flags),
                    sources=dict(identification=IDENTITY_SOURCE, units_and_scope=DATA_SOURCE,
                                 constituent_table="ECMWF ecCodes 2.48.0 bundled grib2/tables/21/4.230.table",
                                 concentration_units_table="ECMWF ecCodes 2.48.0 bundled grib2/tables/21/4.2.0.20.table",
                                 dataset=f"https://ads.atmosphere.copernicus.eu/datasets/{DATASET}", doi="10.24381/a4005cee"),
                    attribution="Copernicus Atmosphere Monitoring Service (CAMS), European regional ensemble providers, Atmosphere Data Store (ADS)",
                    limitations=["Forecast, not station observation or a clinical/health assessment.",
                                 "The surface selection represents regional model lowest layers, not an exact sensor height of zero metres.",
                                 "No spatial/temporal interpolation, bias correction, invented zero, threshold category or AQI.",
                                 "Provider research/experimental status is separate from structural completeness and numeric validity.",
                                 "Raw GRIB units and conversion provenance retained; missing/nonfinite/negative values remain explicit."])


def inventory_file(path):
    """Describe all identities without naming unknown constituents by order."""
    import eccodes as ec
    groups, digest, count = {}, hashlib.sha256(), 0
    for message in grib_messages(path):
        digest.update(message)
        handle = ec.codes_new_from_message(message)
        try:
            meta = read_metadata(ec, handle)
            key = tuple(meta[name] for name in ("centre", "subCentre", "discipline", "parameterCategory", "parameterNumber", "constituentType", "typeOfLevel", "level"))
            group = groups.setdefault(key, dict(metadata=meta, count=0, leads=[], variable=None))
            try:
                group["variable"] = identify_variable(meta)
            except ValueError:
                pass
            group["count"] += 1
            group["leads"].append(meta["endStep"])
            count += 1
        finally:
            ec.codes_release(handle)
    return dict(status="inventory_only_not_verified_extraction", messages=count, input_sha256=digest.hexdigest(),
                identities=list(groups.values()), unverified_variables=sorted(set(EXPECTED_VARIABLES)-set(VARIABLE_IDENTITIES)))


def decoder_plan_options(request_plan, request_plan_hash, expected_area):
    try:
        validate_request_plan(request_plan)
    except PublicMetadataError as exc:
        raise ValueError(str(exc)) from None
    if (
        type(request_plan_hash) is not str
        or len(request_plan_hash) != 64
        or any(character not in "0123456789abcdef" for character in request_plan_hash)
    ):
        raise ValueError("Request-plan SHA-256 is invalid")
    request = request_plan["request_groups"][0]["request"]
    if request["data_format"] != "grib":
        raise ValueError("CAMS decoder requires a GRIB request plan")
    if request["area"] != list(map(float, expected_area)):
        raise ValueError("CAMS request-plan area does not match this decoder")
    return {
        "date": request_plan["run_date"],
        "area": tuple(request["area"]),
        "expected_variables": tuple(request["variable"]),
        "expected_leads": tuple(int(value) for value in request["leadtime_hour"]),
    }


def decode_file(path, *, request_plan, request_plan_sha256):
    options = decoder_plan_options(request_plan, request_plan_sha256, AREA)
    decoder = CamsPointDecoder(**options)
    digest = hashlib.sha256()
    for message in grib_messages(path):
        digest.update(message)
        decoder.decode(message)
    result = decoder.finish()
    result["input_sha256"] = digest.hexdigest()
    result["input_bytes"] = Path(path).stat().st_size
    request = request_plan["request_groups"][0]["request"]
    result["request_plan_sha256"] = request_plan_sha256
    result["request_sha256"] = request_sha256(request)
    result["sources"]["request_plan"] = {
        "sha256": request_plan_sha256,
        "run_date": request_plan["run_date"],
        "request_sha256": result["request_sha256"],
        "metadata_documents": request_plan["metadata_evidence"]["documents"],
    }
    return result


def delivery_report(result, encoded, elapsed_seconds):
    """Separate diagnostics avoid self-referential payload compression sizes."""
    summaries = []
    for variable in result["variables"]:
        rows = variable["hourly"]
        values = [row["value"] for row in rows if row["value"] is not None]
        summaries.append(dict(id=variable["id"], fields=len(rows), units=rows[0]["units"],
                              statuses=dict(Counter(row["status"] for row in rows)),
                              exact_zero_count=sum(value == 0 for value in values),
                              minimum=min(values) if values else None, maximum=max(values) if values else None,
                              first_valid_at_utc=rows[0]["valid_at_utc"], last_valid_at_utc=rows[-1]["valid_at_utc"]))
    compressed = gzip.compress(encoded, mtime=0)
    return dict(schema_version=1, status="offline_cams_decode_and_delivery_measurement_not_acquisition",
                input_sha256=result["input_sha256"], input_bytes=result["input_bytes"],
                request_plan_sha256=result["request_plan_sha256"], request_sha256=result["request_sha256"],
                run_date=result["run_utc"][:10],
                payload_bytes=len(encoded), payload_gzip_bytes=len(compressed),
                payload_sha256=hashlib.sha256(encoded).hexdigest(), payload_gzip_sha256=hashlib.sha256(compressed).hexdigest(),
                elapsed_decode_seconds=elapsed_seconds, decoder_metrics=result["metrics"],
                fields=result["fields"], variables=len(summaries), grid_point=result["grid_point"],
                quality_flag_counts=result["quality_flag_counts"], variable_summary=summaries,
                limitations=["Acquisition queue/processing/download were measured separately.",
                             "One run and one location do not establish model accuracy or operational reliability."])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True, help="NEW JSON, never overwrite")
    parser.add_argument("--inventory", action="store_true", help="Identify raw metadata only; not a complete or validated extraction")
    parser.add_argument("--request-plan", type=Path,
                        help="Required immutable verified plan for extraction; forbidden for inventory")
    parser.add_argument("--report", type=Path, help="Optional NEW separate decode/delivery report; not for inventory")
    args = parser.parse_args()
    if args.input.resolve() == args.output.resolve() or args.output.exists() or not args.output.parent.is_dir():
        parser.error("Output must be a new file distinct from input")
    if args.report and (args.inventory or args.report.resolve() in (args.input.resolve(), args.output.resolve()) or args.report.exists() or not args.report.parent.is_dir()):
        parser.error("Report must be new, distinct and used only with extraction")
    if args.inventory and args.request_plan is not None:
        parser.error("Inventory is explicitly unverified and must not receive a request plan")
    if not args.inventory and args.request_plan is None:
        parser.error("Extraction requires --request-plan")
    started = time.perf_counter()
    if args.inventory:
        result = inventory_file(args.input)
    else:
        try:
            plan, _, plan_hash = load_verified_request_plan(args.request_plan)
        except PublicMetadataError as exc:
            parser.error(str(exc))
        result = decode_file(
            args.input, request_plan=plan, request_plan_sha256=plan_hash
        )
    elapsed = time.perf_counter() - started
    encoded = compact_json(result)
    report = compact_json(delivery_report(result, encoded, elapsed)) if args.report else None
    with args.output.open("xb") as destination:
        destination.write(encoded)
    if report is not None:
        with args.report.open("xb") as destination:
            destination.write(report)
    print(json.dumps(dict(status=result["status"], output_bytes=len(encoded), input_sha256=result["input_sha256"])))


if __name__ == "__main__":
    main()
