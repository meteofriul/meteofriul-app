import {
  buildOfficialAlertSummary,
  formatOfficialAlertContent,
  formatOfficialAlertText,
  getPrimaryOfficialAlert,
} from "../../domain/alerts/officialAlerts";
import { getOsmerStructuredDay, mapOsmerAreaToCondition } from "../../domain/weather/osmerAdapter";
import { classifyOsmerStructuredDay } from "../../domain/weather/osmerStructuredContract";
import { summarizeOsmerTemporalDay } from "../../domain/weather/osmerTemporalSummary";
import {
  BULLETIN_DAYS,
  BULLETIN_SOURCE_URL,
} from "./bulletinFixture";

const DAY_IDS = ["today", "tomorrow", "afterTomorrow", "plus3", "plus4"];

const AREA_MAP_POINTS = {
  A1: { id: "a1", x: 34, y: 19 },
  A2: { id: "a2", x: 68, y: 18 },
  A3: { id: "a3", x: 28, y: 39 },
  A4: { id: "a4", x: 61, y: 37 },
  A5: { id: "a5", x: 31, y: 61 },
  A6: { id: "a6", x: 53, y: 57 },
  A7: { id: "a7", x: 72, y: 63 },
  A8: { id: "a8", x: 55, y: 78 },
  A9: { id: "a9", x: 84, y: 79 },
};

const COPY = {
  it: {
    alertMeta: "Protezione Civile FVG",
    alertLanguageNotice: "",
    alertsLabel: "Avvisi ufficiali",
    fallbackUpdated: "Aggiornamento in verifica",
    updatedPrefix: "Aggiornato",
    linkLabel: "www.meteo.fvg.it",
    mapAlt: "Mappa Meteo Friul con dati previsionali ARPA FVG OSMER",
    pendingBulletinSummary: "Non ancora emesso",
    pendingBulletinText: "Bollettino non ancora emesso.",
    officialAlertMultipleLabel: "allerte ufficiali",
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
    officialAlertSeverityLabels: {
      orange: "Allerta arancione in FVG",
      red: "Allerta rossa in FVG",
      yellow: "Allerta gialla in FVG",
    },
    officialAlertSingleLabel: "Allerta ufficiale",
    source: "OSMER ARPA FVG",
    summaryByCondition: {
      cloud: "Cielo nuvoloso",
      fog: "Nebbia o foschia",
      partly: "Sole e nubi",
      rain: "Piogge o rovesci",
      snow: "Neve",
      storm: "Temporali possibili",
      sun: "Tempo stabile",
    },
    unreachableSummary: "Dati non raggiungibili",
    unreachableText: "Non riusciamo a raggiungere la fonte ARPA FVG - OSMER. Riprova piu tardi.",
    unavailableSummary: "Dati OSMER non disponibili",
    unavailableText: "Il bollettino non e' disponibile in questo momento. Consulta la fonte ARPA FVG - OSMER dal link sotto.",
  },
  fur: {
    alertMeta: "Protezion Civîl FVG",
    alertLanguageNotice: "Test uficiâl in talian - FUR in revision",
    pendingBulletinSummary: "No ancjemò publicât",
    pendingBulletinText: "Boletin no ancjemò publicât.",
    alertsLabel: "Avis uficiâi",
    fallbackUpdated: "Inzornament in verifiche",
    updatedPrefix: "Inzornat",
    linkLabel: "www.meteo.fvg.it",
    mapAlt: "Mape Meteo Friul cun dâts previsionâi ARPA FVG OSMER",
    officialAlertMultipleLabel: "alertis uficiâls",
    officialAlertPhenomenonLabels: {
      cold: "Alerte fret",
      fog: "Alerte nebie",
      hail: "Alerte tampierie",
      heat: "Alerte cjalt",
      ice: "Alerte glaç",
      rain: "Alerte pluie",
      snow: "Alerte nef",
      storm: "Alerte temporâi",
      wind: "Alerte vint",
    },
    officialAlertSeverityLabels: {
      orange: "Alerte narançon in FVG",
      red: "Alerte rosse in FVG",
      yellow: "Alerte zale in FVG",
    },
    officialAlertSingleLabel: "Alerte uficiâl",
    source: "OSMER ARPA FVG",
    summaryByCondition: {
      cloud: "Cîl nul",
      fog: "Nebie o foschie",
      partly: "Soreli e nuls",
      rain: "Pluiis o rovas",
      snow: "Nef",
      storm: "Temporâi pussibii",
      sun: "Timp stabil",
    },
    unreachableSummary: "Dâts no acessibii",
    unreachableText: "No rivin a contatâ la font ARPA FVG - OSMER. Torne a provâ plui tart.",
    unavailableSummary: "Dats OSMER no disponibii",
    unavailableText: "Il boletin OSMER nol e disponibil cumo. Consulte la font ARPA FVG - OSMER dal leam sot.",
  },
};

