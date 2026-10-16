"""Read-only, bounded ICON-2I feasibility probe; NOT an application provider.

Install requests and ECMWF eccodes in an isolated environment, then run this
module. Only anonymous GETs to ItaliaMeteo's documented public download service
are used. No credentials, jobs, schedules, app caches or runtime are touched.

The fixed-message-size shortcut is deliberately experimental: each selected
message must pass GRIB, parameter, level and forecast-time checks. Variable-size
packing fails closed, without downloading the full national-domain file.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser
import json
import math
from pathlib import Path
import re
import time
from urllib.parse import urljoin, urlparse

BASE = "https://meteohub.agenziaitaliameteo.it/nwp/ICON-2I_SURFACE_PRESSURE_LEVELS/"
POINTS = {
    "Pordenone": (45.95689, 12.66051),
    "Trieste": (45.6495, 13.7768),
    "Tarvisio": (46.506, 13.5787),
}
# No RELHUM at 1000 hPa: it is not relative humidity at two metres.
FIELDS = {
    "T_2M": ("heightAboveGround-2", "heightAboveGround", 2, "K"),
    "TD_2M": ("heightAboveGround-2", "heightAboveGround", 2, "K"),
    "U_10M": ("heightAboveGround-10", "heightAboveGround", 10, "m s**-1"),
    "V_10M": ("heightAboveGround-10", "heightAboveGround", 10, "m s**-1"),
    "CLCT": ("surface-0", "surface", 0, "%"),
    "PMSL": ("meanSea-0", "meanSea", 0, "Pa"),
    "TOT_PREC": ("surface-0", "surface", 0, "kg m**-2"),
    "WW": ("surface-0", "surface", 0, None),
}
SHORT_NAMES = {"T_2M": "2t", "TD_2M": "2d", "U_10M": "10u", "V_10M": "10v", "CLCT": "clct", "PMSL": "pmsl", "TOT_PREC": "tp", "WW": "ww"}


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.hrefs = []

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            self.hrefs.extend(v for k, v in attrs if k == "href" and v)


class PublicHTTPError(ValueError):
    """Bounded public-source HTTP failure, without retaining a response or URL."""

    def __init__(self, status, *, operation="source_metadata"):
        if type(status) is not int or not 100 <= status <= 599:
            raise ValueError("Invalid public source HTTP status")
        if operation not in {"source_metadata", "source_range", "source_variable"}:
            raise ValueError("Invalid public source operation")
        self.code = self.http_status = status
        self.retryable = status in {408, 429} or 500 <= status <= 599
        self.weather_diagnostics = {
            "provider": "icon2i", "stage": "source_http", "http_status": status,
            "http_method": "GET", "operation": operation, "retryable": self.retryable,
            "reason_code": "icon_public_http_unexpected_status",
            "error_summary": "ICON public source returned an unexpected HTTP status",
        }
        super().__init__(f"Unexpected HTTP {status}; refusing full-file fallback")


class PublicReader:
    def __init__(self, max_bytes=40 * 1024**2):
        import requests

        self.session = requests.Session()
        self.session.headers.update({"Accept-Encoding": "identity"})
        self.max_bytes = max_bytes
        self.bytes_read = 0
        self.requests = 0

    def get(self, url, start=None, end=None):
        if not url.startswith(BASE) or urlparse(url).hostname != urlparse(BASE).hostname:
            raise ValueError("Only the public ICON-2I directory is permitted")
        limit = 256 * 1024 if start is None else end - start + 1
        if self.bytes_read + limit > self.max_bytes:
            raise ValueError("Probe transfer budget exceeded")
        headers = {} if start is None else {"Range": f"bytes={start}-{end}"}
        self.requests += 1
        with self.session.get(url, headers=headers, stream=True, timeout=30, allow_redirects=False) as response:
            if response.status_code != (200 if start is None else 206):
                raise PublicHTTPError(response.status_code,
                                      operation="source_metadata" if start is None else "source_range")
            total = None
            if start is not None:
                match = re.fullmatch(r"bytes (\d+)-(\d+)/(\d+)", response.headers.get("Content-Range", ""))
                if not match or tuple(map(int, match.groups()[:2])) != (start, end):
                    raise ValueError("Invalid Content-Range")
                total = int(match[3])
            chunks = []
            count = 0
            for chunk in response.iter_content(64 * 1024):
                count += len(chunk)
                self.bytes_read += len(chunk)
                if count > limit or self.bytes_read > self.max_bytes:
                    raise ValueError("Response exceeds transfer budget")
                chunks.append(chunk)
            if start is not None and count != limit:
                raise ValueError("Truncated byte-range response")
            return b"".join(chunks), total

    def links(self, url):
        data, _ = self.get(url)
        parser = Links()
        parser.feed(data.decode("utf-8"))
        return parser.hrefs


def message_length(header):
    if len(header) != 16 or header[:4] != b"GRIB" or header[7] != 2:
        raise ValueError("Expected GRIB edition 2 header")
    length = int.from_bytes(header[8:16], "big")
    if not 20 <= length <= 4 * 1024**2:
        raise ValueError("Unexpected GRIB message size")
    return length


def relative_humidity_from_dewpoint(temperature_c, dewpoint_c):
    """Magnus approximation over water, consistent with BOM's AT vapour law.

    Experimental, not an exact inversion of ICON's native saturation scheme.
    https://www.bom.gov.au/info/thermal_stress/
    Reject grossly inconsistent inputs instead of silently clipping them.
    """
    if not all(math.isfinite(v) and -100 <= v <= 70 for v in (temperature_c, dewpoint_c)):
        raise ValueError("Invalid temperature/dewpoint")
    rh = 100 * math.exp(17.27 * dewpoint_c / (237.7 + dewpoint_c) - 17.27 * temperature_c / (237.7 + temperature_c))
    if not 0 <= rh <= 100:
        raise ValueError("Dewpoint exceeds temperature; no silent saturation clipping")
    return rh


def decode_message(data, field, expected_run, expected_step):
    import eccodes as ec

    handle = ec.codes_new_from_message(data)
    try:
        ec.codes_set(handle, "stepUnits", 1)  # Normalize ecCodes time keys to hours.
        keys = ("shortName", "paramId", "name", "units", "typeOfLevel", "level", "dataDate", "dataTime", "validityDate", "validityTime", "startStep", "endStep", "stepUnits", "stepType", "gridType", "numberOfPoints", "Ni", "Nj", "uvRelativeToGrid", "iDirectionIncrementInDegrees", "jDirectionIncrementInDegrees")
        metadata = {key: ec.codes_get(handle, key) for key in keys}
        if metadata["shortName"] != SHORT_NAMES[field]:
            raise ValueError(f"Unexpected parameter for {field}: {metadata}")
        _, level_type, level, units = FIELDS[field]
        if metadata["typeOfLevel"] != level_type or metadata["level"] != level:
            raise ValueError(f"Wrong vertical level for {field}: {metadata}")
        if units and metadata["units"] != units:
            raise ValueError(f"Unexpected units for {field}: {metadata['units']}")
        run = f"{metadata['dataDate']}{metadata['dataTime']:04d}"
        if run != expected_run + "00" or metadata["endStep"] != expected_step or str(metadata["stepUnits"]) != "1":
            raise ValueError(f"Run/lead mismatch for {field}: {metadata}")
        if field != "TOT_PREC" and metadata["stepType"] != "instant":
            raise ValueError(f"Unexpected time processing for {field}")
        if field == "TOT_PREC" and (metadata["stepType"] != "accum" or metadata["startStep"] != 0):
            raise ValueError("Rain is not an accumulation since model start")
        points = {}
        for name, (lat, lon) in POINTS.items():
            nearest = ec.codes_grib_find_nearest(handle, lat, lon, npoints=1)[0]
            if not math.isfinite(nearest["value"]) or nearest["value"] == ec.codes_get(handle, "missingValue") or nearest["distance"] > 5:
                raise ValueError(f"Missing value or excessive grid distance for {name}")
            points[name] = {key: round(nearest[key], 6) for key in ("lat", "lon", "distance", "value")}
        return {"metadata": metadata, "points": points}
    finally:
        ec.codes_release(handle)


def run_probe(run=None):
    reader = PublicReader()
    started = time.monotonic()
    runs = sorted(link.rstrip("/") for link in reader.links(BASE) if re.fullmatch(r"\d{10}/", link))
    if not runs or run is not None and run not in runs:
        raise ValueError("Requested run not present in public listing")
    run = run or runs[-1]
    run_time = datetime.strptime(run, "%Y%m%d%H").replace(tzinfo=timezone.utc)
    now = datetime.now(timezone.utc)
    next_hour = now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
    first_step = max(0, int((next_hour - run_time).total_seconds() / 3600))
    steps = [first_step, first_step + 24, first_step + 48]
    if steps[-1] > 72:
        raise ValueError("Latest available run cannot cover the next 48 hours")
    report = {"status": "isolated_sample_not_production", "accessed_at_utc": now.isoformat(), "run_utc": run_time.isoformat(), "forecast_steps_hours": steps, "requested_points": POINTS, "fields": {}}
    for field, (suffix, _, _, _) in FIELDS.items():
        directory = f"{BASE}{run}/{field}/"
        files = [link for link in reader.links(directory) if link.endswith(f"_{suffix}.grib")]
        if len(files) != 1:
            raise ValueError(f"No unambiguous public file for {field}")
        url = urljoin(directory, files[0])
        header, total = reader.get(url, 0, 15)
        size = message_length(header)
        # An all-zero initial rain field is packed into a short message. Allow
        # that special first message, but verify every sampled message/time.
        first_size = size
        if total != 73 * size:
            second_header, second_total = reader.get(url, size, size + 15)
            size = message_length(second_header)
            if second_total != total or total != first_size + 72 * size:
                raise ValueError("0..72 hourly layout not confirmed; stop probe")
        samples = []
        for step in steps:
            offset = 0 if step == 0 else first_size + (step - 1) * size
            selected_size = first_size if step == 0 else size
            data, current_total = reader.get(url, offset, offset + selected_size - 1)
            if current_total != total or message_length(data[:16]) != len(data) or data[-4:] != b"7777":
                raise ValueError("File changed or variable-length message layout")
            samples.append(decode_message(data, field, run, step))
        report["fields"][field] = {"url": url, "whole_file_bytes": total, "first_message_bytes": first_size, "message_bytes": size, "samples": samples}
        print(f"Verified {field}: {len(samples)} forecast instants, {len(POINTS)} locations", flush=True)
    # Import only this sibling experiment, never the application's weather engine.
    from thermal_comfort import calculate_thermal_comfort
    from dataclasses import asdict

    report["derived_points"] = []
    for index, step in enumerate(steps):
        for name in POINTS:
            grids = {(report["fields"][field]["samples"][index]["points"][name]["lat"], report["fields"][field]["samples"][index]["points"][name]["lon"]) for field in FIELDS}
            if len(grids) != 1:
                raise ValueError("Selected fields do not use the same nearest grid point")
            if any(report["fields"][field]["samples"][index]["metadata"]["uvRelativeToGrid"] != 0 for field in ("U_10M", "V_10M")):
                raise ValueError("Wind is grid-relative; geographic direction cannot be used without rotation")
            raw = {field: report["fields"][field]["samples"][index]["points"][name]["value"] for field in FIELDS}
            t, td = raw["T_2M"] - 273.15, raw["TD_2M"] - 273.15
            rh = relative_humidity_from_dewpoint(t, td)
            wind = math.hypot(raw["U_10M"], raw["V_10M"])
            report["derived_points"].append({"location": name, "valid_at_utc": (run_time + timedelta(hours=step)).isoformat(), "temperature_c": round(t, 2), "dewpoint_c": round(td, 2), "relative_humidity_derived_pct": round(rh, 2), "wind_10m_m_s": round(wind, 2), "wind_from_degrees": round((270 - math.degrees(math.atan2(raw["V_10M"], raw["U_10M"]))) % 360, 1) if wind > 0 else None, "pressure_msl_hpa": round(raw["PMSL"] / 100, 2), "cloud_cover_pct": raw["CLCT"], "precipitation_since_run_kg_m2": raw["TOT_PREC"], "weather_code_raw": raw["WW"], "thermal": asdict(calculate_thermal_comfort(temperature_c=t, relative_humidity_pct=rh, wind_10m_m_s=wind))})
    report.update({"downloaded_bytes": reader.bytes_read, "http_get_requests": reader.requests, "elapsed_seconds": round(time.monotonic() - started, 2), "sum_whole_file_bytes": sum(f["whole_file_bytes"] for f in report["fields"].values()), "limits": ["Only three forecast instants were decoded: this does not prove complete hourly continuity or forecast accuracy.", "Nearest grid point; no elevation correction, interpolation or land/sea mask.", "RH is an approximation derived from T2m and Td2m, not a native RH2m field.", "Rain is an accumulated quantity: do not display it as hourly rain without interval differencing.", "WW is raw and not yet mapped to application icons; grid-relative wind orientation must be verified before production.", "No application endpoint, hero, official bulletin, alert, cache or deployment was changed."]})
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", help="Optional UTC run YYYYMMDDHH, otherwise latest listed")
    parser.add_argument("--output", type=Path, help="New JSON result path (will never overwrite)")
    args = parser.parse_args()
    result = run_probe(args.run)
    encoded = json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False)
    if args.output:
        with args.output.open("x", encoding="utf-8") as destination:
            destination.write(encoded + "\n")
        print(f"Result: {args.output}")
    else:
        print(encoded)
