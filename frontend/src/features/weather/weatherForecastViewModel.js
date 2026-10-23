import { camsContinuityFromEvidence } from "../../services/camsContinuityPolicy";
import { getLocationDisplayName } from "../../domain/geo/locationDisplayName";
import { readWeatherNumber } from "../../domain/weather/normalizedWeather";
import { buildBulletinLocalViewModel } from "../bulletin/bulletinLocalViewModel";

const TIME_ZONE = "Europe/Rome";
const RETAINED_VALUE_MAX_AGE_MS = 24 * 60 * 60 * 1000;
const RETAINABLE_PRESENTATION_FIELDS = Object.freeze([
  Object.freeze({ detail: null, id: "temperature", display: "temperature" }),
  Object.freeze({ detail: "apparentTemperature", id: "apparentTemperature" }),
  Object.freeze({ detail: "humidity", id: "humidity" }),
  Object.freeze({ detail: "pressure", id: "pressure" }),
  Object.freeze({ detail: "cloudCover", id: "cloudCover" }),
  Object.freeze({ detail: "windSpeed", id: "windSpeed" }),
  Object.freeze({ detail: "windDirection", id: "windDirection" }),
  Object.freeze({ detail: "windGusts", id: "windGusts" }),
  Object.freeze({ detail: "precipitation", id: "precipitation", display: "precipitationAmount" }),
]);

const COPY = {
  it: {
    camsAvailable: "Concentrazioni modellistiche disponibili",
    camsContinuity: "Previsione della corsa precedente · aggiornamento in attesa",
    camsHeading: "Pollini",
    camsLastVerified: "Ultimo dato verificato",
    camsPending: "Caricamento…",
    camsUnavailable: "Dati non disponibili",
    camsValidAt: "Dato valido alle",
    change: "Cambia",
    completeDay: "Giornata completa",
    dataPartial: "Dati parziali",
    dataVerified: "Dati verificati",
    forecastTitle: "Prossime 48 ore",
    fromNow: "Da quest'ora",
    gusts: "Raffica max",
    iconSource: "ICON-2I",
    lastAvailable: "Ultimo aggiornamento disponibile",
    modelLabel: "Modello",
    modelRun: "aggiornamento modello",
    sourceLabel: "Fonte",
    sourceUpdated: "dati aggiornati",
    weatherSource: "Fonte meteo",
    precipitation: "Precipitazioni",
    retainedValues: "Alcuni valori provengono dall'ultimo aggiornamento valido",
    tomorrow: "Domani",
    today: "Oggi",
  },
  fur: {
    camsAvailable: "Concentrazions di model disponibii",
    camsContinuity: "Prevision de corse precedente · in spiete dal inzornament",
    camsHeading: "Polins",
    camsLastVerified: "Ultin dât verificât",
    camsPending: "In cjariament…",
    camsUnavailable: "Dâts no disponibii",
    camsValidAt: "Dât valit aes",
    change: "Cambie",
    completeDay: "Zornade complete",
    dataPartial: "Dâts parziâi",
    dataVerified: "Dâts verificâts",
    forecastTitle: "Prossimis 48 oris",
    fromNow: "Di cheste ore indenant",
    gusts: "Rafiche massime",
    iconSource: "ICON-2I",
    lastAvailable: "Ultin inzornament disponibil",
    modelLabel: "Model",
    modelRun: "inzornament dal model",
    sourceLabel: "Font",
    sourceUpdated: "dâts inzornâts",
    weatherSource: "Font meteo",
    precipitation: "Precipitazions",
    retainedValues: "Cualchi valôr al ven dal ultin inzornament valit",
    tomorrow: "Doman",
    today: "Vuê",
  },
};

function getLanguageKey(language) {
  return language === "fur" ? "fur" : "it";
}

function formatDateParts(value) {
  const date = new Date(value);
  if (!Number.isFinite(date.getTime())) return null;
  const parts = new Intl.DateTimeFormat("en-GB", {
    day: "2-digit",
    month: "2-digit",
    timeZone: TIME_ZONE,
    year: "numeric",
  }).formatToParts(date);
  const values = Object.fromEntries(parts.map(({ type, value: part }) => [type, part]));
  return values.year && values.month && values.day
    ? `${values.year}-${values.month}-${values.day}`
    : null;
}

