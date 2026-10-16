"""Opt-in red diagnostic for the destructive weather-cache freshness lookup.

The filename intentionally does not match pytest's ordinary ``test_*.py``
discovery. Run it with ``pytest.weather-stale-diagnostics.ini``. The test is
expected to remain red until an expired-fresh entry is preserved for the
longer stale-fallback window.
"""

from datetime import datetime, timedelta
from unittest.mock import patch

import requests

from app.weather import forecast_engine, radar_engine


def test_radar_refresh_failure_reuses_entry_inside_stale_window():
    metadata = {
        "products": [
            {
                "id": "rain",
                "product_type": "SRI",
                "layer": "radar:sri",
                "style": "",
                "unit": "mm/h",
                "period": "PT5M",
                "period_minutes": 5,
                "time": "2026-09-12T10:00:00Z",
                "updated_at": "2026-09-12T10:00:00Z",
            }
        ]
    }
    age = radar_engine.RADAR_CACHE_TTL + 1
    assert age < radar_engine.RADAR_STALE_TTL

    radar_engine.clear_radar_cache()
    radar_engine.radar_cache[radar_engine.RADAR_CACHE_KEY] = (
        metadata,
        datetime.now() - timedelta(seconds=age),
    )

    try:
        with (
            patch.object(forecast_engine, "is_fvg_location", return_value=True),
            patch.object(
                radar_engine,
                "fetch_radar_dpc_metadata",
                side_effect=requests.RequestException("diagnostic offline"),
            ),
        ):
            result = radar_engine.get_weather_radar(
                "Udine",
                46.0635,
                13.2358,
            )

        assert result["available"] is True
        assert result["status"] == "stale"
        assert result["products"] == metadata["products"]
    finally:
        radar_engine.clear_radar_cache()
