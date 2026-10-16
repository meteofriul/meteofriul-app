import {
  getLocalizedWeatherCondition,
  getWeatherIconProps,
  isIconLocalPilotWeather,
  normalizeWeatherData,
  readPopPercent,
  readWeatherNumber,
} from "../../domain/weather/normalizedWeather";
import { buildLocalWeatherPilotMetadata } from "../../domain/weather/localWeatherPilotMetadata";
import { getLocationDisplayName } from "../../domain/geo/locationDisplayName";
import { getDateTimeFormatter } from "../../domain/dateTimeFormatters.js";
import { getHomeViewModelCopy } from "../home/homeViewModel";

const COPY = {
  it: {
    change: "Cambia",
    currentDataLabel: "Dati meteo locali",
    evolution: "Prossime 12 ore",
    evolutionExtended: "Prossime 48 ore",
    evolutionPartial: "Evoluzione oraria",
    today: "Oggi",
    gusts: "raffiche",
    degrees: "gradi",
    humidity: "Umidità",
    localWeather: "A",
    modelUpdated: "Aggiornato alle",
    observedAt: "ore",
    pollen: "Pollini",
    pollenAvailable: "Dati disponibili",
    pollenHigh: "Livello alto",
    pollenLow: "Livello basso",
    pollenMedium: "Livello medio",
    pollenUnavailable: "Dati pollinici non disponibili",
    pollenVeryHigh: "Livello molto alto",
    precipitation: "Pioggia",
    pressure: "Pressione",
    sourceCams: "Pollini CAMS",
    sourceModel: "Evoluzione Open-Meteo",
    sourceIcon: "ICON-2I · snapshot locale",
    sourceCamsPilot: "CAMS · previsione sperimentale dei pollini",
    precipitationPilot: "Precipitazioni",
    pollenPilot: "Previsione sperimentale · nessun livello sanitario",
    sourceObserved: "Osservazioni ARPA FVG",
    stale: "Ultimo dato disponibile",
    station: "Stazione OSMER",
    strongestPollen: "Prevalenti",
    wind: "Vento",
  },
  fur: {
    change: "Cambie",
    currentDataLabel: "Dâts meteo locâi",
    degrees: "grâts",
    evolution: "Prossimis 12 oris",
    evolutionExtended: "Prossimis 48 oris",
    evolutionPartial: "Evoluzion orarie",
    today: "Vuê",
    gusts: "rafichis",
    humidity: "Umiditât",
    localWeather: "A",
    modelUpdated: "Inzornât aes",
    observedAt: "aes",
    pollen: "Polins",
    pollenAvailable: "Dâts disponibii",
    pollenHigh: "Nivel alt",
    pollenLow: "Nivel bas",
    pollenMedium: "Nivel medi",
    pollenUnavailable: "Dâts sui polins no disponibii",
    pollenVeryHigh: "Nivel une vore alt",
    precipitation: "Pluie",
    pressure: "Pression",
    sourceCams: "Polins CAMS",
    sourceModel: "Evoluzion Open-Meteo",
    sourceIcon: "ICON-2I · snapshot locâl",
    sourceCamsPilot: "CAMS · prevision sperimentâl dai polins",
    precipitationPilot: "Precipitazions",
    pollenPilot: "Prevision sperimentâl · nissun nivel sanitari",
    sourceObserved: "Osservazions ARPA FVG",
    stale: "Ultin dât disponibil",
    station: "Stazion OSMER",
    strongestPollen: "Principâi",
    wind: "Vint",
  },
};

const POLLEN_LABELS = {
  ambrosia: { it: "Ambrosia", fur: "Ambrosie" },
  artemisia: { it: "Artemisia", fur: "Artemisie" },
  betulla: { it: "Betulla", fur: "Betule" },
  graminacee: { it: "Graminacee", fur: "Graminaceis" },
  olivo: { it: "Olivo", fur: "Ulîf" },
  ontano: { it: "Ontano", fur: "Ontan" },
};

function getLanguageKey(language) {
  return language === "fur" ? "fur" : "it";
}