const EMPTY_DAY_LABELS = {
  today: { it: "Oggi", fur: "Vuê" },
  tomorrow: { it: "Domani", fur: "Doman" },
  afterTomorrow: { it: "Dopodomani", fur: "Dopodoman" },
  plus3: { it: "+3", fur: "+3" },
  plus4: { it: "+4", fur: "+4" },
};

const FUR_WEEKDAY_LABELS = [
  "Domenie",
  "Lunis",
  "Martars",
  "Miercus",
  "Joibe",
  "Vinars",
  "Sabide",
];

const FUR_MONTH_LABELS = [
  "Zenâr",
  "Fevrâr",
  "Març",
  "Avrîl",
  "Mai",
  "Jugn",
  "Lui",
  "Avost",
  "Setembar",
  "Otubar",
  "Novembar",
  "Dicembar",
];

function getCopy(language) {
  return COPY[language === "fur" ? "fur" : "it"];
}

function hasDisplayValue(value) {
  return value !== null && value !== undefined && value !== "";
}

function normalizeSpaces(value) {
  return String(value || "").replace(/\s+/g, " ").trim();
}

function sentenceCase(value) {
  const text = normalizeSpaces(value);
  if (!text) return "";

  return `${text.charAt(0).toUpperCase()}${text.slice(1)}`;
}

function getNowValue(now) {
  return typeof now === "function" ? now() : now;
}

function formatDateKey(value) {
  if (!value) return "";

  if (typeof value === "string" && /^\d{4}-\d{2}-\d{2}$/.test(value)) {
    return value;
  }

  const date = value instanceof Date ? value : new Date(value);
  if (Number.isNaN(date.getTime())) return "";

  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");

  return `${year}-${month}-${day}`;
}

function addDaysToDateKey(value, daysToAdd = 1) {
  if (!value) return "";

  const date = new Date(`${value}T12:00:00`);
  if (Number.isNaN(date.getTime())) return "";

  date.setDate(date.getDate() + daysToAdd);
  return formatDateKey(date);
}

function getModelForecastDays(forecast = {}) {
  if (Array.isArray(forecast?.forecast)) return forecast.forecast;
  if (Array.isArray(forecast?.daily)) return forecast.daily;
  if (Array.isArray(forecast?.days)) return forecast.days;
  return [];
}

function getOfficialForecasts(forecast = {}, language = "it") {
  const languageKey = language === "fur" ? "fur" : "it";
  const localized = forecast?.official?.[languageKey]?.forecasts;
  const italian = forecast?.official?.it?.forecasts;

  if (Array.isArray(localized) && localized.length) return localized;
  return Array.isArray(italian) ? italian : [];
}

function getOfficialCalendarForecasts(forecast = {}, fallbackForecasts = []) {
  const italian = forecast?.official?.it?.forecasts;
  if (Array.isArray(italian) && italian.length) return italian;
  return fallbackForecasts;
}

function getOfficialForecastsByDate(forecasts = []) {
  return new Map(
    forecasts
      .filter((day) => day?.date)
      .map((day) => [day.date, day]),
  );
}

function getOsmerStructuredForecast(forecast = {}) {
  return forecast?.osmer_structured || forecast?.osmerStructured || null;
}

function getStructuredDays(osmerStructured = null) {
  return Array.isArray(osmerStructured?.days) ? osmerStructured.days.filter(Boolean) : [];
}

