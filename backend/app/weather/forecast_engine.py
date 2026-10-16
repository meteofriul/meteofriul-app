"""OSMER forecast engine extracted from the proven Meteo Friul pipeline.

This module intentionally contains only the dependency closure required by
get_real_forecast. Push, cron, event, and Android concerns remain outside the
UI3 weather boundary.
"""

from __future__ import annotations

import json
import math
import os
import re
import unicodedata
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from html import unescape
from pathlib import Path
from urllib.parse import urljoin

import requests

from app.infrastructure.open_meteo_policy import (
    open_meteo_enabled,
    require_open_meteo_enabled,
)
from app.services.fvg_geography import get_default_fvg_geography_catalog

try:
    from zoneinfo import ZoneInfo
except ImportError:  # pragma: no cover - Python 3.9+ always provides it.
    ZoneInfo = None

from . import osmer_interpreter, parser_osmer


try:
    OSMER_STRUCTURED_LOOKBACK_DAYS = max(
        1,
        min(int(os.getenv("OSMER_STRUCTURED_LOOKBACK_DAYS", "3")), 7),
    )
except ValueError:
    OSMER_STRUCTURED_LOOKBACK_DAYS = 3

try:
    OSMER_STRUCTURED_LOOKAHEAD_DAYS = max(
        0,
        min(int(os.getenv("OSMER_STRUCTURED_LOOKAHEAD_DAYS", "2")), 4),
    )
except ValueError:
    OSMER_STRUCTURED_LOOKAHEAD_DAYS = 2

OPEN_METEO_FORECAST_URL = "https://api.open-meteo.com/v1/forecast"

OPEN_METEO_GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search"

OSMER_BASE_URL = "https://www.meteo.fvg.it"

OSMER_DATA_URL = "https://www.osmer.fvg.it/dati.php"

OSMER_DEV_URL = "https://dev.meteo.fvg.it/"

CACHE_TTL = 600

WEATHER_FORECAST_CACHE_TTL = 30 * 60

WEATHER_STALE_TTL = 60 * 60

OPEN_METEO_ERROR_CACHE_TTL = 2 * 60

WEATHER_PIPELINE_VERSION = "osmer-resolver-v4"

OSMER_CACHE_TTL = 30 * 60

HTTP_USER_AGENT = "MeteoFriul/3.0 (+https://meteofriul.it)"

WEATHER_REQUEST_TIMEOUT = 7

WEATHER_SUPPORT_TIMEOUT = 7

forecast_cache = {}

open_meteo_raw_cache = {}

open_meteo_error_cache = {}

osmer_cache = {}

def get_from_cache(cache, key, ttl=CACHE_TTL):
    entry = cache.get(key)
    if not entry:
        return None

    data, timestamp = entry

    if datetime.now() - timestamp > timedelta(seconds=ttl):
        cache.pop(key, None)
        return None

    return data

def get_stale_from_cache(cache, key, ttl):
    entry = cache.get(key)

    if not entry:
        return None

    data, timestamp = entry
    if timestamp is None:
        cache.pop(key, None)
        return None

    age = (datetime.now() - timestamp).total_seconds()

    if age > ttl:
        return None

    return data

def set_cache(cache, key, data):
    cache[key] = (data, datetime.now())

def add_data_quality(data: dict, certainty: str, status: str = "fresh", source: str = None):
    if not isinstance(data, dict):
        return data

    enriched = dict(data)
    enriched["data_quality"] = {
        "certainty": certainty,
        "status": status,
        "source": source or (enriched.get("source") or {}).get("active"),
        "generated_at": datetime.now().isoformat(),
    }
    return enriched

def make_cache_key(*parts):
    return "|".join(str(part).strip().lower() for part in parts)

def normalize_optional_float(value):
    if value is None or hasattr(value, "default"):
        return None

    try:
        return float(value)
    except (TypeError, ValueError):
        return None

def normalize_place_name(value: str) -> str:
    text = unicodedata.normalize("NFKD", str(value or "").lower())
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", text).strip()

CITY_COORDS = {
    "Pordenone": {"lat": 45.9567, "lon": 12.6605},
    "Cordenons": {"lat": 45.9836, "lon": 12.7004},
    "Udine": {"lat": 46.0619, "lon": 13.2378},
    "Trieste": {"lat": 45.6495, "lon": 13.7768},
    "Gorizia": {"lat": 45.9402, "lon": 13.6202},
    "Lignano": {"lat": 45.6792, "lon": 13.1114},
    "Lignano Sabbiadoro": {"lat": 45.6792, "lon": 13.1114},
    "Piancavallo": {"lat": 46.1081, "lon": 12.5186},
    "Tarvisio": {"lat": 46.5050, "lon": 13.5786},
    "Valvasone Arzene": {"lat": 45.99648, "lon": 12.85846},
}


def _load_fvg_municipality_coords() -> dict[str, dict[str, float]]:
    catalog_path = Path(__file__).resolve().parents[1] / "data" / "fvg_municipalities.json"
    payload = json.loads(catalog_path.read_text(encoding="utf-8"))
    municipalities = payload.get("municipalities") or []
    return {
        normalize_place_name(record.get("name")): {
            "lat": float(record["latitude"]),
            "lon": float(record["longitude"]),
        }
        for record in municipalities
        if record.get("name")
    }


FVG_MUNICIPALITY_COORDS = _load_fvg_municipality_coords()

FVG_CITY_NAMES = {
    normalize_place_name(name)
    for name in [
        "Adegliacco",
        "Aviano",
        "Barcis",
        "Cervignano del Friuli",
        "Cividale del Friuli",
        "Codroipo",
        "Cordenons",
        "Fagagna",
        "Forni di Sopra",
        "Gemona del Friuli",
        "Gorizia",
        "Grado",
        "Lignano",
        "Lignano Sabbiadoro",
        "Maniago",
        "Monfalcone",
        "Palmanova",
        "Piancavallo",
        "Pordenone",
        "Sacile",
        "San Daniele del Friuli",
        "San Vito al Tagliamento",
        "San Vito al Tgl.",
        "Sappada",
        "Tarvisio",
        "Tolmezzo",
        "Trieste",
        "Udine",
    ]
}

FVG_BOUNDS = {
    "lat_min": 45.55,
    "lat_max": 46.65,
    "lon_min": 12.30,
    "lon_max": 14.00,
}

OPEN_METEO_SOURCE = {
    "id": "open_meteo",
    "name": "Open-Meteo",
    "type": "fallback_model_api",
    "url": "https://open-meteo.com/",
}

OSMER_SOURCE = {
    "id": "arpa_fvg_osmer",
    "name": "ARPA FVG OSMER",
    "type": "primary_regional_source",
    "url": OSMER_BASE_URL,
}

OSMER_STATION_ALIASES = {
    "udine": ["Udine"],
    "pordenone": ["Pordenone"],
    "gorizia": ["Gorizia"],
    "trieste": ["Trieste"],
    "lignano": ["Lignano S."],
    "tarvisio": ["Tarvisio"],
    "claut": ["Claut"],
    "barcis": ["Barcis"],
    "codroipo": ["Codroipo"],
    "gemona": ["Gemona del F."],
    "tolmezzo": ["Tolmezzo"],
    "cividale": ["Cividale del F."],
    "cervignano del friuli": ["Cervignano del F."],
    "grado": ["Grado"],
}

OSMER_STATION_REFERENCES = [
    {"name": "Udine", "aliases": ["Udine"], "lat": 46.0619, "lon": 13.2378, "area": "friuli_centrale"},
    {"name": "Pordenone", "aliases": ["Pordenone"], "lat": 45.9567, "lon": 12.6605, "area": "pordenonese"},
    {"name": "Gorizia", "aliases": ["Gorizia"], "lat": 45.9402, "lon": 13.6202, "area": "isontino"},
    {"name": "Trieste", "aliases": ["Trieste"], "lat": 45.6495, "lon": 13.7768, "area": "triestino"},
    {"name": "Lignano S.", "aliases": ["Lignano S."], "lat": 45.6792, "lon": 13.1114, "area": "laguna_ovest"},
    {"name": "Tarvisio", "aliases": ["Tarvisio"], "lat": 46.5050, "lon": 13.5786, "area": "canal_del_ferro_valcanale"},
    {"name": "Claut", "aliases": ["Claut"], "lat": 46.2683, "lon": 12.5158, "area": "dolomiti_friulane"},
    {"name": "Barcis", "aliases": ["Barcis"], "lat": 46.1906, "lon": 12.5608, "area": "valcellina"},
    {"name": "Codroipo", "aliases": ["Codroipo"], "lat": 45.9637, "lon": 12.9797, "area": "medio_friuli"},
    {"name": "Gemona del F.", "aliases": ["Gemona del F."], "lat": 46.2775, "lon": 13.1403, "area": "pedemontana_udinese"},
    {"name": "Tolmezzo", "aliases": ["Tolmezzo"], "lat": 46.4067, "lon": 13.0158, "area": "carnia"},
    {"name": "Cividale del F.", "aliases": ["Cividale del F."], "lat": 46.0919, "lon": 13.4322, "area": "valli_del_natisone"},
    {"name": "Cervignano del F.", "aliases": ["Cervignano del F."], "lat": 45.8217, "lon": 13.3397, "area": "bassa_friulana"},
    {"name": "Grado", "aliases": ["Grado"], "lat": 45.6770, "lon": 13.3947, "area": "laguna_est"},
]