function roundValue(value, digits = 0) {
  const number = readWeatherNumber(value);
  if (number === null) return null;

  const factor = 10 ** digits;
  return Math.round(number * factor) / factor;
}

function formatMetric(value, unit, digits = 0, decimalSeparator = ".") {
  const rounded = roundValue(value, digits);

  if (rounded === null) return null;

  const formatted = digits > 0 ? rounded.toFixed(digits) : String(rounded);
  return `${formatted.replace(".", decimalSeparator)}${unit}`;
}

function formatClock(value, timeZone) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";

  return getDateTimeFormatter("it-IT", {
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
    ...(timeZone ? { timeZone } : {}),
  }).format(date);
}

function degreesToCompass(value) {
  if (typeof value === "string" && value.trim() && !Number.isFinite(Number(value))) {
    return value.trim().toUpperCase();
  }

  const degrees = readWeatherNumber(value);
  if (degrees === null) return "";

  const labels = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE", "S", "SSO", "SO", "OSO", "O", "ONO", "NO", "NNO"];
  const normalized = ((degrees % 360) + 360) % 360;

  return labels[Math.round(normalized / 22.5) % labels.length];
}

function readStationValue(station, key) {
  const value = station?.[key];
  return value === null || value === undefined || value === "" ? null : value;
}

function hasObservedValue(station, key) {
  return readStationValue(station, key) !== null;
}

function buildMetrics(current, copy) {
  const normalized = current?.type ? current : normalizeWeatherData(current || {});
  const pilot = isIconLocalPilotWeather(normalized);
  const modelSource = pilot ? "icon2i" : "open-meteo";
  const station = pilot ? {} : normalized.station || current?.station || {};
  const humidity = readStationValue(station, "humidity") ?? normalized.humidity;
  const pressure = readStationValue(station, "pressure") ?? normalized.pressure;
  const windSpeed = readStationValue(station, "wind_speed") ?? normalized.windSpeed;
  const windGusts = readStationValue(station, "wind_gusts") ?? normalized.windGusts;
  const windDirection = readStationValue(station, "wind_direction") ?? normalized.windDirection;
  const precipitation = readStationValue(station, "precipitation") ?? normalized.precipitationAmount;
  const precipitationAmount = readWeatherNumber(precipitation);
  const directionLabel = degreesToCompass(windDirection);
  const gustLabel = formatMetric(windGusts, " km/h");

  return [
    {
      id: "humidity",
      label: copy.humidity,
      source: hasObservedValue(station, "humidity") ? "osmer" : modelSource,
      value: formatMetric(humidity, "%"),
    },
    {
      id: "pressure",
      label: copy.pressure,
      source: hasObservedValue(station, "pressure") ? "osmer" : modelSource,
      value: formatMetric(pressure, " hPa"),
    },
    {
      detail: [directionLabel, gustLabel ? `${copy.gusts} ${gustLabel}` : ""].filter(Boolean).join(" · "),
      id: "wind",
      label: copy.wind,
      source: hasObservedValue(station, "wind_speed") ? "osmer" : modelSource,
      value: formatMetric(windSpeed, " km/h"),
    },
    {
      id: "precipitation",
      label: pilot ? copy.precipitationPilot : copy.precipitation,
      source: hasObservedValue(station, "precipitation") ? "osmer" : modelSource,
      tone: precipitationAmount > 0 ? "active" : "inactive",
      value: formatMetric(precipitation, " mm", precipitation > 0 && precipitation < 1 ? 1 : 0),
    },
  ].filter((metric) => metric.value !== null);
}

function parseClockMinutes(value) {
  const match = String(value || "").match(/T(\d{2}):(\d{2})/);
  if (!match) return null;

  return Number(match[1]) * 60 + Number(match[2]);
}

