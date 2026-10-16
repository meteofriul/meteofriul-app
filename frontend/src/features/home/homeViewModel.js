import {
  getLocalizedWeatherCondition,
  getWeatherIconProps,
  isIconLocalPilotWeather,
} from "../../domain/weather/normalizedWeather";
import { buildLocalWeatherPilotMetadata } from "../../domain/weather/localWeatherPilotMetadata";
import {
  buildOfficialAlertSummary,
} from "../../domain/alerts/officialAlerts";
import { isFvgLocation } from "../../domain/scope/productScope";
import { getLocationCacheKey } from "../../domain/geo/locationCacheKey";
import { getLocationDisplayName } from "../../domain/geo/locationDisplayName";
import { getTemperatureSeverity } from "../../domain/weather/temperatureSeverity";
import {
  formatTemperature,
  formatWindSpeed,
  getTemperatureUnitLabel,
  getWindUnitLabel,
} from "../../domain/weather/unitFormats";
import { getDailySummaryCopy } from "../../copy/dailySummaryCopy";
import { getEventsViewCopy, getDegradedEventsMessage } from "../../copy/eventsViewCopy";
import {
  getEventWeatherFit,
  getHomeWeatherFitScoreDelta,
} from "../events/eventWeatherFit";
import {
  buildEventRecord,
  getContextualEventsSummary,
  parseEventDateRange,
  rankEventsForLocation,
} from "../events/eventsViewModel";
import { getDiscoverCardAnchor } from "../discover/discoverCardAnchor";
import { buildHomeLocalMetricsViewModel } from "./homeLocalMetricsViewModel";

const WEATHER_CONDITION_LABELS = {
  it: {
    conditionSun: "Soleggiato",
    conditionMostlySunny: "Prevalentemente soleggiato",
    conditionPartlyCloudy: "Poco nuvoloso",
    conditionVariable: "Variabile",
    conditionCloudy: "Nuvoloso",
    conditionOvercast: "Coperto",
    conditionLowCloudFog: "Nubi basse",
    conditionFog: "Nebbia",
    conditionMist: "Foschia",
    conditionHaze: "Caligine",
    conditionLightRain: "Pioggia debole",
    conditionFreezingDrizzle: "Pioviggine gelata",
    conditionRain: "Pioggia",
    conditionHeavyRain: "Pioggia abbondante",
    conditionIntenseRain: "Pioggia intensa",
    conditionExtremeRain: "Pioggia molto intensa",
    conditionFreezingRain: "Pioggia gelata",
    conditionShowers: "Rovesci",
    conditionSnow: "Neve",
    conditionSleet: "Nevischio",
    conditionStorm: "Temporale",
    conditionStrongStorm: "Temporale forte",
    conditionStormHail: "Temporale con grandine",
    conditionHail: "Grandine",
    conditionClearNight: "Sereno",
    conditionMostlyClearNight: "Prevalentemente sereno",
    conditionPartlyCloudyNight: "Poco nuvoloso",
    conditionOvercastNight: "Coperto",
    conditionUnavailable: "Condizione non disponibile",
  },
  fur: {
    conditionSun: "Soreli",
    conditionMostlySunny: "Soreli prevalent",
    conditionPartlyCloudy: "Poc nul",
    conditionVariable: "Variabil",
    conditionCloudy: "Nul",
    conditionOvercast: "Cuviert",
    conditionLowCloudFog: "Nuls bas",
    conditionFog: "Nebie",
    conditionMist: "Foschie",
    conditionHaze: "Caligjin",
    conditionLightRain: "Pluie debile",
    conditionFreezingDrizzle: "Plovine glaçade",
    conditionRain: "Pluie",
    conditionHeavyRain: "Pluie abondante",
    conditionIntenseRain: "Pluie intense",
    conditionExtremeRain: "Pluie une vore intense",
    conditionFreezingRain: "Pluie glaçade",
    conditionShowers: "Rovas",
    conditionSnow: "Nef",
    conditionSleet: "Nef miscliçade",
    conditionStorm: "Temporâl",
    conditionStrongStorm: "Temporâl fuart",
    conditionStormHail: "Temporâl cun tampierie",
    conditionHail: "Tampierie",
    conditionClearNight: "Seren",
    conditionMostlyClearNight: "Prevalentement seren",
    conditionPartlyCloudyNight: "Poc nul",
    conditionOvercastNight: "Cuviert",
    conditionUnavailable: "Condizion no disponibile",
  },
};