FVG_LOCALITY_STATION_MAP = {
    "aquileia": "Cervignano del F.",
    "artegna": "Gemona del F.",
    "aviano": "Pordenone",
    "azzano decimo": "Pordenone",
    "barcis": "Barcis",
    "basiliano": "Udine",
    "buja": "Gemona del F.",
    "campoformido": "Udine",
    "carlino": "Lignano S.",
    "casarsa della delizia": "Pordenone",
    "castions di strada": "Codroipo",
    "cervignano del friuli": "Cervignano del F.",
    "cividale": "Cividale del F.",
    "cividale del friuli": "Cividale del F.",
    "claut": "Claut",
    "codroipo": "Codroipo",
    "cordenons": "Pordenone",
    "cormons": "Gorizia",
    "duino aurisina": "Trieste",
    "erto": "Barcis",
    "erto e casso": "Barcis",
    "fagagna": "Udine",
    "fiume veneto": "Pordenone",
    "fontanafredda": "Pordenone",
    "forni di sopra": "Tolmezzo",
    "forni di sotto": "Tolmezzo",
    "gemona": "Gemona del F.",
    "gemona del friuli": "Gemona del F.",
    "gorizia": "Gorizia",
    "grado": "Grado",
    "gradisca d'isonzo": "Gorizia",
    "latisana": "Lignano S.",
    "lignano": "Lignano S.",
    "lignano sabbiadoro": "Lignano S.",
    "maniago": "Barcis",
    "martignacco": "Udine",
    "monfalcone": "Gorizia",
    "muggia": "Trieste",
    "palmanova": "Cervignano del F.",
    "pasian di prato": "Udine",
    "piancavallo": "Barcis",
    "pn": "Pordenone",
    "porcia": "Pordenone",
    "pordenone": "Pordenone",
    "prata di pordenone": "Pordenone",
    "ronchi dei legionari": "Gorizia",
    "roveredo in piano": "Pordenone",
    "sacile": "Pordenone",
    "san daniele del friuli": "Gemona del F.",
    "san dorligo della valle": "Trieste",
    "san giorgio di nogaro": "Cervignano del F.",
    "san quirino": "Pordenone",
    "san vito al tagliamento": "Pordenone",
    "san vito al tgl.": "Pordenone",
    "sappada": "Tolmezzo",
    "spilimbergo": "Codroipo",
    "tarcento": "Gemona del F.",
    "tarvisio": "Tarvisio",
    "tavagnacco": "Udine",
    "tolmezzo": "Tolmezzo",
    "tricesimo": "Udine",
    "trieste": "Trieste",
    "udine": "Udine",
    "valvasone arzene": "Codroipo",
}

def map_weather_code(code, wind_speed=None):
    if wind_speed is not None and wind_speed > 40:
        return "Vento"

    if code == 0:
        return "Soleggiato"
    if code == 1:
        return "Poco nuvoloso"
    if code == 2:
        return "Parzialmente nuvoloso"
    if code == 3:
        return "Coperto"
    if code in [45, 48]:
        return "Nebbia"
    if code in [51, 53, 55]:
        return "Pioggia leggera"
    if code in [61, 63, 65]:
        return "Pioggia"
    if code in [80, 81, 82]:
        return "Rovesci"
    if code in [95, 96, 99]:
        return "Temporale"
    if code in [71, 73, 75, 77, 85, 86]:
        return "Neve"

    return "Coperto"

def is_fvg_location(city: str, lat: float = None, lon: float = None) -> bool:
    normalized_city = normalize_place_name(city)

    if lat is not None and lon is not None:
        try:
            return get_default_fvg_geography_catalog().resolve_municipality_istat(
                float(lat),
                float(lon),
            ) is not None
        except (TypeError, ValueError):
            return False

    if normalized_city in FVG_CITY_NAMES:
        return True

    if lat is None or lon is None:
        coords = CITY_COORDS.get(city)
        if coords:
            lat = coords["lat"]
            lon = coords["lon"]

    if lat is None or lon is None:
        return False

    return get_default_fvg_geography_catalog().resolve_municipality_istat(
        float(lat),
        float(lon),
    ) is not None

def build_weather_sources(
    city: str,
    lat: float = None,
    lon: float = None,
    active_source_id: str = None,
    *,
    include_open_meteo: bool = True,
):
    is_fvg = is_fvg_location(city, lat, lon)
    if include_open_meteo:
        priority = [OSMER_SOURCE, OPEN_METEO_SOURCE] if is_fvg else [OPEN_METEO_SOURCE]
        notes = (
            "Per FVG la fonte primaria editoriale e istituzionale e ARPA FVG OSMER. "
            "Previsioni ufficiali e misure stazione OSMER sono integrate quando disponibili; "
            "Open-Meteo resta supporto operativo normalizzato."
            if is_fvg
            else "Fuori FVG viene usato Open-Meteo come fonte meteo operativa."
        )
    else:
        priority = [OSMER_SOURCE] if is_fvg else []
        notes = (
            "Nel pilot meteo locale il bollettino resta esclusivamente ARPA FVG OSMER; "
            "Open-Meteo e disabilitato dal backend."
            if is_fvg
            else "Open-Meteo e disabilitato dal backend."
        )
    active_source = active_source_id or ("arpa_fvg_osmer" if is_fvg else "open_meteo")

    return {
        "active": active_source,
        "is_fvg": is_fvg,
        "priority": priority,
        "notes": notes,
    }

def html_to_lines(html: str) -> list[str]:
    text = re.sub(r"(?is)<script.*?</script>|<style.*?</style>", " ", html or "")
    text = re.sub(r"(?is)<br\s*/?>|</p>|</div>|</li>|</h\d>|</tr>", "\n", text)
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    text = unescape(text)
    text = re.sub(r"[ \t\r\f\v]+", " ", text)
    return [line.strip() for line in text.splitlines() if line.strip()]

def get_fvg_timezone():
    if ZoneInfo:
        try:
            return ZoneInfo("Europe/Rome")
        except Exception:
            pass

    return timezone(timedelta(hours=2))

def parse_osmer_temperature_line(line: str) -> tuple[str, dict] | None:
    match = re.match(
        r"^(?P<area>pianura|costa)\s+"
        r"(?P<min>\d{1,2}/\d{1,2})\s+"
        r"(?P<max>\d{1,2}/\d{1,2})"
        r"(?:\s+(?P<altitude>\d{3,4})\s*m\s+(?P<altitude_temp>-?\d{1,2}))?",
        line.strip(),
        re.IGNORECASE,
    )

    if not match:
        return None

    data = match.groupdict()
    area = "plain" if data["area"].lower() == "pianura" else "coast"
    result = {
        "min": data["min"],
        "max": data["max"],
    }

    if data.get("altitude") and data.get("altitude_temp"):
        result["altitude"] = {
            "meters": int(data["altitude"]),
            "temperature": int(data["altitude_temp"]),
        }

    return area, result

def parse_osmer_temperatures(lines: list[str], start_index: int) -> dict:
    temperatures = {}
    mountain = {}

    for line in lines[start_index + 1:start_index + 5]:
        parsed = parse_osmer_temperature_line(line)
        if not parsed:
            break

        area, data = parsed
        altitude = data.pop("altitude", None)
        temperatures[area] = data

        if altitude:
            mountain[f"{altitude['meters']}m"] = altitude["temperature"]

    if mountain:
        temperatures["mountain"] = mountain

    return temperatures

def parse_osmer_forecast_blocks(lines: list[str], limit: int = 5) -> list[dict]:
    blocks = []

    for index, line in enumerate(lines):
        if not (line.lower().startswith("emissione:") or line.lower().startswith("emission:")):
            continue

        date_label = ""
        for previous in reversed(lines[max(0, index - 5):index]):
            if re.search(r"\b\d{1,2}\s+[a-zàèéìòù]+\b", previous.lower()):
                date_label = previous
                break

        description_parts = []
        temperatures = {}
        for next_line in lines[index + 1:index + 8]:
            lower = next_line.lower()
            if lower.startswith("temp.") or lower.startswith("emissione:"):
                if lower.startswith("temp."):
                    temp_index = lines.index(next_line, index + 1)
                    temperatures = parse_osmer_temperatures(lines, temp_index)
                break
            if len(next_line) < 20:
                continue
            description_parts.append(next_line)

        description = " ".join(description_parts).strip()
        if not description:
            continue

        blocks.append(
            {
                "date_label": date_label,
                "emission": re.sub(r"^emissione?:", "", line, flags=re.IGNORECASE).strip(),
                "text": description,
                "temperatures": temperatures,
            }
        )

        if len(blocks) >= limit:
            break

    return blocks

def parse_osmer_situation(lines: list[str]) -> str:
    for index, line in enumerate(lines):
        normalized = normalize_for_search(line)
        if normalized not in ("situazione generale", "situazion gjeneral"):
            continue

        parts = []
        for next_line in lines[index + 1:index + 8]:
            if normalize_for_search(next_line) in ("previsioni", "previsions"):
                break
            if len(next_line) >= 20:
                parts.append(next_line)

        return " ".join(parts).strip()

    return ""

def parse_float_value(value):
    if value in (None, "-", ""):
        return None

    try:
        return float(str(value).replace(",", "."))
    except ValueError:
        return None

def get_osmer_station_reference(station_name: str) -> dict | None:
    normalized = normalize_place_name(station_name)

    for station in OSMER_STATION_REFERENCES:
        names = [station.get("name"), *(station.get("aliases") or [])]
        if normalized in {normalize_place_name(name) for name in names if name}:
            return station

    return None

def build_station_resolution(
    city: str,
    station: dict | None,
    scope: str,
    lat: float = None,
    lon: float = None,
    reason: str = "",
) -> dict:
    aliases = (station or {}).get("aliases") or [city]
    station_name = (station or {}).get("name") or aliases[0]
    distance_km = None

    try:
        if station and lat is not None and lon is not None:
            distance_km = haversine_km(float(lat), float(lon), station["lat"], station["lon"])
    except (TypeError, ValueError, KeyError):
        distance_km = None

    return {
        "requested_city": city,
        "station": station_name,
        "aliases": aliases,
        "scope": scope,
        "distance_km": round(distance_km, 1) if distance_km is not None else None,
        "area": (station or {}).get("area"),
        "reason": reason,
    }

