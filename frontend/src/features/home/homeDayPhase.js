import { useEffect, useState } from "react";

import { getSunCycle } from "../../domain/almanac/sunCycle";
import { getDateTimeFormatter } from "../../domain/dateTimeFormatters.js";

const DEFAULT_TIME_ZONE = "Europe/Rome";
const DEFAULT_FVG_LATITUDE = 46.0711;
const DEFAULT_FVG_LONGITUDE = 13.2346;
const MINUTE_MS = 60 * 1000;
const DAWN_DURATION_MINUTES = 45;
const MIDDAY_MARGIN_MINUTES = 90;
const SUNSET_DURATION_MINUTES = 45;
const LOCAL_DATE_TIME_PATTERN =
  /^(\d{4})-(\d{2})-(\d{2})[T ](\d{2}):(\d{2})(?::(\d{2})(?:\.\d+)?)?$/;
const CLOCK_PATTERN = /^(\d{2}):(\d{2})(?::\d{2})?$/;

function isValidCalendarDate(year, month, day) {
  const value = new Date(Date.UTC(year, month - 1, day));

  return (
    value.getUTCFullYear() === year &&
    value.getUTCMonth() === month - 1 &&
    value.getUTCDate() === day
  );
}

function parseLocalDateTime(value) {
  if (typeof value !== "string") return null;

  const match = value.trim().match(LOCAL_DATE_TIME_PATTERN);
  if (!match) return null;

  const [, yearValue, monthValue, dayValue, hourValue, minuteValue] = match;
  const year = Number(yearValue);
  const month = Number(monthValue);
  const day = Number(dayValue);
  const hour = Number(hourValue);
  const minute = Number(minuteValue);

  if (
    !isValidCalendarDate(year, month, day) ||
    hour < 0 ||
    hour > 23 ||
    minute < 0 ||
    minute > 59
  ) {
    return null;
  }

  return {
    dateKey: `${yearValue}-${monthValue}-${dayValue}`,
    minutes: hour * 60 + minute,
  };
}

function parseClock(value) {
  if (typeof value !== "string") return null;

  const match = value.trim().match(CLOCK_PATTERN);
  if (!match) return null;

  const hour = Number(match[1]);
  const minute = Number(match[2]);

  if (hour < 0 || hour > 23 || minute < 0 || minute > 59) return null;

  return hour * 60 + minute;
}

function getZonedDateTime(value, timeZone) {
  const date = value instanceof Date ? value : new Date(value);
  if (Number.isNaN(date.getTime())) return null;

  try {
    const parts = getDateTimeFormatter("en-CA", {
      day: "2-digit",
      hour: "2-digit",
      hourCycle: "h23",
      minute: "2-digit",
      month: "2-digit",
      timeZone,
      year: "numeric",
    }).formatToParts(date);
    const values = Object.fromEntries(parts.map(({ type, value: partValue }) => [type, partValue]));
    const hour = Number(values.hour);
    const minute = Number(values.minute);

    if (!values.year || !values.month || !values.day || !Number.isFinite(hour) || !Number.isFinite(minute)) {
      return null;
    }

    return {
      dateKey: `${values.year}-${values.month}-${values.day}`,
      day: Number(values.day),
      minutes: hour * 60 + minute,
      month: Number(values.month),
      year: Number(values.year),
    };
  } catch {
    return null;
  }
}

function getLocalNow(now, timeZone) {
  const localValue = parseLocalDateTime(now);
  if (localValue) {
    const [year, month, day] = localValue.dateKey.split("-").map(Number);

    return { ...localValue, day, month, year };
  }

  return getZonedDateTime(now ?? new Date(), timeZone);
}

function parseServerTime(value, localDateKey, timeZone) {
  const clockMinutes = parseClock(value);
  if (clockMinutes !== null) return clockMinutes;

  const localValue = parseLocalDateTime(value);
  if (localValue) {
    return localValue.dateKey === localDateKey ? localValue.minutes : null;
  }

  const zonedValue = getZonedDateTime(value, timeZone);
  if (!zonedValue || zonedValue.dateKey !== localDateKey) return null;

  return zonedValue.minutes;
}

function hasValidSolarPair(sunriseMinutes, sunsetMinutes) {
  return (
    Number.isFinite(sunriseMinutes) &&
    Number.isFinite(sunsetMinutes) &&
    sunriseMinutes >= 0 &&
    sunsetMinutes <= 24 * 60 &&
    sunsetMinutes > sunriseMinutes
  );
}

function getFiniteCoordinate(value, minimum, maximum) {
  if (value === null || value === undefined || value === "") return null;

  const number = Number(value);
  return Number.isFinite(number) && number >= minimum && number <= maximum ? number : null;
}