const HOME_VIEW_MODEL_COPY = {
  it: {
    appSectionTitle: "Home",
    locationFallback: "Localita non impostata",
    weatherUnavailable: "Meteo non disponibile",
    nationalForecastPlanned: "Previsioni nazionali in preparazione",
    weatherTerritoryUnsupported: "Località fuori copertura",
    dataUnavailable: "Dato non disponibile",
    updatedNow: "Aggiornato ora",
    updatedFallback: "Aggiornamento in corso",
    weatherFresh: "Meteo aggiornato",
    weatherCache: "Dati salvati",
    weatherStale: "Dati non aggiornati",
    weatherError: "Meteo in aggiornamento",
    updatedOneMinuteAgo: "Aggiornato 1 minuto fa",
    updatedMinutesAgo: "Aggiornato {minutes} minuti fa",
    updatedOneHourAgo: "Aggiornato 1 ora fa",
    updatedHoursAgo: "Aggiornato {hours} ore fa",
    detailsTitle: "Oggi, in breve",
    feelsLike: "Percepita",
    wind: "Vento",
    humidity: "Umidita",
    precipitation: "Pioggia",
    visibility: "Visibilita",
    pressure: "Pressione",
    cloudCover: "Copertura",
    eventsTitle: "Eventi vicino a te",
    eventsNearbySuffix: "vicino a te",
    eventsFvgTitle: "Eventi dal Friuli Venezia Giulia",
    eventsFvgSuffix: "in FVG",
    eventsTagsLabel: "Dettagli evento",
    eventsActionLabel: "Eventi",
    eventsRefreshing: "Eventi in aggiornamento",
    eventsStale: "Mostro gli eventi salvati",
    eventsError: "Eventi non disponibili",
    eventsTodayCountOne: "evento oggi",
    eventsTodayCount: "eventi oggi",
    eventsNextCountOne: "evento nei prossimi 15 giorni",
    eventsNextCount: "eventi nei prossimi 15 giorni",
    alertsLabel: "Avvisi ufficiali",
    officialAlertSingleLabel: "Allerta ufficiale",
    officialAlertMultipleLabel: "allerte ufficiali",
    officialAlertSeverityLabels: {
      yellow: "Allerta gialla",
      orange: "Allerta arancione",
      red: "Allerta rossa",
    },
    officialAlertPhenomenonLabels: {
      cold: "Allerta freddo",
      fog: "Allerta nebbia",
      hail: "Allerta grandine",
      heat: "Allerta caldo",
      ice: "Allerta ghiaccio",
      rain: "Allerta pioggia",
      snow: "Allerta neve",
      storm: "Allerta temporali",
      wind: "Allerta vento",
    },
    bulletinTitle: "Sintesi",
    bulletinSource: "OSMER ARPA FVG",
    bulletinFallbackHeadline: "Bollettino in preparazione",
    bulletinFallbackBody: "Apri il bollettino per leggere il testo ufficiale quando disponibile.",
    bulletinActionLabel: "Bollettino",
    hourlyTitle: "Prossime 48 ore",
    hourlyPartialTitle: "Evoluzione oraria",
    hourlyScrollLabel: "Previsioni orarie: scorri per vedere le prossime ore",
    almanacTitle: "Almanacco",
    almanacEyebrow: "Oggi in Friuli",
    almanacCardTitle: "L'almanacco del giorno",
    almanacFallbackHeadline: "Il giorno, la luna, la tradizione",
    almanacFallbackBody: "Santi, luna, proverbi e lavori della terra per iniziare la giornata.",
    almanacMoonLabel: "Luna",
    almanacActionLabel: "Almanacco",
    changeLocationLabel: "Cambia",
  },
  fur: {
    appSectionTitle: "Home",
    locationFallback: "Localitat no impostade",
    weatherUnavailable: "Meteo no disponibil",
    nationalForecastPlanned: "Previsions nazionâls in preparazion",
    weatherTerritoryUnsupported: "Localitât fûr de cuvierture",
    dataUnavailable: "Dat no disponibil",
    updatedNow: "Inzorn\u00e2t cum\u00f2",
    updatedFallback: "Inzornament in cors",
    weatherFresh: "Dats inzornats",
    weatherCache: "Dats salvats",
    weatherStale: "Dats no inzornats",
    weatherError: "Meteo in inzornament",
    updatedOneMinuteAgo: "Inzorn\u00e2t 1 min\u00fbt inda\u00fbr",
    updatedMinutesAgo: "Inzorn\u00e2t {minutes} min\u00fbts inda\u00fbr",
    updatedOneHourAgo: "Inzorn\u00e2t 1 ore inda\u00fbr",
    updatedHoursAgo: "Inzorn\u00e2t {hours} oris inda\u00fbr",
    detailsTitle: "Vuê, in curt",
    feelsLike: "Percepide",
    wind: "Vint",
    humidity: "Umiditat",
    precipitation: "Pluie",
    visibility: "Visibilitat",
    pressure: "Pression",
    cloudCover: "Cuviert",
    eventsTitle: "Evenis dongje di te",
    eventsNearbySuffix: "dongje di te",
    eventsFvgTitle: "Evenis dal Friûl Vignesie Julie",
    eventsFvgSuffix: "in FVG",
    eventsTagsLabel: "Detais eveni",
    eventsActionLabel: "Evenis",
    eventsRefreshing: "Evenis in inzornament",
    eventsStale: "O mostri i evenis salvats",
    eventsError: "Evenis no disponibii",
    eventsTodayCountOne: "eveniment vuê",
    eventsTodayCount: "evenis vuê",
    eventsNextCountOne: "eveniment tai prossims 15 dîs",
    eventsNextCount: "evenis tai prossims 15 dîs",
    bulletinTitle: "Sintesi",
    bulletinSource: "OSMER ARPA FVG",
    bulletinFallbackHeadline: "Boletin in preparazion",
    bulletinFallbackBody: "Vier\u00e7 il boletin par lei il test ufici\u00e2l cuant che al e disponibil.",
    bulletinActionLabel: "Boletin",
    hourlyTitle: "Prossimis 48 oris",
    hourlyPartialTitle: "Evoluzion orarie",
    hourlyScrollLabel: "Previsions orariis: scor par viodi lis prossimis oris",
    almanacTitle: "Almanac",
    almanacEyebrow: "Vu\u00ea in Friul",
    almanacCardTitle: "L'almanac dal d\u00ec",
    almanacFallbackHeadline: "Il d\u00ec, la lune, la tradizion",
    almanacFallbackBody: "Sants, lune, proverbis e lav\u00f4rs de tiere par tac\u00e2 la zornade.",
    almanacMoonLabel: "Lune",
    almanacActionLabel: "Almanac",
    changeLocationLabel: "Cambie",
    alertsLabel: "Avîs uficiâi",
    officialAlertSingleLabel: "Alerte ufici\u00e2l",
    officialAlertMultipleLabel: "alertis ufici\u00e2ls",
  },
};