function isHourlySlotNight(slot, sunrise, sunset) {
  const isNight = isIconLocalPilotWeather(slot)
    ? readWeatherNumber(slot?.is_day) === 0 : Number(slot?.is_day) === 0;
  if (slot?.isNight === true || isNight) return true;
  if (Number(slot?.is_day) === 1) return false;

  const slotMinutes = parseClockMinutes(slot?.time);
  const sunriseMinutes = parseClockMinutes(sunrise);
  const sunsetMinutes = parseClockMinutes(sunset);

  if (slotMinutes === null || sunriseMinutes === null || sunsetMinutes === null) return false;

  return slotMinutes < sunriseMinutes || slotMinutes >= sunsetMinutes;
}

function selectHourlySlots(slots) {
  if (!Array.isArray(slots) || !slots.length) return [];
  if (slots.length <= 6) return slots;

  return slots.filter((_, index) => index % 2 === 0).slice(0, 6);
}

const HOUR_MS = 60 * 60 * 1000;
const FORECAST_TIME_ZONE = "Europe/Rome";

function selectExtendedHourlySlots(slots, now, { includeIncomplete = false, futureOnly = false } = {}) {
  if (!Array.isArray(slots)) return [];

  const ordered = slots
    .filter((slot) => Number.isFinite(new Date(slot?.time).getTime())
      && (includeIncomplete || readWeatherNumber(slot?.temperature) !== null))
    .sort((a, b) => new Date(a.time).getTime() - new Date(b.time).getTime());
  const nowMs = now === null || now === undefined ? NaN : new Date(now).getTime();
  const firstMs = Number.isFinite(nowMs) ? nowMs : new Date(ordered[0]?.time).getTime();
  // Italian time zones have whole-hour offsets, including both DST transitions.
  // ICON's current sample belongs to the hero. Keep up to 48 actual future
  // points, without losing the last one to a window starting an hour earlier.
  const startMs = futureOnly ? firstMs : Math.floor(firstMs / HOUR_MS) * HOUR_MS;
  const seen = new Set();

  return ordered.filter((slot) => {
    const timeMs = new Date(slot.time).getTime();
    if (timeMs < startMs || (!futureOnly && timeMs >= startMs + 48 * HOUR_MS) || seen.has(timeMs)) return false;
    seen.add(timeMs);
    return true;
  }).slice(0, 48);
}

function getHourlyDay(value, now, copy) {
  const date = new Date(value);
  const dateKeyFormatter = getDateTimeFormatter("en-CA", { timeZone: FORECAST_TIME_ZONE });
  const dateKey = dateKeyFormatter.format(date);
  const current = now === null || now === undefined ? null : new Date(now);
  const isToday = current && Number.isFinite(current.getTime())
    && dateKeyFormatter.format(current) === dateKey;
  const dateLabel = getDateTimeFormatter("it-IT", {
    day: "2-digit", month: "2-digit", timeZone: FORECAST_TIME_ZONE,
  }).format(date);

  return { dateKey, dayLabel: isToday ? copy.today : dateLabel, dateLabel };
}

function getDeviceHourStartMs(now) {
  const current = now instanceof Date ? new Date(now.getTime()) : new Date(now);
  if (Number.isNaN(current.getTime())) return null;

  const hourMs = 60 * 60 * 1000;
  const offsetMs = current.getTimezoneOffset() * 60 * 1000;
  const localTimeMs = current.getTime() - offsetMs;

  return Math.floor(localTimeMs / hourMs) * hourMs + offsetMs;
}

export function filterHourlySlotsByDeviceHour(slots, { now } = {}) {
  if (!Array.isArray(slots) || now === undefined || now === null) return slots || [];

  const currentHourStartMs = getDeviceHourStartMs(now);
  if (currentHourStartMs === null) return slots;

  return slots.filter((slot) => {
    const slotTimeMs = new Date(slot?.time).getTime();
    return Number.isFinite(slotTimeMs) && slotTimeMs >= currentHourStartMs;
  });
}

function getTemperatureTone(value) {
  const temperature = readWeatherNumber(value);
  if (temperature === null) return "mild";
  if (temperature >= 30) return "hot";
  if (temperature >= 20) return "warm";
  if (temperature <= 5) return "cold";
  if (temperature <= 14) return "cool";

  return "mild";
}

