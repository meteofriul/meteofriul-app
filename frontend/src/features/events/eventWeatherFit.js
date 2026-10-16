import { normalizeWeatherData } from "../../domain/weather/normalizedWeather";
import {
  getConditionContext,
  getWeatherGroup,
} from "../../domain/weather/weatherAdviceContext";

const HIGH_SENSITIVITY_CATEGORIES = new Set(["sagra", "mercato", "sport", "natura"]);
const LOW_SENSITIVITY_CATEGORIES = new Set(["cultura", "convegni"]);

const INDOOR_PATTERN = /\b(mostra|museo|teatro|cinema|biblioteca|laboratorio|convegno|incontro|auditorium|sala)\b/;
const OUTDOOR_PATTERN = /\b(sagra|festa|mercat|fier|sport|natura|escursion|cammin|parco|piazza|nautic|porto)\b/;

const FAMILY_TO_GROUP = {
  clear: "sun",
  cloud: "cloud",
  fog: "fog",
  hail: "storm",
  mixed: "rain",
  rain: "rain",
  snow: "snow",
  storm: "storm",
};

function normalizeText(value) {
  return String(value || "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase();
}

function getRawEvent(event) {
  return event?.raw && typeof event.raw === "object" ? event.raw : event || {};
}

function getEventField(event, key) {
  const raw = getRawEvent(event);
  return event?.[key] ?? raw?.[key] ?? "";
}

function getEventText(event) {
  return normalizeText([
    getEventField(event, "title"),
    getEventField(event, "name"),
    getEventField(event, "category"),
    getEventField(event, "categoryLabel"),
    getEventField(event, "category_label"),
    getEventField(event, "place"),
    getEventField(event, "event_city"),
    getEventField(event, "provider_place"),
  ].join(" "));
}

function getExplicitSensitivity(event) {
  const sensitivity = normalizeText(getEventField(event, "weather_sensitivity"));

  return ["low", "medium", "high"].includes(sensitivity) ? sensitivity : null;
}

export function isLikelyIndoorEvent(event) {
  const category = normalizeText(getEventField(event, "category"));
  const text = getEventText(event);

  return LOW_SENSITIVITY_CATEGORIES.has(category) || INDOOR_PATTERN.test(text);
}

export function getEventWeatherSensitivity(event) {
  const explicit = getExplicitSensitivity(event);
  if (explicit) return explicit;

  const category = normalizeText(getEventField(event, "category"));
  const text = getEventText(event);

  if (HIGH_SENSITIVITY_CATEGORIES.has(category) || OUTDOOR_PATTERN.test(text)) return "high";
  if (LOW_SENSITIVITY_CATEGORIES.has(category) || isLikelyIndoorEvent(event)) return "low";

  return "medium";
}

function hasWeatherEvidence(weatherData) {
  if (!weatherData || typeof weatherData !== "object") return false;

  return Boolean(
    String(weatherData.condition || weatherData.weather || weatherData.description || "").trim() ||
      weatherData.weathercode !== undefined ||
      weatherData.weather_code !== undefined ||
      weatherData.temperature !== undefined ||
      weatherData.temp !== undefined ||
      weatherData.current_weather?.weathercode !== undefined ||
      weatherData.current?.weather_code !== undefined,
  );
}

function getWeatherFitGroup(normalized) {
  const family = normalized?.semantic?.family;
  if (FAMILY_TO_GROUP[family]) return FAMILY_TO_GROUP[family];

  return getWeatherGroup(normalized?.semantic?.meteoconType || normalized?.type);
}

function buildFit({ level, reasonCode, score, event, context, normalized }) {
  return {
    level,
    reasonCode,
    score,
    sensitivity: getEventWeatherSensitivity(event),
    indoor: isLikelyIndoorEvent(event),
    weatherGroup: context?.adviceGroup || getWeatherFitGroup(normalized),
  };
}

export function getEventWeatherFit(event, weatherData) {
  if (!event || !hasWeatherEvidence(weatherData)) {
    return {
      indoor: Boolean(event && isLikelyIndoorEvent(event)),
      level: "neutral",
      reasonCode: "no_weather",
      score: 50,
      sensitivity: event ? getEventWeatherSensitivity(event) : "medium",
      weatherGroup: "unknown",
    };
  }

  const normalized = normalizeWeatherData(weatherData);
  const baseWeatherGroup = getWeatherFitGroup(normalized);
  const context = getConditionContext({
    ...(normalized.raw || {}),
    ...normalized,
    is_bora: normalized.isBora,
    wind_direction: normalized.windDirection,
    wind_gusts: normalized.windGusts,
    wind_speed: normalized.windSpeed,
  }, baseWeatherGroup);
  const sensitivity = getEventWeatherSensitivity(event);
  const indoor = isLikelyIndoorEvent(event);
  const badWeather = ["rain", "storm", "snow", "wind", "fog"].includes(context.adviceGroup) ||
    context.heatCaution ||
    context.coldRisk;

  if (!badWeather) {
    return buildFit({
      context,
      event,
      level: "good",
      normalized,
      reasonCode: "fair_weather",
      score: sensitivity === "high" ? 88 : 78,
    });
  }

  if (indoor || sensitivity === "low") {
    return buildFit({
      context,
      event,
      level: "indoor",
      normalized,
      reasonCode: "protected_activity",
      score: 82,
    });
  }

  if (context.adviceGroup === "storm" || context.adviceGroup === "snow") {
    return buildFit({
      context,
      event,
      level: "risky",
      normalized,
      reasonCode: "severe_weather",
      score: sensitivity === "high" ? 34 : 50,
    });
  }

  if (context.adviceGroup === "wind") {
    return buildFit({
      context,
      event,
      level: "watch",
      normalized,
      reasonCode: "wind_exposure",
      score: sensitivity === "high" ? 52 : 62,
    });
  }

  if (context.heatCaution) {
    return buildFit({
      context,
      event,
      level: "watch",
      normalized,
      reasonCode: "heat_exposure",
      score: sensitivity === "high" ? 50 : 63,
    });
  }

  if (context.coldRisk) {
    return buildFit({
      context,
      event,
      level: "watch",
      normalized,
      reasonCode: "cold_exposure",
      score: sensitivity === "high" ? 54 : 64,
    });
  }

  return buildFit({
    context,
    event,
    level: "watch",
    normalized,
    reasonCode: sensitivity === "high" ? "sensitive_weather" : "weather_attention",
    score: sensitivity === "high" ? 56 : 66,
  });
}

export function getHomeWeatherFitScoreDelta(fit) {
  if (!fit || fit.level === "neutral") return 0;

  return Math.max(-35, Math.min(25, Math.round((Number(fit.score) - 60) * 0.8)));
}
