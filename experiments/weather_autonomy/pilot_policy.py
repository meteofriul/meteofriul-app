"""Pure, fail-visible policies for the isolated ICON pilot, not the live app.

These thresholds and presentation rules are experimental product decisions, not
meteorological standards or a claim that ICON has been validated locally.
Only explicit UTC timestamps (``Z`` or a zero UTC offset) are accepted; all model
and row timestamps must be on an exact hour. ``now_utc`` may include minutes.
No function performs I/O, imports app code, or changes its input objects.
"""

from datetime import datetime, timedelta, timezone
import math
from numbers import Real


MAX_USABLE_RUN_AGE_HOURS = 30.0


def _utc(value, *, on_hour=False):
    if not isinstance(value, str):
        raise ValueError("timestamp must be an ISO string with explicit UTC")
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("timestamp must be an ISO string with explicit UTC") from exc
    if result.tzinfo is None or result.utcoffset() != timedelta(0):
        raise ValueError("timestamps must use explicit UTC, not local/naive time")
    if on_hour and (result.minute or result.second or result.microsecond):
        raise ValueError("forecast timestamps must fall on an exact hour")
    return result.astimezone(timezone.utc)


def _iso(value):
    return value.isoformat().replace("+00:00", "Z") if value is not None else None


def _finite_number(value, *, nonnegative=False, positive=False):
    if isinstance(value, bool) or not isinstance(value, Real):
        return False
    try:
        result = float(value)
    except (ValueError, OverflowError):
        return False
    return (
        math.isfinite(result)
        and (not nonnegative or result >= 0)
        and (not positive or result > 0)
    )


def assess_window(
    run_utc, valid_times_utc, now_utc, required_hours=48, max_age_hours=18
):
    """Assess a cached hourly forecast without confusing stale with healthy.

    Return ``status, coverage_hours, run_age_hours, reason, usable``. Coverage is
    the remaining span from ``now`` to the last point, NOT the number of rows.
    A dataset must contain the next hourly tick and reach ``now+required_hours``.
    Earlier points are allowed, but all points must be consecutive and >= run.
    This checks an hourly display horizon; it does not promise a measurement or
    interpolation at the current minute when the first point is in the future.

    A complete window is fresh through 18h (configurable), stale but usable after
    that, and expired after a fixed 30h safety cap. An insufficient window is
    expired irrespective of run age. Malformed data and future runs are invalid.
    The 18/30h thresholds are conservative pilot choices, not provider SLAs.
    """
    result = {
        "status": "invalid",
        "coverage_hours": None,
        "run_age_hours": None,
        "reason": "invalid_input",
        "usable": False,
    }
    if (
        not _finite_number(required_hours, positive=True)
        or not _finite_number(max_age_hours, positive=True)
        or max_age_hours > MAX_USABLE_RUN_AGE_HOURS
    ):
        result["reason"] = "invalid_thresholds"
        return result
    try:
        run = _utc(run_utc, on_hour=True)
        now = _utc(now_utc)
        if not isinstance(valid_times_utc, (list, tuple)) or not valid_times_utc:
            raise ValueError("valid_times_utc must contain hourly timestamps")
        points = [_utc(value, on_hour=True) for value in valid_times_utc]
    except ValueError as exc:
        result["reason"] = str(exc)
        return result

    age = (now - run).total_seconds() / 3600
    result["run_age_hours"] = age
    if age < 0:
        result["reason"] = "future_run"
        return result
    if any(point < run for point in points):
        result["reason"] = "forecast_before_run"
        return result
    if any(right - left != timedelta(hours=1) for left, right in zip(points, points[1:])):
        result["reason"] = "non_consecutive_hourly_timestamps"
        return result

    result["coverage_hours"] = max(0.0, (points[-1] - now).total_seconds() / 3600)
    try:
        next_tick = now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
        required_end = now + timedelta(hours=float(required_hours))
    except OverflowError:
        result["reason"] = "unrepresentable_horizon"
        return result
    if points[0] > next_tick:
        result.update(status="expired", reason="missing_near_term_coverage")
    elif points[-1] < required_end:
        result.update(status="expired", reason="insufficient_future_coverage")
    elif age > MAX_USABLE_RUN_AGE_HOURS:
        result.update(status="expired", reason="run_exceeds_30_hour_safety_cap")
    elif age > max_age_hours:
        result.update(status="stale", reason="complete_window_from_stale_run", usable=True)
    else:
        result.update(status="fresh", reason="complete_window_from_fresh_run", usable=True)
    return result