function buildHourly(current, copy, now, hourlyHours, language, includeIncomplete = false) {
  const normalized = current?.type ? current : normalizeWeatherData(current || {});
  const extended = hourlyHours === 48;
  const available = normalized.hourlyForecast?.length ? normalized.hourlyForecast : normalized.hourlyNext12h;
  const selected = extended
    ? selectExtendedHourlySlots(available, now, { includeIncomplete, futureOnly: isIconLocalPilotWeather(normalized) })
    : selectHourlySlots(filterHourlySlotsByDeviceHour(available, { now }));
  const weatherCopy = getHomeViewModelCopy(language).weatherConditions;

  return selected.map((slot) => {
    const slotWithTime = {
      ...slot,
      isNight: isHourlySlotNight(slot, normalized.sunrise, normalized.sunset),
    };
    const precipitationProbability = readPopPercent(slot);
    const precipitation = readWeatherNumber(slot.precipitation);
    const precipitationAmount = formatMetric(
      precipitation,
      " mm",
      precipitation !== null && precipitation > 0 && precipitation < 1 ? 1 : 0,
      ",",
    );
    const day = extended ? getHourlyDay(slot.time, now, copy) : null;
    const time = formatClock(slot.time, extended ? FORECAST_TIME_ZONE : undefined);
    const hasIntervalValue = precipitation !== null
      || readWeatherNumber(slot.wind_gusts ?? slot.windGusts) !== null;
    const canDerivePilotInterval = isIconLocalPilotWeather(slotWithTime)
      && hasIntervalValue
      && Number.isFinite(new Date(slot.time).getTime());
    const intervalEndValue = slot.interval_end || (canDerivePilotInterval ? slot.time : null);
    const intervalStartValue = slot.interval_start || (canDerivePilotInterval
      ? new Date(new Date(slot.time).getTime() - HOUR_MS).toISOString()
      : null);
    const intervalStart = intervalStartValue
      ? formatClock(intervalStartValue, FORECAST_TIME_ZONE)
      : "";
    const intervalEnd = intervalEndValue
      ? formatClock(intervalEndValue, FORECAST_TIME_ZONE)
      : "";
    const intervalLabel = intervalStart && intervalEnd ? `${intervalStart}–${intervalEnd}` : "";
    const windDirection = degreesToCompass(slot.wind_direction ?? slot.windDirection);
    const conditionLabel = getLocalizedWeatherCondition(slotWithTime, weatherCopy);
    const retainedFields = Array.isArray(slot.retained_fields)
      ? [...new Set(slot.retained_fields.filter((field) => typeof field === "string"))]
      : [];
    const values = {
      apparentTemperature: readWeatherNumber(slot.feels_like ?? slot.feelsLike),
      cloudCover: readWeatherNumber(slot.cloud_cover ?? slot.cloudCover),
      humidity: readWeatherNumber(slot.humidity),
      precipitation,
      pressure: readWeatherNumber(slot.pressure),
      temperature: readWeatherNumber(slot.temperature),
      windDirection: readWeatherNumber(slot.wind_direction ?? slot.windDirection),
      windGusts: readWeatherNumber(slot.wind_gusts ?? slot.windGusts),
      windSpeed: readWeatherNumber(slot.wind_speed ?? slot.windSpeed),
    };

    return {
      ariaLabel: [
        day?.dateLabel,
        time,
        conditionLabel,
        formatMetric(slot.temperature, ` ${copy.degrees}`),
        precipitationProbability === null ? "" : `${precipitationProbability}%`,
        precipitationAmount ? `${copy.precipitationPilot} ${precipitationAmount}` : "",
      ].filter(Boolean).join(", "),
      conditionLabel,
      details: {
        apparentTemperature: formatMetric(slot.feels_like ?? slot.feelsLike, "°"),
        cloudCover: formatMetric(slot.cloud_cover ?? slot.cloudCover, "%"),
        humidity: formatMetric(slot.humidity, "%"),
        intervalLabel,
        precipitation: precipitationAmount,
        pressure: formatMetric(slot.pressure, " hPa"),
        windDirection,
        windGusts: formatMetric(slot.wind_gusts ?? slot.windGusts, " km/h"),
        windSpeed: formatMetric(slot.wind_speed ?? slot.windSpeed, " km/h"),
      },
      intervalEnd: intervalEndValue || null,
      intervalStart: intervalStartValue || null,
      ...(day ? { dateKey: day.dateKey, dayLabel: day.dayLabel, timestamp: slot.time } : {}),
      icon: getWeatherIconProps(slotWithTime),
      precipitationAmount,
      precipitationProbability,
      retainedFields,
      temperature: formatMetric(slot.temperature, "°"),
      temperatureTone: getTemperatureTone(slot.temperature),
      time,
      values,
    };
  }).filter((slot) => slot.time && (includeIncomplete || slot.temperature));
}

