from __future__ import annotations

import hashlib
import json
import math
import os
import re
import threading
import time
import unicodedata
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, wait
from datetime import datetime, timedelta, timezone
from html import unescape
from typing import Any, Optional
from urllib.parse import unquote, urljoin, urlsplit
from zoneinfo import ZoneInfo

import requests

from app.events.http_client import get_with_single_transient_retry
from app.infrastructure.firebase import get_firestore_client
from app.infrastructure.open_meteo_policy import open_meteo_enabled
from app.events.guarded_feed import event_source_feed_mode, load_guarded_official_events
from app.services.location import LocationCatalog

# Migrated from the legacy backend as an isolated Eventi domain.
# Keep source adapters and ranking behavior compatible while UI3 replaces the monolith.


OPEN_METEO_GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search"


TURISMOFVG_EVENTS_URL = "https://www.turismofvg.it/eventi"


TURISMOFVG_EVENTS_FILTER_URL = "https://www.turismofvg.it/events20"


TURISMOFVG_BASE_URL = "https://www.turismofvg.it"


SAGREFVG_BASE_URL = "https://sagrefvg.it"


SAGREFVG_EVENTS_URL = "https://sagrefvg.it/sagris/"


SAGREFVG_API_EVENTS_URL = "https://sagrefvg.it/wp-json/tribe/events/v1/events"


PROLOCOFVG_BASE_URL = "https://prolocoregionefvg.it"


PROLOCOFVG_EVENTS_URL = "https://prolocoregionefvg.it/eventi-delle-associate/"


PAESIINFESTA_BASE_URL = "https://paesiinfesta.com"


PAESIINFESTA_EVENTS_URLS = [
    "https://paesiinfesta.com/sagre-in-friuli-venezia-giulia-e-veneto-orientale/",
    "https://paesiinfesta.com/rievocazioni-storiche/",
]


ANTEPRIMASAGRE_BASE_URL = "https://www.anteprimasagre.it"


ANTEPRIMASAGRE_EVENTS_URL = "https://www.anteprimasagre.it/"


EVENTIFVG_BASE_URL = "https://www.eventifvg.it"


EVENTIFVG_EVENTS_URL = "https://www.eventifvg.it/"


CACHE_TTL = 600


EVENTS_CACHE_TTL = 1800


EVENTS_STALE_TTL = 2 * 60 * 60


EVENTS_PERSISTENT_STALE_TTL = 48 * 60 * 60


EVENTS_PRELOAD_LIMIT = 100


EVENTS_RESPONSE_MAX = 100


EVENTS_SOURCE_COLLECTION_TIMEOUT = 12


EVENTS_REFRESHING_STALE_SECONDS = 90


EVENTS_REFRESH_OUTCOME_TTL = 60


EVENTS_CACHE_VERSION = "v41-canonical-event-identity"


# Contratto esposto anche al client. Quando cambia una regola che modifica
# l'identita delle card, una raccolta parziale nuova non deve lasciare visibile
# per ore una cache del dispositivo costruita con le regole precedenti.
EVENTS_RESPONSE_CONTRACT_VERSION = "canonical-events-v2"


# La chiave della raccolta aggregata resta compatibile durante il cambio di
# contratto: i payload gia salvati vengono deduplicati e qualificati in lettura
# da clone_local_events_response_with_cache, mentre il refresh live ricostruisce
# progressivamente la scheda canonica completa. In questo modo un rallentamento
# simultaneo delle fonti non rende vuota la sezione Eventi dopo un deploy.
LOCAL_EVENTS_RESPONSE_CACHE_VERSION = "v40-without-anteprima-sagre"


EVENTS_CACHE_REPLACE_MIN_RATIO = 0.75


GEOCODE_CACHE_TTL = 7 * 24 * 60 * 60


SAGREFVG_DETAIL_LIMIT = 14


SAGREFVG_DETAIL_TIMEOUT = 4


SAGREFVG_DETAIL_CACHE_TTL = 6 * 60 * 60


TURISMOFVG_DETAIL_LIMIT = 5


TURISMOFVG_MAX_PAGES_PER_SPEC = 20


PROLOCOFVG_DETAIL_LIMIT = 12


PAESIINFESTA_DETAIL_LIMIT = 14


ANTEPRIMASAGRE_DETAIL_LIMIT = 8


EVENTIFVG_DETAIL_LIMIT = 6


SAGREFVG_DETAIL_ERROR_CACHE_TTL = 10 * 60


EVENTS_NEARBY_RADIUS_KM = 20


EVENTS_NEARBY_SOURCE_MUNICIPALITY_LIMIT = 12


EVENTS_NEARBY_PROMOTION_KM = 15


EVENTS_LOCAL_LEAD_COUNT = 6


EVENTS_NEARBY_PROMOTION_LIMIT = 10


EVENTS_UPCOMING_WINDOW_DAYS = 15


HTTP_USER_AGENT = "MeteoFriul/0.1 (https://meteofriul-1-0-1.onrender.com; local development)"


EVENT_IMAGE_CACHE_DIR = os.path.join(os.path.dirname(__file__), "cache", "event_images")


EVENT_IMAGE_MAX_BYTES = 3 * 1024 * 1024


EVENT_IMAGE_MIN_BYTES = 4 * 1024


events_cache = {}


geocode_cache = {}


sagrefvg_detail_cache = {}


turismofvg_detail_cache = {}


turismofvg_locality_cache = {}


prolocofvg_detail_cache = {}


paesiinfesta_detail_cache = {}


anteprimasagre_detail_cache = {}


eventifvg_detail_cache = {}


sagrefvg_detail_error_cache = {}


local_events_response_cache = {}


local_events_refreshing = set()


local_events_refresh_started = {}


local_events_refresh_outcomes = {}


local_events_refresh_lock = threading.Lock()


fvg_municipality_catalog = LocationCatalog()


def get_from_cache(cache, key, ttl=CACHE_TTL):
    entry = cache.get(key)
    if not entry:
        return None

    data, timestamp = entry

    if datetime.now() - timestamp > timedelta(seconds=ttl):
        cache.pop(key, None)
        return None

    return data


def get_cache_entry(cache, key):
    entry = cache.get(key)

    if not entry:
        return None, None

    return entry


def cache_age_seconds(entry) -> float | None:
    if not entry:
        return None

    _, timestamp = entry
    if timestamp is None:
        return None

    return (datetime.now() - timestamp).total_seconds()


def set_cache(cache, key, data):
    cache[key] = (data, datetime.now())


def set_cache_at(cache, key, data, timestamp):
    cache[key] = (data, timestamp or datetime.now())


def make_cache_key(*parts):
    return "|".join(str(part).strip().lower() for part in parts)


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
}


EVENT_PLACE_COORDS = {
    "azzano decimo": {"lat": 45.9092, "lon": 12.7144},
    "borgomeduna": {"lat": 45.9468, "lon": 12.6714},
    "camolli": {"lat": 45.9994, "lon": 12.5386},
    "cervignano del friuli": {"lat": 45.8217, "lon": 13.3397},
    "codroipo": {"lat": 45.9637, "lon": 12.9797},
    "cordenons": {"lat": 45.9836, "lon": 12.7004},
    "cormons": {"lat": 45.9602, "lon": 13.4662},
    "corno di rosazzo": {"lat": 45.9958, "lon": 13.4391},
    "fiume veneto": {"lat": 45.9281, "lon": 12.7381},
    "gemona del friuli": {"lat": 46.2775, "lon": 13.1403},
    "gorizia": {"lat": 45.9402, "lon": 13.6202},
    "lignano": {"lat": 45.6792, "lon": 13.1114},
    "lignano sabbiadoro": {"lat": 45.6792, "lon": 13.1114},
    "palmanova": {"lat": 45.9064, "lon": 13.3097},
    "porcia": {"lat": 45.9597, "lon": 12.6167},
    "pordenone": {"lat": 45.9567, "lon": 12.6605},
    "prepotto": {"lat": 46.0459, "lon": 13.4802},
    "romans d isonzo": {"lat": 45.8891, "lon": 13.4443},
    "ronchi dei legionari": {"lat": 45.8275, "lon": 13.5018},
    "sacile": {"lat": 45.9541, "lon": 12.5027},
    "tarvisio": {"lat": 46.5050, "lon": 13.5786},
    "torre di pordenone": {"lat": 45.9708, "lon": 12.6626},
    "trieste": {"lat": 45.6495, "lon": 13.7768},
    "udine": {"lat": 46.0619, "lon": 13.2378},
    "villorba": {"lat": 45.7333, "lon": 12.2333},
}


EVENT_PLACE_ALIASES = {
    "borgomeduna pordenone": "borgomeduna",
    "camolli di sacile": "camolli",
    "corva di azzano decimo": "azzano decimo",
    "sant antonio di porcia": "porcia",
}


FVG_BOUNDS = {
    "lat_min": 45.55,
    "lat_max": 46.65,
    "lon_min": 12.30,
    "lon_max": 14.00,
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
}


def get_osmer_station_reference(station_name: str) -> dict | None:
    normalized = normalize_place_name(station_name)

    for station in OSMER_STATION_REFERENCES:
        names = [station.get("name"), *(station.get("aliases") or [])]
        if normalized in {normalize_place_name(name) for name in names if name}:
            return station

    return None


def geocode_city(city: str):
    coords = CITY_COORDS.get(city)
    if coords:
        return coords["lat"], coords["lon"]

    mapped_station_name = FVG_LOCALITY_STATION_MAP.get(normalize_place_name(city))
    if mapped_station_name:
        station = get_osmer_station_reference(mapped_station_name)
        if station:
            return station["lat"], station["lon"]

    if not open_meteo_enabled():
        return None, None

    try:
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


def normalize_event_place_key(value: str) -> str:
    text = unicodedata.normalize("NFKD", str(value or "").lower())
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def event_place_coordinate_candidates(place: str) -> list[str]:
    clean_place = clean_event_text(place or "")
    candidates = [normalize_event_place_key(clean_place)]

    for part in re.split(r"[,;/|–—-]+", clean_place):
        key = normalize_event_place_key(part)
        if key:
            candidates.append(key)

    return list(dict.fromkeys(candidate for candidate in candidates if candidate))


def lookup_event_place_coords(place: str):
    for candidate in event_place_coordinate_candidates(place):
        alias = EVENT_PLACE_ALIASES.get(candidate, candidate)
        coords = EVENT_PLACE_COORDS.get(alias)

        if coords:
            return coords["lat"], coords["lon"]

    return None, None


def geocode_event_place_direct(place: str):
    if not open_meteo_enabled():
        return None, None

    try:
        params = {
            "name": clean_event_text(place),
            "count": 5,
            "language": "it",
            "format": "json",
        }

        res = requests.get(OPEN_METEO_GEOCODE_URL, params=params, timeout=8)
        res.raise_for_status()

        data = res.json()
        results = [
            result
            for result in (data.get("results") or [])
            if result.get("country_code") in {"IT", "SI", "AT", "HR"}
        ]

        if not results:
            return None, None

        requested_key = normalize_event_place_key(place)
        results.sort(
            key=lambda item: (
                0 if normalize_event_place_key(item.get("name")) == requested_key else 1,
                0 if "friuli" in (item.get("admin1") or "").lower() else 1,
                -(item.get("population") or 0),
            )
        )

        best = results[0]
        return best.get("latitude"), best.get("longitude")
    except Exception as e:
        print("Errore geocoding evento:", e)
        return None, None


def geocode_event_place(place: str):
    clean_place = clean_event_text(place or "")

    if len(clean_place) < 3:
        return None, None

    lat, lon = lookup_event_place_coords(clean_place)
    if lat is not None and lon is not None:
        return lat, lon

    cache_key = make_cache_key("event_place", clean_place)
    cached = get_from_cache(geocode_cache, cache_key, GEOCODE_CACHE_TTL)

    if cached is not None:
        return cached

    lat, lon = geocode_event_place_direct(clean_place)
    result = (lat, lon) if lat is not None and lon is not None else (None, None)
    set_cache(geocode_cache, cache_key, result)

    return result


def extract_coordinates_from_url(url: str):
    value = unquote(str(url or ""))

    patterns = [
        r"@(-?\d+(?:\.\d+)?),\s*(-?\d+(?:\.\d+)?)",
        r"!3d(-?\d+(?:\.\d+)?)!4d(-?\d+(?:\.\d+)?)",
        r"[?&](?:q|ll|query)=(-?\d+(?:\.\d+)?),\s*(-?\d+(?:\.\d+)?)",
    ]

    for pattern in patterns:
        match = re.search(pattern, value)
        if not match:
            continue

        try:
            lat = float(match.group(1))
            lon = float(match.group(2))
        except ValueError:
            continue

        if FVG_BOUNDS["lat_min"] <= lat <= FVG_BOUNDS["lat_max"] and FVG_BOUNDS["lon_min"] <= lon <= FVG_BOUNDS["lon_max"]:
            return lat, lon

    return None, None


def event_location_coordinates(event: dict):
    lat = event.get("lat") or event.get("latitude")
    lon = event.get("lon") or event.get("longitude")

    if lat is not None and lon is not None:
        try:
            return float(lat), float(lon)
        except (TypeError, ValueError):
            pass

    place = event.get("event_city") or event.get("place")
    return geocode_event_place(place)


def clean_event_text(value: str) -> str:
    value = re.sub(r"<script[^>]*>.*?</script>", " ", value, flags=re.IGNORECASE | re.DOTALL)
    value = re.sub(r"<style[^>]*>.*?</style>", " ", value, flags=re.IGNORECASE | re.DOTALL)
    value = re.sub(r"<[^>]+>", " ", value)
    value = unescape(value)
    value = value.replace('\u200b', '')
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def normalize_for_search(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip().lower())


def clean_event_title(title: str) -> str:
    title = clean_event_text(title)

    noise_patterns = [
        r"^eventi\s+",
        r"^scopri\s+",
        r"^leggi\s+",
        r"^vai all[a']evento\s+",
        r"^dettaglio evento\s+",
    ]

    for pattern in noise_patterns:
        title = re.sub(pattern, "", title, flags=re.IGNORECASE).strip()

    title = re.sub(r"\b\d{1,2}\s+[A-ZÀ-Üa-zà-ÿ]+\s+\d{4}\b", "", title).strip()
    title = re.sub(
        r"\b(lunedì|martedì|mercoledì|giovedì|venerdì|sabato|domenica)\b",
        "",
        title,
        flags=re.IGNORECASE,
    ).strip()
    title = re.sub(r"\s*[-–|]\s*$", "", title).strip()
    title = re.sub(r"\s+", " ", title)

    if len(title) > 90:
        title = title[:87].rstrip() + "..."

    return title


