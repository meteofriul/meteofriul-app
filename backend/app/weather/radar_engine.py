"""Radar-DPC V2 metadata boundary for the UI3 weather API.

The backend exposes verified product timestamps and the public V2 tile contract.
Radar tiles remain served by the source and never pass through Meteo Friul.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone

import requests

from . import forecast_engine


RADAR_DPC_API_URL = "https://radar-api.protezionecivile.it/findLastProductByType"
# Kept for already-distributed clients. New clients use the V2 WebP tiles below.
RADAR_DPC_WMS_URL = "https://radar-geowebcache.protezionecivile.it/service/wms"
RADAR_DPC_TILES_BASE_URL = (
    "https://s3-prod-dpc-radar-webp-cache.s3.eu-south-1.amazonaws.com"
)
RADAR_DPC_PLATFORM_URL = (
    "https://mappe.protezionecivile.gov.it/it/mappe-e-dashboard-rischi/"
    "piattaforma-radar/"
)
RADAR_DPC_DOCS_URL = "https://dpc-radar.readthedocs.io/it/latest/"
RADAR_DPC_ORIGIN = "https://radar.protezionecivile.it"
RADAR_DPC_REFERER = f"{RADAR_DPC_ORIGIN}/"
OSMER_RADAR_MOVIE_URL = "https://www.osmer.fvg.it/radar-geo-movie.php?ln="
OSMER_RADAR_LAST_URL = "https://www.osmer.fvg.it/radar-geo.php?ln="
OSMER_RADAR_TRACKING_URL = "https://www.osmer.fvg.it/radar_tracking.php"

RADAR_CACHE_TTL = 4 * 60
RADAR_STALE_TTL = 30 * 60
RADAR_REQUEST_TIMEOUT = (4, 8)
RADAR_CACHE_KEY = "radar_dpc_fvg"

RADAR_DPC_SOURCE = {
    "id": "radar_dpc",
    "label": "Radar-DPC",
    "authority": "Dipartimento della Protezione Civile",
    "url": RADAR_DPC_PLATFORM_URL,
    "license": "CC BY-SA 4.0",
    "license_url": "https://creativecommons.org/licenses/by-sa/4.0/",
}

RADAR_DPC_PRODUCTS = (
    {
        "id": "rain",
        "product_type": "SRI",
        "layer": "radar:sri",
        "style": "",
        "unit": "mm/h",
    },
    {
        "id": "accumulation_1h",
        "product_type": "SRT1",
        "layer": "radar:srt1",
        "style": "",
        "unit": "mm",
    },
)

radar_cache: dict = {}


def radar_period_minutes(period: str) -> int:
    match = re.fullmatch(r"PT(\d+)M", str(period or "").strip().upper())
    return max(1, int(match.group(1))) if match else 5


def radar_timestamp_iso(value) -> str:
    timestamp = float(value)
    if timestamp > 1_000_000_000_000:
        timestamp /= 1000
    return datetime.fromtimestamp(timestamp, tz=timezone.utc).isoformat().replace(
        "+00:00",
        "Z",
    )


def fetch_radar_dpc_product_metadata(product: dict) -> dict:
    response = requests.get(
        RADAR_DPC_API_URL,
        params={"type": product["product_type"]},
        headers={
            "Accept": "application/json",
            "Origin": RADAR_DPC_ORIGIN,
            "Referer": RADAR_DPC_REFERER,
            "User-Agent": forecast_engine.HTTP_USER_AGENT,
        },
        timeout=RADAR_REQUEST_TIMEOUT,
    )
    response.raise_for_status()
    payload = response.json()
    records = payload.get("lastProducts") if isinstance(payload, dict) else None

    if not records or not isinstance(records[0], dict):
        raise ValueError(f"Radar product unavailable: {product['product_type']}")

    record = records[0]
    raw_time = record.get("time")
    if raw_time in (None, ""):
        raise ValueError(f"Radar product timestamp missing: {product['product_type']}")

    period = str(record.get("period") or "PT5M")
    updated_at = radar_timestamp_iso(raw_time)
    return {
        **product,
        "period": period,
        "period_minutes": radar_period_minutes(period),
        "time": updated_at,
        "updated_at": updated_at,
    }


def fetch_radar_dpc_metadata() -> dict:
    products = []
    for product in RADAR_DPC_PRODUCTS:
        try:
            products.append(fetch_radar_dpc_product_metadata(product))
        except (requests.RequestException, TypeError, ValueError):
            continue

    if not products:
        raise ValueError("No DPC radar products available")

    return {
        "products": products,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }


def _location(lat, lon) -> dict | None:
    if lat is None or lon is None:
        return None
    return {"lat": float(lat), "lon": float(lon)}


def build_radar_dpc_response(
    city: str,
    lat,
    lon,
    metadata: dict,
    status: str,
) -> dict:
    return {
        "city": city,
        "available": True,
        "mode": "radar_dpc_v2_tiles",
        "status": status,
        "source": RADAR_DPC_SOURCE,
        "location": _location(lat, lon),
        "products": metadata.get("products") or [],
        "tiles": {
            "provider": "radar_dpc_v2",
            "base_url": RADAR_DPC_TILES_BASE_URL,
            "format": "webp",
            "tile_size": 256,
            "zoom": 7,
            "encoding": "red_channel_normalized",
        },
        "wms": {
            "url": RADAR_DPC_WMS_URL,
            "version": "1.1.1",
            "crs": "EPSG:3857",
        },
        "links": {
            "platform": RADAR_DPC_PLATFORM_URL,
            "documentation": RADAR_DPC_DOCS_URL,
            "osmer_movie": OSMER_RADAR_MOVIE_URL,
            "osmer_last": OSMER_RADAR_LAST_URL,
            "osmer_tracking": OSMER_RADAR_TRACKING_URL,
        },
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "message": (
            "Radar observation only. It does not generate or modify official FVG alerts."
        ),
    }


def get_weather_radar(
    city: str,
    lat: float | None = None,
    lon: float | None = None,
    *,
    force: bool = False,
) -> dict:
    if not forecast_engine.is_fvg_location(city, lat, lon):
        return {
            "city": city,
            "available": False,
            "source": forecast_engine.OPEN_METEO_SOURCE,
            "mode": "not_available_outside_fvg",
            "status": "unavailable",
            "frames": [],
            "products": [],
            "location": _location(lat, lon),
            "certainty": "verified_scope",
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "message": "Radar regionale disponibile solo per localita FVG.",
        }

    if not force:
        cached_metadata = forecast_engine.get_from_cache(
            radar_cache,
            RADAR_CACHE_KEY,
            RADAR_CACHE_TTL,
        )
        if cached_metadata:
            return build_radar_dpc_response(city, lat, lon, cached_metadata, "cache")

    try:
        metadata = fetch_radar_dpc_metadata()
        forecast_engine.set_cache(radar_cache, RADAR_CACHE_KEY, metadata)
        return build_radar_dpc_response(city, lat, lon, metadata, "fresh")
    except (requests.RequestException, TypeError, ValueError) as error:
        stale_metadata = forecast_engine.get_stale_from_cache(
            radar_cache,
            RADAR_CACHE_KEY,
            RADAR_STALE_TTL,
        )
        if stale_metadata:
            response = build_radar_dpc_response(
                city,
                lat,
                lon,
                stale_metadata,
                "stale",
            )
            response["warning"] = "Latest radar metadata could not be refreshed."
            return response

        return {
            "city": city,
            "available": False,
            "source": RADAR_DPC_SOURCE,
            "mode": "radar_temporarily_unavailable",
            "status": "unavailable",
            "products": [],
            "location": _location(lat, lon),
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "links": {
                "platform": RADAR_DPC_PLATFORM_URL,
                "osmer_movie": OSMER_RADAR_MOVIE_URL,
                "osmer_last": OSMER_RADAR_LAST_URL,
            },
            "message": f"Radar temporaneamente non disponibile: {type(error).__name__}",
        }


def clear_radar_cache() -> None:
    radar_cache.clear()