function getPollenLevelLabel(level, copy) {
  const normalized = String(level || "").trim().toLowerCase();

  if (normalized.includes("molto") || normalized.includes("une vore")) return copy.pollenVeryHigh;
  if (normalized.includes("alt")) return copy.pollenHigh;
  if (normalized.includes("medi")) return copy.pollenMedium;
  if (normalized.includes("bass") || normalized.includes("low")) return copy.pollenLow;

  return copy.pollenAvailable;
}

function getPollenLevelTone(level) {
  const normalized = String(level || "").trim().toLowerCase();

  if (normalized.includes("molto") || normalized.includes("une vore") || normalized.includes("very high")) {
    return "very-high";
  }
  if (normalized.includes("alt") || normalized.includes("high")) return "high";
  if (normalized.includes("medi")) return "medium";
  if (normalized.includes("bass") || normalized.includes("low")) return "low";

  return "available";
}

function buildPollen(current, language, copy) {
  const pollenData = current?.pollen_data || current?.pollenData;
  if (isIconLocalPilotWeather(current)) {
    const values = Object.entries(POLLEN_LABELS).map(([id, labels]) => {
      const number = readWeatherNumber(pollenData?.values?.[id]);
      const value = number !== null && number >= 0 ? number : null;
      return {
        id,
        label: labels[getLanguageKey(language)],
        value,
        displayValue: value === null ? "—" : value > 0 && value < 0.01
          ? "<0,01" : new Intl.NumberFormat("it-IT", { maximumFractionDigits: 2 }).format(value),
      };
    });
    const available = pollenData?.status === "experimental_model_snapshot"
      && values.some((entry) => entry.value !== null);
    return {
      available,
      detail: "",
      label: copy.pollen,
      level: available ? copy.pollenPilot : copy.pollenUnavailable,
      status: pollenData?.status || (available ? "available" : "unavailable"),
      strongestLabel: copy.strongestPollen,
      tone: available ? "available" : "unavailable",
      values: available ? values : [],
      units: "grani/m³",
      runAt: pollenData?.run_utc || null,
      validAt: pollenData?.valid_at_utc || null,
      source: "cams_european_ensemble",
    };
  }
  if (!pollenData || typeof pollenData !== "object") {
    return {
      available: false,
      detail: "",
      label: copy.pollen,
      level: copy.pollenUnavailable,
      status: "unavailable",
      strongestLabel: copy.strongestPollen,
      tone: "unavailable",
    };
  }

  const languageKey = getLanguageKey(language);
  const entries = Object.entries(pollenData.values || {})
    .map(([id, value]) => ({
      id,
      label: POLLEN_LABELS[id]?.[languageKey] || id,
      value: readWeatherNumber(value),
    }))
    .filter((entry) => entry.value !== null && entry.value > 0)
    .sort((first, second) => second.value - first.value)
    .slice(0, 2);

  if (!String(pollenData.level || "").trim() && !entries.length) {
    return {
      available: false,
      detail: "",
      label: copy.pollen,
      level: copy.pollenUnavailable,
      status: "unavailable",
      strongestLabel: copy.strongestPollen,
      tone: "unavailable",
    };
  }

  return {
    available: true,
    detail: entries.map((entry) => entry.label).join(" · "),
    label: copy.pollen,
    level: getPollenLevelLabel(pollenData.level, copy),
    status: "available",
    strongestLabel: copy.strongestPollen,
    tone: getPollenLevelTone(pollenData.level),
  };
}