function buildOsmerStructuredSource(osmerStructured = null, structuredDay = null) {
  const daySource = structuredDay?.osmer_structured_source
    || structuredDay?.osmerStructuredSource
    || null;
  const source = daySource || osmerStructured;
  if (!source) return null;

  return {
    dataEmission: source.data_emissione || source.dataEmission || "",
    fonte: source.source_kind || source.fonte || structuredDay?.source_kind || osmerStructured?.fonte || "",
    id: source.id_emissione || source.id || "",
    isStale: Boolean(source.is_stale ?? source.isStale),
    parserVersion: source.parser_version || source.parserVersion || "",
    publishedAt: source.published_at || source.publishedAt || "",
    rawHash: source.raw_hash || source.rawHash || "",
    requestedDate: source.requested_date || source.requestedDate || "",
    schemaVersion: source.schema_version || source.schemaVersion || "",
    sourceDate: source.source_date || source.sourceDate || "",
    sourceStatus: source.source_status || source.sourceStatus || "",
    sourceUrl: source.source_url || source.sourceUrl || "",
    updatedAt: source.updated_at || source.updatedAt || "",
  };
}

function getStructuredDaysByDate(osmerStructured = null) {
  return new Map(
    getStructuredDays(osmerStructured)
      .filter((day) => day?.valid_date)
      .map((day) => [day.valid_date, day]),
  );
}

function getModelDaysByDate(modelDays = []) {
  return new Map(
    modelDays
      .filter((day) => day?.date)
      .map((day) => [day.date, day]),
  );
}

function buildForecastDateSlots(officialForecasts = [], structuredDays = []) {
  let lastDate = "";

  return DAY_IDS.map((_, index) => {
    const explicitDate = officialForecasts[index]?.date || structuredDays[index]?.valid_date || "";
    if (explicitDate) {
      lastDate = explicitDate;
      return explicitDate;
    }

    if (lastDate) {
      lastDate = addDaysToDateKey(lastDate);
      return lastDate;
    }

    return "";
  });
}

function formatDateLabel(value, fallback = "", language = "it") {
  if (!value) return fallback;

  const date = new Date(`${value}T12:00:00`);
  if (Number.isNaN(date.getTime())) return fallback || String(value);

  if (language === "fur") {
    return `${FUR_WEEKDAY_LABELS[date.getDay()]} ${date.getDate()} ${FUR_MONTH_LABELS[date.getMonth()]}`;
  }

  return new Intl.DateTimeFormat("it-IT", {
    day: "numeric",
    month: "long",
    weekday: "long",
  }).format(date);
}

function formatWeekdayTabLabel(value, fallback = "", language = "it") {
  if (!value) return fallback;

  const date = new Date(`${value}T12:00:00`);
  if (Number.isNaN(date.getTime())) return fallback || String(value);

  if (language === "fur") {
    return FUR_WEEKDAY_LABELS[date.getDay()] || fallback || String(value);
  }

  return sentenceCase(new Intl.DateTimeFormat("it-IT", { weekday: "long" }).format(date));
}

function formatFirstTabLabel(value, fallback = "", language = "it", now = new Date()) {
  const copyKey = language === "fur" ? "fur" : "it";
  const forecastDateKey = formatDateKey(value);
  const todayKey = formatDateKey(getNowValue(now));

  if (forecastDateKey && todayKey && forecastDateKey === todayKey) {
    return EMPTY_DAY_LABELS.today[copyKey];
  }

  return formatWeekdayTabLabel(value, fallback, language);
}

function compactDateLabel(value, fallback = "") {
  if (!value) return fallback;

  const date = new Date(`${value}T12:00:00`);
  if (Number.isNaN(date.getTime())) return fallback || String(value);

  return new Intl.DateTimeFormat("it-IT", {
    day: "2-digit",
    month: "2-digit",
  }).format(date);
}

