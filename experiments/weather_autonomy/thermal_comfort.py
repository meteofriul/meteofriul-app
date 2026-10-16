"""Offline thermal-index experiment; not imported by the weather application.

Sources checked on 2026-09-02:
* BOM: https://www.bom.gov.au/info/thermal_stress/
* NWS/WPC: https://www.wpc.ncep.noaa.gov/html/heatindex_equation.shtml
* NWS charts: https://www.weather.gov/tsa/heatindex and
  https://www.weather.gov/lwx/heat
* NWS: https://www.weather.gov/safety/cold-wind-chill-chart
* NWS height convention: https://www.weather.gov/media/twc/wind-chill-brochure.pdf

The BOM/Steadman approximation uses air temperature in degrees C, relative
humidity in percent and wind at 10 m in m/s. It represents an adult in shade;
solar/body radiation, wet clothing, individual physiology and activity are not
modelled. A calculation from forecast input is a model-derived estimate, not an
observation. None of these indices is a health warning or medical advice.

Heat Index (HI) and Wind Chill (WC) remain separate from apparent temperature
(AT); this experiment never switches between them to invent one "feels like"
value. HI assumes shade/light wind and does not use the supplied wind. WC uses
standard 10 m wind (converted to mph); the published formula already accounts
for reduction toward face height, so we do not reduce that wind a second time.

The NWS HI regression must not be extrapolated to arbitrary extremes. To keep
the experiment conservative, its non-null HI output is limited to NWS screening
>=80 F and the chart-covered rectangles described in _heat_index_domain.
This is an explicitly narrower experimental coverage policy, not a claim to
define the entire scientific domain. No input is silently clipped or imputed.
Missing/non-finite inputs fail explicitly; an index outside its domain returns
None plus an explanation rather than falling back to air temperature.
"""

from dataclasses import dataclass
import math
from numbers import Real


@dataclass(frozen=True)
class IndexEstimate:
    """An individual estimate in Celsius, with explicit availability metadata."""

    value_c: float | None
    status: str
    method: str
    notes: tuple[str, ...]


@dataclass(frozen=True)
class ThermalComfort:
    """Three distinct indices; deliberately no combined feels_like field."""

    apparent_temperature: IndexEstimate
    heat_index: IndexEstimate
    wind_chill: IndexEstimate