function addCalendarDays(dateKey, days) {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(String(dateKey || ""))) return null;
  const date = new Date(`${dateKey}T12:00:00Z`);
  date.setUTCDate(date.getUTCDate() + days);
  return date.toISOString().slice(0, 10);
}

function formatClock(value) {
  const date = new Date(value);
  if (!Number.isFinite(date.getTime())) return "";
  return new Intl.DateTimeFormat("it-IT", {
    hour: "2-digit",
    hour12: false,
    minute: "2-digit",
    timeZone: TIME_ZONE,
  }).format(date);
}

function formatShortDate(value) {
  if (!value) return "";
  const date = new Date(value);
  if (!Number.isFinite(date.getTime())) return "";
  return new Intl.DateTimeFormat("it-IT", {
    day: "2-digit",
    month: "2-digit",
    timeZone: TIME_ZONE,
  }).format(date);
}

function formatCompactRunLabel(value, referenceDateKey) {
  if (!value) return "";
  const runDateKey = formatDateParts(value);
  const runClock = formatClock(value);
  const runDate = runDateKey && runDateKey !== referenceDateKey ? formatShortDate(value) : "";
  return [runDate, runClock].filter(Boolean).join(" · ");
}

function formatDateTime(value) {
  const date = new Date(value);
  if (!Number.isFinite(date.getTime())) return "";
  return new Intl.DateTimeFormat("it-IT", {
    day: "2-digit",
    hour: "2-digit",
    hour12: false,
    minute: "2-digit",
    month: "2-digit",
    timeZone: TIME_ZONE,
    year: "numeric",
  }).format(date);
}

function formatDayLabel(value, language, { month: monthStyle = "short", weekdayOnly = false } = {}) {
  const date = new Date(value);
  if (!Number.isFinite(date.getTime())) return "";
  if (language === "fur") {
    // Do not rely on browser support for fur-IT: unsupported locales fall back to Italian.
    const localDate = formatDateParts(value);
    const [year, month, day] = localDate.split("-").map(Number);
    const weekday = new Date(Date.UTC(year, month - 1, day)).getUTCDay();
    const weekdays = ["Domenie", "Lunis", "Martars", "Miercus", "Joibe", "Vinars", "Sabide"];
    if (weekdayOnly) return weekdays[weekday];
    const months = monthStyle === "long"
      ? ["zenâr", "fevrâr", "març", "avrîl", "mai", "jugn", "lui", "avost", "setembar", "otubar", "novembar", "dicembar"]
      : ["zen", "fev", "mar", "avr", "mai", "jug", "lui", "avo", "set", "otu", "nov", "dic"];
    return `${weekdays[weekday]} ${day} ${months[month - 1]}`;
  }
  const locale = "it-IT";
  const label = new Intl.DateTimeFormat(locale, {
    ...(weekdayOnly ? {} : { day: "numeric", month: monthStyle }),
    timeZone: TIME_ZONE,
    weekday: "long",
  }).format(date);
  return label ? `${label.charAt(0).toUpperCase()}${label.slice(1)}` : "";
}

function zonedHour(value) {
  const date = new Date(value);
  if (!Number.isFinite(date.getTime())) return null;
  const hour = new Intl.DateTimeFormat("en-GB", {
    hour: "2-digit",
    hourCycle: "h23",
    timeZone: TIME_ZONE,
  }).format(date);
  const numeric = Number(hour);
  return Number.isFinite(numeric) ? numeric : null;
}

function formatMetric(value, unit, maximumFractionDigits = 0) {
  const numeric = readWeatherNumber(value);
  if (numeric === null) return null;
  return `${new Intl.NumberFormat("it-IT", {
    maximumFractionDigits,
    minimumFractionDigits: numeric > 0 && numeric < 1 ? 1 : 0,
  }).format(numeric)}${unit}`;
}

function normalizeProviderId(value) {
  return String(value || "").trim().toLowerCase().replaceAll("-", "_");
}

function getSourceDescriptor(source, providerId) {
  if (!source || typeof source !== "object") return null;
  const normalizedProviderId = normalizeProviderId(providerId);
  const descriptor = Array.isArray(source.priority)
    ? source.priority.find((candidate) => (
      normalizeProviderId(candidate?.id) === normalizedProviderId
    ))
    : null;
  return descriptor && typeof descriptor === "object" ? descriptor : null;
}