function getLanguageKey(language) {
  return language === "fur" ? "fur" : "it";
}

export function getHomeViewModelCopy(language) {
  const key = getLanguageKey(language);

  return {
    ...HOME_VIEW_MODEL_COPY[key],
    weatherConditions: WEATHER_CONDITION_LABELS[key],
  };
}

function hasDisplayValue(value) {
  return value !== null && value !== undefined && value !== "";
}

function joinValueUnit(value, unit) {
  if (!hasDisplayValue(value)) return null;

  return unit ? `${value} ${unit}` : String(value);
}

function joinCompactValueUnit(value, unit) {
  if (!hasDisplayValue(value)) return null;

  return unit ? `${value}${unit}` : String(value);
}

function formatPercent(value) {
  if (!Number.isFinite(Number(value))) return null;

  return `${Math.round(Number(value))}%`;
}

function formatVisibility(value) {
  if (!Number.isFinite(Number(value))) return null;

  const visibility = Number(value);
  return `${visibility >= 10 ? Math.round(visibility) : visibility.toFixed(1)} km`;
}

function formatPressure(value) {
  if (!Number.isFinite(Number(value))) return null;

  return `${Math.round(Number(value))} hPa`;
}

function buildDetail(id, label, value, rawValue) {
  if (!hasDisplayValue(value)) return null;

  return {
    id,
    label,
    value,
    rawValue,
  };
}

function formatWindSummary(current, unitSystem) {
  const speed = joinValueUnit(formatWindSpeed(current?.windSpeed, unitSystem), getWindUnitLabel(unitSystem));
  const direction = hasDisplayValue(current?.windDirection) ? String(current.windDirection).trim() : "";

  if (!speed) return null;

  return direction ? `${speed} ${direction}` : speed;
}

function getTextValue(value, fallback) {
  return hasDisplayValue(value) ? String(value) : fallback;
}

function formatHomeDateLabel(value) {
  const label = getTextValue(value, "").trim();
  return label ? `${label.charAt(0).toUpperCase()}${label.slice(1)}` : "";
}

function getTimestampMs(value) {
  if (!hasDisplayValue(value)) return null;

  const timestamp = Date.parse(value);
  return Number.isFinite(timestamp) ? timestamp : null;
}

function replaceToken(template, token, value) {
  return String(template).replace(`{${token}}`, String(value));
}

function getUpdatedLabel(weatherState, copy, { now = Date.now() } = {}) {
  const explicitMinutes = Number(weatherState.updatedAgoMinutes);
  const nowMs = getTimestampMs(now) ?? Number(now);
  const updatedAtMs = getTimestampMs(weatherState.updatedAt);
  const minutesAgo = Number.isFinite(explicitMinutes)
    ? Math.max(0, Math.round(explicitMinutes))
    : Number.isFinite(nowMs) && updatedAtMs !== null
      ? Math.max(0, Math.round((nowMs - updatedAtMs) / 60000))
      : null;

  if (minutesAgo === null) return copy.updatedFallback;
  if (minutesAgo < 1) return copy.updatedNow;
  if (minutesAgo === 1) return copy.updatedOneMinuteAgo;
  if (minutesAgo < 60) return replaceToken(copy.updatedMinutesAgo, "minutes", minutesAgo);

  const hoursAgo = Math.round(minutesAgo / 60);
  if (hoursAgo <= 1) return copy.updatedOneHourAgo;

  return replaceToken(copy.updatedHoursAgo, "hours", hoursAgo);
}