function buildObservationLabel(state, current, copy, languageKey, hasObservedMetrics) {
  if (isIconLocalPilotWeather(current)) {
    const validAt = current?.data_quality?.valid_at_utc;
    const date = validAt ? new Date(validAt) : null;
    return date && Number.isFinite(date.getTime())
      ? `ICON-2I · ${new Intl.DateTimeFormat("it-IT", {
        dateStyle: "short", timeStyle: "short", timeZone: "Europe/Rome",
      }).format(date)} · Europe/Rome`
      : copy.sourceIcon;
  }
  const station = current?.station || {};
  const rawStationName = String(station.station || current?.source?.station || "").trim();
  const stationName = getLocationDisplayName(rawStationName, languageKey);
  const stationTime = String(station.time || "").trim();
  const updatedTime = formatClock(state?.updatedAt);
  const prefix = state?.isStale ? `${copy.stale} · ` : "";

  if (hasObservedMetrics && stationName) {
    return `${prefix}${copy.station} ${stationName}${stationTime ? ` · ${copy.observedAt} ${stationTime}` : ""}`;
  }

  return updatedTime ? `${prefix}${copy.modelUpdated} ${updatedTime}` : prefix.replace(/ · $/, "");
}

export function buildBulletinLocalViewModel(state, {
  language = "it", location = null, now = null, hourlyHours = 12, includeIncompleteHourly = false,
} = {}) {
  if (!state?.current || !state?.rawCurrent) return null;

  const languageKey = getLanguageKey(language);
  const copy = COPY[languageKey];
  const rawCurrent = state.rawCurrent;
  const pilot = isIconLocalPilotWeather(rawCurrent);
  const modelSource = pilot ? copy.sourceIcon : copy.sourceModel;
  const camsSource = pilot ? copy.sourceCamsPilot : copy.sourceCams;
  const metrics = buildMetrics(rawCurrent, copy);
  const hourly = buildHourly(
    rawCurrent,
    copy,
    now,
    hourlyHours,
    languageKey,
    includeIncompleteHourly,
  );
  const pollen = buildPollen(rawCurrent, languageKey, copy);

  if (!metrics.length && !hourly.length && !pollen) return null;

  const rawCity = String(state.city || rawCurrent.city || location?.city || "").trim();
  const city = getLocationDisplayName(location, languageKey)
    || getLocationDisplayName(rawCity, languageKey);
  const sources = [];
  const detailsSources = [];

  if (metrics.some((metric) => metric.source === "osmer")) {
    sources.push(copy.sourceObserved);
    detailsSources.push(copy.sourceObserved);
  }
  if (hourly.length || metrics.some((metric) => metric.source === "open-meteo" || metric.source === "icon2i")) sources.push(modelSource);
  if (metrics.some((metric) => metric.source === "open-meteo" || metric.source === "icon2i")) detailsSources.push(modelSource);
  if (pollen.available) {
    sources.push(camsSource);
    detailsSources.push(camsSource);
  }

  return {
    changeLabel: copy.change,
    city,
    currentDataLabel: copy.currentDataLabel,
    detailsSourceLabel: detailsSources.join(" · "),
    evolutionLabel: hourlyHours === 48
      ? (hourly.length === 48 ? copy.evolutionExtended : copy.evolutionPartial)
      : copy.evolution,
    hourly,
    hourlySourceLabel: hourly.length ? modelSource : "",
    localPilot: buildLocalWeatherPilotMetadata(rawCurrent),
    metrics,
    observationLabel: buildObservationLabel(
      state,
      rawCurrent,
      copy,
      languageKey,
      metrics.some((metric) => metric.source === "osmer"),
    ),
    pollen,
    sourceLabel: sources.join(" · "),
    title: `${copy.localWeather} ${city}`.trim(),
  };
}