function resolveWeatherProvider(weatherState, copy) {
  const rawCurrent = weatherState?.rawCurrent || {};
  const forecast = weatherState?.forecast || {};
  const currentSource = rawCurrent.source || {};
  const forecastSource = forecast.source || {};
  const providerId = [
    rawCurrent.primary_source,
    currentSource.primary_source,
    currentSource.active,
    rawCurrent.data_quality?.source,
    forecast.primary_source,
    forecastSource.primary_source,
    forecastSource.active,
    forecast.data_quality?.source,
  ].map(normalizeProviderId).find(Boolean) || "";
  const knownLabel = {
    arpa_fvg_osmer: "ARPA FVG OSMER",
    icon2i: copy.iconSource,
    icon2i_local_pilot: copy.iconSource,
    open_meteo: "Open-Meteo",
  }[providerId];
  const descriptor = getSourceDescriptor(currentSource, providerId)
    || getSourceDescriptor(forecastSource, providerId);
  const declaredLabel = [
    descriptor?.name,
    descriptor?.label,
    currentSource.label,
    currentSource.name,
    forecastSource.label,
    forecastSource.name,
  ].map((value) => String(value || "").trim()).find(Boolean);
  const source = knownLabel || declaredLabel || copy.weatherSource;
  const isModel = providerId === "icon2i_local_pilot"
    || providerId === "icon2i"
    || providerId === "open_meteo";

  return {
    id: providerId || null,
    isIcon: providerId === "icon2i_local_pilot" || providerId === "icon2i",
    label: source,
    typeLabel: isModel ? copy.modelLabel : copy.sourceLabel,
  };
}

function forecastDayByDate(weatherState) {
  const entries = Array.isArray(weatherState?.forecast?.forecast)
    ? weatherState.forecast.forecast
    : [];
  return new Map(entries.map((entry) => [String(entry?.date || ""), entry]));
}

function representativeItem(items) {
  return items.reduce((selected, item) => {
    if (!selected) return item;
    const selectedHour = zonedHour(selected.timestamp);
    const itemHour = zonedHour(item.timestamp);
    if (itemHour === null) return selected;
    if (selectedHour === null || Math.abs(itemHour - 12) < Math.abs(selectedHour - 12)) return item;
    return selected;
  }, null);
}

function buildHourlyGroups(items, { language, referenceDateKey }) {
  const copy = COPY[language];
  const tomorrowKey = addCalendarDays(referenceDateKey, 1);
  const groups = [];
  const byDate = new Map();

  for (const item of items) {
    const dateKey = item.dateKey || formatDateParts(item.timestamp);
    if (!dateKey) continue;
    let group = byDate.get(dateKey);
    if (!group) {
      const groupLabel = dateKey === referenceDateKey
        ? copy.today
        : dateKey === tomorrowKey
          ? copy.tomorrow
          : formatDayLabel(item.timestamp, language);
      group = {
        dateKey,
        label: groupLabel,
        shortLabel: dateKey === referenceDateKey || dateKey === tomorrowKey
          ? groupLabel
          : formatDayLabel(item.timestamp, language, { weekdayOnly: true }),
        dateLabel: formatDayLabel(item.timestamp, language, { month: "long" }),
        items: [],
      };
      byDate.set(dateKey, group);
      groups.push(group);
    }
    group.items.push({ ...item, groupLabel: group.label });
  }

  return groups;
}