const HOME_WEATHER_BASE_VARIANTS = new Set(["clear", "partly", "cloud", "rain", "storm", "snow", "fog", "night"]);
const HOME_WEATHER_VARIANTS = new Set([
  ...HOME_WEATHER_BASE_VARIANTS,
  "cloud-night",
  "rain-night",
  "snow-night",
  "storm-night",
]);

const HOME_WEATHER_VARIANT_BY_ICON_TYPE = {
  ClearNight: "clear",
  Cloud: "cloud",
  Cloudy: "cloud",
  ExtremeRain: "rain",
  Fog: "fog",
  Hail: "storm",
  Haze: "fog",
  HeavyRain: "rain",
  LightRain: "rain",
  LowCloudFog: "fog",
  Mist: "fog",
  MostlyClearNight: "clear",
  MostlySunny: "partly",
  Overcast: "cloud",
  OvercastNight: "cloud",
  PartlyCloudy: "partly",
  PartlyCloudyNight: "partly",
  Rain: "rain",
  Showers: "rain",
  Sleet: "rain",
  Snow: "snow",
  Storm: "storm",
  StormHail: "storm",
  StrongStorm: "storm",
  Sun: "clear",
};

const HOME_WEATHER_NIGHT_VARIANT_BY_BASE = {
  cloud: "cloud-night",
  partly: "cloud-night",
  rain: "rain-night",
  snow: "snow-night",
  storm: "storm-night",
};

function getHomeWeatherBaseVariant(current, icon) {
  const semanticVariant = current?.semantic?.sceneVariant;

  if (HOME_WEATHER_VARIANTS.has(semanticVariant)) return semanticVariant;
  if (HOME_WEATHER_BASE_VARIANTS.has(icon?.sceneVariant)) return icon.sceneVariant;
  if (HOME_WEATHER_BASE_VARIANTS.has(icon?.semanticFamily)) return icon.semanticFamily;

  return HOME_WEATHER_VARIANT_BY_ICON_TYPE[icon?.type] || "cloud";
}

function getHomeWeatherVariant(current, icon) {
  const baseVariant = getHomeWeatherBaseVariant(current, icon);

  if (HOME_WEATHER_VARIANTS.has(baseVariant) && !HOME_WEATHER_BASE_VARIANTS.has(baseVariant)) {
    return baseVariant;
  }

  if (icon?.night) return HOME_WEATHER_NIGHT_VARIANT_BY_BASE[baseVariant] || "night";

  return baseVariant;
}

export function buildHomeWeatherViewModel(
  weatherState = {},
  { language = "it", location, now, unitSystem = "metric" } = {},
) {
  const copy = getHomeViewModelCopy(language);
  const current = weatherState.current || null;
  const temperatureValue = hasDisplayValue(current?.temperature)
    ? formatTemperature(current.temperature, unitSystem)
    : null;
  const temperatureUnit = getTemperatureUnitLabel(unitSystem);
  const icon = current ? getWeatherIconProps(current) : null;
  const conditionLabel = current
    ? getLocalizedWeatherCondition(current, copy.weatherConditions)
    : weatherState.unavailableReason === "national_icon2i_planned"
      ? copy.nationalForecastPlanned
      : weatherState.unavailableReason === "weather_territory_unsupported"
        ? copy.weatherTerritoryUnsupported
        : copy.weatherUnavailable;
  const statusLabel =
    weatherState.status === "stale"
      ? copy.weatherStale
      : weatherState.status === "cache"
        ? copy.weatherFresh
        : weatherState.error
          ? copy.weatherError
          : copy.weatherFresh;
  const shouldShowStatus = current?.dataQuality?.status === "stale";
  const updatedLabel = shouldShowStatus
    ? copy.weatherStale
    : getUpdatedLabel(weatherState, copy, { now });
  const alertSummary = buildOfficialAlertSummary(weatherState.officialAlerts, copy, { now });
  const alertCount = alertSummary?.count || 0;
  const details = current
    ? [
        buildDetail(
          "feels-like",
          copy.feelsLike,
          hasDisplayValue(current.feelsLike)
            ? joinCompactValueUnit(formatTemperature(current.feelsLike, unitSystem), temperatureUnit)
            : null,
          current.feelsLike,
        ),
        buildDetail(
          "wind",
          copy.wind,
          formatWindSummary(current, unitSystem),
          current.windSpeed,
        ),
        buildDetail("humidity", copy.humidity, formatPercent(current.humidity), current.humidity),
        buildDetail(
          "precipitation",
          isIconLocalPilotWeather(current) ? (language === "fur" ? "Precipitazions" : "Precipitazioni") : copy.precipitation,
          joinValueUnit(current.precipitationAmount, "mm"),
          current.precipitationAmount,
        ),
        buildDetail("visibility", copy.visibility, formatVisibility(current.visibilityKm), current.visibilityKm),
        buildDetail("pressure", copy.pressure, formatPressure(current.pressure), current.pressure),
        buildDetail("cloud-cover", copy.cloudCover, formatPercent(current.cloudCover), current.cloudCover),
      ].filter(Boolean)
    : [];
  const feelsLike = details.find((detail) => detail.id === "feels-like") || null;
  const latitude = Number(location?.lat ?? location?.latitude);
  const longitude = Number(location?.lon ?? location?.longitude);
  return {
    status: weatherState.status || "empty",
    city: weatherState.city || "",
    conditionLabel,
    localPilot: buildLocalWeatherPilotMetadata(current),
    weatherVariant: getHomeWeatherVariant(current, icon),
    temperature: {
      value: temperatureValue,
      unit: temperatureValue === null ? "" : temperatureUnit,
      label: joinCompactValueUnit(temperatureValue, temperatureValue === null ? "" : temperatureUnit) || copy.dataUnavailable,
      severity: getTemperatureSeverity(current?.temperature, "current"),
    },
    feelsLike,
    icon,
    solarContext: {
      sunrise: current?.sunrise || null,
      sunset: current?.sunset || null,
      latitude: Number.isFinite(latitude) ? latitude : null,
      longitude: Number.isFinite(longitude) ? longitude : null,
      timeZone: "Europe/Rome",
    },
    detailsTitle: copy.detailsTitle,
    details,
    updatedAt: weatherState.updatedAt || null,
    updatedLabel,
    statusLabel,
    showStatus: shouldShowStatus,
    statusTone: shouldShowStatus ? "warning" : "fresh",
    fromCache: Boolean(weatherState.fromCache),
    isStale: Boolean(weatherState.isStale || weatherState.status === "stale"),
    error: weatherState.error || null,
    alertCount,
    alertSummary,
    alertsLabel: alertSummary?.label || "",
    officialAlerts: weatherState.officialAlerts || null,
    osmerAudit: weatherState.osmerAudit || null,
  };
}

