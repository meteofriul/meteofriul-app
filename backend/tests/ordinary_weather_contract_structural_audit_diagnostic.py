"""Opt-in red diagnostics for ordinary-weather metadata aggregation.

The filename intentionally does not match pytest's ordinary ``test_*.py``
discovery. Run it with ``pytest.ordinary-weather-contract-diagnostics.ini``.
The assertion is expected to stay red until the bootstrap envelope derives its
freshness and data timestamp from the child payloads instead of stamping the
packaging instant as fresh weather data.
"""

from copy import deepcopy

from app.services.weather import WeatherService
from tests.test_weather_api import ALERTS_FIXTURE, CURRENT_FIXTURE, FORECAST_FIXTURE


def test_bootstrap_does_not_relabel_a_stale_current_child_as_fresh_now():
    current = deepcopy(CURRENT_FIXTURE)
    current["cache"] = {
        "status": "stale",
        "generated_at": "2026-09-11T03:00:00+00:00",
    }
    current["data_quality"] = {
        **current["data_quality"],
        "status": "stale",
    }

    forecast = deepcopy(FORECAST_FIXTURE)
    forecast["cache"] = {
        "status": "fresh",
        "generated_at": "2026-09-12T03:00:00+00:00",
    }

    service = WeatherService(
        current_loader=lambda city, lat, lon: {**current, "city": city},
        forecast_loader=lambda city, lat, lon: {**forecast, "city": city},
        alerts_loader=lambda *, force=False: deepcopy(ALERTS_FIXTURE),
    )

    result = service.get_bootstrap(
        city="Pordenone",
        lat=45.9567,
        lon=12.6605,
    )

    # A composite cannot be fresher than its stalest required child. Its data
    # timestamp must remain source-derived, not become the packaging instant.
    assert result.cache["status"] == "stale"
    assert result.cache["generated_at"] == current["cache"]["generated_at"]