function buildDaySummary(group, forecastDay, { allItems, copy, kind, now }) {
  if (!group?.items?.length) return null;
  const representative = representativeItem(group.items);
  const temperatures = group.items
    .map((item) => readWeatherNumber(item.values?.temperature))
    .filter((value) => value !== null);
  const nowMs = new Date(now).getTime();
  const intervalItems = allItems.filter((item) => {
    if (!item.details?.intervalLabel) return false;
    if (formatDateParts(item.intervalStart) !== group.dateKey) return false;
    const intervalEnd = Date.parse(item.intervalEnd);
    return !Number.isFinite(nowMs) || !Number.isFinite(intervalEnd) || intervalEnd > nowMs;
  });
  const gusts = intervalItems
    .map((item) => readWeatherNumber(item.values?.windGusts))
    .filter((value) => value !== null);
  const precipitationValues = intervalItems
    .map((item) => readWeatherNumber(item.values?.precipitation));
  const hasExpectedIntervals = kind === "today"
    ? precipitationValues.length > 0
    : intervalItems.length === group.items.length;
  const hasCompletePrecipitation = hasExpectedIntervals
    && precipitationValues.every((value) => value !== null);
  const precipitationTotal = hasCompletePrecipitation
    ? precipitationValues.reduce((total, value) => total + value, 0)
    : null;
  const completeDay = forecastDay?.partial_day === false
    && zonedHour(group.items[0]?.timestamp) === 0
    && zonedHour(group.items.at(-1)?.timestamp) === 23;
  const minTemperature = completeDay
    ? readWeatherNumber(forecastDay?.min_temp)
    : temperatures.length ? Math.min(...temperatures) : null;
  const maxTemperature = completeDay
    ? readWeatherNumber(forecastDay?.max_temp)
    : temperatures.length ? Math.max(...temperatures) : null;
  const coverageLabel = kind === "today" && !completeDay
    ? copy.fromNow
    : completeDay ? copy.completeDay : copy.dataPartial;

  return {
    ariaLabel: [
      group.label,
      coverageLabel,
      representative?.conditionLabel,
      minTemperature === null ? "" : `min ${formatMetric(minTemperature, " gradi")}`,
      maxTemperature === null ? "" : `max ${formatMetric(maxTemperature, " gradi")}`,
      precipitationTotal === null ? "" : `${copy.precipitation} ${formatMetric(precipitationTotal, " mm", 1)}`,
    ].filter(Boolean).join(", "),
    conditionLabel: representative?.conditionLabel || "",
    coverageLabel,
    fullDayMinTemperature: formatMetric(readWeatherNumber(forecastDay?.min_temp) ?? readWeatherNumber(forecastDay?.sampled_min_temp), "°"),
    fullDayMaxTemperature: formatMetric(readWeatherNumber(forecastDay?.max_temp) ?? readWeatherNumber(forecastDay?.sampled_max_temp), "°"),
    dateKey: group.dateKey,
    firstItemKey: group.items[0]?.timestamp || "",
    gustLabel: gusts.length ? formatMetric(Math.max(...gusts), " km/h") : null,
    gustsLabel: copy.gusts,
    icon: representative?.icon || null,
    id: kind,
    label: group.label,
    maxTemperature: formatMetric(maxTemperature, "°"),
    minTemperature: formatMetric(minTemperature, "°"),
    precipitationLabel: formatMetric(precipitationTotal, " mm", 1),
    precipitationTitle: copy.precipitation,
  };
}

function formatHeaderStatus(weatherState, copy) {
  const rawCurrent = weatherState?.rawCurrent || {};
  const quality = rawCurrent.data_quality || {};
  const formatTimestamp = (value) => {
    if (!value) return "";
    const date = new Date(value);
    return Number.isFinite(date.getTime()) ? new Intl.DateTimeFormat("it-IT", {
      day: "2-digit", month: "2-digit", year: "numeric",
      hour: "2-digit", minute: "2-digit", timeZone: TIME_ZONE,
    }).format(date) : "";
  };
  const provider = resolveWeatherProvider(weatherState, copy);
  const sourceTimestamp = provider.isIcon
    ? quality.run_utc
    : quality.generated_at || weatherState?.forecast?.data_quality?.generated_at;
  const sourceTime = formatTimestamp(sourceTimestamp);
  const sourceTimingCopy = provider.isIcon ? copy.modelRun : copy.sourceUpdated;
  const runtimeFallback = rawCurrent.cache?.runtime_fallback === true
    || quality.flags?.includes("runtime_refresh_failed_bundle_retained");
  const stale = weatherState?.isStale
    || weatherState?.error
    || quality.status === "stale"
    || runtimeFallback;
  const scopeId = rawCurrent.primary_source === "icon2i_local_pilot"
    && quality.municipality_istat
    && quality.catalog_sha256
    ? [rawCurrent.primary_source, quality.municipality_istat, quality.catalog_sha256].join(":")
    : null;

  return {
    providerId: provider.id,
    runAt: sourceTimestamp || null,
    scopeId,
    source: provider.label,
    sourceTypeLabel: provider.typeLabel,
    sourceTimingLabel: [
      provider.label,
      sourceTime ? `${sourceTimingCopy} ${sourceTime}` : "",
    ].filter(Boolean).join(" · "),
    statusLabel: stale ? copy.lastAvailable : copy.dataVerified,
    statusTone: stale ? "warning" : "fresh",
  };
}

