import {
  buildAlmanacData,
  getAlmanacSeasonInfo,
  localizeAlmanacRecord,
} from "../../domain/almanac/almanacData";
import {
  getAlmanacCopy,
  getAlmanacCulturalSourceLabel,
  getAlmanacHiddenOtherSaintsLabel,
  getMoonNextHint,
} from "../../copy/almanacCopy";

const FUR_WEEKDAYS = ["Domenie", "Lunis", "Martars", "Miercus", "Joibe", "Vinars", "Sabide"];
const FUR_MONTHS = ["Zenâr", "Fevrâr", "Març", "Avrîl", "Mai", "Jugn", "Lui", "Avost", "Setembar", "Otubar", "Novembar", "Dicembar"];

function capitalizeFirst(value) {
  return value ? `${value.charAt(0).toUpperCase()}${value.slice(1)}` : "";
}

function formatDateLabel(date, language = "it") {
  if (language === "fur") {
    return `${FUR_WEEKDAYS[date.getDay()]} ${date.getDate()} ${FUR_MONTHS[date.getMonth()]}`;
  }

  return capitalizeFirst(new Intl.DateTimeFormat("it-IT", {
    day: "numeric",
    month: "long",
    weekday: "long",
  }).format(date));
}

function getSaintDisplayName(saint, language = "it") {
  if (!saint) return "";

  if (language !== "fur") return saint.name_it || saint.name_fur || "";

  return saint.name_fur_status === "curated" && saint.name_fur
    ? saint.name_fur
    : saint.name_it || saint.name_fur || "";
}

function buildSaintBody(saint, language = "it") {
  return language === "fur"
    ? saint?.description_fur_status === "curated" ? saint.description_fur : ""
    : saint?.description_it || "";
}

function normalizeSaintName(value) {
  return String(value || "")
    .replace(/\s*\([^)]*\)\s*$/u, "")
    .replace(/\s+(?:[A-Z]\.\s*){2,}$/u, "")
    .replace(/\s+/g, " ")
    .trim();
}