def rain_interval(
    prev,
    current,
    previous_quantum,
    current_quantum,
    *,
    previous_reference_mm=0.0,
    current_reference_mm=0.0,
):
    """Difference two same-run decoded accumulations without inventing a GRIB error bar.

    GRIB2 simple packing defines decoded values on a lattice: ``reference +
    packed_integer * quantum``. The quantum is the lattice spacing, not a
    provider-certified uncertainty. Consequently an unchanged decoded
    accumulation has a decoded interval amount of exactly zero. A non-zero
    change no larger than ``q_previous + q_current`` remains unresolved: a
    positive trace is not promoted into quantified rain, and a negative reset
    is not clipped into dry weather.

    A special fail-closed case is retained for independently packed messages
    whose packed integer remains zero while their tiny per-message reference
    floor changes. When that floor is so small that adding it to one lattice
    quantum has no effect even in binary64, it is normalized to zero at the
    decoded product's own resolution. This produces an explicit
    ``valid_reference_floor_normalized`` zero, rather than either fabricated
    rain or an unexplained missing value. Negative cumulative changes remain
    null/invalid; they are never clipped into dry weather.

    ``uncertainty_mm`` is retained for artifact compatibility, but it is only
    the conservative sum of the two lattice spacings. The GRIB metadata does
    not establish it as a statistical or worst-case uncertainty.
    """
    result = {
        "value_mm": None,
        "raw_increment_mm": None,
        "status": "invalid",
        "uncertainty_mm": None,
    }
    if not all(_finite_number(value, nonnegative=True) for value in (prev, current)):
        return result
    delta = float(current) - float(prev)
    result["raw_increment_mm"] = delta
    if not all(
        _finite_number(value, nonnegative=True)
        for value in (
            previous_quantum,
            current_quantum,
            previous_reference_mm,
            current_reference_mm,
        )
    ):
        return result

    if (
        prev < previous_reference_mm
        or current < current_reference_mm
        or (previous_quantum == 0 and prev != previous_reference_mm)
        or (current_quantum == 0 and current != current_reference_mm)
    ):
        return result

    def normalize_reference_floor(value, quantum, reference):
        normalize = (
            quantum > 0
            and reference > 0
            and value == reference
            and float(reference) + float(quantum) == float(quantum)
        )
        return (0.0, True) if normalize else (float(value), False)

    normalized_previous, normalized_previous_floor = normalize_reference_floor(
        prev, previous_quantum, previous_reference_mm
    )
    normalized_current, normalized_current_floor = normalize_reference_floor(
        current, current_quantum, current_reference_mm
    )
    normalized_delta = normalized_current - normalized_previous
    bound = float(previous_quantum) + float(current_quantum)
    if not math.isfinite(bound):
        return result
    result["uncertainty_mm"] = bound
    if normalized_delta == 0:
        status = (
            "valid_reference_floor_normalized"
            if delta != 0 and (normalized_previous_floor or normalized_current_floor)
            else "valid"
        )
        result.update(value_mm=0.0, status=status)
    elif normalized_delta < 0:
        if abs(normalized_delta) <= bound:
            result["status"] = "negative_within_encoding_resolution"
    elif normalized_delta <= bound:
        result["status"] = "positive_within_encoding_resolution"
    else:
        result.update(value_mm=normalized_delta, status="valid")
    return result