function buildCamsModel(localWeather, weatherState, copy, loading) {
  const pollen = localWeather?.pollen;
  const rawCurrent = weatherState?.rawCurrent || {};
  const quality = rawCurrent.data_quality || {};
  const air = rawCurrent.air_quality_data || null;
  // An explicit CAMS outcome (including revocation) takes precedence over the weather request.
  const pending = quality.cams_status === "pending" || pollen?.status === "pending"
    || (loading && !quality.cams_status);
  const airAvailable = ["particulate_matter_2.5um", "particulate_matter_10um", "ozone", "nitrogen_dioxide"]
    .some((field) => typeof air?.values?.[field] === "number" && Number.isFinite(air.values[field]));
  const airStatus = airAvailable ? "available" : pending ? "pending" : "unavailable";
  const status = pollen?.available
    ? "available"
    : pending
      ? "pending"
      : "unavailable";
  const validTime = formatClock(pollen?.validAt || quality.cams_valid_at_utc);
  const familyLastKnown = quality.cams_sample_status === "last_known";
  const pollenSampleStatus = familyLastKnown || rawCurrent.pollen_data?.sample_status === "last_known"
    ? "last_known" : "current";
  const airSampleStatus = familyLastKnown || air?.sample_status === "last_known"
    ? "last_known" : "current";
  const lastKnownLabel = (sampleStatus, value) => {
    if (sampleStatus !== "last_known") return "";
    const timestamp = formatDateTime(value);
    return [copy.camsLastVerified, timestamp].filter(Boolean).join(" · ");
  };

  return {
    heading: copy.camsHeading,
    continuityLabel: status === "available" && quality.cams_status === "stale"
      && !familyLastKnown && camsContinuityFromEvidence(rawCurrent) ? copy.camsContinuity : "",
    air,
    airStatus,
    airLastKnownLabel: lastKnownLabel(airSampleStatus, air?.valid_at || quality.cams_valid_at_utc),
    airSampleStatus,
    note: status === "available"
      ? copy.camsAvailable
      : status === "pending" ? copy.camsPending : copy.camsUnavailable,
    runAt: pollen?.runAt || quality.cams_run_utc || null,
    pollenLastKnownLabel: lastKnownLabel(pollenSampleStatus, pollen?.validAt || quality.cams_valid_at_utc),
    pollenSampleStatus,
    status,
    units: pollen?.units || "grani/m³",
    validAt: pollen?.validAt || quality.cams_valid_at_utc || null,
    validLabel: validTime ? `${copy.camsValidAt} ${validTime}` : "",
    values: Array.isArray(pollen?.values)
      ? pollen.values.filter((entry) => readWeatherNumber(entry?.value) !== null)
      : [],
  };
}

function retainHourlyPresentation(previousModel, nextItems, {
  locationTitle, now, scopeId, source,
}) {
  if (
    !Array.isArray(previousModel?.hourly?.items)
    || previousModel.header?.locationTitle !== locationTitle
    || previousModel.header?.source !== source
    || !previousModel.header?.scopeId
    || previousModel.header.scopeId !== scopeId
  ) return nextItems;
  const nowMs = new Date(now).getTime();
  const previousByTimestamp = new Map(
    previousModel.hourly.items
      .map((item) => [Date.parse(item.timestamp), item])
      .filter(([timestamp]) => Number.isFinite(timestamp)),
  );

  return nextItems.map((item) => {
    const timestamp = Date.parse(item.timestamp);
    const previous = Number.isFinite(timestamp) ? previousByTimestamp.get(timestamp) : null;
    if (!previous) return item;
    const retainedFields = new Set(item.retainedFields || []);
    const retainedOrigins = { ...(item.retainedOrigins || {}) };
    const values = { ...(item.values || {}) };
    const details = { ...(item.details || {}) };
    let changed = false;

    for (const field of RETAINABLE_PRESENTATION_FIELDS) {
      if (
        readWeatherNumber(values[field.id]) === null
        && readWeatherNumber(previous.values?.[field.id]) !== null
      ) {
        const origin = previous.retainedOrigins?.[field.id]
          || previousModel.header.runAt
          || null;
        const originMs = Date.parse(origin);
        if (
          !Number.isFinite(nowMs)
          || !Number.isFinite(originMs)
          || nowMs < originMs
          || nowMs - originMs > RETAINED_VALUE_MAX_AGE_MS
        ) continue;
        values[field.id] = previous.values[field.id];
        if (field.detail) details[field.detail] = previous.details?.[field.detail] || "";
        retainedFields.add(field.id);
        retainedOrigins[field.id] = origin;
        changed = true;
      }
    }
    if (!changed) return item;
    if (!details.intervalLabel && previous.details?.intervalLabel) {
      details.intervalLabel = previous.details.intervalLabel;
    }
    const temperatureRetained = retainedFields.has("temperature");
    const precipitationRetained = retainedFields.has("precipitation");
    return {
      ...item,
      details,
      intervalEnd: item.intervalEnd || previous.intervalEnd || null,
      intervalStart: item.intervalStart || previous.intervalStart || null,
      precipitationAmount: precipitationRetained
        ? previous.precipitationAmount
        : item.precipitationAmount,
      retainedFields: [...retainedFields].sort(),
      retainedOrigins,
      temperature: temperatureRetained ? previous.temperature : item.temperature,
      values,
    };
  });
}