export function buildHomeBulletinViewModel(bulletinState = {}, { language = "it" } = {}) {
  const copy = getHomeViewModelCopy(language);
  const adviceStatus = getTextValue(
    bulletinState.adviceStatus,
    bulletinState.advice ? "ready" : "unavailable",
  );

  return {
    advice: bulletinState.advice || null,
    adviceStatus,
    title: copy.bulletinTitle,
    sourceLabel: getTextValue(bulletinState.sourceLabel, copy.bulletinSource),
    dateLabel: formatHomeDateLabel(bulletinState.dateLabel),
    headline: getTextValue(bulletinState.headline, copy.bulletinFallbackHeadline),
    body: getTextValue(
      bulletinState.body,
      bulletinState.advice || adviceStatus === "pending" ? "" : copy.bulletinFallbackBody,
    ),
    icon: bulletinState.icon || { type: "Cloud" },
    kind: getTextValue(bulletinState.kind, "official_text"),
    snapshotKey: getTextValue(bulletinState.snapshotKey, ""),
    actionLabel: copy.bulletinActionLabel,
    raw: bulletinState,
  };
}

export function buildHomeAlmanacStateFromModel(almanacModel = {}, { language = "it" } = {}) {
  const copy = getHomeViewModelCopy(language);
  const saintLabel = getTextValue(almanacModel.saint?.label, "");
  const rawCycleProgress = almanacModel.moon?.cycleProgress;
  const cycleProgress = rawCycleProgress === null || rawCycleProgress === undefined || rawCycleProgress === ""
    ? Number.NaN
    : Number(rawCycleProgress);

  return {
    dateLabel: getTextValue(almanacModel.dayLabel, ""),
    saintLabel,
    body: getTextValue(
      saintLabel,
      getTextValue(almanacModel.tradition?.label, ""),
    ),
    moonLabel: copy.almanacMoonLabel,
    moon: Number.isFinite(cycleProgress)
      ? {
          cycleProgress: Math.min(100, Math.max(0, cycleProgress)),
          phase: getTextValue(almanacModel.moon?.phase, ""),
        }
      : null,
  };
}

export function buildHomeAlmanacViewModel(almanacState = {}, { language = "it" } = {}) {
  const copy = getHomeViewModelCopy(language);
  const rawCycleProgress = almanacState.moon?.cycleProgress;
  const cycleProgress = rawCycleProgress === null || rawCycleProgress === undefined || rawCycleProgress === ""
    ? Number.NaN
    : Number(rawCycleProgress);

  return {
    title: copy.almanacTitle,
    eyebrow: getTextValue(almanacState.eyebrow, copy.almanacEyebrow),
    dateLabel: formatHomeDateLabel(almanacState.dateLabel),
    cardTitle: getTextValue(almanacState.cardTitle, copy.almanacCardTitle),
    headline: getTextValue(almanacState.headline, copy.almanacFallbackHeadline),
    saintLabel: getTextValue(almanacState.saintLabel, ""),
    body: getTextValue(almanacState.body, copy.almanacFallbackBody),
    moonLabel: getTextValue(almanacState.moonLabel, copy.almanacMoonLabel),
    moon: Number.isFinite(cycleProgress)
      ? {
          cycleProgress: Math.min(100, Math.max(0, cycleProgress)),
          phase: getTextValue(almanacState.moon?.phase, ""),
        }
      : null,
    actionLabel: copy.almanacActionLabel,
    raw: almanacState,
  };
}