function uniqueNames(names) {
  const seen = new Set();

  return names.filter((name) => {
    const key = name.toLocaleLowerCase("it-IT");
    if (!name || seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}

function buildSaintNameDays(saint, language = "it") {
  const names = Array.isArray(saint?.all_names) ? saint.all_names : [];

  return uniqueNames(names
    .filter((item) => item?.is_name_day)
    .map((item) => normalizeSaintName(
      language === "fur" && item.name_fur_status === "curated"
        ? item.name_fur
        : item.name_it || item.name_fur,
    )));
}

function buildOtherSaints(saint, language = "it") {
  const names = Array.isArray(saint?.all_names) ? saint.all_names : [];

  return uniqueNames(names
    .filter((item) => (
      item?.name_it
      && item.name_it !== saint.name_it
      && !item.is_name_day
      && !item.is_secondary_name_day
    ))
    .map((item) => normalizeSaintName(getSaintDisplayName(item, language))));
}

function formatNumber(value, fractionDigits = 1) {
  return Number(value).toFixed(fractionDigits);
}

function formatLocalDateKey(date) {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");

  return `${year}-${month}-${day}`;
}

function getVerifiedSolarEventNotice(event, date, language) {
  if (
    event?.type !== "solar_eclipse"
    || event?.verified !== true
    || event?.visibleFromLocation !== true
    || event?.date !== formatLocalDateKey(date)
  ) {
    return "";
  }

  if (!event.notice || typeof event.notice !== "object") return "";

  return language === "fur"
    ? String(event.notice.fur || "").trim()
    : String(event.notice.it || "").trim();
}

export function buildAlmanacViewModel({
  date = new Date(),
  language = "it",
  location,
  now = new Date(),
  solarEvent = null,
  weather = null,
} = {}) {
  const languageKey = language === "fur" ? "fur" : "it";
  const copy = getAlmanacCopy(languageKey);
  const data = buildAlmanacData({ date, location, now, weather });
  const season = getAlmanacSeasonInfo(data.date, languageKey);
  const moonCycleProgress = Math.round(data.moon.cyclePercent * 100);
  const traditionBody =
    localizeAlmanacRecord(data.tradition?.appShort, languageKey) ||
    localizeAlmanacRecord(data.tradition?.text, languageKey);
  const saintNameDays = buildSaintNameDays(data.saint, languageKey);
  const otherSaints = buildOtherSaints(data.saint, languageKey);
  const otherSaintsPreview = otherSaints.slice(0, 3);
  const hiddenOtherSaintsCount = Math.max(0, otherSaints.length - otherSaintsPreview.length);
  const solarEventNotice = getVerifiedSolarEventNotice(solarEvent, data.date, languageKey);

  return {
    dayLabel: formatDateLabel(data.date, languageKey),
    skyDetailsLabel: languageKey === "fur" ? "Detais dal cîl" : "Dettagli del cielo",
    skyFacts: [
      { label: languageKey === "fur" ? "Altece massime dal Soreli" : "Altezza massima del Sole", shortLabel: languageKey === "fur" ? "Altece Soreli" : "Culmine Sole", value: `${data.sun.maxAltitudeDegrees}°`, note: languageKey === "fur" ? "Sore l'orizont" : "Sopra l’orizzonte" },
      { label: copy.lunarAgeLabel, value: new Intl.NumberFormat("it-IT", { maximumFractionDigits: 1 }).format(data.moon.age), note: languageKey === "fur" ? "Dîs" : "Giorni" },
      { label: languageKey === "fur" ? "Lune iluminade" : "Luna illuminata", value: `${data.moon.illuminationPercent}%`, note: `${languageKey === "fur" ? "Cicli" : "Ciclo"} ${moonCycleProgress}%` },
    ],
    dayProgressLabel: languageKey === "fur" ? `Dì ${data.dayOfYear}` : `Giorno ${data.dayOfYear}`,
    discoverCta: copy.discoverCta,
    seasonLabel: season.label,
    sun: {
      cycle: data.sun.cycle ? {
        ...data.sun.cycle,
        label: data.sun.cycle.isDay ? (languageKey === "fur" ? "Dì" : "Giorno") : (languageKey === "fur" ? "Gnot" : "Notte"),
        startLabel: data.sun.cycle.isDay ? (languageKey === "fur" ? "Albe" : "Alba") : (languageKey === "fur" ? "Tramont" : "Tramonto"),
        endLabel: data.sun.cycle.isDay ? (languageKey === "fur" ? "Tramont" : "Tramonto") : (languageKey === "fur" ? "Albe" : "Alba"),
      } : null,
      daylight: data.sun.daylight,
      daylightProgress: data.sun.daylightProgress,
      eventNotice: solarEventNotice,
      daylightSummaryLabel: languageKey === "fur" ? "Lus dal dì" : "Luce del giorno",
      solarSummary: languageKey === "fur"
        ? `Soreli alt · ${data.sun.maxAltitudeDegrees}° sore l'orizont`
        : `Sole alto · ${data.sun.maxAltitudeDegrees}° sopra l'orizzonte`,
      sunrise: data.sun.sunrise,
      sunriseLabel: languageKey === "fur" ? "Albe" : "Alba",
      sunset: data.sun.sunset,
      sunsetLabel: languageKey === "fur" ? "Tramont" : "Tramonto",
      title: languageKey === "fur" ? "Soreli" : "Sole",
    },
    moon: {
      nightDuration: data.sun.nightDuration,
      nightLabel: languageKey === "fur" ? "Durade de gnot" : "Durata della notte",
      ageLabel: copy.lunarAgeLabel,
      ageValue: languageKey === "fur"
        ? `${formatNumber(data.moon.age)} dîs`
        : `${formatNumber(data.moon.age)} giorni`,
      cycleProgress: moonCycleProgress,
      cycleSummary: languageKey === "fur"
        ? `${data.moon.illuminationPercent}% iluminade · cicli ${moonCycleProgress}%`
        : `${data.moon.illuminationPercent}% illuminata · ciclo ${moonCycleProgress}%`,
      next: getMoonNextHint(data.moon, languageKey),
      phase: data.moon.label[languageKey] || data.moon.label.it,
      title: copy.moonTitle,
    },
    proverb: {
      body: languageKey === "fur" ? data.proverb?.fur : data.proverb?.it,
      title: languageKey === "fur" ? "Proverbi" : "Proverbio",
    },
    saint: {
      biography: languageKey === "it" && Array.isArray(data.saint?.biography_it) ? data.saint.biography_it : [],
      biographySource: languageKey === "it" ? data.saint?.biography_source || "" : "",
      body: buildSaintBody(data.saint, languageKey),
      role: languageKey === "fur" ? "" : data.saint?.role_it || "",
      sourceLabel: data.saint?.profile_source || data.saint?.hierarchy_source || "",
      sourceUrl: /^https:\/\//u.test(data.saint?.profile_source_url || data.saint?.source_url || "")
        ? data.saint.profile_source_url || data.saint.source_url : "",
      label: getSaintDisplayName(data.saint, languageKey),
      nameDayLabel: copy.nameDayPrefix,
      nameDays: saintNameDays,
      otherSaints,
      otherSaintsCollapseLabel: copy.otherSaintsCollapseLabel,
      otherSaintsLabel: copy.otherSaintsLabel,
      otherSaintsPreview,
      otherSaintsRemainder: hiddenOtherSaintsCount
        ? getAlmanacHiddenOtherSaintsLabel(hiddenOtherSaintsCount, languageKey)
        : "",
      title: copy.saintTitle,
    },
    tradition: {
      body: traditionBody,
      label: localizeAlmanacRecord(data.tradition?.title, languageKey),
      source: getAlmanacCulturalSourceLabel(data.tradition?.source, languageKey),
      title: copy.traditionTitle,
    },
    earth: {
      items: data.tips
        .map((item) => (languageKey === "fur" ? item.fur : item.it))
        .filter(Boolean),
      title: copy.farmingTitle,
    },
    raw: data,
  };
}
