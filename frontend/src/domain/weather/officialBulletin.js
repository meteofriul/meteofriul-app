import { classifyOsmerStructuredSnapshot } from "./osmerStructuredContract";

function getForecast(payload = {}) {
  return payload?.forecast || payload || {};
}

function getOfficialForecasts(forecast = {}) {
  return [
    ...(Array.isArray(forecast?.official?.it?.forecasts) ? forecast.official.it.forecasts : []),
    ...(Array.isArray(forecast?.official?.fur?.forecasts) ? forecast.official.fur.forecasts : []),
  ];
}

function getModelForecasts(forecast = {}) {
  if (Array.isArray(forecast?.forecast)) return forecast.forecast;
  if (Array.isArray(forecast?.daily)) return forecast.daily;
  if (Array.isArray(forecast?.days)) return forecast.days;
  return [];
}

function getStructuredSnapshot(forecast = {}) {
  return forecast?.osmer_structured || forecast?.osmerStructured || null;
}

function normalizeIsoDate(value) {
  const match = String(value || "").trim().match(/^(\d{4})-(\d{2})-(\d{2})/);
  return match ? `${match[1]}-${match[2]}-${match[3]}` : "";
}

function getNowDate(now = Date.now) {
  const value = typeof now === "function" ? now() : now;
  const date = value instanceof Date ? value : new Date(value);
  return Number.isFinite(date.getTime()) ? date : new Date();
}

export function getFvgCalendarDateKey(now = Date.now) {
  const parts = new Intl.DateTimeFormat("en-CA", {
    day: "2-digit",
    month: "2-digit",
    timeZone: "Europe/Rome",
    year: "numeric",
  }).formatToParts(getNowDate(now));
  const values = Object.fromEntries(parts.map((part) => [part.type, part.value]));

  return `${values.year}-${values.month}-${values.day}`;
}

export function hasOfficialBulletinText(payload = {}) {
  const forecast = getForecast(payload);
  const localizedText = getOfficialForecasts(forecast).some((item) => (
    String(item?.text || item?.official_text || "").trim()
  ));
  const attachedText = getModelForecasts(forecast).some((item) => (
    String(item?.official_text || "").trim()
  ));

  return localizedText || attachedText;
}

export function hasUsableOsmerStructuredMap(payload = {}) {
  const snapshot = getStructuredSnapshot(getForecast(payload));
  return classifyOsmerStructuredSnapshot(snapshot).canRenderNativeMap;
}

export function getOfficialBulletinDates(payload = {}) {
  const forecast = getForecast(payload);
  const dates = new Set();

  getOfficialForecasts(forecast).forEach((item) => {
    const date = normalizeIsoDate(item?.date || item?.valid_date);
    if (date && String(item?.text || item?.official_text || "").trim()) dates.add(date);
  });

  getModelForecasts(forecast).forEach((item) => {
    const date = normalizeIsoDate(item?.date || item?.valid_date);
    if (date && String(item?.official_text || "").trim()) dates.add(date);
  });

  const snapshot = getStructuredSnapshot(forecast);
  if (classifyOsmerStructuredSnapshot(snapshot).canRenderNativeMap) {
    (snapshot?.days || []).forEach((day) => {
      const date = normalizeIsoDate(day?.valid_date || day?.date);
      if (date) dates.add(date);
    });
  }

  return [...dates].sort();
}

export function hasCurrentOfficialBulletinDay(payload = {}, { now = Date.now } = {}) {
  const today = getFvgCalendarDateKey(now);
  return getOfficialBulletinDates(payload).some((date) => date >= today);
}

export function isUsableOfficialBulletin(payload = {}, { now = Date.now } = {}) {
  return Boolean(
    (hasOfficialBulletinText(payload) || hasUsableOsmerStructuredMap(payload)) &&
    hasCurrentOfficialBulletinDay(payload, { now }),
  );
}
