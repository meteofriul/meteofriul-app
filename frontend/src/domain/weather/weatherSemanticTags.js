import { normalizeWeatherData } from "./normalizedWeather";

export function normalizeWeatherText(value = "") {
  return String(value || "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase();
}

function hasPositiveAmount(value) {
  const number = Number(value);
  return Number.isFinite(number) && number > 0;
}

export function getWeatherSemanticTagContext(weather = {}) {
  const normalized = normalizeWeatherData(weather || {});
  const semantic = normalized.semantic;
  const hasCode = normalized.code !== null && normalized.code !== undefined;
  const hasPrimaryMetrics = [
    normalized.precipitation,
    normalized.rain,
    normalized.showers,
    normalized.snowfall,
  ].some(hasPositiveAmount);
  const isOnlyFallbackOvercast =
    semantic?.source === "current_weather_code" &&
    semantic?.key === "overcast" &&
    !hasCode &&
    !hasPrimaryMetrics;

  return {
    normalized,
    semantic,
    hasPrimarySemantic: Boolean(semantic && !isOnlyFallbackOvercast),
    hasWindOverlay: Boolean(semantic?.overlays?.wind),
  };
}
