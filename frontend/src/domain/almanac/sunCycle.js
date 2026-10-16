import { getDateTimeFormatter } from "../dateTimeFormatters.js";

const DAY_MS = 24 * 60 * 60 * 1000;
const DEFAULT_TIME_ZONE = "Europe/Rome";
const OFFICIAL_ZENITH_DEGREES = 90.833;

function toRadians(degrees) {
  return (degrees * Math.PI) / 180;
}

function toDegrees(radians) {
  return (radians * 180) / Math.PI;
}

function normalizeDegrees(value) {
  return ((value % 360) + 360) % 360;
}

function normalizeHours(value) {
  return ((value % 24) + 24) % 24;
}

function getDayOfYear(date) {
  const utcStart = Date.UTC(date.getUTCFullYear(), 0, 1);
  const utcDay = Date.UTC(date.getUTCFullYear(), date.getUTCMonth(), date.getUTCDate());

  return Math.floor((utcDay - utcStart) / DAY_MS) + 1;
}

function getSolarPosition(date, latitude, longitude, isSunrise) {
  const dayOfYear = getDayOfYear(date);
  const longitudeHour = longitude / 15;
  const approximateTime = dayOfYear + ((isSunrise ? 6 : 18) - longitudeHour) / 24;
  const meanAnomaly = 0.9856 * approximateTime - 3.289;
  const trueLongitude = normalizeDegrees(
    meanAnomaly +
      1.916 * Math.sin(toRadians(meanAnomaly)) +
      0.02 * Math.sin(toRadians(2 * meanAnomaly)) +
      282.634
  );
  let rightAscension = toDegrees(Math.atan(0.91764 * Math.tan(toRadians(trueLongitude))));

  rightAscension = normalizeDegrees(rightAscension);
  rightAscension += Math.floor(trueLongitude / 90) * 90 - Math.floor(rightAscension / 90) * 90;
  rightAscension /= 15;

  const sinDeclination = 0.39782 * Math.sin(toRadians(trueLongitude));
  const cosDeclination = Math.cos(Math.asin(sinDeclination));
  const cosHourAngle =
    (Math.cos(toRadians(OFFICIAL_ZENITH_DEGREES)) - sinDeclination * Math.sin(toRadians(latitude))) /
    (cosDeclination * Math.cos(toRadians(latitude)));

  if (cosHourAngle > 1 || cosHourAngle < -1) return null;

  const hourAngle = (isSunrise ? 360 - toDegrees(Math.acos(cosHourAngle)) : toDegrees(Math.acos(cosHourAngle))) / 15;
  const localMeanTime = hourAngle + rightAscension - 0.06571 * approximateTime - 6.622;
  const utcHour = normalizeHours(localMeanTime - longitudeHour);
  const hours = Math.floor(utcHour);
  const minutes = Math.round((utcHour - hours) * 60);

  return new Date(Date.UTC(date.getUTCFullYear(), date.getUTCMonth(), date.getUTCDate(), hours, minutes));
}

function getSolarDeclination(date) {
  const dayOfYear = getDayOfYear(date);

  return 23.44 * Math.sin(toRadians((360 / 365) * (dayOfYear - 81)));
}

function formatTimeInZone(date, timeZone = DEFAULT_TIME_ZONE) {
  return getDateTimeFormatter("it-IT", {
    hour: "2-digit",
    minute: "2-digit",
    timeZone,
  }).format(date);
}

function formatDuration(minutes) {
  const hours = Math.floor(minutes / 60);
  const remainingMinutes = Math.round(minutes % 60);

  return `${hours}h ${String(remainingMinutes).padStart(2, "0")}m`;
}

export function getSunCycle({
  date = new Date(),
  latitude = 46.0711,
  longitude = 13.2346,
  now = new Date(),
  timeZone = DEFAULT_TIME_ZONE,
} = {}) {
  const value = date instanceof Date ? date : new Date(date);
  const sunrise = getSolarPosition(value, latitude, longitude, true);
  const sunset = getSolarPosition(value, latitude, longitude, false);
  const declination = getSolarDeclination(value);
  const maxAltitudeDegrees = Math.round(90 - Math.abs(latitude - declination));

  if (!sunrise || !sunset) {
    return {
      daylight: "",
      daylightMinutes: 0,
      daylightProgress: 0,
      maxAltitudeDegrees,
      sunrise: "",
      sunset: "",
    };
  }

  const daylightMinutes = Math.max(0, (sunset - sunrise) / 60000);
  const referenceNow = now instanceof Date ? now : new Date(now);
  const beforeDawn = Math.abs(referenceNow - value) < DAY_MS && referenceNow < sunrise;
  const nightStart = beforeDawn
    ? getSolarPosition(new Date(+value - DAY_MS), latitude, longitude, false) : sunset;
  const nightEnd = beforeDawn
    ? sunrise : getSolarPosition(new Date(+value + DAY_MS), latitude, longitude, true);
  const nightMinutes = nightStart && nightEnd ? (nightEnd - nightStart) / 60000 : null;
  const daylightProgress = Math.min(100, Math.max(0, ((referenceNow - sunrise) / (sunset - sunrise)) * 100));
  let cycle = null;
  if (Number.isFinite(+referenceNow) && Math.abs(referenceNow - value) < DAY_MS) {
    const isDay = referenceNow >= sunrise && referenceNow < sunset;
    const start = isDay ? sunrise : referenceNow < sunrise
      ? getSolarPosition(new Date(+value - DAY_MS), latitude, longitude, false) : sunset;
    const end = isDay ? sunset : referenceNow < sunrise
      ? sunrise : getSolarPosition(new Date(+value + DAY_MS), latitude, longitude, true);
    if (start && end && end > start && referenceNow >= start && referenceNow <= end) {
      cycle = { isDay, progress: Math.round(100 * (referenceNow - start) / (end - start)),
        start: formatTimeInZone(start, timeZone), end: formatTimeInZone(end, timeZone) };
    }
  }

  return {
    daylight: formatDuration(daylightMinutes),
    nightDuration: nightMinutes !== null ? formatDuration(nightMinutes) : "",
    daylightMinutes,
    cycle,
    daylightProgress: Math.round(daylightProgress),
    maxAltitudeDegrees,
    sunrise: formatTimeInZone(sunrise, timeZone),
    sunset: formatTimeInZone(sunset, timeZone),
  };
}