def resolve_osmer_station_context(city: str, lat: float = None, lon: float = None) -> dict:
    explicit_aliases = OSMER_STATION_ALIASES.get(normalize_place_name(city))
    if explicit_aliases:
        station = get_osmer_station_reference(explicit_aliases[0])
        return build_station_resolution(
            city,
            station,
            "exact",
            lat,
            lon,
            "city_matches_osmer_station_alias",
        )

    mapped_station_name = FVG_LOCALITY_STATION_MAP.get(normalize_place_name(city))
    if mapped_station_name:
        station = get_osmer_station_reference(mapped_station_name)
        return build_station_resolution(
            city,
            station,
            "mapped",
            lat,
            lon,
            "curated_fvg_locality_station_map",
        )

    try:
        latitude = float(lat)
        longitude = float(lon)
    except (TypeError, ValueError):
        return build_station_resolution(city, None, "requested", lat, lon, "missing_coordinates")

    if not is_fvg_location(city, latitude, longitude):
        return build_station_resolution(city, None, "requested", lat, lon, "outside_fvg")

    nearest = min(
        OSMER_STATION_REFERENCES,
        key=lambda station: haversine_km(latitude, longitude, station["lat"], station["lon"]),
        default=None,
    )

    return build_station_resolution(
        city,
        nearest,
        "nearest",
        latitude,
        longitude,
        "nearest_station_by_haversine_distance",
    )

def fetch_osmer_station_data(city: str, lat: float = None, lon: float = None) -> dict | None:
    station_context = resolve_osmer_station_context(city, lat, lon)
    aliases = station_context.get("aliases") or [city]
    cache_key = make_cache_key(
        "osmer-station",
        city,
        lat,
        lon,
        station_context.get("scope"),
        "|".join(aliases),
    )
    cached = get_from_cache(osmer_cache, cache_key, OSMER_CACHE_TTL)

    if cached:
        return cached

    try:
        res = requests.get(
            OSMER_DATA_URL,
            headers={"User-Agent": HTTP_USER_AGENT},
            timeout=WEATHER_REQUEST_TIMEOUT,
        )
        res.raise_for_status()

        rows = re.findall(r"(?is)<tr>\s*(.*?)\s*</tr>", res.text)

        for row in rows:
            cells = re.findall(r"(?is)<td[^>]*>(.*?)</td>", row)
            values = [
                re.sub(r"\s+", " ", re.sub(r"(?s)<[^>]+>", " ", unescape(cell))).strip()
                for cell in cells
            ]

            if len(values) < 9 or values[0] not in aliases:
                continue

            result = {
                "station": values[0],
                "station_scope": station_context.get("scope"),
                "station_distance_km": station_context.get("distance_km"),
                "station_resolution": station_context,
                "requested_city": city,
                "time": values[1],
                "condition": values[2],
                "precipitation": parse_float_value(values[3]),
                "temperature": parse_float_value(values[4]),
                "humidity": int(values[5]) if values[5].isdigit() else None,
                "wind_direction": None if values[6] == "-" else values[6],
                "wind_speed": parse_float_value(values[7]),
                "wind_gusts": parse_float_value(values[8]),
                "pressure": parse_float_value(values[9]) if len(values) > 9 else None,
                "source_url": OSMER_DATA_URL,
            }

            set_cache(osmer_cache, cache_key, result)
            return result

    except Exception as error:
        print("Errore dati stazione OSMER:", error)

    return None

def fetch_osmer_home(language: str = "it") -> dict | None:
    normalized_language = "fur" if language == "fur" else "it"
    cache_key = make_cache_key("osmer-home", normalized_language)
    cached = get_from_cache(osmer_cache, cache_key, OSMER_CACHE_TTL)

    if cached:
        return cached

    try:
        ln = "-fur" if normalized_language == "fur" else ""
        res = requests.get(
            f"{OSMER_BASE_URL}/home.php",
            params={"ln": ln},
            headers={"User-Agent": HTTP_USER_AGENT},
            timeout=WEATHER_REQUEST_TIMEOUT,
        )
        res.raise_for_status()

        lines = html_to_lines(res.text)
        forecasts = date_osmer_forecast_blocks(parse_osmer_forecast_blocks(lines))
        data = {
            "language": normalized_language,
            "url": f"{OSMER_BASE_URL}/home.php?ln={ln}",
            "situation": parse_osmer_situation(lines),
            "forecasts": forecasts,
        }

        set_cache(osmer_cache, cache_key, data)
        return data
    except Exception as error:
        print("Errore OSMER home:", error)
        return None

def get_osmer_structured_requested_date() -> str:
    return datetime.now(get_fvg_timezone()).date().isoformat()

def osmer_xml_source_id_for_date(date_value, language: str = "it", series: str = "PW") -> str:
    language_suffix = "-fur" if language == "fur" else ""
    source_series = "NW" if str(series or "").upper() == "NW" else "PW"
    return f"{source_series}{date_value.strftime('%Y%m%d')}{language_suffix}"

def osmer_xml_url_for_source_id(source_id: str) -> str:
    return urljoin(OSMER_DEV_URL, f"xml/previsioni/{source_id}.xml")

def osmer_xml_candidate_in_fetch_window(candidate: dict, requested, lookback_start, lookahead_end) -> bool:
    source_id = str((candidate or {}).get("source_id") or "")
    try:
        candidate_source_date = datetime.fromisoformat((candidate or {}).get("source_date") or "").date()
    except ValueError:
        return True

    if source_id.startswith("NW"):
        return requested <= candidate_source_date <= lookahead_end

    if candidate_source_date < lookback_start:
        return False
    if candidate_source_date > requested:
        return False
    return True

def discover_osmer_xml_candidates(language: str = "it", requested_date: str | None = None) -> list[dict]:
    normalized_language = "fur" if language == "fur" else "it"
    language_suffix = "-fur" if normalized_language == "fur" else ""
    candidates = []
    seen = set()

    try:
        res = requests.get(
            OSMER_DEV_URL,
            headers={"User-Agent": HTTP_USER_AGENT},
            timeout=WEATHER_SUPPORT_TIMEOUT,
        )
        res.raise_for_status()
        pattern = re.compile(r'href=["\'](?P<path>xml/previsioni/(?P<source>(?P<series>[PN]W)(?P<date>\d{8})(?P<suffix>-[a-z]{2,3})?)\.xml)["\']')
        for match in pattern.finditer(res.text):
            suffix = match.group("suffix") or ""
            if suffix != language_suffix:
                continue
            source_id = match.group("source")
            if source_id in seen:
                continue
            seen.add(source_id)
            candidates.append(
                {
                    "source_id": source_id,
                    "source_date": datetime.strptime(match.group("date"), "%Y%m%d").date().isoformat(),
                    "url": urljoin(OSMER_DEV_URL, match.group("path")),
                    "discovery": "dev_page",
                    "series": match.group("series"),
                }
            )
    except Exception as error:
        print("Errore scoperta XML OSMER:", error)

    try:
        requested = datetime.fromisoformat(requested_date or get_osmer_structured_requested_date()).date()
    except ValueError:
        requested = datetime.now().date()

    for offset in range(OSMER_STRUCTURED_LOOKBACK_DAYS):
        candidate_date = requested - timedelta(days=offset)
        source_id = osmer_xml_source_id_for_date(candidate_date, normalized_language)
        if source_id in seen:
            continue
        seen.add(source_id)
        candidates.append(
            {
                "source_id": source_id,
                "source_date": candidate_date.isoformat(),
                "url": osmer_xml_url_for_source_id(source_id),
                "discovery": "lookback",
                "series": "PW",
            }
        )

    for offset in range(1, OSMER_STRUCTURED_LOOKAHEAD_DAYS + 1):
        candidate_date = requested + timedelta(days=offset)
        source_id = osmer_xml_source_id_for_date(candidate_date, normalized_language, "NW")
        if source_id in seen:
            continue
        seen.add(source_id)
        candidates.append(
            {
                "source_id": source_id,
                "source_date": candidate_date.isoformat(),
                "url": osmer_xml_url_for_source_id(source_id),
                "discovery": "lookahead",
                "series": "NW",
            }
        )

    candidates.sort(key=lambda item: item.get("source_date") or "", reverse=True)
    return candidates

def merge_osmer_structured_snapshots(snapshots: list[dict], requested_date: str | None = None) -> dict | None:
    usable_snapshots = [snapshot for snapshot in snapshots if snapshot and snapshot.get("days")]
    if not usable_snapshots:
        return None

    base = dict(usable_snapshots[0])
    try:
        requested = datetime.fromisoformat(requested_date or base.get("requested_date") or "").date()
    except ValueError:
        requested = None

    days_by_date = {}
    for snapshot in sorted(usable_snapshots, key=lambda item: item.get("source_date") or "", reverse=True):
        day_source = {
            "id_emissione": snapshot.get("id_emissione"),
            "data_emissione": snapshot.get("data_emissione"),
            "published_at": snapshot.get("published_at"),
            "updated_at": snapshot.get("updated_at"),
            "raw_hash": snapshot.get("raw_hash"),
            "source_url": snapshot.get("source_url"),
            "source_date": snapshot.get("source_date"),
            "requested_date": snapshot.get("requested_date"),
            "source_status": snapshot.get("source_status"),
            "is_stale": snapshot.get("is_stale"),
            "stale_reason": snapshot.get("stale_reason"),
            "parser_version": snapshot.get("parser_version"),
            "schema_version": snapshot.get("schema_version"),
        }
        for day in snapshot.get("days") or []:
            valid_date = day.get("valid_date")
            if not valid_date or not day.get("areas9") or valid_date in days_by_date:
                continue
            if requested:
                try:
                    parsed_valid_date = datetime.fromisoformat(valid_date).date()
                except ValueError:
                    parsed_valid_date = None
                if parsed_valid_date and parsed_valid_date < requested:
                    continue

            next_day = dict(day)
            next_day.setdefault("source_kind", "structured_xml")
            next_day["osmer_structured_source"] = day_source
            next_areas = {}
            for area_id, area in (next_day.get("areas9") or {}).items():
                next_area = dict(area)
                next_area.setdefault("source_kind", "structured_xml")
                next_area.setdefault("valid_date", valid_date)
                next_area.setdefault("date_source", "xml_valid_date")
                next_areas[area_id] = next_area
            next_day["areas9"] = next_areas
            next_day.setdefault(
                "decision_trace",
                osmer_interpreter.build_structured_xml_passthrough_trace(next_day),
            )
            days_by_date[valid_date] = next_day

    if not days_by_date:
        return None

    merged_days = [days_by_date[valid_date] for valid_date in sorted(days_by_date)]
    incomplete_days = [
        day.get("valid_date")
        for day in merged_days
        if not ((day.get("quality") or {}).get("all_nodes_present") and (day.get("quality") or {}).get("all_fasce_present"))
    ]

    base["days"] = merged_days
    base["merged_from"] = [
        {
            "id_emissione": snapshot.get("id_emissione"),
            "source_date": snapshot.get("source_date"),
            "source_url": snapshot.get("source_url"),
            "discovery": snapshot.get("discovery"),
        }
        for snapshot in usable_snapshots
    ]
    if len(usable_snapshots) > 1:
        has_lookahead = any(
            str(snapshot.get("id_emissione") or "").startswith("NW") or snapshot.get("series") == "NW"
            for snapshot in usable_snapshots
        )
        base["source_status"] = "merged_xml_window" if has_lookahead else "merged_xml_lookback"
    base["quality"] = {
        **(base.get("quality") or {}),
        "days_count": len(merged_days),
        "all_days_complete": not incomplete_days,
        "incomplete_days": incomplete_days,
        "confidence": "alta" if merged_days and not incomplete_days else "media",
    }
    return base