def _finite_real(value: float, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ValueError(f"{name} must be a finite numeric value, not missing/text/bool")
    try:
        result = float(value)
    except (OverflowError, ValueError) as exc:
        raise ValueError(f"{name} is not representable as a finite number") from exc
    if not math.isfinite(result):
        raise ValueError(f"{name} must be finite")
    return result


def _temperature(value: float) -> float:
    result = _finite_real(value, "temperature_c")
    if result <= -273.15:
        raise ValueError("temperature_c must be above absolute zero")
    return result


def _humidity(value: float) -> float:
    result = _finite_real(value, "relative_humidity_pct")
    if not 0 <= result <= 100:
        raise ValueError("relative_humidity_pct must be between 0 and 100")
    return result


def _wind(value: float) -> float:
    result = _finite_real(value, "wind_10m_m_s")
    if result < 0:
        raise ValueError("wind_10m_m_s must not be negative")
    return result


def kelvin_to_celsius(temperature_k: float) -> float:
    """Explicit conversion for GRIB Kelvin input; reject negative Kelvin."""
    value = _finite_real(temperature_k, "temperature_k")
    if value < 0:
        raise ValueError("temperature_k must not be negative")
    return value - 273.15


def wind_speed_to_m_s(speed: float, unit: str) -> float:
    """Convert a non-negative 10 m wind speed; this does not convert its height."""
    factors = {"m/s": 1.0, "km/h": 1 / 3.6, "mph": 0.44704, "knots": 1852 / 3600}
    if not isinstance(unit, str) or unit not in factors:
        raise ValueError("wind unit must be m/s, km/h, mph or knots")
    return _finite_real(_wind(speed) * factors[unit], "converted wind speed")


def vapour_pressure_hpa(temperature_c: float, relative_humidity_pct: float) -> float:
    """BOM humidity approximation; no assumption that RH is a fraction (0..1).

    The expression is undefined at -237.7 C and inappropriate below it. That
    mathematical guard does not assert physiological validity near the bound.
    """
    temperature = _temperature(temperature_c)
    humidity = _humidity(relative_humidity_pct)
    if temperature <= -237.7:
        raise ValueError("temperature_c is outside the vapour-pressure formula domain")
    exponent = 17.27 * (temperature / (237.7 + temperature))
    vapour_pressure = humidity / 100 * 6.105 * math.exp(exponent)
    return _finite_real(vapour_pressure, "vapour pressure")


def apparent_temperature_c(
    temperature_c: float, relative_humidity_pct: float, wind_10m_m_s: float
) -> float:
    """BOM shade AT = T + 0.33 e - 0.70 v - 4, without radiation correction."""
    temperature = _temperature(temperature_c)
    wind = _wind(wind_10m_m_s)
    vapour_pressure = vapour_pressure_hpa(temperature, relative_humidity_pct)
    result = temperature + 0.33 * vapour_pressure - 0.70 * wind - 4.00
    return _finite_real(result, "apparent temperature")


def _heat_index_domain(temperature_f: float, humidity: float) -> bool:
    """Conservative coverage, not an invented universal validity boundary.

    For RH 0..40%, use only 80..110 F (covered by the NWS LWX chart).
    Above 40%, use the rectangular interiors below the non-empty edge of the
    NWS Tulsa chart. For a humidity between rows, choose the wetter row's
    maximum temperature, never extrapolate into a blank cell. Values outside
    this deliberately limited experiment are withheld, not rounded or clipped.
    The regression itself always receives the original, unrounded inputs.
    """
    if not 80 <= temperature_f <= 110:
        return False
    max_temperature_by_humidity = (
        (40, 110), (45, 108), (50, 106), (55, 104), (60, 102),
        (65, 100), (70, 98), (75, 96), (80, 94), (85, 94),
        (90, 92), (95, 90), (100, 90),
    )
    return any(
        humidity <= row_humidity and temperature_f <= max_temperature
        for row_humidity, max_temperature in max_temperature_by_humidity
    )


def heat_index_c(temperature_c: float, relative_humidity_pct: float) -> IndexEstimate:
    """NWS screening + Rothfusz, within the conservative chart envelope.

    Below the screening threshold the simple NWS expression is used only for
    eligibility; it is not returned as a substitute for the BOM AT. The dry
    correction is specified by NWS for 80..112 F, but this experiment's overall
    upper limit is 110 F. Shade/light-wind assumptions are not a wind forecast.
    """
    temperature = _temperature(temperature_c)
    humidity = _humidity(relative_humidity_pct)
    temperature_f = _finite_real(temperature * 1.8 + 32, "temperature_f")
    method = "nws_rothfusz_heat_index"
    notes = ("Shade and light wind; not a health warning.",)
    simple = 0.5 * (temperature_f + 61 + (temperature_f - 68) * 1.2 + humidity * 0.094)
    screening = _finite_real((simple + temperature_f) / 2, "heat index screening")
    if screening < 80:
        return IndexEstimate(None, "not_applicable", method, notes + ("NWS screening is below 80 F.",))
    if not _heat_index_domain(temperature_f, humidity):
        return IndexEstimate(None, "outside_experiment_domain", method, notes + (
            "Outside the conservative NWS chart envelope; no extreme extrapolation.",
        ))

    t, rh = temperature_f, humidity
    result_f = (
        -42.379 + 2.04901523 * t + 10.14333127 * rh - 0.22475541 * t * rh
        - 0.00683783 * t * t - 0.05481717 * rh * rh
        + 0.00122874 * t * t * rh + 0.00085282 * t * rh * rh
        - 0.00000199 * t * t * rh * rh
    )
    if rh < 13 and 80 <= t <= 112:
        result_f -= (13 - rh) / 4 * math.sqrt((17 - abs(t - 95)) / 17)
    elif rh > 85 and 80 <= t <= 87:
        result_f += (rh - 85) / 10 * ((87 - t) / 5)
    result_c = _finite_real((result_f - 32) / 1.8, "heat index")
    return IndexEstimate(result_c, "estimated", method, notes)


def wind_chill_c(temperature_c: float, wind_10m_m_s: float) -> IndexEstimate:
    """NWS WC: T <= 50 F and wind > 3 mph, using 10 m wind without re-scaling."""
    temperature = _temperature(temperature_c)
    wind = _wind(wind_10m_m_s)
    method = "nws_2001_wind_chill"
    notes = ("No solar heating; not a health warning or frostbite-time prediction.",)
    if temperature > 10 or wind <= 3 * 0.44704:
        return IndexEstimate(None, "not_applicable", method, notes + (
            "Requires temperature <= 10 C and wind strictly above 3 mph.",
        ))
    temperature_f = _finite_real(temperature * 1.8 + 32, "temperature_f")
    wind_mph = _finite_real(wind / 0.44704, "wind_mph")
    wind_factor = wind_mph ** 0.16
    result_f = 35.74 + 0.6215 * temperature_f - 35.75 * wind_factor + 0.4275 * temperature_f * wind_factor
    result_c = _finite_real((result_f - 32) / 1.8, "wind chill")
    return IndexEstimate(result_c, "estimated", method, notes)


def calculate_thermal_comfort(
    *, temperature_c: float, relative_humidity_pct: float, wind_10m_m_s: float
) -> ThermalComfort:
    """Return separate model-derived indices; reject incomplete/invalid rows.

    Inputs must refer to the same place, forecast run and valid time. This pure
    function cannot verify provenance, heights or timestamps: the data adapter
    must enforce them before calling it. No network or provider is involved.
    Use dataclasses.asdict(result) for a JSON-ready result with explicit nulls.
    """
    apparent = apparent_temperature_c(temperature_c, relative_humidity_pct, wind_10m_m_s)
    return ThermalComfort(
        apparent_temperature=IndexEstimate(apparent, "estimated", "bom_steadman_shade", (
            "Adult in shade; 10 m wind; solar radiation is not included.",
            "Model-derived comfort estimate, not an observation or health warning.",
        )),
        heat_index=heat_index_c(temperature_c, relative_humidity_pct),
        wind_chill=wind_chill_c(temperature_c, wind_10m_m_s),
    )