function formatUpdatedLabel(value, copy) {
  if (!value) return copy.fallbackUpdated;
  const updatedPrefix = copy.updatedPrefix || "Aggiornato";

  const ddmmyyyy = String(value).match(/^(\d{2})-(\d{2})-(\d{4})\s+(\d{2}:\d{2})/);
  if (ddmmyyyy) {
    return `${updatedPrefix} ${ddmmyyyy[1]}/${ddmmyyyy[2]} - ${ddmmyyyy[4]}`;
  }

  const date = new Date(value);
  if (!Number.isNaN(date.getTime())) {
    return `${updatedPrefix} ${new Intl.DateTimeFormat("it-IT", {
      day: "2-digit",
      month: "2-digit",
      timeZone: "Europe/Rome",
    }).format(date)} - ${new Intl.DateTimeFormat("it-IT", {
      hour: "2-digit",
      minute: "2-digit",
      timeZone: "Europe/Rome",
    }).format(date)}`;
  }

  return normalizeSpaces(value) || copy.fallbackUpdated;
}

function getBulletinUpdatedValue(forecast = {}, days = [], osmerStructured = null) {
  return (
    days.find((day) => hasDisplayValue(day?.emission))?.emission ||
    forecast?.official?.it?.updated_at ||
    forecast?.official?.it?.updatedAt ||
    osmerStructured?.data_emissione ||
    osmerStructured?.source_date ||
    ""
  );
}

function getReliabilityFromStructuredDay(structuredDay = null, fallback = "") {
  const values = Object.values(structuredDay?.areas9 || {})
    .map((area) => Number(area?.attendibilita?.value ?? area?.attendibilita))
    .filter(Number.isFinite);

  if (!values.length) return fallback;

  const average = values.reduce((sum, value) => sum + value, 0) / values.length;
  return `${Math.round(average)}%`;
}

function getMapGlyphType(markerState = {}) {
  const value = String(markerState.condition || "").toLowerCase();

  if (markerState.lightning || markerState.emphasis === "storm" || value.includes("tempor")) return "storm";
  if (value.includes("neve")) return "snow";
  if (value.includes("nebbia") || value.includes("foschia")) return "fog";
  if (value.includes("piogg") || value.includes("rovesc")) return "rain";
  if (value.includes("sereno") || value.includes("sole")) return "sun";

  return "partly";
}

function buildMapPoints(structuredDay = null) {
  const areas9 = structuredDay?.areas9 || null;
  if (!areas9) return [];

  return Object.entries(AREA_MAP_POINTS)
    .map(([areaId, point]) => {
      const area = areas9[areaId];
      if (!area) return null;

      return {
        ...point,
        osmerAreaId: areaId,
        type: getMapGlyphType(mapOsmerAreaToCondition(area)),
      };
    })
    .filter(Boolean);
}

function getFirstMountainValue(structuredDay = null, key) {
  return Object.values(structuredDay?.areas9 || {})
    .map((area) => area?.mountain?.[key])
    .find((value) => Number.isFinite(Number(value)));
}

function buildMapBadges(structuredDay = null) {
  const temp2000 = getFirstMountainValue(structuredDay, "temperature_2000");
  const temp1000 = getFirstMountainValue(structuredDay, "temperature_1000");
  const badges = [];

  if (Number.isFinite(Number(temp2000))) {
    badges.push({ id: "quota-2000", tone: "mountain", x: 29, y: 29, value: `2000m ${Math.round(Number(temp2000))}°C` });
  }

  if (Number.isFinite(Number(temp1000))) {
    badges.push({ id: "quota-1000", tone: "mountain", x: 25, y: 43, value: `1000m ${Math.round(Number(temp1000))}°C` });
  }

  return badges;
}

function getSummaryLabel({ modelDay, officialDay, structuredDay, copy }) {
  const explicit = officialDay?.title || officialDay?.headline;
  if (explicit) return sentenceCase(explicit);

  const temporalSummary = summarizeOsmerTemporalDay(structuredDay || officialDay || {});
  if (temporalSummary.source !== "fallback") {
    return copy.summaryByCondition[temporalSummary.tabCondition] || copy.summaryByCondition.partly;
  }

  if (modelDay?.condition) return sentenceCase(modelDay.condition);

  return copy.summaryByCondition[temporalSummary.tabCondition] || copy.summaryByCondition.partly;
}