export function buildWeatherForecastViewModel(weatherState, {
  language = "it",
  loading = false,
  location = null,
  now = Date.now(),
  previousModel = null,
} = {}) {
  if (!weatherState) return null;
  const languageKey = getLanguageKey(language);
  const copy = COPY[languageKey];
  const localWeather = buildBulletinLocalViewModel(weatherState, {
    hourlyHours: 48,
    includeIncompleteHourly: true,
    language: languageKey,
    location,
    now,
  });
  const baseItems = localWeather?.hourly || [];
  const header = formatHeaderStatus(weatherState, copy);
  const locationTitle = getLocationDisplayName(location, languageKey)
    || getLocationDisplayName(weatherState.city, languageKey)
    || weatherState.city
    || "";
  const items = retainHourlyPresentation(previousModel, baseItems, {
    locationTitle,
    now,
    scopeId: header.scopeId,
    source: header.source,
  });
  const referenceDateKey = formatDateParts(now) || formatDateParts(items[0]?.timestamp);
  const groups = buildHourlyGroups(items, { language: languageKey, referenceDateKey });
  const tomorrowKey = addCalendarDays(referenceDateKey, 1);
  const forecastDays = forecastDayByDate(weatherState);
  const todayGroup = groups.find(({ dateKey }) => dateKey === referenceDateKey);
  const tomorrowGroup = groups.find(({ dateKey }) => dateKey === tomorrowKey);
  const thirdDayKey = addCalendarDays(referenceDateKey, 2);
  const thirdGroup = groups.find(({ dateKey }) => dateKey === thirdDayKey);
  const summaries = [
    buildDaySummary(todayGroup, forecastDays.get(referenceDateKey), {
      allItems: items, copy, kind: "today", now,
    }),
    buildDaySummary(tomorrowGroup, forecastDays.get(tomorrowKey), {
      allItems: items, copy, kind: "tomorrow", now,
    }),
    buildDaySummary(thirdGroup ? {
      ...thirdGroup, label: languageKey === "fur" ? "Passantdoman" : "Dopodomani",
    } : null, forecastDays.get(thirdDayKey), {
      allItems: items, copy, kind: "dayAfterTomorrow", now,
    }),
  ].filter(Boolean);
  const hasRetainedValues = items.some((item) => item.retainedFields?.length);

  return {
    cams: buildCamsModel(localWeather, weatherState, copy, loading),
    uvPoint: { latitude: location?.latitude ?? location?.lat, longitude: location?.longitude ?? location?.lon },
    changeLocationLabel: localWeather?.changeLabel || copy.change,
    header: {
      ...header,
      compactRunLabel: formatCompactRunLabel(header.runAt, referenceDateKey),
      compactSourceLabel: `${header.sourceTypeLabel} ${header.source}`.trim(),
      locationTitle,
      dateLabel: formatDayLabel(now, languageKey, { month: "long" }),
      dateKey: referenceDateKey,
    },
    hourly: items.length
      ? {
        groups,
        hasRetainedValues,
        items,
        retainedValuesLabel: hasRetainedValues ? copy.retainedValues : "",
        scrollLabel: localWeather?.evolutionLabel || copy.forecastTitle,
        summaries,
        title: localWeather?.evolutionLabel || copy.forecastTitle,
      }
      : null,
    weather: {
      error: weatherState.error || null,
      localPilot: localWeather?.localPilot || null,
    },
  };
}