function getComputedSolarTimes({ localNow, latitude, longitude, timeZone }) {
  const validLatitude = getFiniteCoordinate(latitude, -90, 90) ?? DEFAULT_FVG_LATITUDE;
  const validLongitude = getFiniteCoordinate(longitude, -180, 180) ?? DEFAULT_FVG_LONGITUDE;

  try {
    // getSunCycle derives its calendar day from UTC fields. Noon UTC preserves the
    // intended local calendar date across both sides of the Europe/Rome DST switch.
    const calendarDate = new Date(Date.UTC(localNow.year, localNow.month - 1, localNow.day, 12));
    const cycle = getSunCycle({
      date: calendarDate,
      latitude: validLatitude,
      longitude: validLongitude,
      now: calendarDate,
      timeZone,
    });
    const sunriseMinutes = parseClock(cycle.sunrise);
    const sunsetMinutes = parseClock(cycle.sunset);

    return hasValidSolarPair(sunriseMinutes, sunsetMinutes)
      ? { sunriseMinutes, sunsetMinutes }
      : null;
  } catch {
    return null;
  }
}

function getPhase(minutes, sunriseMinutes, sunsetMinutes) {
  const solarNoonMinutes = (sunriseMinutes + sunsetMinutes) / 2;
  const dawnEnd = sunriseMinutes + DAWN_DURATION_MINUTES;
  const middayStart = solarNoonMinutes - MIDDAY_MARGIN_MINUTES;
  const middayEnd = solarNoonMinutes + MIDDAY_MARGIN_MINUTES;
  const sunsetStart = sunsetMinutes - SUNSET_DURATION_MINUTES;

  if (minutes < sunriseMinutes || minutes >= sunsetMinutes) return "night";
  if (minutes < dawnEnd) return "dawn";
  if (minutes < middayStart) return "morning";
  if (minutes < middayEnd) return "midday";
  if (minutes < sunsetStart) return "afternoon";

  return "sunset";
}

function getFallbackState(fallbackIsNight) {
  const isNight = Boolean(fallbackIsNight);

  return {
    phase: isNight ? "night" : "midday",
    isNight,
    source: "fallback",
    sunriseMinutes: null,
    sunsetMinutes: null,
  };
}

export function getHomeSolarState({
  now = new Date(),
  sunrise,
  sunset,
  latitude,
  longitude,
  timeZone = DEFAULT_TIME_ZONE,
  fallbackIsNight = false,
} = {}) {
  const localNow = getLocalNow(now, timeZone);
  if (!localNow) return getFallbackState(fallbackIsNight);

  let sunriseMinutes = parseServerTime(sunrise, localNow.dateKey, timeZone);
  let sunsetMinutes = parseServerTime(sunset, localNow.dateKey, timeZone);
  let source = "server";

  if (!hasValidSolarPair(sunriseMinutes, sunsetMinutes)) {
    const computedTimes = getComputedSolarTimes({ localNow, latitude, longitude, timeZone });
    if (!computedTimes) return getFallbackState(fallbackIsNight);

    ({ sunriseMinutes, sunsetMinutes } = computedTimes);
    source = "sun-cycle";
  }

  const phase = getPhase(localNow.minutes, sunriseMinutes, sunsetMinutes);

  return {
    phase,
    isNight: localNow.minutes < sunriseMinutes || localNow.minutes >= sunsetMinutes,
    source,
    sunriseMinutes,
    sunsetMinutes,
  };
}

export function getMillisecondsUntilNextMinute(now = new Date()) {
  const value = now instanceof Date ? now.getTime() : new Date(now).getTime();
  if (!Number.isFinite(value)) return MINUTE_MS;

  const elapsedInMinute = ((value % MINUTE_MS) + MINUTE_MS) % MINUTE_MS;

  return elapsedInMinute === 0 ? MINUTE_MS : MINUTE_MS - elapsedInMinute;
}

export function subscribeToHomeSolarClock(
  onTick,
  {
    documentRef = typeof document === "undefined" ? null : document,
    now = () => new Date(),
    timerApi = globalThis,
  } = {},
) {
  let timeoutId;
  let isDisposed = false;

  const scheduleNextTick = () => {
    const currentTime = now();
    timeoutId = timerApi.setTimeout(() => {
      if (isDisposed) return;
      onTick(now());
      scheduleNextTick();
    }, getMillisecondsUntilNextMinute(currentTime));
  };

  const handleVisibilityChange = () => {
    timerApi.clearTimeout(timeoutId);
    if (isDisposed) return;
    onTick(now());
    scheduleNextTick();
  };

  scheduleNextTick();
  documentRef?.addEventListener("visibilitychange", handleVisibilityChange);

  return () => {
    isDisposed = true;
    timerApi.clearTimeout(timeoutId);
    documentRef?.removeEventListener("visibilitychange", handleVisibilityChange);
  };
}

export function useHomeSolarState(solarContext = {}, { fallbackIsNight = false, now } = {}) {
  const hasFixedNow = now !== undefined && now !== null;
  const [clock, setClock] = useState(() => new Date());

  useEffect(() => {
    if (hasFixedNow) return undefined;

    return subscribeToHomeSolarClock(setClock);
  }, [hasFixedNow]);

  return getHomeSolarState({
    ...solarContext,
    fallbackIsNight,
    now: hasFixedNow ? now : clock,
  });
}
