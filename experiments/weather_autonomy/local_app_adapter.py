"""DEV-only API-shaped ICON/CAMS adapter over immutable local snapshots.

No app imports, network, geocoding, credentials, provider fallback or mutation.
The caller controls localhost-only routing and retains official OSMER products.
All generated responses carry the original run/generation/validity timestamps.
"""

from __future__ import annotations

from bisect import bisect_right
from collections import defaultdict
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import calendar
from functools import lru_cache
import hashlib
import json
import math
from pathlib import Path
import re
import unicodedata
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from decode_cams import EXPECTED_VARIABLES
from pilot_policy import assess_window

SOURCE = "icon2i_local_pilot"
MODE = "local_archived_snapshot"
MAX_INPUT = 64 * 1024**2
POLLENS = {"alder_pollen": "ontano", "birch_pollen": "betulla", "grass_pollen": "graminacee",
           "mugwort_pollen": "artemisia", "olive_pollen": "olivo", "ragweed_pollen": "ambrosia"}
NUMERIC_FIELDS = ("temperature_c", "relative_humidity_pct", "apparent_temperature_c", "pressure_msl_hpa",
                  "wind_m_s", "wind_from_degrees", "wind_gust_m_s", "cloud_cover_pct",
                  "precipitation_previous_hour_mm", "rain_previous_hour_mm", "convective_rain_previous_hour_mm",
                  "snow_water_equivalent_previous_hour_mm", "graupel_water_equivalent_previous_hour_mm",
                  "precipitation_probability_pct", "visibility_m")
GAPS = ["precipitation_probability", "visibility", "snow_depth_cm", "showers_amount",
        "day_night_astronomy_not_in_archive", "station_observation", "local_accuracy_validation"]


class LocalSnapshotUnavailable(RuntimeError):
    """Fail visible; the caller should return 503, never Open-Meteo fallback."""


def utc(value):
    if not isinstance(value, str):
        raise ValueError("Expected explicit UTC timestamp")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() != timedelta(0):
        raise ValueError("Timestamp must be explicit UTC")
    return parsed.astimezone(timezone.utc)


def iso(value):
    return value.isoformat().replace("+00:00", "Z")


def numeric_or_null(value):
    if value is not None and (isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value)):
        raise ValueError("Expected finite number or explicit null")
    return value


def normalize(value):
    text = unicodedata.normalize("NFKD", str(value)).casefold()
    return re.sub(r"[^a-z0-9]+", "-", "".join(c for c in text if not unicodedata.combining(c))).strip("-")


def distance_km(lat1, lon1, lat2, lon2):
    p1, p2 = math.radians(lat1), math.radians(lat2)
    a = math.sin((p2-p1)/2)**2 + math.cos(p1)*math.cos(p2)*math.sin(math.radians(lon2-lon1)/2)**2
    return 6371.0 * 2 * math.asin(min(1, math.sqrt(a)))


@lru_cache(maxsize=1)
def _rome_zone():
    try:
        return ZoneInfo("Europe/Rome")
    except ZoneInfoNotFoundError:
        return None


def rome_time(value):
    """UTC→Rome; modern EU fallback if Windows lacks the IANA database.

    No local/ambiguous timestamp is accepted. The UTC switch is 01:00 on the
    last Sunday of March/October, as in the existing app timezone helper.
    """
    zone = _rome_zone()
    if zone is not None:
        return value.astimezone(zone)
    else:
        def last_sunday(month):
            day = datetime(value.year, month, calendar.monthrange(value.year, month)[1], 1, tzinfo=timezone.utc)
            return day - timedelta(days=(day.weekday()+1) % 7)
        summer = last_sunday(3) <= value < last_sunday(10)
        return value.astimezone(timezone(timedelta(hours=2 if summer else 1), "CEST" if summer else "CET"))