function getEventTitle(event) {
  return event?.title || event?.name || event?.summary || "";
}

function getEventLocation(event) {
  return event?.city || event?.location || event?.venue || "";
}

function getEventDateLabel(event) {
  return event?.date_label || event?.dateLabel || event?.date || event?.start_date || "";
}

function getCompactHomeEventDateLabel(dateChip) {
  if (!dateChip) return "";
  if (!dateChip.start) return dateChip.compact || dateChip.label || "";
  if (!dateChip.isRange) return `${dateChip.start.day} ${dateChip.start.month}`;
  return `${dateChip.start.day} ${dateChip.start.month} - ${dateChip.end.day} ${dateChip.end.month}`;
}

function toDate(value) {
  const date = value instanceof Date ? value : new Date(value);
  return Number.isFinite(date.getTime()) ? date : new Date();
}

function getStartOfDay(date) {
  const parsedDate = toDate(date);
  return new Date(parsedDate.getFullYear(), parsedDate.getMonth(), parsedDate.getDate());
}

function getDayDiff(first, second) {
  const firstDay = getStartOfDay(first).getTime();
  const secondDay = getStartOfDay(second).getTime();

  return Math.round((firstDay - secondDay) / 86400000);
}

function normalizeHomeEventText(value) {
  return String(value || "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .trim()
    .toLowerCase();
}

function getHomeEventRaw(record) {
  return record?.raw && typeof record.raw === "object" ? record.raw : {};
}

function getHomeEventLocationText(record) {
  const raw = getHomeEventRaw(record);

  return normalizeHomeEventText([
    record?.location,
    raw.city,
    raw.place,
    raw.event_city,
    raw.provider_place,
    raw.location,
    raw.venue,
  ].filter(Boolean).join(" "));
}

function coerceHomeEventNumber(value) {
  if (typeof value === "number") return Number.isFinite(value) ? value : null;

  const parsed = Number(String(value || "").replace(",", "."));
  return Number.isFinite(parsed) ? parsed : null;
}

function getHomeEventDistanceKm(record) {
  const raw = getHomeEventRaw(record);

  return coerceHomeEventNumber(raw.distance_km ?? raw.distanceKm ?? raw.distance);
}

function getHomeEventLocationRank(record, location = null) {
  const city = normalizeHomeEventText(
    typeof location === "string" ? location : location?.city,
  );

  if (!city) return 0;

  const locationText = getHomeEventLocationText(record);
  const distanceKm = getHomeEventDistanceKm(record);

  if (locationText === city) return 100;
  if (locationText.includes(city)) return 80;

  if (distanceKm !== null) {
    if (distanceKm <= 5) return 60;
    if (distanceKm <= 10) return 45;
    if (distanceKm <= 20) return 25;
    if (distanceKm <= 35) return 5;
    if (distanceKm > 50) return -180;
    return -120;
  }

  return locationText ? -30 : 0;
}

function getHomeEventQualityRank(record) {
  const raw = getHomeEventRaw(record);
  let score = 0;

  if (record?.title) score += 6;
  if (record?.date) score += 5;
  if (record?.location) score += 4;
  if (record?.category && record.category !== "other") score += 3;
  if (record?.image) score += 3;
  if (record?.source || raw.source) score += 2;

  return score;
}

function getHomeEventRank(record, { index = 0, location = null, now = new Date(), weather = null } = {}) {
  const today = getStartOfDay(now);
  const range = parseEventDateRange(record.date, { now });
  const timeScores = {
    today: 400,
    weekend: 260,
    next: 220,
    outside: 0,
  };
  let score = timeScores[record.timeCategory] ?? 0;

  if (range) {
    const startOffset = getDayDiff(range.start, today);
    const endOffset = getDayDiff(range.end, today);
    const durationDays = Math.max(1, getDayDiff(range.end, range.start) + 1);
    const isOngoing = startOffset < 0 && endOffset >= 0;

    if (startOffset === 0) score += 90;
    else if (startOffset === 1) score += 70;
    else if (startOffset > 1 && startOffset <= 3) score += 45;
    else if (isOngoing) score += 20;

    if (endOffset < 0) score -= 500;
    if (durationDays > 3) score -= Math.min(110, (durationDays - 3) * 8);
    if (isOngoing && durationDays > 14) score -= 40;
  }

  score += getHomeEventLocationRank(record, location);
  score += getHomeEventQualityRank(record);
  score += getHomeWeatherFitScoreDelta(getEventWeatherFit(record, weather));

  return score - index / 1000;
}

function rankHomeEventRecords(records, { location = null, now = new Date(), weather = null } = {}) {
  return records
    .map((record, index) => ({
      record,
      score: getHomeEventRank(record, { index, location, now, weather }),
    }))
    .sort((first, second) => second.score - first.score)
    .map((item) => item.record);
}

function parseProgrammeDay(value) {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(String(value || ""))) return null;
  const day = new Date(`${value}T00:00:00`);
  return Number.isFinite(day.getTime())
    && day.getFullYear() === Number(value.slice(0, 4))
    && day.getMonth() + 1 === Number(value.slice(5, 7))
    && day.getDate() === Number(value.slice(8, 10)) ? day : null;
}