function getOfficialDayText(officialDay = {}, modelDay = {}) {
  return normalizeSpaces(
    officialDay.text ||
    officialDay.official_text ||
    modelDay.official_text ||
    modelDay.text ||
    modelDay.displayText ||
    "",
  );
}

function buildBulletinDays({
  allowFixtureFallback = false,
  fallbackDays = BULLETIN_DAYS,
  forecast = {},
  language = "it",
  now = new Date(),
}) {
  const copy = getCopy(language);
  const officialForecasts = getOfficialForecasts(forecast, language);
  const calendarOfficialForecasts = getOfficialCalendarForecasts(forecast, officialForecasts);
  const officialForecastsByDate = getOfficialForecastsByDate(officialForecasts);
  const modelDays = getModelForecastDays(forecast);
  const modelDaysByDate = getModelDaysByDate(modelDays);
  const osmerStructured = getOsmerStructuredForecast(forecast);
  const structuredDays = getStructuredDays(osmerStructured);
  const structuredDaysByDate = getStructuredDaysByDate(osmerStructured);
  const sourceDayCount = Math.max(calendarOfficialForecasts.length, structuredDays.length);
  const forecastDateSlots = buildForecastDateSlots(calendarOfficialForecasts, structuredDays);
  const maxDays = Math.min(
    DAY_IDS.length,
    allowFixtureFallback || sourceDayCount ? DAY_IDS.length : 1,
  );

  const days = DAY_IDS.slice(0, maxDays).map((id, index) => {
    const fallbackDay = fallbackDays[index] || fallbackDays[fallbackDays.length - 1] || {};
    const fixtureDay = allowFixtureFallback ? fallbackDay : {};
    const calendarOfficialDay = calendarOfficialForecasts[index] || {};
    const indexedOfficialDay = officialForecasts[index] || {};
    const indexedModelDay = modelDays[index] || {};
    const indexedStructuredDay = structuredDays[index] || {};
    const forecastDate = calendarOfficialDay.date || indexedStructuredDay.valid_date || forecastDateSlots[index] || indexedModelDay.date || fixtureDay.valid_date || "";
    const officialDayByDate = (forecastDate && officialForecastsByDate.get(forecastDate)) || {};
    const officialDay = Object.keys(indexedOfficialDay).length
      ? indexedOfficialDay
      : officialDayByDate.date === forecastDate
        ? officialDayByDate
        : calendarOfficialDay;
    const hasOfficialCalendarDay = Boolean(calendarOfficialDay.date || indexedStructuredDay.valid_date);
    const isPendingSlot = Boolean(!allowFixtureFallback && sourceDayCount && index >= sourceDayCount);
    const modelDay = isPendingSlot
      ? {}
      : (forecastDate && modelDaysByDate.get(forecastDate)) || (!hasOfficialCalendarDay ? indexedModelDay : {});
    const structuredDay =
      getOsmerStructuredDay(modelDay) ||
      (forecastDate && structuredDaysByDate.get(forecastDate)) ||
      (!officialDay.date && indexedStructuredDay?.valid_date === forecastDate ? indexedStructuredDay : null) ||
      null;
    const structuredSource = buildOsmerStructuredSource(osmerStructured, structuredDay);
    const structuredContract = structuredDay
      ? classifyOsmerStructuredDay(structuredDay, { snapshot: osmerStructured })
      : null;
    const canRenderNativeMap = Boolean(structuredContract?.canRenderNativeMap);
    const displayStructuredDay = canRenderNativeMap ? structuredDay : null;
    const officialText = getOfficialDayText(officialDay, modelDay);
    const officialEmission = normalizeSpaces(
      officialDay.emission ||
      modelDay.emission ||
      calendarOfficialDay.emission ||
      "",
    );
    const hasOfficialText = Boolean(officialText);
    const mapPoints = canRenderNativeMap ? buildMapPoints(displayStructuredDay) : [];
    const hasData = Boolean(hasOfficialText || canRenderNativeMap);
    const isPendingBulletin = Boolean(!allowFixtureFallback && sourceDayCount && forecastDate && !hasData);
    const labels = fallbackDay.labels || { [language === "fur" ? "fur" : "it"]: id };
    const copyKey = language === "fur" ? "fur" : "it";
    const defaultDayLabels = EMPTY_DAY_LABELS[id] || EMPTY_DAY_LABELS.today;
    const fallbackTabLabel = index === 0
      ? (fallbackDay.labels || defaultDayLabels)?.[copyKey]
      : fallbackDay.weekdayLabels?.[copyKey] || (fallbackDay.labels || defaultDayLabels)?.[copyKey];

    return {
      ...fixtureDay,
      id,
      compactDateLabel: compactDateLabel(forecastDate, fixtureDay.compactDateLabel || ""),
      date: officialDay.date_label || formatDateLabel(forecastDate, fixtureDay.date || labels[language === "fur" ? "fur" : "it"] || "", language),
      emission: officialEmission,
      focus: fixtureDay.focus || [],
      forecastDate,
      hasOfficialText,
      hasStructuredMap: canRenderNativeMap && mapPoints.length === 9,
      labels: fallbackDay.labels || EMPTY_DAY_LABELS[id] || EMPTY_DAY_LABELS.today,
      mapAlt: `${copy.mapAlt}${forecastDate ? ` ${forecastDate}` : ""}`,
      mapBadges: canRenderNativeMap ? buildMapBadges(displayStructuredDay) : fixtureDay.mapBadges || [],
      mapPoints: mapPoints.length ? mapPoints : fixtureDay.mapPoints || [],
      osmerStructuredDay: structuredDay,
      osmerStructuredContract: structuredContract,
      osmerStructuredSource: structuredDay ? structuredSource : null,
      reliability: canRenderNativeMap
        ? getReliabilityFromStructuredDay(displayStructuredDay, officialDay.reliability || fixtureDay.reliability || "")
        : fixtureDay.reliability || "",
      source: isPendingBulletin ? "pending_official" : canRenderNativeMap ? "osmer_structured" : hasOfficialText ? "official_text" : allowFixtureFallback ? "fixture_fallback" : "unavailable",
      summary: isPendingBulletin ? copy.pendingBulletinSummary : hasData ? getSummaryLabel({ modelDay, officialDay, structuredDay: displayStructuredDay, copy }) : fixtureDay.summary || copy.unavailableSummary,
      tabLabel: index === 0
        ? formatFirstTabLabel(forecastDate, fallbackTabLabel, language, now)
        : formatWeekdayTabLabel(forecastDate, fallbackTabLabel, language),
      text: isPendingBulletin ? copy.pendingBulletinText : hasOfficialText ? officialText : fixtureDay.text || copy.unavailableText,
      weekdayLabels: fallbackDay.weekdayLabels,
    };
  });

  return days;
}