def canonical_condition(condition):
    """Use native identity only for an explicit broad presentation mapping.

    No WMO/Open-Meteo code is emitted. In particular, native 96 cannot promise
    hail: its conservative icon category is simply thunderstorm.
    """
    if condition.get("status") != "valid":
        return "Condizione meteo non disponibile"
    code = condition.get("code")
    mapping = {0: "Sereno", 1: "Poco nuvoloso", 2: "Parzialmente nuvoloso", 3: "Coperto",
               45: "Nebbia", 48: "Nebbia", 51: "Pioviggine", 53: "Pioviggine", 55: "Pioviggine",
               56: "Pioggia congelata", 57: "Pioggia congelata", 61: "Pioggia", 63: "Pioggia", 65: "Pioggia",
               66: "Pioggia congelata", 67: "Pioggia congelata", 71: "Neve", 73: "Neve", 75: "Neve", 77: "Neve",
               80: "Rovesci", 81: "Rovesci", 82: "Rovesci", 85: "Neve", 86: "Neve", 95: "Temporale", 96: "Temporale"}
    return mapping.get(code, "Condizione meteo non disponibile")


def read_snapshot(path):
    path = Path(path)
    if not path.is_file() or not 1 <= path.stat().st_size <= MAX_INPUT:
        raise ValueError("Snapshot missing or larger than 64 MiB")
    raw = path.read_bytes()
    return json.loads(raw), dict(filename=path.name, bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())