function hasUsableEventUrl(value) {
  return /^https?:\/\/[^\s]+$/i.test(String(value || "").trim());
}

function selectFeaturedHomeEvent(records, { now = new Date() } = {}) {
  const today = getStartOfDay(now);

  return records.find((record) => {
    const raw = getHomeEventRaw(record);
    const start = parseProgrammeDay(raw.programme_start_date);
    const end = parseProgrammeDay(raw.programme_end_date);

    return record.localProgrammePriority
      && raw.is_real !== false
      && start !== null
      && end !== null
      && start <= today
      && end >= today
      && Boolean(String(record.source || "").trim())
      && hasUsableEventUrl(raw.programme_url || record.url)
      && hasUsableEventUrl(record.image);
  }) || null;
}

export function buildHomeEventsViewModel(
  eventsState = {},
  {
    language = "it",
    location = null,
    maxItems = 3,
    now = new Date(),
    weather = null,
    fixedFvgScope = false,
  } = {},
) {
  const copy = getHomeViewModelCopy(language);
  const languageKey = getLanguageKey(language);
  const eventsCopy = getEventsViewCopy(languageKey);
  const available = eventsState.status !== "unsupported"
    && eventsState.unavailableReason !== "events_fvg_only";
  const items = available && Array.isArray(eventsState.items) ? eventsState.items : [];
  const total = Number(eventsState.total ?? items.length);
  const rankingDate = toDate(now);
  const records = items.map((event) => buildEventRecord(event, { language: languageKey, location, now: rankingDate }));
  const uniqueRecords = rankEventsForLocation(records, { location, now: rankingDate });
  const contextualCount = getContextualEventsSummary(uniqueRecords);
  const countCaption = contextualCount.period === "today"
    ? contextualCount.count === 1 ? copy.eventsTodayCountOne : copy.eventsTodayCount
    : contextualCount.count === 1 ? copy.eventsNextCountOne : copy.eventsNextCount;
  const rankedRecords = rankHomeEventRecords(uniqueRecords, { location, now: rankingDate, weather });
  const editorialRecord = selectFeaturedHomeEvent(rankedRecords, { now: rankingDate });
  const teaserRecords = editorialRecord
    ? [editorialRecord, ...rankedRecords.filter((record) => record !== editorialRecord)]
    : rankedRecords;
  const teaserItems = teaserRecords.slice(0, maxItems).map((record) => {
    const event = record.raw;

    return {
      category: record.category || "other",
      id: record.id || event?.id || event?.url || getEventTitle(event),
      image: record.image || "",
      title: record.title || getEventTitle(event),
      location: record.location || getEventLocation(event),
      dateLabel: getCompactHomeEventDateLabel(record.dateChip) || getEventDateLabel(event),
      featured: record === editorialRecord,
      raw: event,
    };
  });
  const hasItems = teaserItems.length > 0;
  const message = (() => {
    if (!available) {
      const locationLabel = String(eventsState.unavailableLocation || "").trim()
        || (languageKey === "fur" ? "cheste localitât" : "questa località");
      return eventsCopy.fvgOnlyBody.replace("{location}", locationLabel);
    }
    const degraded = getDegradedEventsMessage(eventsState, { language: languageKey, hasItems });
    if (degraded) return degraded;
    if (eventsState.error && !hasItems) return `${eventsCopy.unavailableTitle}. ${eventsCopy.unavailableBody}`;
    if (eventsState.error && hasItems) return copy.eventsStale;
    if (eventsState.isRefreshing && !hasItems) return eventsCopy.loadingBody || copy.eventsRefreshing;
    if (eventsState.isPartial || eventsState.shouldRetry) return copy.eventsRefreshing;
    if (!hasItems) return eventsCopy.emptyBody;
    return "";
  })();

  return {
    status: eventsState.status || "empty",
    available,
    title: !available
      ? eventsCopy.fvgOnlyTitle
      : fixedFvgScope ? copy.eventsFvgTitle : copy.eventsTitle,
    countValue: String(contextualCount.count),
    countCaption,
    countLabel: `${contextualCount.count} ${countCaption}`,
    countPeriod: contextualCount.period,
    metaLabel: available
      ? `${contextualCount.count} ${countCaption} ${fixedFvgScope ? copy.eventsFvgSuffix : copy.eventsNearbySuffix}`
      : "",
    items: teaserItems,
    total,
    loadedLimit: eventsState.loadedLimit || 0,
    fromCache: Boolean(eventsState.fromCache),
    cacheStatus: eventsState.cacheStatus || null,
    isRefreshing: Boolean(eventsState.isRefreshing),
    isPartial: Boolean(eventsState.isPartial),
    isDegraded: eventsState.catalogHealth?.status === "degraded",
    isUnavailable: Boolean(eventsState.error && !hasItems),
    shouldRetry: Boolean(eventsState.shouldRetry),
    error: eventsState.error || null,
    message,
    tagsLabel: copy.eventsTagsLabel,
    actionLabel: copy.eventsActionLabel,
    emptyTitle: eventsCopy.emptyTitle,
    emptyBody: eventsCopy.emptyBody,
  };
}