def fetch_osmer_structured_forecast(language: str = "it") -> dict | None:
    normalized_language = "fur" if language == "fur" else "it"
    requested_date = get_osmer_structured_requested_date()
    cache_key = make_cache_key("osmer-structured-forecast", normalized_language, requested_date)
    cached = get_from_cache(osmer_cache, cache_key, OSMER_CACHE_TTL)

    if cached:
        return cached

    try:
        requested = datetime.fromisoformat(requested_date).date()
    except ValueError:
        requested = datetime.now(get_fvg_timezone()).date()
    lookback_start = requested - timedelta(days=OSMER_STRUCTURED_LOOKBACK_DAYS - 1)
    lookahead_end = requested + timedelta(days=OSMER_STRUCTURED_LOOKAHEAD_DAYS)
    snapshots = []

    for candidate in discover_osmer_xml_candidates(normalized_language, requested_date):
        if not osmer_xml_candidate_in_fetch_window(candidate, requested, lookback_start, lookahead_end):
            continue

        try:
            res = requests.get(
                candidate["url"],
                headers={"User-Agent": HTTP_USER_AGENT, "Accept": "application/xml,text/xml,*/*"},
                timeout=WEATHER_SUPPORT_TIMEOUT,
            )
            if res.status_code == 404:
                continue
            res.raise_for_status()
            snapshot = parser_osmer.parse_osmer_xml(
                res.content,
                source_url=candidate["url"],
                source_id=candidate["source_id"],
                requested_date=requested_date,
            )
            source_date = snapshot.get("source_date")
            snapshot["source_status"] = "reachable_xml"
            snapshot["is_stale"] = bool(source_date and source_date < requested_date)
            snapshot["stale_reason"] = "no_new_file" if snapshot["is_stale"] else None
            snapshot["discovery"] = candidate.get("discovery")
            snapshot["lookback_days"] = OSMER_STRUCTURED_LOOKBACK_DAYS
            snapshots.append(snapshot)
        except Exception as error:
            print("Errore XML strutturato OSMER:", candidate.get("url"), error)

    merged = merge_osmer_structured_snapshots(snapshots, requested_date)
    if merged:
        set_cache(osmer_cache, cache_key, merged)
        return merged

    stale = get_stale_from_cache(osmer_cache, cache_key, WEATHER_STALE_TTL)
    if stale:
        stale_copy = dict(stale)
        stale_copy["requested_date"] = requested_date
        stale_copy["checked_at"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        stale_copy["source_status"] = "source_unavailable"
        stale_copy["is_stale"] = True
        stale_copy["stale_reason"] = "source_404"
        return stale_copy

    return None

OSMER_STRUCTURED_PLAIN_COAST_AREA_IDS = ("A5", "A6", "A7", "A8", "A9")

OSMER_STRUCTURED_FORECAST_LABELS = {
    "sun": "Soleggiato",
    "mostly_sunny": "Poco nuvoloso",
    "variable": "Poco nuvoloso",
    "cloudy": "Nuvoloso",
    "overcast": "Coperto",
    "sun_fog": "Nebbia",
    "fog": "Nebbia",
    "mist": "Foschia",
    "light_rain": "Pioggia debole",
    "moderate_rain": "Pioggia",
    "heavy_rain": "Pioggia abbondante",
    "intense_rain": "Pioggia intensa",
    "extreme_rain": "Pioggia molto intensa",
    "moderate_snow": "Neve",
    "heavy_snow": "Neve",
    "intense_snow": "Neve",
    "storm": "Temporale",
    "partly": "Poco nuvoloso",
    "cloud": "Coperto",
    "rain": "Pioggia",
    "snow": "Neve",
}

def osmer_structured_symbol_is_active(symbol: dict | None) -> bool:
    if not symbol:
        return False

    symbol_id = str(symbol.get("id") or "").strip().lower()
    code = symbol.get("code")

    return bool(symbol_id and symbol_id != "none" and code is not None and code != 100)

def osmer_structured_area_condition_type(area: dict | None) -> str | None:
    if not area:
        return None

    symbols = area.get("symbols") or {}

    if osmer_structured_symbol_is_active(symbols.get("temporale")):
        return "storm"
    if osmer_structured_symbol_is_active(symbols.get("neve")):
        return "snow"
    if osmer_structured_symbol_is_active(symbols.get("pioggia")):
        return "rain"
    if osmer_structured_symbol_is_active(symbols.get("nebbia")):
        return "fog"

    sky_id = str((symbols.get("cielo") or {}).get("id") or area.get("dominant_condition") or "").strip().lower()
    if sky_id in ("sun",):
        return "sun"
    if sky_id in ("mostly_sunny", "variable"):
        return "partly"
    if sky_id in ("cloudy", "overcast"):
        return "cloud"
    if sky_id in ("sun_fog", "fog", "mist"):
        return "fog"

    dominant = str(area.get("dominant_condition") or "").strip().lower()
    if dominant in ("storm",):
        return "storm"
    if "rain" in dominant:
        return "rain"
    if "snow" in dominant:
        return "snow"
    if dominant in ("sun", "mostly_sunny", "variable", "cloudy", "overcast", "fog", "mist"):
        return "partly" if dominant in ("mostly_sunny", "variable") else dominant

    return None

def osmer_structured_weighted_winner(entries: list[dict], required_share: float = 0.5) -> str | None:
    total_weight = sum(float(entry.get("weight") or 0) for entry in entries)
    if not total_weight:
        return None

    totals = {}
    for entry in entries:
        condition_type = entry.get("type")
        if not condition_type:
            continue
        totals[condition_type] = totals.get(condition_type, 0) + float(entry.get("weight") or 0)

    if not totals:
        return None

    winner, weight = sorted(totals.items(), key=lambda item: item[1], reverse=True)[0]
    return winner if weight > total_weight * required_share else None

def osmer_structured_forecast_condition(structured_day: dict | None) -> str | None:
    areas9 = (structured_day or {}).get("areas9") or {}
    if not areas9:
        return None

    entries = []
    for area_id, area in areas9.items():
        condition_type = osmer_structured_area_condition_type(area)
        if not condition_type:
            continue
        group = "plain_coast" if area_id in OSMER_STRUCTURED_PLAIN_COAST_AREA_IDS else "mountain"
        entries.append(
            {
                "area_id": area_id,
                "group": group,
                "type": condition_type,
                "weight": 1.35 if group == "plain_coast" else 1.0,
            }
        )

    if not entries:
        return None

    has_mountain_storm = any(entry["group"] == "mountain" and entry["type"] == "storm" for entry in entries)
    has_plain_coast_storm = any(entry["group"] == "plain_coast" and entry["type"] == "storm" for entry in entries)
    storm_count = sum(1 for entry in entries if entry["type"] == "storm")

    if has_plain_coast_storm and (has_mountain_storm or storm_count >= 3):
        return OSMER_STRUCTURED_FORECAST_LABELS["storm"]

    plain_coast_entries = [entry for entry in entries if entry["group"] == "plain_coast"]
    plain_coast_winner = osmer_structured_weighted_winner(plain_coast_entries, 0.5)
    regional_winner = osmer_structured_weighted_winner(entries, 0.5)

    if plain_coast_winner:
        localized_risk = any(entry["type"] in ("storm", "rain", "cloud", "partly") for entry in entries)
        if plain_coast_winner == "sun" and localized_risk:
            return OSMER_STRUCTURED_FORECAST_LABELS["partly"]
        return OSMER_STRUCTURED_FORECAST_LABELS.get(plain_coast_winner)

    if regional_winner:
        return OSMER_STRUCTURED_FORECAST_LABELS.get(regional_winner)

    return OSMER_STRUCTURED_FORECAST_LABELS["partly"]

def attach_osmer_structured_days_to_forecast(forecast_items: list[dict], osmer_structured: dict | None) -> list[dict]:
    if not forecast_items or not osmer_structured:
        return forecast_items

    days_by_date = {
        day.get("valid_date"): day
        for day in osmer_structured.get("days") or []
        if day.get("valid_date") and day.get("areas9")
    }

    if not days_by_date:
        return forecast_items

    attached = []
    for item in forecast_items:
        next_item = dict(item)
        structured_day = days_by_date.get(next_item.get("date"))

        if structured_day:
            next_item["osmer_structured_day"] = structured_day
            next_item["osmer_structured_source"] = structured_day.get("osmer_structured_source") or {
                "id_emissione": osmer_structured.get("id_emissione"),
                "source_url": osmer_structured.get("source_url"),
                "source_date": osmer_structured.get("source_date"),
                "requested_date": osmer_structured.get("requested_date"),
                "source_status": osmer_structured.get("source_status"),
                "is_stale": osmer_structured.get("is_stale"),
                "stale_reason": osmer_structured.get("stale_reason"),
                "parser_version": osmer_structured.get("parser_version"),
                "schema_version": osmer_structured.get("schema_version"),
            }
            structured_condition = osmer_structured_forecast_condition(structured_day)
            if structured_condition:
                next_item["condition"] = structured_condition
                next_item["condition_source"] = "osmer_structured_day"

        attached.append(next_item)

    return attached

def get_osmer_official_weather(city: str, lat: float = None, lon: float = None) -> dict | None:
    if not is_fvg_location(city, lat, lon):
        return None

    cache_key = make_cache_key("osmer-official", city, lat, lon)
    cached = get_from_cache(osmer_cache, cache_key, OSMER_CACHE_TTL)

    if cached:
        return cached

    with ThreadPoolExecutor(max_workers=3) as executor:
        italian_future = executor.submit(fetch_osmer_home, "it")
        friulian_future = executor.submit(fetch_osmer_home, "fur")
        station_future = executor.submit(fetch_osmer_station_data, city, lat, lon)

        italian = italian_future.result()
        friulian = friulian_future.result()
        station = station_future.result()

    if not italian and not friulian:
        return None

    result = {
        "source": OSMER_SOURCE,
        "station": station,
        "it": italian,
        "fur": friulian,
    }

    set_cache(osmer_cache, cache_key, result)
    return result

def geocode_city(city: str, *, allow_open_meteo: bool = True):
    coords = CITY_COORDS.get(city)
    if coords:
        return coords["lat"], coords["lon"]

    municipality_coords = FVG_MUNICIPALITY_COORDS.get(normalize_place_name(city))
    if municipality_coords:
        return municipality_coords["lat"], municipality_coords["lon"]

    mapped_station_name = FVG_LOCALITY_STATION_MAP.get(normalize_place_name(city))
    if mapped_station_name:
        station = get_osmer_station_reference(mapped_station_name)
        if station:
            return station["lat"], station["lon"]

    if not allow_open_meteo or not open_meteo_enabled():
        return None, None

    try:
        require_open_meteo_enabled("geocoding")
        params = {
            "name": city,
            "count": 5,
            "language": "it",
            "format": "json",
        }

        res = requests.get(OPEN_METEO_GEOCODE_URL, params=params, timeout=8)
        res.raise_for_status()

        data = res.json()
        results = data.get("results") or []
        italian = [r for r in results if r.get("country_code") == "IT"]

        if not italian:
            return None, None

        italian.sort(
            key=lambda item: (
                0 if "friuli" in (item.get("admin1") or "").lower() else 1,
                -(item.get("population") or 0),
            )
        )

        best = italian[0]
        return best.get("latitude"), best.get("longitude")

    except Exception as e:
        print("Errore geocoding:", e)
        return None, None

def haversine_km(lat1, lon1, lat2, lon2):
    radius_km = 6371.0

    phi1 = math.radians(float(lat1))
    phi2 = math.radians(float(lat2))
    delta_phi = math.radians(float(lat2) - float(lat1))
    delta_lambda = math.radians(float(lon2) - float(lon1))

    a = (
        math.sin(delta_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return radius_km * c

def open_meteo_forecast(lat: float, lon: float, timeout: int = WEATHER_REQUEST_TIMEOUT):
    require_open_meteo_enabled("forecast")
    cache_key = make_cache_key("open-meteo-forecast", round(float(lat), 4), round(float(lon), 4))
    cached = get_from_cache(open_meteo_raw_cache, cache_key, CACHE_TTL)

    if cached:
        return cached

    recent_error = get_from_cache(open_meteo_error_cache, cache_key, OPEN_METEO_ERROR_CACHE_TTL)
    if recent_error:
        raise requests.RequestException(recent_error.get("error") or "Open-Meteo temporarily unavailable")

    params = {
        "latitude": lat,
        "longitude": lon,
        "current": ",".join(
            [
                "temperature_2m",
                "relative_humidity_2m",
                "apparent_temperature",
                "pressure_msl",
                "cloud_cover",
                "wind_speed_10m",
                "wind_direction_10m",
                "wind_gusts_10m",
                "precipitation",
                "rain",
                "showers",
                "snowfall",
                "visibility",
                "weather_code",
                "is_day",
            ]
        ),
        "hourly": ",".join(
            [
                "temperature_2m",
                "precipitation_probability",
                "precipitation",
                "rain",
                "showers",
                "snowfall",
                "weather_code",
                "wind_speed_10m",
                "wind_gusts_10m",
            ]
        ),
        "daily": ",".join(
            [
                "temperature_2m_max",
                "temperature_2m_min",
                "weather_code",
                "precipitation_probability_max",
                "sunrise",
                "sunset",
            ]
        ),
        "timezone": "auto",
    }

    try:
        res = requests.get(OPEN_METEO_FORECAST_URL, params=params, timeout=timeout)
        res.raise_for_status()
        data = res.json()
        set_cache(open_meteo_raw_cache, cache_key, data)
        open_meteo_error_cache.pop(cache_key, None)
        return data
    except requests.RequestException as error:
        set_cache(open_meteo_error_cache, cache_key, {"error": str(error)})
        raise

OSMER_MONTHS = {
    "gennaio": 1,
    "febbraio": 2,
    "marzo": 3,
    "aprile": 4,
    "maggio": 5,
    "giugno": 6,
    "luglio": 7,
    "agosto": 8,
    "settembre": 9,
    "ottobre": 10,
    "novembre": 11,
    "dicembre": 12,
}

def parse_osmer_date_label(date_label: str, reference_date=None):
    reference = reference_date or datetime.now().date()
    normalized = normalize_for_search(date_label)
    match = re.search(
        r"\b(\d{1,2})\s+("
        + "|".join(OSMER_MONTHS.keys())
        + r")\b",
        normalized,
    )

    if not match:
        return None

    day = int(match.group(1))
    month = OSMER_MONTHS[match.group(2)]

    try:
        parsed = datetime(reference.year, month, day).date()
    except ValueError:
        return None

    if parsed < reference - timedelta(days=30):
        parsed = datetime(reference.year + 1, month, day).date()
    elif parsed > reference + timedelta(days=330):
        parsed = datetime(reference.year - 1, month, day).date()

    return parsed

def parse_osmer_emission_date(emission: str, fallback_date=None):
    match = re.search(r"\b(\d{2})-(\d{2})-(\d{4})\b", str(emission or ""))
    if match:
        day, month, year = match.groups()
        try:
            return datetime(int(year), int(month), int(day)).date()
        except ValueError:
            return fallback_date

    return fallback_date

def date_osmer_forecast_blocks(blocks: list[dict], reference_date=None) -> list[dict]:
    if not blocks:
        return []

    reference = reference_date or datetime.now(get_fvg_timezone()).date()
    emission_anchor = None
    for block in blocks:
        emission_anchor = parse_osmer_emission_date(block.get("emission"), None)
        if emission_anchor:
            break
    emission_anchor = emission_anchor or reference

    expected_dates = [emission_anchor + timedelta(days=index) for index in range(len(blocks))]
    parsed_by_index = {
        index: parse_osmer_date_label(block.get("date_label") or "", emission_anchor)
        for index, block in enumerate(blocks)
    }
    sequence_coherent = True
    for index, parsed in parsed_by_index.items():
        if parsed and parsed != expected_dates[index]:
            sequence_coherent = False
            break

    dated = []
    for index, block in enumerate(blocks):
        next_block = dict(block)
        parsed = parsed_by_index[index]

        if parsed:
            next_block["date"] = parsed.isoformat()
            next_block["date_source"] = "html_date_label"
        elif sequence_coherent:
            next_block["date"] = expected_dates[index].isoformat()
            next_block["date_source"] = "emission_sequence"
        else:
            next_block["date"] = None
            next_block["date_source"] = "undated_incoherent_sequence"

        next_block["sequence_index"] = index
        next_block["emission_date"] = emission_anchor.isoformat() if emission_anchor else None
        dated.append(next_block)

    return dated

def build_osmer_forecast_block_index(blocks: list[dict], reference_date=None) -> dict:
    indexed = {}

    for block in date_osmer_forecast_blocks(blocks or [], reference_date):
        if block.get("date"):
            indexed[block["date"]] = block

    return indexed

def infer_condition_from_text(text: str, fallback: str = "Coperto") -> str:
    normalized = normalize_for_search(text)

    if re.search(r"\btempor|burrasca|burasce\b", normalized):
        return "Temporale"
    if re.search(r"\brovesc|scjassade|precipitazion improvise\b", normalized):
        return "Rovesci"
    if re.search(r"\bpiogg|pluie|ploe|precipitaz|rain\b", normalized):
        return "Pioggia"
    if re.search(r"\bnev|neve|nif|snow\b", normalized):
        return "Neve"
    if re.search(r"\bnebb|nibl|fog\b", normalized):
        return "Nebbia"
    if re.search(r"\bseren|sole|soleggiat|soreli\b", normalized):
        return "Soleggiato"
    if re.search(r"\bpoco nuvol|variabil|schiarit\b", normalized):
        return "Poco nuvoloso"
    if re.search(r"\bnuvol|copert|nuvul|cuviert\b", normalized):
        return "Coperto"
    if re.search(r"\bvento|vent|bora|buere|raffich\b", normalized):
        return "Vento"

    return fallback

OSMER_PROJECTED_AREA_META = {
    "A1": {"name": "Alpi Carniche", "projection_source": "mountain_west"},
    "A2": {"name": "Alpi Giulie", "projection_source": "mountain_east"},
    "A3": {"name": "Pedemontana / alta pianura occidentale", "projection_source": "high_plain_west"},
    "A4": {"name": "Pedemontana / alta pianura orientale", "projection_source": "high_plain_east"},
    "A5": {"name": "Pianura Pordenone", "projection_source": "plain_west"},
    "A6": {"name": "Pianura Udine", "projection_source": "plain_central"},
    "A7": {"name": "Pianura giulia-goriziana", "projection_source": "plain_east"},
    "A8": {"name": "Costa Lignano-Bibione", "projection_source": "coast_west"},
    "A9": {"name": "Costa Trieste", "projection_source": "coast_east"},
}

OSMER_PROJECTED_ALL_AREAS = tuple(OSMER_PROJECTED_AREA_META.keys())

OSMER_PROJECTED_MOUNTAIN_AREAS = ("A1", "A2", "A3", "A4")

OSMER_PROJECTED_PLAIN_AREAS = ("A5", "A6", "A7", "A8")

OSMER_PROJECTED_COAST_FOCUS_AREAS = ("A9",)

def split_osmer_projection_sentences(text: str) -> list[str]:
    return [
        sentence.strip()
        for sentence in re.split(r"(?<=[.!?;:])\s+", str(text or ""))
        if sentence.strip()
    ]

def clean_osmer_projection_text(text: str) -> str:
    return " ".join(str(text or "").split())

def find_osmer_projection_block(clean_text: str, starts: tuple[str, ...], stops: tuple[str, ...]) -> str:
    if not clean_text:
        return ""

    start_pattern = "|".join(starts)
    stop_pattern = "|".join(stops)
    pattern = rf"({start_pattern})(.*?)(?={stop_pattern}|$)" if stop_pattern else rf"({start_pattern})(.*)"
    match = re.search(pattern, clean_text, re.IGNORECASE)
    return match.group(0).strip() if match else ""

def has_projected_wind_alert(text: str) -> bool:
    normalized = normalize_for_search(text)
    return (
        any(token in normalized for token in ("bora", "scirocco", "vento", "venti"))
        and any(token in normalized for token in ("sostenut", "fort", "moderata", "moderato"))
    )

def projected_wind_profile(text: str) -> dict | None:
    normalized = normalize_for_search(text)
    if not has_projected_wind_alert(text):
        return None

    phases = []
    if "bora" in normalized and ("mattino" in normalized or "mattina" in normalized):
        phases.append({"period": "mattino", "wind": "Bora", "direction": "NE", "intensity": "moderata"})
    if "scirocco" in normalized and ("ore centrali" in normalized or "pomerig" in normalized):
        intensity = "moderata-sostenuta" if "sostenut" in normalized else "moderata"
        phases.append({"period": "ore centrali", "wind": "Scirocco", "direction": "SE", "intensity": intensity})
    if "bora" in normalized and ("sera" in normalized or "serata" in normalized):
        phases.append({"period": "sera", "wind": "Bora", "direction": "NE", "intensity": "moderata"})

    return {
        "type": "wind_rotation" if "bora" in normalized and "scirocco" in normalized else "wind_sustained",
        "alert": True,
        "source_text": text.strip(),
        "phases": phases,
    }

def projected_condition_from_macro_block(block_text: str, *, coast_focus: bool = False) -> tuple[str, float, list[dict]]:
    normalized = normalize_for_search(block_text)
    wind_profile = projected_wind_profile(block_text) if coast_focus else None
    overlays = [wind_profile] if wind_profile else []

    if "tempor" in normalized:
        risk = 3.0
        if "localmente fort" in normalized and ("variabil" not in normalized and "minore probabil" not in normalized):
            risk = 4.0
            condition = "temporale forte"
        else:
            condition = "temporale variabile"
        if wind_profile:
            risk = max(risk, 3.5)
        return condition, risk, overlays

    if "piogg" in normalized or "rovesc" in normalized:
        if any(token in normalized for token in ("abbondant", "intens", "battente")):
            return "pioggia intensa", 4.0, overlays
        return "pioggia", 3.0, overlays

    if "copert" in normalized or "molto nuvol" in normalized:
        return "coperto", 2.0, overlays
    if "poco nuvol" in normalized:
        return "poco nuvoloso", 1.0, overlays
    if "seren" in normalized or "sole" in normalized:
        return "sereno", 1.0, overlays
    if "variabil" in normalized:
        return "variabile", 1.0, overlays

    condition = infer_condition_from_text(block_text, "variabile").lower()
    risk = 3.5 if wind_profile else 2.0
    return condition, risk, overlays

def has_projected_weather_signal(text: str) -> bool:
    normalized = normalize_for_search(text)
    return any(
        token in normalized
        for token in (
            "cielo",
            "seren",
            "sole",
            "soleggiat",
            "poco nuvol",
            "nuvol",
            "variabil",
            "copert",
            "piogg",
            "rovesc",
            "tempor",
            "neve",
            "nevic",
            "nebb",
            "fosch",
            "vento",
            "venti",
            "bora",
            "scirocco",
        )
    )

def build_projected_candidate(
    condition: str,
    text: str,
    risk_index: float,
    projection_source: str,
    overlays: list[dict] | None = None,
    locked: bool = False,
) -> dict:
    return {
        "condition": condition,
        "text": text.strip(),
        "severity": max(projected_condition_severity(condition), int(float(risk_index or 0) * 20)),
        "risk_index": risk_index,
        "projection_source": projection_source,
        "overlays": list(overlays or []),
        "locked": locked,
    }

def clone_projected_candidate(candidate: dict) -> dict:
    cloned = dict(candidate)
    cloned["overlays"] = [dict(overlay) for overlay in candidate.get("overlays") or []]
    return cloned

def build_projected_wind_overlay(source_text: str, *, area: str, intensity: str) -> dict:
    return {
        "type": "wind_sustained",
        "alert": True,
        "wind": "Bora",
        "direction": "NE",
        "area": area,
        "intensity": intensity,
        "source_text": source_text.strip(),
    }

def improving_transition_projected_candidates_for_text(text: str) -> dict[str, dict]:
    clean_text = clean_osmer_projection_text(text)
    normalized = normalize_for_search(clean_text)
    is_improving_transition = (
        ("nella notte" in normalized or "di notte" in normalized)
        and "residu" in normalized
        and any(token in normalized for token in ("dal mattino", "dalla mattina"))
        and any(token in normalized for token in ("poco nuvol", "seren"))
    )
    if not is_improving_transition:
        return {}

    candidates = {}

    mountain_candidate = build_projected_candidate(
        "poco nuvoloso",
        clean_text,
        1.5,
        "mountain_improving_transition",
        locked=True,
    )
    for area_id in OSMER_PROJECTED_MOUNTAIN_AREAS:
        candidates[area_id] = clone_projected_candidate(mountain_candidate)

    plain_candidate = build_projected_candidate(
        "sereno",
        clean_text,
        1.0,
        "plain_clear_after_transition",
        locked=True,
    )
    for area_id in ("A5", "A6", "A7"):
        candidates[area_id] = clone_projected_candidate(plain_candidate)

    if "fascia orientale" in normalized or "orientale" in normalized:
        east_overlay = build_projected_wind_overlay(clean_text, area="fascia orientale", intensity="moderata")
        candidates["A8"] = build_projected_candidate(
            "sereno",
            clean_text,
            2.0,
            "eastern_plain_bora",
            [east_overlay],
            locked=True,
        )

    if any(token in normalized for token in ("carso", "trieste", "triest")):
        coast_overlay = build_projected_wind_overlay(clean_text, area="Carso e Trieste", intensity="sostenuta")
        candidates["A9"] = build_projected_candidate(
            "vento con cielo sereno",
            clean_text,
            3.0,
            "coast_bora_focus",
            [coast_overlay],
            locked=True,
        )

    return candidates

def late_possible_storm_transition_projected_candidates_for_text(text: str) -> dict[str, dict]:
    clean_text = clean_osmer_projection_text(text)
    normalized = normalize_for_search(clean_text)
    has_morning_fair = (
        ("al mattino" in normalized or "di mattino" in normalized)
        and any(token in normalized for token in ("stabile", "poco nuvol", "seren"))
    )
    has_afternoon_variability = (
        ("dal pomeriggio" in normalized or "nel pomeriggio" in normalized)
        and "variabil" in normalized
    )
    has_late_possible_storm = (
        any(token in normalized for token in ("sera", "serata"))
        and "tempor" in normalized
        and any(token in normalized for token in ("non esclus", "possibil", "qualche"))
    )
    has_area_specific_scope = any(
        token in normalized
        for token in (
            "zona montana",
            "zone montane",
            "monti",
            "montagna",
            "pianura",
            "costa",
            "prealp",
            "pedemont",
            "alta pianura",
            "carso",
            "trieste",
            "udine",
            "gorizia",
            "pordenon",
        )
    )

    if not (has_morning_fair and has_afternoon_variability and has_late_possible_storm):
        return {}
    if has_area_specific_scope:
        return {}

    candidate = build_projected_candidate(
        "variabile",
        clean_text,
        1.5,
        "late_possible_storm_transition",
        locked=True,
    )
    return {area_id: clone_projected_candidate(candidate) for area_id in OSMER_PROJECTED_ALL_AREAS}

def macro_projected_candidates_for_text(text: str) -> dict[str, dict]:
    clean_text = clean_osmer_projection_text(text)
    if not clean_text:
        return {}

    transition_candidates = improving_transition_projected_candidates_for_text(clean_text)
    if transition_candidates:
        return transition_candidates

    late_storm_transition_candidates = late_possible_storm_transition_projected_candidates_for_text(clean_text)
    if late_storm_transition_candidates:
        return late_storm_transition_candidates

    mountain_text = find_osmer_projection_block(
        clean_text,
        ("Sulla zona montana", "Sui monti", "In montagna", "Sulle zone montane"),
        (
            "Su pianura",
            "Sulla pianura",
            "In pianura",
            "Sulla costa",
            "Sulla zona costiera",
            "Sulle zone costiere",
            "Soffiera",
            "Soffier",
            "Venti?",
            "Bora",
            "Scirocco",
            "Temperature",
            "Temp\\.",
        ),
    )
    plain_text = find_osmer_projection_block(
        clean_text,
        ("Su pianura(?: e costa)?", "Sulla pianura(?: e costa)?", "In pianura(?: e costa)?"),
        (
            "Sui monti",
            "Sulla zona montana",
            "In montagna",
            "Sulle zone montane",
            "Sulla costa",
            "Sulla zona costiera",
            "Sulle zone costiere",
            "Soffiera",
            "Soffier",
            "Venti?",
            "Bora",
            "Scirocco",
            "Temperature",
            "Temp\\.",
        ),
    )
    coast_text = find_osmer_projection_block(
        clean_text,
        ("Sulla costa", "Sulla zona costiera", "Sulle zone costiere"),
        ("Soffiera", "Soffier", "Venti?", "Bora", "Scirocco", "Temperature", "Temp\\."),
    )

    wind_sentences = [
        sentence
        for sentence in split_osmer_projection_sentences(clean_text)
        if has_projected_wind_alert(sentence)
        and any(token in normalize_for_search(sentence) for token in ("costa", "fascia orientale", "trieste", "carso"))
    ]
    wind_text = " ".join(wind_sentences).strip()

    if not coast_text and plain_text and "costa" in normalize_for_search(plain_text):
        coast_text = plain_text
    if wind_text:
        coast_text = f"{coast_text} {wind_text}".strip() if coast_text else wind_text
    if mountain_text and not has_projected_weather_signal(mountain_text):
        mountain_text = ""
    if plain_text and not has_projected_weather_signal(plain_text):
        plain_text = ""
    if coast_text and not has_projected_weather_signal(coast_text):
        coast_text = ""

    candidates = {}
    if mountain_text:
        condition, risk_index, overlays = projected_condition_from_macro_block(mountain_text)
        candidate = build_projected_candidate(condition, mountain_text, risk_index, "mountain", overlays)
        for area_id in OSMER_PROJECTED_MOUNTAIN_AREAS:
            candidates[area_id] = clone_projected_candidate(candidate)

    if plain_text:
        condition, risk_index, overlays = projected_condition_from_macro_block(plain_text)
        candidate = build_projected_candidate(condition, plain_text, risk_index, "plain_coast_generic", overlays)
        for area_id in OSMER_PROJECTED_PLAIN_AREAS:
            candidates[area_id] = clone_projected_candidate(candidate)

    if coast_text:
        condition, risk_index, overlays = projected_condition_from_macro_block(coast_text, coast_focus=True)
        condition_key = normalize_for_search(condition)
        if (
            plain_text
            and "tempor" in normalize_for_search(plain_text)
            and not any(token in condition_key for token in ("tempor", "piogg", "rovesc", "nev"))
        ):
            condition = "temporale variabile"
            risk_index = max(risk_index, 3.5 if overlays else 3.0)
        candidate = build_projected_candidate(condition, coast_text, risk_index, "coast_focus", overlays)
        for area_id in OSMER_PROJECTED_COAST_FOCUS_AREAS:
            candidates[area_id] = clone_projected_candidate(candidate)

    return candidates

def projected_area_ids_for_text(text: str) -> set[str]:
    normalized = normalize_for_search(text)
    area_ids = set()
    has_high_plain = "alta pianura" in normalized or "alte pianure" in normalized

    if any(token in normalized for token in ("tutta la regione", "tutte le zone", "su tutte le zone")):
        return set(OSMER_PROJECTED_ALL_AREAS)

    if any(token in normalized for token in ("alpi carniche", "carnia", "cadore")):
        area_ids.add("A1")
    if any(token in normalized for token in ("alpi giulie", "giulie", "tarvis")):
        area_ids.add("A2")
    if any(token in normalized for token in ("zona montana", "montagna", "monti", "montane", "montana")):
        area_ids.update(("A1", "A2"))

    if any(token in normalized for token in ("prealp", "pedemont", "fascia prealpina")):
        area_ids.update(("A3", "A4"))
    if has_high_plain:
        area_ids.update(("A3", "A4", "A5", "A6"))

    if any(token in normalized for token in ("pordenon", "occident")):
        area_ids.add("A5")
    if any(token in normalized for token in ("udine", "udinese", "centrale")):
        area_ids.add("A6")
    if any(token in normalized for token in ("gorizia", "goriziano", "orientale", "orientali")):
        area_ids.add("A7")
    if "pianura" in normalized and not has_high_plain:
        area_ids.update(("A5", "A6", "A7"))

    if any(token in normalized for token in ("lignano", "bibione", "laguna")):
        area_ids.add("A8")
    if any(token in normalized for token in ("trieste", "carso", "triest")):
        area_ids.add("A9")
    if any(token in normalized for token in ("costa", "mare")):
        area_ids.update(("A8", "A9"))

    return area_ids

def projected_condition_severity(condition: str) -> int:
    normalized = normalize_for_search(condition)
    if "tempor" in normalized:
        return 70
    if "neve" in normalized or "nev" in normalized:
        return 60
    if "rovesc" in normalized:
        return 55
    if "piogg" in normalized:
        return 50
    if "vento" in normalized or "bora" in normalized:
        return 40
    if "nebb" in normalized:
        return 30
    if "copert" in normalized or "nuvol" in normalized:
        return 20
    if "poco nuvol" in normalized or "variabil" in normalized:
        return 10
    if "sole" in normalized or "seren" in normalized:
        return 5
    return 0

def projected_symbol_detail(kind: str, symbol_id: str, label: str = "", code: int = 100, description: str = "") -> dict:
    detail = {
        "id": symbol_id,
        "label": label,
        "code": code,
    }
    if description:
        detail["description"] = description
    return detail

def projected_symbols_for_condition(condition: str) -> dict:
    normalized = normalize_for_search(condition)
    symbols = {
        "cielo": projected_symbol_detail("cielo", "variable", "variabile", 2, "variabile"),
        "pioggia": projected_symbol_detail("pioggia", "none"),
        "neve": projected_symbol_detail("neve", "none"),
        "temporale": projected_symbol_detail("temporale", "none"),
        "nebbia": projected_symbol_detail("nebbia", "none"),
        "vento": projected_symbol_detail("vento", "none"),
    }

    if any(token in normalized for token in ("vento", "ventoso", "bora")):
        symbols["vento"] = projected_symbol_detail("vento", "wind", "vento", 15, "vento")

    if "temporale forte" in normalized or "temporali forti" in normalized:
        symbols["temporale"] = projected_symbol_detail("temporale", "storm", "temporale forte", 13, "temporale forte")
        return symbols
    if "tempor" in normalized:
        symbols["temporale"] = projected_symbol_detail("temporale", "storm", "temporale", 13, "temporale")
        return symbols
    if "neve" in normalized or "nev" in normalized:
        symbols["neve"] = projected_symbol_detail("neve", "moderate_snow", "moderata", 10, "moderata")
        return symbols
    if "rovesc" in normalized or "piogg" in normalized:
        if any(token in normalized for token in ("intens", "battente")):
            rain_id = "intense_rain"
            rain_code = 9
            rain_label = "intensa"
        elif "abbondant" in normalized:
            rain_id = "heavy_rain"
            rain_code = 8
            rain_label = "abbondante"
        else:
            rain_id = "light_rain" if "debole" in normalized else "moderate_rain"
            rain_code = 6 if rain_id == "light_rain" else 7
            rain_label = "debole" if rain_id == "light_rain" else "moderata"
        symbols["pioggia"] = projected_symbol_detail("pioggia", rain_id, rain_label, rain_code, rain_label)
        return symbols
    if "nebb" in normalized or "fosch" in normalized:
        symbols["nebbia"] = projected_symbol_detail("nebbia", "fog", "nebbia", 14, "nebbia")
        return symbols
    if "poco nuvol" in normalized:
        symbols["cielo"] = projected_symbol_detail("cielo", "mostly_sunny", "poco nuvoloso", 1, "poco nuvoloso")
        return symbols
    if "copert" in normalized:
        symbols["cielo"] = projected_symbol_detail("cielo", "overcast", "coperto", 4, "coperto")
        return symbols
    if "nuvol" in normalized:
        symbols["cielo"] = projected_symbol_detail("cielo", "cloudy", "nuvoloso", 3, "nuvoloso")
        return symbols
    if "sole" in normalized or "seren" in normalized:
        symbols["cielo"] = projected_symbol_detail("cielo", "sun", "sereno", 0, "sereno")

    return symbols

def projected_dominant_condition(symbols: dict) -> str:
    if symbols["temporale"]["id"] != "none":
        return "storm"
    if symbols["neve"]["id"] != "none":
        return symbols["neve"]["id"]
    if symbols["pioggia"]["id"] != "none":
        return symbols["pioggia"]["id"]
    if symbols["nebbia"]["id"] != "none":
        return symbols["nebbia"]["id"]
    return symbols["cielo"]["id"]

def build_official_projected_day(block: dict) -> dict | None:
    valid_date = block.get("date")
    official_text = block.get("text") or ""
    if not valid_date or not official_text.strip():
        return None

    area_candidates = macro_projected_candidates_for_text(official_text)
    sentences = split_osmer_projection_sentences(official_text)
    official_text_has_weather_signal = has_projected_weather_signal(official_text)
    for sentence in sentences or [official_text]:
        if official_text_has_weather_signal and not has_projected_weather_signal(sentence):
            continue
        area_ids = projected_area_ids_for_text(sentence)
        if not area_ids:
            area_ids = set(OSMER_PROJECTED_ALL_AREAS)
        condition = infer_condition_from_text(sentence, "Poco nuvoloso")
        if normalize_for_search(condition) == "vento":
            continue
        severity = projected_condition_severity(condition)

        for area_id in area_ids:
            current = area_candidates.get(area_id)
            if current and current.get("locked"):
                continue
            if not current or severity > current["severity"]:
                area_candidates[area_id] = {
                    "condition": condition,
                    "text": sentence,
                    "severity": severity,
                    "risk_index": None,
                    "projection_source": OSMER_PROJECTED_AREA_META.get(area_id, {}).get("projection_source", "region"),
                    "overlays": [],
                    "locked": False,
                }

    if not area_candidates:
        return None

    fallback_condition = infer_condition_from_text(official_text, "Poco nuvoloso")
    fallback_text = official_text
    areas9 = {}
    for area_id, meta in OSMER_PROJECTED_AREA_META.items():
        candidate = area_candidates.get(area_id)
        fallback_used = False
        if not candidate:
            fallback_used = True
            candidate = {
                "condition": fallback_condition,
                "text": fallback_text,
                "severity": projected_condition_severity(fallback_condition),
            }
        symbols = projected_symbols_for_condition(candidate["condition"])
        projection_source = candidate.get("projection_source") or meta["projection_source"]
        overlays = candidate.get("overlays") or []
        risk_index = candidate.get("risk_index")
        areas9[area_id] = {
            "id": area_id,
            "name": meta["name"],
            "source_kind": "official_projected",
            "projection_source": projection_source,
            "valid_date": valid_date,
            "date_source": block.get("date_source"),
            "text": candidate["text"],
            "official_text": official_text,
            "projected_condition": candidate["condition"],
            "risk_index": risk_index,
            "wind_alert": bool(candidate.get("wind_alert") or overlays),
            "overlays": overlays,
            "symbols": symbols,
            "dominant_condition": projected_dominant_condition(symbols),
        }
        areas9[area_id]["decision_trace"] = osmer_interpreter.build_official_projected_area_trace(
            area_id=area_id,
            candidate=candidate,
            projection_source=projection_source,
            block=block,
            fallback_used=fallback_used,
        )

    decision_trace = osmer_interpreter.build_official_projected_day_trace(
        block=block,
        areas9=areas9,
        candidate_count=len(area_candidates),
    )

    return {
        "id": f"official_projected:{valid_date}",
        "valid_date": valid_date,
        "day_label": block.get("date_label") or "",
        "source_kind": "official_projected",
        "date_source": block.get("date_source"),
        "regional": {
            "text": official_text,
            "source_kind": "official_projected",
        },
        "areas9": areas9,
        "fasce4": {},
        "decision_trace": decision_trace,
        "quality": {
            "all_nodes_present": True,
            "missing_nodes": [],
            "all_fasce_present": False,
            "missing_fasce": list(parser_osmer.REQUIRED_FASCE),
            "confidence": "media",
            "projection": True,
        },
    }

def complete_osmer_structured_with_official_projections(osmer_structured: dict | None, official_blocks: list[dict]) -> dict | None:
    dated_blocks = date_osmer_forecast_blocks(official_blocks or [])
    projected_days = [
        day
        for day in (build_official_projected_day(block) for block in dated_blocks)
        if day
    ]

    if not osmer_structured and not projected_days:
        return None

    base = dict(osmer_structured or {})
    existing_days = list(base.get("days") or [])
    existing_dates = {
        day.get("valid_date")
        for day in existing_days
        if day.get("valid_date") and day.get("areas9")
    }
    added_days = [
        day for day in projected_days
        if day.get("valid_date") not in existing_dates
    ]

    if not added_days and osmer_structured:
        return osmer_structured

    merged_days = sorted([*existing_days, *added_days], key=lambda day: day.get("valid_date") or "")
    base.update(
        {
            "id_emissione": base.get("id_emissione") or "official_projected",
            "source_status": base.get("source_status") or "official_projected",
            "fonte": base.get("fonte") or "official_projected",
            "parser_version": base.get("parser_version") or parser_osmer.PARSER_VERSION,
            "schema_version": base.get("schema_version") or parser_osmer.SCHEMA_VERSION,
            "days": merged_days,
            "projection": osmer_interpreter.build_projection_merge_trace(
                existing_dates=existing_dates,
                projected_days=projected_days,
                added_days=added_days,
            ),
            "quality": {
                **(base.get("quality") or {}),
                "days_count": len(merged_days),
                "has_official_projected_days": bool(added_days),
            },
        }
    )

    return base

def build_osmer_text_forecast(osmer_official: dict | None, limit: int = 5) -> dict | None:
    if not osmer_official:
        return None

    official = osmer_official.get("it") or osmer_official.get("fur") or {}
    blocks = date_osmer_forecast_blocks(official.get("forecasts") or [])

    if not blocks:
        return None

    forecast = []
    daily_time = []
    daily_max = []
    daily_min = []
    daily_codes = []
    today = datetime.now().date()

    for index, block in enumerate(blocks[:limit]):
        date_str = block.get("date") or (today + timedelta(days=index)).isoformat()
        condition = infer_condition_from_text(block.get("text") or "")

        forecast.append(
            {
                "date": date_str,
                "date_source": block.get("date_source"),
                "date_label": block.get("date_label") or "",
                "condition": condition,
                "weathercode": None,
                "min_temp": None,
                "max_temp": None,
                "official_text": block.get("text") or "",
                "emission": block.get("emission") or "",
            }
        )
        daily_time.append(date_str)
        daily_max.append(None)
        daily_min.append(None)
        daily_codes.append(None)

    return {
        "forecast": forecast,
        "daily": {
            "time": daily_time,
            "temperature_2m_max": daily_max,
            "temperature_2m_min": daily_min,
            "weathercode": daily_codes,
            "weather_code": daily_codes,
        },
    }

def get_real_forecast(
    city: str,
    lat: float = None,
    lon: float = None,
    *,
    allow_open_meteo: bool = True,
):
    lat = normalize_optional_float(lat)
    lon = normalize_optional_float(lon)
    provider_mode = "mixed" if allow_open_meteo else "osmer-only"
    cache_key = make_cache_key(
        WEATHER_PIPELINE_VERSION,
        "forecast",
        provider_mode,
        city,
        lat,
        lon,
    )
    cached = get_from_cache(forecast_cache, cache_key, WEATHER_FORECAST_CACHE_TTL)

    if cached:
        return cached

    if lat is None or lon is None:
        lat, lon = geocode_city(city, allow_open_meteo=allow_open_meteo)

    if lat is None or lon is None:
        return None

    osmer_official = get_osmer_official_weather(city, lat, lon)
    osmer_structured = fetch_osmer_structured_forecast("it") if is_fvg_location(city, lat, lon) else None

    if allow_open_meteo:
        try:
            data = open_meteo_forecast(
                lat,
                lon,
                WEATHER_SUPPORT_TIMEOUT if osmer_official else WEATHER_REQUEST_TIMEOUT,
            )
            daily = data.get("daily") or {}
        except Exception as e:
            print("Errore forecast Open-Meteo:", e)
            data = {}
            daily = {}
    else:
        data = {}
        daily = {}

    dates = daily.get("time") or []
    tmax = daily.get("temperature_2m_max") or []
    tmin = daily.get("temperature_2m_min") or []
    codes = daily.get("weather_code") or []
    has_open_meteo = bool(dates)

    today = datetime.now().strftime("%Y-%m-%d")
    indices = list(range(len(dates)))

    if dates and dates[0] == today:
        indices = indices[1:]

    indices = indices[:5]

    forecast = []
    daily_time = []
    daily_max = []
    daily_min = []
    daily_codes = []
    osmer_blocks = date_osmer_forecast_blocks(((osmer_official or {}).get("it") or {}).get("forecasts") or [])
    osmer_blocks_by_date = build_osmer_forecast_block_index(osmer_blocks)
    osmer_structured = complete_osmer_structured_with_official_projections(osmer_structured, osmer_blocks)

    for output_index, i in enumerate(indices):
        max_temp = int(round(tmax[i])) if i < len(tmax) and tmax[i] is not None else None
        min_temp = int(round(tmin[i])) if i < len(tmin) and tmin[i] is not None else None
        code = codes[i] if i < len(codes) else None
        official_block = osmer_blocks_by_date.get(dates[i]) or {}
        official_text = official_block.get("text") or ""
        condition = (
            infer_condition_from_text(official_text, map_weather_code(code, 0))
            if official_text
            else map_weather_code(code, 0)
        )

        forecast.append(
            {
                "date": dates[i],
                "date_source": official_block.get("date_source") or "open_meteo_date",
                "date_label": official_block.get("date_label") or "",
                "condition": condition,
                "weathercode": code,
                "min_temp": min_temp,
                "max_temp": max_temp,
                "official_text": official_text,
                "emission": official_block.get("emission") or "",
            }
        )

        daily_time.append(dates[i])
        daily_max.append(max_temp)
        daily_min.append(min_temp)
        daily_codes.append(code)

    if not forecast:
        osmer_forecast = build_osmer_text_forecast(osmer_official)

        if not osmer_forecast:
            stale = get_stale_from_cache(forecast_cache, cache_key, WEATHER_STALE_TTL)
            if stale:
                return add_data_quality(stale, "cached_verified", "stale")
            return None

        forecast = osmer_forecast["forecast"]
        daily_time = osmer_forecast["daily"]["time"]
        daily_max = osmer_forecast["daily"]["temperature_2m_max"]
        daily_min = osmer_forecast["daily"]["temperature_2m_min"]
        daily_codes = osmer_forecast["daily"]["weathercode"]

    forecast = attach_osmer_structured_days_to_forecast(forecast, osmer_structured)

    osmer_station = (osmer_official or {}).get("station") or {}
    model_support = {
        "open_meteo": bool(has_open_meteo),
        "daily": bool(daily),
    }
    primary_source = "arpa_fvg_osmer" if osmer_official else "open_meteo"
    fallback_used = "open_meteo" if osmer_official and has_open_meteo else None
    source = build_weather_sources(
        city,
        lat,
        lon,
        primary_source,
        include_open_meteo=allow_open_meteo,
    )
    source["fallback_used"] = fallback_used
    source["primary_source"] = primary_source
    source["model_support"] = model_support
    source["station"] = osmer_station.get("station") if osmer_station else None
    source["station_scope"] = osmer_station.get("station_scope") if osmer_station else None
    source["station_distance_km"] = osmer_station.get("station_distance_km") if osmer_station else None
    source["official_scope"] = (
        "osmer_bulletin" if osmer_official else "none"
    )

    result = {
        "city": city,
        "forecast": forecast,
        "daily": {
            "time": daily_time,
            "temperature_2m_max": daily_max,
            "temperature_2m_min": daily_min,
            "weathercode": daily_codes,
            "weather_code": daily_codes,
        },
        "official": osmer_official,
        "osmer_structured": osmer_structured,
        "source": source,
        "fallback_used": fallback_used,
        "primary_source": primary_source,
        "model_support": model_support,
        "cache": {
            "status": "fresh",
            "ttl_seconds": WEATHER_FORECAST_CACHE_TTL,
            "generated_at": datetime.now().isoformat(),
        },
    }
    result = add_data_quality(
        result,
        "official" if osmer_official else "model",
        "fresh",
        "arpa_fvg_osmer" if osmer_official else "open_meteo",
    )

    set_cache(forecast_cache, cache_key, result)
    return result


def get_osmer_only_forecast(city: str, lat: float = None, lon: float = None):
    """Return the official OSMER bulletin using an isolated cache namespace."""

    return get_real_forecast(
        city,
        lat,
        lon,
        allow_open_meteo=False,
    )

def normalize_for_search(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip().lower())


def clear_weather_caches() -> None:
    """Invalidate only the caches owned by this weather engine."""

    forecast_cache.clear()
    osmer_cache.clear()
    open_meteo_raw_cache.clear()
    open_meteo_error_cache.clear()