function formatAlertValidity(alert, copy) {
  const rawValue = alert?.valid_to || alert?.validTo || alert?.expires_at || alert?.expiresAt;
  if (!rawValue) return "";

  const date = new Date(rawValue);
  if (!Number.isFinite(date.getTime())) return "";

  const dateLabel = new Intl.DateTimeFormat("it-IT", {
    day: "numeric",
    month: "long",
    timeZone: "Europe/Rome",
  }).format(date);
  const timeLabel = new Intl.DateTimeFormat("it-IT", {
    hour: "2-digit",
    minute: "2-digit",
    timeZone: "Europe/Rome",
  }).format(date);

  if (copy.alertMeta === COPY.fur.alertMeta) {
    const furParts = new Intl.DateTimeFormat("en-GB", {
      day: "numeric",
      month: "numeric",
      timeZone: "Europe/Rome",
    }).formatToParts(date);
    const day = furParts.find((part) => part.type === "day")?.value || "";
    const monthIndex = Number(furParts.find((part) => part.type === "month")?.value || 0) - 1;
    const month = FUR_MONTH_LABELS[monthIndex] || "";

    return `Valide fin aes ${timeLabel} dai ${day} di ${month}`;
  }

  return `Valida fino alle ${timeLabel} del ${dateLabel}`;
}

function normalizeOfficialAlertLabels(value) {
  if (!Array.isArray(value)) return [];

  return value.map((item) => {
    if (typeof item === "string") return item.trim();
    if (!item || typeof item !== "object") return "";
    return String(item.label || item.name || item.id || "").trim();
  }).filter(Boolean);
}