export function buildHomeViewModel(homeData = {}, options = {}) {
  const language = getLanguageKey(options.language);
  const copy = getHomeViewModelCopy(language);
  const dailyCopy = getDailySummaryCopy(language);
  const weather = buildHomeWeatherViewModel(homeData.weather || {}, {
    language,
    location: homeData.location,
    now: options.now,
    unitSystem: options.unitSystem,
  });
  const editorialLocation = homeData.editorialLocation || homeData.location || weather.city || null;
  const hasSeparateEditorialLocation = Boolean(homeData.editorialLocation)
    && getLocationCacheKey(homeData.editorialLocation) !== getLocationCacheKey(homeData.location);
  const eventsUnsupported = homeData.sourceAvailability?.events?.status === "unsupported";
  const eventsState = eventsUnsupported
    ? {
        ...(homeData.events || {}),
        items: [],
        status: "unsupported",
        total: 0,
        unavailableLocation: getLocationDisplayName(homeData.location, language),
        unavailableReason: "events_fvg_only",
      }
    : homeData.events || {};
  const events = buildHomeEventsViewModel(eventsState, {
    language,
    location: editorialLocation,
    maxItems: options.maxEvents,
    now: options.now,
    weather: hasSeparateEditorialLocation ? null : homeData.weather?.current || null,
    fixedFvgScope: hasSeparateEditorialLocation || !isFvgLocation(homeData.location),
  });
  const bulletin = homeData.sourceAvailability
    && homeData.sourceAvailability.osmer?.status !== "enabled"
    ? null
    : buildHomeBulletinViewModel(homeData.bulletin || {}, { language });
  const hourlyItems = Array.isArray(homeData.hourly?.items)
    ? homeData.hourly.items.filter(Boolean).slice(0, 48)
    : [];
  const hourly = hourlyItems.length
      ? {
        items: hourlyItems,
        sourceLabel: String(homeData.hourly?.sourceLabel || "").trim(),
        title: String(homeData.hourly?.title || (hourlyItems.length === 48 ? copy.hourlyTitle : copy.hourlyPartialTitle)).trim(),
        scrollLabel: copy.hourlyScrollLabel,
      }
    : null;
  const almanac = buildHomeAlmanacViewModel(homeData.almanac || {}, { language });
  const activeLocationTitle = getLocationDisplayName(homeData.location, language);
  const locationTitle = activeLocationTitle
    || getLocationDisplayName(weather.city, language)
    || copy.locationFallback;
  const locationRegion = String(homeData.location?.region || "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .trim()
    .toLowerCase();
  const isOutsideFvg = Boolean(locationRegion && !locationRegion.includes("friuli"));
  const territoryTitle = String(homeData.territory?.title || "").trim();
  const territory = territoryTitle
    ? {
      anchor: getDiscoverCardAnchor(homeData.territory?.id),
      heading: String(homeData.territory?.heading || "").trim(),
      id: String(homeData.territory?.id || "").trim(),
      type: String(homeData.territory?.type || "").trim(),
      typeLabel: String(homeData.territory?.typeLabel || "").trim(),
      seasonLabel: String(homeData.territory?.seasonLabel || "").trim(),
      metaLabel: [homeData.territory?.typeLabel, homeData.territory?.seasonLabel]
        .map((value) => String(value || "").trim())
        .filter(Boolean)
        .join(" · "),
      text: String(homeData.territory?.text || "").trim(),
      title: territoryTitle,
    }
    : null;

  return {
    sectionTitle: copy.appSectionTitle,
    locationTitle,
    sceneMode: isOutsideFvg ? "neutral" : "regional",
    locationLabel: dailyCopy.locationLabel,
    summaryFallback: dailyCopy.currentSummaryFallback,
    status: weather.error && !weather.icon ? "error" : weather.isStale || events.error || events.isDegraded ? "degraded" : "ready",
    weather,
    localMetrics: buildHomeLocalMetricsViewModel(homeData.localWeather, { language }),
    hourly,
    bulletin,
    officialAlert: homeData.officialAlert || null,
    almanac,
    events,
    territory,
    ok: !weather.error && !events.error,
    changeLocationLabel: copy.changeLocationLabel,
  };
}