def extract_official_event_image(html: str, base_url: str) -> str | None:
    candidates = []

    def add_srcset_candidates(value: str):
        for item in re.split(r",\s+(?=\S)", str(value or "")):
            src = item.strip().split(" ", 1)[0].strip()
            if src:
                candidates.append(src)

    meta_patterns = [
        r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']',
        r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image["\']',
        r'<meta[^>]+name=["\']twitter:image["\'][^>]+content=["\']([^"\']+)["\']',
        r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+name=["\']twitter:image["\']',
    ]

    for pattern in meta_patterns:
        match = re.search(pattern, html, re.IGNORECASE | re.DOTALL)
        if match:
            candidates.append(match.group(1))

    for image_match in re.finditer(
        r'<img[^>]+src=["\']([^"\']+)["\'][^>]*>',
        html,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        candidates.append(image_match.group(1))

    for attr_match in re.finditer(
        r'<(?:img|source|picture)[^>]+(?:srcset|data-srcset|data-src|data-original)=["\']([^"\']+)["\'][^>]*>',
        html,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        add_srcset_candidates(attr_match.group(1))

    for style_match in re.finditer(
        r'url\(["\']?([^"\')]+)["\']?\)',
        html,
        flags=re.IGNORECASE,
    ):
        candidates.append(style_match.group(1))

    blocked_fragments = [
        "advert",
        "advertisement",
        "banner",
        "logo",
        "icon",
        "loader",
        "loading",
        "placeholder",
        "pubblic",
        "sponsor",
        "spinner",
        "sprite",
        "avatar",
        "facebook",
        "instagram",
        "twitter",
    ]

    usable_candidates = []

    for index, src in enumerate(candidates):
        src = unescape(src or "").strip()
        src_lower = normalize_for_search(src)

        if not src or src.startswith("data:"):
            continue

        if any(fragment in src_lower for fragment in blocked_fragments):
            continue

        if not (
            re.search(r"\.(?:jpe?g|jfif|png|webp)(?:\?|$)", src_lower)
            or re.search(r"[?&]ext=\.?(?:jpe?g|jfif|png|webp)(?:&|$)", src_lower)
            or "proxyvfs.axd" in src_lower
        ):
            continue

        priority = 0
        if "proxyvfs.axd" in src_lower:
            priority += 10
        if "main,image" in src_lower:
            priority += 20
        if "main,thumb" in src_lower:
            priority -= 5

        usable_candidates.append((priority, -index, src))

    if usable_candidates:
        usable_candidates.sort(reverse=True)
        return urljoin(base_url, usable_candidates[0][2])

    return None


def event_image_extension(url: str, content_type: str = "") -> str:
    content_type = normalize_for_search(content_type)

    if "webp" in content_type:
        return ".webp"

    if "png" in content_type:
        return ".png"

    if "jpeg" in content_type or "jpg" in content_type or "jfif" in content_type:
        return ".jpg"

    url_path = str(url or "").split("?", 1)[0].lower()
    match = re.search(r"\.(jpe?g|png|webp)$", url_path)

    if match:
        ext = match.group(1)
        return ".jpg" if ext == "jpeg" else f".{ext}"

    query_ext = re.search(r"[?&]ext=\.?(jpe?g|jfif|png|webp)(?:&|$)", str(url or "").lower())
    if query_ext:
        ext = query_ext.group(1)
        return ".jpg" if ext in ("jpeg", "jfif") else f".{ext}"

    return ".jpg"


def cache_event_image_url(image_url: str) -> str | None:
    image_url = unescape(str(image_url or "")).strip()

    if not image_url:
        return None

    if image_url.startswith("/api/event-images/"):
        return image_url

    if image_url.startswith("data:"):
        return None

    if not re.match(r"^https?://", image_url, re.IGNORECASE):
        return image_url

    image_key = hashlib.sha256(image_url.encode("utf-8")).hexdigest()[:24]
    os.makedirs(EVENT_IMAGE_CACHE_DIR, exist_ok=True)

    for ext in (".jpg", ".png", ".webp"):
        existing_path = os.path.join(EVENT_IMAGE_CACHE_DIR, f"{image_key}{ext}")
        if os.path.exists(existing_path):
            if os.path.getsize(existing_path) < EVENT_IMAGE_MIN_BYTES:
                try:
                    os.remove(existing_path)
                except OSError:
                    pass
                continue

            return f"/api/event-images/{image_key}{ext}"

    try:
        response = requests.get(
            image_url,
            headers={"User-Agent": HTTP_USER_AGENT, "Accept": "image/avif,image/webp,image/png,image/jpeg,*/*"},
            timeout=8,
            stream=True,
        )
        response.raise_for_status()

        content_type = response.headers.get("content-type", "")
        if not normalize_for_search(content_type).startswith("image/"):
            return image_url

        ext = event_image_extension(image_url, content_type)
        file_path = os.path.join(EVENT_IMAGE_CACHE_DIR, f"{image_key}{ext}")
        total = 0

        with open(file_path, "wb") as image_file:
            for chunk in response.iter_content(chunk_size=65536):
                if not chunk:
                    continue

                total += len(chunk)
                if total > EVENT_IMAGE_MAX_BYTES:
                    image_file.close()
                    try:
                        os.remove(file_path)
                    except OSError:
                        pass
                    return image_url

                image_file.write(chunk)

        if total == 0:
            try:
                os.remove(file_path)
            except OSError:
                pass
            return image_url

        if total < EVENT_IMAGE_MIN_BYTES:
            try:
                os.remove(file_path)
            except OSError:
                pass
            return None

        return f"/api/event-images/{image_key}{ext}"
    except Exception as error:
        print("Errore cache immagine evento:", image_url, error)
        return image_url


def is_event_image_api_path(value: str) -> bool:
    return bool(re.match(r"^/api/event-images/[a-f0-9]{24}\.(?:jpg|png|webp)$", str(value or "")))


def event_image_cache_path_from_api_path(image_path: str) -> str | None:
    if not is_event_image_api_path(image_path):
        return None

    filename = str(image_path).rsplit("/", 1)[-1]
    return os.path.join(EVENT_IMAGE_CACHE_DIR, filename)


def event_image_cache_file_exists(image_path: str) -> bool:
    file_path = event_image_cache_path_from_api_path(image_path)
    if not file_path or not os.path.exists(file_path):
        return False

    try:
        return os.path.getsize(file_path) >= EVENT_IMAGE_MIN_BYTES
    except OSError:
        return False


def should_use_event_image_api_cache() -> bool:
    return not bool(os.getenv("K_SERVICE"))


def normalize_event_images_for_response(response: dict | None) -> dict:
    cloned = dict(response or {})
    events = cloned.get("events")
    if not isinstance(events, list):
        return cloned

    normalized_events = []
    for event in events:
        if not isinstance(event, dict):
            normalized_events.append(event)
            continue

        normalized_event = dict(event)
        image = str(normalized_event.get("image") or "").strip()
        original_image = str(normalized_event.get("image_original") or "").strip()

        if is_event_image_api_path(image) and not event_image_cache_file_exists(image):
            if original_image:
                normalized_event["image"] = original_image
            else:
                normalized_event.pop("image", None)

        normalized_events.append(normalized_event)

    cloned["events"] = normalized_events
    return cloned


def cache_selected_event_images(events: list[dict]):
    for event in events or []:
        original_image = event.get("image")
        if re.match(r"^https?://", str(original_image or ""), re.IGNORECASE):
            event["image_original"] = original_image
            if not should_use_event_image_api_cache():
                event["image"] = original_image
                continue

        cached_image = cache_event_image_url(original_image)
        if cached_image:
            event["image"] = cached_image
        elif original_image:
            event.pop("image", None)

    return events


def enrich_selected_event_images(events: list[dict]):
    headers = {"User-Agent": HTTP_USER_AGENT}

    for event in events or []:
        if event.get("image") or not event.get("url"):
            continue

        source = normalize_for_search(event.get("source"))
        detail = {}

        if source == "paesi in festa":
            detail = fetch_paesiinfesta_event_detail(event["url"], headers)
        elif source == "sagrefvg":
            detail = fetch_sagrefvg_event_detail(event["url"], headers)
        elif source == "anteprima sagre":
            detail = fetch_generic_event_detail(
                event["url"],
                headers,
                anteprimasagre_detail_cache,
                "anteprimasagre_detail",
                ANTEPRIMASAGRE_BASE_URL,
            )
        elif source == "pro loco fvg":
            detail = fetch_generic_event_detail(
                event["url"],
                headers,
                prolocofvg_detail_cache,
                "prolocofvg_detail",
                PROLOCOFVG_BASE_URL,
            )
        elif source == "eventifvg":
            detail = fetch_generic_event_detail(
                event["url"],
                headers,
                eventifvg_detail_cache,
                "eventifvg_detail",
                EVENTIFVG_BASE_URL,
            )

        if detail.get("image"):
            event["image"] = detail["image"]

    return events


def is_valid_event_place(place: str, city: str = None) -> bool:
    clean_place = clean_event_text(place or "")
    place_search = normalize_for_search(clean_place)

    if not (2 < len(clean_place) <= 35):
        return False

    if any(word in place_search for word in ("href", "http", "www")):
        return False

    aliases = city_aliases(city) if city else []
    has_city_alias = text_contains_alias(clean_place, aliases) if aliases else False
    has_province = bool(re.search(r"\b(?:ud|pn|go|ts)\b", place_search, re.IGNORECASE))

    if has_city_alias or has_province:
        return True

    words = re.findall(r"[a-z0-9à-ÿ]+", place_search, flags=re.IGNORECASE)
    generic_words = {
        "tema",
        "diversi",
        "diverse",
        "per",
        "con",
        "dalle",
        "dalla",
        "alle",
        "alla",
        "apertura",
        "programma",
        "evento",
        "eventi",
        "giorni",
        "ingresso",
    }

    if len(words) > 3:
        return False

    if len(words) >= 3 and sum(1 for word in words if word in generic_words) >= 2:
        return False

    return True


def extract_event_place_candidate(context: str, city: str = None):
    clean = clean_event_text(context)

    patterns = [
        r"\b(?:luogo|localit\u00e0|comune)\s*[:\-]\s*([A-Za-z\u00c0-\u00ff'\u2019\s().-]{2,40})",
        r"\ba\s+([A-Za-z\u00c0-\u00ff'\u2019\s().-]{2,32})\b",
    ]


    stop_words = [
        " la ",
        " il ",
        " lo ",
        " gli ",
        " le ",
        " una ",
        " un ",
        " dal ",
        " del ",
        " della ",
        " di ",
        " che ",
    ]

    for pattern in patterns:
        match = re.search(pattern, clean, re.IGNORECASE)
        if match:
            place = match.group(1).strip(" .,;:-")
            place = re.split(r"\s{2,}|[|–—•]", place)[0].strip(" .,;:-")

            lowered = f" {normalize_for_search(place)} "
            for stop in stop_words:
                if stop in lowered and len(place.split()) > 2:
                    place = ""
                    break

            if is_valid_event_place(place, city):
                return place

    return None


def city_aliases(city: str):
    c = normalize_for_search(city)

    aliases = [c]

    aliases_map = {
        "lignano": ["lignano sabbiadoro"],
        "lignano sabbiadoro": ["lignano"],
        "udine": ["udin"],
        "udin": ["udine"],
        "pordenone": ["pordenon"],
        "pordenon": ["pordenone"],
        "gorizia": ["gurize"],
        "gurize": ["gorizia"],
        "trieste": ["triest"],
        "triest": ["trieste"],
        "tarvisio": ["tarvis"],
    }

    aliases.extend(aliases_map.get(c, []))

    return list(dict.fromkeys([a for a in aliases if a]))


def extract_event_links(html: str):
    links = []

    pattern = re.compile(
        r'<a[^>]+href=["\']([^"\']*/eventi/[^"\']+)["\'][^>]*>(.*?)</a>',
        re.IGNORECASE | re.DOTALL,
    )

    for match in pattern.finditer(html):
        href = match.group(1)
        inner_html = match.group(2)

        title = clean_event_title(inner_html)

        if not title or len(title) < 4:
            continue

        lowered = normalize_for_search(title)

        blocked_titles = [
            "eventi",
            "events",
            "vai all evento",
            "vai all'evento",
            "go to",
            "scopri di più",
            "leggi tutto",
        ]

        if lowered in blocked_titles:
            continue

        extracted_date = None
        # Try to find EvntDate div first
        date_badge_match = re.search(r'<div[^>]+class=["\']EvntDate["\'][^>]*>(.*?)</div>', inner_html, re.IGNORECASE | re.DOTALL)
        if date_badge_match:
            extracted_date = clean_event_text(date_badge_match.group(1))

        # If not found, try to find any date pattern in inner_html
        if not extracted_date:
            months_pattern = r"(?:gennaio|febbraio|marzo|aprile|maggio|giugno|luglio|agosto|settembre|ottobre|novembre|dicembre|gen|feb|mar|apr|mag|giu|lug|ago|set|ott|nov|dic)"
            date_match = re.search(rf"\b\d{{1,2}}\s+{months_pattern}(?:\s+\d{{4}})?\b", clean_event_text(inner_html), re.IGNORECASE)
            if date_match:
                extracted_date = date_match.group(0)

        url = urljoin(TURISMOFVG_BASE_URL, href)

        links.append(
            {
                "title": title,
                "url": url,
                "extracted_date": extracted_date,
                "start": match.start(),
                "end": match.end(),
            }
        )

    return links


def turismofvg_topic_classification(topic_text: str) -> dict | None:
    topic_parts = [
        clean_event_text(part)
        for part in re.split(r"\s*,\s*", str(topic_text or ""))
        if clean_event_text(part)
    ]

    matches = []

    for topic_part in topic_parts:
        topic_key = normalize_for_search(topic_part)
        classification = TURISMOFVG_TOPIC_CATEGORY_MAP.get(topic_key)

        if not classification:
            continue

        result = dict(classification)
        result["category_label"] = classification.get("category_label") or topic_part
        matches.append(result)

    if not matches:
        return None

    matches.sort(key=lambda item: int(item.get("priority", 0) or 0), reverse=True)
    return matches[0]


def extract_turismofvg_card_links(html: str, *, require_explicit_year: bool = False):
    links = []
    month_names = {
        "GEN": "gennaio",
        "FEB": "febbraio",
        "MAR": "marzo",
        "APR": "aprile",
        "MAG": "maggio",
        "GIU": "giugno",
        "LUG": "luglio",
        "AGO": "agosto",
        "SET": "settembre",
        "OTT": "ottobre",
        "NOV": "novembre",
        "DIC": "dicembre",
    }

    anchor_pattern = re.compile(
        r'<a\b(?=[^>]*class=["\'][^"\']*c-eventsResults__item)'
        r'(?=[^>]*href=["\'][^"\']*(?:/eventi/|/events20/details/\d+))[^>]*>.*?</a>',
        flags=re.IGNORECASE | re.DOTALL,
    )

    for match in anchor_pattern.finditer(html):
        anchor_html = match.group(0)
        href_match = re.search(r'href=["\']([^"\']+)["\']', anchor_html, flags=re.IGNORECASE)

        if not href_match:
            continue

        title_match = re.search(
            r'<h[1-6][^>]*class=["\'][^"\']*title[^"\']*["\'][^>]*>(.*?)</h[1-6]>',
            anchor_html,
            flags=re.IGNORECASE | re.DOTALL,
        )
        # A labelled title is already isolated; removing dates/weekdays here
        # corrupts titles such as "Sabato in Astoria" or "11 settembre 2001".
        title = (clean_event_text(title_match.group(1)) if title_match
                 else clean_event_title(anchor_html)).replace('\u200b', '')

        if not title or len(title) < 4:
            continue

        extracted_date = None
        listing_day_month = None
        multiple_days_match = re.search(
            r'<span[^>]*class=["\'][^"\']*multiple_days_string[^"\']*["\'][^>]*>(.*?)</span>',
            anchor_html,
            flags=re.IGNORECASE | re.DOTALL,
        )
        if multiple_days_match:
            multiple_days = clean_event_text(multiple_days_match.group(1))
            if multiple_days:
                extracted_date = multiple_days
                if not re.search(r"\b20\d{2}\b", extracted_date):
                    extracted_date = None if require_explicit_year else f"{extracted_date} {datetime.now().year}"

        full_date_match = re.search(
            r'<div[^>]*class=["\'][^"\']*item_title[^"\']*["\'][^>]*>.*?<p>\s*<strong[^>]*>(.*?)</strong>\s*</p>',
            anchor_html,
            flags=re.IGNORECASE | re.DOTALL,
        )
        if not extracted_date and full_date_match:
            extracted_date = clean_event_text(full_date_match.group(1))

        date_badge_match = re.search(
            r'<div[^>]*class=["\'][^"\']*info_date[^"\']*["\'][^>]*>.*?'
            r'<div[^>]*class=["\'][^"\']*col1[^"\']*["\'][^>]*>\s*'
            r'<strong[^>]*>(\d{1,2})</strong>\s*<p[^>]*>([^<]+)</p>',
            anchor_html,
            flags=re.IGNORECASE | re.DOTALL,
        )
        if date_badge_match:
            day = clean_event_text(date_badge_match.group(1))
            month_key = clean_event_text(date_badge_match.group(2)).upper()[:3]
            month_name = month_names.get(month_key)
            if month_name:
                listing_day_month = f"{day} {month_name}"
                if not extracted_date and not require_explicit_year:
                    extracted_date = f"{listing_day_month} {datetime.now().year}"

        if require_explicit_year and not re.search(r"\b20\d{2}\b", extracted_date or ""):
            extracted_date = None

        place = None
        place_patterns = [
            r'<div[^>]*class=["\'][^"\']*info_location[^"\']*["\'][^>]*>.*?<strong[^>]*class=["\'][^"\']*col2[^"\']*["\'][^>]*>(.*?)</strong>',
            r'<strong[^>]*class=["\'][^"\']*col2[^"\']*["\'][^>]*>(.*?)</strong>',
            r'<div[^>]*class=["\'][^"\']*col2[^"\']*["\'][^>]*>\s*<strong[^>]*>(.*?)</strong>',
        ]
        for pattern in place_patterns:
            place_match = re.search(pattern, anchor_html, flags=re.IGNORECASE | re.DOTALL)
            if place_match:
                place = clean_event_text(place_match.group(1))
                break

        provider_categories = None
        category_patterns = [
            r'<div[^>]*class=["\'][^"\']*info_category[^"\']*["\'][^>]*>.*?<strong[^>]*class=["\'][^"\']*col2[^"\']*["\'][^>]*>(.*?)</strong>',
            r'<div[^>]*class=["\'][^"\']*col3[^"\']*["\'][^>]*title=["\']([^"\']+)["\']',
        ]
        for pattern in category_patterns:
            category_match = re.search(pattern, anchor_html, flags=re.IGNORECASE | re.DOTALL)
            if category_match:
                provider_categories = clean_event_text(category_match.group(1))
                break

        category_list = [
            clean_event_text(part)
            for part in re.split(r"\s*,\s*", provider_categories or "")
            if clean_event_text(part)
        ]
        classification = turismofvg_topic_classification(provider_categories)
        image = extract_official_event_image(anchor_html, TURISMOFVG_BASE_URL)

        item = {
            "title": title,
            "url": urljoin(TURISMOFVG_BASE_URL, unescape(href_match.group(1))),
            "extracted_date": extracted_date,
            "start": match.start(),
            "end": match.end(),
        }
        if listing_day_month:
            item["listing_day_month"] = listing_day_month
        occurrences = parse_turismofvg_discrete_occurrences(extracted_date or "")
        if occurrences:
            item["occurrences"] = occurrences

        if place:
            item["place"] = place
        if provider_categories:
            item["provider_categories"] = provider_categories
        if category_list:
            item["provider_category_list"] = category_list
        if classification:
            item["classification"] = classification
        if image:
            item["image"] = image

        links.append(item)

    return links


def extract_turismofvg_next_page_url(html: str, current_url: str) -> str | None:
    for match in re.finditer(
        r'<a\b[^>]*href=["\']([^"\']+)["\'][^>]*>(.*?)</a>',
        str(html or ""),
        flags=re.IGNORECASE | re.DOTALL,
    ):
        if "carica altri eventi" not in normalize_for_search(match.group(2)):
            continue

        next_url = urljoin(current_url, unescape(match.group(1)).strip())
        parsed = urlsplit(next_url)
        current = urlsplit(current_url)
        if (
            parsed.scheme != "https"
            or parsed.hostname != "www.turismofvg.it"
            or parsed.path not in {"/eventi", "/events20"}
            or parsed.path != current.path
            or not re.search(r"(?:^|&)page=\d+(?:&|$)", parsed.query)
        ):
            return None
        return next_url

    return None


def find_context(html: str, start: int, end: int):
    before = html[max(0, start - 1800):start]
    after = html[end:min(len(html), end + 1800)]
    return clean_event_text(before + " " + after)


def extract_date_from_context(context: str):
    clean = clean_event_text(context)

    months_pattern = r"(?:gennaio|febbraio|marzo|aprile|maggio|giugno|luglio|agosto|settembre|ottobre|novembre|dicembre|gen|feb|mar|apr|mag|giu|lug|ago|set|ott|nov|dic)"

    date_patterns = [
        rf"\bdal\s+\d{{1,2}}(?:[°º])?\s+(?:al\s+)?\d{{1,2}}(?:[°º])?\s+{months_pattern}(?:\s+\d{{4}})?\b",
        rf"\b\d{{1,2}}(?:[°º])?\s*(?:-|–|al)\s*\d{{1,2}}(?:[°º])?\s+{months_pattern}(?:\s+\d{{4}})?\b",
        rf"\b\d{{1,2}}\s+{months_pattern}\s+\d{{4}}\b",
        rf"\b\d{{1,2}}\s+{months_pattern}\b",
        rf"\b(lunedì|martedì|mercoledì|giovedì|venerdì|sabato|domenica)\s+\d{{1,2}}\s+{months_pattern}(?:\s+\d{{4}})?\b",
        r"\b(oggi|domani)\b",
    ]

    for pattern in date_patterns:
        matches = list(re.finditer(pattern, clean, re.IGNORECASE))
        if matches:
            date = matches[-1].group(0).strip(" .,;:-")
            return date[:45]

    return "Data in aggiornamento"


def format_numeric_date(value: str) -> str:
    match = re.search(r"\b(\d{1,2})/(\d{1,2})/(\d{4})\b", str(value or ""))

    if not match:
        return str(value or "").strip()

    months = [
        "",
        "gennaio",
        "febbraio",
        "marzo",
        "aprile",
        "maggio",
        "giugno",
        "luglio",
        "agosto",
        "settembre",
        "ottobre",
        "novembre",
        "dicembre",
    ]

    day = int(match.group(1))
    month = int(match.group(2))
    year = int(match.group(3))

    if month < 1 or month > 12:
        return str(value or "").strip()

    return f"{day} {months[month]} {year}"


def extract_event_date_matches(value: str):
    clean = clean_event_text(value)
    date_pattern = re.compile(
        r"\b\d{1,2}\s+[A-ZÀ-Üa-zà-ÿ]{3,12}(?:\s+\d{4})?(?:\s*(?:alle|ore)\s*\d{1,2}(?::\d{2})?)?\b",
        re.IGNORECASE,
    )

    matches = []
    seen = set()

    for match in date_pattern.finditer(clean):
        date_text = match.group(0).strip(" .,;:-")
        key = normalize_for_search(date_text)

        if key in seen:
            continue

        seen.add(key)
        matches.append(date_text)

    return matches


def parse_event_date(value: str):
    text = normalize_for_search(value)

    if not text or text == "data in aggiornamento":
        return None

    today = datetime.now().date()

    if re.search(r"\boggi\b", text):
        return today

    if re.search(r"\bdomani\b", text):
        return today + timedelta(days=1)

    numeric_match = re.search(r"\b(\d{1,2})/(\d{1,2})/(\d{4})\b", text)
    if numeric_match:
        try:
            return datetime(
                int(numeric_match.group(3)),
                int(numeric_match.group(2)),
                int(numeric_match.group(1)),
            ).date()
        except ValueError:
            return None

    normalized = unicodedata.normalize("NFKD", text)
    normalized = normalized.encode("ascii", "ignore").decode("ascii")

    month_numbers = {
        "gen": 1,
        "gennaio": 1,
        "feb": 2,
        "febbraio": 2,
        "mar": 3,
        "marzo": 3,
        "apr": 4,
        "aprile": 4,
        "mag": 5,
        "maggio": 5,
        "giu": 6,
        "giugno": 6,
        "lug": 7,
        "luglio": 7,
        "ago": 8,
        "agosto": 8,
        "set": 9,
        "sett": 9,
        "settembre": 9,
        "ott": 10,
        "ottobre": 10,
        "nov": 11,
        "novembre": 11,
        "dic": 12,
        "dicembre": 12,
    }

    match = re.search(
        r"\b(\d{1,2})\s+([a-z]{3,12})(?:\s+(\d{4}))?\b",
        normalized,
        re.IGNORECASE,
    )

    if not match:
        return None

    day = int(match.group(1))
    month = month_numbers.get(match.group(2).lower())
    year_provided = bool(match.group(3))
    year = int(match.group(3)) if match.group(3) else today.year

    if not month:
        return None

    try:
        parsed_date = datetime(year, month, day).date()

        if not year_provided and parsed_date > today + timedelta(days=180):
            parsed_date = datetime(year - 1, month, day).date()

        return parsed_date
    except ValueError:
        return None


def parse_event_date_range(value: str):
    text = normalize_for_search(value)

    if not text:
        return None, None

    today = datetime.now().date()
    normalized = unicodedata.normalize("NFKD", text)
    normalized = normalized.encode("ascii", "ignore").decode("ascii")
    month_numbers = {
        "gen": 1,
        "gennaio": 1,
        "feb": 2,
        "febbraio": 2,
        "mar": 3,
        "marzo": 3,
        "apr": 4,
        "aprile": 4,
        "mag": 5,
        "maggio": 5,
        "giu": 6,
        "giugno": 6,
        "lug": 7,
        "luglio": 7,
        "ago": 8,
        "agosto": 8,
        "set": 9,
        "sett": 9,
        "settembre": 9,
        "ott": 10,
        "ottobre": 10,
        "nov": 11,
        "novembre": 11,
        "dic": 12,
        "dicembre": 12,
    }

    full_dates = []
    for match in re.finditer(r"\b(\d{1,2})\s+([a-z]{3,12})(?:\s+(\d{4}))?\b", normalized):
        month = month_numbers.get(match.group(2).lower())
        if not month:
            continue

        year = int(match.group(3)) if match.group(3) else today.year
        try:
            full_dates.append(datetime(year, month, int(match.group(1))).date())
        except ValueError:
            continue

    if full_dates:
        first_date = full_dates[0]

        if len(full_dates) == 1:
            prefix = normalized[: normalized.find(str(full_dates[0].day))]
            day_numbers = [
                int(day)
                for day in re.findall(r"\b(\d{1,2})\b", prefix)
                if 1 <= int(day) <= 31
            ]

            if day_numbers:
                try:
                    first_date = datetime(full_dates[-1].year, full_dates[-1].month, day_numbers[0]).date()
                except ValueError:
                    first_date = full_dates[0]

        return min(first_date, full_dates[-1]), max(first_date, full_dates[-1])

    parsed = parse_event_date(value)
    return parsed, parsed


def event_dates_are_past(date_values: list[str]):
    parsed_dates = [
        parsed
        for parsed in (parse_event_date(value) for value in date_values)
        if parsed
    ]

    if not parsed_dates:
        return False

    today = datetime.now().date()
    return all(date < today for date in parsed_dates)


def filter_past_events(events: list[dict]):
    today = datetime.now().date()
    current_year = today.year
    filtered = []

    for event in events or []:
        title = str(event.get("title") or "")
        url = str(event.get("url") or "")

        title_lower = title.lower()
        if re.search(r"\b(annullat[oa]|rinviat[oa]|cancellat[oa])\b", title_lower):
            continue

        date_str = str(event.get("date") or "")
        event_date, event_end = parse_event_date_range(date_str)
        date_has_explicit_year = bool(re.search(r"\b20\d{2}\b", date_str))

        # A structured, explicit event date is more authoritative than a
        # historical year left in a WordPress slug (for example a 2026 event
        # whose URL still contains "2025-duplicate-1"). Title/URL years remain
        # a safety fallback when the date is missing or has no explicit year.
        if not date_has_explicit_year:
            years_in_title = [int(year) for year in re.findall(r"\b(20\d{2})\b", title)]
            years_in_url = [int(year) for year in re.findall(r"\b(20\d{2})\b", url)]
            all_years = years_in_title + [y for y in years_in_url if y >= 2000]

            if any(year < current_year for year in all_years):
                continue

        # Se la data non è parsabile, e l'evento proviene da SagreFVG (fonte storica) lo scartiamo
        if event.get("source") == "SagreFVG" and not event_date:
            continue

        if event_end and event_end < today:
            continue

        filtered.append(event)

    return filtered


def event_within_default_window(event: dict, today=None) -> bool:
    today = today or datetime.now().date()
    horizon = today + timedelta(days=EVENTS_UPCOMING_WINDOW_DAYS)
    start, end = parse_event_date_range(event.get("date"))

    if not start:
        return False

    event_end = end or start
    if event_end < today:
        return False

    # La finestra "prossimi" guarda l'inizio: gli stagionali gia' in corso
    # restano visibili, mentre quelli che partono oltre il limite non affollano la lista.
    return start <= horizon


def filter_default_event_window(events: list[dict]):
    today = datetime.now().date()
    return [
        event
        for event in events or []
        if event_within_default_window(event, today)
    ]


def filter_event_window_with_guarded_preview(
    events: list[dict],
    guarded_events: list[dict],
) -> list[dict]:
    filtered = filter_default_event_window(events)
    if event_source_feed_mode() != "preview":
        return filtered

    guarded_ids = {id(event) for event in guarded_events or []}
    included_ids = {id(event) for event in filtered}
    return [
        *filtered,
        *[
            {**event, "preview_outside_window": True}
            for event in events or []
            if id(event) in guarded_ids and id(event) not in included_ids
        ],
    ]


def event_quality_score(event: dict, aliases: list[str]) -> int:
    title = normalize_for_search(event.get("title"))
    place = normalize_for_search(event.get("place"))
    date = normalize_for_search(event.get("date"))

    score = 0

    if any(alias in title for alias in aliases):
        score += 4

    if any(alias in place for alias in aliases):
        score += 3

    if date and date != "data in aggiornamento":
        score += 2

    if event.get("image"):
        score += 2

    if event.get("url"):
        score += 1

    return score


EVENT_DEDUPE_STOP_WORDS = {
    "sagra",
    "sagre",
    "festa",
    "feste",
    "fiesta",
    "degli",
    "delle",
    "della",
    "dell",
    "dello",
    "nell",
    "nella",
    "nello",
    "del",
    "dal",
    "dei",
    "di",
    "da",
    "a",
    "al",
    "alla",
    "in",
    "pn",
    "ud",
    "go",
    "ts",
    "fvg",
    "friuli",
    "venezia",
    "giulia",
    "san",
    "sant",
    "santa",
    "santi",
    "santo",
    "edizione",
    "anno",
    "2026",
}


def event_dedupe_tokens(value: str) -> set[str]:
    raw_value = str(value or "")
    # Alcune fonti usano nomi grafici CamelCase (per esempio FestaInsieme),
    # mentre altre pubblicano lo stesso titolo con parole separate.
    raw_value = re.sub(
        r"(?<=[a-zà-öø-ÿ])(?=[A-ZÀ-ÖØ-Þ])",
        " ",
        raw_value,
    )
    # Conserviamo il nome del santo come segnale, ma neutralizziamo le varianti
    # grafiche S./San/Sant'. L'apostrofo va separato prima della normalizzazione,
    # altrimenti ``Sant’Agostino`` diventa il token opaco ``santagostino``.
    raw_value = re.sub(r"\bsant\s*[’']\s*(?=[A-Za-zÀ-ÖØ-öø-ÿ])", "Sant ", raw_value, flags=re.IGNORECASE)
    # Gli apostrofi non devono saldare le parole durante la normalizzazione
    # (``d’Avost`` diventava il token opaco ``davost``). Le particelle di una
    # lettera vengono poi escluse normalmente dal filtro dei token.
    raw_value = re.sub(r"[’‘ʼ']", " ", raw_value)
    # I numeri d'edizione cambiano frequentemente fra le fonti (49^/49ª) e non
    # fanno parte dell'identita editoriale dell'evento.
    raw_value = re.sub(r"\b\d{1,3}\s*(?:\^|ª|º)\b", " ", raw_value)
    normalized = unicodedata.normalize("NFKD", normalize_for_search(raw_value))
    normalized = normalized.encode("ascii", "ignore").decode("ascii")
    return {
        token
        for token in re.findall(r"[a-z0-9]+", normalized)
        if len(token) > 2 and token not in EVENT_DEDUPE_STOP_WORDS
    }


def event_contextual_identity_aliases(value: str) -> set[str]:
    """Restituisce equivalenze editoriali strette per titoli tradizionali.

    Le equivalenze qui definite non sono sufficienti da sole: il comparatore
    le usa soltanto quando Comune e intervallo di date coincidono esattamente.
    """

    raw_value = re.sub(r"[’‘ʼ']", " ", str(value or ""))
    normalized = unicodedata.normalize("NFKD", normalize_for_search(raw_value))
    normalized = normalized.encode("ascii", "ignore").decode("ascii")
    normalized = re.sub(r"[^a-z0-9]+", " ", normalized).strip()

    aliases = set()
    if re.search(r"\b(?:iv|quarte)\s+d\s+avost\b", normalized):
        aliases.add("quarte-d-avost")
    return aliases


def event_title_identity_variants(value: str) -> set[str]:
    raw_value = re.sub(r"\b\d{1,3}\s*(?:\^|ª|º)\b", " ", str(value or ""))
    parts = re.split(r"\s+[–—-]\s+", raw_value)
    candidates = [raw_value]
    if len(parts) > 1:
        # SagreFVG antepone spesso "Localita (PN) –" al titolo editoriale.
        # La coda resta un'identita forte quando luogo e date coincidono.
        candidates.append(parts[-1])
    return {
        re.sub(
            r"[^a-z0-9]+",
            "",
            unicodedata.normalize("NFKD", normalize_for_search(item))
            .encode("ascii", "ignore")
            .decode("ascii"),
        )
        for item in candidates
        if clean_event_text(item)
    }


TRADITIONAL_EVENT_CATEGORIES = {"sagra", "food_wine", "mercato"}


NON_TRADITIONAL_EVENT_CATEGORIES = {"convegni", "cultura", "famiglia", "musica", "natura", "sport"}


EVENT_LOCATION_GENERIC_TOKENS = {
    "auditorium",
    "campo",
    "centro",
    "chiesa",
    "civico",
    "comune",
    "oratorio",
    "palazzo",
    "parco",
    "piazza",
    "sala",
    "san",
    "santa",
    "santi",
    "santo",
    "teatro",
    "via",
    "viale",
    "villa",
}


def has_strong_traditional_event_signal(title: str = "", context: str = "") -> bool:
    text = normalize_for_search(f"{title} {context}")
    return bool(
        re.search(
            r"\b("
            r"sagra|sagre|fieste|pro loco|patronale|patronali|paesana|paesane|"
            r"festeggiamento|festeggiamenti|"
            r"festa patronale|festa paesana|feste tradizionali|"
            r"enogastronomia|mercato|mercatini|asparag|formaggio|formaggi|gamberi"
            r")\b",
            text,
        )
    )


def event_is_traditional(event: dict) -> bool:
    category = normalize_for_search(event.get("category"))
    category_label = normalize_for_search(event.get("category_label"))
    title = event.get("title") or ""

    if category in TRADITIONAL_EVENT_CATEGORIES:
        return True

    if category in NON_TRADITIONAL_EVENT_CATEGORIES:
        return has_strong_traditional_event_signal(title, category_label)

    return has_strong_traditional_event_signal(title, category_label)


def event_dates_overlap(event_a: dict, event_b: dict) -> bool:
    start_a, end_a = parse_event_date_range(event_a.get("date"))
    start_b, end_b = parse_event_date_range(event_b.get("date"))

    if not start_a or not start_b:
        return False

    end_a = end_a or start_a
    end_b = end_b or start_b
    return start_a <= end_b and start_b <= end_a


def event_date_ranges_match(event_a: dict, event_b: dict) -> bool:
    start_a, end_a = parse_event_date_range(event_a.get("date"))
    start_b, end_b = parse_event_date_range(event_b.get("date"))
    if not start_a or not start_b:
        return False
    return start_a == start_b and (end_a or start_a) == (end_b or start_b)


def event_location_tokens(event: dict) -> set[str]:
    return event_dedupe_tokens(" ".join(
        str(event.get(key) or "")
        for key in ("place", "event_city", "venue", "address")
    )) - EVENT_LOCATION_GENERIC_TOKENS


def shared_specific_location_tokens(event_a: dict, event_b: dict) -> set[str]:
    shared = event_location_tokens(event_a) & event_location_tokens(event_b)
    shared_municipality = (
        event_dedupe_tokens(event_a.get("event_city"))
        & event_dedupe_tokens(event_b.get("event_city"))
    )
    # Pordenone/Udine da soli non identificano una manifestazione. Villanova,
    # Torre, Castions o un'altra frazione/sede condivisa invece sono un segnale
    # territoriale specifico.
    return shared - shared_municipality - EVENT_LOCATION_GENERIC_TOKENS


GENERIC_LOCALITY_AGGREGATOR_SOURCES = {"paesi in festa"}


def is_strict_generic_locality_duplicate(
    event_a: dict,
    event_b: dict,
    title_tokens_a: set[str],
    title_tokens_b: set[str],
) -> bool:
    if not event_date_ranges_match(event_a, event_b):
        return False
    if not event_is_traditional(event_a) or not event_is_traditional(event_b):
        return False
    if not shared_specific_location_tokens(event_a, event_b):
        return False

    source_a = normalize_for_search(event_a.get("source"))
    source_b = normalize_for_search(event_b.get("source"))
    return (
        not title_tokens_a and source_a in GENERIC_LOCALITY_AGGREGATOR_SOURCES
    ) or (
        not title_tokens_b and source_b in GENERIC_LOCALITY_AGGREGATOR_SOURCES
    )


def event_places_are_related(event_a: dict, event_b: dict) -> bool:
    municipality_a = event_dedupe_tokens(event_a.get("event_city")) - EVENT_LOCATION_GENERIC_TOKENS
    municipality_b = event_dedupe_tokens(event_b.get("event_city")) - EVENT_LOCATION_GENERIC_TOKENS
    location_a = event_dedupe_tokens(" ".join(
        str(event_a.get(key) or "")
        for key in ("place", "event_city", "venue")
    )) - EVENT_LOCATION_GENERIC_TOKENS
    location_b = event_dedupe_tokens(" ".join(
        str(event_b.get(key) or "")
        for key in ("place", "event_city", "venue")
    )) - EVENT_LOCATION_GENERIC_TOKENS

    if not location_a or not location_b:
        return False

    if municipality_a and municipality_b:
        if municipality_a == municipality_b:
            return True
        # Una fonte puo indicare il Comune e l'altra una frazione. La relazione
        # e sicura soltanto quando il nome completo di una delle due localita
        # compare nei campi territoriali dell'altra fonte.
        return municipality_a <= location_b or municipality_b <= location_a

    return bool(location_a & location_b)


def events_are_probable_duplicates(event_a: dict, event_b: dict) -> bool:
    if not event_dates_overlap(event_a, event_b):
        return False

    places_related = event_places_are_related(event_a, event_b)
    def patron_name(event):
        match = re.search(r"\b(?:s\.|sant[’']|san\s)\s*([a-zà-ÿ]+)",
                          str(event.get("title") or "").lower())
        return match.group(1) if match else None
    patron = patron_name(event_a)
    if (patron and patron == patron_name(event_b)
            and event_is_traditional(event_a) and event_is_traditional(event_b)
            and places_related and event_date_ranges_match(event_a, event_b)
            and shared_specific_location_tokens(event_a, event_b)):
        return True
    municipality_a = normalize_for_search(event_a.get("event_city"))
    municipality_b = normalize_for_search(event_b.get("event_city"))
    if municipality_a and municipality_b and municipality_a != municipality_b and not places_related:
        return False

    title_tokens_a = event_dedupe_tokens(event_a.get("title"))
    title_tokens_b = event_dedupe_tokens(event_b.get("title"))
    location_tokens = (
        event_dedupe_tokens(municipality_a)
        | event_dedupe_tokens(municipality_b)
        | event_dedupe_tokens(event_a.get("place"))
        | event_dedupe_tokens(event_b.get("place"))
        | event_dedupe_tokens(event_a.get("venue"))
        | event_dedupe_tokens(event_b.get("venue"))
        | event_dedupe_tokens(event_a.get("address"))
        | event_dedupe_tokens(event_b.get("address"))
    )
    # Comune e sede possono comparire nel titolo di molti appuntamenti distinti.
    # Non devono quindi diventare da soli una prova di identità dell'evento.
    title_tokens_a -= location_tokens
    title_tokens_b -= location_tokens
    shared_title_tokens = title_tokens_a & title_tokens_b
    if (
        places_related
        and event_date_ranges_match(event_a, event_b)
        and (
            event_contextual_identity_aliases(event_a.get("title"))
            & event_contextual_identity_aliases(event_b.get("title"))
        )
    ):
        return True

    if places_related and (
        event_title_identity_variants(event_a.get("title"))
        & event_title_identity_variants(event_b.get("title"))
    ):
        return True

    if places_related and shared_title_tokens:
        if title_tokens_a == title_tokens_b:
            return True
        shorter_title = min(len(title_tokens_a), len(title_tokens_b))
        if (
            len(shared_title_tokens) >= 2
            and shorter_title > 0
            and len(shared_title_tokens) / shorter_title >= 0.6
        ):
            return True

    if places_related and is_strict_generic_locality_duplicate(
        event_a,
        event_b,
        title_tokens_a,
        title_tokens_b,
    ):
        return True

    if event_is_traditional(event_a) and event_is_traditional(event_b) and len(shared_title_tokens) >= 2:
        return True

    return False


def event_preference_score(event: dict, aliases: list[str]) -> int:
    date_text = normalize_for_search(event.get("date"))
    start, end = parse_event_date_range(event.get("date"))
    source_priority = {
        "villa manin": 70,
        "erpac": 65,
        "turismofvg": 50,
        "anteprima sagre": 40,
        "sagrefvg": 35,
        "pro loco fvg": 35,
        "paesi in festa": 25,
        "eventifvg": 20,
    }

    score = event_quality_score(event, aliases)

    if event.get("image"):
        score += 4

    if start:
        score += 3

    if start and end and end > start:
        score += 3

    if re.search(r"\b20\d{2}\b", date_text):
        score += 1

    if "dal" in date_text or " al " in f" {date_text} ":
        score += 1

    score += source_priority.get(normalize_for_search(event.get("source")), 0)
    return score


def merge_duplicate_event_data(primary: dict, secondary: dict) -> dict:
    merged = dict(primary)

    for key in (
        "image",
        "place",
        "event_city",
        "venue",
        "address",
        "description",
        "official_site",
        "date",
        "category",
        "category_label",
        "occurrences",
    ):
        if not merged.get(key) and secondary.get(key):
            merged[key] = secondary.get(key)

    location_confidence_score = {
        "none": 0,
        "city_text": 1,
        "municipality": 2,
        "exact": 3,
    }
    primary_location_score = location_confidence_score.get(
        normalize_for_search(primary.get("location_confidence")),
        0,
    )
    secondary_location_score = location_confidence_score.get(
        normalize_for_search(secondary.get("location_confidence")),
        0,
    )

    for key in ("maps_url", "lat", "lon", "location_confidence"):
        secondary_value = secondary.get(key)
        if secondary_location_score > primary_location_score and secondary_value is not None:
            merged[key] = secondary_value
        elif not merged.get(key) and secondary_value is not None:
            merged[key] = secondary_value

    sources = []
    for source in (primary.get("source"), *(primary.get("alternate_sources") or [])):
        if source and source not in sources:
            sources.append(source)

    for source in (secondary.get("source"), *(secondary.get("alternate_sources") or [])):
        if source and source not in sources:
            sources.append(source)

    if len(sources) > 1:
        merged["alternate_sources"] = sources

    return merged


def dedupe_similar_events(events: list[dict], city: str) -> list[dict]:
    aliases = city_aliases(city)
    unique = []

    for event in events or []:
        event = with_explicit_event_days(event)
        duplicate_index = None

        for index, existing in enumerate(unique):
            if events_are_probable_duplicates(existing, event):
                duplicate_index = index
                break

        if duplicate_index is None:
            unique.append(event)
            continue

        existing = unique[duplicate_index]
        existing_score = event_preference_score(existing, aliases)
        candidate_score = event_preference_score(event, aliases)

        if candidate_score > existing_score:
            unique[duplicate_index] = merge_duplicate_event_data(event, existing)
        else:
            unique[duplicate_index] = merge_duplicate_event_data(existing, event)

    return unique


def with_explicit_event_days(event: dict) -> dict:
    """Read only a leading explicit list, never dates mentioned in a narrative.

    The surrounding dated event supplies the year; all days must fit its range.
    """
    if event.get("occurrences"):
        return event
    start, end = parse_event_date_range(event.get("date"))
    if not start or not end or start.year != end.year:
        return event
    match = re.match(
        r"^\s*(\d{1,2}(?:\s*[,e]\s*\d{1,2})+\s+"
        r"(?:gennaio|febbraio|marzo|aprile|maggio|giugno|luglio|agosto|settembre|ottobre|novembre|dicembre))\b",
        str(event.get("description") or ""), re.IGNORECASE,
    )
    if not match:
        return event
    days = parse_turismofvg_discrete_occurrences(f"{match.group(1)} {start.year}")
    if days and all(start.isoformat()[:10] <= day <= end.isoformat()[:10] for day in days):
        return {**event, "occurrences": days}
    return event


def event_date_sort_value(event: dict):
    parsed, _ = parse_event_date_range(event.get("date"))

    if parsed:
        return parsed

    return datetime.max.date()


def category_signal_score(category: str, title: str = "", context: str = "") -> int:
    text = normalize_for_search(f"{title} {context}")
    keyword_map = {
        "sagra": [
            "sagra", "sagre", "festa", "feste", "fieste", "pro loco",
            "patronale", "paesana",
        ],
        "mercato": [
            "mercato", "mercati", "mercatino", "mercatini", "fiera mercato",
            "fiere e mercatini", "bancarelle", "antiqua", "antiquariato",
        ],
        "food_wine": [
            "enogastronomia", "vino", "degustazione", "sapori", "gusto",
            "cibo", "frico", "asparago", "asparagi",
        ],
        "musica": [
            "concerto", "musica", "filarmonica", "filarmoniche", "banda",
            "coro", "orchestra", "festival", "jazz", "trio", "live",
        ],
        "sport": [
            "manifestazioni sportive", "sport", "gara", "corsa", "torneo",
            "marcia", "bike", "bici",
        ],
        "convegni": [
            "convegno", "convegni", "conferenza", "incontro", "seminario",
        ],
        "cultura": [
            "mostra", "museo", "teatro", "libro", "visita guidata",
            "arte", "storia", "spettacolo", "spettacoli", "teatrale",
            "teatrali", "attore", "attori",
        ],
        "natura": [
            "escursione", "camminata", "passeggiata", "trekking", "natura",
            "sentiero",
        ],
        "famiglia": [
            "bambini", "famiglie", "laboratorio", "laboratori",
        ],
    }

    return sum(1 for keyword in keyword_map.get(category, []) if keyword in text)


def reconcile_official_event_classification(
    official: dict,
    fallback: dict,
    title: str = "",
    context: str = "",
) -> dict:
    if not official:
        return fallback

    official_category = official.get("category")
    fallback_category = fallback.get("category")

    if not official_category or official_category == fallback_category:
        return {**fallback, **official}

    official_context = " ".join(
        str(value or "")
        for value in (
            official.get("category_label"),
            official.get("provider_categories"),
            official.get("topic"),
        )
    )
    official_score = category_signal_score(official_category, title, official_context)
    fallback_score = category_signal_score(fallback_category, title, "")

    if (
        fallback_category in {"sagra", "food_wine", "mercato"}
        and has_strong_traditional_event_signal(title, context)
        and fallback_score >= official_score
    ):
        return fallback

    if (
        fallback_category in {"sagra", "food_wine", "mercato"}
        and not has_strong_traditional_event_signal(title, context)
        and official_score > 0
    ):
        return {**fallback, **official}

    if fallback_score >= official_score + 2:
        return fallback

    return {**fallback, **official}


def classify_event(title: str = "", context: str = ""):
    title_text = normalize_for_search(title)
    context_text = normalize_for_search(context)

    categories = [
        {
            "category": "convegni",
            "category_label": "Convegni",
            "keywords": [
                "convegno", "convegni", "conferenza", "conferenze",
                "seminario", "seminari", "scrittura", "scritture",
                "archivi", "archivio", "studio", "studi",
            ],
            "priority": 90,
            "weather_sensitivity": "low",
            "is_traditional": False,
        },
        {
            "category": "sagra",
            "category_label": "Sagra / festa locale",
            "keywords": [
                "sagra", "sagre", "festa", "feste", "fieste",
                "patrono", "patronale", "paesana", "paesano",
                "borgo", "pro loco", "sant", "santis",
            ],
            "priority": 95,
            "weather_sensitivity": "high",
            "is_traditional": True,
        },
        {
            "category": "mercato",
            "category_label": "Mercato / mercatino",
            "keywords": [
                "mercato", "mercati", "mercatino", "mercatini",
                "fiere e mercatini", "fiera mercato",
                "bancarelle", "artigianato", "antiquariato",
                "prodotti locali", "antiqua",
            ],
            "priority": 88,
            "weather_sensitivity": "high",
            "is_traditional": True,
        },
        {
            "category": "food_wine",
            "category_label": "Enogastronomia",
            "keywords": [
                "vino", "vini", "cantina", "cantine",
                "degustazione", "prosciutto", "frico", "polenta",
                "castagne", "castagnata", "formaggio", "sapori",
                "gusto", "cibo", "enogastronomia", "osteria",
                "birra", "asparagi", "asparago", "asparagorgo",
            ],
            "priority": 86,
            "weather_sensitivity": "medium",
            "is_traditional": True,
        },
        {
            "category": "cultura",
            "category_label": "Cultura",
            "keywords": [
                "mostra", "museo", "musei", "teatro", "libro",
                "lettura", "conferenza", "visita guidata",
                "visite guidate", "arte", "storia", "incontro",
                "ville aperte", "villa aperta", "villa", "ville",
                "castello", "biblioteca",
            ],
            "priority": 72,
            "weather_sensitivity": "low",
            "is_traditional": False,
        },
        {
            "category": "natura",
            "category_label": "Natura / camminata",
            "keywords": [
                "camminata", "passeggiata", "escursione", "trekking",
                "sentiero", "natura", "bosco", "laguna", "mare",
                "montagna",
            ],
            "priority": 70,
            "weather_sensitivity": "high",
            "is_traditional": False,
        },
        {
            "category": "musica",
            "category_label": "Musica",
            "keywords": [
                "concerto", "musica", "festival", "live", "coro",
                "orchestra", "filarmonica", "filarmoniche", "banda",
                "bandistico", "bandistica", "dj", "dj set", "band",
                "jazz", "trio",
            ],
            "priority": 68,
            "weather_sensitivity": "medium",
            "is_traditional": False,
        },
        {
            "category": "sport",
            "category_label": "Sport",
            "keywords": [
                "gara", "corsa", "marcia", "bike", "bici",
                "sport", "torneo", "partita", "corri", "running",
                "trail", "maratona",
            ],
            "priority": 60,
            "weather_sensitivity": "high",
            "is_traditional": False,
        },
        {
            "category": "famiglia",
            "category_label": "Famiglia",
            "keywords": [
                "bambini", "famiglie", "laboratorio", "laboratori",
                "gioco", "letture animate",
            ],
            "priority": 58,
            "weather_sensitivity": "medium",
            "is_traditional": False,
        },
    ]

    best = {
        "category": "generico",
        "category_label": "Evento",
        "priority": 40,
        "weather_sensitivity": "medium",
        "is_traditional": False,
        "match_score": 0,
    }

    for item in categories:
        title_matches = sum(1 for keyword in item["keywords"] if keyword in title_text)
        context_matches = sum(1 for keyword in item["keywords"] if keyword in context_text)

        if title_matches == 0 and context_matches == 0:
            continue

        # Il titolo pesa molto più del contesto: evita che un contesto sporco
        # faccia diventare tutto "musica" o "sagra".
        score = item["priority"] + (title_matches * 100) + (context_matches * 5)

        if score > best["match_score"]:
            best = {
                "category": item["category"],
                "category_label": item["category_label"],
                "priority": item["priority"],
                "weather_sensitivity": item["weather_sensitivity"],
                "is_traditional": item["is_traditional"],
                "match_score": score,
            }

    best.pop("match_score", None)
    return best


TURISMOFVG_TOPIC_CATEGORY_MAP = {
    "accessible cinema": {
        "category": "cultura",
        "category_label": "Cinema accessibile",
        "priority": 68,
        "weather_sensitivity": "low",
        "is_traditional": False,
    },
    "cinema accessibile": {
        "category": "cultura",
        "category_label": "Cinema accessibile",
        "priority": 68,
        "weather_sensitivity": "low",
        "is_traditional": False,
    },
    "cinema": {
        "category": "cultura",
        "category_label": "Cinema",
        "priority": 68,
        "weather_sensitivity": "low",
        "is_traditional": False,
    },
    "convegni": {
        "category": "convegni",
        "category_label": "Convegni",
        "priority": 66,
        "weather_sensitivity": "low",
        "is_traditional": False,
    },
    "congress": {
        "category": "convegni",
        "category_label": "Convegni",
        "priority": 66,
        "weather_sensitivity": "low",
        "is_traditional": False,
    },
    "meeting": {
        "category": "convegni",
        "category_label": "Convegni",
        "priority": 66,
        "weather_sensitivity": "low",
        "is_traditional": False,
    },
    "contest": {
        "category": "cultura",
        "category_label": "Concorsi",
        "priority": 64,
        "weather_sensitivity": "medium",
        "is_traditional": False,
    },
    "concorsi": {
        "category": "cultura",
        "category_label": "Concorsi",
        "priority": 64,
        "weather_sensitivity": "medium",
        "is_traditional": False,
    },
    "dance": {
        "category": "cultura",
        "category_label": "Danza",
        "priority": 68,
        "weather_sensitivity": "low",
        "is_traditional": False,
    },
    "danza": {
        "category": "cultura",
        "category_label": "Danza",
        "priority": 68,
        "weather_sensitivity": "low",
        "is_traditional": False,
    },
    "didactic workshops": {
        "category": "famiglia",
        "category_label": "Laboratori didattici",
        "priority": 62,
        "weather_sensitivity": "medium",
        "is_traditional": False,
    },
    "laboratori didattici": {
        "category": "famiglia",
        "category_label": "Laboratori didattici",
        "priority": 62,
        "weather_sensitivity": "medium",
        "is_traditional": False,
    },
    "eventi pro loco": {
        "category": "sagra",
        "category_label": "Eventi Pro Loco",
        "priority": 88,
        "weather_sensitivity": "medium",
        "is_traditional": True,
    },
    "exhibitions": {
        "category": "cultura",
        "category_label": "Mostre",
        "priority": 70,
        "weather_sensitivity": "low",
        "is_traditional": False,
    },
    "manifestazioni sportive": {
        "category": "sport",
        "category_label": "Manifestazioni sportive",
        "priority": 64,
        "weather_sensitivity": "high",
        "is_traditional": False,
    },
    "visite guidate": {
        "category": "cultura",
        "category_label": "Visite guidate",
        "priority": 70,
        "weather_sensitivity": "medium",
        "is_traditional": False,
    },
    "mostre": {
        "category": "cultura",
        "category_label": "Mostre",
        "priority": 70,
        "weather_sensitivity": "low",
        "is_traditional": False,
    },
    "teatro": {
        "category": "cultura",
        "category_label": "Teatro",
        "priority": 68,
        "weather_sensitivity": "low",
        "is_traditional": False,
    },
    "theatrical performances": {
        "category": "cultura",
        "category_label": "Spettacoli teatrali",
        "priority": 68,
        "weather_sensitivity": "low",
        "is_traditional": False,
    },
    "spettacoli teatrali": {
        "category": "cultura",
        "category_label": "Spettacoli teatrali",
        "priority": 68,
        "weather_sensitivity": "low",
        "is_traditional": False,
    },
    "musica": {
        "category": "musica",
        "category_label": "Musica",
        "priority": 68,
        "weather_sensitivity": "medium",
        "is_traditional": False,
    },
    "music": {
        "category": "musica",
        "category_label": "Musica",
        "priority": 68,
        "weather_sensitivity": "medium",
        "is_traditional": False,
    },
    "concerti": {
        "category": "musica",
        "category_label": "Concerti",
        "priority": 68,
        "weather_sensitivity": "medium",
        "is_traditional": False,
    },
    "festival": {
        "category": "musica",
        "category_label": "Festival",
        "priority": 68,
        "weather_sensitivity": "medium",
        "is_traditional": False,
    },
    "enogastronomia": {
        "category": "food_wine",
        "category_label": "Enogastronomia",
        "priority": 86,
        "weather_sensitivity": "medium",
        "is_traditional": True,
    },
    "food and wine": {
        "category": "food_wine",
        "category_label": "Enogastronomia",
        "priority": 86,
        "weather_sensitivity": "medium",
        "is_traditional": True,
    },
    "wine and dine route": {
        "category": "food_wine",
        "category_label": "Strada del vino e dei sapori",
        "priority": 84,
        "weather_sensitivity": "medium",
        "is_traditional": True,
    },
    "strada del vino e dei sapori": {
        "category": "food_wine",
        "category_label": "Strada del vino e dei sapori",
        "priority": 84,
        "weather_sensitivity": "medium",
        "is_traditional": True,
    },
    "mercati": {
        "category": "mercato",
        "category_label": "Mercati",
        "priority": 88,
        "weather_sensitivity": "high",
        "is_traditional": True,
    },
    "mercatini": {
        "category": "mercato",
        "category_label": "Mercatini",
        "priority": 88,
        "weather_sensitivity": "high",
        "is_traditional": True,
    },
    "fair, street markets": {
        "category": "mercato",
        "category_label": "Fiere e mercatini",
        "priority": 88,
        "weather_sensitivity": "high",
        "is_traditional": True,
    },
    "fiere e mercatini": {
        "category": "mercato",
        "category_label": "Fiere e mercatini",
        "priority": 88,
        "weather_sensitivity": "high",
        "is_traditional": True,
    },
    "fiere": {
        "category": "mercato",
        "category_label": "Fiere",
        "priority": 84,
        "weather_sensitivity": "high",
        "is_traditional": True,
    },
    "sagre": {
        "category": "sagra",
        "category_label": "Sagre",
        "priority": 92,
        "weather_sensitivity": "high",
        "is_traditional": True,
    },
    "feste": {
        "category": "sagra",
        "category_label": "Feste",
        "priority": 92,
        "weather_sensitivity": "high",
        "is_traditional": True,
    },
    "traditional feasts": {
        "category": "sagra",
        "category_label": "Feste tradizionali",
        "priority": 92,
        "weather_sensitivity": "high",
        "is_traditional": True,
    },
    "feste tradizionali": {
        "category": "sagra",
        "category_label": "Feste tradizionali",
        "priority": 92,
        "weather_sensitivity": "high",
        "is_traditional": True,
    },
    "escursioni": {
        "category": "natura",
        "category_label": "Escursioni",
        "priority": 72,
        "weather_sensitivity": "high",
        "is_traditional": False,
    },
    "natura": {
        "category": "natura",
        "category_label": "Natura",
        "priority": 70,
        "weather_sensitivity": "high",
        "is_traditional": False,
    },
    "famiglia": {
        "category": "famiglia",
        "category_label": "Famiglia",
        "priority": 58,
        "weather_sensitivity": "medium",
        "is_traditional": False,
    },
    "family": {
        "category": "famiglia",
        "category_label": "Family",
        "priority": 58,
        "weather_sensitivity": "medium",
        "is_traditional": False,
    },
    "bambini": {
        "category": "famiglia",
        "category_label": "Bambini",
        "priority": 58,
        "weather_sensitivity": "medium",
        "is_traditional": False,
    },
    "guided tours": {
        "category": "cultura",
        "category_label": "Visite guidate",
        "priority": 70,
        "weather_sensitivity": "medium",
        "is_traditional": False,
    },
    "history": {
        "category": "cultura",
        "category_label": "Storia",
        "priority": 70,
        "weather_sensitivity": "medium",
        "is_traditional": False,
    },
    "storia": {
        "category": "cultura",
        "category_label": "Storia",
        "priority": 70,
        "weather_sensitivity": "medium",
        "is_traditional": False,
    },
    "local interest": {
        "category": "cultura",
        "category_label": "Interesse locale",
        "priority": 60,
        "weather_sensitivity": "medium",
        "is_traditional": False,
    },
    "local intereset": {
        "category": "cultura",
        "category_label": "Interesse locale",
        "priority": 60,
        "weather_sensitivity": "medium",
        "is_traditional": False,
    },
    "interesse locale": {
        "category": "cultura",
        "category_label": "Interesse locale",
        "priority": 60,
        "weather_sensitivity": "medium",
        "is_traditional": False,
    },
    "re-enactments": {
        "category": "cultura",
        "category_label": "Rievocazioni",
        "priority": 74,
        "weather_sensitivity": "high",
        "is_traditional": True,
    },
    "rievocazioni": {
        "category": "cultura",
        "category_label": "Rievocazioni",
        "priority": 74,
        "weather_sensitivity": "high",
        "is_traditional": True,
    },
    "sailing event": {
        "category": "sport",
        "category_label": "Evento nautico",
        "priority": 64,
        "weather_sensitivity": "high",
        "is_traditional": False,
    },
    "evento nautico": {
        "category": "sport",
        "category_label": "Evento nautico",
        "priority": 64,
        "weather_sensitivity": "high",
        "is_traditional": False,
    },
    "sporting event": {
        "category": "sport",
        "category_label": "Manifestazioni sportive",
        "priority": 64,
        "weather_sensitivity": "high",
        "is_traditional": False,
    },
    "sustainable": {
        "category": "natura",
        "category_label": "Sostenibile",
        "priority": 62,
        "weather_sensitivity": "medium",
        "is_traditional": False,
    },
    "sostenibile": {
        "category": "natura",
        "category_label": "Sostenibile",
        "priority": 62,
        "weather_sensitivity": "medium",
        "is_traditional": False,
    },
}


TURISMOFVG_CATEGORY_FILTERS = (
    {"id": "3594", "topic": "Manifestazioni sportive"},
    {"id": "3595", "topic": "Manifestazioni veliche"},
    {"id": "3590", "topic": "Enogastronomia"},
    {"id": "3599", "topic": "Strada del vino e dei sapori"},
    {"id": "3583", "topic": "Musica"},
    {"id": "3589", "topic": "Festival"},
    {"id": "3584", "topic": "Spettacoli teatrali"},
    {"id": "3585", "topic": "Danza"},
    {"id": "3586", "topic": "Cinema"},
    {"id": "3613", "topic": "Family"},
    {"id": "3596", "topic": "Laboratori didattici"},
    {"id": "4170", "topic": "Sostenibile"},
    {"id": "3588", "topic": "Mostre"},
    {"id": "3591", "topic": "Feste tradizionali"},
    {"id": "3592", "topic": "Fiere e mercatini"},
    {"id": "3640", "topic": "Rievocazioni"},
)


TURISMOFVG_NAVIGATION_EVENT_PATHS = {
    "/eventi/accessibile",
    "/eventi/concorsi",
    "/eventi/congressi",
    "/eventi/convegni",
    "/eventi/eventi-pro-loco",
    "/eventi/manifestazioni-sportive",
    "/eventi/manifestazioni-veliche",
    "/eventi/enogastronomia",
    "/eventi/strada-del-vino-e-dei-sapori",
    "/eventi/musica",
    "/eventi/festival",
    "/eventi/spettacoli-teatrali",
    "/eventi/danza",
    "/eventi/cinema",
    "/eventi/family",
    "/eventi/laboratori-didattici",
    "/eventi/sostenibile",
    "/eventi/mostre",
    "/eventi/feste-tradizionali",
    "/eventi/fiere-e-mercatini",
    "/eventi/rievocazioni",
    "/eventi/interesse-locale",
    "/eventi/storia",
}


def is_trusted_turismofvg_event_url(value: str) -> bool:
    try:
        parsed = urlsplit(str(value or "").strip())
        has_default_port = parsed.port is None
    except ValueError:
        return False

    path = (parsed.path or "").rstrip("/").lower()
    return (
        parsed.scheme == "https"
        and str(parsed.hostname or "").lower() in {"turismofvg.it", "www.turismofvg.it"}
        and has_default_port
        and not parsed.username
        and not parsed.password
        and not parsed.query
        and not parsed.fragment
        and ((path.startswith("/eventi/") and path not in TURISMOFVG_NAVIGATION_EVENT_PATHS)
             or re.fullmatch(r"/events20/details/\d+", path) is not None)
    )


def is_turismofvg_navigation_link(link: dict) -> bool:
    url = str(link.get("url") or "").split("?", 1)[0].rstrip("/")
    path_match = re.search(r"https?://[^/]+(/eventi/[^#]+)$", url, flags=re.IGNORECASE)
    path = (path_match.group(1) if path_match else url).lower()
    return path in TURISMOFVG_NAVIGATION_EVENT_PATHS


def extract_turismofvg_topic(html: str) -> dict | None:
    info_text_matches = re.findall(
        r'<(?:div|li|td)[^>]*>\s*(?:<[^>]+>\s*)*<span[^>]*class=["\'][^"\']*(?:icon|ico)[^"\']*["\'][^>]*>.*?</span>\s*(.*?)</(?:div|li|td)>',
        html,
        flags=re.IGNORECASE | re.DOTALL,
    )

    if not info_text_matches:
        info_text_matches = re.findall(
            r'<div[^>]+class=["\'][^"\']*(?:col|info|event)[^"\']*["\'][^>]*>(.*?)</div>',
            html,
            flags=re.IGNORECASE | re.DOTALL,
        )

    candidates = [
        clean_event_text(candidate)
        for candidate in info_text_matches
    ]

    blocked = {
        "tutti",
        "richiedi informazioni",
        "condividi",
    }

    for candidate in candidates[:12]:
        topic_parts = [
            part.strip()
            for part in re.split(r"\s*,\s*", candidate)
            if part.strip()
        ]

        if not topic_parts:
            topic_parts = [candidate]

        if any(normalize_for_search(part) in blocked for part in topic_parts):
            continue

        classification = turismofvg_topic_classification(candidate)
        if classification:
            return classification

    return None


def fetch_turismofvg_locality_ids(headers: dict) -> dict:
    cache_key = "turismofvg-locality-ids"
    cached = get_from_cache(turismofvg_locality_cache, cache_key, GEOCODE_CACHE_TTL)

    if cached is not None:
        return cached

    localities = {}

    try:
        res = requests.get(TURISMOFVG_EVENTS_URL, headers=headers, timeout=10)
        res.raise_for_status()

        for match in re.finditer(
            r'<option\s+value=["\']([^"\']+)["\'][^>]*data-text=["\']a\s+([^"\']+)["\'][^>]*>([^<\r\n]+)',
            res.text,
            flags=re.IGNORECASE | re.DOTALL,
        ):
            locality_id = clean_event_text(match.group(1))
            data_text_name = clean_event_text(unescape(match.group(2)))
            visible_name = clean_event_text(match.group(3))
            name = visible_name or data_text_name

            if not locality_id or not name:
                continue

            localities[normalize_for_search(name)] = locality_id
            localities[normalize_for_search(data_text_name)] = locality_id

        set_cache(turismofvg_locality_cache, cache_key, localities)
        return localities

    except Exception as e:
        print("Errore lettura localita TurismoFVG:", e)
        return {}


def resolve_turismofvg_locality_id(city: str, headers: dict) -> str | None:
    localities = fetch_turismofvg_locality_ids(headers)

    for alias in city_aliases(city):
        locality_id = localities.get(normalize_for_search(alias))
        if locality_id:
            return locality_id

    return localities.get(normalize_for_search(city))


def nearby_fvg_municipalities(
    city: str,
    origin_lat=None,
    origin_lon=None,
    radius_km: float = EVENTS_NEARBY_RADIUS_KM,
    municipality_limit: int = EVENTS_NEARBY_SOURCE_MUNICIPALITY_LIMIT,
) -> list:
    if not 0 < radius_km <= 50 or not 1 <= municipality_limit <= 215:
        raise ValueError("invalid event search coverage")
    municipality = fvg_municipality_catalog.match_names(city)

    try:
        latitude = float(origin_lat) if origin_lat is not None else None
        longitude = float(origin_lon) if origin_lon is not None else None
    except (TypeError, ValueError):
        latitude = None
        longitude = None

    if latitude is None or longitude is None:
        if municipality:
            latitude = municipality.latitude
            longitude = municipality.longitude
        else:
            latitude, longitude = geocode_city(city)

    if latitude is None or longitude is None:
        return [municipality] if municipality else []

    nearby = []
    for candidate in fvg_municipality_catalog.municipalities:
        distance = haversine_km(
            latitude,
            longitude,
            candidate.latitude,
            candidate.longitude,
        )
        if distance <= radius_km:
            nearby.append((distance, candidate))

    nearby.sort(
        key=lambda item: (
            0 if municipality and item[1].istat_code == municipality.istat_code else 1,
            item[0],
            normalize_for_search(item[1].name),
        )
    )
    return [
        candidate
        for _, candidate in nearby[:municipality_limit]
    ]


def resolve_turismofvg_nearby_locality_ids(
    city: str,
    headers: dict,
    origin_lat=None,
    origin_lon=None,
    *,
    radius_km=EVENTS_NEARBY_RADIUS_KM,
    municipality_limit=EVENTS_NEARBY_SOURCE_MUNICIPALITY_LIMIT,
) -> list[str]:
    localities = fetch_turismofvg_locality_ids(headers)
    locality_ids = []

    for municipality in nearby_fvg_municipalities(city, origin_lat, origin_lon, radius_km, municipality_limit):
        locality_id = localities.get(normalize_for_search(municipality.name))
        if locality_id and locality_id not in locality_ids:
            locality_ids.append(locality_id)

    return locality_ids


def turismofvg_request_specs(
    city: str,
    locality_id: str | None,
    nearby_locality_ids: list[str] | None = None,
    search_queries: list[str] | None = None,
):
    today = datetime.now().date()
    horizon = today + timedelta(days=EVENTS_UPCOMING_WINDOW_DAYS)
    specs = []

    if locality_id:
        specs.append(
            {
                "url": TURISMOFVG_EVENTS_FILTER_URL,
                "params": {"locality": locality_id, "hidehighlights": "true"},
                "topic": "",
                "classification": None,
            }
        )
    else:
        specs.append(
            {
                "url": TURISMOFVG_EVENTS_URL,
                "params": {"q": city, "hidehighlights": "true"},
                "topic": "",
                "classification": None,
            }
        )

    for nearby_locality_id in nearby_locality_ids or []:
        if not nearby_locality_id or nearby_locality_id == locality_id:
            continue

        specs.append(
            {
                "url": TURISMOFVG_EVENTS_FILTER_URL,
                "params": {
                    "locality": nearby_locality_id,
                    "hidehighlights": "true",
                },
                "topic": "",
                "classification": None,
            }
        )

    for category_filter in TURISMOFVG_CATEGORY_FILTERS:
        params = {
            "hidehighlights": "true",
            "category": category_filter["id"],
            "start": today.isoformat(),
            "end": horizon.isoformat(),
        }

        if locality_id:
            params["locality"] = locality_id
        else:
            params["q"] = city

        specs.append(
            {
                "url": TURISMOFVG_EVENTS_URL,
                "params": params,
                "topic": category_filter["topic"],
                "classification": turismofvg_topic_classification(category_filter["topic"]),
            }
        )

    for query in search_queries or []:
        clean_query = clean_event_text(query)
        if not clean_query:
            continue
        specs.append(
            {
                "url": TURISMOFVG_EVENTS_URL,
                "params": {"q": clean_query, "hidehighlights": "true"},
                "topic": "",
                "classification": None,
                "catalog_lookup": True,
            }
        )

    unique_specs = []
    seen = set()

    for spec in specs:
        key = (
            spec["url"],
            tuple(sorted((spec.get("params") or {}).items())),
        )

        if key in seen:
            continue

        seen.add(key)
        unique_specs.append(spec)

    return unique_specs


def extract_turismofvg_detail_rows(html: str) -> list[str]:
    rows = []
    body_col_match = re.search(
        r'<div[^>]+class=["\']body_col2["\'][^>]*>(.*?)<div[^>]+class=["\']c-detail__actions',
        html,
        flags=re.IGNORECASE | re.DOTALL,
    )
    source = body_col_match.group(1) if body_col_match else html

    for match in re.finditer(
        r'<div[^>]*background-image:\s*url\([^)]*icn__[^)]*\)[^>]*>(.*?)</div>',
        source,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        row = clean_event_text(match.group(1))
        if row:
            rows.append(row)

    return rows


def extract_turismofvg_description(html: str) -> str | None:
    body_col_match = re.search(
        r'<div[^>]+class=["\'][^"\']*\bbody_col1\b[^"\']*["\'][^>]*>(.*?)'
        r'<div[^>]+class=["\'][^"\']*\bbody_col2\b[^"\']*["\']',
        html,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if not body_col_match:
        return None

    description_match = re.search(
        r'<h[1-6][^>]*>\s*Descrizione\s*</h[1-6]>(.*?)'
        r'(?=<h[1-6][^>]*>\s*Organizzato\s+da\s*:?\s*</h[1-6]>|\Z)',
        body_col_match.group(1),
        flags=re.IGNORECASE | re.DOTALL,
    )
    if not description_match:
        return None

    description = clean_event_text(description_match.group(1))
    return description or None


def split_event_venue_address(value: str) -> tuple[str, str | None]:
    clean = clean_event_text(value)
    match = re.match(
        r"^(?P<venue>.+?)\s+-\s+(?P<address>"
        r"(?:via|viale|piazza|piazzale|corso|largo|strada|vicolo|borgo|localit[aà])\b.+)$",
        clean,
        flags=re.IGNORECASE,
    )
    if not match:
        return clean, None
    return clean_event_text(match.group("venue")), clean_event_text(match.group("address"))


def extract_turismofvg_detail_metadata(html: str) -> dict:
    rows = extract_turismofvg_detail_rows(html)
    result = {}
    description = extract_turismofvg_description(html)

    if description:
        result["description"] = description

    if not rows:
        return result

    date_index = None
    date_pattern = re.compile(
        r"\b(?:luned[iì]|marted[iì]|mercoled[iì]|gioved[iì]|venerd[iì]|sabato|domenica|\d{1,2}\s+(?:gennaio|febbraio|marzo|aprile|maggio|giugno|luglio|agosto|settembre|ottobre|novembre|dicembre))\b",
        flags=re.IGNORECASE,
    )

    for index, row in enumerate(rows):
        normalized_row = normalize_for_search(row)
        if date_pattern.search(row) or re.search(r"\b20\d{2}\b", normalized_row):
            result["date_full"] = row
            date_index = index
            break

    if date_index is not None and date_index > 0:
        provider_categories = rows[0]
        category_list = [
            clean_event_text(part)
            for part in re.split(r"\s*,\s*", provider_categories)
            if clean_event_text(part)
        ]
        if provider_categories:
            result["provider_categories"] = provider_categories
        if category_list:
            result["provider_category_list"] = category_list

    if date_index is not None:
        for row in rows[date_index + 1:]:
            normalized_row = normalize_for_search(row)
            if not normalized_row:
                continue

            if normalized_row in {"condividi", "richiedi informazioni"}:
                continue

            if normalized_row.startswith(("http", "www")):
                result.setdefault("official_site", row)
                continue

            if "@" in normalized_row:
                result.setdefault("contact", row)
                continue

            if "event_city" not in result:
                result["event_city"] = row
                continue

            if "venue" not in result:
                venue, address = split_event_venue_address(row)
                result["venue"] = venue
                result["place"] = venue
                if address:
                    result["address"] = address
                continue

            result.setdefault("audience", row)

    # The source labels each row with an icon. Never shift optional clock or
    # contact rows into venue/audience based on their position.
    labelled = list(re.finditer(
        r'<div[^>]*background-image:\s*url\([^)]*icn__(?P<icon>[^)/?]+)[^)]*\)[^>]*>(?P<body>.*?)</div>',
        html, re.I | re.S))
    if any(m['icon'].startswith('calendar') for m in labelled):
        for key in ('date_full', 'event_city', 'venue', 'place', 'address', 'audience', 'official_site', 'contact'):
            result.pop(key, None)
        for match in labelled:
            icon, body = match['icon'], match['body']
            value = clean_event_text(body)
            if icon.startswith('calendar'):
                result['date_full'] = value
            elif icon.startswith('pin'):
                result['event_city'] = value
            elif icon.startswith('clock'):
                clock = re.fullmatch(r'([01]?\d|2[0-3])[:.]([0-5]\d)', value)
                if clock:
                    result['time'] = f'{int(clock[1]):02d}:{clock[2]}'
            elif icon.startswith('building'):
                lines = [clean_event_text(s) for s in re.split(r'<br\s*/?>', body, flags=re.I)]
                lines = [s for s in lines if s]
                venue, address = split_event_venue_address(lines[0] if lines else value)
                result.update(venue=venue, place=venue)
                if len(lines) > 1:
                    address = ' '.join(lines[1:])
                if address:
                    result['address'] = address
            elif icon.startswith('web'):
                result['official_site'] = value
            elif icon.startswith('people'):
                result['audience'] = value
    return result


def parse_turismofvg_discrete_occurrences(value: object) -> list[str]:
    clean = clean_event_text(value)
    normalized = normalize_for_search(clean)
    if not normalized or re.search(r"\b(?:dal|al|fino al)\b", normalized):
        return []
    if re.search(r"\s[-–—]\s", clean):
        return []

    month_numbers = {
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
    month_pattern = "|".join(month_numbers)
    groups = list(
        re.finditer(
            rf"\b(?P<days>\d{{1,2}}(?:\s*(?:,|e|/)\s*\d{{1,2}})*)\s+"
            rf"(?P<month>{month_pattern})(?:\s+(?P<year>20\d{{2}}))?\b",
            normalized,
            flags=re.IGNORECASE,
        )
    )
    if not groups or not any(match.group("year") for match in groups):
        return []
    # A partial match would silently lose early days from schedules such as
    # "10, 11 /17, 18 /24, 25 ottobre 2026".
    remainder = normalized
    for match in reversed(groups):
        remainder = remainder[:match.start()] + remainder[match.end():]
    remainder = re.sub(r"\be\b", "", remainder)
    if re.sub(r"[\s,;/]+", "", remainder):
        return []

    current_year = None
    parsed = []
    for match in reversed(groups):
        if match.group("year"):
            current_year = int(match.group("year"))
        if current_year is None:
            return []
        month = month_numbers[match.group("month").lower()]
        days = [int(day) for day in re.findall(r"\d{1,2}", match.group("days"))]
        for day in reversed(days):
            try:
                parsed.append(datetime(current_year, month, day).date())
            except ValueError:
                return []

    occurrences = sorted(set(parsed))
    return [item.isoformat() for item in occurrences] if len(occurrences) > 1 else []


def apply_turismofvg_metadata(result: dict, metadata: dict) -> dict:
    for key in (
        "event_city",
        "place",
        "venue",
        "address",
        "official_site",
        "audience",
        "contact",
        "provider_categories",
        "provider_category_list",
        "description",
    ):
        if metadata.get(key):
            result[key] = metadata[key]

    return result


def fetch_turismofvg_event_detail(url: str, headers: dict) -> dict:
    cache_key = make_cache_key("turismofvg_detail", EVENTS_CACHE_VERSION, url)
    cached = get_from_cache(turismofvg_detail_cache, cache_key, SAGREFVG_DETAIL_CACHE_TTL)

    if cached is not None:
        return cached

    try:
        res = requests.get(url, headers=headers, timeout=10)
        if res.status_code != 200:
            return {"date": "Data in aggiornamento"}

        html = res.text
        topic = extract_turismofvg_topic(html)
        metadata = extract_turismofvg_detail_metadata(html)
        metadata_occurrences = parse_turismofvg_discrete_occurrences(
            metadata.get("date_full")
        )
        image = extract_official_event_image(html, TURISMOFVG_BASE_URL)
        dates = re.findall(r'<div class="col1">\s*<strong>(.*?)</strong>\s*<p>(.*?)</p>', html, re.IGNORECASE)

        if metadata.get("date_full"):
            result = {"date": metadata["date_full"]}
            if metadata_occurrences:
                result["occurrences"] = metadata_occurrences
            if topic:
                result.update(topic)
            if image:
                result["image"] = image
            apply_turismofvg_metadata(result, metadata)
            set_cache(turismofvg_detail_cache, cache_key, result)
            return result

        if not dates:
            result = {"date": metadata.get("date_full") or "Data in aggiornamento"}
            if metadata_occurrences:
                result["occurrences"] = metadata_occurrences
            if topic:
                result.update(topic)
            if image:
                result["image"] = image
            apply_turismofvg_metadata(result, metadata)
            set_cache(turismofvg_detail_cache, cache_key, result)
            return result

        unique_dates = []
        for d in dates:
            if d not in unique_dates:
                unique_dates.append(d)

        if len(unique_dates) == 1:
            date_str = f"{unique_dates[0][0]} {unique_dates[0][1].capitalize()}"
        else:
            date_str = f"Dal {unique_dates[0][0]} al {unique_dates[-1][0]} {unique_dates[-1][1].capitalize()}"

        result = {"date": date_str}
        if topic:
            result.update(topic)
        if image:
            result["image"] = image
        apply_turismofvg_metadata(result, metadata)
        set_cache(turismofvg_detail_cache, cache_key, result)
        return result

    except Exception as e:
        print("Errore fetch dettaglio TurismoFVG:", e)
        return {"date": "Data in aggiornamento"}


def fetch_turismofvg_events(
    city: str,
    limit: int = 3,
    origin_lat=None,
    origin_lon=None,
    *,
    search_queries: list[str] | None = None,
    strict: bool = False,
    radius_km: float = EVENTS_NEARBY_RADIUS_KM,
    municipality_limit: int = EVENTS_NEARBY_SOURCE_MUNICIPALITY_LIMIT,
):
    if not 0 < radius_km <= 50 or not 1 <= municipality_limit <= 215:
        raise ValueError("invalid event search coverage")
    normalized_search_queries = tuple(
        clean_event_text(query)
        for query in search_queries or []
        if clean_event_text(query)
    )
    cache_key = make_cache_key(
        "events",
        EVENTS_CACHE_VERSION,
        city,
        limit,
        round(float(origin_lat), 4) if origin_lat is not None else "",
        round(float(origin_lon), 4) if origin_lon is not None else "",
        normalized_search_queries,
        radius_km,
        municipality_limit,
    )
    cached = get_from_cache(events_cache, cache_key, EVENTS_CACHE_TTL)

    if cached and not strict:
        return cached

    try:
        aliases = city_aliases(city)

        headers = {
            "User-Agent": "Meteo-Friul-App/1.0",
        }

        locality_id = resolve_turismofvg_locality_id(city, headers)
        nearby_locality_ids = resolve_turismofvg_nearby_locality_ids(
            city,
            headers,
            origin_lat,
            origin_lon,
            radius_km=radius_km,
            municipality_limit=municipality_limit,
        )
        request_specs = turismofvg_request_specs(
            city,
            locality_id,
            nearby_locality_ids,
            list(normalized_search_queries),
        )

        # I filtri categoria sono indipendenti: fetch parallelo per non
        # bloccare troppo a lungo la cache Eventi al primo caricamento.
        def fetch_request_spec(request_spec: dict):
            spec_classification = request_spec.get("classification")
            spec_topic = request_spec.get("topic")
            current_url = request_spec["url"]
            current_params = request_spec.get("params")
            visited_urls = set()
            collected_urls = set()
            batches = []

            for _ in range(TURISMOFVG_MAX_PAGES_PER_SPEC):
                try:
                    request_kwargs = {
                        "params": current_params,
                        "headers": headers,
                        "timeout": 10,
                    }
                    if strict:
                        res = get_with_single_transient_retry(
                            requests.get,
                            current_url,
                            **request_kwargs,
                        )
                    else:
                        res = requests.get(current_url, **request_kwargs)
                        res.raise_for_status()
                except Exception as e:
                    topic = request_spec.get("topic") or "base"
                    if strict:
                        raise RuntimeError(
                            f"TurismoFVG filtro {topic}: pagina non acquisita"
                        ) from e
                    print(f"Errore eventi TurismoFVG filtro {topic}:", e)
                    break

                response_url = str(getattr(res, "url", None) or current_url)
                visited_urls.add(response_url)
                html = res.text
                links = extract_turismofvg_card_links(html) or extract_event_links(html)
                links = [link for link in links if not is_turismofvg_navigation_link(link)]

                if spec_classification or spec_topic:
                    for link in links:
                        if spec_classification and not link.get("classification"):
                            link["classification"] = spec_classification
                        if spec_topic and not link.get("provider_categories"):
                            link["provider_categories"] = spec_topic
                            link["provider_category_list"] = [spec_topic]
                if request_spec.get("catalog_lookup"):
                    for link in links:
                        link["catalog_lookup"] = True

                batches.append((html, links))
                collected_urls.update(
                    str(link.get("url") or "").strip()
                    for link in links
                    if str(link.get("url") or "").strip()
                )

                next_url = extract_turismofvg_next_page_url(html, response_url)
                if not next_url:
                    return batches
                if next_url in visited_urls:
                    if strict:
                        raise RuntimeError("TurismoFVG: ciclo nella paginazione")
                    return batches
                if len(collected_urls) >= limit:
                    if strict:
                        raise RuntimeError(
                            f"TurismoFVG: catalogo oltre il limite di {limit} eventi"
                        )
                    return batches

                current_url = next_url
                current_params = None

            if strict and extract_turismofvg_next_page_url(html, response_url):
                raise RuntimeError(
                    "TurismoFVG: superato il limite di sicurezza della paginazione"
                )
            return batches

        link_batches = []
        max_workers = max(1, min(8, len(request_specs)))
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            for batches in executor.map(fetch_request_spec, request_specs):
                if batches:
                    link_batches.extend(batches)

        if not link_batches:
            return []

        events = []
        detail_fetches = 0
        seen_urls = set()
        seen_titles = set()

        flattened_links = [
            (batch_html, link)
            for batch_html, links in link_batches
            for link in links
        ]
        url_occurrences = {}
        for _, link in flattened_links:
            link_url = str(link.get("url") or "").strip()
            if link_url:
                url_occurrences[link_url] = url_occurrences.get(link_url, 0) + 1

        def needs_traditional_single_day_detail(link: dict) -> bool:
            if not has_strong_traditional_event_signal(
                link.get("title") or "",
                link.get("provider_categories") or "",
            ):
                return False
            start, end = parse_event_date_range(link.get("extracted_date"))
            return start is not None and end == start

        # TurismoFVG elenca talvolta lo stesso evento una volta per ogni data
        # del programma. Elaboriamo prima questi link per leggere dal dettaglio
        # l'intervallo ufficiale completo, poi la deduplica conserva una card.
        def detail_priority(item):
            _, link = item
            link_url = str(link.get("url") or "").strip()
            occurrences = url_occurrences.get(link_url, 0)
            traditional_program = (
                occurrences > 1
                and has_strong_traditional_event_signal(
                    link.get("title") or "",
                    link.get("provider_categories") or "",
                )
            )
            traditional_single_day = needs_traditional_single_day_detail(link)
            return (
                -1
                if link.get("catalog_lookup")
                else (
                    0
                    if traditional_program or traditional_single_day
                    else (1 if occurrences > 1 else 2)
                ),
                -occurrences,
            )

        flattened_links.sort(key=detail_priority)

        for html, link in flattened_links:
            context = find_context(html, link["start"], link["end"])
            context_lower = normalize_for_search(context)
            title_lower = normalize_for_search(link["title"])

            if re.search(r"\b(annullat[oa]|rinviat[oa]|cancellat[oa])\b", title_lower) or\
               re.search(r"\b(annullat[oa]|rinviat[oa]|cancellat[oa])\b", context_lower):
                continue

            current_year = datetime.now().year
            years_in_title = [int(y) for y in re.findall(r"\b(20\d{2})\b", title_lower)]
            years_in_url = [int(y) for y in re.findall(r"\b(20\d{2})\b", link["url"])]
            years_in_context = [int(y) for y in re.findall(r"\b(20\d{2})\b", context_lower)]
            all_years = years_in_title + [y for y in years_in_url if y >= 2000] + years_in_context

            if any(year < current_year for year in all_years):
                continue

            title_key = re.sub(r"[^a-z0-9à-ÿ]+", "", title_lower)

            if link["url"] in seen_urls or title_key in seen_titles:
                continue

            seen_urls.add(link["url"])
            seen_titles.add(title_key)

            date_str = link.get("extracted_date")
            if not date_str or date_str == "Data in aggiornamento":
                date_str = extract_date_from_context(context)
            if not date_str or date_str == "Data in aggiornamento":
                date_str = extract_date_from_context(link["title"])

            if not date_str or date_str == "Data in aggiornamento":
                dal_al_match = re.search(
                    r"\b(dal\s+\d{1,2}\s+[a-z]+\s+al\s+\d{1,2}\s+[a-z]+(?:\s+\d{4})?)\b",
                    context,
                    re.IGNORECASE,
                )
                if dal_al_match:
                    date_str = dal_al_match.group(1).capitalize()

            detail = None
            needs_detail = (
                link.get("catalog_lookup")
                or url_occurrences.get(link["url"], 0) > 1
                or needs_traditional_single_day_detail(link)
                or
                not link.get("extracted_date")
                or not link.get("place")
                or not (link.get("classification") or link.get("provider_categories"))
            )
            if needs_detail and detail_fetches < TURISMOFVG_DETAIL_LIMIT:
                detail_fetches += 1
                detail = fetch_turismofvg_event_detail(link["url"], headers)
                if detail.get("date") and detail.get("date") != "Data in aggiornamento":
                    date_str = detail["date"]

            if not date_str:
                date_str = "Data in aggiornamento"

            classification = classify_event(link["title"], context)
            list_classification = link.get("classification")
            if list_classification:
                classification = reconcile_official_event_classification(
                    list_classification,
                    classification,
                    link["title"],
                    context,
                )
            if detail:
                official_classification = {
                    key: detail[key]
                    for key in (
                        "category",
                        "category_label",
                        "priority",
                        "weather_sensitivity",
                        "is_traditional",
                    )
                    if key in detail
                }
                if official_classification:
                    classification = reconcile_official_event_classification(
                        official_classification,
                        classification,
                        link["title"],
                        context,
                    )

            clean_title = link["title"]
            months_pattern = r"(?:gennaio|febbraio|marzo|aprile|maggio|giugno|luglio|agosto|settembre|ottobre|novembre|dicembre|gen|feb|mar|apr|mag|giu|lug|ago|set|ott|nov|dic)"

            title_date_match = re.search(rf'dal\s+(\d+\s+{months_pattern})\s+al\s*(?:-\s*)?(\d+\s+{months_pattern})?', clean_title, re.IGNORECASE)

            if title_date_match:
                d1 = title_date_match.group(1).capitalize()
                d2 = title_date_match.group(2)
                if d2:
                    date_str = f"Dal {d1} al {d2.capitalize()}"
                elif date_str and date_str != "Data in aggiornamento":
                    date_str = f"Dal {d1} al {date_str.lower()}"
                else:
                    date_str = f"Dal {d1}"

            clean_title = re.sub(rf'^.*?dal\s+\d+\s+{months_pattern}\s+al\s*(?:-\s*)?(?:\d+\s+{months_pattern}\s*)?(?:-\s*)?', '', clean_title, flags=re.IGNORECASE).strip()
            clean_title = re.sub(rf'^\d+\s+{months_pattern}\s+[a-zA-Z]+\s+(?:Festival\s+)?', '', clean_title, flags=re.IGNORECASE).strip()
            clean_title = re.sub(r'^.*?\d{2}:\d{2}.*?-\s*', '', clean_title, flags=re.IGNORECASE).strip()

            if not clean_title:
                clean_title = link["title"]

            detected_place = (
                (detail or {}).get("event_city")
                or (detail or {}).get("place")
                or link.get("place")
                or (city if text_contains_alias(context, aliases) else None)
                or extract_event_place_candidate(clean_title, city)
                or extract_event_place_candidate(context, city)
            )

            event_lat, event_lon = (None, None)
            location_confidence = "city_text"
            if detected_place:
                event_lat, event_lon = geocode_event_place(detected_place)
                if event_lat is not None and event_lon is not None:
                    location_confidence = "municipality"

            matches_requested_place = (
                text_contains_alias(clean_title, aliases)
                or text_contains_alias(context, aliases)
                or (detected_place and text_contains_alias(detected_place, aliases))
            )

            if (
                not matches_requested_place
                and origin_lat is not None
                and origin_lon is not None
                and event_lat is not None
                and event_lon is not None
            ):
                matches_requested_place = haversine_km(origin_lat, origin_lon, event_lat, event_lon) <= radius_km

            if not matches_requested_place:
                continue

            detail_data = detail or {}

            events.append(
                {
                    "title": clean_title,
                    "place": detected_place or city,
                    "event_city": detected_place or city,
                    "date": date_str,
                    "source": "TurismoFVG",
                    "url": link["url"],
                    "image": detail_data.get("image") or link.get("image"),
                    "venue": detail_data.get("venue"),
                    "official_site": detail_data.get("official_site"),
                    "audience": detail_data.get("audience"),
                    "provider_place": (detail_data.get("event_city") or detected_place or city),
                    "provider_categories": detail_data.get("provider_categories") or link.get("provider_categories"),
                    "provider_category_list": detail_data.get("provider_category_list") or link.get("provider_category_list"),
                    "description": detail_data.get("description"),
                    "occurrences": list(
                        detail_data.get("occurrences") or link.get("occurrences") or []
                    ),
                    "lat": event_lat,
                    "lon": event_lon,
                    "location_confidence": location_confidence,
                    "is_real": True,
                    **classification,
                }
            )

        events.sort(
            key=lambda item: (
                event_date_sort_value(item),
                -int(item.get("priority", 0) or 0),
                -event_quality_score(item, aliases),
            )
        )

        result = events[: max(1, min(limit, EVENTS_RESPONSE_MAX))]
        set_cache(events_cache, cache_key, result)
        return result

    except Exception as e:
        if strict:
            raise
        print("Errore eventi TurismoFVG:", e)
        return []


def slugify_for_url(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", str(value or ""))
    ascii_value = normalized.encode("ascii", "ignore").decode("ascii")
    ascii_value = ascii_value.lower()
    ascii_value = re.sub(r"[^a-z0-9]+", "-", ascii_value)
    return ascii_value.strip("-")


def sagrefvg_candidate_urls(city: str):
    slug = slugify_for_url(city)

    urls = [
        (SAGREFVG_EVENTS_URL, {"s": city}),
    ]

    if slug:
        urls.append((urljoin(SAGREFVG_BASE_URL, f"/sagris/categoria/{slug}/"), None))

    province_categories = {
        "udine": "udine",
        "udin": "udine",
        "pordenone": "pordenone",
        "pordenon": "pordenone",
        "gorizia": "gorizia",
        "gurize": "gorizia",
        "trieste": "trieste",
        "triest": "trieste",
    }

    category = province_categories.get(normalize_for_search(city))
    if category:
        urls.append((urljoin(SAGREFVG_BASE_URL, f"/sagris/categoria/{category}/"), None))

    # rimuove duplicati mantenendo ordine
    seen = set()
    unique = []
    for url, params in urls:
        key = (url, tuple(sorted((params or {}).items())))
        if key in seen:
            continue
        seen.add(key)
        unique.append((url, params))

    return unique


def extract_sagrefvg_links(html: str):
    links = []

    pattern = re.compile(
        r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>(.*?)</a>',
        re.IGNORECASE | re.DOTALL,
    )

    blocked_title_fragments = [
        "pagina successiva",
        "pagina precedente",
        "successiva",
        "precedente",
        "home",
        "sagre",
        "sagris",
        "eventi",
        "privacy",
        "cookie",
        "contatti",
        "chi siamo",
    ]

    for match in pattern.finditer(html):
        href = match.group(1)
        inner_html = match.group(2)

        if href.startswith(("#", "mailto:", "tel:", "javascript:")):
            continue

        url = urljoin(SAGREFVG_BASE_URL, href)
        lowered_url = normalize_for_search(url)
        base_url = normalize_for_search(SAGREFVG_BASE_URL)

        if not lowered_url.startswith(base_url):
            continue

        if any(
            blocked in lowered_url
            for blocked in [
                "facebook.com",
                "instagram.com",
                "twitter.com",
                "youtube.com",
                "/categoria/",
                "/tag/",
                "/page/",
                "/pagina/",
                "/feed/",
                "/privacy",
                "/cookie",
                "/contatti",
                "ical=",
                "eventdisplay=",
            ]
        ):
            continue

        if (
            lowered_url.rstrip("/") == base_url
            or lowered_url.rstrip("/").endswith("/sagris")
        ):
            continue

        title = clean_event_title(inner_html)
        lowered_title = normalize_for_search(title)
        context = find_context(html, match.start(), match.end())

        if lowered_title in {"leggi tutto", "continua", "read more"}:
            nearby_html = html[max(0, match.start() - 1600):match.start()]
            heading_matches = re.findall(
                r"<h[1-4][^>]*>(.*?)</h[1-4]>",
                nearby_html,
                flags=re.IGNORECASE | re.DOTALL,
            )

            if heading_matches:
                title = clean_event_title(heading_matches[-1])
                lowered_title = normalize_for_search(title)

        if not title or len(title) < 4:
            continue

        if any(fragment in lowered_title for fragment in blocked_title_fragments):
            continue

        event_signal = re.search(
            r"\((?:ud|pn|go|ts)\)|\b(sagra|sagre|festa|fieste|mercato|mercatini|festival|pignar|pan e vin|panevin|fiera|asparag|formaggi|broved)\b",
            normalize_for_search(f"{title} {context}"),
            re.IGNORECASE,
        )

        if not event_signal:
            continue

        if lowered_title in {"←", "→", "»", "«"}:
            continue

        links.append(
            {
                "title": title,
                "url": url,
                "start": match.start(),
                "end": match.end(),
            }
        )

    return links


def classify_sagrefvg_event(title: str, context: str):
    classification = classify_event(title, context)

    if classification.get("category") == "generico":
        classification = {
            "category": "sagra",
            "category_label": "Sagra / festa locale",
            "priority": 92,
            "weather_sensitivity": "high",
            "is_traditional": True,
        }

    if classification.get("category") not in ["sagra", "mercato", "food_wine"]:
        classification = {
            "category": "sagra",
            "category_label": "Sagra / festa locale",
            "priority": 92,
            "weather_sensitivity": "high",
            "is_traditional": True,
        }

    if classification.get("category") in ["sagra", "mercato", "food_wine"]:
        classification["is_traditional"] = True
        classification["priority"] = max(classification.get("priority", 0), 88)

    return classification


def fetch_sagrefvg_event_detail(url: str, headers: dict):
    cache_key = make_cache_key("sagrefvg_detail", url)
    cached = get_from_cache(
        sagrefvg_detail_cache,
        cache_key,
        SAGREFVG_DETAIL_CACHE_TTL,
    )

    if cached is not None:
        return cached

    cached_error = get_from_cache(
        sagrefvg_detail_error_cache,
        cache_key,
        SAGREFVG_DETAIL_ERROR_CACHE_TTL,
    )

    if cached_error is not None:
        return cached_error

    try:
        res = requests.get(url, headers=headers, timeout=SAGREFVG_DETAIL_TIMEOUT)
        res.raise_for_status()
    except Exception as e:
        print("Errore dettaglio SagreFVG:", e)
        fallback = {
            "is_past": False,
            "date": None,
        }
        set_cache(sagrefvg_detail_error_cache, cache_key, fallback)
        return fallback

    html = res.text
    text = clean_event_text(html)
    normalized = normalize_for_search(text)
    image = extract_official_event_image(html, SAGREFVG_BASE_URL)

    if re.search(r"\bquesto evento\s+(?:e|è)\s+passat[oa]\b", normalized, re.IGNORECASE):
        result = {"is_past": True, "date": None}
        set_cache(sagrefvg_detail_cache, cache_key, result)
        return result

    # Livello 2: Controllo tetto massimo anni nell'HTML
    years_in_html = [int(y) for y in set(re.findall(r"\b(20\d{2})\b", normalized))]
    current_year = datetime.now().year
    if years_in_html and max(years_in_html) < current_year:
        result = {"is_past": True, "date": None}
        set_cache(sagrefvg_detail_cache, cache_key, result)
        return result

    # Livello 3: API Nascosta di WordPress
    api_link = re.search(r'href="(https://sagrefvg\.it/wp-json/wp/v2/tribe_events/\d+)"', res.text)
    if api_link:
        try:
            req_api = requests.get(api_link.group(1), headers=headers, timeout=SAGREFVG_DETAIL_TIMEOUT)
            if req_api.status_code == 200:
                data = req_api.json()
                start_date_str = data.get('meta', {}).get('_EventStartDate')
                if start_date_str:
                    api_date_obj = datetime.strptime(start_date_str, "%Y-%m-%d %H:%M:%S").date()
                    if api_date_obj < datetime.now().date():
                        result = {"is_past": True, "date": None}
                        set_cache(sagrefvg_detail_cache, cache_key, result)
                        return result
        except Exception as e:
            print("Errore lettura API JSON SagreFVG:", e)

    date_matches = extract_event_date_matches(text)

    if date_matches and event_dates_are_past(date_matches):
        result = {
            "is_past": True,
            "date": date_matches[0][:45],
        }
        set_cache(sagrefvg_detail_cache, cache_key, result)
        return result

    result = {
        "is_past": False,
        "date": date_matches[0][:45] if date_matches else None,
        "image": image,
    }
    set_cache(sagrefvg_detail_cache, cache_key, result)
    return result


def parse_sagrefvg_api_datetime(value: str):
    if not value:
        return None

    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(str(value), fmt)
        except ValueError:
            continue

    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


def format_sagrefvg_api_date(start_value: str, end_value: str) -> str:
    start_dt = parse_sagrefvg_api_datetime(start_value)
    end_dt = parse_sagrefvg_api_datetime(end_value)

    if not start_dt:
        return "Data in aggiornamento"

    start_text = format_numeric_date(start_dt.strftime("%d/%m/%Y"))

    if end_dt and end_dt.date() != start_dt.date():
        end_text = format_numeric_date(end_dt.strftime("%d/%m/%Y"))
        return f"{start_text} - {end_text}"

    return start_text


def normalize_sagrefvg_api_float(value):
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None

    if math.isnan(parsed):
        return None

    return parsed


def normalize_sagrefvg_api_event(raw_event: dict):
    if not isinstance(raw_event, dict):
        return None

    title = clean_event_title(raw_event.get("title") or "")
    url = raw_event.get("url") or raw_event.get("rest_url") or ""
    venue = raw_event.get("venue") if isinstance(raw_event.get("venue"), dict) else {}
    categories = raw_event.get("categories") if isinstance(raw_event.get("categories"), list) else []
    first_category = categories[0] if categories else {}
    description = clean_event_text(raw_event.get("description") or "")

    if not title or not url:
        return None

    if re.search(r"\b(annullat[oa]|rinviat[oa]|cancellat[oa])\b", normalize_for_search(f"{title} {description}")):
        return None

    category_source = first_category.get("name") if isinstance(first_category, dict) else ""
    image = raw_event.get("image") if isinstance(raw_event.get("image"), dict) else {}
    image_url = image.get("url") or ""
    place = clean_event_text(venue.get("venue") or venue.get("city") or extract_place_from_title(title))
    event_city = clean_event_text(venue.get("city") or place)
    address = clean_event_text(venue.get("address") or "")
    lat = normalize_sagrefvg_api_float(venue.get("geo_lat"))
    lon = normalize_sagrefvg_api_float(venue.get("geo_lng"))
    classification = classify_sagrefvg_event(title, description)

    event = {
        "title": title,
        "place": place,
        "event_city": event_city,
        "venue": place,
        "date": format_sagrefvg_api_date(raw_event.get("start_date"), raw_event.get("end_date")),
        "source": "SagreFVG",
        "url": url,
        "image": image_url or None,
        "is_real": True,
        "category_source": clean_event_text(category_source or ""),
        **classification,
    }

    if address:
        event["address"] = address

    if lat is not None and lon is not None:
        event["lat"] = lat
        event["lon"] = lon
        event["location_confidence"] = "exact" if address else "municipality"
    else:
        event["location_confidence"] = "city_text" if event_city else "none"

    return event


def fetch_sagrefvg_events_api(limit: int = 3):
    today = datetime.now().date()
    horizon = today + timedelta(days=EVENTS_UPCOMING_WINDOW_DAYS)
    per_page = max(10, min(EVENTS_PRELOAD_LIMIT, EVENTS_RESPONSE_MAX))
    headers = {
        "User-Agent": "Meteo-Friul-App/1.0",
        "Accept": "application/json",
    }
    params = {
        "page": 1,
        "per_page": per_page,
        # The Events Calendar treats start_date/end_date as bounds on both
        # endpoints. That drops a festival which starts inside our window but
        # ends just after it. Query by interval overlap instead: an event is
        # useful when it starts before the horizon and ends after today.
        "starts_before": f"{horizon.isoformat()} 23:59:59",
        "ends_after": f"{today.isoformat()} 00:00:00",
        "status": "publish",
    }

    res = requests.get(SAGREFVG_API_EVENTS_URL, params=params, headers=headers, timeout=10)
    res.raise_for_status()
    data = res.json()
    raw_events = data.get("events") if isinstance(data, dict) else []

    events = []
    for raw_event in raw_events or []:
        event = normalize_sagrefvg_api_event(raw_event)
        if event:
            events.append(event)

    events.sort(
        key=lambda item: (
            event_date_sort_value(item),
            -int(item.get("priority", 0) or 0),
            normalize_for_search(item.get("title")),
        )
    )

    return events[: max(1, min(limit, EVENTS_RESPONSE_MAX))]


def fetch_sagrefvg_events(city: str, limit: int = 3):
    cache_key = make_cache_key("events", EVENTS_CACHE_VERSION, "sagrefvg", city, limit)
    cached = get_from_cache(events_cache, cache_key, EVENTS_CACHE_TTL)

    if cached:
        return cached

    try:
        api_events = fetch_sagrefvg_events_api(limit)
        if api_events:
            set_cache(events_cache, cache_key, api_events)
            return api_events
    except Exception as e:
        print("Errore eventi SagreFVG API:", e)

    try:
        aliases = city_aliases(city)
        headers = {
            "User-Agent": "Meteo-Friul-App/1.0",
        }

        events = []
        seen_urls = set()
        seen_titles = set()
        detail_fetches = 0

        for url, params in sagrefvg_candidate_urls(city):
            try:
                res = requests.get(url, params=params, headers=headers, timeout=10)
                res.raise_for_status()
            except Exception as e:
                print("Errore lettura SagreFVG:", e)
                continue

            html = res.text
            links = extract_sagrefvg_links(html)

            for link in links:
                context = find_context(html, link["start"], link["end"])
                context_lower = normalize_for_search(context)
                title_lower = normalize_for_search(link["title"])

                if "questo evento è passato" in context_lower or "questo evento e passato" in context_lower:
                    continue

                if re.search(r"\b(annullat[oa]|rinviat[oa]|cancellat[oa])\b", title_lower) or\
                   re.search(r"\b(annullat[oa]|rinviat[oa]|cancellat[oa])\b", context_lower):
                    continue

                current_year = datetime.now().year
                years_in_title = [int(y) for y in re.findall(r"\b(20\d{2})\b", title_lower)]
                years_in_url = [int(y) for y in re.findall(r"\b(20\d{2})\b", link["url"])]
                years_in_context = [int(y) for y in re.findall(r"\b(20\d{2})\b", context_lower)]
                all_years = years_in_title + [y for y in years_in_url if y >= 2000] + years_in_context

                if any(year < current_year for year in all_years):
                    continue

                # La ricerca interna deve restare locale.
                # Le pagine categoria, invece, possono proporre eventi di zona.
                is_category_page = "/categoria/" in normalize_for_search(url)
                matches_city = any(
                    alias in context_lower or alias in title_lower
                    for alias in aliases
                )
                extracted_place = extract_event_place_candidate(context, city)
                extracted_place_lower = normalize_for_search(extracted_place)
                matches_extracted_place = bool(extracted_place) and any(
                    alias in extracted_place_lower
                    for alias in aliases
                )

                if not matches_city and not matches_extracted_place and not is_category_page:
                    continue

                if is_category_page and not matches_city and not matches_extracted_place:
                    if not extracted_place:
                        continue

                title_key = re.sub(r"[^a-z0-9à-ÿ]+", "", title_lower)

                if link["url"] in seen_urls or title_key in seen_titles:
                    continue

                seen_urls.add(link["url"])
                seen_titles.add(title_key)

                classification = classify_sagrefvg_event(link["title"], context)
                detail = {
                    "is_past": False,
                    "date": None,
                }

                if detail_fetches < SAGREFVG_DETAIL_LIMIT:
                    detail_fetches += 1
                    detail = fetch_sagrefvg_event_detail(link["url"], headers)

                if detail.get("is_past"):
                    continue

                events.append(
                    {
                        "title": link["title"],
                        "place": extracted_place or extract_place_from_title(link["title"]),
                        "date": detail.get("date") or extract_date_from_context(context),
                        "source": "SagreFVG",
                        "url": link["url"],
                        "image": detail.get("image"),
                        "is_real": True,
                        **classification,
                    }
                )

        events.sort(
            key=lambda item: (
                event_date_sort_value(item),
                -int(item.get("priority", 0) or 0),
                -event_quality_score(item, aliases),
            )
        )

        result = events[: max(1, min(limit, EVENTS_RESPONSE_MAX))]
        set_cache(events_cache, cache_key, result)
        return result

    except Exception as e:
        print("Errore eventi SagreFVG:", e)
        return []


PROLOCOFVG_TOPIC_CATEGORY_MAP = {
    "interesse locale": {
        "category": "cultura",
        "category_label": "Interesse locale",
        "priority": 70,
        "weather_sensitivity": "medium",
        "is_traditional": False,
    },
    "feste tradizionali": {
        "category": "sagra",
        "category_label": "Feste tradizionali",
        "priority": 92,
        "weather_sensitivity": "high",
        "is_traditional": True,
    },
    "enogastronomia": {
        "category": "food_wine",
        "category_label": "Enogastronomia",
        "priority": 88,
        "weather_sensitivity": "medium",
        "is_traditional": True,
    },
    "fiere e mercatini": {
        "category": "mercato",
        "category_label": "Fiere e mercatini",
        "priority": 88,
        "weather_sensitivity": "high",
        "is_traditional": True,
    },
    "rievocazioni": {
        "category": "cultura",
        "category_label": "Rievocazioni",
        "priority": 74,
        "weather_sensitivity": "high",
        "is_traditional": True,
    },
    "eventi pro loco": {
        "category": "sagra",
        "category_label": "Eventi Pro Loco",
        "priority": 86,
        "weather_sensitivity": "medium",
        "is_traditional": True,
    },
}


def classify_prolocofvg_event(topic: str, title: str = "", context: str = ""):
    topic_key = normalize_for_search(topic)

    for known_topic, classification in PROLOCOFVG_TOPIC_CATEGORY_MAP.items():
        if topic_key == known_topic or known_topic in topic_key:
            result = dict(classification)
            if topic:
                result["category_label"] = topic.strip()
            return result

    classification = classify_event(title, context)

    if classification.get("category") == "generico":
        classification.update(
            {
                "category": "generico",
                "category_label": topic.strip() if topic else "Evento Pro Loco",
                "priority": max(classification.get("priority", 0), 60),
            }
        )

    return classification


def extract_labeled_value(text: str, label: str, next_labels: list[str]) -> str | None:
    boundaries = "|".join(re.escape(item) for item in next_labels)
    pattern = rf"\b{re.escape(label)}\b\s*(.*?)(?=\s+\b(?:{boundaries})\b|$)"
    match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)

    if not match:
        return None

    value = re.sub(r"\s+", " ", match.group(1)).strip(" .,;:-")
    return value or None


def extract_prolocofvg_links(html: str):
    links = []
    seen = set()
    pattern = re.compile(
        r'<a[^>]+href=["\']([^"\']*/eventi-delle-associate/[^"\']+)["\'][^>]*>(.*?)</a>',
        re.IGNORECASE | re.DOTALL,
    )

    for match in pattern.finditer(html):
        href = match.group(1)
        inner_html = match.group(2)
        url = urljoin(PROLOCOFVG_BASE_URL, href)
        normalized_url = normalize_for_search(url)

        if normalized_url.rstrip("/") == normalize_for_search(PROLOCOFVG_EVENTS_URL).rstrip("/"):
            continue

        if "?page=" in normalized_url or url in seen:
            continue

        title = clean_event_title(inner_html)

        if not title or len(title) < 4:
            continue

        lowered_title = normalize_for_search(title)
        blocked_titles = {
            "eventi",
            "eventi delle associate",
            "dettaglio evento",
            "leggi tutto",
            "scopri di più",
            "scopri di più",
        }

        if lowered_title in blocked_titles:
            continue

        context = find_context(html, match.start(), match.end())
        context_lower = normalize_for_search(context)

        if re.search(r"\b(annullat[oa]|rinviat[oa]|cancellat[oa])\b", lowered_title) or\
           re.search(r"\b(annullat[oa]|rinviat[oa]|cancellat[oa])\b", context_lower):
            continue

        seen.add(url)
        links.append(
            {
                "title": title,
                "url": url,
                "context": context,
                "start": match.start(),
                "end": match.end(),
            }
        )

    return links


def prolocofvg_candidate_urls():
    return [
        PROLOCOFVG_EVENTS_URL,
        f"{PROLOCOFVG_EVENTS_URL}?page=2",
    ]


def select_next_numeric_date(dates: list[str]) -> tuple[str | None, bool]:
    parsed = []

    for date_text in dates:
        parsed_date = parse_event_date(date_text)
        if parsed_date:
            parsed.append((parsed_date, date_text))

    if not parsed:
        return None, False

    today = datetime.now().date()
    future = [(date_value, raw) for date_value, raw in parsed if date_value >= today]

    if future:
        date_value, raw = min(future, key=lambda item: item[0])
        return format_numeric_date(raw), False

    return format_numeric_date(max(parsed, key=lambda item: item[0])[1]), True


def prolocofvg_detail_is_invalid(text: str, title: str | None, date_text: str | None, is_past: bool) -> bool:
    normalized = normalize_for_search(text)
    title_key = normalize_for_search(title)

    if re.search(r"\b(annullat[oa]|rinviat[oa]|cancellat[oa]|evento\s+annullato|evento\s+rinviato)\b", normalized):
        return True

    if is_past:
        return True

    # Pro Loco pubblica eventi datati: senza una data futura leggibile non li
    # trattiamo come eventi validi per l'app.
    if not date_text or not parse_event_date(date_text):
        return True

    if not title_key or title_key in {
        "eventi",
        "eventi delle associate",
        "dettaglio evento",
        "pro loco",
    }:
        return True

    return False


def fetch_prolocofvg_event_detail(url: str, headers: dict):
    cache_key = make_cache_key("prolocofvg_detail", url)
    cached = get_from_cache(prolocofvg_detail_cache, cache_key, SAGREFVG_DETAIL_CACHE_TTL)

    if cached is not None:
        return cached

    try:
        res = requests.get(url, headers=headers, timeout=SAGREFVG_DETAIL_TIMEOUT)
        res.raise_for_status()

        html = res.text
        text = clean_event_text(html)
        detail_labels = ["Tipo", "Città", "Indirizzo", "Sito Web", "Adatto per", "Posizione", "Quando"]

        topic = extract_labeled_value(text, "Tipo", detail_labels[1:])
        event_city = extract_labeled_value(text, "Città", detail_labels[2:])
        address = extract_labeled_value(text, "Indirizzo", detail_labels[3:])
        dates = re.findall(r"\b\d{1,2}/\d{1,2}/\d{4}\b", text)
        date_text, is_past = select_next_numeric_date(dates)

        title_matches = re.findall(
            r"<h2[^>]*>(.*?)</h2>",
            html,
            flags=re.IGNORECASE | re.DOTALL,
        )
        title = clean_event_title(title_matches[-1]) if title_matches else None

        if prolocofvg_detail_is_invalid(text, title, date_text, is_past):
            result = {
                "title": title,
                "date": date_text,
                "is_past": True,
                "invalid_reason": "invalid_or_past",
            }
            set_cache(prolocofvg_detail_cache, cache_key, result)
            return result

        image = None
        for image_match in re.finditer(
            r'<img[^>]+src=["\']([^"\']+)["\'][^>]*>',
            html,
            flags=re.IGNORECASE | re.DOTALL,
        ):
            src = image_match.group(1)
            src_lower = normalize_for_search(src)
            if any(blocked in src_lower for blocked in ["cover", "mobile", "logo"]):
                continue
            image = urljoin(PROLOCOFVG_BASE_URL, src)
            break

        maps_url = None
        for href_match in re.finditer(
            r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>',
            html,
            flags=re.IGNORECASE | re.DOTALL,
        ):
            href = unescape(href_match.group(1))
            href_lower = normalize_for_search(href)
            if "google.com/maps" in href_lower or "maps.app.goo.gl" in href_lower:
                maps_url = href
                break

        lat, lon = extract_coordinates_from_url(maps_url)

        if lat is not None and lon is not None:
            location_confidence = "exact"
        elif event_city:
            lat, lon = geocode_event_place(event_city)
            location_confidence = "municipality" if lat is not None and lon is not None else "city_text"
        else:
            location_confidence = "none"

        result = {
            "title": title,
            "place": event_city,
            "event_city": event_city,
            "address": address,
            "maps_url": maps_url,
            "lat": lat,
            "lon": lon,
            "location_confidence": location_confidence,
            "date": date_text,
            "type": topic,
            "image": image,
            "is_past": is_past,
        }

        result.update(classify_prolocofvg_event(topic or "", title or "", text))
        set_cache(prolocofvg_detail_cache, cache_key, result)
        return result
    except Exception as e:
        print("Errore dettaglio Pro Loco FVG:", e)
        return {"is_past": False}


def fetch_prolocofvg_events(city: str, limit: int = 3):
    cache_key = make_cache_key("events", EVENTS_CACHE_VERSION, "prolocofvg", city, limit)
    cached = get_from_cache(events_cache, cache_key, EVENTS_CACHE_TTL)

    if cached:
        return cached

    try:
        aliases = city_aliases(city)
        headers = {
            "User-Agent": "Meteo-Friul-App/1.0",
        }
        links = []
        for candidate_url in prolocofvg_candidate_urls():
            try:
                res = requests.get(candidate_url, headers=headers, timeout=10)
                res.raise_for_status()
                links.extend(extract_prolocofvg_links(res.text))
            except Exception as e:
                print("Errore lettura Pro Loco FVG:", e)
                continue

        events = []
        seen_urls = set()
        seen_titles = set()
        detail_fetches = 0

        for link in links:
            context = link.get("context") or ""
            context_lower = normalize_for_search(context)
            title_lower = normalize_for_search(link["title"])

            if re.search(r"\b(annullat[oa]|rinviat[oa]|cancellat[oa])\b", title_lower) or\
               re.search(r"\b(annullat[oa]|rinviat[oa]|cancellat[oa])\b", context_lower):
                continue

            if link["url"] in seen_urls:
                continue

            detail = {}
            if detail_fetches < PROLOCOFVG_DETAIL_LIMIT:
                detail_fetches += 1
                detail = fetch_prolocofvg_event_detail(link["url"], headers)

            if detail.get("is_past"):
                continue

            title = detail.get("title") or link["title"]
            date_text = detail.get("date") or extract_date_from_context(context)
            title_key = re.sub(r"[^a-z0-9à-ÿ]+", "", normalize_for_search(title))

            if not title_key or title_key in seen_titles:
                continue

            if not parse_event_date(date_text):
                continue

            verified_place = detail.get("event_city") or detail.get("place")
            resolved_place = verified_place or extract_event_place_candidate(context, city)
            place_lower = normalize_for_search(resolved_place)
            verified_place_lower = normalize_for_search(verified_place)
            title_has_local_match = any(alias in title_lower for alias in aliases)
            verified_place_has_local_match = any(alias in verified_place_lower for alias in aliases)
            has_local_text_match = any(
                alias in place_lower or alias in context_lower or alias in title_lower
                for alias in aliases
            )

            if (
                detail.get("location_confidence") in (None, "none")
                and not verified_place_has_local_match
                and not title_has_local_match
            ):
                continue

            place = resolved_place or city

            seen_urls.add(link["url"])
            seen_titles.add(title_key)

            classification = {
                key: detail[key]
                for key in (
                    "category",
                    "category_label",
                    "priority",
                    "weather_sensitivity",
                    "is_traditional",
                )
                if key in detail
            } or classify_prolocofvg_event("", title, context)

            events.append(
                {
                    "title": title,
                    "place": place,
                    "date": date_text,
                    "source": "Pro Loco FVG",
                    "url": link["url"],
                    "image": detail.get("image"),
                    "event_city": detail.get("event_city"),
                    "address": detail.get("address"),
                    "maps_url": detail.get("maps_url"),
                    "lat": detail.get("lat"),
                    "lon": detail.get("lon"),
                    "location_confidence": detail.get("location_confidence"),
                    "is_real": True,
                    **classification,
                }
            )

        events.sort(
            key=lambda item: (
                event_date_sort_value(item),
                -int(item.get("priority", 0) or 0),
                -event_quality_score(item, aliases),
            )
        )

        result = events[: max(1, min(limit, EVENTS_RESPONSE_MAX))]
        set_cache(events_cache, cache_key, result)
        return result
    except Exception as e:
        print("Errore eventi Pro Loco FVG:", e)
        return []


def extract_paesiinfesta_links(html: str, default_category: str):
    links = []
    seen = set()
    heading_pattern = re.compile(
        r'<h2[^>]*>\s*<a[^>]+href=["\']([^"\']+)["\'][^>]*>(.*?)</a>\s*</h2>(.*?)(?=<h2|\Z)',
        re.IGNORECASE | re.DOTALL,
    )

    for match in heading_pattern.finditer(html):
        href = unescape(match.group(1)).strip()

        if href.startswith(("#", "mailto:", "tel:", "javascript:")):
            continue

        url = urljoin(PAESIINFESTA_BASE_URL, href)
        normalized_url = normalize_for_search(url)

        if not normalized_url.startswith(normalize_for_search(PAESIINFESTA_BASE_URL)):
            continue

        if any(fragment in normalized_url for fragment in ["/privacy", "/cookies", "/contattaci", "/archivio"]):
            continue

        if url in seen:
            continue

        place = clean_event_text(match.group(2))
        body = clean_event_text(match.group(3))
        date_match = re.search(
            r"\b(?:dal\s+)?\d{1,2}(?:[°º])?\s*(?:[-–]\s*\d{1,2})*(?:\s+(?:gennaio|febbraio|marzo|aprile|maggio|giugno|luglio|agosto|settembre|ottobre|novembre|dicembre))?(?:\s+al\s+\d{1,2}(?:[°º])?\s+)?(?:gennaio|febbraio|marzo|aprile|maggio|giugno|luglio|agosto|settembre|ottobre|novembre|dicembre)\s+\d{4}\b",
            body,
            re.IGNORECASE,
        )
        title = ""
        date_text = ""

        if date_match:
            date_text = date_match.group(0).strip(" .,;:-")
            title = clean_event_title(body[: date_match.start()])

        if not title or not date_text:
            continue

        seen.add(url)
        links.append(
            {
                "title": title,
                "place": place,
                "date": date_text[:80],
                "url": url,
                "context": body,
                "default_category": default_category,
            }
        )

    return links


def classify_paesiinfesta_event(title: str, context: str, default_category: str):
    classification = classify_event(title, context)

    if default_category == "rievocazioni" and classification.get("category") == "generico":
        classification = {
            "category": "cultura",
            "category_label": "Rievocazione storica",
            "priority": 78,
            "weather_sensitivity": "high",
            "is_traditional": True,
        }

    if default_category == "sagre" and classification.get("category") == "generico":
        classification = {
            "category": "sagra",
            "category_label": "Sagra / festa locale",
            "priority": 90,
            "weather_sensitivity": "high",
            "is_traditional": True,
        }

    if classification.get("category") in ["sagra", "food_wine", "mercato"]:
        classification["is_traditional"] = True
        classification["priority"] = max(classification.get("priority", 0), 88)

    return classification


def fetch_paesiinfesta_event_detail(url: str, headers: dict):
    cache_key = make_cache_key("paesiinfesta_detail", url)
    cached = get_from_cache(paesiinfesta_detail_cache, cache_key, SAGREFVG_DETAIL_CACHE_TTL)

    if cached is not None:
        return cached

    try:
        res = requests.get(url, headers=headers, timeout=SAGREFVG_DETAIL_TIMEOUT)
        res.raise_for_status()

        html = res.text
        text = clean_event_text(html)
        image = extract_official_event_image(html, PAESIINFESTA_BASE_URL)
        h1_match = re.search(r"<h1[^>]*>(.*?)</h1>", html, re.IGNORECASE | re.DOTALL)
        title = clean_event_title(h1_match.group(1)) if h1_match else None

        result = {
            "title": title,
            "image": image,
            "text": text[:2500],
        }
        set_cache(paesiinfesta_detail_cache, cache_key, result)
        return result
    except Exception as e:
        print("Errore dettaglio Paesi in Festa:", e)
        return {}


def geocode_paesiinfesta_place(place: str):
    candidates = [clean_event_text(place or "")]
    normalized = normalize_for_search(place)
    tail_match = re.search(r"\bdi\s+([A-Za-z\u00c0-\u00ff'\u2019\s.-]{3,35})$", place or "", re.IGNORECASE)

    if tail_match and not normalized.startswith(("meduna di ", "pasiano di ", "sesto al ", "san michele al ")):
        candidates.append(tail_match.group(1).strip(" .,;:-"))

    if " di pordenone" in normalized:
        candidates.append(re.sub(r"\s+di\s+pordenone\b", "", place, flags=re.IGNORECASE).strip())

    for candidate in dict.fromkeys(candidates):
        if not candidate:
            continue

        lat, lon = geocode_event_place(candidate)
        if lat is not None and lon is not None:
            return lat, lon

    return None, None


def fetch_paesiinfesta_events(city: str, limit: int = 3):
    cache_key = make_cache_key("events", EVENTS_CACHE_VERSION, "paesiinfesta", city, limit)
    cached = get_from_cache(events_cache, cache_key, EVENTS_CACHE_TTL)

    if cached:
        return cached

    try:
        headers = {
            "User-Agent": "Meteo-Friul-App/1.0",
        }
        source_pages = [
            (PAESIINFESTA_EVENTS_URLS[0], "sagre"),
            (PAESIINFESTA_EVENTS_URLS[1], "rievocazioni"),
        ]
        links = []

        for url, default_category in source_pages:
            try:
                res = requests.get(url, headers=headers, timeout=10)
                res.raise_for_status()
                links.extend(extract_paesiinfesta_links(res.text, default_category))
            except Exception as e:
                print("Errore lettura Paesi in Festa:", e)
                continue

        events = []
        seen = set()
        detail_fetches = 0
        aliases = city_aliases(city)

        for link in links:
            title = link["title"]
            date_text = link["date"]
            event_start, event_end = parse_event_date_range(date_text)

            if event_end and event_end < datetime.now().date():
                continue

            title_key = re.sub(
                r"[^a-z0-9\u00e0-\u00ff]+",
                "",
                normalize_for_search(f"{title}|{link.get('place')}|{date_text}"),
            )

            if not title_key or title_key in seen:
                continue

            seen.add(title_key)
            detail = {}

            if detail_fetches < PAESIINFESTA_DETAIL_LIMIT:
                detail_fetches += 1
                detail = fetch_paesiinfesta_event_detail(link["url"], headers)

            context = f"{link.get('context') or ''} {detail.get('text') or ''}"
            place = link.get("place") or extract_event_place_candidate(context, city)
            lat, lon = geocode_paesiinfesta_place(place) if place else (None, None)
            classification = classify_paesiinfesta_event(title, context, link.get("default_category"))

            events.append(
                {
                    "title": detail.get("title") or title,
                    "place": place,
                    "event_city": place,
                    "date": date_text,
                    "source": "Paesi in Festa",
                    "url": link["url"],
                    "image": detail.get("image"),
                    "lat": lat,
                    "lon": lon,
                    "location_confidence": "municipality" if lat is not None and lon is not None else "city_text",
                    "is_real": True,
                    **classification,
                }
            )

        events.sort(
            key=lambda item: (
                event_date_sort_value(item),
                -int(item.get("priority", 0) or 0),
                -event_quality_score(item, aliases),
            )
        )

        result = events[: max(1, min(limit, EVENTS_RESPONSE_MAX))]
        set_cache(events_cache, cache_key, result)
        return result
    except Exception as e:
        print("Errore eventi Paesi in Festa:", e)
        return []


def extract_place_from_title(title: str):
    clean_title = clean_event_text(title or "")

    patterns = [
        r"\ba\s+([^–\-|()]{3,45})\s*\((?:UD|PN|GO|TS|TV|VE)\)",
        r"\bdi\s+([^–\-|()]{3,45})\s*\((?:UD|PN|GO|TS|TV|VE)\)",
        r"\bin\s+([^–\-|()]{3,45})\s*\((?:UD|PN|GO|TS|TV|VE)\)",
        r"\b([A-Za-z\u00c0-\u00ff'\u2019\s.-]{3,45})\s*\((?:UD|PN|GO|TS|TV|VE)\)",
    ]

    for pattern in patterns:
        matches = re.findall(pattern, clean_title, re.IGNORECASE)
        if matches:
            place = matches[-1].strip(" .,;:-")
            place = re.sub(r"^(?:Sagra|Festa|Mostra|Maggio|Fiesta)\s+(?:di|dei|della|del|dal|dai)?\s*", "", place, flags=re.IGNORECASE).strip()

            if is_valid_event_place(place):
                return place

    return None


def fetch_generic_event_detail(url: str, headers: dict, cache: dict, cache_prefix: str, base_url: str):
    cache_key = make_cache_key(cache_prefix, url)
    cached = get_from_cache(cache, cache_key, SAGREFVG_DETAIL_CACHE_TTL)

    if cached is not None:
        return cached

    try:
        res = requests.get(url, headers=headers, timeout=SAGREFVG_DETAIL_TIMEOUT)
        res.raise_for_status()

        html = res.text
        text = clean_event_text(html)
        image = extract_official_event_image(html, base_url)
        h1_match = re.search(r"<h1[^>]*>(.*?)</h1>", html, re.IGNORECASE | re.DOTALL)
        title = clean_event_title(h1_match.group(1)) if h1_match else None
        maps_url = None

        for href_match in re.finditer(r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>', html, re.IGNORECASE | re.DOTALL):
            href = unescape(href_match.group(1))
            href_lower = normalize_for_search(href)
            if "google.com/maps" in href_lower or "maps.app.goo.gl" in href_lower:
                maps_url = href
                break

        result = {
            "title": title,
            "image": image,
            "text": text[:2500],
            "maps_url": maps_url,
        }
        set_cache(cache, cache_key, result)
        return result
    except Exception as e:
        print(f"Errore dettaglio {cache_prefix}:", e)
        return {}


def extract_anteprimasagre_links(html: str):
    links = []
    seen = set()
    pattern = re.compile(
        r'<h2[^>]*>\s*<a[^>]+href=["\']([^"\']+)["\'][^>]*>(.*?)</a>\s*</h2>(.*?)(?=<h2|\Z)',
        re.IGNORECASE | re.DOTALL,
    )

    for match in pattern.finditer(html):
        href = unescape(match.group(1)).strip()
        url = urljoin(ANTEPRIMASAGRE_BASE_URL, href)
        normalized_url = normalize_for_search(url)

        if not normalized_url.startswith(normalize_for_search(ANTEPRIMASAGRE_BASE_URL)):
            continue

        if any(fragment in normalized_url for fragment in ["/privacy", "/contatti", "/chi-siamo", "/newsletter", "/whatsapp"]):
            continue

        if url in seen:
            continue

        title = clean_event_title(match.group(2))
        context = clean_event_text(match.group(3))

        if not title or len(title) < 5:
            continue

        if not re.search(r"\b(?:sagra|sagre|festa|fiesta|mostra|sapori|maggio|festeggiamenti)\b", normalize_for_search(title)):
            continue

        date_match = re.search(
            r"\b(?:dal\s+)?\d{1,2}(?:[°º])?\s*(?:[-–]\s*\d{1,2})*(?:\s+(?:gennaio|febbraio|marzo|aprile|maggio|giugno|luglio|agosto|settembre|ottobre|novembre|dicembre))?(?:\s+al\s+\d{1,2}(?:[°º])?\s+)?(?:gennaio|febbraio|marzo|aprile|maggio|giugno|luglio|agosto|settembre|ottobre|novembre|dicembre)\s+\d{4}\b",
            context,
            re.IGNORECASE,
        )
        date_text = date_match.group(0).strip(" .,;:-") if date_match else extract_date_from_context(context)

        seen.add(url)
        links.append(
            {
                "title": title,
                "url": url,
                "date": date_text,
                "place": extract_place_from_title(title) or extract_event_place_candidate(context),
                "context": context,
            }
        )

    return links


def fetch_anteprimasagre_events(city: str, limit: int = 3):
    cache_key = make_cache_key("events", EVENTS_CACHE_VERSION, "anteprimasagre", city, limit)
    cached = get_from_cache(events_cache, cache_key, EVENTS_CACHE_TTL)

    if cached:
        return cached

    try:
        headers = {"User-Agent": "Meteo-Friul-App/1.0"}
        res = requests.get(ANTEPRIMASAGRE_EVENTS_URL, headers=headers, timeout=10)
        res.raise_for_status()

        events = []
        seen = set()
        detail_fetches = 0
        aliases = city_aliases(city)

        for link in extract_anteprimasagre_links(res.text):
            _, event_end = parse_event_date_range(link.get("date"))
            if event_end and event_end < datetime.now().date():
                continue

            key = re.sub(r"[^a-z0-9\u00e0-\u00ff]+", "", normalize_for_search(f"{link['title']}|{link.get('date')}"))
            if not key or key in seen:
                continue
            seen.add(key)

            link_date_start, _ = parse_event_date_range(link.get("date"))
            detail = {}
            should_fetch_detail = detail_fetches < ANTEPRIMASAGRE_DETAIL_LIMIT or not link_date_start

            if should_fetch_detail:
                detail_fetches += 1
                detail = fetch_generic_event_detail(
                    link["url"],
                    headers,
                    anteprimasagre_detail_cache,
                    "anteprimasagre_detail",
                    ANTEPRIMASAGRE_BASE_URL,
                )

            title = detail.get("title") or link["title"]
            context = f"{link.get('context') or ''} {detail.get('text') or ''}"
            date_text = link.get("date")
            date_start, date_end = parse_event_date_range(date_text)

            if not date_start:
                extracted_detail_date = extract_date_from_context(context)
                detail_date_start, _ = parse_event_date_range(extracted_detail_date)
                if detail_date_start:
                    date_text = extracted_detail_date
                    date_start, date_end = parse_event_date_range(date_text)

            if date_end and date_end < datetime.now().date():
                continue

            place = link.get("place") or extract_place_from_title(title) or extract_event_place_candidate(context, city)
            if place:
                place = re.sub(r"\s*\((?:UD|PN|GO|TS|TV|VE)?$", "", place, flags=re.IGNORECASE).strip()
            lat, lon = extract_coordinates_from_url(detail.get("maps_url"))

            if lat is None or lon is None:
                lat, lon = geocode_paesiinfesta_place(place) if place else (None, None)

            classification = classify_sagrefvg_event(title, context)
            events.append(
                {
                    "title": title,
                    "place": place,
                    "event_city": place,
                    "date": date_text,
                    "source": "Anteprima Sagre",
                    "url": link["url"],
                    "image": detail.get("image"),
                    "maps_url": detail.get("maps_url"),
                    "lat": lat,
                    "lon": lon,
                    "location_confidence": "exact" if detail.get("maps_url") and lat is not None else ("municipality" if lat is not None else "city_text"),
                    "is_real": True,
                    **classification,
                }
            )

        events.sort(
            key=lambda item: (
                event_date_sort_value(item),
                -int(item.get("priority", 0) or 0),
                -event_quality_score(item, aliases),
            )
        )

        result = events[: max(1, min(limit, EVENTS_RESPONSE_MAX))]
        set_cache(events_cache, cache_key, result)
        return result
    except Exception as e:
        print("Errore eventi Anteprima Sagre:", e)
        return []


def eventifvg_is_promotional_or_weak(title: str, place: str, context: str):
    text = normalize_for_search(f"{title} {place} {context}")

    blocked = [
        "karaoke",
        "aperitivo",
        "aperitiva",
        "dj set",
        "discoteca",
        "lounge bar",
        "white cafe",
        "baretto",
        "trattoria",
        "ogni mercoledi",
        "ogni giovedi",
        "ogni venerdi",
        "grand opening",
        "night",
        "party",
    ]

    if any(item in text for item in blocked):
        return True

    public_signals = [
        "festival",
        "teatro",
        "concerto",
        "orchestra",
        "mostra",
        "sagra",
        "festa",
        "manifestazione",
        "mercatino",
        "fiera",
        "biker fest",
        "musical",
        "piazza",
    ]

    return not any(signal in text for signal in public_signals)


def normalize_eventifvg_date(value: str):
    text = clean_event_text(value)
    current_year = datetime.now().year
    month_names = (
        "gennaio|febbraio|marzo|aprile|maggio|giugno|luglio|agosto|settembre|ottobre|novembre|dicembre"
    )
    matches = re.findall(rf"\b({month_names})\s+(\d{{1,2}})", text, re.IGNORECASE)

    if not matches:
        return f"{text} {current_year}".strip()

    formatted = [f"{int(day)} {month.lower()} {current_year}" for month, day in matches]

    if len(formatted) >= 2:
        return f"{formatted[0]} - {formatted[-1]}"

    return formatted[0]


def extract_eventifvg_links(html: str):
    links = []
    seen = set()
    pattern = re.compile(
        r'<h4[^>]*>\s*<a[^>]+href=(?:"([^"]+)"|\'([^\']+)\'|([^\s>]+))[^>]*>(.*?)</a>\s*</h4>(.*?)(?=<h4|\Z)',
        re.IGNORECASE | re.DOTALL,
    )

    for match in pattern.finditer(html):
        href = unescape(match.group(1) or match.group(2) or match.group(3) or "").strip()
        url = urljoin(EVENTIFVG_BASE_URL, href)

        if not normalize_for_search(url).startswith(normalize_for_search(EVENTIFVG_BASE_URL)):
            continue

        if url in seen:
            continue

        title = clean_event_title(match.group(4))
        body = clean_event_text(match.group(5))
        date_match = re.search(
            r"\b(?:gennaio|febbraio|marzo|aprile|maggio|giugno|luglio|agosto|settembre|ottobre|novembre|dicembre)\s+\d{1,2}(?:\s*@\s*\d{1,2}:\d{2})?(?:\s*[–-]\s*(?:gennaio|febbraio|marzo|aprile|maggio|giugno|luglio|agosto|settembre|ottobre|novembre|dicembre)\s+\d{1,2}(?:\s*@\s*\d{1,2}:\d{2})?)?",
            body,
            re.IGNORECASE,
        )

        if not title or not date_match:
            continue

        date_text = date_match.group(0).strip(" .,;:-")
        after_date = body[date_match.end():].strip(" .,;:-")
        place = re.split(r"\s{2,}|\.{3}|, \.", after_date, maxsplit=1)[0].strip(" .,;:-")
        place = clean_event_text(place)

        if eventifvg_is_promotional_or_weak(title, place, body):
            continue

        seen.add(url)
        links.append(
            {
                "title": title,
                "url": url,
                "date": date_text,
                "place": place[:80] if place else None,
                "context": body,
            }
        )

    return links


def iter_jsonld_events(payload):
    if isinstance(payload, list):
        for item in payload:
            yield from iter_jsonld_events(item)
        return

    if not isinstance(payload, dict):
        return

    item_type = payload.get("@type")
    if item_type == "Event" or (isinstance(item_type, list) and "Event" in item_type):
        yield payload

    for value in payload.values():
        if isinstance(value, (dict, list)):
            yield from iter_jsonld_events(value)


def extract_eventifvg_jsonld_events(html: str):
    events = []

    def append_payload_events(payload):
        for item in iter_jsonld_events(payload):
            title = clean_event_title(item.get("name"))
            url = item.get("url")
            start_date = str(item.get("startDate") or "")
            end_date = str(item.get("endDate") or "")
            location = item.get("location") or {}
            address = location.get("address") if isinstance(location, dict) else {}
            place = location.get("name") if isinstance(location, dict) else ""

            if isinstance(address, dict):
                street = address.get("streetAddress") or ""
                locality = address.get("addressLocality") or ""
                place = locality or place or street

            description = clean_event_text(item.get("description") or "")

            if not title or not url or not start_date:
                continue

            if eventifvg_is_promotional_or_weak(title, place, description):
                continue

            date_text = ""
            try:
                start = datetime.fromisoformat(start_date.replace("Z", "+00:00")).date()
                month_labels = ["", "gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno", "luglio", "agosto", "settembre", "ottobre", "novembre", "dicembre"]
                date_text = f"{start.day} {month_labels[start.month]} {start.year}"

                if end_date:
                    end = datetime.fromisoformat(end_date.replace("Z", "+00:00")).date()
                    if end != start:
                        date_text += f" - {end.day} {month_labels[end.month]} {end.year}"
            except ValueError:
                date_text = normalize_eventifvg_date(start_date)

            events.append(
                {
                    "title": title,
                    "url": url,
                    "date": date_text,
                    "place": clean_event_text(place),
                    "context": description,
                    "image": item.get("image"),
                }
            )

    for script_match in re.finditer(
        r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        html,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        raw = unescape(script_match.group(1)).strip()

        if not raw:
            continue

        try:
            payload = json.loads(raw)
        except ValueError:
            continue

        append_payload_events(payload)

    if not events and '"@type":"Event"' in html:
        decoder = json.JSONDecoder()
        for match in re.finditer(r'\{"@context":"http://schema\.org","@type":"Event"', html):
            try:
                payload, _ = decoder.raw_decode(html[match.start():])
            except ValueError:
                continue

            append_payload_events(payload)

    return events


def fetch_eventifvg_events(city: str, limit: int = 3):
    cache_key = make_cache_key("events", EVENTS_CACHE_VERSION, "eventifvg", city, limit)
    cached = get_from_cache(events_cache, cache_key, EVENTS_CACHE_TTL)

    if cached:
        return cached

    try:
        headers = {"User-Agent": "Meteo-Friul-App/1.0"}
        res = requests.get(EVENTIFVG_EVENTS_URL, headers=headers, timeout=10)
        res.raise_for_status()

        events = []
        seen = set()
        detail_fetches = 0
        aliases = city_aliases(city)

        links = extract_eventifvg_jsonld_events(res.text) or extract_eventifvg_links(res.text)

        for link in links:
            raw_date = link.get("date")
            date_text = raw_date if parse_event_date(raw_date) else normalize_eventifvg_date(raw_date)
            _, event_end = parse_event_date_range(date_text)
            if event_end and event_end < datetime.now().date():
                continue

            key = re.sub(r"[^a-z0-9\u00e0-\u00ff]+", "", normalize_for_search(f"{link['title']}|{date_text}|{link.get('place')}"))
            if not key or key in seen:
                continue
            seen.add(key)

            detail = {"image": link.get("image")}
            if detail_fetches < EVENTIFVG_DETAIL_LIMIT and not detail.get("image"):
                detail_fetches += 1
                detail = fetch_generic_event_detail(
                    link["url"],
                    headers,
                    eventifvg_detail_cache,
                    "eventifvg_detail",
                    EVENTIFVG_BASE_URL,
                )

            title = detail.get("title") or link["title"]
            context = f"{link.get('context') or ''} {detail.get('text') or ''}"
            place = extract_event_place_candidate(link.get("place") or "", city) or link.get("place") or extract_event_place_candidate(context, city)
            lat, lon = extract_coordinates_from_url(detail.get("maps_url"))

            if lat is None or lon is None:
                lat, lon = geocode_event_place(place) if place else (None, None)

            classification = classify_event(title, context)
            classification["priority"] = min(int(classification.get("priority", 55) or 55), 68)
            if classification.get("category") == "generico":
                classification["category_label"] = "Evento"

            events.append(
                {
                    "title": title,
                    "place": place,
                    "event_city": place,
                    "date": date_text,
                    "source": "EventiFVG",
                    "url": link["url"],
                    "image": detail.get("image"),
                    "maps_url": detail.get("maps_url"),
                    "lat": lat,
                    "lon": lon,
                    "location_confidence": "exact" if detail.get("maps_url") and lat is not None else ("municipality" if lat is not None else "city_text"),
                    "is_real": True,
                    **classification,
                }
            )

        events.sort(
            key=lambda item: (
                event_date_sort_value(item),
                -int(item.get("priority", 0) or 0),
                -event_quality_score(item, aliases),
            )
        )

        result = events[: max(1, min(limit, EVENTS_RESPONSE_MAX))]
        set_cache(events_cache, cache_key, result)
        return result
    except Exception as e:
        print("Errore eventi EventiFVG:", e)
        return []


def merge_events(*event_lists, city: str, limit: int = 3):
    aliases = city_aliases(city)
    seen = set()
    unique = []

    for event_list in event_lists:
        for event in event_list or []:
            title_key = normalize_for_search(event.get("title"))
            date_key = normalize_for_search(event.get("date"))
            place_key = normalize_for_search(event.get("place"))
            dedupe_key = re.sub(r"[^a-z0-9à-ÿ]+", "", f"{title_key}|{date_key}|{place_key}")

            if not title_key or dedupe_key in seen:
                continue

            seen.add(dedupe_key)
            unique.append(event)

    unique = dedupe_similar_events(unique, city)

    unique.sort(
        key=lambda item: (
            event_date_sort_value(item),
            -int(item.get("priority", 0) or 0),
            -event_quality_score(item, aliases),
        )
    )

    return unique[: max(1, min(limit, EVENTS_RESPONSE_MAX))]


def text_contains_alias(text: str, aliases: list[str]) -> bool:
    value = normalize_for_search(text)

    for alias in aliases:
        if not alias:
            continue

        pattern = rf"(?<![a-z0-9à-ÿ]){re.escape(alias)}(?![a-z0-9à-ÿ])"
        if re.search(pattern, value):
            return True

    return False


def is_local_event(city: str, event: dict) -> bool:
    aliases = city_aliases(city)
    title = event.get("title") or ""
    place = event.get("place") or ""
    event_city = event.get("event_city") or ""
    explicit_place = clean_event_text(event_city or place)

    if explicit_place:
        return text_contains_alias(explicit_place, aliases)

    return text_contains_alias(title, aliases)


def event_matches_requested_place(city: str, origin_lat, origin_lon, event: dict) -> bool:
    aliases = city_aliases(city)
    title = event.get("title") or ""
    place = event.get("place") or ""
    event_city = event.get("event_city") or ""
    explicit_place = clean_event_text(event_city or place)

    if explicit_place and text_contains_alias(explicit_place, aliases):
        return True

    event_lat, event_lon = event_location_coordinates(event)
    if origin_lat is not None and origin_lon is not None and event_lat is not None and event_lon is not None:
        try:
            return haversine_km(origin_lat, origin_lon, event_lat, event_lon) <= EVENTS_NEARBY_RADIUS_KM
        except (TypeError, ValueError):
            return False

    if explicit_place and normalize_for_search(explicit_place) != normalize_for_search(city):
        return False

    return text_contains_alias(title, aliases)


def filter_events_for_requested_place(city: str, origin_lat, origin_lon, events: list[dict]) -> list[dict]:
    return [
        event
        for event in events or []
        if event_matches_requested_place(city, origin_lat, origin_lon, event)
    ]


def select_events_by_scope(
    city: str,
    origin_lat: float,
    origin_lon: float,
    events: list[dict],
    limit: int,
):
    max_events = max(1, min(limit, EVENTS_RESPONSE_MAX))
    candidates = list(events or [])
    aliases = city_aliases(city)
    local_events = [
        event
        for event in candidates
        if is_local_event(city, event)
    ]

    if len(local_events) >= max_events:
        return local_events[:max_events], "local"

    if origin_lat is None or origin_lon is None:
        return local_events[:max_events], "local" if local_events else "none"

    geo_candidates = []
    local_ids = {id(event) for event in local_events}

    for index, event in enumerate(candidates):
        if id(event) in local_ids:
            continue

        event_lat, event_lon = event_location_coordinates(event)

        if event_lat is None or event_lon is None:
            continue

        distance = haversine_km(origin_lat, origin_lon, event_lat, event_lon)

        if distance > EVENTS_NEARBY_RADIUS_KM:
            continue

        geo_candidates.append(
            {
                "distance": distance,
                "event": event,
                "index": index,
            }
        )

    geo_candidates.sort(
        key=lambda item: (
            item["distance"],
            -int(item["event"].get("priority", 0) or 0),
            -event_quality_score(item["event"], aliases),
            item["index"],
        )
    )

    nearby = [
        item
        for item in geo_candidates
        if item["distance"] <= EVENTS_NEARBY_RADIUS_KM
    ]

    if nearby:
        nearby_events = [
            {
                **item["event"],
                "distance_km": round(item["distance"], 1),
                "distance_scope": "nearby",
            }
            for item in nearby
        ]

        promoted_nearby = []
        remaining_nearby = []

        for event in nearby_events:
            distance = float(event.get("distance_km") or EVENTS_NEARBY_RADIUS_KM + 1)
            if (
                distance <= EVENTS_NEARBY_PROMOTION_KM
                and event_is_traditional(event)
                and len(promoted_nearby) < EVENTS_NEARBY_PROMOTION_LIMIT
            ):
                promoted_nearby.append(event)
            else:
                remaining_nearby.append(event)

        if promoted_nearby:
            lead_count = min(EVENTS_LOCAL_LEAD_COUNT, len(local_events))
            selected = [
                *local_events[:lead_count],
                *promoted_nearby,
                *local_events[lead_count:],
                *remaining_nearby,
            ]
        else:
            selected = [
                *local_events,
                *nearby_events,
            ]
        return selected[:max_events], "local" if local_events else "nearby"

    return local_events[:max_events], "local" if local_events else "none"


def filter_relevant_nearby_events(city: str, events: list[dict]):
    candidates = list(events or [])

    if not candidates:
        return []

    aliases = city_aliases(city)
    city_text = normalize_for_search(city)

    stop_tokens = {
        "di",
        "del",
        "della",
        "de",
        "dal",
        "friuli",
        "val",
        "valle",
        "san",
        "santa",
        "santo",
    }

    city_tokens = [
        token
        for token in re.split(r"[^a-z0-9\u00e0-\u00ff]+", city_text)
        if len(token) >= 4 and token not in stop_tokens
    ]

    def contains_alias(text: str) -> bool:
        value = normalize_for_search(text)

        for alias in aliases:
            if not alias:
                continue

            pattern = rf"(?<![a-z0-9\u00e0-\u00ff]){re.escape(alias)}(?![a-z0-9\u00e0-\u00ff])"
            if re.search(pattern, value):
                return True

        return False

    def contains_distinctive_token(text: str) -> bool:
        value = normalize_for_search(text)
        return any(
            re.search(rf"(?<![a-z0-9\u00e0-\u00ff]){re.escape(token)}(?![a-z0-9\u00e0-\u00ff])", value)
            for token in city_tokens
        )

    def is_generic_or_navigation(event: dict) -> bool:
        title = normalize_for_search(event.get("title"))

        if not title or len(title) < 4:
            return True

        blocked_titles = {
            "segnalaci la tua sagra",
            "tomas marcuzzi",
            "home",
            "sagre",
            "sagris",
            "eventi",
        }

        return title in blocked_titles

    def multi_place_penalty(event: dict) -> int:
        title = clean_event_text(event.get("title") or "")
        prefix = re.split(r"\s[-\u2013\u2014]\s", title, maxsplit=1)[0]
        comma_parts = [part.strip() for part in prefix.split(",") if part.strip()]

        if len(comma_parts) >= 4:
            return 3

        if len(comma_parts) >= 3:
            return 2

        return 0

    def relevance_score(event: dict) -> int:
        title = event.get("title") or ""
        place = event.get("place") or ""
        event_city = event.get("event_city") or ""

        if is_generic_or_navigation(event):
            return -100

        score = 0

        if contains_alias(title):
            score += 8
        elif contains_distinctive_token(title):
            score += 5

        if contains_alias(place):
            score += 3
        elif contains_distinctive_token(place):
            score += 2

        if contains_alias(event_city):
            score += 5
        elif contains_distinctive_token(event_city):
            score += 3

        if event.get("location_confidence") in ["exact", "municipality"]:
            score += 1

        title_place = normalize_for_search(f"{title} {place} {event_city}")
        if re.search(r"\((?:ud|pn|go|ts)\)", title_place):
            score += 1

        if normalize_for_search(event.get("date")) == "data in aggiornamento":
            score -= 1

        if normalize_for_search(event.get("category")) == "generico":
            score -= 1

        score -= multi_place_penalty(event)

        return score

    scored = [(relevance_score(event), index, event) for index, event in enumerate(candidates)]
    strong = [(score, index, event) for score, index, event in scored if score >= 5]
    weak = [(score, index, event) for score, index, event in scored if 0 < score < 5]

    selected = [*strong, *weak]

    if not selected:
        return []

    selected.sort(key=lambda item: (-item[0], item[1]))
    return [event for _, _, event in selected]


def diversify_events(events: list[dict], limit: int = 3):
    max_events = max(1, min(limit, EVENTS_RESPONSE_MAX))
    candidates = list(events or [])

    def category_key(event: dict) -> str:
        return normalize_for_search(
            event.get("category") or event.get("category_label") or "generico"
        )

    def source_key(event: dict) -> str:
        return normalize_for_search(event.get("source") or "unknown")

    def has_weak_date(event: dict) -> bool:
        date = normalize_for_search(event.get("date"))
        return not date or date == "data in aggiornamento"

    def sort_key(indexed_event):
        index, event = indexed_event
        date_penalty = 1 if has_weak_date(event) else 0
        return (
            event_date_sort_value(event),
            date_penalty,
            -int(event.get("priority", 0) or 0),
            index,
        )

    indexed = sorted(enumerate(candidates), key=sort_key)
    selected = []
    selected_keys = set()
    used_categories = set()
    used_sources = set()
    available_sources = {source_key(event) for event in candidates}
    available_categories = {category_key(event) for event in candidates}
    low_variety = len(available_categories) <= 1

    def event_key(event: dict) -> str:
        title_key = normalize_for_search(event.get("title"))
        date_key = normalize_for_search(event.get("date"))
        place_key = normalize_for_search(
            event.get("place") or event.get("event_city") or extract_place_from_title(event.get("title") or "")
        )
        return re.sub(r"\W+", "", f"{title_key}|{date_key}|{place_key}", flags=re.UNICODE)

    def add_event(index: int, event: dict):
        key = event_key(event)
        if not key or key in selected_keys:
            return False

        selected.append((index, event))
        selected_keys.add(key)
        used_categories.add(category_key(event))
        used_sources.add(source_key(event))
        return True

    if not low_variety:
        for index, event in indexed:
            if len(selected) >= max_events:
                break

            category = category_key(event)
            source = source_key(event)
            if category in used_categories:
                continue
            if source in used_sources and len(used_sources) < len(available_sources):
                continue

            add_event(index, event)

        for index, event in indexed:
            if len(selected) >= max_events:
                break

            category = category_key(event)
            if category in used_categories:
                continue

            add_event(index, event)

    for index, event in indexed:
        if len(selected) >= max_events:
            break

        source = source_key(event)
        if event.get("image"):
            add_event(index, event)
            continue

        if source in used_sources and len(used_sources) < len(available_sources):
            continue

        add_event(index, event)

    for index, event in indexed:
        if len(selected) >= max_events:
            break

        add_event(index, event)

    selected.sort(key=lambda item: item[0])
    return [event for _, event in selected[:max_events]]


def build_local_events_response(city: str, limit: int = 3, lat: float = None, lon: float = None, *, on_partial=None):
    origin_lat = lat
    origin_lon = lon

    if origin_lat is None or origin_lon is None:
        origin_lat, origin_lon = geocode_city(city)

    # Le fonti Eventi sono indipendenti: le leggiamo in parallelo e poi
    # applichiamo gli stessi filtri globali di localita, data e deduplica.
    source_fetchers = {
        "turismo": lambda: fetch_turismofvg_events(city, limit, origin_lat, origin_lon),
        "sagrefvg": lambda: fetch_sagrefvg_events(city, limit),
        "proloco": lambda: fetch_prolocofvg_events(city, limit),
        "paesiinfesta": lambda: fetch_paesiinfesta_events(city, limit),
        "eventifvg": lambda: fetch_eventifvg_events(city, limit),
    }
    guarded_official_events = load_guarded_official_events()
    if guarded_official_events:
        source_fetchers["official_guarded"] = lambda: guarded_official_events
    source_results = {key: [] for key in source_fetchers}

    executor = ThreadPoolExecutor(max_workers=len(source_fetchers))
    futures = {
        executor.submit(fetcher): key
        for key, fetcher in source_fetchers.items()
    }

    completed_source_keys = set()
    pending_source_keys = set()

    try:
        collection_started = time.monotonic()
        completed, pending = wait(futures.keys(), timeout=EVENTS_SOURCE_COLLECTION_TIMEOUT)

        for future in completed:
            key = futures[future]
            completed_source_keys.add(key)
            try:
                source_results[key] = future.result() or []
            except Exception as e:
                print(f"Errore fonte eventi {key}:", e)

        for future in pending:
            pending_source_keys.add(futures[future])
            if on_partial is None:
                future.cancel()

        if on_partial is not None and pending:
            on_partial(_assemble_local_events_response(city, limit, origin_lat, origin_lon,
                source_results, guarded_official_events, completed_source_keys, pending_source_keys))
            # Keep the original futures: no second scrape and no lost late
            # results. Only the local pilot opts into this background window.
            from concurrent.futures import FIRST_COMPLETED
            while pending and time.monotonic() - collection_started < 75:
                finished, pending = wait(pending, timeout=max(0, 75 - (time.monotonic() - collection_started)),
                                         return_when=FIRST_COMPLETED)
                for future in finished:
                    source_key = futures[future]
                    pending_source_keys.discard(source_key)
                    completed_source_keys.add(source_key)
                    try:
                        source_results[source_key] = future.result() or []
                    except Exception as exc:
                        print(f"Errore fonte eventi {source_key}: {exc}")
                if finished and pending:
                    on_partial(_assemble_local_events_response(city, limit, origin_lat, origin_lon,
                        source_results, guarded_official_events, completed_source_keys, pending_source_keys))

        if pending:
            skipped = ", ".join(sorted(pending_source_keys))
            print(f"Timeout fonti eventi {city}: uso risultati parziali, fonti lente: {skipped}")
    finally:
        executor.shutdown(wait=False, cancel_futures=True)

    return _assemble_local_events_response(city, limit, origin_lat, origin_lon,
        source_results, guarded_official_events, completed_source_keys, pending_source_keys)


def _assemble_local_events_response(city, limit, origin_lat, origin_lon,
                                   source_results, guarded_official_events,
                                   completed_source_keys, pending_source_keys):
    merged_limit = max(limit * 2, 6)
    source_events = filter_events_for_requested_place(
        city,
        origin_lat,
        origin_lon,
        [
            event
            for source_key in source_results
            for event in source_results[source_key]
        ],
    )
    candidate_events = filter_relevant_nearby_events(city, source_events)
    candidate_events = filter_past_events(candidate_events)
    candidate_events = filter_event_window_with_guarded_preview(
        candidate_events,
        guarded_official_events,
    )

    merged_events = merge_events(
        candidate_events,
        city=city,
        limit=merged_limit,
    )
    scoped_events, events_scope = select_events_by_scope(
        city,
        origin_lat,
        origin_lon,
        merged_events,
        merged_limit,
    )
    events = diversify_events(scoped_events, limit)
    events = enrich_selected_event_images(events)
    events = cache_selected_event_images(events)

    sources = list(
        dict.fromkeys(
            event.get("source")
            for event in events
            if event.get("source")
        )
    )

    source_counts = {
        key: len(value or [])
        for key, value in source_results.items()
    }
    has_source_payload = any(count > 0 for count in source_counts.values())
    has_pending_sources = bool(pending_source_keys)
    if events and has_pending_sources:
        cache_status = "partial"
    elif events:
        cache_status = "fresh"
    else:
        cache_status = "source_empty" if has_source_payload else "source_unavailable"

    return {
        "city": city,
        "events": events,
        "events_scope": events_scope,
        "source": "multi" if len(sources) > 1 else (sources[0] if sources else None),
        "sources": sources,
        "is_real": any(event.get("is_real") for event in events),
        "cache": {
            "status": cache_status,
            "event_contract_version": EVENTS_RESPONSE_CONTRACT_VERSION,
            "generated_at": datetime.now().isoformat(),
            "source_counts": source_counts,
            "completed_sources": sorted(completed_source_keys),
            "pending_sources": sorted(pending_source_keys),
        },
    }


def local_events_cache_key(city: str, limit: int, lat: float = None, lon: float = None):
    lat_value = None
    lon_value = None

    try:
        if lat is not None and not hasattr(lat, "default"):
            lat_value = round(float(lat), 4)
    except (TypeError, ValueError):
        lat_value = None

    try:
        if lon is not None and not hasattr(lon, "default"):
            lon_value = round(float(lon), 4)
    except (TypeError, ValueError):
        lon_value = None

    if lat_value is None or lon_value is None:
        city_text = str(city or "").strip()
        known_coords = CITY_COORDS.get(city_text) or EVENT_PLACE_COORDS.get(normalize_place_name(city_text))

        if known_coords:
            try:
                lat_value = round(float(known_coords["lat"]), 4)
                lon_value = round(float(known_coords["lon"]), 4)
            except (KeyError, TypeError, ValueError):
                lat_value = None
                lon_value = None

    return make_cache_key(
        "local-events-response",
        LOCAL_EVENTS_RESPONSE_CACHE_VERSION,
        city,
        limit,
        lat_value if lat_value is not None else "city",
        lon_value if lon_value is not None else "city",
    )


def normalized_local_events_limit(limit: int) -> int:
    try:
        value = int(limit)
    except (TypeError, ValueError):
        value = EVENTS_PRELOAD_LIMIT

    return max(1, min(value, EVENTS_RESPONSE_MAX))


def local_events_collection_limit(limit: int) -> int:
    return max(normalized_local_events_limit(limit), EVENTS_PRELOAD_LIMIT)


def limit_local_events_response(response: dict | None, limit: int) -> dict | None:
    if not isinstance(response, dict):
        return response

    max_events = normalized_local_events_limit(limit)
    events = response.get("events")

    if not isinstance(events, list) or len(events) <= max_events:
        return response

    limited_events = events[:max_events]
    limited = dict(response)
    limited["events"] = limited_events

    sources = list(
        dict.fromkeys(
            event.get("source")
            for event in limited_events
            if isinstance(event, dict) and event.get("source")
        )
    )
    limited["sources"] = sources
    limited["source"] = "multi" if len(sources) > 1 else (sources[0] if sources else None)
    limited["is_real"] = any(
        bool(event.get("is_real"))
        for event in limited_events
        if isinstance(event, dict)
    )

    return limited


def local_events_cache_doc_id(key: str) -> str:
    return hashlib.sha256(str(key or "").encode("utf-8")).hexdigest()


def local_events_count(response: dict | None) -> int:
    events = response.get("events") if isinstance(response, dict) else None
    return len(events) if isinstance(events, list) else 0


def local_events_pending_sources(response: dict | None) -> list[str]:
    cache_meta = response.get("cache") if isinstance(response, dict) else None
    pending = cache_meta.get("pending_sources") if isinstance(cache_meta, dict) else None

    if not isinstance(pending, list):
        return []

    return [
        str(source or "").strip()
        for source in pending
        if str(source or "").strip()
    ]


def is_partial_local_events_response(response: dict | None) -> bool:
    return bool(local_events_pending_sources(response))


def is_test_local_events_response(response: dict | None) -> bool:
    if not isinstance(response, dict):
        return False

    source = str(response.get("source") or "").strip().lower()
    sources = {
        str(source_item or "").strip().lower()
        for source_item in response.get("sources") or []
    }

    if source == "test" or "test" in sources:
        return True

    events = response.get("events")
    if not isinstance(events, list):
        return False

    return any(str(event.get("source") or "").strip().lower() == "test" for event in events if isinstance(event, dict))


def clone_local_events_response_with_cache(
    response: dict,
    status: str,
    age_seconds: float | None = None,
    storage: str = "",
) -> dict:
    cloned = normalize_event_images_for_response(response)
    cached_events = cloned.get("events")
    if isinstance(cached_events, list):
        upgraded_events = []
        for event in cached_events:
            if not isinstance(event, dict):
                continue

            upgraded = dict(event)
            # Le versioni precedenti conservavano le coordinate fornite dal
            # venue SagreFVG senza qualificarle. Provengono comunque dai campi
            # geo_lat/geo_lng della sede ufficiale e sono quindi utilizzabili
            # come destinazione esatta anche durante la migrazione della cache.
            if (
                normalize_for_search(upgraded.get("source")) == "sagrefvg"
                and upgraded.get("lat") is not None
                and upgraded.get("lon") is not None
                and not upgraded.get("location_confidence")
            ):
                upgraded["location_confidence"] = "exact"

            upgraded_events.append(upgraded)

        city = str(cloned.get("city") or "").strip()
        cloned["events"] = dedupe_similar_events(upgraded_events, city)
        sources = list(
            dict.fromkeys(
                event.get("source")
                for event in cloned["events"]
                if event.get("source")
            )
        )
        cloned["sources"] = sources
        cloned["source"] = "multi" if len(sources) > 1 else (sources[0] if sources else None)
        cloned["is_real"] = any(event.get("is_real") for event in cloned["events"])

    cache_meta = dict(cloned.get("cache") or {})
    cache_meta["status"] = status
    cache_meta["event_contract_version"] = EVENTS_RESPONSE_CONTRACT_VERSION

    if age_seconds is not None:
        cache_meta["age_seconds"] = int(max(0, age_seconds))

    if storage:
        cache_meta["storage"] = storage

    cloned["cache"] = cache_meta
    return cloned


def load_persistent_local_events_cache(key: str):
    db = get_firestore_client()
    if not db:
        return None

    try:
        snapshot = db.collection("local_event_responses").document(local_events_cache_doc_id(key)).get()
        if not snapshot.exists:
            return None

        data = snapshot.to_dict() or {}
        response = data.get("response")
        saved_at_epoch = data.get("saved_at_epoch")

        if not isinstance(response, dict) or not response.get("events"):
            return None
        if is_test_local_events_response(response):
            return None

        try:
            saved_at = datetime.fromtimestamp(float(saved_at_epoch))
        except (TypeError, ValueError, OSError):
            return None

        age = (datetime.now() - saved_at).total_seconds()
        if age < 0 or age > EVENTS_PERSISTENT_STALE_TTL:
            return None

        return response, saved_at, age
    except Exception as error:
        print("Errore lettura cache persistente eventi:", error)
        return None


def store_persistent_local_events_cache(key: str, response: dict) -> bool:
    if local_events_count(response) <= 0:
        return False
    if is_test_local_events_response(response):
        return False

    db = get_firestore_client()
    if not db:
        return False

    try:
        db.collection("local_event_responses").document(local_events_cache_doc_id(key)).set(
            {
                "key": key,
                "version": LOCAL_EVENTS_RESPONSE_CACHE_VERSION,
                "city": response.get("city") or "",
                "count": local_events_count(response),
                "sources": response.get("sources") or [],
                "saved_at": datetime.now().isoformat(),
                "saved_at_epoch": time.time(),
                "response": response,
            }
        )
        return True
    except Exception as error:
        print("Errore scrittura cache persistente eventi:", error)
        return False


def should_replace_local_events_cache(candidate: dict | None, existing: dict | None, existing_age: float | None = None) -> bool:
    if is_test_local_events_response(candidate):
        return False

    candidate_count = local_events_count(candidate)
    if candidate_count <= 0:
        return False

    existing_count = local_events_count(existing)
    if existing_count <= 0:
        # Al primo avvio è preferibile una risposta parziale ma utile a una
        # schermata vuota. La salviamo anche su Firestore così tutte le istanze
        # Cloud Run possono servirla mentre le fonti lente vengono riprovate.
        return True

    candidate_is_partial = is_partial_local_events_response(candidate)
    existing_is_partial = is_partial_local_events_response(existing)

    if candidate_is_partial:
        # Una raccolta incompleta non deve degradare una cache completa. Può
        # sostituire un'altra parziale soltanto se conserva tutte le fonti già
        # concluse e contiene almeno lo stesso numero di eventi.
        if not existing_is_partial:
            return False

        candidate_cache = candidate.get("cache") if isinstance(candidate, dict) else None
        existing_cache = existing.get("cache") if isinstance(existing, dict) else None
        candidate_completed = {
            str(source or "").strip()
            for source in (candidate_cache or {}).get("completed_sources") or []
            if str(source or "").strip()
        }
        existing_completed = {
            str(source or "").strip()
            for source in (existing_cache or {}).get("completed_sources") or []
            if str(source or "").strip()
        }
        preserves_completed_sources = candidate_completed.issuperset(existing_completed)
        adds_completed_source = candidate_completed != existing_completed
        adds_events = candidate_count > existing_count
        return preserves_completed_sources and (adds_completed_source or adds_events)

    if candidate_count >= existing_count:
        return True

    if existing_age is not None and existing_age > EVENTS_STALE_TTL:
        return True

    return candidate_count >= max(1, int(existing_count * EVENTS_CACHE_REPLACE_MIN_RATIO))


def load_best_local_events_cache_entry(key: str):
    entry = get_cache_entry(local_events_response_cache, key)
    if entry and entry[0]:
        return entry

    persistent_entry = load_persistent_local_events_cache(key)
    if not persistent_entry:
        return None, None

    response, saved_at, _ = persistent_entry
    set_cache_at(local_events_response_cache, key, response, saved_at)
    return response, saved_at


def refresh_local_events_cache(city: str, limit: int = EVENTS_PRELOAD_LIMIT, lat: float = None, lon: float = None):
    collection_limit = local_events_collection_limit(limit)
    key = local_events_cache_key(city, collection_limit, lat, lon)

    with local_events_refresh_lock:
        if key in local_events_refreshing:
            started_at = local_events_refresh_started.get(key)
            if started_at and time.time() - started_at <= EVENTS_REFRESHING_STALE_SECONDS:
                return None

            local_events_refreshing.discard(key)
            local_events_refresh_started.pop(key, None)

        local_events_refreshing.add(key)
        local_events_refresh_started[key] = time.time()
        local_events_refresh_outcomes.pop(key, None)

    try:
        existing_entry = load_best_local_events_cache_entry(key)
        existing_response = existing_entry[0] if existing_entry else None
        existing_age = cache_age_seconds(existing_entry) if existing_entry else None
        def publish_partial(partial):
            current = load_best_local_events_cache_entry(key)
            if should_replace_local_events_cache(partial, current[0] if current else None,
                                                cache_age_seconds(current) if current else None):
                set_cache(local_events_response_cache, key, partial)
                store_persistent_local_events_cache(key, partial)

        import os
        if os.environ.get('METEOFRIUL_LOCAL_WEATHER_PILOT') == '1':
            response = build_local_events_response(city, collection_limit, lat, lon, on_partial=publish_partial)
        else:
            response = build_local_events_response(city, collection_limit, lat, lon)
        latest = load_best_local_events_cache_entry(key)
        if latest:
            existing_response, existing_age = latest[0], cache_age_seconds(latest)
        should_replace = should_replace_local_events_cache(response, existing_response, existing_age)
        response_status = str((response.get("cache") or {}).get("status") or "source_unavailable")
        if should_replace:
            set_cache(local_events_response_cache, key, response)
            store_persistent_local_events_cache(key, response)
        else:
            print(
                "Refresh eventi non sostituisce cache migliore:",
                city,
                "nuovi=",
                local_events_count(response),
                "cache=",
                local_events_count(existing_response),
                (response.get("cache") or {}).get("status"),
                (response.get("cache") or {}).get("source_counts"),
            )
        set_local_events_refresh_outcome(
            key,
            response_status,
        )
        if should_replace:
            return response
        return existing_response if existing_response else (response if local_events_count(response) else None)
    except Exception as e:
        print("Errore refresh cache eventi:", city, e)
        set_local_events_refresh_outcome(key, "source_unavailable")
        return None
    finally:
        with local_events_refresh_lock:
            local_events_refreshing.discard(key)
            local_events_refresh_started.pop(key, None)


def schedule_local_events_refresh(city: str, limit: int = EVENTS_PRELOAD_LIMIT, lat: float = None, lon: float = None):
    thread = threading.Thread(
        target=refresh_local_events_cache,
        args=(city, limit, lat, lon),
        daemon=True,
    )
    thread.start()


def local_events_refresh_in_progress(key: str) -> bool:
    with local_events_refresh_lock:
        return key in local_events_refreshing


def set_local_events_refresh_outcome(key: str, status: str) -> None:
    with local_events_refresh_lock:
        local_events_refresh_outcomes[key] = (status, time.time())


def local_events_recent_refresh_outcome(key: str) -> str | None:
    with local_events_refresh_lock:
        entry = local_events_refresh_outcomes.get(key)
        if not entry:
            return None

        status, recorded_at = entry
        if time.time() - recorded_at > EVENTS_REFRESH_OUTCOME_TTL:
            local_events_refresh_outcomes.pop(key, None)
            return None

        return status