class LocalSnapshotAdapter:
    def __init__(self, icon_path, cams_path, now_provider=None):
        self._now_provider = now_provider or (lambda: datetime.now(timezone.utc))
        self.icon, self.icon_evidence = read_snapshot(icon_path)
        self.cams, self.cams_evidence = read_snapshot(cams_path)
        if self.icon.get("schema_version") != 1 or self.icon.get("status") != "partial_pilot_not_production" or self.icon.get("validation", {}).get("usable") is not True:
            raise ValueError("Expected the verified complete diagnostic ICON snapshot")
        if self.cams.get("schema_version") != 2 or self.cams.get("kind") != "cams_region_point_extraction":
            raise ValueError("Expected the verified regional CAMS shared-cell snapshot")
        icon_source = self.icon.get("sources", {}).get("icon", {})
        if icon_source.get("status") != "acquired_and_decoded" or icon_source.get("run_utc") != self.icon["run_utc"]:
            raise ValueError("Unverified ICON source/run")
        for value in (self.icon["run_utc"], self.icon["generated_at_utc"], self.cams["run_utc"], self.cams["generated_at_utc"]):
            utc(value)
        self.towns = {town["id"]: town for town in self.icon["municipalities"]}
        self.cams_towns = {town["id"]: town for town in self.cams["municipalities"]}
        if len(self.icon["municipalities"]) != 215 or len(self.cams["municipalities"]) != 215 or len(self.towns) != 215 or set(self.towns) != set(self.cams_towns):
            raise ValueError("Expected the same 215 unique municipalities in both snapshots")
        self.cells = {cell["id"]: cell for cell in self.cams["cells"]}
        if len(self.cells) != len(self.cams["cells"]):
            raise ValueError("Duplicate CAMS cells")
        self.variables = {variable["id"]: variable for variable in self.cams["variables"]}
        if len(self.cams["variables"]) != 28 or set(self.variables) != set(EXPECTED_VARIABLES):
            raise ValueError("Expected all 28 CAMS variables")
        self.aliases = {}
        first = next(iter(self.towns.values()))
        self.icon_times = [utc(row["valid_at_utc"]) for row in first["hourly"]]
        self.cams_times = [utc(value) for value in self.cams["times_utc"]]
        for times, count, run in ((self.icon_times, 73, self.icon["run_utc"]), (self.cams_times, 97, self.cams["run_utc"])):
            if len(times) != count or times[0] != utc(run) or any(b-a != timedelta(hours=1) for a, b in zip(times, times[1:])):
                raise ValueError("Incomplete native hourly snapshot timeline")
        for tid, town in self.towns.items():
            cams_town = self.cams_towns[tid]
            if [utc(row["valid_at_utc"]) for row in town["hourly"]] != self.icon_times:
                raise ValueError("Municipality ICON timeline differs")
            for key in ("latitude", "longitude"):
                numeric_or_null(town[key])
                if town[key] is None or abs(town[key]-cams_town[key]) > 1e-6:
                    raise ValueError("Municipality coordinates differ across providers")
            if cams_town["cell_id"] not in self.cells:
                raise ValueError("CAMS municipality references an unknown cell")
            for alias in (normalize(tid), normalize(town["name"])):
                if alias in self.aliases and self.aliases[alias] != tid:
                    raise ValueError("Ambiguous municipality name")
                self.aliases[alias] = tid
            for row in town["hourly"]:
                for field in NUMERIC_FIELDS:
                    numeric_or_null(row[field])
                if not isinstance(row["quality_flags"], list) or not all(isinstance(f, str) for f in row["quality_flags"]):
                    raise ValueError("Invalid ICON quality flags")
                native = row["condition"]
                numeric_or_null(native["code"])
                if native["code"] is not None and int(native["code"]) != native["code"]:
                    raise ValueError("Native weather code must be integer or null")
                if native["status"] not in ("valid", "unknown", "invalid") or not isinstance(native["label"], str):
                    raise ValueError("Invalid native weather interpretation")
        for cell in self.cells.values():
            for vid in self.variables:
                variable = self.variables[vid]
                expected_unit = "grains/m3" if vid in POLLENS else "ug/m3"
                if variable["units"] != expected_unit or variable["source_units"] != ("grains/m3" if vid in POLLENS else "kg/m3"):
                    raise ValueError("CAMS concentration unit mismatch")
                if not isinstance(variable["quality_flags"], list) or not all(isinstance(f, str) for f in variable["quality_flags"]):
                    raise ValueError("Invalid CAMS variable flags")
                for field in ("values", "raw_values"):
                    if len(cell[field][vid]) != 97:
                        raise ValueError("Incomplete CAMS variable timeline")
                    for value in cell[field][vid]:
                        numeric_or_null(value)
                        if field == "values" and value is not None and value < 0:
                            raise ValueError("Negative CAMS concentrations must remain flagged nulls")
        self._icon_times_text = [iso(t) for t in self.icon_times]
        self._cams_times_text = [iso(t) for t in self.cams_times]

    def _now(self):
        now = self._now_provider()
        if not isinstance(now, datetime) or now.tzinfo is None:
            raise LocalSnapshotUnavailable("local_snapshot_clock_requires_aware_datetime")
        return now.astimezone(timezone.utc)

    def metadata(self):
        now = self._now()
        icon = assess_window(self.icon["run_utc"], self._icon_times_text, iso(now))
        cams = assess_window(self.cams["run_utc"], self._cams_times_text, iso(now), max_age_hours=24)
        return dict(mode=MODE, primary_source=SOURCE, usable=icon["usable"] and cams["usable"],
                    icon=dict(icon, run_utc=self.icon["run_utc"], generated_at_utc=self.icon["generated_at_utc"], **self.icon_evidence),
                    cams=dict(cams, run_utc=self.cams["run_utc"], generated_at_utc=self.cams["generated_at_utc"], **self.cams_evidence),
                    municipalities=215, cams_variables=28, capability_gaps=list(GAPS))

    def _context(self, city, lat, lon):
        tid = self.aliases.get(normalize(city))
        if tid is None:
            raise LocalSnapshotUnavailable("local_snapshot_unknown_municipality")
        town = self.towns[tid]
        requested_distance = None
        if (lat is None) != (lon is None):
            raise LocalSnapshotUnavailable("local_snapshot_incomplete_coordinates")
        if lat is not None:
            try:
                numeric_or_null(lat)
                numeric_or_null(lon)
            except ValueError as exc:
                raise LocalSnapshotUnavailable("local_snapshot_invalid_coordinates") from exc
            if not 45 <= lat <= 47 or not 12 <= lon <= 14.5:
                raise LocalSnapshotUnavailable("local_snapshot_coordinates_outside_fvg")
            requested_distance = distance_km(lat, lon, town["latitude"], town["longitude"])
            if requested_distance > 10:
                raise LocalSnapshotUnavailable("local_snapshot_coordinates_do_not_match_municipality")
        now = self._now()
        icon_check = assess_window(self.icon["run_utc"], self._icon_times_text, iso(now))
        cams_check = assess_window(self.cams["run_utc"], self._cams_times_text, iso(now), max_age_hours=24)
        if not icon_check["usable"] or not cams_check["usable"]:
            reason = icon_check["reason"] if not icon_check["usable"] else cams_check["reason"]
            raise LocalSnapshotUnavailable(f"local_snapshot_unavailable:{reason}")
        index, cams_index = bisect_right(self.icon_times, now)-1, bisect_right(self.cams_times, now)-1
        if index < 0 or cams_index < 0 or now-self.icon_times[index] >= timedelta(hours=1) or now-self.cams_times[cams_index] >= timedelta(hours=1):
            raise LocalSnapshotUnavailable("local_snapshot_current_hour_unavailable")
        return town, now, index, cams_index, icon_check, cams_check, requested_distance

    def _source(self, town):
        return dict(active=SOURCE, primary_source=SOURCE, mode=MODE, label="ItaliaMeteo ICON-2I · pilota locale",
                    fallback_used=None, icon=deepcopy(self.icon["sources"]["icon"]), cams=deepcopy(self.cams["sources"]),
                    icon_snapshot=dict(self.icon_evidence), cams_snapshot=dict(self.cams_evidence),
                    municipality_id=town["id"], current_policy="local-icon-cams-snapshot-no-provider-fallback")

    def _quality(self, town, row, check, cams_index, requested_distance):
        native = row["condition"]
        return dict(mode=MODE, status=check["status"], certainty="experimental_model", source=SOURCE,
                    run_utc=self.icon["run_utc"], generated_at_utc=self.icon["generated_at_utc"],
                    valid_at_utc=row["valid_at_utc"], coverage_hours=check["coverage_hours"], run_age_hours=check["run_age_hours"],
                    native_weather_code=native["code"], native_condition_label=native["label"], native_condition_status=native["status"],
                    native_condition_period="previous_hour", cams_run_utc=self.cams["run_utc"],
                    cams_valid_at_utc=self._cams_times_text[cams_index], municipality_id=town["id"],
                    location_scope="Precomputed catalog municipality point, not the requested GPS point or a station sensor",
                    catalog_point=dict(latitude=town["latitude"], longitude=town["longitude"]),
                    requested_coordinate_distance_km=requested_distance, grid_point=dict(town["grid_point"]),
                    capability_gaps=list(GAPS), flags=list(row["quality_flags"]),
                    precipitation_encoding=deepcopy(row.get("precipitation_encoding", {})),
                    snowfall_water_equivalent_mm=row["snow_water_equivalent_previous_hour_mm"],
                    graupel_water_equivalent_mm=row["graupel_water_equivalent_previous_hour_mm"])

    def _hour(self, row):
        def kmh(value):
            return value * 3.6 if value is not None else None
        native = row["condition"]
        return dict(time=row["valid_at_utc"], temperature=row["temperature_c"], condition=canonical_condition(native),
                    weathercode=None, primary_source=SOURCE, feels_like=row["apparent_temperature_c"],
                    humidity=row["relative_humidity_pct"], pressure=row["pressure_msl_hpa"], cloud_cover=row["cloud_cover_pct"],
                    wind_speed=kmh(row["wind_m_s"]), wind_direction=row["wind_from_degrees"], wind_gusts=kmh(row["wind_gust_m_s"]),
                    precipitation=row["precipitation_previous_hour_mm"], rain=row["rain_previous_hour_mm"],
                    showers=None, snowfall=None, precipitation_probability=None, visibility=None, is_day=None,
                    snowfall_water_equivalent_mm=row["snow_water_equivalent_previous_hour_mm"],
                    graupel_water_equivalent_mm=row["graupel_water_equivalent_previous_hour_mm"],
                    quality_flags=list(row["quality_flags"]),
                    data_quality=dict(mode=MODE, native_weather_code=native["code"], native_condition_label=native["label"],
                                      native_condition_status=native["status"], valid_at_utc=row["valid_at_utc"]))

    def _pollen(self, tid, position, check):
        cell = self.cells[self.cams_towns[tid]["cell_id"]]
        records = []
        for vid, variable in self.variables.items():
            records.append(dict(id=vid, value=cell["values"][vid][position], raw_value=cell["raw_values"][vid][position],
                                units=variable["units"], source_units=variable["source_units"],
                                quality_flags=list(variable["quality_flags"]) + list(cell["quality_flags"].get(vid, {}).get(str(position), []))))
        return dict(status="experimental_model_snapshot", freshness=check["status"],
                    summary="Previsione pollini CAMS · sperimentale", level=None, main=None,
                    values={name: cell["values"][vid][position] for vid, name in POLLENS.items()}, units="grains/m3",
                    run_utc=self.cams["run_utc"], generated_at_utc=self.cams["generated_at_utc"], valid_at_utc=self._cams_times_text[position],
                    source="cams_european_ensemble", all_variables=records,
                    grid_point={k: cell[k] for k in ("lat", "lon", "grid_index")},
                    source_evidence=dict(self.cams_evidence), attribution=self.cams["attribution"],
                    health_classification=None, note="Concentrazioni previste; nessuna soglia sanitaria o classe allergica introdotta dal pilota")

    def current(self, city, lat=None, lon=None):
        town, now, index, cams_index, check, cams_check, requested_distance = self._context(city, lat, lon)
        row = town["hourly"][index]
        sample = self._hour(row)
        floor = now.replace(minute=0, second=0, microsecond=0)
        ceiling = floor if now == floor else floor + timedelta(hours=1)
        horizon = ceiling + timedelta(hours=48)
        hourly = [self._hour(r) for r, t in zip(town["hourly"], self.icon_times) if self.icon_times[index] <= t <= horizon]
        pollen = self._pollen(town["id"], cams_index, cams_check)
        result = {key: sample[key] for key in ("temperature", "condition", "weathercode", "wind_speed", "wind_direction", "wind_gusts", "cloud_cover", "precipitation", "rain", "showers", "snowfall", "humidity", "pressure", "feels_like", "visibility", "is_day")}
        result.update(city=town["name"], phrase="", is_bora=False, pop=None, sunrise=None, sunset=None,
                      hourly_next_12h=hourly[:12], hourly_forecast=hourly, pollen=pollen["summary"], pollen_data=pollen,
                      source=self._source(town), station=None, official=None, fallback_used=None, primary_source=SOURCE,
                      model_support=dict(open_meteo=False, icon2i=True, cams=True, hourly=True, daily=True),
                      cache=dict(status=check["status"], mode=MODE, generated_at=self.icon["generated_at_utc"], ttl_seconds=0),
                      data_quality=self._quality(town, row, check, cams_index, requested_distance))
        return result

    def forecast(self, city, lat=None, lon=None):
        town, now, index, cams_index, check, _, requested_distance = self._context(city, lat, lon)
        grouped = defaultdict(list)
        today = rome_time(now).date().isoformat()
        for row, timestamp in zip(town["hourly"], self.icon_times):
            local = rome_time(timestamp)
            if local.date().isoformat() >= today:
                grouped[local.date().isoformat()].append((row, local))
        forecast = []
        for day, entries in sorted(grouped.items()):
            temperatures = [row["temperature_c"] for row, _ in entries]
            representative, _ = min(entries, key=lambda pair: abs(pair[1].hour - 12))
            # Partial-day extrema stay diagnostic-only instead of masquerading
            # as complete daily minimum/maximum temperatures.
            complete = entries[0][1].hour == 0 and entries[-1][1].hour == 23 and len(entries) in (23, 24, 25)
            numeric = [v for v in temperatures if v is not None]
            forecast.append(dict(date=day, condition=canonical_condition(representative["condition"]), weathercode=None,
                                 min_temp=min(numeric) if complete and len(numeric) == len(entries) else None,
                                 max_temp=max(numeric) if complete and len(numeric) == len(entries) else None,
                                 sampled_min_temp=min(numeric) if numeric else None, sampled_max_temp=max(numeric) if numeric else None,
                                 source_hours=len(entries), partial_day=not complete,
                                 condition_policy="Nearest available local-noon native condition; not a daily severity aggregate",
                                 extrema_policy="Hourly sampled extrema; partial days are not presented as full-day extrema",
                                 primary_source=SOURCE, official_text="", emission="",
                                 data_quality=dict(mode=MODE, native_weather_code=representative["condition"]["code"],
                                                   native_condition_label=representative["condition"]["label"], native_condition_status=representative["condition"]["status"])))
        if not forecast:
            raise LocalSnapshotUnavailable("local_snapshot_daily_forecast_unavailable")
        return dict(city=town["name"], forecast=forecast,
                    daily=dict(time=[d["date"] for d in forecast], temperature_2m_min=[d["min_temp"] for d in forecast],
                               temperature_2m_max=[d["max_temp"] for d in forecast], weathercode=[None]*len(forecast), weather_code=[None]*len(forecast)),
                    official=None, osmer_structured=None, source=self._source(town), fallback_used=None, primary_source=SOURCE,
                    model_support=dict(open_meteo=False, icon2i=True, cams=True, hourly=True, daily=True),
                    cache=dict(status=check["status"], mode=MODE, generated_at=self.icon["generated_at_utc"], ttl_seconds=0),
                    data_quality=self._quality(town, town["hourly"][index], check, cams_index, requested_distance))