def aggregate_two_hour(rows):
    """Aggregate pairs of hourly END timestamps; do not skip every second row.

    Each row is a dict with ``valid_at_utc``, ``precipitation_previous_hour_mm``,
    ``wind_gust_m_s``, ``temperature_c`` and optional ``quality_flags`` (list of
    strings). Gust must already be a maximum over the previous hour, not an
    instantaneous wind speed or a maximum since run. Precipitation likewise
    must already be an interval amount, e.g. from :func:`rain_interval`.

    Output list records: ``start_at_utc``, ``end_at_utc``, ``source_hours``,
    ``precipitation_mm``, ``wind_gust_max_m_s``, ``temperature_min_c``,
    ``temperature_max_c``, ``temperature_end_c``, ``status``, ``quality_flags``.
    Temperature min/max are extrema of the two samples, not continuous extrema.
    Rain is summed, gust is maximised, and both temperature samples are retained
    as min/max plus the last endpoint. Missing members make the affected metric
    null; a known member is not substituted for a complete two-hour aggregate.
    Endpoint temperature may remain available on an otherwise incomplete pair.

    The final unpaired hour has status ``incomplete`` and null two-hour metrics.
    Invalid times, gaps, duplicates, out-of-order rows or invalid numeric values
    are explicit ``invalid`` records. A chronology problem nulls every metric in
    the affected record. Flags are sorted/deduplicated and inputs are untouched.
    A non-list/tuple top-level input raises ValueError; empty input returns [].
    """
    if not isinstance(rows, (list, tuple)):
        raise ValueError("rows must be a list or tuple")
    outputs = []
    preceding_time = None
    preceding_time_invalid = False
    for offset in range(0, len(rows), 2):
        pair = rows[offset:offset + 2]
        flags = set()
        invalid = False
        incomplete = len(pair) != 2
        if incomplete:
            flags.add("incomplete_two_hour_window")
        parsed = []
        times = []
        chronology_invalid = preceding_time_invalid
        if chronology_invalid:
            flags.add("invalid_previous_timestamp")
        for item in pair:
            if not isinstance(item, dict):
                item = {}
                invalid = True
                flags.add("invalid_row")
            parsed.append(item)
            item_flags = item.get("quality_flags", [])
            if not isinstance(item_flags, (list, tuple)) or not all(isinstance(flag, str) for flag in item_flags):
                invalid = True
                flags.add("invalid_quality_flags")
            else:
                flags.update(item_flags)
            try:
                instant = _utc(item.get("valid_at_utc"), on_hour=True)
            except ValueError:
                instant = None
                chronology_invalid = True
                flags.add("invalid_timestamp")
            if instant is not None and preceding_time is not None and instant - preceding_time != timedelta(hours=1):
                chronology_invalid = True
                flags.add("non_contiguous_hours")
            if instant is not None and preceding_time_invalid:
                chronology_invalid = True
                flags.add("invalid_previous_timestamp")
            times.append(instant)
            preceding_time = instant
            preceding_time_invalid = instant is None

        record = {
            "start_at_utc": _iso(times[0] - timedelta(hours=1)) if times[0] is not None else None,
            "end_at_utc": _iso(times[-1]),
            "source_hours": len(pair),
            "precipitation_mm": None,
            "wind_gust_max_m_s": None,
            "temperature_min_c": None,
            "temperature_max_c": None,
            "temperature_end_c": None,
            "status": None,
            "quality_flags": None,
        }
        validated = {}
        for key in ("precipitation_previous_hour_mm", "wind_gust_m_s", "temperature_c"):
            values = []
            for item in parsed:
                value = item.get(key)
                if value is None:
                    incomplete = True
                    flags.add(f"missing_{key}")
                    values.append(None)
                elif not _finite_number(value, nonnegative=key != "temperature_c"):
                    invalid = True
                    flags.add(f"invalid_{key}")
                    values.append(None)
                else:
                    values.append(float(value))
            validated[key] = values
        if chronology_invalid:
            invalid = True
        else:
            rain = validated["precipitation_previous_hour_mm"]
            gust = validated["wind_gust_m_s"]
            temperature = validated["temperature_c"]
            record["temperature_end_c"] = temperature[-1]
            if len(pair) == 2:
                if all(value is not None for value in rain):
                    total = sum(rain)
                    if math.isfinite(total):
                        record["precipitation_mm"] = total
                    else:
                        invalid = True
                        flags.add("precipitation_sum_overflow")
                if all(value is not None for value in gust):
                    record["wind_gust_max_m_s"] = max(gust)
                if all(value is not None for value in temperature):
                    record["temperature_min_c"] = min(temperature)
                    record["temperature_max_c"] = max(temperature)
        record["status"] = "invalid" if invalid else "incomplete" if incomplete else "valid"
        record["quality_flags"] = sorted(flags)
        outputs.append(record)
    return outputs