function getOfficialAlertArea(alert) {
  const area = String(alert?.area || "").trim();
  if (area) return area;

  return normalizeOfficialAlertLabels(alert?.zones).join(" · ");
}

function getOfficialAlertSourceLabel(alert, fallback) {
  const source = alert?.source;
  if (source && typeof source === "object") {
    const sourceName = String(source.name || source.label || "").trim();
    if (sourceName) return sourceName;
  }

  const sourceName = typeof source === "string" ? source.trim() : "";
  return sourceName || fallback;
}

export function buildOfficialAlertPresentation(
  officialAlerts,
  { language = "it", now } = {},
) {
  const copy = getCopy(language);
  const alertSummary = buildOfficialAlertSummary(officialAlerts, copy, { now });
  const alert = getPrimaryOfficialAlert(officialAlerts, { now });

  if (!alertSummary) return null;

  const content = formatOfficialAlertContent(alert);

  return {
    ...alertSummary,
    area: getOfficialAlertArea(alert),
    languageNotice: copy.alertLanguageNotice,
    levels: normalizeOfficialAlertLabels(alert?.levels),
    meta: copy.alertMeta,
    mixedLevels: Boolean(alert?.mixed_levels || alert?.mixedLevels),
    paragraphs: content.paragraphs,
    risks: normalizeOfficialAlertLabels(alert?.risks),
    sourceLabel: getOfficialAlertSourceLabel(alert, copy.alertMeta),
    text: content.text || formatOfficialAlertText(alert),
    validFrom: alert?.valid_from || alert?.validFrom || "",
    validTo: alert?.valid_to || alert?.validTo || alert?.expires_at || alert?.expiresAt || "",
    validityIncludedInText: content.includesValidity,
    validityLabel: formatAlertValidity(alert, copy),
    zones: normalizeOfficialAlertLabels(alert?.zones),
  };
}

export function buildBulletinViewModel(data = {}, {
  allowFixtureFallback = false,
  fallbackDays = BULLETIN_DAYS,
  language = "it",
  now = new Date(),
} = {}) {
  const copy = getCopy(language);
  const sourceUnreachable = Boolean(data?.error && !data?.forecast);
  const sourceStaleVisible = Boolean(data?.isStale && data?.error && data?.forecast);
  const forecast = sourceUnreachable ? {} : data?.forecast || {};
  const osmerStructured = getOsmerStructuredForecast(forecast);
  const days = buildBulletinDays({ allowFixtureFallback, fallbackDays, forecast, language, now }).map((day) => {
    if (!sourceUnreachable) return day;

    return {
      ...day,
      focus: [],
      hasOfficialText: false,
      hasStructuredMap: false,
      mapBadges: [],
      mapPoints: [],
      reliability: "",
      source: "source_unreachable",
      summary: copy.unreachableSummary || COPY.it.unreachableSummary,
      text: copy.unreachableText || COPY.it.unreachableText,
    };
  });
  const updatedValue = getBulletinUpdatedValue(forecast, days, osmerStructured);
  const structuredDays = days.filter((day) => day.source === "osmer_structured").length;
  const officialTextDays = days.filter((day) => day.hasOfficialText).length;

  return {
    activeDayId: days[0]?.id || "today",
    alert: buildOfficialAlertPresentation(
      data?.officialAlerts || data?.official_alerts || null,
      { language, now },
    ),
    days,
    diagnostics: {
      officialTextDays,
      structuredDays,
    },
    hasOfficialText: officialTextDays > 0,
    hasStructuredMap: structuredDays > 0,
    source: {
      label: copy.source,
      linkLabel: copy.linkLabel,
      updatedLabel: formatUpdatedLabel(updatedValue, copy),
      url: BULLETIN_SOURCE_URL,
    },
    status: sourceUnreachable
      ? "source_unreachable"
      : structuredDays > 0 || officialTextDays > 0
        ? sourceStaleVisible ? "stale_visible" : "ready"
        : allowFixtureFallback
          ? "fixture_fallback"
          : "unavailable",
  };
}
